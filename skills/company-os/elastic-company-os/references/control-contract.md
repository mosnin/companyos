# Elastic Company OS Control Contract

## Separation of authority

| Loop | May do | May not do |
| --- | --- | --- |
| Product/work | Discover, prototype, implement, test, publish evidence | Change its own acceptance gate or approve its own result |
| Audit | Inspect evidence, score applicable dimensions, reject or request rework | Implement the work being audited |
| Meta | Diagnose recurring process failures and propose reversible instance changes | Approve itself, alter the north star, expand authority, or create another meta-loop |
| Promotion | Compare outcomes across project instances and propose a core improvement | Promote from one project or erase project-specific differences |

All state changes go through the controller's atomic commands. `control.db` is
the project-bound authority; direct `control.json` or `events.jsonl` edits are
export drift and never mutate governed truth. Each accepted mutation commits
one state revision, its exactly paired ordered event, current projections, and
any command-idempotency/inbox/outbox records in one SQLite transaction. Every
mutating CLI command carries a stable `--command-key`; the same key and
canonical argument digest is a revision-free retry, while a different digest
is a conflict. The paired event immutably retains the command name, key, and
canonical request digest. A stored replay acknowledgment carries its own
digest and is reconstructed against that event before the store can pass audit
or serve the replay. Every project-scoped table is audited
for foreign rows rather than filtering them from view. Completion review,
quality scoring/review, certification, P0
admission, repeat overrides, and adaptation review require externally issued
asymmetric grants. Adaptation review binds the exact proposal digest, program
version, independent reviewer, decision, nonce, and expiry. The controller
accepts only a configured public key from
`COMPANY_OS_ACTOR_GRANT_PUBLIC_KEY`; it contains no issuer, mint helper, shared
secret, or private-key path. Claims bind actor, action, resource, project,
program, work, cycle/checkpoint, dimension, decision, a canonical
command-payload hash, nonce, and expiry. The payload hash covers every
security- and decision-relevant argument: certification binds the exact
canonical governance digest; finish binds evidence IDs and their recomputed
digest, outcome, metrics, visibility, disposition, decision, reviewer, and
commit/ref; quality binds its full evidence checkpoint; and P0/repeat
admission binds its full queue decision. Audits reconstruct payloads from
retained governed records rather than trusting stored hashes. Full tokens and
the issuing public verification material remain in new audit records, so
signatures survive process restarts and issuer rotation; consumed nonces cannot
be replayed. Legacy accepted records that predate retained public keys are
checked against their token digest, exact claims, consumed nonce, and
transactional revision chain, but are explicitly warned as not
cryptographically replay-verifiable.

Evidence bytes are published to the immutable content-addressed store before
an authoritative record may reference them. Transaction atomicity covers the
SQLite state revision, event, projections, command records, and consumed grant
nonces. A rejected or crashed command may leave an unreferenced immutable blob;
that blob is non-authoritative, cannot become evidence without a later governed
record, and may be removed only by future reference-aware garbage collection.

The operator command center is a curated read-only projection of this
authority. It may disclose direction, gate state, work, quality, aggregate
usage, evidence counts, and safe runtime identity fields. It may not disclose
signed grants, nonces, issuer material, raw provider envelopes, or arbitrary
state. When SQLite exists it must read SQLite even if JSON exports are stale or
tampered. Markdown output treats project-controlled text as inert content;
JSON output uses a versioned projection schema. A presentation failure or
blocked gate cannot mutate controller state.

The public key does not prove launcher protection. Because a scheduler with unrestricted local authority could replace local files or environment configuration, the standalone controller exposes no local attestation bypass and keeps `protected_launcher_ready` and `scheduler_ready` false. A protected launcher/issuer attestation that this process cannot mint or replace is an explicit external deployment prerequisite, not a locally closed control.

Runtime observations use a different trust root. The controller reads only an
external public-key keyring named by `COMPANY_OS_OBSERVATION_GATEWAY_KEYRING`.
An observation is accepted only for one admitted attempt when both runtime and
its attempt inbox are explicitly enabled. Strict JSON parsing, signed identity
bindings, immutable raw-artifact hashes, key validity, nonce/event uniqueness,
monotonic provider sequence, and retained-history revalidation all fail closed.
Observation ingestion cannot launch work, advance lifecycle, accept a model,
consume a budget, reconcile a result, or schedule another cycle.

