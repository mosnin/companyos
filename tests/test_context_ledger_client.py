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
import io
import json
import tempfile
import unittest
import urllib.error
import urllib.request
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


class V110WireShapeTests(FakeTransport, unittest.TestCase):
    """Minor 1.10: the work queue, and search that can reach quotes and facts."""

    def test_context_search_stays_a_bare_array_without_include(self) -> None:
        self.responses.append(self._ok([{"slug": "swot-analysis", "snippet": "churn"}]))
        hits = self.client.context_search("churn", limit=5)
        self.assertEqual(self.requests[0]["params"]["name"], "context_search")
        self.assertEqual(
            self.requests[0]["params"]["arguments"], {"query": "churn", "limit": 5}
        )
        self.assertIsInstance(hits, list)

    def test_context_search_include_asks_for_the_envelope(self) -> None:
        self.responses.append(
            self._ok({"documents": [], "quotes": [{"quote": "we churn"}], "facts": []})
        )
        hits = self.client.context_search("churn", include=["quotes", "facts"])
        self.assertEqual(
            self.requests[0]["params"]["arguments"],
            {"query": "churn", "include": ["quotes", "facts"]},
        )
        self.assertEqual(hits["quotes"][0]["quote"], "we churn")

    def test_business_context_read_verbs_shape_their_calls(self) -> None:
        self.responses.extend([
            self._ok({"facts": [], "total": 0}),
            self._ok({"unevidenced": []}),
            self._ok({"kind": "okrs", "facts": []}),
            self._ok({"programs": []}),
        ])
        self.client.context_known(topic="pricing", search="enterprise")
        self.client.context_gaps()
        self.client.context_compose("okrs")
        self.client.portfolio_snapshot(branch="growth-plan")
        calls = [request["params"] for request in self.requests]
        self.assertEqual(calls[0], {"name": "context_known", "arguments": {"topic": "pricing", "search": "enterprise"}})
        self.assertEqual(calls[1], {"name": "context_gaps", "arguments": {}})
        self.assertEqual(calls[2], {"name": "context_compose", "arguments": {"kind": "okrs"}})
        self.assertEqual(calls[3], {"name": "portfolio_snapshot", "arguments": {"branch": "growth-plan"}})

    def test_business_context_packet_indexes_all_and_binds_relevant_bodies(self) -> None:
        value_content = {"statement": "For governed agent teams"}
        research_content = {"findings": ["Enterprise teams need auditability"]}
        index = [
            {
                "slug": "value-proposition",
                "kind": "value-proposition",
                "title": "Value Proposition",
                "revision": 2,
                "contentHash": LEDGER.content_hash(value_content),
                "status": "active",
            },
            {
                "slug": "market-research",
                "kind": "market-research",
                "title": "Market Research",
                "revision": 4,
                "contentHash": LEDGER.content_hash(research_content),
                "status": "active",
            },
        ]
        self.responses.extend([
            self._ok({"documents": index, "documents_has_more": False}),
            self._ok({"documents": [{"slug": "market-research"}], "quotes": [], "facts": []}),
            self._ok({**index[0], "content": value_content}),
            self._ok({**index[1], "content": research_content}),
            self._ok({"facts": [{"claim": "Auditability is required"}]}),
            self._ok({"unevidenced": [{"topic": "pricing"}]}),
            self._ok({"programs": [{"id": "growth"}]}),
        ])
        packet = self.client.business_context_packet("Choose an enterprise segment")
        self.assertEqual("company-os.business-context.v1", packet["protocol"])
        self.assertEqual(2, len(packet["context_index"]))
        self.assertEqual(2, len(packet["ledger"]["documents"]))
        self.assertEqual("relevant", packet["scope"])
        self.assertEqual([], packet["search_evidence"]["quotes"])
        unsealed = {key: value for key, value in packet.items() if key != "packet_sha256"}
        self.assertEqual(LEDGER.content_hash(unsealed), packet["packet_sha256"])
        self.assertEqual(
            ["config_pull", "context_search", "document_get", "document_get", "context_known", "context_gaps", "portfolio_snapshot"],
            [request["params"]["name"] for request in self.requests],
        )

    def test_full_business_context_binds_every_active_document(self) -> None:
        contents = [{"value": "one"}, {"value": "two"}]
        index = [
            {
                "slug": f"doc-{number}",
                "kind": "custom",
                "title": f"Document {number}",
                "revision": 1,
                "contentHash": LEDGER.content_hash(contents[number - 1]),
                "status": "active",
            }
            for number in (1, 2)
        ]
        self.responses.extend([
            self._ok({"documents": index, "documents_has_more": False}),
            self._ok({**index[0], "content": contents[0]}),
            self._ok({**index[1], "content": contents[1]}),
            self._ok({"facts": []}),
            self._ok({"unevidenced": []}),
            self._ok({"programs": []}),
        ])
        packet = self.client.business_context_packet("Review the company", full=True)
        self.assertEqual("full", packet["scope"])
        self.assertEqual(["doc-1", "doc-2"], [item["slug"] for item in packet["ledger"]["documents"]])
        self.assertNotIn("context_search", [request["params"]["name"] for request in self.requests])

    def test_work_verbs_shape_their_arguments(self) -> None:
        self.responses.append(self._ok({"requests": [], "count": 0}))
        self.client.work_list(status="open", view="marketing", limit=10)
        self.assertEqual(self.requests[0]["params"]["name"], "work_list")
        self.assertEqual(
            self.requests[0]["params"]["arguments"],
            {"status": "open", "view": "marketing", "limit": 10},
        )

        self.responses.append(self._ok({"requests": [], "count": 0}))
        self.client.work_list()
        self.assertEqual(self.requests[1]["params"]["arguments"], {})

        self.responses.append(
            self._ok({"seq": 7, "status": "claimed", "claimed_by": "writer", "claimed_at": 1})
        )
        claimed = self.client.work_claim(7)
        self.assertEqual(self.requests[2]["params"]["name"], "work_claim")
        self.assertEqual(self.requests[2]["params"]["arguments"], {"seq": 7})
        self.assertEqual(claimed["status"], "claimed")

        self.responses.append(self._ok({"seq": 7, "status": "done", "done_at": 2}))
        self.client.work_complete(
            7,
            "Drafted the pricing page",
            documents=[{"slug": "pricing-page", "branch": "work-7"}],
            branch="work-7",
        )
        self.assertEqual(self.requests[3]["params"]["name"], "work_complete")
        self.assertEqual(
            self.requests[3]["params"]["arguments"],
            {
                "seq": 7,
                "summary": "Drafted the pricing page",
                "documents": [{"slug": "pricing-page", "branch": "work-7"}],
                "branch": "work-7",
            },
        )

    def test_a_claim_refusal_carries_the_server_sentence(self) -> None:
        self.responses.append(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [
                        {"type": "text", "text": "Work request #7 is claimed by writer"}
                    ],
                    "isError": True,
                },
            }
        )
        with self.assertRaises(LEDGER.ContextLedgerError) as caught:
            self.client.work_claim(7)
        self.assertIn("claimed by writer", str(caught.exception))


