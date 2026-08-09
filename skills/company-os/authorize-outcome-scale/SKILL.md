---
name: authorize-outcome-scale
description: Compile the final content bound authorization required before Company OS may scale ordinary production. Use after outcome, artifact, evaluator, benchmark, and evaluator calibration contracts are available.
---

# Authorize Outcome Scale

Production scale is a consequence of understanding, not a substitute for it.

This gate joins the outcome control plane into one deterministic authorization receipt. It does
not launch work. It decides whether high concurrency production is permitted for the exact
objective and exact contract set.

## Required inputs

1. `company-os.outcome-contract.v1`
2. `company-os.artifact-observation-contract.v1`
3. `company-os.evaluator-runtime-contract.v1`
4. `company-os.benchmark-contract.v1`
5. one passed `company-os.evaluator-calibration-receipt.v1` for every required evaluator

All inputs must bind the same objective. Required rich artifacts must be covered by at least one
required executable evaluator. Every required evaluator must have a passing calibration receipt.

## Compile

```bash
python3 scripts/authorize_outcome_scale.py authorize \
  --outcome /absolute/path/outcome-contract.json \
  --artifacts /absolute/path/artifact-contract.json \
  --evaluators /absolute/path/evaluator-contract.json \
  --benchmarks /absolute/path/benchmark-contract.json \
  --calibrations /absolute/path/calibration-receipts.json \
  --output /absolute/path/outcome-scale-authorization.json
```

The authorization is fail closed. An unauthorized receipt is useful diagnostic evidence but may
not be interpreted as production authority.
