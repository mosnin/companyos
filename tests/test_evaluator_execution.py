from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "skills"
    / "company-os"
    / "execute-outcome-evaluator"
    / "scripts"
    / "execute_evaluator.py"
)
SPEC = importlib.util.spec_from_file_location("execute_evaluator", MODULE_PATH)
assert SPEC and SPEC.loader
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def seal(value: dict, field: str) -> dict:
    result = dict(value)
    result[field] = runtime.digest({**result, field: None})
    return result


ADAPTER_SOURCE = r'''#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import sys

request = json.loads(sys.stdin.read())
artifact = request["artifacts"][0]
content = Path(artifact["resolved_path"]).read_text(encoding="utf-8")
mode = request["arguments"].get("mode", "valid")
if mode == "fail":
    raise SystemExit(7)
run_id = request["run_id"]
evidence_path = Path("evidence") / f"{run_id}.json"
evidence_path.parent.mkdir(parents=True, exist_ok=True)
evidence_path.write_text(
    json.dumps({"artifact_sha256": hashlib.sha256(content.encode()).hexdigest()}),
    encoding="utf-8",
)
objective_id = request["objective_id"] if mode != "wrong_objective" else "wrong"
evidence = [] if mode == "missing_evidence" else [
    {"evidence_id": "play-trace", "evidence_type": "play_trace", "path": evidence_path.as_posix()}
]
scores = {"fun": 9.5, "polish": 9.0}
if mode == "missing_score":
    scores.pop("polish")
output = {
    "$schema": "company-os.evaluator-adapter-output.v1",
    "run_id": run_id,
    "objective_id": objective_id,
    "evaluator_id": request["evaluator_id"],
    "accepted": "excellent" in content,
    "scores": scores,
    "findings": [],
    "evidence": evidence,
}
sys.stdout.write(json.dumps(output, sort_keys=True, separators=(",", ":")))
'''


class EvaluatorExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.objective_id = "viral-game"
        self.evaluator_id = "gameplay"
        self.artifact = self.root / "build.txt"
        self.artifact.write_text("excellent playable build", encoding="utf-8")
        self.adapter = self.root / "evaluators" / "gameplay.py"
        self.adapter.parent.mkdir(parents=True)
        self.adapter.write_text(ADAPTER_SOURCE, encoding="utf-8")
        self.write_contracts()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_json(self, name: str, value: object) -> str:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return name

    def write_contracts(self) -> None:
        evaluator_contract = seal(
            {
                "$schema": runtime.CONTRACT_SCHEMA,
                "schema_version": 1,
                "objective_id": self.objective_id,
                "evaluators": [
                    {
                        "evaluator_id": self.evaluator_id,
                        "label": "Gameplay evaluator",
                        "required": True,
                        "independent_role": True,
                        "research_only": False,
                        "adapter_locator": "workspace://evaluators/gameplay",
                        "artifact_classes": ["playable-build"],
                        "produces_evidence": ["play_trace"],
                        "score_dimensions": ["fun", "polish"],
                    }
                ],
                "blockers": [],
                "ready": True,
                "contract_sha256": None,
            },
            "contract_sha256",
        )
        benchmark_contract = seal(
            {
                "$schema": runtime.BENCHMARK_SCHEMA,
                "schema_version": 1,
                "objective_id": self.objective_id,
                "dimensions": [
                    {
                        "dimension_id": "polish",
                        "label": "Polish",
                        "required": True,
                        "references": [
                            {
                                "reference_id": "bad",
                                "locator": "reference://bad",
                                "provenance": "curated",
                                "quality_tier": "negative",
                            },
                            {
                                "reference_id": "great",
                                "locator": "reference://great",
                                "provenance": "curated",
                                "quality_tier": "exemplar",
                            },
                        ],
                    }
                ],
                "blockers": [],
                "ready": True,
                "contract_sha256": None,
            },
            "contract_sha256",
        )
        registry = seal(
            {
                "$schema": runtime.REGISTRY_SCHEMA,
                "schema_version": 1,
                "adapters": [
                    {
                        "adapter_locator": "workspace://evaluators/gameplay",
                        "runtime": "python",
                        "entrypoint": "evaluators/gameplay.py",
                        "entrypoint_sha256": runtime.file_digest(self.adapter),
                        "timeout_seconds": 10,
                        "max_output_bytes": 1024 * 1024,
                        "arguments": [],
                        "artifact_classes": ["playable-build"],
                        "produces_evidence": ["play_trace"],
                        "score_dimensions": ["fun", "polish"],
                    }
                ],
                "registry_sha256": None,
            },
            "registry_sha256",
        )
        self.write_json("evaluator-contract.json", evaluator_contract)
        self.write_json("benchmark-contract.json", benchmark_contract)
        self.write_json("adapter-registry.json", registry)

    def request(self, *, mode: str = "valid") -> dict:
        return {
            "$schema": runtime.REQUEST_SCHEMA,
            "run_id": "run-1",
            "objective_id": self.objective_id,
            "evaluator_id": self.evaluator_id,
            "evaluator_contract_path": "evaluator-contract.json",
            "adapter_registry_path": "adapter-registry.json",
            "benchmark_contract_path": "benchmark-contract.json",
            "executor_actor_id": "independent-reviewer",
            "production_actor_ids": ["builder", "manager"],
            "artifacts": [
                {
                    "artifact_id": "game-build",
                    "artifact_class_id": "playable-build",
                    "path": "build.txt",
                    "sha256": runtime.file_digest(self.artifact),
                }
            ],
            "arguments": {"mode": mode},
        }

    def test_executes_adapter_and_binds_actual_files(self) -> None:
        receipt = runtime.execute(self.root, self.request())
        self.assertTrue(receipt["accepted"])
        self.assertTrue(receipt["independent_role"])
        self.assertEqual(receipt["scores"], {"fun": 9.5, "polish": 9.0})
        self.assertEqual(receipt["artifact_bindings"][0]["sha256"], runtime.file_digest(self.artifact))
        self.assertEqual(receipt["evidence_bindings"][0]["evidence_type"], "play_trace")
        verified = runtime.verify_receipt(self.root, receipt)
        self.assertTrue(verified["accepted"])
        self.assertEqual(verified["receipt_sha256"], receipt["receipt_sha256"])

    def test_production_actor_cannot_execute_independent_evaluation(self) -> None:
        request = self.request()
        request["executor_actor_id"] = "builder"
        with self.assertRaises(runtime.EvaluatorExecutionError) as caught:
            runtime.execute(self.root, request)
        self.assertEqual(caught.exception.code, "E_AUTHORITY")

    def test_artifact_digest_mismatch_blocks_before_adapter_runs(self) -> None:
        request = self.request()
        request["artifacts"][0]["sha256"] = "0" * 64
        with self.assertRaises(runtime.EvaluatorExecutionError) as caught:
            runtime.execute(self.root, request)
        self.assertEqual(caught.exception.code, "E_DIGEST")
        self.assertFalse((self.root / "evidence").exists())

    def test_adapter_digest_mismatch_blocks_execution(self) -> None:
        registry_path = self.root / "adapter-registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["adapters"][0]["entrypoint_sha256"] = "0" * 64
        registry = seal(registry, "registry_sha256")
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        with self.assertRaises(runtime.EvaluatorExecutionError) as caught:
            runtime.execute(self.root, self.request())
        self.assertEqual(caught.exception.code, "E_DIGEST")

    def test_missing_required_evidence_rejects_output(self) -> None:
        with self.assertRaises(runtime.EvaluatorExecutionError) as caught:
            runtime.execute(self.root, self.request(mode="missing_evidence"))
        self.assertEqual(caught.exception.code, "E_OUTPUT")

    def test_missing_required_score_rejects_output(self) -> None:
        with self.assertRaises(runtime.EvaluatorExecutionError) as caught:
            runtime.execute(self.root, self.request(mode="missing_score"))
        self.assertEqual(caught.exception.code, "E_OUTPUT")

    def test_output_identity_mismatch_rejects(self) -> None:
        with self.assertRaises(runtime.EvaluatorExecutionError) as caught:
            runtime.execute(self.root, self.request(mode="wrong_objective"))
        self.assertEqual(caught.exception.code, "E_BINDING")

    def test_receipt_detects_artifact_drift(self) -> None:
        receipt = runtime.execute(self.root, self.request())
        self.artifact.write_text("substituted", encoding="utf-8")
        with self.assertRaises(runtime.EvaluatorExecutionError) as caught:
            runtime.verify_receipt(self.root, receipt)
        self.assertEqual(caught.exception.code, "E_DIGEST")

    def test_symlinked_artifact_is_rejected(self) -> None:
        target = self.root / "real-build.txt"
        target.write_text("excellent playable build", encoding="utf-8")
        self.artifact.unlink()
        try:
            self.artifact.symlink_to(target)
        except OSError:
            self.skipTest("symlinks are not supported on this platform")
        request = self.request()
        request["artifacts"][0]["sha256"] = runtime.file_digest(target)
        with self.assertRaises(runtime.EvaluatorExecutionError) as caught:
            runtime.execute(self.root, request)
        self.assertEqual(caught.exception.code, "E_PATH")

    def test_nonzero_adapter_exit_is_controlled(self) -> None:
        with self.assertRaises(runtime.EvaluatorExecutionError) as caught:
            runtime.execute(self.root, self.request(mode="fail"))
        self.assertEqual(caught.exception.code, "E_ADAPTER")
        self.assertIn("stderr_sha256", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
