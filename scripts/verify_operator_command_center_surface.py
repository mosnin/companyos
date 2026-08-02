#!/usr/bin/env python3
"""Verify the independently signed Operator Command Center product surface.

The reviewer delegation is intentionally not stored in this repository.  A
caller must supply both the reviewer identity and the DER public-key fingerprint
from independently governed acceptance evidence; repository-local keys,
attestations, and CI configuration cannot establish that trust on their own.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = Path("programs/company-os-self-hosting")
SURFACE = PROGRAM / "OPERATOR_COMMAND_CENTER_ACCEPTED_SURFACE.json"
ATTESTATION = PROGRAM / "OPERATOR_COMMAND_CENTER_ACCEPTANCE_ATTESTATION.json"
SIGNATURE = PROGRAM / "OPERATOR_COMMAND_CENTER_ACCEPTANCE_SIGNATURE.bin"
PUBLIC_KEY = PROGRAM / "OPERATOR_COMMAND_CENTER_ACCEPTANCE_REVIEWER_PUBLIC.der"
EXPECTED_REVIEWER_ID = "company-os-0.5.1-external-independent-surface-reviewer"
EXPECTED_REVIEWER_PUBLIC_KEY_DER_SHA256 = (
    "41826fdd1c0d78a414bba0876bdf840e01d6836430baab5f7d47a65719408aba"
)
EXPECTED_ATTESTATION = {
    "schema_version": 1,
    "acceptance_kind": "company-os-0.5.1-operator-command-center-regression-acceptance",
    "attestation_id": "operator-command-center-v5-company-os-0.5.1-independent-regression-acceptance",
    "checkpoint": "checkpoint:experience:5:2a556ed20ab06f5192066424d7fdfe07148f9fba98a78d10284d51c3a8637032",
    "company_os_release_version": "0.5.1",
    "decision": "accepted",
    "evidence_boundary": (
        "Accepts only the exact signed 21-file Operator Command Center product surface "
        "identified by carrier_binding as a Company OS 0.5.1 regression acceptance. "
        "It preserves the Operator Command Center v5 program and outcome semantics. "
        "It does not accept distribution integration, installation, provider execution, "
        "runtime or scheduler activation, deployment, production or customer mutation, "
        "or Chippy action."
    ),
    "reviewer_delegation_evidence_id": (
        "operator-command-center-exact-carrier-surface-delegation-company-os-0.5.1"
    ),
    "reviewer_delegation_boundary": (
        "one-time external independent acceptance of the exact 21-file carrier-bound "
        "Operator Command Center surface only"
    ),
    "reviewer_delegation_source": {
        "kind": "explicit-master-instruction",
        "source_thread_id": "019fa4e9-cd80-7bd2-9416-c8dce5a7e8c3",
    },
    "program_version": 5,
    "outcome_id": "operator-command-center-v5",
    "work_id": "work-operator-command-center-v5",
    "rubric_version": "operator-command-center-v5-company-os-0.5.1-regression-review",
    "critical_dimension_count": 13,
    "minimum_critical_score": 9.0,
    "surface_file_count": 21,
    "signature_algorithm": "RSA-3072-SHA256-PKCS1-v1_5",
}
EXPECTED_CARRIER_BINDING = {
    "canonical_authority_commit": "60211bd6962b733344c0c789272e96dc5db18a28",
    "runtime_source_commit": "315924018da7a7684787c79922dd3fd4887209c0",
}
EXPECTED_PRIOR_ATTESTATION_LINEAGE = {
    "accepted_artifact_commit": "09eada016b2da84eb0b49a0a3c1f5873a6dcbcaf",
    "accepted_artifact_git_tree": "6d1f73c486af4e8d7f8106f28db4f182863521fa",
    "attestation_id": "operator-command-center-v5-company-os-0.4.3-independent-acceptance",
    "attestation_sha256": "67d3702a4768302f0c9b22c376226a2edff3793d957c6747d4e2fa71404af8d9",
    "company_os_release_version": "0.4.3",
    "detached_signature_sha256": "46602064f59eeb347fb63d07f2987eda0cd808504a9fc21fbcd73f6c07ecb21b",
    "reviewed_implementation_base": "bf1a8a3918d37d248371528e4360c8f2ef0abc14",
    "reviewer_id": "company-os-0.4.3-independent-surface-reviewer",
    "reviewer_public_key_der_sha256": "d4148cf6bad103207e18a93b3d04f02a31e92c954b18250b0d63f565be7e5b8b",
    "surface_aggregate_sha256": "ed20e7f9026fca0614276cd1df3c5bc3114f3304876334eb149de37533c5d3f6",
    "surface_id": "operator-command-center-v5-company-os-0.4.3-accepted-surface",
    "surface_manifest_sha256": "84cddf4250ca509d899fdfef448466d32aa25ba33d945764765175f5aeab3016",
}
EXPECTED_PRIOR_SURFACE_LINEAGE = {
    "accepted_artifact_commit": "09eada016b2da84eb0b49a0a3c1f5873a6dcbcaf",
    "accepted_artifact_git_tree": "6d1f73c486af4e8d7f8106f28db4f182863521fa",
    "aggregate_sha256": "ed20e7f9026fca0614276cd1df3c5bc3114f3304876334eb149de37533c5d3f6",
    "surface_id": "operator-command-center-v5-company-os-0.4.3-accepted-surface",
    "surface_manifest_sha256": "84cddf4250ca509d899fdfef448466d32aa25ba33d945764765175f5aeab3016",
}
EXPECTED_SCORE_DIMENSIONS = (
    "North-star alignment", "User value", "Product coherence", "Differentiation",
    "Innovation", "Domain fit", "Information architecture", "Usability",
    "Accessibility", "Interaction quality", "Visual quality", "Brand cohesion",
    "Evidence integrity",
)
EXPECTED_SURFACE_PATHS = (
    ".github/workflows/ci.yml",
    "docs/design/operator-command-center-concept-v1.png",
    "programs/company-os-self-hosting/OPERATOR_COMMAND_CENTER_ACCEPTANCE_MATRIX.md",
    "programs/company-os-self-hosting/OPERATOR_COMMAND_CENTER_ACCEPTANCE_REPORT.md",
    "programs/company-os-self-hosting/OPERATOR_COMMAND_CENTER_DESIGN_SYSTEM.md",
    "programs/company-os-self-hosting/OPERATOR_COMMAND_CENTER_DESKTOP.jpg",
    "programs/company-os-self-hosting/OPERATOR_COMMAND_CENTER_MOBILE.jpg",
    "programs/company-os-self-hosting/OPERATOR_COMMAND_CENTER_PRODUCT_BRIEF.md",
    "programs/company-os-self-hosting/OPERATOR_COMMAND_CENTER_PROGRAM_CONTRACT.md",
    "programs/company-os-self-hosting/OPERATOR_COMMAND_CENTER_REALITY.md",
    "programs/company-os-self-hosting/OPERATOR_COMMAND_CENTER_RENDERED.html",
    "scripts/verify_operator_command_center_surface.py",
    "skills/company-os/elastic-company-os/SKILL.md",
    "skills/company-os/elastic-company-os/references/control-contract.md",
    "skills/company-os/elastic-company-os/scripts/company_os_controller.py",
    "skills/company-os/elastic-company-os/scripts/control_store.py",
    "skills/company-os/elastic-company-os/scripts/operator_brief.py",
    "skills/company-os/elastic-company-os/scripts/test_company_os_controller.py",
    "skills/company-os/elastic-company-os/scripts/test_control_store.py",
    "skills/company-os/elastic-company-os/scripts/test_operator_brief.py",
    "tests/test_operator_command_center_surface.py",
)


class SurfaceVerificationError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_git_oid(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_external_reviewer_delegation(
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


def _reject_constant(value: str) -> None:
    raise SurfaceVerificationError(f"non-finite JSON value is forbidden: {value}")


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SurfaceVerificationError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object,
            parse_constant=_reject_constant,
        )
    except (FileNotFoundError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SurfaceVerificationError(f"invalid JSON artifact: {path}") from error
    if not isinstance(value, dict):
        raise SurfaceVerificationError(f"JSON artifact must be an object: {path}")
    return value


def _canonical_files(entries: list[dict[str, Any]]) -> bytes:
    return json.dumps(
        entries,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _canonical_paths(paths: list[str]) -> bytes:
    return json.dumps(
        paths,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _validate_scores(attestation: dict[str, Any]) -> None:
    scores = attestation.get("review_scores")
    if not isinstance(scores, list) or len(scores) != len(EXPECTED_SCORE_DIMENSIONS):
        raise SurfaceVerificationError("attestation must retain exactly 13 product scores")
    observed: list[float] = []
    for expected_dimension, item in zip(EXPECTED_SCORE_DIMENSIONS, scores):
        if not isinstance(item, dict) or set(item) != {
            "dimension", "minimum", "score", "status"
        }:
            raise SurfaceVerificationError("attestation product score shape is invalid")
        score = item.get("score")
        if (
            item.get("dimension") != expected_dimension
            or item.get("minimum") != 9.0
            or item.get("status") != "pass"
            or isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
            or score < 9.0
        ):
            raise SurfaceVerificationError(
                f"attestation product score is invalid: {expected_dimension}"
            )
        observed.append(float(score))
    mean = round(sum(observed) / len(observed), 2)
    if attestation.get("critical_dimension_count") != len(observed):
        raise SurfaceVerificationError("attestation product score count is invalid")
    if attestation.get("review_mean_score") != mean:
        raise SurfaceVerificationError("attestation product score mean is invalid")


def _validate_public_key(public_key_path: Path) -> None:
    result = subprocess.run(
        [
            "openssl", "pkey", "-pubin", "-inform", "DER", "-in",
            str(public_key_path), "-text", "-noout",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    first_line = result.stdout.splitlines()[0] if result.stdout.splitlines() else ""
    if result.returncode != 0 or first_line != "Public-Key: (3072 bit)":
        raise SurfaceVerificationError("reviewer public key is not RSA-3072")


def _verify_detached_signature(
    attestation_path: Path, signature_path: Path, public_key_path: Path
) -> None:
    if len(signature_path.read_bytes()) != 384:
        raise SurfaceVerificationError("independent acceptance signature size is invalid")
    result = subprocess.run(
        [
            "openssl", "dgst", "-sha256", "-verify", str(public_key_path),
            "-keyform", "DER", "-signature", str(signature_path),
            str(attestation_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or "Verified OK" not in result.stdout:
        raise SurfaceVerificationError("independent acceptance signature is invalid")


def verify_surface(
    root: Path = ROOT,
    *,
    expected_reviewer_id: str | None = None,
    expected_reviewer_public_key_der_sha256: str | None = None,
    surface_path: Path | None = None,
    attestation_path: Path | None = None,
    signature_path: Path | None = None,
    public_key_path: Path | None = None,
) -> dict[str, Any]:
    expected_reviewer_id, expected_reviewer_public_key_der_sha256 = (
        _require_external_reviewer_delegation(
            expected_reviewer_id,
            expected_reviewer_public_key_der_sha256,
        )
    )
    root = root.resolve()
    surface_path = surface_path or root / SURFACE
    attestation_path = attestation_path or root / ATTESTATION
    signature_path = signature_path or root / SIGNATURE
    public_key_path = public_key_path or root / PUBLIC_KEY

    surface_bytes = surface_path.read_bytes()
    attestation_bytes = attestation_path.read_bytes()
    public_key_bytes = public_key_path.read_bytes()
    surface = read_json(surface_path)
    attestation = read_json(attestation_path)

    expected_attestation_keys = set(EXPECTED_ATTESTATION) | {
        "carrier_binding", "issued_at", "prior_accepted_surface_lineage",
        "review_mean_score", "review_scores", "reviewer_id",
        "reviewer_public_key_der_sha256", "surface_aggregate_sha256",
        "surface_manifest_path", "surface_manifest_sha256",
    }
    if set(attestation) != expected_attestation_keys:
        raise SurfaceVerificationError("attestation claim shape is invalid")
    for key, expected in EXPECTED_ATTESTATION.items():
        if attestation.get(key) != expected:
            raise SurfaceVerificationError(f"attestation claim mismatch: {key}")
    issued_at = attestation.get("issued_at")
    if not isinstance(issued_at, str) or not issued_at.endswith("Z"):
        raise SurfaceVerificationError("attestation issued_at is invalid")
    if attestation.get("reviewer_id") != expected_reviewer_id:
        raise SurfaceVerificationError(
            "attestation reviewer identity does not match the externally supplied trust anchor"
        )
    if attestation.get("surface_manifest_path") != SURFACE.as_posix():
        raise SurfaceVerificationError("attestation surface path is invalid")
    if attestation.get("surface_manifest_sha256") != sha256_bytes(surface_bytes):
        raise SurfaceVerificationError("attestation does not bind the surface manifest bytes")
    public_key_fingerprint = sha256_bytes(public_key_bytes)
    if attestation.get("reviewer_public_key_der_sha256") != public_key_fingerprint:
        raise SurfaceVerificationError("attestation does not bind the reviewer public key")
    if public_key_fingerprint != expected_reviewer_public_key_der_sha256:
        raise SurfaceVerificationError(
            "reviewer public key does not match the externally supplied trust anchor"
        )
    _validate_public_key(public_key_path)

    carrier_binding = attestation.get("carrier_binding")
    if not isinstance(carrier_binding, dict) or set(carrier_binding) != {
        "accepted_carrier_commit", "accepted_carrier_git_tree",
        "canonical_authority_commit", "runtime_source_commit",
    }:
        raise SurfaceVerificationError("attestation carrier binding shape is invalid")
    if (
        not _is_git_oid(carrier_binding.get("accepted_carrier_commit"))
        or not _is_git_oid(carrier_binding.get("accepted_carrier_git_tree"))
    ):
        raise SurfaceVerificationError("attestation carrier evidence is not a 40-hex Git identity")
    for key, expected in EXPECTED_CARRIER_BINDING.items():
        if carrier_binding.get(key) != expected:
            raise SurfaceVerificationError(f"attestation carrier binding mismatch: {key}")
    if attestation.get("prior_accepted_surface_lineage") != EXPECTED_PRIOR_ATTESTATION_LINEAGE:
        raise SurfaceVerificationError("attestation prior 0.4.3 lineage is invalid")
    _validate_scores(attestation)

    if set(surface) != {
        "aggregate_algorithm", "aggregate_sha256", "carrier_commit",
        "carrier_git_tree", "company_os_release_version", "files",
        "path_set_sha256", "prior_surface_lineage", "schema_version", "surface_id",
    }:
        raise SurfaceVerificationError("surface claim shape is invalid")
    if surface.get("schema_version") != 1:
        raise SurfaceVerificationError("surface schema is unsupported")
    if surface.get("surface_id") != "operator-command-center-v5-company-os-0.5.1-accepted-surface":
        raise SurfaceVerificationError("surface identity is invalid")
    if surface.get("company_os_release_version") != "0.5.1":
        raise SurfaceVerificationError("surface release version is invalid")
    if surface.get("aggregate_algorithm") != (
        "sha256(canonical-json(files,sort_keys=true,separators=comma-colon,utf8))"
    ):
        raise SurfaceVerificationError("surface aggregate algorithm is invalid")
    if (
        surface.get("carrier_commit") != carrier_binding["accepted_carrier_commit"]
        or surface.get("carrier_git_tree") != carrier_binding["accepted_carrier_git_tree"]
    ):
        raise SurfaceVerificationError("surface carrier evidence does not match attestation")
    if surface.get("prior_surface_lineage") != EXPECTED_PRIOR_SURFACE_LINEAGE:
        raise SurfaceVerificationError("surface prior 0.4.3 lineage is invalid")
    entries = surface.get("files")
    if not isinstance(entries, list) or len(entries) != 21:
        raise SurfaceVerificationError("surface must bind exactly 21 files")
    if any(not isinstance(entry, dict) for entry in entries):
        raise SurfaceVerificationError("surface file entry is invalid")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        path_value = entry.get("path")
        digest = entry.get("sha256")
        size = entry.get("size")
        if not isinstance(path_value, str) or not path_value:
            raise SurfaceVerificationError("surface file path is invalid")
        pure = PurePosixPath(path_value)
        if pure.is_absolute() or ".." in pure.parts or path_value != pure.as_posix():
            raise SurfaceVerificationError(f"surface file path escapes the repository: {path_value}")
        if path_value in seen:
            raise SurfaceVerificationError(f"surface file path is duplicated: {path_value}")
        seen.add(path_value)
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise SurfaceVerificationError(f"surface file digest is invalid: {path_value}")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise SurfaceVerificationError(f"surface file size is invalid: {path_value}")
        artifact = root / pure
        if artifact.is_symlink() or not artifact.is_file():
            raise SurfaceVerificationError(f"surface file is missing or not regular: {path_value}")
        payload = artifact.read_bytes()
        if len(payload) != size or sha256_bytes(payload) != digest:
            raise SurfaceVerificationError(f"surface file drifted: {path_value}")
        normalized.append({"path": path_value, "sha256": digest, "size": size})

    normalized_paths = [entry["path"] for entry in normalized]
    if normalized_paths != sorted(seen):
        raise SurfaceVerificationError("surface file entries are not globally path-sorted")
    if tuple(normalized_paths) != EXPECTED_SURFACE_PATHS:
        raise SurfaceVerificationError("surface does not bind the exact 21-file product inventory")
    path_set_digest = sha256_bytes(_canonical_paths(normalized_paths))
    if surface.get("path_set_sha256") != path_set_digest:
        raise SurfaceVerificationError("surface path-set digest is invalid")
    aggregate = sha256_bytes(_canonical_files(normalized))
    if surface.get("aggregate_sha256") != aggregate:
        raise SurfaceVerificationError("surface aggregate does not match its file entries")
    if attestation.get("surface_aggregate_sha256") != aggregate:
        raise SurfaceVerificationError("attestation does not bind the surface aggregate")

    _verify_detached_signature(attestation_path, signature_path, public_key_path)
    return {
        "ok": True,
        "files": len(normalized),
        "aggregate_sha256": aggregate,
        "attestation_sha256": sha256_bytes(attestation_bytes),
        "reviewer_id": expected_reviewer_id,
        "reviewer_public_key_der_sha256": public_key_fingerprint,
        "carrier_commit": carrier_binding["accepted_carrier_commit"],
        "carrier_git_tree": carrier_binding["accepted_carrier_git_tree"],
        "review_mean_score": attestation["review_mean_score"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--expected-reviewer-id",
        required=True,
        help="reviewer identity from independently governed acceptance evidence",
    )
    parser.add_argument(
        "--expected-reviewer-public-key-der-sha256",
        required=True,
        help="DER SHA-256 fingerprint from the same independent reviewer delegation",
    )
    args = parser.parse_args()
    try:
        result = verify_surface(
            args.root,
            expected_reviewer_id=args.expected_reviewer_id,
            expected_reviewer_public_key_der_sha256=(
                args.expected_reviewer_public_key_der_sha256
            ),
        )
    except (OSError, SurfaceVerificationError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
