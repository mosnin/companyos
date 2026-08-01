#!/usr/bin/env python3

from __future__ import annotations

import json
import io
import os
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest import mock

import test_company_os_controller as controller_test

controller = controller_test.controller
store = controller.control_store_module()


class ControlStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = controller_test.ControllerTests(methodName="runTest")
        self.fixture.setUp()
        self.project = self.fixture.project

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def migrate_valid_state(self) -> dict:
        state = self.fixture.valid_state()
        self.fixture.write_state(state)
        result = controller.migrate_control_store(
            type("Args", (), {"project": str(self.project)})()
        )
        self.assertEqual(result, 0)
        return state

    def test_init_creates_authoritative_sqlite_store_and_exact_exports(self) -> None:
        empty_project = Path(tempfile.mkdtemp()).resolve()
        try:
            args = type(
                "Args",
                (),
                {
                    "project": str(empty_project),
                    "name": "Transactional",
                    "project_type": "software",
                    "north_star": "Never split state from evidence",
                },
            )()
            self.assertEqual(controller.init_instance(args), 0)
            self.assertTrue(store.database_path(empty_project).is_file())
            report = store.audit(empty_project)
            self.assertTrue(report["ok"], report["errors"])
            self.assertEqual(report["revision"], 1)
            self.assertTrue(report["state_export_match"])
            self.assertTrue(report["events_export_match"])
        finally:
            shutil.rmtree(empty_project)

    def test_initialization_failure_never_publishes_partial_authority(self) -> None:
        state = self.fixture.valid_state()
        event = {
            "at": controller.utc_now(),
            "type": "instance_initialized",
            "project_id": state["instance"]["project_id"],
            "program_version": state["strategy"]["program_version"],
        }
        with mock.patch.object(store, "_insert_revision", side_effect=RuntimeError("fault")):
            with self.assertRaises(RuntimeError):
                store.initialize(self.project, state, event)
        self.assertFalse(store.database_path(self.project).exists())
        self.assertEqual(
            list((self.project / ".company-os").glob(".control.db.*.initializing*")),
            [],
        )

    def test_migration_is_exact_idempotent_and_preserves_legacy_events(self) -> None:
        state = self.migrate_valid_state()
        revision, loaded = store.load(self.project)
        self.assertEqual(revision, 1)
        self.assertEqual(controller.canonical_json(loaded), controller.canonical_json(state))
        first_events = (self.project / ".company-os" / "events.jsonl").read_bytes()
        self.assertEqual(
            controller.migrate_control_store(type("Args", (), {"project": str(self.project)})()),
            0,
        )
        self.assertEqual(store.load(self.project)[0], 1)
        self.assertEqual(first_events, (self.project / ".company-os" / "events.jsonl").read_bytes())

    def test_migration_rejects_missing_corrupt_and_stale_sources(self) -> None:
        args = type("Args", (), {"project": str(self.project)})()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.migrate_control_store(args), 2)
        self.assertFalse(store.exists(self.project))

        directory = self.project / ".company-os"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "control.json").write_text('{"broken":', encoding="utf-8")
        (directory / "events.jsonl").write_text("", encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.migrate_control_store(args), 2)
        self.assertFalse(store.exists(self.project))

        stale = self.fixture.valid_state()
        stale["schema_version"] = controller.SCHEMA_VERSION - 1
        stale["core_version"] = "stale-core"
        self.fixture.write_state(stale)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.migrate_control_store(args), 2)
        self.assertFalse(store.exists(self.project))

    def test_governed_command_commits_one_revision_and_repairs_export_drift(self) -> None:
        self.migrate_valid_state()
        args = type(
            "Args",
            (),
            {
                "project": str(self.project),
                "north_star": "A new transactional mandate",
                "current_outcome": "Prove one committed revision",
                "success_metric": "Exactly one state and event pair",
                "reason": "transactional test",
            },
        )()
        self.assertEqual(controller.replace_program(args), 0)
        report = store.audit(self.project)
        self.assertEqual(report["revision"], 2)
        self.assertTrue(report["state_export_match"] and report["events_export_match"])

        authoritative = store.load(self.project)[1]
        (self.project / ".company-os" / "control.json").write_text('{"tampered":true}\n', encoding="utf-8")
        read_only = controller.audit_instance(type("Args", (), {"project": str(self.project)})())
        self.assertEqual(read_only, 1 if controller.validate_state(authoritative, expected_project=self.project)["errors"] else 0)
        self.assertEqual(store.load(self.project)[1], authoritative)
        self.assertFalse(store.audit(self.project)["state_export_match"])

        rejected = controller.record_evidence(
            type(
                "Args",
                (),
                {
                    "project": str(self.project),
                    "outcome": "reality",
                    "artifact": "missing.md",
                    "source": "test",
                    "decision_impact": "none",
                    "author": "a",
                    "reviewer": "b",
                    "freshness_days": 30,
                    "quality_dimensions": [],
                    "outcome_id": None,
                    "work_id": None,
                    "cycle_id": None,
                    "rubric_version": None,
                    "id": None,
                },
            )()
        )
        self.assertEqual(rejected, 2)
        repaired = store.audit(self.project)
        self.assertTrue(repaired["state_export_match"])
        self.assertEqual(repaired["revision"], 2)

        (self.project / ".company-os" / "events.jsonl").unlink()
        self.assertFalse(store.audit(self.project)["events_export_match"])
        rejected = controller.record_evidence(
            type(
                "Args",
                (),
                {
                    "project": str(self.project),
                    "outcome": "reality",
                    "artifact": "still-missing.md",
                    "source": "test",
                    "decision_impact": "none",
                    "author": "a",
                    "reviewer": "b",
                    "freshness_days": 30,
                    "quality_dimensions": [],
                    "outcome_id": None,
                    "work_id": None,
                    "cycle_id": None,
                    "rubric_version": None,
                    "id": None,
                },
            )()
        )
        self.assertEqual(rejected, 2)
        repaired = store.audit(self.project)
        self.assertTrue(repaired["events_export_match"])
        self.assertEqual(repaired["revision"], 2)

    def test_sqlite_single_writer_and_project_binding_fail_closed(self) -> None:
        self.migrate_valid_state()
        first = store.connect(self.project)
        second = store.connect(self.project)
        try:
            first.execute("BEGIN IMMEDIATE")
            second.execute("PRAGMA busy_timeout = 25")
            with self.assertRaises(sqlite3.OperationalError):
                second.execute("BEGIN IMMEDIATE")
        finally:
            first.rollback()
            second.rollback()
            first.close()
            second.close()

        other_root = Path(tempfile.mkdtemp()).resolve()
        try:
            (other_root / ".company-os").mkdir()
            shutil.copy2(store.database_path(self.project), store.database_path(other_root))
            with self.assertRaises(store.StoreError):
                store.load(other_root)
        finally:
            shutil.rmtree(other_root)

    @unittest.skipUnless(hasattr(os, "fork"), "requires process-level file locking")
    def test_two_process_lease_claim_has_exactly_one_owner(self) -> None:
        state = self.fixture.valid_state()
        state["controller"]["schedule_enabled"] = True
        self.fixture.write_state(state)
        self.assertEqual(
            controller.migrate_control_store(
                type("Args", (), {"project": str(self.project)})()
            ),
            0,
        )
        children: list[int] = []
        for owner in ("claimant-a", "claimant-b"):
            child = os.fork()
            if child == 0:
                result = controller.acquire_lease(
                    type(
                        "Args",
                        (),
                        {
                            "project": str(self.project),
                            "owner": owner,
                            "ttl_seconds": 300,
                        },
                    )()
                )
                os._exit(result)
            children.append(child)
        statuses = [os.waitpid(child, 0)[1] for child in children]
        exits = sorted(os.waitstatus_to_exitcode(status) for status in statuses)
        self.assertEqual(exits, [0, 2])
        state = store.load(self.project)[1]
        self.assertIn(state["controller"]["lease"]["owner"], {"claimant-a", "claimant-b"})
        self.assertEqual(store.audit(self.project)["revision"], 2)

    def test_idempotency_survives_restart_and_digest_conflict_rejects(self) -> None:
        state = self.migrate_valid_state()
        connection = store.connect(self.project)
        try:
            connection.execute("BEGIN IMMEDIATE")
            store.idempotency_record(
                connection,
                project_id=state["instance"]["project_id"],
                scope="runtime-launch",
                key="launch-1",
                command_name="launch",
                payload_sha256="a" * 64,
                result={"accepted": True},
                state_revision=1,
                created_at=controller.utc_now(),
            )
            connection.commit()
        finally:
            connection.close()
        reopened = store.connect(self.project)
        try:
            exact = store.idempotency_lookup(
                reopened,
                state["instance"]["project_id"],
                "runtime-launch",
                "launch-1",
                "a" * 64,
            )
            self.assertEqual(exact["result"], {"accepted": True})
            with self.assertRaises(store.StoreError):
                store.idempotency_lookup(
                    reopened,
                    state["instance"]["project_id"],
                    "runtime-launch",
                    "launch-1",
                    "b" * 64,
                )
        finally:
            reopened.close()

    def test_projection_tampering_is_detected(self) -> None:
        self.migrate_valid_state()
        connection = store.connect(self.project)
        try:
            connection.execute("UPDATE entities SET record_sha256 = ? WHERE entity_type = 'program'", ("0" * 64,))
            connection.commit()
        finally:
            connection.close()
        report = store.audit(self.project)
        self.assertFalse(report["ok"])
        self.assertIn("transactional entity projections do not match authoritative state", report["errors"])

    def test_migration_rejects_invalid_source_and_corrupt_existing_store(self) -> None:
        invalid = self.fixture.valid_state()
        invalid["instance"]["status"] = "invented"
        self.fixture.write_state(invalid)
        with redirect_stdout(output := io.StringIO()):
            result = controller.migrate_control_store(
                type("Args", (), {"project": str(self.project)})()
            )
        self.assertEqual(result, 2, output.getvalue())
        self.assertFalse(store.exists(self.project))

        self.fixture.write_state(self.fixture.valid_state())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                controller.migrate_control_store(
                    type("Args", (), {"project": str(self.project)})()
                ),
                0,
            )
        connection = store.connect(self.project)
        try:
            connection.execute(
                "UPDATE events SET payload_sha256=? WHERE state_revision=1",
                ("0" * 64,),
            )
            connection.commit()
        finally:
            connection.close()
        with redirect_stdout(output := io.StringIO()):
            result = controller.migrate_control_store(
                type("Args", (), {"project": str(self.project)})()
            )
        self.assertEqual(result, 2, output.getvalue())

    def test_audit_rejects_reordered_events_and_historical_hash_tampering(self) -> None:
        self.migrate_valid_state()
        self.assertEqual(
            controller.replace_program(
                type(
                    "Args",
                    (),
                    {
                        "project": str(self.project),
                        "north_star": "Historical integrity",
                        "current_outcome": "Audit every revision",
                        "success_metric": "Tampering is rejected",
                        "reason": "create second revision",
                    },
                )()
            ),
            0,
        )
        connection = store.connect(self.project)
        try:
            connection.execute("UPDATE events SET sequence=99 WHERE sequence=1")
            connection.execute("UPDATE events SET sequence=1 WHERE sequence=2")
            connection.execute("UPDATE events SET sequence=2 WHERE sequence=99")
            connection.commit()
        finally:
            connection.close()
        report = store.audit(self.project)
        self.assertFalse(report["ok"])
        self.assertIn("audit event order does not match state revision order", report["errors"])

        connection = store.connect(self.project)
        try:
            connection.execute("UPDATE events SET sequence=99 WHERE sequence=1")
            connection.execute("UPDATE events SET sequence=1 WHERE sequence=2")
            connection.execute("UPDATE events SET sequence=2 WHERE sequence=99")
            connection.execute(
                "UPDATE state_revisions SET state_json=state_json || ' ' WHERE revision=1"
            )
            connection.commit()
        finally:
            connection.close()
        report = store.audit(self.project)
        self.assertFalse(report["ok"])
        self.assertIn("a retained state revision hash is invalid", report["errors"])

    def test_database_constraints_and_audit_reject_duplicate_or_skipped_revisions(self) -> None:
        self.migrate_valid_state()
        connection = store.connect(self.project)
        try:
            retained = connection.execute(
                "SELECT * FROM state_revisions WHERE revision=1"
            ).fetchone()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO state_revisions VALUES (?,?,?,?,?,?)",
                    tuple(retained),
                )
            connection.rollback()
        finally:
            connection.close()

        self.assertEqual(
            controller.replace_program(
                type(
                    "Args",
                    (),
                    {
                        "project": str(self.project),
                        "north_star": "Contiguous history",
                        "current_outcome": "Reject a revision gap",
                        "success_metric": "Audit fails closed",
                        "reason": "adversarial history test",
                    },
                )()
            ),
            0,
        )
        connection = store.connect(self.project)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("DELETE FROM events WHERE state_revision=1")
            connection.execute("DELETE FROM state_revisions WHERE revision=1")
            connection.commit()
        finally:
            connection.close()
        report = store.audit(self.project)
        self.assertFalse(report["ok"])
        self.assertIn("state revision sequence is not contiguous from one", report["errors"])

    def test_cli_command_key_is_exactly_once_and_conflicts_fail_closed(self) -> None:
        self.migrate_valid_state()
        base = [
            "company-os",
            "replace-program",
            "--project",
            str(self.project),
            "--north-star",
            "Exactly once",
            "--current-outcome",
            "Prove command replay",
            "--success-metric",
            "One revision",
            "--reason",
            "transactional retry",
            "--command-key",
            "replace-once",
        ]
        with mock.patch.object(controller.sys, "argv", base), redirect_stdout(first := io.StringIO()):
            self.assertEqual(controller.main(), 0)
        self.assertEqual(store.load(self.project)[0], 2)
        with mock.patch.object(controller.sys, "argv", base), redirect_stdout(output := io.StringIO()):
            self.assertEqual(controller.main(), 0)
        self.assertEqual(first.getvalue(), output.getvalue())
        self.assertEqual(store.load(self.project)[0], 2)

        conflicting = [*base]
        conflicting[conflicting.index("transactional retry")] = "different payload"
        with mock.patch.object(controller.sys, "argv", conflicting), redirect_stdout(io.StringIO()):
            self.assertEqual(controller.main(), 2)
        self.assertEqual(store.load(self.project)[0], 2)

    def test_forged_replay_result_is_rejected_even_with_recomputed_hash(self) -> None:
        self.migrate_valid_state()
        command = [
            "company-os",
            "replace-program",
            "--project",
            str(self.project),
            "--north-star",
            "Authenticated replay",
            "--current-outcome",
            "Bind response to event",
            "--success-metric",
            "Forgery is rejected",
            "--reason",
            "adversarial replay",
            "--command-key",
            "replay-integrity",
        ]
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(io.StringIO()):
            self.assertEqual(controller.main(), 0)
        forged = store.canonical_json({"ok": False, "forged": True})
        connection = store.connect(self.project)
        try:
            connection.execute(
                "UPDATE command_idempotency SET result_json=?,result_sha256=? "
                "WHERE command_scope='controller-cli' AND command_key='replay-integrity'",
                (forged, store.sha256_bytes(forged.encode())),
            )
            connection.commit()
        finally:
            connection.close()
        report = store.audit(self.project)
        self.assertFalse(report["ok"])
        self.assertIn(
            "controller command replay result does not match its paired audit event",
            report["errors"],
        )
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(output := io.StringIO()):
            self.assertEqual(controller.main(), 2)
        self.assertIn("transactional control store failed integrity audit", output.getvalue())
        self.assertEqual(store.load(self.project)[0], 2)

    def test_forged_command_identity_is_rejected_by_paired_event_binding(self) -> None:
        self.migrate_valid_state()
        command = [
            "company-os",
            "replace-program",
            "--project",
            str(self.project),
            "--north-star",
            "Immutable command identity",
            "--current-outcome",
            "Bind the request",
            "--success-metric",
            "Substitution is rejected",
            "--reason",
            "identity test",
            "--command-key",
            "original-command",
        ]
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(io.StringIO()):
            self.assertEqual(controller.main(), 0)
        connection = store.connect(self.project)
        try:
            retained = connection.execute(
                "SELECT result_json FROM command_idempotency WHERE command_scope='controller-cli'"
            ).fetchone()
            result = json.loads(retained["result_json"])
            result["command"] = "cancel"
            result["command_key"] = "substituted-command"
            encoded = store.canonical_json(result)
            connection.execute(
                "UPDATE command_idempotency SET command_name='cancel',command_key='substituted-command',"
                "payload_sha256=?,result_json=?,result_sha256=? WHERE command_scope='controller-cli'",
                ("b" * 64, encoded, store.sha256_bytes(encoded.encode())),
            )
            connection.commit()
        finally:
            connection.close()
        report = store.audit(self.project)
        self.assertFalse(report["ok"])
        self.assertIn(
            "controller command identity does not match its paired audit event",
            report["errors"],
        )

    def test_foreign_project_rows_in_any_projection_fail_store_audit(self) -> None:
        state = self.migrate_valid_state()
        payload = store.canonical_json({"action": "foreign"})
        result = store.canonical_json({"accepted": True})
        connection = store.connect(self.project)
        try:
            connection.execute(
                "INSERT INTO outbox_messages(project_id,channel,message_key,payload_sha256,payload_json,status,attempt_count,not_before,created_revision,updated_revision) "
                "VALUES (?,?,?,?,?,'pending',0,NULL,1,1)",
                (
                    "foreign-project",
                    "runtime-launch",
                    "foreign-outbox",
                    store.sha256_bytes(payload.encode()),
                    payload,
                ),
            )
            connection.execute(
                "INSERT INTO command_idempotency VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "foreign-project",
                    "runtime-launch",
                    "foreign-command",
                    "launch",
                    "a" * 64,
                    result,
                    store.sha256_bytes(result.encode()),
                    1,
                    controller.utc_now(),
                ),
            )
            connection.commit()
        finally:
            connection.close()
        report = store.audit(self.project)
        self.assertFalse(report["ok"])
        self.assertIn("outbox_messages contains records for a foreign project", report["errors"])
        self.assertIn("command_idempotency contains records for a foreign project", report["errors"])

    def test_committed_authority_survives_export_publication_failure(self) -> None:
        self.migrate_valid_state()
        original_atomic = store._atomic_bytes
        calls = 0

        def fail_after_open_repairs(path: Path, value: bytes) -> None:
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("simulated export failure after commit")
            original_atomic(path, value)

        args = type(
            "Args",
            (),
            {
                "project": str(self.project),
                "north_star": "Committed authority",
                "current_outcome": "Survive export failure",
                "success_metric": "Database remains revision two",
                "reason": "fault injection",
            },
        )()
        with mock.patch.object(store, "_atomic_bytes", side_effect=fail_after_open_repairs), redirect_stderr(
            io.StringIO()
        ):
            self.assertEqual(controller.replace_program(args), 0)
        self.assertEqual(store.load(self.project)[0], 2)
        self.assertFalse(store.audit(self.project)["state_export_match"])
        store.repair_exports(self.project)
        self.assertTrue(store.audit(self.project)["state_export_match"])

    def test_cancellation_is_authoritative_over_stale_worker_completion(self) -> None:
        state = self.fixture.running_finish_state()
        state["controller"]["lease"]["allowed_transitions"] = sorted(
            controller.LEASE_TRANSITIONS
        )
        state["controller"]["lease"]["recovery_chain"] = []
        self.fixture.write_state(state)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                controller.migrate_control_store(
                    type("Args", (), {"project": str(self.project)})()
                ),
                0,
            )
            self.assertEqual(
                controller.cancel_instance(
                    type("Args", (), {"project": str(self.project), "reason": "operator stop"})()
                ),
                0,
            )
        revision, cancelled = store.load(self.project)
        self.assertEqual(revision, 2)
        self.assertTrue(cancelled["controller"]["cancellation_requested"])
        self.assertEqual(cancelled["feedback"]["cycles"][0]["status"], "cancelled")
        stale = type(
            "Args",
            (),
            {
                "project": str(self.project),
                "lease_id": "lease-substitution",
                "generation": 1,
                "owner": "scheduler",
                "cycle_id": "cycle-substitution",
            },
        )()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.finish_cycle(stale), 2)
        self.assertEqual(store.load(self.project)[0], 2)
        self.assertEqual(store.load(self.project)[1]["instance"]["status"], "cancelled")

    def test_outbox_and_idempotency_commit_with_state_and_enforce_lifecycle(self) -> None:
        state = self.migrate_valid_state()
        payload = {"attempt_id": "worker-1", "action": "launch"}
        payload_digest = store.sha256_bytes(store.canonical_json(payload).encode())
        transaction = store.begin(self.project)
        transaction.stage(
            deepcopy(state),
            {
                "at": controller.utc_now(),
                "type": "outbox_enqueued",
                "project_id": state["instance"]["project_id"],
                "program_version": state["strategy"]["program_version"],
            },
        )
        transaction.enqueue_outbox(channel="runtime-launch", key="worker-1", payload=payload)
        exact_retry = transaction.enqueue_outbox(
            channel="runtime-launch", key="worker-1", payload=payload
        )
        self.assertTrue(exact_retry["idempotent"])
        with self.assertRaises(store.StoreError):
            transaction.enqueue_outbox(
                channel="runtime-launch",
                key="worker-1",
                payload={"attempt_id": "worker-1", "action": "different"},
            )
        transaction.record_idempotency(
            scope="runtime-launch",
            key="worker-1",
            command_name="enqueue-launch",
            payload_sha256=payload_digest,
            result={"accepted": True},
            created_at=controller.utc_now(),
        )
        transaction.close(True)
        self.assertEqual(store.load(self.project)[0], 2)

        transaction = store.begin(self.project)
        self.assertIsNotNone(
            transaction.idempotency_lookup(
                scope="runtime-launch", key="worker-1", payload_sha256=payload_digest
            )
        )
        self.assertTrue(
            transaction.outbox_lookup(
                channel="runtime-launch", key="worker-1", payload_sha256=payload_digest
            )["status"]
            == "pending"
        )
        transaction.close(False)
        self.assertEqual(store.load(self.project)[0], 2)

        for revision, target in ((3, "leased"), (4, "failed"), (5, "leased"), (6, "succeeded")):
            transaction = store.begin(self.project)
            transaction.stage(
                deepcopy(transaction.state),
                {
                    "at": controller.utc_now(),
                    "type": f"outbox_{target}",
                    "project_id": state["instance"]["project_id"],
                    "program_version": state["strategy"]["program_version"],
                },
            )
            result = transaction.transition_outbox(
                channel="runtime-launch", key="worker-1", status=target
            )
            transaction.close(True)
            self.assertEqual(store.load(self.project)[0], revision)
        self.assertEqual(result["attempt_count"], 2)
        transaction = store.begin(self.project)
        transaction.stage(
            deepcopy(transaction.state),
            {
                "at": controller.utc_now(),
                "type": "invalid_retry",
                "project_id": state["instance"]["project_id"],
                "program_version": state["strategy"]["program_version"],
            },
        )
        with self.assertRaises(store.StoreError):
            transaction.transition_outbox(
                channel="runtime-launch", key="worker-1", status="leased"
            )
        transaction.close(False)
        self.assertEqual(store.load(self.project)[0], 6)
        self.assertTrue(store.audit(self.project)["ok"])


if __name__ == "__main__":
    unittest.main()
