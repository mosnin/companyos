# Improvement Plane v2 contract

The compiler accepts `company-os.improvement-request.v2` and emits
`company-os.improvement-program.v2`. Every input object is closed: unknown
fields, registry paths, registry digests, evaluator truth, capability truth,
partition members, exposure/burn state, and observed telemetry are rejected.

The request contains only program identity, bounded intent, a baseline and
target identifier, source IDs, capability IDs, requested artifact/stage IDs,
and finite budgets. Source, mechanism, capability-review, catalog, and
evaluator-method registries are resolved from pinned checked-in files. The
portable mechanism registry proves all 81 source records map exactly once to
8 destination planes and 11 source groups, with explicit adopted/rejected
mechanism decisions.

Compilation always creates exactly three immutable differentiated candidates:
`conservative`, `adjacent`, and `first_principles`. It derives four
member-level partitions (`discovery`, `adaptive_validation`,
`sealed_challenge`, and `production_shadow`), a disjoint exposure/burn ledger,
a dependency DAG with one owner per resource, finite retry/cancel/dead-letter
contracts, independent decision receipts, one promotion authority, and an
atomic rollback contract.

The compiler is feature-off and read-only apart from an explicit `--output`
target. It never schedules, executes, imports a provider/runtime, installs a
capability, mutates a database, or promotes a candidate. The current
production-like registries contain zero ready evaluator adapters and twelve
capabilities awaiting independent acceptance, so every valid compile is
`activation_state: planned`, `executable: false`, and `execution_status:
blocked` with named blockers. Missing, stale, tampered, overlapping, exposed,
burned, or otherwise invalid evidence fails closed; evaluator failure is never
converted to a numeric score.

The ordered lifecycle is:

`observed -> reproduced -> proposed -> compiled -> sandbox_admitted -> validation_qualified -> challenge_qualified -> manager_accepted -> shadowed -> promoted -> monitored`

Terminal states are `rejected`, `invalid_evidence`, `inconclusive`,
`cancelled`, `superseded`, `revoked`, `rolled_back`, and `dead_letter`.
