#!/usr/bin/env python3
"""PostgreSQL adapter for the durable federated Company OS runtime.

The adapter loads its DSN only from the environment variable named by the
compiled kernel. It never prints the DSN and never falls back to SQLite.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
RECONCILER_PATH = SKILL_ROOT / "scripts" / "reconcile_federated_kernel.py"
SQLITE_ADAPTER_PATH = SKILL_ROOT / "scripts" / "persist_federated_runtime.py"
MIGRATION_PATH = SKILL_ROOT / "references" / "postgresql-federated-runtime.sql"
POSTGRESQL_ADAPTER_SCHEMA = "company-os.postgresql-federated-runtime-adapter.v1"
POSTGRESQL_CLAIM_SCHEMA = "company-os.postgresql-federated-command-claim.v1"
POSTGRESQL_NATIVE_LAUNCH_SCHEMA = "company-os.postgresql-native-launch-attempt.v1"
POSTGRESQL_NATIVE_RECOVERY_SCHEMA = "company-os.postgresql-native-launch-recovery.v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PostgresRuntimeError(ValueError):
    """A closed PostgreSQL adapter or configuration failure."""


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PostgresRuntimeError(f"cannot load required module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RECONCILE = load_module("company_os_postgres_reconciler", RECONCILER_PATH)
LOCAL = load_module("company_os_local_federated_store_helpers", SQLITE_ADAPTER_PATH)


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
        raise PostgresRuntimeError("value is not canonical JSON encodable") from exc


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def native_launch_content_digest(
    message_key: str,
    payload_sha256: str,
    attempt_id: str,
    dispatch_digest: str,
    initial_prompt_sha256: str,
) -> str:
    """Derive the exact content binding used by native launch SQL."""
    fields = (
        message_key,
        payload_sha256,
        attempt_id,
        dispatch_digest,
        initial_prompt_sha256,
    )
    if any(not isinstance(value, str) or not value for value in fields):
        raise PostgresRuntimeError("native launch content fields are required")
    for label, value in (
        ("message_key", message_key),
        ("payload_sha256", payload_sha256),
        ("dispatch_digest", dispatch_digest),
        ("initial_prompt_sha256", initial_prompt_sha256),
    ):
        if SHA256_RE.fullmatch(value) is None:
            raise PostgresRuntimeError(f"native launch {label} must be lowercase SHA-256")
    return digest_text("|".join(fields))


def _native_attempt_envelope(
    schema: str,
    *,
    project_id: str,
    message_key: str,
    result: Any,
) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise PostgresRuntimeError("PostgreSQL native launch function returned an invalid receipt")
    return {
        "$schema": schema,
        "ok": True,
        "backend": "postgresql",
        "project_id": project_id,
        "message_key": message_key,
        "attempt": result,
    }


def _read_canonical_value(path: Path, label: str) -> Any:
    if path.is_symlink() or not path.is_file():
        raise PostgresRuntimeError(f"{label} must be a regular non-symlink file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PostgresRuntimeError(f"{label} is not valid JSON") from exc
    if raw != (canonical_json(value) + "\n").encode("utf-8"):
        raise PostgresRuntimeError(f"{label} bytes are not canonical JSON")
    return value


def _native_hash(value: str, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise PostgresRuntimeError(f"{label} must be lowercase SHA-256")
    return value


def _native_text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PostgresRuntimeError(f"{label} must be non-empty trimmed text")
    return value


def quote_identifier(value: str) -> str:
    if RECONCILE.KERNEL.ID_RE.fullmatch(value) is None:
        raise PostgresRuntimeError("PostgreSQL schema is not a valid kernel identifier")
    return '"' + value.replace('"', '""') + '"'


def split_sql(source: str) -> list[str]:
    """Split PostgreSQL DDL without breaking quoted or dollar-quoted bodies."""
    statements: list[str] = []
    buffer: list[str] = []
    index = 0
    single = False
    double = False
    line_comment = False
    block_comment = False
    dollar: str | None = None
    while index < len(source):
        if line_comment:
            buffer.append(source[index])
            if source[index] == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            if source.startswith("*/", index):
                buffer.extend("*/")
                index += 2
                block_comment = False
            else:
                buffer.append(source[index])
                index += 1
            continue
        if dollar is not None:
            if source.startswith(dollar, index):
                buffer.extend(dollar)
                index += len(dollar)
                dollar = None
            else:
                buffer.append(source[index])
                index += 1
            continue
        if single:
            buffer.append(source[index])
            if source[index] == "'":
                if index + 1 < len(source) and source[index + 1] == "'":
                    buffer.append(source[index + 1])
                    index += 2
                    continue
                single = False
            index += 1
            continue
        if double:
            buffer.append(source[index])
            if source[index] == '"':
                if index + 1 < len(source) and source[index + 1] == '"':
                    buffer.append(source[index + 1])
                    index += 2
                    continue
                double = False
            index += 1
            continue
        if source.startswith("--", index):
            buffer.extend("--")
            index += 2
            line_comment = True
            continue
        if source.startswith("/*", index):
            buffer.extend("/*")
            index += 2
            block_comment = True
            continue
        if source[index] == "'":
            buffer.append(source[index])
            index += 1
            single = True
            continue
        if source[index] == '"':
            buffer.append(source[index])
            index += 1
            double = True
            continue
        if source[index] == "$":
            match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", source[index:])
            if match is not None:
                dollar = match.group(0)
                buffer.extend(dollar)
                index += len(dollar)
                continue
        if source[index] == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            index += 1
            continue
        buffer.append(source[index])
        index += 1
    statement = "".join(buffer).strip()
    if statement:
        statements.append(statement)
    if single or double or block_comment or dollar is not None:
        raise PostgresRuntimeError("PostgreSQL migration contains an unclosed quoted body")
    return statements


def render_migration(schema: str) -> list[str]:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    rendered = source.replace('"company-os"', quote_identifier(schema))
    statements = split_sql(rendered)
    if not statements:
        raise PostgresRuntimeError("PostgreSQL migration is empty")
    return statements


def verified_inputs(
    kernel_path: Path, request_path: Path, plan_path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    kernel = RECONCILE.verify_kernel_document(kernel_path)
    if kernel.get("persistence", {}).get("adapter") != "postgresql":
        raise PostgresRuntimeError(
            "PostgreSQL adapter cannot consume a kernel configured for another backend"
        )
    request = RECONCILE.validate_request(
        RECONCILE.read_canonical_object(request_path, "reconciliation request"),
        kernel,
    )
    plan = RECONCILE.read_canonical_object(plan_path, "reconciliation plan")
    if plan != RECONCILE.compile_plan(kernel, request):
        raise PostgresRuntimeError("reconciliation plan does not reproduce")
    return kernel, request, plan


def build_record(
    kernel: dict[str, Any],
    request: dict[str, Any],
    plan: dict[str, Any],
    *,
    created_at: str,
) -> dict[str, Any]:
    if kernel.get("persistence", {}).get("adapter") != "postgresql":
        raise PostgresRuntimeError("kernel is not configured for PostgreSQL")
    LOCAL.parse_time(created_at, "created_at")
    if plan != RECONCILE.compile_plan(kernel, request):
        raise PostgresRuntimeError("plan does not match the supplied kernel and request")
    commands: list[dict[str, Any]] = []
    for action in LOCAL.actionable(plan):
        payload = LOCAL.command_payload(request, plan, action)
        payload_json = canonical_json(payload)
        commands.append(
            {
                "message_key": LOCAL.command_key(payload),
                "plan_order": action["order"],
                "payload_json": payload_json,
                "payload_sha256": digest_text(payload_json),
            }
        )
    command_keys = sorted(item["message_key"] for item in commands)
    request_json = canonical_json(request)
    plan_json = canonical_json(plan)
    kernel_json = canonical_json(kernel)
    return {
        "$schema": POSTGRESQL_ADAPTER_SCHEMA,
        "project_id": request["project_id"],
        "kernel_digest": kernel["kernel_digest"],
        "kernel_json": kernel_json,
        "kernel_sha256": digest_text(kernel_json),
        "plan_key": LOCAL.plan_key(request),
        "stream_key": LOCAL.stream_key(request),
        "generation": request["generation"],
        "cycle_id": request["cycle_id"],
        "parent_runtime_id": request["parent_runtime_id"],
        "request_digest": plan["request_digest"],
        "snapshot_cursor": plan["snapshot_cursor"],
        "snapshot_digest": LOCAL.digest_value(request["observed_snapshot"]),
        "status": plan["status"],
        "request_json": request_json,
        "request_sha256": digest_text(request_json),
        "plan_json": plan_json,
        "plan_sha256": digest_text(plan_json),
        "plan_digest": plan["plan_digest"],
        "command_set_digest": digest_text(",".join(command_keys)),
        "commands": commands,
        "created_at": created_at,
    }


def psycopg_module():
    try:
        import psycopg  # type: ignore
    except ImportError as exc:
        raise PostgresRuntimeError(
            "PostgreSQL runtime requires psycopg 3; install psycopg[binary] in the host environment"
        ) from exc
    return psycopg


def configured_dsn(kernel: dict[str, Any]) -> str:
    env_name = kernel.get("persistence", {}).get("dsn_env")
    if not isinstance(env_name, str) or not env_name:
        raise PostgresRuntimeError("kernel does not name a PostgreSQL DSN environment variable")
    dsn = os.environ.get(env_name)
    if not dsn:
        raise PostgresRuntimeError(f"required PostgreSQL DSN environment variable {env_name} is absent")
    return dsn


@contextmanager
def database_connection(kernel: dict[str, Any], operation: str):
    """Open a connection while keeping provider errors and DSNs out of receipts."""
    psycopg = psycopg_module()
    try:
        with psycopg.connect(configured_dsn(kernel)) as connection:
            yield connection
    except psycopg.Error as exc:
        raise PostgresRuntimeError(
            f"PostgreSQL {operation} failed ({type(exc).__name__})"
        ) from None


def row_dict(cursor) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    return {column.name: value for column, value in zip(cursor.description, row)}


def migrate(kernel: dict[str, Any]) -> dict[str, Any]:
    statements = render_migration(kernel["persistence"]["schema"])
    with database_connection(kernel, "migration") as connection:
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
    return {
        "ok": True,
        "backend": "postgresql",
        "schema": kernel["persistence"]["schema"],
        "statements": len(statements),
    }


def persist(kernel: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    schema = quote_identifier(kernel["persistence"]["schema"])
    with database_connection(kernel, "persistence") as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM {schema}.persist_reconciliation(%s::jsonb)",
                (canonical_json(record),),
            )
            result = row_dict(cursor)
    if result is None:
        raise PostgresRuntimeError("PostgreSQL persistence returned no receipt")
    return {"ok": True, "backend": "postgresql", **result}


def claim(
    kernel: dict[str, Any],
    *,
    project_id: str,
    owner: str,
    claim_token: str,
    now: str,
    lease_expires_at: str,
    message_key: str | None,
) -> dict[str, Any]:
    schema = quote_identifier(kernel["persistence"]["schema"])
    with database_connection(kernel, "claim") as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM {schema}.claim_command(%s,%s,%s,%s,%s,%s)",
                (project_id, owner, claim_token, now, lease_expires_at, message_key),
            )
            result = row_dict(cursor)
    return {
        "$schema": POSTGRESQL_CLAIM_SCHEMA,
        "ok": True,
        "backend": "postgresql",
        "project_id": project_id,
        "claim_owner": owner,
        "claim": result,
    }


def prepare_native_launch_attempt(
    kernel: dict[str, Any],
    *,
    project_id: str,
    message_key: str,
    owner: str,
    claim_token: str,
    lease_generation: int,
    attempt_id: str,
    dispatch_digest: str,
    initial_prompt_sha256: str,
    at: str,
) -> dict[str, Any]:
    """Durably prepare one content-bound native host create before the effect."""
    _native_text(project_id, "project_id")
    _native_hash(message_key, "message_key")
    _native_text(owner, "owner")
    _native_text(claim_token, "claim_token")
    _native_text(attempt_id, "attempt_id")
    if not isinstance(lease_generation, int) or lease_generation < 1:
        raise PostgresRuntimeError("lease_generation must be a positive integer")
    _native_hash(dispatch_digest, "dispatch_digest")
    _native_hash(initial_prompt_sha256, "initial_prompt_sha256")
    LOCAL.parse_time(at, "at")
    schema = quote_identifier(kernel["persistence"]["schema"])
    with database_connection(kernel, "native launch preparation") as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {schema}.prepare_native_launch_attempt(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    project_id,
                    message_key,
                    owner,
                    claim_token,
                    lease_generation,
                    attempt_id,
                    dispatch_digest,
                    initial_prompt_sha256,
                    at,
                ),
            )
            result = cursor.fetchone()[0]
    return _native_attempt_envelope(
        POSTGRESQL_NATIVE_LAUNCH_SCHEMA,
        project_id=project_id,
        message_key=message_key,
        result=result,
    )


def mark_native_launch_ambiguous(
    kernel: dict[str, Any],
    *,
    project_id: str,
    message_key: str,
    owner: str,
    claim_token: str,
    lease_generation: int,
    attempt_id: str,
    at: str,
) -> dict[str, Any]:
    """Record a possible host effect without asserting task creation."""
    _native_hash(message_key, "message_key")
    _native_text(owner, "owner")
    _native_text(claim_token, "claim_token")
    _native_text(attempt_id, "attempt_id")
    if not isinstance(lease_generation, int) or lease_generation < 1:
        raise PostgresRuntimeError("lease_generation must be a positive integer")
    LOCAL.parse_time(at, "at")
    schema = quote_identifier(kernel["persistence"]["schema"])
    with database_connection(kernel, "native launch ambiguity") as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {schema}.mark_native_launch_ambiguous(%s,%s,%s,%s,%s,%s,%s)",
                (
                    project_id,
                    message_key,
                    owner,
                    claim_token,
                    lease_generation,
                    attempt_id,
                    at,
                ),
            )
            result = cursor.fetchone()[0]
    return _native_attempt_envelope(
        POSTGRESQL_NATIVE_LAUNCH_SCHEMA,
        project_id=project_id,
        message_key=message_key,
        result=result,
    )


def reclaim_native_launch_attempt(
    kernel: dict[str, Any],
    *,
    project_id: str,
    message_key: str,
    owner: str,
    claim_token: str,
    expected_generation: int,
    now: str,
    lease_expires_at: str,
) -> dict[str, Any]:
    """Acquire a new fenced lease only for explicit launch recovery."""
    _native_hash(message_key, "message_key")
    _native_text(owner, "owner")
    _native_text(claim_token, "claim_token")
    if not isinstance(expected_generation, int) or expected_generation < 1:
        raise PostgresRuntimeError("expected_generation must be a positive integer")
    LOCAL.parse_time(now, "now")
    LOCAL.parse_time(lease_expires_at, "lease_expires_at")
    schema = quote_identifier(kernel["persistence"]["schema"])
    with database_connection(kernel, "native launch recovery claim") as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT * FROM {schema}.reclaim_native_launch_attempt(%s,%s,%s,%s,%s,%s,%s)",
                (
                    project_id,
                    message_key,
                    owner,
                    claim_token,
                    expected_generation,
                    now,
                    lease_expires_at,
                ),
            )
            result = row_dict(cursor)
    return _native_attempt_envelope(
        POSTGRESQL_NATIVE_RECOVERY_SCHEMA,
        project_id=project_id,
        message_key=message_key,
        result=result,
    )


def recover_native_launch_attempt(
    kernel: dict[str, Any],
    *,
    project_id: str,
    message_key: str,
    owner: str,
    claim_token: str,
    lease_generation: int,
    attempt_id: str,
    candidates: list[dict[str, Any]],
    at: str,
    requeue_at: str | None = None,
    absence_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind one exact task, audit typed zero evidence while blocked, or persist conflict."""
    _native_hash(message_key, "message_key")
    _native_text(owner, "owner")
    _native_text(claim_token, "claim_token")
    _native_text(attempt_id, "attempt_id")
    if not isinstance(lease_generation, int) or lease_generation < 1:
        raise PostgresRuntimeError("lease_generation must be a positive integer")
    if not isinstance(candidates, list) or any(not isinstance(item, dict) for item in candidates):
        raise PostgresRuntimeError("native launch candidates must be a list of objects")
    if not candidates and absence_evidence is None:
        raise PostgresRuntimeError("absence evidence is required when candidates are empty")
    if absence_evidence is not None and not isinstance(absence_evidence, dict):
        raise PostgresRuntimeError("absence evidence must be an object")
    LOCAL.parse_time(at, "at")
    if requeue_at is not None:
        LOCAL.parse_time(requeue_at, "requeue_at")
    candidates_json = canonical_json(candidates)
    absence_evidence_json = (
        canonical_json(absence_evidence) if absence_evidence is not None else None
    )
    schema = quote_identifier(kernel["persistence"]["schema"])
    with database_connection(kernel, "native launch recovery") as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {schema}.recover_native_launch_attempt(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    project_id,
                    message_key,
                    owner,
                    claim_token,
                    lease_generation,
                    attempt_id,
                    candidates_json,
                    at,
                    requeue_at,
                    absence_evidence_json,
                ),
            )
            result = cursor.fetchone()[0]
    return _native_attempt_envelope(
        POSTGRESQL_NATIVE_RECOVERY_SCHEMA,
        project_id=project_id,
        message_key=message_key,
        result=result,
    )


