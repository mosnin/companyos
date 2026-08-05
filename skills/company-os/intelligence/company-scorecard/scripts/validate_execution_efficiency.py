#!/usr/bin/env python3
"""Validate real Company OS execution-efficiency receipts.

The validator deliberately separates deliverable acceptance from hierarchy,
Luna, efficiency, and scale evidence. Missing host telemetry is valid only when
it is declared unavailable; it can never make an efficiency gate pass.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA = "company-os.execution-efficiency-receipt.v1"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
TIMING_FIELDS = (
    "program_start",
    "first_manager_dispatch",
    "first_worker_dispatch",
    "first_usable_result",
    "first_artifact_materialization",
    "final_acceptance",
)
USAGE_FIELDS = (
    "total_tokens",
    "luna_tokens",
    "sol_tokens",
    "cost_usd",
    "single_thread_baseline_sol_tokens",
    "single_thread_baseline_lead_time_seconds",
)
TOP_LEVEL_KEYS = {
    "schema",
    "program_id",
    "comparison_class",
    "status",
    "timing",
    "topology",
    "usage",
    "quality",
    "requirements",
    "requirement_results",
    "artifact_plan",
    "artifacts",
    "decision",
}
AUTHORITY_RANK = {"manager": 1, "master": 2, "user": 3}


class ReceiptError(ValueError):
    """Raised for a malformed receipt source."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _check_exact_keys(
    value: Any,
    expected: set[str],
    path: str,
    errors: list[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return {}
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing:
            errors.append(f"{path} missing keys: {', '.join(missing)}")
        if extra:
            errors.append(f"{path} has unknown keys: {', '.join(extra)}")
    return value


def _check_nonempty_string(value: Any, path: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} must be a non-empty string")
        return None
    return value


def _check_id(value: Any, path: str, errors: list[str]) -> str | None:
    result = _check_nonempty_string(value, path, errors)
    if result is not None and not ID_PATTERN.fullmatch(result):
        errors.append(f"{path} must be canonical lowercase ASCII ID")
    return result


def _check_string_list(
    value: Any,
    path: str,
    errors: list[str],
    *,
    allow_empty: bool = True,
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{path} must be an array")
        return []
    if not allow_empty and not value:
        errors.append(f"{path} must not be empty")
    result: list[str] = []
    for index, item in enumerate(value):
        checked = _check_nonempty_string(item, f"{path}[{index}]", errors)
        if checked is not None:
            result.append(checked)
    if len(result) != len(set(result)):
        errors.append(f"{path} must not contain duplicates")
    return result


def _check_id_list(
    value: Any,
    path: str,
    errors: list[str],
    *,
    allow_empty: bool = True,
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{path} must be an array")
        return []
    if not allow_empty and not value:
        errors.append(f"{path} must not be empty")
    result: list[str] = []
    for index, item in enumerate(value):
        checked = _check_id(item, f"{path}[{index}]", errors)
        if checked is not None:
            result.append(checked)
    if len(result) != len(set(result)):
        errors.append(f"{path} must not contain duplicates")
    return result


def _parse_timestamp(value: Any, path: str, errors: list[str]) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        errors.append(f"{path} must be an RFC3339 timestamp or null")
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        errors.append(f"{path} must be an RFC3339 timestamp or null")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{path} timestamp must include a timezone")
        return None
    return parsed


def _load_receipt(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ReceiptError(f"cannot read {path}: {error}") from error
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ReceiptError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ReceiptError(f"{path} must contain one JSON object")
    return value


def validate_receipt(receipt: dict[str, Any], source: str = "<memory>") -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    root = _check_exact_keys(receipt, TOP_LEVEL_KEYS, "receipt", errors)
    if root.get("schema") != SCHEMA:
        errors.append(f"receipt.schema must equal {SCHEMA!r}")
    program_id = _check_id(root.get("program_id"), "receipt.program_id", errors)
    comparison_class = _check_id(
        root.get("comparison_class"), "receipt.comparison_class", errors
    )
    status = root.get("status")
    if status not in {"accepted", "rework", "blocked", "failed"}:
        errors.append("receipt.status must be accepted, rework, blocked, or failed")

    timing = _check_exact_keys(
        root.get("timing"),
        set(TIMING_FIELDS) | {"unavailable", "not_applicable"},
        "receipt.timing",
        errors,
    )
    timing_unavailable = set(
        _check_string_list(timing.get("unavailable"), "receipt.timing.unavailable", errors)
    )
    timing_not_applicable = set(
        _check_string_list(
            timing.get("not_applicable"), "receipt.timing.not_applicable", errors
        )
    )
    unknown_timing_markers = (timing_unavailable | timing_not_applicable) - set(
        TIMING_FIELDS
    )
    if unknown_timing_markers:
        errors.append(
            "receipt.timing markers reference unknown fields: "
            + ", ".join(sorted(unknown_timing_markers))
        )
    if timing_unavailable & timing_not_applicable:
        errors.append("receipt.timing unavailable and not_applicable must be disjoint")
    parsed_times: dict[str, datetime | None] = {}
    for field in TIMING_FIELDS:
        value = timing.get(field)
        parsed_times[field] = _parse_timestamp(value, f"receipt.timing.{field}", errors)
        if value is None and field not in timing_unavailable | timing_not_applicable:
            errors.append(
                f"receipt.timing.{field} is null but is not declared unavailable or not_applicable"
            )
        if value is not None and field in timing_unavailable | timing_not_applicable:
            errors.append(f"receipt.timing.{field} has a value but is marked unavailable")
    observed_sequence = [
        (field, parsed_times[field])
        for field in TIMING_FIELDS
        if parsed_times[field] is not None
    ]
    for (prior_name, prior), (later_name, later) in zip(
        observed_sequence, observed_sequence[1:]
    ):
        assert prior is not None and later is not None
        if later < prior:
            errors.append(
                f"receipt.timing.{later_name} precedes {prior_name}"
            )

    topology = _check_exact_keys(
        root.get("topology"),
        {
            "requested_lanes",
            "manager_assignments",
            "workers",
            "max_observed_concurrency",
            "concurrency_limit",
            "variances",
        },
        "receipt.topology",
        errors,
    )
    lanes_value = topology.get("requested_lanes")
    if not isinstance(lanes_value, list) or not lanes_value:
        errors.append("receipt.topology.requested_lanes must be a non-empty array")
        lanes_value = []
    lanes: dict[str, dict[str, Any]] = {}
    for index, raw_lane in enumerate(lanes_value):
        lane = _check_exact_keys(
            raw_lane,
            {"lane_id", "outcome"},
            f"receipt.topology.requested_lanes[{index}]",
            errors,
        )
        lane_id = _check_id(
            lane.get("lane_id"),
            f"receipt.topology.requested_lanes[{index}].lane_id",
            errors,
        )
        _check_nonempty_string(
            lane.get("outcome"),
            f"receipt.topology.requested_lanes[{index}].outcome",
            errors,
        )
        if lane_id:
            if lane_id in lanes:
                errors.append(f"duplicate requested lane {lane_id!r}")
            lanes[lane_id] = lane

    managers_value = topology.get("manager_assignments")
    if not isinstance(managers_value, list) or not managers_value:
        errors.append("receipt.topology.manager_assignments must be a non-empty array")
        managers_value = []
    managers: dict[str, dict[str, Any]] = {}
    lane_owners: dict[str, list[str]] = defaultdict(list)
    for index, raw_manager in enumerate(managers_value):
        manager = _check_exact_keys(
            raw_manager,
            {
                "manager_task_id",
                "lane_ids",
                "requested_model",
                "requested_effort",
                "observed_model",
                "observed_effort",
            },
            f"receipt.topology.manager_assignments[{index}]",
            errors,
        )
        manager_id = _check_id(
            manager.get("manager_task_id"),
            f"receipt.topology.manager_assignments[{index}].manager_task_id",
            errors,
        )
        lane_ids = _check_string_list(
            manager.get("lane_ids"),
            f"receipt.topology.manager_assignments[{index}].lane_ids",
            errors,
            allow_empty=False,
        )
        for lane_id in lane_ids:
            if lane_id not in lanes:
                errors.append(f"manager {manager_id!r} references unknown lane {lane_id!r}")
            elif manager_id:
                lane_owners[lane_id].append(manager_id)
        _check_nonempty_string(
            manager.get("requested_model"),
            f"receipt.topology.manager_assignments[{index}].requested_model",
            errors,
        )
        _check_nonempty_string(
            manager.get("requested_effort"),
            f"receipt.topology.manager_assignments[{index}].requested_effort",
            errors,
        )
        observed_model = manager.get("observed_model")
        observed_effort = manager.get("observed_effort")
        if (observed_model is None) != (observed_effort is None):
            errors.append(f"manager {manager_id!r} observed model and effort must be paired")
        for field, value in (
            ("observed_model", observed_model),
            ("observed_effort", observed_effort),
        ):
            if value is not None:
                _check_nonempty_string(
                    value,
                    f"receipt.topology.manager_assignments[{index}].{field}",
                    errors,
                )
        if manager_id:
            if manager_id in managers:
                errors.append(f"duplicate manager task {manager_id!r}")
            managers[manager_id] = manager

    for lane_id in lanes:
        owners = lane_owners.get(lane_id, [])
        if len(owners) != 1:
            errors.append(
                f"requested lane {lane_id!r} must have exactly one manager owner; found {len(owners)}"
            )

    workers_value = topology.get("workers")
    if not isinstance(workers_value, list):
        errors.append("receipt.topology.workers must be an array")
        workers_value = []
    workers: dict[str, dict[str, Any]] = {}
    for index, raw_worker in enumerate(workers_value):
        worker = _check_exact_keys(
            raw_worker,
            {
                "worker_task_id",
                "manager_task_id",
                "requested_model",
                "requested_effort",
                "observed_model",
                "observed_effort",
            },
            f"receipt.topology.workers[{index}]",
            errors,
        )
        worker_id = _check_id(
            worker.get("worker_task_id"),
            f"receipt.topology.workers[{index}].worker_task_id",
            errors,
        )
        manager_id = _check_id(
            worker.get("manager_task_id"),
            f"receipt.topology.workers[{index}].manager_task_id",
            errors,
        )
        if manager_id and manager_id not in managers:
            errors.append(f"worker {worker_id!r} references unknown manager {manager_id!r}")
        _check_nonempty_string(
            worker.get("requested_model"),
            f"receipt.topology.workers[{index}].requested_model",
            errors,
        )
        _check_nonempty_string(
            worker.get("requested_effort"),
            f"receipt.topology.workers[{index}].requested_effort",
            errors,
        )
        observed_model = worker.get("observed_model")
        observed_effort = worker.get("observed_effort")
        if (observed_model is None) != (observed_effort is None):
            errors.append(f"worker {worker_id!r} observed model and effort must be paired")
        for field, value in (
            ("observed_model", observed_model),
            ("observed_effort", observed_effort),
        ):
            if value is not None:
                _check_nonempty_string(
                    value,
                    f"receipt.topology.workers[{index}].{field}",
                    errors,
                )
        if worker_id:
            if worker_id in workers:
                errors.append(f"duplicate worker task {worker_id!r}")
            workers[worker_id] = worker

    concurrency_limit = topology.get("concurrency_limit")
    if not _is_int(concurrency_limit) or concurrency_limit < 1:
        errors.append("receipt.topology.concurrency_limit must be a positive integer")
        concurrency_limit = None
    max_concurrency = topology.get("max_observed_concurrency")
    if max_concurrency is not None and (
        not _is_int(max_concurrency) or max_concurrency < 1
    ):
        errors.append(
            "receipt.topology.max_observed_concurrency must be a positive integer or null"
        )
        max_concurrency = None
    if (
        max_concurrency is not None
        and concurrency_limit is not None
        and max_concurrency > concurrency_limit
    ):
        errors.append("observed concurrency exceeds the declared concurrency limit")

    variances_value = topology.get("variances")
    if not isinstance(variances_value, list):
        errors.append("receipt.topology.variances must be an array")
        variances_value = []
    variance_keys: set[tuple[str, tuple[str, ...]]] = set()
    for index, raw_variance in enumerate(variances_value):
        variance = _check_exact_keys(
            raw_variance,
            {"type", "actor_task_id", "actor_role", "lane_ids", "reason"},
            f"receipt.topology.variances[{index}]",
            errors,
        )
        variance_type = variance.get("type")
        if variance_type not in {
            "host_cap_consolidation",
            "manager_direct_labor",
            "master_direct_labor",
            "other",
        }:
            errors.append(f"receipt.topology.variances[{index}].type is invalid")
        actor_id = _check_id(
            variance.get("actor_task_id"),
            f"receipt.topology.variances[{index}].actor_task_id",
            errors,
        )
        actor_role = variance.get("actor_role")
        if actor_role not in {"master", "manager"}:
            errors.append(f"receipt.topology.variances[{index}].actor_role is invalid")
        if actor_role == "manager" and actor_id and actor_id not in managers:
            errors.append(f"variance references unknown manager {actor_id!r}")
        if variance_type == "master_direct_labor" and actor_role != "master":
            errors.append("master_direct_labor must use actor_role master")
        if variance_type in {"host_cap_consolidation", "manager_direct_labor"} and actor_role != "manager":
            errors.append(f"{variance_type} must use actor_role manager")
        lane_ids = sorted(
            _check_string_list(
                variance.get("lane_ids"),
                f"receipt.topology.variances[{index}].lane_ids",
                errors,
                allow_empty=False,
            )
        )
        for lane_id in lane_ids:
            if lane_id not in lanes:
                errors.append(f"variance references unknown lane {lane_id!r}")
        _check_nonempty_string(
            variance.get("reason"),
            f"receipt.topology.variances[{index}].reason",
            errors,
        )
        if variance_type == "host_cap_consolidation" and len(lane_ids) < 2:
            errors.append("host_cap_consolidation must name at least two lanes")
        if variance_type == "host_cap_consolidation" and actor_id:
            variance_keys.add((actor_id, tuple(lane_ids)))

    for manager_id, manager in managers.items():
        owned = tuple(sorted(manager.get("lane_ids", [])))
        if len(owned) > 1 and (manager_id, owned) not in variance_keys:
            errors.append(
                f"manager {manager_id!r} owns multiple lanes without an exact disclosed variance"
            )

    if not workers and "first_worker_dispatch" not in timing_not_applicable:
        errors.append(
            "first_worker_dispatch must be not_applicable when no workers were dispatched"
        )
    if workers and "first_worker_dispatch" in timing_not_applicable:
        errors.append("first_worker_dispatch cannot be not_applicable when workers exist")

    usage = _check_exact_keys(
        root.get("usage"), set(USAGE_FIELDS) | {"unavailable"}, "receipt.usage", errors
    )
    usage_unavailable = set(
        _check_string_list(usage.get("unavailable"), "receipt.usage.unavailable", errors)
    )
    unknown_usage = usage_unavailable - set(USAGE_FIELDS)
    if unknown_usage:
        errors.append(
            "receipt.usage.unavailable references unknown fields: "
            + ", ".join(sorted(unknown_usage))
        )
    usage_values: dict[str, float | None] = {}
    for field in USAGE_FIELDS:
        value = usage.get(field)
        if value is None:
            usage_values[field] = None
            if field not in usage_unavailable:
                errors.append(
                    f"receipt.usage.{field} is null but is not declared unavailable"
                )
        elif not _is_number(value) or value < 0:
            errors.append(f"receipt.usage.{field} must be a non-negative number or null")
            usage_values[field] = None
        else:
            usage_values[field] = float(value)
            if field in usage_unavailable:
                errors.append(f"receipt.usage.{field} has a value but is marked unavailable")
    total_tokens = usage_values["total_tokens"]
    luna_tokens = usage_values["luna_tokens"]
    sol_tokens = usage_values["sol_tokens"]
    if total_tokens is not None and luna_tokens is not None and luna_tokens > total_tokens:
        errors.append("luna_tokens cannot exceed total_tokens")
    if total_tokens is not None and sol_tokens is not None and sol_tokens > total_tokens:
        errors.append("sol_tokens cannot exceed total_tokens")

    quality = _check_exact_keys(
        root.get("quality"),
        {
            "required_artifacts",
            "accepted_artifacts",
            "first_pass_accepted",
            "rework_cycles",
            "write_collisions",
            "duplicate_artifacts",
            "independent_reviewed",
        },
        "receipt.quality",
        errors,
    )
    for field in (
        "required_artifacts",
        "accepted_artifacts",
        "rework_cycles",
        "write_collisions",
        "duplicate_artifacts",
    ):
        value = quality.get(field)
        if not _is_int(value) or value < 0:
            errors.append(f"receipt.quality.{field} must be a non-negative integer")
    for field in ("first_pass_accepted", "independent_reviewed"):
        if not isinstance(quality.get(field), bool):
            errors.append(f"receipt.quality.{field} must be boolean")

    requirements_value = root.get("requirements")
    if not isinstance(requirements_value, list) or not requirements_value:
        errors.append("receipt.requirements must be a non-empty array")
        requirements_value = []
    requirements: dict[str, dict[str, Any]] = {}
    for index, raw_requirement in enumerate(requirements_value):
        requirement = _check_exact_keys(
            raw_requirement,
            {"requirement_id", "statement", "source", "mandatory"},
            f"receipt.requirements[{index}]",
            errors,
        )
        requirement_id = _check_id(
            requirement.get("requirement_id"),
            f"receipt.requirements[{index}].requirement_id",
            errors,
        )
        _check_nonempty_string(
            requirement.get("statement"),
            f"receipt.requirements[{index}].statement",
            errors,
        )
        _check_nonempty_string(
            requirement.get("source"),
            f"receipt.requirements[{index}].source",
            errors,
        )
        if not isinstance(requirement.get("mandatory"), bool):
            errors.append(f"receipt.requirements[{index}].mandatory must be boolean")
        if requirement_id:
            if requirement_id in requirements:
                errors.append(f"duplicate requirement {requirement_id!r}")
            requirements[requirement_id] = requirement

    results_value = root.get("requirement_results")
    if not isinstance(results_value, list):
        errors.append("receipt.requirement_results must be an array")
        results_value = []
    requirement_results: dict[str, dict[str, Any]] = {}
    for index, raw_result in enumerate(results_value):
        result = _check_exact_keys(
            raw_result,
            {"requirement_id", "status", "evidence"},
            f"receipt.requirement_results[{index}]",
            errors,
        )
        requirement_id = _check_id(
            result.get("requirement_id"),
            f"receipt.requirement_results[{index}].requirement_id",
            errors,
        )
        if requirement_id and requirement_id not in requirements:
            errors.append(f"requirement result references unknown requirement {requirement_id!r}")
        if result.get("status") not in {"satisfied", "unsatisfied", "unknown"}:
            errors.append(f"receipt.requirement_results[{index}].status is invalid")
        _check_string_list(
            result.get("evidence"),
            f"receipt.requirement_results[{index}].evidence",
            errors,
            allow_empty=False,
        )
        if requirement_id:
            if requirement_id in requirement_results:
                errors.append(f"duplicate requirement result {requirement_id!r}")
            requirement_results[requirement_id] = result
    missing_requirement_results = sorted(set(requirements) - set(requirement_results))
    if missing_requirement_results:
        errors.append(
            "requirements missing independent results: "
            + ", ".join(missing_requirement_results)
        )

    plan_value = root.get("artifact_plan")
    if not isinstance(plan_value, list):
        errors.append("receipt.artifact_plan must be an array")
        plan_value = []
    artifact_plan: dict[str, dict[str, Any]] = {}
    mandatory_requirement_ids = {
        requirement_id
        for requirement_id, requirement in requirements.items()
        if requirement.get("mandatory") is True
    }
    planned_requirement_ids: set[str] = set()
    planned_capability_bindings: set[tuple[str, str]] = set()
    for index, raw_plan in enumerate(plan_value):
        plan = _check_exact_keys(
            raw_plan,
            {
                "artifact_id",
                "kind",
                "expected_title",
                "owner_lane_id",
                "requirement_ids",
                "required_capability_ids",
            },
            f"receipt.artifact_plan[{index}]",
            errors,
        )
        artifact_id = _check_id(
            plan.get("artifact_id"), f"receipt.artifact_plan[{index}].artifact_id", errors
        )
        _check_nonempty_string(
            plan.get("kind"), f"receipt.artifact_plan[{index}].kind", errors
        )
        _check_nonempty_string(
            plan.get("expected_title"),
            f"receipt.artifact_plan[{index}].expected_title",
            errors,
        )
        owner_lane = _check_id(
            plan.get("owner_lane_id"),
            f"receipt.artifact_plan[{index}].owner_lane_id",
            errors,
        )
        if owner_lane and owner_lane not in lanes:
            errors.append(f"artifact plan references unknown lane {owner_lane!r}")
        requirement_ids = _check_id_list(
            plan.get("requirement_ids"),
            f"receipt.artifact_plan[{index}].requirement_ids",
            errors,
            allow_empty=False,
        )
        for requirement_id in requirement_ids:
            if requirement_id not in requirements:
                errors.append(
                    f"artifact plan {artifact_id!r} references unknown requirement {requirement_id!r}"
                )
            else:
                planned_requirement_ids.add(requirement_id)
        capability_ids = _check_id_list(
            plan.get("required_capability_ids"),
            f"receipt.artifact_plan[{index}].required_capability_ids",
            errors,
            allow_empty=False,
        )
        if artifact_id:
            planned_capability_bindings.update(
                (artifact_id, capability_id) for capability_id in capability_ids
            )
        if artifact_id:
            if artifact_id in artifact_plan:
                errors.append(f"duplicate planned artifact {artifact_id!r}")
            artifact_plan[artifact_id] = plan
    unmapped_mandatory_requirements = sorted(
        mandatory_requirement_ids - planned_requirement_ids
    )
    if unmapped_mandatory_requirements:
        errors.append(
            "mandatory requirements not mapped to an artifact: "
            + ", ".join(unmapped_mandatory_requirements)
        )

    artifacts_value = root.get("artifacts")
    if not isinstance(artifacts_value, list):
        errors.append("receipt.artifacts must be an array")
        artifacts_value = []
    artifacts: dict[str, dict[str, Any]] = {}
    external_ids: set[str] = set()
    artifact_requirement_gaps: dict[str, list[str]] = {}
    artifact_capability_gaps: dict[str, list[str]] = {}
    for index, raw_artifact in enumerate(artifacts_value):
        artifact = _check_exact_keys(
            raw_artifact,
            {
                "artifact_id",
                "kind",
                "title",
                "external_id",
                "owner_lane_id",
                "satisfied_requirement_ids",
                "applied_capability_ids",
                "refetched",
                "accepted",
            },
            f"receipt.artifacts[{index}]",
            errors,
        )
        artifact_id = _check_id(
            artifact.get("artifact_id"), f"receipt.artifacts[{index}].artifact_id", errors
        )
        kind = _check_nonempty_string(
            artifact.get("kind"), f"receipt.artifacts[{index}].kind", errors
        )
        title = _check_nonempty_string(
            artifact.get("title"), f"receipt.artifacts[{index}].title", errors
        )
        external_id = _check_nonempty_string(
            artifact.get("external_id"),
            f"receipt.artifacts[{index}].external_id",
            errors,
        )
        owner_lane = _check_id(
            artifact.get("owner_lane_id"),
            f"receipt.artifacts[{index}].owner_lane_id",
            errors,
        )
        if owner_lane and owner_lane not in lanes:
            errors.append(f"artifact {artifact_id!r} references unknown lane {owner_lane!r}")
        satisfied_requirement_ids = set(
            _check_id_list(
                artifact.get("satisfied_requirement_ids"),
                f"receipt.artifacts[{index}].satisfied_requirement_ids",
                errors,
            )
        )
        for requirement_id in satisfied_requirement_ids:
            if requirement_id not in requirements:
                errors.append(
                    f"artifact {artifact_id!r} claims unknown requirement {requirement_id!r}"
                )
        applied_capability_ids = set(
            _check_id_list(
                artifact.get("applied_capability_ids"),
                f"receipt.artifacts[{index}].applied_capability_ids",
                errors,
            )
        )
        for field in ("refetched", "accepted"):
            if not isinstance(artifact.get(field), bool):
                errors.append(f"receipt.artifacts[{index}].{field} must be boolean")
        if external_id:
            if external_id in external_ids:
                errors.append(f"duplicate artifact external_id {external_id!r}")
            external_ids.add(external_id)
        if artifact_id:
            if artifact_id in artifacts:
                errors.append(f"duplicate artifact {artifact_id!r}")
            artifacts[artifact_id] = artifact
            planned = artifact_plan.get(artifact_id)
            if planned is None:
                errors.append(f"artifact {artifact_id!r} is not in artifact_plan")
            else:
                comparisons = (
                    ("kind", kind, planned.get("kind")),
                    ("title", title, planned.get("expected_title")),
                    ("owner_lane_id", owner_lane, planned.get("owner_lane_id")),
                )
                for field, actual, expected in comparisons:
                    if actual != expected:
                        errors.append(
                            f"artifact {artifact_id!r} {field} does not match its plan"
                        )
                required_requirement_ids = set(planned.get("requirement_ids", []))
                required_capability_ids = set(
                    planned.get("required_capability_ids", [])
                )
                missing_requirement_ids = sorted(
                    required_requirement_ids - satisfied_requirement_ids
                )
                missing_capability_ids = sorted(
                    required_capability_ids - applied_capability_ids
                )
                artifact_requirement_gaps[artifact_id] = missing_requirement_ids
                artifact_capability_gaps[artifact_id] = missing_capability_ids
                if artifact.get("accepted") is True and missing_requirement_ids:
                    errors.append(
                        f"artifact {artifact_id!r} is accepted but misses requirements: "
                        + ", ".join(missing_requirement_ids)
                    )
                if artifact.get("accepted") is True and missing_capability_ids:
                    errors.append(
                        f"artifact {artifact_id!r} is accepted but misses required capabilities: "
                        + ", ".join(missing_capability_ids)
                    )
    missing_artifacts = sorted(set(artifact_plan) - set(artifacts))
    if missing_artifacts:
        errors.append("planned artifacts missing from readback: " + ", ".join(missing_artifacts))

    decision = _check_exact_keys(
        root.get("decision"),
        {
            "status",
            "reviewer",
            "authority",
            "required_authority",
            "evidence",
        },
        "receipt.decision",
        errors,
    )
    decision_status = decision.get("status")
    if decision_status not in {"accepted", "rework", "blocked", "failed"}:
        errors.append("receipt.decision.status is invalid")
    if status != decision_status:
        errors.append("receipt.status must equal receipt.decision.status")
    _check_nonempty_string(decision.get("reviewer"), "receipt.decision.reviewer", errors)
    decision_authority = decision.get("authority")
    required_authority = decision.get("required_authority")
    if decision_authority not in AUTHORITY_RANK:
        errors.append("receipt.decision.authority must be manager, master, or user")
    if required_authority not in AUTHORITY_RANK:
        errors.append(
            "receipt.decision.required_authority must be manager, master, or user"
        )
    authority_sufficient = bool(
        decision_authority in AUTHORITY_RANK
        and required_authority in AUTHORITY_RANK
        and AUTHORITY_RANK[decision_authority]
        >= AUTHORITY_RANK[required_authority]
    )
    _check_string_list(
        decision.get("evidence"), "receipt.decision.evidence", errors, allow_empty=False
    )

    required_artifacts = quality.get("required_artifacts")
    accepted_artifacts = quality.get("accepted_artifacts")
    if _is_int(required_artifacts) and required_artifacts != len(artifact_plan):
        errors.append("quality.required_artifacts must equal artifact_plan length")
    counted_accepted = sum(
        1
        for artifact in artifacts.values()
        if artifact.get("accepted") is True and artifact.get("refetched") is True
    )
    if _is_int(accepted_artifacts) and accepted_artifacts != counted_accepted:
        errors.append("quality.accepted_artifacts does not match accepted readback artifacts")

    satisfied_mandatory_requirements = {
        requirement_id
        for requirement_id in mandatory_requirement_ids
        if requirement_results.get(requirement_id, {}).get("status") == "satisfied"
    }
    mandatory_requirements_satisfied = bool(
        mandatory_requirement_ids
        and satisfied_mandatory_requirements == mandatory_requirement_ids
    )
    applied_capability_bindings = {
        (artifact_id, capability_id)
        for artifact_id, artifact in artifacts.items()
        for capability_id in artifact.get("applied_capability_ids", [])
    }
    applied_required_capability_bindings = (
        planned_capability_bindings & applied_capability_bindings
    )
    required_capabilities_applied = bool(
        planned_capability_bindings
        and planned_capability_bindings <= applied_capability_bindings
    )
    artifact_contracts_satisfied = bool(
        artifact_plan
        and set(artifact_plan) == set(artifacts)
        and all(
            not artifact_requirement_gaps.get(artifact_id)
            and not artifact_capability_gaps.get(artifact_id)
            and artifact.get("refetched") is True
            for artifact_id, artifact in artifacts.items()
        )
    )
    if status == "accepted" and not mandatory_requirements_satisfied:
        errors.append("accepted receipt has unsatisfied or unknown mandatory requirements")
    if status == "accepted" and not required_capabilities_applied:
        errors.append("accepted receipt is missing required capability application")
    if status == "accepted" and not authority_sufficient:
        errors.append("accepted receipt decision is below the required authority")

    delivery_accepted = bool(
        not errors
        and status == "accepted"
        and decision_status == "accepted"
        and quality.get("independent_reviewed") is True
        and mandatory_requirements_satisfied
        and required_capabilities_applied
        and artifact_contracts_satisfied
        and authority_sufficient
        and _is_int(required_artifacts)
        and required_artifacts > 0
        and accepted_artifacts == required_artifacts
        and quality.get("write_collisions") == 0
        and quality.get("duplicate_artifacts") == 0
    )
    hierarchy_materialized = bool(
        not errors and lanes and managers and all(len(lane_owners.get(lane_id, [])) == 1 for lane_id in lanes)
    )
    observed_luna_workers = [
        worker
        for worker in workers.values()
        if worker.get("observed_model") == "gpt-5.6-luna"
        and worker.get("observed_effort") == "max"
    ]
    all_worker_models_observed = bool(
        workers
        and all(
            worker.get("observed_model") is not None
            and worker.get("observed_effort") is not None
            for worker in workers.values()
        )
    )
    luna_execution_proven = bool(
        delivery_accepted
        and hierarchy_materialized
        and observed_luna_workers
        and all_worker_models_observed
    )

    required_timing = {
        "program_start",
        "first_manager_dispatch",
        "first_usable_result",
        "first_artifact_materialization",
        "final_acceptance",
    }
    if workers:
        required_timing.add("first_worker_dispatch")
    timing_complete = all(parsed_times.get(field) is not None for field in required_timing)
    usage_complete = all(usage_values[field] is not None for field in USAGE_FIELDS)
    lead_time_seconds: float | None = None
    if parsed_times.get("program_start") and parsed_times.get("final_acceptance"):
        lead_time_seconds = (
            parsed_times["final_acceptance"] - parsed_times["program_start"]
        ).total_seconds()
    luna_token_share: float | None = None
    if total_tokens and luna_tokens is not None:
        luna_token_share = luna_tokens / total_tokens
    sol_token_reduction: float | None = None
    baseline_sol = usage_values["single_thread_baseline_sol_tokens"]
    if baseline_sol and sol_tokens is not None:
        sol_token_reduction = 1.0 - (sol_tokens / baseline_sol)
    lead_time_improvement: float | None = None
    baseline_lead = usage_values["single_thread_baseline_lead_time_seconds"]
    if baseline_lead and lead_time_seconds is not None:
        lead_time_improvement = 1.0 - (lead_time_seconds / baseline_lead)

    scaling_evidence_eligible = bool(
        delivery_accepted
        and hierarchy_materialized
        and luna_execution_proven
        and timing_complete
        and usage_complete
        and max_concurrency is not None
        and lead_time_seconds is not None
    )
    efficiency_proven = bool(
        scaling_evidence_eligible
        and sol_token_reduction is not None
        and sol_token_reduction >= 0.40
        and lead_time_improvement is not None
        and lead_time_improvement >= 0.0
    )

    if not workers:
        warnings.append("no worker tasks were dispatched; Luna execution is unproven")
    if timing_unavailable:
        warnings.append(
            "timing unavailable: " + ", ".join(sorted(timing_unavailable))
        )
    if usage_unavailable:
        warnings.append("usage unavailable: " + ", ".join(sorted(usage_unavailable)))
    if any(manager.get("observed_model") is None for manager in managers.values()):
        warnings.append("one or more manager models were not observed")
    if workers and not all_worker_models_observed:
        warnings.append("one or more worker models were not observed")
    if quality.get("first_pass_accepted") is False:
        warnings.append("final acceptance required rework")
    unsatisfied_mandatory_requirements = sorted(
        mandatory_requirement_ids - satisfied_mandatory_requirements
    )
    if unsatisfied_mandatory_requirements:
        warnings.append(
            "mandatory requirements not satisfied: "
            + ", ".join(unsatisfied_mandatory_requirements)
        )
    missing_required_capabilities = sorted(
        planned_capability_bindings - applied_capability_bindings
    )
    if missing_required_capabilities:
        warnings.append(
            "required capabilities not applied: "
            + ", ".join(
                f"{artifact_id}:{capability_id}"
                for artifact_id, capability_id in missing_required_capabilities
            )
        )
    if not authority_sufficient:
        warnings.append("acceptance decision is below the required authority")

    return {
        "source": source,
        "program_id": program_id,
        "comparison_class": comparison_class,
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "requested_lanes": len(lanes),
            "unique_managers": len(managers),
            "workers": len(workers),
            "observed_luna_max_workers": len(observed_luna_workers),
            "maximum_observed_concurrency": max_concurrency,
            "mandatory_requirements_satisfied": len(
                satisfied_mandatory_requirements
            ),
            "mandatory_requirements_total": len(mandatory_requirement_ids),
            "required_capabilities_applied": len(
                applied_required_capability_bindings
            ),
            "required_capabilities_total": len(planned_capability_bindings),
            "accepted_artifact_rate": (
                accepted_artifacts / required_artifacts
                if _is_int(required_artifacts)
                and required_artifacts > 0
                and _is_int(accepted_artifacts)
                else None
            ),
            "first_pass_accepted": quality.get("first_pass_accepted"),
            "rework_cycles": quality.get("rework_cycles"),
            "write_collisions": quality.get("write_collisions"),
            "duplicate_artifacts": quality.get("duplicate_artifacts"),
            "lead_time_seconds": lead_time_seconds,
            "luna_token_share": luna_token_share,
            "sol_token_reduction": sol_token_reduction,
            "lead_time_improvement": lead_time_improvement,
        },
        "gates": {
            "delivery_accepted": delivery_accepted,
            "mandatory_requirements_satisfied": mandatory_requirements_satisfied,
            "required_capabilities_applied": required_capabilities_applied,
            "acceptance_authority_satisfied": authority_sufficient,
            "hierarchy_materialized": hierarchy_materialized,
            "luna_execution_proven": luna_execution_proven,
            "efficiency_proven": efficiency_proven,
            "scaling_evidence_eligible": scaling_evidence_eligible,
        },
        "_aggregate": {
            "status": status,
            "quality": quality,
            "usage": usage_values,
            "lead_time_seconds": lead_time_seconds,
        },
    }


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        comparison_class = result.get("comparison_class")
        if result.get("ok") and isinstance(comparison_class, str):
            groups[comparison_class].append(result)

    output: dict[str, Any] = {}
    for comparison_class, group in sorted(groups.items()):
        cycles = len(group)
        accepted = sum(1 for item in group if item["gates"]["delivery_accepted"])
        first_pass = sum(
            1 for item in group if item["metrics"]["first_pass_accepted"] is True
        )
        rework_cycles = sum(
            item["metrics"]["rework_cycles"]
            for item in group
            if _is_int(item["metrics"]["rework_cycles"])
        )
        collisions = sum(
            item["metrics"]["write_collisions"]
            for item in group
            if _is_int(item["metrics"]["write_collisions"])
        )
        duplicates = sum(
            item["metrics"]["duplicate_artifacts"]
            for item in group
            if _is_int(item["metrics"]["duplicate_artifacts"])
        )
        total_tokens_values = [item["_aggregate"]["usage"]["total_tokens"] for item in group]
        luna_tokens_values = [item["_aggregate"]["usage"]["luna_tokens"] for item in group]
        sol_tokens_values = [item["_aggregate"]["usage"]["sol_tokens"] for item in group]
        baseline_sol_values = [
            item["_aggregate"]["usage"]["single_thread_baseline_sol_tokens"]
            for item in group
        ]
        luna_share = None
        if all(value is not None for value in total_tokens_values + luna_tokens_values):
            total = sum(total_tokens_values)
            luna_share = sum(luna_tokens_values) / total if total else None
        sol_reduction = None
        if all(value is not None for value in sol_tokens_values + baseline_sol_values):
            baseline = sum(baseline_sol_values)
            sol_reduction = 1.0 - (sum(sol_tokens_values) / baseline) if baseline else None
        lead_nonregression = all(
            item["metrics"]["lead_time_improvement"] is not None
            and item["metrics"]["lead_time_improvement"] >= 0
            for item in group
        )
        first_pass_rate = first_pass / cycles if cycles else 0.0
        rework_rate = rework_cycles / (cycles + rework_cycles) if cycles + rework_cycles else 0.0
        all_eligible = all(item["gates"]["scaling_evidence_eligible"] for item in group)
        scale_gate = bool(
            cycles >= 3
            and accepted == cycles
            and all_eligible
            and first_pass_rate >= 0.85
            and rework_rate < 0.20
            and collisions == 0
            and duplicates == 0
            and luna_share is not None
            and luna_share >= 0.70
            and sol_reduction is not None
            and sol_reduction >= 0.40
            and lead_nonregression
        )
        output[comparison_class] = {
            "cycles": cycles,
            "accepted_cycles": accepted,
            "first_pass_rate": first_pass_rate,
            "rework_rate": rework_rate,
            "write_collisions": collisions,
            "duplicate_artifacts": duplicates,
            "luna_token_share": luna_share,
            "sol_token_reduction": sol_reduction,
            "lead_time_nonregression": lead_nonregression,
            "all_receipts_scaling_eligible": all_eligible,
            "scale_gate_passed": scale_gate,
        }
    return output


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("receipts", nargs="+", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    results: list[dict[str, Any]] = []
    load_errors: list[str] = []
    for path in args.receipts:
        try:
            receipt = _load_receipt(path)
        except ReceiptError as error:
            load_errors.append(str(error))
            continue
        results.append(validate_receipt(receipt, str(path)))
    payload = {
        "schema": "company-os.execution-efficiency-validation.v1",
        "ok": not load_errors and all(result["ok"] for result in results),
        "load_errors": load_errors,
        "receipts": [
            {key: value for key, value in result.items() if key != "_aggregate"}
            for result in results
        ],
        "comparison_groups": aggregate_results(results),
    }
    sys.stdout.write(_canonical_json(payload) + "\n")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
