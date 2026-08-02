# Company OS Self-Hosting Ledger

## Current checkpoint

- Canonical repository: `/Users/preston/Documents/Codex/company-os-core`
- Distribution version: accepted `0.4.3`; the canonical 72-file distribution
  is installed byte-exact under `/Users/preston/.codex/skills`
- Canonical release: `a761efab3884555ac352c95cc7378017bbc9415a`
- Authoritative control revision: 131; program 6 is paused in Reality Audit,
  unscheduled, uncertified, runtime-disabled, and lease-free
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

Verification on 2026-08-02 at the accepted 0.4.3 release:

- Independent detached release suite: 302/302 pass.
- Repository release/distribution/surface tests: 29/29 pass.
- Canonical controller regression: 126/126 pass.
- Transactional control regression: 37/37 pass.
- Canonical observation integration: 8/8 pass.
- Observation-gateway reference: 10/10 pass.
- Fixture-only Responses gateway: 29/29 pass.
- Provider-neutral runtime gateway/lifecycle/receipts: 33/33 pass.
- Luna Execution Fabric validator self-test: pass.
- Python compilation: pass.
- Exact 21-file Operator Command Center surface: independently signed and
  verified at 9.22/10 mean, 9.0 minimum, no P0/P1/P2.
- Distribution manifest: 72/72 exact files, zero missing and zero extras;
  disposable fresh install and 0.4.2-to-0.4.3 transactional upgrade pass.
- Canonical installed-copy comparison after the real local upgrade: pass.

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

### Phase 1F — stale program-transition authority repaired

- Program 5-to-6 replacement state is mechanically reconstructed from exact
  revisions 129 and 130 under a positive, versioned runtime archive schema.
- Unknown or credential-shaped archive material fails before mutation; rejected
  commands preserve revision, exports, and event history.
- Independent source, release, and application reviews all returned GO with no
  P0/P1/P2. One short-lived signed grant authorized only command key
  `repair-program-transition-v5-v6-r129-r130`.
- Revision 131 contains exactly one adaptation archive, quality archive,
  runtime archive, repair record, repair event, and idempotency receipt. It has
  zero live stale adaptations or scores. The store and readable exports match.

### Phase 2A — provider-neutral lifecycle and fixture gateway accepted locally

- The lifecycle contract defines signed admissions, leases, budgets,
  cancellation dominance, terminal receipts, restart reconstruction, telemetry,
  and reconciliation without binding authority to one provider.
- The OpenAI Responses adapter is deliberately fixture-only. Request and result
  signing authorities are cryptographically distinct; provider-shaped secrets,
  unknown fields, invalid usage, duplicate task identity, and unverified
  cancellation are rejected.
- Launch identity is protected by a durable no-relaunch fence. Adversarial tests
  cover pre-commit, post-replace/pre-fsync, one-shot fallback, persistent
  fallback, and artifact-cleanup failures without a second provider create.
- This is source and disposable-fixture proof only. It is not live OpenAI,
  GPT-5.6 Luna, protected-launcher, provider-cost, or production evidence.

## Not yet implemented

- A network-capable provider adapter and protected launcher.
- Provider launch or provider-observed identity in a real account.
- Real Sol manager or GPT-5.6 Luna worker execution.
- Controller integration that advances one real provider lifecycle through
  heartbeats, terminal receipt, cancellation, telemetry, and reconciliation.
- Self-hosted accepted capability or adaptation cycle.
- Dedicated spend-limited provider credential, external issuer deployment, or
  recurring scheduling.

## Exact next action

Record one decision-grade, independently challenged Program 6 Reality Audit
artifact, then advance only into Intelligence. Intelligence must resolve the
current OpenAI Responses/provider identity, protected-launcher design, dedicated
credential and spend boundary, controller integration seam, and one exact
minimal live-job acceptance matrix. Only then implement and prove one
authenticated, budgeted, cancellable Sol-to-Luna job. Recursive self-hosting,
multi-project isolation, protected scheduling, and Chippy onboarding remain
later gated phases. Production and customer systems remain frozen.
