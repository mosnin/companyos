from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/direct-outcome/scripts/direct_outcome.py"
spec = importlib.util.spec_from_file_location("director_product_checkpoint", SCRIPT)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


class DirectorProductCheckpointTests(unittest.TestCase):
    def test_candidate_checkpoint_commits_only_bound_product_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            artifact = project / "outcome-lanes/product/artifact/app.html"
            runtime = project / "outcome-lanes/product/artifact/runtime.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("<button>Working product</button>\n", encoding="utf-8")
            runtime.write_text('{"rendered":true}\n', encoding="utf-8")
            mission = MODULE.mission_control_module().initialize_state(
                "product",
                "Build a website",
                mission_class="quick_build",
                duration_minutes=90,
            )
            MODULE.save_mission_state(project, mission)
            candidate = {
                "candidate_id": "candidate-1",
                "artifacts": [
                    {
                        "artifact_id": "app",
                        "artifact_class_id": "first_real_artifact",
                        "path": "outcome-lanes/product/artifact/app.html",
                        "sha256": MODULE.file_digest(artifact),
                    }
                ],
                "observations": [
                    {
                        "kind": "runtime_observed",
                        "capability_id": "first_real_artifact",
                        "path": "outcome-lanes/product/artifact/runtime.json",
                        "sha256": MODULE.file_digest(runtime),
                        "observation_kind": "browser",
                    }
                ],
            }
            reference = MODULE.checkpoint_candidate(project, "product", candidate)
            self.assertEqual(reference["git_commit"], subprocess.run(
                ["git", "-C", str(project), "rev-parse", "HEAD"],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip())
            tracked = subprocess.run(
                ["git", "-C", str(project), "ls-files"],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.splitlines()
            self.assertEqual(tracked, ["outcome-lanes/product/artifact/app.html"])
            updated = MODULE.load_mission_state(project, "product")
            self.assertIsNotNone(updated["checkpoint"])
            self.assertEqual(updated["checkpoint"]["candidate_id"], "candidate-1")

    def test_checkpoint_refuses_unrelated_staged_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            subprocess.run(["git", "-C", str(project), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(project), "config", "user.email", "test@example.invalid"], check=True)
            unrelated = project / "unrelated.txt"
            unrelated.write_text("staged\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(project), "add", "unrelated.txt"], check=True)
            artifact = project / "app.html"
            artifact.write_text("real\n", encoding="utf-8")
            mission = MODULE.mission_control_module().initialize_state(
                "product",
                "Build a website",
                mission_class="quick_build",
                duration_minutes=90,
            )
            candidate = {
                "candidate_id": "candidate-1",
                "artifacts": [
                    {
                        "artifact_id": "app",
                        "artifact_class_id": "first_real_artifact",
                        "path": "app.html",
                        "sha256": MODULE.file_digest(artifact),
                    }
                ],
            }
            with self.assertRaises(Exception):
                MODULE.checkpoint_product_module().checkpoint(
                    project,
                    mission,
                    candidate,
                    [],
                    commit=True,
                )


if __name__ == "__main__":
    unittest.main()
