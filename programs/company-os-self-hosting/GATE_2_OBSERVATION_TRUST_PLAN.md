# Company OS Gate 2 — Observation Trust Plan

## Outcome

Company OS can distinguish an authenticated provider observation from a local
claim before any lifecycle, telemetry, receipt, or reconciliation logic is
allowed to consume it.

This is a feature-off trust-boundary slice. It does not launch managers or
workers, call a provider, enable the runtime adapter, advance an attempt beyond
`admitted`, or enable scheduling.

## Product-program position

Gate 1 proved that one exact manager or worker launch intent can be admitted
under a signed master decision and a current lease fence. Gate 2 proves the
opposite side of that boundary: only a separately authenticated observation
gateway can attribute provider facts to that attempt.

The governing geometry remains:

`outcome → envelope → budget → execution → evidence → reconciliation`

Gate 2 covers only the `evidence` ingress boundary. It creates no execution or
reconciliation authority.

## Standards baseline

- Use a canonical signed claim set with a pinned asymmetric public-key ID.
- Bind the exact received provider artifact with SHA-256. RFC 9421 explicitly
  requires a verifier to validate a signed content digest against the received
  content; checking the signature alone is insufficient.
- Keep provider/source plus event ID as the replay identity, following the
  CloudEvents uniqueness model, while retaining the stricter Company OS key of
  provider + account + task + provider event/revision ID.
- Keep message-content integrity separate from representation semantics, in
  line with RFC 9530.

Primary references:

- https://www.rfc-editor.org/rfc/rfc9421.html
- https://www.rfc-editor.org/rfc/rfc9530.html
- https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md

The project-local verifier uses the existing OpenSSL/RSA-SHA256 test mechanism
to avoid adding a runtime dependency. A later transport adapter may implement
RFC 9421 wire headers, but it must map them into the same canonical Company OS
claim set.

## Frozen observation envelope v1

Every signed observation binds:

- schema and gateway key ID;
- provider, surface, and provider account/workspace;
- provider task/thread ID, event/revision ID, event type, and sequence;
- provider timestamp and gateway receipt timestamp;
- canonical provider-payload SHA-256 and exact raw-artifact SHA-256;
- project, program, work, cycle, runtime attempt, parent, and role;
- requested model and independently observed model (`null` remains unknown);
- nonce, issued-at, and expiry.

The raw artifact is project-local JSON with a strict provider projection. Its
metadata must exactly match the signed claims, and its `payload` digest must
match independently. Duplicate JSON keys, non-finite values, traversal, and
oversized artifacts reject.

## State and replay rules

- The gateway keyring contains public keys only and is separate from the
  decision-issuer key.
- Exact event key plus exact observation digest is a byte-for-byte no-op.
- Same event key with a different digest is a conflict.
- A nonce may be consumed once; reuse on another event rejects.
- Provider sequence must increase for a bound provider/account/task stream.
- Unknown, expired, inactive, or substituted keys reject.
- Wrong attempt, provider, account, parent, role, requested model, task, raw
  artifact, payload digest, timestamp, or sequence rejects.
- Rejection returns no candidate state and leaves governed state unchanged.
- Accepted observations enter only a trusted-observation inbox. They do not
  modify lifecycle, model acceptance, telemetry, receipts, or budgets.

## Delivery phases

### A. Contract and threat model — active

1. Freeze the v1 envelope and keyring.
2. Freeze timestamp, nonce, event-key, and sequence semantics.
3. Freeze the no-go boundary and evidence labels.

### B. Project-local executable verifier — active

1. Verify the separate gateway signature.
2. Recompute raw-artifact and canonical payload digests.
3. Bind the exact admitted attempt and provider account.
4. Apply idempotency, nonce, and monotonic-sequence checks to a candidate state.
5. Prove invalid inputs are atomic with adversarial tests.

### C. Canonical controller integration — blocked pending B acceptance

1. Add the accepted fields to the installed schema without enabling them.
2. Add one `ingest-runtime-observation` command.
3. Re-run the full controller regression suite and skill validators.
4. Require an independent Sol review with no P0/P1.

### D. Lifecycle consumption — explicitly excluded from Gate 2

Trusted observations may drive `launched`, `running`, heartbeat, terminal, and
cancellation states only in later separately accepted slices.

### E. Real provider dogfood — explicitly excluded from Gate 2

Real provider evidence remains Gate 14. Mock/test-key observations prove only
the verifier mechanics.

## Acceptance matrix

Gate 2 passes locally only when all cases below are executable and green:

| Class | Required proof |
| --- | --- |
| Trust root | valid gateway key passes; unknown/inactive/expired key and decision-key substitution fail |
| Signature | malformed and substituted signatures fail |
| Identity | project/program/work/cycle/attempt/parent/role/provider/account/task mismatches fail |
| Content | raw artifact and canonical payload digest mismatch fail |
| Time | missing/invalid/future/expired/overlong envelopes fail |
| Replay | exact duplicate is no-op; nonce replay and key/digest conflict fail |
| Ordering | missing, negative, boolean, duplicate, or decreasing sequence fails |
| Model truth | requested and observed model remain separate; unknown observed model stays `null` |
| Atomicity | every invalid ingest leaves the input state byte-identical |
| Boundary | no launcher, lifecycle transition, telemetry, receipt, reconciliation, scheduler, or external effect exists |

## Stop conditions

Stop immediately on self-minted gateway trust, reuse of the decision key as the
gateway key, acceptance without raw-content verification, hidden model
substitution, lifecycle advancement, non-atomic rejection, private material in
state, provider calls, scheduling, production effects, or unrelated Chippy
work.

## Exit and next decision

After the project-local verifier and adversarial suite pass, run a read-only
security review. If accepted, prepare a small canonical-controller patch. If
not, keep Gate 1 frozen and label Gate 2 `REWORK`; do not start lifecycle or
provider-launch work.
