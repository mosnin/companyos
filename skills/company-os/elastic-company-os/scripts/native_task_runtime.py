"""Pure feature-off state machine for host-operated native Codex tasks.

This module performs no I/O and has no Codex app-tool integration. The
interactive host executes native operations; the controller persists only
explicit desired state and returned host observations.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Mapping


SCHEMA = "company-os.native-task-runtime.v1"
DISPATCH_RECEIPT_SCHEMA = "company-os.native-task-dispatch-admission.v1"
TERMINAL_STATUSES = {
    "succeeded",
    "failed",
    "cancelled",
    "blocked_model_unavailable",
    "cancelled_before_launch",
}
ACTIVE_STATUSES = {
    "dispatch_intent_recorded",
    "dispatch_claimed",
    "host_created",
    "running",
    "cancel_requested",
    "cancel_acknowledged",
}
HARD_CANCELLATION_STATUSES = {"acknowledged", "refused", "failed"}
ACKNOWLEDGEMENT_STATUSES = {"acknowledged", "not_acknowledged"}


class RuntimeStateError(ValueError):
    """Raised when a native lifecycle transition fails closed."""


def canonical_digest(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise RuntimeStateError("native runtime value is not canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def unavailable(reason: str) -> dict[str, Any]:
    return {"status": "unavailable", "value": None, "reason": reason}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise RuntimeStateError(f"{field} must be a non-empty trimmed string")
    return value


def _validate_state_header(state: Mapping[str, Any]) -> None:
    if not isinstance(state, Mapping) or state.get("schema") != SCHEMA:
        raise RuntimeStateError("invalid native runtime state")
    if state.get("status") not in ACTIVE_STATUSES | TERMINAL_STATUSES:
        raise RuntimeStateError("invalid native runtime status")


def _event_payload(state: Mapping[str, Any], event: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(dict(payload))
    identity = state.get("native_identity")
    if event == "dispatch_claimed":
        allowed = {"dispatch_key", "payload_sha256"}
        if set(normalized) != allowed:
            raise RuntimeStateError("dispatch claim payload shape is invalid")
        _text(normalized.get("dispatch_key"), "dispatch_key")
        _text(normalized.get("payload_sha256"), "payload_sha256")
    elif event == "cancel_requested":
        allowed = {"reason", "requested_by"}
        if set(normalized) != allowed:
            raise RuntimeStateError("cancellation intent payload shape is invalid")
        _text(normalized.get("reason"), "reason")
        _text(normalized.get("requested_by"), "requested_by")
    elif event == "cancelled_before_launch":
        if normalized != {"source": "controller_reconciliation"}:
            raise RuntimeStateError("pre-launch cancellation requires controller reconciliation")
    elif event in {
        "host_created",
        "running",
        "cooperative_stop_delivered",
        "hard_cancellation_observed",
        "terminal",
    }:
        common = {"source", "tool", "task_id", "thread_id"}
        optional = {"host_id"}
        required = set(common)
        if event == "host_created":
            required.add("host_id")
        elif event == "running":
            optional.add("current_status")
        elif event == "hard_cancellation_observed":
            required.update({"hard_status", "acknowledgement_status"})
        elif event == "terminal":
            required.add("status")
            optional.update({"terminal_message_digest", "artifact_digests"})
        if not required.issubset(normalized) or set(normalized) - required - optional:
            raise RuntimeStateError(f"{event} host observation payload shape is invalid")
        if normalized.get("source") != "host_observation":
            raise RuntimeStateError(f"{event} requires a returned host observation")
        for field in ("tool", "task_id", "thread_id"):
            _text(normalized.get(field), field)
        if "host_id" in normalized:
            _text(normalized.get("host_id"), "host_id")
        if identity is not None and (
            normalized.get("task_id") != identity.get("task_id")
            or normalized.get("thread_id") != identity.get("thread_id")
            or (
                "host_id" in normalized
                and normalized.get("host_id") != identity.get("host_id")
            )
        ):
            raise RuntimeStateError("host observation identity conflicts with the bound native task")
        if event == "hard_cancellation_observed":
            if normalized.get("hard_status") not in HARD_CANCELLATION_STATUSES:
                raise RuntimeStateError("hard cancellation status is invalid")
            if normalized.get("acknowledgement_status") not in ACKNOWLEDGEMENT_STATUSES:
                raise RuntimeStateError("cancellation acknowledgement status is invalid")
        if event == "terminal":
            if normalized.get("status") not in TERMINAL_STATUSES - {"cancelled_before_launch"}:
                raise RuntimeStateError("terminal status is invalid")
            artifact_digests = normalized.get("artifact_digests")
            if artifact_digests is not None and (
                not isinstance(artifact_digests, list)
                or any(not isinstance(item, str) or not item for item in artifact_digests)
            ):
                raise RuntimeStateError("terminal artifact digests are invalid")
    else:
        raise RuntimeStateError(f"unsupported native runtime event: {event}")
    canonical_digest(normalized)
    return normalized


def _has_event(state: Mapping[str, Any], event: str, payload: Mapping[str, Any]) -> bool:
    return any(
        isinstance(item, Mapping)
        and item.get("event") == event
        and item.get("payload") == payload
        for item in state.get("events", [])
    )


def _append_event(state: dict[str, Any], event: str, payload: dict[str, Any]) -> None:
    state["sequence"] += 1
    retained = {
        "sequence": state["sequence"],
        "event": event,
        "payload": deepcopy(payload),
        "payload_sha256": canonical_digest(payload),
    }
    state["events"].append(retained)
    if payload.get("source") == "host_observation":
        state["host_observations"].append(deepcopy(retained))


def _receipt_payload(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "admission_digest": state.get("admission_digest"),
        "dispatch": state.get("dispatch"),
        "native_identity": state.get("native_identity"),
        "host_observations": state.get("host_observations"),
        "cancellation": state.get("cancellation"),
        "terminal": state.get("terminal"),
        "observed_model": state.get("observed_model"),
        "provider_usage": state.get("provider_usage"),
        "cost": state.get("cost"),
        "authority_history": state.get("authority_history"),
    }


def admit(
    *,
    attempt_id: str,
    idempotency_key: str,
    requested_model: str,
    project_id: str,
    work_id: str,
    cycle_id: str,
    parent_runtime_id: str,
    role: str,
    scope: Any,
    budget: Mapping[str, Any],
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a content-bound, pre-create admission and dispatch receipt."""
    admission = {
        "attempt_id": _text(attempt_id, "attempt_id"),
        "idempotency_key": _text(idempotency_key, "idempotency_key"),
        "requested_model": _text(requested_model, "requested_model"),
        "project_id": _text(project_id, "project_id"),
        "work_id": _text(work_id, "work_id"),
        "cycle_id": _text(cycle_id, "cycle_id"),
        "parent_runtime_id": _text(parent_runtime_id, "parent_runtime_id"),
        "role": _text(role, "role"),
        "scope": deepcopy(scope),
        "budget": deepcopy(dict(budget)),
        "metadata": deepcopy(dict(metadata or {})),
    }
    admission_digest = canonical_digest(admission)
    dispatch_receipt = {
        "schema": DISPATCH_RECEIPT_SCHEMA,
        "status": "admitted_pre_create",
        "attempt_id": attempt_id,
        "dispatch_key": idempotency_key,
        "admission_digest": admission_digest,
    }
    state = {
        "schema": SCHEMA,
        "status": "dispatch_intent_recorded",
        "attempt_id": attempt_id,
        "requested_model": requested_model,
        "admission": admission,
        "admission_digest": admission_digest,
        "dispatch_receipt": dispatch_receipt,
        "dispatch": {
            "status": "intent_recorded",
            "key": idempotency_key,
            "payload_sha256": canonical_digest(dispatch_receipt),
        },
        "native_identity": None,
        "host_observations": [],
        "observed_model": unavailable("native_host_did_not_expose_observed_model"),
        "provider_usage": unavailable("native_host_did_not_expose_provider_usage"),
        "cost": unavailable("native_host_did_not_expose_cost"),
        "authority_history": [],
        "cancellation": {
            "desired_intent": "run",
            "intent_status": "not_requested",
            "intent": None,
            "cooperative_stop_delivery": "not_requested",
            "hard_cancellation_status": "unavailable",
            "acknowledgement_status": "unavailable",
        },
        "sequence": 1,
        "events": [
            {
                "sequence": 1,
                "event": "dispatch_intent_recorded",
                "payload": deepcopy(dispatch_receipt),
                "payload_sha256": canonical_digest(dispatch_receipt),
            }
        ],
        "terminal": None,
        "receipt": None,
        "reconciliation": {"status": "pending", "next_action": "claim_dispatch"},
    }
    errors = audit_state(state)
    if errors:
        raise RuntimeStateError("invalid admitted native runtime state: " + "; ".join(errors))
    return state


