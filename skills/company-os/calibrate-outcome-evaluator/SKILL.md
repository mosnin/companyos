---
name: calibrate-outcome-evaluator
description: Prove an executable evaluator can discriminate weak from strong artifacts using verified execution receipts before Company OS authorizes elastic production. Use when a compiled executable evaluator must be shown to rank poor, intermediate, and excellent candidates before scale authorization. Do not use for ad hoc scoring or before an executable evaluator runtime exists.
---

# Calibrate Outcome Evaluator

Do not trust a judge merely because it returns scores.

Calibration accepts no manually supplied candidate scores. Every candidate must reference a content addressed execution receipt produced by `$execute-outcome-evaluator`. The calibration runtime revalidates the evaluator contract, benchmark contract, adapter registry, adapter entrypoint, artifact bytes, evidence bytes, executor independence, and exact retained scores before comparing candidates.

Use at least three sealed candidates with a known ascending quality order. Candidate artifacts and execution receipts must be distinct. Every candidate must use the same evaluator contract, benchmark contract, adapter registry, and adapter bytes. The gate passes only when every required score dimension increases strictly across the known order.

A progress bar, a broken game, a functional but weak game, and a polished reference must not receive indistinguishable or inverted scores.

A calibration receipt remains valid only while every bound execution receipt, artifact, evidence file, contract, registry, and adapter retains the exact verified digest. Any drift blocks outcome control and production scale.
