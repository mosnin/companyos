#!/usr/bin/env python3
"""Assemble verified evaluator execution receipts into one Company OS evaluation batch."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

FABRIC_MODE = "outcome_closed_loop"
BATCH_SCHEMA = "company-os.outcome-evaluation-batch.v1"
EVALUATOR_SCHEMA = "company-os.evaluator-runtime-contract.v1"


class EvaluationAssemblyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise EvaluationAssemblyError("E_SCHEMA", f"{label} must be nonempty")
    return value.strip()


def obj(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvaluationAssemblyError("E_SCHEMA", f"{label} must be an object")
    return value


def safe_relative(value: Any, label: str) -> PurePosixPath:
    raw = text(value, label)
    pure = PurePosixPath(raw)
    if (
        "\\" in raw
        or pure.is_absolute()
        or not pure.parts
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise EvaluationAssemblyError("E_PATH", f"{label} is unsafe")
    return pure


def resolve_file(project_root: Path, value: Any, label: str) -> tuple[Path, str]:
    pure = safe_relative(value, label)
    root = project_root.resolve()
    current = root
    for part in pure.parts:
        current /= part
        if current.is_symlink():
            raise EvaluationAssemblyError("E_PATH", f"{label} traverses a symlink")
    try:
        resolved = (root / Path(*pure.parts)).resolve(strict=True)
    except FileNotFoundError as exc:
        raise EvaluationAssemblyError("E_RECEIPT_MISSING", f"missing {label}: {pure.as_posix()}") from exc
    except OSError as exc:
        raise EvaluationAssemblyError("E_PATH", f"cannot resolve {label}") from exc
    if (
        (resolved != root and root not in resolved.parents)
        or not resolved.is_file()
        or resolved.is_symlink()
    ):
        raise EvaluationAssemblyError("E_PATH", f"{label} is not a regular project file")
    return resolved, pure.as_posix()


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvaluationAssemblyError("E_RECEIPT_MISSING", f"missing {label}: {path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluationAssemblyError("E_JSON", f"invalid {label}: {path}") from exc


def execute_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "execute-outcome-evaluator/scripts/execute_evaluator.py"
    )
    spec = importlib.util.spec_from_file_location("company_os_assemble_evaluations_runtime", path)
    if spec is None or spec.loader is None:
        raise EvaluationAssemblyError("E_RUNTIME", "execute outcome evaluator runtime cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def required_evaluators(project_root: Path, fabric: Mapping[str, Any]) -> set[str]:
    control = obj(fabric.get("outcome_control"), "outcome_control")
    path, _ = resolve_file(
        project_root,
        control.get("evaluator_contract_path"),
        "outcome_control.evaluator_contract_path",
    )
    contract = obj(read_json(path, "evaluator contract"), "evaluator contract")
    if contract.get("$schema") != EVALUATOR_SCHEMA:
        raise EvaluationAssemblyError("E_SCHEMA", f"evaluator contract must use {EVALUATOR_SCHEMA}")
    records = contract.get("evaluators")
    if not isinstance(records, list):
        raise EvaluationAssemblyError("E_SCHEMA", "evaluator contract evaluators must be an array")
    required = {
        text(record.get("evaluator_id"), "evaluator_id")
        for record in records
        if isinstance(record, Mapping) and record.get("required") is True
    }
    if not required:
        raise EvaluationAssemblyError("E_EVALUATOR", "evaluator contract has no required evaluators")
    return required


def expected_receipts(fabric: Mapping[str, Any]) -> list[dict[str, str]]:
    managers = fabric.get("managers")
    if not isinstance(managers, list) or not managers:
        raise EvaluationAssemblyError("E_FABRIC", "evaluation fabric has no managers")
    expected = []
    for manager_index, manager_raw in enumerate(managers):
        manager = obj(manager_raw, f"managers[{manager_index}]")
        workers = manager.get("workers")
        if not isinstance(workers, list) or not workers:
            raise EvaluationAssemblyError("E_FABRIC", "evaluation manager has no workers")
        for worker_index, worker_raw in enumerate(workers):
            worker = obj(worker_raw, f"worker[{worker_index}]")
            scopes = worker.get("write_scope")
            if not isinstance(scopes, list) or len(scopes) != 1:
                raise EvaluationAssemblyError("E_SCOPE", "evaluation worker must have exactly one write scope")
            scope = safe_relative(scopes[0], "worker.write_scope").as_posix()
            evaluator_id = worker.get("evaluator_id")
            if not isinstance(evaluator_id, str) or not evaluator_id.strip():
                authority = worker.get("evaluation_authority")
                if isinstance(authority, Mapping):
                    evaluator_id = authority.get("evaluator_id")
            if not isinstance(evaluator_id, str) or not evaluator_id.strip():
                lane_id = worker.get("outcome_loop_lane_id")
                if isinstance(lane_id, str) and lane_id.startswith("evaluator:"):
                    evaluator_id = lane_id.split(":", 1)[1]
            evaluator_id = text(evaluator_id, "evaluation worker evaluator_id")
            expected.append(
                {
                    "evaluator_id": evaluator_id,
                    "worker_id": text(worker.get("id"), "worker.id"),
                    "receipt_path": f"{scope}/execution-receipt.json",
                }
            )
    return sorted(expected, key=lambda item: item["evaluator_id"])


def assemble(
    project_root: Path,
    fabric_raw: Mapping[str, Any],
    candidate_id: str,
    verifier: Callable[[Path, Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    fabric = dict(fabric_raw)
    if fabric.get("topology_mode") != FABRIC_MODE:
        raise EvaluationAssemblyError("E_FABRIC", f"fabric must use topology_mode {FABRIC_MODE}")
    loop_binding = obj(fabric.get("outcome_loop"), "outcome_loop")
    if loop_binding.get("phase") != "evaluate":
        raise EvaluationAssemblyError("E_PHASE", "evaluation assembly requires evaluate phase")
    control = obj(fabric.get("outcome_control"), "outcome_control")
    objective_id = text(control.get("objective_id"), "outcome_control.objective_id")
    candidate_id = text(candidate_id, "candidate_id")
    required = required_evaluators(project_root, fabric)
    verify = verifier or execute_module().verify_receipt
    receipt_paths: list[str] = []
    observed: set[str] = set()
    for expected in expected_receipts(fabric):
        path, relative_path = resolve_file(
            project_root,
            expected["receipt_path"],
            f"execution receipt for {expected['evaluator_id']}",
        )
        receipt = obj(read_json(path, "execution receipt"), "execution receipt")
        try:
            verified = dict(verify(project_root, receipt))
        except Exception as exc:
            raise EvaluationAssemblyError(
                getattr(exc, "code", "E_EVALUATOR"),
                f"execution receipt failed verification: {exc}",
            ) from exc
        evaluator_id = text(
            verified.get("evaluator_id", receipt.get("evaluator_id")),
            "verified evaluator_id",
        )
        if evaluator_id != expected["evaluator_id"]:
            raise EvaluationAssemblyError("E_BINDING", "execution receipt evaluator does not match assigned worker")
        if verified.get("objective_id", receipt.get("objective_id")) != objective_id:
            raise EvaluationAssemblyError("E_BINDING", "execution receipt objective does not match fabric")
        if evaluator_id in observed:
            raise EvaluationAssemblyError("E_DUPLICATE", f"duplicate evaluator receipt: {evaluator_id}")
        observed.add(evaluator_id)
        receipt_paths.append(relative_path)
    if observed != required:
        raise EvaluationAssemblyError(
            "E_EVALUATOR",
            f"exact required evaluator set is needed; required={sorted(required)} observed={sorted(observed)}",
        )
    return {
        "$schema": BATCH_SCHEMA,
        "candidate_id": candidate_id,
        "receipt_paths": sorted(receipt_paths),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--fabric", type=Path, required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        fabric = obj(read_json(args.fabric, "fabric"), "fabric")
        batch = assemble(args.project_root, fabric, args.candidate_id)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(batch, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "ok": True,
                    "candidate_id": batch["candidate_id"],
                    "receipt_count": len(batch["receipt_paths"]),
                },
                sort_keys=True,
            )
        )
        return 0
    except EvaluationAssemblyError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "error": exc.message}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
