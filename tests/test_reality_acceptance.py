from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1];P=ROOT/"skills"/"company-os"/"accept-outcome-reality"/"scripts"/"accept_reality.py"
s=importlib.util.spec_from_file_location("ra",P);M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
class RealityAcceptanceTests(unittest.TestCase):
 def req(self):
  return {"$schema":M.SCHEMA,"objective_id":"game","original_objective":"Make a viral game.","production_narrative_admissible":False,
   "calibration_receipts":[{"evaluator_id":"gameplay","passed":True}],
   "claims":[{"claim_id":"playable","statement":"A player can complete the core loop.","required":True,
    "artifact_evidence":[{"type":"play_trace","sha256":"abc"}],
    "evaluator_receipts":[{"evaluator_id":"gameplay","independent_role":True,"accepted":True}]}]}
 def test_independent_real_evidence_accepts(self): self.assertTrue(M.accept(self.req())["accepted"])
 def test_team_completion_narrative_cannot_be_admissible(self):
  r=self.req();r["production_narrative_admissible"]=True
  with self.assertRaises(M.RealityError) as c:M.accept(r)
  self.assertEqual(c.exception.code,"E_AUTHORITY")
 def test_failed_calibration_blocks_before_reality_judgment(self):
  r=self.req();r["calibration_receipts"][0]["passed"]=False
  with self.assertRaises(M.RealityError) as c:M.accept(r)
  self.assertEqual(c.exception.code,"E_CALIBRATION")
 def test_missing_artifact_evidence_blocks(self):
  r=self.req();r["claims"][0]["artifact_evidence"]=[]
  o=M.accept(r);self.assertFalse(o["accepted"]);self.assertIn("NO_ARTIFACT_EVIDENCE",{x["code"] for x in o["blockers"]})
if __name__=="__main__":unittest.main()
