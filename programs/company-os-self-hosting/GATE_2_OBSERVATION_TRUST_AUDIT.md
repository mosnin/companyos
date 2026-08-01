# Company OS Gate 2 — Observation Trust Audit

## Decision

**Reference mechanics: PASS. Canonical Company OS acceptance: PARTIAL / NO-GO.**

The project-local, feature-off verifier now proves that a runtime report can be
cryptographically attributed to a separate observation gateway, bound to one
exact admitted attempt and one provider task, and checked against the exact raw
provider bytes before entering a trusted inbox.

It is not installed in the canonical controller, has not observed a real
provider, has not received an independent Sol acceptance review, and cannot
advance lifecycle state. It therefore does not make Company OS operational and
does not justify launching managers or workers.

## Evidence executed on 2026-07-31

- `10/10` focused Python contract tests passed.
- Python compilation passed for the verifier and adversarial suite.
- Valid gateway signatures pass; decision-key substitution, unknown, revoked,
  expired, malformed, or retired-for-new-work keys reject.
- Exact retries are no-ops; event conflicts, nonce reuse, decreasing sequence,
  boolean sequence, and provider-task switching reject atomically.
- Project, program, work, cycle, attempt, parent, role, model request,
  provider, surface, account, and contract/manifest substitutions reject.
- Raw-artifact tampering, traversal, duplicate JSON keys, invalid UTF-8,
  oversized input, payload-digest mismatch, and post-signature changes reject.
- Unknown observed model remains `null`; it is never filled from the requested
  model.
- Corrupted retained signatures, claims, event keys, nonce history, or provider
  task binding prevent further ingestion.
- Rejection leaves the caller-owned input state byte-identical.

## Recursive review findings repaired

### 1. Corrupted-history inheritance

The first prototype checked a new observation without fully revalidating every
retained trusted observation. A corrupt historical record could therefore
remain underneath later accepted evidence.

**Repair:** retained observations are rebuilt from their claims, signature,
raw artifact, original verification time, and gateway key validity before any
new observation can be considered.

### 2. Provider-task identity drift

The first task binding was not an explicit inbox invariant. One admitted
attempt could have accumulated observations from multiple provider tasks.

**Repair:** the first verified observation binds one provider task ID. Every
retained and incoming record must match it.

### 3. Double-read content race

The first content check hashed one file read and parsed a second. A changing
artifact could make the verified bytes differ from the interpreted bytes.

**Repair:** size validation, SHA-256, UTF-8 decoding, duplicate-key rejection,
and JSON parsing now operate on one exact byte buffer.

### 4. Permissive signature decoding

The first decoder could classify some malformed base64 as merely an invalid
signature.

**Repair:** URL-safe base64 is decoded with strict validation before OpenSSL
verification.

## Acceptance-gate status

| Gate | Result | Evidence boundary |
| --- | --- | --- |
| 2 — Observation trust | **PASS at project-local mock mechanics; PARTIAL overall** | Separate gateway key, exact content binding, replay/order/identity checks pass locally. Real provider reconfirmation and canonical integration are absent. |
| 12 — Regression/tooling | **PARTIAL** | Focused tests and compilation pass. The canonical controller's full regression and official skill validators were not rerun because the installed controller was not changed. |
| 13 — Independent review | **NOT RUN** | Root recursive review found and repaired four issues. This is not an independent Sol acceptance. |
| 15 — Evidence truthfulness | **PASS for this slice** | Requested versus observed model, mock versus real provider, reference versus canonical, and code-complete versus runtime-verified remain separated. |

All later runtime, lifecycle, reconciliation, real-provider, Chippy, and
scheduled-operation gates remain unavailable.

## Brutal score

| Dimension | Score | Reason |
| --- | ---: | --- |
| Contract clarity | 9.1/10 | Exact identities, content, time, replay, ordering, and no-go boundaries are explicit. |
| Reference verifier correctness | 8.8/10 | Adversarial mechanics are strong after recursive repairs; this is still a local reference using subprocess OpenSSL. |
| Evidence honesty | 9.4/10 | No mock, code, or self-review result is represented as runtime proof. |
| Canonical integration | 2.0/10 | Nothing is installed in the controller yet. |
| Real provider proof | 0.0/10 | No real manager, worker, provider event, or observed-model evidence exists. |
| Company OS operational readiness | 4.2/10 | Gate 1 admission is frozen and Gate 2 mechanics exist, but the execution/reconciliation chain is incomplete. |

The slice is valuable but deliberately narrow. It prevents false evidence from
becoming the foundation of later automation; it is not the automation itself.

## No effects

No provider call, manager or worker launch, scheduler, lifecycle transition,
Chippy change, database mutation, deployment, customer-data access, or outbound
message occurred.
