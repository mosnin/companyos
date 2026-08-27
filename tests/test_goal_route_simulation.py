from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/goal-route-system/scripts/goal_route.py"
spec = importlib.util.spec_from_file_location("company_os_goal_route_simulation", SCRIPT)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


class GoalRouteSimulationTests(unittest.TestCase):
    def test_cross_domain_simulation_passes(self):
        result = MODULE.simulate()
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["scenario_count"], 4)
        self.assertEqual(
            [item["scenario_id"] for item in result["results"]],
            ["software", "consumer_company", "marketing", "operations"],
        )
        self.assertTrue(all(item["manager_goals"] > 0 for item in result["results"]))
        self.assertTrue(all(item["worker_goals"] > 0 for item in result["results"]))
        marketing = next(item for item in result["results"] if item["scenario_id"] == "marketing")
        self.assertEqual(marketing["revenue_target"], 100000.0)


if __name__ == "__main__":
    unittest.main()
