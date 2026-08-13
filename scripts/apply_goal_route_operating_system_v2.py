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


def patch_goal_route() -> None:
    path = ROOT / "skills/company-os/goal-route-system/scripts/goal_route.py"
    replace_once(path, '        if value in {None, ""} or value == []:\n', '        if value is None or value == "" or value == []:\n')
    replace_once(
        path,
        '        if template_level != level and not (template_level == "manager" and level == "company"):\n',
        '        if template_level != level and not (level == "company" and template_level in {"master", "manager"}):\n',
    )
    replace_once(
        path,
        '        phase_bonus = 4 if phase == "evaluate" and goal["route_segment_id"] == "verification_acceptance" else 0\n',
        '        phase_bonus = 8 if phase == "evaluate" and goal["route_segment_id"] == "verification_acceptance" else 6 if phase == "discovery" and goal["route_segment_id"] in {"context", "strategy"} else 6 if phase in {"build_candidate", "rework"} and goal["route_segment_id"] == "first_reality" else 0\n',
    )
    replace_once(
        path,
        '''    root = next(goal for goal in goals if goal["goal_id"] == state["root_goal_id"])
    if root["status"] == "accepted":
''',
        '''    root = next(goal for goal in goals if goal["goal_id"] == state["root_goal_id"])
    state["root_goal_sha256"] = root["goal_sha256"]
    if root["status"] == "accepted":
''',
    )
    insert = '''\n\ndef verify_assignment(raw: Mapping[str, Any], route_raw: Mapping[str, Any]) -> dict[str, Any]:
    assignment = verify_seal(raw, "assignment_sha256", "goal assignment")
    if assignment.get("$schema") != "company-os.goal-assignment.v1":
        raise GoalRouteError("E_SCHEMA", "goal assignment schema is invalid")
    route = verify_state(route_raw)
    if assignment.get("route_state_sha256") != route["state_sha256"] or assignment.get("route_version") != route["route_version"]:
        raise GoalRouteError("E_BINDING", "goal assignment binds a stale route")
    goals = {goal["goal_id"]: goal for goal in route["goals"]}
    for label in ("manager_goal", "worker_goal"):
        goal = assignment.get(label)
        if not isinstance(goal, Mapping) or goal.get("goal_id") not in goals:
            raise GoalRouteError("E_BINDING", f"{label} is missing from the route")
        if goal.get("goal_sha256") != goals[goal["goal_id"]]["goal_sha256"]:
            raise GoalRouteError("E_BINDING", f"{label} digest changed")
    if assignment["worker_goal"]["parent_goal_id"] not in {assignment["manager_goal"]["goal_id"], *[goal["goal_id"] for goal in route["goals"] if goal.get("parent_goal_id") == assignment["manager_goal"]["goal_id"]]}:
        worker_parent = goals.get(assignment["worker_goal"]["parent_goal_id"])
        if worker_parent is None or worker_parent.get("parent_goal_id") != assignment["manager_goal"]["goal_id"]:
            raise GoalRouteError("E_BINDING", "worker goal is not under the manager goal")
    if assignment.get("cohesion_contract", {}).get("cohesion_sha256") != route["cohesion_contract"]["cohesion_sha256"]:
        raise GoalRouteError("E_COHESION", "assignment cohesion changed")
    return assignment


def delegation_plan(route_raw: Mapping[str, Any], manager_goal_id: str) -> dict[str, Any]:
    route = verify_state(route_raw)
    manager = goal_by_id(route, manager_goal_id)
    submanagers = [dict(goal) for goal in route["goals"] if goal.get("parent_goal_id") == manager_goal_id and goal.get("owner", {}).get("goal_level") == "submanager"]
    workers = [dict(goal) for goal in route["goals"] if goal.get("parent_goal_id") in {item["goal_id"] for item in submanagers} and goal.get("owner", {}).get("goal_level") == "worker"]
    return {
        "$schema": "company-os.goal-delegation-plan.v1",
        "route_state_sha256": route["state_sha256"],
        "manager_goal_id": manager_goal_id,
        "manager_goal_sha256": manager["goal_sha256"],
        "submanager_goals": submanagers,
        "worker_goals": workers,
        "coverage": sorted({condition for item in submanagers for condition in item.get("contributes_to", [])}),
        "delegation_sha256": None,
    } | {}


def sealed_delegation_plan(route_raw: Mapping[str, Any], manager_goal_id: str) -> dict[str, Any]:
    return seal(delegation_plan(route_raw, manager_goal_id), "delegation_sha256")


def record_candidate(state_raw: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    state = verify_state(state_raw)
    for artifact in candidate.get("artifacts", []):
        if not isinstance(artifact, Mapping) or not artifact.get("goal_id"):
            continue
        goal = goal_by_id(state, artifact["goal_id"])
        current = goal["progress"]["state"]
        if PROGRESS_ORDER[current] < PROGRESS_ORDER["artifact_materialized"]:
            state = record_evidence(state, goal_id=goal["goal_id"], evidence_type="artifact_manifest", path=artifact["path"], sha256=artifact["sha256"], progress_state="artifact_materialized")
    observations = sorted((item for item in candidate.get("observations", []) if isinstance(item, Mapping) and item.get("goal_id")), key=lambda item: (0 if item.get("kind") == "runtime_observed" else 1, str(item.get("goal_id"))))
    for observation in observations:
        goal = goal_by_id(state, observation["goal_id"])
        target = "runnable" if observation.get("kind") == "runtime_observed" else "connected"
        if PROGRESS_ORDER[goal["progress"]["state"]] >= PROGRESS_ORDER[target]:
            continue
        evidence_type = "runtime_receipt" if target == "runnable" else "journey_receipt"
        state = record_evidence(state, goal_id=goal["goal_id"], evidence_type=evidence_type, path=observation["path"], sha256=observation["sha256"], progress_state=target)
    return state


def accept_route(state_raw: Mapping[str, Any], *, receipt_path: str, receipt_sha256: str) -> dict[str, Any]:
    state = verify_state(state_raw)
    worker_ids = [goal["goal_id"] for goal in state["goals"] if goal.get("owner", {}).get("goal_level") == "worker" and goal.get("status") != "accepted"]
    for goal_id in worker_ids:
        state = record_evidence(state, goal_id=goal_id, evidence_type="independent_acceptance", path=receipt_path, sha256=receipt_sha256, progress_state="accepted")
    if state.get("status") != "accepted":
        raise GoalRouteError("E_ACCEPTANCE", "independent receipt did not close the complete goal graph")
    return state
'''
    replace_once(path, '\ndef summary(state_raw: Mapping[str, Any]) -> dict[str, Any]:\n', insert + '\n\ndef summary(state_raw: Mapping[str, Any]) -> dict[str, Any]:\n')


