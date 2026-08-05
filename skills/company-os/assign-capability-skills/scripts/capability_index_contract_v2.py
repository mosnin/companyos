#!/usr/bin/env python3
"""Executable exact-key contract for company-os.capability-index-row.v2.

This is a dependency-free architecture fixture, not a production registry.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime


class ContractError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


ROW_KEYS = {
    "$schema", "schema_version", "capability_id", "capability_version", "aliases",
    "capability_kind", "source", "materialization", "classification", "activation",
    "trust", "freshness", "evaluation", "context",
}
SOURCE_KEYS = {
    "requested_url", "redirect_chain", "canonical_forge_id", "canonical_url",
    "source_commit", "source_tree", "source_commit_at", "upstream_forge_id",
    "upstream_url", "upstream_commit", "observed_at",
}
MATERIALIZATION_KEYS = {
    "mode", "transform_id", "transform_version", "transform_receipt_sha256",
    "original_entrypoint_sha256", "materialized_package_sha256",
    "entrypoint_resource_id", "companion_policy", "resources",
}
RESOURCE_KEYS = {
    "resource_id", "path", "kind", "sha256", "bytes", "load_when", "license_spdx",
    "license_evidence_path", "redistribution",
}
CLASSIFICATION_KEYS = {
    "domains", "produces_artifacts", "reviews_artifacts", "consumes_artifacts",
    "reviewer_capabilities", "lifecycle_phases", "intents", "named_technologies",
    "modalities",
}
ACTIVATION_KEYS = {
    "roles", "positive_trigger_dnf", "negative_triggers", "required_permissions",
    "prerequisites", "requires_capability_ids", "provides_prerequisite_ids",
    "network_mode", "allowed_hosts", "data_egress", "sensitivity_ceiling",
    "side_effects", "controller_effect", "conflicts", "composes_before", "composes_after",
}
PREDICATE_KEYS = {"field", "op", "value"}
PREREQUISITE_KEYS = {"prerequisite_id", "kind", "constraint", "availability_source", "required"}
TRUST_KEYS = {
    "state", "provenance_tier", "publisher_identity", "source_lineage", "integrity",
    "signature", "scan", "human_review", "risk_flags",
}
EVIDENCE_KEYS = {
    "status", "evidence_class", "enforcement", "reviewer_or_issuer", "observed_at",
    "evidence_sha256",
}
FRESHNESS_KEYS = {"last_revalidated_at", "stale_after_days", "next_review_at", "supersedes"}
EVALUATION_KEYS = {
    "evaluation_class", "independence", "enforcement", "suite_version", "suite_ids",
    "scenario_ids", "passed", "failed", "last_run_at", "stale_after_days", "evidence_sha256",
}
CONTEXT_KEYS = {
    "summary", "context_accounting_id", "metadata_context_units", "max_loaded_bytes", "max_loaded_context_units",
    "load_policy", "section_index",
}
SECTION_KEYS = {"section_id", "resource_id", "start_byte", "end_byte", "load_when"}
PUBLISHER_IDENTITY_KEYS = EVIDENCE_KEYS | {"publisher_id"}
TASK_KEYS = {
    "$schema", "schema_version", "program_id", "packet_id", "parent_packet_id", "role",
    "controller_id", "decision_as_of", "coverage_atoms", "typed_features", "authority",
    "policy", "prohibitions", "mandatory_requirements",
}
TASK_FEATURE_KEYS = {
    "domains", "artifact_produces", "artifact_reviews", "named_technologies",
    "lifecycle_phases", "intents", "reviewer_capabilities",
}
TASK_AUTHORITY_KEYS = {
    "allowed_permissions", "available_prerequisites", "network_mode", "allowed_hosts",
    "data_egress_ceiling", "sensitivity_ceiling", "write_scopes", "allowed_side_effects",
    "license_use_mode",
}
TASK_PREREQUISITE_KEYS = {
    "prerequisite_id", "kind", "version_or_constraint", "availability_source", "available",
}
TASK_POLICY_KEYS = {
    "risk_tier", "max_freshness_days", "minimum_evaluation_class",
    "minimum_evaluation_independence", "minimum_evaluation_enforcement", "max_skills",
    "max_closed_resource_bytes", "context_accounting_id", "max_context_cost_units",
}
SNAPSHOT_KEYS = {
    "$schema", "schema_version", "policy_version", "generated_at", "source_pins", "rows",
    "inverted_indices", "snapshot_sha256",
}
SOURCE_PIN_KEYS = {
    "source_id", "canonical_forge_id", "source_commit", "source_tree", "observed_at",
}

CAPABILITY_KINDS = {
    "advisory_instruction", "artifact_producer", "artifact_reviewer", "deterministic_adapter",
    "connector", "workflow_orchestrator", "controller_like",
}
MATERIALIZATION_MODES = {
    "host_native", "bound_external", "reviewed_wrapper", "reference_only", "deterministic_adapter",
}
RESOURCE_KINDS = {"entrypoint", "reference", "script", "asset", "template", "manifest"}
REDISTRIBUTION = {"allowed", "unknown", "prohibited", "not_applicable"}
PREREQUISITE_KINDS = {"tool", "runtime", "credential", "input", "service", "artifact", "policy"}
NETWORK_MODES = {"none", "allowlisted_read", "allowlisted_write"}
EGRESS = {"none", "metadata_only", "content"}
SENSITIVITY = {"public", "internal", "confidential", "restricted"}
SIDE_EFFECTS = {
    "advisory", "local_read", "local_write", "external_read", "external_write", "deploy",
    "spend", "contact", "delegate", "publish", "global_config_write", "service_start",
}
CONTROLLER_EFFECTS = {"none", "workflow_only", "spawn", "schedule", "approve", "replace"}
TRUST_STATES = {"approved", "reference_only", "quarantine", "rejected"}
PROVENANCE = {"internal_reviewed", "vendored_reviewed", "external_verified"}
EVIDENCE_STATUS = {"pass", "fail", "unknown", "not_applicable"}
EVIDENCE_CLASSES = {"source_code", "publisher_assertion", "user_report", "independent_review", "inference"}
ENFORCEMENT = {"hard_gate", "advisory", "none"}
EVALUATION_CLASSES = {"none", "static_contract", "scenario", "independent_scenario"}
INDEPENDENCE = {"maintainer", "independent", "mixed"}
CONTEXT_ACCOUNTING_ID = "company-os-utf8-byteceil4-v1"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:/-]*$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def _exact(obj: dict, keys: set[str]) -> None:
    if not isinstance(obj, dict) or set(obj) != keys:
        raise ContractError("E_SCHEMA_EXACT_KEYS")


def _enum(value: str, allowed: set[str]) -> None:
    if value not in allowed:
        raise ContractError("E_SCHEMA_ENUM")


def normalize_scalar(value: str) -> str:
    if not isinstance(value, str):
        raise ContractError("E_TRIGGER_TYPE")
    return unicodedata.normalize("NFC", value).casefold()


def _sorted_unique(values: list[str], *, ids: bool = False) -> None:
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ContractError("E_SCHEMA_TYPE")
    normalized = [normalize_scalar(value) for value in values]
    if normalized != sorted(normalized) or len(normalized) != len(set(normalized)):
        raise ContractError("E_SCHEMA_CANONICAL_SET")
    if ids and any(not ID_RE.fullmatch(value) for value in values):
        raise ContractError("E_SCHEMA_ID")


def _digest(value: str | None) -> None:
    if value is not None and (not isinstance(value, str) or not HEX64_RE.fullmatch(value)):
        raise ContractError("E_SCHEMA_DIGEST")


def _required_digest(value: str) -> None:
    if not isinstance(value, str) or not HEX64_RE.fullmatch(value):
        raise ContractError("E_SCHEMA_DIGEST")


def _nonempty_string(value: object, code: str = "E_SCHEMA_TYPE") -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(code)
    return value


def _nonnegative_int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ContractError("E_SCHEMA_TYPE")
    return value


def _rfc3339(value: object) -> datetime:
    if not isinstance(value, str):
        raise ContractError("E_SCHEMA_TIMESTAMP")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ContractError("E_SCHEMA_TIMESTAMP") from error
    if parsed.tzinfo is None:
        raise ContractError("E_SCHEMA_TIMESTAMP")
    return parsed


def deterministic_context_units(byte_count: int, accounting_id: str = CONTEXT_ACCOUNTING_ID) -> int:
    if accounting_id != CONTEXT_ACCOUNTING_ID or not isinstance(byte_count, int) or byte_count < 0:
        raise ContractError("E_CONTEXT_ACCOUNTING")
    return (byte_count + 3) // 4


def _validate_predicate(predicate: dict) -> None:
    _exact(predicate, PREDICATE_KEYS)
    if not isinstance(predicate["field"], str) or not predicate["field"]:
        raise ContractError("E_TRIGGER_FIELD")
    _enum(predicate["op"], {"eq", "in", "contains", "present"})
    value = predicate["value"]
    if predicate["op"] == "present":
        if value is not None:
            raise ContractError("E_TRIGGER_TYPE")
    elif predicate["op"] == "in":
        _sorted_unique(value)
        if not value:
            raise ContractError("E_TRIGGER_TYPE")
    elif not isinstance(value, str):
        raise ContractError("E_TRIGGER_TYPE")


def _validate_dnf(dnf: list[list[dict]]) -> None:
    if not isinstance(dnf, list) or not dnf:
        raise ContractError("E_TRIGGER_DNF")
    for clause in dnf:
        if not isinstance(clause, list) or not clause:
            raise ContractError("E_TRIGGER_DNF")
        for predicate in clause:
            _validate_predicate(predicate)


def predicate_matches(task_features: dict, predicate: dict) -> bool:
    _validate_predicate(predicate)
    field = predicate["field"]
    if field not in task_features:
        raise ContractError("E_TRIGGER_FIELD")
    actual = task_features[field]
    op = predicate["op"]
    if op == "present":
        return actual is not None and actual != "" and actual != []
    if op == "eq":
        if not isinstance(actual, str):
            raise ContractError("E_TRIGGER_TYPE")
        return normalize_scalar(actual) == normalize_scalar(predicate["value"])
    if op == "in":
        if not isinstance(actual, str):
            raise ContractError("E_TRIGGER_TYPE")
        return normalize_scalar(actual) in {normalize_scalar(value) for value in predicate["value"]}
    if not isinstance(actual, list):
        raise ContractError("E_TRIGGER_TYPE")
    return normalize_scalar(predicate["value"]) in {normalize_scalar(value) for value in actual}


def dnf_matches(task_features: dict, dnf: list[list[dict]]) -> bool:
    _validate_dnf(dnf)
    return any(all(predicate_matches(task_features, predicate) for predicate in clause) for clause in dnf)


def _validate_evidence(value: dict) -> None:
    _exact(value, EVIDENCE_KEYS)
    _enum(value["status"], EVIDENCE_STATUS)
    _enum(value["evidence_class"], EVIDENCE_CLASSES)
    _enum(value["enforcement"], ENFORCEMENT)
    _nonempty_string(value["reviewer_or_issuer"])
    _rfc3339(value["observed_at"])
    _required_digest(value["evidence_sha256"])


def _validate_publisher_identity(value: dict) -> None:
    _exact(value, PUBLISHER_IDENTITY_KEYS)
    if not ID_RE.fullmatch(_nonempty_string(value["publisher_id"])):
        raise ContractError("E_SCHEMA_ID")
    evidence_value = {key: value[key] for key in EVIDENCE_KEYS}
    _validate_evidence(evidence_value)


def validate_row(row: dict) -> None:
    _exact(row, ROW_KEYS)
    if row["$schema"] != "company-os.capability-index-row.v2" or row["schema_version"] != 2:
        raise ContractError("E_SCHEMA_VERSION")
    if not ID_RE.fullmatch(row["capability_id"]):
        raise ContractError("E_SCHEMA_ID")
    _nonempty_string(row["capability_version"])
    _sorted_unique(row["aliases"], ids=True)
    _enum(row["capability_kind"], CAPABILITY_KINDS)

    source = row["source"]
    _exact(source, SOURCE_KEYS)
    for key in ("requested_url", "canonical_forge_id", "canonical_url"):
        _nonempty_string(source[key])
    if not isinstance(source["redirect_chain"], list) or any(not isinstance(value, str) or not value for value in source["redirect_chain"]):
        raise ContractError("E_SCHEMA_TYPE")
    for key in ("source_commit", "source_tree", "upstream_commit"):
        value = source[key]
        if value is not None and not re.fullmatch(r"[0-9a-f]{40}", value):
            raise ContractError("E_SCHEMA_SOURCE_PIN")
    for key in ("source_commit_at", "observed_at"):
        _rfc3339(source[key])
    upstream_values = [source["upstream_forge_id"], source["upstream_url"], source["upstream_commit"]]
    if any(value is None for value in upstream_values) and not all(value is None for value in upstream_values):
        raise ContractError("E_SCHEMA_UPSTREAM_IDENTITY")
    for value in upstream_values[:2]:
        if value is not None:
            _nonempty_string(value)

    materialization = row["materialization"]
    _exact(materialization, MATERIALIZATION_KEYS)
    _enum(materialization["mode"], MATERIALIZATION_MODES)
    if materialization["companion_policy"] not in {"closed", "reference_only"}:
        raise ContractError("E_SCHEMA_ENUM")
    _required_digest(materialization["original_entrypoint_sha256"])
    _required_digest(materialization["materialized_package_sha256"])
    if materialization["mode"] in {"reviewed_wrapper", "deterministic_adapter"}:
        _nonempty_string(materialization["transform_id"])
        _nonempty_string(materialization["transform_version"])
        _required_digest(materialization["transform_receipt_sha256"])
    else:
        for key in ("transform_id", "transform_version", "transform_receipt_sha256"):
            if materialization[key] is not None:
                raise ContractError("E_SCHEMA_MATERIALIZATION")
    resource_ids: list[str] = []
    for resource in materialization["resources"]:
        _exact(resource, RESOURCE_KEYS)
        resource_ids.append(resource["resource_id"])
        if not ID_RE.fullmatch(resource["resource_id"]):
            raise ContractError("E_SCHEMA_ID")
        if not isinstance(resource["path"], str) or resource["path"].startswith("/") or ".." in resource["path"].split("/"):
            raise ContractError("E_MATERIALIZATION_CLOSURE")
        _enum(resource["kind"], RESOURCE_KINDS)
        _required_digest(resource["sha256"])
        _nonnegative_int(resource["bytes"])
        _validate_dnf(resource["load_when"])
        _nonempty_string(resource["license_spdx"])
        if resource["license_evidence_path"] is not None:
            _nonempty_string(resource["license_evidence_path"])
        if resource["redistribution"] == "allowed" and resource["license_evidence_path"] is None:
            raise ContractError("E_LICENSE_RESOURCE_CONFLICT")
        _enum(resource["redistribution"], REDISTRIBUTION)
    if resource_ids != sorted(resource_ids) or len(resource_ids) != len(set(resource_ids)):
        raise ContractError("E_SCHEMA_CANONICAL_SET")
    if materialization["entrypoint_resource_id"] not in resource_ids:
        raise ContractError("E_MATERIALIZATION_CLOSURE")

    classification = row["classification"]
    _exact(classification, CLASSIFICATION_KEYS)
    for value in classification.values():
        _sorted_unique(value)

    activation = row["activation"]
    _exact(activation, ACTIVATION_KEYS)
    _validate_dnf(activation["positive_trigger_dnf"])
    for predicate in activation["negative_triggers"]:
        _validate_predicate(predicate)
    for key in (
        "roles", "required_permissions", "requires_capability_ids", "provides_prerequisite_ids",
        "allowed_hosts", "side_effects", "conflicts", "composes_before", "composes_after",
    ):
        _sorted_unique(activation[key], ids=key in {"requires_capability_ids", "provides_prerequisite_ids", "conflicts", "composes_before", "composes_after"})
    if not set(activation["side_effects"]) <= SIDE_EFFECTS:
        raise ContractError("E_SCHEMA_ENUM")
    _enum(activation["network_mode"], NETWORK_MODES)
    _enum(activation["data_egress"], EGRESS)
    _enum(activation["sensitivity_ceiling"], SENSITIVITY)
    _enum(activation["controller_effect"], CONTROLLER_EFFECTS)
    for prerequisite in activation["prerequisites"]:
        _exact(prerequisite, PREREQUISITE_KEYS)
        if not ID_RE.fullmatch(_nonempty_string(prerequisite["prerequisite_id"])):
            raise ContractError("E_SCHEMA_ID")
        _enum(prerequisite["kind"], PREREQUISITE_KINDS)
        _nonempty_string(prerequisite["constraint"])
        _nonempty_string(prerequisite["availability_source"])
        if not isinstance(prerequisite["required"], bool):
            raise ContractError("E_SCHEMA_TYPE")

    trust = row["trust"]
    _exact(trust, TRUST_KEYS)
    _enum(trust["state"], TRUST_STATES)
    _enum(trust["provenance_tier"], PROVENANCE)
    _validate_publisher_identity(trust["publisher_identity"])
    for key in ("source_lineage", "integrity", "signature", "scan", "human_review"):
        _validate_evidence(trust[key])
    _sorted_unique(trust["risk_flags"])

    freshness = row["freshness"]
    _exact(freshness, FRESHNESS_KEYS)
    last_revalidated = _rfc3339(freshness["last_revalidated_at"])
    _nonnegative_int(freshness["stale_after_days"])
    next_review = _rfc3339(freshness["next_review_at"])
    if next_review < last_revalidated:
        raise ContractError("E_SCHEMA_TIMESTAMP_ORDER")
    _sorted_unique(freshness["supersedes"], ids=True)

    evaluation = row["evaluation"]
    _exact(evaluation, EVALUATION_KEYS)
    _enum(evaluation["evaluation_class"], EVALUATION_CLASSES)
    _enum(evaluation["independence"], INDEPENDENCE)
    _enum(evaluation["enforcement"], ENFORCEMENT)
    _nonempty_string(evaluation["suite_version"])
    _sorted_unique(evaluation["suite_ids"], ids=True)
    _sorted_unique(evaluation["scenario_ids"], ids=True)
    _nonnegative_int(evaluation["passed"])
    _nonnegative_int(evaluation["failed"])
    _rfc3339(evaluation["last_run_at"])
    _nonnegative_int(evaluation["stale_after_days"])
    _required_digest(evaluation["evidence_sha256"])

    context = row["context"]
    _exact(context, CONTEXT_KEYS)
    _nonempty_string(context["summary"])
    if context["context_accounting_id"] != CONTEXT_ACCOUNTING_ID:
        raise ContractError("E_CONTEXT_ACCOUNTING")
    for key in ("metadata_context_units", "max_loaded_bytes", "max_loaded_context_units"):
        _nonnegative_int(context[key])
    _enum(context["load_policy"], {"metadata_only", "metadata_then_closed_resources", "closed_resources"})
    if not isinstance(context["section_index"], list):
        raise ContractError("E_SCHEMA_TYPE")
    section_ids: list[str] = []
    resource_id_set = set(resource_ids)
    for section in context["section_index"]:
        _exact(section, SECTION_KEYS)
        section_ids.append(section["section_id"])
        if not ID_RE.fullmatch(_nonempty_string(section["section_id"])):
            raise ContractError("E_SCHEMA_ID")
        if section["resource_id"] not in resource_id_set:
            raise ContractError("E_MATERIALIZATION_CLOSURE")
        start = _nonnegative_int(section["start_byte"])
        end = _nonnegative_int(section["end_byte"])
        if end <= start:
            raise ContractError("E_SCHEMA_SECTION_RANGE")
        _validate_dnf(section["load_when"])
    if section_ids != sorted(section_ids) or len(section_ids) != len(set(section_ids)):
        raise ContractError("E_SCHEMA_CANONICAL_SET")


def validate_task(task: dict) -> None:
    _exact(task, TASK_KEYS)
    if task["$schema"] != "company-os.capability-routing-task.v2" or task["schema_version"] != 2:
        raise ContractError("E_SCHEMA_VERSION")
    for key in ("program_id", "packet_id", "parent_packet_id", "controller_id"):
        if not ID_RE.fullmatch(_nonempty_string(task[key])):
            raise ContractError("E_SCHEMA_ID")
    _enum(task["role"], {"manager", "worker"})
    _rfc3339(task["decision_as_of"])
    _sorted_unique(task["coverage_atoms"], ids=True)
    if not task["coverage_atoms"]:
        raise ContractError("E_REQUIRED_CAPABILITY_UNAVAILABLE")
    features = task["typed_features"]
    _exact(features, TASK_FEATURE_KEYS)
    for values in features.values():
        _sorted_unique(values)
    authority = task["authority"]
    _exact(authority, TASK_AUTHORITY_KEYS)
    for key in ("allowed_permissions", "allowed_hosts", "write_scopes", "allowed_side_effects"):
        _sorted_unique(authority[key])
    if not set(authority["allowed_side_effects"]) <= SIDE_EFFECTS:
        raise ContractError("E_SCHEMA_ENUM")
    _enum(authority["network_mode"], NETWORK_MODES)
    _enum(authority["data_egress_ceiling"], EGRESS)
    _enum(authority["sensitivity_ceiling"], SENSITIVITY)
    _enum(authority["license_use_mode"], {"reference_only", "internal_use", "vendor_redistribute", "external_distribution"})
    prerequisite_ids: list[str] = []
    for prerequisite in authority["available_prerequisites"]:
        _exact(prerequisite, TASK_PREREQUISITE_KEYS)
        prerequisite_ids.append(prerequisite["prerequisite_id"])
        if not ID_RE.fullmatch(_nonempty_string(prerequisite["prerequisite_id"])):
            raise ContractError("E_SCHEMA_ID")
        _enum(prerequisite["kind"], PREREQUISITE_KINDS)
        _nonempty_string(prerequisite["version_or_constraint"])
        _nonempty_string(prerequisite["availability_source"])
        if not isinstance(prerequisite["available"], bool):
            raise ContractError("E_SCHEMA_TYPE")
    if prerequisite_ids != sorted(prerequisite_ids) or len(prerequisite_ids) != len(set(prerequisite_ids)):
        raise ContractError("E_SCHEMA_CANONICAL_SET")
    policy = task["policy"]
    _exact(policy, TASK_POLICY_KEYS)
    _enum(policy["risk_tier"], {"low", "medium", "high", "critical"})
    _nonnegative_int(policy["max_freshness_days"])
    _enum(policy["minimum_evaluation_class"], EVALUATION_CLASSES)
    _enum(policy["minimum_evaluation_independence"], INDEPENDENCE)
    _enum(policy["minimum_evaluation_enforcement"], ENFORCEMENT)
    if not isinstance(policy["max_skills"], int) or isinstance(policy["max_skills"], bool) or not 1 <= policy["max_skills"] <= 4:
        raise ContractError("E_SCHEMA_TYPE")
    _nonnegative_int(policy["max_closed_resource_bytes"])
    if policy["context_accounting_id"] != CONTEXT_ACCOUNTING_ID:
        raise ContractError("E_CONTEXT_ACCOUNTING")
    _nonnegative_int(policy["max_context_cost_units"])
    _sorted_unique(task["prohibitions"])
    _sorted_unique(task["mandatory_requirements"])


def validate_snapshot(snapshot: dict) -> None:
    _exact(snapshot, SNAPSHOT_KEYS)
    if snapshot["$schema"] != "company-os.capability-index-snapshot.v2" or snapshot["schema_version"] != 2:
        raise ContractError("E_SCHEMA_VERSION")
    _nonempty_string(snapshot["policy_version"])
    _rfc3339(snapshot["generated_at"])
    source_ids: list[str] = []
    for source_pin in snapshot["source_pins"]:
        _exact(source_pin, SOURCE_PIN_KEYS)
        source_ids.append(source_pin["source_id"])
        for key in ("source_id", "canonical_forge_id"):
            if not ID_RE.fullmatch(_nonempty_string(source_pin[key])):
                raise ContractError("E_SCHEMA_ID")
        for key in ("source_commit", "source_tree"):
            if not re.fullmatch(r"[0-9a-f]{40}", _nonempty_string(source_pin[key])):
                raise ContractError("E_SCHEMA_SOURCE_PIN")
        _rfc3339(source_pin["observed_at"])
    if source_ids != sorted(source_ids) or len(source_ids) != len(set(source_ids)):
        raise ContractError("E_SCHEMA_CANONICAL_SET")
    if not isinstance(snapshot["rows"], list):
        raise ContractError("E_SCHEMA_TYPE")
    row_ids: list[str] = []
    for row in snapshot["rows"]:
        validate_row(row)
        row_ids.append(row["capability_id"])
    if row_ids != sorted(row_ids) or len(row_ids) != len(set(row_ids)):
        raise ContractError("E_SCHEMA_CANONICAL_SET")
    if not isinstance(snapshot["inverted_indices"], dict):
        raise ContractError("E_SCHEMA_TYPE")
    for atom, capability_ids in snapshot["inverted_indices"].items():
        if not ID_RE.fullmatch(atom):
            raise ContractError("E_SCHEMA_ID")
        _sorted_unique(capability_ids, ids=True)
        if not set(capability_ids) <= set(row_ids):
            raise ContractError("E_SCHEMA_INDEX_BINDING")
    _required_digest(snapshot["snapshot_sha256"])
