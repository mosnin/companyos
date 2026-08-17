#!/usr/bin/env python3
"""Validate the Value Creation Delivery pack and spawn template.

The template is a thinking overlay for value-creation and value-delivery Sol
managers. It cannot be spawned as the master persona, a Luna worker, or a
default for every manager.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "company-os.value-creation-delivery-spawn-template.v1"
TEMPLATE_ID = "value-creation-delivery"
REQUIRED_SKILLS = ("manage-company-program", "value-creation-delivery")
FORBIDDEN_ROLES = ("master", "worker")
USE_WHEN = (
    "offer_architecture",
    "value_creation",
    "value_delivery",
    "value_scaling",
    "value_validation",
)
SOURCE_FILES = (
    "00-index.txt",
    "01-business-model-core.txt",
    "02-market-selection-market-laws.txt",
    "03-human-drives-social-status.txt",
    "04-forms-of-value-offer-architecture.txt",
    "05-value-levers-importance-testing.txt",
    "06-validation-assumptions-iteration.txt",
    "07-value-delivery-streams-expectations.txt",
    "08-delivery-reliability-quality-metrics.txt",
    "09-scaling-systemization-moats.txt",
    "10-integrated-playbooks-templates.txt",
)
TOP_LEVEL = {
    "schema",
    "template_id",
    "role",
    "requested_model",
    "skills",
    "forbidden_roles",
    "source_pack",
    "authority",
    "use_when",
}
SKILL_MARKERS = (
    "value-creation and value-delivery sol managers",
    "do not send this skill to luna workers",
    "do not use it as the master persona",
    "does not own",
    "separate creation from delivery",
    "offer without a proof plan",
    "not a claim of personal identity",
    "satisfaction is reality minus expectations",
)


def validate_pack(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    skill = root / "SKILL.md"
    if not skill.is_file():
        return ["missing SKILL.md"]
    text = skill.read_text(encoding="utf-8")
    if not text.startswith("---\nname: value-creation-delivery\n"):
        errors.append("SKILL.md name must be value-creation-delivery")
    words = len(text.split())
    if words > 700:
        errors.append(f"SKILL.md exceeds 700 words: {words}")
    folded = text.casefold()
    for marker in SKILL_MARKERS:
        if marker not in folded:
            errors.append(f"SKILL.md missing required marker: {marker}")
    if "TODO" in text:
        errors.append("SKILL.md has unresolved TODO")

    source_root = root / "references" / "source"
    for name in SOURCE_FILES:
        path = source_root / name
        if not path.is_file() or path.stat().st_size <= 0:
            errors.append(f"missing source file: {name}")
    extra = sorted(
        path.name
        for path in source_root.iterdir()
        if path.is_file() and path.name not in SOURCE_FILES
    )
    if extra:
        errors.append(f"unexpected source files: {', '.join(extra)}")

    for host in ("openai.yaml", "grok.yaml"):
        host_path = root / "agents" / host
        if not host_path.is_file():
            errors.append(f"missing agents/{host}")
            continue
        host_text = host_path.read_text(encoding="utf-8")
        if "$value-creation-delivery" not in host_text:
            errors.append(f"agents/{host} must invoke the skill")
        if "allow_implicit_invocation: false" not in host_text:
            errors.append(f"agents/{host} must disable implicit invocation")

    template_path = root / "assets" / "spawn-template.json"
    if not template_path.is_file():
        errors.append("missing spawn template")
    else:
        try:
            payload = json.loads(template_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            errors.append("spawn template is unreadable JSON")
        else:
            errors.extend(validate_spawn_template(payload))
    return errors


def validate_spawn_template(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["spawn template must be an object"]
    extra = sorted(set(payload) - TOP_LEVEL)
    missing = sorted(TOP_LEVEL - set(payload))
    if extra:
        errors.append(f"unknown spawn keys: {', '.join(extra)}")
    if missing:
        errors.append(f"missing spawn keys: {', '.join(missing)}")
    if payload.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if payload.get("template_id") != TEMPLATE_ID:
        errors.append("template_id drifted")
    if payload.get("role") != "manager":
        errors.append("spawn role must be manager")
    if payload.get("requested_model") != "gpt-5.6-sol":
        errors.append("requested_model must remain gpt-5.6-sol")
    if payload.get("authority") != "thinking_overlay":
        errors.append("authority must be thinking_overlay")
    if payload.get("source_pack") != "references/source":
        errors.append("source_pack drifted")
    skills = payload.get("skills")
    if not isinstance(skills, list) or list(skills) != list(REQUIRED_SKILLS):
        errors.append(
            "spawn skills must be the manager role skill plus value-creation-delivery"
        )
    forbidden = payload.get("forbidden_roles")
    if not isinstance(forbidden, list) or set(forbidden) != set(FORBIDDEN_ROLES):
        errors.append("forbidden_roles must be master and worker")
    use_when = payload.get("use_when")
    if not isinstance(use_when, list) or list(use_when) != list(USE_WHEN):
        errors.append("use_when must be the value-system lanes")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate_pack(args.root)
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
