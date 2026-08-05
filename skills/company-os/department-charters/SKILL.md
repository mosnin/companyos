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
- **Operations:** service health, incidents, process, cost/capacity.
- **Customer/Go-to-Market:** only with strict approval for external communications and data access.

Each department may propose work to another. It may not command cross-functional or consequential action without the receiving owner and configured approval. Keep a shared company scorecard and resolve conflicts through explicit decision rights.

Department packs are reusable definitions, not always-running agents. The
accepted program work graph determines which Sol manager outcomes and Luna
worker tasks exist for a particular objective. Scheduled department routines
remain planned until runtime and scheduler activation are separately accepted.

For multi-program companies, `$compile-federated-company-kernel` turns accepted
department boundaries into durable business-unit control cells. A control cell
owns policy, budget, interfaces, and exceptions; it is not one permanently
running manager. Program demand creates peer Sol manager partitions under that
cell, and bounded Luna worker slots are admitted only for runnable tasks. Keep
executive span at nine or fewer direct business-unit cells; split work by real
ownership and interfaces, not by an arbitrary agent ratio.
