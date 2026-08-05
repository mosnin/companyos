---
name: bounded-autonomy-loop
description: Run a safe, reusable autonomous project loop with durable state, scheduled reviews, explicit stop conditions, and anti-loop controls. Use when a user wants ongoing work on any project to continue independently at a cadence such as every 30–45 minutes until they stop it.
---

# Bounded Autonomy Loop

Run autonomous work as a durable state machine, never as an uncontrolled background process.

## Intake

Establish the smallest complete operating contract before starting:

- Outcome, in-scope systems, and success evidence.
- Allowed actions, prohibited actions, and approval gates.
- Cadence, defaulting to 45 minutes when the user gives a range of 30–45 minutes.
- State location: a version-controlled Markdown ledger plus an optional human-readable tracker.
- Stop conditions: completion, budget/time limit, meaningful blocker, user cancellation, or safety concern.

Make reasonable project decisions; ask only when a missing decision would materially expand authority or create irreversible risk.

## Durable State

Create or update a compact execution ledger before material work. Keep these fields current:

- North-star outcome and constraints.
- Current phase, owner, and next safe action.
- Evidence ledger: source review, tests, interaction checks, and unverified runtime assumptions kept separate.
- Decisions and rejected approaches.
- Work completed, active work, blockers, risks, and rollback notes.
- Quality gate, acceptance criteria, and last-review time.

Never store secrets, credentials, or customer data. Link detailed reports instead of duplicating them.

## State Machine

Use these states and transitions:

1. **Observe** — load the ledger, inspect only fresh relevant state, and detect changed conditions.
2. **Decide** — choose one highest-value action that fits scope, budget, and risk.
3. **Execute** — run bounded, non-overlapping work with a clear owner.
4. **Verify** — collect direct evidence; do not infer production success from local checks.
5. **Publish** — update the ledger and human tracker with meaningful outcomes.
6. **Wait** — schedule the next review or wake promptly on a meaningful event.
7. **Stop/Escalate** — finish, pause safely, or request the minimum necessary decision.

Do not advance after a failed verification. Prefer safe pause and diagnosis over speculative retries.

## Scheduling

Use the platform’s automation/scheduler facility when it can target the correct project and does not create unwanted deployment or production work. Otherwise keep the cadence inside the delegated project worker and record each review in the ledger.

At every wake:

- Check the prior review’s exact next action and completion evidence.
- Detect duplicate work, stuck retries, lease expiration, budget exhaustion, and changed scope.
- Continue only if a new, safe, valuable action exists.
- Suppress no-op heartbeats. Report only discoveries, progress, blockers, or completion.

## Anti-Loop Rules

- Do not repeat the same failed action without a new hypothesis or changed evidence.
- Limit retry attempts and use backoff; record attempt counts and failure signatures.
- Keep concurrent lanes disjoint and assign explicit ownership.
- Require idempotency, cancellation, and rollback considerations for consequential actions.
- Escalate after a material blocker persists across three reviews or cannot be resolved safely.
- Stop when acceptance criteria are met; do not manufacture work to stay active.

Record every wake, transition, retry, lease expiry, and stop reason as durable control-plane events. Treat a missed wake or failed scheduler delivery as an incident to diagnose, never as an implicit completed review.

## Quality Gate

Define stage-specific acceptance criteria before implementation. Score applicable dimensions with evidence: outcome quality, user value, safety, reliability, privacy, usability, latency, cost, maintainability, test coverage, observability, and rollback readiness.

Do not claim a score without evidence. Treat unresolved security or data-safety issues as a no-go regardless of average score. For ambitious work, require every critical applicable dimension to meet the user’s stated threshold before advancing.

## Delegation

Delegate only bounded lanes that can progress independently. Transfer outcome, constraints, authority, state location, evidence standard, and return-report requirement. Review every delegated result against the ledger before accepting it.

For high-stakes plans, use a stronger planning/review lane and cheaper bounded execution lanes only when their work can be independently verified.

## Completion

On completion or user stop:

- Cancel or disable the associated scheduler/automation.
- Finalize the ledger with outcome, evidence, known gaps, and exact follow-up actions.
- Report what changed, what was verified, what remains unverified, and any rollback or monitoring needed.
