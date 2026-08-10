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


def reality_module():
    return load_module("accept-outcome-reality/scripts/accept_reality.py", "company_os_director_reality")


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
    return save_state(project_root, state)


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
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = workspace(project_root, state["objective_id"])
    runtime = base / "runtime"
    scale = scale_module().authorize(outcome, artifacts, evaluators, benchmarks, calibrations)
    if scale.get("authorized") is not True:
        raise DirectorError(
            "E_SCALE",
            "outcome stack is not scale authorized: " + json.dumps(scale.get("blockers", []), sort_keys=True),
        )
    scale_path = runtime / "scale-authorization.json"
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
    required_artifact_count = sum(
        1
        for item in artifacts.get("artifact_classes", [])
        if isinstance(item, Mapping) and item.get("required") is True
    )
    lane = "pilot" if 1 <= required_artifact_count <= 2 else "production_scale"
    work_id = f"outcome-delivery-{slug(state['objective_id'])}"
    calibrations_path = runtime / "calibrations.json"
    write_json(calibrations_path, calibrations)
    binding = {
        "$schema": "company-os.outcome-control-binding.v1",
        "execution_lane": lane,
        "project_id": project_id,
        "program_version": program_version,
        "work_id": work_id,
        "governed_outcome": state["original_objective"],
        "objective_id": state["objective_id"],
        "outcome_contract_path": relative(project_root, base / "measurable-outcome-contract.json"),
        "artifact_contract_path": relative(project_root, runtime / "artifact-contract.json"),
        "evaluator_contract_path": relative(project_root, runtime / "evaluator-contract.json"),
        "benchmark_contract_path": relative(project_root, runtime / "benchmark-contract.json"),
        "calibration_receipts_path": relative(project_root, calibrations_path),
        "scale_authorization_path": (
            None
            if lane == "pilot"
            else relative(project_root, scale_path)
        ),
    }
    manager_count = max(1, min(required_artifact_count, 2))
    probe_manifest = {
        "outcome": state["original_objective"],
        "max_managers": manager_count,
        "max_manager_concurrency": manager_count,
        "max_workers_per_manager": 1,
        "max_total_workers": manager_count,
        "managers": [{"workers": [{}]} for _ in range(manager_count)],
        "outcome_control": binding,
    }
    try:
        portable = outcome_control_module().validate_manifest_binding(
            project_root=project_root,
            manifest=probe_manifest,
            project_id=project_id,
            program_version=program_version,
            work_id=work_id,
            governed_outcome=state["original_objective"],
        )
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
    request = organization_request(project_root, state, binding)
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
            state["next_action"] = next_execute_fabric(
                "discovery",
                state["artifacts"]["discovery_fabric"],
                reason="Discovery proposals are still missing: " + ", ".join(missing),
            )
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
        state["stage"] = "evaluator_capability"
        state["artifacts"].update(
            {
                "measurable_outcome_request": relative(project_root, base / "measurable-outcome-request.json"),
                "measurable_outcome_contract": relative(project_root, base / "measurable-outcome-contract.json"),
                "artifact_contract": relative(project_root, base / "runtime/artifact-contract.json"),
                "evaluator_contract": relative(project_root, base / "runtime/evaluator-contract.json"),
                "benchmark_contract": relative(project_root, base / "runtime/benchmark-contract.json"),
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
        calibrations, calibrated = verified_calibrations(project_root, base, evaluators)
        required = {
            item["evaluator_id"]
            for item in evaluators.get("evaluators", [])
            if isinstance(item, Mapping) and item.get("required") is True
        }
        if not required.issubset(calibrated):
            state["stage"] = "calibration"
            return save_state(project_root, state)
        binding, portable = build_outcome_control(
            project_root,
            state,
            outcome,
            artifacts,
            evaluators,
            benchmarks,
            calibrations,
        )
        loop_path = base / "outcome-loop.json"
        loop = obj(read_json(loop_path, "outcome loop"), "outcome loop")
        try:
            bound_loop = outcome_loop_module().bind_control(project_root, loop, portable)
        except Exception as exc:
            raise DirectorError(getattr(exc, "code", "E_LOOP"), f"outcome loop control binding failed: {exc}") from exc
        write_json(loop_path, bound_loop)
        state["stage"] = "loop"
        state["artifacts"]["outcome_control_state"] = relative(project_root, base / "runtime/outcome-control-state.json")
        state["artifacts"]["scale_authorization"] = relative(project_root, base / "runtime/scale-authorization.json")
        state["history"].append({"event": "outcome_control_bound", "execution_lane": portable["execution_lane"]})
        state = save_state(project_root, state)
        return advance(project_root, objective_id)

    if stage == "loop":
        loop_path = base / "outcome-loop.json"
        loop = obj(read_json(loop_path, "outcome loop"), "outcome loop")
        phase = loop.get("phase")
        if phase == "accepted":
            state["stage"] = "accepted"
            state["next_action"] = {
                "action": "complete",
                "stage": "accepted",
                "candidate_id": loop.get("acceptance", {}).get("candidate_id"),
                "receipt_sha256": loop.get("acceptance", {}).get("receipt_sha256"),
            }
            state["history"].append({"event": "objective_accepted"})
            return save_state(project_root, state)
        if phase == "reality":
            template = obj(obj(loop.get("next_action"), "loop.next_action").get("request_template"), "reality request template")
            request_path = base / "runtime/reality-request.json"
            receipt_path = base / "runtime/reality-receipt.json"
            write_json(request_path, template)
            try:
                receipt = reality_module().accept(project_root, template)
            except Exception as exc:
                raise DirectorError(getattr(exc, "code", "E_REALITY"), f"reality acceptance failed: {exc}") from exc
            write_json(receipt_path, receipt)
            try:
                updated_loop = outcome_loop_module().record_reality(
                    project_root,
                    loop,
                    relative(project_root, receipt_path),
                )
            except Exception as exc:
                raise DirectorError(getattr(exc, "code", "E_LOOP"), f"outcome loop rejected reality receipt: {exc}") from exc
            write_json(loop_path, updated_loop)
            return advance(project_root, objective_id)
        if phase in {"build_candidate", "rework", "evaluate"}:
            control_state = obj(
                read_json(base / "runtime/outcome-control-state.json", "outcome control state"),
                "outcome control state",
            )
            binding = {
                "$schema": "company-os.outcome-control-binding.v1",
                "execution_lane": control_state["execution_lane"],
                "project_id": control_state["project_id"],
                "program_version": control_state["program_version"],
                "work_id": control_state["work_id"],
                "governed_outcome": control_state["governed_outcome"],
                "objective_id": control_state["objective_id"],
                "outcome_contract_path": control_state["outcome"]["path"],
                "artifact_contract_path": control_state["artifacts"]["path"],
                "evaluator_contract_path": control_state["evaluators"]["path"],
                "benchmark_contract_path": control_state["benchmarks"]["path"],
                "calibration_receipts_path": control_state["calibrations"]["path"],
                "scale_authorization_path": control_state["scale_authorization"]["path"],
            }
            manifest_path = compile_current_fabric(project_root, state, binding)
            state["next_action"] = next_execute_fabric(
                phase,
                manifest_path,
                reason=f"The outcome loop is waiting for real {phase} work against the current content bound state.",
            )
            state["next_action"]["loop_state_path"] = relative(project_root, loop_path)
            state["next_action"]["loop_phase"] = phase
            state["next_action"]["loop_next_action"] = loop.get("next_action")
            return save_state(project_root, state)
        raise DirectorError("E_PHASE", f"unsupported outcome loop phase: {phase}")

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
    return {
        "objective_id": state["objective_id"],
        "original_objective": state["original_objective"],
        "stage": state["stage"],
        "next_action": state["next_action"],
        "director_sha256": state["director_sha256"],
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
