#!/usr/bin/env python3
"""Destination-driven navigation controller for Company OS.

The controller treats research, audits, tests, browser observations, and runtime
telemetry as sensors. They exist to improve the next safe action, not to become
an alternate destination. Product changes, integration, runtime execution, and
repair are actuators that move objective reality.

The minimum-sufficient-actuation ladder is informed by the MIT-licensed
DietrichGebert/ponytail project, but deliberately does not inherit Ponytail's
requirement-challenging modes. Explicit user requirements and safety invariants
remain mandatory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

INPUT_SCHEMA = "company-os.navigation-input.v1"
DECISION_SCHEMA = "company-os.navigation-decision.v1"
CAPABILITY_ORDER = {"missing": 0, "partial": 1, "runnable": 2, "connected": 3, "verified": 4}
SENSOR_CLASSES = {"research", "architecture", "governance", "evaluation", "documentation"}
ACTUATOR_CLASSES = {"implementation", "integration", "runtime", "repair", "checkpoint", "packaging"}
EXECUTION_CLASSES = {"implementation", "integration", "runtime", "repair"}
PROGRESS_EVENT_KINDS = {"artifact_materialized", "runtime_observed", "journey_connected", "independent_accepted", "checkpoint_recorded"}
ACTUATION_ATTEMPT_EVENT_KINDS = {"task_completed", "task_failed"}


class NavigationError(ValueError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise NavigationError(f"{label} must be a nonempty string")
    return value.strip()


def _time(value: Any, label: str) -> datetime:
    raw = _text(value, label)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NavigationError(f"{label} must be RFC3339") from exc
    if parsed.tzinfo is None:
        raise NavigationError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


def _format(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _fraction(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise NavigationError(f"{label} must be finite")
    result = float(value)
    if result < 0.0 or result > 1.0:
        raise NavigationError(f"{label} must be between zero and one")
    return result


def _capabilities(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise NavigationError("capabilities must be a nonempty array")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise NavigationError(f"capabilities[{index}] must be an object")
        capability_id = _text(item.get("capability_id"), f"capabilities[{index}].capability_id")
        if capability_id in seen:
            raise NavigationError(f"duplicate capability {capability_id}")
        seen.add(capability_id)
        state = item.get("state")
        if state not in CAPABILITY_ORDER:
            raise NavigationError(f"{capability_id}.state is invalid")
        priority = item.get("priority", 50)
        if not isinstance(priority, int) or isinstance(priority, bool) or priority < 0 or priority > 100:
            raise NavigationError(f"{capability_id}.priority must be 0..100")
        existing = item.get("existing_implementation")
        if existing is not None:
            existing = _text(existing, f"{capability_id}.existing_implementation")
        result.append({
            "capability_id": capability_id,
            "label": str(item.get("label") or capability_id),
            "state": state,
            "critical": item.get("critical") is True,
            "priority": priority,
            "first_reality": item.get("first_reality") is True,
            "final_required": item.get("final_required") is not False,
            "existing_implementation": existing,
        })
    return result


def _signals(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, Mapping):
        raise NavigationError("reality must be an object")
    keys = ("internal_primitives", "runnable_capability", "connected_vertical_slice", "user_usable", "independent_acceptance")
    result = {}
    for key in keys:
        value = raw.get(key, False)
        if not isinstance(value, bool):
            raise NavigationError(f"reality.{key} must be boolean")
        result[key] = value
    return result


def _allocation(raw: Any) -> dict[str, float]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise NavigationError("allocation must be an object")
    result = {}
    total = 0.0
    for key, value in raw.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or float(value) < 0:
            raise NavigationError(f"allocation.{key} must be nonnegative finite")
        result[str(key)] = float(value)
        total += float(value)
    if total <= 0:
        return result
    return {key: value / total for key, value in result.items()}


def _weight(item: Mapping[str, Any]) -> float:
    weight = 1.0 + float(item.get("priority", 50)) / 100.0
    if item.get("critical") is True:
        weight += 1.0
    if item.get("first_reality") is True:
        weight += 0.5
    return weight


def _distance(capabilities: list[dict[str, Any]], target: int, selector, *, checkpoint_required: bool, checkpointed: bool) -> float:
    relevant = [item for item in capabilities if selector(item)]
    if not relevant:
        return 0.0
    maximum = sum(_weight(item) * target for item in relevant)
    remaining = sum(_weight(item) * max(0, target - CAPABILITY_ORDER[item["state"]]) for item in relevant)
    if checkpoint_required:
        maximum += 1.0
        if not checkpointed:
            remaining += 1.0
    if maximum <= 0:
        return 0.0
    return round(remaining / maximum, 6)


def _waypoint(signals: Mapping[str, bool]) -> str:
    if not signals["connected_vertical_slice"]:
        return "R3_FIRST_REALITY"
    if not signals["user_usable"]:
        return "R4_USER_USABLE"
    if not signals["independent_acceptance"]:
        return "R5_INDEPENDENT_ACCEPTANCE"
    return "ARRIVED"


def _relevant_for_waypoint(item: Mapping[str, Any], waypoint: str) -> bool:
    if waypoint == "R3_FIRST_REALITY":
        return item.get("first_reality") is True or item.get("critical") is True
    return item.get("final_required") is True


def _next_capability(capabilities: list[dict[str, Any]], waypoint: str, target: int) -> dict[str, Any] | None:
    unresolved = [item for item in capabilities if _relevant_for_waypoint(item, waypoint) and CAPABILITY_ORDER[item["state"]] < target]
    if not unresolved:
        return None
    unresolved.sort(key=lambda item: (
        CAPABILITY_ORDER[item["state"]],
        0 if item["critical"] else 1,
        -item["priority"],
        item["capability_id"],
    ))
    return unresolved[0]


def _action_for(capability: Mapping[str, Any] | None, *, waypoint: str, checkpointed: bool) -> dict[str, Any]:
    if waypoint == "ARRIVED":
        return {"action_kind": "hold_destination", "work_class": "checkpoint", "capability_id": None, "instruction": "Destination reached. Preserve the accepted state and do not invent new work."}
    if capability is None:
        if waypoint == "R4_USER_USABLE" and not checkpointed:
            return {"action_kind": "checkpoint", "work_class": "checkpoint", "capability_id": None, "instruction": "Checkpoint the connected product bytes so the fresh-user outcome becomes durable."}
        return {"action_kind": "verify", "work_class": "evaluation", "capability_id": None, "instruction": "Run the minimum independent verification needed to advance the current waypoint."}
    capability_id = capability["capability_id"]
    state = capability["state"]
    existing = capability.get("existing_implementation")
    if state == "missing":
        if existing:
            return {"action_kind": "integrate_existing", "work_class": "integration", "capability_id": capability_id, "instruction": f"Exercise and integrate the supplied implementation for {capability_id} before writing a replacement."}
        return {"action_kind": "materialize", "work_class": "implementation", "capability_id": capability_id, "instruction": f"Materialize the smallest real {capability_id} artifact that changes objective reality."}
    if state == "partial":
        return {"action_kind": "run", "work_class": "runtime", "capability_id": capability_id, "instruction": f"Run the real {capability_id} capability and observe its behavior; do not add supporting prose instead."}
    if state == "runnable":
        return {"action_kind": "connect", "work_class": "integration", "capability_id": capability_id, "instruction": f"Connect {capability_id} into the active end-to-end user journey and observe the resulting state transition."}
    return {"action_kind": "verify", "work_class": "evaluation", "capability_id": capability_id, "instruction": f"Independently verify the connected {capability_id} behavior against the original objective."}


def _events(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        occurred_at = item.get("occurred_at")
        kind = item.get("kind")
        if not isinstance(occurred_at, str) or not isinstance(kind, str):
            continue
        try:
            parsed = _time(occurred_at, "event.occurred_at")
        except NavigationError:
            continue
        result.append({"kind": kind, "occurred_at": parsed, "work_class": item.get("work_class")})
    result.sort(key=lambda item: item["occurred_at"])
    return result


def _velocity(previous: Mapping[str, Any] | None, *, now: datetime, destination_distance: float, events: list[dict[str, Any]], mission_class: str) -> dict[str, Any]:
    previous_distance = None
    previous_at = None
    trajectory = []
    if isinstance(previous, Mapping):
        trajectory_raw = previous.get("trajectory")
        if isinstance(trajectory_raw, list):
            trajectory = [dict(item) for item in trajectory_raw if isinstance(item, Mapping)][-31:]
        position = previous.get("position")
        if isinstance(position, Mapping) and isinstance(position.get("destination_distance"), (int, float)):
            previous_distance = float(position["destination_distance"])
        if trajectory and isinstance(trajectory[-1].get("at"), str):
            try:
                previous_at = _time(trajectory[-1]["at"], "trajectory.at")
            except NavigationError:
                previous_at = None
    delta = 0.0 if previous_distance is None else round(previous_distance - destination_distance, 6)
    per_minute = None
    if previous_at is not None and now > previous_at:
        elapsed_minutes = max((now - previous_at).total_seconds() / 60.0, 1e-6)
        per_minute = round(delta / elapsed_minutes, 6)

    last_progress = None
    for event in events:
        if event["kind"] in PROGRESS_EVENT_KINDS:
            last_progress = event["occurred_at"]
    action_events = [
        event for event in events
        if event["kind"] in ACTUATION_ATTEMPT_EVENT_KINDS
        and event.get("work_class") in ACTUATOR_CLASSES
        and (last_progress is None or event["occurred_at"] > last_progress)
    ]
    thresholds = {"quick_build": 10.0, "bounded_feature": 20.0, "company_mission": 30.0, "long_running_company": 60.0}
    threshold = thresholds.get(mission_class, 30.0)
    minutes_since_progress = None
    if last_progress is not None:
        minutes_since_progress = max(0.0, (now - last_progress).total_seconds() / 60.0)
    elif events:
        minutes_since_progress = max(0.0, (now - events[0]["occurred_at"]).total_seconds() / 60.0)
    stalled = bool(
        len(action_events) >= 3
        or (minutes_since_progress is not None and minutes_since_progress >= threshold and len(action_events) >= 1)
    )
    return {
        "distance_delta": delta,
        "distance_per_minute": per_minute,
        "minutes_since_progress": None if minutes_since_progress is None else round(minutes_since_progress, 3),
        "actuation_attempts_since_progress": len(action_events),
        "stalled": stalled,
        "stagnation_threshold_minutes": threshold,
        "trajectory": trajectory,
    }


def _sensor_ceiling(waypoint: str, stalled: bool) -> float:
    if stalled:
        return 0.15
    if waypoint == "R3_FIRST_REALITY":
        return 0.25
    if waypoint == "R4_USER_USABLE":
        return 0.30
    if waypoint == "R5_INDEPENDENT_ACCEPTANCE":
        return 0.35
    return 0.10


def _minimum_sufficient_actuation() -> dict[str, Any]:
    return {
        "policy": "minimum_sufficient_actuation",
        "ladder": [
            "Reuse the existing code path, helper, integration, or supplied implementation when it satisfies the route.",
            "Prefer standard-library or native platform capability over custom infrastructure when it preserves required behavior.",
            "Prefer an already-installed dependency over adding another dependency when it satisfies the route.",
            "Only then write the smallest new code that produces the required observable state transition.",
            "Leave one runnable check for non-trivial logic so simplification cannot silently remove correctness.",
        ],
        "never_cut": [
            "explicit user requirements",
            "trust-boundary validation",
            "security controls",
            "data-loss prevention",
            "required error handling",
            "accessibility basics",
            "runtime observation needed to prove the state transition",
        ],
        "forbid_speculation": True,
    }


def evaluate(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("$schema") != INPUT_SCHEMA:
        raise NavigationError("input schema is invalid")
    objective_id = _text(payload.get("objective_id"), "objective_id")
    objective = _text(payload.get("objective"), "objective")
    current = _time(payload.get("now"), "now")
    mission_class = _text(payload.get("mission_class"), "mission_class")
    capabilities = _capabilities(payload.get("capabilities"))
    signals = _signals(payload.get("reality"))
    checkpointed = payload.get("checkpointed") is True
    allocation = _allocation(payload.get("allocation"))
    events = _events(payload.get("events"))
    previous = payload.get("previous_navigation") if isinstance(payload.get("previous_navigation"), Mapping) else None

    waypoint = _waypoint(signals)
    destination_distance = _distance(capabilities, 4, lambda item: item.get("final_required") is True, checkpoint_required=True, checkpointed=checkpointed)
    waypoint_target = 3 if waypoint in {"R3_FIRST_REALITY", "R4_USER_USABLE"} else 4
    waypoint_distance = 0.0 if waypoint == "ARRIVED" else _distance(
        capabilities,
        waypoint_target,
        lambda item: _relevant_for_waypoint(item, waypoint),
        checkpoint_required=waypoint in {"R4_USER_USABLE", "R5_INDEPENDENT_ACCEPTANCE"},
        checkpointed=checkpointed,
    )
    velocity = _velocity(previous, now=current, destination_distance=destination_distance, events=events, mission_class=mission_class)
    target = _next_capability(capabilities, waypoint, waypoint_target)
    next_action = _action_for(target, waypoint=waypoint, checkpointed=checkpointed)

    sensor_fraction = sum(value for key, value in allocation.items() if key in SENSOR_CLASSES)
    sensor_ceiling = _sensor_ceiling(waypoint, velocity["stalled"])
    sensor_overrun = sensor_fraction > sensor_ceiling + 1e-9
    if waypoint == "ARRIVED":
        mode = "arrived"
    elif velocity["stalled"]:
        mode = "stalled_replan"
    else:
        mode = "navigate"

    trajectory = list(velocity.pop("trajectory"))
    snapshot = {
        "at": _format(current),
        "destination_distance": destination_distance,
        "waypoint_distance": waypoint_distance,
        "waypoint": waypoint,
        "next_action_kind": next_action["action_kind"],
        "capability_id": next_action.get("capability_id"),
    }
    if not trajectory or any(
        trajectory[-1].get(key) != snapshot.get(key)
        for key in ("destination_distance", "waypoint_distance", "waypoint", "next_action_kind", "capability_id")
    ):
        trajectory.append(snapshot)
    trajectory = trajectory[-32:]

    orders = []
    if mode == "stalled_replan":
        orders.append("Trajectory is stalled. Change the implementation strategy or responsible context; do not answer stagnation with more general research or reports.")
    if sensor_overrun:
        orders.append("Sensor work exceeded its route budget. Stop nonblocking research, architecture, governance, evaluation, and documentation until objective movement resumes.")
    if waypoint != "ARRIVED":
        orders.append(next_action["instruction"])
        orders.append("After the action, observe the resulting environment state and replan from evidence rather than from the prior plan.")
    else:
        orders.append("Destination reached. Preserve the accepted state and stop generating work.")

    decision = {
        "$schema": DECISION_SCHEMA,
        "objective_id": objective_id,
        "objective": objective,
        "mode": mode,
        "waypoint": waypoint,
        "position": {"destination_distance": destination_distance, "waypoint_distance": waypoint_distance, "reality": signals, "checkpointed": checkpointed},
        "velocity": velocity,
        "next_action": next_action,
        "sensor_posture": {"sensor_fraction": round(sensor_fraction, 6), "sensor_fraction_ceiling": sensor_ceiling, "overrun": sensor_overrun, "principle": "Sense only enough to improve or safely constrain the next action."},
        "actuation_policy": _minimum_sufficient_actuation(),
        "orders": orders,
        "trajectory": trajectory,
        "decision_sha256": None,
    }
    decision["decision_sha256"] = digest(decision)
    return decision


def verify(raw: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(raw)
    if value.get("$schema") != DECISION_SCHEMA:
        raise NavigationError("navigation decision schema is invalid")
    observed = value.get("decision_sha256")
    if not isinstance(observed, str) or len(observed) != 64:
        raise NavigationError("navigation decision digest is invalid")
    candidate = dict(value)
    candidate["decision_sha256"] = None
    if digest(candidate) != observed:
        raise NavigationError("navigation decision changed")
    return value


def sensor_request_is_useful(navigation: Mapping[str, Any], request: Mapping[str, Any]) -> tuple[bool, str]:
    decision = verify(navigation)
    next_action = decision.get("next_action") or {}
    blocker = request.get("blocker_id")
    dependency = request.get("decision_dependency")
    current_action_blocked = request.get("current_action_blocked") is True
    expected_change = request.get("expected_action_change", True)
    if not isinstance(expected_change, bool):
        return False, "sensor request expected_action_change must be boolean"
    if not isinstance(dependency, str) or not dependency.strip():
        return False, "sensor request must name the decision that depends on the answer"
    target = next_action.get("capability_id")
    safety_interrupt = request.get("safety_interrupt") is True
    hazard_evidence = request.get("hazard_evidence")
    if safety_interrupt:
        if isinstance(hazard_evidence, str) and hazard_evidence.strip():
            return True, "concrete safety hazard interrupts the route"
        return False, "safety interrupt requires concrete hazard evidence"
    if current_action_blocked:
        if target is not None and blocker == target:
            return True, "active route action is explicitly blocked by this uncertainty"
        return False, "claimed blocked action is not bound to the active route capability"
    if target is not None and blocker == target and expected_change:
        return True, "sensor question is bound to the active route blocker and can change the next action"
    if next_action.get("work_class") == "evaluation" and expected_change:
        return True, "verification is the active route action"
    return False, "sensor work does not materially change or unblock the active route action"


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("evaluate")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if args.command == "evaluate":
            decision = evaluate(payload)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            decision = verify(payload)
        print(json.dumps({"ok": True, "mode": decision["mode"], "waypoint": decision["waypoint"], "next_action": decision["next_action"], "destination_distance": decision["position"]["destination_distance"]}, sort_keys=True))
        return 0
    except (NavigationError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
