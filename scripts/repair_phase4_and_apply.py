#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

phase = Path("scripts/apply_execution_enforcement_v2_phase4.py")
text = phase.read_text(encoding="utf-8")
replacements = {
    'path.write_text(json.dumps(mission, indent=2, sort_keys=True) + "\\n", encoding="utf-8")':
        'path.write_text(json.dumps(mission, indent=2, sort_keys=True) + "\\\\n", encoding="utf-8")',
    '(self.root / ".company-os/mission.json").write_text(json.dumps(mission, indent=2, sort_keys=True) + "\\n", encoding="utf-8")':
        '(self.root / ".company-os/mission.json").write_text(json.dumps(mission, indent=2, sort_keys=True) + "\\\\n", encoding="utf-8")',
}
for old, new in replacements.items():
    if text.count(old) != 1:
        raise SystemExit(f"phase 4 escape anchor expected once, found {text.count(old)}: {old}")
    text = text.replace(old, new, 1)
phase.write_text(text, encoding="utf-8")
runpy.run_path(str(phase), run_name="__main__")

mission = Path("skills/company-os/mission-execution-control/scripts/mission_control.py")
mission_text = mission.read_text(encoding="utf-8")
old = "    state = refresh_governor(reconcile_deadlines(raw_state, now=now), now=now)\n"
new = "    del now\n    state = verify_state(raw_state)\n"
if mission_text.count(old) != 1:
    raise SystemExit(f"admission state anchor expected once, found {mission_text.count(old)}")
mission.write_text(mission_text.replace(old, new, 1), encoding="utf-8")
