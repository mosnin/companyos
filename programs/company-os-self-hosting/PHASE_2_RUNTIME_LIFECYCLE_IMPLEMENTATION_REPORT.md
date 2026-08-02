# Phase 2 Runtime Lifecycle — Feature-Off Implementation Report

## Verdict

`FEATURE_OFF_CODE_COMPLETE / RUNTIME_UNVERIFIED / NO_GO`

This slice defines the provider-neutral boundary required for one exact
`GPT-5.6 Sol manager → GPT-5.6 Luna worker` read-only artifact task. It makes no
provider call, does not enable the runtime adapter or scheduler, and does not
claim that a callable Luna surface exists.

The implementation is deliberately separate from
`company_os_controller.py`. Canonical controller integration, persistence, a
real provider connector, and real provider evidence are later reviewed gates.

The controller now also contains one prerequisite state-integrity repair for a
previously committed program transition. That repair does not integrate or
activate the runtime boundary; it prevents stale prior-program authority from
contaminating the future integration.

## Pre-integration transition repair

The former `replace-program` path archived evidence and execution-fabric state
but left live adaptation decisions and the complete prior-program quality
scorecard in the replacement program. The reality phase happened not to require
those dimensions, so the stale scorecard was not previously evaluated.

The feature-off repair slice now:

- archives and clears pending/applied adaptations and every quality score,
  binding, scorer grant, and reviewer grant on every future program replacement;
- retains the complete source strategy and digest, original transition reason,
  exact evidence-backed scorecard, complete archived evidence authority, signed
  adaptation authority, and exact runtime attempt/observation/audit state;
- permits one narrowly eligible repair only when the instance is paused,
  scheduling is off, no lease/cycle/live work/evidence/runtime attempt exists,
  and every affected record belongs to exactly the immediately prior program;
- requires a new independent `repair-program-transition` grant whose actor is
  distinct from every affected proposal, quality, evidence author/reviewer, and
  retained signed-grant actor;
- binds the grant to the exact source/transition revisions and hashes, complete
  adaptation, quality, and runtime archive hashes, the exact retained
  `program_replaced` event, both complete strategy documents, transition
  identity/reason, and the exact post-repair candidate-state hash;
- commits the repair and its command receipt as one SQLite revision/event;
  exact command-key replay is a no-op, while a distinct retry fails closed;
- replays the candidate hash and prior-state hashes from immutable transactional
  history, reconstructs the exact old replace mutation, requires one-to-one
  adaptation/quality/runtime archives and repair record/event history, and
  rejects unrelated mutation, archive, event, evidence, strategy, score, grant,
  source-history, runtime-history, and candidate-state tampering;
- prevents prior-program quality grants from becoming live again when work is
  queued under the replacement program.

This is a local code/test result only. The repair has not been applied to the
authoritative Company OS instance in this branch report.

## Fixed first vertical slice

- Exactly one manager using the exact provider-observed model
  `gpt-5.6-sol`.
- Exactly one child worker using the exact provider-observed model
  `gpt-5.6-luna`.
- Worker capabilities are exactly `emit_artifact` and `read_project`.
- Worker write scope is empty; external effects and child delegation are
  forbidden.
- Launch requires an admitted immutable runtime identity, externally signed
  admission grant, unexpired lease fence, and one stable idempotency key.
- Missing Luna availability is `blocked_model_unavailable`; no Sol or Terra
  substitution may be recorded as Luna work.
- The original admission fence governs launch only. Query, observe, and cancel
  require a fresh controller lease fence so long-running and ambiguous launches
  remain recoverable after admission expiry.

## Implemented modules

### `runtime_gateway.py`

- Builds deterministic `launch`, `query`, `observe`, and `cancel` requests
  without executing them.
- Carries the exact admitted provider, surface, account, model, parent, scope,
  budget, lease fence, decision grant, manifest digest, contract digest, and
  idempotency key.
- Verifies an asymmetric gateway signature, validity window, request digest,
  runtime binding, raw provider artifact digest, payload digest, provider task,
  provider sequence, and exact observed model.
- Represents an ambiguous launch as `launch_unknown`; restart recovery queries
  with the original idempotency key instead of blind relaunch.
- Separately verifies gateway-signed receipt attestations bound to the exact
  attempt, provider task, and receipt payload hash.
- Replays retained observation and attestation signatures against pinned trust
  roots after restart; a deserialized `trust` label is not accepted evidence.

### `runtime_lifecycle.py`

- Applies only verifier-produced records whose gateway signature and retained
  raw provider bytes are replay-verified.
- Keeps provider task and terminal state immutable, requires strictly
  increasing provider sequences, and rejects decreasing provider timestamps.
- Requires an issuer-signed, runtime-bound cancellation decision; cancellation
  is terminal before launch, survives ambiguous-launch recovery, and dominates
  a late provider success.
- Requires terminal provider usage, preserves unknown usage as unavailable,
  rejects invalid totals, and prevents cumulative usage or cost from
  decreasing.
- Rejects provider revision reuse and retains every usage source-observation
  digest.
