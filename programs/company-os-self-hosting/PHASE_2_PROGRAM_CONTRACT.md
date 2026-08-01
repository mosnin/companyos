# Company OS Self-Hosting Program — Phase 2

## Program identity

- Program ID: `company-os-self-hosting`
- Contract version: `2`
- Contract revision: `2`
- Phase: `runtime-adapter`
- Depends on: independently accepted Phase 1 kernel truthfulness
- North star: Company OS turns an accepted program into attributable,
  inspectable manager and worker execution without confusing a launch request,
  local hash, self-report, heartbeat, provider timeout, or thread creation with
  accepted work.
- Phase outcome: the feature-off local Company OS can admit one exact runtime
  attempt before launch, bind externally attested provider lifecycle evidence
  to it, and reconcile receipts, telemetry, cancellation, and terminal results
  without widening the accepted fractal program.

## Fractal runtime invariant

Every executable level uses the same control geometry:

`outcome → envelope → budget → execution → evidence → reconciliation`

- The program envelope is authoritative.
- Each manager receives one narrower outcome, envelope, and budget.
- Each worker receives one narrower task, scope, and budget from its manager.
- Authority and reserved resources narrow downward.
- Provider evidence, artifacts, receipts, exceptions, and actual usage roll
  upward.
- Executable depth remains `master → manager → worker`.
- Managers may not hide worker labor inside their own task. Workers may not
  delegate.
- Missing or unverifiable model identity fails closed. Terra or Sol work can
  never be recorded as Luna work.

## Trust roots and authority separation

Company OS does not mint runtime authority or provider provenance.

Two external trust roots are distinct:

1. **Decision issuer:** authorizes one pre-launch admission, cancellation, or
   reconciliation decision under the current Company OS lease/fence.
2. **Observation gateway:** attests the result of an actual provider
   launch/read/wait/cancel/terminal operation.

Only public verification keys and key IDs may enter Company OS. Private signing
material, provider credentials, and gateway credentials remain outside the
controller. A gateway may report provider facts; it may not change the program,
scope, budgets, acceptance criteria, or reconciliation.

Every trusted provider observation carries an asymmetric signature over:

- provider, surface, and provider account/workspace identifier;
- provider task/thread ID;
- provider-native event or revision ID;
- command/event type, provider timestamp, gateway receipt timestamp, and
  monotonic provider sequence;
- canonical payload digest and raw observation artifact SHA-256;
- project ID, program version, work ID, cycle ID, and runtime-attempt ID;
- parent runtime identity, role, requested model, and observed model;
- gateway issuer key ID, nonce, issued-at, and expiry.

Unverified, self-authored, or malformed observations may be retained only as
diagnostic evidence. They cannot advance lifecycle state, counters, budgets,
receipts, or reconciliation.

The controller verifies either the provider's native webhook signature or a
gateway signature over a direct provider API result using the pinned
observation-gateway public key. Unsigned task output, local files, requested
model strings, controller-authored records, and receipt-only claims remain
`untrusted_claim`.

## Pre-launch admission and crash boundary

No provider spawn may occur before a feature-off `admit-runtime-attempt`
transition succeeds.

The immutable admission binds:

- current program/work/cycle and admitted fabric-manifest digest;
- current controller lease ID, owner, generation, expiry, and permitted action;
- runtime-attempt ID and one launch idempotency key;
- allowed provider, surface, and provider account/workspace;
- parent runtime identity;
- role and requested model;
- canonical scope and budget;
- outcome, acceptance, stop condition, and contract digest;
- externally signed decision grant.

One admission may bind at most one provider task ID. Registration consumes the
launch intent exactly once.

The gateway may launch only an unexpired exact admission. Registration creates
no authority. Gateway authority is limited to executing an admitted launch,
observing provider state, and executing an authorized cancellation. A manager
may request bounded child admission but cannot authorize it. Only the master
decision issuer may admit work or reconcile a terminal outcome.

If the external launch may have occurred but registration did not, the attempt
becomes `launch_unknown`. Recovery must query the provider using the same
idempotency key or known provider task reference. It may never blindly relaunch.
Provider observations may be archived after a lease expires, but governed
advancement and reconciliation require a current authoritative lease/fence.

Phase 2 owns local state/event atomicity and this launch-unknown ambiguity.
Provider callbacks, durable inbox/outbox, multi-host recovery, and automatic
crash replay remain Phase 3.

## Runtime identity and model proof

The immutable runtime identity digest covers:

- project/program/work/cycle/runtime-attempt;
- admitted fabric manifest and Phase 2 contract digest;
- parent runtime identity and role;
- requested model;
- canonical scope and budget;
- launch idempotency key.

After trusted launch evidence, the bound identity also records:

