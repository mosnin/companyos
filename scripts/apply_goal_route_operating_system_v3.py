#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_v2():
    path = ROOT / "scripts/apply_goal_route_operating_system_v2.py"
    spec = importlib.util.spec_from_file_location("company_os_goal_route_v2_patch", path)
    if spec is None or spec.loader is None:
        raise SystemExit("missing v2 integration script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replace_if_missing(path: Path, marker: str, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    if old not in text:
        raise SystemExit(f"{path}: missing integration anchor {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def run_patch(name: str, function) -> None:
    try:
        function()
    except SystemExit as exc:
        print(f"{name} requested fallback: {exc}")


def repair_organization_return() -> None:
    path = ROOT / "skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py"
    replace_if_missing(
        path,
        '"goal_route": route_manifest_binding',
        '    return {"program_id": project_id, "topology_mode": TOPOLOGY_MODE, "mission_control": mission_control, "work_admission": admission, "engineering_execution_contract": master_engineering, "program_version":',
        '    return {"program_id": project_id, "topology_mode": TOPOLOGY_MODE, "mission_control": mission_control, "work_admission": admission, "goal_route": route_manifest_binding, "goal_route_state": route_state if route_manifest_binding.get("embedded") is True else None, "engineering_execution_contract": master_engineering, "program_version":',
    )


def repair_doctrine() -> None:
    path = ROOT / "skills/company-os/company-os/SKILL.md"
    replace_if_missing(
        path,
        '| Goal route operating system |',
        '| Navigation control | Treat the original objective as the destination; continuously observe, act, verify, measure objective distance/velocity, and replan while keeping research/audits as subordinate sensors | `$navigation-control` |',
        '| Navigation control | Treat the original objective as the destination; continuously observe, act, verify, measure objective distance/velocity, and replan while keeping research/audits as subordinate sensors | `$navigation-control` |\n| Goal route operating system | Compile operator context, a concrete root goal, causal goal graph, route segments, sprints, recursive manager and worker goals, agent templates, cohesion, takeover, and evidence rollup | `$goal-route-system` |',
    )
    replace_if_missing(
        path,
        'controller first compiles `$goal-route-system`',
        'For every autonomous build mission, the controller runs `$mission-execution-control`, `$navigation-control`, and `$govern-outcome-execution` at dispatch, retry, wake, evidence, expansion, evaluation, and packaging boundaries.',
        'For every autonomous build mission, the controller first compiles `$goal-route-system`, then runs `$mission-execution-control`, `$navigation-control`, and `$govern-outcome-execution` at dispatch, retry, wake, evidence, expansion, evaluation, and packaging boundaries. Every master, manager, submanager, and worker receives a content addressed goal contract and route assignment; a prompt alone is not an executable goal.',
    )

    path = ROOT / "skills/company-os/manage-company-program/SKILL.md"
    replace_if_missing(
        path,
        'Before delegation, verify the exact `$goal-route-system` manager goal',
        'Operate `company-os.manager-role.v2`. The manager exists to make the requested outcome real.',
        'Operate `company-os.manager-role.v2`. The manager exists to make the requested outcome real. Before delegation, verify the exact `$goal-route-system` manager goal, parent and root bindings, route segment, sprint, success metrics, evidence requirements, authority, budget, cohesion contract, and takeover packet. A manager may decompose only into admitted child goals that causally cover the parent conditions.',
    )

    path = ROOT / "skills/autonomy-suite/execute-bounded-task/SKILL.md"
    replace_if_missing(
        path,
        'and its exact `$goal-route-system` leaf goal',
        'Operate contract version `company-os.worker-role.v2`. Read the compact work\npacket; do not request the root transcript or repeat the Company OS manual.',
        'Operate contract version `company-os.worker-role.v2`. Read the compact work\npacket and its exact `$goal-route-system` leaf goal; do not request the root transcript or repeat the Company OS manual. Before acting, identify the parent goal, current state, target state, required state changes, tasks, subtasks, evidence, authority, budget, route node, sprint, cohesion contract, and reporting destination. A prompt without that bound goal is not executable authority.',
    )

    path = ROOT / ".github/workflows/ci.yml"
    replace_if_missing(
        path,
        'Verify goal route simulation',
        '      - name: Verify execution regression lab\n        run: python3 skills/company-os/mission-execution-control/scripts/execution_regression_lab.py --json',
        '      - name: Verify execution regression lab\n        run: python3 skills/company-os/mission-execution-control/scripts/execution_regression_lab.py --json\n      - name: Verify goal route simulation\n        run: python3 skills/company-os/goal-route-system/scripts/goal_route.py simulate',
    )
    replace_if_missing(
        path,
        'skills/company-os/goal-route-system/scripts/goal_route.py',
        '          skills/company-os/navigation-control/scripts/navigation_control.py',
        '          skills/company-os/navigation-control/scripts/navigation_control.py\n          skills/company-os/goal-route-system/scripts/goal_route.py',
    )


def repair_route_runtime() -> None:
    path = ROOT / "skills/company-os/goal-route-system/scripts/goal_route.py"
    replace_if_missing(path, 'leaf_bonus = 20', '        leaf_bonus = 2 if level == "worker" else 0', '        leaf_bonus = 20 if level == "worker" else 0')
    replace_if_missing(path, 'plan("route_strategy", "Design the causal route and dependencies", "product-manager"', 'plan("route_strategy", "Design the causal route and dependencies", "chief-executive-manager"', 'plan("route_strategy", "Design the causal route and dependencies", "product-manager"')
    replace_if_missing(path, 'plan("first_reality", "Create the smallest connected real outcome", "technical-manager"', 'plan("first_reality", "Create the smallest connected real outcome", "delivery-submanager"', 'plan("first_reality", "Create the smallest connected real outcome", "technical-manager"')
    replace_if_missing(path, 'plan("capability_expansion", "Build the remaining required capabilities", "technical-manager"', 'plan("capability_expansion", "Build the remaining required capabilities", "delivery-submanager"', 'plan("capability_expansion", "Build the remaining required capabilities", "technical-manager"')


def verify_markers() -> None:
    checks = {
        ROOT / "skills/company-os/direct-outcome/scripts/direct_outcome.py": ["def goal_route_module", "goal_route_binding", "record_candidate_goal_evidence"],
        ROOT / "skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py": ["def _goal_route_module", "goal_assignment =", '"goal_route": route_manifest_binding'],
        ROOT / "skills/company-os/assemble-outcome-candidate/scripts/assemble_candidate.py": ["goal_route_state_sha256", '"goal_id": worker.get("goal_id")'],
        ROOT / "skills/company-os/goal-route-system/scripts/goal_route.py": ["def verify_assignment", "def accept_route", "def sealed_delegation_plan"],
    }
    for path, markers in checks.items():
        text = path.read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise SystemExit(f"{path}: incomplete integration markers {missing}")


def cleanup() -> None:
    for path in [
        ROOT / "scripts/apply_goal_route_operating_system_v2.py",
        ROOT / "scripts/repair_goal_route_operating_system_v2.py",
        ROOT / "scripts/apply_goal_route_operating_system_v3.py",
        ROOT / ".github/workflows/apply-goal-route-operating-system-v2.yml",
        ROOT / ".github/workflows/repair-goal-route-operating-system-v2.yml",
        ROOT / ".github/workflows/finalize-goal-route-operating-system-v2.yml",
        ROOT / ".github/workflows/apply-goal-route-operating-system.yml",
    ]:
        if path.exists():
            path.unlink()
    bundle = ROOT / "scripts/goal-route-bundle"
    if bundle.exists():
        for child in bundle.iterdir():
            child.unlink()
        bundle.rmdir()
    for name in ("goal-route-branch-verification.txt", "ignore-this", "last-probe", "oops", "pr-probe.txt", "upload-probe-4.txt"):
        path = ROOT / "tmp" / name
        if path.exists():
            path.unlink()


def main() -> None:
    v2 = load_v2()
    run_patch("goal route runtime", v2.patch_goal_route)
    run_patch("director", v2.patch_director)
    run_patch("organization", v2.patch_organization)
    repair_organization_return()
    run_patch("candidate", v2.patch_candidate)
    repair_doctrine()
    repair_route_runtime()
    verify_markers()
    cleanup()
    print("goal route operating system v3 integrated")


if __name__ == "__main__":
    main()
