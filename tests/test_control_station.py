#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills/company-os/intelligence/company-scorecard/scripts/render_control_station.py"
SPEC = importlib.util.spec_from_file_location("company_os_control_station", MODULE_PATH)
assert SPEC and SPEC.loader
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def snapshot() -> dict:
    return {
        "schema": "company-os.control-station-snapshot.v1",
        "workspace_id": "operator-company-os",
        "as_of": "2026-08-06T00:00:00Z",
        "summary": {
            "run_count": 1,
            "accepted_runs": 0,
            "blocked_runs": 1,
            "rework_runs": 0,
            "failed_runs": 0,
            "luna_proven_runs": 0,
            "efficiency_proven_runs": 0,
            "scale_eligible_runs": 0,
            "delivery_acceptance_rate": 0,
            "artifact_acceptance_rate": 0.5,
            "write_collisions": 0,
        },
        "runs": [{
            "run_id": "real-run-1",
            "project_id": "client-project",
            "program_id": "working-proof",
            "comparison_class": "client-product-proof",
            "status": "blocked",
            "recorded_at": "2026-08-06T00:00:00Z",
            "delivery_accepted": False,
            "hierarchy_materialized": True,
            "luna_execution_proven": False,
            "efficiency_proven": False,
            "scaling_evidence_eligible": False,
            "accepted_artifact_rate": 0.5,
            "rework_cycles": 1,
            "write_collisions": 0,
            "luna_token_share": None,
            "sol_token_reduction": None,
            "lead_time_seconds": None,
            "mandatory_requirements_satisfied": 3,
            "mandatory_requirements_total": 5,
            "required_capabilities_applied": 3,
            "required_capabilities_total": 5,
        }],
        "blockers": [{
            "run_id": "real-run-1",
            "kind": "requirement",
            "id": "production-source-integration",
            "status": "unsatisfied",
            "summary": "Locate <script>alert(1)</script> before integration.",
        }],
    }


class ControlStationTests(unittest.TestCase):
    def test_blocked_snapshot_renders_evidence_without_promoting_scale(self) -> None:
        output = renderer.render_html(snapshot())
        self.assertIn("Hold scale. Close the evidence gaps.", output)
        self.assertIn("50%", output)
        self.assertIn("Unproven", output)
        self.assertIn("production-source-integration", output)
        self.assertNotIn("<script>alert", output)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", output)
        self.assertIn("prefers-reduced-motion", output)
        self.assertIn('href="#runs"', output)

    def test_missing_metrics_render_as_unavailable(self) -> None:
        value = snapshot()
        value["summary"]["artifact_acceptance_rate"] = None
        output = renderer.render_html(value)
        self.assertIn("Unavailable", output)
        self.assertNotIn("nan", output.lower())

    def test_cli_creates_one_read_only_html_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "snapshot.json"
            target = root / "control-station.html"
            source.write_text(json.dumps(snapshot()), encoding="utf-8")
            loaded = renderer.load_snapshot(source)
            target.write_text(renderer.render_html(loaded), encoding="utf-8")
            self.assertTrue(target.is_file())
            self.assertIn("Company OS Control Station", target.read_text(encoding="utf-8"))
            self.assertEqual({"snapshot.json", "control-station.html"}, {path.name for path in root.iterdir()})

    def test_sql_surface_is_bounded_and_read_only(self) -> None:
        sql = (ROOT / "skills/company-os/intelligence/company-scorecard/sql/004_control_station_snapshot.sql").read_text(encoding="utf-8")
        self.assertIn("STABLE", sql)
        self.assertIn("SECURITY INVOKER", sql)
        self.assertIn("p_run_limit", sql)
        self.assertIn("LEAST(COALESCE(p_run_limit, 50), 200)", sql)
        self.assertNotIn("SECURITY DEFINER", sql)
        self.assertNotIn("CREATE TABLE", sql)
        self.assertNotIn("UPDATE ", sql)
        self.assertNotIn("DELETE ", sql)


if __name__ == "__main__":
    unittest.main()
