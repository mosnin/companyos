#!/usr/bin/env python3
from pathlib import Path
path = Path('tests/test_outcome_director.py')
text = path.read_text(encoding='utf-8')
old = '''        (base / "outcome-loop.json").write_text(json.dumps({"$schema": "company-os.outcome-loop-state.v1"}) + "\\n")
'''
new = '''        (base / "outcome-loop.json").write_text(json.dumps({"$schema": "company-os.outcome-loop-state.v1", "phase": "discovery"}) + "\\n")
'''
if old not in text:
    raise SystemExit('director fake loop fixture marker missing')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('director fixture upgraded for first-reality sequencing')
