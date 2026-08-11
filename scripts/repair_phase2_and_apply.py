#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

phase2 = Path("scripts/apply_execution_enforcement_v2_phase2.py")
text = phase2.read_text(encoding="utf-8")

method_patch = "    replace_once(path, '    def test_two_evaluators_are_maximum_batch(self):\\n', '    def test_one_evaluator_is_maximum_economic_batch(self):\\n')\n"
assertion_patch = "    replace_once(path, '        self.assertEqual(result[\"calibration_evaluator_ids\"], [\"eval-0\", \"eval-1\"])\\n        self.assertEqual(result[\"remaining_evaluator_ids\"], [\"eval-2\"])\\n', '        self.assertEqual(result[\"calibration_evaluator_ids\"], [\"eval-0\"])\\n        self.assertEqual(result[\"remaining_evaluator_ids\"], [\"eval-1\", \"eval-2\"])\\n        self.assertLessEqual(result[\"fabric\"][\"budget\"][\"time_minutes\"], 30.0)\\n')\n"
if text.count(method_patch) != 1 or text.count(assertion_patch) != 1:
    raise SystemExit("phase 2 calibration migration anchors are unavailable")
text = text.replace(method_patch, "", 1).replace(assertion_patch, "", 1)
phase2.write_text(text, encoding="utf-8")

calibration = Path("tests/test_calibration_fabric.py")
calibration_text = calibration.read_text(encoding="utf-8")
old = '''    def test_two_evaluators_are_maximum_batch(self) -> None:
        self.write_contracts(3)
        result = self.compile()
        self.assertEqual(result["calibration_evaluator_ids"], ["eval-0", "eval-1"])
        self.assertEqual(result["remaining_evaluator_ids"], ["eval-2"])
        self.assertEqual(len(result["fabric"]["managers"]), 2)
        self.assertEqual(sum(len(manager["workers"]) for manager in result["fabric"]["managers"]), 6)
        self.assertTrue(MODULE.fabric_module().validate(result["fabric"])["valid"])
'''
new = '''    def test_one_evaluator_is_maximum_economic_batch(self) -> None:
        self.write_contracts(3)
        result = self.compile()
        self.assertEqual(result["calibration_evaluator_ids"], ["eval-0"])
        self.assertEqual(result["remaining_evaluator_ids"], ["eval-1", "eval-2"])
        self.assertEqual(len(result["fabric"]["managers"]), 1)
        self.assertEqual(sum(len(manager["workers"]) for manager in result["fabric"]["managers"]), 3)
        self.assertLessEqual(result["fabric"]["budget"]["time_minutes"], 30.0)
        self.assertTrue(MODULE.fabric_module().validate(result["fabric"])["valid"])
'''
if calibration_text.count(old) != 1:
    raise SystemExit(f"calibration test block expected once, found {calibration_text.count(old)}")
calibration.write_text(calibration_text.replace(old, new, 1), encoding="utf-8")

runpy.run_path(str(phase2), run_name="__main__")

director = Path("skills/company-os/direct-outcome/scripts/direct_outcome.py")
director_text = director.read_text(encoding="utf-8")
replacements = {
    '                "modalities": list(raw.get("modalities", [])),\n': '                "modalities": list(raw.get("modalities") or ["executable"]),\n',
    '                "observation_methods": list(raw.get("observation_methods", [])),\n': '                "observation_methods": list(raw.get("observation_methods") or ["runtime"]),\n',
    '                "required_evidence": list(raw.get("required_evidence", [])),\n': '                "required_evidence": list(raw.get("required_evidence") or ["runtime_receipt"]),\n',
}
for source, target in replacements.items():
    if director_text.count(source) != 1:
        raise SystemExit(f"director default anchor expected once, found {director_text.count(source)}")
    director_text = director_text.replace(source, target, 1)
director.write_text(director_text, encoding="utf-8")
