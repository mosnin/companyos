#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

APPENDICES = {
    "skills/company-os/company-os/SKILL.md": """

## Recursive reusable skills

Use `$recursive-skill-foundry` as the project local learning and capability compounding layer. Search promoted project skills before external capability selection. Forge a new skill only when the user explicitly requests one, the active navigation route is concretely blocked by a missing reusable mechanism, or accepted field evidence proves repeated reuse value.

A skill candidate is not product progress unless skill creation is the original destination. For normal product missions, finish and checkpoint the real route first, then capture the reusable mechanism. Project skills install under `.agents/skills`, remain content addressed, and must be verified before assignment. Learned mechanisms require two accepted independent uses. Shared core promotion requires three independent projects plus fresh independent review and is never automatic.
""",
    "skills/company-os/manage-company-program/SKILL.md": """

## Reusable mechanism compounding

Before dispatching a new mechanism, search the project registry with `$recursive-skill-foundry`. Prefer an exact verified promoted project skill over recreating the procedure. When no match exists, do not pause the destination to abstract ordinary work. Create a candidate only for an explicit skill request or a concrete reusable capability gap that directly blocks the active route.

After a product checkpoint, preserve a successful repeated mechanism as field evidence. Two accepted independent uses may promote a learned project skill. A manager cannot self promote a candidate, cannot treat skill creation as product movement, and cannot widen worker authority through a generated child skill.
""",
    "skills/autonomy-suite/execute-bounded-task/SKILL.md": """

## Reusable mechanism return

When the work packet includes a verified project skill assignment, load only the exact bound entrypoints in the declared order and verify each digest before use. Do not discover or load unassigned project skills.

When the task reveals a genuinely reusable mechanism, return a concise `reusable_mechanism` record containing the trigger, outcome, exact evidence path, regression case, and expected reuse context. Do not forge or promote the skill unless the work packet explicitly authorizes `$recursive-skill-foundry`. One successful task is evidence, not promotion.
""",
    "skills/company-os/assign-capability-skills/SKILL.md": """

## Project local registry precedence

Before selecting from the static curated catalog, search the current project registry through `$recursive-skill-foundry`. A promoted project skill may be assigned only when its registry digest, entrypoint digest, role, selection rationale, and execution order are bound in the work packet. Keep the combined assignment limit at four skills.

The static catalog remains the cross project control plane. The project foundry registry is a local compounding layer and never silently mutates the static catalog or Company OS core.
""",
    "skills/company-os/navigation-control/SKILL.md": """

## Skill foundry navigation rule

Reusable skill creation is an actuator only when the destination is a skill or a missing reusable capability is the current concrete blocker. Otherwise it is post checkpoint learning and contributes zero destination movement. Sensor work about possible abstractions cannot interrupt the current actuator without value of information evidence.
""",
}


def append_once(path: Path, appendix: str) -> None:
    text = path.read_text(encoding="utf-8")
    heading = appendix.strip().splitlines()[0]
    if heading not in text:
        path.write_text(text.rstrip() + appendix, encoding="utf-8")


def main() -> None:
    for relative, appendix in APPENDICES.items():
        append_once(ROOT / relative, appendix)

    foundry = ROOT / "skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py"
    foundry.chmod(0o755)

    for relative in (
        "tmp/foundry-placeholder.txt",
        "experiments/schema-probe/c.txt",
    ):
        path = ROOT / relative
        if path.exists() or path.is_symlink():
            path.unlink()

    for relative in ("tmp", "experiments/schema-probe", "experiments"):
        path = ROOT / relative
        try:
            path.rmdir()
        except OSError:
            pass

    print("recursive skill foundry integration applied")


if __name__ == "__main__":
    main()
