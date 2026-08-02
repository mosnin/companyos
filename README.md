# Company OS Core

Company OS is a project-isolated control plane for turning ambitious direction
into attributable, independently verified outcomes. This repository is the
canonical source for its controller, operating skills, execution contracts,
distribution tooling, and self-hosting program.

## Current reality

Version 0.5.0 is the accepted globally distributed source release. It adds
concise global Sol-manager and Luna-worker role skills, strict v2 mission
contracts, deterministic task-evidence validation, and a five-scenario
simulation ladder. After two rejected candidates and bounded rework,
independent exact-commit review of `0900cfe` found 0 P0, 0 P1, and 0 P2 defects
and scored the source contract 9.1/10. In this development session the Sol
manager manually used native Codex task tools; the Company OS controller still
does not invoke, admit, cancel, or durably observe them.

Version 0.5.0 retains the independently accepted 0.4.3 Operator Command Center
and its two locally verified, feature-off foundations. First, program replacement
now uses a positive, versioned archive schema and rejects credential-shaped or
unknown runtime material transactionally. Second, a provider-neutral lifecycle
contract and fixture-only OpenAI Responses gateway prove signed request/result
separation, bounded usage provenance, cancellation receipts, and crash-safe
no-relaunch semantics. This source release does not enable a provider,
scheduler, or autonomous execution. Global skill availability is not runtime
certification.

It also preserves the 0.4.2 semantic-evidence correction for one narrowly
typed failure: a structurally valid immutable JSON record whose `/commit`
identity is factually wrong. The transition is append-only, dual-authorized,
content-addressed, lineage-audited, and unable to perform generic semantic
edits. Quality scores continue to bind a canonical set of independent
artifacts and fail closed on duplicate IDs, digest substitution, or
evidence-set drift.

The Operator Command Center remains a
read-only decision surface on top of immutable, content-addressed evidence,
signed evidence supersession, and enforced phase-exit quality gates. `brief`
turns authoritative state into one safe Markdown, JSON, or self-contained HTML
surface: outcome, stage, governed change, exact next move, quality, work,
supervision, evidence, cost, blockers, and non-claims. It never exposes signed
grants or treats a mutable export as authority. The accepted experience scored
9.22/10 with every one of 13 critical product dimensions at or above 9.0.

These capabilities extend the project-local transactional authority and
schema-9/core-2.6 observation trust boundary. New instances use
SQLite with full synchronous durability and WAL concurrency; existing valid
schema-9 instances migrate explicitly. State revisions, ordered audit events,
projections, trusted observation inboxes, effect outboxes, command
idempotency, and fenced leases commit under one project lock. JSON and JSONL
are deterministic compatibility exports, not authority. The controller can
verify and retain signed provider observations without changing attempt
lifecycle or launching work. It is **not yet an autonomous company**:
controller-native admission, hard cancellation, clean two-Luna integration,
installed fresh-thread role proof, recursive dogfood, and protected scheduling
remain gated roadmap work.

Chippy is not part of this repository and is frozen as a Company OS client
until the standalone self-hosting gates pass.

## Repository map

- `skills/company-os/` — company direction, operations, intelligence, and the
  Elastic Company OS controller.
- `skills/autonomy-suite/` — bounded loops, work graphs, quality, routing, and
  the Luna Execution Fabric contract.
- `programs/company-os-self-hosting/` — versioned program contracts, evidence,
  and the preserved pre-integration observation reference.
- `scripts/distribution.py` — deterministic manifest, install, and installed
  distribution verification.
- `tests/` — repository-level provenance and clean-bootstrap tests.
- `docs/` — architecture and stage-gated roadmap.

## Verify

```bash
python3 scripts/distribution.py verify-manifest
python3 scripts/verify_operator_command_center_surface.py \
  --expected-reviewer-id "$COMPANY_OS_OCC_REVIEWER_ID" \
  --expected-reviewer-public-key-der-sha256 \
  "$COMPANY_OS_OCC_REVIEWER_PUBLIC_KEY_DER_SHA256"
python3 -m unittest discover -s tests -v
python3 skills/company-os/elastic-company-os/scripts/test_company_os_controller.py
python3 skills/company-os/elastic-company-os/scripts/test_control_store.py -v
python3 skills/company-os/elastic-company-os/scripts/test_runtime_observation_integration.py RuntimeObservationIntegrationTests
python3 skills/company-os/elastic-company-os/scripts/test_operator_brief.py -v
python3 -m unittest discover -s programs/company-os-self-hosting/reference -v
python3 skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_fabric.py --self-test
```

## Distribution

Generate or verify the committed content-addressed manifest:

```bash
python3 scripts/distribution.py write-manifest
python3 scripts/distribution.py verify-manifest
```

Install into an empty skills root:

```bash
python3 scripts/distribution.py install --target /absolute/skills/root
```

An existing, different installation is rejected. A controlled upgrade must
prove the exact expected prior version and manifest before either skill bundle
is replaced. Both bundles are staged and verified first, then replaced as one
transaction with rollback on any failure. `--force` is never a blind overwrite.
Use `check-install` to compare without changing anything. If it detects an
interrupted journal or orphaned transaction directory, it fails without
restoring or deleting anything. Run the explicit recovery command first:

```bash
python3 scripts/distribution.py recover-install --target /absolute/skills/root
```

```bash
python3 scripts/distribution.py install \
  --target /absolute/skills/root \
  --prior-manifest /absolute/accepted-0.3.1/distribution-manifest.json \
  --prior-version 0.3.1
```

## Operator command center

Render the current project decision surface without changing state:

```bash
python3 skills/company-os/elastic-company-os/scripts/company_os_controller.py brief \
  --project /absolute/project/path \
  --format markdown
```

Use `--format json` for an agent-readable projection and `--strict` when a
blocked gate should return a nonzero exit status. Use `--format html` for the
accessible, responsive Operator Command Center; it has no client script and
remains a read-only projection of the same governed state.

The accepted visual, adversarial, and Learning evidence lives in
`programs/company-os-self-hosting/`. It is release evidence for this capability,
not a claim that provider execution, recursive self-hosting, protected
scheduling, or Chippy onboarding is complete.

The two Operator Command Center reviewer values are non-secret trust anchors,
but they must come from the independently governed Company OS delegation rather
than a repository default. CI reads them from repository variables and fails
closed when either value is absent or changed.
