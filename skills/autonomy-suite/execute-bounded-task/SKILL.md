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
   decisions, stop rules, and reporting destination.
   Treat the design authorization as inherited evidence. Never wait on or
   contact the master; report only to the manager destination in the packet.
2. Stop before work when a dependency is absent, malformed, stale, foreign, or
   unaccepted. Do not start downstream work speculatively.
3. Perform only the named task inside the exact scope. Do not spawn children,
   delegate, approve, deploy, publish, message externally, change authority, or
   widen access.
4. Run the smallest checks that satisfy the acceptance oracle. For read-only
   work, set `PYTHONDONTWRITEBYTECODE=1` or use an isolated temporary copy;
   inspect ignored artifacts as well as tracked status.
5. Stop on scope change, side effect, collision, budget exhaustion, refusal,
   missing access, or unsafe ambiguity. Report the failure honestly.
6. Return the receipt schema defined in the contract reference. A manager must
   inspect it; worker completion is never acceptance.

Use [assets/work-packet.json](assets/work-packet.json) as the compact input
shape. Record only metadata the host or checks actually expose. Requested model
is intent; observed model, tokens, cost, and cancellation acknowledgement stay
unavailable unless independently exposed. Record elapsed duration when present.
