#!/usr/bin/env python3
"""Join outcome understanding contracts into one deterministic scale authorization."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

OUTCOME_SCHEMA = "company-os.outcome-contract.v1"
ARTIFACT_SCHEMA = "company-os.artifact-observation-contract.v1"
EVALUATOR_SCHEMA = "company-os.evaluator-runtime-contract.v1"
BENCHMARK_SCHEMA = "company-os.benchmark-contract.v1"
CALIBRATION_SCHEMA = "company-os.evaluator-calibration-receipt.v1"
AUTH_SCHEMA = "company-os.outcome-scale-authorization.v1"


class ScaleAuthorizationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ScaleAuthorizationError("E_READ", f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ScaleAuthorizationError("E_JSON", f"invalid JSON at {path}: {exc}") from exc


def require_object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ScaleAuthorizationError("E_SCHEMA", f"{label} must be an object")
    return value


def require_schema(value: Mapping[str, Any], expected: str, label: str) -> None:
    if value.get("$schema") != expected:
        raise ScaleAuthorizationError(
            "E_SCHEMA", f"{label} $schema must equal {expected!r}"
        )


def objective_id(value: Mapping[str, Any], label: str) -> str:
    current = value.get("objective_id")
    if not isinstance(current, str) or not current.strip():
        raise ScaleAuthorizationError("E_SCHEMA", f"{label}.objective_id must be nonempty")
    return current


def string_set(value: Any, label: str) -> set[str]:
    if value is None:
        return set()
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ScaleAuthorizationError("E_SCHEMA", f"{label} must be an array of nonempty strings")
    if len(value) != len(set(value)):
        raise ScaleAuthorizationError("E_DUPLICATE", f"{label} contains duplicates")
    return set(value)


def authorize(
    outcome: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    evaluators: Mapping[str, Any],
    benchmarks: Mapping[str, Any],
    calibrations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    require_schema(outcome, OUTCOME_SCHEMA, "outcome")
    require_schema(artifacts, ARTIFACT_SCHEMA, "artifacts")
    require_schema(evaluators, EVALUATOR_SCHEMA, "evaluators")
    require_schema(benchmarks, BENCHMARK_SCHEMA, "benchmarks")

    expected_objective = objective_id(outcome, "outcome")
    bound_objectives = {
        "outcome": expected_objective,
        "artifacts": objective_id(artifacts, "artifacts"),
        "evaluators": objective_id(evaluators, "evaluators"),
        "benchmarks": objective_id(benchmarks, "benchmarks"),
    }
    mismatched = sorted(
        label for label, value in bound_objectives.items() if value != expected_objective
    )
    if mismatched:
        raise ScaleAuthorizationError(
            "E_OBJECTIVE_BINDING",
            f"objective mismatch in: {', '.join(mismatched)}",
        )

    blockers: list[dict[str, Any]] = []

    if outcome.get("scale_allowed") is not True:
        blockers.append({"code": "OUTCOME_NOT_SCALE_READY", "detail": "outcome"})
    if artifacts.get("ready") is not True:
        blockers.append({"code": "ARTIFACTS_NOT_READY", "detail": "artifacts"})
    if evaluators.get("ready") is not True:
        blockers.append({"code": "EVALUATORS_NOT_READY", "detail": "evaluators"})
    if benchmarks.get("ready") is not True:
        blockers.append({"code": "BENCHMARKS_NOT_READY", "detail": "benchmarks"})

    artifact_records = artifacts.get("artifact_classes")
    if not isinstance(artifact_records, list):
        raise ScaleAuthorizationError("E_SCHEMA", "artifact_classes must be an array")
    required_artifacts: set[str] = set()
    required_evidence_by_artifact: dict[str, set[str]] = {}
    for index, item in enumerate(artifact_records):
        if not isinstance(item, Mapping):
            raise ScaleAuthorizationError("E_SCHEMA", f"artifact_classes[{index}] must be an object")
        artifact_id = item.get("artifact_class_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ScaleAuthorizationError("E_SCHEMA", f"artifact_classes[{index}].artifact_class_id invalid")
        if item.get("required") is True:
            required_artifacts.add(artifact_id)
            required_evidence_by_artifact[artifact_id] = string_set(
                item.get("required_evidence", []),
                f"artifact {artifact_id}.required_evidence",
            )

    evaluator_records = evaluators.get("evaluators")
    if not isinstance(evaluator_records, list):
        raise ScaleAuthorizationError("E_SCHEMA", "evaluators.evaluators must be an array")
    required_evaluators: dict[str, set[str]] = {}
    artifact_coverage: set[str] = set()
    evidence_coverage_by_artifact: dict[str, set[str]] = {}
    for item in evaluator_records:
        if not isinstance(item, Mapping):
            raise ScaleAuthorizationError("E_SCHEMA", "evaluator record must be an object")
        evaluator_id = item.get("evaluator_id")
        if not isinstance(evaluator_id, str) or not evaluator_id:
            raise ScaleAuthorizationError("E_SCHEMA", "evaluator_id must be nonempty")
        covered = item.get("artifact_classes")
        if not isinstance(covered, list) or not all(isinstance(x, str) and x for x in covered):
            raise ScaleAuthorizationError("E_SCHEMA", f"{evaluator_id}.artifact_classes invalid")
        produces_evidence = string_set(
            item.get("produces_evidence", []),
            f"{evaluator_id}.produces_evidence",
        )
        if item.get("required") is True:
            required_evaluators[evaluator_id] = set(covered)
            artifact_coverage.update(covered)
            for artifact_id in covered:
                evidence_coverage_by_artifact.setdefault(artifact_id, set()).update(produces_evidence)

    uncovered = sorted(required_artifacts - artifact_coverage)
    for artifact_id in uncovered:
        blockers.append({"code": "ARTIFACT_WITHOUT_EVALUATOR", "detail": artifact_id})

    for artifact_id in sorted(required_artifacts):
        required_evidence = required_evidence_by_artifact.get(artifact_id, set())
        observed_coverage = evidence_coverage_by_artifact.get(artifact_id, set())
        missing_evidence = sorted(required_evidence - observed_coverage)
        if missing_evidence:
            blockers.append(
                {
                    "code": "ARTIFACT_OBSERVATION_EVIDENCE_UNCOVERED",
                    "detail": f"{artifact_id}:{','.join(missing_evidence)}",
                }
            )

    calibration_by_evaluator: dict[str, Mapping[str, Any]] = {}
    for receipt in calibrations:
        if not isinstance(receipt, Mapping):
            raise ScaleAuthorizationError("E_SCHEMA", "calibration receipt must be an object")
        require_schema(receipt, CALIBRATION_SCHEMA, "calibration")
        evaluator_id = receipt.get("evaluator_id")
        if not isinstance(evaluator_id, str) or not evaluator_id:
            raise ScaleAuthorizationError("E_SCHEMA", "calibration evaluator_id invalid")
        if evaluator_id in calibration_by_evaluator:
            raise ScaleAuthorizationError(
                "E_DUPLICATE", f"duplicate calibration receipt for {evaluator_id}"
            )
        calibration_by_evaluator[evaluator_id] = receipt

    for evaluator_id in sorted(required_evaluators):
        receipt = calibration_by_evaluator.get(evaluator_id)
        if receipt is None:
            blockers.append({"code": "EVALUATOR_UNCALIBRATED", "detail": evaluator_id})
        elif receipt.get("passed") is not True:
            blockers.append({"code": "EVALUATOR_CALIBRATION_FAILED", "detail": evaluator_id})

    blockers = sorted(blockers, key=lambda item: (item["code"], item["detail"]))
    authorized = not blockers

    result: dict[str, Any] = {
        "$schema": AUTH_SCHEMA,
        "schema_version": 1,
        "objective_id": expected_objective,
        "authorized": authorized,
        "blockers": blockers,
        "required_artifact_classes": sorted(required_artifacts),
        "required_evaluator_ids": sorted(required_evaluators),
        "required_observation_evidence": {
            artifact_id: sorted(required_evidence_by_artifact.get(artifact_id, set()))
            for artifact_id in sorted(required_artifacts)
        },
        "input_bindings": {
            "outcome_sha256": digest(outcome),
            "artifacts_sha256": digest(artifacts),
            "evaluators_sha256": digest(evaluators),
            "benchmarks_sha256": digest(benchmarks),
            "calibrations_sha256": digest(
                sorted(
                    [dict(item) for item in calibrations],
                    key=lambda item: str(item.get("evaluator_id", "")),
                )
            ),
        },
    }
    result["authorization_sha256"] = digest(
        {**result, "authorization_sha256": None}
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    authorize_parser = sub.add_parser("authorize")
    authorize_parser.add_argument("--outcome", required=True, type=Path)
    authorize_parser.add_argument("--artifacts", required=True, type=Path)
    authorize_parser.add_argument("--evaluators", required=True, type=Path)
    authorize_parser.add_argument("--benchmarks", required=True, type=Path)
    authorize_parser.add_argument("--calibrations", required=True, type=Path)
    authorize_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    calibrations_raw = read_json(args.calibrations)
    if not isinstance(calibrations_raw, list):
        raise ScaleAuthorizationError("E_SCHEMA", "calibrations file must be an array")
    receipt = authorize(
        require_object(read_json(args.outcome), "outcome"),
        require_object(read_json(args.artifacts), "artifacts"),
        require_object(read_json(args.evaluators), "evaluators"),
        require_object(read_json(args.benchmarks), "benchmarks"),
        calibrations_raw,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"outcome scale authorized={receipt['authorized']} "
        f"blockers={len(receipt['blockers'])}"
    )


if __name__ == "__main__":
    main()
