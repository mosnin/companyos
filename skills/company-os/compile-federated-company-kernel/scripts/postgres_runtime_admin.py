#!/usr/bin/env python3
"""Provision and audit the PostgreSQL Company OS runtime authority boundary.

The command uses the local ``psql`` client so the core stays dependency-free.
It reads DSNs only from caller-named environment variables, never prints them,
and emits canonical JSON evidence. Runtime and scheduler activation are outside
this tool's authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


SCHEMA = "company-os"
EVIDENCE_SCHEMA = "company-os.postgresql-runtime-admin-evidence.v1"
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "references" / "postgresql-federated-runtime.sql"

API_SIGNATURES = (
    "persist_reconciliation(jsonb)",
    "claim_command(text,text,text,timestamptz,timestamptz,text)",
    "prepare_native_launch_attempt(text,text,text,text,bigint,text,text,text,timestamptz)",
    "mark_native_launch_ambiguous(text,text,text,text,bigint,text,timestamptz)",
    "reclaim_native_launch_attempt(text,text,text,text,bigint,timestamptz,timestamptz)",
    "recover_native_launch_attempt(text,text,text,text,bigint,text,text,timestamptz,timestamptz,text)",
    "abandon_native_launch_attempt(text,text,text,text,bigint,text,timestamptz,text,timestamptz)",
    "settle_command(text,text,text,text,bigint,text,text,text,timestamptz)",
    "cancel_command(text,text,text,text,bigint,text,timestamptz)",
    "audit_project(text)",
)
TRUSTED_OWNER_SIGNATURES = API_SIGNATURES + (
    "assert_project_runtime_principal(text)",
    "native_launch_content_sha256(text,text,text,text,text)",
    "reject_immutable_change()",
)


class AdminError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def identifier(value: str) -> str:
    if not isinstance(value, str) or NAME_RE.fullmatch(value) is None:
        raise AdminError("database role must be a simple PostgreSQL identifier")
    return '"' + value.replace('"', '""') + '"'


def literal(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
        raise AdminError("SQL text value must be non-empty trimmed text")
    return "'" + value.replace("'", "''") + "'"


def qualified(signature: str) -> str:
    return f'"{SCHEMA}".{signature}'


def catalog_signature(signature: str) -> str:
    """Match PostgreSQL's regprocedure text normalization."""
    return qualified(signature).replace("timestamptz", "timestamp with time zone")


def bootstrap_sql(project_id: str, runtime_role: str, definer_role: str, create_definer: bool) -> list[str]:
    runtime_ident = identifier(runtime_role)
    definer_ident = identifier(definer_role)
    runtime_lit = literal(runtime_role)
    definer_lit = literal(definer_role)
    project_lit = literal(project_id)
    statements: list[str] = []
    if create_definer:
        statements.append(
            "DO $company_os_create_definer$ BEGIN "
            f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname={definer_lit}) THEN "
            f"EXECUTE 'CREATE ROLE {definer_ident} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS'; "
            "END IF; END $company_os_create_definer$"
        )
    statements.append(
        "DO $company_os_validate_admin_roles$ BEGIN "
        f"IF NOT EXISTS (SELECT 1 FROM pg_roles r WHERE r.rolname={runtime_lit} AND r.rolcanlogin AND NOT r.rolinherit AND NOT r.rolsuper AND NOT r.rolcreatedb AND NOT r.rolcreaterole AND NOT r.rolreplication AND NOT r.rolbypassrls AND NOT EXISTS (SELECT 1 FROM pg_auth_members am WHERE am.member=r.oid)) THEN RAISE EXCEPTION 'runtime role is not a restricted direct NOINHERIT login with zero role memberships'; END IF; "
        f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname={definer_lit} AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls) THEN RAISE EXCEPTION 'definer role is not a restricted NOLOGIN role'; END IF; "
        f"IF NOT pg_has_role(current_user,{definer_lit},'MEMBER') AND NOT (SELECT rolsuper FROM pg_roles WHERE rolname=current_user) THEN RAISE EXCEPTION 'migration login cannot administer protected definer role'; END IF; "
        "END $company_os_validate_admin_roles$"
    )
    statements.extend(
        [
            f'SELECT "{SCHEMA}".bind_project_runtime_principal({project_lit},{runtime_lit}::name)',
            f'GRANT USAGE, CREATE ON SCHEMA "{SCHEMA}" TO {definer_ident}',
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{SCHEMA}" TO {definer_ident}',
            f'REVOKE ALL ON ALL TABLES IN SCHEMA "{SCHEMA}" FROM {runtime_ident}',
            f'REVOKE ALL ON ALL SEQUENCES IN SCHEMA "{SCHEMA}" FROM {runtime_ident}',
            f'REVOKE ALL ON ALL FUNCTIONS IN SCHEMA "{SCHEMA}" FROM {runtime_ident}',
            f'GRANT USAGE ON SCHEMA "{SCHEMA}" TO {runtime_ident}',
            f'REVOKE {definer_ident} FROM {runtime_ident}',
        ]
    )
    for signature in TRUSTED_OWNER_SIGNATURES:
        statements.append(f'ALTER FUNCTION {qualified(signature)} OWNER TO {definer_ident}')
    for signature in API_SIGNATURES:
        statements.append(f'GRANT EXECUTE ON FUNCTION {qualified(signature)} TO {runtime_ident}')
    return statements


