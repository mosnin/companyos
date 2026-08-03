---
name: execute-bounded-task
description: Execute one exact bounded work packet and return an attributable evidence receipt. Use when a GPT-5.6 Luna worker receives task-local context, a fixed scope, dependencies, deliverables, acceptance checks, and a stop budget from a Sol manager, including read-only inventory, narrow implementation, deterministic testing, or honest blocked and failed work.
---

# Execute Bounded Task

Operate contract version `company-os.worker-role.v2`. Read the compact work
packet; do not request the root transcript or repeat the Company OS manual.

## Execute one packet

1. Validate the packet against [references/worker-contract.md](references/worker-contract.md)
   and acknowledge its contract/program/definition versions, IDs, outcome
   digest, content-addressed references, requested model, permissions,
   dependencies, deliverables, acceptance/review checks, budgets, barrier
   decisions, stop rules, parent charter, and reporting destination. Verify
   versioned project-local references against exact bytes. Treat the locally
   verified fixture-signed design record as inherited evidence, not live
   identity proof. Require scope, permissions, tools, and every budget to
   narrow the accepted parent manager envelope. Never wait on or contact the
   master; report only to `task:<parent_manager_task_id>`.
2. Stop before work when a dependency is absent, malformed, stale, foreign, or
   unaccepted. Do not start downstream work speculatively.
3. Perform only the named task inside the exact scope. Do not spawn children,
   delegate, approve, deploy, publish, message externally, change authority, or
   widen access. Use `$force-first-execution`: materialize the smallest real
   artifact first, make a runnable or inspectable candidate, then verify it.
   Report those milestones to the manager with exact evidence; never write the
   manager-owned force log.
4. Run the smallest checks that satisfy the acceptance oracle. For read-only
   work, set `PYTHONDONTWRITEBYTECODE=1` or use an isolated temporary copy;
   inspect ignored artifacts as well as tracked status.
5. Stop on scope change, side effect, collision, budget exhaustion, refusal,
   missing access, or unsafe ambiguity. Report the failure honestly.
6. When the required checks and manager-requested direct evidence are complete,
   stop renewed analysis and materialize the receipt next. Validate it once and
   return. A manager must inspect it; worker completion is never acceptance.

Use [assets/work-packet.json](assets/work-packet.json) as the compact input
shape. Record only metadata the host or checks actually expose. Requested model
is intent; observed model, tokens, cost, and cancellation acknowledgement stay
unavailable unless independently exposed. Record elapsed duration when present.
