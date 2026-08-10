from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/calibrate-outcome-stack/scripts/compile_calibration_fabric.py"
spec = importlib.util.spec_from_file_location("compile_calibration_fabric_under_test", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(MODULE)


class FakeStore:
    @staticmethod
    def load(project_root):
        return 4, {
            "instance": {"project_id": "project-a"},
            "strategy": {
                "program_version": 6,
                "north_star": "Produce excellent independently verified outcomes",
            },
        }


class CalibrationFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        MODULE.control_store_module = lambda: FakeStore
        self.write_contracts(1)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_json(self, relative: str, value) -> None:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def write_contracts(self, evaluator_count: int) -> None:
        evaluators = []
        adapters = []
        for index in range(evaluator_count):
            locator = f"workspace://.company-os/evaluators/eval-{index}/adapter.py"
            evaluators.append(
                {
                    "evaluator_id": f"eval-{index}",
                    "label": f"Evaluator {index}",
                    "required": True,
                    "independent_role": True,
                    "research_only": False,
                    "adapter_locator": locator,
                    "artifact_classes": ["playable_game"],
                    "produces_evidence": ["interaction_trace", "screenshot"],
                    "score_dimensions": ["gameplay", "visual_quality"],
                }
            )
            adapters.append(
                {
                    "adapter_locator": locator,
                    "runtime": "python",
                    "entrypoint": f".company-os/evaluators/eval-{index}/adapter.py",
                    "entrypoint_sha256": "a" * 64,
                    "timeout_seconds": 300,
                    "max_output_bytes": 1048576,
                    "arguments": [],
                    "artifact_classes": ["playable_game"],
                    "produces_evidence": ["interaction_trace", "screenshot"],
                    "score_dimensions": ["gameplay", "visual_quality"],
                }
            )
        self.write_json(
            "runtime/evaluators.json",
            {
                "$schema": MODULE.EVALUATOR_SCHEMA,
                "schema_version": 1,
                "objective_id": "viral-game",
                "ready": True,
                "evaluators": evaluators,
            },
        )
        self.write_json(
            "runtime/artifacts.json",
            {
                "$schema": MODULE.ARTIFACT_SCHEMA,
                "schema_version": 1,
                "objective_id": "viral-game",
                "ready": True,
                "artifact_classes": [
                    {
                        "artifact_class_id": "playable_game",
                        "required": True,
                        "modalities": ["interactive", "visual", "executable"],
                        "observation_methods": ["play_session"],
                        "required_evidence": ["interaction_trace", "screenshot"],
                    }
                ],
            },
        )
        self.write_json(
            "runtime/benchmarks.json",
            {
                "$schema": MODULE.BENCHMARK_SCHEMA,
                "schema_version": 1,
                "objective_id": "viral-game",
                "ready": True,
                "dimensions": [
                    {
                        "dimension_id": "gameplay-quality",
                        "required": True,
                        "references": [
                            {
                                "reference_id": "bad",
                                "locator": "https://example.com/bad",
                                "provenance": "Known weak example",
                                "quality_tier": "negative",
                            },
                            {
                                "reference_id": "excellent",
                                "locator": "https://example.com/excellent",
                                "provenance": "Known excellent example",
                                "quality_tier": "exemplar",
                            },
                        ],
                    }
                ],
            },
        )
        self.write_json(
            "runtime/registry.json",
            {
                "$schema": MODULE.REGISTRY_SCHEMA,
                "schema_version": 1,
                "adapters": adapters,
                "registry_sha256": "b" * 64,
            },
        )

    def compile(self, already=None):
        return MODULE.compile_manifest(
            self.project,
            "runtime/evaluators.json",
            "runtime/artifacts.json",
            "runtime/benchmarks.json",
            "runtime/registry.json",
            set(already or []),
        )

    def test_one_evaluator_creates_three_ranked_candidate_workers(self) -> None:
        result = self.compile()
        self.assertFalse(result["complete"])
        fabric = result["fabric"]
        self.assertTrue(MODULE.fabric_module().validate(fabric)["valid"])
        self.assertEqual(len(fabric["managers"]), 1)
        workers = fabric["managers"][0]["workers"]
        self.assertEqual(len(workers), 3)
        self.assertIn("rank 1", workers[0]["task"])
        self.assertIn("rank 2", workers[1]["task"])
        self.assertIn("rank 3", workers[2]["task"])
        self.assertIn("expected ranks 1, 2, 3", fabric["managers"][0]["acceptance"][-1])

    def test_two_evaluators_are_maximum_batch(self) -> None:
        self.write_contracts(3)
        result = self.compile()
        self.assertEqual(result["calibration_evaluator_ids"], ["eval-0", "eval-1"])
        self.assertEqual(result["remaining_evaluator_ids"], ["eval-2"])
        self.assertEqual(len(result["fabric"]["managers"]), 2)
        self.assertEqual(sum(len(manager["workers"]) for manager in result["fabric"]["managers"]), 6)
        self.assertTrue(MODULE.fabric_module().validate(result["fabric"])["valid"])

    def test_already_calibrated_evaluator_is_skipped(self) -> None:
        self.write_contracts(2)
        result = self.compile(["eval-0"])
        self.assertEqual(result["calibration_evaluator_ids"], ["eval-1"])

    def test_all_calibrated_returns_complete(self) -> None:
        result = self.compile(["eval-0"])
        self.assertTrue(result["complete"])
        self.assertIsNone(result["fabric"])

    def test_missing_negative_anchor_fails(self) -> None:
        benchmarks = json.loads((self.project / "runtime/benchmarks.json").read_text())
        benchmarks["dimensions"][0]["references"] = [benchmarks["dimensions"][0]["references"][1]]
        self.write_json("runtime/benchmarks.json", benchmarks)
        with self.assertRaises(MODULE.CalibrationFabricError) as caught:
            self.compile()
        self.assertEqual(caught.exception.code, "E_BENCHMARK")


if __name__ == "__main__":
    unittest.main()
