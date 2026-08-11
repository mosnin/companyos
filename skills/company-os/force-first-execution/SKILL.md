---
name: force-first-execution
description: Drive a bounded Company OS task from objective to materialized artifact, runnable candidate, observed behavior, verified evidence, and prompt decision. Use when a Sol manager supervises Luna work and must prevent planning, research, documentation, or receipt ceremony from replacing real delivery.
---

# Force-First Execution

Use this skill as soon as the objective is concrete enough to attempt a **bounded reversible real-artifact slice**. A complete product design is not a prerequisite for local source edits, builds, tests, browser/simulator runs, disposable services, or sandbox execution.

This skill does not weaken authority. It distinguishes low-consequence learning-by-doing from customer-facing, financial, privileged, irreversible, destructive, or production-impacting effects that still require explicit authority.

## First reality sequence

The preferred sequence is:

`task_started -> artifact_materialized -> candidate_runnable -> behavior_observed -> verification_passed -> manager_inspection_passed -> receipt_materialized -> manager_decision`

A plan, architecture, schema, fixture corpus, benchmark policy, test suite, manager report, or audit is not a substitute for `artifact_materialized`, `candidate_runnable`, or `behavior_observed` unless that item is itself the requested artifact.

## Run the force loop

1. Create one manager-owned force contract from [assets/force-contract.v1.json](assets/force-contract.v1.json). Set explicit soft SLOs for first artifact, runnable candidate, direct observation, verification, receipt, and decision.
2. For a build mission, target a connected real-artifact path before roughly 25% of the mission budget is consumed. Within each implementation lane, target first runnable bytes inside the first third of the lane budget.
3. Keep the force event log manager-owned. Workers report compact observations; they never share-write the manager log. Credit only events backed by artifact paths/digests, runnable candidates, runtime/browser/API observations, check results, receipts, or decisions. Commentary and repeated planning earn no progress credit.
4. Evaluate the force contract and JSONL log with [scripts/force_loop_controller.py](scripts/force_loop_controller.py) at each checkpoint. Follow its single next action. Do not reopen broad discovery when the existing scope is sufficiently known to execute.
5. If an artifact does not exist by its SLO, intervene on the missing artifact. Do **not** respond by requesting another general plan, research report, architecture packet, or audit unless a concrete blocker proves that information is necessary.
6. If the candidate does not run, move directly into runtime diagnosis and repair. Runtime failure is higher-value evidence than speculative architecture review.
7. On a soft miss, continue only when a fresh observable operation is in flight. Otherwise send one precise intervention naming the missing artifact or runtime check. Preserve late output and inspect it independently before use.
8. Once verification and manager inspection pass, materialize the receipt and make the manager decision promptly. Preserve first-pass failure and rework history; never rewrite history to improve the score.
9. Checkpoint or commit accepted product bytes promptly. Product durability has priority over committing only governance metadata.

## Existing capability preference

When the task has a supplied repository, SDK, provider, framework, or other authoritative implementation that already provides the needed capability:

1. inspect it;
2. integrate it;
3. run it;
4. observe it;
5. record specific blocker evidence if it cannot satisfy the objective;
6. only then build a replacement.

Agents may not reimplement a provider merely because new code is easier than integration.

## Research and evaluator timing

Research is initially bounded by what blocks the first artifact. Once execution begins, research is pull-based from live defects or implementation uncertainty.

Evaluator construction is just in time. Unless execution would be unsafe without it, produce a candidate before spending substantial resources building and auditing the evaluator that will judge it.

## Execution incident

If the mission has consumed roughly 25% of its resource budget without a connected vertical slice, the manager records an execution incident and redirects work toward:

- implementation;
- integration;
- runtime;
- repair;
- direct verification.

Broad research, speculative architecture, benchmark expansion, documentation, and governance refinement lose priority until connected behavior exists.

## Hard stops

Authority loss, cancellation, scope escape, ownership collision, prohibited side effects, or exhausted hard budgets remain hard stops.

A hard stop should stop the specific unsafe effect, not automatically forbid unrelated safe local work. If production deployment is unauthorized, continue building/testing locally when the charter permits it.

## Release authority

Before consequential release or external effects, classify promised release deliverables as `required` or `optional` in [assets/release-scope.v1.json](assets/release-scope.v1.json) and run the existing release-scope admission/verification chain with the required external trust anchor and authenticated master decision.

That release ceremony belongs at the release boundary. Do not require an RSA-backed production release admission merely to create the first local reversible candidate.

## What to measure

- Reality Level reached;
- time and resource fraction to first materialized artifact;
- time and resource fraction to runnable candidate;
- time to connected vertical behavior;
- time to direct observation and verification;
- product execution ratio;
- research, governance, and documentation tax;
- first-pass acceptance and targeted rework count;
- global bottleneck changes;
- accepted customer-facing or user-usable output.

The manager owns control and acceptance; the worker owns its bounded deliverable. Final integration still requires the authority reserved by the program contract.
