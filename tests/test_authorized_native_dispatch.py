from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "company-os" / "operate-federated-codex-runtime" / "scripts" / "prepare_authorized_native_codex_dispatch.py"
spec = importlib.util.spec_from_file_location("authorized_native_dispatch", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(MODULE)


def fixtures() -> tuple[dict, dict, dict]:
    outcome = {
        "$schema": MODULE.OUTCOME_SCHEMA,
        "objective_id": "viral-game",
        "original_objective": "Make a viral game.",
        "scale_allowed": True,
    }
    authorization = {
        "$schema": MODULE.AUTH_SCHEMA,
        "schema_version": 1,
        "objective_id": "viral-game",
        "authorized": True,
        "blockers": [],
        "required_artifact_classes": ["playable-build"],
        "required_evaluator_ids": ["gameplay"],
        "input_bindings": {
            "outcome_sha256": MODULE.outcome_digest(outcome),
            "artifacts_sha256": "1" * 64,
            "evaluators_sha256": "2" * 64,
            "benchmarks_sha256": "3" * 64,
            "calibrations_sha256": "4" * 64,
        },
        "authorization_sha256": None,
    }
    authorization["authorization_sha256"] = MODULE.outcome_digest(authorization)
    kernel = {"objective": "Make a viral game."}
    return kernel, authorization, outcome


class AuthorizedNativeDispatchTests(unittest.TestCase):
    def test_current_authorization_binds_kernel_objective(self) -> None:
        kernel, authorization, outcome = fixtures()
        supplied = MODULE.validate_outcome_authorization(kernel, authorization, outcome)
        self.assertEqual(supplied, authorization["authorization_sha256"])

    def test_missing_authority_blocks(self) -> None:
        kernel, authorization, outcome = fixtures()
        authorization["authorized"] = False
        with self.assertRaises(MODULE.AuthorizedDispatchError):
            MODULE.validate_outcome_authorization(kernel, authorization, outcome)

    def test_stale_outcome_contract_blocks(self) -> None:
        kernel, authorization, outcome = fixtures()
        outcome["scale_allowed"] = False
        with self.assertRaises(MODULE.AuthorizedDispatchError) as ctx:
            MODULE.validate_outcome_authorization(kernel, authorization, outcome)
        self.assertIn("stale", str(ctx.exception))

    def test_kernel_objective_drift_blocks(self) -> None:
        kernel, authorization, outcome = fixtures()
        kernel["objective"] = "Build something else."
        with self.assertRaises(MODULE.AuthorizedDispatchError) as ctx:
            MODULE.validate_outcome_authorization(kernel, authorization, outcome)
        self.assertIn("kernel objective differs", str(ctx.exception))

    def test_tampered_authorization_digest_blocks(self) -> None:
        kernel, authorization, outcome = fixtures()
        authorization["required_artifact_classes"].append("audio-mix")
        with self.assertRaises(MODULE.AuthorizedDispatchError) as ctx:
            MODULE.validate_outcome_authorization(kernel, authorization, outcome)
        self.assertIn("digest does not verify", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
