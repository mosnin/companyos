from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_operator_command_center_surface.py"
REVIEWER_ID = "company-os-0.5.1-external-independent-surface-reviewer"
REVIEWER_PUBLIC_KEY_DER_SHA256 = (
    "41826fdd1c0d78a414bba0876bdf840e01d6836430baab5f7d47a65719408aba"
)
CURRENT_RELEASE = json.loads(
    (ROOT / "programs/company-os-self-hosting/OPERATOR_COMMAND_CENTER_ACCEPTANCE_ATTESTATION.json").read_text()
).get("company_os_release_version")
SCORES = (
    ("North-star alignment", 9.5),
    ("User value", 9.3),
    ("Product coherence", 9.2),
    ("Differentiation", 9.1),
    ("Innovation", 9.0),
    ("Domain fit", 9.4),
    ("Information architecture", 9.2),
    ("Usability", 9.1),
    ("Accessibility", 9.3),
    ("Interaction quality", 9.0),
    ("Visual quality", 9.2),
    ("Brand cohesion", 9.2),
    ("Evidence integrity", 9.3),
)


def load_verifier():
    spec = importlib.util.spec_from_file_location("occ_surface_verifier", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compatible_fixture(verifier, temp_dir: str) -> dict[str, Path | dict]:
    directory = Path(temp_dir)
    entries = []
    for path_value in verifier.EXPECTED_SURFACE_PATHS:
        payload = (ROOT / path_value).read_bytes()
        entries.append({
            "path": path_value,
            "sha256": verifier.sha256_bytes(payload),
            "size": len(payload),
        })
    aggregate = verifier.sha256_bytes(verifier._canonical_files(entries))
    surface = {
        "aggregate_algorithm": (
            "sha256(canonical-json(files,sort_keys=true,separators=comma-colon,utf8))"
        ),
        "aggregate_sha256": aggregate,
        "carrier_commit": "a" * 40,
        "carrier_git_tree": "b" * 40,
        "company_os_release_version": "0.5.1",
        "files": entries,
        "path_set_sha256": verifier.sha256_bytes(
            verifier._canonical_paths([entry["path"] for entry in entries])
        ),
        "prior_surface_lineage": copy.deepcopy(verifier.EXPECTED_PRIOR_SURFACE_LINEAGE),
        "schema_version": 1,
        "surface_id": "operator-command-center-v5-company-os-0.5.1-accepted-surface",
    }
    surface_path = directory / "surface.json"
    write_json(surface_path, surface)
    review_scores = [
        {"dimension": dimension, "minimum": 9.0, "score": score, "status": "pass"}
        for dimension, score in SCORES
    ]
    attestation = copy.deepcopy(verifier.EXPECTED_ATTESTATION)
    attestation.update({
        "carrier_binding": {
            "accepted_carrier_commit": surface["carrier_commit"],
            "accepted_carrier_git_tree": surface["carrier_git_tree"],
            **verifier.EXPECTED_CARRIER_BINDING,
        },
        "issued_at": "2026-08-02T14:30:00Z",
        "prior_accepted_surface_lineage": copy.deepcopy(
            verifier.EXPECTED_PRIOR_ATTESTATION_LINEAGE
        ),
        "review_mean_score": round(
            sum(item["score"] for item in review_scores) / len(review_scores), 2
        ),
        "review_scores": review_scores,
        "reviewer_id": REVIEWER_ID,
        "reviewer_public_key_der_sha256": REVIEWER_PUBLIC_KEY_DER_SHA256,
        "surface_aggregate_sha256": aggregate,
        "surface_manifest_path": verifier.SURFACE.as_posix(),
        "surface_manifest_sha256": verifier.sha256_bytes(surface_path.read_bytes()),
    })
    attestation_path = directory / "attestation.json"
    write_json(attestation_path, attestation)
    signature_path = directory / "signature.bin"
    signature_path.write_bytes(b"\0" * 384)
    return {
        "surface": surface,
        "surface_path": surface_path,
        "attestation": attestation,
        "attestation_path": attestation_path,
        "signature_path": signature_path,
    }


def reseal_surface(verifier, fixture: dict[str, Path | dict]) -> None:
    surface_path = fixture["surface_path"]
    attestation_path = fixture["attestation_path"]
    assert isinstance(surface_path, Path) and isinstance(attestation_path, Path)
    assert isinstance(fixture["surface"], dict) and isinstance(fixture["attestation"], dict)
    write_json(surface_path, fixture["surface"])
    fixture["attestation"]["surface_manifest_sha256"] = verifier.sha256_bytes(
        surface_path.read_bytes()
    )
    write_json(attestation_path, fixture["attestation"])


class OperatorCommandCenterSurfaceTests(unittest.TestCase):
    def verifier_kwargs(self) -> dict[str, str]:
        return {
            "expected_reviewer_id": REVIEWER_ID,
            "expected_reviewer_public_key_der_sha256": REVIEWER_PUBLIC_KEY_DER_SHA256,
        }

    def verify_fixture(self, verifier, fixture) -> dict:
        with mock.patch.object(verifier, "_verify_detached_signature", return_value=None):
            return verifier.verify_surface(
                ROOT,
                surface_path=fixture["surface_path"],
                attestation_path=fixture["attestation_path"],
                signature_path=fixture["signature_path"],
                **self.verifier_kwargs(),
            )

    @unittest.skipUnless(CURRENT_RELEASE == "0.4.3", "legacy surface already replaced")
    def test_current_legacy_surface_is_expected_stale_until_final_signing(self) -> None:
        verifier = load_verifier()
        with self.assertRaisesRegex(
            verifier.SurfaceVerificationError, "attestation claim shape is invalid"
        ):
            verifier.verify_surface(ROOT, **self.verifier_kwargs())

    @unittest.skipUnless(CURRENT_RELEASE == "0.5.1", "final signed surface not imported")
    def test_current_final_surface_and_independent_signature_verify(self) -> None:
        verifier = load_verifier()
        result = verifier.verify_surface(ROOT, **self.verifier_kwargs())
        self.assertTrue(result["ok"])
        self.assertEqual(result["files"], 21)
        self.assertEqual(result["reviewer_id"], REVIEWER_ID)

    def test_generated_compatible_claim_and_surface_fixture_verifies(self) -> None:
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.verify_fixture(verifier, compatible_fixture(verifier, temp_dir))
        self.assertEqual(result["files"], 21)
        self.assertEqual(result["carrier_commit"], "a" * 40)
        self.assertEqual(result["review_mean_score"], 9.22)

    def test_missing_external_reviewer_trust_anchor_fails_closed(self) -> None:
        verifier = load_verifier()
        with self.assertRaisesRegex(
            verifier.SurfaceVerificationError,
            "externally supplied reviewer identity trust anchor is required",
        ):
            verifier.verify_surface(ROOT)

    def test_external_reviewer_identity_and_fingerprint_are_exact(self) -> None:
        verifier = load_verifier()
        with self.assertRaisesRegex(verifier.SurfaceVerificationError, "required stable reviewer"):
            verifier.verify_surface(
                ROOT,
                expected_reviewer_id="another-reviewer",
                expected_reviewer_public_key_der_sha256=REVIEWER_PUBLIC_KEY_DER_SHA256,
            )
        with self.assertRaisesRegex(verifier.SurfaceVerificationError, "required stable reviewer"):
            verifier.verify_surface(
                ROOT,
                expected_reviewer_id=REVIEWER_ID,
                expected_reviewer_public_key_der_sha256="0" * 64,
            )

    def test_carrier_shape_and_surface_binding_drift_fail_closed(self) -> None:
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = compatible_fixture(verifier, temp_dir)
            fixture["attestation"]["carrier_binding"]["accepted_carrier_commit"] = "a" * 39
            write_json(fixture["attestation_path"], fixture["attestation"])
            with self.assertRaisesRegex(verifier.SurfaceVerificationError, "40-hex Git identity"):
                self.verify_fixture(verifier, fixture)

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = compatible_fixture(verifier, temp_dir)
            fixture["surface"]["carrier_commit"] = "c" * 40
            reseal_surface(verifier, fixture)
            with self.assertRaisesRegex(verifier.SurfaceVerificationError, "surface carrier evidence"):
                self.verify_fixture(verifier, fixture)

    def test_exact_runtime_and_authority_commits_reject_drift(self) -> None:
        verifier = load_verifier()
        for field in ("runtime_source_commit", "canonical_authority_commit"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp_dir:
                fixture = compatible_fixture(verifier, temp_dir)
                fixture["attestation"]["carrier_binding"][field] = "c" * 40
                write_json(fixture["attestation_path"], fixture["attestation"])
                with self.assertRaisesRegex(verifier.SurfaceVerificationError, field):
                    self.verify_fixture(verifier, fixture)

    def test_prior_attestation_and_surface_lineage_drift_fail_closed(self) -> None:
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = compatible_fixture(verifier, temp_dir)
            fixture["attestation"]["prior_accepted_surface_lineage"]["company_os_release_version"] = "0.4.2"
            write_json(fixture["attestation_path"], fixture["attestation"])
            with self.assertRaisesRegex(verifier.SurfaceVerificationError, "prior 0.4.3 lineage"):
                self.verify_fixture(verifier, fixture)
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = compatible_fixture(verifier, temp_dir)
            fixture["surface"]["prior_surface_lineage"]["surface_id"] = "drifted"
            reseal_surface(verifier, fixture)
            with self.assertRaisesRegex(verifier.SurfaceVerificationError, "prior 0.4.3 lineage"):
                self.verify_fixture(verifier, fixture)

    def test_score_floor_mean_and_named_dimension_drift_fail_closed(self) -> None:
        verifier = load_verifier()
        mutations = (
            lambda a: a["review_scores"][0].__setitem__("score", 8.9),
            lambda a: a.__setitem__("review_mean_score", 9.21),
            lambda a: a["review_scores"][0].__setitem__("dimension", "Other"),
        )
        for mutate in mutations:
            with tempfile.TemporaryDirectory() as temp_dir:
                fixture = compatible_fixture(verifier, temp_dir)
                mutate(fixture["attestation"])
                write_json(fixture["attestation_path"], fixture["attestation"])
                with self.assertRaisesRegex(verifier.SurfaceVerificationError, "product score"):
                    self.verify_fixture(verifier, fixture)

    def test_signature_algorithm_and_attestation_shape_drift_fail_closed(self) -> None:
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = compatible_fixture(verifier, temp_dir)
            fixture["attestation"]["signature_algorithm"] = "RSA-PSS"
            write_json(fixture["attestation_path"], fixture["attestation"])
            with self.assertRaisesRegex(verifier.SurfaceVerificationError, "signature_algorithm"):
                self.verify_fixture(verifier, fixture)
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = compatible_fixture(verifier, temp_dir)
            fixture["attestation"]["unexpected"] = True
            write_json(fixture["attestation_path"], fixture["attestation"])
            with self.assertRaisesRegex(verifier.SurfaceVerificationError, "claim shape"):
                self.verify_fixture(verifier, fixture)

    def test_public_key_and_surface_drift_fail_closed(self) -> None:
        verifier = load_verifier()
        source = ROOT / verifier.PUBLIC_KEY
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = compatible_fixture(verifier, temp_dir)
            changed_key = Path(temp_dir) / "changed.der"
            payload = bytearray(source.read_bytes())
            payload[len(payload) // 2] ^= 1
            changed_key.write_bytes(payload)
            with self.assertRaisesRegex(verifier.SurfaceVerificationError, "does not bind"):
                with mock.patch.object(verifier, "_verify_detached_signature", return_value=None):
                    verifier.verify_surface(
                        ROOT,
                        surface_path=fixture["surface_path"],
                        attestation_path=fixture["attestation_path"],
                        signature_path=fixture["signature_path"],
                        public_key_path=changed_key,
                        **self.verifier_kwargs(),
                    )
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = compatible_fixture(verifier, temp_dir)
            fixture["surface"]["files"][0]["size"] += 1
            reseal_surface(verifier, fixture)
            with self.assertRaisesRegex(verifier.SurfaceVerificationError, "surface file drifted"):
                self.verify_fixture(verifier, fixture)

    def test_surface_aggregate_and_manifest_binding_drift_fail_closed(self) -> None:
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = compatible_fixture(verifier, temp_dir)
            fixture["surface"]["aggregate_sha256"] = "0" * 64
            reseal_surface(verifier, fixture)
            with self.assertRaisesRegex(verifier.SurfaceVerificationError, "surface aggregate"):
                self.verify_fixture(verifier, fixture)
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = compatible_fixture(verifier, temp_dir)
            fixture["attestation"]["surface_manifest_sha256"] = "0" * 64
            write_json(fixture["attestation_path"], fixture["attestation"])
            with self.assertRaisesRegex(verifier.SurfaceVerificationError, "manifest bytes"):
                self.verify_fixture(verifier, fixture)

    def test_real_rsa3072_detached_signature_and_drift(self) -> None:
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            private_key = directory / "private.pem"
            public_key = directory / "public.der"
            attestation = directory / "attestation.json"
            signature = directory / "signature.bin"
            subprocess.run(
                ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:3072", "-out", str(private_key)],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["openssl", "pkey", "-in", str(private_key), "-pubout", "-outform", "DER", "-out", str(public_key)],
                check=True, capture_output=True,
            )
            attestation.write_text('{"signed":true}\n', encoding="utf-8")
            subprocess.run(
                ["openssl", "dgst", "-sha256", "-sign", str(private_key), "-out", str(signature), str(attestation)],
                check=True, capture_output=True,
            )
            verifier._validate_public_key(public_key)
            verifier._verify_detached_signature(attestation, signature, public_key)
            payload = bytearray(signature.read_bytes())
            payload[len(payload) // 2] ^= 1
            signature.write_bytes(payload)
            with self.assertRaisesRegex(verifier.SurfaceVerificationError, "signature is invalid"):
                verifier._verify_detached_signature(attestation, signature, public_key)

    def test_non_rsa3072_public_key_rejects(self) -> None:
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            private_key = directory / "private.pem"
            public_key = directory / "public.der"
            subprocess.run(
                ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private_key)],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["openssl", "pkey", "-in", str(private_key), "-pubout", "-outform", "DER", "-out", str(public_key)],
                check=True, capture_output=True,
            )
            with self.assertRaisesRegex(verifier.SurfaceVerificationError, "not RSA-3072"):
                verifier._validate_public_key(public_key)


if __name__ == "__main__":
    unittest.main()
