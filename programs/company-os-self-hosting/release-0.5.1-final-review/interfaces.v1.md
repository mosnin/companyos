# Company OS 0.5.1 Final Release Review Interfaces v1

## Input contract

- Project/program: `company-os-self-hosting`
- Program version: `6`
- Release candidate: `ca09765716f468f37916d546c636286060ae616c`
- Canonical baseline: `19fe809a9544303fb00150c957b317ed03c7a1a3`
- Requested reviewer model: `gpt-5.6-sol`
- Operation: repository reads and non-writing local tests only

## Required review receipt

The reviewer reports one receipt to
`task:019fa4e9-cd80-7bd2-9416-c8dce5a7e8c3` containing:

- exact reviewed commit, tree, baseline, branch, cleanliness, and changed paths;
- requested model separately from observed model and all unavailable telemetry;
- exact test commands, results, skips, failures, and residue observations;
- findings with severity, file/evidence location, impact, and required repair;
- numeric scores and evidence for security, authority, durability,
  cancellation, evidence integrity, and every other applicable dimension;
- three independent decisions named `source_release`, `install_permission`, and
  `runtime_scheduler_permission`.

`source_release` is `ACCEPT` only with zero open P0/P1 findings, all required
checks passing, each critical score at least 9.0, and each other applicable
score at least 8.0; otherwise it is `REWORK`.

`install_permission` is independently `ALLOW` or `DENY` and states whether a
later separately authorized actor may attempt a transactional install. It must
not claim that installation occurred.

`runtime_scheduler_permission` contains separate `runtime` and `scheduler`
values, each `ALLOW` or `DENY`. Both default to `DENY`; either requires separate
live, protected, independently accepted evidence unavailable from source-only
review. Runtime permission never implies scheduler permission.

## Fail-closed rules

The receipt must not invent observed model, host identity, tokens, cost,
provider execution, cancellation acknowledgement, runtime activation,
scheduler readiness, installation, deployment, production, or Chippy evidence.
Any prohibited side effect invalidates the review receipt.
