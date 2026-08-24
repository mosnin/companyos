#!/usr/bin/env python3
"""Validate a scientific-method overlay packet.

The packet is a checklist bound to existing Company OS records. It is not
governed state and cannot own iteration, leases, fabric, or completion.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "company-os.scientific-method-packet.v1"
REQUEST_SCHEMA = "company-os.outcome-request.v1"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
EXPERIMENT_CLASSES = ("outcome", "innovation_bet", "process_adaptation")
STATUSES = ("hypothesis", "supported", "refuted")
AUTHORITY = "overlay"
BINDING_KIND = {
    "outcome": "outcome_request",
    "innovation_bet": "innovation_bet",
    "process_adaptation": "adaptation",
}
TEST_KIND = {
    "outcome": "evaluator",
    "innovation_bet": "kill_rule",
    "process_adaptation": "adaptation_review",
}
PRIMARY_LOOPS = {
    "bounded-evidence-loop",
    "contract-delivery-loop",
    "recursive-worktree-loop",
    "bounded-divergent-exploration-loop",
    "recurring-operations-loop",
    "event-reaction-loop",
}
NEXT_ACTIONS = {
    "close_outcome_discovery",
    "evidence_research_campaign",
    "select_execution_loop",
    "execute_outcome_evaluator",
    "accept_outcome_reality",
    "run_outcome_loop",
    "propose_adaptation",
    "review_adaptation",
    "hold_bet",
    "kill_bet",
    "scale_bet",
    "rework",
}
FORBIDDEN_NEXT = {
    "launch_runtime",
    "enable_scheduler",
    "complete_from_narrative",
    "run_scientific_method",
}
EVIDENCE_KINDS = {
    "citation",
    "evaluator_receipt",
    "reality_receipt",
    "adaptation_decision",
    "bet_decision",
}
TOP_LEVEL = {
    "schema",
    "packet_id",
    "experiment_class",
    "hypothesis_id",
    "hypothesis",
    "status",
    "disconfirm_condition",
    "binding",
    "cap",
    "test",
    "loop",
    "next_action",
    "authority",
    "evidence",
}
BINDING_KEYS = {"kind", "record_id", "record_sha256", "field_id"}
CAP_KEYS = {"max_time_minutes", "max_cost_usd", "max_variants"}
TEST_KEYS = {"kind", "rule"}
LOOP_KEYS = {"primary", "activation_state"}
EVIDENCE_KEYS = {"kind", "ref"}


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


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
    hypothesis_id = payload.get("hypothesis_id")
    if not isinstance(hypothesis_id, str) or not ID_RE.fullmatch(hypothesis_id):
        errors.append("hypothesis_id is invalid")
    if not _text(payload.get("hypothesis")):
        errors.append("hypothesis must be a non-empty string")
    if not _text(payload.get("disconfirm_condition")):
        errors.append("disconfirm_condition must be a non-empty string")

    experiment_class = payload.get("experiment_class")
    if experiment_class not in EXPERIMENT_CLASSES:
        errors.append("experiment_class is invalid")
    status = payload.get("status")
    if status not in STATUSES:
        errors.append("status is invalid")
    next_action = payload.get("next_action")
    if next_action in FORBIDDEN_NEXT:
        errors.append("next_action cannot launch runtime, schedule, narrate completion, or orchestrate")
    elif next_action not in NEXT_ACTIONS:
        errors.append("next_action is not a governed Company OS action")

    errors.extend(_validate_binding(payload.get("binding"), experiment_class, hypothesis_id))
    errors.extend(_validate_cap(payload.get("cap")))
    errors.extend(_validate_test(payload.get("test"), experiment_class))
    errors.extend(_validate_loop(payload.get("loop"), payload.get("cap")))
    errors.extend(_validate_evidence(payload.get("evidence"), status, experiment_class))
    return errors


def _validate_binding(binding: Any, experiment_class: Any, hypothesis_id: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(binding, dict):
        return ["binding must be an object"]
    if set(binding) != BINDING_KEYS:
        errors.append("binding keys drifted")
    expected_kind = BINDING_KIND.get(experiment_class)
    if expected_kind is not None and binding.get("kind") != expected_kind:
        errors.append("binding.kind does not match experiment_class")
    if not isinstance(binding.get("record_id"), str) or not ID_RE.fullmatch(binding.get("record_id", "")):
        errors.append("binding.record_id is invalid")
    field_id = binding.get("field_id")
    if not isinstance(field_id, str) or not ID_RE.fullmatch(field_id):
        errors.append("binding.field_id is invalid")
    elif isinstance(hypothesis_id, str) and field_id != hypothesis_id:
        errors.append("hypothesis_id must equal binding.field_id")
    digest = binding.get("record_sha256")
    if digest is not None and not (isinstance(digest, str) and SHA_RE.fullmatch(digest)):
        errors.append("binding.record_sha256 must be sha256 or null")
    return errors


def _validate_cap(cap: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(cap, dict):
        return ["cap must be an object"]
    if set(cap) != CAP_KEYS:
        errors.append("cap keys drifted")
    minutes = cap.get("max_time_minutes")
    if not _is_int(minutes) or minutes <= 0:
        errors.append("cap.max_time_minutes must be a positive integer")
    cost = cap.get("max_cost_usd")
    if cost is not None and (not _is_number(cost) or cost < 0):
        errors.append("cap.max_cost_usd must be a finite non-negative number or null")
    variants = cap.get("max_variants")
    if not _is_int(variants) or variants < 1 or variants > 6:
        errors.append("cap.max_variants must be an integer from 1 through 6")
    return errors


def _validate_test(test: Any, experiment_class: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(test, dict):
        return ["test must be an object"]
    if set(test) != TEST_KEYS:
        errors.append("test keys drifted")
    expected = TEST_KIND.get(experiment_class)
    if expected is not None and test.get("kind") != expected:
        errors.append("test.kind does not match experiment_class")
    if not _text(test.get("rule")):
        errors.append("test.rule must be a non-empty string")
    return errors


def _validate_loop(loop: Any, cap: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(loop, dict):
        return ["loop must be an object"]
    if set(loop) != LOOP_KEYS:
        errors.append("loop keys drifted")
    if loop.get("activation_state") != "planned":
        errors.append("loop.activation_state must be planned")
    primary = loop.get("primary")
    if primary is not None and primary not in PRIMARY_LOOPS:
        errors.append("loop.primary is not an existing Company OS primary loop")
    variants = cap.get("max_variants") if isinstance(cap, dict) else None
    if _is_int(variants) and variants > 1 and primary != "bounded-divergent-exploration-loop":
        errors.append("parallel variants require bounded-divergent-exploration-loop")
    return errors


def _validate_evidence(evidence: Any, status: Any, experiment_class: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(evidence, list):
        return ["evidence must be an array"]
    kinds: set[str] = set()
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(evidence):
        label = f"evidence[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        if set(item) != EVIDENCE_KEYS:
            errors.append(f"{label} keys drifted")
        kind = item.get("kind")
        ref = item.get("ref")
        if kind not in EVIDENCE_KINDS:
            errors.append(f"{label}.kind is invalid")
        if not _text(ref):
            errors.append(f"{label}.ref must be a non-empty string")
            continue
        key = (str(kind), str(ref))
        if key in seen:
            errors.append(f"{label} is duplicated")
        seen.add(key)
        if kind in EVIDENCE_KINDS:
            kinds.add(kind)
    if status == "hypothesis" and evidence:
        errors.append("hypothesis status cannot carry acceptance evidence")
    if status in {"supported", "refuted"} and not evidence:
        errors.append(f"{status} requires preserved evidence")
    if status == "supported" and experiment_class == "outcome":
        if "evaluator_receipt" not in kinds and "reality_receipt" not in kinds:
            errors.append("supported outcome requires an evaluator or reality receipt")
    if status == "supported" and experiment_class == "process_adaptation":
        if "adaptation_decision" not in kinds:
            errors.append("supported adaptation requires an independent review decision")
    if status == "supported" and experiment_class == "innovation_bet":
        if "bet_decision" not in kinds:
            errors.append("supported innovation bet requires a portfolio decision")
    return errors


def validate_against_request(packet: Any, request: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(request, dict):
        return ["outcome request must be an object"]
    if request.get("$schema") != REQUEST_SCHEMA:
        errors.append(f"request $schema must be {REQUEST_SCHEMA}")
    if not isinstance(packet, dict):
        return errors + ["packet must be an object"]
    if packet.get("experiment_class") != "outcome":
        errors.append("request binding requires experiment_class outcome")
    binding = packet.get("binding") if isinstance(packet.get("binding"), dict) else {}
    if binding.get("record_id") != request.get("objective_id"):
        errors.append("binding.record_id must equal request.objective_id")
    hypotheses = request.get("domain_hypotheses")
    if not isinstance(hypotheses, list):
        errors.append("request.domain_hypotheses must be an array")
        return errors
    field_id = binding.get("field_id")
    match = next(
        (
            item
            for item in hypotheses
            if isinstance(item, dict) and item.get("domain_id") == field_id
        ),
        None,
    )
    if match is None:
        errors.append("binding.field_id is not a request domain_id")
        return errors
    if packet.get("hypothesis") != match.get("hypothesis"):
        errors.append("packet hypothesis must match the bound domain hypothesis")
    request_status = match.get("status")
    packet_status = packet.get("status")
    if request_status == "refuted" and packet_status == "supported":
        errors.append("a refuted request hypothesis cannot be marked supported")
    return errors


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable JSON: {path}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--request", type=Path)
    args = parser.parse_args()
    try:
        packet = _load_json(args.packet)
        errors = validate_packet(packet)
        if args.request is not None:
            errors.extend(validate_against_request(packet, _load_json(args.request)))
    except ValueError as exc:
        errors = [str(exc)]
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
