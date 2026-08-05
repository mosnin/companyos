# Phase 2 Provider Surface Discovery

## Verdict

`CALLABLE_LUNA_REQUEST / MODEL_IDENTITY_UNPROVEN / NO_GO`

On 2026-08-01, the installed `codex-cli 0.145.0` successfully completed one
ephemeral, read-only probe requested with `-m gpt-5.6-luna`. The isolated task
returned exactly `READY`, made no tool call, and changed no project file.

This proves that the locally authenticated CLI accepts the requested Luna model
and can return usage telemetry. It does **not** prove the provider-resolved
model identity: the CLI JSONL surface emitted `thread.started`, `turn.started`,
`item.completed`, and `turn.completed`, but no event contained a model field.
Company OS must not convert the requested command-line model into
`observed_model` evidence.

## Observed telemetry

- Input tokens: 13,714
- Cached input tokens: 8,960
- Cache-write input tokens: 0
- Output tokens: 5
- Reasoning output tokens: 0
- Final text: `READY`
- External effects: none
- Project writes: none

The unexpectedly large input for a five-token answer is also direct evidence
that the future gateway must measure total provider usage and reduce inherited
context for Luna workers. A cheap model alone does not make a wasteful task
envelope efficient.

## Connector consequence

The protected connector may use this CLI only if an authenticated upstream
record exposes the provider-resolved model and can be bound into the signed
gateway envelope. Otherwise, the connector must use a provider/API response
that returns the resolved model identity. Until then, a successful CLI process
may be recorded only as requested-model discovery—not a verified Luna run.

The production gate remains unchanged: no receipt, reconciliation, manager
credit, quality score, scheduler activation, or Chippy onboarding may claim
Luna execution without exact provider/model evidence.
