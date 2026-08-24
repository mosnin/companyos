from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "company-os" / "middle-manager-operating-doctrine"
SCRIPT = SKILL / "scripts" / "validate_middle_manager_doctrine.py"
SPEC = importlib.util.spec_from_file_location("validate_middle_manager_doctrine", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MiddleManagerDoctrineTests(unittest.TestCase):
    def test_pack_and_spawn_template_validate(self) -> None:
        self.assertEqual([], MODULE.validate_pack(SKILL))

    def test_cli_accepts_canonical_pack(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(SKILL)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual([], payload["errors"])

    def test_source_pack_preserves_identity_boundary(self) -> None:
        charter = (SKILL / "references/source/01-charter-ground-rules.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("It is not Elon Musk", charter)
        self.assertIn("does not claim his personal experiences", charter)

    def test_spawn_template_rejects_worker_or_master_role(self) -> None:
        template = json.loads((SKILL / "assets/spawn-template.json").read_text(encoding="utf-8"))
        for role in ("master", "worker"):
            with self.subTest(role=role):
                mutated = dict(template)
                mutated["role"] = role
                errors = MODULE.validate_spawn_template(mutated)
                self.assertIn("spawn role must be manager", errors)

    def test_spawn_template_rejects_missing_forbidden_role(self) -> None:
        template = json.loads((SKILL / "assets/spawn-template.json").read_text(encoding="utf-8"))
        template["forbidden_roles"] = ["master"]
        self.assertIn(
            "forbidden_roles must be master and worker",
            MODULE.validate_spawn_template(template),
        )

    def test_spawn_template_rejects_worker_skill_bundle(self) -> None:
        template = json.loads((SKILL / "assets/spawn-template.json").read_text(encoding="utf-8"))
        template["skills"] = ["execute-bounded-task", "middle-manager-operating-doctrine"]
        self.assertIn(
            "spawn skills must be the manager role skill plus this doctrine",
            MODULE.validate_spawn_template(template),
        )

    def test_manager_role_skill_requires_the_doctrine(self) -> None:
        text = (
            ROOT / "skills/company-os/manage-company-program/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("$middle-manager-operating-doctrine", text)
        self.assertLessEqual(len(text.split()), 700)

    def test_master_spawn_path_sends_doctrine_only_to_managers(self) -> None:
        text = (ROOT / "skills/company-os/company-os/SKILL.md").read_text(encoding="utf-8")
        compact = " ".join(text.split())
        self.assertIn("$middle-manager-operating-doctrine", compact)
        self.assertIn("Do not use the doctrine as the master persona", compact)
        self.assertIn("Send workers only the worker packet", compact)

    def test_worker_role_skill_does_not_load_the_doctrine(self) -> None:
        text = (
            ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("middle-manager-operating-doctrine", text)

    def test_host_bindings_stay_manager_explicit(self) -> None:
        for name in ("openai.yaml", "grok.yaml"):
            text = (SKILL / "agents" / name).read_text(encoding="utf-8")
            self.assertIn("$middle-manager-operating-doctrine", text)
            self.assertIn("$manage-company-program", text)
            self.assertIn("Do not load this skill on the master or on Luna workers", text)
            self.assertIn("allow_implicit_invocation: false", text)


if __name__ == "__main__":
    unittest.main()
