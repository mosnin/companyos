#!/usr/bin/env python3
"""Persist federated reconciliation and deliver lease-fenced commands.

This module extends the existing project-local Company OS SQLite authority. It
does not create a second control plane and performs no provider, task, network,
scheduler, or production action.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any, Mapping


SKILL_ROOT = Path(__file__).resolve().parents[1]
COMPANY_OS_ROOT = SKILL_ROOT.parent
RECONCILER_PATH = SKILL_ROOT / "scripts" / "reconcile_federated_kernel.py"
CONTROL_STORE_PATH = (
    COMPANY_OS_ROOT / "elastic-company-os" / "scripts" / "control_store.py"
)

EXTENSION_SCHEMA = "company-os.federated-runtime-store.v1"
EXTENSION_SCHEMA_VERSION = 1
COMMAND_SCHEMA = "company-os.federated-runtime-command.v1"
OUTBOX_CHANNEL = "federated-runtime"
COMMAND_KINDS = {
    "archive-stale-terminal",
    "native-next-action",
    "observe-role",
    "persist-admission-intent",
    "quarantine-terminal",
    "request-cancellation",
    "settle-terminal",
}
TERMINAL_OUTBOX_STATUSES = {"succeeded", "cancelled"}
HEX64 = re.compile(r"[0-9a-f]{64}")


class PersistenceError(ValueError):
    """A closed persistence, delivery, or audit failure."""


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PersistenceError(f"cannot load required module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RECONCILE = load_module("company_os_federated_reconciler_for_store", RECONCILER_PATH)
STORE = load_module("company_os_control_store_for_federated_runtime", CONTROL_STORE_PATH)


EXTENSION_SQL = """
CREATE TABLE IF NOT EXISTS federated_runtime_metadata (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  schema_name TEXT NOT NULL,
  schema_version INTEGER NOT NULL,
  project_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS federated_kernels (
  project_id TEXT NOT NULL,
  kernel_digest TEXT NOT NULL,
  kernel_json TEXT NOT NULL,
  kernel_sha256 TEXT NOT NULL,
  first_seen_revision INTEGER NOT NULL REFERENCES state_revisions(revision),
  PRIMARY KEY (project_id, kernel_digest)
);
CREATE TABLE IF NOT EXISTS federated_reconciliation_plans (
  project_id TEXT NOT NULL,
  plan_key TEXT NOT NULL,
  stream_key TEXT NOT NULL,
  kernel_digest TEXT NOT NULL,
  generation INTEGER NOT NULL CHECK (generation > 0),
  cycle_id TEXT NOT NULL,
  parent_runtime_id TEXT NOT NULL,
  request_digest TEXT NOT NULL,
  snapshot_cursor INTEGER NOT NULL CHECK (snapshot_cursor >= 0),
  snapshot_digest TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ready','deferred','blocked')),
  request_json TEXT NOT NULL,
  request_sha256 TEXT NOT NULL,
  plan_json TEXT NOT NULL,
  plan_sha256 TEXT NOT NULL,
  state_revision INTEGER NOT NULL REFERENCES state_revisions(revision),
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id, plan_key),
  UNIQUE (project_id, stream_key, snapshot_cursor),
  FOREIGN KEY (project_id, kernel_digest)
    REFERENCES federated_kernels(project_id, kernel_digest)
);
CREATE TABLE IF NOT EXISTS federated_observation_cursors (
  project_id TEXT NOT NULL,
  stream_key TEXT NOT NULL,
  kernel_digest TEXT NOT NULL,
  generation INTEGER NOT NULL CHECK (generation > 0),
  cycle_id TEXT NOT NULL,
  parent_runtime_id TEXT NOT NULL,
  last_event_cursor INTEGER NOT NULL CHECK (last_event_cursor >= 0),
  snapshot_digest TEXT NOT NULL,
  updated_revision INTEGER NOT NULL REFERENCES state_revisions(revision),
  PRIMARY KEY (project_id, stream_key)
);
CREATE INDEX IF NOT EXISTS federated_plan_revision_idx
  ON federated_reconciliation_plans(project_id, state_revision);
