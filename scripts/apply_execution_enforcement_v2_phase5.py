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
    replace_once(
        path,
        '''def mission_binding(project_root: Path, objective_id: str) -> dict[str, Any]:
    state = refresh_mission_state(project_root, objective_id)
    decision = obj(state.get("governor_decision"), "governor decision")
''',
        '''def mission_binding_from_state(project_root: Path, state: Mapping[str, Any]) -> dict[str, Any]:
    state = mission_control_module().verify_state(state)
    decision = obj(state.get("governor_decision"), "governor decision")
''',
    )
    replace_once(
        path,
        '''        "state_path": relative(project_root, mission_state_path(project_root, objective_id)),
''',
        '''        "state_path": relative(project_root, mission_state_path(project_root, state["objective_id"])),
''',
    )
    replace_once(
        path,
        '''        "replacement_orders": list(state.get("replacement_orders", [])),
    }


def admit_mission_work(
''',
        '''        "replacement_orders": list(state.get("replacement_orders", [])),
    }


def mission_binding(project_root: Path, objective_id: str) -> dict[str, Any]:
    return mission_binding_from_state(project_root, load_mission_state(project_root, objective_id))


def _admission_receipt_path(project_root: Path, objective_id: str, task_id: str) -> Path:
    return workspace(project_root, objective_id) / "runtime/work-admissions" / f"{slug(task_id)}.json"


def bind_discovery_fabric(project_root: Path, objective_id: str, fabric_relative: str) -> dict[str, Any]:
    module = mission_control_module()
    state = refresh_mission_state(project_root, objective_id)
    stamp = module.format_time(module.now_utc())
    for work_class in ("research", "implementation"):
        state = module.record_event(
            state,
            module.make_event(
                f"dispatch:discovery:{work_class}:{state['generation']}",
                "work_recorded",
                occurred_at=stamp,
                work_class=work_class,
                units=1.0,
            ),
        )
    save_mission_state(project_root, state)
    admissions: dict[str, dict[str, Any]] = {}
    for work_class in ("research", "implementation"):
        task_id = f"outcome-discovery-{work_class}"
        receipt = module.admit_work(
            state,
            {
                "$schema": module.ADMISSION_SCHEMA,
                "request_id": f"admit:{task_id}:{state['generation']}",
                "task_id": task_id,
                "manager_id": "outcome-director",
                "work_class": work_class,
                "bootstrap": True,
            },
        )
        if receipt.get("admitted") is not True:
            raise DirectorError("E_GOVERNOR", "; ".join(receipt.get("blockers", [])))
        receipt_path = _admission_receipt_path(project_root, objective_id, task_id)
        write_json(receipt_path, receipt)
        admissions[work_class] = {
            **receipt,
            "receipt_path": relative(project_root, receipt_path),
            "receipt_file_sha256": file_digest(receipt_path),
        }
    binding = mission_binding_from_state(project_root, state)
    fabric_path = project_root / Path(*fabric_relative.split("/"))
    fabric = obj(read_json(fabric_path, "discovery fabric"), "discovery fabric")
    bound = dict(fabric)
    bound["mission_control"] = binding
    bound["work_admissions"] = admissions
    managers = []
    for manager_raw in fabric.get("managers", []):
        manager = dict(obj(manager_raw, "discovery manager"))
        workers = []
        manager_classes = []
        for worker_raw in manager.get("workers", []):
            worker = dict(obj(worker_raw, "discovery worker"))
            work_class = worker.get("work_class") or "research"
            if work_class not in admissions:
                raise DirectorError("E_GOVERNOR", f"discovery worker uses unsupported work class {work_class!r}")
            manager_classes.append(work_class)
            worker["work_class"] = work_class
            worker["mission_control"] = binding
            worker["work_admission"] = admissions[work_class]
            workers.append(worker)
        manager_class = "implementation" if "implementation" in manager_classes else "research"
        manager["work_class"] = manager_class
        manager["mission_control"] = binding
        manager["work_admission"] = admissions[manager_class]
        manager["workers"] = workers
        managers.append(manager)
    bound["managers"] = managers
    validation = bootstrap_module().fabric_module().validate(bound)
    if validation.get("valid") is not True:
        raise DirectorError("E_FABRIC", "; ".join(validation.get("errors", [])))
    write_json(fabric_path, bound)
    return {
        "mission_control": binding,
        "work_admissions": admissions,
        "fabric_path": fabric_relative,
        "fabric_file_sha256": file_digest(fabric_path),
    }


def verify_bound_discovery_fabric(project_root: Path, objective_id: str, fabric_relative: str) -> dict[str, Any]:
    module = mission_control_module()
    mission = load_mission_state(project_root, objective_id)
    fabric_path = project_root / Path(*fabric_relative.split("/"))
    fabric = obj(read_json(fabric_path, "discovery fabric"), "discovery fabric")
    binding = obj(fabric.get("mission_control"), "discovery mission binding")
    if binding.get("state_sha256") != mission["state_sha256"] or binding.get("generation") != mission["generation"]:
        raise DirectorError("E_GOVERNOR", "discovery fabric binds a stale mission state")
    decision = obj(mission.get("governor_decision"), "governor decision")
    if binding.get("governor_decision_sha256") != decision.get("decision_sha256"):
        raise DirectorError("E_GOVERNOR", "discovery fabric binds a stale governor decision")
    admissions = obj(fabric.get("work_admissions"), "discovery work admissions")
    for work_class in ("research", "implementation"):
        receipt = module.verify_admission(obj(admissions.get(work_class), f"{work_class} admission"))
        if receipt.get("admitted") is not True or receipt.get("mission_state_sha256") != mission["state_sha256"] or receipt.get("governor_decision_sha256") != decision.get("decision_sha256"):
            raise DirectorError("E_GOVERNOR", f"discovery {work_class} admission is stale")
    return {"mission_state_sha256": mission["state_sha256"], "governor_decision_sha256": decision["decision_sha256"], "fabric_file_sha256": file_digest(fabric_path)}


def admit_mission_work(
''',
    )
    replace_once(
        path,
        '''    admission_root = workspace(project_root, objective_id) / "runtime/work-admissions"
    admission_path = admission_root / f"{slug(task_id)}.json"
''',
        '''    admission_path = _admission_receipt_path(project_root, objective_id, task_id)
''',
    )
    replace_once(
        path,
        '''    mission = refresh_mission_state(project_root, candidate["objective_id"])
''',
        '''    mission = load_mission_state(project_root, candidate["objective_id"])
''',
    )
    replace_once(
        path,
        '''    discovery_fabric = receipt["paths"]["discovery_fabric"]
    mission = mission_control_module().initialize_state(objective_id, objective)
    save_mission_state(project_root, mission)
    state = {
''',
        '''    discovery_fabric = receipt["paths"]["discovery_fabric"]
    mission = mission_control_module().initialize_state(objective_id, objective)
    save_mission_state(project_root, mission)
    discovery_binding = bind_discovery_fabric(project_root, objective_id, discovery_fabric)
    state = {
''',
    )
    replace_once(
        path,
        '''    saved = save_state(project_root, state)
    saved["next_action"]["mission_control"] = mission_binding(project_root, objective_id)
    return save_state(project_root, saved)
''',
        '''    state["next_action"].update(discovery_binding)
    return save_state(project_root, state)
''',
    )
    replace_once(
        path,
        '''    state = load_state(project_root, objective_id)
    base = workspace(project_root, objective_id)
    ingest_reality_spike_if_present(project_root, objective_id)
    stage = state["stage"]
''',
        '''    state = load_state(project_root, objective_id)
    base = workspace(project_root, objective_id)
    ingest_reality_spike_if_present(project_root, objective_id)
    refresh_mission_state(project_root, objective_id)
    stage = state["stage"]
''',
    )
    replace_once(
        path,
        '''        if missing:
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
''',
        '''        if missing:
            discovery_binding = bind_discovery_fabric(project_root, objective_id, state["artifacts"]["discovery_fabric"])
            verify_bound_discovery_fabric(project_root, objective_id, state["artifacts"]["discovery_fabric"])
            state["next_action"] = next_execute_fabric(
                "discovery",
                state["artifacts"]["discovery_fabric"],
                reason="Discovery proposals are still missing: " + ", ".join(missing),
            )
            state["next_action"].update(discovery_binding)
            return save_state(project_root, state)
''',
    )


def main() -> None:
    patch_director()
    print("execution enforcement v2 phase 5 applied")


if __name__ == "__main__":
    main()
