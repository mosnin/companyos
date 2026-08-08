from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1];SCRIPT=ROOT/"skills"/"company-os"/"compile-outcome-evaluators"/"scripts"/"compile_evaluator_runtime.py"
s=importlib.util.spec_from_file_location("ev",SCRIPT);M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
class EvaluatorRuntimeTests(unittest.TestCase):
 def test_research_method_cannot_satisfy_required_evaluator(self):
  r={"$schema":M.SCHEMA,"objective_id":"game","evaluators":[{"evaluator_id":"gameplay","label":"Gameplay review","required":True,"independent_role":True,"research_only":True,"adapter_locator":"tool://game/play","artifact_classes":["playable-build"],"produces_evidence":["play-trace"],"score_dimensions":["fun"]}]}
  o=M.compile_contract(r);self.assertFalse(o["ready"]);self.assertIn("RESEARCH_ONLY",{x["code"] for x in o["blockers"]})
 def test_candidate_self_review_is_not_independent(self):
  r={"$schema":M.SCHEMA,"objective_id":"game","evaluators":[{"evaluator_id":"self","label":"Self review","required":True,"independent_role":False,"research_only":False,"adapter_locator":"tool://game/play","artifact_classes":["playable-build"],"produces_evidence":["score"],"score_dimensions":[]}]}
  self.assertIn("NOT_INDEPENDENT",{x["code"] for x in M.compile_contract(r)["blockers"]})
 def test_executable_independent_evaluator_passes(self):
  r={"$schema":M.SCHEMA,"objective_id":"game","evaluators":[{"evaluator_id":"gameplay","label":"Gameplay evaluator","required":True,"independent_role":True,"research_only":False,"adapter_locator":"tool://game/play","artifact_classes":["playable-build"],"produces_evidence":["play-trace","video"],"score_dimensions":["clarity","fun","polish"]}]}
  self.assertTrue(M.compile_contract(r)["ready"])
if __name__=="__main__":unittest.main()
