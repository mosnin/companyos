from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/build-outcome-evaluators/scripts/compile_evaluator_build_fabric.py"
spec = importlib.util.spec_from_file_location("compile_evaluator_build_fabric_under_test", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(MODULE)


class FakeStore:
    @staticmethod
    def load(project_root):
        return 7, {
            "instance": {"project_id": "project-a"},
            "strategy": {
                "program_version": 4,
                "north_star": "Produce excellent independently verified outcomes",
            },
        }


class EvaluatorBuildFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        MODULE.control_store_module = lambda: FakeStore
        self.write_contracts(2)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_json(self, relative: str, value) -> None:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def evaluator_contract(self, count: int) -> dict:
        return {
            "$schema": MODULE.CONTRACT_SCHEMA,
            "schema_version": 1,
            "objective_id": "viral-game",
            "ready": True,
            "blockers": [],
            "evaluators": [
                {
                    "evaluator_id": f"eval-{index}",
                    "label": f"Evaluator {index}",
                    "required": True,
                    "independent_role": True,
                    "research_only": False,
                    "adapter_locator": f"workspace://.company-os/evaluators/eval-{index}/adapter.py",
                    "artifact_classes": ["playable_game"],
                    "produces_evidence": ["interaction_trace", "screenshot"],
                    "score_dimensions": [f"dimension-{index}"],
                }
                for index in range(count)
            ],
        }

    def write_contracts(self, count: int) -> None:
        self.write_json("runtime/evaluators.json", self.evaluator_contract(count))
        self.write_json(
            "runtime/artifacts.json",
            {
                "$schema": MODULE.ARTIFACT_SCHEMA,
                "schema_version": 1,
                "objective_id": "viral-game",
                "ready": True,
                "artifact_classes": [],
            },
        )
        self.write_json(
            "runtime/benchmarks.json",
            {
                "$schema": MODULE.BENCHMARK_SCHEMA,
                "schema_version": 1,
                "objective_id": "viral-game",
                "ready": True,
                "dimensions": [],
            },
        )

    def compile(self):
        return MODULE.compile_manifest(
            self.project,
            "runtime/evaluators.json",
            "runtime/artifacts.json",
            "runtime/benchmarks.json",
        )

    def test_missing_adapters_compile_bounded_build_fabric(self) -> None:
        result = self.compile()
        self.assertFalse(result["complete"])
        self.assertEqual(result["missing_evaluator_ids"], ["eval-0", "eval-1"])
        fabric = result["fabric"]
        self.assertEqual(len(fabric["managers"]), 1)
        self.assertEqual(len(fabric["managers"][0]["workers"]), 2)
        self.assertTrue(MODULE.fabric_module().validate(fabric)["valid"])
        task = fabric["managers"][0]["workers"][0]["task"]
        self.assertIn("Do not modify the product candidate", task)
        self.assertIn("interaction_trace", task)

    def test_existing_adapter_is_not_rebuilt(self) -> None:
        adapter = self.project / ".company-os/evaluators/eval-0/adapter.py"
        adapter.parent.mkdir(parents=True, exist_ok=True)
        adapter.write_text("print('{}')\n", encoding="utf-8")
        result = self.compile()
        self.assertEqual(result["missing_evaluator_ids"], ["eval-1"])

    def test_more_than_six_missing_adapters_are_batched(self) -> None:
        self.write_contracts(7)
        result = self.compile()
        self.assertEqual(len(result["missing_evaluator_ids"]), 6)
        self.assertEqual(result["remaining_evaluator_ids"], ["eval-6"])
        fabric = result["fabric"]
        self.assertEqual(len(fabric["managers"]), 2)
        self.assertTrue(all(len(manager["workers"]) == 3 for manager in fabric["managers"]))
        self.assertTrue(MODULE.fabric_module().validate(fabric)["valid"])

    def test_no_missing_adapters_returns_complete_without_fabric(self) -> None:
        for index in range(2):
            adapter = self.project / f".company-os/evaluators/eval-{index}/adapter.py"
            adapter.parent.mkdir(parents=True, exist_ok=True)
            adapter.write_text("print('{}')\n", encoding="utf-8")
        result = self.compile()
        self.assertTrue(result["complete"])
        self.assertIsNone(result["fabric"])

    def test_non_workspace_evaluator_is_not_downgraded(self) -> None:
        contract = self.evaluator_contract(1)
        contract["evaluators"][0]["adapter_locator"] = "tool://browser"
        self.write_json("runtime/evaluators.json", contract)
        with self.assertRaises(MODULE.BuildFabricError) as caught:
            self.compile()
        self.assertEqual(caught.exception.code, "E_UNBUILDABLE_LOCATOR")


if __name__ == "__main__":
    unittest.main()
