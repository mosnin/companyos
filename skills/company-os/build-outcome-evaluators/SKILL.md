---
name: build-outcome-evaluators
description: Compile bounded Company OS work to construct missing required workspace evaluator adapters from the evaluator, artifact, and benchmark contracts. Use when register-outcome-evaluators reports E_ADAPTER_MISSING.
---

# Build Outcome Evaluators

Missing evaluation capability is a build problem, not permission to remove the quality gate.

## Compile evaluator build work

```bash
python3 skills/company-os/build-outcome-evaluators/scripts/compile_evaluator_build_fabric.py \
  --project-root /absolute/project \
  --evaluator-contract .company-os/outcomes/viral-game/runtime/evaluator-contract.json \
  --artifact-contract .company-os/outcomes/viral-game/runtime/artifact-contract.json \
  --benchmark-contract .company-os/outcomes/viral-game/runtime/benchmark-contract.json \
  --output .company-os/outcomes/viral-game/runtime/evaluator-build-fabric.json
```

The compiler finds required `workspace://` adapters whose entrypoint files do not yet exist. It assigns each missing evaluator to a disjoint worker scope at the exact adapter path. A batch contains at most six evaluator workers under the existing bounded two manager legacy fabric. If more remain, run the next batch after the first is materialized and registered.

## Worker contract

Each worker receives the exact evaluator definition and the bound artifact and benchmark contract paths. It must inspect `$execute-outcome-evaluator`, implement the required adapter input and output protocol, and prove that the adapter can emit every required evidence type and score dimension. The adapter must judge actual artifact behavior for its modalities. Source inspection or a production completion narrative cannot substitute for required interaction, visual, audio, runtime, or other experiential evidence.

If a real external runtime is required and unavailable, return the exact prerequisite as a blocker. Do not fake evidence.

After workers finish, run `$register-outcome-evaluators`. Calibration remains mandatory before production scale.
