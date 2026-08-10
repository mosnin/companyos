---
name: compile-outcome-organization
description: Compile the current Company OS outcome loop state into the smallest executable Sol manager and Luna worker organization that can move the present quality bottleneck. Use before configuring an outcome owned execution fabric.
---

# Compile Outcome Organization

The organization is a function of the current outcome state, not a static department chart.

## Rules

1. Read the exact current outcome loop state.
2. During initial candidate materialization, derive production lanes from required artifact classes.
3. During rework, derive specialist lanes only from the dominant failing dimensions and their coupled artifact classes.
4. Preserve independently passing dimensions as explicit constraints on every rework worker.
5. Keep independent evaluator lanes outside the production organization.
6. Begin with the smallest organization that can create a real candidate.
7. A pilot may not silently exceed its outcome control scale authority.
8. Bind every manager and worker to the exact outcome loop lane digest.
9. If the outcome loop state, organization plan, lane definitions, or next action changes, the existing execution manifest becomes stale and must not run.

## Compile

```bash
python3 skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py compile \
  --project-root /absolute/project \
  --loop-state .company-os/outcome-loop.json \
  --request .company-os/outcome-organization-request.json \
  --output .company-os/outcome-fabric.json
```

The compiler emits `topology_mode: outcome_closed_loop`. This mode carries a content bound `outcome_loop` receipt in addition to the existing portable outcome control binding.

## Reconciliation

After independent evaluation changes the outcome loop state, do not reuse the previous organization merely because its tasks are unfinished. Recompile the organization from the new dominant constraint. Passing dimensions are preserved. Stagnant dimensions trigger a different strategy owner or capability mix rather than more identical workers.
