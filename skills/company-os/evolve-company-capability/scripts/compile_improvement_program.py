#!/usr/bin/env python3
"""Compile a deterministic, feature-off Company OS improvement program v2.

The caller supplies only bounded intent and identifiers.  All authority,
source, capability, evaluator, partition, telemetry, and execution truth is
resolved here from pinned checked-in registries; no provider or runtime is
imported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
SOURCE_REGISTRY_PATH = REPO_ROOT / "skills/company-os/source-intelligence/references/source-intelligence-registry.json"
MECHANISM_REGISTRY_PATH = REPO_ROOT / "skills/company-os/source-intelligence/references/mechanism-plane-registry.json"
CAPABILITY_CATALOG_PATH = REPO_ROOT / "skills/company-os/assign-capability-skills/references/capability-catalog.json"
CAPABILITY_REVIEW_PATH = REPO_ROOT / "skills/company-os/assign-capability-skills/references/capability-review-registry.json"
EVALUATOR_REGISTRY_PATH = REPO_ROOT / "skills/company-os/evaluate-company-evidence/references/evaluator-evidence-registry.json"

SOURCE_REGISTRY_SHA256 = "2668c17579e97d4afa2ca7bbc3e36e320b98164f68bdfbcda57ea7599097faae"
MECHANISM_REGISTRY_SHA256 = "4b4ec45b35bba85013d5bdc7a5d16e72ccd08465da8b7a7738bd49f6d4202e73"
CAPABILITY_CATALOG_SHA256 = "46e31b2f4ffdf2362e2c70a8bc254b72a01d5b5b1d37a138e634cf33096ca271"
CAPABILITY_REVIEW_SHA256 = "022d12afad5148b1e847612b112cbf50b35147aba10e64e3ac18e47ffd1d25f6"
EVALUATOR_REGISTRY_SHA256 = "57174252aca7e992d612d1b5ad7f81d2c2b05093c27c59c355cad385819df405"

SCHEMA = "company-os.improvement-request.v2"
PROGRAM_SCHEMA = "company-os.improvement-program.v2"
ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

REQUEST_KEYS = {"schema", "program", "intent", "baseline", "target", "source_ids", "capability_ids", "evaluation", "budgets"}
PROGRAM_KEYS = {"tenant_id", "project_id", "program_id", "cycle_id", "definition_version", "policy_version"}
INTENT_KEYS = {"objective", "hypothesis", "success_criteria", "falsification_criteria", "evidence_ids"}
BASELINE_KEYS = {"artifact_id", "version"}
TARGET_KEYS = {"kind", "opportunity_type", "reason", "protected_surfaces", "reversible_scope"}
EVALUATION_KEYS = {"artifact_classes", "stages"}
BUDGET_KEYS = {
    "max_candidates", "max_passes", "max_concurrency", "max_time_minutes",
    "max_tokens", "max_cost_usd", "max_context_bytes", "max_retries",
    "dead_letter_after", "cancel_grace_seconds",
}

TARGET_KINDS = {
    "prompt", "context", "skill", "tool_policy", "routing", "workflow", "code",
    "evaluator", "architecture", "memory", "organization", "research_method",
}
STAGES = {"discovery", "adaptive_validation", "deterministic_floor", "semantic_review", "sealed_challenge", "transfer"}
PARTITION_ORDER = ("discovery", "adaptive_validation", "sealed_challenge", "production_shadow")
PARTITION_EXPOSURE = {
    "discovery": "visible",
    "adaptive_validation": "feedback",
    "sealed_challenge": "hidden",
    "production_shadow": "controlled",
}
PROFILES = {
    "conservative": {
        "rank": 1,
        "strategy": "preserve_baseline_with_smallest_reversible_delta",
        "intervention": "Apply the smallest typed, reversible change that addresses the bounded hypothesis while preserving protected control surfaces.",
        "controls": ["baseline_compatibility", "narrow_scope", "rollback_first"],
    },
    "adjacent": {
        "rank": 2,
        "strategy": "compose_one_adjacent_local_capability",
        "intervention": "Compose one adjacent task-local mechanism with the baseline and compare it against the conservative candidate under the same held-out protocol.",
        "controls": ["capability_boundary", "compatibility_check", "held_out_transfer"],
    },
    "first_principles": {
        "rank": 3,
        "strategy": "rederive_contract_without_inheriting_baseline_assumptions",
        "intervention": "Re-derive the bounded contract from first principles, retaining only the explicit objective and protected surfaces and no inherited authority.",
        "controls": ["independent_lineage", "counterexample_review", "reversible_trial"],
    },
}
TERMINAL_STATES = ["rejected", "invalid_evidence", "inconclusive", "cancelled", "superseded", "revoked", "rolled_back", "dead_letter"]
ORDERED_STATES = [
    "observed", "reproduced", "proposed", "compiled", "sandbox_admitted", "validation_qualified",
    "challenge_qualified", "manager_accepted", "shadowed", "promoted", "monitored",
]

PROGRAM_OUTPUT_KEYS = {
    "schema", "activation_state", "executable", "execution_status", "blockers", "request_sha256",
    "registry_bindings", "program", "intent", "baseline", "target", "source_resolution",
    "capability_resolution", "evaluation", "candidates", "cohort_digest", "organization",
    "decision_receipt_requirements", "budgets", "lifecycle", "authority", "promotion", "telemetry",
    "side_effects", "warnings",
}
BLOCKER_KEYS = {"code", "reason", "evidence"}
REGISTRY_BINDING_KEYS = {"source_intelligence", "mechanism_plane", "capability_catalog", "capability_review", "evaluator_methods"}
SOURCE_RESOLUTION_KEYS = {"requested_source_ids", "resolved_record_count", "records", "mechanism_group_counts"}
SOURCE_RECORD_KEYS = {
    "source_id", "normalized_family_id", "pin", "license_state", "disposition", "review_decision",
    "review_evidence_sha256", "mechanism_group_id", "destination_plane", "adopt", "reject",
}
CAPABILITY_RESOLUTION_KEYS = {"requested_capability_ids", "resolved_candidate_count", "accepted_count", "portable_resolver", "records"}
CAPABILITY_RECORD_KEYS = {
    "capability_id", "source_id", "source_intelligence_id", "source_review_sha256", "review_id",
    "review_record_sha256", "upstream_entrypoint_sha256", "wrapper_entrypoint_sha256",
    "checkout_manifest_sha256", "source_checkout_commit", "source_checkout_tree", "review_decision",
    "efficacy_state", "phase", "effect_class", "provider_boundary", "required_permissions",
    "exclusive_family", "license_conclusion", "portable_acceptance_state", "production_dispatchable",
}
PORTABLE_RESOLVER_KEYS = {"resolver_id", "registry_sha256", "accepted_receipt_required", "portable_bundle_allowed", "selected_acceptance_receipt", "production_dispatchable"}
EVALUATION_OUTPUT_KEYS = {
    "artifact_classes", "requested_stages", "methods", "ready_adapter_count", "partitions",
    "exposure_burn_ledger", "failure_semantics", "evaluator_epoch_policy",
}
PARTITION_KEYS = {"kind", "membership_state", "exposure_state", "burned", "reused_after_feedback", "members"}
MEMBER_KEYS = {"candidate_profile", "partition", "ordinal", "seed", "member_id", "member_digest"}
LEDGER_KEYS = {"partition", "membership_state", "exposure_state", "burned", "reused_after_feedback", "member_ids", "event"}
CANDIDATE_KEYS = {
    "profile", "profile_rank", "strategy", "intervention", "controls", "parent_digest", "common_ancestor_digest",
    "environment_digest", "tool_policy_digest", "owned_resources", "semantic_contract_touches",
    "expected_artifact_classes", "capability_ids", "roles", "candidate_digest",
}
ROLE_KEYS = {"proposer", "candidate_owner", "evaluator", "confirmer", "accepter", "promoter"}
ORGANIZATION_KEYS = {"nodes", "topological_order", "ownership_policy"}
NODE_KEYS = {"id", "depends_on", "owned_resources"}
RECEIPT_REQUIREMENT_KEYS = {"candidate_profile", "decision_type", "role", "status", "requirements", "independent_of"}
AUTHORITY_KEYS = {"control_plane_id", "scheduler_id", "evaluator_registry_id", "promotion_registry_id", "promotion_authority_id", "external_effects_allowed"}
PROMOTION_KEYS = {"registry_id", "current_pointer_digest", "rollback_pointer_digest", "atomicity_required", "authority_id", "delayed_outcome_required", "delayed_outcome_window_days"}
TELEMETRY_KEYS = {"requested", "observed", "observed_evidence_ref"}
TELEMETRY_REQUEST_KEYS = {"model", "effort"}
LIFECYCLE_KEYS = {"ordered_states", "terminal_states", "retry", "cancellation", "invalidation", "dead_letter", "rollback"}
RETRY_KEYS = {"max_attempts", "retryable", "non_retryable", "backoff"}
CANCELLATION_KEYS = {"request_state", "ack_state", "terminal_state", "grace_seconds", "requires_terminal_reconciliation"}
INVALIDATION_KEYS = {"state", "triggers"}
DEAD_LETTER_KEYS = {"state", "after_attempts", "requires_reconciliation"}
ROLLBACK_KEYS = {"atomic_pointer_swap", "rollback_pointer_required", "independent_authority_required", "terminal_state"}

class ImprovementError(ValueError):
    """A closed-contract or stale-binding failure."""


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ImprovementError(f"{label} must be an object")
    actual = set(value)
    missing = sorted(keys - actual)
    extra = sorted(actual - keys)
    if missing or extra:
        detail = []
        if missing:
            detail.append("missing=" + ",".join(missing))
        if extra:
            detail.append("unknown=" + ",".join(extra))
        raise ImprovementError(f"{label} keys differ ({'; '.join(detail)})")
    return value


def _text(value: Any, label: str, minimum: int = 1) -> str:
    if not isinstance(value, str) or len(value.strip()) < minimum:
        raise ImprovementError(f"{label} must be a non-empty string")
    return value


def _id(value: Any, label: str) -> str:
    value = _text(value, label)
    if not ID_RE.fullmatch(value):
        raise ImprovementError(f"{label} must be a canonical lower-case identifier")
    return value


def _ids(value: Any, label: str, *, empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not empty and not value):
        raise ImprovementError(f"{label} must be a {'possibly empty ' if empty else ''}array")
    if any(not isinstance(item, str) for item in value):
        raise ImprovementError(f"{label} must contain strings")
    if value != sorted(set(value)):
        raise ImprovementError(f"{label} must be sorted and unique")
    for item in value:
        _id(item, label)
    return value


def _texts(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ImprovementError(f"{label} must be a non-empty array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ImprovementError(f"{label} must contain non-empty strings")
    if value != sorted(set(value)):
        raise ImprovementError(f"{label} must be sorted and unique")
    return value


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ImprovementError(f"{label} must be boolean")
    return value


def _positive(value: Any, label: str, *, zero: bool = False) -> int:
    floor = 0 if zero else 1
    if not isinstance(value, int) or isinstance(value, bool) or value < floor:
        raise ImprovementError(f"{label} must be {'non-negative' if zero else 'positive'} integer")
    return value


def _finite_number(value: Any, label: str, *, zero: bool = False) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ImprovementError(f"{label} must be a finite number")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")) or (not zero and number <= 0) or (zero and number < 0):
        raise ImprovementError(f"{label} must be {'non-negative' if zero else 'positive'} and finite")
    return number


def _read_pinned(path: Path, expected: str, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ImprovementError(f"{label} is missing or is not a regular file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImprovementError(f"{label} is invalid JSON") from exc
    if not isinstance(value, dict) or raw != canonical_bytes(value):
        raise ImprovementError(f"{label} is not canonical JSON")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise ImprovementError(f"{label} is stale or tampered (digest {actual})")
    return value


def _validate_registries() -> dict[str, Any]:
    source = _read_pinned(SOURCE_REGISTRY_PATH, SOURCE_REGISTRY_SHA256, "source-intelligence registry")
    mechanism = _read_pinned(MECHANISM_REGISTRY_PATH, MECHANISM_REGISTRY_SHA256, "mechanism-plane registry")
    catalog = _read_pinned(CAPABILITY_CATALOG_PATH, CAPABILITY_CATALOG_SHA256, "capability catalog")
    capability = _read_pinned(CAPABILITY_REVIEW_PATH, CAPABILITY_REVIEW_SHA256, "capability review registry")
    evaluator = _read_pinned(EVALUATOR_REGISTRY_PATH, EVALUATOR_REGISTRY_SHA256, "evaluator evidence registry")
    if source.get("$schema") != "company-os.source-intelligence-registry.v1" or source.get("record_count") != 81:
        raise ImprovementError("source-intelligence registry has unsupported schema or count")
    source_records = source.get("records")
    if not isinstance(source_records, list) or len(source_records) != 81:
        raise ImprovementError("source-intelligence registry records are incomplete")
    source_ids = [record.get("source_id") for record in source_records]
    if any(not isinstance(item, str) for item in source_ids) or len(set(source_ids)) != 81:
        raise ImprovementError("source-intelligence source IDs are not unique")
    if source.get("policy") != {
        "catalog_membership_is_review": False,
        "entrypoint_promotion_requires_dossier": True,
        "invalid_source_dispatchable": False,
        "unknown_license_allows_copy": False,
        "upstream_instructions_are_authority": False,
    }:
        raise ImprovementError("source-intelligence policy is not fail-closed")
    _validate_mechanism(source, mechanism, source_ids)
    if catalog.get("$schema") != "company-os.capability-catalog.v1" or catalog.get("catalog_id") != "company-os-capability-library":
        raise ImprovementError("capability catalog schema is unsupported")
    if capability.get("$schema") != "company-os.capability-review-registry.v1" or capability.get("review_count") != 12:
        raise ImprovementError("capability review registry schema or count is unsupported")
    if capability.get("catalog_sha256") != CAPABILITY_CATALOG_SHA256 or capability.get("source_intelligence_registry_sha256") != SOURCE_REGISTRY_SHA256:
        raise ImprovementError("capability review registry binding is stale")
    capability_records = capability.get("records")
    if not isinstance(capability_records, list) or len(capability_records) != 12:
        raise ImprovementError("capability review records are incomplete")
    capability_ids = [record.get("capability_id") for record in capability_records]
    if len(set(capability_ids)) != 12 or any(not isinstance(item, str) for item in capability_ids):
        raise ImprovementError("capability review IDs are not unique")
    if any(record.get("review_decision") != "candidate_for_independent_acceptance" for record in capability_records):
        raise ImprovementError("capability review contains an ungoverned acceptance")
    catalog_capabilities = {item.get("capability_id"): item for item in catalog.get("capabilities", []) if isinstance(item, dict)}
    if not set(capability_ids).issubset(catalog_capabilities):
        raise ImprovementError("capability review references missing catalog entries")
    if evaluator.get("$schema") != "company-os.evaluator-evidence-registry.v1" or evaluator.get("method_count") != 8:
        raise ImprovementError("evaluator evidence registry schema or count is unsupported")
    if evaluator.get("source_intelligence_registry_sha256") != SOURCE_REGISTRY_SHA256:
        raise ImprovementError("evaluator evidence source binding is stale")
    evaluator_records = evaluator.get("records")
    if not isinstance(evaluator_records, list) or len(evaluator_records) != 8:
        raise ImprovementError("evaluator evidence records are incomplete")
    if any(record.get("status") != "research_method_only" for record in evaluator_records):
        raise ImprovementError("evaluator registry unexpectedly contains a ready adapter")
    if evaluator.get("policy", {}).get("research_methods_execute") is not False or evaluator.get("policy", {}).get("research_methods_score") is not False:
        raise ImprovementError("evaluator registry policy permits execution or scoring")
    return {
        "source": source,
        "mechanism": mechanism,
        "catalog": catalog,
        "capability": capability,
        "evaluator": evaluator,
        "source_records": {record["source_id"]: record for record in source_records},
        "capability_records": {record["capability_id"]: record for record in capability_records},
        "catalog_capabilities": catalog_capabilities,
        "evaluator_records": evaluator_records,
    }


def _validate_mechanism(source: Mapping[str, Any], mechanism: Mapping[str, Any], source_ids: list[str]) -> None:
    if mechanism.get("$schema") != "company-os.mechanism-plane-registry.v1" or mechanism.get("schema_version") != 1:
        raise ImprovementError("mechanism-plane registry schema is unsupported")
    if mechanism.get("source_intelligence_registry_sha256") != SOURCE_REGISTRY_SHA256:
        raise ImprovementError("mechanism-plane source binding is stale")
    planes = mechanism.get("destination_planes")
    if not isinstance(planes, list) or len(planes) != 8:
        raise ImprovementError("mechanism registry must contain exactly 8 destination planes")
    plane_ids = [item.get("id") for item in planes]
    if plane_ids != sorted(plane_ids, key=lambda item: next(p.get("build_order", 99) for p in planes if p.get("id") == item)) or len(set(plane_ids)) != 8:
        raise ImprovementError("destination planes are not unique and ordered")
    plane_by_id = {item["id"]: item for item in planes}
    if sorted(item.get("build_order") for item in planes) != list(range(1, 9)):
        raise ImprovementError("destination plane build order is not exact")
    groups = mechanism.get("source_groups")
    if not isinstance(groups, list) or len(groups) != 11:
        raise ImprovementError("mechanism registry must contain exactly 11 source groups")
    group_by_id: dict[str, Mapping[str, Any]] = {}
    assigned: list[str] = []
    for group in groups:
        if not isinstance(group, dict):
            raise ImprovementError("mechanism source group is not an object")
        group_id = group.get("id")
        destination = group.get("destination")
        ids = group.get("source_ids")
        if not isinstance(group_id, str) or group_id in group_by_id or destination not in plane_by_id:
            raise ImprovementError("mechanism source group identity is invalid")
        if not isinstance(ids, list) or len(ids) != len(set(ids)) or any(not isinstance(item, str) for item in ids):
            raise ImprovementError(f"mechanism group {group_id!r} source IDs are not sorted and unique")
        if not isinstance(group.get("adopt"), list) or not isinstance(group.get("reject"), list) or not group.get("reject"):
            raise ImprovementError(f"mechanism group {group_id!r} lacks adopt/reject decisions")
        group_by_id[group_id] = group
        assigned.extend(ids)
    if len(assigned) != len(set(assigned)) or set(assigned) != set(source_ids) or len(assigned) != 81:
        raise ImprovementError("mechanism source groups do not cover each submitted source exactly once")
    decisions = mechanism.get("mechanism_decisions")
    if not isinstance(decisions, list) or len(decisions) != 81:
        raise ImprovementError("mechanism decisions do not cover 81 source records")
    decision_ids = [item.get("source_id") for item in decisions]
    if decision_ids != sorted(set(decision_ids)) or set(decision_ids) != set(source_ids):
        raise ImprovementError("mechanism decisions have duplicate or missing source IDs")
    source_by_id = {item["source_id"]: item for item in source.get("records", [])}
    for decision in decisions:
        if not isinstance(decision, dict):
            raise ImprovementError("mechanism decision is not an object")
        source_id = decision["source_id"]
        source_record = source_by_id[source_id]
        group_id = decision.get("mechanism_group_id")
        group = group_by_id.get(group_id)
        if group is None or decision.get("destination_plane") != group.get("destination"):
            raise ImprovementError(f"mechanism decision binding differs for {source_id!r}")
        if decision.get("normalized_family_id") != source_record.get("normalized_family_id") or source_record.get("mechanism_group_id") != group_id:
            raise ImprovementError(f"mechanism source binding differs for {source_id!r}")
        if decision.get("disposition") != group.get("disposition") or decision.get("adopt") != group.get("adopt") or decision.get("reject") != group.get("reject"):
            raise ImprovementError(f"mechanism decision evidence differs for {source_id!r}")


def _validate_request_shape(raw: Any) -> dict[str, Any]:
    request = _exact(raw, REQUEST_KEYS, "request")
    if request.get("schema") != SCHEMA:
        raise ImprovementError("unsupported request schema")
    program = _exact(request["program"], PROGRAM_KEYS, "program")
    for key in ("tenant_id", "project_id", "program_id", "cycle_id"):
        _id(program[key], f"program.{key}")
    _positive(program["definition_version"], "program.definition_version")
    _positive(program["policy_version"], "program.policy_version")
    intent = _exact(request["intent"], INTENT_KEYS, "intent")
    _text(intent["objective"], "intent.objective", 10)
    hypothesis = _text(intent["hypothesis"], "intent.hypothesis", 20)
    normalized = " ".join(hypothesis.lower().split())
    if any(phrase in normalized for phrase in ("improve everything", "make everything better", "fix everything", "optimize everything", "do whatever it takes")):
        raise ImprovementError("intent.hypothesis is unbounded")
    _texts(intent["success_criteria"], "intent.success_criteria")
    _texts(intent["falsification_criteria"], "intent.falsification_criteria")
    _ids(intent["evidence_ids"], "intent.evidence_ids")
    baseline = _exact(request["baseline"], BASELINE_KEYS, "baseline")
    _id(baseline["artifact_id"], "baseline.artifact_id")
    _text(baseline["version"], "baseline.version")
    target = _exact(request["target"], TARGET_KEYS, "target")
    if target["kind"] not in TARGET_KINDS:
        raise ImprovementError("target.kind is invalid")
    if target["opportunity_type"] not in {"reproduced_bottleneck", "forward_capability"}:
        raise ImprovementError("target.opportunity_type is invalid")
    _text(target["reason"], "target.reason", 20)
    protected = _ids(target["protected_surfaces"] , "target.protected_surfaces")
    if not {"authority", "scheduler", "evaluation", "promotion"}.issubset(protected):
        raise ImprovementError("target.protected_surfaces must preserve authority, scheduler, evaluation, and promotion")
    _text(target["reversible_scope"], "target.reversible_scope", 12)
    source_ids = _ids(request["source_ids"], "source_ids")
    capability_ids = _ids(request["capability_ids"], "capability_ids")
    evaluation = _exact(request["evaluation"], EVALUATION_KEYS, "evaluation")
    artifact_classes = _ids(evaluation["artifact_classes"], "evaluation.artifact_classes")
    stages = _ids(evaluation["stages"], "evaluation.stages")
    if any(stage not in STAGES for stage in stages):
        raise ImprovementError("evaluation.stages contains an unsupported stage")
    budgets = _exact(request["budgets"], BUDGET_KEYS, "budgets")
    if budgets["max_candidates"] != 3:
        raise ImprovementError("budgets.max_candidates must be exactly three")
    for key in ("max_candidates", "max_passes", "max_concurrency", "max_time_minutes", "max_tokens", "max_context_bytes", "dead_letter_after", "cancel_grace_seconds"):
        _positive(budgets[key], f"budgets.{key}")
    _positive(budgets["max_retries"], "budgets.max_retries", zero=True)
    _finite_number(budgets["max_cost_usd"], "budgets.max_cost_usd")
    if budgets["max_passes"] < 3 or budgets["max_concurrency"] > 3:
        raise ImprovementError("budgets do not permit exactly three bounded candidates")
    if budgets["dead_letter_after"] <= budgets["max_retries"]:
        raise ImprovementError("dead-letter threshold must exceed retry budget")
    ceilings = {"max_passes": 64, "max_concurrency": 3, "max_time_minutes": 1440, "max_tokens": 50_000_000, "max_context_bytes": 65_536, "dead_letter_after": 32, "cancel_grace_seconds": 3600}
    for key, ceiling in ceilings.items():
        if budgets[key] > ceiling:
            raise ImprovementError(f"budgets.{key} exceeds compiler safety ceiling")
    if len(source_ids) > 81 or len(capability_ids) > 12:
        raise ImprovementError("requested registry selection exceeds governed coverage")
    return request


def _resolve_selection(request: Mapping[str, Any], registries: Mapping[str, Any]) -> dict[str, Any]:
    source_ids = request["source_ids"]
    source_index = registries["source_records"]
    missing_sources = sorted(set(source_ids) - set(source_index))
    if missing_sources:
        raise ImprovementError("unknown source IDs: " + ", ".join(missing_sources))
    capability_ids = request["capability_ids"]
    cap_index = registries["capability_records"]
    missing_caps = sorted(set(capability_ids) - set(cap_index))
    if missing_caps:
        raise ImprovementError("unknown capability IDs: " + ", ".join(missing_caps))
    for capability_id in capability_ids:
        record = cap_index[capability_id]
        if record.get("review_decision") != "candidate_for_independent_acceptance":
            raise ImprovementError(f"capability {capability_id!r} is not an unresolved candidate")
    source_resolution = []
    mechanism_decisions = {item["source_id"]: item for item in registries["mechanism"]["mechanism_decisions"]}
    for source_id in source_ids:
        source = source_index[source_id]
        decision = mechanism_decisions[source_id]
        source_resolution.append({
            "source_id": source_id,
            "normalized_family_id": source["normalized_family_id"],
            "pin": source["pin"],
            "license_state": source["license_state"],
            "disposition": source["disposition"],
            "review_decision": source["review_decision"],
            "review_evidence_sha256": source["review_evidence_sha256"],
            "mechanism_group_id": source["mechanism_group_id"],
            "destination_plane": decision["destination_plane"],
            "adopt": decision["adopt"],
            "reject": decision["reject"],
        })
    capability_resolution = []
    for capability_id in capability_ids:
        review = cap_index[capability_id]
        catalog_record = registries["catalog_capabilities"][capability_id]
        capability_resolution.append({
            "capability_id": capability_id,
            "source_id": review["source_id"],
            "source_intelligence_id": review["source_intelligence_id"],
            "source_review_sha256": review["source_review_sha256"],
            "review_id": review["review_id"],
            "review_record_sha256": digest_value(review),
            "upstream_entrypoint_sha256": review["upstream_entrypoint_sha256"],
            "wrapper_entrypoint_sha256": review["wrapper_entrypoint_sha256"],
            "checkout_manifest_sha256": review["checkout_manifest_sha256"],
            "source_checkout_commit": review["source_checkout_commit"],
            "source_checkout_tree": review["source_checkout_tree"],
            "review_decision": review["review_decision"],
            "efficacy_state": review["efficacy_state"],
            "phase": review["phase"],
            "effect_class": review["effect_class"],
            "provider_boundary": review["provider_boundary"],
            "required_permissions": review["required_permissions"],
            "exclusive_family": review["exclusive_family"],
            "license_conclusion": review["license_conclusion"],
            "portable_acceptance_state": "absent",
            "production_dispatchable": False,
        })
    stages = request["evaluation"]["stages"]
    artifacts = set(request["evaluation"]["artifact_classes"])
    methods = []
    for record in registries["evaluator_records"]:
        if record.get("stage") in stages and (artifacts & set(record.get("artifact_classes", []))):
            methods.append(dict(record))
    if not methods:
        raise ImprovementError("requested evaluation stages have no governed research methods")
    methods.sort(key=lambda item: item["method_id"])
    return {"source_ids": source_ids, "capability_ids": capability_ids, "methods": methods, "source_records": source_resolution, "capability_records": capability_resolution}


def validate_request(raw: Any) -> dict[str, Any]:
    """Validate the closed caller contract without resolving external truth."""
    return _validate_request_shape(raw)


def _partition_manifest(request_sha: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    partitions = []
    ledger = []
    for kind in PARTITION_ORDER:
        members = []
        for profile in PROFILES:
            for ordinal in (1, 2):
                body = {"candidate_profile": profile, "partition": kind, "ordinal": ordinal, "seed": digest_value({"request": request_sha, "profile": profile, "partition": kind, "ordinal": ordinal})}
                members.append({**body, "member_id": f"member-{profile}-{kind}-{ordinal}", "member_digest": digest_value(body)})
        partitions.append({"kind": kind, "membership_state": "planned_unmaterialized", "exposure_state": PARTITION_EXPOSURE[kind], "burned": False, "reused_after_feedback": False, "members": members})
        ledger.append({"partition": kind, "membership_state": "planned_unmaterialized", "exposure_state": PARTITION_EXPOSURE[kind], "burned": False, "reused_after_feedback": False, "member_ids": [member["member_id"] for member in members], "event": "planned_unmaterialized"})
    return partitions, ledger


def _candidate_body(request: Mapping[str, Any], request_sha: str, profile: str, selection: Mapping[str, Any]) -> dict[str, Any]:
    body = {
        "profile": profile,
        "profile_rank": PROFILES[profile]["rank"],
        "strategy": PROFILES[profile]["strategy"],
        "intervention": PROFILES[profile]["intervention"],
        "controls": PROFILES[profile]["controls"],
        "parent_digest": digest_value({"baseline": request["baseline"], "target": request["target"]}),
        "common_ancestor_digest": digest_value({"request": request_sha, "baseline": request["baseline"]["artifact_id"]}),
        "environment_digest": digest_value({"program": request["program"], "profile": profile}),
        "tool_policy_digest": digest_value({"authority": "company-os-control-plane", "external_effects": False, "profile": profile}),
        "owned_resources": [f"candidate/{profile}/artifact", f"candidate/{profile}/evidence"],
        "semantic_contract_touches": [f"target/{request['target']['kind']}", f"profile/{profile}"],
        "expected_artifact_classes": request["evaluation"]["artifact_classes"],
        "capability_ids": selection["capability_ids"],
        "roles": {
            "proposer": f"proposer-{profile}",
            "candidate_owner": f"candidate-owner-{profile}",
            "evaluator": f"evaluator-{profile}",
            "confirmer": f"confirmer-{profile}",
            "accepter": f"accepter-{profile}",
            "promoter": "company-os-promotion-authority",
        },
    }
    return body


def _validate_dag(organization: Mapping[str, Any], candidate_resources: set[str]) -> None:
    nodes = organization.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ImprovementError("organization dependency DAG is empty")
    by_id: dict[str, Mapping[str, Any]] = {}
    owners: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ImprovementError("organization DAG node is not an object")
        node_id = node.get("id")
        if not isinstance(node_id, str) or node_id in by_id:
            raise ImprovementError("organization DAG node IDs must be unique")
        deps = node.get("depends_on")
        resources = node.get("owned_resources")
        if not isinstance(deps, list) or deps != sorted(set(deps)) or any(not isinstance(item, str) for item in deps):
            raise ImprovementError("organization DAG dependencies must be sorted and unique")
        if not isinstance(resources, list) or resources != sorted(set(resources)) or any(not isinstance(item, str) for item in resources):
            raise ImprovementError("organization owned resources must be sorted and unique")
        by_id[node_id] = node
        for resource in resources:
            if resource in owners:
                raise ImprovementError(f"organization resource ownership collision: {resource}")
            owners[resource] = node_id
    for node_id, node in by_id.items():
        for dependency in node["depends_on"]:
            if dependency not in by_id or dependency == node_id:
                raise ImprovementError("organization DAG has missing or self dependency")
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ImprovementError("organization dependency DAG contains a cycle")
        if node_id in visited:
            return
        visiting.add(node_id)
        for dep in by_id[node_id]["depends_on"]:
            visit(dep)
        visiting.remove(node_id)
        visited.add(node_id)
    for node_id in by_id:
        visit(node_id)
    if not candidate_resources.issubset(set(owners)):
        raise ImprovementError("candidate resources are not owned by the dependency DAG")


def _build_organization(candidate_resources: set[str] | None = None) -> dict[str, Any]:
    nodes = [
        {"id": "source-resolution", "depends_on": [], "owned_resources": ["registry/source-intelligence", "registry/mechanism-plane"]},
        {"id": "capability-resolution", "depends_on": ["source-resolution"], "owned_resources": ["registry/capability-review"]},
        {"id": "evaluator-resolution", "depends_on": ["source-resolution"], "owned_resources": ["registry/evaluator-methods"]},
        {"id": "candidate-cohort", "depends_on": ["capability-resolution", "evaluator-resolution"], "owned_resources": ["cohort/candidates"]},
        {"id": "partition-manifests", "depends_on": ["candidate-cohort"], "owned_resources": ["evaluation/partitions"]},
        {"id": "decision-receipts", "depends_on": ["partition-manifests"], "owned_resources": ["decision/receipts"]},
        {"id": "promotion-gate", "depends_on": ["decision-receipts"], "owned_resources": ["promotion/pointer"]},
    ]
    for node in nodes:
        node["depends_on"] = sorted(node["depends_on"])
        node["owned_resources"] = sorted(node["owned_resources"])
    if candidate_resources:
        nodes[3]["owned_resources"] = sorted(set(nodes[3]["owned_resources"]) | candidate_resources)
    organization = {"nodes": nodes, "topological_order": [node["id"] for node in nodes], "ownership_policy": "one-owner-per-resource"}
    _validate_dag(organization, {"cohort/candidates", "evaluation/partitions", "decision/receipts", "promotion/pointer"})
    return organization


def _build_lifecycle(budgets: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ordered_states": ORDERED_STATES,
        "terminal_states": TERMINAL_STATES,
        "retry": {"max_attempts": budgets["max_retries"], "retryable": ["cancel_ack_timeout", "lease_expired", "transient_evaluator_unavailable"], "non_retryable": ["authority_violation", "invalid_evidence", "stale_binding"], "backoff": "bounded_exponential"},
        "cancellation": {"request_state": "cancel_requested", "ack_state": "cancel_acknowledged", "terminal_state": "cancelled", "grace_seconds": budgets["cancel_grace_seconds"], "requires_terminal_reconciliation": True},
        "invalidation": {"state": "invalid_evidence", "triggers": ["burned_member_reuse", "evaluator_epoch_drift", "observed_telemetry_without_evidence", "partition_overlap", "sealed_exposure", "stale_registry_binding"]},
        "dead_letter": {"state": "dead_letter", "after_attempts": budgets["dead_letter_after"], "requires_reconciliation": True},
        "rollback": {"atomic_pointer_swap": True, "rollback_pointer_required": True, "independent_authority_required": True, "terminal_state": "rolled_back"},
    }


def _build_decision_receipt_requirements(candidates: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    required_by_type = {
        "proposal": ["bounded_intent", "source_resolution", "common_ancestor"],
        "ownership": ["owned_resources", "role_separation", "capability_boundary"],
        "evaluation": ["method_registry", "partition_manifest", "calibration_and_epoch"],
        "confirmation": ["negative_results", "independent_comparison", "rollback_plan"],
        "acceptance": ["critical_floors", "evidence_integrity", "manager_decision"],
        "promotion": ["atomic_pointer", "delayed_outcome", "promotion_authority"],
    }
    role_by_type = {
        "proposal": "proposer", "ownership": "candidate_owner", "evaluation": "evaluator",
        "confirmation": "confirmer", "acceptance": "accepter", "promotion": "promoter",
    }
    for candidate in candidates:
        roles = candidate["roles"]
        for decision_type in ("proposal", "ownership", "evaluation", "confirmation", "acceptance", "promotion"):
            role_key = role_by_type[decision_type]
            requirements.append({
                "candidate_profile": candidate["profile"],
                "decision_type": decision_type,
                "role": roles[role_key],
                "status": "pending",
                "requirements": required_by_type[decision_type],
                "independent_of": sorted(set(roles.values()) - {roles[role_key]}),
            })
    requirements.sort(key=lambda item: (item["candidate_profile"], item["decision_type"]))
    return requirements


def compile_program(request: Mapping[str, Any]) -> dict[str, Any]:
    request = _validate_request_shape(request)
    registries = _validate_registries()
    selection = _resolve_selection(request, registries)
    request_sha = digest_value(request)
    partitions, ledger = _partition_manifest(request_sha)
    candidates = []
    for profile in PROFILES:
        body = _candidate_body(request, request_sha, profile, selection)
        candidates.append({**body, "candidate_digest": digest_value(body)})
    cohort_digest = digest_value([candidate["candidate_digest"] for candidate in candidates])
    candidate_resources = {resource for candidate in candidates for resource in candidate["owned_resources"]}
    organization = _build_organization(candidate_resources)
    _validate_dag(organization, set(organization["nodes"][3]["owned_resources"]) | {"evaluation/partitions", "decision/receipts", "promotion/pointer"})
    decision_receipt_requirements = _build_decision_receipt_requirements(candidates)
    blockers = [
        {"code": "EVALUATOR_ADAPTERS_UNREADY", "reason": "evaluator registry contains zero ready adapters", "evidence": registries["evaluator"]["registry_id"]},
        {"code": "CAPABILITIES_PENDING_ACCEPTANCE", "reason": f"all {len(selection['capability_ids'])} requested external capabilities remain candidate_for_independent_acceptance", "evidence": registries["capability"]["registry_id"]},
        {"code": "EXTERNAL_EFFECTS_DISABLED", "reason": "feature-off compiler cannot authorize runtime, provider, or production effects", "evidence": "company-os-control-plane"},
    ]
    source_records = registries["source_records"]
    groups = {}
    for source_id in selection["source_ids"]:
        group = source_records[source_id]["mechanism_group_id"]
        groups[group] = groups.get(group, 0) + 1
    program = {
        "schema": PROGRAM_SCHEMA,
        "activation_state": "planned",
        "executable": False,
        "execution_status": "blocked",
        "blockers": blockers,
        "request_sha256": request_sha,
        "registry_bindings": {
            "source_intelligence": {"registry_id": registries["source"]["registry_id"], "sha256": SOURCE_REGISTRY_SHA256, "record_count": 81},
            "mechanism_plane": {"registry_id": registries["mechanism"]["registry_id"], "sha256": MECHANISM_REGISTRY_SHA256, "destination_plane_count": 8, "source_group_count": 11, "decision_count": 81},
            "capability_catalog": {"catalog_id": registries["catalog"]["catalog_id"], "sha256": CAPABILITY_CATALOG_SHA256},
            "capability_review": {"registry_id": registries["capability"]["registry_id"], "sha256": CAPABILITY_REVIEW_SHA256, "accepted_count": 0, "candidate_count": 12},
            "evaluator_methods": {"registry_id": registries["evaluator"]["registry_id"], "sha256": EVALUATOR_REGISTRY_SHA256, "ready_adapter_count": 0, "method_count": 8},
        },
        "program": request["program"],
        "intent": request["intent"],
        "baseline": request["baseline"],
        "target": request["target"],
        "source_resolution": {"requested_source_ids": selection["source_ids"], "resolved_record_count": len(selection["source_ids"]), "records": selection["source_records"], "mechanism_group_counts": groups},
        "capability_resolution": {
            "requested_capability_ids": selection["capability_ids"], "resolved_candidate_count": len(selection["capability_ids"]), "accepted_count": 0,
            "portable_resolver": {
                "resolver_id": "company-os-capability-review-portable-resolver", "registry_sha256": CAPABILITY_REVIEW_SHA256,
                "accepted_receipt_required": True, "portable_bundle_allowed": False, "selected_acceptance_receipt": None,
                "production_dispatchable": False,
            },
            "records": selection["capability_records"],
        },
        "evaluation": {
            "artifact_classes": request["evaluation"]["artifact_classes"], "requested_stages": request["evaluation"]["stages"],
            "methods": selection["methods"], "ready_adapter_count": 0, "partitions": partitions, "exposure_burn_ledger": ledger,
            "failure_semantics": "invalid_evidence", "evaluator_epoch_policy": "epoch_change_invalidates_current_decision",
        },
        "candidates": candidates,
        "cohort_digest": cohort_digest,
        "organization": organization,
        "decision_receipt_requirements": decision_receipt_requirements,
        "budgets": request["budgets"],
        "lifecycle": _build_lifecycle(request["budgets"]),
        "authority": {
            "control_plane_id": "company-os-control-plane", "scheduler_id": "company-os-scheduler", "evaluator_registry_id": registries["evaluator"]["registry_id"],
            "promotion_registry_id": "company-os-promotion-registry", "promotion_authority_id": "company-os-promotion-authority", "external_effects_allowed": False,
        },
        "promotion": {
            "registry_id": "company-os-promotion-registry", "current_pointer_digest": digest_value({"baseline": request["baseline"], "program": request["program"]}),
            "rollback_pointer_digest": digest_value({"rollback": request["baseline"], "program": request["program"]}), "atomicity_required": True,
            "authority_id": "company-os-promotion-authority", "delayed_outcome_required": True, "delayed_outcome_window_days": 30,
        },
        "telemetry": {"requested": {"model": None, "effort": None}, "observed": None, "observed_evidence_ref": None},
        "side_effects": [],
        "warnings": ["observed runtime model, effort, tokens, and cost are intentionally unavailable"],
    }
    validate_program(program)
    return program


def _validate_source_resolution(value: Any, registries: Mapping[str, Any]) -> None:
    resolution = _exact(value, SOURCE_RESOLUTION_KEYS, "source_resolution")
    source_ids = _ids(resolution["requested_source_ids"], "source_resolution.requested_source_ids")
    if resolution["resolved_record_count"] != len(source_ids):
        raise ImprovementError("source resolution count does not match selected IDs")
    records = resolution["records"]
    if not isinstance(records, list) or len(records) != len(source_ids):
        raise ImprovementError("source resolution records are incomplete")
    source_index = registries["source_records"]
    decisions = {item["source_id"]: item for item in registries["mechanism"]["mechanism_decisions"]}
    expected_records = []
    for source_id in source_ids:
        source = source_index.get(source_id)
        decision = decisions.get(source_id)
        if source is None or decision is None:
            raise ImprovementError(f"source resolution references unknown source {source_id!r}")
        expected_records.append({
            "source_id": source_id,
            "normalized_family_id": source["normalized_family_id"],
            "pin": source["pin"],
            "license_state": source["license_state"],
            "disposition": source["disposition"],
            "review_decision": source["review_decision"],
            "review_evidence_sha256": source["review_evidence_sha256"],
            "mechanism_group_id": source["mechanism_group_id"],
            "destination_plane": decision["destination_plane"],
            "adopt": decision["adopt"],
            "reject": decision["reject"],
        })
    for index, record in enumerate(records):
        record = _exact(record, SOURCE_RECORD_KEYS, f"source_resolution.records[{index}]")
        if record != expected_records[index]:
            raise ImprovementError(f"source resolution binding differs for {source_ids[index]!r}")
    counts: dict[str, int] = {}
    for record in expected_records:
        counts[record["mechanism_group_id"]] = counts.get(record["mechanism_group_id"], 0) + 1
    if resolution["mechanism_group_counts"] != counts:
        raise ImprovementError("source mechanism group counts are stale")


def _validate_capability_resolution(value: Any, registries: Mapping[str, Any]) -> None:
    resolution = _exact(value, CAPABILITY_RESOLUTION_KEYS, "capability_resolution")
    capability_ids = _ids(resolution["requested_capability_ids"], "capability_resolution.requested_capability_ids")
    if resolution["resolved_candidate_count"] != len(capability_ids) or resolution["accepted_count"] != 0:
        raise ImprovementError("capability resolution count or acceptance is invalid")
    resolver = _exact(resolution["portable_resolver"], PORTABLE_RESOLVER_KEYS, "capability_resolution.portable_resolver")
    expected_resolver = {
        "resolver_id": "company-os-capability-review-portable-resolver",
        "registry_sha256": CAPABILITY_REVIEW_SHA256,
        "accepted_receipt_required": True,
        "portable_bundle_allowed": False,
        "selected_acceptance_receipt": None,
        "production_dispatchable": False,
    }
    if resolver != expected_resolver:
        raise ImprovementError("portable capability resolver binding is invalid")
    records = resolution["records"]
    if not isinstance(records, list) or len(records) != len(capability_ids):
        raise ImprovementError("capability resolution records are incomplete")
    expected_records = []
    for capability_id in capability_ids:
        review = registries["capability_records"].get(capability_id)
        if review is None or review.get("review_decision") != "candidate_for_independent_acceptance":
            raise ImprovementError(f"capability {capability_id!r} is not an unresolved candidate")
        expected_records.append({
            "capability_id": capability_id,
            "source_id": review["source_id"],
            "source_intelligence_id": review["source_intelligence_id"],
            "source_review_sha256": review["source_review_sha256"],
            "review_id": review["review_id"],
            "review_record_sha256": digest_value(review),
            "upstream_entrypoint_sha256": review["upstream_entrypoint_sha256"],
            "wrapper_entrypoint_sha256": review["wrapper_entrypoint_sha256"],
            "checkout_manifest_sha256": review["checkout_manifest_sha256"],
            "source_checkout_commit": review["source_checkout_commit"],
            "source_checkout_tree": review["source_checkout_tree"],
            "review_decision": review["review_decision"],
            "efficacy_state": review["efficacy_state"],
            "phase": review["phase"],
            "effect_class": review["effect_class"],
            "provider_boundary": review["provider_boundary"],
            "required_permissions": review["required_permissions"],
            "exclusive_family": review["exclusive_family"],
            "license_conclusion": review["license_conclusion"],
            "portable_acceptance_state": "absent",
            "production_dispatchable": False,
        })
    for index, record in enumerate(records):
        record = _exact(record, CAPABILITY_RECORD_KEYS, f"capability_resolution.records[{index}]")
        if record != expected_records[index]:
            raise ImprovementError(f"capability resolution binding differs for {capability_ids[index]!r}")


def _validate_evaluation_output(value: Any, registries: Mapping[str, Any], request_sha: str) -> None:
    evaluation = _exact(value, EVALUATION_OUTPUT_KEYS, "evaluation")
    artifact_classes = _ids(evaluation["artifact_classes"], "evaluation.artifact_classes")
    stages = _ids(evaluation["requested_stages"], "evaluation.requested_stages")
    if any(stage not in STAGES for stage in stages) or evaluation["ready_adapter_count"] != 0:
        raise ImprovementError("evaluator readiness or stage selection is invalid")
    if evaluation["failure_semantics"] != "invalid_evidence" or evaluation["evaluator_epoch_policy"] != "epoch_change_invalidates_current_decision":
        raise ImprovementError("evaluator failure or epoch policy is invalid")
    methods = evaluation["methods"]
    if not isinstance(methods, list):
        raise ImprovementError("evaluation methods must be an array")
    expected = [record for record in registries["evaluator_records"] if record.get("stage") in stages and set(artifact_classes) & set(record.get("artifact_classes", []))]
    expected.sort(key=lambda item: item["method_id"])
    if methods != expected:
        raise ImprovementError("evaluator method records are stale or incomplete")
    _validate_partitions(evaluation["partitions"], evaluation["exposure_burn_ledger"], request_sha)


def _validate_partitions(partitions: Any, ledger: Any, request_sha: str) -> None:
    if not isinstance(partitions, list) or [item.get("kind") for item in partitions] != list(PARTITION_ORDER):
        raise ImprovementError("evaluation must contain exactly four partition manifests")
    all_member_ids: set[str] = set()
    all_member_digests: set[str] = set()
    partition_ids: dict[str, list[str]] = {}
    for partition_index, raw in enumerate(partitions):
        partition = _exact(raw, PARTITION_KEYS, f"evaluation.partitions[{partition_index}]")
        kind = partition["kind"]
        if partition["membership_state"] != "planned_unmaterialized" or partition["exposure_state"] != PARTITION_EXPOSURE[kind] or partition["burned"] is not False or partition["reused_after_feedback"] is not False:
            raise ImprovementError("partition is actualized, exposed, burned, or reused")
        members = partition["members"]
        if not isinstance(members, list) or len(members) != 6:
            raise ImprovementError("planned partition member count is invalid")
        ids: list[str] = []
        expected_pairs = [(profile, ordinal) for profile in PROFILES for ordinal in (1, 2)]
        for member_index, raw_member in enumerate(members):
            member = _exact(raw_member, MEMBER_KEYS, f"evaluation.partitions[{partition_index}].members[{member_index}]")
            expected_profile, expected_ordinal = expected_pairs[member_index]
            if member["candidate_profile"] != expected_profile or member["partition"] != kind or member["ordinal"] != expected_ordinal:
                raise ImprovementError("partition member assignment is not the deterministic planned manifest")
            _positive(member["ordinal"], "partition member ordinal")
            if not isinstance(member["seed"], str) or not HEX64.fullmatch(member["seed"]):
                raise ImprovementError("partition member seed is invalid")
            expected_seed = digest_value({"request": request_sha, "profile": expected_profile, "partition": kind, "ordinal": expected_ordinal})
            if member["seed"] != expected_seed:
                raise ImprovementError("partition member seed does not bind the request")
            expected_id = f"member-{expected_profile}-{kind}-{expected_ordinal}"
            if member["member_id"] != expected_id:
                raise ImprovementError("partition member is not a planned synthetic allocation")
            body = {key: member[key] for key in ("candidate_profile", "partition", "ordinal", "seed")}
            if member["member_digest"] != digest_value(body):
                raise ImprovementError("partition member digest does not verify")
            if member["member_id"] in all_member_ids or member["member_digest"] in all_member_digests:
                raise ImprovementError("partition members overlap")
            ids.append(member["member_id"])
            all_member_ids.add(member["member_id"])
            all_member_digests.add(member["member_digest"])
        partition_ids[kind] = ids
    if not isinstance(ledger, list) or [item.get("partition") for item in ledger] != list(PARTITION_ORDER):
        raise ImprovementError("exposure/burn ledger is incomplete")
    for ledger_index, raw_entry in enumerate(ledger):
        entry = _exact(raw_entry, LEDGER_KEYS, f"evaluation.exposure_burn_ledger[{ledger_index}]")
        kind = entry["partition"]
        if entry["membership_state"] != "planned_unmaterialized" or entry["exposure_state"] != PARTITION_EXPOSURE[kind] or entry["burned"] is not False or entry["reused_after_feedback"] is not False or entry["event"] != "planned_unmaterialized":
            raise ImprovementError("exposure/burn ledger invalidates planned evidence")
        if entry["member_ids"] != partition_ids[kind]:
            raise ImprovementError("exposure ledger member set differs from partition manifest")


def _validate_candidates(value: Any, evaluation: Mapping[str, Any], capability_ids: list[str], target: Mapping[str, Any]) -> tuple[list[dict[str, Any]], set[str]]:
    candidates = value
    if not isinstance(candidates, list) or [item.get("profile") for item in candidates] != list(PROFILES):
        raise ImprovementError("candidate cohort must contain conservative, adjacent, and first_principles in order")
    request_sha = target.get("_request_sha256")
    baseline = target.get("_baseline")
    program_identity = target.get("_program")
    if not isinstance(request_sha, str) or not HEX64.fullmatch(request_sha) or not isinstance(baseline, dict) or not isinstance(program_identity, dict):
        raise ImprovementError("candidate lineage request binding is invalid")
    digests: list[str] = []
    resources: set[str] = set()
    for index, raw in enumerate(candidates):
        candidate = _exact(raw, CANDIDATE_KEYS, f"candidates[{index}]")
        profile = candidate["profile"]
        spec = PROFILES[profile]
        if candidate["profile_rank"] != spec["rank"] or candidate["strategy"] != spec["strategy"] or candidate["intervention"] != spec["intervention"] or candidate["controls"] != spec["controls"]:
            raise ImprovementError("candidate profile strategy is not immutable")
        expected_digests = {
            "parent_digest": digest_value({"baseline": baseline, "target": {key: value for key, value in target.items() if not key.startswith("_")}}),
            "common_ancestor_digest": digest_value({"request": request_sha, "baseline": baseline["artifact_id"]}),
            "environment_digest": digest_value({"program": program_identity, "profile": profile}),
            "tool_policy_digest": digest_value({"authority": "company-os-control-plane", "external_effects": False, "profile": profile}),
        }
        if any(candidate[key] != expected for key, expected in expected_digests.items()):
            raise ImprovementError("candidate lineage digest binding differs")
        for key in ("parent_digest", "common_ancestor_digest", "environment_digest", "tool_policy_digest", "candidate_digest"):
            if not isinstance(candidate[key], str) or not HEX64.fullmatch(candidate[key]):
                raise ImprovementError(f"candidate {key} is not a digest")
        if candidate["owned_resources"] != sorted(set(candidate["owned_resources"])) or any(not isinstance(item, str) for item in candidate["owned_resources"]):
            raise ImprovementError("candidate resources are not unique")
        if set(resources) & set(candidate["owned_resources"]):
            raise ImprovementError("candidate resource ownership collision")
        resources.update(candidate["owned_resources"])
        expected_resources = [f"candidate/{profile}/artifact", f"candidate/{profile}/evidence"]
        if candidate["owned_resources"] != expected_resources:
            raise ImprovementError("candidate resource scope differs")
        if candidate["semantic_contract_touches"] != [f"target/{target['kind']}", f"profile/{profile}"]:
            raise ImprovementError("candidate semantic contract scope differs")
        if candidate["expected_artifact_classes"] != evaluation["artifact_classes"] or candidate["capability_ids"] != capability_ids:
            raise ImprovementError("candidate selection binding differs")
        roles = _exact(candidate["roles"], ROLE_KEYS, f"candidates[{index}].roles")
        if len(set(roles.values())) != len(roles) or roles["promoter"] != "company-os-promotion-authority":
            raise ImprovementError("candidate roles are not independent")
        body = {key: candidate[key] for key in CANDIDATE_KEYS if key != "candidate_digest"}
        if candidate["candidate_digest"] != digest_value(body):
            raise ImprovementError("candidate digest does not verify")
        digests.append(candidate["candidate_digest"])
    return digests, resources


def _validate_lifecycle(value: Any, budgets: Mapping[str, Any]) -> None:
    lifecycle = _exact(value, LIFECYCLE_KEYS, "lifecycle")
    expected = _build_lifecycle(budgets)
    if lifecycle != expected:
        raise ImprovementError("lifecycle contract differs from finite budgets")
    retry = _exact(lifecycle["retry"], RETRY_KEYS, "lifecycle.retry")
    _positive(retry["max_attempts"], "lifecycle.retry.max_attempts", zero=True)
    _ids(retry["retryable"], "lifecycle.retry.retryable")
    _ids(retry["non_retryable"], "lifecycle.retry.non_retryable")
    _text(retry["backoff"], "lifecycle.retry.backoff")
    _exact(lifecycle["cancellation"], CANCELLATION_KEYS, "lifecycle.cancellation")
    _exact(lifecycle["invalidation"], INVALIDATION_KEYS, "lifecycle.invalidation")
    _exact(lifecycle["dead_letter"], DEAD_LETTER_KEYS, "lifecycle.dead_letter")
    _exact(lifecycle["rollback"], ROLLBACK_KEYS, "lifecycle.rollback")


def _validate_organization(value: Any, resources: set[str]) -> None:
    organization = _exact(value, ORGANIZATION_KEYS, "organization")
    expected = _build_organization(resources)
    if organization != expected:
        raise ImprovementError("organization dependency or ownership plan differs")
    _validate_dag(organization, set(organization["nodes"][3]["owned_resources"]) | {"evaluation/partitions", "decision/receipts", "promotion/pointer"})


def _validate_echoes(program: Mapping[str, Any]) -> None:
    _exact(program["program"], PROGRAM_KEYS, "output.program")
    _exact(program["intent"], INTENT_KEYS, "output.intent")
    _exact(program["baseline"], BASELINE_KEYS, "output.baseline")
    target = _exact(program["target"], TARGET_KEYS, "output.target")
    _id(program["program"]["tenant_id"], "output.program.tenant_id")
    _text(program["intent"]["objective"], "output.intent.objective")
    _text(program["baseline"]["artifact_id"], "output.baseline.artifact_id")
    if target["kind"] not in TARGET_KINDS:
        raise ImprovementError("output target kind is invalid")


def validate_program(program: Mapping[str, Any]) -> None:
    if not isinstance(program, dict):
        raise ImprovementError("program must be an object")
    _exact(program, PROGRAM_OUTPUT_KEYS, "program")
    if program["schema"] != PROGRAM_SCHEMA or program["activation_state"] != "planned" or program["executable"] is not False or program["execution_status"] != "blocked":
        raise ImprovementError("feature-off program must be planned and blocked")
    if not isinstance(program["request_sha256"], str) or not HEX64.fullmatch(program["request_sha256"]):
        raise ImprovementError("request digest is invalid")
    registries = _validate_registries()
    _validate_echoes(program)
    bindings = _exact(program["registry_bindings"], REGISTRY_BINDING_KEYS, "registry_bindings")
    expected_bindings = {
        "source_intelligence": {"registry_id": registries["source"]["registry_id"], "sha256": SOURCE_REGISTRY_SHA256, "record_count": 81},
        "mechanism_plane": {"registry_id": registries["mechanism"]["registry_id"], "sha256": MECHANISM_REGISTRY_SHA256, "destination_plane_count": 8, "source_group_count": 11, "decision_count": 81},
        "capability_catalog": {"catalog_id": registries["catalog"]["catalog_id"], "sha256": CAPABILITY_CATALOG_SHA256},
        "capability_review": {"registry_id": registries["capability"]["registry_id"], "sha256": CAPABILITY_REVIEW_SHA256, "accepted_count": 0, "candidate_count": 12},
        "evaluator_methods": {"registry_id": registries["evaluator"]["registry_id"], "sha256": EVALUATOR_REGISTRY_SHA256, "ready_adapter_count": 0, "method_count": 8},
    }
    for name, expected in expected_bindings.items():
        if _exact(bindings[name], set(expected), f"registry_bindings.{name}") != expected:
            raise ImprovementError(f"registry binding {name!r} differs")
    _validate_source_resolution(program["source_resolution"], registries)
    source_ids = program["source_resolution"]["requested_source_ids"]
    _validate_capability_resolution(program["capability_resolution"], registries)
    capability_ids = program["capability_resolution"]["requested_capability_ids"]
    _validate_evaluation_output(program["evaluation"], registries, program["request_sha256"])
    request_echo = {"schema": SCHEMA, "program": program["program"], "intent": program["intent"], "baseline": program["baseline"], "target": program["target"], "source_ids": source_ids, "capability_ids": capability_ids, "evaluation": {"artifact_classes": program["evaluation"]["artifact_classes"], "stages": program["evaluation"]["requested_stages"]}, "budgets": program["budgets"]}
    if digest_value(request_echo) != program["request_sha256"]:
        raise ImprovementError("request digest does not bind the echoed request")
    target_for_candidates = dict(program["target"])
    target_for_candidates.update({"_request_sha256": program["request_sha256"], "_baseline": program["baseline"], "_program": program["program"]})
    digests, resources = _validate_candidates(program["candidates"], program["evaluation"], capability_ids, target_for_candidates)
    if program["cohort_digest"] != digest_value(digests):
        raise ImprovementError("cohort digest does not verify")
    requirements = program["decision_receipt_requirements"]
    expected_requirements = _build_decision_receipt_requirements(program["candidates"])
    if not isinstance(requirements, list) or requirements != expected_requirements:
        raise ImprovementError("decision receipt requirements are missing, fabricated, or non-pending")
    for index, requirement in enumerate(requirements):
        _exact(requirement, RECEIPT_REQUIREMENT_KEYS, f"decision_receipt_requirements[{index}]")
        if requirement["status"] != "pending" or any(token in requirement for token in ("receipt", "signature", "evidence")):
            raise ImprovementError("decision receipt requirement claims completed evidence")
    _validate_organization(program["organization"], resources)
    budgets = _exact(program["budgets"], BUDGET_KEYS, "budgets")
    _validate_request_shape({"schema": SCHEMA, "program": program["program"], "intent": program["intent"], "baseline": program["baseline"], "target": program["target"], "source_ids": source_ids, "capability_ids": capability_ids, "evaluation": {"artifact_classes": program["evaluation"]["artifact_classes"], "stages": program["evaluation"]["requested_stages"]}, "budgets": budgets})
    _validate_lifecycle(program["lifecycle"], budgets)
    authority = _exact(program["authority"], AUTHORITY_KEYS, "authority")
    expected_authority = {"control_plane_id": "company-os-control-plane", "scheduler_id": "company-os-scheduler", "evaluator_registry_id": registries["evaluator"]["registry_id"], "promotion_registry_id": "company-os-promotion-registry", "promotion_authority_id": "company-os-promotion-authority", "external_effects_allowed": False}
    if authority != expected_authority:
        raise ImprovementError("authority binding differs")
    promotion = _exact(program["promotion"], PROMOTION_KEYS, "promotion")
    expected_promotion = {"registry_id": "company-os-promotion-registry", "current_pointer_digest": digest_value({"baseline": program["baseline"], "program": program["program"]}), "rollback_pointer_digest": digest_value({"rollback": program["baseline"], "program": program["program"]}), "atomicity_required": True, "authority_id": "company-os-promotion-authority", "delayed_outcome_required": True, "delayed_outcome_window_days": 30}
    if promotion != expected_promotion or promotion["current_pointer_digest"] == promotion["rollback_pointer_digest"]:
        raise ImprovementError("promotion or rollback binding differs")
    telemetry = _exact(program["telemetry"], TELEMETRY_KEYS, "telemetry")
    _exact(telemetry["requested"], TELEMETRY_REQUEST_KEYS, "telemetry.requested")
    if telemetry["observed"] is not None or telemetry["observed_evidence_ref"] is not None:
        raise ImprovementError("observed telemetry cannot be supplied")
    if program["side_effects"] != [] or program["warnings"] != ["observed runtime model, effort, tokens, and cost are intentionally unavailable"]:
        raise ImprovementError("feature-off side-effect or warning declaration differs")
    blockers = program["blockers"]
    if not isinstance(blockers, list) or [item.get("code") for item in blockers] != ["EVALUATOR_ADAPTERS_UNREADY", "CAPABILITIES_PENDING_ACCEPTANCE", "EXTERNAL_EFFECTS_DISABLED"]:
        raise ImprovementError("named blocker set is incomplete")
    expected_blockers = [
        {"code": "EVALUATOR_ADAPTERS_UNREADY", "reason": "evaluator registry contains zero ready adapters", "evidence": registries["evaluator"]["registry_id"]},
        {"code": "CAPABILITIES_PENDING_ACCEPTANCE", "reason": f"all {len(capability_ids)} requested external capabilities remain candidate_for_independent_acceptance", "evidence": registries["capability"]["registry_id"]},
        {"code": "EXTERNAL_EFFECTS_DISABLED", "reason": "feature-off compiler cannot authorize runtime, provider, or production effects", "evidence": "company-os-control-plane"},
    ]
    for index, blocker in enumerate(blockers):
        if _exact(blocker, BLOCKER_KEYS, f"blockers[{index}]") != expected_blockers[index]:
            raise ImprovementError("named blocker differs")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-output", type=Path)
    args = parser.parse_args(argv)
    if args.output and args.verify_output:
        parser.error("--output and --verify-output are mutually exclusive")
    try:
        raw_bytes = args.request.read_bytes()
        raw = json.loads(raw_bytes)
        if raw_bytes != canonical_bytes(raw):
            raise ImprovementError("request bytes must be canonical JSON")
        request = _validate_request_shape(raw)
        program = compile_program(request)
        payload = canonical_bytes(program)
        if args.verify_output:
            if args.verify_output.read_bytes() != payload:
                raise ImprovementError("compiled program does not match deterministic replay")
            print(json.dumps({"ok": True, "program_sha256": digest_value(program)}, sort_keys=True))
        elif args.output:
            args.output.write_bytes(payload)
        else:
            sys.stdout.buffer.write(payload)
        return 0
    except (OSError, json.JSONDecodeError, ImprovementError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
