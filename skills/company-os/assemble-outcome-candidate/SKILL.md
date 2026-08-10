---
name: assemble-outcome-candidate
description: Assemble content bound production lane artifact manifests from an outcome closed loop fabric into the exact Company OS candidate consumed by independent evaluation. Use after a candidate or rework production fabric finishes.
---

# Assemble Outcome Candidate

A manager saying “done” is not a candidate. The candidate is the exact set of real artifact bytes produced by the current content bound organization.

Each production worker writes `artifact-manifest.json` inside its assigned write scope. That manifest must bind:

1. the exact outcome loop state digest
2. the exact organization digest
3. the exact lane ID and lane digest
4. the exact production actor ID
5. every artifact ID, artifact class, project relative path, and SHA256

The assembler rejects stale manifests, wrong lanes, wrong worker identities, missing required artifact classes, symlinks, path escapes, digest drift, duplicate artifacts, and artifacts outside the worker’s authorized write scope.

## Assemble

```bash
python3 skills/company-os/assemble-outcome-candidate/scripts/assemble_candidate.py \
  --project-root /absolute/project \
  --fabric .company-os/outcomes/viral-game/runtime/build_candidate-fabric.json \
  --candidate-id candidate-1 \
  --output .company-os/outcomes/viral-game/runtime/candidate-1.json
```

The output uses `company-os.outcome-candidate.v1` and can be passed directly to the outcome director `record-candidate` command.
