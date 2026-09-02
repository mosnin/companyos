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
| `document_put` `{kind, message, content, base_revision?, base_content_hash?, doc_slug?, title?, review_every_days?, branch?}` | write | Commit one revision. **Revision-checked**: `base_revision` must equal the revision the caller read (`0` for a new document); a mismatch or an omitted base on an existing document is rejected. Send `base_content_hash` too and the write is also checked against the exact head you read, which catches a rewrite that landed at the same revision number. Unchanged content is rejected. The commit records `authorKind: "agent"` with the key's name. Returns `{doc_slug, revision, content_hash}`. |
| `run_append` `{run_id, type, payload?, summary?}` | write | Append one execution-telemetry event (≤64KB payload). Append-only. `type: "brief_snapshot"` with the operator-brief economics payload surfaces execution economics on the company overview. |

Deliberately absent: dispatch, leases, scheduler control, acceptance,
spend. Authority stays in the framework's signed, hash-chained controller.

## Content addressing (the evidence bridge)

`contentHash` is **sha256 over Company OS canonical JSON** — exactly
`json.dumps(value, sort_keys=True, separators=(",", ":"),
ensure_ascii=True)`, the encoding pinned by the framework's frozen golden
vectors (`tests/test_canonical_digest_vectors.py`). Every document field
value serializes as a JSON string, an array of strings, or an object of
string arrays (see **Field value shapes**), so no number formatting or
float repr ever enters the hashed material and the encoding is
language-independent.

Because the encodings match, a ledger revision is admissible evidence in the
framework's fail-closed gates: `context_ledger.py materialize` writes a
revision's canonical bytes to a file whose file sha256 **equals** the
ledger's `contentHash`, so `record-evidence` ingests it and every downstream
grant, quality score, and audit cites the exact ledger revision.

## Field value shapes

There are **ten** field types, not three. `schema_describe` is authoritative:
its `content_encoding` block states the wire shape of every one of them, and
a server's answer beats this table if they ever disagree.

| Field type | Value |
| --- | --- |
| `text` | A JSON string. |
| `select` | A JSON string drawn from the field's `options`. The empty string means unset. |
| `date` | An ISO date string (`YYYY-MM-DD`), or the empty string when unset. |
| `number` | A finite number **serialized as a JSON string**; honour the field's `minimum`, `maximum` and `step`. Never a JSON number: that is what keeps the hash language-independent. |
| `list` | `string[]`, one entry per bullet. |
| `table` | `{ "rows": string[][] }`. Every row carries exactly the declared cell count, in the declared column order; a short or extra-wide row is refused before normalization. |
| `structured-list` | `{ "rows": string[][], "rowIds": string[] }`; see stable row IDs below. |
| `structured-table` | `{ "rows": string[][], "rowIds": string[] }`, columns per the template. |
| `reference` | A structured value. Document scope uses the declared ledger-pointer columns: target identity, kind, tenant/branch, optional immutable revision and content hash, and pin mode (`live`, `branch`, `revision`). Every other scope uses one declared `referenceId` column carrying that scope's stable identity; it is **not** a document pointer. |
| `person` | A structured value with provider-neutral `personId`, display name and email columns. |

Fields the kind does not declare are dropped on commit; declared fields you
omit keep their empty value.

### Stable row IDs

Every tabular field except plain `table` carries a parallel `rowIds` array:
one immutable id per row, travelling with that row across edits and
reordering, so a reference to "row 3" survives someone inserting a row above
it. A write that omits them, or whose `rowIds` length does not match `rows`,
is refused with `invalid-stable-row-ids`. **Sending a `structured-table` as a
bare `{rows: [...]}` does not work**: that shape is only correct for `table`.

Inside a table-shaped field, a **non-document** reference cell encodes like
this:

- singular: the stable ID string itself;
- plural: `stable-ref:v1:` followed by a URI-encoded JSON array of strings;
- a singular ID that itself begins with that prefix keeps a canonical
  one-item wrapper, so it cannot be mistaken for protocol bytes.

