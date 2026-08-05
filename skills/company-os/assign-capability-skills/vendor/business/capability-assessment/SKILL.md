---
name: capability-assessment
description: Assess a bounded set of internal capabilities with traceable evidence and scoring. Use when a Company OS packet needs a gap and priority view for one strategic objective without authorizing investment or operational changes.
---

# Capability Assessment

Assess the ability of one named unit to support one authorized objective. This is an internal
decision-support record, not a performance verdict, benchmark claim, hiring plan, or funding
decision.

## Admission

Require an active caller packet or charter and these inputs:

- objective, decision to inform, accountable owner, and organization or unit in scope;
- five to eight capability areas or a packet-authorized method for selecting fewer;
- a defined scoring rubric, target state, and supplied evidence; and
- a local artifact destination only if the packet authorizes writing one.

Retain the packet's role, scope, allowed actions, budgets, barriers, cancellation, reporting
destination, and acceptance authority. Do not broaden a score into an approval.

## Operating boundary

- Use supplied internal materials only unless the packet explicitly authorizes another exact
  local source. Do not gather external benchmarks by default.
- Do not autonomously discover or invoke wrappers. Packet-bound companion wrappers explicitly
  listed in the verified assignment are allowed only in `execution_order`; they cannot widen
  authority, scope, tools, budgets, effects, or acceptance. Do not call agents, hooks,
  installers, systems, providers, credentials, or mutable network services; do not create
  global files, deploy, or execute a recommendation.
- Treat named benchmarks, stakeholder opinions, and self-reports as inputs with limitations,
  not objective fact.

## Procedure

1. Bind the assessment to one objective, time horizon, owner, and decision. Reject a vague
   request to rate an entire company.
2. Define each capability and each score level before scoring. State the target condition and
   the scoring scale's meaning; do not alter it after seeing results.
3. Assemble an evidence row for each capability: source, observation date, scope, quality,
   and limitation. Separate direct observations from stakeholder interpretations.
4. Score only against the declared rubric. Mark a score as an **Inference** when it requires
   judgment; mark an unsupported input as an **Assumption**; leave insufficiently supported
   areas as **Unknown** rather than inventing precision.
5. Calculate a gap only from comparable current and target scores. If a comparator is used,
   label its provenance and comparability; never call it best-in-class without evidence.
6. Order candidate investments by stated impact, urgency, feasibility, and confidence. Keep
   the weighting visible. Label the result a recommendation, not a budget or operating order.
7. Check that no visual summary hides uncertainty, a low-confidence score, or an excluded
   capability. Use a table instead of a chart when the evidence cannot support a chart.

## Output

Return one compact assessment containing:

| Section | Required content |
| --- | --- |
| Packet binding | objective, owner, scope, audience, decision |
| Scoring contract | capability definitions, scale, target, weighting |
| Evidence ledger | observed evidence, provenance, date, limitations |
| Score table | current score, confidence, inference or assumption flag, target, gap |
| Unknowns | absent evidence, disputed scores, and impact on use |
| Priority candidates | rationale, dependency, proposed owner, and non-binding recommendation |
| Decision record | decisions already authorized versus decisions still needed |

Do not state that a target, comparator, priority, or maturity score is verified unless its
supporting evidence says so.

## Stop and escalate

Stop when a scoring rubric, owner, objective, or evidence source is missing; when a requested
comparison would require unsupplied external data; or when the result is being used to trigger
hiring, spending, restructuring, customer, legal, or production action. Report the smallest
missing input and the designated authority required to continue.

## Capability contract

- Effect: `no_effect`; permissions: none (`[]`).
- Consumes: `business_context`; produces: `capability_assessment`.
- Provider boundary: `none; output cannot authorize action`.
