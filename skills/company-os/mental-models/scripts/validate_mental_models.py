#!/usr/bin/env python3
"""Validate the mental-models reasoning pack and spawn template.

This is the default thinking overlay for every Company OS role: twelve
general-thinking models bound to controller gates. The validator pins the
pack's invariants — all twelve models present in both the doctrine and the
catalog, authority disclaimed, the overlay open to every role — so the
reasoning layer cannot silently lose a model or quietly grow authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "company-os.mental-models-spawn-template.v1"
TEMPLATE_ID = "mental-models"
REQUIRED_SKILLS = ("mental-models",)
USE_WHEN = (
    "acceptance_decision",
    "branch_merge",
    "metric_interpretation",
    "repair_triage",
    "work_admission",
)
TOP_LEVEL = {
    "schema",
    "template_id",
    "role",
    "skills",
    "forbidden_roles",
    "source_pack",
    "authority",
    "use_when",
}
# Every model must be named in SKILL.md and the reference catalog. Matched
# lowercase; keep these to the stable fragment of each name.
MODEL_MARKERS = (
    "map",
    "circle of competence",
    "falsifiab",
    "first principles",
    "thought experiment",
    "necessity",
    "second-order",
    "probabilistic",
    "correlation",
    "inversion",
    "occam",
    "hanlon",
)
SKILL_MARKERS = (
    "owns no",
    "do not use as the master persona",
    "reality outranks",
    "falsifiable observation",
)


def validate_pack(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    skill = root / "SKILL.md"
    if not skill.is_file():
        return ["missing SKILL.md"]
    text = skill.read_text(encoding="utf-8")
    if not text.startswith("---\nname: mental-models\n"):
        errors.append("SKILL.md name must be mental-models")
    words = len(text.split())
    if words > 700:
        errors.append(f"SKILL.md exceeds 700 words: {words}")
    lowered = text.lower()
    for marker in SKILL_MARKERS:
        if marker not in lowered:
            errors.append(f"SKILL.md missing required doctrine marker: {marker}")
    for marker in MODEL_MARKERS:
        if marker not in lowered:
            errors.append(f"SKILL.md missing model: {marker}")

    catalog = root / "references" / "models.md"
    if not catalog.is_file():
        errors.append("missing references/models.md")
    else:
        catalog_text = catalog.read_text(encoding="utf-8").lower()
        for marker in MODEL_MARKERS:
            if marker not in catalog_text:
                errors.append(f"references/models.md missing model: {marker}")

    template_path = root / "assets" / "spawn-template.json"
    if not template_path.is_file():
        errors.append("missing assets/spawn-template.json")
    else:
        try:
            template = json.loads(template_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"spawn template is not JSON: {exc}")
        else:
            errors.extend(validate_spawn_template(template))
    return errors


def validate_spawn_template(template: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(template, dict):
        return ["spawn template must be an object"]
    if set(template) != TOP_LEVEL:
        errors.append("spawn template keys must match the pinned schema")
    if template.get("schema") != SCHEMA:
        errors.append(f"spawn schema must be {SCHEMA}")
    if template.get("template_id") != TEMPLATE_ID:
        errors.append(f"spawn template_id must be {TEMPLATE_ID}")
    # The default reasoning layer is deliberately role-universal: unlike the
    # lane personas, no role may be locked out of thinking clearly.
    if template.get("role") != "any":
        errors.append("spawn role must be any")
    if template.get("forbidden_roles") != []:
        errors.append("spawn forbidden_roles must be empty")
    if template.get("authority") != "thinking_overlay":
        errors.append("spawn authority must be thinking_overlay")
    if tuple(template.get("skills", ())) != REQUIRED_SKILLS:
        errors.append("spawn skills must be exactly (mental-models,)")
    if tuple(template.get("use_when", ())) != USE_WHEN:
        errors.append("spawn use_when must match the pinned gate list")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    errors = validate_pack(Path(args.root))
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"ok": True}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
