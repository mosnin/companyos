from __future__ import annotations

from copy import deepcopy
import importlib.util
import inspect
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
VALIDATION_EVIDENCE = SKILL / "references" / "postgresql-validation-evidence.json"
ADMIN_VALIDATION_EVIDENCE = SKILL / "references" / "postgresql-admin-validation-evidence.json"
ADMIN_HARNESS = SKILL / "scripts" / "postgres_runtime_admin.py"


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
        self.assertIn("DROP FUNCTION IF EXISTS", sql)
        self.assertIn("pg_advisory_xact_lock", sql)
        self.assertIn("company-os:federated-runtime-migration:v2", sql)
        self.assertIn("native creation receipt does not bind the claimed command", sql)
        self.assertIn("company-os.codex-native-creation-receipt.v1", sql)
        settle = sql.index('CREATE OR REPLACE FUNCTION "company-os".settle_command')
        cancelled = sql.index("IF v_command.status = 'cancelled'", settle)
        fence = sql.index("IF v_command.status <> 'leased'", settle)
        self.assertLess(cancelled, fence)
        self.assertNotRegex(sql, r"postgres(?:ql)?://")

    def test_native_launch_attempt_protocol_is_durable_and_recovery_is_explicit(self) -> None:
        sql = SQL_PATH.read_text()
        self.assertIn('CREATE TABLE IF NOT EXISTS "company-os".native_launch_attempts', sql)
        self.assertIn("content_sha256", sql)
        self.assertIn("CREATE OR REPLACE FUNCTION \"company-os\".prepare_native_launch_attempt", sql)
        self.assertIn("CREATE OR REPLACE FUNCTION \"company-os\".mark_native_launch_ambiguous", sql)
        self.assertIn("CREATE OR REPLACE FUNCTION \"company-os\".reclaim_native_launch_attempt", sql)
        self.assertIn("CREATE OR REPLACE FUNCTION \"company-os\".recover_native_launch_attempt", sql)
        self.assertIn("CREATE OR REPLACE FUNCTION \"company-os\".abandon_native_launch_attempt", sql)
        self.assertIn("federated_native_launch_prepared", sql)
        self.assertNotIn("federated_native_launch_abandoned_requeued", sql)
        self.assertIn("federated_native_launch_conflict", sql)
        self.assertIn("federated_native_launch_bound", sql)
        self.assertIn(
            "v_attempt.creation_receipt_json::jsonb IS DISTINCT FROM v_receipt",
            sql,
        )
        self.assertNotIn(
            "v_attempt.creation_receipt_sha256 IS DISTINCT FROM p_receipt_sha256",
            sql,
        )
        self.assertIn("native launch recovery candidates must be a JSON array", sql)
        self.assertIn("(v_candidate ->> 'cell_id') IS DISTINCT FROM", sql)
        self.assertIn("native launch absence evidence is required for zero candidates", sql)
        self.assertIn("federated_native_launch_absence_observed", sql)
        self.assertIn("native launch attempt must be explicitly recovered before failure settlement", sql)
        self.assertIn("native launch recovery candidate does not bind the prepared content", sql)
        self.assertIn("federated command cancellation lease fence does not match", sql)
        self.assertIn("DROP FUNCTION IF EXISTS \"company-os\".cancel_command", sql)
        self.assertIn("status IN ('prepared', 'ambiguous', 'bound', 'abandoned', 'conflict')", sql)
        claim = sql.index('CREATE OR REPLACE FUNCTION "company-os".claim_command')
        settle = sql.index('CREATE OR REPLACE FUNCTION "company-os".settle_command')
        self.assertLess(
            sql.index("native_launch_attempts", claim),
            sql.index("FOR UPDATE SKIP LOCKED", claim),
        )
        self.assertIn("native launch attempt is not bound to the verified creation receipt", sql[settle:])
        self.assertLess(
            sql.index("IF v_command.status = 'cancelled'", settle),
            sql.index("native launch attempt is not bound", settle),
        )

    def test_native_launch_content_digest_matches_sql_binding_contract(self) -> None:
        fields = {
            "message_key": "a" * 64,
            "payload_sha256": "b" * 64,
            "attempt_id": "brokerage-manager-g1",
            "dispatch_digest": "c" * 64,
            "initial_prompt_sha256": "d" * 64,
        }
        expected = POSTGRES.digest_text("|".join(fields.values()))
        self.assertEqual(POSTGRES.native_launch_content_digest(**fields), expected)
        with self.assertRaisesRegex(POSTGRES.PostgresRuntimeError, "dispatch_digest"):
            POSTGRES.native_launch_content_digest(**{**fields, "dispatch_digest": "not-a-digest"})

    def test_native_candidate_file_may_encode_zero_but_does_not_authorize_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidates.json"
            path.write_text("[]\n", encoding="utf-8")
            self.assertEqual(POSTGRES._read_canonical_value(path, "candidates"), [])
            path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(POSTGRES.PostgresRuntimeError, "canonical"):
                POSTGRES._read_canonical_value(path, "candidates")

    def test_native_zero_candidate_recovery_is_audit_only_and_fail_closed(self) -> None:
        with self.assertRaisesRegex(POSTGRES.PostgresRuntimeError, "absence evidence"):
            POSTGRES.recover_native_launch_attempt(
                self.kernel,
                project_id="atlas-project",
                message_key="a" * 64,
                owner="recovery-worker",
                claim_token="claim-token",
                lease_generation=1,
                attempt_id="attempt-1",
                candidates=[],
                at="2026-08-05T12:00:00+00:00",
            )

        sql = SQL_PATH.read_text()
        zero = sql[sql.index("IF v_count = 0 THEN") : sql.index("IF v_count > 1 THEN")]
        recover = sql[sql.index('CREATE OR REPLACE FUNCTION "company-os".recover_native_launch_attempt') :]
        self.assertLess(
            recover.index("IF v_command.status = 'cancelled'"),
            recover.index("v_candidates := p_candidates_json::jsonb"),
        )
        self.assertIn("federated_native_launch_absence_observed", zero)
        self.assertIn("status = 'ambiguous'", zero)
        self.assertIn("'blocked', true", zero)
        self.assertIn("'requeued', false", zero)
        self.assertNotIn("status = 'failed'", zero)
        self.assertNotIn("not_before = v_requeue_at", zero)
        self.assertNotIn("lease_owner = NULL", zero)
        self.assertNotIn("lease_token_sha256 = NULL", zero)
        self.assertNotIn("lease_expires_at = NULL", zero)

        # The bridge can only submit a typed observation; even a self-attested
        # complete listing/read remains blocked by the SQL transition above.
        unsigned = {
            "$schema": "company-os.codex-native-absence-evidence.v1",
            "project_id": "atlas-project",
            "message_key": "a" * 64,
            "attempt_id": "attempt-1",
            "attempt_id_sha256": POSTGRES.digest_text("attempt-1"),
            "message_key_sha256": POSTGRES.digest_text("a" * 64),
            "content_sha256": "b" * 64,
            "dispatch_digest": "c" * 64,
            "observed_at": "2026-08-05T12:00:00+00:00",
            "listing_complete": True,
            "read_complete": True,
            "listed_task_ids": [],
            "read_task_ids": [],
            "scenario": "limit_saturated_or_truncated_timeout_read_failure_create_after_list_race",
        }
        self.assertEqual(len(unsigned), 14)
        self.assertNotIn("evidence_digest", unsigned)

    def test_cancel_requires_current_owner_token_and_generation_fence(self) -> None:
        signature = inspect.signature(POSTGRES.cancel)
        for name in ("owner", "claim_token", "lease_generation"):
            self.assertIn(name, signature.parameters)
        sql = SQL_PATH.read_text()
        cancel = sql[sql.index('CREATE OR REPLACE FUNCTION "company-os".cancel_command') :]
        self.assertIn("v_command.lease_owner <> p_owner", cancel)
        self.assertIn("v_command.lease_token_sha256 <> encode", cancel)
        self.assertIn("v_command.lease_generation <> p_lease_generation", cancel)
        self.assertIn("WHERE project_id = p_project_id AND message_key = p_message_key", cancel)

    def test_every_project_runtime_operation_requires_database_role_binding(self) -> None:
        sql = SQL_PATH.read_text()
        self.assertIn('CREATE TABLE IF NOT EXISTS "company-os".project_runtime_principals', sql)
        self.assertIn('CREATE OR REPLACE FUNCTION "company-os".bind_project_runtime_principal', sql)
        self.assertIn("project runtime principal is immutable", sql)
        self.assertIn("database role is already bound to another Company OS project", sql)
        self.assertIn("database role is not authorized for Company OS project", sql)
        # Eight direct project operations assert explicitly. The SQL
        # abandon wrapper delegates to recover (which asserts), while audit
        # references the assertion through its MATERIALIZED CTE.
        expected_calls = 8
        self.assertEqual(
            sql.count('PERFORM "company-os".assert_project_runtime_principal('),
            expected_calls,
        )
        audit = sql[sql.index('CREATE OR REPLACE FUNCTION "company-os".audit_project') :]
        self.assertIn('WITH authorized AS MATERIALIZED', audit)
        self.assertIn('FROM authorized;', audit)

    def test_runtime_api_is_execute_only_security_definer_boundary(self) -> None:
        sql = SQL_PATH.read_text()
        self.assertIn("database_role = session_user::name", sql)
        self.assertNotIn("database_role = current_user::name", sql)
        self.assertNotIn("SECURITY INVOKER", sql)
        self.assertNotRegex(sql, r"(?<!public\.)\bdigest\(")
        runtime_functions = (
            "assert_project_runtime_principal",
            "prepare_native_launch_attempt",
            "mark_native_launch_ambiguous",
            "reclaim_native_launch_attempt",
            "recover_native_launch_attempt",
            "abandon_native_launch_attempt",
            "persist_reconciliation",
            "claim_command",
            "settle_command",
            "cancel_command",
            "audit_project",
        )
        for index, name in enumerate(runtime_functions):
            start = sql.index(f'FUNCTION "company-os".{name}')
            later = [
                sql.find('CREATE OR REPLACE FUNCTION "company-os".', start + 1),
                sql.find('CREATE FUNCTION "company-os".', start + 1),
            ]
            ends = [position for position in later if position >= 0]
            end = min(ends) if ends else len(sql)
            body = sql[start:end]
            self.assertIn("SECURITY DEFINER", body, name)
            self.assertIn("SET search_path = pg_catalog", body, name)
        binding = sql[
            sql.index('FUNCTION "company-os".bind_project_runtime_principal') :
            sql.index('FUNCTION "company-os".assert_project_runtime_principal')
        ]
        self.assertNotIn("SECURITY DEFINER", binding)
        self.assertIn('REVOKE ALL ON ALL TABLES IN SCHEMA "company-os" FROM PUBLIC', sql)
        self.assertIn('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA "company-os" FROM PUBLIC', sql)
        self.assertIn("project_runtime_principals_database_role_idx", sql)
        self.assertIn("'claim-command-signature-v2'", sql)
        claim_gate = sql[
            sql.index("DO $company_os_claim_command_v2$") :
            sql.index('CREATE OR REPLACE FUNCTION "company-os".claim_command')
        ]
        self.assertIn("ON CONFLICT DO NOTHING", claim_gate)
        self.assertIn("RETURNING migration_key INTO v_acquired", claim_gate)
        self.assertIn("IF v_acquired IS NOT NULL THEN", claim_gate)

    def test_legacy_native_launch_states_are_quarantined_once_and_never_reprepared(self) -> None:
        sql = SQL_PATH.read_text()
        self.assertIn('CREATE TABLE IF NOT EXISTS "company-os".native_launch_legacy_quarantine', sql)
        self.assertIn("VALUES ('native-launch-authority-v2', transaction_timestamp())", sql)
        quarantine_gate = sql[
            sql.index("DO $company_os_native_launch_v2$") :
            sql.index("$company_os_native_launch_v2$;", sql.index("DO $company_os_native_launch_v2$"))
        ]
        self.assertIn("ON CONFLICT DO NOTHING", quarantine_gate)
        self.assertIn("RETURNING migration_key INTO v_acquired", quarantine_gate)
        self.assertIn("'legacy-unproven-absence'", sql)
        self.assertIn("'legacy-failed-command-active-launch'", sql)
        self.assertIn("'legacy-unverified-bound-receipt'", sql)
        self.assertIn("SET status = 'conflict'", sql)
        self.assertIn("legacy native launch attempt is quarantined; explicit resolution required", sql)
        self.assertNotIn("federated_native_launch_reprepared", sql)
        self.assertIn("native_launch_quarantines", sql)
        self.assertIn("v_attempt.status <> 'cancelled'", sql)

    def test_first_v2_upgrade_rebuilds_the_exact_bound_runtime_api(self) -> None:
        sql = SQL_PATH.read_text()
        gate = sql[
            sql.index("DO $company_os_restore_bound_runtime_acl$") :
            sql.index("$company_os_restore_bound_runtime_acl$;", sql.index("DO $company_os_restore_bound_runtime_acl$"))
        ]
        self.assertIn('FROM "company-os".project_runtime_principals', gate)
        self.assertIn("bound Company OS runtime role must be a restricted direct NOINHERIT login with zero role memberships", gate)
        self.assertIn("NOT r.rolreplication", gate)
        self.assertIn("NOT r.rolbypassrls", gate)
        self.assertIn("pg_auth_members", gate)
        self.assertIn('REVOKE ALL ON ALL TABLES IN SCHEMA "company-os"', gate)
        self.assertIn('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA "company-os"', gate)
        self.assertIn('GRANT USAGE ON SCHEMA "company-os"', gate)
        expected = {
            "persist_reconciliation",
            "claim_command",
            "prepare_native_launch_attempt",
            "mark_native_launch_ambiguous",
            "reclaim_native_launch_attempt",
            "recover_native_launch_attempt",
            "abandon_native_launch_attempt",
            "settle_command",
            "cancel_command",
            "audit_project",
        }
        granted = {
            line.split('"company-os".', 1)[1].split("(", 1)[0]
            for line in gate.splitlines()
            if 'GRANT EXECUTE ON FUNCTION "company-os".' in line
        }
        self.assertEqual(granted, expected)

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
        evidence_raw = VALIDATION_EVIDENCE.read_bytes()
        evidence = json.loads(evidence_raw)
        self.assertEqual(
            evidence_raw,
            (POSTGRES.canonical_json(evidence) + "\n").encode(),
        )
        self.assertEqual(
            receipt["machine_evidence_sha256"],
            POSTGRES.digest_text(evidence_raw.decode()),
        )
        self.assertEqual(
            receipt["machine_evidence_path"],
            "references/postgresql-validation-evidence.json",
        )
        self.assertEqual(
            receipt["schema_source_sha256"],
            POSTGRES.digest_text(SQL_PATH.read_text()),
        )
        self.assertEqual(
            receipt["adapter_source_sha256"],
            POSTGRES.digest_text(POSTGRES_PATH.read_text()),
        )
        self.assertRegex(receipt["bridge_source_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(receipt["tested_kernel_digest"], self.kernel["kernel_digest"])
        admin_raw = ADMIN_VALIDATION_EVIDENCE.read_bytes()
        admin = json.loads(admin_raw)
        self.assertEqual(admin_raw, (POSTGRES.canonical_json(admin) + "\n").encode())
        self.assertTrue(admin["ok"])
        self.assertFalse(admin["runtime_activated"])
        self.assertFalse(admin["scheduler_activated"])
        for role in admin["database"]["roles"]:
            self.assertFalse(role["rolreplication"], role["rolname"])
            self.assertFalse(role["rolbypassrls"], role["rolname"])
        self.assertEqual(admin["database"]["memberships"], [])
        self.assertEqual(admin["database"]["summary"]["runtime_membership_count"], 0)
        self.assertEqual(
            receipt["admin_evidence_sha256"],
            POSTGRES.digest_text(admin_raw.decode()),
        )
        self.assertEqual(
            receipt["admin_harness_sha256"],
            POSTGRES.digest_text(ADMIN_HARNESS.read_text()),
        )
        self.assertEqual(evidence["migration_statement_count"], 50)
        self.assertEqual(evidence["api_acl"]["api_count"], 10)
        self.assertTrue(evidence["api_acl"]["all_runtime_a_execute"])
        self.assertTrue(evidence["api_acl"]["all_runtime_b_execute"])
        self.assertTrue(evidence["api_acl"]["no_public_execute"])
        self.assertFalse(evidence["api_acl"]["protected_owner_can_login"])
        self.assertTrue(evidence["role_matrix"]["all_table_dml_denied"])
        self.assertTrue(evidence["role_matrix"]["owner_membership_denied"])
        self.assertEqual(evidence["role_matrix"]["runtime_membership_count"], 0)
        self.assertEqual(evidence["role_matrix"]["runtime_memberships"], [])
        membership = evidence["negative_membership_fixture"]
        self.assertTrue(membership["escape_reproduced"])
        self.assertTrue(membership["migration_rejected"])
        self.assertTrue(membership["admin_bootstrap_rejected"])
        self.assertTrue(membership["admin_audit_rejected"])
        self.assertTrue(membership["cleanup_verified"])
        for role in evidence["role_matrix"]["roles"]:
            self.assertFalse(role["replication"], role["role"])
            self.assertFalse(role["bypass_rls"], role["role"])
        self.assertEqual(evidence["concurrent_migration"]["exit_codes"], [0, 0])
        self.assertEqual(evidence["first_upgrade_acl"]["api_count"], 10)
        self.assertEqual(evidence["first_upgrade_acl"]["marker_before"], 0)
        self.assertEqual(evidence["first_upgrade_acl"]["marker_after"], 1)
        self.assertTrue(evidence["first_upgrade_acl"]["old_claim_signature_existed_before"])
        self.assertTrue(evidence["first_upgrade_acl"]["runtime_a_execute_after"])
        self.assertTrue(evidence["first_upgrade_acl"]["runtime_b_execute_after"])
        self.assertEqual(
            evidence["first_upgrade_acl"]["claim_owner_after_admin_bootstrap"],
            "company_os_runtime_definer",
        )
        self.assertEqual(evidence["first_upgrade_acl"]["direct_claim_rows_after_upgrade"], 0)
        self.assertEqual(evidence["legacy_quarantine"]["projects"], 3)
        self.assertEqual(evidence["legacy_quarantine"]["conflict_attempts"], 3)
        self.assertEqual(evidence["legacy_quarantine"]["rerun_rows"], 3)
        self.assertEqual(
            {item["reason_code"] for item in evidence["legacy_quarantine"]["rows"]},
            {
                "legacy-unproven-absence",
                "legacy-unverified-bound-receipt",
                "legacy-failed-command-active-launch",
            },
        )
        probes = {item["probe"] for item in receipt["evidence"]}
        self.assertEqual(
            probes,
            {
                "migration",
                "migration_rerun",
                "restricted_project_role_matrix",
                "first_persistence",
                "idempotent_replay",
                "native_prepare_before_create",
                "ordinary_reclaim_blocked",
                "zero_candidate_audit_only",
                "malformed_cell_rejected",
                "failed_settlement_blocked",
                "native_receipt_binding",
                "cancellation_fence",
                "cancellation_precedence",
                "pre_upgrade_atlas_audit",
                "pre_upgrade_cancel_audit",
                "legacy_upgrade_quarantine",
                "legacy_quarantine_blocks_execution",
                "legacy_upgrade_rerun",
            },
        )
        self.assertFalse(receipt["main_schema_mutated"])
        self.assertFalse(receipt["runtime_activated"])
        self.assertFalse(receipt["scheduler_activated"])


if __name__ == "__main__":
    unittest.main()
