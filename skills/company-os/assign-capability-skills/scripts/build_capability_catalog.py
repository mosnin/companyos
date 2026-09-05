#!/usr/bin/env python3
"""Build a metadata-only capability catalog from pinned local Git objects."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import capability_catalog as catalog_contract


CAMPAIGN_SCHEMA = "company-os.capability-source-campaign.v1"
CAMPAIGN_KEYS = {"$schema", "schema_version", "campaign_id", "sources"}
SOURCE_KEYS = {
    "source_id",
    "checkout_path",
    "canonical_url",
    "source_commit",
    "source_tree",
    "observed_at",
    "license",
    "disposition",
    "risk_flags",
    "default_domains",
    "default_roles",
    "default_trust_state",
    "entrypoint_paths",
    "entrypoint_globs",
}
OPTIONAL_SOURCE_KEYS = {"intelligence_node_manifest"}
FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
FIELD_RE = re.compile(r"^(?P<key>name|description):\s*(?P<value>.+?)\s*$", re.MULTILINE)
TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "agent",
    "agents",
    "for",
    "from",
    "of",
    "skill",
    "skills",
    "the",
    "to",
    "with",
}


def _git(checkout: Path, *arguments: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(checkout), *arguments],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise catalog_contract.CatalogError("E_GIT", f"git {' '.join(arguments)} failed: {message}")
    return result.stdout if binary else result.stdout.decode("utf-8").strip()


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise catalog_contract.CatalogError(
            "E_SCHEMA",
            f"{label} keys differ; missing={sorted(expected - actual)!r}, extra={sorted(actual - expected)!r}",
        )


def _canonical_id(*parts: str) -> str:
    tokens = TOKEN_RE.findall("-".join(parts).lower())
    value = "-".join(tokens) or "external-skill"
    if not value[0].isalpha():
        value = "skill-" + value
    if len(value) > 120:
        value = value[:107].rstrip("-") + "-" + hashlib.sha256(value.encode()).hexdigest()[:12]
    return value


def _frontmatter(raw: bytes, path: str) -> tuple[str, str]:
    text = raw.decode("utf-8", errors="replace")
    match = FRONTMATTER_RE.search(text)
    values: dict[str, str] = {}
    if match:
        for field in FIELD_RE.finditer(match.group("body")):
            value = field.group("value").strip().strip("\"'")
            values[field.group("key")] = value
    parent = PurePosixPath(path).parent.name
    name = values.get("name") or ("instruction-foundation" if PurePosixPath(path).name == "CLAUDE.md" else parent)
    description = values.get("description") or f"External skill reference from {path}."
    description = re.sub(r"\s+", " ", description).strip()
    if len(description) > 280:
        description = description[:277].rstrip() + "..."
    return name, description


def _tags(source_id: str, name: str, path: str, domains: Sequence[str]) -> list[str]:
    values = set(domains)
    values.update(TOKEN_RE.findall(source_id.lower()))
    values.update(TOKEN_RE.findall(name.lower()))
    values.update(TOKEN_RE.findall(PurePosixPath(path).parent.as_posix().lower()))
    values.difference_update(STOPWORDS)
    return sorted(
        value
        for value in values
        if value and len(value) <= 48 and catalog_contract.PERMISSION_RE.fullmatch(value)
    )[:24]


def _validate_campaign(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    _exact_keys(value, CAMPAIGN_KEYS, "campaign")
    if value["$schema"] != CAMPAIGN_SCHEMA or value["schema_version"] != 1:
        raise catalog_contract.CatalogError("E_SCHEMA", "campaign schema/version is unsupported")
    catalog_contract._id(value["campaign_id"], "campaign.campaign_id")
    if not isinstance(value["sources"], list) or not value["sources"]:
        raise catalog_contract.CatalogError("E_SCHEMA", "campaign.sources must be a nonempty array")
    sources: list[dict[str, Any]] = []
    for raw_source in value["sources"]:
        source = dict(catalog_contract._object(raw_source, "campaign source"))
        missing = SOURCE_KEYS - set(source)
        extra = set(source) - SOURCE_KEYS - OPTIONAL_SOURCE_KEYS
        if missing or extra:
            raise catalog_contract.CatalogError(
                "E_SCHEMA",
                f"campaign source keys differ; missing={sorted(missing)!r}, extra={sorted(extra)!r}",
            )
        catalog_contract._id(source["source_id"], "campaign source.source_id")
        checkout = Path(catalog_contract._string(source["checkout_path"], "campaign source.checkout_path"))
        if checkout.is_symlink() or not checkout.is_dir():
            raise catalog_contract.CatalogError("E_PATH", f"source checkout is not a regular directory: {checkout}")
        if not catalog_contract.HEX40.fullmatch(str(source["source_commit"])) or not catalog_contract.HEX40.fullmatch(str(source["source_tree"])):
            raise catalog_contract.CatalogError("E_SCHEMA", "campaign source commit/tree is invalid")
        catalog_contract._sorted_unique_strings(
            source["risk_flags"], "campaign source.risk_flags", pattern=catalog_contract.PERMISSION_RE
        )
        catalog_contract._sorted_unique_strings(
            source["default_domains"],
            "campaign source.default_domains",
            pattern=catalog_contract.PERMISSION_RE,
            nonempty=True,
        )
        catalog_contract._sorted_unique_strings(
            source["default_roles"],
            "campaign source.default_roles",
            allowed=catalog_contract.ROLES,
            nonempty=True,
        )
        if source["default_trust_state"] not in {"reference_only", "quarantine", "rejected"}:
            raise catalog_contract.CatalogError(
                "E_TRUST", "automated source ingestion may not create approved capabilities"
            )
        explicit = catalog_contract._sorted_unique_strings(
            source["entrypoint_paths"], "campaign source.entrypoint_paths"
        )
        for path in explicit:
            catalog_contract._relative_path(path, "campaign source entrypoint")
        globs = catalog_contract._sorted_unique_strings(
            source["entrypoint_globs"], "campaign source.entrypoint_globs"
        )
        for pattern in globs:
            if pattern.startswith("/") or ".." in PurePosixPath(pattern).parts or "**" in pattern:
                raise catalog_contract.CatalogError(
                    "E_PATH", f"campaign source glob is not bounded: {pattern!r}"
                )
        if "intelligence_node_manifest" in source:
            catalog_contract._relative_path(
                catalog_contract._string(
                    source["intelligence_node_manifest"],
                    "campaign source.intelligence_node_manifest",
                ),
                "campaign source intelligence node manifest",
            )
        sources.append(source)
    if [item["source_id"] for item in sources] != sorted(item["source_id"] for item in sources):
        raise catalog_contract.CatalogError("E_SCHEMA", "campaign sources must be sorted by source_id")
    if len({item["source_id"] for item in sources}) != len(sources):
        raise catalog_contract.CatalogError("E_SCHEMA", "campaign source IDs must be unique")
    return sources


def build_catalog(campaign: Mapping[str, Any]) -> dict[str, Any]:
    sources = _validate_campaign(campaign)
    catalog_sources: list[dict[str, Any]] = []
    capabilities: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for source in sources:
        checkout = Path(source["checkout_path"])
        commit = source["source_commit"]
        observed_commit = str(_git(checkout, "rev-parse", "HEAD"))
        observed_tree = str(_git(checkout, "rev-parse", f"{commit}^{{tree}}"))
        if observed_commit != commit or observed_tree != source["source_tree"]:
            raise catalog_contract.CatalogError(
                "E_SOURCE",
                f"source {source['source_id']!r} checkout does not match its pinned commit/tree",
            )
        tracked_raw = _git(checkout, "ls-tree", "-r", "-z", "--name-only", commit, binary=True)
        assert isinstance(tracked_raw, bytes)
        tracked = sorted(
            item.decode("utf-8")
            for item in tracked_raw.split(b"\0")
            if item
        )
        tracked_set = set(tracked)
        manifest_path = source.get("intelligence_node_manifest")
        if manifest_path and manifest_path not in tracked_set:
            raise catalog_contract.CatalogError(
                "E_SOURCE",
                f"source {source['source_id']!r} intelligence node manifest is missing: {manifest_path!r}",
            )
        if manifest_path:
            manifest_raw = _git(checkout, "cat-file", "blob", f"{commit}:{manifest_path}", binary=True)
            assert isinstance(manifest_raw, bytes)
            try:
                manifest = json.loads(manifest_raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise catalog_contract.CatalogError("E_SCHEMA", "intelligence node manifest is not valid JSON") from exc
            authority = manifest.get("authority") if isinstance(manifest, dict) else None
            if (
                manifest.get("$schema") != "company-os.intelligence-node.v1"
                or manifest.get("schema_version") != 1
                or manifest.get("controller") != "company-os"
                or manifest.get("role") != "passive_expert_kernel"
                or manifest.get("effects") != []
                or not isinstance(authority, dict)
                or any(value is not False for value in authority.values())
            ):
                raise catalog_contract.CatalogError(
                    "E_TRUST", "intelligence node manifest must declare a passive Company OS controlled node"
                )
        glob_matches = {
            path
            for path in tracked
            if any(fnmatch.fnmatchcase(path, pattern) for pattern in source["entrypoint_globs"])
        }
        unmatched_globs = sorted(
            pattern
            for pattern in source["entrypoint_globs"]
            if not any(fnmatch.fnmatchcase(path, pattern) for path in tracked)
        )
        if unmatched_globs:
            raise catalog_contract.CatalogError(
                "E_SOURCE",
                f"source {source['source_id']!r} entrypoint globs matched nothing: {unmatched_globs!r}",
            )
        entrypoints = sorted(
            {path for path in tracked if PurePosixPath(path).name == "SKILL.md"}
            | set(source["entrypoint_paths"])
            | glob_matches
        )
        missing = sorted(set(source["entrypoint_paths"]) - tracked_set)
        if missing:
            raise catalog_contract.CatalogError(
                "E_SOURCE", f"source {source['source_id']!r} explicit entrypoints are missing: {missing!r}"
            )
        catalog_sources.append(
            {
                "source_id": source["source_id"],
                "canonical_url": source["canonical_url"],
                "source_commit": commit,
                "source_tree": source["source_tree"],
                "observed_at": source["observed_at"],
                "license": source["license"],
                "disposition": source["disposition"],
                "risk_flags": source["risk_flags"],
            }
        )
        for path in entrypoints:
            blob = _git(checkout, "cat-file", "blob", f"{commit}:{path}", binary=True)
            assert isinstance(blob, bytes)
            name, description = _frontmatter(blob, path)
            base_id = _canonical_id(source["source_id"], name)
            capability_id = base_id
            if capability_id in used_ids:
                capability_id = f"{base_id}-{hashlib.sha256(path.encode()).hexdigest()[:10]}"
            used_ids.add(capability_id)
            capabilities.append(
                {
                    "capability_id": capability_id,
                    "name": name[:96],
                    "description": description,
                    "source_id": source["source_id"],
                    "upstream_skill_path": path,
                    "upstream_entrypoint_sha256": hashlib.sha256(blob).hexdigest(),
                    "upstream_entrypoint_bytes": len(blob),
                    "entrypoint": None,
                    "entrypoint_sha256": None,
                    "entrypoint_bytes": 0,
                    "roles": source["default_roles"],
                    "domains": source["default_domains"],
                    "tags": _tags(source["source_id"], name, path, source["default_domains"]),
                    "trust_state": source["default_trust_state"],
                    "dispatchable": False,
                    "load_policy": "explicit",
                    "required_permissions": [],
                    "conflicts": [],
                }
            )
    result = {
        "$schema": catalog_contract.CATALOG_SCHEMA,
        "schema_version": 1,
        "catalog_id": _canonical_id(campaign["campaign_id"], "catalog"),
        "policy": {
            "max_skills_per_assignment": 4,
            "max_entrypoint_bytes_per_assignment": 49152,
            "max_search_results": 8,
        },
        "sources": sorted(catalog_sources, key=lambda item: item["source_id"]),
        "capabilities": sorted(capabilities, key=lambda item: item["capability_id"]),
    }
    catalog_contract.validate_catalog(result, Path(__file__).resolve().parents[1], verify_files=False)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        campaign = catalog_contract._read_canonical_json(args.campaign, "campaign")
        result = build_catalog(campaign)
        catalog_contract._write_atomic(args.output, result)
        catalog_contract._print(
            {
                "ok": True,
                "catalog": args.output.as_posix(),
                "catalog_sha256": catalog_contract.canonical_digest(result),
                "source_count": len(result["sources"]),
                "capability_count": len(result["capabilities"]),
            }
        )
        return 0
    except catalog_contract.CatalogError as exc:
        catalog_contract._print({"ok": False, "error": {"code": exc.code, "message": str(exc)}})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
