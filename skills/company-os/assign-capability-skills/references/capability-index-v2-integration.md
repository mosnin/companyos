# Capability Index v2 Integration Contract

Status: feature-off executable contract. It may validate architecture and
fixtures, but it cannot select a live task until the controller binds a v2
catalog snapshot and typed task record.

## Why it exists

V1 safely binds manager-selected capability IDs. It does not prove the manager
found every required capability, chose the smallest sufficient bundle, closed
dependencies and companion resources, or avoided a semantic tie. V2 moves that
decision into a deterministic service while preserving one Company OS
controller.

## Required flow

1. Compile the accepted task and artifact plan into typed coverage atoms:
   domain, artifact production, artifact review, named technology, lifecycle,
   intent, and independent reviewer capability.
2. Retrieve matching metadata exhaustively. Never apply a top-N limit before
   eligibility and bundle construction.
3. Reject role, trigger, trust, license, provenance, freshness, evaluation,
   prerequisite, permission, network, host, egress, sensitivity, side-effect,
   resource-closure, and controller conflicts as hard gates.
4. Expand transitive capability and resource dependencies. Cycles fail closed.
5. Enumerate exact sufficient bundles within skill, byte, and deterministic
   context-cost limits.
6. Rank smallest closed bundle first, then bytes, context cost, weakest trust,
   weakest evaluation, freshness margin, prerequisite count, and structured
   trigger specificity.
7. A semantic tie or high/critical-risk task requires a named manager decision.
   Capability ID is never a semantic tiebreaker.
8. Bind one decision receipt, lazy-load only selected closed resources, and
   verify applied capability evidence separately from artifact acceptance.

## Non-negotiable boundaries

- Skills remain advisory capability packages, never controllers.
- Vendor hooks, agent spawning, scheduling, approval, global configuration,
  deploy, spend, contact, service start, and publish behavior are ineligible
  without separate authority.
- Descriptions and popularity do not satisfy typed coverage.
- Selection is not evidence that the deliverable works.
- Context accounting uses exact UTF-8 bytes with `ceil(bytes / 4)` as a stable
  cost unit. It is not a model-token claim.

## Acceptance gate

Before activation, the integration must compile the existing audited catalog
into exact v2 rows, bind task records from Program Preflight, produce canonical
selection/rejection receipts, and pass the full N01-N42 negative suite. The
current executable oracle covers the highest-risk closure, tie, drift, and
authority invariants; deferred fixtures are not production evidence.
