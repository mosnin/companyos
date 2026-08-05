#!/usr/bin/env python3
"""Provider-neutral, feature-off Company OS runtime gateway contract.

This module builds exact requests for an external protected launcher and
verifies signed gateway results.  It never calls a provider, signs a result,
persists state, enables a feature gate, or owns provider credentials.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import base64
import binascii
from collections.abc import Iterator, Mapping
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REQUEST_SCHEMA = "company-os.runtime-gateway-request.v1"
RESULT_SCHEMA = "company-os.runtime-gateway-result.v1"
RECEIPT_ATTESTATION_SCHEMA = "company-os.runtime-receipt-attestation.v1"
MAX_RESULT_TTL = timedelta(minutes=5)
MAX_FUTURE_SKEW = timedelta(seconds=30)
OPERATIONS = {"launch", "query", "observe", "cancel"}
OPERATION_EVENTS = {
    "launch": {"launch", "launch_unknown", "launch_rejected"},
    "query": {"launch", "launch_unknown", "launch_rejected"},
    "observe": {"running", "heartbeat", "terminal"},
    "cancel": {"cancel_acknowledged", "terminal"},
}
RESULT_FIELDS = {
    "schema",
    "gateway_key_id",
    "request_digest",
    "operation",
    "provider",
    "surface",
    "account",
    "provider_task_id",
    "provider_event_id",
    "event_type",
    "provider_sequence",
    "provider_timestamp",
    "gateway_received_at",
    "observed_model",
    "raw_artifact_path",
    "raw_artifact_sha256",
    "payload_sha256",
    "project_id",
    "program_version",
    "work_id",
    "cycle_id",
    "attempt_id",
    "parent_runtime_id",
    "role",
    "requested_model",
    "fabric_manifest_digest",
    "phase2_contract_digest",
    "nonce",
    "issued_at",
    "expires_at",
}
RECEIPT_ATTESTATION_FIELDS = {
    "schema",
    "gateway_key_id",
    "action",
    "project_id",
    "attempt_id",
    "provider_task_id",
    "receipt_payload_hash",
    "nonce",
    "issued_at",
    "expires_at",
}
RAW_FIELDS = {
    "provider",
    "surface",
    "account",
    "provider_task_id",
    "provider_event_id",
    "event_type",
    "provider_sequence",
    "provider_timestamp",
    "observed_model",
    "payload",
}
IMMUTABLE_ATTEMPT_FIELDS = (
    "attempt_id",
    "project_id",
    "manifest_identity_id",
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
    "program_version",
)


class GatewayError(ValueError):
    """A gateway request or signed result that must fail closed."""


_VERIFICATION_SEAL = object()


class VerifiedGatewayRecord(Mapping[str, Any]):
    """In-memory proof object; ordinary/deserialized dictionaries are rejected."""

    __slots__ = ("_value",)

    def __init__(self, value: dict[str, Any], *, _seal: object) -> None:
        if _seal is not _VERIFICATION_SEAL:
            raise GatewayError("verified gateway records can only be created by cryptographic verification")
        self._value = deepcopy(value)

    def __getitem__(self, key: str) -> Any:
        return self._value[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._value)

    def __len__(self) -> int:
        return len(self._value)

    def retained_record(self) -> dict[str, Any]:
        return deepcopy(self._value)


class VerifiedReceiptAttestation(Mapping[str, Any]):
    """In-memory receipt proof created only after gateway signature verification."""

    __slots__ = ("_value",)

    def __init__(self, value: dict[str, Any], *, _seal: object) -> None:
        if _seal is not _VERIFICATION_SEAL:
            raise GatewayError("verified receipt attestations require cryptographic verification")
        self._value = deepcopy(value)

    def __getitem__(self, key: str) -> Any:
        return self._value[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._value)

    def __len__(self) -> int:
        return len(self._value)

    def retained_record(self) -> dict[str, Any]:
        return deepcopy(self._value)


def observation_module() -> Any:
    module_path = Path(__file__).resolve().with_name("runtime_observations.py")
    spec = importlib.util.spec_from_file_location("company_os_runtime_observations", module_path)
    if spec is None or spec.loader is None:
        raise GatewayError("runtime observation verifier could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise GatewayError(f"{field} must be a non-empty trimmed string")
    return value


def _sha(value: Any, field: str) -> str:
    value = _text(value, field)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise GatewayError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _time(value: Any, field: str) -> datetime:
    value = _text(value, field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise GatewayError(f"{field} must be timezone-aware ISO-8601") from None
    if parsed.tzinfo is None:
        raise GatewayError(f"{field} must be timezone-aware ISO-8601")
    return parsed.astimezone(timezone.utc)


def _forbidden_material(value: Any, *, path: str = "request") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if any(part in str(key).casefold() for part in ("private_key", "credential", "api_key", "secret")):
                raise GatewayError(f"{path} contains forbidden private authority or credentials")
            _forbidden_material(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _forbidden_material(item, path=f"{path}[{index}]")


def validate_vertical_slice_manifest(manifest: Any) -> dict[str, Any]:
    """Apply the stricter first-dogfood envelope after the general validator."""
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return {"valid": False, "errors": ["fabric manifest must be an object"]}
    managers = manifest.get("managers")
    if not isinstance(managers, list) or len(managers) != 1:
        return {"valid": False, "errors": ["first runtime slice requires exactly one manager"]}
    manager = managers[0]
    workers = manager.get("workers") if isinstance(manager, dict) else None
    if not isinstance(workers, list) or len(workers) != 1:
        errors.append("first runtime slice requires exactly one worker")
        workers = []
    if isinstance(manager, dict) and manager.get("model") != "gpt-5.6-sol":
        errors.append("runtime manager must use exact gpt-5.6-sol")
    worker = workers[0] if workers else {}
    if worker.get("model") != "gpt-5.6-luna":
        errors.append("runtime worker must use exact gpt-5.6-luna")
    if manifest.get("external_effects_allowed") is not False:
        errors.append("runtime vertical slice must prohibit external effects")
    if worker.get("write_scope") != []:
        errors.append("first Luna task must be read-only")
    if worker.get("capabilities") != ["emit_artifact", "read_project"]:
        errors.append("first Luna task must use the exact read-only capability set")
    if worker.get("may_delegate", False) is not False:
        errors.append("Luna worker may not delegate")
    if worker.get("external_effects", False) is not False:
        errors.append("Luna worker may not perform external effects")
    if manifest.get("max_managers") != 1 or manifest.get("max_workers_per_manager") != 1 or manifest.get("max_total_workers") != 1:
        errors.append("first runtime slice must cap managers and workers at one")
    return {"valid": not errors, "errors": errors}


def _manifest_identity(manifest: dict[str, Any], attempt: dict[str, Any]) -> dict[str, Any]:
    report = validate_vertical_slice_manifest(manifest)
    if not report["valid"]:
        raise GatewayError("runtime manifest violates the first vertical-slice contract")
    if sha256_json(manifest) != attempt.get("fabric_manifest_digest"):
        raise GatewayError("runtime admission does not bind the exact validated manifest")
    manager = manifest["managers"][0]
    if attempt.get("role") == "manager":
        identity = manager
        if attempt.get("manifest_identity_id") != manager.get("id") or attempt.get("parent_runtime_id") != "master":
            raise GatewayError("manager admission does not bind the exact manifest identity")
    elif attempt.get("role") == "worker":
        identity = manager["workers"][0]
        if attempt.get("manifest_identity_id") != identity.get("id") or attempt.get("parent_runtime_id") == "master":
            raise GatewayError("worker admission does not bind the exact manifest identity and manager parent")
    else:
        raise GatewayError("runtime role is unsupported")
    if attempt.get("requested_model") != identity.get("model"):
        raise GatewayError("runtime admission model differs from the validated manifest")
    if attempt.get("scope") != identity.get("write_scope"):
        raise GatewayError("runtime admission scope differs from the validated manifest")
    if attempt.get("scope_digest") != sha256_json(attempt.get("scope")):
        raise GatewayError("runtime admission scope digest is invalid")
    if attempt.get("budget") != identity.get("budget"):
        raise GatewayError("runtime admission budget differs from the validated manifest")
    budget = attempt.get("budget")
    expected_budget_fields = {"time_minutes", "token_limit", "cost_usd", "max_concurrency", "max_retries"}
    if not isinstance(budget, dict) or set(budget) != expected_budget_fields:
        raise GatewayError("runtime budget has the wrong shape")
    for field in ("token_limit", "max_concurrency", "max_retries"):
        if not isinstance(budget[field], int) or isinstance(budget[field], bool) or budget[field] < 0:
            raise GatewayError(f"runtime budget {field} must be a non-negative integer")
    for field in ("time_minutes", "cost_usd"):
        if (
            not isinstance(budget[field], (int, float))
            or isinstance(budget[field], bool)
            or not math.isfinite(budget[field])
            or budget[field] < 0
        ):
            raise GatewayError(f"runtime budget {field} must be finite and non-negative")
    if budget["max_concurrency"] != 1 or budget["max_retries"] != 0:
        raise GatewayError("first runtime slice requires concurrency one and no retry")
    return identity


def _lifecycle(attempt: dict[str, Any]) -> dict[str, Any]:
    lifecycle = attempt.get("lifecycle") if isinstance(attempt, dict) else None
    if not isinstance(lifecycle, dict):
        raise GatewayError("runtime attempt lacks lifecycle state")
    return lifecycle


def build_request(
    attempt: dict[str, Any],
    *,
    manifest: dict[str, Any],
    operation: str,
    current_lease_fence: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build one immutable command for a protected external gateway."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if operation not in OPERATIONS:
        raise GatewayError("gateway operation is unsupported")
    lifecycle = _lifecycle(attempt)
    status = lifecycle.get("status")
    permitted = {
        "launch": {"admitted"},
        "query": {"launch_unknown", "cancel_requested"},
        "observe": {"launched", "running", "cancel_requested", "cancel_acknowledged"},
        "cancel": {"cancel_requested"},
    }
    if status not in permitted[operation]:
        raise GatewayError(f"gateway {operation} is not valid from {status}")
    if operation == "query" and lifecycle.get("provider_task_id") is not None:
        raise GatewayError("query recovery is only for an unbound launch intent")
    if operation in {"observe", "cancel"} and lifecycle.get("provider_task_id") is None:
        raise GatewayError(f"gateway {operation} requires a bound provider task")
    if any(attempt.get(field) in (None, "") for field in IMMUTABLE_ATTEMPT_FIELDS):
        raise GatewayError("runtime admission is missing immutable launch fields")
    _manifest_identity(manifest, attempt)
    if attempt.get("role") == "manager":
        if attempt.get("requested_model") != "gpt-5.6-sol" or attempt.get("parent_runtime_id") != "master":
            raise GatewayError("manager launch requires exact Sol identity and master parent")
    elif attempt.get("role") == "worker":
        if attempt.get("requested_model") != "gpt-5.6-luna" or attempt.get("parent_runtime_id") == "master":
            raise GatewayError("worker launch requires exact Luna identity and manager parent")
    else:
        raise GatewayError("runtime role is unsupported")
    if attempt.get("capabilities") != ["emit_artifact", "read_project"]:
        raise GatewayError("runtime attempt exceeds the read-only artifact capability set")
    fence = attempt.get("lease_fence") if operation == "launch" else current_lease_fence
    if not isinstance(fence, dict):
        raise GatewayError("runtime operation lacks a current controller lease fence")
    expiry = _time(fence.get("expires_at"), "lease_fence.expires_at")
    if expiry <= now:
        raise GatewayError("runtime admission lease fence is expired")
    if any(fence.get(field) in (None, "") for field in ("lease_id", "generation", "owner", "program_version")):
        raise GatewayError("runtime operation lease fence is incomplete")
    if fence.get("program_version") != attempt.get("program_version"):
        raise GatewayError("runtime operation lease belongs to a different program")
    grant = attempt.get("actor_grant")
    if not isinstance(grant, dict) or not grant.get("token") or not grant.get("grant_digest"):
        raise GatewayError("runtime admission lacks its externally signed grant")
    _sha(grant["grant_digest"], "actor_grant.grant_digest")
    request = {
        "schema": REQUEST_SCHEMA,
        "operation": operation,
        "attempt": {field: deepcopy(attempt[field]) for field in IMMUTABLE_ATTEMPT_FIELDS},
        "provider_task_id": lifecycle.get("provider_task_id"),
        "admission_grant_token": _text(grant["token"], "actor_grant.token"),
        "admission_grant_digest": grant["grant_digest"],
        "lease_fence": deepcopy(fence),
        "external_effects_allowed": False,
    }
    _forbidden_material(request)
    return request | {"request_digest": sha256_json(request)}


def load_envelope(path: Path) -> dict[str, Any]:
    value = observation_module().load_json_strict(path)
    if not isinstance(value, dict):
        raise GatewayError("gateway result envelope must be an object")
    return value


def _project_artifact(root: Path, relative: Any) -> tuple[Path, bytes]:
    try:
        path = observation_module().resolve_project_artifact(root, relative)
        value = path.read_bytes()
    except (OSError, ValueError) as exc:
        raise GatewayError(str(exc)) from None
    return path, value


def verify_result(
    envelope: Any,
    *,
    request: dict[str, Any],
    keyring_path: Path,
    artifact_root: Path,
    now: datetime | None = None,
) -> VerifiedGatewayRecord:
    """Verify one gateway result and return a lifecycle-ready trusted record."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not isinstance(envelope, dict) or set(envelope) != {"claims", "signature"}:
        raise GatewayError("gateway result must contain exactly claims and signature")
    claims = envelope.get("claims")
    if not isinstance(claims, dict) or set(claims) != RESULT_FIELDS or claims.get("schema") != RESULT_SCHEMA:
        raise GatewayError("gateway result claims have the wrong shape")
    if request.get("schema") != REQUEST_SCHEMA or request.get("request_digest") != sha256_json({
        key: value for key, value in request.items() if key != "request_digest"
    }):
        raise GatewayError("gateway request is not canonically bound")
    operation = claims.get("operation")
    if operation != request.get("operation") or claims.get("event_type") not in OPERATION_EVENTS.get(operation, set()):
        raise GatewayError("gateway result event is not permitted for the request")
    if claims.get("request_digest") != request.get("request_digest"):
        raise GatewayError("gateway result does not bind the exact request")
    issued_at = _time(claims.get("issued_at"), "issued_at")
    expires_at = _time(claims.get("expires_at"), "expires_at")
    provider_time = _time(claims.get("provider_timestamp"), "provider_timestamp")
    gateway_time = _time(claims.get("gateway_received_at"), "gateway_received_at")
    if issued_at > now + MAX_FUTURE_SKEW or expires_at <= now or expires_at <= issued_at:
        raise GatewayError("gateway result has an invalid validity window")
    if expires_at - issued_at > MAX_RESULT_TTL:
        raise GatewayError("gateway result TTL exceeds five minutes")
    if provider_time > now + MAX_FUTURE_SKEW or gateway_time < provider_time or gateway_time > issued_at + MAX_FUTURE_SKEW:
        raise GatewayError("gateway/provider timestamps are inconsistent")
    attempt = request["attempt"]
    binding_fields = (
        "project_id",
        "provider",
        "surface",
        "account",
        "program_version",
        "work_id",
        "cycle_id",
        "attempt_id",
        "parent_runtime_id",
        "role",
        "requested_model",
        "fabric_manifest_digest",
        "phase2_contract_digest",
    )
    if any(claims.get(field) != attempt.get(field) for field in binding_fields):
        raise GatewayError("gateway result does not bind the admitted runtime identity")
    task_id = claims.get("provider_task_id")
    if claims["event_type"] in {"launch_unknown", "launch_rejected"}:
        if task_id is not None or claims.get("observed_model") is not None:
            raise GatewayError("pre-task launch outcome cannot invent task or model identity")
    else:
        _text(task_id, "provider_task_id")
        if claims.get("observed_model") != attempt.get("requested_model"):
            raise GatewayError("gateway result does not prove the exact admitted model")
    if request.get("provider_task_id") not in {None, task_id}:
        raise GatewayError("gateway result changes the bound provider task")
    if not isinstance(claims.get("provider_sequence"), int) or isinstance(claims["provider_sequence"], bool) or claims["provider_sequence"] < 0:
        raise GatewayError("provider_sequence must be a non-negative integer")
    for field in ("raw_artifact_sha256", "payload_sha256"):
        _sha(claims.get(field), field)
    public_key = observation_module().load_gateway_key(
        keyring_path,
        _text(claims.get("gateway_key_id"), "gateway_key_id"),
        issued_at,
    )
    try:
        observation_module().verify_signature(claims, envelope.get("signature"), public_key)
    except ValueError as exc:
        raise GatewayError(str(exc)) from None
    _, raw_bytes = _project_artifact(artifact_root, claims.get("raw_artifact_path"))
    if hashlib.sha256(raw_bytes).hexdigest() != claims.get("raw_artifact_sha256"):
        raise GatewayError("gateway raw artifact digest does not match")
    raw = observation_module().load_json_bytes_strict(raw_bytes)
    if not isinstance(raw, dict) or set(raw) != RAW_FIELDS:
        raise GatewayError("gateway raw artifact has the wrong shape")
    for field in RAW_FIELDS - {"payload"}:
        if raw.get(field) != claims.get(field):
            raise GatewayError(f"gateway raw artifact {field} does not match signed claims")
    if sha256_json(raw.get("payload")) != claims.get("payload_sha256"):
        raise GatewayError("gateway provider payload digest does not match")
    if claims["event_type"] == "launch_rejected" and raw["payload"] != {
        "provider_status": "rejected",
        "reason": "model_unavailable",
        "usage": None,
    }:
        raise GatewayError("launch_rejected must prove definitive model unavailability")
    digest = sha256_json(claims)
    value = {
        "observation_digest": digest,
        "claims": deepcopy(claims),
        "signature": envelope["signature"],
        "signature_digest": hashlib.sha256(str(envelope["signature"]).encode("utf-8")).hexdigest(),
        "raw": deepcopy(raw),
        "raw_artifact_b64": base64.b64encode(raw_bytes).decode("ascii"),
        "verified_at": now.isoformat(),
    }
    return VerifiedGatewayRecord(value, _seal=_VERIFICATION_SEAL)


