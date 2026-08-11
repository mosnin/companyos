#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


director = Path("skills/company-os/direct-outcome/scripts/direct_outcome.py")
replace_once(
    director,
    '    elif work_class in {"research", "architecture", "governance", "documentation"} and not bootstrap:\n',
    '    elif work_class in {"research", "architecture", "governance", "documentation", "evaluation"} and not bootstrap:\n',
)

mission = Path("skills/company-os/mission-execution-control/scripts/mission_control.py")
replace_once(
    mission,
    '        keep_sensors = {"evaluation"} if next_work == "evaluation" else set()\n',
    '        keep_sensors = {"evaluation"}\n',
)

org = Path("skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py")
replace_once(
    org,
    '''    budget = _budget(request.get("budget"), len(lanes))
    manager_budget = _child_budget(budget, len(lanes))
    preserve_dimensions: list[str] = []
''',
    '''    budget = _budget(request.get("budget"), len(lanes))
    manager_budget = _child_budget(budget, len(lanes))
    navigation = mission_control.get("navigation") if isinstance(mission_control.get("navigation"), Mapping) else {}
    route_action = navigation.get("next_action") if isinstance(navigation.get("next_action"), Mapping) else {}
    route_policy = navigation.get("actuation_policy") if isinstance(navigation.get("actuation_policy"), Mapping) else {}
    if state.get("phase") == "evaluate" and route_action.get("work_class") != "evaluation":
        manager_budget = {
            **manager_budget,
            "time_minutes": min(float(manager_budget["time_minutes"]), 10.0),
            "token_limit": min(int(manager_budget["token_limit"]), 3000),
            "cost_usd": min(float(manager_budget["cost_usd"]), 3.0),
            "max_concurrency": 1,
            "max_retries": 0,
        }
    preserve_dimensions: list[str] = []
''',
)
replace_once(
    org,
    '''    navigation = mission_control.get("navigation") if isinstance(mission_control.get("navigation"), Mapping) else {}
    route_action = navigation.get("next_action") if isinstance(navigation.get("next_action"), Mapping) else {}
    route_policy = navigation.get("actuation_policy") if isinstance(navigation.get("actuation_policy"), Mapping) else {}
    replace_manager = any(item.get("kind") == "replace_manager" for item in replacement_orders)
''',
    '''    replace_manager = any(item.get("kind") == "replace_manager" for item in replacement_orders)
''',
)
replace_once(
    org,
    '''            worker_task = lane["mandate"] + " Navigation route action: " + json.dumps(route_action, sort_keys=True) + ". Evaluate only because verification is the current route action or a safety interrupt requires it. Score only the bound dimensions: " + ", ".join(lane["score_dimensions"]) + "."
''',
    '''            sensor_reason = "Verification is the current route action." if route_action.get("work_class") == "evaluation" else "This is a bounded sensor interrupt; inspect only what can change route confidence or trigger targeted repair, then return control to the active route."
            worker_task = lane["mandate"] + " Navigation route action: " + json.dumps(route_action, sort_keys=True) + ". " + sensor_reason + " Score only the bound dimensions: " + ", ".join(lane["score_dimensions"]) + "."
''',
)
print("navigation followup applied")