- provider/surface/account and provider task ID;
- provider-attested `observed_model`;
- raw observation digest;
- canonical model-mapping version.

`requested_model` and `observed_model` are separate. Missing provider model
evidence remains `unknown`; it never inherits the requested value. Unsupported
aliases, model mismatch, version drift, or gateway claims without provider proof
block receipt acceptance and require escalation. Tests must cover each case.

## Normative lifecycle

Allowed states:

| State | Meaning |
| --- | --- |
| `admitted` | Exact launch intent is authorized but no provider launch is proven |
| `launch_unknown` | Launch may have happened; query/reconcile, never blind relaunch |
| `launched` | Trusted provider launch binds one provider task ID |
| `running` | Trusted provider observation proves active execution |
| `cancel_requested` | Authoritative cancellation is recorded |
| `cancel_acknowledged` | Provider/gateway attests receipt of cancellation |
| `succeeded` | Immutable trusted provider terminal success |
| `failed` | Immutable trusted provider terminal failure |
| `cancelled` | Immutable trusted provider terminal cancellation |
| `receipt_recorded` | Required attributable receipt chain is present |
| `reconciled` | Independent master decision closes the attempt |

Provider-native event/revision order is distinct from local ingestion order.

- The event key is provider + account + provider task ID + provider event or
  revision ID.
- Exact repetition of the same key and digest is a byte-for-byte no-op.
- The same key with a different digest is a replay/conflict and fails closed.
- Stale or reordered observations may be retained diagnostically but cannot
  regress state or counters.
- Provider terminal state is immutable.
- Parent admission precedes child admission.
- Child terminal evidence precedes a complete manager receipt.
- Reconciliation occurs exactly once.

The launch idempotency key is passed through to providers that support
idempotent spawn. If the provider does not support it and the response is lost
or ambiguous, the attempt becomes `launch_unknown` and must be queried by its
intent key or known provider reference. Multiple provider task IDs for one
intent are quarantined and cannot contribute to accepted work.

An authoritative cancellation records its source, scope, generation, and signed
authority; cascades parent → descendants; blocks new children, retries,
success receipts, and acceptance for the attempt; and is idempotent. It is
irreversible inside the current program/work/cycle. Late success is quarantined
evidence only. Work may resume only in a new user-authorized cycle. Provider
cancellation acknowledgement must be a trusted observation.

## Receipts and evidence roots

Every worker receipt binds:

- immutable runtime identity digest;
- terminal provider observation digest;
- artifact paths and SHA-256 digests;
- exact checks and outcomes;
- actual model and model-evidence digest;
- usage-source digest;
- status and stop reason;
- receipt author identity and external attestation.

A receipt is attributable only when the observation gateway attests that its
exact canonical content was fetched from the bound provider task, or when it
carries a per-task signature whose public key was bound at launch. Receipt
semantics remain self-reported until their artifacts and checks are
independently verified.

Every manager receipt binds:

- manager runtime identity digest;
- complete set of admitted child identity digests;
- complete set of child terminal-receipt digests;
- explicit missing-child exceptions;
- hashed integration artifacts and checks;
- manager receipt author identity and external attestation.

The receipt-chain root is a canonical digest of the manager identity, complete
admitted-child set, child terminal receipts, missing-child exceptions, provider
terminal observation root, telemetry root, and integration evidence.

The final master decision grant binds the receipt-chain root, terminal
observation root, telemetry digest, decision, reviewer identity, nonce, issued
time, and expiry. Missing, extra, substituted, stale, or duplicate children fail
closed.

## Telemetry and budgets

Admission reserves concurrency and budget before launch.

Each telemetry field defines:

- provider source and observation digest;
- unit and currency where applicable;
- cumulative or delta semantics;
- rounding rule;
- provider revision/event ID.

Token and count fields are non-negative integers. Time and cost are finite
non-negative numbers. Unknown values remain unavailable; they are never
converted to zero or estimates.

Actual model, token counts, provider timestamps, and provider status derive only
from authenticated provider metadata. Receipt-reported values are stored
separately as untrusted claims. Cost is provider-reported or calculated from
authenticated usage through a versioned pricing table whose digest is retained.
Every derived metric stores its source observation IDs and formula.

- Cumulative counters are deduplicated by provider revision.
- Decreasing cumulative counters are rejected as conflicting evidence.
- Delta counters are applied exactly once by event key.
- Actual time, tokens, cost, concurrency, retries, accepted-first-pass, rework,
  and failures aggregate idempotently up worker → manager → program.
- Budget exhaustion prevents new admission and requests cancellation of active
  work where safe.
- An observed overage is recorded honestly, then triggers pause/cancellation
  and budget-violation reconciliation. It is never discarded merely because it
  exceeds the budget.
