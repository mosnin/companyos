#!/usr/bin/env python3
"""Small executable specification for critical Company OS router invariants.

This feature-off resolver is the executable v2 routing contract; production activation requires a compiled v2 catalog.
"""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations

from capability_index_contract_v2 import dnf_matches, deterministic_context_units


NETWORK = {"none": 0, "allowlisted_read": 1, "allowlisted_write": 2}
EGRESS = {"none": 0, "metadata_only": 1, "content": 2}
SENSITIVITY = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
class RouteError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _closed_bundle(seed: set[str], indexed: dict[str, dict]) -> set[str]:
    closed = set(seed)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(capability_id: str) -> None:
        if capability_id in visiting:
            raise RouteError("E_DEPENDENCY_CYCLE")
        if capability_id in visited:
            return
        row = indexed.get(capability_id)
        if row is None:
            raise RouteError("E_REQUIRED_DEPENDENCY")
        visiting.add(capability_id)
        for dependency in row["requires"]:
            closed.add(dependency)
            visit(dependency)
        visiting.remove(capability_id)
        visited.add(capability_id)

    for capability_id in sorted(seed):
        visit(capability_id)
    return closed


def _age_days(decision_as_of: str, observed_at: str) -> int:
    decision = datetime.fromisoformat(decision_as_of.replace("Z", "+00:00")).astimezone(timezone.utc)
    observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00")).astimezone(timezone.utc)
    if observed > decision:
        raise RouteError("E_FRESHNESS_FUTURE")
    return (decision - observed).days


def eligibility_errors(task: dict, row: dict) -> list[str]:
    errors: list[str] = []
    if task["role"] not in row["roles"]:
        errors.append("E_ROLE")
    if row["positive_trigger_dnf"] and not dnf_matches(task["typed_features"], row["positive_trigger_dnf"]):
        errors.append("E_TRIGGER_FALSE")
    if any(dnf_matches(task["typed_features"], [[predicate]]) for predicate in row["negative_triggers"]):
        errors.append("E_NEGATIVE_TRIGGER")
    if row["trust"] != "approved":
        errors.append("E_TRUST")
    if not row["license_ok"]:
        errors.append("E_LICENSE")
    if not row["materialization_digest_ok"]:
        errors.append("E_MATERIALIZATION_DRIFT")
    if not row["materialization_closure_ok"]:
        errors.append("E_MATERIALIZATION_CLOSURE")
    if row["hidden_controller_effect"]:
        errors.append("E_HIDDEN_CONTROLLER_EFFECT")
    if not row["resource_license_ok"]:
        errors.append("E_LICENSE_RESOURCE_CONFLICT")
    if not row["evaluation_receipt_ok"]:
        errors.append("E_EVALUATION_RECEIPT")
    if not row["evaluation_fresh"]:
        errors.append("E_EVALUATION_FRESHNESS")
    if not row["source_redirect_ok"]:
        errors.append("E_SOURCE_REDIRECT_DRIFT")
    if row["controller_effect"] != "none":
        errors.append("E_CONTROLLER_CONFLICT")
    try:
        freshness_age_days = _age_days(task["decision_as_of"], row["last_revalidated_at"])
        if freshness_age_days > task["max_freshness_days"]:
            errors.append("E_FRESHNESS")
    except RouteError as error:
        errors.append(error.code)
    if row["evaluation_class"] < task["min_evaluation_class"]:
        errors.append("E_EVALUATION_INSUFFICIENT")
    if not set(row["prerequisites"]) <= set(task["available_prerequisites"]):
        errors.append("E_PREREQUISITE")
    if not set(row["permissions"]) <= set(task["permissions"]):
        errors.append("E_PERMISSION_WIDENING")
    if NETWORK[row["network_mode"]] > NETWORK[task["network_mode"]]:
        errors.append("E_PREREQUISITE_NETWORK")
    if not set(row["allowed_hosts"]) <= set(task["allowed_hosts"]):
        errors.append("E_HOST_ALLOWLIST")
    if EGRESS[row["data_egress"]] > EGRESS[task["data_egress"]]:
        errors.append("E_DATA_EGRESS")
    if SENSITIVITY[row["sensitivity"]] > SENSITIVITY[task["sensitivity_ceiling"]]:
        errors.append("E_DATA_SENSITIVITY")
    if not set(row["side_effects"]) <= set(task["allowed_side_effects"]):
        errors.append("E_SIDE_EFFECT_WIDENING")
    return errors


