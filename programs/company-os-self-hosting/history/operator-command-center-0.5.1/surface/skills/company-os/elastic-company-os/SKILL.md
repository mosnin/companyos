---
name: elastic-company-os
description: Create, validate, and evolve an isolated Company OS instance for each project while preserving a shared governed core. Use when starting or repairing project orchestration, creating adaptive product and business feedback loops, preventing scheduler drift, auditing cross-functional execution, or promoting proven operating improvements across projects.
---

# Elastic Company OS

Create one isolated `.company-os/` instance per project. Never reuse another project's objectives, work queue, metrics, customer context, or learned adaptations. Treat `control.db` as authoritative controller state. `control.json` and `events.jsonl` are inspectable, deterministic exports; editing them never changes authority.

## Architecture

- **Core:** shared constitutional rules, schemas, audit dimensions, and promotion gates. Project agents may not edit it during ordinary work.
- **Instance:** project-specific strategy, product reality, departments, methods, metrics, cadence, budgets, and feedback history.
- **Work loop:** discovers and delivers project value.
- **Audit loop:** independently evaluates evidence and drift.
- **Meta-loop:** proposes bounded instance adaptations. It cannot self-approve, modify authority boundaries, or recurse beyond depth one.
- **Promotion loop:** promotes an instance improvement to the core only after independent evidence from at least three projects.
- **Execution fabric:** after direction and experience are accepted, the master
  may use `$luna-execution-fabric` to create isolated Sol manager threads and
  bounded Luna worker teams. Managers never edit `control.json` or approve
  Company OS state.

The operating shape is fractal: company, program, manager, and worker each use
the same outcome → envelope → budget → execution → evidence → reconciliation
contract. Every child receives a strictly narrower envelope; every result,
exception, and proof rolls upward. The pattern may repeat conceptually at any
planning level, but executable delegation is capped at master → manager →
worker and the self-improvement meta-loop is capped at depth one.

Read [references/control-contract.md](references/control-contract.md) before changing a project instance or enabling a scheduler.

Configure only the external issuer's public key through `COMPANY_OS_ACTOR_GRANT_PUBLIC_KEY`. If it is absent, grant-governed decisions and certification fail closed. The controller never mints grants or holds issuer private material.

A configured public key is necessary but not sufficient for unattended execution. This standalone controller cannot prove that an unrestricted scheduler did not replace its launcher or issuer configuration, so it deliberately reports `protected_launcher_ready: false`, lists the protected launcher as an external prerequisite, and keeps `scheduler_ready: false`. There is no local flag, file, environment value, or controller-minted attestation that closes this gate. A deployment must add and independently verify that protected launcher/issuer boundary outside this controller before scheduling can be considered ready.

## Bootstrap

Run:

```bash
python3 scripts/company_os_controller.py init \
  --project /absolute/project/path \
  --name "Project name" \
  --project-type software \
  --north-star "Category-level outcome"
```

This creates `.company-os/control.db` plus derived `control.json` and
`events.jsonl` exports without touching product code. Preserve an existing
instance; `init` refuses to overwrite it.

Upgrade a schema-version 1 through 8 instance before use:

```bash
python3 scripts/company_os_controller.py upgrade --project /absolute/project/path
```

The schema-9 upgrade is fail-closed and monotonic: it archives the old strategy, work, evidence, cycles, adaptations, fabric, and dormant runtime state; increments the program version; revokes leases; disables scheduling; pauses the instance; and creates a disabled runtime-adapter state with a separate observation inbox per future attempt. Schema 9 may verify and retain an observation only when both feature gates are explicitly enabled and an external `COMPANY_OS_OBSERVATION_GATEWAY_KEYRING` is configured. It does not launch providers or advance lifecycle, receipts, telemetry, reconciliation, or real Luna dogfood evidence.

After upgrading a legacy schema-9 JSON instance, validate and migrate it once:

```bash
python3 scripts/company_os_controller.py migrate-control-store \
  --project /absolute/project/path
```

Migration rejects invalid source state, cross-project bindings, and corrupt
existing stores. It preserves legacy events, creates revision one, and is an
exact no-op when repeated against a healthy store.

## Operating sequence

1. **Reality audit:** inspect the actual product, business, repository, runtime, customers, and constraints. Record direct evidence and access limits.
2. **Intelligence:** research current technology, customer behavior, competitors, practitioner experience, and counterevidence.
3. **Direction:** choose a first-principles product or business thesis and rank committed capabilities plus bounded innovation bets.
4. **Experience:** define the end-to-end journey, prototype, information architecture, interaction, brand, and measurable value.
5. **Delivery:** version a complete Program Contract, assign bounded roadmap
   outcomes to Sol manager threads, and use Luna workers for most labor.
   Managers report at charter, discovery, design, execution, verification, and
   integration; implement vertical, user-visible slices with direct enablers.
