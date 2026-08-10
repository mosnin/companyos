#!/usr/bin/env python3
"""Compile an outcome loop state into a bounded Luna execution organization."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import importlib.util
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

REQUEST_SCHEMA = "company-os.outcome-organization-request.v1"
BINDING_SCHEMA = "company-os.outcome-loop-fabric-binding.v1"
LOOP_SCHEMA = "company-os.outcome-loop-state.v1"
TOPOLOGY_MODE = "outcome_closed_loop"
PHASES = ["charter", "discovery", "design", "execution", "verification", "integration"]
BUDGET_FIELDS = {"time_minutes", "token_limit", "cost_usd", "max_concurrency", "max_retries"}
OUTCOME_CONTROL_FIELDS = {
    "$schema", "execution_lane", "project_id", "program_version", "work_id",
    "governed_outcome", "objective_id", "outcome_contract_path",
    "artifact_contract_path", "evaluator_contract_path", "benchmark_contract_path",
    "calibration_receipts_path", "scale_authorization_path",
}

class OrganizationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()

def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise OrganizationError("E_SCHEMA", f"{label} must be nonempty")
    return value

def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OrganizationError("E_SCHEMA", f"{label} must be an object")
    return value

def _sha(value: Any, label: str) -> str:
    value = _text(value, label)
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise OrganizationError("E_SCHEMA", f"{label} must be lowercase sha256")
    return value

def _safe(project_root: Path, value: Any, label: str) -> tuple[Path, str]:
    raw = _text(value, label)
    pure = PurePosixPath(raw)
    if "\\" in raw or pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise OrganizationError("E_PATH", f"{label} is unsafe")
    root = project_root.resolve()
    current = root
    for part in pure.parts:
        current /= part
        if current.is_symlink():
            raise OrganizationError("E_PATH", f"{label} traverses a symlink")
    try:
        resolved = (root / Path(*pure.parts)).resolve(strict=True)
    except OSError as exc:
        raise OrganizationError("E_PATH", f"{label} does not exist") from exc
    if (root != resolved and root not in resolved.parents) or not resolved.is_file() or resolved.is_symlink():
        raise OrganizationError("E_PATH", f"{label} is invalid")
    return resolved, pure.as_posix()

def _read(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OrganizationError("E_JSON", f"invalid {label}") from exc

def verify_loop_state(value: Mapping[str, Any]) -> dict[str, Any]:
    state = dict(value)
    if state.get("$schema") != LOOP_SCHEMA:
        raise OrganizationError("E_SCHEMA", "outcome loop state schema is invalid")
    observed = _sha(state.get("state_sha256"), "state_sha256")
    if observed != digest({**state, "state_sha256": None}):
        raise OrganizationError("E_DIGEST", "outcome loop state changed")
    phase = state.get("phase")
    if phase not in {"build_candidate", "rework", "evaluate"}:
        raise OrganizationError("E_PHASE", "execution organization is allowed only while materializing, evaluating, or reworking a candidate")
    next_action = _object(state.get("next_action"), "next_action").get("action")
    expected_action = {
        "build_candidate": "materialize_candidate",
        "rework": "execute_intervention",
        "evaluate": "execute_required_evaluators",
    }[phase]
    if next_action != expected_action:
        raise OrganizationError("E_PHASE", f"{phase} requires next_action {expected_action}")
    return state

def _normalize_lane(raw: Mapping[str, Any]) -> dict[str, Any]:
    lane_id = _text(raw.get("lane_id"), "lane_id")
    role = _text(raw.get("role"), f"{lane_id}.role")
    mandate = raw.get("mandate")
    if not isinstance(mandate, str) or not mandate.strip():
        target = raw.get("target_dimension")
        artifact = raw.get("artifact_class_id")
        if isinstance(target, str) and target.strip():
            mandate = f"Improve the {target} bottleneck on the current real candidate."
        elif isinstance(artifact, str) and artifact.strip():
            mandate = f"Materialize the required {artifact} artifact for the current candidate."
        else:
            mandate = f"Materialize the current candidate for lane {lane_id}."
    classes: list[str] = []
    if isinstance(raw.get("artifact_class_id"), str) and raw["artifact_class_id"].strip():
        classes.append(raw["artifact_class_id"])
    if isinstance(raw.get("artifact_classes"), list):
        classes.extend(item for item in raw["artifact_classes"] if isinstance(item, str) and item.strip())
    classes = sorted(set(classes))
    if not classes:
        raise OrganizationError("E_ORGANIZATION", f"{lane_id} has no artifact classes")
    normalized = {"lane_id": lane_id, "role": role, "mandate": mandate, "artifact_classes": classes}
    if isinstance(raw.get("target_dimension"), str) and raw["target_dimension"].strip():
        normalized["target_dimension"] = raw["target_dimension"]
    if role == "independent_evaluator":
        normalized["evaluator_id"] = _text(raw.get("evaluator_id"), f"{lane_id}.evaluator_id")
        dimensions = raw.get("score_dimensions")
        if not isinstance(dimensions, list) or not dimensions or not all(isinstance(item, str) and item.strip() for item in dimensions):
            raise OrganizationError("E_ORGANIZATION", f"{lane_id} has no score dimensions")
        normalized["score_dimensions"] = sorted(set(dimensions))
    return normalized

def expected_lanes(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    organization = _object(state.get("organization_plan"), "organization_plan")
    if state.get("phase") == "build_candidate":
        raw_lanes = organization.get("production_lanes")
        if not isinstance(raw_lanes, list) or not raw_lanes:
            raw_lanes = organization.get("specialist_lanes")
    elif state.get("phase") == "evaluate":
        raw_lanes = organization.get("evaluation_lanes")
    else:
        raw_lanes = organization.get("specialist_lanes")
    if not isinstance(raw_lanes, list) or not raw_lanes:
        raise OrganizationError("E_ORGANIZATION", "outcome loop has no executable specialist lanes")
    lanes = [_normalize_lane(_object(item, "organization lane")) for item in raw_lanes]
    ids = [lane["lane_id"] for lane in lanes]
    if len(ids) != len(set(ids)):
        raise OrganizationError("E_ORGANIZATION", "organization lane IDs must be unique")
    return sorted(lanes, key=lambda lane: lane["lane_id"])

def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "lane"

def _list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        raise OrganizationError("E_SCHEMA", f"{label} must contain nonempty strings")
    return list(value)

def _budget(value: Any, manager_count: int) -> dict[str, Any]:
    if value is None:
        value = {"time_minutes": 60.0, "token_limit": 12000, "cost_usd": 12.0, "max_concurrency": manager_count, "max_retries": 1}
    value = dict(_object(value, "budget"))
    if set(value) != BUDGET_FIELDS:
        raise OrganizationError("E_SCHEMA", "budget fields are invalid")
    if not isinstance(value.get("token_limit"), int) or isinstance(value["token_limit"], bool) or value["token_limit"] < manager_count:
        raise OrganizationError("E_BUDGET", "budget.token_limit is too small")
    for field in ("time_minutes", "cost_usd"):
        current = value.get(field)
        if not isinstance(current, (int, float)) or isinstance(current, bool) or not math.isfinite(float(current)) or current < 0:
            raise OrganizationError("E_BUDGET", f"budget.{field} is invalid")
    for field in ("max_concurrency", "max_retries"):
        current = value.get(field)
        if not isinstance(current, int) or isinstance(current, bool) or current < 0:
            raise OrganizationError("E_BUDGET", f"budget.{field} is invalid")
    if value["max_concurrency"] < 1 or value["max_concurrency"] > manager_count:
        raise OrganizationError("E_BUDGET", "budget.max_concurrency must fit the compiled organization")
    if value["max_retries"] > 1:
        raise OrganizationError("E_BUDGET", "budget.max_retries cannot exceed one")
    return value

def _child_budget(parent: Mapping[str, Any], manager_count: int) -> dict[str, Any]:
    return {"time_minutes": float(parent["time_minutes"]) / manager_count, "token_limit": max(1, int(parent["token_limit"]) // manager_count), "cost_usd": float(parent["cost_usd"]) / manager_count, "max_concurrency": 1, "max_retries": int(parent["max_retries"])}

def _engineering_module():
    path = Path(__file__).resolve().parents[2] / "engineering-execution-constitution/scripts/engineering_contract.py"
    spec = importlib.util.spec_from_file_location("company_os_engineering_contract", path)
    if spec is None or spec.loader is None:
        raise OrganizationError("E_ENGINEERING", "engineering constitution is unavailable")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def _engineering_root(objective_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
    module = _engineering_module()
    raw = request.get("engineering_execution_contract")
    if raw is None:
        raw = {"contract_id": f"engineering:master:{objective_id}", "objective_id": objective_id, "engineering_rigor": 8, "security_verification": "static", "required_skills": ["repository-intelligence", "architecture", "testing", "runtime-observation"], "write_scopes": []}
        return module.root(raw)
    return module.verify(_object(raw, "engineering_execution_contract"))

def _validate_outcome_control(control: Mapping[str, Any], *, project_id: str, program_version: int, work_id: str, governed_outcome: str, objective_id: str) -> dict[str, Any]:
    if set(control) != OUTCOME_CONTROL_FIELDS:
        raise OrganizationError("E_SCHEMA", "outcome_control fields are invalid")
    if control.get("$schema") != "company-os.outcome-control-binding.v1":
        raise OrganizationError("E_SCHEMA", "outcome_control schema is invalid")
    if control.get("project_id") != project_id or control.get("program_version") != program_version:
        raise OrganizationError("E_BINDING", "outcome_control project or program mismatch")
    if control.get("work_id") != work_id or control.get("governed_outcome") != governed_outcome:
        raise OrganizationError("E_BINDING", "outcome_control work or outcome mismatch")
    if control.get("objective_id") != objective_id:
        raise OrganizationError("E_BINDING", "outcome_control objective mismatch")
    lane = control.get("execution_lane")
    if lane not in {"pilot", "production_scale"}:
        raise OrganizationError("E_SCHEMA", "outcome_control execution lane is invalid")
    for field in ("outcome_contract_path", "artifact_contract_path", "evaluator_contract_path", "benchmark_contract_path", "calibration_receipts_path"):
        _text(control.get(field), f"outcome_control.{field}")
    if lane == "production_scale":
        _text(control.get("scale_authorization_path"), "outcome_control.scale_authorization_path")
    elif control.get("scale_authorization_path") not in {None, ""}:
        raise OrganizationError("E_AUTHORITY", "pilot cannot carry production scale authority")
    return dict(control)

def compile_manifest(project_root: Path, loop_state_path: str, request: Mapping[str, Any]) -> dict[str, Any]:
    if request.get("$schema") != REQUEST_SCHEMA:
        raise OrganizationError("E_SCHEMA", "organization request schema is invalid")
    state_path, state_relative = _safe(project_root, loop_state_path, "loop_state_path")
    state = verify_loop_state(_object(_read(state_path, "outcome loop state"), "outcome loop state"))
    lanes = expected_lanes(state)
    project_id = _text(request.get("project_id"), "project_id")
    program_version = request.get("program_version")
    if not isinstance(program_version, int) or isinstance(program_version, bool) or program_version < 1:
        raise OrganizationError("E_SCHEMA", "program_version must be positive")
    work_id = _text(request.get("work_id"), "work_id")
    governed_outcome = _text(request.get("governed_outcome"), "governed_outcome")
    north_star = _text(request.get("north_star"), "north_star")
    user_value = _text(request.get("user_value"), "user_value")
    rationale = _text(request.get("rationale"), "rationale")
    architecture = _text(request.get("architecture"), "architecture")
    dependencies = _list(request.get("dependencies"), "dependencies")
    non_goals = _list(request.get("non_goals"), "non_goals")
    constraints = _list(request.get("constraints"), "constraints")
    objective_id = _text(state.get("objective_id"), "state.objective_id")
    control = _validate_outcome_control(_object(request.get("outcome_control"), "outcome_control"), project_id=project_id, program_version=program_version, work_id=work_id, governed_outcome=governed_outcome, objective_id=objective_id)
    engineering_module = _engineering_module()
    master_engineering = _engineering_root(objective_id, request)
    if control["execution_lane"] == "pilot" and len(lanes) > 2:
        raise OrganizationError("E_SCALE", "the current organization exceeds pilot authority and requires production scale authorization")
    if len(lanes) > 256:
        raise OrganizationError("E_SCALE", "organization exceeds control plane manager ceiling")
    budget = _budget(request.get("budget"), len(lanes))
    manager_budget = _child_budget(budget, len(lanes))
    preserve_dimensions: list[str] = []
    if state.get("phase") == "rework":
        action = _object(state.get("next_action"), "next_action")
        intervention = _object(action.get("intervention"), "intervention")
        preserve_dimensions = sorted(set(intervention.get("preserve_dimensions", [])))
    managers = []
    lane_sha256s: dict[str, str] = {}
    for index, lane in enumerate(lanes, 1):
        lane_sha = digest(lane)
        lane_sha256s[lane["lane_id"]] = lane_sha
        manager_id = f"outcome-manager-{index:02d}-{_slug(lane['lane_id'])}"
        resource_scope = f"outcome-lanes/{index:02d}-{_slug(lane['lane_id'])}"
        if state.get("phase") == "evaluate":
            acceptance = [
                "Execute the exact bound independent evaluator against the current candidate artifact bytes",
                "Produce an evaluator execution receipt with required scores, findings, and observation evidence",
                "Do not modify candidate artifacts or inherit the production team's completion narrative",
            ]
            worker_task = lane["mandate"] + " Score only the bound dimensions: " + ", ".join(lane["score_dimensions"]) + "."
            worker_write_scope = [f"{resource_scope}/evaluation-receipt"]
            stop_condition = "A verified evaluator execution receipt is materialized, or evaluator execution fails closed"
            extra_constraints = [
                "Candidate artifact bytes are read only during independent evaluation",
                "Evaluator identity must remain independent of every production actor",
                "Evaluation must emit the observation evidence required by the artifact contract",
            ]
        else:
            acceptance = ["Materialize a real candidate artifact for the assigned artifact classes", "Return exact artifact paths and SHA256 digests", "Do not use source code, tests, or completion narrative as product acceptance"]
            acceptance.extend(f"Preserve independently passing quality dimension {dimension}" for dimension in preserve_dimensions)
            worker_task = lane["mandate"]
            if preserve_dimensions:
                worker_task += " Preserve already passing dimensions: " + ", ".join(preserve_dimensions) + "."
            worker_write_scope = [f"{resource_scope}/artifact"]
            stop_condition = "A real artifact is materialized with exact evidence, or a blocking constraint is proven"
            extra_constraints = ["Materialize a real candidate before independent evaluation", "Production actors cannot perform final independent evaluation"]
        outcome_context = {"program_version": program_version, "north_star": north_star, "user_value": user_value, "program_outcome": governed_outcome, "manager_outcome": lane["mandate"], "roadmap_position": "evaluation" if state.get("phase") == "evaluate" else "execution", "artifact_classes": lane["artifact_classes"], "dependencies": dependencies, "non_goals": non_goals, "constraints": constraints + extra_constraints}
        if state.get("phase") == "evaluate":
            outcome_context["evaluator_id"] = lane["evaluator_id"]
            outcome_context["score_dimensions"] = lane["score_dimensions"]
        manager_engineering = engineering_module.derive(master_engineering, {"contract_id": f"engineering:{manager_id}", "objective_id": objective_id, "manager_level": "mid", "required_skills": list(master_engineering["required_skills"]), "write_scopes": [resource_scope]})
        worker_engineering = engineering_module.derive(manager_engineering, {"contract_id": f"engineering:{manager_id}:worker-01", "objective_id": objective_id, "manager_level": "worker", "required_skills": list(manager_engineering["required_skills"]), "write_scopes": worker_write_scope})
        outcome_context["engineering_execution_contract"] = worker_engineering
        workers = [{"id": f"{manager_id}-worker-01", "model": "gpt-5.6-luna", "task": worker_task, "acceptance": acceptance, "write_scope": worker_write_scope, "risk": "medium", "budget": dict(manager_budget), "outcome_context": outcome_context, "engineering_execution_contract": worker_engineering, "stop_condition": stop_condition, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha}]
        managers.append({"id": manager_id, "model": "gpt-5.6-sol", "outcome": lane["mandate"], "acceptance": acceptance, "phase_ids": PHASES, "budget": dict(manager_budget), "write_scope": [resource_scope], "artifact_classes": lane["artifact_classes"], "engineering_execution_contract": manager_engineering, "workers": workers, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha})
    loop_binding = {"$schema": BINDING_SCHEMA, "state_path": state_relative, "state_file_sha256": file_digest(state_path), "state_sha256": state["state_sha256"], "phase": state["phase"], "iteration": state["iteration"], "next_action": state["next_action"]["action"], "organization_sha256": digest(state["organization_plan"]), "lane_sha256s": lane_sha256s}
    engineering_module.assert_nonoverlap([manager["engineering_execution_contract"] for manager in managers])
    return {"program_id": project_id, "topology_mode": TOPOLOGY_MODE, "engineering_execution_contract": master_engineering, "program_version": program_version, "outcome": governed_outcome, "acceptance": ["All required artifact classes are materialized as real inspectable artifacts", "All required independent evaluators execute against the current candidate", "The next outcome loop state is derived from evaluator evidence"], "program_contract": {"north_star": north_star, "user_value": user_value, "rationale": rationale, "architecture": architecture, "roadmap": PHASES, "dependencies": dependencies, "non_goals": non_goals, "constraints": constraints}, "max_managers": len(managers), "max_manager_concurrency": min(len(managers), int(budget["max_concurrency"])), "max_workers_per_manager": 1, "max_total_workers": len(managers), "max_depth": 2, "max_worker_retries": 1, "max_manager_rework_rounds": 2, "budget": budget, "luna_token_share_target": 0.75, "external_effects_allowed": False, "managers": managers, "outcome_control": control, "outcome_loop": loop_binding}

def validate_manifest_binding(project_root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    if manifest.get("topology_mode") != TOPOLOGY_MODE:
        raise OrganizationError("E_MODE", "manifest is not outcome closed loop topology")
    binding = dict(_object(manifest.get("outcome_loop"), "outcome_loop"))
    expected_fields = {"$schema", "state_path", "state_file_sha256", "state_sha256", "phase", "iteration", "next_action", "organization_sha256", "lane_sha256s"}
    if set(binding) != expected_fields or binding.get("$schema") != BINDING_SCHEMA:
        raise OrganizationError("E_SCHEMA", "outcome_loop binding shape is invalid")
    state_path, state_relative = _safe(project_root, binding.get("state_path"), "outcome_loop.state_path")
    if state_relative != binding["state_path"] or file_digest(state_path) != _sha(binding.get("state_file_sha256"), "state_file_sha256"):
        raise OrganizationError("E_DIGEST", "outcome loop state file changed")
    state = verify_loop_state(_object(_read(state_path, "outcome loop state"), "outcome loop state"))
    expected = {"state_sha256": state["state_sha256"], "phase": state["phase"], "iteration": state["iteration"], "next_action": state["next_action"]["action"], "organization_sha256": digest(state["organization_plan"])}
    for field, value in expected.items():
        if binding.get(field) != value:
            raise OrganizationError("E_BINDING", f"outcome_loop.{field} is stale")
    lanes = expected_lanes(state)
    expected_lane_digests = {lane["lane_id"]: digest(lane) for lane in lanes}
    if binding.get("lane_sha256s") != expected_lane_digests:
        raise OrganizationError("E_BINDING", "outcome loop lane bindings are stale")
    managers = manifest.get("managers")
    if not isinstance(managers, list) or len(managers) != len(lanes):
        raise OrganizationError("E_ORGANIZATION", "manifest manager count does not match outcome loop lanes")
    manager_by_lane: dict[str, Mapping[str, Any]] = {}
    for manager in managers:
        manager = _object(manager, "manager")
        lane_id = _text(manager.get("outcome_loop_lane_id"), "manager.outcome_loop_lane_id")
        if lane_id in manager_by_lane:
            raise OrganizationError("E_ORGANIZATION", f"duplicate manager lane {lane_id}")
        manager_by_lane[lane_id] = manager
    if set(manager_by_lane) != set(expected_lane_digests):
        raise OrganizationError("E_ORGANIZATION", "manifest manager lanes do not match outcome loop")
    lane_by_id = {lane["lane_id"]: lane for lane in lanes}
    for lane_id, manager in manager_by_lane.items():
        lane = lane_by_id[lane_id]
        if manager.get("outcome_loop_lane_sha256") != expected_lane_digests[lane_id]:
            raise OrganizationError("E_BINDING", f"manager lane digest changed: {lane_id}")
        if manager.get("outcome") != lane["mandate"]:
            raise OrganizationError("E_ORGANIZATION", f"manager outcome drifted from lane mandate: {lane_id}")
        workers = manager.get("workers")
        if not isinstance(workers, list) or not workers:
            raise OrganizationError("E_ORGANIZATION", f"manager {lane_id} has no worker")
        for worker in workers:
            worker = _object(worker, "worker")
            if worker.get("outcome_loop_lane_id") != lane_id or worker.get("outcome_loop_lane_sha256") != expected_lane_digests[lane_id]:
                raise OrganizationError("E_BINDING", f"worker lane binding changed: {lane_id}")
    control = _object(manifest.get("outcome_control"), "outcome_control")
    if control.get("objective_id") != state.get("objective_id"):
        raise OrganizationError("E_BINDING", "manifest outcome control and loop objective differ")
    return {"state_path": state_relative, "state_file_sha256": binding["state_file_sha256"], "state_sha256": state["state_sha256"], "phase": state["phase"], "iteration": state["iteration"], "next_action": state["next_action"]["action"], "organization_sha256": binding["organization_sha256"], "lane_sha256s": expected_lane_digests}

def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    compile_parser = sub.add_parser("compile")
    compile_parser.add_argument("--project-root", type=Path, required=True)
    compile_parser.add_argument("--loop-state", required=True)
    compile_parser.add_argument("--request", type=Path, required=True)
    compile_parser.add_argument("--output", type=Path, required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--project-root", type=Path, required=True)
    verify_parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "compile":
            request = _object(_read(args.request, "organization request"), "organization request")
            manifest = compile_manifest(args.project_root, args.loop_state, request)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result = validate_manifest_binding(args.project_root, manifest)
        else:
            manifest = _object(_read(args.manifest, "manifest"), "manifest")
            result = validate_manifest_binding(args.project_root, manifest)
        print(json.dumps({"ok": True, **result}, sort_keys=True))
        return 0
    except OrganizationError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "error": exc.message}, sort_keys=True))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
