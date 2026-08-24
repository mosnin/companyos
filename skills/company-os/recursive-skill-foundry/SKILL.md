---
name: recursive-skill-foundry
description: Create, validate, simulate, iteratively repair, version, recursively compose, promote, search, and assign project local Codex skills inside Company OS. Use when the user explicitly asks for a reusable skill or skill system, or when accepted field evidence proves that a mechanism should compound across future work. Do not use for one off work, speculative abstraction, generic documentation, or as a substitute for completing the active product route.
---

# Recursive Skill Foundry

## Objective

Convert explicit reusable capability requests and evidence backed repeated mechanisms into project local skills that are versioned, content addressed, simulated, independently verifiable, and loadable by later Company OS managers and workers.

The foundry is an actuator only when skill creation is the requested destination or a missing reusable capability directly blocks the active route. Otherwise it is a post checkpoint learning process and does not count as product movement.

## First Principles Model

1. A skill is compressed operational knowledge, not another report.
2. A skill is useful only when it changes future agent behavior reliably.
3. Candidate bytes are untrusted until deterministic validation and held out simulation pass.
4. A learned mechanism needs repeated field evidence before promotion.
5. Recursive skill systems need strict depth, node, scope, authority, and cycle bounds.
6. Accepted skills are immutable versions. Repairs create a replacement version and preserve the failing case as a regression.
7. Project promotion is local. Shared Company OS core promotion requires multi project evidence and independent review.

## Source map

1. `scripts/skill_foundry.py`
   Run the deterministic candidate, simulation, repair, recursion, evidence, promotion, search, verification, and assignment controller.
2. `references/foundry-contract.md`
   Read for storage, promotion, recursion, and Company OS integration invariants.
3. `references/beem-adaptation.md`
   Read for the selectively adapted Beem mechanisms and the mechanisms deliberately excluded.
4. `examples/simulation-cases.json`
   Read when extending the factory simulation or adding a regression.

## Admission rule

Use the foundry only when one of these is true:

1. The user explicitly requests a Codex skill, reusable workflow, or skill system.
2. The current Company OS navigation route is blocked by a missing capability whose expected reuse value exceeds the cost of creating it.
3. A completed mission or checkpoint produced at least two accepted independent uses of the same reusable mechanism.

Do not invoke it merely because work can be abstracted. Complete the active route first.

## Standard workflow

1. Search the project registry before creating anything.
2. If an exact promoted skill exists, verify its digest and assign it.
3. If no exact skill exists, classify the request as explicit skill creation, evidence backed learning, or one off work.
4. Forge a candidate with a bounded trigger, exclusions, workflow, validation, output contract, safety boundary, examples, and only justified resources.
5. Run strict validation and held out trigger simulation.
6. Repair deterministic defects and rerun the same checks. Stop after the bounded repair budget.
7. For a skill system, validate the dependency tree, reject cycles, enforce depth and node limits, build child candidates, then bind a coordinator manifest.
8. Promote an explicit request only after validation and simulation pass. Promote a learned mechanism only after two accepted independent field receipts.
9. Install the accepted project skill under `.agents/skills/<skill-name>` so later Codex threads can discover it.
10. Search and assign no more than four project skills to one manager or worker packet, with exact entrypoint hashes and explicit execution order.
11. Verify installed bytes before every assignment. Drift fails closed.

## Commands

Forge one candidate:

```bash
python3 skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py forge \
  --project-root /absolute/project \
  --request "Create a reusable Codex skill that repairs failed deployment builds" \
  --promote
```

Forge a bounded recursive system:

```bash
python3 skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py forge-system \
  --project-root /absolute/project \
  --spec /absolute/system-request.json \
  --promote
```

Record accepted field evidence for a learned mechanism:

```bash
python3 skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py record-evidence \
  --project-root /absolute/project \
  --skill-name deployment-build-repair \
  --run-id run-one \
  --objective-id objective-one \
  --project-id project-one \
  --outcome accepted \
  --artifact-sha256 <64-hex> \
  --notes "Independent runtime checks passed"
```

Search and assign promoted project skills:

```bash
python3 skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py search \
  --project-root /absolute/project \
  --query "deployment repair"

python3 skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py assign \
  --project-root /absolute/project \
  --assignment-id release-worker \
  --role worker \
  --skill deployment-build-repair \
  --execution-order deployment-build-repair \
  --rationale /absolute/rationale.json \
  --output /absolute/assignment.json
```

Run the full foundry simulation:

```bash
python3 skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py simulate-foundry \
  --project-root /absolute/disposable-project \
  --output /absolute/simulation.json
```

## Recursive contract

1. Maximum depth is three.
2. Maximum skill nodes in one system is twelve.
3. Skill names must be unique across the system.
4. A skill cannot depend on itself or an ancestor.
5. Child skills cannot widen tools, permissions, cost, time, side effects, or write scope.
6. The coordinator stores exact component candidate and skill digests.
7. Core promotion is never automatic.

## Promotion contract

Project promotion requires candidate status `validated`, a passing quality threshold, held out simulation status `pass`, no rejected field evidence, and an exact content addressed manifest. Learned mechanisms additionally require two accepted independent field receipts.

Shared Company OS core promotion additionally requires evidence from at least three independent projects, a fresh independent review, and an explicit integration change outside the foundry.

## Validation

Verify exact frontmatter, trigger boundaries, required procedural sections, referenced resources, no symlink or absolute path escapes, direct and near neighbor examples, safety boundaries, content digests, recursion limits, promotion evidence, and installed byte drift rejection.

## Output contract

Return the create, skip, validate, fail, promote, or block decision, candidate version and digest, skill digest, validation score, simulation cases, repair rounds, recursion lineage, field evidence count, installed entrypoint, registry digest, and concrete blocker.

## Safety

Never let generated skills widen authority, expose secrets, bypass approvals, hide behavior, suppress monitoring, create covert persistence, or perform destructive or consequential external effects outside the active Company OS packet. A skill candidate cannot self promote or declare itself accepted.
