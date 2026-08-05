---
name: supervised-subagent-tree
description: Delegate nested sub-agent work safely through a permissioned hierarchy with approval gates, budgets, lineage, and visible results. Use when an orchestrator needs workers to create bounded child tasks without uncontrolled self-spawning.
---

# Supervised Subagent Tree

Treat delegation as a governed capability, not an unrestricted tool.

## Root policy

- Define the root outcome, allowed systems, prohibited actions, approval thresholds, maximum depth, concurrency, token/cost/time budgets, and stop conditions.
- Give every child a durable parent link, task contract, permission envelope, lease, audit trail, and return artifact.
- Children inherit the narrowest permission set; they may never escalate their own authority.
- For the Luna Execution Fabric, use exactly two delegation edges: Sol master → Sol manager → Luna worker. Luna workers may not create children.

## Delegation rules

- Allow child creation only for independent, bounded work that advances the parent task.
- Require approval for new external access, spending, deployment, data mutation, customer-facing communication, privilege changes, or crossing the configured depth/budget limits.
- Prevent cycles, duplicate children, and same-resource concurrent writers.
- Require a parent or designated reviewer to accept child evidence before merging it into the parent result.
- Require managers to inspect the artifact or diff and rerun acceptance checks. A worker summary is never acceptance evidence by itself.
- Bind manager count, workers per manager, and total worker capacity to the
  accepted work graph. Bind active concurrency separately to the current scale
  gate and available budget. Start with the smallest cohort that exposes real
  dependencies, then raise or lower active slots from measured acceptance,
  rework, collisions, recovery, latency, and cost. Never collapse unrelated
  outcomes to satisfy a fixed team ratio.
- Enforce approval and delegation limits in the control plane and tool adapters; do not rely on task text or prompts to constrain authority.

## Supervision

- Track tree status, lineage, cost, leases, progress, artifacts, and blocked edges in one control plane.
- Propagate cancellation downward; propagate failures upward with the lowest safe recovery action.
- Quarantine untrusted external content and enforce tool policy outside prompts.
- Terminate idle, stuck, or budget-exhausted branches; retain the evidence ledger for recovery.
- Emit lineage, model-tier, cost, policy-decision, and artifact events so the full tree can be reconstructed after an incident.
