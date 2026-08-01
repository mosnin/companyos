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

1. Create one versioned Program Contract with north star, customer value,
   complete outcome, rationale, architecture, roadmap, dependencies, non-goals,
   acceptance evidence, constraints, budget, and stop conditions.
2. Split the roadmap into at most two independent manager outcomes initially.
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
   `configure-fabric`. Use `record-fabric-phase` and
   `decide-fabric-phase` for every manager barrier.
8. Dispatch only unblocked tasks. Prefer parallel reads; allow one active writer
   for a resource or file-ownership scope.
9. Require managers to inspect evidence and the integrated result, not merely
   summarize worker claims.
10. Return phase reports and manager receipts to the master. The master accepts,
   requests bounded rework, escalates, pauses, or stops.

Read [references/fabric-contract.md](references/fabric-contract.md) before
launching manager threads or changing the default limits.

## Runtime adapter

For work governed by an Elastic Company OS instance, runtime admission is
always first. Before any provider call, native subagent spawn, or task/thread
creation, require all of the following:

- the exact validated and configured fabric manifest;
- the current program, work, cycle, and unexpired lease fence;
- the exact manager or worker identity, parent, model, canonical full scope,
  and budget from that manifest;
- an allowlisted provider, surface, and account;
- a single-capability signed master admission grant; and
- a successfully persisted `admit-runtime-attempt` record with its unique
  attempt ID and idempotency key.

Schema 8 implements only that feature-off, pre-launch admission record. It has
no provider launcher, provider observation, receipt, telemetry, or
reconciliation command. Therefore do not spawn a governed manager or worker
from this skill yet. Record the slice as `feature_off_code_complete` and
`runtime_unverified`; provider execution remains blocked until a later accepted
runtime slice consumes the admission before launch.

Outside an Elastic Company OS instance, prefer a native Luna subagent only when
the active collaboration surface explicitly lists `gpt-5.6-luna`; otherwise use
an isolated Luna task/thread. This non-governed fallback must not be represented
as Company OS admission, provider execution evidence, or real Luna dogfood.

Never substitute Terra or Sol while recording the worker as Luna. If neither
native subagents nor Luna tasks are callable, pause dispatch and report the
capability gap.

## Default limits

- Two concurrent Sol managers.
- Three concurrent Luna workers per manager and six globally. These are hard Phase 1 caps; a signed scaling expansion is not implemented yet.
- Delegation depth two: master → manager → worker.
- One retry per worker; two manager review/rework rounds.
- One write-enabled worker per ownership scope.
- One read-only Sol reviewer per manager at high-risk design, verification, or
  integration gates; close the reviewer after the gate.
- No production, deployment, spending, customer communication, privilege
  expansion, or destructive operation without the existing user approval gate.
- Target 70–85% of model tokens in Luna, 10–20% in managers, and 5–10% in the
  master. These are measured targets, not dispatch quotas.

Raise concurrency only after three accepted cycles show at least 85% first-pass
worker acceptance, under 20% rework, zero write collisions, and at least 40%
less Sol-token use per accepted outcome than the single-thread baseline. That evidence may justify a future reviewed policy, not an increase under this validator.

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

Every manager sends one compact report at every barrier. The master replies
with `continue`, `rework`, `pause`, or `terminate`. Workers cannot start before
the manager's design report is accepted. A manager cannot integrate before its
verification report is accepted.

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
