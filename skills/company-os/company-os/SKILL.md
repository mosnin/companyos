---
name: company-os
description: Coordinate a lightweight autonomous company operating system across strategy, project/program management, operations, and functional departments. Use when work needs direction, roadmaps, goals, monitoring, operating cadence, and cross-functional execution beyond individual agent loops.
---

# Company OS

Use this as the control layer above the Autonomy Suite. It runs the company operating rhythm; it does not replace human leadership or grant agents unrestricted authority.

## Pillars

| Pillar | Responsibility | Skill |
| --- | --- | --- |
| Outcome control plane | Own a broad objective end to end: discovery, executable outcome contracts, a real candidate, just-in-time independent evaluation, bottleneck rework, organization mutation, and execution-bound reality acceptance. The single master entry point; the per-stage skills (`$bootstrap-outcome`, `$close-outcome-discovery`, `$synthesize-outcome-model`, `$materialize-outcome-stack`, the `$compile-outcome-*` / `$build-outcome-evaluators` / `$calibrate-outcome-*` evaluator lifecycle, `$run-outcome-loop`, `$accept-outcome-reality`, `$authorize-outcome-scale`) are its subordinate steps, not separate entry points | `$direct-outcome` |
| Company blueprint | Compile identity, objectives, organization, capabilities, routines, knowledge, assets, integrations, and storage | `$company-blueprint`, `$civilization-builder`, `$corporate-management` |
| Loop strategy | Select one finite task-shaped feedback loop and compatible diagnostic, learning, or event adapters | `$select-execution-loop` |
| Strategy and portfolio | Decide what matters and what stops | `$strategy-pillar`, `$portfolio-direction`, `$business-architect`, `$civilization-builder`, `$economics-architect` |
| Project and program management | Turn bets into accountable roadmaps | `$project-program-management`, `$project-kickoff-roadmap`, `$project-manager` |
| Operations | Run metrics, incidents, process health, and continuous improvement | `$operational-control`, `$ops-architect` |
| Functional departments | Define mandates, interfaces, decisions, and service levels | `$department-charters`, `$corporate-management`, `$corporate-departments`, `$hr-architect` |
| Brand and creative | Keep product, language, content, and motion cohesive and differentiated | `$brand-creative-system`, `$brand-architect`, `$steve` |
| UI design quality | Require high-craft interaction, motion, accessibility, responsive, performance, and visual evidence for every interface change | `$ui-design-quality`, `$design`, `$interface-design`, `$steve` |
| Capability library | Discover and bind a minimal audited skill bundle without loading the whole library into agent context | `$assign-capability-skills` |
| Commercial and customer | Connect discovery, adoption, sales, support, and retention to decisions | `$commercial-customer-system`, `$marketing-architect`, `$sales-architect`, `$steve`, `$value-creation-delivery` |
| Research and intelligence | Gather evidence, customer signal, tech options, and innovation bets | `$research-intelligence` |
| Mission dispatch loop | The single dispatch-boundary control layer: enforce First Reality scope, work admission, planning-budget metering, hard deadlines, scheduler leases, evidence-bound capability state, replacement, and product checkpoints. Route compilation (`$goal-route-system`), navigation (`$navigation-control`), and the executive governor (`$govern-outcome-execution`) run programmatically inside its controller — they are internal mechanisms, not additional dispatch skills to load | `$mission-execution-control` |
| Execution | Deliver work through Sol manager tasks and bounded Luna labor with early real artifacts, runtime observation, targeted rework, verification, and decisions | `$manage-company-program`, `$execute-bounded-task`, `$force-first-execution`, `$autonomy-suite`, `$luna-execution-fabric` |
| Elastic control | Create an isolated project operating model and improve it through independently reviewed feedback | `$elastic-company-os` |
| Hosted company ledger | Pull and write shared company context through one company-os-web MCP across Claude, ChatGPT Work, and Grok | `$company-context-ledger` |

## Project isolation

Use `$elastic-company-os` to create one `.company-os/` instance per project. The shared Company OS is the governed core; it is not a shared project ledger. Keep each project's strategy, product reality, metrics, departments, cadence, work, and adaptations inside that project's instance.

Before creating the first project instance for a company, use
`$company-blueprint`. Interview the operator until mission, thesis, customers,
offers, objectives, constraints, authority, brand, knowledge, systems, and
blocking unknowns are concrete. Compile the accepted blueprint into department,
capability, playbook, routine, work-graph, knowledge, asset, integration, and
storage artifacts. The blueprint describes the company; project instances
execute bounded programs inside it.

An instance may adapt its operating method through evidence-backed, reversible experiments. It may not autonomously expand authority, weaken approvals, change cancellation precedence, mix project data, or approve its own adaptations. Promote a pattern into the shared core only after it improves at least three independent project instances and passes independent review.

