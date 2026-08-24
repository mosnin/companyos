---
name: company-context-ledger
description: Connect Claude Code, Claude Cowork, ChatGPT Work, and Grok to one hosted Company OS ledger through a single MCP. Use when pulling or writing shared company context, architecture, documents, harness lanes, or loop records. Do not load as the Company OS master persona or on Luna workers.
---

# Company Context Ledger

This is a thinking overlay for the hosted company-os-web ledger. It does not own authority, leases, fabric, spend, or completion. `$manage-company-program`, `$company-blueprint`, `$mission-execution-control`, `$govern-outcome-execution`, and `$force-first-execution` still win.

company-os-web is Convex storage and display. Open-source Company OS remains the installable operating system. The ledger is shared company context. It is not a control plane.

Do not send this skill to Luna workers. Do not use it as the master persona.

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
- Shared kinds need a writeShared token. Department kinds stay in the bound lane.
- Operators sign in with a session. Agents use `cos_` bearer tokens.
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
