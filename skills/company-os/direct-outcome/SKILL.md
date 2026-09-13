---
name: direct-outcome
description: Own the durable Company OS objective lifecycle and automatically perform deterministic transitions from minimal discovery into a real bounded candidate, then build/calibrate independent evaluation just in time, rework dominant gaps, and close reality acceptance. Use as the master entry point for broad outcome-owned work.
---

# Direct Outcome

<!-- council-os:begin -->
## Board and executive conversations

Company OS owns **owner → board → executives → managers → workers**. Company OS
Web stores business context. At startup/resume the entry conversation loads
`company-board` (`skills/company-os/company-board/SKILL.md` from this distribution)
and reconciles the instance's board conversation in its host project.

The board creates executive conversations with `company-executive`; executives
create manager conversations; managers create Luna worker conversations. Every
management role has its own native thread in the same host project, with explicit
parent/return IDs and message acknowledgements. Executives and managers use
`gpt-6-astra` at `medium` reasoning; workers retain `gpt-5.6-luna`.

Consult `$council` inside the board on strategic direction, major roadmap/resource
changes, pivots/stops and executive conflict. Bind its 17-member deliberation to
the instance, responsible executive, program version and Web context revisions.
Executives record disposition, apply existing dispatch rules, and report measured
results back to the board. Routine work under accepted direction continues.

Follow `company-board` for provisioning and reconciliation. Human authority and
existing execution gates remain; appointments do not enable feature-off schedulers
or permit direct board-to-worker dispatch. Report unavailable host capabilities
honestly. An explicit human waiver is recorded as a waiver, not a council result.
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
