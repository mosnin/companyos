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
            "status": "observed",
            "value": "gpt-5.6-sol",
            "source": "requested_model",
        }
        result = fabric.validate_scenario(scenario)
        self.assertIn("fixture_model_mislabeled_observed", result["error_codes"])

    def test_native_model_requires_recognized_host_observation_source(self) -> None:
        scenario = json.loads(json.dumps(self.payload["scenarios"][2]))
        scenario["tasks"][0]["observed_model"] = {
            "status": "observed",
            "value": "gpt-5.6-sol",
            "source": "charter.requested_model",
        }
        result = fabric.validate_scenario(scenario)
        self.assertIn("observed_model_source_untrusted", result["error_codes"])

    def test_recognized_native_model_source_is_attributable(self) -> None:
        scenario = json.loads(json.dumps(self.payload["scenarios"][2]))
        scenario["tasks"][0]["observed_model"] = {
            "status": "observed",
            "value": "gpt-5.6-sol",
            "source": "host_observation:list_threads:model",
        }
        result = fabric.validate_scenario(scenario)
        self.assertNotIn("observed_model_source_untrusted", result["error_codes"])

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
        self.assertIsNone(scenario["tasks"][1]["created_order"])
        self.assertIsNone(scenario["tasks"][1]["started_order"])
        self.assertIsNone(scenario["tasks"][2]["created_order"])
        self.assertIsNone(scenario["tasks"][2]["started_order"])

    def test_fixture_timing_cannot_masquerade_as_host_observation(self) -> None:
        scenario = json.loads(json.dumps(self.payload["scenarios"][0]))
        scenario["tasks"][0]["telemetry"]["elapsed_ms"]["status"] = "observed"
        result = fabric.validate_scenario(scenario)
        self.assertIn("fixture_mislabeled_observed", result["error_codes"])

    def test_real_manager_lifecycle_remains_active(self) -> None:
        scenario = self.payload["scenarios"][2]
        manager = scenario["tasks"][0]
        self.assertEqual("native_observation", scenario["evidence_kind"])
        self.assertEqual("active", manager["current_status"])
        self.assertIsNone(manager["terminal_status"])
        self.assertIsNone(manager["terminal_order"])
        self.assertEqual("rework_required", scenario["simulation_disposition"])
        self.assertEqual("rework", fabric.validate_scenario(scenario)["decision"])

    def test_accepted_task_requires_created_and_started_events(self) -> None:
        scenario = json.loads(json.dumps(self.payload["scenarios"][0]))
        scenario["tasks"][1]["started_order"] = None
        result = fabric.validate_scenario(scenario)
        self.assertIn("terminal_order", result["error_codes"])

    def test_active_interval_counts_toward_concurrency_pressure(self) -> None:
        scenario = json.loads(json.dumps(self.payload["scenarios"][2]))
        scenario["budget"]["max_concurrency"] = 2
        result = fabric.validate_scenario(scenario)
        self.assertIn("budget_concurrency_pressure", result["error_codes"])

    def test_active_task_can_never_claim_terminal_state(self) -> None:
        scenario = json.loads(json.dumps(self.payload["scenarios"][2]))
        scenario["tasks"][0]["terminal_status"] = "accepted"
        scenario["tasks"][0]["terminal_order"] = 6
        result = fabric.validate_scenario(scenario)
        self.assertIn("active_marked_terminal", result["error_codes"])

    def test_native_identity_must_be_unique_and_match_native_task_id(self) -> None:
        scenario = json.loads(json.dumps(self.payload["scenarios"][2]))
        scenario["tasks"][1]["native_metadata"]["thread_id"] = scenario["tasks"][0]["task_id"]
        result = fabric.validate_scenario(scenario)
        self.assertIn("native_identity_duplicate", result["error_codes"])
        self.assertIn("native_identity_mismatch", result["error_codes"])

    def test_iteration_mappings_are_nonempty_unique_and_known(self) -> None:
        for reruns in ([], ["scenario-1-known-answer", "scenario-1-known-answer"], ["scenario-unknown"]):
            with self.subTest(reruns=reruns):
                payload = json.loads(json.dumps(self.payload))
                payload["iterations"][0]["rerun_scenarios"] = reruns
                result = fabric.validate_simulation(payload)
                self.assertFalse(result["valid"])
                self.assertTrue(any("rerun_scenarios" in item for item in result["errors"]))

    def test_scope_ancestor_overlap_is_rejected(self) -> None:
        scenario = json.loads(json.dumps(self.payload["scenarios"][0]))
        scenario["tasks"][1]["scope"] = ["work"]
        scenario["tasks"][1]["scope_digest"] = fabric.digest(["work"])
        extra = json.loads(json.dumps(scenario["tasks"][1]))
        extra["task_id"] = "worker-synthetic-child"
        extra["native_metadata"]["thread_id"] = "synthetic-worker-child-thread"
        extra["scope"] = ["work/child"]
        extra["scope_digest"] = fabric.digest(["work/child"])
        extra["report"]["scope_digest"] = extra["scope_digest"]
        extra["artifact"]["task_id"] = extra["task_id"]
        scenario["tasks"].append(extra)
        scenario["budget"]["max_tasks"] = 3
        result = fabric.validate_scenario(scenario)
        self.assertIn("scope_collision", result["error_codes"])

    def test_case_unicode_and_path_ambiguity_fail_closed(self) -> None:
        for scope in ("Worker/Synthetic", "worker/synthétic", "worker//synthetic", "../worker"):
            with self.subTest(scope=scope):
                scenario = json.loads(json.dumps(self.payload["scenarios"][0]))
                scenario["tasks"][1]["scope"] = [scope]
                scenario["tasks"][1]["scope_digest"] = fabric.digest([scope])
                scenario["tasks"][1]["report"]["scope_digest"] = fabric.digest([scope])
                result = fabric.validate_scenario(scenario)
                self.assertIn("scope_noncanonical", result["error_codes"])


if __name__ == "__main__":
    unittest.main()
