from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "distribution.py"
CONTROLLER = (
    ROOT
    / "skills"
    / "company-os"
    / "elastic-company-os"
    / "scripts"
    / "company_os_controller.py"
)


def load_distribution():
    spec = importlib.util.spec_from_file_location("company_os_distribution", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DistributionTests(unittest.TestCase):
    def test_committed_manifest_matches_canonical_skills(self) -> None:
        distribution = load_distribution()
        committed = json.loads((ROOT / "distribution-manifest.json").read_text())
        self.assertEqual(committed, distribution.build_manifest())

    def test_install_to_empty_root_is_exact_and_idempotent(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "skills"
            distribution.install(target, force=False)
            first = {
                bundle: distribution.bundle_snapshot(target, bundle)
                for bundle in distribution.BUNDLES
            }
            distribution.install(target, force=False)
            second = {
                bundle: distribution.bundle_snapshot(target, bundle)
                for bundle in distribution.BUNDLES
            }
            self.assertEqual(first, second)

    def test_modified_install_requires_force(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "skills"
            distribution.install(target, force=False)
            skill = target / "company-os" / "company-os" / "SKILL.md"
            skill.write_text(skill.read_text() + "\nmodified\n")
            with self.assertRaises(distribution.DistributionError):
                distribution.install(target, force=False)
            distribution.install(target, force=True)
            distribution.check_install(target)

    def test_clean_project_bootstrap_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "self-host"
            project.mkdir()
            initialized = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER),
                    "init",
                    "--project",
                    str(project),
                    "--name",
                    "Company OS Self Host",
                    "--project-type",
                    "software",
                    "--north-star",
                    "Company OS produces independently verified outcomes",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            self.assertTrue((project / ".company-os" / "control.json").exists())
            audit = subprocess.run(
                [sys.executable, str(CONTROLLER), "audit", "--project", str(project)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(audit.returncode, 1)
            report = json.loads(audit.stdout)
            self.assertFalse(report["ok"])
            self.assertFalse(report["scheduler_ready"])
            self.assertIn("strategy.current_outcome is required before execution", report["errors"])


if __name__ == "__main__":
    unittest.main()
