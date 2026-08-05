#!/usr/bin/env python3
"""Plan feature-off desired/observed reconciliation for a federated kernel.

The planner performs no task, provider, network, scheduler, or database action.
It converts a verified kernel, a bounded admission request, and returned native
task observations into a deterministic action plan for an external controller.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


SKILL_ROOT = Path(__file__).resolve().parents[1]
COMPANY_OS_ROOT = SKILL_ROOT.parent
KERNEL_COMPILER_PATH = SKILL_ROOT / "scripts" / "compile_federated_kernel.py"
NATIVE_RUNTIME_PATH = (
    COMPANY_OS_ROOT / "elastic-company-os" / "scripts" / "native_task_runtime.py"
)

REQUEST_SCHEMA = "company-os.federated-reconciliation-request.v1"
SNAPSHOT_SCHEMA = "company-os.federated-observed-state.v1"
PLAN_SCHEMA = "company-os.federated-reconciliation-plan.v1"
ROLE_STATUSES = {"confirmed", "refuted", "inconclusive"}
MODEL_REASONS = {"xhigh", "max"}


class ReconciliationError(ValueError):
    """A closed reconciliation-contract failure."""


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReconciliationError(f"cannot load required module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


KERNEL = load_module("company_os_federated_kernel_compiler", KERNEL_COMPILER_PATH)
NATIVE = load_module("company_os_native_task_runtime", NATIVE_RUNTIME_PATH)


def canonical_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ReconciliationError("value is not canonical JSON") from exc


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_canonical_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReconciliationError(f"{label} must be a regular non-symlink file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReconciliationError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ReconciliationError(f"{label} must be a JSON object")
    if raw != canonical_bytes(value):
        raise ReconciliationError(f"{label} bytes are not canonical JSON")
    return value


def exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ReconciliationError(
            f"{label} keys differ: missing={sorted(expected - actual)} "
            f"extra={sorted(actual - expected)}"
        )


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReconciliationError(f"{label} must be non-empty trimmed text")
    return value


def integer(value: Any, minimum: int, maximum: int, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ReconciliationError(f"{label} must be an integer from {minimum} to {maximum}")
    return value


def verify_kernel_document(path: Path) -> dict[str, Any]:
    actual = read_canonical_object(path, "compiled kernel")
    source_request = actual.get("source_request")
    if not isinstance(source_request, dict):
        raise ReconciliationError("compiled kernel lacks a valid source request")
    request = KERNEL.validate_request(source_request)
    mechanisms, _sources, mechanism_digest, source_digest = KERNEL.validate_mechanisms()
    expected = KERNEL.compile_kernel(request, mechanisms, mechanism_digest, source_digest)
    if actual != expected:
        raise ReconciliationError("compiled kernel does not reproduce from current registries")
    return actual


def validate_budget(value: Any, label: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ReconciliationError(f"{label} must be an object")
    exact_keys(
        value,
        {"max_tokens", "max_cost_microusd", "max_wall_seconds"},
        label,
    )
    return {
        "max_tokens": integer(value["max_tokens"], 1, 10**12, f"{label}.max_tokens"),
        "max_cost_microusd": integer(
            value["max_cost_microusd"], 0, 10**15, f"{label}.max_cost_microusd"
        ),
        "max_wall_seconds": integer(
            value["max_wall_seconds"], 1, 31_536_000, f"{label}.max_wall_seconds"
        ),
    }


def validate_role_readback(
    value: Any,
    *,
    requested_model: str,
    requested_reasoning: str,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ReconciliationError(f"{label} must be an object")
    exact_keys(
        value,
        {"status", "observed_model", "observed_reasoning", "source", "reason"},
        label,
    )
    status = value["status"]
    if status not in ROLE_STATUSES:
        raise ReconciliationError(f"{label}.status is unsupported")
    observed_model = value["observed_model"]
    observed_reasoning = value["observed_reasoning"]
    source = value["source"]
    reason = value["reason"]
    if status == "inconclusive":
        if observed_model is not None or observed_reasoning is not None:
            raise ReconciliationError(f"{label} inconclusive readback cannot invent observations")
        if source != "unavailable":
            raise ReconciliationError(f"{label} inconclusive readback source must be unavailable")
        reason = text(reason, f"{label}.reason")
    else:
        observed_model = text(observed_model, f"{label}.observed_model")
        observed_reasoning = text(observed_reasoning, f"{label}.observed_reasoning")
        if source != "host_observation" or reason is not None:
            raise ReconciliationError(f"{label} observed readback shape is invalid")
        matches = (
            observed_model == requested_model
            and observed_reasoning == requested_reasoning
        )
        if status == "confirmed" and not matches:
            raise ReconciliationError(f"{label} confirmed readback conflicts with requested role")
        if status == "refuted" and matches:
            raise ReconciliationError(f"{label} refuted readback does not contain drift")
    return {
        "status": status,
        "observed_model": observed_model,
        "observed_reasoning": observed_reasoning,
        "source": source,
        "reason": reason,
    }


def manager_spec(kernel: Mapping[str, Any], cell: Mapping[str, Any], generation: int) -> dict[str, Any]:
    return {
        "kernel_digest": kernel["kernel_digest"],
        "generation": generation,
        "manager_cell_id": cell["cell_id"],
        "parent_program_id": cell["parent_program_id"],
        "business_unit_id": cell["business_unit_id"],
        "workstream_id": cell["workstream_id"],
        "partition_index": cell["partition_index"],
        "partition_count": cell["partition_count"],
        "deliverable": cell["deliverable"],
        "risk_tier": cell["risk_tier"],
        "decision_mode": cell["decision_mode"],
        "requested_model": cell["requested_manager_model"],
        "requested_reasoning": cell["requested_manager_reasoning"],
        "required_capabilities": cell["required_capabilities"],
        "artifact_kinds": cell["artifact_kinds"],
    }


def admitted_state(
    *,
    kernel: Mapping[str, Any],
    cell: Mapping[str, Any],
    generation: int,
    project_id: str,
    cycle_id: str,
    parent_runtime_id: str,
    budget: Mapping[str, int],
) -> dict[str, Any]:
    spec = manager_spec(kernel, cell, generation)
    spec_digest = digest_value(spec)
    attempt_id = f"{cell['cell_id']}-g{generation}"
    idempotency_key = digest_value(
        {
            "attempt_id": attempt_id,
            "kernel_digest": kernel["kernel_digest"],
            "manager_spec_digest": spec_digest,
        }
    )
    return NATIVE.admit(
        attempt_id=attempt_id,
        idempotency_key=idempotency_key,
        requested_model=cell["requested_manager_model"],
        project_id=project_id,
        work_id=cell["cell_id"],
        cycle_id=cycle_id,
        parent_runtime_id=parent_runtime_id,
        role="manager",
        scope={
            "deliverable": cell["deliverable"],
            "required_capabilities": cell["required_capabilities"],
            "artifact_kinds": cell["artifact_kinds"],
            "decision_mode": cell["decision_mode"],
        },
        budget=budget,
        metadata={
            "kernel_digest": kernel["kernel_digest"],
            "generation": generation,
            "manager_cell_id": cell["cell_id"],
            "manager_spec_digest": spec_digest,
            "requested_reasoning": cell["requested_manager_reasoning"],
        },
    )


def validate_request(
    value: dict[str, Any], kernel: Mapping[str, Any]
) -> dict[str, Any]:
    exact_keys(
        value,
        {
            "$schema",
            "kernel_digest",
            "generation",
            "project_id",
            "cycle_id",
            "parent_runtime_id",
            "budget_envelope",
            "manager_admissions",
            "observed_snapshot",
        },
        "reconciliation request",
    )
    if value["$schema"] != REQUEST_SCHEMA:
        raise ReconciliationError("unsupported reconciliation request schema")
    if value["kernel_digest"] != kernel["kernel_digest"]:
        raise ReconciliationError("reconciliation request does not bind the exact kernel")
    generation = integer(value["generation"], 1, 10**12, "generation")
    project_id = text(value["project_id"], "project_id")
    cycle_id = text(value["cycle_id"], "cycle_id")
    parent_runtime_id = text(value["parent_runtime_id"], "parent_runtime_id")
    envelope = validate_budget(value["budget_envelope"], "budget_envelope")
    manager_limit = kernel["admission"]["initial_active_manager_limit"]
    admissions_raw = value["manager_admissions"]
    if not isinstance(admissions_raw, list) or not admissions_raw:
        raise ReconciliationError("manager_admissions must be a non-empty array")
    if len(admissions_raw) > manager_limit:
        raise ReconciliationError("manager admissions exceed the kernel manager limit")
    cell_index = {
        item["cell_id"]: item for item in kernel["organization"]["manager_cells"]
    }
    admissions: list[dict[str, Any]] = []
    seen_cells: set[str] = set()
    token_total = 0
    cost_total = 0
    for index, item in enumerate(admissions_raw):
        label = f"manager_admissions[{index}]"
        if not isinstance(item, Mapping):
            raise ReconciliationError(f"{label} must be an object")
        exact_keys(item, {"cell_id", "budget"}, label)
        cell_id = text(item["cell_id"], f"{label}.cell_id")
        if cell_id in seen_cells:
            raise ReconciliationError(f"duplicate manager admission {cell_id}")
        seen_cells.add(cell_id)
        if cell_id not in cell_index:
            raise ReconciliationError(f"unknown manager cell {cell_id}")
        budget = validate_budget(item["budget"], f"{label}.budget")
        if budget["max_wall_seconds"] > envelope["max_wall_seconds"]:
            raise ReconciliationError(f"{label} wall budget exceeds the envelope")
        token_total += budget["max_tokens"]
        cost_total += budget["max_cost_microusd"]
        admissions.append({"cell_id": cell_id, "budget": budget})
    if token_total > envelope["max_tokens"] or cost_total > envelope["max_cost_microusd"]:
        raise ReconciliationError("manager budgets exceed the global envelope")

    snapshot = value["observed_snapshot"]
    if not isinstance(snapshot, Mapping):
        raise ReconciliationError("observed_snapshot must be an object")
    exact_keys(snapshot, {"$schema", "last_event_cursor", "attempts"}, "observed_snapshot")
    if snapshot["$schema"] != SNAPSHOT_SCHEMA:
        raise ReconciliationError("unsupported observed snapshot schema")
    last_cursor = integer(snapshot["last_event_cursor"], 0, 10**18, "last_event_cursor")
    attempts_raw = snapshot["attempts"]
    if not isinstance(attempts_raw, list):
        raise ReconciliationError("observed_snapshot.attempts must be an array")
    attempts: list[dict[str, Any]] = []
    cursors: list[int] = []
    attempt_ids: set[str] = set()
    idempotency_keys: dict[str, str] = {}
    cell_generations: set[tuple[str, int]] = set()
    for index, item in enumerate(attempts_raw):
        label = f"observed_snapshot.attempts[{index}]"
        if not isinstance(item, Mapping):
            raise ReconciliationError(f"{label} must be an object")
        exact_keys(item, {"event_cursor", "native_runtime", "role_readback"}, label)
        cursor = integer(item["event_cursor"], 1, 10**18, f"{label}.event_cursor")
        cursors.append(cursor)
        state = item["native_runtime"]
        errors = NATIVE.audit_state(state)
        if errors:
            raise ReconciliationError(f"{label} native runtime failed audit: {'; '.join(errors)}")
        admission = state["admission"]
        if (
            admission["project_id"] != project_id
            or admission["cycle_id"] != cycle_id
            or admission["parent_runtime_id"] != parent_runtime_id
            or admission["role"] != "manager"
        ):
            raise ReconciliationError(f"{label} native authority does not match the request")
        metadata = admission["metadata"]
        if not isinstance(metadata, Mapping):
            raise ReconciliationError(f"{label} manager metadata must be an object")
        exact_keys(
            metadata,
            {
                "kernel_digest",
                "generation",
                "manager_cell_id",
                "manager_spec_digest",
                "requested_reasoning",
            },
            f"{label}.metadata",
        )
        attempt_id = state["attempt_id"]
        if attempt_id in attempt_ids:
            raise ReconciliationError(f"duplicate observed attempt {attempt_id}")
        attempt_ids.add(attempt_id)
        idempotency_key = admission["idempotency_key"]
        owner = idempotency_keys.get(idempotency_key)
        if owner is not None and owner != attempt_id:
            raise ReconciliationError("idempotency key is reused by different attempts")
        idempotency_keys[idempotency_key] = attempt_id
        cell_id = text(metadata["manager_cell_id"], f"{label}.manager_cell_id")
        observed_generation = integer(
            metadata["generation"], 1, 10**12, f"{label}.generation"
        )
        cell_generation = (cell_id, observed_generation)
        if cell_generation in cell_generations:
            raise ReconciliationError("multiple attempts claim the same cell generation")
        cell_generations.add(cell_generation)
        requested_reasoning = text(
            metadata["requested_reasoning"], f"{label}.requested_reasoning"
        )
        if requested_reasoning not in MODEL_REASONS:
            raise ReconciliationError(f"{label} requested reasoning is unsupported")
        role_readback = validate_role_readback(
            item["role_readback"],
            requested_model=state["requested_model"],
            requested_reasoning=requested_reasoning,
            label=f"{label}.role_readback",
        )
        if role_readback["status"] != "inconclusive" and state.get("native_identity") is None:
            raise ReconciliationError(
                f"{label} observed role readback requires a bound native host identity"
            )
        attempts.append(
            {
                "event_cursor": cursor,
                "native_runtime": deepcopy(state),
                "role_readback": role_readback,
            }
        )
    if cursors != sorted(cursors) or len(cursors) != len(set(cursors)):
        raise ReconciliationError("observed event cursors must be strictly increasing")
    if (cursors[-1] if cursors else 0) != last_cursor:
        raise ReconciliationError("last_event_cursor does not match the observed stream")
    return {
        "$schema": REQUEST_SCHEMA,
        "kernel_digest": kernel["kernel_digest"],
        "generation": generation,
        "project_id": project_id,
        "cycle_id": cycle_id,
        "parent_runtime_id": parent_runtime_id,
        "budget_envelope": envelope,
        "manager_admissions": sorted(admissions, key=lambda item: item["cell_id"]),
        "observed_snapshot": {
            "$schema": SNAPSHOT_SCHEMA,
            "last_event_cursor": last_cursor,
            "attempts": attempts,
        },
    }


def compile_plan(kernel: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    generation = request["generation"]
    cell_index = {
        item["cell_id"]: item for item in kernel["organization"]["manager_cells"]
    }
    desired = {item["cell_id"]: item for item in request["manager_admissions"]}
    current_by_cell: dict[str, dict[str, Any]] = {}
    stale: list[dict[str, Any]] = []
    conflicts: list[dict[str, str]] = []
    active_count = 0
    terminal_statuses = NATIVE.TERMINAL_STATUSES
    for observed in request["observed_snapshot"]["attempts"]:
        state = observed["native_runtime"]
        metadata = state["admission"]["metadata"]
        cell_id = metadata["manager_cell_id"]
        is_terminal = state["status"] in terminal_statuses
        if not is_terminal:
            active_count += 1
        is_current = (
            metadata["kernel_digest"] == kernel["kernel_digest"]
            and metadata["generation"] == generation
            and cell_id in desired
        )
        if not is_current:
            stale.append(observed)
            continue
        cell = cell_index.get(cell_id)
        if cell is None:
            conflicts.append({"cell_id": cell_id, "reason": "current_cell_missing_from_kernel"})
            continue
        expected = admitted_state(
            kernel=kernel,
            cell=cell,
            generation=generation,
            project_id=request["project_id"],
            cycle_id=request["cycle_id"],
            parent_runtime_id=request["parent_runtime_id"],
            budget=desired[cell_id]["budget"],
        )
        if (
            state["admission_digest"] != expected["admission_digest"]
            or state["attempt_id"] != expected["attempt_id"]
            or state["dispatch"]["key"] != expected["dispatch"]["key"]
        ):
            conflicts.append({"cell_id": cell_id, "reason": "current_spec_or_budget_drift"})
            continue
        current_by_cell[cell_id] = observed

    manager_limit = kernel["admission"]["initial_active_manager_limit"]
    if active_count > manager_limit:
        conflicts.append(
            {
                "cell_id": "*",
                "reason": "observed_active_managers_exceed_admission_limit",
            }
        )
    actions: list[dict[str, Any]] = []

    def add(kind: str, cell_id: str, attempt_id: str, reason: str, **extra: Any) -> None:
        actions.append(
            {
                "order": len(actions) + 1,
                "kind": kind,
                "cell_id": cell_id,
                "attempt_id": attempt_id,
                "reason": reason,
                **extra,
            }
        )

    if not conflicts:
        for observed in sorted(
            stale,
            key=lambda item: (
                item["native_runtime"]["admission"]["metadata"]["manager_cell_id"],
                item["native_runtime"]["attempt_id"],
            ),
        ):
            state = observed["native_runtime"]
            cell_id = state["admission"]["metadata"]["manager_cell_id"]
            if state["status"] in terminal_statuses:
                add(
                    "archive-stale-terminal",
                    cell_id,
                    state["attempt_id"],
                    "stale_generation_or_scope",
                )
            else:
                add(
                    "request-cancellation",
                    cell_id,
                    state["attempt_id"],
                    "stale_generation_or_scope",
                )

        for cell_id in sorted(current_by_cell):
            observed = current_by_cell[cell_id]
            state = observed["native_runtime"]
            role = observed["role_readback"]
            if role["status"] == "refuted" and state["status"] in terminal_statuses:
                add(
                    "quarantine-terminal",
                    cell_id,
                    state["attempt_id"],
                    "terminal_artifacts_have_observed_role_drift",
                    terminal_status=state["status"],
                )
            elif state["status"] in terminal_statuses:
                add(
                    "settle-terminal",
                    cell_id,
                    state["attempt_id"],
                    "native_terminal_requires_separate_manager_acceptance",
                    terminal_status=state["status"],
                )
            elif role["status"] == "refuted":
                add("request-cancellation", cell_id, state["attempt_id"], "observed_role_drift")
            elif state.get("native_identity") is not None and role["status"] == "inconclusive":
                add("observe-role", cell_id, state["attempt_id"], "runtime_role_not_observed")
            else:
                reconciled = NATIVE.reconcile_restart(state)
                add(
                    "native-next-action",
                    cell_id,
                    state["attempt_id"],
                    "retained_native_state",
                    native_next_action=reconciled["reconciliation"]["next_action"],
                )

        available_slots = max(0, manager_limit - active_count)
        missing = [cell_id for cell_id in sorted(desired) if cell_id not in current_by_cell]
        for cell_id in missing[:available_slots]:
            state = admitted_state(
                kernel=kernel,
                cell=cell_index[cell_id],
                generation=generation,
                project_id=request["project_id"],
                cycle_id=request["cycle_id"],
                parent_runtime_id=request["parent_runtime_id"],
                budget=desired[cell_id]["budget"],
            )
            add(
                "persist-admission-intent",
                cell_id,
                state["attempt_id"],
                "desired_cell_missing_and_slot_available",
                admission_state=state,
            )
        for cell_id in missing[available_slots:]:
            state = admitted_state(
                kernel=kernel,
                cell=cell_index[cell_id],
                generation=generation,
                project_id=request["project_id"],
                cycle_id=request["cycle_id"],
                parent_runtime_id=request["parent_runtime_id"],
                budget=desired[cell_id]["budget"],
            )
            add(
                "defer-admission",
                cell_id,
                state["attempt_id"],
                "manager_capacity_unavailable_until_settlement",
            )

    if conflicts:
        status = "blocked"
    elif any(item["kind"] == "defer-admission" for item in actions):
        status = "deferred"
    else:
        status = "ready"
    plan: dict[str, Any] = {
        "$schema": PLAN_SCHEMA,
        "kernel_digest": kernel["kernel_digest"],
        "generation": generation,
        "request_digest": digest_value(request),
        "snapshot_cursor": request["observed_snapshot"]["last_event_cursor"],
        "status": status,
        "slot_accounting": {
            "manager_limit": manager_limit,
            "observed_active_managers": active_count,
            "available_manager_slots": max(0, manager_limit - active_count),
            "wind_down_reserve_slots": kernel["admission"]["wind_down_reserve_slots"],
        },
        "conflicts": sorted(conflicts, key=lambda item: (item["cell_id"], item["reason"])),
        "actions": actions,
        "non_claims": {
            "task_launch_performed": False,
            "cancellation_performed": False,
            "database_write_performed": False,
            "scheduler_activated": False,
            "role_readback_cryptographically_attested": False,
        },
    }
    plan["plan_digest"] = digest_value(plan)
    return plan


def verify_plan(kernel_path: Path, request_path: Path, plan_path: Path) -> dict[str, Any]:
    kernel = verify_kernel_document(kernel_path)
    request_raw = read_canonical_object(request_path, "reconciliation request")
    request = validate_request(request_raw, kernel)
    expected = compile_plan(kernel, request)
    actual = read_canonical_object(plan_path, "reconciliation plan")
    if actual != expected:
        raise ReconciliationError("reconciliation plan does not reproduce")
    return {
        "ok": True,
        "plan_digest": actual["plan_digest"],
        "status": actual["status"],
        "action_count": len(actual["actions"]),
        "launch_performed": actual["non_claims"]["task_launch_performed"],
    }


def write_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(canonical_bytes(value))
    os.replace(temporary, path)


def command_plan(args: argparse.Namespace) -> int:
    try:
        kernel = verify_kernel_document(Path(args.kernel))
        request_raw = read_canonical_object(Path(args.request), "reconciliation request")
        request = validate_request(request_raw, kernel)
        plan = compile_plan(kernel, request)
        write_atomic(Path(args.output), plan)
        print(
            json.dumps(
                {
                    "ok": True,
                    "output": args.output,
                    "plan_digest": plan["plan_digest"],
                    "status": plan["status"],
                },
                sort_keys=True,
            )
        )
        return 0
    except (ReconciliationError, KERNEL.KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def command_verify(args: argparse.Namespace) -> int:
    try:
        receipt = verify_plan(Path(args.kernel), Path(args.request), Path(args.plan))
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except (ReconciliationError, KERNEL.KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    create = sub.add_parser("plan")
    create.add_argument("--kernel", required=True)
    create.add_argument("--request", required=True)
    create.add_argument("--output", required=True)
    create.set_defaults(handler=command_plan)
    verify = sub.add_parser("verify")
    verify.add_argument("--kernel", required=True)
    verify.add_argument("--request", required=True)
    verify.add_argument("--plan", required=True)
    verify.set_defaults(handler=command_verify)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
