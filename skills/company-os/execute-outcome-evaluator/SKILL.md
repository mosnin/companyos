---
name: execute-outcome-evaluator
description: Execute a content addressed independent evaluator against real project artifacts and produce a verifiable execution receipt. Use after evaluator, artifact, and benchmark contracts exist and before calibration, scale authorization, or reality acceptance.
---

# Execute Outcome Evaluator

An evaluator contract is not evidence that evaluation happened. This skill runs the declared adapter and binds the resulting judgment to the exact artifact bytes, evaluator contract, benchmark contract, adapter registry, adapter entrypoint, executor identity, scores, findings, and evidence files.

## Required sequence

1. Compile the evaluator contract and benchmark contract.
2. Register the adapter with an exact project relative entrypoint path and SHA256 digest.
3. Provide content addressed artifacts covering every artifact class consumed by the evaluator.
4. Execute through `scripts/execute_evaluator.py execute`.
5. Verify the receipt through `scripts/execute_evaluator.py verify` before using it for calibration or acceptance.

## Adapter protocol

The runner invokes adapters without a shell and sends one canonical JSON document through standard input. Python adapters run through the current Python interpreter. Native adapters must be executable files. The adapter must write exactly one JSON object to standard output using schema `company-os.evaluator-adapter-output.v1`. Diagnostic logs belong on standard error.

The output must bind the supplied run, objective, and evaluator identifiers. It must include every declared score dimension and produce at least one real project file for every declared evidence type.

## Authority and integrity

The executor actor must not appear in the production actor set. Artifact, contract, registry, adapter, and evidence paths must remain inside the project root, may not traverse symlinks, and must match their recorded digests. A nonzero adapter exit, timeout, oversized output, missing evidence, missing scores, identity drift, or byte drift fails closed.

The receipt stores only portable project relative paths and content digests. Absolute paths used during local execution are not retained as authority.