def abandon_native_launch_attempt(
    kernel: dict[str, Any],
    *,
    project_id: str,
    message_key: str,
    owner: str,
    claim_token: str,
    lease_generation: int,
    attempt_id: str,
    at: str,
    absence_evidence: dict[str, Any],
    requeue_at: str | None = None,
) -> dict[str, Any]:
    return recover_native_launch_attempt(
        kernel,
        project_id=project_id,
        message_key=message_key,
        owner=owner,
        claim_token=claim_token,
        lease_generation=lease_generation,
        attempt_id=attempt_id,
        candidates=[],
        at=at,
        requeue_at=requeue_at,
        absence_evidence=absence_evidence,
    )


# Compatibility aliases retain older host names. `abandon` is deliberately an
# audit-only zero-candidate call in this version; it cannot requeue or authorize
# another host create without a future separately authorized transition.
prepare_native_launch = prepare_native_launch_attempt
reclaim_native_launch = reclaim_native_launch_attempt
recover_native_launch = recover_native_launch_attempt
abandon_native_launch = abandon_native_launch_attempt
prepare_launch_attempt = prepare_native_launch_attempt
mark_launch_ambiguous = mark_native_launch_ambiguous
reclaim_launch_attempt = reclaim_native_launch_attempt
recover_launch_attempt = recover_native_launch_attempt
abandon_launch_attempt = abandon_native_launch_attempt


