# Company OS Scorecard

Scores are evidence-bound. Future-phase dimensions are not rounded up to make
the current stage appear operational.

## Phase 0 applicable dimensions

| Dimension | Score | Evidence |
| --- | ---: | --- |
| Canonical source ownership | 9.0 | Dedicated Git repository; installed skills are distributions. |
| Project/client separation | 9.0 | Company OS source is outside Chippy and client work is frozen. |
| Distribution integrity | 9.0 | Content-addressed manifest and exact installed-source comparison. |
| Reproducible bootstrap | 9.0 | Clean temporary project initialization and fail-closed audit test. |
| Change safety | 9.0 | Existing changed installs reject by default; staged replacement rolls back; state/event pairs recover from a partial replace. |
| Test strength | 9.0 | Repository, 112-controller, 8 canonical-integration, 10 reference, validator, and compile gates. |
| Evidence truthfulness | 9.0 | Reference, canonical, mock, runtime, and client evidence remain distinct. |
| Documentation and handoff | 8.5 | Architecture, roadmap, program contracts, and append-only ledger are colocated. |

Phase 0 passes its applicable 8/10 gate.

## Phase 1B transactional-control dimensions

These scores apply only to the accepted single-host control substrate in
version 0.3.0. They do not certify provider execution or distributed control.

| Dimension | Score | Evidence |
| --- | ---: | --- |
| Transactional authority | 9.0 | One SQLite transaction binds each accepted state revision, audit event, current projections, and command records. |
| Project isolation | 9.0 | Root and project bindings fail closed; foreign-project records in every project-scoped table fail audit. |
| Durability and recovery | 9.0 | Full synchronous SQLite, WAL, atomic database publication, parent-directory fsync, retained-history hashes, and deterministic export recovery. |
| Cancellation authority | 9.0 | Cancellation revokes the lease, terminates running cycles, and cannot be superseded by stale completion. |
| Evidence integrity | 9.0 | State/event pairing, ordering, hashes, command identity, replay result, projections, inboxes, outboxes, and exports are audited. |
| Idempotency and effect intent | 9.0 | Stable command and outbox keys distinguish exact retry from payload conflict across process restart. |
| Concurrency control | 9.0 | Project file lock plus SQLite immediate transactions admit one of two concurrent lease claimants. |
| Migration safety | 9.0 | Missing, corrupt, stale, cross-project, and corrupt-retained sources reject; healthy repeat is revision-free. |
| Operator clarity | 8.5 | Backend, revision, export parity, pending outbox work, migration, and explicit non-claims are documented and inspectable. |
| Regression strength | 9.0 | 101 controller, 19 transactional, 8 integration, 10 frozen reference, and 4 distribution tests plus compile and validator gates. |

Phase 1B passes its applicable gate. Authority, durability, cancellation,
isolation, and evidence integrity meet the required 9/10 threshold.

## Phase 1C evidence-integrity dimensions

These scores cover the locally verified evidence and phase-control slice only.
They do not certify a provider runtime or unattended operation.

| Dimension | Score | Evidence |
| --- | ---: | --- |
| Evidence immutability | 9.0 | SHA-256-addressed snapshots use create-if-absent publication and every audit rehashes retained bytes. |
| Recovery authority | 9.0 | A distinct external reviewer signs the exact predecessor, successor bytes, bindings, metadata, and reason. |
| History integrity | 9.0 | Full predecessor records and grants remain audit-valid in a linear, cycle-free chain across repeated replacements. |
| Fail-closed safety | 9.0 | Active scheduling, leases, cancellation, running cycles, completed-cycle references, accepted-fabric references, missing snapshots, and corrupt snapshots reject. |
| Quality freshness | 9.0 | Scores citing replaced proof are cleared; critical dimensions require 9 and applicable noncritical dimensions require 8. |
| Phase integrity | 9.0 | Active work cannot leave its current phase until current applicable quality passes; target-phase scores are reset. |
| Crash semantics | 9.0 | A pre-transaction snapshot can remain only as an unreferenced orphan and never becomes governed evidence. |
| Regression strength | 9.0 | 112 controller, 20 transactional, 8 observation-integration, 10 frozen-reference, and 4 distribution tests plus compile, manifest, and validator gates. |

Phase 1C passes only after independent review, the canonical manifest, exact
installed distribution, and self-host evidence repair are all verified.

## Operational dimensions — not passed

| Dimension | Current evidence state |
| --- | --- |
| Durable distributed control | Single-host transactional authority accepted; distributed or multi-region control is not implemented |
| Runtime execution | Not implemented |
| Sol manager orchestration | Not observed |
| GPT-5.6 Luna labor | Not observed |
| Provider identity and telemetry | Signed observation ingestion is locally verified; no real provider observation or telemetry |
| Cancellation and recovery | Contract only; no real runtime evidence |
| Recursive adaptation | Not exercised |
| Protected scheduling | Disabled |
| Cross-project promotion | No qualifying project evidence |

Company OS must not be called operational until these dimensions become
applicable, independently evidenced, and score at least 8/10. Security,
authority, durability, cancellation, and evidence integrity require 9/10.
