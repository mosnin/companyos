# Company OS 0.5.0 native-role forward test

Date: 2026-08-02  
Decision: accepted for the bounded evidence package only  
Runtime/provider/scheduler decision: NO-GO

## Outcome

Prove that the globally installed 0.5.0 role skills can run the intended native
hierarchy without embedding the Company OS manual in every prompt:

`master -> Sol manager -> two tasks requested as GPT-5.6 Luna -> manager verification -> gated integration -> master acceptance`

## Native tasks

| Role | Native task | Requested model | Observed executing model | Disposition |
| --- | --- | --- | --- | --- |
| manager | `019fc20a-4b45-71c2-a686-6eaca74efb2f` | `gpt-5.6-sol` | unavailable | accepted |
| reference audit | `019fc212-8179-7c02-b62b-545b61f57ccf` | `gpt-5.6-luna` | unavailable | accepted |
| model-evidence audit | `019fc212-8a5c-7031-bcb9-358a82c56558` | `gpt-5.6-luna` | unavailable | accepted |

The task creation records configure/request the named models. They are not
provider-runtime attestations, so observed executing-model identity remains
unavailable.

## Prompt and authority proof

- The manager prompt contained `$manage-company-program`, the artifact root,
  and one compact `company-os.mission-charter.v2` object.
- Each worker prompt contained `$execute-bounded-task`, the artifact root, and
  one compact `company-os.work-packet.v2` object.
- No task received the root transcript or a repeated Company OS manual.
- The manager stopped at design, verification, and final integration barriers.
- Worker packets narrowed parent scope, permissions, tools, prohibitions, and
  all six budgets and returned only to the exact native manager task.

## Accepted artifacts

| Artifact | SHA-256 |
| --- | --- |
| reference audit | `45b296f3ccfb2b717d5056d662380b5bb13bf044bcf1af87941e5eb8a0c67ae5` |
| model-evidence audit | `468c40705eb7e661c403094f1407d40c0f45490bce5973e222e9f6d669cb250b` |
| integration summary | `42399c72fdcce018098ce2c9ba4c4e29a05f58fcedf62b83766c5d426c0790a4` |

The manager re-read both native worker tasks, revalidated both packets,
recomputed both worker artifact hashes, checked disjoint writer scopes and
unexpected files, then integrated only the accepted artifacts. It explicitly
left program acceptance to the master.

## Independent gates

- Verification audit: 0 P0, 0 P1, 0 P2; GO.
- Final integration audit: 0 P0, 0 P1, 0 P2; ACCEPT.
- No extra task, rework task, external message, deployment, production
  mutation, scheduler action, symlink, cache, or bytecode artifact was observed.

## What this proves

- Global manager and worker skills are discoverable and byte-identical to the
  accepted 0.5.0 source.
- Compact charter/packet prompts can drive a real native manager/worker task
  tree with explicit phase barriers, disjoint work, manager inspection, and
  final master acceptance.
- Requested and observed model evidence remain separated.

## What remains unproven

- Controller admission before native task creation.
- Hard cancellation acknowledgement and durable task reconciliation.
- Provider-observed executing model identity.
- Attributable token and cost telemetry.
- Provider, production, customer-environment, or scheduler behavior.
- Recursive self-improvement under controller-governed state.
