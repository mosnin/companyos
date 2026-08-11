from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/direct-outcome/scripts/direct_outcome.py"
spec = importlib.util.spec_from_file_location("discovery_mission_binding", SCRIPT)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


def budget(time=20.0, tokens=4000, cost=4.0, concurrency=1):
    return {
        "time_minutes": time,
        "token_limit": tokens,
        "cost_usd": cost,
        "max_concurrency": concurrency,
        "max_retries": 1,
    }


def context(manager_outcome):
    return {
        "program_version": 1,
        "north_star": "Build the real product",
        "user_value": "A working product",
        "program_outcome": "Build the real product",
        "manager_outcome": manager_outcome,
        "roadmap_position": "discovery",
        "dependencies": ["repository"],
        "non_goals": ["production deployment"],
        "constraints": ["reversible local work only"],
    }


def worker(worker_id, manager_outcome, work_class):
    return {
        "id": worker_id,
        "model": "gpt-5.6-luna",
        "task": "Create evidence for the current execution path.",
        "acceptance": ["Exact evidence exists"],
        "write_scope": [f".company-os/work/{worker_id}"],
        "risk": "low",
        "budget": budget(),
        "work_class": work_class,
        "outcome_context": context(manager_outcome),
        "stop_condition": "Evidence exists or a concrete blocker is proven.",
    }


def manifest():
    research_outcome = "Resolve the live product blocker."
    implementation_outcome = "Create and run the first real artifact."
    return {
        "program_id": "project",
        "program_version": 1,
        "outcome": "Build the real product",
        "acceptance": ["A real artifact and cited discovery evidence exist"],
        "program_contract": {
            "north_star": "Build the real product",
            "user_value": "A working product",
            "rationale": "Research and execution proceed together.",
            "architecture": "One research lane and one reality lane.",
            "roadmap": ["charter", "discovery", "design", "execution", "verification", "integration"],
            "dependencies": ["repository"],
            "non_goals": ["production deployment"],
            "constraints": ["reversible local work only"],
        },
        "max_managers": 2,
        "max_manager_concurrency": 2,
        "max_workers_per_manager": 1,
        "max_total_workers": 2,
        "max_depth": 2,
        "max_worker_retries": 1,
        "max_manager_rework_rounds": 2,
        "budget": budget(40.0, 8000, 8.0, 2),
        "luna_token_share_target": 0.75,
        "external_effects_allowed": False,
        "managers": [
            {
                "id": "research-manager",
                "model": "gpt-5.6-sol",
                "outcome": research_outcome,
                "acceptance": ["Research resolves a live blocker"],
                "phase_ids": ["charter", "discovery", "design", "execution", "verification", "integration"],
                "budget": budget(),
                "write_scope": [".company-os/work/research"],
                "workers": [worker("research-worker", research_outcome, "research")],
            },
            {
                "id": "implementation-manager",
                "model": "gpt-5.6-sol",
                "outcome": implementation_outcome,
                "acceptance": ["A real artifact runs"],
                "phase_ids": ["charter", "discovery", "design", "execution", "verification", "integration"],
                "budget": budget(),
                "write_scope": [".company-os/work/implementation"],
                "workers": [worker("implementation-worker", implementation_outcome, "implementation")],
            },
        ],
    }


class DiscoveryMissionBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.objective_id = "product"
        mission = MODULE.mission_control_module().initialize_state(
            self.objective_id,
            "Build the real product",
            mission_class="bounded_feature",
            duration_minutes=180,
        )
        MODULE.save_mission_state(self.root, mission)
        self.fabric_path = MODULE.workspace(self.root, self.objective_id) / "discovery-fabric.json"
        self.fabric_path.parent.mkdir(parents=True, exist_ok=True)
        self.fabric_path.write_text(json.dumps(manifest(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.relative = MODULE.relative(self.root, self.fabric_path)

    def tearDown(self):
        self.temp.cleanup()

    def test_discovery_research_and_execution_receive_exact_admissions(self):
        result = MODULE.bind_discovery_fabric(self.root, self.objective_id, self.relative)
        bound = json.loads(self.fabric_path.read_text(encoding="utf-8"))
        self.assertEqual(set(bound["work_admissions"]), {"implementation", "research"})
        self.assertTrue(bound["work_admissions"]["implementation"]["admitted"])
        self.assertTrue(bound["work_admissions"]["research"]["admitted"])
        self.assertEqual(bound["mission_control"]["state_sha256"], result["mission_control"]["state_sha256"])
        for manager in bound["managers"]:
            self.assertEqual(manager["mission_control"], bound["mission_control"])
            for child in manager["workers"]:
                self.assertEqual(child["mission_control"], bound["mission_control"])
                self.assertEqual(child["work_admission"], bound["work_admissions"][child["work_class"]])
        verified = MODULE.verify_bound_discovery_fabric(self.root, self.objective_id, self.relative)
        self.assertEqual(verified["mission_state_sha256"], bound["mission_control"]["state_sha256"])

    def test_mission_state_change_invalidates_discovery_fabric(self):
        MODULE.bind_discovery_fabric(self.root, self.objective_id, self.relative)
        mission = MODULE.load_mission_state(self.root, self.objective_id)
        mission = MODULE.mission_control_module().record_event(
            mission,
            MODULE.mission_control_module().make_event(
                "after-dispatch",
                "work_recorded",
                work_class="implementation",
            ),
        )
        MODULE.save_mission_state(self.root, mission)
        with self.assertRaises(MODULE.DirectorError) as caught:
            MODULE.verify_bound_discovery_fabric(self.root, self.objective_id, self.relative)
        self.assertEqual(caught.exception.code, "E_GOVERNOR")


if __name__ == "__main__":
    unittest.main()
