from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "company-os" / "steve"
SCRIPT = SKILL / "scripts" / "validate_steve_doctrine.py"
SPEC = importlib.util.spec_from_file_location("validate_steve_doctrine", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SteveDoctrineTests(unittest.TestCase):
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
        charter = (SKILL / "references/source/01-charter-standards.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("It is not Steve Jobs", charter)
        self.assertIn("does not claim his experiences", charter)

    def test_spawn_template_is_lane_specific(self) -> None:
        template = json.loads((SKILL / "assets/spawn-template.json").read_text(encoding="utf-8"))
        self.assertEqual(
            template["use_when"],
            [
                "branding",
                "customer_experience",
                "product_design",
                "user_experience",
            ],
        )
        mutated = dict(template)
        mutated["use_when"] = ["general_management"]
        self.assertIn(
            "use_when must be the product, brand, UX, and customer lanes",
            MODULE.validate_spawn_template(mutated),
        )

    def test_spawn_template_rejects_worker_or_master_role(self) -> None:
        template = json.loads((SKILL / "assets/spawn-template.json").read_text(encoding="utf-8"))
        for role in ("master", "worker"):
            with self.subTest(role=role):
                mutated = dict(template)
                mutated["role"] = role
                self.assertIn("spawn role must be manager", MODULE.validate_spawn_template(mutated))

    def test_product_lanes_point_at_steve(self) -> None:
        paths = (
            ROOT / "skills/company-os/company-os/SKILL.md",
            ROOT / "skills/company-os/brand-creative-system/SKILL.md",
            ROOT / "skills/company-os/commercial-customer-system/SKILL.md",
            ROOT / "skills/company-os/ui-design-quality/SKILL.md",
        )
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = " ".join(path.read_text(encoding="utf-8").split())
                self.assertIn("$steve", text)

    def test_company_os_does_not_send_steve_to_every_manager(self) -> None:
        text = " ".join(
            (ROOT / "skills/company-os/company-os/SKILL.md").read_text(encoding="utf-8").split()
        )
        self.assertIn(
            "When the manager outcome is product design, brand, user experience, or customer experience, also send `$steve`.",
            text,
        )
        self.assertIn("Do not send `$steve` to workers", text)

    def test_general_manager_role_skill_does_not_require_steve(self) -> None:
        text = (
            ROOT / "skills/company-os/manage-company-program/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("$steve", text)

    def test_worker_role_skill_does_not_load_steve(self) -> None:
        text = (
            ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("$steve", text)

    def test_host_bindings_stay_explicit_and_lane_bound(self) -> None:
        for name in ("openai.yaml", "grok.yaml"):
            text = (SKILL / "agents" / name).read_text(encoding="utf-8")
            self.assertIn("$steve", text)
            self.assertIn("$manage-company-program", text)
            self.assertIn("product, brand, UX, or customer work", text)
            self.assertIn("allow_implicit_invocation: false", text)


if __name__ == "__main__":
    unittest.main()
