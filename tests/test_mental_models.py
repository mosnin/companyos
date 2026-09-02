"""The mental-models reasoning pack: twelve models, zero authority.

Pins the default thinking layer's invariants: every model present in both
the doctrine and the catalog, the overlay open to every role (unlike the
lane personas), authority disclaimed, and the validator failing loudly when
a model is dropped or the template quietly narrows or widens.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "company-os" / "mental-models"
SCRIPT = SKILL / "scripts" / "validate_mental_models.py"
SPEC = importlib.util.spec_from_file_location("validate_mental_models", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MentalModelsPackTests(unittest.TestCase):
    def test_pack_and_spawn_template_validate(self) -> None:
        self.assertEqual([], MODULE.validate_pack(SKILL))

    def test_cli_accepts_canonical_pack(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(SKILL)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_all_twelve_models_are_pinned(self) -> None:
        self.assertEqual(12, len(MODULE.MODEL_MARKERS))

    def test_template_is_role_universal(self) -> None:
        template = json.loads(
            (SKILL / "assets/spawn-template.json").read_text(encoding="utf-8")
        )
        self.assertEqual("any", template["role"])
        self.assertEqual([], template["forbidden_roles"])
        self.assertEqual("thinking_overlay", template["authority"])

    def test_template_rejects_role_narrowing(self) -> None:
        template = json.loads(
            (SKILL / "assets/spawn-template.json").read_text(encoding="utf-8")
        )
        for mutation in (
            {"role": "manager"},
            {"forbidden_roles": ["worker"]},
            {"authority": "dispatch"},
        ):
            mutated = {**template, **mutation}
            self.assertNotEqual([], MODULE.validate_spawn_template(mutated), mutation)

    def test_dropping_a_model_fails_validation(self) -> None:
        # Simulate a doctrine edit that loses Hanlon: the validator must say so.
        import tempfile
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "mental-models"
            shutil.copytree(SKILL, copy)
            skill_md = copy / "SKILL.md"
            skill_md.write_text(
                skill_md.read_text(encoding="utf-8").replace("Hanlon", "H4nlon"),
                encoding="utf-8",
            )
            errors = MODULE.validate_pack(copy)
            self.assertTrue(any("hanlon" in error for error in errors), errors)

    def test_doctrine_reaches_every_role_surface(self) -> None:
        # The default layer is wired into the skills every role already
        # loads: the master map, the manager doctrine, and the dispatch loop.
        for relative in (
            "skills/company-os/company-os/SKILL.md",
            "skills/company-os/middle-manager-operating-doctrine/SKILL.md",
            "skills/company-os/mission-execution-control/SKILL.md",
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("mental-models", text, relative)


if __name__ == "__main__":
    unittest.main()
