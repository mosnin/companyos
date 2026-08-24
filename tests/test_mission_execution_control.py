from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/mission-execution-control/scripts/mission_control.py"
spec = importlib.util.spec_from_file_location("mission_execution_control_under_test", SCRIPT)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


def artifact_contract():
    return {
        "$schema": "company-os.artifact-observation-contract.v1",
        "ready": True,
        "artifact_classes": [
            {
                "artifact_class_id": "support_runtime",
                "label": "Support runtime",
                "required": True,
                "modalities": ["service", "executable"],
                "observation_methods": ["runtime"],
            },
            {
                "artifact_class_id": "browser_interface",
                "label": "Browser interface",
                "required": True,
                "modalities": ["interactive", "ui"],
                "observation_methods": ["browser"],
            },
            {
                "artifact_class_id": "billing_system",
                "label": "Billing system",
                "required": True,
                "modalities": ["service"],
                "observation_methods": ["api"],
            },
            {
                "artifact_class_id": "research_report",
                "label": "Research report",
                "required": True,
                "modalities": ["document"],
                "observation_methods": ["inspection"],
            },
        ],
    }


def start_time():
    return datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)


def state():
    return MODULE.initialize_state(
        "support-mission",
        "Build a complete production quality support application with a widget, inbox, backend, security, and billing.",
        started_at=MODULE.format_time(start_time()),
        mission_class="company_mission",
        duration_minutes=420,
        artifact_contract=artifact_contract(),
    )


def evidence(capability_id, suffix):
    return {
        "kind": suffix,
        "path": f"artifacts/{capability_id}-{suffix}.json",
        "sha256": "a" * 64,
        "capability_id": capability_id,
    }


