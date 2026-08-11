#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path


def replace_between(path: Path, start: str, end: str, replacement: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    a = text.find(start)
    if a < 0:
        raise SystemExit(f"{label}: start marker missing")
    b = text.find(end, a)
    if b < 0:
        raise SystemExit(f"{label}: end marker missing")
    path.write_text(text[:a] + replacement + text[b:], encoding="utf-8")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_outcome_loop() -> None:
    path = Path("skills/company-os/elastic-company-os/scripts/outcome_loop.py")
    start = "def bind_control(project,raw_state,control):\n"
    end = "def record_candidate(project,raw_state,candidate):\n"
    replacement = '''def _production_lanes(required_artifacts, execution_lane):
 if execution_lane=='pilot':
  lane_count=min(2,len(required_artifacts)); groups=[[] for _ in range(lane_count)]
  for index,artifact_class in enumerate(required_artifacts): groups[index%lane_count].append(artifact_class)
  return [
   {'lane_id':f'pilot:artifact-bundle:{index+1:02d}','role':'artifact_specialist','artifact_classes':group,
    'mandate':'Materialize and run the smallest connected candidate covering these required artifact classes: '+', '.join(group)+'. Plans, schemas, reports, tests, and completion narratives do not substitute for the actual artifact unless explicitly required as an artifact class.'}
   for index,group in enumerate(groups)
  ]
 return [
  {'lane_id':f'artifact:{artifact_class}','role':'artifact_specialist','artifact_class_id':artifact_class,'artifact_classes':[artifact_class],
   'mandate':f'Materialize, run, and observe the required {artifact_class} artifact against the original objective.'}
  for artifact_class in required_artifacts
 ]

def _loop_control_projection(control):
 return {'state_sha256':control['state_sha256'],'execution_lane':control['execution_lane'],'outcome':dict(control['outcome']),'artifacts':dict(control['artifacts']),'evaluators':dict(control['evaluators']),'benchmarks':dict(control['benchmarks']),'calibrations':dict(control['calibrations']),'scale_authorization':dict(control['scale_authorization'])}

def bind_control(project,raw_state,control):
 state=verify_state(raw_state)
 if state['phase']!='discovery': raise OutcomeLoopError('E_PHASE','control can only bind from discovery')
 if control.get('$schema')!=CONTROL_SCHEMA: raise OutcomeLoopError('E_SCHEMA','bad control schema')
 observed=sha(control.get('state_sha256'),'control.state_sha256')
 if observed!=digest({**control,'state_sha256':None}): raise OutcomeLoopError('E_DIGEST','control state changed')
 if control.get('objective_id')!=state['objective_id'] or control.get('original_objective')!=state['original_objective']: raise OutcomeLoopError('E_BINDING','control does not bind original objective')
 artifacts,_=load_contract(project,obj(control.get('artifacts'),'control.artifacts'),'artifact contract')
 evaluators,_=load_contract(project,obj(control.get('evaluators'),'control.evaluators'),'evaluator contract')
 outcome,_=load_contract(project,obj(control.get('outcome'),'control.outcome'),'outcome contract')
 required_artifacts=sorted({text(x.get('artifact_class_id'),'artifact_class_id') for x in artifacts.get('artifact_classes',[]) if isinstance(x,Mapping) and x.get('required') is True})
 required_evaluators=[]
 for x in evaluators.get('evaluators',[]):
  if isinstance(x,Mapping) and x.get('required') is True:
   required_evaluators.append({'evaluator_id':text(x.get('evaluator_id'),'evaluator_id'),'artifact_classes':sorted(x.get('artifact_classes',[])),'score_dimensions':sorted(x.get('score_dimensions',[]))})
 if not required_artifacts or not required_evaluators: raise OutcomeLoopError('E_CONTROL','real artifacts and evaluators are required')
 production_lanes=_production_lanes(required_artifacts,control.get('execution_lane'))
 org={'mode':'initial_reality_pilot' if control.get('execution_lane')=='pilot' else 'production_scale',
 'manager_lanes':[{'lane_id':'manager:outcome','role':'outcome_manager','mandate':'Own the shortest executable path from the original objective to a real candidate.'}],
 'production_lanes':production_lanes,
 'evaluation_lanes':[{'lane_id':f'evaluator:{e["evaluator_id"]}','role':'independent_evaluator','evaluator_id':e['evaluator_id'],'artifact_classes':e['artifact_classes'],'score_dimensions':e['score_dimensions'],'mandate':f'Independently evaluate the current candidate with {e["evaluator_id"]} against the bound artifact evidence and benchmarks.'} for e in required_evaluators],
 'specialist_lanes':[{'lane_id':f'artifact:{a}','role':'artifact_specialist','artifact_classes':[a]} for a in required_artifacts],
 'independent_evaluators':[{'lane_id':f'evaluator:{e["evaluator_id"]}','role':'independent_evaluator','evaluator_id':e['evaluator_id'],'artifact_classes':e['artifact_classes'],'score_dimensions':e['score_dimensions']} for e in required_evaluators],
 'instruction':'Reach connected artifact reality before expanding organization. Production work must create and exercise the real artifact; documentation and governance are support work, not the mission.'}
 next_state={**state,'phase':'build_candidate','control_state':_loop_control_projection(control),'outcome_claims':[dict(x) for x in outcome.get('outcome_claims',[]) if isinstance(x,Mapping)],'required_artifact_classes':required_artifacts,'required_evaluators':required_evaluators,'organization_plan':org,
 'next_action':{'action':'materialize_candidate','authority':'bounded_reversible_pilot','required_artifact_classes':required_artifacts,'organization_plan':org,'first_reality_target':'R3'}}
 return seal(next_state)

def refresh_control(project,raw_state,control):
 state=verify_state(raw_state)
 if state['phase'] not in {'evaluate','rework'}: raise OutcomeLoopError('E_PHASE','control refresh is allowed only after a real candidate exists')
 if control.get('$schema')!=CONTROL_SCHEMA: raise OutcomeLoopError('E_SCHEMA','bad control schema')
 observed=sha(control.get('state_sha256'),'control.state_sha256')
 if observed!=digest({**control,'state_sha256':None}): raise OutcomeLoopError('E_DIGEST','control state changed')
 if control.get('objective_id')!=state['objective_id'] or control.get('original_objective')!=state['original_objective']: raise OutcomeLoopError('E_BINDING','refreshed control does not bind original objective')
 current=obj(state.get('control_state'),'state.control_state')
 for field in ('outcome','artifacts','evaluators','benchmarks'):
  if dict(obj(control.get(field),f'control.{field}'))!=dict(obj(current.get(field),f'state.control_state.{field}')): raise OutcomeLoopError('E_BINDING',f'control refresh changed bound {field} contract')
 history=[*state.get('history',[]),{'event':'outcome_control_refreshed','from_execution_lane':current.get('execution_lane'),'to_execution_lane':control.get('execution_lane'),'control_state_sha256':observed}]
 return seal({**state,'control_state':_loop_control_projection(control),'history':history})

'''
    replace_between(path, start, end, replacement, "outcome loop reality-first control")


def patch_director() -> None:
    path = Path("skills/company-os/direct-outcome/scripts/direct_outcome.py")
    text = path.read_text(encoding="utf-8")
    if "def candidate_assembler_module():" not in text:
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
        if marker not in text: raise SystemExit("director assembler loader marker missing")
        text = text.replace(marker, insertion, 1)
        path.write_text(text, encoding="utf-8")

    start = "def build_outcome_control(\n"
    end = "def organization_request(\n"
    replacement = '''def build_outcome_control(
    project_root: Path,
    state: Mapping[str, Any],
    outcome: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    evaluators: Mapping[str, Any],
    benchmarks: Mapping[str, Any],
    calibrations: list[dict[str, Any]],
    *,
    force_lane: str | None = None,
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

'''
    replace_between(path, start, end, replacement, "director outcome control")
    replace_once(path, '        state["stage"] = "evaluator_capability"\n', '        state["stage"] = "control"\n', "discovery must build before evaluators")

    control_start = '    if stage == "control":\n'
    control_end = '    if stage == "loop":\n'
    control_replacement = '''    if stage == "control":
        outcome, artifacts, evaluators, benchmarks = load_contracts(base)
        loop_path = base / "outcome-loop.json"
        loop = obj(read_json(loop_path, "outcome loop"), "outcome loop")
        phase = loop.get("phase")
        if phase == "discovery":
            # Build the first real candidate before spending the mission on evaluator
            # construction/calibration. Empty calibration bindings are valid for a
            # bounded, reversible pilot.
            binding, portable = build_outcome_control(project_root, state, outcome, artifacts, evaluators, benchmarks, [], force_lane="pilot")
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

'''
    replace_between(path, control_start, control_end, control_replacement, "director control stage")

    loop_start = '    if stage == "loop":\n'
    loop_end = '    if stage == "accepted":\n'
    loop_replacement = '''    if stage == "loop":
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
            return advance(project_root, objective_id)
        if phase not in {"build_candidate", "rework", "evaluate"}:
            raise DirectorError("E_PHASE", f"unsupported outcome loop phase: {phase}")

        # Evaluator capability is just-in-time. Until a real candidate exists the
        # organization spends its scarce budget on product reality, not on building
        # and auditing hypothetical judges.
        if phase == "evaluate":
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

'''
    replace_between(path, loop_start, loop_end, loop_replacement, "director loop stage")


def patch_organization() -> None:
    path = Path("skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py")
    text = path.read_text(encoding="utf-8")
    old = '''        else:
            acceptance = ["Materialize a real candidate artifact for the assigned artifact classes", "Return exact artifact paths and SHA256 digests", "Do not use source code, tests, or completion narrative as product acceptance"]
            acceptance.extend(f"Preserve independently passing quality dimension {dimension}" for dimension in preserve_dimensions)
            worker_task = lane["mandate"]
            if preserve_dimensions:
                worker_task += " Preserve already passing dimensions: " + ", ".join(preserve_dimensions) + "."
            worker_write_scope = [f"{resource_scope}/artifact"]
            stop_condition = "A real artifact is materialized with exact evidence, or a blocking constraint is proven"
            extra_constraints = ["Materialize a real candidate before independent evaluation", "Production actors cannot perform final independent evaluation"]
'''
    new = '''        else:
            acceptance = [
                "Materialize and execute a real candidate artifact for every assigned artifact class",
                "Reach the smallest connected end-to-end behavior before spending the lane on refinement",
                "Return exact artifact paths and SHA256 digests",
                "Do not use source code, tests, plans, schemas, reports, or completion narrative as product acceptance unless the artifact contract explicitly requires that class",
            ]
            acceptance.extend(f"Preserve independently passing quality dimension {dimension}" for dimension in preserve_dimensions)
            worker_task = lane["mandate"] + " Within the first third of this lane budget, create and run the smallest real end-to-end artifact path. Stop broad research and speculative architecture once enough is known to execute. If the user supplied a provider, repository, SDK, or framework that already implements a required capability, integrate and exercise it before building a replacement; replacement requires concrete blocker evidence."
            if preserve_dimensions:
                worker_task += " Preserve already passing dimensions: " + ", ".join(preserve_dimensions) + "."
            worker_write_scope = [f"{resource_scope}/artifact"]
            artifact_manifest_path = f"{resource_scope}/artifact/artifact-manifest.json"
            artifact_manifest_binding = {"$schema": "company-os.outcome-lane-artifact-manifest.v1", "schema_version": 1, "objective_id": state["objective_id"], "outcome_loop_state_sha256": state["state_sha256"], "organization_sha256": digest(state["organization_plan"]), "lane_id": lane["lane_id"], "lane_sha256": lane_sha, "production_actor_id": f"{manager_id}-worker-01"}
            worker_task += " When materialized, write the canonical artifact handoff at " + artifact_manifest_path + ". Preserve these exact immutable bindings: " + json.dumps(artifact_manifest_binding, sort_keys=True) + ". Add an artifacts array containing each actual artifact_id, artifact_class_id, project-relative path, and exact sha256. A prose report is not a handoff."
            stop_condition = "A real connected artifact is materialized and executed with exact evidence, or a blocking constraint is proven"
            extra_constraints = [
                "Materialize a real candidate before independent evaluation",
                "Plans, research, schemas, and governance are support work and cannot replace execution",
                "Integrate supplied capabilities before reimplementing them unless blocker evidence proves integration cannot satisfy the requirement",
                "Production actors cannot perform final independent evaluation",
            ]
'''
    if old not in text: raise SystemExit("organization production block missing")
    text = text.replace(old, new, 1)
    old_ctx = '''        outcome_context = {"program_version": program_version, "north_star": north_star, "user_value": user_value, "program_outcome": governed_outcome, "manager_outcome": lane["mandate"], "roadmap_position": "evaluation" if state.get("phase") == "evaluate" else "execution", "artifact_classes": lane["artifact_classes"], "dependencies": dependencies, "non_goals": non_goals, "constraints": constraints + extra_constraints}
'''
    new_ctx = '''        outcome_context = {"program_version": program_version, "north_star": north_star, "user_value": user_value, "program_outcome": governed_outcome, "manager_outcome": lane["mandate"], "roadmap_position": "evaluation" if state.get("phase") == "evaluate" else "execution", "artifact_classes": lane["artifact_classes"], "dependencies": dependencies, "non_goals": non_goals, "constraints": constraints + extra_constraints, "execution_policy": {"first_reality_target": "R3", "first_reality_budget_fraction": 0.25, "global_bottleneck": lane["mandate"], "documentation_is_not_progress": True, "prefer_existing_capabilities": True}}
'''
    if old_ctx not in text: raise SystemExit("organization outcome context missing")
    path.write_text(text.replace(old_ctx, new_ctx, 1), encoding="utf-8")


def patch_bootstrap() -> None:
    path = Path("skills/company-os/bootstrap-outcome/scripts/bootstrap_outcome.py")
    replace_once(path,
        '"Every conclusion and every proposed outcome claim, artifact, evaluator, benchmark, or final acceptance policy must carry citations. Unknown means research until measurable. Do not ask the operator to provide domain vocabulary."',
        '"Every conclusion and every proposed outcome claim, artifact, evaluator, benchmark, or final acceptance policy must carry citations. Research only until the first real vertical slice is executable; defer nonblocking corpus expansion. Unknown means research until measurable enough to act. Do not ask the operator to provide domain vocabulary."',
        "bootstrap pull-based research")
    replace_once(path,
        '"Research output is integrated only as a proposal, not product acceptance",',
        '"Research output is integrated only as a proposal, not product acceptance",\n                    "Stop discovery when enough evidence exists to execute the first reversible real-artifact slice",',
        "bootstrap manager stop rule")
    replace_once(path,
        '"rationale": "Resolve domain uncertainty before expensive production.",',
        '"rationale": "Resolve only the uncertainty blocking the first real vertical slice, then execute and learn from the artifact.",',
        "bootstrap rationale")
    replace_once(path,
        '"budget": {"time_minutes": 90.0, "token_limit": 24000, "cost_usd": 24.0, "max_concurrency": 2, "max_retries": 1},',
        '"budget": {"time_minutes": 45.0, "token_limit": 12000, "cost_usd": 12.0, "max_concurrency": 2, "max_retries": 1},',
        "bootstrap discovery ceiling")


def patch_director_tests() -> None:
    path = Path("tests/test_outcome_director.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace('''    def test_completed_discovery_advances_until_real_missing_adapter_boundary(self) -> None:
        self.write_proposals()
        MODULE.registry_module = lambda: FakeMissingRegistry
        result = MODULE.advance(self.project, "viral-game")
        self.assertEqual(result["stage"], "evaluator_capability")
        self.assertEqual(result["next_action"]["stage"], "evaluator_capability")
        fabric = MODULE.workspace(self.project, "viral-game") / "runtime/evaluator-build-fabric.json"
        self.assertEqual(json.loads(fabric.read_text())["kind"], "evaluator-build")
        self.assertTrue((MODULE.workspace(self.project, "viral-game") / "measurable-outcome-request.json").is_file())

    def test_ready_adapters_advance_to_calibration_boundary(self) -> None:
        self.write_proposals()
        MODULE.registry_module = lambda: FakeReadyRegistry
        result = MODULE.advance(self.project, "viral-game")
        self.assertEqual(result["stage"], "calibration")
        self.assertEqual(result["next_action"]["stage"], "calibration")
        fabric = MODULE.workspace(self.project, "viral-game") / "runtime/calibration-fabric.json"
        self.assertEqual(json.loads(fabric.read_text())["kind"], "calibration")
        self.assertTrue((MODULE.workspace(self.project, "viral-game") / "runtime/evaluator-adapter-registry.json").is_file())
''', '''    def test_completed_discovery_enters_control_before_evaluator_construction(self) -> None:
        self.write_proposals()
        state = MODULE.load_state(self.project, "viral-game")
        # Stop the deterministic recursion at the control boundary so this unit test
        # proves sequencing without constructing a full project control store.
        original = MODULE.build_outcome_control
        def stop_at_control(*args, **kwargs):
            raise MODULE.DirectorError("E_TEST_CONTROL", "reached first reality control")
        MODULE.build_outcome_control = stop_at_control
        try:
            with self.assertRaises(MODULE.DirectorError) as caught:
                MODULE.advance(self.project, "viral-game")
            self.assertEqual(caught.exception.code, "E_TEST_CONTROL")
            persisted = MODULE.load_state(self.project, "viral-game")
            self.assertEqual(persisted["stage"], "control")
            self.assertTrue((MODULE.workspace(self.project, "viral-game") / "measurable-outcome-request.json").is_file())
        finally:
            MODULE.build_outcome_control = original

    def test_evaluators_are_not_requested_before_candidate_phase(self) -> None:
        self.write_proposals()
        MODULE.registry_module = lambda: FakeMissingRegistry
        original = MODULE.build_outcome_control
        def stop_at_control(*args, **kwargs):
            raise MODULE.DirectorError("E_TEST_CONTROL", "reached first reality control")
        MODULE.build_outcome_control = stop_at_control
        try:
            with self.assertRaises(MODULE.DirectorError):
                MODULE.advance(self.project, "viral-game")
            self.assertFalse((MODULE.workspace(self.project, "viral-game") / "runtime/evaluator-build-fabric.json").exists())
            self.assertFalse((MODULE.workspace(self.project, "viral-game") / "runtime/calibration-fabric.json").exists())
        finally:
            MODULE.build_outcome_control = original
''')
    path.write_text(text, encoding="utf-8")


patch_outcome_loop()
patch_director()
patch_organization()
patch_bootstrap()
patch_director_tests()
print("reality-first execution governor integrated")
