---
name: autonomy-suite
description: Coordinate the Autonomy Suite of reusable agent-work skills as one governed system. Use when a user asks to run, plan, supervise, or improve autonomous multi-agent work and needs the right combination of loops, task graphs, verification, delegation, and cost-aware routing.
---

# Autonomy Suite

Use this as the single entry point for the named Autonomy Suite. Load only the components required by the work.

## Canonical components

| Need | Skill | Use it for |
| --- | --- | --- |
| Recurring autonomous work | `$bounded-autonomy-loop` | Durable periodic review, state, stop conditions, and anti-loop controls. |
| Work decomposition and parallelism | `$durable-task-dag` | Dependencies, pull-based tasks, leases, recovery, and a visible control plane. |
| Quality-critical work | `$verified-work-loop` | Plan-execute-verify-replan cycles with independent challenge. |
| Nested delegation | `$supervised-subagent-tree` | Approval-gated child tasks, restricted inheritance, lineage, and budgets. |
| Cost and capability selection | `$tiered-agent-routing` | Strong planning/review with cheaper bounded execution lanes. |
| Sol-managed Luna labor | `$luna-execution-fabric` | Isolated Sol manager threads supervising bounded Luna worker teams with compressed evidence handoffs. |
| Portfolio and product direction | `$strategy-pillar` | Run the separate strategy layer that chooses outcomes before execution. |
| Adaptive project operating model | `$elastic-company-os` | Create one isolated project control instance and evolve its method through reviewed feedback. |

## Assembly order

1. Start with **Strategy Pillar** for a new project, major initiative, portfolio decision, or unclear direction.
2. Create or load the project's **Elastic Company OS** instance when the work spans multiple cycles, functions, or agents.
3. Load **Bounded Autonomy Loop** only after strategy has defined an accepted outcome and the project instance passes its scheduler-readiness gate.
4. Add **Durable Task DAG** when there are dependencies, more than one work lane, or recoverable long-running work.
5. Add **Verified Work Loop** before changes with material safety, customer, production, financial, or quality impact.
6. Add **Supervised Subagent Tree** only if nested delegation is necessary; define approvals and budgets first.
7. Add **Tiered Agent Routing** whenever tasks vary materially in ambiguity, blast radius, or verification cost.
8. Add **Luna Execution Fabric** when the user explicitly wants hierarchical manager threads or Luna-heavy parallel execution. Keep the master at Sol, managers at Sol, and bounded labor at Luna.

## Default operating contract

Before dispatching work, record outcome, scope, acceptance evidence, allowed and prohibited actions, budget, review cadence, data boundaries, ownership, stop conditions, and rollback. Use the smallest combination that covers the task.

For product-transformation work, also require a program-requirement ID, user-visible capability, demo path, and a statement of why the work outranks the next available capability or innovation bet. A clean test, unchanged repository, or audit finding does not by itself justify more work or a no-op.

Persist one shared ledger and one control-plane view. Require every component to read the ledger before work and write evidence after material progress. Treat user approval as mandatory for external side effects, privilege expansion, spending, deployment, customer communications, and delegation beyond the configured child depth or budget.

Use [references/control-plane-schema.md](references/control-plane-schema.md) to define durable task, run, lease, approval, artifact, and budget records. Use [references/quality-telemetry.md](references/quality-telemetry.md) to set measurable engineering gates. Use [references/development-delivery.md](references/development-delivery.md) for branch, review, rollout, and rollback discipline. Start new work from the matching file in [templates/](templates/).

## Model ladder

- Route deterministic, repetitive, inventory, formatting, and narrow-check work to **GPT-5.6 Luna**.
- Route scoped implementation, debugging, targeted research, and test creation to **GPT-5.6 Terra**.
- Route architecture, decomposition, risk decisions, delegation, conflict resolution, security review, and final acceptance to **GPT-5.6 Sol**.

Escalate to a higher tier when ambiguity, blast radius, novelty, or verification difficulty exceeds the current tier. Never use lower cost as a reason to bypass independent verification or a required approval.

## Guardrails

- Do not create perpetual loops; every loop must have a scheduler, budget, lease, stop condition, and escalation path.
- Do not use nested agents to bypass tool policies, approvals, or permission boundaries.
- Do not accept a worker result without evidence appropriate to its risk class.
- Do not use all components by default. Avoid complexity that produces no measurable improvement.
- Do not let safety, audit, or maintenance lanes become the product roadmap. If two accepted tasks fail to advance a visible milestone, emit a drift event and re-plan from the product program.
- Do not broadcast the root transcript to all workers. Managers must send task-local context and return compressed evidence receipts.
- Do not assume more agents reduce tokens. Measure total tokens, Sol-token share, cache use, rework, and accepted lead time against a single-thread baseline.

## Handoff

On pause, completion, or escalation, update the ledger with the exact state, completed evidence, rejected paths, known gaps, and next safe action. Cancel scheduled work on completion or user stop.

## Readiness requirement

Do not call the suite production-ready from principles alone. Before a stage is accepted, verify that its control-plane records, policy enforcement, quality gate, telemetry, tests, and delivery/rollback path exist and are exercised for that stage's risk class.
