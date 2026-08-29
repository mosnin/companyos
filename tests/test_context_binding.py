"""Context bundles: selected by work class, verified offline, bound fail-closed.

The controller never fetches — the client pulls a sealed bundle at compile
time and mission_control.bind_context re-verifies every hash before the
mission carries the references. These tests prove the seal and per-document
hashes are actually enforced, and that binding stores references (not
prose) inside a resealed state.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LEDGER = _load(
    "skills/company-os/company-context-ledger/scripts/context_ledger.py",
    "context_ledger_for_binding",
)
MISSION = _load(
    "skills/company-os/mission-execution-control/scripts/mission_control.py",
    "mission_control_for_binding",
)


def sealed_bundle() -> dict:
    content = {"vision": "One governed company", "targets": ["Ship"]}
    documents = [
        {
            "slug": "vmtm",
            "kind": "vmtm",
            "title": "VMTM",
            "revision": 3,
            "content_hash": LEDGER.content_hash(content),
            "content": content,
        }
    ]
    bundle = {"protocol": "context-ledger.v1", "documents": documents}
    return {**bundle, "bundle_sha256": LEDGER.content_hash(bundle)}


class BindContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = MISSION.initialize_state(
            "bind-mission",
            "Ship a runnable binding fixture",
            started_at="2026-08-29T00:00:00Z",
            mission_class="bounded_feature",
        )

    def test_valid_bundle_binds_references_and_reseals(self) -> None:
        bundle = sealed_bundle()
        bound = MISSION.bind_context(
            self.state, bundle, bound_at="2026-08-29T00:05:00Z"
        )
        record = bound["context_bundle"]
        self.assertEqual(record["bundle_sha256"], bundle["bundle_sha256"])
        self.assertEqual(
            record["documents"],
            [
                {
                    "slug": "vmtm",
                    "kind": "vmtm",
                    "revision": 3,
                    "content_hash": bundle["documents"][0]["content_hash"],
                }
            ],
        )
        # References only — the prose stays in the ledger.
        self.assertNotIn("content", record["documents"][0])
        # The state is resealed, so downstream verify_state still passes.
        MISSION.verify_state(bound)

    def test_tampered_document_content_is_rejected(self) -> None:
        bundle = sealed_bundle()
        bundle["documents"][0]["content"]["vision"] = "tampered"
        # Reseal the bundle so ONLY the per-document hash catches it.
        unsealed = {k: v for k, v in bundle.items() if k != "bundle_sha256"}
        bundle["bundle_sha256"] = LEDGER.content_hash(unsealed)
        with self.assertRaises(MISSION.MissionControlError) as caught:
            MISSION.bind_context(self.state, bundle, bound_at="2026-08-29T00:05:00Z")
        self.assertEqual(caught.exception.code, "E_DIGEST")

    def test_tampered_seal_is_rejected(self) -> None:
        bundle = sealed_bundle()
        bundle["documents"][0]["revision"] = 4
        with self.assertRaises(MISSION.MissionControlError) as caught:
            MISSION.bind_context(self.state, bundle, bound_at="2026-08-29T00:05:00Z")
        self.assertEqual(caught.exception.code, "E_DIGEST")

    def test_wrong_protocol_is_rejected(self) -> None:
        bundle = sealed_bundle()
        bundle["protocol"] = "context-ledger.v0"
        with self.assertRaises(MISSION.MissionControlError):
            MISSION.bind_context(self.state, bundle, bound_at="2026-08-29T00:05:00Z")


class BundleForTests(unittest.TestCase):
    def test_bundle_for_selects_by_work_class_and_seals(self) -> None:
        contents = {
            "vmtm": {"vision": "V"},
            "tech-stack": {"principles": ["boring by default"]},
            "brand-positioning": {"statement": "For builders"},
        }
        config = {
            "protocol": "context-ledger.v1",
            "documents": [
                {"slug": slug, "kind": slug, "status": "active", "contentHash": LEDGER.content_hash(body)}
                for slug, body in contents.items()
            ],
        }
        responses = [config] + [
            {
                "slug": slug,
                "kind": slug,
                "title": slug,
                "revision": 1,
                "contentHash": LEDGER.content_hash(body),
                "content": body,
            }
            # implementation pulls vmtm + tech-stack but NOT brand-positioning
            for slug, body in contents.items()
            if slug != "brand-positioning"
        ]

        def transport(payload: dict) -> dict:
            structured = responses.pop(0)
            return {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {
                    "content": [{"type": "text", "text": json.dumps(structured)}],
                    "structuredContent": structured,
                },
            }

        client = LEDGER.ContextLedgerClient(
            "https://ledger.example/mcp", "cos_test", transport=transport
        )
        bundle = client.bundle_for("implementation")
        slugs = [doc["slug"] for doc in bundle["documents"]]
        self.assertEqual(slugs, ["vmtm", "tech-stack"])
        # Sealed exactly the way bind_context will verify it.
        state = MISSION.initialize_state(
            "select-mission",
            "Ship a runnable selection fixture",
            started_at="2026-08-29T00:00:00Z",
            mission_class="quick_build",
        )
        bound = MISSION.bind_context(state, bundle, bound_at="2026-08-29T00:01:00Z")
        self.assertEqual(len(bound["context_bundle"]["documents"]), 2)


if __name__ == "__main__":
    unittest.main()
