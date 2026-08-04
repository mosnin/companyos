#!/usr/bin/env python3
"""Minimal RSA-3072 PKCS#1 v1.5 trust verification for Company OS records."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import stat
from pathlib import Path
from typing import Any


SCHEME = "company-os.rsa-3072-sha256-pkcs1-v1_5.v1"
SIGNATURE = re.compile(r"^[A-Za-z0-9_-]{512}$")
KEY_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
PEM_HEADER = b"-----BEGIN PUBLIC KEY-----"
PEM_FOOTER = b"-----END PUBLIC KEY-----"
RSA_ALGORITHM = bytes.fromhex("300d06092a864886f70d0101010500")
SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


class TrustError(ValueError):
    """Raised when a trust anchor or detached signature is invalid."""


def _length(data: bytes, offset: int) -> tuple[int, int]:
    if offset >= len(data):
        raise TrustError("RSA public key DER length is truncated")
    first = data[offset]
    if first < 0x80:
        return first, offset + 1
    count = first & 0x7F
    if count == 0 or count > 4 or offset + 1 + count > len(data):
        raise TrustError("RSA public key DER length is invalid")
    raw = data[offset + 1 : offset + 1 + count]
    if raw[0] == 0:
        raise TrustError("RSA public key DER length is noncanonical")
    value = int.from_bytes(raw, "big")
    if value < 0x80:
        raise TrustError("RSA public key DER length is noncanonical")
    return value, offset + 1 + count


def _tlv(data: bytes, offset: int, tag: int, label: str) -> tuple[bytes, int]:
    if offset >= len(data) or data[offset] != tag:
        raise TrustError(f"RSA public key {label} tag is invalid")
    size, start = _length(data, offset + 1)
    end = start + size
    if end > len(data):
        raise TrustError(f"RSA public key {label} is truncated")
    return data[start:end], end


def _integer(data: bytes, offset: int, label: str) -> tuple[int, int]:
    raw, end = _tlv(data, offset, 0x02, label)
    if not raw or raw[0] & 0x80:
        raise TrustError(f"RSA public key {label} is not a positive integer")
    if len(raw) > 1 and raw[0] == 0 and not raw[1] & 0x80:
        raise TrustError(f"RSA public key {label} is noncanonical")
    return int.from_bytes(raw, "big"), end


def _pem_der(raw: bytes) -> bytes:
    lines = raw.strip().splitlines()
    if len(lines) < 3 or lines[0] != PEM_HEADER or lines[-1] != PEM_FOOTER:
        raise TrustError("master public key must be a PEM SubjectPublicKeyInfo key")
    body = b"".join(lines[1:-1])
    if not body or any(not line or line.strip() != line for line in lines[1:-1]):
        raise TrustError("master public key PEM encoding is invalid")
    try:
        return base64.b64decode(body, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise TrustError("master public key PEM body is invalid") from error


def parse_public_key(raw: bytes) -> tuple[int, int]:
    der = _pem_der(raw)
    outer, end = _tlv(der, 0, 0x30, "SubjectPublicKeyInfo")
    if end != len(der):
        raise TrustError("RSA public key has trailing DER bytes")
    algorithm, offset = _tlv(outer, 0, 0x30, "algorithm")
    if algorithm != RSA_ALGORITHM[2:]:
        raise TrustError("public key algorithm is not canonical rsaEncryption")
    bit_string, offset = _tlv(outer, offset, 0x03, "bit string")
    if offset != len(outer) or not bit_string or bit_string[0] != 0:
        raise TrustError("RSA public key bit string is invalid")
    rsa, rsa_end = _tlv(bit_string[1:], 0, 0x30, "key sequence")
    if rsa_end != len(bit_string) - 1:
        raise TrustError("RSA public key sequence has trailing bytes")
    modulus, rsa_offset = _integer(rsa, 0, "modulus")
    exponent, rsa_offset = _integer(rsa, rsa_offset, "exponent")
    if rsa_offset != len(rsa):
        raise TrustError("RSA public key integers have trailing bytes")
    if modulus.bit_length() != 3072 or exponent != 65537:
        raise TrustError("public key must be RSA-3072 with exponent 65537")
    return modulus, exponent


def read_public_key(path: Path, label: str) -> tuple[bytes, int, int]:
    if path.is_symlink():
        raise TrustError(f"{label} must not be a symlink")
    try:
        status = path.lstat()
        raw = path.read_bytes()
    except OSError as error:
        raise TrustError(f"{label} could not be read: {error}") from error
    if not stat.S_ISREG(status.st_mode):
        raise TrustError(f"{label} must be a regular file")
    modulus, exponent = parse_public_key(raw)
    return raw, modulus, exponent


def unsigned_record(record: dict[str, Any]) -> dict[str, Any]:
    authentication = record.get("authentication")
    if not isinstance(authentication, dict):
        raise TrustError("record authentication is invalid")
    if set(authentication) != {"scheme", "key_id", "public_key_sha256", "signature"}:
        raise TrustError("record authentication keys differ")
    if authentication.get("scheme") != SCHEME:
        raise TrustError("record authentication scheme is unsupported")
    key_id = authentication.get("key_id")
    if not isinstance(key_id, str) or not KEY_ID.fullmatch(key_id):
        raise TrustError("record authentication key_id is invalid")
    public_digest = authentication.get("public_key_sha256")
    if (
        not isinstance(public_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", public_digest)
    ):
        raise TrustError("record public-key digest is invalid")
    unsigned = dict(record)
    unsigned["authentication"] = {
        "scheme": SCHEME,
        "key_id": key_id,
        "public_key_sha256": public_digest,
    }
    return unsigned


def verify_record(
    record: dict[str, Any],
    canonical_payload: bytes,
    public_key_path: Path,
    label: str,
) -> str:
    unsigned_record(record)
    authentication = record["authentication"]
    raw_key, modulus, exponent = read_public_key(public_key_path, f"{label} public key")
    key_digest = hashlib.sha256(raw_key).hexdigest()
    if not hmac.compare_digest(authentication["public_key_sha256"], key_digest):
        raise TrustError(f"{label} public key does not match the signed trust anchor")
    signature_text = authentication.get("signature")
    if not isinstance(signature_text, str) or not SIGNATURE.fullmatch(signature_text):
        raise TrustError(f"{label} signature encoding is invalid")
    try:
        signature = base64.urlsafe_b64decode(signature_text + "==")
    except (ValueError, base64.binascii.Error) as error:
        raise TrustError(f"{label} signature encoding is invalid") from error
    if len(signature) != 384:
        raise TrustError(f"{label} signature length is invalid")
    signature_value = int.from_bytes(signature, "big")
    if signature_value >= modulus:
        raise TrustError(f"{label} signature representative is out of range")
    encoded = pow(signature_value, exponent, modulus).to_bytes(384, "big")
    digest_info = SHA256_DIGEST_INFO + hashlib.sha256(canonical_payload).digest()
    expected = b"\x00\x01" + (b"\xff" * (384 - len(digest_info) - 3)) + b"\x00" + digest_info
    if not hmac.compare_digest(encoded, expected):
        raise TrustError(f"{label} signature does not verify")
    return key_digest
