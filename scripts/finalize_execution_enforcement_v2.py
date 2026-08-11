#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PERMANENT_CI = '''name: Company OS Core

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Verify distribution manifest
        run: python3 scripts/distribution.py verify-manifest
      - name: Verify repository suite
        run: python3 -m unittest discover -s tests -v
      - name: Verify execution regression lab
        run: python3 skills/company-os/mission-execution-control/scripts/execution_regression_lab.py --json
      - name: Verify operator command center
        run: python3 scripts/verify_operator_command_center_surface.py
      - name: Verify controller
        run: python3 skills/company-os/elastic-company-os/scripts/test_company_os_controller.py
      - name: Verify control store
        run: python3 skills/company-os/elastic-company-os/scripts/test_control_store.py -v
      - name: Verify runtime observations
        run: python3 skills/company-os/elastic-company-os/scripts/test_runtime_observation_integration.py RuntimeObservationIntegrationTests
      - name: Verify operator brief
        run: python3 skills/company-os/elastic-company-os/scripts/test_operator_brief.py -v
      - name: Verify self hosting references
        run: python3 -m unittest discover -s programs/company-os-self-hosting/reference -v
      - name: Verify execution fabric
        run: python3 skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_fabric.py --self-test
      - name: Verify Python compilation
        run: >-
          python3 -m py_compile
          skills/company-os/mission-execution-control/scripts/mission_control.py
          skills/company-os/mission-execution-control/scripts/checkpoint_product.py
          skills/company-os/mission-execution-control/scripts/execution_regression_lab.py
          skills/company-os/govern-outcome-execution/scripts/executive_governor.py
          skills/company-os/direct-outcome/scripts/direct_outcome.py
          skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py
          skills/company-os/assemble-outcome-candidate/scripts/assemble_candidate.py
          skills/company-os/bootstrap-outcome/scripts/bootstrap_outcome.py
          skills/company-os/calibrate-outcome-stack/scripts/compile_calibration_fabric.py
          skills/company-os/elastic-company-os/scripts/company_os_controller.py
          skills/company-os/elastic-company-os/scripts/control_store.py
          skills/company-os/elastic-company-os/scripts/runtime_observations.py
          skills/company-os/elastic-company-os/scripts/operator_brief.py
          scripts/distribution.py
'''

REDUNDANT_REFERENCES = [
    "_end",
    ".keep",
    "actual-end.md",
    "authority-policy.md",
    "ci-policy.md",
    "concurrency.md",
    "director-integration.md",
    "failure-handling.md",
    "finalization.md",
    "implementation-status.md",
    "integration-policy.md",
    "migration-note.md",
    "mission-classes.md",
    "next.md",
    "no-document-spiral.md",
    "no-more-docs.md",
    "operating-modes.md",
    "operator-report.md",
    "reality-levels.md",
    "reality-spike.md",
    "security-boundary.md",
    "state-storage.md",
    "status.md",
    "stop.txt",
    "temporary.md",
    "testing-policy.md",
    "why-this-exists.md",
]


def remove(path: Path) -> None:
    if path.exists() or path.is_symlink():
        path.unlink()


def main() -> None:
    workflow_root = ROOT / ".github/workflows"
    for path in workflow_root.glob("*.yml"):
        if path.name not in {"ci.yml", "finalize-execution-enforcement-v2.yml"}:
            remove(path)
    (workflow_root / "ci.yml").write_text(PERMANENT_CI, encoding="utf-8")

    scripts = ROOT / "scripts"
    for pattern in (
        "apply_execution_enforcement_v2*.py",
        "repair_apply_execution_v2.py",
        "repair_phase*_and_apply.py",
        "patch_outcome_stack_verification.py",
    ):
        for path in scripts.glob(pattern):
            remove(path)

    reference_root = ROOT / "skills/company-os/mission-execution-control/references"
    for name in REDUNDANT_REFERENCES:
        remove(reference_root / name)

    remove(workflow_root / "finalize-execution-enforcement-v2.yml")
    remove(Path(__file__))
    print("execution enforcement v2 permanent tree prepared")


if __name__ == "__main__":
    main()
