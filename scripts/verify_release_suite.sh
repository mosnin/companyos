#!/usr/bin/env bash
set -euo pipefail

release_tag="${1:?usage: verify_release_suite.sh vX.Y.Z [--publish]}"
publish_mode="${2:-}"

npm test
npm run test:package
if [[ "$publish_mode" == "--publish" ]]; then
  npm run test:release -- --tag "$release_tag" --publish
elif [[ -n "$publish_mode" ]]; then
  printf 'unknown release-suite option: %s\n' "$publish_mode" >&2
  exit 2
else
  npm run test:release -- --tag "$release_tag"
fi

python3 scripts/distribution.py verify-manifest
python3 -m unittest discover -s tests -v
python3 skills/company-os/mission-execution-control/scripts/execution_regression_lab.py --json
python3 skills/company-os/goal-route-system/scripts/goal_route.py simulate
python3 scripts/verify_operator_command_center_surface.py
python3 skills/company-os/elastic-company-os/scripts/test_company_os_controller.py
python3 skills/company-os/elastic-company-os/scripts/test_control_store.py -v
python3 skills/company-os/elastic-company-os/scripts/test_runtime_observation_integration.py RuntimeObservationIntegrationTests
python3 skills/company-os/elastic-company-os/scripts/test_operator_brief.py -v
python3 -m unittest discover -s programs/company-os-self-hosting/reference -v
python3 skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_fabric.py --self-test
python3 skills/company-os/company-blueprint/scripts/assert_chippi_north_star.py --self-test
python3 -m py_compile \
  skills/company-os/company-blueprint/scripts/assert_chippi_north_star.py \
  skills/company-os/navigation-control/scripts/navigation_control.py \
  skills/company-os/goal-route-system/scripts/goal_route.py \
  skills/company-os/mission-execution-control/scripts/mission_control.py \
  skills/company-os/mission-execution-control/scripts/checkpoint_product.py \
  skills/company-os/mission-execution-control/scripts/execution_regression_lab.py \
  skills/company-os/govern-outcome-execution/scripts/executive_governor.py \
  skills/company-os/direct-outcome/scripts/direct_outcome.py \
  skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py \
  skills/company-os/assemble-outcome-candidate/scripts/assemble_candidate.py \
  skills/company-os/bootstrap-outcome/scripts/bootstrap_outcome.py \
  skills/company-os/calibrate-outcome-stack/scripts/compile_calibration_fabric.py \
  skills/company-os/elastic-company-os/scripts/company_os_controller.py \
  skills/company-os/elastic-company-os/scripts/control_store.py \
  skills/company-os/elastic-company-os/scripts/runtime_observations.py \
  skills/company-os/elastic-company-os/scripts/operator_brief.py \
  scripts/distribution.py
