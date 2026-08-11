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
        '''def governor_module():
    return load_module(
        "govern-outcome-execution/scripts/executive_governor.py",
        "company_os_mission_executive_governor",
    )

''',
        '''def governor_module():
    return load_module(
        "govern-outcome-execution/scripts/executive_governor.py",
        "company_os_mission_executive_governor",
    )


def navigation_module():
    return load_module(
        "navigation-control/scripts/navigation_control.py",
        "company_os_mission_navigation_control",
    )

''',
    )
    replace_once(
        path,
        '''        "scheduler": {
            "mission_id": objective_id,
            "generation": 1,
            "owner_id": "company-os-director",
            "started_at": format_time(start),
            "expires_at": format_time(expiry),
            "max_wakes": 256 if klass == "long_running_company" else 64,
            "wake_count": 0,
            "status": "active",
        },
        "governor_decision": None,
        "checkpoint": None,
''',
        '''        "scheduler": {
            "mission_id": objective_id,
            "generation": 1,
            "owner_id": "company-os-director",
            "started_at": format_time(start),
            "expires_at": format_time(expiry),
            "max_wakes": 256 if klass == "long_running_company" else 64,
            "wake_count": 0,
            "status": "active",
        },
        "navigation": None,
        "governor_decision": None,
        "checkpoint": None,
''',
    )
    replace_once(
        path,
        '''    if not isinstance(value.get("capabilities"), list) or not value["capabilities"]:
        raise MissionControlError("E_SCHEMA", "mission capabilities are missing")
    return value
''',
        '''    if not isinstance(value.get("capabilities"), list) or not value["capabilities"]:
        raise MissionControlError("E_SCHEMA", "mission capabilities are missing")
    if value.get("navigation") is not None:
        try:
            navigation_module().verify(value["navigation"])
        except Exception as exc:
            raise MissionControlError("E_NAVIGATION", f"navigation state is invalid: {exc}") from exc
    return value
''',
    )
    replace_once(
        path,
        '''def _deadline_evidence(state: Mapping[str, Any]) -> dict[str, bool]:
''',
        '''def _navigation_input(state: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    return {
        "$schema": navigation_module().INPUT_SCHEMA,
        "objective_id": state["objective_id"],
        "objective": state["objective"],
        "now": format_time(now),
        "mission_class": state["mission_class"],
        "capabilities": [
            {
                "capability_id": item["capability_id"],
                "label": item.get("label") or item["capability_id"],
                "state": item["state"],
                "critical": item.get("critical") is True,
                "priority": int(item.get("priority", 50)),
                "first_reality": item.get("first_reality") is True,
                "final_required": item.get("final_required") is not False,
                "existing_implementation": item.get("existing_implementation"),
            }
            for item in state["capabilities"]
        ],
        "reality": reality_signals(state),
        "checkpointed": bool(state.get("checkpoint")),
        "allocation": _allocation(state),
        "events": [dict(item) for item in state.get("events", []) if isinstance(item, Mapping)],
        "previous_navigation": state.get("navigation"),
    }


def _apply_navigation_to_governor(decision: Mapping[str, Any], navigation: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(decision))
    nav = navigation_module().verify(navigation)
    next_action = dict(nav.get("next_action") or {})
    target_id = next_action.get("capability_id")
    if target_id is not None:
        match = next((item for item in result.get("required_capabilities", []) if item.get("capability_id") == target_id), None)
        if match is not None:
            result["dominant_bottleneck"] = match
    result["navigation_decision_sha256"] = nav["decision_sha256"]
    result["navigation_mode"] = nav["mode"]
    result["waypoint"] = nav["waypoint"]
    result["destination_distance"] = nav["position"]["destination_distance"]
    result["waypoint_distance"] = nav["position"]["waypoint_distance"]
    result["objective_velocity"] = nav["velocity"]
    result["next_action"] = next_action
    result["sensor_posture"] = nav["sensor_posture"]
    result["actuation_policy"] = nav["actuation_policy"]
    result["manager_orders"] = list(dict.fromkeys([*nav.get("orders", []), *result.get("manager_orders", [])]))

    should_tighten = nav["mode"] == "stalled_replan" or nav["sensor_posture"].get("overrun") is True
    if should_tighten and result.get("mode") != "accepted":
        next_work = next_action.get("work_class")
        allowed = set(result.get("allowed_work_classes", []))
        sensor_classes = set(navigation_module().SENSOR_CLASSES)
        keep_sensors = {"evaluation"} if next_work == "evaluation" else set()
        allowed -= sensor_classes - keep_sensors
        if next_work in WORK_CLASSES:
            allowed.add(next_work)
        allowed.update({"implementation", "integration", "runtime", "repair", "checkpoint", "packaging"} & set(WORK_CLASSES))
        result["allowed_work_classes"] = [name for name in sorted(WORK_CLASSES) if name in allowed]
        result["paused_work_classes"] = [name for name in sorted(WORK_CLASSES) if name not in allowed]
        if result.get("mode") == "normal":
            result["mode"] = "compression"
    result["decision_sha256"] = None
    result["decision_sha256"] = governor_module().digest(result)
    return result


def _deadline_evidence(state: Mapping[str, Any]) -> dict[str, bool]:
''',
    )
    replace_once(
        path,
        '''    decision = governor_module().evaluate(_governor_input(state, current))
    state["governor_decision"] = decision
    return seal(state)
''',
        '''    decision = governor_module().evaluate(_governor_input(state, current))
    navigation = navigation_module().evaluate(_navigation_input(state, current))
    state["navigation"] = navigation
    state["governor_decision"] = _apply_navigation_to_governor(decision, navigation)
    return seal(state)
''',
    )
    replace_once(
        path,
        '''    justification = request.get("justification")
    if work_class in {"research", "documentation"} and request.get("bootstrap") is not True:
        if not isinstance(justification, Mapping):
            allowed = False
            blockers.append("research or documentation requires consumer-bound justification")
        else:
            for key in ("consumer_task_id", "blocker_id", "decision_dependency"):
                try:
                    text(justification.get(key), f"justification.{key}")
                except MissionControlError as exc:
                    allowed = False
                    blockers.append(exc.message)
            try:
                deadline = integer(justification.get("deadline_minutes"), "justification.deadline_minutes", minimum=1)
                if deadline > 45:
                    allowed = False
                    blockers.append("research or documentation deadline exceeds 45 minutes")
            except MissionControlError as exc:
                allowed = False
                blockers.append(exc.message)
''',
        '''    justification = request.get("justification")
    navigation = state.get("navigation") or {}
    if work_class in navigation_module().SENSOR_CLASSES and request.get("bootstrap") is not True:
        route_action = navigation.get("next_action") if isinstance(navigation, Mapping) else {}
        active_verification = work_class == "evaluation" and isinstance(route_action, Mapping) and route_action.get("work_class") == "evaluation"
        if not active_verification:
            if not isinstance(justification, Mapping):
                allowed = False
                blockers.append("sensor work requires a consumer-bound value-of-information justification")
            else:
                for key in ("consumer_task_id", "blocker_id", "decision_dependency"):
                    try:
                        text(justification.get(key), f"justification.{key}")
                    except MissionControlError as exc:
                        allowed = False
                        blockers.append(exc.message)
                try:
                    deadline = integer(justification.get("deadline_minutes"), "justification.deadline_minutes", minimum=1)
                    if deadline > 45:
                        allowed = False
                        blockers.append("sensor work deadline exceeds 45 minutes")
                except MissionControlError as exc:
                    allowed = False
                    blockers.append(exc.message)
                if allowed:
                    useful, reason = navigation_module().sensor_request_is_useful(navigation, justification)
                    if not useful:
                        allowed = False
                        blockers.append(reason)
''',
    )
    replace_once(
        path,
        '''        "replacement_orders": state.get("replacement_orders", []),
        "receipt_sha256": None,
''',
        '''        "replacement_orders": state.get("replacement_orders", []),
        "navigation_decision_sha256": navigation.get("decision_sha256") if isinstance(navigation, Mapping) else None,
        "navigation_mode": navigation.get("mode") if isinstance(navigation, Mapping) else None,
        "next_action": navigation.get("next_action") if isinstance(navigation, Mapping) else None,
        "receipt_sha256": None,
''',
    )


