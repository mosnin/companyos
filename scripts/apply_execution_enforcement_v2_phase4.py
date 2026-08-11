#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_mission_control() -> None:
    path = ROOT / "skills/company-os/mission-execution-control/scripts/mission_control.py"
    replace_once(
        path,
        '''        elif miss_count == 2:
            active_workers = sorted(key for key, item in workers.items() if isinstance(item, Mapping) and item.get("status") == "active")
            for worker_id in active_workers[:1]:
                replacements.append(
                    {
                        "order_id": f"replace-worker:{worker_id}:{name}",
                        "kind": "replace_worker",
                        "worker_id": worker_id,
                        "reason": f"second miss of {name}",
                        "issued_at": format_time(current),
                    }
                )
                workers[worker_id] = {**workers[worker_id], "status": "replace"}
        elif miss_count >= 3:
            active_managers = sorted(key for key, item in managers.items() if isinstance(item, Mapping) and item.get("status") == "active")
            for manager_id in active_managers[:1]:
                replacements.append(
                    {
                        "order_id": f"replace-manager:{manager_id}:{name}",
                        "kind": "replace_manager",
                        "manager_id": manager_id,
                        "reason": f"repeated mission deadline failure: {name}",
                        "issued_at": format_time(current),
                    }
                )
                managers[manager_id] = {**managers[manager_id], "status": "replace"}
''',
        '''        elif miss_count == 2:
            active_workers = sorted(key for key, item in workers.items() if isinstance(item, Mapping) and item.get("status") == "active")
            targets = active_workers[:1] or ["current-bottleneck-worker"]
            for worker_id in targets:
                order = {
                    "order_id": f"replace-worker:{worker_id}:{name}",
                    "kind": "replace_worker",
                    "worker_id": worker_id,
                    "reason": f"second miss of {name}",
                    "issued_at": format_time(current),
                }
                if order not in replacements:
                    replacements.append(order)
                if worker_id in workers:
                    workers[worker_id] = {**workers[worker_id], "status": "replace"}
        elif miss_count >= 3:
            active_managers = sorted(key for key, item in managers.items() if isinstance(item, Mapping) and item.get("status") == "active")
            targets = active_managers[:1] or ["current-bottleneck-manager"]
            for manager_id in targets:
                order = {
                    "order_id": f"replace-manager:{manager_id}:{name}",
                    "kind": "replace_manager",
                    "manager_id": manager_id,
                    "reason": f"repeated mission deadline failure: {name}",
                    "issued_at": format_time(current),
                }
                if order not in replacements:
                    replacements.append(order)
                if manager_id in managers:
                    managers[manager_id] = {**managers[manager_id], "status": "replace"}
''',
    )


