---
name: strategy-pillar
description: Run a separate strategy and portfolio-management control plane that determines what projects, products, and initiatives should exist before autonomous execution begins. Use for product direction, business planning, portfolio choices, project intake, roadmaps, prioritization, and outcome governance.
---

# Strategy Pillar

Keep strategy independent from execution loops. Own why, what, and how success is measured; let the Autonomy Suite execute approved work.

## Operating model

Use four connected levels:

1. **North star** — customer, business, and product thesis; principles and constraints.
2. **Portfolio** — choose the few bets that deserve investment; defer or stop the rest.
3. **Initiative** — define problem, target user, opportunity, success metric, risk, and investment thesis.
4. **Project** — create roadmap, milestones, feature slices, operating plan, and execution contract.

Do not start an autonomous build loop until the initiative has a decision record, measurable outcome, owner, risk class, and smallest valuable first slice.

## Cadence and handoff

Run weekly portfolio review and material project checkpoints. Review customer signal, economics, risk, progress, cost, and evidence. Decide continue, expand, pivot, pause, or stop.

When the review turns on opportunity cost, unit economics, pricing, or market structure, load `$economics-architect` as the economics overlay.
Do not send `$economics-architect` to Luna workers.

When the review turns on business model, competitive strategy, value proposition, or market analysis, load `$business-architect` as the business-architecture overlay.
Do not send `$business-architect` to Luna workers.

Pass only approved project slices to execution with outcome, constraints, acceptance evidence, budget, action boundaries, rollout/rollback, and feedback signals that can change strategy. Execution returns evidence; it cannot silently expand scope.
