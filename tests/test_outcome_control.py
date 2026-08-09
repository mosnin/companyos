from __future__ import annotations

import hashlib
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


CONTROL = load(
    "outcome_control",
    ROOT / "skills/company-os/elastic-company-os/scripts/outcome_control.py",
)
RUNTIME = load(
    "execute_evaluator",
    ROOT / "skills/company-os/execute-outcome-evaluator/scripts/execute_evaluator.py",
)
CALIBRATION = load(
    "calibrate_evaluator",
    ROOT / "skills/company-os/calibrate-outcome-evaluator/scripts/calibrate_evaluator.py",
)


def seal(value: dict, field: str, module=CONTROL) -> dict:
    result = dict(value)
    result[field] = module.digest({**result, field: None})
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
    "evidence": [{"evidence_id": f"trace-{run_id}", "evidence_type": "play_trace", "path": evidence.as_posix()}],
}))
'''


class OutcomeControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project_id = "project-a"
        self.program_version = 1
        self.work_id = "work-a"
        self.governed_outcome = "A player completes the core loop."
        self.objective_id = "viral-game"
        self.prepare_contracts_and_calibration()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, path: str, value: object) -> str:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def prepare_contracts_and_calibration(self) -> None:
        adapter = self.root / "evaluators/gameplay.py"
        adapter.parent.mkdir(parents=True)
        adapter.write_text(ADAPTER, encoding="utf-8")
        self.outcome = seal({
            "$schema": CONTROL.OUTCOME_SCHEMA,
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
            "outcome_claims": [{
                "claim_id": "playable",
                "statement": self.governed_outcome,
                "evidence_bindings": ["playable-build", "gameplay"],
            }],
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
        }, "contract_sha256")
        self.artifacts = seal({
            "$schema": CONTROL.ARTIFACT_SCHEMA,
            "schema_version": 1,
            "objective_id": self.objective_id,
            "artifact_classes": [{
                "artifact_class_id": "playable-build",
                "label": "Playable build",
                "required": True,
                "modalities": ["interactive", "visual", "audio", "executable"],
                "observation_methods": ["launch_build", "scripted_play_session"],
                "required_evidence": ["play_trace"],
                "rich": True,
            }],
            "blockers": [],
            "ready": True,
            "contract_sha256": None,
        }, "contract_sha256")
        self.evaluators = seal({
            "$schema": RUNTIME.CONTRACT_SCHEMA,
            "schema_version": 1,
            "objective_id": self.objective_id,
            "evaluators": [{
                "evaluator_id": "gameplay",
                "label": "Gameplay evaluator",
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
        self.benchmarks = seal({
            "$schema": RUNTIME.BENCHMARK_SCHEMA,
            "schema_version": 1,
            "objective_id": self.objective_id,
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
            "$schema": RUNTIME.REGISTRY_SCHEMA,
            "schema_version": 1,
            "adapters": [{
                "adapter_locator": "workspace://gameplay",
                "runtime": "python",
                "entrypoint": "evaluators/gameplay.py",
                "entrypoint_sha256": RUNTIME.file_digest(adapter),
                "timeout_seconds": 10,
                "max_output_bytes": 1048576,
                "arguments": [],
                "artifact_classes": ["playable-build"],
                "produces_evidence": ["play_trace"],
                "score_dimensions": ["fun", "polish"],
            }],
            "registry_sha256": None,
        }, "registry_sha256")
        self.write("outcome.json", self.outcome)
        self.write("artifacts.json", self.artifacts)
        self.write("evaluators.json", self.evaluators)
        self.write("benchmarks.json", self.benchmarks)
        self.write("registry.json", registry)
        candidate_paths = []
        for index, content in enumerate(("poor", "middle", "excellent"), 1):
            artifact = self.root / f"candidate-{index}.txt"
            artifact.write_text(content, encoding="utf-8")
            execution = RUNTIME.execute(self.root, {
                "$schema": RUNTIME.REQUEST_SCHEMA,
                "run_id": f"run-{index}",
                "objective_id": self.objective_id,
                "evaluator_id": "gameplay",
                "evaluator_contract_path": "evaluators.json",
                "adapter_registry_path": "registry.json",
                "benchmark_contract_path": "benchmarks.json",
                "executor_actor_id": "independent-reviewer",
                "production_actor_ids": ["builder", "manager"],
                "artifacts": [{
                    "artifact_id": f"candidate-{index}",
                    "artifact_class_id": "playable-build",
                    "path": artifact.name,
                    "sha256": RUNTIME.file_digest(artifact),
                }],
                "arguments": {},
            })
            path = self.write(f"receipts/candidate-{index}.json", execution)
            candidate_paths.append(path)
        calibration = CALIBRATION.calibrate(self.root, {
            "$schema": CALIBRATION.REQUEST_SCHEMA,
            "objective_id": self.objective_id,
            "evaluator_id": "gameplay",
            "required_dimensions": ["fun", "polish"],
            "candidates": [
                {"candidate_id": f"candidate-{index}", "expected_rank": index, "execution_receipt_path": path}
                for index, path in enumerate(candidate_paths, 1)
            ],
        })
        self.calibrations = [calibration]
        self.write("calibrations.json", self.calibrations)

    def manifest(self, lane: str = "pilot") -> dict:
        binding = {
            "$schema": CONTROL.BINDING_SCHEMA,
            "execution_lane": lane,
            "project_id": self.project_id,
            "program_version": self.program_version,
            "work_id": self.work_id,
            "governed_outcome": self.governed_outcome,
            "objective_id": self.objective_id,
            "outcome_contract_path": "outcome.json",
            "artifact_contract_path": "artifacts.json",
            "evaluator_contract_path": "evaluators.json",
            "benchmark_contract_path": "benchmarks.json",
            "calibration_receipts_path": "calibrations.json",
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
            authorization = seal({
                "$schema": CONTROL.AUTHORIZATION_SCHEMA,
                "schema_version": 1,
                "objective_id": self.objective_id,
                "authorized": True,
                "blockers": [],
                "required_artifact_classes": ["playable-build"],
                "required_evaluator_ids": ["gameplay"],
                "input_bindings": {
                    "outcome_sha256": CONTROL.digest(self.outcome),
                    "artifacts_sha256": CONTROL.digest(self.artifacts),
                    "evaluators_sha256": CONTROL.digest(self.evaluators),
                    "benchmarks_sha256": CONTROL.digest(self.benchmarks),
                    "calibrations_sha256": CONTROL.digest(self.calibrations),
                },
                "authorization_sha256": None,
            }, "authorization_sha256")
            binding["scale_authorization_path"] = self.write("authorization.json", authorization)
        return manifest

    def validate(self, manifest: dict) -> dict:
        return CONTROL.validate_manifest_binding(
            project_root=self.root,
            manifest=manifest,
            project_id=self.project_id,
            program_version=self.program_version,
            work_id=self.work_id,
            governed_outcome=self.governed_outcome,
        )

    def test_bounded_pilot_passes_with_execution_bound_calibration(self) -> None:
        state = self.validate(self.manifest("pilot"))
        self.assertEqual(state["execution_lane"], "pilot")
        self.assertTrue(state["calibration_receipts"][0]["execution_bound"])

    def test_pilot_cannot_hide_elastic_scale(self) -> None:
        manifest = self.manifest("pilot")
        manifest["max_total_workers"] = 7
        with self.assertRaises(CONTROL.OutcomeControlError) as caught:
            self.validate(manifest)
        self.assertEqual(caught.exception.code, "E_PILOT_SCALE")

    def test_production_scale_requires_execution_bound_authorization(self) -> None:
        state = self.validate(self.manifest("production_scale"))
        self.assertEqual(state["execution_lane"], "production_scale")
        self.assertTrue(state["scale_authorization"]["authorization_sha256"])

    def test_prefilled_calibration_json_is_rejected(self) -> None:
        fake = seal({
            "$schema": CONTROL.CALIBRATION_SCHEMA,
            "schema_version": 1,
            "evaluator_id": "gameplay",
            "candidate_count": 3,
            "required_dimensions": ["fun", "polish"],
            "pairwise_failures": [],
            "passed": True,
            "receipt_sha256": None,
        }, "receipt_sha256")
        self.write("calibrations.json", [fake])
        with self.assertRaises(CONTROL.OutcomeControlError) as caught:
            self.validate(self.manifest("pilot"))
        self.assertEqual(caught.exception.code, "E_CALIBRATION")

    def test_calibration_artifact_drift_invalidates_fabric(self) -> None:
        state = self.validate(self.manifest("pilot"))
        self.assertTrue(state["calibration_receipts"])
        (self.root / "candidate-1.txt").write_text("substituted", encoding="utf-8")
        with self.assertRaises(CONTROL.OutcomeControlError):
            self.validate(self.manifest("pilot"))

    def reality_receipt(self) -> dict:
        return seal({
            "$schema": CONTROL.REALITY_SCHEMA,
            "schema_version": 1,
            "objective_id": self.objective_id,
            "original_objective": "Make a viral game.",
            "original_objective_sha256": hashlib.sha256(b"Make a viral game.").hexdigest(),
            "claim_decisions": [{
                "claim_id": "playable",
                "statement": self.governed_outcome,
                "required": True,
                "passed": True,
                "artifact_evidence_count": 2,
                "evaluator_receipt_count": 1,
            }],
            "blockers": [],
            "accepted": True,
            "receipt_sha256": None,
        }, "receipt_sha256")

    def test_completion_requires_matching_reality_receipt(self) -> None:
        control = self.validate(self.manifest("pilot"))
        receipt_path = self.write("reality.json", self.reality_receipt())
        result = CONTROL.find_reality_receipt(
            project_root=self.root,
            evidence_by_id={"reality-evidence": {"id": "reality-evidence", "artifact_path": receipt_path}},
            evidence_ids=["reality-evidence"],
            outcome_control=control,
        )
        self.assertEqual(result["evidence_id"], "reality-evidence")


if __name__ == "__main__":
    unittest.main()
