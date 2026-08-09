from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "skills"
    / "company-os"
    / "elastic-company-os"
    / "scripts"
    / "outcome_control.py"
)
spec = importlib.util.spec_from_file_location("outcome_control", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(MODULE)


def seal(value: dict, field: str) -> dict:
    result = dict(value)
    result[field] = MODULE.digest({**result, field: None})
    return result


class OutcomeControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project_id = "project-a"
        self.program_version = 1
        self.work_id = "work-a"
        self.governed_outcome = "A player completes the core loop."
        self.objective_id = "viral-game"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, name: str, value: object) -> str:
        path = self.root / name
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return name

    def contracts(self) -> tuple[dict, dict, dict, dict, list[dict]]:
        outcome = seal(
            {
                "$schema": MODULE.OUTCOME_SCHEMA,
                "schema_version": 1,
                "objective_id": self.objective_id,
                "original_objective": "Make a viral game.",
                "request_sha256": "a" * 64,
                "state": "scale_allowed",
                "pilot_allowed": True,
                "scale_allowed": True,
                "blocking_unknown_count": 0,
                "blockers": [],
                "discovery_agenda": [],
                "outcome_claims": [
                    {
                        "claim_id": "playable",
                        "statement": self.governed_outcome,
                        "evidence_bindings": ["playable-build", "gameplay"],
                    }
                ],
                "domain_hypotheses": [],
                "artifact_classes": [],
                "evaluators": [],
                "benchmarks": [],
                "reality_acceptance": {
                    "policy": "Independent reality review",
                    "independent_from_production": True,
                    "binds_original_objective": True,
                },
                "contract_sha256": None,
            },
            "contract_sha256",
        )
        artifacts = seal(
            {
                "$schema": MODULE.ARTIFACT_SCHEMA,
                "schema_version": 1,
                "objective_id": self.objective_id,
                "artifact_classes": [
                    {
                        "artifact_class_id": "playable-build",
                        "label": "Playable build",
                        "required": True,
                        "modalities": ["interactive", "visual", "audio", "executable"],
                        "observation_methods": ["launch_build", "scripted_play_session"],
                        "required_evidence": ["play_trace", "video_capture"],
                        "rich": True,
                    }
                ],
                "blockers": [],
                "ready": True,
                "contract_sha256": None,
            },
            "contract_sha256",
        )
        evaluators = seal(
            {
                "$schema": MODULE.EVALUATOR_SCHEMA,
                "schema_version": 1,
                "objective_id": self.objective_id,
                "evaluators": [
                    {
                        "evaluator_id": "gameplay",
                        "label": "Gameplay evaluator",
                        "required": True,
                        "independent_role": True,
                        "research_only": False,
                        "adapter_locator": "tool://game/play",
                        "artifact_classes": ["playable-build"],
                        "produces_evidence": ["play_trace"],
                        "score_dimensions": ["fun", "polish"],
                    }
                ],
                "blockers": [],
                "ready": True,
                "contract_sha256": None,
            },
            "contract_sha256",
        )
        benchmarks = seal(
            {
                "$schema": MODULE.BENCHMARK_SCHEMA,
                "schema_version": 1,
                "objective_id": self.objective_id,
                "dimensions": [
                    {
                        "dimension_id": "polish",
                        "label": "Polish",
                        "required": True,
                        "references": [
                            {
                                "reference_id": "bad",
                                "locator": "reference://bad",
                                "provenance": "curated",
                                "quality_tier": "negative",
                            },
                            {
                                "reference_id": "great",
                                "locator": "reference://great",
                                "provenance": "curated",
                                "quality_tier": "exemplar",
                            },
                        ],
                    }
                ],
                "blockers": [],
                "ready": True,
                "contract_sha256": None,
            },
            "contract_sha256",
        )
        calibrations = [
            seal(
                {
                    "$schema": MODULE.CALIBRATION_SCHEMA,
                    "schema_version": 1,
                    "evaluator_id": "gameplay",
                    "candidate_count": 3,
                    "required_dimensions": ["fun", "polish"],
                    "pairwise_failures": [],
                    "passed": True,
                    "receipt_sha256": None,
                },
                "receipt_sha256",
            )
        ]
        return outcome, artifacts, evaluators, benchmarks, calibrations

    def manifest(self, lane: str = "pilot") -> dict:
        outcome, artifacts, evaluators, benchmarks, calibrations = self.contracts()
        paths = {
            "outcome_contract_path": self.write("outcome.json", outcome),
            "artifact_contract_path": self.write("artifacts.json", artifacts),
            "evaluator_contract_path": self.write("evaluators.json", evaluators),
            "benchmark_contract_path": self.write("benchmarks.json", benchmarks),
            "calibration_receipts_path": self.write("calibrations.json", calibrations),
        }
        binding = {
            "$schema": MODULE.BINDING_SCHEMA,
            "execution_lane": lane,
            "project_id": self.project_id,
            "program_version": self.program_version,
            "work_id": self.work_id,
            "governed_outcome": self.governed_outcome,
            "objective_id": self.objective_id,
            **paths,
            "scale_authorization_path": None,
        }
        manifest = {
            "program_id": self.project_id,
            "program_version": self.program_version,
            "outcome": self.governed_outcome,
            "max_managers": 2,
            "max_workers_per_manager": 3,
            "max_total_workers": 6,
            "max_manager_concurrency": 2,
            "managers": [
                {"id": "manager-a", "workers": [{"id": "worker-a"}]},
                {"id": "manager-b", "workers": [{"id": "worker-b"}]},
            ],
            "outcome_control": binding,
        }
        if lane == "production_scale":
            authorization = seal(
                {
                    "$schema": MODULE.AUTHORIZATION_SCHEMA,
                    "schema_version": 1,
                    "objective_id": self.objective_id,
                    "authorized": True,
                    "blockers": [],
                    "required_artifact_classes": ["playable-build"],
                    "required_evaluator_ids": ["gameplay"],
                    "input_bindings": {
                        "outcome_sha256": MODULE.digest(outcome),
                        "artifacts_sha256": MODULE.digest(artifacts),
                        "evaluators_sha256": MODULE.digest(evaluators),
                        "benchmarks_sha256": MODULE.digest(benchmarks),
                        "calibrations_sha256": MODULE.digest(calibrations),
                    },
                    "authorization_sha256": None,
                },
                "authorization_sha256",
            )
            binding["scale_authorization_path"] = self.write("authorization.json", authorization)
        return manifest

    def validate(self, manifest: dict) -> dict:
        return MODULE.validate_manifest_binding(
            project_root=self.root,
            manifest=manifest,
            project_id=self.project_id,
            program_version=self.program_version,
            work_id=self.work_id,
            governed_outcome=self.governed_outcome,
        )

    def test_bounded_pilot_passes_without_scale_authorization(self) -> None:
        state = self.validate(self.manifest("pilot"))
        self.assertEqual(state["execution_lane"], "pilot")
        self.assertIsNone(state["scale_authorization"]["authorization_sha256"])

    def test_pilot_cannot_hide_elastic_scale(self) -> None:
        manifest = self.manifest("pilot")
        manifest["max_total_workers"] = 7
        with self.assertRaises(MODULE.OutcomeControlError) as caught:
            self.validate(manifest)
        self.assertEqual(caught.exception.code, "E_PILOT_SCALE")

    def test_production_scale_requires_exact_content_bound_authorization(self) -> None:
        state = self.validate(self.manifest("production_scale"))
        self.assertEqual(state["execution_lane"], "production_scale")
        self.assertTrue(state["scale_authorization"]["authorization_sha256"])

    def test_production_scale_rejects_tampered_contract_after_authorization(self) -> None:
        manifest = self.manifest("production_scale")
        path = self.root / manifest["outcome_control"]["artifact_contract_path"]
        value = json.loads(path.read_text(encoding="utf-8"))
        value["ready"] = False
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(MODULE.OutcomeControlError) as caught:
            self.validate(manifest)
        self.assertIn(caught.exception.code, {"E_DIGEST", "E_ARTIFACT"})

    def reality_receipt(self) -> dict:
        return seal(
            {
                "$schema": MODULE.REALITY_SCHEMA,
                "schema_version": 1,
                "objective_id": self.objective_id,
                "original_objective": "Make a viral game.",
                "original_objective_sha256": __import__("hashlib").sha256(
                    b"Make a viral game."
                ).hexdigest(),
                "claim_decisions": [
                    {
                        "claim_id": "playable",
                        "statement": self.governed_outcome,
                        "required": True,
                        "passed": True,
                        "artifact_evidence_count": 2,
                        "evaluator_receipt_count": 1,
                    }
                ],
                "blockers": [],
                "accepted": True,
                "receipt_sha256": None,
            },
            "receipt_sha256",
        )

    def test_completion_requires_one_matching_reality_receipt(self) -> None:
        control = self.validate(self.manifest("pilot"))
        receipt_path = self.write("reality.json", self.reality_receipt())
        evidence = {
            "reality-evidence": {
                "id": "reality-evidence",
                "artifact_path": receipt_path,
            }
        }
        result = MODULE.find_reality_receipt(
            project_root=self.root,
            evidence_by_id=evidence,
            evidence_ids=["reality-evidence"],
            outcome_control=control,
        )
        self.assertEqual(result["evidence_id"], "reality-evidence")

    def test_mismatched_reality_receipt_fails(self) -> None:
        control = self.validate(self.manifest("pilot"))
        receipt = self.reality_receipt()
        receipt["objective_id"] = "other"
        receipt = seal(receipt, "receipt_sha256")
        with self.assertRaises(MODULE.OutcomeControlError) as caught:
            MODULE.validate_reality_receipt(receipt, control)
        self.assertEqual(caught.exception.code, "E_BINDING")


if __name__ == "__main__":
    unittest.main()
