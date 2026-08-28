---
name: materialize-outcome-stack
description: Convert a synthesized measurable Company OS outcome request into the rich artifact observation contract, executable evaluator runtime contract, and quality benchmark contract used by the closed loop runtime. Use immediately after synthesize-outcome-model succeeds. Do not use before an accepted measurable outcome model exists, or for one-off artifact work outside the outcome loop.
---

# Materialize Outcome Stack

Discovery output must become runtime contracts without a manager manually rewriting the same model into new schemas.

## Compile

```bash
python3 skills/company-os/materialize-outcome-stack/scripts/materialize_outcome_stack.py \
  --outcome-request .company-os/outcomes/viral-game/measurable-outcome-request.json \
  --output-dir .company-os/outcomes/viral-game/runtime
```

The command deterministically emits:

1. `artifact-request.json`
2. `artifact-contract.json`
3. `evaluator-request.json`
4. `evaluator-contract.json`
5. `benchmark-request.json`
6. `benchmark-contract.json`
7. `stack-receipt.json`

Every emitted contract must report `ready: true`. Rich artifact required evidence is preserved exactly. Evaluator artifact coverage, evidence outputs, score dimensions, independence, and adapter locations are preserved exactly. Benchmark reference tiers and provenance are preserved exactly.

## Failure behavior

Do not downgrade a rich artifact because an evaluator is inconvenient to build. Do not remove required evidence to make the scale gate pass. Do not silently rename benchmark tiers. If a discovered model is incompatible with the runtime contract schemas, fail and send the specific mismatch back to discovery synthesis.

## Next action

After materialization, required workspace evaluator adapters must exist and be registered with `$register-outcome-evaluators`. Missing adapters are a capability construction problem, not permission to skip independent evaluation.
