---
name: project-program-management
description: Run project and program management for autonomous and human teams, including charters, roadmaps, milestones, goals, constraints, dependencies, monitoring, and methodology selection. Use when coordinating multiple projects or a complex initiative from kickoff through outcomes.
---

# Project and Program Management

## Start with outcomes

Create a project charter with objective, customer/business outcome, metric baseline and target, scope/exclusions, constraints, risks, owners, decision rights, budget, dependencies, and stop criteria.

Break programs into initiatives, milestones, and smallest valuable slices. Distinguish committed work from options, discovery, and debt. Use a dependency map and a risk register; never hide a blocked milestone behind percent-complete reporting.

## Product-program control

For an ambitious product mandate, create one program contract before autonomous execution. Give every task a requirement ID, a user-visible outcome, a demo path, an evidence standard, a budget, and a stop condition. Maintain two deliberately separate backlogs:

- **Committed capabilities:** the experiences required to make the product real.
- **Frontier bets:** bold, differentiated possibilities that could make the product category-defining.

At every portfolio review, generate and rank fresh product opportunities. Do not let existing code, an audit finding, or the easiest testable task choose the roadmap. Reliability, security, and infrastructure work are enablers; cap them to the minimum required to unlock the next demonstrable capability unless a P0 customer-safety issue requires an explicit interruption.

## Frontier product sequence

For a category-ambitious product, the sequence is mandatory. Do not begin with implementation, hardening, or an abstract feature brainstorm.

1. **Product reality audit.** Trace the actual user journey and its backing code: current capabilities, hidden capabilities, failure states, duplicated surfaces, data/context available to the agent, and the harness that produces each interaction. Capture the real UI where access permits; name an access blocker rather than substituting marketing copy for the application.
2. **First-principles opportunity brief.** Define the customer job, the painful status quo, the agent's unfair advantage, the interaction model, and the category-level experience Chippi should make possible. Identify both what must be preserved and what should disappear.
3. **Technology radar.** Research current primary technical sources and credible practitioner evidence for the relevant capability. Compare the existing stack with what is newly viable, what is maturing, and what is still experimental. Record dates, migration path, operating cost, security constraints, and an explicit reason to adopt or reject each option.
4. **Experience concept and prototype.** Turn the opportunity into a cohesive user journey, information architecture, interface/motion behavior, and a smallest credible prototype. A list of isolated features is not a product concept.
5. **Stage-gated delivery.** Only now decompose the accepted concept into vertical slices. Each slice must create a visible new capability, include its direct enablers, and end in a usable demo plus evidence.
6. **Quality and operations.** Audit reliability, security, latency, accessibility, cost, telemetry, and rollout only against a named experience being protected or unlocked.

The default order cannot be reversed merely because maintenance work is easier to test. A P0 customer-safety issue may interrupt it, but must be logged as an interruption and the product sequence resumes immediately after containment.

## Exceptional-product standard

Treat an established, customer-facing product as an ambitious product program, never as a hobby-project backlog. For each concept ask: does it create a meaningfully better way to work, does it feel native rather than bolted on, does it compound Chippi's real-estate context and trust, and would removing it make the product less inevitable? If not, do not elevate it over a stronger concept. Preserve the product's visual language while making interaction, clarity, motion, and perceived intelligence feel deliberate and calm.

## Drift prevention

Require every task to be one of two valid types: a **committed capability** or a **frontier bet**. Do not reject a novel idea merely because its final feature name or implementation is unknown. A frontier bet must instead state a point of view, the new experience it could create, the smallest credible prototype, a learning signal, a cap, and a scale/pivot/kill decision.

Reject a task only when it cannot answer all four questions in the form appropriate to its type:

1. Which program requirement does it advance?
2. What can a user do after it that they could not do before?
3. What artifact demonstrates it: a working flow, UI state, prototype, test, or measured experiment?
4. Why is it higher leverage than the next available capability or frontier bet?

Raise a drift event after two accepted tasks without visible milestone movement **or** validated frontier learning, or when enabler/audit work exceeds its program allocation without an approved P0 exception. Pause the affected lane, reconcile cost and outcome, and re-rank the whole portfolio. An unchanged Git diff is never a reason to no-op while a committed milestone or bounded frontier bet remains open.

Use [templates/frontier-product-program.md](templates/frontier-product-program.md) as the governing contract for product transformation work.

## Methodology selection

- **Discovery/lean:** uncertain customer need or solution; optimize for learning speed.
- **Iterative/Agile:** evolving product; optimize for working slices and feedback.
- **Stage-gated:** high-risk, regulated, expensive, or integration-heavy delivery; optimize for readiness evidence.
- **Flow/Kanban:** continuous operations or maintenance; optimize for queue age, throughput, and work-in-progress limits.

Use hybrids deliberately and record why.

## Monitoring

Track outcome metric, milestone health, dependency age, work in progress, lead time, rework, quality escapes, budget burn, capacity, risk trend, and decision latency. At every checkpoint decide continue, re-scope, re-sequence, pause, pivot, or stop.

For a Luna-heavy program, assign each independent roadmap outcome to one Sol
manager and represent the worker plan as a validated DAG. Require the Company
OS master to decide every charter, discovery, design, execution, verification,
and integration barrier. Track first-pass Luna acceptance, rework, collisions,
actual model-token share, Sol-token reduction against baseline, and accepted
lead time. Agent activity and phase reports are operating evidence, not
milestone progress.

## Handoff

Release only approved slices to the Autonomy Suite with an execution contract, quality gate, approvals, release plan, and rollback. Reconcile execution evidence against roadmap and outcomes at each checkpoint.
