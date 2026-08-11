from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BOOT = load(
    "bootstrap_outcome_under_test",
    ROOT / "skills/company-os/bootstrap-outcome/scripts/bootstrap_outcome.py",
)
SYN = load(
    "synthesize_outcome_under_test",
    ROOT / "skills/company-os/synthesize-outcome-model/scripts/synthesize_outcome_model.py",
)
FABRIC = load(
    "bootstrap_fabric_validator",
    ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_fabric.py",
)


class OutcomeDiscoveryBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = BOOT.seed_request("viral-game", "Make a viral game.")
        self.contract = BOOT.outcome_module().compile_contract(self.base)
        self.state = {
            "instance": {"project_id": "project-a"},
            "strategy": {
                "program_version": 3,
                "north_star": "Autonomous excellent outcomes",
                "constraints": ["No consequential external effects"],
                "non_goals": ["Production deployment during discovery"],
            },
        }

    def proposal(self, proposal_id: str) -> dict:
        return {
            "$schema": SYN.PROPOSAL_SCHEMA,
            "proposal_id": proposal_id,
            "objective_id": "viral-game",
            "request_sha256": SYN.digest(self.base),
            "sources": [f"https://example.com/{proposal_id}"],
            "unknown_resolutions": [],
            "domain_hypotheses": [],
            "outcome_claims": [],
            "artifact_classes": [],
            "evaluators": [],
            "benchmarks": [],
            "reality_acceptance": None,
        }

    def complete_proposals(self) -> list[dict]:
        domain = self.proposal("domain-truth")
        domain["unknown_resolutions"] = [
            {
                "unknown_id": "success-state",
                "conclusion": "A player can understand, play, and complete a rewarding core loop.",
                "citations": ["https://example.com/success"],
                "counterevidence": [],
                "reconciliation": None,
                "closure_evidence": ["cited_success_definition", "measurable_outcome_claims"],
            },
            {
                "unknown_id": "domain-constraints",
                "conclusion": "The target runtime and distribution surface impose input, packaging, and performance constraints.",
                "citations": ["https://example.com/platform"],
                "counterevidence": ["https://example.com/counter"],
                "reconciliation": "The primary platform requirements control the target release while the conflicting source described a different runtime.",
                "closure_evidence": ["primary_domain_sources", "constraint_summary", "counterevidence_review"],
            },
        ]
        domain["domain_hypotheses"] = [
            {
                "domain_id": "target-runtime",
                "hypothesis": "The target runtime requires a responsive packaged interactive build.",
                "status": "supported",
                "source_bindings": ["https://example.com/platform"],
            }
        ]
        domain["outcome_claims"] = [
            {
                "claim_id": "playable",
                "statement": "A player can complete the core interaction loop on the target runtime.",
                "evidence_bindings": ["playable_game", "gameplay-evaluator", "gameplay-quality"],
                "citations": ["https://example.com/success"],
            }
        ]

        quality = self.proposal("artifact-quality")
        quality["unknown_resolutions"] = [
            {
                "unknown_id": "artifact-reality",
                "conclusion": "A real playable build must exist and be exercised through interaction traces and rendered frames.",
                "citations": ["https://example.com/artifacts"],
                "counterevidence": [],
                "reconciliation": None,
                "closure_evidence": ["artifact_classes", "observation_methods", "required_evidence_types"],
            },
            {
                "unknown_id": "quality-bar",
                "conclusion": "Quality requires benchmarked gameplay, visual quality, responsiveness, and reward feedback.",
                "citations": ["https://example.com/quality"],
                "counterevidence": [],
                "reconciliation": None,
                "closure_evidence": ["benchmark_set", "quality_dimensions", "failure_signatures"],
            },
            {
                "unknown_id": "evaluator-runtime",
                "conclusion": "An independent evaluator must play the build and emit interaction and screenshot evidence with gameplay and visual scores.",
                "citations": ["https://example.com/evaluation"],
                "counterevidence": [],
                "reconciliation": None,
                "closure_evidence": ["evaluator_methods", "independent_roles", "evidence_outputs"],
            },
            {
                "unknown_id": "reality-acceptance",
                "conclusion": "A fresh independent judge must compare the actual candidate with the original objective and reject production narrative as evidence.",
                "citations": ["https://example.com/acceptance"],
                "counterevidence": [],
                "reconciliation": None,
                "closure_evidence": ["independent_acceptance_policy", "original_objective_binding"],
            },
        ]
        quality["artifact_classes"] = [
            {
                "artifact_class_id": "playable_game",
                "label": "Playable game",
                "required": True,
                "modalities": ["interactive", "visual", "executable"],
                "observation_methods": ["play_session", "rendered_frame_inspection"],
                "required_evidence": ["interaction_trace", "screenshot"],
                "citations": ["https://example.com/artifacts"],
            }
        ]
        quality["evaluators"] = [
            {
                "evaluator_id": "gameplay-evaluator",
                "label": "Independent gameplay evaluator",
                "required": True,
                "independent_role": True,
                "executable_methods": ["play_candidate"],
                "artifact_classes": ["playable_game"],
                "produces_evidence": ["interaction_trace", "screenshot"],
                "score_dimensions": ["gameplay", "visual_quality"],
                "citations": ["https://example.com/evaluation"],
            }
        ]
        quality["benchmarks"] = [
            {
                "benchmark_id": "gameplay-quality",
                "dimension": "gameplay and visual quality",
                "required": True,
                "citations": ["https://example.com/quality"],
                "references": [
                    {
                        "reference_id": "weak-example",
                        "locator": "https://example.com/weak",
                        "quality_tier": "negative",
                        "provenance": "Observed weak comparison candidate",
                        "citations": ["https://example.com/weak"],
                    },
                    {
                        "reference_id": "excellent-example",
                        "locator": "https://example.com/excellent",
                        "quality_tier": "exemplar",
                        "provenance": "Observed high quality comparison candidate",
                        "citations": ["https://example.com/excellent"],
                    },
                ],
            }
        ]
        quality["reality_acceptance"] = {
            "policy": "Judge the actual playable candidate against the original objective using independent artifact and evaluator evidence.",
            "independent_from_production": True,
            "binds_original_objective": True,
            "citations": ["https://example.com/acceptance"],
        }
        return [domain, quality]

    def test_one_sentence_seeds_blocking_unknowns_without_user_vocabulary(self) -> None:
        self.assertEqual(self.base["objective"], "Make a viral game.")
        self.assertEqual(len(self.base["unknowns"]), 6)
        self.assertTrue(all(item["blocking"] for item in self.base["unknowns"]))
        self.assertEqual(self.contract["state"], "discovery_required")

    def test_bootstrap_compiles_two_managers_with_concurrent_reality_spike(self) -> None:
        manifest = BOOT.discovery_manifest(
            self.state,
            self.base,
            self.contract,
            ".company-os/outcomes/viral-game",
        )
        result = FABRIC.validate(manifest)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(len(manifest["managers"]), 2)
        tasks = [worker["task"] for manager in manifest["managers"] for worker in manager["workers"]]
        self.assertEqual(sum(len(manager["workers"]) for manager in manifest["managers"]), 3)
        self.assertTrue(any("success and domain truth" in task for task in tasks))
        self.assertTrue(any("artifact and quality system" in task for task in tasks))
        self.assertTrue(any("reversible reality spike" in task for task in tasks))

    def test_complete_cited_proposals_synthesize_measurable_outcome(self) -> None:
        request, contract = SYN.synthesize(self.base, self.complete_proposals())
        self.assertEqual(contract["state"], "scale_allowed")
        self.assertTrue(contract["scale_allowed"])
        self.assertEqual(contract["blockers"], [])
        self.assertTrue(all(item["resolved"] for item in request["unknowns"]))
        self.assertEqual(request["artifact_classes"][0]["required_evidence"], ["interaction_trace", "screenshot"])
        self.assertEqual(request["evaluators"][0]["adapter_locator"], "workspace://.company-os/evaluators/gameplay-evaluator/adapter.py")

    def test_missing_unknown_resolution_fails_instead_of_guessing(self) -> None:
        proposals = self.complete_proposals()
        proposals[1]["unknown_resolutions"] = [
            item for item in proposals[1]["unknown_resolutions"]
            if item["unknown_id"] != "evaluator-runtime"
        ]
        with self.assertRaises(SYN.SynthesisError) as caught:
            SYN.synthesize(self.base, proposals)
        self.assertEqual(caught.exception.code, "E_INCOMPLETE")

    def test_conflicting_claims_require_specific_reconciliation(self) -> None:
        proposals = self.complete_proposals()
        conflicting = self.proposal("conflicting-domain")
        conflicting["outcome_claims"] = [
            {
                "claim_id": "playable",
                "statement": "A static progress bar counts as the core interaction loop.",
                "evidence_bindings": ["playable_game", "gameplay-evaluator", "gameplay-quality"],
                "citations": ["https://example.com/conflict"],
            }
        ]
        with self.assertRaises(SYN.SynthesisError) as caught:
            SYN.synthesize(self.base, proposals + [conflicting])
        self.assertEqual(caught.exception.code, "E_CONFLICT")


if __name__ == "__main__":
    unittest.main()
