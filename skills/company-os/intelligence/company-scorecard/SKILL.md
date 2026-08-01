---
name: company-scorecard
description: Define and operate a decision dashboard for strategy, projects, operations, customer outcomes, research confidence, cost, risk, and autonomous-agent health. Use when leaders need a clear control plane rather than scattered reports or status updates.
---

# Company Scorecard

Build a dashboard around decisions and exceptions, not vanity metrics.

## Panels

- Strategy: active bets, expected outcomes, evidence confidence, decision dates, stop/pivot candidates.
- Customer: adoption, retention/health, pain themes, feedback freshness, research gaps.
- Delivery: milestone health, dependency age, lead time, rework, quality gates, blocked work.
- Operations: service health, incidents, recovery, capacity, cost, security/privacy exceptions.
- Agent system: active Sol managers and Luna workers, current manager phase and
  age, stale reports, first-pass worker acceptance, rework, write collisions,
  policy denials, approvals, total tokens, Luna token share, Sol tokens per
  accepted outcome, single-thread baseline, and cancellation propagation.
- Product-program alignment: requirement coverage, visible-capability progress, demo evidence, frontier-bet pipeline, enabler allocation, drift events, and cost per accepted capability.

For every metric define source, owner, baseline, target, threshold, update cadence, reliability, and decision triggered by deviation. Show uncertainty and data freshness. Do not score green when data is absent.

Use the scorecard for daily exceptions, weekly program/portfolio decisions, and monthly operating review. Keep deep evidence linked behind each material signal.

Do not mark the execution fabric healthy because managers or workers are
active. Require an accepted Company OS outcome, zero collisions, independently
accepted verification, and measured cost/lead-time comparison with the
single-thread baseline. Keep concurrency at the default until three comparable
accepted cycles pass the scaling policy.

## Drift gate

Do not equate clean tests or completed technical tasks with product progress. Every program review must show which user-visible capability moved, what demonstrates it, and which requirement it satisfies. Trigger a stop-and-replan decision when two work items in a row have no visible milestone movement, a frontier-bet pipeline is empty, or enabler work exceeds its allocated share without a documented P0 exception.