def reverify_retained_record(
    record: Any,
    *,
    keyring_path: Path,
    now: datetime | None = None,
    historical: bool = False,
) -> VerifiedGatewayRecord:
    """Cryptographically replay one retained observation after restart."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expected_fields = {
        "observation_digest", "claims", "signature", "signature_digest",
        "raw", "raw_artifact_b64", "verified_at",
    }
    if not isinstance(record, dict) or set(record) != expected_fields:
        raise GatewayError("retained gateway record has the wrong shape")
    claims = record.get("claims")
    if not isinstance(claims, dict) or set(claims) != RESULT_FIELDS or claims.get("schema") != RESULT_SCHEMA:
        raise GatewayError("retained gateway claims have the wrong shape")
    if record.get("observation_digest") != sha256_json(claims):
        raise GatewayError("retained observation digest does not bind signed claims")
    if record.get("signature_digest") != hashlib.sha256(str(record.get("signature")).encode("utf-8")).hexdigest():
        raise GatewayError("retained signature digest is invalid")
    issued_at = _time(claims.get("issued_at"), "issued_at")
    expires_at = _time(claims.get("expires_at"), "expires_at")
    if expires_at <= issued_at or expires_at - issued_at > MAX_RESULT_TTL:
        raise GatewayError("retained gateway validity window is invalid")
    if not historical and (issued_at > now + MAX_FUTURE_SKEW or expires_at <= now):
        raise GatewayError("retained gateway result is not currently valid")
    operation = claims.get("operation")
    if operation not in OPERATIONS or claims.get("event_type") not in OPERATION_EVENTS[operation]:
        raise GatewayError("retained gateway operation/event binding is invalid")
    public_key = observation_module().load_gateway_key(
        keyring_path,
        _text(claims.get("gateway_key_id"), "gateway_key_id"),
        issued_at,
        allow_retired=historical,
    )
    try:
        observation_module().verify_signature(claims, record.get("signature"), public_key)
    except ValueError as exc:
        raise GatewayError(str(exc)) from None
    try:
        raw_bytes = base64.b64decode(record.get("raw_artifact_b64"), validate=True)
    except (ValueError, TypeError, binascii.Error):
        raise GatewayError("retained raw artifact encoding is invalid") from None
    if hashlib.sha256(raw_bytes).hexdigest() != claims.get("raw_artifact_sha256"):
        raise GatewayError("retained raw artifact digest does not match")
    raw = observation_module().load_json_bytes_strict(raw_bytes)
    if raw != record.get("raw") or not isinstance(raw, dict) or set(raw) != RAW_FIELDS:
        raise GatewayError("retained raw artifact content changed")
    for field in RAW_FIELDS - {"payload"}:
        if raw.get(field) != claims.get(field):
            raise GatewayError(f"retained raw artifact {field} does not match signed claims")
    if sha256_json(raw.get("payload")) != claims.get("payload_sha256"):
        raise GatewayError("retained provider payload digest does not match")
    event = claims.get("event_type")
    if event in {"launch_unknown", "launch_rejected"}:
        if claims.get("provider_task_id") is not None or claims.get("observed_model") is not None:
            raise GatewayError("retained pre-task launch outcome invents task or model identity")
    elif (
        not isinstance(claims.get("provider_task_id"), str)
        or not claims["provider_task_id"]
        or claims.get("observed_model") != claims.get("requested_model")
    ):
        raise GatewayError("retained gateway result lacks exact provider task/model proof")
    if event == "launch_rejected" and raw.get("payload") != {
        "provider_status": "rejected", "reason": "model_unavailable", "usage": None,
    }:
        raise GatewayError("retained launch rejection semantics changed")
    _time(record.get("verified_at"), "verified_at")
    return VerifiedGatewayRecord(record, _seal=_VERIFICATION_SEAL)


def verify_receipt_attestation(
    envelope: Any,
    *,
    attempt: dict[str, Any],
    keyring_path: Path,
    now: datetime | None = None,
) -> VerifiedReceiptAttestation:
    """Verify the gateway signature that binds a receipt to one provider task.

    Receipt content is retained only after this verifier succeeds.  This keeps
    provider attribution separate from an agent-authored ``author`` string.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not isinstance(envelope, dict) or set(envelope) != {"claims", "signature"}:
        raise GatewayError("receipt attestation must contain exactly claims and signature")
    claims = envelope.get("claims")
    if (
        not isinstance(claims, dict)
        or set(claims) != RECEIPT_ATTESTATION_FIELDS
        or claims.get("schema") != RECEIPT_ATTESTATION_SCHEMA
    ):
        raise GatewayError("receipt attestation claims have the wrong shape")
    lifecycle = _lifecycle(attempt)
    provider_task_id = lifecycle.get("provider_task_id")
    if lifecycle.get("status") == "blocked_model_unavailable":
        if provider_task_id is not None:
            raise GatewayError("model-unavailable receipt cannot invent a provider task")
    else:
        provider_task_id = _text(provider_task_id, "provider_task_id")
    expected = {
        "action": "attest-runtime-receipt",
        "project_id": attempt.get("project_id"),
        "attempt_id": attempt.get("attempt_id"),
        "provider_task_id": provider_task_id,
    }
    if any(claims.get(field) != value for field, value in expected.items()):
        raise GatewayError("receipt attestation does not bind the exact runtime task")
    _sha(claims.get("receipt_payload_hash"), "receipt_payload_hash")
    _text(claims.get("nonce"), "nonce")
    issued_at = _time(claims.get("issued_at"), "issued_at")
    expires_at = _time(claims.get("expires_at"), "expires_at")
    if issued_at > now + MAX_FUTURE_SKEW or expires_at <= now or expires_at <= issued_at:
        raise GatewayError("receipt attestation has an invalid validity window")
    if expires_at - issued_at > MAX_RESULT_TTL:
        raise GatewayError("receipt attestation TTL exceeds five minutes")
    public_key = observation_module().load_gateway_key(
        keyring_path,
        _text(claims.get("gateway_key_id"), "gateway_key_id"),
        issued_at,
    )
    try:
        observation_module().verify_signature(claims, envelope.get("signature"), public_key)
    except ValueError as exc:
        raise GatewayError(str(exc)) from None
    value = {
        "attestation_digest": sha256_json(claims),
        "claims": deepcopy(claims),
        "signature": envelope["signature"],
        "signature_digest": hashlib.sha256(str(envelope["signature"]).encode("utf-8")).hexdigest(),
        "verified_at": now.isoformat(),
    }
    return VerifiedReceiptAttestation(value, _seal=_VERIFICATION_SEAL)


