#!/usr/bin/env python3

from __future__ import annotations

import json
import unittest
from pathlib import Path

import validate_codex_native_fabric as fabric


ROOT = Path(__file__).resolve().parents[5]
SIMULATION = ROOT / "programs/company-os-self-hosting/CODEX_NATIVE_TASK_FABRIC_SIMULATION.json"


class CodexNativeFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(SIMULATION.read_text(encoding="utf-8"))

    def test_five_scenario_ladder_matches_oracles(self) -> None:
        result = fabric.validate_simulation(self.payload)
        self.assertTrue(result["valid"], result)
        self.assertEqual(5, len(result["results"]))
        self.assertTrue(all(item["matched"] for item in result["results"]))

    def test_requested_model_never_proves_observed_model(self) -> None:
        scenario = json.loads(json.dumps(self.payload["scenarios"][0]))
        scenario["tasks"][0]["observed_model"] = {
            "status": "unavailable",
            "value": "gpt-5.6-sol",
            "source": "requested_model",
        }
        result = fabric.validate_scenario(scenario)
        self.assertIn("observed_model_fabricated", result["error_codes"])

    def test_foreign_artifact_fails_closed(self) -> None:
        scenario = json.loads(json.dumps(self.payload["scenarios"][0]))
        scenario["tasks"][-1]["artifact"]["project_id"] = "project-synthetic-01-copy"
        result = fabric.validate_scenario(scenario)
        self.assertEqual("rejected", result["decision"])
        self.assertIn("artifact_isolation", result["error_codes"])

    def test_unavailable_host_telemetry_cannot_be_filled(self) -> None:
        scenario = json.loads(json.dumps(self.payload["scenarios"][0]))
        scenario["tasks"][0]["telemetry"]["tokens"] = {
            "status": "observed",
            "value": 1,
            "source": "invented",
        }
        result = fabric.validate_scenario(scenario)
        self.assertIn("host_capability_overclaim", result["error_codes"])

    def test_dependency_cannot_start_on_malformed_upstream(self) -> None:
        scenario = self.payload["scenarios"][1]
        result = fabric.validate_scenario(scenario)
        self.assertEqual("blocked", result["decision"])
        self.assertIn("dependency_blocked", result["error_codes"])
        self.assertIsNone(scenario["tasks"][1]["start_order"])
        self.assertIsNone(scenario["tasks"][2]["start_order"])

    def test_fixture_timing_cannot_masquerade_as_host_observation(self) -> None:
        scenario = json.loads(json.dumps(self.payload["scenarios"][0]))
        scenario["tasks"][0]["telemetry"]["elapsed_ms"]["status"] = "observed"
        result = fabric.validate_scenario(scenario)
        self.assertIn("fixture_mislabeled_observed", result["error_codes"])

    def test_real_manager_lifecycle_remains_active(self) -> None:
        scenario = self.payload["scenarios"][2]
        manager = scenario["tasks"][0]
        self.assertEqual("native_observation", scenario["evidence_kind"])
        self.assertEqual("active", manager["terminal_status"])
        self.assertIsNone(manager["terminal_order"])
        self.assertEqual("rework_required", scenario["simulation_disposition"])
        self.assertEqual("rework", fabric.validate_scenario(scenario)["decision"])


if __name__ == "__main__":
    unittest.main()
