from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/company-os/evaluate-company-evidence"
MODULE_PATH = SKILL_ROOT / "scripts/evaluator_evidence_registry.py"
DECISIONS_PATH = SKILL_ROOT / "references/evaluation-method-decisions.json"
REGISTRY_PATH = SKILL_ROOT / "references/evaluator-evidence-registry.json"
SOURCE_PATH = ROOT / "skills/company-os/source-intelligence/references/source-intelligence-registry.json"
SPEC = importlib.util.spec_from_file_location("evaluator_evidence_registry", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
sys.modules["evaluator_evidence_registry"] = MODULE


class EvaluatorEvidenceRegistryTests(unittest.TestCase):
    def values(self) -> tuple[dict, dict, dict]:
        return tuple(
            json.loads(path.read_text(encoding="utf-8"))
            for path in (DECISIONS_PATH, SOURCE_PATH, REGISTRY_PATH)
        )

    def test_registry_is_canonical_reproducible_and_covers_evaluation_family(self) -> None:
        decisions, sources, registry = self.values()
        self.assertEqual(REGISTRY_PATH.read_bytes(), MODULE.canonical_bytes(registry))
        rebuilt = MODULE.build_registry(decisions, sources)
        self.assertEqual(MODULE.canonical_bytes(rebuilt), REGISTRY_PATH.read_bytes())
        evidence = MODULE.validate_registry(registry, sources)
        self.assertEqual(evidence["method_count"], 8)
        self.assertEqual(evidence["source_family_count"], 8)
        self.assertFalse(evidence["execution_authorized"])

    def test_methods_are_research_only_and_cannot_score_or_execute(self) -> None:
        _, _, registry = self.values()
        self.assertFalse(registry["policy"]["research_methods_execute"])
        self.assertFalse(registry["policy"]["research_methods_score"])
        self.assertTrue(registry["policy"]["judge_failure_is_invalid_evidence"])
        self.assertTrue(all(record["status"] == "research_method_only" for record in registry["records"]))

    def test_resolution_exposes_missing_stage_instead_of_inventing_an_evaluator(self) -> None:
        _, sources, registry = self.values()
        code = MODULE.resolve(
            registry,
            sources,
            ["code"],
            ["deterministic_floor", "sealed_challenge", "transfer"],
        )
        self.assertEqual(
            code["research_covered_stages"],
            ["deterministic_floor", "sealed_challenge", "transfer"],
        )
        self.assertEqual(
            code["missing_ready_stages"],
            ["deterministic_floor", "sealed_challenge", "transfer"],
        )
        self.assertEqual(code["ready_evaluator_stages"], [])
        self.assertFalse(code["execution_authorized"])
        voice = MODULE.resolve(registry, sources, ["voice"], ["sealed_challenge"])
        self.assertEqual(voice["research_methods"], [])
        self.assertEqual(voice["missing_ready_stages"], ["sealed_challenge"])

    def test_source_policy_and_method_tampering_fail_closed(self) -> None:
        _, sources, registry = self.values()
        mutations = []
        value = copy.deepcopy(registry)
        value["source_intelligence_registry_sha256"] = "0" * 64
        mutations.append((value, "E_BINDING"))
        value = copy.deepcopy(registry)
        value["policy"]["research_methods_score"] = True
        mutations.append((value, "E_POLICY"))
        value = copy.deepcopy(registry)
        value["records"][0]["source_bindings"][0]["pin"] = "0" * 40
        mutations.append((value, "E_BINDING"))
        value = copy.deepcopy(registry)
        value["records"][0]["method_sha256"] = "0" * 64
        mutations.append((value, "E_BINDING"))
        value = copy.deepcopy(registry)
        value["records"][0]["status"] = "ready"
        mutations.append((value, "E_AUTHORITY"))
        value = copy.deepcopy(registry)
        value["records"][0]["mechanism_evidence_sha256"] = "0" * 64
        mutations.append((value, "E_EVIDENCE"))
        for mutation, code in mutations:
            with self.subTest(code=code):
                with self.assertRaises(MODULE.EvaluatorRegistryError) as ctx:
                    MODULE.validate_registry(mutation, sources)
                self.assertEqual(ctx.exception.code, code)

    def test_builder_rejects_source_family_omission_and_duplicate_method(self) -> None:
        decisions, sources, _ = self.values()
        omitted = copy.deepcopy(decisions)
        omitted["decisions"] = [
            item for item in omitted["decisions"]
            if item["method_id"] != "private-rotating-challenge-design"
        ]
        with self.assertRaises(MODULE.EvaluatorRegistryError) as ctx:
            MODULE.build_registry(omitted, sources)
        self.assertEqual(ctx.exception.code, "E_COVERAGE")
        duplicate = copy.deepcopy(decisions)
        duplicate["decisions"].append(copy.deepcopy(duplicate["decisions"][0]))
        with self.assertRaises(MODULE.EvaluatorRegistryError) as ctx:
            MODULE.build_registry(duplicate, sources)
        self.assertEqual(ctx.exception.code, "E_COVERAGE")

    def test_verifier_rejects_invalid_source_substitution_and_stage_loss(self) -> None:
        _, sources, registry = self.values()
        invalid = copy.deepcopy(registry)
        record = invalid["records"][0]
        record["source_intelligence_ids"] = ["aeon-placeholder"]
        record["source_bindings"] = [{
            "source_intelligence_id": "aeon-placeholder",
            "pin": None,
            "review_evidence_sha256": next(
                item["review_evidence_sha256"]
                for item in sources["records"]
                if item["source_id"] == "aeon-placeholder"
            ),
        }]
        unsigned = {key: record[key] for key in MODULE.RECORD_KEYS - {"method_sha256"}}
        record["method_sha256"] = MODULE.canonical_digest(unsigned)
        with self.assertRaises(MODULE.EvaluatorRegistryError) as ctx:
            MODULE.validate_registry(invalid, sources)
        self.assertEqual(ctx.exception.code, "E_SOURCE")

        stage_loss = copy.deepcopy(registry)
        sealed = next(item for item in stage_loss["records"] if item["stage"] == "sealed_challenge")
        sealed["stage"] = "adaptive_validation"
        unsigned = {key: sealed[key] for key in MODULE.RECORD_KEYS - {"method_sha256"}}
        sealed["method_sha256"] = MODULE.canonical_digest(unsigned)
        with self.assertRaises(MODULE.EvaluatorRegistryError) as ctx:
            MODULE.validate_registry(stage_loss, sources)
        self.assertEqual(ctx.exception.code, "E_COVERAGE")


if __name__ == "__main__":
    unittest.main()
