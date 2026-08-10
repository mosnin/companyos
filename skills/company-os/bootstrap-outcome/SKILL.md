---
name: bootstrap-outcome
description: Turn a one sentence objective into the initial Company OS outcome request, discovery contract, outcome loop state, and bounded research organization. Use when the operator supplies an outcome but does not know the domain requirements, artifacts, benchmarks, or evaluator vocabulary.
---

# Bootstrap Outcome

A broad objective is sufficient input. Do not ask the operator to provide implementation terminology that Company OS can discover itself.

## Bootstrap

```bash
python3 skills/company-os/bootstrap-outcome/scripts/bootstrap_outcome.py \
  --project-root /absolute/project \
  --objective-id viral-game \
  --objective "Make a viral game."
```

The command reads the authoritative local Company OS control store and creates a content bound outcome workspace under `.company-os/outcomes/<objective-id>/` containing:

1. the original objective request with universal blocking unknowns
2. the deterministic discovery contract
3. the closed loop outcome state
4. a bounded two manager discovery fabric
5. a bootstrap receipt with the work ID and exact artifact paths

## Universal discovery questions

Company OS creates these questions itself:

1. What observable state of reality proves the objective succeeded?
2. What domain, platform, operational, legal, or technical constraints define a valid solution?
3. What actual artifacts must exist, and how can each be exercised or observed?
4. What separates weak, baseline, strong, and exemplar quality?
5. How can independent evaluators execute against the actual artifacts and produce required evidence?
6. How can the final candidate be judged against the original objective independently of production?

## Discovery organization

The bootstrap fabric uses the existing bounded legacy execution authority because outcome control cannot exist before discovery closes.

Manager one owns success and domain truth.

Manager two owns artifact reality, quality, benchmarks, evaluator design, and final acceptance.

Workers must research primary or authoritative sources where available, search for counterevidence, and write structured `company-os.outcome-model-proposal.v1` proposals. Research reports are inputs to synthesis, not acceptance.

After both manager proposals exist, use `$synthesize-outcome-model`. If proposals conflict, resolve the specific conflict with another bounded research pass. Do not ask the operator to become the domain expert.
