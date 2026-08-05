# Company OS 0.5.1 Pre-Signing Review Interfaces v2

## Input contract

- Project/program: company-os-self-hosting
- Program version: 6
- Release candidate: ed4863b4d7832c03c1bc892aa768cdad32ba29b8
- Canonical baseline: 19fe809a9544303fb00150c957b317ed03c7a1a3
- Manifest implementation: 1e489780e6587a38c36e6e4bb38042dd8ed03835
- Verification carrier: a79fb8c37af674cbdd0609d5bc349145aebe5c8d
- Requested reviewer model: gpt-5.6-sol
- Operation: repository reads and non-writing local tests only

## Required review receipt

The reviewer reports to task:019fa4e9-cd80-7bd2-9416-c8dce5a7e8c3:

- exact commit, tree, baseline, branch, cleanliness, and changed paths;
- requested model separated from observed model and unavailable telemetry;
- exact tests, results, skips, failures, and residue;
- expected stale-signature rejection;
- findings with severity, evidence location, impact, and required repair;
- numeric scores for security, authority, durability, cancellation, evidence
  integrity, reliability, maintainability, tests, observability, rollback, and
  other applicable dimensions;
- pre_signing as READY-TO-SIGN or REWORK;
- separate source_release, install_permission, runtime_permission, and
  scheduler_permission decisions.

READY-TO-SIGN requires zero open P0/P1, every required check passing, each
critical score at least 9.0, and every other applicable score at least 8.0. It
does not authorize signing. All four downstream decisions remain NO-GO or DENY
in this phase.

## Fail-closed rules

The receipt must not invent observed model, host identity, tokens, cost,
provider execution, cancellation acknowledgement, runtime activation,
scheduler readiness, installation, deployment, production, or Chippy evidence.
Any write or external side effect invalidates the review.
