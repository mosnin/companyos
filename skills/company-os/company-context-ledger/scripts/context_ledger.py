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

v1.6 adds version control with enforced authority. The rule an agent must
internalise: BRANCHING AND COMMITTING ARE ORDINARY; MERGING TO MAIN IS NOT.
Open a branch, commit into it, diff it — then ask an owner or admin to land
it, because `branch_merge` needs the `branch:merge` capability that no
legacy key and no ordinary member holds. Reverting is `git revert`, never
`git reset`: the old content is committed forward as a new revision, so the
history stays readable and nothing is ever rewritten.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


class ContextLedgerError(RuntimeError):
    """A ledger call failed; the message is the server's sentence."""


class LedgerAuthError(ContextLedgerError):
    """The key itself was refused: missing, unknown, revoked, or expired.

    Distinct from a capability refusal — nothing this key can be granted
    fixes it, because the credential is not accepted at all.
    """


class LedgerCapabilityError(ContextLedgerError):
    """The key authenticated, but does not hold the capability the verb needs.

    Catch this instead of the bare ``ContextLedgerError`` when the
    difference matters, because it is not a fault to retry: a missing
    capability is a decision a person has to make. The one that will be hit
    most is ``branch:merge`` — an agent may branch and commit all day, but
    landing a branch on main is granted deliberately by an owner or admin.

    ``capability`` names the grant the server wanted (parsed from the
    server's own sentence, or inferred from the verb); ``granted`` is the
    set this key does hold, when the ledger reports one.
    """

    def __init__(
        self,
        message: str,
        *,
        capability: str | None = None,
        granted: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.capability = capability
        self.granted = tuple(granted)


class LedgerRateLimitError(ContextLedgerError):
    """The key exhausted its fixed-window call budget.

    The only retryable refusal in the protocol: wait for ``reset_at`` (epoch
    milliseconds) or ``retry_after_ms`` and the same call succeeds. Fields
    are ``None`` when the ledger reported no structured budget.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after_ms: int | None = None,
        reset_at: int | None = None,
        limit: int | None = None,
        remaining: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_ms = retry_after_ms
        self.reset_at = reset_at
        self.limit = limit
        self.remaining = remaining


class LedgerTransportError(ContextLedgerError):
    """The call never produced a ledger answer: the wire failed.

    A DNS failure, a refused or reset connection, a timeout, or an HTTP
    status whose body is not a JSON-RPC frame at all (a proxy's 502 page,
    say). It is a ContextLedgerError like every other failure in this
    module, so a caller that catches the base type keeps working and a
    polling loop logs it and tries again on the next interval instead of
    dying on one unreachable poll.

    ``status`` is the HTTP status when there was one, otherwise ``None``.
    Note what is NOT here: a 401 carrying the ledger's own ``-32001`` frame
    is an auth refusal, so it stays a LedgerAuthError.
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


#: MCP protocol revision this client speaks in `initialize`.
MCP_PROTOCOL_VERSION = "2025-06-18"
#: The context-ledger contract revision this client implements.
LEDGER_PROTOCOL = "context-ledger.v1"
LEDGER_PROTOCOL_MINOR = "1.10"

# JSON-RPC error codes the ledger uses outside a tool result. Auth failures
# cannot be tool errors — they happen before a tool is chosen.
AUTH_ERROR_CODE = -32001
RATE_LIMIT_ERROR_CODE = -32029

# The ledger's closed capability set, mirrored from the server's authority
# model. It is here for two jobs only: recognising a refusal so it can be
# raised as LedgerCapabilityError, and letting an agent ask what its key
# holds BEFORE it plans work it will not be allowed to land. It is never
# enforcement — the server is the only gate, and this client deliberately
# fails OPEN when a ledger reports no set, so a pre-v1.6 ledger still works.
CAPABILITIES: tuple[str, ...] = (
    "context:read",
    "context:write",
    "context:revert",
    "branch:create",
    "branch:merge",
    "feedback:write",
    "run:append",
)

CAPABILITY_MEANING: dict[str, str] = {
    "context:read": "Read documents, history, search and the branch list.",
    "context:write": "Commit revisions to documents, on main or on a branch.",
    "context:revert": (
        "Revert a document to an earlier revision. History is never rewritten: "
        "the old content is committed forward as a new revision."
    ),
    "branch:create": "Open a branch to draft an alternate version of the company.",
    "branch:merge": (
        "Land a branch on main, and revert a merge. This changes what every "
        "other agent reads as the company's truth, so it is never granted by "
        "default — an owner or admin grants it deliberately."
    ),
    "feedback:write": "Append raw customer feedback to a product document.",
    "run:append": "Append execution telemetry from a mission.",
}

# Which capability each verb needs, for every verb the ledger serves at
# minor 1.10, all forty-six of them, mirrored from the server's own
# TOOL_CAPABILITY table.
#
# THE AUTHORITY RULE IS VISIBLE HERE: reading is ordinary and writing is
# ordinary: nearly every verb below wants a capability a working agent
# normally has, except the three verbs that redefine main for everyone
# (`branch_merge`, `merge_revert` and `venture_sync`, which promotes a whole
# venture to an operating company), which want `branch:merge`, and the two
# that move something backwards (`document_revert`, `dataset_row_revert`),
# which want `context:revert`.
#
# Completeness matters more than it looks: `_tool_failure` reports the
# refused grant by looking a verb up here, so a verb missing from this table
# turns a nameable refusal into `capability=None` and an agent that cannot
# tell a person which grant to ask for.
VERB_CAPABILITY: dict[str, str] = {
    # Reading the store.
    "config_pull": "context:read",
    "document_get": "context:read",
    "document_list": "context:read",
    "document_history": "context:read",
    "context_search": "context:read",
    "context_changes": "context:read",
    "branch_list": "context:read",
    "branch_diff": "context:read",
    "merge_list": "context:read",
    "schema_describe": "context:read",
    "feedback_list": "context:read",
    # Reading the connected canvases and the portfolio.
    "canvas_graph": "context:read",
    "canvas_validate": "context:read",
    "portfolio_snapshot": "context:read",
    # Reading typed datasets.
    "dataset_list": "context:read",
    "dataset_describe": "context:read",
    "dataset_query": "context:read",
    "dataset_row_history": "context:read",
    # Reading the venture build state and its optional method Library.
    "venture_state": "context:read",
    "venture_handover_preview": "context:read",
    "venture_method": "context:read",
    "venture_brief": "context:read",
    "venture_publish_check": "context:read",
    # Reading the fact ledger.
    "context_known": "context:read",
    "context_gaps": "context:read",
    "context_compose": "context:read",
    # Reading the work queue (1.10).
    "work_list": "context:read",
    # Committing.
    "document_put": "context:write",
    "dataset_create": "context:write",
    "dataset_row_put": "context:write",
    "dataset_row_delete": "context:write",
    "venture_artifact_set": "context:write",
    "venture_artifact_accept": "context:write",
    "venture_artifact_skip": "context:write",
    "venture_define_kind": "context:write",
    "context_note": "context:write",
    # Taking and finishing a work request (1.10). Lane-checked against the
    # request's department, like every other write.
    "work_claim": "context:write",
    "work_complete": "context:write",
    # Moving something backwards.
    "document_revert": "context:revert",
    "dataset_row_revert": "context:revert",
    # Branching, and the three verbs that change what main says.
    "branch_create": "branch:create",
    "branch_merge": "branch:merge",
    "merge_revert": "branch:merge",
    "venture_sync": "branch:merge",
    # The rest.
    "feedback_add": "feedback:write",
    "run_append": "run:append",
}

# A server refusal names the capability in double quotes ("branch:merge").
# Matching against the closed set above means an ordinary quoted string in
# some other error can never be mistaken for a capability.
_QUOTED_CAPABILITY = re.compile(
    '"(' + "|".join(re.escape(name) for name in CAPABILITIES) + ')"'
)

# Phrasings that make a refusal specifically an AUTHORITY refusal, for the
# case where the server did not quote a capability name — a legacy
# read-scope key, say. Deliberately narrow: a generic "Refused: …" is not
# enough, because plenty of ordinary refusals ("that merge has already been
# reverted") are about state, not authority, and telling an agent it lacks a
# capability it actually holds would send it to bother a human for nothing.
_AUTHORITY_MARKERS = (
    "capabilit",
    "is read-only",
    "write-scope",
    "not authorized",
)


def verify_webhook_signature(secret: str, body: bytes, signature_header: str) -> bool:
    """Verify a ledger webhook delivery (v1.3 push convention).

    The ledger signs the exact raw request body with
    ``X-CompanyOS-Signature: sha256=<hex hmac-sha256(secret, body)>``.
    Verify BEFORE parsing the body; constant-time comparison. A payload
    that fails verification is untrusted input, not a change signal.
    """
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header[len("sha256="):])


