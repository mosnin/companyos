#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

runpy.run_path("scripts/apply_execution_enforcement_v2_phase5.py", run_name="__main__")

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
            "fabric_path": fabric_relative,
            "fabric_file_sha256": MODULE.file_digest(project_root / Path(*fabric_relative.split("/"))),
        }
        MODULE.verify_bound_discovery_fabric = lambda *args, **kwargs: {}
        self.state = MODULE.start(self.project, "viral-game", "Make a viral game.")
'''
if text.count(old) != 1:
    raise SystemExit(f"director fixture anchor expected once, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
