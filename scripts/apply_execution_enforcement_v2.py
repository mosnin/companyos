#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, found {count}: {old[:90]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_director() -> None:
    path = ROOT / "skills/company-os/direct-outcome/scripts/direct_outcome.py"
    replace_once(
        path,
        '''def reality_module():
    return load_module("accept-outcome-reality/scripts/accept_reality.py", "company_os_director_reality")


def control_store_module():
''',
        '''def reality_module():
    return load_module("accept-outcome-reality/scripts/accept_reality.py", "company_os_director_reality")


def artifact_observation_module():
    return load_module("define-outcome-artifacts/scripts/compile_artifact_observations.py", "company_os_director_artifacts")


def mission_control_module():
    return load_module("mission-execution-control/scripts/mission_control.py", "company_os_director_mission_control")


def control_store_module():
''',
    )
    replace_once(
        path,
        '''def state_path(project_root: Path, objective_id: str) -> Path:
    return workspace(project_root, objective_id) / "director-state.json"


def seal(state: Mapping[str, Any]) -> dict[str, Any]:
''',
        '''def state_path(project_root: Path, objective_id: str) -> Path:
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
                "label": raw["label"],
                "required": True,
                "modalities": list(raw.get("modalities", [])),
                "observation_methods": list(raw.get("observation_methods", [])),
                "required_evidence": list(raw.get("required_evidence", [])),
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
    for observation in candidate.get("observations", []):
        if not isinstance(observation, Mapping) or observation.get("capability_id") not in known:
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
''',
    )
    replace_once(
        path,
        '''    discovery_fabric = receipt["paths"]["discovery_fabric"]
    state = {
''',
        '''    discovery_fabric = receipt["paths"]["discovery_fabric"]
    mission = mission_control_module().initialize_state(objective_id, objective)
    save_mission_state(project_root, mission)
    state = {
''',
    )
    replace_once(
        path,
        '''            "discovery_fabric": discovery_fabric,
        },
''',
        '''            "discovery_fabric": discovery_fabric,
            "mission_execution_state": relative(project_root, mission_state_path(project_root, objective_id)),
        },
''',
    )
    replace_once(
        path,
        '''    return save_state(project_root, state)


def proposal_paths(base: Path) -> list[Path]:
''',
        '''    saved = save_state(project_root, state)
    saved["next_action"]["mission_control"] = mission_binding(project_root, objective_id)
    return save_state(project_root, saved)


def proposal_paths(base: Path) -> list[Path]:
''',
    )
    replace_once(
        path,
        '''    calibrations: list[dict[str, Any]],
    *,
    force_lane: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
''',
        '''    calibrations: list[dict[str, Any]],
    *,
    force_lane: str | None = None,
    artifact_contract_file: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
''',
    )
    replace_once(
        path,
        '''    binding = {
        "$schema": "company-os.outcome-control-binding.v1",
''',
        '''    active_artifact_contract = artifact_contract_file or (runtime / "artifact-contract.json")
    binding = {
        "$schema": "company-os.outcome-control-binding.v1",
''',
    )
    replace_once(
        path,
        '''        "artifact_contract_path": relative(project_root, runtime / "artifact-contract.json"),
''',
        '''        "artifact_contract_path": relative(project_root, active_artifact_contract),
''',
    )
    replace_once(
        path,
        '''        "$schema": "company-os.outcome-organization-request.v1",
        "project_id": text(instance.get("project_id"), "project_id"),
''',
        '''        "$schema": "company-os.outcome-organization-request.v1",
        "mission_control": mission_binding(project_root, state["objective_id"]),
        "project_id": text(instance.get("project_id"), "project_id"),
''',
    )
    replace_once(
        path,
        '''    loop_path = base / "outcome-loop.json"
    request = organization_request(project_root, state, binding)
    request_path = base / "runtime/outcome-organization-request.json"
''',
        '''    loop_path = base / "outcome-loop.json"
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
''',
    )
    replace_once(
        path,
        '''            state["next_action"] = next_execute_fabric(
                "discovery",
                state["artifacts"]["discovery_fabric"],
                reason="Discovery proposals are still missing: " + ", ".join(missing),
            )
            return save_state(project_root, state)
''',
        '''            admission = admit_mission_work(
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
''',
    )
    replace_once(
        path,
        '''        stack_module().materialize(
            base / "measurable-outcome-request.json",
            base / "runtime",
        )
        state["stage"] = "control"
''',
        '''        stack_module().materialize(
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
''',
    )
    replace_once(
        path,
        '''                "benchmark_contract": relative(project_root, base / "runtime/benchmark-contract.json"),
            }
''',
        '''                "benchmark_contract": relative(project_root, base / "runtime/benchmark-contract.json"),
                "first_reality_contract": relative(project_root, first_reality_path),
                "first_reality_artifact_contract": relative(project_root, first_artifact_path),
            }
''',
    )
    replace_once(
        path,
        '''            binding, portable = build_outcome_control(project_root, state, outcome, artifacts, evaluators, benchmarks, [], force_lane="pilot")
''',
        '''            pilot_artifacts = obj(read_json(base / "runtime/first-reality-artifact-contract.json", "first reality artifact contract"), "first reality artifact contract")
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
''',
    )
    replace_once(
        path,
        '''                candidate_path = base / f"runtime/{candidate_id}.json"; write_json(candidate_path, candidate)
                try: updated_loop = outcome_loop_module().record_candidate(project_root, loop, candidate)
''',
        '''                candidate_path = base / f"runtime/{candidate_id}.json"; write_json(candidate_path, candidate)
                record_candidate_mission_evidence(project_root, objective_id, candidate)
                try: updated_loop = outcome_loop_module().record_candidate(project_root, loop, candidate)
''',
    )
    replace_once(
        path,
        '''            write_json(loop_path, updated_loop)
            return advance(project_root, objective_id)
''',
        '''            write_json(loop_path, updated_loop)
            finalize_mission_acceptance(project_root, objective_id, updated_loop, receipt_path, receipt)
            return advance(project_root, objective_id)
''',
    )
    replace_once(
        path,
        '''    return {
        "objective_id": state["objective_id"],
        "original_objective": state["original_objective"],
        "stage": state["stage"],
        "next_action": state["next_action"],
        "director_sha256": state["director_sha256"],
    }
''',
        '''    mission = load_mission_state(project_root, objective_id)
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
''',
    )


