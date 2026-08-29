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

## Versioning

This is `context-ledger.v1` (`config_pull` echoes it as `protocol`).
Additive fields are non-breaking; verb or hashing changes require `v2` and a
deliberate, reviewed update to this document.