An unambiguous legacy raw single ID stays readable and is normalized into the
versioned plural form on the next write. Legacy delimiter-authored values are
preserved byte for byte and **refused** until explicitly migrated: the server
never guesses how to split them. Blank IDs, duplicates, malformed payloads
and excess IDs are refused. This validates syntax and cardinality only;
existence is checked only by domain views holding the exact local producer
table, never by a universal registry of opaque IDs.

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
| `branch:merge` | `branch_merge`, `merge_revert` **and** `venture_sync`: change what main says. Never granted by default. |
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
| `document_list` `{view?, branch?, limit?, cursor?}` | `context:read` | The document index alone, with no profile, no registry and no branch list. Returns `{protocol, branch, view, documents, document_count, has_more, cursor}` (plus the `documents_has_more` / `documents_cursor` aliases kept for v1.5-preview clients). Each document carries `slug, kind, view, title, status, group, multiple, revision, content_hash, last_message, last_author, on_branch, forked_from_seq, updated_at` and a **`review` block** (see below). Paged like `config_pull`; drain with the client's `document_list_all`. |
| `branch_list` `{status?, limit?}` | `context:read` | **An envelope, not a bare array**: `{protocol, counts: {open, merged, abandoned, total}, branches}`. Each branch is `{slug, name, description, status, creator, created_at, merged_at, document_count, commit_count, views, last_merge}`, newest first; `last_merge` is `{merge_id, at, by, message, documents, reverted_at}` or `null`, so undoing a landing needs no second call. `status` filters to `open`, `merged` or `abandoned`. |
| `branch_diff` `{branch}` | `context:read` | What landing this branch would change: `{protocol, branch: {slug, name, status, description, created_at, merged_at}, summary: {added, clean, conflict, identical}, entries}`. Each entry is `{slug, title, kind, view, branchRevision, branchMessage, forkedFromSeq, mainRevision, state}` where `state` is `added` (main has no such document), `clean` (main has not moved since the fork), `conflict` (main moved underneath it) or `identical` (same bytes as main). This is the diff a human is being asked to approve, and the call to make before `branch_merge`, which refuses while any entry is an unresolved conflict. |
| `branch_merge` `{branch, message?, resolutions?}` | **`branch:merge`** | Land the branch on main, writing one revision per changed document and one **merge receipt**. Returns `{protocol, branch, branch_name, merged, merge_id, message}`. Pass one `resolution` per conflicting slug from `branch_diff` (`take-branch` or `keep-main`); omit when the diff shows none. Keep the `merge_id`: it is what `merge_revert` undoes. |
| `document_revert` `{slug, to_seq, message?, branch?}` | `context:revert` | Commit revision `to_seq`'s content forward as a NEW revision. Returns `{protocol, doc_slug, branch, seq, revision, content_hash, reverted_from}`, where `seq` is the new head. |
| `merge_revert` `{merge_id, message?}` | **`branch:merge`** | Undo a merge by committing each document's pre-merge content forward again. A document the merge *created* is archived, not deleted. Returns `{protocol, merge_id, branch, branch_name, reverted, archived}`. A merge can be reverted once; a second attempt is refused. |
| `merge_list` `{branch?, limit?}` | `context:read` | **An envelope, not a bare array**: `{protocol, merge_count, has_more, merges}`. Each receipt is `{merge_id, branch, branch_name, branch_status, actor, by, message, at, entry_count, document_count, created_count, updated_count, reverted, reverted_at, reverted_by, documents: [{slug, created}]}`, newest first. A row carrying `reverted_at` is already undone. |
| `schema_describe` `{view?, kind?}` | `context:read` | The kind registry: `{protocol, registry, content_encoding, views, kinds}`. `views` is `[{id, label, description, groups, essentials, pulls}]`; `kinds` is `[{kind, view, title, description, group, multiple, version, fields: [{id, label, type, hint, options?, columns?, reference?, minimum?, maximum?, step?}]}]`. `content_encoding` is the authoritative wire shape of every field type (see **Field value shapes**). `registry` reports `custom_kinds.truncated` and `main_document_scan.truncated`: check them before treating a kind or instance list as complete, and query an exact `kind` to reach a company-defined kind beyond the window. How an agent learns the document shapes instead of guessing them. |

Nothing was removed. `branch_create`'s v1.1 note that "there is no merge
verb, deliberately" is superseded: there is now a merge verb, and it is
deliberately gated.

**Two documented exceptions to the array rule.** `branch_list` and
`merge_list` ship as envelopes, not the bare arrays an earlier draft of this
document described. They were envelopes from the day they shipped, so no
deployed client ever saw the array form; the framework client's `_as_list`
accepts either and is the reason nothing broke. They are the *only* two
exceptions: everywhere else, a return that is an array stays an array.
`feedback_list` and `context_search`, in particular, are still bare arrays
(`context_search` answers with an envelope only when asked to with `include`,
see the 1.10 additions).

