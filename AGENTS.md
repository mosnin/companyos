# Company OS Core

This repository is the canonical source for Company OS. Installed Codex skills
are distributions and must not be edited as the source of truth.

## Scope

- Build and verify Company OS outside all managed client projects.
- Do not edit Chippy or use Chippy progress as Company OS progress.
- Keep runtime and scheduling feature-off until their acceptance gates pass.
- Treat `programs/company-os-self-hosting/reference/` as unintegrated reference
  code until it is ported into the canonical controller and independently
  accepted.

## Required sequence

1. Reality and source provenance.
2. Canonical packaging and reproducible bootstrap.
3. Durable transactional control state.
4. Provider-authenticated runtime lifecycle.
5. Real self-hosted manager and Luna-worker cycles.
6. Recursive adaptation and scorecard evidence.
7. Multi-project validation and protected scheduling.
8. Client onboarding, beginning with Chippy only after prior gates pass.

## Acceptance

- Every applicable score must be at least 8/10.
- Security, authority, durability, cancellation, and evidence integrity must be
  at least 9/10.
- Tests, documentation, schemas, and audits are enablers, not accepted product
  movement by themselves.
- Never claim a requested model is the observed runtime model.
- Rejected commands must not mutate governed state.