## Outcome executive governor

For every autonomous build mission, the controller runs ONE dispatch loop: `$mission-execution-control`. Its `mission_control.py` compiles the goal route once at mission start (`$goal-route-system`) and, at every dispatch, retry, wake, evidence, expansion, evaluation, and packaging boundary, programmatically evaluates the navigation module (`$navigation-control`) and the executive governor (`$govern-outcome-execution`). Masters and managers load exactly one control skill at the dispatch boundary — never the four layers side by side; the other three are internal mechanisms of that loop. Every master, manager, submanager, and worker receives a content addressed goal contract and route assignment; a prompt alone is not an executable goal. These decisions are enforced state, not optional manager advice. The original objective is the destination; research, audits, tests, browser/runtime observations, and reports are sensors; implementation, integration, runtime execution, repair, checkpointing, and packaging are actuators. The governor is the mission-level CEO/COO/CFO function above local managers.

Maintain an explicit **Reality Map** from the original user objective to observable capabilities. Classify the strongest state reached as R0 research/design, R1 internal primitives, R2 isolated runnable capability, R3 connected vertical behavior, R4 fresh-user usable outcome, or R5 independently accepted outcome.

The master must always name the **global bottleneck**: the missing capability whose completion most increases the probability of the original objective becoming real. Managers may optimize local work, but resources follow the global bottleneck.

For build missions, target R3 before roughly 25% of the mission resource budget is consumed. Missing that boundary is an execution incident. The master pauses broad research, speculative architecture, benchmark expansion, noncritical documentation, and governance refinement and redirects capacity to implementation, integration, runtime, and repair.

Use mission modes:

- **NORMAL:** enough discovery to act, while a real product lane starts immediately.
- **COMPRESSION:** research/design/governance shrink because reality progress is lagging burn.
- **CRITICAL_PATH:** only blockers to a fresh user-usable outcome receive substantial resources.
- **REALITY_CLOSURE:** near budget exhaustion, start nothing new; integrate, run, fix, verify, package, and checkpoint.

A green document review cannot cancel an execution incident. Reality advances from actual artifact behavior.

Prefer supplied capabilities over reimplementation. If the user provides a repository, SDK, provider, or framework that already implements a required capability, inspect, integrate, and exercise it first. A replacement requires specific blocker evidence. This prevents an agent from solving an adjacent problem because writing new infrastructure is easier than learning the requested system.

Product bytes are first-class durable state. Tested, bounded product increments should be checkpointed or committed promptly; governance records must never be more durable than the actual product they govern.

## Company rhythm

- **Daily operations review:** material exceptions, customer impact, delivery risks, blocked work, budget, and decisions.
- **Weekly portfolio/program review:** priorities, milestones, outcomes, dependencies, resourcing, and continue/pivot/stop decisions.
- **Monthly operating review:** scorecard trends, process health, risk, learning, and strategic adjustments.

Use `$company-scorecard` as the ChatGPT Work decision dashboard. It should link evidence and exceptions from every pillar instead of presenting unsupported status colors.

Use an exception-based model: report decisions and deviations, not ritual status. Every meeting or loop must update a decision record, metric, or next action.

For a multi-manager delivery program, the primary thread acts as the Company OS
master. It versions the Program Contract, spawns one Sol manager thread per
bounded roadmap outcome, and receives a compact report at charter, discovery,
design, execution, verification, and integration. Managers use
`$manage-company-program`, `$middle-manager-operating-doctrine`, and
`$luna-execution-fabric`; workers use `$execute-bounded-task`. Send the
manager role skill, the middle-manager doctrine, and one compact mission
charter. Send workers only the worker packet. Do not use the doctrine as the
master persona or repeat the operating system in every prompt.

When the manager outcome is product design, brand, user experience, or customer
experience, also send `$steve`.
When the manager outcome is brand system, positioning, identity, voice, or
presence, also send `$brand-architect`.
When the manager outcome is a civilizational system, infrastructure network,
industrial production system, technological platform, or digital ecosystem,
also send `$civilization-builder`.
When the manager outcome is interaction design, service design, problem
framing, prototyping, or user understanding, also send `$design`.
When the manager outcome is market strategy, segmentation, go-to-market,
advertising, or growth lifecycle, also send `$marketing-architect`.
When the manager outcome is prospecting, qualification, discovery, pipeline,
or closing, also send `$sales-architect`.
When the manager outcome is opportunity cost, unit economics, pricing, market
sizing, or market structure, also send `$economics-architect`.
When the manager outcome is process flow, capacity, queueing, inventory, or
supply chain, also send `$ops-architect`.
When the manager outcome is hiring, recruiting, org design, onboarding, or
performance management, also send `$hr-architect`.
When the manager outcome is business model, competitive strategy, value
proposition, jobs-to-be-done, or market analysis, also send
`$business-architect`.
When the manager outcome is project scoping, phase planning, work breakdown,
risk management, or execution workflow, also send `$project-manager`.
When the manager outcome is value creation, offer architecture, value
validation, value delivery, or scaling a delivery system, also send
`$value-creation-delivery`.

