---
name: company-blueprint
description: Interview an operator, define a versioned company blueprint, and compile it into an elastic organization of departments, capabilities, playbooks, routines, knowledge, assets, integrations, and governed work graphs. Use when initializing Company OS for a new company or materially changing how an existing company operates.
---

# Company Blueprint

Company OS is an organization compiler. Do not dispatch managers until the
company blueprint is concrete enough to explain what the organization is,
which outcomes matter, what it may access, and what it must not do.

## Intake

Ask the operator focused questions about identity, customer, offer, operating
reality, objectives, constraints, authority, brand, existing systems, and
success measures. Resolve contradictions explicitly. Unknowns are allowed only
when they are recorded with an owner and resolution path. `execution_ready`
may be true only when every blocking unknown is resolved.

Use [assets/company-blueprint.example.json](assets/company-blueprint.example.json)
as the canonical shape. Keep credentials out of the blueprint. Database and
integration configuration name environment-variable references and logical
locators, never secret values.

## Compile the organization

Run:

`python3 scripts/compile_company_blueprint.py --blueprint path/to/blueprint.json --output path/to/compiled`

The compiler selects composable department packs from the accepted archetypes
and requested capabilities. It emits a content-addressed organization,
capability map, agent registry, routine plan, work graph, knowledge graph,
asset registry, integration registry, storage plan, and manifest.

Each department pack is a reusable module. It stores agent slots: one middle
or low-level Sol-manager template and staff Luna-worker templates. Created
agents are stored by cloning a slot into a project-local catalog. Slots are
templates, not running threads. Department labels are not dispatch quotas.

Store a created agent without mutating the shared core unless that catalog is
the explicit output:

`python3 scripts/compile_company_blueprint.py --store-agent path/to/slot.json --department engineering-quality --departments path/to/project-department-packs.json --output path/to/project-department-packs.json`

Department count is not fixed. Create departments only when they own a distinct
outcome, decision boundary, or operating system. Manager and Luna capacity is
derived later from the accepted work graph.

## Operating planes

- **Identity plane:** mission, thesis, customers, offers, objectives, values.
- **Organization plane:** departments, interfaces, decision rights, metrics, reusable agent slots. When compiling the organization, load `$corporate-management` and name senior, middle, low-level, and staff tiers.
Do not send `$corporate-management` to Luna workers.
- **Capability plane:** skills, tools, playbooks, models, permissions.
- **Execution plane:** programs, DAGs, leases, budgets, acceptance, recovery.
- **Context plane:** knowledge, brand, assets, content and style references.
- **Integration plane:** MCP, plugins, APIs, repositories, business systems.
- **Learning plane:** execution receipts, business outcomes, exceptions, and
  framework adaptations.

## Activation boundary

Compilation is planning, not runtime activation. Recurring routines are emitted
as `planned`. Enable them only after the project controller, database,
cancellation, idempotency, permissions, and scheduler gates pass. External
writes retain the operator's approval policy.

## Acceptance

Require deterministic recompilation, exact manifest verification, complete
capability coverage, valid dependency edges, no duplicate ownership, no secret
material, explicit storage portability, and a manager-readable summary. A
compiled blueprint is accepted operating context; it is not evidence that the
company or its schedules are running.
