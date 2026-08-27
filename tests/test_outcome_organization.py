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
MISSION = load(
    "mission_control_for_outcome_organization",
    ROOT / "skills/company-os/mission-execution-control/scripts/mission_control.py",
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
        self.write_mission()

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

    def write_mission(self, *, replacement_orders=None) -> dict:
        mission = MISSION.initialize_state(
            "viral-game",
            "Make a viral game.",
            started_at="2026-08-11T12:00:00Z",
            mission_class="company_mission",
            duration_minutes=420,
        )
        if replacement_orders is not None:
            mission["replacement_orders"] = replacement_orders
            mission = MISSION.refresh_governor(MISSION.seal(mission), now=MISSION.parse_time("2026-08-11T12:01:00Z", "now"))
        path = self.root / ".company-os/mission.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(mission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return mission

    def make_mission_evaluation_ready(self) -> dict:
        path = self.root / ".company-os/mission.json"
        mission = MISSION.verify_state(json.loads(path.read_text(encoding="utf-8")))
        for capability in mission["capabilities"]:
            capability["state"] = "connected"
            capability["evidence"] = [{"kind": "fixture_connected", "capability_id": capability["capability_id"]}]
        mission["checkpoint"] = {"fixture": "candidate-is-durable"}
        mission = MISSION.refresh_governor(
            MISSION.seal(mission),
            now=MISSION.parse_time("2026-08-11T12:01:00Z", "now"),
        )
        path.write_text(json.dumps(mission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.assertEqual(mission["navigation"]["next_action"]["work_class"], "evaluation")
        return mission

    def write_state(self, state: dict) -> None:
        path = self.root / ".company-os/outcome-loop.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def compile(self) -> dict:
        state = json.loads((self.root / ".company-os/outcome-loop.json").read_text(encoding="utf-8"))
        mission = MISSION.verify_state(json.loads((self.root / ".company-os/mission.json").read_text(encoding="utf-8")))
        decision = mission["governor_decision"]
        self.request["mission_control"].update({
            "state_sha256": mission["state_sha256"],
            "generation": mission["generation"],
            "status": mission["status"],
            "mission_class": mission["mission_class"],
            "governor_decision_sha256": decision["decision_sha256"],
            "governor_mode": decision["mode"],
            "allowed_work_classes": decision["allowed_work_classes"],
            "paused_work_classes": decision["paused_work_classes"],
            "dominant_bottleneck": decision["dominant_bottleneck"],
            "replacement_orders": mission["replacement_orders"],
            "navigation": mission.get("navigation"),
        })
        work_class = {
            "build_candidate": "implementation",
            "rework": "repair",
            "evaluate": "evaluation",
        }[state["phase"]]
        self.request["work_admission"] = MISSION.admit_work(
            mission,
            {
                "$schema": MISSION.ADMISSION_SCHEMA,
                "request_id": f"request:{state['phase']}",
                "task_id": f"task:{state['phase']}",
                "manager_id": "manager",
                "work_class": work_class,
                "bootstrap": False,
            },
            now=MISSION.parse_time("2026-08-11T12:01:00Z", "now"),
        )
        return ORG.compile_manifest(self.root, ".company-os/outcome-loop.json", self.request)

    def test_initial_candidate_compiles_smallest_bound_fabric(self) -> None:
        manifest = self.compile()
        self.assertEqual(manifest["topology_mode"], "outcome_closed_loop")
        self.assertEqual(len(manifest["managers"]), 1)
        manager = manifest["managers"][0]
        self.assertEqual(manager["outcome_loop_lane_id"], "artifact:playable_game")
        self.assertEqual(manager["workers"][0]["model"], "gpt-5.6-luna")
        self.assertEqual(manifest["goal_route"]["state_sha256"], manifest["goal_route_state"]["state_sha256"])
        self.assertEqual(manager["goal_contract"], manager["goal_assignment"]["manager_goal"])
        self.assertEqual(manager["workers"][0]["goal_contract"], manager["goal_assignment"]["worker_goal"])
        self.assertEqual(FABRIC.validate(manifest)["valid"], True)
        verified = ORG.validate_manifest_binding(self.root, manifest)
        self.assertEqual(verified["phase"], "build_candidate")
        self.assertEqual(verified["goal_route_state_sha256"], manifest["goal_route"]["state_sha256"])

    def test_goal_assignment_tampering_is_rejected(self) -> None:
        manifest = self.compile()
        manifest["managers"][0]["goal_assignment"]["worker_id"] = "replacement-without-reseal"
        with self.assertRaises(ORG.OrganizationError) as caught:
            ORG.validate_manifest_binding(self.root, manifest)
        self.assertEqual(caught.exception.code, "E_GOAL_ROUTE")

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
        self.make_mission_evaluation_ready()
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
        self.assertEqual(worker["outcome_context"]["navigation"]["next_action"]["work_class"], "evaluation")
        self.assertEqual(ORG.validate_manifest_binding(self.root, manifest)["phase"], "evaluate")

    def test_stale_mission_state_invalidates_existing_fabric(self) -> None:
        manifest = self.compile()
        mission = MISSION.verify_state(json.loads((self.root / ".company-os/mission.json").read_text(encoding="utf-8")))
        mission = MISSION.record_event(
            mission,
            MISSION.make_event(
                "after-fabric",
                "work_recorded",
                occurred_at="2026-08-11T12:02:00Z",
                work_class="implementation",
            ),
        )
        (self.root / ".company-os/mission.json").write_text(json.dumps(mission, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with self.assertRaises(ORG.OrganizationError) as caught:
            ORG.validate_manifest_binding(self.root, manifest)
        self.assertEqual(caught.exception.code, "E_GOVERNOR")

    def test_replacement_order_compiles_fresh_manager_and_worker_identities(self) -> None:
        self.write_mission(
            replacement_orders=[
                {"order_id": "replace-manager", "kind": "replace_manager", "manager_id": "current-bottleneck-manager", "reason": "deadline", "issued_at": "2026-08-11T12:01:00Z"},
                {"order_id": "replace-worker", "kind": "replace_worker", "worker_id": "current-bottleneck-worker", "reason": "deadline", "issued_at": "2026-08-11T12:01:00Z"},
            ]
        )
        manifest = self.compile()
        manager = manifest["managers"][0]
        worker = manager["workers"][0]
        self.assertIn("replacement-2", manager["id"])
        self.assertIn("replacement-2", worker["id"])
        self.assertIn("replacement context", worker["task"])

    def test_loop_state_drift_invalidates_existing_fabric(self) -> None:
        manifest = self.compile()
        state = self.initial_state()
        state["iteration"] = 7
        state["state_sha256"] = ORG.digest({**state, "state_sha256": None})
        self.write_state(state)
        with self.assertRaises(ORG.OrganizationError) as caught:
            ORG.validate_manifest_binding(self.root, manifest)
        self.assertEqual(caught.exception.code, "E_DIGEST")

    def test_manager_lane_tampering_is_rejected(self) -> None:
        manifest = self.compile()
        manifest["managers"][0]["outcome_loop_lane_sha256"] = "0" * 64
        with self.assertRaises(ORG.OrganizationError) as caught:
            ORG.validate_manifest_binding(self.root, manifest)
        self.assertEqual(caught.exception.code, "E_BINDING")

    def test_pilot_cannot_compile_three_manager_bottleneck_fanout(self) -> None:
        state = self.initial_state()
        state["organization_plan"]["production_lanes"] = [
            {"lane_id": f"artifact:part-{index}", "role": "artifact_specialist", "artifact_class_id": f"part-{index}", "artifact_classes": [f"part-{index}"], "mandate": f"Build part {index}."}
            for index in range(3)
        ]
        state["required_artifact_classes"] = [f"part-{index}" for index in range(3)]
        state["state_sha256"] = ORG.digest({**state, "state_sha256": None})
        self.write_state(state)
        with self.assertRaises(ORG.OrganizationError) as caught:
            self.compile()
        self.assertEqual(caught.exception.code, "E_SCALE")


if __name__ == "__main__":
    unittest.main()
