---
name: tiered-agent-routing
description: Route agent work across planning, execution, and review tiers to balance quality, latency, and token cost. Use for multi-model or multi-agent systems that need strong oversight without using the most expensive model for every task.
---

# Tiered Agent Routing

Use capability deliberately. High-cost reasoning is for irreversible judgment; cheaper lanes are for bounded, verifiable work.

## Assign tiers

- **Strategic tier — GPT-5.6 Sol**: architecture, decomposition, risk decisions, manager supervision, security review, integration decisions, and final acceptance.
- **Exception tier — GPT-5.6 Terra**: scoped implementation or debugging that failed twice in a properly bounded Luna lane because more reasoning is required.
- **Execution tier — GPT-5.6 Luna**: bounded implementation, test authoring and execution, repository exploration, structured research, mechanical refactors, formatting, inventory, narrow retrieval, and repetitive transformations.

Choose using task ambiguity, blast radius, reversibility, required context, verification cost, latency target, and budget.

## Routing contract

- Give workers a bounded specification, acceptance evidence, budget, and explicit stop/escalation rules.
- Keep sensitive context and powerful tools in the minimum necessary tier.
- Escalate to the strategic tier for novel decisions, conflicting evidence, security findings, broad changes, or failed verification.
- Require strategic review before accepting consequential output, regardless of execution tier.
- Default hierarchical programs to 70–85% Luna tokens, 10–20% manager Sol tokens, and 5–10% master Sol tokens. Treat these as measured targets, not dispatch quotas.
- After one failed Luna attempt, change the task contract or hypothesis. After two failed attempts, replan or use one bounded Terra exception.

## Optimize with evidence

- Measure quality, task completion, retries, latency, token use, cache effectiveness, and rework by route.
- Prefer deterministic tools over model calls for deterministic tasks.
- Revisit routing only from actual outcomes; do not optimize solely for low cost or high throughput.
- Keep a route decision record with task class, selected tier, escalation reason, evidence quality, latency, token/cost use, and rework result; periodically test lower-cost routes against a fixed evaluation set before widening their authority.
- Compare total tokens and Sol tokens separately. Parallelism may reduce elapsed time and expensive-model usage while increasing total tokens.