## Elasticity boundary

Each instance may adapt:

- departments and interfaces;
- discovery method;
- delivery method;
- metrics and scorecard;
- review cadence;
- work-in-progress limits within the core ceiling;
- model routing and research depth within budget;
- project-specific quality dimensions.

An instance may not autonomously adapt:

- user authority or approval requirements;
- production, financial, legal, privacy, or security boundaries;
- cancellation precedence;
- evidence integrity;
- cross-project data isolation;
- core-promotion threshold;
- meta-loop depth.

## Progress taxonomy

Only these outcomes count as progress:

1. **Reality:** verified new understanding of the actual project that changes a decision.
2. **Intelligence:** current evidence that changes the roadmap, architecture, or experiment.
3. **Experience:** a coherent prototype or journey that can be inspected.
4. **Capability:** a user can do something materially valuable they could not do before.
5. **Learning:** a bounded experiment resolves an important uncertainty.
6. **Adaptation:** an independently accepted operating improvement demonstrates better outcomes.

Audits, tests, schemas, migrations, hardening, refactors, and documentation are evidence or enablers. They do not count unless linked to one of the six outcomes.

## Evidence contract

Every evidence item must include:

- a unique ID and matching progress outcome;
- the current project ID and program version;
- an immutable project-local SHA-256 content address and matching digest, plus
  the descriptive project-local source path;
- observation time and bounded freshness;
- source and explicit decision impact;
- different author and reviewer;
- explicit quality dimensions when used for scoring.

Evidence used to complete work must additionally bind `outcome_id`, `work_id`, `cycle_id`, and `rubric_version`. Every applicable quality score and cited artifact must match the current primary outcome, work, and accepted phase checkpoint/cycle. Changing the primary clears prior quality applicability. Capability and innovation work reference a committed outcome. P0 work is the only interruption type and requires separately authenticated incident and independent approval grants.

Quality scores require dimension-specific evidence, a rubric version, separately authenticated scorer and reviewer identities, and a different reviewer. The certifier cannot be any work owner, evidence author/reviewer, completion reviewer, scorer, or quality reviewer. A non-empty object, generic evidence string, or repeated unsupported score is not evidence.

New evidence records bind immutable snapshot bytes rather than a mutable source
file. A legacy source-bound record or a snapshot-backed record that becomes
invalid may be superseded only through a paused, unscheduled, lease-free,
uncancelled, cycle-idle transition signed by an independent reviewer. The
review binds both digests, both IDs, the exact replacement metadata and
bindings, bucket, source path, and reason. The predecessor and full signed
transition remain in a linear audited history. Evidence referenced by a
completed cycle or accepted execution-fabric report is terminal and cannot be
superseded. Dependent quality scores are invalidated rather than silently
retargeted.

A structurally valid immutable record whose JSON `/commit` claim is factually
wrong is not structural drift and must not pass through `supersede-evidence`.
`correct-evidence` supports only the typed `git_commit_identity` transition:
the old value must match the archived snapshot, the new full SHA must resolve
locally as a commit, and the replacement may differ at no other path. Separate
signed declarant and independent adjudicator decisions bind the full
predecessor-record digest, both artifact hashes and IDs, old/new claim values,
the complete deterministic successor-record digest, transition timestamp,
governance binding, and reason. The old bytes and record remain append-only as
a semantic retraction; current and later-program audits recheck both immutable
content addresses and reject unsigned metadata. Completed-cycle/work and
accepted fabric evidence are terminal; certification and scheduling stay
disabled.

Changing the north star, current outcome, or success metric requires `replace-program`. That command increments the program version, revokes the active lease, cancels stale work, archives prior evidence, invalidates certification, disables scheduling, and returns the instance to a paused reality audit.

## Default portfolio limits

- Transformative capabilities: 65%.
- Innovation bets and prototypes: 20%.
- Direct enablers: at most 10%.
- Maintenance and audit: at most 5%.
- Active work: at most three items, with one primary vertical slice. Scheduler readiness requires exactly one ready primary item. Maintenance and enablers are never primary; use the existing typed `p0` work type for a genuine interruption.
- Meta-loop depth: one.
- Scheduler: one controller per project, gated by an independently verified protected launcher/issuer boundary outside the standalone controller.
- Quality: certification requires independently reviewed, dimension-specific evidence and scores for the deterministic dimensions applicable to the current phase and primary work. Every applicable critical dimension must score at least 9/10 and every applicable noncritical dimension at least 8/10; future production dimensions do not gate an experience prototype. Active work cannot leave its current phase before that gate passes, and entering the next phase clears prior scores.

