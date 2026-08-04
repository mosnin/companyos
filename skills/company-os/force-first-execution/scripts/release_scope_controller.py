#!/usr/bin/env python3
"""Evaluate authenticated, predeclared release scope without weakening gates."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import re
import stat
from pathlib import Path
from typing import Any

import force_loop_controller as force
import seal_force_snapshot as force_snapshot


CONTRACT_SCHEMA = "company-os.release-scope.v1"
STATUS_SCHEMA = "company-os.release-status.v1"
DESIGN_DECISION_SCHEMA = "company-os.release-scope-design-decision.v1"
DELIVERABLE_RECEIPT_SCHEMA = "company-os.release-deliverable-receipt.v1"
SNAPSHOT_RECEIPT_SCHEMA = "company-os.force-log-snapshot.v1"
AUTH_SCHEME = "company-os.fixture-hmac-sha256.v1"
AUTH_KEYS = {"company-os-repository-test-v1": b"company-os-public-test-fixture-key-v1"}
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


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
            "deliverables",
            "policy",
        )
    }


def scope_definition_sha256(contract: dict[str, Any]) -> str:
    return canonical_sha256(scope_definition(contract))


def fixture_signature(record: dict[str, Any]) -> str:
    authentication = record.get("authentication")
    if not isinstance(authentication, dict):
        raise ReleaseScopeError("fixture authentication is invalid")
    if authentication.get("scheme") != AUTH_SCHEME:
        raise ReleaseScopeError("fixture authentication scheme is unsupported")
    key_id = authentication.get("key_id")
    key = AUTH_KEYS.get(key_id) if isinstance(key_id, str) else None
    if key is None:
        raise ReleaseScopeError("fixture authentication key is unsupported")
    unsigned = dict(record)
    unsigned["authentication"] = {"scheme": AUTH_SCHEME, "key_id": key_id}
    return hmac.new(key, canonical_sha256(unsigned).encode("ascii"), hashlib.sha256).hexdigest()


def _validate_design_decision(contract: dict[str, Any], root: Path) -> None:
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
        "scope_definition_sha256": scope_definition_sha256(contract),
    }
    if bindings != expected:
        raise ReleaseScopeError("accepted design decision does not bind exact pre-dispatch scope")
    authentication = decision["authentication"]
    if not isinstance(authentication, dict):
        raise ReleaseScopeError("accepted design decision authentication is invalid")
    _exact_keys(authentication, {"scheme", "key_id", "signature"}, "design authentication")
    signature = _digest(authentication["signature"], "design authentication signature")
    if not hmac.compare_digest(signature, fixture_signature(decision)):
        raise ReleaseScopeError("accepted design decision fixture signature does not verify")


def validate_contract(value: Any, artifact_root: Path) -> dict[str, Any]:
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
            "deliverables",
            "policy",
            "accepted_design_decision",
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
                "criticality",
                "outcome_contribution",
            },
            f"deliverables[{index}]",
        )
        ids.append(_identifier(item["deliverable_id"], f"deliverables[{index}].deliverable_id"))
        _identifier(item["manager_task_id"], f"deliverables[{index}].manager_task_id")
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
    root = _root(artifact_root)
    _validate_design_decision(value, root)
    return value


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
    return {
        "artifacts": verification["terminal_artifacts"],
        "rework_cycles": verification["rework_cycles"],
    }


def _validate_terminal_receipt(
    contract: dict[str, Any],
    root: Path,
    reference: dict[str, Any],
    deliverable_id: str,
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
    authentication = receipt["authentication"]
    if not isinstance(authentication, dict):
        raise ReleaseScopeError(f"{label} authentication is invalid")
    _exact_keys(authentication, {"scheme", "key_id", "signature"}, f"{label}.authentication")
    signature = _digest(authentication["signature"], f"{label}.authentication.signature")
    if not hmac.compare_digest(signature, fixture_signature(receipt)):
        raise ReleaseScopeError(f"{label} fixture signature does not verify")
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
    contract: dict[str, Any], value: Any, artifact_root: Path
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
    root.add_argument("--contract", type=Path, required=True)
    root.add_argument("--status", type=Path, required=True)
    root.add_argument("--artifact-root", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        contract = validate_contract(
            _read_json(args.contract, "release scope contract"), args.artifact_root
        )
        status = validate_status(
            contract,
            _read_json(args.status, "release status"),
            args.artifact_root,
        )
        result = evaluate(contract, status)
    except ReleaseScopeError as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
