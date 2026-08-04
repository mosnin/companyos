---
name: manage-company-program
description: Manage one bounded Company OS outcome through native Codex tasks. Use when a Sol manager must supervise Luna work, enforce gates, inspect evidence, rework defects, and integrate accepted artifacts.
---

# Manage Company Program

Operate contract version `company-os.manager-role.v2`. Receive a compact mission
charter; never require the root transcript or a repeated Company OS manual.

## Run the outcome

1. Validate the charter against [references/manager-contract.md](references/manager-contract.md).
   Verify its project-local authorization digests and repository-fixture
   signature without creating a duplicate charter wait. This proves fixture
   integrity, not live identity.
2. Before design or dispatch, run the Program Preflight Compiler in
   [scripts/compile_program_preflight.py](scripts/compile_program_preflight.py)
   against program semantics, host capabilities, and bounded work definitions.
   Compile, then `verify` with the same three sources before dispatch or tool
   use. Keep their digests in the receipt; dispatch by packet reference.
   `ui_design` work must pass `$ui-design-quality` classification and capability checks.
3. Before dispatch, acknowledge versions, IDs, outcome digest, references,
   requested model, permissions, budgets, reviews, barriers, and destination.
4. Decompose only after design acceptance and verified preflight. Give each Luna
   task one compact packet using `$execute-bounded-task` and its
   `assets/work-packet.json`; include the compiled packet reference and digest,
   not a pasted manual. Bind it to this exact accepted manager charter,
   parent task destination, available budget, and narrower scope/permissions.
   The manager's own input uses
   [assets/mission-charter.json](assets/mission-charter.json).
5. Before each worker launch, use `$force-first-execution` to create one
   manager-owned force contract and event log. This is an execution control,
   not an approval barrier. Set materialization, candidate, verification,
   receipt, and decision SLOs. Credit only artifacts and checks. On a soft miss,
   continue fresh observable work or send one precise intervention. After
   verification and inspection, write the receipt; after it verifies, decide.
   At design time, also freeze required versus optional release scope and the
   optional recovery-chain cap. After each terminal decision, seal and verify
   the immutable force-log snapshot before integration.
6. Use native Codex task creation, waiting, reading, listing, and messaging only
   from the interactive host. Repository code does not call those app tools.
7. Keep at most three Luna workers active, one task per worker, no worker child
   delegation, and one writer per ownership scope.
8. Inspect every artifact, check, scope, dependency, and receipt. Reject stale,
   weak, failed, refused, scope-drifted, cross-project, or side-effecting work.
   Resolve references only from versioned project-local repository paths and
   verify exact bytes; never read an absolute, escaped, or symlinked target.
   Independently inspect UI work under `$ui-design-quality`.
9. Report upward at charter, discovery, design, execution, verification, and
   integration. Require authenticated master decisions at charter, design,
   verification, and final integration. Never infer consent from silence.
   Only routine execution subphases after accepted design and before verification
   may auto-continue while charter, checks, budget, concurrency, and authority
   remain valid. Every subphase stays visible.
10. Integrate only accepted worker artifacts and sealed force snapshots. An
   optional failure becomes eligible for omission only through the predeclared,
   design-bound graceful-degradation policy and typed terminal receipts;
   integration still waits for the authenticated master decision. Required
   failures block release. Escalate authority, cancellation, budget, model
   availability, or evidence gaps instead of widening the charter.

## Program preflight packet contract

The compiler is a dispatch safety gate. Semantics owns terms, constants,
authority, prohibitions, evidence, oracles, and capabilities. The host provides
available runtimes and locators. Definitions bind the semantics, cite evidence,
attach a nonempty oracle, and use disjoint project-relative writer scopes.

The manager receives the compiled manifest and its manager packet reference.
Each Luna task receives only its packet reference, parent digest, scope,
authority, deliverables, oracle, evidence, and capability slice. Rerun `verify`
after transport; mutation, extras, stale parents, or unbound digests stop.

## Preserve truth

- Record task/thread ID and host observations only when the native host exposes
  them. Host ID is coordination metadata, not lineage.
- Record `requested_model` separately from `observed_model`; unavailable stays
  unavailable.
- Record elapsed duration when exposed. Keep tokens, cost, and cancellation
  acknowledgement unavailable when the host does not expose them.
- Treat a task stop message as cooperative intent, not a proven hard interrupt.
- Run read-only checks with `PYTHONDONTWRITEBYTECODE=1` or in an isolated
  temporary copy. A clean tracked status does not erase ignored side effects.

Return one manager receipt using the exact schema in the contract reference.
The master, not the manager, accepts the program outcome.
