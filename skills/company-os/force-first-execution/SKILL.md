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
7. After the terminal manager decision, seal the event log with
   [scripts/seal_force_snapshot.py](scripts/seal_force_snapshot.py). Bind
   integration evidence to the immutable snapshot receipt, never to a live log
   that can append later. Verify the snapshot again before integration.
8. Before worker dispatch, classify each promised release deliverable as
   `required` or `optional` in
   [assets/release-scope.v1.json](assets/release-scope.v1.json). Classification,
   manager ownership, manager public keys, and exact manager charters are
   immutable for the cycle. Sign the design decision and typed scope admission
   with the external RSA-3072 master key. Run `release_scope_controller.py
   admit` with the host-controlled public trust anchor and admission registry
   before dispatch; it create-only materializes the admission verification at
   the path already named in every admitted manager charter. Never place the
   trust anchor or registry under the project artifact root. A failed required
   deliverable blocks release. A failed
   optional enhancement becomes eligible for omission only after every
   predeclared recovery chain ends in a typed terminal rejection receipt. Never
   transfer a failed score to the released scope or create another recovery lane
   without a new master decision. Evaluate the result with
   [scripts/release_scope_controller.py](scripts/release_scope_controller.py)
   using its `evaluate` command and the same external trust inputs,
   using [assets/release-status.v1.json](assets/release-status.v1.json) for the
   exact accepted/rejected evidence envelope and
   [assets/release-deliverable-receipt.v1.json](assets/release-deliverable-receipt.v1.json)
   for each attempt chain. The controller returns eligibility; integration still
   requires an authenticated master scope decision.

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

Terminal logs are not integrated directly. `seal_force_snapshot.py seal`
creates a canonical JSONL snapshot and content-addressed receipt with
create-only, exact-replay-idempotent semantics. `verify` proves the contract, terminal sequence,
artifact set, snapshot bytes, and receipt again. Later writes to the live log
cannot change the accepted snapshot.

Graceful degradation is not a quality exception. Release scope is declared
before dispatch, bound to the external master design decision and admission,
and recorded in a host-controlled create-only version lineage. A changed scope
must advance exactly one definition version from the registered predecessor;
same-version replacement fails even if newly signed. The controller only
marks a reduced release eligible when every required deliverable is accepted,
every optional recovery chain has a typed rejected terminal force snapshot, and
the failed score and defects are retained. It never infers master acceptance.
Each manager signs its terminal receipt with the public key and exact charter
frozen into the admitted scope. Each terminal receipt also binds the exact force contract and the sealer
replays the underlying snapshot before the receipt is credited. Claimed release
artifacts must exactly equal the manager-inspected terminal candidate. The JSON assets
are templates: replace every zero digest and signature with values computed
from the exact bytes. Release-scope identity uses external RSA-3072 trust;
repository fixture authentication used by other role contracts is not release
authority. Final integration remains a separate authenticated master decision.
