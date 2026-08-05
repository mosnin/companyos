#!/usr/bin/env python3
"""Build and verify entrypoint-level review bindings for dispatchable wrappers."""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import datetime as _datetime
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


DECISIONS_SCHEMA = "company-os.capability-review-decisions.v1"
REGISTRY_SCHEMA = "company-os.capability-review-registry.v1"
SOURCE_SCHEMA = "company-os.source-intelligence-registry.v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")
PHASES = {"analysis", "design", "implementation", "verification"}
EFFECT_CLASSES = {"no_effect", "project_local_write", "read_only_local"}
CHECKOUT_SCHEMA = "company-os.capability-review-checkouts.v1"
ACCEPTANCE_SCHEMA = "company-os.capability-review-acceptance.v1"
PORTABLE_BUNDLE_SCHEMA = "company-os.capability-review-portable-bundle.v1"
TRUST_ANCHOR_SCHEMA = "company-os.capability-review-trust-anchor.v1"
REVIEWER_AUTHORITY_SCHEMA = "company-os.reviewer-authority-receipt.v1"
NO_REDISTRIBUTION_AUTHORITY = "no_redistribution_authority_established"
EFFICACY_UNPROVEN = "unproven"
PERMISSIONS = {"fs_read", "fs_write", "process_test"}
ACCEPTED_VERDICT = "accepted"
REJECTED_VERDICT = "rejected"
SIGNATURE_ALGORITHM = "rsa-pkcs1v1.5-sha256"
BINDING_ALGORITHM = "sha256-canonical-json-v1"
DECISION_KEYS = {
    "capability_id", "review_id", "exclusive_family", "phase", "effect_class",
    "provider_boundary", "consumes_artifact_kinds", "produces_artifact_kinds",
    "upstream_references_admitted", "upstream_effect_observations",
    "wrapper_effect_ceiling", "review_decision", "upstream_transitive_references",
    "upstream_transitive_manifest_sha256", "claim_observations",
    "prompt_injection_findings", "efficacy_state", "license_evidence",
    "effect_conditions",
}
RECORD_KEYS = DECISION_KEYS | {
    "source_id", "source_intelligence_id", "source_review_sha256",
    "upstream_skill_path", "upstream_entrypoint_sha256",
    "upstream_entrypoint_bytes", "wrapper_entrypoint", "wrapper_entrypoint_sha256", "wrapper_entrypoint_bytes",
    "checkout_manifest_sha256", "source_checkout_commit", "source_checkout_tree",
    "roles", "domains", "required_permissions", "conflicts",
    "license_conclusion", "prompt_injection_boundary", "invalidation_triggers",
}


class ReviewError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ReviewError("E_SCHEMA", f"{label} must be an object")
    return value


