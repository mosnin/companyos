from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "company-os" / "compile-federated-company-kernel"
KERNEL_PATH = SKILL / "scripts" / "compile_federated_kernel.py"
RECONCILE_PATH = SKILL / "scripts" / "reconcile_federated_kernel.py"
POSTGRES_PATH = SKILL / "scripts" / "postgres_federated_runtime.py"
EXAMPLE = SKILL / "references" / "federated-kernel-request.example.json"
SQL_PATH = SKILL / "references" / "postgresql-federated-runtime.sql"
VALIDATION_RECEIPT = SKILL / "references" / "postgresql-validation-receipt.json"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


KERNEL = load("postgres_federated_kernel_tests", KERNEL_PATH)
RECONCILE = load("postgres_federated_reconcile_tests", RECONCILE_PATH)
POSTGRES = load("postgres_federated_runtime_tests", POSTGRES_PATH)


def compiled_kernel() -> dict:
    request = KERNEL.validate_request(json.loads(EXAMPLE.read_text()))
    mechanisms, _sources, mechanism_digest, source_digest = KERNEL.validate_mechanisms()
    return KERNEL.compile_kernel(request, mechanisms, mechanism_digest, source_digest)


def budget(tokens: int = 1000, cost: int = 100, wall: int = 60) -> dict:
    return {
        "max_tokens": tokens,
        "max_cost_microusd": cost,
        "max_wall_seconds": wall,
    }


def request_fixture(kernel: dict, *, count: int = 3) -> dict:
    cells = kernel["organization"]["manager_cells"][:count]
    return {
        "$schema": RECONCILE.REQUEST_SCHEMA,
        "kernel_digest": kernel["kernel_digest"],
        "generation": 1,
        "project_id": "atlas-project",
        "cycle_id": "cycle-1",
        "parent_runtime_id": "master-runtime-1",
        "budget_envelope": budget(tokens=10_000, cost=10_000, wall=300),
        "manager_admissions": [
            {"cell_id": cell["cell_id"], "budget": budget()} for cell in cells
        ],
        "observed_snapshot": {
            "$schema": RECONCILE.SNAPSHOT_SCHEMA,
            "last_event_cursor": 0,
            "attempts": [],
        },
    }


class PostgresFederatedRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.kernel = compiled_kernel()

    def plan(self, request: dict) -> tuple[dict, dict]:
        normalized = RECONCILE.validate_request(request, self.kernel)
        return normalized, RECONCILE.compile_plan(self.kernel, normalized)

    def test_record_is_deterministic_and_binds_complete_command_set(self) -> None:
        request, plan = self.plan(request_fixture(self.kernel))
        first = POSTGRES.build_record(
            self.kernel, request, plan, created_at="2026-08-05T12:00:00+00:00"
        )
        second = POSTGRES.build_record(
            self.kernel, deepcopy(request), deepcopy(plan), created_at="2026-08-05T12:00:00+00:00"
        )
        self.assertEqual(first, second)
        self.assertEqual(first["$schema"], POSTGRES.POSTGRESQL_ADAPTER_SCHEMA)
        self.assertEqual(len(first["commands"]), 3)
        self.assertEqual(first["plan_digest"], plan["plan_digest"])
        keys = sorted(item["message_key"] for item in first["commands"])
        self.assertEqual(first["command_set_digest"], POSTGRES.digest_text(",".join(keys)))
        for item in first["commands"]:
            self.assertEqual(item["payload_sha256"], POSTGRES.digest_text(item["payload_json"]))
            payload = json.loads(item["payload_json"])
            self.assertEqual(payload["command_digest"], item["message_key"])

    def test_sqlite_kernel_cannot_use_postgresql_adapter(self) -> None:
        raw = json.loads(EXAMPLE.read_text())
        raw["persistence"] = {"adapter": "sqlite", "dsn_env": None, "schema": "company-os"}
        request = KERNEL.validate_request(raw)
        mechanisms, _sources, mechanism_digest, source_digest = KERNEL.validate_mechanisms()
        sqlite_kernel = KERNEL.compile_kernel(request, mechanisms, mechanism_digest, source_digest)
        reconciliation = request_fixture(sqlite_kernel, count=1)
        normalized = RECONCILE.validate_request(reconciliation, sqlite_kernel)
        plan = RECONCILE.compile_plan(sqlite_kernel, normalized)
        with self.assertRaisesRegex(POSTGRES.PostgresRuntimeError, "not configured"):
            POSTGRES.build_record(
                sqlite_kernel,
                normalized,
                plan,
                created_at="2026-08-05T12:00:00+00:00",
            )

    def test_migration_parser_preserves_functions_and_renders_exact_schema(self) -> None:
        statements = POSTGRES.render_migration("tenant-control")
        joined = "\n".join(statements)
        self.assertGreaterEqual(len(statements), 20)
        self.assertNotIn('"company-os"', joined)
        self.assertIn('"tenant-control".persist_reconciliation', joined)
        self.assertIn('"tenant-control".claim_command', joined)
        self.assertIn('FOR UPDATE SKIP LOCKED', joined)
        self.assertIn('REVOKE ALL ON ALL FUNCTIONS', joined)
        self.assertTrue(all(statement.strip() for statement in statements))

    def test_sql_contract_has_immutable_history_fences_and_cancel_precedence(self) -> None:
        sql = SQL_PATH.read_text()
        self.assertIn("events_immutable", sql)
        self.assertIn("kernels_immutable", sql)
        self.assertIn("plans_immutable", sql)
        self.assertIn("command set digest does not verify", sql)
        self.assertIn("blocked reconciliation cannot enqueue commands", sql)
        self.assertIn("federated kernel request or plan binding is invalid", sql)
        self.assertIn("observation cursor would move backwards", sql)
        self.assertIn("same observation cursor conflicts", sql)
        self.assertIn("lease_generation = target.lease_generation + 1", sql)
        settle = sql.index('CREATE OR REPLACE FUNCTION "company-os".settle_command')
        cancelled = sql.index("IF v_command.status = 'cancelled'", settle)
        fence = sql.index("IF v_command.status <> 'leased'", settle)
        self.assertLess(cancelled, fence)
        self.assertNotRegex(sql, r"postgres(?:ql)?://")

    def test_missing_dsn_fails_without_exposing_or_inventing_credentials(self) -> None:
        env_name = self.kernel["persistence"]["dsn_env"]
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(POSTGRES.PostgresRuntimeError, env_name):
                POSTGRES.configured_dsn(self.kernel)

    def test_provider_failure_is_redacted_and_does_not_expose_dsn(self) -> None:
        class FakePsycopgError(Exception):
            pass

        class FakePsycopg:
            Error = FakePsycopgError

            @staticmethod
            def connect(_dsn: str):
                raise FakePsycopgError("postgresql://operator:secret@example.invalid/db")

        env_name = self.kernel["persistence"]["dsn_env"]
        with mock.patch.object(POSTGRES, "psycopg_module", return_value=FakePsycopg):
            with mock.patch.dict(os.environ, {env_name: "postgresql://secret"}, clear=True):
                with self.assertRaises(POSTGRES.PostgresRuntimeError) as raised:
                    POSTGRES.migrate(self.kernel)
        message = str(raised.exception)
        self.assertEqual(message, "PostgreSQL migration failed (FakePsycopgError)")
        self.assertNotIn("secret", message)

    def test_invalid_migration_schema_and_unclosed_sql_fail_closed(self) -> None:
        with self.assertRaises(POSTGRES.PostgresRuntimeError):
            POSTGRES.quote_identifier("bad_schema")
        with self.assertRaisesRegex(POSTGRES.PostgresRuntimeError, "unclosed"):
            POSTGRES.split_sql("CREATE FUNCTION x() RETURNS void AS $$ BEGIN")

    def test_checked_in_postgresql_kernel_requires_target_database_proof(self) -> None:
        self.assertIn(
            "postgresql_target_database_unverified",
            self.kernel["activation"]["blockers"],
        )

    def test_live_validation_receipt_is_canonical_and_binds_current_sources(self) -> None:
        raw = VALIDATION_RECEIPT.read_bytes()
        receipt = json.loads(raw)
        self.assertEqual(raw, (POSTGRES.canonical_json(receipt) + "\n").encode())
        self.assertEqual(
            receipt["schema_source_sha256"],
            POSTGRES.digest_text(SQL_PATH.read_text()),
        )
        self.assertEqual(
            receipt["adapter_source_sha256"],
            POSTGRES.digest_text(POSTGRES_PATH.read_text()),
        )
        self.assertEqual(receipt["tested_kernel_digest"], self.kernel["kernel_digest"])
        probes = {item["probe"] for item in receipt["evidence"]}
        self.assertEqual(
            probes,
            {
                "migration",
                "first_persistence",
                "idempotent_replay",
                "cross_project_binding",
                "parallel_claim",
                "cancellation_precedence",
                "lease_recovery",
                "history_mutation",
                "validation_audit",
                "recovery_audit",
            },
        )
        self.assertFalse(receipt["main_schema_mutated"])
        self.assertFalse(receipt["runtime_activated"])
        self.assertFalse(receipt["scheduler_activated"])


if __name__ == "__main__":
    unittest.main()
