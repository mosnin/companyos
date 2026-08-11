from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/navigation-control/scripts/navigation_control.py"
spec = importlib.util.spec_from_file_location("company_os_navigation_control_test", SCRIPT)
assert spec and spec.loader
NAV = importlib.util.module_from_spec(spec)
spec.loader.exec_module(NAV)


def capability(
    capability_id: str,
    state: str,
    *,
    critical: bool = True,
    priority: int = 100,
    first: bool = True,
    final: bool = True,
    existing: str | None = None,
):
    return {
        "capability_id": capability_id,
        "label": capability_id.replace("_", " "),
        "state": state,
        "critical": critical,
        "priority": priority,
        "first_reality": first,
        "final_required": final,
        "existing_implementation": existing,
    }


def payload(capabilities, *, reality=None, checkpointed=False, allocation=None, events=None, previous=None, now="2026-08-11T12:10:00Z", mission_class="quick_build"):
    return {
        "$schema": NAV.INPUT_SCHEMA,
        "objective_id": "micro",
        "objective": "Build a real browser tool.",
        "now": now,
        "mission_class": mission_class,
        "capabilities": capabilities,
        "reality": reality or {
            "internal_primitives": False,
            "runnable_capability": False,
            "connected_vertical_slice": False,
            "user_usable": False,
            "independent_acceptance": False,
        },
        "checkpointed": checkpointed,
        "allocation": allocation or {},
        "events": events or [],
        "previous_navigation": previous,
    }


