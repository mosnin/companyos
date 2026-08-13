#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEMP_WORKFLOWS = (
    ".github/workflows/merge-recursive-skill-foundry.yml",
    ".github/workflows/apply-recursive-skill-foundry.yml",
    ".github/workflows/repair-recursive-skill-foundry-phase1.yml",
    ".github/workflows/repair-recursive-skill-foundry-phase2.yml",
    ".github/workflows/repair-recursive-skill-foundry-phase3.yml",
    ".github/workflows/finalize-recursive-skill-foundry.yml",
    ".github/workflows/verify-recursive-skill-foundry-phase4.yml",
    ".github/workflows/cleanup-recursive-skill-foundry.yml",
    ".github/workflows/cleanup-recursive-skill-foundry-v2.yml",
)
TEMP_SCRIPTS = (
    "scripts/apply_recursive_skill_foundry_integration.py",
    "scripts/repair_recursive_skill_foundry_phase1.py",
    "scripts/repair_recursive_skill_foundry_phase2.py",
    "scripts/repair_recursive_skill_foundry_phase3.py",
    "scripts/finalize_recursive_skill_foundry.py",
    "scripts/finalize_recursive_skill_foundry_v2.py",
)


def main() -> None:
    required = (
        ROOT / "skills/company-os/recursive-skill-foundry/SKILL.md",
        ROOT / "skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py",
        ROOT / "skills/company-os/recursive-skill-foundry/scripts/run_foundry_simulation.py",
        ROOT / ".github/workflows/verify-recursive-skill-foundry.yml",
        ROOT / "artifacts/recursive-skill-foundry/merge-ready.json",
    )
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.is_file()]
    if missing:
        raise SystemExit("recursive skill foundry was not merged into main: " + ", ".join(missing))
    for relative in TEMP_WORKFLOWS + TEMP_SCRIPTS:
        path = ROOT / relative
        if path.exists() or path.is_symlink():
            path.unlink()
    print("recursive skill foundry post merge cleanup prepared")


if __name__ == "__main__":
    main()
