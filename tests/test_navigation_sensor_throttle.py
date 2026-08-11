from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/mission-execution-control/scripts/mission_control.py"
spec = importlib.util.spec_from_file_location("company_os_navigation_sensor_throttle", SCRIPT)
assert spec and spec.loader
MISSION = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MISSION)


class NavigationSensorThrottleTests(unittest.TestCase):
    def stalled_state(self):
        state = MISSION.initialize_state(
            "micro",
            "Build a real browser app.",
            started_at="2026-08-11T12:00:00Z",
            mission_class="quick_build",
            duration_minutes=90,
        )
        for index, kind in enumerate(("task_completed", "task_failed", "task_completed"), 1):
            state = MISSION.record_event(
                state,
                MISSION.make_event(
                    f"attempt-{index}",
                    kind,
                    occurred_at=f"2026-08-11T12:0{index}:00Z",
                    work_class="implementation" if index < 3 else "repair",
                ),
            )
        self.assertEqual(state["navigation"]["mode"], "stalled_replan")
        return state

    def test_stalled_route_pauses_broad_sensors_but_keeps_evaluation_available(self):
        state = self.stalled_state()
        decision = state["governor_decision"]
        self.assertIn("research", decision["paused_work_classes"])
        self.assertIn("architecture", decision["paused_work_classes"])
        self.assertIn("governance", decision["paused_work_classes"])
        self.assertIn("documentation", decision["paused_work_classes"])
        self.assertIn("evaluation", decision["allowed_work_classes"])

        target = state["navigation"]["next_action"]["capability_id"]
        evaluation = MISSION.admit_work(
            state,
            {
                "$schema": MISSION.ADMISSION_SCHEMA,
                "request_id": "bounded-evaluation",
                "task_id": "bounded-evaluation",
                "manager_id": "manager",
                "work_class": "evaluation",
                "bootstrap": False,
                "justification": {
                    "consumer_task_id": "route-worker",
                    "blocker_id": target,
                    "decision_dependency": "Determine whether the current candidate is broken and which targeted repair changes the route.",
                    "deadline_minutes": 10,
                    "expected_action_change": True,
                },
            },
        )
        self.assertTrue(evaluation["admitted"], evaluation)

        research = MISSION.admit_work(
            state,
            {
                "$schema": MISSION.ADMISSION_SCHEMA,
                "request_id": "more-research",
                "task_id": "more-research",
                "manager_id": "manager",
                "work_class": "research",
                "bootstrap": False,
                "justification": {
                    "consumer_task_id": "route-worker",
                    "blocker_id": target,
                    "decision_dependency": "Research the blocker further.",
                    "deadline_minutes": 10,
                    "expected_action_change": True,
                },
            },
        )
        self.assertFalse(research["admitted"])
        self.assertTrue(any("paused" in blocker for blocker in research["blockers"]))


if __name__ == "__main__":
    unittest.main()