def patch_organization() -> None:
    path = ROOT / "skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py"
    replace_once(
        path,
        '''def _engineering_root(objective_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
''',
        '''def _mission_module():
    path = Path(__file__).resolve().parents[2] / "mission-execution-control/scripts/mission_control.py"
    spec = importlib.util.spec_from_file_location("company_os_mission_execution_control", path)
    if spec is None or spec.loader is None:
        raise OrganizationError("E_GOVERNOR", "mission execution control is unavailable")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def _engineering_root(objective_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
''',
    )
    replace_once(
        path,
        '''    managers = []
    lane_sha256s: dict[str, str] = {}
    for index, lane in enumerate(lanes, 1):
''',
        '''    managers = []
    lane_sha256s: dict[str, str] = {}
    replacement_orders = [item for item in mission_control.get("replacement_orders", []) if isinstance(item, Mapping)]
    replace_manager = any(item.get("kind") == "replace_manager" for item in replacement_orders)
    replace_worker = any(item.get("kind") == "replace_worker" for item in replacement_orders)
    replacement_generation = len(replacement_orders)
    for index, lane in enumerate(lanes, 1):
''',
    )
    replace_once(
        path,
        '''        manager_id = f"outcome-manager-{index:02d}-{_slug(lane['lane_id'])}"
        resource_scope = f"outcome-lanes/{index:02d}-{_slug(lane['lane_id'])}"
''',
        '''        manager_id = f"outcome-manager-{index:02d}-{_slug(lane['lane_id'])}"
        if replace_manager:
            manager_id += f"-replacement-{replacement_generation}"
        worker_id = f"{manager_id}-worker-01"
        if replace_worker:
            worker_id += f"-replacement-{replacement_generation}"
        resource_scope = f"outcome-lanes/{index:02d}-{_slug(lane['lane_id'])}"
''',
    )
    replace_once(
        path,
        '''            artifact_manifest_binding = {"$schema": "company-os.outcome-lane-artifact-manifest.v1", "schema_version": 1, "objective_id": state["objective_id"], "outcome_loop_state_sha256": state["state_sha256"], "organization_sha256": digest(state["organization_plan"]), "lane_id": lane["lane_id"], "lane_sha256": lane_sha, "production_actor_id": f"{manager_id}-worker-01"}
''',
        '''            artifact_manifest_binding = {"$schema": "company-os.outcome-lane-artifact-manifest.v1", "schema_version": 1, "objective_id": state["objective_id"], "outcome_loop_state_sha256": state["state_sha256"], "organization_sha256": digest(state["organization_plan"]), "lane_id": lane["lane_id"], "lane_sha256": lane_sha, "production_actor_id": worker_id}
''',
    )
    replace_once(
        path,
        '''        worker_engineering = engineering_module.derive(manager_engineering, {"contract_id": f"engineering:{manager_id}:worker-01", "objective_id": objective_id, "manager_level": "worker", "required_skills": list(manager_engineering["required_skills"]), "write_scopes": worker_write_scope})
''',
        '''        worker_engineering = engineering_module.derive(manager_engineering, {"contract_id": f"engineering:{worker_id}", "objective_id": objective_id, "manager_level": "worker", "required_skills": list(manager_engineering["required_skills"]), "write_scopes": worker_write_scope})
''',
    )
    replace_once(
        path,
        '''        outcome_context["engineering_execution_contract"] = worker_engineering
        work_class = "evaluation" if state.get("phase") == "evaluate" else "repair" if state.get("phase") == "rework" else "implementation"
        outcome_context["mission_control"] = mission_control
        outcome_context["work_admission"] = admission
        workers = [{"id": f"{manager_id}-worker-01", "model": "gpt-5.6-luna", "task": worker_task, "acceptance": acceptance, "write_scope": worker_write_scope, "risk": "medium", "budget": dict(manager_budget), "work_class": work_class, "outcome_context": outcome_context, "engineering_execution_contract": worker_engineering, "stop_condition": stop_condition, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha}]
        managers.append({"id": manager_id, "model": "gpt-5.6-sol", "outcome": lane["mandate"], "acceptance": acceptance, "phase_ids": PHASES, "budget": dict(manager_budget), "work_class": work_class, "write_scope": [resource_scope], "artifact_classes": lane["artifact_classes"], "engineering_execution_contract": manager_engineering, "workers": workers, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha})
''',
        '''        outcome_context["engineering_execution_contract"] = worker_engineering
        work_class = "evaluation" if state.get("phase") == "evaluate" else "repair" if state.get("phase") == "rework" else "implementation"
        outcome_context["mission_control"] = mission_control
        outcome_context["work_admission"] = admission
        if replace_worker or replace_manager:
            worker_task += " This is a replacement context. Read the durable artifact and runtime evidence, do not repeat the failed strategy, and move the current global bottleneck."
        workers = [{"id": worker_id, "model": "gpt-5.6-luna", "task": worker_task, "acceptance": acceptance, "write_scope": worker_write_scope, "risk": "medium", "budget": dict(manager_budget), "work_class": work_class, "mission_control": mission_control, "work_admission": admission, "outcome_context": outcome_context, "engineering_execution_contract": worker_engineering, "stop_condition": stop_condition, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha}]
        managers.append({"id": manager_id, "model": "gpt-5.6-sol", "outcome": lane["mandate"], "acceptance": acceptance, "phase_ids": PHASES, "budget": dict(manager_budget), "work_class": work_class, "mission_control": mission_control, "work_admission": admission, "write_scope": [resource_scope], "artifact_classes": lane["artifact_classes"], "engineering_execution_contract": manager_engineering, "workers": workers, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha})
''',
    )
    replace_once(
        path,
        '''    binding = dict(_object(manifest.get("outcome_loop"), "outcome_loop"))
''',
        '''    mission_binding = dict(_object(manifest.get("mission_control"), "mission_control"))
    mission_path, mission_relative = _safe(project_root, mission_binding.get("state_path"), "mission_control.state_path")
    mission = _mission_module().verify_state(_object(_read(mission_path, "mission execution state"), "mission execution state"))
    if mission_relative != mission_binding.get("state_path") or mission.get("state_sha256") != mission_binding.get("state_sha256"):
        raise OrganizationError("E_GOVERNOR", "mission execution binding is stale")
    if mission.get("status") != "active" or mission.get("generation") != mission_binding.get("generation"):
        raise OrganizationError("E_GOVERNOR", "mission is inactive or generation changed")
    decision = _object(mission.get("governor_decision"), "governor decision")
    if decision.get("decision_sha256") != mission_binding.get("governor_decision_sha256"):
        raise OrganizationError("E_GOVERNOR", "governor decision changed")
    admission = _mission_module().verify_admission(_object(manifest.get("work_admission"), "work_admission"))
    if admission.get("admitted") is not True or admission.get("mission_state_sha256") != mission["state_sha256"] or admission.get("governor_decision_sha256") != decision.get("decision_sha256"):
        raise OrganizationError("E_GOVERNOR", "work admission is stale or rejected")
    if admission.get("work_class") not in set(decision.get("allowed_work_classes", [])) or admission.get("work_class") in set(decision.get("paused_work_classes", [])):
        raise OrganizationError("E_GOVERNOR", "admitted work class is no longer allowed")
    binding = dict(_object(manifest.get("outcome_loop"), "outcome_loop"))
''',
    )
    replace_once(
        path,
        '''        workers = manager.get("workers")
        if not isinstance(workers, list) or not workers:
            raise OrganizationError("E_ORGANIZATION", f"manager {lane_id} has no worker")
        for worker in workers:
''',
        '''        if manager.get("mission_control") != mission_binding or manager.get("work_admission") != admission:
            raise OrganizationError("E_GOVERNOR", f"manager {lane_id} lost mission admission")
        workers = manager.get("workers")
        if not isinstance(workers, list) or not workers:
            raise OrganizationError("E_ORGANIZATION", f"manager {lane_id} has no worker")
        for worker in workers:
''',
    )
    replace_once(
        path,
        '''            worker = _object(worker, "worker")
            if worker.get("outcome_loop_lane_id") != lane_id or worker.get("outcome_loop_lane_sha256") != expected_lane_digests[lane_id]:
''',
        '''            worker = _object(worker, "worker")
            if worker.get("mission_control") != mission_binding or worker.get("work_admission") != admission:
                raise OrganizationError("E_GOVERNOR", f"worker {lane_id} lost mission admission")
            if worker.get("outcome_loop_lane_id") != lane_id or worker.get("outcome_loop_lane_sha256") != expected_lane_digests[lane_id]:
''',
    )


