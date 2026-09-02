---
name: company-context-ledger
description: Connect Claude Code, Claude Cowork, ChatGPT Work, and Grok to one hosted Company OS ledger through a single MCP. Use when pulling or writing shared company context, architecture, documents, harness lanes, or loop records. Do not load as the Company OS master persona or on Luna workers.
---

# Company Context Ledger

This is a thinking overlay for the hosted company-os-web ledger. It does not own authority, leases, fabric, spend, or completion. `$manage-company-program`, `$company-blueprint`, `$mission-execution-control`, `$govern-outcome-execution`, and `$force-first-execution` still win.

company-os-web is Convex storage and display. Open-source Company OS remains the installable operating system. The ledger is shared company context. It is not a control plane.

Do not send this skill to Luna workers. Do not use it as the master persona.

## Wire contract (context-ledger.v1)

The verbs are pinned in [references/protocol-v1.md](references/protocol-v1.md)
and implemented by `scripts/context_ledger.py` (stdlib-only). On the wire the
dotted names use MCP-safe underscores: `config_pull`, `document_get`,
`document_put`, `run_append`. Writes are revision-checked (`base_revision`
must equal the revision read; 0 for new documents). Ledger `contentHash` is
sha256 over the framework's frozen canonical JSON, so
`context_ledger.py materialize` yields files whose file sha256 equals the
ledger hash — record them with `record-evidence` and every grant and audit
cites the exact ledger revision. `push_brief` appends the operator brief's
economics block as a `brief_snapshot` run event for the company overview.

v1.3 adds the change signal: `context_changes {since?, limit?}` is the poll
cursor, and app-registered webhooks push the same events HMAC-signed
(`verify_webhook_signature` checks the raw body before anything is parsed).
`scripts/ledger_runner.py` turns that signal into work orders — cadence,
feedback-threshold, and kind-watch triggers, each order carrying a sealed
`bundle_for` context bundle for `mission_control.bind_context`. The runner
emits invitations, never leases: `$mission-execution-control` remains the
only dispatch boundary.

## Branch, commit, ask to merge (v1.6)

The ledger is version-controlled and the authority is enforced. Writing is
ordinary; merging to main is not.

1. `branch_create` an overlay, then `document_put` into it with `branch`.
   Any write key may do both — this is where agent work belongs.
2. `branch_diff` to see exactly what landing it would change.
3. **Ask an owner or admin to merge.** `branch_merge` needs the
   `branch:merge` capability, which no legacy key and no ordinary member
   holds. A `LedgerCapabilityError` there is the design, not a bug: report
   the branch and its diff to a person instead of retrying.

Ask the key what it holds (`granted_capabilities()`, `can()`) before
planning work you will not be allowed to land.

Mistakes are recoverable and history is never rewritten. `document_revert`
restores an earlier revision, `merge_revert` unwinds a whole merge, and both
commit the old content FORWARD as a new revision — `git revert`, never `git
reset`. Nothing is ever mutated or deleted. `schema_describe` returns the
kind registry, so read the document shapes instead of guessing them.

## Every heartbeat

Before reading or writing the hosted ledger, answer these:

1. Name the harness and department lane. Claude may code while ChatGPT Work runs operations. They share one company.
2. Call `config.pull` before writing. Do not invent architecture the ledger already holds.
3. Write with `document.put` (revision-checked) and `run.append` (append-only).
4. Pause if asked to dispatch, lease, enable the scheduler or runtime, accept an outcome, spend, or mutate CRM/HRIS.

Do not dispatch, spend, or enable the scheduler or runtime from this overlay.

## Forced moves

- One MCP URL for every harness. Never add a second server per product.
- operate.to, marketer.sh, govern.sh, tryscalar.xyz, and glove.so stay `coming_soon` until those products expose OAuth.
- A key carries a scope, a capability set, and optional department lanes.
  Writing costs `context:write`; a lane-bound key is refused outside its lanes.
- Operators sign in with a session. Agents use `cos_` bearer tokens.
- Never assume merge authority. `branch:merge` is granted per key by an owner or admin.
- `$force-first-execution` still wins. A pulled config without a written artifact is not progress.

## Artifacts

Keep these manager-local and compact:

- harness, department lane, and token scope
- config.pull digest
- document kind/key/revision or run loopId

## Source pack

Load only the file needed.

| Need | File |
| --- | --- |
| Boundary | `references/source/01-what-it-is.txt` |
| Connect | `references/source/02-connect-harnesses.txt` |
| Writes | `references/source/03-write-contract.txt` |

Index: `references/source/00-index.txt`. Spawn with `assets/spawn-template.json`.
