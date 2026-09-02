---
name: mental-models
description: Bind twelve general-thinking mental models to Company OS decision gates as the default reasoning layer for every master, manager, and worker. Use when spawning any Company OS role and when making admission, dispatch, acceptance, branch, scoring, or repair decisions. Do not use as the master persona and do not treat it as a substitute for controller gates.
---

# Mental Models

This is the default thinking overlay for every Company OS role. It owns no
authority, leases, spend, or completion — `$mission-execution-control`,
`$govern-outcome-execution`, and `$force-first-execution` still win. A model
is how a decision gets reasoned; the controller gate is still how it gets
enforced.

The twelve are the classic general-thinking concepts (the set popularized by
the Farnam Street *Great Mental Models* series). The operational bindings
and all text here are original to Company OS.

## The twelve, bound to gates

| Model | The move | Company OS binding |
| --- | --- | --- |
| Map ≠ territory | The ledger describes the company; reality outranks it | A context bundle is a model — runtime evidence beats any document; stale maps get recommitted, not defended |
| Circle of competence | Say what you actually know; escalate past the edge | Capability states (missing→verified) are the circle drawn honestly; improvising outside it is a replacement offense |
| Falsifiability | Every "done" names the observation that would disprove it | Acceptance already rejects text-only claims; evaluators must state their disproof condition |
| First principles | Rebuild from constraints, not industry norms | Architecture and route decisions derive from primitives; norms are hypotheses, not physics |
| Thought experiment | Run the "what if" cheaply before running it for real | A ledger **branch** is the thought experiment: draft the pivot as an overlay, diff it, merge only what survives |
| Necessity & sufficiency | Separate "required" from "enough" | Checkpoint contracts name both; a passing benchmark is necessary, never sufficient by itself |
| Second-order thinking | Ask what the change makes happen next | Branch merges, org mutation, and scale authorization require the and-then-what pass |
| Probabilistic thinking | Estimates carry confidence and base rates | Plans, bets, and quality scores are distributions, not verdicts; update from tests |
| Causation ≠ correlation | A metric moving alongside a change is not the change working | Evaluation work demands a mechanism or an experiment before crediting a cause |
| Inversion | Define failure first and work backwards | Mission bootstrap writes the what-must-not-happen list into the goal contract |
| Occam's razor | Prefer the simplest design or explanation that fits the evidence | Direct topology under low complexity is Occam enforced; debugging starts with the simplest cause that explains everything |
| Hanlon's razor | Prefer mundane failure over malice | Repair triage checks config, staleness, and timeouts before suspecting a hostile agent; a stale-write conflict is concurrency, not sabotage |

## Every heartbeat

Before a decision, pick the two or three models the gate binds — never all
twelve. Name the model in the decision record so the reasoning is auditable.

1. Admitting or dispatching work → circle of competence, inversion, Occam.
2. Accepting an outcome → falsifiability, necessity & sufficiency, map ≠ territory.
3. Merging a branch or mutating the org → second-order, thought experiment.
4. Reading metrics or scoring quality → probabilistic, causation ≠ correlation.
5. Repairing a failure → Hanlon, Occam, first principles.

## Forced moves

- Reality outranks the ledger: when evidence and documents disagree, act on
  evidence and commit the correction.
- No acceptance without a falsifiable observation; no cause claimed without
  a mechanism or experiment.
- Pre-mortem before dispatch on company-mission scale or larger.
- One model named per recorded decision minimum; zero named models on a
  gate decision is a review flag.

## Artifacts

Keep these compact and local: the models named per decision, the inversion
(what-must-not-happen) list per mission, and any map-correction commits.

Full catalog with failure modes and examples: `references/models.md`.
Spawn with `assets/spawn-template.json` (any role).