def settle(
    kernel: dict[str, Any],
    *,
    project_id: str,
    message_key: str,
    owner: str,
    claim_token: str,
    lease_generation: int,
    outcome: str,
    receipt: dict[str, Any],
    at: str,
) -> dict[str, Any]:
    schema = quote_identifier(kernel["persistence"]["schema"])
    receipt_json = canonical_json(receipt)
    with database_connection(kernel, "settlement") as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {schema}.settle_command(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    project_id,
                    message_key,
                    owner,
                    claim_token,
                    lease_generation,
                    outcome,
                    receipt_json,
                    digest_text(receipt_json),
                    at,
                ),
            )
            result = cursor.fetchone()[0]
    return {"ok": True, "backend": "postgresql", "status": result}


def cancel(
    kernel: dict[str, Any],
    *,
    project_id: str,
    message_key: str,
    owner: str,
    claim_token: str,
    lease_generation: int,
    reason: str,
    at: str,
) -> dict[str, Any]:
    schema = quote_identifier(kernel["persistence"]["schema"])
    with database_connection(kernel, "cancellation") as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {schema}.cancel_command(%s,%s,%s,%s,%s,%s,%s)",
                (
                    project_id,
                    message_key,
                    owner,
                    claim_token,
                    lease_generation,
                    reason,
                    at,
                ),
            )
            result = cursor.fetchone()[0]
    return {"ok": True, "backend": "postgresql", "status": result}