### The review block

`document_list` returns a `review` block per document, and it is additive:
an agent that ignores it reads exactly what it read before.

```json
{ "review": { "state": "fresh | due | stale | unscheduled",
              "reviewed_at": 1767225600000,
              "review_every_days": 90,
              "owner": "Dana Okafor" } }
```

The cadence is set by `document_put`'s `review_every_days` (1 to 3650). It is
**metadata, not content**: setting it never changes the document's
`content_hash`, so a cadence change is not a revision and cannot invalidate a
citation. `unscheduled` means no cadence is set, which is a statement about
the document, not a complaint about it. `context_compose` reads staleness
from the same place.

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
**One counter, two ceilings**: the reference implementation meters a 60000 ms
window and allows 300 reads or 60 writes against the same count, a write
being any call whose capability is not `context:read`. A key that has spent
60 calls in the window reading may keep reading and cannot write until the
window rolls, which is the safe direction for a credential guard.

Exhausting it is a JSON-RPC **error frame** (not a tool result), because the
refusal happens before a tool is chosen:

```json
{ "jsonrpc": "2.0", "id": 4, "error": {
    "code": -32029,
    "message": "Rate limit reached for the key \"planner\": at most 60 write call(s) per 60s window (reads 300, writes 60). The window resets at …",
    "data": { "limit": 60, "remaining": 0, "reset_at": 1767225600000, "retry_after_ms": 17000 }
} }
```

`limit` is the ceiling **this call** was charged against, and `reset_at` is
epoch milliseconds. This is the only refusal in the protocol that is worth
retrying unchanged; every other one needs a human to grant something or a
caller to send something different.

### Error shapes, and what is catchable

| Condition | Frame | Client type |
| --- | --- | --- |
| Missing / unknown / revoked / expired key | `error.code -32001`, HTTP 401 | `LedgerAuthError` |
| Budget exhausted | `error.code -32029` | `LedgerRateLimitError` |
| Key lacks the capability | tool result with `isError`, message naming the capability in double quotes | `LedgerCapabilityError` |
| Stale write, unknown branch, bad input | tool result with `isError` | `ContextLedgerError` |
| Ledger unreachable, timed out, connection dropped, or an HTTP status whose body is not a JSON-RPC frame | no frame at all | `LedgerTransportError` |

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
             "scope": "write",
             "capabilities": ["context:read", "context:write", "branch:create"],
             "views": ["marketing"],
             "rate_limit": { "window_ms": 60000,
                             "read_limit": 300,
                             "write_limit": 60,
                             "limit": 300,
                             "remaining": 297,
                             "reset_at": 1767225600000 } } }
