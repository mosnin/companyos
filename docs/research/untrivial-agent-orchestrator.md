# Agent Orchestrator comparison and bounded adoption

Reviewed Untrivial-ai/agent-orchestrator at commit
`ab968d5e761469eb32c1b4dc780cde721a9998de` on 2026-09-13.
Upstream license: Apache-2.0. This change is an original Company OS adaptation
of mechanisms, with no vendored upstream implementation or daemon.

Company OS remains the orchestration framework; Company OS Web remains business
context and display. Native board, executive, manager, and worker conversations
and their existing authority boundaries remain the execution structure.

| Mechanism found | Company OS disposition |
| --- | --- |
| Route PR feedback to its owning session; process CI, review, and conflict conditions independently | Added manager feedback procedure and pure action planner that targets the existing worker conversation. |
| Persist meaningful feedback signatures across restarts | Added explicit history input, duplicate suppression, and durable host recording instructions. |
| Bound retries and distinguish blocked permission from idle | Added explicit exhausted, deferred, approval, and uncertain-delivery outcomes. |
| Launch generation guards and isolated worker sessions | Already represented by native task runtime generation, lineage, dispatch, and reconciliation contracts; no second runtime added. |
| Continuously observe sessions and PR lifecycle | Requires host event ingestion and durable adapter integration; the new helper does not implement a daemon or prove live delivery. |

## Source evidence

- [Lifecycle reactions](https://github.com/Untrivial-ai/agent-orchestrator/blob/ab968d5e761469eb32c1b4dc780cde721a9998de/backend/internal/lifecycle/reactions.go):
  `ApplyPRObservation` evaluates independent actionable conditions; `sendOnce`
  checks worker state before sending and persists signatures. A crash between
  send and persistence can duplicate delivery. Its accounted-result abstraction
  can conflate already-sent or exhausted with handled; Company OS instead exposes
  those outcomes separately and requires reconciliation after uncertain delivery.
- [Activity states](https://github.com/Untrivial-ai/agent-orchestrator/blob/ab968d5e761469eb32c1b4dc780cde721a9998de/backend/internal/domain/activity.go):
  input and permission waits are sticky states, distinct from inactivity.
- [Lifecycle manager](https://github.com/Untrivial-ai/agent-orchestrator/blob/ab968d5e761469eb32c1b4dc780cde721a9998de/backend/internal/lifecycle/manager.go):
  launch generations guard delayed events and one controller owns session transitions.
- [Reaction guide](https://github.com/Untrivial-ai/agent-orchestrator/blob/ab968d5e761469eb32c1b4dc780cde721a9998de/frontend/src/landing/content/docs/guides/reactions.mdx):
  current implementation is lifecycle policy, not a generic configurable reaction
  recipe engine. We did not invent a `reactions:` configuration consumer.

## Validation and limits

Eighteen local fixture tests cover simultaneous conditions, persisted-history replay,
uncertain delivery, exhaustion, retry counts, worker states, stale revisions,
verified recurrence, duplicate/mutated events, and pending native IDs. They prove
planner decisions, not source evidence authenticity, live native messaging,
automated polling, or improved company outcomes. Existing host adapters must
provide fresh reads, serialized durable records, and verified sends.

Upstream source was selectively inspected at the pinned commit; its runtime and
test suite were not executed. A full clone failed for insufficient local disk
space, so the review used the GitHub tree and selected raw source files.

## Cybernetics and Details refinement

Run `AO-FEEDBACK-02`, improve mode. Baseline: Company OS `f5b7cfb`.
Boundary: the manager-to-owning-worker feedback loop, including shared repair
capacity and upstream dependencies. Company OS Web stores context; host tools
own messaging and durable state. No new management tier or scheduler is introduced.

Loaded and applied Cybernetics OS feedback-control and early-warning methods,
Details artifact/state review, and Software Architect OS contract/recovery methods
locally. This is self-review, not an independent specialist-agent evaluation.

| Requirement | Exact baseline weakness | Implemented refinement and falsifying test |
| --- | --- | --- |
| FB-FRESH | A reference labeled fresh had no age check | V2 requires observation time and allowed age in seconds; stale/future observations cannot produce a send. Test the exact age boundary. |
| FB-PROGRESS | An active worker could defer forever; delivery could conceal unresolved work | Fixed blocker deadline yields escalation/alert even when active or already delivered. Test the deadline boundary with both states. |
| FB-BUDGET | Only per-occurrence attempts were enforced | Shared program attempt count caps the entire batch; a new occurrence cannot reset it. Test three defects with one attempt remaining. |
| FB-DEPENDENCY | Conflict repair ignored upstream work | Readiness gate defers conflict repair while keeping CI/review actionable. Test blocked, unknown and released parent states. |
| FB-RECOVERY | Revision change took precedence over an uncertain send | Reconcile the old send first. Test uncertainty followed by a new revision. |

The dependency mechanism is grounded in upstream `prBlockedByOpenParent` in the
linked lifecycle reactions source. Upstream also resolves obsolete ready-to-merge
notifications in `readyToMergeResolutions`; Company OS should apply that to Web
projections when its event adapter is integrated. A stale notification must be
withdrawn from a fresh resource observation, not interpreted as standing approval.
This projection integration is a recommendation, not implemented here.

Chosen alternative: explicit host-supplied control envelope over inferred wall-clock
freshness or an imported background daemon. It preserves host authority and enables
repeatable tests, but cannot authenticate timestamps, budgets, ownership or source
state. Serialized reservations and reliable native readback remain host obligations.

Hypothesis: under identical stale, delayed, capacity-limited and dependency-blocked
inputs, the refined planner avoids inappropriate sends without suppressing unrelated
feedback. The regression scenarios test this finite-state claim, not controller
stability or business throughput. No historical operating trace was available;
there is no claimed calibrated simulation or historical backtest.

Next discriminating test: an authorized host shadow run capturing observation age
(seconds), unresolved blocker age (seconds), attempted deliveries (count), duplicate
sends (count), and verified repairs/remaining defects (counts, including unfinished
work). Compare the same events; stop on wrong-owner sends, permission bypass, budget
overrun or untracked delivery. No live benefit or unattended readiness is claimed.

Details verdict: local planner checks pass; the complete unattended feedback path
**Needs work** until durable host actuation and source-authenticated observation
are exercised. Review scope covers the helper, its tests and manager handoff;
upstream internals outside the cited files remain uninspected.
