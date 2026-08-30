# Context Ledger Protocol — context-ledger.v1

The wire contract between the open-source Company OS framework and a hosted
context ledger (reference implementation: company-os-web). The framework is
the operating system; the ledger is shared company context and execution
history — **never a control plane**. Any server implementing this contract
can serve a Company OS instance.

## Transport

MCP over Streamable HTTP in stateless JSON mode: one `POST` endpoint
speaking JSON-RPC 2.0 (`initialize`, `ping`, `tools/list`, `tools/call`;
`notifications/*` acknowledged with `202` and no body). No SSE stream: every
verb is a single request and a single response.

Auth: `Authorization: Bearer cos_<hex>` — an agent key issued per company,
per agent, with scope `read` or `write` (write includes read). The key
selects the company; no tool takes a company argument. Operators use the web
session, never bearer keys.

## Verbs

The skill doctrine names the verbs with dots (`config.pull`,
`document.put`, `run.append`); on the wire they are the same verbs with
MCP-safe underscores.

| Verb | Scope | Contract |
| --- | --- | --- |
| `config_pull` | read | Company profile, department views, the full kind registry (kind, view, title, group, multiple, version), and every committed document with `revision` and `contentHash`. Call before writing; do not invent structure the ledger already holds. |
| `document_get` `{slug}` | read | One document as typed JSON: `content` (field id → value), the template (`fields` with labels, types, table columns, authoring hints), `revision`, `contentHash`. An uncommitted registry kind returns its empty template. |
| `document_put` `{kind, message, content, base_revision?, doc_slug?, title?}` | write | Commit one revision. **Revision-checked**: `base_revision` must equal the revision the caller read (`0` for a new document); a mismatch or an omitted base on an existing document is rejected. Unchanged content is rejected. The commit records `authorKind: "agent"` with the key's name. |
| `run_append` `{run_id, type, payload?, summary?}` | write | Append one execution-telemetry event (≤64KB payload). Append-only. `type: "brief_snapshot"` with the operator-brief economics payload surfaces execution economics on the company overview. |

Deliberately absent: dispatch, leases, scheduler control, acceptance,
spend. Authority stays in the framework's signed, hash-chained controller.

## Content addressing (the evidence bridge)

`contentHash` is **sha256 over Company OS canonical JSON** — exactly
`json.dumps(value, sort_keys=True, separators=(",", ":"),
ensure_ascii=True)`, the encoding pinned by the framework's frozen golden
vectors (`tests/test_canonical_digest_vectors.py`). Document content is
strings, string lists, and `{rows: string[][]}` tables only, so the encoding
is language-independent.

Because the encodings match, a ledger revision is admissible evidence in the
framework's fail-closed gates: `context_ledger.py materialize` writes a
revision's canonical bytes to a file whose file sha256 **equals** the
ledger's `contentHash`, so `record-evidence` ingests it and every downstream
grant, quality score, and audit cites the exact ledger revision.

## Field value shapes

| Field type | Value |
| --- | --- |
| `text` | string |
| `list` | `string[]` |
| `table` | `{ "rows": string[][] }`, columns per the template |

## Client

`scripts/context_ledger.py` (stdlib-only) implements the contract:
`config_pull`, `document_get`, `document_put`, `run_append`,
`verify_content_hash`, `materialize`, and `context_bundle` (a compact
`{slug, revision, content_hash}` block for goal contracts). Errors surface
as `ContextLedgerError` with the server's sentence intact.

## v1.1 additions (additive, still context-ledger.v1)

**Branches.** The ledger versions the organization the way git versions
code: a branch is an overlay over main that stores only the documents
committed on it. `config_pull` returns `branches` and accepts `branch`;
`document_get`/`document_put` accept `branch` (omit or `"main"` for main).
Reads through a branch fall through to main for untouched documents;
`base_revision` refers to the revision read *through that overlay*. New
verb `branch_create {name, description?}` (write) opens a branch — agents
may draft alternate strategies, but **merging into main is a human decision
made in the app**, with per-document conflict resolution when main moved
since the fork. There is no merge verb, deliberately.

**Feedback.** Raw customer feedback is append-only ground truth attached to
product documents: `feedback_list {product_slug?, limit?}` (read) and
`feedback_add {product_slug, source, text}` (write, verbatim quotes only).
The intended loop: agents read the raw feedback, find the patterns, and
commit the synthesis into the product document's `feedbackThemes` field
with `document_put` — so the analysis is versioned context with an author,
not a black-box score.

