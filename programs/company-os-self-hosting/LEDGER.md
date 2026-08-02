# Company OS Self-Hosting Ledger

## Current checkpoint

- Canonical repository: `/Users/preston/Documents/Codex/company-os-core`
- Distribution version: accepted `0.5.0`; the canonical 83-file distribution
  is installed byte-exact under `/Users/preston/.codex/skills`
- Canonical source acceptance: `0900cfe1d4661dffbbd612695aea57dfa4562448`;
  release metadata is the current canonical `main` HEAD
- Authoritative control revision: 131; program 6 is paused in Reality Audit,
  unscheduled, uncertified, runtime-disabled, and lease-free
- Canonical controller: schema 9 / core 2.6
- Client work: frozen; Chippy is not an implementation target
- Recurring automation: disabled
- Production or customer effects: none
- Program 6 direction: Codex-native task fabric; external provider/API gateway
  implementation retired from the active roadmap
- Release state: source distribution accepted and installed; scheduler-off;
  broader runtime NO-GO

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

### Phase 2B — initial Codex-native task-fabric correction rejected on independent review

- Commit `16592d4c95671638c6d538e0d2932488020ace91` was initially accepted by
  the implementing manager, then independently reviewed NO-GO at 5.8 with
  0 P0, 4 P1, and 3 P2 findings. Its local scorecard is superseded; the commit
  remains immutable history.

- Exactly two projectless tasks were requested as `gpt-5.6-luna`. Native task
  IDs, host observations, status, and elapsed durations were exposed; observed
  model, tokens, cost, and cancellation acknowledgement were not.
- Worker A completed and its source inventory was manager-verified. Worker B
  failed after violating the read-only boundary through bytecode creation and
  cleanup. Its execution receipt remains rejected; no status upgrade occurred.
- The failure drove a side-effect-free validation rule, explicit ignored-file
  inspection, and `PYTHONDONTWRITEBYTECODE=1` for subsequent checks.
- The final hygiene audit found 16 `.pyc` files in the three authorized test
  trees, timestamped to Worker B's compilation window. Only those caches were
  removed. The acceptance rerun began with 0 bytecode artifacts and ended with
  0; its fail-closed scan reported
  `acceptance-rerun-passed pyc_before=0 pyc_after=0`.
- New versioned `manage-company-program` and `execute-bounded-task` source
  skills keep stable role policy outside compact prompts. Installation and
  fresh-thread forward testing are not claimed.
- Five concrete scenarios deterministically accept the known-answer fixture,
  block a malformed dependency chain, preserve real manager rework, reject
  stale/scope/failure/budget pressure, and reject cross-project artifacts.
- Verification at that commit passed: 32 repository tests, 7 focused native-fabric tests, 126
  controller, 37 store, 8 observation, 10 gateway, 14 lifecycle, 9 receipt, 29
  Responses-fixture, and 10 reference tests, plus both fabric validators,
  strict role validation, distribution manifest verification, and 26-file AST
  parsing. Standard `quick_validate.py` lacked its real PyYAML dependency; a
  compatibility-shim result is not acceptance evidence.
- Passing tests did not close the independent review's phase-authority, compact
  schema, evidence-provenance, lifecycle/concurrency, iteration, scope, and
  agent-policy defects.

### Phase 2C — bounded v2 source-contract rework locally validated

- Phase authority now requires authenticated master decisions at charter,
  design, verification, and final integration. Silence escalates at a bounded
  timeout. Only visible routine execution subphases inside the unchanged
  accepted charter may auto-continue.
- The v2 charter and packet carry explicit contract/program/definition
  versions, outcome and artifact digests, requested model, permissions, all six
  budgets, review requirements, barriers, and attributable authorization. A
  worker inherits accepted-design evidence, never awaits the master, and
  returns to its manager.
- Fixture model observations are forbidden; native model evidence requires a
  recognized host-observation source class. The two historical tasks remain
  described only as requested `gpt-5.6-luna`; observed model is unavailable.
- Lifecycle records separate current and optional terminal status, enforce
  ordered create/start/terminal evidence, validate native identity, and include
  open active intervals in concurrency pressure.
- Iteration mappings, lowercase ASCII project-relative scope, ancestor overlap,
  and explicit no-implicit-invocation agent policy fail closed under
  adversarial tests. Malformed contract and metadata types return errors rather
  than raising.
- Verification passed: 41 repository tests, 16 focused native-fabric tests,
  126 controller, 37 store, 8 observation, 10 gateway, 14 lifecycle, 9 receipt,
  29 Responses-fixture, 30 operator-brief, and 10 reference tests, plus strict
  role/fabric validators, distribution manifest, 28-file syntax parsing, and a
  repository-wide zero-bytecode/cache before/after gate.
