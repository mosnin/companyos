#!/usr/bin/env python3
from pathlib import Path
import runpy

patch = Path("scripts/apply_navigation_control_loop.py")
text = patch.read_text(encoding="utf-8")
old = "For every autonomous build mission, the controller runs `$mission-execution-control` and `$govern-outcome-execution` at dispatch, retry, wake, rework, evaluation, scope expansion, and packaging boundaries. These decisions are enforced state, not optional manager advice. The governor is the mission-level CEO/COO/CFO function above local managers."
new = "For every autonomous build mission, the controller runs `$mission-execution-control` and `$govern-outcome-execution` at dispatch, retry, wake, evidence, expansion, evaluation, and packaging boundaries. These decisions are enforced state, not optional manager advice. The governor is the mission-level CEO/COO/CFO function above local managers."
replacement = "For every autonomous build mission, the controller runs `$mission-execution-control`, `$navigation-control`, and `$govern-outcome-execution` at dispatch, retry, wake, evidence, expansion, evaluation, and packaging boundaries. These decisions are enforced state, not optional manager advice. The original objective is the destination; research, audits, tests, browser/runtime observations, and reports are sensors; implementation, integration, runtime execution, repair, checkpointing, and packaging are actuators. The governor is the mission-level CEO/COO/CFO function above local managers."
if old not in text:
    raise SystemExit("old navigation skill anchor missing")
text = text.replace(old, new, 1)
text = text.replace(
    "For every autonomous build mission, the controller runs `$mission-execution-control`, `$navigation-control`, and `$govern-outcome-execution` at dispatch, retry, wake, rework, evaluation, scope expansion, and packaging boundaries. These decisions are enforced state, not optional manager advice. The original objective is the destination; research, audits, tests, browser/runtime observations, and reports are sensors; implementation, integration, runtime execution, repair, checkpointing, and packaging are actuators. The governor is the mission-level CEO/COO/CFO function above local managers.",
    replacement,
    1,
)
patch.write_text(text, encoding="utf-8")
runpy.run_path(str(patch), run_name="__main__")

# Initial discovery is a sensor+actuator pair. Charge the sensor at a bounded
# fraction so the act of starting one research lane cannot immediately pause
# itself before the reality spike gets a chance to move the mission.
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
# research or documentation.
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

# This temporary migration script is intentionally rerunnable only against the
# unintegrated branch tree; permanent runtime files remain the source of truth.
