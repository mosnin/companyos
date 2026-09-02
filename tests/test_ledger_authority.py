"""Authority, revert semantics, and typed refusals for the context ledger.

The ledger's promise is not "you can write to it" — it is that the history
is trustworthy and that changing what the company says on main takes an
authority someone granted on purpose. Two invariants carry that promise, and
both are tested here against an in-memory ledger that enforces the same
rules the server does:

1. **Writing is ordinary; merging to main is not.** Any writer may open a
   branch and commit into it. Landing it on main needs `branch:merge`, which
   no legacy key and no ordinary member holds.
2. **History is never rewritten.** A revert is `git revert`, never
   `git reset`: the old content is committed FORWARD as a new revision. No
   revision is ever mutated or removed, by anyone, for any reason.

No live server: the transport is a fake, exactly as the rest of the ledger
suite does it.
"""
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLIENT_SOURCE = ROOT / "skills/company-os/company-context-ledger/scripts/context_ledger.py"


def _load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LEDGER = _load(
    "skills/company-os/company-context-ledger/scripts/context_ledger.py",
    "context_ledger_for_authority",
)

# A write-scope key as v1.5 issued them. The point of the constant is what is
# NOT in it: no `branch:merge`, no `context:revert`. An existing credential
# must not silently acquire the power to redefine main or to move a document
# backwards, so both are new grants that must be asked for.
LEGACY_WRITE_KEY = (
    "context:read",
    "context:write",
    "branch:create",
    "feedback:write",
    "run:append",
)
MERGE_KEY = LEGACY_WRITE_KEY + ("branch:merge", "context:revert")
READ_KEY = ("context:read",)


class Refused(Exception):
    """A refusal the fake ledger raises as a tool error, like the server."""


