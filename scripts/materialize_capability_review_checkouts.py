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
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
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


def source_index() -> dict[str, Mapping[str, Any]]:
    registry = read_json(SOURCE_REGISTRY_PATH)
    records = registry.get("records")
    if not isinstance(records, list):
        raise MaterializeError("source registry records are invalid")
    index: dict[str, Mapping[str, Any]] = {}
    for raw in records:
        if not isinstance(raw, dict):
            continue
        source_id = raw.get("source_id")
        if isinstance(source_id, str):
            index[source_id] = raw
        aliases = raw.get("catalog_source_ids")
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str):
                    index[alias] = raw
    return index


def required_sources() -> list[dict[str, Any]]:
    catalog = read_json(CATALOG_PATH)
    decisions = read_json(DECISIONS_PATH)
    registry = read_json(REGISTRY_PATH)
    sources = source_index()
    capabilities = catalog.get("capabilities")
    review_records = registry.get("records")
    decision_records = decisions.get("decisions")
    if not isinstance(capabilities, list) or not isinstance(review_records, list) or not isinstance(decision_records, list):
        raise MaterializeError("capability review inputs are invalid")
    review_by_id = {r.get("capability_id"): r for r in review_records if isinstance(r, dict)}
    decisions_by_id = {r.get("capability_id"): r for r in decision_records if isinstance(r, dict)}
    grouped: dict[str, dict[str, Any]] = {}
    for capability in capabilities:
        if not isinstance(capability, dict) or capability.get("dispatchable") is not True:
            continue
        capability_id = capability.get("capability_id")
        source_id = capability.get("source_id")
        if not isinstance(capability_id, str) or not isinstance(source_id, str):
            raise MaterializeError("dispatchable capability lacks identity")
        review = review_by_id.get(capability_id)
        decision = decisions_by_id.get(capability_id)
        source = sources.get(source_id)
        if not isinstance(review, dict) or not isinstance(decision, dict) or not isinstance(source, Mapping):
            raise MaterializeError(f"missing provenance inputs for {capability_id}")
        canonical_source = source.get("canonical_source")
        if not isinstance(canonical_source, str) or not canonical_source.startswith("https://github.com/"):
            raise MaterializeError(f"source {source_id} lacks a public GitHub canonical source")
        commit = review.get("source_checkout_commit")
        tree = review.get("source_checkout_tree")
        if not isinstance(commit, str) or not isinstance(tree, str):
            raise MaterializeError(f"review {capability_id} lacks checkout pin")
        entrypoint = capability.get("upstream_skill_path")
        if not isinstance(entrypoint, str):
            raise MaterializeError(f"capability {capability_id} lacks upstream path")
        item = grouped.setdefault(
            source_id,
            {
                "source_id": source_id,
                "canonical_source": canonical_source,
                "source_commit": commit,
                "source_tree": tree,
                "paths": set(),
            },
        )
        if item["source_commit"] != commit or item["source_tree"] != tree:
            raise MaterializeError(f"source {source_id} has conflicting review pins")
        item["paths"].add(entrypoint)
        refs = decision.get("upstream_transitive_references", [])
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, dict) and isinstance(ref.get("path"), str):
                    item["paths"].add(ref["path"])
        license_evidence = decision.get("license_evidence")
        if isinstance(license_evidence, dict) and isinstance(license_evidence.get("path"), str):
            item["paths"].add(license_evidence["path"])
    result = []
    for source_id in sorted(grouped):
        item = grouped[source_id]
        item["paths"] = sorted(item["paths"])
        result.append(item)
    return result


def materialize_source(source: Mapping[str, Any], checkout: Path) -> None:
    source_id = str(source["source_id"])
    url = str(source["canonical_source"])
    commit = str(source["source_commit"])
    tree = str(source["source_tree"])
    if checkout.exists():
        shutil.rmtree(checkout)
    checkout.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", url, str(checkout)], check=True, capture_output=True, text=True)
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(checkout), "fetch", "--depth=1", "origin", commit],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise MaterializeError(result.stderr.strip() or f"cannot fetch {source_id}@{commit}")
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(checkout), "checkout", "--detach", "FETCH_HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    actual_commit = git(checkout, "rev-parse", "HEAD")
    actual_tree = git(checkout, "rev-parse", "HEAD^{tree}")
    if actual_commit != commit or actual_tree != tree:
        raise MaterializeError(f"checkout pin mismatch for {source_id}")
    paths = source.get("paths", [])
    if not isinstance(paths, list):
        raise MaterializeError(f"paths for {source_id} are invalid")
    missing = [path for path in paths if not (checkout / path).is_file()]
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
