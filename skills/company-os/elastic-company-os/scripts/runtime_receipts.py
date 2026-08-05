#!/usr/bin/env python3
"""Immutable receipt roots and issuer-bound runtime reconciliation.

This module consumes lifecycle state that has already been advanced from
gateway-verified provider observations.  It never verifies provider facts,
mints authority, performs IO, or persists state.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import base64
import binascii
import subprocess
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RECEIPT_SCHEMA = "company-os.runtime-receipt.v1"
RECONCILIATION_SCHEMA = "company-os.runtime-reconciliation.v1"
RECEIPT_STATUSES = {"complete", "blocked", "failed", "cancelled"}
RECONCILIATION_DECISIONS = {"accepted", "rejected", "cancelled", "blocked"}
TERMINAL_STATES = {
    "succeeded", "failed", "cancelled", "blocked_model_unavailable",
    "cancelled_before_launch",
}


class ReceiptError(ValueError):
    """A receipt or reconciliation that must not be retained."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def gateway_module() -> Any:
    module_path = Path(__file__).resolve().with_name("runtime_gateway.py")
    spec = importlib.util.spec_from_file_location("company_os_runtime_gateway_for_receipts", module_path)
    if spec is None or spec.loader is None:
        raise ReceiptError("runtime gateway verifier could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lifecycle_module() -> Any:
    module_path = Path(__file__).resolve().with_name("runtime_lifecycle.py")
    spec = importlib.util.spec_from_file_location("company_os_runtime_lifecycle_for_receipts", module_path)
    if spec is None or spec.loader is None:
        raise ReceiptError("runtime lifecycle auditor could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReceiptError(f"{field} must be a non-empty trimmed string")
    return value


def _sha(value: Any, field: str) -> str:
    value = _text(value, field)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ReceiptError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _time(value: Any, field: str) -> str:
    value = _text(value, field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ReceiptError(f"{field} must be timezone-aware ISO-8601") from None
    if parsed.tzinfo is None:
        raise ReceiptError(f"{field} must be timezone-aware ISO-8601")
    return parsed.astimezone(timezone.utc).isoformat()


def runtime_identity(attempt: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "attempt_id",
        "project_id",
        "manifest_identity_id",
        "program_version",
        "work_id",
        "cycle_id",
        "parent_runtime_id",
        "role",
        "requested_model",
        "provider",
        "surface",
        "account",
        "scope",
        "scope_digest",
        "budget",
        "capabilities",
        "fabric_manifest_digest",
        "phase2_contract_digest",
        "idempotency_key",
    )
    if not isinstance(attempt, dict) or any(attempt.get(field) in (None, "") for field in fields):
        raise ReceiptError("runtime identity is incomplete")
    return {field: attempt[field] for field in fields}


def runtime_identity_digest(attempt: dict[str, Any]) -> str:
    return sha256_json(runtime_identity(attempt))


def telemetry_digest(lifecycle: dict[str, Any]) -> str:
    telemetry = lifecycle.get("telemetry")
    if (
        lifecycle.get("status") == "cancelled_before_launch"
        or lifecycle.get("terminal_status") == "cancelled_before_launch"
    ) and telemetry is None:
        return sha256_json({
            "cancelled_before_launch": True,
            "terminal_decision_digest": lifecycle.get("terminal_decision_digest"),
        })
    if (
        lifecycle.get("status") == "blocked_model_unavailable"
        or lifecycle.get("terminal_status") == "blocked_model_unavailable"
    ) and telemetry is None:
        return sha256_json({
            "unavailable_reason": "model_unavailable",
            "source_observation_digest": lifecycle.get("terminal_observation_digest"),
        })
    if not isinstance(telemetry, dict):
        raise ReceiptError("receipt requires provider-derived telemetry")
    return sha256_json(telemetry)


def _audit_child_provider_proof(
    child: dict[str, Any],
    *,
    parent_attempt_id: str,
    keyring_path: Path,
) -> str:
    """Return one child receipt digest only after full provider-proof replay."""
    lifecycle = child.get("lifecycle") if isinstance(child, dict) else None
    if (
        not isinstance(lifecycle, dict)
        or child.get("role") != "worker"
        or child.get("requested_model") != "gpt-5.6-luna"
        or child.get("parent_runtime_id") != parent_attempt_id
        or lifecycle.get("status") not in {"receipt_recorded", "reconciled"}
        or lifecycle.get("terminal_status") != "succeeded"
        or lifecycle.get("observed_model") != "gpt-5.6-luna"
    ):
        raise ReceiptError("manager child is not a successful exact receipted Luna runtime")
    retained = lifecycle.get("verified_observations")
    digests = lifecycle.get("observation_digests")
    if not isinstance(retained, list) or not retained or not isinstance(digests, list):
        raise ReceiptError("manager child lacks its signed provider observation set")
    verified_digests: list[str] = []
    for record in retained:
        verified = gateway_module().reverify_retained_record(
            record,
            keyring_path=keyring_path,
            historical=True,
        )
        claims = verified["claims"]
        bindings = {
            "attempt_id": child.get("attempt_id"),
            "project_id": child.get("project_id"),
            "program_version": child.get("program_version"),
            "work_id": child.get("work_id"),
            "cycle_id": child.get("cycle_id"),
            "parent_runtime_id": parent_attempt_id,
            "role": "worker",
            "requested_model": "gpt-5.6-luna",
            "provider": child.get("provider"),
            "surface": child.get("surface"),
            "account": child.get("account"),
            "fabric_manifest_digest": child.get("fabric_manifest_digest"),
            "phase2_contract_digest": child.get("phase2_contract_digest"),
        }
        if any(claims.get(field) != value for field, value in bindings.items()):
            raise ReceiptError("manager child provider proof does not bind its exact runtime identity")
        verified_digests.append(verified["observation_digest"])
    if verified_digests != digests:
        raise ReceiptError("manager child provider observation order changed")
    if (
        lifecycle.get("model_evidence_digest") not in verified_digests
        or lifecycle.get("terminal_observation_digest") not in verified_digests
        or not isinstance(lifecycle.get("provider_task_id"), str)
        or not lifecycle["provider_task_id"]
    ):
        raise ReceiptError("manager child lacks signed model, task, or terminal provider proof")
    terminal_child = deepcopy(child)
    terminal_child["lifecycle"]["status"] = lifecycle["terminal_status"]
    terminal_child["lifecycle"]["receipt"] = None
    terminal_child["lifecycle"]["reconciliation"] = None
    lifecycle_errors = lifecycle_module().audit_attempt(
        terminal_child,
        keyring_path=keyring_path,
    )
    if lifecycle_errors:
        raise ReceiptError(f"manager child lifecycle failed replay: {lifecycle_errors[0]}")
    child_errors = audit_retained_receipt(
        child,
        keyring_path=keyring_path,
        expected_child_attempts=[],
    )
    if child_errors:
        raise ReceiptError(f"manager child receipt failed replay: {child_errors[0]}")
    child_receipt = lifecycle.get("receipt")
    if not isinstance(child_receipt, dict) or child_receipt.get("status") != "complete":
        raise ReceiptError("manager child lacks a complete immutable receipt")
    return _sha(child_receipt.get("receipt_digest"), "child receipt digest")


def _receipt_root_payload(retained: dict[str, Any]) -> dict[str, Any]:
    return {
        "runtime_identity_digest": retained["runtime_identity_digest"],
        "terminal_observation_digest": retained["terminal_observation_digest"],
        "model_evidence_digest": retained["model_evidence_digest"],
        "telemetry_digest": retained["telemetry_digest"],
        "artifact_digests": retained["artifact_digests"],
        "checks": retained["checks"],
        "child_receipt_digests": sorted(retained["child_receipt_digests"]),
        "receipt_digest": retained["receipt_digest"],
    }


def _validate_receipt_payload(
    attempt: dict[str, Any],
    receipt: dict[str, Any],
    *,
    expected_child_attempts: list[dict[str, Any]],
    verified_attestation: Any,
    keyring_path: Path,
    decision_public_key_path: Path | None,
    now: datetime | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    lifecycle = attempt.get("lifecycle") if isinstance(attempt, dict) else None
    if not isinstance(lifecycle, dict) or lifecycle.get("status") not in TERMINAL_STATES:
        raise ReceiptError("receipt requires trusted terminal state")
    if lifecycle.get("status") in {"blocked_model_unavailable", "cancelled_before_launch"}:
        if lifecycle.get("observed_model") is not None or lifecycle.get("model_evidence_digest") is not None:
            raise ReceiptError("pre-task terminal receipt cannot invent model evidence")
    elif lifecycle.get("observed_model") != attempt.get("requested_model"):
        raise ReceiptError("receipt requires verified exact model identity")
    expected_fields = {
        "schema",
        "attempt_id",
        "role",
        "status",
        "runtime_identity_digest",
        "terminal_observation_digest",
        "observed_model",
        "model_evidence_digest",
        "telemetry_digest",
        "artifact_digests",
        "checks",
        "author",
        "attestation_digest",
        "child_receipt_digests",
    }
    if not isinstance(receipt, dict) or set(receipt) != expected_fields:
        raise ReceiptError("runtime receipt has the wrong shape")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise ReceiptError("runtime receipt schema is unsupported")
    if receipt.get("attempt_id") != attempt.get("attempt_id") or receipt.get("role") != attempt.get("role"):
        raise ReceiptError("runtime receipt identity does not bind the attempt")
    if receipt.get("status") not in RECEIPT_STATUSES:
        raise ReceiptError("runtime receipt status is invalid")
    expected_statuses = {
        "succeeded": {"complete"},
        "failed": {"failed", "blocked"},
        "cancelled": {"cancelled"},
        "blocked_model_unavailable": {"blocked"},
        "cancelled_before_launch": {"cancelled"},
    }
    if receipt.get("status") not in expected_statuses[lifecycle["status"]]:
        raise ReceiptError("runtime receipt status contradicts provider terminal state")
    if receipt.get("runtime_identity_digest") != runtime_identity_digest(attempt):
        raise ReceiptError("runtime receipt identity digest is stale")
    if receipt.get("terminal_observation_digest") != lifecycle.get("terminal_observation_digest"):
        raise ReceiptError("runtime receipt does not bind terminal provider evidence")
    if receipt.get("observed_model") != lifecycle.get("observed_model"):
        raise ReceiptError("runtime receipt observed model is stale")
    if receipt.get("model_evidence_digest") != lifecycle.get("model_evidence_digest"):
        raise ReceiptError("runtime receipt does not bind model evidence")
    if receipt.get("telemetry_digest") != telemetry_digest(lifecycle):
        raise ReceiptError("runtime receipt does not bind provider telemetry")
    author = _text(receipt.get("author"), "author")
    cancellation = lifecycle.get("cancellation")
    expected_author = (
        cancellation.get("requested_by")
        if lifecycle.get("status") == "cancelled_before_launch" and isinstance(cancellation, dict)
        else lifecycle.get("provider_task_id") or lifecycle.get("terminal_provider_event_id")
    )
    if author != expected_author:
        raise ReceiptError("runtime receipt author is not the attested provider task")
    attestation_digest = _sha(receipt.get("attestation_digest"), "attestation_digest")
    for field in ("artifact_digests", "checks", "child_receipt_digests"):
        if not isinstance(receipt.get(field), list):
            raise ReceiptError(f"receipt.{field} must be an array")
    if any(
        not isinstance(item, dict) or set(item) != {"path", "sha256"}
        for item in receipt["artifact_digests"]
    ):
        raise ReceiptError("runtime receipt artifact entries must be content-addressed")
    if receipt.get("status") == "complete" and not receipt["artifact_digests"]:
        raise ReceiptError("complete runtime receipt requires a content-addressed artifact")
    for artifact in receipt["artifact_digests"]:
        _text(artifact.get("path"), "artifact.path")
        _sha(artifact.get("sha256"), "artifact.sha256")
    if any(
        not isinstance(item, dict)
        or set(item) != {"name", "status", "evidence"}
        or item.get("status") not in {"passed", "failed"}
        for item in receipt["checks"]
    ):
        raise ReceiptError("runtime receipt check outcomes are invalid")
    if receipt.get("status") == "complete" and not receipt["checks"]:
        raise ReceiptError("complete runtime receipt requires exact check outcomes")
    for check in receipt["checks"]:
        _text(check.get("name"), "check.name")
        _text(check.get("evidence"), "check.evidence")
    if receipt.get("status") == "complete" and any(
        check.get("status") != "passed" for check in receipt["checks"]
    ):
        raise ReceiptError("complete runtime receipt cannot contain failed checks")
    if lifecycle.get("status") == "cancelled_before_launch" and (
        receipt["artifact_digests"]
        or receipt["checks"]
        or receipt["child_receipt_digests"]
    ):
        raise ReceiptError("pre-launch cancellation receipt must use the canonical empty evidence set")
    if receipt.get("status") == "complete" and lifecycle.get("budget_overage") is not None:
        raise ReceiptError("budget-overage runtime cannot produce a complete receipt")
    if not isinstance(expected_child_attempts, list):
        raise ReceiptError("expected child attempts must be an array")
    if attempt.get("role") == "manager":
        if receipt.get("status") == "complete" and len(expected_child_attempts) != 1:
            raise ReceiptError("successful runtime manager receipt requires exactly one Luna child")
        if receipt.get("status") != "complete" and len(expected_child_attempts) > 1:
            raise ReceiptError("non-successful runtime manager receipt has too many children")
        expected_children = sorted(
            _audit_child_provider_proof(
                child,
                parent_attempt_id=attempt.get("attempt_id"),
                keyring_path=keyring_path,
            )
            for child in expected_child_attempts
        )
    else:
        if expected_child_attempts:
            raise ReceiptError("worker receipt cannot receive expected child attempts")
        expected_children = []
    actual_children = sorted(_sha(value, "child_receipt_digest") for value in receipt["child_receipt_digests"])
    if len(actual_children) != len(set(actual_children)) or actual_children != expected_children:
        raise ReceiptError("runtime receipt child set is incomplete, extra, duplicated, or substituted")
    if attempt.get("role") == "worker" and actual_children:
        raise ReceiptError("workers cannot report child receipts")
    if lifecycle.get("status") == "cancelled_before_launch":
        if verified_attestation is not None:
            raise ReceiptError("pre-launch cancellation receipt cannot claim provider attestation")
        if decision_public_key_path is None or not isinstance(cancellation, dict):
            raise ReceiptError("pre-launch cancellation receipt requires the pinned decision issuer key")
        grant = _verify_cancellation_grant(
            attempt,
            cancellation,
            public_key_path=decision_public_key_path,
        )
        if attestation_digest != grant.get("grant_digest"):
            raise ReceiptError("pre-launch cancellation receipt does not bind its decision grant")
        retained_attestation = {
            "authority": "decision_grant",
            "grant_digest": grant["grant_digest"],
            "grant": grant,
        }
    else:
        retained_attestation = None
        if not isinstance(verified_attestation, dict) and callable(getattr(verified_attestation, "retained_record", None)):
            retained_attestation = verified_attestation.retained_record()
        if not isinstance(retained_attestation, dict):
            raise ReceiptError("runtime receipt requires verifier-produced cryptographic attestation")
        try:
            verified = gateway_module().reverify_receipt_attestation(
                retained_attestation,
                keyring_path=keyring_path,
                now=now,
                historical=False,
            )
        except ValueError as exc:
            raise ReceiptError(str(exc)) from None
        retained_attestation = verified.retained_record()
        claims = retained_attestation.get("claims")
        if not isinstance(claims, dict):
            raise ReceiptError("runtime receipt attestation lacks verified claims")
        attested_payload = {key: value for key, value in receipt.items() if key != "attestation_digest"}
        expected_attestation = {
            "action": "attest-runtime-receipt",
            "attempt_id": attempt.get("attempt_id"),
            "provider_task_id": lifecycle.get("provider_task_id"),
            "receipt_payload_hash": sha256_json(attested_payload),
        }
        if any(claims.get(key) != value for key, value in expected_attestation.items()):
            raise ReceiptError("runtime receipt attestation does not bind the exact provider task and content")
        if retained_attestation.get("attestation_digest") != attestation_digest:
            raise ReceiptError("runtime receipt attestation digest does not match verified evidence")
    return deepcopy(receipt), retained_attestation


def record_receipt(
    attempt: dict[str, Any],
    receipt: dict[str, Any],
    *,
    expected_child_attempts: list[dict[str, Any]],
    verified_attestation: Any,
    keyring_path: Path,
    decision_public_key_path: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    candidate = deepcopy(attempt)
    lifecycle = candidate.get("lifecycle")
    if not isinstance(lifecycle, dict):
        raise ReceiptError("runtime lifecycle is missing")
    existing = lifecycle.get("receipt")
    if isinstance(existing, dict):
        accepted_payload = {
            key: value
            for key, value in existing.items()
            if key not in {"receipt_digest", "receipt_root", "attestation_record"}
        }
        if accepted_payload == receipt:
            audit_errors = audit_retained_receipt(
                candidate,
                keyring_path=keyring_path,
                decision_public_key_path=decision_public_key_path,
                expected_child_attempts=expected_child_attempts,
            )
            if audit_errors:
                raise ReceiptError(audit_errors[0])
            return candidate
        raise ReceiptError("runtime receipt is immutable")
    retained, retained_attestation = _validate_receipt_payload(
        candidate,
        receipt,
        expected_child_attempts=expected_child_attempts,
        verified_attestation=verified_attestation,
        keyring_path=keyring_path,
        decision_public_key_path=decision_public_key_path,
        now=now,
    )
    retained["receipt_digest"] = sha256_json(receipt)
    retained["receipt_root"] = sha256_json(_receipt_root_payload(retained))
    retained["attestation_record"] = retained_attestation
    lifecycle["receipt"] = retained
    lifecycle["status"] = "receipt_recorded"
    return candidate


def reconciliation_payload(
    attempt: dict[str, Any],
    *,
    decision: str,
    reviewer: str,
    reconciled_at: str,
) -> dict[str, Any]:
    lifecycle = attempt.get("lifecycle") if isinstance(attempt, dict) else None
    receipt = lifecycle.get("receipt") if isinstance(lifecycle, dict) else None
    if not isinstance(receipt, dict):
        raise ReceiptError("reconciliation requires a complete runtime receipt")
    if decision not in RECONCILIATION_DECISIONS:
        raise ReceiptError("runtime reconciliation decision is invalid")
    terminal_authority = lifecycle.get("terminal_authority")
    terminal_observation_digest = lifecycle.get("terminal_observation_digest")
    terminal_decision_digest = lifecycle.get("terminal_decision_digest")
    if terminal_authority == "provider_observation":
        _sha(terminal_observation_digest, "terminal_observation_digest")
    elif terminal_authority == "decision_grant":
        _sha(terminal_decision_digest, "terminal_decision_digest")
    else:
        raise ReceiptError("reconciliation requires a recognized terminal authority")
    return {
        "schema": RECONCILIATION_SCHEMA,
        "attempt_id": attempt.get("attempt_id"),
        "decision": decision,
        "reviewer": _text(reviewer, "reviewer"),
        "receipt_root": _sha(receipt.get("receipt_root"), "receipt_root"),
        "terminal_authority": terminal_authority,
        "terminal_observation_digest": terminal_observation_digest,
        "terminal_decision_digest": terminal_decision_digest,
        "telemetry_digest": _sha(receipt.get("telemetry_digest"), "telemetry_digest"),
        "reconciled_at": _time(reconciled_at, "reconciled_at"),
    }


def _verify_decision_grant(
    token: Any,
    *,
    public_key_path: Path,
    expected_claims: dict[str, Any],
    now: datetime,
    historical: bool = False,
) -> dict[str, Any]:
    if not isinstance(token, str) or not token:
        raise ReceiptError("reconciliation decision grant is required")
    try:
        encoded, encoded_signature = token.split(".", 1)
        payload_bytes = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        claims = json.loads(payload_bytes.decode("utf-8"))
        signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError, binascii.Error):
        raise ReceiptError("reconciliation decision grant is malformed") from None
    if not isinstance(claims, dict) or any(claims.get(key) != value for key, value in expected_claims.items()):
        raise ReceiptError("reconciliation decision grant does not bind the exact decision")
    _text(claims.get("nonce"), "decision grant nonce")
    expiry = datetime.fromisoformat(_time(claims.get("expiry"), "decision grant expiry"))
    if not historical and expiry <= now.astimezone(timezone.utc):
        raise ReceiptError("reconciliation decision grant is expired")
    try:
        public_key_bytes = public_key_path.resolve().read_bytes()
        with tempfile.NamedTemporaryFile() as payload_file, tempfile.NamedTemporaryFile() as signature_file, tempfile.NamedTemporaryFile() as public_file:
            payload_file.write(encoded.encode("ascii")); payload_file.flush()
            signature_file.write(signature); signature_file.flush()
            public_file.write(public_key_bytes); public_file.flush()
            result = subprocess.run(
                ["openssl", "dgst", "-sha256", "-verify", public_file.name, "-signature", signature_file.name, payload_file.name],
                capture_output=True,
                check=False,
            )
    except (OSError, UnicodeError):
        raise ReceiptError("reconciliation decision grant could not be verified") from None
    if result.returncode != 0:
        raise ReceiptError("reconciliation decision grant signature is invalid")
    public_key_pem = public_key_bytes.decode("utf-8")
    return {
        "token": token,
        "grant_digest": hashlib.sha256(token.encode()).hexdigest(),
        "claims": claims,
        "verification_key_pem": public_key_pem,
        "verification_key_sha256": hashlib.sha256(public_key_bytes).hexdigest(),
    }


def _verify_cancellation_grant(
    attempt: dict[str, Any],
    cancellation: dict[str, Any],
    *,
    public_key_path: Path,
) -> dict[str, Any]:
    request_payload = {
        key: cancellation.get(key)
        for key in (
            "attempt_id", "requested_by", "reason", "requested_at",
            "after_observation_count",
        )
    }
    expected_claims = {
        "actor": cancellation.get("requested_by"),
        "action": "cancel-runtime",
        "resource": f"runtime:{attempt.get('attempt_id')}",
        "project_id": attempt.get("project_id"),
        "program_version": attempt.get("program_version"),
        "work_id": attempt.get("work_id"),
        "cycle_id": attempt.get("cycle_id"),
        "dimension": "runtime-cancellation",
        "decision": "cancelled",
        "payload_hash": sha256_json(request_payload),
    }
    retained_grant = cancellation.get("grant")
    if not isinstance(retained_grant, dict):
        raise ReceiptError("retained cancellation decision grant is missing")
    verified = _verify_decision_grant(
        retained_grant.get("token"),
        public_key_path=public_key_path,
        expected_claims=expected_claims,
        now=datetime.now(timezone.utc),
        historical=True,
    )
    if verified != retained_grant:
        raise ReceiptError("retained cancellation decision grant changed")
    return verified


def reconcile(
    attempt: dict[str, Any],
    *,
    decision: str,
    reviewer: str,
    grant_token: str,
    decision_public_key_path: Path,
    reconciled_at: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    candidate = deepcopy(attempt)
    lifecycle = candidate.get("lifecycle")
    if not isinstance(lifecycle, dict):
        raise ReceiptError("runtime lifecycle is missing")
    normalized_time = _time(reconciled_at, "reconciled_at")
    payload = reconciliation_payload(
        candidate, decision=decision, reviewer=reviewer, reconciled_at=normalized_time
    )
    payload_hash = sha256_json(payload)
    receipt = lifecycle.get("receipt")
    if not isinstance(receipt, dict):
        raise ReceiptError("reconciliation requires a complete runtime receipt")
    if decision == "accepted" and (
        lifecycle.get("terminal_status") != "succeeded"
        or receipt.get("status") != "complete"
        or any(check.get("status") != "passed" for check in receipt.get("checks", []))
    ):
        raise ReceiptError("accepted reconciliation requires successful provider state and passed checks")
    if decision == "cancelled" and (
        lifecycle.get("terminal_status") not in {"cancelled", "cancelled_before_launch"}
        or receipt.get("status") != "cancelled"
    ):
        raise ReceiptError("cancelled reconciliation requires cancelled provider and receipt state")
    if decision == "blocked" and receipt.get("status") != "blocked":
        raise ReceiptError("blocked reconciliation requires a blocked receipt")
    existing = lifecycle.get("reconciliation")
    if existing is not None:
        expected_existing = payload | {"grant": existing.get("grant")}
        expected_existing["reconciliation_digest"] = sha256_json(expected_existing)
        if (
            existing == expected_existing
            and isinstance(existing.get("grant"), dict)
            and existing["grant"].get("token") == grant_token
            and not audit_retained_reconciliation(
                candidate,
                decision_public_key_path=decision_public_key_path,
            )
        ):
            return candidate
        raise ReceiptError("runtime reconciliation is immutable")
    expected_claims = {
        "actor": reviewer,
        "action": "reconcile-runtime",
        "resource": f"runtime:{candidate.get('attempt_id')}",
        "project_id": candidate.get("project_id"),
        "program_version": candidate.get("program_version"),
        "work_id": candidate.get("work_id"),
        "cycle_id": candidate.get("cycle_id"),
        "dimension": "runtime-reconciliation",
        "decision": decision,
        "payload_hash": payload_hash,
    }
    grant = _verify_decision_grant(
        grant_token,
        public_key_path=decision_public_key_path,
        expected_claims=expected_claims,
        now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc),
    )
    value = payload | {
        "grant": grant,
    }
    value["reconciliation_digest"] = sha256_json(value)
    if lifecycle.get("status") != "receipt_recorded":
        raise ReceiptError("reconciliation requires receipt_recorded state")
    lifecycle["reconciliation"] = value
    lifecycle["status"] = "reconciled"
    return candidate


def audit_retained_receipt(
    attempt: dict[str, Any],
    *,
    keyring_path: Path,
    decision_public_key_path: Path | None = None,
    expected_child_attempts: list[dict[str, Any]],
) -> list[str]:
    """Recompute receipt roots and replay receipt attribution after restart."""
    try:
        lifecycle = attempt.get("lifecycle") if isinstance(attempt, dict) else None
        receipt = lifecycle.get("receipt") if isinstance(lifecycle, dict) else None
        if not isinstance(receipt, dict):
            raise ReceiptError("retained runtime receipt is missing")
        base = {
            key: value for key, value in receipt.items()
            if key not in {"receipt_digest", "receipt_root", "attestation_record"}
        }
        if receipt.get("receipt_digest") != sha256_json(base):
            raise ReceiptError("retained runtime receipt digest is invalid")
        if receipt.get("receipt_root") != sha256_json(_receipt_root_payload(receipt)):
            raise ReceiptError("retained runtime receipt root is invalid")
        if receipt.get("runtime_identity_digest") != runtime_identity_digest(attempt):
            raise ReceiptError("retained runtime receipt identity changed")
        if receipt.get("terminal_observation_digest") != lifecycle.get("terminal_observation_digest"):
            raise ReceiptError("retained runtime receipt terminal evidence changed")
        if receipt.get("telemetry_digest") != telemetry_digest(lifecycle):
            raise ReceiptError("retained runtime receipt telemetry changed")
        attestation_record = receipt.get("attestation_record")
        if lifecycle.get("terminal_status") == "cancelled_before_launch":
            if decision_public_key_path is None:
                raise ReceiptError("pre-launch cancellation receipt audit requires the pinned decision issuer key")
            cancellation = lifecycle.get("cancellation")
            if not isinstance(cancellation, dict):
                raise ReceiptError("pre-launch cancellation receipt lost its decision")
            verified_grant = _verify_cancellation_grant(
                attempt,
                cancellation,
                public_key_path=decision_public_key_path,
            )
            expected_attestation = {
                "authority": "decision_grant",
                "grant_digest": verified_grant["grant_digest"],
                "grant": verified_grant,
            }
            expected_base = {
                "schema": RECEIPT_SCHEMA,
                "attempt_id": attempt.get("attempt_id"),
                "role": attempt.get("role"),
                "status": "cancelled",
                "runtime_identity_digest": runtime_identity_digest(attempt),
                "terminal_observation_digest": lifecycle.get("terminal_observation_digest"),
                "observed_model": lifecycle.get("observed_model"),
                "model_evidence_digest": lifecycle.get("model_evidence_digest"),
                "telemetry_digest": telemetry_digest(lifecycle),
                "artifact_digests": [],
                "checks": [],
                "author": cancellation.get("requested_by"),
                "attestation_digest": verified_grant["grant_digest"],
                "child_receipt_digests": [],
            }
            if (
                attestation_record != expected_attestation
                or base.get("attestation_digest") != verified_grant["grant_digest"]
                or base != expected_base
            ):
                raise ReceiptError("retained pre-launch cancellation receipt changed from canonical decision evidence")
        else:
            verified = gateway_module().reverify_receipt_attestation(
                attestation_record,
                keyring_path=keyring_path,
                historical=True,
            )
            claims = verified["claims"]
            if (
                claims.get("attempt_id") != attempt.get("attempt_id")
                or claims.get("provider_task_id") != lifecycle.get("provider_task_id")
                or claims.get("receipt_payload_hash") != sha256_json(
                    {key: value for key, value in base.items() if key != "attestation_digest"}
                )
                or verified["attestation_digest"] != base.get("attestation_digest")
            ):
                raise ReceiptError("retained receipt attestation binding changed")
        if attempt.get("role") == "manager":
            if base.get("status") == "complete" and len(expected_child_attempts) != 1:
                raise ReceiptError("retained successful manager receipt lacks its exact Luna child")
            if base.get("status") != "complete" and len(expected_child_attempts) > 1:
                raise ReceiptError("retained non-successful manager receipt has too many children")
            expected_children = sorted(
                _audit_child_provider_proof(
                    child,
                    parent_attempt_id=attempt.get("attempt_id"),
                    keyring_path=keyring_path,
                )
                for child in expected_child_attempts
            )
            if base.get("child_receipt_digests") != expected_children:
                raise ReceiptError("retained manager child receipt binding changed")
        elif expected_child_attempts or base.get("child_receipt_digests"):
            raise ReceiptError("retained worker receipt cannot have children")
    except (ReceiptError, ValueError) as exc:
        return [str(exc)]
    return []


def audit_retained_reconciliation(
    attempt: dict[str, Any],
    *,
    decision_public_key_path: Path,
) -> list[str]:
    """Recompute the signed master decision and immutable digest after restart."""
    try:
        lifecycle = attempt.get("lifecycle") if isinstance(attempt, dict) else None
        value = lifecycle.get("reconciliation") if isinstance(lifecycle, dict) else None
        if not isinstance(value, dict):
            raise ReceiptError("retained runtime reconciliation is missing")
        digest = value.get("reconciliation_digest")
        if digest != sha256_json({key: item for key, item in value.items() if key != "reconciliation_digest"}):
            raise ReceiptError("retained runtime reconciliation digest is invalid")
        grant = value.get("grant")
        if not isinstance(grant, dict):
            raise ReceiptError("retained runtime reconciliation grant is missing")
        payload = {key: item for key, item in value.items() if key not in {"grant", "reconciliation_digest"}}
        expected_payload = reconciliation_payload(
            attempt,
            decision=payload.get("decision"),
            reviewer=payload.get("reviewer"),
            reconciled_at=payload.get("reconciled_at"),
        )
        if payload != expected_payload:
            raise ReceiptError("retained reconciliation payload changed from runtime state")
        expected_claims = {
            "actor": payload.get("reviewer"),
            "action": "reconcile-runtime",
            "resource": f"runtime:{attempt.get('attempt_id')}",
            "project_id": attempt.get("project_id"),
            "program_version": attempt.get("program_version"),
            "work_id": attempt.get("work_id"),
            "cycle_id": attempt.get("cycle_id"),
            "dimension": "runtime-reconciliation",
            "decision": payload.get("decision"),
            "payload_hash": sha256_json(payload),
        }
        pem = grant.get("verification_key_pem")
        trusted_public = decision_public_key_path.resolve().read_bytes()
        if (
            not isinstance(pem, str)
            or grant.get("verification_key_sha256") != hashlib.sha256(pem.encode()).hexdigest()
            or hashlib.sha256(trusted_public).hexdigest() != grant.get("verification_key_sha256")
        ):
            raise ReceiptError("retained decision verification key changed")
        verified = _verify_decision_grant(
            grant.get("token"),
            public_key_path=decision_public_key_path,
            expected_claims=expected_claims,
            now=datetime.now(timezone.utc),
            historical=True,
        )
        if verified.get("grant_digest") != grant.get("grant_digest"):
            raise ReceiptError("retained decision grant digest changed")
    except (ReceiptError, ValueError, OSError) as exc:
        return [str(exc)]
    return []