class FakeLedger:
    """An in-memory ledger that enforces the real authority rule.

    Faithful where it matters: capabilities gate the verbs, revisions are
    append-only, and a merge writes a receipt recording each document's
    before/after so the merge can be walked backwards later.
    """

    def __init__(
        self,
        *,
        capabilities: tuple[str, ...] = MERGE_KEY,
        key_name: str = "planner",
        report_capabilities: bool = True,
        company: str = "acme",
    ) -> None:
        self.capabilities = tuple(capabilities)
        self.key_name = key_name
        self.report_capabilities = report_capabilities
        self.company = company
        self.revisions: dict[str, list[dict[str, Any]]] = {}
        self.archived: set[str] = set()
        self.branches: dict[str, dict[str, Any]] = {}
        self.branch_docs: dict[str, dict[str, dict[str, Any]]] = {}
        self.merges: list[dict[str, Any]] = []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    # ----------------------------- ledger state -----------------------------

    def commit(
        self,
        slug: str,
        content: dict[str, Any],
        message: str,
        *,
        reverted_from: int | None = None,
    ) -> dict[str, Any]:
        """Append one revision. Nothing in this class ever edits an existing one."""
        log = self.revisions.setdefault(slug, [])
        entry: dict[str, Any] = {
            "seq": len(log) + 1,
            "content": content,
            "message": message,
            "content_hash": LEDGER.content_hash(content),
        }
        if reverted_from is not None:
            entry["reverted_from"] = reverted_from
        log.append(entry)
        return entry

    def head(self, slug: str) -> dict[str, Any] | None:
        log = self.revisions.get(slug)
        return log[-1] if log else None

    # ------------------------------- transport ------------------------------

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        method = payload.get("method")
        request_id = payload.get("id")
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": request_id, "result": self._handshake()}
        if method == "resources/read":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "contents": [
                        {"uri": payload["params"]["uri"], "mimeType": "application/json"}
                    ]
                },
            }
        if method != "tools/call":
            return self._rpc_error(request_id, -32601, f"Unknown method: {method}")
        name = payload["params"]["name"]
        arguments = payload["params"].get("arguments", {})
        self.calls.append((name, arguments))
        needed = LEDGER.VERB_CAPABILITY[name]
        if needed not in self.capabilities:
            return self._tool_error(request_id, self._refusal(needed))
        try:
            result = self._dispatch(name, arguments)
        except Refused as refused:
            return self._tool_error(request_id, str(refused))
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result)}],
                "structuredContent": result,
            },
        }

    def _handshake(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "protocolVersion": "2025-06-18",
            # The SERVER's capabilities: an object, and never to be mistaken
            # for the key's granted set.
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "company-os-ledger", "version": "1.6.0"},
        }
        if self.report_capabilities:
            result["agent"] = {
                "key_name": self.key_name,
                "capabilities": list(self.capabilities),
                "rate_limit": {"limit": 120, "remaining": 119, "reset_at": 1767225600000},
            }
        return result

    def _refusal(self, capability: str) -> str:
        """The server's own sentence: names the grant, and who holds it."""
        return (
            f'Refused: this needs the "{capability}" capability. '
            f'The key "{self.key_name}" does not hold it. '
            "Merging to main changes what every other agent reads as the "
            "company's truth, so an owner or admin grants it deliberately."
        )

    @staticmethod
    def _rpc_error(request_id: Any, code: int, message: str, data: Any = None) -> dict:
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}

    @staticmethod
    def _tool_error(request_id: Any, text: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": text}], "isError": True},
        }

    # ------------------------------- the verbs ------------------------------

    def _dispatch(self, name: str, args: dict[str, Any]) -> Any:
        handler = getattr(self, f"_verb_{name}", None)
        if handler is None:
            raise Refused(f"Unknown tool: {name}")
        return handler(args)

    def _verb_config_pull(self, args: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "protocol": "context-ledger.v1",
            "documents": [
                {"slug": slug, "revision": log[-1]["seq"], "contentHash": log[-1]["content_hash"]}
                for slug, log in sorted(self.revisions.items())
            ],
        }
        if self.report_capabilities:
            payload["agent"] = {
                "key_name": self.key_name,
                "capabilities": list(self.capabilities),
            }
        return payload

    def _verb_document_list(self, args: dict[str, Any]) -> dict[str, Any]:
        slugs = sorted(self.revisions)
        cursor = args.get("cursor")
        if cursor:
            slugs = [slug for slug in slugs if slug > cursor]
        limit = args.get("limit") or len(slugs)
        page = slugs[:limit]
        return {
            "documents": [
                {"slug": slug, "revision": self.revisions[slug][-1]["seq"]} for slug in page
            ],
            "has_more": len(page) < len(slugs),
            "cursor": page[-1] if page else None,
            "document_count": len(self.revisions),
        }

    def _verb_document_put(self, args: dict[str, Any]) -> dict[str, Any]:
        slug = args.get("doc_slug") or args["kind"]
        branch = args.get("branch")
        if branch:
            self.branch_docs.setdefault(branch, {})[slug] = {
                "content": args["content"],
                "message": args["message"],
            }
            return {"doc_slug": slug, "branch": branch, "revision": 1}
        entry = self.commit(slug, args["content"], args["message"])
        return {"doc_slug": slug, "revision": entry["seq"], "contentHash": entry["content_hash"]}

    def _verb_document_history(self, args: dict[str, Any]) -> dict[str, Any]:
        log = self.revisions.get(args["slug"], [])
        return {
            "revisions": [
                {
                    key: value
                    for key, value in entry.items()
                    if key != "content"
                }
                for entry in log
            ],
            "has_more": False,
        }

    def _verb_document_revert(self, args: dict[str, Any]) -> dict[str, Any]:
        slug, to_seq = args["slug"], args["to_seq"]
        log = self.revisions.get(slug, [])
        source = next((entry for entry in log if entry["seq"] == to_seq), None)
        if source is None:
            raise Refused(f'"{slug}" has no revision {to_seq}')
        entry = self.commit(
            slug,
            source["content"],
            args.get("message") or f"Revert to revision {to_seq}",
            reverted_from=to_seq,
        )
        return {
            "seq": entry["seq"],
            "content_hash": entry["content_hash"],
            "reverted_from": to_seq,
        }

    def _verb_branch_create(self, args: dict[str, Any]) -> dict[str, Any]:
        slug = args["name"].lower().replace(" ", "-")
        self.branches[slug] = {"slug": slug, "name": args["name"], "status": "open"}
        self.branch_docs.setdefault(slug, {})
        return {"slug": slug, "name": args["name"], "status": "open"}

    def _verb_branch_list(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        status = args.get("status")
        rows = []
        for slug, branch in self.branches.items():
            if status and branch["status"] != status:
                continue
            documents = self.branch_docs.get(slug, {})
            ahead = sum(
                1
                for doc_slug, draft in documents.items()
                if (self.head(doc_slug) or {}).get("content") != draft["content"]
            )
            rows.append({**branch, "document_count": len(documents), "ahead": ahead})
        return rows

    def _verb_branch_diff(self, args: dict[str, Any]) -> dict[str, Any]:
        branch = args["branch"]
        entries = []
        for slug, draft in sorted(self.branch_docs.get(branch, {}).items()):
            head = self.head(slug)
            entries.append(
                {
                    "slug": slug,
                    "change": "modified" if head else "added",
                    "base_revision": head["seq"] if head else 0,
                    "content_hash": LEDGER.content_hash(draft["content"]),
                }
            )
        return {"branch": branch, "entries": entries}

    def _verb_branch_merge(self, args: dict[str, Any]) -> dict[str, Any]:
        branch = args["branch"]
        if branch not in self.branches:
            raise Refused(f'Unknown branch "{branch}"')
        if self.branches[branch]["status"] != "open":
            raise Refused(f'Branch "{branch}" is {self.branches[branch]["status"]}')
        entries = []
        for slug, draft in sorted(self.branch_docs.get(branch, {}).items()):
            before = self.head(slug)
            after = self.commit(
                slug, draft["content"], args.get("message") or f"Merge {branch}"
            )
            entries.append(
                {
                    "slug": slug,
                    # Absent when the merge CREATED the document on main —
                    # that is what makes the revert archive instead of restore.
                    "before_seq": before["seq"] if before else None,
                    "after_seq": after["seq"],
                }
            )
        self.branches[branch]["status"] = "merged"
        merge_id = f"mrg{len(self.merges) + 1}"
        self.merges.append(
            {
                "merge_id": merge_id,
                "branch": branch,
                "actor": self.key_name,
                "entries": entries,
                "reverted_at": None,
            }
        )
        return {"merged": len(entries), "merge_id": merge_id, "branch": branch}

    def _verb_merge_revert(self, args: dict[str, Any]) -> dict[str, Any]:
        receipt = next(
            (row for row in self.merges if row["merge_id"] == args["merge_id"]), None
        )
        if receipt is None:
            raise Refused("Merge not found")
        if receipt["reverted_at"]:
            # State, not authority: the caller holds branch:merge and still
            # cannot do this. The client must not read it as a refusal to
            # take to a human.
            raise Refused(
                f'That merge was already reverted at {receipt["reverted_at"]}.'
            )
        reverted = archived = 0
        for entry in receipt["entries"]:
            slug = entry["slug"]
            if entry["before_seq"] is None:
                self.archived.add(slug)
                archived += 1
                continue
            log = self.revisions[slug]
            source = next(item for item in log if item["seq"] == entry["before_seq"])
            self.commit(
                slug,
                source["content"],
                args.get("message") or f'Revert merge {args["merge_id"]}',
                reverted_from=entry["before_seq"],
            )
            reverted += 1
        receipt["reverted_at"] = 1767225600000
        receipt["reverted_by"] = self.key_name
        return {"reverted": reverted, "archived": archived}

    def _verb_merge_list(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        rows = [
            {
                "merge_id": row["merge_id"],
                "branch": row["branch"],
                "actor": row["actor"],
                "entry_count": len(row["entries"]),
                "reverted_at": row["reverted_at"],
            }
            for row in reversed(self.merges)
        ]
        return rows[: args["limit"]] if args.get("limit") else rows

    def _verb_schema_describe(self, args: dict[str, Any]) -> dict[str, Any]:
        kinds = [
            {
                "kind": "okrs",
                "view": "strategy",
                "title": "OKRs",
                "multiple": False,
                "version": 2,
                "fields": [{"id": "period", "label": "Period", "type": "text"}],
            }
        ]
        if args.get("kind"):
            kinds = [row for row in kinds if row["kind"] == args["kind"]]
        return {
            "views": [{"id": "strategy", "label": "Strategy", "groups": ["direction"]}],
            "kinds": kinds,
        }

    def _verb_feedback_list(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def _verb_feedback_add(self, args: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    def _verb_run_append(self, args: dict[str, Any]) -> dict[str, Any]:
        return {"run_id": args["run_id"]}

    def _verb_context_search(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def _verb_context_changes(self, args: dict[str, Any]) -> dict[str, Any]:
        return {"cursor": "0:0", "has_more": False, "events": []}

    def _verb_document_get(self, args: dict[str, Any]) -> dict[str, Any]:
        head = self.head(args["slug"])
        return {
            "slug": args["slug"],
            "revision": head["seq"] if head else 0,
            "content": head["content"] if head else {},
            "contentHash": head["content_hash"] if head else None,
        }


def client_for(ledger: FakeLedger) -> Any:
    return LEDGER.ContextLedgerClient(
        "https://ledger.example/mcp", "cos_test", transport=ledger
    )


def seeded(**kwargs: Any) -> tuple[FakeLedger, Any]:
    """A ledger with a two-revision okrs document and an open branch."""
    ledger = FakeLedger(**kwargs)
    ledger.commit("okrs", {"period": "2026 Q1"}, "Set Q1 OKRs")
    ledger.commit("okrs", {"period": "2026 Q2"}, "Set Q2 OKRs")
    ledger.branches["plg-pivot"] = {
        "slug": "plg-pivot",
        "name": "PLG pivot",
        "status": "open",
    }
    ledger.branch_docs["plg-pivot"] = {
        "okrs": {"content": {"period": "2026 Q3 self-serve"}, "message": "Draft"},
        "pricing-packaging": {"content": {"tiers": ["free", "team"]}, "message": "Draft"},
    }
    return ledger, client_for(ledger)


class MergeAuthorityTests(unittest.TestCase):
    """Writing is ordinary; merging to main is not."""

    def test_a_key_without_branch_merge_is_refused_and_told_why(self) -> None:
        ledger, client = seeded(capabilities=LEGACY_WRITE_KEY)
        with self.assertRaises(LEDGER.LedgerCapabilityError) as caught:
            client.branch_merge("plg-pivot")
        refusal = caught.exception
        # The refusal is typed, names the missing grant, and says what the
        # key does hold — an agent can act on it without parsing prose.
        self.assertEqual(refusal.capability, "branch:merge")
        self.assertIn("branch:merge", str(refusal))
        # And nothing landed. A refused merge must not half-apply.
        self.assertEqual(ledger.merges, [])
        self.assertEqual(ledger.head("okrs")["content"], {"period": "2026 Q2"})
        self.assertNotIn("pricing-packaging", ledger.revisions)

    def test_a_capability_refusal_is_not_an_ordinary_failure(self) -> None:
        _, client = seeded(capabilities=LEGACY_WRITE_KEY)
        # Catching the base class still works (nothing existing breaks), but
        # the subclass is what lets an agent tell "ask a human" from "retry".
        with self.assertRaises(LEDGER.ContextLedgerError):
            client.branch_merge("plg-pivot")
        with self.assertRaises(LEDGER.LedgerCapabilityError):
            client.branch_merge("plg-pivot")

    def test_a_key_with_branch_merge_lands_the_branch(self) -> None:
        ledger, client = seeded(capabilities=MERGE_KEY)
        result = client.branch_merge("plg-pivot", message="Land the PLG pivot")
        self.assertEqual(result["merged"], 2)
        self.assertEqual(len(ledger.merges), 1)
        self.assertEqual(ledger.head("okrs")["content"], {"period": "2026 Q3 self-serve"})
        # The merge is a receipt, not just an effect: it is what a revert walks.
        receipt = ledger.merges[0]
        self.assertEqual(receipt["merge_id"], result["merge_id"])
        self.assertEqual(
            {entry["slug"] for entry in receipt["entries"]},
            {"okrs", "pricing-packaging"},
        )

    def test_branching_and_committing_never_need_merge_authority(self) -> None:
        """The other half of the rule, and the half agents live in."""
        ledger, client = seeded(capabilities=LEGACY_WRITE_KEY)
        client.branch_create("Q4 rethink")
        client.document_put(
            kind="okrs",
            message="Draft Q4 OKRs",
            content={"period": "2026 Q4"},
            base_revision=2,
            branch="q4-rethink",
        )
        diff = client.branch_diff("q4-rethink")
        self.assertEqual(diff["entries"][0]["slug"], "okrs")
        self.assertEqual(diff["entries"][0]["change"], "modified")
        # Reads and branch work all succeeded on a key that cannot merge.
        self.assertEqual(client.branch_list(status="open")[0]["status"], "open")

    def test_a_read_only_key_is_refused_every_write(self) -> None:
        ledger, client = seeded(capabilities=READ_KEY)
        for call in (
            lambda: client.document_put(
                kind="okrs", message="x", content={"period": "z"}, base_revision=2
            ),
            lambda: client.branch_create("nope"),
            lambda: client.branch_merge("plg-pivot"),
            lambda: client.document_revert("okrs", to_seq=1),
        ):
            with self.assertRaises(LEDGER.LedgerCapabilityError):
                call()
        self.assertEqual(len(ledger.revisions["okrs"]), 2)


class RevertSemanticsTests(unittest.TestCase):
    """Revert is `git revert`. History is never rewritten."""

    def test_revert_commits_forward_and_leaves_every_revision_alone(self) -> None:
        ledger, client = seeded(capabilities=MERGE_KEY)
        ledger.commit("okrs", {"period": "2026 Q3"}, "Set Q3 OKRs")
        before = json.dumps(ledger.revisions["okrs"], sort_keys=True)

        result = client.document_revert(
            "okrs", to_seq=1, message="Q3 plan was premature"
        )

        # A NEW revision, with a NEW seq strictly beyond the head.
        self.assertEqual(result["seq"], 4)
        self.assertEqual(result["reverted_from"], 1)
        self.assertEqual(len(ledger.revisions["okrs"]), 4)
        # Nothing before it moved: the first three revisions are byte-identical.
        self.assertEqual(
            json.dumps(ledger.revisions["okrs"][:3], sort_keys=True), before
        )
        # And the content came back, addressed by the same hash as revision 1.
        self.assertEqual(ledger.head("okrs")["content"], {"period": "2026 Q1"})
        self.assertEqual(result["content_hash"], ledger.revisions["okrs"][0]["content_hash"])

    def test_history_only_ever_grows_across_a_revert_of_a_revert(self) -> None:
        ledger, client = seeded(capabilities=MERGE_KEY)
        client.document_revert("okrs", to_seq=1)
        client.document_revert("okrs", to_seq=2)
        seqs = [entry["seq"] for entry in ledger.revisions["okrs"]]
        self.assertEqual(seqs, [1, 2, 3, 4])
        self.assertEqual(ledger.head("okrs")["content"], {"period": "2026 Q2"})

    def test_document_revert_needs_context_revert(self) -> None:
        ledger, client = seeded(capabilities=LEGACY_WRITE_KEY)
        with self.assertRaises(LEDGER.LedgerCapabilityError) as caught:
            client.document_revert("okrs", to_seq=1)
        self.assertEqual(caught.exception.capability, "context:revert")
        self.assertEqual(len(ledger.revisions["okrs"]), 2)

    def test_merge_revert_restores_content_and_archives_what_the_merge_created(self) -> None:
        ledger, client = seeded(capabilities=MERGE_KEY)
        merge = client.branch_merge("plg-pivot")

        result = client.merge_revert(merge["merge_id"], message="Pivot was wrong")

        # okrs existed before the merge, so it is restored forward; the
        # pricing document the merge CREATED is archived, never deleted.
        self.assertEqual(result, {"reverted": 1, "archived": 1})
        self.assertEqual(ledger.head("okrs")["content"], {"period": "2026 Q2"})
        self.assertEqual([e["seq"] for e in ledger.revisions["okrs"]], [1, 2, 3, 4])
        self.assertIn("pricing-packaging", ledger.archived)
        self.assertIn("pricing-packaging", ledger.revisions)

    def test_reverting_an_already_reverted_merge_is_refused(self) -> None:
        ledger, client = seeded(capabilities=MERGE_KEY)
        merge = client.branch_merge("plg-pivot")
        client.merge_revert(merge["merge_id"])
        history_after_first = json.dumps(ledger.revisions, sort_keys=True)

        with self.assertRaises(LEDGER.ContextLedgerError) as caught:
            client.merge_revert(merge["merge_id"])

        self.assertIn("already reverted", str(caught.exception))
        # It is a state refusal, NOT an authority one: this key holds
        # branch:merge. Typing it as a capability error would send an agent
        # to ask a human for a grant it already has.
        self.assertNotIsInstance(caught.exception, LEDGER.LedgerCapabilityError)
        self.assertEqual(json.dumps(ledger.revisions, sort_keys=True), history_after_first)

    def test_merge_list_shows_the_landing_and_the_taking_back(self) -> None:
        ledger, client = seeded(capabilities=MERGE_KEY)
        merge = client.branch_merge("plg-pivot")
        self.assertIsNone(client.merge_list()[0]["reverted_at"])
        client.merge_revert(merge["merge_id"])
        row = client.merge_list(limit=1)[0]
        self.assertEqual(row["merge_id"], merge["merge_id"])
        self.assertIsNotNone(row["reverted_at"])


class CapabilityReportingTests(unittest.TestCase):
    def test_the_client_surfaces_the_keys_granted_capabilities(self) -> None:
        _, client = seeded(capabilities=LEGACY_WRITE_KEY)
        self.assertEqual(client.granted_capabilities(), LEGACY_WRITE_KEY)
        self.assertTrue(client.can("context:write"))
        self.assertFalse(client.can("branch:merge"))
        self.assertEqual(client.rate_limit()["limit"], 120)

    def test_assert_can_refuses_locally_only_when_the_ledger_reported(self) -> None:
        _, client = seeded(capabilities=LEGACY_WRITE_KEY)
        with self.assertRaises(LEDGER.LedgerCapabilityError) as caught:
            client.assert_can("branch:merge")
        self.assertEqual(caught.exception.capability, "branch:merge")
        client.assert_can("context:write")

    def test_an_unreporting_ledger_leaves_the_set_unknown_and_fails_open(self) -> None:
        ledger, client = seeded(capabilities=MERGE_KEY, report_capabilities=False)
        # None means "the ledger did not say", which is not the same claim as
        # "() — it holds nothing".
        self.assertIsNone(client.granted_capabilities())
        # The server is the only gate, so an unknown set must never make the
        # client refuse work a perfectly authorized key can do.
        self.assertTrue(client.can("branch:merge"))
        client.assert_can("branch:merge")
        self.assertEqual(client.branch_merge("plg-pivot")["merged"], 2)

    def test_config_pull_harvests_the_agent_block_without_an_extra_call(self) -> None:
        ledger, client = seeded(capabilities=LEGACY_WRITE_KEY)
        client.config_pull()
        self.assertEqual(client.granted_capabilities(), LEGACY_WRITE_KEY)
        # Only the one call: the handshake was never needed.
        self.assertEqual([name for name, _ in ledger.calls], ["config_pull"])

    def test_the_server_capabilities_object_is_never_read_as_a_grant(self) -> None:
        """`initialize` also carries the SERVER's capabilities, an object."""
        ledger, client = seeded(capabilities=MERGE_KEY, report_capabilities=False)
        client.initialize()
        self.assertIsNone(client.granted_capabilities())


class TypedRefusalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.responses: list[dict] = []
        self.client = LEDGER.ContextLedgerClient(
            "https://ledger.example/mcp",
            "cos_test",
            transport=lambda payload: self.responses.pop(0),
        )

    def test_an_unknown_key_raises_an_auth_error(self) -> None:
        self.responses.append(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32001, "message": "That key is unknown or revoked."},
            }
        )
        with self.assertRaises(LEDGER.LedgerAuthError):
            self.client.config_pull()

    def test_a_rate_limited_call_carries_the_budget(self) -> None:
        self.responses.append(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "code": -32029,
                    "message": 'Rate limit exceeded for key "planner": 120 calls per minute.',
                    "data": {
                        "limit": 120,
                        "remaining": 0,
                        "reset_at": 1767225600000,
                        "retry_after_ms": 17000,
                    },
                },
            }
        )
        with self.assertRaises(LEDGER.LedgerRateLimitError) as caught:
            self.client.config_pull()
        self.assertEqual(caught.exception.retry_after_ms, 17000)
        self.assertEqual(caught.exception.reset_at, 1767225600000)
        self.assertEqual(self.client.rate_limit()["limit"], 120)

    def test_a_legacy_read_scope_refusal_is_still_a_capability_error(self) -> None:
        """The pre-capability wording the MCP server already ships."""
        self.responses.append(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": 'The key "reader" is read-only; document_put needs a write-scope key.',
                        }
                    ],
                    "isError": True,
                },
            }
        )
        with self.assertRaises(LEDGER.LedgerCapabilityError) as caught:
            self.client.document_put(
                kind="okrs", message="x", content={"period": "z"}, base_revision=1
            )
        # No capability was quoted, so it is inferred from the verb.
        self.assertEqual(caught.exception.capability, "context:write")

    def test_a_stale_write_stays_an_ordinary_error(self) -> None:
        self.responses.append(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [
                        {"type": "text", "text": 'Stale write: "okrs" is at revision 4'}
                    ],
                    "isError": True,
                },
            }
        )
        with self.assertRaises(LEDGER.ContextLedgerError) as caught:
            self.client.document_put(
                kind="okrs", message="x", content={"period": "z"}, base_revision=1
            )
        self.assertNotIsInstance(caught.exception, LEDGER.LedgerCapabilityError)