class NavigationControlTests(unittest.TestCase):
    def test_missing_first_reality_routes_to_action_not_research(self):
        decision = NAV.evaluate(payload([capability("browser_path", "missing")]))
        self.assertEqual(decision["waypoint"], "R3_FIRST_REALITY")
        self.assertEqual(decision["next_action"]["action_kind"], "materialize")
        self.assertEqual(decision["next_action"]["work_class"], "implementation")
        self.assertGreater(decision["position"]["destination_distance"], 0)
        self.assertIn("explicit user requirements", decision["actuation_policy"]["never_cut"])

    def test_existing_implementation_is_integrated_before_replacement(self):
        decision = NAV.evaluate(payload([
            capability("firecrawl_provider", "missing", existing="https://github.com/firecrawl/firecrawl.git")
        ]))
        self.assertEqual(decision["next_action"]["action_kind"], "integrate_existing")
        self.assertEqual(decision["next_action"]["work_class"], "integration")

    def test_runnable_capability_routes_to_connection(self):
        decision = NAV.evaluate(payload([
            capability("browser_path", "runnable")
        ], reality={
            "internal_primitives": True,
            "runnable_capability": True,
            "connected_vertical_slice": False,
            "user_usable": False,
            "independent_acceptance": False,
        }))
        self.assertEqual(decision["next_action"]["action_kind"], "connect")
        self.assertEqual(decision["next_action"]["work_class"], "integration")

    def test_connected_final_scope_without_checkpoint_routes_to_checkpoint(self):
        decision = NAV.evaluate(payload([
            capability("browser_path", "connected", first=True, final=True)
        ], reality={
            "internal_primitives": True,
            "runnable_capability": True,
            "connected_vertical_slice": True,
            "user_usable": False,
            "independent_acceptance": False,
        }, checkpointed=False))
        self.assertEqual(decision["waypoint"], "R4_USER_USABLE")
        self.assertEqual(decision["next_action"]["action_kind"], "checkpoint")

    def test_checkpointed_connected_scope_routes_to_independent_verification(self):
        decision = NAV.evaluate(payload([
            capability("browser_path", "connected", first=True, final=True)
        ], reality={
            "internal_primitives": True,
            "runnable_capability": True,
            "connected_vertical_slice": True,
            "user_usable": True,
            "independent_acceptance": False,
        }, checkpointed=True))
        self.assertEqual(decision["waypoint"], "R5_INDEPENDENT_ACCEPTANCE")
        self.assertEqual(decision["next_action"]["action_kind"], "verify")
        self.assertEqual(decision["next_action"]["work_class"], "evaluation")

    def test_verified_destination_stops_inventing_work(self):
        decision = NAV.evaluate(payload([
            capability("browser_path", "verified")
        ], reality={
            "internal_primitives": True,
            "runnable_capability": True,
            "connected_vertical_slice": True,
            "user_usable": True,
            "independent_acceptance": True,
        }, checkpointed=True))
        self.assertEqual(decision["mode"], "arrived")
        self.assertEqual(decision["position"]["destination_distance"], 0.0)
        self.assertEqual(decision["next_action"]["action_kind"], "hold_destination")

    def test_real_progress_reduces_destination_distance(self):
        first = NAV.evaluate(payload([
            capability("browser_path", "missing")
        ], now="2026-08-11T12:00:00Z"))
        second = NAV.evaluate(payload([
            capability("browser_path", "runnable")
        ], reality={
            "internal_primitives": True,
            "runnable_capability": True,
            "connected_vertical_slice": False,
            "user_usable": False,
            "independent_acceptance": False,
        }, previous=first, now="2026-08-11T12:05:00Z", events=[
            {"kind": "artifact_materialized", "occurred_at": "2026-08-11T12:02:00Z", "work_class": "implementation"},
            {"kind": "runtime_observed", "occurred_at": "2026-08-11T12:05:00Z", "work_class": "runtime"},
        ]))
        self.assertLess(second["position"]["destination_distance"], first["position"]["destination_distance"])
        self.assertGreater(second["velocity"]["distance_delta"], 0)

    def test_three_completed_actuation_attempts_without_progress_trigger_replan(self):
        events = [
            {"kind": "task_completed", "occurred_at": "2026-08-11T12:01:00Z", "work_class": "implementation"},
            {"kind": "task_failed", "occurred_at": "2026-08-11T12:03:00Z", "work_class": "implementation"},
            {"kind": "task_completed", "occurred_at": "2026-08-11T12:05:00Z", "work_class": "repair"},
        ]
        decision = NAV.evaluate(payload([
            capability("browser_path", "missing")
        ], events=events, now="2026-08-11T12:06:00Z"))
        self.assertEqual(decision["mode"], "stalled_replan")
        self.assertTrue(decision["velocity"]["stalled"])
        self.assertLessEqual(decision["sensor_posture"]["sensor_fraction_ceiling"], 0.15)

    def test_parallel_dispatch_alone_does_not_fake_stagnation(self):
        events = [
            {"kind": "work_recorded", "occurred_at": "2026-08-11T12:01:00Z", "work_class": "implementation"},
            {"kind": "work_recorded", "occurred_at": "2026-08-11T12:01:10Z", "work_class": "implementation"},
            {"kind": "work_recorded", "occurred_at": "2026-08-11T12:01:20Z", "work_class": "integration"},
        ]
        decision = NAV.evaluate(payload([capability("browser_path", "missing")], events=events, now="2026-08-11T12:02:00Z"))
        self.assertFalse(decision["velocity"]["stalled"])
        self.assertEqual(decision["velocity"]["actuation_attempts_since_progress"], 0)

    def test_sensor_overrun_is_detected_before_r3(self):
        decision = NAV.evaluate(payload([
            capability("browser_path", "missing")
        ], allocation={"research": 0.4, "documentation": 0.1, "implementation": 0.5}))
        self.assertTrue(decision["sensor_posture"]["overrun"])
        self.assertTrue(any("Sensor work exceeded" in order for order in decision["orders"]))

    def test_sensor_question_must_change_or_unblock_next_action(self):
        decision = NAV.evaluate(payload([
            capability("browser_path", "missing")
        ]))
        useful, _ = NAV.sensor_request_is_useful(decision, {
            "blocker_id": "browser_path",
            "decision_dependency": "Need exact browser API semantics before implementation.",
            "expected_action_change": True,
        })
        useless, reason = NAV.sensor_request_is_useful(decision, {
            "blocker_id": "brand-history",
            "decision_dependency": "Would be nice to know more background.",
            "expected_action_change": True,
        })
        self.assertTrue(useful)
        self.assertFalse(useless)
        self.assertIn("does not materially change", reason)


if __name__ == "__main__":
    unittest.main()
