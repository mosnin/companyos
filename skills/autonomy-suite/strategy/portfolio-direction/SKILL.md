---
name: portfolio-direction
description: Choose and govern a focused portfolio of product, business, or engineering bets using evidence, opportunity scoring, explicit tradeoffs, and stop decisions. Use when deciding what to build, defer, fund, scale, pivot, or stop.
---

# Portfolio Direction

<!-- council-os:begin -->
## Board and executive conversations

Company OS owns **owner → board → executives → managers → workers**. Company OS
Web stores business context. At startup/resume the entry conversation loads
`company-board` (`skills/company-os/company-board/SKILL.md` from this distribution)
and reconciles the instance's board conversation in its host project.

The board creates executive conversations with `company-executive`; executives
create manager conversations; managers create Luna worker conversations. Every
management role has its own native thread in the same host project, with explicit
parent/return IDs and message acknowledgements. Executives and managers use
`gpt-6-astra` at `medium` reasoning; workers retain `gpt-5.6-luna`.

Consult `$council` inside the board on strategic direction, major roadmap/resource
changes, pivots/stops and executive conflict. Bind its 17-member deliberation to
the instance, responsible executive, program version and Web context revisions.
Executives record disposition, apply existing dispatch rules, and report measured
results back to the board. Routine work under accepted direction continues.

Follow `company-board` for provisioning and reconciliation. Human authority and
existing execution gates remain; appointments do not enable feature-off schedulers
or permit direct board-to-worker dispatch. Report unavailable host capabilities
honestly. An explicit human waiver is recorded as a waiver, not a council result.
<!-- council-os:end -->


Evaluate customer pain, strategic fit, differentiation, business impact, evidence strength, founder/product insight, reversibility, time-to-learning, technical/operational cost, capacity, and dependency risk.

Classify each bet as active, incubating, deferred, or stopped. Limit active bets. Every active bet needs a target metric, decision owner, review date, kill/pivot criteria, and next learning milestone.

Do not let weighted scores replace judgment. Reserve intentional capacity for a small number of high-conviction, category-creating bets; evaluate them against clarity of thesis, experience potential, learning speed, and strategic asymmetry rather than only existing demand. Record the rationale for tradeoffs and feed only approved slices to project kickoff.

When a bet is a civilizational system, infrastructure network, industrial production system, technological platform, or digital ecosystem, load `$civilization-builder` as the systems overlay. Do not send `$civilization-builder` to Luna workers.

When a bet needs opportunity cost, unit economics, pricing, or TAM/SAM/SOM, load `$economics-architect` as the economics overlay.
Do not send `$economics-architect` to Luna workers.

When a bet needs a business model, value proposition, competitive strategy, or jobs-to-be-done map, load `$business-architect` as the business-architecture overlay.
Do not send `$business-architect` to Luna workers.
