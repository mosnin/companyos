# Codex-native task fabric

Contract: `company-os.codex-native-task-fabric.v2`.

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
   plus one `company-os.mission-charter.v2` asset referencing the accepted
   charter decision record.
2. Manager locally verifies the record's exact bindings, content digest,
   phase-evidence bytes, and repository-fixture signature, performs
   discovery, then submits the design/worker DAG. It waits only within the
   declared time budget for the authenticated master decision at design. Silence never
   grants the barrier; timeout escalates.
3. Manager gives each Luna task `$execute-bounded-task` plus one
   `company-os.work-packet.v2` asset carrying the exact parent charter,
   parent-available budget, canonical parent task destination, and inherited
   accepted-design decision record. Validate each packet against that parent:
   child scope, actions, tools, and all six budgets may only narrow. Workers
   never await the master and may not delegate.
4. Do not create a task whose dependencies are absent, malformed, foreign, or
   unaccepted. Use each manager cell's work-graph-derived direct-report and
   worker-slot capacity, while the global admission controller independently
   bounds how many managers and workers may be active. Capacity is not
   concurrency and there is no fixed cross-program team ratio.
5. Wait and read bounded task sets. Inspect artifacts and checks directly.
6. Reject or rework stale reports, changed scopes, failed/refused tasks,
   project contamination, policy side effects, and budget pressure.
7. Keep every phase and routine execution subphase visible. After accepted
   design and before verification, routine execution subphases may
   auto-continue only under the
   unchanged charter when checks, budgets, concurrency, and authority all pass.
   Require authenticated verification before integration and authenticated
   final acceptance after integration. Integrate only accepted receipts.

## Evidence fields

Record project/program/cycle/task/parent IDs, role, requested model,
observed-model status/source, task/thread ID, all raw host-ID observations,
current status, created/started order, optional terminal status/order, elapsed
duration when exposed, artifact paths/digests, oracle results,
rejections/rework, and final disposition. `active` is never terminal. An
accepted task requires native identity plus ordered create, start, and terminal
events. Open active intervals count toward concurrency until terminal evidence
arrives.

Deterministic fixtures may never claim an observed model. Native model identity
is accepted only from the explicit host-observation source classes enumerated
by the validator; requested model, charter, packet, or prompt text is never an
observation source.

Canonical writer scopes are lowercase ASCII project-relative POSIX paths.
Reject case, Unicode, absolute, backslash, empty-segment, dot-segment, and
parent-segment ambiguity. Equal or ancestor/descendant writer scopes overlap.
Apply overlap checks independently to manager peers and worker peers.

All native contract references are versioned, project-local paths under a
caller-authorized local repository root. Reject absolute/backslash/dot/escape
or symlink paths, missing files, mutable names, foreign project bindings, and
hashes that do not match exact bytes. Authorization records use canonical JSON
digests plus a public repository-fixture HMAC and bind the accepted decision to
the exact contract, parent, phase evidence, and decider. That offline fixture
check is not live identity authentication; the runtime remains NO-GO for live
authorization.

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
