"""The planning meter: enforce action economics, not doctrine.

A mission may spend at most FIRST_ARTIFACT_BUDGET_FRACTION of its budget —
wall clock OR tokens, whichever runs out first — before the first real
artifact exists. Past that point the governor pauses every non-execution work
class and admit_work rejects further planning fail-closed.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MISSION = _load(
    "skills/company-os/mission-execution-control/scripts/mission_control.py",
    "planning_meter_mission_control",
)
GOVERNOR = _load(
    "skills/company-os/govern-outcome-execution/scripts/executive_governor.py",
    "planning_meter_executive_governor",
)


def governor_input(*, budget: float, reality_level: int) -> dict:
    reality = {
        "internal_primitives": reality_level >= 1,
        "runnable_capability": reality_level >= 2,
        "connected_vertical_slice": reality_level >= 3,
        "user_usable": reality_level >= 4,
        "independent_acceptance": reality_level >= 5,
    }
    return {
        "$schema": GOVERNOR.INPUT_SCHEMA,
        "objective_id": "meter",
        "objective": "Prove the planning meter",
        "budget_fraction_consumed": budget,
        "reality": reality,
        "required_capabilities": [
            {"capability_id": "core", "state": "missing", "critical": True, "priority": 90}
        ],
        "allocation": {"research": 1.0},
    }


class GovernorPlanningMeterTests(unittest.TestCase):
    def test_overrun_pauses_every_non_execution_class(self) -> None:
        decision = GOVERNOR.evaluate(governor_input(budget=0.30, reality_level=0))
        self.assertTrue(decision["planning_overrun"])
        self.assertEqual(decision["mode"], "compression")
        paused = set(decision["paused_work_classes"])
        self.assertLessEqual({"research", "architecture", "governance", "documentation"}, paused)
        allowed = set(decision["allowed_work_classes"])
        self.assertLessEqual({"implementation", "integration", "runtime", "repair"}, allowed)
        self.assertFalse(allowed & paused)
        self.assertTrue(any("Planning allowance is exhausted" in order for order in decision["manager_orders"]))

    def test_first_artifact_lifts_the_planning_lock(self) -> None:
        decision = GOVERNOR.evaluate(governor_input(budget=0.30, reality_level=1))
        self.assertFalse(decision["planning_overrun"])

    def test_meter_respects_a_configured_fraction(self) -> None:
        payload = governor_input(budget=0.15, reality_level=0)
        self.assertFalse(GOVERNOR.evaluate(payload)["planning_overrun"])
        payload["first_artifact_budget_fraction"] = 0.10
        self.assertTrue(GOVERNOR.evaluate(payload)["planning_overrun"])


class TokenBudgetMeterTests(unittest.TestCase):
    def _mission(self, token_budget: int | None):
        return MISSION.initialize_state(
            "meter-mission",
            "Ship a runnable meter fixture",
            started_at="2026-08-29T00:00:00Z",
            mission_class="bounded_feature",
            token_budget=token_budget,
        )

    def _spend(self, state, event_id: str, tokens: float, occurred_at: str):
        event = MISSION.make_event(
            event_id,
            "work_recorded",
            occurred_at=occurred_at,
            work_class="research",
            units=1.0,
            tokens=tokens,
        )
        return MISSION.record_event(state, event)

    def test_token_burn_advances_the_budget_without_wall_clock(self) -> None:
        state = self._mission(token_budget=1_000_000)
        # One minute of wall clock, 40% of the token allowance, zero artifacts.
        state = self._spend(state, "burn-1", 400_000.0, "2026-08-29T00:01:00Z")
        self.assertEqual(state["tokens_consumed"], 400_000.0)
        decision = state["governor_decision"]
        self.assertTrue(decision["planning_overrun"])
        self.assertGreaterEqual(decision["budget_fraction_consumed"], 0.4)
        self.assertIn("research", decision["paused_work_classes"])

    def test_overrun_blocks_planning_admissions_but_not_execution(self) -> None:
        state = self._mission(token_budget=1_000_000)
        state = self._spend(state, "burn-1", 400_000.0, "2026-08-29T00:01:00Z")
        research = MISSION.admit_work(
            state,
            {
                "$schema": MISSION.ADMISSION_SCHEMA,
                "request_id": "req-research",
                "work_class": "research",
                "task_id": "task-1",
                "manager_id": "manager-1",
            },
        )
        self.assertFalse(research["admitted"])
        self.assertTrue(any("paused by governor" in blocker for blocker in research["blockers"]))
        implementation = MISSION.admit_work(
            state,
            {
                "$schema": MISSION.ADMISSION_SCHEMA,
                "request_id": "req-implementation",
                "work_class": "implementation",
                "task_id": "task-2",
                "manager_id": "manager-1",
            },
        )
        self.assertTrue(implementation["admitted"], implementation["blockers"])

    def test_token_spend_accumulates_across_events(self) -> None:
        state = self._mission(token_budget=1_000_000)
        state = self._spend(state, "burn-1", 100_000.0, "2026-08-29T00:01:00Z")
        state = self._spend(state, "burn-2", 50_000.0, "2026-08-29T00:02:00Z")
        self.assertEqual(state["tokens_consumed"], 150_000.0)
        self.assertFalse(state["governor_decision"]["planning_overrun"])

    def test_missions_without_a_token_budget_keep_time_only_metering(self) -> None:
        state = self._mission(token_budget=None)
        state = self._spend(state, "burn-1", 900_000.0, "2026-08-29T00:01:00Z")
        # Enormous token burn, but no token budget declared: only wall clock
        # meters the mission, and one minute in it is still in normal mode.
        decision = state["governor_decision"]
        self.assertFalse(decision["planning_overrun"])
        self.assertLess(decision["budget_fraction_consumed"], 0.05)


if __name__ == "__main__":
    unittest.main()
