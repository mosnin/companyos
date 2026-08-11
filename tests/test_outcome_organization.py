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


ORG = load(
    "outcome_organization",
    ROOT / "skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py",
)
FABRIC = load(
    "fabric_validator_for_outcome_organization",
    ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_fabric.py",
)


class OutcomeOrganizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.control = {
            "$schema": "company-os.outcome-control-binding.v1",
            "execution_lane": "pilot",
            "project_id": "project-a",
            "program_version": 1,
            "work_id": "work-a",
            "governed_outcome": "A player can complete the core loop.",
            "objective_id": "viral-game",
            "outcome_contract_path": ".company-os/outcome.json",
            "artifact_contract_path": ".company-os/artifacts.json",
            "evaluator_contract_path": ".company-os/evaluators.json",
            "benchmark_contract_path": ".company-os/benchmarks.json",
            "calibration_receipts_path": ".company-os/calibrations.json",
            "scale_authorization_path": None,
        }
        self.request = {
            "$schema": ORG.REQUEST_SCHEMA,
            "project_id": "project-a",
            "program_version": 1,
            "work_id": "work-a",
            "governed_outcome": "A player can complete the core loop.",
            "north_star": "Turn broad objectives into excellent real outcomes.",
            "user_value": "A polished playable game.",
            "rationale": "Prove autonomous product delivery.",
            "architecture": "Closed loop outcome delivery.",
            "dependencies": ["project repository"],
            "non_goals": ["production deployment"],
            "constraints": ["no consequential external effects"],
            "outcome_control": self.control,
            "mission_control": {
                "$schema": "company-os.mission-execution-binding.v1",
                "state_path": ".company-os/mission.json",
                "state_sha256": "a" * 64,
                "mission_id": "viral-game",
                "generation": 1,
                "status": "active",
                "mission_class": "company_mission",
                "governor_decision_sha256": "b" * 64,
                "governor_mode": "normal",
                "allowed_work_classes": ["implementation", "repair", "evaluation"],
                "paused_work_classes": [],
                "dominant_bottleneck": {"capability_id": "playable_game", "state": "missing"},
                "first_reality": None,
                "first_reality_required": False,
                "replacement_orders": [],
            },
            "work_admission": {
                "$schema": "company-os.work-admission-receipt.v1",
                "request_id": "request",
                "task_id": "task",
                "manager_id": "manager",
                "work_class": "implementation",
                "admitted": True,
                "blockers": [],
                "mission_state_sha256": "a" * 64,
                "governor_decision_sha256": "b" * 64,
                "governor_mode": "normal",
                "dominant_bottleneck": {"capability_id": "playable_game", "state": "missing"},
                "allowed_work_classes": ["implementation", "repair", "evaluation"],
                "replacement_orders": [],
                "receipt_sha256": "c" * 64,
            },
        }
        self.write_state(self.initial_state())

    def tearDown(self) -> None:
        self.temp.cleanup()

    def initial_state(self) -> dict:
        state = {
            "$schema": ORG.LOOP_SCHEMA,
            "schema_version": 1,
            "objective_id": "viral-game",
            "original_objective": "Make a viral game.",
            "quality_policy": {},
            "phase": "build_candidate",
            "iteration": 0,
            "control_state": None,
            "required_artifact_classes": ["playable_game"],
            "required_evaluators": [],
            "organization_plan": {
                "production_lanes": [{
                    "lane_id": "artifact:playable_game",
                    "role": "artifact_specialist",
                    "artifact_class_id": "playable_game",
                    "artifact_classes": ["playable_game"],
                    "mandate": "Materialize a real playable game.",
                }]
            },
            "candidates": [],
            "evaluations": [],
            "diagnoses": [],
            "interventions": [],
            "acceptance": None,
            "history": [],
            "next_action": {"action": "materialize_candidate"},
            "state_sha256": None,
        }
        state["state_sha256"] = ORG.digest({**state, "state_sha256": None})
        return state

    def write_state(self, state: dict) -> None:
        path = self.root / ".company-os/outcome-loop.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def compile(self) -> dict:
        state = json.loads((self.root / ".company-os/outcome-loop.json").read_text(encoding="utf-8"))
        self.request["work_admission"]["work_class"] = {
            "build_candidate": "implementation",
            "rework": "repair",
            "evaluate": "evaluation",
        }[state["phase"]]
        return ORG.compile_manifest(self.root, ".company-os/outcome-loop.json", self.request)

    def test_initial_candidate_compiles_smallest_bound_fabric(self) -> None:
        manifest = self.compile()
        self.assertEqual(manifest["topology_mode"], "outcome_closed_loop")
        self.assertEqual(len(manifest["managers"]), 1)
        manager = manifest["managers"][0]
        self.assertEqual(manager["outcome_loop_lane_id"], "artifact:playable_game")
        self.assertEqual(manager["workers"][0]["model"], "gpt-5.6-luna")
        self.assertEqual(FABRIC.validate(manifest)["valid"], True)
        verified = ORG.validate_manifest_binding(self.root, manifest)
        self.assertEqual(verified["phase"], "build_candidate")

    def test_rework_compiles_only_bottleneck_lane_and_preserves_strengths(self) -> None:
        state = self.initial_state()
        state["phase"] = "rework"
        state["iteration"] = 2
        intervention = {
            "target_dimensions": ["visual_quality"],
            "preserve_dimensions": ["gameplay"],
        }
        state["organization_plan"] = {
            "specialist_lanes": [{
                "lane_id": "improve:visual_quality",
                "role": "bottleneck_specialist",
                "target_dimension": "visual_quality",
                "artifact_classes": ["playable_game"],
                "mandate": "Improve visual quality without rebuilding accepted gameplay.",
            }]
        }
        state["next_action"] = {"action": "execute_intervention", "intervention": intervention}
        state["state_sha256"] = ORG.digest({**state, "state_sha256": None})
        self.write_state(state)
        manifest = self.compile()
        self.assertEqual(len(manifest["managers"]), 1)
        manager = manifest["managers"][0]
        self.assertEqual(manager["outcome_loop_lane_id"], "improve:visual_quality")
        self.assertTrue(any("Preserve independently passing quality dimension gameplay" == item for item in manager["acceptance"]))
        self.assertIn("Preserve already passing dimensions: gameplay.", manager["workers"][0]["task"])

    def test_evaluation_phase_compiles_independent_read_only_evaluator_lane(self) -> None:
        state = self.initial_state()
        state["phase"] = "evaluate"
        state["iteration"] = 1
        state["required_evaluators"] = [{
            "evaluator_id": "gameplay-evaluator",
            "artifact_classes": ["playable_game"],
            "score_dimensions": ["gameplay", "visual_quality"],
        }]
        state["organization_plan"] = {
            "evaluation_lanes": [{
                "lane_id": "evaluator:gameplay-evaluator",
                "role": "independent_evaluator",
                "evaluator_id": "gameplay-evaluator",
                "artifact_classes": ["playable_game"],
                "score_dimensions": ["gameplay", "visual_quality"],
                "mandate": "Independently play and score the current game candidate.",
            }]
        }
        state["next_action"] = {
            "action": "execute_required_evaluators",
            "candidate_id": "candidate:1",
            "evaluator_ids": ["gameplay-evaluator"],
        }
        state["state_sha256"] = ORG.digest({**state, "state_sha256": None})
        self.write_state(state)
        manifest = self.compile()
        self.assertEqual(manifest["outcome_loop"]["phase"], "evaluate")
        self.assertEqual(len(manifest["managers"]), 1)
        manager = manifest["managers"][0]
        worker = manager["workers"][0]
        self.assertEqual(manager["outcome_loop_lane_id"], "evaluator:gameplay-evaluator")
        self.assertEqual(worker["outcome_context"]["evaluator_id"], "gameplay-evaluator")
        self.assertEqual(worker["outcome_context"]["artifact_classes"], ["playable_game"])
        self.assertEqual(worker["outcome_context"]["score_dimensions"], ["gameplay", "visual_quality"])
        self.assertTrue(worker["write_scope"][0].endswith("/evaluation-receipt"))
        self.assertTrue(any("Do not modify candidate artifacts" in item for item in manager["acceptance"]))
        self.assertEqual(ORG.validate_manifest_binding(self.root, manifest)["phase"], "evaluate")

    def test_loop_state_drift_invalidates_existing_fabric(self) -> None:
        manifest = self.compile()
        state = self.initial_state()
        state["iteration"] = 1
        state["state_sha256"] = ORG.digest({**state, "state_sha256": None})
        self.write_state(state)
        with self.assertRaises(ORG.OrganizationError) as caught:
            ORG.validate_manifest_binding(self.root, manifest)
        self.assertEqual(caught.exception.code, "E_DIGEST")

    def test_manager_lane_tampering_is_rejected(self) -> None:
        manifest = self.compile()
        manifest["managers"][0]["outcome"] = "Do generic work"
        with self.assertRaises(ORG.OrganizationError) as caught:
            ORG.validate_manifest_binding(self.root, manifest)
        self.assertEqual(caught.exception.code, "E_ORGANIZATION")

    def test_pilot_cannot_compile_three_manager_bottleneck_fanout(self) -> None:
        state = self.initial_state()
        state["organization_plan"]["production_lanes"] = [
            {"lane_id": f"artifact:a{i}", "role": "artifact_specialist", "artifact_class_id": f"a{i}", "mandate": f"Build a{i}"}
            for i in range(3)
        ]
        state["state_sha256"] = ORG.digest({**state, "state_sha256": None})
        self.write_state(state)
        with self.assertRaises(ORG.OrganizationError) as caught:
            self.compile()
        self.assertEqual(caught.exception.code, "E_SCALE")


if __name__ == "__main__":
    unittest.main()
