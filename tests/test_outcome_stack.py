from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/materialize-outcome-stack/scripts/materialize_outcome_stack.py"
spec = importlib.util.spec_from_file_location("materialize_outcome_stack_under_test", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(MODULE)


def outcome_request() -> dict:
    return {
        "$schema": MODULE.OUTCOME_REQUEST_SCHEMA,
        "objective_id": "viral-game",
        "objective": "Make a viral game.",
        "artifact_classes": [
            {
                "artifact_class_id": "playable_game",
                "label": "Playable game",
                "required": True,
                "modalities": ["interactive", "visual", "executable"],
                "observation_methods": ["play_session", "rendered_frame_inspection"],
                "required_evidence": ["interaction_trace", "screenshot"],
            }
        ],
        "evaluators": [
            {
                "evaluator_id": "gameplay-evaluator",
                "label": "Independent gameplay evaluator",
                "required": True,
                "independent_role": True,
                "research_only": False,
                "adapter_locator": "workspace://.company-os/evaluators/gameplay-evaluator/adapter.py",
                "artifact_classes": ["playable_game"],
                "produces_evidence": ["interaction_trace", "screenshot"],
                "score_dimensions": ["gameplay", "visual_quality"],
            }
        ],
        "benchmarks": [
            {
                "benchmark_id": "gameplay-quality",
                "dimension": "Gameplay and visual quality",
                "required": True,
                "reference_records": [
                    {
                        "reference_id": "bad",
                        "locator": "https://example.com/bad",
                        "quality_tier": "negative",
                        "provenance": "Known weak candidate",
                    },
                    {
                        "reference_id": "excellent",
                        "locator": "https://example.com/excellent",
                        "quality_tier": "exemplar",
                        "provenance": "Known excellent candidate",
                    },
                ],
            }
        ],
    }


class OutcomeStackTests(unittest.TestCase):
    def test_measurable_outcome_compiles_all_runtime_contracts(self) -> None:
        stack = MODULE.compile_stack(outcome_request())
        self.assertTrue(stack["contracts"]["artifact"]["ready"])
        self.assertTrue(stack["contracts"]["evaluator"]["ready"])
        self.assertTrue(stack["contracts"]["benchmark"]["ready"])
        self.assertEqual(
            stack["contracts"]["artifact"]["artifact_classes"][0]["required_evidence"],
            ["interaction_trace", "screenshot"],
        )
        self.assertEqual(
            stack["contracts"]["evaluator"]["evaluators"][0]["produces_evidence"],
            ["interaction_trace", "screenshot"],
        )
        self.assertEqual(
            [
                item["quality_tier"]
                for item in stack["contracts"]["benchmark"]["dimensions"][0]["references"]
            ],
            ["negative", "exemplar"],
        )

    def test_runtime_translation_preserves_adapter_location(self) -> None:
        stack = MODULE.compile_stack(outcome_request())
        self.assertEqual(
            stack["contracts"]["evaluator"]["evaluators"][0]["adapter_locator"],
            "workspace://.company-os/evaluators/gameplay-evaluator/adapter.py",
        )

    def test_unsupported_benchmark_tier_fails_instead_of_silent_rename(self) -> None:
        request = outcome_request()
        request["benchmarks"][0]["reference_records"][0]["quality_tier"] = "weak"
        with self.assertRaises(MODULE.StackError) as caught:
            MODULE.compile_stack(request)
        self.assertEqual(caught.exception.code, "E_BENCHMARK_TIER")

    def test_missing_structured_reference_records_fails(self) -> None:
        request = outcome_request()
        request["benchmarks"][0].pop("reference_records")
        with self.assertRaises(MODULE.StackError) as caught:
            MODULE.compile_stack(request)
        self.assertEqual(caught.exception.code, "E_INCOMPLETE")

    def test_missing_required_evaluator_evidence_is_not_downgraded(self) -> None:
        request = outcome_request()
        request["evaluators"][0]["produces_evidence"] = []
        with self.assertRaises(MODULE.StackError) as caught:
            MODULE.compile_stack(request)
        self.assertEqual(caught.exception.code, "E_NOT_READY")


if __name__ == "__main__":
    unittest.main()
