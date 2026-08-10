#!/usr/bin/env python3
"""Advance Company OS evaluation phases from typed native evaluator terminal receipts."""
from __future__ import annotations

import importlib.util
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping


class OutcomeEvaluationBridgeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise OutcomeEvaluationBridgeError("E_SCHEMA", f"{label} must be nonempty")
    return value


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OutcomeEvaluationBridgeError("E_SCHEMA", f"{label} must be an object")
    return value


def _loop_module():
    path = Path(__file__).resolve().with_name("outcome_loop.py")
    spec = importlib.util.spec_from_file_location("company_os_outcome_loop_eval_bridge", path)
    if not spec or not spec.loader:
        raise OutcomeEvaluationBridgeError("E_RUNTIME", "cannot load outcome loop")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safe_relative(value: Any, label: str) -> str:
    raw = _text(value, label)
    pure = PurePosixPath(raw)
    if "\\" in raw or pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise OutcomeEvaluationBridgeError("E_PATH", f"{label} is unsafe")
    return pure.as_posix()


def _evaluator_identity_map(manifest: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    managers = manifest.get("managers")
    if not isinstance(managers, list) or not managers:
        raise OutcomeEvaluationBridgeError("E_MANIFEST", "evaluation fabric has no managers")
    for manager_index, raw_manager in enumerate(managers):
        manager = _object(raw_manager, f"managers[{manager_index}]")
        lane_id = _text(manager.get("outcome_loop_lane_id"), "manager lane id")
        if not lane_id.startswith("evaluator:"):
            raise OutcomeEvaluationBridgeError("E_MANIFEST", f"non evaluator lane present during evaluation: {lane_id}")
        workers = manager.get("workers")
        if not isinstance(workers, list) or len(workers) != 1:
            raise OutcomeEvaluationBridgeError("E_MANIFEST", f"evaluator lane {lane_id} must have exactly one worker")
        worker = _object(workers[0], f"{lane_id}.worker")
        identity = _text(worker.get("id"), "evaluator worker id")
        context = _object(worker.get("outcome_context"), f"{identity}.outcome_context")
        evaluator_id = context.get("evaluator_id")
        if not isinstance(evaluator_id, str) or not evaluator_id:
            evaluator_id = lane_id.split("evaluator:", 1)[1]
        if identity in result:
            raise OutcomeEvaluationBridgeError("E_MANIFEST", f"duplicate evaluator identity {identity}")
        result[identity] = {"lane_id": lane_id, "evaluator_id": evaluator_id}
    return result


def advance_evaluations(
    project_root: Path,
    loop_state: Mapping[str, Any],
    fabric_manifest: Mapping[str, Any],
    runtime_attempts: list[Mapping[str, Any]],
    verifier: Callable | None = None,
) -> dict[str, Any]:
    """Advance evaluate to rework or reality only after every required evaluator terminates with a typed receipt."""
    loop = _loop_module()
    try:
        state = loop.verify_state(loop_state)
    except Exception as exc:
        raise OutcomeEvaluationBridgeError(getattr(exc, "code", "E_LOOP"), str(exc)) from exc
    if state.get("phase") != "evaluate":
        raise OutcomeEvaluationBridgeError("E_PHASE", "evaluation bridge requires evaluate phase")
    candidate = state.get("candidates", [])[-1] if state.get("candidates") else None
    if not isinstance(candidate, Mapping):
        raise OutcomeEvaluationBridgeError("E_LOOP", "evaluate phase has no current candidate")

    identity_map = _evaluator_identity_map(fabric_manifest)
    required = {item["evaluator_id"] for item in state.get("required_evaluators", []) if isinstance(item, Mapping)}
    manifest_evaluators = {item["evaluator_id"] for item in identity_map.values()}
    if manifest_evaluators != required:
        raise OutcomeEvaluationBridgeError("E_BINDING", "evaluation fabric does not equal required evaluator set")

    receipts: dict[str, str] = {}
    seen_attempts: set[str] = set()
    for index, raw_attempt in enumerate(runtime_attempts):
        attempt = _object(raw_attempt, f"runtime_attempts[{index}]")
        attempt_id = _text(attempt.get("attempt_id"), "attempt_id")
        if attempt_id in seen_attempts:
            raise OutcomeEvaluationBridgeError("E_RUNTIME", f"duplicate evaluator attempt {attempt_id}")
        seen_attempts.add(attempt_id)
        runtime = _object(attempt.get("native_task_runtime"), f"{attempt_id}.native_task_runtime")
        admission = _object(runtime.get("admission"), f"{attempt_id}.admission")
        metadata = _object(admission.get("metadata"), f"{attempt_id}.metadata")
        identity = metadata.get("manifest_identity_id")
        if identity not in identity_map:
            continue
        evaluator_id = identity_map[identity]["evaluator_id"]
        if evaluator_id in receipts:
            raise OutcomeEvaluationBridgeError("E_RUNTIME", f"multiple terminal attempts claim evaluator {evaluator_id}")
        terminal = runtime.get("terminal")
        if terminal is None:
            continue
        terminal = _object(terminal, f"{attempt_id}.terminal")
        observation = _object(terminal.get("observation"), f"{attempt_id}.terminal.observation")
        if observation.get("status") != "succeeded":
            raise OutcomeEvaluationBridgeError("E_TERMINAL", f"evaluator {evaluator_id} ended {observation.get('status')}")
        receipt_path = _safe_relative(observation.get("evaluation_receipt_path"), "evaluation_receipt_path")
        if not (project_root / receipt_path).is_file():
            raise OutcomeEvaluationBridgeError("E_PATH", f"evaluator receipt does not exist: {receipt_path}")
        receipts[evaluator_id] = receipt_path

    missing = sorted(required - set(receipts))
    if missing:
        return {
            "advanced": False,
            "phase": "evaluate",
            "reason": "waiting_for_evaluator_receipts",
            "missing_evaluators": missing,
            "state": dict(state),
        }

    batch = {
        "$schema": loop.BATCH_SCHEMA,
        "candidate_id": candidate["candidate_id"],
        "execution_receipt_paths": [receipts[evaluator_id] for evaluator_id in sorted(receipts)],
    }
    try:
        next_state = loop.record_evaluations(project_root, state, batch, verifier=verifier)
    except Exception as exc:
        raise OutcomeEvaluationBridgeError(getattr(exc, "code", "E_LOOP"), str(exc)) from exc
    return {
        "advanced": True,
        "phase": next_state["phase"],
        "dominant_gap": (
            next_state.get("interventions", [])[-1].get("dominant_gap")
            if next_state.get("phase") == "rework" and next_state.get("interventions")
            else None
        ),
        "state": next_state,
    }
