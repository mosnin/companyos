from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/navigation-control/scripts/navigation_control.py"
spec = importlib.util.spec_from_file_location("company_os_navigation_safety_test", SCRIPT)
assert spec and spec.loader
NAV = importlib.util.module_from_spec(spec)
spec.loader.exec_module(NAV)


def decision():
    return NAV.evaluate({
        "$schema": NAV.INPUT_SCHEMA,
        "objective_id": "micro",
        "objective": "Build a real browser tool.",
        "now": "2026-08-11T12:00:00Z",
        "mission_class": "quick_build",
        "capabilities": [{
            "capability_id": "browser_path",
            "label": "browser path",
            "state": "missing",
            "critical": True,
            "priority": 100,
            "first_reality": True,
            "final_required": True,
            "existing_implementation": None,
        }],
        "reality": {
            "internal_primitives": False,
            "runnable_capability": False,
            "connected_vertical_slice": False,
            "user_usable": False,
            "independent_acceptance": False,
        },
        "checkpointed": False,
        "allocation": {},
        "events": [],
    })


class NavigationSafetyInterruptTests(unittest.TestCase):
    def test_concrete_hazard_can_interrupt_active_route(self):
        useful, reason = NAV.sensor_request_is_useful(decision(), {
            "blocker_id": "security-boundary",
            "decision_dependency": "Determine whether the active operation would expose a production secret.",
            "safety_interrupt": True,
            "hazard_evidence": "Runtime trace shows a production credential would be written to a client bundle.",
        })
        self.assertTrue(useful)
        self.assertIn("safety hazard", reason)

    def test_empty_safety_claim_cannot_be_used_as_sensor_escape_hatch(self):
        useful, reason = NAV.sensor_request_is_useful(decision(), {
            "blocker_id": "security-boundary",
            "decision_dependency": "Do more general security research.",
            "safety_interrupt": True,
            "hazard_evidence": "",
        })
        self.assertFalse(useful)
        self.assertIn("requires concrete hazard evidence", reason)

    def test_blocked_action_claim_must_match_active_route(self):
        useful, reason = NAV.sensor_request_is_useful(decision(), {
            "blocker_id": "unrelated-history",
            "decision_dependency": "Research something adjacent.",
            "current_action_blocked": True,
        })
        self.assertFalse(useful)
        self.assertIn("not bound to the active route capability", reason)


if __name__ == "__main__":
    unittest.main()
