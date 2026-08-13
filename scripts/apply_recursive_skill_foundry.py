#!/usr/bin/env python3
from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS_ROOT = ROOT / "scripts/recursive-skill-foundry-bundle"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one patch anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def unpack_bundle() -> None:
    parts = sorted(PARTS_ROOT.glob("part-*.txt"))
    if not parts:
        raise SystemExit("recursive skill foundry bundle parts are missing")
    encoded = "".join(path.read_text(encoding="ascii").strip() for path in parts)
    data = base64.b64decode(encoded)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for member in archive.infolist():
            path = Path(member.filename)
            if path.is_absolute() or ".." in path.parts:
                raise SystemExit(f"unsafe bundle path: {member.filename}")
        archive.extractall(ROOT)


def patch_company_os_skill() -> None:
    path = ROOT / "skills/company-os/company-os/SKILL.md"
    replace_once(
        path,
        "| Capability library | Discover and bind a minimal audited skill bundle without loading the whole library into agent context | `$assign-capability-skills` |\n",
        "| Capability library | Discover and bind a minimal audited skill bundle without loading the whole library into agent context | `$assign-capability-skills` |\n"
        "| Recursive skill foundry | Convert repeated accepted mechanisms into immutable project local skills with strict simulation, bounded lineage, and versioned learning | `$recursive-skill-foundry` |\n",
    )
    replace_once(
        path,
        "An instance may adapt its operating method through evidence-backed, reversible experiments. It may not autonomously expand authority, weaken approvals, change cancellation precedence, mix project data, or approve its own adaptations. Promote a pattern into the shared core only after it improves at least three independent project instances and passes independent review.\n",
        "An instance may adapt its operating method through evidence-backed, reversible experiments. It may not autonomously expand authority, weaken approvals, change cancellation precedence, mix project data, or approve its own adaptations. Promote a pattern into the shared core only after it improves at least three independent project instances and passes independent review.\n\n"
        "Use `$recursive-skill-foundry` for project local procedural learning. An accepted and arrived mission records one idempotent learning snapshot without starting more work. One ordinary success remains evidence only. Repeated accepted objectives, or an explicit operator request, may create an immutable skill candidate that must pass strict quality, prompt simulation, lineage, permission, and checkpoint gates before local promotion. Failed uses queue a new version candidate and never rewrite the active skill.\n",
    )
    replace_once(
        path,
        """Resolve capabilities before manager dispatch and bind the selected capability
IDs to each artifact plan. Use the host's current available-skill registry for
first-party, installed, and plugin skills; use `$assign-capability-skills` for
the governed external catalog. A proposal, PRD, technical architecture,
spreadsheet, UI, or other specialized artifact must receive its required domain
and artifact-production skills. At acceptance, verify applied capability
receipts against the plan. Reading a general Company OS skill is not evidence
that the proposal, offer-design, product-requirements, research, or document-
production capability was used.
""",
        """Resolve capabilities before manager dispatch and bind the selected capability
IDs to each artifact plan. Search the project local `$recursive-skill-foundry`
registry first, verify its exact assignment, and load only the assigned versioned
entrypoints. Then use the host's current available-skill registry for first-party,
installed, and plugin skills; use `$assign-capability-skills` for the governed
external catalog. A proposal, PRD, technical architecture, spreadsheet, UI, or
other specialized artifact must receive its required domain and
artifact-production skills. At acceptance, verify applied capability receipts
against the plan. Reading a general Company OS skill is not evidence that the
proposal, offer-design, product-requirements, research, or document-production
capability was used.
""",
    )


