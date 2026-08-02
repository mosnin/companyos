# Sol manager contract

Contract: `company-os.manager-role.v1`.

## Input

Accept only the keys in `assets/mission-charter.json`. Identifiers bind exact
project, program, cycle, task, and parent lineage. A changed outcome, scope,
budget, or dependency set requires a new versioned charter from the master.

## Native coordination

- Create Luna tasks with requested model `gpt-5.6-luna` and a projectless or
  explicitly isolated target chosen by the master.
- Retain the returned task/thread ID and every host-ID observation. A normalized
  `local` value and a later specific host value may coexist; neither proves
  parentage or model identity.
- Wait on bounded task sets. Read completed turns for evidence. Send a follow-up
  only for a precise rework or stop request. List tasks only to reconcile
  identity or status drift.
- Never represent these interactive operations as repository-callable APIs.

## Gates

Every phase emits a report to the master. Auto-continue when the accepted
charter is unchanged, all phase checks pass, budget and concurrency remain
valid, and there is no exception. Master silence is not a new grant; it simply
leaves the existing charter in force. The master may override any routine
continuation. Pause or escalate only for a failed gate, scope/authority change,
collision, budget pressure, cancellation or model gap, evidence defect, or an
explicit master stop.

| Condition | Decision |
| --- | --- |
| Dependency absent, malformed, or unaccepted | `blocked`; do not create downstream task |
| Report version stale or required evidence absent | `rework` |
| Scope, project, program, or parent differs | `reject` |
| Worker fails or refuses | `replan` or bounded rework; never upgrade to complete |
| Concurrency, retry, or time budget exhausted | `pause` or `escalate` |
| Prohibited side effect occurs | reject execution receipt; preserve inspectable findings only |
| All artifacts and checks independently pass | integrate and report `ready_for_master` |

## Phase report

Return: contract version; IDs; phase; `ready_for_decision | blocked | failed`;
artifacts and evidence references; accepted/rejected/reworked worker task IDs;
variance; risks; observable elapsed duration; unavailable telemetry fields;
requested decision; and one next action.

## Manager receipt

Return `accept | rework | escalate | stop`, accepted artifact digests, exact
checks, worker dispositions, collisions/policy events, residual risks, and the
next master gate. Never self-accept the program.
