#!/usr/bin/env python3
from pathlib import Path

p=Path('skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py')
s=p.read_text()
s=s.replace('import re\nfrom pathlib', 'import re\nimport importlib.util\nfrom pathlib',1)
needle='''def _child_budget(parent: Mapping[str, Any], manager_count: int) -> dict[str, Any]:
    return {"time_minutes": float(parent["time_minutes"]) / manager_count, "token_limit": max(1, int(parent["token_limit"]) // manager_count), "cost_usd": float(parent["cost_usd"]) / manager_count, "max_concurrency": 1, "max_retries": int(parent["max_retries"])}
'''
insert=needle+'''\ndef _engineering_module():
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
'''
if needle not in s: raise SystemExit('budget anchor missing')
s=s.replace(needle,insert,1)
needle='''    control = _validate_outcome_control(_object(request.get("outcome_control"), "outcome_control"), project_id=project_id, program_version=program_version, work_id=work_id, governed_outcome=governed_outcome, objective_id=objective_id)
'''
replacement=needle+'''    engineering_module = _engineering_module()
    master_engineering = _engineering_root(objective_id, request)
'''
s=s.replace(needle,replacement,1)
needle='''        workers = [{"id": f"{manager_id}-worker-01", "model": "gpt-5.6-luna", "task": worker_task, "acceptance": acceptance, "write_scope": worker_write_scope, "risk": "medium", "budget": dict(manager_budget), "outcome_context": outcome_context, "stop_condition": stop_condition, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha}]
        managers.append({"id": manager_id, "model": "gpt-5.6-sol", "outcome": lane["mandate"], "acceptance": acceptance, "phase_ids": PHASES, "budget": dict(manager_budget), "write_scope": [resource_scope], "artifact_classes": lane["artifact_classes"], "workers": workers, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha})
'''
replacement='''        manager_engineering = engineering_module.derive(master_engineering, {"contract_id": f"engineering:{manager_id}", "objective_id": objective_id, "manager_level": "mid", "required_skills": list(master_engineering["required_skills"]), "write_scopes": [resource_scope]})
        worker_engineering = engineering_module.derive(manager_engineering, {"contract_id": f"engineering:{manager_id}:worker-01", "objective_id": objective_id, "manager_level": "worker", "required_skills": list(manager_engineering["required_skills"]), "write_scopes": worker_write_scope})
        outcome_context["engineering_execution_contract"] = worker_engineering
        workers = [{"id": f"{manager_id}-worker-01", "model": "gpt-5.6-luna", "task": worker_task, "acceptance": acceptance, "write_scope": worker_write_scope, "risk": "medium", "budget": dict(manager_budget), "outcome_context": outcome_context, "engineering_execution_contract": worker_engineering, "stop_condition": stop_condition, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha}]
        managers.append({"id": manager_id, "model": "gpt-5.6-sol", "outcome": lane["mandate"], "acceptance": acceptance, "phase_ids": PHASES, "budget": dict(manager_budget), "write_scope": [resource_scope], "artifact_classes": lane["artifact_classes"], "engineering_execution_contract": manager_engineering, "workers": workers, "outcome_loop_lane_id": lane["lane_id"], "outcome_loop_lane_sha256": lane_sha})
'''
if needle not in s: raise SystemExit('worker anchor missing')
s=s.replace(needle,replacement,1)
needle='''    return {"program_id": project_id, "topology_mode": TOPOLOGY_MODE,'''
s=s.replace(needle,'''    engineering_module.assert_nonoverlap([manager["engineering_execution_contract"] for manager in managers])
    return {"program_id": project_id, "topology_mode": TOPOLOGY_MODE, "engineering_execution_contract": master_engineering,''',1)
p.write_text(s)
