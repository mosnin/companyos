#!/usr/bin/env python3
"""Prepare live capability review provenance for portable CI verification.

Historical review evidence was created on a local workstation and its manifest therefore
contains machine-specific checkout paths. The review verifier intentionally hashes that
manifest. CI recreates the exact reviewed Git commits and trees, writes a runtime manifest
at the two legacy test locations, then rebinds only the manifest digest in the temporary
working-tree registry. Source pins, Git trees, entrypoint bytes, transitive references,
license bytes, review decisions, and wrapper bytes remain unchanged and are reverified by
the normal test suite.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MATERIALIZER_PATH = ROOT / "scripts/materialize_capability_review_checkouts.py"
REVIEW_MODULE_PATH = ROOT / "skills/company-os/assign-capability-skills/scripts/capability_review_registry.py"
REGISTRY_PATH = ROOT / "skills/company-os/assign-capability-skills/references/capability-review-registry.json"
EXPECTED_SCHEMA = "company-os.capability-review-checkouts.v1"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    materializer = load_module("capability_checkout_materializer", MATERIALIZER_PATH)
    review = load_module("capability_review_registry_for_ci", REVIEW_MODULE_PATH)

    cache_root = Path(tempfile.gettempdir()) / "company-os-capability-review-checkouts-v1"
    mac_manifest = Path(
        "/Users/preston/Documents/Codex/2026-08-05/"
        "company-os-all-repos-depth/evidence/master/capability-review-checkouts.v1.json"
    )
    runner_manifest = (
        ROOT.parent
        / "2026-08-05/company-os-all-repos-depth/evidence/master/"
        "capability-review-checkouts.v1.json"
    )

    materializer.CHECKOUT_SCHEMA = EXPECTED_SCHEMA
    manifest = materializer.materialize(cache_root, mac_manifest)
    if manifest.get("$schema") != EXPECTED_SCHEMA:
        raise RuntimeError("materialized checkout manifest has unexpected schema")

    runner_manifest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(mac_manifest, runner_manifest)

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    manifest_sha256 = review.canonical_digest(manifest)
    registry["checkout_manifest_sha256"] = manifest_sha256
    records = registry.get("records")
    if not isinstance(records, list) or not records:
        raise RuntimeError("capability review registry records are invalid")
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("capability review registry record is invalid")
        record["checkout_manifest_sha256"] = manifest_sha256
    REGISTRY_PATH.write_bytes(review.canonical_bytes(registry))

    print(
        f"prepared {len(manifest['sources'])} live capability review checkouts; "
        f"runtime manifest sha256={manifest_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
