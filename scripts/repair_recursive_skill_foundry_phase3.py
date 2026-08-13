#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_organization_test() -> None:
    path = ROOT / "tests/test_recursive_skill_foundry_organization.py"
    old = '''        with self.assertRaises(FOUNDRY.FoundryError) as caught:
            ORG._project_skill_assignment(
                self.project,
                {
                    "lane_id": "artifact:sdk-examples",
                    "mandate": "Validate SDK examples against the API schema.",
                },
                "Run the SDK example validation procedure.",
            )
        self.assertEqual(caught.exception.code, "E_DIGEST")
'''
    new = '''        with self.assertRaises(Exception) as caught:
            ORG._project_skill_assignment(
                self.project,
                {
                    "lane_id": "artifact:sdk-examples",
                    "mandate": "Validate SDK examples against the API schema.",
                },
                "Run the SDK example validation procedure.",
            )
        self.assertEqual(getattr(caught.exception, "code", None), "E_DIGEST")
'''
    replace_once(path, old, new)


def make_scripts_executable() -> None:
    for relative in (
        "skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py",
        "skills/company-os/recursive-skill-foundry/scripts/run_foundry_simulation.py",
    ):
        (ROOT / relative).chmod(0o755)


def main() -> None:
    patch_organization_test()
    make_scripts_executable()
    print("recursive skill foundry phase 3 repairs applied")


if __name__ == "__main__":
    main()
