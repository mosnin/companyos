#!/usr/bin/env python3
"""Validate the Design pack and spawn template.

The template is a thinking overlay for design Sol managers. It cannot be
spawned as the master persona, a Luna worker, or a default for every manager.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "company-os.design-spawn-template.v1"
TEMPLATE_ID = "design"
REQUIRED_SKILLS = ("manage-company-program", "design")
FORBIDDEN_ROLES = ("master", "worker")
USE_WHEN = (
    "interaction_design",
    "problem_framing",
    "prototyping",
    "service_design",
    "user_understanding",
)
SOURCE_FILES = (
    "thinking/00-index.txt",
    "thinking/01-user-understanding-foundations.txt",
    "thinking/02-problem-definition.txt",
    "thinking/03-ideation-concept-development.txt",
    "thinking/04-prototyping-testing.txt",
    "thinking/05-lean-startup-integration.txt",
    "thinking/06-scale-ecosystem-design.txt",
    "thinking/07-service-design-experience-excellence.txt",
    "thinking/08-problem-to-growth-scale-framework.txt",
    "thinking/09-desirability-feasibility-viability-bridge.txt",
    "thinking/10-iteration-experiment-reporting-system.txt",
    "architect/00-index.txt",
    "architect/01-thesis-discoverability-understanding.txt",
    "architect/02-gulfs-of-execution-and-evaluation.txt",
    "architect/03-seven-stages-of-action.txt",
    "architect/04-affordances-signifiers-feedback-models.txt",
    "architect/05-knowledge-world-vs-head.txt",
    "architect/06-human-error-slips-mistakes-recovery.txt",
    "architect/07-design-principles-visibility-mapping-consistency.txt",
    "architect/08-conventions-culture-semantics.txt",
    "architect/09-system-image-mental-models.txt",
    "architect/10-evaluation-checklist-testing-protocol.txt",
    "design-system-tokens.md",
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
    "design sol managers",
    "do not send this skill to luna workers",
    "do not use it as the master persona",
    "does not own",
    "right action obvious",
    "prototype is a question",
    "ui-design-quality",
)


def validate_pack(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    skill = root / "SKILL.md"
    if not skill.is_file():
        return ["missing SKILL.md"]
    text = skill.read_text(encoding="utf-8")
    if not text.startswith("---\nname: design\n"):
        errors.append("SKILL.md name must be design")
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
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*")
        if path.is_file() and path.relative_to(source_root).as_posix() not in SOURCE_FILES
    )
    if extra:
        errors.append(f"unexpected source files: {', '.join(extra)}")

    for host in ("openai.yaml", "grok.yaml"):
        host_path = root / "agents" / host
        if not host_path.is_file():
            errors.append(f"missing agents/{host}")
            continue
        host_text = host_path.read_text(encoding="utf-8")
        if "$design" not in host_text:
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
        errors.append("spawn skills must be the manager role skill plus design")
    forbidden = payload.get("forbidden_roles")
    if not isinstance(forbidden, list) or set(forbidden) != set(FORBIDDEN_ROLES):
        errors.append("forbidden_roles must be master and worker")
    use_when = payload.get("use_when")
    if not isinstance(use_when, list) or list(use_when) != list(USE_WHEN):
        errors.append("use_when must be the design lanes")
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
