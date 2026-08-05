#!/usr/bin/env python3
"""Validate a Luna Execution Fabric dispatch manifest."""

from __future__ import annotations

import argparse
import json
import math
import unicodedata
import sys
from pathlib import Path
from typing import Any


DEFAULTS = {
    "max_depth": 2,
    "max_worker_retries": 1,
    "max_manager_rework_rounds": 2,
}
CAPACITY_FIELDS = ("max_managers", "max_workers_per_manager", "max_total_workers")
# These protect the local validator and control plane from accidental manifest
# explosions. They are safety ceilings, not a prescribed organization shape.
SAFETY_CEILINGS = {
    "max_managers": 256,
    "max_workers_per_manager": 64,
    "max_total_workers": 4096,
}
LEGACY_HARD_CAPS = {
    "max_managers": 2,
    "max_workers_per_manager": 3,
    "max_total_workers": 6,
}
BUDGET_FIELDS = {"time_minutes", "token_limit", "cost_usd", "max_concurrency", "max_retries"}
PHASES = [
    "charter",
    "discovery",
    "design",
    "execution",
    "verification",
    "integration",
]
CONTRACT_FIELDS = {
    "north_star",
    "user_value",
    "rationale",
    "architecture",
    "roadmap",
    "dependencies",
    "non_goals",
    "constraints",
}
OUTCOME_CONTEXT_FIELDS = {
    "program_version",
    "north_star",
    "user_value",
    "program_outcome",
    "manager_outcome",
    "roadmap_position",
    "dependencies",
    "non_goals",
    "constraints",
}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _list_of_nonempty(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_nonempty(v) for v in value)


