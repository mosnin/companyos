from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FOUNDRY_PATH = ROOT / "skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py"
ORG_PATH = ROOT / "skills/company-os/compile-outcome-organization/scripts/compile_outcome_organization.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FOUNDRY = load(FOUNDRY_PATH, "recursive_skill_foundry_for_organization")
ORG = load(ORG_PATH, "outcome_organization_for_project_skills")


class RecursiveSkillFoundryOrganizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_exact_promoted_project_skill_is_assigned_to_matching_lane(self) -> None:
        candidate = FOUNDRY.forge_candidate(
            self.project,
            "Create a reusable Codex skill that diagnoses and repairs failed deployment builds using compiler logs and local verification.",
            name="deployment-build-repair",
        )
        FOUNDRY.promote_candidate(self.project, candidate["skill_name"])
        assignment = ORG._project_skill_assignment(
            self.project,
            {
                "lane_id": "artifact:deployment-runtime",
                "mandate": "Repair the failed deployment build and prove the runtime starts.",
            },
            "Inspect compiler logs, repair the deployment build, and rerun the same verification.",
        )
        self.assertIsNotNone(assignment)
        assert assignment is not None
        self.assertEqual(assignment["role"], "worker")
        self.assertEqual(assignment["execution_order"], ["deployment-build-repair"])
        self.assertEqual(assignment["skills"][0]["skill_sha256"], candidate["skill_sha256"])

    def test_unrelated_promoted_skill_is_not_assigned(self) -> None:
        candidate = FOUNDRY.forge_candidate(
            self.project,
            "Create a reusable Codex skill for collecting incident timelines and corrective action evidence.",
            name="incident-timeline-review",
        )
        FOUNDRY.promote_candidate(self.project, candidate["skill_name"])
        assignment = ORG._project_skill_assignment(
            self.project,
            {
                "lane_id": "artifact:pricing-page",
                "mandate": "Build the pricing page visual hierarchy.",
            },
            "Implement responsive pricing cards and inspect the browser output.",
        )
        self.assertIsNone(assignment)

    def test_registry_drift_fails_before_assignment(self) -> None:
        candidate = FOUNDRY.forge_candidate(
            self.project,
            "Create a reusable Codex skill that validates SDK examples against an API schema.",
            name="sdk-example-validation",
        )
        promoted = FOUNDRY.promote_candidate(self.project, candidate["skill_name"])
        skill = self.project / promoted["install_path"] / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\nunauthorized drift\n", encoding="utf-8")
        with self.assertRaises(FOUNDRY.FoundryError) as caught:
            ORG._project_skill_assignment(
                self.project,
                {
                    "lane_id": "artifact:sdk-examples",
                    "mandate": "Validate SDK examples against the API schema.",
                },
                "Run the SDK example validation procedure.",
            )
        self.assertEqual(caught.exception.code, "E_DIGEST")


if __name__ == "__main__":
    unittest.main()