def patch_organization() -> None:
    path = ROOT / "skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py"
    replace_once(
        path,
        '''    control = _validate_outcome_control(_object(request.get("outcome_control"), "outcome_control"), project_id=project_id, program_version=program_version, work_id=work_id, governed_outcome=governed_outcome, objective_id=objective_id)
    engineering_module = _engineering_module()
''',
        '''    control = _validate_outcome_control(_object(request.get("outcome_control"), "outcome_control"), project_id=project_id, program_version=program_version, work_id=work_id, governed_outcome=governed_outcome, objective_id=objective_id)
    mission_control = dict(_object(request.get("mission_control"), "mission_control"))
    admission = dict(_object(request.get("work_admission"), "work_admission"))
    if admission.get("admitted") is not True:
        raise OrganizationError("E_GOVERNOR", "current work admission is not accepted")
    if admission.get("mission_state_sha256") != mission_control.get("state_sha256"):
        raise OrganizationError("E_GOVERNOR", "work admission binds a stale mission state")
    if admission.get("governor_decision_sha256") != mission_control.get("governor_decision_sha256"):
        raise OrganizationError("E_GOVERNOR", "work admission binds a stale governor decision")
    expected_work_class = "evaluation" if state.get("phase") == "evaluate" else "repair" if state.get("phase") == "rework" else "implementation"
    if admission.get("work_class") != expected_work_class:
        raise OrganizationError("E_GOVERNOR", f"{state.get('phase')} requires work class {expected_work_class}")
    if expected_work_class in set(mission_control.get("paused_work_classes", [])):
        raise OrganizationError("E_GOVERNOR", f"work class {expected_work_class} is paused")
    engineering_module = _engineering_module()
''',
    )
    replace_once(
        path,
        '''            worker_task += " When materialized, write the canonical artifact handoff at " + artifact_manifest_path + ". Preserve these exact immutable bindings: " + json.dumps(artifact_manifest_binding, sort_keys=True) + ". Add an artifacts array containing each actual artifact_id, artifact_class_id, project-relative path, and exact sha256. A prose report is not a handoff."
''',
        '''            worker_task += " When materialized, write the canonical artifact handoff at " + artifact_manifest_path + ". Preserve these exact immutable bindings: " + json.dumps(artifact_manifest_binding, sort_keys=True) + ". Add an artifacts array containing each actual artifact_id, artifact_class_id, project-relative path, and exact sha256. Also add an observations array with runtime_observed and journey_connected receipts containing capability_id, project-relative evidence path, exact sha256, and observation_kind. The first-reality candidate is incomplete until the real artifact runs and one connected user journey is observed. A prose report is not a handoff."
''',
    )
    replace_once(
        path,
        '''        workers = [{"id": f"{manager_id}-worker-01", "model": "gpt-5.6-luna", "task": worker_task, "acceptance": acceptance, "write_scope": worker_write_scope, "risk": "medium", "budget": dict(manager_budget), "outcome_context": outcome_context, "engineering_execution_contract": worker_engineering, "stop_condition": stop_condition, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha}]
        managers.append({"id": manager_id, "model": "gpt-5.6-sol", "outcome": lane["mandate"], "acceptance": acceptance, "phase_ids": PHASES, "budget": dict(manager_budget), "write_scope": [resource_scope], "artifact_classes": lane["artifact_classes"], "engineering_execution_contract": manager_engineering, "workers": workers, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha})
''',
        '''        work_class = "evaluation" if state.get("phase") == "evaluate" else "repair" if state.get("phase") == "rework" else "implementation"
        outcome_context["mission_control"] = mission_control
        outcome_context["work_admission"] = admission
        workers = [{"id": f"{manager_id}-worker-01", "model": "gpt-5.6-luna", "task": worker_task, "acceptance": acceptance, "write_scope": worker_write_scope, "risk": "medium", "budget": dict(manager_budget), "work_class": work_class, "outcome_context": outcome_context, "engineering_execution_contract": worker_engineering, "stop_condition": stop_condition, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha}]
        managers.append({"id": manager_id, "model": "gpt-5.6-sol", "outcome": lane["mandate"], "acceptance": acceptance, "phase_ids": PHASES, "budget": dict(manager_budget), "work_class": work_class, "write_scope": [resource_scope], "artifact_classes": lane["artifact_classes"], "engineering_execution_contract": manager_engineering, "workers": workers, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha})
''',
    )
    replace_once(
        path,
        '''    return {"program_id": project_id, "topology_mode": TOPOLOGY_MODE, "engineering_execution_contract": master_engineering,
''',
        '''    return {"program_id": project_id, "topology_mode": TOPOLOGY_MODE, "mission_control": mission_control, "work_admission": admission, "engineering_execution_contract": master_engineering,
''',
    )


