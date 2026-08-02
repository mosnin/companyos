#!/usr/bin/env python3
"""Strictly validate the compact Company OS v2 role-skill source packages."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SKILLS = {
    "manage-company-program": ROOT / "skills/company-os/manage-company-program",
    "execute-bounded-task": ROOT / "skills/autonomy-suite/execute-bounded-task",
}
ROLE_SPECS = {
    "manage-company-program": {
        "asset": "mission-charter.json",
        "schema": "company-os.mission-charter.v2",
        "version_key": "charter_version",
        "requested_model": "gpt-5.6-sol",
        "authorization_phase": "charter",
        "barriers": ["charter", "design", "verification", "integration"],
        "routine_conditions": {
            "unchanged_charter", "checks_pass", "budget_valid",
            "concurrency_valid", "authority_unchanged", "no_exception",
        },
        "independent_review": True,
    },
    "execute-bounded-task": {
        "asset": "work-packet.json",
        "schema": "company-os.work-packet.v2",
        "version_key": "packet_version",
        "requested_model": "gpt-5.6-luna",
        "authorization_phase": "design",
        "independent_review": False,
    },
}
COMMON_KEYS = {
    "schema", "program_version", "definition_version", "ids", "outcome",
    "outcome_digest", "requested_model", "authorization", "artifact_references",
    "task_local_context", "scope", "permissions", "dependencies",
    "deliverables", "acceptance", "decision_barriers", "budget",
    "stop_escalation", "reporting_destination",
}
REQUIRED_IDS = {"project_id", "program_id", "cycle_id", "task_id", "parent_task_id"}
REFERENCE_KINDS = {"architecture", "roadmap", "interfaces"}
BUDGET_KEYS = {
    "max_tokens", "max_cost_usd", "max_time_minutes", "max_tasks",
    "max_concurrency", "max_retries",
}
FORBIDDEN_PROMPT_FIELDS = {
    "full_transcript", "conversation_history", "master_prompt",
    "global_context", "complete_operating_system",
}
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
SCOPE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*(?:/[a-z0-9][a-z0-9._-]*)*$")
PHASE_POLICY_FILES = [
    ROOT / "skills/company-os/manage-company-program/SKILL.md",
    ROOT / "skills/company-os/company-os/SKILL.md",
    ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/SKILL.md",
    ROOT / "skills/company-os/manage-company-program/references/manager-contract.md",
    ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/references/fabric-contract.md",
    ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/references/codex-native-task-fabric.md",
    ROOT / "programs/company-os-self-hosting/PHASE_2_CODEX_NATIVE_TASK_FABRIC_CONTRACT.md",
]


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_set(value: Any) -> set[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return None
    return set(value)


def _canonical_scope(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.isascii()
        and value == unicodedata.normalize("NFKC", value)
        and value == value.casefold()
        and bool(SCOPE_RE.fullmatch(value))
    )


def _scope_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def contract_definition_digest(payload: dict[str, Any]) -> str:
    definition = {key: value for key, value in payload.items() if key != "authorization"}
    encoded = json.dumps(
        definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def parse_agent_yaml(text: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Parse only the bounded two-level YAML subset used by role metadata."""
    result: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    section: str | None = None
    for line_number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        if "\t" in raw:
            errors.append(f"line {line_number}: tabs are forbidden")
            continue
        top = re.fullmatch(r"([a-z_]+):", raw)
        if top:
            section = top.group(1)
            if section in result:
                errors.append(f"line {line_number}: duplicate section {section}")
            result.setdefault(section, {})
            continue
        item = re.fullmatch(r"  ([a-z_]+): (.+)", raw)
        if not item or section is None:
            errors.append(f"line {line_number}: unsupported YAML shape")
            continue
        key, encoded = item.groups()
        if key in result[section]:
            errors.append(f"line {line_number}: duplicate key {section}.{key}")
            continue
        if encoded in {"true", "false"}:
            value: Any = encoded == "true"
        elif encoded.startswith('"') and encoded.endswith('"'):
            try:
                value = json.loads(encoded)
            except json.JSONDecodeError:
                errors.append(f"line {line_number}: invalid quoted string")
                continue
            if not isinstance(value, str):
                errors.append(f"line {line_number}: metadata string required")
                continue
        else:
            errors.append(f"line {line_number}: value must be quoted string or boolean")
            continue
        result[section][key] = value
    return result, errors


