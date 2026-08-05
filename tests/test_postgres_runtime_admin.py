from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "company-os" / "compile-federated-company-kernel" / "scripts" / "postgres_runtime_admin.py"


def load():
    spec = importlib.util.spec_from_file_location("postgres_runtime_admin_tests", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ADMIN = load()


class PostgresRuntimeAdminTests(unittest.TestCase):
    def test_exact_closed_api_and_owner_surface(self) -> None:
        self.assertEqual(len(ADMIN.API_SIGNATURES), 10)
        self.assertEqual(len(ADMIN.TRUSTED_OWNER_SIGNATURES), 13)
        self.assertEqual(len(set(ADMIN.API_SIGNATURES)), 10)
        self.assertIn("claim_command(text,text,text,timestamptz,timestamptz,text)", ADMIN.API_SIGNATURES)

    def test_bootstrap_requires_existing_restricted_runtime_and_protected_owner(self) -> None:
        statements = ADMIN.bootstrap_sql("project-a", "runtime_a", "runtime_definer", False)
        sql = ";\n".join(statements)
        self.assertIn("rolcanlogin AND NOT rolinherit", sql)
        self.assertIn("NOT rolcanlogin AND NOT rolinherit", sql)
        self.assertIn("NOT r.rolreplication", sql)
        self.assertIn("NOT r.rolbypassrls", sql)
        self.assertIn("NOT rolreplication", sql)
        self.assertIn("NOT rolbypassrls", sql)
        self.assertIn("pg_auth_members", sql)
        self.assertIn("bind_project_runtime_principal", sql)
        self.assertIn("REVOKE ALL ON ALL TABLES", sql)
        self.assertIn("REVOKE ALL ON ALL FUNCTIONS", sql)
        self.assertIn("REVOKE \"runtime_definer\" FROM \"runtime_a\"", sql)
        grants = [item for item in statements if item.startswith("GRANT EXECUTE ON FUNCTION")]
        owners = [item for item in statements if item.startswith("ALTER FUNCTION")]
        self.assertEqual(len(grants), 10)
        self.assertEqual(len(owners), 13)

    def test_create_definer_is_explicit_and_never_creates_runtime_login(self) -> None:
        without = ADMIN.bootstrap_sql("project-a", "runtime_a", "runtime_definer", False)
        with_create = ADMIN.bootstrap_sql("project-a", "runtime_a", "runtime_definer", True)
        self.assertFalse(any("CREATE ROLE" in item for item in without))
        self.assertTrue(any("CREATE ROLE \"runtime_definer\" NOLOGIN NOINHERIT" in item for item in with_create))
        self.assertTrue(any("NOREPLICATION NOBYPASSRLS" in item for item in with_create))
        self.assertFalse(any("CREATE ROLE \"runtime_a\"" in item for item in with_create))

    def test_names_and_literals_fail_closed(self) -> None:
        for bad in ("", "bad-role", "x;drop", "a" * 64):
            with self.assertRaises(ADMIN.AdminError):
                ADMIN.identifier(bad)
        with self.assertRaises(ADMIN.AdminError):
            ADMIN.literal(" bad")

    def test_audit_contract_rejects_every_bad_posture(self) -> None:
        good = {
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
        self.assertTrue(ADMIN.audit_ok({"summary": good}))
        for key in good:
            broken = dict(good)
            broken[key] = not good[key] if isinstance(good[key], bool) else good[key] + 1
            self.assertFalse(ADMIN.audit_ok({"summary": broken}), key)

    def test_audit_query_derives_acl_owner_role_and_table_evidence(self) -> None:
        sql = ADMIN.audit_query("project-a", "runtime_a", "runtime_definer")
        for term in (
            "project_runtime_principals",
            "has_function_privilege",
            "has_table_privilege",
            "pg_has_role",
            "pg_get_userbyid",
            "extra_execute_count",
            "public_execute_count",
            "trusted_owners_ok",
            "rolreplication",
            "rolbypassrls",
            "runtime_membership_count",
            "memberships",
        ):
            self.assertIn(term, sql)
        self.assertIn(
            '"company-os".claim_command(text,text,text,timestamp with time zone,timestamp with time zone,text)',
            sql,
        )

    def test_bootstrap_and_audit_fail_closed_on_replication_or_bypassrls_roles(self) -> None:
        bootstrap = ";\n".join(
            ADMIN.bootstrap_sql("project-a", "runtime_a", "runtime_definer", False)
        )
        audit = ADMIN.audit_query("project-a", "runtime_a", "runtime_definer")
        for sql in (bootstrap, audit):
            self.assertIn("rolreplication", sql)
            self.assertIn("rolbypassrls", sql)
            self.assertIn("pg_auth_members", sql)
        self.assertIn("NOREPLICATION NOBYPASSRLS", ";\n".join(
            ADMIN.bootstrap_sql("project-a", "runtime_a", "runtime_definer", True)
        ))

    def test_missing_dsn_and_provider_failure_are_redacted(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ADMIN.AdminError, "TEST_ADMIN_DSN"):
                ADMIN.configured_dsn("TEST_ADMIN_DSN")
        secret = "postgresql://operator:secret@example.invalid/db"
        failed = subprocess.CompletedProcess([], 2, "", "could not connect " + secret)
        with mock.patch.object(ADMIN.shutil, "which", return_value="/usr/bin/psql"):
            with mock.patch.object(ADMIN.subprocess, "run", return_value=failed):
                with self.assertRaises(ADMIN.AdminError) as raised:
                    ADMIN.run_psql(secret, "SELECT 1")
        self.assertNotIn("secret", str(raised.exception))
        self.assertNotIn("example.invalid", str(raised.exception))

    def test_collect_evidence_is_canonical_and_source_bound(self) -> None:
        database = {
            "summary": {
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
            },
            "functions": [],
            "memberships": [],
            "roles": [],
            "tables": [],
        }
        with mock.patch.object(ADMIN, "run_psql", return_value=json.dumps(database)):
            evidence = ADMIN.collect_evidence("secret", "project-a", "runtime_a", "runtime_definer", "branch-a")
        self.assertTrue(evidence["ok"])
        self.assertFalse(evidence["runtime_activated"])
        self.assertFalse(evidence["scheduler_activated"])
        self.assertRegex(evidence["migration_source_sha256"], r"^[0-9a-f]{64}$")
        encoded = ADMIN.canonical_json(evidence)
        self.assertEqual(encoded, json.dumps(json.loads(encoded), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    unittest.main()
