---
name: mcp-tool-contract-design
description: Design a single bounded Company OS MCP tool contract with explicit schemas, effects, errors, and verification cases. Use when an authorized task needs a tool-design artifact without building a server, installing an SDK, or calling a service.
---

# MCP Tool Contract Design

Use this capability for one proposed tool. Do not use it to design a generic
server, discover remote APIs, register a tool, or autonomously invoke an
unassigned wrapper.

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

## Admit one tool contract

Require:

- One user outcome, one named resource boundary, and one tool owner.
- The exact allowed effect class: no effect, read, local write, or named
  external write.
- Supplied authorization source, data classification, scope limits, and retry
  or idempotency expectation.
- A known reporting destination and acceptance authority.

Stop rather than infer protocol details, authentication, remote API behavior,
or a write authorization from a tool argument.

## Design the contract

1. Name one action-oriented tool and state its purpose, non-goals, caller, and
   resource boundary. Split unrelated actions into a decision request rather
   than adding convenience operations.
2. Define input fields, requiredness, types, bounds, defaults, and invalid
   input handling. Reject ambiguous identifiers and unbounded collection sizes.
3. Define success output as stable structured fields. Separate display text
   from machine-readable result fields; omit secrets and unnecessary data.
4. Declare effect semantics: read-only status, state mutation, idempotency key
   treatment, duplicate behavior, ordering, and cancellation boundary. Require
   a separately authorized decision for irreversible or external effects.
5. Define stable error classes for invalid input, unauthorized caller, denied
   effect, not found, conflict, transient dependency, and internal failure.
   Include safe remediation, not sensitive implementation detail.
6. Define bounded verification cases: valid request, invalid schema, denied
   authorization, denied effect, duplicate or retry, and relevant state
   conflict. Describe expected results only unless execution is authorized.

## Return a contract record

Report to the packet's destination with these distinct fields:

| Field | Include |
| --- | --- |
| Observed evidence | Supplied packet facts, resource limits, and existing local contract evidence. |
| Inference | Why the proposed schema and effect model satisfy the stated outcome. |
| Assumptions | Transport, identity propagation, storage, or dependency behavior not proven. |
| Unknowns | Missing authorization, lifecycle, error, or data-retention facts. |
| Recommendation or decision | Revise, seek policy, implement under separate authority, or stop; name the decision authority. |

Do not claim a server, tool, or external integration exists from a contract.

## Stop and escalate

Stop and report the blocker when one tool would cross multiple ownership
boundaries, effect authority is unclear, required data is sensitive without an
approved handling rule, verification needs a provider call, or cancellation
applies.

## Capability contract

- Effect: `no_effect`; permissions: none (`[]`).
- Consumes: `integration_requirements`, `tool_policy`; produces: `mcp_tool_contract`.
- Provider boundary: `provider_neutral_design; no tool/provider execution`.
