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

## Runtime target

The operational system will use transactional state for programs, outcomes,
work, cycles, leases, attempts, events, receipts, evidence, decisions, quality,
and adaptations. One Sol master owns the program. At most two Sol managers own
disjoint outcomes, and at most three GPT-5.6 Luna workers per manager perform
bounded labor. Every child receives a narrower outcome, authority envelope,
budget, scope, and stop condition. Evidence and exceptions reconcile upward.

Requested and provider-observed model identity remain separate. Provider
launch, observation, heartbeats, terminal receipts, cancellation, telemetry,
and reconciliation must be attributable and idempotent before a result can be
accepted.

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
