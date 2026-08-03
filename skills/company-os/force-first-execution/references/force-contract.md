# Force contract v1

The contract is manager-owned and task-local. It adds flow control to an
already authorized work packet; it never expands authority or scope.

## Contract rules

- `started_at_epoch` is the observed task launch epoch.
- All SLOs are positive integer seconds. They are performance objectives, not
  safety authority.
- `event_log_owner` is exactly `manager`; workers report observations rather
  than sharing the control file.
- `max_rework_cycles` is bounded from zero through three.
- Hard-stop codes are explicit. A manager may add a narrower project-specific
  code, but it may not omit the six baseline safety codes in the example.

## Event envelope

Each JSONL line has exactly:

```json
{"schema":"company-os.force-event.v1","sequence":1,"task_id":"example-worker-1","event":"task_started","at_epoch":0,"evidence":{}}
```

Sequence numbers are contiguous and timestamps never move backward. Supported
events and required evidence are:

| Event | Required evidence |
| --- | --- |
| `task_started` | empty object |
| `inflight_observed` | non-empty `operation` |
| `intervention_sent` | non-empty `missing` material checkpoint |
| `artifact_materialized` | safe project-relative `path`, SHA-256 `sha256` |
| `late_output_reviewed` | non-empty `artifact_paths`, `accept`, `rework`, or `reject` decision |
| `candidate_runnable` | non-empty project-relative `artifact_paths` |
| `verification_passed` | non-empty `check` |
| `manager_inspection_passed` | non-empty `artifact_paths` |
| `manager_inspection_failed` | non-empty `defects` |
| `rework_started` | non-empty `defects` |
| `receipt_materialized` | safe project-relative `path`, SHA-256 `sha256` |
| `manager_accept` | empty object |
| `manager_rework` | non-empty `defects` |
| `manager_reject` | non-empty `reason` |
| `hard_stop` | declared `code`, non-empty `detail` |

An acceptance or receipt must follow fresh verification and inspection after
the latest rework. Every cycle requires fresh materialization and a candidate
before verification. Candidate paths must be current-cycle materialized files;
inspection must cover that exact candidate. Milestones are monotonic: a new
artifact invalidates the candidate and all downstream proof; a new candidate
invalidates verification, inspection, and receipt; new verification invalidates
inspection and receipt. Once a receipt exists, only a manager decision or hard
stop may follow. A manager rework decision opens a fresh bounded rework cycle;
no stale milestone can carry forward. Materialized and receipt paths are
immutable across the event log and their recorded digests must match regular,
non-symlinked bytes under the required `--artifact-root`. Events after a
terminal manager decision are invalid.

## Controller actions

- `materialize_first_artifact` and `produce_runnable_candidate` keep work moving.
- `continue_bounded_grace` is allowed only with a fresh observable in-flight
  operation.
- `quarantine_and_inspect_late_output` prevents a late artifact from entering a
  candidate until the manager records its quality decision.
- `send_precise_intervention` names a missed material checkpoint without
  reopening the plan.
- `verify_candidate` and `manager_inspect_now` move through quality proof.
- `exact_rework` is bounded to named defects and the remaining retry budget.
- `materialize_receipt_now` and `manager_decide_now` compress completed work;
  renewed analysis is not a valid transition.
- `stop_and_report` is reserved for hard-stop evidence.

Soft SLO misses remain in the output metrics even when later work is accepted.
First-pass failure remains false after successful rework.