def _finite_nonnegative(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def canonical_scope(value: Any) -> str:
    """Return a lexical project-relative scope; never consult the filesystem."""
    if (
        not _nonempty(value) or value.startswith("/") or "\\" in value
        or (len(value) >= 3 and value[0].isalpha() and value[1:3] == ":/")
    ):
        raise ValueError("scope must be a non-empty relative slash path")
    if value != value.strip() or "//" in value:
        raise ValueError("scope must not use whitespace aliases or empty segments")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("scope must not contain empty, dot, or traversal segments")
    return unicodedata.normalize("NFC", "/".join(parts)).casefold()


def _contains(parent: str, child: str) -> bool:
    return child == parent or child.startswith(parent + "/")


def _validate_budget(value: Any, label: str, errors: list[str], parent: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    if set(value) != BUDGET_FIELDS:
        errors.append(f"{label} must define exactly {sorted(BUDGET_FIELDS)}")
    for field in ("time_minutes", "cost_usd"):
        if not _finite_nonnegative(value.get(field)):
            errors.append(f"{label}.{field} must be a finite non-negative number")
    if not _nonnegative_int(value.get("token_limit")):
        errors.append(f"{label}.token_limit must be a non-negative integer")
    for field in ("max_concurrency", "max_retries"):
        if not _nonnegative_int(value.get(field)):
            errors.append(f"{label}.{field} must be a non-negative integer")
    if parent:
        for field in BUDGET_FIELDS:
            if field in value and field in parent and _budget_value_valid(field, value[field]) and _budget_value_valid(field, parent[field]) and value[field] > parent[field]:
                errors.append(f"{label}.{field} may not exceed its parent budget")
    return value


def _budget_value_valid(field: str, value: Any) -> bool:
    return _nonnegative_int(value) if field in {"token_limit", "max_concurrency", "max_retries"} else _finite_nonnegative(value)


def validate(manifest: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not _nonempty(manifest.get("program_id")):
        errors.append("program_id must be a non-empty string")
    program_version = manifest.get("program_version")
    if (
        not isinstance(program_version, int)
        or isinstance(program_version, bool)
        or program_version < 1
    ):
        errors.append("program_version must be a positive integer")
    if not _nonempty(manifest.get("outcome")):
        errors.append("outcome must be a non-empty string")
    if not _list_of_nonempty(manifest.get("acceptance")):
        errors.append("acceptance must contain at least one non-empty check")

    contract = manifest.get("program_contract")
    if not isinstance(contract, dict):
        errors.append("program_contract must be an object")
        contract = {}
    for field in sorted(CONTRACT_FIELDS):
        if field in {"roadmap", "dependencies", "non_goals", "constraints"}:
            if not _list_of_nonempty(contract.get(field)):
                errors.append(f"program_contract.{field} must contain a value")
        elif not _nonempty(contract.get(field)):
            errors.append(f"program_contract.{field} must be non-empty")
    if contract.get("roadmap") != PHASES:
        errors.append(
            "program_contract.roadmap must use the six ordered fabric phases"
        )
    program_budget = _validate_budget(manifest.get("budget"), "budget", errors)

    limits: dict[str, int] = {}
    for key in CAPACITY_FIELDS:
        value = manifest.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            errors.append(f"{key} must be an explicitly sized positive integer")
            value = 1
        elif value > SAFETY_CEILINGS[key]:
            errors.append(
                f"{key} exceeds the control-plane safety ceiling of {SAFETY_CEILINGS[key]}"
            )
        limits[key] = value
    for key, default in DEFAULTS.items():
        value = manifest.get(key, default)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            errors.append(f"{key} must be a positive integer")
            value = default
        limits[key] = value

    if limits["max_depth"] != 2:
        errors.append("max_depth must be exactly 2: master -> manager -> worker")
    declared_managers = manifest.get("managers")
    derived_manager_concurrency = (
        len(declared_managers) if isinstance(declared_managers, list) and declared_managers else 1
    )
    manager_concurrency = manifest.get(
        "max_manager_concurrency", derived_manager_concurrency
    )
    topology_mode = manifest.get("topology_mode")
    if topology_mode not in {None, "elastic_work_graph"}:
        errors.append("topology_mode must be 'elastic_work_graph' when provided")
    if topology_mode is None:
        for key, cap in LEGACY_HARD_CAPS.items():
            if limits[key] > cap:
                errors.append(f"{key} cannot exceed the legacy Phase 1 hard cap of {cap}")
        warnings.append(
            "legacy fixed topology is active; new programs should declare "
            "topology_mode='elastic_work_graph'"
        )
    if (
        not isinstance(manager_concurrency, int)
        or isinstance(manager_concurrency, bool)
        or manager_concurrency < 1
    ):
        errors.append("max_manager_concurrency must be a positive integer when provided")
        manager_concurrency = 1
    elif manager_concurrency > limits["max_managers"]:
        errors.append("max_manager_concurrency may not exceed max_managers")
    if (
        program_budget
        and _nonnegative_int(program_budget.get("max_concurrency"))
        and program_budget["max_concurrency"] > limits["max_total_workers"]
    ):
        errors.append("budget.max_concurrency may not exceed max_total_workers")
    if (
        program_budget
        and _nonnegative_int(program_budget.get("max_retries"))
        and program_budget["max_retries"] > limits["max_worker_retries"]
    ):
        errors.append("budget.max_retries may not exceed max_worker_retries")
    if limits["max_worker_retries"] > 1:
        errors.append("max_worker_retries cannot exceed 1")
    if limits["max_manager_rework_rounds"] > 2:
        errors.append("max_manager_rework_rounds cannot exceed 2")

    share = manifest.get("luna_token_share_target", 0.75)
    if not isinstance(share, (int, float)) or isinstance(share, bool):
        errors.append("luna_token_share_target must be numeric")
    elif not 0.70 <= float(share) <= 0.85:
        errors.append("luna_token_share_target must be between 0.70 and 0.85")

    if manifest.get("external_effects_allowed", False) is not False:
        errors.append("external_effects_allowed must remain false in the manifest")

    managers = manifest.get("managers")
    if not isinstance(managers, list) or not managers:
        errors.append("managers must contain at least one manager")
        managers = []
    if len(managers) > limits["max_managers"]:
        errors.append("manager count exceeds max_managers")

    manager_ids: set[str] = set()
    worker_ids: set[str] = set()
    manager_write_scopes: dict[str, str] = {}
    manager_budgets: list[dict[str, Any]] = []
    total_workers = 0

    for manager_index, manager in enumerate(managers):
        prefix = f"managers[{manager_index}]"
        if not isinstance(manager, dict):
            errors.append(f"{prefix} must be an object")
            continue
        manager_id = manager.get("id")
        if not _nonempty(manager_id):
            errors.append(f"{prefix}.id must be non-empty")
            manager_id = prefix
        elif manager_id in manager_ids:
            errors.append(f"duplicate manager id: {manager_id}")
        manager_ids.add(str(manager_id))

        if manager.get("model") != "gpt-5.6-sol":
            errors.append(f"{prefix}.model must be gpt-5.6-sol")
        if not _nonempty(manager.get("outcome")):
            errors.append(f"{prefix}.outcome must be non-empty")
        if not _list_of_nonempty(manager.get("acceptance")):
            errors.append(f"{prefix}.acceptance must contain a check")
        if manager.get("phase_ids") != PHASES:
            errors.append(f"{prefix}.phase_ids must use the six ordered phases")
        manager_budget = _validate_budget(manager.get("budget"), f"{prefix}.budget", errors, program_budget)
        manager_budgets.append(manager_budget)
        if (
            manager_budget
            and _nonnegative_int(manager_budget.get("max_concurrency"))
            and manager_budget["max_concurrency"] > limits["max_workers_per_manager"]
        ):
            errors.append(f"{prefix}.budget.max_concurrency may not exceed max_workers_per_manager")
        if (
            manager_budget
            and _nonnegative_int(manager_budget.get("max_retries"))
            and manager_budget["max_retries"] > limits["max_worker_retries"]
        ):
            errors.append(f"{prefix}.budget.max_retries may not exceed max_worker_retries")

        write_scope = manager.get("write_scope", [])
        if not isinstance(write_scope, list) or not write_scope:
            errors.append(f"{prefix}.write_scope must be a list of non-empty strings")
            write_scope = []
        canonical_manager_scopes: list[str] = []
        for scope in write_scope:
            try:
                scope = canonical_scope(scope)
            except ValueError as exc:
                errors.append(f"{prefix}.write_scope: {exc}")
                continue
            if any(_contains(other, scope) or _contains(scope, other) for other in canonical_manager_scopes):
                errors.append(f"{prefix}.write_scope contains duplicate or parent/child collision: {scope}")
            if any(_contains(other, scope) or _contains(scope, other) for other in manager_write_scopes):
                errors.append(
                    f"manager write scope collision: {scope} overlaps another manager and {manager_id}"
                )
            manager_write_scopes[scope] = str(manager_id)
            canonical_manager_scopes.append(scope)

        workers = manager.get("workers")
        if not isinstance(workers, list) or not workers:
            errors.append(f"{prefix}.workers must contain at least one worker")
            workers = []
        if len(workers) > limits["max_workers_per_manager"]:
            errors.append(f"{prefix} exceeds max_workers_per_manager")
        total_workers += len(workers)

        worker_write_scopes: dict[str, str] = {}
        worker_budgets: list[dict[str, Any]] = []
        for worker_index, worker in enumerate(workers):
            wp = f"{prefix}.workers[{worker_index}]"
            if not isinstance(worker, dict):
                errors.append(f"{wp} must be an object")
                continue
            worker_id = worker.get("id")
            if not _nonempty(worker_id):
                errors.append(f"{wp}.id must be non-empty")
                worker_id = wp
            elif worker_id in worker_ids:
                errors.append(f"duplicate worker id: {worker_id}")
            worker_ids.add(str(worker_id))

            if worker.get("model") != "gpt-5.6-luna":
                errors.append(f"{wp}.model must be gpt-5.6-luna")
            if not _nonempty(worker.get("task")):
                errors.append(f"{wp}.task must be non-empty")
            if not _list_of_nonempty(worker.get("acceptance")):
                errors.append(f"{wp}.acceptance must contain a check")
            if not _nonempty(worker.get("stop_condition")):
                errors.append(f"{wp}.stop_condition must be non-empty")
            if worker.get("risk") not in {"low", "medium", "high", "critical"}:
                errors.append(f"{wp}.risk must be low, medium, high, or critical")
            if worker.get("may_delegate", False):
                errors.append(f"{wp} may not delegate")
            if worker.get("external_effects", False):
                errors.append(f"{wp} may not perform external effects")
            worker_budget = _validate_budget(worker.get("budget"), f"{wp}.budget", errors, manager_budget)
            worker_budgets.append(worker_budget)
            if worker_budget.get("max_concurrency") != 1:
                errors.append(f"{wp}.budget.max_concurrency must be exactly 1")

            outcome_context = worker.get("outcome_context")
            if not isinstance(outcome_context, dict):
                errors.append(f"{wp}.outcome_context must be an object")
                outcome_context = {}
            for field in sorted(OUTCOME_CONTEXT_FIELDS):
                value = outcome_context.get(field)
                if field == "program_version":
                    if value != program_version:
                        errors.append(
                            f"{wp}.outcome_context.program_version must match the program"
                        )
                elif field in {"dependencies", "non_goals", "constraints"}:
                    if not _list_of_nonempty(value):
                        errors.append(
                            f"{wp}.outcome_context.{field} must contain a value"
                        )
                elif not _nonempty(value):
                    errors.append(f"{wp}.outcome_context.{field} must be non-empty")
            if outcome_context.get("program_outcome") != manifest.get("outcome"):
                errors.append(f"{wp} must receive the complete program outcome")
            if outcome_context.get("manager_outcome") != manager.get("outcome"):
                errors.append(f"{wp} must receive the owning manager outcome")
            if outcome_context.get("roadmap_position") not in PHASES:
                errors.append(f"{wp}.outcome_context.roadmap_position is invalid")

            scopes = worker.get("write_scope", [])
            if not isinstance(scopes, list):
                errors.append(f"{wp}.write_scope must be a list of non-empty strings")
                scopes = []
            for scope in scopes:
                try:
                    scope = canonical_scope(scope)
                except ValueError as exc:
                    errors.append(f"{wp}.write_scope: {exc}")
                    continue
                if not any(_contains(parent, scope) for parent in canonical_manager_scopes):
                    errors.append(f"{wp} write scope {scope} is outside manager ownership")
                if any(_contains(other, scope) or _contains(scope, other) for other in worker_write_scopes):
                    errors.append(
                        f"concurrent worker write scope collision: {scope} overlaps another worker and {worker_id}"
                    )
                worker_write_scopes[scope] = str(worker_id)

            if worker.get("risk") in {"high", "critical"}:
                warnings.append(f"{wp} requires manager, reviewer, and master verification")

        for field in ("time_minutes", "token_limit", "cost_usd"):
            if (
                field in manager_budget
                and all(field in budget for budget in worker_budgets)
                and _budget_value_valid(field, manager_budget[field])
                and all(_budget_value_valid(field, budget[field]) for budget in worker_budgets)
                and sum(budget[field] for budget in worker_budgets) > manager_budget[field]
            ):
                errors.append(f"{prefix} worker {field} allocations oversubscribe the manager budget")

    if total_workers > limits["max_total_workers"]:
        errors.append("total worker count exceeds max_total_workers")
    for field in ("time_minutes", "token_limit", "cost_usd"):
        if (
            field in program_budget
            and all(field in budget for budget in manager_budgets)
            and _budget_value_valid(field, program_budget[field])
            and all(_budget_value_valid(field, budget[field]) for budget in manager_budgets)
            and sum(budget[field] for budget in manager_budgets) > program_budget[field]
        ):
            errors.append(f"manager {field} allocations oversubscribe the program budget")
    if total_workers > 0 and len(managers) > 0:
        average = total_workers / len(managers)
        if average < 1.5:
            warnings.append("manager fan-out is low; verify the hierarchy saves tokens")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "managers": len(managers),
            "workers": total_workers,
            "declared_manager_concurrency": manager_concurrency,
            "declared_worker_concurrency": program_budget.get("max_concurrency"),
            "luna_token_share_target": share,
        },
    }


def _self_test() -> int:
    valid_manifest = {
        "program_id": "self-test",
        "program_version": 1,
        "outcome": "Produce one accepted artifact",
        "acceptance": ["Manager verifies artifact"],
        "program_contract": {
            "north_star": "Efficient verified execution",
            "user_value": "Accepted work with less Sol usage",
            "rationale": "Exercise the fabric contract",
            "architecture": "Sol managers supervise Luna workers",
            "roadmap": PHASES,
            "dependencies": ["Local toolchain"],
            "non_goals": ["Production deployment"],
            "constraints": ["No external effects"],
        },
        "max_managers": 2,
        "max_workers_per_manager": 3,
        "max_total_workers": 6,
        "max_depth": 2,
        "max_worker_retries": 1,
        "max_manager_rework_rounds": 2,
        "luna_token_share_target": 0.75,
        "external_effects_allowed": False,
        "budget": {"time_minutes": 60, "token_limit": 10000, "cost_usd": 10.0, "max_concurrency": 6, "max_retries": 1},
        "managers": [
            {
                "id": "manager-a",
                "model": "gpt-5.6-sol",
                "outcome": "Bounded outcome",
                "acceptance": ["Run exact check"],
                "phase_ids": PHASES,
                "write_scope": ["src/a"],
                "budget": {"time_minutes": 30, "token_limit": 5000, "cost_usd": 5.0, "max_concurrency": 3, "max_retries": 1},
                "workers": [
                    {
                        "id": "worker-a1",
                        "model": "gpt-5.6-luna",
                        "task": "Implement bounded change",
                        "acceptance": ["Focused test passes"],
                        "write_scope": ["src/a"],
                        "risk": "medium",
                        "budget": {"time_minutes": 15, "token_limit": 2500, "cost_usd": 2.5, "max_concurrency": 1, "max_retries": 1},
                        "outcome_context": {
                            "program_version": 1,
                            "north_star": "Efficient verified execution",
                            "user_value": "Accepted work with less Sol usage",
                            "program_outcome": "Produce one accepted artifact",
                            "manager_outcome": "Bounded outcome",
                            "roadmap_position": "execution",
                            "dependencies": ["Local toolchain"],
                            "non_goals": ["Production deployment"],
                            "constraints": ["No external effects"],
                        },
                        "stop_condition": "Test passes or blocker is reported",
                    }
                ],
            }
        ],
    }
    valid_result = validate(valid_manifest)
    if not valid_result["valid"]:
        print(json.dumps(valid_result, indent=2))
        return 1

    invalid_manifest = json.loads(json.dumps(valid_manifest))
    invalid_manifest["managers"][0]["workers"][0]["model"] = "gpt-5.6-sol"
    invalid_manifest["managers"][0]["workers"][0]["may_delegate"] = True
    invalid_manifest["managers"][0]["workers"][0]["outcome_context"][
        "program_version"
    ] = 2
    invalid_result = validate(invalid_manifest)
    expected = {
        "managers[0].workers[0].model must be gpt-5.6-luna",
        "managers[0].workers[0] may not delegate",
        "managers[0].workers[0].outcome_context.program_version must match the program",
    }
    if invalid_result["valid"] or not expected.issubset(set(invalid_result["errors"])):
        print(json.dumps(invalid_result, indent=2))
        return 1

    # A large program may declare many independently owned outcomes while the
    # scheduler keeps only a bounded subset active. Capacity is not concurrency.
    large_manifest = json.loads(json.dumps(valid_manifest))
    large_manifest.update(
        {
            "program_id": "large-self-test",
            "topology_mode": "elastic_work_graph",
            "max_managers": 30,
            "max_manager_concurrency": 6,
            "max_workers_per_manager": 10,
            "max_total_workers": 300,
            "budget": {
                "time_minutes": 3000,
                "token_limit": 300000,
                "cost_usd": 300.0,
                "max_concurrency": 60,
                "max_retries": 1,
            },
        }
    )
    large_manifest["managers"] = []
    for manager_number in range(30):
        manager = json.loads(json.dumps(valid_manifest["managers"][0]))
        manager["id"] = f"manager-{manager_number:02d}"
        manager["outcome"] = f"Deliver outcome {manager_number:02d}"
        manager["write_scope"] = [f"work/manager-{manager_number:02d}"]
        manager["budget"] = {
            "time_minutes": 100,
            "token_limit": 10000,
            "cost_usd": 10.0,
            "max_concurrency": 2,
            "max_retries": 1,
        }
        manager["workers"] = []
        for worker_number in range(10):
            worker = json.loads(json.dumps(valid_manifest["managers"][0]["workers"][0]))
            worker["id"] = f"worker-{manager_number:02d}-{worker_number:02d}"
            worker["task"] = f"Deliver task {manager_number:02d}-{worker_number:02d}"
            worker["write_scope"] = [
                f"work/manager-{manager_number:02d}/worker-{worker_number:02d}"
            ]
            worker["budget"] = {
                "time_minutes": 10,
                "token_limit": 1000,
                "cost_usd": 1.0,
                "max_concurrency": 1,
                "max_retries": 1,
            }
            worker["outcome_context"]["manager_outcome"] = manager["outcome"]
            manager["workers"].append(worker)
        large_manifest["managers"].append(manager)
    large_result = validate(large_manifest)
    if not large_result["valid"] or large_result["summary"] != {
        "managers": 30,
        "workers": 300,
        "declared_manager_concurrency": 6,
        "declared_worker_concurrency": 60,
        "luna_token_share_target": 0.75,
    }:
        print(json.dumps(large_result, indent=2))
        return 1

    oversized_manifest = json.loads(json.dumps(large_manifest))
    oversized_manifest["max_managers"] = 257
    oversized_result = validate(oversized_manifest)
    if oversized_result["valid"] or not any(
        "control-plane safety ceiling" in error
        for error in oversized_result["errors"]
    ):
        print(json.dumps(oversized_result, indent=2))
        return 1

    print("self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()
    if args.manifest is None:
        parser.error("manifest is required unless --self-test is used")
    try:
        payload = json.loads(args.manifest.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2))
        return 2
    if not isinstance(payload, dict):
        print(json.dumps({"valid": False, "errors": ["manifest must be an object"]}, indent=2))
        return 2
    result = validate(payload)
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
