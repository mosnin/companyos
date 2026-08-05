# Quality and telemetry

Define baselines before optimizing. Measure accepted outcomes, not raw task count.

## Core scorecard

| Area | Measure | Gate |
| --- | --- | --- |
| Delivery | accepted-task rate, lead time, rework rate | improve without increasing escaped defects |
| Reliability | retry recovery, stale-lease recovery, duplicate-action rate, dead-letter age | zero silent drops; tested recovery paths |
| Quality | acceptance-test pass rate, regression escape rate, reviewer disagreement | evidence attached to every accepted consequential task |
| Safety | policy-denial correctness, approval coverage, privilege violations | zero unresolved critical violations |
| Cost | cost per accepted outcome, token use by tier, cache hit/usefulness, wasted retries | route changes require measured benefit |
| Latency | queue age, time-to-first-progress, task completion percentile, approval wait | define service targets per risk class |
| Operations | heartbeat freshness, alert precision, incident recovery time | alert on stalled work before user impact |

## Evaluation fixtures

Maintain fixtures for: dependency ordering, duplicate delivery, crash-after-claim, stale lease, cancellation, partial side effect, expired approval, denied tool call, prompt injection, budget exhaustion, rollback, and model-route escalation.

Run deterministic fixtures in local/CI checks. Use controlled integration tests for real providers. Label source review, local test, preview evidence, and production evidence separately.
