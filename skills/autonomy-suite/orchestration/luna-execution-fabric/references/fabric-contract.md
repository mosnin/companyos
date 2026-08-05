# Luna Execution Fabric contract

## Control analogy

| Compute concept | Agent fabric |
| --- | --- |
| Kubernetes control plane | Master Sol thread plus durable Program Contract |
| Namespace controller | One isolated Sol manager thread |
| Job or pod | One bounded Luna worker task |
| Container isolation | Worktree or sandbox plus permission envelope |
| Desired state | Outcome, acceptance criteria, budget, and task DAG |
| Observed state | Attributable receipts, artifacts, tests, and usage |
| Reconciliation | Master comparison of reports against desired state |
| Resource quota | Concurrency, token, time, cost, and write-scope limits |
| Readiness probe | Acceptance checks run by manager and reviewer |

Threads alone do not isolate files, tools, credentials, or side effects.

## Runtime modes

Use one authoritative mode: the Sol manager creates an isolated native Codex
task requesting `gpt-5.6-luna`, then coordinates it through bounded waits,
reads, follow-up messages, and list reconciliation. If the manager lacks native
task authority, it asks the master to create the task and returns the resulting
task/thread ID; responsibility remains with the manager.

Record the requested model and observed model separately. A task creation
request proves only the request. Record actual task/thread and host metadata
only when the host exposes them, and never use host identity as lineage. Pause
when Luna cannot be requested; do not silently reroute and mislabel work.

## Elastic program manifest

The JSON below is the controller/`validate_fabric.py` manifest, not a
native v2 prompt payload. Do not copy its embedded descriptive fields into a
manager or worker prompt. Native dispatch uses only the exact compact v2 assets
described after this legacy example.

```json
{
  "program_id": "program-001",
  "topology_mode": "elastic_work_graph",
  "program_version": 1,
  "outcome": "User-visible accepted outcome",
  "acceptance": ["Executable evidence"],
  "program_contract": {
    "north_star": "Category-level direction",
    "user_value": "Concrete user or business value",
    "rationale": "Why this outcome now",
    "architecture": "Accepted system direction",
    "roadmap": [
      "charter",
      "discovery",
      "design",
      "execution",
      "verification",
      "integration"
    ],
    "dependencies": ["External or internal dependency"],
    "non_goals": ["Explicit exclusion"],
    "constraints": ["Safety, product, time, or cost constraint"]
  },
  "max_managers": 2,
  "max_manager_concurrency": 2,
  "max_workers_per_manager": 3,
  "max_total_workers": 6,
  "max_depth": 2,
  "max_worker_retries": 1,
  "max_manager_rework_rounds": 2,
  "budget": {"time_minutes": 60, "token_limit": 10000, "cost_usd": 10.0, "max_concurrency": 6, "max_retries": 1},
  "luna_token_share_target": 0.75,
  "external_effects_allowed": false,
  "managers": [
    {
      "id": "manager-a",
      "model": "gpt-5.6-sol",
      "outcome": "Bounded outcome",
      "acceptance": ["Manager-owned verification"],
      "phase_ids": [
        "charter",
        "discovery",
        "design",
        "execution",
        "verification",
        "integration"
      ],
      "budget": {"time_minutes": 30, "token_limit": 5000, "cost_usd": 5.0, "max_concurrency": 3, "max_retries": 1},
      "write_scope": ["path/or/resource-prefix"],
      "workers": [
        {
          "id": "worker-a1",
          "model": "gpt-5.6-luna",
          "task": "One bounded unit of labor",
          "acceptance": ["Exact evidence"],
          "write_scope": [],
          "risk": "low",
          "budget": {"time_minutes": 15, "token_limit": 2500, "cost_usd": 2.5, "max_concurrency": 1, "max_retries": 1},
          "outcome_context": {
            "program_version": 1,
            "north_star": "Category-level direction",
            "user_value": "Concrete user or business value",
            "program_outcome": "User-visible accepted outcome",
            "manager_outcome": "Bounded outcome",
            "roadmap_position": "execution",
            "dependencies": ["Required interface"],
            "non_goals": ["Explicit exclusion"],
            "constraints": ["Bounded authority"]
          },
          "stop_condition": "Evidence produced or blocker identified"
        }
      ]
    }
  ]
}
```

## Native v2 compact contracts