def patch_candidate_assembler() -> None:
    path = ROOT / "skills/company-os/assemble-outcome-candidate/scripts/assemble_candidate.py"
    replace_once(
        path,
        '''    return sorted(artifacts, key=lambda item: item["artifact_id"]), {
        "path": worker["manifest_path"],
        "file_sha256": digest(manifest),
        "lane_id": worker["lane_id"],
        "production_actor_id": worker["worker_id"],
    }
''',
        '''    observations = []
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
        })
    return sorted(artifacts, key=lambda item: item["artifact_id"]), {
        "path": worker["manifest_path"],
        "file_sha256": digest(manifest),
        "lane_id": worker["lane_id"],
        "production_actor_id": worker["worker_id"],
    }, sorted(observations, key=lambda item: (item["capability_id"], item["kind"], item["path"]))
''',
    )
    replace_once(
        path,
        '''    source_manifests = []
    for worker in production_workers(fabric):
''',
        '''    source_manifests = []
    all_observations = []
    for worker in production_workers(fabric):
''',
    )
    replace_once(
        path,
        '''        artifacts, manifest_binding = validate_lane_manifest(
''',
        '''        artifacts, manifest_binding, observations = validate_lane_manifest(
''',
    )
    replace_once(
        path,
        '''        production_actor_ids.append(worker["worker_id"])
        source_manifests.append(manifest_binding)
''',
        '''        production_actor_ids.append(worker["worker_id"])
        source_manifests.append(manifest_binding)
        all_observations.extend(observations)
''',
    )
    replace_once(
        path,
        '''    if missing:
        raise CandidateAssemblyError(
            "E_ARTIFACT",
            "candidate is missing required artifact classes: " + ", ".join(missing),
        )
    return {
''',
        '''    if missing:
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
''',
    )
    replace_once(
        path,
        '''        "artifacts": sorted(all_artifacts, key=lambda item: item["artifact_id"]),
    }
''',
        '''        "artifacts": sorted(all_artifacts, key=lambda item: item["artifact_id"]),
        "observations": sorted(all_observations, key=lambda item: (item["capability_id"], item["kind"], item["path"])),
    }
''',
    )


