#!/usr/bin/env python3
"""Validate, search, resolve, and verify bounded Company OS skill assignments."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


CATALOG_SCHEMA = "company-os.capability-catalog.v1"
REQUEST_SCHEMA = "company-os.capability-request.v1"
ASSIGNMENT_SCHEMA = "company-os.capability-assignment.v1"
BINDING_ALGORITHM = "sha256-canonical-json-v1"
SKILL_RUNTIME_ID = "company-os-skill-reference"
SKILL_RUNTIME_TYPE = "codex_native_skill_reference"
SKILL_RUNTIME_LOCATOR = "runtime://codex/native-skill"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")
PERMISSION_RE = re.compile(r"^[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*$")
TOKEN_RE = re.compile(r"[a-z0-9]+")
ROLES = {"manager", "worker"}
TRUST_STATES = {"approved", "reference_only", "quarantine", "rejected"}
DISPOSITIONS = {
    "vendor_curated_subset",
    "extract_wrapper",
    "reference_only",
    "quarantine",
    "reject",
}
SOURCE_KEYS = {
    "source_id",
    "canonical_url",
    "source_commit",
    "source_tree",
    "observed_at",
    "license",
    "disposition",
    "risk_flags",
}
LICENSE_KEYS = {"spdx", "evidence_path", "redistribution"}
CAPABILITY_KEYS = {
    "capability_id",
    "name",
    "description",
    "source_id",
    "upstream_skill_path",
    "upstream_entrypoint_sha256",
    "upstream_entrypoint_bytes",
    "entrypoint",
    "entrypoint_sha256",
    "entrypoint_bytes",
    "roles",
    "domains",
    "tags",
    "trust_state",
    "dispatchable",
    "load_policy",
    "required_permissions",
    "conflicts",
}
POLICY_KEYS = {
    "max_skills_per_assignment",
    "max_entrypoint_bytes_per_assignment",
    "max_search_results",
}
REQUEST_KEYS = {
    "$schema",
    "request_id",
    "program_id",
    "packet_id",
    "role",
    "domains",
    "authorized_permissions",
    "requested_capability_ids",
    "execution_order",
    "selection_rationale",
    "max_skills",
    "max_entrypoint_bytes",
}
ASSIGNMENT_SKILL_KEYS = {
    "capability_id",
    "entrypoint",
    "entrypoint_bytes",
    "entrypoint_sha256",
    "required_permissions",
    "selection_rationale",
    "source_commit",
    "source_id",
    "upstream_entrypoint_bytes",
    "upstream_entrypoint_sha256",
    "upstream_skill_path",
    "workspace_locator",
}


class CatalogError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise CatalogError("E_SCHEMA", f"{label} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise CatalogError(
            "E_SCHEMA",
            f"{label} keys differ; missing={sorted(expected - actual)!r}, "
            f"extra={sorted(actual - expected)!r}",
        )


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise CatalogError("E_SCHEMA", f"{label} is not a canonical identifier")
    return value


def _string(value: Any, label: str, *, maximum: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogError("E_SCHEMA", f"{label} must be a nonempty string")
    if maximum is not None and len(value) > maximum:
        raise CatalogError("E_SCHEMA", f"{label} exceeds {maximum} characters")
    return value


def _sorted_unique_strings(
    value: Any,
    label: str,
    *,
    pattern: re.Pattern[str] | None = None,
    allowed: set[str] | None = None,
    nonempty: bool = False,
) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise CatalogError("E_SCHEMA", f"{label} must be a{' nonempty' if nonempty else ''} array")
    if not all(isinstance(item, str) and item for item in value):
        raise CatalogError("E_SCHEMA", f"{label} must contain strings")
    if len(value) != len(set(value)) or value != sorted(value):
        raise CatalogError("E_SCHEMA", f"{label} must be unique and sorted")
    if pattern is not None and any(not pattern.fullmatch(item) for item in value):
        raise CatalogError("E_SCHEMA", f"{label} contains a noncanonical value")
    if allowed is not None and any(item not in allowed for item in value):
        raise CatalogError("E_SCHEMA", f"{label} contains an unsupported value")
    return value


def _ordered_unique_strings(
    value: Any,
    label: str,
    *,
    pattern: re.Pattern[str] | None = None,
) -> list[str]:
    if not isinstance(value, list):
        raise CatalogError("E_SCHEMA", f"{label} must be an array")
    if not all(isinstance(item, str) and item for item in value):
        raise CatalogError("E_SCHEMA", f"{label} must contain strings")
    if len(value) != len(set(value)):
        raise CatalogError("E_SCHEMA", f"{label} must be unique")
    if pattern is not None and any(not pattern.fullmatch(item) for item in value):
        raise CatalogError("E_SCHEMA", f"{label} contains a noncanonical value")
    return value


def _read_canonical_json(path: Path, label: str) -> Mapping[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CatalogError("E_PATH", f"{label} is not a regular non-symlink file")
    raw = path.read_bytes()
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogError("E_JSON", f"{label} is not valid UTF-8 JSON: {exc}") from exc
    obj = _object(parsed, label)
    if raw != canonical_bytes(obj):
        raise CatalogError("E_CANONICAL", f"{label} is not canonical JSON")
    return obj


def _relative_path(value: Any, label: str, *, required_prefix: str | None = None) -> str:
    text = _string(value, label)
    pure = PurePosixPath(text)
    if pure.is_absolute() or text != pure.as_posix() or any(part in {"", ".", ".."} for part in pure.parts):
        raise CatalogError("E_PATH", f"{label} is not a safe canonical relative path")
    if required_prefix is not None and (not pure.parts or pure.parts[0] != required_prefix):
        raise CatalogError("E_PATH", f"{label} must be beneath {required_prefix!r}")
    return text


def _safe_entrypoint(skill_root: Path, relative: str) -> Path:
    root = skill_root.resolve(strict=True)
    candidate = root / relative
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise CatalogError("E_PATH", f"entrypoint traverses symlink {relative!r}")
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise CatalogError("E_ENTRYPOINT", f"entrypoint is missing: {relative!r}") from exc
    if resolved.parent != root and root not in resolved.parents:
        raise CatalogError("E_PATH", f"entrypoint escapes the skill root: {relative!r}")
    if not resolved.is_file():
        raise CatalogError("E_ENTRYPOINT", f"entrypoint is not a regular file: {relative!r}")
    return resolved


def _validate_source(value: Any) -> dict[str, Any]:
    source = dict(_object(value, "source"))
    _exact_keys(source, SOURCE_KEYS, "source")
    _id(source["source_id"], "source.source_id")
    url = _string(source["canonical_url"], "source.canonical_url")
    if not url.startswith("https://"):
        raise CatalogError("E_SCHEMA", "source.canonical_url must use https")
    if not HEX40.fullmatch(str(source["source_commit"])) or not HEX40.fullmatch(str(source["source_tree"])):
        raise CatalogError("E_SCHEMA", "source commit and tree must be lowercase 40-hex")
    _string(source["observed_at"], "source.observed_at")
    license_value = dict(_object(source["license"], "source.license"))
    _exact_keys(license_value, LICENSE_KEYS, "source.license")
    spdx = license_value["spdx"]
    if spdx is not None:
        _string(spdx, "source.license.spdx")
    evidence_path = license_value["evidence_path"]
    if evidence_path is not None:
        _relative_path(evidence_path, "source.license.evidence_path")
    if license_value["redistribution"] not in {"allowed", "unknown", "prohibited", "not_applicable"}:
        raise CatalogError("E_SCHEMA", "source.license.redistribution is unsupported")
    if source["disposition"] not in DISPOSITIONS:
        raise CatalogError("E_SCHEMA", "source.disposition is unsupported")
    _sorted_unique_strings(source["risk_flags"], "source.risk_flags", pattern=PERMISSION_RE)
    return source


def _validate_capability(value: Any, sources: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    capability = dict(_object(value, "capability"))
    _exact_keys(capability, CAPABILITY_KEYS, "capability")
    capability_id = _id(capability["capability_id"], "capability.capability_id")
    _string(capability["name"], f"capability {capability_id}.name", maximum=96)
    _string(capability["description"], f"capability {capability_id}.description", maximum=280)
    source_id = _id(capability["source_id"], f"capability {capability_id}.source_id")
    if source_id not in sources:
        raise CatalogError("E_SOURCE", f"capability {capability_id!r} references an unknown source")
    _relative_path(
        capability["upstream_skill_path"],
        f"capability {capability_id}.upstream_skill_path",
    )
    if not isinstance(capability["upstream_entrypoint_sha256"], str) or not HEX64.fullmatch(
        capability["upstream_entrypoint_sha256"]
    ):
        raise CatalogError("E_SCHEMA", f"capability {capability_id!r} upstream digest is invalid")
    if (
        not isinstance(capability["upstream_entrypoint_bytes"], int)
        or isinstance(capability["upstream_entrypoint_bytes"], bool)
        or capability["upstream_entrypoint_bytes"] <= 0
    ):
        raise CatalogError("E_SCHEMA", f"capability {capability_id!r} upstream size is invalid")
    entrypoint = capability["entrypoint"]
    digest = capability["entrypoint_sha256"]
    entrypoint_bytes = capability["entrypoint_bytes"]
    if entrypoint is None:
        if digest is not None or entrypoint_bytes != 0:
            raise CatalogError("E_SCHEMA", f"capability {capability_id!r} has inconsistent empty entrypoint metadata")
    else:
        _relative_path(entrypoint, f"capability {capability_id}.entrypoint", required_prefix="vendor")
        if not isinstance(digest, str) or not HEX64.fullmatch(digest):
            raise CatalogError("E_SCHEMA", f"capability {capability_id!r} entrypoint digest is invalid")
        if not isinstance(entrypoint_bytes, int) or isinstance(entrypoint_bytes, bool) or entrypoint_bytes <= 0:
            raise CatalogError("E_SCHEMA", f"capability {capability_id!r} entrypoint size is invalid")
    roles = _sorted_unique_strings(capability["roles"], f"capability {capability_id}.roles", allowed=ROLES, nonempty=True)
    _sorted_unique_strings(capability["domains"], f"capability {capability_id}.domains", pattern=PERMISSION_RE, nonempty=True)
    _sorted_unique_strings(capability["tags"], f"capability {capability_id}.tags", pattern=PERMISSION_RE, nonempty=True)
    trust = capability["trust_state"]
    if trust not in TRUST_STATES:
        raise CatalogError("E_SCHEMA", f"capability {capability_id!r} trust state is invalid")
    if not isinstance(capability["dispatchable"], bool):
        raise CatalogError("E_SCHEMA", f"capability {capability_id!r} dispatchable must be boolean")
    if capability["load_policy"] != "explicit":
        raise CatalogError("E_POLICY", f"capability {capability_id!r} must use explicit loading")
    _sorted_unique_strings(
        capability["required_permissions"],
        f"capability {capability_id}.required_permissions",
        pattern=PERMISSION_RE,
    )
    _sorted_unique_strings(capability["conflicts"], f"capability {capability_id}.conflicts", pattern=ID_RE)
    if capability_id in capability["conflicts"]:
        raise CatalogError("E_CONFLICT", f"capability {capability_id!r} conflicts with itself")
    if capability["dispatchable"]:
        source = sources[source_id]
        if trust != "approved" or entrypoint is None:
            raise CatalogError("E_TRUST", f"dispatchable capability {capability_id!r} is not approved and materialized")
        if source["disposition"] not in {"vendor_curated_subset", "extract_wrapper"}:
            raise CatalogError("E_TRUST", f"dispatchable capability {capability_id!r} has a blocked source disposition")
        if source["disposition"] == "vendor_curated_subset" and source["license"]["redistribution"] != "allowed":
            raise CatalogError("E_LICENSE", f"vendored capability {capability_id!r} lacks redistribution authority")
    elif trust == "approved" and entrypoint is not None:
        raise CatalogError("E_TRUST", f"approved materialized capability {capability_id!r} must be dispatchable")
    _ = roles
    return capability


def validate_catalog(catalog: Mapping[str, Any], skill_root: Path, *, verify_files: bool = True) -> dict[str, Any]:
    expected = {"$schema", "schema_version", "catalog_id", "policy", "sources", "capabilities"}
    _exact_keys(catalog, expected, "catalog")
    if catalog["$schema"] != CATALOG_SCHEMA or catalog["schema_version"] != 1:
        raise CatalogError("E_SCHEMA", "catalog schema/version is unsupported")
    _id(catalog["catalog_id"], "catalog.catalog_id")
    policy = dict(_object(catalog["policy"], "catalog.policy"))
    _exact_keys(policy, POLICY_KEYS, "catalog.policy")
    for key in POLICY_KEYS:
        value = policy[key]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise CatalogError("E_SCHEMA", f"catalog.policy.{key} must be a positive integer")
    sources_list = catalog["sources"]
    capabilities_list = catalog["capabilities"]
    if not isinstance(sources_list, list) or not isinstance(capabilities_list, list):
        raise CatalogError("E_SCHEMA", "catalog sources and capabilities must be arrays")
    validated_sources = [_validate_source(item) for item in sources_list]
    if [item["source_id"] for item in validated_sources] != sorted(item["source_id"] for item in validated_sources):
        raise CatalogError("E_SCHEMA", "catalog sources must be sorted by source_id")
    sources = {item["source_id"]: item for item in validated_sources}
    if len(sources) != len(validated_sources):
        raise CatalogError("E_SCHEMA", "catalog source IDs must be unique")
    validated_capabilities = [_validate_capability(item, sources) for item in capabilities_list]
    ids = [item["capability_id"] for item in validated_capabilities]
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise CatalogError("E_SCHEMA", "catalog capabilities must have unique sorted IDs")
    known_ids = set(ids)
    for capability in validated_capabilities:
        unknown = set(capability["conflicts"]) - known_ids
        if unknown:
            raise CatalogError("E_CONFLICT", f"capability {capability['capability_id']!r} has unknown conflicts {sorted(unknown)!r}")
        if verify_files and capability["entrypoint"] is not None:
            path = _safe_entrypoint(skill_root, capability["entrypoint"])
            raw = path.read_bytes()
            if len(raw) != capability["entrypoint_bytes"]:
                raise CatalogError("E_ENTRYPOINT", f"entrypoint size drift for {capability['capability_id']!r}")
            if hashlib.sha256(raw).hexdigest() != capability["entrypoint_sha256"]:
                raise CatalogError("E_ENTRYPOINT", f"entrypoint digest drift for {capability['capability_id']!r}")
    return {
        "$schema": CATALOG_SCHEMA,
        "catalog_id": catalog["catalog_id"],
        "catalog_sha256": canonical_digest(catalog),
        "source_count": len(validated_sources),
        "capability_count": len(validated_capabilities),
        "dispatchable_count": sum(1 for item in validated_capabilities if item["dispatchable"]),
    }


def validate_request(request: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    _exact_keys(request, REQUEST_KEYS, "request")
    if request["$schema"] != REQUEST_SCHEMA:
        raise CatalogError("E_SCHEMA", "request schema is unsupported")
    for key in ("request_id", "program_id", "packet_id"):
        _id(request[key], f"request.{key}")
    if request["role"] not in ROLES:
        raise CatalogError("E_ROLE", "request role is unsupported")
    _sorted_unique_strings(request["domains"], "request.domains", pattern=PERMISSION_RE, nonempty=True)
    _sorted_unique_strings(request["authorized_permissions"], "request.authorized_permissions", pattern=PERMISSION_RE)
    requested = _sorted_unique_strings(
        request["requested_capability_ids"],
        "request.requested_capability_ids",
        pattern=ID_RE,
    )
    execution_order = _ordered_unique_strings(
        request["execution_order"],
        "request.execution_order",
        pattern=ID_RE,
    )
    if set(execution_order) != set(requested):
        raise CatalogError(
            "E_COMPOSITION",
            "execution_order must contain exactly the requested capability IDs",
        )
    rationale = _object(request["selection_rationale"], "request.selection_rationale")
    if set(rationale) != set(requested) or not all(isinstance(value, str) and value.strip() for value in rationale.values()):
        raise CatalogError("E_RATIONALE", "selection rationale must exactly cover requested capabilities")
    for key, policy_key in (
        ("max_skills", "max_skills_per_assignment"),
        ("max_entrypoint_bytes", "max_entrypoint_bytes_per_assignment"),
    ):
        value = request[key]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise CatalogError("E_LIMIT", f"request.{key} must be positive")
        if value > policy[policy_key]:
            raise CatalogError("E_LIMIT", f"request.{key} exceeds catalog policy")
    if len(requested) > request["max_skills"]:
        raise CatalogError("E_LIMIT", "requested capabilities exceed the task-local skill limit")
    return dict(request)


def _assignment_unsigned(value: Mapping[str, Any]) -> dict[str, Any]:
    unsigned = copy.deepcopy(dict(value))
    binding = dict(_object(unsigned.get("binding"), "assignment.binding"))
    binding["canonical_sha256"] = None
    unsigned["binding"] = binding
    return unsigned


def resolve_assignment(catalog: Mapping[str, Any], request: Mapping[str, Any], skill_root: Path) -> dict[str, Any]:
    validate_catalog(catalog, skill_root, verify_files=True)
    policy = _object(catalog["policy"], "catalog.policy")
    request = validate_request(request, policy)
    indexed = {item["capability_id"]: item for item in catalog["capabilities"]}
    selected: list[dict[str, Any]] = []
    selected_ids = set(request["requested_capability_ids"])
    total_bytes = 0
    for capability_id in request["requested_capability_ids"]:
        capability = indexed.get(capability_id)
        if capability is None:
            raise CatalogError("E_CAPABILITY", f"unknown capability {capability_id!r}")
        if not capability["dispatchable"] or capability["trust_state"] != "approved":
            raise CatalogError("E_TRUST", f"capability {capability_id!r} is not dispatchable")
        if request["role"] not in capability["roles"]:
            raise CatalogError("E_ROLE", f"capability {capability_id!r} is not allowed for role {request['role']!r}")
        if not set(request["domains"]).intersection(capability["domains"]):
            raise CatalogError("E_DOMAIN", f"capability {capability_id!r} does not match the task domains")
        missing_permissions = set(capability["required_permissions"]) - set(request["authorized_permissions"])
        if missing_permissions:
            raise CatalogError("E_PERMISSION", f"capability {capability_id!r} would widen permissions {sorted(missing_permissions)!r}")
        conflicts = set(capability["conflicts"]).intersection(selected_ids)
        if conflicts:
            raise CatalogError("E_CONFLICT", f"capability {capability_id!r} conflicts with {sorted(conflicts)!r}")
        path = _safe_entrypoint(skill_root, capability["entrypoint"])
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != capability["entrypoint_sha256"] or len(raw) != capability["entrypoint_bytes"]:
            raise CatalogError("E_ENTRYPOINT", f"entrypoint drift for {capability_id!r}")
        total_bytes += capability["entrypoint_bytes"]
        source = next(item for item in catalog["sources"] if item["source_id"] == capability["source_id"])
        selected.append(
            {
                "capability_id": capability_id,
                "entrypoint": capability["entrypoint"],
                "entrypoint_bytes": capability["entrypoint_bytes"],
                "entrypoint_sha256": capability["entrypoint_sha256"],
                "required_permissions": copy.deepcopy(capability["required_permissions"]),
                "selection_rationale": request["selection_rationale"][capability_id],
                "source_commit": source["source_commit"],
                "source_id": capability["source_id"],
                "upstream_entrypoint_bytes": capability["upstream_entrypoint_bytes"],
                "upstream_entrypoint_sha256": capability["upstream_entrypoint_sha256"],
                "upstream_skill_path": capability["upstream_skill_path"],
                "workspace_locator": (
                    "workspace://skills/company-os/assign-capability-skills/"
                    + PurePosixPath(capability["entrypoint"]).parent.as_posix()
                ),
            }
        )
    if total_bytes > request["max_entrypoint_bytes"]:
        raise CatalogError("E_LIMIT", "selected entrypoints exceed the task-local byte limit")
    assignment = {
        "$schema": ASSIGNMENT_SCHEMA,
        "schema_version": 1,
        "assignment_id": request["request_id"],
        "program_id": request["program_id"],
        "packet_id": request["packet_id"],
        "role": request["role"],
        "domains": copy.deepcopy(request["domains"]),
        "execution_order": copy.deepcopy(request["execution_order"]),
        "catalog_sha256": canonical_digest(catalog),
        "request_sha256": canonical_digest(request),
        "skill_count": len(selected),
        "total_entrypoint_bytes": total_bytes,
        "skills": selected,
        "binding": {"algorithm": BINDING_ALGORITHM, "canonical_sha256": None},
    }
    assignment["binding"]["canonical_sha256"] = canonical_digest(_assignment_unsigned(assignment))
    return assignment


def validate_assignment(assignment: Mapping[str, Any]) -> None:
    expected = {
        "$schema",
        "schema_version",
        "assignment_id",
        "program_id",
        "packet_id",
        "role",
        "domains",
        "execution_order",
        "catalog_sha256",
        "request_sha256",
        "skill_count",
        "total_entrypoint_bytes",
        "skills",
        "binding",
    }
    _exact_keys(assignment, expected, "assignment")
    if assignment["$schema"] != ASSIGNMENT_SCHEMA or assignment["schema_version"] != 1:
        raise CatalogError("E_SCHEMA", "assignment schema/version is unsupported")
    for key in ("assignment_id", "program_id", "packet_id"):
        _id(assignment[key], f"assignment.{key}")
    if assignment["role"] not in ROLES:
        raise CatalogError("E_ROLE", "assignment role is unsupported")
    _sorted_unique_strings(assignment["domains"], "assignment.domains", pattern=PERMISSION_RE, nonempty=True)
    execution_order = _ordered_unique_strings(
        assignment["execution_order"],
        "assignment.execution_order",
        pattern=ID_RE,
    )
    for key in ("catalog_sha256", "request_sha256"):
        if not isinstance(assignment[key], str) or not HEX64.fullmatch(assignment[key]):
            raise CatalogError("E_SCHEMA", f"assignment.{key} is invalid")
    if not isinstance(assignment["skills"], list):
        raise CatalogError("E_SCHEMA", "assignment.skills must be an array")
    if not isinstance(assignment["skill_count"], int) or isinstance(assignment["skill_count"], bool) or assignment["skill_count"] < 0:
        raise CatalogError("E_SCHEMA", "assignment skill_count must be a nonnegative integer")
    if not isinstance(assignment["total_entrypoint_bytes"], int) or isinstance(assignment["total_entrypoint_bytes"], bool) or assignment["total_entrypoint_bytes"] < 0:
        raise CatalogError("E_SCHEMA", "assignment total_entrypoint_bytes must be a nonnegative integer")
    skill_ids: list[str] = []
    for index, raw_skill in enumerate(assignment["skills"]):
        skill = dict(_object(raw_skill, f"assignment.skills[{index}]"))
        _exact_keys(skill, ASSIGNMENT_SKILL_KEYS, f"assignment.skills[{index}]")
        capability_id = _id(skill["capability_id"], f"assignment.skills[{index}].capability_id")
        skill_ids.append(capability_id)
        entrypoint = _relative_path(
            skill["entrypoint"],
            f"assignment.skills[{index}].entrypoint",
            required_prefix="vendor",
        )
        if not isinstance(skill["entrypoint_bytes"], int) or isinstance(skill["entrypoint_bytes"], bool) or skill["entrypoint_bytes"] <= 0:
            raise CatalogError("E_SCHEMA", f"assignment skill {capability_id!r} has invalid entrypoint bytes")
        if not isinstance(skill["upstream_entrypoint_bytes"], int) or isinstance(skill["upstream_entrypoint_bytes"], bool) or skill["upstream_entrypoint_bytes"] <= 0:
            raise CatalogError("E_SCHEMA", f"assignment skill {capability_id!r} has invalid upstream bytes")
        for key in ("entrypoint_sha256", "upstream_entrypoint_sha256"):
            if not isinstance(skill[key], str) or not HEX64.fullmatch(skill[key]):
                raise CatalogError("E_SCHEMA", f"assignment skill {capability_id!r} has invalid {key}")
        if not isinstance(skill["source_commit"], str) or not HEX40.fullmatch(skill["source_commit"]):
            raise CatalogError("E_SCHEMA", f"assignment skill {capability_id!r} has invalid source commit")
        _id(skill["source_id"], f"assignment.skills[{index}].source_id")
        _relative_path(skill["upstream_skill_path"], f"assignment.skills[{index}].upstream_skill_path")
        _string(skill["selection_rationale"], f"assignment.skills[{index}].selection_rationale")
        _sorted_unique_strings(
            skill["required_permissions"],
            f"assignment.skills[{index}].required_permissions",
            pattern=PERMISSION_RE,
        )
        expected_locator = (
            "workspace://skills/company-os/assign-capability-skills/"
            + PurePosixPath(entrypoint).parent.as_posix()
        )
        if skill["workspace_locator"] != expected_locator:
            raise CatalogError("E_PATH", f"assignment skill {capability_id!r} workspace locator is not bound to its entrypoint")
    if skill_ids != sorted(skill_ids) or len(skill_ids) != len(set(skill_ids)):
        raise CatalogError("E_SCHEMA", "assignment skills must have unique sorted capability IDs")
    if set(execution_order) != set(skill_ids):
        raise CatalogError(
            "E_COMPOSITION",
            "assignment execution_order must contain exactly the assigned capability IDs",
        )
    if assignment["skill_count"] != len(assignment["skills"]):
        raise CatalogError("E_SCHEMA", "assignment skill_count does not match skills")
    if assignment["total_entrypoint_bytes"] != sum(item.get("entrypoint_bytes", -1) for item in assignment["skills"]):
        raise CatalogError("E_SCHEMA", "assignment total_entrypoint_bytes does not match skills")
    binding = _object(assignment["binding"], "assignment.binding")
    _exact_keys(binding, {"algorithm", "canonical_sha256"}, "assignment.binding")
    if binding["algorithm"] != BINDING_ALGORITHM or not isinstance(binding["canonical_sha256"], str) or not HEX64.fullmatch(binding["canonical_sha256"]):
        raise CatalogError("E_BINDING", "assignment binding is invalid")
    if binding["canonical_sha256"] != canonical_digest(_assignment_unsigned(assignment)):
        raise CatalogError("E_BINDING", "assignment canonical digest does not verify")


def augment_host_manifest(
    catalog: Mapping[str, Any],
    base_host: Mapping[str, Any],
    request_assignment_pairs: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    skill_root: Path,
) -> dict[str, Any]:
    """Bind verified task-local skill assignments into a host manifest.

    The result contains references and digests only. Skill bodies remain lazy
    loaded from their exact workspace entrypoints by the assigned task.
    """

    evidence = validate_catalog(catalog, skill_root, verify_files=True)
    host = copy.deepcopy(dict(_object(base_host, "base host manifest")))
    if host.get("$id") != "company-os.host-capabilities.v1" or host.get("schema_version") != 1:
        raise CatalogError("E_HOST", "base host manifest schema/version is unsupported")
    program_id = _id(host.get("program_id"), "base host manifest.program_id")
    if not isinstance(host.get("runtimes"), list) or not isinstance(host.get("capabilities"), list):
        raise CatalogError("E_HOST", "base host manifest runtimes and capabilities must be arrays")
    if "skill_assignments" in host or any(
        isinstance(item, dict) and item.get("capability_kind") == "skill"
        for item in host["capabilities"]
    ):
        raise CatalogError(
            "E_HOST",
            "base host manifest already contains skill state; rebuild all assignments in one augmentation",
        )

    indexed_catalog = {item["capability_id"]: item for item in catalog["capabilities"]}
    runtimes = {item.get("runtime_id"): copy.deepcopy(item) for item in host["runtimes"] if isinstance(item, dict)}
    if len(runtimes) != len(host["runtimes"]) or None in runtimes:
        raise CatalogError("E_HOST", "base host manifest runtime IDs must be present and unique")
    capabilities = {
        item.get("capability_id"): copy.deepcopy(item)
        for item in host["capabilities"]
        if isinstance(item, dict)
    }
    if len(capabilities) != len(host["capabilities"]) or None in capabilities:
        raise CatalogError("E_HOST", "base host manifest capability IDs must be present and unique")

    selected_any = False
    assignment_records: list[dict[str, Any]] = []
    bound_packet_ids: set[str] = set()
    bound_packet_capabilities: set[tuple[str, str, str]] = set()
    for request, assignment in request_assignment_pairs:
        expected = resolve_assignment(catalog, request, skill_root)
        validate_assignment(assignment)
        if canonical_bytes(assignment) != canonical_bytes(expected):
            raise CatalogError("E_ASSIGNMENT_DRIFT", "assignment does not reproduce from its catalog and request")
        if assignment["program_id"] != program_id:
            raise CatalogError("E_HOST", "assignment program_id does not match the base host manifest")
        if assignment["packet_id"] in bound_packet_ids:
            raise CatalogError(
                "E_HOST",
                f"packet {assignment['packet_id']!r} has more than one capability assignment",
            )
        bound_packet_ids.add(assignment["packet_id"])
        if assignment["skills"]:
            assignment_records.append(
                {
                    "assignment": copy.deepcopy(dict(assignment)),
                    "request": copy.deepcopy(dict(request)),
                }
            )
        for skill in assignment["skills"]:
            selected_any = True
            capability_id = skill["capability_id"]
            identity = (assignment["packet_id"], assignment["role"], capability_id)
            if identity in bound_packet_capabilities:
                raise CatalogError("E_HOST", f"duplicate skill binding for packet capability {identity!r}")
            bound_packet_capabilities.add(identity)
            catalog_capability = indexed_catalog[capability_id]
            binding = {
                "assignment_id": assignment["assignment_id"],
                "assignment_sha256": assignment["binding"]["canonical_sha256"],
                "catalog_sha256": evidence["catalog_sha256"],
                "entrypoint_sha256": skill["entrypoint_sha256"],
                "packet_id": assignment["packet_id"],
                "request_sha256": assignment["request_sha256"],
                "role": assignment["role"],
                "source_commit": skill["source_commit"],
                "source_id": skill["source_id"],
                "upstream_entrypoint_sha256": skill["upstream_entrypoint_sha256"],
            }
            expected_capability = {
                "capability_id": capability_id,
                "available": True,
                "runtime_id": SKILL_RUNTIME_ID,
                "tool_locator": skill["workspace_locator"],
                "runtime_locator": SKILL_RUNTIME_LOCATOR,
                "capability_kind": "skill",
                "artifact_sha256": skill["entrypoint_sha256"],
                "skill_bindings": [binding],
            }
            current = capabilities.get(capability_id)
            if current is None:
                capabilities[capability_id] = expected_capability
                continue
            stable_keys = set(expected_capability) - {"skill_bindings"}
            if any(current.get(key) != expected_capability[key] for key in stable_keys):
                raise CatalogError("E_HOST", f"host capability {capability_id!r} conflicts with the assignment")
            bindings = current.get("skill_bindings")
            if not isinstance(bindings, list):
                raise CatalogError("E_HOST", f"host capability {capability_id!r} is not a skill capability")
            bindings.append(binding)
            current["skill_bindings"] = sorted(
                bindings,
                key=lambda item: (item["packet_id"], item["role"], item["assignment_id"]),
            )

    if not selected_any:
        return host

    required_runtime = {
        "runtime_id": SKILL_RUNTIME_ID,
        "runtime_type": SKILL_RUNTIME_TYPE,
        "available": True,
        "locator": SKILL_RUNTIME_LOCATOR,
    }
    existing_runtime = runtimes.get(SKILL_RUNTIME_ID)
    if existing_runtime is not None and existing_runtime != required_runtime:
        raise CatalogError("E_HOST", "the reserved skill runtime ID conflicts with the base host manifest")
    runtimes[SKILL_RUNTIME_ID] = required_runtime
    host["runtimes"] = sorted(runtimes.values(), key=lambda item: item["runtime_id"])
    host["capabilities"] = sorted(capabilities.values(), key=lambda item: item["capability_id"])
    host["skill_assignments"] = sorted(
        assignment_records,
        key=lambda item: item["assignment"]["assignment_id"],
    )
    return host


def search_catalog(
    catalog: Mapping[str, Any],
    query: str,
    *,
    role: str | None,
    domain: str | None,
    limit: int,
    dispatchable_only: bool = False,
) -> dict[str, Any]:
    tokens = set(TOKEN_RE.findall(query.lower()))
    if not tokens:
        raise CatalogError("E_QUERY", "search query must contain a word or number")
    if role is not None and role not in ROLES:
        raise CatalogError("E_ROLE", "search role is unsupported")
    maximum = catalog["policy"]["max_search_results"]
    if limit <= 0 or limit > maximum:
        raise CatalogError("E_LIMIT", f"search limit must be between 1 and {maximum}")
    matches: list[tuple[int, str, Mapping[str, Any]]] = []
    for capability in catalog["capabilities"]:
        if dispatchable_only and not capability["dispatchable"]:
            continue
        if role is not None and role not in capability["roles"]:
            continue
        if domain is not None and domain not in capability["domains"]:
            continue
        fields = {
            "id": set(TOKEN_RE.findall(capability["capability_id"].lower())),
            "name": set(TOKEN_RE.findall(capability["name"].lower())),
            "description": set(TOKEN_RE.findall(capability["description"].lower())),
            "tags": set(capability["tags"]),
            "domains": set(capability["domains"]),
        }
        score = (
            8 * len(tokens & fields["id"])
            + 6 * len(tokens & fields["name"])
            + 4 * len(tokens & fields["tags"])
            + 3 * len(tokens & fields["domains"])
            + len(tokens & fields["description"])
        )
        if score:
            matches.append((score, capability["capability_id"], capability))
    matches.sort(key=lambda item: (-item[0], item[1]))
    return {
        "$schema": "company-os.capability-search-results.v1",
        "catalog_sha256": canonical_digest(catalog),
        "query": query,
        "role": role,
        "domain": domain,
        "dispatchable_only": dispatchable_only,
        "results": [
            {
                "capability_id": capability["capability_id"],
                "description": capability["description"],
                "dispatchable": capability["dispatchable"],
                "domains": capability["domains"],
                "name": capability["name"],
                "roles": capability["roles"],
                "score": score,
                "source_id": capability["source_id"],
                "trust_state": capability["trust_state"],
            }
            for score, _, capability in matches[:limit]
        ],
    }


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists() and path.is_symlink():
        raise CatalogError("E_PATH", "output path may not be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(value)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _print(value: Mapping[str, Any]) -> None:
    print(canonical_bytes(value).decode("utf-8"), end="")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--catalog", type=Path, required=True)
    validate.add_argument("--skill-root", type=Path, required=True)
    search = sub.add_parser("search")
    search.add_argument("--catalog", type=Path, required=True)
    search.add_argument("--skill-root", type=Path, required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--role", choices=sorted(ROLES))
    search.add_argument("--domain")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--dispatchable-only", action="store_true")
    resolve = sub.add_parser("resolve")
    resolve.add_argument("--catalog", type=Path, required=True)
    resolve.add_argument("--request", type=Path, required=True)
    resolve.add_argument("--skill-root", type=Path, required=True)
    resolve.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--catalog", type=Path, required=True)
    verify.add_argument("--request", type=Path, required=True)
    verify.add_argument("--assignment", type=Path, required=True)
    verify.add_argument("--skill-root", type=Path, required=True)
    augment = sub.add_parser("augment-host")
    augment.add_argument("--catalog", type=Path, required=True)
    augment.add_argument("--skill-root", type=Path, required=True)
    augment.add_argument("--base-host", type=Path, required=True)
    augment.add_argument("--request", type=Path, action="append", required=True)
    augment.add_argument("--assignment", type=Path, action="append", required=True)
    augment.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        catalog = _read_canonical_json(args.catalog, "catalog")
        evidence = validate_catalog(catalog, args.skill_root, verify_files=True)
        if args.command == "validate":
            _print({"ok": True, **evidence})
            return 0
        if args.command == "search":
            _print(
                search_catalog(
                    catalog,
                    args.query,
                    role=args.role,
                    domain=args.domain,
                    limit=args.limit,
                    dispatchable_only=args.dispatchable_only,
                )
            )
            return 0
        if args.command == "augment-host":
            if len(args.request) != len(args.assignment):
                raise CatalogError("E_SCHEMA", "augment-host requires one assignment for each request")
            base_host = _read_canonical_json(args.base_host, "base host manifest")
            pairs = [
                (
                    _read_canonical_json(request_path, f"request[{index}]"),
                    _read_canonical_json(assignment_path, f"assignment[{index}]"),
                )
                for index, (request_path, assignment_path) in enumerate(zip(args.request, args.assignment))
            ]
            augmented = augment_host_manifest(catalog, base_host, pairs, args.skill_root)
            _write_atomic(args.output, augmented)
            _print(
                {
                    "ok": True,
                    "host_manifest": args.output.as_posix(),
                    "host_manifest_sha256": canonical_digest(augmented),
                    "assignment_count": len(pairs),
                    "skill_capability_count": sum(
                        1 for item in augmented["capabilities"] if item.get("capability_kind") == "skill"
                    ),
                }
            )
            return 0
        request = _read_canonical_json(args.request, "request")
        expected = resolve_assignment(catalog, request, args.skill_root)
        if args.command == "resolve":
            _write_atomic(args.output, expected)
            _print(
                {
                    "ok": True,
                    "assignment": args.output.as_posix(),
                    "assignment_sha256": expected["binding"]["canonical_sha256"],
                    "skill_count": expected["skill_count"],
                    "total_entrypoint_bytes": expected["total_entrypoint_bytes"],
                }
            )
            return 0
        assignment = _read_canonical_json(args.assignment, "assignment")
        validate_assignment(assignment)
        if canonical_bytes(assignment) != canonical_bytes(expected):
            raise CatalogError("E_ASSIGNMENT_DRIFT", "assignment does not reproduce from catalog and request")
        _print(
            {
                "ok": True,
                "assignment_sha256": assignment["binding"]["canonical_sha256"],
                "catalog_sha256": assignment["catalog_sha256"],
                "request_sha256": assignment["request_sha256"],
            }
        )
        return 0
    except CatalogError as exc:
        _print({"ok": False, "error": {"code": exc.code, "message": str(exc)}})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