`company-os.mission-charter.v2` and `company-os.work-packet.v2` are the only
native role inputs. Their exact source assets carry role-contract,
program/definition versions; IDs; outcome and SHA-256; requested model;
attributable charter or inherited-design authorization with definition,
parent-definition, decision, decider, exact phase-evidence bytes, canonical
record digest, and repository-fixture HMAC bindings; versioned project-local
SHA-256-bound architecture, roadmap, and interface artifact references;
task-local paths; canonical scope; allowed actions/tools and prohibitions;
dependencies and deliverables; oracle/checks and review requirements; barrier
policy; token/cost/time/task/concurrency/retry caps; stop/escalation; and one
reporting destination. They never carry a transcript or global context.
The fixture HMAC is an offline integrity oracle with a public test key; it is
not live identity authentication for a user or host.

## Authority

- The master owns program version, manager admission, cross-manager conflicts,
  program budget, and final acceptance.
- A manager owns task decomposition and acceptance only within its allocated
  outcome and write scope.
- A Luna worker owns no authority-bearing state. It proposes artifacts and
  evidence.
- Managers may not change the program outcome, add a manager, widen external
  access, or raise their own budgets.
- Workers may not spawn, merge, deploy, publish, message customers, alter
  permissions, or approve work.

## Fractal envelope and budgets

Every executable manifest repeats the six-part Company OS contract: outcome,
envelope, budget, execution, evidence, and reconciliation. The program owns a
budget object (`time_minutes`, `token_limit`, `cost_usd`, `max_concurrency`,
`max_retries`); each manager budget may only narrow it; each worker budget may
only narrow its manager. Scope follows the same rule. Canonical scopes are
lowercase ASCII, project-relative POSIX paths: no absolute paths, backslashes,
empty, `.` or `..` segments, control characters, Unicode, or leading/trailing
separators. Reject rather than normalize case or Unicode so two spellings
cannot alias. Writer scopes overlap when equal or when either is an ancestor of
the other. Manager scopes are mutually disjoint; worker scopes are canonical
descendants of their manager envelope and mutually disjoint.
No child may widen authority, retries, concurrency, cost, time, tokens, or
write scope. Evidence and exceptions move upward. The executable depth remains
master → manager → worker. Each worker has concurrency one, and sibling time,
token, and cost allocations must fit within their manager; manager allocations
must fit within the program envelope. Declared child capacity may exceed active
concurrency because the scheduler can queue dependency-blocked work.

Topology is derived from the accepted work graph rather than a fixed ratio.
Create a manager for each independently accountable outcome or interface
boundary, then create Luna tasks from that manager's dependency DAG. Keep
`max_manager_concurrency` at or below `max_managers`. The program worker-
concurrency budget may be lower than total workers, and a manager's worker-
concurrency budget may be lower than its worker count. This is expected:
capacity describes the organization; concurrency describes the active window.
Before worker dispatch, resolve the exact accepted parent manager charter and
design record. Require matching project/program/cycle/parent identity and
parent definition digest; make actions/tools subsets, retain every parent
prohibition, contain child scope, and compare every child budget field against
both the signed parent-available allocation and parent charter. Reject stale
parent digests and cross-manager replay.

Artifact paths must be lowercase ASCII, versioned, project-namespaced, and
beneath an allowed repository root. Reject absolute paths, backslashes, dot or
parent segments, escapes, symlinks, missing files, mutable names, and digest
mismatch after hashing exact bytes. Manager-manager and worker-worker writer
scopes reject equality or ancestor/descendant overlap.

## Manager Charter

The master sends every manager:

- charter, program, and definition versions plus immutable outcome digest;
- attributable authenticated charter authorization bound to definition and
  evidence digests;
- north star, user/customer value, rationale, and complete outcome;
- accepted architecture and full roadmap;
- the manager's outcome, phases, dependencies, interfaces, and ownership;
- acceptance rubric and required independent review;
- allowed and prohibited tools/actions;
- token, cost, time, concurrency, and rework budgets;
- reporting barriers, stop conditions, and escalation route.

The manager acknowledges the exact version and digest before dispatch. Any
master change increments the version and invalidates stale worker contracts.

## Manager phase report

