#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

phase = Path("scripts/apply_execution_enforcement_v2_phase5.py")
phase_text = phase.read_text(encoding="utf-8")
replacements = {
    '    admissions: dict[str, dict[str, Any]] = {}\n':
        '    admissions: dict[str, dict[str, Any]] = {}\n    admission_refs: dict[str, dict[str, Any]] = {}\n',
    '''        admissions[work_class] = {
            **receipt,
            "receipt_path": relative(project_root, receipt_path),
            "receipt_file_sha256": file_digest(receipt_path),
        }
''':
        '''        admissions[work_class] = receipt
        admission_refs[work_class] = {
            "receipt_path": relative(project_root, receipt_path),
            "receipt_file_sha256": file_digest(receipt_path),
            "receipt_sha256": receipt["receipt_sha256"],
        }
''',
    '    bound["work_admissions"] = admissions\n':
        '    bound["work_admissions"] = admissions\n    bound["work_admission_refs"] = admission_refs\n',
    '''        "work_admissions": admissions,
        "fabric_path": fabric_relative,
''':
        '''        "work_admissions": admissions,
        "work_admission_refs": admission_refs,
        "fabric_path": fabric_relative,
''',
}
for old, new in replacements.items():
    if phase_text.count(old) != 1:
        raise SystemExit(f"phase 5 admission anchor expected once, found {phase_text.count(old)}: {old[:80]}")
    phase_text = phase_text.replace(old, new, 1)
phase.write_text(phase_text, encoding="utf-8")

runpy.run_path(str(phase), run_name="__main__")

path = Path("tests/test_outcome_director.py")
text = path.read_text(encoding="utf-8")
old = '''        MODULE.evaluator_build_module = lambda: FakeEvaluatorBuild
        MODULE.calibration_fabric_module = lambda: FakeCalibrationFabric
        self.state = MODULE.start(self.project, "viral-game", "Make a viral game.")
'''
new = '''        MODULE.evaluator_build_module = lambda: FakeEvaluatorBuild
        MODULE.calibration_fabric_module = lambda: FakeCalibrationFabric
        MODULE.bind_discovery_fabric = lambda project_root, objective_id, fabric_relative: {
            "mission_control": MODULE.mission_binding(project_root, objective_id),
            "work_admissions": {},
            "work_admission_refs": {},
            "fabric_path": fabric_relative,
            "fabric_file_sha256": MODULE.file_digest(project_root / Path(*fabric_relative.split("/"))),
        }
        MODULE.verify_bound_discovery_fabric = lambda *args, **kwargs: {}
        self.state = MODULE.start(self.project, "viral-game", "Make a viral game.")
'''
if text.count(old) != 1:
    raise SystemExit(f"director fixture anchor expected once, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
