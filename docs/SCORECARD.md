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
| Test strength | 9.0 | Repository, 101-controller, 8 canonical-integration, 10 reference, validator, and compile gates. |
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
