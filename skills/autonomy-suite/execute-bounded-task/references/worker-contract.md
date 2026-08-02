# Luna worker contract

Contract: `company-os.worker-role.v1`.

## Input boundary

Accept only the keys in `assets/work-packet.json`. Reject missing identifiers,
foreign project/program/cycle bindings, an unaccepted dependency, a scope that
exceeds the packet, a non-Luna requested model, or a budget above concurrency
one and retry one.

## Side-effect rule

Read-only means no creation, deletion, cleanup, formatting, cache generation,
lock update, or ignored artifact. Use bytecode-disabled commands or a disposable
copy. If an unintended side effect occurs, stop; name every observed path; do
not call the task clean because tracked Git status is clean.

## Receipt

Return:

- contract version and all input IDs;
- `complete | blocked | failed | refused`;
- requested model and observed model with evidence status;
- native task/thread and host observations when exposed;
- exact artifact paths and content digests;
- checks and results;
- dependency, scope, and prohibition compliance;
- elapsed duration when observable;
- tokens, cost, and cancellation acknowledgement independently marked
  `observed | unavailable`;
- assumptions, side effects, unresolved risks, and one recommended next action.

`complete` means the packet deliverable and oracle passed. It does not mean the
manager or master accepted it. A failed or refused receipt may retain source
findings that the manager can independently verify, but it may never be silently
rewritten as complete.
