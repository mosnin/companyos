#!/usr/bin/env python3
"""Lint the first-class Company OS skill surface for structural integrity.

The distribution manifest content-addresses skill bytes but never inspects their
meaning, so a skill could ship with no frontmatter, a name that does not match
its folder, or a description with no trigger — and every byte check still passes.
This linter closes that gap for the skills Company OS authors itself.

Checked, per first-class SKILL.md:
  * begins with a closed YAML frontmatter block;
  * frontmatter carries exactly ``name`` and ``description`` and nothing else;
  * ``name`` is a valid slug and equals the containing folder name;
  * ``description`` is substantial and carries an explicit trigger clause.

Vendored and reference third-party skills (any path under ``vendor/`` or
``references/``) are out of scope: Company OS does not own their frontmatter.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"
VALID_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
EXCLUDED_PARTS = {"vendor", "references"}
ALLOWED_KEYS = {"name", "description"}
MIN_DESCRIPTION = 40
# An explicit routing signal. Kept broad enough to accept the surface's existing
# phrasings, strict enough that a description with no trigger at all fails.
TRIGGER_MARKERS = (
    "use when",
    "use for",
    "use as",
    "use to",
    "use on",
    "use at",
    "use during",
    "use after",
    "use before",
    "use only",
    "use immediately",
    "use whenever",
    "use it when",
    "use this when",
)


def is_first_class(path: Path) -> bool:
    relative = path.relative_to(SKILLS_ROOT)
    return not (EXCLUDED_PARTS & set(relative.parts))


def parse_frontmatter(text: str) -> tuple[dict[str, str] | None, str]:
    if not text.startswith("---\n"):
        return None, "missing opening frontmatter fence"
    end = text.find("\n---", 4)
    if end < 0:
        return None, "frontmatter fence is not closed"
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            return None, f"invalid frontmatter line: {line.strip()!r}"
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields, ""


def check_skill(path: Path) -> list[str]:
    folder = path.parent.name
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")
    fields, error = parse_frontmatter(text)
    if fields is None:
        return [error]
    extra = set(fields) - ALLOWED_KEYS
    if extra:
        problems.append(f"unsupported frontmatter keys: {', '.join(sorted(extra))}")
    if "name" not in fields:
        problems.append("frontmatter is missing name")
    else:
        name = fields["name"]
        if not VALID_NAME.fullmatch(name):
            problems.append(f"invalid skill name: {name!r}")
        elif name != folder:
            problems.append(f"name {name!r} does not match folder {folder!r}")
    description = fields.get("description", "")
    if len(description) < MIN_DESCRIPTION:
        problems.append("description is missing or too short")
    elif not any(marker in description.lower() for marker in TRIGGER_MARKERS):
        problems.append("description has no explicit trigger clause (e.g. 'Use when ...')")
    return problems


def audit_surface() -> dict[str, list[str]]:
    findings: dict[str, list[str]] = {}
    for path in sorted(SKILLS_ROOT.rglob("SKILL.md")):
        if not is_first_class(path):
            continue
        problems = check_skill(path)
        if problems:
            findings[str(path.relative_to(REPO_ROOT))] = problems
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args(argv)
    findings = audit_surface()
    scanned = sum(
        1 for path in SKILLS_ROOT.rglob("SKILL.md") if is_first_class(path)
    )
    if args.json:
        print(json.dumps({"scanned": scanned, "violations": findings}, indent=2, sort_keys=True))
    else:
        if not findings:
            print(f"skill surface verified: {scanned} first-class skills, 0 violations")
        else:
            for skill, problems in findings.items():
                for problem in problems:
                    print(f"{skill}: {problem}")
            print(f"\n{len(findings)} of {scanned} first-class skills have violations")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