def validate_agent_metadata(text: str, skill_name: str) -> list[str]:
    metadata, errors = parse_agent_yaml(text)
    if set(metadata) != {"interface", "policy"}:
        errors.append("agent metadata sections drifted")
    interface = metadata.get("interface")
    policy = metadata.get("policy")
    if not isinstance(interface, dict) or set(interface) != {"display_name", "short_description", "default_prompt"}:
        errors.append("interface metadata keys drifted")
        interface = {}
    default_prompt = interface.get("default_prompt")
    short_description = interface.get("short_description")
    display_name = interface.get("display_name")
    if not all(isinstance(value, str) for value in (default_prompt, short_description, display_name)):
        errors.append("interface metadata values must be strings")
    if not isinstance(default_prompt, str) or f"${skill_name}" not in default_prompt:
        errors.append("default_prompt must invoke the skill")
    if not isinstance(short_description, str) or not 25 <= len(short_description) <= 64:
        errors.append("short_description must be 25-64 characters")
    if policy != {"allow_implicit_invocation": False}:
        errors.append("implicit invocation must be structurally disabled")
    return errors


def validate_contract_payload(payload: Any, role_name: str, *, template: bool) -> list[str]:
    errors: list[str] = []
    if role_name not in ROLE_SPECS:
        return ["unknown role"]
    spec = ROLE_SPECS[role_name]
    if not isinstance(payload, dict):
        return ["payload must be an object"]
    expected_keys = COMMON_KEYS | {spec["version_key"]}
    if set(payload) != expected_keys:
        errors.append("top-level contract keys drifted")
    if payload.get("schema") != spec["schema"]:
        errors.append("schema version is invalid")
    for key in (spec["version_key"], "program_version", "definition_version"):
        if not _positive_int(payload.get(key)):
            errors.append(f"{key} must be a positive integer")
    ids = payload.get("ids")
    if not isinstance(ids, dict) or set(ids) != REQUIRED_IDS:
        errors.append("identifier set drifted")
    elif not template and any(not _nonempty(ids[key]) for key in REQUIRED_IDS):
        errors.append("all identifiers must be populated")
    outcome = payload.get("outcome")
    outcome_digest = payload.get("outcome_digest")
    if template and outcome == "" and outcome_digest is None:
        pass
    elif not _nonempty(outcome) or not isinstance(outcome_digest, str) or not DIGEST_RE.fullmatch(outcome_digest):
        errors.append("outcome and sha256 digest are required")
    elif hashlib.sha256(outcome.encode("utf-8")).hexdigest() != outcome_digest:
        errors.append("outcome digest does not match outcome")
    if payload.get("requested_model") != spec["requested_model"]:
        errors.append("requested_model does not match role")

    authorization = payload.get("authorization")
    authorization_keys = {
        "phase", "decision", "decision_id", "decider_id", "decision_version",
        "definition_digest", "evidence_digest", "authentication_digest",
    }
    if not isinstance(authorization, dict) or set(authorization) != authorization_keys:
        errors.append("authorization reference shape is invalid")
    else:
        if authorization.get("phase") != spec["authorization_phase"] or authorization.get("decision") != "continue":
            errors.append("authorization phase/decision does not admit this role")
        if not _positive_int(authorization.get("decision_version")):
            errors.append("authorization decision_version must be positive")
        if template and authorization.get("decision_id") == "" and authorization.get("decider_id") == "" and authorization.get("definition_digest") is None and authorization.get("evidence_digest") is None and authorization.get("authentication_digest") is None:
            pass
        elif (
            not _nonempty(authorization.get("decision_id"))
            or not _nonempty(authorization.get("decider_id"))
            or not isinstance(authorization.get("definition_digest"), str)
            or not DIGEST_RE.fullmatch(authorization["definition_digest"])
            or not isinstance(authorization.get("evidence_digest"), str)
            or not DIGEST_RE.fullmatch(authorization["evidence_digest"])
            or not isinstance(authorization.get("authentication_digest"), str)
            or not DIGEST_RE.fullmatch(authorization["authentication_digest"])
        ):
            errors.append("authorization must be attributable and digest-bound")
        elif authorization["definition_digest"] != contract_definition_digest(payload):
            errors.append("authorization definition digest does not bind this exact contract")

    references = payload.get("artifact_references")
    if not isinstance(references, list) or len(references) != 3:
        errors.append("exact architecture, roadmap, and interface references are required")
    else:
        kinds: list[str] = []
        for reference in references:
            if not isinstance(reference, dict) or set(reference) != {"kind", "path", "version", "sha256"}:
                errors.append("artifact reference shape is invalid")
                continue
            kind = reference.get("kind")
            if isinstance(kind, str):
                kinds.append(kind)
            else:
                errors.append("artifact reference kind must be a string")
            if not _positive_int(reference.get("version")):
                errors.append("artifact reference version must be positive")
            if template and reference.get("path") == "" and reference.get("sha256") is None:
                continue
            if not _nonempty(reference.get("path")) or not isinstance(reference.get("sha256"), str) or not DIGEST_RE.fullmatch(reference["sha256"]):
                errors.append("artifact reference must be path-bound and content-addressed")
        if set(kinds) != REFERENCE_KINDS or len(kinds) != len(set(kinds)):
            errors.append("artifact reference kinds are missing or duplicated")

    task_context = payload.get("task_local_context")
    if not isinstance(task_context, dict) or set(task_context) != {"artifact_paths"} or not isinstance(task_context.get("artifact_paths"), list):
        errors.append("task_local_context shape is invalid")
    elif not template and any(not _nonempty(item) for item in task_context["artifact_paths"]):
        errors.append("task-local artifact paths must be nonempty strings")
    scope = payload.get("scope")
    if not isinstance(scope, dict) or set(scope) != {"owned_paths"} or not isinstance(scope.get("owned_paths"), list):
        errors.append("scope shape is invalid")
    elif not template:
        owned_paths = scope["owned_paths"]
        if not owned_paths or any(not _canonical_scope(value) for value in owned_paths):
            errors.append("scope paths must be canonical lowercase ASCII relative POSIX paths")
        elif any(
            _scope_overlap(left, right)
            for index, left in enumerate(owned_paths)
            for right in owned_paths[index + 1:]
        ):
            errors.append("scope paths overlap by equality or ancestry")
    permissions = payload.get("permissions")
    if not isinstance(permissions, dict) or set(permissions) != {"allowed_actions", "allowed_tools", "prohibited_actions"} or any(not isinstance(permissions.get(key), list) for key in ("allowed_actions", "allowed_tools", "prohibited_actions")):
        errors.append("permissions must explicitly define allowed actions/tools and prohibitions")
    elif not template and any(not permissions[key] for key in ("allowed_actions", "allowed_tools", "prohibited_actions")):
        errors.append("permissions cannot be empty in a dispatched contract")
    elif not template and any(
        any(not _nonempty(item) for item in permissions[key])
        for key in ("allowed_actions", "allowed_tools", "prohibited_actions")
    ):
        errors.append("permission entries must be nonempty strings")
    for key in ("dependencies", "deliverables"):
        if not isinstance(payload.get(key), list):
            errors.append(f"{key} must be a list")
        elif not template and any(not _nonempty(item) for item in payload[key]):
            errors.append(f"{key} entries must be nonempty strings")
    if not template and not payload.get("deliverables"):
        errors.append("deliverables cannot be empty in a dispatched contract")

    acceptance = payload.get("acceptance")
    if not isinstance(acceptance, dict) or set(acceptance) != {"oracle", "checks", "independent_review"}:
        errors.append("acceptance shape is invalid")
    else:
        review = acceptance.get("independent_review")
        if not isinstance(review, dict) or set(review) != {"required", "barriers", "evidence_requirements"}:
            errors.append("independent review requirements are malformed")
        elif review.get("required") is not spec["independent_review"] or not isinstance(review.get("barriers"), list) or not isinstance(review.get("evidence_requirements"), list):
            errors.append("independent review policy does not match role")
        else:
            review_barriers = _string_set(review.get("barriers"))
            if review_barriers is None:
                errors.append("independent review barriers must be strings")
            elif role_name == "manage-company-program" and not {"design", "verification"}.issubset(review_barriers):
                errors.append("manager independent review must cover design and verification")
        if not isinstance(acceptance.get("checks"), list):
            errors.append("acceptance checks must be a list")
        if not template and (not _nonempty(acceptance.get("oracle")) or not acceptance.get("checks")):
            errors.append("acceptance oracle and checks are required")
        elif not template and any(not _nonempty(item) for item in acceptance.get("checks", [])):
            errors.append("acceptance checks must be nonempty strings")
        if (
            not template
            and isinstance(review, dict)
            and isinstance(review.get("evidence_requirements"), list)
            and any(not _nonempty(item) for item in review["evidence_requirements"])
        ):
            errors.append("review evidence requirements must be nonempty strings")

    barriers = payload.get("decision_barriers")
    if role_name == "manage-company-program":
        expected_barrier_keys = {
            "authenticated_master_decision_required", "routine_auto_continue_phase",
            "routine_conditions",
        }
        if not isinstance(barriers, dict) or set(barriers) != expected_barrier_keys:
            errors.append("manager decision barrier shape is invalid")
        else:
            if barriers.get("authenticated_master_decision_required") != spec["barriers"]:
                errors.append("authenticated decision barriers drifted")
            if barriers.get("routine_auto_continue_phase") != "execution":
                errors.append("only execution may auto-continue")
            conditions = _string_set(barriers.get("routine_conditions"))
            if conditions is None or conditions != spec["routine_conditions"]:
                errors.append("routine auto-continuation conditions drifted")
    else:
        expected_barrier_keys = {
            "inherited_design_authorization_required", "manager_verification_required",
            "worker_waits_for_master",
        }
        if not isinstance(barriers, dict) or set(barriers) != expected_barrier_keys:
            errors.append("worker decision evidence policy shape is invalid")
        elif barriers != {
            "inherited_design_authorization_required": True,
            "manager_verification_required": True,
            "worker_waits_for_master": False,
        }:
            errors.append("worker must inherit design authorization and never await the master")

    budget = payload.get("budget")
    if not isinstance(budget, dict) or set(budget) != BUDGET_KEYS:
        errors.append("budget keys drifted")
    elif template:
        populated = {key: value for key, value in budget.items() if value is not None}
        if role_name == "execute-bounded-task" and (populated.get("max_tasks") != 1 or populated.get("max_concurrency") != 1):
            errors.append("worker template must cap task and concurrency at one")
    else:
        for key in ("max_tokens", "max_time_minutes", "max_tasks", "max_concurrency"):
            if not _positive_int(budget.get(key)):
                errors.append(f"budget.{key} must be a positive integer")
        if not isinstance(budget.get("max_cost_usd"), (int, float)) or isinstance(budget.get("max_cost_usd"), bool) or budget["max_cost_usd"] < 0:
            errors.append("budget.max_cost_usd must be nonnegative")
        if not _nonnegative_int(budget.get("max_retries")):
            errors.append("budget.max_retries must be a nonnegative integer")
        retries = budget.get("max_retries")
        if role_name == "execute-bounded-task" and (
            budget.get("max_tasks") != 1
            or budget.get("max_concurrency") != 1
            or not _nonnegative_int(retries)
            or retries > 1
        ):
            errors.append("worker budget exceeds one task/concurrency/retry")

    stop = payload.get("stop_escalation")
    if not isinstance(stop, dict) or set(stop) != {"stop_conditions", "escalate_on"} or any(not isinstance(stop.get(key), list) for key in ("stop_conditions", "escalate_on")):
        errors.append("stop/escalation shape is invalid")
    elif not template and any(
        not stop[key] or any(not _nonempty(item) for item in stop[key])
        for key in ("stop_conditions", "escalate_on")
    ):
        errors.append("stop/escalation entries must be nonempty strings")
    if not template and not _nonempty(payload.get("reporting_destination")):
        errors.append("reporting_destination is required")
    forbidden = FORBIDDEN_PROMPT_FIELDS.intersection(_all_keys(payload))
    if forbidden:
        errors.append(f"forbidden giant-prompt fields: {sorted(forbidden)}")
    return errors


