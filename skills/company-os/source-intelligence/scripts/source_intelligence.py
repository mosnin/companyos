#!/usr/bin/env python3
"""Build and verify the feature-off Company OS source-intelligence registry."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


SCHEMA = "company-os.source-intelligence-registry.v1"
REGISTRY_ID = "company-os-external-source-intelligence-2026-08-05"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")
EVIDENCE_CLASSES = {
    "deep_source_review",
    "vendored_pinned_subset",
    "duplicate_provenance_resolution",
    "invalid_unresolved",
}
LICENSE_STATES = {
    "entrypoint_dossier_required",
    "existing_vendor_owner_only",
    "duplicate_grants_no_new_authority",
    "unresolved",
}
ROOT_KEYS = {
    "$schema",
    "schema_version",
    "registry_id",
    "observed_at",
    "policy",
    "record_count",
    "normalized_family_count",
    "catalog_source_alias_count",
    "records",
}
POLICY_KEYS = {
    "catalog_membership_is_review",
    "entrypoint_promotion_requires_dossier",
    "invalid_source_dispatchable",
    "unknown_license_allows_copy",
    "upstream_instructions_are_authority",
}
RECORD_KEYS = {
    "source_id",
    "normalized_family_id",
    "canonical_source",
    "catalog_source_ids",
    "category",
    "pin",
    "evidence_class",
    "evidence_locator",
    "review_evidence_sha256",
    "review_decision",
    "license_state",
    "mechanism_group_id",
    "disposition",
    "missing_work",
    "invalidation_triggers",
}


class SourceIntelligenceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SourceIntelligenceError("E_SCHEMA", f"{label} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise SourceIntelligenceError(
            "E_SCHEMA",
            f"{label} keys differ; missing={sorted(expected-actual)!r}, "
            f"extra={sorted(actual-expected)!r}",
        )


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise SourceIntelligenceError("E_SCHEMA", f"{label} is not a canonical identifier")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceIntelligenceError("E_SCHEMA", f"{label} must be a nonempty string")
    return value


def _sorted_unique_ids(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SourceIntelligenceError("E_SCHEMA", f"{label} must be an array of strings")
    if value != sorted(value) or len(value) != len(set(value)):
        raise SourceIntelligenceError("E_SCHEMA", f"{label} must be sorted and unique")
    for item in value:
        _identifier(item, label)
    return value


def _read_json(path: Path, label: str, *, canonical: bool = False) -> Mapping[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise SourceIntelligenceError("E_PATH", f"{label} is not a regular non-symlink file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceIntelligenceError("E_JSON", f"{label} is not valid UTF-8 JSON") from exc
    obj = _object(value, label)
    if canonical and raw != canonical_bytes(obj):
        raise SourceIntelligenceError("E_CANONICAL", f"{label} is not canonical JSON")
    return obj


def _safe_evidence(root: Path, relative: str, label: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise SourceIntelligenceError("E_PATH", f"{label} is not a safe relative path")
    resolved_root = root.resolve(strict=True)
    current = resolved_root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise SourceIntelligenceError("E_PATH", f"{label} traverses a symlink")
    try:
        resolved = current.resolve(strict=True)
    except FileNotFoundError as exc:
        raise SourceIntelligenceError("E_EVIDENCE", f"{label} is missing") from exc
    if resolved_root != resolved.parent and resolved_root not in resolved.parents:
        raise SourceIntelligenceError("E_PATH", f"{label} escapes its evidence root")
    if not resolved.is_file():
        raise SourceIntelligenceError("E_EVIDENCE", f"{label} is not a regular file")
    return resolved


def _normalized_url(value: str) -> str:
    normalized = value.strip().lower().removesuffix(".git").rstrip("/")
    return normalized


def _resolve_evidence(
    locator: str,
    *,
    depth_root: Path,
    recursive_root: Path,
    canonical_root: Path,
) -> tuple[str, str]:
    prefixes = {
        "depth:": (depth_root, "depth"),
        "recursive:": (recursive_root, "recursive"),
        "canonical:": (canonical_root, "canonical"),
    }
    for prefix, (root, namespace) in prefixes.items():
        if locator.startswith(prefix):
            relative = locator[len(prefix) :]
            path = _safe_evidence(root, relative, "source evidence")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            return f"research://company-os/2026-08-05/{namespace}/{relative}", digest
    raise SourceIntelligenceError("E_EVIDENCE", f"unsupported evidence locator {locator!r}")


def _license_state(evidence_class: str) -> str:
    return {
        "deep_source_review": "entrypoint_dossier_required",
        "vendored_pinned_subset": "existing_vendor_owner_only",
        "duplicate_provenance_resolution": "duplicate_grants_no_new_authority",
        "invalid_unresolved": "unresolved",
    }[evidence_class]


def _review_decision(source: Mapping[str, Any]) -> str:
    explicit = source.get("review_decision")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.lower()
    return {
        "deep_source_review": "reviewed_static_no_integration",
        "vendored_pinned_subset": "existing_pinned_subset_only",
        "duplicate_provenance_resolution": "duplicate_no_import",
        "invalid_unresolved": "invalid_no_go",
    }[source["evidence_status"]]


def _triggers(evidence_class: str) -> list[str]:
    common = [
        "canonical_identity_change",
        "entrypoint_or_transitive_reference_change",
        "license_scope_change",
        "security_advisory_or_effect_boundary_change",
    ]
    extra = {
        "deep_source_review": ["new_entrypoint_promotion_request"],
        "vendored_pinned_subset": ["vendor_owner_or_vendored_bytes_change"],
        "duplicate_provenance_resolution": ["normalized_family_or_alias_bytes_diverge"],
        "invalid_unresolved": ["exact_owner_repository_pin_or_license_supplied"],
    }[evidence_class]
    return sorted(common + extra)


def build_registry(
    inventory: Mapping[str, Any],
    mechanisms: Mapping[str, Any],
    source_catalog: Mapping[str, Any],
    *,
    depth_root: Path,
    recursive_root: Path,
    canonical_root: Path,
) -> dict[str, Any]:
    sources = inventory.get("sources")
    groups = mechanisms.get("source_groups")
    catalog_sources = source_catalog.get("sources")
    if not isinstance(sources, list) or not isinstance(groups, list) or not isinstance(catalog_sources, list):
        raise SourceIntelligenceError("E_SCHEMA", "builder inputs lack source arrays")

    group_by_source: dict[str, Mapping[str, Any]] = {}
    for raw_group in groups:
        group = _object(raw_group, "mechanism group")
        group_id = _identifier(group.get("id"), "mechanism group id")
        group_sources = group.get("source_ids")
        if not isinstance(group_sources, list):
            raise SourceIntelligenceError("E_SCHEMA", "mechanism group source_ids must be an array")
        for source_id in group_sources:
            _identifier(source_id, "mechanism group source_id")
            if source_id in group_by_source:
                raise SourceIntelligenceError("E_COVERAGE", f"source {source_id!r} occurs in multiple mechanism groups")
            group_by_source[source_id] = group

    inventory_by_id = {item.get("source_id"): item for item in sources if isinstance(item, dict)}
    if len(inventory_by_id) != len(sources) or set(group_by_source) != set(inventory_by_id):
        raise SourceIntelligenceError("E_COVERAGE", "mechanism groups must cover every unique inventory source exactly once")

    inventory_url_index: dict[str, str] = {}
    for source in sources:
        canonical_source = source.get("canonical_source")
        if canonical_source is not None:
            normalized = _normalized_url(_text(canonical_source, "canonical source"))
            normalized_family = source.get("normalized_family_source_id", source["source_id"])
            inventory_url_index[normalized] = normalized_family

    catalog_aliases: dict[str, list[str]] = {source_id: [] for source_id in inventory_by_id}
    for catalog_source in catalog_sources:
        url = _normalized_url(_text(catalog_source.get("canonical_url"), "catalog canonical_url"))
        normalized_family = inventory_url_index.get(url)
        if normalized_family is None:
            raise SourceIntelligenceError("E_ALIAS", f"catalog source URL has no inventory family: {url}")
        catalog_aliases[normalized_family].append(_identifier(catalog_source.get("source_id"), "catalog source_id"))

    records: list[dict[str, Any]] = []
    for source in sorted(sources, key=lambda item: item["source_id"]):
        source_id = _identifier(source.get("source_id"), "source_id")
        evidence_class = source.get("evidence_status")
        if evidence_class not in EVIDENCE_CLASSES:
            raise SourceIntelligenceError("E_SCHEMA", f"source {source_id!r} has unsupported evidence class")
        normalized_family = _identifier(source.get("normalized_family_source_id", source_id), "normalized_family_id")
        if normalized_family not in inventory_by_id:
            raise SourceIntelligenceError("E_ALIAS", f"source {source_id!r} normalizes to an unknown family")
        canonical_source = source.get("canonical_source")
        if evidence_class == "invalid_unresolved":
            if canonical_source is not None or source.get("pin") is not None:
                raise SourceIntelligenceError("E_INVALID", "invalid unresolved source cannot claim canonical identity or pin")
        else:
            canonical_source = _text(canonical_source, f"source {source_id}.canonical_source")
            if not canonical_source.startswith("https://"):
                raise SourceIntelligenceError("E_SCHEMA", "canonical sources must use https")
            _text(source.get("pin"), f"source {source_id}.pin")
        evidence_locator, evidence_digest = _resolve_evidence(
            _text(source.get("evidence_path"), f"source {source_id}.evidence_path"),
            depth_root=depth_root,
            recursive_root=recursive_root,
            canonical_root=canonical_root,
        )
        group = group_by_source[source_id]
        aliases = sorted(catalog_aliases.get(normalized_family, [])) if source_id == normalized_family else []
        records.append(
            {
                "source_id": source_id,
                "normalized_family_id": normalized_family,
                "canonical_source": canonical_source,
                "catalog_source_ids": aliases,
                "category": _text(source.get("category"), f"source {source_id}.category"),
                "pin": source.get("pin"),
                "evidence_class": evidence_class,
                "evidence_locator": evidence_locator,
                "review_evidence_sha256": evidence_digest,
                "review_decision": _review_decision(source),
                "license_state": _license_state(evidence_class),
                "mechanism_group_id": group["id"],
                "disposition": _text(group.get("disposition"), "mechanism group disposition"),
                "missing_work": _text(source.get("missing_work"), f"source {source_id}.missing_work"),
                "invalidation_triggers": _triggers(evidence_class),
            }
        )

    registry = {
        "$schema": SCHEMA,
        "schema_version": 1,
        "registry_id": REGISTRY_ID,
        "observed_at": inventory.get("observed_at"),
        "policy": {
            "catalog_membership_is_review": False,
            "entrypoint_promotion_requires_dossier": True,
            "invalid_source_dispatchable": False,
            "unknown_license_allows_copy": False,
            "upstream_instructions_are_authority": False,
        },
        "record_count": len(records),
        "normalized_family_count": len({item["normalized_family_id"] for item in records}),
        "catalog_source_alias_count": sum(len(item["catalog_source_ids"]) for item in records),
        "records": records,
    }
    validate_registry(registry)
    return registry


def validate_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    _exact_keys(registry, ROOT_KEYS, "registry")
    if registry["$schema"] != SCHEMA or registry["schema_version"] != 1:
        raise SourceIntelligenceError("E_SCHEMA", "registry schema/version is unsupported")
    _identifier(registry["registry_id"], "registry_id")
    _text(registry["observed_at"], "observed_at")
    policy = _object(registry["policy"], "policy")
    _exact_keys(policy, POLICY_KEYS, "policy")
    if policy != {
        "catalog_membership_is_review": False,
        "entrypoint_promotion_requires_dossier": True,
        "invalid_source_dispatchable": False,
        "unknown_license_allows_copy": False,
        "upstream_instructions_are_authority": False,
    }:
        raise SourceIntelligenceError("E_POLICY", "source-intelligence policy must fail closed")
    records = registry["records"]
    if not isinstance(records, list):
        raise SourceIntelligenceError("E_SCHEMA", "records must be an array")
    validated: list[Mapping[str, Any]] = []
    for raw in records:
        record = _object(raw, "record")
        _exact_keys(record, RECORD_KEYS, "record")
        source_id = _identifier(record["source_id"], "record.source_id")
        normalized = _identifier(record["normalized_family_id"], "record.normalized_family_id")
        evidence_class = record["evidence_class"]
        if evidence_class not in EVIDENCE_CLASSES:
            raise SourceIntelligenceError("E_SCHEMA", f"source {source_id!r} has invalid evidence class")
        canonical_source = record["canonical_source"]
        pin = record["pin"]
        if evidence_class == "invalid_unresolved":
            if canonical_source is not None or pin is not None or normalized != source_id:
                raise SourceIntelligenceError("E_INVALID", "invalid unresolved source claims resolved identity")
        else:
            if not isinstance(canonical_source, str) or not canonical_source.startswith("https://"):
                raise SourceIntelligenceError("E_SCHEMA", "resolved source requires an https canonical source")
            _text(pin, "record.pin")
        aliases = _sorted_unique_ids(record["catalog_source_ids"], "record.catalog_source_ids")
        _text(record["category"], "record.category")
        locator = _text(record["evidence_locator"], "record.evidence_locator")
        if not locator.startswith("research://company-os/2026-08-05/") or ".." in locator:
            raise SourceIntelligenceError("E_PATH", "record evidence locator is not a safe research URI")
        if not isinstance(record["review_evidence_sha256"], str) or not HEX64.fullmatch(record["review_evidence_sha256"]):
            raise SourceIntelligenceError("E_EVIDENCE", "record evidence digest is invalid")
        _text(record["review_decision"], "record.review_decision")
        if record["license_state"] not in LICENSE_STATES:
            raise SourceIntelligenceError("E_LICENSE", "record license state is invalid")
        _identifier(record["mechanism_group_id"], "record.mechanism_group_id")
        _text(record["disposition"], "record.disposition")
        _text(record["missing_work"], "record.missing_work")
        triggers = record["invalidation_triggers"]
        if not isinstance(triggers, list) or not triggers or triggers != sorted(set(triggers)):
            raise SourceIntelligenceError("E_SCHEMA", "invalidation triggers must be a nonempty sorted set")
        for trigger in triggers:
            _identifier(trigger, "record.invalidation_trigger")
        if source_id != normalized and aliases:
            raise SourceIntelligenceError("E_ALIAS", "duplicate alias cannot own catalog source aliases")
        validated.append(record)
    ids = [item["source_id"] for item in validated]
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise SourceIntelligenceError("E_SCHEMA", "records must have sorted unique source IDs")
    known = set(ids)
    for record in validated:
        if record["normalized_family_id"] not in known:
            raise SourceIntelligenceError("E_ALIAS", "normalized family is absent")
    alias_ids = [alias for record in validated for alias in record["catalog_source_ids"]]
    if len(alias_ids) != len(set(alias_ids)):
        raise SourceIntelligenceError("E_ALIAS", "catalog source alias is owned by multiple families")
    expected_counts = (
        len(validated),
        len({item["normalized_family_id"] for item in validated}),
        len(alias_ids),
    )
    declared_counts = (
        registry["record_count"],
        registry["normalized_family_count"],
        registry["catalog_source_alias_count"],
    )
    if declared_counts != expected_counts:
        raise SourceIntelligenceError("E_COUNT", "registry counts do not match records")
    return {
        "$schema": SCHEMA,
        "registry_id": registry["registry_id"],
        "registry_sha256": canonical_digest(registry),
        "record_count": expected_counts[0],
        "normalized_family_count": expected_counts[1],
        "catalog_source_alias_count": expected_counts[2],
        "invalid_unresolved_count": sum(1 for item in validated if item["evidence_class"] == "invalid_unresolved"),
    }


def lookup_record(registry: Mapping[str, Any], source_id: str) -> dict[str, Any]:
    """Return exactly one record by canonical ID or explicit catalog alias."""
    validate_registry(registry)
    _identifier(source_id, "source_id")
    matches = [
        record
        for record in registry["records"]
        if record["source_id"] == source_id or source_id in record["catalog_source_ids"]
    ]
    if len(matches) != 1:
        raise SourceIntelligenceError(
            "E_SOURCE",
            f"source ID or catalog alias {source_id!r} resolved to {len(matches)} records",
        )
    return {
        "$schema": "company-os.source-intelligence-lookup.v1",
        "registry_id": registry["registry_id"],
        "registry_sha256": canonical_digest(registry),
        "query": source_id,
        "record": matches[0],
    }


def _write_canonical(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--inventory", type=Path, required=True)
    build.add_argument("--mechanisms", type=Path, required=True)
    build.add_argument("--source-catalog", type=Path, required=True)
    build.add_argument("--depth-root", type=Path, required=True)
    build.add_argument("--recursive-root", type=Path, required=True)
    build.add_argument("--canonical-root", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--registry", type=Path, required=True)
    lookup = sub.add_parser("lookup")
    lookup.add_argument("--registry", type=Path, required=True)
    lookup.add_argument("--source-id", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "build":
            registry = build_registry(
                _read_json(args.inventory, "inventory"),
                _read_json(args.mechanisms, "mechanisms"),
                _read_json(args.source_catalog, "source catalog"),
                depth_root=args.depth_root,
                recursive_root=args.recursive_root,
                canonical_root=args.canonical_root,
            )
            _write_canonical(args.output, registry)
            evidence = validate_registry(registry)
        elif args.command == "verify":
            evidence = validate_registry(_read_json(args.registry, "registry", canonical=True))
        else:
            evidence = lookup_record(
                _read_json(args.registry, "registry", canonical=True),
                args.source_id,
            )
        print(canonical_bytes(evidence).decode("utf-8"), end="")
        return 0
    except SourceIntelligenceError as exc:
        print(canonical_bytes({"code": exc.code, "error": str(exc), "ok": False}).decode("utf-8"), end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