def patch_tests() -> None:
    path = ROOT / "tests/test_outcome_organization.py"
    replace_once(
        path,
        '''FABRIC = load(
    "fabric_validator_for_outcome_organization",
    ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_fabric.py",
)
''',
        '''FABRIC = load(
    "fabric_validator_for_outcome_organization",
    ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_fabric.py",
)
MISSION = load(
    "mission_control_for_outcome_organization",
    ROOT / "skills/company-os/mission-execution-control/scripts/mission_control.py",
)
''',
    )
    replace_once(
        path,
        '''        self.write_state(self.initial_state())
''',
        '''        self.write_state(self.initial_state())
        self.write_mission()
''',
    )
    replace_once(
        path,
        '''    def write_state(self, state: dict) -> None:
''',
        '''    def write_mission(self, *, replacement_orders=None) -> dict:
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
        path.write_text(json.dumps(mission, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
        return mission

    def write_state(self, state: dict) -> None:
''',
    )
    replace_once(
        path,
        '''    def compile(self) -> dict:
        state = json.loads((self.root / ".company-os/outcome-loop.json").read_text(encoding="utf-8"))
        self.request["work_admission"]["work_class"] = {
            "build_candidate": "implementation",
            "rework": "repair",
            "evaluate": "evaluation",
        }[state["phase"]]
        return ORG.compile_manifest(self.root, ".company-os/outcome-loop.json", self.request)
''',
        '''    def compile(self) -> dict:
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
''',
    )
    replace_once(
        path,
        '''    def test_loop_state_drift_invalidates_existing_fabric(self) -> None:
''',
        '''    def test_stale_mission_state_invalidates_existing_fabric(self) -> None:
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
        (self.root / ".company-os/mission.json").write_text(json.dumps(mission, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
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
''',
    )


def main() -> None:
    patch_mission_control()
    patch_organization()
    patch_tests()
    print("execution enforcement v2 phase 4 applied")


if __name__ == "__main__":
    main()
