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

## v1.5 additions (additive)

**Opt-in paging.** `config_pull` accepts `limit` (max 500) and `cursor`,
and always returns `document_count`; when paging it also returns
`documents_has_more` and `documents_cursor` (the last slug of the page,
ordered by slug so a cursor means the same thing across calls). **With
neither argument the whole index comes back exactly as before** — no
existing agent changes behavior, and paging is there for stores large
enough that the full index is a heavy first call. `context_ledger.py`
exposes `config_documents()`, which drains pages and is correct against an
unpaged server too. `feedback_list` accepts `before` (the `at` of the last
item seen) and still returns a plain newest-first array.

## v1.6 additions (additive)

Version control with **enforced authority**: branches and commits stay open
to every writer, landing on main does not, and anything landed can be taken
back without rewriting a byte of history.

### The authority rule

> **An agent may branch and commit freely. Merging to main requires
> `branch:merge`, which an owner or admin grants deliberately.**

This is the load-bearing sentence of the whole protocol, so it is worth
saying why. A commit on a branch is a proposal: it changes what one agent is
working on and nothing else. Landing that branch on main changes what
*every* other agent reads as the company's truth on its next `config_pull` —
the OKRs a mission binds, the pricing a sales agent quotes, the architecture
an implementation agent builds against. That is a different kind of act, so
it takes a different grant, and the grant is not conferred by anything else:
not by having write scope, not by having created the branch, not by being a
member of the company.

Concretely:

- `branch_create` needs `branch:create`. Every write-scope key has it.
- `document_put` needs `context:write`. Every write-scope key has it, on
  main and on branches alike.
- `branch_merge` needs `branch:merge`. **No legacy key has it** — a key
  issued before v1.6 carries the v1.5 scope set, which stops at
  `branch:create`. It must be granted explicitly, per key, by an owner or
  admin.
- On the human side the same rule runs through roles: members write, admins
  and owners merge. One capability name, two ladders, one enforcement path.

The intended agent workflow is therefore: `branch_create` → `document_put`
on the branch → `branch_diff` to see exactly what would change → **ask a
human to merge**. An agent that catches `LedgerCapabilityError` on
`branch_merge` has not hit a bug; it has hit the design, and its correct
next move is to report the branch and the diff to a person.

### The capability model

A `cos_` key carries a set drawn from a closed list. Every capability
implies `context:read` — a writer that cannot read cannot compute a
revision-checked write.

| Capability | Permits |
| --- | --- |
| `context:read` | Read documents, history, search, branches, merges, and the kind registry. |
| `context:write` | Commit revisions with `document_put`, on main or on a branch. |
| `context:revert` | `document_revert`: restore an earlier revision's content by committing it forward. |
| `branch:create` | `branch_create`: open a branch. |
| `branch:merge` | `branch_merge` **and** `merge_revert`: change what main says. Never granted by default. |
| `feedback:write` | `feedback_add`: append raw customer feedback. |
| `run:append` | `run_append`: append execution telemetry. |

**Legacy keys are read through a fixed table, never upgraded.** A key with
no explicit set gets `context:read` for scope `read`, and
`context:read, context:write, branch:create, feedback:write, run:append` for
scope `write`. Note what write scope does *not* confer: `branch:merge` and
`context:revert`. An existing credential must not silently acquire the power
to redefine main or to move a document backwards — new powers are opt-in.

A read-scope key may only ever hold `context:read`; scope and capabilities
can never disagree.

### New verbs

