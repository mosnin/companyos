from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_skill_surface.py"
spec = importlib.util.spec_from_file_location("validate_skill_surface", SCRIPT)
assert spec and spec.loader
LINTER = importlib.util.module_from_spec(spec)
spec.loader.exec_module(LINTER)


class SkillSurfaceTests(unittest.TestCase):
    def test_every_first_class_skill_is_structurally_valid(self) -> None:
        findings = LINTER.audit_surface()
        self.assertEqual(
            findings,
            {},
            "first-class skills with structural violations: "
            + "; ".join(f"{skill}: {problems}" for skill, problems in findings.items()),
        )

    def test_linter_scans_the_expected_first_class_surface(self) -> None:
        scanned = [
            path for path in LINTER.SKILLS_ROOT.rglob("SKILL.md") if LINTER.is_first_class(path)
        ]
        # Guard against the scope filter silently excluding everything.
        self.assertGreaterEqual(len(scanned), 60)
        for path in scanned:
            self.assertNotIn("vendor", path.relative_to(LINTER.SKILLS_ROOT).parts)
            self.assertNotIn("references", path.relative_to(LINTER.SKILLS_ROOT).parts)


if __name__ == "__main__":
    unittest.main()