```json
{
  "message_type": "manager_phase_report",
  "program_id": "program-001",
  "program_version": 1,
  "manager_id": "manager-a",
  "phase": "design",
  "status": "ready_for_authenticated_decision",
  "outcome_state": "on_track",
  "artifacts": ["immutable reference"],
  "evidence": ["check and result"],
  "plan_variance": [],
  "dependencies": [],
  "risks": [],
  "usage": {
    "luna_tokens": 0,
    "terra_tokens": 0,
    "manager_sol_tokens": 0,
    "reviewer_sol_tokens": 0,
    "elapsed_minutes": 0
  },
  "worker_metrics": {
    "accepted_first_pass": 0,
    "reworked": 0,
    "failed": 0,
    "collisions": 0
  },
  "continuation": "await_authenticated_master_decision",
  "decision_binding": {
    "definition_version": 1,
    "outcome_digest": "sha256",
    "phase_report_digest": "sha256"
  },
  "next_plan": ["bounded next action"]
}
```

Every phase and routine execution subphase is visible to the master. Charter,
design, verification, and final integration require an authenticated master
decision bound to the current program/definition versions, outcome digest, and
phase report. Silence never grants a barrier; the manager escalates when its
time-budgeted wait expires. Only routine execution subphases after accepted
design and before verification may auto-continue, and only when the accepted
charter is unchanged, every check passes, budgets/concurrency/authority remain
valid, and no cancellation, model, evidence, collision, scope, or other
exception exists. The master may override every routine continuation.

## Isolation

- Give each write-capable manager a separate worktree or mutually exclusive
  path/resource lease.
- Allow read-only workers to share a checkout.
- Give a write-enabled Luna worker a disjoint ownership scope. Serialize
  workers that need the same scope.
- Merge through the manager after validation; integrate managers through the
  master after conflict and acceptance review.

## Token-efficiency rules

1. Send the complete decision contract without the full transcript.
2. Share immutable references by path or commit rather than repeating them.
3. Limit worker reports to evidence and decisions; omit narration.
4. Batch deterministic operations sharing one scope and acceptance test.
5. Stop accepted branches immediately.
6. Cache stable system and repository prefixes when supported.
7. Track input, cached input, and output tokens separately by role only when the
   host exposes them. Otherwise record each as unavailable.

Parallelism succeeds only when accepted lead time or cost improves.

## Execution-efficiency evidence

Every real program integration includes one canonical
`company-os.execution-efficiency-receipt.v1`. The receipt is operating evidence,
not authority. It must bind:

- program and comparison-class identity;
- mandatory requirements, their source, and independent satisfaction results;
- requested lanes and actual manager-to-lane ownership;
- actual worker tasks, requested and observed model/effort, and manager binding;
- maximum observed concurrency, configured limit, and every consolidation or
  host-cap variance;
- program start, first manager dispatch, first worker dispatch, first usable
  result, first artifact, and final acceptance, with unavailable and
  not-applicable fields explicit;
- role-level total, Luna, and Sol tokens, cost, single-thread Sol-token and
  lead-time baselines when exposed;
- required/accepted artifact counts, first-pass decision, rework, collisions,
  duplicates, and independent-review truth;
- one semantic artifact plan and readback per result: kind, title, external ID,
  owner lane, requirement IDs, required and applied capability IDs, readback,
  and acceptance;
- actual and required acceptance-authority levels.

The Company Scorecard verifier returns separate gates. `delivery_accepted`
means every mandatory requirement and required capability passed under the
required acceptance authority. `hierarchy_materialized` means every requested
lane has exactly one actual owner. `luna_execution_proven` requires an observed
Luna/max worker, not a requested model. `efficiency_proven` additionally
requires complete timing/usage and baseline comparison. A single receipt can
never prove scale. Three comparable accepted receipts must satisfy the scaling
policy as a group.

## Acceptance sampling

- Critical/high risk: manager, independent Sol reviewer, and master verify 100%.
- Medium risk: manager verifies 100%; master verifies the integrated result and
  one underlying artifact.
- Low risk: manager verifies 100%; master samples one result per manager and
  reviews aggregate failure and rework metrics.

The reviewer does not receive the manager's desired verdict.

## Scaling policy

Start with two managers and six Luna workers globally. Scale one dimension at a
time after three comparable accepted cycles satisfy:

- first-pass worker acceptance at least 85%;
- total rework below 20%;
- zero write collisions or duplicate side effects;
- at least 40% lower Sol-token use per accepted outcome;
- no regression in acceptance quality or lead time.

Scale down immediately when any invariant fails.
