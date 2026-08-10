---
name: calibrate-outcome-stack
description: Compile bounded Company OS calibration work that forces each required evaluator to judge multiple real candidates with known quality ordering using the exact registered adapter, benchmark contract, and artifact classes. Use after evaluator adapters are registered and before outcome control or production scale.
---

# Calibrate Outcome Stack

Company OS must prove that its judge can distinguish bad from good before trusting that judge with production.

## Compile a calibration batch

```bash
python3 skills/company-os/calibrate-outcome-stack/scripts/compile_calibration_fabric.py \
  --project-root /absolute/project \
  --evaluator-contract .company-os/outcomes/viral-game/runtime/evaluator-contract.json \
  --artifact-contract .company-os/outcomes/viral-game/runtime/artifact-contract.json \
  --benchmark-contract .company-os/outcomes/viral-game/runtime/benchmark-contract.json \
  --adapter-registry .company-os/outcomes/viral-game/runtime/evaluator-adapter-registry.json \
  --output .company-os/outcomes/viral-game/runtime/calibration-fabric.json
```

The compiler creates at most two evaluator managers per batch. Each manager gets three disjoint Luna candidate workers:

1. rank one: deliberately weak but valid candidate, anchored to negative or baseline references
2. rank two: materially intermediate candidate
3. rank three: strong or exemplar candidate anchored to the positive reference set

The workers materialize real artifacts for the evaluator artifact classes. The manager then runs the exact registered evaluator adapter on each distinct artifact set using the same evaluator contract, benchmark contract, registry, and adapter bytes. Finally it runs the execution bound calibration compiler.

## Pass condition

Calibration passes only when every required score dimension strictly increases with the known candidate ordering. Ties fail. Inversions fail. Reused execution receipts fail. Reused artifact sets fail. Changed adapter or benchmark bytes fail.

If the judge cannot distinguish the candidates, Company OS must improve or replace the evaluator capability before production. It must not lower the quality bar, remove score dimensions, or proceed because the evaluator returned numbers.
