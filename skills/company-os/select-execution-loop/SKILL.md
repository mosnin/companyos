---
name: select-execution-loop
description: Select and bind a finite, evidence-driven execution loop for a Company OS manager outcome. Use before manager dispatch when task shape, uncertainty, recurrence, traces, novelty, parallel lanes, or durable events should change how work iterates.
---

# Select Execution Loop

Choose how an accepted outcome should learn from feedback. This skill does not
replace the Company OS master, manager contracts, Luna task packets, authority,
or acceptance barriers. It binds one primary execution loop and only the
compatible adapters justified by the task.

## Selection workflow

1. Start from an accepted outcome and its mandatory requirements. Never use a
   loop to redefine the requested product or business result.
2. Create a `company-os.loop-selection-request.v1` using the schema documented
   in [references/selection-contract.md](references/selection-contract.md).
   Every run needs finite pass, stagnation, concurrency, depth, and cost
   boundaries. `null` cost is allowed only when the host cannot observe cost.
3. Run:

   ```bash
   python3 scripts/select_execution_loop.py request.json --output loop-plan.json
   ```

4. Inspect the chosen primary loop, adapters, reasons, required controls,
   metrics, and terminal states. A manager may reject the plan with evidence,
   but may not silently substitute a different loop.
5. Bind the plan digest into the manager charter and every affected worker
   packet. Load only the selected strategy references; do not inject the full
   loop catalog into prompts.
6. At verification, compare the actual run receipt with the bound plan. Missing
   checks, exceeded limits, fabricated telemetry, or a different loop make the
   execution evidence invalid.

## Composition rules

- Exactly one primary loop owns iteration order.
- At most three adapters may add diagnostics, learning, or durable event
  transport. Adapters never create a second authority chain.
- `bounded-evidence-loop` is the safe general loop when no specialized primary
  is justified.
- Recursive decomposition is for independently owned work, not an excuse to
  duplicate shared files or let children approve parents.
- Trace optimization diagnoses observed executions. It does not authorize a
  repair or prove that its recommendation works.
- Recurring and event-driven plans compile as desired state only. Scheduler,
  credential, production, and external-message activation remain separately
  gated.
- Divergent exploration must use a held-out acceptance gate so novelty does not
  replace usefulness. Do not invent another primary loop for a RIOCL TC
  overlay. Bottleneck optimization stays a `company-os.riocl-tc-packet.v1`
  checklist on the selected loop.
- No strategy is infinite. Success, clean no-op, blocked, approval-required,
  exhausted, and stagnated are always terminal outcomes.

## Source boundary

The catalog adapts mechanisms from pinned public projects. Read
[references/source-essence.md](references/source-essence.md) when changing a
strategy or evaluating an upstream update. External repositories are evidence,
not executable dependencies. Company OS does not install their shell scripts,
plugins, runtimes, or credentials through this skill.

