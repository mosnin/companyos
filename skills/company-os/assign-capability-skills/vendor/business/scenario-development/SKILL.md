---
name: scenario-development
description: Develop distinct, evidence-labeled strategic scenarios for one bounded decision. Use when a Company OS packet needs to test options against material uncertainty without presenting forecasts as facts or authorizing a strategic move.
---

# Scenario Development

Create a small set of plausible, decision-relevant futures for one focal question. Do not
predict the future, assign invented probabilities, or execute a recommended strategy.

## Admission

Require the caller's active packet or charter plus:

- a focal decision, accountable decision-maker, geography or operating context, and horizon;
- supplied evidence about current conditions and candidate driving forces;
- a declared decision criterion or the authority to document it as unknown; and
- an authorized local artifact destination if an output file is requested.

Keep the packet's role, ownership, scope, allowed tools and actions, budgets, barriers,
cancellation, reporting destination, and acceptance authority unchanged.

## Controls

- Use local, packet-authorized analysis only. Do not autonomously discover or invoke wrappers.
  Packet-bound companion wrappers explicitly listed in the verified assignment are allowed
  only in `execution_order`; they cannot widen authority, scope, tools, budgets, effects, or
  acceptance. Do not start agents, hooks, installers, provider calls, credentials, mutable
  network research, global writes, deployments, or external activities.
- Treat supplied forecasts and market statements as inputs with provenance, not truth.
- Keep scenarios as decision support; only an authorized decision-maker may choose or fund a
  response.

## Procedure

1. Write the focal question in a decision form, state the horizon, and name the decision owner.
   Stop rather than invent a question that spans unrelated choices.
2. Build a conditions ledger. Separate **Observed evidence** from **Inferences**, **Assumptions**,
   and **Unknowns**; attach source, date, limitation, and potential decision effect to evidence.
3. Identify candidate forces and assess each against a stated materiality and uncertainty
   rubric. Explain why a force was selected or excluded without claiming a forecast.
4. Choose a bounded scenario structure from the admitted inputs. Use two critical uncertainties
   when useful, or a smaller alternative set when the packet requires it; make each scenario
   internally consistent and meaningfully distinct.
5. For each scenario, list operating conditions, what evidence would support or weaken it,
   decision implications, and assumptions that must hold. Do not assign a probability unless an
   authorized model and its source data are supplied; label such output as model-derived.
6. Derive robust options, contingent options, and deferred choices. Mark each as a
   recommendation, specify the authority needed, and never turn it into an action.
7. Define signposts that could update the scenario set. Describe review criteria only; do not
   establish a monitoring service, alert, or recurring task.

## Output

Return one decision-support scenario brief containing:

| Section | Required content |
| --- | --- |
| Packet binding | focal decision, owner, horizon, scope, artifact status |
| Conditions ledger | observed evidence, inference, assumptions, unknowns, limitations |
| Uncertainty selection | rubric, material forces, exclusions, selected structure |
| Scenario cards | conditions, logic, implications, disconfirming evidence, confidence |
| Signposts | observable trigger, interpretation rule, review owner |
| Options | robust, contingent, and deferred recommendations with authority needed |
| Decision ledger | existing decisions, pending choices, and no implied execution |

Describe every scenario as plausible analysis, never as a forecast, customer insight, approved
plan, or external commitment.

## Stop and escalate

Stop when the focal decision or horizon is absent, evidence is too thin to distinguish scenarios,
the caller asks for forecasts or probabilities without an authorized model, or an implication
would trigger spending, contracting, customer outreach, legal advice, production action, or
another external effect. Report the evidence gap and route it to the named authority.

## Capability contract

- Effect: `no_effect`; permissions: none (`[]`).
- Consumes: `business_context`, `uncertainty_evidence`; produces: `scenario_set`.
- Provider boundary: `none; output cannot authorize action`.
