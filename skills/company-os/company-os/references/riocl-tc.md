# RIOCL TC playbook

This is the default bottleneck-optimization overlay on existing Company OS
contracts. It does not own iteration, leases, fabric, completion, or authority.
Do not add a seventh primary loop or a second bottleneck store.

Right rules, fast truth, real bottleneck, safe leverage, one action, reality
updates, repeat.

## Mapping

| Step | Existing record | Next governed action |
| --- | --- | --- |
| Boundary and flow | Reality Map, lane, or Elastic instance | Shrink the frame until one flow is controllable |
| Regime identification | `$govern-outcome-execution` mode plus exploration or exploitation | Obey the current rule set. If the regime is unclear, default to exploration and test |
| Time compression | `$force-first-execution`, pull-based research | Shorten the slowest feedback path without raising fragility |
| Outcome, constraints, bottleneck | Global bottleneck on the master heartbeat | One dominant outcome, at most two binding constraints, one bottleneck |
| Time horizon | Mission budget, deadline, and actor clocks | Name clock mismatch; do not optimize a local clock against the original objective |
| Incentive and reversion | Receipts, scorecard, and authority | If change will revert, add an incentive fix, downgrade to a test, or redesign |
| Expected-value gate | Authority barriers and survivability | Discard any move with non-survivable downside |
| Phase check | Reality Level R0-R5 | Before the threshold, cross it. Do not polish documents before R3 |
| One action | `$navigation-control` `next_action` | Delete, simplify, accelerate, then automate last |
| Update | Evidence-bound state and receipts | Ask whether the bottleneck moved. Rejected commands must not mutate governed state |

## Decision modes

Each loop produces exactly one output. Map it to an existing action.

| Mode | Meaning | Allowed `next_action` |
| --- | --- | --- |
| `do_nothing` | Keep observing | `observe` |
| `test` | One reversible falsification | `close_outcome_discovery`, `evidence_research_campaign`, `select_execution_loop`, `execute_outcome_evaluator` |
| `execute_leverage` | One move on the bottleneck | `force_first_execution`, `run_outcome_loop`, `rework`, `direct_outcome` |
| `redesign` | Change the subsystem, not the symptom | `compile_outcome_organization`, `propose_adaptation`, `review_adaptation` |

`observe` is a non-mutating keep-watch action. It does not grant leases, launch
runtime, or complete work.

## Hard stops

- If the regime cannot be tagged, default to exploration. Output a test, not a
  large commitment.
- If the outcome is unclear, or more than two constraints look binding, shrink
  the boundary. Do not act.
- If removing a point would not improve flow immediately, it is not the
  bottleneck.
- Irreversible context and non-survivable downside forbid leverage and
  redesign.
- Execute only one significant action per loop. Stacking destroys attribution.
- Automate last, only after deletion and simplification.

## Packet

The `company-os.riocl-tc-packet.v1` packet is a checklist, not governed
state. The bound governor decision, outcome request, charter, or adaptation
remains authoritative.

Validate with:

```bash
python3 scripts/validate_riocl_tc_packet.py path/to/packet.json
```

Load the source algorithm only when needed:
`references/source/riocl-tc-master-algorithm.txt`. Do not paste it into worker
prompts.
