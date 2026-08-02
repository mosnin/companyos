# Phase 2 Codex-native task fabric contract

Status: `LOCALLY_VALIDATED_CORRECTION / HOST_OPERATED / SCHEDULER_OFF /
BROADER_AUTONOMOUS_RUNTIME_NO_GO`.

## Outcome

Use the Codex task runtime itself as Company OS execution:

`master GPT-5.6 Sol task → Sol manager task → GPT-5.6 Luna worker tasks`

The interactive host creates, waits on, reads, lists, and messages tasks.
Repository code validates exported contracts and evidence only; it does not call
Codex app tools. Existing provider gateway, lifecycle, and Responses fixtures
remain historical regression evidence, not current execution direction.

## Role protocol

- Master invokes `$manage-company-program` with one
  `company-os.mission-charter.v1` asset.
- Manager invokes `$execute-bounded-task` with one
  `company-os.work-packet.v1` asset per Luna task.
- Prompts contain only the skill invocation plus the compact charter/packet.
  Stable operating policy lives in the versioned skills.
- Manager emits every phase report. It auto-continues only while the accepted
  charter is unchanged, all checks pass, budgets remain valid, and no exception
  exists. The master may override at any phase.
- Workers cannot delegate, self-accept, widen scope, deploy, publish, message
  externally, or mutate during a read-only task.

## Identity and evidence

Company OS mission IDs establish project/program/cycle/task lineage. Native
task/thread ID identifies one Codex task. Host ID identifies coordination
location and may have normalized and specific representations; it never proves
lineage or model identity.

Record requested and observed models separately. This slice requested
`gpt-5.6-luna` for both workers, while the later wait/read/list evidence exposed
no observed-model field. Record observed model as unavailable. Elapsed duration
was exposed independently. Tokens, cost, cancellation acknowledgement, and a
hard interrupt remain unavailable.

## Reconciliation

Do not create downstream work until every dependency artifact passes its
objective oracle. Reject stale reports, scope drift, foreign project bindings,
failed/refused workers, prohibited side effects, and budget/concurrency
pressure. A failed worker may leave inspectable source findings; the manager
must verify them independently and may not upgrade the receipt to complete.

Read-only checks set `PYTHONDONTWRITEBYTECODE=1` or use a disposable copy.
Tracked Git cleanliness is insufficient when ignored artifacts changed.

## Acceptance and no-go

The deterministic five-scenario ladder and focused tests may accept this
contract/schema correction. They do not prove installed role-skill discovery,
fresh-thread behavior, controller admission-before-create, token/cost telemetry,
or hard cancellation. The broader autonomous runtime remains NO-GO until those
gates pass without enabling scheduling or external providers.
