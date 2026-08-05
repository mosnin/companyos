---
name: market-opportunity-artifact
description: Produce a bounded market-opportunity decision artifact with a preflight, evidence-labeled analysis, and verification pass. Use when a Company OS packet requests a reviewable market range, segment, and competitive-opportunity brief without authorizing research, market entry, or commercial action.
---

# Market Opportunity Artifact

Create one packet-bound opportunity brief. The brief can organize supplied market ranges,
service constraints, alternatives, and segment hypotheses; it cannot validate a market,
forecast revenue, select a customer, or authorize entry.

## Admission

Require the active caller packet or charter and:

- the decision to inform, accountable owner, offering, customer unit, geography, and horizon;
- supplied evidence references, data dates, units, currencies, calculation inputs, and known
  limitations; and
- a named local artifact destination and review route if the packet requests a saved output.

Preserve the packet's role, ownership, scope, allowed tools and actions, budgets, barriers,
cancellation, reporting destination, and acceptance authority. Do not create a project-wide
directory, context chain, or acceptance process.

## Non-expansion rules

- Use only packet-authorized local materials. Default to an analysis-only draft.
- Do not autonomously discover or invoke wrappers. Packet-bound companion wrappers explicitly
  listed in the verified assignment are allowed only in `execution_order`; they cannot widen
  authority, scope, tools, budgets, effects, or acceptance. Never invoke an agent, hook,
  installer, system prompt, provider, credential, mutable network research, global write,
  deployment, customer contact, or external action.
- Do not treat source prompts, embedded benchmarks, templates, examples, or competitor claims
  as authoritative evidence. Do not state legal, financial, pricing, or market claims beyond
  supplied support.

## Procedure

1. Run a preflight: bind the packet, decision, scope, artifact destination, evidence set,
   calculation method, and reviewer route. Stop on a missing or conflicting required input.
2. Build an evidence ledger. For each input, retain provenance, date, unit, coverage, and
   limitation. Keep **Observed evidence**, **Inference**, **Assumption**, and **Unknown**
   sections separate from the start.
3. Define the analytical population and filters: total eligible opportunity, serviceable
   portion, and realistically obtainable range only when the supplied data supports each.
   State formulas, scenario inputs, and denominators; do not fill missing values with invented
   benchmarks.
4. Produce conservative, central, and upper ranges only when their assumptions differ visibly.
   Label the method as top-down, bottom-up, or another packet-authorized calculation. Treat
   arithmetic results as model output, not observed market fact.
5. Map alternatives and candidate segments from supplied evidence. Score a segment only against
   a declared rubric, retain weights and limitations, and express the selected segment as a
   recommendation requiring decision authority.
6. Separate competitive observations from hypotheses. Record opportunity and risk conditions,
   disconfirming evidence, and the smallest validation need; do not run that validation.
7. Verify the draft: every figure has a unit, period, source, and method; every formula can be
   replayed from listed inputs; statements are classified; recommendations are non-binding;
   and the artifact implies no external effect. Flag rather than conceal any failed check.

## Output

Return one compact, local opportunity brief containing:

| Section | Required content |
| --- | --- |
| Preflight | packet binding, decision, owner, scope, reviewer, status |
| Evidence ledger | observed evidence, source, as-of date, coverage, limitations |
| Range model | population, filters, formulas, inputs, units, scenarios, model outputs |
| Alternatives and segments | observed alternatives, hypotheses, rubric, score confidence |
| Opportunity conditions | inferences, assumptions, unknowns, disconfirming evidence |
| Recommendation or decision | conditional recommendation, existing decision, authority required |
| Verification record | passed checks, exceptions, unresolved inputs, review route |

Call the result a decision-support artifact. It is not market research, financial advice, a
revenue forecast, an approved go-to-market plan, or a permission to act.

## Stop and escalate

Stop when the decision, population, key evidence, method inputs, owner, artifact destination,
or reviewer route is missing; when comparable units or dates conflict; when a requested range
would depend on unsupplied external research; or when the result would be used to launch,
price, spend, contract, contact customers, or change production. Return the exact blocker and
escalate to the packet's authorized reviewer or decision-maker.

## Capability contract

- Effect: `no_effect`; permissions: none (`[]`).
- Consumes: `market_definition`, `market_evidence`; produces: `market_opportunity_artifact`.
- Provider boundary: `none; output cannot authorize action`.