def audit_query(project_id: str, runtime_role: str, definer_role: str) -> str:
    names = ",".join(literal(item.split("(", 1)[0]) for item in TRUSTED_OWNER_SIGNATURES)
    api_names = ",".join(literal(item.split("(", 1)[0]) for item in API_SIGNATURES)
    runtime_lit = literal(runtime_role)
    definer_lit = literal(definer_role)
    project_lit = literal(project_id)
    return f"""
WITH role_state AS (
  SELECT rolname, oid::bigint AS oid, rolcanlogin, rolinherit, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
  FROM pg_roles WHERE rolname IN ({runtime_lit},{definer_lit})
), memberships AS (
  SELECT member_role.rolname AS member_role,
         granted_role.rolname AS granted_role,
         am.admin_option
  FROM pg_auth_members am
  JOIN pg_roles member_role ON member_role.oid=am.member
  JOIN pg_roles granted_role ON granted_role.oid=am.roleid
  WHERE member_role.rolname={runtime_lit}
), functions AS (
  SELECT p.oid, p.oid::regprocedure::text AS signature, p.proname,
         pg_get_userbyid(p.proowner) AS owner,
         has_function_privilege({runtime_lit},p.oid,'EXECUTE') AS runtime_execute,
         has_function_privilege('public',p.oid,'EXECUTE') AS public_execute
  FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname={literal(SCHEMA)}
), tables AS (
  SELECT c.oid::regclass::text AS relation,
         has_table_privilege({runtime_lit},c.oid,'SELECT,INSERT,UPDATE,DELETE') AS runtime_dml
  FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname={literal(SCHEMA)} AND c.relkind IN ('r','p')
), expected(signature) AS (VALUES {','.join(f'({literal(catalog_signature(item))})' for item in API_SIGNATURES)}),
summary AS (
  SELECT jsonb_build_object(
    'project_binding_ok', EXISTS (SELECT 1 FROM "{SCHEMA}".project_runtime_principals WHERE project_id={project_lit} AND database_role={runtime_lit}::name),
    'runtime_role_ok', EXISTS (SELECT 1 FROM role_state WHERE rolname={runtime_lit} AND rolcanlogin AND NOT rolinherit AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls) AND NOT EXISTS (SELECT 1 FROM memberships),
    'definer_role_ok', EXISTS (SELECT 1 FROM role_state WHERE rolname={definer_lit} AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls),
    'owner_membership_denied', NOT pg_has_role({runtime_lit},{definer_lit},'MEMBER'),
    'runtime_membership_count', (SELECT count(*) FROM memberships),
    'api_count', (SELECT count(*) FROM functions WHERE proname IN ({api_names})),
    'all_api_execute', NOT EXISTS (SELECT 1 FROM expected e LEFT JOIN functions f ON f.signature=e.signature WHERE f.oid IS NULL OR NOT f.runtime_execute),
    'extra_execute_count', (SELECT count(*) FROM functions f WHERE f.runtime_execute AND NOT EXISTS (SELECT 1 FROM expected e WHERE e.signature=f.signature)),
    'public_execute_count', (SELECT count(*) FROM functions WHERE public_execute),
    'trusted_owner_count', (SELECT count(*) FROM functions WHERE proname IN ({names})),
    'trusted_owners_ok', NOT EXISTS (SELECT 1 FROM functions WHERE proname IN ({names}) AND owner<>{definer_lit}),
    'table_dml_count', (SELECT count(*) FROM tables WHERE runtime_dml)
  ) AS value
)
SELECT jsonb_build_object(
  'summary', value,
  'roles', (SELECT jsonb_agg(to_jsonb(role_state) ORDER BY rolname) FROM role_state),
  'memberships', COALESCE((SELECT jsonb_agg(to_jsonb(memberships) ORDER BY granted_role) FROM memberships), '[]'::jsonb),
  'functions', (SELECT jsonb_agg(to_jsonb(functions) ORDER BY signature) FROM functions WHERE proname IN ({names})),
  'tables', (SELECT jsonb_agg(to_jsonb(tables) ORDER BY relation) FROM tables)
) FROM summary
""".strip()


