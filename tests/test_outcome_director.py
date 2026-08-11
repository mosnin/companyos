from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/direct-outcome/scripts/direct_outcome.py"
spec = importlib.util.spec_from_file_location("direct_outcome_under_test", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(MODULE)


class FakeBootstrap:
    @staticmethod
    def bootstrap(project_root, objective_id, objective):
        base = project_root / ".company-os/outcomes" / MODULE.slug(objective_id)
        base.mkdir(parents=True, exist_ok=True)
        request = {"$schema": "company-os.outcome-request.v1", "objective_id": objective_id, "objective": objective}
        (base / "outcome-request.json").write_text(json.dumps(request) + "\n")
        (base / "outcome-contract.json").write_text("{}\n")
        (base / "outcome-loop.json").write_text(json.dumps({"$schema": "company-os.outcome-loop-state.v1", "phase": "discovery"}) + "\n")
        (base / "discovery-fabric.json").write_text("{}\n")
        receipt_path = base / "bootstrap-receipt.json"
        receipt_path.write_text("{}\n")
        return {
            "receipt_sha256": "a" * 64,
            "paths": {
                "request": MODULE.relative(project_root, base / "outcome-request.json"),
                "contract": MODULE.relative(project_root, base / "outcome-contract.json"),
                "loop_state": MODULE.relative(project_root, base / "outcome-loop.json"),
                "discovery_fabric": MODULE.relative(project_root, base / "discovery-fabric.json"),
                "receipt": MODULE.relative(project_root, receipt_path),
            },
        }


class FakeSynthesis:
    @staticmethod
    def synthesize(base, proposals):
        return (
            {
                "$schema": "company-os.outcome-request.v1",
                "objective_id": base["objective_id"],
                "objective": base["objective"],
            },
            {
                "$schema": "company-os.outcome-contract.v1",
                "objective_id": base["objective_id"],
                "scale_allowed": True,
                "contract_sha256": "b" * 64,
            },
        )


class FakeStack:
    @staticmethod
    def materialize(outcome_path, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        objective_id = json.loads(outcome_path.read_text())["objective_id"]
        files = {
            "artifact-contract.json": {
                "$schema": "company-os.artifact-observation-contract.v1",
                "objective_id": objective_id,
                "ready": True,
                "artifact_classes": [{"artifact_class_id": "product", "required": True}],
            },
            "evaluator-contract.json": {
                "$schema": "company-os.evaluator-runtime-contract.v1",
                "objective_id": objective_id,
                "ready": True,
                "evaluators": [
                    {
                        "evaluator_id": "judge",
                        "required": True,
                        "adapter_locator": "workspace://.company-os/evaluators/judge/adapter.py",
                    }
                ],
            },
            "benchmark-contract.json": {
                "$schema": "company-os.benchmark-contract.v1",
                "objective_id": objective_id,
                "ready": True,
                "dimensions": [],
            },
        }
        for name, value in files.items():
            (output_dir / name).write_text(json.dumps(value) + "\n")
        return {"receipt_sha256": "c" * 64}


class MissingAdapterError(ValueError):
    code = "E_ADAPTER_MISSING"


class FakeMissingRegistry:
    @staticmethod
    def build_registry(project_root, evaluator_contract):
        raise MissingAdapterError("adapter missing")


class FakeReadyRegistry:
    @staticmethod
    def build_registry(project_root, evaluator_contract):
        return {
            "$schema": "company-os.evaluator-adapter-registry.v1",
            "schema_version": 1,
            "adapters": [{"adapter_locator": "workspace://.company-os/evaluators/judge/adapter.py"}],
            "registry_sha256": "d" * 64,
        }


class FakeEvaluatorBuild:
    @staticmethod
    def compile_manifest(project_root, evaluator_contract_path, artifact_contract_path, benchmark_contract_path):
        return {
            "complete": False,
            "missing_evaluator_ids": ["judge"],
            "remaining_evaluator_ids": [],
            "fabric": {"kind": "evaluator-build"},
        }


class FakeCalibrationFabric:
    @staticmethod
    def compile_manifest(project_root, evaluator_contract_path, artifact_contract_path, benchmark_contract_path, adapter_registry_path, calibrated):
        return {
            "complete": False,
            "calibration_evaluator_ids": ["judge"],
            "remaining_evaluator_ids": [],
            "fabric": {"kind": "calibration"},
        }


class OutcomeDirectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        MODULE.bootstrap_module = lambda: FakeBootstrap
        MODULE.synthesis_module = lambda: FakeSynthesis
        MODULE.stack_module = lambda: FakeStack
        MODULE.evaluator_build_module = lambda: FakeEvaluatorBuild
        MODULE.calibration_fabric_module = lambda: FakeCalibrationFabric
        MODULE.bind_discovery_fabric = lambda project_root, objective_id, fabric_relative: {
            "mission_control": MODULE.mission_binding(project_root, objective_id),
            "work_admissions": {},
            "work_admission_refs": {},
            "fabric_path": fabric_relative,
            "fabric_file_sha256": MODULE.file_digest(project_root / Path(*fabric_relative.split("/"))),
        }
        MODULE.verify_bound_discovery_fabric = lambda *args, **kwargs: {}
        self.state = MODULE.start(self.project, "viral-game", "Make a viral game.")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_proposals(self) -> None:
        base = MODULE.workspace(self.project, "viral-game")
        for path in MODULE.proposal_paths(base):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"proposal_id": path.parent.name}) + "\n")

    def test_start_returns_one_discovery_execution_boundary(self) -> None:
        self.assertEqual(self.state["stage"], "discovery")
        self.assertEqual(self.state["next_action"]["action"], "execute_fabric")
        self.assertEqual(self.state["next_action"]["stage"], "discovery")

    def test_advance_does_not_invent_missing_discovery(self) -> None:
        result = MODULE.advance(self.project, "viral-game")
        self.assertEqual(result["stage"], "discovery")
        self.assertIn("proposal.json", result["next_action"]["reason"])

    def test_completed_discovery_enters_control_before_evaluator_construction(self) -> None:
        self.write_proposals()
        state = MODULE.load_state(self.project, "viral-game")
        # Stop the deterministic recursion at the control boundary so this unit test
        # proves sequencing without constructing a full project control store.
        original = MODULE.build_outcome_control
        def stop_at_control(*args, **kwargs):
            raise MODULE.DirectorError("E_TEST_CONTROL", "reached first reality control")
        MODULE.build_outcome_control = stop_at_control
        try:
            with self.assertRaises(MODULE.DirectorError) as caught:
                MODULE.advance(self.project, "viral-game")
            self.assertEqual(caught.exception.code, "E_TEST_CONTROL")
            persisted = MODULE.load_state(self.project, "viral-game")
            self.assertEqual(persisted["stage"], "control")
            self.assertTrue((MODULE.workspace(self.project, "viral-game") / "measurable-outcome-request.json").is_file())
        finally:
            MODULE.build_outcome_control = original

    def test_evaluators_are_not_requested_before_candidate_phase(self) -> None:
        self.write_proposals()
        MODULE.registry_module = lambda: FakeMissingRegistry
        original = MODULE.build_outcome_control
        def stop_at_control(*args, **kwargs):
            raise MODULE.DirectorError("E_TEST_CONTROL", "reached first reality control")
        MODULE.build_outcome_control = stop_at_control
        try:
            with self.assertRaises(MODULE.DirectorError):
                MODULE.advance(self.project, "viral-game")
            self.assertFalse((MODULE.workspace(self.project, "viral-game") / "runtime/evaluator-build-fabric.json").exists())
            self.assertFalse((MODULE.workspace(self.project, "viral-game") / "runtime/calibration-fabric.json").exists())
        finally:
            MODULE.build_outcome_control = original

    def test_director_state_tampering_is_rejected(self) -> None:
        path = MODULE.state_path(self.project, "viral-game")
        raw = json.loads(path.read_text())
        raw["stage"] = "accepted"
        path.write_text(json.dumps(raw) + "\n")
        with self.assertRaises(MODULE.DirectorError) as caught:
            MODULE.load_state(self.project, "viral-game")
        self.assertEqual(caught.exception.code, "E_DIGEST")


if __name__ == "__main__":
    unittest.main()
