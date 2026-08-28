---
name: engineering-execution-constitution
description: Bind every Company OS coding or software-engineering workstream to the recursively inherited engineering execution contract that governs quality, evidence, and authority. Use when a master, manager, or worker admission carries software engineering scope and must derive or verify its engineering_execution_contract. Do not use for non-engineering workstreams or as a substitute for the active product route.
---

# Engineering Execution Constitution

This contract is mandatory for every Company OS coding or software engineering workstream.

## Recursive inheritance

Every master manager, mid level manager, lower level manager, and worker admission must carry an `engineering_execution_contract` derived from its parent. A child may specialize or strengthen the parent contract. It may never weaken, remove, or bypass a parent requirement.

The controller must fail closed when an engineering child is admitted without a valid inherited contract.

## Delivery loop

Engineering work must follow a resumable delivery loop inspired by Loom:

1. Preserve the original objective, requirements, architecture decisions, repository facts, task state, tests, runtime facts, repair history, and handoff evidence as durable project state.
2. Convert loose objectives into explicit scope, behavior, interfaces, ownership boundaries, runtime responsibilities, nonfunctional requirements, failure modes, and acceptance evidence before broad implementation fanout.
3. Split work into bounded tasks with explicit read scope, exclusive write ownership, verification intent, result evidence, and continuation rules.
4. Separate implementation from independent review and repair.
5. Resume from persisted state after interruption rather than reconstructing the project from conversational memory.

## Long horizon execution

Managers must use persistent goals, durable state, heartbeats, scheduled continuation, retained subagents, and direct agent communication when the runtime supports them. Long running work may not depend on one conversation remaining open. This follows the useful runtime properties demonstrated by Prime Agent without requiring Prime Agent itself as the Company OS runtime.

## Ownership

One writer owns a resource boundary at a time. Parallel teams may read broadly but their write scopes must not overlap unless an integration manager explicitly serializes the writes. Massive engineering work must partition by architectural ownership boundaries, not arbitrary agent count.

## Skill resolution

Before admitting an engineering worker, the manager must classify the task domains and bind applicable engineering skills. Required skills are part of admission evidence, not optional prompt context. Examples include framework practices, language practices, database engineering, testing, accessibility, performance, security, deployment, and observability.

If a required capability or skill does not exist, the manager must acquire, research, or build the missing capability before implementation continues.

## Artifact first execution

Workers must produce observable artifacts early. Source code, tests, plans, reports, and completion narratives are not equivalent to the product. Verification must inspect the running or rendered artifact in the modality that users experience it.

## Verification hierarchy

Applicable gates include:

1. Static correctness: formatting, lint, type checks, compilation.
2. Unit and component tests.
3. Integration and contract tests.
4. Build and packaging verification.
5. Runtime observation of the real application or service.
6. Browser, simulator, API, database, audio, video, game, performance, or other modality specific verification.
7. Independent engineering review.
8. Security verification when the attack surface warrants it.
9. Original objective reality acceptance.

Passing an earlier gate never implies a later gate passed.

## Security lane

For web applications and APIs with an authorized disposable local or staging target, Company OS may invoke Shannon as a proof by exploitation security evaluator. Shannon must never be pointed at systems outside explicit authorization or at production by default. Findings must remain evidence bound and remediation must be retested.

Security verification should also include applicable dependency, secret, configuration, authorization, authentication, injection, and infrastructure checks rather than treating one pentest engine as exhaustive.

## Control surface

T3 Code is a useful reference for a provider independent control and observability surface across coding agents. Company OS should expose project, agent, task, runtime, branch, evidence, and intervention state through a common control plane rather than coupling the operating model to one coding agent UI.

## Independent review

Production actors cannot provide final acceptance for their own work. Reviewers receive the original objective, relevant contracts, actual artifact evidence, runtime observations, benchmarks, and verification receipts. They do not treat the production team's completion narrative as acceptance evidence.

## Rework

When verification fails, identify the dominant constraint, preserve independently passing dimensions, and assign targeted repair. Repeated stagnation must trigger strategy or organization mutation rather than repeated polishing of the same failed abstraction.

## Completion

Engineering work is complete only when the actual integrated software has been observed behaving correctly against the original objective and all required verification gates have passed. A green test suite, merged pull request, successful build, worker completion report, or manager approval is insufficient by itself.
