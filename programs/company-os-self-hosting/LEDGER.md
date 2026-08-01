# Company OS Self-Hosting Ledger

## Current checkpoint

- Canonical repository: `/Users/preston/Documents/Codex/company-os-core`
- Distribution version: `0.3.1`
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

Verification on 2026-08-01 at the Phase 1C candidate:

- Repository distribution/bootstrap tests: 4/4 pass.
- Canonical controller regression: 112/112 pass.
- Transactional control regression: 20/20 pass.
- Canonical observation integration: 8/8 pass.
- Observation-gateway reference: 10/10 pass.
- Luna Execution Fabric validator self-test: pass.
- Python compilation: pass.
- Independent Phase 1C Sol review: no P0/P1/P2 after two identified gaps
  were fixed and re-reviewed.
- Distribution manifest and exact installed copy: pending final candidate
  publication after the self-host evidence repair.

### Phase 1B — transactional control accepted locally

- SQLite is the project-bound authority; state revisions, paired ordered
  events, projections, inboxes, outboxes, command idempotency, and leases
  commit together.
- Exact command retries survive restart without another revision; conflicting
  payloads fail closed.
- Cancellation is authoritative, concurrent claims are fenced, foreign-project
  rows fail audit, and JSON/JSONL are deterministic repairable exports.

### Phase 1C — durable evidence and phase integrity accepted locally

- New evidence binds immutable project-local SHA-256 snapshots, while source
  paths are descriptive and may evolve without rewriting accepted proof.
- Invalid legacy or current evidence can be superseded only while paused,
  unscheduled, lease-free, uncancelled, and cycle-idle with an exact external
  independent grant.
- The full predecessor, reviewed transition, signature, and linear history are
  retained and re-audited. Completed-cycle and accepted-fabric references are
  terminal.
- Supersession is permitted only when the named predecessor is itself invalid
  and the replacement removes that defect. Dependent quality scores are
  cleared.
- Active work cannot exit a phase until current applicable quality passes;
  critical dimensions require 9 and noncritical dimensions require 8.

## Not yet implemented

- Provider-driven lifecycle state beyond immutable observation retention.
- Provider launch or provider-observed identity.
- Real Sol manager or GPT-5.6 Luna worker execution.
- Heartbeats, terminal receipts, cancellation propagation, telemetry, or
  reconciliation from a provider.
- Self-hosted accepted capability or adaptation cycle.
- Protected launcher, external issuer deployment, or recurring scheduling.

## Exact next action

Publish the reviewed 0.3.1 candidate, repair the two stale self-host evidence
records through signed supersession, and re-audit the self-hosting instance.
Then implement Phase 2's provider-neutral admission-before-launch gateway,
heartbeats, terminal receipts, cancellation propagation, provider-derived
identity/usage, and restart reconciliation while runtime and scheduling remain
feature-off.
