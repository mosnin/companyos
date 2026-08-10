---
name: run-outcome-loop
description: Drive a Company OS objective from broad intent through autonomous discovery, executable outcome contracts, a real candidate, independent evaluation, bottleneck focused rework, organization mutation, and execution bound reality acceptance. Use whenever Company OS owns an outcome rather than a narrow task.
---

# Run Outcome Loop

Company OS is an outcome engine. Task completion, source code, tests, worker reports, and manager approval are not the stopping condition.

## Required loop

1. Preserve the original objective exactly as supplied.
2. If the operator supplied only a broad objective, use `$bootstrap-outcome`. Company OS creates the blocking unknowns and bounded discovery organization itself. Do not ask the operator for domain vocabulary that can be researched.
3. Execute the discovery fabric. Research managers produce cited outcome model proposals with counterevidence and reconciliation.
4. Use `$synthesize-outcome-model`. Conflicting proposals fail closed and trigger focused additional discovery. Successful synthesis must resolve every blocking unknown and produce a measurable outcome model.
5. Use `$materialize-outcome-stack` to compile the artifact observation contract, evaluator runtime contract, and benchmark contract directly from the synthesized model.
6. Build or locate every required evaluator adapter and register it with `$register-outcome-evaluators`. An evaluator definition without executable adapter bytes is not a capability.
7. Calibrate required evaluators against multiple quality tiers. Do not scale production until the evaluator system can distinguish weak, baseline, strong, and exemplar candidates as required by the benchmark contract.
8. Compile the smallest organization needed to materialize a real candidate.
9. Materialize the candidate before expanding production scale.
10. Execute every required independent evaluator against the actual candidate artifacts and required observation modalities.
11. Aggregate evaluator scores conservatively and select the dominant quality gap.
12. Preserve dimensions that already pass. Rework only the dominant constraint and directly coupled artifact classes.
13. If the same constraint fails to improve across the stagnation window, reorganize the producing team, acquire missing capability or benchmarks, and challenge the current artifact approach instead of polishing the same failed abstraction.
14. Repeat candidate, observation, evaluation, diagnosis, and targeted intervention until the quality policy passes.
15. Run execution bound reality acceptance against the original objective. Production narratives are inadmissible.
16. Complete only when the reality receipt accepts the current candidate. A rejected reality receipt returns the loop to rework and may reopen discovery assumptions.

## Runtime

Use `skills/company-os/elastic-company-os/scripts/outcome_loop.py` as the deterministic state machine.

For a broad objective, first bootstrap discovery:

```bash
python3 skills/company-os/bootstrap-outcome/scripts/bootstrap_outcome.py \
  --project-root /absolute/project \
  --objective-id viral-game \
  --objective "Make a viral game."
```

After discovery proposals are synthesized, materialize the runtime contracts:

```bash
python3 skills/company-os/materialize-outcome-stack/scripts/materialize_outcome_stack.py \
  --outcome-request .company-os/outcomes/viral-game/measurable-outcome-request.json \
  --output-dir .company-os/outcomes/viral-game/runtime
```

After outcome control contracts are compiled and verified:

```bash
python3 skills/company-os/elastic-company-os/scripts/outcome_loop.py bind-control \
  --project-root /absolute/project \
  --state .company-os/outcomes/viral-game/outcome-loop.json \
  --control-state .company-os/outcomes/viral-game/outcome-control-state.json \
  --output .company-os/outcomes/viral-game/outcome-loop.json
```

Record each materialized candidate, then record the exact evaluator execution receipts. Follow only the returned `next_action`. Do not infer acceptance from activity.

## Organizational rule

Organization is compiled from the current bottleneck. Initial specialist lanes are derived from required artifact classes and evaluator coverage. Rework creates only the specialist lanes needed for the dominant quality gap. Stagnation triggers organization mutation rather than additional identical workers.

## Scale rule

Large execution is not a substitute for understanding. Begin with the smallest real candidate and independent observation. Expand concurrency only after the evaluator system can distinguish materially different quality tiers and after the current outcome control authorizes scale.

## Completion rule

The only terminal success state is `accepted`. It requires an execution bound reality receipt for the current candidate, with actual artifact digests, required experiential evidence, and independently verified evaluator execution receipts bound to the original objective.