class VerbAuthorityTableTests(unittest.TestCase):
    """The map from verb to capability is the rule a reviewer reads."""

    def test_every_verb_the_client_calls_declares_its_capability(self) -> None:
        called = set(re.findall(r'_call_tool\(\s*"([a-z_]+)"', CLIENT_SOURCE.read_text("utf-8")))
        self.assertTrue(called)
        self.assertEqual(called - set(LEDGER.VERB_CAPABILITY), set())

    def test_the_table_only_names_real_capabilities(self) -> None:
        for verb, capability in LEDGER.VERB_CAPABILITY.items():
            self.assertIn(capability, LEDGER.CAPABILITIES, verb)
            self.assertIn(capability, LEDGER.CAPABILITY_MEANING, capability)

    def test_only_the_main_changing_verbs_require_branch_merge(self) -> None:
        """Three verbs, and each one redefines what main says.

        `venture_sync` joined at minor 1.9: handing a venture over flips the
        company from building to operating and publishes every department's
        documents as operating truth at once. That is the same act
        `branch:merge` was named for, so it is priced the same, and a default
        Builder key deliberately cannot do it.
        """
        gated = {
            verb
            for verb, capability in LEDGER.VERB_CAPABILITY.items()
            if capability == "branch:merge"
        }
        self.assertEqual(gated, {"branch_merge", "merge_revert", "venture_sync"})

    def test_writing_and_branching_are_never_gated_on_merge(self) -> None:
        for verb in ("document_put", "branch_create", "run_append", "feedback_add"):
            self.assertNotEqual(LEDGER.VERB_CAPABILITY[verb], "branch:merge")


if __name__ == "__main__":
    unittest.main()
