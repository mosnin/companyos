#!/usr/bin/env python3
"""Validate a RIOCL TC overlay packet.

The packet is a checklist bound to existing Company OS records. It is not
governed state and cannot own iteration, leases, fabric, or completion.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "company-os.riocl-tc-packet.v1"
AUTHORITY = "overlay"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
BOUNDARIES = ("interaction", "subsystem", "system")
FLOWS = ("people", "information", "work", "cash", "attention", "energy")
REGIMES = (
    "exploration",
    "exploitation",
    "crisis",
    "scarcity",
    "abundance",
    "early",
    "mature",
    "optimization",
    "power_building",
)
STAKES = ("low", "medium", "high")
REVERSIBILITY = ("reversible", "semi_reversible", "irreversible")
HORIZONS = ("minutes", "hours", "days", "months", "years")
PHASES = (None, "pre_threshold", "post_threshold")
DECISION_MODES = ("do_nothing", "test", "execute_leverage", "redesign")
BINDING_KINDS = (
    "outcome_request",
    "governor_decision",
    "manager_charter",
    "adaptation",
)
MODE_ACTIONS = {
    "do_nothing": {"observe"},
    "test": {
        "close_outcome_discovery",
        "evidence_research_campaign",
        "select_execution_loop",
        "execute_outcome_evaluator",
    },
    "execute_leverage": {
        "force_first_execution",
        "run_outcome_loop",
        "rework",
        "direct_outcome",
    },
    "redesign": {
        "compile_outcome_organization",
        "propose_adaptation",
        "review_adaptation",
    },
}
NEXT_ACTIONS = set().union(*MODE_ACTIONS.values())
FORBIDDEN_NEXT = {
    "launch_runtime",
    "enable_scheduler",
    "complete_from_narrative",
    "run_riocl_tc",
    "run_scientific_method",
}
TEST_ONLY_REGIMES = {"exploration"}
TOP_LEVEL = {
    "schema",
    "packet_id",
    "authority",
    "binding",
    "boundary",
    "flow",
    "regime",
    "stakes",
    "reversibility",
    "outcome",
    "constraints",
    "bottleneck",
    "leverage_candidates",
    "time_horizon",
    "incentives",
    "reversion_risk",
    "survivable",
    "decision_mode",
    "phase",
    "next_action",
}
BINDING_KEYS = {"kind", "record_id", "record_sha256"}


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _string_list(value: Any, *, minimum: int, maximum: int, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return [f"{label} must be an array"]
    if not (minimum <= len(value) <= maximum):
        errors.append(f"{label} must contain {minimum} to {maximum} items")
    seen: set[str] = set()
    for index, item in enumerate(value):
        text = _text(item)
        if text is None:
            errors.append(f"{label}[{index}] must be a non-empty string")
            continue
        if text in seen:
            errors.append(f"{label}[{index}] is duplicated")
        seen.add(text)
    return errors


def validate_packet(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["packet must be an object"]
    extra = sorted(set(payload) - TOP_LEVEL)
    missing = sorted(TOP_LEVEL - set(payload))
    if extra:
        errors.append(f"unknown keys: {', '.join(extra)}")
    if missing:
        errors.append(f"missing keys: {', '.join(missing)}")
    if payload.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if payload.get("authority") != AUTHORITY:
        errors.append("authority must be overlay")

    packet_id = payload.get("packet_id")
    if not isinstance(packet_id, str) or not ID_RE.fullmatch(packet_id):
        errors.append("packet_id is invalid")
    if payload.get("boundary") not in BOUNDARIES:
        errors.append("boundary is invalid")
    if payload.get("flow") not in FLOWS:
        errors.append("flow is invalid")
    if payload.get("regime") not in REGIMES:
        errors.append("regime is invalid")
    if payload.get("stakes") not in STAKES:
        errors.append("stakes is invalid")
    if payload.get("reversibility") not in REVERSIBILITY:
        errors.append("reversibility is invalid")
    if payload.get("time_horizon") not in HORIZONS:
        errors.append("time_horizon is invalid")
    if payload.get("phase") not in PHASES:
        errors.append("phase is invalid")
    if not _text(payload.get("outcome")):
        errors.append("outcome must be a non-empty string")
    if not _text(payload.get("bottleneck")):
        errors.append("bottleneck must be a non-empty string")
    if not _text(payload.get("incentives")):
        errors.append("incentives must be a non-empty string")
    if not isinstance(payload.get("reversion_risk"), bool):
        errors.append("reversion_risk must be a boolean")
    if not isinstance(payload.get("survivable"), bool):
        errors.append("survivable must be a boolean")

    decision_mode = payload.get("decision_mode")
    if decision_mode not in DECISION_MODES:
        errors.append("decision_mode is invalid")
    next_action = payload.get("next_action")
    if next_action in FORBIDDEN_NEXT:
        errors.append("next_action cannot launch runtime, schedule, narrate completion, or orchestrate")
    elif next_action not in NEXT_ACTIONS:
        errors.append("next_action is not a governed Company OS action")
    elif decision_mode in MODE_ACTIONS and next_action not in MODE_ACTIONS[decision_mode]:
        errors.append("next_action does not match decision_mode")

    errors.extend(_validate_binding(payload.get("binding")))
    errors.extend(_string_list(payload.get("constraints"), minimum=1, maximum=2, label="constraints"))
    leverage_minimum = 1 if decision_mode in {"execute_leverage", "redesign"} else 0
    errors.extend(
        _string_list(
            payload.get("leverage_candidates"),
            minimum=leverage_minimum,
            maximum=3,
            label="leverage_candidates",
        )
    )
    errors.extend(_validate_gates(payload))
    return errors


def _validate_binding(binding: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(binding, dict):
        return ["binding must be an object"]
    if set(binding) != BINDING_KEYS:
        errors.append("binding keys drifted")
    if binding.get("kind") not in BINDING_KINDS:
        errors.append("binding.kind is invalid")
    if not isinstance(binding.get("record_id"), str) or not ID_RE.fullmatch(binding.get("record_id", "")):
        errors.append("binding.record_id is invalid")
    digest = binding.get("record_sha256")
    if digest is not None and not (isinstance(digest, str) and SHA_RE.fullmatch(digest)):
        errors.append("binding.record_sha256 must be sha256 or null")
    return errors


def _validate_gates(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    decision_mode = payload.get("decision_mode")
    if decision_mode not in {"execute_leverage", "redesign"}:
        return errors
    if payload.get("survivable") is False:
        errors.append("non-survivable downside forbids leverage and redesign")
    if payload.get("reversibility") == "irreversible":
        errors.append("irreversible context forbids leverage and redesign")
    if payload.get("regime") in TEST_ONLY_REGIMES:
        errors.append("exploration regime forbids leverage and redesign")
    if payload.get("stakes") == "high" and payload.get("reversibility") != "reversible":
        errors.append("high-stakes irreversible or semi-reversible moves must stay a test")
    return errors


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable JSON: {path}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    args = parser.parse_args()
    try:
        errors = validate_packet(_load_json(args.packet))
    except ValueError as exc:
        errors = [str(exc)]
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
