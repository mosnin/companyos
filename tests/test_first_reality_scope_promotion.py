from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/elastic-company-os/scripts/outcome_loop.py"
spec = importlib.util.spec_from_file_location("first_reality_scope_promotion", SCRIPT)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


def write_contract(root: Path, name: str, value: dict) -> dict:
    payload = dict(value)
    payload["contract_sha256"] = None
    payload["contract_sha256"] = MODULE.digest(payload)
    path = root / name
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "path": name,
        "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "contract_sha256": payload["contract_sha256"],
    }


class FirstRealityScopePromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.outcome = write_contract(
            self.root,
            "outcome.json",
            {"$schema": MODULE.OUTCOME_SCHEMA, "objective_id": "obj", "outcome_claims": []},
        )
        self.evaluators = write_contract(
            self.root,
            "evaluators.json",
            {
                "$schema": MODULE.EVALUATOR_SCHEMA,
                "objective_id": "obj",
                "evaluators": [
                    {
                        "evaluator_id": "judge",
                        "required": True,
                        "artifact_classes": ["browser_path", "billing"],
                        "score_dimensions": ["correctness"],
                    }
                ],
            },
        )
        self.benchmarks = write_contract(
            self.root,
            "benchmarks.json",
            {"$schema": MODULE.BENCHMARK_SCHEMA, "objective_id": "obj"},
        )
        self.pilot_artifacts = write_contract(
            self.root,
            "pilot-artifacts.json",
            {
                "$schema": MODULE.ARTIFACT_SCHEMA,
                "objective_id": "obj",
                "artifact_classes": [
                    {"artifact_class_id": "browser_path", "required": True}
                ],
            },
        )
        self.final_artifacts = write_contract(
            self.root,
            "final-artifacts.json",
            {
                "$schema": MODULE.ARTIFACT_SCHEMA,
                "objective_id": "obj",
                "artifact_classes": [
                    {"artifact_class_id": "browser_path", "required": True},
                    {"artifact_class_id": "billing", "required": True},
                ],
            },
        )
        calibrations = self.root / "calibrations.json"
        calibrations.write_text("[]\n", encoding="utf-8")
        self.calibration_binding = {
            "path": "calibrations.json",
            "file_sha256": hashlib.sha256(calibrations.read_bytes()).hexdigest(),
            "receipts_sha256": MODULE.digest([]),
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def control(self, lane: str, artifacts: dict) -> dict:
        value = {
            "$schema": MODULE.CONTROL_SCHEMA,
            "schema_version": 1,
            "execution_lane": lane,
            "project_id": "project",
            "program_version": 1,
            "work_id": "work",
            "governed_outcome": "Build the real product.",
            "objective_id": "obj",
            "original_objective": "Build the real product.",
            "outcome": self.outcome,
            "artifacts": artifacts,
            "evaluators": self.evaluators,
            "benchmarks": self.benchmarks,
            "calibrations": self.calibration_binding,
            "calibration_receipts": [],
            "scale_authorization": {
                "path": None if lane == "pilot" else "scale.json",
                "file_sha256": None if lane == "pilot" else "a" * 64,
                "authorization_sha256": None if lane == "pilot" else "b" * 64,
            },
            "state_sha256": None,
        }
        value["state_sha256"] = MODULE.digest(value)
        return value

    def test_connected_pilot_expands_to_final_scope_without_discarding_candidate(self) -> None:
        initial = MODULE.start(
            {
                "$schema": MODULE.REQUEST_SCHEMA,
                "objective_id": "obj",
                "original_objective": "Build the real product.",
            }
        )
        bound = MODULE.bind_control(
            self.root,
            initial,
            self.control("pilot", self.pilot_artifacts),
        )
        pilot_candidate = {
            "candidate_id": "candidate-1",
            "iteration": 1,
            "production_actor_ids": ["worker"],
            "artifact_bindings": [],
            "artifacts": [],
            "candidate_sha256": "c" * 64,
        }
        evaluating = MODULE.seal(
            {
                **bound,
                "phase": "evaluate",
                "candidates": [pilot_candidate],
                "iteration": 1,
            }
        )
        expanded = MODULE.refresh_control(
            self.root,
            evaluating,
            self.control("production_scale", self.final_artifacts),
        )
        self.assertEqual(expanded["phase"], "build_candidate")
        self.assertEqual(expanded["required_artifact_classes"], ["billing", "browser_path"])
        self.assertEqual(expanded["next_action"]["preserve_candidate_id"], "candidate-1")
        self.assertEqual(expanded["history"][-1]["event"], "first_reality_scope_expanded")
        self.assertEqual(
            sorted(
                artifact
                for lane in expanded["organization_plan"]["production_lanes"]
                for artifact in lane["artifact_classes"]
            ),
            ["billing", "browser_path"],
        )

    def test_final_scope_cannot_remove_first_reality_artifact(self) -> None:
        invalid = write_contract(
            self.root,
            "invalid-final.json",
            {
                "$schema": MODULE.ARTIFACT_SCHEMA,
                "objective_id": "obj",
                "artifact_classes": [
                    {"artifact_class_id": "billing", "required": True}
                ],
            },
        )
        initial = MODULE.start(
            {
                "$schema": MODULE.REQUEST_SCHEMA,
                "objective_id": "obj",
                "original_objective": "Build the real product.",
            }
        )
        bound = MODULE.bind_control(
            self.root,
            initial,
            self.control("pilot", self.pilot_artifacts),
        )
        evaluating = MODULE.seal({**bound, "phase": "evaluate"})
        with self.assertRaises(MODULE.OutcomeLoopError) as caught:
            MODULE.refresh_control(
                self.root,
                evaluating,
                self.control("production_scale", invalid),
            )
        self.assertEqual(caught.exception.code, "E_BINDING")


if __name__ == "__main__":
    unittest.main()