def route(task: dict, rows: list[dict]) -> dict:
    if task["decision_as_of"] is None:
        raise RouteError("E_DECISION_AS_OF")
    atoms = set(task["atoms"])
    if not atoms:
        return {"selected": [], "ties": [], "decision_required": False}
    indexed = {row["id"]: row for row in rows}
    if len(indexed) != len(rows):
        raise RouteError("E_SCHEMA_DUPLICATE_ID")

    # Exhaustive metadata retrieval: no top-N cap before eligibility.
    seed_candidates = [row for row in rows if set(row["coverage"]) & atoms]
    if not seed_candidates:
        raise RouteError("E_REQUIRED_CAPABILITY_UNAVAILABLE")

    # Eligibility is evaluated for seed candidates and every transitive helper.
    dependency_ids: set[str] = set()
    for candidate in seed_candidates:
        try:
            dependency_ids |= _closed_bundle({candidate["id"]}, indexed)
        except RouteError:
            dependency_ids.add(candidate["id"])
    eligible = {
        capability_id: indexed[capability_id]
        for capability_id in sorted(dependency_ids)
        if capability_id in indexed and not eligibility_errors(task, indexed[capability_id])
    }
    if not any(candidate["id"] in eligible for candidate in seed_candidates):
        raise RouteError("E_REQUIRED_CAPABILITY_UNAVAILABLE")

    bundles: list[tuple[tuple, tuple[str, ...]]] = []
    eligible_seed_ids = sorted(candidate["id"] for candidate in seed_candidates if candidate["id"] in eligible)
    bundle_errors: set[str] = set()
    for size in range(1, task["max_skills"] + 1):
        for seed_tuple in combinations(eligible_seed_ids, size):
            try:
                closed_ids = _closed_bundle(set(seed_tuple), indexed)
            except RouteError as error:
                if error.code == "E_DEPENDENCY_CYCLE":
                    bundle_errors.add(error.code)
                    continue
                raise
            if len(closed_ids) > task["max_skills"] or not closed_ids <= set(eligible):
                continue
            closed = [indexed[item] for item in sorted(closed_ids)]
            if any(set(row["conflicts"]) & closed_ids for row in closed):
                continue
            coverage = set().union(*(set(row["coverage"]) for row in closed))
            if not atoms <= coverage:
                continue
            total_bytes = sum(row["closed_bytes"] for row in closed)
            total_context_units = sum(
                deterministic_context_units(row["closed_bytes"], task["context_accounting_id"])
                for row in closed
            )
            if total_bytes > task["max_bytes"]:
                bundle_errors.add("E_CONTEXT_BYTES")
                continue
            if total_context_units > task["max_context_cost_units"]:
                bundle_errors.add("E_CONTEXT_COST_UNITS")
                continue
            key = (
                len(closed_ids),
                total_bytes,
                total_context_units,
                -min(row["provenance"] for row in closed),
                -min(row["evaluation_class"] for row in closed),
                -min(task["max_freshness_days"] - _age_days(task["decision_as_of"], row["last_revalidated_at"]) for row in closed),
                sum(len(row["prerequisites"]) for row in closed),
                -sum(row["specificity"] for row in closed),
            )
            bundles.append((key, tuple(sorted(closed_ids))))
    if not bundles:
        for code in ("E_DEPENDENCY_CYCLE", "E_CONTEXT_BYTES", "E_CONTEXT_COST_UNITS"):
            if code in bundle_errors:
                raise RouteError(code)
        raise RouteError("E_NO_VALID_BUNDLE")
    best_key = min(item[0] for item in bundles)
    ties = sorted({ids for key, ids in bundles if key == best_key})
    if len(ties) > 1 or task["risk"] in {"high", "critical"}:
        return {"selected": [], "ties": [list(item) for item in ties], "decision_required": True}
    return {"selected": list(ties[0]), "ties": [], "decision_required": False}


def row(capability_id: str, coverage: list[str], **overrides) -> dict:
    value = {
        "id": capability_id,
        "coverage": coverage,
        "roles": ["worker"],
        "positive_trigger_dnf": [[{"field": "intents", "op": "contains", "value": "report"}]],
        "negative_triggers": [],
        "trust": "approved",
        "license_ok": True,
        "materialization_digest_ok": True,
        "materialization_closure_ok": True,
        "hidden_controller_effect": False,
        "resource_license_ok": True,
        "evaluation_receipt_ok": True,
        "evaluation_fresh": True,
        "source_redirect_ok": True,
        "controller_effect": "none",
        "last_revalidated_at": "2026-08-04T00:00:00Z",
        "evaluation_class": 3,
        "prerequisites": [],
        "requires": [],
        "permissions": [],
        "network_mode": "none",
        "allowed_hosts": [],
        "data_egress": "none",
        "sensitivity": "public",
        "side_effects": ["advisory"],
        "conflicts": [],
        "closed_bytes": 100,
        "provenance": 3,
        "specificity": 8,
    }
    value.update(overrides)
    return value


def task(**overrides) -> dict:
    value = {
        "decision_as_of": "2026-08-05T00:00:00Z",
        "atoms": ["artifact:produce:report"],
        "typed_features": {"intents": ["report"], "role": "worker"},
        "role": "worker",
        "available_prerequisites": [],
        "permissions": [],
        "network_mode": "none",
        "allowed_hosts": [],
        "data_egress": "none",
        "sensitivity_ceiling": "public",
        "allowed_side_effects": ["advisory"],
        "max_freshness_days": 90,
        "min_evaluation_class": 2,
        "max_skills": 4,
        "max_bytes": 49152,
        "max_context_cost_units": 12000,
        "context_accounting_id": "company-os-utf8-byteceil4-v1",
        "risk": "low",
    }
    value.update(overrides)
    return value
