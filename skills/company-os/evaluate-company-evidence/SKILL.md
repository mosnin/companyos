---
name: evaluate-company-evidence
description: Resolve Company OS evaluation methods from the governed evaluator-and-evidence registry. Use when a master or manager must design deterministic floors, independent semantic review, sealed challenges, transfer checks, or evidence requirements for a real company deliverable without loading benchmark repositories or inventing evaluator authority.
---

# Evaluate Company Evidence

Select evaluation methods before execution. This skill is a planning and
evidence contract, not an evaluator runtime and not acceptance authority.

## Resolve a method set

1. State the artifact classes and the evaluation stages required by the
   program contract.
2. Verify the checked-in registry:

   ```bash
   python3 scripts/evaluator_evidence_registry.py verify \
     --registry references/evaluator-evidence-registry.json \
     --source-intelligence ../source-intelligence/references/source-intelligence-registry.json
   ```

3. Resolve only the requested stages and artifact classes:

   ```bash
   python3 scripts/evaluator_evidence_registry.py resolve \
     --registry references/evaluator-evidence-registry.json \
     --source-intelligence ../source-intelligence/references/source-intelligence-registry.json \
     --artifact-class code \
     --stage deterministic_floor \
     --stage sealed_challenge \
     --stage transfer
   ```

4. Bind the returned registry and method digests into the program charter.
   Materialize actual evaluator adapters, calibration evidence, protected
   member manifests, challenge exposure state, and observed telemetry before
   claiming an evaluator is ready.

## Boundaries

- Research repositories contribute methods, never evaluator authority.
- A method marked `research_method_only` cannot score, accept, promote, or
  execute work.
- Deterministic floors run before semantic or pairwise review.
- Discovery, adaptive validation, sealed challenge, and real-work transfer are
  separate partitions. Exposure burns a sealed challenge.
- Judge failure is `invalid_evidence`; it is never zero, pass, or a usable
  score.
- Record member-level protected manifests, evaluator version and epoch,
  calibration evidence, artifact compatibility, evidence locators, and
  requested-versus-observed telemetry. Unknown observations remain null.
- The proposer, candidate owner, evaluator, confirmer, accepter, and promoter
  remain distinct.
- A benchmark result does not establish product, runtime, or business outcome.

The compact registry is safe to query. Do not load upstream repository bodies
into manager or worker prompts.
