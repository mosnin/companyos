---
name: luna-execution-fabric
description: Orchestrate a hierarchical, cost-aware agent organization in which a GPT-5.6 Sol master supervises isolated GPT-5.6 Sol manager threads and bounded GPT-5.6 Luna worker teams. Use when a user asks for manager threads, Luna-heavy execution, parallel low-cost labor, Kubernetes-like agent orchestration, hierarchical delegation, or lower-cost multi-agent delivery with independent review.
---

# Luna Execution Fabric

Use a three-level control hierarchy to move implementation tokens away from the
master context without weakening ownership or acceptance.

Treat the hierarchy as a bounded fractal control pattern. The master, each
manager, and each worker receive the same six-part contract—outcome, envelope,
budget, execution, evidence, and reconciliation—at a progressively narrower
scale. Authority and resources flow down by delegation; evidence, exceptions,
and accepted results flow up by reconciliation. Never add another executable
level merely because the pattern is recursive.

## Roles

- **Master / CEO — GPT-5.6 Sol:** define the Program Contract, allocate
  manager outcomes and budgets, resolve conflicts, audit every phase, and
  accept the integrated program.
- **Manager / orchestrator — GPT-5.6 Sol:** own exactly one bounded outcome,
  create a worker roadmap, supervise execution, inspect artifacts, report at
  every phase, and return one compressed manager receipt.
- **Worker — GPT-5.6 Luna:** perform one bounded task and return evidence.
  Workers cannot delegate, approve themselves, deploy, change authority, or
  expand scope.
- **Independent reviewer — GPT-5.6 Sol:** challenge a manager's design or
  acceptance evidence at a high-risk phase boundary. It stays read-only.
- **Exception lane — GPT-5.6 Terra:** use only when a Luna task fails twice
  because the implementation itself needs more reasoning.

Treat a thread as a controller identity, not a container. Isolate mutable work
with worktrees, sandboxes, file ownership, permission envelopes, and leases.

## Start the fabric

1. Start from the original objective and compile its outcome control plane. Resolve blocking unknowns with cited evidence, define observable artifact classes, compile executable independent evaluators, bind benchmark tiers, and calibrate the evaluators. Create one versioned Program Contract only after those controls can measure the intended outcome.
2. Derive manager outcomes from the accepted work graph. Use one manager for
   each independently accountable outcome or interface boundary; never combine
   unrelated departments merely to fit a fixed agent count.
3. Spawn a separate Sol manager thread for each outcome. Send its Manager
   Charter and establish master ↔ manager communication before work.
4. Require each manager to acknowledge the program ID, version, outcome digest,
   owned phases, interfaces, and limits.
5. Have each manager create a DAG of Luna-sized tasks and submit it to the
   master at the design barrier.
6. Validate the dispatch manifest:

   `python3 scripts/validate_fabric.py path/to/manifest.json`

7. When an Elastic Company OS instance exists, queue the governed primary work
   with `--execution-mode luna_fabric`, then bind the validated manifest through
   `configure-fabric`. A new `elastic_work_graph` manifest requires `outcome_control`. A pilot is capped at 2 managers, 3 workers per manager, and 6 total workers. Production scale requires a content-bound authorized scale receipt. Record every visible phase; use `decide-fabric-phase`
   only for the authenticated charter, design, verification, and final
   integration barriers. The current controller has not implemented native v2
   routine-subphase admission, so the broader runtime remains blocked.
8. Dispatch only unblocked tasks. Prefer parallel reads; allow one active writer
   for a resource or file-ownership scope.
9. Require managers to inspect evidence and the integrated result, not merely
   summarize worker claims.
10. Return phase reports and manager receipts to the master. The master accepts,
   requests bounded rework, escalates, pauses, or stops.

Read [references/fabric-contract.md](references/fabric-contract.md) before
launching manager threads or changing the default limits.

## Runtime adapter

The execution surface is the native Codex task runtime operated from the
interactive host: master Sol task → Sol manager task → Luna worker tasks. Read
[references/codex-native-task-fabric.md](references/codex-native-task-fabric.md)
before dispatch or acceptance.

Invoke `$manage-company-program` for each manager and `$execute-bounded-task`
for each worker. Send only their compact versioned charter or work packet.
Native task tools are host capabilities, not repository-callable APIs.

