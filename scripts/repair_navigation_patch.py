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
director.write_text(director_text.replace(old_units, new_units, 1), encoding="utf-8")

# This temporary migration script is intentionally rerunnable only against the
# unintegrated branch tree; permanent runtime files remain the source of truth.
