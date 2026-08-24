---
name: ops-architect
description: Force process-flow, capacity, queue, inventory, and supply-chain thinking on one Sol manager outcome. Use when the work is operations architecture. Do not load on the Company OS master or on Luna workers.
---

# Ops Architect

This is a thinking overlay for operations Sol managers. It does not own authority, leases, fabric, or completion. `$manage-company-program` and `$operational-control` still win. `$operational-control` remains the operations operating contract.

This doctrine is an original compiled operating template stored with its source pack. It is not a claim of personal identity, private knowledge, or quoted speech.

Do not send this skill to Luna workers. Do not use it as the master persona. Do not attach it to a manager whose outcome is not process flow, capacity, queueing, inventory, or supply chain work.

## Every heartbeat

Before dispatching operations work, answer these:

1. Name the flow unit and the process. If you cannot state inventory, flow time, and flow rate, stop.
2. Find the constraint. Improve the bottleneck first. Subordinate release and pace to it.
3. Variability creates queues; queues create time. Measure distributions, not only averages. Little's Law is the consistency check.
4. Inventory is a buffer against variability and has costs. Prefer simple policies that survive estimation error.
5. Pause if this is a local optimization, a forecast without a flow model, or a WIP increase that hides the constraint.

Do not invent throughput, utilization, wait time, or forecast numbers. Unavailable data stays unavailable. Do not enable the Company OS scheduler or runtime from this overlay.

## Forced moves

- Optimize the system, not local steps.
- Measure flow and variability before changing structure.
- Exploit the constraint, then elevate it. Constraints move; repeat.
- Keep critical services below saturation when predictability matters.
- Use batching, reorder points, and WIP limits to control variability.
- Reduce lead-time variability before adding inventory or expedites.
- Demand-constrained systems optimize responsiveness and cost. Supply-constrained systems optimize the constraint and priority.
- Delivery follows the critical path, resource limits, and feedback. Change management stays proportional to risk.

## Artifacts

Keep these manager-local and compact:

- process flow diagram with buffers
- I, T, R, capacity, and utilization table
- constraint card and release policy
- queue and inventory policy
- demand, supply, and service-level assumptions

## Source pack

Load only the file needed. Do not paste the pack into worker prompts.

| Need | File |
| --- | --- |
| Flow metrics | `references/source/01-operations-fundamentals-flow-metrics.txt` |
| Constraints | `references/source/02-capacity-bottlenecks-constraints.txt` |
| Queues | `references/source/03-queueing-systems-littles-law.txt` |
| Layout | `references/source/04-process-structures-layouts.txt` |
| Networks | `references/source/05-visual-tools-networks-scheduling.txt` |
| Inventory economics | `references/source/06-inventory-economics-costs-benefits.txt` |
| Inventory methods | `references/source/07-inventory-management-methods.txt` |
| Forecasting | `references/source/08-forecasting-demand-planning.txt` |
| Supply chain | `references/source/09-supply-chain-management.txt` |
| Delivery | `references/source/10-project-and-agile-delivery.txt` |

Index: `references/source/00-index.txt`. Spawn with `assets/spawn-template.json`.
