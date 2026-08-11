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


def patch_mission_control() -> None:
    path = ROOT / "skills/company-os/mission-execution-control/scripts/mission_control.py"
    replace_once(
        path,
        'WAKE_SCHEMA = "company-os.scheduler-wake.v1"\nCHECKPOINT_SCHEMA = "company-os.product-checkpoint-request.v1"\n',
        'WAKE_SCHEMA = "company-os.scheduler-wake.v1"\nREALITY_SPIKE_SCHEMA = "company-os.reality-spike-receipt.v1"\nCHECKPOINT_SCHEMA = "company-os.product-checkpoint-request.v1"\n',
    )
    replace_once(
        path,
        '''def update_scope(
    raw_state: Mapping[str, Any],
    artifact_contract: Mapping[str, Any],
    *,
    explicit_first_reality: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
''',
        '''def verify_reality_spike(
    project_root: Path,
    raw: Mapping[str, Any],
    *,
    objective_id: str | None = None,
) -> dict[str, Any]:
    value = deepcopy(dict(raw))
    if value.get("$schema") != REALITY_SPIKE_SCHEMA:
        raise MissionControlError("E_SCHEMA", "reality spike receipt schema is invalid")
    if objective_id is not None and value.get("objective_id") != objective_id:
        raise MissionControlError("E_BINDING", "reality spike objective is incorrect")
    observed = sha256(value.get("receipt_sha256"), "receipt_sha256")
    unsigned = deepcopy(value)
    unsigned["receipt_sha256"] = None
    if digest(unsigned) != observed:
        raise MissionControlError("E_DIGEST", "reality spike receipt changed")
    root = project_root.resolve()
    artifacts = value.get("artifacts")
    observations = value.get("observations")
    commands = value.get("commands")
    blockers = value.get("blockers")
    if not isinstance(artifacts, list) or not artifacts:
        raise MissionControlError("E_SPIKE", "reality spike contains no product artifacts")
    if not isinstance(observations, list) or not observations:
        raise MissionControlError("E_SPIKE", "reality spike contains no runtime observations")
    if not isinstance(commands, list) or not commands:
        raise MissionControlError("E_SPIKE", "reality spike contains no executed commands")
    if not isinstance(blockers, list):
        raise MissionControlError("E_SPIKE", "reality spike blockers must be an array")
    for collection_name, records in (("artifacts", artifacts), ("observations", observations)):
        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                raise MissionControlError("E_SPIKE", f"{collection_name}[{index}] is invalid")
            capability_id = text(record.get("capability_id"), f"{collection_name}[{index}].capability_id")
            relative = safe_relative(record.get("path"), f"{collection_name}[{index}].path")
            expected = sha256(record.get("sha256"), f"{collection_name}[{index}].sha256")
            resolved = (root / Path(*PurePosixPath(relative).parts)).resolve(strict=True)
            if (resolved != root and root not in resolved.parents) or not resolved.is_file() or resolved.is_symlink():
                raise MissionControlError("E_PATH", f"{collection_name}[{index}] is not a regular project file")
            if file_digest(resolved) != expected:
                raise MissionControlError("E_DIGEST", f"{collection_name}[{index}] bytes changed")
            if collection_name == "observations" and record.get("kind") not in {"runtime_observed", "journey_connected"}:
                raise MissionControlError("E_SPIKE", f"unsupported spike observation kind for {capability_id}")
    for index, command in enumerate(commands):
        if not isinstance(command, Mapping):
            raise MissionControlError("E_SPIKE", f"commands[{index}] is invalid")
        text(command.get("command"), f"commands[{index}].command")
        integer(command.get("exit_code"), f"commands[{index}].exit_code", minimum=0)
    return value


def ingest_reality_spike(
    raw_state: Mapping[str, Any],
    project_root: Path,
    raw_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    state = verify_state(raw_state)
    receipt = verify_reality_spike(project_root, raw_receipt, objective_id=state["objective_id"])
    stamp = text(receipt.get("completed_at"), "completed_at")
    parse_time(stamp, "completed_at")
    receipt_id = receipt["receipt_sha256"][:16]
    known = {item["capability_id"] for item in state["capabilities"]}
    for index, artifact in enumerate(receipt["artifacts"]):
        capability_id = artifact["capability_id"]
        if capability_id not in known:
            continue
        current = next(item for item in state["capabilities"] if item["capability_id"] == capability_id)
        if current["state"] != "missing":
            continue
        state = record_event(
            state,
            make_event(
                f"spike:{receipt_id}:artifact:{index}",
                "artifact_materialized",
                occurred_at=stamp,
                work_class="implementation",
                capability_id=capability_id,
                evidence={"kind": "reality_spike_artifact", "path": artifact["path"], "sha256": artifact["sha256"], "capability_id": capability_id},
            ),
        )
    ordered = sorted(
        receipt["observations"],
        key=lambda item: (0 if item.get("kind") == "runtime_observed" else 1, str(item.get("capability_id")), str(item.get("path"))),
    )
    for index, observation in enumerate(ordered):
        capability_id = observation["capability_id"]
        if capability_id not in known:
            continue
        current = next(item for item in state["capabilities"] if item["capability_id"] == capability_id)
        expected = "partial" if observation["kind"] == "runtime_observed" else "runnable"
        if current["state"] != expected:
            continue
        state = record_event(
            state,
            make_event(
                f"spike:{receipt_id}:observation:{index}",
                observation["kind"],
                occurred_at=stamp,
                work_class="runtime" if observation["kind"] == "runtime_observed" else "integration",
                capability_id=capability_id,
                evidence={"kind": observation.get("observation_kind") or observation["kind"], "path": observation["path"], "sha256": observation["sha256"], "capability_id": capability_id},
                observation_kind=observation.get("observation_kind") or observation["kind"],
            ),
        )
    return state


def update_scope(
    raw_state: Mapping[str, Any],
    artifact_contract: Mapping[str, Any],
    *,
    explicit_first_reality: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
''',
    )
    replace_once(
        path,
        '''    for capability in capabilities:
        prior = old.get(capability["capability_id"])
        if prior:
            capability["state"] = prior.get("state", "missing")
            capability["evidence"] = deepcopy(prior.get("evidence", []))
            if prior.get("existing_implementation"):
                capability["existing_implementation"] = prior["existing_implementation"]
    state["first_reality"] = first
''',
        '''    for capability in capabilities:
        prior = old.get(capability["capability_id"])
        if prior:
            capability["state"] = prior.get("state", "missing")
            capability["evidence"] = deepcopy(prior.get("evidence", []))
            if prior.get("existing_implementation"):
                capability["existing_implementation"] = prior["existing_implementation"]
    selected_ids = list(first.get("required_capability_ids", []))
    selected = {item["capability_id"]: item for item in capabilities if item["capability_id"] in selected_ids}
    provisional = old.get("first_real_artifact")
    if provisional and selected_ids:
        target = selected[selected_ids[0]]
        if CAPABILITY_ORDER.get(provisional.get("state"), 0) > CAPABILITY_ORDER.get(target.get("state"), 0):
            target["state"] = provisional["state"]
            target["evidence"] = deepcopy(provisional.get("evidence", []))
    rendered = old.get("rendered_user_path")
    if rendered and selected:
        ui_targets = [
            item for item in selected.values()
            if any(marker in (item.get("label") or "").casefold() for marker in ("browser", "ui", "interface", "app", "widget", "game"))
        ]
        target = ui_targets[0] if ui_targets else selected[selected_ids[0]]
        if CAPABILITY_ORDER.get(rendered.get("state"), 0) > CAPABILITY_ORDER.get(target.get("state"), 0):
            target["state"] = rendered["state"]
            target["evidence"] = deepcopy(rendered.get("evidence", []))
    supplied = old.get("supplied_implementation_integration")
    if supplied and selected_ids:
        selected[selected_ids[0]]["existing_implementation"] = supplied.get("existing_implementation")
    state["first_reality"] = first
''',
    )
    replace_once(
        path,
        '''    check = sub.add_parser("verify")
    check.add_argument("--state", type=Path, required=True)

    args = parser.parse_args()
''',
        '''    wake_create = sub.add_parser("make-wake")
    wake_create.add_argument("--state", type=Path, required=True)
    wake_create.add_argument("--wake-id", required=True)
    wake_create.add_argument("--not-before", required=True)
    wake_create.add_argument("--reason", required=True)
    wake_create.add_argument("--output", type=Path, required=True)

    wake_admit = sub.add_parser("admit-wake")
    wake_admit.add_argument("--state", type=Path, required=True)
    wake_admit.add_argument("--wake", type=Path, required=True)
    wake_admit.add_argument("--output", type=Path, required=True)

    check = sub.add_parser("verify")
    check.add_argument("--state", type=Path, required=True)

    args = parser.parse_args()
''',
    )
    replace_once(
        path,
        '''        elif args.command == "admit-work":
            result = admit_work(load(args.state), json.loads(args.request.read_text(encoding="utf-8")))
            save(args.output, result)
        else:
            result = load(args.state)
''',
        '''        elif args.command == "admit-work":
            result = admit_work(load(args.state), json.loads(args.request.read_text(encoding="utf-8")))
            save(args.output, result)
        elif args.command == "make-wake":
            current = load(args.state)
            result = make_wake(
                current,
                wake_id=args.wake_id,
                not_before=args.not_before,
                reason=args.reason,
                expected_state_sha256=current["state_sha256"],
            )
            save(args.output, result)
        elif args.command == "admit-wake":
            result = admit_wake(load(args.state), json.loads(args.wake.read_text(encoding="utf-8")))
            save(args.output, result)
        else:
            result = load(args.state)
''',
    )


