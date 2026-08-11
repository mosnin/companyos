from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/govern-outcome-execution/scripts/executive_governor.py"
spec = importlib.util.spec_from_file_location("executive_governor_under_test", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(MODULE)


def payload(*, budget, reality, capabilities, allocation):
    return {
        "$schema": MODULE.INPUT_SCHEMA,
        "objective_id": "regression",
        "objective": "Deliver the actual requested outcome.",
        "budget_fraction_consumed": budget,
        "reality": reality,
        "required_capabilities": capabilities,
        "allocation": allocation,
    }


class OutcomeExecutiveGovernorTests(unittest.TestCase):
    def test_fin_regression_declares_critical_path_instead_of_more_docs(self):
        decision = MODULE.evaluate(payload(
            budget=0.75,
            reality={"internal_primitives": True, "runnable_capability": False, "connected_vertical_slice": False, "user_usable": False, "independent_acceptance": False},
            capabilities=[
                {"capability_id": "browser_support_vertical_slice", "state": "missing", "critical": True, "priority": 100},
                {"capability_id": "billing", "state": "missing", "critical": False, "priority": 40},
            ],
            allocation={"research": .25, "architecture": .20, "governance": .20, "documentation": .10, "implementation": .15, "integration": .05, "runtime": .05},
        ))
        self.assertEqual(decision["reality_level"], "R1")
        self.assertEqual(decision["mode"], "critical_path")
        self.assertTrue(decision["first_reality_incident"])
        self.assertTrue(decision["allocation_incident"])
        self.assertEqual(decision["dominant_bottleneck"]["capability_id"], "browser_support_vertical_slice")
        self.assertIn("documentation", decision["paused_work_classes"])
        self.assertLess(decision["product_execution_ratio"], .5)

    def test_n8n_regression_prioritizes_compiler_after_runtime_harness_exists(self):
        decision = MODULE.evaluate(payload(
            budget=0.44,
            reality={"internal_primitives": True, "runnable_capability": True, "connected_vertical_slice": False, "user_usable": False, "independent_acceptance": False},
            capabilities=[
                {"capability_id": "objective_to_workflow_compiler", "state": "missing", "critical": True, "priority": 100},
                {"capability_id": "protected_benchmarks", "state": "missing", "critical": False, "priority": 30},
            ],
            allocation={"research": .25, "governance": .25, "architecture": .20, "implementation": .20, "runtime": .10},
        ))
        self.assertEqual(decision["reality_level"], "R2")
        self.assertEqual(decision["mode"], "compression")
        self.assertTrue(decision["first_reality_incident"])
        self.assertEqual(decision["dominant_bottleneck"]["capability_id"], "objective_to_workflow_compiler")
        self.assertTrue(any("smallest connected end-to-end artifact" in order for order in decision["manager_orders"]))

    def test_firecrawl_regression_prefers_supplied_provider_over_adjacent_reimplementation(self):
        decision = MODULE.evaluate(payload(
            budget=0.65,
            reality={"internal_primitives": True, "runnable_capability": True, "connected_vertical_slice": True, "user_usable": False, "independent_acceptance": False},
            capabilities=[
                {"capability_id": "firecrawl_provider_integration", "state": "missing", "critical": True, "priority": 100, "existing_implementation": "firecrawl/firecrawl + CLI + MCP"},
                {"capability_id": "browser_rendering", "state": "missing", "critical": False, "priority": 50},
            ],
            allocation={"research": .15, "governance": .15, "implementation": .35, "integration": .10, "runtime": .15, "evaluation": .10},
        ))
        self.assertEqual(decision["reality_level"], "R3")
        self.assertEqual(decision["mode"], "normal")
        self.assertFalse(decision["first_reality_incident"])
        self.assertTrue(decision["existing_capability_preference"])
        self.assertEqual(decision["dominant_bottleneck"]["capability_id"], "firecrawl_provider_integration")
        self.assertTrue(any("Integrate and exercise supplied capability" in order for order in decision["manager_orders"]))

    def test_reality_closure_forces_run_fix_verify_package(self):
        decision = MODULE.evaluate(payload(
            budget=.92,
            reality={"internal_primitives": True, "runnable_capability": True, "connected_vertical_slice": True, "user_usable": True, "independent_acceptance": False},
            capabilities=[{"capability_id": "final_acceptance", "state": "connected", "critical": True, "priority": 100}],
            allocation={"implementation": .4, "integration": .2, "runtime": .2, "evaluation": .2},
        ))
        self.assertEqual(decision["mode"], "reality_closure")
        self.assertIn("research", decision["paused_work_classes"])
        self.assertIn("documentation", decision["paused_work_classes"])
        self.assertNotIn("implementation", decision["allowed_work_classes"])
        MODULE.verify(decision)

    def test_higher_reality_cannot_float_above_missing_lower_layer(self):
        with self.assertRaises(MODULE.GovernorError):
            MODULE.evaluate(payload(
                budget=.1,
                reality={"internal_primitives": False, "runnable_capability": True, "connected_vertical_slice": False, "user_usable": False, "independent_acceptance": False},
                capabilities=[{"capability_id": "thing", "state": "missing"}],
                allocation={"implementation": 1.0},
            ))


if __name__ == "__main__":
    unittest.main()
