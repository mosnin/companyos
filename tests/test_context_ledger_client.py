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


class FakeTransport:
    """A recorded, queued transport shared by the wire-shaping suites."""

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


class FakeTransportTests(FakeTransport, unittest.TestCase):
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


class V16WireShapeTests(FakeTransport, unittest.TestCase):
    """The v1.6 verbs: argument shaping, paging, and tolerant list reads."""

    def test_document_list_pages_and_drains_like_config_documents(self) -> None:
        self.responses.append(
            self._ok(
                {
                    "documents": [{"slug": "icp"}, {"slug": "okrs"}],
                    "has_more": True,
                    "cursor": "okrs",
                    "document_count": 3,
                }
            )
        )
        self.responses.append(
            self._ok(
                {"documents": [{"slug": "vmtm"}], "has_more": False, "cursor": "vmtm"}
            )
        )
        documents = self.client.document_list_all(view="strategy", page_size=2)
        self.assertEqual([row["slug"] for row in documents], ["icp", "okrs", "vmtm"])
        first, second = (request["params"]["arguments"] for request in self.requests)
        self.assertEqual(first, {"view": "strategy", "limit": 2})
        # The second page carries the cursor the first one handed back.
        self.assertEqual(second["cursor"], "okrs")

    def test_an_unpaged_server_ends_the_drain_on_the_first_call(self) -> None:
        self.responses.append(self._ok({"documents": [{"slug": "okrs"}]}))
        self.assertEqual(len(self.client.document_list_all()), 1)
        self.assertEqual(len(self.requests), 1)

    def test_list_verbs_read_a_bare_array_or_an_envelope(self) -> None:
        # The canonical shape is a bare array, matching feedback_list.
        self.responses.append(self._ok([{"slug": "plg-pivot", "status": "open"}]))
        self.assertEqual(self.client.branch_list(status="open")[0]["slug"], "plg-pivot")
        self.assertEqual(
            self.requests[0]["params"]["arguments"], {"status": "open"}
        )
        # A deployment that wrapped it must not strand the caller.
        self.responses.append(self._ok({"branches": [{"slug": "q4"}]}))
        self.assertEqual(self.client.branch_list()[0]["slug"], "q4")
        self.responses.append(self._ok({"merges": [{"merge_id": "mrg1"}]}))
        self.assertEqual(self.client.merge_list()[0]["merge_id"], "mrg1")

    def test_branch_and_merge_verbs_shape_their_arguments(self) -> None:
        self.responses.append(self._ok({"branch": "plg-pivot", "entries": []}))
        self.client.branch_diff("plg-pivot")
        self.assertEqual(self.requests[0]["params"]["name"], "branch_diff")
        self.assertEqual(self.requests[0]["params"]["arguments"], {"branch": "plg-pivot"})

        self.responses.append(self._ok({"merged": 2, "merge_id": "mrg1"}))
        self.client.branch_merge("plg-pivot", message="Land it")
        self.assertEqual(
            self.requests[1]["params"]["arguments"],
            {"branch": "plg-pivot", "message": "Land it"},
        )

        self.responses.append(self._ok({"reverted": 1, "archived": 0}))
        self.client.merge_revert("mrg1")
        self.assertEqual(self.requests[2]["params"]["arguments"], {"merge_id": "mrg1"})

    def test_document_revert_sends_the_target_sequence(self) -> None:
        self.responses.append(
            self._ok({"seq": 7, "content_hash": "a" * 64, "reverted_from": 3})
        )
        result = self.client.document_revert("okrs", to_seq=3, message="Undo Q3")
        # The returned seq is the NEW revision, never the one restored from.
        self.assertEqual(result["seq"], 7)
        self.assertEqual(result["reverted_from"], 3)
        self.assertEqual(
            self.requests[0]["params"]["arguments"],
            {"slug": "okrs", "to_seq": 3, "message": "Undo Q3"},
        )
        self.assertNotIn("branch", self.requests[0]["params"]["arguments"])

    def test_schema_describe_filters_are_optional(self) -> None:
        self.responses.append(self._ok({"views": [], "kinds": []}))
        self.client.schema_describe()
        self.assertEqual(self.requests[0]["params"]["arguments"], {})
        self.responses.append(self._ok({"views": [], "kinds": []}))
        self.client.schema_describe(kind="okrs")
        self.assertEqual(self.requests[1]["params"]["arguments"], {"kind": "okrs"})

    def test_resource_uris_follow_the_v16_grammar(self) -> None:
        build = LEDGER.ContextLedgerClient.resource_uri
        self.assertEqual(build("acme", slug="okrs"), "companyos://acme/document/okrs")
        self.assertEqual(
            build("acme", slug="okrs", seq=4), "companyos://acme/document/okrs@4"
        )
        self.assertEqual(
            build("acme", slug="okrs", branch="plg-pivot"),
            "companyos://acme/branch/plg-pivot/document/okrs",
        )
        self.assertEqual(build("acme", branch="plg-pivot"), "companyos://acme/branch/plg-pivot")
        self.assertEqual(build("acme", merge_id="mrg1"), "companyos://acme/merge/mrg1")
        self.assertEqual(build("acme", schema=True), "companyos://acme/schema")
        self.assertEqual(build("acme", kind="okrs"), "companyos://acme/schema/okrs")
        with self.assertRaises(LEDGER.ContextLedgerError):
            build("acme")

    def test_read_resource_uses_the_mcp_resources_method(self) -> None:
        self.responses.append(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"contents": [{"uri": "companyos://acme/document/okrs"}]},
            }
        )
        contents = self.client.read_resource("companyos://acme/document/okrs")
        self.assertEqual(self.requests[0]["method"], "resources/read")
        self.assertEqual(contents[0]["uri"], "companyos://acme/document/okrs")

    def test_the_existing_verbs_are_untouched_by_v16(self) -> None:
        """Additive means additive: a v1.5 call still looks exactly the same."""
        self.responses.append(self._ok({"protocol": "context-ledger.v1"}))
        self.client.config_pull()
        self.assertEqual(self.requests[0]["params"]["arguments"], {})
        self.responses.append(self._ok([{"text": "love it"}]))
        self.assertEqual(self.client.feedback_list()[0]["text"], "love it")



if __name__ == "__main__":
    unittest.main()
