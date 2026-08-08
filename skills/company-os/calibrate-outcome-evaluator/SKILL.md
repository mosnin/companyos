---
name: calibrate-outcome-evaluator
description: Prove an evaluator can discriminate weak from strong artifacts before Company OS scales production. Use after executable evaluators and benchmark tiers exist.
---

# Calibrate Outcome Evaluator

Do not trust a judge merely because it returns scores.

Before high concurrency production, run the evaluator against sealed candidates with known quality
ordering. The gate passes only when the evaluator preserves the required ordering across every
required dimension and does not collapse materially different candidates into ties.

A progress bar, a broken game, a functional but weak game, and a polished reference should not
receive indistinguishable scores.
