#!/usr/bin/env python3
"""Feature-off verifier for canonical Company OS runtime observations.

This module performs no provider calls and writes no files. It verifies one
signed observation and returns a candidate in-memory inbox for the controller
to persist under its lock.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import subprocess
import tempfile
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA = "company-os.runtime-observation.v1"
KEYRING_SCHEMA = "company-os.runtime-gateway-keyring.v1"
MAX_ARTIFACT_BYTES = 1_048_576
MAX_ENVELOPE_TTL = timedelta(minutes=5)
MAX_FUTURE_SKEW = timedelta(seconds=30)
ALLOWED_EVENT_TYPES = {
    "launch",
    "running",
    "heartbeat",
    "cancel_acknowledged",
    "terminal",
}

CLAIM_FIELDS = {
    "schema",
    "gateway_key_id",
    "provider",
    "surface",
    "account",
    "provider_task_id",
    "provider_event_id",
    "event_type",
    "provider_sequence",
    "provider_timestamp",
    "gateway_received_at",
    "payload_sha256",
    "raw_artifact_path",
    "raw_artifact_sha256",
    "project_id",
    "program_version",
    "work_id",
    "cycle_id",
    "attempt_id",
    "parent_runtime_id",
    "role",
    "requested_model",
    "observed_model",
    "fabric_manifest_digest",
    "phase2_contract_digest",
    "nonce",
    "issued_at",
    "expires_at",
}

RAW_ARTIFACT_FIELDS = {
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

EXPECTED_BINDINGS = {
    "project_id",
    "program_version",
    "work_id",
    "cycle_id",
    "attempt_id",
    "parent_runtime_id",
    "role",
    "requested_model",
    "provider",
    "surface",
    "account",
    "fabric_manifest_digest",
    "phase2_contract_digest",
}


class ObservationError(ValueError):
    """A rejected envelope.  Callers must not persist candidate state."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def _reject_constant(value: str) -> None:
    raise ObservationError(f"non-finite JSON number is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ObservationError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def load_json_bytes_strict(value: bytes) -> Any:
    try:
        text = value.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ObservationError(f"invalid JSON artifact: {exc}") from None


def load_json_strict(path: Path) -> Any:
    try:
        value = path.read_bytes()
    except OSError as exc:
        raise ObservationError(f"invalid JSON artifact: {exc}") from None
    return load_json_bytes_strict(value)


def parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ObservationError(f"{field} must be a timezone-aware ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ObservationError(f"{field} must be a timezone-aware ISO-8601 string") from None
    if parsed.tzinfo is None:
        raise ObservationError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def require_trimmed_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ObservationError(f"{field} must be a non-empty trimmed string")
    return value


def require_sha256(value: Any, field: str) -> str:
    text = require_trimmed_string(value, field)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ObservationError(f"{field} must be a lowercase SHA-256 hex digest")
    return text


def resolve_project_artifact(root: Path, relative: Any) -> Path:
    relative_text = require_trimmed_string(relative, "raw_artifact_path")
    candidate_path = Path(relative_text)
    if candidate_path.is_absolute() or "\\" in relative_text:
        raise ObservationError("raw_artifact_path must be a relative project-local path")
    root = root.resolve()
    resolved = (root / candidate_path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ObservationError("raw_artifact_path escapes the artifact root") from None
    if not resolved.is_file():
        raise ObservationError("raw observation artifact does not exist")
    if resolved.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ObservationError("raw observation artifact exceeds the one-megabyte limit")
    return resolved


def load_gateway_key(
    keyring_path: Path,
    key_id: str,
    valid_at: datetime,
    *,
    allow_retired: bool = False,
) -> Path:
    keyring = load_json_strict(keyring_path.resolve())
    if not isinstance(keyring, dict) or set(keyring) != {"schema", "keys"}:
        raise ObservationError("gateway keyring has the wrong shape")
    if keyring.get("schema") != KEYRING_SCHEMA or not isinstance(keyring.get("keys"), list):
        raise ObservationError("gateway keyring schema is unsupported")
    keys: dict[str, dict[str, Any]] = {}
    for item in keyring["keys"]:
        required = {
            "key_id", "algorithm", "public_key_path", "status", "not_before", "not_after"
        }
        if not isinstance(item, dict) or set(item) != required:
            raise ObservationError("gateway keyring entry has the wrong shape")
        item_id = require_trimmed_string(item.get("key_id"), "gateway key ID")
        if item_id in keys:
            raise ObservationError("gateway keyring contains a duplicate key ID")
        keys[item_id] = item
    if key_id not in keys:
        raise ObservationError("observation gateway key ID is unknown")
    selected = keys[key_id]
    allowed_statuses = {"active", "retired"} if allow_retired else {"active"}
    if selected.get("algorithm") != "rsa-sha256" or selected.get("status") not in allowed_statuses:
        raise ObservationError("observation gateway key status or algorithm is not permitted")
    not_before = parse_time(selected.get("not_before"), "gateway key not_before")
    not_after = parse_time(selected.get("not_after"), "gateway key not_after")
    if not_before > valid_at or not_after <= valid_at or not_after <= not_before:
        raise ObservationError("observation gateway key is outside its validity window")
    public_value = require_trimmed_string(selected.get("public_key_path"), "public_key_path")
    public_path = Path(public_value)
    if not public_path.is_absolute():
        public_path = keyring_path.resolve().parent / public_path
    public_path = public_path.resolve()
    if not public_path.is_file():
        raise ObservationError("observation gateway public key does not exist")
    return public_path


def verify_signature(claims: dict[str, Any], signature_value: Any, public_key: Path) -> None:
    signature_text = require_trimmed_string(signature_value, "signature")
    try:
        signature = base64.b64decode(
            signature_text + "=" * (-len(signature_text) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError, TypeError):
        raise ObservationError("observation gateway signature is malformed") from None
    if not signature:
        raise ObservationError("observation gateway signature is empty")
    payload = canonical_json(claims).encode("utf-8")
    try:
        with tempfile.NamedTemporaryFile() as payload_file, tempfile.NamedTemporaryFile() as signature_file:
            payload_file.write(payload)
            payload_file.flush()
            signature_file.write(signature)
            signature_file.flush()
            result = subprocess.run(
                [
                    "openssl",
                    "dgst",
                    "-sha256",
                    "-verify",
                    str(public_key),
                    "-signature",
                    signature_file.name,
                    payload_file.name,
                ],
                capture_output=True,
                check=False,
            )
    except OSError:
        raise ObservationError("OpenSSL verification is unavailable") from None
    if result.returncode != 0:
        raise ObservationError("observation gateway signature is invalid")


def verify_observation(
    envelope: Any,
    *,
    expected_attempt: dict[str, Any],
    keyring_path: Path,
    artifact_root: Path,
    now: datetime | None = None,
    retained_verified_at: datetime | None = None,
) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not isinstance(envelope, dict) or set(envelope) != {"claims", "signature"}:
        raise ObservationError("observation envelope must contain exactly claims and signature")
    claims = envelope.get("claims")
    if not isinstance(claims, dict) or set(claims) != CLAIM_FIELDS:
        raise ObservationError("observation claims have the wrong shape")
    if claims.get("schema") != SCHEMA:
        raise ObservationError("observation schema is unsupported")

    text_fields = CLAIM_FIELDS - {
        "program_version", "provider_sequence", "observed_model"
    }
    for field in text_fields:
        require_trimmed_string(claims.get(field), field)
    if not isinstance(claims.get("program_version"), int) or isinstance(claims["program_version"], bool) or claims["program_version"] < 1:
        raise ObservationError("program_version must be a positive integer")
    if not isinstance(claims.get("provider_sequence"), int) or isinstance(claims["provider_sequence"], bool) or claims["provider_sequence"] < 0:
        raise ObservationError("provider_sequence must be a non-negative integer")
    observed_model = claims.get("observed_model")
    if observed_model is not None:
        require_trimmed_string(observed_model, "observed_model")
    if claims.get("event_type") not in ALLOWED_EVENT_TYPES:
        raise ObservationError("event_type is not supported")
    for field in ("payload_sha256", "raw_artifact_sha256", "fabric_manifest_digest", "phase2_contract_digest"):
        require_sha256(claims.get(field), field)

    issued_at = parse_time(claims.get("issued_at"), "issued_at")
    expires_at = parse_time(claims.get("expires_at"), "expires_at")
    provider_time = parse_time(claims.get("provider_timestamp"), "provider_timestamp")
    gateway_time = parse_time(claims.get("gateway_received_at"), "gateway_received_at")
    verification_time = retained_verified_at or now
    if issued_at > verification_time + MAX_FUTURE_SKEW:
        raise ObservationError("observation issued_at is in the future")
    if expires_at <= verification_time or expires_at <= issued_at:
        raise ObservationError("observation envelope is expired or has an invalid time window")
    if expires_at - issued_at > MAX_ENVELOPE_TTL:
        raise ObservationError("observation envelope TTL exceeds five minutes")
    if provider_time > verification_time + MAX_FUTURE_SKEW or gateway_time > verification_time + MAX_FUTURE_SKEW:
        raise ObservationError("provider or gateway timestamp is in the future")
    if gateway_time < provider_time:
        raise ObservationError("gateway receipt cannot predate the provider event")
    if gateway_time > issued_at + MAX_FUTURE_SKEW:
        raise ObservationError("gateway receipt cannot postdate envelope issuance")
    if issued_at - gateway_time > MAX_ENVELOPE_TTL:
        raise ObservationError("gateway receipt is too old for this envelope")

    if not isinstance(expected_attempt, dict) or expected_attempt.get("status") != "admitted":
        raise ObservationError("observation requires an admitted runtime attempt")
    admitted_at_value = expected_attempt.get("admitted_at")
    if admitted_at_value is not None:
        admitted_at = parse_time(admitted_at_value, "admitted_at")
        if provider_time + MAX_FUTURE_SKEW < admitted_at:
            raise ObservationError("provider observation predates runtime admission")
    missing_expected = EXPECTED_BINDINGS - set(expected_attempt)
    if missing_expected:
        raise ObservationError(f"expected attempt lacks bindings: {sorted(missing_expected)}")
    for field in EXPECTED_BINDINGS:
        if claims.get(field) != expected_attempt.get(field):
            raise ObservationError(f"observation {field} does not match the admitted attempt")
    bound_task = expected_attempt.get("provider_task_id")
    if bound_task is not None and claims.get("provider_task_id") != bound_task:
        raise ObservationError("observation provider_task_id conflicts with the bound task")

    public_key = load_gateway_key(
        keyring_path,
        require_trimmed_string(claims.get("gateway_key_id"), "gateway_key_id"),
        issued_at,
        allow_retired=retained_verified_at is not None,
    )
    verify_signature(claims, envelope.get("signature"), public_key)

    artifact_path = resolve_project_artifact(artifact_root, claims.get("raw_artifact_path"))
    try:
        artifact_bytes = artifact_path.read_bytes()
    except OSError as exc:
        raise ObservationError(f"raw observation artifact could not be read: {exc}") from None
    if len(artifact_bytes) > MAX_ARTIFACT_BYTES:
        raise ObservationError("raw observation artifact exceeds the one-megabyte limit")
    if sha256_bytes(artifact_bytes) != claims.get("raw_artifact_sha256"):
        raise ObservationError("raw observation artifact digest does not match")
    raw = load_json_bytes_strict(artifact_bytes)
    if not isinstance(raw, dict) or set(raw) != RAW_ARTIFACT_FIELDS:
        raise ObservationError("raw observation artifact has the wrong shape")
    raw_claim_map = {
        "provider": "provider",
        "surface": "surface",
        "account": "account",
        "provider_task_id": "provider_task_id",
        "provider_event_id": "provider_event_id",
        "event_type": "event_type",
        "provider_sequence": "provider_sequence",
        "provider_timestamp": "provider_timestamp",
        "observed_model": "observed_model",
    }
    for raw_field, claim_field in raw_claim_map.items():
        if raw.get(raw_field) != claims.get(claim_field):
            raise ObservationError(f"raw artifact {raw_field} does not match signed claims")
    if sha256_json(raw.get("payload")) != claims.get("payload_sha256"):
        raise ObservationError("canonical provider payload digest does not match")

    event_identity = {
        "provider": claims["provider"],
        "account": claims["account"],
        "provider_task_id": claims["provider_task_id"],
        "provider_event_id": claims["provider_event_id"],
    }
    claims_digest = sha256_json(claims)
    return {
        "event_key": sha256_json(event_identity),
        "observation_digest": claims_digest,
        "claims": deepcopy(claims),
        "signature": str(envelope["signature"]),
        "signature_digest": sha256_bytes(str(envelope["signature"]).encode("utf-8")),
        "verified_at": verification_time.isoformat(),
        "trust": "gateway_verified",
    }


def empty_inbox(*, enabled: bool = False) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "status": "enabled" if enabled else "disabled",
        "attempt_binding_digest": None,
        "bound_provider_task_id": None,
        "trusted_observations": [],
        "consumed_nonces": [],
    }


def attempt_binding_digest(expected_attempt: dict[str, Any]) -> str:
    return sha256_json({
        field: expected_attempt.get(field)
        for field in sorted(EXPECTED_BINDINGS | {"provider_task_id", "status"})
    })


def audit_retained_inbox(
    state: dict[str, Any],
    *,
    expected_attempt: dict[str, Any],
    keyring_path: Path,
    artifact_root: Path,
    now: datetime,
) -> None:
    expected_state_fields = {
        "enabled", "status", "attempt_binding_digest", "bound_provider_task_id",
        "trusted_observations", "consumed_nonces"
    }
    if set(state) != expected_state_fields:
        raise ObservationError("observation inbox state has the wrong shape")
    expected_digest = attempt_binding_digest(expected_attempt)
    binding = state.get("attempt_binding_digest")
    observations = state.get("trusted_observations")
    nonces = state.get("consumed_nonces")
    if binding not in {None, expected_digest}:
        raise ObservationError("observation inbox belongs to a different admitted attempt")
    if binding is None and observations:
        raise ObservationError("retained observations lack an attempt binding")
    bound_task = state.get("bound_provider_task_id")
    if bound_task is not None:
        require_trimmed_string(bound_task, "bound_provider_task_id")
    if observations and bound_task is None:
        raise ObservationError("retained observations lack one bound provider task")
    if not observations and bound_task is not None:
        raise ObservationError("provider task is bound without a trusted observation")
    if not isinstance(observations, list) or not isinstance(nonces, list):
        raise ObservationError("observation inbox state is invalid")
    if any(not isinstance(item, dict) for item in observations) or any(
        not isinstance(item, str) or not item for item in nonces
    ):
        raise ObservationError("retained observation inbox state is invalid")

    event_keys: set[str] = set()
    observed_nonces: list[str] = []
    latest_sequence: dict[tuple[str, str, str], int] = {}
    record_fields = {
        "event_key", "observation_digest", "claims", "signature",
        "signature_digest", "verified_at", "trust",
    }
    for item in observations:
        if set(item) != record_fields or item.get("trust") != "gateway_verified":
            raise ObservationError("retained trusted observation has the wrong shape")
        verified_at = parse_time(item.get("verified_at"), "retained observation verified_at")
        if verified_at > now + MAX_FUTURE_SKEW:
            raise ObservationError("retained observation verified_at is in the future")
        rebuilt = verify_observation(
            {"claims": item.get("claims"), "signature": item.get("signature")},
            expected_attempt=expected_attempt,
            keyring_path=keyring_path,
            artifact_root=artifact_root,
            now=now,
            retained_verified_at=verified_at,
        )
        for field in ("event_key", "observation_digest", "signature_digest", "trust"):
            if rebuilt.get(field) != item.get(field):
                raise ObservationError(f"retained observation {field} failed revalidation")
        event_key = str(item["event_key"])
        if event_key in event_keys:
            raise ObservationError("retained observation event keys are not unique")
        event_keys.add(event_key)
        claims = item["claims"]
        if claims.get("provider_task_id") != bound_task:
            raise ObservationError("retained observation binds a different provider task")
        nonce = claims["nonce"]
        if nonce in observed_nonces:
            raise ObservationError("retained observation nonce is duplicated")
        observed_nonces.append(nonce)
        stream = (claims["provider"], claims["account"], claims["provider_task_id"])
        sequence = claims["provider_sequence"]
        if stream in latest_sequence and sequence <= latest_sequence[stream]:
            raise ObservationError("retained provider sequence is not monotonic")
        latest_sequence[stream] = sequence
    if nonces != observed_nonces:
        raise ObservationError("retained consumed nonces do not match trusted observations")


def verify_and_ingest(
    state: dict[str, Any],
    envelope: Any,
    *,
    expected_attempt: dict[str, Any],
    keyring_path: Path,
    artifact_root: Path,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(state, dict):
        raise ObservationError("observation inbox state must be an object")
    if state.get("enabled") is not True or state.get("status") != "enabled":
        raise ObservationError("observation gateway is feature-off")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    audit_retained_inbox(
        state,
        expected_attempt=expected_attempt,
        keyring_path=keyring_path,
        artifact_root=artifact_root,
        now=now,
    )
    observations = state["trusted_observations"]
    nonces = state["consumed_nonces"]

    record = verify_observation(
        envelope,
        expected_attempt=expected_attempt,
        keyring_path=keyring_path,
        artifact_root=artifact_root,
        now=now,
    )
    for existing in observations:
        if existing.get("event_key") == record["event_key"]:
            if existing.get("observation_digest") == record["observation_digest"]:
                return deepcopy(state), {
                    "status": "verified",
                    "idempotent": True,
                    "event_key": record["event_key"],
                }
            raise ObservationError("provider event key conflicts with a different observation digest")

    claims = record["claims"]
    bound_task = state.get("bound_provider_task_id")
    if bound_task is not None and claims["provider_task_id"] != bound_task:
        raise ObservationError("one runtime admission cannot bind multiple provider tasks")
    nonce = claims["nonce"]
    if nonce in nonces:
        raise ObservationError("observation gateway nonce was already consumed")
    stream = (
        claims["provider"],
        claims["account"],
        claims["provider_task_id"],
    )
    stream_sequences = [
        item.get("claims", {}).get("provider_sequence")
        for item in observations
        if (
            item.get("claims", {}).get("provider"),
            item.get("claims", {}).get("account"),
            item.get("claims", {}).get("provider_task_id"),
        ) == stream
    ]
    if stream_sequences and claims["provider_sequence"] <= max(stream_sequences):
        raise ObservationError("provider sequence is duplicate, stale, or reordered")

    candidate = deepcopy(state)
    candidate["attempt_binding_digest"] = attempt_binding_digest(expected_attempt)
    candidate["bound_provider_task_id"] = claims["provider_task_id"]
    candidate["trusted_observations"].append(record)
    candidate["consumed_nonces"].append(nonce)
    return candidate, {
        "status": "verified",
        "idempotent": False,
        "event_key": record["event_key"],
    }
