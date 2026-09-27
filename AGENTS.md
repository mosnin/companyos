# Company OS Core

This repository is the canonical source for Company OS. Installed Codex skills
and installed Grok Bot / Cursor / Claude skills are distributions and must not be edited
as the source of truth.

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

## External skill intake through Find Skills OS

When a capability gap requires discovering or integrating an external skill, use
`$find-skills-os`, then its mandatory `$skill-integration-os` stage. The shared
plugin lives in the canonical `mosnin/find-skills-os` repository. Review actual
kernel ownership, adapt the selected skill, and run its `integrate.py check` and
`stage` commands before native admission. If the shared plugin is unavailable,
report that intake dependency; do not silently bypass the adaptation gate.

Use the project foundry and exact capability assignment/Program Preflight gates after staging. Never import an unapproved candidate directly into the approved catalog.
A complete relevant ownership review may create a separate candidate peer kernel;
a partial or inaccessible catalog cannot establish absence. Staging is not
approval, execution authority, or accepted integration.

## Portable library release gate

The library uses os.config.json plus skill.json schema v2 and generated
catalog/os-builder indexes. Record original GitHub/npm sources inside each skill;
keep native provenance and authority intact. Regenerate native metadata first,
then run OS Builder format and check before publication/distribution. Company OS
and Business OS's local plugin updater now runs this check before replacement.
