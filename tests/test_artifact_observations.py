from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"skills"/"company-os"/"define-outcome-artifacts"/"scripts"/"compile_artifact_observations.py"
spec=importlib.util.spec_from_file_location("artifact_obs",SCRIPT); M=importlib.util.module_from_spec(spec); spec.loader.exec_module(M)

class ArtifactObservationTests(unittest.TestCase):
    def test_playable_game_rejects_text_only_proof(self):
        req={"$schema":M.SCHEMA,"objective_id":"game","artifact_classes":[{
            "artifact_class_id":"playable-build","label":"Playable game build","required":True,
            "modalities":["interactive","visual","audio","executable"],
            "observation_methods":["file_exists","build_succeeds"],
            "required_evidence":["artifact_digest","build_log"]}]}
        out=M.compile_contract(req)
        self.assertFalse(out["ready"])
        self.assertIn("RICH_ARTIFACT_TEXT_ONLY",{x["code"] for x in out["blockers"]})

    def test_playable_game_accepts_experiential_observation(self):
        req={"$schema":M.SCHEMA,"objective_id":"game","artifact_classes":[{
            "artifact_class_id":"playable-build","label":"Playable game build","required":True,
            "modalities":["interactive","visual","audio","executable"],
            "observation_methods":["launch_build","scripted_play_session","capture_video","capture_audio"],
            "required_evidence":["artifact_digest","play_trace","video_capture","audio_capture"]}]}
        self.assertTrue(M.compile_contract(req)["ready"])

    def test_service_requires_behavioral_observation(self):
        req={"$schema":M.SCHEMA,"objective_id":"api","artifact_classes":[{
            "artifact_class_id":"api","label":"Running API","required":True,
            "modalities":["service"],"observation_methods":["file_exists"],
            "required_evidence":["source_hash"]}]}
        self.assertFalse(M.compile_contract(req)["ready"])

    def test_required_document_rejects_text_only_observation(self):
        # A prose deliverable observed only by weak methods is planning currency,
        # not evidence: TEXT_ONLY_OBSERVATION blocks it even for non-rich classes.
        req={"$schema":M.SCHEMA,"objective_id":"docs","artifact_classes":[{
            "artifact_class_id":"launch-plan","label":"Launch plan document","required":True,
            "modalities":["text"],"observation_methods":["file_exists","text_review","hash_matches"],
            "required_evidence":["artifact_digest"]}]}
        out=M.compile_contract(req)
        self.assertFalse(out["ready"])
        self.assertIn("TEXT_ONLY_OBSERVATION",{x["code"] for x in out["blockers"]})

    def test_required_document_accepts_an_executed_check(self):
        req={"$schema":M.SCHEMA,"objective_id":"docs","artifact_classes":[{
            "artifact_class_id":"launch-plan","label":"Launch plan document","required":True,
            "modalities":["text"],"observation_methods":["text_review","structure_lint_executes"],
            "required_evidence":["artifact_digest","lint_receipt"]}]}
        self.assertTrue(M.compile_contract(req)["ready"])

    def test_advisory_document_stays_out_of_the_gate(self):
        req={"$schema":M.SCHEMA,"objective_id":"docs","artifact_classes":[
            {"artifact_class_id":"real-artifact","label":"Running service","required":True,
             "modalities":["service"],"observation_methods":["probe_endpoint_executes"],
             "required_evidence":["probe_receipt"]},
            {"artifact_class_id":"notes","label":"Advisory notes","required":False,
             "modalities":["text"],"observation_methods":["text_review"],
             "required_evidence":[]}]}
        self.assertTrue(M.compile_contract(req)["ready"])
if __name__=="__main__": unittest.main()
