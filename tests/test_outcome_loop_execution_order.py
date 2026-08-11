from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/elastic-company-os/scripts/outcome_loop.py"
spec = importlib.util.spec_from_file_location("outcome_loop_execution_order", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(MODULE)


def write_contract(root: Path, name: str, value: dict) -> dict:
    value = dict(value)
    value["contract_sha256"] = None
    value["contract_sha256"] = MODULE.digest(value)
    path = root / name
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return {"path": name, "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "contract_sha256": value["contract_sha256"]}


def control(root: Path, lane: str, *, calibration_name: str = "calibrations-empty.json") -> dict:
    outcome = write_contract(root, "outcome.json", {"$schema": MODULE.OUTCOME_SCHEMA, "objective_id": "obj", "outcome_claims": []})
    artifacts = write_contract(root, "artifacts.json", {"$schema": MODULE.ARTIFACT_SCHEMA, "objective_id": "obj", "artifact_classes": [
        {"artifact_class_id": "web_app", "required": True},
        {"artifact_class_id": "support_widget", "required": True},
        {"artifact_class_id": "help_center", "required": True},
        {"artifact_class_id": "billing_runtime", "required": True},
    ]})
    evaluators = write_contract(root, "evaluators.json", {"$schema": MODULE.EVALUATOR_SCHEMA, "objective_id": "obj", "evaluators": [
        {"evaluator_id": "reality-judge", "required": True, "artifact_classes": ["web_app"], "score_dimensions": ["correctness"]}
    ]})
    benchmarks = write_contract(root, "benchmarks.json", {"$schema": MODULE.BENCHMARK_SCHEMA, "objective_id": "obj"})
    calibration_path = root / calibration_name
    if not calibration_path.exists(): calibration_path.write_text("[]\n")
    calibration_binding = {"path": calibration_name, "file_sha256": hashlib.sha256(calibration_path.read_bytes()).hexdigest(), "receipts_sha256": MODULE.digest([])}
    scale_binding = {"path": None, "file_sha256": None, "authorization_sha256": None}
    raw = {
        "$schema": MODULE.CONTROL_SCHEMA,
        "schema_version": 1,
        "execution_lane": lane,
        "project_id": "project",
        "program_version": 1,
        "work_id": "work",
        "governed_outcome": "Build the real product.",
        "objective_id": "obj",
        "original_objective": "Build the real product.",
        "outcome": outcome,
        "artifacts": artifacts,
        "evaluators": evaluators,
        "benchmarks": benchmarks,
        "calibrations": calibration_binding,
        "calibration_receipts": [],
        "scale_authorization": scale_binding,
        "state_sha256": None,
    }
    raw["state_sha256"] = MODULE.digest(raw)
    return raw


class OutcomeLoopExecutionOrderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.initial = MODULE.start({"$schema": MODULE.REQUEST_SCHEMA, "objective_id": "obj", "original_objective": "Build the real product."})

    def tearDown(self): self.temp.cleanup()

    def test_pilot_bundles_all_required_artifacts_into_at_most_two_execution_lanes(self):
        bound = MODULE.bind_control(self.root, self.initial, control(self.root, "pilot"))
        lanes = bound["organization_plan"]["production_lanes"]
        self.assertLessEqual(len(lanes), 2)
        covered = sorted({klass for lane in lanes for klass in lane["artifact_classes"]})
        self.assertEqual(covered, ["billing_runtime", "help_center", "support_widget", "web_app"])
        self.assertEqual(bound["required_artifact_classes"], covered)
        self.assertEqual(bound["control_state"]["execution_lane"], "pilot")

    def test_control_can_be_refreshed_after_candidate_exists_without_restarting_loop(self):
        bound = MODULE.bind_control(self.root, self.initial, control(self.root, "pilot"))
        evaluating = MODULE.seal({**bound, "phase": "evaluate"})
        promoted_control = control(self.root, "production_scale")
        promoted_control["scale_authorization"] = {"path": "scale.json", "file_sha256": "a" * 64, "authorization_sha256": "b" * 64}
        promoted_control["state_sha256"] = MODULE.digest({**promoted_control, "state_sha256": None})
        refreshed = MODULE.refresh_control(self.root, evaluating, promoted_control)
        self.assertEqual(refreshed["phase"], "evaluate")
        self.assertEqual(refreshed["control_state"]["execution_lane"], "production_scale")
        self.assertEqual(refreshed["required_artifact_classes"], bound["required_artifact_classes"])
        self.assertEqual(refreshed["iteration"], bound["iteration"])
        self.assertEqual(refreshed["history"][-1]["event"], "outcome_control_refreshed")


if __name__ == "__main__": unittest.main()