def patch_bootstrap() -> None:
    path = ROOT / "skills/company-os/bootstrap-outcome/scripts/bootstrap_outcome.py"
    replace_once(
        path,
        '''def manager_budget() -> dict[str, Any]:
    return {"time_minutes": 22.5, "token_limit": 6000, "cost_usd": 6.0, "max_concurrency": 1, "max_retries": 1}
''',
        '''def manager_budget() -> dict[str, Any]:
    return {"time_minutes": 10.0, "token_limit": 3000, "cost_usd": 3.0, "max_concurrency": 1, "max_retries": 1}
''',
    )
    replace_once(
        path,
        '''    managers = []
    for index, (lane_id, manager_outcome, agenda, section) in enumerate(lanes, 1):
''',
        '''    managers = []
    for index, (lane_id, manager_outcome, agenda, section) in enumerate(lanes, 1):
''',
    )
    replace_once(
        path,
        '''    manifest = {
        "program_id": project_id,
''',
        '''    spike_scope = f"{base}/reality-spike"
    spike_worker = {
        "id": "outcome-reality-spike-manager-worker-01",
        "model": "gpt-5.6-luna",
        "task": (
            f"Start a reversible reality spike for the exact objective {objective!r} immediately while discovery runs. "
            "Inspect the repository, identify the task archetype, make the smallest real product mutation, run or render it, and observe actual behavior. "
            "Prefer supplied repositories, SDKs, frameworks, and existing project structure. Do not replace a supplied implementation without a failed integration attempt. "
            f"Write a receipt at {spike_scope}/reality-spike-receipt.json with schema company-os.reality-spike-receipt.v1, exact product artifact paths and sha256 values, commands executed, runtime result, observation evidence paths and sha256 values, and unresolved blockers. "
            "Research only a live implementation blocker. A plan or report without product mutation and runtime evidence fails this lane."
        ),
        "acceptance": [
            "At least one real product file is created or changed",
            "At least one build, runtime, browser, simulator, workflow, or equivalent execution command is run",
            "The exact artifact and observation evidence is content addressed",
            f"The receipt exists at {spike_scope}/reality-spike-receipt.json",
        ],
        "write_scope": ["app", "src", "public", "tests", "scripts", "prisma", "package.json", spike_scope],
        "risk": "low",
        "budget": {"time_minutes": 20.0, "token_limit": 6000, "cost_usd": 6.0, "max_concurrency": 1, "max_retries": 1},
        "work_class": "implementation",
        "outcome_context": worker_context(state, objective, "Create the first running artifact while focused discovery proceeds", constraints, non_goals),
        "stop_condition": "A real artifact runs or renders with exact evidence, or a concrete environment blocker is proven.",
    }
    managers.append({
        "id": "outcome-reality-spike-manager",
        "model": "gpt-5.6-sol",
        "outcome": "Create the first reversible running artifact in parallel with discovery.",
        "acceptance": spike_worker["acceptance"],
        "phase_ids": PHASES,
        "budget": dict(spike_worker["budget"]),
        "work_class": "implementation",
        "write_scope": list(spike_worker["write_scope"]),
        "workers": [spike_worker],
    })
    manifest = {
        "program_id": project_id,
''',
    )
    replace_once(
        path,
        '''        "max_managers": 2,
        "max_manager_concurrency": 2,
        "max_workers_per_manager": 1,
        "max_total_workers": 2,
''',
        '''        "max_managers": 3,
        "max_manager_concurrency": 3,
        "max_workers_per_manager": 1,
        "max_total_workers": 3,
''',
    )
    replace_once(
        path,
        '''        "budget": {"time_minutes": 45.0, "token_limit": 12000, "cost_usd": 12.0, "max_concurrency": 2, "max_retries": 1},
''',
        '''        "budget": {"time_minutes": 40.0, "token_limit": 12000, "cost_usd": 12.0, "max_concurrency": 3, "max_retries": 1},
''',
    )


