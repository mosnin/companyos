#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

path = Path("scripts/apply_execution_enforcement_v2.py")
text = path.read_text(encoding="utf-8")
old = (
    "        '''    return {\"program_id\": project_id, \"topology_mode\": TOPOLOGY_MODE, \"engineering_execution_contract\": master_engineering,\n"
    "''',\n"
    "        '''    return {\"program_id\": project_id, \"topology_mode\": TOPOLOGY_MODE, \"mission_control\": mission_control, \"work_admission\": admission, \"engineering_execution_contract\": master_engineering,\n"
    "''',\n"
)
new = (
    "        '''    return {\"program_id\": project_id, \"topology_mode\": TOPOLOGY_MODE, \"engineering_execution_contract\": master_engineering, \"program_version\":''',\n"
    "        '''    return {\"program_id\": project_id, \"topology_mode\": TOPOLOGY_MODE, \"mission_control\": mission_control, \"work_admission\": admission, \"engineering_execution_contract\": master_engineering, \"program_version\":''',\n"
)
if text.count(old) != 1:
    raise SystemExit(f"migration anchor repair expected one match, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

governor = Path("skills/company-os/govern-outcome-execution/scripts/executive_governor.py")
governor_text = governor.read_text(encoding="utf-8")
governor_old = "    elif budget_fraction >= 0.40 and reality_level < 3:\n        mode = \"compression\"\n"
governor_new = "    elif first_reality_incident or (budget_fraction >= 0.40 and reality_level < 3):\n        mode = \"compression\"\n"
if governor_text.count(governor_old) != 1:
    raise SystemExit(f"governor mode repair expected one match, found {governor_text.count(governor_old)}")
governor.write_text(governor_text.replace(governor_old, governor_new, 1), encoding="utf-8")

runpy.run_path(str(path), run_name="__main__")
