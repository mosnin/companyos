# Loop selection contract

## Request

`company-os.loop-selection-request.v1` requires:

- `outcome_id`: stable lower-case identifier.
- `task_family`: `general`, `software_delivery`, `product_delivery`,
  `research`, `optimization`, `creative_exploration`, or `operations`.
- `evidence`: booleans for an acceptance oracle, objective metric, production
  traces, and durable event source.
- `shape`: parallel lane count, uncertainty, recurrence, failure cost, novelty
  need, and whether code is mutated.
- `limits`: finite maximum passes, consecutive no-progress limit, active
  concurrency, recursion depth, and observable cost budget or `null`.
- `requirements`: independent review, worktree isolation, post-run learning,
  and named approval boundaries.

Unknown keys fail closed. A request without an acceptance oracle cannot select
an execution loop because it cannot distinguish progress from activity.

## Plan

`company-os.loop-plan.v1` contains:

- the request SHA-256;
- one primary strategy and zero to three adapters;
- deterministic selection scores and reasons;
- the exact limits copied from the request;
- required controls, metrics, and terminal states;
- `activation_state: planned`;
- a catalog revision and selected-source provenance.

The plan is canonical JSON. Its SHA-256 is the manager/worker binding. Selection
never activates a scheduler, tool, integration, or external runtime. Recurring
work always carries scheduler admission, frequency guard, lease/heartbeat, and
missed-run reconciliation, even when another primary scores higher.

## Runtime receipt

A conforming execution receipt must bind the plan digest and record each pass:
fresh observation, chosen action, effect, verification, measured delta,
cumulative budget, and terminal decision. For recursive work it also records
parent, child, branch/worktree, owned paths, and integration decision. For
event-driven work it records stream or event identity, cursor, claim generation,
lease, acknowledgement, and replay outcome without embedding credentials.

