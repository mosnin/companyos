# Federated Company Kernel contract

## Purpose

Compile a company objective into durable organizational cells and elastic
execution capacity without turning the entire company into one prompt tree.

## Operating model

The kernel uses four non-sequential operating domains:

1. **Policy and capital:** founder authority, mission, prohibited actions,
   material approvals, portfolio budget.
2. **Coordination and operations:** business-unit control, program ownership,
   interfaces, queues, admission, exception routing.
3. **Execution:** Sol manager partitions and Luna-max workers operating inside
   immutable charters, task scopes, budgets, leases, and artifact contracts.
4. **Learning:** independent evaluation, trace diagnosis, lessons, candidate
   experiments, and delayed promotion.

Capability routing, context retrieval, tools, artifacts, persistence, and
telemetry are shared services. They are not management layers.

## Recursive cell contract

Every company, business unit, program, and manager partition has:

- one bounded outcome;
- explicit inputs, outputs, customers, and decision rights;
- a budget and admission envelope;
- a queue and service-level objective;
- evidence and exception channels;
- cancellation and shutdown semantics.

Organizational recursion is not unlimited agent delegation. Business-unit and
program cells are durable control entities. Executable model delegation remains
program manager to bounded workers unless a separately accepted host proves an
additional level.

## Desired and observed runtime contract

The compiled kernel is desired state. The external host snapshot is observed
state. Reconciliation binds both to one kernel generation, immutable manager
specification, idempotency key, native lifecycle, and monotonic event cursor.
Persist the admission intent before asking the host to create a task. If a
create is claimed but no identity returns, query the host listing with the same
idempotency key; do not relaunch. Stale active attempts retain their slot until
cancellation or terminal evidence settles. Any identity, budget, specification,
cursor, or role conflict blocks the entire plan so unrelated actions cannot
leak through a failed reconciliation.

Requested model and reasoning are intent. Returned role readback is evidence;
it may be confirmed, refuted, or inconclusive. Unattested local snapshots do not
prove model identity, cost, token use, or cancellation acknowledgement and may
not become acceptance evidence.

## Durable intent and command contract

The federated runtime is an extension of the project-local Company OS control
store, not an independent database. One transaction retains the exact kernel,
normalized request, observed snapshot cursor, deterministic plan, paired audit
event, idempotency record, and complete actionable command set. A crash before
commit retains none of them; a crash after commit retains all of them.

An observation cursor may advance but never move backward. Reusing the same
cursor with different snapshot bytes is a conflict. Replaying the exact plan is
idempotent and cannot enqueue another command.

Every command claim has an owner, private token digest, expiry, and monotonically
increasing lease generation. Recovery may reclaim an expired command with a
new generation. A stale owner or generation cannot settle it. Cancellation
clears live claim authority and wins over any later success or retry result.
Pending or leased commands prove neither host acceptance nor completed work.
Backend substitution is forbidden. A SQLite authority cannot consume a kernel
configured for PostgreSQL, and a PostgreSQL authority cannot be inferred from
portable SQL or a schema-only check. Each backend must pass the complete
transaction and recovery contract before activation.

The PostgreSQL adapter uses immutable event, kernel, and plan history;
transactional plan plus command-set ingestion; `FOR UPDATE SKIP LOCKED` command
claims; expiring generation-fenced leases; authoritative cancellation; and a
database audit. It revokes public schema, table, and function authority. A
deployment must grant the minimum required functions to a dedicated runtime
role; using an owner connection as the runtime identity is not accepted
production evidence.

## Throughput contract

Keep volatile knowledge-work queues below the configured utilization ceiling.
Measure accepted output, not launched tasks. Scale admission only when first-
pass acceptance, rework, collisions, recovery, observed model mix, management
overhead, latency, and cost-per-accepted-outcome remain inside the request.

The global target is a capacity ceiling, not an instruction to keep idle agents
running. Cells admit work from demand and preserve wind-down capacity for
cancellation, review, recovery, and integration.

## Authority contract

Managers decide routine reversible work inside their program charter. Escalate
only material scope changes, cross-cell conflicts, consequential external
actions, budget exceptions, repeated quality failures, and recovery failures.
Quality services may reject evidence but may not change scope or execute the
repair. Offline learning may propose changes but cannot promote itself.

## Repository mechanism rule

Every adopted mechanism binds an exact source ID and pin through the Source
Intelligence Registry. Adopt the smallest behavior contract and retain the
source's counterevidence. A mechanism contract grants no license, tool,
runtime, network, credential, scheduler, or production authority.
