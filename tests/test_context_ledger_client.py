"""The context-ledger client: canonical parity, wire shaping, evidence bridge.

The ledger's whole value to the framework rests on one identity: the hash a
hosted ledger stores for a revision equals the hash the framework computes
for the same content. These tests pin the client's canonicalization to the
controller's (golden-vectored) encoding and prove the materialize path
yields files whose file-sha256 IS the ledger content address.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
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
    "context_ledger_under_test",
)
CONTROLLER = _load(
    "skills/company-os/elastic-company-os/scripts/company_os_controller.py",
    "controller_for_ledger_parity",
)


class CanonicalParityTests(unittest.TestCase):
    def test_client_canonicalization_matches_the_controller(self) -> None:
        vectors = [
            {},
            {"b": 1, "a": 2},
            {"z": [3, 2, 1], "nested": {"k": "vé", "t": True, "n": None}},
            {"unicode": "café–✓", "list": [{"x": 1}, {"y": 2}]},
            {"text": "line\nbreak\ttab", "rows": {"rows": [["a", "b"], ["", "✓"]]}},
        ]
        for value in vectors:
            self.assertEqual(
                LEDGER.canonical_json(value),
                CONTROLLER.canonical_json(value),
                value,
            )
            self.assertEqual(
                LEDGER.content_hash(value),
                hashlib.sha256(
                    CONTROLLER.canonical_json(value).encode("utf-8")
                ).hexdigest(),
            )


class FakeTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requests: list[dict] = []
        self.responses: list[dict] = []

        def transport(payload: dict) -> dict:
            self.requests.append(payload)
            return self.responses.pop(0)

        self.client = LEDGER.ContextLedgerClient(
            "https://ledger.example/mcp", "cos_test", transport=transport
        )

    def _ok(self, structured: object) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": json.dumps(structured)}],
                "structuredContent": structured,
            },
        }

    def test_document_put_sends_the_revision_checked_shape(self) -> None:
        self.responses.append(self._ok({"doc_slug": "okrs", "revision": 3}))
        result = self.client.document_put(
            kind="okrs",
            message="Advance Q3 key results",
            content={"period": "2026 Q3"},
            base_revision=2,
        )
        self.assertEqual(result["revision"], 3)
        request = self.requests[0]
        self.assertEqual(request["method"], "tools/call")
        self.assertEqual(request["params"]["name"], "document_put")
        arguments = request["params"]["arguments"]
        self.assertEqual(arguments["base_revision"], 2)
        self.assertEqual(arguments["kind"], "okrs")
        self.assertNotIn("doc_slug", arguments)

    def test_tool_error_raises_with_the_server_sentence(self) -> None:
        self.responses.append(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [{"type": "text", "text": 'Stale write: "okrs" is at revision 4'}],
                    "isError": True,
                },
            }
        )
        with self.assertRaises(LEDGER.ContextLedgerError) as caught:
            self.client.document_put(
                kind="okrs", message="x", content={}, base_revision=2
            )
        self.assertIn("Stale write", str(caught.exception))

    def test_push_brief_appends_a_brief_snapshot(self) -> None:
        self.responses.append(self._ok({"run_id": "m1", "type": "brief_snapshot"}))
        self.client.push_brief("m1", {"tokens_observed": 12000, "accepted_receipts": 2})
        arguments = self.requests[0]["params"]["arguments"]
        self.assertEqual(arguments["type"], "brief_snapshot")
        self.assertEqual(arguments["payload"]["accepted_receipts"], 2)

    def test_materialized_file_sha256_equals_the_ledger_content_hash(self) -> None:
        content = {
            "vision": "One governed company",
            "targets": ["Ship the ledger"],
            "measures": {"rows": [["NRR", "net revenue retention", "", "120%", "monthly"]]},
        }
        document = {
            "slug": "vmtm",
            "kind": "vmtm",
            "title": "Vision · Mission · Targets · Measures",
            "revision": 5,
            "contentHash": LEDGER.content_hash(content),
            "content": content,
        }
        self.responses.append(self._ok(document))
        with tempfile.TemporaryDirectory() as tmp:
            path = self.client.materialize("vmtm", Path(tmp))
            file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(file_hash, document["contentHash"])
        self.assertEqual(path.name, "vmtm@r5.canonical.json")

    def test_materialize_refuses_a_hash_mismatch(self) -> None:
        document = {
            "slug": "vmtm",
            "kind": "vmtm",
            "title": "VMTM",
            "revision": 5,
            "contentHash": "0" * 64,
            "content": {"vision": "tampered"},
        }
        self.responses.append(self._ok(document))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(LEDGER.ContextLedgerError):
                self.client.materialize("vmtm", Path(tmp))

    def test_context_bundle_pins_documents_by_hash(self) -> None:
        content = {"statement": "For builders who ship"}
        document = {
            "slug": "value-proposition",
            "kind": "value-proposition",
            "title": "Value Proposition",
            "revision": 2,
            "contentHash": LEDGER.content_hash(content),
            "content": content,
        }
        self.responses.append(self._ok(document))
        bundle = self.client.context_bundle(["value-proposition"])
        self.assertEqual(bundle["protocol"], "context-ledger.v1")
        self.assertEqual(bundle["documents"][0]["content_hash"], document["contentHash"])
        unsealed = {key: value for key, value in bundle.items() if key != "bundle_sha256"}
        self.assertEqual(bundle["bundle_sha256"], LEDGER.content_hash(unsealed))

    def test_rejects_a_token_without_the_cos_prefix(self) -> None:
        with self.assertRaises(LEDGER.ContextLedgerError):
            LEDGER.ContextLedgerClient("https://x/mcp", "vtr_wrong")

    def test_branch_parameter_threads_through_reads_and_writes(self) -> None:
        self.responses.append(self._ok({"protocol": "context-ledger.v1"}))
        self.client.config_pull(branch="plg-pivot")
        self.assertEqual(
            self.requests[0]["params"]["arguments"], {"branch": "plg-pivot"}
        )
        self.responses.append(self._ok({"doc_slug": "okrs", "revision": 1}))
        self.client.document_put(
            kind="okrs",
            message="Draft pivot OKRs",
            content={"period": "2027 Q1"},
            base_revision=4,
            branch="plg-pivot",
        )
        arguments = self.requests[1]["params"]["arguments"]
        self.assertEqual(arguments["branch"], "plg-pivot")
        self.assertEqual(arguments["base_revision"], 4)
        # Main reads never send the parameter at all.
        self.responses.append(self._ok({"slug": "okrs"}))
        self.client.document_get("okrs")
        self.assertNotIn("branch", self.requests[2]["params"]["arguments"])

    def test_branch_create_and_feedback_verbs_shape_their_calls(self) -> None:
        self.responses.append(self._ok({"slug": "plg-pivot"}))
        self.client.branch_create("PLG pivot", description="Self-serve motion")
        request = self.requests[0]["params"]
        self.assertEqual(request["name"], "branch_create")
        self.assertEqual(request["arguments"]["description"], "Self-serve motion")

        self.responses.append(self._ok([{"doc_slug": "product-app", "text": "love it"}]))
        rows = self.client.feedback_list(product_slug="product-app", limit=50)
        self.assertEqual(rows[0]["text"], "love it")
        self.assertEqual(
            self.requests[1]["params"]["arguments"],
            {"product_slug": "product-app", "limit": 50},
        )

        self.responses.append(self._ok({"doc_slug": "product-app"}))
        self.client.feedback_add(
            product_slug="product-app", source="review", text="Setup took 5 minutes"
        )
        self.assertEqual(self.requests[2]["params"]["name"], "feedback_add")


if __name__ == "__main__":
    unittest.main()
