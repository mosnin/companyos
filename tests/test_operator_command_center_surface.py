from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_operator_command_center_surface.py"
REVIEWER_ID = "company-os-0.4.2-independent-sol-reviewer"
REVIEWER_PUBLIC_KEY_DER_SHA256 = (
    "0704f603904625394a04a0f02722f286297843b4cf478e643f895357f66901e1"
)


def load_verifier():
    spec = importlib.util.spec_from_file_location("occ_surface_verifier", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OperatorCommandCenterSurfaceTests(unittest.TestCase):
    def verifier_kwargs(self) -> dict[str, str]:
        return {
            "expected_reviewer_id": REVIEWER_ID,
            "expected_reviewer_public_key_der_sha256": REVIEWER_PUBLIC_KEY_DER_SHA256,
        }

    def test_current_surface_and_independent_signature_verify(self) -> None:
        verifier = load_verifier()
        result = verifier.verify_surface(ROOT, **self.verifier_kwargs())
        self.assertTrue(result["ok"])
        self.assertEqual(result["files"], 21)
        self.assertEqual(result["reviewer_id"], REVIEWER_ID)

    def test_missing_external_reviewer_trust_anchor_fails_closed(self) -> None:
        verifier = load_verifier()
        with self.assertRaisesRegex(
            verifier.SurfaceVerificationError,
            "externally supplied reviewer identity trust anchor is required",
        ):
            verifier.verify_surface(ROOT)

    def test_wrong_external_reviewer_fingerprint_fails_closed(self) -> None:
        verifier = load_verifier()
        with self.assertRaisesRegex(
            verifier.SurfaceVerificationError,
            "does not match the externally supplied trust anchor",
        ):
            verifier.verify_surface(
                ROOT,
                expected_reviewer_id=REVIEWER_ID,
                expected_reviewer_public_key_der_sha256="0" * 64,
            )

    def test_signer_identity_must_match_external_reviewer_delegation(self) -> None:
        verifier = load_verifier()
        with self.assertRaisesRegex(
            verifier.SurfaceVerificationError,
            "identity does not match the externally supplied trust anchor",
        ):
            verifier.verify_surface(
                ROOT,
                expected_reviewer_id="another-reviewer",
                expected_reviewer_public_key_der_sha256=REVIEWER_PUBLIC_KEY_DER_SHA256,
            )

    def test_manifest_drift_fails_closed(self) -> None:
        verifier = load_verifier()
        source = ROOT / verifier.SURFACE
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["files"][0]["size"] += 1
        with tempfile.TemporaryDirectory() as temp_dir:
            changed = Path(temp_dir) / "surface.json"
            changed.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(
                verifier.SurfaceVerificationError,
                "surface manifest bytes",
            ):
                verifier.verify_surface(ROOT, surface_path=changed, **self.verifier_kwargs())

    def test_attestation_or_signature_drift_fails_closed(self) -> None:
        verifier = load_verifier()
        source = ROOT / verifier.ATTESTATION
        with tempfile.TemporaryDirectory() as temp_dir:
            changed = Path(temp_dir) / "attestation.json"
            changed.write_bytes(source.read_bytes().replace(b'"accepted"', b'"rejected"', 1))
            with self.assertRaisesRegex(
                verifier.SurfaceVerificationError,
                "attestation claim mismatch",
            ):
                verifier.verify_surface(ROOT, attestation_path=changed, **self.verifier_kwargs())


if __name__ == "__main__":
    unittest.main()
