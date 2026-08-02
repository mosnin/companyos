# Company OS 0.5.1 Cancellation Repair Architecture v1

## Exact repair boundary

This repair starts from rejected candidate
`722f5e5bf706d1dd1a48dfbcfacddfff269b7eb1` and tree
`dd164733eb9b970792960566080048e8b567dd01`. Independent review task
`019fc2f8-0465-7db2-9323-762f0537e42c` found a P1 evidence-integrity defect:
`native_task_runtime.py` validates hard-cancellation and acknowledgement values
independently, accepts contradictory pairs, persists them, derives
`cancel_acknowledged`, and audits the retained state as clean.

The implementation remains feature-off and repository-local. It performs no
signing, installation, native task operation, runtime or scheduler activation,
provider call, network access, production mutation, or Chippy action.

## Legal cancellation evidence matrix

| `hard_status` | `acknowledgement_status` | Valid | Meaning |
| --- | --- | --- | --- |
| `acknowledged` | `acknowledged` | yes | explicit host evidence of hard acknowledgement |
| `acknowledged` | `not_acknowledged` | no | contradictory acknowledgement evidence |
| `refused` | `acknowledged` | no | refusal cannot become hard acknowledgement |
| `refused` | `not_acknowledged` | yes | explicit refusal with no hard acknowledgement |
| `failed` | `acknowledged` | no | failed hard cancellation cannot be acknowledged |
| `failed` | `not_acknowledged` | yes | explicit hard-cancellation failure with no acknowledgement |

Only `acknowledged/acknowledged` may derive lifecycle status
`cancel_acknowledged`. Refused and failed observations remain explicit,
non-acknowledged cancellation outcomes and must not be collapsed into success.
Cancellation intent requested, cooperative delivery pending or delivered, hard
acknowledged, hard refused, hard failed, and not-acknowledged evidence remain
distinct projections. Cooperative delivery never invents hard acknowledgement.

## Enforcement layers

The same matrix is enforced before event append, after reduction, during
persistence/load, during store audit, through controller commands, and when
retained lifecycle state is reconstructed by replay. Every legal row retains
its exact payload and authority binding. Every illegal row is rejected before
mutation or makes contradictory persisted/replayed state fail audit. No invalid
attempt leaves partial event, outbox, projection, receipt, or export changes.

The repair preserves cancellation dominance over later success/failure,
explicit-host-evidence requirements, authority-history payload hashes,
duplicate/reordered/deleted/state-only replay rejection, v2 downgrade
rejection, and ambiguous-create restart reconciliation without relaunch.

## Writer isolation

After authenticated design approval, at most two Luna workers may receive
compact v2 packets. One owns runtime semantics and direct/replay tests. One
owns store/controller/integration tests. Workers do not delegate or create
child tasks. The manager inspects both diffs and test evidence, integrates only
accepted work, and is the sole writer of the final distribution-manifest
refresh and the lowercase cancellation-repair report. No path has more than
one writer.

## Master-owned documentation and signature gates

`README.md` and `programs/company-os-self-hosting/LEDGER.md` are deliberately
outside manager and Luna owned scope because mission-charter v2 cannot bind
those uppercase paths without weakening or widening authority. After worker
integration, the master must separately correct the README upgrade example to
bind exact prior release 0.5.0 and distinguish the canonical repository path
from the reviewed worktree path in the ledger. Those corrections are not Luna
deliverables and are not accepted by this charter.

The distribution manifest is refreshed only after accepted lowercase repair
bytes settle. Required store/controller test changes make the current 21-file
signature stale. Master-owned documentation corrections, fresh external
signing, and independent final review are required before release acceptance.
This charter never authorizes signing or installation.
