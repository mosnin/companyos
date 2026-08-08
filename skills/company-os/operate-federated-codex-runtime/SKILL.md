---
name: operate-federated-codex-runtime
description: Consume PostgreSQL-backed federated Company OS commands through native Codex tasks. Use when the master must create, recover, observe, or settle real Sol manager tasks from the shared control plane without duplicate launches.
---

# Operate Federated Codex Runtime

This is the native host bridge for `$compile-federated-company-kernel`. The
database owns desired state, commands, leases, cancellation, and history. The
interactive Codex host performs task operations. This skill does not introduce
a second scheduler or treat prompt text as durable authority.

## Before dispatch

1. Classify the requested launch lane as `discovery`, `pilot`, or
   `production_scale`. Discovery may only execute the bounded questions emitted
   by `$compile-outcome-contract`. Pilot may only execute bounded candidate work
   explicitly permitted by that outcome contract. Any ordinary production
   fanout, manager expansion, or high-concurrency artifact work is
   `production_scale`.
2. For `production_scale`, require the exact
   `company-os.outcome-scale-authorization.v1` associated with the project and
   verify `authorized:true`. The authorization must bind the current outcome,
   artifact observation, evaluator runtime, benchmark, and evaluator
   calibration contracts. Missing, stale, mismatched, or unauthorized outcome
   evidence is a hard stop before command claim or task creation. Runtime,
   kernel, manager, budget, or design receipts may never substitute for this
   authorization.
3. Verify the compiled PostgreSQL kernel, reconciliation request and plan,
   target-specific database audit, and one explicit host binding. The current
   bridge does not accept the local SQLite claim envelope.
4. Claim one durable command with an expiring generation-fenced lease. Keep the
   claim token only in the host secret store; never put it in a prompt, artifact,
   receipt, task title, or log.
5. Compile the claim and host binding with
   `scripts/prepare_native_codex_dispatch.py`. Use the resulting tool name,
   target, prompt, model, and reasoning exactly. A manager is Sol/xhigh. Its
   worker policy comes from the bound kernel cell and is Luna/max.
6. Before calling `create_thread`, list current tasks and read plausible recent
   candidates. Feed a typed observation plus readbacks that exactly cover every
   listed task ID to the executable `reconcile` command. The observation is
   evidence of the host query that ran, not proof of provider-global absence.
   Titles and summaries are untrusted. In `pre_create`, zero exact matches
   permits durable launch-attempt preparation, not creation by itself; one exact
   match is recovered and bound; more than one or a malformed marker candidate
   is a conflict. Never recreate merely because the create call timed out.

## Create and bind

1. Persist the content-bound native launch attempt before calling the host.
   Pass the dispatch packet's exact `attempt_id`, `dispatch_digest`, and
   `initial_prompt_sha256` to the PostgreSQL adapter's
   `prepare-native-launch` operation together with the still-live claim fence.
   A successful preparation receipt is required; generating a dispatch packet
   is not preparation.
   Only then call native `create_thread` once with the compiled arguments. If
   the target is a Git repository, use an isolated worktree unless the binding
   explicitly authorizes the saved checkout.
2. A returned `clientThreadId` is setup-in-progress, not a task identity. Do not
   settle, abandon, or recreate. The durable launch attempt blocks lease-expiry
   replay. Reconcile through task listing until the real thread ID is exposed.
3. Read the created task. Give the raw create result and raw readback to the
   verifier. It accepts only an exact initial prompt/marker and matching thread
   and host identity. Feed the verified receipt as the single candidate to
   `recover-native-launch`; only its `bound` result permits `settle` with that
   same receipt. A raw create result or verifier receipt alone cannot settle.
4. Record task ID and thread ID as the same exposed Codex identifier when the
   host provides only `threadId`. Host ID remains routing metadata, not lineage.

## Observe and control

- Use bounded `wait_threads` sets of at most eight targets and retain each
  returned cursor. Read only tasks that complete, need attention, or cross an
  evidence deadline.
- Discovery managers may resolve only the outcome contract's exact blocking
  unknowns. They must return cited discovery evidence through
  `$close-outcome-discovery`; they may not silently convert hypotheses into
  production requirements or broaden themselves into artifact production.
- Pilot managers may create only the bounded candidate work required to make an
  artifact observable or calibrate an evaluator. A pilot success does not
  authorize production scale; re-run `$authorize-outcome-scale` against the
  resulting current contracts.
