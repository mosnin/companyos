from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills/company-os/force-first-execution/scripts/force_loop_controller.py"
SPEC = importlib.util.spec_from_file_location("force_loop_controller", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def contract(**overrides: object) -> dict:
    value = {
        "schema": "company-os.force-contract.v1",
        "task_id": "worker-1",
        "outcome": "Produce a working customer-facing deliverable.",
        "started_at_epoch": 1000,
        "soft_slos": {
            "first_artifact_seconds": 300,
            "runnable_candidate_seconds": 900,
            "verification_seconds": 1200,
            "acceptance_to_receipt_seconds": 120,
            "receipt_to_decision_seconds": 120,
        },
        "control": {
            "inflight_observation_fresh_seconds": 120,
            "max_rework_cycles": 1,
            "event_log_owner": "manager",
        },
        "hard_stop_codes": sorted(MODULE.BASELINE_HARD_STOPS),
    }
    value.update(overrides)
    return value


def event(sequence: int, event_type: str, at_epoch: int, evidence: dict | None = None) -> dict:
    return {
        "schema": "company-os.force-event.v1",
        "sequence": sequence,
        "task_id": "worker-1",
        "event": event_type,
        "at_epoch": at_epoch,
        "evidence": evidence or {},
    }


ARTIFACT_BYTES = b"force-first-evidence"
SHA = hashlib.sha256(ARTIFACT_BYTES).hexdigest()


def materialize_bound_files(root: Path, events: list[dict], *, overrides: dict[str, bytes] | None = None) -> None:
    replacements = overrides or {}
    for item in events:
        if item["event"] not in {"artifact_materialized", "receipt_materialized"}:
            continue
        relative = item["evidence"]["path"]
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(replacements.get(relative, ARTIFACT_BYTES))


class ForceFirstExecutionTests(unittest.TestCase):
    def evaluate(self, events: list[dict], now: int) -> dict:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            materialize_bound_files(root, events)
            accepted_contract = MODULE.validate_contract(contract())
            accepted_events = MODULE.validate_events(accepted_contract, events, root)
            return MODULE.evaluate(accepted_contract, accepted_events, now)

    def validate(
        self,
        events: list[dict],
        *,
        contract_value: dict | None = None,
        overrides: dict[str, bytes] | None = None,
    ) -> list[dict]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            materialize_bound_files(root, events, overrides=overrides)
            return MODULE.validate_events(
                MODULE.validate_contract(contract_value or contract()), events, root
            )

    def test_missing_first_artifact_triggers_one_precise_intervention(self) -> None:
        result = self.evaluate([event(1, "task_started", 1000)], 1301)
        self.assertEqual("materialization_late", result["state"])
        self.assertEqual("send_precise_intervention", result["next_action"])
        self.assertIn("first_artifact", result["metrics"]["soft_slo_misses"])
        self.assertIsNone(result["metrics"]["first_pass_acceptance"])

    def test_fresh_observable_work_allows_bounded_grace(self) -> None:
        result = self.evaluate(
            [
                event(1, "task_started", 1000),
                event(2, "inflight_observed", 1290, {"operation": "image generation request in flight"}),
            ],
            1301,
        )
        self.assertEqual("continue_bounded_grace", result["next_action"])

    def test_interventions_are_counted_from_observed_events(self) -> None:
        result = self.evaluate(
            [
                event(1, "task_started", 1000),
                event(2, "intervention_sent", 1301, {"missing": "first materialized artifact"}),
            ],
            1301,
        )
        self.assertEqual(1, result["metrics"]["manager_intervention_count"])

    def test_late_useful_output_is_quarantined_for_quality_review_not_discarded(self) -> None:
        events = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1310, {"path": "design/late.webp", "sha256": SHA}),
        ]
        result = self.evaluate(events, 1310)
        self.assertEqual("late_output_quarantined", result["state"])
        self.assertEqual("quarantine_and_inspect_late_output", result["next_action"])
        self.assertIn("first_artifact", result["metrics"]["soft_slo_misses"])

        events.append(
            event(
                3,
                "late_output_reviewed",
                1320,
                {"artifact_paths": ["design/late.webp"], "decision": "accept"},
            )
        )
        result = self.evaluate(events, 1320)
        self.assertEqual("produce_runnable_candidate", result["next_action"])

    def test_acceptance_inputs_force_immediate_receipt_materialization(self) -> None:
        result = self.evaluate(
            [
                event(1, "task_started", 1000),
                event(2, "artifact_materialized", 1100, {"path": "site/index.html", "sha256": SHA}),
                event(3, "candidate_runnable", 1200, {"artifact_paths": ["site/index.html"]}),
                event(4, "verification_passed", 1250, {"check": "browser and accessibility checks pass"}),
                event(5, "manager_inspection_passed", 1260, {"artifact_paths": ["site/index.html"]}),
            ],
            1261,
        )
        self.assertEqual("acceptance_ready", result["state"])
        self.assertEqual("materialize_receipt_now", result["next_action"])

    def test_verified_receipt_forces_immediate_manager_decision(self) -> None:
        events = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1100, {"path": "site/index.html", "sha256": SHA}),
            event(3, "candidate_runnable", 1200, {"artifact_paths": ["site/index.html"]}),
            event(4, "verification_passed", 1250, {"check": "tests pass"}),
            event(5, "manager_inspection_passed", 1260, {"artifact_paths": ["site/index.html"]}),
            event(6, "receipt_materialized", 1265, {"path": "evidence/receipt.json", "sha256": SHA}),
        ]
        result = self.evaluate(events, 1266)
        self.assertEqual("manager_decide_now", result["next_action"])

    def test_morrow_like_late_first_pass_and_rework_preserve_truth(self) -> None:
        events = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1516, {"path": "site/src/app.jsx", "sha256": SHA}),
            event(3, "late_output_reviewed", 1520, {"artifact_paths": ["site/src/app.jsx"], "decision": "accept"}),
            event(4, "candidate_runnable", 1790, {"artifact_paths": ["site/src/app.jsx"]}),
            event(5, "verification_passed", 2018, {"check": "build and tests pass"}),
            event(6, "manager_inspection_failed", 2050, {"defects": ["contrast", "section order"]}),
            event(7, "rework_started", 2060, {"defects": ["contrast", "section order"]}),
            event(8, "artifact_materialized", 2217, {"path": "site/src/styles.css", "sha256": SHA}),
            event(9, "candidate_runnable", 2230, {"artifact_paths": ["site/src/styles.css"]}),
            event(10, "verification_passed", 2590, {"check": "zero axe violations and tests pass"}),
            event(11, "manager_inspection_passed", 2600, {"artifact_paths": ["site/src/styles.css"]}),
            event(12, "receipt_materialized", 2720, {"path": "site/evidence/v2/receipt.json", "sha256": SHA}),
            event(13, "manager_accept", 2730),
        ]
        result = self.evaluate(events, 2730)
        self.assertEqual("completed", result["state"])
        self.assertFalse(result["metrics"]["first_pass_acceptance"])
        self.assertEqual(1, result["metrics"]["rework_count"])
        self.assertIn("first_artifact", result["metrics"]["soft_slo_misses"])
        self.assertNotIn("acceptance_to_receipt", result["metrics"]["soft_slo_misses"])

    def test_hard_stop_always_wins(self) -> None:
        result = self.evaluate(
            [
                event(1, "task_started", 1000),
                event(2, "hard_stop", 1010, {"code": "scope_violation", "detail": "worker wrote outside scope"}),
            ],
            1010,
        )
        self.assertEqual("stop_and_report", result["next_action"])
        self.assertEqual(1, result["metrics"]["hard_stop_count"])

    def test_acceptance_without_fresh_post_rework_verification_is_rejected(self) -> None:
        events = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1100, {"path": "site/index.html", "sha256": SHA}),
            event(3, "candidate_runnable", 1200, {"artifact_paths": ["site/index.html"]}),
            event(4, "verification_passed", 1210, {"check": "tests pass"}),
            event(5, "manager_inspection_failed", 1220, {"defects": ["broken focus"]}),
            event(6, "rework_started", 1230, {"defects": ["broken focus"]}),
            event(7, "manager_inspection_passed", 1240, {"artifact_paths": ["site/index.html"]}),
        ]
        with self.assertRaisesRegex(MODULE.ForceContractError, "fresh verification"):
            self.validate(events)

    def test_later_inspection_failure_cannot_be_masked_by_an_earlier_pass(self) -> None:
        valid_prefix = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1100, {"path": "site/index.html", "sha256": SHA}),
            event(3, "candidate_runnable", 1200, {"artifact_paths": ["site/index.html"]}),
            event(4, "verification_passed", 1210, {"check": "tests pass"}),
            event(5, "manager_inspection_passed", 1220, {"artifact_paths": ["site/index.html"]}),
            event(6, "manager_inspection_failed", 1230, {"defects": ["visual defect"]}),
        ]
        result = self.evaluate(valid_prefix, 1230)
        self.assertEqual("exact_rework", result["next_action"])

        events = valid_prefix + [
            event(7, "receipt_materialized", 1240, {"path": "evidence/receipt.json", "sha256": SHA}),
        ]
        with self.assertRaisesRegex(MODULE.ForceContractError, "fresh manager inspection"):
            self.validate(events)

    def test_acceptance_requires_materialization_and_runnable_candidate(self) -> None:
        events = [
            event(1, "task_started", 1000),
            event(2, "verification_passed", 1010, {"check": "claimed pass"}),
            event(3, "manager_inspection_passed", 1020, {"artifact_paths": ["ghost/not-materialized.bin"]}),
            event(4, "receipt_materialized", 1030, {"path": "ghost/receipt.json", "sha256": SHA}),
            event(5, "manager_accept", 1040),
        ]
        with self.assertRaisesRegex(MODULE.ForceContractError, "fresh runnable candidate"):
            self.validate(events)

    def test_rework_requires_fresh_materialization_and_candidate(self) -> None:
        events = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1100, {"path": "site/v1.html", "sha256": SHA}),
            event(3, "candidate_runnable", 1110, {"artifact_paths": ["site/v1.html"]}),
            event(4, "verification_passed", 1120, {"check": "tests pass"}),
            event(5, "manager_inspection_failed", 1130, {"defects": ["visual defect"]}),
            event(6, "rework_started", 1140, {"defects": ["visual defect"]}),
            event(7, "verification_passed", 1150, {"check": "claimed rework pass"}),
        ]
        with self.assertRaisesRegex(MODULE.ForceContractError, "fresh runnable candidate"):
            self.validate(events)

    def test_late_review_must_bind_exact_unresolved_artifact_once(self) -> None:
        wrong_path = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1310, {"path": "design/late.webp", "sha256": SHA}),
            event(3, "late_output_reviewed", 1320, {"artifact_paths": ["design/different.webp"], "decision": "accept"}),
        ]
        with self.assertRaisesRegex(MODULE.ForceContractError, "exact unresolved"):
            self.validate(wrong_path)

        duplicate = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1310, {"path": "design/late.webp", "sha256": SHA}),
            event(3, "late_output_reviewed", 1320, {"artifact_paths": ["design/late.webp"], "decision": "reject"}),
            event(4, "late_output_reviewed", 1330, {"artifact_paths": ["design/late.webp"], "decision": "accept"}),
        ]
        with self.assertRaisesRegex(MODULE.ForceContractError, "unresolved late artifact"):
            self.validate(duplicate)

    def test_later_artifact_is_not_misclassified_when_cycle_first_was_on_time(self) -> None:
        events = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1100, {"path": "design/first.webp", "sha256": SHA}),
            event(3, "artifact_materialized", 1400, {"path": "design/second.webp", "sha256": SHA}),
            event(4, "candidate_runnable", 1410, {"artifact_paths": ["design/first.webp", "design/second.webp"]}),
        ]
        result = self.evaluate(events, 1410)
        self.assertEqual("verify_candidate", result["next_action"])
        self.assertNotIn("first_artifact", result["metrics"]["soft_slo_misses"])

    def test_replacement_candidate_cannot_inherit_stale_verification_or_inspection(self) -> None:
        events = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1050, {"path": "site/a.html", "sha256": SHA}),
            event(3, "candidate_runnable", 1060, {"artifact_paths": ["site/a.html"]}),
            event(4, "verification_passed", 1070, {"check": "candidate A tests pass"}),
            event(5, "manager_inspection_passed", 1080, {"artifact_paths": ["site/a.html"]}),
            event(6, "artifact_materialized", 1090, {"path": "site/b.html", "sha256": SHA}),
            event(7, "candidate_runnable", 1100, {"artifact_paths": ["site/b.html"]}),
            event(8, "receipt_materialized", 1110, {"path": "evidence/receipt.json", "sha256": SHA}),
            event(9, "manager_accept", 1120),
        ]
        with self.assertRaisesRegex(
            MODULE.ForceContractError,
            "inspection of the current verified candidate",
        ):
            self.validate(events)

        result = self.evaluate(events[:7], 1100)
        self.assertEqual("verify_candidate", result["next_action"])

    def test_receipt_seals_upstream_work_until_manager_decision(self) -> None:
        events = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1050, {"path": "site/a.html", "sha256": SHA}),
            event(3, "candidate_runnable", 1060, {"artifact_paths": ["site/a.html"]}),
            event(4, "verification_passed", 1070, {"check": "tests pass"}),
            event(5, "manager_inspection_passed", 1080, {"artifact_paths": ["site/a.html"]}),
            event(6, "receipt_materialized", 1090, {"path": "evidence/receipt.json", "sha256": SHA}),
            event(7, "artifact_materialized", 1100, {"path": "site/b.html", "sha256": SHA}),
        ]
        with self.assertRaisesRegex(MODULE.ForceContractError, "receipt is sealed"):
            self.validate(events)

    def test_manager_may_request_rework_after_receipt_then_start_fresh_cycle(self) -> None:
        events = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1050, {"path": "site/a.html", "sha256": SHA}),
            event(3, "candidate_runnable", 1060, {"artifact_paths": ["site/a.html"]}),
            event(4, "verification_passed", 1070, {"check": "tests pass"}),
            event(5, "manager_inspection_passed", 1080, {"artifact_paths": ["site/a.html"]}),
            event(6, "receipt_materialized", 1090, {"path": "evidence/receipt.json", "sha256": SHA}),
            event(7, "manager_rework", 1100, {"defects": ["final packaging mismatch"]}),
            event(8, "rework_started", 1110, {"defects": ["final packaging mismatch"]}),
            event(9, "artifact_materialized", 1120, {"path": "site/b.html", "sha256": SHA}),
        ]
        result = self.evaluate(events, 1120)
        self.assertEqual("produce_runnable_candidate", result["next_action"])
        self.assertEqual(1, result["metrics"]["rework_count"])

    def test_prior_receipt_decision_slo_miss_survives_successful_rework(self) -> None:
        events = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1010, {"path": "site/a.html", "sha256": SHA}),
            event(3, "candidate_runnable", 1020, {"artifact_paths": ["site/a.html"]}),
            event(4, "verification_passed", 1030, {"check": "candidate A tests pass"}),
            event(5, "manager_inspection_passed", 1040, {"artifact_paths": ["site/a.html"]}),
            event(6, "receipt_materialized", 1050, {"path": "evidence/a.json", "sha256": SHA}),
            event(7, "manager_rework", 1200, {"defects": ["packaging mismatch"]}),
            event(8, "rework_started", 1210, {"defects": ["packaging mismatch"]}),
            event(9, "artifact_materialized", 1220, {"path": "site/b.html", "sha256": SHA}),
            event(10, "candidate_runnable", 1230, {"artifact_paths": ["site/b.html"]}),
            event(11, "verification_passed", 1240, {"check": "candidate B tests pass"}),
            event(12, "manager_inspection_passed", 1250, {"artifact_paths": ["site/b.html"]}),
            event(13, "receipt_materialized", 1260, {"path": "evidence/b.json", "sha256": SHA}),
            event(14, "manager_accept", 1270),
        ]
        result = self.evaluate(events, 1270)
        self.assertEqual("completed", result["state"])
        self.assertIn("receipt_to_decision", result["metrics"]["soft_slo_misses"])
        self.assertEqual(10, result["metrics"]["receipt_to_decision_seconds"])

    def test_late_output_rework_respects_zero_rework_budget(self) -> None:
        events = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1310, {"path": "design/late.webp", "sha256": SHA}),
            event(3, "late_output_reviewed", 1320, {"artifact_paths": ["design/late.webp"], "decision": "rework"}),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            materialize_bound_files(root, events)
            zero_rework = contract()
            zero_rework["control"]["max_rework_cycles"] = 0
            accepted_contract = MODULE.validate_contract(zero_rework)
            accepted_events = MODULE.validate_events(accepted_contract, events, root)
            result = MODULE.evaluate(accepted_contract, accepted_events, 1320)
        self.assertEqual("escalate_rework_exhausted", result["next_action"])

    def test_artifact_digest_and_symlink_are_verified_against_root(self) -> None:
        events = [
            event(1, "task_started", 1000),
            event(2, "artifact_materialized", 1100, {"path": "site/index.html", "sha256": SHA}),
        ]
        with self.assertRaisesRegex(MODULE.ForceContractError, "digest does not match"):
            self.validate(events, overrides={"site/index.html": b"different"})

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "site").mkdir()
            target = root / "target.html"
            target.write_bytes(ARTIFACT_BYTES)
            (root / "site/index.html").symlink_to(target)
            with self.assertRaisesRegex(MODULE.ForceContractError, "symlink"):
                MODULE.validate_events(MODULE.validate_contract(contract()), events, root)

    def test_contract_cannot_remove_baseline_hard_stops(self) -> None:
        broken = contract(hard_stop_codes=["scope_violation"])
        with self.assertRaisesRegex(MODULE.ForceContractError, "omit baseline"):
            MODULE.validate_contract(broken)

    def test_cli_outputs_canonical_json_and_does_not_mutate_inputs(self) -> None:
        events = [event(1, "task_started", 1000)]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path = root / "contract.json"
            events_path = root / "events.jsonl"
            contract_path.write_text(json.dumps(contract()), encoding="utf-8")
            events_path.write_text("\n".join(json.dumps(item) for item in events), encoding="utf-8")
            before = {path.name: path.read_bytes() for path in (contract_path, events_path)}
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(
                    0,
                    MODULE.main(
                        [
                            "evaluate",
                            "--contract",
                            str(contract_path),
                            "--events",
                            str(events_path),
                            "--artifact-root",
                            str(root),
                            "--now-epoch",
                            "1100",
                        ]
                    ),
                )
            self.assertEqual(MODULE.canonical_bytes(json.loads(output.getvalue())) + b"\n", output.getvalue().encode())
            after = {path.name: path.read_bytes() for path in (contract_path, events_path)}
            self.assertEqual(before, after)

    def test_role_skills_route_managers_and_workers_through_force_control(self) -> None:
        manager = (ROOT / "skills/company-os/manage-company-program/SKILL.md").read_text()
        worker = (ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md").read_text()
        index = (ROOT / "skills/company-os/company-os/SKILL.md").read_text()
        for content in (manager, worker, index):
            self.assertIn("$force-first-execution", content)


if __name__ == "__main__":
    unittest.main()