def patch_director() -> None:
    path = ROOT / "skills/company-os/direct-outcome/scripts/direct_outcome.py"
    replace_once(
        path,
        '''def mission_control_module():
    return load_module("mission-execution-control/scripts/mission_control.py", "company_os_director_mission_control")


def control_store_module():
''',
        '''def mission_control_module():
    return load_module("mission-execution-control/scripts/mission_control.py", "company_os_director_mission_control")


def goal_route_module():
    return load_module("goal-route-system/scripts/goal_route.py", "company_os_director_goal_route")


def control_store_module():
''',
    )
    replace_once(
        path,
        '''def mission_state_path(project_root: Path, objective_id: str) -> Path:
    return workspace(project_root, objective_id) / "mission-execution-state.json"


def load_mission_state''',
        '''def mission_state_path(project_root: Path, objective_id: str) -> Path:
    return workspace(project_root, objective_id) / "mission-execution-state.json"


def goal_route_path(project_root: Path, objective_id: str) -> Path:
    return workspace(project_root, objective_id) / "goal-route.json"


def load_goal_route(project_root: Path, objective_id: str) -> dict[str, Any]:
    return goal_route_module().verify_state(obj(read_json(goal_route_path(project_root, objective_id), "goal route"), "goal route"))


def save_goal_route(project_root: Path, state: Mapping[str, Any]) -> dict[str, Any]:
    verified = goal_route_module().verify_state(state)
    write_json(goal_route_path(project_root, verified["objective_id"]), verified)
    return verified


def goal_route_binding(project_root: Path, objective_id: str) -> dict[str, Any]:
    route = load_goal_route(project_root, objective_id)
    path = goal_route_path(project_root, objective_id)
    return {"$schema": "company-os.goal-route-binding.v1", "path": relative(project_root, path), "file_sha256": file_digest(path), "state_sha256": route["state_sha256"], "route_version": route["route_version"], "root_goal_id": route["root_goal_id"], "root_goal_sha256": route["root_goal_sha256"]}


def load_mission_state''',
    )
    replace_once(
        path,
        '''        "navigation": state.get("navigation"),
    }
''',
        '''        "navigation": state.get("navigation"),
        "goal_route": goal_route_binding(project_root, state["objective_id"]) if goal_route_path(project_root, state["objective_id"]).is_file() else None,
    }
''',
    )
    replace_once(
        path,
        '''    binding = mission_binding_from_state(project_root, state)
    fabric_path = project_root / Path(*fabric_relative.split("/"))
''',
        '''    binding = mission_binding_from_state(project_root, state)
    route = load_goal_route(project_root, objective_id)
    fabric_path = project_root / Path(*fabric_relative.split("/"))
''',
    )
    replace_once(
        path,
        '''            worker["work_class"] = work_class
            worker["mission_control"] = binding
            worker["work_admission"] = admissions[work_class]
            workers.append(worker)
''',
        '''            worker["work_class"] = work_class
            worker["mission_control"] = binding
            worker["work_admission"] = admissions[work_class]
            phase_hint = "discovery" if work_class == "research" else "build_candidate"
            assignment = goal_route_module().assignment_for_lane(route, artifact_classes=[], phase=phase_hint, lane_id=f"discovery:{manager.get('id')}:{worker.get('id')}", manager_id=str(manager.get("id")), worker_id=str(worker.get("id")))
            worker["goal_assignment"] = assignment
            worker["goal_contract"] = assignment["worker_goal"]
            worker["agent_template"] = assignment["worker_template"]
            worker["cohesion_contract"] = assignment["cohesion_contract"]
            worker["task"] = "Concrete goal contract: " + json.dumps(assignment["worker_goal"], sort_keys=True) + ". Sprint: " + json.dumps(assignment["sprint"], sort_keys=True) + ". " + str(worker.get("task") or "")
            workers.append(worker)
''',
    )
    replace_once(
        path,
        '''        manager["work_class"] = manager_class
        manager["mission_control"] = binding
        manager["work_admission"] = admissions[manager_class]
        manager["workers"] = workers
''',
        '''        manager["work_class"] = manager_class
        manager["mission_control"] = binding
        manager["work_admission"] = admissions[manager_class]
        if workers:
            manager_assignment = workers[0]["goal_assignment"]
            manager["goal_assignment"] = manager_assignment
            manager["goal_contract"] = manager_assignment["manager_goal"]
            manager["agent_template"] = manager_assignment["manager_template"]
            manager["cohesion_contract"] = manager_assignment["cohesion_contract"]
            manager["delegation_plan"] = goal_route_module().sealed_delegation_plan(route, manager_assignment["manager_goal"]["goal_id"])
        manager["workers"] = workers
''',
    )
    replace_once(
        path,
        '''        "fabric_file_sha256": file_digest(fabric_path),
    }
''',
        '''        "fabric_file_sha256": file_digest(fabric_path),
        "goal_route": goal_route_binding(project_root, objective_id),
    }
''',
        )
    replace_once(
        path,
        '''def start(project_root: Path, objective_id: str, objective: str) -> dict[str, Any]:
''',
        '''def start(project_root: Path, objective_id: str, objective: str, *, kickoff_profile: Mapping[str, Any] | None = None, autonomy_mode: str | None = None) -> dict[str, Any]:
''',
    )
    replace_once(
        path,
        '''    mission = mission_control_module().initialize_state(objective_id, objective)
    save_mission_state(project_root, mission)
    discovery_binding = bind_discovery_fabric(project_root, objective_id, discovery_fabric)
''',
        '''    mission = mission_control_module().initialize_state(objective_id, objective)
    save_mission_state(project_root, mission)
    route = goal_route_module().compile_goal_route(objective_id, objective, mission_class=mission["mission_class"], kickoff_profile=kickoff_profile, autonomy_mode=autonomy_mode)
    save_goal_route(project_root, route)
    discovery_binding = bind_discovery_fabric(project_root, objective_id, discovery_fabric)
''',
    )
    replace_once(
        path,
        '''            "mission_execution_state": relative(project_root, mission_state_path(project_root, objective_id)),
        },
''',
        '''            "mission_execution_state": relative(project_root, mission_state_path(project_root, objective_id)),
            "goal_route": relative(project_root, goal_route_path(project_root, objective_id)),
        },
''',
    )
    replace_once(
        path,
        '''        "outcome_control": dict(binding),
    }
''',
        '''        "outcome_control": dict(binding),
        "goal_route": goal_route_binding(project_root, state["objective_id"]),
    }
''',
    )
    replace_once(
        path,
        '''def checkpoint_candidate(
''',
        '''def record_candidate_goal_evidence(project_root: Path, objective_id: str, candidate: Mapping[str, Any]) -> None:
    route = load_goal_route(project_root, objective_id)
    route = goal_route_module().record_candidate(route, candidate)
    save_goal_route(project_root, route)


def checkpoint_candidate(
''',
    )
    replace_once(
        path,
        '''                record_candidate_mission_evidence(project_root, objective_id, candidate)
                checkpoint = checkpoint_candidate(project_root, objective_id, candidate)
''',
        '''                record_candidate_mission_evidence(project_root, objective_id, candidate)
                record_candidate_goal_evidence(project_root, objective_id, candidate)
                checkpoint = checkpoint_candidate(project_root, objective_id, candidate)
''',
    )
    replace_once(
        path,
        '''    save_mission_state(project_root, state)


def seal(state: Mapping[str, Any]) -> dict[str, Any]:
''',
        '''    save_mission_state(project_root, state)
    route = load_goal_route(project_root, objective_id)
    route = goal_route_module().accept_route(route, receipt_path=relative(project_root, receipt_path), receipt_sha256=file_digest(receipt_path))
    save_goal_route(project_root, route)


def seal(state: Mapping[str, Any]) -> dict[str, Any]:
''',
    )
    replace_once(
        path,
        '''        "mission_execution": {
''',
        '''        "goal_route": goal_route_module().summary(load_goal_route(project_root, objective_id)),
        "mission_execution": {
''',
    )
    replace_once(
        path,
        '''    start_parser.add_argument("--objective", required=True)
''',
        '''    start_parser.add_argument("--objective", required=True)
    start_parser.add_argument("--kickoff-profile", type=Path)
    start_parser.add_argument("--autonomy-mode", choices=["guided_interview", "guided_defaults", "autonomous_research"])
''',
    )
    replace_once(
        path,
        '''        if args.command == "start":
            result = start(args.project_root, args.objective_id, args.objective)
''',
        '''        if args.command == "start":
            kickoff = obj(read_json(args.kickoff_profile, "kickoff profile"), "kickoff profile") if args.kickoff_profile else None
            result = start(args.project_root, args.objective_id, args.objective, kickoff_profile=kickoff, autonomy_mode=args.autonomy_mode)
''',
    )


