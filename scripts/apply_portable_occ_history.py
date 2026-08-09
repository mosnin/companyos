#!/usr/bin/env python3
"""Make Operator Command Center verification portable for local clones."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "programs/company-os-self-hosting"
SURFACE_PATH = PROGRAM / "OPERATOR_COMMAND_CENTER_ACCEPTED_SURFACE.json"
HISTORY_ROOT = PROGRAM / "history/operator-command-center-0.5.1"
HISTORICAL_SURFACE_ROOT = HISTORY_ROOT / "surface"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def materialize_historical_surface() -> None:
    surface = json.loads(SURFACE_PATH.read_text(encoding="utf-8"))
    carrier = surface.get("carrier_commit")
    if not isinstance(carrier, str) or len(carrier) != 40:
        raise RuntimeError("signed surface carrier commit is invalid")
    subprocess.run(
        ["git", "cat-file", "-e", f"{carrier}^{{commit}}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    if HISTORY_ROOT.exists():
        shutil.rmtree(HISTORY_ROOT)
    for entry in surface.get("files", []):
        path_value = entry.get("path")
        expected_digest = entry.get("sha256")
        expected_size = entry.get("size")
        if not isinstance(path_value, str):
            raise RuntimeError("signed surface path is invalid")
        payload = subprocess.run(
            ["git", "show", f"{carrier}:{path_value}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        if len(payload) != expected_size or sha256_bytes(payload) != expected_digest:
            raise RuntimeError(f"carrier bytes do not match signed surface: {path_value}")
        target = HISTORICAL_SURFACE_ROOT / path_value
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    (HISTORY_ROOT / "README.md").write_text(
        """# Operator Command Center 0.5.1 historical surface

This directory preserves the exact twenty one files bound by the existing 0.5.1 detached acceptance signature. The files were materialized from the signed carrier commit and verified against the committed signed surface manifest before being added here.

The bundle is historical release evidence. It does not claim that later Company OS source revisions are covered by the 0.5.1 review. The current verifier checks this immutable bundle, the signed manifest, the bundled reviewer public key fingerprint, and the detached signature without environment variables or repository settings.
""",
        encoding="utf-8",
    )


def patch_verifier() -> None:
    path = ROOT / "scripts/verify_operator_command_center_surface.py"
    replace_once(
        path,
        '''"""Verify the independently signed Operator Command Center product surface.

The reviewer delegation is intentionally not stored in this repository.  A
caller must supply both the reviewer identity and the DER public-key fingerprint
from independently governed acceptance evidence; repository-local keys,
attestations, and CI configuration cannot establish that trust on their own.
"""''',
        '''"""Verify the bundled historical Operator Command Center 0.5.1 surface.

