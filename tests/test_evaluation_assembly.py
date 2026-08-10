from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/assemble-outcome-evaluations/scripts/assemble_evaluations.py"
spec = importlib.util.spec_from_file_location("assemble_evaluations_under_test", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(MODULE)


class EvaluationAssemblyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        self.write_json(
            ".company-os/runtime/evaluators.json",
            {
                "$schema": MODULE.EVALUATOR_SCHEMA,
                "evaluators": [
                    {"evaluator_id": "gameplay", "required": True},
                    {"evaluator_id": "visual", "required": True},
                ],
            },
        )
        self.fabric = {
            "topology_mode": MODULE.FABRIC_MODE,
            "outcome_control": {
                "objective_id": "viral-game",
                "evaluator_contract_path": ".company-os/runtime/evaluators.json",
            },
            "outcome_loop": {"phase": "evaluate"},
            "managers": [
                {
                    "workers": [
                        {
                            "id": "judge-gameplay",
                            "evaluator_id": "gameplay",
                            "write_scope": ["evaluations/gameplay"],
                        }
                    ]
                },
                {
                    "workers": [
                        {
                            "id": "judge-visual",
                            "outcome_loop_lane_id": "evaluator:visual",
                            "write_scope": ["evaluations/visual"],
                        }
                    ]
                },
            ],
        }
        self.write_receipt("evaluations/gameplay/execution-receipt.json", "gameplay")
        self.write_receipt("evaluations/visual/execution-receipt.json", "visual")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_json(self, relative: str, value) -> None:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def write_receipt(self, relative: str, evaluator_id: str) -> None:
        self.write_json(
            relative,
            {
                "$schema": "company-os.evaluator-execution-receipt.v1",
                "objective_id": "viral-game",
                "evaluator_id": evaluator_id,
                "receipt_sha256": evaluator_id.ljust(64, "a")[:64],
            },
        )

    @staticmethod
    def verify(project_root, receipt):
        return {
            "objective_id": receipt["objective_id"],
            "evaluator_id": receipt["evaluator_id"],
            "receipt_sha256": receipt["receipt_sha256"],
        }

    def test_exact_required_receipts_assemble_batch(self) -> None:
        batch = MODULE.assemble(
            self.project,
            self.fabric,
            "candidate-1",
            verifier=self.verify,
        )
        self.assertEqual(batch["$schema"], MODULE.BATCH_SCHEMA)
        self.assertEqual(batch["candidate_id"], "candidate-1")
        self.assertEqual(
            batch["receipt_paths"],
            [
                "evaluations/gameplay/execution-receipt.json",
                "evaluations/visual/execution-receipt.json",
            ],
        )

    def test_missing_receipt_keeps_evaluation_incomplete(self) -> None:
        (self.project / "evaluations/visual/execution-receipt.json").unlink()
        with self.assertRaises(MODULE.EvaluationAssemblyError) as caught:
            MODULE.assemble(
                self.project,
                self.fabric,
                "candidate-1",
                verifier=self.verify,
            )
        self.assertEqual(caught.exception.code, "E_RECEIPT_MISSING")

    def test_wrong_evaluator_identity_is_rejected(self) -> None:
        self.write_receipt("evaluations/visual/execution-receipt.json", "gameplay")
        with self.assertRaises(MODULE.EvaluationAssemblyError) as caught:
            MODULE.assemble(
                self.project,
                self.fabric,
                "candidate-1",
                verifier=self.verify,
            )
        self.assertEqual(caught.exception.code, "E_BINDING")

    def test_wrong_objective_is_rejected(self) -> None:
        path = self.project / "evaluations/gameplay/execution-receipt.json"
        receipt = json.loads(path.read_text())
        receipt["objective_id"] = "other"
        self.write_json("evaluations/gameplay/execution-receipt.json", receipt)
        with self.assertRaises(MODULE.EvaluationAssemblyError) as caught:
            MODULE.assemble(
                self.project,
                self.fabric,
                "candidate-1",
                verifier=self.verify,
            )
        self.assertEqual(caught.exception.code, "E_BINDING")

    def test_evaluation_assembly_rejects_production_phase(self) -> None:
        self.fabric["outcome_loop"]["phase"] = "build_candidate"
        with self.assertRaises(MODULE.EvaluationAssemblyError) as caught:
            MODULE.assemble(
                self.project,
                self.fabric,
                "candidate-1",
                verifier=self.verify,
            )
        self.assertEqual(caught.exception.code, "E_PHASE")


if __name__ == "__main__":
    unittest.main()
