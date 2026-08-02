from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_role_skills", ROOT / "scripts/validate_role_skills.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RoleSkillTests(unittest.TestCase):
    def test_role_skills_are_compact_and_versioned(self) -> None:
        self.assertEqual([], MODULE.validate())


if __name__ == "__main__":
    unittest.main()
