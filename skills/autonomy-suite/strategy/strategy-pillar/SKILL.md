---
name: strategy-pillar
description: Run a separate strategy and portfolio-management control plane that determines what projects, products, and initiatives should exist before autonomous execution begins. Use for product direction, business planning, portfolio choices, project intake, roadmaps, prioritization, and outcome governance.
---

# Strategy Pillar

<!-- council-os:begin -->
## Board above executive management

Company OS owns the corporate hierarchy: **human owner → board → executive
management/master → managers → workers**. Company OS Web stores and displays
business data and context. It does not host or control the hierarchy.

At framework startup/resume, the executive loads `company-board` from this
Company OS distribution (`skills/company-os/company-board/SKILL.md` relative to
the distribution root). Establish or reconcile one persistent host-native board
chat for the active orchestration instance before adopting strategic direction.
Derive the instance from existing framework state; do not ask for a Web project
to contain the board. Managers escalate strategic matters through the executive.

Consult that board on company thesis, market entry/exit, material positioning or
business-model changes, strategic roadmaps, portfolio priorities, major resource
allocations, reorganization, pivots/stops, and conflicting executive proposals.
Inside its chat the board invokes `$council` with all 17 requested perspectives
and Karpathy's independent response → peer review → synthesis process. Use the
host's available agent tools and concurrency limits. A missing host capability
must remain visible; do not manufacture a running chat or completed council.

Bind advice to the exact instance, executive and board chat IDs, Program Contract
version, and canonical Company OS Web context revisions. The executive records
adoption/modification/rejection and translates direction into accountable goals
and manager charters through existing dispatch rules. Report measured results
back to the same board at the agreed review trigger. Reconsult on material changes;
routine execution under unchanged accepted direction continues without a meeting.

Follow `company-board` for provisioning, context grounding, artifacts, validation,
and the reporting loop. Human instructions retain authority. The board provides
strategic direction and challenge; it does not dispatch workers, grant permissions,
or enable feature-off runtime adapters or schedulers. An explicit human waiver is
recorded as such, never as a completed consultation.
<!-- council-os:end -->


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
