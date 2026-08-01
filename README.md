# Company OS Core

Company OS is a project-isolated control plane for turning ambitious direction
into attributable, independently verified outcomes. This repository is the
canonical source for its controller, operating skills, execution contracts,
distribution tooling, and self-hosting program.

## Current reality

Version `0.3.0` adds a project-local transactional authority to the canonical
source and schema-9/core-2.6 observation trust boundary. New instances use
SQLite with full synchronous durability and WAL concurrency; existing valid
schema-9 instances migrate explicitly. State revisions, ordered audit events,
projections, trusted observation inboxes, effect outboxes, command
idempotency, and fenced leases commit under one project lock. JSON and JSONL
are deterministic compatibility exports, not authority. The controller can
verify and retain signed provider observations without changing attempt
lifecycle or launching work. It is **not yet an autonomous company**:
provider launch, lifecycle advancement, real Sol-manager/Luna-worker
execution, recursive dogfood, multi-project proof, and protected scheduling
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
python3 -m unittest discover -s tests -v
python3 skills/company-os/elastic-company-os/scripts/test_company_os_controller.py
python3 skills/company-os/elastic-company-os/scripts/test_control_store.py -v
python3 skills/company-os/elastic-company-os/scripts/test_runtime_observation_integration.py RuntimeObservationIntegrationTests
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

An existing, different installation is rejected unless `--force` is supplied.
Use `check-install` to compare without changing anything.