def patch_director() -> None:
    path = ROOT / "skills/company-os/direct-outcome/scripts/direct_outcome.py"
    replace_once(
        path,
        '''        "replacement_orders": list(state.get("replacement_orders", [])),
    }
''',
        '''        "replacement_orders": list(state.get("replacement_orders", [])),
        "navigation": state.get("navigation"),
    }
''',
    )
    replace_once(
        path,
        '''def admit_mission_work(
    project_root: Path,
    objective_id: str,
    *,
    work_class: str,
    task_id: str,
    manager_id: str,
    bootstrap: bool = False,
    justification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
''',
        '''def admit_mission_work(
    project_root: Path,
    objective_id: str,
    *,
    work_class: str,
    task_id: str,
    manager_id: str,
    bootstrap: bool = False,
    justification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
''',
    )
    # The signature stays stable. Generate sensor justification automatically when the
    # active route itself is an evaluation action.
    replace_once(
        path,
        '''    request = {
        "$schema": module.ADMISSION_SCHEMA,
        "request_id": f"admit:{task_id}:{state['generation']}",
        "task_id": task_id,
        "manager_id": manager_id,
        "work_class": work_class,
        "bootstrap": bootstrap,
    }
    if justification is not None:
        request["justification"] = dict(justification)
''',
        '''    request = {
        "$schema": module.ADMISSION_SCHEMA,
        "request_id": f"admit:{task_id}:{state['generation']}",
        "task_id": task_id,
        "manager_id": manager_id,
        "work_class": work_class,
        "bootstrap": bootstrap,
    }
    if justification is not None:
        request["justification"] = dict(justification)
    elif work_class in {"research", "architecture", "governance", "documentation"} and not bootstrap:
        navigation = state.get("navigation") or {}
        route = navigation.get("next_action") if isinstance(navigation, Mapping) else {}
        request["justification"] = {
            "consumer_task_id": task_id,
            "blocker_id": route.get("capability_id") or "route-action",
            "decision_dependency": "Resolve only the uncertainty that blocks or materially changes the active navigation action.",
            "deadline_minutes": 15,
            "current_action_blocked": True,
            "expected_action_change": True,
        }
''',
    )


