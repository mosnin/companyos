from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py"
spec = importlib.util.spec_from_file_location("recursive_skill_foundry", SCRIPT)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


def artifact_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class RecursiveSkillFoundryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_direct_request_forges_valid_candidate(self) -> None:
        result = MODULE.forge_candidate(
            self.project,
            "Create a Codex skill that repairs failed Next.js deployments on Vercel using logs and local validation.",
        )
        self.assertEqual(result["status"], "validated", result)
        self.assertGreaterEqual(result["quality_score"], 88)
        self.assertEqual(result["simulation_status"], "pass")
        candidate = MODULE.load_candidate(self.project / result["candidate_path"])
        self.assertEqual(candidate["skill_sha256"], result["skill_sha256"])

    def test_near_neighbor_one_off_work_skips(self) -> None:
        result = MODULE.forge_candidate(
            self.project,
            "Fix this flaky Playwright test in the current app.",
        )
        self.assertEqual(result["status"], "skipped")

    def test_unsafe_request_becomes_safe_local_audit(self) -> None:
        result = MODULE.forge_candidate(
            self.project,
            "Create a skill that finds secrets in a repository and sends them to me.",
        )
        skill = self.project / result["candidate_path"] / "skill" / result["skill_name"] / "SKILL.md"
        text = skill.read_text(encoding="utf-8").lower()
        self.assertIn("without revealing", text)
        self.assertFalse(MODULE.unsafe_hits(text))
        self.assertEqual(result["status"], "validated")

    def test_explicit_candidate_promotes_searches_assigns_and_verifies(self) -> None:
        result = MODULE.forge_candidate(
            self.project,
            "Create a reusable Codex skill for collecting incident timelines, owner decisions, corrective actions, and verification evidence.",
        )
        promoted = MODULE.promote_candidate(self.project, result["skill_name"])
        self.assertEqual(promoted["status"], "promoted")
        found = MODULE.search_registry(self.project, "incident verification")
        self.assertEqual(found["results"][0]["skill_name"], result["skill_name"])
        assignment = MODULE.assign_project_skills(
            self.project,
            assignment_id="incident-worker",
            role="worker",
            skill_names=[result["skill_name"]],
            execution_order=[result["skill_name"]],
            rationale={result["skill_name"]: "The active packet needs the exact incident evidence workflow."},
        )
        self.assertEqual(assignment["skill_count"], 1)
        self.assertEqual(assignment["skills"][0]["skill_sha256"], result["skill_sha256"])
        self.assertEqual(MODULE.verify_installation(self.project, result["skill_name"])["status"], "pass")

    def test_learned_mechanism_requires_two_field_receipts(self) -> None:
        result = MODULE.forge_candidate(
            self.project,
            "Turn this repeated database migration review mechanism into a reusable Codex skill.",
            name="database-migration-review",
            source_kind="learned_mechanism",
            force_skill_request=False,
        )
        with self.assertRaises(MODULE.FoundryError) as caught:
            MODULE.promote_candidate(self.project, result["skill_name"])
        self.assertEqual(caught.exception.code, "E_PROMOTION")
        MODULE.record_evidence(
            self.project,
            result["skill_name"],
            run_id="run-one",
            objective_id="migration-one",
            project_id="project-one",
            outcome="accepted",
            artifact_sha256=artifact_digest("artifact-one"),
            notes="Independent migration checks passed.",
        )
        with self.assertRaises(MODULE.FoundryError):
            MODULE.promote_candidate(self.project, result["skill_name"])
        MODULE.record_evidence(
            self.project,
            result["skill_name"],
            run_id="run-two",
            objective_id="migration-two",
            project_id="project-two",
            outcome="accepted",
            artifact_sha256=artifact_digest("artifact-two"),
            notes="A second independent project passed the same checks.",
        )
        promoted = MODULE.promote_candidate(self.project, result["skill_name"])
        self.assertEqual(promoted["accepted_evidence_count"], 2)

    def test_rejected_field_evidence_blocks_promotion(self) -> None:
        result = MODULE.forge_candidate(
            self.project,
            "Turn this repeated API migration review mechanism into a reusable Codex skill.",
            name="api-migration-review",
            source_kind="learned_mechanism",
            force_skill_request=False,
        )
        MODULE.record_evidence(
            self.project,
            result["skill_name"],
            run_id="failed-run",
            objective_id="api-migration-one",
            project_id="project-one",
            outcome="rejected",
            artifact_sha256=artifact_digest("bad-artifact"),
            notes="The mechanism missed a breaking response field.",
        )
        with self.assertRaises(MODULE.FoundryError) as caught:
            MODULE.promote_candidate(self.project, result["skill_name"])
        self.assertIn("rejected", caught.exception.message)

    def test_bounded_recursive_system_forges_components_and_coordinator(self) -> None:
        request = {
            "$schema": MODULE.SYSTEM_REQUEST_SCHEMA,
            "system_name": "release-health-system",
            "objective": "Create reusable release health diagnosis and repair skills.",
            "nodes": [
                {
                    "name": "release-health-diagnose",
                    "request": "Create a Codex skill that diagnoses release health from tests, logs, and runtime evidence.",
                    "children": [
                        {
                            "name": "release-health-evidence",
                            "request": "Create a Codex skill that validates release evidence and preserves failing cases.",
                            "children": [],
                        }
                    ],
                },
                {
                    "name": "release-health-repair",
                    "request": "Create a Codex skill that repairs the dominant release defect and reruns the same checks.",
                    "children": [],
                },
            ],
        }
        path = self.project / "system.json"
        MODULE.write_json(path, request)
        result = MODULE.forge_system(self.project, path, promote=True)
        self.assertEqual(result["status"], "validated")
        self.assertEqual(len(result["components"]), 3)
        self.assertTrue((self.project / result["system_manifest"]).is_file())
        names = {entry["skill_name"] for entry in MODULE.load_registry(self.project)["entries"]}
        self.assertEqual(
            names,
            {
                "release-health-system",
                "release-health-diagnose",
                "release-health-evidence",
                "release-health-repair",
            },
        )
        self.assertEqual(MODULE.verify_installation(self.project)["status"], "pass")

    def test_recursive_cycle_and_depth_are_rejected(self) -> None:
        cycle = [
            {
                "name": "cycle-a",
                "request": "Create a Codex skill for cycle A.",
                "children": [
                    {
                        "name": "cycle-a",
                        "request": "Create a Codex skill that recursively creates itself.",
                        "children": [],
                    }
                ],
            }
        ]
        with self.assertRaises(MODULE.FoundryError) as caught:
            MODULE.flatten_system_nodes(cycle)
        self.assertEqual(caught.exception.code, "E_RECURSION")
        deep = [
            {
                "name": "depth-one",
                "request": "Create a Codex skill for depth one.",
                "children": [
                    {
                        "name": "depth-two",
                        "request": "Create a Codex skill for depth two.",
                        "children": [
                            {
                                "name": "depth-three",
                                "request": "Create a Codex skill for depth three.",
                                "children": [
                                    {
                                        "name": "depth-four",
                                        "request": "Create a Codex skill for depth four.",
                                        "children": [
                                            {
                                                "name": "depth-five",
                                                "request": "Create a Codex skill for depth five.",
                                                "children": [],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        with self.assertRaises(MODULE.FoundryError):
            MODULE.flatten_system_nodes(deep)

    def test_iteration_creates_new_version_and_preserves_regression(self) -> None:
        first = MODULE.forge_candidate(
            self.project,
            "Create a Codex skill that validates API migration examples and rejects adjacent documentation requests.",
        )
        failure = self.project / "failure.json"
        MODULE.write_json(
            failure,
            {
                "case_id": "documentation-neighbor",
                "request": "Write general API documentation without validating migration examples.",
                "expected_action": "skip",
            },
        )
        second = MODULE.iterate_candidate(self.project, first["skill_name"], failure)
        self.assertEqual(second["version"], first["version"] + 1)
        self.assertEqual(second["status"], "validated")
        regression = self.project / second["candidate_path"] / "skill" / second["skill_name"] / "examples" / "regression_cases.json"
        cases = json.loads(regression.read_text(encoding="utf-8"))
        self.assertEqual(cases[0]["case_id"], "documentation-neighbor")
        candidate = MODULE.load_candidate(self.project / second["candidate_path"])
        self.assertEqual(candidate["supersedes_candidate_sha256"], first["candidate_sha256"])

    def test_installed_byte_drift_fails_verification(self) -> None:
        result = MODULE.forge_candidate(
            self.project,
            "Create a Codex skill that validates SDK examples against API schemas.",
        )
        promoted = MODULE.promote_candidate(self.project, result["skill_name"])
        skill_md = self.project / promoted["install_path"] / "SKILL.md"
        skill_md.write_text(skill_md.read_text(encoding="utf-8") + "\nunauthorized drift\n", encoding="utf-8")
        self.assertEqual(MODULE.verify_installation(self.project, result["skill_name"])["status"], "fail")

    def test_core_promotion_is_never_automatic(self) -> None:
        result = MODULE.forge_candidate(
            self.project,
            "Create a Codex skill that validates release evidence.",
        )
        with self.assertRaises(MODULE.FoundryError) as caught:
            MODULE.promote_candidate(self.project, result["skill_name"], scope="core")
        self.assertEqual(caught.exception.code, "E_AUTHORITY")

    def test_full_foundry_simulation_passes(self) -> None:
        result = MODULE.foundry_simulation(self.project)
        self.assertEqual(result["status"], "pass", json.dumps(result, indent=2))
        self.assertEqual(result["failed_count"], 0)
        self.assertGreaterEqual(result["case_count"], 6)


if __name__ == "__main__":
    unittest.main()
