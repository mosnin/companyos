# Luna worker contract

Contract: `company-os.worker-role.v2`.

## Input boundary

Accept only the keys in `assets/work-packet.json`. Require exact packet,
program, and definition versions; an outcome digest; versioned SHA-256-bound
architecture, roadmap, and interface references; requested model; allowed
actions/tools; prohibitions; all six budgets; independent-review requirements;
and the accepted design-decision data. Reject missing identifiers, foreign
project/program/cycle bindings, an unaccepted dependency, a scope that exceeds
the packet, a non-Luna requested model, or a budget above one task,
concurrency one, and retry one.

The packet's `authorization` is attributable evidence of the manager's already
accepted master design decision. Its decision, decider, definition, evidence,
and authentication digests must be populated before dispatch. The definition
digest is SHA-256 over canonical sorted compact JSON for every top-level field
except `authorization`, so post-decision mutation fails. It is inherited
authority, not a worker-owned wait condition. The worker never contacts or
awaits the master; it returns its receipt to the manager, and the manager owns
the later verification barrier.

Owned scopes are lowercase ASCII project-relative POSIX paths. Reject case,
Unicode, absolute/backslash/dot-segment ambiguity, and equal or
ancestor/descendant writer overlap rather than normalizing aliases.

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
