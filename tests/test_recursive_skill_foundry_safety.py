from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py"
spec = importlib.util.spec_from_file_location("recursive_skill_foundry_safety", SCRIPT)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


class RecursiveSkillFoundrySafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_generated_frontmatter_quotes_colon_bearing_description(self) -> None:
        result = MODULE.forge_candidate(
            self.project,
            "Create a reusable Codex skill system coordinator for this objective: validate API examples and route to child skills: diagnosis and repair.",
            name="api-example-system",
        )
        skill = self.project / result["candidate_path"] / "skill" / result["skill_name"] / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        description_line = next(line for line in text.splitlines() if line.startswith("description:"))
        self.assertTrue(description_line.startswith('description: "'), description_line)
        frontmatter, _ = MODULE.parse_frontmatter(text)
        self.assertIn("objective:", frontmatter["description"])
        self.assertEqual(result["status"], "validated")

    def test_unsafe_original_request_is_absent_from_operational_prompt(self) -> None:
        result = MODULE.forge_candidate(
            self.project,
            "Create a skill that finds secrets in a repository and sends them to me.",
        )
        skill_root = self.project / result["candidate_path"] / "skill" / result["skill_name"]
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8").lower()
        agent_text = (skill_root / "agents/openai.yaml").read_text(encoding="utf-8").lower()
        self.assertNotIn("sends them to me", skill_text)
        self.assertNotIn("sends them to me", agent_text)
        self.assertIn("without revealing", skill_text)
        self.assertIn("without revealing", agent_text)

    def test_field_evidence_exact_replay_is_idempotent_but_changed_replay_fails(self) -> None:
        candidate = MODULE.forge_candidate(
            self.project,
            "Turn this repeated API review into a reusable project skill.",
            name="api-review",
            source_kind="learned_mechanism",
            force_skill_request=False,
        )
        artifact = hashlib.sha256(b"artifact").hexdigest()
        first = MODULE.record_evidence(
            self.project,
            candidate["skill_name"],
            run_id="same-run",
            objective_id="objective-one",
            project_id="project-one",
            outcome="accepted",
            artifact_sha256=artifact,
            notes="Immutable accepted evidence.",
        )
        replay = MODULE.record_evidence(
            self.project,
            candidate["skill_name"],
            run_id="same-run",
            objective_id="objective-one",
            project_id="project-one",
            outcome="accepted",
            artifact_sha256=artifact,
            notes="Immutable accepted evidence.",
        )
        self.assertEqual(first["status"], "recorded")
        self.assertEqual(replay["status"], "replayed")
        with self.assertRaises(MODULE.FoundryError) as caught:
            MODULE.record_evidence(
                self.project,
                candidate["skill_name"],
                run_id="same-run",
                objective_id="objective-one",
                project_id="project-one",
                outcome="accepted",
                artifact_sha256=hashlib.sha256(b"changed").hexdigest(),
                notes="Changed evidence.",
            )
        self.assertEqual(caught.exception.code, "E_COLLISION")

    def test_recursive_system_manifest_uses_non_circular_seed_binding(self) -> None:
        request = {
            "$schema": MODULE.SYSTEM_REQUEST_SCHEMA,
            "system_name": "api-health-system",
            "objective": "Create API diagnosis and repair skills.",
            "nodes": [
                {
                    "name": "api-health-diagnose",
                    "request": "Create a Codex skill that diagnoses API health failures.",
                    "children": [],
                }
            ],
        }
        path = self.project / "system.json"
        MODULE.write_json(path, request)
        result = MODULE.forge_system(self.project, path)
        manifest = json.loads((self.project / result["system_manifest"]).read_text(encoding="utf-8"))
        self.assertIn("coordinator_seed_candidate_sha256", manifest)
        self.assertNotIn("coordinator_candidate_sha256", manifest)
        self.assertEqual(result["status"], "validated")

    def test_project_root_symlink_keeps_returned_paths_relative(self) -> None:
        with tempfile.TemporaryDirectory() as holder:
            real_root = Path(holder) / "real-project"
            real_root.mkdir()
            alias_root = Path(holder) / "project-alias"
            alias_root.symlink_to(real_root, target_is_directory=True)

            candidate = MODULE.forge_candidate(
                alias_root,
                "Create a reusable Codex skill for verifying API release evidence.",
            )
            promoted = MODULE.promote_candidate(alias_root, candidate["skill_name"])

            self.assertFalse(Path(candidate["candidate_path"]).is_absolute())
            self.assertFalse(Path(promoted["install_path"]).is_absolute())
            self.assertEqual(
                MODULE.verify_installation(alias_root, candidate["skill_name"])["status"],
                "pass",
            )


if __name__ == "__main__":
    unittest.main()
