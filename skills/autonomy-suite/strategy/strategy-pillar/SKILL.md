---
name: strategy-pillar
description: Run a separate strategy and portfolio-management control plane that determines what projects, products, and initiatives should exist before autonomous execution begins. Use for product direction, business planning, portfolio choices, project intake, roadmaps, prioritization, and outcome governance.
---

# Strategy Pillar

<!-- council-os:begin -->
## Board above management

The hierarchy is **human owner → Council OS advisory board → Company OS executive
management/master → program managers → workers**. Council OS informs high-level
direction; the human owner and existing authorization rules retain decision authority.

Automatically invoke `$council` before adopting a company thesis, market entry or
exit, material positioning/business-model change, portfolio reprioritization,
resource allocation outside the accepted budget, strategic reorganization, or a
major continue/pivot/stop decision. Also consult when executive recommendations
conflict. Do not wait for the user to type the command. Routine work under an
unchanged accepted charter proceeds without another board session.

Resolve the installed `council` skill (plugin-qualified name `council-os:council`
when required) from the host skill registry and follow its full 18-member process.
Use Codex-native agents by default. If unavailable, name the missing consultation
capability; do not manufacture a council result. Continue independent reversible
work, but leave the strategic adoption gate pending. The user can explicitly waive
consultation for a decision; record the waiver instead of implying board review.

Pass a project-local packet containing decision ID, question, company context,
options, evidence, constraints, and decision owner. Preserve all mandatory user
requirements. Store the packet and complete, validated advisory record under
`.company-os/council/<decision-id>/`. Bind it to the exact packet digest. Reuse an
unchanged decision record; reconsult on material changes to scope, evidence,
options, constraints, or direction. Avoid recursive consultation: the council does
not dispatch management or invoke itself.

Before strategic dispatch, the master records its adoption, modification, or
rejection and rationale, decision owner, record path/digest, management owner,
success metric and review trigger in the Program Contract or decision log. Preserve
minority concerns. A board memo is advice, not execution approval or proof of
runtime, provider, or business outcomes. Managers escalate strategic changes to
the master and may not bypass this consultation by changing their own charters.

This is a skill-orchestration consultation gate. It does not change controller
schemas, grant new runtime permissions, or enable schedulers.
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
