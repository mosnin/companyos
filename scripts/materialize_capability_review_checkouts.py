#!/usr/bin/env python3
"""Materialize the exact public source checkouts required by capability review evidence.

The checkout directory is transport state, not provenance identity. The emitted manifest
binds each source to the exact reviewed commit and tree while pointing at a local checkout
that can be recreated on any machine with Git and network access.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "skills/company-os/assign-capability-skills/references/capability-catalog.json"
DECISIONS_PATH = ROOT / "skills/company-os/assign-capability-skills/references/capability-review-decisions.json"
REGISTRY_PATH = ROOT / "skills/company-os/assign-capability-skills/references/capability-review-registry.json"
SOURCE_REGISTRY_PATH = ROOT / "skills/company-os/source-intelligence/references/source-intelligence-registry.json"
CHECKOUT_SCHEMA = "company-os.capability-review-checkout-manifest.v1"


class MaterializeError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MaterializeError(f"{path} must contain a JSON object")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise MaterializeError(detail)
    return result.stdout.strip()


def source_record(source_registry: Mapping[str, Any], catalog_source_id: str) -> Mapping[str, Any]:
    records = source_registry.get("records")
    if not isinstance(records, list):
        raise MaterializeError("source intelligence registry records are invalid")
    matches = [
        item
        for item in records
        if isinstance(item, Mapping)
        and (
            item.get("source_id") == catalog_source_id
            or catalog_source_id in item.get("catalog_source_ids", [])
        )
    ]
    if len(matches) != 1:
        raise MaterializeError(
            f"catalog source {catalog_source_id!r} resolves to {len(matches)} source records"
        )
    return matches[0]


def required_sources() -> list[dict[str, Any]]:
    catalog = read_json(CATALOG_PATH)
    decisions = read_json(DECISIONS_PATH)
    registry = read_json(REGISTRY_PATH)
    sources = read_json(SOURCE_REGISTRY_PATH)

    decision_index = {
        item["capability_id"]: item
        for item in decisions.get("decisions", [])
        if isinstance(item, dict) and isinstance(item.get("capability_id"), str)
    }
    registry_records = {
        item["capability_id"]: item
        for item in registry.get("records", [])
        if isinstance(item, dict) and isinstance(item.get("capability_id"), str)
    }

    grouped: dict[str, dict[str, Any]] = {}
    for capability in catalog.get("capabilities", []):
        if not isinstance(capability, dict) or capability.get("dispatchable") is not True:
            continue
        capability_id = capability.get("capability_id")
        source_id = capability.get("source_id")
        if not isinstance(capability_id, str) or not isinstance(source_id, str):
            raise MaterializeError("dispatchable capability identity is invalid")
        decision = decision_index.get(capability_id)
        reviewed = registry_records.get(capability_id)
        if decision is None or reviewed is None:
            raise MaterializeError(f"missing review evidence for {capability_id}")
        source = source_record(sources, source_id)
        url = source.get("canonical_source")
        pin = source.get("pin")
        if not isinstance(url, str) or not url.startswith("https://github.com/"):
            raise MaterializeError(f"source {source_id} lacks a public GitHub canonical source")
        if not isinstance(pin, str) or len(pin) != 40:
            raise MaterializeError(f"source {source_id} lacks an immutable pin")
        if reviewed.get("source_checkout_commit") != pin:
            raise MaterializeError(f"source {source_id} registry commit differs from source intelligence")
        tree = reviewed.get("source_checkout_tree")
        if not isinstance(tree, str) or len(tree) != 40:
            raise MaterializeError(f"source {source_id} registry tree is invalid")

        entry = grouped.setdefault(
            source_id,
            {
                "source_id": source_id,
                "canonical_source": url,
                "source_commit": pin,
                "source_tree": tree,
                "paths": set(),
            },
        )
        if entry["source_commit"] != pin or entry["source_tree"] != tree:
            raise MaterializeError(f"source {source_id} has inconsistent reviewed pins")

        upstream = capability.get("upstream_skill_path")
        if not isinstance(upstream, str) or not upstream:
            raise MaterializeError(f"capability {capability_id} lacks upstream skill path")
        entry["paths"].add(upstream)
        license_evidence = decision.get("license_evidence")
        if not isinstance(license_evidence, dict) or not isinstance(license_evidence.get("path"), str):
            raise MaterializeError(f"capability {capability_id} lacks license evidence path")
        entry["paths"].add(license_evidence["path"])
        refs = decision.get("upstream_transitive_references")
        if not isinstance(refs, list):
            raise MaterializeError(f"capability {capability_id} transitive references are invalid")
        for ref in refs:
            if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
                raise MaterializeError(f"capability {capability_id} reference path is invalid")
            entry["paths"].add(ref["path"])

    result = []
    for source_id in sorted(grouped):
        entry = grouped[source_id]
        result.append({**entry, "paths": sorted(entry["paths"])})
    if not result:
        raise MaterializeError("no dispatchable capability sources were found")
    return result


def checkout_matches(root: Path, commit: str, tree: str, required_paths: list[str]) -> bool:
    if not (root / ".git").exists():
        return False
    try:
        if git(root, "rev-parse", "--verify", "HEAD") != commit:
            return False
        if git(root, "rev-parse", "--verify", "HEAD^{tree}") != tree:
            return False
    except MaterializeError:
        return False
    return all((root / path).is_file() for path in required_paths)


def materialize_source(source: Mapping[str, Any], root: Path) -> None:
    source_id = str(source["source_id"])
    commit = str(source["source_commit"])
    tree = str(source["source_tree"])
    url = str(source["canonical_source"])
    paths = [str(item) for item in source["paths"]]
    if checkout_matches(root, commit, tree, paths):
        return

    if root.exists():
        shutil.rmtree(root)
    root.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir()
    git(root, "init", "-q")
    git(root, "remote", "add", "origin", url)
    git(root, "sparse-checkout", "init", "--no-cone")
    sparse_file = root / ".git/info/sparse-checkout"
    sparse_file.write_text("\n".join(paths) + "\n", encoding="utf-8")

    last_error: Exception | None = None
    for _ in range(3):
        try:
            git(root, "fetch", "--depth=1", "--filter=blob:none", "origin", commit)
            git(root, "checkout", "--detach", "-q", "FETCH_HEAD")
            last_error = None
            break
        except MaterializeError as exc:
            last_error = exc
    if last_error is not None:
        raise MaterializeError(f"cannot fetch {source_id}: {last_error}") from last_error

    actual_commit = git(root, "rev-parse", "--verify", "HEAD")
    actual_tree = git(root, "rev-parse", "--verify", "HEAD^{tree}")
    if actual_commit != commit or actual_tree != tree:
        raise MaterializeError(f"checkout pin drift for {source_id}")
    missing = [path for path in paths if not (root / path).is_file()]
    if missing:
        raise MaterializeError(f"checkout {source_id} lacks required paths: {', '.join(missing)}")


def materialize(cache_root: Path, output: Path) -> dict[str, Any]:
    sources = required_sources()
    manifest_sources = []
    for source in sources:
        checkout = cache_root / str(source["source_id"])
        materialize_source(source, checkout)
        manifest_sources.append(
            {
                "checkout_path": str(checkout.resolve()),
                "source_commit": source["source_commit"],
                "source_id": source["source_id"],
                "source_tree": source["source_tree"],
            }
        )
    manifest = {
        "$schema": CHECKOUT_SCHEMA,
        "schema_version": 1,
        "sources": manifest_sources,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(manifest))
    return manifest


def default_cache_root() -> Path:
    configured = os.environ.get("COMPANY_OS_CAPABILITY_CHECKOUT_CACHE")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(tempfile.gettempdir()) / "company-os-capability-review-checkouts-v1"


def default_output() -> Path:
    configured = os.environ.get("COMPANY_OS_CAPABILITY_CHECKOUT_MANIFEST")
    if configured:
        return Path(configured).expanduser().resolve()
    return default_cache_root().parent / "company-os-capability-review-checkouts.v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, default=default_cache_root())
    parser.add_argument("--output", type=Path, default=default_output())
    args = parser.parse_args()
    manifest = materialize(args.cache_root.resolve(), args.output.resolve())
    print(f"materialized {len(manifest['sources'])} capability review source checkouts at {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
