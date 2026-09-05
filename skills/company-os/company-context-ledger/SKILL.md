---
name: company-context-ledger
description: Connect Claude Code, Claude Cowork, ChatGPT Work, and Grok to one hosted Company OS ledger through a single MCP. Use when pulling or writing shared company context, architecture, documents, harness lanes, or loop records. Do not load as the Company OS master persona or on Luna workers.
---

# Company Context Ledger

This is a thinking overlay for the hosted company-os-web ledger. It does not own authority, leases, fabric, spend, or completion. `$manage-company-program`, `$company-blueprint`, `$mission-execution-control`, `$govern-outcome-execution`, and `$force-first-execution` still win.

company-os-web is Convex storage and display. Open-source Company OS remains the installable operating system. The ledger is shared company context. It is not a control plane.

Before Business OS advice, call `business_context_packet(decision)`. It indexes
all active documents and seals relevant bodies, facts, gaps, and portfolio
state. Use `full=True` only when needed. Send the packet, never the credential;
Business OS cannot fetch, dispatch, or write.

Do not send this skill to Luna workers. Do not use it as the master persona.

## Wire contract (context-ledger.v1)

Verbs are pinned in [references/protocol-v1.md](references/protocol-v1.md) and
implemented by the stdlib-only `scripts/context_ledger.py`. Wire names use
underscores: `config_pull`, `document_get`, `document_put`, `run_append`.
Writes are revision-checked. `contentHash` is canonical JSON sha256, so
`materialize` produces exact evidence bytes. Change signals create invitations,
never leases.

## Branch, commit, ask to merge (v1.6)

Agents may `branch_create`, `document_put`, and `branch_diff`. Ask an owner or
admin to land changes: `branch_merge` requires `branch:merge`; report
`LedgerCapabilityError` instead of retrying. Check `granted_capabilities()`
before planning. Reverts commit forward; history is never rewritten. Read
shapes from `schema_describe`.

## Every heartbeat

Before reading or writing the hosted ledger, answer these:

1. Name the harness and department lane. Claude may code while ChatGPT Work runs operations. They share one company.
2. Call `config.pull` before writing. Do not invent architecture the ledger already holds.
3. Before Business OS advice, create a sealed business-context packet and bind
   its `packet_sha256` to the manager assignment.
4. Write with `document.put` (revision-checked) and `run.append` (append-only).
5. Pause if asked to dispatch, lease, enable the scheduler or runtime, accept an outcome, spend, or mutate CRM/HRIS.

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

## Founding (v1.11)

An agent founds a company in conversation. Read `playbook_get("founding-interview")`
first, write only to a `founding/<date>` branch, research with `research_search`
and `research_scrape`, record facts with `context_note`, then `proposal_review`,
show the brief, ask, and `proposal_commit` with the person's name only after an
explicit yes.
