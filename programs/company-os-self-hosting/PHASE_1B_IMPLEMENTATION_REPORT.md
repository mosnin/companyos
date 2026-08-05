# Phase 1B Transactional Control — Implementation Report

## Status

Accepted for the version 0.3.0 commit by an independent read-only Sol review
of the fixed source hashes. The reviewer reported no P0, P1, or P2 findings.
Runtime launch, provider lifecycle, scheduling, and Chippy remain disabled.

## Implemented capability

- Project-bound SQLite authority at `.company-os/control.db`.
- Atomic immutable state revision and ordered audit-event pairs.
- Transactional current projections for program, work, cycles, leases,
  attempts, evidence, adaptations, and trusted observation inboxes.
- Durable effect outbox and command-idempotency records.
- Stable mutating CLI command keys with exact retry and digest-conflict rules.
- Single-writer process/file/SQLite locking and fenced lease generations.
- Authoritative cancellation of running cycles before stale worker completion.
- Explicit migration from valid schema-9 JSON state; invalid or corrupt input
  fails closed.
- Deterministic JSON/JSONL exports repaired from committed authority.
- Whole-history hash, binding, pairing, ordering, projection, inbox, outbox,
  and idempotency audit checks.
- Replay acknowledgments are content-hashed and reconstructed against their
  paired immutable audit event; foreign-project rows in any project-scoped
  table fail the store audit.
- Atomic initialization through a private temporary database publication.

## Fault evidence

The dedicated control-store suite covers initialization failure before
publication, legacy migration and repeat, invalid source, corrupt retained
store, one-revision command commit, exact retry, conflicting retry, direct
export tampering, post-commit export failure, historical state tampering,
event reordering, two-process lease contention, cancellation versus stale
completion, project-root copying, projection tampering, restart idempotency,
and outbox retry/terminal rules.

Current local verification:

- 101 controller tests passed.
- 19 transactional-control tests passed.
- 8 runtime-observation integration tests passed.
- 10 preserved observation-contract reference tests passed.
- 4 clean-distribution/bootstrap tests passed.
- Luna Execution Fabric validator self-test passed.
- Distribution manifest verification passed.
- Independent fixed-tree acceptance review passed with no open finding.

## Explicit non-claims

- This is a single-host transactional substrate, not distributed consensus.
- Outbox delivery and provider launch are not enabled.
- No real Sol or GPT-5.6 Luna runtime has been observed.
- The protected scheduler gate remains closed.
- No client repository or Chippy state was changed.
