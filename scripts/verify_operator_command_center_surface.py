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
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = Path("programs/company-os-self-hosting")
SURFACE = PROGRAM / "OPERATOR_COMMAND_CENTER_ACCEPTED_SURFACE.json"
ATTESTATION = PROGRAM / "OPERATOR_COMMAND_CENTER_ACCEPTANCE_ATTESTATION.json"
SIGNATURE = PROGRAM / "OPERATOR_COMMAND_CENTER_ACCEPTANCE_SIGNATURE.bin"
PUBLIC_KEY = PROGRAM / "OPERATOR_COMMAND_CENTER_ACCEPTANCE_REVIEWER_PUBLIC.der"
EXPECTED = {
    "schema_version": 1,
    "attestation_id": "operator-command-center-v5-independent-acceptance",
    "checkpoint": "checkpoint:experience:5:2a556ed20ab06f5192066424d7fdfe07148f9fba98a78d10284d51c3a8637032",
    "decision": "accepted",
    "reviewer_delegation_evidence_id": "operator-command-center-exact-surface-delegation-v5",
    "reviewer_delegation_boundary": "product-surface acceptance only",
    "reviewer_delegation_expires_at": "2026-09-01T23:59:59Z",
    "program_version": 5,
    "outcome_id": "operator-command-center-v5",
    "work_id": "work-operator-command-center-v5",
    "rubric_version": "operator-command-center-v5-cycle-4",
    "critical_dimension_count": 13,
    "minimum_critical_score": 9.0,
    "review_mean_score": 9.22,
    "surface_file_count": 21,
}


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

    for key, expected in EXPECTED.items():
        if attestation.get(key) != expected:
            raise SurfaceVerificationError(f"attestation claim mismatch: {key}")
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

    if surface.get("schema_version") != 1:
        raise SurfaceVerificationError("surface schema is unsupported")
    if surface.get("surface_id") != "operator-command-center-v5-accepted-surface":
        raise SurfaceVerificationError("surface identity is invalid")
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

    if [entry["path"] for entry in normalized] != sorted(seen):
        raise SurfaceVerificationError("surface file entries are not globally path-sorted")
    aggregate = sha256_bytes(_canonical_files(normalized))
    if surface.get("aggregate_sha256") != aggregate:
        raise SurfaceVerificationError("surface aggregate does not match its file entries")
    if attestation.get("surface_aggregate_sha256") != aggregate:
        raise SurfaceVerificationError("attestation does not bind the surface aggregate")

    result = subprocess.run(
        [
            "openssl",
            "dgst",
            "-sha256",
            "-verify",
            str(public_key_path),
            "-keyform",
            "DER",
            "-signature",
            str(signature_path),
            str(attestation_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or "Verified OK" not in result.stdout:
        raise SurfaceVerificationError("independent acceptance signature is invalid")
    return {
        "ok": True,
        "files": len(normalized),
        "aggregate_sha256": aggregate,
        "attestation_sha256": sha256_bytes(attestation_bytes),
        "reviewer_id": expected_reviewer_id,
        "reviewer_public_key_der_sha256": public_key_fingerprint,
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
