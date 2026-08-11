from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/assemble-outcome-candidate/scripts/assemble_candidate.py"
spec = importlib.util.spec_from_file_location("first_reality_candidate_observations", SCRIPT)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


class FirstRealityCandidateObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        contract = self.root / ".company-os/artifacts.json"
        contract.parent.mkdir(parents=True, exist_ok=True)
        contract.write_text(
            json.dumps(
                {
                    "$schema": MODULE.ARTIFACT_SCHEMA,
                    "artifact_classes": [
                        {"artifact_class_id": "browser_path", "required": True}
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        scope = self.root / "out/lane/artifact"
        scope.mkdir(parents=True)
        artifact = scope / "app.html"
        artifact.write_text("<button>Real application</button>\n", encoding="utf-8")
        self.runtime = scope / "runtime.json"
        self.runtime.write_text('{"rendered":true}\n', encoding="utf-8")
        self.journey = scope / "journey.json"
        self.journey.write_text('{"clicked":true}\n', encoding="utf-8")
        self.fabric = {
            "topology_mode": MODULE.FABRIC_MODE,
            "outcome_control": {
                "objective_id": "objective",
                "artifact_contract_path": ".company-os/artifacts.json",
            },
            "outcome_loop": {
                "phase": "build_candidate",
                "state_sha256": "a" * 64,
                "organization_sha256": "b" * 64,
            },
            "mission_control": {
                "first_reality_required": True,
            },
            "managers": [
                {
                    "outcome_loop_lane_id": "artifact:browser_path",
                    "outcome_loop_lane_sha256": "c" * 64,
                    "workers": [
                        {
                            "id": "worker",
                            "outcome_loop_lane_id": "artifact:browser_path",
                            "outcome_loop_lane_sha256": "c" * 64,
                            "write_scope": ["out/lane/artifact"],
                        }
                    ],
                }
            ],
        }
        self.artifact_path = artifact

    def tearDown(self) -> None:
        self.temp.cleanup()

    def manifest(self, observations=None) -> None:
        value = {
            "$schema": MODULE.MANIFEST_SCHEMA,
            "schema_version": 1,
            "objective_id": "objective",
            "outcome_loop_state_sha256": "a" * 64,
            "organization_sha256": "b" * 64,
            "lane_id": "artifact:browser_path",
            "lane_sha256": "c" * 64,
            "production_actor_id": "worker",
            "artifacts": [
                {
                    "artifact_id": "app",
                    "artifact_class_id": "browser_path",
                    "path": "out/lane/artifact/app.html",
                    "sha256": MODULE.file_digest(self.artifact_path),
                }
            ],
        }
        if observations is not None:
            value["observations"] = observations
        path = self.root / "out/lane/artifact/artifact-manifest.json"
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def test_artifact_without_runtime_evidence_is_not_first_reality(self) -> None:
        self.manifest()
        with self.assertRaises(MODULE.CandidateAssemblyError) as caught:
            MODULE.assemble(self.root, self.fabric, "candidate-1")
        self.assertEqual(caught.exception.code, "E_OBSERVATION")

    def test_runtime_without_connected_journey_is_not_first_reality(self) -> None:
        self.manifest(
            [
                {
                    "kind": "runtime_observed",
                    "capability_id": "browser_path",
                    "path": "out/lane/artifact/runtime.json",
                    "sha256": MODULE.file_digest(self.runtime),
                    "observation_kind": "browser",
                }
            ]
        )
        with self.assertRaises(MODULE.CandidateAssemblyError) as caught:
            MODULE.assemble(self.root, self.fabric, "candidate-1")
        self.assertEqual(caught.exception.code, "E_OBSERVATION")

    def test_runtime_and_connected_journey_assemble_candidate(self) -> None:
        self.manifest(
            [
                {
                    "kind": "journey_connected",
                    "capability_id": "browser_path",
                    "path": "out/lane/artifact/journey.json",
                    "sha256": MODULE.file_digest(self.journey),
                    "observation_kind": "browser_interaction",
                },
                {
                    "kind": "runtime_observed",
                    "capability_id": "browser_path",
                    "path": "out/lane/artifact/runtime.json",
                    "sha256": MODULE.file_digest(self.runtime),
                    "observation_kind": "browser",
                },
            ]
        )
        candidate = MODULE.assemble(self.root, self.fabric, "candidate-1")
        self.assertEqual(
            [item["kind"] for item in candidate["observations"]],
            ["journey_connected", "runtime_observed"],
        )
        self.assertEqual(candidate["observations"][0]["capability_id"], "browser_path")


if __name__ == "__main__":
    unittest.main()
