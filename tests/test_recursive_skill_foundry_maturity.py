from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/recursive-skill-foundry/scripts/skill_foundry.py"
spec = importlib.util.spec_from_file_location("recursive_skill_foundry_maturity", SCRIPT)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


def artifact_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class FoundryTriggerEvalAndMaturityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def forge(self, request: str, **kwargs):
        result = MODULE.forge_candidate(self.project, request, **kwargs)
        self.assertEqual(result["status"], "validated", result)
        return result

    def test_simulation_grades_train_dev_and_holdout_splits(self) -> None:
        result = self.forge(
            "Create a Codex skill that repairs failed Next.js deployments on Vercel using logs and local validation.",
        )
        simulation = json.loads((self.project / result["candidate_path"] / "simulation.json").read_text(encoding="utf-8"))
        self.assertEqual(set(simulation["splits"]), {"train", "dev", "holdout"})
        for split in ("train", "dev", "holdout"):
            self.assertEqual(simulation["splits"][split]["status"], "pass", simulation["splits"][split])
        self.assertEqual(simulation["trigger_grade"], 100)
        self.assertEqual(result["trigger_grade"], 100)
        self.assertEqual(result["description_eval_status"], "pass")
        candidate = MODULE.load_candidate(self.project / result["candidate_path"])
        self.assertEqual(candidate["description_eval_status"], "pass")
        self.assertEqual(candidate["trigger_grade"], 100)

    def test_description_eval_runs_before_packaging_artifacts_exist(self) -> None:
        description = MODULE.infer_description(
            "deployment-build-repair",
            "Create a Codex skill that repairs failed deployment builds using logs and local validation.",
        )
        report = MODULE.evaluate_description("deployment-build-repair", description)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(set(report["splits"]), {"dev", "holdout"})
        self.assertEqual(report["trigger_grade"], 100)

    def test_mismatched_description_fails_the_train_split(self) -> None:
        train = MODULE.build_examples(
            "kitchen-recipe-planner",
            "Create a skill for reviewing database schema migrations.",
        )
        report = MODULE.evaluate_description(
            "kitchen-recipe-planner",
            "Plan weekly kitchen recipes and grocery lists for a household. Use when the user asks for meal planning help. Do not use for unrelated engineering work.",
            train,
        )
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["splits"]["train"]["status"], "fail")
        self.assertLess(report["trigger_grade"], 100)
        self.assertEqual(report["splits"]["holdout"]["status"], "pass")

    def test_holdout_cases_stay_outside_authored_examples(self) -> None:
        result = self.forge(
            "Create a reusable Codex skill for collecting incident timelines, owner decisions, corrective actions, and verification evidence.",
        )
        skill_dir = self.project / result["candidate_path"] / "skill" / result["skill_name"]
        authored = {case.get("case_id") for case in MODULE.examples_from(skill_dir)}
        holdout = {case["case_id"] for case in MODULE.fixed_holdout_cases(result["skill_name"])}
        self.assertFalse(authored & holdout)

    def test_maturity_levels_track_the_promotion_lifecycle(self) -> None:
        result = self.forge(
            "Create a reusable Codex skill for auditing changelog completeness before each release.",
        )
        name = result["skill_name"]
        first = MODULE.maturity_report(self.project, name)
        self.assertEqual(first["level"], "validated")
        self.assertFalse(first["installed"])
        MODULE.promote_candidate(self.project, name)
        second = MODULE.maturity_report(self.project, name)
        self.assertEqual(second["level"], "project_approved")
        self.assertGreater(second["maturity_score"], first["maturity_score"])
        for index, project_id in enumerate(("project-one", "project-two"), 1):
            MODULE.record_evidence(
                self.project,
                name,
                run_id=f"run-{index}",
                objective_id=f"objective-{index}",
                project_id=project_id,
                outcome="accepted",
                artifact_sha256=artifact_digest(f"artifact-{index}"),
                notes="Independent checks passed.",
            )
        third = MODULE.maturity_report(self.project, name)
        self.assertEqual(third["level"], "field_proven")
        self.assertEqual(third["accepted_independent_runs"], 2)
        MODULE.record_evidence(
            self.project,
            name,
            run_id="run-3",
            objective_id="objective-3",
            project_id="project-three",
            outcome="accepted",
            artifact_sha256=artifact_digest("artifact-3"),
            notes="A third independent project passed the same checks.",
        )
        fourth = MODULE.maturity_report(self.project, name)
        self.assertEqual(fourth["level"], "core_eligible")
        self.assertEqual(fourth["distinct_projects"], 3)
        self.assertGreater(fourth["maturity_score"], third["maturity_score"])

    def test_rejected_field_evidence_marks_maturity_regressed(self) -> None:
        result = self.forge(
            "Create a reusable Codex skill for validating billing invoice exports before delivery.",
        )
        name = result["skill_name"]
        MODULE.promote_candidate(self.project, name)
        MODULE.record_evidence(
            self.project,
            name,
            run_id="run-bad",
            objective_id="objective-bad",
            project_id="project-one",
            outcome="rejected",
            artifact_sha256=artifact_digest("artifact-bad"),
            notes="Independent checks rejected the output.",
        )
        report = MODULE.maturity_report(self.project, name)
        self.assertEqual(report["level"], "regressed")
        self.assertEqual(report["rejected_receipts"], 1)

    def test_maturity_report_is_content_addressed(self) -> None:
        result = self.forge(
            "Create a reusable Codex skill for auditing dependency license compliance in a repository.",
        )
        report = MODULE.maturity_report(self.project, result["skill_name"])
        unsigned = dict(report)
        observed = unsigned["maturity_sha256"]
        unsigned["maturity_sha256"] = None
        self.assertEqual(MODULE.digest(unsigned), observed)


if __name__ == "__main__":
    unittest.main()
