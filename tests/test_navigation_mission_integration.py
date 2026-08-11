from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/mission-execution-control/scripts/mission_control.py"
spec = importlib.util.spec_from_file_location("company_os_navigation_mission_integration", SCRIPT)
assert spec and spec.loader
MISSION = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MISSION)


class NavigationMissionIntegrationTests(unittest.TestCase):
    def state(self):
        return MISSION.initialize_state(
            "micro",
            "Build a real browser app.",
            started_at="2026-08-11T12:00:00Z",
            mission_class="quick_build",
            duration_minutes=90,
        )

    def test_initial_mission_has_navigation_route_action(self):
        state = self.state()
        self.assertIsNotNone(state["navigation"])
        self.assertEqual(state["navigation"]["waypoint"], "R3_FIRST_REALITY")
        self.assertEqual(state["navigation"]["next_action"]["work_class"], "implementation")
        self.assertEqual(state["governor_decision"]["next_action"], state["navigation"]["next_action"])
        self.assertEqual(state["governor_decision"]["navigation_decision_sha256"], state["navigation"]["decision_sha256"])

    def test_unrelated_sensor_work_is_rejected(self):
        state = self.state()
        receipt = MISSION.admit_work(
            state,
            {
                "$schema": MISSION.ADMISSION_SCHEMA,
                "request_id": "research-background",
                "task_id": "research-background",
                "manager_id": "manager",
                "work_class": "research",
                "bootstrap": False,
                "justification": {
                    "consumer_task_id": "worker",
                    "blocker_id": "market-history",
                    "decision_dependency": "Learn unrelated background.",
                    "deadline_minutes": 10,
                    "expected_action_change": True,
                },
            },
        )
        self.assertFalse(receipt["admitted"])
        self.assertTrue(any("does not materially change" in blocker for blocker in receipt["blockers"]))

    def test_sensor_work_bound_to_route_blocker_is_admitted(self):
        state = self.state()
        target = state["navigation"]["next_action"]["capability_id"]
        receipt = MISSION.admit_work(
            state,
            {
                "$schema": MISSION.ADMISSION_SCHEMA,
                "request_id": "research-blocker",
                "task_id": "research-blocker",
                "manager_id": "manager",
                "work_class": "research",
                "bootstrap": False,
                "justification": {
                    "consumer_task_id": "worker",
                    "blocker_id": target,
                    "decision_dependency": "Resolve exact API behavior required by the active action.",
                    "deadline_minutes": 10,
                    "expected_action_change": True,
                },
            },
        )
        self.assertTrue(receipt["admitted"], receipt)
        self.assertEqual(receipt["navigation_decision_sha256"], state["navigation"]["decision_sha256"])
        self.assertEqual(receipt["next_action"], state["navigation"]["next_action"])

    def test_three_actuation_dispatches_without_reality_progress_tighten_route(self):
        state = self.state()
        for index, minute in enumerate((1, 2, 3), 1):
            state = MISSION.record_event(
                state,
                MISSION.make_event(
                    f"dispatch-{index}",
                    "work_recorded",
                    occurred_at=f"2026-08-11T12:0{minute}:00Z",
                    work_class="implementation" if index < 3 else "repair",
                ),
            )
        self.assertEqual(state["navigation"]["mode"], "stalled_replan")
        self.assertTrue(state["navigation"]["velocity"]["stalled"])
        self.assertIn("research", state["governor_decision"]["paused_work_classes"])
        self.assertIn("documentation", state["governor_decision"]["paused_work_classes"])
        self.assertIn("implementation", state["governor_decision"]["allowed_work_classes"])
        self.assertTrue(any("Trajectory is stalled" in order for order in state["governor_decision"]["manager_orders"]))

    def test_reality_progress_reduces_distance_and_reprioritizes_route(self):
        state = self.state()
        before_distance = state["navigation"]["position"]["destination_distance"]
        target = state["navigation"]["next_action"]["capability_id"]
        state = MISSION.record_event(
            state,
            MISSION.make_event(
                "artifact",
                "artifact_materialized",
                occurred_at="2026-08-11T12:01:00Z",
                work_class="implementation",
                capability_id=target,
                evidence={"kind": "artifact", "path": "src/app.txt", "sha256": "a" * 64, "capability_id": target},
            ),
        )
        by_id = {item["capability_id"]: item for item in state["capabilities"]}
        self.assertEqual(by_id[target]["state"], "partial")
        self.assertLess(state["navigation"]["position"]["destination_distance"], before_distance)
        self.assertNotEqual(state["navigation"]["next_action"]["capability_id"], target)
        self.assertEqual(state["navigation"]["next_action"]["action_kind"], "materialize")


if __name__ == "__main__":
    unittest.main()