def canonical_json(value: Any) -> str:
    """The framework's frozen canonical encoding (golden-vector pinned)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


Transport = Callable[[dict[str, Any]], dict[str, Any]]


def _as_list(result: Any, key: str) -> list[dict[str, Any]]:
    """Read a list-returning verb whether or not it is wrapped in an envelope.

    The canonical v1.6 shape for `branch_list` and `merge_list` is a bare
    array, matching `feedback_list`. The protocol forbids a server changing
    an array return into an object, but a *new* deployment is free to have
    chosen an envelope, and an agent stuck on the wrong reading of a merge
    history is a bad failure. Read both; insist on neither.
    """
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        wrapped = result.get(key)
        if isinstance(wrapped, list):
            return wrapped
    return []

# Which ledger kinds a mission of each work class should carry into its goal
# contracts. Every class gets the direction core; the rest follows what that
# work actually decides on. Multi-instance kinds (icp, sop, product...) match
# every committed instance.
CORE_CONTEXT_KINDS = ("vmtm", "okrs", "value-proposition", "business-model")
# Anything that speaks or renders in the company's voice binds these first:
# tone and messaging decide the words, the visual kinds decide the surfaces.
BRAND_VOICE_KINDS = (
    "brand-foundation",
    "brand-positioning-statement",
    "tone-of-voice",
    "brand-messaging-architecture",
)
WORK_CLASS_CONTEXT: dict[str, tuple[str, ...]] = {
    "research": CORE_CONTEXT_KINDS
    + ("icp", "buyer-persona", "buyer-psychology", "competitor-matrix", "pestle-analysis"),
    "architecture": CORE_CONTEXT_KINDS
    + ("product", "tech-stack", "architecture-overview", "north-star-metric"),
    "implementation": CORE_CONTEXT_KINDS
    + ("product", "tech-stack", "architecture-overview", "dev-process", "north-star-metric"),
    "integration": CORE_CONTEXT_KINDS
    + ("product", "tech-stack", "architecture-overview", "integrations-register"),
    "runtime": CORE_CONTEXT_KINDS + ("product", "tech-stack", "security-posture"),
    "repair": CORE_CONTEXT_KINDS + ("product", "tech-stack", "dev-process"),
    "evaluation": CORE_CONTEXT_KINDS + ("product", "north-star-metric", "voice-of-customer"),
    "documentation": CORE_CONTEXT_KINDS + ("product", "brand-positioning") + BRAND_VOICE_KINDS,
    "governance": CORE_CONTEXT_KINDS
    + ("operating-model-canvas", "raci-matrix", "capabilities-map", "financial-policies"),
    "marketing": CORE_CONTEXT_KINDS
    + ("brand-positioning", "messaging-framework", "icp", "funnel-map", "lead-lifecycle", "content-pillars", "gtm-strategy", "customer-touchpoints")
    + BRAND_VOICE_KINDS,
    "sales": CORE_CONTEXT_KINDS
    + ("icp", "buyer-persona", "pricing-packaging", "qualification-framework", "command-of-message", "objection-handling", "battle-card", "sales-process", "elevator-pitch", "customer-touchpoints"),
}
MAX_BUNDLE_DOCUMENTS = 12


class ContextLedgerClient:
    def __init__(self, url: str, token: str, transport: Transport | None = None):
        if not token.startswith("cos_"):
            raise ContextLedgerError("agent keys start with cos_")
        self.url = url
        self.token = token
        self._transport = transport or self._http_transport
        self._next_id = 0
        # Tri-state, and the distinction matters: None means the ledger has
        # not told us what this key holds (pre-v1.6, or not asked yet), an
        # empty tuple would mean it holds nothing.
        self._granted: tuple[str, ...] | None = None
        self._rate_limit: dict[str, Any] | None = None
        # Whether we have already asked. A ledger that reports nothing must
        # be asked once, not once per `can()` — otherwise a loop that checks
        # authority before each step pays a handshake every time.
        self._authority_checked = False

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
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            # An auth refusal is HTTP 401 whose body IS the JSON-RPC error
            # frame (code -32001). Hand that frame back so `_rpc` classifies
            # it exactly as it would on a 200, which makes it a
            # LedgerAuthError rather than a raw HTTPError escaping the
            # module's ContextLedgerError contract.
            try:
                error_body = exc.read()
            except Exception:
                error_body = b""
            frame: Any = None
            try:
                frame = json.loads(error_body.decode("utf-8", "replace"))
            except json.JSONDecodeError:
                frame = None
            if isinstance(frame, dict) and ("error" in frame or "result" in frame):
                return frame
            detail = error_body.decode("utf-8", "replace").strip()
            raise LedgerTransportError(
                f"ledger returned HTTP {exc.code} with no JSON-RPC body"
                + (f": {detail[:200]}" if detail else ""),
                status=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise LedgerTransportError(
                f"ledger unreachable at {self.url}: {exc.reason}"
            ) from exc
        except OSError as exc:
            # Timeouts and dropped connections (socket.timeout,
            # http.client.RemoteDisconnected) land here.
            raise LedgerTransportError(
                f"ledger call to {self.url} failed: {exc}"
            ) from exc
        try:
            return json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise LedgerTransportError(
                f"ledger returned a body that is not JSON: {exc}"
            ) from exc

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """One JSON-RPC round trip; an `error` frame becomes a typed exception."""
        self._next_id += 1
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        response = self._transport(payload)
        if "error" in response:
            raise self._protocol_failure(response["error"])
        return response.get("result", {})

    def _protocol_failure(self, error: Any) -> ContextLedgerError:
        """Classify a JSON-RPC `error` frame (auth and rate limits live here).

        Both refusals happen before a tool is chosen, so neither can arrive
        as a tool result. The message is kept verbatim either way — the
        server's sentence is the useful part; the type is what makes it
        catchable.
        """
        if not isinstance(error, dict):
            return ContextLedgerError(str(error))
        message = str(error.get("message", "ledger error"))
        code = error.get("code")
        data = error.get("data") if isinstance(error.get("data"), dict) else {}
        if code == RATE_LIMIT_ERROR_CODE or message.casefold().startswith("rate limit"):
            self._rate_limit = dict(data) or self._rate_limit
            return LedgerRateLimitError(
                message,
                retry_after_ms=data.get("retry_after_ms"),
                reset_at=data.get("reset_at"),
                limit=data.get("limit"),
                remaining=data.get("remaining"),
            )
        if code == AUTH_ERROR_CODE:
            return LedgerAuthError(message)
        return ContextLedgerError(message)

    def _tool_failure(self, tool: str, text: str) -> ContextLedgerError:
        """Classify an `isError` tool result.

        A capability refusal arrives here, not as a JSON-RPC error, because
        the key authenticated fine — it simply may not do this. Surfacing it
        as its own type is the whole point: an agent that catches
        LedgerCapabilityError knows to ask a human to merge instead of
        retrying a call that will never succeed.
        """
        folded = text.casefold()
        match = _QUOTED_CAPABILITY.search(text)
        capability = match.group(1) if match else None
        refused = capability is not None or any(
            marker in folded for marker in _AUTHORITY_MARKERS
        )
        if refused:
            return LedgerCapabilityError(
                text,
                capability=capability or VERB_CAPABILITY.get(tool),
                granted=self._granted or (),
            )
        if folded.startswith("rate limit"):
            return LedgerRateLimitError(text)
        return ContextLedgerError(text)

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            content = result.get("content", [])
            text = content[0].get("text", "tool failed") if content else "tool failed"
            raise self._tool_failure(name, text)
        if "structuredContent" in result:
            return result["structuredContent"]
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        raise ContextLedgerError("ledger returned no content")

    # --------------------------- Key authority ---------------------------

    def initialize(self) -> dict[str, Any]:
        """The MCP handshake; also how a v1.6 ledger reports this key.

        The result's optional ``agent`` block carries ``{key_name,
        capabilities, rate_limit}``. Older ledgers omit it, which is why
        the granted set is tri-state below: reported, or simply unknown.
        """
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "company-os-context-ledger",
                    "version": LEDGER_PROTOCOL_MINOR,
                },
            },
        )
        self._note_authority(result)
        return result

    def _note_authority(self, payload: Any) -> None:
        """Harvest the key's granted capabilities wherever the ledger says them.

        Read opportunistically from the handshake and from ``config_pull``,
        so an agent that already pulls config never pays for an extra call
        to learn what it may do.
        """
        if not isinstance(payload, dict):
            return
        agent = payload.get("agent")
        block = agent if isinstance(agent, dict) else payload
        granted = block.get("capabilities")
        # An MCP `initialize` result also has a `capabilities` key — the
        # SERVER's, an object. Only a list of strings is a key's grant set.
        if isinstance(granted, list) and all(isinstance(item, str) for item in granted):
            self._granted = tuple(granted)
        limits = block.get("rate_limit")
        if isinstance(limits, dict):
            self._rate_limit = dict(limits)

    def granted_capabilities(
        self, *, refresh: bool = False
    ) -> tuple[str, ...] | None:
        """What this key may do, per the ledger. ``None`` = the ledger did not say.

        ``None`` is not ``()``: an empty tuple would claim the key holds
        nothing, which is a different (and wrong) statement about a ledger
        that predates capability reporting.
        """
        if refresh or (self._granted is None and not self._authority_checked):
            self.initialize()
            self._authority_checked = True
        return self._granted

    def rate_limit(self) -> dict[str, Any] | None:
        """The last call budget the ledger reported, if any."""
        return dict(self._rate_limit) if self._rate_limit is not None else None

    def can(self, capability: str) -> bool:
        """Whether this key holds ``capability`` — a pre-flight, not a gate.

        FAILS OPEN when the ledger reports no set, because the server is the
        only enforcement point and a client that guessed "no" would refuse
        work a perfectly authorized key is allowed to do. Never rely on this
        for safety; rely on it to plan (ask a human to merge up front rather
        than after the branch is built).
        """
        granted = self.granted_capabilities()
        return True if granted is None else capability in granted

    def assert_can(self, capability: str) -> None:
        """Raise LedgerCapabilityError locally when the key demonstrably lacks it."""
        granted = self.granted_capabilities()
        if granted is not None and capability not in granted:
            raise LedgerCapabilityError(
                f'This key does not hold "{capability}". '
                f"{CAPABILITY_MEANING.get(capability, '')} "
                f"It holds: {', '.join(granted) or 'nothing'}. "
                "Ask an owner or admin of the company to grant it.",
                capability=capability,
                granted=granted,
            )

    def capability_for(self, verb: str) -> str | None:
        """The capability a verb needs, for planning and for operator messages."""
        return VERB_CAPABILITY.get(verb)

    # ------------------------------- Verbs -------------------------------

    def config_pull(
        self,
        *,
        branch: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """The company's context index.

        Paging (v1.5) is opt-in: with neither ``cursor`` nor ``limit`` the
        whole document index comes back, exactly as it always has. Pass a
        limit only when a store is large enough that the full index is a
        heavy first call, and drain with ``config_documents``.
        """
        arguments: dict[str, Any] = {}
        if branch:
            arguments["branch"] = branch
        if cursor is not None:
            arguments["cursor"] = cursor
        if limit is not None:
            arguments["limit"] = limit
        result = self._call_tool("config_pull", arguments)
        # v1.6 ledgers echo the calling key's capabilities here, so an agent
        # that pulls config already knows what it may do — no extra call.
        self._note_authority(result)
        return result

    def config_documents(
        self, *, branch: str | None = None, page_size: int = 500
    ) -> list[dict[str, Any]]:
        """Every document in the index, draining pages when the store is large.

        Correct on any ledger: an unpaged server returns everything on the
        first call and reports no cursor, which ends the loop immediately.
        """
        documents: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            page = self.config_pull(branch=branch, cursor=cursor, limit=page_size)
            documents.extend(page.get("documents", []))
            if not page.get("documents_has_more"):
                return documents
            cursor = page.get("documents_cursor")
            if not cursor:
                return documents

    def document_get(self, slug: str, *, branch: str | None = None) -> dict[str, Any]:
        arguments: dict[str, Any] = {"slug": slug}
        if branch:
            arguments["branch"] = branch
        return self._call_tool("document_get", arguments)

    def document_put(
        self,
        *,
        kind: str,
        message: str,
        content: dict[str, Any],
        base_revision: int,
        doc_slug: str | None = None,
        title: str | None = None,
        branch: str | None = None,
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
        if branch is not None:
            arguments["branch"] = branch
        return self._call_tool("document_put", arguments)

    def branch_create(
        self, name: str, *, description: str | None = None
    ) -> dict[str, Any]:
        """Open an overlay branch to draft an alternate company version.

        Merging back to main is a human decision made in the app.
        """
        arguments: dict[str, Any] = {"name": name}
        if description is not None:
            arguments["description"] = description
        return self._call_tool("branch_create", arguments)

    def feedback_list(
        self,
        *,
        product_slug: str | None = None,
        limit: int | None = None,
        before: float | None = None,
    ) -> list[dict[str, Any]]:
        """Raw feedback, newest first.

        ``before`` pages backwards through time: pass the ``at`` of the last
        item you saw. The return stays a plain list, so callers that do not
        page are unaffected.
        """
        arguments: dict[str, Any] = {}
        if product_slug is not None:
            arguments["product_slug"] = product_slug
        if limit is not None:
            arguments["limit"] = limit
        if before is not None:
            arguments["before"] = before
        result = self._call_tool("feedback_list", arguments)
        return result if isinstance(result, list) else []

    def feedback_add(
        self, *, product_slug: str, source: str, text: str
    ) -> dict[str, Any]:
        return self._call_tool(
            "feedback_add",
            {"product_slug": product_slug, "source": source, "text": text},
        )

    def document_history(
        self,
        slug: str,
        *,
        branch: str | None = None,
        from_seq: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """One document's commit log (v1.4): seq, message, author, hash.

        Oldest first from ``from_seq``; ``has_more`` says whether the head
        is beyond this page. Content bodies stay out — ``document_get``
        returns the current content.
        """
        arguments: dict[str, Any] = {"slug": slug}
        if branch is not None:
            arguments["branch"] = branch
        if from_seq is not None:
            arguments["from"] = from_seq
        if limit is not None:
            arguments["limit"] = limit
        return self._call_tool("document_history", arguments)

    def context_changes(
        self, *, since: float | str | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        """What changed since a cursor (v1.3): the runner's poll primitive.

        Returns ``{cursor, has_more, events}``, oldest first. The cursor is
        an opaque string (v1.4 tie-safe form); feed it back verbatim on the
        next call. Webhooks push the same signal; this is the pull side.
        """
        arguments: dict[str, Any] = {}
        if since is not None:
            arguments["since"] = since
        if limit is not None:
            arguments["limit"] = limit
        return self._call_tool("context_changes", arguments)

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

    # ---------------------------- v1.6 verbs -----------------------------
    # Version control with enforced authority. Everything here except
    # branch_merge / merge_revert / document_revert is an ordinary read.

    def document_list(
        self,
        *,
        view: str | None = None,
        branch: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """One page of the document index, optionally one department view.

        The narrow read `config_pull` is not: no profile, no registry, no
        branch list — just documents. Returns ``{documents, has_more,
        cursor, document_count}``; drain it with ``document_list_all``.
        """
        arguments: dict[str, Any] = {}
        if view is not None:
            arguments["view"] = view
        if branch is not None:
            arguments["branch"] = branch
        if limit is not None:
            arguments["limit"] = limit
        if cursor is not None:
            arguments["cursor"] = cursor
        return self._call_tool("document_list", arguments)

    def document_list_all(
        self,
        *,
        view: str | None = None,
        branch: str | None = None,
        page_size: int = 500,
    ) -> list[dict[str, Any]]:
        """Every matching document, draining pages.

        Same shape of loop as ``config_documents``: a server that answers
        in one page reports no cursor and the loop ends immediately.
        """
        documents: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            page = self.document_list(
                view=view, branch=branch, limit=page_size, cursor=cursor
            )
            documents.extend(page.get("documents", []))
            if not page.get("has_more"):
                return documents
            cursor = page.get("cursor")
            if not cursor:
                return documents

    def context_search(
        self,
        query: str,
        *,
        branch: str | None = None,
        limit: int | None = None,
        include: list[str] | None = None,
    ) -> Any:
        """Full-text search over the company's documents.

        Without ``include`` the return is the bare array of document hits
        it has been since v1.2 ``[{slug, title, view, kind, revision,
        on_branch, snippet}]``. With ``include`` naming ``"quotes"`` and/or
        ``"facts"`` (1.10) the server answers with an envelope
        ``{documents, quotes?, facts?}``: ``quotes`` are the matching rows
        of evidence-source key-quote tables ``{slug, title, row_id, quote,
        ...}`` and ``facts`` are live fact-ledger claims ``{id, topic,
        claim, source, source_detail, confidence}``. The array form never
        changes shape; the envelope only appears when asked for.
        """
        arguments: dict[str, Any] = {"query": query}
        if branch is not None:
            arguments["branch"] = branch
        if limit is not None:
            arguments["limit"] = limit
        if include:
            arguments["include"] = list(include)
        return self._call_tool("context_search", arguments)

    def work_list(
        self,
        *,
        status: str | None = None,
        view: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Open work requests an owner has queued for agents (1.10).

        Returns ``{requests, count}``; each request is ``{seq, title,
        brief, view, priority, status, requested_by, claimed_by,
        created_at, updated_at, due_at, result}``. ``status`` defaults to
        ``open`` on the server; a lane-scoped key sees only requests filed
        in its departments or company-wide. Call it before starting work,
        and ``work_claim`` before writing anything for a request.
        """
        arguments: dict[str, Any] = {}
        if status is not None:
            arguments["status"] = status
        if view is not None:
            arguments["view"] = view
        if limit is not None:
            arguments["limit"] = limit
        return self._call_tool("work_list", arguments)

    def work_claim(self, seq: int) -> dict[str, Any]:
        """Take an open request so no other agent starts the same work.

        Returns ``{seq, status: "claimed", claimed_by, claimed_at}``. A
        request already claimed is refused with a sentence naming who
        holds it; the refusal is the answer, not a retry signal.
        """
        return self._call_tool("work_claim", {"seq": seq})

    def work_complete(
        self,
        seq: int,
        summary: str,
        *,
        documents: list[dict[str, Any]] | None = None,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """Finish a request this key claimed, naming what it produced.

        ``documents`` is ``[{slug, branch?}]`` for the documents touched
        (at most twenty) and ``branch`` the branch the work landed on, so
        the person who asked can open the result from the queue. Returns
        ``{seq, status: "done", done_at}``. Only the key that claimed the
        request may complete it.
        """
        arguments: dict[str, Any] = {"seq": seq, "summary": summary}
        if documents is not None:
            arguments["documents"] = documents
        if branch is not None:
            arguments["branch"] = branch
        return self._call_tool("work_complete", arguments)

    def branch_list(self, *, status: str | None = None) -> list[dict[str, Any]]:
        """Every branch, newest first, with its status and document counts.

        ``status`` filters to ``open``, ``merged``, or ``abandoned``; omit
        for all three. Each row carries ``document_count`` (documents
        committed on the overlay) and ``ahead`` (how many of those differ
        from main), so an agent can see what a branch actually proposes
        before diffing it.
        """
        arguments: dict[str, Any] = {}
        if status is not None:
            arguments["status"] = status
        return _as_list(self._call_tool("branch_list", arguments), "branches")

    def branch_diff(self, branch: str) -> dict[str, Any]:
        """What landing this branch would change on main.

        Returns ``{branch, entries: [{slug, kind, title, change,
        base_revision, branch_revision, content_hash, base_content_hash}]}``
        where ``change`` is ``added`` (the branch creates the document on
        main) or ``modified``. Read this BEFORE asking for a merge — it is
        the diff a human is being asked to approve.
        """
        return self._call_tool("branch_diff", {"branch": branch})

    def branch_merge(self, branch: str, *, message: str | None = None) -> dict[str, Any]:
        """Land a branch on main. **Requires `branch:merge`.**

        This is the one verb that changes what every other agent reads as
        the company's truth, so most keys do not hold it and will get a
        ``LedgerCapabilityError`` here — that is the design, not a bug. The
        normal agent workflow is branch, commit, diff, then ask an owner or
        admin to merge.

        No local pre-flight: authority is the server's answer, and a client
        that decided for itself would refuse a key an admin had just
        upgraded. Returns ``{merged, merge_id, branch}``; keep the
        ``merge_id`` — it is what ``merge_revert`` undoes.
        """
        arguments: dict[str, Any] = {"branch": branch}
        if message is not None:
            arguments["message"] = message
        return self._call_tool("branch_merge", arguments)

    def document_revert(
        self,
        slug: str,
        *,
        to_seq: int,
        message: str | None = None,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """Restore a document's content from revision ``to_seq``. Requires `context:revert`.

        ``git revert``, never ``git reset``: the old content is committed
        FORWARD as a new revision with a new seq. Nothing between then and
        now is erased, and ``document_history`` still shows every step
        including this one. Returns ``{seq, content_hash, reverted_from}``,
        where ``seq`` is the NEW revision and ``reverted_from`` is
        ``to_seq``.
        """
        arguments: dict[str, Any] = {"slug": slug, "to_seq": to_seq}
        if message is not None:
            arguments["message"] = message
        if branch is not None:
            arguments["branch"] = branch
        return self._call_tool("document_revert", arguments)

    def merge_revert(self, merge_id: str, *, message: str | None = None) -> dict[str, Any]:
        """Undo a merge by committing every document's prior content forward.

        **Requires `branch:merge`** — the same authority that landed it, for
        the same reason: this changes main for everyone. Also ``git
        revert`` semantics: no revision is rewritten or removed, and a
        document the merge CREATED is archived rather than deleted. A merge
        can only be reverted once; a second attempt is refused. Returns
        ``{reverted, archived}``.
        """
        arguments: dict[str, Any] = {"merge_id": merge_id}
        if message is not None:
            arguments["message"] = message
        return self._call_tool("merge_revert", arguments)

    def merge_list(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        """Merge receipts, newest first: who landed what, and whether it was reverted.

        Each row is ``{merge_id, branch, branch_slug, actor, at,
        entry_count, reverted_at?, reverted_by?}``. A row with
        ``reverted_at`` set is already undone — reverting it again is
        refused.
        """
        arguments: dict[str, Any] = {}
        if limit is not None:
            arguments["limit"] = limit
        return _as_list(self._call_tool("merge_list", arguments), "merges")

    def schema_describe(
        self, *, view: str | None = None, kind: str | None = None
    ) -> dict[str, Any]:
        """The kind registry: every document shape the company can hold.

        Returns ``{views, kinds}`` — views as ``{id, label, description,
        groups, essentials, pulls}`` and kinds as ``{kind, view, title,
        description, group, multiple, version, fields}`` with each field's
        ``{id, label, type, hint, columns}``. This is how an agent learns
        the shapes instead of guessing them; filter with ``view`` or
        ``kind`` when only one is needed.
        """
        arguments: dict[str, Any] = {}
        if view is not None:
            arguments["view"] = view
        if kind is not None:
            arguments["kind"] = kind
        return self._call_tool("schema_describe", arguments)

    # ------------------------- Resource addressing -------------------------

    @staticmethod
    def resource_uri(
        company: str,
        *,
        slug: str | None = None,
        seq: int | None = None,
        branch: str | None = None,
        merge_id: str | None = None,
        kind: str | None = None,
        schema: bool = False,
    ) -> str:
        """Build a ``companyos://`` resource URI (v1.6 addressing scheme).

        The scheme names a thing in the ledger the same way every time, so
        an evidence record, a work order, and a merge receipt can all cite
        the identical string. See references/protocol-v1.md for the grammar.
        """
        base = f"companyos://{company}"
        if schema or kind:
            return f"{base}/schema/{kind}" if kind else f"{base}/schema"
        if merge_id:
            return f"{base}/merge/{merge_id}"
        if branch and not slug:
            return f"{base}/branch/{branch}"
        if not slug:
            raise ContextLedgerError("a resource URI needs a slug, branch, merge, or schema")
        prefix = f"{base}/branch/{branch}" if branch else base
        return f"{prefix}/document/{slug}" + (f"@{seq}" if seq is not None else "")

    def read_resource(self, uri: str) -> list[dict[str, Any]]:
        """Read one ``companyos://`` resource via MCP ``resources/read``.

        Returns the raw ``contents`` array. Resources are a convenience
        surface over the same reads and obey the same authority — a key
        without ``context:read`` gets nothing here either.
        """
        result = self._rpc("resources/read", {"uri": uri})
        contents = result.get("contents", [])
        return contents if isinstance(contents, list) else []

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

    def bundle_for(
        self, work_class: str, *, extra_slugs: list[str] | None = None
    ) -> dict[str, Any]:
        """The hash-pinned context bundle a mission of this work class binds.

        Selects committed documents whose kind belongs to the class's
        context set (plus any explicit extras), capped at
        MAX_BUNDLE_DOCUMENTS, then seals them with ``context_bundle``. Feed
        the result to ``mission_control.bind_context``, which re-verifies
        every hash offline before binding.
        """
        kinds = set(WORK_CLASS_CONTEXT.get(work_class, CORE_CONTEXT_KINDS))
        # Drain the index: on a large store the selection must still see
        # every committed document, not just the first page.
        slugs: list[str] = []
        for document in self.config_documents():
            if (
                document.get("kind") in kinds
                and document.get("contentHash")
                and document.get("status") == "active"
            ):
                slugs.append(document["slug"])
        for slug in extra_slugs or []:
            if slug not in slugs:
                slugs.append(slug)
        return self.context_bundle(slugs[:MAX_BUNDLE_DOCUMENTS])


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
    changes_parser = commands.add_parser("changes", help="context_changes since a cursor")
    changes_parser.add_argument("--since", default=None, help="cursor from the previous call")
    changes_parser.add_argument("--limit", type=int, default=None)
    history_parser = commands.add_parser("history", help="document_history for a slug")
    history_parser.add_argument("--slug", required=True)
    history_parser.add_argument("--from-seq", type=int, default=None)
    history_parser.add_argument("--limit", type=int, default=None)
    append_parser = commands.add_parser("append", help="run_append")
    append_parser.add_argument("--run-id", required=True)
    append_parser.add_argument("--type", required=True)
    append_parser.add_argument("--payload", help="JSON, or @file")
    append_parser.add_argument("--summary")
    bundle_parser = commands.add_parser(
        "bundle", help="hash-pinned context bundle for a work class"
    )
    bundle_parser.add_argument("--work-class", required=True)
    bundle_parser.add_argument("--out", help="write the bundle JSON here")
    materialize_parser = commands.add_parser(
        "materialize", help="write canonical bytes for record-evidence"
    )
    materialize_parser.add_argument("--slug", required=True)
    materialize_parser.add_argument("--dir", required=True)
    # ---------------------------- v1.6 commands ----------------------------
    commands.add_parser("caps", help="what this key is allowed to do")
    documents_parser = commands.add_parser(
        "documents", help="document_list, drained across pages"
    )
    documents_parser.add_argument("--view")
    documents_parser.add_argument("--branch")
    branches_parser = commands.add_parser("branches", help="branch_list")
    branches_parser.add_argument(
        "--status", choices=["open", "merged", "abandoned"], default=None
    )
    diff_parser = commands.add_parser(
        "diff", help="branch_diff — what landing this branch would change"
    )
    diff_parser.add_argument("--branch", required=True)
    merge_parser = commands.add_parser(
        "merge", help="branch_merge — needs the branch:merge capability"
    )
    merge_parser.add_argument("--branch", required=True)
    merge_parser.add_argument("--message")
    revert_parser = commands.add_parser(
        "revert", help="document_revert — commits an old revision forward"
    )
    revert_parser.add_argument("--slug", required=True)
    revert_parser.add_argument("--to-seq", type=int, required=True)
    revert_parser.add_argument("--message")
    revert_parser.add_argument("--branch")
    revert_merge_parser = commands.add_parser(
        "revert-merge", help="merge_revert — needs the branch:merge capability"
    )
    revert_merge_parser.add_argument("--merge-id", required=True)
    revert_merge_parser.add_argument("--message")
    merges_parser = commands.add_parser("merges", help="merge_list, newest first")
    merges_parser.add_argument("--limit", type=int, default=None)
    schema_parser = commands.add_parser(
        "schema", help="schema_describe — the kind registry"
    )
    schema_parser.add_argument("--view")
    schema_parser.add_argument("--kind")
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
        elif args.command == "changes":
            result = client.context_changes(since=args.since, limit=args.limit)
        elif args.command == "history":
            result = client.document_history(
                args.slug, from_seq=args.from_seq, limit=args.limit
            )
        elif args.command == "bundle":
            result = client.bundle_for(args.work_class)
            if args.out:
                Path(args.out).write_text(
                    json.dumps(result, indent=2) + "\n", encoding="utf-8"
                )
        elif args.command == "caps":
            granted = client.granted_capabilities()
            result = {
                "capabilities": list(granted) if granted is not None else None,
                "reported": granted is not None,
                "can_merge": client.can("branch:merge"),
                "rate_limit": client.rate_limit(),
            }
        elif args.command == "documents":
            result = client.document_list_all(view=args.view, branch=args.branch)
        elif args.command == "branches":
            result = client.branch_list(status=args.status)
        elif args.command == "diff":
            result = client.branch_diff(args.branch)
        elif args.command == "merge":
            result = client.branch_merge(args.branch, message=args.message)
        elif args.command == "revert":
            result = client.document_revert(
                args.slug,
                to_seq=args.to_seq,
                message=args.message,
                branch=args.branch,
            )
        elif args.command == "revert-merge":
            result = client.merge_revert(args.merge_id, message=args.message)
        elif args.command == "merges":
            result = client.merge_list(limit=args.limit)
        elif args.command == "schema":
            result = client.schema_describe(view=args.view, kind=args.kind)
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
        # The exit code stays 2 for every failure — callers that already
        # branch on it must not change behavior. What is new is the shape of
        # the printed object: a refusal is machine-readable, so a shell
        # caller can tell "you may not, ask an admin" from "that broke".
        failure: dict[str, Any] = {"ok": False, "error": str(exc)}
        if isinstance(exc, LedgerCapabilityError):
            failure["refused"] = "capability"
            failure["capability"] = exc.capability
            failure["granted"] = list(exc.granted)
        elif isinstance(exc, LedgerRateLimitError):
            failure["refused"] = "rate_limit"
            failure["retry_after_ms"] = exc.retry_after_ms
            failure["reset_at"] = exc.reset_at
        elif isinstance(exc, LedgerAuthError):
            failure["refused"] = "key"
        print(json.dumps(failure, indent=2))
        return 2
    print(json.dumps({"ok": True, "result": result}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
