---
name: govern-outcome-execution
description: Govern mission-level execution economics. Use on every master heartbeat to measure distance from the original objective, identify the global bottleneck, force early real-artifact execution, cap research/governance overhead, prefer supplied capabilities over reimplementation, and enter compression or critical-path modes when reality progress lags resource burn.
---

# Govern Outcome Execution

This skill exists to prevent Company OS from becoming a competent bureaucracy that never produces the requested thing.

The governor is above local manager optimization. It answers one question repeatedly:

> Given the original objective, current reality, remaining time/tokens/cost, and current bottlenecks, what work most increases the probability that the user receives the actual finished outcome?

## Reality levels

Classify mission progress by the strongest observable level reached:

- **R0** — research, plans, schemas, contracts, reports, or designs only.
- **R1** — internal implementation primitives exist.
- **R2** — an isolated capability actually runs.
- **R3** — the smallest connected end-to-end vertical behavior actually runs.
- **R4** — a fresh user can use the requested outcome.
- **R5** — the user-usable outcome has passed independent reality acceptance.

Accepted internal documents do not advance reality by themselves. Tests around code that is not connected to the requested behavior do not imply R3 or R4.

## First-reality rule

For build missions, reach R3 before roughly 25% of the mission budget is consumed. The first slice may be narrow and ugly, but it must exercise the real artifact path.

If R3 is missing at the first-reality boundary, declare an **execution incident**. Pause broad research, speculative architecture, benchmark expansion, noncritical documentation, and governance refinement. Redirect management capacity to implementation, integration, runtime, repair, and direct observation.

## Global bottleneck

Every master heartbeat must identify the single most important missing capability between current reality and the original objective. Managers optimize their local lanes; the governor optimizes the company.

Resources follow the global bottleneck. A technically interesting lane is paused when it does not materially shorten objective distance.

When choosing the intervention, bind a `company-os.riocl-tc-packet.v1` and
follow the RIOCL TC overlay: tag the regime, compress feedback latency, name
one outcome, at most two constraints, one bottleneck, and exactly one safe
action. The packet is a checklist. This skill remains the governor.

## Operating modes

- **NORMAL** — initial discovery and execution proceed together.
- **COMPRESSION** — reality is lagging resource consumption; research/design/governance shrink and execution dominates.
- **CRITICAL_PATH** — most discretionary work pauses; only blockers to a user-usable outcome receive meaningful resources.
- **REALITY_CLOSURE** — near budget exhaustion, allow only integrate, run, fix, verify, package, and durable checkpoint work.
- **ACCEPTED** — R5 reached.

Default thresholds are policy inputs, not universal truths. The executable governor currently uses 25% for the first-reality incident, 40% for compression when R3 is absent, 70% for critical-path mode when R4 is absent, and 88% for reality closure.

## Existing-capability preference

When the user supplies a repository, provider, SDK, framework, or authoritative implementation that already provides a required capability:

1. Inspect it.
2. Integrate and exercise it in a bounded environment.
3. Observe the real behavior.
4. Record blocker evidence if it cannot satisfy the requirement.
5. Only then authorize replacement or reimplementation.

Writing a new substitute because it is easier for an agent to code is not a valid reason to bypass an existing capability.

## Research policy

Initial research exists to remove uncertainty blocking the first real slice. Once enough is known to execute, research becomes pull-based: implementation managers request specific research to remove a live blocker. Do not continue producing a corpus merely because researchers are available.

## Just-in-time governance and evaluation

Use strong governance before irreversible or externally consequential actions. For local source edits, builds, tests, browser/simulator runs, disposable staging, and sandbox execution, prefer fast bounded action plus observation.

Do not build elaborate evaluator infrastructure for an artifact that does not exist. Materialize a candidate first, then build/calibrate the evaluator required to judge that candidate.

## Durability

Product bytes are first-class durable state. After a bounded slice passes its relevant checks, checkpoint or commit it promptly. A mission where governance records are committed while the actual product remains untracked is unhealthy.

## Executable policy

Run:

```bash
python3 skills/company-os/govern-outcome-execution/scripts/executive_governor.py evaluate \
  --input .company-os/executive-governor-input.json \
  --output .company-os/executive-governor-decision.json
```

The output is content-addressed and includes reality level, operating mode, first-reality incident state, dominant bottleneck, allocation ratios, paused work classes, existing-capability directives, and manager orders.

Managers may provide additional evidence, but they may not downgrade an execution incident through narrative. Reality advances only from observable capability state.