The committed reviewer identity, public key fingerprint, public key, detached
signature, signed manifest, and exact reviewed file bytes make verification
self contained for a local clone. This proves the preserved 0.5.1 review only.
It does not claim that later Company OS source revisions share that acceptance.
Repository authenticity still depends on obtaining the release or commit from a
trusted distribution channel.
"""''',
        "verifier purpose",
    )
    replace_once(
        path,
        'PUBLIC_KEY = PROGRAM / "OPERATOR_COMMAND_CENTER_ACCEPTANCE_REVIEWER_PUBLIC.der"\n',
        'PUBLIC_KEY = PROGRAM / "OPERATOR_COMMAND_CENTER_ACCEPTANCE_REVIEWER_PUBLIC.der"\nHISTORICAL_SURFACE_ROOT = PROGRAM / "history/operator-command-center-0.5.1/surface"\n',
        "historical surface root",
    )
    replace_once(
        path,
        '''def _require_external_reviewer_delegation(
    expected_reviewer_id: str | None,
    expected_reviewer_public_key_der_sha256: str | None,
) -> tuple[str, str]:
    """Require an identity/key pair supplied outside the accepted repository tree."""
    if not isinstance(expected_reviewer_id, str) or not expected_reviewer_id.strip():
        raise SurfaceVerificationError(
            "an externally supplied reviewer identity trust anchor is required"
        )
    if not _is_sha256(expected_reviewer_public_key_der_sha256):
        raise SurfaceVerificationError(
            "an externally supplied reviewer public-key fingerprint trust anchor is required"
        )
    if expected_reviewer_id != EXPECTED_REVIEWER_ID:
        raise SurfaceVerificationError(
            "externally supplied reviewer identity does not match the required stable reviewer"
        )
    if expected_reviewer_public_key_der_sha256 != EXPECTED_REVIEWER_PUBLIC_KEY_DER_SHA256:
        raise SurfaceVerificationError(
            "externally supplied reviewer public-key fingerprint does not match the required stable reviewer"
        )
    return expected_reviewer_id, expected_reviewer_public_key_der_sha256
''',
        '''def _require_external_reviewer_delegation(
    expected_reviewer_id: str | None,
    expected_reviewer_public_key_der_sha256: str | None,
) -> tuple[str, str]:
    """Resolve the bundled trust anchor while allowing exact explicit rechecks."""
    reviewer_id = (
        EXPECTED_REVIEWER_ID
        if expected_reviewer_id is None
        else expected_reviewer_id
    )
    fingerprint = (
        EXPECTED_REVIEWER_PUBLIC_KEY_DER_SHA256
        if expected_reviewer_public_key_der_sha256 is None
        else expected_reviewer_public_key_der_sha256
    )
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise SurfaceVerificationError("reviewer identity trust anchor is invalid")
    if not _is_sha256(fingerprint):
        raise SurfaceVerificationError("reviewer public-key fingerprint trust anchor is invalid")
    if reviewer_id != EXPECTED_REVIEWER_ID:
        raise SurfaceVerificationError(
            "reviewer identity does not match the required stable reviewer"
        )
    if fingerprint != EXPECTED_REVIEWER_PUBLIC_KEY_DER_SHA256:
        raise SurfaceVerificationError(
            "reviewer public-key fingerprint does not match the required stable reviewer"
        )
    return reviewer_id, fingerprint
''',
        "bundled trust anchor",
    )
    replace_once(
        path,
        '''    signature_path: Path | None = None,
    public_key_path: Path | None = None,
) -> dict[str, Any]:
    expected_reviewer_id, expected_reviewer_public_key_der_sha256 = (
''',
        '''    signature_path: Path | None = None,
    public_key_path: Path | None = None,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    default_surface = surface_path is None
    expected_reviewer_id, expected_reviewer_public_key_der_sha256 = (
''',
        "verifier artifact root parameter",
    )
    replace_once(
        path,
        '''    root = root.resolve()
    surface_path = surface_path or root / SURFACE
    attestation_path = attestation_path or root / ATTESTATION
    signature_path = signature_path or root / SIGNATURE
    public_key_path = public_key_path or root / PUBLIC_KEY
''',
        '''    root = root.resolve()
    surface_path = surface_path or root / SURFACE
    attestation_path = attestation_path or root / ATTESTATION
    signature_path = signature_path or root / SIGNATURE
    public_key_path = public_key_path or root / PUBLIC_KEY
    historical_bundle = default_surface and artifact_root is None
    verification_root = (
        (root / HISTORICAL_SURFACE_ROOT).resolve()
        if historical_bundle
        else (artifact_root or root).resolve()
    )
    if verification_root.is_symlink() or not verification_root.is_dir():
        raise SurfaceVerificationError(
            f"reviewed surface root is missing or invalid: {verification_root}"
        )
''',
        "verifier historical root selection",
    )
    replace_once(
        path,
        '        artifact = root / pure\n',
        '        artifact = verification_root / pure\n',
        "historical artifact lookup",
    )
    replace_once(
        path,
        '''        "review_mean_score": attestation["review_mean_score"],
    }
''',
        '''        "review_mean_score": attestation["review_mean_score"],
        "verification_mode": (
            "historical_bundle" if historical_bundle else "explicit_surface"
        ),
        "accepted_release_version": "0.5.1",
        "current_source_accepted": False if historical_bundle else None,
    }
''',
        "verifier result boundary",
    )
    replace_once(
        path,
        '''        "--expected-reviewer-id",
        required=True,
        help="reviewer identity from independently governed acceptance evidence",
''',
        '''        "--expected-reviewer-id",
        default=None,
        help="optional exact recheck of the bundled reviewer identity",
''',
        "optional reviewer id",
    )
    replace_once(
        path,
        '''        "--expected-reviewer-public-key-der-sha256",
        required=True,
        help="DER SHA-256 fingerprint from the same independent reviewer delegation",
''',
        '''        "--expected-reviewer-public-key-der-sha256",
        default=None,
        help="optional exact recheck of the bundled reviewer public-key fingerprint",
''',
        "optional reviewer fingerprint",
    )


def patch_tests() -> None:
    path = ROOT / "tests/test_operator_command_center_surface.py"
    replace_once(
        path,
        '''    @unittest.skipUnless(CURRENT_RELEASE == "0.5.1", "final signed surface not imported")
    def test_current_final_surface_and_independent_signature_verify(self) -> None:
        verifier = load_verifier()
        result = verifier.verify_surface(ROOT, **self.verifier_kwargs())
        self.assertTrue(result["ok"])
        self.assertEqual(result["files"], 21)
        self.assertEqual(result["reviewer_id"], REVIEWER_ID)
''',
        '''    @unittest.skipUnless(CURRENT_RELEASE == "0.5.1", "historical signed surface not imported")
    def test_bundled_historical_surface_and_independent_signature_verify(self) -> None:
        verifier = load_verifier()
        result = verifier.verify_surface(ROOT)
        self.assertTrue(result["ok"])
        self.assertEqual(result["files"], 21)
        self.assertEqual(result["reviewer_id"], REVIEWER_ID)
        self.assertEqual(result["verification_mode"], "historical_bundle")
        self.assertEqual(result["accepted_release_version"], "0.5.1")
        self.assertFalse(result["current_source_accepted"])
        historical_controller = (
            ROOT
            / verifier.HISTORICAL_SURFACE_ROOT
            / "skills/company-os/elastic-company-os/scripts/company_os_controller.py"
        )
        current_controller = (
            ROOT / "skills/company-os/elastic-company-os/scripts/company_os_controller.py"
        )
        self.assertTrue(historical_controller.is_file())
        self.assertNotEqual(
            verifier.sha256_bytes(historical_controller.read_bytes()),
            verifier.sha256_bytes(current_controller.read_bytes()),
        )
''',
        "historical signed surface test",
    )
    replace_once(
        path,
        '''    def test_missing_external_reviewer_trust_anchor_fails_closed(self) -> None:
        verifier = load_verifier()
        with self.assertRaisesRegex(
            verifier.SurfaceVerificationError,
            "externally supplied reviewer identity trust anchor is required",
        ):
            verifier.verify_surface(ROOT)
''',
        '''    def test_bundled_reviewer_trust_anchor_requires_no_environment(self) -> None:
        verifier = load_verifier()
        result = verifier.verify_surface(ROOT)
        self.assertEqual(result["reviewer_id"], REVIEWER_ID)
        self.assertEqual(
            result["reviewer_public_key_der_sha256"],
            REVIEWER_PUBLIC_KEY_DER_SHA256,
        )
''',
        "portable trust anchor test",
    )


def patch_ci() -> None:
    path = ROOT / ".github/workflows/ci.yml"
    replace_once(
        path,
        '''      - run: >-
          python3 scripts/verify_operator_command_center_surface.py
          --expected-reviewer-id "$COMPANY_OS_OCC_REVIEWER_ID"
          --expected-reviewer-public-key-der-sha256
          "$COMPANY_OS_OCC_REVIEWER_PUBLIC_KEY_DER_SHA256"
        env:
          COMPANY_OS_OCC_REVIEWER_ID: ${{ vars.COMPANY_OS_OCC_REVIEWER_ID }}
          COMPANY_OS_OCC_REVIEWER_PUBLIC_KEY_DER_SHA256: ${{ vars.COMPANY_OS_OCC_REVIEWER_PUBLIC_KEY_DER_SHA256 }}
''',
        '''      - run: python3 scripts/verify_operator_command_center_surface.py
''',
        "portable CI verification",
    )


def patch_readme() -> None:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    start = text.index("## Current reality\n")
    end = text.index("## Repository map\n")
    current_reality = '''## Current reality

Version 0.6.0 adds an outcome control plane to the canonical Company OS product line. Broad objectives can enter discovery without the operator already knowing the domain terminology. Before elastic execution, Company OS must close blocking unknowns with cited evidence, define observable artifact classes, compile executable independent evaluators, bind benchmark tiers, and prove those evaluators can distinguish poor, intermediate, and excellent candidates.

A bounded pilot remains limited to two managers, three workers per manager, and six total workers. Any larger elastic organization is production scale and requires a content bound authorization over the exact outcome, artifact, evaluator, benchmark, and calibration contracts. Contract drift invalidates the execution fabric. Final completion requires an accepted reality receipt derived from actual artifact evidence and bound to the original objective. A production team completion narrative cannot substitute for that receipt.

The 0.5.1 Operator Command Center review remains preserved as historical release evidence. Its exact twenty one reviewed files now live in a committed historical bundle materialized from carrier `166cbcc189074d70d0953e2897c85bc4791a39d2`. The verifier checks that bundle, the signed manifest, the bundled reviewer public key fingerprint, and the detached signature without environment variables or GitHub repository settings. It explicitly does not claim that the current 0.6.0 source files were accepted by the 0.5.1 reviewer.

The controller remains project isolated and fail closed. SQLite state, ordered events, leases, evidence, quality decisions, execution fabric state, and reality acceptance are locally auditable. Provider execution, protected recurring scheduling, spending, deployment, and other consequential external effects still require their existing authority boundaries.

'''
    text = text[:start] + current_reality + text[end:]
    old_verify = '''python3 scripts/verify_operator_command_center_surface.py \\
  --expected-reviewer-id "$COMPANY_OS_OCC_REVIEWER_ID" \\
  --expected-reviewer-public-key-der-sha256 \\
  "$COMPANY_OS_OCC_REVIEWER_PUBLIC_KEY_DER_SHA256"
'''
    if old_verify not in text:
        raise RuntimeError("README verification command was not found")
    text = text.replace(
        old_verify,
        "python3 scripts/verify_operator_command_center_surface.py\n",
        1,
    )
    text = text.replace(
        "/absolute/accepted-0.5.0/distribution-manifest.json",
        "/absolute/accepted-0.5.1/distribution-manifest.json",
    )
    text = text.replace("--prior-version 0.5.0", "--prior-version 0.5.1")
    obsolete = '''
The two Operator Command Center reviewer values are non-secret trust anchors,
but they must come from the independently governed Company OS delegation rather
than a repository default. CI reads them from repository variables and fails
closed when either value is absent or changed.
'''
    replacement = '''
The bundled reviewer identity and public key fingerprint are versioned integrity anchors for the preserved 0.5.1 historical review. A local clone needs no secret, environment variable, or repository configuration to verify it. Trust in the repository itself still comes from the release or commit channel used to obtain the clone.
'''
    if obsolete not in text:
        raise RuntimeError("obsolete reviewer variable guidance was not found")
    path.write_text(text.replace(obsolete, replacement, 1), encoding="utf-8")


def main() -> None:
    materialize_historical_surface()
    patch_verifier()
    patch_tests()
    patch_ci()
    patch_readme()
    print("portable historical verification applied")


if __name__ == "__main__":
    main()
