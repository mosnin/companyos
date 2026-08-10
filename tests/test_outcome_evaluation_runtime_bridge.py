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
    "outcome_loop_for_evaluation_bridge",
    ROOT / "skills/company-os/elastic-company-os/scripts/outcome_loop.py",
)
BRIDGE = load(
    "outcome_evaluation_runtime_bridge",
    ROOT / "skills/company-os/elastic-company-os/scripts/outcome_evaluation_runtime_bridge.py",
)


class OutcomeEvaluationRuntimeBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        artifact = self.root / "dist/game.bin"
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b"candidate bytes")
        self.artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
        receipt = self.root / ".company-os/evaluations/gameplay.json"
        receipt.parent.mkdir(parents=True)
        self.receipt = {
            "evaluator_id": "gameplay-evaluator",
            "objective_id": "viral-game",
            "production_actor_ids": ["production-attempt"],
            "artifact_bindings": [{
                "artifact_class_id": "playable_game",
                "path": "dist/game.bin",
                "sha256": self.artifact_sha,
            }],
            "scores": {"gameplay": 5.0, "visual_quality": 9.0},
            "findings": [],
            "accepted": False,
            "receipt_sha256": "c" * 64,
        }
        receipt.write_text(json.dumps(self.receipt), encoding="utf-8")
        self.state = self.evaluation_state()
        self.manifest = {
            "managers": [{
                "id": "manager-eval",
                "outcome_loop_lane_id": "evaluator:gameplay-evaluator",
                "workers": [{
                    "id": "worker-eval",
                    "outcome_context": {
                        "evaluator_id": "gameplay-evaluator",
                        "artifact_classes": ["playable_game"],
                        "score_dimensions": ["gameplay", "visual_quality"],
                    },
                }],
            }]
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def evaluation_state(self) -> dict:
        candidate = {
            "candidate_id": "candidate:one",
            "iteration": 1,
            "production_actor_ids": ["production-attempt"],
            "artifact_bindings": [{
                "artifact_id": "game",
                "artifact_class_id": "playable_game",
                "path": "dist/game.bin",
                "sha256": self.artifact_sha,
                "size": len(b"candidate bytes"),
            }],
        }
        candidate["artifacts"] = list(candidate["artifact_bindings"])
        candidate["candidate_sha256"] = LOOP.digest(candidate)
        state = {
            "$schema": LOOP.STATE_SCHEMA,
            "schema_version": 1,
            "objective_id": "viral-game",
            "original_objective": "Make a viral game.",
            "quality_policy": LOOP.policy(),
            "phase": "evaluate",
            "iteration": 1,
            "control_state": None,
            "outcome_claims": [],
            "required_artifact_classes": ["playable_game"],
            "required_evaluators": [{
                "evaluator_id": "gameplay-evaluator",
                "artifact_classes": ["playable_game"],
                "score_dimensions": ["gameplay", "visual_quality"],
            }],
            "organization_plan": {
                "evaluation_lanes": [{
                    "lane_id": "evaluator:gameplay-evaluator",
                    "role": "independent_evaluator",
                    "evaluator_id": "gameplay-evaluator",
                    "artifact_classes": ["playable_game"],
                    "score_dimensions": ["gameplay", "visual_quality"],
                }]
            },
            "candidates": [candidate],
            "evaluations": [],
            "diagnoses": [],
            "interventions": [],
            "acceptance": None,
            "history": [],
            "next_action": {
                "action": "execute_required_evaluators",
                "candidate_id": "candidate:one",
                "evaluator_ids": ["gameplay-evaluator"],
            },
            "state_sha256": None,
        }
        return LOOP.seal(state)

    def attempt(self, *, status: str = "succeeded", include_receipt: bool = True) -> dict:
        observation = {"status": status}
        if include_receipt:
            observation["evaluation_receipt_path"] = ".company-os/evaluations/gameplay.json"
        return {
            "attempt_id": "eval-attempt",
            "native_task_runtime": {
                "admission": {"metadata": {"manifest_identity_id": "worker-eval"}},
                "terminal": {"observation": observation},
            },
        }

    def verifier(self, project_root: Path, receipt: dict) -> dict:
        return {
            "evaluator_id": receipt["evaluator_id"],
            "objective_id": receipt["objective_id"],
            "receipt_sha256": receipt["receipt_sha256"],
        }

    def test_missing_evaluator_terminal_waits(self) -> None:
        result = BRIDGE.advance_evaluations(
            self.root, self.state, self.manifest, [], verifier=self.verifier
        )
        self.assertFalse(result["advanced"])
        self.assertEqual(result["missing_evaluators"], ["gameplay-evaluator"])

    def test_complete_evaluator_receipt_drives_targeted_rework(self) -> None:
        result = BRIDGE.advance_evaluations(
            self.root,
            self.state,
            self.manifest,
            [self.attempt()],
            verifier=self.verifier,
        )
        self.assertTrue(result["advanced"])
        self.assertEqual(result["phase"], "rework")
        self.assertEqual(result["dominant_gap"]["dimension"], "gameplay")
        intervention = result["state"]["interventions"][-1]
        self.assertEqual(intervention["target_dimensions"][0], "gameplay")
        self.assertIn("visual_quality", intervention["preserve_dimensions"])

    def test_failed_evaluator_blocks_transition(self) -> None:
        with self.assertRaises(BRIDGE.OutcomeEvaluationBridgeError) as caught:
            BRIDGE.advance_evaluations(
                self.root,
                self.state,
                self.manifest,
                [self.attempt(status="failed")],
                verifier=self.verifier,
            )
        self.assertEqual(caught.exception.code, "E_TERMINAL")


if __name__ == "__main__":
    unittest.main()