def reverify_receipt_attestation(
    record: Any,
    *,
    keyring_path: Path,
    now: datetime | None = None,
    historical: bool = False,
) -> VerifiedReceiptAttestation:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expected_fields = {"attestation_digest", "claims", "signature", "signature_digest", "verified_at"}
    if not isinstance(record, dict) or set(record) != expected_fields:
        raise GatewayError("retained receipt attestation has the wrong shape")
    claims = record.get("claims")
    if (
        not isinstance(claims, dict)
        or set(claims) != RECEIPT_ATTESTATION_FIELDS
        or claims.get("schema") != RECEIPT_ATTESTATION_SCHEMA
    ):
        raise GatewayError("retained receipt attestation claims have the wrong shape")
    if record.get("attestation_digest") != sha256_json(claims):
        raise GatewayError("retained receipt attestation digest is invalid")
    if record.get("signature_digest") != hashlib.sha256(str(record.get("signature")).encode("utf-8")).hexdigest():
        raise GatewayError("retained receipt signature digest is invalid")
    issued_at = _time(claims.get("issued_at"), "issued_at")
    expires_at = _time(claims.get("expires_at"), "expires_at")
    if expires_at <= issued_at or expires_at - issued_at > MAX_RESULT_TTL:
        raise GatewayError("retained receipt attestation validity window is invalid")
    if not historical and (issued_at > now + MAX_FUTURE_SKEW or expires_at <= now):
        raise GatewayError("retained receipt attestation is not currently valid")
    public_key = observation_module().load_gateway_key(
        keyring_path,
        _text(claims.get("gateway_key_id"), "gateway_key_id"),
        issued_at,
        allow_retired=historical,
    )
    try:
        observation_module().verify_signature(claims, record.get("signature"), public_key)
    except ValueError as exc:
        raise GatewayError(str(exc)) from None
    _time(record.get("verified_at"), "verified_at")
    return VerifiedReceiptAttestation(record, _seal=_VERIFICATION_SEAL)
