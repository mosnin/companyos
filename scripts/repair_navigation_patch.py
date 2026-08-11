#!/usr/bin/env python3
from pathlib import Path
import runpy

# Apply the primary closed-loop integration against the clean branch source.
runpy.run_path("scripts/apply_navigation_control_loop.py", run_name="__main__")

# Initial discovery is a sensor+actuator pair. Charge the sensor at a bounded
# fraction so starting focused research cannot immediately pause itself before
# the reality spike gets a chance to move the mission.
director = Path("skills/company-os/direct-outcome/scripts/direct_outcome.py")
director_text = director.read_text(encoding="utf-8")
old_units = '''                work_class=work_class,
                units=1.0,
'''
new_units = '''                work_class=work_class,
                units=0.25 if work_class == "research" else 1.0,
'''
if director_text.count(old_units) != 1:
    raise SystemExit(f"discovery unit anchor expected once, found {director_text.count(old_units)}")
director_text = director_text.replace(old_units, new_units, 1)

# Route-bound sensor work must stand on its blocker/decision binding; the
# director may not self-assert that an action is blocked merely to admit more
# research. Evaluation is included so the outcome loop can run a short sensor
# pass without pretending that evaluation is the destination.
old_sensor_set = '    elif work_class in {"research", "architecture", "governance", "documentation"} and not bootstrap:\n'
new_sensor_set = '    elif work_class in {"research", "architecture", "governance", "documentation", "evaluation"} and not bootstrap:\n'
if director_text.count(old_sensor_set) != 1:
    raise SystemExit(f"director sensor set anchor expected once, found {director_text.count(old_sensor_set)}")
director_text = director_text.replace(old_sensor_set, new_sensor_set, 1)
old_auto = '''            "decision_dependency": "Resolve only the uncertainty that blocks or materially changes the active navigation action.",
            "deadline_minutes": 15,
            "current_action_blocked": True,
            "expected_action_change": True,
'''
new_auto = '''            "decision_dependency": "Resolve only the uncertainty that blocks or materially changes the active navigation action.",
            "deadline_minutes": 15,
            "expected_action_change": True,
'''
if director_text.count(old_auto) != 1:
    raise SystemExit(f"auto sensor justification anchor expected once, found {director_text.count(old_auto)}")
director.write_text(director_text.replace(old_auto, new_auto, 1), encoding="utf-8")

# Safety is an interrupt, not a general research escape hatch. A safety sensor
# requires concrete hazard evidence; a claimed blocked action must still bind
# the active route capability.
nav = Path("skills/company-os/navigation-control/scripts/navigation_control.py")
nav_text = nav.read_text(encoding="utf-8")
old_sensor = '''    target = next_action.get("capability_id")
    if current_action_blocked:
        return True, "current actuation is explicitly blocked by this uncertainty"
    if target is not None and blocker == target and expected_change:
        return True, "sensor question is bound to the active route blocker and can change the next action"
'''
new_sensor = '''    target = next_action.get("capability_id")
    safety_interrupt = request.get("safety_interrupt") is True
    hazard_evidence = request.get("hazard_evidence")
    if safety_interrupt:
        if isinstance(hazard_evidence, str) and hazard_evidence.strip():
            return True, "concrete safety hazard interrupts the route"
        return False, "safety interrupt requires concrete hazard evidence"
    if current_action_blocked:
        if target is not None and blocker == target:
            return True, "active route action is explicitly blocked by this uncertainty"
        return False, "claimed blocked action is not bound to the active route capability"
    if target is not None and blocker == target and expected_change:
        return True, "sensor question is bound to the active route blocker and can change the next action"
'''
if nav_text.count(old_sensor) != 1:
    raise SystemExit(f"sensor policy anchor expected once, found {nav_text.count(old_sensor)}")
nav.write_text(nav_text.replace(old_sensor, new_sensor, 1), encoding="utf-8")

# When evaluation is not itself the active route action, it is a bounded sensor
# interrupt rather than a full phase-sized activity.
org = Path("skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py")
org_text = org.read_text(encoding="utf-8")
old_budget = '''    budget = _budget(request.get("budget"), len(lanes))
    manager_budget = _child_budget(budget, len(lanes))
    preserve_dimensions: list[str] = []
'''
new_budget = '''    budget = _budget(request.get("budget"), len(lanes))
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
'''
if org_text.count(old_budget) != 1:
    raise SystemExit(f"organization budget anchor expected once, found {org_text.count(old_budget)}")
org_text = org_text.replace(old_budget, new_budget, 1)
old_duplicate = '''    navigation = mission_control.get("navigation") if isinstance(mission_control.get("navigation"), Mapping) else {}
    route_action = navigation.get("next_action") if isinstance(navigation.get("next_action"), Mapping) else {}
    route_policy = navigation.get("actuation_policy") if isinstance(navigation.get("actuation_policy"), Mapping) else {}
    replace_manager = any(item.get("kind") == "replace_manager" for item in replacement_orders)
'''
new_duplicate = '''    replace_manager = any(item.get("kind") == "replace_manager" for item in replacement_orders)
'''
if org_text.count(old_duplicate) != 1:
    raise SystemExit(f"duplicate navigation locals expected once, found {org_text.count(old_duplicate)}")
org.write_text(org_text.replace(old_duplicate, new_duplicate, 1), encoding="utf-8")

print("navigation control loop integration repaired and applied")
