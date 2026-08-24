---
name: close-outcome-discovery
description: Turn bounded research into verified domain knowledge that closes Outcome Compiler unknowns without inventing requirements. Use after compile-outcome-contract emits a discovery agenda.
---

# Close Outcome Discovery

Resolve unknowns with evidence, not intuition.

The discovery worker may research documentation, reference products, repositories, standards,
market behavior, platform constraints, expert material, and observed artifacts. The resulting
report is not authority by itself. This skill verifies that every claimed resolution is tied
to cited evidence and preserves contradictions as unresolved.

## Sequence

1. Start from an exact `company-os.outcome-request.v1`.
2. Research only the blocking questions emitted by the outcome contract.
3. Produce a discovery report with claims, citations, counterevidence, and proposed updates.
4. Apply it:

```bash
python3 scripts/close_outcome_discovery.py apply \
  --request /absolute/path/outcome-request.json \
  --report /absolute/path/discovery-report.json \
  --output /absolute/path/outcome-request.updated.json
```

5. Recompile the updated request with `$compile-outcome-contract`.
6. Continue discovery until the outcome compiler no longer reports blocking unknowns.

## Evidence rules

A resolution must have at least one citation. A report with counterevidence may not mark the
unknown resolved unless it includes a non-empty reconciliation explaining why the evidence
still supports closure. Every proposed domain hypothesis must carry source bindings.

Do not silently change the original objective. Do not choose implementation technology merely
because one source mentions it. Preserve alternatives as hypotheses until evidence closes them.
When a domain hypothesis is under test, bind a
`company-os.scientific-method-packet.v1` to the same `domain_id`. The packet
cannot close unknowns; this skill still requires citations.
