# Codex-native task fabric

Contract: `company-os.codex-native-task-fabric.v1`.

## Authority and runtime

The native hierarchy is master Sol task → Sol manager task → Luna worker task.
Codex tasks are peers in the app, so lineage comes from Company OS mission IDs
and explicit parent IDs, never from host ID or sidebar position. The host may
expose a task/thread ID, host ID, status, timestamps, and elapsed duration.
Requested model is admission intent; observed model is unavailable unless a
separate trusted field is actually returned.

Interactive coordination uses native task creation, bounded waits, reads,
follow-up messages, and list reconciliation. Repository code validates exported
records only and must not claim it can call app task tools.

## Dispatch playbook

1. Master versions the program and gives a manager `$manage-company-program`
   plus one `company-os.mission-charter.v1` asset.
2. Manager acknowledges the charter and submits its design/worker DAG. It
   reports the phase upward and auto-continues only when the charter is
   unchanged, every phase check passes, budgets remain valid, and no exception
   exists; the master may override.
3. Manager gives each Luna task `$execute-bounded-task` plus one
   `company-os.work-packet.v1` asset. Workers may not delegate.
4. Do not create a task whose dependencies are absent, malformed, foreign, or
   unaccepted. Keep concurrency at three workers per manager and six globally.
5. Wait and read bounded task sets. Inspect artifacts and checks directly.
6. Reject or rework stale reports, changed scopes, failed/refused tasks,
   project contamination, policy side effects, and budget pressure.
7. Report every phase barrier. Integrate only accepted receipts, then request
   master acceptance.

## Evidence fields

Record project/program/cycle/task/parent IDs, role, requested model,
observed-model status/source, task/thread ID, all raw host-ID observations,
start/terminal status and timestamps, elapsed duration when exposed, artifact
paths/digests, oracle results, rejections/rework, and final disposition.

Track tokens, cost, cancellation acknowledgement, and observed model as
independent fields. One available metric never fills another. A follow-up stop
request is cooperative intent; the current accepted surface has no proven hard
interrupt or cancellation acknowledgement.

## Side-effect-free verification

Read-only workers and validators must use `PYTHONDONTWRITEBYTECODE=1` or an
isolated temporary copy. Inspect ignored artifacts before and after. If a
worker creates then cleans generated files, reject the execution receipt even
when tracked Git status is clean; retain only independently verified findings.

Validate deterministic simulation exports with:

`python3 scripts/validate_codex_native_fabric.py path/to/simulation.json`

This validator exercises evidence rules; it does not invoke native task tools.