def validate() -> list[str]:
    errors: list[str] = []
    combined_body = ""
    for name, root in SKILLS.items():
        skill_text = (root / "SKILL.md").read_text(encoding="utf-8")
        combined_body += "\n" + skill_text.casefold()
        if len(skill_text.split()) > 700:
            errors.append(f"{name}: SKILL.md exceeds 700 words")
        if "TODO" in skill_text:
            errors.append(f"{name}: unresolved TODO")
        frontmatter = re.match(r"\A---\n(.*?)\n---\n", skill_text, re.DOTALL)
        keys = set() if not frontmatter else {
            line.split(":", 1)[0].strip()
            for line in frontmatter.group(1).splitlines() if ":" in line
        }
        if keys != {"name", "description"}:
            errors.append(f"{name}: frontmatter must contain only name and description")

        metadata_text = (root / "agents/openai.yaml").read_text(encoding="utf-8")
        errors.extend(f"{name}: {item}" for item in validate_agent_metadata(metadata_text, name))

        spec = ROLE_SPECS[name]
        asset = root / "assets" / spec["asset"]
        payload = json.loads(asset.read_text(encoding="utf-8"))
        errors.extend(f"{name}: {item}" for item in validate_contract_payload(payload, name, template=True))
        if asset.stat().st_size > 3500:
            errors.append(f"{name}: compact contract exceeds 3500 bytes")

    if combined_body.count("master outcome") > 1:
        errors.append("role skills repeat master-outcome prompt language")
    manager_text = (SKILLS["manage-company-program"] / "SKILL.md").read_text(encoding="utf-8")
    if "`assets/work-packet.json`" not in manager_text:
        errors.append("manager skill does not route Luna tasks to the worker packet")

    required_phase_terms = {
        "authenticated master decision", "charter", "design", "verification",
        "integration", "routine execution subphase", "auto-continue", "silence",
        "visible",
    }
    for path in PHASE_POLICY_FILES:
        text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8").casefold())
        missing = sorted(term for term in required_phase_terms if term not in text)
        if missing:
            errors.append(f"{path.relative_to(ROOT)}: phase policy terms missing: {missing}")
        routine_window = (
            ("after accepted design" in text or "after design acceptance" in text)
            and "before verification" in text
        ) or "between those barriers" in text
        if not routine_window:
            errors.append(f"{path.relative_to(ROOT)}: routine continuation is not fenced between design and verification")
        if "escalat" not in text or not ("time" in text or "bounded" in text):
            errors.append(f"{path.relative_to(ROOT)}: silence lacks bounded escalation")
        if "auto-continue routine phases" in text or "auto-continues only when the accepted charter" in text:
            errors.append(f"{path.relative_to(ROOT)}: broad auto-continuation wording remains")
    return errors


def main() -> int:
    errors = validate()
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
