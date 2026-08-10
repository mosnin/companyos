---
name: register-outcome-evaluators
description: Bind required Company OS evaluator definitions to actual local adapter bytes and produce the content addressed adapter registry used by execute-outcome-evaluator. Use after materialize-outcome-stack and after any evaluator adapter is created or changed.
---

# Register Outcome Evaluators

An evaluator definition is not an evaluator capability until its executable adapter exists.

## Register

```bash
python3 skills/company-os/register-outcome-evaluators/scripts/register_outcome_evaluators.py \
  --project-root /absolute/project \
  --evaluator-contract .company-os/outcomes/viral-game/runtime/evaluator-contract.json \
  --output .company-os/outcomes/viral-game/runtime/evaluator-adapter-registry.json
```

For each required evaluator, the command requires a `workspace://` adapter locator, maps it to a real project relative file, rejects symlinks, hashes the exact entrypoint bytes, and creates the registry descriptor expected by `$execute-outcome-evaluator`.

The resulting registry is self addressed with `registry_sha256`. Every adapter is then resolved through the real evaluator execution runtime to prove artifact classes, evidence outputs, score dimensions, runtime, path, and entrypoint digest agree with the evaluator contract.

## Missing capability

If a required adapter path does not exist, registration fails with `E_ADAPTER_MISSING`. Route that evaluator to `$build-outcome-evaluators`. Do not remove the evaluator requirement and do not replace execution with prose review.