def patch_bootstrap() -> None:
    path = ROOT / "skills/company-os/bootstrap-outcome/scripts/bootstrap_outcome.py"
    replace_once(
        path,
        '''            f"Write a receipt at {spike_scope}/reality-spike-receipt.json with schema company-os.reality-spike-receipt.v1, exact product artifact paths and sha256 values, commands executed, runtime result, observation evidence paths and sha256 values, and unresolved blockers. "
''',
        '''            f"Write a receipt at {spike_scope}/reality-spike-receipt.json with schema company-os.reality-spike-receipt.v1. It must contain objective_id {objective_id!r}, completed_at RFC3339 UTC, artifacts with capability_id first_real_artifact or rendered_user_path plus exact project-relative path and sha256, commands with exact command and nonnegative exit_code, observations with capability_id, kind runtime_observed or journey_connected, observation_kind, exact evidence path and sha256, blockers as an array, and receipt_sha256 over the canonical object with receipt_sha256 null. "
''',
    )


def patch_director() -> None:
    path = ROOT / "skills/company-os/direct-outcome/scripts/direct_outcome.py"
    replace_once(path, "import re\nfrom pathlib", "import re\nfrom datetime import timedelta\nfrom pathlib")
    replace_once(
        path,
        '''def save_state(project_root: Path, state: Mapping[str, Any]) -> dict[str, Any]:
    result = seal(state)
    write_json(state_path(project_root, result["objective_id"]), result)
    return result
''',
        '''def _attach_scheduler_wake(project_root: Path, state: Mapping[str, Any]) -> dict[str, Any]:
    candidate = dict(state)
    next_action = candidate.get("next_action")
    mission_path = mission_state_path(project_root, candidate["objective_id"])
    if not isinstance(next_action, Mapping) or next_action.get("action") != "execute_fabric" or not mission_path.is_file():
        return candidate
    mission = refresh_mission_state(project_root, candidate["objective_id"])
    if mission.get("status") != "active":
        return candidate
    decision = obj(mission.get("governor_decision"), "governor decision")
    interval = {"normal": 8, "compression": 4, "critical_path": 3, "reality_closure": 2}.get(decision.get("mode"), 5)
    if next_action.get("stage") in {"loop", "build_candidate", "rework", "evaluate"}:
        interval = min(interval, 5)
    not_before = mission_control_module().now_utc() + timedelta(minutes=interval)
    wake_id = f"{candidate['objective_id']}:{candidate.get('stage')}:{len(candidate.get('history', []))}:{mission['generation']}"
    wake = mission_control_module().make_wake(
        mission,
        wake_id=wake_id,
        not_before=mission_control_module().format_time(not_before),
        reason=str(next_action.get("reason") or "Continue the current Company OS critical path."),
        expected_state_sha256=mission["state_sha256"],
    )
    wake_path = workspace(project_root, candidate["objective_id"]) / "scheduler" / f"wake-{slug(wake_id)}.json"
    write_json(wake_path, wake)
    updated_action = dict(next_action)
    updated_action["scheduler_wake"] = {
        "path": relative(project_root, wake_path),
        "file_sha256": file_digest(wake_path),
        "wake_sha256": wake["wake_sha256"],
        "not_before": wake["not_before"],
        "expires_at": wake["expires_at"],
        "generation": wake["generation"],
        "idempotency_key": wake["idempotency_key"],
    }
    candidate["next_action"] = updated_action
    return candidate


def save_state(project_root: Path, state: Mapping[str, Any]) -> dict[str, Any]:
    result = seal(_attach_scheduler_wake(project_root, state))
    write_json(state_path(project_root, result["objective_id"]), result)
    return result
''',
    )
    replace_once(
        path,
        '''def admit_mission_work(
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
''',
        '''def admit_mission_work(
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
    dispatch_event = module.make_event(
        f"dispatch:{task_id}:{state['generation']}",
        "work_recorded",
        work_class=work_class,
        units=1.0,
    )
    state = module.record_event(state, dispatch_event)
    save_mission_state(project_root, state)
    request = {
''',
    )
    replace_once(
        path,
        '''def proposal_paths(base: Path) -> list[Path]:
''',
        '''def ingest_reality_spike_if_present(project_root: Path, objective_id: str) -> None:
    receipt_path = workspace(project_root, objective_id) / "reality-spike/reality-spike-receipt.json"
    if not receipt_path.is_file():
        return
    mission = load_mission_state(project_root, objective_id)
    receipt = obj(read_json(receipt_path, "reality spike receipt"), "reality spike receipt")
    updated = mission_control_module().ingest_reality_spike(mission, project_root, receipt)
    save_mission_state(project_root, updated)


def proposal_paths(base: Path) -> list[Path]:
''',
    )
    replace_once(
        path,
        '''    state = load_state(project_root, objective_id)
    base = workspace(project_root, objective_id)
    stage = state["stage"]
''',
        '''    state = load_state(project_root, objective_id)
    base = workspace(project_root, objective_id)
    ingest_reality_spike_if_present(project_root, objective_id)
    stage = state["stage"]
''',
    )


def main() -> None:
    patch_mission_control()
    patch_bootstrap()
    patch_director()
    print("execution enforcement v2 phase 3 applied")


if __name__ == "__main__":
    main()
