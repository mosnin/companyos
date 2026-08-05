---
name: durable-task-dag
description: Turn a complex outcome into a durable task graph that agents can continuously pull, execute, verify, and recover. Use for long-running software, research, operations, or product work with dependencies, parallel lanes, and human review.
---

# Durable Task DAG

Use a task system as the control plane, not chat sessions or pull requests.

## Build the graph

- Express each deliverable as an independently verifiable task with an owner, scope, acceptance evidence, risk class, budget, and rollback plan.
- Represent dependencies explicitly. Agents may pull only unblocked tasks.
- Keep tasks small enough for one agent lane but large enough to produce a meaningful artifact.
- Allow agents to propose follow-up tasks, but require the control plane to classify and schedule them before work begins.

## Durable execution

- Persist task status, attempts, lease holder, heartbeat, artifact links, and failure reason outside the agent process.
- On lease expiry or crash, release the task safely; resume only after checking idempotency and partial side effects.
- Separate task completion from transport success. Mark complete only when acceptance evidence is attached.
- Use concurrency limits per repository, integration, tenant, and cost budget.
- Enforce state transitions, leases, approvals, budgets, and artifact provenance through a transactional control-plane contract; prompts may propose work but must not authorize it.

## Review and recovery

- Require independent verification for consequential tasks.
- Route failures to retry, replan, human approval, or dead-letter with explicit reason; never silently advance a dependency.
- Surface a control-plane view of queued, active, blocked, failed, and completed work plus cost and latency.
- Stop the graph when the outcome is accepted, budget is exhausted, or a material safety blocker occurs.
- Measure queue age, lease recovery, retry recovery, duplicate-action rate, accepted-task lead time, cost per accepted outcome, and blocked-dependency age.
