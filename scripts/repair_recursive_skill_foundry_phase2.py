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


def patch_foundry() -> None:
    path = ROOT / "skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py"
    text = path.read_text(encoding="utf-8")

    text = text.replace('"coordinator_candidate_sha256": coordinator["candidate_sha256"]', '"coordinator_seed_candidate_sha256": coordinator["candidate_sha256"]')

    old = '''    if path.exists():
        existing = require_object(read_json(path, "existing field evidence"), "existing field evidence")
        return {"status": "replayed", "path": path.relative_to(project_root).as_posix(), "receipt_sha256": existing["receipt_sha256"]}
'''
    new = '''    if path.exists():
        existing = require_object(read_json(path, "existing field evidence"), "existing field evidence")
        expected = {
            "skill_name": candidate["skill_name"],
            "skill_version": candidate["version"],
            "skill_sha256": candidate["skill_sha256"],
            "run_id": normalize_name(run_id),
            "objective_id": normalize_name(objective_id),
            "project_id": normalize_name(project_id),
            "outcome": outcome,
            "artifact_sha256": artifact_sha256,
            "notes": require_text(notes, "notes"),
        }
        changed = [key for key, value in expected.items() if existing.get(key) != value]
        if changed:
            raise FoundryError("E_COLLISION", "field evidence run id was reused with changed content: " + ", ".join(changed))
        return {"status": "replayed", "path": path.relative_to(project_root).as_posix(), "receipt_sha256": existing["receipt_sha256"]}
'''
    if old in text:
        text = text.replace(old, new, 1)

    path.write_text(text, encoding="utf-8")


def patch_agent_interface() -> None:
    path = ROOT / "skills/company-os/recursive-skill-foundry/agents/openai.yaml"
    path.write_text(
        '''interface:
  display_name: "Recursive Skill Foundry"
  short_description: "Forge and evolve reusable project skills"
  default_prompt: "Use $recursive-skill-foundry to create or evolve this bounded reusable capability inside Company OS."
''',
        encoding="utf-8",
    )


def patch_organization() -> None:
    path = ROOT / "skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py"
    text = path.read_text(encoding="utf-8")

    helper_anchor = '''def _engineering_root(objective_id: str, request: Mapping[str, Any]) -> dict[str, Any]:
'''
    helper = '''def _skill_foundry_module():
    path = Path(__file__).resolve().parents[2] / "recursive-skill-foundry/scripts/skill_foundry.py"
    spec = importlib.util.spec_from_file_location("company_os_recursive_skill_foundry", path)
    if spec is None or spec.loader is None:
        raise OrganizationError("E_SKILL", "recursive skill foundry is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _project_skill_assignment(
    project_root: Path,
    lane: Mapping[str, Any],
    worker_task: str,
) -> dict[str, Any] | None:
    registry = project_root / ".company-os/skill-foundry/registry.json"
    if not registry.is_file():
        return None
    module = _skill_foundry_module()
    query = " ".join(
        value
        for value in (
            str(lane.get("lane_id") or ""),
            str(lane.get("mandate") or ""),
            worker_task,
        )
        if value
    )
    results = module.search_registry(project_root, query, limit=4).get("results", [])
    selected = [item for item in results if isinstance(item, Mapping) and int(item.get("score", 0)) >= 4][:2]
    if not selected:
        return None
    names = [str(item["skill_name"]) for item in selected]
    rationale = {
        name: f"The promoted project skill directly matches the active outcome lane and was selected from the content-addressed project registry."
        for name in names
    }
    lane_id = re.sub(r"[^a-z0-9]+", "-", str(lane.get("lane_id") or "lane").lower()).strip("-")
    return module.assign_project_skills(
        project_root,
        assignment_id=f"outcome-{lane_id or 'lane'}-worker",
        role="worker",
        skill_names=names,
        execution_order=names,
        rationale=rationale,
    )


'''
    if "def _skill_foundry_module():" not in text:
        if helper_anchor not in text:
            raise SystemExit("organization helper anchor is unavailable")
        text = text.replace(helper_anchor, helper + helper_anchor, 1)

    assignment_anchor = '''        outcome_context["engineering_execution_contract"] = worker_engineering
        work_class = "evaluation" if state.get("phase") == "evaluate" else "repair" if state.get("phase") == "rework" else "implementation"
        outcome_context["mission_control"] = mission_control
        outcome_context["work_admission"] = admission
'''
    assignment_patch = '''        outcome_context["engineering_execution_contract"] = worker_engineering
        work_class = "evaluation" if state.get("phase") == "evaluate" else "repair" if state.get("phase") == "rework" else "implementation"
        outcome_context["mission_control"] = mission_control
        outcome_context["work_admission"] = admission
        project_skill_assignment = _project_skill_assignment(project_root, lane, worker_task)
        if project_skill_assignment is not None:
            outcome_context["project_skill_assignment"] = project_skill_assignment
            ordered = ", ".join(project_skill_assignment["execution_order"])
            worker_task += f" Load only the exact bound project skill entrypoints in this order: {ordered}. Verify every entrypoint digest before use and do not discover unassigned project skills."
'''
    if "project_skill_assignment = _project_skill_assignment" not in text:
        if assignment_anchor not in text:
            raise SystemExit("organization assignment anchor is unavailable")
        text = text.replace(assignment_anchor, assignment_patch, 1)

    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_foundry()
    patch_agent_interface()
    patch_organization()
    print("recursive skill foundry phase 2 repairs applied")


if __name__ == "__main__":
    main()