def patch_organization() -> None:
    path = ROOT / "skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py"
    replace_once(
        path,
        '''def _mission_module():
''',
        '''def _goal_route_module():
    path = Path(__file__).resolve().parents[2] / "goal-route-system/scripts/goal_route.py"
    spec = importlib.util.spec_from_file_location("company_os_goal_route_system", path)
    if spec is None or spec.loader is None:
        raise OrganizationError("E_GOAL_ROUTE", "goal route system is unavailable")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def _mission_module():
''',
    )
    replace_once(
        path,
        '''    engineering_module = _engineering_module()
    master_engineering = _engineering_root(objective_id, request)
''',
        '''    engineering_module = _engineering_module()
    master_engineering = _engineering_root(objective_id, request)
    goal_module = _goal_route_module()
    route_binding = request.get("goal_route")
    if isinstance(route_binding, Mapping):
        route_path, route_relative = _safe(project_root, route_binding.get("path"), "goal_route.path")
        route_state = goal_module.verify_state(_object(_read(route_path, "goal route"), "goal route"))
        if route_binding.get("file_sha256") != file_digest(route_path) or route_binding.get("state_sha256") != route_state["state_sha256"] or route_binding.get("root_goal_sha256") != route_state["root_goal_sha256"]:
            raise OrganizationError("E_GOAL_ROUTE", "goal route binding is stale")
        route_manifest_binding = dict(route_binding)
    else:
        route_state = goal_module.compile_goal_route(objective_id, governed_outcome, mission_class=str(mission_control.get("mission_class") or "bounded_feature"), autonomy_mode="autonomous_research")
        route_manifest_binding = {"$schema": "company-os.goal-route-binding.v1", "path": None, "file_sha256": None, "state_sha256": route_state["state_sha256"], "route_version": route_state["route_version"], "root_goal_id": route_state["root_goal_id"], "root_goal_sha256": route_state["root_goal_sha256"], "embedded": True}
''',
    )
    replace_once(
        path,
        '''        resource_scope = f"outcome-lanes/{index:02d}-{_slug(lane['lane_id'])}"
        if state.get("phase") == "evaluate":
''',
        '''        resource_scope = f"outcome-lanes/{index:02d}-{_slug(lane['lane_id'])}"
        goal_assignment = goal_module.assignment_for_lane(route_state, artifact_classes=lane["artifact_classes"], phase=state.get("phase"), lane_id=lane["lane_id"], manager_id=manager_id, worker_id=worker_id)
        manager_goal = goal_assignment["manager_goal"]
        worker_goal = goal_assignment["worker_goal"]
        delegation = goal_module.sealed_delegation_plan(route_state, manager_goal["goal_id"])
        if state.get("phase") == "evaluate":
''',
    )
    replace_once(
        path,
        '''            worker_task = lane["mandate"] + " Navigation route action: " + json.dumps(route_action, sort_keys=True) + ". " + sensor_reason + " Score only the bound dimensions: " + ", ".join(lane["score_dimensions"]) + "."
''',
        '''            worker_task = lane["mandate"] + " Concrete goal contract: " + json.dumps(worker_goal, sort_keys=True) + ". Navigation route action: " + json.dumps(route_action, sort_keys=True) + ". " + sensor_reason + " Score only the bound dimensions: " + ", ".join(lane["score_dimensions"]) + "."
''',
    )
    replace_once(
        path,
        '''            worker_task = lane["mandate"] + " Navigation route action: " + json.dumps(route_action, sort_keys=True) + ". Execute that state-changing action first, then observe the environment and replan. Within the first third of this lane budget, create and run the smallest real end-to-end artifact path. Stop broad research and speculative architecture once enough is known to execute. Use the minimum-sufficient-actuation policy: " + json.dumps(route_policy, sort_keys=True) + ". If the user supplied a provider, repository, SDK, or framework that already implements a required capability, integrate and exercise it before building a replacement; replacement requires concrete blocker evidence."
''',
        '''            worker_task = lane["mandate"] + " Concrete goal contract: " + json.dumps(worker_goal, sort_keys=True) + ". Sprint: " + json.dumps(goal_assignment["sprint"], sort_keys=True) + ". Route node: " + json.dumps(goal_assignment["route_node"], sort_keys=True) + ". Navigation route action: " + json.dumps(route_action, sort_keys=True) + ". Execute that state-changing action first, then observe the environment and replan. Within the first third of this lane budget, create and run the smallest real end-to-end artifact path. Stop broad research and speculative architecture once enough is known to execute. Use the minimum-sufficient-actuation policy: " + json.dumps(route_policy, sort_keys=True) + ". If the user supplied a provider, repository, SDK, or framework that already implements a required capability, integrate and exercise it before building a replacement; replacement requires concrete blocker evidence."
''',
    )
    replace_once(
        path,
        '''            artifact_manifest_binding = {"$schema": "company-os.outcome-lane-artifact-manifest.v1", "schema_version": 1, "objective_id": state["objective_id"], "outcome_loop_state_sha256": state["state_sha256"], "organization_sha256": digest(state["organization_plan"]), "lane_id": lane["lane_id"], "lane_sha256": lane_sha, "production_actor_id": worker_id}
''',
        '''            artifact_manifest_binding = {"$schema": "company-os.outcome-lane-artifact-manifest.v1", "schema_version": 1, "objective_id": state["objective_id"], "outcome_loop_state_sha256": state["state_sha256"], "organization_sha256": digest(state["organization_plan"]), "lane_id": lane["lane_id"], "lane_sha256": lane_sha, "production_actor_id": worker_id, "goal_id": worker_goal["goal_id"], "goal_sha256": worker_goal["goal_sha256"], "goal_route_state_sha256": route_state["state_sha256"]}
''',
    )
    replace_once(
        path,
        '''        outcome_context["mission_control"] = mission_control
        outcome_context["work_admission"] = admission
''',
        '''        outcome_context["mission_control"] = mission_control
        outcome_context["work_admission"] = admission
        outcome_context["goal_route"] = route_manifest_binding
        outcome_context["goal_assignment"] = goal_assignment
        outcome_context["goal_contract"] = worker_goal
        outcome_context["cohesion_contract"] = goal_assignment["cohesion_contract"]
        outcome_context["delegation_plan"] = delegation
''',
    )
    replace_once(
        path,
        '''        workers = [{"id": worker_id, "model": "gpt-5.6-luna", "task": worker_task, "acceptance": acceptance, "write_scope": worker_write_scope, "risk": "medium", "budget": dict(manager_budget), "work_class": work_class, "mission_control": mission_control, "work_admission": admission, "outcome_context": outcome_context, "engineering_execution_contract": worker_engineering, "stop_condition": stop_condition, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha}]
        managers.append({"id": manager_id, "model": "gpt-5.6-sol", "outcome": lane["mandate"], "acceptance": acceptance, "phase_ids": PHASES, "budget": dict(manager_budget), "work_class": work_class, "mission_control": mission_control, "work_admission": admission, "write_scope": [resource_scope], "artifact_classes": lane["artifact_classes"], "engineering_execution_contract": manager_engineering, "workers": workers, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha})
''',
        '''        workers = [{"id": worker_id, "model": "gpt-5.6-luna", "task": worker_task, "acceptance": acceptance, "write_scope": worker_write_scope, "risk": "medium", "budget": dict(manager_budget), "work_class": work_class, "mission_control": mission_control, "work_admission": admission, "goal_route": route_manifest_binding, "goal_assignment": goal_assignment, "goal_contract": worker_goal, "agent_template": goal_assignment["worker_template"], "cohesion_contract": goal_assignment["cohesion_contract"], "sprint": goal_assignment["sprint"], "route_node": goal_assignment["route_node"], "outcome_context": outcome_context, "engineering_execution_contract": worker_engineering, "stop_condition": stop_condition, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha}]
        managers.append({"id": manager_id, "model": "gpt-5.6-sol", "outcome": lane["mandate"], "acceptance": acceptance, "phase_ids": PHASES, "budget": dict(manager_budget), "work_class": work_class, "mission_control": mission_control, "work_admission": admission, "goal_route": route_manifest_binding, "goal_assignment": goal_assignment, "goal_contract": manager_goal, "agent_template": goal_assignment["manager_template"], "cohesion_contract": goal_assignment["cohesion_contract"], "delegation_plan": delegation, "write_scope": [resource_scope], "artifact_classes": lane["artifact_classes"], "engineering_execution_contract": manager_engineering, "workers": workers, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha})
''',
    )
    replace_once(
        path,
        '''    return {"program_id": project_id, "topology_mode": TOPOLOGY_MODE, "mission_control": mission_control, "work_admission": admission, "engineering_execution_contract": master_engineering,
''',
        '''    return {"program_id": project_id, "topology_mode": TOPOLOGY_MODE, "mission_control": mission_control, "work_admission": admission, "goal_route": route_manifest_binding, "goal_route_state": route_state if route_manifest_binding.get("embedded") is True else None, "engineering_execution_contract": master_engineering,
''',
    )
    replace_once(
        path,
        '''    binding = dict(_object(manifest.get("outcome_loop"), "outcome_loop"))
''',
        '''    goal_module = _goal_route_module()
    route_binding = _object(manifest.get("goal_route"), "goal_route")
    if route_binding.get("embedded") is True:
        route_state = goal_module.verify_state(_object(manifest.get("goal_route_state"), "goal_route_state"))
    else:
        route_path, route_relative = _safe(project_root, route_binding.get("path"), "goal_route.path")
        route_state = goal_module.verify_state(_object(_read(route_path, "goal route"), "goal route"))
        if route_relative != route_binding.get("path") or file_digest(route_path) != route_binding.get("file_sha256"):
            raise OrganizationError("E_GOAL_ROUTE", "goal route file changed")
    if route_state.get("state_sha256") != route_binding.get("state_sha256") or route_state.get("root_goal_sha256") != route_binding.get("root_goal_sha256"):
        raise OrganizationError("E_GOAL_ROUTE", "goal route binding changed")
    binding = dict(_object(manifest.get("outcome_loop"), "outcome_loop"))
''',
    )
    replace_once(
        path,
        '''        if manager.get("mission_control") != mission_binding or manager.get("work_admission") != admission:
            raise OrganizationError("E_GOVERNOR", f"manager {lane_id} lost mission admission")
''',
        '''        if manager.get("mission_control") != mission_binding or manager.get("work_admission") != admission:
            raise OrganizationError("E_GOVERNOR", f"manager {lane_id} lost mission admission")
        try:
            manager_assignment = goal_module.verify_assignment(_object(manager.get("goal_assignment"), "manager.goal_assignment"), route_state)
        except Exception as exc:
            raise OrganizationError("E_GOAL_ROUTE", f"manager {lane_id} goal assignment is invalid: {exc}") from exc
        if manager_assignment.get("manager_id") != manager.get("id") or manager.get("goal_contract", {}).get("goal_sha256") != manager_assignment["manager_goal"]["goal_sha256"]:
            raise OrganizationError("E_GOAL_ROUTE", f"manager {lane_id} goal binding changed")
''',
    )
    replace_once(
        path,
        '''            if worker.get("mission_control") != mission_binding or worker.get("work_admission") != admission:
                raise OrganizationError("E_GOVERNOR", f"worker {lane_id} lost mission admission")
''',
        '''            if worker.get("mission_control") != mission_binding or worker.get("work_admission") != admission:
                raise OrganizationError("E_GOVERNOR", f"worker {lane_id} lost mission admission")
            try:
                worker_assignment = goal_module.verify_assignment(_object(worker.get("goal_assignment"), "worker.goal_assignment"), route_state)
            except Exception as exc:
                raise OrganizationError("E_GOAL_ROUTE", f"worker {lane_id} goal assignment is invalid: {exc}") from exc
            if worker_assignment.get("worker_id") != worker.get("id") or worker.get("goal_contract", {}).get("goal_sha256") != worker_assignment["worker_goal"]["goal_sha256"]:
                raise OrganizationError("E_GOAL_ROUTE", f"worker {lane_id} goal binding changed")
''',
    )