def patch_manager_skill() -> None:
    path = ROOT / "skills/company-os/manage-company-program/SKILL.md"
    replace_once(
        path,
        "- Prefer supplied repositories, providers, SDKs, and frameworks. Integrate and run them before authorizing replacement; replacement needs concrete blocker evidence.\n",
        "- Prefer supplied repositories, providers, SDKs, and frameworks. Integrate and run them before authorizing replacement; replacement needs concrete blocker evidence.\n"
        "- Before loading broad external capability catalogs, resolve the current route against `$recursive-skill-foundry`. Verify the returned registry digest, version, entrypoint digest, tree digest, role, domain, and permission bounds before forwarding an exact local skill to a worker.\n",
    )
    replace_once(
        path,
        "On failure, diagnose the dominant defect, preserve independently passing dimensions, assign targeted rework, and reorganize if the bottleneck does not move. Do not respond to missing execution by requesting another general document.\n\n## Upward report\n",
        "On failure, diagnose the dominant defect, preserve independently passing dimensions, assign targeted rework, and reorganize if the bottleneck does not move. Do not respond to missing execution by requesting another general document.\n\n"
        "## Reusable learning\n\n"
        "Do not create a skill merely because one task succeeded. After acceptance, record a reusable mechanism observation only when exact artifact and validation evidence exists, the mechanism is narrower than the mission, trigger exclusions are explicit, and the procedure is stable. Use `$recursive-skill-foundry` to record the observation. The first ordinary observation remains evidence only. Repeated distinct accepted objectives, or an explicit operator request, may create and promote a versioned project local skill after strict simulation. Record failed uses rather than silently changing active instructions. Child skills must represent distinct submechanisms and remain inside the recursion bound.\n\n"
        "## Upward report\n",
    )


def patch_assignment_skill() -> None:
    path = ROOT / "skills/company-os/assign-capability-skills/SKILL.md"
    replace_once(
        path,
        """Start from the accepted mandatory-requirement list and semantic artifact plan.
For each artifact, derive the smallest capability classes needed to produce and
verify it: domain expertise, artifact production, named technology, and
independent review. Search each class separately. Do not send one long natural-
language query and treat an empty result as proof that no skill is needed.

""",
        """Start from the accepted mandatory-requirement list and semantic artifact plan.
For each artifact, derive the smallest capability classes needed to produce and
verify it: domain expertise, artifact production, named technology, and
independent review. Search each class separately. Do not send one long natural-
language query and treat an empty result as proof that no skill is needed.

Search the project local `$recursive-skill-foundry` before the external catalog when `.company-os/skill-foundry/registry.json` and the bound local skill root exist. Its resolver returns exact active versions and content digests. Verify that assignment before reading any entrypoint. Local skills remain subordinate to the same work definition, role, domain, permission, budget, cancellation, and acceptance boundaries. A local foundry miss is not proof that the external catalog is unnecessary.

""",
    )
    replace_once(
        path,
        """Retain the catalog digest, request digest, assignment digest, source commits,
entrypoint hashes, selected capability IDs, selection rationale, resolver result,
requirement-to-artifact-to-capability coverage matrix, and the manager's
independent artifact inspection. Skill selection is not evidence that the
deliverable works. A completed artifact must also return the applied capability
IDs and their task-local assignment receipt; a skill mentioned only in prose
does not count.
""",
        """Retain the project local foundry registry digest and versioned assignment when used, then retain the external catalog digest, request digest, assignment digest, source commits, entrypoint hashes, selected capability IDs, selection rationale, resolver result, requirement-to-artifact-to-capability coverage matrix, and the manager's independent artifact inspection. Skill selection is not evidence that the deliverable works. A completed artifact must also return the applied capability IDs and their task-local assignment receipt; a skill mentioned only in prose does not count. Record accepted or failed local skill use through `$recursive-skill-foundry` so improvement remains evidence bound and versioned.
""",
    )