For an Elastic Company OS instance, controller admission remains feature-off
and is not yet integrated with native task creation. A manually created task
may supply simulation evidence, but it is not a governed controller launch.
Keep scheduling and the broader autonomous runtime NO-GO until controller
admission, cancellation authority, and durable reconciliation are accepted.

Record requested model separately from observed model. Record thread/task and
host metadata only when exposed. Treat tokens, cost, and cancellation
acknowledgement as unavailable when absent; elapsed duration may be observed
independently. Never substitute Terra or Sol while labeling labor Luna.

## Live topology and efficiency gate

Do not report that the hierarchy exists merely because dispatch was requested.
Read the actual task surface and bind every observed manager and worker ID to one
declared lane. Record requested lanes, unique managers, workers, maximum observed
concurrency, consolidated lanes, and host-cap variance. When the task surface
cannot be read after one bounded retry, mark topology and scale unproven; do not
create a replacement hierarchy while the original may still be running.

Before accepting external pages or other mutable artifacts, refetch them and
bind semantic kind, title, external ID, and owner lane. Never update or accept by
call order alone. A title/ID/owner mismatch is rework even when the content is
otherwise correct.

Reconcile every mandatory requirement and every artifact's required capability
assignment before acceptance. Managers may recommend an alternative, but a
mandatory requirement changes only through an explicit user/master change
decision at the required authority. Missing domain skills or artifact-production
skills are not a stylistic issue; they are an execution-contract failure.

Write and validate one `company-os.execution-efficiency-receipt.v1` at final
integration. A manager may choose not to dispatch a worker when doing so would
duplicate completed work, but must record zero workers and cannot claim Luna,
efficiency, or scaling proof. Requested Luna/max is intent until observed.

## Elastic capacity and limits

- The program declares capacity from its accepted work graph. Manager count,
  workers per manager, and total workers are not fixed defaults. A large
  program may validly declare 30 Sol managers with 10 Luna tasks each.
- New manifests declare `topology_mode: elastic_work_graph` and carry an exact portable outcome control binding. Manifests without it retain the frozen 2/3/6 Phase 1 limits solely for replay compatibility and cannot establish elastic scale evidence.
- The pilot lane may use no more than 2 managers, 3 workers per manager, and 6 total workers. Any larger organization is production scale and requires current outcome authorization before configuration.
- Capacity is not concurrency. `max_managers`, `max_workers_per_manager`, and
  `max_total_workers` describe the admitted organization; optional
  `max_manager_concurrency` and `budget.max_concurrency` bound how many manager
  controllers and Luna tasks may be active at once. Queued work does not consume
  an active slot.
- Start a new program at the smallest concurrency that can expose real
  dependency and integration behavior, then increase active slots from observed
  acceptance, collision, recovery, latency, and budget evidence. Do not reduce
  the declared organization by cramming unrelated outcomes into fewer managers.
- The validator retains high control-plane safety ceilings (256 managers, 64
  workers per manager, 4,096 total workers) to reject accidental manifest
  explosions. These are implementation safeguards, not recommended team sizes.
- Delegation depth two: master → manager → worker.
- One retry per worker; two manager review/rework rounds.
- One write-enabled worker per ownership scope.
- One read-only Sol reviewer per manager at high-risk design, verification, or
  integration gates; close the reviewer after the gate.
- No production, deployment, spending, customer communication, privilege
  expansion, or destructive operation without the existing user approval gate.
- Target 70–85% of model tokens in Luna, 10–20% in managers, and 5–10% in the
  master. These are measured targets, not dispatch quotas.

Raise concurrency after accepted cycles show at least 85% first-pass worker
acceptance, under 20% rework, zero write collisions, and at least 40% less
Sol-token use per accepted outcome than the single-thread baseline. Lower
concurrency when collision, rework, provider throttling, or integration queues
rise. Scaling is a reconciliation decision, not a one-time phase unlock.

## Complete context without context pollution

Do not broadcast the master transcript or raw logs. Give every manager the
complete Program Contract. Give every worker a complete outcome capsule:

