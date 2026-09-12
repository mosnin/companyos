---
name: direct-outcome
description: Own the durable Company OS objective lifecycle and automatically perform deterministic transitions from minimal discovery into a real bounded candidate, then build/calibrate independent evaluation just in time, rework dominant gaps, and close reality acceptance. Use as the master entry point for broad outcome-owned work.
---

# Direct Outcome

<!-- council-os:begin -->
## Board above management

The hierarchy is **human owner → Council OS advisory board → Company OS executive
management/master → program managers → workers**. Council OS informs high-level
direction; the human owner and existing authorization rules retain decision authority.

Automatically invoke `$council` before adopting a company thesis, market entry or
exit, material positioning/business-model change, portfolio reprioritization,
resource allocation outside the accepted budget, strategic reorganization, or a
major continue/pivot/stop decision. Also consult when executive recommendations
conflict. Do not wait for the user to type the command. Routine work under an
unchanged accepted charter proceeds without another board session.

Resolve the installed `council` skill (plugin-qualified name `council-os:council`
when required) from the host skill registry and follow its full 18-member process.
Use Codex-native agents by default. If unavailable, name the missing consultation
capability; do not manufacture a council result. Continue independent reversible
work, but leave the strategic adoption gate pending. The user can explicitly waive
consultation for a decision; record the waiver instead of implying board review.

Pass a project-local packet containing decision ID, question, company context,
options, evidence, constraints, and decision owner. Preserve all mandatory user
requirements. Store the packet and complete, validated advisory record under
`.company-os/council/<decision-id>/`. Bind it to the exact packet digest. Reuse an
unchanged decision record; reconsult on material changes to scope, evidence,
options, constraints, or direction. Avoid recursive consultation: the council does
not dispatch management or invoke itself.

Before strategic dispatch, the master records its adoption, modification, or
rejection and rationale, decision owner, record path/digest, management owner,
success metric and review trigger in the Program Contract or decision log. Preserve
minority concerns. A board memo is advice, not execution approval or proof of
runtime, provider, or business outcomes. Managers escalate strategic changes to
the master and may not bypass this consultation by changing their own charters.

This is a skill-orchestration consultation gate. It does not change controller
schemas, grant new runtime permissions, or enable schedulers.
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