def patch_calibration() -> None:
    path = ROOT / "skills/company-os/calibrate-outcome-stack/scripts/compile_calibration_fabric.py"
    replace_once(path, "MAX_EVALUATORS_PER_BATCH = 2\n", "MAX_EVALUATORS_PER_BATCH = 1\n")
    replace_once(
        path,
        '''    fabric = {
        "program_id": project_id,
''',
        '''    mission_path = project_root / ".company-os" / "outcomes" / objective_id / "mission-execution-state.json"
    remaining_minutes = 60.0
    if mission_path.is_file():
        try:
            mission = read_json(mission_path, "mission execution state")
            from datetime import datetime, timezone
            expires_at = datetime.fromisoformat(str(mission["expires_at"]).replace("Z", "+00:00"))
            remaining_minutes = max(10.0, (expires_at - datetime.now(timezone.utc)).total_seconds() / 60.0)
        except Exception:
            remaining_minutes = 60.0
    calibration_budget_minutes = max(10.0, min(30.0, remaining_minutes * 0.10))
    per_manager_minutes = calibration_budget_minutes / max(1, len(managers))
    per_manager_tokens = max(3000, int(18000 / max(1, len(managers))))
    for manager in managers:
        manager["budget"] = {
            "time_minutes": per_manager_minutes,
            "token_limit": per_manager_tokens,
            "cost_usd": max(3.0, 18.0 / max(1, len(managers))),
            "max_concurrency": 1,
            "max_retries": 1,
        }
        for worker in manager["workers"]:
            worker["budget"] = {
                "time_minutes": per_manager_minutes / 3.0,
                "token_limit": max(1000, per_manager_tokens // 3),
                "cost_usd": max(1.0, 6.0 / max(1, len(managers))),
                "max_concurrency": 1,
                "max_retries": 0,
            }
    fabric = {
        "program_id": project_id,
''',
    )
    replace_once(
        path,
        '''        "budget": {
            "time_minutes": 360.0,
            "token_limit": 90000,
            "cost_usd": 90.0,
            "max_concurrency": len(managers),
            "max_retries": 1,
        },
''',
        '''        "budget": {
            "time_minutes": calibration_budget_minutes,
            "token_limit": 18000,
            "cost_usd": 18.0,
            "max_concurrency": len(managers),
            "max_retries": 1,
        },
''',
    )


def main() -> None:
    patch_director()
    patch_organization()
    patch_candidate_assembler()
    patch_bootstrap()
    patch_calibration()
    print("execution enforcement v2 integration applied")


if __name__ == "__main__":
    main()
