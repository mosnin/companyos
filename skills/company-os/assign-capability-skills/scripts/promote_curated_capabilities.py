#!/usr/bin/env python3
"""Promote independently written wrappers into a generated source catalog."""

from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

import capability_catalog as catalog_contract


CURATION_SCHEMA = "company-os.capability-curation.v1"
CURATION_KEYS = {"$schema", "schema_version", "curation_id", "capabilities"}
ENTRY_KEYS = {
    "capability_id",
    "name",
    "description",
    "source_id",
    "upstream_skill_path",
    "entrypoint",
    "roles",
    "domains",
    "tags",
    "required_permissions",
    "conflicts",
}


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise catalog_contract.CatalogError(
            "E_SCHEMA",
            f"{label} keys differ; missing={sorted(expected - actual)!r}, extra={sorted(actual - expected)!r}",
        )


def _validate_curation(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    _exact_keys(value, CURATION_KEYS, "curation")
    if value["$schema"] != CURATION_SCHEMA or value["schema_version"] != 1:
        raise catalog_contract.CatalogError("E_SCHEMA", "curation schema/version is unsupported")
    catalog_contract._id(value["curation_id"], "curation.curation_id")
    if not isinstance(value["capabilities"], list) or not value["capabilities"]:
        raise catalog_contract.CatalogError("E_SCHEMA", "curation.capabilities must be a nonempty array")
    entries: list[dict[str, Any]] = []
    for raw_entry in value["capabilities"]:
        entry = dict(catalog_contract._object(raw_entry, "curation capability"))
        _exact_keys(entry, ENTRY_KEYS, "curation capability")
        capability_id = catalog_contract._id(entry["capability_id"], "curation capability.capability_id")
        catalog_contract._string(entry["name"], f"curation {capability_id}.name", maximum=96)
        catalog_contract._string(entry["description"], f"curation {capability_id}.description", maximum=280)
        catalog_contract._id(entry["source_id"], f"curation {capability_id}.source_id")
        catalog_contract._relative_path(
            entry["upstream_skill_path"], f"curation {capability_id}.upstream_skill_path"
        )
        catalog_contract._relative_path(
            entry["entrypoint"], f"curation {capability_id}.entrypoint", required_prefix="vendor"
        )
        catalog_contract._sorted_unique_strings(
            entry["roles"], f"curation {capability_id}.roles", allowed=catalog_contract.ROLES, nonempty=True
        )
        catalog_contract._sorted_unique_strings(
            entry["domains"],
            f"curation {capability_id}.domains",
            pattern=catalog_contract.PERMISSION_RE,
            nonempty=True,
        )
        catalog_contract._sorted_unique_strings(
            entry["tags"],
            f"curation {capability_id}.tags",
            pattern=catalog_contract.PERMISSION_RE,
            nonempty=True,
        )
        catalog_contract._sorted_unique_strings(
            entry["required_permissions"],
            f"curation {capability_id}.required_permissions",
            pattern=catalog_contract.PERMISSION_RE,
        )
        catalog_contract._sorted_unique_strings(
            entry["conflicts"],
            f"curation {capability_id}.conflicts",
            pattern=catalog_contract.ID_RE,
        )
        entries.append(entry)
    ids = [entry["capability_id"] for entry in entries]
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise catalog_contract.CatalogError("E_SCHEMA", "curation capability IDs must be unique and sorted")
    return entries


def _validate_wrapper_entrypoint(
    path: Path, capability_id: str
) -> bytes:
    if path.name != "SKILL.md" or path.parent.name != capability_id:
        raise catalog_contract.CatalogError(
            "E_ENTRYPOINT",
            f"curated capability {capability_id!r} must use vendor/.../{capability_id}/SKILL.md",
        )
    raw = path.read_bytes()
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise catalog_contract.CatalogError(
            "E_ENTRYPOINT",
            f"curated capability {capability_id!r} is not UTF-8",
        ) from exc
    if not lines or lines[0] != "---":
        raise catalog_contract.CatalogError(
            "E_ENTRYPOINT",
            f"curated capability {capability_id!r} lacks exact YAML frontmatter",
        )
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise catalog_contract.CatalogError(
            "E_ENTRYPOINT",
            f"curated capability {capability_id!r} has unterminated YAML frontmatter",
        ) from exc
    fields: dict[str, str] = {}
    for line in lines[1:closing]:
        key, separator, value = line.partition(": ")
        if not separator or key not in {"name", "description"} or key in fields or not value.strip():
            raise catalog_contract.CatalogError(
                "E_ENTRYPOINT",
                f"curated capability {capability_id!r} frontmatter is not the exact standalone skill contract",
            )
        fields[key] = value
    if set(fields) != {"name", "description"}:
        raise catalog_contract.CatalogError(
            "E_ENTRYPOINT",
            f"curated capability {capability_id!r} frontmatter must contain only name and description",
        )
    catalog_contract._id(fields["name"], f"curated capability {capability_id}.frontmatter.name")
    catalog_contract._string(
        fields["description"],
        f"curated capability {capability_id}.frontmatter.description",
        maximum=1024,
    )
    if fields["name"] != capability_id:
        raise catalog_contract.CatalogError(
            "E_ENTRYPOINT",
            f"curated capability {capability_id!r} frontmatter name does not match its ID",
        )
    return raw


def promote(
    source_catalog: Mapping[str, Any],
    curation: Mapping[str, Any],
    skill_root: Path,
) -> dict[str, Any]:
    catalog_contract.validate_catalog(source_catalog, skill_root, verify_files=False)
    entries = _validate_curation(curation)
    sources = {item["source_id"]: item for item in source_catalog["sources"]}
    upstream = {
        (item["source_id"], item["upstream_skill_path"]): item
        for item in source_catalog["capabilities"]
    }
    known_ids = {item["capability_id"] for item in source_catalog["capabilities"]}
    additions: list[dict[str, Any]] = []
    for entry in entries:
        capability_id = entry["capability_id"]
        if capability_id in known_ids:
            raise catalog_contract.CatalogError("E_CAPABILITY", f"curated capability ID collides: {capability_id!r}")
        source = sources.get(entry["source_id"])
        if source is None:
            raise catalog_contract.CatalogError("E_SOURCE", f"unknown curated source {entry['source_id']!r}")
        if source["disposition"] not in {"vendor_curated_subset", "extract_wrapper"}:
            raise catalog_contract.CatalogError(
                "E_TRUST", f"source {entry['source_id']!r} is not eligible for a dispatchable wrapper"
            )
        observed = upstream.get((entry["source_id"], entry["upstream_skill_path"]))
        if observed is None:
            raise catalog_contract.CatalogError(
                "E_SOURCE",
                f"curated capability {capability_id!r} has no exact pinned upstream entrypoint",
            )
        path = catalog_contract._safe_entrypoint(skill_root, entry["entrypoint"])
        siblings = sorted(path.parent.iterdir(), key=lambda item: item.name)
        if siblings != [path] or any(item.is_symlink() for item in siblings):
            raise catalog_contract.CatalogError(
                "E_ENTRYPOINT",
                f"curated capability {capability_id!r} must be a standalone SKILL.md with no sidecar files",
            )
        raw = _validate_wrapper_entrypoint(path, capability_id)
        additions.append(
            {
                "capability_id": capability_id,
                "name": entry["name"],
                "description": entry["description"],
                "source_id": entry["source_id"],
                "upstream_skill_path": entry["upstream_skill_path"],
                "upstream_entrypoint_sha256": observed["upstream_entrypoint_sha256"],
                "upstream_entrypoint_bytes": observed["upstream_entrypoint_bytes"],
                "entrypoint": entry["entrypoint"],
                "entrypoint_sha256": hashlib.sha256(raw).hexdigest(),
                "entrypoint_bytes": len(raw),
                "roles": copy.deepcopy(entry["roles"]),
                "domains": copy.deepcopy(entry["domains"]),
                "tags": copy.deepcopy(entry["tags"]),
                "trust_state": "approved",
                "dispatchable": True,
                "load_policy": "explicit",
                "required_permissions": copy.deepcopy(entry["required_permissions"]),
                "conflicts": copy.deepcopy(entry["conflicts"]),
            }
        )
    result = copy.deepcopy(dict(source_catalog))
    result["catalog_id"] = "company-os-capability-library"
    result["capabilities"] = sorted(
        [*result["capabilities"], *additions], key=lambda item: item["capability_id"]
    )
    catalog_contract.validate_catalog(result, skill_root, verify_files=True)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-catalog", type=Path, required=True)
    parser.add_argument("--curation", type=Path, required=True)
    parser.add_argument("--skill-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        source_catalog = catalog_contract._read_canonical_json(args.source_catalog, "source catalog")
        curation = catalog_contract._read_canonical_json(args.curation, "curation")
        result = promote(source_catalog, curation, args.skill_root)
        catalog_contract._write_atomic(args.output, result)
        catalog_contract._print(
            {
                "ok": True,
                "catalog": args.output.as_posix(),
                "catalog_sha256": catalog_contract.canonical_digest(result),
                "source_count": len(result["sources"]),
                "capability_count": len(result["capabilities"]),
                "dispatchable_count": sum(1 for item in result["capabilities"] if item["dispatchable"]),
            }
        )
        return 0
    except catalog_contract.CatalogError as exc:
        catalog_contract._print({"ok": False, "error": {"code": exc.code, "message": str(exc)}})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
