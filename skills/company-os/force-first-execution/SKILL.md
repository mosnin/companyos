---
name: force-first-execution
description: Drive a bounded Company OS task from accepted outcome to materialized artifact, runnable candidate, verified evidence, and a prompt decision. Use when a Sol manager supervises Luna work and must prevent planning, narration, or receipt ceremony from replacing real delivery.
---

# Force-First Execution

Use this skill after a program direction and design are accepted. It does not
replace authority, scope, safety, or quality gates. It makes useful work flow
through them.

## Run the force loop

1. Create one manager-owned force contract from
   [assets/force-contract.v1.json](assets/force-contract.v1.json). Set explicit
   soft SLOs for first artifact, runnable candidate, verification, and the short
   acceptance-to-receipt and receipt-to-decision transitions.
   Put its project-relative path in the worker packet's existing
   `task_local_context.artifact_paths`; this does not change packet authority.
2. Keep the force event log manager-owned. Workers report compact observations;
   they never share-write the manager log. Credit only events backed by an
   artifact path and digest, a runnable candidate, a check result, direct
   inspection, a receipt, or a decision. Commentary and repeated planning earn
   no progress credit.
3. Evaluate the contract and JSONL log with
   [scripts/force_loop_controller.py](scripts/force_loop_controller.py) at each
   checkpoint, always passing the exact project `--artifact-root`. Materialized
   and receipt paths are immutable, versioned evidence paths; the controller
   rejects missing, symlinked, digest-mismatched, unmaterialized, or partially
   inspected candidate bytes. Follow its single `next_action`; do not reopen
   discovery when the accepted outcome and scope are unchanged.
   Use [assets/force-events.example.jsonl](assets/force-events.example.jsonl) as
   the initial log shape and [schemas/force-contract.schema.json](schemas/force-contract.schema.json)
   for editor/schema validation.
4. Treat authority loss, cancellation, scope violation, collision, prohibited
   side effects, and exhausted hard budgets as hard stops. Treat missed delivery
   SLOs as scored performance variance. A soft miss cannot silently discard
   useful work or weaken a hard stop.
5. On a soft miss, continue only when a fresh, observable operation is in
   flight. Otherwise send one precise intervention naming the missing artifact
   or check. If late output arrives, quarantine it, inspect it independently,
   and record `late_output_reviewed` before using it in a candidate. Accept,
   rework, or reject it on quality—not punctuality alone.
6. Once verification and manager inspection pass, freeze renewed analysis and
   materialize the receipt immediately. Once the receipt verifies, make the
   manager decision immediately. Preserve first-pass failure and every rework;
   never rewrite history to make the final score look cleaner.

## Evidence sequence

The normal sequence is:

`task_started -> artifact_materialized -> candidate_runnable -> verification_passed -> manager_inspection_passed -> receipt_materialized -> manager_accept`

Exact rework is represented by `manager_inspection_failed -> rework_started`,
followed by fresh materialization, verification, and inspection events. See
[references/force-contract.md](references/force-contract.md) for event evidence
requirements and state transitions.

## What to measure

- time to first materialized artifact;
- time to runnable candidate;
- time to verification and direct inspection;
- acceptance-to-receipt and receipt-to-decision latency;
- first-pass acceptance, rework count, and manager interventions;
- collisions, hard stops, and soft SLO variance;
- accepted customer-facing output, not task activity.

This skill is used by `$manage-company-program` and `$execute-bounded-task`.
The manager owns control and acceptance; the worker owns only its bounded
deliverable scope.
