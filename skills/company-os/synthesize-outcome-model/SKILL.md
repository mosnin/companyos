---
name: synthesize-outcome-model
description: Deterministically merge cited Company OS discovery proposals into the complete measurable outcome model required before production. Use after the bounded discovery organization created by bootstrap-outcome finishes.
---

# Synthesize Outcome Model

Research is not useful until it becomes an executable definition of success.

Discovery workers write `company-os.outcome-model-proposal.v1` files. The synthesizer accepts only proposals bound to the exact initial request and rejects unsupported records, missing citations, unresolved blocking unknowns, and conflicting definitions.

## Synthesize

```bash
python3 skills/company-os/synthesize-outcome-model/scripts/synthesize_outcome_model.py \
  --base-request .company-os/outcomes/viral-game/outcome-request.json \
  --proposal .company-os/outcomes/viral-game/discovery/domain-truth/proposal.json \
  --proposal .company-os/outcomes/viral-game/discovery/artifact-quality/proposal.json \
  --request-output .company-os/outcomes/viral-game/measurable-outcome-request.json \
  --contract-output .company-os/outcomes/viral-game/measurable-outcome-contract.json
```

## Proposal requirements

Every proposal is bound to the initial request digest and carries citations. Together the proposals must define:

1. observable outcome claims
2. supported or refuted domain hypotheses
3. real artifact classes with modalities, observation methods, and required evidence
4. independent executable evaluator requirements with artifact coverage, evidence outputs, score dimensions, and an intended workspace adapter location
5. benchmark dimensions with multiple quality tiers and provenance
6. independent final reality acceptance bound to the original objective
7. cited closure for every blocking unknown

If two proposals define the same ID differently, synthesis fails with a conflict. Company OS then researches that exact disagreement. It does not average incompatible claims or silently pick one.

Successful synthesis must produce a deterministic outcome contract with no outcome level blockers. Rich artifact, evaluator runtime, benchmark, calibration, and scale gates still run afterward and can reveal deeper implementation gaps.
