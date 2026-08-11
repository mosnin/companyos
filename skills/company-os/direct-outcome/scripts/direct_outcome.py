#!/usr/bin/env python3
"""Durable director for the Company OS objective lifecycle."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Mapping

STATE_SCHEMA = "company-os.objective-director-state.v1"


class DirectorError(ValueError):
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
        raise DirectorError("E_SCHEMA", f"{label} must be nonempty")
    return value.strip()


def obj(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DirectorError("E_SCHEMA", f"{label} must be an object")
    return value


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not result:
        raise DirectorError("E_SCHEMA", "objective_id cannot normalize to an empty path")
    return result[:64]


def company_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_module(relative: str, name: str):
    path = company_root() / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise DirectorError("E_RUNTIME", f"cannot load Company OS module {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bootstrap_module():
    return load_module("bootstrap-outcome/scripts/bootstrap_outcome.py", "company_os_director_bootstrap")


def synthesis_module():
    return load_module("synthesize-outcome-model/scripts/synthesize_outcome_model.py", "company_os_director_synthesis")


def stack_module():
    return load_module("materialize-outcome-stack/scripts/materialize_outcome_stack.py", "company_os_director_stack")


def registry_module():
    return load_module("register-outcome-evaluators/scripts/register_outcome_evaluators.py", "company_os_director_registry")


def evaluator_build_module():
    return load_module("build-outcome-evaluators/scripts/compile_evaluator_build_fabric.py", "company_os_director_evaluator_build")


def calibration_fabric_module():
    return load_module("calibrate-outcome-stack/scripts/compile_calibration_fabric.py", "company_os_director_calibration_fabric")


def calibration_module():
    return load_module("calibrate-outcome-evaluator/scripts/calibrate_evaluator.py", "company_os_director_calibration")


def scale_module():
    return load_module("authorize-outcome-scale/scripts/authorize_outcome_scale.py", "company_os_director_scale")


def outcome_control_module():
    return load_module("elastic-company-os/scripts/outcome_control.py", "company_os_director_control")


def outcome_loop_module():
    return load_module("elastic-company-os/scripts/outcome_loop.py", "company_os_director_loop")


def organization_module():
    return load_module("compile-outcome-organization/scripts/compile_outcome_organization.py", "company_os_director_organization")


def candidate_assembler_module():
    return load_module("assemble-outcome-candidate/scripts/assemble_candidate.py", "company_os_director_candidate_assembler")


def evaluation_assembler_module():
    return load_module("assemble-outcome-evaluations/scripts/assemble_evaluations.py", "company_os_director_evaluation_assembler")


def reality_module():
    return load_module("accept-outcome-reality/scripts/accept_reality.py", "company_os_director_reality")


def artifact_observation_module():
    return load_module("define-outcome-artifacts/scripts/compile_artifact_observations.py", "company_os_director_artifacts")


def mission_control_module():
    return load_module("mission-execution-control/scripts/mission_control.py", "company_os_director_mission_control")


def control_store_module():
    return load_module("elastic-company-os/scripts/control_store.py", "company_os_director_store")


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DirectorError("E_JSON", f"cannot read {label}: {path}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def relative(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError as exc:
        raise DirectorError("E_PATH", f"path escapes project root: {path}") from exc


def workspace(project_root: Path, objective_id: str) -> Path:
    return project_root.resolve() / ".company-os" / "outcomes" / slug(objective_id)


def state_path(project_root: Path, objective_id: str) -> Path:
    return workspace(project_root, objective_id) / "director-state.json"


def mission_state_path(project_root: Path, objective_id: str) -> Path:
    return workspace(project_root, objective_id) / "mission-execution-state.json"


def load_mission_state(project_root: Path, objective_id: str) -> dict[str, Any]:
    return mission_control_module().verify_state(
        obj(read_json(mission_state_path(project_root, objective_id), "mission execution state"), "mission execution state")
    )


def save_mission_state(project_root: Path, state: Mapping[str, Any]) -> dict[str, Any]:
    verified = mission_control_module().verify_state(state)
    write_json(mission_state_path(project_root, verified["objective_id"]), verified)
    return verified


def refresh_mission_state(project_root: Path, objective_id: str) -> dict[str, Any]:
    module = mission_control_module()
    refreshed = module.refresh_governor(module.reconcile_deadlines(load_mission_state(project_root, objective_id)))
    return save_mission_state(project_root, refreshed)


def mission_binding(project_root: Path, objective_id: str) -> dict[str, Any]:
    state = refresh_mission_state(project_root, objective_id)
    decision = obj(state.get("governor_decision"), "governor decision")
    return {
        "$schema": "company-os.mission-execution-binding.v1",
        "state_path": relative(project_root, mission_state_path(project_root, objective_id)),
        "state_sha256": state["state_sha256"],
        "mission_id": state["mission_id"],
        "generation": state["generation"],
        "status": state["status"],
        "mission_class": state["mission_class"],
        "governor_decision_sha256": decision["decision_sha256"],
        "governor_mode": decision["mode"],
        "allowed_work_classes": list(decision["allowed_work_classes"]),
        "paused_work_classes": list(decision["paused_work_classes"]),
        "dominant_bottleneck": decision.get("dominant_bottleneck"),
        "first_reality": state.get("first_reality"),
        "first_reality_required": state.get("first_reality") is not None and not mission_control_module().reality_signals(state)["connected_vertical_slice"],
        "replacement_orders": list(state.get("replacement_orders", [])),
    }


def admit_mission_work(
    project_root: Path,
    objective_id: str,
    *,
    work_class: str,
    task_id: str,
    manager_id: str,
    bootstrap: bool = False,
    justification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    module = mission_control_module()
    state = refresh_mission_state(project_root, objective_id)
    request = {
        "$schema": module.ADMISSION_SCHEMA,
        "request_id": f"admit:{task_id}:{state['generation']}",
        "task_id": task_id,
        "manager_id": manager_id,
        "work_class": work_class,
        "bootstrap": bootstrap,
    }
    if justification is not None:
        request["justification"] = dict(justification)
    receipt = module.admit_work(state, request)
    admission_root = workspace(project_root, objective_id) / "runtime/work-admissions"
    admission_path = admission_root / f"{slug(task_id)}.json"
    write_json(admission_path, receipt)
    if receipt.get("admitted") is not True:
        raise DirectorError("E_GOVERNOR", "; ".join(receipt.get("blockers", [])))
    return {
        **receipt,
        "receipt_path": relative(project_root, admission_path),
        "receipt_file_sha256": file_digest(admission_path),
    }


def compile_first_reality_artifact_contract(
    artifact_contract: Mapping[str, Any],
    first_reality: Mapping[str, Any],
) -> dict[str, Any]:
    selected = set(first_reality.get("required_artifact_class_ids", []))
    records = []
    for raw in artifact_contract.get("artifact_classes", []):
        if not isinstance(raw, Mapping) or raw.get("artifact_class_id") not in selected:
            continue
        records.append(
            {
                "artifact_class_id": raw["artifact_class_id"],
                "label": raw.get("label") or raw["artifact_class_id"],
                "required": True,
                "modalities": list(raw.get("modalities") or ["executable"]),
                "observation_methods": list(raw.get("observation_methods") or ["runtime"]),
                "required_evidence": list(raw.get("required_evidence") or ["runtime_receipt"]),
            }
        )
    request = {
        "$schema": "company-os.artifact-observation-request.v1",
        "objective_id": first_reality["objective_id"],
        "artifact_classes": records,
    }
    return artifact_observation_module().compile_contract(request)


def record_candidate_mission_evidence(
    project_root: Path,
    objective_id: str,
    candidate: Mapping[str, Any],
) -> None:
    module = mission_control_module()
    state = load_mission_state(project_root, objective_id)
    known = {item["capability_id"] for item in state["capabilities"]}
    stamp = module.format_time(module.now_utc())
    for artifact in candidate.get("artifacts", []):
        if not isinstance(artifact, Mapping) or artifact.get("artifact_class_id") not in known:
            continue
        capability_id = artifact["artifact_class_id"]
        current = next(item for item in state["capabilities"] if item["capability_id"] == capability_id)
        if current["state"] == "missing":
            event = module.make_event(
                f"{candidate['candidate_id']}:{capability_id}:artifact",
                "artifact_materialized",
                occurred_at=stamp,
                work_class="implementation",
                capability_id=capability_id,
                evidence={"kind": "candidate_artifact", "path": artifact["path"], "sha256": artifact["sha256"], "capability_id": capability_id},
            )
            state = module.record_event(state, event)
    observations = sorted(
        (item for item in candidate.get("observations", []) if isinstance(item, Mapping)),
        key=lambda item: (0 if item.get("kind") == "runtime_observed" else 1, str(item.get("capability_id")), str(item.get("path"))),
    )
    for observation in observations:
        if observation.get("capability_id") not in known:
            continue
        capability_id = observation["capability_id"]
        kind = observation.get("kind")
        event_kind = "runtime_observed" if kind == "runtime_observed" else "journey_connected" if kind == "journey_connected" else None
        if event_kind is None:
            continue
        current = next(item for item in state["capabilities"] if item["capability_id"] == capability_id)
        expected = "partial" if event_kind == "runtime_observed" else "runnable"
        if current["state"] != expected:
            continue
        event = module.make_event(
            f"{candidate['candidate_id']}:{capability_id}:{event_kind}",
            event_kind,
            occurred_at=stamp,
            work_class="runtime" if event_kind == "runtime_observed" else "integration",
            capability_id=capability_id,
            evidence={"kind": observation.get("observation_kind") or event_kind, "path": observation["path"], "sha256": observation["sha256"], "capability_id": capability_id},
            observation_kind=observation.get("observation_kind"),
        )
        state = module.record_event(state, event)
    save_mission_state(project_root, state)


def finalize_mission_acceptance(
    project_root: Path,
    objective_id: str,
    loop: Mapping[str, Any],
    receipt_path: Path,
    receipt: Mapping[str, Any],
) -> None:
    if receipt.get("accepted") is not True:
        return
    module = mission_control_module()
    state = load_mission_state(project_root, objective_id)
    candidate = loop.get("candidates", [])[-1]
    stamp = module.format_time(module.now_utc())
    for capability in list(state["capabilities"]):
        if capability["state"] != "connected":
            continue
        state = module.record_event(
            state,
            module.make_event(
                f"{candidate['candidate_id']}:{capability['capability_id']}:accepted",
                "independent_accepted",
                occurred_at=stamp,
                work_class="evaluation",
                capability_id=capability["capability_id"],
                evidence={"kind": "reality_acceptance", "path": relative(project_root, receipt_path), "sha256": file_digest(receipt_path), "capability_id": capability["capability_id"]},
            ),
        )
    checkpoint = module.create_checkpoint(
        state,
        candidate_id=candidate["candidate_id"],
        capability_ids=[item["capability_id"] for item in state["capabilities"]],
        artifacts=[{"path": item["path"], "sha256": item["sha256"]} for item in candidate.get("artifact_bindings", candidate.get("artifacts", []))],
        verification_receipts=[{"path": relative(project_root, receipt_path), "sha256": file_digest(receipt_path)}],
    )
    state = module.record_event(
        state,
        module.make_event(
            f"{candidate['candidate_id']}:checkpoint",
            "checkpoint_recorded",
            occurred_at=stamp,
            work_class="checkpoint",
            checkpoint=checkpoint,
        ),
    )
    save_mission_state(project_root, state)


def seal(state: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(state)
    result["director_sha256"] = None
    result["director_sha256"] = digest(result)
    return result


def verify_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(raw)
    if value.get("$schema") != STATE_SCHEMA:
        raise DirectorError("E_SCHEMA", "objective director state schema is invalid")
    observed = text(value.get("director_sha256"), "director_sha256")
    if len(observed) != 64 or digest({**value, "director_sha256": None}) != observed:
        raise DirectorError("E_DIGEST", "objective director state changed")
    return value


def load_state(project_root: Path, objective_id: str) -> dict[str, Any]:
    path = state_path(project_root, objective_id)
    return verify_state(obj(read_json(path, "director state"), "director state"))


def save_state(project_root: Path, state: Mapping[str, Any]) -> dict[str, Any]:
    result = seal(state)
    write_json(state_path(project_root, result["objective_id"]), result)
    return result


def next_execute_fabric(stage: str, path: str, *, reason: str) -> dict[str, Any]:
    return {
        "action": "execute_fabric",
        "stage": stage,
        "fabric_path": path,
        "reason": reason,
        "after_completion": "advance_director",
    }


def start(project_root: Path, objective_id: str, objective: str) -> dict[str, Any]:
    project_root = project_root.resolve()
    objective_id = text(objective_id, "objective_id")
    objective = text(objective, "objective")
    path = state_path(project_root, objective_id)
    if path.exists():
        existing = load_state(project_root, objective_id)
        if existing.get("original_objective") != objective:
            raise DirectorError("E_CONFLICT", "objective director already exists with a different original objective")
        return existing
    try:
        receipt = bootstrap_module().bootstrap(project_root, objective_id, objective)
    except Exception as exc:
        raise DirectorError(getattr(exc, "code", "E_BOOTSTRAP"), f"outcome bootstrap failed: {exc}") from exc
    discovery_fabric = receipt["paths"]["discovery_fabric"]
    mission = mission_control_module().initialize_state(objective_id, objective)
    save_mission_state(project_root, mission)
    state = {
        "$schema": STATE_SCHEMA,
        "schema_version": 1,
        "objective_id": objective_id,
        "original_objective": objective,
        "workspace": relative(project_root, workspace(project_root, objective_id)),
        "stage": "discovery",
        "artifacts": {
            "bootstrap_receipt": receipt["paths"]["receipt"],
            "outcome_request": receipt["paths"]["request"],
            "discovery_contract": receipt["paths"]["contract"],
            "outcome_loop": receipt["paths"]["loop_state"],
            "discovery_fabric": discovery_fabric,
            "mission_execution_state": relative(project_root, mission_state_path(project_root, objective_id)),
        },
        "next_action": next_execute_fabric(
            "discovery",
            discovery_fabric,
            reason="Close the universal blocking unknowns with cited independent research.",
        ),
        "history": [
            {
                "event": "objective_started",
                "bootstrap_receipt_sha256": receipt["receipt_sha256"],
            }
        ],
        "director_sha256": None,
    }
    saved = save_state(project_root, state)
    saved["next_action"]["mission_control"] = mission_binding(project_root, objective_id)
    return save_state(project_root, saved)


def proposal_paths(base: Path) -> list[Path]:
    return [
        base / "discovery/domain-truth/proposal.json",
        base / "discovery/artifact-quality/proposal.json",
    ]


def load_contracts(base: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    outcome = obj(read_json(base / "measurable-outcome-contract.json", "outcome contract"), "outcome contract")
    runtime = base / "runtime"
    artifacts = obj(read_json(runtime / "artifact-contract.json", "artifact contract"), "artifact contract")
    evaluators = obj(read_json(runtime / "evaluator-contract.json", "evaluator contract"), "evaluator contract")
    benchmarks = obj(read_json(runtime / "benchmark-contract.json", "benchmark contract"), "benchmark contract")
    return dict(outcome), dict(artifacts), dict(evaluators), dict(benchmarks)


def verified_calibrations(project_root: Path, base: Path, evaluator_contract: Mapping[str, Any]) -> tuple[list[dict[str, Any]], set[str]]:
    required = {
        item["evaluator_id"]
        for item in evaluator_contract.get("evaluators", [])
        if isinstance(item, Mapping) and item.get("required") is True
    }
    receipts: dict[str, dict[str, Any]] = {}
    calibration_root = project_root / ".company-os" / "calibration"
    if calibration_root.is_dir():
        for path in sorted(calibration_root.rglob("*.json")):
            try:
                raw = read_json(path, "calibration candidate")
            except DirectorError:
                continue
            if not isinstance(raw, Mapping) or raw.get("$schema") != "company-os.evaluator-calibration-receipt.v1":
                continue
            try:
                verified = calibration_module().verify_receipt(project_root, raw)
            except Exception:
                continue
            evaluator_id = verified.get("evaluator_id")
            if evaluator_id not in required or verified.get("passed") is not True or verified.get("execution_bound") is not True:
                continue
            if evaluator_id in receipts:
                raise DirectorError("E_DUPLICATE", f"multiple valid calibration receipts exist for {evaluator_id}")
            receipts[evaluator_id] = dict(raw)
    ordered = [receipts[key] for key in sorted(receipts)]
    return ordered, set(receipts)


def build_outcome_control(
    project_root: Path,
    state: Mapping[str, Any],
    outcome: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    evaluators: Mapping[str, Any],
    benchmarks: Mapping[str, Any],
    calibrations: list[dict[str, Any]],
    *,
    force_lane: str | None = None,
    artifact_contract_file: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = workspace(project_root, state["objective_id"])
    runtime = base / "runtime"
    required_artifact_count = sum(1 for item in artifacts.get("artifact_classes", []) if isinstance(item, Mapping) and item.get("required") is True)
    if required_artifact_count < 1:
        raise DirectorError("E_ARTIFACT", "outcome requires at least one real artifact class")
    lane = force_lane or ("pilot" if required_artifact_count <= 2 else "production_scale")
    if lane not in {"pilot", "production_scale"}:
        raise DirectorError("E_SCHEMA", "force_lane must be pilot or production_scale")
    scale_path = runtime / "scale-authorization.json"
    if lane == "production_scale":
        scale = scale_module().authorize(outcome, artifacts, evaluators, benchmarks, calibrations)
        if scale.get("authorized") is not True:
            raise DirectorError("E_SCALE", "outcome stack is not scale authorized: " + json.dumps(scale.get("blockers", []), sort_keys=True))
        write_json(scale_path, scale)
    try:
        _, control_state = control_store_module().load(project_root)
    except Exception as exc:
        raise DirectorError("E_STATE", f"control store unavailable: {exc}") from exc
    project_id = text(obj(control_state.get("instance"), "instance").get("project_id"), "project_id")
    strategy = obj(control_state.get("strategy"), "strategy")
    program_version = strategy.get("program_version")
    if not isinstance(program_version, int) or isinstance(program_version, bool) or program_version < 1:
        raise DirectorError("E_STATE", "strategy.program_version is invalid")
    work_id = f"outcome-delivery-{slug(state['objective_id'])}"
    calibrations_path = runtime / "calibrations.json"
    write_json(calibrations_path, calibrations)
    active_artifact_contract = artifact_contract_file or (runtime / "artifact-contract.json")
    binding = {
        "$schema": "company-os.outcome-control-binding.v1",
        "execution_lane": lane,
        "project_id": project_id,
        "program_version": program_version,
        "work_id": work_id,
        "governed_outcome": state["original_objective"],
        "objective_id": state["objective_id"],
        "outcome_contract_path": relative(project_root, base / "measurable-outcome-contract.json"),
        "artifact_contract_path": relative(project_root, active_artifact_contract),
        "evaluator_contract_path": relative(project_root, runtime / "evaluator-contract.json"),
        "benchmark_contract_path": relative(project_root, runtime / "benchmark-contract.json"),
        "calibration_receipts_path": relative(project_root, calibrations_path),
        "scale_authorization_path": None if lane == "pilot" else relative(project_root, scale_path),
    }
    # Initial pilots stay inside the legacy two-manager ceiling even when the final
    # product has many required artifact classes. outcome_loop bundles classes into
    # those lanes; the candidate must still cover every required class.
    manager_count = min(2, required_artifact_count) if lane == "pilot" else max(1, min(required_artifact_count, 2))
    probe_manifest = {"outcome": state["original_objective"], "max_managers": manager_count, "max_manager_concurrency": manager_count, "max_workers_per_manager": 1, "max_total_workers": manager_count, "managers": [{"workers": [{}]} for _ in range(manager_count)], "outcome_control": binding}
    try:
        portable = outcome_control_module().validate_manifest_binding(project_root=project_root, manifest=probe_manifest, project_id=project_id, program_version=program_version, work_id=work_id, governed_outcome=state["original_objective"])
    except Exception as exc:
        raise DirectorError(getattr(exc, "code", "E_CONTROL"), f"outcome control binding failed: {exc}") from exc
    write_json(runtime / "outcome-control-state.json", portable)
    return binding, portable

def organization_request(
    project_root: Path,
    state: Mapping[str, Any],
    binding: Mapping[str, Any],
) -> dict[str, Any]:
    _, control_state = control_store_module().load(project_root)
    strategy = obj(control_state.get("strategy"), "strategy")
    instance = obj(control_state.get("instance"), "instance")
    return {
        "$schema": "company-os.outcome-organization-request.v1",
        "mission_control": mission_binding(project_root, state["objective_id"]),
        "project_id": text(instance.get("project_id"), "project_id"),
        "program_version": strategy["program_version"],
        "work_id": binding["work_id"],
        "governed_outcome": state["original_objective"],
        "north_star": strategy.get("north_star") or state["original_objective"],
        "user_value": state["original_objective"],
        "rationale": "Materialize and improve the real artifact until independent evidence accepts the original objective.",
        "architecture": "Outcome closed loop organization compiled from current artifact requirements or dominant bottleneck.",
        "dependencies": ["Current Company OS outcome contracts and evaluator capabilities"],
        "non_goals": ["Treat process completion as product acceptance"],
        "constraints": ["Production narratives are inadmissible for final acceptance", "Passing dimensions must be preserved during rework"],
        "outcome_control": dict(binding),
    }


def compile_current_fabric(project_root: Path, state: Mapping[str, Any], binding: Mapping[str, Any]) -> str:
    base = workspace(project_root, state["objective_id"])
    loop_path = base / "outcome-loop.json"
    phase = read_json(loop_path, "outcome loop").get("phase")
    work_class = {"build_candidate": "implementation", "rework": "repair", "evaluate": "evaluation"}.get(phase)
    if work_class is None:
        raise DirectorError("E_PHASE", f"cannot compile execution fabric for phase {phase!r}")
    admission = admit_mission_work(
        project_root,
        state["objective_id"],
        work_class=work_class,
        task_id=f"outcome-{phase}",
        manager_id="outcome-director",
    )
    request = organization_request(project_root, state, binding)
    request["work_admission"] = admission
    request_path = base / "runtime/outcome-organization-request.json"
    write_json(request_path, request)
    try:
        manifest = organization_module().compile_manifest(
            project_root,
            relative(project_root, loop_path),
            request,
        )
    except Exception as exc:
        raise DirectorError(getattr(exc, "code", "E_ORGANIZATION"), f"outcome organization failed: {exc}") from exc
    phase = read_json(loop_path, "outcome loop").get("phase")
    manifest_path = base / f"runtime/{phase}-fabric.json"
    write_json(manifest_path, manifest)
    return relative(project_root, manifest_path)


def advance(project_root: Path, objective_id: str) -> dict[str, Any]:
    project_root = project_root.resolve()
    state = load_state(project_root, objective_id)
    base = workspace(project_root, objective_id)
    stage = state["stage"]

    if stage == "discovery":
        proposals = proposal_paths(base)
        missing = [relative(project_root, path) for path in proposals if not path.is_file()]
        if missing:
            admission = admit_mission_work(
                project_root,
                objective_id,
                work_class="research",
                task_id="outcome-discovery",
                manager_id="outcome-director",
                bootstrap=True,
            )
            state["next_action"] = next_execute_fabric(
                "discovery",
                state["artifacts"]["discovery_fabric"],
                reason="Discovery proposals are still missing: " + ", ".join(missing),
            )
            state["next_action"]["mission_control"] = mission_binding(project_root, objective_id)
            state["next_action"]["work_admission"] = admission
            return save_state(project_root, state)
        base_request = obj(
            read_json(base / "outcome-request.json", "outcome request"),
            "outcome request",
        )
        proposal_values = [obj(read_json(path, "discovery proposal"), "discovery proposal") for path in proposals]
        try:
            measurable_request, measurable_contract = synthesis_module().synthesize(
                base_request,
                proposal_values,
            )
        except Exception as exc:
            raise DirectorError(getattr(exc, "code", "E_SYNTHESIS"), f"outcome synthesis failed: {exc}") from exc
        write_json(base / "measurable-outcome-request.json", measurable_request)
        write_json(base / "measurable-outcome-contract.json", measurable_contract)
        stack_module().materialize(
            base / "measurable-outcome-request.json",
            base / "runtime",
        )
        final_artifact_contract = obj(read_json(base / "runtime/artifact-contract.json", "artifact contract"), "artifact contract")
        mission = mission_control_module().update_scope(load_mission_state(project_root, objective_id), final_artifact_contract)
        save_mission_state(project_root, mission)
        first_reality_path = base / "first-reality-contract.json"
        write_json(first_reality_path, mission["first_reality"])
        first_artifact_contract = compile_first_reality_artifact_contract(final_artifact_contract, mission["first_reality"])
        first_artifact_path = base / "runtime/first-reality-artifact-contract.json"
        write_json(first_artifact_path, first_artifact_contract)
        state["stage"] = "control"
        state["artifacts"].update(
            {
                "measurable_outcome_request": relative(project_root, base / "measurable-outcome-request.json"),
                "measurable_outcome_contract": relative(project_root, base / "measurable-outcome-contract.json"),
                "artifact_contract": relative(project_root, base / "runtime/artifact-contract.json"),
                "evaluator_contract": relative(project_root, base / "runtime/evaluator-contract.json"),
                "benchmark_contract": relative(project_root, base / "runtime/benchmark-contract.json"),
                "first_reality_contract": relative(project_root, first_reality_path),
                "first_reality_artifact_contract": relative(project_root, first_artifact_path),
            }
        )
        state["history"].append({"event": "discovery_synthesized"})
        state = save_state(project_root, state)
        return advance(project_root, objective_id)

    if stage == "evaluator_capability":
        evaluator_contract = obj(
            read_json(base / "runtime/evaluator-contract.json", "evaluator contract"),
            "evaluator contract",
        )
        registry_path = base / "runtime/evaluator-adapter-registry.json"
        try:
            registry = registry_module().build_registry(project_root, evaluator_contract)
        except Exception as exc:
            if getattr(exc, "code", None) != "E_ADAPTER_MISSING":
                raise DirectorError(getattr(exc, "code", "E_ADAPTER"), f"evaluator registration failed: {exc}") from exc
            build = evaluator_build_module().compile_manifest(
                project_root,
                relative(project_root, base / "runtime/evaluator-contract.json"),
                relative(project_root, base / "runtime/artifact-contract.json"),
                relative(project_root, base / "runtime/benchmark-contract.json"),
            )
            if build.get("complete") is True:
                raise DirectorError("E_ADAPTER", "evaluator registry reported missing adapter but build compiler found no missing capability")
            build_path = base / "runtime/evaluator-build-fabric.json"
            write_json(build_path, build["fabric"])
            state["next_action"] = next_execute_fabric(
                "evaluator_capability",
                relative(project_root, build_path),
                reason="Required evaluator adapter bytes are missing.",
            )
            return save_state(project_root, state)
        write_json(registry_path, registry)
        state["artifacts"]["evaluator_adapter_registry"] = relative(project_root, registry_path)
        state["stage"] = "calibration"
        state["history"].append({"event": "evaluator_adapters_registered", "registry_sha256": registry["registry_sha256"]})
        state = save_state(project_root, state)
        return advance(project_root, objective_id)

    if stage == "calibration":
        evaluator_contract = obj(
            read_json(base / "runtime/evaluator-contract.json", "evaluator contract"),
            "evaluator contract",
        )
        receipts, calibrated = verified_calibrations(project_root, base, evaluator_contract)
        required = {
            item["evaluator_id"]
            for item in evaluator_contract.get("evaluators", [])
            if isinstance(item, Mapping) and item.get("required") is True
        }
        if not required.issubset(calibrated):
            result = calibration_fabric_module().compile_manifest(
                project_root,
                relative(project_root, base / "runtime/evaluator-contract.json"),
                relative(project_root, base / "runtime/artifact-contract.json"),
                relative(project_root, base / "runtime/benchmark-contract.json"),
                relative(project_root, base / "runtime/evaluator-adapter-registry.json"),
                calibrated,
            )
            if result.get("complete") is True:
                raise DirectorError("E_CALIBRATION", "required calibration receipts are missing but calibration compiler found no work")
            calibration_path = base / "runtime/calibration-fabric.json"
            write_json(calibration_path, result["fabric"])
            state["next_action"] = next_execute_fabric(
                "calibration",
                relative(project_root, calibration_path),
                reason="Required evaluators have not yet proven strict quality discrimination.",
            )
            return save_state(project_root, state)
        state["stage"] = "control"
        state["history"].append({"event": "evaluators_calibrated", "evaluator_ids": sorted(calibrated)})
        state = save_state(project_root, state)
        return advance(project_root, objective_id)

    if stage == "control":
        outcome, artifacts, evaluators, benchmarks = load_contracts(base)
        loop_path = base / "outcome-loop.json"
        loop = obj(read_json(loop_path, "outcome loop"), "outcome loop")
        phase = loop.get("phase")
        if phase == "discovery":
            # Build the first real candidate before spending the mission on evaluator
            # construction/calibration. Empty calibration bindings are valid for a
            # bounded, reversible pilot.
            pilot_artifacts = obj(read_json(base / "runtime/first-reality-artifact-contract.json", "first reality artifact contract"), "first reality artifact contract")
            binding, portable = build_outcome_control(
                project_root,
                state,
                outcome,
                pilot_artifacts,
                evaluators,
                benchmarks,
                [],
                force_lane="pilot",
                artifact_contract_file=base / "runtime/first-reality-artifact-contract.json",
            )
            try:
                bound_loop = outcome_loop_module().bind_control(project_root, loop, portable)
            except Exception as exc:
                raise DirectorError(getattr(exc, "code", "E_LOOP"), f"outcome loop pilot binding failed: {exc}") from exc
            write_json(loop_path, bound_loop)
            state["history"].append({"event": "first_reality_pilot_bound", "execution_lane": "pilot"})
        elif phase == "evaluate":
            calibrations, calibrated = verified_calibrations(project_root, base, evaluators)
            required = {item["evaluator_id"] for item in evaluators.get("evaluators", []) if isinstance(item, Mapping) and item.get("required") is True}
            if not required.issubset(calibrated):
                state["stage"] = "calibration"
                return save_state(project_root, state)
            binding, portable = build_outcome_control(project_root, state, outcome, artifacts, evaluators, benchmarks, calibrations, force_lane="production_scale")
            try:
                refreshed = outcome_loop_module().refresh_control(project_root, loop, portable)
            except Exception as exc:
                raise DirectorError(getattr(exc, "code", "E_LOOP"), f"outcome loop control refresh failed: {exc}") from exc
            write_json(loop_path, refreshed)
            state["history"].append({"event": "outcome_control_promoted_after_candidate", "execution_lane": "production_scale"})
        else:
            raise DirectorError("E_PHASE", f"control stage cannot bind loop phase {phase!r}")
        state["stage"] = "loop"
        state["artifacts"]["outcome_control_state"] = relative(project_root, base / "runtime/outcome-control-state.json")
        if portable["execution_lane"] == "production_scale":
            state["artifacts"]["scale_authorization"] = relative(project_root, base / "runtime/scale-authorization.json")
        state = save_state(project_root, state)
        return advance(project_root, objective_id)

    if stage == "loop":
        loop_path = base / "outcome-loop.json"
        loop = obj(read_json(loop_path, "outcome loop"), "outcome loop")
        phase = loop.get("phase")
        if phase == "accepted":
            state["stage"] = "accepted"
            state["next_action"] = {"action": "complete", "stage": "accepted", "candidate_id": loop.get("acceptance", {}).get("candidate_id"), "receipt_sha256": loop.get("acceptance", {}).get("receipt_sha256")}
            state["history"].append({"event": "objective_accepted"})
            return save_state(project_root, state)
        if phase == "reality":
            template = obj(obj(loop.get("next_action"), "loop.next_action").get("request_template"), "reality request template")
            request_path = base / "runtime/reality-request.json"; receipt_path = base / "runtime/reality-receipt.json"
            write_json(request_path, template)
            try: receipt = reality_module().accept(project_root, template)
            except Exception as exc: raise DirectorError(getattr(exc, "code", "E_REALITY"), f"reality acceptance failed: {exc}") from exc
            write_json(receipt_path, receipt)
            try: updated_loop = outcome_loop_module().record_reality(project_root, loop, relative(project_root, receipt_path))
            except Exception as exc: raise DirectorError(getattr(exc, "code", "E_LOOP"), f"outcome loop rejected reality receipt: {exc}") from exc
            write_json(loop_path, updated_loop)
            finalize_mission_acceptance(project_root, objective_id, updated_loop, receipt_path, receipt)
            return advance(project_root, objective_id)
        if phase not in {"build_candidate", "rework", "evaluate"}:
            raise DirectorError("E_PHASE", f"unsupported outcome loop phase: {phase}")

        # Evaluator capability is just-in-time. Until a real candidate exists the
        # organization spends its scarce budget on product reality, not on building
        # and auditing hypothetical judges.
        if phase == "evaluate":
            control_state = obj(read_json(base / "runtime/outcome-control-state.json", "outcome control state"), "outcome control state")
            if control_state.get("execution_lane") == "pilot":
                mission = refresh_mission_state(project_root, objective_id)
                if not mission_control_module().reality_signals(mission)["connected_vertical_slice"]:
                    raise DirectorError("E_FIRST_REALITY", "pilot candidate reached evaluation without connected First Reality evidence")
                state["stage"] = "control"
                state["history"].append({"event": "first_reality_connected", "mission_state_sha256": mission["state_sha256"]})
                state = save_state(project_root, state)
                return advance(project_root, objective_id)
            evaluator_contract = obj(read_json(base / "runtime/evaluator-contract.json", "evaluator contract"), "evaluator contract")
            registry_path = base / "runtime/evaluator-adapter-registry.json"
            try:
                registry = registry_module().build_registry(project_root, evaluator_contract)
            except Exception as exc:
                if getattr(exc, "code", None) != "E_ADAPTER_MISSING":
                    raise DirectorError(getattr(exc, "code", "E_ADAPTER"), f"evaluator registration failed: {exc}") from exc
                state["stage"] = "evaluator_capability"
                state["history"].append({"event": "evaluator_capability_deferred_until_candidate"})
                state = save_state(project_root, state)
                return advance(project_root, objective_id)
            write_json(registry_path, registry)
            state["artifacts"]["evaluator_adapter_registry"] = relative(project_root, registry_path)
            receipts, calibrated = verified_calibrations(project_root, base, evaluator_contract)
            required = {item["evaluator_id"] for item in evaluator_contract.get("evaluators", []) if isinstance(item, Mapping) and item.get("required") is True}
            if not required.issubset(calibrated):
                state["stage"] = "calibration"
                state = save_state(project_root, state)
                return advance(project_root, objective_id)
            control_state = obj(read_json(base / "runtime/outcome-control-state.json", "outcome control state"), "outcome control state")
            if control_state.get("execution_lane") == "pilot":
                state["stage"] = "control"
                state = save_state(project_root, state)
                return advance(project_root, objective_id)

        control_state = obj(read_json(base / "runtime/outcome-control-state.json", "outcome control state"), "outcome control state")
        binding = {"$schema": "company-os.outcome-control-binding.v1", "execution_lane": control_state["execution_lane"], "project_id": control_state["project_id"], "program_version": control_state["program_version"], "work_id": control_state["work_id"], "governed_outcome": control_state["governed_outcome"], "objective_id": control_state["objective_id"], "outcome_contract_path": control_state["outcome"]["path"], "artifact_contract_path": control_state["artifacts"]["path"], "evaluator_contract_path": control_state["evaluators"]["path"], "benchmark_contract_path": control_state["benchmarks"]["path"], "calibration_receipts_path": control_state["calibrations"]["path"], "scale_authorization_path": control_state["scale_authorization"]["path"]}
        manifest_path = compile_current_fabric(project_root, state, binding)
        fabric = obj(read_json(project_root / Path(*manifest_path.split("/")), "outcome fabric"), "outcome fabric")

        if phase in {"build_candidate", "rework"}:
            candidate_id = f"candidate-{int(loop.get('iteration', 0)) + 1:03d}"
            try: candidate = candidate_assembler_module().assemble(project_root, fabric, candidate_id)
            except Exception as exc:
                if getattr(exc, "code", None) != "E_MANIFEST_MISSING": raise DirectorError(getattr(exc, "code", "E_CANDIDATE_HANDOFF"), f"production artifact handoff is invalid: {exc}") from exc
            else:
                candidate_path = base / f"runtime/{candidate_id}.json"; write_json(candidate_path, candidate)
                record_candidate_mission_evidence(project_root, objective_id, candidate)
                try: updated_loop = outcome_loop_module().record_candidate(project_root, loop, candidate)
                except Exception as exc: raise DirectorError(getattr(exc, "code", "E_CANDIDATE"), f"assembled candidate was rejected by outcome loop: {exc}") from exc
                write_json(loop_path, updated_loop)
                state["history"].append({"event": "candidate_auto_assembled", "candidate_id": candidate_id, "candidate_path": relative(project_root, candidate_path)})
                save_state(project_root, state); return advance(project_root, objective_id)

        if phase == "evaluate":
            candidates = loop.get("candidates")
            if not isinstance(candidates, list) or not candidates: raise DirectorError("E_EVALUATION", "evaluate phase has no current candidate")
            candidate_id = text(candidates[-1].get("candidate_id"), "current candidate_id")
            try: batch = evaluation_assembler_module().assemble(project_root, fabric, candidate_id)
            except Exception as exc:
                if getattr(exc, "code", None) != "E_RECEIPT_MISSING": raise DirectorError(getattr(exc, "code", "E_EVALUATION_HANDOFF"), f"independent evaluation handoff is invalid: {exc}") from exc
            else:
                batch_path = base / f"runtime/{candidate_id}-evaluations.json"; write_json(batch_path, batch)
                try: updated_loop = outcome_loop_module().record_evaluations(project_root, loop, batch)
                except Exception as exc: raise DirectorError(getattr(exc, "code", "E_EVALUATION"), f"assembled evaluation batch was rejected by outcome loop: {exc}") from exc
                write_json(loop_path, updated_loop)
                state["history"].append({"event": "evaluations_auto_assembled", "candidate_id": candidate_id, "batch_path": relative(project_root, batch_path)})
                save_state(project_root, state); return advance(project_root, objective_id)

        state["next_action"] = next_execute_fabric(phase, manifest_path, reason=f"The outcome loop is waiting for real {phase} work against the current content bound state.")
        state["next_action"]["loop_state_path"] = relative(project_root, loop_path); state["next_action"]["loop_phase"] = phase; state["next_action"]["loop_next_action"] = loop.get("next_action")
        state["next_action"]["required_handoff"] = "Each production worker must write artifact-manifest.json in its exact write scope." if phase in {"build_candidate", "rework"} else "Each independent evaluator worker must write execution-receipt.json in its exact write scope."
        return save_state(project_root, state)

    if stage == "accepted":
        return state

    raise DirectorError("E_STAGE", f"unsupported director stage: {stage}")


def record_candidate(project_root: Path, objective_id: str, candidate_path: Path) -> dict[str, Any]:
    state = load_state(project_root, objective_id)
    if state.get("stage") != "loop":
        raise DirectorError("E_STAGE", "candidate can only be recorded during the outcome loop")
    base = workspace(project_root, objective_id)
    loop_path = base / "outcome-loop.json"
    loop = obj(read_json(loop_path, "outcome loop"), "outcome loop")
    candidate = obj(read_json(candidate_path, "candidate"), "candidate")
    try:
        updated = outcome_loop_module().record_candidate(project_root, loop, candidate)
    except Exception as exc:
        raise DirectorError(getattr(exc, "code", "E_CANDIDATE"), f"candidate rejected: {exc}") from exc
    write_json(loop_path, updated)
    state["history"].append({"event": "candidate_recorded", "candidate_id": candidate.get("candidate_id")})
    save_state(project_root, state)
    return advance(project_root, objective_id)


def record_evaluations(project_root: Path, objective_id: str, batch_path: Path) -> dict[str, Any]:
    state = load_state(project_root, objective_id)
    if state.get("stage") != "loop":
        raise DirectorError("E_STAGE", "evaluations can only be recorded during the outcome loop")
    base = workspace(project_root, objective_id)
    loop_path = base / "outcome-loop.json"
    loop = obj(read_json(loop_path, "outcome loop"), "outcome loop")
    batch = obj(read_json(batch_path, "evaluation batch"), "evaluation batch")
    try:
        updated = outcome_loop_module().record_evaluations(project_root, loop, batch)
    except Exception as exc:
        raise DirectorError(getattr(exc, "code", "E_EVALUATION"), f"evaluation batch rejected: {exc}") from exc
    write_json(loop_path, updated)
    state["history"].append({"event": "evaluations_recorded", "candidate_id": batch.get("candidate_id")})
    save_state(project_root, state)
    return advance(project_root, objective_id)


def status(project_root: Path, objective_id: str) -> dict[str, Any]:
    state = load_state(project_root, objective_id)
    mission = load_mission_state(project_root, objective_id)
    return {
        "objective_id": state["objective_id"],
        "original_objective": state["original_objective"],
        "stage": state["stage"],
        "next_action": state["next_action"],
        "director_sha256": state["director_sha256"],
        "mission_execution": {
            "status": mission["status"],
            "mission_class": mission["mission_class"],
            "reality": mission_control_module().reality_signals(mission),
            "governor_decision": mission["governor_decision"],
            "deadline_status": mission["deadline_status"],
            "checkpoint": mission.get("checkpoint"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    start_parser = sub.add_parser("start")
    start_parser.add_argument("--project-root", type=Path, required=True)
    start_parser.add_argument("--objective-id", required=True)
    start_parser.add_argument("--objective", required=True)
    advance_parser = sub.add_parser("advance")
    advance_parser.add_argument("--project-root", type=Path, required=True)
    advance_parser.add_argument("--objective-id", required=True)
    status_parser = sub.add_parser("status")
    status_parser.add_argument("--project-root", type=Path, required=True)
    status_parser.add_argument("--objective-id", required=True)
    candidate_parser = sub.add_parser("record-candidate")
    candidate_parser.add_argument("--project-root", type=Path, required=True)
    candidate_parser.add_argument("--objective-id", required=True)
    candidate_parser.add_argument("--candidate", type=Path, required=True)
    evaluation_parser = sub.add_parser("record-evaluations")
    evaluation_parser.add_argument("--project-root", type=Path, required=True)
    evaluation_parser.add_argument("--objective-id", required=True)
    evaluation_parser.add_argument("--batch", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "start":
            result = start(args.project_root, args.objective_id, args.objective)
        elif args.command == "advance":
            result = advance(args.project_root, args.objective_id)
        elif args.command == "status":
            print(json.dumps({"ok": True, **status(args.project_root, args.objective_id)}, sort_keys=True))
            return 0
        elif args.command == "record-candidate":
            result = record_candidate(args.project_root, args.objective_id, args.candidate)
        else:
            result = record_evaluations(args.project_root, args.objective_id, args.batch)
        print(
            json.dumps(
                {
                    "ok": True,
                    "objective_id": result["objective_id"],
                    "stage": result["stage"],
                    "next_action": result["next_action"],
                    "director_sha256": result["director_sha256"],
                },
                sort_keys=True,
            )
        )
        return 0
    except DirectorError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "error": exc.message}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
