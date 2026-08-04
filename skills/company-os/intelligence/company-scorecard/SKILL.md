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

## Execution-efficiency receipt

For every real multi-manager program, require one canonical
`company-os.execution-efficiency-receipt.v1`. Use the template under `assets/`
and validate one or more receipts with:

```bash
python3 scripts/validate_execution_efficiency.py path/to/receipt.json
```

The receipt records planned lanes versus actual manager ownership, actual
workers and observed models, maximum observed concurrency, host-cap variances,
milestone times, role-level usage, baseline comparisons, first-pass acceptance,
rework, collisions, and semantic artifact bindings after independent readback.
Unavailable is a valid observation, not a zero. A structurally valid receipt may
accept the business deliverable while returning `efficiency_proven: false` and
`scaling_evidence_eligible: false`.

It also records the immutable mandatory-requirement plan, independent
requirement results, per-artifact required versus applied capability IDs, and
the authority level required for acceptance. Any mandatory requirement that is
unsatisfied or unknown, any missing required capability, or any lower-authority
decision makes `delivery_accepted` false. Report time-to-rejected-artifact
separately; never count it as throughput.

Only a group of at least three comparable accepted receipts may pass the scale
gate. The verifier requires at least 85% first-pass acceptance, under 20% rework,
zero collisions and duplicate artifacts, observed Luna/max labor, measured token
share, at least 40% lower Sol-token use than the single-thread baseline, and no
lead-time regression. Never scale from task count, requested models, or a clean
artifact alone.

## Durable observatory

Persist every completed, rejected, blocked, cancelled, or failed real program in
the provider-neutral Postgres observatory under `sql/`. The database is an
evidence ledger, not the orchestrator: Company OS remains reusable, and each
operator supplies their own Postgres-compatible connection. Neon is a supported
host, not a hard dependency.

Apply migrations in numerical order, render ingestion SQL with
`scripts/render_execution_efficiency_ingest.py`, and execute it through the
operator's approved database connection. The renderer validates and hashes the
canonical receipt before producing SQL. The database verifies that hash again,
stores immutable raw and normalized evidence, supports explicit supersession,
and exposes `run_scorecard` plus `comparison_trends`. Never overwrite a rejected
run after rework; ingest the revision as a successor so improvement and
regression remain measurable.

Before persistence, remove secrets, credentials, access tokens, raw customer
records, and unnecessary personal data from receipts. Store evidence references
or content hashes when the underlying artifact contains sensitive material.
Keep database credentials outside the repository and output. Follow
[references/company-os-observatory.md](references/company-os-observatory.md) for
the lifecycle, provider contract, standard queries, and activation gates.

## Drift gate

Do not equate clean tests or completed technical tasks with product progress. Every program review must show which user-visible capability moved, what demonstrates it, and which requirement it satisfies. Trigger a stop-and-replan decision when two work items in a row have no visible milestone movement, a frontier-bet pipeline is empty, or enabler work exceeds its allocated share without a documented P0 exception.
