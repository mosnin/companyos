#!/usr/bin/env python3
"""Bridge verified native task terminal receipts into the Company OS outcome loop."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


class OutcomeRuntimeBridgeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise OutcomeRuntimeBridgeError("E_SCHEMA", f"{label} must be nonempty")
    return value


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OutcomeRuntimeBridgeError("E_SCHEMA", f"{label} must be an object")
    return value


def _outcome_loop_module():
    path = Path(__file__).resolve().with_name("outcome_loop.py")
    spec = importlib.util.spec_from_file_location("company_os_outcome_loop_bridge_target", path)
    if not spec or not spec.loader:
        raise OutcomeRuntimeBridgeError("E_RUNTIME", "cannot load outcome loop")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safe_artifact(project_root: Path, relative: str, expected_sha: str) -> None:
    pure = PurePosixPath(_text(relative, "artifact path"))
    if pure.is_absolute() or "\\" in relative or any(part in {"", ".", ".."} for part in pure.parts):
        raise OutcomeRuntimeBridgeError("E_PATH", "artifact path is unsafe")
    root = project_root.resolve()
    current = root
    for part in pure.parts:
        current /= part
        if current.is_symlink():
            raise OutcomeRuntimeBridgeError("E_PATH", "artifact path traverses symlink")
    try:
        resolved = (root / Path(*pure.parts)).resolve(strict=True)
    except OSError as exc:
        raise OutcomeRuntimeBridgeError("E_PATH", "artifact path does not exist") from exc
    if (resolved != root and root not in resolved.parents) or not resolved.is_file() or resolved.is_symlink():
        raise OutcomeRuntimeBridgeError("E_PATH", "artifact path is invalid")
    observed = hashlib.sha256(resolved.read_bytes()).hexdigest()
    if observed != expected_sha:
        raise OutcomeRuntimeBridgeError("E_DIGEST", f"artifact digest changed: {relative}")


def _identity_lanes(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    managers = manifest.get("managers")
    if not isinstance(managers, list) or not managers:
        raise OutcomeRuntimeBridgeError("E_MANIFEST", "outcome fabric has no managers")
    result: dict[str, dict[str, Any]] = {}
    for manager_index, raw_manager in enumerate(managers):
        manager = _object(raw_manager, f"managers[{manager_index}]")
        lane_id = _text(manager.get("outcome_loop_lane_id"), "manager outcome loop lane")
        lane_sha = _text(manager.get("outcome_loop_lane_sha256"), "manager outcome loop lane digest")
        workers = manager.get("workers")
        if not isinstance(workers, list) or not workers:
            raise OutcomeRuntimeBridgeError("E_MANIFEST", f"{lane_id} has no workers")
        for worker_index, raw_worker in enumerate(workers):
            worker = _object(raw_worker, f"workers[{worker_index}]")
            identity = _text(worker.get("id"), "worker id")
            if identity in result:
                raise OutcomeRuntimeBridgeError("E_MANIFEST", f"duplicate runtime identity {identity}")
            if worker.get("outcome_loop_lane_id") != lane_id or worker.get("outcome_loop_lane_sha256") != lane_sha:
                raise OutcomeRuntimeBridgeError("E_BINDING", f"worker lane binding changed: {identity}")
            context = _object(worker.get("outcome_context"), f"{identity}.outcome_context")
            classes = context.get("artifact_classes")
            if not isinstance(classes, list) or not classes:
                classes = manager.get("artifact_classes")
            if not isinstance(classes, list) or not classes:
                lane_classes = []
                for scope in worker.get("acceptance", []):
                    if isinstance(scope, str):
                        continue
                raw_classes = manager.get("artifact_classes")
                if isinstance(raw_classes, list):
                    lane_classes.extend(raw_classes)
                classes = lane_classes
            if not isinstance(classes, list) or not all(isinstance(item, str) and item for item in classes):
                raise OutcomeRuntimeBridgeError("E_MANIFEST", f"{identity} has no artifact class authority")
            result[identity] = {
                "lane_id": lane_id,
                "lane_sha256": lane_sha,
                "artifact_classes": sorted(set(classes)),
            }
    return result


def _classes_from_manifest(manifest: Mapping[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    managers = manifest.get("managers")
    if not isinstance(managers, list):
        return result
    for raw_manager in managers:
        if not isinstance(raw_manager, Mapping):
            continue
        lane_id = raw_manager.get("outcome_loop_lane_id")
        if not isinstance(lane_id, str) or not lane_id:
            continue
        classes: set[str] = set()
        for worker in raw_manager.get("workers", []):
            if not isinstance(worker, Mapping):
                continue
            context = worker.get("outcome_context")
            if isinstance(context, Mapping):
                raw = context.get("artifact_classes")
                if isinstance(raw, list):
                    classes.update(item for item in raw if isinstance(item, str) and item)
        if not classes:
            suffix = lane_id.split("artifact:", 1)[1] if lane_id.startswith("artifact:") else None
            if suffix:
                classes.add(suffix)
        result[lane_id] = sorted(classes)
    return result


def advance_candidate(
    project_root: Path,
    loop_state: Mapping[str, Any],
    fabric_manifest: Mapping[str, Any],
    runtime_attempts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Advance build or rework to evaluation when every current lane has real terminal artifacts."""
    loop = _outcome_loop_module()
    try:
        state = loop.verify_state(loop_state)
    except Exception as exc:
        raise OutcomeRuntimeBridgeError(getattr(exc, "code", "E_LOOP"), str(exc)) from exc
    if state.get("phase") not in {"build_candidate", "rework"}:
        raise OutcomeRuntimeBridgeError("E_PHASE", "candidate bridge requires build_candidate or rework")

    lane_classes = _classes_from_manifest(fabric_manifest)
    expected_lanes = set(lane_classes)
    if not expected_lanes:
        raise OutcomeRuntimeBridgeError("E_MANIFEST", "fabric has no outcome production lanes")

    by_lane: dict[str, dict[str, Any]] = {}
    seen_attempt_ids: set[str] = set()
    for index, raw_attempt in enumerate(runtime_attempts):
        attempt = _object(raw_attempt, f"runtime_attempts[{index}]")
        attempt_id = _text(attempt.get("attempt_id"), "attempt_id")
        if attempt_id in seen_attempt_ids:
            raise OutcomeRuntimeBridgeError("E_RUNTIME", f"duplicate attempt {attempt_id}")
        seen_attempt_ids.add(attempt_id)
        admission = _object(attempt.get("native_task_runtime", {}).get("admission"), f"{attempt_id}.admission")
        metadata = _object(admission.get("metadata"), f"{attempt_id}.metadata")
        identity = _text(metadata.get("manifest_identity_id"), f"{attempt_id}.manifest_identity_id")

        lane_id = None
        allowed_classes: list[str] = []
        for manager in fabric_manifest.get("managers", []):
            if not isinstance(manager, Mapping):
                continue
            workers = manager.get("workers")
            if not isinstance(workers, list):
                continue
            if any(isinstance(worker, Mapping) and worker.get("id") == identity for worker in workers):
                lane_id = manager.get("outcome_loop_lane_id")
                if isinstance(lane_id, str):
                    allowed_classes = lane_classes.get(lane_id, [])
                break
        if lane_id not in expected_lanes:
            continue
        if lane_id in by_lane:
            raise OutcomeRuntimeBridgeError("E_RUNTIME", f"multiple terminal attempts claim lane {lane_id}")

        runtime = _object(attempt.get("native_task_runtime"), f"{attempt_id}.native_task_runtime")
        terminal = runtime.get("terminal")
        if terminal is None:
            continue
        terminal = _object(terminal, f"{attempt_id}.terminal")
        observation = _object(terminal.get("observation"), f"{attempt_id}.terminal.observation")
        status = observation.get("status")
        if status != "succeeded":
            raise OutcomeRuntimeBridgeError("E_TERMINAL", f"lane {lane_id} ended {status}")
        bindings = observation.get("artifact_bindings")
        if not isinstance(bindings, list) or not bindings:
            raise OutcomeRuntimeBridgeError("E_ARTIFACT", f"lane {lane_id} produced no classified artifact bindings")
        normalized = []
        for binding_index, raw_binding in enumerate(bindings):
            binding = _object(raw_binding, f"{attempt_id}.artifact_bindings[{binding_index}]")
            artifact_id = _text(binding.get("artifact_id"), "artifact_id")
            artifact_class_id = _text(binding.get("artifact_class_id"), "artifact_class_id")
            path = _text(binding.get("path"), "artifact path")
            sha256 = _text(binding.get("sha256"), "artifact sha256")
            if len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256):
                raise OutcomeRuntimeBridgeError("E_SCHEMA", "artifact sha256 is invalid")
            if allowed_classes and artifact_class_id not in allowed_classes:
                raise OutcomeRuntimeBridgeError("E_AUTHORITY", f"lane {lane_id} produced unauthorized artifact class {artifact_class_id}")
            _safe_artifact(project_root, path, sha256)
            normalized.append({
                "artifact_id": artifact_id,
                "artifact_class_id": artifact_class_id,
                "path": path,
                "sha256": sha256,
            })
        by_lane[lane_id] = {"actor_id": attempt_id, "artifacts": normalized}

    missing_lanes = sorted(expected_lanes - set(by_lane))
    if missing_lanes:
        return {
            "advanced": False,
            "phase": state["phase"],
            "reason": "waiting_for_terminal_artifacts",
            "missing_lanes": missing_lanes,
            "state": dict(state),
        }

    artifacts = []
    artifact_ids: set[str] = set()
    actors = []
    for lane_id in sorted(by_lane):
        lane = by_lane[lane_id]
        actors.append(lane["actor_id"])
        for artifact in lane["artifacts"]:
            if artifact["artifact_id"] in artifact_ids:
                raise OutcomeRuntimeBridgeError("E_ARTIFACT", f"duplicate artifact id {artifact['artifact_id']}")
            artifact_ids.add(artifact["artifact_id"])
            artifacts.append(artifact)
    candidate_basis = {
        "objective_id": state["objective_id"],
        "iteration": state["iteration"] + 1,
        "prior_state_sha256": state["state_sha256"],
        "production_actor_ids": sorted(actors),
        "artifacts": sorted(artifacts, key=lambda item: item["artifact_id"]),
    }
    candidate = {
        "$schema": loop.CANDIDATE_SCHEMA,
        "objective_id": state["objective_id"],
        "candidate_id": f"candidate:{_digest(candidate_basis)[:24]}",
        "production_actor_ids": sorted(actors),
        "artifacts": sorted(artifacts, key=lambda item: item["artifact_id"]),
    }
    try:
        next_state = loop.record_candidate(project_root, state, candidate)
    except Exception as exc:
        raise OutcomeRuntimeBridgeError(getattr(exc, "code", "E_LOOP"), str(exc)) from exc
    return {
        "advanced": True,
        "phase": next_state["phase"],
        "candidate_id": candidate["candidate_id"],
        "state": next_state,
    }
