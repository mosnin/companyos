---
name: run-outcome-loop
description: Drive a Company OS objective from broad intent through a real candidate, independent evaluation, bottleneck focused rework, organization mutation, and execution bound reality acceptance. Use whenever Company OS owns an outcome rather than a narrow task.
---

# Run Outcome Loop

Company OS is an outcome engine. Task completion, source code, tests, worker reports, and manager approval are not the stopping condition.

## Required loop

1. Start from the original objective exactly as supplied.
2. When the objective is not measurable, run discovery until the outcome contract, artifact classes, evaluator contracts, benchmark tiers, and calibration are closed enough for a bounded pilot.
3. Compile the smallest organization needed to materialize a real candidate.
4. Materialize the candidate before expanding production scale.
5. Execute every required independent evaluator against the actual candidate artifacts.
6. Aggregate evaluator scores conservatively and select the dominant quality gap.
7. Preserve dimensions that already pass. Rework only the dominant constraint and directly coupled artifact classes.
8. If the same constraint fails to improve across the stagnation window, reorganize the producing team, acquire missing capability or benchmarks, and challenge the current artifact approach instead of polishing the same failed abstraction.
9. Repeat candidate, observation, evaluation, diagnosis, and targeted intervention until the quality policy passes.
10. Run execution bound reality acceptance against the original objective. Production narratives are inadmissible.
11. Complete only when the reality receipt accepts the current candidate. A rejected reality receipt returns the loop to rework and may reopen discovery assumptions.

## Runtime

Use `skills/company-os/elastic-company-os/scripts/outcome_loop.py` as the deterministic state machine.

Start a broad objective:

```bash
python3 skills/company-os/elastic-company-os/scripts/outcome_loop.py start --request objective.json --output outcome-loop.json
```

After outcome control contracts are compiled and verified:

```bash
python3 skills/company-os/elastic-company-os/scripts/outcome_loop.py bind-control --project-root /absolute/project --state outcome-loop.json --control-state outcome-control-state.json --output outcome-loop.json
```

Record each materialized candidate, then record the exact evaluator execution receipts. Follow only the returned `next_action`. Do not infer acceptance from activity.

## Organizational rule

Organization is compiled from the current bottleneck. Initial specialist lanes are derived from required artifact classes and evaluator coverage. Rework creates only the specialist lanes needed for the dominant quality gap. Stagnation triggers organization mutation rather than additional identical workers.

## Scale rule

Large execution is not a substitute for understanding. Begin with the smallest real candidate and independent observation. Expand concurrency only after the evaluator system can distinguish poor, intermediate, and excellent artifacts and after the current outcome control authorizes scale.

## Completion rule

The only terminal success state is `accepted`. It requires an execution bound reality receipt for the current candidate, with actual artifact digests and independently verified evaluator execution receipts bound to the original objective.
