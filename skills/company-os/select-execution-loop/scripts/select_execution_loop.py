#!/usr/bin/env python3
"""Deterministically select a bounded Company OS execution loop."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
CATALOG_PATH = HERE.parent / "assets" / "loop-strategies.json"
REQUEST_KEYS = {"schema", "outcome_id", "task_family", "evidence", "shape", "limits", "requirements"}
EVIDENCE_KEYS = {"acceptance_oracle", "objective_metric", "production_traces", "durable_event_source"}
SHAPE_KEYS = {"parallel_lanes", "uncertainty", "recurrence", "failure_cost", "novelty_need", "code_mutation"}
LIMIT_KEYS = {"max_passes", "no_progress_limit", "max_concurrency", "max_depth", "max_cost_usd"}
REQUIREMENT_KEYS = {"independent_review", "worktree_isolation", "post_run_learning", "approval_boundaries"}
TASK_FAMILIES = {"general", "software_delivery", "product_delivery", "research", "optimization", "creative_exploration", "operations"}


class SelectionError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SelectionError(f"{label} must be an object")
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown:
        raise SelectionError(f"{label} has unknown keys: {', '.join(unknown)}")
    if missing:
        raise SelectionError(f"{label} is missing keys: {', '.join(missing)}")
    return value


def validate_request(raw: Any) -> dict[str, Any]:
    request = _exact_keys(raw, REQUEST_KEYS, "request")
    if request["schema"] != "company-os.loop-selection-request.v1":
        raise SelectionError("unsupported request schema")
    outcome_id = request["outcome_id"]
    if not isinstance(outcome_id, str) or not outcome_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in outcome_id):
        raise SelectionError("outcome_id must be a lower-case slug")
    if request["task_family"] not in TASK_FAMILIES:
        raise SelectionError("task_family is invalid")

    evidence = _exact_keys(request["evidence"], EVIDENCE_KEYS, "evidence")
    shape = _exact_keys(request["shape"], SHAPE_KEYS, "shape")
    limits = _exact_keys(request["limits"], LIMIT_KEYS, "limits")
    requirements = _exact_keys(request["requirements"], REQUIREMENT_KEYS, "requirements")

    for key, value in evidence.items():
        if not isinstance(value, bool):
            raise SelectionError(f"evidence.{key} must be boolean")
    if not evidence["acceptance_oracle"]:
        raise SelectionError("an observable acceptance oracle is required")

    if not isinstance(shape["parallel_lanes"], int) or isinstance(shape["parallel_lanes"], bool) or shape["parallel_lanes"] < 1:
        raise SelectionError("shape.parallel_lanes must be a positive integer")
    if shape["uncertainty"] not in {"low", "medium", "high"}:
        raise SelectionError("shape.uncertainty is invalid")
    if shape["recurrence"] not in {"one_off", "recurring", "event_driven"}:
        raise SelectionError("shape.recurrence is invalid")
    if shape["failure_cost"] not in {"low", "medium", "high"}:
        raise SelectionError("shape.failure_cost is invalid")
    if shape["novelty_need"] not in {"low", "medium", "high"}:
        raise SelectionError("shape.novelty_need is invalid")
    if not isinstance(shape["code_mutation"], bool):
        raise SelectionError("shape.code_mutation must be boolean")

    for key in ("max_passes", "no_progress_limit", "max_concurrency"):
        value = limits[key]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise SelectionError(f"limits.{key} must be a positive integer")
    if not isinstance(limits["max_depth"], int) or isinstance(limits["max_depth"], bool) or limits["max_depth"] < 0:
        raise SelectionError("limits.max_depth must be a non-negative integer")
    cost = limits["max_cost_usd"]
    if cost is not None and (not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0):
        raise SelectionError("limits.max_cost_usd must be non-negative or null")
    if limits["no_progress_limit"] > limits["max_passes"]:
        raise SelectionError("no_progress_limit cannot exceed max_passes")
    if limits["max_concurrency"] > shape["parallel_lanes"]:
        raise SelectionError("max_concurrency cannot exceed declared parallel_lanes")

    for key in ("independent_review", "worktree_isolation", "post_run_learning"):
        if not isinstance(requirements[key], bool):
            raise SelectionError(f"requirements.{key} must be boolean")
    boundaries = requirements["approval_boundaries"]
    if not isinstance(boundaries, list) or any(not isinstance(item, str) or not item.strip() for item in boundaries):
        raise SelectionError("requirements.approval_boundaries must be a string array")
    if len(set(boundaries)) != len(boundaries):
        raise SelectionError("requirements.approval_boundaries contains duplicates")
    if shape["failure_cost"] == "high" and not requirements["independent_review"]:
        raise SelectionError("high failure cost requires independent review")
    if shape["code_mutation"] and shape["parallel_lanes"] > 1 and not requirements["worktree_isolation"]:
        raise SelectionError("parallel code mutation requires worktree isolation")
    if shape["code_mutation"] and shape["parallel_lanes"] > 1 and limits["max_depth"] < 1:
        raise SelectionError("parallel code mutation requires positive recursion depth")
    if shape["recurrence"] == "event_driven" and not evidence["durable_event_source"]:
        raise SelectionError("event-driven work requires a durable event source")
    return request


def load_catalog() -> dict[str, Any]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if catalog.get("$schema") != "company-os.loop-strategy-catalog.v1" or catalog.get("catalog_version") != 1:
        raise SelectionError("loop strategy catalog is invalid")
    strategies = catalog.get("strategies")
    if not isinstance(strategies, list) or not strategies:
        raise SelectionError("loop strategy catalog has no strategies")
    ids = [item.get("id") for item in strategies]
    if any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
        raise SelectionError("loop strategy IDs must be unique strings")
    required_ids = {
        "bounded-evidence-loop", "contract-delivery-loop", "recursive-worktree-loop",
        "bounded-divergent-exploration-loop", "recurring-operations-loop", "event-reaction-loop",
        "trace-optimization-adapter", "apprenticeship-learning-adapter", "durable-event-transport-adapter",
    }
    if set(ids) != required_ids:
        raise SelectionError("loop strategy catalog has an unexpected strategy set")
    strategy_keys = {"id", "kind", "source_ids", "use_when", "cycle", "required_controls", "metrics", "terminal_states"}
    for strategy in strategies:
        if set(strategy) != strategy_keys:
            raise SelectionError(f"strategy has an invalid shape: {strategy.get('id')}")
        if strategy["kind"] not in {"primary", "adapter"}:
            raise SelectionError(f"strategy kind is invalid: {strategy['id']}")
        for key in ("source_ids", "use_when", "cycle", "required_controls", "metrics", "terminal_states"):
            values = strategy[key]
            if not isinstance(values, list) or not values or any(not isinstance(value, str) or not value for value in values):
                raise SelectionError(f"strategy {strategy['id']}.{key} must be a non-empty string array")
    return catalog


def choose_primary(request: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> tuple[str, dict[str, int], list[str]]:
    family = request["task_family"]
    shape = request["shape"]
    scores = {item: 0 for item in (
        "bounded-evidence-loop", "contract-delivery-loop", "recursive-worktree-loop",
        "bounded-divergent-exploration-loop", "recurring-operations-loop", "event-reaction-loop"
    )}
    reasons: list[str] = []
    scores["bounded-evidence-loop"] = 10
    if family in {"software_delivery", "product_delivery"}:
        scores["contract-delivery-loop"] += 35
    if (
        family == "software_delivery"
        and shape["code_mutation"]
        and shape["parallel_lanes"] > 1
        and shape["recurrence"] == "one_off"
    ):
        scores["recursive-worktree-loop"] += 55 + min(shape["parallel_lanes"], 20)
    if (
        family in {"creative_exploration", "product_delivery"}
        and shape["novelty_need"] == "high"
        and shape["recurrence"] == "one_off"
    ):
        scores["bounded-divergent-exploration-loop"] += 60
    if shape["recurrence"] == "recurring":
        scores["recurring-operations-loop"] += 90
    if shape["recurrence"] == "event_driven" and request["evidence"]["durable_event_source"]:
        scores["event-reaction-loop"] += 80
    if shape["failure_cost"] == "high":
        scores["contract-delivery-loop"] += 12
    if shape["uncertainty"] == "high":
        scores["bounded-evidence-loop"] += 8

    selected = sorted(scores, key=lambda item: (-scores[item], item))[0]
    if selected == "recursive-worktree-loop":
        reasons.append("parallel code lanes justify recursively owned isolated worktrees")
    elif selected == "contract-delivery-loop":
        reasons.append("delivery requires confirmed contracts, implementation evidence, and integration review")
    elif selected == "bounded-divergent-exploration-loop":
        reasons.append("high novelty need justifies bounded independent variants and held-out selection")
    elif selected == "recurring-operations-loop":
        reasons.append("recurring work requires due-state, health, and missed-run reconciliation")
    elif selected == "event-reaction-loop":
        reasons.append("event-driven work has a durable source and requires fenced replayable handling")
    else:
        reasons.append("a bounded observe-act-verify loop is the smallest justified strategy")
    if selected not in by_id:
        raise SelectionError(f"catalog is missing selected strategy: {selected}")
    return selected, scores, reasons


def select_plan(request: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    by_id = {item["id"]: item for item in catalog["strategies"]}
    primary_id, scores, reasons = choose_primary(request, by_id)
    adapters: list[str] = []
    if request["evidence"]["production_traces"]:
        adapters.append("trace-optimization-adapter")
    if request["requirements"]["post_run_learning"]:
        adapters.append("apprenticeship-learning-adapter")
    if request["evidence"]["durable_event_source"] and primary_id != "event-reaction-loop":
        adapters.append("durable-event-transport-adapter")
    adapters = adapters[:3]
    selected = [primary_id, *adapters]
    controls = sorted({control for strategy_id in selected for control in by_id[strategy_id]["required_controls"]})
    if request["shape"]["recurrence"] == "recurring":
        controls = sorted(set(controls) | set(by_id["recurring-operations-loop"]["required_controls"]))
        scheduler_reason = "recurring work requires due-state, health, and missed-run reconciliation"
        if scheduler_reason not in reasons:
            reasons.append(scheduler_reason)
    metrics = sorted({metric for strategy_id in selected for metric in by_id[strategy_id]["metrics"]})
    terminals = sorted({state for strategy_id in selected for state in by_id[strategy_id]["terminal_states"]})
    sources = sorted({source for strategy_id in selected for source in by_id[strategy_id]["source_ids"]})
    return {
        "schema": "company-os.loop-plan.v1",
        "activation_state": "planned",
        "outcome_id": request["outcome_id"],
        "request_sha256": sha256(request),
        "catalog_version": catalog["catalog_version"],
        "primary": {"id": primary_id, "score": scores[primary_id], "cycle": by_id[primary_id]["cycle"]},
        "adapters": [{"id": item, "cycle": by_id[item]["cycle"]} for item in adapters],
        "reasons": reasons,
        "limits": request["limits"],
        "approval_boundaries": request["requirements"]["approval_boundaries"],
        "required_controls": controls,
        "metrics": metrics,
        "terminal_states": terminals,
        "source_ids": sources,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-output", type=Path)
    args = parser.parse_args()
    try:
        request = validate_request(json.loads(args.request.read_text(encoding="utf-8")))
        plan = select_plan(request, load_catalog())
        payload = canonical_bytes(plan)
        if args.verify_output:
            if args.verify_output.read_bytes() != payload:
                raise SelectionError("loop plan does not match deterministic selection")
            print(json.dumps({"ok": True, "plan_sha256": sha256(plan)}, sort_keys=True))
            return 0
        if args.output:
            args.output.write_bytes(payload)
        else:
            sys.stdout.buffer.write(payload)
        return 0
    except (OSError, json.JSONDecodeError, SelectionError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