def patch_organization() -> None:
    path = ROOT / "skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py"
    replace_once(
        path,
        '''    replacement_orders = [item for item in mission_control.get("replacement_orders", []) if isinstance(item, Mapping)]
    replace_manager = any(item.get("kind") == "replace_manager" for item in replacement_orders)
''',
        '''    replacement_orders = [item for item in mission_control.get("replacement_orders", []) if isinstance(item, Mapping)]
    navigation = mission_control.get("navigation") if isinstance(mission_control.get("navigation"), Mapping) else {}
    route_action = navigation.get("next_action") if isinstance(navigation.get("next_action"), Mapping) else {}
    route_policy = navigation.get("actuation_policy") if isinstance(navigation.get("actuation_policy"), Mapping) else {}
    replace_manager = any(item.get("kind") == "replace_manager" for item in replacement_orders)
''',
    )
    replace_once(
        path,
        '''            worker_task = lane["mandate"] + " Within the first third of this lane budget, create and run the smallest real end-to-end artifact path. Stop broad research and speculative architecture once enough is known to execute. If the user supplied a provider, repository, SDK, or framework that already implements a required capability, integrate and exercise it before building a replacement; replacement requires concrete blocker evidence."
''',
        '''            worker_task = lane["mandate"] + " Navigation route action: " + json.dumps(route_action, sort_keys=True) + ". Execute that state-changing action first, then observe the environment and replan. Within the first third of this lane budget, create and run the smallest real end-to-end artifact path. Stop broad research and speculative architecture once enough is known to execute. Use the minimum-sufficient-actuation policy: " + json.dumps(route_policy, sort_keys=True) + ". If the user supplied a provider, repository, SDK, or framework that already implements a required capability, integrate and exercise it before building a replacement; replacement requires concrete blocker evidence."
''',
    )
    replace_once(
        path,
        '''            worker_task = lane["mandate"] + " Score only the bound dimensions: " + ", ".join(lane["score_dimensions"]) + "."
''',
        '''            worker_task = lane["mandate"] + " Navigation route action: " + json.dumps(route_action, sort_keys=True) + ". Evaluate only because verification is the current route action or a safety interrupt requires it. Score only the bound dimensions: " + ", ".join(lane["score_dimensions"]) + "."
''',
    )
    replace_once(
        path,
        '''        outcome_context = {"program_version": program_version, "north_star": north_star, "user_value": user_value, "program_outcome": governed_outcome, "manager_outcome": lane["mandate"], "roadmap_position": "evaluation" if state.get("phase") == "evaluate" else "execution", "artifact_classes": lane["artifact_classes"], "dependencies": dependencies, "non_goals": non_goals, "constraints": constraints + extra_constraints, "execution_policy": {"first_reality_target": "R3", "first_reality_budget_fraction": 0.25, "global_bottleneck": lane["mandate"], "documentation_is_not_progress": True, "prefer_existing_capabilities": True}}
''',
        '''        outcome_context = {"program_version": program_version, "north_star": north_star, "user_value": user_value, "program_outcome": governed_outcome, "manager_outcome": lane["mandate"], "roadmap_position": "evaluation" if state.get("phase") == "evaluate" else "execution", "artifact_classes": lane["artifact_classes"], "dependencies": dependencies, "non_goals": non_goals, "constraints": constraints + extra_constraints, "navigation": navigation, "execution_policy": {"first_reality_target": "R3", "first_reality_budget_fraction": 0.25, "global_bottleneck": route_action.get("capability_id") or lane["mandate"], "documentation_is_not_progress": True, "prefer_existing_capabilities": True, "destination_distance": navigation.get("position", {}).get("destination_distance") if isinstance(navigation.get("position"), Mapping) else None, "waypoint": navigation.get("waypoint"), "objective_velocity": navigation.get("velocity")}}
''',
    )


