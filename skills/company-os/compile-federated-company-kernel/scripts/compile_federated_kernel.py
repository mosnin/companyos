#!/usr/bin/env python3
"""Compile and verify a feature-off federated Company OS kernel."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable


SKILL_ROOT = Path(__file__).resolve().parents[1]
COMPANY_OS_ROOT = SKILL_ROOT.parent
DEFAULT_MECHANISMS = SKILL_ROOT / "references" / "federated-mechanism-contracts.json"
DEFAULT_SOURCE_REGISTRY = (
    COMPANY_OS_ROOT / "source-intelligence" / "references" / "source-intelligence-registry.json"
)

REQUEST_SCHEMA = "company-os.federated-kernel-request.v1"
KERNEL_SCHEMA = "company-os.federated-company-kernel.v1"
MECHANISM_SCHEMA = "company-os.federated-mechanism-contracts.v1"
SOURCE_SCHEMA = "company-os.source-intelligence-registry.v1"
ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PIN_RE = re.compile(r"^[0-9a-f]{40}$")
PLACEMENTS = {"execution_hot_path", "shared_service", "quality_service", "offline_learning"}
RISK_TIERS = {"low", "medium", "high", "consequential"}
PROTECTED_ACTIONS = {
    "external-communication",
    "financial-commitment",
    "legal-commitment",
    "production-write",
}


class KernelError(ValueError):
    """A closed-contract validation failure."""


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_value(value: Any) -> str:
    return digest_bytes(canonical_bytes(value))


def read_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file():
        raise KernelError(f"{label} must be a regular non-symlink file: {path}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise KernelError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise KernelError(f"{label} must be a JSON object")
    return value, raw


def require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise KernelError(f"{label} keys differ: missing={missing} extra={extra}")


def require_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise KernelError(f"{label} must be a lowercase hyphenated ID")
    return value


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise KernelError(f"{label} must be non-empty trimmed text")
    return value


def require_int(value: Any, low: int, high: int, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise KernelError(f"{label} must be an integer from {low} to {high}")
    return value


def require_ratio(value: Any, label: str, *, positive: bool = False) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise KernelError(f"{label} must be a finite number")
    number = float(value)
    lower = 0.0 if not positive else 0.000001
    if number < lower or number > 1.0:
        raise KernelError(f"{label} must be between {lower} and 1")
    return number


def require_string_list(value: Any, label: str, *, ids: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise KernelError(f"{label} must be an array")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(require_id(item, f"{label}[{index}]") if ids else require_text(item, f"{label}[{index}]"))
    if len(result) != len(set(result)):
        raise KernelError(f"{label} must not contain duplicates")
    return sorted(result)


def index_unique(values: Iterable[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in values:
        item_id = value[key]
        if item_id in result:
            raise KernelError(f"duplicate {label} {item_id}")
        result[item_id] = value
    return result


def validate_mechanisms(
    mechanism_path: Path = DEFAULT_MECHANISMS,
    source_registry_path: Path = DEFAULT_SOURCE_REGISTRY,
) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    mechanisms, mechanism_raw = read_json(mechanism_path, "mechanism registry")
    sources, source_raw = read_json(source_registry_path, "source intelligence registry")
    require_exact_keys(
        mechanisms,
        {"$schema", "registry_version", "source_intelligence_registry_sha256", "contracts"},
        "mechanism registry",
    )
    if mechanisms["$schema"] != MECHANISM_SCHEMA or mechanisms["registry_version"] != 1:
        raise KernelError("unsupported mechanism registry schema or version")
    if sources.get("$schema") != SOURCE_SCHEMA:
        raise KernelError("unsupported source intelligence registry schema")
    source_digest = digest_bytes(source_raw)
    if mechanisms["source_intelligence_registry_sha256"] != source_digest:
        raise KernelError("mechanism registry does not bind the exact source intelligence registry")
    if not isinstance(mechanisms["contracts"], list) or not mechanisms["contracts"]:
        raise KernelError("mechanism registry must contain contracts")
    if not isinstance(sources.get("records"), list):
        raise KernelError("source intelligence registry records are invalid")
    source_index = index_unique(sources["records"], "source_id", "source record")
    contract_ids: set[str] = set()
    for index, contract in enumerate(mechanisms["contracts"]):
        label = f"contracts[{index}]"
        if not isinstance(contract, dict):
            raise KernelError(f"{label} must be an object")
        require_exact_keys(contract, {"contract_id", "placement", "source_bindings", "adopt", "reject"}, label)
        contract_id = require_id(contract["contract_id"], f"{label}.contract_id")
        if contract_id in contract_ids:
            raise KernelError(f"duplicate mechanism contract {contract_id}")
        contract_ids.add(contract_id)
        if contract["placement"] not in PLACEMENTS:
            raise KernelError(f"{label}.placement is unsupported")
        adopt = require_string_list(contract["adopt"], f"{label}.adopt")
        reject = require_string_list(contract["reject"], f"{label}.reject")
        if not adopt or not reject or set(adopt).intersection(reject):
            raise KernelError(f"{label} must have distinct adopted and rejected mechanisms")
        bindings = contract["source_bindings"]
        if not isinstance(bindings, list) or not bindings:
            raise KernelError(f"{label}.source_bindings must be non-empty")
        seen_sources: set[str] = set()
        for binding_index, binding in enumerate(bindings):
            binding_label = f"{label}.source_bindings[{binding_index}]"
            if not isinstance(binding, dict):
                raise KernelError(f"{binding_label} must be an object")
            require_exact_keys(binding, {"source_id", "pin"}, binding_label)
            source_id = require_id(binding["source_id"], f"{binding_label}.source_id")
            if source_id in seen_sources:
                raise KernelError(f"{label} repeats source {source_id}")
            seen_sources.add(source_id)
            if not isinstance(binding["pin"], str) or not PIN_RE.fullmatch(binding["pin"]):
                raise KernelError(f"{binding_label}.pin must be a full Git commit")
            source = source_index.get(source_id)
            if source is None or source.get("pin") != binding["pin"]:
                raise KernelError(f"{binding_label} does not resolve to the exact source pin")
            if source.get("review_decision") != "reviewed_static_no_integration":
                raise KernelError(f"{binding_label} source is not in the expected research-only state")
            if not SHA256_RE.fullmatch(str(source.get("review_evidence_sha256", ""))):
                raise KernelError(f"{binding_label} source lacks review evidence")
    return mechanisms, sources, digest_bytes(mechanism_raw), source_digest


def validate_request(value: dict[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        value,
        {
            "$schema",
            "company_id",
            "objective",
            "target_capacity_agents",
            "initial_active_concurrency_limit",
            "authority",
            "persistence",
            "quality_targets",
            "business_units",
        },
        "request",
    )
    if value["$schema"] != REQUEST_SCHEMA:
        raise KernelError("unsupported kernel request schema")
    company_id = require_id(value["company_id"], "company_id")
    target_capacity = require_int(value["target_capacity_agents"], 3, 100000, "target_capacity_agents")
    active_limit = require_int(
        value["initial_active_concurrency_limit"], 3, target_capacity, "initial_active_concurrency_limit"
    )

    objective = value["objective"]
    if not isinstance(objective, dict):
        raise KernelError("objective must be an object")
    require_exact_keys(objective, {"id", "statement", "metric", "target", "horizon"}, "objective")
    normalized_objective = {
        "id": require_id(objective["id"], "objective.id"),
        "statement": require_text(objective["statement"], "objective.statement"),
        "metric": require_text(objective["metric"], "objective.metric"),
        "target": require_text(objective["target"], "objective.target"),
        "horizon": require_text(objective["horizon"], "objective.horizon"),
    }

    authority = value["authority"]
    if not isinstance(authority, dict):
        raise KernelError("authority must be an object")
    require_exact_keys(
        authority,
        {"human_approval_actions", "executive_exception_actions", "delegated_risk_tiers"},
        "authority",
    )
    human_actions = require_string_list(authority["human_approval_actions"], "authority.human_approval_actions", ids=True)
    if not PROTECTED_ACTIONS.issubset(human_actions):
        raise KernelError(f"human approval must cover protected actions {sorted(PROTECTED_ACTIONS)}")
    exception_actions = require_string_list(
        authority["executive_exception_actions"], "authority.executive_exception_actions", ids=True
    )
    delegated_tiers = require_string_list(
        authority["delegated_risk_tiers"], "authority.delegated_risk_tiers"
    )
    if not set(delegated_tiers).issubset(RISK_TIERS - {"consequential"}):
        raise KernelError("consequential work cannot be delegated by default")

    persistence = value["persistence"]
    if not isinstance(persistence, dict):
        raise KernelError("persistence must be an object")
    require_exact_keys(persistence, {"adapter", "dsn_env", "schema"}, "persistence")
    adapter = persistence["adapter"]
    if adapter not in {"sqlite", "postgresql"}:
        raise KernelError("persistence.adapter must be sqlite or postgresql")
    schema = require_id(persistence["schema"], "persistence.schema")
    dsn_env = persistence["dsn_env"]
    if adapter == "postgresql":
        if not isinstance(dsn_env, str) or not ENV_RE.fullmatch(dsn_env):
            raise KernelError("postgresql persistence requires an environment-variable reference")
    elif dsn_env is not None:
        raise KernelError("sqlite persistence must use null dsn_env")

    quality = value["quality_targets"]
    if not isinstance(quality, dict):
        raise KernelError("quality_targets must be an object")
    quality_keys = {
        "first_pass_acceptance_min",
        "rework_max",
        "write_collisions_max",
        "recovery_rate_min",
        "luna_labor_share_min",
        "sol_overhead_share_max",
        "scale_efficiency_min",
        "utilization_ceiling",
    }
    require_exact_keys(quality, quality_keys, "quality_targets")
    normalized_quality = {
        "first_pass_acceptance_min": require_ratio(
            quality["first_pass_acceptance_min"], "quality_targets.first_pass_acceptance_min", positive=True
        ),
        "rework_max": require_ratio(quality["rework_max"], "quality_targets.rework_max"),
        "write_collisions_max": require_int(
            quality["write_collisions_max"], 0, 1000000, "quality_targets.write_collisions_max"
        ),
        "recovery_rate_min": require_ratio(
            quality["recovery_rate_min"], "quality_targets.recovery_rate_min", positive=True
        ),
        "luna_labor_share_min": require_ratio(
            quality["luna_labor_share_min"], "quality_targets.luna_labor_share_min", positive=True
        ),
        "sol_overhead_share_max": require_ratio(
            quality["sol_overhead_share_max"], "quality_targets.sol_overhead_share_max", positive=True
        ),
        "scale_efficiency_min": require_ratio(
            quality["scale_efficiency_min"], "quality_targets.scale_efficiency_min", positive=True
        ),
        "utilization_ceiling": require_ratio(
            quality["utilization_ceiling"], "quality_targets.utilization_ceiling", positive=True
        ),
    }
    if normalized_quality["first_pass_acceptance_min"] < 0.85:
        raise KernelError("first-pass acceptance target must be at least 0.85")
    if normalized_quality["rework_max"] > 0.20:
        raise KernelError("rework target must be at most 0.20")
    if normalized_quality["write_collisions_max"] != 0:
        raise KernelError("write collision target must be zero")
    if normalized_quality["recovery_rate_min"] < 1.0:
        raise KernelError("recovery target must be 1.0")
    if normalized_quality["utilization_ceiling"] > 0.75:
        raise KernelError("knowledge-work utilization ceiling must be at most 0.75")

    units = value["business_units"]
    if not isinstance(units, list) or not units:
        raise KernelError("business_units must be a non-empty array")
    normalized_units: list[dict[str, Any]] = []
    unit_ids: set[str] = set()
    program_ids: set[str] = set()
    workstream_ids: set[str] = set()
    for unit_index, unit in enumerate(units):
        label = f"business_units[{unit_index}]"
        if not isinstance(unit, dict):
            raise KernelError(f"{label} must be an object")
        require_exact_keys(unit, {"id", "mission", "budget_share_percent", "programs"}, label)
        unit_id = require_id(unit["id"], f"{label}.id")
        if unit_id in unit_ids:
            raise KernelError(f"duplicate business unit {unit_id}")
        unit_ids.add(unit_id)
        unit_budget = require_int(unit["budget_share_percent"], 1, 100, f"{label}.budget_share_percent")
        programs = unit["programs"]
        if not isinstance(programs, list) or not programs:
            raise KernelError(f"{label}.programs must be non-empty")
        normalized_programs: list[dict[str, Any]] = []
        for program_index, program in enumerate(programs):
            program_label = f"{label}.programs[{program_index}]"
            if not isinstance(program, dict):
                raise KernelError(f"{program_label} must be an object")
            require_exact_keys(
                program, {"id", "objective", "risk_tier", "budget_share_percent", "workstreams"}, program_label
            )
            program_id = require_id(program["id"], f"{program_label}.id")
            if program_id in program_ids:
                raise KernelError(f"duplicate program {program_id}")
            program_ids.add(program_id)
            risk_tier = program["risk_tier"]
            if risk_tier not in RISK_TIERS:
                raise KernelError(f"{program_label}.risk_tier is unsupported")
            program_budget = require_int(
                program["budget_share_percent"], 1, 100, f"{program_label}.budget_share_percent"
            )
            workstreams = program["workstreams"]
            if not isinstance(workstreams, list) or not workstreams:
                raise KernelError(f"{program_label}.workstreams must be non-empty")
            normalized_workstreams: list[dict[str, Any]] = []
            for stream_index, stream in enumerate(workstreams):
                stream_label = f"{program_label}.workstreams[{stream_index}]"
                if not isinstance(stream, dict):
                    raise KernelError(f"{stream_label} must be an object")
                require_exact_keys(
                    stream,
                    {
                        "id",
                        "deliverable",
                        "complexity",
                        "uncertainty",
                        "repetitiveness",
                        "estimated_tasks",
                        "parallel_width",
                        "artifact_kinds",
                        "required_capabilities",
                    },
                    stream_label,
                )
                stream_id = require_id(stream["id"], f"{stream_label}.id")
                if stream_id in workstream_ids:
                    raise KernelError(f"duplicate workstream {stream_id}")
                workstream_ids.add(stream_id)
                estimated_tasks = require_int(
                    stream["estimated_tasks"], 1, 100000, f"{stream_label}.estimated_tasks"
                )
                parallel_width = require_int(
                    stream["parallel_width"], 1, estimated_tasks, f"{stream_label}.parallel_width"
                )
                normalized_workstreams.append(
                    {
                        "id": stream_id,
                        "deliverable": require_text(stream["deliverable"], f"{stream_label}.deliverable"),
                        "complexity": require_int(stream["complexity"], 1, 5, f"{stream_label}.complexity"),
                        "uncertainty": require_int(stream["uncertainty"], 1, 5, f"{stream_label}.uncertainty"),
                        "repetitiveness": require_int(
                            stream["repetitiveness"], 1, 5, f"{stream_label}.repetitiveness"
                        ),
                        "estimated_tasks": estimated_tasks,
                        "parallel_width": parallel_width,
                        "artifact_kinds": require_string_list(
                            stream["artifact_kinds"], f"{stream_label}.artifact_kinds", ids=True
                        ),
                        "required_capabilities": require_string_list(
                            stream["required_capabilities"], f"{stream_label}.required_capabilities", ids=True
                        ),
                    }
                )
            normalized_programs.append(
                {
                    "id": program_id,
                    "objective": require_text(program["objective"], f"{program_label}.objective"),
                    "risk_tier": risk_tier,
                    "budget_share_percent": program_budget,
                    "workstreams": sorted(normalized_workstreams, key=lambda item: item["id"]),
                }
            )
        if sum(program["budget_share_percent"] for program in normalized_programs) != 100:
            raise KernelError(f"{label} program budget shares must total 100")
        normalized_units.append(
            {
                "id": unit_id,
                "mission": require_text(unit["mission"], f"{label}.mission"),
                "budget_share_percent": unit_budget,
                "programs": sorted(normalized_programs, key=lambda item: item["id"]),
            }
        )
    if sum(unit["budget_share_percent"] for unit in normalized_units) != 100:
        raise KernelError("business unit budget shares must total 100")
    if len(normalized_units) > 9:
        raise KernelError("executive span exceeds nine business-unit control cells")

    return {
        "$schema": REQUEST_SCHEMA,
        "company_id": company_id,
        "objective": normalized_objective,
        "target_capacity_agents": target_capacity,
        "initial_active_concurrency_limit": active_limit,
        "authority": {
            "human_approval_actions": human_actions,
            "executive_exception_actions": exception_actions,
            "delegated_risk_tiers": sorted(delegated_tiers),
        },
        "persistence": {"adapter": adapter, "dsn_env": dsn_env, "schema": schema},
        "quality_targets": normalized_quality,
        "business_units": sorted(normalized_units, key=lambda item: item["id"]),
    }


def manager_span(workstream: dict[str, Any], risk_tier: str) -> int:
    pressure = max(workstream["complexity"], workstream["uncertainty"])
    if risk_tier in {"high", "consequential"} or pressure == 5:
        return 5
    if pressure == 4:
        return 6
    if pressure == 3:
        return 8
    return 12 if workstream["repetitiveness"] >= 4 else 10


def distribute(total: int, parts: int) -> list[int]:
    quotient, remainder = divmod(total, parts)
    return [quotient + (1 if index < remainder else 0) for index in range(parts)]


def compile_kernel(
    request: dict[str, Any],
    mechanisms: dict[str, Any],
    mechanism_digest: str,
    source_digest: str,
) -> dict[str, Any]:
    manager_cells: list[dict[str, Any]] = []
    program_cells: list[dict[str, Any]] = []
    unit_cells: list[dict[str, Any]] = []
    potential_worker_tasks = 0
    for unit in request["business_units"]:
        unit_cells.append(
            {
                "cell_id": f"unit-{unit['id']}",
                "cell_kind": "business_unit_control",
                "mission": unit["mission"],
                "budget_share_percent": unit["budget_share_percent"],
                "decision_mode": "exception_based",
                "activation_state": "planned",
            }
        )
        for program in unit["programs"]:
            program_manager_ids: list[str] = []
            for workstream in program["workstreams"]:
                span = manager_span(workstream, program["risk_tier"])
                active_demand = min(workstream["estimated_tasks"], workstream["parallel_width"])
                partitions = math.ceil(active_demand / span)
                worker_distribution = distribute(active_demand, partitions)
                task_distribution = distribute(workstream["estimated_tasks"], partitions)
                potential_worker_tasks += workstream["estimated_tasks"]
                for partition_index, (worker_slots, task_count) in enumerate(
                    zip(worker_distribution, task_distribution), start=1
                ):
                    manager_id = f"manager-{program['id']}-{workstream['id']}-{partition_index}"
                    program_manager_ids.append(manager_id)
                    manager_cells.append(
                        {
                            "cell_id": manager_id,
                            "cell_kind": "program_manager_partition",
                            "parent_program_id": program["id"],
                            "business_unit_id": unit["id"],
                            "workstream_id": workstream["id"],
                            "partition_index": partition_index,
                            "partition_count": partitions,
                            "deliverable": workstream["deliverable"],
                            "risk_tier": program["risk_tier"],
                            "direct_report_limit": span,
                            "declared_worker_slots": worker_slots,
                            "queued_task_count": task_count,
                            "requested_manager_model": "gpt-5.6-sol",
                            "requested_manager_reasoning": "xhigh",
                            "requested_worker_model": "gpt-5.6-luna",
                            "requested_worker_reasoning": "max",
                            "required_capabilities": workstream["required_capabilities"],
                            "artifact_kinds": workstream["artifact_kinds"],
                            "decision_mode": (
                                "analysis_only_human_decision"
                                if program["risk_tier"] == "consequential"
                                else "delegated_with_exception_escalation"
                            ),
                            "activation_state": "planned",
                        }
                    )
            program_cells.append(
                {
                    "cell_id": f"program-{program['id']}",
                    "cell_kind": "program_control",
                    "business_unit_id": unit["id"],
                    "program_id": program["id"],
                    "objective": program["objective"],
                    "risk_tier": program["risk_tier"],
                    "budget_share_percent_within_unit": program["budget_share_percent"],
                    "manager_partitions": sorted(program_manager_ids),
                    "activation_state": "planned",
                }
            )

    manager_count = len(manager_cells)
    active_limit = request["initial_active_concurrency_limit"]
    quality = request["quality_targets"]
    wind_down_reserve = max(1, math.ceil(active_limit * 0.10))
    oversight_ceiling = max(2, math.floor(active_limit * quality["sol_overhead_share_max"]))
    initial_manager_limit = min(manager_count, max(1, oversight_ceiling - 1))
    quality_reviewer_slots = 1
    initial_luna_limit = max(0, active_limit - wind_down_reserve - initial_manager_limit - quality_reviewer_slots)
    blockers = [
        "protected_launcher_unproven",
        "codex_native_runtime_adapter_unproven",
        "observed_model_and_token_telemetry_unproven",
        "distributed_cancellation_and_recovery_unproven",
    ]
    if request["persistence"]["adapter"] == "postgresql":
        blockers.append("postgresql_target_database_unverified")
    if initial_luna_limit < 1:
        blockers.append("initial_concurrency_cannot_admit_a_luna_worker")

    contracts = sorted(mechanisms["contracts"], key=lambda item: item["contract_id"])
    contracts_by_placement = {
        placement: [item["contract_id"] for item in contracts if item["placement"] == placement]
        for placement in sorted(PLACEMENTS)
    }
    scale_capacities = [10, 50, 100, 250, 500, 1000]
    if request["target_capacity_agents"] not in scale_capacities:
        scale_capacities.append(request["target_capacity_agents"])
    scale_ladder = []
    for capacity in sorted(set(scale_capacities)):
        if capacity > request["target_capacity_agents"]:
            continue
        scale_ladder.append(
            {
                "capacity_agents": capacity,
                "requires_new_admission_decision": capacity > active_limit,
                "first_pass_acceptance_min": quality["first_pass_acceptance_min"],
                "rework_max": quality["rework_max"],
                "write_collisions_max": quality["write_collisions_max"],
                "recovery_rate_min": quality["recovery_rate_min"],
                "luna_labor_share_min": quality["luna_labor_share_min"],
                "sol_overhead_share_max": quality["sol_overhead_share_max"],
                "scale_efficiency_min": quality["scale_efficiency_min"],
                "utilization_ceiling": quality["utilization_ceiling"],
                "required_sustained_windows": 3,
            }
        )

    kernel: dict[str, Any] = {
        "$schema": KERNEL_SCHEMA,
        "kernel_version": 1,
        "company_id": request["company_id"],
        "objective": request["objective"],
        "request_digest": digest_value(request),
        "source_request": request,
        "mechanism_registry_sha256": mechanism_digest,
        "source_intelligence_registry_sha256": source_digest,
        "operating_domains": [
            {
                "domain_id": "policy-and-capital",
                "authority": "founder_or_board",
                "purpose": "mission capital constitutional limits and material approvals",
            },
            {
                "domain_id": "coordination-and-operations",
                "authority": "executive_kernel_and_business_unit_cells",
                "purpose": "portfolio allocation admission interfaces and exception routing",
            },
            {
                "domain_id": "execution",
                "authority": "program_charters_and_task_packets",
                "purpose": "manager partitions and bounded worker delivery",
            },
            {
                "domain_id": "learning",
                "authority": "independent_evidence_and_promotion_decisions",
                "purpose": "evaluation trace diagnosis lessons and reversible experiments",
            },
        ],
        "authority": {
            **request["authority"],
            "routine_decision_mode": "delegated_within_signed_charter",
            "executive_reporting_mode": "exceptions_and_aggregated_outcomes_only",
            "self_approval": False,
        },
        "organization": {
            "executive_kernel": {
                "cell_id": f"company-{request['company_id']}",
                "cell_kind": "company_kernel",
                "direct_business_unit_count": len(unit_cells),
                "direct_report_limit": 9,
                "activation_state": "planned",
            },
            "business_unit_cells": sorted(unit_cells, key=lambda item: item["cell_id"]),
            "program_cells": sorted(program_cells, key=lambda item: item["cell_id"]),
            "manager_cells": sorted(manager_cells, key=lambda item: item["cell_id"]),
            "manager_partition_count": manager_count,
            "potential_worker_task_count": potential_worker_tasks,
            "topology_mode": "federated_recursive_cells",
            "executable_delegation_depth": 2,
        },
        "admission": {
            "target_capacity_agents": request["target_capacity_agents"],
            "initial_active_concurrency_limit": active_limit,
            "initial_active_manager_limit": initial_manager_limit,
            "initial_active_luna_limit": initial_luna_limit,
            "quality_reviewer_slots": quality_reviewer_slots,
            "wind_down_reserve_slots": wind_down_reserve,
            "utilization_ceiling": quality["utilization_ceiling"],
            "policy": "cell_local_wip_global_budget_and_backpressure",
            "scale_only_from_observed_accepted_throughput": True,
        },
        "persistence": {
            **request["persistence"],
            "authority_model": "append_only_events_transactional_queues_leases_and_materialized_views",
            "artifact_bytes": "content_addressed_external_store",
            "conversation_context_is_authority": False,
        },
        "shared_services": [
            {
                "service_id": "capability-router",
                "mode": "metadata_query_then_task_local_packet",
                "governing_layer": False,
            },
            {
                "service_id": "context-broker",
                "mode": "read_only_cited_evidence_projection",
                "governing_layer": False,
                "mechanism_contracts": contracts_by_placement["shared_service"],
            },
            {
                "service_id": "artifact-store",
                "mode": "content_addressed_immutable_outputs",
                "governing_layer": False,
            },
            {
                "service_id": "quality-service",
                "mode": "risk_tiered_artifact_specific_independent_review",
                "governing_layer": False,
                "mechanism_contracts": contracts_by_placement["quality_service"],
            },
            {
                "service_id": "telemetry-and-finance",
                "mode": "accepted_throughput_latency_cost_and_capacity",
                "governing_layer": False,
            },
        ],
        "execution_hot_path": [
            {"order": 1, "stage": "admit", "contract": "contract-transition-diagnostics"},
            {"order": 2, "stage": "reconcile-desired-observed", "contract": "desired-observed-host-reconciliation"},
            {"order": 3, "stage": "reserve-and-fence", "contract": "bounded-cell-reservation-and-adoption"},
            {"order": 4, "stage": "launch-and-readback", "contract": "role-intent-and-observed-readback"},
            {"order": 5, "stage": "execute-task-packet", "contract": "contract-transition-diagnostics"},
            {"order": 6, "stage": "append-observe-and-replay", "contract": "durable-event-cursor-and-replay"},
            {"order": 7, "stage": "independent-evaluate", "contract": "artifact-specific-transfer-evaluation"},
            {"order": 8, "stage": "settle-or-escalate", "contract": "contract-transition-diagnostics"},
        ],
        "offline_learning": {
            "mechanism_contracts": contracts_by_placement["offline_learning"],
            "may_dispatch": False,
            "may_accept": False,
            "may_promote": False,
            "promotion_requires": "independent_multi-company_decision",
        },
        "mechanism_bindings": [
            {
                "contract_id": item["contract_id"],
                "placement": item["placement"],
                "source_bindings": item["source_bindings"],
                "adopted_mechanisms": item["adopt"],
                "rejected_mechanisms": item["reject"],
            }
            for item in contracts
        ],
        "scale_ladder": scale_ladder,
        "activation": {
            "state": "planned",
            "execution_authorized": False,
            "runtime_authorized": False,
            "scheduler_authorized": False,
            "blockers": sorted(blockers),
        },
    }
    kernel["kernel_digest"] = digest_value(kernel)
    return kernel


def verify_kernel(
    request_path: Path,
    kernel_path: Path,
    mechanism_path: Path,
    source_registry_path: Path,
) -> dict[str, Any]:
    request_raw, _ = read_json(request_path, "kernel request")
    request = validate_request(request_raw)
    mechanisms, _sources, mechanism_digest, source_digest = validate_mechanisms(
        mechanism_path, source_registry_path
    )
    expected = compile_kernel(request, mechanisms, mechanism_digest, source_digest)
    actual, actual_raw = read_json(kernel_path, "compiled kernel")
    if actual_raw != canonical_bytes(actual):
        raise KernelError("compiled kernel bytes are not canonical JSON")
    if actual != expected:
        raise KernelError("compiled kernel does not reproduce from its request and registries")
    return {
        "ok": True,
        "kernel_digest": actual["kernel_digest"],
        "manager_partitions": actual["organization"]["manager_partition_count"],
        "potential_worker_tasks": actual["organization"]["potential_worker_task_count"],
        "target_capacity_agents": actual["admission"]["target_capacity_agents"],
        "execution_authorized": actual["activation"]["execution_authorized"],
    }


def command_compile(args: argparse.Namespace) -> int:
    try:
        request_raw, _ = read_json(Path(args.request), "kernel request")
        request = validate_request(request_raw)
        mechanisms, _sources, mechanism_digest, source_digest = validate_mechanisms(
            Path(args.mechanisms), Path(args.source_registry)
        )
        kernel = compile_kernel(request, mechanisms, mechanism_digest, source_digest)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
        temporary.write_bytes(canonical_bytes(kernel))
        os.replace(temporary, output)
        print(json.dumps({"ok": True, "output": str(output), "kernel_digest": kernel["kernel_digest"]}, sort_keys=True))
        return 0
    except (KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def command_verify(args: argparse.Namespace) -> int:
    try:
        receipt = verify_kernel(
            Path(args.request),
            Path(args.kernel),
            Path(args.mechanisms),
            Path(args.source_registry),
        )
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except (KernelError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, sort_keys=True))
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    compile_parser = subparsers.add_parser("compile", help="compile a feature-off federated kernel")
    compile_parser.add_argument("--request", required=True)
    compile_parser.add_argument("--output", required=True)
    compile_parser.add_argument("--mechanisms", default=str(DEFAULT_MECHANISMS))
    compile_parser.add_argument("--source-registry", default=str(DEFAULT_SOURCE_REGISTRY))
    compile_parser.set_defaults(handler=command_compile)
    verify_parser = subparsers.add_parser("verify", help="verify a compiled kernel")
    verify_parser.add_argument("--request", required=True)
    verify_parser.add_argument("--kernel", required=True)
    verify_parser.add_argument("--mechanisms", default=str(DEFAULT_MECHANISMS))
    verify_parser.add_argument("--source-registry", default=str(DEFAULT_SOURCE_REGISTRY))
    verify_parser.set_defaults(handler=command_verify)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
