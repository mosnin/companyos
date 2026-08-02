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

    def initialize_stale_transition(self) -> tuple[dict, dict, dict]:
        source = self.fixture.valid_state()
        stale = self.fixture.stale_program_transition_state(source)
        transition_event_record = self.stage_stale_transition(source, stale)
        _, payload, _ = controller.prepare_stale_program_transition_repair(
            stale,
            source_state=source,
            transition_event_record=transition_event_record,
            source_state_revision=1,
            source_state_digest=controller.hashlib.sha256(
                controller.canonical_json(source).encode("utf-8")
            ).hexdigest(),
            transition_state_revision=2,
            transition_state_digest=controller.hashlib.sha256(
                controller.canonical_json(stale).encode("utf-8")
            ).hexdigest(),
        )
        return source, stale, payload

    def stage_stale_transition(
        self,
        source: dict,
        stale: dict,
        *,
        event_updates: dict | None = None,
    ) -> dict:
        store.initialize(
            self.project,
            source,
            {
                "at": controller.utc_now(),
                "type": "instance_initialized",
                "project_id": source["instance"]["project_id"],
                "program_version": 1,
            },
        )
        transition = store.begin(self.project)
        try:
            event = {
                "at": controller.utc_now(),
                "type": "program_replaced",
                "project_id": stale["instance"]["project_id"],
                "program_version": 2,
                "old_program_version": 1,
                "reason": stale["feedback"]["archived_evidence"][-1]["reason"],
            }
            event.update(event_updates or {})
            transition.stage(
                stale,
                event,
            )
        finally:
            transition.close(True)
        read_transaction = store.begin(self.project)
        try:
            transition_event_record = read_transaction.load_event(2)
        finally:
            read_transaction.close(False)
        return transition_event_record

    def repair_command(
        self,
        payload: dict,
        *,
        reviewer: str = "transition-repair-reviewer",
        command_key: str = "repair-transition-once",
    ) -> tuple[list[str], str]:
        repair_grant = self.fixture.grant(
            reviewer,
            "repair-program-transition",
            resource="program-transition:1:2",
            work_id="",
            cycle_id="",
            dimension="state-integrity",
            decision="archive-stale-authority",
            payload_hash=controller.command_payload_hash("repair-program-transition", payload),
            program_version=2,
        )
        return (
            [
                "company-os", "repair-program-transition", "--project", str(self.project),
                "--reviewer", reviewer, "--repair-grant", repair_grant,
                "--command-key", command_key,
            ],
            repair_grant,
        )

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

    def test_historical_revision_load_is_exact_hash_verified_and_bounded(self) -> None:
        original = self.migrate_valid_state()
        self.assertEqual(store.load_revision(self.project, 1), original)
        with self.assertRaises(store.StoreError):
            store.load_revision(self.project, 0)
        with self.assertRaises(store.StoreError):
            store.load_revision(self.project, 2)
        connection = store.connect(self.project)
        try:
            connection.execute(
                "UPDATE state_revisions SET state_json=? WHERE revision=1",
                ('{"tampered":true}',),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(store.StoreError):
            store.load_revision(self.project, 1)

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

    def test_stale_transition_repair_is_one_revision_exactly_once_and_preserves_authority(self) -> None:
        source = self.fixture.valid_state()
        stale = self.fixture.stale_program_transition_state(source)
        original_adaptations = deepcopy(stale["feedback"]["applied_adaptations"])
        original_quality = deepcopy(stale["quality"])
        store.initialize(
            self.project,
            source,
            {
                "at": controller.utc_now(),
                "type": "instance_initialized",
                "project_id": source["instance"]["project_id"],
                "program_version": 1,
            },
        )
        transition = store.begin(self.project)
        try:
            transition.stage(
                stale,
                {
                    "at": controller.utc_now(),
                    "type": "program_replaced",
                    "project_id": stale["instance"]["project_id"],
                    "program_version": 2,
                    "old_program_version": 1,
                    "reason": stale["feedback"]["archived_evidence"][-1]["reason"],
                },
            )
        finally:
            transition.close(True)
        read_transaction = store.begin(self.project)
        try:
            transition_event_record = read_transaction.load_event(2)
        finally:
            read_transaction.close(False)
        _, repair_payload, affected_actors = controller.prepare_stale_program_transition_repair(
            stale,
            source_state=source,
            transition_event_record=transition_event_record,
            source_state_revision=1,
            source_state_digest=controller.hashlib.sha256(
                controller.canonical_json(source).encode("utf-8")
            ).hexdigest(),
            transition_state_revision=2,
            transition_state_digest=controller.hashlib.sha256(
                controller.canonical_json(stale).encode("utf-8")
            ).hexdigest(),
        )
        self.assertNotIn("transition-repair-reviewer", affected_actors)
        repair_grant = self.fixture.grant(
            "transition-repair-reviewer", "repair-program-transition",
            resource="program-transition:1:2", work_id="", cycle_id="",
            dimension="state-integrity", decision="archive-stale-authority",
            payload_hash=controller.command_payload_hash(
                "repair-program-transition", repair_payload
            ),
            program_version=2,
        )
        command = [
            "company-os", "repair-program-transition", "--project", str(self.project),
            "--reviewer", "transition-repair-reviewer",
            "--repair-grant", repair_grant,
            "--command-key", "repair-transition-once",
        ]
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(first := io.StringIO()):
            self.assertEqual(controller.main(), 0)
        revision, repaired = store.load(self.project)
        self.assertEqual(revision, 3)
        self.assertEqual(repaired["feedback"]["applied_adaptations"], [])
        self.assertTrue(
            all(item["score"] is None for item in repaired["quality"]["dimensions"].values())
        )
        self.assertEqual(
            repaired["feedback"]["archived_adaptations"][-1]["applied_adaptations"],
            original_adaptations,
        )
        self.assertEqual(
            repaired["feedback"]["archived_quality_scorecards"][-1]["quality"],
            original_quality,
        )
        report = controller.validate_state(repaired, expected_project=self.project)
        self.assertFalse(
            any("stale program" in error or "governed project or program" in error for error in report["errors"]),
            report["errors"],
        )
        store_report = store.audit(self.project)
        self.assertTrue(store_report["ok"], store_report["errors"])
        self.assertEqual(
            repaired["feedback"]["archived_adaptations"][-1]["source_strategy"],
            source["strategy"],
        )
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(replay := io.StringIO()):
            self.assertEqual(controller.main(), 0)
        self.assertEqual(first.getvalue(), replay.getvalue())
        self.assertEqual(store.load(self.project)[0], 3)
        nonce_count = len(store.load(self.project)[1]["controller"]["consumed_grant_nonces"])
        distinct_retry = list(command)
        distinct_retry[-1] = "repair-transition-distinct-retry"
        with mock.patch.object(controller.sys, "argv", distinct_retry), redirect_stdout(io.StringIO()):
            self.assertEqual(controller.main(), 2)
        self.assertEqual(store.load(self.project)[0], 3)
        self.assertEqual(
            len(store.load(self.project)[1]["controller"]["consumed_grant_nonces"]),
            nonce_count,
        )

    def test_transition_repair_reviewer_conflict_rolls_back_revision_nonce_and_state(self) -> None:
        _, _, payload = self.initialize_stale_transition()
        command, _ = self.repair_command(payload, reviewer="quality-scorer")
        before_revision, before_state = store.load(self.project)
        before_events = (self.project / ".company-os" / "events.jsonl").read_bytes()
        before_nonces = list(before_state["controller"]["consumed_grant_nonces"])
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(io.StringIO()):
            self.assertEqual(controller.main(), 2)
        after_revision, after_state = store.load(self.project)
        self.assertEqual(after_revision, before_revision)
        self.assertEqual(after_state, before_state)
        self.assertEqual(after_state["controller"]["consumed_grant_nonces"], before_nonces)
        self.assertEqual((self.project / ".company-os" / "events.jsonl").read_bytes(), before_events)

    def test_transition_repair_archive_grant_score_strategy_and_candidate_tamper_fail_audit(self) -> None:
        _, _, payload = self.initialize_stale_transition()
        command, _ = self.repair_command(payload)
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(io.StringIO()):
            self.assertEqual(controller.main(), 0)
        repaired = store.load(self.project)[1]

        strategy_tamper = deepcopy(repaired)
        strategy_tamper["feedback"]["archived_adaptations"][0]["source_strategy"]["north_star"] = "tampered"
        self.assertTrue(
            any("source strategy" in error for error in controller.validate_state(strategy_tamper, expected_project=self.project)["errors"])
        )

        score_tamper = deepcopy(repaired)
        score_tamper["feedback"]["archived_quality_scorecards"][0]["quality"]["dimensions"]["user_value"]["score"] = 1
        self.assertTrue(
            any("archived_quality" in error for error in controller.validate_state(score_tamper, expected_project=self.project)["errors"])
        )

        grant_tamper = deepcopy(repaired)
        archived_adaptation = grant_tamper["feedback"]["archived_adaptations"][0]
        archived_adaptation["applied_adaptations"][0]["reviewer_grant"]["token"] += "tamper"
        archived_adaptation["archive_digest"] = controller.transition_archive_digest(archived_adaptation)
        self.assertTrue(
            any("reviewer grant" in error for error in controller.validate_state(grant_tamper, expected_project=self.project)["errors"])
        )

        candidate_tamper = deepcopy(repaired)
        candidate_tamper["feedback"]["program_transition_repairs"][0]["payload"]["candidate_state_digest"] = "0" * 64
        self.assertTrue(
            any("repair grant" in error for error in controller.validate_state(candidate_tamper, expected_project=self.project)["errors"])
        )

    def test_transition_repair_history_and_candidate_digest_tamper_fail_store_audit(self) -> None:
        _, _, payload = self.initialize_stale_transition()
        command, _ = self.repair_command(payload)
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(io.StringIO()):
            self.assertEqual(controller.main(), 0)

        connection = store.connect(self.project)
        try:
            source_row = connection.execute(
                "SELECT state_json FROM state_revisions WHERE revision=1"
            ).fetchone()
            source_state = json.loads(source_row["state_json"])
            source_state["strategy"]["north_star"] = "tampered historical source"
            encoded = store.canonical_json(source_state)
            connection.execute(
                "UPDATE state_revisions SET state_json=?,state_sha256=? WHERE revision=1",
                (encoded, store.sha256_bytes(encoded.encode())),
            )
            connection.commit()
        finally:
            connection.close()
        history_report = store.audit(self.project)
        self.assertTrue(
            any("historical state digest" in error or "source transition" in error for error in history_report["errors"]),
            history_report["errors"],
        )

        # Restore by rebuilding this disposable fixture, then tamper the signed
        # candidate digest while maintaining the row's ordinary hash.
        self.tearDown()
        self.setUp()
        _, _, payload = self.initialize_stale_transition()
        command, _ = self.repair_command(payload)
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(io.StringIO()):
            self.assertEqual(controller.main(), 0)
        connection = store.connect(self.project)
        try:
            repair_row = connection.execute(
                "SELECT state_json FROM state_revisions WHERE revision=3"
            ).fetchone()
            repair_state = json.loads(repair_row["state_json"])
            repair_state["feedback"]["program_transition_repairs"][0]["payload"]["candidate_state_digest"] = "f" * 64
            encoded = store.canonical_json(repair_state)
            connection.execute(
                "UPDATE state_revisions SET state_json=?,state_sha256=? WHERE revision=3",
                (encoded, store.sha256_bytes(encoded.encode())),
            )
            connection.commit()
        finally:
            connection.close()
        candidate_report = store.audit(self.project)
        self.assertTrue(
            any("candidate state digest" in error or "signed payload" in error for error in candidate_report["errors"]),
            candidate_report["errors"],
        )

    def test_repaired_prior_quality_cannot_resurface_when_replacement_work_is_queued(self) -> None:
        _, _, payload = self.initialize_stale_transition()
        command, _ = self.repair_command(payload)
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(io.StringIO()):
            self.assertEqual(controller.main(), 0)
        self.assertEqual(
            controller.commit_outcome(
                controller_test.namespace(
                    project=str(self.project), id="replacement-outcome", type="capability",
                    title="Replacement capability", user_visible_outcome="A user sees the replacement",
                )
            ),
            0,
        )
        self.assertEqual(
            controller.queue_work(
                controller_test.namespace(
                    project=str(self.project), id="replacement-work", type="capability",
                    title="Build replacement capability",
                    user_visible_outcome="A user sees the replacement",
                    claimed_progress="capability", owner="replacement-owner", primary="true",
                    unlocks=[], outcome_id="replacement-outcome", incident_ref=None,
                    severity=None, justification=None, incident_actor=None, incident_grant=None,
                    approval_actor=None, approval_grant=None, repeat_override_reason=None,
                    repeat_override_reviewer=None, repeat_override_grant=None,
                )
            ),
            0,
        )
        queued = store.load(self.project)[1]
        self.assertEqual(queued["portfolio"]["active_work"][0]["program_version"], 2)
        self.assertTrue(
            all(item["score"] is None for item in queued["quality"]["dimensions"].values())
        )
        report = controller.validate_state(queued, expected_project=self.project)
        self.assertFalse(
            any("retains authority outside the current checkpoint" in error for error in report["errors"]),
            report["errors"],
        )

    def test_transition_repair_record_requires_exactly_one_atomic_repair_event(self) -> None:
        _, _, payload = self.initialize_stale_transition()
        command, _ = self.repair_command(payload)
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(io.StringIO()):
            self.assertEqual(controller.main(), 0)
        connection = store.connect(self.project)
        try:
            row = connection.execute(
                "SELECT state_json FROM state_revisions WHERE revision=3"
            ).fetchone()
            repaired = json.loads(row["state_json"])
            repaired["feedback"]["program_transition_repairs"] = []
            encoded = store.canonical_json(repaired)
            connection.execute(
                "UPDATE state_revisions SET state_json=?,state_sha256=? WHERE revision=3",
                (encoded, store.sha256_bytes(encoded.encode())),
            )
            connection.commit()
        finally:
            connection.close()
        report = store.audit(self.project)
        self.assertIn(
            "program transition repair records and atomic repair events are not one-to-one",
            report["errors"],
        )

    def test_transition_repair_rejects_unrelated_source_to_transition_mutation_before_grant(self) -> None:
        source = self.fixture.valid_state()
        stale = self.fixture.stale_program_transition_state(source)
        stale["profile"]["maturity"] = "unrelated-mutation"
        self.stage_stale_transition(source, stale)
        before_revision, before_state = store.load(self.project)
        command = [
            "company-os", "repair-program-transition", "--project", str(self.project),
            "--reviewer", "independent-repair-reviewer", "--repair-grant", "not-a-grant",
            "--command-key", "reject-unrelated-transition-mutation",
        ]
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(output := io.StringIO()):
            self.assertEqual(controller.main(), 2)
        self.assertIn("unrelated transition mutation", output.getvalue())
        self.assertEqual(store.load(self.project), (before_revision, before_state))

    def test_transition_repair_store_audit_catches_later_replace_event_tamper(self) -> None:
        _, _, payload = self.initialize_stale_transition()
        command, _ = self.repair_command(payload)
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(io.StringIO()):
            self.assertEqual(controller.main(), 0)
        connection = store.connect(self.project)
        try:
            row = connection.execute(
                "SELECT payload_json FROM events WHERE state_revision=2"
            ).fetchone()
            event = json.loads(row["payload_json"])
            event["reason"] = "tampered after independently authorized repair"
            encoded = store.canonical_json(event)
            connection.execute(
                "UPDATE events SET payload_json=?,payload_sha256=? WHERE state_revision=2",
                (encoded, store.sha256_bytes(encoded.encode())),
            )
            connection.commit()
        finally:
            connection.close()
        report = store.audit(self.project)
        self.assertTrue(
            any("retained replace-program event binding is not replay-valid" in error for error in report["errors"]),
            report["errors"],
        )

    def test_transition_repair_rejects_bogus_archived_evidence_snapshot_before_grant(self) -> None:
        source = self.fixture.valid_state()
        evidence = source["evidence"]["verification"][0]
        bogus_digest = "a" * 64
        bogus_path = f".company-os/evidence/sha256/{bogus_digest}"
        evidence.update(
            {
                "artifact_path": bogus_path,
                "artifact_sha256": bogus_digest,
                "snapshot_path": bogus_path,
                "snapshot_sha256": bogus_digest,
            }
        )
        stale = self.fixture.stale_program_transition_state(source)
        self.stage_stale_transition(source, stale)
        before = store.load(self.project)
        command = [
            "company-os", "repair-program-transition", "--project", str(self.project),
            "--reviewer", "independent-repair-reviewer", "--repair-grant", "not-a-grant",
            "--command-key", "reject-bogus-evidence-snapshot",
        ]
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(output := io.StringIO()):
            self.assertEqual(controller.main(), 2)
        self.assertIn("snapshot does not exist", output.getvalue())
        self.assertEqual(store.load(self.project), before)

    def test_transition_repair_rejects_archived_evidence_self_review_before_grant(self) -> None:
        source = self.fixture.valid_state()
        evidence = source["evidence"]["verification"][0]
        evidence["reviewer"] = evidence["author"]
        stale = self.fixture.stale_program_transition_state(source)
        self.stage_stale_transition(source, stale)
        before = store.load(self.project)
        command = [
            "company-os", "repair-program-transition", "--project", str(self.project),
            "--reviewer", "independent-repair-reviewer", "--repair-grant", "not-a-grant",
            "--command-key", "reject-evidence-self-review",
        ]
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(output := io.StringIO()):
            self.assertEqual(controller.main(), 2)
        self.assertIn("lacks independent review", output.getvalue())
        self.assertEqual(store.load(self.project), before)

    def test_transition_repair_rejects_every_archived_evidence_actor_as_reviewer(self) -> None:
        source, _, payload = self.initialize_stale_transition()
        evidence = source["evidence"]["verification"][0]
        for index, actor in enumerate((evidence["author"], evidence["reviewer"])):
            command, _ = self.repair_command(
                payload,
                reviewer=actor,
                command_key=f"reject-evidence-actor-{index}",
            )
            before = store.load(self.project)
            with mock.patch.object(controller.sys, "argv", command), redirect_stdout(output := io.StringIO()):
                self.assertEqual(controller.main(), 2)
            self.assertIn("independent of every affected authority actor", output.getvalue())
            self.assertEqual(store.load(self.project), before)

    def test_transition_repair_runtime_archive_tamper_fails_history_replay(self) -> None:
        _, _, payload = self.initialize_stale_transition()
        command, _ = self.repair_command(payload)
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(io.StringIO()):
            self.assertEqual(controller.main(), 0)
        connection = store.connect(self.project)
        try:
            row = connection.execute(
                "SELECT state_json FROM state_revisions WHERE revision=3"
            ).fetchone()
            repaired = json.loads(row["state_json"])
            runtime_archive = repaired["feedback"]["archived_runtime_adapters"][0]
            runtime_archive["runtime_adapter"]["status"] = "enabled"
            runtime_archive["archive_digest"] = controller.transition_archive_digest(runtime_archive)
            encoded = store.canonical_json(repaired)
            connection.execute(
                "UPDATE state_revisions SET state_json=?,state_sha256=? WHERE revision=3",
                (encoded, store.sha256_bytes(encoded.encode())),
            )
            connection.commit()
        finally:
            connection.close()
        report = store.audit(self.project)
        self.assertTrue(
            any("archives do not exactly preserve the source transition" in error for error in report["errors"]),
            report["errors"],
        )

    def test_replace_program_rejects_nested_token_variants_without_authority_mutation(self) -> None:
        source = self.fixture.valid_state()
        source["runtime_adapter"]["archive_probe"] = {
            "provider": {"provider_token": "provider-secret"},
            "transport": {"bearer_token": "bearer-secret"},
            "client": {"client_token": "client-secret"},
        }
        store.initialize(
            self.project,
            source,
            {
                "at": controller.utc_now(),
                "type": "instance_initialized",
                "project_id": source["instance"]["project_id"],
                "program_version": 1,
            },
        )
        before_revision, before_state = store.load(self.project)
        directory = self.project / ".company-os"
        before_exports = (
            (directory / "control.json").read_bytes(),
            (directory / "events.jsonl").read_bytes(),
        )
        connection = store.connect(self.project)
        try:
            before_counts = tuple(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("state_revisions", "events", "command_idempotency")
            )
        finally:
            connection.close()
        with redirect_stdout(output := io.StringIO()):
            self.assertEqual(
                controller.replace_program(
                    controller_test.namespace(
                        project=str(self.project),
                        north_star="Reject archived runtime credentials",
                        current_outcome="Preserve authority atomically",
                        success_metric="No revision, event, or nonce mutation",
                        reason="nested token variants",
                    )
                ),
                2,
            )
        for field in ("provider_token", "bearer_token", "client_token"):
            self.assertIn(field, output.getvalue())
        self.assertEqual(store.load(self.project), (before_revision, before_state))
        self.assertEqual(
            store.load(self.project)[1]["controller"]["consumed_grant_nonces"],
            before_state["controller"]["consumed_grant_nonces"],
        )
        self.assertEqual(
            before_exports,
            (
                (directory / "control.json").read_bytes(),
                (directory / "events.jsonl").read_bytes(),
            ),
        )
        connection = store.connect(self.project)
        try:
            self.assertEqual(
                tuple(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in ("state_revisions", "events", "command_idempotency")
                ),
                before_counts,
            )
        finally:
            connection.close()

    def test_transition_repair_rejects_nested_token_variants_without_authority_mutation(self) -> None:
        source = self.fixture.valid_state()
        source["runtime_adapter"]["archive_probe"] = {
            "provider": {"provider_token": "provider-secret"},
            "transport": {"bearer_token": "bearer-secret"},
            "client": {"client_token": "client-secret"},
        }
        stale = self.fixture.stale_program_transition_state(source)
        self.stage_stale_transition(source, stale)
        before_revision, before_state = store.load(self.project)
        directory = self.project / ".company-os"
        before_exports = (
            (directory / "control.json").read_bytes(),
            (directory / "events.jsonl").read_bytes(),
        )
        connection = store.connect(self.project)
        try:
            before_counts = tuple(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("state_revisions", "events", "command_idempotency")
            )
        finally:
            connection.close()
        command = [
            "company-os", "repair-program-transition", "--project", str(self.project),
            "--reviewer", "independent-repair-reviewer", "--repair-grant", "not-a-grant",
            "--command-key", "reject-nested-runtime-token-variants",
        ]
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(output := io.StringIO()):
            self.assertEqual(controller.main(), 2)
        for field in ("provider_token", "bearer_token", "client_token"):
            self.assertIn(field, output.getvalue())
        self.assertEqual(store.load(self.project), (before_revision, before_state))
        self.assertEqual(
            store.load(self.project)[1]["controller"]["consumed_grant_nonces"],
            before_state["controller"]["consumed_grant_nonces"],
        )
        self.assertEqual(
            before_exports,
            (
                (directory / "control.json").read_bytes(),
                (directory / "events.jsonl").read_bytes(),
            ),
        )
        connection = store.connect(self.project)
        try:
            self.assertEqual(
                tuple(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in ("state_revisions", "events", "command_idempotency")
                ),
                before_counts,
            )
        finally:
            connection.close()

    def test_supersede_evidence_cli_retry_is_exact_across_restart_and_conflicts_fail_closed(self) -> None:
        state = self.fixture.valid_state()
        state["instance"]["status"] = "paused"
        state["portfolio"]["active_work"] = []
        state["controller"]["validation"] = None
        state["controller"]["validated"] = False
        predecessor = state["evidence"]["reality"][0]
        predecessor["id"] = "transactional-drift"
        source = self.project / predecessor["artifact_path"]
        self.fixture.write_state(state)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                controller.migrate_control_store(
                    type("Args", (), {"project": str(self.project)})()
                ),
                0,
            )
        source.write_text("transactional replacement\n", encoding="utf-8")
        args = self.fixture.supersession_args(
            state, "transactional-drift", source, "transactional-repaired"
        )
        command = [
            "company-os", "supersede-evidence", "--project", str(self.project),
            "--evidence-id", args.evidence_id, "--artifact", args.artifact,
            "--source", args.source, "--decision-impact", args.decision_impact,
            "--author", args.author, "--reviewer", args.reviewer,
            "--reviewer-grant", args.reviewer_grant, "--reason", args.reason,
            "--id", args.id, "--command-key", "supersede-once",
        ]
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(first := io.StringIO()):
            self.assertEqual(controller.main(), 0)
        self.assertEqual(store.load(self.project)[0], 2)

        # Reopen through main/store lookup to prove the acknowledgment survives
        # the original command transaction and no grant is consumed twice.
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(replay := io.StringIO()):
            self.assertEqual(controller.main(), 0)
        self.assertEqual(first.getvalue(), replay.getvalue())
        self.assertEqual(store.load(self.project)[0], 2)

        conflicting = list(command)
        conflicting[conflicting.index(args.reason)] = "different repair reason"
        with mock.patch.object(controller.sys, "argv", conflicting), redirect_stdout(io.StringIO()):
            self.assertEqual(controller.main(), 2)
        self.assertEqual(store.load(self.project)[0], 2)

    def test_correct_evidence_cli_retry_is_exact_across_restart_and_conflicts_fail_closed(self) -> None:
        _, _, args, _, _ = self.fixture.commit_correction_fixture()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                controller.migrate_control_store(
                    type("Args", (), {"project": str(self.project)})()
                ),
                0,
            )
        command = [
            "company-os", "correct-evidence", "--project", str(self.project),
            "--evidence-id", args.evidence_id, "--artifact", args.artifact,
            "--source", args.source, "--decision-impact", args.decision_impact,
            "--reason", args.reason, "--declarant", args.declarant,
            "--adjudicator", args.adjudicator, "--declarant-grant", args.declarant_grant,
            "--adjudicator-grant", args.adjudicator_grant, "--old-value", args.old_value,
            "--new-value", args.new_value, "--transition-at", args.transition_at,
            "--freshness-days", "30", "--id", args.id,
            "--command-key", "correct-once",
        ]
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(first := io.StringIO()):
            self.assertEqual(controller.main(), 0)
        self.assertEqual(store.load(self.project)[0], 2)
        with mock.patch.object(controller.sys, "argv", command), redirect_stdout(replay := io.StringIO()):
            self.assertEqual(controller.main(), 0)
        self.assertEqual(first.getvalue(), replay.getvalue())
        self.assertEqual(store.load(self.project)[0], 2)

        conflicting = list(command)
        conflicting[conflicting.index(args.reason)] = "different semantic correction reason"
        with mock.patch.object(controller.sys, "argv", conflicting), redirect_stdout(io.StringIO()):
            self.assertEqual(controller.main(), 2)
        self.assertEqual(store.load(self.project)[0], 2)

    def test_correct_evidence_post_publication_failure_preserves_authoritative_transaction(self) -> None:
        _, artifact, args, _, _ = self.fixture.commit_correction_fixture()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                controller.migrate_control_store(
                    type("Args", (), {"project": str(self.project)})()
                ),
                0,
            )
        revision, state = store.load(self.project)
        predecessor = next(
            item for item in state["evidence"]["learning"]
            if item["id"] == args.evidence_id
        )
        args.freshness_days = 0
        review_payload = controller.correct_evidence_review_payload(
            args,
            predecessor=predecessor,
            replacement_id=args.id,
            replacement_digest=controller.sha256_file(artifact),
            bucket="learning",
            source_artifact_path=artifact.name,
        )
        payload_hash = controller.command_payload_hash("correct-evidence", review_payload)
        args.declarant_grant = self.fixture.grant(
            args.declarant, "correct-evidence-declare",
            resource=f"evidence:{args.evidence_id}", work_id="", cycle_id="",
            dimension="evidence", decision="proposed", payload_hash=payload_hash,
        )
        args.adjudicator_grant = self.fixture.grant(
            args.adjudicator, "correct-evidence-adjudicate",
            resource=f"evidence:{args.evidence_id}", work_id="", cycle_id="",
            dimension="evidence", decision="accepted", payload_hash=payload_hash,
        )
        directory = self.project / ".company-os"
        control_before = (directory / "control.json").read_bytes()
        events_before = (directory / "events.jsonl").read_bytes()
        nonces_before = deepcopy(state["controller"]["consumed_grant_nonces"])
        digest = controller.sha256_file(artifact)
        orphan = controller.evidence_snapshot_path(self.project, digest)
        self.assertFalse(orphan.exists())

        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.correct_evidence(args), 2)

        retained_revision, retained = store.load(self.project)
        self.assertEqual(retained_revision, revision)
        self.assertEqual(retained, state)
        self.assertEqual(retained["controller"]["consumed_grant_nonces"], nonces_before)
        self.assertEqual((directory / "control.json").read_bytes(), control_before)
        self.assertEqual((directory / "events.jsonl").read_bytes(), events_before)
        self.assertTrue(orphan.is_file())
        self.assertEqual(controller.sha256_file(orphan), digest)
        self.assertTrue(store.audit(self.project)["ok"])

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

    def test_sqlite_store_cancellation_matrix_rejects_illegal_pairs_without_revision_event_or_authority_mutation(self) -> None:
        pairs = (
            ("acknowledged", "acknowledged", True),
            ("acknowledged", "not_acknowledged", False),
            ("refused", "acknowledged", False),
            ("refused", "not_acknowledged", True),
            ("failed", "acknowledged", False),
            ("failed", "not_acknowledged", True),
        )
        for index, (hard_status, acknowledgement_status, legal) in enumerate(pairs):
            with self.subTest(hard_status=hard_status, acknowledgement_status=acknowledgement_status):
                fixture = controller_test.ControllerTests(methodName="runTest")
                fixture.setUp()
                try:
                    attempt_id = fixture.prepare_native_cancellation(attempt_id=f"store-pair-{index}")
                    before = controller.load_json(fixture.project / ".company-os" / "control.json")
                    before_revision = store.audit(fixture.project)["revision"]
                    before_events = store.connect(fixture.project)
                    try:
                        before_event_count = before_events.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                    finally:
                        before_events.close()
                    observation = {
                        "source": "host_observation",
                        "tool": "store-hard-cancel-return",
                        "task_id": f"{attempt_id}-task",
                        "thread_id": f"{attempt_id}-thread",
                        "host_id": f"{attempt_id}-host",
                        "hard_status": hard_status,
                        "acknowledgement_status": acknowledgement_status,
                    }
                    result = controller.record_native_task_observation(
                        fixture.native_observation_args(attempt_id, "hard_cancellation_observed", observation)
                    )
                    after = controller.load_json(fixture.project / ".company-os" / "control.json")
                    if not legal:
                        self.assertEqual(result, 2)
                        self.assertEqual(before, after)
                        self.assertEqual(store.audit(fixture.project)["revision"], before_revision)
                        connection = store.connect(fixture.project)
                        try:
                            self.assertEqual(
                                connection.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                                before_event_count,
                            )
                        finally:
                            connection.close()
                    else:
                        self.assertEqual(result, 0)
                        self.assertEqual(store.audit(fixture.project)["revision"], before_revision + 1)
                        native = after["runtime_adapter"]["attempts"][0]["native_task_runtime"]
                        self.assertEqual(
                            (native["cancellation"]["hard_cancellation_status"], native["cancellation"]["acknowledgement_status"]),
                            (hard_status, acknowledgement_status),
                        )
                        self.assertEqual(
                            native["status"],
                            "cancel_acknowledged" if (hard_status, acknowledgement_status) == ("acknowledged", "acknowledged") else "cancel_requested",
                        )
                finally:
                    fixture.tearDown()

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

    def test_outbox_inspection_is_project_bound_and_reconciliation_is_compare_and_set(self) -> None:
        state = self.migrate_valid_state()
        payload = {"attempt_id": "inspect-1", "action": "dispatch"}
        tx = store.begin(self.project)
        tx.stage(deepcopy(state), {
            "at": controller.utc_now(), "type": "dispatch_intent",
            "project_id": state["instance"]["project_id"], "program_version": 1,
        })
        tx.enqueue_outbox(channel="native-dispatch", key="inspect-1", payload=payload)
        tx.close(True)
        rows = store.inspect_outbox(self.project, channel="native-dispatch", statuses=["pending"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["payload"], payload)
        digest = rows[0]["payload_sha256"]

        tx = store.begin(self.project)
        tx.stage(deepcopy(tx.state), {
            "at": controller.utc_now(), "type": "dispatch_reconciled",
            "project_id": state["instance"]["project_id"], "program_version": 1,
        })
        result = tx.reconcile_outbox(
            channel="native-dispatch", key="inspect-1", status="leased",
            expected_status="pending", payload_sha256=digest,
        )
        self.assertFalse(result["idempotent"])
        tx.close(True)
        self.assertEqual(store.inspect_outbox(self.project)[0]["status"], "leased")

        tx = store.begin(self.project)
        tx.stage(deepcopy(tx.state), {
            "at": controller.utc_now(), "type": "dispatch_succeeded",
            "project_id": state["instance"]["project_id"], "program_version": 1,
        })
        tx.reconcile_outbox(channel="native-dispatch", key="inspect-1", status="succeeded", expected_status="leased")
        tx.close(True)

        connection = store.connect(self.project)
        try:
            connection.execute(
                "UPDATE outbox_messages SET payload_json=? WHERE channel=? AND message_key=?",
                ('{"tampered":true}', "native-dispatch", "inspect-1"),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(store.StoreError):
            store.inspect_outbox(self.project)
        connection = store.connect(self.project)
        try:
            encoded = store.canonical_json(payload)
            connection.execute(
                "UPDATE outbox_messages SET payload_json=?,payload_sha256=? WHERE channel=? AND message_key=?",
                (encoded, store.sha256_bytes(encoded.encode()), "native-dispatch", "inspect-1"),
            )
            connection.commit()
        finally:
            connection.close()

        # A restart preserves the exact row; a compare-and-set mismatch cannot
        # create a revision or mutate the outbox.
        before = store.load(self.project)[0]
        tx = store.begin(self.project)
        tx.stage(deepcopy(tx.state), {
            "at": controller.utc_now(), "type": "bad_reconciliation",
            "project_id": state["instance"]["project_id"], "program_version": 1,
        })
        with self.assertRaises(store.StoreError):
            tx.reconcile_outbox(channel="native-dispatch", key="inspect-1", status="failed", expected_status="pending")
        tx.close(False)
        self.assertEqual(store.load(self.project)[0], before)

        other = Path(tempfile.mkdtemp()).resolve()
        try:
            with self.assertRaises(store.StoreError):
                store.inspect_outbox(other)
        finally:
            shutil.rmtree(other)


if __name__ == "__main__":
    unittest.main()
