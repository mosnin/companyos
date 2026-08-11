from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/mission-execution-control/scripts/checkpoint_product.py"
spec = importlib.util.spec_from_file_location("checkpoint_product_under_test", SCRIPT)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)

MISSION_SCRIPT = ROOT / "skills/company-os/mission-execution-control/scripts/mission_control.py"
mission_spec = importlib.util.spec_from_file_location("mission_control_checkpoint_test", MISSION_SCRIPT)
assert mission_spec and mission_spec.loader
MISSION = importlib.util.module_from_spec(mission_spec)
mission_spec.loader.exec_module(MISSION)


class ProductCheckpointTests(unittest.TestCase):
    def test_checkpoint_verifies_exact_bytes_and_commits_only_product_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Company OS Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "company-os@example.invalid"], check=True)
            product = root / "src/app.py"
            product.parent.mkdir(parents=True)
            product.write_text("print('real product')\n", encoding="utf-8")
            governance = root / ".company-os/report.json"
            governance.parent.mkdir(parents=True)
            governance.write_text("{}\n", encoding="utf-8")
            state = MISSION.initialize_state("mission", "Build a website", mission_class="quick_build", duration_minutes=90)
            candidate = {
                "candidate_id": "candidate-1",
                "artifacts": [
                    {
                        "artifact_id": "app",
                        "artifact_class_id": "first_real_artifact",
                        "path": "src/app.py",
                        "sha256": MODULE.digest_file(product),
                    }
                ],
            }
            checkpoint = MODULE.checkpoint(root, state, candidate, [], commit=True)
            self.assertIsNotNone(checkpoint["git_commit"])
            tracked = subprocess.run(
                ["git", "-C", str(root), "ls-files"],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.splitlines()
            self.assertEqual(tracked, ["src/app.py"])
            MISSION.verify_checkpoint(checkpoint)

    def test_digest_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            product = root / "src/app.py"
            product.parent.mkdir(parents=True)
            product.write_text("print('changed')\n", encoding="utf-8")
            state = MISSION.initialize_state("mission", "Build a website", mission_class="quick_build", duration_minutes=90)
            candidate = {
                "candidate_id": "candidate-1",
                "artifacts": [
                    {
                        "artifact_id": "app",
                        "artifact_class_id": "first_real_artifact",
                        "path": "src/app.py",
                        "sha256": "0" * 64,
                    }
                ],
            }
            with self.assertRaises(MODULE.CheckpointError):
                MODULE.checkpoint(root, state, candidate, [], commit=False)


if __name__ == "__main__":
    unittest.main()