- Retains token/cost/time overages as evidence and prevents them from becoming
  a complete accepted receipt.
- Reconstructs lifecycle state from the ordered signed observation set and
  signed cancellation boundary after restart, then rejects any retained status,
  task, model, terminal, telemetry, or budget field that differs from replay.

### `runtime_receipts.py`

- Binds receipts to immutable runtime identity, terminal observation, exact
  observed model evidence, provider telemetry, content-addressed artifacts,
  checks, and the complete child receipt set.
- Requires a gateway-verified receipt attestation; an agent-authored `author`
  string is not attribution.
- Requires exactly one successful receipted Luna child for a successful first
  manager slice. The child's signed task/model/terminal observations, complete
  receipt, and deterministic lifecycle replay are independently re-audited;
  stubs, failed children, Sol substitution, and child-set drift are rejected.
  Workers require an empty child set.
- Allows failed, blocked, or cancelled work to close honestly without inventing
  an artifact or check. Definitive model unavailability can produce an attested
  blocked receipt and signed blocked reconciliation without inventing a task,
  model, or usage. Cancellation before launch closes with the already verified
  decision grant as its cryptographic receipt authority and a separately signed
  cancelled reconciliation; it never invents provider evidence.
- Builds an immutable receipt root and permits only byte-equivalent restart
  retries.
- Requires a separately verified master decision grant that binds the exact
  reconciliation payload, including reconciliation time, and makes
  reconciliation immutable.
- Recomputes receipt roots, attestation signatures, provider telemetry
  provenance, decision signatures, and reconciliation digests after restart.

## Evidence included in this branch

The focused suite covers:

- deterministic read-only launch requests;
- signature, request, identity, artifact, payload, task, and model tampering;
- exact Sol/Luna role enforcement;
- exact committed-manifest, scope-digest, budget, and one-pair binding;
- launch-unknown recovery without blind relaunch;
- signed launch, running, terminal, and receipt-attestation evidence;
- monotonic provider sequences, timestamps, usage, cost, and revision provenance;
- signed cancellation authority, ambiguous-launch recovery, cancellation
  dominance, and terminal immutability;
- receipt child-set completeness, content drift, and restart idempotency;
- rejection of stub, failed, substituted, or replay-invalid Luna children;
- deterministic restart replay of lifecycle and blocked-model closure;
- token, cost, and elapsed-time budget enforcement;
- signed decision-grant binding and immutable reconciliation;
- restart tamper detection and exact expired-grant reconciliation replay.

All evidence is local/test-key evidence (`M`). It is not provider-runtime
evidence (`R`).

Current local evidence: the full controller/control-store/runtime/observation/
operator suite passes 230 tests in 213.412 seconds, including thirteen focused
adversarial transition-repair/replace tests, along with Python compilation and
whitespace validation.
The separate repository release suite is intentionally not green: 24 of 26
tests pass, while manifest freshness and signed Operator Command Center surface
parity fail because the remediated controller has not yet been independently
accepted, versioned, manifested, signed, or installed as 0.4.3. Those two
failures are release gates, not passing implementation evidence.
The repository skill validator itself did not execute because its host Python
environment lacks the `yaml` module (`ModuleNotFoundError`); no dependency was
installed and this is not counted as passing evidence.

## Explicit integration points

The later canonical integration must, atomically under the controller lock:

1. load an admitted attempt and its trusted observation inbox;
2. persist the immutable launch request before any connector call;
3. retain `launch_unknown` when provider acceptance is ambiguous;
4. verify and append gateway results before lifecycle advancement;
5. persist lifecycle, observation provenance, and event history together;
6. verify receipt attestation and artifacts before retaining a receipt root;
7. require a current master lease and signed decision grant for
   reconciliation;
8. derive the manager's exact expected Luna child from durable admissions,
   never from manager self-report;
9. re-run signed retained-state audit and reconciliation after restart.

Rejected commands and exact retries must not change governed state or the event
log. Runtime and scheduler feature gates remain disabled throughout this work.

## Remaining release blockers

1. The new modules are not wired into canonical controller commands or durable
   storage.
2. No connector maps an actual provider's launch/read/wait/cancel surface into
   these exact signed envelopes.
3. No callable surface in this work has proved exact `gpt-5.6-luna` identity.
4. No real provider launch/running/terminal, failure, cancellation, receipt,
   artifact, usage, or reconciliation evidence exists.
5. Restart/crash reconciliation is specified and unit-tested as pure state
   behavior, not proven through a persisted process fault matrix.
6. The latest independent repair review returned `NO-GO` with three P1s. The
   exact-event/state binding, full archived-evidence authority audit, and
   digest-chained runtime archive repairs now pass the focused and complete
   local suites, but the remediated exact commit still requires independent
   re-review. Controller-wide integration acceptance remains a separate gate.

The next safe action is a separate controller-integration change that keeps the
adapter disabled, followed by an authenticated connector and one real
read-only dogfood attempt. Until those gates pass, Phase 2 remains `NO_GO`.
