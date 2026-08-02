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
  `company-os.mission-charter.v2` asset.
- Manager invokes `$execute-bounded-task` with one
  `company-os.work-packet.v2` asset per task requested as `gpt-5.6-luna`.
- Prompts contain only the skill invocation plus the compact charter/packet.
  Stable operating policy lives in the versioned skills.
- Manager emits every visible phase and routine execution subphase report.
  Charter, design,
  verification, and final integration require an authenticated master decision
  bound to the current program/definition versions, outcome digest, and phase
  evidence. Silence never grants a barrier; timeout escalates. Only routine
  execution subphases after accepted design and before verification may
  auto-continue while the charter is unchanged and all checks, budgets,
  concurrency, and authority conditions pass. The master may override.
- Workers cannot delegate, self-accept, widen scope, deploy, publish, message
  externally, or mutate during a read-only task.
- The manager charter carries attributable authenticated charter authorization.
  Each worker packet carries attributable inherited accepted-design evidence;
  it is not a worker-owned wait condition. Workers never await the master and
  return only to the manager destination.

## Compact v2 inputs

The exact source assets carry charter/packet, program, and definition versions;
project/program/cycle/task/parent IDs; outcome plus SHA-256; requested model;
attributable phase authorization with definition, evidence, and authentication
digests; versioned SHA-256-bound architecture,
roadmap, and interface references; task-local artifact paths; canonical scope;
allowed actions/tools and prohibitions; dependencies; deliverables; objective
oracle/checks and independent-review requirements; decision policy; token,
cost, time, task, concurrency, and retry caps; stop/escalation rules; and one
reporting destination. Dispatched values may reference content-addressed
artifacts but may not embed transcripts or global context.
The authorization definition digest binds canonical sorted compact JSON for
every top-level field except `authorization`; post-decision mutation fails.

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

Fixtures never claim observed model. A native observed model requires a
validator-recognized `host_observation:<tool>:model` source; requested model,
charter, packet, and prompt are untrusted for observation.

Task evidence uses `current_status`, `created_order`, `started_order`, optional
`terminal_status`, and optional `terminal_order`. Active is never terminal.
Accepted work requires native identity and ordered create/start/terminal
events. Open active intervals remain in concurrency accounting.

## Reconciliation

Do not create downstream work until every dependency artifact passes its
objective oracle. Reject stale reports, scope drift, foreign project bindings,
failed/refused workers, prohibited side effects, and budget/concurrency
pressure. A failed worker may leave inspectable source findings; the manager
must verify them independently and may not upgrade the receipt to complete.

Writer scopes are lowercase ASCII project-relative POSIX paths. Case, Unicode,
absolute/backslash/dot-segment ambiguity and equal or ancestor/descendant
overlap fail closed.

Read-only checks set `PYTHONDONTWRITEBYTECODE=1` or use a disposable copy.
Tracked Git cleanliness is insufficient when ignored artifacts changed.

## Acceptance and no-go

The deterministic five-scenario ladder and focused tests may accept this
contract/schema correction. They do not prove installed role-skill discovery,
fresh-thread behavior, controller admission-before-create, token/cost telemetry,
or hard cancellation. The broader autonomous runtime remains NO-GO until those
gates pass without enabling scheduling or external providers.
