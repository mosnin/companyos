from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/company-os/interface-design"
PINNED_COMMIT = "ba35986bcf433fdca78ea571b0a3dc329cea89ba"


class InterfaceDesignTests(unittest.TestCase):
    def test_full_pinned_upstream_suite_is_present_and_byte_exact(self) -> None:
        provenance = json.loads((SKILL_ROOT / "UPSTREAM.json").read_text(encoding="utf-8"))
        self.assertEqual(PINNED_COMMIT, provenance["source_commit"])
        self.assertEqual("https://github.com/jakubkrehel/skills", provenance["source_repository"])
        expected = provenance["files"]
        actual_paths = {
            path.relative_to(SKILL_ROOT).as_posix()
            for path in (SKILL_ROOT / "vendor").rglob("*")
            if path.is_file()
        }
        self.assertEqual(set(expected), actual_paths)
        for relative, digest in expected.items():
            path = SKILL_ROOT / relative
            self.assertFalse(path.is_symlink())
            self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_all_eight_skill_entrypoints_match_the_provenance_index(self) -> None:
        provenance = json.loads((SKILL_ROOT / "UPSTREAM.json").read_text(encoding="utf-8"))
        actual = []
        for path in sorted((SKILL_ROOT / "vendor").glob("*/SKILL.md")):
            match = re.search(r"^name:\s*([^\n]+)$", path.read_text(), re.MULTILINE)
            self.assertIsNotNone(match, path)
            actual.append(match.group(1).strip())
        self.assertEqual(sorted(provenance["skills"]), actual)
        self.assertEqual(8, len(actual))

    def test_wrapper_routes_every_vendored_skill_and_preserves_authority(self) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        provenance = json.loads((SKILL_ROOT / "UPSTREAM.json").read_text(encoding="utf-8"))
        for skill in provenance["skills"]:
            self.assertIn(f"vendor/{skill}", content)
        self.assertIn("references/source/frontend-design/SKILL.md", content)
        self.assertIn("Company OS authority", content)
        self.assertIn("`$ui-design-quality` remains the UI evidence gate", content)
        self.assertIn("Do not start it implicitly", content)
        words = len(content.split())
        self.assertLessEqual(words, 700, words)

    def test_frontend_design_companion_is_present_and_byte_exact(self) -> None:
        companion = SKILL_ROOT / "references/source/frontend-design"
        provenance = json.loads((companion / "UPSTREAM.json").read_text(encoding="utf-8"))
        self.assertEqual("frontend-design", provenance["skill"])
        self.assertEqual("https://github.com/anthropics/skills", provenance["source_repository"])
        self.assertEqual("2235be7c60b551f5de82ade908fd3816455afcda", provenance["source_commit"])
        self.assertEqual("Apache-2.0", provenance["license"])
        expected = provenance["files"]
        actual_paths = {
            path.name
            for path in companion.iterdir()
            if path.is_file() and path.name != "UPSTREAM.json"
        }
        self.assertEqual(set(expected), actual_paths)
        for name, digest in expected.items():
            path = companion / name
            self.assertFalse(path.is_symlink())
            self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())
        skill = (companion / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---\nname: frontend-design\n"))
        self.assertIn("Apache License", (companion / "LICENSE.txt").read_text(encoding="utf-8"))

    def test_ui_lanes_load_interface_design_without_replacing_the_gate(self) -> None:
        paths = (
            ROOT / "skills/company-os/company-os/SKILL.md",
            ROOT / "skills/company-os/ui-design-quality/SKILL.md",
            ROOT / "skills/company-os/manage-company-program/SKILL.md",
            ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md",
        )
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8")
                self.assertIn("$interface-design", text)
                self.assertIn("$ui-design-quality", text)

        company_os = " ".join(
            (ROOT / "skills/company-os/company-os/SKILL.md").read_text(encoding="utf-8").split()
        )
        self.assertIn(
            "When building digital interfaces, also load `$interface-design`",
            company_os,
        )
        self.assertIn("`$ui-design-quality` remains the evidence gate", company_os)

        gate = (ROOT / "skills/company-os/ui-design-quality/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`$ui-design-quality` remains the UI evidence gate", gate)
        self.assertIn("below `9.0/10`", gate)

    def test_interface_design_is_not_a_second_preflight_capability(self) -> None:
        compiler = (
            ROOT / "skills/company-os/manage-company-program/scripts/compile_program_preflight.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("interface-design", compiler)
        self.assertIn("ui_design_quality", compiler)

    def test_host_bindings_stay_explicit_and_gate_bound(self) -> None:
        for name in ("openai.yaml", "grok.yaml"):
            text = (SKILL_ROOT / "agents" / name).read_text(encoding="utf-8")
            self.assertIn("$interface-design", text)
            self.assertIn("$ui-design-quality", text)
            self.assertIn("building or reviewing digital interfaces", text)
            self.assertIn("allow_implicit_invocation: false", text)

    def test_upstream_mit_license_is_retained(self) -> None:
        license_text = (SKILL_ROOT / "LICENSE.upstream").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Copyright (c) 2026 Jakub Krehel", license_text)


if __name__ == "__main__":
    unittest.main()