Change project allocations only through an independently reviewed instance adaptation. The core ceilings remain binding.

Validate the allocation against completed cycle cost (or elapsed time when cost is zero), not only declared percentages. Two consecutive cycles without accepted product movement or learning are a drift failure and pause execution.

## Feedback recursion

At the end of a cycle:

1. Compare intended outcome, actual artifact, evidence, cost, latency, and user-visible movement.
2. Record drift and failure signatures.
3. When the same pattern occurs twice, or one severe control failure occurs, open an adaptation proposal.
4. Run the smallest reversible process experiment.
5. Have an independent reviewer accept, reject, or request another experiment.
6. Apply only to the project instance.
7. Consider core promotion only after the same mechanism improves at least three independent projects without weakening a protected boundary.

The meta-loop audits itself through its decision latency, false-positive adaptations, reversions, repeated drift, and cost-to-value ratio. It does not create a meta-meta-loop.

## Lifecycle contract

1. Record hashed evidence.
2. Advance one phase at a time.
3. Commit the product outcome and queue bounded work.
4. Independently certify the current program/evidence/work digest.
5. Activate the instance, then enable scheduling.
6. For `luna_fabric` work, bind a validated project-local manifest whose
   program, north star, outcome, work, manager ownership, worker models, limits,
   and write scopes match the governed program.
7. Acquire one fenced lease tied to the current program version, owner, explicit permitted transition list, generation, and expiry. Every leased transition presents that exact owner and an unexpired lease; rejection mutates neither state nor events.
8. Begin one cycle for one ready work item. A fabric becomes running and binds
   to that exact cycle.
9. Record manager reports in the fixed order charter, discovery, design,
   execution, verification, and integration. Each report cites project-local
   evidence bound to the same program, work, and cycle. A distinct Sol reviewer
   must accept verification.
10. Require a separately signed master decision for every manager barrier.
    Rework is capped at two rounds, blocked reports cannot continue, and phase
    skips or self-approval fail closed.
11. Finish with a signed reviewer whose canonical payload hash binds the cycle/lease generation, recorded evidence IDs and digest, actual outcome, cost, latency, tokens, user-visible movement, reviewer decision, reviewer, optional commit/ref, and `continue` or `complete` disposition. Revalidate evidence integrity, freshness, relevance, and bindings first. Fabric work cannot complete until every manager's integration is master-accepted. A completed item is archived with the evidence digest, an immutable completion digest, and this completion record before it leaves active work; rejected review cannot complete it.
12. Disable scheduling and invalidate certification after the cycle.
13. Release the exact lease generation.
14. Re-audit before any continuation.

Quality scoring binds distinct scorer and reviewer grants to the canonical set
of evidence IDs and a digest covering every cited artifact plus its
outcome/work/checkpoint/rubric binding. This allows genuinely independent
multi-artifact proof without weakening retained legacy single-artifact grants.

Certification hashes the canonical controller state and the signed certification payload binds that exact `governance_digest`. Only self-referential validation fields, consumed grant nonces, and live lease/fence, schedule, execution-timestamp, and activation-status fields are excluded because they change as a consequence of certification or execution rather than represent governable content. An expired lease may be reclaimed only to `resolve-cycle --action recover|abandon|fail`; a running cycle blocks ordinary release.

Schema upgrades from versions 1 through 8 preserve monotonic program history: archive the old strategy/work/evidence/cycles/adaptations/fabric/runtime state under the true old program version in a unique history record, advance to `old + 1`, clear current evidence and work, revoke leases and certification, reset the fabric and runtime, and create a paused `reality_audit` restart checkpoint that requires new evidence. Schema-8 attempts remain byte-for-byte in archived history and are never carried into the new program.

Cancellation increments the lease generation, revokes the active lease, clears active work, disables scheduling, invalidates certification, propagates `cancelled` to the execution fabric, and overrides later completion.
