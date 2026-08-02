---
name: manage-company-program
description: Manage one bounded Company OS program outcome through native Codex tasks. Use when a GPT-5.6 Sol manager must decompose an accepted charter, create and supervise GPT-5.6 Luna work, enforce phase and budget gates, inspect evidence, reject or rework weak receipts, integrate accepted artifacts, or escalate a blocked outcome.
---

# Manage Company Program

Operate contract version `company-os.manager-role.v2`. Receive a compact mission
charter; never require the root transcript or a repeated Company OS manual.

## Run the outcome

1. Validate the charter against [references/manager-contract.md](references/manager-contract.md).
   Its attributable authorization is the initial charter decision; validate it
   and do not create a second charter wait.
2. Acknowledge the exact contract/program/definition versions, IDs, outcome
   digest, content-addressed architecture/roadmap/interface references,
   requested model, permissions, budgets, review requirements, barriers, and
   reporting destination before dispatch.
3. Decompose only after the design barrier. Give each Luna task one compact
   work packet using `$execute-bounded-task` and that skill's
   `assets/work-packet.json`. The manager's own input uses
   [assets/mission-charter.json](assets/mission-charter.json).
4. Use native Codex task creation, waiting, reading, listing, and messaging only
   from the interactive host. Repository code does not call those app tools.
5. Keep at most three Luna workers active, one task per worker, no worker child
   delegation, and one writer per ownership scope.
6. Inspect every artifact, check, scope, dependency, and receipt. Reject stale,
   weak, failed, refused, scope-drifted, cross-project, or side-effecting work.
7. Report upward at charter, discovery, design, execution, verification, and
   integration. Require an authenticated master decision at the charter,
   design, verification, and final-integration barriers. Never infer that
   decision from silence; escalate when the barrier wait reaches its time
   budget. Auto-continue only routine execution subphases after accepted design
   and before verification when the accepted charter is unchanged, every check
   passes, budget/concurrency/authority remain valid, and no exception exists.
   Every subphase stays visible and the master may override.
8. Integrate only accepted worker artifacts. Escalate authority, cancellation,
   budget, model availability, or evidence gaps instead of widening the charter.

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
