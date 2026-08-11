from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/navigation-control/scripts/navigation_control.py"
spec = importlib.util.spec_from_file_location("company_os_navigation_trace", SCRIPT)
assert spec and spec.loader
NAV = importlib.util.module_from_spec(spec)
spec.loader.exec_module(NAV)


def state(name: str):
    return {
        "capability_id": "browser_path",
        "label": "Browser path",
        "state": name,
        "critical": True,
        "priority": 100,
        "first_reality": True,
        "final_required": True,
        "existing_implementation": None,
    }


def evaluate(capability_state: str, at: str, reality: dict, *, checkpointed=False, previous=None, events=None):
    return NAV.evaluate({
        "$schema": NAV.INPUT_SCHEMA,
        "objective_id": "trace",
        "objective": "Build and verify one real browser path.",
        "now": at,
        "mission_class": "quick_build",
        "capabilities": [state(capability_state)],
        "reality": reality,
        "checkpointed": checkpointed,
        "allocation": {"implementation": 1.0},
        "events": events or [],
        "previous_navigation": previous,
    })


class NavigationTraceTests(unittest.TestCase):
    def test_destination_distance_moves_monotonically_to_zero(self):
        r0 = {
            "internal_primitives": False,
            "runnable_capability": False,
            "connected_vertical_slice": False,
            "user_usable": False,
            "independent_acceptance": False,
        }
        r1 = {**r0, "internal_primitives": True}
        r2 = {**r1, "runnable_capability": True}
        r3 = {**r2, "connected_vertical_slice": True}
        r4 = {**r3, "user_usable": True}
        r5 = {**r4, "independent_acceptance": True}

        decisions = []
        first = evaluate("missing", "2026-08-11T12:00:00Z", r0)
        decisions.append(first)
        partial = evaluate("partial", "2026-08-11T12:02:00Z", r1, previous=first, events=[
            {"kind": "artifact_materialized", "occurred_at": "2026-08-11T12:02:00Z", "work_class": "implementation"},
        ])
        decisions.append(partial)
        runnable = evaluate("runnable", "2026-08-11T12:04:00Z", r2, previous=partial, events=[
            {"kind": "runtime_observed", "occurred_at": "2026-08-11T12:04:00Z", "work_class": "runtime"},
        ])
        decisions.append(runnable)
        connected = evaluate("connected", "2026-08-11T12:06:00Z", r3, previous=runnable, events=[
            {"kind": "journey_connected", "occurred_at": "2026-08-11T12:06:00Z", "work_class": "integration"},
        ])
        decisions.append(connected)
        durable = evaluate("connected", "2026-08-11T12:07:00Z", r4, checkpointed=True, previous=connected, events=[
            {"kind": "checkpoint_recorded", "occurred_at": "2026-08-11T12:07:00Z", "work_class": "checkpoint"},
        ])
        decisions.append(durable)
        arrived = evaluate("verified", "2026-08-11T12:09:00Z", r5, checkpointed=True, previous=durable, events=[
            {"kind": "independent_accepted", "occurred_at": "2026-08-11T12:09:00Z", "work_class": "evaluation"},
        ])
        decisions.append(arrived)

        distances = [item["position"]["destination_distance"] for item in decisions]
        self.assertEqual(distances, sorted(distances, reverse=True))
        self.assertEqual(distances[-1], 0.0)
        self.assertEqual(
            [item["next_action"]["action_kind"] for item in decisions],
            ["materialize", "run", "connect", "checkpoint", "verify", "hold_destination"],
        )
        self.assertEqual(arrived["mode"], "arrived")
        self.assertIn("do not invent new work", arrived["next_action"]["instruction"])


if __name__ == "__main__":
    unittest.main()
