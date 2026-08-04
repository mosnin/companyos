---
name: manage-company-program
description: Manage one bounded Company OS outcome through native Codex tasks. Use when a Sol manager must supervise Luna work, enforce gates, inspect evidence, rework defects, and integrate accepted artifacts.
---

# Manage Company Program

Operate contract version `company-os.manager-role.v2`. Receive a compact mission
charter; never require the root transcript or a repeated Company OS manual.

## Run the outcome

1. Validate the charter against [references/manager-contract.md](references/manager-contract.md).
   Verify local authorization digests and fixture signature. Fixture integrity
   is not live identity.
2. Freeze mandatory user requirements separately from recommendations. Bind
   each artifact to requirement IDs, acceptance authority, and capability
   classes. Resolve exact current host skills, then use
   `$assign-capability-skills` for governed external additions. Verify all
   bindings. Zero skills is valid only without specialized requirements.
   Otherwise stop with `E_REQUIRED_CAPABILITY_UNAVAILABLE`; never silently
   substitute an MVP or reference-only instructions.
3. Run the Program Preflight Compiler in
   [scripts/compile_program_preflight.py](scripts/compile_program_preflight.py)
   against semantics, host capabilities, and work definitions. Compile and
   `verify` from identical sources. Bind skills only to their exact packet.
   `ui_design` work must pass `$ui-design-quality`.
4. Before dispatch, acknowledge versions, IDs, outcome digest, references,
   requested model, permissions, budgets, reviews, barriers, and destination.
5. Decompose only after design acceptance and verified preflight. Give each Luna
   task one compact packet using `$execute-bounded-task` and its
   `assets/work-packet.json`; include its reference and digest, not a manual.
   Bind the accepted charter, parent destination, budget, and narrower authority.
   The manager's own input uses
   [assets/mission-charter.json](assets/mission-charter.json).
6. Before each worker launch, use `$force-first-execution` to create one
   force contract and event log. Set artifact, candidate, verification, receipt,
   and decision SLOs. Credit only artifacts and checks. On a soft miss, continue
   observable work or intervene once. Freeze required/optional scope and the
   optional recovery cap. After each decision, seal and verify the force log.
7. Use native Codex task creation, waiting, reading, listing, and messaging only
   from the interactive host. Repository code does not call those app tools.
8. Keep at most three Luna workers active, one task per worker, no worker child
   delegation, and one writer per ownership scope.
9. Inspect every artifact, check, scope, dependency, and receipt. Reject stale,
   weak, failed, refused, scope-drifted, cross-project, or side-effecting work.
   Resolve only exact versioned local references; reject absolute, escaped, or
   symlinked targets. Inspect UI under `$ui-design-quality`. Reconcile mandatory
   requirements and applied-capability receipts. Any omission is zero accepted
   throughput and returns `REWORK`.
10. Report upward at charter, discovery, design, execution, verification, and
   integration. Require authenticated master decisions at charter, design,
   verification, and integration. Never infer consent from silence. Only a
   routine execution subphase after accepted design and before verification may
   auto-continue while every bound constraint remains valid and visible.
11. Integrate only accepted worker artifacts and sealed force snapshots. An
   optional failure becomes eligible for omission only through the predeclared,
   design-bound graceful-degradation policy and typed terminal receipts;
   integration still waits for the authenticated master decision. Required
   failures block release. Escalate authority, cancellation, budget, model
   availability, or evidence gaps instead of widening the charter.

## Program preflight packet contract

Preflight is a dispatch gate. Semantics owns authority, evidence, oracles, and
capabilities; the host supplies runtimes and locators. Definitions bind evidence,
nonempty oracles, and disjoint writer scopes. Send only compiled slices. Verify
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

Return one manager receipt and one validated execution-efficiency receipt. The
master accepts the program unless the contract reserves acceptance to the user.
