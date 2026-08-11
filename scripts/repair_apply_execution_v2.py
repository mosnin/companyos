#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

path = Path("scripts/apply_execution_enforcement_v2.py")
text = path.read_text(encoding="utf-8")
old = '''        ''' + "'''" + '''    return {"program_id": project_id, "topology_mode": TOPOLOGY_MODE, "engineering_execution_contract": master_engineering,
''',
        ''' + "'''" + '''    return {"program_id": project_id, "topology_mode": TOPOLOGY_MODE, "mission_control": mission_control, "work_admission": admission, "engineering_execution_contract": master_engineering,
''',
'''
new = '''        ''' + "'''" + '''    return {"program_id": project_id, "topology_mode": TOPOLOGY_MODE, "engineering_execution_contract": master_engineering, "program_version":''',
        ''' + "'''" + '''    return {"program_id": project_id, "topology_mode": TOPOLOGY_MODE, "mission_control": mission_control, "work_admission": admission, "engineering_execution_contract": master_engineering, "program_version":''',
'''
if text.count(old) != 1:
    raise SystemExit(f"migration anchor repair expected one match, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
runpy.run_path(str(path), run_name="__main__")
