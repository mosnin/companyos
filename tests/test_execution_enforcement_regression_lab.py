from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/mission-execution-control/scripts/execution_regression_lab.py"
spec = importlib.util.spec_from_file_location("execution_enforcement_regression_lab", SCRIPT)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


class ExecutionEnforcementRegressionLabTests(unittest.TestCase):
    def test_all_controlled_missions_pass(self):
        result = MODULE.run_lab()
        self.assertTrue(result["passed"], result)
        self.assertEqual(
            [item["case_id"] for item in result["results"]],
            ["website", "n8n", "firecrawl", "support"],
        )
        self.assertTrue(all(item["passed"] for item in result["results"]))


if __name__ == "__main__":
    unittest.main()