```

`rate_limit` states both ceilings **and** the live counter: `limit` is the
ceiling the call carrying this block was charged against, `remaining` is what
is left of it in this window, and `reset_at` is when the window rolls. The
three shared names match the `-32029` refusal's `data` block exactly, so a
caller can budget proactively instead of learning its allowance by being
refused once. `views` is the key's department lanes, or `null` when it is
unrestricted.

Both blocks are optional. A client must treat "absent" as *unknown*, never as
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

## v1.7 to v1.9 additions (additive)

Twenty-five verbs joined the contract after v1.6, in four groups. Nothing was
removed, no return shape changed, and every one of them is priced from the
same closed capability list, so a v1.6 agent is unaffected: it simply never
calls them.

Three things are true of the whole tier and are not repeated on every row:

- **Branch overlays.** A verb that takes `branch` reads or writes through the
  overlay exactly as `document_get` does. The canvas and portfolio readers
  take it; the dataset, venture and fact verbs do not, because datasets,
  ventures and facts live on main only.
- **Lanes.** A key bound to department lanes is refused by
  `dataset_create`, `dataset_row_put`, `dataset_row_delete`,
  `dataset_row_revert`, `venture_artifact_set`, `venture_artifact_accept`,
  `venture_artifact_skip`, `venture_define_kind` and `venture_sync` when the
  target is filed outside its departments. `context_note` is the deliberate
  exception: a fact is company-wide by design, it has a topic and never a
  department, so there is no lane to check a claim against.
- **Bounded reads.** Several of these returns are windows over a store that
  can be larger than one response. Where a return carries `truncated`,
  `atLeast`, `limit` or a `note`, read them: they are the difference between
  "this is everything" and "this is the newest 200 of an unknown number".

### Connected canvases and the portfolio

| Verb | Capability | Contract |
| --- | --- | --- |
| `canvas_graph` `{branch?}` | `context:read` | The connected canvas graph across Business Model, Customer Profile, Value Map, Value Proposition Fit, Explore/Exploit, guidance, culture, pattern, shift, metrics, Team Alignment, Business Environment, Assumptions, Test, Learning and Corporate Identity kinds. Returns `{protocol, branch, complete, edge_scope, non_document_reference_resolution, node_count, edge_count, issue_count, nodes, edges, issues}`. Edges are rebuilt only from committed document-scoped references, so overlays, reverts and immutable pins stay authoritative; each resolved edge carries a followable `target_uri`, and a revision pin adds `immutable_target_uri`. Opaque non-document IDs stay inside content. |
| `canvas_validate` `{branch?, document_slug?}` | `context:read` | Structural integrity of the whole overlay, or of one canvas slug. Returns `{protocol, branch, document, validation_scope, non_document_reference_resolution, valid, checked_documents, issue_count, issues, note}`. Document pointers are checked for dangling, cross-tenant, kind-mismatched, wrong-branch, immutable-hash and canonical-shape failures; non-document IDs for syntax and cardinality, plus exact local relationships where the producer table is present. A `valid` result is deliberately not proof of fit or of readiness. |
| `portfolio_snapshot` `{branch?}` | `context:read` | The Explore/Exploit operating snapshot: `{protocol, branch, coordinate_scale, portfolio_count, initiative_count, explore_count, exploit_count, unassigned_count, portfolios, portfolio_items, initiatives}`, with revision and content identities, canonical 0 to 100 coordinates, and source-defined zones where the required scores are present. It never promotes an initiative or claims transfer readiness. |

### Typed datasets

A dataset is the typed table a company **tracks records** in, as against the
documents it reasons in prose about: platforms it got listed on, conferences
applied to, vendors under contract. Rows are versioned and tombstoned exactly
as documents are, and `dataset_row_revert` is `git revert`, never `git reset`.

| Verb | Capability | Contract |
| --- | --- | --- |
| `dataset_list` `{view?}` | `context:read` | `{datasets}`: slug, title, department, column count and live row count. |
| `dataset_describe` `{dataset}` | `context:read` | `{slug, title, view, description, schema_version, rows, columns, cell_encoding}`. Each column carries `id`, `label`, `type`, whether it is required, and for a select the exact permitted `options`. `cell_encoding` states the JSON encoding of every cell type. Read this before writing: a cell that does not match its column's type is refused, never coerced. |
| `dataset_query` `{dataset, limit?, include_deleted?}` | `context:read` | `{dataset, schema_version, columns, rows}`, newest first, `limit` default 100 and max 200. Each row carries its `row_key` (the stable handle every write takes back), its cells, its revision number and its content hash. Tombstoned rows are omitted unless `include_deleted` is true. |
| `dataset_row_history` `{dataset, row_key}` | `context:read` | `{rowKey, deleted, revision, versions}` oldest first; each version is `{seq, label, message, author, authorKind, contentHash, deleted, at}`. This is where `dataset_row_revert`'s `to_seq` comes from. |
| `dataset_create` `{view, title, columns, slug?, description?}` | `context:write` | Create a typed table. `columns` is `[{label, type, required?, options?, hint?}]` where `type` is one of `text`, `long-text`, `number`, `date`, `checkbox`, `url`, `email`, `select`, `multi-select`, `document`. A select or multi-select must declare its options. Returns `{slug}`. |
| `dataset_row_put` `{dataset, cells, message, row_key?}` | `context:write` | Add a row (omit `row_key`) or update one (pass it). A write **merges** over the row's current cells, so name only the columns you are changing; supplying your own `row_key` makes a retry idempotent instead of duplicating the row. Returns `{rowKey, revision, contentHash, created}`. |
| `dataset_row_delete` `{dataset, row_key, message}` | `context:write` | Tombstone, never erase: a delete appends a version marking the row gone and its history stays readable. Returns `{rowKey, revision}`. Refuses a row that is already deleted. |
| `dataset_row_revert` `{dataset, row_key, to_seq, message?}` | `context:revert` | Commit an earlier version's cells forward as a new version. Reverting to a version that was a deletion re-deletes the row; reverting a deleted row to a live version brings it back. Returns `{rowKey, revision, restoredFrom, contentHash}`. |

**One caveat on dataset content hashes.** A `number` column stores a real JSON
number, not the stringified form a document's `number` field uses, so a
dataset row's `contentHash` is computed over material whose float repr differs
between JavaScript and Python. Dataset row hashes are therefore **server-local
identity**: they are stable content addresses within one ledger, and they are
not cross-language citable the way a document's `contentHash` is. Do not feed
one to the framework's evidence bridge.

### Venture build

The build workflow for a company that is not operating yet: `stage` is
`building`, and `venture_sync` is the act that ends it. The taxonomy Library
these verbs expose is **reference material, never a queue**: no verb here
returns a readiness score, and none of them gate the handover.

| Verb | Capability | Contract |
| --- | --- | --- |
| `venture_state` | `context:read` | `{slug, name, stage, shapes, concept, startedAt, syncedAt, contextVersion, referenceLibrary, handover}`. `referenceLibrary` is explicitly `referenceOnly: true` and carries `phases`, `artifacts` and an optional `suggestedSequence` which is a suggestion and not a required queue. Answers only for stage `building`. |
| `venture_handover_preview` | `context:read` | The bounded factual risk review required immediately before handover: `{contract: "venture-handover-review.v3", stage, acknowledgementRequired, contextVersion, reviewedSnapshotDigest, contextSnapshot, artifactReferenceSnapshot, warnings, note}`. Lower-bound and truncation-aware fact, topic, document, dataset, row-count, custom-kind, contradiction and assumption summaries, capped warning samples, and every warning. It never returns a readiness score and never copies the full ledger. Any semantic context change invalidates the digest. |
| `venture_method` `{artifact?}` | `context:read` | Optional Library guidance for one named output: method steps, review checks, audit questions and common failure modes. Omit `artifact` for the whole Library. |
| `venture_brief` `{artifact?}` | `context:read` | A focused brief for one deliberately selected Library method: `{venture, artifact, source, opening, questions, ...}`, including how many founder questions remain. Omit `artifact` and it returns adaptive-ledger guidance rather than silently defaulting to a fixed queue. |
| `venture_publish_check` `{act?}` | `context:read` | `{acts}`: a human-review aid for an outward, irreversible act (`publish-marketing`, `list-publicly`, `take-payment`, `sign-customer`, `launch-publicly`, `run-paid-acquisition`, `hire-employee`, `raise-investment`, `handle-personal-data`). Surfaces conditions a person must confirm and what is deliberately not required. It never grants permission, blocks an act, or claims readiness. |
| `venture_artifact_set` `{artifact, status?, doc_slug?, dataset?, sources?, answers?, reopen?}` | `context:write` | Attach one selected Library method's document, table, sources, or method-specific answers. An accepted or skipped artifact refuses edits unless `reopen: true`, which returns it to drafting and clears the decision. Returns `{artifactId}`. `context_note` remains the canonical cross-session ledger: record the underlying claims there. |
| `venture_artifact_accept` `{artifact}` | `context:write` | Mark one Library output accepted within its method sequence. Library-local checks refuse missing content, unsettled dependencies or missing citations, but acceptance never certifies readiness. Returns `{artifactId}`. |
| `venture_artifact_skip` `{artifact, reason}` | `context:write` | Record that one non-core reference does not apply. A method-local core step cannot be skipped; leave the whole optional method unused instead. Returns `{artifactId}`. |
| `venture_define_kind` `{kind, view, title, fields, description?, rationale?}` | `context:write` | Define a company-scoped document type the compiled registry does not have, or override a derived Builder kind. `fields` uses the validated FieldSpec contract (the ten types above, with the applicable `options`, `columns`, `reference`, `allowMultiple`, `minimum`, `maximum`, `step`); runtime custom kinds do not declare canvas layout areas. An identical redefine is a no-op. Structural changes version the kind before any document uses it; afterwards fields and owning department are frozen, while title, description and rationale stay editable. Returns `{kind, version}`. |
| `venture_sync` `{acknowledge_context_review, reviewed_snapshot_digest}` | **`branch:merge`** | Hand the venture over: it stops being a build and becomes an operating company. Call `venture_handover_preview` first, review its bounded summary, capped samples, truncation labels and every warning, then pass that `reviewedSnapshotDigest` with `acknowledge_context_review: true`. A stale context revision is refused. Returns a compact durable receipt: `{syncId, slug, artifactCount, artifactReferenceCount, documentCount, datasetCount, warnings, contextSnapshot, artifactReferenceSnapshot, reviewedContextVersion, reviewedSnapshotDigest}`. It never certifies completeness or readiness. |

**Why `venture_sync` costs `branch:merge`.** It is the same act the capability
was named for: it changes what every other agent reads as the company's truth,
all at once and for every department. A default Builder key deliberately
cannot flip a company's stage, and the server's refusal says so by name. It is
also lane-checked against every department, because a handover promotes all of
them and leaves none alone.

### The adaptive fact ledger

Facts are atomic claims with provenance, recorded the moment they are learned
and read back by topic. They are company-wide by design and are the reason
`context_note` is the one write verb lanes do not fence.

| Verb | Capability | Contract |
| --- | --- | --- |
| `context_note` `{facts}` | `context:write` | Record what you just learned. `facts` is `[{topic, claim, source, confidence, source_detail?, question?, supersedes?, conflicts_with?}]` where `source` is `founder`, `research` or `derived` and `confidence` is `stated`, `evidenced` or `assumed`. `source_detail` is **required** when `confidence` is `evidenced`, and must name the URL, document revision or dataset row. Correct with `supersedes`; record a disagreement in `conflicts_with` rather than silently reconciling it. Returns `{recorded, superseded}`. |
| `context_known` `{topic?, search?}` | `context:read` | Live facts grouped by topic: `{mode, order, total, atLeast, truncated, limit, note, topics}`, each topic being `{topic, count, facts}`. Call it first in every session. All-ledger and topic reads are newest-first bounded windows; `search` is a relevance-ranked bounded window. Inspect `truncated` and `note` before treating the answer as the whole retained ledger. |
| `context_gaps` | `context:read` | Where the context is weak, and only what can honestly be measured: `{factCount, factCountAtLeast, topicCount, topicCountAtLeast, truncated, note, thinTopics, thinTopicsExact, unevidenced, contradictions, documentCount, writtenKinds, customKinds, unwritten}`. `thinTopics` were opened and dropped, `unevidenced` are live assumptions still open, `contradictions` are live facts flagged as disagreeing, and `unwritten` inventories kinds with no main document. It deliberately does not tell you what to ask next, and kinds are never a completion target. |
| `context_compose` `{kind}` | `context:read` | Getting ready to write: `{kind, title, view, fields, relatedFacts, truncated, note, essentials, stale}`. The kind's field structure plus the facts whose text bears on it, and the department shelf: `essentials` says which of the department's essential kinds exist, and `stale` lists the department's documents past their review cadence or inside its last fifth, worst first, as `{slug, kind, title, state, reviewed_at, review_every_days, owner, updated_at}`. **Read the stale list before citing anything from it.** It returns no readiness score, by design. |

### What the framework client covers

`scripts/context_ledger.py` **prices** all forty-six verbs: `VERB_CAPABILITY`
is a mirror of the server's table, so `capability_for()` names the grant behind
any refusal and `assert_can()` can be asked about any verb before work is
planned. It **wraps** the v1.6 set, `context_search` and the three work-queue
verbs. There is no typed method for `dataset_row_put` or `context_note`; reach
them through the client's tool-call path, and expect the return verbatim as
documented above.

### The complete verb index

Forty-six verbs at minor 1.10. `tools/list` is authoritative; this table is
what it should say.

| Capability | Verbs |
| --- | --- |
| `context:read` | `config_pull`, `document_get`, `document_list`, `document_history`, `context_search`, `context_changes`, `feedback_list`, `branch_list`, `branch_diff`, `merge_list`, `schema_describe`, `canvas_graph`, `canvas_validate`, `portfolio_snapshot`, `dataset_list`, `dataset_describe`, `dataset_query`, `dataset_row_history`, `venture_state`, `venture_handover_preview`, `venture_method`, `venture_brief`, `venture_publish_check`, `context_known`, `context_gaps`, `context_compose`, `work_list` (27) |
| `context:write` | `document_put`, `dataset_create`, `dataset_row_put`, `dataset_row_delete`, `venture_artifact_set`, `venture_artifact_accept`, `venture_artifact_skip`, `venture_define_kind`, `context_note`, `work_claim`, `work_complete` (11) |
| `context:revert` | `document_revert`, `dataset_row_revert` (2) |
| `branch:create` | `branch_create` (1) |
| `branch:merge` | `branch_merge`, `merge_revert`, `venture_sync` (3) |
| `feedback:write` | `feedback_add` (1) |
| `run:append` | `run_append` (1) |

## v1.10 additions (additive)

Three verbs and one optional parameter. Nothing removed, no return shape
changed, every price drawn from the same closed capability list.

### The work queue

An owner writes down what they want done ("Draft the Q4 pricing page from
the offer ladder", filed under marketing) on the company's Work page. Agents
pull from that queue instead of guessing what the company needs next: list,
claim, do the work through the ordinary verbs, complete. The queue lives on
main only; the work itself lands wherever the agent commits it, normally a
branch named in the completion.

| Verb | Capability | Contract |
| --- | --- | --- |
| `work_list` `{status?, view?, limit?}` | `context:read` | `{requests, count}`, each request `{seq, title, brief, view, priority, status, requested_by, claimed_by, created_at, updated_at, due_at, result}`. `status` is `open` (default), `claimed`, `done` or `cancelled`; `view` narrows to one department; `limit` 1 to 100, default 50. A lane-scoped key sees only requests filed in its departments or company-wide (`view` null). Call it before starting work. |
| `work_claim` `{seq}` | `context:write` | Take an open request: `{seq, status: "claimed", claimed_by, claimed_at}`. Refused, with the holder named, when the request is not open ("Work request #7 is claimed by writer"). Lane-checked against the request's `view`. |
| `work_complete` `{seq, summary, documents?, branch?}` | `context:write` | Finish a request this key claimed: `{seq, status: "done", done_at}`. `summary` is what was done, at most 4000 characters; `documents` is `[{slug, branch?}]` for what was touched, at most twenty; `branch` is where the work landed. Only the claiming key may complete; a request claimed by another key is refused with that key named. |

Requests are created, cancelled, released and human-completed on the web
only; there is no verb for an agent to file work for itself.

### Search that reaches quotes and facts

`context_search` gains an optional `include` array. Without it the verb
returns the bare array it always has. With `include` naming `"quotes"`,
`"facts"` or both, it returns an envelope `{documents, quotes?, facts?}`:
`quotes` are the matching rows of evidence-source key-quote tables
`{slug, title, row_id, quote, ...}`, so a claim can be cited at the row it
rests on; `facts` are live fact-ledger claims `{id, topic, claim, source,
source_detail, confidence}`. The envelope only ever appears when asked for,
which keeps the array rule above intact.

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
minor **1.10**. Additive fields are non-breaking; verb or hashing changes
require `v2` and a deliberate, reviewed update to this document.

**`protocol_minor`.** `config_pull` returns the minor as a string beside the
unchanging protocol name:

```json
{ "protocol": "context-ledger.v1", "protocol_minor": "1.10", "...": "…" }
```

That is how a client tells which additive tier answered without probing
`tools/list` verb by verb: whether `document_list` (1.6) exists, or
`dataset_query` and `context_known` (1.9), or `work_list` (1.10). The minor
is a string of two integers, not a decimal: 1.10 follows 1.9 and compares as
`(1, 10) > (1, 9)`, never as `1.10 < 1.9`. It is itself an additive field: a
server that omits it is a ledger of unknown minor, which a client must treat
as *unknown*, never as 1.6. The framework client sends its own minor as
`clientInfo.version` in `initialize`, and the server ignores it: the client
asks for nothing, it reports what it is.

**Why 1.10 and not 2.0.** Everything added since 1.6 is additive: 28 new
verbs, new optional parameters, new fields on existing returns. No verb was
removed, no return shape changed, and the wire `protocol` string is
unchanged. A major would mean a new wire name and a new document, and there
is no `protocol-v2.md` because nothing has earned one.

The additive contract, precisely, because agents in the field depend on it:
no verb is ever removed, no return shape ever changes from an array to an
object (or the reverse, with the two documented `branch_list` / `merge_list`
exceptions above, which shipped as envelopes and never as arrays), and no
parameter that was optional ever becomes required. New capability means a new
verb or a new optional parameter. A v1.5 agent runs unchanged against a v1.10
ledger; it simply never merges, never sees a dataset, and never takes work
from the queue.
