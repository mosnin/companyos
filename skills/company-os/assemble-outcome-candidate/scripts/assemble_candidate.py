#!/usr/bin/env python3
"""Assemble bound production lane manifests into one Company OS outcome candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

FABRIC_MODE = "outcome_closed_loop"
MANIFEST_SCHEMA = "company-os.outcome-lane-artifact-manifest.v1"
CANDIDATE_SCHEMA = "company-os.outcome-candidate.v1"
ARTIFACT_SCHEMA = "company-os.artifact-observation-contract.v1"


class CandidateAssemblyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise CandidateAssemblyError("E_SCHEMA", f"{label} must be nonempty")
    return value.strip()


def sha(value: Any, label: str) -> str:
    value = text(value, label)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise CandidateAssemblyError("E_SCHEMA", f"{label} must be lowercase sha256")
    return value


def obj(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CandidateAssemblyError("E_SCHEMA", f"{label} must be an object")
    return value


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CandidateAssemblyError("E_MANIFEST_MISSING", f"missing {label}: {path}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateAssemblyError("E_JSON", f"invalid {label}: {path}") from exc


def safe_relative(value: Any, label: str) -> PurePosixPath:
    raw = text(value, label)
    pure = PurePosixPath(raw)
    if (
        "\\" in raw
        or pure.is_absolute()
        or not pure.parts
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise CandidateAssemblyError("E_PATH", f"{label} is unsafe")
    return pure


def resolve_file(project_root: Path, value: Any, label: str) -> tuple[Path, str]:
    pure = safe_relative(value, label)
    root = project_root.resolve()
    current = root
    for part in pure.parts:
        current /= part
        if current.is_symlink():
            raise CandidateAssemblyError("E_PATH", f"{label} traverses a symlink")
    try:
        resolved = (root / Path(*pure.parts)).resolve(strict=True)
    except FileNotFoundError as exc:
        raise CandidateAssemblyError("E_ARTIFACT_MISSING", f"{label} does not exist: {pure.as_posix()}") from exc
    except OSError as exc:
        raise CandidateAssemblyError("E_PATH", f"{label} cannot be resolved") from exc
    if (
        (resolved != root and root not in resolved.parents)
        or not resolved.is_file()
        or resolved.is_symlink()
    ):
        raise CandidateAssemblyError("E_PATH", f"{label} is not a regular project file")
    return resolved, pure.as_posix()


def inside_scope(path_value: str, scope_value: str) -> bool:
    path = PurePosixPath(path_value)
    scope = PurePosixPath(scope_value)
    return path == scope or scope in path.parents


def required_artifact_classes(project_root: Path, fabric: Mapping[str, Any]) -> set[str]:
    control = obj(fabric.get("outcome_control"), "outcome_control")
    contract_path, _ = resolve_file(
        project_root,
        control.get("artifact_contract_path"),
        "outcome_control.artifact_contract_path",
    )
    raw = obj(read_json(contract_path, "artifact contract"), "artifact contract")
    if raw.get("$schema") != ARTIFACT_SCHEMA:
        raise CandidateAssemblyError("E_SCHEMA", f"artifact contract must use {ARTIFACT_SCHEMA}")
    records = raw.get("artifact_classes")
    if not isinstance(records, list):
        raise CandidateAssemblyError("E_SCHEMA", "artifact contract artifact_classes must be an array")
    required = {
        text(record.get("artifact_class_id"), "artifact_class_id")
        for record in records
        if isinstance(record, Mapping) and record.get("required") is True
    }
    if not required:
        raise CandidateAssemblyError("E_ARTIFACT", "artifact contract contains no required artifact classes")
    return required


def production_workers(fabric: Mapping[str, Any]) -> list[dict[str, Any]]:
    workers: list[dict[str, Any]] = []
    managers = fabric.get("managers")
    if not isinstance(managers, list) or not managers:
        raise CandidateAssemblyError("E_FABRIC", "fabric contains no managers")
    for manager_index, manager_raw in enumerate(managers):
        manager = obj(manager_raw, f"managers[{manager_index}]")
        lane_id = text(manager.get("outcome_loop_lane_id"), f"managers[{manager_index}].outcome_loop_lane_id")
        lane_sha = sha(manager.get("outcome_loop_lane_sha256"), f"managers[{manager_index}].outcome_loop_lane_sha256")
        manager_workers = manager.get("workers")
        if not isinstance(manager_workers, list) or not manager_workers:
            raise CandidateAssemblyError("E_FABRIC", f"manager {lane_id} has no workers")
        for worker_index, worker_raw in enumerate(manager_workers):
            worker = dict(obj(worker_raw, f"manager {lane_id} worker {worker_index}"))
            if worker.get("outcome_loop_lane_id") != lane_id:
                raise CandidateAssemblyError("E_BINDING", f"worker lane does not match manager lane: {lane_id}")
            if worker.get("outcome_loop_lane_sha256") != lane_sha:
                raise CandidateAssemblyError("E_BINDING", f"worker lane digest does not match manager lane: {lane_id}")
            scopes = worker.get("write_scope")
            if not isinstance(scopes, list) or len(scopes) != 1:
                raise CandidateAssemblyError("E_SCOPE", f"production worker {worker.get('id')} must have exactly one write scope")
            scope = safe_relative(scopes[0], "worker.write_scope").as_posix()
            workers.append(
                {
                    "worker_id": text(worker.get("id"), "worker.id"),
                    "lane_id": lane_id,
                    "lane_sha256": lane_sha,
                    "write_scope": scope,
                    "manifest_path": f"{scope}/artifact-manifest.json",
                    "goal_id": worker.get("goal_contract", {}).get("goal_id"),
                    "goal_sha256": worker.get("goal_contract", {}).get("goal_sha256"),
                    "goal_route_state_sha256": worker.get("goal_assignment", {}).get("route_state_sha256"),
                }
            )
    return workers


def validate_lane_manifest(
    project_root: Path,
    manifest: Mapping[str, Any],
    worker: Mapping[str, Any],
    loop_binding: Mapping[str, Any],
    objective_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if manifest.get("$schema") != MANIFEST_SCHEMA or manifest.get("schema_version") != 1:
        raise CandidateAssemblyError("E_SCHEMA", f"lane manifest must use {MANIFEST_SCHEMA}")
    if manifest.get("objective_id") != objective_id:
        raise CandidateAssemblyError("E_BINDING", "lane manifest objective does not match fabric")
    if manifest.get("outcome_loop_state_sha256") != loop_binding.get("state_sha256"):
        raise CandidateAssemblyError("E_STALE", "lane manifest binds a stale outcome loop state")
    if manifest.get("organization_sha256") != loop_binding.get("organization_sha256"):
        raise CandidateAssemblyError("E_STALE", "lane manifest binds a stale organization")
    if manifest.get("lane_id") != worker["lane_id"]:
        raise CandidateAssemblyError("E_BINDING", "lane manifest lane_id is incorrect")
    if manifest.get("lane_sha256") != worker["lane_sha256"]:
        raise CandidateAssemblyError("E_BINDING", "lane manifest lane digest is incorrect")
    if manifest.get("production_actor_id") != worker["worker_id"]:
        raise CandidateAssemblyError("E_AUTHORITY", "lane manifest production actor is incorrect")
    if worker.get("goal_id") is not None:
        if manifest.get("goal_id") != worker.get("goal_id") or manifest.get("goal_sha256") != worker.get("goal_sha256") or manifest.get("goal_route_state_sha256") != worker.get("goal_route_state_sha256"):
            raise CandidateAssemblyError("E_BINDING", "lane manifest goal binding is incorrect")
    artifacts_raw = manifest.get("artifacts")
    if not isinstance(artifacts_raw, list) or not artifacts_raw:
        raise CandidateAssemblyError("E_ARTIFACT", f"lane {worker['lane_id']} has no materialized artifacts")
    artifacts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, artifact_raw in enumerate(artifacts_raw):
        artifact = obj(artifact_raw, f"artifact[{index}]")
        artifact_id = text(artifact.get("artifact_id"), f"artifact[{index}].artifact_id")
        if artifact_id in seen:
            raise CandidateAssemblyError("E_DUPLICATE", f"duplicate artifact_id {artifact_id}")
        seen.add(artifact_id)
        artifact_class_id = text(
            artifact.get("artifact_class_id"),
            f"artifact[{index}].artifact_class_id",
        )
        artifact_path, relative_path = resolve_file(
            project_root,
            artifact.get("path"),
            f"artifact[{index}].path",
        )
        if not inside_scope(relative_path, worker["write_scope"]):
            raise CandidateAssemblyError(
                "E_SCOPE",
                f"artifact {artifact_id} is outside worker write scope {worker['write_scope']}",
            )
        observed_sha = sha(artifact.get("sha256"), f"artifact[{index}].sha256")
        actual_sha = file_digest(artifact_path)
        if observed_sha != actual_sha:
            raise CandidateAssemblyError("E_DIGEST", f"artifact bytes changed: {artifact_id}")
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "artifact_class_id": artifact_class_id,
                "path": relative_path,
                "sha256": actual_sha,
                "goal_id": worker.get("goal_id"),
                "goal_sha256": worker.get("goal_sha256"),
            }
        )
    observations = []
    observations_raw = manifest.get("observations", [])
    if observations_raw is not None and not isinstance(observations_raw, list):
        raise CandidateAssemblyError("E_OBSERVATION", "lane observations must be an array")
    for index, raw in enumerate(observations_raw or []):
        observation = obj(raw, f"observation[{index}]")
        kind = text(observation.get("kind"), f"observation[{index}].kind")
        if kind not in {"runtime_observed", "journey_connected"}:
            raise CandidateAssemblyError("E_OBSERVATION", f"unsupported observation kind {kind}")
        capability_id = text(observation.get("capability_id"), f"observation[{index}].capability_id")
        evidence_path, relative_path = resolve_file(project_root, observation.get("path"), f"observation[{index}].path")
        if not inside_scope(relative_path, worker["write_scope"]):
            raise CandidateAssemblyError("E_SCOPE", f"observation evidence is outside worker write scope {worker['write_scope']}")
        observed_sha = sha(observation.get("sha256"), f"observation[{index}].sha256")
        actual_sha = file_digest(evidence_path)
        if observed_sha != actual_sha:
            raise CandidateAssemblyError("E_DIGEST", f"observation evidence changed: {relative_path}")
        observations.append({
            "kind": kind,
            "capability_id": capability_id,
            "path": relative_path,
            "sha256": actual_sha,
            "observation_kind": text(observation.get("observation_kind", kind), f"observation[{index}].observation_kind"),
            "goal_id": worker.get("goal_id"),
            "goal_sha256": worker.get("goal_sha256"),
        })
    return sorted(artifacts, key=lambda item: item["artifact_id"]), {
        "path": worker["manifest_path"],
        "file_sha256": digest(manifest),
        "lane_id": worker["lane_id"],
        "production_actor_id": worker["worker_id"],
    }, sorted(observations, key=lambda item: (item["capability_id"], item["kind"], item["path"]))


def assemble(
    project_root: Path,
    fabric_raw: Mapping[str, Any],
    candidate_id: str,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    fabric = dict(fabric_raw)
    if fabric.get("topology_mode") != FABRIC_MODE:
        raise CandidateAssemblyError("E_FABRIC", f"fabric must use topology_mode {FABRIC_MODE}")
    loop_binding = obj(fabric.get("outcome_loop"), "outcome_loop")
    if loop_binding.get("phase") not in {"build_candidate", "rework"}:
        raise CandidateAssemblyError("E_PHASE", "candidate assembly requires build_candidate or rework phase")
    control = obj(fabric.get("outcome_control"), "outcome_control")
    objective_id = text(control.get("objective_id"), "outcome_control.objective_id")
    candidate_id = text(candidate_id, "candidate_id")
    required = required_artifact_classes(project_root, fabric)
    all_artifacts: list[dict[str, Any]] = []
    production_actor_ids: list[str] = []
    seen_artifact_ids: set[str] = set()
    seen_paths: set[str] = set()
    source_manifests = []
    all_observations = []
    for worker in production_workers(fabric):
        manifest_path = project_root / Path(*PurePosixPath(worker["manifest_path"]).parts)
        manifest_raw = obj(read_json(manifest_path, f"lane artifact manifest for {worker['lane_id']}"), "lane manifest")
        artifacts, manifest_binding, observations = validate_lane_manifest(
            project_root,
            manifest_raw,
            worker,
            loop_binding,
            objective_id,
        )
        production_actor_ids.append(worker["worker_id"])
        source_manifests.append(manifest_binding)
        all_observations.extend(observations)
        for artifact in artifacts:
            if artifact["artifact_id"] in seen_artifact_ids:
                raise CandidateAssemblyError("E_DUPLICATE", f"artifact_id reused across lanes: {artifact['artifact_id']}")
            if artifact["path"] in seen_paths:
                raise CandidateAssemblyError("E_DUPLICATE", f"artifact path reused across lanes: {artifact['path']}")
            seen_artifact_ids.add(artifact["artifact_id"])
            seen_paths.add(artifact["path"])
            all_artifacts.append(artifact)
    observed_classes = {artifact["artifact_class_id"] for artifact in all_artifacts}
    missing = sorted(required - observed_classes)
    if missing:
        raise CandidateAssemblyError(
            "E_ARTIFACT",
            "candidate is missing required artifact classes: " + ", ".join(missing),
        )
    mission = fabric.get("mission_control")
    if isinstance(mission, Mapping) and mission.get("first_reality_required") is True:
        runtime_classes = {item["capability_id"] for item in all_observations if item["kind"] == "runtime_observed"}
        connected_classes = {item["capability_id"] for item in all_observations if item["kind"] == "journey_connected"}
        missing_runtime = sorted(required - runtime_classes)
        if missing_runtime:
            raise CandidateAssemblyError("E_OBSERVATION", "first reality candidate lacks runtime observations: " + ", ".join(missing_runtime))
        if not connected_classes.intersection(required):
            raise CandidateAssemblyError("E_OBSERVATION", "first reality candidate lacks a connected journey observation")
    return {
        "$schema": CANDIDATE_SCHEMA,
        "candidate_id": candidate_id,
        "objective_id": objective_id,
        "production_actor_ids": sorted(set(production_actor_ids)),
        "artifacts": sorted(all_artifacts, key=lambda item: item["artifact_id"]),
        "observations": sorted(all_observations, key=lambda item: (item["capability_id"], item["kind"], item["path"])),
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
        candidate = assemble(args.project_root, fabric, args.candidate_id)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "ok": True,
                    "candidate_id": candidate["candidate_id"],
                    "artifact_count": len(candidate["artifacts"]),
                    "production_actor_count": len(candidate["production_actor_ids"]),
                },
                sort_keys=True,
            )
        )
        return 0
    except CandidateAssemblyError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "error": exc.message}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
