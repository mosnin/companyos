from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

_PREPARED_PATH: Path | None = None


def ensure_capability_review_checkouts() -> Path:
    """Materialize exact pinned upstream checkouts and return a portable manifest path."""
    global _PREPARED_PATH
    if _PREPARED_PATH is not None and _PREPARED_PATH.is_file():
        return _PREPARED_PATH
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts/materialize_capability_review_checkouts.py"
    spec = importlib.util.spec_from_file_location("capability_review_test_materializer", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cache_root = Path(tempfile.gettempdir()) / "company-os-capability-review-checkouts-v1"
    output = Path(tempfile.gettempdir()) / "company-os-capability-review-checkouts.v1.json"
    module.CHECKOUT_SCHEMA = "company-os.capability-review-checkouts.v1"
    manifest = module.materialize(cache_root, output)
    if manifest.get("$schema") != "company-os.capability-review-checkouts.v1":
        raise RuntimeError("capability review manifest schema is invalid")
    _PREPARED_PATH = output
    return output
