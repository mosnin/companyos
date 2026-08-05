#!/usr/bin/env python3
"""Validate and evaluate the Company OS force-first execution state machine."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
from pathlib import Path
from typing import Any


CONTRACT_SCHEMA = "company-os.force-contract.v1"
EVENT_SCHEMA = "company-os.force-event.v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SAFE_PATH = re.compile(r"^[a-z0-9][a-z0-9._/-]*$")
SOFT_SLO_KEYS = {
    "first_artifact_seconds",
    "runnable_candidate_seconds",
    "verification_seconds",
    "acceptance_to_receipt_seconds",
    "receipt_to_decision_seconds",
}
BASELINE_HARD_STOPS = {
    "authority_loss",
    "budget_exhausted",
    "collision",
    "explicit_cancel",
    "prohibited_side_effect",
    "scope_violation",
}
EVENTS = {
    "task_started",
    "inflight_observed",
    "intervention_sent",
    "artifact_materialized",
    "late_output_reviewed",
    "candidate_runnable",
    "verification_passed",
    "manager_inspection_passed",
    "manager_inspection_failed",
    "rework_started",
    "receipt_materialized",
    "manager_accept",
    "manager_rework",
    "manager_reject",
    "hard_stop",
}
TERMINAL_EVENTS = {"manager_accept", "manager_reject", "hard_stop"}


class ForceContractError(ValueError):
    """Raised when a force contract or event log is invalid."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ForceContractError(
            f"{label} keys differ; extra={sorted(actual - expected)!r}, "
            f"missing={sorted(expected - actual)!r}"
        )


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ForceContractError(f"{label} must be a positive integer")
    return value


def _safe_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SAFE_PATH.fullmatch(value):
        raise ForceContractError(f"{label} must be a safe project-relative path")
    if value.startswith("/") or "//" in value or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ForceContractError(f"{label} must not escape or contain ambiguous segments")
    return value


