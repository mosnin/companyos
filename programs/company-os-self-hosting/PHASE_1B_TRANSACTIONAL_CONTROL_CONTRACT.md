# Company OS Phase 1B — Transactional Control Contract

## Outcome

Company OS uses a project-local transactional database as authoritative state.
The JSON control file and JSONL event log become recoverable exports, never the
source of truth. A process crash, stale export, duplicate command, or concurrent
claim must not split state from evidence or create two owners.

## Scope

This phase implements a single-host SQLite control store behind the existing
controller interface. It is a durability and isolation substrate, not runtime
permission.

Included:

- one database per project under `.company-os/control.db`;
- WAL mode, full synchronous durability, foreign keys, and bounded lock waits;
- immutable state revisions paired one-to-one with ordered audit events;
- transactional projections for programs, work, cycles, leases, runtime
  attempts, trusted observations, evidence, and adaptations;
- durable inbox and outbox tables with unique message keys and explicit state;
- command idempotency records with exact payload digests and stored results;
- migration from a valid schema-9 JSON instance;
- derived JSON/JSONL exports rebuilt from committed database truth;
- audit reporting for backend, revision, export drift, and pending outbox work.

Excluded:

- networked or multi-region databases;
- provider launch or lifecycle advancement;
- automatic outbox delivery;
- scheduler activation;
- Chippy or customer state;
- production deployment.

## Invariants

1. Project ID is stored in every authoritative table and checked on every read.
2. One transaction commits the next state revision, its audit event, all
   projections, inbox entries, idempotency records, and outbox entries.
3. Revision numbers increase by exactly one; each event references exactly one
   revision and each revision exactly one event.
4. A command key plus the same digest returns the recorded result without a new
   revision. The same key plus a different digest is a conflict.
5. A lease has one owner, generation, program version, expiry, and allowed
   transition set. Cancellation remains authoritative over completion/retry.
6. Export failure cannot roll back committed authority. The next controller
   open rebuilds exports from database truth.
7. A project cannot open a database whose stored project ID or root binding
   differs from the current instance.
8. Direct edits to JSON exports never mutate authoritative state.
9. No private key, provider credential, customer content, or signing material
   enters the database fixtures or repository.
10. The existing runtime and scheduling feature gates remain off.

## Exit gate

Accept only when migration, atomic success, rejection, duplicate replay,
digest conflict, export drift recovery, concurrent lease claim, cancellation,
restart, and cross-project isolation tests pass together with every existing
controller, observation, distribution, and validator test.
