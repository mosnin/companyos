"""Frozen golden vectors for the canonicalization the trust model rests on.

Every receipt, grant, manifest, and content address in Company OS is sealed by
these functions. Fixtures elsewhere seal themselves with the same production
hasher, so a silent change to canonical JSON (separators, key ordering, unicode
escaping, trailing newline) would keep those suites green while invalidating
every receipt ever issued in the field. These vectors are the one place that
pins the exact bytes and digests, so such a change fails loudly here.

If a change to canonicalization is ever intended, updating these vectors must be
a deliberate, reviewed act — never an automatic refresh.
"""
from __future__ import annotations

import hashlib
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTROLLER = _load(
    "skills/company-os/elastic-company-os/scripts/company_os_controller.py",
    "controller_canonical_vectors",
)
FOUNDRY = _load(
    "skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py",
    "foundry_canonical_vectors",
)

# (value, exact canonical string, sha256 of that string). ensure_ascii=True and
# no trailing newline are load-bearing and pinned here on purpose.
CONTROLLER_CANONICAL_JSON = [
    ({}, "{}", "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"),
    ({"b": 1, "a": 2}, '{"a":2,"b":1}', "d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772"),
    (
        {"z": [3, 2, 1], "nested": {"k": "vé", "t": True, "n": None}},
        '{"nested":{"k":"v\\u00e9","n":null,"t":true},"z":[3,2,1]}',
        "73049c393d3b6772b07dc67dacbae3692e652019ccb8563b4e5f638625fdfd7c",
    ),
    (
        {"unicode": "café–✓", "list": [{"x": 1}, {"y": 2}]},
        '{"list":[{"x":1},{"y":2}],"unicode":"caf\\u00e9\\u2013\\u2713"}',
        "25f88343f079b5e90cb82893d3d1967487e7f3f905fce983db46422ae2896376",
    ),
]

# (value, exact canonical bytes, sha256 hex). ensure_ascii=False (raw UTF-8) and
# the trailing newline are load-bearing and pinned here on purpose.
FOUNDRY_CANONICAL_BYTES = [
    ({}, b"{}\n", "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356"),
    ({"b": 1, "a": 2}, b'{"a":2,"b":1}\n', "81103aa69250ea56e887eaab3cd9bf363d341563f05d0676be389c3e40a72871"),
    (
        {"z": [3, 2, 1], "nested": {"k": "vé", "t": True, "n": None}},
        '{"nested":{"k":"vé","n":null,"t":true},"z":[3,2,1]}\n'.encode("utf-8"),
        "2523a2fa9029cc6ad01d06a3c2495efdef54d3de31f34e1395a482ebabcd6445",
    ),
    (
        {"unicode": "café–✓", "list": [{"x": 1}, {"y": 2}]},
        '{"list":[{"x":1},{"y":2}],"unicode":"café–✓"}\n'.encode("utf-8"),
        "3b71dbd831564240663b51a3f576ee23352c20ef90c22352018c0eced2e5496c",
    ),
]

# The command-envelope hash that keys idempotency and replay.
COMMAND_PAYLOAD_HASH = (
    "advance",
    {"a": 1, "b": [2, 3]},
    "4cf876d603524aa239a5f4a4b5656091e1dbe30c0112fef74cfcf71491cf593e",
)


class CanonicalDigestVectorTests(unittest.TestCase):
    def test_controller_canonical_json_is_byte_stable(self) -> None:
        for value, expected_json, expected_sha in CONTROLLER_CANONICAL_JSON:
            with self.subTest(value=value):
                encoded = CONTROLLER.canonical_json(value)
                self.assertEqual(encoded, expected_json)
                self.assertEqual(
                    hashlib.sha256(encoded.encode("utf-8")).hexdigest(), expected_sha
                )

    def test_controller_command_payload_hash_is_stable(self) -> None:
        command, payload, expected = COMMAND_PAYLOAD_HASH
        self.assertEqual(CONTROLLER.command_payload_hash(command, payload), expected)

    def test_foundry_canonical_bytes_and_digest_are_stable(self) -> None:
        for value, expected_bytes, expected_sha in FOUNDRY_CANONICAL_BYTES:
            with self.subTest(value=value):
                self.assertEqual(FOUNDRY.canonical_bytes(value), expected_bytes)
                self.assertEqual(FOUNDRY.digest(value), expected_sha)

    def test_controller_and_foundry_canonicalization_stay_distinct(self) -> None:
        # A regression guard against accidentally unifying the two: the controller
        # escapes non-ASCII and emits no trailing newline; the foundry does the
        # opposite. If these ever converge it must be a deliberate change.
        value = {"k": "é"}
        self.assertNotIn("\n", CONTROLLER.canonical_json(value))
        self.assertTrue(FOUNDRY.canonical_bytes(value).endswith(b"\n"))
        self.assertIn(b"\\u00e9", CONTROLLER.canonical_json(value).encode("ascii"))
        self.assertIn("é".encode("utf-8"), FOUNDRY.canonical_bytes(value))


if __name__ == "__main__":
    unittest.main()
