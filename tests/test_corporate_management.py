from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "company-os" / "corporate-management"
SCRIPT = SKILL / "scripts" / "validate_corporate_management.py"
SPEC = importlib.util.spec_from_file_location("validate_corporate_management", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CorporateManagementTests(unittest.TestCase):
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

    def test_source_pack_has_six_doctrine_sections(self) -> None:
        names = sorted(
            path.name
            for path in (SKILL / "references/source").iterdir()
            if path.is_file()
        )
        self.assertEqual(len(names), 7)
        self.assertIn("00-index.txt", names)
        self.assertIn("04-tier-to-company-os-mapping.txt", names)
        mapping = (SKILL / "references/source/04-tier-to-company-os-mapping.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("master → manager → worker", mapping)
        self.assertIn("not a new runtime role", mapping.casefold())

    def test_spawn_template_is_organization_lane_specific(self) -> None:
        template = json.loads((SKILL / "assets/spawn-template.json").read_text(encoding="utf-8"))
        self.assertEqual(template["use_when"], list(MODULE.USE_WHEN))
        mutated = dict(template)
        mutated["use_when"] = ["general_management"]
        self.assertIn(
            "use_when must be the corporate-management lanes",
            MODULE.validate_spawn_template(mutated),
        )

    def test_spawn_template_rejects_worker_or_master_role(self) -> None:
        template = json.loads((SKILL / "assets/spawn-template.json").read_text(encoding="utf-8"))
        for role in ("master", "worker"):
            with self.subTest(role=role):
                mutated = dict(template)
                mutated["role"] = role
                self.assertIn("spawn role must be manager", MODULE.validate_spawn_template(mutated))

    def test_organization_lanes_point_at_corporate_management(self) -> None:
        paths = (
            ROOT / "skills/company-os/company-os/SKILL.md",
            ROOT / "skills/company-os/company-blueprint/SKILL.md",
            ROOT / "skills/company-os/department-charters/SKILL.md",
        )
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("$corporate-management", path.read_text(encoding="utf-8"))

    def test_company_os_does_not_send_corporate_management_to_every_manager(self) -> None:
        text = " ".join(
            (ROOT / "skills/company-os/company-os/SKILL.md").read_text(encoding="utf-8").split()
        )
        self.assertIn(
            "When compiling a company or spawning a multi-manager program, also send `$corporate-management` and name each actor as senior, middle, low-level, or staff.",
            text,
        )
        self.assertIn("Do not send `$corporate-management` to workers", text)
        self.assertIn("master → manager → worker", text)

    def test_general_manager_role_skill_does_not_require_corporate_management(self) -> None:
        text = (
            ROOT / "skills/company-os/manage-company-program/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("$corporate-management", text)

    def test_worker_role_skill_does_not_load_corporate_management(self) -> None:
        text = (
            ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("$corporate-management", text)

    def test_fabric_delegation_cap_is_unchanged(self) -> None:
        fabric = (
            ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("master → manager → worker", fabric)
        self.assertNotIn("$corporate-management", fabric)

    def test_host_bindings_stay_explicit_and_lane_bound(self) -> None:
        for name in ("openai.yaml", "grok.yaml", "claude.yaml"):
            text = (SKILL / "agents" / name).read_text(encoding="utf-8")
            self.assertIn("$corporate-management", text)
            self.assertIn("$manage-company-program", text)
            self.assertIn("senior, middle, low-level, or staff", text)
            self.assertIn("allow_implicit_invocation: false", text)


if __name__ == "__main__":
    unittest.main()
