from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1];P=ROOT/"skills"/"company-os"/"calibrate-outcome-evaluator"/"scripts"/"calibrate_evaluator.py"
s=importlib.util.spec_from_file_location("cal",P);M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
class CalibrationTests(unittest.TestCase):
 def req(self,scores):
  return {"$schema":M.SCHEMA,"evaluator_id":"gameplay","required_dimensions":["fun","polish"],"candidates":[
   {"candidate_id":"progress-bar","expected_rank":1,"scores":scores[0]},
   {"candidate_id":"weak-game","expected_rank":2,"scores":scores[1]},
   {"candidate_id":"reference","expected_rank":3,"scores":scores[2]}]}
 def test_correct_discrimination_passes(self):
  o=M.calibrate(self.req([{"fun":1,"polish":1},{"fun":5,"polish":4},{"fun":9,"polish":9}]))
  self.assertTrue(o["passed"])
 def test_tie_fails(self):
  o=M.calibrate(self.req([{"fun":1,"polish":1},{"fun":5,"polish":4},{"fun":5,"polish":9}]))
  self.assertFalse(o["passed"]);self.assertEqual(o["pairwise_failures"][0]["dimension"],"fun")
 def test_inverted_quality_fails(self):
  o=M.calibrate(self.req([{"fun":8,"polish":1},{"fun":5,"polish":4},{"fun":9,"polish":9}]))
  self.assertFalse(o["passed"])
if __name__=="__main__":unittest.main()
