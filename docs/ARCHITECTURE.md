# Architecture

## Authority layers

1. **Canonical core repository** owns controller code, schemas, contracts,
   skills, tests, and releases.
2. **Installed distribution** is a content-addressed copy consumed by Codex.
3. **Project instance** owns only project strategy, evidence, work, metrics,
   adaptations, and runtime state.
4. **Protected launcher and issuer** live outside the managed project and are
   required before recurring execution.

Installed skills and project instances may never silently modify the canonical
core.

## Operator experience

The `brief` command is a read-only projection, never another authority. It
loads the SQLite state when present, runs the same complete audit, and emits a
curated Markdown, JSON, or self-contained HTML command center. The projection exposes the north
star, current outcome, phase track, one deterministic next action, required
quality, active work, manager/runtime counts, evidence health, feedback cost,
and control posture. It omits grants, nonces, private authority material, raw
provider envelopes, and arbitrary state. Untrusted project text is rendered as
inert content. The self-contained HTML view uses semantic native disclosure,
responsive first-viewport decision hierarchy, reduced-motion support, real
evidence and handoff links, and no client script. Every view binds its
comparison to an exact authoritative revision window, so a partial trail is
never represented as total history. `--strict` makes a blocked gate observable
to automation while still printing the full brief.

## Runtime target

The operational system uses one project-bound SQLite control store for
programs, outcomes, work, cycles, leases, attempts, events, inboxes, outboxes,
evidence, decisions, quality, and adaptations. Every accepted controller
mutation appends one immutable state revision and one exactly paired event;
current entity/inbox projections are rebuilt in the same transaction. Stable
command keys provide exact retry semantics. JSON and JSONL are repairable
exports. This is the accepted single-host authority substrate, not a claim of
distributed or multi-region consensus.

One Sol master will own the program. At most two Sol managers own
disjoint outcomes, and at most three GPT-5.6 Luna workers per manager perform
bounded labor. Every child receives a narrower outcome, authority envelope,
budget, scope, and stop condition. Evidence and exceptions reconcile upward.

The interactive Codex host is the target execution surface. It can host tasks
requested for Sol-manager and Luna-worker roles, while Company OS provides
mission lineage, scope, budgets, phase rules, evidence, and reconciliation. App task tools are
not repository-callable APIs. The controller does not yet admit or durably
observe native task creation, so the full runtime remains disabled.

Native source contracts use strict v2 compact assets. A manager charter carries
an offline-verifiable accepted charter record and exact-byte architecture,
roadmap, and interface references. A worker packet references the exact parent
manager charter, its available budget, and inherited accepted-design record,
but never waits on the master; its canonical destination is that manager task.
Child scope, actions, tools, restrictions, and all six budgets must narrow the
parent envelope. Fixture HMAC validation proves deterministic repository
integrity only, not live identity. Authenticated master decisions fence charter,
design, verification, and final integration. Only visible routine execution
subphases inside the unchanged accepted charter may auto-continue.

Task evidence separates current from optional terminal state and orders create,
start, and terminal events. An open active interval consumes concurrency until
terminal evidence arrives. Writer scopes are lowercase ASCII relative POSIX
paths; case, Unicode, path aliases, and ancestor overlap reject.
Manager-manager and worker-worker overlaps are separate fail-closed checks.
Referenced evidence must be a versioned project-namespaced regular file under
an allowed repository root; exact bytes are hashed and unsafe, missing,
mutable, symlinked, foreign, or escaped paths reject without exposing content.

Requested and observed model identity remain separate. Task/thread IDs and host
IDs are coordination metadata; host identity is not lineage. Status and elapsed
duration may be observable even when model, tokens, cost, and cancellation
acknowledgement are unavailable. No absent field is inferred from another.

The provider-neutral lifecycle and fixture-only Responses code is retained as
historical regression machinery. It is not the active Program 6 runtime path.

Evidence bytes are published once under a project-local SHA-256 content
address. Governed records bind that immutable snapshot; the original source
path remains descriptive and may evolve without silently changing accepted
proof. A drifted legacy or expired current record can be replaced only while
the instance is paused and unscheduled, with no lease or running cycle, and
only through an independently signed `supersede-evidence` transition. The full
predecessor, exact reviewed payload, grant, and linear successor relation stay
auditable. Completed-cycle and accepted-fabric evidence cannot be rewritten.

Schema 9 implements the observation trust boundary. Version 0.3 adds the
single-host transactional control substrate without enabling runtime launch.
Legacy JSON instances continue to use the write-ahead pair until an explicit,
validated `migrate-control-store` operation publishes their database. New
instances begin transactionally. Version 0.4 adds the Operator Command Center
and a transaction-safe two-bundle distribution upgrade path; it still does not
enable a provider runtime or recurring scheduling.

## Feedback target

Each accepted cycle records intended outcome, observed result, evidence, time,
tokens, cost, rework, collisions, and visible movement. Repeated failure opens
one reversible adaptation proposal. A different reviewer must accept it. The
meta-loop cannot alter protected authority, create another meta-loop, or
promote a core change without evidence from three isolated projects.

## Client boundary

Client repositories such as Chippy contain only isolated project instances and
client work. Company OS source changes occur here. Client work cannot be used
as proof that the standalone Company OS runtime works.