def audit_ok(payload: dict[str, Any]) -> bool:
    summary = payload.get("summary")
    return isinstance(summary, dict) and summary == {
        "all_api_execute": True,
        "api_count": 10,
        "definer_role_ok": True,
        "extra_execute_count": 0,
        "owner_membership_denied": True,
        "project_binding_ok": True,
        "public_execute_count": 0,
        "runtime_role_ok": True,
        "runtime_membership_count": 0,
        "table_dml_count": 0,
        "trusted_owner_count": 13,
        "trusted_owners_ok": True,
    }


def configured_dsn(env_name: str) -> str:
    if NAME_RE.fullmatch(env_name or "") is None:
        raise AdminError("DSN environment variable name is invalid")
    value = os.environ.get(env_name)
    if not value:
        raise AdminError(f"required DSN environment variable is absent: {env_name}")
    return value


def run_psql(dsn: str, sql: str) -> str:
    executable = shutil.which("psql")
    if executable is None:
        raise AdminError("psql is required for PostgreSQL administration")
    try:
        result = subprocess.run(
            [executable, dsn, "-X", "-v", "ON_ERROR_STOP=1", "-Atc", sql],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise AdminError(f"PostgreSQL administration failed ({type(exc).__name__})") from exc
    if result.returncode != 0:
        raise AdminError("PostgreSQL administration failed (psql)")
    return result.stdout.strip()


def execute_bootstrap(dsn: str, statements: list[str]) -> None:
    run_psql(dsn, "BEGIN;\n" + ";\n".join(statements) + ";\nCOMMIT;")


def collect_evidence(dsn: str, project_id: str, runtime_role: str, definer_role: str, target_label: str) -> dict[str, Any]:
    raw = run_psql(dsn, audit_query(project_id, runtime_role, definer_role))
    try:
        database = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AdminError("PostgreSQL audit did not return JSON") from exc
    if not isinstance(database, dict):
        raise AdminError("PostgreSQL audit returned an invalid payload")
    evidence = {
        "$schema": EVIDENCE_SCHEMA,
        "database": database,
        "migration_source_sha256": digest_bytes(MIGRATION.read_bytes()),
        "project_id": project_id,
        "runtime_activated": False,
        "runtime_role": runtime_role,
        "scheduler_activated": False,
        "target_label": target_label,
    }
    evidence["ok"] = audit_ok(database)
    return evidence


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=("bootstrap", "audit", "emit-bootstrap-sql"))
    result.add_argument("--dsn-env", default="COMPANY_OS_POSTGRES_ADMIN_DSN")
    result.add_argument("--project-id", required=True)
    result.add_argument("--runtime-role", required=True)
    result.add_argument("--definer-role", required=True)
    result.add_argument("--target-label", required=True)
    result.add_argument("--create-definer", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        statements = bootstrap_sql(args.project_id, args.runtime_role, args.definer_role, args.create_definer)
        if args.command == "emit-bootstrap-sql":
            print("BEGIN;\n" + ";\n".join(statements) + ";\nCOMMIT;")
            return 0
        dsn = configured_dsn(args.dsn_env)
        if args.command == "bootstrap":
            execute_bootstrap(dsn, statements)
        evidence = collect_evidence(dsn, args.project_id, args.runtime_role, args.definer_role, args.target_label)
        print(canonical_json(evidence))
        return 0 if evidence["ok"] else 1
    except AdminError as exc:
        print(canonical_json({"$schema": EVIDENCE_SCHEMA, "error": str(exc), "ok": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
