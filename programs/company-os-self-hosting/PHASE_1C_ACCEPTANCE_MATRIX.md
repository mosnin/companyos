# Company OS Phase 1C Acceptance Matrix

| Gate | Fault or substitution | Required result |
| --- | --- | --- |
| Snapshot publication | Exact retry; pre-existing conflicting bytes; symlink path | Same content address or atomic rejection; never overwrite |
| Source drift | Descriptive source changes after record | Snapshot-backed evidence remains valid |
| Snapshot integrity | Missing, corrupt, or substituted retained bytes | Audit fails closed |
| Legacy recovery | Mutable legacy artifact hash drifts | Exact signed successor replaces the current slot; predecessor is archived honestly |
| Authorization | Missing, malformed, mismatched, replayed, or self-issued review | No governed mutation |
| Runtime gates | Active instance, schedule, lease, cancellation, or running cycle | Supersession rejects before publication/state mutation |
| Terminal history | Completed-cycle or accepted-fabric reference | Supersession rejects permanently |
| Transition history | Repeated successor; branch, cycle, cross-project/program/bucket link | One linear audited chain or fail closed |
| Command retry | Same command key/payload after restart; changed payload | Same acknowledgment and revision; conflict rejects |
| Recovery relevance | Healthy predecessor plus unrelated validation error | Supersession rejects; named evidence must itself be invalid |
| Quality invalidation | Score cites superseded predecessor | Only dependent score and binding are cleared |
| Phase exit | Missing/below-gate current score | Current phase remains authoritative |
| Thresholds | Critical below 9; noncritical below 8 | Quality and scheduler readiness fail closed |
| Crash window | Snapshot publishes but state transaction rejects | Blob remains an unreferenced, unauthoritative orphan |
| Regression | Controller, store, observation, reference, distribution, compile, validator | All green; runtime and scheduler remain off |

## Non-claims

This matrix certifies local evidence durability and phase-control semantics. It
does not certify provider launch, remote lifecycle, protected scheduling,
distributed consensus, or any client project.
