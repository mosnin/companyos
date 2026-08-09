from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load(
    "execute_evaluator",
    ROOT / "skills/company-os/execute-outcome-evaluator/scripts/execute_evaluator.py",
)
calibration = load(
    "calibrate_evaluator",
    ROOT / "skills/company-os/calibrate-outcome-evaluator/scripts/calibrate_evaluator.py",
)


def seal(value: dict, field: str) -> dict:
    result = dict(value)
    result[field] = runtime.digest({**result, field: None})
    return result


ADAPTER = r'''#!/usr/bin/env python3
import json
from pathlib import Path
import sys

request = json.loads(sys.stdin.read())
content = Path(request["artifacts"][0]["resolved_path"]).read_text().strip()
score = {"poor": 2.0, "middle": 6.0, "excellent": 9.0}[content]
run_id = request["run_id"]
evidence = Path("evidence") / f"{run_id}.json"
evidence.parent.mkdir(exist_ok=True)
evidence.write_text(json.dumps({"content": content}))
print(json.dumps({
    "$schema": "company-os.evaluator-adapter-output.v1",
    "run_id": run_id,
    "objective_id": request["objective_id"],
    "evaluator_id": request["evaluator_id"],
    "accepted": content == "excellent",
    "scores": {"fun": score, "polish": score},
    "findings": [],
    "evidence": [{"evidence_id": f"evidence-{run_id}", "evidence_type": "play_trace", "path": evidence.as_posix()}],
}))
'''


class ExecutionBoundCalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        adapter = self.root / "evaluators/gameplay.py"
        adapter.parent.mkdir()
        adapter.write_text(ADAPTER)
        evaluator = seal({
            "$schema": runtime.CONTRACT_SCHEMA,
            "schema_version": 1,
            "objective_id": "viral-game",
            "evaluators": [{
                "evaluator_id": "gameplay",
                "label": "Gameplay",
                "required": True,
                "independent_role": True,
                "research_only": False,
                "adapter_locator": "workspace://gameplay",
                "artifact_classes": ["playable-build"],
                "produces_evidence": ["play_trace"],
                "score_dimensions": ["fun", "polish"],
            }],
            "blockers": [],
            "ready": True,
            "contract_sha256": None,
        }, "contract_sha256")
        benchmark = seal({
            "$schema": runtime.BENCHMARK_SCHEMA,
            "schema_version": 1,
            "objective_id": "viral-game",
            "dimensions": [{
                "dimension_id": "polish",
                "label": "Polish",
                "required": True,
                "references": [
                    {"reference_id": "bad", "locator": "reference://bad", "provenance": "curated", "quality_tier": "negative"},
                    {"reference_id": "great", "locator": "reference://great", "provenance": "curated", "quality_tier": "exemplar"},
                ],
            }],
            "blockers": [],
            "ready": True,
            "contract_sha256": None,
        }, "contract_sha256")
        registry = seal({
            "$schema": runtime.REGISTRY_SCHEMA,
            "schema_version": 1,
            "adapters": [{
                "adapter_locator": "workspace://gameplay",
                "runtime": "python",
                "entrypoint": "evaluators/gameplay.py",
                "entrypoint_sha256": runtime.file_digest(adapter),
                "timeout_seconds": 10,
                "max_output_bytes": 1048576,
                "arguments": [],
                "artifact_classes": ["playable-build"],
                "produces_evidence": ["play_trace"],
                "score_dimensions": ["fun", "polish"],
            }],
            "registry_sha256": None,
        }, "registry_sha256")
        self.write("evaluator.json", evaluator)
        self.write("benchmark.json", benchmark)
        self.write("registry.json", registry)
        self.paths = []
        for index, content in enumerate(("poor", "middle", "excellent"), 1):
            artifact = self.root / f"candidate-{index}.txt"
            artifact.write_text(content)
            request = {
                "$schema": runtime.REQUEST_SCHEMA,
                "run_id": f"run-{index}",
                "objective_id": "viral-game",
                "evaluator_id": "gameplay",
                "evaluator_contract_path": "evaluator.json",
                "adapter_registry_path": "registry.json",
                "benchmark_contract_path": "benchmark.json",
                "executor_actor_id": "independent",
                "production_actor_ids": ["builder"],
                "artifacts": [{
                    "artifact_id": f"candidate-{index}",
                    "artifact_class_id": "playable-build",
                    "path": artifact.name,
                    "sha256": runtime.file_digest(artifact),
                }],
                "arguments": {},
            }
            receipt = runtime.execute(self.root, request)
            path = f"receipts/candidate-{index}.json"
            self.write(path, receipt)
            self.paths.append(path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, path: str, value: object) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")

    def request(self) -> dict:
        return {
            "$schema": calibration.REQUEST_SCHEMA,
            "objective_id": "viral-game",
            "evaluator_id": "gameplay",
            "required_dimensions": ["fun", "polish"],
            "candidates": [
                {"candidate_id": f"candidate-{index}", "expected_rank": index, "execution_receipt_path": path}
                for index, path in enumerate(self.paths, 1)
            ],
        }

    def test_calibration_is_derived_from_verified_executions(self) -> None:
        receipt = calibration.calibrate(self.root, self.request())
        self.assertTrue(receipt["passed"])
        self.assertTrue(receipt["execution_bound"])
        self.assertEqual(receipt["schema_version"], 2)
        self.assertTrue(calibration.verify_receipt(self.root, receipt)["passed"])

    def test_prefilled_scores_are_not_accepted_as_input(self) -> None:
        request = self.request()
        request["candidates"][0]["scores"] = {"fun": 10, "polish": 10}
        with self.assertRaises(calibration.CalibrationError) as caught:
            calibration.calibrate(self.root, request)
        self.assertEqual(caught.exception.code, "E_SCHEMA")

    def test_execution_receipt_drift_invalidates_calibration(self) -> None:
        receipt = calibration.calibrate(self.root, self.request())
        artifact = self.root / "candidate-1.txt"
        artifact.write_text("substituted")
        with self.assertRaises(calibration.CalibrationError):
            calibration.verify_receipt(self.root, receipt)

    def test_reusing_execution_receipt_is_rejected(self) -> None:
        request = self.request()
        request["candidates"][1]["execution_receipt_path"] = self.paths[0]
        with self.assertRaises(calibration.CalibrationError) as caught:
            calibration.calibrate(self.root, request)
        self.assertEqual(caught.exception.code, "E_DUPLICATE")

    def test_inverted_evaluator_scores_fail_calibration(self) -> None:
        receipt_path = self.root / self.paths[2]
        receipt = json.loads(receipt_path.read_text())
        receipt["scores"] = {"fun": 1.0, "polish": 1.0}
        receipt["receipt_sha256"] = runtime.digest({**receipt, "receipt_sha256": None})
        receipt_path.write_text(json.dumps(receipt))
        result = calibration.calibrate(self.root, self.request())
        self.assertFalse(result["passed"])
        self.assertTrue(result["pairwise_failures"])


if __name__ == "__main__":
    unittest.main()
