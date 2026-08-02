#!/usr/bin/env python3
"""Validate deterministic evidence for a host-operated Codex task fabric.

This module never calls Codex app tools.  It validates exported task records
that a Sol master or manager captured from the interactive host.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


SCHEMA = "company-os.codex-native-task-fabric-simulation.v2"
REQUESTED_MODELS = {
    "master": "gpt-5.6-sol",
    "manager": "gpt-5.6-sol",
    "worker": "gpt-5.6-luna",
}
CURRENT_STATUSES = {"planned", "created", "active", "accepted", "blocked", "failed", "refused", "cancelled"}
TERMINAL_STATUSES = {"accepted", "blocked", "failed", "refused", "cancelled"}
UNAVAILABLE_FIELDS = {"tokens", "cost_usd", "cancellation_acknowledgement"}
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]{2,127}$")
SCOPE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*(?:/[a-z0-9][a-z0-9._-]*)*$")
HOST_MODEL_SOURCE_PATTERN = re.compile(
    r"^host_observation:(?:create_thread|list_threads|read_thread|wait_threads):model$"
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_id(value: Any) -> bool:
    return _nonempty(value) and bool(ID_PATTERN.fullmatch(value))


def _finite_nonnegative(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _positive_order(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _canonical_scope(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.isascii()
        and value == unicodedata.normalize("NFKC", value)
        and value == value.casefold()
        and bool(SCOPE_PATTERN.fullmatch(value))
    )


def _scopes_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _error(errors: list[dict[str, str]], code: str, detail: str) -> None:
    errors.append({"code": code, "detail": detail})


def _validate_metric(
    metrics: Any,
    field: str,
    errors: list[dict[str, str]],
    task_id: str,
    evidence_kind: str,
) -> None:
    value = metrics.get(field) if isinstance(metrics, dict) else None
    if not isinstance(value, dict) or set(value) != {"status", "value", "source"}:
        _error(errors, "telemetry_shape", f"{task_id}.{field} must define status, value, and source")
        return
    status = value.get("status")
    observed = value.get("value")
    source = value.get("source")
    if status == "unavailable":
        if observed is not None or source is not None:
            _error(errors, "telemetry_fabricated", f"{task_id}.{field} unavailable value/source must be null")
        return
    if field in UNAVAILABLE_FIELDS:
        _error(errors, "host_capability_overclaim", f"{task_id}.{field} is unavailable on the accepted host surface")
        return
    if field == "elapsed_ms" and status in {"observed", "fixture"} and _finite_nonnegative(observed) and _nonempty(source):
        if evidence_kind == "deterministic_fixture" and status != "fixture":
            _error(errors, "fixture_mislabeled_observed", f"{task_id}.{field} fixture timing is not a host observation")
        if evidence_kind == "native_observation" and status != "observed":
            _error(errors, "native_timing_mislabeled", f"{task_id}.{field} native timing must be observed or unavailable")
        return
    _error(errors, "telemetry_invalid", f"{task_id}.{field} has an unsupported observation")


def validate_scenario(scenario: Any) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if not isinstance(scenario, dict):
        _error(errors, "scenario_shape", "scenario must be an object")
        return {"decision": "rework", "errors": errors, "error_codes": ["scenario_shape"]}
    project_id = scenario.get("project_id")
    program_id = scenario.get("program_id")
    program_version = scenario.get("program_version")
    master_task_id = scenario.get("master_task_id")
    evidence_kind = scenario.get("evidence_kind")
    if evidence_kind not in {"deterministic_fixture", "native_observation"}:
        _error(errors, "evidence_kind", "scenario evidence_kind is invalid")
        evidence_kind = "invalid"
    if not _nonempty(scenario.get("evidence_source")):
        _error(errors, "evidence_source", "scenario evidence_source is required")
    if not _valid_id(project_id):
        _error(errors, "project_id", "project_id is invalid")
    if not _valid_id(program_id):
        _error(errors, "program_id", "program_id is invalid")
    if not isinstance(program_version, int) or isinstance(program_version, bool) or program_version < 1:
        _error(errors, "program_version", "program_version must be a positive integer")
    if not _valid_id(master_task_id):
        _error(errors, "master_task_id", "master_task_id is invalid")

    budget = scenario.get("budget")
    if not isinstance(budget, dict):
        _error(errors, "budget_shape", "budget must be an object")
        budget = {}
    max_concurrency = budget.get("max_concurrency")
    max_tasks = budget.get("max_tasks")
    if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool) or max_concurrency < 1:
        _error(errors, "budget_concurrency", "max_concurrency must be a positive integer")
        max_concurrency = 1
    if not isinstance(max_tasks, int) or isinstance(max_tasks, bool) or max_tasks < 1:
        _error(errors, "budget_tasks", "max_tasks must be a positive integer")
        max_tasks = 1

    tasks = scenario.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        _error(errors, "tasks", "tasks must contain at least one task")
        tasks = []
    if len(tasks) > max_tasks:
        _error(errors, "budget_task_pressure", "task count exceeds max_tasks")

    by_id: dict[str, dict[str, Any]] = {}
    for task in tasks:
        task_id = task.get("task_id") if isinstance(task, dict) else None
        if not isinstance(task, dict) or not _valid_id(task_id):
            _error(errors, "task_id", "task_id is invalid")
            continue
        if task_id in by_id:
            _error(errors, "duplicate_task", f"duplicate task_id {task_id}")
        by_id[task_id] = task

    active_windows: list[tuple[int, int | None, str]] = []
    worker_scopes: list[tuple[str, str]] = []
    manager_scopes: list[tuple[str, str]] = []
    native_thread_ids: dict[str, str] = {}
    for task_id, task in by_id.items():
        if task.get("project_id") != project_id or task.get("program_id") != program_id or task.get("program_version") != program_version:
            _error(errors, "project_isolation", f"{task_id} does not match its exact project/program binding")

        role = task.get("role")
        if role not in REQUESTED_MODELS:
            _error(errors, "role", f"{task_id} role is invalid")
        elif task.get("requested_model") != REQUESTED_MODELS[role]:
            _error(errors, "requested_model", f"{task_id} requested model does not match role")

        observed_model = task.get("observed_model")
        if not isinstance(observed_model, dict) or set(observed_model) != {"status", "value", "source"}:
            _error(errors, "observed_model_shape", f"{task_id} observed_model is malformed")
        elif observed_model.get("status") == "unavailable":
            if observed_model.get("value") is not None or observed_model.get("source") is not None:
                _error(errors, "observed_model_fabricated", f"{task_id} unavailable model must have null value/source")
        elif evidence_kind == "deterministic_fixture":
            _error(errors, "fixture_model_mislabeled_observed", f"{task_id} fixture cannot claim an observed model")
        elif not (
            evidence_kind == "native_observation"
            and observed_model.get("status") == "observed"
            and _nonempty(observed_model.get("value"))
            and isinstance(observed_model.get("source"), str)
            and HOST_MODEL_SOURCE_PATTERN.fullmatch(observed_model["source"])
        ):
            _error(errors, "observed_model_source_untrusted", f"{task_id} model source is not a recognized host observation")

        native = task.get("native_metadata")
        if not isinstance(native, dict) or set(native) != {"thread_id", "host_id"}:
            _error(errors, "native_metadata_shape", f"{task_id} native metadata is malformed")
            native = {}
        current_status = task.get("current_status")
        created_order = task.get("created_order")
        started_order = task.get("started_order")
        terminal_status = task.get("terminal_status")
        terminal_order = task.get("terminal_order")
        if current_status not in CURRENT_STATUSES:
            _error(errors, "current_status", f"{task_id} current_status is invalid")
        if current_status == "planned":
            if any(value is not None for value in (created_order, started_order, terminal_status, terminal_order)):
                _error(errors, "planned_task_order", f"{task_id} planned task cannot claim lifecycle orders")
            if native.get("thread_id") is not None or native.get("host_id") is not None:
                _error(errors, "native_identity_before_create", f"{task_id} has native identity before creation")
        else:
            if not _positive_order(created_order):
                _error(errors, "created_order", f"{task_id} non-planned task lacks created_order")
            if not _nonempty(native.get("thread_id")) or not _nonempty(native.get("host_id")):
                _error(errors, "native_identity_missing", f"{task_id} created task lacks thread_id/host_id")
            else:
                thread_id = native["thread_id"]
                if thread_id in native_thread_ids:
                    _error(errors, "native_identity_duplicate", f"{task_id} reuses native thread identity from {native_thread_ids[thread_id]}")
                native_thread_ids[thread_id] = task_id
                if evidence_kind == "native_observation" and thread_id != task_id:
                    _error(errors, "native_identity_mismatch", f"{task_id} native observation thread_id differs")

        if current_status == "created":
            if started_order is not None or terminal_status is not None or terminal_order is not None:
                _error(errors, "created_task_order", f"{task_id} created task cannot claim start or terminal state")
        elif current_status == "active":
            if not _positive_order(created_order) or not _positive_order(started_order) or started_order <= created_order:
                _error(errors, "started_order", f"{task_id} active task lacks ordered create/start events")
            if terminal_status is not None or terminal_order is not None:
                _error(errors, "active_marked_terminal", f"{task_id} active task cannot be terminal")
            if _positive_order(started_order):
                active_windows.append((started_order, None, task_id))
        elif current_status in TERMINAL_STATUSES:
            if terminal_status != current_status:
                _error(errors, "terminal_status_mismatch", f"{task_id} terminal_status must match current_status")
            if (
                not _positive_order(created_order)
                or not _positive_order(started_order)
                or not _positive_order(terminal_order)
                or not created_order < started_order < terminal_order
            ):
                _error(errors, "terminal_order", f"{task_id} terminal task requires ordered create/start/terminal events")
            else:
                active_windows.append((started_order, terminal_order, task_id))

        parent_id = task.get("parent_task_id")
        if role == "manager":
            if parent_id != master_task_id:
                _error(errors, "lineage", f"{task_id} manager parent must be master_task_id")
        elif role == "worker":
            parent = by_id.get(parent_id)
            if not parent or parent.get("role") != "manager":
                _error(errors, "lineage", f"{task_id} worker parent must be a manager in the same scenario")
            elif parent.get("project_id") != project_id:
                _error(errors, "project_isolation", f"{task_id} parent belongs to another project")

        dependencies = task.get("dependencies")
        if not isinstance(dependencies, list) or any(not _valid_id(item) for item in dependencies):
            _error(errors, "dependency_shape", f"{task_id} dependencies are invalid")
            dependencies = []
        for dependency_id in dependencies:
            dependency = by_id.get(dependency_id)
            if dependency is None:
                _error(errors, "dependency_missing", f"{task_id} dependency {dependency_id} is absent")
                continue
            if dependency.get("project_id") != project_id:
                _error(errors, "project_isolation", f"{task_id} dependency crosses project boundary")
            task_started_order = task.get("started_order")
            dependency_accepted = (
                dependency.get("terminal_status") == "accepted"
                and isinstance(dependency.get("terminal_order"), int)
            )
            if task_started_order is None and not dependency_accepted:
                _error(errors, "dependency_blocked", f"{task_id} correctly remained blocked on {dependency_id}")
            elif task_started_order is not None and (
                not dependency_accepted or dependency["terminal_order"] >= task_started_order
            ):
                _error(errors, "dependency_not_accepted", f"{task_id} started before {dependency_id} was accepted")

        scope = task.get("scope")
        if not isinstance(scope, list) or any(not _nonempty(item) for item in scope):
            _error(errors, "scope_shape", f"{task_id} scope is invalid")
            scope = []
        elif any(not _canonical_scope(item) for item in scope):
            _error(errors, "scope_noncanonical", f"{task_id} scope must be lowercase ASCII project-relative POSIX paths")
        expected_scope_digest = digest(sorted(scope))
        if task.get("scope_digest") != expected_scope_digest:
            _error(errors, "scope_changed", f"{task_id} scope digest does not match its current scope")
        if role == "worker":
            for item in scope:
                for existing, owner in worker_scopes:
                    if _scopes_overlap(item, existing):
                        _error(errors, "scope_collision", f"{task_id} scope {item} overlaps {owner} scope {existing}")
                worker_scopes.append((item, task_id))
        elif role == "manager":
            for item in scope:
                for existing, owner in manager_scopes:
                    if _scopes_overlap(item, existing):
                        _error(errors, "manager_scope_collision", f"{task_id} manager scope {item} overlaps {owner} scope {existing}")
                manager_scopes.append((item, task_id))

        report = task.get("report")
        if not isinstance(report, dict):
            _error(errors, "report_missing", f"{task_id} report is missing")
            report = {}
        if report.get("version") != 1:
            _error(errors, "report_stale", f"{task_id} report version is not current")
        if report.get("scope_digest") != expected_scope_digest:
            _error(errors, "report_scope_changed", f"{task_id} report uses a different scope")

        if terminal_status in {"failed", "refused", "cancelled"}:
            _error(errors, "task_terminal_failure", f"{task_id} ended {terminal_status}")

        artifact = task.get("artifact")
        oracle = task.get("acceptance_oracle")
        if artifact is not None:
            if not isinstance(artifact, dict):
                _error(errors, "artifact_shape", f"{task_id} artifact is malformed")
            else:
                if artifact.get("project_id") != project_id or artifact.get("task_id") != task_id:
                    _error(errors, "artifact_isolation", f"{task_id} artifact binding is foreign")
                if artifact.get("sha256") != digest(artifact.get("content")):
                    _error(errors, "artifact_digest", f"{task_id} artifact digest is invalid")
        if terminal_status == "accepted":
            if not isinstance(artifact, dict):
                _error(errors, "artifact_missing", f"{task_id} accepted without artifact")
            if not isinstance(oracle, dict) or oracle.get("kind") != "json_equals":
                _error(errors, "oracle_missing", f"{task_id} acceptance oracle is invalid")
            elif isinstance(artifact, dict):
                key = oracle.get("key")
                content = artifact.get("content")
                if not isinstance(content, dict) or content.get(key) != oracle.get("value"):
                    _error(errors, "oracle_failed", f"{task_id} artifact failed its objective oracle")

        telemetry = task.get("telemetry")
        for field in ("tokens", "cost_usd", "elapsed_ms", "cancellation_acknowledgement"):
            _validate_metric(telemetry, field, errors, task_id, evidence_kind)

    if active_windows:
        for tick in sorted({item[0] for item in active_windows}):
            active = [
                task_id for start, end, task_id in active_windows
                if start <= tick and (end is None or tick < end)
            ]
            if len(active) > max_concurrency:
                _error(errors, "budget_concurrency_pressure", f"concurrency {len(active)} exceeds {max_concurrency} at order {tick}")
                break

    codes = {item["code"] for item in errors}
    if not errors:
        decision = "accepted"
    elif codes & {"project_isolation", "artifact_isolation", "lineage"}:
        decision = "rejected"
    elif codes & {"dependency_missing", "dependency_blocked", "dependency_not_accepted", "budget_task_pressure", "budget_concurrency_pressure"}:
        decision = "blocked"
    else:
        decision = "rework"
    return {"decision": decision, "errors": errors, "error_codes": sorted(codes)}


def validate_simulation(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("simulation schema is unsupported")
    scenarios = payload.get("scenarios")
    iterations = payload.get("iterations")
    scorecard = payload.get("scorecard")
    runtime_scorecard = payload.get("runtime_readiness_scorecard")
    if not isinstance(iterations, list) or not iterations:
        errors.append("before/after iterations are required")
    scenario_ids = {
        item.get("scenario_id") for item in scenarios or []
        if isinstance(item, dict) and _valid_id(item.get("scenario_id"))
    } if isinstance(scenarios, list) else set()
    if isinstance(iterations, list):
        seen_iterations: set[str] = set()
        for item in iterations:
            if not isinstance(item, dict):
                errors.append("iteration defect-to-correction mapping is invalid")
                continue
            iteration_id = item.get("iteration_id")
            reruns = item.get("rerun_scenarios")
            if not _nonempty(iteration_id) or iteration_id in seen_iterations:
                errors.append(f"invalid or duplicate iteration_id: {iteration_id}")
            else:
                seen_iterations.add(iteration_id)
            if not _nonempty(item.get("defect")) or not _nonempty(item.get("correction")):
                errors.append(f"{iteration_id}: defect and correction are required")
            if (
                not isinstance(reruns, list)
                or not reruns
                or any(not _valid_id(value) for value in reruns)
                or len(reruns) != len(set(reruns))
            ):
                errors.append(f"{iteration_id}: rerun_scenarios must be nonempty and unique")
            elif any(value not in scenario_ids for value in reruns):
                errors.append(f"{iteration_id}: rerun_scenarios references an unknown scenario")
    if not isinstance(scorecard, list) or not scorecard:
        errors.append("simulation scorecard is required")
    elif any(
        not isinstance(item, dict)
        or not _nonempty(item.get("dimension"))
        or not _finite_nonnegative(item.get("score"))
        or not _nonempty(item.get("evidence"))
        for item in scorecard
    ):
        errors.append("simulation scorecard is invalid")
    if payload.get("runtime_readiness_decision") != "no_go":
        errors.append("full runtime readiness must remain no_go")
    if not isinstance(runtime_scorecard, list) or not runtime_scorecard:
        errors.append("full runtime readiness scorecard is required")
    elif any(
        not isinstance(item, dict)
        or not _nonempty(item.get("dimension"))
        or not _finite_nonnegative(item.get("score"))
        or not _nonempty(item.get("evidence"))
        for item in runtime_scorecard
    ):
        errors.append("full runtime readiness scorecard is invalid")
    elif all(item["score"] >= 8 for item in runtime_scorecard):
        errors.append("runtime no_go lacks a below-gate capability score")
    if not isinstance(scenarios, list) or len(scenarios) != 5:
        return {"valid": False, "errors": errors + ["exactly five scenarios are required"], "results": []}
    results = []
    seen: set[str] = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            errors.append("scenario must be an object")
            continue
        scenario_id = scenario.get("scenario_id")
        if not _valid_id(scenario_id) or scenario_id in seen:
            errors.append(f"invalid or duplicate scenario_id: {scenario_id}")
            continue
        seen.add(scenario_id)
        result = validate_scenario(scenario)
        expected = scenario.get("expected_after")
        raw_expected_codes = scenario.get("expected_error_codes")
        if not isinstance(raw_expected_codes, list) or any(not isinstance(item, str) for item in raw_expected_codes):
            errors.append(f"{scenario_id} expected_error_codes is invalid")
            expected_codes: list[str] = []
        else:
            expected_codes = sorted(raw_expected_codes)
        matched = result["decision"] == expected and result["error_codes"] == expected_codes
        if not matched:
            errors.append(f"{scenario_id} did not match its deterministic oracle")
        results.append({"scenario_id": scenario_id, "matched": matched, **result})
    return {"valid": not errors, "errors": errors, "results": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("simulation", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.simulation.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2))
        return 2
    if not isinstance(payload, dict):
        print(json.dumps({"valid": False, "errors": ["simulation must be an object"]}, indent=2))
        return 2
    result = validate_simulation(payload)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
