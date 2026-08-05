#!/usr/bin/env python3
"""Pure, fail-closed lifecycle rules for authenticated Company OS runtimes.

The controller owns persistence, leases, decision grants, and artifact IO.  This
module only transforms an already-admitted attempt using gateway-verified
observations or explicit master decisions.  It performs no provider calls and
writes no files.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LIFECYCLE_VERSION = "company-os.runtime-lifecycle.v1"
MODEL_MAPPING_VERSION = "exact-provider-model-v1"
ACTIVE_STATES = {
    "admitted",
    "launch_unknown",
    "launched",
    "running",
    "cancel_requested",
    "cancel_acknowledged",
}
TERMINAL_STATES = {
    "succeeded", "failed", "cancelled", "blocked_model_unavailable",
    "cancelled_before_launch",
}
POST_TERMINAL_STATES = {"receipt_recorded", "reconciled"}
ALL_STATES = ACTIVE_STATES | TERMINAL_STATES | POST_TERMINAL_STATES
OBSERVATION_EVENTS = {
    "launch",
    "launch_unknown",
    "launch_rejected",
    "running",
    "heartbeat",
    "cancel_acknowledged",
    "terminal",
}
RECEIPT_STATUSES = {"complete", "blocked", "failed", "cancelled"}
RECONCILIATION_DECISIONS = {"accepted", "rejected", "cancelled", "blocked"}
USAGE_FIELDS = {
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "total_tokens",
    "cost_usd",
    "currency",
    "semantics",
    "provider_revision",
}


class LifecycleError(ValueError):
    """A transition that must not be persisted."""


def receipt_module() -> Any:
    module_path = Path(__file__).resolve().with_name("runtime_receipts.py")
    spec = importlib.util.spec_from_file_location("company_os_runtime_receipts", module_path)
    if spec is None or spec.loader is None:
        raise LifecycleError("runtime receipt module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def gateway_module() -> Any:
    module_path = Path(__file__).resolve().with_name("runtime_gateway.py")
    spec = importlib.util.spec_from_file_location("company_os_runtime_gateway_for_lifecycle", module_path)
    if spec is None or spec.loader is None:
        raise LifecycleError("runtime gateway verifier could not be loaded")
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


def _trimmed(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise LifecycleError(f"{field} must be a non-empty trimmed string")
    return value


def _sha(value: Any, field: str) -> str:
    value = _trimmed(value, field)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise LifecycleError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _time(value: Any, field: str) -> str:
    text = _trimmed(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise LifecycleError(f"{field} must be timezone-aware ISO-8601") from None
    if parsed.tzinfo is None:
        raise LifecycleError(f"{field} must be timezone-aware ISO-8601")
    return parsed.astimezone(timezone.utc).isoformat()


def _nonnegative_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise LifecycleError(f"{field} must be a non-negative integer")
    return value


def _nonnegative_number(value: Any, field: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0
    ):
        raise LifecycleError(f"{field} must be a finite non-negative number")
    return float(value)


def empty_lifecycle() -> dict[str, Any]:
    return {
        "schema": LIFECYCLE_VERSION,
        "status": "admitted",
        "provider_task_id": None,
        "observed_model": None,
        "model_mapping_version": None,
        "model_evidence_digest": None,
        "observation_digests": [],
        "verified_observations": [],
        "last_provider_sequence": None,
        "last_provider_timestamp": None,
        "last_heartbeat_at": None,
        "terminal_observation_digest": None,
        "terminal_decision_digest": None,
        "terminal_provider_event_id": None,
        "terminal_authority": None,
        "terminal_status": None,
        "cancellation": None,
        "telemetry": None,
        "budget_overage": None,
        "receipt": None,
        "reconciliation": None,
    }


def _require_lifecycle(attempt: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(attempt, dict):
        raise LifecycleError("runtime attempt must be an object")
    lifecycle = attempt.get("lifecycle")
    expected = set(empty_lifecycle())
    if not isinstance(lifecycle, dict) or set(lifecycle) != expected:
        raise LifecycleError("runtime attempt lifecycle has the wrong shape")
    if lifecycle.get("schema") != LIFECYCLE_VERSION or lifecycle.get("status") not in ALL_STATES:
        raise LifecycleError("runtime attempt lifecycle schema or status is invalid")
    return lifecycle


def _verified_record(
    record: Any,
    *,
    keyring_path: Path,
    now: datetime | None,
    historical: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    retained = None
    if not isinstance(record, dict) and callable(getattr(record, "retained_record", None)):
        retained = record.retained_record()
    if not isinstance(retained, dict):
        raise LifecycleError("runtime advancement requires verifier-produced cryptographic evidence")
    try:
        verified = gateway_module().reverify_retained_record(
            retained,
            keyring_path=keyring_path,
            now=now,
            historical=historical,
        )
    except ValueError as exc:
        raise LifecycleError(str(exc)) from None
    retained = verified.retained_record()
    claims = retained.get("claims")
    if not isinstance(claims, dict):
        raise LifecycleError("verified observation lacks claims")
    if claims.get("event_type") not in OBSERVATION_EVENTS:
        raise LifecycleError("verified observation event is unsupported")
    _sha(retained.get("observation_digest"), "observation_digest")
    raw = retained.get("raw")
    if not isinstance(raw, dict) or not isinstance(raw.get("payload"), dict):
        raise LifecycleError("verified observation requires its exact parsed raw artifact")
    return claims, raw["payload"], retained


def _assert_binding(attempt: dict[str, Any], claims: dict[str, Any]) -> None:
    bindings = {
        "attempt_id": "attempt_id",
        "project_id": "project_id",
        "work_id": "work_id",
        "cycle_id": "cycle_id",
        "parent_runtime_id": "parent_runtime_id",
        "role": "role",
        "requested_model": "requested_model",
        "provider": "provider",
        "surface": "surface",
        "account": "account",
        "fabric_manifest_digest": "fabric_manifest_digest",
        "phase2_contract_digest": "phase2_contract_digest",
    }
    for attempt_field, claim_field in bindings.items():
        if attempt.get(attempt_field) != claims.get(claim_field):
            raise LifecycleError(f"verified observation {claim_field} does not bind the attempt")
    if attempt.get("program_version") != claims.get("program_version"):
        raise LifecycleError("verified observation program_version does not bind the attempt")


def _usage(payload: dict[str, Any]) -> dict[str, Any] | None:
    value = payload.get("usage")
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != USAGE_FIELDS:
        raise LifecycleError("provider usage has the wrong shape")
    result = {
        field: _nonnegative_int(value.get(field), f"usage.{field}")
        for field in ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens")
    }
    if result["cached_input_tokens"] > result["input_tokens"]:
        raise LifecycleError("cached input tokens cannot exceed input tokens")
    if result["total_tokens"] != result["input_tokens"] + result["output_tokens"]:
        raise LifecycleError("total tokens must equal input plus output tokens")
    result.update(
        {
            "cost_usd": _nonnegative_number(value.get("cost_usd"), "usage.cost_usd"),
            "currency": _trimmed(value.get("currency"), "usage.currency"),
            "semantics": _trimmed(value.get("semantics"), "usage.semantics"),
            "provider_revision": _trimmed(value.get("provider_revision"), "usage.provider_revision"),
        }
    )
    if result["currency"] != "USD" or result["semantics"] not in {"cumulative", "terminal"}:
        raise LifecycleError("provider usage currency or semantics is unsupported")
    return result


def _merge_usage(
    existing: dict[str, Any] | None,
    current: dict[str, Any],
    *,
    observation_digest: str,
) -> dict[str, Any]:
    value = deepcopy(current)
    value["source_observation_digests"] = [observation_digest]
    value["provider_revisions"] = [current["provider_revision"]]
    if existing is None:
        return value
    if not isinstance(existing, dict):
        raise LifecycleError("retained provider telemetry is invalid")
    revisions = existing.get("provider_revisions")
    sources = existing.get("source_observation_digests")
    if not isinstance(revisions, list) or not isinstance(sources, list):
        raise LifecycleError("retained provider telemetry lacks provenance")
    if current["provider_revision"] in revisions:
        raise LifecycleError("provider telemetry revision cannot be reused")
    for field in ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens", "cost_usd"):
        prior = existing.get(field)
        if not isinstance(prior, (int, float)) or isinstance(prior, bool) or current[field] < prior:
            raise LifecycleError(f"provider telemetry {field} cannot decrease")
    if current["currency"] != existing.get("currency"):
        raise LifecycleError("provider telemetry currency cannot change")
    value["provider_revisions"] = revisions + [current["provider_revision"]]
    value["source_observation_digests"] = sources + [observation_digest]
    return value


def apply_verified_observation(
    attempt: dict[str, Any],
    record: Any,
    *,
    keyring_path: Path,
    now: datetime | None = None,
    historical: bool = False,
) -> dict[str, Any]:
    """Return a candidate attempt after one trusted provider fact."""
    candidate = deepcopy(attempt)
    lifecycle = _require_lifecycle(candidate)
    claims, payload, retained_record = _verified_record(
        record,
        keyring_path=keyring_path,
        now=now,
        historical=historical,
    )
    _assert_binding(candidate, claims)
    digest = retained_record["observation_digest"]
    if digest in lifecycle["observation_digests"]:
        return candidate
    sequence = _nonnegative_int(claims.get("provider_sequence"), "provider_sequence")
    previous_sequence = lifecycle.get("last_provider_sequence")
    if previous_sequence is not None and sequence <= previous_sequence:
        raise LifecycleError("provider sequence cannot regress or repeat")
    provider_time = _time(claims.get("provider_timestamp"), "provider_timestamp")
    previous_provider_time = lifecycle.get("last_provider_timestamp")
    if (
        previous_provider_time is not None
        and datetime.fromisoformat(provider_time)
        < datetime.fromisoformat(_time(previous_provider_time, "last_provider_timestamp"))
    ):
        raise LifecycleError("provider timestamp cannot decrease")
    event = claims["event_type"]
    provider_task_id = claims.get("provider_task_id")
    if event in {"launch_unknown", "launch_rejected"}:
        if provider_task_id is not None:
            _trimmed(provider_task_id, "provider_task_id")
    else:
        provider_task_id = _trimmed(provider_task_id, "provider_task_id")
    bound_task = lifecycle.get("provider_task_id")
    if bound_task is not None and provider_task_id is not None and provider_task_id != bound_task:
        raise LifecycleError("one runtime attempt cannot bind multiple provider tasks")

    status = lifecycle["status"]
    observed_model = claims.get("observed_model")
    if event not in {"launch_unknown", "launch_rejected"}:
        observed_model = _trimmed(observed_model, "observed_model")
        if observed_model != candidate.get("requested_model"):
            raise LifecycleError("provider-observed model does not exactly match the admitted model")
    if status in TERMINAL_STATES | POST_TERMINAL_STATES:
        raise LifecycleError("provider terminal state is immutable")
    current_usage = _usage(payload)
    if current_usage is not None:
        expected_semantics = "terminal" if event == "terminal" else "cumulative"
        if current_usage["semantics"] != expected_semantics:
            raise LifecycleError(f"{event} observation requires {expected_semantics} usage semantics")

    next_status = status
    if event == "launch_unknown":
        if status not in {"admitted", "launch_unknown", "cancel_requested"}:
            raise LifecycleError("launch_unknown is invalid after a provider task is bound")
        next_status = "cancel_requested" if lifecycle.get("cancellation") is not None else "launch_unknown"
    elif event == "launch_rejected":
        if status not in {"admitted", "launch_unknown", "cancel_requested"}:
            raise LifecycleError("launch_rejected is valid only before a provider task is bound")
        if payload != {
            "provider_status": "rejected",
            "reason": "model_unavailable",
            "usage": None,
        }:
            raise LifecycleError("launch rejection does not prove model unavailability")
        terminal = "cancelled_before_launch" if lifecycle.get("cancellation") is not None else "blocked_model_unavailable"
        lifecycle["terminal_status"] = terminal
        lifecycle["terminal_observation_digest"] = digest
        lifecycle["terminal_provider_event_id"] = claims.get("provider_event_id")
        lifecycle["terminal_authority"] = "provider_observation"
        next_status = terminal
    elif event == "launch":
        if status not in {"admitted", "launch_unknown", "cancel_requested"}:
            raise LifecycleError("launch is valid only from admitted or launch_unknown")
        next_status = "cancel_requested" if lifecycle.get("cancellation") is not None else "launched"
    elif event in {"running", "heartbeat"}:
        if status not in {"launched", "running", "cancel_requested", "cancel_acknowledged"}:
            raise LifecycleError("running evidence requires a launched attempt")
        next_status = status if status in {"cancel_requested", "cancel_acknowledged"} else "running"
        lifecycle["last_heartbeat_at"] = provider_time
    elif event == "cancel_acknowledged":
        if status != "cancel_requested":
            raise LifecycleError("cancellation acknowledgement requires an authoritative request")
        next_status = "cancel_acknowledged"
    elif event == "terminal":
        terminal = payload.get("status")
        if terminal not in {"succeeded", "failed", "cancelled"}:
            raise LifecycleError("terminal observation must declare succeeded, failed, or cancelled")
        if lifecycle.get("cancellation") is not None:
            terminal = "cancelled"
        elif status not in {"launched", "running"}:
            raise LifecycleError("terminal evidence requires launched or running state")
        if current_usage is None:
            raise LifecycleError("terminal observation requires provider-derived usage")
        lifecycle["terminal_status"] = terminal
        lifecycle["terminal_observation_digest"] = digest
        lifecycle["terminal_provider_event_id"] = claims.get("provider_event_id")
        lifecycle["terminal_authority"] = "provider_observation"
        next_status = terminal

    if provider_task_id is not None:
        lifecycle["provider_task_id"] = provider_task_id
    if observed_model is not None:
        lifecycle["observed_model"] = observed_model
        lifecycle["model_mapping_version"] = MODEL_MAPPING_VERSION
        if lifecycle.get("model_evidence_digest") is None:
            lifecycle["model_evidence_digest"] = digest
    if current_usage is not None:
        lifecycle["telemetry"] = _merge_usage(
            lifecycle.get("telemetry"),
            current_usage,
            observation_digest=digest,
        )
    budget = candidate.get("budget")
    if not isinstance(budget, dict):
        raise LifecycleError("runtime attempt lacks its admitted budget")
    overages: dict[str, dict[str, float]] = {}
    telemetry = lifecycle.get("telemetry")
    if telemetry is not None:
        if telemetry["total_tokens"] > budget.get("token_limit", -1):
            overages["total_tokens"] = {
                "actual": float(telemetry["total_tokens"]),
                "limit": float(budget.get("token_limit", -1)),
            }
        if telemetry["cost_usd"] > budget.get("cost_usd", -1):
            overages["cost_usd"] = {
                "actual": float(telemetry["cost_usd"]),
                "limit": float(budget.get("cost_usd", -1)),
            }
    retained = lifecycle.get("verified_observations")
    first_time = (
        _time(
            retained[0].get("claims", {}).get("provider_timestamp"),
            "first_provider_timestamp",
        )
        if retained
        else provider_time
    )
    elapsed_minutes = max(
        0.0,
        (
            datetime.fromisoformat(provider_time)
            - datetime.fromisoformat(first_time)
        ).total_seconds()
        / 60.0,
    )
    time_limit = _nonnegative_number(budget.get("time_minutes"), "budget.time_minutes")
    if elapsed_minutes > time_limit:
        overages["time_minutes"] = {
            "actual": elapsed_minutes,
            "limit": time_limit,
        }
    lifecycle["budget_overage"] = overages or None
    lifecycle["status"] = next_status
    lifecycle["observation_digests"].append(digest)
    lifecycle["verified_observations"].append(retained_record)
    lifecycle["last_provider_sequence"] = sequence
    lifecycle["last_provider_timestamp"] = provider_time
    return candidate


def request_cancellation(
    attempt: dict[str, Any],
    *,
    requested_by: str,
    reason: str,
    grant_token: str,
    decision_public_key_path: Path,
    requested_at: str,
    now: datetime | None = None,
    historical: bool = False,
) -> dict[str, Any]:
    candidate = deepcopy(attempt)
    lifecycle = _require_lifecycle(candidate)
    if (
        lifecycle["status"] in TERMINAL_STATES | POST_TERMINAL_STATES
        and lifecycle.get("cancellation") is None
    ):
        raise LifecycleError("terminal runtime cannot be cancelled")
    existing = lifecycle.get("cancellation")
    normalized_time = _time(requested_at, "requested_at")
    request_payload = {
        "attempt_id": candidate.get("attempt_id"),
        "requested_by": _trimmed(requested_by, "requested_by"),
        "reason": _trimmed(reason, "reason"),
        "requested_at": normalized_time,
        "after_observation_count": (
            existing.get("after_observation_count")
            if isinstance(existing, dict)
            else len(lifecycle.get("verified_observations", []))
        ),
    }
    expected_claims = {
        "actor": requested_by,
        "action": "cancel-runtime",
        "resource": f"runtime:{candidate.get('attempt_id')}",
        "project_id": candidate.get("project_id"),
        "program_version": candidate.get("program_version"),
        "work_id": candidate.get("work_id"),
        "cycle_id": candidate.get("cycle_id"),
        "dimension": "runtime-cancellation",
        "decision": "cancelled",
        "payload_hash": sha256_json(request_payload),
    }
    try:
        grant = receipt_module()._verify_decision_grant(
            grant_token,
            public_key_path=decision_public_key_path,
            expected_claims=expected_claims,
            now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc),
            historical=historical or existing is not None,
        )
    except ValueError as exc:
        raise LifecycleError(str(exc)) from None
    request = {
        **request_payload,
        "grant": grant,
    }
    if existing is not None:
        if existing == request:
            return candidate
        raise LifecycleError("runtime cancellation is irreversible and already bound")
    lifecycle["cancellation"] = request
    if lifecycle["status"] == "admitted":
        lifecycle["status"] = "cancelled_before_launch"
        lifecycle["terminal_status"] = "cancelled_before_launch"
        lifecycle["terminal_authority"] = "decision_grant"
        lifecycle["terminal_decision_digest"] = grant["grant_digest"]
    else:
        lifecycle["status"] = "cancel_requested"
    return candidate


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
    try:
        return receipt_module().record_receipt(
            attempt,
            receipt,
            expected_child_attempts=expected_child_attempts,
            verified_attestation=verified_attestation,
            keyring_path=keyring_path,
            decision_public_key_path=decision_public_key_path,
            now=now,
        )
    except ValueError as exc:
        raise LifecycleError(str(exc)) from None


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
    try:
        return receipt_module().reconcile(
            attempt,
            decision=decision,
            reviewer=reviewer,
            grant_token=grant_token,
            decision_public_key_path=decision_public_key_path,
            reconciled_at=reconciled_at,
            now=now,
        )
    except ValueError as exc:
        raise LifecycleError(str(exc)) from None


def audit_attempt(
    attempt: dict[str, Any],
    *,
    keyring_path: Path,
    decision_public_key_path: Path | None = None,
    expected_child_attempts: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Replay all signed authority and reject any retained-state divergence."""
    try:
        current = _require_lifecycle(attempt)
        status = current["status"]
        retained = current.get("verified_observations")
        if not isinstance(retained, list) or len(retained) != len(current.get("observation_digests", [])):
            raise LifecycleError("runtime retained observation set is incomplete")

        cancellation = current.get("cancellation")
        cancellation_index = -1
        if cancellation is not None:
            if decision_public_key_path is None:
                raise LifecycleError("cancelled runtime audit requires the pinned decision issuer key")
            expected_fields = {
                "attempt_id", "requested_by", "reason", "requested_at",
                "after_observation_count", "grant",
            }
            if not isinstance(cancellation, dict) or set(cancellation) != expected_fields:
                raise LifecycleError("retained cancellation has the wrong shape")
            cancellation_index = _nonnegative_int(
                cancellation.get("after_observation_count"),
                "cancellation.after_observation_count",
            )
            if cancellation_index > len(retained):
                raise LifecycleError("retained cancellation observation boundary is invalid")
            grant = cancellation.get("grant")
            if not isinstance(grant, dict) or not isinstance(grant.get("token"), str):
                raise LifecycleError("retained cancellation lacks its signed decision grant")

        replay = deepcopy(attempt)
        replay["lifecycle"] = empty_lifecycle()
        verified_digests: list[str] = []
        for index, record in enumerate(retained):
            if cancellation is not None and cancellation_index == index:
                replay = request_cancellation(
                    replay,
                    requested_by=cancellation["requested_by"],
                    reason=cancellation["reason"],
                    grant_token=cancellation["grant"]["token"],
                    decision_public_key_path=decision_public_key_path,
                    requested_at=cancellation["requested_at"],
                    historical=True,
                )
            try:
                verified = gateway_module().reverify_retained_record(
                    record,
                    keyring_path=keyring_path,
                    historical=True,
                )
            except ValueError as exc:
                raise LifecycleError(str(exc)) from None
            _assert_binding(attempt, verified["claims"])
            verified_digests.append(verified["observation_digest"])
            replay = apply_verified_observation(
                replay,
                verified,
                keyring_path=keyring_path,
                historical=True,
            )
        if cancellation is not None and cancellation_index == len(retained):
            replay = request_cancellation(
                replay,
                requested_by=cancellation["requested_by"],
                reason=cancellation["reason"],
                grant_token=cancellation["grant"]["token"],
                decision_public_key_path=decision_public_key_path,
                requested_at=cancellation["requested_at"],
                historical=True,
            )

        if verified_digests != current.get("observation_digests"):
            raise LifecycleError("runtime observation digest order changed")
        derived_fields = set(empty_lifecycle()) - {"schema", "status", "receipt", "reconciliation"}
        replay_lifecycle = replay["lifecycle"]
        for field in sorted(derived_fields):
            if current.get(field) != replay_lifecycle.get(field):
                raise LifecycleError(f"retained runtime {field} differs from deterministic replay")
        expected_status = current.get("terminal_status") if status in POST_TERMINAL_STATES else status
        if replay_lifecycle.get("status") != expected_status:
            raise LifecycleError("retained runtime status differs from deterministic replay")
        if status != "admitted" and not current["observation_digests"] and cancellation is None:
            raise LifecycleError("advanced runtime lifecycle lacks trusted evidence or cancellation authority")

        if status in TERMINAL_STATES | POST_TERMINAL_STATES:
            if current.get("terminal_status") not in TERMINAL_STATES:
                raise LifecycleError("terminal runtime lacks a terminal status")
            if current.get("terminal_authority") == "provider_observation":
                _sha(current.get("terminal_observation_digest"), "terminal_observation_digest")
                if current.get("terminal_observation_digest") not in verified_digests:
                    raise LifecycleError("terminal runtime evidence is not in the signed observation set")
            elif current.get("terminal_authority") == "decision_grant":
                grant = current.get("cancellation", {}).get("grant", {})
                if current.get("terminal_decision_digest") != grant.get("grant_digest"):
                    raise LifecycleError("terminal cancellation does not bind its signed decision grant")
                if current.get("terminal_observation_digest") is not None:
                    raise LifecycleError("decision-terminal runtime cannot invent provider terminal evidence")
            else:
                raise LifecycleError("terminal runtime lacks a recognized authority")
        if current.get("observed_model") is not None:
            if current.get("observed_model") != attempt.get("requested_model"):
                raise LifecycleError("retained observed model differs from admitted model")
            if current.get("model_evidence_digest") not in verified_digests:
                raise LifecycleError("retained model evidence is not signed")
        telemetry = current.get("telemetry")
        if telemetry is not None:
            sources = telemetry.get("source_observation_digests") if isinstance(telemetry, dict) else None
            revisions = telemetry.get("provider_revisions") if isinstance(telemetry, dict) else None
            if (
                not isinstance(sources, list)
                or not set(sources).issubset(set(verified_digests))
                or not isinstance(revisions, list)
                or len(revisions) != len(set(revisions))
            ):
                raise LifecycleError("retained telemetry provenance is invalid")
        if status in POST_TERMINAL_STATES and not isinstance(current.get("receipt"), dict):
            raise LifecycleError("post-terminal runtime lacks a receipt")
        if status in POST_TERMINAL_STATES:
            receipt_errors = receipt_module().audit_retained_receipt(
                attempt,
                keyring_path=keyring_path,
                decision_public_key_path=decision_public_key_path,
                expected_child_attempts=expected_child_attempts or [],
            )
            if receipt_errors:
                raise LifecycleError(receipt_errors[0])
        if status == "reconciled" and not isinstance(current.get("reconciliation"), dict):
            raise LifecycleError("reconciled runtime lacks reconciliation")
        if status == "reconciled":
            if decision_public_key_path is None:
                raise LifecycleError("reconciled runtime audit requires the pinned decision issuer key")
            reconciliation_errors = receipt_module().audit_retained_reconciliation(
                attempt,
                decision_public_key_path=decision_public_key_path,
            )
            if reconciliation_errors:
                raise LifecycleError(reconciliation_errors[0])
    except LifecycleError as exc:
        return [str(exc)]
    return []