CREATE INDEX IF NOT EXISTS federated_plan_stream_idx
  ON federated_reconciliation_plans(project_id, stream_key, snapshot_cursor);
"""


LEASE_COLUMNS = {
    "lease_owner": "TEXT",
    "lease_token_sha256": "TEXT",
    "lease_generation": "INTEGER NOT NULL DEFAULT 0",
    "lease_expires_at": "TEXT",
    "terminal_receipt_json": "TEXT",
    "terminal_receipt_sha256": "TEXT",
}


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeError) as exc:
        raise PersistenceError("value is not canonical JSON encodable") from exc


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest_value(value: Any) -> str:
    return digest_text(canonical_json(value))


def require_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or HEX64.fullmatch(value) is None:
        raise PersistenceError(f"{label} must be a lowercase SHA-256 digest")
    return value


def parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PersistenceError(f"{label} must be non-empty ISO-8601 text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PersistenceError(f"{label} must be valid ISO-8601 text") from exc
    if parsed.tzinfo is None:
        raise PersistenceError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def ensure_extension_schema(connection: sqlite3.Connection, project_id: str) -> None:
    # sqlite3.executescript() performs an implicit COMMIT. Execute each closed
    # DDL statement individually so schema installation remains inside the
    # same BEGIN IMMEDIATE transaction as the first retained plan.
    for statement in EXTENSION_SQL.split(";"):
        statement = statement.strip()
        if statement:
            connection.execute(statement)
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(outbox_messages)").fetchall()
    }
    for name, declaration in LEASE_COLUMNS.items():
        if name not in columns:
            connection.execute(
                f"ALTER TABLE outbox_messages ADD COLUMN {name} {declaration}"
            )
    row = connection.execute(
        "SELECT schema_name,schema_version,project_id "
        "FROM federated_runtime_metadata WHERE singleton=1"
    ).fetchone()
    if row is None:
        connection.execute(
            "INSERT INTO federated_runtime_metadata VALUES (1,?,?,?)",
            (EXTENSION_SCHEMA, EXTENSION_SCHEMA_VERSION, project_id),
        )
        return
    if (
        row["schema_name"] != EXTENSION_SCHEMA
        or row["schema_version"] != EXTENSION_SCHEMA_VERSION
        or row["project_id"] != project_id
    ):
        raise PersistenceError("federated runtime store metadata is unsupported or cross-project")


def verify_extension_schema(connection: sqlite3.Connection, project_id: str) -> None:
    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    required = {
        "federated_runtime_metadata",
        "federated_kernels",
        "federated_reconciliation_plans",
        "federated_observation_cursors",
    }
    if not required <= tables:
        raise PersistenceError("federated runtime store is not initialized")
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(outbox_messages)").fetchall()
    }
    if not set(LEASE_COLUMNS) <= columns:
        raise PersistenceError("federated outbox lease columns are incomplete")
    row = connection.execute(
        "SELECT schema_name,schema_version,project_id "
        "FROM federated_runtime_metadata WHERE singleton=1"
    ).fetchone()
    if row is None or (
        row["schema_name"] != EXTENSION_SCHEMA
        or row["schema_version"] != EXTENSION_SCHEMA_VERSION
        or row["project_id"] != project_id
    ):
        raise PersistenceError("federated runtime store metadata is invalid")


def stream_key(request: Mapping[str, Any]) -> str:
    return digest_value(
        {
            "kernel_digest": request["kernel_digest"],
            "generation": request["generation"],
            "project_id": request["project_id"],
            "cycle_id": request["cycle_id"],
            "parent_runtime_id": request["parent_runtime_id"],
        }
    )


def plan_key(request: Mapping[str, Any]) -> str:
    return digest_value(
        {
            "stream_key": stream_key(request),
            "snapshot_cursor": request["observed_snapshot"]["last_event_cursor"],
        }
    )


def command_payload(
    request: Mapping[str, Any], plan: Mapping[str, Any], action: Mapping[str, Any]
) -> dict[str, Any]:
    payload = {
        "$schema": COMMAND_SCHEMA,
        "project_id": request["project_id"],
        "kernel_digest": request["kernel_digest"],
        "generation": request["generation"],
        "cycle_id": request["cycle_id"],
        "parent_runtime_id": request["parent_runtime_id"],
        "plan_digest": plan["plan_digest"],
        "plan_order": action["order"],
        "action": deepcopy(action),
    }
    payload["command_digest"] = digest_value(payload)
    return payload


def command_key(payload: Mapping[str, Any]) -> str:
    return str(payload["command_digest"])


def actionable(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    if plan["status"] == "blocked":
        return []
    actions = []
    for action in plan["actions"]:
        kind = action.get("kind")
        if kind == "defer-admission":
            continue
        if kind not in COMMAND_KINDS:
            raise PersistenceError(f"unsupported federated action kind {kind}")
        actions.append(action)
    return actions


def _load_verified_inputs(
    kernel_path: Path, request_path: Path, plan_path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    kernel = RECONCILE.verify_kernel_document(kernel_path)
    request = RECONCILE.validate_request(
        RECONCILE.read_canonical_object(request_path, "reconciliation request"),
        kernel,
    )
    expected = RECONCILE.compile_plan(kernel, request)
    plan = RECONCILE.read_canonical_object(plan_path, "reconciliation plan")
    if plan != expected:
        raise PersistenceError("reconciliation plan does not reproduce")
    return kernel, request, plan


def persist_plan(
    project: Path,
    kernel: dict[str, Any],
    request: dict[str, Any],
    plan: dict[str, Any],
    *,
    created_at: str,
    inject_failure_after: int | None = None,
) -> dict[str, Any]:
    """Commit kernel, snapshot cursor, plan, event, and commands atomically."""
    project = project.resolve()
    parse_time(created_at, "created_at")
    if plan != RECONCILE.compile_plan(kernel, request):
        raise PersistenceError("plan does not match the supplied kernel and request")
    persistence = kernel.get("persistence", {})
    if persistence.get("adapter") != "sqlite":
        raise PersistenceError(
            "local SQLite persistence cannot consume a kernel configured for "
            "a different persistence adapter"
        )
    transaction = STORE.begin(project)
    success = False
    try:
        state = transaction.state
        project_id = state.get("instance", {}).get("project_id")
        program_version = state.get("strategy", {}).get("program_version")
        if project_id != request["project_id"]:
            raise PersistenceError("reconciliation request belongs to a different project")
        if not isinstance(program_version, int) or isinstance(program_version, bool):
            raise PersistenceError("control state has no valid program version")
        ensure_extension_schema(transaction.connection, project_id)
        key = plan_key(request)
        request_text = canonical_json(request)
        request_sha = digest_text(request_text)
        plan_text = canonical_json(plan)
        plan_sha = digest_text(plan_text)
        snapshot_digest = digest_value(request["observed_snapshot"])
        retained = transaction.connection.execute(
            "SELECT request_sha256,plan_sha256,state_revision FROM "
            "federated_reconciliation_plans WHERE project_id=? AND plan_key=?",
            (project_id, key),
        ).fetchone()
        if retained is not None:
            if retained["request_sha256"] != request_sha or retained["plan_sha256"] != plan_sha:
                raise PersistenceError("federated plan key conflicts with different bytes")
            transaction.close(False)
            return {
                "ok": True,
                "idempotent": True,
                "plan_key": key,
                "plan_digest": plan["plan_digest"],
                "state_revision": retained["state_revision"],
                "enqueued_commands": 0,
            }

        stream = stream_key(request)
        cursor = request["observed_snapshot"]["last_event_cursor"]
        retained_cursor = transaction.connection.execute(
            "SELECT last_event_cursor,snapshot_digest FROM federated_observation_cursors "
            "WHERE project_id=? AND stream_key=?",
            (project_id, stream),
        ).fetchone()
        if retained_cursor is not None:
            if cursor < retained_cursor["last_event_cursor"]:
                raise PersistenceError("observation cursor would move backwards")
            if (
                cursor == retained_cursor["last_event_cursor"]
                and snapshot_digest != retained_cursor["snapshot_digest"]
            ):
                raise PersistenceError("same observation cursor conflicts with different snapshot")

        transaction.stage(
            deepcopy(state),
            {
                "at": created_at,
                "type": "federated_reconciliation_plan_persisted",
                "project_id": project_id,
                "program_version": program_version,
                "kernel_digest": kernel["kernel_digest"],
                "generation": request["generation"],
                "cycle_id": request["cycle_id"],
                "plan_key": key,
                "plan_digest": plan["plan_digest"],
                "snapshot_cursor": cursor,
                "status": plan["status"],
            },
        )
        revision = transaction.staged_revision
        assert revision is not None
        kernel_text = canonical_json(kernel)
        kernel_sha = digest_text(kernel_text)
        existing_kernel = transaction.connection.execute(
            "SELECT kernel_sha256 FROM federated_kernels "
            "WHERE project_id=? AND kernel_digest=?",
            (project_id, kernel["kernel_digest"]),
        ).fetchone()
        if existing_kernel is None:
            transaction.connection.execute(
                "INSERT INTO federated_kernels VALUES (?,?,?,?,?)",
                (project_id, kernel["kernel_digest"], kernel_text, kernel_sha, revision),
            )
        elif existing_kernel["kernel_sha256"] != kernel_sha:
            raise PersistenceError("kernel digest conflicts with different bytes")

        transaction.connection.execute(
            "INSERT INTO federated_reconciliation_plans VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                project_id,
                key,
                stream,
                kernel["kernel_digest"],
                request["generation"],
                request["cycle_id"],
                request["parent_runtime_id"],
                plan["request_digest"],
                cursor,
                snapshot_digest,
                plan["status"],
                request_text,
                request_sha,
                plan_text,
                plan_sha,
                revision,
                created_at,
            ),
        )
        if retained_cursor is None:
            transaction.connection.execute(
                "INSERT INTO federated_observation_cursors VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    project_id,
                    stream,
                    kernel["kernel_digest"],
                    request["generation"],
                    request["cycle_id"],
                    request["parent_runtime_id"],
                    cursor,
                    snapshot_digest,
                    revision,
                ),
            )
        elif cursor > retained_cursor["last_event_cursor"]:
            transaction.connection.execute(
                "UPDATE federated_observation_cursors SET last_event_cursor=?,"
                "snapshot_digest=?,updated_revision=? WHERE project_id=? AND stream_key=?",
                (cursor, snapshot_digest, revision, project_id, stream),
            )

        enqueued = 0
        for action in actionable(plan):
            payload = command_payload(request, plan, action)
            transaction.enqueue_outbox(
                channel=OUTBOX_CHANNEL,
                key=command_key(payload),
                payload=payload,
            )
            enqueued += 1
            if inject_failure_after is not None and enqueued >= inject_failure_after:
                raise PersistenceError("injected persistence failure")
        transaction.record_idempotency(
            scope="federated-reconciliation-plan",
            key=key,
            command_name="persist-federated-plan",
            payload_sha256=request_sha,
            result={
                "plan_digest": plan["plan_digest"],
                "enqueued_commands": enqueued,
            },
            created_at=created_at,
        )
        success = True
        transaction.close(True)
        return {
            "ok": True,
            "idempotent": False,
            "plan_key": key,
            "plan_digest": plan["plan_digest"],
            "state_revision": revision,
            "enqueued_commands": enqueued,
        }
    except Exception:
        if not success:
            transaction.close(False)
        raise


def _outbox_row(connection: sqlite3.Connection, project_id: str, key: str):
    row = connection.execute(
        "SELECT * FROM outbox_messages WHERE project_id=? AND channel=? AND message_key=?",
        (project_id, OUTBOX_CHANNEL, key),
    ).fetchone()
    if row is None:
        raise PersistenceError("federated command does not exist")
    return row


def claim_command(
    project: Path,
    *,
    key: str,
    owner: str,
    claim_token: str,
    now: str,
    lease_expires_at: str,
) -> dict[str, Any]:
    """Claim one command with an expiring generation-fenced lease."""
    if not owner or owner != owner.strip() or not claim_token:
        raise PersistenceError("lease owner and claim token must be non-empty")
    now_value = parse_time(now, "now")
    expiry = parse_time(lease_expires_at, "lease_expires_at")
    if expiry <= now_value:
        raise PersistenceError("lease expiry must be after now")
    project = project.resolve()
    transaction = STORE.begin(project)
    success = False
    try:
        state = transaction.state
        project_id = state["instance"]["project_id"]
        ensure_extension_schema(transaction.connection, project_id)
        row = _outbox_row(transaction.connection, project_id, key)
        status = row["status"]
        if status in TERMINAL_OUTBOX_STATUSES:
            raise PersistenceError("terminal federated command cannot be claimed")
        if status == "leased":
            prior_expiry = parse_time(row["lease_expires_at"], "retained lease expiry")
            if prior_expiry > now_value:
                raise PersistenceError("federated command already has a live lease")
        elif status not in {"pending", "failed"}:
            raise PersistenceError(f"federated command status {status} is not claimable")
        if row["not_before"] is not None and parse_time(row["not_before"], "not_before") > now_value:
            raise PersistenceError("federated command is not ready")
        next_generation = int(row["lease_generation"]) + 1
        transaction.stage(
            deepcopy(state),
            {
                "at": now,
                "type": "federated_runtime_command_claimed",
                "project_id": project_id,
                "program_version": state["strategy"]["program_version"],
                "message_key": key,
                "lease_owner": owner,
                "lease_generation": next_generation,
                "lease_expires_at": lease_expires_at,
            },
        )
        revision = transaction.staged_revision
        token_sha = digest_text(claim_token)
        transaction.connection.execute(
            "UPDATE outbox_messages SET status='leased',attempt_count=attempt_count+1,"
            "lease_owner=?,lease_token_sha256=?,lease_generation=?,lease_expires_at=?,"
            "terminal_receipt_json=NULL,terminal_receipt_sha256=NULL,updated_revision=? "
            "WHERE project_id=? AND channel=? AND message_key=?",
            (
                owner,
                token_sha,
                next_generation,
                lease_expires_at,
                revision,
                project_id,
                OUTBOX_CHANNEL,
                key,
            ),
        )
        success = True
        transaction.close(True)
        return {
            "ok": True,
            "message_key": key,
            "payload": json.loads(row["payload_json"]),
            "lease_generation": next_generation,
            "lease_expires_at": lease_expires_at,
        }
    except Exception:
        if not success:
            transaction.close(False)
        raise


def settle_command(
    project: Path,
    *,
    key: str,
    owner: str,
    claim_token: str,
    lease_generation: int,
    outcome: str,
    receipt: dict[str, Any],
    at: str,
) -> dict[str, Any]:
    """Settle a live claim; stale generations and tokens cannot commit."""
    if outcome not in {"succeeded", "failed"}:
        raise PersistenceError("command outcome must be succeeded or failed")
    if not isinstance(lease_generation, int) or isinstance(lease_generation, bool) or lease_generation < 1:
        raise PersistenceError("lease generation must be a positive integer")
    at_value = parse_time(at, "at")
    project = project.resolve()
    transaction = STORE.begin(project)
    success = False
    try:
        state = transaction.state
        project_id = state["instance"]["project_id"]
        ensure_extension_schema(transaction.connection, project_id)
        row = _outbox_row(transaction.connection, project_id, key)
        if row["status"] == "cancelled":
            transaction.close(False)
            return {"ok": True, "message_key": key, "status": "cancelled", "idempotent": True}
        if row["status"] != "leased":
            raise PersistenceError("federated command does not have a live claim")
        if (
            row["lease_owner"] != owner
            or row["lease_token_sha256"] != digest_text(claim_token)
            or row["lease_generation"] != lease_generation
        ):
            raise PersistenceError("federated command lease fence does not match")
        if parse_time(row["lease_expires_at"], "retained lease expiry") < at_value:
            raise PersistenceError("federated command lease expired before settlement")
        receipt_text = canonical_json(receipt)
        receipt_sha = digest_text(receipt_text)
        transaction.stage(
            deepcopy(state),
            {
                "at": at,
                "type": "federated_runtime_command_settled",
                "project_id": project_id,
                "program_version": state["strategy"]["program_version"],
                "message_key": key,
                "lease_generation": lease_generation,
                "outcome": outcome,
                "receipt_sha256": receipt_sha,
            },
        )
        revision = transaction.staged_revision
        transaction.connection.execute(
            "UPDATE outbox_messages SET status=?,lease_owner=NULL,lease_token_sha256=NULL,"
            "lease_expires_at=NULL,terminal_receipt_json=?,terminal_receipt_sha256=?,"
            "updated_revision=? WHERE project_id=? AND channel=? AND message_key=?",
            (
                outcome,
                receipt_text,
                receipt_sha,
                revision,
                project_id,
                OUTBOX_CHANNEL,
                key,
            ),
        )
        success = True
        transaction.close(True)
        return {
            "ok": True,
            "message_key": key,
            "status": outcome,
            "lease_generation": lease_generation,
            "receipt_sha256": receipt_sha,
            "idempotent": False,
        }
    except Exception:
        if not success:
            transaction.close(False)
        raise


def cancel_command(project: Path, *, key: str, reason: str, at: str) -> dict[str, Any]:
    """Cancel pending, leased, or failed work; cancellation is authoritative."""
    if not reason or reason != reason.strip():
        raise PersistenceError("cancellation reason must be non-empty trimmed text")
    parse_time(at, "at")
    project = project.resolve()
    transaction = STORE.begin(project)
    success = False
    try:
        state = transaction.state
        project_id = state["instance"]["project_id"]
        ensure_extension_schema(transaction.connection, project_id)
        row = _outbox_row(transaction.connection, project_id, key)
        if row["status"] == "cancelled":
            transaction.close(False)
            return {"ok": True, "message_key": key, "status": "cancelled", "idempotent": True}
        if row["status"] == "succeeded":
            raise PersistenceError("succeeded federated command cannot be cancelled")
        receipt = {
            "schema": "company-os.federated-command-cancellation.v1",
            "reason": reason,
            "at": at,
            "superseded_lease_generation": row["lease_generation"],
        }
        receipt_text = canonical_json(receipt)
        receipt_sha = digest_text(receipt_text)
        transaction.stage(
            deepcopy(state),
            {
                "at": at,
                "type": "federated_runtime_command_cancelled",
                "project_id": project_id,
                "program_version": state["strategy"]["program_version"],
                "message_key": key,
                "reason": reason,
                "receipt_sha256": receipt_sha,
            },
        )
        revision = transaction.staged_revision
        transaction.connection.execute(
            "UPDATE outbox_messages SET status='cancelled',lease_owner=NULL,"
            "lease_token_sha256=NULL,lease_expires_at=NULL,terminal_receipt_json=?,"
            "terminal_receipt_sha256=?,updated_revision=? "
            "WHERE project_id=? AND channel=? AND message_key=?",
            (
                receipt_text,
                receipt_sha,
                revision,
                project_id,
                OUTBOX_CHANNEL,
                key,
            ),
        )
        success = True
        transaction.close(True)
        return {
            "ok": True,
            "message_key": key,
            "status": "cancelled",
            "receipt_sha256": receipt_sha,
            "idempotent": False,
        }
    except Exception:
        if not success:
            transaction.close(False)
        raise


def audit(project: Path) -> dict[str, Any]:
    """Audit the extension, plan replay, cursors, commands, and lease truth."""
    project = project.resolve()
    errors: list[str] = []
    core = STORE.audit(project)
    if not core["ok"]:
        errors.extend(f"control store: {item}" for item in core["errors"])
    connection = STORE.connect(project)
    plan_count = 0
    command_count = 0
    try:
        metadata = STORE._assert_binding(connection, project)
        project_id = metadata["project_id"]
        try:
            verify_extension_schema(connection, project_id)
        except PersistenceError as exc:
            errors.append(str(exc))
            return {"ok": False, "errors": errors, "plans": 0, "commands": 0}
        for table in (
            "federated_kernels",
            "federated_reconciliation_plans",
            "federated_observation_cursors",
        ):
            if connection.execute(
                f"SELECT 1 FROM {table} WHERE project_id<>? LIMIT 1", (project_id,)
            ).fetchone():
                errors.append(f"{table} contains records for a foreign project")

        kernels: dict[str, dict[str, Any]] = {}
        for row in connection.execute(
            "SELECT * FROM federated_kernels WHERE project_id=?", (project_id,)
        ):
            if digest_text(row["kernel_json"]) != row["kernel_sha256"]:
                errors.append("federated kernel bytes failed integrity verification")
                continue
            try:
                kernel = json.loads(row["kernel_json"])
            except json.JSONDecodeError:
                errors.append("federated kernel JSON is invalid")
                continue
            if not isinstance(kernel, dict) or kernel.get("kernel_digest") != row["kernel_digest"]:
                errors.append("federated kernel identity is invalid")
                continue
            kernels[row["kernel_digest"]] = kernel

        expected_commands: dict[str, dict[str, Any]] = {}
        cursor_expectations: dict[str, tuple[int, str]] = {}
        for row in connection.execute(
            "SELECT * FROM federated_reconciliation_plans WHERE project_id=? "
            "ORDER BY state_revision,plan_key",
            (project_id,),
        ):
            plan_count += 1
            if (
                digest_text(row["request_json"]) != row["request_sha256"]
                or digest_text(row["plan_json"]) != row["plan_sha256"]
            ):
                errors.append("federated plan bytes failed integrity verification")
                continue
            try:
                request = json.loads(row["request_json"])
                plan = json.loads(row["plan_json"])
            except json.JSONDecodeError:
                errors.append("federated plan JSON is invalid")
                continue
            kernel = kernels.get(row["kernel_digest"])
            if kernel is None:
                errors.append("federated plan references an unavailable kernel")
                continue
            try:
                normalized = RECONCILE.validate_request(request, kernel)
                expected_plan = RECONCILE.compile_plan(kernel, normalized)
            except Exception as exc:
                errors.append(f"federated plan cannot replay: {exc}")
                continue
            if normalized != request or expected_plan != plan:
                errors.append("federated plan is not deterministic from retained inputs")
                continue
            if (
                row["plan_key"] != plan_key(request)
                or row["stream_key"] != stream_key(request)
                or row["request_digest"] != plan["request_digest"]
                or row["snapshot_cursor"] != plan["snapshot_cursor"]
                or row["snapshot_digest"] != digest_value(request["observed_snapshot"])
                or row["status"] != plan["status"]
            ):
                errors.append("federated plan row does not match retained plan bindings")
                continue
            current = cursor_expectations.get(row["stream_key"])
            candidate = (row["snapshot_cursor"], row["snapshot_digest"])
            if current is None or candidate[0] > current[0]:
                cursor_expectations[row["stream_key"]] = candidate
            for action in actionable(plan):
                payload = command_payload(request, plan, action)
                expected_commands[command_key(payload)] = payload

        actual_cursors = {
            row["stream_key"]: (row["last_event_cursor"], row["snapshot_digest"])
            for row in connection.execute(
                "SELECT stream_key,last_event_cursor,snapshot_digest FROM "
                "federated_observation_cursors WHERE project_id=?",
                (project_id,),
            )
        }
        if actual_cursors != cursor_expectations:
            errors.append("federated observation cursors do not match retained plan history")

        rows = connection.execute(
            "SELECT * FROM outbox_messages WHERE project_id=? AND channel=?",
            (project_id, OUTBOX_CHANNEL),
        ).fetchall()
        command_count = len(rows)
        actual_keys: set[str] = set()
        for row in rows:
            key = row["message_key"]
            actual_keys.add(key)
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                errors.append("federated command JSON is invalid")
                continue
            if (
                expected_commands.get(key) != payload
                or row["payload_sha256"] != STORE.sha256_bytes(row["payload_json"].encode())
                or payload.get("command_digest") != key
            ):
                errors.append("federated command does not match its retained plan")
            leased = row["status"] == "leased"
            lease_fields = (
                row["lease_owner"],
                row["lease_token_sha256"],
                row["lease_expires_at"],
            )
            if leased and (
                not all(isinstance(value, str) and value for value in lease_fields)
                or row["lease_generation"] < 1
            ):
                errors.append("leased federated command has an incomplete lease fence")
            if not leased and any(value is not None for value in lease_fields):
                errors.append("unleased federated command retains live lease authority")
            if row["terminal_receipt_json"] is not None:
                if (
                    row["status"] not in {"succeeded", "failed", "cancelled"}
                    or digest_text(row["terminal_receipt_json"])
                    != row["terminal_receipt_sha256"]
                ):
                    errors.append("federated command terminal receipt is invalid")
        if actual_keys != set(expected_commands):
            errors.append("federated command set does not match retained actionable plans")
    finally:
        connection.close()
    return {
        "ok": not errors,
        "errors": errors,
        "backend": "sqlite",
        "extension_schema": EXTENSION_SCHEMA,
        "plans": plan_count,
        "commands": command_count,
        "runtime_activated": False,
        "scheduler_activated": False,
    }


def command_persist(args: argparse.Namespace) -> int:
    try:
        kernel, request, plan = _load_verified_inputs(
            Path(args.kernel), Path(args.request), Path(args.plan)
        )
        result = persist_plan(
            Path(args.project), kernel, request, plan, created_at=args.at
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (
        PersistenceError,
        RECONCILE.ReconciliationError,
        RECONCILE.KERNEL.KernelError,
        STORE.StoreError,
        OSError,
    ) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def command_audit(args: argparse.Namespace) -> int:
    try:
        result = audit(Path(args.project))
        print(json.dumps(result, sort_keys=True))
        return 0 if result["ok"] else 2
    except (PersistenceError, STORE.StoreError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def command_claim(args: argparse.Namespace) -> int:
    try:
        result = claim_command(
            Path(args.project),
            key=args.message_key,
            owner=args.owner,
            claim_token=args.claim_token,
            now=args.now,
            lease_expires_at=args.lease_expires_at,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PersistenceError, STORE.StoreError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def read_receipt(path: Path) -> dict[str, Any]:
    value = RECONCILE.read_canonical_object(path, "settlement receipt")
    return value


def command_settle(args: argparse.Namespace) -> int:
    try:
        result = settle_command(
            Path(args.project),
            key=args.message_key,
            owner=args.owner,
            claim_token=args.claim_token,
            lease_generation=args.lease_generation,
            outcome=args.outcome,
            receipt=read_receipt(Path(args.receipt)),
            at=args.at,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PersistenceError, RECONCILE.ReconciliationError, STORE.StoreError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def command_cancel(args: argparse.Namespace) -> int:
    try:
        result = cancel_command(
            Path(args.project), key=args.message_key, reason=args.reason, at=args.at
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PersistenceError, STORE.StoreError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    persist = sub.add_parser("persist")
    persist.add_argument("--project", required=True)
    persist.add_argument("--kernel", required=True)
    persist.add_argument("--request", required=True)
    persist.add_argument("--plan", required=True)
    persist.add_argument("--at", required=True)
    persist.set_defaults(handler=command_persist)
    inspect = sub.add_parser("audit")
    inspect.add_argument("--project", required=True)
    inspect.set_defaults(handler=command_audit)
    claim = sub.add_parser("claim")
    claim.add_argument("--project", required=True)
    claim.add_argument("--message-key", required=True)
    claim.add_argument("--owner", required=True)
    claim.add_argument("--claim-token", required=True)
    claim.add_argument("--now", required=True)
    claim.add_argument("--lease-expires-at", required=True)
    claim.set_defaults(handler=command_claim)
    settle = sub.add_parser("settle")
    settle.add_argument("--project", required=True)
    settle.add_argument("--message-key", required=True)
    settle.add_argument("--owner", required=True)
    settle.add_argument("--claim-token", required=True)
    settle.add_argument("--lease-generation", required=True, type=int)
    settle.add_argument("--outcome", required=True, choices=("succeeded", "failed"))
    settle.add_argument("--receipt", required=True)
    settle.add_argument("--at", required=True)
    settle.set_defaults(handler=command_settle)
    cancel = sub.add_parser("cancel")
    cancel.add_argument("--project", required=True)
    cancel.add_argument("--message-key", required=True)
    cancel.add_argument("--reason", required=True)
    cancel.add_argument("--at", required=True)
    cancel.set_defaults(handler=command_cancel)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
