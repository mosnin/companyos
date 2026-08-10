---
name: assemble-outcome-evaluations
description: Assemble the independently verified execution receipts emitted by an outcome closed loop evaluation fabric into the exact evaluation batch consumed by the Company OS outcome loop. Use after an evaluation fabric finishes.
---

# Assemble Outcome Evaluations

Independent evaluation must enter Company OS through verified receipt bytes, not through a manager summary.

For every independent evaluator worker in the current evaluation fabric, the assembler expects `execution-receipt.json` in that worker’s exact write scope. It verifies each receipt through `$execute-outcome-evaluator`, requires the exact current objective, requires exactly one receipt per required evaluator, and rejects duplicate evaluator identities.

## Assemble

```bash
python3 skills/company-os/assemble-outcome-evaluations/scripts/assemble_evaluations.py \
  --project-root /absolute/project \
  --fabric .company-os/outcomes/viral-game/runtime/evaluate-fabric.json \
  --candidate-id candidate-1 \
  --output .company-os/outcomes/viral-game/runtime/candidate-1-evaluations.json
```

The output uses `company-os.outcome-evaluation-batch.v1` and can be passed directly to the outcome director `record-evaluations` command.

Missing receipts return `E_RECEIPT_MISSING`. Invalid or stale receipts fail closed instead of causing the director to rerun production blindly.
