#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_if_present(path: Path, old: str, new: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def require_contains(path: Path, marker: str) -> None:
    if marker not in path.read_text(encoding="utf-8"):
        raise SystemExit(f"{path}: required marker is unavailable: {marker}")


def harden_foundry() -> None:
    path = ROOT / "skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py"
    text = path.read_text(encoding="utf-8")

    old_parse = '''        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"').strip("'")
'''
    new_parse = '''        key, value = line.split(":", 1)
        raw_value = value.strip()
        if raw_value.startswith('"') and raw_value.endswith('"'):
            try:
                parsed_value = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                raise FoundryError("E_SKILL", f"invalid quoted frontmatter value for {key.strip()}") from exc
            fields[key.strip()] = str(parsed_value)
        else:
            fields[key.strip()] = raw_value.strip("'")
'''
    if old_parse in text:
        text = text.replace(old_parse, new_parse, 1)

    boundary_marker = '''def infer_description(name: str, request: str) -> str:
'''
    operational = '''def operational_request(request: str) -> str:
    request = require_text(request, "request")
    lowered = request.lower()
    if any(term in lowered for term in SECRET_TERMS) and any(term in lowered for term in EXFILTRATION_TERMS):
        return "Audit the repository for likely secret exposure without revealing, copying, transmitting, uploading, or exfiltrating secret values. Report only file locations, risk classes, and remediation steps."
    if any(pattern in lowered for pattern in UNSAFE_PATTERNS):
        return "Create a reusable procedure that detects and rejects attempts to bypass approvals, hide behavior, suppress monitoring, expose secrets, or create covert persistence."
    return request


'''
    if "def operational_request(request: str)" not in text:
        if boundary_marker not in text:
            raise SystemExit("foundry operational request anchor is unavailable")
        text = text.replace(boundary_marker, operational + boundary_marker, 1)

    old_create = '''def create_skill_files(skill_dir: Path, name: str, request: str, resources: Sequence[str], dependencies: Sequence[str]) -> None:
    description = infer_description(name, request)
    skill_dir.mkdir(parents=True, exist_ok=False)
    write_text(skill_dir / "SKILL.md", f"---\\nname: {name}\\ndescription: {description}\\n---\\n\\n{build_body(name, request, resources, dependencies)}")
    write_text(skill_dir / "agents" / "openai.yaml", "\\n".join(["interface:", f"  display_name: {json.dumps(title_case(name))}", f"  short_description: {json.dumps(description[:120])}", f"  default_prompt: {json.dumps(f'Use ${name} for this bounded reusable workflow: {request.strip()}')}", "policy:", "  allow_implicit_invocation: false", ""]))
'''
    new_create = '''def create_skill_files(skill_dir: Path, name: str, request: str, resources: Sequence[str], dependencies: Sequence[str]) -> None:
    description = infer_description(name, request)
    bounded_request = operational_request(request)
    skill_dir.mkdir(parents=True, exist_ok=False)
    write_text(skill_dir / "SKILL.md", f"---\\nname: {name}\\ndescription: {json.dumps(description, ensure_ascii=False)}\\n---\\n\\n{build_body(name, bounded_request, resources, dependencies)}")
    write_text(skill_dir / "agents" / "openai.yaml", "\\n".join(["interface:", f"  display_name: {json.dumps(title_case(name))}", f"  short_description: {json.dumps(description[:120])}", f"  default_prompt: {json.dumps(f'Use ${name} for this bounded reusable workflow: {bounded_request}')}", ""]))
'''
    if old_create in text:
        text = text.replace(old_create, new_create, 1)
    elif "bounded_request = operational_request(request)" not in text:
        raise SystemExit("foundry create skill hardening anchor is unavailable")

    text = text.replace('"coordinator_candidate_sha256": coordinator["candidate_sha256"]', '"coordinator_seed_candidate_sha256": coordinator["candidate_sha256"]')

    old_order = '''    write_json(coordinator_dir / "skill" / system_name / "assets" / "system_manifest.json", manifest)
    prior = load_candidate(coordinator_dir); skill_dir = coordinator_dir / "skill" / system_name; validation = validate_skill(skill_dir, threshold); simulation = simulate_skill(skill_dir); skill_files = skill_manifest(skill_dir); updated = dict(prior); updated.update({"skill_manifest": skill_files, "skill_sha256": digest(skill_files), "quality_score": validation["quality_score"], "validation_status": validation["status"], "simulation_status": simulation["status"]}); updated = seal_candidate(updated); write_json(coordinator_dir / "validation.json", validation); write_json(coordinator_dir / "simulation.json", simulation); write_json(coordinator_dir / "candidate.json", updated); coordinator.update({"candidate_sha256": updated["candidate_sha256"], "skill_sha256": updated["skill_sha256"], "quality_score": updated["quality_score"]})
'''
    new_order = '''    prior = load_candidate(coordinator_dir)
    write_json(coordinator_dir / "skill" / system_name / "assets" / "system_manifest.json", manifest)
    skill_dir = coordinator_dir / "skill" / system_name; validation = validate_skill(skill_dir, threshold); simulation = simulate_skill(skill_dir); skill_files = skill_manifest(skill_dir); updated = dict(prior); updated.update({"skill_manifest": skill_files, "skill_sha256": digest(skill_files), "quality_score": validation["quality_score"], "validation_status": validation["status"], "simulation_status": simulation["status"]}); updated = seal_candidate(updated); write_json(coordinator_dir / "validation.json", validation); write_json(coordinator_dir / "simulation.json", simulation); write_json(coordinator_dir / "candidate.json", updated); coordinator.update({"candidate_sha256": updated["candidate_sha256"], "skill_sha256": updated["skill_sha256"], "quality_score": updated["quality_score"]})
'''
    if old_order in text:
        text = text.replace(old_order, new_order, 1)

    old_replay = '''    if path.exists():
        existing = require_object(read_json(path, "existing field evidence"), "existing field evidence")
        return {"status": "replayed", "path": path.relative_to(project_root).as_posix(), "receipt_sha256": existing["receipt_sha256"]}
'''
    new_replay = '''    if path.exists():
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
    if old_replay in text:
        text = text.replace(old_replay, new_replay, 1)

    path.write_text(text, encoding="utf-8")
    require_contains(path, "bounded_request = operational_request(request)")
    require_contains(path, "field evidence run id was reused with changed content")
    require_contains(path, "coordinator_seed_candidate_sha256")


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
    query = " ".join(value for value in (str(lane.get("lane_id") or ""), str(lane.get("mandate") or ""), worker_task) if value)
    results = module.search_registry(project_root, query, limit=4).get("results", [])
    selected = [item for item in results if isinstance(item, Mapping) and int(item.get("score", 0)) >= 4][:2]
    if not selected:
        return None
    names = [str(item["skill_name"]) for item in selected]
    rationale = {name: "The promoted project skill directly matches the active outcome lane and was selected from the content-addressed project registry." for name in names}
    lane_id = re.sub(r"[^a-z0-9]+", "-", str(lane.get("lane_id") or "lane").lower()).strip("-")
    return module.assign_project_skills(project_root, assignment_id=f"outcome-{lane_id or 'lane'}-worker", role="worker", skill_names=names, execution_order=names, rationale=rationale)


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


def patch_tests() -> None:
    path = ROOT / "tests/test_recursive_skill_foundry_organization.py"
    old = '''        with self.assertRaises(FOUNDRY.FoundryError) as caught:
            ORG._project_skill_assignment(
                self.project,
                {
                    "lane_id": "artifact:sdk-examples",
                    "mandate": "Validate SDK examples against the API schema.",
                },
                "Run the SDK example validation procedure.",
            )
        self.assertEqual(caught.exception.code, "E_DIGEST")
