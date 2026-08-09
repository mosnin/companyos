---
name: compile-outcome-contract
description: Compile a broad user objective into a measurable outcome contract before Company OS is allowed to scale execution. Use when the objective is underspecified, domain knowledge is incomplete, artifact classes are unknown, or quality cannot yet be independently evaluated.
---

# Compile Outcome Contract

Company OS must understand what success means before it scales production.

A broad objective such as `make a viral game` is valid input. Do not require the user to
pre-supply implementation requirements, acceptance checks, artifact classes, or domain
expertise. Unknowns become bounded discovery work instead of invented certainty.

## Sequence

1. Capture the original objective byte-for-byte.
2. Record current outcome claims, domain hypotheses, artifact classes, evaluator
   requirements, benchmark requirements, and unresolved questions.
3. Compile with:

```bash
python3 scripts/compile_outcome_contract.py compile \
  --request /absolute/path/outcome-request.json \
  --output /absolute/path/outcome-contract.json
```

4. Verify with:

```bash
python3 scripts/compile_outcome_contract.py verify \
  --request /absolute/path/outcome-request.json \
  --contract /absolute/path/outcome-contract.json
```

5. If `scale_allowed` is false, dispatch only the emitted discovery agenda. Do not
   expand ordinary production concurrency.
6. Recompile after discovery evidence changes. Production may scale only when all
   required outcome dimensions have observable evidence paths.

## Required semantics

The compiler distinguishes three states:

* `discovery_required`: the system does not yet know enough to define reality.
* `pilot_allowed`: enough is known to build a bounded candidate for evaluator calibration.
* `scale_allowed`: the outcome, artifacts, evaluators, and benchmarks are closed enough
  for expensive production to scale.

`scale_allowed` requires all of the following:

* no unresolved blocking unknowns;
* at least one explicit outcome claim;
* every required artifact class has an observation method;
* every required evaluator has an executable method and independent role;
* every benchmark requirement has at least one bound reference;
* every outcome claim maps to at least one artifact, evaluator, or external metric;
* a reality acceptance policy is present and binds the original objective.

## Unknown means research until measurable

Never convert an unknown into a guessed requirement merely to satisfy a schema.
The discovery agenda is executable planning output. It states what must be learned,
why it blocks confidence, and which closure evidence is required.

## Authority boundary

This compiler does not launch agents, approve production, choose a technology, or claim
that a product is good. It only proves whether the current understanding of the outcome
is sufficiently measurable to permit the next execution scale.
