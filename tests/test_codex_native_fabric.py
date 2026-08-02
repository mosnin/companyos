from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_codex_native_fabric.py"
SPEC = importlib.util.spec_from_file_location("validate_codex_native_fabric", MODULE_PATH)
assert SPEC and SPEC.loader
FABRIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FABRIC)
SIMULATION = ROOT / "programs/company-os-self-hosting/CODEX_NATIVE_TASK_FABRIC_SIMULATION.json"


class CodexNativeFabricRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(SIMULATION.read_text(encoding="utf-8"))

    def test_simulation_ladder_matches_all_five_oracles(self) -> None:
        result = FABRIC.validate_simulation(self.payload)
        self.assertTrue(result["valid"], result)
        self.assertEqual(5, len(result["results"]))
        self.assertEqual("no_go", self.payload["runtime_readiness_decision"])
        scores = {
            item["dimension"]: item["score"]
            for item in self.payload["runtime_readiness_scorecard"]
        }
        self.assertEqual(2.0, scores["hard_cancellation"])

    def test_native_lane_keeps_active_lifecycle_separate_from_rework(self) -> None:
        scenario = self.payload["scenarios"][2]
        self.assertEqual("native_observation", scenario["evidence_kind"])
        self.assertEqual("active", scenario["tasks"][0]["current_status"])
        self.assertIsNone(scenario["tasks"][0]["terminal_status"])
        self.assertEqual("rework_required", scenario["simulation_disposition"])
        self.assertEqual("rework", FABRIC.validate_scenario(scenario)["decision"])

    def test_open_active_manager_counts_against_concurrency(self) -> None:
        scenario = json.loads(json.dumps(self.payload["scenarios"][2]))
        scenario["budget"]["max_concurrency"] = 2
        result = FABRIC.validate_scenario(scenario)
        self.assertIn("budget_concurrency_pressure", result["error_codes"])


if __name__ == "__main__":
    unittest.main()
