---
name: direct-outcome
description: Own the durable Company OS objective lifecycle and automatically perform deterministic transitions between discovery, synthesis, runtime contract materialization, evaluator construction, registration, calibration, outcome control, and closed loop candidate execution. Use as the master entry point for broad outcome owned work.
---

# Direct Outcome

The master should not memorize the Company OS pipeline. The director does.

## Start

```bash
python3 skills/company-os/direct-outcome/scripts/direct_outcome.py start \
  --project-root /absolute/project \
  --objective-id viral-game \
  --objective "Make a viral game."
```

The director bootstraps the broad objective, persists a content addressed director state, and returns one `next_action`.

## Advance

On every scheduled wake up and after every completed Company OS fabric:

```bash
python3 skills/company-os/direct-outcome/scripts/direct_outcome.py advance \
  --project-root /absolute/project \
  --objective-id viral-game
```

The director performs all safe deterministic work immediately. It stops only when agents must create or change real artifacts.

## Director stages

1. discovery: run the bounded discovery fabric until both cited proposals exist
2. synthesis: merge proposals and reject conflicts or unresolved unknowns
3. runtime stack: compile artifact, evaluator, and benchmark contracts
4. evaluator capability: register real adapter bytes or compile missing adapter build work
5. calibration: verify existing execution bound calibration receipts or compile the next calibration lab
6. control: create scale authorization when justified, bind outcome control, and bind the closed loop state
7. candidate and rework: compile the smallest organization from the current bottleneck
8. evaluation: follow the loop’s exact independent evaluator action
9. reality: execute final reality acceptance against the original objective
10. accepted: terminal success

## Master rule

Follow only the director’s returned `next_action`. When it returns `execute_fabric`, run that exact manifest under the existing Company OS controller. When the fabric finishes, call `advance` again.

Do not substitute a new plan because the previous plan is familiar. The director is content bound to the latest outcome evidence. A new bottleneck can invalidate the previous organization.