def audit(kernel: dict[str, Any], project_id: str) -> dict[str, Any]:
    schema = quote_identifier(kernel["persistence"]["schema"])
    with database_connection(kernel, "audit") as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {schema}.audit_project(%s)", (project_id,))
            result = cursor.fetchone()[0]
    if not isinstance(result, dict):
        raise PostgresRuntimeError("PostgreSQL audit returned an invalid receipt")
    return {"backend": "postgresql", **result}


def load_kernel(path: Path) -> dict[str, Any]:
    kernel = RECONCILE.verify_kernel_document(path)
    if kernel.get("persistence", {}).get("adapter") != "postgresql":
        raise PostgresRuntimeError("kernel is not configured for PostgreSQL")
    return kernel


def command_migrate(args: argparse.Namespace) -> int:
    try:
        result = migrate(load_kernel(Path(args.kernel)))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PostgresRuntimeError, RECONCILE.ReconciliationError, RECONCILE.KERNEL.KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def command_persist(args: argparse.Namespace) -> int:
    try:
        kernel, request, plan = verified_inputs(
            Path(args.kernel), Path(args.request), Path(args.plan)
        )
        result = persist(
            kernel, build_record(kernel, request, plan, created_at=args.at)
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PostgresRuntimeError, RECONCILE.ReconciliationError, RECONCILE.KERNEL.KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def token_from_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise PostgresRuntimeError(f"claim token environment variable {name} is absent")
    return value


def command_claim(args: argparse.Namespace) -> int:
    try:
        result = claim(
            load_kernel(Path(args.kernel)),
            project_id=args.project_id,
            owner=args.owner,
            claim_token=token_from_env(args.claim_token_env),
            now=args.now,
            lease_expires_at=args.lease_expires_at,
            message_key=args.message_key,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PostgresRuntimeError, RECONCILE.ReconciliationError, RECONCILE.KERNEL.KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def command_prepare_native_launch(args: argparse.Namespace) -> int:
    try:
        result = prepare_native_launch_attempt(
            load_kernel(Path(args.kernel)),
            project_id=args.project_id,
            message_key=args.message_key,
            owner=args.owner,
            claim_token=token_from_env(args.claim_token_env),
            lease_generation=args.lease_generation,
            attempt_id=args.attempt_id,
            dispatch_digest=args.dispatch_digest,
            initial_prompt_sha256=args.initial_prompt_sha256,
            at=args.at,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PostgresRuntimeError, RECONCILE.ReconciliationError, RECONCILE.KERNEL.KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def command_mark_native_launch_ambiguous(args: argparse.Namespace) -> int:
    try:
        result = mark_native_launch_ambiguous(
            load_kernel(Path(args.kernel)),
            project_id=args.project_id,
            message_key=args.message_key,
            owner=args.owner,
            claim_token=token_from_env(args.claim_token_env),
            lease_generation=args.lease_generation,
            attempt_id=args.attempt_id,
            at=args.at,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PostgresRuntimeError, RECONCILE.ReconciliationError, RECONCILE.KERNEL.KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def command_reclaim_native_launch(args: argparse.Namespace) -> int:
    try:
        result = reclaim_native_launch_attempt(
            load_kernel(Path(args.kernel)),
            project_id=args.project_id,
            message_key=args.message_key,
            owner=args.owner,
            claim_token=token_from_env(args.claim_token_env),
            expected_generation=args.expected_generation,
            now=args.now,
            lease_expires_at=args.lease_expires_at,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PostgresRuntimeError, RECONCILE.ReconciliationError, RECONCILE.KERNEL.KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def command_recover_native_launch(args: argparse.Namespace) -> int:
    try:
        candidates = _read_canonical_value(Path(args.candidates), "native launch candidates")
        if not isinstance(candidates, list):
            raise PostgresRuntimeError("native launch candidates must be a JSON array")
        absence_evidence = None
        if args.absence_evidence:
            absence_evidence = _read_canonical_value(
                Path(args.absence_evidence), "native launch absence evidence"
            )
            if not isinstance(absence_evidence, dict):
                raise PostgresRuntimeError("native launch absence evidence must be a JSON object")
        result = recover_native_launch_attempt(
            load_kernel(Path(args.kernel)),
            project_id=args.project_id,
            message_key=args.message_key,
            owner=args.owner,
            claim_token=token_from_env(args.claim_token_env),
            lease_generation=args.lease_generation,
            attempt_id=args.attempt_id,
            candidates=candidates,
            at=args.at,
            requeue_at=args.requeue_at,
            absence_evidence=absence_evidence,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PostgresRuntimeError, RECONCILE.ReconciliationError, RECONCILE.KERNEL.KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def command_abandon_native_launch(args: argparse.Namespace) -> int:
    try:
        absence_evidence = _read_canonical_value(
            Path(args.absence_evidence), "native launch absence evidence"
        )
        if not isinstance(absence_evidence, dict):
            raise PostgresRuntimeError("native launch absence evidence must be a JSON object")
        result = abandon_native_launch_attempt(
            load_kernel(Path(args.kernel)),
            project_id=args.project_id,
            message_key=args.message_key,
            owner=args.owner,
            claim_token=token_from_env(args.claim_token_env),
            lease_generation=args.lease_generation,
            attempt_id=args.attempt_id,
            at=args.at,
            absence_evidence=absence_evidence,
            requeue_at=args.requeue_at,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PostgresRuntimeError, RECONCILE.ReconciliationError, RECONCILE.KERNEL.KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def command_settle(args: argparse.Namespace) -> int:
    try:
        receipt = RECONCILE.read_canonical_object(Path(args.receipt), "settlement receipt")
        result = settle(
            load_kernel(Path(args.kernel)),
            project_id=args.project_id,
            message_key=args.message_key,
            owner=args.owner,
            claim_token=token_from_env(args.claim_token_env),
            lease_generation=args.lease_generation,
            outcome=args.outcome,
            receipt=receipt,
            at=args.at,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PostgresRuntimeError, RECONCILE.ReconciliationError, RECONCILE.KERNEL.KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def command_cancel(args: argparse.Namespace) -> int:
    try:
        result = cancel(
            load_kernel(Path(args.kernel)),
            project_id=args.project_id,
            message_key=args.message_key,
            owner=args.owner,
            claim_token=token_from_env(args.claim_token_env),
            lease_generation=args.lease_generation,
            reason=args.reason,
            at=args.at,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (PostgresRuntimeError, RECONCILE.ReconciliationError, RECONCILE.KERNEL.KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def command_audit(args: argparse.Namespace) -> int:
    try:
        result = audit(load_kernel(Path(args.kernel)), args.project_id)
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("ok") else 2
    except (PostgresRuntimeError, RECONCILE.ReconciliationError, RECONCILE.KERNEL.KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    migration = sub.add_parser("migrate")
    migration.add_argument("--kernel", required=True)
    migration.set_defaults(handler=command_migrate)
    persist_parser = sub.add_parser("persist")
    persist_parser.add_argument("--kernel", required=True)
    persist_parser.add_argument("--request", required=True)
    persist_parser.add_argument("--plan", required=True)
    persist_parser.add_argument("--at", required=True)
    persist_parser.set_defaults(handler=command_persist)
    claim_parser = sub.add_parser("claim")
    claim_parser.add_argument("--kernel", required=True)
    claim_parser.add_argument("--project-id", required=True)
    claim_parser.add_argument("--owner", required=True)
    claim_parser.add_argument("--claim-token-env", required=True)
    claim_parser.add_argument("--now", required=True)
    claim_parser.add_argument("--lease-expires-at", required=True)
    claim_parser.add_argument("--message-key")
    claim_parser.set_defaults(handler=command_claim)
    prepare_native_parser = sub.add_parser(
        "prepare-native-launch",
        help="durably prepare a content-bound native host launch before create",
    )
    prepare_native_parser.add_argument("--kernel", required=True)
    prepare_native_parser.add_argument("--project-id", required=True)
    prepare_native_parser.add_argument("--message-key", required=True)
    prepare_native_parser.add_argument("--owner", required=True)
    prepare_native_parser.add_argument("--claim-token-env", required=True)
    prepare_native_parser.add_argument("--lease-generation", required=True, type=int)
    prepare_native_parser.add_argument("--attempt-id", required=True)
    prepare_native_parser.add_argument("--dispatch-digest", required=True)
    prepare_native_parser.add_argument("--initial-prompt-sha256", required=True)
    prepare_native_parser.add_argument("--at", required=True)
    prepare_native_parser.set_defaults(handler=command_prepare_native_launch)
    ambiguous_native_parser = sub.add_parser(
        "mark-native-launch-ambiguous",
        help="retain a possible native launch effect without claiming success",
    )
    ambiguous_native_parser.add_argument("--kernel", required=True)
    ambiguous_native_parser.add_argument("--project-id", required=True)
    ambiguous_native_parser.add_argument("--message-key", required=True)
    ambiguous_native_parser.add_argument("--owner", required=True)
    ambiguous_native_parser.add_argument("--claim-token-env", required=True)
    ambiguous_native_parser.add_argument("--lease-generation", required=True, type=int)
    ambiguous_native_parser.add_argument("--attempt-id", required=True)
    ambiguous_native_parser.add_argument("--at", required=True)
    ambiguous_native_parser.set_defaults(handler=command_mark_native_launch_ambiguous)
    reclaim_native_parser = sub.add_parser(
        "reclaim-native-launch",
        help="take an explicit fenced recovery lease without another host create",
    )
    reclaim_native_parser.add_argument("--kernel", required=True)
    reclaim_native_parser.add_argument("--project-id", required=True)
    reclaim_native_parser.add_argument("--message-key", required=True)
    reclaim_native_parser.add_argument("--owner", required=True)
    reclaim_native_parser.add_argument("--claim-token-env", required=True)
    reclaim_native_parser.add_argument("--expected-generation", required=True, type=int)
    reclaim_native_parser.add_argument("--now", required=True)
    reclaim_native_parser.add_argument("--lease-expires-at", required=True)
    reclaim_native_parser.set_defaults(handler=command_reclaim_native_launch)
    recover_native_parser = sub.add_parser(
        "recover-native-launch",
        help="bind one exact task, audit typed zero evidence while blocked, or block on conflict",
    )
    recover_native_parser.add_argument("--kernel", required=True)
    recover_native_parser.add_argument("--project-id", required=True)
    recover_native_parser.add_argument("--message-key", required=True)
    recover_native_parser.add_argument("--owner", required=True)
    recover_native_parser.add_argument("--claim-token-env", required=True)
    recover_native_parser.add_argument("--lease-generation", required=True, type=int)
    recover_native_parser.add_argument("--attempt-id", required=True)
    recover_native_parser.add_argument("--candidates", required=True)
    recover_native_parser.add_argument("--at", required=True)
    recover_native_parser.add_argument("--requeue-at")
    recover_native_parser.add_argument("--absence-evidence")
    recover_native_parser.set_defaults(handler=command_recover_native_launch)
    abandon_native_parser = sub.add_parser(
        "abandon-native-launch",
        help="compatibility alias: record typed zero evidence while remaining blocked; never requeues",
    )
    abandon_native_parser.add_argument("--kernel", required=True)
    abandon_native_parser.add_argument("--project-id", required=True)
    abandon_native_parser.add_argument("--message-key", required=True)
    abandon_native_parser.add_argument("--owner", required=True)
    abandon_native_parser.add_argument("--claim-token-env", required=True)
    abandon_native_parser.add_argument("--lease-generation", required=True, type=int)
    abandon_native_parser.add_argument("--attempt-id", required=True)
    abandon_native_parser.add_argument("--at", required=True)
    abandon_native_parser.add_argument("--absence-evidence", required=True)
    abandon_native_parser.add_argument("--requeue-at")
    abandon_native_parser.set_defaults(handler=command_abandon_native_launch)
    settle_parser = sub.add_parser("settle")
    settle_parser.add_argument("--kernel", required=True)
    settle_parser.add_argument("--project-id", required=True)
    settle_parser.add_argument("--message-key", required=True)
    settle_parser.add_argument("--owner", required=True)
    settle_parser.add_argument("--claim-token-env", required=True)
    settle_parser.add_argument("--lease-generation", required=True, type=int)
    settle_parser.add_argument("--outcome", required=True, choices=("succeeded", "failed"))
    settle_parser.add_argument("--receipt", required=True)
    settle_parser.add_argument("--at", required=True)
    settle_parser.set_defaults(handler=command_settle)
    cancel_parser = sub.add_parser("cancel")
    cancel_parser.add_argument("--kernel", required=True)
    cancel_parser.add_argument("--project-id", required=True)
    cancel_parser.add_argument("--message-key", required=True)
    cancel_parser.add_argument("--owner", required=True)
    cancel_parser.add_argument("--claim-token-env", required=True)
    cancel_parser.add_argument("--lease-generation", required=True, type=int)
    cancel_parser.add_argument("--reason", required=True)
    cancel_parser.add_argument("--at", required=True)
    cancel_parser.set_defaults(handler=command_cancel)
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--kernel", required=True)
    audit_parser.add_argument("--project-id", required=True)
    audit_parser.set_defaults(handler=command_audit)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
