from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "company-os" / "elastic-company-os" / "scripts" / "outcome_loop.py"
spec = importlib.util.spec_from_file_location("outcome_loop_under_test", MODULE_PATH)
M = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(M)


class OutcomeLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.objective = "Make a viral game."
        self.objective_id = "viral-game"
        self._write_sources()
        self.state = M.start({"$schema": M.REQUEST_SCHEMA,"objective_id": self.objective_id,"original_objective": self.objective})
        self.control = self._control()
        self.bound = M.bind_control(self.project, self.state, self.control)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _self_digest(self, value: dict, field: str) -> dict:
        value[field] = None
        value[field] = M.digest(value)
        return value

    def _write(self, name: str, value) -> str:
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, (dict, list)):
            path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        else:
            path.write_bytes(value)
        return name

    def _write_sources(self) -> None:
        outcome = self._self_digest({"$schema": M.OUTCOME_SCHEMA,"schema_version": 1,"objective_id": self.objective_id,"original_objective": self.objective,"outcome_claims": [{"claim_id": "playable","statement": "A player can complete the core loop.","evidence_bindings": ["playable_game", "gameplay-evaluator"]}],"pilot_allowed": True,"scale_allowed": False,"blockers": [],"contract_sha256": None},"contract_sha256")
        artifacts = self._self_digest({"$schema": M.ARTIFACT_SCHEMA,"schema_version": 1,"objective_id": self.objective_id,"ready": True,"artifact_classes": [{"artifact_class_id": "playable_game","label": "Playable game","required": True}],"blockers": [],"contract_sha256": None},"contract_sha256")
        evaluators = self._self_digest({"$schema": M.EVALUATOR_SCHEMA,"schema_version": 1,"objective_id": self.objective_id,"ready": True,"evaluators": [{"evaluator_id": "gameplay-evaluator","required": True,"artifact_classes": ["playable_game"],"score_dimensions": ["gameplay", "visual_quality"]}],"blockers": [],"contract_sha256": None},"contract_sha256")
        benchmarks = self._self_digest({"$schema": M.BENCHMARK_SCHEMA,"schema_version": 1,"objective_id": self.objective_id,"ready": True,"benchmarks": [],"blockers": [],"contract_sha256": None},"contract_sha256")
        self._write("outcome.json", outcome); self._write("artifacts.json", artifacts); self._write("evaluators.json", evaluators); self._write("benchmarks.json", benchmarks); self._write("calibrations.json", [])

    def _binding(self, path: str) -> dict:
        file = self.project / path
        value = json.loads(file.read_text())
        result = {"path": path,"file_sha256": M.file_digest(file)}
        if isinstance(value, dict) and "contract_sha256" in value: result["contract_sha256"] = value["contract_sha256"]
        return result

    def _control(self) -> dict:
        value = {"$schema": M.CONTROL_SCHEMA,"schema_version": 1,"execution_lane": "pilot","project_id": "p","program_version": 1,"work_id": "w","governed_outcome": self.objective,"objective_id": self.objective_id,"original_objective": self.objective,"outcome": self._binding("outcome.json"),"artifacts": self._binding("artifacts.json"),"evaluators": self._binding("evaluators.json"),"benchmarks": self._binding("benchmarks.json"),"calibrations": {"path": "calibrations.json","file_sha256": M.file_digest(self.project / "calibrations.json"),"receipts_sha256": M.digest([])},"calibration_receipts": [],"scale_authorization": {"path": None,"file_sha256": None,"authorization_sha256": None},"state_sha256": None}
        value["state_sha256"] = M.digest({**value, "state_sha256": None})
        return value

    def _candidate(self, state: dict, candidate_id: str, payload: bytes = b"game") -> dict:
        name = f"{candidate_id}.bin"; self._write(name, payload)
        return M.record_candidate(self.project,state,{"$schema": M.CANDIDATE_SCHEMA,"candidate_id": candidate_id,"production_actor_ids": ["worker-1"],"artifacts": [{"artifact_id": "game","artifact_class_id": "playable_game","path": name,"sha256": M.file_digest(self.project / name)}]})

    def _receipt(self,state,candidate_id,gameplay,visual,accepted=True,finding=None):
        candidate = next(x for x in state["candidates"] if x["candidate_id"] == candidate_id)
        receipt = {"$schema": "company-os.evaluator-execution-receipt.v1","schema_version": 1,"run_id": f"run-{candidate_id}","objective_id": self.objective_id,"evaluator_id": "gameplay-evaluator","executor_actor_id": "judge-1","production_actor_ids": ["worker-1"],"independent_role": True,"accepted": accepted,"scores": {"gameplay": gameplay, "visual_quality": visual},"findings": [] if finding is None else [finding],"artifact_bindings": candidate["artifacts"],"evidence_bindings": [],"source_bindings": {},"execution": {},"receipt_sha256": "a" * 64}
        path = f"receipt-{candidate_id}.json"; self._write(path, receipt); return path

    @staticmethod
    def _fake_verify(project_root, receipt):
        return {"evaluator_id": receipt["evaluator_id"],"objective_id": receipt["objective_id"],"receipt_sha256": receipt["receipt_sha256"]}

    def _evaluate(self,state,candidate_id,gameplay,visual,accepted=True,finding=None):
        receipt_path = self._receipt(state,candidate_id,gameplay,visual,accepted,finding)
        return M.record_evaluations(self.project,state,{"$schema": M.EVALUATION_BATCH_SCHEMA,"candidate_id": candidate_id,"receipt_paths": [receipt_path]},verifier=self._fake_verify)

    def test_broad_objective_starts_in_discovery(self):
        state=M.start({"$schema":M.REQUEST_SCHEMA,"objective_id":"x","original_objective":"Build something excellent."})
        self.assertEqual(state["phase"],"discovery"); self.assertEqual(state["next_action"]["action"],"compile_outcome_contract")

    def test_control_compiles_initial_organization(self):
        self.assertEqual(self.bound["phase"],"build_candidate"); self.assertEqual(self.bound["required_artifact_classes"],["playable_game"])
        self.assertEqual(self.bound["organization_plan"]["production_lanes"][0]["artifact_class_id"],"playable_game")
        self.assertEqual(self.bound["organization_plan"]["evaluation_lanes"][0]["evaluator_id"],"gameplay-evaluator")

    def test_candidate_missing_required_artifact_is_rejected(self):
        bad=self.project/"bad.txt"; bad.write_text("x")
        with self.assertRaises(M.OutcomeLoopError) as ctx:
            M.record_candidate(self.project,self.bound,{"$schema":M.CANDIDATE_SCHEMA,"candidate_id":"bad","production_actor_ids":["worker-1"],"artifacts":[{"artifact_id":"text","artifact_class_id":"document","path":"bad.txt","sha256":M.file_digest(bad)}]})
        self.assertEqual(ctx.exception.code,"E_ARTIFACT")

    def test_weak_candidate_targets_dominant_gap_and_preserves_strength(self):
        candidate=self._candidate(self.bound,"c1"); result=self._evaluate(candidate,"c1",9.2,4.0); intervention=result["interventions"][-1]
        self.assertEqual(result["phase"],"rework"); self.assertEqual(intervention["target_dimensions"],["visual_quality"]); self.assertIn("gameplay",intervention["preserve_dimensions"]); self.assertEqual(intervention["mode"],"retask")

    def test_stagnation_reorganizes_instead_of_repeating_rework(self):
        c1=self._candidate(self.bound,"c1"); e1=self._evaluate(c1,"c1",9.2,4.0); c2=self._candidate(e1,"c2",b"game2"); e2=self._evaluate(c2,"c2",9.2,4.1); c3=self._candidate(e2,"c3",b"game3"); e3=self._evaluate(c3,"c3",9.2,4.2)
        self.assertEqual(e3["interventions"][-1]["mode"],"reorganize"); self.assertTrue(any("Challenge" in item for item in e3["interventions"][-1]["organization_mutation"]["instructions"]))

    def test_evaluator_rejection_blocks_even_with_high_scores(self):
        candidate=self._candidate(self.bound,"c1"); result=self._evaluate(candidate,"c1",9.2,9.2,accepted=False)
        self.assertEqual(result["phase"],"rework"); self.assertEqual(result["diagnoses"][-1]["rejected_evaluators"],["gameplay-evaluator"])

    def test_strong_candidate_routes_to_independent_reality(self):
        candidate=self._candidate(self.bound,"c1"); result=self._evaluate(candidate,"c1",9.2,9.2); template=result["next_action"]["request_template"]
        self.assertEqual(result["phase"],"reality"); self.assertFalse(template["production_narrative_admissible"]); self.assertEqual(template["candidate_id"],"c1"); self.assertEqual(template["claims"][0]["claim_id"],"playable")

    def test_accepted_reality_finishes_loop(self):
        candidate=self._candidate(self.bound,"c1"); ready=self._evaluate(candidate,"c1",9.2,9.2)
        receipt={"$schema":M.REALITY_SCHEMA,"schema_version":2,"execution_bound":True,"objective_id":self.objective_id,"candidate_id":"c1","accepted":True,"claim_decisions":[{"claim_id":"playable"}],"receipt_sha256":"b"*64}; self._write("reality.json",receipt)
        def verify(project_root,value): return {"objective_id":value["objective_id"],"candidate_id":value["candidate_id"],"accepted":value["accepted"],"claim_count":1,"receipt_sha256":value["receipt_sha256"]}
        done=M.record_reality(self.project,ready,"reality.json",verifier=verify); self.assertEqual(done["phase"],"accepted"); self.assertEqual(done["next_action"]["action"],"complete")

    def test_rejected_reality_returns_to_strategy_rework(self):
        candidate=self._candidate(self.bound,"c1"); ready=self._evaluate(candidate,"c1",9.2,9.2)
        receipt={"$schema":M.REALITY_SCHEMA,"schema_version":2,"execution_bound":True,"objective_id":self.objective_id,"candidate_id":"c1","accepted":False,"blockers":[{"claim_id":"playable","code":"FAILED"}],"receipt_sha256":"b"*64}; self._write("reality.json",receipt)
        def verify(project_root,value): return {"objective_id":value["objective_id"],"candidate_id":value["candidate_id"],"accepted":False,"claim_count":1,"receipt_sha256":value["receipt_sha256"]}
        result=M.record_reality(self.project,ready,"reality.json",verifier=verify); self.assertEqual(result["phase"],"rework"); self.assertEqual(result["interventions"][-1]["mode"],"reorganize"); self.assertEqual(result["interventions"][-1]["dominant_gap"]["kind"],"reality_rejection")

if __name__ == "__main__": unittest.main()