'''
    new = '''        with self.assertRaises(Exception) as caught:
            ORG._project_skill_assignment(
                self.project,
                {
                    "lane_id": "artifact:sdk-examples",
                    "mandate": "Validate SDK examples against the API schema.",
                },
                "Run the SDK example validation procedure.",
            )
        self.assertEqual(getattr(caught.exception, "code", None), "E_DIGEST")
'''
    replace_if_present(path, old, new)


def make_scripts_executable() -> None:
    for relative in (
        "skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py",
        "skills/company-os/recursive-skill-foundry/scripts/run_foundry_simulation.py",
    ):
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"missing foundry script: {relative}")
        path.chmod(0o755)


def remove_probe_files() -> None:
    for relative in ("tmp/foundry-placeholder.txt", "experiments/schema-probe/c.txt"):
        path = ROOT / relative
        if path.exists() or path.is_symlink():
            path.unlink()
    for relative in ("tmp", "experiments/schema-probe", "experiments"):
        path = ROOT / relative
        try:
            path.rmdir()
        except OSError:
            pass


def main() -> None:
    harden_foundry()
    patch_agent_interface()
    patch_organization()
    patch_tests()
    make_scripts_executable()
    remove_probe_files()
    print("recursive skill foundry final hardening applied")


if __name__ == "__main__":
    main()
