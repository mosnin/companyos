from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1];P=ROOT/"skills"/"company-os"/"compile-outcome-benchmarks"/"scripts"/"compile_benchmarks.py"
s=importlib.util.spec_from_file_location("bm",P);M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
class BenchmarkTests(unittest.TestCase):
 def req(self,refs):
  return {"$schema":M.SCHEMA,"objective_id":"game","dimensions":[{"dimension_id":"polish","label":"Polish","required":True,"references":refs}]}
 def test_single_good_reference_is_not_enough_to_calibrate_discrimination(self):
  o=M.compile_contract(self.req([{"reference_id":"a","locator":"reference://a","provenance":"user","quality_tier":"exemplar"}]))
  self.assertIn("NO_DISCRIMINATION_TIERS",{x["code"] for x in o["blockers"]})
 def test_negative_and_exemplar_reference_set_passes(self):
  refs=[{"reference_id":"bad","locator":"reference://bad","provenance":"curated","quality_tier":"negative"},{"reference_id":"great","locator":"reference://great","provenance":"curated","quality_tier":"exemplar"}]
  self.assertTrue(M.compile_contract(self.req(refs))["ready"])
 def test_missing_positive_anchor_blocks(self):
  refs=[{"reference_id":"bad","locator":"reference://bad","provenance":"curated","quality_tier":"negative"},{"reference_id":"base","locator":"reference://base","provenance":"curated","quality_tier":"baseline"}]
  self.assertIn("NO_POSITIVE_ANCHOR",{x["code"] for x in M.compile_contract(self.req(refs))["blockers"]})
if __name__=="__main__":unittest.main()
