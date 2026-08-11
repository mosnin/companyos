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