When compiling a company or spawning a multi-manager program, also send
`$corporate-management` and name each actor as senior, middle, low-level, or
staff. When compiling named departments, also send `$corporate-departments` to
the department manager. When compiling Marketing, also send `$marketing-os` to
that department manager. When a hosted company-os-web ledger is in use, send
`$company-context-ledger` to the master or department manager that will pull or
write company context. The ledger is not a control plane.

Do not send `$steve` to workers. Do not send `$brand-architect` to workers. Do
not send `$civilization-builder` to workers. Do not send `$design` to workers.
Do not send `$marketing-architect` to workers. Do not send `$sales-architect`
to workers. Do not send `$economics-architect` to workers. Do not send
`$ops-architect` to workers. Do not send `$hr-architect` to workers. Do not
send `$business-architect` to workers. Do not send `$project-manager` to
workers. Do not send `$value-creation-delivery` to workers. Do not send
`$corporate-management` to workers. Do not send `$corporate-departments` to
workers. Do not send `$marketing-os` to workers. Do not send
`$company-context-ledger` to workers. These overlays and corporate skills are
not the master persona.

Executable delegation stays master → manager → worker.
Managers may not change the project
strategy, roadmap ownership, or authority. Company OS accepts the integrated
program; manager and worker activity is not company progress by itself.

The organization is elastic. Derive manager count from independently
accountable outcomes, interfaces, and departments in the accepted work graph;
derive each manager's Luna team from its dependency DAG. Never collapse
unrelated lanes to fit a fixed agent ratio. Declared capacity and active
concurrency are separate controls: a program may admit 30 managers with 10
workers each while initially running only a bounded subset. Increase or reduce
active slots from acceptance, collision, recovery, latency, provider, and
budget evidence without rewriting the program's real ownership structure.

Before dispatch, the master must publish a compact execution baseline: required
lanes, intended manager ownership, intended Luna labor, concurrency limit,
single-thread comparison when available, required artifacts, and the timestamps,
model observations, token fields, cost fields, and quality fields it expects the
host to expose. After dispatch, read the actual task tree rather than trusting a
launch message. A host-cap consolidation is a named variance and must preserve
complete lane ownership; it is not another independent manager.

Before finalizing each manager charter, use `$select-execution-loop` to bind one
primary loop to the manager outcome. Select from task evidence such as
recurrence, parallel lanes, uncertainty, traces, novelty, durable events, and
failure cost. Add diagnostic, learning, or event adapters only when their
required evidence exists. The loop plan must preserve mandatory requirements,
finite limits, independent acceptance, and the existing Company OS authority
chain. External loop runtimes are not automatically installed or activated.

The Program Contract separates **mandatory user requirements** from manager
recommendations. A manager may challenge a technology or propose a narrower
phase, but may not silently delete, invert, or replace a mandatory requirement.
If the user asks for an agent, recurring runners, a named technology, or a
specific client offer, the final artifacts must cover it or the master must stop
for an explicit change decision. Calling the manager's preferred alternative an
"MVP" does not change the accepted outcome.

Resolve capabilities before manager dispatch and bind the selected capability
IDs to each artifact plan. Use the host's current available-skill registry for
first-party, installed, and plugin skills; use `$assign-capability-skills` for
the governed external catalog. A proposal, PRD, technical architecture,
spreadsheet, UI, or other specialized artifact must receive its required domain
and artifact-production skills. At acceptance, verify applied capability
receipts against the plan. Reading a general Company OS skill is not evidence
that the proposal, offer-design, product-requirements, research, or document-
production capability was used.

Every accepted multi-manager program must produce a
`company-os.execution-efficiency-receipt.v1` and validate it with the Company
Scorecard verifier. The receipt binds semantic artifact identity—kind, title,
external ID, and owner lane—to independent readback. This prevents a correct
artifact from being credited to the wrong page, file, or manager. A deliverable
may be accepted while efficiency or scaling remains unproven; never average
missing runtime evidence into a green score.

The receipt also binds mandatory requirements and required capability IDs to
each artifact. Unsatisfied requirements, missing required skills, incomplete
artifacts, or an acceptance decision below the contract's required authority
make delivery unaccepted. Fast materialization of rejected artifacts is zero
accepted throughput.

