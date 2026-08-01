# Company OS Self-Hosting Ledger

## Current checkpoint

- Canonical repository: `/Users/preston/Documents/Codex/company-os-core`
- Distribution version: `0.2.0`
- Canonical controller: schema 9 / core 2.6
- Client work: frozen; Chippy is not an implementation target
- Recurring automation: disabled
- Production or customer effects: none

## Accepted evidence

### Phase 0 — canonical source accepted

- The previously unversioned Company OS and Autonomy Suite sources were copied
  byte-for-byte into one dedicated Git repository outside all client projects.
- A content-addressed distribution manifest covers both complete skill bundles.
- The installer stages and hashes every file, refuses a changed installation by
  default, restores the prior bundle if atomic replacement fails, and supports
  a read-only installed-source comparison.
- Clean bootstrap creates an isolated project instance and proves it remains
  fail-closed without reality, direction, evidence, issuer, or launcher gates.
- The pre-integration Gate 2 verifier remains preserved under `reference/` as
  a comparison oracle.

### Phase 1A — canonical observation trust accepted locally

- Every admitted attempt receives a separate, disabled observation inbox.
- `ingest-runtime-observation` uses strict duplicate-key/non-finite JSON
  parsing, a distinct external gateway keyring, signed immutable identity
  bindings, exact raw-artifact hashes, time bounds, nonce/event uniqueness,
  monotonic provider sequence, and retained-history revalidation.
- Exact retries are byte-for-byte no-ops. Rejections change neither state nor
  audit events. Observations cannot mutate attempts, models, budgets,
  lifecycle, reconciliation, work, evidence, scheduling, or feedback.
- Schema-8 runtime attempts remain unchanged in archived history and never
  carry authority into the new program.
- `replace-program` now resets the runtime adapter to the new program version;
  a regression test prevents the stale-authority defect found during dogfood.
- State plus audit event use a recoverable write-ahead transaction. A staged
  pair interrupted after one target replacement is completed under the next
  controller lock.

Verification on 2026-08-01:

- Repository distribution/bootstrap tests: 4/4 pass.
- Canonical controller regression: 100/100 pass.
- Canonical observation integration: 7/7 pass.
- Observation-gateway reference: 10/10 pass.
- Luna Execution Fabric validator self-test: pass.
- Python compilation: pass.
- Distribution manifest: verified.

## Not yet implemented

- Transactional distributed control state; the current local filesystem pair
  is crash-recoverable but remains single-host.
- Provider-driven lifecycle state beyond immutable observation retention.
- Provider launch or provider-observed identity.
- Real Sol manager or GPT-5.6 Luna worker execution.
- Heartbeats, terminal receipts, cancellation propagation, telemetry, or
  reconciliation from a provider.
- Self-hosted accepted capability or adaptation cycle.
- Protected launcher, external issuer deployment, or recurring scheduling.

## Exact next action

Move programs, work, attempts, inbox events, leases, idempotency keys, and
outbox commands into transactional storage with isolated project namespaces.
Prove concurrent claims, crash recovery, replay, cancellation precedence, and
restart before implementing a provider launcher or lifecycle advancement.
