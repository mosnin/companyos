#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_director() -> None:
    path = ROOT / "skills/company-os/direct-outcome/scripts/direct_outcome.py"
    replace_once(path, '                "label": raw["label"],\n', '                "label": raw.get("label") or raw["artifact_class_id"],\n')
    replace_once(
        path,
        '''    for observation in candidate.get("observations", []):
        if not isinstance(observation, Mapping) or observation.get("capability_id") not in known:
''',
        '''    observations = sorted(
        (item for item in candidate.get("observations", []) if isinstance(item, Mapping)),
        key=lambda item: (0 if item.get("kind") == "runtime_observed" else 1, str(item.get("capability_id")), str(item.get("path"))),
    )
    for observation in observations:
        if observation.get("capability_id") not in known:
''',
    )
    replace_once(
        path,
        '''        if phase == "evaluate":
            evaluator_contract = obj(read_json(base / "runtime/evaluator-contract.json", "evaluator contract"), "evaluator contract")
''',
        '''        if phase == "evaluate":
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
''',
    )


def patch_outcome_loop() -> None:
    path = ROOT / "skills/company-os/elastic-company-os/scripts/outcome_loop.py"
    old = '''def refresh_control(project,raw_state,control):
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
    new = '''def _required_artifact_ids(contract):
 return sorted({text(item.get('artifact_class_id'),'artifact_class_id') for item in contract.get('artifact_classes',[]) if isinstance(item,Mapping) and item.get('required') is True})

def refresh_control(project,raw_state,control):
 state=verify_state(raw_state)
 if state['phase'] not in {'evaluate','rework'}: raise OutcomeLoopError('E_PHASE','control refresh is allowed only after a real candidate exists')
 if control.get('$schema')!=CONTROL_SCHEMA: raise OutcomeLoopError('E_SCHEMA','bad control schema')
 observed=sha(control.get('state_sha256'),'control.state_sha256')
 if observed!=digest({**control,'state_sha256':None}): raise OutcomeLoopError('E_DIGEST','control state changed')
 if control.get('objective_id')!=state['objective_id'] or control.get('original_objective')!=state['original_objective']: raise OutcomeLoopError('E_BINDING','refreshed control does not bind original objective')
 current=obj(state.get('control_state'),'state.control_state')
 promotion=current.get('execution_lane')=='pilot' and control.get('execution_lane')=='production_scale'
 for field in ('outcome','evaluators','benchmarks'):
  if dict(obj(control.get(field),f'control.{field}'))!=dict(obj(current.get(field),f'state.control_state.{field}')): raise OutcomeLoopError('E_BINDING',f'control refresh changed bound {field} contract')
 old_artifacts,_=load_contract(project,obj(current.get('artifacts'),'state.control_state.artifacts'),'current artifact contract')
 new_artifacts,_=load_contract(project,obj(control.get('artifacts'),'control.artifacts'),'refreshed artifact contract')
 old_required=_required_artifact_ids(old_artifacts); new_required=_required_artifact_ids(new_artifacts)
 if promotion:
  if not set(old_required).issubset(new_required): raise OutcomeLoopError('E_BINDING','production scope removed a First Reality artifact class')
 else:
  if dict(obj(control.get('artifacts'),'control.artifacts'))!=dict(obj(current.get('artifacts'),'state.control_state.artifacts')): raise OutcomeLoopError('E_BINDING','control refresh changed bound artifacts contract')
 history=[*state.get('history',[]),{'event':'outcome_control_refreshed','from_execution_lane':current.get('execution_lane'),'to_execution_lane':control.get('execution_lane'),'control_state_sha256':observed}]
 if promotion and set(new_required)!=set(old_required):
  production_lanes=_production_lanes(new_required,'production_scale')
  org={
   'mode':'production_scale_after_first_reality',
   'manager_lanes':[{'lane_id':'manager:outcome','role':'outcome_manager','mandate':'Expand the proven First Reality path to the complete final product scope.'}],
   'production_lanes':production_lanes,
   'evaluation_lanes':state['organization_plan'].get('evaluation_lanes',[]) if isinstance(state.get('organization_plan'),Mapping) else [],
   'specialist_lanes':[{'lane_id':f'artifact:{artifact}','role':'artifact_specialist','artifact_classes':[artifact]} for artifact in new_required],
   'independent_evaluators':state['organization_plan'].get('independent_evaluators',[]) if isinstance(state.get('organization_plan'),Mapping) else [],
   'instruction':'Preserve the connected First Reality journey while materializing every deferred final capability.'
  }
  history.append({'event':'first_reality_scope_expanded','from_artifact_classes':old_required,'to_artifact_classes':new_required})
  return seal({**state,'phase':'build_candidate','control_state':_loop_control_projection(control),'required_artifact_classes':new_required,'organization_plan':org,'history':history,
   'next_action':{'action':'materialize_candidate','authority':'scope_expansion_after_first_reality','required_artifact_classes':new_required,'organization_plan':org,'preserve_candidate_id':state['candidates'][-1]['candidate_id'] if state.get('candidates') else None}})
 return seal({**state,'control_state':_loop_control_projection(control),'history':history})