6. **Verification:** audit the completed slice across applicable dimensions; evidence is mandatory.
7. **Learning:** compare predicted and actual results, identify recurring failure patterns, and propose instance adaptations.

Do not reverse this sequence because maintenance is easier to test. A genuine P0 may interrupt; record the interruption and resume the prior phase after containment.

## Controller rules

Before every cycle, run:

```bash
python3 scripts/company_os_controller.py audit --project /absolute/project/path
```

At kickoff and every operator check-in, render the decision surface:

```bash
python3 scripts/company_os_controller.py brief \
  --project /absolute/project/path \
  --format markdown
```

Use `--format json` as the compact master/manager handoff so an agent can read
the current outcome, gate, quality, work, supervision, evidence, feedback, and
one exact next action without loading raw control state or every skill. This is
a read-only projection, not authority. It deliberately omits grants, nonces,
raw provider envelopes, and private issuer material. Use `--strict` in a
monitor when a blocked governed gate must produce a nonzero exit status.

The controller rejects:

- a scheduler before reality, direction, and evidence gates are ready;
- non-positive, stale, wrong-owner, wrong-program, or transition-unpermitted controller leases;
- more than three active work items;
- maintenance or enablers without a named user-visible capability;
- audit artifacts presented as product progress;
- manager/worker activity or phase reports presented as product progress
  without an accepted user-visible outcome;
- unsigned, replayed, proposal-mismatched, or self-approved adaptations;
- recursive meta-loops;
- core promotion without evidence from three independent projects;
- stage completion with missing evidence, any applicable critical quality score below 9, or any applicable noncritical score below 8;
- direct goal edits that do not increment the program version;
- stale work, evidence, leases, or certification from another program version;
- evidence without an immutable project-local SHA-256 snapshot, freshness, decision impact, and independent review;
- static allocation claims contradicted by actual cycle cost or time;
- a paused/cancelled instance with scheduling enabled;
- cancellation that leaves an active lease or work item;
- maintenance or enablers occupying the primary lane; use the existing typed `p0` work type for a genuine interruption.

Every accepted cycle must produce a reality artifact, intelligence decision, experience prototype, user-visible capability, verified learning, or accepted adaptation. Tests, ledgers, migrations, and audits count only as linked evidence or direct enablers.

Use controller commands for every state transition:

- Every mutating CLI command requires a stable caller-generated
  `--command-key`. An exact retry returns the committed acknowledgment without
  a new revision; reuse with different arguments fails closed. Runtime
  admission and observation ingestion retain their stricter domain-specific
  idempotency keys.

- `replace-program` versions a changed mandate, archives evidence, cancels stale work, revokes leases, and returns to paused reality audit.
- `record-evidence` publishes the artifact under its project-local SHA-256 content address and binds that immutable snapshot to the project and program; completion evidence must additionally bind the committed outcome, work, cycle, and rubric.
- `supersede-evidence` repairs an invalid current record only while paused, unscheduled, lease-free, uncancelled, and cycle-idle. An external independent grant binds the old and new digests, exact successor ID and metadata, source path, bindings, bucket, and reason. The command preserves the full predecessor and grant, rejects completed-cycle or accepted-fabric references, and clears every quality score that cited the predecessor.
- `correct-evidence` is a separate, narrower transition for a structurally valid JSON record with a false Git commit identity. It permits only an exact `/commit` replacement whose full SHA resolves locally, requires distinct signed declarant and conflict-free adjudicator grants over the complete predecessor and successor record digests plus a current transition timestamp, preserves the predecessor as a `semantic_retraction`, rejects terminal references, clears citing quality, invalidates certification, and keeps scheduling disabled. Current and later-program audits require exact content-addressed paths and reject added authority-shaped metadata. It cannot perform generic semantic edits or weaken `supersede-evidence`.
- `advance-phase` moves exactly one evidenced stage, refuses to leave active work before current applicable quality passes, and clears scores for the new phase.
- `commit-outcome` and `queue-work` create the governed portfolio.
- `score-quality` requires separate signed grants for scorer and reviewer; its
  canonical payload hash binds the score, canonical evidence IDs, actors,
  outcome, work, cycle, complete evidence-set digest, and rubric. The set
  digest covers every cited artifact and binding. Legacy single-artifact
  signed history retains its original `artifact_digest` payload shape, but new
  multi-source reviews should use `--evidence-digest`.