class V111WireShapeTests(FakeTransport, unittest.TestCase):
    """Minor 1.11: the founding protocol, from playbook to permission."""

    def test_playbook_get_lists_and_fetches(self) -> None:
        self.responses.append(self._ok({"playbooks": [{"slug": "founding-interview"}]}))
        self.client.playbook_get()
        self.assertEqual(self.requests[0]["params"]["name"], "playbook_get")
        self.assertEqual(self.requests[0]["params"]["arguments"], {})

        self.responses.append(self._ok({"slug": "founding-interview", "body": "# The founding interview"}))
        book = self.client.playbook_get("founding-interview")
        self.assertEqual(self.requests[1]["params"]["arguments"], {"slug": "founding-interview"})
        self.assertTrue(book["body"].startswith("# "))

    def test_research_verbs_shape_their_arguments(self) -> None:
        self.responses.append(self._ok({"provider": "firecrawl", "query": "q", "results": []}))
        self.client.research_search("dental practice churn benchmarks", limit=3, scrape=True)
        self.assertEqual(self.requests[0]["params"]["name"], "research_search")
        self.assertEqual(
            self.requests[0]["params"]["arguments"],
            {"query": "dental practice churn benchmarks", "limit": 3, "scrape": True},
        )

        self.responses.append(
            self._ok({"url": "https://example.com/a", "title": "A", "markdown": "# A", "truncated": False,
                      "evidence": {"slug": "evidence-example-com-20260902", "title": "A", "branch": "founding/20260902"}})
        )
        page = self.client.research_scrape("https://example.com/a", record=True, branch="founding/20260902")
        self.assertEqual(self.requests[1]["params"]["name"], "research_scrape")
        self.assertEqual(
            self.requests[1]["params"]["arguments"],
            {"url": "https://example.com/a", "record": True, "branch": "founding/20260902"},
        )
        self.assertEqual(page["evidence"]["slug"], "evidence-example-com-20260902")

    def test_proposal_review_then_commit_carry_the_yes(self) -> None:
        self.responses.append(self._ok({"branch": "founding/20260902", "ready": False, "blockers": ["Row 3 of swot-analysis cites nothing"], "brief": "..."}))
        review = self.client.proposal_review("founding/20260902")
        self.assertEqual(self.requests[0]["params"]["arguments"], {"branch": "founding/20260902"})
        self.assertFalse(review["ready"])

        self.responses.append(self._ok({"merged": 12, "merge_id": "mrg1", "approved_by": "Ana Ruiz", "review": {"ready": True, "blockers": []}}))
        done = self.client.proposal_commit("founding/20260902", "Ana Ruiz", message="Founding proposal")
        self.assertEqual(self.requests[1]["params"]["name"], "proposal_commit")
        self.assertEqual(
            self.requests[1]["params"]["arguments"],
            {"branch": "founding/20260902", "approved_by": "Ana Ruiz", "message": "Founding proposal"},
        )
        self.assertEqual(done["approved_by"], "Ana Ruiz")

    def test_a_not_ready_refusal_reaches_the_agent_verbatim(self) -> None:
        self.responses.append(
            {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "Proposal founding/20260902 is not ready: 2 uncited claim rows. Fix them or pass force with a force_reason."}], "isError": True}}
        )
        with self.assertRaises(LEDGER.ContextLedgerError) as caught:
            self.client.proposal_commit("founding/20260902", "Ana Ruiz")
        self.assertIn("not ready", str(caught.exception))


