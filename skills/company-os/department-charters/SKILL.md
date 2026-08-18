---
name: department-charters
description: Define coordinated human and agent departments with clear mandates, decision rights, interfaces, metrics, safeguards, and escalation paths. Use when organizing a mini autonomous company or cross-functional agent organization.
---

# Department Charters

Create a charter before creating a department or agent team.

## Charter fields

- Mission and customers served.
- In-scope work and explicit exclusions.
- Inputs, outputs, service levels, and interface contracts.
- Decision rights and approval boundaries.
- Allowed tools/data and prohibited actions.
- Success metrics, budget, capacity, and quality bar.
- Escalation, incident, audit, and shutdown path.

## Composable department packs

Use `$company-blueprint` to select department packs from company archetypes and
requested capabilities. Start lean, but never combine unrelated decision
boundaries merely to fit a fixed manager count. A department is accepted only
when its capabilities, playbooks, tools, routines, metrics, inputs, outputs,
interfaces, approvals, and shutdown path are concrete.

Common foundations include:

- **Strategy & Product:** direction, research, portfolio, customer outcomes.
- **Program Management:** roadmaps, dependencies, plans, decision records.
- **Engineering & Quality:** implementation, testing, reliability, security review.
- **Marketing:** demand, campaigns, positioning; separate from Sales.
- **Sales:** qualification, pipeline, revenue conversion.
- **Operations:** service health, incidents, process, cost/capacity.
- **Finance:** cash truth, forecast, allocation.
- **Human Resources:** roles, hiring plans, org slices; no invented headcount.
- **Customer Success / Brand / Security-Legal:** value realized, brand system, controls.

Load `$corporate-departments` on the department manager for issue trees and
function doctrine. Do not send `$corporate-departments` to Luna workers.

Each department may propose work to another. It may not command cross-functional or consequential action without the receiving owner and configured approval. Keep a shared company scorecard and resolve conflicts through explicit decision rights.

Department packs are reusable modules, not always-running agents. Each pack
stores agent slots for a middle or low-level manager and staff workers. Store
a created agent as a cloned slot with `origin=stored`; do not invent a new
fabric role or a live thread. The accepted program work graph determines which
slots are instantiated for a particular objective. Scheduled department
routines remain planned until runtime and scheduler activation are separately
accepted.

When chartering departments, load `$corporate-management` and name each department manager as middle or low-level. Staff remain Luna workers.
Do not send `$corporate-management` to Luna workers.
