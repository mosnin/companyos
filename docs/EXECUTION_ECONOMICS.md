# Execution Economics

Field evidence from running Company OS on real missions showed a consistent
failure mode: the system became a competent bureaucracy. It produced
comprehensive plans, burned very large token budgets on research, architecture,
and governance artifacts, and had trouble actually acting. This document
records the mechanistic diagnosis and the enforcement — in code, not doctrine —
that now taxes planning and subsidizes action.

## The diagnosis

Doctrine alone did not fail for lack of words. Five separate skills already
said "act early, cap research." The system still over-planned because its
*enforced* economics rewarded planning:

1. **Planning was free.** The budget meter measured wall-clock time only. A
   mission could burn 40% of its token allowance on research in its first
   minute and the governor still reported an on-track budget fraction.
2. **Documents satisfied gates.** Artifact observation methods like
   `file_exists`, `nonempty`, and `text_review` counted as acceptance
   evidence, so a written plan could clear a gate that was meant to prove a
   running capability.
3. **Hierarchy was paid by default.** Every pilot compiled one production lane
   per artifact class — managers, packets, and reports multiplied before any
   artifact existed.
4. **Action carried the ceremony tax.** Scoring one quality checkpoint took
   two signed grants *per dimension* (~76 signatures for the full 38-dimension
   scorecard), while writing another plan required none.
5. **Nobody priced the spend.** The operator brief reported phases, gates, and
   grants, but never tokens per accepted deliverable, so unconverted burn was
   invisible.
6. **Five control layers loaded per dispatch.** Masters were told to run
   goal-route, mission-control, navigation, and governor skills side by side,
   so every boundary paid a doctrine-rereading tax.

Each mechanism below closes one of those gaps. All of them are enforced by
controller code with tests; none of them depends on an agent choosing to obey.

## Enforced mechanisms

### 1. Token-aware planning meter (pre-action budget gate)

*Code:* `skills/company-os/mission-execution-control/scripts/mission_control.py`,
`skills/company-os/govern-outcome-execution/scripts/executive_governor.py`
· *Tests:* `tests/test_planning_meter.py`

A mission may spend at most `FIRST_ARTIFACT_BUDGET_FRACTION` (default **0.25**)
of its budget before the first real artifact exists (Reality Level ≥ 1). The
budget fraction is now `max(time_fraction, token_fraction)`:

- `initialize_state(..., token_budget=N)` (CLI: `init --token-budget N`)
  declares the mission's token allowance.
- Every recorded event may carry a `tokens` field; `record_event` accumulates
  it into `state["tokens_consumed"]`, so token burn advances the meter with no
  wall clock at all.
- Past the threshold with no artifact, the governor decision sets
  `planning_overrun: true`, forces compression mode, and pauses `research`,
  `architecture`, `governance`, and `documentation` work classes.
- `admit_work` rejects paused work classes fail-closed. Implementation,
  integration, runtime, and repair stay admissible.

Missions without a declared token budget keep time-only metering — the meter
never guesses.

### 2. Executed-evidence-only acceptance

*Code:* `skills/company-os/define-outcome-artifacts/scripts/compile_artifact_observations.py`
· *Tests:* `tests/test_artifact_observations.py`

A required artifact class whose observation methods are all *weak*
(`file_exists`, `nonempty`, `normalized_nonempty`, `hash_matches`,
`build_succeeds`, `text_review`) raises a `TEXT_ONLY_OBSERVATION` blocker. At
least one method must execute the artifact — run it, probe it, exercise its
behavior. A document describing the artifact can no longer clear the gate that
proves the artifact. Advisory (`required: false`) classes are exempt.

### 3. Direct topology below the complexity threshold

*Code:* `skills/company-os/elastic-company-os/scripts/outcome_loop.py`
· *Tests:* `tests/test_outcome_loop.py`

Hierarchy is earned by scale, not paid by default. A pilot with at most
`DIRECT_TOPOLOGY_MAX_ARTIFACT_CLASSES` (**2**) required artifact classes
compiles **one** production lane — one manager, one worker, organization mode
`direct_pilot`. Small outcomes get a master→worker line instead of an org
chart; the multi-lane topology appears only when the artifact surface actually
demands it.

### 4. Batched grant ceremony (`score-quality-batch`)

