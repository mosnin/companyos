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

Ten local fixture tests cover simultaneous conditions, persisted-history replay,
uncertain delivery, exhaustion, retry counts, worker states, stale revisions,
verified recurrence, duplicate/mutated events, and pending native IDs. They prove
planner decisions, not source evidence authenticity, live native messaging,
automated polling, or improved company outcomes. Existing host adapters must
provide fresh reads, serialized durable records, and verified sends.

Upstream source was selectively inspected at the pinned commit; its runtime and
test suite were not executed. A full clone failed for insufficient local disk
space, so the review used the GitHub tree and selected raw source files.