- program ID/version, north star, and user value;
- complete global and manager outcomes;
- roadmap position, dependencies, and interfaces;
- architecture rules, non-goals, and constraints;
- owned task and paths;
- acceptance checks, budget, and stop rules.

This is complete decision context, not the entire conversation.

Each worker returns:

- `complete | blocked | failed`;
- artifact or exact changed paths;
- checks run and outcomes;
- assumptions and unresolved risks;
- token/time usage when available;
- recommended next action.

Each manager independently verifies the work and returns:

- `accept | rework | escalate | stop`;
- accepted artifacts or commit;
- evidence and failed checks;
- worker acceptance/rework statistics;
- Luna, Terra, manager Sol, and reviewer Sol usage;
- collisions, policy events, and residual risks;
- next exact action.

The master additionally returns the validated execution-efficiency receipt and
its separate delivery, hierarchy, Luna, efficiency, and scaling gate decisions.
Business acceptance does not imply that any execution-fabric gate passed. Completion of outcome-controlled fabric work additionally requires one independently accepted reality receipt that judges actual artifacts against the original objective. Production summaries are not acceptance evidence.

The master consumes manager receipts, not worker transcripts. It verifies every
high-risk result and samples at least one low-risk result per manager.

## Phase barriers and communication

Use these mandatory phase states:

1. `charter`: acknowledge Program Contract and authority.
2. `discovery`: report verified reality, gaps, and roadmap effects.
3. `design`: submit task DAG, interfaces, isolation, tests, and budget.
4. `execution`: report accepted worker outputs, rework, and drift.
5. `verification`: report manager and independent-review evidence and risks.
6. `integration`: report the integrated artifact for master acceptance.

Every manager sends one compact report at every phase. Charter, design,
verification, and final integration are true decision barriers: the master
returns an authenticated master decision of `continue`, `rework`, `pause`, or
`terminate`
bound to the current program, definition, outcome digest, and phase report.
Silence is never a grant; a time-budgeted wait escalates rather than waiting
forever. Workers cannot start before design is accepted, and integration cannot
start before verification is accepted. Routine execution subphases between
those barriers may auto-continue only under the unchanged accepted charter when
all checks, budgets, concurrency, and authority conditions pass. Every
subphase remains visible and overridable.

Use five typed messages:

- `master_directive`: program version, manager charter, decision, and deadline;
- `manager_phase_report`: state, evidence, variance, usage, risks, requested
  decision, and next plan;
- `manager_worker_contract`: complete outcome capsule plus bounded task;
- `worker_receipt`: artifact, evidence, usage, assumptions, and status;
- `manager_escalation`: exact decision or authority the manager cannot make.

Cross-manager dependencies go through the master or durable control plane.
Managers may exchange read-only artifacts but cannot silently change each
other's roadmap, scope, or ownership.

## Routing and escalation

Use Luna for repository mapping, implementation inside a bounded ownership
scope, test creation and execution, mechanical refactors, structured research,
feature-off migration drafts, and artifact production.

Keep architecture, prioritization, cross-cutting design, permission changes,
security decisions, schema authority, conflict resolution, and final acceptance
with Sol.

Allow a manager to spawn one read-only Sol reviewer at a material phase gate.
The reviewer receives the Program Contract, phase report, artifacts, and rubric,
but not the manager's preferred conclusion.

After one failed Luna attempt, change the hypothesis or task contract. After
two failures, use one bounded Terra exception or replan; never repeat the same
prompt.

## Reconciliation loop

The master reconciles desired and observed state:

1. Observe phase reports, manager receipts, and durable task state.
2. Compare results with the versioned Program Contract.
3. Stop duplicate, stale, blocked, or budget-exhausted branches.
4. Resolve cross-manager conflicts and dependency drift.
5. Issue `continue`, bounded `rework`, `pause`, or `terminate`.
6. Accept evidence, revise the program version when direction changes, publish
   one checkpoint, and release completed threads.

Do not count audits, tests, migrations, or agent activity as product movement
unless they are evidence for a named accepted outcome.

## Stop conditions

Stop when the outcome is accepted, a material safety boundary is reached, the
budget expires, two manager cycles produce no accepted movement, worker rework
exceeds 30%, a write collision occurs, or the user stops it. Cancellation
propagates from master to managers to workers.