def record_event(
    state: Mapping[str, Any],
    event: str,
    *,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply one monotonic event; an exact repeated observation is a no-op."""
    _validate_state_header(state)
    normalized = _event_payload(state, event, payload or {})
    if _has_event(state, event, normalized):
        return deepcopy(dict(state))
    if state.get("status") in TERMINAL_STATUSES:
        raise RuntimeStateError("terminal native runtime state is immutable")

    out = deepcopy(dict(state))
    status = out["status"]
    if event == "dispatch_claimed":
        if out["dispatch"]["status"] != "intent_recorded" or status != "dispatch_intent_recorded":
            raise RuntimeStateError("dispatch claim is out of order")
        if normalized["dispatch_key"] != out["dispatch"]["key"]:
            raise RuntimeStateError("dispatch claim key conflicts with admission")
        if normalized["payload_sha256"] != out["dispatch"]["payload_sha256"]:
            raise RuntimeStateError("dispatch claim payload conflicts with admission")
        out["dispatch"]["status"] = "claimed_create_in_flight"
        out["status"] = "dispatch_claimed"
    elif event == "host_created":
        if out["dispatch"]["status"] != "claimed_create_in_flight" or status != "dispatch_claimed":
            raise RuntimeStateError("host creation requires a durable dispatch claim")
        identity = {
            "task_id": normalized["task_id"],
            "thread_id": normalized["thread_id"],
            "host_id": normalized["host_id"],
        }
        if out["native_identity"] not in (None, identity):
            raise RuntimeStateError("native task identity is immutable")
        out["native_identity"] = identity
        out["dispatch"]["status"] = "bound"
        out["status"] = "host_created"
    elif event == "running":
        if status != "host_created" or out.get("native_identity") is None:
            raise RuntimeStateError("running observation is out of order")
        out["status"] = "running"
    elif event == "cancel_requested":
        if out["cancellation"]["desired_intent"] == "cancel":
            raise RuntimeStateError("cancellation intent conflicts with an earlier request")
        out["cancellation"].update(
            {
                "desired_intent": "cancel",
                "intent_status": "requested",
                "intent": deepcopy(normalized),
                "cooperative_stop_delivery": (
                    "pending" if out.get("native_identity") is not None else "not_applicable"
                ),
            }
        )
        out["status"] = "cancel_requested"
    elif event == "cooperative_stop_delivered":
        if out["cancellation"]["desired_intent"] != "cancel" or out.get("native_identity") is None:
            raise RuntimeStateError("cooperative stop delivery is out of order")
        out["cancellation"]["cooperative_stop_delivery"] = "delivered"
        out["status"] = "cancel_requested"
    elif event == "hard_cancellation_observed":
        if out["cancellation"]["desired_intent"] != "cancel" or out.get("native_identity") is None:
            raise RuntimeStateError("hard cancellation observation is out of order")
        out["cancellation"]["hard_cancellation_status"] = normalized["hard_status"]
        out["cancellation"]["acknowledgement_status"] = normalized[
            "acknowledgement_status"
        ]
        out["status"] = "cancel_acknowledged"
    elif event == "cancelled_before_launch":
        if (
            out["cancellation"]["desired_intent"] != "cancel"
            or out.get("native_identity") is not None
            or out["dispatch"]["status"] != "intent_recorded"
        ):
            raise RuntimeStateError("pre-launch cancellation cannot resolve ambiguous creation")
        out["dispatch"]["status"] = "cancelled"
        out["status"] = "cancelled_before_launch"
        out["terminal"] = {"status": "cancelled_before_launch", "observation": normalized}
    elif event == "terminal":
        if status not in {"running", "cancel_requested", "cancel_acknowledged"}:
            raise RuntimeStateError("terminal observation requires ordered create and start evidence")
        terminal_status = normalized["status"]
        if (
            out["cancellation"]["desired_intent"] == "cancel"
            and terminal_status != "cancelled"
        ):
            raise RuntimeStateError("post-cancellation success or failure is rejected")
        out["status"] = terminal_status
        out["terminal"] = {"status": terminal_status, "observation": normalized}

    _append_event(out, event, normalized)
    if out["status"] in TERMINAL_STATUSES:
        receipt_payload = _receipt_payload(out)
        out["receipt"] = {
            "status": (
                "cancelled"
                if out["status"].startswith("cancelled")
                else "complete" if out["status"] == "succeeded" else "failed"
            ),
            "terminal_status": out["status"],
            "payload_sha256": canonical_digest(receipt_payload),
        }
        out["reconciliation"] = {"status": "terminal", "next_action": "none"}
    else:
        out = reconcile_restart(out)
    errors = audit_state(out)
    if errors:
        raise RuntimeStateError("native runtime transition failed audit: " + "; ".join(errors))
    return out


def claim_dispatch(state: Mapping[str, Any]) -> dict[str, Any]:
    dispatch = state.get("dispatch", {})
    return record_event(
        state,
        "dispatch_claimed",
        payload={
            "dispatch_key": dispatch.get("key"),
            "payload_sha256": dispatch.get("payload_sha256"),
        },
    )


def bind_host_identity(
    state: Mapping[str, Any],
    *,
    task_id: str,
    thread_id: str,
    tool: str,
    host_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "source": "host_observation",
        "tool": tool,
        "task_id": task_id,
        "thread_id": thread_id,
    }
    if host_id is not None:
        payload["host_id"] = host_id
    return record_event(state, "host_created", payload=payload)


def request_cancellation(
    state: Mapping[str, Any], *, reason: str, requested_by: str
) -> dict[str, Any]:
    return record_event(
        state,
        "cancel_requested",
        payload={"reason": reason, "requested_by": requested_by},
    )


def reconcile_restart(state: Mapping[str, Any]) -> dict[str, Any]:
    """Derive the next host action without binding identity or relaunching work."""
    _validate_state_header(state)
    out = deepcopy(dict(state))
    if out["status"] in TERMINAL_STATUSES:
        next_action = "none"
        reconciliation_status = "terminal"
    elif out["cancellation"]["desired_intent"] == "cancel":
        if out.get("native_identity") is not None:
            if out["cancellation"]["cooperative_stop_delivery"] == "pending":
                next_action = "deliver_cooperative_stop"
            else:
                next_action = "await_cancellation_observation"
        elif out["dispatch"]["status"] == "intent_recorded":
            next_action = "finalize_cancelled_before_launch"
        else:
            next_action = "reconcile_host_listing"
        reconciliation_status = "pending"
    elif out.get("native_identity") is None:
        if out["dispatch"]["status"] == "intent_recorded":
            next_action = "claim_dispatch"
        else:
            next_action = "reconcile_host_listing"
        reconciliation_status = "pending"
    elif out["status"] == "host_created":
        next_action = "await_started_observation"
        reconciliation_status = "pending"
    else:
        next_action = "await_terminal_observation"
        reconciliation_status = "pending"
    out["reconciliation"] = {
        "status": reconciliation_status,
        "next_action": next_action,
    }
    return out


def audit_state(state: Mapping[str, Any]) -> list[str]:
    """Return deterministic retained-state integrity errors."""
    errors: list[str] = []
    try:
        _validate_state_header(state)
    except RuntimeStateError as exc:
        return [str(exc)]
    expected_fields = {
        "schema", "status", "attempt_id", "requested_model", "admission",
        "admission_digest", "dispatch_receipt", "dispatch", "native_identity",
        "host_observations", "observed_model", "provider_usage", "cost",
        "authority_history", "cancellation", "sequence", "events", "terminal",
        "receipt", "reconciliation",
    }
    if set(state) != expected_fields:
        errors.append("native runtime state fields are invalid")
    admission = state.get("admission")
    admission_fields = {
        "attempt_id", "idempotency_key", "requested_model", "project_id",
        "work_id", "cycle_id", "parent_runtime_id", "role", "scope", "budget",
        "metadata",
    }
    if (
        not isinstance(admission, Mapping)
        or set(admission) != admission_fields
        or canonical_digest(admission) != state.get("admission_digest")
        or state.get("attempt_id") != admission.get("attempt_id")
        or state.get("requested_model") != admission.get("requested_model")
    ):
        errors.append("native runtime admission digest is invalid")
    dispatch_receipt = state.get("dispatch_receipt")
    expected_dispatch_receipt = {
        "schema": DISPATCH_RECEIPT_SCHEMA,
        "status": "admitted_pre_create",
        "attempt_id": state.get("attempt_id"),
        "dispatch_key": admission.get("idempotency_key") if isinstance(admission, Mapping) else None,
        "admission_digest": state.get("admission_digest"),
    }
    if dispatch_receipt != expected_dispatch_receipt:
        errors.append("native runtime dispatch admission receipt is invalid")
    dispatch = state.get("dispatch")
    if (
        not isinstance(dispatch, Mapping)
        or set(dispatch) != {"status", "key", "payload_sha256"}
        or dispatch.get("status") not in {
            "intent_recorded", "claimed_create_in_flight", "bound", "cancelled",
        }
        or dispatch.get("key") != expected_dispatch_receipt["dispatch_key"]
        or dispatch.get("payload_sha256") != canonical_digest(expected_dispatch_receipt)
    ):
        errors.append("native runtime dispatch state is invalid")
    events = state.get("events")
    if not isinstance(events, list) or not events:
        errors.append("native runtime events are missing")
    else:
        for expected, event in enumerate(events, start=1):
            if (
                not isinstance(event, Mapping)
                or event.get("sequence") != expected
                or canonical_digest(event.get("payload")) != event.get("payload_sha256")
            ):
                errors.append("native runtime event order or digest is invalid")
                break
            if expected > 1:
                try:
                    _event_payload(state, event.get("event"), event.get("payload"))
                except (RuntimeStateError, TypeError):
                    errors.append("native runtime retained event payload is invalid")
                    break
        if state.get("sequence") != len(events):
            errors.append("native runtime sequence does not match retained events")
        if events[0].get("event") != "dispatch_intent_recorded" or events[0].get("payload") != dispatch_receipt:
            errors.append("native runtime first event does not bind pre-create admission")
    identity = state.get("native_identity")
    if identity is not None and (
        not isinstance(identity, Mapping)
        or not identity.get("task_id")
        or not identity.get("thread_id")
        or not identity.get("host_id")
    ):
        errors.append("native runtime identity binding is invalid")
    if isinstance(dispatch, Mapping):
        status = state.get("status")
        if (
            (status == "dispatch_intent_recorded" and dispatch.get("status") != "intent_recorded")
            or (status == "dispatch_claimed" and dispatch.get("status") != "claimed_create_in_flight")
            or (status == "cancelled_before_launch" and dispatch.get("status") != "cancelled")
            or (
                status not in {"dispatch_intent_recorded", "dispatch_claimed", "cancel_requested", "cancelled_before_launch"}
                and dispatch.get("status") != "bound"
            )
            or (identity is not None and dispatch.get("status") != "bound")
        ):
            errors.append("native runtime status conflicts with dispatch state")
    host_observations = state.get("host_observations")
    expected_host_observations = [
        deepcopy(event) for event in events or []
        if isinstance(event, Mapping)
        and isinstance(event.get("payload"), Mapping)
        and event["payload"].get("source") == "host_observation"
    ]
    if host_observations != expected_host_observations:
        errors.append("native runtime host observation chain is invalid")
    for field in ("observed_model", "provider_usage", "cost"):
        value = state.get(field)
        if (
            not isinstance(value, Mapping)
            or set(value) != {"status", "value", "reason"}
            or value.get("status") != "unavailable"
            or value.get("value") is not None
            or not isinstance(value.get("reason"), str)
            or not value.get("reason")
        ):
            errors.append(f"native runtime {field} must remain unavailable")
    cancellation = state.get("cancellation")
    cancellation_fields = {
        "desired_intent", "intent_status", "intent", "cooperative_stop_delivery",
        "hard_cancellation_status", "acknowledgement_status",
    }
    if not isinstance(cancellation, Mapping) or frozenset(cancellation) not in {
        frozenset(cancellation_fields), frozenset(cancellation_fields | {"dispatch"})
    } or cancellation.get("desired_intent") not in {"run", "cancel"}:
        errors.append("native runtime cancellation state is invalid")
    elif cancellation.get("desired_intent") == "run":
        if (
            cancellation.get("intent_status") != "not_requested"
            or cancellation.get("intent") is not None
            or "dispatch" in cancellation
        ):
            errors.append("native runtime cancellation intent is inconsistent")
    else:
        if cancellation.get("intent_status") != "requested" or not isinstance(cancellation.get("intent"), Mapping):
            errors.append("native runtime cancellation intent is inconsistent")
        cancellation_dispatch = cancellation.get("dispatch")
        if cancellation_dispatch is not None and (
            not isinstance(cancellation_dispatch, Mapping)
            or set(cancellation_dispatch) != {"status", "key", "payload_sha256"}
            or cancellation_dispatch.get("status") not in {"pending", "claimed", "delivered"}
            or cancellation_dispatch.get("key") != state.get("attempt_id")
            or not isinstance(cancellation_dispatch.get("payload_sha256"), str)
            or len(cancellation_dispatch.get("payload_sha256")) != 64
        ):
            errors.append("native runtime cancellation dispatch is invalid")
    authority_history = state.get("authority_history")
    if not isinstance(authority_history, list) or any(
        not isinstance(item, Mapping)
        or set(item) != {"action", "actor", "decision", "event", "payload_hash", "grant"}
        for item in authority_history
    ):
        errors.append("native runtime authority history is invalid")
    if state.get("status") in TERMINAL_STATUSES:
        terminal = state.get("terminal")
        if not isinstance(terminal, Mapping) or terminal.get("status") != state.get("status"):
            errors.append("native runtime terminal state is invalid")
        receipt = state.get("receipt")
        if not isinstance(receipt, Mapping) or receipt.get("payload_sha256") != canonical_digest(
            _receipt_payload(state)
        ):
            errors.append("native runtime terminal receipt is invalid")
    elif state.get("receipt") is not None:
        errors.append("active native runtime state cannot contain a terminal receipt")
    elif state.get("terminal") is not None:
        errors.append("active native runtime state cannot contain terminal observation")
    try:
        expected_reconciliation = reconcile_restart(state)["reconciliation"]
        if state.get("reconciliation") != expected_reconciliation:
            errors.append("native runtime reconciliation state is invalid")
    except RuntimeStateError:
        errors.append("native runtime reconciliation state is invalid")
    return errors


def apply_event(state: Mapping[str, Any], event: str, **payload: Any) -> dict[str, Any]:
    return record_event(state, event, payload=payload)
