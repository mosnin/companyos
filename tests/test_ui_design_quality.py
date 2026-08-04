from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/company-os/ui-design-quality"


class UIDesignQualityTests(unittest.TestCase):
    def test_full_pinned_upstream_suite_is_present_and_byte_exact(self) -> None:
        provenance = json.loads((SKILL_ROOT / "UPSTREAM.json").read_text(encoding="utf-8"))
        self.assertEqual(
            "da80201b64de7d608a6dc5f723797ce6c65b692b",
            provenance["source_commit"],
        )
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

    def test_company_manager_and_worker_roles_make_ui_gate_mandatory(self) -> None:
        paths = [
            ROOT / "skills/company-os/company-os/SKILL.md",
            ROOT / "skills/company-os/manage-company-program/SKILL.md",
            ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md",
        ]
        for path in paths:
            content = path.read_text(encoding="utf-8")
            self.assertIn("$ui-design-quality", content, path)
            self.assertIn("ui_design", content, path)

    def test_wrapper_routes_every_vendored_skill_and_preserves_authority(self) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        provenance = json.loads((SKILL_ROOT / "UPSTREAM.json").read_text(encoding="utf-8"))
        for skill in provenance["skills"]:
            self.assertIn(f"vendor/{skill}", content)
        self.assertIn("Company OS authority", content)
        self.assertIn("below `9.0/10`", content)
        self.assertIn("independently reviewing manager", content)

    def test_upstream_mit_license_is_retained(self) -> None:
        license_text = (SKILL_ROOT / "LICENSE.upstream").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Copyright (c) 2026 Emil Kowalski", license_text)


if __name__ == "__main__":
    unittest.main()
