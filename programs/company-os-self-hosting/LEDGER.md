# Company OS Self-Hosting Ledger

## Current checkpoint

- Canonical repository: `/Users/preston/Documents/Codex/company-os-core`
- Distribution version: `0.4.2` candidate; 0.4.1 is installed exactly and the
  0.4.2 semantic-evidence correction has independent implementation GO
- Authoritative control revision: 102; paused in Learning, unscheduled,
  uncertified, lease-free
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

Verification on 2026-08-01 at the 0.4.2 candidate:

- Repository distribution/bootstrap tests: 4/4 pass.
- Canonical controller regression: 122/122 pass.
- Transactional control regression: 23/23 pass.
- Canonical observation integration: 8/8 pass.
- Observation-gateway reference: 10/10 pass.
- Luna Execution Fabric validator self-test: pass.
- Python compilation: pass.
- Independent semantic-correction review: GO with no remaining P0/P1/P2 after
  five adversarial repair rounds.
- Distribution manifest: current for the 0.4.2 candidate; exact installed-copy
  upgrade remains pending the refreshed independent surface signature and
  release commit.

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

### Phase 1D — Operator Command Center accepted for Delivery

- Program v5 moved the self-hosting outcome from backend control work to one
  exceptional operator decision surface before implementation began.
- The first product candidate was independently rejected at 6.40/10. Three
  repair cycles at 8.70, 8.97, and 9.11 were also rejected. The fourth passed
  at 9.22 with all 13 critical dimensions at or above 9.0.
- Markdown, JSON, and self-contained HTML read the SQLite authority without
  mutation and show governed change, why it matters, direction, phase, one
  action, owner, output, done condition, verification, quality exceptions,
  work, supervision, evidence, cost, and control posture.
- Adversarial tests cover authority selection, redaction, markup safety,
  invalid quality proof, missing telemetry, blocker routing, exact comparison
  scope, requested-versus-observed model identity, strict monitoring, and
  empty state.
- Browser acceptance covers 1435 x 1096 desktop and 375 x 812 mobile surfaces,
  real links, semantic disclosure, reduced motion, target sizing, first-viewport
  decision completeness, and horizontal overflow.
- Delivery is governed by
  `OPERATOR_COMMAND_CENTER_DELIVERY_CONTRACT.md`. The accepted Experience
  candidate may not change during packaging without returning to Experience.

### Phase 1E — semantic evidence integrity accepted locally

- A structurally valid immutable JSON record with a false Git commit identity
  now uses a separate `correct-evidence` command rather than weakening
  structural supersession.
- Only `/commit` may change; the new full SHA must resolve locally. Distinct
  signed declarant and conflict-free adjudicator grants bind the complete old
  and new records, artifacts, transition, governance context, and reason.
- The predecessor remains append-only as an inactive semantic retraction;
  current and later-program audits reconstruct immutable bytes, linear
  lineage, actor authority, transition timestamps, and the locally verifiable
  Git object.
- The authoritative false 0.4.1 install record was corrected at SQLite
  revision 102. Store audit is healthy; quality, certification, and scheduling
  remain deliberately invalidated pending the honest Learning evaluation.

## Not yet implemented

- Provider-driven lifecycle state beyond immutable observation retention.
- Provider launch or provider-observed identity.
- Real Sol manager or GPT-5.6 Luna worker execution.
- Heartbeats, terminal receipts, cancellation propagation, telemetry, or
  reconciliation from a provider.
- Self-hosted accepted capability or adaptation cycle.
- Protected launcher, external issuer deployment, or recurring scheduling.

## Exact next action

Refresh the independent signed product-surface attestation for the accepted
0.4.2 bytes, commit and verify the release from clean source, then
transactionally upgrade the canonical installed skills from exact 0.4.1.
Afterward, record the failed Learning scores and independently reviewed
runtime-first adaptation. Integrate the separately reviewed Phase 2 lifecycle
only after its final GO and prove one authenticated, budgeted, cancellable
Sol-to-Luna job before any scheduler or Chippy work. Production and customer
systems remain frozen.
