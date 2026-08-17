from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "company-os" / "value-creation-delivery"
SCRIPT = SKILL / "scripts" / "validate_value_creation_delivery.py"
SPEC = importlib.util.spec_from_file_location("validate_value_creation_delivery", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ValueCreationDeliveryTests(unittest.TestCase):
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

    def test_source_pack_has_ten_doctrine_sections(self) -> None:
        names = sorted(
            path.name
            for path in (SKILL / "references/source").iterdir()
            if path.is_file()
        )
        self.assertEqual(len(names), 12)
        self.assertIn("00-index.txt", names)
        self.assertIn("10-integrated-playbooks-templates.txt", names)
        self.assertIn("cold-start-problem.md", names)
        cold_start = (SKILL / "references/source/cold-start-problem.md").read_text(encoding="utf-8")
        self.assertTrue(cold_start.startswith("# The Cold Start Problem Advanced Guide"))
        self.assertIn("atomic network", cold_start.casefold())
        self.assertIn("never scale a broken atomic network", cold_start.casefold())

    def test_spawn_template_is_value_lane_specific(self) -> None:
        template = json.loads((SKILL / "assets/spawn-template.json").read_text(encoding="utf-8"))
        self.assertEqual(template["use_when"], list(MODULE.USE_WHEN))
        mutated = dict(template)
        mutated["use_when"] = ["general_management"]
        self.assertIn(
            "use_when must be the value-system lanes",
            MODULE.validate_spawn_template(mutated),
        )

    def test_spawn_template_rejects_worker_or_master_role(self) -> None:
        template = json.loads((SKILL / "assets/spawn-template.json").read_text(encoding="utf-8"))
        for role in ("master", "worker"):
            with self.subTest(role=role):
                mutated = dict(template)
                mutated["role"] = role
                self.assertIn("spawn role must be manager", MODULE.validate_spawn_template(mutated))

    def test_value_lanes_point_at_value_creation_delivery(self) -> None:
        paths = (
            ROOT / "skills/company-os/company-os/SKILL.md",
            ROOT / "skills/company-os/commercial-customer-system/SKILL.md",
            ROOT / "skills/company-os/company-blueprint/SKILL.md",
        )
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn("$value-creation-delivery", path.read_text(encoding="utf-8"))

    def test_company_os_does_not_send_value_creation_delivery_to_every_manager(self) -> None:
        text = " ".join(
            (ROOT / "skills/company-os/company-os/SKILL.md").read_text(encoding="utf-8").split()
        )
        self.assertIn(
            "When the manager outcome is value creation, offer architecture, value validation, value delivery, or scaling a delivery system, also send `$value-creation-delivery`.",
            text,
        )
        self.assertIn("Do not send `$value-creation-delivery` to workers", text)

    def test_general_manager_role_skill_does_not_require_value_creation_delivery(self) -> None:
        text = (
            ROOT / "skills/company-os/manage-company-program/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("$value-creation-delivery", text)

    def test_worker_role_skill_does_not_load_value_creation_delivery(self) -> None:
        text = (
            ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("$value-creation-delivery", text)

    def test_host_bindings_stay_explicit_and_lane_bound(self) -> None:
        for name in ("openai.yaml", "grok.yaml"):
            text = (SKILL / "agents" / name).read_text(encoding="utf-8")
            self.assertIn("$value-creation-delivery", text)
            self.assertIn("$manage-company-program", text)
            self.assertIn(
                "value creation, offer architecture, value validation, value delivery, or scaling a delivery system",
                text,
            )
            self.assertIn("allow_implicit_invocation: false", text)


if __name__ == "__main__":
    unittest.main()