*Code:* `skills/company-os/elastic-company-os/scripts/company_os_controller.py`
· *Tests:* `test_company_os_controller.py` (batch scoring, tamper, re-score suites)

One checkpoint, two signatures. The `score-quality-batch` command records the
entire scorecard under a single scorer grant and a single independent-reviewer
grant. The grant decision binds `sha256` of the canonical score set
(`score-batch:<digest>` / `review-batch:<digest>`), and the shared payload
hash binds every dimension, score, evidence id, and evidence digest — so the
ceremony is cheaper but not weaker:

- Each dimension record stores a self-contained copy of the signed score set
  (`batch.scores` + `batch.scores_sha256`). Audit replays the signature
  against the stored copy and cross-checks the record's own entry, so
  tampering with either the record or the copy is detected per dimension.
- An individual `score-quality` re-score of one dimension clears only that
  dimension's batch marker; sibling batch records stay independently valid.
- Nonce consumption, issuer pinning, program-version pinning, checkpoint
  binding, and evidence validation are identical to the per-dimension path.

For the 38-dimension base scorecard this replaces ~76 grant ceremonies per
checkpoint with 2.

### 5. Execution economics on the operator brief

*Code:* `skills/company-os/elastic-company-os/scripts/operator_brief.py`
· *Tests:* `test_operator_brief.py` (`ExecutionEconomicsTests`)

Every brief now carries an `economics` block and a rendered
"Execution economics" section: tokens observed across runtime attempts, the
granted token budget, accepted receipts, and **tokens per accepted receipt**.
Spend with zero accepted deliverables renders an explicit
"⚠ Unconverted spend" warning. The operator sees the price of bureaucracy on
the same page as the status it used to hide behind.

### 6. One dispatch loop

*Code/doctrine:* `skills/company-os/company-os/SKILL.md`,
`skills/company-os/mission-execution-control/SKILL.md`

`$mission-execution-control` is the single dispatch-boundary control layer.
Its `mission_control.py` already invoked the navigation module and executive
governor programmatically; the skill surface now says so. `$goal-route-system`
(compile-time), `$navigation-control`, and `$govern-outcome-execution` are
documented as internal mechanisms — masters load one control skill at the
boundary, not four overlapping layers of doctrine.

## Operating the mechanisms

```bash
# Declare a token budget at mission start (enables token-aware metering):
python3 mission_control.py init --mission-id m1 --objective "…" \
  --mission-class bounded_feature --token-budget 2000000

# Record token spend on any event (accumulates into the meter):
#   make_event(..., tokens=125000.0)

# Score a whole checkpoint with one ceremony:
python3 company_os_controller.py score-quality-batch --project . \
  --scores scores.json --rubric-version quality-v1 \
  --scored-by scorer --reviewed-by reviewer \
  --scored-by-grant <token> --reviewed-by-grant <token> \
  --outcome-id cap-1 --work-id cap-1 --cycle-id <checkpoint> \
  --command-key <key>
# scores.json: [{"dimension": …, "score": …, "evidence_ids": […],
#               "evidence_digest": … | "artifact_digest": …}, …]
```

The batch grants sign `resource "quality:batch"`, `dimension "quality-batch"`,
actions `score-quality-batch` / `score-quality-review-batch`, decisions
`score-batch:<scores_sha256>` / `review-batch:<scores_sha256>`, and the
payload hash of `command_payload_hash("score-quality-batch", …)` over the
canonical score set plus the shared rubric/actor/checkpoint fields
(`normalized_batch_scores` + `quality_batch_payload` in the controller).

## What remains doctrine

Not everything is enforceable in the controller, and pretending otherwise
would be its own bureaucracy. Still doctrine, deliberately:

- Mode discipline inside a work class (e.g. "narrow research to the named
  blocker") — the meter can pause a class, not read intent inside one.
- Preferring supplied capabilities over reimplementation — enforced only as
  review posture and governor manager-orders.
- The reality map narrative (R0–R5 classification quality) — the levels are
  computed from evidence flags, but choosing honest flags is on the evidence
  pipeline and its reviewers.

The test of every future control-plane addition is the same question this
document answers: **does it make acting cheaper than planning, or the
reverse?** A mechanism that adds ceremony to action without adding at least as
much friction to unconverted planning burn repeats the failure this page
exists to prevent.