| Verb | Capability | Contract |
| --- | --- | --- |
| `document_list` `{view?, branch?, limit?, cursor?}` | `context:read` | The document index alone — no profile, no registry, no branch list. Returns `{documents, has_more, cursor, document_count}`. Paged like `config_pull`; drain with the client's `document_list_all`. |
| `branch_list` `{status?}` | `context:read` | Every branch newest-first as `[{slug, name, status, document_count, ahead, created_at, merged_at?}]`. `status` filters to `open`, `merged`, or `abandoned`. `ahead` counts the documents that actually differ from main. |
| `branch_diff` `{branch}` | `context:read` | What landing this branch would change: `{branch, entries: [{slug, kind, title, change, base_revision, branch_revision, content_hash, base_content_hash?}]}`, `change` being `added` or `modified`. This is the diff a human is being asked to approve. |
| `branch_merge` `{branch, message?}` | **`branch:merge`** | Land the branch on main, writing one revision per changed document and one **merge receipt**. Returns `{merged, merge_id, branch}`. Keep the `merge_id`: it is what `merge_revert` undoes. |
| `document_revert` `{slug, to_seq, message?, branch?}` | `context:revert` | Commit revision `to_seq`'s content forward as a NEW revision. Returns `{seq, content_hash, reverted_from}`, where `seq` is the new head. |
| `merge_revert` `{merge_id, message?}` | **`branch:merge`** | Undo a merge by committing each document's pre-merge content forward again. A document the merge *created* is archived, not deleted. Returns `{reverted, archived}`. A merge can be reverted once; a second attempt is refused. |
| `merge_list` `{limit?}` | `context:read` | Merge receipts newest-first: `[{merge_id, branch, branch_slug, actor, at, entry_count, reverted_at?, reverted_by?}]`. A row carrying `reverted_at` is already undone. |
| `schema_describe` `{view?, kind?}` | `context:read` | The kind registry: `{views: [{id, label, description, groups, essentials, pulls}], kinds: [{kind, view, title, description, group, multiple, version, fields: [{id, label, type, hint, columns?}]}]}`. How an agent learns the document shapes instead of guessing them. |

Nothing was removed and nothing changed shape. `branch_create`'s v1.1 note
that "there is no merge verb, deliberately" is superseded: there is now a
merge verb, and it is deliberately gated.

### Revert is `git revert`, never `git reset`

**History is never rewritten.** No revision row is ever mutated, renumbered,
or deleted, by any verb, for any actor. A revert reads the old content and
**commits it forward** as a new revision with a new `seq` and a message
naming what it reverted, exactly as `git revert` writes a new commit. So:

- `document_history` after a revert is strictly longer than before, and the
  reverted-past revisions are all still in it.
- The `seq` a revert returns is a *new* number, always greater than the one
  it restored from.
- Reverting a revert is just another revert. There is no special case.
- A merge revert restores content but leaves the merge receipt in place,
  stamped `revertedAt`/`revertedBy`, so the timeline shows the landing *and*
  the taking-back.

This is the product's whole proposition — an agent can trust what
`document_history` says because nothing can quietly edit it — so a server
that implements revert by rolling back rows is not implementing this
protocol.

### Merge receipts

A merge writes one receipt recording, per document, the revision that was
head on main *before* (absent when the merge created the document) and the
revision it wrote. `merge_revert` walks that receipt; it does not re-derive
the diff, because main may have moved since. Receipts are readable via
`merge_list` and addressable as resources.

### Resource URIs

Reads are also addressable as MCP resources under a stable scheme, so an
evidence record, a work order, and a merge receipt can all cite the same
string. The company segment is the key's own company — it is provenance in
the URI, never a selector, and a URI naming another company is refused with
the ordinary not-found sentence.

```
companyos://{company}/document/{slug}              head of the document on main
companyos://{company}/document/{slug}@{seq}        one pinned revision (immutable)
companyos://{company}/branch/{branch}              the branch and its diff vs main
companyos://{company}/branch/{branch}/document/{slug}   the document read through the overlay
companyos://{company}/merge/{merge_id}             one merge receipt
companyos://{company}/schema                       the whole kind registry
companyos://{company}/schema/{kind}                one kind's field template
```

`@{seq}` is the citable form: a revision URI names content that can never
change, which is what makes it admissible alongside a `contentHash`.

### Rate limits

Each key carries a fixed-window call budget enforced on the key row itself.
Exhausting it is a JSON-RPC **error frame** (not a tool result), because the
refusal happens before a tool is chosen:

