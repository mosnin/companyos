#!/usr/bin/env python3
"""Mission-level executive governor for reality-first Company OS execution."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

INPUT_SCHEMA = "company-os.outcome-executive-input.v1"
DECISION_SCHEMA = "company-os.outcome-executive-decision.v1"
CAPABILITY_STATES = {"missing": 0, "partial": 1, "runnable": 2, "connected": 3, "verified": 4}
WORK_CLASSES = (
    "research",
    "architecture",
    "governance",
    "implementation",
    "integration",
    "runtime",
    "repair",
    "evaluation",
    "documentation",
    "packaging",
    "checkpoint",
)
EXECUTION_CLASSES = {"implementation", "integration", "runtime", "repair"}


class GovernorError(ValueError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise GovernorError(f"{label} must be a nonempty string")
    return value.strip()


def _fraction(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise GovernorError(f"{label} must be finite")
    current = float(value)
    if current < 0.0 or current > 1.0:
        raise GovernorError(f"{label} must be between 0 and 1")
    return current


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise GovernorError(f"{label} must be boolean")
    return value


def _reality_level(signals: Mapping[str, Any]) -> int:
    names = (
        "internal_primitives",
        "runnable_capability",
        "connected_vertical_slice",
        "user_usable",
        "independent_acceptance",
    )
    observed = [_bool(signals.get(name, False), f"reality.{name}") for name in names]
    # Higher reality is not allowed to float above a missing lower layer.
    for index in range(1, len(observed)):
        if observed[index] and not observed[index - 1]:
            raise GovernorError(f"reality.{names[index]} requires reality.{names[index - 1]}")
    level = 0
    for index, present in enumerate(observed, 1):
        if present:
            level = index
    return level


def _capabilities(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise GovernorError("required_capabilities must be a nonempty list")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise GovernorError(f"required_capabilities[{index}] must be an object")
        capability_id = _text(item.get("capability_id"), f"required_capabilities[{index}].capability_id")
        if capability_id in seen:
            raise GovernorError(f"duplicate capability_id {capability_id}")
        seen.add(capability_id)
        state = item.get("state")
        if state not in CAPABILITY_STATES:
            raise GovernorError(f"{capability_id}.state is invalid")
        critical = item.get("critical", True)
        if not isinstance(critical, bool):
            raise GovernorError(f"{capability_id}.critical must be boolean")
        priority = item.get("priority", 50)
        if not isinstance(priority, int) or isinstance(priority, bool) or priority < 0 or priority > 100:
            raise GovernorError(f"{capability_id}.priority must be 0..100")
        existing = item.get("existing_implementation")
        if existing is not None:
            existing = _text(existing, f"{capability_id}.existing_implementation")
        result.append(
            {
                "capability_id": capability_id,
                "state": state,
                "critical": critical,
                "priority": priority,
                "existing_implementation": existing,
            }
        )
    return result


def _allocation(raw: Any) -> dict[str, float]:
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise GovernorError("allocation must be an object")
    unknown = set(raw) - set(WORK_CLASSES)
    if unknown:
        raise GovernorError(f"allocation has unknown work classes: {sorted(unknown)}")
    result = {name: _fraction(raw.get(name, 0.0), f"allocation.{name}") for name in WORK_CLASSES}
    total = sum(result.values())
    if total <= 0:
        return result
    return {name: value / total for name, value in result.items()}


def _dominant_bottleneck(capabilities: list[dict[str, Any]]) -> dict[str, Any] | None:
    unresolved = [item for item in capabilities if item["state"] != "verified"]
    if not unresolved:
        return None
    # Critical first, then closest-to-nothing first, then explicit priority.
    unresolved.sort(
        key=lambda item: (
            0 if item["critical"] else 1,
            CAPABILITY_STATES[item["state"]],
            -item["priority"],
            item["capability_id"],
        )
    )
    return unresolved[0]


def evaluate(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("$schema") != INPUT_SCHEMA:
        raise GovernorError("input schema is invalid")
    objective_id = _text(payload.get("objective_id"), "objective_id")
    objective = _text(payload.get("objective"), "objective")
    budget_fraction = _fraction(payload.get("budget_fraction_consumed", 0.0), "budget_fraction_consumed")
    first_artifact_fraction = _fraction(
        payload.get("first_artifact_budget_fraction", 0.25), "first_artifact_budget_fraction"
    )
    if first_artifact_fraction <= 0.0:
        raise GovernorError("first_artifact_budget_fraction must be positive")
    reality_raw = payload.get("reality", {})
    if not isinstance(reality_raw, Mapping):
        raise GovernorError("reality must be an object")
    reality_level = _reality_level(reality_raw)
    capabilities = _capabilities(payload.get("required_capabilities"))
    allocation = _allocation(payload.get("allocation"))
    bottleneck = _dominant_bottleneck(capabilities)

    first_reality_incident = budget_fraction >= 0.25 and reality_level < 3
    # Planning meter: the metered resource is everything spent before the first
    # real mutation. Past the first-artifact share of the budget with NOTHING
    # materialized (reality below R1), planning has consumed its allowance, and
    # every non-execution work class is paused rather than merely discouraged.
    planning_overrun = budget_fraction >= first_artifact_fraction and reality_level < 1
    if reality_level >= 5:
        mode = "accepted"
    elif budget_fraction >= 0.88:
        mode = "reality_closure"
    elif budget_fraction >= 0.70 and reality_level < 4:
        mode = "critical_path"
    elif first_reality_incident or (budget_fraction >= 0.40 and reality_level < 3):
        mode = "compression"
    else:
        mode = "normal"

    total = sum(allocation.values())
    if total:
        execution_ratio = sum(allocation[name] for name in EXECUTION_CLASSES)
        governance_tax = allocation["governance"]
        research_tax = allocation["research"]
        documentation_tax = allocation["documentation"]
    else:
        execution_ratio = governance_tax = research_tax = documentation_tax = 0.0

    allocation_incident = reality_level < 3 and budget_fraction >= 0.10 and total > 0 and execution_ratio < 0.50
    existing_capability_preference = bool(
        bottleneck and bottleneck.get("existing_implementation") and bottleneck["state"] in {"missing", "partial"}
    )

    if mode == "accepted":
        allowed = ["checkpoint", "documentation", "packaging"]
        paused: list[str] = []
    elif mode == "reality_closure":
        allowed = ["integration", "runtime", "repair", "evaluation", "packaging", "checkpoint"]
        paused = [name for name in WORK_CLASSES if name not in allowed]
    elif mode == "critical_path":
        allowed = ["implementation", "integration", "runtime", "repair", "evaluation", "packaging", "checkpoint"]
        paused = ["research", "architecture", "governance", "documentation"]
    elif mode == "compression" or first_reality_incident:
        allowed = ["implementation", "integration", "runtime", "repair", "evaluation", "checkpoint", "packaging"]
        paused = ["documentation"]
        if reality_level < 2:
            paused.extend(["governance"])
        if planning_overrun:
            # Enforcement, not doctrine: research and architecture join the
            # paused set, so admit_work rejects further planning fail-closed
            # until at least one internal primitive actually exists.
            paused.extend(["research", "architecture", "governance"])
        paused = sorted(set(paused))
        allowed = [name for name in allowed if name not in set(paused)]
    else:
        allowed = list(WORK_CLASSES)
        paused = []

    orders: list[str] = []
    if mode != "accepted":
        if planning_overrun:
            orders.append(
                "Planning allowance is exhausted: the first-artifact budget share passed with nothing materialized. "
                "Research, architecture, and governance admissions are paused fail-closed until one real internal primitive exists."
            )
        if bottleneck:
            orders.append(f"Make {bottleneck['capability_id']} the global execution bottleneck until observable progress changes its state.")
        if reality_level < 3:
            orders.append("Materialize and run the smallest connected end-to-end artifact before expanding architecture, research, or governance.")
        if first_reality_incident:
            orders.append("Execution incident: pause broad research/speculation and redirect managers to implementation, integration, runtime, and repair.")
        if allocation_incident:
            orders.append("Raise direct product execution above half of active mission allocation until R3 exists.")
        if existing_capability_preference and bottleneck:
            orders.append(
                f"Integrate and exercise supplied capability {bottleneck['existing_implementation']} before authorizing a replacement implementation."
            )
        if mode == "reality_closure":
            orders.append("Do not start new features or broad research. Integrate, run, fix, verify, package, and checkpoint the strongest real outcome now.")
        elif mode == "critical_path":
            orders.append("Pause noncritical lanes. Spend remaining resources only on blockers between current reality and a fresh user-usable outcome.")
        orders.append("Checkpoint tested product bytes promptly; governance receipts are not a substitute for durable product state.")

    decision = {
        "$schema": DECISION_SCHEMA,
        "objective_id": objective_id,
        "objective": objective,
        "budget_fraction_consumed": budget_fraction,
        "reality_level": f"R{reality_level}",
        "reality_level_index": reality_level,
        "mode": mode,
        "first_reality_incident": first_reality_incident,
        "planning_overrun": planning_overrun,
        "first_artifact_budget_fraction": first_artifact_fraction,
        "allocation_incident": allocation_incident,
        "dominant_bottleneck": bottleneck,
        "existing_capability_preference": existing_capability_preference,
        "product_execution_ratio": round(execution_ratio, 6),
        "governance_tax": round(governance_tax, 6),
        "research_tax": round(research_tax, 6),
        "documentation_tax": round(documentation_tax, 6),
        "allowed_work_classes": allowed,
        "paused_work_classes": paused,
        "manager_orders": orders,
        "required_capabilities": capabilities,
        "decision_sha256": None,
    }
    decision["decision_sha256"] = digest(decision)
    return decision


def verify(decision: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(decision)
    if value.get("$schema") != DECISION_SCHEMA:
        raise GovernorError("decision schema is invalid")
    observed = value.get("decision_sha256")
    if not isinstance(observed, str) or len(observed) != 64:
        raise GovernorError("decision digest is invalid")
    candidate = dict(value)
    candidate["decision_sha256"] = None
    if digest(candidate) != observed:
        raise GovernorError("decision digest changed")
    return value


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
            result = evaluate(payload)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            result = verify(payload)
        print(json.dumps({"ok": True, "decision_sha256": result["decision_sha256"], "mode": result["mode"], "reality_level": result["reality_level"]}, sort_keys=True))
        return 0
    except (GovernorError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
