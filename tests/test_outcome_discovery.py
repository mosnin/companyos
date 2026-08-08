from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "company-os" / "close-outcome-discovery" / "scripts" / "close_outcome_discovery.py"
spec = importlib.util.spec_from_file_location("close_outcome_discovery", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(MODULE)


def request() -> dict:
    return {
        "$schema": "company-os.outcome-request.v1",
        "objective_id": "viral-game",
        "objective": "Make a viral game.",
        "outcome_claims": [],
        "domain_hypotheses": [],
        "artifact_classes": [],
        "evaluators": [],
        "benchmarks": [],
        "unknowns": [{
            "unknown_id": "engine",
            "question": "Which engine and runtime are required?",
            "blocking": True,
            "resolved": False,
            "closure_evidence": ["platform_documentation"],
        }],
        "reality_acceptance": None,
    }


class DiscoveryClosureTests(unittest.TestCase):
    def report(self, req: dict) -> dict:
        return {
            "$schema": "company-os.outcome-discovery-report.v1",
            "objective_id": "viral-game",
            "request_sha256": MODULE.digest(req),
            "resolutions": [{
                "unknown_id": "engine",
                "conclusion": "The target platform contract requires a web runtime; Unity is not required.",
                "citations": ["source://platform/docs/runtime"],
                "counterevidence": [],
                "reconciliation": None,
                "closure_evidence": ["platform_documentation"],
            }],
            "domain_hypotheses": [{
                "domain_id": "runtime",
                "hypothesis": "The platform executes web bundles.",
                "status": "supported",
                "source_bindings": ["source://platform/docs/runtime"],
            }],
        }

    def test_cited_resolution_closes_unknown_and_preserves_objective(self) -> None:
        req = request()
        updated = MODULE.apply_report(req, self.report(req))
        self.assertEqual(updated["objective"], req["objective"])
        self.assertTrue(updated["unknowns"][0]["resolved"])
        self.assertEqual(updated["domain_hypotheses"][0]["status"], "supported")

    def test_uncited_resolution_rejects(self) -> None:
        req = request()
        report = self.report(req)
        report["resolutions"][0]["citations"] = []
        with self.assertRaises(MODULE.DiscoveryError) as ctx:
            MODULE.apply_report(req, report)
        self.assertEqual(ctx.exception.code, "E_EVIDENCE")

    def test_stale_report_rejects(self) -> None:
        req = request()
        report = self.report(req)
        req["objective"] = "Changed objective"
        with self.assertRaises(MODULE.DiscoveryError) as ctx:
            MODULE.apply_report(req, report)
        self.assertEqual(ctx.exception.code, "E_BINDING")

    def test_counterevidence_requires_reconciliation(self) -> None:
        req = request()
        report = self.report(req)
        report["resolutions"][0]["counterevidence"] = ["source://contradiction"]
        with self.assertRaises(MODULE.DiscoveryError) as ctx:
            MODULE.apply_report(req, report)
        self.assertEqual(ctx.exception.code, "E_SCHEMA")


if __name__ == "__main__":
    unittest.main()