Managers should route bounded research, drafting, implementation, formatting,
and verification labor to Luna. Manager-authored labor is a disclosed execution
variance unless the task is inherently managerial or dispatch would duplicate
already completed work. Never redo accepted work merely to manufacture Luna
utilization. Zero observed Luna workers means the run cannot prove the Luna
fabric, even when its deliverables are excellent.

Before Program Preflight, resolve every specialized artifact against both skill
planes. Select the smallest exact set of current host skills, then use
`$assign-capability-skills` only for external additions. Search metadata by
separate domain, artifact-production, named-tech, and review needs; bind exact
host skill names plus external assignment digests into task evidence. Never
paste the whole registry, catalog, or external skill collection into a prompt.
Selecting no skill is valid only when the artifact has no required specialized
capability. If the only matches are unavailable, reference-only, quarantined,
or unapproved, stop with a named capability gap rather than pretending generic
reasoning satisfied it. A skill may not grant tools, permissions, budget, or
side effects.

Use `$force-first-execution` inside every delivery lane. Planning, commentary,
thread count, tests without an artifact, and receipts without an accepted
deliverable are not progress. The manager tracks first materialization,
runnable candidate, verification, direct inspection, receipt, and decision;
soft speed misses remain visible while hard safety stops remain authoritative.

Any program that creates, changes, prototypes, or reviews a user interface must
use `$ui-design-quality`. When building digital interfaces, also load
`$interface-design` for typography, color, layout, writing, accessibility,
UI polish, and distinctive visual identity. `$ui-design-quality` remains the
evidence gate. Classify UI manager
and worker packets as
`ui_design`, require host capability `ui_design_quality`, and retain the exact
vendored-suite revision in evidence. Program Preflight fails closed when UI
signals appear without that classification or capability. A passing code check
or screenshot alone is insufficient: the independently reviewing manager must
run and inspect the interaction, accessibility, responsive states, motion, and
performance before integration.

When the project uses an Elastic Company OS instance, this hierarchy is
controller-governed state. Queue the primary work with
`--execution-mode luna_fabric`, configure the validated project-local manifest,
record each manager phase report, and require a separately authenticated master
decision at the charter, design, verification, and final-integration barriers.
Silence never grants a barrier decision; a bounded wait escalates instead of
deadlocking. Routine execution subphases inside an unchanged, already accepted
charter may auto-continue only after design acceptance and before verification
when every check, budget, concurrency, and authority condition passes. Every
subphase remains visible. The controller rejects phase skips, stale programs,
self-approval, write collisions, unreviewed verification, and completion before
every manager integration is accepted.

Do not enable recurring project work until the instance controller validates product/project reality, direction, measurable outcome, evidence gates, one active controller, and cancellation. A recurring wake runs one bounded cycle inside the same project controller; it does not create a new operating thread as its durable state.

## Authority

Separate recommendation, approval, execution, and audit. Agents may observe, analyze, propose, and perform pre-authorized low-risk work. Require an approval for customer-facing, financial, legal, privileged, irreversible, or production-impacting actions.

## Method selection

Choose the lightest method that fits uncertainty:

- Use discovery and short experiments for uncertain problems.
- Use iterative delivery for evolving products.
- Use stage-gated plans for regulated, high-risk, or dependency-heavy work.
- Use a hybrid when discovery and deterministic implementation coexist.

When the work is a testable belief rather than a delivery slice, bind a
`company-os.scientific-method-packet.v1` and follow
[references/scientific-method.md](references/scientific-method.md). The packet
is a checklist over existing outcome, bet, and adaptation records. It does not
own iteration, leases, or completion.

When optimizing a named bottleneck, bind a
`company-os.riocl-tc-packet.v1` and follow
[references/riocl-tc.md](references/riocl-tc.md). This is the default
bottleneck-optimization overlay. The packet is a checklist over the existing
governor, navigation, and adaptation records. It does not own iteration,
leases, or completion.

Do not force Agile or Waterfall as identity. Define decision cadence, evidence gates, and flow constraints for the actual work.

## Recursive reusable skills

Use `$recursive-skill-foundry` as the project local learning and capability compounding layer. Search promoted project skills before external capability selection. Forge a new skill only when the user explicitly requests one, the active navigation route is concretely blocked by a missing reusable mechanism, or accepted field evidence proves repeated reuse value.

A skill candidate is not product progress unless skill creation is the original destination. For normal product missions, finish and checkpoint the real route first, then capture the reusable mechanism. Project skills install under `.agents/skills`, remain content addressed, and must be verified before assignment. Learned mechanisms require two accepted independent uses. Shared core promotion requires three independent projects plus fresh independent review and is never automatic.
