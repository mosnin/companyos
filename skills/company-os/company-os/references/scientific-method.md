# Scientific method playbook

This is a checklist overlay on existing Company OS contracts. It does not own
iteration, leases, fabric, completion, or authority. Do not add a seventh
primary loop or a second hypothesis store.

## Mapping

| Step | Existing record | Next governed action |
| --- | --- | --- |
| Hypothesis | `domain_hypotheses[]` in `company-os.outcome-request.v1`, an `$innovation-bets` contract, or a meta-loop adaptation `hypothesis` | Write a `company-os.scientific-method-packet.v1` bound to that record |
| Research | `$evidence-research-campaign` or `$close-outcome-discovery` | Sensor work only. Navigation treats research as observe, not destination |
| Parallel experiments | `bounded-divergent-exploration-loop` plus outcome lanes | `$select-execution-loop`. Pilot cap remains 2 managers / 3 workers each / 6 total |
| Yes / no | `$execute-outcome-evaluator` or bet kill/scale rule | Independent receipts. Manager narrative cannot complete |
| Analyze | `outcome_loop.py` diagnosis or `$company-scorecard` | Bind receipts, not a write-up |
| Implement | `$direct-outcome` / `$run-outcome-loop` `next_action` | Master follows only that action |
| Recycle | Rework, reopen discovery, hold/kill a bet, or `propose-adaptation` | Preserve the negative result. Rejected commands must not mutate governed state |

## Experiment classes

Keep these authorities separate.

| Class | Binding | Who accepts |
| --- | --- | --- |
| `outcome` | `company-os.outcome-request.v1` `domain_id` | Independent evaluator and reality receipt |
| `innovation_bet` | `$innovation-bets` contract | Portfolio kill/scale/hold, not the proposer |
| `process_adaptation` | Elastic `propose-adaptation` | A different reviewer |

## Hypothesis rules

A legal hypothesis is falsifiable, sourced, and statused `hypothesis`,
`supported`, or `refuted`. Agents may propose; they may not self-accept.

- Do not silently change the original objective.
- Do not pick a technology because one source mentioned it.
- Do not mark `supported` from the experimenter's own implementation.
- `$close-outcome-discovery` still requires citations and source bindings.
- Thin evidence authorizes a capped `$innovation-bets` packet, not infinite research.

## Experiment rules

`$select-execution-loop` binds exactly one primary loop. High novelty uses
`bounded-divergent-exploration-loop`. Do not invent a scientific-method loop.

That loop already requires a finite variant budget, independent lanes, novelty
separated from usefulness, held-out acceptance, and human approval for
consequential selection. Loop plans stay `activation_state: planned`. Selection
does not start a runtime or scheduler.

## Conclusion rules

The experimenter does not declare success.

- `supported` on an outcome packet requires an evaluator or reality receipt.
- `refuted` must keep the negative evidence.
- Unavailable data stays unavailable. It is not zero and not a green score.
- Completion still requires `company-os.reality-acceptance-receipt.v1` with
  `execution_bound: true`.
- A production-team story is not admissible.

## Implementation rules

Alignment is not a license to start writing product. After `supported`, follow
only the `next_action` returned by `$direct-outcome` / `$run-outcome-loop`.
`$govern-outcome-execution` may compress further research when reality lags
burn. Core promotion still needs evidence from three isolated projects plus
independent review.

## Packet

Validate the overlay packet with:

```bash
python3 scripts/validate_scientific_method_packet.py path/to/packet.json
```

Bind an outcome request when the class is `outcome`:

```bash
python3 scripts/validate_scientific_method_packet.py path/to/packet.json \
  --request path/to/outcome-request.json
```

The packet is not governed state. The bound outcome request, bet, adaptation,
evaluator receipt, or reality receipt remains authoritative.