def _exact(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ReviewError("E_SCHEMA", f"{label} keys differ")


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise ReviewError("E_SCHEMA", f"{label} is not a canonical identifier")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewError("E_SCHEMA", f"{label} must be a nonempty string")
    return value


def _ids(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value) or any(not isinstance(item, str) for item in value):
        raise ReviewError("E_SCHEMA", f"{label} must be an array of identifiers")
    if value != sorted(set(value)):
        raise ReviewError("E_SCHEMA", f"{label} must be sorted and unique")
    for item in value:
        _id(item, label)
    return value


def _read(path: Path, label: str, *, canonical: bool = True) -> Mapping[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReviewError("E_PATH", f"{label} is not a regular non-symlink file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewError("E_JSON", f"{label} is invalid JSON") from exc
    obj = _object(value, label)
    if canonical and raw != canonical_bytes(obj):
        raise ReviewError("E_CANONICAL", f"{label} is not canonical JSON")
    return obj


def _safe_file(root: Path, relative: str, label: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise ReviewError("E_PATH", f"{label} is not a safe relative path")
    root = root.resolve(strict=True)
    current = root
    for part in pure.parts:
        current /= part
        if current.is_symlink():
            raise ReviewError("E_PATH", f"{label} traverses a symlink")
    try:
        resolved = current.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ReviewError("E_PATH", f"{label} is missing") from exc
    if root != resolved.parent and root not in resolved.parents:
        raise ReviewError("E_PATH", f"{label} escapes its root")
    if not resolved.is_file():
        raise ReviewError("E_PATH", f"{label} is not a regular file")
    return resolved


def transitive_manifest_digest(references: list[Mapping[str, Any]]) -> str:
    """Digest the reviewer's path/size/blob manifest exactly.

    The entrypoint and license evidence are intentionally excluded.  This
    keeps the transitive closure binding independently tamper-evident.
    """
    lines = "".join(
        f"{item['path']}\t{item['bytes']}\t{item['sha256']}\n"
        for item in sorted(references, key=lambda item: item["path"])
    ).encode("utf-8")
    return hashlib.sha256(lines).hexdigest()


def _hex(value: Any, label: str, *, length: int = 64) -> str:
    pattern = HEX64 if length == 64 else re.compile(rf"^[0-9a-f]{{{length}}}$")
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ReviewError("E_SCHEMA", f"{label} must be lowercase {length}-hex")
    return value


def _safe_checkout_root(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value or not value.startswith("/"):
        raise ReviewError("E_PATH", f"{label} must be an absolute path")
    path = Path(value)
    if any(part in {"", ".", ".."} for part in PurePosixPath(value).parts):
        raise ReviewError("E_PATH", f"{label} must not contain dot path segments")
    if path.is_symlink() or not path.is_dir():
        raise ReviewError("E_PATH", f"{label} is not a regular checkout directory")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ReviewError("E_PATH", f"{label} is missing") from exc
    if resolved != path:
        raise ReviewError("E_PATH", f"{label} is not a canonical absolute path")
    return resolved


def _checkout_file(root: Path, relative: str, label: str) -> Path:
    return _safe_file(root, relative, label)


def _git_value(root: Path, expression: str, label: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "-C", str(root), "rev-parse", "--verify", expression],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReviewError("E_CHECKOUT", f"{label} cannot be verified") from exc
    value = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ReviewError("E_CHECKOUT", f"{label} is not a lowercase 40-hex git object")
    return value


def _validate_checkout_manifest(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    _exact(manifest, {"$schema", "schema_version", "sources"}, "checkout manifest")
    if manifest["$schema"] != CHECKOUT_SCHEMA or manifest["schema_version"] != 1:
        raise ReviewError("E_SCHEMA", "checkout manifest schema/version is unsupported")
    sources = manifest["sources"]
    if not isinstance(sources, list) or not sources:
        raise ReviewError("E_SCHEMA", "checkout manifest sources must be nonempty")
    validated: list[Mapping[str, Any]] = []
    for raw in sources:
        source = _object(raw, "checkout manifest source")
        _exact(source, {"checkout_path", "source_commit", "source_id", "source_tree"}, "checkout manifest source")
        _id(source["source_id"], "checkout manifest source_id")
        _hex(source["source_commit"], "checkout manifest source_commit", length=40)
        _hex(source["source_tree"], "checkout manifest source_tree", length=40)
        _safe_checkout_root(source["checkout_path"], f"checkout {source['source_id']}")
        validated.append(source)
    if [item["source_id"] for item in validated] != sorted(item["source_id"] for item in validated):
        raise ReviewError("E_SCHEMA", "checkout manifest sources must be sorted")
    if len({item["source_id"] for item in validated}) != len(validated):
        raise ReviewError("E_SCHEMA", "checkout manifest source IDs must be unique")
    return validated


def _read_checkout_manifest(path: Path) -> Mapping[str, Any]:
    return _read(path, "checkout manifest")


def _require_manifest(manifest: Mapping[str, Any] | Path | None) -> Mapping[str, Any]:
    if manifest is None:
        raise ReviewError("E_CHECKOUT", "checkout manifest is required")
    if isinstance(manifest, Path):
        manifest = _read_checkout_manifest(manifest)
    return manifest


def _manifest_digest(manifest: Mapping[str, Any]) -> str:
    return canonical_digest(manifest)


def _source_record(source_registry: Mapping[str, Any], catalog_source_id: str) -> Mapping[str, Any]:
    matches = [
        record for record in source_registry["records"]
        if record["source_id"] == catalog_source_id or catalog_source_id in record["catalog_source_ids"]
    ]
    if len(matches) != 1:
        raise ReviewError("E_SOURCE", f"catalog source {catalog_source_id!r} resolves to {len(matches)} records")
    return matches[0]


def _validate_references(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ReviewError("E_SCHEMA", f"{label} must be an array")
    result: list[dict[str, Any]] = []
    for raw in value:
        item = dict(_object(raw, label))
        _exact(item, {"path", "bytes", "sha256"}, f"{label} item")
        pure = PurePosixPath(item["path"])
        if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
            raise ReviewError("E_PATH", f"{label} path is unsafe")
        if not isinstance(item["bytes"], int) or isinstance(item["bytes"], bool) or item["bytes"] <= 0:
            raise ReviewError("E_SCHEMA", f"{label} bytes must be positive")
        _hex(item["sha256"], f"{label} sha256")
        result.append(item)
    if [item["path"] for item in result] != sorted(item["path"] for item in result):
        raise ReviewError("E_SCHEMA", f"{label} must be sorted by path")
    if len({item["path"] for item in result}) != len(result):
        raise ReviewError("E_SCHEMA", f"{label} paths must be unique")
    return result


def _observations(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ReviewError("E_SCHEMA", f"{label} must be an array of observations")
    if value != sorted(set(value)):
        raise ReviewError("E_SCHEMA", f"{label} must be sorted and unique")
    return value


def _validate_license_evidence(value: Any) -> dict[str, Any]:
    evidence = dict(_object(value, "license_evidence"))
    _exact(
        evidence,
        {"path", "bytes", "sha256", "spdx", "scope", "redistribution_conclusion"},
        "license_evidence",
    )
    pure = PurePosixPath(evidence["path"])
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise ReviewError("E_PATH", "license evidence path is unsafe")
    if not isinstance(evidence["bytes"], int) or isinstance(evidence["bytes"], bool) or evidence["bytes"] <= 0:
        raise ReviewError("E_SCHEMA", "license evidence bytes must be positive")
    _hex(evidence["sha256"], "license evidence sha256")
    _text(evidence["spdx"], "license evidence spdx")
    _text(evidence["scope"], "license evidence scope")
    if evidence["redistribution_conclusion"] != NO_REDISTRIBUTION_AUTHORITY:
        raise ReviewError("E_LICENSE", "license evidence must establish no redistribution authority")
    return evidence


def _validate_decision(decision: Mapping[str, Any], *, exact: bool = True) -> None:
    if exact:
        _exact(decision, DECISION_KEYS, "decision")
    for key in ("capability_id", "review_id", "exclusive_family", "provider_boundary", "wrapper_effect_ceiling"):
        _id(decision[key], f"decision.{key}")
    if decision["phase"] not in PHASES:
        raise ReviewError("E_PHASE", "decision phase is unsupported")
    if decision["effect_class"] not in EFFECT_CLASSES:
        raise ReviewError("E_EFFECT", "decision effect class is unsupported")
    _ids(decision["consumes_artifact_kinds"], "decision.consumes_artifact_kinds", nonempty=True)
    _ids(decision["produces_artifact_kinds"], "decision.produces_artifact_kinds", nonempty=True)
    _ids(decision["upstream_effect_observations"], "decision.upstream_effect_observations", nonempty=True)
    _validate_references(decision["upstream_transitive_references"], "decision.upstream_transitive_references")
    if decision["upstream_transitive_manifest_sha256"] != transitive_manifest_digest(decision["upstream_transitive_references"]):
        raise ReviewError("E_BINDING", "upstream transitive manifest digest does not verify")
    _observations(decision["claim_observations"], "decision.claim_observations", nonempty=True)
    _observations(decision["prompt_injection_findings"], "decision.prompt_injection_findings", nonempty=True)
    _validate_license_evidence(decision["license_evidence"])
    _ids(decision["effect_conditions"], "decision.effect_conditions")
    if decision["efficacy_state"] != EFFICACY_UNPROVEN:
        raise ReviewError("E_EFFICACY", "capability efficacy must remain unproven")
    if decision["upstream_references_admitted"] is not False:
        raise ReviewError("E_AUTHORITY", "upstream references must not be admitted")
    if decision["review_decision"] not in {"candidate_for_independent_acceptance", "approved_narrow_wrapper"}:
        raise ReviewError("E_DECISION", "review decision is unsupported")
    if decision["capability_id"] in {"capability-assessment", "risk-matrix", "scenario-development"} and decision["exclusive_family"] != "business_decision_lens":
        raise ReviewError("E_EXCLUSIVE_FAMILY", "business decision lenses must share one exclusive family")
    if decision["capability_id"] == "systematic-debugging":
        if decision["effect_class"] != "project_local_write":
            raise ReviewError("E_EFFECT", "systematic-debugging must expose conditional project-local write")
        if decision["wrapper_effect_ceiling"] != "conditional_packet_owned_project_write_after_supported_root_cause":
            raise ReviewError("E_EFFECT", "systematic-debugging write ceiling is not conditional")
        if decision["effect_conditions"] != ["packet_authorization", "supported_root_cause"]:
            raise ReviewError("E_EFFECT", "systematic-debugging effect conditions are incomplete")


def expected_permissions(effect_class: str, upstream_effect_observations: list[str]) -> list[str]:
    """Derive the narrow permission ceiling from the reviewed effect class."""
    if effect_class == "no_effect":
        return []
    if effect_class == "read_only_local":
        return ["fs_read"]
    if effect_class == "project_local_write":
        permissions = ["fs_read", "fs_write"]
        if any(
            any(token in observation.lower() for token in (
                "test_execution", "focused_test", "full_suite", "process_execution",
                "verification_execution", "test_run", "test_command",
            ))
            for observation in upstream_effect_observations
        ):
            permissions.append("process_test")
        return permissions
    raise ReviewError("E_EFFECT", f"unsupported effect class {effect_class!r}")


def validate_effect_permissions(record: Mapping[str, Any]) -> list[str]:
    permissions = record.get("required_permissions")
    if permissions is None:
        raise ReviewError("E_PERMISSION", f"record {record.get('capability_id')!r} lacks required permissions")
    actual = _ids(permissions, f"record {record.get('capability_id')}.required_permissions")
    if any(permission not in PERMISSIONS for permission in actual):
        raise ReviewError("E_PERMISSION", "record contains a permission outside fs_read/fs_write/process_test")
    expected = expected_permissions(record["effect_class"], record["upstream_effect_observations"])
    if actual != expected:
        raise ReviewError(
            "E_PERMISSION",
            f"record {record.get('capability_id')!r} permissions {actual!r} do not match effect ceiling {expected!r}",
        )
    if record["effect_class"] == "no_effect" and (record["effect_conditions"] or expected):
        raise ReviewError("E_EFFECT", "no_effect wrappers must be response-only with no conditions or permissions")
    return actual


def build_registry(
    decisions: Mapping[str, Any],
    catalog: Mapping[str, Any],
    source_registry: Mapping[str, Any],
    skill_root: Path,
    checkout_manifest: Mapping[str, Any] | Path | None = None,
) -> dict[str, Any]:
    if decisions.get("$schema") != DECISIONS_SCHEMA or decisions.get("schema_version") != 1:
        raise ReviewError("E_SCHEMA", "decision schema/version is unsupported")
    raw_decisions = decisions.get("decisions")
    if not isinstance(raw_decisions, list):
        raise ReviewError("E_SCHEMA", "decisions must be an array")
    for item in raw_decisions:
        _validate_decision(_object(item, "decision"))
    decision_index = {item["capability_id"]: item for item in raw_decisions}
    if len(decision_index) != len(raw_decisions):
        raise ReviewError("E_SCHEMA", "decision capability IDs must be unique")
    dispatchable = {item["capability_id"]: item for item in catalog["capabilities"] if item["dispatchable"]}
    if set(decision_index) != set(dispatchable):
        raise ReviewError("E_COVERAGE", "decisions must exactly cover dispatchable capabilities")
    manifest = _require_manifest(checkout_manifest)
    manifest_sources = _validate_checkout_manifest(manifest)
    manifest_by_id = {item["source_id"]: item for item in manifest_sources}
    dispatchable_sources = {item["source_id"] for item in dispatchable.values()}
    if set(manifest_by_id) != dispatchable_sources:
        raise ReviewError("E_COVERAGE", "checkout manifest must cover every dispatchable source exactly")
    manifest_sha256 = _manifest_digest(manifest)
    records = []
    for capability_id in sorted(dispatchable):
        capability = dispatchable[capability_id]
        decision = decision_index[capability_id]
        source = _source_record(source_registry, capability["source_id"])
        if source["evidence_class"] in {"invalid_unresolved", "duplicate_provenance_resolution"}:
            raise ReviewError("E_SOURCE", "dispatchable capability source is invalid or duplicate-only")
        checkout = manifest_by_id.get(capability["source_id"])
        if checkout is None:
            raise ReviewError("E_CHECKOUT", f"missing checkout for {capability['source_id']!r}")
        checkout_root = _safe_checkout_root(checkout["checkout_path"], f"checkout {capability['source_id']}")
        actual_commit = _git_value(checkout_root, "HEAD", f"checkout {capability['source_id']} commit")
        actual_tree = _git_value(checkout_root, "HEAD^{tree}", f"checkout {capability['source_id']} tree")
        if actual_commit != checkout["source_commit"] or actual_tree != checkout["source_tree"]:
            raise ReviewError("E_CHECKOUT", f"checkout pin drift for {capability['source_id']!r}")
        if source.get("pin") != checkout["source_commit"]:
            raise ReviewError("E_BINDING", f"source intelligence pin drift for {capability['source_id']!r}")
        upstream = _checkout_file(checkout_root, capability["upstream_skill_path"], "upstream entrypoint")
        upstream_raw = upstream.read_bytes()
        if len(upstream_raw) != capability["upstream_entrypoint_bytes"] or hashlib.sha256(upstream_raw).hexdigest() != capability["upstream_entrypoint_sha256"]:
            raise ReviewError("E_UPSTREAM", f"upstream entrypoint drift for {capability_id!r}")
        decision_refs = decision["upstream_transitive_references"]
        for ref in decision_refs:
            path = _checkout_file(checkout_root, ref["path"], "upstream transitive reference")
            raw_ref = path.read_bytes()
            if len(raw_ref) != ref["bytes"] or hashlib.sha256(raw_ref).hexdigest() != ref["sha256"]:
                raise ReviewError("E_UPSTREAM", f"transitive reference drift for {capability_id!r}")
        license_evidence = _validate_license_evidence(decision["license_evidence"])
        license_path = _checkout_file(checkout_root, license_evidence["path"], "license evidence")
        license_raw = license_path.read_bytes()
        if len(license_raw) != license_evidence["bytes"] or hashlib.sha256(license_raw).hexdigest() != license_evidence["sha256"]:
            raise ReviewError("E_LICENSE", f"license evidence drift for {capability_id!r}")
        wrapper = _safe_file(skill_root, capability["entrypoint"], "wrapper entrypoint")
        raw = wrapper.read_bytes()
        if hashlib.sha256(raw).hexdigest() != capability["entrypoint_sha256"] or len(raw) != capability["entrypoint_bytes"]:
            raise ReviewError("E_WRAPPER", f"wrapper drift for {capability_id!r}")
        record = dict(decision)
        record.update(
            {
                "source_id": capability["source_id"],
                "source_intelligence_id": source["source_id"],
                "source_review_sha256": source["review_evidence_sha256"],
                "upstream_skill_path": capability["upstream_skill_path"],
                "upstream_entrypoint_sha256": capability["upstream_entrypoint_sha256"],
                "upstream_entrypoint_bytes": capability["upstream_entrypoint_bytes"],
                "wrapper_entrypoint": capability["entrypoint"],
                "wrapper_entrypoint_sha256": capability["entrypoint_sha256"],
                "wrapper_entrypoint_bytes": capability["entrypoint_bytes"],
                "roles": capability["roles"],
                "domains": capability["domains"],
                "required_permissions": capability["required_permissions"],
                "conflicts": capability["conflicts"],
                "checkout_manifest_sha256": manifest_sha256,
                "source_checkout_commit": checkout["source_commit"],
                "source_checkout_tree": checkout["source_tree"],
                "license_conclusion": "source_acceptance_only_no_redistribution_claim",
                "prompt_injection_boundary": "upstream_content_not_loaded_at_dispatch",
                "invalidation_triggers": sorted(
                    {
                        "capability_metadata_change",
                        "source_review_or_disposition_change",
                        "upstream_entrypoint_digest_change",
                        "wrapper_entrypoint_digest_change",
                        "wrapper_effect_or_permission_change",
                    }
                ),
            }
        )
        records.append(record)
    registry = {
        "$schema": REGISTRY_SCHEMA,
        "schema_version": 1,
        "registry_id": "company-os-capability-entrypoint-reviews-2026-08-05",
        "catalog_sha256": canonical_digest(catalog),
        "source_intelligence_registry_sha256": canonical_digest(source_registry),
        "checkout_manifest_sha256": manifest_sha256,
        "review_count": len(records),
        "records": records,
    }
    validate_registry(registry, catalog, source_registry, skill_root, checkout_manifest)
    return registry


def validate_registry(
    registry: Mapping[str, Any],
    catalog: Mapping[str, Any],
    source_registry: Mapping[str, Any],
    skill_root: Path,
    checkout_manifest: Mapping[str, Any] | Path | None = None,
    *,
    require_accepted: bool = False,
) -> dict[str, Any]:
    expected = {
        "$schema", "schema_version", "registry_id", "catalog_sha256",
        "source_intelligence_registry_sha256", "checkout_manifest_sha256",
        "review_count", "records",
    }
    _exact(registry, expected, "registry")
    if registry["$schema"] != REGISTRY_SCHEMA or registry["schema_version"] != 1:
        raise ReviewError("E_SCHEMA", "review registry schema/version is unsupported")
    _id(registry["registry_id"], "registry.registry_id")
    if registry["catalog_sha256"] != canonical_digest(catalog):
        raise ReviewError("E_BINDING", "review registry catalog binding is stale")
    if registry["source_intelligence_registry_sha256"] != canonical_digest(source_registry):
        raise ReviewError("E_BINDING", "review registry source-intelligence binding is stale")
    manifest = _require_manifest(checkout_manifest)
    manifest_sources = _validate_checkout_manifest(manifest)
    manifest_by_id = {item["source_id"]: item for item in manifest_sources}
    dispatchable = {item["capability_id"]: item for item in catalog["capabilities"] if item["dispatchable"]}
    if set(manifest_by_id) != {item["source_id"] for item in dispatchable.values()}:
        raise ReviewError("E_COVERAGE", "checkout manifest must cover every dispatchable source exactly")
    manifest_sha256 = _manifest_digest(manifest)
    if registry["checkout_manifest_sha256"] != manifest_sha256:
        raise ReviewError("E_BINDING", "review registry checkout-manifest binding is stale")
    checkout_actuals: dict[str, Path] = {}
    for source_id, checkout in manifest_by_id.items():
        checkout_root = _safe_checkout_root(checkout["checkout_path"], f"checkout {source_id}")
        actual_commit = _git_value(checkout_root, "HEAD", f"checkout {source_id} commit")
        actual_tree = _git_value(checkout_root, "HEAD^{tree}", f"checkout {source_id} tree")
        if actual_commit != checkout["source_commit"] or actual_tree != checkout["source_tree"]:
            raise ReviewError("E_CHECKOUT", f"checkout pin drift for {source_id!r}")
        checkout_actuals[source_id] = checkout_root
    records = registry["records"]
    if not isinstance(records, list) or registry["review_count"] != len(records):
        raise ReviewError("E_COUNT", "review count does not match records")
    ids = []
    for raw in records:
        record = _object(raw, "record")
        _exact(record, RECORD_KEYS, "record")
        _validate_decision(record, exact=False)
        validate_effect_permissions(record)
        capability_id = record["capability_id"]
        ids.append(capability_id)
        capability = dispatchable.get(capability_id)
        if capability is None:
            raise ReviewError("E_COVERAGE", f"review {capability_id!r} is not a dispatchable capability")
        source = _source_record(source_registry, capability["source_id"])
        expected_values = {
            "source_id": capability["source_id"],
            "source_intelligence_id": source["source_id"],
            "source_review_sha256": source["review_evidence_sha256"],
            "upstream_skill_path": capability["upstream_skill_path"],
            "upstream_entrypoint_sha256": capability["upstream_entrypoint_sha256"],
            "upstream_entrypoint_bytes": capability["upstream_entrypoint_bytes"],
            "wrapper_entrypoint": capability["entrypoint"],
            "wrapper_entrypoint_sha256": capability["entrypoint_sha256"],
            "wrapper_entrypoint_bytes": capability["entrypoint_bytes"],
            "roles": capability["roles"],
            "domains": capability["domains"],
            "required_permissions": capability["required_permissions"],
            "conflicts": capability["conflicts"],
            "checkout_manifest_sha256": manifest_sha256,
            "source_checkout_commit": manifest_by_id[capability["source_id"]]["source_commit"],
            "source_checkout_tree": manifest_by_id[capability["source_id"]]["source_tree"],
        }
        if any(record[key] != value for key, value in expected_values.items()):
            raise ReviewError("E_BINDING", f"review binding differs for {capability_id!r}")
        if record["license_conclusion"] != "source_acceptance_only_no_redistribution_claim":
            raise ReviewError("E_LICENSE", "review cannot claim redistribution authority")
        if record["prompt_injection_boundary"] != "upstream_content_not_loaded_at_dispatch":
            raise ReviewError("E_AUTHORITY", "review must keep upstream content out of dispatch")
        _ids(record["roles"], "record.roles", nonempty=True)
        _ids(record["domains"], "record.domains", nonempty=True)
        _ids(record["required_permissions"], "record.required_permissions")
        _ids(record["conflicts"], "record.conflicts")
        _ids(record["invalidation_triggers"], "record.invalidation_triggers", nonempty=True)
        _validate_references(record["upstream_transitive_references"], "record.upstream_transitive_references")
        if record["upstream_transitive_manifest_sha256"] != transitive_manifest_digest(record["upstream_transitive_references"]):
            raise ReviewError("E_BINDING", f"transitive manifest digest differs for {capability_id!r}")
        _observations(record["claim_observations"], "record.claim_observations", nonempty=True)
        _observations(record["prompt_injection_findings"], "record.prompt_injection_findings", nonempty=True)
        _validate_license_evidence(record["license_evidence"])
        _ids(record["effect_conditions"], "record.effect_conditions")
        if record["efficacy_state"] != EFFICACY_UNPROVEN:
            raise ReviewError("E_EFFICACY", f"efficacy state is not unproven for {capability_id!r}")
        checkout_root = checkout_actuals[capability["source_id"]]
        upstream = _checkout_file(checkout_root, record["upstream_skill_path"], "review upstream entrypoint")
        raw_upstream = upstream.read_bytes()
        if len(raw_upstream) != record["upstream_entrypoint_bytes"] or hashlib.sha256(raw_upstream).hexdigest() != record["upstream_entrypoint_sha256"]:
            raise ReviewError("E_UPSTREAM", f"reviewed upstream drift for {capability_id!r}")
        for ref in record["upstream_transitive_references"]:
            ref_path = _checkout_file(checkout_root, ref["path"], "review transitive reference")
            raw_ref = ref_path.read_bytes()
            if len(raw_ref) != ref["bytes"] or hashlib.sha256(raw_ref).hexdigest() != ref["sha256"]:
                raise ReviewError("E_UPSTREAM", f"reviewed transitive reference drift for {capability_id!r}")
        license_evidence = record["license_evidence"]
        license_path = _checkout_file(checkout_root, license_evidence["path"], "review license evidence")
        raw_license = license_path.read_bytes()
        if len(raw_license) != license_evidence["bytes"] or hashlib.sha256(raw_license).hexdigest() != license_evidence["sha256"]:
            raise ReviewError("E_LICENSE", f"reviewed license evidence drift for {capability_id!r}")
        wrapper = _safe_file(skill_root, record["wrapper_entrypoint"], "review wrapper")
        raw_wrapper = wrapper.read_bytes()
        if hashlib.sha256(raw_wrapper).hexdigest() != record["wrapper_entrypoint_sha256"] or len(raw_wrapper) != record["wrapper_entrypoint_bytes"]:
            raise ReviewError("E_WRAPPER", f"reviewed wrapper drift for {capability_id!r}")
        if require_accepted and record["review_decision"] != "approved_narrow_wrapper":
            raise ReviewError("E_DECISION", f"capability {capability_id!r} lacks independent acceptance")
    if ids != sorted(ids) or len(ids) != len(set(ids)) or set(ids) != set(dispatchable):
        raise ReviewError("E_COVERAGE", "reviews must be sorted, unique, and cover every dispatchable capability")
    return {
        "$schema": REGISTRY_SCHEMA,
        "registry_id": registry["registry_id"],
        "registry_sha256": canonical_digest(registry),
        "catalog_sha256": registry["catalog_sha256"],
        "source_intelligence_registry_sha256": registry["source_intelligence_registry_sha256"],
        "checkout_manifest_sha256": registry["checkout_manifest_sha256"],
        "review_count": len(records),
        "accepted_count": sum(1 for item in records if item["review_decision"] == "approved_narrow_wrapper"),
        "candidate_count": sum(1 for item in records if item["review_decision"] == "candidate_for_independent_acceptance"),
    }


def resolve_reviews(
    registry: Mapping[str, Any],
    catalog: Mapping[str, Any],
    source_registry: Mapping[str, Any],
    skill_root: Path,
    capability_ids: list[str],
    checkout_manifest: Mapping[str, Any] | Path | None = None,
    *,
    require_accepted: bool = True,
) -> dict[str, Any]:
    """Resolve a small accepted review set and reject semantic-family collisions."""
    evidence = validate_registry(
        registry,
        catalog,
        source_registry,
        skill_root,
        checkout_manifest,
        require_accepted=require_accepted,
    )
    if capability_ids != sorted(set(capability_ids)):
        raise ReviewError("E_SCHEMA", "requested capability IDs must be sorted and unique")
    index = {record["capability_id"]: record for record in registry["records"]}
    selected = []
    families: dict[str, str] = {}
    for capability_id in capability_ids:
        _id(capability_id, "capability_id")
        record = index.get(capability_id)
        if record is None:
            raise ReviewError("E_CAPABILITY", f"capability {capability_id!r} lacks a review")
        family = record["exclusive_family"]
        prior = families.get(family)
        if prior is not None:
            raise ReviewError(
                "E_EXCLUSIVE_FAMILY",
                f"capabilities {prior!r} and {capability_id!r} share exclusive family {family!r}",
            )
        families[family] = capability_id
        selected.append(
            {
                "capability_id": capability_id,
                "review_id": record["review_id"],
                "review_sha256": canonical_digest(record),
                "exclusive_family": family,
                "phase": record["phase"],
                "effect_class": record["effect_class"],
                "provider_boundary": record["provider_boundary"],
                "consumes_artifact_kinds": record["consumes_artifact_kinds"],
                "produces_artifact_kinds": record["produces_artifact_kinds"],
                "upstream_effect_observations": record["upstream_effect_observations"],
            }
        )
    return {
        "$schema": "company-os.capability-review-resolution.v1",
        "registry_sha256": evidence["registry_sha256"],
        "capability_ids": capability_ids,
        "reviews": selected,
    }


# ---------------------------------------------------------------------------
# Independently authenticated acceptance and portable dispatch evidence
# ---------------------------------------------------------------------------

ACCEPTANCE_KEYS = {
    "$schema", "schema_version", "receipt_id", "reviewer_id", "reviewer_role",
    "reviewer_authority_receipt", "candidate_digest", "catalog_sha256",
    "source_intelligence_registry_sha256", "checkout_manifest_sha256",
    "selected_capability_ids", "selected_review_record_digests", "verdict", "issued_at", "expires_at", "scope",
    "trust_anchor_id", "signature",
}
SIGNATURE_KEYS = {"algorithm", "key_id", "value"}
AUTHORITY_KEYS = {
    "$schema", "schema_version", "receipt_id", "reviewer_id", "authority", "status",
    "issued_at", "expires_at", "scope",
}
PORTABLE_KEYS = {
    "$schema", "schema_version", "bundle_id", "candidate_registry_sha256",
    "catalog_sha256", "source_intelligence_registry_sha256", "checkout_manifest_sha256",
    "trust_anchor_id", "trust_anchor_sha256", "acceptance_receipt",
    "acceptance_receipt_sha256", "selected_capability_ids", "scope", "created_at",
    "records", "live_checkout_proof", "binding",
}


def _utc_now() -> _datetime.datetime:
    return _datetime.datetime.now(_datetime.timezone.utc)


def _time(value: Any, label: str) -> _datetime.datetime:
    if not isinstance(value, str) or not value.strip():
        raise ReviewError("E_TIME", f"{label} must be an RFC3339 timestamp")
    try:
        parsed = _datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewError("E_TIME", f"{label} is not an RFC3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ReviewError("E_TIME", f"{label} must include a timezone")
    return parsed.astimezone(_datetime.timezone.utc)


def _now(value: _datetime.datetime | str | None) -> _datetime.datetime:
    if value is None:
        return _utc_now()
    if isinstance(value, _datetime.datetime):
        if value.tzinfo is None:
            raise ReviewError("E_TIME", "now must include a timezone")
        return value.astimezone(_datetime.timezone.utc)
    return _time(value, "now")


def _anchor_material(anchor: Mapping[str, Any] | str | bytes) -> tuple[str, str, bytes]:
    """Return (anchor id, algorithm, DER public key) from an injected anchor.

    The verifier intentionally accepts public material only.  It never creates,
    stores, or discovers a signing key; callers must inject the trust anchor.
    """
    anchor_id: str | None = None
    algorithm = SIGNATURE_ALGORITHM
    material: bytes | None = None
    if isinstance(anchor, Mapping):
        if any("PRIVATE" in str(value).upper() for value in anchor.values()):
            raise ReviewError("E_TRUST", "trust anchor contains forbidden signing material")
        anchor_id = anchor.get("anchor_id") or anchor.get("key_id")
        algorithm = str(anchor.get("algorithm", SIGNATURE_ALGORITHM))
        value = anchor.get("public_key_pem", anchor.get("public_key"))
        if isinstance(value, str):
            material = value.encode("ascii")
        elif isinstance(value, (bytes, bytearray)):
            material = bytes(value)
        elif isinstance(anchor.get("public_key_der_b64"), str):
            try:
                material = base64.b64decode(anchor["public_key_der_b64"], validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ReviewError("E_TRUST", "trust anchor public key encoding is invalid") from exc
    elif isinstance(anchor, str):
        material = anchor.encode("ascii")
    elif isinstance(anchor, (bytes, bytearray)):
        material = bytes(anchor)
    if material is None:
        raise ReviewError("E_TRUST", "an injected public trust anchor is required")
    if b"PRIVATE KEY" in material.upper():
        raise ReviewError("E_TRUST", "trust anchor contains forbidden signing material")
    if algorithm != SIGNATURE_ALGORITHM:
        raise ReviewError("E_TRUST", "unsupported acceptance signature algorithm")
    if anchor_id is None:
        anchor_id = "rsa-anchor-" + hashlib.sha256(material).hexdigest()[:24]
    _id(anchor_id, "trust anchor id")
    return anchor_id, algorithm, material


def trust_anchor_digest(anchor: Mapping[str, Any] | str | bytes) -> str:
    """Digest only the injected public trust anchor, never a signing secret."""
    if isinstance(anchor, Mapping):
        public = dict(anchor)
        for key in tuple(public):
            if "PRIVATE" in str(public[key]).upper():
                raise ReviewError("E_TRUST", "trust anchor contains forbidden signing material")
        return canonical_digest(public)
    return hashlib.sha256(bytes(anchor, "ascii") if isinstance(anchor, str) else bytes(anchor)).hexdigest()


def _der_tlv(raw: bytes, offset: int = 0) -> tuple[int, bytes, int]:
    if offset >= len(raw):
        raise ReviewError("E_TRUST", "public key DER is truncated")
    tag = raw[offset]
    offset += 1
    if offset >= len(raw):
        raise ReviewError("E_TRUST", "public key DER length is truncated")
    length = raw[offset]
    offset += 1
    if length & 0x80:
        count = length & 0x7F
        if count == 0 or count > 4 or offset + count > len(raw):
            raise ReviewError("E_TRUST", "public key DER length is invalid")
        length = int.from_bytes(raw[offset:offset + count], "big")
        offset += count
    end = offset + length
    if end > len(raw):
        raise ReviewError("E_TRUST", "public key DER value is truncated")
    return tag, raw[offset:end], end


def _der_integer(value: bytes, label: str) -> int:
    if not value or value[0] & 0x80:
        raise ReviewError("E_TRUST", f"{label} is not a positive DER integer")
    number = int.from_bytes(value, "big")
    if number <= 0:
        raise ReviewError("E_TRUST", f"{label} is empty")
    return number


def _rsa_numbers(material: bytes) -> tuple[int, int]:
    pem = material.strip()
    if pem.startswith(b"-----BEGIN"):
        lines = pem.splitlines()
        if len(lines) < 3 or not lines[0].startswith(b"-----BEGIN"):
            raise ReviewError("E_TRUST", "public key PEM is invalid")
        if b"PRIVATE" in lines[0].upper():
            raise ReviewError("E_TRUST", "private signing material is not accepted")
        try:
            der = base64.b64decode(b"".join(lines[1:-1]), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ReviewError("E_TRUST", "public key PEM body is invalid") from exc
    else:
        der = pem
    tag, outer, end = _der_tlv(der)
    if tag != 0x30 or end != len(der):
        raise ReviewError("E_TRUST", "public key must be a DER sequence")
    # SubjectPublicKeyInfo: AlgorithmIdentifier + BIT STRING(RSAPublicKey).
    first_tag, first, cursor = _der_tlv(outer)
    second_tag, second, cursor2 = _der_tlv(outer, cursor)
    if cursor2 != len(outer):
        raise ReviewError("E_TRUST", "public key sequence has trailing data")
    if first_tag == 0x30 and second_tag == 0x03:
        if not second or second[0] != 0:
            raise ReviewError("E_TRUST", "public key bit string is invalid")
        inner = second[1:]
    elif first_tag == 0x02 and second_tag == 0x02:
        inner = outer
    else:
        raise ReviewError("E_TRUST", "public key is not RSA SubjectPublicKeyInfo")
    tag, sequence, cursor = _der_tlv(inner)
    if tag != 0x30 or cursor != len(inner):
        raise ReviewError("E_TRUST", "RSA public key sequence is invalid")
    n_tag, n_raw, cursor = _der_tlv(sequence)
    e_tag, e_raw, cursor = _der_tlv(sequence, cursor)
    if n_tag != 0x02 or e_tag != 0x02 or cursor != len(sequence):
        raise ReviewError("E_TRUST", "RSA public key integers are invalid")
    n = _der_integer(n_raw, "RSA modulus")
    e = _der_integer(e_raw, "RSA exponent")
    if e < 3 or e % 2 == 0 or n.bit_length() < 2048:
        raise ReviewError("E_TRUST", "RSA trust anchor strength is insufficient")
    return n, e


def verify_asymmetric_signature(payload: bytes, signature_b64: str, anchor: Mapping[str, Any] | str | bytes) -> None:
    """Verify an RSA PKCS#1 v1.5 SHA-256 signature using injected public data."""
    _, algorithm, material = _anchor_material(anchor)
    if algorithm != SIGNATURE_ALGORITHM:
        raise ReviewError("E_TRUST", "unsupported acceptance signature algorithm")
    try:
        signature = base64.b64decode(signature_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ReviewError("E_SIGNATURE", "signature is not base64") from exc
    n, e = _rsa_numbers(material)
    size = (n.bit_length() + 7) // 8
    if len(signature) != size:
        raise ReviewError("E_SIGNATURE", "signature length does not match trust anchor")
    value = pow(int.from_bytes(signature, "big"), e, n).to_bytes(size, "big")
    digest_info = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(payload).digest()
    expected = b"\x00\x01" + b"\xff" * (size - len(digest_info) - 3) + b"\x00" + digest_info
    if value != expected:
        raise ReviewError("E_SIGNATURE", "acceptance signature does not verify")


def _receipt_unsigned(receipt: Mapping[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(dict(receipt))
    value.pop("signature", None)
    return value


def _selected_record_digests(
    records: list[Mapping[str, Any]],
    capability_ids: list[str],
) -> list[dict[str, str]]:
    index = {record["capability_id"]: record for record in records}
    if len(index) != len(records):
        raise ReviewError("E_SCHEMA", "review records contain duplicate capability IDs")
    result: list[dict[str, str]] = []
    for capability_id in capability_ids:
        record = index.get(capability_id)
        if record is None:
            raise ReviewError("E_SELECTION", f"selected capability {capability_id!r} lacks a review record")
        result.append({"capability_id": capability_id, "record_sha256": canonical_digest(record)})
    return result


def _validate_selected_record_digests(value: Any, capability_ids: list[str]) -> list[dict[str, str]]:
    if not isinstance(value, list) or [item.get("capability_id") for item in value if isinstance(item, Mapping)] != capability_ids:
        raise ReviewError("E_SELECTION", "selected review record digests do not match selected IDs")
    result: list[dict[str, str]] = []
    for item in value:
        item = dict(_object(item, "selected review record digest"))
        _exact(item, {"capability_id", "record_sha256"}, "selected review record digest")
        _id(item["capability_id"], "selected review record digest capability_id")
        _hex(item["record_sha256"], "selected review record digest record_sha256")
        result.append(item)
    if [item["capability_id"] for item in result] != capability_ids:
        raise ReviewError("E_SELECTION", "selected review record digests must be sorted and unique")
    return result


def _scope_operation_id(scope: Mapping[str, Any]) -> str:
    operation_id = scope.get("operation_id")
    if not isinstance(operation_id, str) or not operation_id.strip():
        raise ReviewError("E_SCOPE", "scope.operation_id is required for replay-safe production use")
    _id(operation_id, "scope.operation_id")
    return operation_id


def _check_replay(
    replay_state: Any,
    receipt_id: str,
    operation_id: str,
) -> None:
    """Reject cross-operation reuse without changing the replay ledger."""
    if replay_state is None:
        raise ReviewError("E_REPLAY_REQUIRED", "production verification requires replay state")
    if hasattr(replay_state, "check") and callable(replay_state.check):
        accepted = replay_state.check(receipt_id, operation_id)
        if accepted is False:
            raise ReviewError("E_REPLAY", "acceptance receipt has already been consumed")
        return
    if isinstance(replay_state, set):
        if receipt_id in replay_state:
            raise ReviewError("E_REPLAY", "acceptance receipt has already been consumed")
        for value in replay_state:
            if isinstance(value, tuple) and len(value) == 2 and value[0] == receipt_id and value[1] != operation_id:
                raise ReviewError("E_REPLAY", "acceptance receipt has already been consumed by another operation")
        return
    if isinstance(replay_state, Mapping):
        consumed = replay_state.get("consumed_receipts")
        if consumed is None:
            return
        if not isinstance(consumed, Mapping):
            raise ReviewError("E_REPLAY", "replay state consumed_receipts must be an object")
        prior = consumed.get(receipt_id)
        if prior is not None and prior != operation_id:
            raise ReviewError("E_REPLAY", "acceptance receipt has already been consumed by another operation")
        return


def commit_replay_use(
    replay_state: Any,
    receipt_id: str,
    operation_id: str,
) -> None:
    """Commit a previously checked replay use after the complete operation succeeds."""
    _check_replay(replay_state, receipt_id, operation_id)
    if hasattr(replay_state, "consume") and callable(replay_state.consume):
        try:
            accepted = replay_state.consume(receipt_id, operation_id)
        except TypeError:
            accepted = replay_state.consume(receipt_id)
        if accepted is False:
            raise ReviewError("E_REPLAY", "acceptance receipt has already been consumed")
        return
    if isinstance(replay_state, set):
        key = (receipt_id, operation_id)
        if key in replay_state:
            return
        replay_state.add(key)
        return
    if isinstance(replay_state, Mapping):
        # A mutable JSON-safe ledger is accepted as the portable CLI interface.
        consumed = replay_state.get("consumed_receipts")
        if consumed is None:
            try:
                replay_state["consumed_receipts"] = {}
                consumed = replay_state["consumed_receipts"]
            except Exception as exc:
                raise ReviewError("E_REPLAY", "replay state is not mutable") from exc
        if not isinstance(consumed, dict):
            raise ReviewError("E_REPLAY", "replay state consumed_receipts must be an object")
        prior = consumed.get(receipt_id)
        if prior == operation_id:
            return
        consumed[receipt_id] = operation_id
        return
    raise ReviewError("E_REPLAY", "replay state does not implement receipt consumption")


def _scope(value: Any, label: str = "scope") -> dict[str, Any]:
    scope = dict(_object(value, label))
    if not scope:
        raise ReviewError("E_SCOPE", f"{label} must not be empty")
    # Scope is data, not authority.  Canonicalization prevents equivalent JSON
    # spellings from becoming two different acceptance domains.
    canonical_bytes(scope)
    return scope


def _identity_values(value: Any, key_hint: str = "") -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            hint = str(key).lower()
            if hint == "reviewer_id":
                found.update(_identity_values(item, hint))
                continue
            if isinstance(item, str) and (hint.endswith("id") or hint.endswith("_id") or hint in {"author", "worker", "manager", "producer", "subject"}):
                found.add(item)
            found.update(_identity_values(item, hint))
    elif isinstance(value, list):
        for item in value:
            found.update(_identity_values(item, key_hint))
    return found


def _validate_authority_receipt(
    value: Any,
    reviewer_id: str,
    *,
    now: _datetime.datetime,
    expected_scope: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    authority = dict(_object(value, "reviewer_authority_receipt"))
    _exact(authority, AUTHORITY_KEYS, "reviewer authority receipt")
    if authority["$schema"] != REVIEWER_AUTHORITY_SCHEMA or authority["schema_version"] != 1:
        raise ReviewError("E_AUTHORITY", "reviewer authority receipt schema/version is unsupported")
    _id(authority["receipt_id"], "reviewer authority receipt receipt_id")
    _id(authority["reviewer_id"], "reviewer authority receipt reviewer_id")
    if authority["reviewer_id"] != reviewer_id:
        raise ReviewError("E_AUTHORITY", "reviewer authority receipt does not name the reviewer")
    if authority["authority"] != "independent_capability_review":
        raise ReviewError("E_AUTHORITY", "reviewer authority is not independent capability review")
    if authority["status"] != "active":
        raise ReviewError("E_AUTHORITY", "reviewer authority receipt is not active")
    issued = _time(authority["issued_at"], "reviewer authority receipt issued_at")
    expires = _time(authority["expires_at"], "reviewer authority receipt expires_at")
    if expires <= issued or now < issued or now >= expires:
        raise ReviewError("E_AUTHORITY", "reviewer authority receipt is expired or not yet valid")
    authority_scope = _scope(authority["scope"], "reviewer authority receipt scope")
    if expected_scope is not None and authority_scope != dict(expected_scope):
        raise ReviewError("E_AUTHORITY", "reviewer authority scope does not match acceptance scope")
    return authority


def _validate_signature(value: Any, anchor_id: str) -> str:
    if isinstance(value, str):
        return value
    signature = dict(_object(value, "signature"))
    _exact(signature, SIGNATURE_KEYS, "signature")
    if signature["algorithm"] != SIGNATURE_ALGORITHM or signature["key_id"] != anchor_id:
        raise ReviewError("E_SIGNATURE", "signature algorithm or key ID is not bound to the trust anchor")
    if not isinstance(signature["value"], str) or not signature["value"]:
        raise ReviewError("E_SIGNATURE", "signature value is empty")
    return signature["value"]


def validate_acceptance_receipt(
    receipt: Mapping[str, Any],
    trust_anchor: Mapping[str, Any] | str | bytes,
    *,
    candidate_digest: str | None = None,
    catalog_sha256: str | None = None,
    source_intelligence_registry_sha256: str | None = None,
    checkout_manifest_sha256: str | None = None,
    selected_capability_ids: list[str] | None = None,
    selected_review_record_digests: list[Mapping[str, Any]] | None = None,
    expected_scope: Mapping[str, Any] | None = None,
    now: _datetime.datetime | str | None = None,
    used_receipt_ids: set[str] | None = None,
    replay_state: Any = None,
    subject_identity: Mapping[str, Any] | None = None,
    require_accepted: bool = True,
) -> dict[str, Any]:
    value = dict(_object(receipt, "acceptance receipt"))
    _exact(value, ACCEPTANCE_KEYS, "acceptance receipt")
    if value["$schema"] != ACCEPTANCE_SCHEMA or value["schema_version"] != 1:
        raise ReviewError("E_SCHEMA", "acceptance receipt schema/version is unsupported")
    for key in ("receipt_id", "reviewer_id", "trust_anchor_id"):
        _id(value[key], f"acceptance receipt {key}")
    if value["reviewer_role"] in {"author", "worker", "manager", "candidate"}:
        raise ReviewError("E_AUTHORITY", "author/worker/manager cannot act as independent reviewer")
    current = _now(now)
    _validate_authority_receipt(
        value["reviewer_authority_receipt"], value["reviewer_id"], now=current,
        expected_scope=expected_scope,
    )
    _hex(value["candidate_digest"], "acceptance receipt candidate_digest")
    for key in ("catalog_sha256", "source_intelligence_registry_sha256", "checkout_manifest_sha256"):
        _hex(value[key], f"acceptance receipt {key}")
    ids = _ids(value["selected_capability_ids"], "acceptance receipt selected_capability_ids", nonempty=True)
    if value["verdict"] not in {ACCEPTED_VERDICT, REJECTED_VERDICT}:
        raise ReviewError("E_DECISION", "acceptance verdict is unsupported")
    if require_accepted and value["verdict"] != ACCEPTED_VERDICT:
        raise ReviewError("E_DECISION", "acceptance receipt verdict is not accepted")
    issued = _time(value["issued_at"], "acceptance receipt issued_at")
    expires = _time(value["expires_at"], "acceptance receipt expires_at")
    if expires <= issued:
        raise ReviewError("E_TIME", "acceptance receipt expiry must be after issuance")
    if current < issued:
        raise ReviewError("E_TIME", "acceptance receipt is not yet valid")
    if current >= expires:
        raise ReviewError("E_EXPIRED", "acceptance receipt is expired")
    scope = _scope(value["scope"], "acceptance receipt scope")
    if expected_scope is not None and scope != dict(expected_scope):
        raise ReviewError("E_SCOPE", "acceptance receipt scope does not match the requested scope")
    if candidate_digest is not None and value["candidate_digest"] != candidate_digest:
        raise ReviewError("E_BINDING", "acceptance receipt candidate digest is stale")
    for key, expected in (
        ("catalog_sha256", catalog_sha256),
        ("source_intelligence_registry_sha256", source_intelligence_registry_sha256),
        ("checkout_manifest_sha256", checkout_manifest_sha256),
    ):
        if expected is not None and value[key] != expected:
            raise ReviewError("E_BINDING", f"acceptance receipt {key} is stale")
    if selected_capability_ids is not None and ids != sorted(set(selected_capability_ids)):
        raise ReviewError("E_SELECTION", "acceptance receipt selected IDs do not match the requested selection")
    selected_record_digests = _validate_selected_record_digests(value["selected_review_record_digests"], ids)
    if selected_review_record_digests is not None and selected_record_digests != [dict(item) for item in selected_review_record_digests]:
        raise ReviewError("E_BINDING", "acceptance receipt selected review record digests are stale")
    if used_receipt_ids is not None and value["receipt_id"] in used_receipt_ids:
        raise ReviewError("E_REPLAY", "acceptance receipt has already been consumed")
    identities = _identity_values(value["scope"]) | _identity_values(value["reviewer_authority_receipt"])
    if subject_identity is not None:
        identities |= _identity_values(subject_identity)
    if value["reviewer_id"] in identities:
        raise ReviewError("E_SELF_REVIEW", "reviewer identity overlaps candidate author/worker/manager identity")
    if expected_scope is not None:
        expected_scope_value = _scope(expected_scope, "expected scope")
        for required in ("program_id", "packet_id", "purpose", "operation_id"):
            if required not in expected_scope_value:
                raise ReviewError("E_SCOPE", f"expected scope lacks required {required}")
        _scope_operation_id(expected_scope_value)
    anchor_id, _, _ = _anchor_material(trust_anchor)
    if value["trust_anchor_id"] != anchor_id:
        raise ReviewError("E_TRUST", "acceptance receipt trust anchor is not trusted")
    signature_value = _validate_signature(value["signature"], anchor_id)
    verify_asymmetric_signature(canonical_bytes(_receipt_unsigned(value)), signature_value, trust_anchor)
    if replay_state is not None:
        _check_replay(replay_state, value["receipt_id"], _scope_operation_id(scope))
    return {
        "$schema": ACCEPTANCE_SCHEMA,
        "receipt_id": value["receipt_id"],
        "reviewer_id": value["reviewer_id"],
        "candidate_digest": value["candidate_digest"],
        "selected_capability_ids": ids,
        "selected_review_record_digests": selected_record_digests,
        "verdict": value["verdict"],
        "trust_anchor_id": anchor_id,
        "receipt_sha256": canonical_digest(value),
        "issued_at": value["issued_at"],
        "expires_at": value["expires_at"],
        "scope": scope,
    }


def build_acceptance_receipt(
    *,
    receipt_id: str,
    reviewer_id: str,
    reviewer_role: str,
    reviewer_authority_receipt: Mapping[str, Any],
    candidate: Mapping[str, Any] | None = None,
    candidate_digest: str | None = None,
    catalog_sha256: str,
    source_intelligence_registry_sha256: str,
    checkout_manifest_sha256: str,
    selected_capability_ids: list[str],
    selected_review_record_digests: list[Mapping[str, Any]] | None = None,
    verdict: str,
    issued_at: str,
    expires_at: str,
    scope: Mapping[str, Any],
    trust_anchor: Mapping[str, Any] | str | bytes,
    signature: Mapping[str, Any] | str,
) -> dict[str, Any]:
    """Construct, but never sign, an acceptance receipt.

    A caller must supply an externally produced signature and an injected public
    anchor.  There is deliberately no local signer or private-key path.
    """
    if candidate_digest is None:
        if candidate is None:
            raise ReviewError("E_BINDING", "candidate or candidate_digest is required")
        candidate_digest = canonical_digest(candidate)
    _hex(candidate_digest, "candidate_digest")
    selected_capability_ids = sorted(set(selected_capability_ids))
    if selected_review_record_digests is None:
        if candidate is None or not isinstance(candidate.get("records"), list):
            raise ReviewError("E_BINDING", "candidate records or selected review record digests are required")
        selected_review_record_digests = _selected_record_digests(candidate["records"], selected_capability_ids)
    else:
        selected_review_record_digests = _validate_selected_record_digests(
            selected_review_record_digests, selected_capability_ids,
        )
    anchor_id, _, _ = _anchor_material(trust_anchor)
    receipt = {
        "$schema": ACCEPTANCE_SCHEMA,
        "schema_version": 1,
        "receipt_id": receipt_id,
        "reviewer_id": reviewer_id,
        "reviewer_role": reviewer_role,
        "reviewer_authority_receipt": copy.deepcopy(dict(reviewer_authority_receipt)),
        "candidate_digest": candidate_digest,
        "catalog_sha256": catalog_sha256,
        "source_intelligence_registry_sha256": source_intelligence_registry_sha256,
        "checkout_manifest_sha256": checkout_manifest_sha256,
        "selected_capability_ids": selected_capability_ids,
        "selected_review_record_digests": copy.deepcopy(list(selected_review_record_digests)),
        "verdict": verdict,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "scope": copy.deepcopy(dict(scope)),
        "trust_anchor_id": anchor_id,
        "signature": copy.deepcopy(dict(signature)) if isinstance(signature, Mapping) else signature,
    }
    # Validate all fields and cryptographically verify the externally supplied
    # signature before returning a receipt that can be persisted or dispatched.
    validate_acceptance_receipt(receipt, trust_anchor, require_accepted=False)
    return receipt


def _bundle_unsigned(bundle: Mapping[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(dict(bundle))
    binding = dict(value.get("binding", {}))
    binding["canonical_sha256"] = None
    value["binding"] = binding
    return value


def _portable_record(record: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(record)
    _validate_decision(value, exact=False)
    for key in (
        "source_id", "source_intelligence_id", "source_review_sha256", "upstream_skill_path",
        "upstream_entrypoint_sha256", "wrapper_entrypoint", "wrapper_entrypoint_sha256",
        "checkout_manifest_sha256", "source_checkout_commit", "source_checkout_tree",
    ):
        if key not in value:
            raise ReviewError("E_PORTABLE", f"portable record lacks {key}")
    _hex(value["source_review_sha256"], "portable source review digest")
    _hex(value["wrapper_entrypoint_sha256"], "portable wrapper digest")
    _hex(value["upstream_entrypoint_sha256"], "portable upstream digest")
    _hex(value["checkout_manifest_sha256"], "portable checkout digest")
    _hex(value["source_checkout_commit"], "portable source commit", length=40)
    _hex(value["source_checkout_tree"], "portable source tree", length=40)
    _validate_references(value["upstream_transitive_references"], "portable transitive references")
    _validate_license_evidence(value["license_evidence"])
    if value["upstream_references_admitted"] is not False:
        raise ReviewError("E_AUTHORITY", "portable upstream references cannot become authority")
    if value["review_decision"] not in {"candidate_for_independent_acceptance", "approved_narrow_wrapper"}:
        raise ReviewError("E_DECISION", "portable bundle contains an unsupported review decision")
    return copy.deepcopy(value)


def verify_portable_bundle(
    bundle: Mapping[str, Any],
    trust_anchor: Mapping[str, Any] | str | bytes,
    *,
    catalog: Mapping[str, Any] | None = None,
    source_registry: Mapping[str, Any] | None = None,
    skill_root: Path | None = None,
    expected_scope: Mapping[str, Any] | None = None,
    now: _datetime.datetime | str | None = None,
    used_receipt_ids: set[str] | None = None,
    replay_state: Any = None,
    commit_replay: bool = True,
) -> dict[str, Any]:
    value = dict(_object(bundle, "portable bundle"))
    _exact(value, PORTABLE_KEYS, "portable bundle")
    if value["$schema"] != PORTABLE_BUNDLE_SCHEMA or value["schema_version"] != 1:
        raise ReviewError("E_SCHEMA", "portable bundle schema/version is unsupported")
    for key in ("bundle_id", "trust_anchor_id"):
        _id(value[key], f"portable bundle {key}")
    for key in (
        "candidate_registry_sha256", "catalog_sha256", "source_intelligence_registry_sha256",
        "checkout_manifest_sha256", "trust_anchor_sha256", "acceptance_receipt_sha256",
    ):
        _hex(value[key], f"portable bundle {key}")
    _time(value["created_at"], "portable bundle created_at")
    ids = _ids(value["selected_capability_ids"], "portable bundle selected_capability_ids", nonempty=True)
    scope = _scope(value["scope"], "portable bundle scope")
    if expected_scope is not None and scope != dict(expected_scope):
        raise ReviewError("E_SCOPE", "portable bundle scope does not match the requested scope")
    binding = dict(_object(value["binding"], "portable bundle binding"))
    _exact(binding, {"algorithm", "canonical_sha256"}, "portable bundle binding")
    if binding["algorithm"] != BINDING_ALGORITHM or binding["canonical_sha256"] != canonical_digest(_bundle_unsigned(value)):
        raise ReviewError("E_BINDING", "portable bundle binding does not verify")
    anchor_id, _, _ = _anchor_material(trust_anchor)
    if value["trust_anchor_id"] != anchor_id or value["trust_anchor_sha256"] != trust_anchor_digest(trust_anchor):
        raise ReviewError("E_TRUST", "portable bundle trust anchor binding is stale")
    receipt = value["acceptance_receipt"]
    if value["acceptance_receipt_sha256"] != canonical_digest(receipt):
        raise ReviewError("E_BINDING", "portable acceptance receipt digest is stale")
    receipt_evidence = validate_acceptance_receipt(
        receipt,
        trust_anchor,
        candidate_digest=value["candidate_registry_sha256"],
        catalog_sha256=value["catalog_sha256"],
        source_intelligence_registry_sha256=value["source_intelligence_registry_sha256"],
        checkout_manifest_sha256=value["checkout_manifest_sha256"],
        selected_capability_ids=ids,
        expected_scope=scope,
        now=now,
        used_receipt_ids=used_receipt_ids,
        replay_state=replay_state,
        require_accepted=True,
    )
    if catalog is not None and canonical_digest(catalog) != value["catalog_sha256"]:
        raise ReviewError("E_BINDING", "portable catalog digest is stale")
    if source_registry is not None and canonical_digest(source_registry) != value["source_intelligence_registry_sha256"]:
        raise ReviewError("E_BINDING", "portable source-intelligence digest is stale")
    records = value["records"]
    if not isinstance(records, list) or [r.get("capability_id") for r in records if isinstance(r, Mapping)] != ids:
        raise ReviewError("E_SELECTION", "portable records do not exactly match selected IDs")
    record_digests = {item["capability_id"]: item["record_sha256"] for item in receipt["selected_review_record_digests"]}
    for raw in records:
        record = _portable_record(_object(raw, "portable record"))
        if canonical_digest(record) != record_digests.get(record["capability_id"]):
            raise ReviewError("E_BINDING", f"portable review record digest is not signed for {record['capability_id']!r}")
        if record["checkout_manifest_sha256"] != value["checkout_manifest_sha256"]:
            raise ReviewError("E_BINDING", "portable record checkout binding is stale")
        if skill_root is not None:
            wrapper = _safe_file(skill_root, record["wrapper_entrypoint"], "portable wrapper")
            raw_wrapper = wrapper.read_bytes()
            if len(raw_wrapper) != record["wrapper_entrypoint_bytes"] or hashlib.sha256(raw_wrapper).hexdigest() != record["wrapper_entrypoint_sha256"]:
                raise ReviewError("E_WRAPPER", f"portable wrapper drift for {record['capability_id']!r}")
    proof = _object(value["live_checkout_proof"], "portable live checkout proof")
    _exact(proof, {"$schema", "schema_version", "manifest_sha256", "sources"}, "portable live checkout proof")
    if proof["$schema"] != CHECKOUT_SCHEMA or proof["schema_version"] != 1 or proof["manifest_sha256"] != value["checkout_manifest_sha256"]:
        raise ReviewError("E_BINDING", "portable checkout proof is stale")
    _ids([item["source_id"] for item in proof["sources"]], "portable checkout proof source IDs")
    if replay_state is not None and commit_replay:
        commit_replay_use(replay_state, receipt_evidence["receipt_id"], _scope_operation_id(scope))
    return {
        "$schema": PORTABLE_BUNDLE_SCHEMA,
        "bundle_id": value["bundle_id"],
        "bundle_sha256": canonical_digest(value),
        "candidate_registry_sha256": value["candidate_registry_sha256"],
        "catalog_sha256": value["catalog_sha256"],
        "selected_capability_ids": ids,
        "acceptance_receipt_sha256": value["acceptance_receipt_sha256"],
        "receipt_id": receipt_evidence["receipt_id"],
        "trust_anchor_id": anchor_id,
    }


def build_portable_bundle(
    registry: Mapping[str, Any],
    catalog: Mapping[str, Any],
    source_registry: Mapping[str, Any],
    skill_root: Path,
    checkout_manifest: Mapping[str, Any] | Path,
    acceptance_receipt: Mapping[str, Any],
    trust_anchor: Mapping[str, Any] | str | bytes,
    selected_capability_ids: list[str],
    *,
    expected_scope: Mapping[str, Any] | None = None,
    now: _datetime.datetime | str | None = None,
    replay_state: Any = None,
    bundle_id: str = "company-os-capability-review-portable-bundle-v1",
) -> dict[str, Any]:
    evidence = validate_registry(registry, catalog, source_registry, skill_root, checkout_manifest, require_accepted=False)
    ids = sorted(set(selected_capability_ids))
    if ids != selected_capability_ids or not ids:
        raise ReviewError("E_SELECTION", "selected capability IDs must be sorted and nonempty")
    if any(record["review_decision"] != "candidate_for_independent_acceptance" for record in registry["records"]):
        raise ReviewError("E_DECISION", "promotion input must remain an unaccepted candidate registry")
    receipt_evidence = validate_acceptance_receipt(
        acceptance_receipt,
        trust_anchor,
        candidate_digest=canonical_digest(registry),
        catalog_sha256=canonical_digest(catalog),
        source_intelligence_registry_sha256=canonical_digest(source_registry),
        checkout_manifest_sha256=evidence["checkout_manifest_sha256"],
        selected_capability_ids=ids,
        selected_review_record_digests=_selected_record_digests(registry["records"], ids),
        expected_scope=expected_scope,
        now=now,
        replay_state=replay_state,
        require_accepted=True,
    )
    anchor_id, _, _ = _anchor_material(trust_anchor)
    manifest = _require_manifest(checkout_manifest)
    records_by_id = {record["capability_id"]: record for record in registry["records"]}
    records = [_portable_record(copy.deepcopy(records_by_id[capability_id])) for capability_id in ids]
    proof_sources = [
        {"source_id": item["source_id"], "source_commit": item["source_commit"], "source_tree": item["source_tree"]}
        for item in _validate_checkout_manifest(manifest)
    ]
    bundle = {
        "$schema": PORTABLE_BUNDLE_SCHEMA,
        "schema_version": 1,
        "bundle_id": bundle_id,
        "candidate_registry_sha256": canonical_digest(registry),
        "catalog_sha256": canonical_digest(catalog),
        "source_intelligence_registry_sha256": canonical_digest(source_registry),
        "checkout_manifest_sha256": evidence["checkout_manifest_sha256"],
        "trust_anchor_id": anchor_id,
        "trust_anchor_sha256": trust_anchor_digest(trust_anchor),
        "acceptance_receipt": copy.deepcopy(dict(acceptance_receipt)),
        "acceptance_receipt_sha256": canonical_digest(acceptance_receipt),
        "selected_capability_ids": ids,
        "scope": copy.deepcopy(dict(acceptance_receipt["scope"])),
        "created_at": acceptance_receipt["issued_at"],
        "records": records,
        "live_checkout_proof": {
            "$schema": CHECKOUT_SCHEMA,
            "schema_version": 1,
            "manifest_sha256": evidence["checkout_manifest_sha256"],
            "sources": proof_sources,
        },
        "binding": {"algorithm": BINDING_ALGORITHM, "canonical_sha256": None},
    }
    bundle["binding"]["canonical_sha256"] = canonical_digest(_bundle_unsigned(bundle))
    verify_portable_bundle(
        bundle, trust_anchor, catalog=catalog, source_registry=source_registry,
        skill_root=skill_root, expected_scope=expected_scope, now=now,
        replay_state=replay_state,
    )
    return bundle


def promote_selected_reviews(
    registry: Mapping[str, Any],
    catalog: Mapping[str, Any],
    source_registry: Mapping[str, Any],
    skill_root: Path,
    checkout_manifest: Mapping[str, Any] | Path,
    acceptance_receipt: Mapping[str, Any],
    trust_anchor: Mapping[str, Any] | str | bytes,
    selected_capability_ids: list[str],
    *,
    expected_scope: Mapping[str, Any] | None = None,
    now: _datetime.datetime | str | None = None,
    replay_state: Any = None,
) -> dict[str, Any]:
    """Promote only the signed selected IDs into a portable dispatch bundle."""
    return build_portable_bundle(
        registry, catalog, source_registry, skill_root, checkout_manifest,
        acceptance_receipt, trust_anchor, selected_capability_ids,
        expected_scope=expected_scope, now=now, replay_state=replay_state,
    )


# Short aliases make the contract discoverable to callers while preserving one
# implementation and one verification gate.
verify_acceptance = validate_acceptance_receipt
verify_portable = verify_portable_bundle
promote = promote_selected_reviews


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "verify", "resolve"):
        command = sub.add_parser(name)
        command.add_argument("--catalog", type=Path, required=True)
        command.add_argument("--source-intelligence", type=Path, required=True)
        command.add_argument("--skill-root", type=Path, required=True)
        command.add_argument("--checkout-manifest", type=Path, required=True)
        if name == "build":
            command.add_argument("--decisions", type=Path, required=True)
            command.add_argument("--output", type=Path, required=True)
        else:
            command.add_argument("--registry", type=Path, required=True)
            command.add_argument("--require-accepted", action="store_true")
            if name == "resolve":
                command.add_argument("--capability-id", action="append", default=[])
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        catalog = _read(args.catalog, "catalog")
        source_registry = _read(args.source_intelligence, "source intelligence")
        if source_registry.get("$schema") != SOURCE_SCHEMA:
            raise ReviewError("E_SCHEMA", "source-intelligence schema is unsupported")
        if args.command == "build":
            registry = build_registry(
                _read(args.decisions, "decisions"), catalog, source_registry, args.skill_root, args.checkout_manifest
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(canonical_bytes(registry))
            evidence = validate_registry(registry, catalog, source_registry, args.skill_root, args.checkout_manifest)
        elif args.command == "verify":
            evidence = validate_registry(
                _read(args.registry, "review registry"),
                catalog,
                source_registry,
                args.skill_root,
                args.checkout_manifest,
                require_accepted=args.require_accepted,
            )
        else:
            evidence = resolve_reviews(
                _read(args.registry, "review registry"),
                catalog,
                source_registry,
                args.skill_root,
                sorted(args.capability_id),
                args.checkout_manifest,
                require_accepted=args.require_accepted,
            )
        print(canonical_bytes(evidence).decode(), end="")
        return 0
    except ReviewError as exc:
        print(canonical_bytes({"code": exc.code, "error": str(exc), "ok": False}).decode(), end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