def patch_director() -> None:
    path = ROOT / "skills/company-os/direct-outcome/scripts/direct_outcome.py"
    replace_once(
        path,
        """def mission_control_module():
    return load_module("mission-execution-control/scripts/mission_control.py", "company_os_director_mission_control")


def control_store_module():
""",
        """def mission_control_module():
    return load_module("mission-execution-control/scripts/mission_control.py", "company_os_director_mission_control")


def recursive_skill_foundry_module():
    return load_module("recursive-skill-foundry/scripts/recursive_skill_foundry.py", "company_os_director_recursive_skill_foundry")


def control_store_module():
""",
    )
    replace_once(
        path,
        """    if stage == "accepted":
        return state
""",
        """    if stage == "accepted":
        foundry = recursive_skill_foundry_module()
        try:
            captured = foundry.capture_accepted_outcome(
                project_root,
                objective_id,
                state,
                load_mission_state(project_root, objective_id),
            )
        except Exception as exc:
            event = {"event": "accepted_outcome_learning_capture_failed", "error": str(exc)}
            if event not in state["history"]:
                state["history"].append(event)
                return save_state(project_root, state)
            return state
        if captured is not None:
            snapshot = captured["snapshot"]
            snapshot_path = relative(project_root, Path(captured["path"]))
            state["artifacts"]["accepted_outcome_learning_snapshot"] = snapshot_path
            event = {
                "event": "accepted_outcome_learning_captured",
                "snapshot_path": snapshot_path,
                "snapshot_sha256": snapshot["snapshot_sha256"],
            }
            if event not in state["history"]:
                state["history"].append(event)
                return save_state(project_root, state)
        return state
""",
    )
    replace_once(
        path,
        """def status(project_root: Path, objective_id: str) -> dict[str, Any]:
    state = load_state(project_root, objective_id)
    mission = load_mission_state(project_root, objective_id)
    return {
""",
        """def status(project_root: Path, objective_id: str) -> dict[str, Any]:
    state = load_state(project_root, objective_id)
    mission = load_mission_state(project_root, objective_id)
    foundry = recursive_skill_foundry_module()
    foundry_state = foundry.foundry_root(project_root)
    registry = foundry.load_registry(foundry_state)
    return {
""",
    )
    replace_once(
        path,
        """        "director_sha256": state["director_sha256"],
        "mission_execution": {
""",
        """        "director_sha256": state["director_sha256"],
        "skill_foundry": {
            "registry_sha256": registry["registry_sha256"],
            "active_skills": registry["active"],
            "improvement_queue_count": len(registry["improvement_queue"]),
            "accepted_outcome_snapshot": state.get("artifacts", {}).get("accepted_outcome_learning_snapshot"),
        },
        "mission_execution": {
""",
    )


def patch_ci() -> None:
    path = ROOT / ".github/workflows/ci.yml"
    replace_once(
        path,
        "      - name: Verify repository suite\n        run: python3 -m unittest discover -s tests -v\n",
        "      - name: Verify repository suite\n        run: python3 -m unittest discover -s tests -v\n"
        "      - name: Verify recursive skill foundry simulation\n"
        "        run: python3 skills/company-os/recursive-skill-foundry/scripts/simulate_recursive_skill_foundry.py --output /tmp/recursive-skill-foundry-simulation.json\n",
    )
    replace_once(
        path,
        "          skills/company-os/navigation-control/scripts/navigation_control.py\n",
        "          skills/company-os/navigation-control/scripts/navigation_control.py\n"
        "          skills/company-os/recursive-skill-foundry/scripts/recursive_skill_foundry.py\n"
        "          skills/company-os/recursive-skill-foundry/scripts/simulate_recursive_skill_foundry.py\n",
    )


def clean_probe() -> None:
    probe = ROOT / "experiments/schema-probe/c.txt"
    if probe.exists():
        probe.unlink()
    parent = probe.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
    experiments = ROOT / "experiments"
    if experiments.exists() and not any(experiments.iterdir()):
        experiments.rmdir()


def main() -> None:
    unpack_bundle()
    patch_company_os_skill()
    patch_manager_skill()
    patch_assignment_skill()
    patch_director()
    patch_ci()
    clean_probe()
    print("recursive skill foundry bundle applied")


if __name__ == "__main__":
    main()
