from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "company-os" / "authorize-outcome-scale" / "scripts" / "authorize_outcome_scale.py"
spec = importlib.util.spec_from_file_location("authorize_outcome_scale", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(MODULE)


def stack() -> tuple[dict, dict, dict, dict, list[dict]]:
    objective_id = "viral-game"
    outcome = {
        "$schema": MODULE.OUTCOME_SCHEMA,
        "objective_id": objective_id,
        "scale_allowed": True,
    }
    artifacts = {
        "$schema": MODULE.ARTIFACT_SCHEMA,
        "objective_id": objective_id,
        "ready": True,
        "artifact_classes": [
            {
                "artifact_class_id": "playable-build",
                "required": True,
                "rich": True,
                "required_evidence": ["interaction_trace", "screenshot"],
            }
        ],
    }
    evaluators = {
        "$schema": MODULE.EVALUATOR_SCHEMA,
        "objective_id": objective_id,
        "ready": True,
        "evaluators": [
            {
                "evaluator_id": "gameplay",
                "required": True,
                "artifact_classes": ["playable-build"],
                "produces_evidence": ["interaction_trace", "screenshot"],
            }
        ],
    }
    benchmarks = {
        "$schema": MODULE.BENCHMARK_SCHEMA,
        "objective_id": objective_id,
        "ready": True,
    }
    calibrations = [
        {
            "$schema": MODULE.CALIBRATION_SCHEMA,
            "evaluator_id": "gameplay",
            "passed": True,
        }
    ]
    return outcome, artifacts, evaluators, benchmarks, calibrations


class OutcomeScaleAuthorizationTests(unittest.TestCase):
    def test_fully_closed_stack_authorizes_scale(self) -> None:
        receipt = MODULE.authorize(*stack())
        self.assertTrue(receipt["authorized"])
        self.assertEqual(receipt["blockers"], [])
        self.assertEqual(
            receipt["required_observation_evidence"]["playable-build"],
            ["interaction_trace", "screenshot"],
        )

    def test_failed_calibration_blocks_scale(self) -> None:
        outcome, artifacts, evaluators, benchmarks, calibrations = stack()
        calibrations[0]["passed"] = False
        receipt = MODULE.authorize(outcome, artifacts, evaluators, benchmarks, calibrations)
        self.assertFalse(receipt["authorized"])
        self.assertIn(
            "EVALUATOR_CALIBRATION_FAILED",
            {item["code"] for item in receipt["blockers"]},
        )

    def test_required_artifact_without_evaluator_coverage_blocks(self) -> None:
        outcome, artifacts, evaluators, benchmarks, calibrations = stack()
        evaluators["evaluators"][0]["artifact_classes"] = ["audio-mix"]
        receipt = MODULE.authorize(outcome, artifacts, evaluators, benchmarks, calibrations)
        self.assertFalse(receipt["authorized"])
        self.assertIn(
            "ARTIFACT_WITHOUT_EVALUATOR",
            {item["code"] for item in receipt["blockers"]},
        )

    def test_rich_artifact_required_evidence_must_be_covered(self) -> None:
        outcome, artifacts, evaluators, benchmarks, calibrations = stack()
        evaluators["evaluators"][0]["produces_evidence"] = ["screenshot"]
        receipt = MODULE.authorize(outcome, artifacts, evaluators, benchmarks, calibrations)
        self.assertFalse(receipt["authorized"])
        blockers = [
            item for item in receipt["blockers"]
            if item["code"] == "ARTIFACT_OBSERVATION_EVIDENCE_UNCOVERED"
        ]
        self.assertEqual(
            blockers,
            [{"code": "ARTIFACT_OBSERVATION_EVIDENCE_UNCOVERED", "detail": "playable-build:interaction_trace"}],
        )

    def test_objective_mismatch_rejects(self) -> None:
        outcome, artifacts, evaluators, benchmarks, calibrations = stack()
        benchmarks["objective_id"] = "different-objective"
        with self.assertRaises(MODULE.ScaleAuthorizationError) as ctx:
            MODULE.authorize(outcome, artifacts, evaluators, benchmarks, calibrations)
        self.assertEqual(ctx.exception.code, "E_OBJECTIVE_BINDING")


if __name__ == "__main__":
    unittest.main()
