---
name: direct-outcome
description: Own the durable Company OS objective lifecycle and automatically perform deterministic transitions from minimal discovery into a real bounded candidate, then build/calibrate independent evaluation just in time, rework dominant gaps, and close reality acceptance. Use as the master entry point for broad outcome-owned work.
---

# Direct Outcome

<!-- council-os:begin -->
## Board above executive management

Company OS owns the corporate hierarchy: **human owner → board → executive
management/master → managers → workers**. Company OS Web stores and displays
business data and context. It does not host or control the hierarchy.

At framework startup/resume, the executive loads `company-board` from this
Company OS distribution (`skills/company-os/company-board/SKILL.md` relative to
the distribution root). Establish or reconcile one persistent host-native board
chat for the active orchestration instance before adopting strategic direction.
Derive the instance from existing framework state; do not ask for a Web project
to contain the board. Managers escalate strategic matters through the executive.

Consult that board on company thesis, market entry/exit, material positioning or
business-model changes, strategic roadmaps, portfolio priorities, major resource
allocations, reorganization, pivots/stops, and conflicting executive proposals.
Inside its chat the board invokes `$council` with all 17 requested perspectives
and Karpathy's independent response → peer review → synthesis process. Use the
host's available agent tools and concurrency limits. A missing host capability
must remain visible; do not manufacture a running chat or completed council.

Bind advice to the exact instance, executive and board chat IDs, Program Contract
version, and canonical Company OS Web context revisions. The executive records
adoption/modification/rejection and translates direction into accountable goals
and manager charters through existing dispatch rules. Report measured results
back to the same board at the agreed review trigger. Reconsult on material changes;
routine execution under unchanged accepted direction continues without a meeting.

Follow `company-board` for provisioning, context grounding, artifacts, validation,
and the reporting loop. Human instructions retain authority. The board provides
strategic direction and challenge; it does not dispatch workers, grant permissions,
or enable feature-off runtime adapters or schedulers. An explicit human waiver is
recorded as such, never as a completed consultation.
<!-- council-os:end -->


The master should not memorize the Company OS pipeline. The director does.

The director is **execution-first**: discovery exists to make the first reversible real-artifact slice executable. Evaluator construction, calibration, benchmark hardening, and scale authority happen after a real candidate exists unless a consequential action requires them earlier.

## Start

```bash
python3 skills/company-os/direct-outcome/scripts/direct_outcome.py start \
  --project-root /absolute/project \
  --objective-id viral-game \
  --objective "Make a viral game."
```

The director bootstraps the broad objective, persists content-addressed state, and returns one `next_action`.

## Advance

On every scheduled wakeup and after every completed Company OS fabric:

```bash
python3 skills/company-os/direct-outcome/scripts/direct_outcome.py advance \
  --project-root /absolute/project \
  --objective-id viral-game
```

The director performs all safe deterministic work immediately. It stops only when agents must create, execute, observe, or independently evaluate real artifacts.

## Director stages

1. **discovery** — close only the unknowns required to define observable success, real artifact classes, the first execution path, and eventual evaluation.
2. **runtime stack** — materialize artifact/evaluator/benchmark contracts, but do not build the evaluator machinery yet.
3. **first-reality pilot** — bind a reversible pilot with at most two production lanes and require all real artifact classes to be represented by the candidate.
4. **candidate** — materialize, run, and observe the smallest connected end-to-end artifact. Production workers hand off exact artifact paths/classes/SHA256, not prose completion reports.
5. **evaluator capability, just in time** — once the candidate exists, register or build only the evaluators needed for that candidate.
6. **calibration, just in time** — prove evaluator discrimination against bound anchors after there is something real to judge.
7. **scale promotion** — after candidate existence and evaluator calibration, authorize production-scale evaluation and refresh the existing loop without discarding the candidate.
8. **evaluation/rework** — independently evaluate actual candidate bytes, identify the dominant gap, preserve passing dimensions, and repair the bottleneck.
9. **reality** — execute final reality acceptance against the original objective and actual artifact evidence.
10. **accepted** — terminal success.

## Master rule

Follow only the director's returned `next_action`. When it returns `execute_fabric`, run that exact manifest under the existing Company OS controller. When the fabric finishes, call `advance` again.

Do not replace execution with additional planning because planning feels safer. Do not build elaborate evaluator infrastructure before the first candidate. Do not treat accepted documents, schemas, tests, manager reports, or governance receipts as progress toward a user-facing artifact unless the original artifact contract explicitly requires them.

On every master heartbeat also apply `$govern-outcome-execution`: track Reality Level, global bottleneck, mission resource burn, and first-reality deadline. If R3 is absent after the configured first-reality budget fraction, pause broad research/speculative architecture/governance refinement and redirect the organization to implementation, integration, runtime, and repair.