- Full-system hard cancellation, controller admission, installed behavior,
  successful two-requested-Luna integration, telemetry, durable reconciliation,
  and scheduling remain far below gate.

### Phase 2D — final v2 enforcement rework locally validated

- Independent exact-commit review of `d6f6a03` closed the previous seven
  findings but returned NO-GO at 6.8/10 with three P1 and two P2 enforcement
  gaps. No new worker tasks were authorized or created for this rework.
- Authorization now resolves a versioned project-local
  `company-os.authorization-decision.v1` record, recomputes its canonical
  digest and exact phase-evidence byte digest, verifies a repository-fixture
  HMAC, and matches accepted decision, program, versions, outcome, phase,
  decider, task lineage, requested model, and parent definition. Arbitrary
  hashes and replay substitutions fail. This is not live identity proof.
- Worker packets load the exact accepted parent manager charter, bind mission
  lineage to that charter, and separately bind the design-record native
  `parent_manager_task_id` to the destination. They reject cross-project or
  cross-manager replay, stale parent digest, scope escape, action/tool
  widening, weakened prohibitions, or any of six budgets above signed parent
  availability or charter limits.
- Artifact references resolve only versioned project-namespaced regular files
  under allowed local roots. Exact bytes are hashed; absolute, backslash,
  dot/escape, symlink, missing, mutable, foreign-project, path-string-hash, and
  digest-mismatch cases fail without exposing content.
- Every numeric budget rejects booleans, strings, negatives, invalid zero
  boundaries, NaN, and infinities without raising. Manager-manager ancestor
  overlap joins worker-worker overlap in the executable simulation validator.
- Final bytecode-disabled verification at `e991230` passed 55 root repository
  tests, including all 23 role-contract tests, plus 17 separate native-fabric,
  126 controller, 37 store, 8 observation, 10 gateway, 14 lifecycle, 9 receipt,
  29 Responses-fixture, 30 operator-brief, and 10 reference tests, plus strict
  role/simulation/legacy-fabric validators and distribution manifest
  verification.

### Phase 2E — final fail-closed evidence correction locally validated

- Independent exact-commit review of `e991230` returned 8.3/10 with no P0 or
  P1 and two P2 gaps. No worker tasks were authorized or created.
- Parent charter scope, identifiers, permissions, tools, prohibitions, budgets,
  references, and other nested inputs are type-checked before comparison.
  Direct null, boolean, object, numeric-list, and mixed-list attacks plus a
  bounded JSON-shape matrix return deterministic errors without raising.
- Signed authorization regression cases now cover exact task ID, mission parent
  and native parent-manager bindings, and substitution of an entire separately
  valid signed record. The observed failed Worker B receipt remains rejected as
  `failed_policy_exception`; it is not upgraded to successful integration.
- Final bytecode-disabled verification passed 59 root repository tests,
  including all 27 role-contract tests, plus 17 separate native-fabric, 126
  controller, 37 store, 8 observation, 10 gateway, 14 lifecycle, 9 receipt, 29
  Responses-fixture, 30 operator-brief, and 10 reference tests, plus strict
  role/simulation/legacy-fabric validators, manifest, syntax, diff,
  secret/scope, fail-closed, and repository-wide zero-bytecode gates.

### Phase 2F — source distribution accepted

- Independent exact-commit review of `0900cfe` returned 0 P0, 0 P1, and 0 P2
  findings and scored source readiness 9.1/10.
- The review approved only a manifest-backed global source installation. It did
  not approve controller/runtime or scheduler activation.
- Version 0.5.0 packages the manager and worker role skills as global reusable
  policy. Task prompts carry only the explicit skill invocation and compact,
  versioned charter or packet; they do not carry the operating system prose.
- The governed installation preserves the exact accepted 0.4.3 manifest for
  rollback and replaces both bundles transactionally.

## Not yet implemented

- A network-capable provider adapter and protected launcher.
- Provider launch or provider-observed identity in a real account.
- Successful fresh installed-role Sol-manager/two-requested-Luna forward test.
- Controller integration that advances one real provider lifecycle through
  heartbeats, terminal receipt, cancellation, telemetry, and reconciliation.
- Self-hosted accepted capability or adaptation cycle.
- Dedicated spend-limited provider credential, external issuer deployment, or
  recurring scheduling.

## Exact next action

Forward-test a fresh Sol manager and two fresh tasks requested as GPT-5.6 Luna
using only the global skill invocation plus compact charter/packet. Do not
enable scheduling. The
following gate must add controller admission-before-create and prove a hard
native cancellation acknowledgement before broader runtime acceptance.