class MissionExecutionControlTests(unittest.TestCase):
    def test_mission_classifier_distinguishes_quick_and_company_work(self):
        self.assertEqual(MODULE.classify_mission("Build a landing page"), "quick_build")
        self.assertEqual(
            MODULE.classify_mission(
                "Build a full application with backend, billing, security, multiple companies, and production quality autonomous operation"
            ),
            "company_mission",
        )

    def test_first_reality_is_strict_subset_of_final_scope(self):
        current = state()
        contract = MODULE.verify_first_reality(current["first_reality"])
        self.assertLessEqual(len(contract["required_artifact_class_ids"]), 2)
        self.assertIn("browser_interface", contract["required_artifact_class_ids"])
        self.assertTrue(contract["deferred_capability_ids"])
        self.assertEqual(
            set(contract["required_artifact_class_ids"]) | set(contract["deferred_capability_ids"]),
            {"support_runtime", "browser_interface", "billing_system", "research_report"},
        )

    def test_capability_state_requires_ordered_evidence(self):
        current = state()
        capability = current["first_reality"]["required_capability_ids"][0]
        with self.assertRaises(MODULE.MissionControlError):
            MODULE.record_event(
                current,
                MODULE.make_event(
                    "connected-too-early",
                    "journey_connected",
                    occurred_at=MODULE.format_time(start_time() + timedelta(minutes=5)),
                    work_class="integration",
                    capability_id=capability,
                    evidence=evidence(capability, "connected"),
                ),
            )
        current = MODULE.record_event(
            current,
            MODULE.make_event(
                "artifact",
                "artifact_materialized",
                occurred_at=MODULE.format_time(start_time() + timedelta(minutes=5)),
                work_class="implementation",
                capability_id=capability,
                evidence=evidence(capability, "artifact"),
            ),
        )
        current = MODULE.record_event(
            current,
            MODULE.make_event(
                "runtime",
                "runtime_observed",
                occurred_at=MODULE.format_time(start_time() + timedelta(minutes=10)),
                work_class="runtime",
                capability_id=capability,
                evidence=evidence(capability, "runtime"),
                observation_kind="browser",
            ),
        )
        current = MODULE.record_event(
            current,
            MODULE.make_event(
                "connected",
                "journey_connected",
                occurred_at=MODULE.format_time(start_time() + timedelta(minutes=15)),
                work_class="integration",
                capability_id=capability,
                evidence=evidence(capability, "connected"),
            ),
        )
        observed = {item["capability_id"]: item["state"] for item in current["capabilities"]}
        self.assertEqual(observed[capability], "connected")

    def test_governor_pauses_documentation_after_first_reality_incident(self):
        current = state()
        current = MODULE.refresh_governor(
            current,
            now=start_time() + timedelta(minutes=120),
        )
        self.assertEqual(current["governor_decision"]["mode"], "compression")
        self.assertTrue(current["governor_decision"]["first_reality_incident"])
        receipt = MODULE.admit_work(
            current,
            {
                "$schema": MODULE.ADMISSION_SCHEMA,
                "request_id": "docs",
                "task_id": "docs-worker",
                "manager_id": "manager",
                "work_class": "documentation",
                "bootstrap": False,
                "justification": {
                    "consumer_task_id": "product-worker",
                    "blocker_id": "browser",
                    "decision_dependency": "choose component layout",
                    "deadline_minutes": 10,
                },
            },
            now=start_time() + timedelta(minutes=120),
        )
        self.assertFalse(receipt["admitted"])
        self.assertTrue(any("paused" in item for item in receipt["blockers"]))

    def test_research_requires_live_consumer_after_bootstrap(self):
        current = state()
        receipt = MODULE.admit_work(
            current,
            {
                "$schema": MODULE.ADMISSION_SCHEMA,
                "request_id": "research",
                "task_id": "research-worker",
                "manager_id": "manager",
                "work_class": "research",
                "bootstrap": False,
            },
            now=start_time() + timedelta(minutes=5),
        )
        self.assertFalse(receipt["admitted"])
        self.assertTrue(any("consumer" in item for item in receipt["blockers"]))

    def test_supplied_implementation_cannot_be_replaced_without_spike(self):
        current = MODULE.initialize_state(
            "firecrawl",
            "Build a Firecrawl expert with https://github.com/firecrawl/firecrawl.git",
            started_at=MODULE.format_time(start_time()),
            mission_class="bounded_feature",
            duration_minutes=180,
        )
        receipt = MODULE.admit_work(
            current,
            {
                "$schema": MODULE.ADMISSION_SCHEMA,
                "request_id": "replacement",
                "task_id": "crawler-worker",
                "manager_id": "manager",
                "work_class": "implementation",
                "bootstrap": False,
                "replaces_existing_implementation": True,
            },
            now=start_time() + timedelta(minutes=5),
        )
        self.assertFalse(receipt["admitted"])
        self.assertTrue(any("integration spike" in item for item in receipt["blockers"]))

    def test_deadline_misses_escalate_to_replacement(self):
        current = state()
        current["workers"] = {"worker-1": {"status": "active", "manager_id": "manager-1"}}
        current["managers"] = {"manager-1": {"status": "active"}}
        current = MODULE.seal(current)
        miss_time = start_time() + timedelta(minutes=121)
        current = MODULE.reconcile_deadlines(current, now=miss_time)
        self.assertTrue(current["interventions"])
        current = MODULE.reconcile_deadlines(current, now=miss_time + timedelta(seconds=1))
        self.assertTrue(any(item["kind"] == "replace_worker" for item in current["replacement_orders"]))
        current = MODULE.reconcile_deadlines(current, now=miss_time + timedelta(seconds=2))
        self.assertTrue(any(item["kind"] == "replace_manager" for item in current["replacement_orders"]))

    def test_scheduler_wake_is_generation_state_and_expiry_bound(self):
        current = state()
        wake = MODULE.make_wake(
            current,
            wake_id="wake-1",
            not_before=MODULE.format_time(start_time() + timedelta(minutes=5)),
            reason="continue critical path",
            expected_state_sha256=current["state_sha256"],
        )
        early = MODULE.admit_wake(current, wake, now=start_time() + timedelta(minutes=4))
        self.assertFalse(early["admitted"])
        admitted = MODULE.admit_wake(current, wake, now=start_time() + timedelta(minutes=5))
        self.assertTrue(admitted["admitted"])
        consumed = MODULE.record_event(
            current,
            MODULE.make_event(
                "wake-consumed",
                "wake_consumed",
                occurred_at=MODULE.format_time(start_time() + timedelta(minutes=5)),
                wake_key=wake["idempotency_key"],
            ),
        )
        self.assertEqual(consumed["scheduler"]["wake_count"], 1)
        self.assertEqual(consumed["consumed_wake_keys"], [wake["idempotency_key"]])
        replay = MODULE.admit_wake(consumed, wake, now=start_time() + timedelta(minutes=6))
        self.assertFalse(replay["admitted"])
        with self.assertRaisesRegex(MODULE.MissionControlError, "already consumed"):
            MODULE.record_event(
                consumed,
                MODULE.make_event(
                    "wake-consumed-again",
                    "wake_consumed",
                    occurred_at=MODULE.format_time(start_time() + timedelta(minutes=6)),
                    wake_key=wake["idempotency_key"],
                ),
            )

    def test_scheduler_lease_drift_and_revocation_fail_closed(self):
        current = state()
        drifted = dict(current)
        drifted["scheduler"] = {**current["scheduler"], "generation": current["generation"] + 1}
        with self.assertRaisesRegex(MODULE.MissionControlError, "generation drifted"):
            MODULE.verify_state(MODULE.seal(drifted))
        count_drift = dict(current)
        count_drift["scheduler"] = {**current["scheduler"], "wake_count": 3}
        with self.assertRaisesRegex(MODULE.MissionControlError, "wake_count drifted"):
            MODULE.verify_state(MODULE.seal(count_drift))
        expired = MODULE.refresh_governor(
            current,
            now=start_time() + timedelta(minutes=current["duration_minutes"]),
        )
        self.assertEqual(expired["status"], "expired")
        self.assertEqual(expired["scheduler"]["status"], "revoked")
        self.assertEqual(expired["scheduler"]["generation"], expired["generation"])
        with self.assertRaisesRegex(MODULE.MissionControlError, "inactive scheduler"):
            MODULE.make_wake(
                expired,
                wake_id="late-wake",
                not_before=MODULE.format_time(start_time() + timedelta(minutes=5)),
                reason="continue after expiry",
                expected_state_sha256=expired["state_sha256"],
            )

    def test_checkpoint_is_required_for_user_usable_reality(self):
        current = state()
        for capability in list(current["capabilities"]):
            capability_id = capability["capability_id"]
            for index, kind in enumerate(("artifact_materialized", "runtime_observed", "journey_connected"), 1):
                current = MODULE.record_event(
                    current,
                    MODULE.make_event(
                        f"{capability_id}-{kind}",
                        kind,
                        occurred_at=MODULE.format_time(start_time() + timedelta(minutes=index)),
                        work_class="implementation" if index == 1 else "runtime",
                        capability_id=capability_id,
                        evidence=evidence(capability_id, kind),
                        observation_kind="browser" if kind == "runtime_observed" else None,
                    ),
                )
        self.assertFalse(MODULE.reality_signals(current)["user_usable"])
        checkpoint = MODULE.create_checkpoint(
            current,
            candidate_id="candidate-1",
            capability_ids=[item["capability_id"] for item in current["capabilities"]],
            artifacts=[{"path": "src/app.py", "sha256": "b" * 64}],
            verification_receipts=[{"path": "artifacts/runtime.json", "sha256": "c" * 64}],
            git_commit="d" * 40,
            created_at=MODULE.format_time(start_time() + timedelta(minutes=10)),
        )
        current = MODULE.record_event(
            current,
            MODULE.make_event(
                "checkpoint",
                "checkpoint_recorded",
                occurred_at=MODULE.format_time(start_time() + timedelta(minutes=10)),
                work_class="checkpoint",
                checkpoint=checkpoint,
            ),
        )
        self.assertTrue(MODULE.reality_signals(current)["user_usable"])


if __name__ == "__main__":
    unittest.main()
