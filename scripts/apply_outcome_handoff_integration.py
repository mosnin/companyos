#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_organization() -> None:
    path = Path("skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py")
    text = path.read_text(encoding="utf-8")
    marker = '''        if preserve_dimensions and phase == "rework":
            worker_task += " Preserve already passing dimensions: " + ", ".join(preserve_dimensions) + "."
        workers = [{
'''
    insertion = '''        if preserve_dimensions and phase == "rework":
            worker_task += " Preserve already passing dimensions: " + ", ".join(preserve_dimensions) + "."
        if phase in {"build_candidate", "rework"}:
            artifact_scope = f"{resource_scope}/artifact"
            artifact_manifest_path = f"{artifact_scope}/artifact-manifest.json"
            artifact_manifest_binding = {
                "$schema": "company-os.outcome-lane-artifact-manifest.v1",
                "schema_version": 1,
                "objective_id": state["objective_id"],
                "outcome_loop_state_sha256": state["state_sha256"],
                "organization_sha256": digest(state["organization_plan"]),
                "lane_id": lane["lane_id"],
                "lane_sha256": lane_sha,
                "production_actor_id": f"{manager_id}-worker-01",
            }
            worker_task += (
                " When the real artifact work is materialized, write the canonical lane artifact manifest at "
                + artifact_manifest_path
                + ". The manifest must use company-os.outcome-lane-artifact-manifest.v1 and preserve these exact immutable bindings: "
                + json.dumps(artifact_manifest_binding, sort_keys=True)
                + ". Add an artifacts array containing every materialized artifact with artifact_id, artifact_class_id, project-relative path, and exact sha256. Every artifact path must remain inside your single write scope. The manifest is the only production handoff accepted by the outcome director; a prose completion report is insufficient."
            )
        workers = [{
'''
    if marker not in text:
        raise SystemExit("production worker insertion marker was not found")
    text = text.replace(marker, insertion, 1)
    path.write_text(text, encoding="utf-8")


def patch_director() -> None:
    path = Path("skills/company-os/direct-outcome/scripts/direct_outcome.py")
    text = path.read_text(encoding="utf-8")
    marker = '''def organization_module():
    return load_module("compile-outcome-organization/scripts/compile_outcome_organization.py", "company_os_director_organization")


def reality_module():
'''
    insertion = '''def organization_module():
    return load_module("compile-outcome-organization/scripts/compile_outcome_organization.py", "company_os_director_organization")


def candidate_assembler_module():
    return load_module("assemble-outcome-candidate/scripts/assemble_candidate.py", "company_os_director_candidate_assembler")


def evaluation_assembler_module():
    return load_module("assemble-outcome-evaluations/scripts/assemble_evaluations.py", "company_os_director_evaluation_assembler")


def reality_module():
'''
    if marker not in text:
        raise SystemExit("director module loader marker was not found")
    text = text.replace(marker, insertion, 1)

    start_marker = '''        if phase in {"build_candidate", "rework", "evaluate"}:
            control_state = obj(
'''
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit("director loop execution block start was not found")
    end_marker = '''            return save_state(project_root, state)
        raise DirectorError("E_PHASE", f"unsupported outcome loop phase: {phase}")
'''
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit("director loop execution block end was not found")
    end += len('''            return save_state(project_root, state)
''')
    replacement = '''        if phase in {"build_candidate", "rework", "evaluate"}:
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
            manifest_absolute = project_root / Path(*manifest_path.split("/"))
            fabric = obj(read_json(manifest_absolute, "outcome fabric"), "outcome fabric")

            if phase in {"build_candidate", "rework"}:
                candidate_id = f"candidate-{int(loop.get('iteration', 0)) + 1:03d}"
                try:
                    candidate = candidate_assembler_module().assemble(
                        project_root,
                        fabric,
                        candidate_id,
                    )
                except Exception as exc:
                    if getattr(exc, "code", None) != "E_MANIFEST_MISSING":
                        raise DirectorError(
                            getattr(exc, "code", "E_CANDIDATE_HANDOFF"),
                            f"production artifact handoff is invalid: {exc}",
                        ) from exc
                else:
                    candidate_path = base / f"runtime/{candidate_id}.json"
                    write_json(candidate_path, candidate)
                    try:
                        updated_loop = outcome_loop_module().record_candidate(
                            project_root,
                            loop,
                            candidate,
                        )
                    except Exception as exc:
                        raise DirectorError(
                            getattr(exc, "code", "E_CANDIDATE"),
                            f"assembled candidate was rejected by outcome loop: {exc}",
                        ) from exc
                    write_json(loop_path, updated_loop)
                    state["history"].append(
                        {
                            "event": "candidate_auto_assembled",
                            "candidate_id": candidate_id,
                            "candidate_path": relative(project_root, candidate_path),
                        }
                    )
                    save_state(project_root, state)
                    return advance(project_root, objective_id)

            if phase == "evaluate":
                candidates = loop.get("candidates")
                if not isinstance(candidates, list) or not candidates:
                    raise DirectorError("E_EVALUATION", "evaluate phase has no current candidate")
                candidate_id = text(candidates[-1].get("candidate_id"), "current candidate_id")
                try:
                    batch = evaluation_assembler_module().assemble(
                        project_root,
                        fabric,
                        candidate_id,
                    )
                except Exception as exc:
                    if getattr(exc, "code", None) != "E_RECEIPT_MISSING":
                        raise DirectorError(
                            getattr(exc, "code", "E_EVALUATION_HANDOFF"),
                            f"independent evaluation handoff is invalid: {exc}",
                        ) from exc
                else:
                    batch_path = base / f"runtime/{candidate_id}-evaluations.json"
                    write_json(batch_path, batch)
                    try:
                        updated_loop = outcome_loop_module().record_evaluations(
                            project_root,
                            loop,
                            batch,
                        )
                    except Exception as exc:
                        raise DirectorError(
                            getattr(exc, "code", "E_EVALUATION"),
                            f"assembled evaluation batch was rejected by outcome loop: {exc}",
                        ) from exc
                    write_json(loop_path, updated_loop)
                    state["history"].append(
                        {
                            "event": "evaluations_auto_assembled",
                            "candidate_id": candidate_id,
                            "batch_path": relative(project_root, batch_path),
                        }
                    )
                    save_state(project_root, state)
                    return advance(project_root, objective_id)

            state["next_action"] = next_execute_fabric(
                phase,
                manifest_path,
                reason=f"The outcome loop is waiting for real {phase} work against the current content bound state.",
            )
            state["next_action"]["loop_state_path"] = relative(project_root, loop_path)
            state["next_action"]["loop_phase"] = phase
            state["next_action"]["loop_next_action"] = loop.get("next_action")
            if phase in {"build_candidate", "rework"}:
                state["next_action"]["required_handoff"] = "Each production worker must write artifact-manifest.json in its exact write scope."
            else:
                state["next_action"]["required_handoff"] = "Each independent evaluator worker must write execution-receipt.json in its exact write scope."
            return save_state(project_root, state)
'''
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding="utf-8")


patch_organization()
patch_director()
print("automatic outcome handoffs integrated")