**Media** (product photos/videos/files on Wasabi S3) is an app surface, not
a protocol verb: bytes move via presigned URLs between browser and bucket.
A signed media verb may join a later protocol version.

## v1.2 additions (additive)

**Search.** `context_search {query, branch?, limit?}` (read) — full-text
over the company's documents, filtered to the key's company inside the
search index itself. Returns compact hits (slug, title, view, revision,
snippet); follow with `document_get` for typed content.

**Context bundles (client convention, not a verb).** `context_ledger.py
bundle --work-class X` selects committed documents by the work class's kind
set (`WORK_CLASS_CONTEXT`), seals them with `context_bundle`, and
`mission_control.bind_context` re-verifies the seal and every per-document
hash **offline, fail-closed** before the mission binds
`{slug, kind, revision, content_hash}` references into its state. The
controller never fetches; the network stops at the client.

## v1.3 additions (additive)

**Change signal — pull.** `context_changes {since?, limit?}` (read) returns
the company's context events oldest-first past a numeric cursor:
`{cursor, has_more, events: [{type, at, actor, message, docSlug?, kind?,
view?, revision?, branch?}]}`. Pass the returned `cursor` back on the next
call. This is the runner's poll primitive: react to commits, branch events,
and new feedback without re-pulling config. Event `revision` reflects the
document's revision at read time, not at event time — a change signal, not
a history verb; follow with `document_get`.

**Change signal — push (webhook convention).** The app can register HTTPS
endpoints per company. Each context event POSTs JSON
`{protocol: "context-ledger.v1", event, company, at, data}` with headers
`X-CompanyOS-Event: <event>` and
`X-CompanyOS-Signature: sha256=<hex hmac-sha256(secret, raw body)>`.
The signing secret is issued once at registration. Receivers MUST verify
the signature over the exact raw bytes before parsing
(`context_ledger.verify_webhook_signature`); an unverified payload is
untrusted input. Webhooks carry no authority — they are a doorbell, and the
runner still reads through the authenticated verbs.

**Runner (client convention, not a verb).** `ledger_runner.py` turns the
change signal into framework work: declarative triggers (cadence per work
class, feedback backlog threshold, kind-watch on `context_changes`) emit
work orders carrying a sealed `bundle_for` context bundle, and the runner
appends `run_append` telemetry so the company timeline shows what woke up
and why. Dispatch authority stays in the controller: a work order is an
invitation to run the mission loop, never a lease.

## v1.4 additions (additive)

**History.** `document_history {slug, branch?, from?, limit?}` (read)
returns a document's commit log oldest-first: `{seq, message, author_kind,
author, at, content_hash, template_version}` per revision, with `has_more`.
Content bodies stay out — `document_get` returns the head; a cited
revision is addressed by its `content_hash`.

**Tie-safe change cursor.** `context_changes` now returns an **opaque
string cursor** (`"timestamp:id"`); pass it back verbatim. Reading resumes
at ≥ the timestamp and skips past the id among equal timestamps, so two
events sharing a creation time can never be lost the way a strict
greater-than on timestamp alone could lose one. Legacy numeric `since`
values are still accepted with their original strictly-after semantics.

**Scoped and expiring keys (server-side; no wire change).** A `cos_` key
may carry **department lanes**: `document_put` is rejected for kinds
outside the key's views, and `feedback_add` requires the product lane —
the error names the lanes. A key may also carry an expiry; an expired key
stops authenticating exactly like a revoked one. Read verbs stay
company-wide: context is one fabric, but write authority can be delegated
one department at a time.

## Tenancy & security model

One deployment serves many companies. The boundary is enforced server-side
at every layer: web sessions resolve through company membership on every
query and mutation (with identical not-found/not-member errors, so slugs
cannot be enumerated); agent keys are company-scoped secrets (sha256-stored,
shown once, revocable, read/write scoped) and the key itself selects the
company — no verb takes a company argument; search is filtered inside the
index; input sizes are capped (256KB canonical content, 64KB run payloads,
8KB feedback). Roles: owners manage everyone, admins manage members,
members manage nothing. Agents are never members — they hold keys.

## Versioning

This is `context-ledger.v1` (`config_pull` echoes it as `protocol`).
Additive fields are non-breaking; verb or hashing changes require `v2` and a
deliberate, reviewed update to this document.