def _artifact_root(path: Path) -> Path:
    if path.is_symlink():
        raise ForceContractError("artifact root must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ForceContractError(f"artifact root could not be resolved: {error}") from error
    if not resolved.is_dir():
        raise ForceContractError("artifact root must be a directory")
    return resolved


def _verified_file(root: Path, relative: str, expected_sha256: str | None = None) -> str:
    safe = _safe_path(relative, "artifact path")
    current = root
    parts = safe.split("/")
    for index, part in enumerate(parts):
        current = current / part
        try:
            status = current.lstat()
        except OSError as error:
            raise ForceContractError(f"artifact path is missing or unreadable: {safe}") from error
        if stat.S_ISLNK(status.st_mode):
            raise ForceContractError(f"artifact path contains a symlink: {safe}")
        if index < len(parts) - 1 and not stat.S_ISDIR(status.st_mode):
            raise ForceContractError(f"artifact path parent is not a directory: {safe}")
        if index == len(parts) - 1 and not stat.S_ISREG(status.st_mode):
            raise ForceContractError(f"artifact path is not a regular file: {safe}")
    try:
        current.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as error:
        raise ForceContractError(f"artifact path escapes its root: {safe}") from error
    try:
        digest = hashlib.sha256(current.read_bytes()).hexdigest()
    except OSError as error:
        raise ForceContractError(f"artifact bytes could not be read: {safe}") from error
    if expected_sha256 is not None and digest != expected_sha256:
        raise ForceContractError(f"artifact digest does not match exact bytes: {safe}")
    return digest


def validate_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ForceContractError("contract must be an object")
    _exact_keys(
        value,
        {"schema", "task_id", "outcome", "started_at_epoch", "soft_slos", "control", "hard_stop_codes"},
        "contract",
    )
    if value["schema"] != CONTRACT_SCHEMA:
        raise ForceContractError("unsupported contract schema")
    if not isinstance(value["task_id"], str) or not IDENTIFIER.fullmatch(value["task_id"]):
        raise ForceContractError("task_id is invalid")
    if not isinstance(value["outcome"], str) or not value["outcome"].strip():
        raise ForceContractError("outcome must be non-empty")
    if isinstance(value["started_at_epoch"], bool) or not isinstance(value["started_at_epoch"], int) or value["started_at_epoch"] < 0:
        raise ForceContractError("started_at_epoch must be a non-negative integer")

    soft_slos = value["soft_slos"]
    if not isinstance(soft_slos, dict):
        raise ForceContractError("soft_slos must be an object")
    _exact_keys(soft_slos, SOFT_SLO_KEYS, "soft_slos")
    for key in sorted(SOFT_SLO_KEYS):
        _positive_int(soft_slos[key], f"soft_slos.{key}")
    if soft_slos["first_artifact_seconds"] > soft_slos["runnable_candidate_seconds"]:
        raise ForceContractError("first artifact SLO must not exceed runnable candidate SLO")
    if soft_slos["runnable_candidate_seconds"] > soft_slos["verification_seconds"]:
        raise ForceContractError("runnable candidate SLO must not exceed verification SLO")

    control = value["control"]
    if not isinstance(control, dict):
        raise ForceContractError("control must be an object")
    _exact_keys(
        control,
        {"inflight_observation_fresh_seconds", "max_rework_cycles", "event_log_owner"},
        "control",
    )
    _positive_int(control["inflight_observation_fresh_seconds"], "control.inflight_observation_fresh_seconds")
    if (
        isinstance(control["max_rework_cycles"], bool)
        or not isinstance(control["max_rework_cycles"], int)
        or not 0 <= control["max_rework_cycles"] <= 3
    ):
        raise ForceContractError("control.max_rework_cycles must be between zero and three")
    if control["event_log_owner"] != "manager":
        raise ForceContractError("control.event_log_owner must be manager")

    codes = value["hard_stop_codes"]
    if not isinstance(codes, list) or not codes or any(not isinstance(code, str) or not IDENTIFIER.fullmatch(code) for code in codes):
        raise ForceContractError("hard_stop_codes must be a non-empty unique identifier list")
    if len(codes) != len(set(codes)):
        raise ForceContractError("hard_stop_codes must be unique")
    missing = sorted(BASELINE_HARD_STOPS - set(codes))
    if missing:
        raise ForceContractError(f"hard_stop_codes omit baseline stops: {missing!r}")
    return value


def _nonempty_strings(value: Any, label: str, *, paths: bool = False) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ForceContractError(f"{label} must be a non-empty list")
    result: list[str] = []
    for index, item in enumerate(value):
        if paths:
            result.append(_safe_path(item, f"{label}[{index}]"))
        elif not isinstance(item, str) or not item.strip():
            raise ForceContractError(f"{label}[{index}] must be non-empty")
        else:
            result.append(item)
    return result


def _validate_evidence(event: str, evidence: Any, hard_stop_codes: set[str]) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise ForceContractError(f"{event} evidence must be an object")
    if event in {"task_started", "manager_accept"}:
        _exact_keys(evidence, set(), f"{event} evidence")
    elif event == "inflight_observed":
        _exact_keys(evidence, {"operation"}, f"{event} evidence")
        if not isinstance(evidence["operation"], str) or not evidence["operation"].strip():
            raise ForceContractError("inflight_observed operation must be non-empty")
    elif event == "intervention_sent":
        _exact_keys(evidence, {"missing"}, f"{event} evidence")
        if not isinstance(evidence["missing"], str) or not evidence["missing"].strip():
            raise ForceContractError("intervention_sent missing must be non-empty")
    elif event in {"artifact_materialized", "receipt_materialized"}:
        _exact_keys(evidence, {"path", "sha256"}, f"{event} evidence")
        _safe_path(evidence["path"], f"{event} evidence.path")
        if not isinstance(evidence["sha256"], str) or not HEX64.fullmatch(evidence["sha256"]):
            raise ForceContractError(f"{event} evidence.sha256 must be lowercase SHA-256")
    elif event in {"candidate_runnable", "manager_inspection_passed"}:
        _exact_keys(evidence, {"artifact_paths"}, f"{event} evidence")
        _nonempty_strings(evidence["artifact_paths"], f"{event} evidence.artifact_paths", paths=True)
    elif event == "late_output_reviewed":
        _exact_keys(evidence, {"artifact_paths", "decision"}, f"{event} evidence")
        _nonempty_strings(evidence["artifact_paths"], f"{event} evidence.artifact_paths", paths=True)
        if evidence["decision"] not in {"accept", "rework", "reject"}:
            raise ForceContractError("late_output_reviewed decision must be accept, rework, or reject")
    elif event == "verification_passed":
        _exact_keys(evidence, {"check"}, f"{event} evidence")
        if not isinstance(evidence["check"], str) or not evidence["check"].strip():
            raise ForceContractError("verification_passed check must be non-empty")
    elif event in {"manager_inspection_failed", "rework_started", "manager_rework"}:
        _exact_keys(evidence, {"defects"}, f"{event} evidence")
        _nonempty_strings(evidence["defects"], f"{event} evidence.defects")
    elif event == "manager_reject":
        _exact_keys(evidence, {"reason"}, f"{event} evidence")
        if not isinstance(evidence["reason"], str) or not evidence["reason"].strip():
            raise ForceContractError("manager_reject reason must be non-empty")
    elif event == "hard_stop":
        _exact_keys(evidence, {"code", "detail"}, f"{event} evidence")
        if evidence["code"] not in hard_stop_codes:
            raise ForceContractError("hard_stop code is not declared by the contract")
        if not isinstance(evidence["detail"], str) or not evidence["detail"].strip():
            raise ForceContractError("hard_stop detail must be non-empty")
    return evidence


def validate_events(
    contract: dict[str, Any], values: Any, artifact_root: Path
) -> list[dict[str, Any]]:
    if not isinstance(values, list) or not values:
        raise ForceContractError("event log must contain at least task_started")
    resolved_root = _artifact_root(artifact_root)
    events: list[dict[str, Any]] = []
    last_at = contract["started_at_epoch"]
    terminal_seen = False
    task_started_count = 0
    last_rework_sequence = 0
    cycle_started_at = contract["started_at_epoch"]
    cycle_artifact_sequence = 0
    cycle_artifact_paths: dict[str, str] = {}
    candidate_sequence = 0
    candidate_paths: set[str] = set()
    inspection_pass_sequence = 0
    verification_pass_sequence = 0
    receipt_sequence = 0
    rework_requested_sequence = 0
    rework_count = 0
    unresolved_late_paths: set[str] = set()
    late_reviewed_paths: set[str] = set()
    blocked_late_paths: set[str] = set()
    all_materialized_paths: set[str] = set()
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            raise ForceContractError(f"event {index} must be an object")
        _exact_keys(value, {"schema", "sequence", "task_id", "event", "at_epoch", "evidence"}, f"event {index}")
        if value["schema"] != EVENT_SCHEMA:
            raise ForceContractError(f"event {index} schema is unsupported")
        if value["sequence"] != index:
            raise ForceContractError("event sequences must be contiguous starting at one")
        if value["task_id"] != contract["task_id"]:
            raise ForceContractError(f"event {index} task_id does not match contract")
        event = value["event"]
        if event not in EVENTS:
            raise ForceContractError(f"event {index} type is unsupported")
        at_epoch = value["at_epoch"]
        if isinstance(at_epoch, bool) or not isinstance(at_epoch, int) or at_epoch < last_at:
            raise ForceContractError("event timestamps must be non-decreasing and not predate launch")
        if terminal_seen:
            raise ForceContractError("events after a terminal decision are not allowed")
        _validate_evidence(event, value["evidence"], set(contract["hard_stop_codes"]))

        if event == "task_started":
            task_started_count += 1
            if index != 1 or task_started_count != 1:
                raise ForceContractError("task_started must appear exactly once as the first event")
        elif index == 1:
            raise ForceContractError("task_started must be the first event")

        if receipt_sequence > last_rework_sequence and event not in {
            "manager_accept",
            "manager_rework",
            "manager_reject",
            "hard_stop",
        }:
            raise ForceContractError(
                "receipt is sealed; only a manager decision or hard stop may follow"
            )

        if event == "rework_started":
            if rework_requested_sequence <= last_rework_sequence:
                raise ForceContractError("rework_started requires a preceding bounded rework request")
            if rework_count >= contract["control"]["max_rework_cycles"]:
                raise ForceContractError("rework count exceeds contract maximum")
            rework_count += 1
            last_rework_sequence = index
            cycle_started_at = at_epoch
            cycle_artifact_sequence = 0
            cycle_artifact_paths = {}
            candidate_sequence = 0
            candidate_paths = set()
            inspection_pass_sequence = 0
            verification_pass_sequence = 0
            receipt_sequence = 0
            rework_requested_sequence = 0
            unresolved_late_paths = set()
            blocked_late_paths = set()
        elif event == "artifact_materialized":
            path = value["evidence"]["path"]
            if path in all_materialized_paths:
                raise ForceContractError("materialized artifact paths must be immutable and unique")
            digest = _verified_file(resolved_root, path, value["evidence"]["sha256"])
            all_materialized_paths.add(path)
            cycle_artifact_paths[path] = digest
            candidate_sequence = 0
            candidate_paths = set()
            verification_pass_sequence = 0
            inspection_pass_sequence = 0
            receipt_sequence = 0
            if cycle_artifact_sequence == 0:
                cycle_artifact_sequence = index
                if at_epoch - cycle_started_at > contract["soft_slos"]["first_artifact_seconds"]:
                    unresolved_late_paths = {path}
        elif event == "late_output_reviewed":
            reviewed = set(value["evidence"]["artifact_paths"])
            if not unresolved_late_paths:
                raise ForceContractError("late_output_reviewed requires an unresolved late artifact")
            if reviewed != unresolved_late_paths:
                raise ForceContractError("late output review must bind the exact unresolved artifact paths")
            if reviewed & late_reviewed_paths:
                raise ForceContractError("late output review decisions are immutable")
            late_reviewed_paths.update(reviewed)
            unresolved_late_paths = set()
            late_decision = value["evidence"]["decision"]
            if late_decision in {"rework", "reject"}:
                blocked_late_paths.update(reviewed)
            if late_decision == "rework":
                rework_requested_sequence = index
        elif event == "candidate_runnable":
            proposed = set(value["evidence"]["artifact_paths"])
            if cycle_artifact_sequence <= last_rework_sequence:
                raise ForceContractError("candidate requires fresh materialization in the current cycle")
            if unresolved_late_paths:
                raise ForceContractError("late artifact must be reviewed before candidate use")
            if not proposed.issubset(cycle_artifact_paths):
                raise ForceContractError("candidate paths must be materialized in the current cycle")
            if proposed & blocked_late_paths:
                raise ForceContractError("reworked or rejected late output cannot enter a candidate")
            for path in proposed:
                _verified_file(resolved_root, path, cycle_artifact_paths[path])
            candidate_paths = proposed
            candidate_sequence = index
            verification_pass_sequence = 0
            inspection_pass_sequence = 0
            receipt_sequence = 0
        elif event == "verification_passed":
            if candidate_sequence <= last_rework_sequence:
                raise ForceContractError("verification requires a fresh runnable candidate")
            verification_pass_sequence = index
            inspection_pass_sequence = 0
            receipt_sequence = 0
        elif event == "manager_inspection_passed":
            if rework_requested_sequence > last_rework_sequence:
                raise ForceContractError("manager inspection pass requires the requested rework to start")
            if verification_pass_sequence <= candidate_sequence:
                raise ForceContractError(
                    "manager inspection pass requires fresh verification of the current candidate"
                )
            inspected = set(value["evidence"]["artifact_paths"])
            if inspected != candidate_paths:
                raise ForceContractError("manager inspection must bind every current candidate path")
            for path in inspected:
                _verified_file(resolved_root, path, cycle_artifact_paths[path])
            inspection_pass_sequence = index
            receipt_sequence = 0
        elif event == "manager_inspection_failed":
            inspection_pass_sequence = 0
            receipt_sequence = 0
            rework_requested_sequence = index
        elif event == "manager_rework":
            receipt_sequence = 0
            rework_requested_sequence = index
        elif event == "receipt_materialized":
            if inspection_pass_sequence <= verification_pass_sequence:
                raise ForceContractError(
                    "receipt requires fresh manager inspection of the current verified candidate"
                )
            _verified_file(
                resolved_root,
                value["evidence"]["path"],
                value["evidence"]["sha256"],
            )
            receipt_sequence = index
        elif event == "manager_accept":
            if rework_requested_sequence > last_rework_sequence:
                raise ForceContractError("manager acceptance cannot bypass requested rework")
            if receipt_sequence <= last_rework_sequence:
                raise ForceContractError("manager acceptance requires a fresh receipt after rework")

        if event in TERMINAL_EVENTS:
            terminal_seen = True
        last_at = at_epoch
        events.append(value)
    return events


def read_contract(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ForceContractError(f"contract could not be read: {error}") from error
    return validate_contract(value)


def read_events(
    path: Path, contract: dict[str, Any], artifact_root: Path
) -> list[dict[str, Any]]:
    values: list[Any] = []
    try:
        for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                raise ForceContractError(f"event log line {line_number} is blank")
            try:
                values.append(json.loads(raw))
            except json.JSONDecodeError as error:
                raise ForceContractError(f"event log line {line_number} is not JSON") from error
    except (OSError, UnicodeError) as error:
        raise ForceContractError(f"event log could not be read: {error}") from error
    return validate_events(contract, values, artifact_root)


def _latest(events: list[dict[str, Any]], event_type: str, *, after_sequence: int = 0) -> dict[str, Any] | None:
    return next(
        (item for item in reversed(events) if item["event"] == event_type and item["sequence"] > after_sequence),
        None,
    )


def evaluate(contract: dict[str, Any], events: list[dict[str, Any]], now_epoch: int) -> dict[str, Any]:
    if isinstance(now_epoch, bool) or not isinstance(now_epoch, int) or now_epoch < events[-1]["at_epoch"]:
        raise ForceContractError("now_epoch must be an integer at or after the latest event")
    started = contract["started_at_epoch"]
    elapsed = now_epoch - started
    latest_rework = _latest(events, "rework_started")
    rework_sequence = latest_rework["sequence"] if latest_rework else 0
    cycle_started = latest_rework["at_epoch"] if latest_rework else started
    cycle_elapsed = now_epoch - cycle_started
    artifacts = [item for item in events if item["event"] == "artifact_materialized"]
    cycle_artifacts = [item for item in artifacts if item["sequence"] > rework_sequence]
    cycle_first_artifact = cycle_artifacts[0] if cycle_artifacts else None
    latest_cycle_artifact_sequence = (
        cycle_artifacts[-1]["sequence"] if cycle_artifacts else rework_sequence
    )
    candidate = _latest(
        events,
        "candidate_runnable",
        after_sequence=latest_cycle_artifact_sequence,
    )
    verification = (
        _latest(events, "verification_passed", after_sequence=candidate["sequence"])
        if candidate
        else None
    )
    inspection_pass = (
        _latest(events, "manager_inspection_passed", after_sequence=verification["sequence"])
        if verification
        else None
    )
    inspection_fail = _latest(events, "manager_inspection_failed", after_sequence=rework_sequence)
    inspection_failure_is_latest = bool(
        inspection_fail
        and (not inspection_pass or inspection_fail["sequence"] > inspection_pass["sequence"])
    )
    receipt = (
        _latest(events, "receipt_materialized", after_sequence=inspection_pass["sequence"])
        if inspection_pass
        else None
    )
    accepted = _latest(events, "manager_accept")
    rejected = _latest(events, "manager_reject")
    hard_stop = _latest(events, "hard_stop")
    manager_rework = _latest(events, "manager_rework", after_sequence=rework_sequence)
    latest_late_artifact = (
        cycle_first_artifact
        if cycle_first_artifact
        and cycle_first_artifact["at_epoch"] - cycle_started
        > contract["soft_slos"]["first_artifact_seconds"]
        else None
    )
    late_review = _latest(
        events,
        "late_output_reviewed",
        after_sequence=latest_late_artifact["sequence"] if latest_late_artifact else 0,
    )
    fresh_inflight = _latest(
        events,
        "inflight_observed",
        after_sequence=max(
            rework_sequence,
            cycle_artifacts[-1]["sequence"] if cycle_artifacts else 0,
        ),
    )
    fresh_window = contract["control"]["inflight_observation_fresh_seconds"]
    inflight_is_fresh = bool(fresh_inflight and now_epoch - fresh_inflight["at_epoch"] <= fresh_window)

    first_artifact = cycle_first_artifact
    slos = contract["soft_slos"]
    soft_miss_set: set[str] = set()
    cycle_boundaries = [
        {"sequence": 0, "at_epoch": started},
        *[item for item in events if item["event"] == "rework_started"],
    ]
    for cycle_index, boundary in enumerate(cycle_boundaries):
        next_boundary = (
            cycle_boundaries[cycle_index + 1]
            if cycle_index + 1 < len(cycle_boundaries)
            else None
        )
        end_sequence = next_boundary["sequence"] if next_boundary else len(events) + 1
        end_epoch = next_boundary["at_epoch"] if next_boundary else now_epoch
        cycle_events = [
            item
            for item in events
            if boundary["sequence"] < item["sequence"] < end_sequence
        ]
        milestones = {
            "first_artifact": next(
                (item for item in cycle_events if item["event"] == "artifact_materialized"),
                None,
            ),
            "runnable_candidate": next(
                (item for item in cycle_events if item["event"] == "candidate_runnable"),
                None,
            ),
            "verification": next(
                (item for item in cycle_events if item["event"] == "verification_passed"),
                None,
            ),
        }
        milestone_slos = {
            "first_artifact": slos["first_artifact_seconds"],
            "runnable_candidate": slos["runnable_candidate_seconds"],
            "verification": slos["verification_seconds"],
        }
        for name, milestone in milestones.items():
            observed_elapsed = (
                milestone["at_epoch"] - boundary["at_epoch"]
                if milestone
                else end_epoch - boundary["at_epoch"]
            )
            if observed_elapsed > milestone_slos[name]:
                soft_miss_set.add(name)
        cycle_receipt = next(
            (item for item in cycle_events if item["event"] == "receipt_materialized"),
            None,
        )
        cycle_inspection = next(
            (
                item
                for item in reversed(cycle_events)
                if item["event"] == "manager_inspection_passed"
                and (not cycle_receipt or item["sequence"] < cycle_receipt["sequence"])
            ),
            None,
        )
        if cycle_inspection and cycle_receipt:
            if (
                cycle_receipt["at_epoch"] - cycle_inspection["at_epoch"]
                > slos["acceptance_to_receipt_seconds"]
            ):
                soft_miss_set.add("acceptance_to_receipt")
        elif cycle_inspection and not any(
            item["sequence"] > cycle_inspection["sequence"]
            and item["event"] in {"manager_inspection_failed", "manager_rework"}
            for item in cycle_events
        ):
            if end_epoch - cycle_inspection["at_epoch"] > slos["acceptance_to_receipt_seconds"]:
                soft_miss_set.add("acceptance_to_receipt")

        if cycle_receipt:
            cycle_decision = next(
                (
                    item
                    for item in cycle_events
                    if item["sequence"] > cycle_receipt["sequence"]
                    and item["event"] in {"manager_accept", "manager_rework", "manager_reject"}
                ),
                None,
            )
            decision_epoch = cycle_decision["at_epoch"] if cycle_decision else end_epoch
            if decision_epoch - cycle_receipt["at_epoch"] > slos["receipt_to_decision_seconds"]:
                soft_miss_set.add("receipt_to_decision")
    manager_decisions = [
        item
        for item in events
        if item["event"] in {"manager_accept", "manager_rework", "manager_reject"}
    ]
    terminal_manager = manager_decisions[-1] if manager_decisions else None

    first_pass_acceptance: bool | None
    if any(item["event"] in {"manager_inspection_failed", "manager_rework", "manager_reject"} for item in events):
        first_pass_acceptance = False
    elif inspection_pass:
        first_pass_acceptance = True
    else:
        first_pass_acceptance = None

    if hard_stop:
        state, action, reason = "stopped", "stop_and_report", hard_stop["evidence"]["code"]
    elif accepted:
        state, action, reason = "completed", "publish_manager_receipt", "manager accepted the verified receipt"
    elif rejected:
        state, action, reason = "rejected", "report_rejection", rejected["evidence"]["reason"]
    elif latest_late_artifact and not late_review:
        state, action, reason = "late_output_quarantined", "quarantine_and_inspect_late_output", "late output requires an independent quality decision"
    elif late_review and late_review["evidence"]["decision"] == "reject":
        state, action, reason = "late_output_rejected", "manager_decide_rejected_late_output", "manager rejected the late output on quality"
    elif late_review and late_review["evidence"]["decision"] == "rework":
        if sum(item["event"] == "rework_started" for item in events) >= contract["control"]["max_rework_cycles"]:
            state, action, reason = "rework_exhausted", "escalate_rework_exhausted", "late-output defects remain after the rework budget"
        else:
            state, action, reason = "rework_required", "exact_rework", "manager found bounded defects in late output"
    elif manager_rework or inspection_failure_is_latest:
        if sum(item["event"] == "rework_started" for item in events) >= contract["control"]["max_rework_cycles"]:
            state, action, reason = "rework_exhausted", "escalate_rework_exhausted", "named defects remain after the rework budget"
        else:
            state, action, reason = "rework_required", "exact_rework", "manager inspection named bounded defects"
    elif receipt:
        state, action, reason = "decision_ready", "manager_decide_now", "receipt exists and verifies"
    elif verification and inspection_pass:
        state, action, reason = "acceptance_ready", "materialize_receipt_now", "all acceptance inputs are complete"
    elif verification:
        state, action, reason = "inspection_ready", "manager_inspect_now", "verification passed; direct inspection is next"
    elif candidate:
        if cycle_elapsed > slos["verification_seconds"] and not inflight_is_fresh:
            state, action, reason = "verification_late", "send_precise_intervention", "verification SLO missed without fresh in-flight evidence"
        elif cycle_elapsed > slos["verification_seconds"]:
            state, action, reason = "verification_inflight", "continue_bounded_grace", "verification is observably in flight"
        else:
            state, action, reason = "candidate_ready", "verify_candidate", "runnable candidate exists"
    elif first_artifact:
        if cycle_elapsed > slos["runnable_candidate_seconds"] and not inflight_is_fresh:
            state, action, reason = "candidate_late", "send_precise_intervention", "candidate SLO missed without fresh in-flight evidence"
        elif cycle_elapsed > slos["runnable_candidate_seconds"]:
            state, action, reason = "candidate_inflight", "continue_bounded_grace", "candidate work is observably in flight"
        else:
            state, action, reason = "materialized", "produce_runnable_candidate", "at least one real artifact exists"
    elif cycle_elapsed > slos["first_artifact_seconds"] and inflight_is_fresh:
        state, action, reason = "materialization_inflight", "continue_bounded_grace", "first artifact is late but work is observably in flight"
    elif cycle_elapsed > slos["first_artifact_seconds"]:
        state, action, reason = "materialization_late", "send_precise_intervention", "first artifact SLO missed without fresh in-flight evidence"
    else:
        state, action, reason = "materializing", "materialize_first_artifact", "no real artifact exists yet"

    return {
        "schema": "company-os.force-evaluation.v1",
        "ok": True,
        "task_id": contract["task_id"],
        "state": state,
        "next_action": action,
        "reason": reason,
        "metrics": {
            "elapsed_seconds": elapsed,
            "first_artifact_seconds": None if not first_artifact else first_artifact["at_epoch"] - cycle_started,
            "runnable_candidate_seconds": None if not candidate else candidate["at_epoch"] - cycle_started,
            "verification_seconds": None if not verification else verification["at_epoch"] - cycle_started,
            "acceptance_to_receipt_seconds": None if not (inspection_pass and receipt) else receipt["at_epoch"] - inspection_pass["at_epoch"],
            "receipt_to_decision_seconds": None if not (receipt and terminal_manager) else terminal_manager["at_epoch"] - receipt["at_epoch"],
            "first_pass_acceptance": first_pass_acceptance,
            "rework_count": sum(item["event"] == "rework_started" for item in events),
            "manager_intervention_count": sum(item["event"] == "intervention_sent" for item in events),
            "soft_slo_misses": sorted(soft_miss_set),
            "hard_stop_count": sum(item["event"] == "hard_stop" for item in events),
        },
        "bindings": {
            "contract_sha256": canonical_sha256(contract),
            "event_log_sha256": canonical_sha256(events),
            "artifact_set_sha256": canonical_sha256(
                [
                    {
                        "event": item["event"],
                        "path": item["evidence"]["path"],
                        "sha256": item["evidence"]["sha256"],
                    }
                    for item in events
                    if item["event"] in {"artifact_materialized", "receipt_materialized"}
                ]
            ),
            "last_sequence": events[-1]["sequence"],
        },
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("validate", "evaluate"):
        command = commands.add_parser(name)
        command.add_argument("--contract", type=Path, required=True)
        command.add_argument("--events", type=Path, required=True)
        command.add_argument("--artifact-root", type=Path, required=True)
        if name == "evaluate":
            command.add_argument("--now-epoch", type=int, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        contract = read_contract(args.contract)
        events = read_events(args.events, contract, args.artifact_root)
        if args.command == "validate":
            result = {
                "schema": "company-os.force-validation.v1",
                "ok": True,
                "task_id": contract["task_id"],
                "contract_sha256": canonical_sha256(contract),
                "event_log_sha256": canonical_sha256(events),
                "artifact_set_sha256": canonical_sha256(
                    [
                        {
                            "event": item["event"],
                            "path": item["evidence"]["path"],
                            "sha256": item["evidence"]["sha256"],
                        }
                        for item in events
                        if item["event"] in {"artifact_materialized", "receipt_materialized"}
                    ]
                ),
                "event_count": len(events),
            }
        else:
            result = evaluate(contract, events, args.now_epoch)
    except ForceContractError as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
