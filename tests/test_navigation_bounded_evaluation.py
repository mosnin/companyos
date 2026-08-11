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


MISSION = load("navigation_bounded_eval_mission", ROOT / "skills/company-os/mission-execution-control/scripts/mission_control.py")
ORG = load("navigation_bounded_eval_org", ROOT / "skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py")


class NavigationBoundedEvaluationTests(unittest.TestCase):
    def test_route_bound_evaluation_is_a_small_sensor_interrupt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = {
                "$schema": ORG.LOOP_SCHEMA,
                "schema_version": 1,
                "objective_id": "micro",
                "original_objective": "Build the product.",
                "quality_policy": {},
                "phase": "evaluate",
                "iteration": 1,
                "control_state": None,
                "required_artifact_classes": ["browser_path"],
                "required_evaluators": [{
                    "evaluator_id": "browser-evaluator",
                    "artifact_classes": ["browser_path"],
                    "score_dimensions": ["correctness"],
                }],
                "organization_plan": {
                    "evaluation_lanes": [{
                        "lane_id": "evaluator:browser-evaluator",
                        "role": "independent_evaluator",
                        "evaluator_id": "browser-evaluator",
                        "artifact_classes": ["browser_path"],
                        "score_dimensions": ["correctness"],
                        "mandate": "Inspect the current browser candidate and identify whether repair is needed.",
                    }]
                },
                "candidates": [],
                "evaluations": [],
                "diagnoses": [],
                "interventions": [],
                "acceptance": None,
                "history": [],
                "next_action": {"action": "execute_required_evaluators"},
                "state_sha256": None,
            }
            state["state_sha256"] = ORG.digest({**state, "state_sha256": None})
            loop_path = root / ".company-os/outcome-loop.json"
            loop_path.parent.mkdir(parents=True)
            loop_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            mission = MISSION.initialize_state(
                "micro",
                "Build a real browser product.",
                started_at="2026-08-11T12:00:00Z",
                mission_class="quick_build",
                duration_minutes=90,
            )
            self.assertNotEqual(mission["navigation"]["next_action"]["work_class"], "evaluation")
            target = mission["navigation"]["next_action"]["capability_id"]
            mission_path = root / ".company-os/mission.json"
            mission_path.write_text(json.dumps(mission, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            admission = MISSION.admit_work(
                mission,
                {
                    "$schema": MISSION.ADMISSION_SCHEMA,
                    "request_id": "candidate-sensor-evaluation",
                    "task_id": "candidate-sensor-evaluation",
                    "manager_id": "outcome-director",
                    "work_class": "evaluation",
                    "bootstrap": False,
                    "justification": {
                        "consumer_task_id": "active-route-worker",
                        "blocker_id": target,
                        "decision_dependency": "Determine whether the current candidate changes route confidence or requires targeted repair.",
                        "deadline_minutes": 10,
                        "expected_action_change": True,
                    },
                },
            )
            self.assertTrue(admission["admitted"], admission)

            control = {
                "$schema": "company-os.outcome-control-binding.v1",
                "execution_lane": "pilot",
                "project_id": "project",
                "program_version": 1,
                "work_id": "work",
                "governed_outcome": "Build the product.",
                "objective_id": "micro",
                "outcome_contract_path": ".company-os/outcome.json",
                "artifact_contract_path": ".company-os/artifacts.json",
                "evaluator_contract_path": ".company-os/evaluators.json",
                "benchmark_contract_path": ".company-os/benchmarks.json",
                "calibration_receipts_path": ".company-os/calibrations.json",
                "scale_authorization_path": None,
            }
            decision = mission["governor_decision"]
            request = {
                "$schema": ORG.REQUEST_SCHEMA,
                "project_id": "project",
                "program_version": 1,
                "work_id": "work",
                "governed_outcome": "Build the product.",
                "north_star": "Reach the destination.",
                "user_value": "Working product",
                "rationale": "Use evaluation as a bounded sensor.",
                "architecture": "Closed-loop navigation.",
                "dependencies": ["project repository"],
                "non_goals": ["production deployment"],
                "constraints": ["reversible local work"],
                "outcome_control": control,
                "mission_control": {
                    "$schema": "company-os.mission-execution-binding.v1",
                    "state_path": ".company-os/mission.json",
                    "state_sha256": mission["state_sha256"],
                    "mission_id": "micro",
                    "generation": mission["generation"],
                    "status": mission["status"],
                    "mission_class": mission["mission_class"],
                    "governor_decision_sha256": decision["decision_sha256"],
                    "governor_mode": decision["mode"],
                    "allowed_work_classes": decision["allowed_work_classes"],
                    "paused_work_classes": decision["paused_work_classes"],
                    "dominant_bottleneck": decision["dominant_bottleneck"],
                    "first_reality": mission.get("first_reality"),
                    "first_reality_required": bool(mission.get("first_reality")),
                    "replacement_orders": mission["replacement_orders"],
                    "navigation": mission["navigation"],
                },
                "work_admission": admission,
                "budget": {"time_minutes": 60.0, "token_limit": 12000, "cost_usd": 12.0, "max_concurrency": 1, "max_retries": 1},
            }
            manifest = ORG.compile_manifest(root, ".company-os/outcome-loop.json", request)
            worker_budget = manifest["managers"][0]["workers"][0]["budget"]
            self.assertLessEqual(worker_budget["time_minutes"], 10.0)
            self.assertLessEqual(worker_budget["token_limit"], 3000)
            self.assertLessEqual(worker_budget["cost_usd"], 3.0)
            self.assertEqual(worker_budget["max_retries"], 0)


if __name__ == "__main__":
    unittest.main()
