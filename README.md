# Company OS Core

Company OS is a project-isolated control plane for turning ambitious direction
into attributable, independently verified outcomes. This repository is the
canonical source for its controller, operating skills, execution contracts,
distribution tooling, and self-hosting program.

## Current reality

Version 0.6.0 adds an outcome control plane to the canonical Company OS product line. Broad objectives can enter discovery without the operator already knowing the domain terminology. Before elastic execution, Company OS must close blocking unknowns with cited evidence, define observable artifact classes, compile executable independent evaluators, bind benchmark tiers, and prove those evaluators can distinguish poor, intermediate, and excellent candidates.

A bounded pilot remains limited to two managers, three workers per manager, and six total workers. Any larger elastic organization is production scale and requires a content bound authorization over the exact outcome, artifact, evaluator, benchmark, and calibration contracts. Contract drift invalidates the execution fabric. Final completion requires an accepted reality receipt derived from actual artifact evidence and bound to the original objective. A production team completion narrative cannot substitute for that receipt.

The 0.5.1 Operator Command Center review remains preserved as historical release evidence. Its exact twenty one reviewed files now live in a committed historical bundle materialized from carrier `166cbcc189074d70d0953e2897c85bc4791a39d2`. The verifier checks that bundle, the signed manifest, the bundled reviewer public key fingerprint, and the detached signature without environment variables or GitHub repository settings. It explicitly does not claim that the current 0.6.0 source files were accepted by the 0.5.1 reviewer.

The controller remains project isolated and fail closed. SQLite state, ordered events, leases, evidence, quality decisions, execution fabric state, and reality acceptance are locally auditable. Provider execution, protected recurring scheduling, spending, deployment, and other consequential external effects still require their existing authority boundaries.

## Repository map

- `skills/company-os/` — company direction, operations, intelligence, and the
  Elastic Company OS controller.
- `skills/company-os/company-blueprint/` — operator intake and deterministic
  compilation of company archetypes, departments, capabilities, playbooks,
  routines, knowledge, assets, integrations, storage, and work graphs.
- `skills/company-os/select-execution-loop/` — deterministic selection of one
  bounded task-shaped loop plus compatible diagnostic, learning, and durable
  event adapters.
- `skills/autonomy-suite/` — bounded loops, work graphs, quality, routing, and
  the Luna Execution Fabric contract.
- `programs/company-os-self-hosting/` — versioned program contracts, evidence,
  and the preserved pre-integration observation reference.
- `scripts/distribution.py` — deterministic manifest, install, and installed
  distribution verification.
- `tests/` — the repository-wide test suite covering the product surface:
  provenance, clean bootstrap, distribution, the outcome control plane, the
  skill-surface linter, and canonical-digest golden vectors.
- `docs/` — architecture, stage-gated roadmap, and the enforced execution
  economics ([docs/EXECUTION_ECONOMICS.md](docs/EXECUTION_ECONOMICS.md)):
  the anti-bureaucracy mechanisms that keep acting cheaper than planning.

## Verify

This is the same battery `.github/workflows/ci.yml` runs on every push:

```bash
python3 scripts/distribution.py verify-manifest
python3 scripts/verify_operator_command_center_surface.py
python3 scripts/validate_skill_surface.py
python3 -m unittest discover -s tests -v
python3 skills/company-os/mission-execution-control/scripts/execution_regression_lab.py --json
python3 skills/company-os/goal-route-system/scripts/goal_route.py simulate
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
  --prior-manifest /absolute/accepted-0.5.1/distribution-manifest.json \
  --prior-version 0.5.1
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

The bundled reviewer identity and public key fingerprint are versioned integrity anchors for the preserved 0.5.1 historical review. A local clone needs no secret, environment variable, or repository configuration to verify it. Trust in the repository itself still comes from the release or commit channel used to obtain the clone.