class HttpTransportFailureTests(unittest.TestCase):
    """Every wire failure has to arrive as a ContextLedgerError.

    The CLI documents "exit 2 on every failure" and the runner loop catches
    only ContextLedgerError, so an HTTPError, a URLError or a socket
    timeout escaping this module is a crash in both. Offline throughout:
    urlopen is replaced, nothing is dialed.
    """

    def setUp(self) -> None:
        self.client = LEDGER.ContextLedgerClient(
            "https://ledger.example/mcp", "cos_test"
        )
        self._real_urlopen = urllib.request.urlopen
        self.addCleanup(setattr, urllib.request, "urlopen", self._real_urlopen)

    def _urlopen_raises(self, exc: Exception) -> None:
        def fake_urlopen(request, timeout=None):
            raise exc

        urllib.request.urlopen = fake_urlopen

    def test_http_401_with_the_auth_frame_becomes_a_ledger_auth_error(self) -> None:
        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "code": LEDGER.AUTH_ERROR_CODE,
                    "message": "That agent key is unknown or has been revoked.",
                },
            }
        ).encode("utf-8")
        self._urlopen_raises(
            urllib.error.HTTPError(
                "https://ledger.example/mcp",
                401,
                "Unauthorized",
                {"Content-Type": "application/json"},
                io.BytesIO(body),
            )
        )
        with self.assertRaises(LEDGER.LedgerAuthError) as caught:
            self.client.config_pull()
        self.assertIn("revoked", str(caught.exception))

    def test_a_non_json_502_body_becomes_a_transport_error(self) -> None:
        self._urlopen_raises(
            urllib.error.HTTPError(
                "https://ledger.example/mcp",
                502,
                "Bad Gateway",
                {"Content-Type": "text/html"},
                io.BytesIO(b"<html>proxy could not reach upstream</html>"),
            )
        )
        with self.assertRaises(LEDGER.LedgerTransportError) as caught:
            self.client.config_pull()
        self.assertEqual(caught.exception.status, 502)
        self.assertIsInstance(caught.exception, LEDGER.ContextLedgerError)

    def test_an_unreachable_url_raises_a_transport_error_not_a_url_error(self) -> None:
        self._urlopen_raises(urllib.error.URLError("Name or service not known"))
        with self.assertRaises(LEDGER.LedgerTransportError) as caught:
            self.client.config_pull()
        self.assertIn("unreachable", str(caught.exception))
        self.assertIsNone(caught.exception.status)

    def test_a_dropped_connection_and_a_timeout_stay_inside_the_contract(self) -> None:
        for failure in (TimeoutError("timed out"), ConnectionResetError("reset")):
            with self.subTest(failure=type(failure).__name__):
                self._urlopen_raises(failure)
                with self.assertRaises(LEDGER.ContextLedgerError):
                    self.client.config_pull()

    def test_a_body_that_is_not_json_is_a_transport_error(self) -> None:
        class _Response:
            def read(self) -> bytes:
                return b"not json at all"

            def __enter__(self):
                return self

            def __exit__(self, *args) -> bool:
                return False

        urllib.request.urlopen = lambda request, timeout=None: _Response()
        with self.assertRaises(LEDGER.LedgerTransportError):
            self.client.config_pull()



