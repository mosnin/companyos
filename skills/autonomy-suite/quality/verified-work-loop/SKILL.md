---
name: verified-work-loop
description: Run a plan-execute-verify-replan loop for complex agent work with evidence gates, adversarial review, and safe recovery. Use when correctness, safety, or production readiness matters more than raw throughput.
---

# Verified Work Loop

Optimize for accepted outcomes, not activity.

## Cycle

1. **Plan**: state the objective, constraints, hypotheses, measurable acceptance criteria, and rollback.
2. **Execute**: perform one bounded change or investigation.
3. **Verify**: collect direct evidence from tests, source, runtime, or interaction. Label evidence type and limits.
4. **Challenge**: run an independent reviewer against assumptions, failure modes, security, regressions, and missing tests.
5. **Decide**: accept, replan, retry with a new hypothesis, escalate, or stop.

## Gates

- Never treat successful HTTP delivery, a generated artifact, or a passing narrow test as proof of the intended outcome.
- Require negative-path tests for retries, cancellation, concurrency, permissions, and degraded dependencies when applicable.
- Keep the planned scope fixed inside one cycle; capture discoveries as queued follow-up work.
- Use a release checklist covering behavior, security, privacy, reliability, observability, cost, accessibility, and rollback.
- Maintain reusable negative-path fixtures for duplicate delivery, crash-after-claim, stale lease, cancellation, expired approval, denied tool call, partial side effect, budget exhaustion, and rollback.

## Output

Maintain an evidence ledger with claim, evidence, confidence, remaining gap, owner, and next action. Report material findings only.
