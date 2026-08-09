#!/usr/bin/env python3
"""Calibrate an outcome evaluator from verified execution receipts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

REQUEST_SCHEMA = "company-os.evaluator-calibration.v2"
RECEIPT_SCHEMA = "company-os.evaluator-calibration-receipt.v1"


class CalibrationError(ValueError):
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
        raise CalibrationError("E_CANONICAL", f"value is not canonical JSON: {exc}") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _reject_constant(value: str) -> None:
    raise CalibrationError("E_JSON", f"non finite JSON value is forbidden: {value}")


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CalibrationError("E_JSON", f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object,
            parse_constant=_reject_constant,
        )
    except CalibrationError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CalibrationError("E_JSON", f"invalid JSON in {label}: {path}") from exc


def require_object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CalibrationError("E_SCHEMA", f"{label} must be an object")
    return value


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise CalibrationError("E_SCHEMA", f"{label} must be a nonempty string")
    return value


def require_sha256(value: Any, label: str) -> str:
    text = require_text(value, label)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise CalibrationError("E_SCHEMA", f"{label} must be a lowercase sha256")
    return text


def require_dimensions(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise CalibrationError("E_SCHEMA", "required_dimensions must be a nonempty array")
    result = [require_text(item, "required_dimensions[]") for item in value]
    if len(result) != len(set(result)):
        raise CalibrationError("E_DUPLICATE", "required_dimensions contains duplicates")
    return sorted(result)


def safe_file(project_root: Path, value: Any, label: str) -> tuple[Path, str]:
    raw = require_text(value, label)
    if "\\" in raw:
        raise CalibrationError("E_PATH", f"{label} must use slash separated paths")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise CalibrationError("E_PATH", f"{label} must be a safe project relative path")
    root = project_root.resolve()
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise CalibrationError("E_PATH", f"{label} may not traverse a symlink")
    try:
        resolved = (root / Path(*pure.parts)).resolve(strict=True)
    except OSError as exc:
        raise CalibrationError("E_PATH", f"{label} does not resolve to a file") from exc
    if resolved != root and root not in resolved.parents:
        raise CalibrationError("E_PATH", f"{label} escapes the project root")
    if not resolved.is_file() or resolved.is_symlink():
        raise CalibrationError("E_PATH", f"{label} must reference a regular file")
    return resolved, pure.as_posix()


def runtime_module() -> Any:
    path = (
        Path(__file__).resolve().parents[2]
        / "execute-outcome-evaluator"
        / "scripts"
        / "execute_evaluator.py"
    )
    spec = importlib.util.spec_from_file_location("company_os_execute_outcome_evaluator", path)
    if spec is None or spec.loader is None:
        raise CalibrationError("E_RUNTIME", "evaluator execution runtime cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_self_digest(value: Mapping[str, Any], field: str, label: str) -> str:
    observed = require_sha256(value.get(field), f"{label}.{field}")
    candidate = dict(value)
    candidate[field] = None
    if digest(candidate) != observed:
        raise CalibrationError("E_DIGEST", f"{label}.{field} does not match exact content")
    return observed


def clean_scores(value: Any, dimensions: list[str], label: str) -> dict[str, float]:
    scores = require_object(value, label)
    if set(scores) != set(dimensions):
        raise CalibrationError(
            "E_SCORE",
            f"{label} dimensions are invalid; expected={dimensions} observed={sorted(scores)}",
        )
    result: dict[str, float] = {}
    for dimension in dimensions:
        score = scores.get(dimension)
        if (
            not isinstance(score, (int, float))
            or isinstance(score, bool)
            or not math.isfinite(float(score))
            or float(score) < 0.0
            or float(score) > 10.0
        ):
            raise CalibrationError("E_SCORE", f"{label}.{dimension} is invalid")
        result[dimension] = float(score)
    return result


def pairwise_failures(candidates: list[dict[str, Any]], dimensions: list[str]) -> list[dict[str, Any]]:
    by_rank = sorted(candidates, key=lambda item: item["expected_rank"])
    failures: list[dict[str, Any]] = []
    for dimension in dimensions:
        for lower, higher in zip(by_rank, by_rank[1:]):
            lower_score = lower["scores"][dimension]
            higher_score = higher["scores"][dimension]
            if not lower_score < higher_score:
                failures.append(
                    {
                        "dimension": dimension,
                        "lower_candidate": lower["candidate_id"],
                        "higher_candidate": higher["candidate_id"],
                        "lower_score": lower_score,
                        "higher_score": higher_score,
                    }
                )
    return sorted(
        failures,
        key=lambda item: (
            item["dimension"],
            item["lower_candidate"],
            item["higher_candidate"],
        ),
    )


def _source_identity(receipt: Mapping[str, Any]) -> dict[str, Any]:
    sources = require_object(receipt.get("source_bindings"), "execution receipt source_bindings")
    return {
        key: dict(require_object(sources.get(key), f"source_bindings.{key}"))
        for key in (
            "evaluator_contract",
            "benchmark_contract",
            "adapter_registry",
            "adapter_entrypoint",
        )
    }


def calibrate(project_root: Path, request: Mapping[str, Any]) -> dict[str, Any]:
    project_root = project_root.resolve()
    if not project_root.is_dir() or project_root.is_symlink():
        raise CalibrationError("E_PATH", "project_root must be a real directory")
    expected_keys = {
        "$schema",
        "objective_id",
        "evaluator_id",
        "required_dimensions",
        "candidates",
    }
    if set(request) != expected_keys:
        raise CalibrationError("E_SCHEMA", "calibration request keys are invalid")
    if request.get("$schema") != REQUEST_SCHEMA:
        raise CalibrationError("E_SCHEMA", f"calibration request must use {REQUEST_SCHEMA}")
    objective_id = require_text(request.get("objective_id"), "objective_id")
    evaluator_id = require_text(request.get("evaluator_id"), "evaluator_id")
    dimensions = require_dimensions(request.get("required_dimensions"))
    raw_candidates = request.get("candidates")
    if not isinstance(raw_candidates, list) or len(raw_candidates) < 3:
        raise CalibrationError("E_SCHEMA", "at least three calibration candidates are required")

    runtime = runtime_module()
    candidates: list[dict[str, Any]] = []
    candidate_ids: set[str] = set()
    receipt_digests: set[str] = set()
    artifact_sets: set[str] = set()
    expected_source_identity: dict[str, Any] | None = None
    for index, raw in enumerate(raw_candidates):
        item = require_object(raw, f"candidates[{index}]")
        if set(item) != {"candidate_id", "expected_rank", "execution_receipt_path"}:
            raise CalibrationError("E_SCHEMA", f"candidates[{index}] keys are invalid")
        candidate_id = require_text(item.get("candidate_id"), f"candidates[{index}].candidate_id")
        if candidate_id in candidate_ids:
            raise CalibrationError("E_DUPLICATE", f"duplicate candidate_id {candidate_id}")
        candidate_ids.add(candidate_id)
        expected_rank = item.get("expected_rank")
        if not isinstance(expected_rank, int) or isinstance(expected_rank, bool) or expected_rank < 1:
            raise CalibrationError("E_SCHEMA", f"{candidate_id}.expected_rank is invalid")
        receipt_path, relative = safe_file(
            project_root,
            item.get("execution_receipt_path"),
            f"{candidate_id}.execution_receipt_path",
        )
        receipt = dict(require_object(read_json(receipt_path, f"{candidate_id} execution receipt"), "execution receipt"))
        try:
            verified = runtime.verify_receipt(project_root, receipt)
        except Exception as exc:
            code = getattr(exc, "code", "E_EXECUTION")
            raise CalibrationError(code, f"{candidate_id} execution receipt is invalid: {exc}") from exc
        if verified.get("objective_id") != objective_id:
            raise CalibrationError("E_BINDING", f"{candidate_id} objective_id does not match")
        if verified.get("evaluator_id") != evaluator_id:
            raise CalibrationError("E_BINDING", f"{candidate_id} evaluator_id does not match")
        receipt_sha256 = require_sha256(
            verified.get("receipt_sha256"),
            f"{candidate_id}.receipt_sha256",
        )
        if receipt_sha256 in receipt_digests:
            raise CalibrationError("E_DUPLICATE", "calibration candidates cannot reuse an execution receipt")
        receipt_digests.add(receipt_sha256)
        artifact_bindings = receipt.get("artifact_bindings")
        if not isinstance(artifact_bindings, list) or not artifact_bindings:
            raise CalibrationError("E_EXECUTION", f"{candidate_id} has no artifact bindings")
        artifact_set_sha256 = runtime.digest(artifact_bindings)
        if artifact_set_sha256 in artifact_sets:
            raise CalibrationError("E_DUPLICATE", "calibration candidates must use distinct artifact sets")
        artifact_sets.add(artifact_set_sha256)
        source_identity = _source_identity(receipt)
        if expected_source_identity is None:
            expected_source_identity = source_identity
        elif source_identity != expected_source_identity:
            raise CalibrationError(
                "E_BINDING",
                "all calibration candidates must use the same evaluator, benchmark, registry, and adapter bytes",
            )
        scores = clean_scores(receipt.get("scores"), dimensions, f"{candidate_id}.scores")
        candidates.append(
            {
                "candidate_id": candidate_id,
                "expected_rank": expected_rank,
                "execution_receipt_path": relative,
                "execution_receipt_file_sha256": file_digest(receipt_path),
                "execution_receipt_sha256": receipt_sha256,
                "artifact_set_sha256": artifact_set_sha256,
                "scores": scores,
            }
        )

    ranks = [item["expected_rank"] for item in candidates]
    if len(ranks) != len(set(ranks)) or sorted(ranks) != list(range(1, len(ranks) + 1)):
        raise CalibrationError("E_SCHEMA", "expected ranks must be unique and contiguous")
    candidates.sort(key=lambda item: item["expected_rank"])
    failures = pairwise_failures(candidates, dimensions)
    source_identity = expected_source_identity or {}
    output: dict[str, Any] = {
        "$schema": RECEIPT_SCHEMA,
        "schema_version": 2,
        "objective_id": objective_id,
        "evaluator_id": evaluator_id,
        "execution_bound": True,
        "candidate_count": len(candidates),
        "required_dimensions": dimensions,
        "source_bindings": source_identity,
        "source_bindings_sha256": digest(source_identity),
        "candidates": candidates,
        "pairwise_failures": failures,
        "passed": not failures,
    }
    output["receipt_sha256"] = digest({**output, "receipt_sha256": None})
    return output


def verify_receipt(project_root: Path, receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("$schema") != RECEIPT_SCHEMA:
        raise CalibrationError("E_SCHEMA", f"calibration receipt must use {RECEIPT_SCHEMA}")
    if receipt.get("schema_version") != 2 or receipt.get("execution_bound") is not True:
        raise CalibrationError("E_CALIBRATION", "calibration receipt is not execution bound")
    receipt_sha256 = verify_self_digest(receipt, "receipt_sha256", "calibration receipt")
    objective_id = require_text(receipt.get("objective_id"), "objective_id")
    evaluator_id = require_text(receipt.get("evaluator_id"), "evaluator_id")
    dimensions = require_dimensions(receipt.get("required_dimensions"))
    source_bindings = dict(require_object(receipt.get("source_bindings"), "source_bindings"))
    if receipt.get("source_bindings_sha256") != digest(source_bindings):
        raise CalibrationError("E_DIGEST", "source_bindings_sha256 does not match")
    raw_candidates = receipt.get("candidates")
    if not isinstance(raw_candidates, list) or len(raw_candidates) < 3:
        raise CalibrationError("E_CALIBRATION", "calibration receipt requires three candidates")
    runtime = runtime_module()
    candidates: list[dict[str, Any]] = []
    receipt_digests: set[str] = set()
    artifact_sets: set[str] = set()
    candidate_ids: set[str] = set()
    for index, raw in enumerate(raw_candidates):
        item = dict(require_object(raw, f"candidates[{index}]"))
        candidate_id = require_text(item.get("candidate_id"), f"candidates[{index}].candidate_id")
        if candidate_id in candidate_ids:
            raise CalibrationError("E_DUPLICATE", f"duplicate candidate_id {candidate_id}")
        candidate_ids.add(candidate_id)
        rank = item.get("expected_rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
            raise CalibrationError("E_SCHEMA", f"{candidate_id}.expected_rank is invalid")
        path, relative = safe_file(
            project_root,
            item.get("execution_receipt_path"),
            f"{candidate_id}.execution_receipt_path",
        )
        if relative != item.get("execution_receipt_path"):
            raise CalibrationError("E_PATH", f"{candidate_id} receipt path is not canonical")
        if file_digest(path) != require_sha256(
            item.get("execution_receipt_file_sha256"),
            f"{candidate_id}.execution_receipt_file_sha256",
        ):
            raise CalibrationError("E_DIGEST", f"{candidate_id} execution receipt file drifted")
        execution = dict(require_object(read_json(path, f"{candidate_id} execution receipt"), "execution receipt"))
        try:
            verified = runtime.verify_receipt(project_root, execution)
        except Exception as exc:
            code = getattr(exc, "code", "E_EXECUTION")
            raise CalibrationError(code, f"{candidate_id} execution receipt is invalid: {exc}") from exc
        observed_receipt = require_sha256(verified.get("receipt_sha256"), f"{candidate_id}.receipt_sha256")
        if observed_receipt != item.get("execution_receipt_sha256"):
            raise CalibrationError("E_DIGEST", f"{candidate_id} execution receipt digest drifted")
        if observed_receipt in receipt_digests:
            raise CalibrationError("E_DUPLICATE", "execution receipt is reused")
        receipt_digests.add(observed_receipt)
        if verified.get("objective_id") != objective_id or verified.get("evaluator_id") != evaluator_id:
            raise CalibrationError("E_BINDING", f"{candidate_id} execution identity drifted")
        artifact_set_sha256 = runtime.digest(execution.get("artifact_bindings"))
        if artifact_set_sha256 != item.get("artifact_set_sha256"):
            raise CalibrationError("E_DIGEST", f"{candidate_id} artifact set drifted")
        if artifact_set_sha256 in artifact_sets:
            raise CalibrationError("E_DUPLICATE", "artifact set is reused")
        artifact_sets.add(artifact_set_sha256)
        if _source_identity(execution) != source_bindings:
            raise CalibrationError("E_BINDING", f"{candidate_id} source bindings drifted")
        scores = clean_scores(execution.get("scores"), dimensions, f"{candidate_id}.scores")
        if scores != item.get("scores"):
            raise CalibrationError("E_DIGEST", f"{candidate_id} retained scores drifted")
        candidates.append({**item, "scores": scores})
    ranks = [item["expected_rank"] for item in candidates]
    if len(ranks) != len(set(ranks)) or sorted(ranks) != list(range(1, len(ranks) + 1)):
        raise CalibrationError("E_SCHEMA", "expected ranks must be unique and contiguous")
    failures = pairwise_failures(candidates, dimensions)
    if failures != receipt.get("pairwise_failures"):
        raise CalibrationError("E_DIGEST", "pairwise failures do not match current executions")
    passed = not failures
    if receipt.get("passed") is not passed:
        raise CalibrationError("E_DIGEST", "calibration decision does not match current executions")
    if receipt.get("candidate_count") != len(candidates):
        raise CalibrationError("E_SCHEMA", "candidate_count does not match")
    return {
        "receipt_sha256": receipt_sha256,
        "objective_id": objective_id,
        "evaluator_id": evaluator_id,
        "passed": passed,
        "execution_bound": True,
        "candidate_count": len(candidates),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    calibrate_parser = subparsers.add_parser("calibrate")
    calibrate_parser.add_argument("--project-root", required=True, type=Path)
    calibrate_parser.add_argument("--request", required=True, type=Path)
    calibrate_parser.add_argument("--output", required=True, type=Path)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--project-root", required=True, type=Path)
    verify_parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "calibrate":
        request = require_object(read_json(args.request, "calibration request"), "calibration request")
        receipt = calibrate(args.project_root, request)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"calibration passed={receipt['passed']} failures={len(receipt['pairwise_failures'])}")
        return
    receipt = require_object(read_json(args.receipt, "calibration receipt"), "calibration receipt")
    print(json.dumps(verify_receipt(args.project_root, receipt), sort_keys=True))


if __name__ == "__main__":
    main()