def patch_candidate() -> None:
    path = ROOT / "skills/company-os/assemble-outcome-candidate/scripts/assemble_candidate.py"
    replace_once(
        path,
        '''                    "manifest_path": f"{scope}/artifact-manifest.json",
                }
''',
        '''                    "manifest_path": f"{scope}/artifact-manifest.json",
                    "goal_id": worker.get("goal_contract", {}).get("goal_id"),
                    "goal_sha256": worker.get("goal_contract", {}).get("goal_sha256"),
                    "goal_route_state_sha256": worker.get("goal_assignment", {}).get("route_state_sha256"),
                }
''',
    )
    replace_once(
        path,
        '''    artifacts_raw = manifest.get("artifacts")
''',
        '''    if worker.get("goal_id") is not None:
        if manifest.get("goal_id") != worker.get("goal_id") or manifest.get("goal_sha256") != worker.get("goal_sha256") or manifest.get("goal_route_state_sha256") != worker.get("goal_route_state_sha256"):
            raise CandidateAssemblyError("E_BINDING", "lane manifest goal binding is incorrect")
    artifacts_raw = manifest.get("artifacts")
''',
    )
    replace_once(
        path,
        '''                "sha256": actual_sha,
            }
''',
        '''                "sha256": actual_sha,
                "goal_id": worker.get("goal_id"),
                "goal_sha256": worker.get("goal_sha256"),
            }
''',
    )
    replace_once(
        path,
        '''            "observation_kind": text(observation.get("observation_kind", kind), f"observation[{index}].observation_kind"),
        })
''',
        '''            "observation_kind": text(observation.get("observation_kind", kind), f"observation[{index}].observation_kind"),
            "goal_id": worker.get("goal_id"),
            "goal_sha256": worker.get("goal_sha256"),
        })
''',
    )


