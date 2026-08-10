#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_loop() -> None:
    path = Path("skills/company-os/elastic-company-os/scripts/outcome_loop.py")
    old = ''' 'evaluation_lanes':[{'lane_id':f'evaluator:{e["evaluator_id"]}','role':'independent_evaluator','evaluator_id':e['evaluator_id']} for e in required_evaluators],
 'specialist_lanes':[{'lane_id':f'artifact:{a}','role':'artifact_specialist','artifact_classes':[a]} for a in required_artifacts],
 'independent_evaluators':[{'lane_id':f'evaluator:{e["evaluator_id"]}','role':'independent_evaluator','evaluator_id':e['evaluator_id']} for e in required_evaluators],
'''
    new = ''' 'evaluation_lanes':[{'lane_id':f'evaluator:{e["evaluator_id"]}','role':'independent_evaluator','evaluator_id':e['evaluator_id'],'artifact_classes':e['artifact_classes'],'score_dimensions':e['score_dimensions'],'mandate':f'Independently evaluate the current candidate with {e["evaluator_id"]} against the bound artifact evidence and benchmarks.'} for e in required_evaluators],
 'specialist_lanes':[{'lane_id':f'artifact:{a}','role':'artifact_specialist','artifact_classes':[a]} for a in required_artifacts],
 'independent_evaluators':[{'lane_id':f'evaluator:{e["evaluator_id"]}','role':'independent_evaluator','evaluator_id':e['evaluator_id'],'artifact_classes':e['artifact_classes'],'score_dimensions':e['score_dimensions']} for e in required_evaluators],
'''
    replace_once(path, old, new, "outcome evaluator lane enrichment")


def patch_organization() -> None:
    path = Path("skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py")
    replace_once(
        path,
        '''    if phase not in {"build_candidate", "rework"}:
        raise OrganizationError("E_PHASE", "execution organization is allowed only while materializing or reworking a candidate")
    next_action = _object(state.get("next_action"), "next_action").get("action")
    expected_action = "materialize_candidate" if phase == "build_candidate" else "execute_intervention"
''',
        '''    if phase not in {"build_candidate", "rework", "evaluate"}:
        raise OrganizationError("E_PHASE", "execution organization is allowed only while materializing, evaluating, or reworking a candidate")
    next_action = _object(state.get("next_action"), "next_action").get("action")
    expected_action = {
        "build_candidate": "materialize_candidate",
        "rework": "execute_intervention",
        "evaluate": "execute_required_evaluators",
    }[phase]
''',
        "allow evaluate phase",
    )
    replace_once(
        path,
        '''    normalized = {"lane_id": lane_id, "role": role, "mandate": mandate, "artifact_classes": classes}
    if isinstance(raw.get("target_dimension"), str) and raw["target_dimension"].strip():
        normalized["target_dimension"] = raw["target_dimension"]
    return normalized
''',
        '''    normalized = {"lane_id": lane_id, "role": role, "mandate": mandate, "artifact_classes": classes}
    if isinstance(raw.get("target_dimension"), str) and raw["target_dimension"].strip():
        normalized["target_dimension"] = raw["target_dimension"]
    if role == "independent_evaluator":
        normalized["evaluator_id"] = _text(raw.get("evaluator_id"), f"{lane_id}.evaluator_id")
        dimensions = raw.get("score_dimensions")
        if not isinstance(dimensions, list) or not dimensions or not all(isinstance(item, str) and item.strip() for item in dimensions):
            raise OrganizationError("E_ORGANIZATION", f"{lane_id} has no score dimensions")
        normalized["score_dimensions"] = sorted(set(dimensions))
    return normalized
''',
        "normalize evaluator lane",
    )
    replace_once(
        path,
        '''    if state.get("phase") == "build_candidate":
        raw_lanes = organization.get("production_lanes")
        if not isinstance(raw_lanes, list) or not raw_lanes:
            raw_lanes = organization.get("specialist_lanes")
    else:
        raw_lanes = organization.get("specialist_lanes")
''',
        '''    if state.get("phase") == "build_candidate":
        raw_lanes = organization.get("production_lanes")
        if not isinstance(raw_lanes, list) or not raw_lanes:
            raw_lanes = organization.get("specialist_lanes")
    elif state.get("phase") == "evaluate":
        raw_lanes = organization.get("evaluation_lanes")
    else:
        raw_lanes = organization.get("specialist_lanes")
''',
        "select evaluator lanes",
    )
    old = '''        acceptance = ["Materialize a real candidate artifact for the assigned artifact classes", "Return exact artifact paths and SHA256 digests", "Do not use source code, tests, or completion narrative as product acceptance"]
        acceptance.extend(f"Preserve independently passing quality dimension {dimension}" for dimension in preserve_dimensions)
        worker_task = lane["mandate"]
        if preserve_dimensions:
            worker_task += " Preserve already passing dimensions: " + ", ".join(preserve_dimensions) + "."
        workers = [{"id": f"{manager_id}-worker-01", "model": "gpt-5.6-luna", "task": worker_task, "acceptance": acceptance, "write_scope": [f"{resource_scope}/artifact"], "risk": "medium", "budget": dict(manager_budget), "outcome_context": {"program_version": program_version, "north_star": north_star, "user_value": user_value, "program_outcome": governed_outcome, "manager_outcome": lane["mandate"], "roadmap_position": "execution", "dependencies": dependencies, "non_goals": non_goals, "constraints": constraints + ["Materialize a real candidate before independent evaluation", "Production actors cannot perform final independent evaluation"]}, "stop_condition": "A real artifact is materialized with exact evidence, or a blocking constraint is proven", "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha}]
        managers.append({"id": manager_id, "model": "gpt-5.6-sol", "outcome": lane["mandate"], "acceptance": acceptance, "phase_ids": PHASES, "budget": dict(manager_budget), "write_scope": [resource_scope], "workers": workers, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha})
'''
    new = '''        if state.get("phase") == "evaluate":
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
        workers = [{"id": f"{manager_id}-worker-01", "model": "gpt-5.6-luna", "task": worker_task, "acceptance": acceptance, "write_scope": worker_write_scope, "risk": "medium", "budget": dict(manager_budget), "outcome_context": outcome_context, "stop_condition": stop_condition, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha}]
        managers.append({"id": manager_id, "model": "gpt-5.6-sol", "outcome": lane["mandate"], "acceptance": acceptance, "phase_ids": PHASES, "budget": dict(manager_budget), "write_scope": [resource_scope], "artifact_classes": lane["artifact_classes"], "workers": workers, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha})
'''
    replace_once(path, old, new, "compile evaluator managers")


