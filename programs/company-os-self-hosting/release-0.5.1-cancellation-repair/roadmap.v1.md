# Company OS 0.5.1 Cancellation Repair Roadmap v1

## Charter and design gate

1. Validate the authenticated manager charter, exact candidate/tree, rejected
   review task dependency, references, permissions, budgets, and writer scopes.
2. Inspect current source and tests and return a design report mapping the
   complete 3×2 cancellation matrix through transition, persistence, store,
   controller, replay, audit, and reconciliation behavior.
3. Stop for an authenticated master design decision. Do not create Luna tasks
   before that decision.

## Bounded implementation

4. After design approval only, issue at most two disjoint compact v2 Luna work
   packets using global `$execute-bounded-task`, requested model
   `gpt-5.6-luna`, one task per worker, no child delegation, and narrower
   budgets, scopes, and permissions.
5. Implement the legal-pair validator and truthful derived cancellation states.
   Reject illegal input before mutation and audit-fail contradictory retained
   or replayed histories.
6. Add table-driven adversarial coverage for all six pairings at direct, store,
   controller, and replay layers, plus preservation regressions for dominance,
   non-invention, authority binding, downgrade rejection, and ambiguous-restart
   no-relaunch.
7. The manager inspects every worker diff and result, integrates only accepted
   lowercase paths, runs focused and full discovered suites, and refreshes the
   distribution manifest exactly once after implementation bytes settle.

## Verification and integration gates

8. Report exact artifacts, commits, test counts, residue, expected stale signed
   surface, scores, and findings at the authenticated verification barrier.
9. Require zero P0/P1; cancellation, evidence integrity, authority, durability,
   and security each at least 9.0; every other applicable dimension above 8.0;
   focused adversarial and all non-signature discovered suites green; and an
   exact distribution manifest.
10. Stop for master-owned corrections to `README.md` and
    `programs/company-os-self-hosting/LEDGER.md`. These are required integration
    prerequisites, not manager or Luna deliverables.
11. Require fresh external surface signing and independent Sol review. Full
    discovered suites must be green after the signature. Do not sign or install.
12. Require an authenticated master integration decision before release
    acceptance. Installation and runtime/scheduler activation remain separate,
    prohibited, and unapproved.
