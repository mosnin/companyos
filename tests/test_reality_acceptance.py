from __future__ import annotations
import importlib.util, json, tempfile
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"skills"/"company-os"/"accept-outcome-reality"/"scripts"/"accept_reality.py"
s=importlib.util.spec_from_file_location("accept_reality_under_test",P); M=importlib.util.module_from_spec(s); assert s.loader is not None; s.loader.exec_module(M)

class FakeExecution:
 @staticmethod
 def verify_receipt(project_root,receipt): return {"objective_id":receipt["objective_id"],"evaluator_id":receipt["evaluator_id"],"receipt_sha256":receipt["receipt_sha256"]}
class FakeCalibration:
 @staticmethod
 def verify_receipt(project_root,receipt): return {"objective_id":receipt["objective_id"],"evaluator_id":receipt["evaluator_id"],"execution_bound":True,"passed":receipt["passed"],"receipt_sha256":receipt["receipt_sha256"]}

class RealityAcceptanceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.project=Path(self.tmp.name); M._EXECUTION_MODULE=FakeExecution; M._CALIBRATION_MODULE=FakeCalibration; self.objective_id="game"; self.objective="Make a viral game."; self._write_sources()
 def tearDown(self): M._EXECUTION_MODULE=None; M._CALIBRATION_MODULE=None; self.tmp.cleanup()
 def _write_json(self,name,value):
  p=self.project/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n"); return p
 def _contract(self,schema,extra):
  v={"$schema":schema,"schema_version":1,"objective_id":self.objective_id,**extra,"contract_sha256":None}; v["contract_sha256"]=M.digest({**v,"contract_sha256":None}); return v
 def _write_sources(self):
  self._write_json("outcome.json",self._contract(M.OUTCOME_SCHEMA,{"original_objective":self.objective,"outcome_claims":[{"claim_id":"playable","statement":"A player can complete the core loop.","evidence_bindings":[]}],"pilot_allowed":True}))
  self._write_json("artifacts.json",self._contract(M.ARTIFACT_SCHEMA,{"ready":True,"artifact_classes":[{"artifact_class_id":"playable_game","required":True,"required_evidence":["interaction_trace"]}]})); self._write_json("evaluators.json",self._contract(M.EVALUATOR_SCHEMA,{"ready":True,"evaluators":[]})); self._write_json("benchmarks.json",self._contract(M.BENCHMARK_SCHEMA,{"ready":True,"benchmarks":[]}))
  self._write_json("calibrations.json",[{"$schema":M.CALIBRATION_SCHEMA,"objective_id":self.objective_id,"evaluator_id":"gameplay","execution_bound":True,"passed":True,"receipt_sha256":"c"*64}])
  artifact=self.project/"game.bin"; artifact.write_bytes(b"playable"); self.artifact_sha=M.file_digest(artifact)
  trace=self.project/"interaction.json"; trace.write_text("{}\n"); trace_sha=M.file_digest(trace)
  self._write_json("eval.json",{"$schema":"company-os.evaluator-execution-receipt.v1","schema_version":1,"objective_id":self.objective_id,"evaluator_id":"gameplay","production_actor_ids":["worker"],"independent_role":True,"accepted":True,"evidence_bindings":[{"evidence_id":"interaction","evidence_type":"interaction_trace","path":"interaction.json","sha256":trace_sha,"size":trace.stat().st_size}],"receipt_sha256":"d"*64})
 def request(self):
  return {"$schema":M.REQUEST_SCHEMA,"objective_id":self.objective_id,"original_objective":self.objective,"candidate_id":"candidate-1","production_actor_ids":["worker"],"production_narrative_admissible":False,"source_paths":{"outcome_contract":"outcome.json","artifact_contract":"artifacts.json","evaluator_contract":"evaluators.json","benchmark_contract":"benchmarks.json","calibration_receipts":"calibrations.json"},"claims":[{"claim_id":"playable","statement":"A player can complete the core loop.","required":True,"artifact_evidence":[{"artifact_id":"game","artifact_class_id":"playable_game","path":"game.bin","sha256":self.artifact_sha}],"evaluator_execution_receipt_paths":["eval.json"]}]}
 def test_execution_bound_reality_accepts_and_reverifies(self):
  receipt=M.accept(self.project,self.request()); self.assertTrue(receipt["accepted"]); self.assertTrue(receipt["execution_bound"]); verified=M.verify_receipt(self.project,receipt); self.assertTrue(verified["accepted"]); self.assertEqual(verified["candidate_id"],"candidate-1")
 def test_production_narrative_is_never_authority(self):
  r=self.request(); r["production_narrative_admissible"]=True
  with self.assertRaises(M.RealityError) as ctx: M.accept(self.project,r)
  self.assertEqual(ctx.exception.code,"E_AUTHORITY")
 def test_rejected_independent_evaluator_blocks_reality(self):
  evaluation=json.loads((self.project/"eval.json").read_text()); evaluation["accepted"]=False; self._write_json("eval.json",evaluation); receipt=M.accept(self.project,self.request()); self.assertFalse(receipt["accepted"]); self.assertEqual({x["code"] for x in receipt["blockers"]},{"INDEPENDENT_EVALUATION_FAILED"})
 def test_required_observation_evidence_is_not_optional(self):
  evaluation=json.loads((self.project/"eval.json").read_text()); evaluation["evidence_bindings"]=[]; self._write_json("eval.json",evaluation)
  receipt=M.accept(self.project,self.request()); self.assertFalse(receipt["accepted"])
  self.assertEqual({item["code"] for item in receipt["blockers"]},{"REQUIRED_OBSERVATION_EVIDENCE_MISSING"})
 def test_artifact_drift_invalidates_existing_reality_receipt(self):
  receipt=M.accept(self.project,self.request()); (self.project/"game.bin").write_bytes(b"changed")
  with self.assertRaises(M.RealityError) as ctx: M.verify_receipt(self.project,receipt)
  self.assertEqual(ctx.exception.code,"E_DIGEST")
if __name__=="__main__": unittest.main()