def patch_tests() -> None:
    path = Path("tests/test_outcome_organization.py")
    marker = '''    def test_loop_state_drift_invalidates_existing_fabric(self) -> None:
'''
    test = '''    def test_evaluation_phase_compiles_independent_read_only_evaluator_lane(self) -> None:
        state = self.initial_state()
        state["phase"] = "evaluate"
        state["iteration"] = 1
        state["required_evaluators"] = [{
            "evaluator_id": "gameplay-evaluator",
            "artifact_classes": ["playable_game"],
            "score_dimensions": ["gameplay", "visual_quality"],
        }]
        state["organization_plan"] = {
            "evaluation_lanes": [{
                "lane_id": "evaluator:gameplay-evaluator",
                "role": "independent_evaluator",
                "evaluator_id": "gameplay-evaluator",
                "artifact_classes": ["playable_game"],
                "score_dimensions": ["gameplay", "visual_quality"],
                "mandate": "Independently play and score the current game candidate.",
            }]
        }
        state["next_action"] = {
            "action": "execute_required_evaluators",
            "candidate_id": "candidate:1",
            "evaluator_ids": ["gameplay-evaluator"],
        }
        state["state_sha256"] = ORG.digest({**state, "state_sha256": None})
        self.write_state(state)
        manifest = self.compile()
        self.assertEqual(manifest["outcome_loop"]["phase"], "evaluate")
        self.assertEqual(len(manifest["managers"]), 1)
        manager = manifest["managers"][0]
        worker = manager["workers"][0]
        self.assertEqual(manager["outcome_loop_lane_id"], "evaluator:gameplay-evaluator")
        self.assertEqual(worker["outcome_context"]["evaluator_id"], "gameplay-evaluator")
        self.assertEqual(worker["outcome_context"]["artifact_classes"], ["playable_game"])
        self.assertEqual(worker["outcome_context"]["score_dimensions"], ["gameplay", "visual_quality"])
        self.assertTrue(worker["write_scope"][0].endswith("/evaluation-receipt"))
        self.assertTrue(any("Do not modify candidate artifacts" == item for item in manager["acceptance"]))
        self.assertEqual(ORG.validate_manifest_binding(self.root, manifest)["phase"], "evaluate")

'''
    replace_once(path, marker, test + marker, "evaluator organization test")


if __name__ == "__main__":
    patch_loop()
    patch_organization()
    patch_tests()
