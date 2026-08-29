#!/usr/bin/env python3
"""Client for the context-ledger.v1 protocol (see references/protocol-v1.md).

Stdlib-only. Speaks MCP Streamable HTTP in stateless JSON mode against a
hosted ledger (reference implementation: company-os-web). The ledger is
shared company context — this client carries no dispatch, lease, scheduler,
acceptance, or spend capability, matching the protocol's boundary.

The evidence bridge: ``materialize`` writes a revision's canonical JSON
bytes to a file whose sha256 equals the ledger's ``contentHash``, so
``record-evidence`` can ingest a ledger revision and every downstream grant
and audit cites it exactly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any, Callable


class ContextLedgerError(RuntimeError):
    """A ledger call failed; the message is the server's sentence."""


def canonical_json(value: Any) -> str:
    """The framework's frozen canonical encoding (golden-vector pinned)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


Transport = Callable[[dict[str, Any]], dict[str, Any]]


class ContextLedgerClient:
    def __init__(self, url: str, token: str, transport: Transport | None = None):
        if not token.startswith("cos_"):
            raise ContextLedgerError("agent keys start with cos_")
        self.url = url
        self.token = token
        self._transport = transport or self._http_transport
        self._next_id = 0

    def _http_transport(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self._next_id += 1
        response = self._transport(
            {
                "jsonrpc": "2.0",
                "id": self._next_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if "error" in response:
            raise ContextLedgerError(str(response["error"].get("message", "ledger error")))
        result = response.get("result", {})
        if result.get("isError"):
            content = result.get("content", [])
            text = content[0].get("text", "tool failed") if content else "tool failed"
            raise ContextLedgerError(text)
        if "structuredContent" in result:
            return result["structuredContent"]
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        raise ContextLedgerError("ledger returned no content")

    # ------------------------------- Verbs -------------------------------

    def config_pull(self) -> dict[str, Any]:
        return self._call_tool("config_pull", {})

    def document_get(self, slug: str) -> dict[str, Any]:
        return self._call_tool("document_get", {"slug": slug})

    def document_put(
        self,
        *,
        kind: str,
        message: str,
        content: dict[str, Any],
        base_revision: int,
        doc_slug: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {
            "kind": kind,
            "message": message,
            "content": content,
            "base_revision": base_revision,
        }
        if doc_slug is not None:
            arguments["doc_slug"] = doc_slug
        if title is not None:
            arguments["title"] = title
        return self._call_tool("document_put", arguments)

    def run_append(
        self,
        *,
        run_id: str,
        type: str,
        payload: Any = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        arguments: dict[str, Any] = {"run_id": run_id, "type": type}
        if payload is not None:
            arguments["payload"] = payload
        if summary is not None:
            arguments["summary"] = summary
        return self._call_tool("run_append", arguments)

    def push_brief(self, run_id: str, economics: dict[str, Any]) -> dict[str, Any]:
        """Surface the operator brief's economics block on the company overview."""
        return self.run_append(
            run_id=run_id,
            type="brief_snapshot",
            payload=economics,
            summary="Operator brief economics snapshot",
        )

    # --------------------------- Evidence bridge ---------------------------

    def verify_content_hash(self, document: dict[str, Any]) -> bool:
        """Recompute the canonical hash of a fetched document's content."""
        expected = document.get("contentHash")
        if not isinstance(expected, str):
            return False
        return content_hash(document.get("content")) == expected

    def materialize(self, slug: str, directory: Path) -> Path:
        """Write a revision's canonical bytes so file sha256 == contentHash.

        The written file is admissible framework evidence: record-evidence
        hashes the file, and that hash IS the ledger's content address.
        """
        document = self.document_get(slug)
        if document.get("contentHash") is None:
            raise ContextLedgerError(f'"{slug}" has no committed revision to materialize')
        if not self.verify_content_hash(document):
            raise ContextLedgerError(
                f'"{slug}" content does not match its contentHash — refusing to materialize'
            )
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{document['slug']}@r{document['revision']}.canonical.json"
        path.write_bytes(canonical_json(document["content"]).encode("ascii"))
        return path

    def context_bundle(self, slugs: list[str]) -> dict[str, Any]:
        """A compact, hash-pinned context block for goal contracts."""
        documents = []
        for slug in slugs:
            document = self.document_get(slug)
            if not self.verify_content_hash(document) and document.get("contentHash"):
                raise ContextLedgerError(f'"{slug}" failed hash verification')
            documents.append(
                {
                    "slug": document["slug"],
                    "kind": document["kind"],
                    "title": document["title"],
                    "revision": document["revision"],
                    "content_hash": document["contentHash"],
                    "content": document["content"],
                }
            )
        bundle = {"protocol": "context-ledger.v1", "documents": documents}
        return {**bundle, "bundle_sha256": content_hash(bundle)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="ledger MCP endpoint (…/mcp)")
    parser.add_argument("--token", required=True, help="cos_ agent key")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("pull", help="config_pull")
    get_parser = commands.add_parser("get", help="document_get")
    get_parser.add_argument("--slug", required=True)
    put_parser = commands.add_parser("put", help="document_put")
    put_parser.add_argument("--kind", required=True)
    put_parser.add_argument("--message", required=True)
    put_parser.add_argument("--content", required=True, help="JSON object, or @file")
    put_parser.add_argument("--base-revision", type=int, required=True)
    put_parser.add_argument("--doc-slug")
    put_parser.add_argument("--title")
    append_parser = commands.add_parser("append", help="run_append")
    append_parser.add_argument("--run-id", required=True)
    append_parser.add_argument("--type", required=True)
    append_parser.add_argument("--payload", help="JSON, or @file")
    append_parser.add_argument("--summary")
    materialize_parser = commands.add_parser(
        "materialize", help="write canonical bytes for record-evidence"
    )
    materialize_parser.add_argument("--slug", required=True)
    materialize_parser.add_argument("--dir", required=True)
    args = parser.parse_args()

    def load_json(raw: str) -> Any:
        text = Path(raw[1:]).read_text(encoding="utf-8") if raw.startswith("@") else raw
        return json.loads(text)

    client = ContextLedgerClient(args.url, args.token)
    try:
        if args.command == "pull":
            result: Any = client.config_pull()
        elif args.command == "get":
            result = client.document_get(args.slug)
        elif args.command == "put":
            result = client.document_put(
                kind=args.kind,
                message=args.message,
                content=load_json(args.content),
                base_revision=args.base_revision,
                doc_slug=args.doc_slug,
                title=args.title,
            )
        elif args.command == "append":
            result = client.run_append(
                run_id=args.run_id,
                type=args.type,
                payload=load_json(args.payload) if args.payload else None,
                summary=args.summary,
            )
        else:
            result = {"materialized": str(client.materialize(args.slug, Path(args.dir)))}
    except ContextLedgerError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2
    print(json.dumps({"ok": True, "result": result}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
