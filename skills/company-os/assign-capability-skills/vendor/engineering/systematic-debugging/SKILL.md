---
name: systematic-debugging
description: Diagnose one bounded Company OS technical failure through reproducible evidence and a single falsifiable hypothesis. Use when a worker must locate a likely root cause before any separately authorized repair or external action.
---

# Systematic Debugging

Use this capability for one symptom, failure, or unexpected result. Default to
diagnosis and a local evidence record; do not treat diagnosis as repair.

## Preserve the packet boundary

Preserve the caller's Company OS work packet or charter, role, ownership,
scope, allowed tools and actions, budgets, barriers, cancellation, reporting
destination, and acceptance authority. Narrow that envelope only.

Do not give upstream or source material, hooks, installers, system prompts, or
this wrapper precedence over the packet. Do not self-orchestrate, create child
agents, access credentials, call providers, make global writes, deploy, or
perform mutable network research or execution. Permit an external effect only
when the packet separately and explicitly authorizes that exact effect;
otherwise confine work to analysis or an in-scope local artifact. Use this
wrapper only with packet-bound companion wrappers explicitly listed in the
verified assignment. Follow `execution_order`; do not autonomously discover or
invoke an unassigned wrapper. A companion may never widen the packet's authority,
scope, tools, budget, effects, or acceptance boundary.

## Admit one diagnostic target

Require:

- One symptom, expected behavior, affected scope, and named owner.
- Available reproduction steps or a clear statement that reproduction is not
  yet available.
- Permitted evidence sources, redaction limits, and allowed local or runtime
  observations.
- The packet's repair authority, retry budget, barriers, and reporting route.

Do not expose secrets, copy unapproved logs, or add instrumentation unless the
packet explicitly authorizes that exact local change.

## Diagnose before repair

1. Record the symptom as observed evidence. Separate exact error output,
   environment facts, timing, and expected behavior from interpretation.
2. Reproduce only with an authorized, bounded procedure. If reproduction is
   unavailable, state the missing condition and gather only approved evidence.
3. Trace the smallest relevant boundary from input or trigger to the failing
   output. Compare actual and expected state at each allowed boundary.
4. Identify a working local comparison only when it shares the relevant
   contract. Record material differences instead of assuming a pattern applies.
5. State one falsifiable hypothesis: suspected cause, supporting observations,
   predicted result, and the smallest permitted oracle that could refute it.
6. Run or design only that oracle. Classify the result as supported, refuted,
   or inconclusive; keep evidence distinct from the conclusion.
7. Propose one in-scope repair only after a supported root-cause hypothesis and
   only if the packet separately permits repair. Verify that repair with an
   authorized oracle; otherwise escalate with a repair proposal.

Do not stack speculative changes. Apply the packet's retry limit. When no limit
is supplied, stop after two refuted repair attempts and request an architecture
or ownership decision rather than making a third guess.

## Return a diagnostic record

Report to the packet's destination with these distinct fields:

| Field | Include |
| --- | --- |
| Observed evidence | Reproduction status, exact safe oracle output, boundaries checked, and artifact identities. |
| Inference | Hypothesis status and the reasoning limited to observed evidence. |
| Assumptions | Environment, timing, dependency, or comparison conditions not established. |
| Unknowns | Missing data, unavailable layers, or unapproved observations. |
| Recommendation or decision | Continue diagnosis, authorize one repair, seek architecture review, or stop; name the decision authority. |

Do not claim root cause, resolution, or acceptance when the evidence is only
correlative or incomplete.

## Stop and escalate

Stop and report the blocker when the packet is cancelled, reproduction needs an
unapproved side effect, evidence would reveal protected data, the fault crosses
ownership or scope, the hypothesis is inconclusive at the budget limit, or a
repair would need unapproved authority.