class VerbTableTests(unittest.TestCase):
    """The verb table has to cover the whole server, not the part we wrote first.

    `_tool_failure` names the refused grant by looking the verb up in
    VERB_CAPABILITY. A verb the server serves and this table omits turns a
    refusal an agent could act on ("ask an owner for branch:merge") into
    `capability=None`, so the count is worth pinning: the ledger at minor 1.11
    serves fifty-one verbs.
    """

    def test_every_verb_the_ledger_serves_is_priced(self) -> None:
        self.assertEqual(len(LEDGER.VERB_CAPABILITY), 51)
        self.assertEqual(LEDGER.LEDGER_PROTOCOL_MINOR, "1.11")
        # Every price is drawn from the closed capability set; a typo here
        # would make capability_for() report a grant no owner can give.
        self.assertEqual(
            set(LEDGER.VERB_CAPABILITY.values()) - set(LEDGER.CAPABILITIES),
            set(),
        )

    def test_the_verbs_that_redefine_main_cost_branch_merge(self) -> None:
        spot_check = {
            "config_pull": "context:read",
            "document_put": "context:write",
            # Datasets and the fact ledger, added after v1.6 and priced the
            # same way documents are.
            "dataset_query": "context:read",
            "dataset_row_put": "context:write",
            "dataset_row_revert": "context:revert",
            "context_note": "context:write",
            "context_compose": "context:read",
            "venture_state": "context:read",
            # The work queue (1.10): reading is ordinary, taking is a write.
            "work_list": "context:read",
            "work_claim": "context:write",
            "work_complete": "context:write",
            # The founding protocol (1.11).
            "playbook_get": "context:read",
            "research_search": "context:read",
            "proposal_review": "context:read",
            "proposal_commit": "branch:merge",
            # The three that change what every other agent reads as truth.
            "branch_merge": "branch:merge",
            "merge_revert": "branch:merge",
            "venture_sync": "branch:merge",
        }
        for verb, capability in spot_check.items():
            self.assertEqual(LEDGER.VERB_CAPABILITY.get(verb), capability, verb)
            self.assertEqual(
                LEDGER.ContextLedgerClient(
                    "https://ledger.example/mcp", "cos_test", transport=lambda p: {}
                ).capability_for(verb),
                capability,
                verb,
            )


if __name__ == "__main__":
    unittest.main()