```json
{ "jsonrpc": "2.0", "id": 4, "error": {
    "code": -32029,
    "message": "Rate limit exceeded for key \"planner\": 120 calls per minute. Retry in 17s.",
    "data": { "limit": 120, "remaining": 0, "reset_at": 1767225600000, "retry_after_ms": 17000 }
} }
```

`reset_at` is epoch milliseconds. This is the only refusal in the protocol
that is worth retrying unchanged; every other one needs a human to grant
something or a caller to send something different.

### Error shapes, and what is catchable

| Condition | Frame | Client type |
| --- | --- | --- |
| Missing / unknown / revoked / expired key | `error.code -32001`, HTTP 401 | `LedgerAuthError` |
| Budget exhausted | `error.code -32029` | `LedgerRateLimitError` |
| Key lacks the capability | tool result with `isError`, message naming the capability in double quotes | `LedgerCapabilityError` |
| Stale write, unknown branch, bad input | tool result with `isError` | `ContextLedgerError` |

A capability refusal is a tool result rather than a protocol error because
the key authenticated perfectly well — it simply may not do this. The
message names the capability, what it permits, and who holds it. It is a
*decision*, not a fault: catch `LedgerCapabilityError` and ask a person,
do not retry.

**Uniform refusals still hold.** Nothing above lets an error enumerate
another tenant: an unknown company and a company you are not in produce the
identical sentence, and a resource URI or `merge_id` belonging to someone
else's company is simply not found. Capability messages are only ever
detailed *after* the caller has proved they belong here.

### Audit

Every authenticated tool call is recorded with the key, the tool, and
whether it succeeded — including the refusals, which is exactly what you
want when auditing a leaked key. A standing credential with no record of its
use is not auditable.

### Key reporting (additive fields)

The `initialize` result may carry an `agent` block, and `config_pull` may
echo the same, so an agent can learn what it may do without an extra call:

```json
{ "agent": { "key_name": "planner",
             "capabilities": ["context:read", "context:write", "branch:create"],
             "rate_limit": { "limit": 120, "remaining": 118, "reset_at": 1767225600000 } } }
```

Both are optional. A client must treat "absent" as *unknown*, never as
*holds nothing* — and must not turn a local capability check into a gate.
The server is the only enforcement point; a client-side check is for
planning (ask for the merge up front) and for a better error message.

### Client

`scripts/context_ledger.py` gains `document_list`, `document_list_all`,
`branch_list`, `branch_diff`, `branch_merge`, `document_revert`,
`merge_revert`, `merge_list`, `schema_describe`, `read_resource`, and
`resource_uri`, plus `granted_capabilities()` / `can()` / `assert_can()`
over the reported set. CLI subcommands mirror them (`caps`, `documents`,
`branches`, `diff`, `merge`, `revert`, `revert-merge`, `merges`, `schema`);
failures still exit 2, and the printed JSON now carries `refused` and
`capability` so a shell caller can tell a refusal from a fault.

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

Since v1.6 the same boundary carries **capabilities** (above): scope says
whether a key may write at all, capabilities say which acts it may perform,
and the two can never disagree because a read-scope key may only ever hold
`context:read`. Keys are additionally rate-limited per window and every
authenticated call is audited. The one act that changes the company's truth
for everyone — merging to main — is behind `branch:merge`, granted per key
by an owner or admin and held by no legacy key.

## Versioning

This is `context-ledger.v1` (`config_pull` echoes it as `protocol`), at
minor **1.6**. Additive fields are non-breaking; verb or hashing changes
require `v2` and a deliberate, reviewed update to this document.

The additive contract, precisely, because agents in the field depend on it:
no verb is ever removed, no return shape ever changes from an array to an
object (or the reverse), and no parameter that was optional ever becomes
required. New capability means a new verb or a new optional parameter. A
v1.5 agent runs unchanged against a v1.6 ledger; it simply never merges.
