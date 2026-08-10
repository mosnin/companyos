from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LOOP = load(
    "outcome_loop_for_runtime_bridge",
    ROOT / "skills/company-os/elastic-company-os/scripts/outcome_loop.py",
)
BRIDGE = load(
    "outcome_runtime_bridge",
    ROOT / "skills/company-os/elastic-company-os/scripts/outcome_runtime_bridge.py",
)


class OutcomeRuntimeBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        artifact = self.root / "dist/game.bin"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b"playable candidate")
        self.artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
        self.state = self.state_for(["playable_game"])
        self.manifest = {
            "managers": [
                {
                    "id": "outcome-manager-01",
                    "outcome_loop_lane_id": "artifact:playable_game",
                    "outcome_loop_lane_sha256": "a" * 64,
                    "workers": [
                        {
                            "id": "worker-playable",
                            "outcome_loop_lane_id": "artifact:playable_game",
                            "outcome_loop_lane_sha256": "a" * 64,
                            "outcome_context": {},
                        }
                    ],
                }
            ]
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def state_for(self, classes: list[str]) -> dict:
        state = {
            "$schema": LOOP.STATE_SCHEMA,
            "schema_version": 1,
            "objective_id": "viral-game",
            "original_objective": "Make a viral game.",
            "quality_policy": LOOP.policy(),
            "phase": "build_candidate",
            "iteration": 0,
            "control_state": None,
            "outcome_claims": [],
            "required_artifact_classes": classes,
            "required_evaluators": [
                {
                    "evaluator_id": "playability",
                    "artifact_classes": classes,
                    "score_dimensions": ["gameplay"],
                }
            ],
            "organization_plan": {},
            "candidates": [],
            "evaluations": [],
            "diagnoses": [],
            "interventions": [],
            "acceptance": None,
            "history": [],
            "next_action": {"action": "materialize_candidate"},
            "state_sha256": None,
        }
        return LOOP.seal(state)

    def attempt(self, *, status: str = "succeeded", klass: str = "playable_game") -> dict:
        return {
            "attempt_id": "attempt-playable",
            "native_task_runtime": {
                "admission": {
                    "metadata": {"manifest_identity_id": "worker-playable"}
                },
                "terminal": {
                    "observation": {
                        "status": status,
                        "artifact_bindings": [
                            {
                                "artifact_id": "game",
                                "artifact_class_id": klass,
                                "path": "dist/game.bin",
                                "sha256": self.artifact_sha,
                            }
                        ],
                    }
                },
            },
        }

    def test_missing_terminal_lane_waits_without_inventing_completion(self) -> None:
        result = BRIDGE.advance_candidate(self.root, self.state, self.manifest, [])
        self.assertFalse(result["advanced"])
        self.assertEqual(result["reason"], "waiting_for_terminal_artifacts")
        self.assertEqual(result["missing_lanes"], ["artifact:playable_game"])
        self.assertEqual(result["state"]["state_sha256"], self.state["state_sha256"])

    def test_exact_real_artifact_advances_to_independent_evaluation(self) -> None:
        result = BRIDGE.advance_candidate(
            self.root, self.state, self.manifest, [self.attempt()]
        )
        self.assertTrue(result["advanced"])
        self.assertEqual(result["phase"], "evaluate")
        self.assertEqual(result["state"]["iteration"], 1)
        self.assertEqual(
            result["state"]["next_action"]["action"],
            "execute_required_evaluators",
        )
        candidate = result["state"]["candidates"][-1]
        self.assertEqual(candidate["artifact_bindings"][0]["artifact_class_id"], "playable_game")
        self.assertEqual(candidate["production_actor_ids"], ["attempt-playable"])

    def test_failed_worker_blocks_candidate(self) -> None:
        with self.assertRaises(BRIDGE.OutcomeRuntimeBridgeError) as caught:
            BRIDGE.advance_candidate(
                self.root,
                self.state,
                self.manifest,
                [self.attempt(status="failed")],
            )
        self.assertEqual(caught.exception.code, "E_TERMINAL")

    def test_wrong_artifact_class_is_rejected(self) -> None:
        with self.assertRaises(BRIDGE.OutcomeRuntimeBridgeError) as caught:
            BRIDGE.advance_candidate(
                self.root,
                self.state,
                self.manifest,
                [self.attempt(klass="marketing_page")],
            )
        self.assertEqual(caught.exception.code, "E_AUTHORITY")

    def test_artifact_byte_drift_is_rejected(self) -> None:
        (self.root / "dist/game.bin").write_bytes(b"changed after terminal")
        with self.assertRaises(BRIDGE.OutcomeRuntimeBridgeError) as caught:
            BRIDGE.advance_candidate(self.root, self.state, self.manifest, [self.attempt()])
        self.assertEqual(caught.exception.code, "E_DIGEST")


if __name__ == "__main__":
    unittest.main()
