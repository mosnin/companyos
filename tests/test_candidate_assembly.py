from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/assemble-outcome-candidate/scripts/assemble_candidate.py"
spec = importlib.util.spec_from_file_location("assemble_candidate_under_test", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(MODULE)


class CandidateAssemblyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        self.loop_sha = "a" * 64
        self.org_sha = "b" * 64
        self.lane_sha = "c" * 64
        self.write_json(
            ".company-os/runtime/artifacts.json",
            {
                "$schema": MODULE.ARTIFACT_SCHEMA,
                "artifact_classes": [
                    {"artifact_class_id": "playable_game", "required": True}
                ],
            },
        )
        artifact = self.project / "out/lane/artifact/game.bin"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(b"real game")
        self.artifact_sha = MODULE.file_digest(artifact)
        self.fabric = {
            "topology_mode": MODULE.FABRIC_MODE,
            "outcome_control": {
                "objective_id": "viral-game",
                "artifact_contract_path": ".company-os/runtime/artifacts.json",
            },
            "outcome_loop": {
                "phase": "build_candidate",
                "state_sha256": self.loop_sha,
                "organization_sha256": self.org_sha,
            },
            "managers": [
                {
                    "outcome_loop_lane_id": "artifact:playable_game",
                    "outcome_loop_lane_sha256": self.lane_sha,
                    "workers": [
                        {
                            "id": "worker-1",
                            "outcome_loop_lane_id": "artifact:playable_game",
                            "outcome_loop_lane_sha256": self.lane_sha,
                            "write_scope": ["out/lane/artifact"],
                        }
                    ],
                }
            ],
        }
        self.write_manifest()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_json(self, relative: str, value) -> None:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def write_manifest(self, **overrides) -> None:
        value = {
            "$schema": MODULE.MANIFEST_SCHEMA,
            "schema_version": 1,
            "objective_id": "viral-game",
            "outcome_loop_state_sha256": self.loop_sha,
            "organization_sha256": self.org_sha,
            "lane_id": "artifact:playable_game",
            "lane_sha256": self.lane_sha,
            "production_actor_id": "worker-1",
            "artifacts": [
                {
                    "artifact_id": "game",
                    "artifact_class_id": "playable_game",
                    "path": "out/lane/artifact/game.bin",
                    "sha256": self.artifact_sha,
                }
            ],
        }
        value.update(overrides)
        self.write_json("out/lane/artifact/artifact-manifest.json", value)

    def test_valid_lane_manifest_assembles_real_candidate(self) -> None:
        candidate = MODULE.assemble(self.project, self.fabric, "candidate-1")
        self.assertEqual(candidate["$schema"], MODULE.CANDIDATE_SCHEMA)
        self.assertEqual(candidate["production_actor_ids"], ["worker-1"])
        self.assertEqual(candidate["artifacts"][0]["sha256"], self.artifact_sha)
        self.assertEqual(candidate["artifacts"][0]["artifact_class_id"], "playable_game")

    def test_missing_lane_manifest_is_execution_boundary_not_completion(self) -> None:
        (self.project / "out/lane/artifact/artifact-manifest.json").unlink()
        with self.assertRaises(MODULE.CandidateAssemblyError) as caught:
            MODULE.assemble(self.project, self.fabric, "candidate-1")
        self.assertEqual(caught.exception.code, "E_MANIFEST_MISSING")

    def test_stale_loop_manifest_is_rejected(self) -> None:
        self.write_manifest(outcome_loop_state_sha256="d" * 64)
        with self.assertRaises(MODULE.CandidateAssemblyError) as caught:
            MODULE.assemble(self.project, self.fabric, "candidate-1")
        self.assertEqual(caught.exception.code, "E_STALE")

    def test_wrong_production_actor_is_rejected(self) -> None:
        self.write_manifest(production_actor_id="manager-1")
        with self.assertRaises(MODULE.CandidateAssemblyError) as caught:
            MODULE.assemble(self.project, self.fabric, "candidate-1")
        self.assertEqual(caught.exception.code, "E_AUTHORITY")

    def test_artifact_outside_worker_scope_is_rejected(self) -> None:
        outside = self.project / "outside.bin"
        outside.write_bytes(b"outside")
        self.write_manifest(
            artifacts=[
                {
                    "artifact_id": "game",
                    "artifact_class_id": "playable_game",
                    "path": "outside.bin",
                    "sha256": MODULE.file_digest(outside),
                }
            ]
        )
        with self.assertRaises(MODULE.CandidateAssemblyError) as caught:
            MODULE.assemble(self.project, self.fabric, "candidate-1")
        self.assertEqual(caught.exception.code, "E_SCOPE")

    def test_artifact_digest_drift_is_rejected(self) -> None:
        (self.project / "out/lane/artifact/game.bin").write_bytes(b"changed")
        with self.assertRaises(MODULE.CandidateAssemblyError) as caught:
            MODULE.assemble(self.project, self.fabric, "candidate-1")
        self.assertEqual(caught.exception.code, "E_DIGEST")


if __name__ == "__main__":
    unittest.main()