'''
    replace_once(path, old, new)


def patch_bootstrap() -> None:
    path = ROOT / "skills/company-os/bootstrap-outcome/scripts/bootstrap_outcome.py"
    old = '''    managers.append({
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
'''
    new = '''    first_manager = managers[0]
    first_manager["outcome"] = "Discover domain truth while creating the first reversible running artifact."
    first_manager["budget"] = {"time_minutes": 30.0, "token_limit": 9000, "cost_usd": 9.0, "max_concurrency": 2, "max_retries": 1}
    first_manager["write_scope"] = list(dict.fromkeys([*first_manager["write_scope"], *spike_worker["write_scope"]]))
    first_manager["acceptance"].extend(spike_worker["acceptance"])
    first_manager["workers"][0]["outcome_context"]["manager_outcome"] = first_manager["outcome"]
    spike_worker["outcome_context"]["manager_outcome"] = first_manager["outcome"]
    first_manager["workers"].append(spike_worker)
'''
    replace_once(path, old, new)
    replace_once(path, '        "max_managers": 3,\n        "max_manager_concurrency": 3,\n        "max_workers_per_manager": 1,\n        "max_total_workers": 3,\n', '        "max_managers": 2,\n        "max_manager_concurrency": 2,\n        "max_workers_per_manager": 2,\n        "max_total_workers": 3,\n')
    replace_once(path, '        "budget": {"time_minutes": 40.0, "token_limit": 12000, "cost_usd": 12.0, "max_concurrency": 3, "max_retries": 1},\n', '        "budget": {"time_minutes": 40.0, "token_limit": 12000, "cost_usd": 12.0, "max_concurrency": 2, "max_retries": 1},\n')


def patch_tests() -> None:
    path = ROOT / "tests/test_calibration_fabric.py"
    replace_once(path, '    def test_two_evaluators_are_maximum_batch(self):\n', '    def test_one_evaluator_is_maximum_economic_batch(self):\n')
    replace_once(path, '        self.assertEqual(result["calibration_evaluator_ids"], ["eval-0", "eval-1"])\n        self.assertEqual(result["remaining_evaluator_ids"], ["eval-2"])\n', '        self.assertEqual(result["calibration_evaluator_ids"], ["eval-0"])\n        self.assertEqual(result["remaining_evaluator_ids"], ["eval-1", "eval-2"])\n        self.assertLessEqual(result["fabric"]["budget"]["time_minutes"], 30.0)\n')

    path = ROOT / "tests/test_outcome_discovery_bootstrap.py"
    replace_once(path, '    def test_bootstrap_compiles_two_manager_research_fabric(self) -> None:\n', '    def test_bootstrap_compiles_two_managers_with_concurrent_reality_spike(self) -> None:\n')
    replace_once(
        path,
        '''        tasks = [manager["workers"][0]["task"] for manager in manifest["managers"]]
        self.assertTrue(any("success and domain truth" in task for task in tasks))
        self.assertTrue(any("artifact and quality system" in task for task in tasks))
''',
        '''        tasks = [worker["task"] for manager in manifest["managers"] for worker in manager["workers"]]
        self.assertEqual(sum(len(manager["workers"]) for manager in manifest["managers"]), 3)
        self.assertTrue(any("success and domain truth" in task for task in tasks))
        self.assertTrue(any("artifact and quality system" in task for task in tasks))
        self.assertTrue(any("reversible reality spike" in task for task in tasks))
''',
    )

    path = ROOT / "tests/test_outcome_organization.py"
    replace_once(
        path,
        '''            "constraints": ["no consequential external effects"],
            "outcome_control": self.control,
        }
''',
        '''            "constraints": ["no consequential external effects"],
            "outcome_control": self.control,
            "mission_control": {
                "$schema": "company-os.mission-execution-binding.v1",
                "state_path": ".company-os/mission.json",
                "state_sha256": "a" * 64,
                "mission_id": "viral-game",
                "generation": 1,
                "status": "active",
                "mission_class": "company_mission",
                "governor_decision_sha256": "b" * 64,
                "governor_mode": "normal",
                "allowed_work_classes": ["implementation", "repair", "evaluation"],
                "paused_work_classes": [],
                "dominant_bottleneck": {"capability_id": "playable_game", "state": "missing"},
                "first_reality": None,
                "first_reality_required": False,
                "replacement_orders": [],
            },
            "work_admission": {
                "$schema": "company-os.work-admission-receipt.v1",
                "request_id": "request",
                "task_id": "task",
                "manager_id": "manager",
                "work_class": "implementation",
                "admitted": True,
                "blockers": [],
                "mission_state_sha256": "a" * 64,
                "governor_decision_sha256": "b" * 64,
                "governor_mode": "normal",
                "dominant_bottleneck": {"capability_id": "playable_game", "state": "missing"},
                "allowed_work_classes": ["implementation", "repair", "evaluation"],
                "replacement_orders": [],
                "receipt_sha256": "c" * 64,
            },
        }
''',
    )
    replace_once(
        path,
        '''    def compile(self) -> dict:
        return ORG.compile_manifest(self.root, ".company-os/outcome-loop.json", self.request)
''',
        '''    def compile(self) -> dict:
        state = json.loads((self.root / ".company-os/outcome-loop.json").read_text(encoding="utf-8"))
        self.request["work_admission"]["work_class"] = {
            "build_candidate": "implementation",
            "rework": "repair",
            "evaluate": "evaluation",
        }[state["phase"]]
        return ORG.compile_manifest(self.root, ".company-os/outcome-loop.json", self.request)
''',
    )


def main() -> None:
    patch_director()
    patch_outcome_loop()
    patch_bootstrap()
    patch_tests()
    print("execution enforcement v2 phase 2 applied")


if __name__ == "__main__":
    main()
