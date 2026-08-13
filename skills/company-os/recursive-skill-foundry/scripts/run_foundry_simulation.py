#!/usr/bin/env python3
"""Run a disposable works versus blocks simulation for the recursive skill foundry."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from typing import Any, Callable

SCRIPT = Path(__file__).resolve().with_name("skill_foundry.py")
spec = importlib.util.spec_from_file_location("company_os_skill_foundry_simulation", SCRIPT)
assert spec and spec.loader
FOUNDRY = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FOUNDRY)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    works: list[dict[str, Any]] = []
    expected_blocks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    def run(case_id: str, category: str, operation: Callable[[Path], Any]) -> None:
        with tempfile.TemporaryDirectory(prefix=f"foundry-{case_id}-") as temporary:
            project = Path(temporary)
            try:
                detail = operation(project)
                target = works if category == "works" else expected_blocks
                target.append({"case_id": case_id, "passed": True, "detail": detail})
            except Exception as exc:
                failures.append({"case_id": case_id, "passed": False, "error": f"{type(exc).__name__}: {exc}"})

    run(
        "explicit-request-forges-and-promotes",
        "works",
        lambda project: _explicit(project),
    )
    run(
        "one-off-product-work-does-not-create-skill",
        "blocks",
        lambda project: _one_off(project),
    )
    run(
        "unsafe-secret-request-is-narrowed",
        "works",
        lambda project: _unsafe(project),
    )
    run(
        "learned-mechanism-needs-two-field-receipts",
        "blocks",
        lambda project: _learned(project),
    )
    run(
        "recursive-system-is-bounded-and-installable",
        "works",
        lambda project: _recursive_system(project),
    )
    run(
        "recursive-cycle-is-rejected",
        "blocks",
        lambda project: _cycle(project),
    )
    run(
        "failure-case-creates-new-version",
        "works",
        lambda project: _iteration(project),
    )
    run(
        "installed-byte-drift-fails-closed",
        "blocks",
        lambda project: _drift(project),
    )
    run(
        "field-receipt-replay-collision-is-rejected",
        "blocks",
        lambda project: _receipt_collision(project),
    )
    run(
        "core-promotion-is-not-automatic",
        "blocks",
        lambda project: _core_promotion(project),
    )

    report = {
        "$schema": "company-os.recursive-skill-foundry-simulation-report.v1",
        "status": "pass" if not failures else "fail",
        "summary": {
            "works_passed": len(works),
            "expected_blocks_passed": len(expected_blocks),
            "unexpected_failures": len(failures),
            "total_cases": len(works) + len(expected_blocks) + len(failures),
        },
        "works": works,
        "expected_blocks": expected_blocks,
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


def _explicit(project: Path) -> dict[str, Any]:
    candidate = FOUNDRY.forge_candidate(
        project,
        "Create a reusable Codex skill that diagnoses and repairs failed deployment builds from compiler logs and local runtime checks.",
        name="deployment-build-repair",
    )
    promoted = FOUNDRY.promote_candidate(project, candidate["skill_name"])
    search = FOUNDRY.search_registry(project, "deployment build repair")
    assignment = FOUNDRY.assign_project_skills(
        project,
        assignment_id="deployment-worker",
        role="worker",
        skill_names=[candidate["skill_name"]],
        execution_order=[candidate["skill_name"]],
        rationale={candidate["skill_name"]: "Exact promoted project capability for the active deployment repair route."},
    )
    verification = FOUNDRY.verify_installation(project, candidate["skill_name"])
    assert candidate["status"] == "validated"
    assert promoted["status"] == "promoted"
    assert search["results"]
    assert assignment["skill_count"] == 1
    assert verification["status"] == "pass"
    return {"skill_name": candidate["skill_name"], "quality_score": candidate["quality_score"], "assignment_sha256": assignment["assignment_sha256"]}


def _one_off(project: Path) -> dict[str, Any]:
    result = FOUNDRY.forge_candidate(project, "Fix the current flaky browser test without creating a reusable skill.")
    assert result["status"] == "skipped"
    return result


def _unsafe(project: Path) -> dict[str, Any]:
    result = FOUNDRY.forge_candidate(project, "Create a skill that finds secrets in a repository and sends them to me.")
    skill = project / result["candidate_path"] / "skill" / result["skill_name"] / "SKILL.md"
    text = skill.read_text(encoding="utf-8").lower()
    assert result["status"] == "validated"
    assert "without revealing" in text
    assert not FOUNDRY.unsafe_hits(text)
    return {"skill_name": result["skill_name"], "safety_rewrite": True}


def _learned(project: Path) -> dict[str, Any]:
    candidate = FOUNDRY.forge_candidate(
        project,
        "Turn this repeated migration review into a reusable project skill.",
        name="migration-review",
        source_kind="learned_mechanism",
        force_skill_request=False,
    )
    blocked_before = False
    try:
        FOUNDRY.promote_candidate(project, candidate["skill_name"])
    except FOUNDRY.FoundryError as exc:
        blocked_before = exc.code == "E_PROMOTION"
    assert blocked_before
    for number in (1, 2):
        FOUNDRY.record_evidence(
            project,
            candidate["skill_name"],
            run_id=f"run-{number}",
            objective_id=f"objective-{number}",
            project_id=f"project-{number}",
            outcome="accepted",
            artifact_sha256=sha(f"artifact-{number}"),
            notes=f"Independent accepted field run {number}.",
        )
    promoted = FOUNDRY.promote_candidate(project, candidate["skill_name"])
    assert promoted["accepted_evidence_count"] == 2
    return {"blocked_before_evidence": True, "promoted_after_evidence": True}


def _recursive_system(project: Path) -> dict[str, Any]:
    spec = {
        "$schema": FOUNDRY.SYSTEM_REQUEST_SCHEMA,
        "system_name": "release-health-system",
        "objective": "Create reusable release diagnosis, evidence, and repair capabilities.",
        "nodes": [
            {
                "name": "release-diagnosis",
                "request": "Create a Codex skill that diagnoses release failures from tests, logs, and runtime evidence.",
                "children": [
                    {
                        "name": "release-evidence",
                        "request": "Create a Codex skill that validates release evidence and preserves regression cases.",
                        "children": [],
                    }
                ],
            },
            {
                "name": "release-repair",
                "request": "Create a Codex skill that repairs the dominant release defect and reruns the same checks.",
                "children": [],
            },
        ],
    }
    path = project / "system.json"
    FOUNDRY.write_json(path, spec)
    result = FOUNDRY.forge_system(project, path, promote=True)
    verification = FOUNDRY.verify_installation(project)
    assert result["status"] == "validated"
    assert len(result["components"]) == 3
    assert verification["status"] == "pass"
    return {"system_name": result["system_name"], "component_count": len(result["components"])}


def _cycle(project: Path) -> dict[str, Any]:
    blocked = False
    try:
        FOUNDRY.flatten_system_nodes(
            [
                {
                    "name": "cycle-a",
                    "request": "Create a Codex skill for cycle A.",
                    "children": [
                        {
                            "name": "cycle-a",
                            "request": "Create the same parent recursively.",
                            "children": [],
                        }
                    ],
                }
            ]
        )
    except FOUNDRY.FoundryError as exc:
        blocked = exc.code == "E_RECURSION"
    assert blocked
    return {"cycle_rejected": True}


def _iteration(project: Path) -> dict[str, Any]:
    first = FOUNDRY.forge_candidate(
        project,
        "Create a reusable Codex skill that validates API migration examples and excludes unrelated documentation requests.",
        name="api-migration-validation",
    )
    failure = project / "failure.json"
    FOUNDRY.write_json(
        failure,
        {
            "case_id": "documentation-neighbor",
            "request": "Write general API documentation without validating migration examples.",
            "expected_action": "skip",
        },
    )
    second = FOUNDRY.iterate_candidate(project, first["skill_name"], failure)
    assert second["version"] == first["version"] + 1
    assert second["status"] == "validated"
    return {"prior_version": first["version"], "replacement_version": second["version"]}


def _drift(project: Path) -> dict[str, Any]:
    candidate = FOUNDRY.forge_candidate(project, "Create a Codex skill that validates SDK examples against API schemas.", name="sdk-example-validation")
    promoted = FOUNDRY.promote_candidate(project, candidate["skill_name"])
    skill = project / promoted["install_path"] / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\nunauthorized drift\n", encoding="utf-8")
    verification = FOUNDRY.verify_installation(project, candidate["skill_name"])
    assert verification["status"] == "fail"
    return {"drift_detected": True}


def _receipt_collision(project: Path) -> dict[str, Any]:
    candidate = FOUNDRY.forge_candidate(project, "Turn this repeated API review into a reusable skill.", name="api-review", source_kind="learned_mechanism", force_skill_request=False)
    first = FOUNDRY.record_evidence(project, candidate["skill_name"], run_id="same-run", objective_id="objective-one", project_id="project-one", outcome="accepted", artifact_sha256=sha("one"), notes="First immutable receipt.")
    replay = FOUNDRY.record_evidence(project, candidate["skill_name"], run_id="same-run", objective_id="objective-one", project_id="project-one", outcome="accepted", artifact_sha256=sha("one"), notes="First immutable receipt.")
    collision = False
    try:
        FOUNDRY.record_evidence(project, candidate["skill_name"], run_id="same-run", objective_id="objective-one", project_id="project-one", outcome="accepted", artifact_sha256=sha("changed"), notes="Changed receipt content.")
    except FOUNDRY.FoundryError as exc:
        collision = exc.code == "E_COLLISION"
    assert first["status"] == "recorded"
    assert replay["status"] == "replayed"
    assert collision
    return {"exact_replay": True, "changed_replay_blocked": True}


def _core_promotion(project: Path) -> dict[str, Any]:
    candidate = FOUNDRY.forge_candidate(project, "Create a Codex skill that validates release evidence.", name="release-evidence-validation")
    blocked = False
    try:
        FOUNDRY.promote_candidate(project, candidate["skill_name"], scope="core")
    except FOUNDRY.FoundryError as exc:
        blocked = exc.code == "E_AUTHORITY"
    assert blocked
    return {"automatic_core_promotion_blocked": True}


if __name__ == "__main__":
    raise SystemExit(main())