- Overage or unavailable required telemetry blocks acceptance.

## Included implementation

- Additive schema-8, feature-off runtime-attempt state.
- Typed commands for:
  1. admit runtime attempt;
  2. register trusted provider launch;
  3. ingest trusted provider observation/heartbeat;
  4. request cancellation;
  5. ingest trusted cancellation acknowledgement or terminal observation;
  6. record worker receipt;
  7. record manager receipt;
  8. reconcile terminal result.
- Runtime gateway interface that maps actual orchestration-surface
  spawn/read/wait/cancel results into signed observation envelopes.
- Atomic validation before persistence, stable idempotency, replay/conflict
  rejection, lifecycle fencing, receipt roots, and provider-derived telemetry.
- One bounded, non-product dogfood attempt using a real manager and worker on an
  available provider surface.

## Excluded

- Recurring or unattended scheduling.
- Protected scheduler deployment.
- Distributed/Postgres state and multi-host coordination.
- Provider callbacks, durable inbox/outbox, or automatic crash replay.
- Chippy code, database, deployment, or customer-visible work.
- Browser, email, Slack, CRM, spending, destructive, or production effects.
- Raising the accepted limits of 2 managers, 3 workers per manager, 6 workers
  globally, depth two, or meta-loop depth one.
- Treating mocks, local hashes, self-authored receipts, HTTP success, or thread
  creation alone as proof of runtime execution.

## Acceptance gates

All must pass:

1. Pre-launch admission is externally authorized, lease-fenced, immutable, and
   consumes one idempotency key for at most one provider task ID.
2. Trusted observations verify the external gateway signature and exact claims;
   unverified observations cannot advance governed state.
3. Runtime identities exactly bind provider, actual model, role, parent,
   program, work, cycle, contract, scope, and budget.
4. Parent-before-child, depth, 2/3/6 scaling, model-role, and disjoint-scope
   rules reject atomically.
5. Lifecycle tests cover duplicate, conflicting, stale, reordered, replayed,
   wrong-program, wrong-parent, wrong-provider-ID, post-terminal, expired-lease,
   launch-unknown, and recovery cases.
6. Heartbeats are monotonic, provider-attributable, freshness-scored, and never
   treated as completion.
7. Cancellation dominance and success-before-cancellation ordering pass the
   full fault matrix.
8. Worker and manager receipts form one immutable complete receipt-chain root;
   missing, extra, substituted, or stale children fail closed.
9. Terminal acceptance requires trusted terminal evidence, verified actual
   model, valid artifacts, complete receipts, required telemetry, and a signed
   master reconciliation grant.
10. Telemetry source/unit/revision semantics, deduplication, unknown values,
    decreasing counters, overages, and fractal aggregation pass.
11. Provider/model unavailability fails closed without substitution or invented
    telemetry.
12. Existing Phase 1 regressions remain green; runtime negative-path and
    fault-injection tests pass; both skills validate and Python compiles.
13. A separate Sol reviewer finds no P0/P1 inside Phase 2 scope.
14. Dogfood proves at least one real bounded manager → worker provider run with
    trusted launch/running/terminal observations, verified model identity,
    cancellation or failure fault evidence, complete receipts/artifacts,
    provider-derived telemetry, and signed reconciliation.
15. The ledger separately labels requested, admitted, provider-launched,
    provider-observed, self-reported, artifact-verified,
    terminal-provider-observed, reconciled, blocked, and unverified states.

A missing GPT-5.6 Luna capability is an honest blocked dogfood result, not Phase
2 acceptance. In that state the only permitted dogfood result is
`blocked_model_unavailable`: no Luna launch/running/receipt/telemetry/success
claim may be recorded. Code may be labeled `feature_off_code_complete`, but
Phase 2 remains `runtime_unverified`. No substitute model may satisfy Gate 14;
mocks validate mechanics only.

Negative tests must include untrusted gateway keys, wrong provider account,
signature substitution, raw-artifact mismatch, requested/observed model
mismatch, missing model evidence, and receipt-sourced telemetry presented as
provider telemetry.

## Stop conditions

Stop on any authority widening, false provider attribution, self-minted trust,
hidden model substitution, lifecycle regression, state/event non-atomicity,
unrecorded overage, unrelated product edit, production effect, or repeated
failure without a new hypothesis. Do not enable a scheduler at Phase 2
completion.

## Phase 3 candidate

Only after Phase 2 acceptance: move the accepted controller/runtime contract to
durable transactional state with multi-host leases, inbox/outbox processing,
provider callbacks, crash recovery, and replay/fault testing. Phase 3 may not
weaken the Phase 1 or Phase 2 invariants.
