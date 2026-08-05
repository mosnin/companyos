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
    return {"ok": True, "backend": "postgresql", "claim": result}


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
    kernel: dict[str, Any], *, project_id: str, message_key: str, reason: str, at: str
) -> dict[str, Any]:
    schema = quote_identifier(kernel["persistence"]["schema"])
    with database_connection(kernel, "cancellation") as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {schema}.cancel_command(%s,%s,%s,%s)",
                (project_id, message_key, reason, at),
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