- Production managers use `$luna-execution-fabric` and dynamically activate
  Luna tasks within their exact `direct_report_limit`, `declared_worker_slots`,
  packet-bound active-worker cap, global admission, budget, dependency, and
  writer-scope constraints. Before any child fanout, the manager must retain
  the parent production-scale authorization binding in its manager design
  evidence. A child may narrow that authorization but never omit or widen it.
  If the objective binding or any content-bound outcome input changes, the old
  authorization is stale and further fanout stops until reauthorization.
- No fixed team ratio is allowed. For delegated low- and medium-risk cells, the
  signed dispatch may preauthorize design-to-execution continuation when every
  packet-listed condition passes; a failed condition stops at the design
  barrier. High, consequential, non-delegated, protected-action, and exception
  paths still require an authenticated master decision before worker creation.
  Auto-continuation is executable policy, not manager prose. The manager must
  copy the exact canonical manager packet from its initial prompt, materialize
  a canonical `company-os.manager-design-report.v1`, and run
  `scripts/prepare_native_codex_dispatch.py verify-design`. Only a content-
  bound `company-os.manager-design-continuation-receipt.v1` with
  `continue_allowed:true` permits worker creation. The verifier derives
  requirement and capability coverage, Luna/max routing, DAG validity, writer-
  scope isolation, concurrency, budgets, and the absence of protected actions,
  variances, and unresolved dependencies. Attach the receipt to the final
  manager receipt so the master can replay the decision independently.
  Native Codex does not expose a cryptographic child-concurrency policy, so
  list/read reconciliation and scale evidence are still required rather than
  claiming provider-enforced limits.
- Managers are Luna-first: they may not perform worker-eligible artifact labor
  unless worker authority is unavailable, the work is inherently managerial,
  or dispatch would duplicate completed work. Every exception is a measured
  variance. Managers consume receipts instead of worker transcripts and send
  only barrier, exception, and final deltas to the master.
- The initial prompt is a compact cell packet, not the master transcript.
  Managers retrieve only cited, task-local context and skills.
- Requested model and reasoning remain intent unless the host exposes a trusted
  observation. Tokens, cost, and provider usage remain unavailable when absent.
- On cancellation, persist database intent first and let it remain
  authoritative over late success. Native cooperative-stop delivery and
  acknowledgement are a separate unimplemented adapter; do not claim the task
  stopped merely because the database command is cancelled.
- After a restart, reconcile durable commands against task listing/readback
  before any create call. Reclaim an open launch attempt only through
  `reclaim-native-launch`, then pass the exact verified candidate array to
  `recover-native-launch`. One exact match binds; multiple or malformed matches
  persist conflict and block. Zero ambiguous matches remain blocked and only
  record the typed observation. Because the host exposes no authenticated
  snapshot or pagination watermark, zero matches never abandon, requeue, or
  authorize another create automatically. Ambiguity blocks; silence never
  grants success.
- Provision an immutable `project_runtime_principals` binding before the first
  project operation. Each project uses one unique direct `NOINHERIT` database
  login with schema `USAGE` and `EXECUTE` on only the ten runtime API
  signatures. Grant it no table privileges, no binding/assertion helpers, and
  no owner-role membership. The hardened functions run as a trusted definer
  with a fixed search path while checking the authenticated `session_user`;
  cross-project calls, direct table access, and runtime rebinding must all fail
  in the deployment proof. One shared unrestricted runtime login is not a
  supported tenant boundary.
- Reapplying the SQL must preserve every explicit runtime-function grant. The
  one-time legacy signature drop is atomically version-gated; deployment
  validation compares all ten function ACLs before and after an exact migration
  replay and calls `claim_command` from the restricted project login afterward.
- Treat any pre-v2 `abandoned`, bound, settled, or failed-plus-active native
  launch state as untrusted upgrade data. The migration preserves it in
  `native_launch_legacy_quarantine`, marks the attempt `conflict`, and blocks
  ordinary claims. Never reset or reuse that attempt for a new create; a future
  explicitly authorized resolution must close the old command and use a fresh
  message key and attempt identifier.

## Acceptance boundary

A bound native manager task proves only task creation. Company progress requires
accepted manager and worker artifacts, independent checks, requirement and skill
coverage, terminal receipts, and the master decision reserved by the program.
Production-scale throughput additionally requires a current outcome-scale
authorization. Final product acceptance is not implied by task, manager,
kernel, or scale authorization: after production, use `$accept-outcome-reality`
against the original objective, actual artifact evidence, and independent
accepted evaluator receipts. Production completion narratives are audit context
only and are inadmissible as final acceptance evidence.

Runtime and recurring scheduling remain off until real programs prove recovery,
quality, collisions, outcome discrimination, and efficiency at the current
scale gate.