- `certify` requires a command-specific signed certifier grant whose payload hash binds the exact canonical `governance_digest`, reviewer, and accepted decision. It rejects every actor already involved in the work, evidence, cycle review, or quality review.
- `activate` and `set-schedule` open execution only after certification.
- `configure-fabric` binds a validated project-local Sol-manager/Luna-worker
  manifest to primary work queued with `--execution-mode luna_fabric`.
- `record-fabric-phase` records one immutable manager report for the exact
  running cycle and current phase barrier.
- `decide-fabric-phase` requires a command-specific signed master grant and
  records `continue`, `rework`, `pause`, or `terminate`; no implicit approval
  advances a manager.
- `admit-runtime-attempt` is an admission-only, feature-gated command. It
  records no provider activity and requires the exact current lease, running
  fabric/work/cycle/manifest, frozen Phase 2 contract digest, allowlisted
  provider surface/account, full canonical manifest scope and budget, signed
  master grant, unique attempt ID, and launch idempotency key. A manager must
  be admitted before a worker; exact retries are no-op and conflicts fail
  closed.
- `ingest-runtime-observation` strictly parses one project-local signed
  envelope, revalidates all retained observations and immutable raw artifacts,
  and stores only the attempt-scoped verified record. It uses a keyring trust
  root separate from actor decisions, changes no lifecycle or model-acceptance
  state, and makes exact retries byte-for-byte no-ops.
- `acquire-lease`, `begin-cycle`, `finish-cycle`, `resolve-cycle`, and `release-lease` fence one bounded cycle. A running cycle must be explicitly recovered, abandoned, or failed before its lease can be released.
- `cancel` revokes the lease, clears active work, and makes cancellation authoritative.
- `propose-adaptation` and `review-adaptation` preserve reviewer separation and protected fields.

Run `python3 scripts/company_os_controller.py <command> --help` for exact arguments.

## Elastic adaptation

Adapt the project instance when evidence shows the current operating method is wrong. An adaptation must include:

- observed failure pattern and affected cycles;
- hypothesis;
- smallest reversible change;
- success and regression metrics;
- time/cost cap;
- rollback;
- proposer and different independent reviewer.

Apply changes to the instance first. Do not alter the core from a single project's preferences.

## Scheduling

Keep scheduling disabled until `audit` returns both `protected_launcher_ready: true` and `scheduler_ready: true`. The standalone controller intentionally cannot produce either launcher attestation or scheduler readiness; treat `external_prerequisites` as a release blocker until independently satisfied by deployment infrastructure. After that external integration exists, use one recurring controller task per project, not one task per cycle. A wake must acquire the project lease, read the exact next action, perform at most one bounded cycle, publish evidence, release the lease, and stop. Empty wakes end without model work.

On user cancellation, pause the schedule and make cancellation authoritative over completion or retry.

`finish-cycle` requires an externally signed reviewer grant, reviewer identity, `--work-disposition continue|complete`, and a reviewer decision. Its canonical payload hash binds the exact cycle/lease generation, actual outcome, sorted evidence IDs plus recomputed evidence digest, cost, latency, token usage, user-visible movement, disposition, decision, reviewer, and optional commit/ref. Before archival, it rechecks every linked artifact hash, freshness, program/outcome/work/cycle/rubric binding, and decision relevance. `complete` stores the evidence digest, immutable completion digest, reviewer, and full signed token before removing the work from active work; a rejected review must continue the work. Semantic fingerprints normalize Unicode, case, whitespace, and punctuation. P0 admission and repeat overrides hash every decision-relevant queue argument, and audits reconstruct that canonical payload from the retained record before accepting the grant. Repeating completed semantics requires a reason and independent signed override. Every finish disables scheduling and invalidates certification. Re-audit and independently certify the full canonical governable-state digest before another scheduled cycle; only self-referential validation plus live lease/fence, schedule, execution-timestamp, consumed-nonce, and activation-status fields are excluded. Rearm only with exactly one ready primary work item and the externally verified launcher prerequisite. Quality certification requires independently reviewed scores and evidence bound to the current primary and accepted checkpoint/cycle—not irrelevant future production dimensions during an experience prototype. Changing primary work clears old quality applicability. Two consecutive cycles without accepted product movement or learning, or an actual portfolio allocation breach, pauses the instance and records drift.

## Handoff

Report:

- project instance and phase;
- concrete capability or learning produced;
- audit coverage and evidence gaps;
- adaptations proposed/applied;
- scheduler and lease state;
- exact next action.

Prefer the `brief` projection for routine check-ins. Explain only the blocker,
the one next move, and the evidence that changed since the prior check-in; do
not substitute activity logs for product movement.

Never call the system healthy because its files validate. Run the project's adversarial simulation after changes, forward-test it on the real project, and require a visible outcome.