def patch_skills() -> None:
    path = ROOT / "skills/company-os/company-os/SKILL.md"
    replace_once(
        path,
        '''| Mission execution control | Enforce First Reality scope, work admission, hard deadlines, scheduler leases, evidence-bound capability state, replacement, and product checkpoints at controller boundaries | `$mission-execution-control` |
''',
        '''| Mission execution control | Enforce First Reality scope, work admission, hard deadlines, scheduler leases, evidence-bound capability state, replacement, and product checkpoints at controller boundaries | `$mission-execution-control` |
| Navigation control | Treat the original objective as the destination; continuously observe, act, verify, measure objective distance/velocity, and replan while keeping research/audits as subordinate sensors | `$navigation-control` |
''',
    )
    replace_once(
        path,
        '''For every autonomous build mission, the controller runs `$mission-execution-control` and `$govern-outcome-execution` at dispatch, retry, wake, evidence, expansion, evaluation, and packaging boundaries. These decisions are enforced state, not optional manager advice. The governor is the mission-level CEO/COO/CFO function above local managers.
''',
        '''For every autonomous build mission, the controller runs `$mission-execution-control`, `$navigation-control`, and `$govern-outcome-execution` at dispatch, retry, wake, evidence, expansion, evaluation, and packaging boundaries. These decisions are enforced state, not optional manager advice. The original objective is the destination; research, audits, tests, browser/runtime observations, and reports are sensors; implementation, integration, runtime execution, repair, checkpointing, and packaging are actuators. The governor is the mission-level CEO/COO/CFO function above local managers.
''',
    )

    path = ROOT / "skills/company-os/manage-company-program/SKILL.md"
    replace_once(
        path,
        '''Operate `company-os.manager-role.v2`. The manager exists to make the requested outcome real. Planning, research, architecture, audits, receipts, and governance support execution; they are not substitutes for it. Verify the exact `$mission-execution-control` state and work-admission receipt before dispatch; a paused class, stale generation, replacement order, or expired mission stops the old context.
''',
        '''Operate `company-os.manager-role.v2`. The manager exists to make the requested outcome real. Operate as a destination controller: observe the evidence-bound current state, orient against the original objective and current waypoint, execute the highest-value safe route action, verify the environment changed, and replan. Planning, research, architecture, audits, receipts, and governance are sensor inputs; they are not substitutes for motion. Verify the exact `$mission-execution-control` and `$navigation-control` state plus work-admission receipt before dispatch; a paused class, stale generation, replacement order, stalled trajectory, or expired mission changes or stops the old context.
''',
    )

    path = ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md"
    replace_once(
        path,
        '''2. Stop before work when a dependency is absent, malformed, stale, foreign, or
   unaccepted. Verify the bound `$mission-execution-control` state and work admission;
   stop when the mission generation changed, the work class is paused, the receipt is
   stale, or this worker was replaced. Do not start downstream work speculatively.
''',
        '''2. Stop before work when a dependency is absent, malformed, stale, foreign, or
   unaccepted. Verify the bound `$mission-execution-control`, `$navigation-control`, and
   work admission; stop when the mission generation changed, the work class is paused,
   the receipt is stale, or this worker was replaced. Execute the navigation `next_action`
   before optional support work. Use minimum-sufficient actuation: reuse existing code or
   integrations, then native/stdlib, then installed dependencies, then the smallest new
   code that changes objective reality. Never cut explicit requirements or safety guards.
''',
    )


def main() -> None:
    patch_mission_control()
    patch_director()
    patch_organization()
    patch_skills()
    print("navigation control loop integration applied")


if __name__ == "__main__":
    main()
