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


def patch_mission_priority() -> None:
    path = ROOT / "skills/company-os/mission-execution-control/scripts/mission_control.py"
    replace_once(
        path,
        '''    supplied = re.findall(r"https://github\\.com/[^\\s)]+", objective)
    if supplied:
        result.append(
            {
                "capability_id": "supplied_implementation_integration",
                "label": "Supplied implementation integration",
                "critical": True,
                "priority": 95,
''',
        '''    supplied = re.findall(r"https://github\\.com/[^\\s)]+", objective)
    if supplied:
        result[0]["priority"] = 90
        result.append(
            {
                "capability_id": "supplied_implementation_integration",
                "label": "Supplied implementation integration",
                "critical": True,
                "priority": 100,
''',
    )


def patch_checkpoint_product() -> None:
    path = ROOT / "skills/company-os/mission-execution-control/scripts/checkpoint_product.py"
    replace_once(
        path,
        '''    commit_sha = None
    if commit:
        run_git(project_root, "rev-parse", "--is-inside-work-tree")
        run_git(project_root, "add", "--", *paths)
''',
        '''    commit_sha = None
    if commit:
        run_git(project_root, "rev-parse", "--is-inside-work-tree")
        staged_before = run_git(project_root, "diff", "--cached", "--name-only").stdout.splitlines()
        if staged_before:
            raise CheckpointError("refusing product checkpoint while unrelated staged files exist")
        if run_git(project_root, "config", "--get", "user.name", check=False).returncode != 0:
            run_git(project_root, "config", "user.name", "company-os-product-checkpoint-bot")
        if run_git(project_root, "config", "--get", "user.email", check=False).returncode != 0:
            run_git(project_root, "config", "user.email", "company-os-product-checkpoint-bot@users.noreply.github.com")
        run_git(project_root, "add", "--", *paths)
''',
    )


def patch_director() -> None:
    path = ROOT / "skills/company-os/direct-outcome/scripts/direct_outcome.py"
    replace_once(
        path,
        '''def reality_module():
    return load_module("accept-outcome-reality/scripts/accept_reality.py", "company_os_director_reality")


def artifact_observation_module():
''',
        '''def reality_module():
    return load_module("accept-outcome-reality/scripts/accept_reality.py", "company_os_director_reality")


def checkpoint_product_module():
    return load_module("mission-execution-control/scripts/checkpoint_product.py", "company_os_director_checkpoint_product")


def artifact_observation_module():
''',
    )
    replace_once(
        path,
        '''def finalize_mission_acceptance(
    project_root: Path,
    objective_id: str,
    loop: Mapping[str, Any],
''',
        '''def checkpoint_candidate(
    project_root: Path,
    objective_id: str,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    mission_module = mission_control_module()
    mission = load_mission_state(project_root, objective_id)
    verification_receipts = [
        {"path": item["path"], "sha256": item["sha256"]}
        for item in candidate.get("observations", [])
        if isinstance(item, Mapping) and isinstance(item.get("path"), str) and isinstance(item.get("sha256"), str)
    ]
    try:
        checkpoint = checkpoint_product_module().checkpoint(
            project_root,
            mission,
            candidate,
            verification_receipts,
            commit=(project_root / ".git").is_dir(),
            message=f"checkpoint(company-os): {candidate['candidate_id']}",
        )
    except Exception as exc:
        raise DirectorError("E_CHECKPOINT", f"product checkpoint failed: {exc}") from exc
    checkpoint_path = workspace(project_root, objective_id) / "runtime" / f"{candidate['candidate_id']}-checkpoint.json"
    write_json(checkpoint_path, checkpoint)
    stamp = mission_module.format_time(mission_module.now_utc())
    mission = mission_module.record_event(
        mission,
        mission_module.make_event(
            f"{candidate['candidate_id']}:checkpoint",
            "checkpoint_recorded",
            occurred_at=stamp,
            work_class="checkpoint",
            checkpoint=checkpoint,
        ),
    )
    save_mission_state(project_root, mission)
    return {
        "path": relative(project_root, checkpoint_path),
        "file_sha256": file_digest(checkpoint_path),
        "checkpoint_sha256": checkpoint["checkpoint_sha256"],
        "git_commit": checkpoint.get("git_commit"),
    }


def finalize_mission_acceptance(
    project_root: Path,
    objective_id: str,
    loop: Mapping[str, Any],
''',
    )
    replace_once(
        path,
        '''                candidate_path = base / f"runtime/{candidate_id}.json"; write_json(candidate_path, candidate)
                record_candidate_mission_evidence(project_root, objective_id, candidate)
                try: updated_loop = outcome_loop_module().record_candidate(project_root, loop, candidate)
''',
        '''                candidate_path = base / f"runtime/{candidate_id}.json"; write_json(candidate_path, candidate)
                record_candidate_mission_evidence(project_root, objective_id, candidate)
                checkpoint = checkpoint_candidate(project_root, objective_id, candidate)
                try: updated_loop = outcome_loop_module().record_candidate(project_root, loop, candidate)
''',
    )
    replace_once(
        path,
        '''                state["history"].append({"event": "candidate_auto_assembled", "candidate_id": candidate_id, "candidate_path": relative(project_root, candidate_path)})
''',
        '''                state["history"].append({"event": "candidate_auto_assembled", "candidate_id": candidate_id, "candidate_path": relative(project_root, candidate_path), "checkpoint": checkpoint})
''',
    )


