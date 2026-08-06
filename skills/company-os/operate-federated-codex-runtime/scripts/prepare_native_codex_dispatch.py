#!/usr/bin/env python3
"""Compile and verify a durable Company OS command for native Codex dispatch."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping


SKILL_ROOT = Path(__file__).resolve().parents[1]
COMPANY_OS_ROOT = SKILL_ROOT.parent
RECONCILE_PATH = (
    COMPANY_OS_ROOT
    / "compile-federated-company-kernel"
    / "scripts"
    / "reconcile_federated_kernel.py"
)
CLAIM_SCHEMA = "company-os.postgresql-federated-command-claim.v1"
BINDING_SCHEMA = "company-os.codex-native-host-binding.v1"
DISPATCH_SCHEMA = "company-os.codex-native-dispatch.v1"
CREATION_RECEIPT_SCHEMA = "company-os.codex-native-creation-receipt.v1"
MANAGER_PACKET_SCHEMA = "company-os.federated-manager-cell-packet.v1"
DESIGN_REPORT_SCHEMA = "company-os.manager-design-report.v1"
DESIGN_RECEIPT_SCHEMA = "company-os.manager-design-continuation-receipt.v1"
RECONCILIATION_INPUT_SCHEMA = "company-os.codex-native-candidate-set.v1"
RECONCILIATION_OBSERVATION_SCHEMA = "company-os.codex-native-task-observation.v1"
RECONCILIATION_RECEIPT_SCHEMA = "company-os.codex-native-candidate-reconciliation.v1"
SHA256_LENGTH = 64


class NativeBridgeError(ValueError):
    """A fail-closed host bridge contract error."""


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise NativeBridgeError(f"cannot load required module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RECONCILE = load_module("company_os_native_bridge_reconciler", RECONCILE_PATH)


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeError) as exc:
        raise NativeBridgeError("value is not canonical JSON encodable") from exc


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise NativeBridgeError(
            f"{label} keys differ: missing={sorted(expected - set(value))} "
            f"extra={sorted(set(value) - expected)}"
        )


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise NativeBridgeError(f"{label} must be non-empty trimmed text")
    return value


def sha256(value: Any, label: str) -> str:
    value = text(value, label)
    if len(value) != SHA256_LENGTH or any(char not in "0123456789abcdef" for char in value):
        raise NativeBridgeError(f"{label} must be lowercase SHA-256")
    return value


def string_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise NativeBridgeError(f"{label} must be an array")
    rendered = [text(item, f"{label} item") for item in value]
    if not allow_empty and not rendered:
        raise NativeBridgeError(f"{label} must not be empty")
    if len(rendered) != len(set(rendered)):
        raise NativeBridgeError(f"{label} must contain unique values")
    return rendered


def read_canonical(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise NativeBridgeError(f"{label} must be a regular non-symlink file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeBridgeError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise NativeBridgeError(f"{label} must be an object")
    if raw != (canonical_json(value) + "\n").encode("utf-8"):
        raise NativeBridgeError(f"{label} must use canonical JSON bytes")
    return value


def validate_claim(value: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    exact_keys(
        value,
        {"$schema", "ok", "backend", "project_id", "claim_owner", "claim"},
        "claim",
    )
    if value["$schema"] != CLAIM_SCHEMA or value["ok"] is not True or value["backend"] != "postgresql":
        raise NativeBridgeError("claim header is invalid")
    project_id = text(value["project_id"], "claim.project_id")
    text(value["claim_owner"], "claim.claim_owner")
    claim = value["claim"]
    if not isinstance(claim, Mapping):
        raise NativeBridgeError("claim has no command")
    exact_keys(
        claim,
        {"message_key", "payload_json", "payload_sha256", "lease_generation"},
        "claim.claim",
    )
    message_key = sha256(claim["message_key"], "claim.message_key")
    payload_sha256 = sha256(claim["payload_sha256"], "claim.payload_sha256")
    generation = claim["lease_generation"]
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
        raise NativeBridgeError("claim.lease_generation must be a positive integer")
    payload_json = text(claim["payload_json"], "claim.payload_json")
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise NativeBridgeError("claimed payload is not JSON") from exc
    if not isinstance(payload, dict) or payload_json != canonical_json(payload):
        raise NativeBridgeError("claimed payload must be a canonical JSON object")
    exact_keys(
        payload,
        {
            "$schema",
            "action",
            "command_digest",
            "cycle_id",
            "generation",
            "kernel_digest",
            "parent_runtime_id",
            "plan_digest",
            "plan_order",
            "project_id",
        },
        "claimed payload",
    )
    if payload["$schema"] != "company-os.federated-runtime-command.v1":
        raise NativeBridgeError("claimed payload schema is unsupported")
    unsigned_payload = dict(payload)
    supplied_command_digest = unsigned_payload.pop("command_digest")
    if (
        supplied_command_digest != message_key
        or digest_text(canonical_json(unsigned_payload)) != message_key
        or digest_text(payload_json) != payload_sha256
    ):
        raise NativeBridgeError("claimed command digest does not verify")
    if payload["project_id"] != project_id:
        raise NativeBridgeError("claim project does not match command project")
    return dict(claim), payload


def validate_binding(value: Mapping[str, Any], *, project_id: str, kernel_digest: str) -> dict[str, Any]:
    exact_keys(
        value,
        {"$schema", "binding_id", "company_project_id", "kernel_digest", "target"},
        "binding",
    )
    if value["$schema"] != BINDING_SCHEMA:
        raise NativeBridgeError("host binding schema is unsupported")
    text(value["binding_id"], "binding.binding_id")
    if value["company_project_id"] != project_id or value["kernel_digest"] != kernel_digest:
        raise NativeBridgeError("host binding does not match project and kernel")
    target = value["target"]
    if not isinstance(target, Mapping):
        raise NativeBridgeError("binding.target must be an object")
    target_type = target.get("type")
    if target_type == "projectless":
        if set(target) not in ({"type"}, {"type", "directory_name"}):
            raise NativeBridgeError("projectless target shape is invalid")
        result: dict[str, Any] = {"type": "projectless"}
        if "directory_name" in target:
            result["directoryName"] = text(target["directory_name"], "target.directory_name")
        return result
    if target_type != "project":
        raise NativeBridgeError("only native project and projectless targets are supported")
    exact_keys(target, {"type", "project_id", "environment"}, "binding.target")
    project = text(target["project_id"], "target.project_id")
    environment = target["environment"]
    if not isinstance(environment, Mapping):
        raise NativeBridgeError("target.environment must be an object")
    env_type = environment.get("type")
    if env_type == "local":
        exact_keys(environment, {"type"}, "target.environment")
        rendered_environment: dict[str, Any] = {"type": "local"}
    elif env_type == "worktree":
        if set(environment) not in ({"type"}, {"type", "starting_state"}):
            raise NativeBridgeError("worktree environment shape is invalid")
        rendered_environment = {"type": "worktree"}
        if "starting_state" in environment:
            state = environment["starting_state"]
            if not isinstance(state, Mapping):
                raise NativeBridgeError("starting_state must be an object")
            if state.get("type") == "working-tree":
                exact_keys(state, {"type"}, "starting_state")
                rendered_environment["startingState"] = {"type": "working-tree"}
            elif state.get("type") == "branch":
                exact_keys(state, {"type", "branch_name"}, "starting_state")
                rendered_environment["startingState"] = {
                    "type": "branch",
                    "branchName": text(state["branch_name"], "starting_state.branch_name"),
                }
            else:
                raise NativeBridgeError("starting_state type is unsupported")
    else:
        raise NativeBridgeError("target environment is unsupported")
    return {"type": "project", "projectId": project, "environment": rendered_environment}


def manager_cell(kernel: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    action = payload["action"]
    if not isinstance(action, Mapping):
        raise NativeBridgeError("command action must be an object")
    exact_keys(
        action,
        {"admission_state", "attempt_id", "cell_id", "kind", "order", "reason"},
        "command action",
    )
    if action["kind"] != "persist-admission-intent":
        raise NativeBridgeError("native create bridge accepts only manager admission intent")
    cell_id = text(action["cell_id"], "action.cell_id")
    cells = kernel.get("organization", {}).get("manager_cells", [])
    matches = [item for item in cells if isinstance(item, Mapping) and item.get("cell_id") == cell_id]
    if len(matches) != 1:
        raise NativeBridgeError("command manager cell is not uniquely present in kernel")
    cell = dict(matches[0])
    state = action["admission_state"]
    if not isinstance(state, Mapping) or state.get("schema") != "company-os.native-task-runtime.v2":
        raise NativeBridgeError("command admission state is invalid")
    admission = state.get("admission")
    if not isinstance(admission, Mapping) or admission.get("role") != "manager":
        raise NativeBridgeError("command does not contain a manager admission")
    if (
        admission.get("project_id") != payload["project_id"]
        or admission.get("cycle_id") != payload["cycle_id"]
        or admission.get("parent_runtime_id") != payload["parent_runtime_id"]
        or admission.get("work_id") != cell_id
        or admission.get("requested_model") != cell["requested_manager_model"]
    ):
        raise NativeBridgeError("manager admission conflicts with command or kernel")
    metadata = admission.get("metadata")
    if not isinstance(metadata, Mapping) or (
        metadata.get("kernel_digest") != kernel["kernel_digest"]
        or metadata.get("manager_cell_id") != cell_id
        or metadata.get("requested_reasoning") != cell["requested_manager_reasoning"]
    ):
        raise NativeBridgeError("manager admission metadata conflicts with kernel")
    return cell


def manager_context(kernel: Mapping[str, Any], cell: Mapping[str, Any]) -> dict[str, Any]:
    programs = kernel.get("organization", {}).get("program_cells", [])
    units = kernel.get("organization", {}).get("business_unit_cells", [])
    program_matches = [
        item
        for item in programs
        if isinstance(item, Mapping)
        and item.get("program_id") == cell["parent_program_id"]
        and item.get("business_unit_id") == cell["business_unit_id"]
    ]
    unit_matches = [
        item
        for item in units
        if isinstance(item, Mapping)
        and item.get("cell_id") == f"unit-{cell['business_unit_id']}"
    ]
    if len(program_matches) != 1 or len(unit_matches) != 1:
        raise NativeBridgeError("manager cell has no unique program and business-unit context")
    admission = kernel.get("admission")
    quality = kernel.get("source_request", {}).get("quality_targets")
    if not isinstance(admission, Mapping) or not isinstance(quality, Mapping):
        raise NativeBridgeError("kernel lacks admission or quality context")
    manager_limit = admission.get("initial_active_manager_limit")
    luna_limit = admission.get("initial_active_luna_limit")
    if not isinstance(manager_limit, int) or manager_limit < 1:
        raise NativeBridgeError("kernel manager concurrency is invalid")
    if not isinstance(luna_limit, int) or luna_limit < 0:
        raise NativeBridgeError("kernel Luna concurrency is invalid")
    per_manager_cap = min(
        cell["declared_worker_slots"],
        luna_limit // manager_limit,
    )
    risk_tier = cell["risk_tier"]
    delegated_tiers = kernel.get("authority", {}).get("delegated_risk_tiers", [])
    autonomous_design = (
        risk_tier in {"low", "medium"}
        and risk_tier in delegated_tiers
        and per_manager_cap > 0
        and cell.get("delivery_contract_status") == "complete"
        and bool(cell.get("mandatory_requirements"))
        and bool(cell.get("acceptance_checks"))
    )
    report_contract = (
        {
            "$schema": DESIGN_REPORT_SCHEMA,
            "report_fields": [
                "$schema",
                "manager_packet_digest",
                "project_id",
                "cycle_id",
                "attempt_id",
                "cell_id",
                "design_barrier",
                "workers",
                "requirement_assignments",
                "capability_assignments",
                "unresolved_dependencies",
                "protected_actions",
                "scope_variances",
                "manager_direct_labor_variances",
            ],
            "worker_fields": [
                "worker_id",
                "outcome",
                "requested_model",
                "requested_reasoning",
                "depends_on",
                "write_scopes",
                "budget",
            ],
            "requirement_assignment_fields": [
                "requirement",
                "owner_worker_ids",
                "acceptance_checks",
            ],
            "capability_assignment_fields": ["capability_id", "worker_ids"],
            "empty_for_auto_continue": [
                "unresolved_dependencies",
                "protected_actions",
                "scope_variances",
                "manager_direct_labor_variances",
            ],
            "gate_command": (
                "prepare_native_codex_dispatch.py verify-design "
                "--manager-packet <packet.json> --design-report <report.json>"
            ),
        }
        if autonomous_design
        else None
    )
    return {
        "business_unit_mission": unit_matches[0]["mission"],
        "program_objective": program_matches[0]["objective"],
        "quality_targets": dict(quality),
        "global_admission": dict(admission),
        "active_worker_concurrency_cap": per_manager_cap,
        "execution_policy": {
            "mode": "luna_first",
            "design_barrier": (
                "charter_bound_auto_continue"
                if autonomous_design
                else "authenticated_master_decision"
            ),
            "autonomous_design_conditions": (
                [
                    "all_mandatory_requirements_have_exact_owners_and_checks",
                    "all_worker_write_scopes_are_disjoint",
                    "all_dependencies_are_satisfied",
                    "all_required_capabilities_are_resolved",
                    "no_protected_action_or_scope_variance_is_required",
                    "budget_concurrency_and_authority_checks_pass",
                ]
                if autonomous_design
                else []
            ),
            "autonomous_design_report_contract": report_contract,
            "manager_direct_labor": "exception_only_with_variance",
            "manager_reports": "barrier_exception_and_final_delta_only",
            "master_context": "packet_and_receipts_only",
            "luna_labor_share_min": quality["luna_labor_share_min"],
            "sol_overhead_share_max": quality["sol_overhead_share_max"],
        },
    }


def build_dispatch(
    kernel: Mapping[str, Any], claim_value: Mapping[str, Any], binding_value: Mapping[str, Any]
) -> dict[str, Any]:
    claim, payload = validate_claim(claim_value)
    if kernel.get("kernel_digest") != payload["kernel_digest"]:
        raise NativeBridgeError("claimed command does not match compiled kernel")
    cell = manager_cell(kernel, payload)
    context = manager_context(kernel, cell)
    target = validate_binding(
        binding_value,
        project_id=payload["project_id"],
        kernel_digest=kernel["kernel_digest"],
    )
    action = payload["action"]
    admission = action["admission_state"]["admission"]
    marker = f"company-os-dispatch:{claim['message_key']}"
    manager_packet = {
        "$schema": MANAGER_PACKET_SCHEMA,
        "project_id": payload["project_id"],
        "kernel_digest": kernel["kernel_digest"],
        "cycle_id": payload["cycle_id"],
        "generation": payload["generation"],
        "parent_runtime_id": payload["parent_runtime_id"],
        "attempt_id": action["attempt_id"],
        "manager_cell": cell,
        "manager_context": context,
        "company_objective": kernel["objective"],
        "budget": admission["budget"],
        "authority": kernel["authority"],
        "dispatch_marker": marker,
    }
    manager_packet["manager_packet_digest"] = digest_text(canonical_json(manager_packet))
    execution_policy = context["execution_policy"]
    if execution_policy["design_barrier"] == "charter_bound_auto_continue":
        design_instruction = (
            "The signed dispatch preauthorizes design-to-execution continuation only when "
            "every manager_context.execution_policy.autonomous_design_condition is explicitly "
            "evidenced in a canonical company-os.manager-design-report.v1. Before worker creation, "
            "materialize the exact Canonical manager packet and the report, then run "
            "prepare_native_codex_dispatch.py verify-design --manager-packet <packet.json> "
            "--design-report <report.json>. Create eligible Luna/max workers in the same turn only "
            "when its receipt says continue_allowed:true; attach that receipt to the final manager "
            "receipt. If validation fails or any condition is unresolved, stop at design and "
            "request an authenticated master decision. "
        )
    else:
        design_instruction = (
            "Do not create workers until the master sends an explicit CONTINUE to this task after "
            "reviewing the design report. "
        )
    prompt = (
        "Use $luna-execution-fabric.\n\n"
        f"Dispatch marker: {marker}\n"
        "You are the Sol manager for exactly one bounded Company OS cell. "
        "Treat this packet as the complete cell-level program contract, not as permission to "
        "widen it. First return a compact design report with a Luna task DAG, artifact owners, "
        "acceptance checks, dependencies, and budgets. "
        + design_instruction
        + "Then create "
        "Luna/max worker tasks only for independently owned work and never exceed "
        "manager_context.active_worker_concurrency_cap or the cell's declared capacity. "
        "Validate required skills before worker dispatch. A manager must not materialize a "
        "worker-eligible artifact itself; direct labor is allowed only for inherently managerial "
        "work, unavailable native worker authority, or duplicate-work avoidance, and every use "
        "requires an exact variance. Consume worker receipts rather than transcripts, report only "
        "barriers, exceptions, and final deltas, and stop accepted branches immediately. Preserve "
        "mandatory requirements, budgets, writer "
        "scopes, evidence, cancellation, and parent reporting. Do not deploy, spend, contact "
        "customers, or write production without the packet's existing approval boundary. "
        "Return one compact manager receipt with accepted artifacts, checks, observed task "
        "identities, unavailable telemetry, rework, and the next master decision.\n\n"
        "Canonical manager packet:\n" + canonical_json(manager_packet)
    )
    arguments = {
        "prompt": prompt,
        "target": target,
        "model": cell["requested_manager_model"],
        "thinking": cell["requested_manager_reasoning"],
    }
    dispatch = {
        "$schema": DISPATCH_SCHEMA,
        "message_key": claim["message_key"],
        "lease_generation": claim["lease_generation"],
        "project_id": payload["project_id"],
        "kernel_digest": kernel["kernel_digest"],
        "cell_id": cell["cell_id"],
        "attempt_id": action["attempt_id"],
        "binding_digest": digest_text(canonical_json(binding_value)),
        "marker": marker,
        "tool": "codex_app__create_thread",
        "arguments": arguments,
        "initial_prompt_sha256": digest_text(prompt),
    }
    dispatch["dispatch_digest"] = digest_text(canonical_json(dispatch))
    return dispatch


def verify_manager_packet(value: Mapping[str, Any]) -> str:
    packet = dict(value)
    supplied_digest = packet.pop("manager_packet_digest", None)
    if value.get("$schema") != MANAGER_PACKET_SCHEMA:
        raise NativeBridgeError("manager packet schema is unsupported")
    if supplied_digest != digest_text(canonical_json(packet)):
        raise NativeBridgeError("manager packet digest does not verify")
    return sha256(supplied_digest, "manager_packet.manager_packet_digest")


def worker_budget(value: Any, label: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise NativeBridgeError(f"{label} must be an object")
    exact_keys(value, {"max_tokens", "max_cost_microusd", "max_wall_seconds"}, label)
    result: dict[str, int] = {}
    for key in ("max_tokens", "max_cost_microusd", "max_wall_seconds"):
        amount = value[key]
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            raise NativeBridgeError(f"{label}.{key} must be a non-negative integer")
        result[key] = amount
    if result["max_tokens"] < 1 or result["max_wall_seconds"] < 1:
        raise NativeBridgeError(f"{label} must allocate positive tokens and wall time")
    return result


def scope_conflicts(first: str, second: str) -> bool:
    first_parts = tuple(first.split("/"))
    second_parts = tuple(second.split("/"))
    shorter = min(len(first_parts), len(second_parts))
    return first_parts[:shorter] == second_parts[:shorter]


def validate_writer_scope(value: Any, label: str) -> str:
    scope = text(value, label)
    parts = scope.split("/")
    if scope.startswith("/") or any(part in {"", ".", ".."} for part in parts) or "\\" in scope:
        raise NativeBridgeError(f"{label} must be a normalized relative scope")
    return scope


def has_dependency_cycle(dependencies: Mapping[str, list[str]]) -> bool:
    active: set[str] = set()
    complete: set[str] = set()

    def visit(worker_id: str) -> bool:
        if worker_id in active:
            return True
        if worker_id in complete:
            return False
        active.add(worker_id)
        if any(visit(dependency) for dependency in dependencies[worker_id]):
            return True
        active.remove(worker_id)
        complete.add(worker_id)
        return False

    return any(visit(worker_id) for worker_id in dependencies)


def dependency_critical_wall_seconds(
    dependencies: Mapping[str, list[str]], wall_seconds: Mapping[str, int]
) -> int:
    memo: dict[str, int] = {}

    def duration(worker_id: str) -> int:
        if worker_id not in memo:
            prior = max((duration(item) for item in dependencies[worker_id]), default=0)
            memo[worker_id] = prior + wall_seconds[worker_id]
        return memo[worker_id]

    return max((duration(worker_id) for worker_id in dependencies), default=0)


def verify_design_continuation(
    manager_packet: Mapping[str, Any], design_report: Mapping[str, Any]
) -> dict[str, Any]:
    packet_digest = verify_manager_packet(manager_packet)
    exact_keys(
        design_report,
        {
            "$schema",
            "manager_packet_digest",
            "project_id",
            "cycle_id",
            "attempt_id",
            "cell_id",
            "design_barrier",
            "workers",
            "requirement_assignments",
            "capability_assignments",
            "unresolved_dependencies",
            "protected_actions",
            "scope_variances",
            "manager_direct_labor_variances",
        },
        "design report",
    )
    if design_report["$schema"] != DESIGN_REPORT_SCHEMA:
        raise NativeBridgeError("design report schema is unsupported")
    report_digest = digest_text(canonical_json(design_report))
    errors: list[str] = []
    for key in ("project_id", "cycle_id", "attempt_id"):
        if design_report[key] != manager_packet.get(key):
            errors.append(f"design report {key} does not match manager packet")
    cell = manager_packet.get("manager_cell")
    context = manager_packet.get("manager_context")
    if not isinstance(cell, Mapping) or not isinstance(context, Mapping):
        raise NativeBridgeError("manager packet lacks cell or context")
    if design_report["cell_id"] != cell.get("cell_id"):
        errors.append("design report cell_id does not match manager packet")
    if design_report["manager_packet_digest"] != packet_digest:
        errors.append("design report does not bind the exact manager packet")
    policy = context.get("execution_policy")
    if not isinstance(policy, Mapping):
        raise NativeBridgeError("manager packet lacks execution policy")
    expected_barrier = policy.get("design_barrier")
    if (
        expected_barrier != "charter_bound_auto_continue"
        or design_report["design_barrier"] != expected_barrier
    ):
        errors.append("manager cell is not authorized for charter-bound continuation")

    workers_value = design_report["workers"]
    if not isinstance(workers_value, list) or not workers_value:
        raise NativeBridgeError("design report workers must be a non-empty array")
    workers: dict[str, dict[str, Any]] = {}
    dependencies: dict[str, list[str]] = {}
    scope_owners: list[tuple[str, str]] = []
    wall_seconds: dict[str, int] = {}
    token_total = 0
    cost_total = 0
    for index, worker in enumerate(workers_value):
        label = f"design report worker {index}"
        if not isinstance(worker, Mapping):
            raise NativeBridgeError(f"{label} must be an object")
        exact_keys(
            worker,
            {
                "worker_id",
                "outcome",
                "requested_model",
                "requested_reasoning",
                "depends_on",
                "write_scopes",
                "budget",
            },
            label,
        )
        worker_id = text(worker["worker_id"], f"{label}.worker_id")
        if worker_id in workers:
            raise NativeBridgeError("design report worker IDs must be unique")
        text(worker["outcome"], f"{label}.outcome")
        if (
            worker["requested_model"] != cell.get("requested_worker_model")
            or worker["requested_reasoning"] != cell.get("requested_worker_reasoning")
        ):
            errors.append(f"worker {worker_id} does not use the packet-bound Luna/max route")
        dependencies[worker_id] = string_list(
            worker["depends_on"], f"{label}.depends_on", allow_empty=True
        )
        scopes = string_list(worker["write_scopes"], f"{label}.write_scopes")
        for scope_index, scope in enumerate(scopes):
            scope_owners.append(
                (validate_writer_scope(scope, f"{label}.write_scopes[{scope_index}]"), worker_id)
            )
        allocated = worker_budget(worker["budget"], f"{label}.budget")
        token_total += allocated["max_tokens"]
        cost_total += allocated["max_cost_microusd"]
        wall_seconds[worker_id] = allocated["max_wall_seconds"]
        workers[worker_id] = dict(worker)

    worker_ids = set(workers)
    for worker_id, requirements in dependencies.items():
        unknown = set(requirements) - worker_ids
        if worker_id in requirements or unknown:
            errors.append(f"worker {worker_id} has invalid dependencies")
    dependency_references_valid = not any(
        set(values) - worker_ids for values in dependencies.values()
    )
    dependency_cycle = dependency_references_valid and has_dependency_cycle(dependencies)
    if dependency_cycle:
        errors.append("worker dependency graph contains a cycle")

    active_cap = context.get("active_worker_concurrency_cap")
    declared_cap = cell.get("declared_worker_slots")
    if (
        not isinstance(active_cap, int)
        or isinstance(active_cap, bool)
        or not isinstance(declared_cap, int)
        or isinstance(declared_cap, bool)
        or len(workers) > min(active_cap, declared_cap)
    ):
        errors.append("worker plan exceeds packet-bound concurrency")

    manager_budget = manager_packet.get("budget")
    if not isinstance(manager_budget, Mapping):
        raise NativeBridgeError("manager packet lacks budget")
    critical_wall = (
        dependency_critical_wall_seconds(dependencies, wall_seconds)
        if dependency_references_valid and not dependency_cycle
        else manager_budget.get("max_wall_seconds", -1) + 1
    )
    if (
        token_total > manager_budget.get("max_tokens", -1)
        or cost_total > manager_budget.get("max_cost_microusd", -1)
        or critical_wall > manager_budget.get("max_wall_seconds", -1)
    ):
        errors.append("worker plan exceeds packet-bound budget")

    for first_index, (first_scope, first_owner) in enumerate(scope_owners):
        for second_scope, second_owner in scope_owners[first_index + 1 :]:
            if first_owner != second_owner and scope_conflicts(first_scope, second_scope):
                errors.append(
                    f"writer scopes overlap between {first_owner} and {second_owner}"
                )

    assignments_value = design_report["requirement_assignments"]
    if not isinstance(assignments_value, list):
        raise NativeBridgeError("requirement_assignments must be an array")
    assigned_requirements: list[str] = []
    assigned_checks: set[str] = set()
    assigned_workers: set[str] = set()
    for index, assignment in enumerate(assignments_value):
        label = f"requirement assignment {index}"
        if not isinstance(assignment, Mapping):
            raise NativeBridgeError(f"{label} must be an object")
        exact_keys(
            assignment,
            {"requirement", "owner_worker_ids", "acceptance_checks"},
            label,
        )
        assigned_requirements.append(text(assignment["requirement"], f"{label}.requirement"))
        owners = string_list(assignment["owner_worker_ids"], f"{label}.owner_worker_ids")
        checks = string_list(assignment["acceptance_checks"], f"{label}.acceptance_checks")
        if set(owners) - worker_ids:
            errors.append(f"{label} names an unknown worker")
        assigned_workers.update(owners)
        assigned_checks.update(checks)
    required_requirements = cell.get("mandatory_requirements")
    required_checks = cell.get("acceptance_checks")
    if (
        assigned_requirements != list(required_requirements or [])
        or len(assigned_requirements) != len(set(assigned_requirements))
    ):
        errors.append("mandatory requirements are not assigned exactly in packet order")
    if assigned_checks != set(required_checks or []):
        errors.append("acceptance checks do not exactly cover the packet contract")

    capability_values = design_report["capability_assignments"]
    if not isinstance(capability_values, list):
        raise NativeBridgeError("capability_assignments must be an array")
    assigned_capabilities: list[str] = []
    for index, assignment in enumerate(capability_values):
        label = f"capability assignment {index}"
        if not isinstance(assignment, Mapping):
            raise NativeBridgeError(f"{label} must be an object")
        exact_keys(assignment, {"capability_id", "worker_ids"}, label)
        assigned_capabilities.append(text(assignment["capability_id"], f"{label}.capability_id"))
        owners = string_list(assignment["worker_ids"], f"{label}.worker_ids")
        if set(owners) - worker_ids:
            errors.append(f"{label} names an unknown worker")
        assigned_workers.update(owners)
    if (
        assigned_capabilities != list(cell.get("required_capabilities") or [])
        or len(assigned_capabilities) != len(set(assigned_capabilities))
    ):
        errors.append("required capabilities are not assigned exactly in packet order")
    if assigned_workers != worker_ids:
        errors.append("every worker must own a requirement or required capability")

    for field in (
        "unresolved_dependencies",
        "protected_actions",
        "scope_variances",
        "manager_direct_labor_variances",
    ):
        values = string_list(design_report[field], f"design report {field}", allow_empty=True)
        if values:
            errors.append(f"design report {field} must be empty for auto-continuation")

    errors = sorted(set(errors))
    return {
        "$schema": DESIGN_RECEIPT_SCHEMA,
        "status": "continue_allowed" if not errors else "blocked",
        "continue_allowed": not errors,
        "manager_packet_digest": packet_digest,
        "report_digest": report_digest,
        "cell_id": cell["cell_id"],
        "attempt_id": manager_packet["attempt_id"],
        "authorized_worker_count": len(workers) if not errors else 0,
        "errors": errors,
    }


def initial_user_text(readback: Mapping[str, Any]) -> tuple[str, str, str]:
    thread = readback.get("thread")
    turns = readback.get("turns")
    if not isinstance(thread, Mapping) or not isinstance(turns, list) or not turns:
        raise NativeBridgeError("thread readback is incomplete")
    thread_id = text(thread.get("id"), "readback.thread.id")
    host_id = text(thread.get("hostId"), "readback.thread.hostId")
    ordered: list[tuple[float, Mapping[str, Any]]] = []
    for index, turn in enumerate(turns):
        if not isinstance(turn, Mapping):
            raise NativeBridgeError(f"thread turn {index} must be an object")
        started_at = turn.get("startedAt")
        if (
            not isinstance(started_at, (int, float))
            or isinstance(started_at, bool)
            or not math.isfinite(started_at)
        ):
            raise NativeBridgeError("every thread turn needs authoritative startedAt ordering")
        ordered.append((float(started_at), turn))
    earliest = min(item[0] for item in ordered)
    earliest_turns = [turn for started_at, turn in ordered if started_at == earliest]
    if len(earliest_turns) != 1:
        raise NativeBridgeError("initial thread turn ordering is ambiguous")
    items = earliest_turns[0].get("items")
    if not isinstance(items, list):
        raise NativeBridgeError("initial thread turn items must be an array")
    initial_messages = [
        item
        for item in items
        if isinstance(item, Mapping) and item.get("type") == "userMessage"
    ]
    if len(initial_messages) != 1:
        raise NativeBridgeError("initial thread turn must contain exactly one user message")
    parts = initial_messages[0].get("content")
    if not isinstance(parts, list) or not parts:
        raise NativeBridgeError("initial user message has no content")
    if any(
        not isinstance(part, Mapping)
        or part.get("type") != "text"
        or not isinstance(part.get("text"), str)
        for part in parts
    ):
        raise NativeBridgeError("initial user message has unsupported content")
    rendered = "".join(part["text"] for part in parts)
    if not rendered:
        raise NativeBridgeError("initial user message is empty")
    return thread_id, host_id, rendered


def validate_observation(
    value: Any, readbacks: list[Any]
) -> tuple[str, list[str]]:
    if not isinstance(value, Mapping):
        raise NativeBridgeError("candidate observation must be an object")
    exact_keys(
        value,
        {
            "$schema",
            "source",
            "observed_at",
            "listing_complete",
            "listing_limit",
            "returned_count",
            "listed_thread_ids",
        },
        "candidate observation",
    )
    if value["$schema"] != RECONCILIATION_OBSERVATION_SCHEMA:
        raise NativeBridgeError("candidate observation schema is unsupported")
    if value["source"] != "codex_app__list_threads" or value["listing_complete"] is not True:
        raise NativeBridgeError("candidate observation must attest a complete native task listing")
    observed_at = text(value["observed_at"], "candidate observation.observed_at")
    try:
        timestamp = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NativeBridgeError("candidate observation time must be RFC3339") from exc
    if timestamp.tzinfo is None:
        raise NativeBridgeError("candidate observation time must include a timezone")
    listing_limit = value["listing_limit"]
    returned_count = value["returned_count"]
    if (
        not isinstance(listing_limit, int)
        or isinstance(listing_limit, bool)
        or listing_limit < 1
        or not isinstance(returned_count, int)
        or isinstance(returned_count, bool)
        or returned_count < 0
        or returned_count > listing_limit
    ):
        raise NativeBridgeError("candidate observation counts are invalid")
    listed = value["listed_thread_ids"]
    if (
        not isinstance(listed, list)
        or any(not isinstance(item, str) or not item or item != item.strip() for item in listed)
        or listed != sorted(set(listed))
        or returned_count != len(listed)
    ):
        raise NativeBridgeError("listed task identities must be complete, unique, and sorted")
    read_ids: list[str] = []
    for index, readback in enumerate(readbacks):
        if not isinstance(readback, Mapping):
            raise NativeBridgeError(f"candidate readback {index} must be an object")
        thread = readback.get("thread")
        if not isinstance(thread, Mapping):
            raise NativeBridgeError(f"candidate readback {index} has no thread identity")
        read_ids.append(text(thread.get("id"), f"candidate readback {index} thread id"))
    if sorted(read_ids) != listed or len(read_ids) != len(set(read_ids)):
        raise NativeBridgeError("candidate readbacks must cover the complete listed task set exactly")
    return observed_at, listed


def creation_receipt_from_readback(
    dispatch: Mapping[str, Any], readback: Mapping[str, Any]
) -> dict[str, Any]:
    thread_id, host_id, first_text = initial_user_text(readback)
    expected_prompt = dispatch.get("arguments", {}).get("prompt")
    if first_text != expected_prompt or dispatch.get("marker") not in first_text:
        raise NativeBridgeError("initial task prompt does not match dispatch packet")
    return {
        "$schema": CREATION_RECEIPT_SCHEMA,
        "status": "host_created",
        "dispatch_digest": dispatch["dispatch_digest"],
        "message_key": dispatch["message_key"],
        "project_id": dispatch["project_id"],
        "cell_id": dispatch["cell_id"],
        "task_id": thread_id,
        "thread_id": thread_id,
        "host_id": host_id,
        "tool": "codex_app__create_thread",
        "initial_prompt_sha256": dispatch["initial_prompt_sha256"],
        "settlement_eligible": True,
    }


def verify_dispatch(dispatch: Mapping[str, Any]) -> str:
    retained = dict(dispatch)
    supplied_digest = retained.pop("dispatch_digest", None)
    if (
        dispatch.get("$schema") != DISPATCH_SCHEMA
        or supplied_digest != digest_text(canonical_json(retained))
        or dispatch.get("initial_prompt_sha256")
        != digest_text(dispatch.get("arguments", {}).get("prompt", ""))
    ):
        raise NativeBridgeError("dispatch packet digest does not verify")
    return supplied_digest


def reconcile_candidates(
    dispatch: Mapping[str, Any], candidate_set: Mapping[str, Any]
) -> dict[str, Any]:
    verify_dispatch(dispatch)
    exact_keys(
        candidate_set,
        {"$schema", "phase", "observation", "readbacks"},
        "candidate set",
    )
    if candidate_set["$schema"] != RECONCILIATION_INPUT_SCHEMA:
        raise NativeBridgeError("candidate set schema is unsupported")
    phase = candidate_set["phase"]
    if phase not in {"pre_create", "ambiguous_recovery"}:
        raise NativeBridgeError("candidate reconciliation phase is unsupported")
    readbacks = candidate_set["readbacks"]
    if not isinstance(readbacks, list):
        raise NativeBridgeError("candidate readbacks must be an array")
    observed_at, listed_thread_ids = validate_observation(
        candidate_set["observation"], readbacks
    )
    marker = dispatch["marker"]
    matches: list[dict[str, Any]] = []
    invalid_marker_candidates: list[str] = []
    seen: set[tuple[str, str]] = set()
    for index, value in enumerate(readbacks):
        if not isinstance(value, Mapping):
            raise NativeBridgeError(f"candidate readback {index} must be an object")
        if marker not in canonical_json(value):
            continue
        try:
            receipt = creation_receipt_from_readback(dispatch, value)
        except NativeBridgeError:
            invalid_marker_candidates.append(str(index))
            continue
        identity = (receipt["host_id"], receipt["thread_id"])
        if identity in seen:
            continue
        seen.add(identity)
        matches.append(receipt)
    status: str
    action: str
    recovered: dict[str, Any] | None = None
    if invalid_marker_candidates or len(matches) > 1:
        status = "conflict"
        action = "block_and_escalate"
    elif len(matches) == 1:
        status = "recovered"
        action = "bind_launch_attempt_and_settle"
        recovered = matches[0]
    else:
        if phase == "pre_create":
            status = "absent"
            action = "prepare_launch_attempt_before_create"
        else:
            status = "ambiguous"
            action = "require_separately_authorized_absence_decision"
    return {
        "$schema": RECONCILIATION_RECEIPT_SCHEMA,
        "dispatch_digest": dispatch["dispatch_digest"],
        "message_key": dispatch["message_key"],
        "phase": phase,
        "observation_sha256": digest_text(canonical_json(candidate_set["observation"])),
        "observed_at": observed_at,
        "listed_thread_ids": listed_thread_ids,
        "status": status,
        "action": action,
        "create_allowed": phase == "pre_create" and status == "absent",
        "matching_tasks": len(matches),
        "invalid_marker_candidates": invalid_marker_candidates,
        "recovered_creation_receipt": recovered,
    }


def verify_creation(
    dispatch: Mapping[str, Any], create_result: Mapping[str, Any], readback: Mapping[str, Any]
) -> dict[str, Any]:
    supplied_digest = verify_dispatch(dispatch)
    if "clientThreadId" in create_result and "threadId" not in create_result:
        client_id = text(create_result["clientThreadId"], "create_result.clientThreadId")
        return {
            "$schema": CREATION_RECEIPT_SCHEMA,
            "status": "setup_pending",
            "dispatch_digest": supplied_digest,
            "message_key": dispatch["message_key"],
            "client_thread_id": client_id,
            "settlement_eligible": False,
        }
    thread_id = text(create_result.get("threadId"), "create_result.threadId")
    host_id = text(create_result.get("hostId"), "create_result.hostId")
    receipt = creation_receipt_from_readback(dispatch, readback)
    if thread_id != receipt["thread_id"] or host_id != receipt["host_id"]:
        raise NativeBridgeError("create result and readback identity conflict")
    if receipt["dispatch_digest"] != supplied_digest:
        raise NativeBridgeError("creation receipt dispatch digest conflicts")
    return receipt


def command_compile(args: argparse.Namespace) -> int:
    try:
        kernel = RECONCILE.verify_kernel_document(Path(args.kernel))
        claim = read_canonical(Path(args.claim), "command claim")
        binding = read_canonical(Path(args.binding), "host binding")
        print(canonical_json(build_dispatch(kernel, claim, binding)))
        return 0
    except (NativeBridgeError, RECONCILE.ReconciliationError, RECONCILE.KERNEL.KernelError, OSError) as exc:
        print(canonical_json({"ok": False, "errors": [str(exc)]}))
        return 2


def command_verify(args: argparse.Namespace) -> int:
    try:
        dispatch = read_canonical(Path(args.dispatch), "dispatch packet")
        create_result = read_canonical(Path(args.create_result), "create result")
        readback = read_canonical(Path(args.readback), "thread readback")
        print(canonical_json(verify_creation(dispatch, create_result, readback)))
        return 0
    except (NativeBridgeError, OSError) as exc:
        print(canonical_json({"ok": False, "errors": [str(exc)]}))
        return 2


def command_reconcile(args: argparse.Namespace) -> int:
    try:
        dispatch = read_canonical(Path(args.dispatch), "dispatch packet")
        candidate_set = read_canonical(Path(args.candidate_set), "candidate set")
        print(canonical_json(reconcile_candidates(dispatch, candidate_set)))
        return 0
    except (NativeBridgeError, OSError) as exc:
        print(canonical_json({"ok": False, "errors": [str(exc)]}))
        return 2


def command_verify_design(args: argparse.Namespace) -> int:
    try:
        manager_packet = read_canonical(Path(args.manager_packet), "manager packet")
        design_report = read_canonical(Path(args.design_report), "design report")
        receipt = verify_design_continuation(manager_packet, design_report)
        print(canonical_json(receipt))
        return 0 if receipt["continue_allowed"] else 1
    except (NativeBridgeError, OSError) as exc:
        print(canonical_json({"ok": False, "errors": [str(exc)]}))
        return 2


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    compile_parser = sub.add_parser("compile")
    compile_parser.add_argument("--kernel", required=True)
    compile_parser.add_argument("--claim", required=True)
    compile_parser.add_argument("--binding", required=True)
    compile_parser.set_defaults(handler=command_compile)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--dispatch", required=True)
    verify_parser.add_argument("--create-result", required=True)
    verify_parser.add_argument("--readback", required=True)
    verify_parser.set_defaults(handler=command_verify)
    reconcile_parser = sub.add_parser("reconcile")
    reconcile_parser.add_argument("--dispatch", required=True)
    reconcile_parser.add_argument("--candidate-set", required=True)
    reconcile_parser.set_defaults(handler=command_reconcile)
    design_parser = sub.add_parser("verify-design")
    design_parser.add_argument("--manager-packet", required=True)
    design_parser.add_argument("--design-report", required=True)
    design_parser.set_defaults(handler=command_verify_design)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
