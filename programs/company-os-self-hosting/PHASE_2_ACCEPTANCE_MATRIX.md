# Company OS Phase 2 Acceptance Matrix

Evidence labels:

- `M`: local/mock/test-key evidence.
- `R`: real provider evidence.

Global assertions:

- Every invalid command leaves `control.json`, governed runtime state, and
  `events.jsonl` byte-for-byte unchanged.
- Exact command/event key plus exact digest is a no-op with no new bytes.
- Same key with a different digest is a conflict and rejects atomically.
- Untrusted diagnostics cannot advance governed lifecycle, counters, budgets,
  receipts, or reconciliation.
- Gates 1–13 may use `M` unless stated. Gate 14 requires `R`.

| Gate | Required adversarial proof | Acceptance |
| --- | --- | --- |
| 1 — Admission | Grants missing/malformed/untrusted/expired/replayed; wrong lease/program/work/cycle/manifest/contract/provider/account; duplicate attempt/key | One immutable valid admission; invalid cases atomic; exact retry no-op; one intent binds at most one provider task |
| 2 — Observation trust | Unknown gateway key, decision key used as gateway key, signature substitution, wrong account/task/event, expired/replayed nonce, payload/raw-artifact mismatch, missing timestamp/sequence, self-authored claim | Only a trusted exact envelope may advance the attempt (`M`, reconfirm with `R`) |
| 3 — Runtime identity | Mutate provider/account/task/model/role/parent/program/work/cycle/contract/scope/budget/idempotency independently | Every substitution rejects; requested model never fills observed model |
| 4 — Fractal admission | Child before parent, manager authorizes child, worker delegates, depth 3, wrong model-role, out-of-parent/overlapping scope, wider budget, 3/4/7 scaling | Exact 2 managers × 3 workers = 6 may pass; every widening/overage is atomic |
| 5 — Lifecycle/recovery | Duplicate/conflicting/stale/reordered/post-terminal events, wrong identity, expired lease advancement, second provider task, lost launch response | Duplicate no-op; conflict rejects; terminal immutable; ambiguous launch is `launch_unknown`; no blind relaunch |
| 6 — Heartbeats | Unsigned/decreasing/future/stale heartbeat or heartbeat claiming completion | Freshness only; never terminal or accepted (`M` plus one `R`) |
| 7 — Cancellation | Duplicate/cascading cancel, child/retry/success/receipt after cancel, wrong acknowledgement | Idempotent, cascading, irreversible; late success quarantined (`M` plus real fault evidence) |
| 8 — Receipt chain | Missing/extra/duplicate/stale/substituted child, identity/model/artifact/check/usage mismatch, unattested receipt, manager-before-child | Immutable complete roots; incomplete chain blocks acceptance |
| 9 — Reconciliation | Nonterminal/heartbeat-only, missing or drifted artifact, unknown model/telemetry, incomplete receipt, bad/replayed grant or wrong root | Exact complete binding accepts once; all substitutions atomic (`M`, real signed reconciliation in Gate 14) |
| 10 — Telemetry | Invalid numbers/types, unknown-as-zero, delta replay, cumulative decrease, wrong units/currency, pricing drift, receipt claims as provider data, budget overage | Idempotent fractal aggregation; unknown stays unavailable; overage retained, pauses/cancels, and blocks acceptance (`M` plus `R` sample) |
| 11 — Provider/model unavailable | Provider/Luna absent, missing observed model, alias/version drift, Terra/Sol substituted, gateway claim without provider proof | `blocked_model_unavailable` / `runtime_unverified`; no fabricated Luna evidence |
| 12 — Regression/tooling | Full Phase 1 plus runtime tests, validator, compilation, official skill validation | All pass; scheduler disabled; runtime feature off by default |
| 13 — Independent review | Trust roots, mutation order, crash ambiguity, secret handling, evidence labels, scope | Separate Sol finds no P0/P1 |
| 14 — Real dogfood | Real admitted manager→worker attempt and real cancellation/failure path | Trusted launch/running/terminal observations, actual model, receipts/artifacts, provider telemetry, signed reconciliation; Luna unavailability blocks acceptance (`R` only) |
| 15 — Ledger | Attempts to collapse requested/launched, self-report/provider observation, receipt/artifact verification, mock/real, code-complete/runtime-verified | Every evidence and lifecycle state remains explicitly separated |

## No-go boundary

- Feature-off local schema-8 adapter and tests only.
- No provider spawn before successful admission.
- No private signing keys or provider/gateway credentials in state, logs,
  fixtures, or commits.
- No scheduler, recurrence, distributed state, callbacks, inbox/outbox,
  automatic crash replay, Chippy/product work, deployment, or customer effects.
- Do not raise 2/3/6, depth two, or meta-loop depth one.
- Stop on authority widening, false attribution, hidden model substitution,
  non-atomic mutation, unrecorded overage, or any production effect.
