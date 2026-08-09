#!/usr/bin/env python3
"""Portable outcome control validation for Company OS execution and acceptance."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

BINDING_SCHEMA = "company-os.outcome-control-binding.v1"
STATE_SCHEMA = "company-os.outcome-control-state.v1"
OUTCOME_SCHEMA = "company-os.outcome-contract.v1"
ARTIFACT_SCHEMA = "company-os.artifact-observation-contract.v1"
EVALUATOR_SCHEMA = "company-os.evaluator-runtime-contract.v1"
BENCHMARK_SCHEMA = "company-os.benchmark-contract.v1"
CALIBRATION_SCHEMA = "company-os.evaluator-calibration-receipt.v1"
AUTHORIZATION_SCHEMA = "company-os.outcome-scale-authorization.v1"
REALITY_SCHEMA = "company-os.reality-acceptance-receipt.v1"

LANES = {"pilot", "production_scale"}
LEGACY_PILOT_CAPS = {
    "max_managers": 2,
    "max_workers_per_manager": 3,
    "max_total_workers": 6,
    "max_manager_concurrency": 2,
}

_CALIBRATION_MODULE: Any | None = None


def calibration_module() -> Any:
    global _CALIBRATION_MODULE
    if _CALIBRATION_MODULE is not None:
        return _CALIBRATION_MODULE
    module_path = (
        Path(__file__).resolve().parents[2]
        / "calibrate-outcome-evaluator"
        / "scripts"
        / "calibrate_evaluator.py"
    )
    spec = importlib.util.spec_from_file_location(
        "company_os_calibrate_outcome_evaluator",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise OutcomeControlError(
            "E_RUNTIME",
            "calibration runtime cannot be loaded",
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _CALIBRATION_MODULE = module
    return module


class OutcomeControlError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise OutcomeControlError("E_CANONICAL", f"value is not canonical JSON: {exc}") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OutcomeControlError("E_JSON", f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise OutcomeControlError("E_JSON", f"non finite JSON value is forbidden: {value}")


def read_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object,
            parse_constant=_reject_constant,
        )
    except OutcomeControlError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OutcomeControlError("E_JSON", f"invalid JSON artifact: {path}") from exc


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OutcomeControlError("E_SCHEMA", f"{label} must be a nonempty string")
    return value


def _sha256(value: Any, label: str) -> str:
    text = _text(value, label)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise OutcomeControlError("E_SCHEMA", f"{label} must be a lowercase sha256")
    return text


def _object_value(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OutcomeControlError("E_SCHEMA", f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise OutcomeControlError("E_SCHEMA", f"{label} must be an array")
    return value


def _safe_file(project_root: Path, value: Any, label: str) -> tuple[Path, str]:
    raw = _text(value, label)
    if "\\" in raw:
        raise OutcomeControlError("E_PATH", f"{label} must use slash separated project paths")
    relative = Path(raw)
    if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise OutcomeControlError("E_PATH", f"{label} must be a safe project relative path")
    root = project_root.resolve()
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise OutcomeControlError("E_PATH", f"{label} may not traverse a symlink")
    try:
        resolved = (root / relative).resolve(strict=True)
    except OSError as exc:
        raise OutcomeControlError("E_PATH", f"{label} does not resolve to a file") from exc
    if root != resolved and root not in resolved.parents:
        raise OutcomeControlError("E_PATH", f"{label} escapes the project root")
    if not resolved.is_file() or resolved.is_symlink():
        raise OutcomeControlError("E_PATH", f"{label} must reference a regular file")
    return resolved, relative.as_posix()


def _verify_self_digest(value: Mapping[str, Any], field: str, label: str) -> str:
    observed = _sha256(value.get(field), f"{label}.{field}")
    candidate = dict(value)
    candidate[field] = None
    expected = digest(candidate)
    if observed != expected:
        raise OutcomeControlError("E_DIGEST", f"{label}.{field} does not match exact content")
    return observed


def _require_schema(value: Mapping[str, Any], schema: str, label: str) -> None:
    if value.get("$schema") != schema:
        raise OutcomeControlError("E_SCHEMA", f"{label} must use {schema}")


def _load_contract(
    project_root: Path,
    binding: Mapping[str, Any],
    path_field: str,
    schema: str,
    digest_field: str,
    label: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    path, relative = _safe_file(project_root, binding.get(path_field), path_field)
    raw = read_json(path)
    value = dict(_object_value(raw, label))
    _require_schema(value, schema, label)
    self_digest = _verify_self_digest(value, digest_field, label)
    return value, {
        "path": relative,
        "file_sha256": file_digest(path),
        digest_field: self_digest,
    }


def _capacity_value(manifest: Mapping[str, Any], field: str, default: int | None = None) -> int:
    value = manifest.get(field, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise OutcomeControlError("E_CAPACITY", f"manifest {field} must be a positive integer")
    return value


def _validate_pilot_capacity(manifest: Mapping[str, Any]) -> None:
    for field in ("max_managers", "max_workers_per_manager", "max_total_workers"):
        value = _capacity_value(manifest, field)
        if value > LEGACY_PILOT_CAPS[field]:
            raise OutcomeControlError(
                "E_PILOT_SCALE",
                f"pilot {field} exceeds the bounded ceiling of {LEGACY_PILOT_CAPS[field]}",
            )
    managers = manifest.get("managers")
    if not isinstance(managers, list) or not managers:
        raise OutcomeControlError("E_PILOT_SCALE", "pilot manifest requires managers")
    derived_concurrency = len(managers)
    manager_concurrency = _capacity_value(
        manifest,
        "max_manager_concurrency",
        derived_concurrency,
    )
    if manager_concurrency > LEGACY_PILOT_CAPS["max_manager_concurrency"]:
        raise OutcomeControlError(
            "E_PILOT_SCALE",
            "pilot max_manager_concurrency exceeds the bounded ceiling of 2",
        )
    if len(managers) > LEGACY_PILOT_CAPS["max_managers"]:
        raise OutcomeControlError("E_PILOT_SCALE", "pilot manager count exceeds 2")
    total_workers = 0
    for manager in managers:
        if not isinstance(manager, Mapping):
            raise OutcomeControlError("E_PILOT_SCALE", "pilot manager must be an object")
        workers = manager.get("workers")
        if not isinstance(workers, list):
            raise OutcomeControlError("E_PILOT_SCALE", "pilot manager workers must be an array")
        if len(workers) > LEGACY_PILOT_CAPS["max_workers_per_manager"]:
            raise OutcomeControlError("E_PILOT_SCALE", "pilot workers per manager exceed 3")
        total_workers += len(workers)
    if total_workers > LEGACY_PILOT_CAPS["max_total_workers"]:
        raise OutcomeControlError("E_PILOT_SCALE", "pilot total workers exceed 6")


def _validate_calibrations(
    project_root: Path,
    value: Any,
    objective_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    receipts: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    seen: set[str] = set()
    runtime = calibration_module()
    for index, raw in enumerate(_array(value, "calibration receipts")):
        receipt = dict(_object_value(raw, f"calibration[{index}]"))
        _require_schema(receipt, CALIBRATION_SCHEMA, f"calibration[{index}]")
        try:
            verified = runtime.verify_receipt(project_root, receipt)
        except Exception as exc:
            code = getattr(exc, "code", "E_CALIBRATION")
            raise OutcomeControlError(
                code,
                f"calibration[{index}] failed execution verification: {exc}",
            ) from exc
        evaluator_id = _text(
            verified.get("evaluator_id"),
            f"calibration[{index}].evaluator_id",
        )
        if evaluator_id in seen:
            raise OutcomeControlError(
                "E_DUPLICATE",
                f"duplicate calibration for {evaluator_id}",
            )
        seen.add(evaluator_id)
        if verified.get("objective_id") != objective_id:
            raise OutcomeControlError(
                "E_BINDING",
                f"calibration objective does not match outcome control: {evaluator_id}",
            )
        if verified.get("execution_bound") is not True:
            raise OutcomeControlError(
                "E_CALIBRATION",
                f"calibration is not execution bound: {evaluator_id}",
            )
        if verified.get("passed") is not True:
            raise OutcomeControlError(
                "E_CALIBRATION",
                f"calibration failed for {evaluator_id}",
            )
        receipt_digest = _sha256(
            verified.get("receipt_sha256"),
            f"calibration[{index}].receipt_sha256",
        )
        candidate_count = verified.get("candidate_count")
        if (
            not isinstance(candidate_count, int)
            or isinstance(candidate_count, bool)
            or candidate_count < 3
        ):
            raise OutcomeControlError(
                "E_CALIBRATION",
                f"calibration candidate count is invalid: {evaluator_id}",
            )
        receipts.append(receipt)
        bindings.append(
            {
                "evaluator_id": evaluator_id,
                "receipt_sha256": receipt_digest,
                "execution_bound": True,
                "candidate_count": candidate_count,
            }
        )
    receipts.sort(key=lambda item: str(item.get("evaluator_id", "")))
    bindings.sort(key=lambda item: str(item["evaluator_id"]))
    return receipts, bindings

def validate_manifest_binding(
    *,
    project_root: Path,
    manifest: Mapping[str, Any],
    project_id: str,
    program_version: int,
    work_id: str,
    governed_outcome: str,
) -> dict[str, Any]:
    binding = dict(_object_value(manifest.get("outcome_control"), "manifest.outcome_control"))
    allowed = {
        "$schema",
        "execution_lane",
        "project_id",
        "program_version",
        "work_id",
        "governed_outcome",
        "objective_id",
        "outcome_contract_path",
        "artifact_contract_path",
        "evaluator_contract_path",
        "benchmark_contract_path",
        "calibration_receipts_path",
        "scale_authorization_path",
    }
    extra = sorted(set(binding) - allowed)
    if extra:
        raise OutcomeControlError("E_SCHEMA", f"unknown outcome control fields: {', '.join(extra)}")
    if binding.get("$schema") != BINDING_SCHEMA:
        raise OutcomeControlError("E_SCHEMA", f"manifest.outcome_control must use {BINDING_SCHEMA}")
    lane = binding.get("execution_lane")
    if lane not in LANES:
        raise OutcomeControlError("E_SCHEMA", "execution_lane must be pilot or production_scale")
    if binding.get("project_id") != project_id:
        raise OutcomeControlError("E_BINDING", "outcome control project_id does not match the project")
    if binding.get("program_version") != program_version:
        raise OutcomeControlError("E_BINDING", "outcome control belongs to a stale program")
    if binding.get("work_id") != work_id:
        raise OutcomeControlError("E_BINDING", "outcome control work_id does not match governed work")
    if binding.get("governed_outcome") != governed_outcome or manifest.get("outcome") != governed_outcome:
        raise OutcomeControlError("E_BINDING", "outcome control does not bind the governed work outcome")
    objective_id = _text(binding.get("objective_id"), "outcome_control.objective_id")

    outcome, outcome_binding = _load_contract(
        project_root,
        binding,
        "outcome_contract_path",
        OUTCOME_SCHEMA,
        "contract_sha256",
        "outcome contract",
    )
    artifacts, artifact_binding = _load_contract(
        project_root,
        binding,
        "artifact_contract_path",
        ARTIFACT_SCHEMA,
        "contract_sha256",
        "artifact contract",
    )
    evaluators, evaluator_binding = _load_contract(
        project_root,
        binding,
        "evaluator_contract_path",
        EVALUATOR_SCHEMA,
        "contract_sha256",
        "evaluator contract",
    )
    benchmarks, benchmark_binding = _load_contract(
        project_root,
        binding,
        "benchmark_contract_path",
        BENCHMARK_SCHEMA,
        "contract_sha256",
        "benchmark contract",
    )

    contracts = {
        "outcome": outcome,
        "artifacts": artifacts,
        "evaluators": evaluators,
        "benchmarks": benchmarks,
    }
    for label, contract in contracts.items():
        if contract.get("objective_id") != objective_id:
            raise OutcomeControlError("E_BINDING", f"{label} objective_id does not match outcome control")
    original_objective = _text(outcome.get("original_objective"), "outcome.original_objective")
    if outcome.get("pilot_allowed") is not True:
        raise OutcomeControlError("E_OUTCOME", "outcome contract does not permit a bounded pilot")
    if artifacts.get("ready") is not True:
        raise OutcomeControlError("E_ARTIFACT", "artifact observation contract is not ready")
    if evaluators.get("ready") is not True:
        raise OutcomeControlError("E_EVALUATOR", "evaluator runtime contract is not ready")
    if benchmarks.get("ready") is not True:
        raise OutcomeControlError("E_BENCHMARK", "benchmark contract is not ready")

    calibration_path, calibration_relative = _safe_file(
        project_root,
        binding.get("calibration_receipts_path"),
        "calibration_receipts_path",
    )
    calibrations, calibration_bindings = _validate_calibrations(
        project_root,
        read_json(calibration_path),
        objective_id,
    )
    calibration_binding = {
        "path": calibration_relative,
        "file_sha256": file_digest(calibration_path),
        "receipts_sha256": digest(calibrations),
    }

    scale_binding: dict[str, str | None]
    if lane == "pilot":
        _validate_pilot_capacity(manifest)
        scale_path_value = binding.get("scale_authorization_path")
        if scale_path_value not in {None, ""}:
            raise OutcomeControlError(
                "E_AUTHORITY",
                "pilot outcome control must not present scale authorization as pilot authority",
            )
        scale_binding = {"path": None, "file_sha256": None, "authorization_sha256": None}
    else:
        if outcome.get("scale_allowed") is not True:
            raise OutcomeControlError("E_OUTCOME", "outcome contract does not permit production scale")
        scale, scale_binding_raw = _load_contract(
            project_root,
            binding,
            "scale_authorization_path",
            AUTHORIZATION_SCHEMA,
            "authorization_sha256",
            "scale authorization",
        )
        if scale.get("objective_id") != objective_id:
            raise OutcomeControlError("E_BINDING", "scale authorization objective_id does not match")
        if scale.get("authorized") is not True or scale.get("blockers") not in ([], None):
            raise OutcomeControlError("E_AUTHORITY", "production scale is not outcome authorized")
        input_bindings = _object_value(scale.get("input_bindings"), "scale authorization input_bindings")
        expected_inputs = {
            "outcome_sha256": digest(outcome),
            "artifacts_sha256": digest(artifacts),
            "evaluators_sha256": digest(evaluators),
            "benchmarks_sha256": digest(benchmarks),
            "calibrations_sha256": digest(calibrations),
        }
        if dict(input_bindings) != expected_inputs:
            raise OutcomeControlError("E_BINDING", "scale authorization does not bind the current contracts")
        required_evaluators = {
            _text(item.get("evaluator_id"), "required evaluator id")
            for item in _array(evaluators.get("evaluators"), "evaluators.evaluators")
            if isinstance(item, Mapping) and item.get("required") is True
        }
        calibrated = {item["evaluator_id"] for item in calibration_bindings}
        if not required_evaluators.issubset(calibrated):
            missing = ", ".join(sorted(required_evaluators - calibrated))
            raise OutcomeControlError("E_CALIBRATION", f"required evaluators are uncalibrated: {missing}")
        scale_binding = {
            "path": scale_binding_raw["path"],
            "file_sha256": scale_binding_raw["file_sha256"],
            "authorization_sha256": scale_binding_raw["authorization_sha256"],
        }

    result: dict[str, Any] = {
        "$schema": STATE_SCHEMA,
        "schema_version": 1,
        "execution_lane": lane,
        "project_id": project_id,
        "program_version": program_version,
        "work_id": work_id,
        "governed_outcome": governed_outcome,
        "objective_id": objective_id,
        "original_objective": original_objective,
        "outcome": outcome_binding,
        "artifacts": artifact_binding,
        "evaluators": evaluator_binding,
        "benchmarks": benchmark_binding,
        "calibrations": calibration_binding,
        "calibration_receipts": calibration_bindings,
        "scale_authorization": scale_binding,
    }
    result["state_sha256"] = digest({**result, "state_sha256": None})
    return result


def validate_reality_receipt(
    receipt: Mapping[str, Any],
    outcome_control: Mapping[str, Any],
) -> dict[str, Any]:
    value = dict(receipt)
    _require_schema(value, REALITY_SCHEMA, "reality acceptance receipt")
    receipt_sha256 = _verify_self_digest(value, "receipt_sha256", "reality acceptance receipt")
    if value.get("accepted") is not True:
        raise OutcomeControlError("E_REALITY", "reality acceptance did not accept the outcome")
    if value.get("blockers") not in ([], None):
        raise OutcomeControlError("E_REALITY", "reality acceptance retains blockers")
    if value.get("objective_id") != outcome_control.get("objective_id"):
        raise OutcomeControlError("E_BINDING", "reality acceptance objective_id does not match")
    original = _text(value.get("original_objective"), "reality original_objective")
    if original != outcome_control.get("original_objective"):
        raise OutcomeControlError("E_BINDING", "reality acceptance does not bind the original objective")
    if value.get("original_objective_sha256") != hashlib.sha256(original.encode("utf-8")).hexdigest():
        raise OutcomeControlError("E_DIGEST", "reality original objective digest does not match")
    decisions = _array(value.get("claim_decisions"), "reality claim_decisions")
    if not decisions:
        raise OutcomeControlError("E_REALITY", "reality acceptance requires claim decisions")
    seen: set[str] = set()
    for index, raw in enumerate(decisions):
        decision = _object_value(raw, f"claim_decisions[{index}]")
        claim_id = _text(decision.get("claim_id"), f"claim_decisions[{index}].claim_id")
        if claim_id in seen:
            raise OutcomeControlError("E_DUPLICATE", f"duplicate reality claim decision: {claim_id}")
        seen.add(claim_id)
        required = decision.get("required")
        if not isinstance(required, bool):
            raise OutcomeControlError("E_SCHEMA", f"claim {claim_id}.required must be boolean")
        if required and decision.get("passed") is not True:
            raise OutcomeControlError("E_REALITY", f"required reality claim failed: {claim_id}")
        for field in ("artifact_evidence_count", "evaluator_receipt_count"):
            count = decision.get(field)
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise OutcomeControlError("E_SCHEMA", f"claim {claim_id}.{field} is invalid")
            if required and count < 1:
                raise OutcomeControlError("E_REALITY", f"required reality claim lacks {field}: {claim_id}")
    return {
        "objective_id": value["objective_id"],
        "receipt_sha256": receipt_sha256,
        "claim_count": len(decisions),
    }


def find_reality_receipt(
    *,
    project_root: Path,
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    evidence_ids: Sequence[str],
    outcome_control: Mapping[str, Any],
) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for evidence_id in sorted(set(evidence_ids)):
        record = evidence_by_id.get(evidence_id)
        if not isinstance(record, Mapping):
            continue
        path_value = record.get("snapshot_path") or record.get("artifact_path")
        try:
            path, _ = _safe_file(project_root, path_value, f"evidence {evidence_id} artifact")
            raw = read_json(path)
        except OutcomeControlError:
            continue
        if not isinstance(raw, Mapping) or raw.get("$schema") != REALITY_SCHEMA:
            continue
        validated = validate_reality_receipt(raw, outcome_control)
        matches.append({"evidence_id": evidence_id, **validated})
    if not matches:
        raise OutcomeControlError(
            "E_REALITY",
            "completed execution fabric work requires one accepted reality receipt in completion evidence",
        )
    if len(matches) != 1:
        raise OutcomeControlError(
            "E_REALITY",
            "completion evidence must contain exactly one accepted reality receipt",
        )
    return matches[0]