def patch_skills() -> None:
    path = ROOT / "skills/company-os/company-os/SKILL.md"
    replace_once(
        path,
        '''| Executive execution governor | Measure distance from the original objective, identify the global bottleneck, allocate scarce time/tokens/cost toward reality, and trigger compression/critical-path modes when execution lags | `$govern-outcome-execution` |
| Execution | Deliver work through Sol manager tasks and bounded Luna labor with early real artifacts, runtime observation, targeted rework, verification, and decisions | `$manage-company-program`, `$execute-bounded-task`, `$force-first-execution`, `$autonomy-suite`, `$luna-execution-fabric` |
''',
        '''| Executive execution governor | Measure distance from the original objective, identify the global bottleneck, allocate scarce time/tokens/cost toward reality, and trigger compression/critical-path modes when execution lags | `$govern-outcome-execution` |
| Mission execution control | Enforce First Reality scope, work admission, hard deadlines, scheduler leases, evidence-bound capability state, replacement, and product checkpoints at controller boundaries | `$mission-execution-control` |
| Execution | Deliver work through Sol manager tasks and bounded Luna labor with early real artifacts, runtime observation, targeted rework, verification, and decisions | `$manage-company-program`, `$execute-bounded-task`, `$force-first-execution`, `$autonomy-suite`, `$luna-execution-fabric` |
''',
    )
    replace_once(
        path,
        '''For every autonomous build mission, the master runs `$govern-outcome-execution` on each meaningful heartbeat. The governor is the mission-level CEO/COO/CFO function above local managers.
''',
        '''For every autonomous build mission, the controller runs `$mission-execution-control` and `$govern-outcome-execution` at dispatch, retry, wake, evidence, expansion, evaluation, and packaging boundaries. These decisions are enforced state, not optional manager advice. The governor is the mission-level CEO/COO/CFO function above local managers.
''',
    )

    path = ROOT / "skills/company-os/manage-company-program/SKILL.md"
    replace_once(
        path,
        '''Operate `company-os.manager-role.v2`. The manager exists to make the requested outcome real. Planning, research, architecture, audits, receipts, and governance support execution; they are not substitutes for it.
''',
        '''Operate `company-os.manager-role.v2`. The manager exists to make the requested outcome real. Planning, research, architecture, audits, receipts, and governance support execution; they are not substitutes for it. Verify the exact `$mission-execution-control` state and work-admission receipt before dispatch; a paused class, stale generation, replacement order, or expired mission stops the old context.
''',
    )

    path = ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md"
    replace_once(
        path,
        '''2. Stop before work when a dependency is absent, malformed, stale, foreign, or
   unaccepted. Do not start downstream work speculatively.
''',
        '''2. Stop before work when a dependency is absent, malformed, stale, foreign, or
   unaccepted. Verify the bound `$mission-execution-control` state and work admission;
   stop when the mission generation changed, the work class is paused, the receipt is
   stale, or this worker was replaced. Do not start downstream work speculatively.
''',
    )


def main() -> None:
    patch_mission_priority()
    patch_checkpoint_product()
    patch_director()
    patch_skills()
    print("execution enforcement v2 phase 6 applied")


if __name__ == "__main__":
    main()
