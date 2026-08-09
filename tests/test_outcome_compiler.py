from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "company-os" / "compile-outcome-contract" / "scripts" / "compile_outcome_contract.py"

spec = importlib.util.spec_from_file_location("compile_outcome_contract", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(MODULE)


def base_request() -> dict:
    return {
        "$schema": "company-os.outcome-request.v1",
        "objective_id": "viral-game",
        "objective": "Make a viral game.",
        "outcome_claims": [],
        "domain_hypotheses": [],
        "artifact_classes": [],
        "evaluators": [],
        "benchmarks": [],
        "unknowns": [
            {
                "unknown_id": "platform",
                "question": "Which runtime and platform constraints are mandatory?",
                "blocking": True,
                "resolved": False,
                "closure_evidence": ["platform_documentation"],
            }
        ],
        "reality_acceptance": None,
    }


class OutcomeCompilerTests(unittest.TestCase):
    def test_broad_objective_compiles_to_discovery_instead_of_failing_schema(self) -> None:
        contract = MODULE.compile_contract(base_request())
        self.assertEqual(contract["original_objective"], "Make a viral game.")
        self.assertEqual(contract["state"], "discovery_required")
        self.assertFalse(contract["scale_allowed"])
        self.assertTrue(any(item["code"] == "OUTCOME_UNDEFINED" for item in contract["blockers"]))
        self.assertTrue(any(item["discovery_id"] == "resolve-platform" for item in contract["discovery_agenda"]))

    def test_scale_requires_observable_artifacts_executable_evaluators_and_benchmarks(self) -> None:
        request = base_request()
        request["unknowns"][0]["resolved"] = True
        request["artifact_classes"] = [{
            "artifact_class_id": "playable-build",
            "label": "Playable build",
            "required": True,
            "observation_methods": ["launch_and_interact"],
        }]
        request["evaluators"] = [{
            "evaluator_id": "gameplay-evaluator",
            "label": "Gameplay evaluator",
            "required": True,
            "executable_methods": ["play_session"],
            "independent_role": True,
        }]
        request["benchmarks"] = [{
            "benchmark_id": "quality-reference",
            "dimension": "game_quality",
            "required": True,
            "references": ["reference://peer-game-1"],
        }]
        request["outcome_claims"] = [{
            "claim_id": "playable",
            "statement": "A player can launch and complete the core loop.",
            "evidence_bindings": ["playable-build", "gameplay-evaluator"],
        }]
        request["reality_acceptance"] = {
            "policy": "Fresh evaluator judges the artifact without production completion narrative.",
            "independent_from_production": True,
            "binds_original_objective": True,
        }

        contract = MODULE.compile_contract(request)
        self.assertEqual(contract["state"], "scale_allowed")
        self.assertTrue(contract["scale_allowed"])
        self.assertEqual(contract["blockers"], [])

    def test_unobservable_artifact_blocks_scale(self) -> None:
        request = base_request()
        request["unknowns"][0]["resolved"] = True
        request["outcome_claims"] = [{
            "claim_id": "exists",
            "statement": "The product exists.",
            "evidence_bindings": ["product"],
        }]
        request["artifact_classes"] = [{
            "artifact_class_id": "product",
            "label": "Product",
            "required": True,
            "observation_methods": [],
        }]
        request["evaluators"] = [{
            "evaluator_id": "review",
            "label": "Review",
            "required": True,
            "executable_methods": ["inspect"],
            "independent_role": True,
        }]
        request["benchmarks"] = [{
            "benchmark_id": "peer",
            "dimension": "quality",
            "required": True,
            "references": ["reference://peer"],
        }]
        request["reality_acceptance"] = {
            "policy": "Independent final review",
            "independent_from_production": True,
            "binds_original_objective": True,
        }

        contract = MODULE.compile_contract(request)
        self.assertFalse(contract["scale_allowed"])
        self.assertTrue(any(item["code"] == "UNOBSERVABLE_ARTIFACT" for item in contract["blockers"]))

    def test_verify_rejects_tampering(self) -> None:
        request = base_request()
        contract = MODULE.compile_contract(request)
        contract["scale_allowed"] = True
        with self.assertRaises(MODULE.OutcomeError) as ctx:
            MODULE.verify_contract(request, contract)
        self.assertEqual(ctx.exception.code, "E_MISMATCH")

    def test_cli_round_trip_is_canonical(self) -> None:
        request = base_request()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request_path = root / "request.json"
            output_path = root / "contract.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            compiled = MODULE.compile_contract(request)
            MODULE.write_json(output_path, compiled)
            candidate = json.loads(output_path.read_text(encoding="utf-8"))
            verified = MODULE.verify_contract(request, candidate)
            self.assertEqual(compiled, verified)


if __name__ == "__main__":
    unittest.main()
