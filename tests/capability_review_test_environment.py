from __future__ import annotations

import importlib.util
from pathlib import Path

_PREPARED = False


def ensure_capability_review_checkouts() -> None:
    """Materialize exact reviewed upstream checkouts before provenance dependent tests."""
    global _PREPARED
    if _PREPARED:
        return
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts/prepare_capability_review_ci.py"
    spec = importlib.util.spec_from_file_location("prepare_capability_review_test_environment", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.main()
    if result != 0:
        raise RuntimeError("capability review checkout preparation failed")
    _PREPARED = True
