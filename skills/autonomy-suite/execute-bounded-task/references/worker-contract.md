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

The packet references the exact byte-digested accepted parent manager charter
and a versioned project-local `company-os.authorization-decision.v1` record for
the master-accepted design. Recompute the record's canonical SHA-256, exact
phase-evidence byte digest, and `company-os.fixture-hmac-sha256.v1` signature.
Require `accepted` plus `continue` and exact project/program/version,
cycle/task/parent, parent-definition, worker-definition/outcome/model, phase,
decision, and decider bindings. Reject arbitrary hashes, stale parent digests,
cross-manager replay, and any substituted program, phase, definition, outcome,
or decider. This proves only deterministic repository-fixture integrity, not
live identity authentication. The definition digest excludes only the
authorization reference, so post-decision mutation fails. The design record is
inherited authority, not a worker-owned wait condition. The worker never
contacts or awaits the master; it returns only to the canonical
`task:<parent_manager_task_id>` destination. Here `ids.parent_task_id` is the
Company OS mission parent and must equal the accepted parent charter's mission
task ID; `parent_manager_task_id` is the separately bound native Codex task ID
observed in the accepted design record. Host identity never substitutes for
mission lineage.

Load and validate the parent charter before accepting the packet. Every owned
scope must equal or descend from a parent scope; allowed actions and tools must
be subsets; parent prohibitions must remain; and token, cost, time, task,
concurrency, and retry caps must not exceed the signed parent-available
allocation or the parent charter. Reject cross-project identity or paths.

Owned scopes are lowercase ASCII project-relative POSIX paths. Reject case,
Unicode, absolute/backslash/dot-segment ambiguity, and equal or
ancestor/descendant writer overlap rather than normalizing aliases.

Resolve architecture, roadmap, interface, authorization, phase-evidence, and
parent-charter references only from versioned paths beneath an allowed local
repository root and the exact project namespace. Reject absolute paths,
backslashes, dot segments, escapes, symlinks, missing files, mutable names, and
digests that do not match exact bytes. Never expose file contents in errors.

## Side-effect rule

When a compiled packet declares `work_domains: ["ui_design"]`, it must retain
the parent manager's `ui_design` domain and `ui_design_quality` capability.
Load `$ui-design-quality` before UI work and return the exact runnable,
responsive, accessibility, interaction, motion, and visual evidence its
acceptance barrier requires. Missing classification or capability is not
permission to proceed.

Read-only means no creation, deletion, cleanup, formatting, cache generation,
lock update, or ignored artifact. Use bytecode-disabled commands or a disposable
copy. If an unintended side effect occurs, stop; name every observed path; do
not call the task clean because tracked Git status is clean.

## Receipt

When the packet includes a force contract in its task-local artifact paths,
validate and follow it through `$force-first-execution`. The manager owns the
event log. Report exact materialization, candidate, check, and receipt evidence
to the manager; do not share-write the control record. Soft SLO misses remain
performance variance and do not authorize a scope, safety, or budget breach.

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