def patch_doctrine_and_ci() -> None:
    path = ROOT / "skills/company-os/company-os/SKILL.md"
    replace_once(
        path,
        '''| Navigation control | Treat the original objective as the destination; continuously observe, act, verify, measure objective distance/velocity, and replan while keeping research/audits as subordinate sensors | `$navigation-control` |
''',
        '''| Navigation control | Treat the original objective as the destination; continuously observe, act, verify, measure objective distance/velocity, and replan while keeping research/audits as subordinate sensors | `$navigation-control` |
| Goal route operating system | Compile operator context, a concrete root goal, causal goal graph, route segments, sprints, recursive manager and worker goals, agent templates, cohesion, takeover, and evidence rollup | `$goal-route-system` |
''',
    )
    replace_once(
        path,
        '''For every autonomous build mission, the controller runs `$mission-execution-control`, `$navigation-control`, and `$govern-outcome-execution` at dispatch, retry, wake, evidence, expansion, evaluation, and packaging boundaries.
''',
        '''For every autonomous build mission, the controller first compiles `$goal-route-system`, then runs `$mission-execution-control`, `$navigation-control`, and `$govern-outcome-execution` at dispatch, retry, wake, evidence, expansion, evaluation, and packaging boundaries. Every master, manager, submanager, and worker receives a content addressed goal contract and route assignment; a prompt alone is not an executable goal.
''',
    )
    path = ROOT / "skills/company-os/manage-company-program/SKILL.md"
    replace_once(
        path,
        '''Operate `company-os.manager-role.v2`. The manager exists to make the requested outcome real.
''',
        '''Operate `company-os.manager-role.v2`. The manager exists to make the requested outcome real. Before delegation, verify the exact `$goal-route-system` manager goal, parent and root bindings, route segment, sprint, success metrics, evidence requirements, authority, budget, cohesion contract, and takeover packet. A manager may decompose only into admitted child goals that causally cover the parent conditions.
''',
    )
    path = ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md"
    replace_once(
        path,
        '''Operate contract version `company-os.worker-role.v2`. Read the compact work
packet; do not request the root transcript or repeat the Company OS manual.
''',
        '''Operate contract version `company-os.worker-role.v2`. Read the compact work
packet and its exact `$goal-route-system` leaf goal; do not request the root transcript or repeat the Company OS manual. Before acting, identify the parent goal, current state, target state, required state changes, tasks, subtasks, evidence, authority, budget, route node, sprint, cohesion contract, and reporting destination. A prompt without that bound goal is not executable authority.
''',
    )
    path = ROOT / ".github/workflows/ci.yml"
    replace_once(
        path,
        '''      - name: Verify execution regression lab
        run: python3 skills/company-os/mission-execution-control/scripts/execution_regression_lab.py --json
''',
        '''      - name: Verify execution regression lab
        run: python3 skills/company-os/mission-execution-control/scripts/execution_regression_lab.py --json
      - name: Verify goal route simulation
        run: python3 skills/company-os/goal-route-system/scripts/goal_route.py simulate
''',
    )
    replace_once(
        path,
        '''          skills/company-os/navigation-control/scripts/navigation_control.py
''',
        '''          skills/company-os/navigation-control/scripts/navigation_control.py
          skills/company-os/goal-route-system/scripts/goal_route.py
''',
    )


def cleanup_staging() -> None:
    for path in [
        ROOT / ".github/workflows/apply-goal-route-operating-system.yml",
        ROOT / "scripts/goal-route-bundle/part-00",
        ROOT / "scripts/goal-route-bundle/part-01-00",
        ROOT / "tmp/goal-route-branch-verification.txt",
        ROOT / "tmp/ignore-this",
        ROOT / "tmp/last-probe",
        ROOT / "tmp/oops",
        ROOT / "tmp/pr-probe.txt",
        ROOT / "tmp/upload-probe-4.txt",
    ]:
        if path.exists():
            path.unlink()


def main() -> None:
    patch_goal_route()
    patch_director()
    patch_organization()
    patch_candidate()
    patch_doctrine_and_ci()
    cleanup_staging()
    print("goal route operating system v2 integrated")


if __name__ == "__main__":
    main()
