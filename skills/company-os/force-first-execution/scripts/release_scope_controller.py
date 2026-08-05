#!/usr/bin/env python3
"""Evaluate authenticated, predeclared release scope without weakening gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
from pathlib import Path
from typing import Any

import force_loop_controller as force
import rsa_trust
import seal_force_snapshot as force_snapshot


CONTRACT_SCHEMA = "company-os.release-scope.v1"
STATUS_SCHEMA = "company-os.release-status.v1"
DESIGN_DECISION_SCHEMA = "company-os.release-scope-design-decision.v1"
DELIVERABLE_RECEIPT_SCHEMA = "company-os.release-deliverable-receipt.v1"
SNAPSHOT_RECEIPT_SCHEMA = "company-os.force-log-snapshot.v1"
ADMISSION_SCHEMA = "company-os.release-scope-admission.v1"
ADMISSION_VERIFICATION_SCHEMA = "company-os.release-scope-admission-verification.v1"
ADMISSION_REGISTRY_SCHEMA = "company-os.release-scope-admission-registry.v1"
AUTH_SCHEME = rsa_trust.SCHEME
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
REGISTRY_FILE = re.compile(r"^definition-([0-9]{8})\.json$")


class ReleaseScopeError(ValueError):
    """Raised when release-scope evidence is invalid."""


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError) as error:
        raise ReleaseScopeError(f"value is not canonical JSON: {error}") from error


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ReleaseScopeError(
            f"{label} keys differ; extra={sorted(actual - expected)!r}, "
            f"missing={sorted(expected - actual)!r}"
        )


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ReleaseScopeError(f"{label} is invalid")
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise ReleaseScopeError(f"{label} must be lowercase SHA-256")
    return value


def _safe_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SAFE_PATH.fullmatch(value):
        raise ReleaseScopeError(f"{label} must be a safe project-relative path")
    if value.startswith("/") or "//" in value or any(
        part in {"", ".", ".."} for part in value.split("/")
    ):
        raise ReleaseScopeError(f"{label} must not escape or contain ambiguous segments")
    return value


def _root(path: Path) -> Path:
    if path.is_symlink():
        raise ReleaseScopeError("artifact root must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ReleaseScopeError(f"artifact root could not be resolved: {error}") from error
    if not resolved.is_dir():
        raise ReleaseScopeError("artifact root must be a directory")
    return resolved


def _trusted_master_public_key(root: Path, path: Path) -> Path:
    """Resolve the host trust anchor and keep it outside manager-owned evidence."""
    if path.is_symlink():
        raise ReleaseScopeError("trusted master public key must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ReleaseScopeError(
            f"trusted master public key could not be resolved: {error}"
        ) from error
    if resolved == root or root in resolved.parents:
        raise ReleaseScopeError(
            "trusted master public key must be supplied outside the artifact root"
        )
    try:
        rsa_trust.read_public_key(resolved, "trusted master public key")
    except rsa_trust.TrustError as error:
        raise ReleaseScopeError(str(error)) from error
    return resolved


def _trusted_admission_registry(root: Path, path: Path) -> Path:
    if path.is_symlink():
        raise ReleaseScopeError("trusted admission registry must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
        status = resolved.lstat()
    except OSError as error:
        raise ReleaseScopeError(
            f"trusted admission registry could not be resolved: {error}"
        ) from error
    if not stat.S_ISDIR(status.st_mode):
        raise ReleaseScopeError("trusted admission registry must be a directory")
    if resolved == root or root in resolved.parents:
        raise ReleaseScopeError(
            "trusted admission registry must be supplied outside the artifact root"
        )
    return resolved


def _registry_program_directory(
    registry_root: Path,
    contract: dict[str, Any],
    *,
    create: bool,
) -> Path:
    current = registry_root
    for key in ("project_id", "program_id", "cycle_id"):
        part = _identifier(contract[key], f"registry.{key}")
        current = current / part
        if create:
            try:
                current.mkdir(mode=0o700)
                force_snapshot._fsync_directory(current.parent)
            except FileExistsError:
                pass
            except OSError as error:
                raise ReleaseScopeError(
                    f"trusted admission registry could not create its program path: {error}"
                ) from error
        try:
            status = current.lstat()
        except FileNotFoundError as error:
            raise ReleaseScopeError("release scope has no registered admission") from error
        except OSError as error:
            raise ReleaseScopeError(
                f"trusted admission registry program path is unreadable: {error}"
            ) from error
        if stat.S_ISLNK(status.st_mode) or not stat.S_ISDIR(status.st_mode):
            raise ReleaseScopeError(
                "trusted admission registry program path must be a real directory"
            )
    return current


def _admission_registry_record(
    contract: dict[str, Any],
    trusted_master_public_key: Path,
) -> dict[str, Any]:
    try:
        raw_key, _, _ = rsa_trust.read_public_key(
            trusted_master_public_key, "trusted master public key"
        )
    except rsa_trust.TrustError as error:
        raise ReleaseScopeError(str(error)) from error
    return {
        "schema": ADMISSION_REGISTRY_SCHEMA,
        "project_id": contract["project_id"],
        "program_id": contract["program_id"],
        "program_version": contract["program_version"],
        "definition_version": contract["definition_version"],
        "cycle_id": contract["cycle_id"],
        "scope_admission_sha256": contract["scope_admission"]["sha256"],
        "scope_definition_sha256": scope_definition_sha256(contract),
        "predecessor_admission_sha256": contract["predecessor_admission_sha256"],
        "trusted_master_public_key_sha256": hashlib.sha256(raw_key).hexdigest(),
    }


def _read_registry_records(directory: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        entries = sorted(directory.iterdir(), key=lambda item: item.name)
    except OSError as error:
        raise ReleaseScopeError(f"trusted admission registry is unreadable: {error}") from error
    for entry in entries:
        match = REGISTRY_FILE.fullmatch(entry.name)
        if match is None:
            raise ReleaseScopeError(
                f"trusted admission registry contains an unexpected entry: {entry.name}"
            )
        if entry.is_symlink():
            raise ReleaseScopeError("trusted admission registry contains a symlink")
        try:
            status = entry.lstat()
            raw = entry.read_bytes()
            value = json.loads(raw)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ReleaseScopeError(
                f"trusted admission registry record is unreadable: {entry.name}"
            ) from error
        if not stat.S_ISREG(status.st_mode) or not isinstance(value, dict):
            raise ReleaseScopeError("trusted admission registry record is not canonical JSON")
        if raw != canonical_bytes(value) + b"\n":
            raise ReleaseScopeError("trusted admission registry record bytes are noncanonical")
        _exact_keys(
            value,
            {
                "schema",
                "project_id",
                "program_id",
                "program_version",
                "definition_version",
                "cycle_id",
                "scope_admission_sha256",
                "scope_definition_sha256",
                "predecessor_admission_sha256",
                "trusted_master_public_key_sha256",
            },
            "trusted admission registry record",
        )
        version = int(match.group(1))
        if (
            value["schema"] != ADMISSION_REGISTRY_SCHEMA
            or isinstance(value["definition_version"], bool)
            or not isinstance(value["definition_version"], int)
            or value["definition_version"] != version
            or isinstance(value["program_version"], bool)
            or not isinstance(value["program_version"], int)
            or value["program_version"] < 1
        ):
            raise ReleaseScopeError("trusted admission registry version binding is invalid")
        for key in ("project_id", "program_id", "cycle_id"):
            _identifier(value[key], f"trusted admission registry record.{key}")
        for key in (
            "scope_admission_sha256",
            "scope_definition_sha256",
            "predecessor_admission_sha256",
            "trusted_master_public_key_sha256",
        ):
            _digest(value[key], f"trusted admission registry record.{key}")
        records.append(value)
    for index, record in enumerate(records, start=1):
        if record["definition_version"] != index:
            raise ReleaseScopeError("trusted admission registry versions are not contiguous")
        expected_predecessor = (
            "0" * 64 if index == 1 else records[index - 2]["scope_admission_sha256"]
        )
        if record["predecessor_admission_sha256"] != expected_predecessor:
            raise ReleaseScopeError("trusted admission registry lineage is broken")
    return records


def _register_admission(
    contract: dict[str, Any],
    artifact_root: Path,
    trusted_master_public_key: Path,
    trusted_admission_registry: Path,
) -> dict[str, Any]:
    root = _root(artifact_root)
    key = _trusted_master_public_key(root, trusted_master_public_key)
    registry = _trusted_admission_registry(root, trusted_admission_registry)
    directory = _registry_program_directory(registry, contract, create=True)
    records = _read_registry_records(directory)
    expected = _admission_registry_record(contract, key)
    identity_keys = {
        "project_id",
        "program_id",
        "program_version",
        "cycle_id",
        "trusted_master_public_key_sha256",
    }
    if any(
        any(record[item] != expected[item] for item in identity_keys)
        for record in records
    ):
        raise ReleaseScopeError("trusted admission registry identity lineage is broken")
    version = contract["definition_version"]
    if version <= len(records):
        if version == len(records) and records[version - 1] == expected:
            return expected
        raise ReleaseScopeError(
            "release scope definition version is already registered with different bytes"
        )
    if version != len(records) + 1:
        raise ReleaseScopeError(
            "release scope definition version must advance exactly one registered predecessor"
        )
    expected_predecessor = (
        "0" * 64 if not records else records[-1]["scope_admission_sha256"]
    )
    if contract["predecessor_admission_sha256"] != expected_predecessor:
        raise ReleaseScopeError(
            "release scope predecessor does not match the trusted admission registry head"
        )
    target = directory / f"definition-{version:08d}.json"
    try:
        force_snapshot._exclusive_write(target, canonical_bytes(expected) + b"\n")
    except force.ForceContractError as error:
        raise ReleaseScopeError(f"release scope admission could not be registered: {error}") from error
    return expected


def _verify_registered_admission(
    contract: dict[str, Any],
    artifact_root: Path,
    trusted_master_public_key: Path,
    trusted_admission_registry: Path,
) -> dict[str, Any]:
    root = _root(artifact_root)
    key = _trusted_master_public_key(root, trusted_master_public_key)
    registry = _trusted_admission_registry(root, trusted_admission_registry)
    directory = _registry_program_directory(registry, contract, create=False)
    records = _read_registry_records(directory)
    version = contract["definition_version"]
    expected = _admission_registry_record(contract, key)
    identity_keys = {
        "project_id",
        "program_id",
        "program_version",
        "cycle_id",
        "trusted_master_public_key_sha256",
    }
    if any(
        any(record[item] != expected[item] for item in identity_keys)
        for record in records
    ):
        raise ReleaseScopeError("trusted admission registry identity lineage is broken")
    if not records or version != len(records) or records[-1] != expected:
        raise ReleaseScopeError(
            "release scope is not the current exact trusted admission"
        )
    return expected


def _verified_file(
    root: Path, item: dict[str, Any], label: str
) -> tuple[Path, bytes]:
    _exact_keys(item, {"path", "sha256"}, label)
    relative = _safe_path(item["path"], f"{label}.path")
    digest = _digest(item["sha256"], f"{label}.sha256")
    current = root
    parts = relative.split("/")
    for index, part in enumerate(parts):
        current = current / part
        try:
            status = current.lstat()
        except OSError as error:
            raise ReleaseScopeError(f"{label} path is missing: {relative}") from error
        if stat.S_ISLNK(status.st_mode):
            raise ReleaseScopeError(f"{label} path contains a symlink: {relative}")
        if index < len(parts) - 1 and not stat.S_ISDIR(status.st_mode):
            raise ReleaseScopeError(f"{label} parent is not a directory: {relative}")
        if index == len(parts) - 1 and not stat.S_ISREG(status.st_mode):
            raise ReleaseScopeError(f"{label} is not a regular file: {relative}")
    try:
        raw = current.read_bytes()
    except OSError as error:
        raise ReleaseScopeError(f"{label} could not be read: {relative}") from error
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ReleaseScopeError(f"{label} digest does not match exact bytes: {relative}")
    return current, raw


def _canonical_json_evidence(
    root: Path, item: dict[str, Any], label: str
) -> dict[str, Any]:
    _, raw = _verified_file(root, item, label)
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseScopeError(f"{label} must be canonical JSON") from error
    if not isinstance(value, dict) or raw != canonical_bytes(value) + b"\n":
        raise ReleaseScopeError(f"{label} must be a canonical JSON object")
    return value


def scope_definition(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        key: contract[key]
        for key in (
            "schema",
            "project_id",
            "program_id",
            "program_version",
            "definition_version",
            "cycle_id",
            "master_task_id",
            "outcome_digest",
            "predecessor_admission_sha256",
            "admission_verification_path",
            "deliverables",
            "policy",
        )
    }


def scope_definition_sha256(contract: dict[str, Any]) -> str:
    return canonical_sha256(scope_definition(contract))


def signature_payload(record: dict[str, Any]) -> bytes:
    try:
        return canonical_bytes(rsa_trust.unsigned_record(record))
    except rsa_trust.TrustError as error:
        raise ReleaseScopeError(str(error)) from error


def _verify_signed_record(
    record: dict[str, Any], public_key_path: Path, label: str
) -> str:
    try:
        return rsa_trust.verify_record(
            record,
            signature_payload(record),
            public_key_path,
            label,
        )
    except rsa_trust.TrustError as error:
        raise ReleaseScopeError(str(error)) from error


def _validate_design_decision(
    contract: dict[str, Any], root: Path, trusted_master_public_key: Path
) -> dict[str, Any]:
    reference = contract["accepted_design_decision"]
    if not isinstance(reference, dict):
        raise ReleaseScopeError("accepted_design_decision must be an evidence reference")
    decision = _canonical_json_evidence(root, reference, "accepted design decision")
    _exact_keys(
        decision,
        {
            "schema",
            "record_version",
            "decision",
            "authority_role",
            "decider_task_id",
            "bindings",
            "authentication",
        },
        "accepted design decision",
    )
    if decision["schema"] != DESIGN_DECISION_SCHEMA or decision["record_version"] != 1:
        raise ReleaseScopeError("accepted design decision schema/version is invalid")
    if decision["decision"] != "accepted" or decision["authority_role"] != "master":
        raise ReleaseScopeError("release scope lacks an accepted master design decision")
    if decision["decider_task_id"] != contract["master_task_id"]:
        raise ReleaseScopeError("release scope design decider does not match master task")
    bindings = decision["bindings"]
    if not isinstance(bindings, dict):
        raise ReleaseScopeError("accepted design decision bindings are invalid")
    _exact_keys(
        bindings,
        {
            "project_id",
            "program_id",
            "program_version",
            "definition_version",
            "cycle_id",
            "outcome_digest",
            "predecessor_admission_sha256",
            "scope_definition_sha256",
        },
        "accepted design decision bindings",
    )
    expected = {
        "project_id": contract["project_id"],
        "program_id": contract["program_id"],
        "program_version": contract["program_version"],
        "definition_version": contract["definition_version"],
        "cycle_id": contract["cycle_id"],
        "outcome_digest": contract["outcome_digest"],
        "predecessor_admission_sha256": contract["predecessor_admission_sha256"],
        "scope_definition_sha256": scope_definition_sha256(contract),
    }
    if bindings != expected:
        raise ReleaseScopeError("accepted design decision does not bind exact pre-dispatch scope")
    _verify_signed_record(decision, trusted_master_public_key, "accepted design decision")
    return decision


def _validate_admission_shape(
    admission: dict[str, Any],
    trusted_master_public_key: Path,
    label: str,
) -> dict[str, Any]:
    _exact_keys(
        admission,
        {
            "schema",
            "record_version",
            "admission_id",
            "decision",
            "bindings",
            "accepted_design_decision",
            "authentication",
        },
        label,
    )
    if admission["schema"] != ADMISSION_SCHEMA or admission["record_version"] != 1:
        raise ReleaseScopeError(f"{label} schema/version is invalid")
    _identifier(admission["admission_id"], f"{label}.admission_id")
    if admission["decision"] != "admitted_pre_dispatch":
        raise ReleaseScopeError(f"{label} is not a pre-dispatch admission")
    bindings = admission["bindings"]
    if not isinstance(bindings, dict):
        raise ReleaseScopeError(f"{label} bindings are invalid")
    _exact_keys(
        bindings,
        {
            "project_id",
            "program_id",
            "program_version",
            "definition_version",
            "cycle_id",
            "master_task_id",
            "outcome_digest",
            "scope_definition_sha256",
            "predecessor_admission_sha256",
            "accepted_design_decision_sha256",
        },
        f"{label} bindings",
    )
    if not isinstance(admission["accepted_design_decision"], dict):
        raise ReleaseScopeError(f"{label} design-decision reference is invalid")
    _exact_keys(
        admission["accepted_design_decision"],
        {"path", "sha256"},
        f"{label}.accepted_design_decision",
    )
    for key in (
        "outcome_digest",
        "scope_definition_sha256",
        "predecessor_admission_sha256",
        "accepted_design_decision_sha256",
    ):
        _digest(bindings[key], f"{label}.bindings.{key}")
    if (
        bindings["accepted_design_decision_sha256"]
        != admission["accepted_design_decision"]["sha256"]
    ):
        raise ReleaseScopeError(
            f"{label} design-decision digest does not match its evidence reference"
        )
    _verify_signed_record(admission, trusted_master_public_key, label)
    return admission


def _validate_predecessor_admission(
    contract: dict[str, Any],
    root: Path,
    trusted_master_public_key: Path,
) -> None:
    reference = contract["predecessor_scope_admission"]
    digest = contract["predecessor_admission_sha256"]
    if contract["definition_version"] == 1:
        if reference is not None or digest != "0" * 64:
            raise ReleaseScopeError(
                "definition version one must not claim a predecessor admission"
            )
        return
    if not isinstance(reference, dict) or reference.get("sha256") != digest:
        raise ReleaseScopeError(
            "scope change requires the exact predecessor admission reference"
        )
    predecessor = _canonical_json_evidence(root, reference, "predecessor scope admission")
    _validate_admission_shape(
        predecessor,
        trusted_master_public_key,
        "predecessor scope admission",
    )
    bindings = predecessor["bindings"]
    expected = {
        "project_id": contract["project_id"],
        "program_id": contract["program_id"],
        "program_version": contract["program_version"],
        "definition_version": contract["definition_version"] - 1,
    }
    if any(bindings.get(key) != value for key, value in expected.items()):
        raise ReleaseScopeError(
            "predecessor admission does not form an exact definition lineage"
        )


def _validate_scope_admission(
    contract: dict[str, Any],
    root: Path,
    trusted_master_public_key: Path,
) -> dict[str, Any]:
    reference = contract["scope_admission"]
    if not isinstance(reference, dict):
        raise ReleaseScopeError("scope_admission must be an evidence reference")
    admission = _canonical_json_evidence(root, reference, "scope admission")
    _validate_admission_shape(admission, trusted_master_public_key, "scope admission")
    expected_bindings = {
        "project_id": contract["project_id"],
        "program_id": contract["program_id"],
        "program_version": contract["program_version"],
        "definition_version": contract["definition_version"],
        "cycle_id": contract["cycle_id"],
        "master_task_id": contract["master_task_id"],
        "outcome_digest": contract["outcome_digest"],
        "scope_definition_sha256": scope_definition_sha256(contract),
        "predecessor_admission_sha256": contract["predecessor_admission_sha256"],
        "accepted_design_decision_sha256": contract["accepted_design_decision"]["sha256"],
    }
    if admission["bindings"] != expected_bindings:
        raise ReleaseScopeError("scope admission does not bind exact pre-dispatch scope")
    if admission["accepted_design_decision"] != contract["accepted_design_decision"]:
        raise ReleaseScopeError("scope admission does not bind the accepted design decision bytes")
    return admission


def _validate_contract_structure(
    value: Any,
    artifact_root: Path,
    trusted_master_public_key: Path,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseScopeError("release scope contract must be an object")
    _exact_keys(
        value,
        {
            "schema",
            "project_id",
            "program_id",
            "program_version",
            "definition_version",
            "cycle_id",
            "master_task_id",
            "outcome_digest",
            "predecessor_admission_sha256",
            "predecessor_scope_admission",
            "admission_verification_path",
            "deliverables",
            "policy",
            "accepted_design_decision",
            "scope_admission",
        },
        "release scope contract",
    )
    if value["schema"] != CONTRACT_SCHEMA:
        raise ReleaseScopeError("release scope contract schema is unsupported")
    for key in ("project_id", "program_id", "cycle_id", "master_task_id"):
        _identifier(value[key], key)
    for key in ("program_version", "definition_version"):
        if isinstance(value[key], bool) or not isinstance(value[key], int) or value[key] < 1:
            raise ReleaseScopeError(f"{key} must be a positive integer")
    _digest(value["outcome_digest"], "outcome_digest")
    _digest(value["predecessor_admission_sha256"], "predecessor_admission_sha256")
    root = _root(artifact_root)
    trusted_master_public_key = _trusted_master_public_key(
        root, trusted_master_public_key
    )
    _safe_path(value["admission_verification_path"], "admission_verification_path")
    policy = value["policy"]
    if not isinstance(policy, dict):
        raise ReleaseScopeError("policy must be an object")
    _exact_keys(
        policy,
        {"required_failure", "optional_failure", "max_optional_recovery_chains"},
        "policy",
    )
    if policy["required_failure"] != "block_release":
        raise ReleaseScopeError("required_failure must be block_release")
    if policy["optional_failure"] != "omit_without_quality_relaxation":
        raise ReleaseScopeError("optional_failure must be omit_without_quality_relaxation")
    if (
        isinstance(policy["max_optional_recovery_chains"], bool)
        or not isinstance(policy["max_optional_recovery_chains"], int)
        or not 0 <= policy["max_optional_recovery_chains"] <= 2
    ):
        raise ReleaseScopeError("max_optional_recovery_chains must be between zero and two")
    deliverables = value["deliverables"]
    if not isinstance(deliverables, list) or not deliverables:
        raise ReleaseScopeError("deliverables must be a non-empty list")
    ids: list[str] = []
    required_count = 0
    for index, item in enumerate(deliverables):
        if not isinstance(item, dict):
            raise ReleaseScopeError(f"deliverables[{index}] must be an object")
        _exact_keys(
            item,
            {
                "deliverable_id",
                "manager_task_id",
                "manager_public_key",
                "manager_charter",
                "criticality",
                "outcome_contribution",
            },
            f"deliverables[{index}]",
        )
        ids.append(_identifier(item["deliverable_id"], f"deliverables[{index}].deliverable_id"))
        _identifier(item["manager_task_id"], f"deliverables[{index}].manager_task_id")
        manager_key = item["manager_public_key"]
        if not isinstance(manager_key, dict):
            raise ReleaseScopeError(f"deliverables[{index}].manager_public_key is invalid")
        manager_key_path, _ = _verified_file(
            root,
            manager_key,
            f"deliverables[{index}].manager_public_key",
        )
        try:
            rsa_trust.read_public_key(
                manager_key_path,
                f"deliverables[{index}].manager_public_key",
            )
        except rsa_trust.TrustError as error:
            raise ReleaseScopeError(str(error)) from error
        manager_charter = item["manager_charter"]
        if not isinstance(manager_charter, dict):
            raise ReleaseScopeError(f"deliverables[{index}].manager_charter is invalid")
        _validate_manager_charter(
            value,
            root,
            manager_charter,
            item["manager_task_id"],
            f"deliverables[{index}].manager_charter",
        )
        if item["criticality"] not in {"required", "optional"}:
            raise ReleaseScopeError(f"deliverables[{index}].criticality is invalid")
        required_count += item["criticality"] == "required"
        if not isinstance(item["outcome_contribution"], str) or not item[
            "outcome_contribution"
        ].strip():
            raise ReleaseScopeError(f"deliverables[{index}].outcome_contribution is empty")
    if len(ids) != len(set(ids)):
        raise ReleaseScopeError("deliverable identifiers must be unique")
    if required_count == 0:
        raise ReleaseScopeError("at least one deliverable must be required")
    _validate_design_decision(value, root, trusted_master_public_key)
    _validate_predecessor_admission(value, root, trusted_master_public_key)
    _validate_scope_admission(value, root, trusted_master_public_key)
    return value


def validate_contract(
    value: Any,
    artifact_root: Path,
    trusted_master_public_key: Path,
    trusted_admission_registry: Path,
) -> dict[str, Any]:
    contract = _validate_contract_structure(
        value,
        artifact_root,
        trusted_master_public_key,
    )
    _verify_registered_admission(
        contract,
        artifact_root,
        trusted_master_public_key,
        trusted_admission_registry,
    )
    return contract


def build_admission_verification(
    contract: dict[str, Any],
    artifact_root: Path,
    trusted_master_public_key: Path,
    trusted_admission_registry: Path,
) -> dict[str, Any]:
    contract = validate_contract(
        contract,
        artifact_root,
        trusted_master_public_key,
        trusted_admission_registry,
    )
    registry_record = _verify_registered_admission(
        contract,
        artifact_root,
        trusted_master_public_key,
        trusted_admission_registry,
    )
    decision = _canonical_json_evidence(
        _root(artifact_root),
        contract["accepted_design_decision"],
        "accepted design decision",
    )
    return {
        "schema": ADMISSION_VERIFICATION_SCHEMA,
        "ok": True,
        "project_id": contract["project_id"],
        "program_id": contract["program_id"],
        "program_version": contract["program_version"],
        "definition_version": contract["definition_version"],
        "cycle_id": contract["cycle_id"],
        "admission_verification_path": contract["admission_verification_path"],
        "scope_definition_sha256": scope_definition_sha256(contract),
        "scope_contract_sha256": canonical_sha256(contract),
        "registry_record_sha256": canonical_sha256(registry_record),
        "scope_admission": contract["scope_admission"],
        "accepted_design_decision": contract["accepted_design_decision"],
        "master_public_key_sha256": decision["authentication"]["public_key_sha256"],
    }


def write_admission_verification(
    contract: dict[str, Any],
    artifact_root: Path,
    trusted_master_public_key: Path,
    trusted_admission_registry: Path,
) -> dict[str, Any]:
    """Materialize the deterministic pre-dispatch gate at its signed path."""
    root = _root(artifact_root)
    contract = _validate_contract_structure(
        contract,
        root,
        trusted_master_public_key,
    )
    _register_admission(
        contract,
        root,
        trusted_master_public_key,
        trusted_admission_registry,
    )
    value = build_admission_verification(
        contract,
        root,
        trusted_master_public_key,
        trusted_admission_registry,
    )
    relative = contract["admission_verification_path"]
    target, existing = force_snapshot._safe_target(root, relative)
    content = canonical_bytes(value) + b"\n"
    if existing is not None and existing != content:
        raise ReleaseScopeError(
            "existing admission verification conflicts with the admitted scope"
        )
    if existing is None:
        try:
            force_snapshot._exclusive_write(target, content)
        except force.ForceContractError as error:
            raise ReleaseScopeError(
                f"admission verification could not be materialized: {error}"
            ) from error
    return {
        **value,
        "evidence": {
            "path": relative,
            "sha256": hashlib.sha256(content).hexdigest(),
        },
    }


def _validate_snapshot_receipt(
    root: Path,
    reference: dict[str, Any],
    force_contract_reference: dict[str, Any],
    expected_terminal: str,
    expected_task_id: str,
    label: str,
) -> dict[str, Any]:
    force_contract_path, _ = _verified_file(
        root,
        force_contract_reference,
        f"{label}.force_contract",
    )
    try:
        force_contract = force.read_contract(force_contract_path)
    except force.ForceContractError as error:
        raise ReleaseScopeError(f"{label} force contract is invalid: {error}") from error
    if force_contract["task_id"] != expected_task_id:
        raise ReleaseScopeError(f"{label} force contract task does not match terminal receipt")
    snapshot = _canonical_json_evidence(root, reference, label)
    _exact_keys(
        snapshot,
        {
            "schema",
            "task_id",
            "contract_sha256",
            "snapshot_path",
            "snapshot_sha256",
            "event_count",
            "terminal",
            "artifact_set_sha256",
        },
        label,
    )
    if snapshot["schema"] != SNAPSHOT_RECEIPT_SCHEMA:
        raise ReleaseScopeError(f"{label} schema is invalid")
    if snapshot["task_id"] != expected_task_id:
        raise ReleaseScopeError(f"{label} task does not match terminal receipt")
    terminal = snapshot["terminal"]
    if not isinstance(terminal, dict):
        raise ReleaseScopeError(f"{label} terminal evidence is invalid")
    _exact_keys(terminal, {"event", "sequence", "at_epoch"}, f"{label} terminal")
    if terminal["event"] != expected_terminal:
        raise ReleaseScopeError(f"{label} terminal decision does not match disposition")
    for key in ("contract_sha256", "snapshot_sha256", "artifact_set_sha256"):
        _digest(snapshot[key], f"{label}.{key}")
    snapshot_path = _safe_path(snapshot["snapshot_path"], f"{label}.snapshot_path")
    _verified_file(
        root,
        {"path": snapshot_path, "sha256": snapshot["snapshot_sha256"]},
        f"{label}.snapshot",
    )
    if (
        isinstance(snapshot["event_count"], bool)
        or not isinstance(snapshot["event_count"], int)
        or snapshot["event_count"] < 1
    ):
        raise ReleaseScopeError(f"{label} event_count is invalid")
    try:
        verification = force_snapshot.verify(
            force_contract_path,
            root,
            snapshot_path,
            reference["path"],
        )
    except force.ForceContractError as error:
        raise ReleaseScopeError(f"{label} sealed force evidence is invalid: {error}") from error
    if verification["terminal_event"] != expected_terminal:
        raise ReleaseScopeError(f"{label} verified terminal decision does not match disposition")
    if expected_terminal == "manager_reject" and not verification[
        "terminal_rejection_inspected"
    ]:
        raise ReleaseScopeError(
            f"{label} rejection lacks verified failed inspection of the terminal candidate"
        )
    return {
        "artifacts": verification["terminal_artifacts"],
        "rework_cycles": verification["rework_cycles"],
    }


def _validate_admission_verification(
    contract: dict[str, Any],
    root: Path,
    reference: dict[str, Any],
    expected: dict[str, Any],
    label: str,
) -> None:
    if reference.get("path") != contract["admission_verification_path"]:
        raise ReleaseScopeError(f"{label} path differs from the pre-dispatch gate")
    value = _canonical_json_evidence(root, reference, label)
    if value != expected:
        raise ReleaseScopeError(f"{label} does not match the pre-dispatch admission gate")


def _validate_manager_charter(
    contract: dict[str, Any],
    root: Path,
    reference: dict[str, Any],
    manager_task_id: str,
    label: str,
) -> None:
    charter = _canonical_json_evidence(root, reference, label)
    if not isinstance(charter, dict) or charter.get("schema") != "company-os.mission-charter.v2":
        raise ReleaseScopeError(f"{label} schema is invalid")
    for key in ("program_version", "definition_version", "outcome_digest"):
        if charter.get(key) != contract[key]:
            raise ReleaseScopeError(f"{label} {key} does not match release scope")
    ids = charter.get("ids")
    expected_ids = {
        "project_id": contract["project_id"],
        "program_id": contract["program_id"],
        "cycle_id": contract["cycle_id"],
        "task_id": manager_task_id,
        "parent_task_id": contract["master_task_id"],
    }
    if not isinstance(ids, dict) or any(ids.get(key) != value for key, value in expected_ids.items()):
        raise ReleaseScopeError(f"{label} identity does not match release manager ownership")
    context = charter.get("task_local_context")
    paths = context.get("artifact_paths") if isinstance(context, dict) else None
    required_paths = {
        contract["scope_admission"]["path"],
        contract["admission_verification_path"],
    }
    if (
        not isinstance(paths, list)
        or any(not isinstance(path, str) for path in paths)
        or not required_paths.issubset(set(paths))
    ):
        raise ReleaseScopeError(
            f"{label} was not dispatched with the pre-dispatch admission evidence"
        )


def _validate_terminal_receipt(
    contract: dict[str, Any],
    root: Path,
    reference: dict[str, Any],
    deliverable_id: str,
    admission_verification: dict[str, Any],
    trusted_master_public_key: Path,
    label: str,
) -> dict[str, Any]:
    receipt = _canonical_json_evidence(root, reference, label)
    _exact_keys(
        receipt,
        {
            "schema",
            "project_id",
            "program_id",
            "program_version",
            "definition_version",
            "cycle_id",
            "deliverable_id",
            "manager_task_id",
            "attempt_chain",
            "force_task_id",
            "rework_cycles",
            "disposition",
            "manager_charter",
            "scope_admission_verification",
            "force_contract",
            "terminal_force_snapshot_receipt",
            "quality_score",
            "quality_gate_lowered",
            "defects",
            "artifact_evidence",
            "authentication",
        },
        label,
    )
    if receipt["schema"] != DELIVERABLE_RECEIPT_SCHEMA:
        raise ReleaseScopeError(f"{label} schema is invalid")
    expected_bindings = {
        "project_id": contract["project_id"],
        "program_id": contract["program_id"],
        "program_version": contract["program_version"],
        "definition_version": contract["definition_version"],
        "cycle_id": contract["cycle_id"],
        "deliverable_id": deliverable_id,
        "manager_task_id": next(
            item["manager_task_id"]
            for item in contract["deliverables"]
            if item["deliverable_id"] == deliverable_id
        ),
    }
    if any(receipt[key] != expected for key, expected in expected_bindings.items()):
        raise ReleaseScopeError(f"{label} does not bind exact release scope")
    definition = next(
        item for item in contract["deliverables"] if item["deliverable_id"] == deliverable_id
    )
    manager_key_path, _ = _verified_file(
        root,
        definition["manager_public_key"],
        f"{label}.manager_public_key",
    )
    _verify_signed_record(receipt, manager_key_path, label)
    admission_reference = receipt["scope_admission_verification"]
    manager_charter_reference = receipt["manager_charter"]
    if not isinstance(admission_reference, dict):
        raise ReleaseScopeError(f"{label} admission verification reference is invalid")
    if not isinstance(manager_charter_reference, dict):
        raise ReleaseScopeError(f"{label} manager charter reference is invalid")
    _validate_admission_verification(
        contract,
        root,
        admission_reference,
        admission_verification,
        f"{label}.scope_admission_verification",
    )
    if manager_charter_reference != definition["manager_charter"]:
        raise ReleaseScopeError(f"{label} manager charter differs from admitted scope")
    _validate_manager_charter(
        contract,
        root,
        manager_charter_reference,
        receipt["manager_task_id"],
        f"{label}.manager_charter",
    )
    _identifier(receipt["force_task_id"], f"{label}.force_task_id")
    for key in ("attempt_chain", "rework_cycles"):
        if isinstance(receipt[key], bool) or not isinstance(receipt[key], int) or receipt[key] < 0:
            raise ReleaseScopeError(f"{label}.{key} is invalid")
    if receipt["attempt_chain"] < 1 or receipt["rework_cycles"] > 3:
        raise ReleaseScopeError(f"{label} attempt/rework bounds are invalid")
    if receipt["disposition"] not in {"accepted", "rejected"}:
        raise ReleaseScopeError(f"{label} disposition is invalid")
    score = receipt["quality_score"]
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
        raise ReleaseScopeError(f"{label} quality_score is invalid")
    if not 0 <= score <= 10:
        raise ReleaseScopeError(f"{label} quality_score must be between zero and ten")
    if receipt["quality_gate_lowered"] is not False:
        raise ReleaseScopeError(f"{label} lowered a quality gate")
    defects = receipt["defects"]
    if not isinstance(defects, list) or any(
        not isinstance(defect, str) or not defect.strip() for defect in defects
    ):
        raise ReleaseScopeError(f"{label} defects are invalid")
    if receipt["disposition"] == "accepted":
        if score < 9 or defects:
            raise ReleaseScopeError(f"{label} accepted below the quality threshold")
        terminal_event = "manager_accept"
    else:
        if score >= 9 or not defects:
            raise ReleaseScopeError(f"{label} rejected receipt must retain failed score and defects")
        terminal_event = "manager_reject"
    force_contract_reference = receipt["force_contract"]
    snapshot_reference = receipt["terminal_force_snapshot_receipt"]
    if not isinstance(force_contract_reference, dict):
        raise ReleaseScopeError(f"{label} force contract reference is invalid")
    if not isinstance(snapshot_reference, dict):
        raise ReleaseScopeError(f"{label} snapshot reference is invalid")
    terminal_force = _validate_snapshot_receipt(
        root,
        snapshot_reference,
        force_contract_reference,
        terminal_event,
        receipt["force_task_id"],
        f"{label}.terminal_force_snapshot_receipt",
    )
    if receipt["rework_cycles"] != terminal_force["rework_cycles"]:
        raise ReleaseScopeError(f"{label} rework count does not match sealed force evidence")
    artifact_evidence = receipt["artifact_evidence"]
    if not isinstance(artifact_evidence, list) or not artifact_evidence:
        raise ReleaseScopeError(f"{label} requires exact artifact evidence")
    seen_paths: set[str] = set()
    for index, artifact in enumerate(artifact_evidence):
        if not isinstance(artifact, dict):
            raise ReleaseScopeError(f"{label}.artifact_evidence[{index}] is invalid")
        _verified_file(root, artifact, f"{label}.artifact_evidence[{index}]")
        path = artifact["path"]
        if path in seen_paths:
            raise ReleaseScopeError(f"{label} repeats artifact evidence path")
        seen_paths.add(path)
    normalized_artifacts = sorted(
        ({"path": item["path"], "sha256": item["sha256"]} for item in artifact_evidence),
        key=lambda item: item["path"],
    )
    if normalized_artifacts != terminal_force["artifacts"]:
        raise ReleaseScopeError(
            f"{label} artifact evidence does not match the terminal force candidate"
        )
    return receipt


def validate_status(
    contract: dict[str, Any],
    value: Any,
    artifact_root: Path,
    trusted_master_public_key: Path,
    trusted_admission_registry: Path,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseScopeError("release status must be an object")
    _exact_keys(
        value,
        {
            "schema",
            "project_id",
            "program_id",
            "program_version",
            "definition_version",
            "cycle_id",
            "scope_contract_sha256",
            "deliverables",
        },
        "release status",
    )
    if value["schema"] != STATUS_SCHEMA:
        raise ReleaseScopeError("release status schema is unsupported")
    for key in (
        "project_id",
        "program_id",
        "program_version",
        "definition_version",
        "cycle_id",
    ):
        if value[key] != contract[key]:
            raise ReleaseScopeError(f"release status {key} does not match scope contract")
    if value["scope_contract_sha256"] != canonical_sha256(contract):
        raise ReleaseScopeError("release status scope digest does not match")
    expected = {item["deliverable_id"]: item for item in contract["deliverables"]}
    statuses = value["deliverables"]
    if not isinstance(statuses, list):
        raise ReleaseScopeError("release status deliverables must be a list")
    actual_ids: list[str] = []
    root = _root(artifact_root)
    admission_verification = build_admission_verification(
        contract,
        root,
        trusted_master_public_key,
        trusted_admission_registry,
    )
    for index, item in enumerate(statuses):
        if not isinstance(item, dict):
            raise ReleaseScopeError(f"status deliverables[{index}] must be an object")
        _exact_keys(
            item,
            {"deliverable_id", "disposition", "attempt_chains", "rework_cycles", "evidence"},
            f"status deliverables[{index}]",
        )
        deliverable_id = _identifier(
            item["deliverable_id"], f"status deliverables[{index}].deliverable_id"
        )
        actual_ids.append(deliverable_id)
        if deliverable_id not in expected:
            raise ReleaseScopeError(f"status contains unknown deliverable: {deliverable_id}")
        if item["disposition"] not in {"accepted", "rejected"}:
            raise ReleaseScopeError("deliverable disposition must be accepted or rejected")
        for key in ("attempt_chains", "rework_cycles"):
            if isinstance(item[key], bool) or not isinstance(item[key], int) or item[key] < 0:
                raise ReleaseScopeError(f"{key} must be a non-negative integer")
        if item["attempt_chains"] < 1:
            raise ReleaseScopeError("attempt_chains must be at least one")
        evidence = item["evidence"]
        if not isinstance(evidence, dict):
            raise ReleaseScopeError("deliverable evidence must be an object")
        _exact_keys(evidence, {"terminal_receipts"}, "deliverable evidence")
        references = evidence["terminal_receipts"]
        if not isinstance(references, list) or len(references) != item["attempt_chains"]:
            raise ReleaseScopeError("terminal receipts must cover every attempt chain")
        receipts: list[dict[str, Any]] = []
        reference_paths: set[str] = set()
        for receipt_index, reference in enumerate(references):
            if not isinstance(reference, dict):
                raise ReleaseScopeError("terminal receipt reference must be an object")
            _exact_keys(reference, {"path", "sha256"}, "terminal receipt reference")
            if reference["path"] in reference_paths:
                raise ReleaseScopeError("terminal receipt references must be unique")
            reference_paths.add(reference["path"])
            receipts.append(
                _validate_terminal_receipt(
                    contract,
                    root,
                    reference,
                    deliverable_id,
                    admission_verification,
                    trusted_master_public_key,
                    f"{deliverable_id}.terminal_receipts[{receipt_index}]",
                )
            )
        chains = [receipt["attempt_chain"] for receipt in receipts]
        if chains != list(range(1, item["attempt_chains"] + 1)):
            raise ReleaseScopeError("terminal receipts must be ordered contiguous attempt chains")
        if sum(receipt["rework_cycles"] for receipt in receipts) != item["rework_cycles"]:
            raise ReleaseScopeError("release status rework count does not match terminal receipts")
        dispositions = [receipt["disposition"] for receipt in receipts]
        if item["disposition"] == "accepted":
            if dispositions[-1] != "accepted" or any(
                disposition != "rejected" for disposition in dispositions[:-1]
            ):
                raise ReleaseScopeError("accepted deliverable attempt history is inconsistent")
        elif any(disposition != "rejected" for disposition in dispositions):
            raise ReleaseScopeError("rejected deliverable attempt history is inconsistent")
        if expected[deliverable_id]["criticality"] == "optional":
            maximum = 1 + contract["policy"]["max_optional_recovery_chains"]
            if item["attempt_chains"] > maximum:
                raise ReleaseScopeError(
                    f"optional deliverable {deliverable_id} exceeded its recovery-chain cap"
                )
            if item["disposition"] == "rejected" and item["attempt_chains"] != maximum:
                raise ReleaseScopeError(
                    f"optional deliverable {deliverable_id} cannot be omitted before recovery cap exhaustion"
                )
    if len(actual_ids) != len(set(actual_ids)):
        raise ReleaseScopeError("release status deliverable identifiers must be unique")
    if set(actual_ids) != set(expected):
        raise ReleaseScopeError(
            f"release status scope differs; extra={sorted(set(actual_ids) - set(expected))!r}, "
            f"missing={sorted(set(expected) - set(actual_ids))!r}"
        )
    return value


def evaluate(contract: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    definitions = {item["deliverable_id"]: item for item in contract["deliverables"]}
    required_rejected: list[str] = []
    optional_rejected: list[str] = []
    accepted: list[str] = []
    for item in status["deliverables"]:
        deliverable_id = item["deliverable_id"]
        if item["disposition"] == "accepted":
            accepted.append(deliverable_id)
        elif definitions[deliverable_id]["criticality"] == "required":
            required_rejected.append(deliverable_id)
        else:
            optional_rejected.append(deliverable_id)
    if required_rejected:
        decision = "release_blocked"
        next_action = "repair_or_reject_required_scope"
    elif optional_rejected:
        decision = "eligible_for_core_acceptance_with_graceful_degradation"
        next_action = "request_authenticated_master_scope_decision"
    else:
        decision = "eligible_for_full_acceptance"
        next_action = "request_authenticated_master_scope_decision"
    return {
        "schema": "company-os.release-scope-evaluation.v1",
        "ok": True,
        "project_id": contract["project_id"],
        "program_id": contract["program_id"],
        "program_version": contract["program_version"],
        "definition_version": contract["definition_version"],
        "cycle_id": contract["cycle_id"],
        "decision": decision,
        "next_action": next_action,
        "accepted_deliverables": sorted(accepted),
        "rejected_required_deliverables": sorted(required_rejected),
        "omitted_optional_deliverables": sorted(optional_rejected),
        "quality_gate_lowered": False,
        "master_acceptance_inferred": False,
        "scope_definition_sha256": scope_definition_sha256(contract),
        "scope_contract_sha256": canonical_sha256(contract),
        "release_status_sha256": canonical_sha256(status),
    }


def _read_json(path: Path, label: str) -> Any:
    if path.is_symlink():
        raise ReleaseScopeError(f"{label} must not be a symlink")
    try:
        status = path.lstat()
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseScopeError(f"{label} could not be read: {error}") from error
    if not stat.S_ISREG(status.st_mode):
        raise ReleaseScopeError(f"{label} must be a regular file")
    return value


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    admit = commands.add_parser("admit")
    evaluate_parser = commands.add_parser("evaluate")
    for command in (admit, evaluate_parser):
        command.add_argument("--contract", type=Path, required=True)
        command.add_argument("--artifact-root", type=Path, required=True)
        command.add_argument("--trusted-master-public-key", type=Path, required=True)
        command.add_argument("--trusted-admission-registry", type=Path, required=True)
    evaluate_parser.add_argument("--status", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        raw_contract = _read_json(args.contract, "release scope contract")
        if args.command == "admit":
            result = write_admission_verification(
                raw_contract,
                args.artifact_root,
                args.trusted_master_public_key,
                args.trusted_admission_registry,
            )
        else:
            contract = validate_contract(
                raw_contract,
                args.artifact_root,
                args.trusted_master_public_key,
                args.trusted_admission_registry,
            )
            status = validate_status(
                contract,
                _read_json(args.status, "release status"),
                args.artifact_root,
                args.trusted_master_public_key,
                args.trusted_admission_registry,
            )
            result = evaluate(contract, status)
    except ReleaseScopeError as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
