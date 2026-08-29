#!/usr/bin/env python3
"""Controller enforced mission execution state for Company OS."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

STATE_SCHEMA = "company-os.mission-execution-state.v2"
FIRST_REALITY_SCHEMA = "company-os.first-reality-contract.v1"
EVENT_SCHEMA = "company-os.mission-execution-event.v1"
ADMISSION_SCHEMA = "company-os.work-admission-request.v1"
ADMISSION_RECEIPT_SCHEMA = "company-os.work-admission-receipt.v1"
WAKE_SCHEMA = "company-os.scheduler-wake.v1"
REALITY_SPIKE_SCHEMA = "company-os.reality-spike-receipt.v1"
CHECKPOINT_SCHEMA = "company-os.product-checkpoint-request.v1"

MISSION_CLASSES = {
    "quick_build": {"duration_minutes": 90, "max_managers": 1, "max_workers": 2},
    "bounded_feature": {"duration_minutes": 180, "max_managers": 3, "max_workers": 6},
    "company_mission": {"duration_minutes": 420, "max_managers": 8, "max_workers": 24},
    "long_running_company": {"duration_minutes": 1440, "max_managers": 16, "max_workers": 64},
}
WORK_CLASSES = {
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
}
EXECUTION_CLASSES = {"implementation", "integration", "runtime", "repair"}
# Share of the mission budget (time or tokens, whichever runs out first) that
# may be spent before the first real artifact exists. Past this point the
# governor pauses every non-execution work class fail-closed.
FIRST_ARTIFACT_BUDGET_FRACTION = 0.25
CAPABILITY_ORDER = {"missing": 0, "partial": 1, "runnable": 2, "connected": 3, "verified": 4}
EVENT_KINDS = {
    "work_recorded",
    "artifact_materialized",
    "runtime_observed",
    "journey_connected",
    "independent_accepted",
    "task_failed",
    "task_completed",
    "checkpoint_recorded",
    "wake_consumed",
    "manager_intervened",
    "worker_replaced",
    "manager_replaced",
}
STATUS_VALUES = {"active", "accepted", "blocked", "expired", "cancelled"}
SCHEDULER_STATUSES = {"active", "revoked"}
TERMINAL_MISSION_STATUSES = {"accepted", "expired", "cancelled"}
SCHEDULER_FIELDS = {
    "mission_id",
    "generation",
    "owner_id",
    "started_at",
    "expires_at",
    "max_wakes",
    "wake_count",
    "status",
}


class MissionControlError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise MissionControlError("E_SCHEMA", f"{label} must be nonempty")
    return value.strip()


def finite(value: Any, label: str, *, minimum: float = 0.0) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise MissionControlError("E_SCHEMA", f"{label} must be finite")
    result = float(value)
    if result < minimum:
        raise MissionControlError("E_SCHEMA", f"{label} must be at least {minimum}")
    return result


def integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise MissionControlError("E_SCHEMA", f"{label} must be an integer of at least {minimum}")
    return value


def parse_time(value: Any, label: str) -> datetime:
    raw = text(value, label)
    try:
        result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MissionControlError("E_TIME", f"{label} is not RFC3339") from exc
    if result.tzinfo is None:
        raise MissionControlError("E_TIME", f"{label} must include timezone")
    return result.astimezone(timezone.utc)


def format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def safe_relative(value: Any, label: str) -> str:
    raw = text(value, label)
    pure = PurePosixPath(raw)
    if "\\" in raw or pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise MissionControlError("E_PATH", f"{label} is unsafe")
    return pure.as_posix()


def sha256(value: Any, label: str) -> str:
    raw = text(value, label)
    if len(raw) != 64 or any(character not in "0123456789abcdef" for character in raw):
        raise MissionControlError("E_SCHEMA", f"{label} must be lowercase sha256")
    return raw


def seal(value: Mapping[str, Any], field: str = "state_sha256") -> dict[str, Any]:
    result = deepcopy(dict(value))
    result[field] = None
    result[field] = digest(result)
    return result


def verify_seal(value: Mapping[str, Any], field: str = "state_sha256") -> dict[str, Any]:
    result = deepcopy(dict(value))
    observed = sha256(result.get(field), field)
    result[field] = None
    if digest(result) != observed:
        raise MissionControlError("E_DIGEST", f"{field} changed")
    result[field] = observed
    return result


def company_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_module(relative: str, name: str):
    path = company_root() / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise MissionControlError("E_RUNTIME", f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def governor_module():
    return load_module(
        "govern-outcome-execution/scripts/executive_governor.py",
        "company_os_mission_executive_governor",
    )


def navigation_module():
    return load_module(
        "navigation-control/scripts/navigation_control.py",
        "company_os_mission_navigation_control",
    )


def classify_mission(objective: str, override: str | None = None) -> str:
    if override is not None:
        if override not in MISSION_CLASSES:
            raise MissionControlError("E_CLASS", f"unsupported mission class {override}")
        return override
    lowered = objective.casefold()
    broad_markers = (
        "entire platform",
        "full application",
        "complete system",
        "autonomously",
        "production quality",
        "company",
        "multiple companies",
        "backend",
        "security",
        "billing",
        "seven hour",
    )
    long_markers = ("ongoing company", "continuous operations", "run indefinitely", "always on")
    if any(marker in lowered for marker in long_markers):
        return "long_running_company"
    if sum(marker in lowered for marker in broad_markers) >= 3 or len(objective) > 900:
        return "company_mission"
    feature_markers = ("feature", "integration", "workflow", "agent", "dashboard", "api", "database")
    if any(marker in lowered for marker in feature_markers) or len(objective) > 280:
        return "bounded_feature"
    return "quick_build"


def deadline_schedule(started_at: datetime, duration_minutes: int, mission_class: str) -> dict[str, str]:
    duration = max(1, duration_minutes)
    if mission_class == "quick_build":
        fractions = {
            "first_mutation": 0.10,
            "first_runtime": 0.18,
            "first_render": 0.28,
            "connected_r3": 0.50,
            "independent_review": 0.72,
            "reality_closure": 0.88,
        }
    else:
        fractions = {
            "first_mutation": min(15 / duration, 0.08),
            "first_runtime": min(20 / duration, 0.12),
            "first_render": min(40 / duration, 0.20),
            "connected_r3": 0.25,
            "independent_review": 0.36,
            "reality_closure": 0.88,
        }
    return {
        name: format_time(started_at + timedelta(minutes=max(1.0, duration * fraction)))
        for name, fraction in fractions.items()
    }


def _artifact_records(artifact_contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = artifact_contract.get("artifact_classes")
    if not isinstance(records, list) or not records:
        raise MissionControlError("E_ARTIFACT", "artifact contract contains no classes")
    result = []
    for index, raw in enumerate(records):
        if not isinstance(raw, Mapping):
            raise MissionControlError("E_ARTIFACT", f"artifact class {index} is invalid")
        artifact_id = text(raw.get("artifact_class_id"), f"artifact_classes[{index}].artifact_class_id")
        if raw.get("required") is not True:
            continue
        modalities = [str(item).casefold() for item in raw.get("modalities", []) if isinstance(item, str)]
        methods = [str(item).casefold() for item in raw.get("observation_methods", []) if isinstance(item, str)]
        result.append(
            {
                "artifact_class_id": artifact_id,
                "label": str(raw.get("label") or artifact_id),
                "modalities": modalities,
                "observation_methods": methods,
            }
        )
    if not result:
        raise MissionControlError("E_ARTIFACT", "artifact contract contains no required classes")
    return result


def _first_reality_score(record: Mapping[str, Any]) -> tuple[int, str]:
    joined = " ".join(
        [record.get("artifact_class_id", ""), record.get("label", "")]
        + list(record.get("modalities", []))
        + list(record.get("observation_methods", []))
    ).casefold()
    score = 0
    for marker, weight in {
        "interactive": 100,
        "executable": 95,
        "browser": 90,
        "runtime": 90,
        "service": 85,
        "application": 85,
        "workflow": 85,
        "api": 80,
        "game": 80,
        "ui": 75,
        "website": 75,
        "integration": 70,
        "render": 65,
        "database": 45,
        "document": 10,
        "report": 0,
        "plan": 0,
        "schema": 0,
    }.items():
        if marker in joined:
            score = max(score, weight)
    return (-score, str(record.get("artifact_class_id")))


def compile_first_reality(
    objective_id: str,
    objective: str,
    artifact_contract: Mapping[str, Any],
    *,
    explicit: Mapping[str, Any] | None = None,
    mission_class: str = "company_mission",
) -> dict[str, Any]:
    objective_id = text(objective_id, "objective_id")
    objective = text(objective, "objective")
    records = _artifact_records(artifact_contract)
    all_ids = [record["artifact_class_id"] for record in records]
    if explicit is not None:
        requested = explicit.get("required_artifact_class_ids")
        if not isinstance(requested, list) or not requested:
            raise MissionControlError("E_FIRST_REALITY", "explicit first reality classes are empty")
        selected = [text(item, "required_artifact_class_id") for item in requested]
        unknown = sorted(set(selected) - set(all_ids))
        if unknown:
            raise MissionControlError("E_FIRST_REALITY", f"unknown first reality artifact classes: {unknown}")
        journey_steps = explicit.get("journey_steps")
        if not isinstance(journey_steps, list) or not journey_steps or not all(isinstance(item, str) and item.strip() for item in journey_steps):
            raise MissionControlError("E_FIRST_REALITY", "explicit journey steps are invalid")
        required_observations = explicit.get("required_observations", ["artifact_bytes", "runtime_receipt", "connected_journey_receipt"])
    else:
        ordered = sorted(records, key=_first_reality_score)
        limit = 1 if mission_class == "quick_build" else min(2, len(ordered))
        selected = [record["artifact_class_id"] for record in ordered[:limit]]
        labels = [record["label"] for record in ordered[:limit]]
        journey_steps = [
            "A fresh operator starts the smallest reversible product path.",
            *[f"The real {label} artifact is materialized and exercised." for label in labels],
            "One connected user-observable outcome completes without a mocked success claim.",
        ]
        required_observations = ["artifact_bytes", "runtime_receipt", "connected_journey_receipt"]
    deferred = sorted(set(all_ids) - set(selected))
    contract = {
        "$schema": FIRST_REALITY_SCHEMA,
        "objective_id": objective_id,
        "objective": objective,
        "journey_id": "first-reality",
        "journey_steps": journey_steps,
        "required_capability_ids": list(selected),
        "required_artifact_class_ids": list(selected),
        "required_observations": list(required_observations),
        "deferred_capability_ids": deferred,
        "deadline_fraction": 0.25,
        "contract_sha256": None,
    }
    contract["contract_sha256"] = digest(contract)
    return contract


def verify_first_reality(raw: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(raw))
    if value.get("$schema") != FIRST_REALITY_SCHEMA:
        raise MissionControlError("E_SCHEMA", "first reality contract schema is invalid")
    observed = sha256(value.get("contract_sha256"), "contract_sha256")
    value["contract_sha256"] = None
    if digest(value) != observed:
        raise MissionControlError("E_DIGEST", "first reality contract changed")
    value["contract_sha256"] = observed
    return value


def provisional_capabilities(objective: str) -> list[dict[str, Any]]:
    lowered = objective.casefold()
    result = [
        {
            "capability_id": "first_real_artifact",
            "label": "First real artifact",
            "critical": True,
            "priority": 100,
            "first_reality": True,
            "final_required": True,
            "existing_implementation": None,
            "state": "missing",
            "evidence": [],
        }
    ]
    supplied = re.findall(r"https://github\.com/[^\s)]+", objective)
    if supplied:
        result[0]["priority"] = 90
        result.append(
            {
                "capability_id": "supplied_implementation_integration",
                "label": "Supplied implementation integration",
                "critical": True,
                "priority": 100,
                "first_reality": True,
                "final_required": True,
                "existing_implementation": ", ".join(sorted(set(supplied))),
                "state": "missing",
                "evidence": [],
            }
        )
    if any(marker in lowered for marker in ("website", "ui", "dashboard", "application", "app", "widget", "game")):
        result.append(
            {
                "capability_id": "rendered_user_path",
                "label": "Rendered user path",
                "critical": True,
                "priority": 90,
                "first_reality": True,
                "final_required": True,
                "existing_implementation": None,
                "state": "missing",
                "evidence": [],
            }
        )
    return result


def capability_records(first_reality: Mapping[str, Any], artifact_contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    contract = verify_first_reality(first_reality)
    existing = {item["artifact_class_id"]: item for item in _artifact_records(artifact_contract)}
    result = []
    first = set(contract["required_capability_ids"])
    for artifact_id, record in sorted(existing.items()):
        result.append(
            {
                "capability_id": artifact_id,
                "label": record["label"],
                "critical": artifact_id in first,
                "priority": 100 if artifact_id in first else 50,
                "first_reality": artifact_id in first,
                "final_required": True,
                "existing_implementation": None,
                "state": "missing",
                "evidence": [],
            }
        )
    return result


def initialize_state(
    objective_id: str,
    objective: str,
    *,
    started_at: str | None = None,
    mission_class: str | None = None,
    duration_minutes: int | None = None,
    token_budget: int | None = None,
    artifact_contract: Mapping[str, Any] | None = None,
    explicit_first_reality: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    objective_id = text(objective_id, "objective_id")
    objective = text(objective, "objective")
    klass = classify_mission(objective, mission_class)
    duration = duration_minutes or MISSION_CLASSES[klass]["duration_minutes"]
    integer(duration, "duration_minutes", minimum=1)
    if token_budget is not None:
        integer(token_budget, "token_budget", minimum=1)
    start = parse_time(started_at, "started_at") if started_at is not None else now_utc()
    expiry = start + timedelta(minutes=duration)
    first_reality = None
    capabilities = provisional_capabilities(objective)
    if artifact_contract is not None:
        first_reality = compile_first_reality(
            objective_id,
            objective,
            artifact_contract,
            explicit=explicit_first_reality,
            mission_class=klass,
        )
        capabilities = capability_records(first_reality, artifact_contract)
    state = {
        "$schema": STATE_SCHEMA,
        "schema_version": 2,
        "mission_id": objective_id,
        "objective_id": objective_id,
        "objective": objective,
        "mission_class": klass,
        "duration_minutes": duration,
        "started_at": format_time(start),
        "expires_at": format_time(expiry),
        "status": "active",
        "generation": 1,
        "token_budget": token_budget,
        "tokens_consumed": 0.0,
        "deadlines": deadline_schedule(start, duration, klass),
        "deadline_status": {},
        "first_reality": first_reality,
        "capabilities": capabilities,
        "events": [],
        "work_units": {name: 0.0 for name in sorted(WORK_CLASSES)},
        "tasks": {},
        "managers": {},
        "workers": {},
        "interventions": [],
        "replacement_orders": [],
        "consumed_wake_keys": [],
        "scheduler": {
            "mission_id": objective_id,
            "generation": 1,
            "owner_id": "company-os-director",
            "started_at": format_time(start),
            "expires_at": format_time(expiry),
            "max_wakes": 256 if klass == "long_running_company" else 64,
            "wake_count": 0,
            "status": "active",
        },
        "navigation": None,
        "governor_decision": None,
        "checkpoint": None,
        "state_sha256": None,
    }
    return refresh_governor(seal(state), now=start)


def verify_scheduler(state: Mapping[str, Any]) -> dict[str, Any]:
    scheduler = state.get("scheduler")
    if not isinstance(scheduler, Mapping) or not SCHEDULER_FIELDS.issubset(scheduler):
        raise MissionControlError("E_SCHEDULER", "mission scheduler lease is missing required fields")
    if scheduler.get("mission_id") != state.get("mission_id"):
        raise MissionControlError("E_SCHEDULER", "scheduler mission_id drifted from the mission")
    if integer(scheduler.get("generation"), "scheduler.generation", minimum=1) != integer(
        state.get("generation"), "generation", minimum=1
    ):
        raise MissionControlError("E_SCHEDULER", "scheduler generation drifted from the mission")
    if scheduler.get("started_at") != state.get("started_at"):
        raise MissionControlError("E_SCHEDULER", "scheduler started_at drifted from the mission")
    if scheduler.get("expires_at") != state.get("expires_at"):
        raise MissionControlError("E_SCHEDULER", "scheduler expires_at drifted from the mission")
    text(scheduler.get("owner_id"), "scheduler.owner_id")
    if scheduler.get("status") not in SCHEDULER_STATUSES:
        raise MissionControlError("E_SCHEDULER", "scheduler status is invalid")
    if state.get("status") == "active" and scheduler.get("status") != "active":
        raise MissionControlError("E_SCHEDULER", "active mission has a revoked scheduler lease")
    if state.get("status") in TERMINAL_MISSION_STATUSES and scheduler.get("status") != "revoked":
        raise MissionControlError("E_SCHEDULER", "terminal mission did not revoke the scheduler lease")
    max_wakes = integer(scheduler.get("max_wakes"), "scheduler.max_wakes", minimum=1)
    wake_count = integer(scheduler.get("wake_count"), "scheduler.wake_count", minimum=0)
    consumed = state.get("consumed_wake_keys")
    if not isinstance(consumed, list) or any(not isinstance(item, str) or not item.strip() for item in consumed):
        raise MissionControlError("E_SCHEDULER", "consumed wake keys are invalid")
    if len(consumed) != len(set(consumed)):
        raise MissionControlError("E_SCHEDULER", "consumed wake keys drifted")
    if wake_count != len(consumed):
        raise MissionControlError("E_SCHEDULER", "scheduler wake_count drifted from consumed keys")
    if wake_count > max_wakes:
        raise MissionControlError("E_SCHEDULER", "scheduler wake_count exceeds max_wakes")
    return dict(scheduler)


def verify_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    value = verify_seal(raw)
    if value.get("$schema") != STATE_SCHEMA or value.get("schema_version") != 2:
        raise MissionControlError("E_SCHEMA", "mission execution state schema is invalid")
    if value.get("status") not in STATUS_VALUES:
        raise MissionControlError("E_SCHEMA", "mission status is invalid")
    if value.get("mission_class") not in MISSION_CLASSES:
        raise MissionControlError("E_SCHEMA", "mission class is invalid")
    parse_time(value.get("started_at"), "started_at")
    parse_time(value.get("expires_at"), "expires_at")
    if not isinstance(value.get("capabilities"), list) or not value["capabilities"]:
        raise MissionControlError("E_SCHEMA", "mission capabilities are missing")
    verify_scheduler(value)
    if value.get("navigation") is not None:
        try:
            navigation_module().verify(value["navigation"])
        except Exception as exc:
            raise MissionControlError("E_NAVIGATION", f"navigation state is invalid: {exc}") from exc
    return value


def _evidence_record(raw: Mapping[str, Any], *, require_file: bool = True) -> dict[str, Any]:
    kind = text(raw.get("kind"), "evidence.kind")
    record = {"kind": kind}
    if require_file:
        record["path"] = safe_relative(raw.get("path"), "evidence.path")
        record["sha256"] = sha256(raw.get("sha256"), "evidence.sha256")
    if raw.get("artifact_class_id") is not None:
        record["artifact_class_id"] = text(raw.get("artifact_class_id"), "evidence.artifact_class_id")
    if raw.get("capability_id") is not None:
        record["capability_id"] = text(raw.get("capability_id"), "evidence.capability_id")
    return record


def _set_capability_state(state: dict[str, Any], capability_id: str, target: str, evidence: dict[str, Any]) -> None:
    if target not in CAPABILITY_ORDER:
        raise MissionControlError("E_CAPABILITY", f"unknown capability state {target}")
    matches = [item for item in state["capabilities"] if item.get("capability_id") == capability_id]
    if len(matches) != 1:
        raise MissionControlError("E_CAPABILITY", f"unknown or duplicate capability {capability_id}")
    capability = matches[0]
    if CAPABILITY_ORDER[target] < CAPABILITY_ORDER[capability["state"]]:
        raise MissionControlError("E_CAPABILITY", "capability state cannot regress through an evidence event")
    if CAPABILITY_ORDER[target] > CAPABILITY_ORDER[capability["state"]] + 1:
        raise MissionControlError("E_CAPABILITY", "capability state cannot skip an evidence level")
    capability["state"] = target
    if evidence not in capability["evidence"]:
        capability["evidence"].append(evidence)


def reality_signals(state: Mapping[str, Any]) -> dict[str, bool]:
    capabilities = [item for item in state.get("capabilities", []) if isinstance(item, Mapping)]
    first = [item for item in capabilities if item.get("first_reality") is True]
    final = [item for item in capabilities if item.get("final_required") is True]
    if not first:
        first = capabilities
    minimum_first = min((CAPABILITY_ORDER.get(str(item.get("state")), 0) for item in first), default=0)
    minimum_final = min((CAPABILITY_ORDER.get(str(item.get("state")), 0) for item in final), default=0)
    checkpointed = bool(state.get("checkpoint"))
    return {
        "internal_primitives": minimum_first >= 1,
        "runnable_capability": minimum_first >= 2,
        "connected_vertical_slice": minimum_first >= 3,
        "user_usable": minimum_final >= 3 and checkpointed,
        "independent_acceptance": minimum_final >= 4 and checkpointed,
    }


def _allocation(state: Mapping[str, Any]) -> dict[str, float]:
    raw = state.get("work_units", {})
    if not isinstance(raw, Mapping):
        return {}
    total = sum(float(raw.get(name, 0.0)) for name in WORK_CLASSES)
    if total <= 0:
        return {}
    return {name: float(raw.get(name, 0.0)) / total for name in WORK_CLASSES}


def _budget_fraction(state: Mapping[str, Any], now: datetime) -> float:
    start = parse_time(state.get("started_at"), "started_at")
    expiry = parse_time(state.get("expires_at"), "expires_at")
    total = max((expiry - start).total_seconds(), 1.0)
    time_fraction = max(0.0, min(1.0, (now - start).total_seconds() / total))
    # A mission can burn its entire token allowance in minutes of wall clock;
    # the governor must see that spend as consumed budget or the planning
    # meter never fires on exactly the failure it exists to stop. The meter
    # advances on whichever resource is scarcer.
    token_budget = state.get("token_budget")
    token_fraction = 0.0
    if isinstance(token_budget, int) and not isinstance(token_budget, bool) and token_budget > 0:
        consumed = state.get("tokens_consumed", 0)
        if isinstance(consumed, (int, float)) and not isinstance(consumed, bool) and math.isfinite(float(consumed)):
            token_fraction = max(0.0, min(1.0, float(consumed) / float(token_budget)))
    return max(time_fraction, token_fraction)


def _governor_input(state: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    return {
        "$schema": governor_module().INPUT_SCHEMA,
        "objective_id": state["objective_id"],
        "objective": state["objective"],
        "budget_fraction_consumed": _budget_fraction(state, now),
        "first_artifact_budget_fraction": FIRST_ARTIFACT_BUDGET_FRACTION,
        "reality": reality_signals(state),
        "required_capabilities": [
            {
                "capability_id": item["capability_id"],
                "state": item["state"],
                "critical": item.get("critical") is True,
                "priority": int(item.get("priority", 50)),
                "existing_implementation": item.get("existing_implementation"),
            }
            for item in state["capabilities"]
        ],
        "allocation": _allocation(state),
    }


def _navigation_input(state: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    return {
        "$schema": navigation_module().INPUT_SCHEMA,
        "objective_id": state["objective_id"],
        "objective": state["objective"],
        "now": format_time(now),
        "mission_class": state["mission_class"],
        "capabilities": [
            {
                "capability_id": item["capability_id"],
                "label": item.get("label") or item["capability_id"],
                "state": item["state"],
                "critical": item.get("critical") is True,
                "priority": int(item.get("priority", 50)),
                "first_reality": item.get("first_reality") is True,
                "final_required": item.get("final_required") is not False,
                "existing_implementation": item.get("existing_implementation"),
            }
            for item in state["capabilities"]
        ],
        "reality": reality_signals(state),
        "checkpointed": bool(state.get("checkpoint")),
        "allocation": _allocation(state),
        "events": [dict(item) for item in state.get("events", []) if isinstance(item, Mapping)],
        "previous_navigation": state.get("navigation"),
    }


def _apply_navigation_to_governor(decision: Mapping[str, Any], navigation: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(decision))
    nav = navigation_module().verify(navigation)
    next_action = dict(nav.get("next_action") or {})
    target_id = next_action.get("capability_id")
    if target_id is not None:
        match = next((item for item in result.get("required_capabilities", []) if item.get("capability_id") == target_id), None)
        if match is not None:
            result["dominant_bottleneck"] = match
    result["navigation_decision_sha256"] = nav["decision_sha256"]
    result["navigation_mode"] = nav["mode"]
    result["waypoint"] = nav["waypoint"]
    result["destination_distance"] = nav["position"]["destination_distance"]
    result["waypoint_distance"] = nav["position"]["waypoint_distance"]
    result["objective_velocity"] = nav["velocity"]
    result["next_action"] = next_action
    result["sensor_posture"] = nav["sensor_posture"]
    result["actuation_policy"] = nav["actuation_policy"]
    result["manager_orders"] = list(dict.fromkeys([*nav.get("orders", []), *result.get("manager_orders", [])]))

    should_tighten = nav["mode"] == "stalled_replan" or nav["sensor_posture"].get("overrun") is True
    if should_tighten and result.get("mode") != "accepted":
        next_work = next_action.get("work_class")
        allowed = set(result.get("allowed_work_classes", []))
        sensor_classes = set(navigation_module().SENSOR_CLASSES)
        keep_sensors = {"evaluation"}
        allowed -= sensor_classes - keep_sensors
        if next_work in WORK_CLASSES:
            allowed.add(next_work)
        allowed.update({"implementation", "integration", "runtime", "repair", "checkpoint", "packaging"} & set(WORK_CLASSES))
        result["allowed_work_classes"] = [name for name in sorted(WORK_CLASSES) if name in allowed]
        result["paused_work_classes"] = [name for name in sorted(WORK_CLASSES) if name not in allowed]
        if result.get("mode") == "normal":
            result["mode"] = "compression"
    result["decision_sha256"] = None
    result["decision_sha256"] = governor_module().digest(result)
    return result


def _deadline_evidence(state: Mapping[str, Any]) -> dict[str, bool]:
    signals = reality_signals(state)
    has_mutation = any(
        event.get("kind") in {"artifact_materialized", "checkpoint_recorded"}
        for event in state.get("events", [])
        if isinstance(event, Mapping)
    )
    has_runtime = signals["runnable_capability"]
    has_render = any(
        event.get("kind") == "runtime_observed" and event.get("observation_kind") in {"browser", "simulator", "render", "gameplay"}
        for event in state.get("events", [])
        if isinstance(event, Mapping)
    )
    return {
        "first_mutation": has_mutation,
        "first_runtime": has_runtime,
        "first_render": has_render or (has_runtime and not any("render" in str(item.get("label", "")).casefold() for item in state.get("capabilities", []))),
        "connected_r3": signals["connected_vertical_slice"],
        "independent_review": signals["independent_acceptance"],
        "reality_closure": False,
    }


def reconcile_deadlines(raw_state: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    state = verify_state(raw_state)
    current = now or now_utc()
    status = dict(state.get("deadline_status", {}))
    evidence = _deadline_evidence(state)
    tasks = deepcopy(state.get("tasks", {}))
    workers = deepcopy(state.get("workers", {}))
    managers = deepcopy(state.get("managers", {}))
    interventions = deepcopy(state.get("interventions", []))
    replacements = deepcopy(state.get("replacement_orders", []))
    for name, deadline_raw in state.get("deadlines", {}).items():
        deadline = parse_time(deadline_raw, f"deadlines.{name}")
        previous = status.get(name, {"miss_count": 0, "satisfied": False})
        if evidence.get(name) is True:
            status[name] = {"satisfied": True, "miss_count": previous.get("miss_count", 0), "satisfied_at": format_time(current)}
            continue
        if current <= deadline or name == "reality_closure":
            status[name] = previous
            continue
        miss_count = int(previous.get("miss_count", 0)) + 1 if previous.get("last_checked_at") != format_time(current) else int(previous.get("miss_count", 0))
        status[name] = {"satisfied": False, "miss_count": miss_count, "last_checked_at": format_time(current)}
        if miss_count == 1:
            interventions.append(
                {
                    "intervention_id": f"deadline:{name}:1",
                    "kind": "deadline_intervention",
                    "deadline": name,
                    "issued_at": format_time(current),
                    "order": "Stop support work and perform the exact missing execution action.",
                }
            )
        elif miss_count == 2:
            active_workers = sorted(key for key, item in workers.items() if isinstance(item, Mapping) and item.get("status") == "active")
            targets = active_workers[:1] or ["current-bottleneck-worker"]
            for worker_id in targets:
                order = {
                    "order_id": f"replace-worker:{worker_id}:{name}",
                    "kind": "replace_worker",
                    "worker_id": worker_id,
                    "reason": f"second miss of {name}",
                    "issued_at": format_time(current),
                }
                if order not in replacements:
                    replacements.append(order)
                if worker_id in workers:
                    workers[worker_id] = {**workers[worker_id], "status": "replace"}
        elif miss_count >= 3:
            active_managers = sorted(key for key, item in managers.items() if isinstance(item, Mapping) and item.get("status") == "active")
            targets = active_managers[:1] or ["current-bottleneck-manager"]
            for manager_id in targets:
                order = {
                    "order_id": f"replace-manager:{manager_id}:{name}",
                    "kind": "replace_manager",
                    "manager_id": manager_id,
                    "reason": f"repeated mission deadline failure: {name}",
                    "issued_at": format_time(current),
                }
                if order not in replacements:
                    replacements.append(order)
                if manager_id in managers:
                    managers[manager_id] = {**managers[manager_id], "status": "replace"}
    updated = {
        **state,
        "deadline_status": status,
        "tasks": tasks,
        "workers": workers,
        "managers": managers,
        "interventions": interventions,
        "replacement_orders": replacements,
    }
    return seal(updated)


def refresh_governor(raw_state: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    state = verify_state(raw_state)
    current = now or now_utc()
    if current >= parse_time(state["expires_at"], "expires_at") and state["status"] == "active":
        state["status"] = "expired"
        state["scheduler"] = {**state["scheduler"], "status": "revoked", "generation": int(state["generation"]) + 1}
        state["generation"] = int(state["generation"]) + 1
    decision = governor_module().evaluate(_governor_input(state, current))
    navigation = navigation_module().evaluate(_navigation_input(state, current))
    state["navigation"] = navigation
    state["governor_decision"] = _apply_navigation_to_governor(decision, navigation)
    return seal(state)


def verify_reality_spike(
    project_root: Path,
    raw: Mapping[str, Any],
    *,
    objective_id: str | None = None,
) -> dict[str, Any]:
    value = deepcopy(dict(raw))
    if value.get("$schema") != REALITY_SPIKE_SCHEMA:
        raise MissionControlError("E_SCHEMA", "reality spike receipt schema is invalid")
    if objective_id is not None and value.get("objective_id") != objective_id:
        raise MissionControlError("E_BINDING", "reality spike objective is incorrect")
    observed = sha256(value.get("receipt_sha256"), "receipt_sha256")
    unsigned = deepcopy(value)
    unsigned["receipt_sha256"] = None
    if digest(unsigned) != observed:
        raise MissionControlError("E_DIGEST", "reality spike receipt changed")
    root = project_root.resolve()
    artifacts = value.get("artifacts")
    observations = value.get("observations")
    commands = value.get("commands")
    blockers = value.get("blockers")
    if not isinstance(artifacts, list) or not artifacts:
        raise MissionControlError("E_SPIKE", "reality spike contains no product artifacts")
    if not isinstance(observations, list) or not observations:
        raise MissionControlError("E_SPIKE", "reality spike contains no runtime observations")
    if not isinstance(commands, list) or not commands:
        raise MissionControlError("E_SPIKE", "reality spike contains no executed commands")
    if not isinstance(blockers, list):
        raise MissionControlError("E_SPIKE", "reality spike blockers must be an array")
    for collection_name, records in (("artifacts", artifacts), ("observations", observations)):
        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                raise MissionControlError("E_SPIKE", f"{collection_name}[{index}] is invalid")
            capability_id = text(record.get("capability_id"), f"{collection_name}[{index}].capability_id")
            relative = safe_relative(record.get("path"), f"{collection_name}[{index}].path")
            expected = sha256(record.get("sha256"), f"{collection_name}[{index}].sha256")
            resolved = (root / Path(*PurePosixPath(relative).parts)).resolve(strict=True)
            if (resolved != root and root not in resolved.parents) or not resolved.is_file() or resolved.is_symlink():
                raise MissionControlError("E_PATH", f"{collection_name}[{index}] is not a regular project file")
            if file_digest(resolved) != expected:
                raise MissionControlError("E_DIGEST", f"{collection_name}[{index}] bytes changed")
            if collection_name == "observations" and record.get("kind") not in {"runtime_observed", "journey_connected"}:
                raise MissionControlError("E_SPIKE", f"unsupported spike observation kind for {capability_id}")
    for index, command in enumerate(commands):
        if not isinstance(command, Mapping):
            raise MissionControlError("E_SPIKE", f"commands[{index}] is invalid")
        text(command.get("command"), f"commands[{index}].command")
        integer(command.get("exit_code"), f"commands[{index}].exit_code", minimum=0)
    return value


def ingest_reality_spike(
    raw_state: Mapping[str, Any],
    project_root: Path,
    raw_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    state = verify_state(raw_state)
    receipt = verify_reality_spike(project_root, raw_receipt, objective_id=state["objective_id"])
    stamp = text(receipt.get("completed_at"), "completed_at")
    parse_time(stamp, "completed_at")
    receipt_id = receipt["receipt_sha256"][:16]
    known = {item["capability_id"] for item in state["capabilities"]}
    for index, artifact in enumerate(receipt["artifacts"]):
        capability_id = artifact["capability_id"]
        if capability_id not in known:
            continue
        current = next(item for item in state["capabilities"] if item["capability_id"] == capability_id)
        if current["state"] != "missing":
            continue
        state = record_event(
            state,
            make_event(
                f"spike:{receipt_id}:artifact:{index}",
                "artifact_materialized",
                occurred_at=stamp,
                work_class="implementation",
                capability_id=capability_id,
                evidence={"kind": "reality_spike_artifact", "path": artifact["path"], "sha256": artifact["sha256"], "capability_id": capability_id},
            ),
        )
    ordered = sorted(
        receipt["observations"],
        key=lambda item: (0 if item.get("kind") == "runtime_observed" else 1, str(item.get("capability_id")), str(item.get("path"))),
    )
    for index, observation in enumerate(ordered):
        capability_id = observation["capability_id"]
        if capability_id not in known:
            continue
        current = next(item for item in state["capabilities"] if item["capability_id"] == capability_id)
        expected = "partial" if observation["kind"] == "runtime_observed" else "runnable"
        if current["state"] != expected:
            continue
        state = record_event(
            state,
            make_event(
                f"spike:{receipt_id}:observation:{index}",
                observation["kind"],
                occurred_at=stamp,
                work_class="runtime" if observation["kind"] == "runtime_observed" else "integration",
                capability_id=capability_id,
                evidence={"kind": observation.get("observation_kind") or observation["kind"], "path": observation["path"], "sha256": observation["sha256"], "capability_id": capability_id},
                observation_kind=observation.get("observation_kind") or observation["kind"],
            ),
        )
    return state


def update_scope(
    raw_state: Mapping[str, Any],
    artifact_contract: Mapping[str, Any],
    *,
    explicit_first_reality: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state = verify_state(raw_state)
    first = compile_first_reality(
        state["objective_id"],
        state["objective"],
        artifact_contract,
        explicit=explicit_first_reality,
        mission_class=state["mission_class"],
    )
    old = {item["capability_id"]: item for item in state["capabilities"]}
    capabilities = capability_records(first, artifact_contract)
    for capability in capabilities:
        prior = old.get(capability["capability_id"])
        if prior:
            capability["state"] = prior.get("state", "missing")
            capability["evidence"] = deepcopy(prior.get("evidence", []))
            if prior.get("existing_implementation"):
                capability["existing_implementation"] = prior["existing_implementation"]
    selected_ids = list(first.get("required_capability_ids", []))
    selected = {item["capability_id"]: item for item in capabilities if item["capability_id"] in selected_ids}
    provisional = old.get("first_real_artifact")
    if provisional and selected_ids:
        target = selected[selected_ids[0]]
        if CAPABILITY_ORDER.get(provisional.get("state"), 0) > CAPABILITY_ORDER.get(target.get("state"), 0):
            target["state"] = provisional["state"]
            target["evidence"] = deepcopy(provisional.get("evidence", []))
    rendered = old.get("rendered_user_path")
    if rendered and selected:
        ui_targets = [
            item for item in selected.values()
            if any(marker in (item.get("label") or "").casefold() for marker in ("browser", "ui", "interface", "app", "widget", "game"))
        ]
        target = ui_targets[0] if ui_targets else selected[selected_ids[0]]
        if CAPABILITY_ORDER.get(rendered.get("state"), 0) > CAPABILITY_ORDER.get(target.get("state"), 0):
            target["state"] = rendered["state"]
            target["evidence"] = deepcopy(rendered.get("evidence", []))
    supplied = old.get("supplied_implementation_integration")
    if supplied and selected_ids:
        selected[selected_ids[0]]["existing_implementation"] = supplied.get("existing_implementation")
    state["first_reality"] = first
    state["capabilities"] = capabilities
    return refresh_governor(seal(state))


def verify_event(raw: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(raw))
    if value.get("$schema") != EVENT_SCHEMA:
        raise MissionControlError("E_SCHEMA", "mission event schema is invalid")
    if value.get("kind") not in EVENT_KINDS:
        raise MissionControlError("E_EVENT", "mission event kind is invalid")
    text(value.get("event_id"), "event_id")
    parse_time(value.get("occurred_at"), "occurred_at")
    if value.get("work_class") is not None and value.get("work_class") not in WORK_CLASSES:
        raise MissionControlError("E_EVENT", "event work_class is invalid")
    observed = sha256(value.get("event_sha256"), "event_sha256")
    value["event_sha256"] = None
    if digest(value) != observed:
        raise MissionControlError("E_DIGEST", "mission event changed")
    value["event_sha256"] = observed
    return value


def record_event(raw_state: Mapping[str, Any], raw_event: Mapping[str, Any]) -> dict[str, Any]:
    state = verify_state(raw_state)
    event = verify_event(raw_event)
    if event["event_id"] in {item.get("event_id") for item in state["events"] if isinstance(item, Mapping)}:
        return state
    if state["status"] != "active" and event["kind"] not in {"checkpoint_recorded"}:
        raise MissionControlError("E_STATUS", "inactive mission cannot accept this event")
    if event.get("work_class"):
        units = finite(event.get("units", 1.0), "event.units")
        state["work_units"][event["work_class"]] = float(state["work_units"].get(event["work_class"], 0.0)) + units
    if event.get("tokens") is not None:
        tokens = finite(event.get("tokens"), "event.tokens")
        state["tokens_consumed"] = float(state.get("tokens_consumed", 0.0)) + tokens
    kind = event["kind"]
    if kind in {"artifact_materialized", "runtime_observed", "journey_connected", "independent_accepted"}:
        capability_id = text(event.get("capability_id"), "event.capability_id")
        evidence = _evidence_record(event.get("evidence", {}))
        target = {
            "artifact_materialized": "partial",
            "runtime_observed": "runnable",
            "journey_connected": "connected",
            "independent_accepted": "verified",
        }[kind]
        _set_capability_state(state, capability_id, target, evidence)
    if kind == "checkpoint_recorded":
        checkpoint = event.get("checkpoint")
        if not isinstance(checkpoint, Mapping):
            raise MissionControlError("E_CHECKPOINT", "checkpoint event is missing checkpoint")
        state["checkpoint"] = verify_checkpoint(checkpoint)
    if kind == "wake_consumed":
        if state["scheduler"].get("status") != "active":
            raise MissionControlError("E_SCHEDULER", "revoked scheduler cannot consume a wake")
        wake_key = text(event.get("wake_key"), "wake_key")
        if wake_key in state["consumed_wake_keys"]:
            raise MissionControlError("E_SCHEDULER", "wake was already consumed")
        if int(state["scheduler"].get("wake_count", 0)) >= int(state["scheduler"].get("max_wakes", 0)):
            raise MissionControlError("E_SCHEDULER", "mission wake limit is exhausted")
        state["consumed_wake_keys"].append(wake_key)
        state["scheduler"]["wake_count"] = len(state["consumed_wake_keys"])
    state["events"].append(event)
    state = reconcile_deadlines(seal(state), now=parse_time(event["occurred_at"], "occurred_at"))
    signals = reality_signals(state)
    if signals["independent_acceptance"]:
        state["status"] = "accepted"
        state["scheduler"] = {**state["scheduler"], "status": "revoked", "generation": int(state["generation"]) + 1}
        state["generation"] = int(state["generation"]) + 1
        state = seal(state)
    return refresh_governor(state, now=parse_time(event["occurred_at"], "occurred_at"))


def make_event(
    event_id: str,
    kind: str,
    *,
    occurred_at: str | None = None,
    work_class: str | None = None,
    units: float | None = None,
    tokens: float | None = None,
    capability_id: str | None = None,
    evidence: Mapping[str, Any] | None = None,
    observation_kind: str | None = None,
    wake_key: str | None = None,
    checkpoint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if kind not in EVENT_KINDS:
        raise MissionControlError("E_EVENT", f"unsupported event kind {kind}")
    value: dict[str, Any] = {
        "$schema": EVENT_SCHEMA,
        "event_id": text(event_id, "event_id"),
        "kind": kind,
        "occurred_at": occurred_at or format_time(now_utc()),
        "event_sha256": None,
    }
    if work_class is not None:
        if work_class not in WORK_CLASSES:
            raise MissionControlError("E_EVENT", "work_class is invalid")
        value["work_class"] = work_class
        value["units"] = 1.0 if units is None else finite(units, "units")
    if tokens is not None:
        value["tokens"] = finite(tokens, "tokens")
    if capability_id is not None:
        value["capability_id"] = text(capability_id, "capability_id")
    if evidence is not None:
        value["evidence"] = dict(evidence)
    if observation_kind is not None:
        value["observation_kind"] = text(observation_kind, "observation_kind")
    if wake_key is not None:
        value["wake_key"] = text(wake_key, "wake_key")
    if checkpoint is not None:
        value["checkpoint"] = dict(checkpoint)
    value["event_sha256"] = digest(value)
    return value


def _admission_digest(value: Mapping[str, Any]) -> str:
    result = deepcopy(dict(value))
    result["receipt_sha256"] = None
    return digest(result)


def admit_work(raw_state: Mapping[str, Any], raw_request: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    del now
    state = verify_state(raw_state)
    request = deepcopy(dict(raw_request))
    if request.get("$schema") != ADMISSION_SCHEMA:
        raise MissionControlError("E_SCHEMA", "work admission schema is invalid")
    request_id = text(request.get("request_id"), "request_id")
    work_class = request.get("work_class")
    if work_class not in WORK_CLASSES:
        raise MissionControlError("E_WORK", "work class is invalid")
    task_id = text(request.get("task_id"), "task_id")
    manager_id = text(request.get("manager_id"), "manager_id")
    if state["status"] != "active":
        allowed = False
        blockers = [f"mission status is {state['status']}"]
    else:
        decision = state.get("governor_decision") or {}
        allowed_classes = set(decision.get("allowed_work_classes", []))
        paused_classes = set(decision.get("paused_work_classes", []))
        allowed = work_class in allowed_classes and work_class not in paused_classes
        blockers = [] if allowed else [f"work class {work_class} is paused by governor mode {decision.get('mode')}"]
    justification = request.get("justification")
    navigation = state.get("navigation") or {}
    if work_class in navigation_module().SENSOR_CLASSES and request.get("bootstrap") is not True:
        route_action = navigation.get("next_action") if isinstance(navigation, Mapping) else {}
        active_verification = work_class == "evaluation" and isinstance(route_action, Mapping) and route_action.get("work_class") == "evaluation"
        if not active_verification:
            if not isinstance(justification, Mapping):
                allowed = False
                blockers.append("sensor work requires a consumer-bound value-of-information justification")
            else:
                for key in ("consumer_task_id", "blocker_id", "decision_dependency"):
                    try:
                        text(justification.get(key), f"justification.{key}")
                    except MissionControlError as exc:
                        allowed = False
                        blockers.append(exc.message)
                try:
                    deadline = integer(justification.get("deadline_minutes"), "justification.deadline_minutes", minimum=1)
                    if deadline > 45:
                        allowed = False
                        blockers.append("sensor work deadline exceeds 45 minutes")
                except MissionControlError as exc:
                    allowed = False
                    blockers.append(exc.message)
                if allowed:
                    useful, reason = navigation_module().sensor_request_is_useful(navigation, justification)
                    if not useful:
                        allowed = False
                        blockers.append(reason)
    if request.get("replaces_existing_implementation") is True:
        receipt = request.get("integration_spike_receipt")
        if not isinstance(receipt, Mapping):
            allowed = False
            blockers.append("replacement requires an integration spike receipt")
        else:
            required = {"implementation", "version", "commands", "runtime_evidence", "blocking_incompatibility", "extension_analysis", "replacement_cost", "receipt_sha256"}
            if set(receipt) != required:
                allowed = False
                blockers.append("integration spike receipt shape is invalid")
            else:
                candidate = dict(receipt)
                observed = candidate.pop("receipt_sha256", None)
                if not isinstance(observed, str) or digest(candidate) != observed:
                    allowed = False
                    blockers.append("integration spike receipt digest is invalid")
    decision = state.get("governor_decision") or {}
    receipt = {
        "$schema": ADMISSION_RECEIPT_SCHEMA,
        "request_id": request_id,
        "task_id": task_id,
        "manager_id": manager_id,
        "work_class": work_class,
        "admitted": allowed,
        "blockers": sorted(set(blockers)),
        "mission_state_sha256": state["state_sha256"],
        "governor_decision_sha256": decision.get("decision_sha256"),
        "governor_mode": decision.get("mode"),
        "dominant_bottleneck": decision.get("dominant_bottleneck"),
        "allowed_work_classes": decision.get("allowed_work_classes", []),
        "replacement_orders": state.get("replacement_orders", []),
        "navigation_decision_sha256": navigation.get("decision_sha256") if isinstance(navigation, Mapping) else None,
        "navigation_mode": navigation.get("mode") if isinstance(navigation, Mapping) else None,
        "next_action": navigation.get("next_action") if isinstance(navigation, Mapping) else None,
        "receipt_sha256": None,
    }
    receipt["receipt_sha256"] = _admission_digest(receipt)
    return receipt


def verify_admission(raw: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(raw))
    if value.get("$schema") != ADMISSION_RECEIPT_SCHEMA:
        raise MissionControlError("E_SCHEMA", "admission receipt schema is invalid")
    observed = sha256(value.get("receipt_sha256"), "receipt_sha256")
    value["receipt_sha256"] = None
    if digest(value) != observed:
        raise MissionControlError("E_DIGEST", "admission receipt changed")
    value["receipt_sha256"] = observed
    return value


def make_wake(
    raw_state: Mapping[str, Any],
    *,
    wake_id: str,
    not_before: str,
    reason: str,
    expected_state_sha256: str,
) -> dict[str, Any]:
    state = verify_state(raw_state)
    scheduler = verify_scheduler(state)
    if state["status"] != "active" or scheduler["status"] != "active":
        raise MissionControlError("E_SCHEDULER", "inactive scheduler cannot mint a wake")
    if int(scheduler["wake_count"]) >= int(scheduler["max_wakes"]):
        raise MissionControlError("E_SCHEDULER", "mission wake limit is exhausted")
    generation = integer(scheduler["generation"], "scheduler.generation", minimum=1)
    wake = {
        "$schema": WAKE_SCHEMA,
        "wake_id": text(wake_id, "wake_id"),
        "mission_id": scheduler["mission_id"],
        "generation": generation,
        "not_before": format_time(parse_time(not_before, "not_before")),
        "expires_at": scheduler["expires_at"],
        "reason": text(reason, "reason"),
        "expected_state_sha256": sha256(expected_state_sha256, "expected_state_sha256"),
        "idempotency_key": digest({"mission_id": scheduler["mission_id"], "generation": generation, "wake_id": wake_id}),
        "wake_sha256": None,
    }
    wake["wake_sha256"] = digest(wake)
    return wake


def admit_wake(raw_state: Mapping[str, Any], raw_wake: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    state = verify_state(raw_state)
    wake = deepcopy(dict(raw_wake))
    if wake.get("$schema") != WAKE_SCHEMA:
        raise MissionControlError("E_SCHEMA", "wake schema is invalid")
    observed = sha256(wake.get("wake_sha256"), "wake_sha256")
    wake["wake_sha256"] = None
    if digest(wake) != observed:
        raise MissionControlError("E_DIGEST", "wake changed")
    wake["wake_sha256"] = observed
    current = now or now_utc()
    scheduler = verify_scheduler(state)
    blockers = []
    if state["status"] != "active" or scheduler.get("status") != "active":
        blockers.append("mission scheduler is inactive")
    if wake.get("mission_id") != scheduler.get("mission_id") or wake.get("generation") != scheduler.get("generation"):
        blockers.append("wake mission or generation is stale")
    if current < parse_time(wake.get("not_before"), "not_before"):
        blockers.append("wake is early")
    if current >= parse_time(wake.get("expires_at"), "expires_at") or current >= parse_time(scheduler.get("expires_at"), "scheduler.expires_at"):
        blockers.append("wake is expired")
    if wake.get("expected_state_sha256") != state["state_sha256"]:
        blockers.append("wake expected state is stale")
    if wake.get("idempotency_key") in state["consumed_wake_keys"]:
        blockers.append("wake was already consumed")
    if int(scheduler.get("wake_count", 0)) >= int(scheduler.get("max_wakes", 0)):
        blockers.append("mission wake limit is exhausted")
    return {
        "admitted": not blockers,
        "blockers": blockers,
        "wake_id": wake.get("wake_id"),
        "idempotency_key": wake.get("idempotency_key"),
        "mission_state_sha256": state["state_sha256"],
    }


def create_checkpoint(
    raw_state: Mapping[str, Any],
    *,
    candidate_id: str,
    capability_ids: list[str],
    artifacts: list[Mapping[str, Any]],
    verification_receipts: list[Mapping[str, Any]],
    git_commit: str | None = None,
    quarantined_paths: list[str] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    state = verify_state(raw_state)
    if not artifacts:
        raise MissionControlError("E_CHECKPOINT", "checkpoint requires product artifacts")
    artifact_records = []
    for index, raw in enumerate(artifacts):
        artifact_records.append(
            {
                "path": safe_relative(raw.get("path"), f"artifacts[{index}].path"),
                "sha256": sha256(raw.get("sha256"), f"artifacts[{index}].sha256"),
            }
        )
    receipts = []
    for index, raw in enumerate(verification_receipts):
        receipts.append(
            {
                "path": safe_relative(raw.get("path"), f"verification_receipts[{index}].path"),
                "sha256": sha256(raw.get("sha256"), f"verification_receipts[{index}].sha256"),
            }
        )
    checkpoint = {
        "$schema": CHECKPOINT_SCHEMA,
        "mission_id": state["mission_id"],
        "objective_id": state["objective_id"],
        "candidate_id": text(candidate_id, "candidate_id"),
        "capability_ids": sorted({text(item, "capability_id") for item in capability_ids}),
        "artifacts": sorted(artifact_records, key=lambda item: item["path"]),
        "verification_receipts": sorted(receipts, key=lambda item: item["path"]),
        "git_commit": git_commit,
        "quarantined_paths": sorted({safe_relative(item, "quarantined_path") for item in (quarantined_paths or [])}),
        "created_at": created_at or format_time(now_utc()),
        "checkpoint_sha256": None,
    }
    checkpoint["checkpoint_sha256"] = digest(checkpoint)
    return checkpoint


def verify_checkpoint(raw: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(raw))
    if value.get("$schema") != CHECKPOINT_SCHEMA:
        raise MissionControlError("E_SCHEMA", "checkpoint schema is invalid")
    observed = sha256(value.get("checkpoint_sha256"), "checkpoint_sha256")
    value["checkpoint_sha256"] = None
    if digest(value) != observed:
        raise MissionControlError("E_DIGEST", "checkpoint changed")
    value["checkpoint_sha256"] = observed
    return value


def save(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MissionControlError("E_JSON", f"cannot read {path}") from exc
    if not isinstance(raw, Mapping):
        raise MissionControlError("E_JSON", "mission state must be an object")
    return verify_state(raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--objective-id", required=True)
    init.add_argument("--objective", required=True)
    init.add_argument("--mission-class", choices=sorted(MISSION_CLASSES))
    init.add_argument("--duration-minutes", type=int)
    init.add_argument("--token-budget", type=int)
    init.add_argument("--started-at")
    init.add_argument("--artifact-contract", type=Path)
    init.add_argument("--output", type=Path, required=True)

    scope = sub.add_parser("update-scope")
    scope.add_argument("--state", type=Path, required=True)
    scope.add_argument("--artifact-contract", type=Path, required=True)
    scope.add_argument("--output", type=Path, required=True)

    event = sub.add_parser("record-event")
    event.add_argument("--state", type=Path, required=True)
    event.add_argument("--event", type=Path, required=True)
    event.add_argument("--output", type=Path, required=True)

    admit = sub.add_parser("admit-work")
    admit.add_argument("--state", type=Path, required=True)
    admit.add_argument("--request", type=Path, required=True)
    admit.add_argument("--output", type=Path, required=True)

    wake_create = sub.add_parser("make-wake")
    wake_create.add_argument("--state", type=Path, required=True)
    wake_create.add_argument("--wake-id", required=True)
    wake_create.add_argument("--not-before", required=True)
    wake_create.add_argument("--reason", required=True)
    wake_create.add_argument("--output", type=Path, required=True)

    wake_admit = sub.add_parser("admit-wake")
    wake_admit.add_argument("--state", type=Path, required=True)
    wake_admit.add_argument("--wake", type=Path, required=True)
    wake_admit.add_argument("--output", type=Path, required=True)

    check = sub.add_parser("verify")
    check.add_argument("--state", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "init":
            artifact_contract = None
            if args.artifact_contract:
                artifact_contract = json.loads(args.artifact_contract.read_text(encoding="utf-8"))
            result = initialize_state(
                args.objective_id,
                args.objective,
                started_at=args.started_at,
                mission_class=args.mission_class,
                duration_minutes=args.duration_minutes,
                token_budget=args.token_budget,
                artifact_contract=artifact_contract,
            )
            save(args.output, result)
        elif args.command == "update-scope":
            result = update_scope(load(args.state), json.loads(args.artifact_contract.read_text(encoding="utf-8")))
            save(args.output, result)
        elif args.command == "record-event":
            result = record_event(load(args.state), json.loads(args.event.read_text(encoding="utf-8")))
            save(args.output, result)
        elif args.command == "admit-work":
            result = admit_work(load(args.state), json.loads(args.request.read_text(encoding="utf-8")))
            save(args.output, result)
        elif args.command == "make-wake":
            current = load(args.state)
            result = make_wake(
                current,
                wake_id=args.wake_id,
                not_before=args.not_before,
                reason=args.reason,
                expected_state_sha256=current["state_sha256"],
            )
            save(args.output, result)
        elif args.command == "admit-wake":
            result = admit_wake(load(args.state), json.loads(args.wake.read_text(encoding="utf-8")))
            save(args.output, result)
        else:
            result = load(args.state)
        print(
            json.dumps(
                {
                    "ok": True,
                    "mission_id": result.get("mission_id"),
                    "state_sha256": result.get("state_sha256"),
                    "receipt_sha256": result.get("receipt_sha256"),
                    "status": result.get("status"),
                },
                sort_keys=True,
            )
        )
        return 0
    except (MissionControlError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        code = exc.code if isinstance(exc, MissionControlError) else "E_RUNTIME"
        message = exc.message if isinstance(exc, MissionControlError) else str(exc)
        print(json.dumps({"ok": False, "code": code, "error": message}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
