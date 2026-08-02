#!/usr/bin/env python3
"""Strictly validate the compact Company OS v2 role-skill source packages."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
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
        "extra_keys": {
            "parent_manager_task_id", "parent_manager_charter",
            "parent_budget_available",
        },
    },
}
COMMON_KEYS = {
    "schema", "program_version", "definition_version", "ids", "outcome",
    "outcome_digest", "requested_model", "authorization_expectation",
    "authorization", "artifact_references",
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
CONTRACT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{2,127}$")
SCOPE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*(?:/[a-z0-9][a-z0-9._-]*)*$")
ALLOWED_LOCAL_ROOTS = {"artifacts", "docs", "programs", "skills"}
AUTHORIZATION_SCHEMA = "company-os.authorization-decision.v1"
AUTHORIZATION_EVIDENCE_KIND = "repository_fixture"
AUTHORIZATION_SIGNATURE_SCHEME = "company-os.fixture-hmac-sha256.v1"
AUTHORIZATION_FIXTURE_KEYS = {
    "company-os-repository-test-v1": b"company-os-public-test-fixture-key-v1",
}
AUTHORIZATION_RECORD_KEYS = {
    "schema", "record_version", "decision_id", "decision_version", "status",
    "decision", "bindings", "evidence_reference", "evidence_kind",
    "authentication",
}
AUTHORIZATION_BINDING_KEYS = {
    "project_id", "program_id", "program_version", "cycle_id", "task_id",
    "parent_task_id", "definition_version", "outcome_digest",
    "requested_model", "definition_digest", "parent_definition_digest",
    "parent_manager_native_task_id", "phase", "decider_id",
}
PHASE_POLICY_FILES = [
    ROOT / "skills/company-os/manage-company-program/SKILL.md",
    ROOT / "skills/company-os/company-os/SKILL.md",
    ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/SKILL.md",
    ROOT / "skills/company-os/manage-company-program/references/manager-contract.md",
    ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/references/fabric-contract.md",
    ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/references/codex-native-task-fabric.md",
    ROOT / "programs/company-os-self-hosting/PHASE_2_CODEX_NATIVE_TASK_FABRIC_CONTRACT.md",
]
ENFORCEMENT_POLICY_FILES = [
    ROOT / "skills/company-os/manage-company-program/references/manager-contract.md",
    ROOT / "skills/autonomy-suite/execute-bounded-task/references/worker-contract.md",
    ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/references/fabric-contract.md",
    ROOT / "skills/autonomy-suite/orchestration/luna-execution-fabric/references/codex-native-task-fabric.md",
    ROOT / "programs/company-os-self-hosting/PHASE_2_CODEX_NATIVE_TASK_FABRIC_CONTRACT.md",
]


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _finite_nonnegative_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value >= 0
    return isinstance(value, float) and math.isfinite(value) and value >= 0


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _contract_id(value: Any) -> bool:
    return isinstance(value, str) and bool(CONTRACT_ID_RE.fullmatch(value))


def _string_set(value: Any) -> set[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return None
    return set(value)


def _nonempty_string_set(value: Any) -> set[str] | None:
    if (
        not isinstance(value, list)
        or not value
        or any(not _nonempty(item) for item in value)
    ):
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


def _contained_scope(child: Any, parent: Any) -> bool:
    return (
        _canonical_scope(child)
        and _canonical_scope(parent)
        and (child == parent or child.startswith(parent + "/"))
    )


def _canonical_scope_list(value: Any) -> list[str] | None:
    if (
        not isinstance(value, list)
        or not value
        or any(not _canonical_scope(item) for item in value)
    ):
        return None
    return value


def _canonical_id_map(value: Any) -> dict[str, str] | None:
    if (
        not isinstance(value, dict)
        or set(value) != REQUIRED_IDS
        or any(not _contract_id(value.get(key)) for key in REQUIRED_IDS)
    ):
        return None
    return value


def _sha256_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    except UnicodeError:
        return None


def _versioned_local_path(value: Any, version: Any) -> bool:
    return (
        _canonical_scope(value)
        and str(value).split("/", 1)[0] in ALLOWED_LOCAL_ROOTS
        and _positive_int(version)
        and f".v{version}." in str(value).rsplit("/", 1)[-1]
    )


def _project_local_path(value: Any, version: Any, project_id: Any) -> bool:
    return (
        _versioned_local_path(value, version)
        and _canonical_scope(project_id)
        and len(str(value).split("/")) >= 3
        and str(value).split("/")[1] == project_id
    )


def _read_safe_local_file(
    repository_root: Path | None, relative_path: Any, *, max_bytes: int = 1_048_576
) -> tuple[bytes | None, list[str]]:
    if (
        repository_root is None
        or not _canonical_scope(relative_path)
        or str(relative_path).split("/", 1)[0] not in ALLOWED_LOCAL_ROOTS
    ):
        return None, ["local evidence path is outside an allowed repository root"]
    try:
        root = repository_root.resolve(strict=True)
        cursor = root
        for segment in str(relative_path).split("/"):
            cursor = cursor / segment
            if cursor.is_symlink():
                return None, ["local evidence path may not traverse a symlink"]
        resolved = cursor.resolve(strict=True)
        resolved.relative_to(root)
        if not resolved.is_file() or resolved.stat().st_size > max_bytes:
            return None, ["local evidence file is missing, non-regular, or oversized"]
        return resolved.read_bytes(), []
    except (OSError, ValueError):
        return None, ["local evidence file is unavailable"]


def canonical_digest(value: Any) -> str | None:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError):
        return None
    return hashlib.sha256(encoded).hexdigest()


def contract_definition_digest(payload: dict[str, Any]) -> str | None:
    definition = {key: value for key, value in payload.items() if key != "authorization"}
    return canonical_digest(definition)


def authorization_fixture_signature(record: dict[str, Any]) -> str | None:
    authentication = record.get("authentication")
    if not isinstance(authentication, dict):
        return None
    if authentication.get("scheme") != AUTHORIZATION_SIGNATURE_SCHEME:
        return None
    key_id = authentication.get("key_id")
    if not isinstance(key_id, str):
        return None
    key = AUTHORIZATION_FIXTURE_KEYS.get(key_id)
    if key is None:
        return None
    unsigned = dict(record)
    unsigned["authentication"] = {
        "scheme": authentication.get("scheme"),
        "key_id": authentication.get("key_id"),
    }
    digest = canonical_digest(unsigned)
    if digest is None:
        return None
    return hmac.new(key, digest.encode("ascii"), hashlib.sha256).hexdigest()


def _load_authorization_record(
    reference: dict[str, Any], artifact_root: Path | None
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    record_path = reference.get("record_path")
    expected_digest = reference.get("record_sha256")
    if not _versioned_local_path(record_path, 1) or not str(record_path).endswith(".json"):
        return None, ["authorization record path must be canonical versioned local JSON"]
    if not isinstance(expected_digest, str) or not DIGEST_RE.fullmatch(expected_digest):
        return None, ["authorization record canonical sha256 is required"]
    raw, read_errors = _read_safe_local_file(artifact_root, record_path, max_bytes=16384)
    if raw is None:
        return None, [f"authorization {item}" for item in read_errors]
    try:
        record = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant {value}")
            ),
        )
    except (UnicodeError, ValueError, json.JSONDecodeError):
        return None, ["authorization record is unavailable or invalid JSON"]
    if not isinstance(record, dict):
        return None, ["authorization record must be an object"]
    actual_digest = canonical_digest(record)
    if actual_digest is None or not hmac.compare_digest(actual_digest, expected_digest):
        errors.append("authorization record canonical digest mismatch")
    return record, errors


def _validate_authorization_record(
    payload: dict[str, Any],
    spec: dict[str, Any],
    reference: dict[str, Any],
    artifact_root: Path | None,
    parent_definition_digest: str | None,
) -> list[str]:
    record, errors = _load_authorization_record(reference, artifact_root)
    if record is None:
        return errors
    if set(record) != AUTHORIZATION_RECORD_KEYS:
        errors.append("authorization record keys drifted")
        return errors
    expectation = payload.get("authorization_expectation")
    if not isinstance(expectation, dict):
        return errors + ["authorization expectation is invalid"]
    bindings = record.get("bindings")
    authentication = record.get("authentication")
    if not isinstance(bindings, dict) or set(bindings) != AUTHORIZATION_BINDING_KEYS:
        errors.append("authorization record bindings drifted")
        bindings = {}
    if not isinstance(authentication, dict) or set(authentication) != {"scheme", "key_id", "signature"}:
        errors.append("authorization authentication shape is invalid")
        authentication = {}
    if record.get("schema") != AUTHORIZATION_SCHEMA or record.get("record_version") != 1:
        errors.append("authorization record schema/version is invalid")
    if record.get("status") != "accepted" or record.get("decision") != "continue":
        errors.append("authorization decision is not accepted for dispatch")
    if record.get("evidence_kind") != AUTHORIZATION_EVIDENCE_KIND:
        errors.append("authorization evidence kind is not repository_fixture")
    expected_bindings = {
        "project_id": payload.get("ids", {}).get("project_id") if isinstance(payload.get("ids"), dict) else None,
        "program_id": payload.get("ids", {}).get("program_id") if isinstance(payload.get("ids"), dict) else None,
        "program_version": payload.get("program_version"),
        "cycle_id": payload.get("ids", {}).get("cycle_id") if isinstance(payload.get("ids"), dict) else None,
        "task_id": payload.get("ids", {}).get("task_id") if isinstance(payload.get("ids"), dict) else None,
        "parent_task_id": payload.get("ids", {}).get("parent_task_id") if isinstance(payload.get("ids"), dict) else None,
        "definition_version": payload.get("definition_version"),
        "outcome_digest": payload.get("outcome_digest"),
        "requested_model": payload.get("requested_model"),
        "definition_digest": contract_definition_digest(payload),
        "parent_definition_digest": parent_definition_digest,
        "parent_manager_native_task_id": (
            payload.get("parent_manager_task_id")
            if spec["schema"] == "company-os.work-packet.v2"
            else None
        ),
        "phase": expectation.get("phase"),
        "decider_id": expectation.get("decider_id"),
    }
    if not _project_local_path(
        reference.get("record_path"), 1, expected_bindings["project_id"]
    ):
        errors.append("authorization record path crosses the contract project")
    evidence = record.get("evidence_reference")
    if not isinstance(evidence, dict) or set(evidence) != {"project_id", "path", "version", "sha256"}:
        errors.append("authorization evidence reference shape is invalid")
    else:
        if evidence.get("project_id") != expected_bindings["project_id"]:
            errors.append("authorization evidence crosses the contract project")
        if not _project_local_path(
            evidence.get("path"), evidence.get("version"), expected_bindings["project_id"]
        ):
            errors.append("authorization evidence path must be project-local and versioned")
        else:
            evidence_sha = evidence.get("sha256")
            if not isinstance(evidence_sha, str) or not DIGEST_RE.fullmatch(evidence_sha):
                errors.append("authorization evidence sha256 is invalid")
            else:
                evidence_bytes, evidence_errors = _read_safe_local_file(
                    artifact_root, evidence.get("path")
                )
                errors.extend(
                    f"authorization evidence {item}" for item in evidence_errors
                )
                if evidence_bytes is not None and not hmac.compare_digest(
                    hashlib.sha256(evidence_bytes).hexdigest(), evidence_sha
                ):
                    errors.append("authorization evidence byte digest mismatch")
    if bindings != expected_bindings:
        errors.append("authorization record does not bind the exact contract and lineage")
    if (
        record.get("decision_id") != expectation.get("decision_id")
        or record.get("decision_version") != expectation.get("decision_version")
    ):
        errors.append("authorization decision identity/version does not match expectation")
    expected_signature = authorization_fixture_signature(record)
    signature = authentication.get("signature")
    if (
        expected_signature is None
        or not isinstance(signature, str)
        or not DIGEST_RE.fullmatch(signature)
        or not hmac.compare_digest(expected_signature, signature)
    ):
        errors.append("authorization fixture signature is invalid")
    return errors


def _load_parent_manager_charter(
    payload: dict[str, Any], repository_root: Path | None
) -> tuple[dict[str, Any] | None, list[str]]:
    reference = payload.get("parent_manager_charter")
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        return None, ["parent manager charter reference shape is invalid"]
    path = reference.get("path")
    digest = reference.get("sha256")
    project_id = payload.get("ids", {}).get("project_id") if isinstance(payload.get("ids"), dict) else None
    if not _project_local_path(path, payload.get("program_version"), project_id) or not str(path).endswith(".json"):
        return None, ["parent manager charter path must be project-local and versioned"]
    if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
        return None, ["parent manager charter sha256 is invalid"]
    raw, errors = _read_safe_local_file(repository_root, path, max_bytes=32768)
    if raw is None:
        return None, [f"parent manager charter {item}" for item in errors]
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), digest):
        errors.append("parent manager charter byte digest mismatch")
    try:
        parent = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant {value}")
            ),
        )
    except (UnicodeError, ValueError, json.JSONDecodeError):
        return None, errors + ["parent manager charter is invalid JSON"]
    if not isinstance(parent, dict):
        return None, errors + ["parent manager charter must be an object"]
    return parent, errors


def _validate_parent_narrowing(
    child: dict[str, Any], parent: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    child_ids = _canonical_id_map(child.get("ids"))
    parent_ids = _canonical_id_map(parent.get("ids"))
    parent_task_id = child.get("parent_manager_task_id")
    if child_ids is None or parent_ids is None:
        errors.append("worker and parent identifiers cannot be safely compared")
    else:
        if child_ids["parent_task_id"] != parent_ids["task_id"]:
            errors.append("worker mission parent lineage does not match accepted charter")
        for key in ("project_id", "program_id", "cycle_id"):
            if child_ids[key] != parent_ids[key]:
                errors.append(f"worker {key} crosses its accepted parent manager")
    if not _contract_id(parent_task_id):
        errors.append("worker parent manager native task identity is required")
    if child.get("program_version") != parent.get("program_version"):
        errors.append("worker program version is stale relative to parent manager")

    child_scope_value = child.get("scope")
    parent_scope_value = parent.get("scope")
    child_scope = _canonical_scope_list(
        child_scope_value.get("owned_paths")
        if isinstance(child_scope_value, dict)
        and set(child_scope_value) == {"owned_paths"}
        else None
    )
    parent_scope = _canonical_scope_list(
        parent_scope_value.get("owned_paths")
        if isinstance(parent_scope_value, dict)
        and set(parent_scope_value) == {"owned_paths"}
        else None
    )
    if child_scope is None or parent_scope is None or any(
        not any(_contained_scope(path, envelope) for envelope in parent_scope)
        for path in child_scope
    ):
        errors.append("worker scope escapes the accepted parent envelope")

    child_permissions_value = child.get("permissions")
    parent_permissions_value = parent.get("permissions")
    permission_keys = {"allowed_actions", "allowed_tools", "prohibited_actions"}
    child_permissions = (
        child_permissions_value
        if isinstance(child_permissions_value, dict)
        and set(child_permissions_value) == permission_keys
        else {}
    )
    parent_permissions = (
        parent_permissions_value
        if isinstance(parent_permissions_value, dict)
        and set(parent_permissions_value) == permission_keys
        else {}
    )
    for key in ("allowed_actions", "allowed_tools"):
        child_values = _nonempty_string_set(child_permissions.get(key))
        parent_values = _nonempty_string_set(parent_permissions.get(key))
        if child_values is None or parent_values is None or not child_values.issubset(parent_values):
            errors.append(f"worker {key} widens parent authority")
    child_prohibited = _nonempty_string_set(child_permissions.get("prohibited_actions"))
    parent_prohibited = _nonempty_string_set(parent_permissions.get("prohibited_actions"))
    if child_prohibited is None or parent_prohibited is None or not parent_prohibited.issubset(child_prohibited):
        errors.append("worker prohibited_actions weakens parent restrictions")

    child_budget_value = child.get("budget")
    parent_budget_value = parent.get("budget")
    child_budget = (
        child_budget_value
        if isinstance(child_budget_value, dict) and set(child_budget_value) == BUDGET_KEYS
        else {}
    )
    parent_budget = (
        parent_budget_value
        if isinstance(parent_budget_value, dict) and set(parent_budget_value) == BUDGET_KEYS
        else {}
    )
    available = child.get("parent_budget_available")
    if not isinstance(available, dict) or set(available) != BUDGET_KEYS:
        errors.append("parent available budget shape is invalid")
        available = {}
    for key in BUDGET_KEYS:
        child_value = child_budget.get(key)
        available_value = available.get(key)
        parent_value = parent_budget.get(key)
        valid = _finite_nonnegative_number if key == "max_cost_usd" else _nonnegative_int
        if not valid(child_value) or not valid(available_value) or not valid(parent_value):
            errors.append(f"budget.{key} cannot be compared to parent allocation")
        elif child_value > available_value or available_value > parent_value:
            errors.append(f"budget.{key} widens parent residual/allocation")
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


def _validate_contract_payload(
    payload: Any,
    role_name: str,
    *,
    template: bool,
    artifact_root: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if role_name not in ROLE_SPECS:
        return ["unknown role"]
    spec = ROLE_SPECS[role_name]
    if not isinstance(payload, dict):
        return ["payload must be an object"]
    expected_keys = COMMON_KEYS | {spec["version_key"]} | spec.get("extra_keys", set())
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
    elif not template and any(not _contract_id(ids[key]) for key in REQUIRED_IDS):
        errors.append("all identifiers must be canonical populated IDs")
    if role_name == "execute-bounded-task" and template:
        if payload.get("parent_manager_task_id") != "":
            errors.append("worker template parent manager task ID must be empty")
        if payload.get("parent_manager_charter") != {"path": "", "sha256": None}:
            errors.append("worker template parent manager charter reference drifted")
        available_template = payload.get("parent_budget_available")
        if (
            not isinstance(available_template, dict)
            or set(available_template) != BUDGET_KEYS
            or any(value is not None for value in available_template.values())
        ):
            errors.append("worker template parent available budget drifted")
    outcome = payload.get("outcome")
    outcome_digest = payload.get("outcome_digest")
    if template and outcome == "" and outcome_digest is None:
        pass
    elif not _nonempty(outcome) or not isinstance(outcome_digest, str) or not DIGEST_RE.fullmatch(outcome_digest):
        errors.append("outcome and sha256 digest are required")
    elif _sha256_text(outcome) != outcome_digest:
        errors.append("outcome digest does not match outcome")
    if payload.get("requested_model") != spec["requested_model"]:
        errors.append("requested_model does not match role")

    parent_payload: dict[str, Any] | None = None
    parent_definition_digest: str | None = None
    if role_name == "execute-bounded-task" and not template:
        parent_payload, parent_errors = _load_parent_manager_charter(
            payload, artifact_root
        )
        errors.extend(parent_errors)
        if parent_payload is not None:
            errors.extend(
                f"parent manager: {item}"
                for item in validate_contract_payload(
                    parent_payload,
                    "manage-company-program",
                    template=False,
                    artifact_root=artifact_root,
                )
            )
            parent_definition_digest = contract_definition_digest(parent_payload)

    expectation = payload.get("authorization_expectation")
    expectation_keys = {"phase", "decision_id", "decision_version", "decider_id"}
    if not isinstance(expectation, dict) or set(expectation) != expectation_keys:
        errors.append("authorization expectation shape is invalid")
    else:
        if expectation.get("phase") != spec["authorization_phase"]:
            errors.append("authorization phase expectation does not admit this role")
        if not _positive_int(expectation.get("decision_version")):
            errors.append("authorization decision_version must be positive")
        if template and expectation.get("decision_id") == "" and expectation.get("decider_id") == "":
            pass
        elif not _nonempty(expectation.get("decision_id")) or not _nonempty(expectation.get("decider_id")):
            errors.append("authorization decision identity and decider are required")

    authorization = payload.get("authorization")
    authorization_keys = {"record_path", "record_sha256"}
    if not isinstance(authorization, dict) or set(authorization) != authorization_keys:
        errors.append("authorization reference shape is invalid")
    elif template and authorization == {"record_path": "", "record_sha256": None}:
        pass
    else:
        errors.extend(
            _validate_authorization_record(
                payload,
                spec,
                authorization,
                artifact_root,
                parent_definition_digest,
            )
        )

    references = payload.get("artifact_references")
    if not isinstance(references, list) or len(references) != 3:
        errors.append("exact architecture, roadmap, and interface references are required")
    else:
        kinds: list[str] = []
        for reference in references:
            if not isinstance(reference, dict) or set(reference) != {"kind", "project_id", "path", "version", "sha256"}:
                errors.append("artifact reference shape is invalid")
                continue
            kind = reference.get("kind")
            if isinstance(kind, str):
                kinds.append(kind)
            else:
                errors.append("artifact reference kind must be a string")
            if not _positive_int(reference.get("version")):
                errors.append("artifact reference version must be positive")
            if template and reference.get("project_id") == "" and reference.get("path") == "" and reference.get("sha256") is None:
                continue
            if reference.get("project_id") != (ids.get("project_id") if isinstance(ids, dict) else None):
                errors.append("artifact reference crosses the contract project")
            if not _project_local_path(
                reference.get("path"),
                reference.get("version"),
                ids.get("project_id") if isinstance(ids, dict) else None,
            ):
                errors.append("artifact reference path must be project-local and versioned")
                continue
            expected_sha = reference.get("sha256")
            if not isinstance(expected_sha, str) or not DIGEST_RE.fullmatch(expected_sha):
                errors.append("artifact reference sha256 is invalid")
                continue
            raw, read_errors = _read_safe_local_file(artifact_root, reference.get("path"))
            errors.extend(f"artifact reference {item}" for item in read_errors)
            if raw is not None and not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), expected_sha):
                errors.append("artifact reference byte digest mismatch")
        if set(kinds) != REFERENCE_KINDS or len(kinds) != len(set(kinds)):
            errors.append("artifact reference kinds are missing or duplicated")

    task_context = payload.get("task_local_context")
    if not isinstance(task_context, dict) or set(task_context) != {"artifact_paths"} or not isinstance(task_context.get("artifact_paths"), list):
        errors.append("task_local_context shape is invalid")
    elif not template and any(not _nonempty(item) for item in task_context["artifact_paths"]):
        errors.append("task-local artifact paths must be nonempty strings")
    elif not template and isinstance(authorization, dict) and authorization.get("record_path") not in task_context["artifact_paths"]:
        errors.append("authorization record must be a task-local artifact reference")
    if (
        role_name == "execute-bounded-task"
        and not template
        and isinstance(task_context, dict)
        and isinstance(task_context.get("artifact_paths"), list)
        and isinstance(payload.get("parent_manager_charter"), dict)
        and payload["parent_manager_charter"].get("path") not in task_context["artifact_paths"]
    ):
        errors.append("parent manager charter must be a task-local artifact reference")
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
        checks = acceptance.get("checks")
        if not isinstance(checks, list):
            errors.append("acceptance checks must be a list")
        if not template and (not _nonempty(acceptance.get("oracle")) or not checks):
            errors.append("acceptance oracle and checks are required")
        elif not template and isinstance(checks, list) and any(
            not _nonempty(item) for item in checks
        ):
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
        if not _finite_nonnegative_number(budget.get("max_cost_usd")):
            errors.append("budget.max_cost_usd must be a finite nonnegative number")
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
    if not template:
        ids_value = payload.get("ids") if isinstance(payload.get("ids"), dict) else {}
        expected_parent = ids_value.get("parent_task_id")
        if role_name == "execute-bounded-task":
            parent_manager = payload.get("parent_manager_task_id")
            if not _contract_id(parent_manager):
                errors.append("worker parent_manager_task_id must be a native task identity")
            expected_destination = f"task:{parent_manager}" if _contract_id(parent_manager) else None
        else:
            expected_destination = f"task:{expected_parent}" if _contract_id(expected_parent) else None
        if payload.get("reporting_destination") != expected_destination:
            errors.append("reporting_destination must canonically target the exact parent task")
    if role_name == "execute-bounded-task" and not template and parent_payload is not None:
        errors.extend(_validate_parent_narrowing(payload, parent_payload))
    forbidden = FORBIDDEN_PROMPT_FIELDS.intersection(_all_keys(payload))
    if forbidden:
        errors.append(f"forbidden giant-prompt fields: {sorted(forbidden)}")
    return errors


def validate_contract_payload(
    payload: Any,
    role_name: str,
    *,
    template: bool,
    artifact_root: Path | None = None,
) -> list[str]:
    """Fail closed without raising for malformed JSON-shaped contract data."""
    try:
        return _validate_contract_payload(
            payload,
            role_name,
            template=template,
            artifact_root=artifact_root,
        )
    except (
        AttributeError,
        KeyError,
        OverflowError,
        RecursionError,
        TypeError,
        UnicodeError,
        ValueError,
    ):
        return ["malformed JSON-shaped contract failed closed"]


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
    for path in ENFORCEMENT_POLICY_FILES:
        text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8").casefold())
        required_groups = {
            "offline fixture authority": ("repository-fixture", "not live"),
            "local artifact bytes": ("versioned", "project-local", "exact byte", "symlink"),
            "parent narrowing": ("parent", "scope", "tool", "budget"),
        }
        for label, terms in required_groups.items():
            if any(term not in text for term in terms):
                errors.append(
                    f"{path.relative_to(ROOT)}: {label} policy is incomplete"
                )
    return errors


def main() -> int:
    errors = validate()
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
