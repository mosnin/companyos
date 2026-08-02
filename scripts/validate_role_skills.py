#!/usr/bin/env python3
"""Validate compact Company OS manager and worker role skills."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = {
    "manage-company-program": ROOT / "skills/company-os/manage-company-program",
    "execute-bounded-task": ROOT / "skills/autonomy-suite/execute-bounded-task",
}
ALLOWED_PACKET_KEYS = {
    "schema",
    "ids",
    "outcome",
    "task_local_context",
    "scope",
    "dependencies",
    "deliverables",
    "acceptance",
    "budget",
    "stop_escalation",
    "reporting_destination",
}
REQUIRED_IDS = {"project_id", "program_id", "cycle_id", "task_id", "parent_task_id"}
FORBIDDEN_PROMPT_FIELDS = {
    "full_transcript",
    "conversation_history",
    "master_prompt",
    "global_context",
    "complete_operating_system",
}


def validate() -> list[str]:
    errors: list[str] = []
    combined_body = ""
    for name, root in SKILLS.items():
        skill = root / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        combined_body += "\n" + text.casefold()
        if len(text.split()) > 700:
            errors.append(f"{name}: SKILL.md exceeds 700 words")
        if "TODO" in text:
            errors.append(f"{name}: unresolved TODO")
        frontmatter = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
        if not frontmatter:
            errors.append(f"{name}: invalid frontmatter")
        else:
            keys = {
                line.split(":", 1)[0].strip()
                for line in frontmatter.group(1).splitlines()
                if ":" in line
            }
            if keys != {"name", "description"}:
                errors.append(f"{name}: frontmatter must contain only name and description")

        yaml = (root / "agents/openai.yaml").read_text(encoding="utf-8")
        if f"${name}" not in yaml:
            errors.append(f"{name}: default_prompt must invoke the skill")

        asset_name = "mission-charter.json" if name == "manage-company-program" else "work-packet.json"
        asset = root / "assets" / asset_name
        payload = json.loads(asset.read_text(encoding="utf-8"))
        if set(payload) != ALLOWED_PACKET_KEYS:
            errors.append(f"{name}: compact packet keys drifted")
        if set(payload.get("ids", {})) != REQUIRED_IDS:
            errors.append(f"{name}: identifier set drifted")
        forbidden = FORBIDDEN_PROMPT_FIELDS.intersection(_all_keys(payload))
        if forbidden:
            errors.append(f"{name}: forbidden giant-prompt fields: {sorted(forbidden)}")
        if asset.stat().st_size > 2500:
            errors.append(f"{name}: compact packet exceeds 2500 bytes")

    repeated = "master outcome"
    if combined_body.count(repeated) > 1:
        errors.append("role skills repeat master-outcome prompt language")
    manager_text = (SKILLS["manage-company-program"] / "SKILL.md").read_text(
        encoding="utf-8"
    )
    if "`assets/work-packet.json`" not in manager_text:
        errors.append("manager skill does not route Luna tasks to the worker packet")
    if "Auto-continue routine phases only when" not in manager_text:
        errors.append("manager skill lacks exception-based phase continuation")
    if "Request `continue | rework | pause | terminate`" in manager_text:
        errors.append("manager skill requires manual approval at every phase")
    detailed_paths = [
        ROOT
        / "skills/autonomy-suite/orchestration/luna-execution-fabric/references/fabric-contract.md",
        ROOT
        / "skills/autonomy-suite/orchestration/luna-execution-fabric/references/codex-native-task-fabric.md",
        ROOT / "programs/company-os-self-hosting/PHASE_2_CODEX_NATIVE_TASK_FABRIC_CONTRACT.md",
    ]
    detailed_text = "\n".join(path.read_text(encoding="utf-8") for path in detailed_paths)
    if detailed_text.count("auto-continue") < 3:
        errors.append("detailed contracts do not consistently require guarded auto-continuation")
    forbidden_deadlock_phrases = {
        "waits for `continue`",
        "No implicit\napproval is valid",
        "Request `continue | rework | pause | terminate`",
    }
    for phrase in forbidden_deadlock_phrases:
        if phrase in detailed_text:
            errors.append(f"detailed contract retains manual phase deadlock wording: {phrase!r}")
    return errors


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        result = set(value)
        for item in value.values():
            result.update(_all_keys(item))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(_all_keys(item))
        return result
    return set()


def main() -> int:
    errors = validate()
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
