from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "skills/company-os/intelligence/company-scorecard/scripts/validate_execution_efficiency.py"
)
SPEC = importlib.util.spec_from_file_location("validate_execution_efficiency", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
sys.modules["validate_execution_efficiency"] = MODULE
INGEST_MODULE_PATH = (
    ROOT
    / "skills/company-os/intelligence/company-scorecard/scripts/render_execution_efficiency_ingest.py"
)
INGEST_SPEC = importlib.util.spec_from_file_location(
    "render_execution_efficiency_ingest", INGEST_MODULE_PATH
)
assert INGEST_SPEC and INGEST_SPEC.loader
INGEST_MODULE = importlib.util.module_from_spec(INGEST_SPEC)
INGEST_SPEC.loader.exec_module(INGEST_MODULE)


def manager(manager_id: str, lane_ids: list[str]) -> dict:
    return {
        "manager_task_id": manager_id,
        "lane_ids": lane_ids,
        "requested_model": "gpt-5.6-sol",
        "requested_effort": "xhigh",
        "observed_model": None,
        "observed_effort": None,
    }


def meta_ads_receipt() -> dict:
    lanes = [
        {"lane_id": "lane-a", "outcome": "Meta API feasibility"},
        {"lane_id": "lane-b", "outcome": "Technical architecture"},
        {"lane_id": "lane-c", "outcome": "Product requirements"},
        {"lane_id": "lane-d", "outcome": "Commercial proposal"},
    ]
    plan = [
        {
            "artifact_id": "technical-architecture",
            "kind": "notion_page",
            "expected_title": "Meta Ads Multi-Account Dashboard — Technical Architecture",
            "owner_lane_id": "lane-b",
            "requirement_ids": [
                "req-account-portfolio",
                "req-agent-runtime",
                "req-recurring-runners",
                "req-technical-report",
            ],
            "required_capability_ids": [
                "notion:notion-research-documentation",
                "openai-developers:agents-sdk",
                "technology-radar",
            ],
        },
        {
            "artifact_id": "product-requirements",
            "kind": "notion_page",
            "expected_title": "Meta Ads Multi-Account Dashboard — Product Requirements Document",
            "owner_lane_id": "lane-c",
            "requirement_ids": [
                "req-account-portfolio",
                "req-agent-runtime",
                "req-recurring-runners",
                "req-complete-prd",
            ],
            "required_capability_ids": [
                "notion:notion-research-documentation",
                "project-program-management",
            ],
        },
        {
            "artifact_id": "client-proposal",
            "kind": "notion_page",
            "expected_title": "Meta Ads Multi-Account Dashboard — Client Proposal and Quote",
            "owner_lane_id": "lane-d",
            "requirement_ids": [
                "req-agent-runtime",
                "req-client-proposal",
            ],
            "required_capability_ids": [
                "alexsmedile-hormozi-skills-hormozi-offer",
                "commercial-customer-system",
                "notion:notion-research-documentation",
            ],
        },
    ]
    requirements = [
        {
            "requirement_id": "req-account-portfolio",
            "statement": "Design for one agency operating reporting across 104 client ad accounts.",
            "source": "user-meta-ads-intake",
            "mandatory": True,
        },
        {
            "requirement_id": "req-agent-runtime",
            "statement": "Use an OpenAI Agents SDK based agent as a core system capability.",
            "source": "user-meta-ads-intake",
            "mandatory": True,
        },
        {
            "requirement_id": "req-recurring-runners",
            "statement": "Include workers, runners, and recurring hourly analysis and reporting.",
            "source": "user-meta-ads-intake",
            "mandatory": True,
        },
        {
            "requirement_id": "req-technical-report",
            "statement": "Deliver a complete technical architecture for the requested system.",
            "source": "user-meta-ads-intake",
            "mandatory": True,
        },
        {
            "requirement_id": "req-complete-prd",
            "statement": "Deliver a complete and implementation-ready product requirements document.",
            "source": "user-meta-ads-intake",
            "mandatory": True,
        },
        {
            "requirement_id": "req-client-proposal",
            "statement": "Deliver a client-ready proposal and quote positioned around the requested agent system.",
            "source": "user-meta-ads-intake",
            "mandatory": True,
        },
    ]
    result_statuses = {
        "req-account-portfolio": "satisfied",
        "req-agent-runtime": "unsatisfied",
        "req-recurring-runners": "unsatisfied",
        "req-technical-report": "unsatisfied",
        "req-complete-prd": "unsatisfied",
        "req-client-proposal": "unsatisfied",
    }
    return {
        "schema": "company-os.execution-efficiency-receipt.v1",
        "program_id": "meta-ads-dashboard",
        "comparison_class": "multi-document-research",
        "status": "rework",
        "timing": {
            "program_start": None,
            "first_manager_dispatch": None,
            "first_worker_dispatch": None,
            "first_usable_result": None,
            "first_artifact_materialization": None,
            "final_acceptance": "2026-08-04T21:45:14Z",
            "unavailable": [
                "program_start",
                "first_manager_dispatch",
                "first_usable_result",
                "first_artifact_materialization",
            ],
            "not_applicable": ["first_worker_dispatch"],
        },
        "topology": {
            "requested_lanes": lanes,
            "manager_assignments": [
                manager("meta-api-manager", ["lane-a"]),
                manager("architecture-manager", ["lane-b"]),
                manager("product-manager", ["lane-c", "lane-d"]),
            ],
            "workers": [],
            "max_observed_concurrency": 4,
            "concurrency_limit": 4,
            "variances": [
                {
                    "type": "host_cap_consolidation",
                    "actor_task_id": "product-manager",
                    "actor_role": "manager",
                    "lane_ids": ["lane-c", "lane-d"],
                    "reason": "Host allowed three subordinate slots for four lanes.",
                },
                {
                    "type": "master_direct_labor",
                    "actor_task_id": "meta-ads-master",
                    "actor_role": "master",
                    "lane_ids": ["lane-b", "lane-c", "lane-d"],
                    "reason": "Master drafted pages after research managers completed.",
                },
            ],
        },
        "usage": {
            "total_tokens": None,
            "luna_tokens": None,
            "sol_tokens": None,
            "cost_usd": None,
            "single_thread_baseline_sol_tokens": None,
            "single_thread_baseline_lead_time_seconds": None,
            "unavailable": [
                "total_tokens",
                "luna_tokens",
                "sol_tokens",
                "cost_usd",
                "single_thread_baseline_sol_tokens",
                "single_thread_baseline_lead_time_seconds",
            ],
        },
        "quality": {
            "required_artifacts": 3,
            "accepted_artifacts": 0,
            "first_pass_accepted": False,
            "rework_cycles": 1,
            "write_collisions": 0,
            "duplicate_artifacts": 0,
            "independent_reviewed": True,
        },
        "requirements": requirements,
        "requirement_results": [
            {
                "requirement_id": item["requirement_id"],
                "status": result_statuses[item["requirement_id"]],
                "evidence": [
                    "Direct user acceptance review of the three delivered Notion pages."
                ],
            }
            for item in requirements
        ],
        "artifact_plan": plan,
        "artifacts": [
            {
                "artifact_id": item["artifact_id"],
                "kind": item["kind"],
                "title": item["expected_title"],
                "external_id": f"notion-{index}",
                "owner_lane_id": item["owner_lane_id"],
                "satisfied_requirement_ids": (
                    ["req-account-portfolio"]
                    if "req-account-portfolio" in item["requirement_ids"]
                    else []
                ),
                "applied_capability_ids": [],
                "refetched": True,
                "accepted": False,
            }
            for index, item in enumerate(plan, start=1)
        ],
        "decision": {
            "status": "rework",
            "reviewer": "user",
            "authority": "user",
            "required_authority": "user",
            "evidence": [
                "User rejected the PRD as incomplete, the architecture as scope-inverting, and the proposal as mispositioned."
            ],
        },
    }


def scalable_receipt(index: int) -> dict:
    receipt = meta_ads_receipt()
    receipt["program_id"] = f"scaled-program-{index}"
    receipt["comparison_class"] = "bounded-code-delivery"
    receipt["timing"] = {
        "program_start": f"2026-08-0{index}T10:00:00Z",
        "first_manager_dispatch": f"2026-08-0{index}T10:00:20Z",
        "first_worker_dispatch": f"2026-08-0{index}T10:00:40Z",
        "first_usable_result": f"2026-08-0{index}T10:04:00Z",
        "first_artifact_materialization": f"2026-08-0{index}T10:05:00Z",
        "final_acceptance": f"2026-08-0{index}T10:08:00Z",
        "unavailable": [],
        "not_applicable": [],
    }
    receipt["topology"]["manager_assignments"] = [
        {
            "manager_task_id": f"manager-{index}",
            "lane_ids": ["lane-a", "lane-b", "lane-c", "lane-d"],
            "requested_model": "gpt-5.6-sol",
            "requested_effort": "xhigh",
            "observed_model": "gpt-5.6-sol",
            "observed_effort": "xhigh",
        }
    ]
    receipt["topology"]["workers"] = [
        {
            "worker_task_id": f"worker-{index}",
            "manager_task_id": f"manager-{index}",
            "requested_model": "gpt-5.6-luna",
            "requested_effort": "max",
            "observed_model": "gpt-5.6-luna",
            "observed_effort": "max",
        }
    ]
    receipt["topology"]["max_observed_concurrency"] = 3
    receipt["topology"]["concurrency_limit"] = 3
    receipt["topology"]["variances"] = [
        {
            "type": "host_cap_consolidation",
            "actor_task_id": f"manager-{index}",
            "actor_role": "manager",
            "lane_ids": ["lane-a", "lane-b", "lane-c", "lane-d"],
            "reason": "One manager owns this bounded comparison-class outcome.",
        }
    ]
    receipt["usage"] = {
        "total_tokens": 1000,
        "luna_tokens": 750,
        "sol_tokens": 200,
        "cost_usd": 1.0,
        "single_thread_baseline_sol_tokens": 400,
        "single_thread_baseline_lead_time_seconds": 600,
        "unavailable": [],
    }
    receipt["quality"]["first_pass_accepted"] = True
    receipt["quality"]["rework_cycles"] = 0
    receipt["quality"]["accepted_artifacts"] = 3
    receipt["status"] = "accepted"
    receipt["requirement_results"] = [
        {
            "requirement_id": item["requirement_id"],
            "status": "satisfied",
            "evidence": ["Independent acceptance evidence."],
        }
        for item in receipt["requirements"]
    ]
    for artifact, planned in zip(receipt["artifacts"], receipt["artifact_plan"]):
        artifact["satisfied_requirement_ids"] = list(planned["requirement_ids"])
        artifact["applied_capability_ids"] = list(
            planned["required_capability_ids"]
        )
        artifact["accepted"] = True
    receipt["decision"] = {
        "status": "accepted",
        "reviewer": "company-os-master",
        "authority": "master",
        "required_authority": "master",
        "evidence": ["Independent master acceptance evidence."],
    }
    return receipt


class ExecutionEfficiencyReceiptTests(unittest.TestCase):
    def test_real_meta_run_is_valid_rework_not_accepted_throughput(self) -> None:
        result = MODULE.validate_receipt(meta_ads_receipt(), "meta-real-run")
        self.assertTrue(result["ok"], result["errors"])
        self.assertFalse(result["gates"]["delivery_accepted"])
        self.assertFalse(result["gates"]["mandatory_requirements_satisfied"])
        self.assertFalse(result["gates"]["required_capabilities_applied"])
        self.assertTrue(result["gates"]["acceptance_authority_satisfied"])
        self.assertTrue(result["gates"]["hierarchy_materialized"])
        self.assertFalse(result["gates"]["luna_execution_proven"])
        self.assertFalse(result["gates"]["efficiency_proven"])
        self.assertFalse(result["gates"]["scaling_evidence_eligible"])
        self.assertEqual(3, result["metrics"]["unique_managers"])
        self.assertEqual(0, result["metrics"]["workers"])
        self.assertEqual(1, result["metrics"]["mandatory_requirements_satisfied"])
        self.assertEqual(6, result["metrics"]["mandatory_requirements_total"])
        self.assertEqual(0, result["metrics"]["required_capabilities_applied"])
        self.assertIn("no worker tasks were dispatched", " ".join(result["warnings"]))

    def test_crossed_artifact_owner_is_rejected(self) -> None:
        receipt = meta_ads_receipt()
        receipt["artifacts"][0]["owner_lane_id"] = "lane-c"
        result = MODULE.validate_receipt(receipt)
        self.assertFalse(result["ok"])
        self.assertIn(
            "artifact 'technical-architecture' owner_lane_id does not match its plan",
            result["errors"],
        )

    def test_manager_lane_consolidation_requires_exact_variance(self) -> None:
        receipt = meta_ads_receipt()
        receipt["topology"]["variances"] = receipt["topology"]["variances"][1:]
        result = MODULE.validate_receipt(receipt)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("owns multiple lanes without an exact disclosed variance" in error for error in result["errors"])
        )

    def test_requested_luna_is_not_observed_luna(self) -> None:
        receipt = scalable_receipt(1)
        receipt["topology"]["workers"][0]["observed_model"] = None
        receipt["topology"]["workers"][0]["observed_effort"] = None
        result = MODULE.validate_receipt(receipt)
        self.assertTrue(result["ok"], result["errors"])
        self.assertFalse(result["gates"]["luna_execution_proven"])
        self.assertFalse(result["gates"]["scaling_evidence_eligible"])

    def test_null_telemetry_must_be_explicitly_unavailable(self) -> None:
        receipt = meta_ads_receipt()
        receipt["usage"]["unavailable"].remove("cost_usd")
        result = MODULE.validate_receipt(receipt)
        self.assertFalse(result["ok"])
        self.assertIn(
            "receipt.usage.cost_usd is null but is not declared unavailable",
            result["errors"],
        )

    def test_accepted_receipt_cannot_ignore_mandatory_requirement(self) -> None:
        receipt = scalable_receipt(1)
        receipt["requirement_results"][1]["status"] = "unsatisfied"
        result = MODULE.validate_receipt(receipt)
        self.assertFalse(result["ok"])
        self.assertIn(
            "accepted receipt has unsatisfied or unknown mandatory requirements",
            result["errors"],
        )

    def test_accepted_artifact_cannot_omit_required_capability(self) -> None:
        receipt = scalable_receipt(1)
        receipt["artifacts"][0]["applied_capability_ids"].remove(
            "openai-developers:agents-sdk"
        )
        result = MODULE.validate_receipt(receipt)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any(
                "misses required capabilities" in error
                for error in result["errors"]
            )
        )

    def test_manager_cannot_accept_user_authority_outcome(self) -> None:
        receipt = scalable_receipt(1)
        receipt["decision"]["authority"] = "manager"
        receipt["decision"]["required_authority"] = "user"
        result = MODULE.validate_receipt(receipt)
        self.assertFalse(result["ok"])
        self.assertIn(
            "accepted receipt decision is below the required authority",
            result["errors"],
        )

    def test_three_comparable_measured_cycles_pass_scale_gate(self) -> None:
        results = [
            MODULE.validate_receipt(scalable_receipt(index), f"cycle-{index}")
            for index in (1, 2, 3)
        ]
        self.assertTrue(all(result["ok"] for result in results))
        group = MODULE.aggregate_results(results)["bounded-code-delivery"]
        self.assertTrue(group["scale_gate_passed"])
        self.assertEqual(1.0, group["first_pass_rate"])
        self.assertEqual(0.0, group["rework_rate"])
        self.assertAlmostEqual(0.75, group["luna_token_share"])
        self.assertAlmostEqual(0.50, group["sol_token_reduction"])

    def test_one_good_cycle_cannot_prove_scale(self) -> None:
        result = MODULE.validate_receipt(scalable_receipt(1))
        group = MODULE.aggregate_results([result])["bounded-code-delivery"]
        self.assertFalse(group["scale_gate_passed"])

    def test_cli_outputs_canonical_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps(meta_ads_receipt()), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(MODULE_PATH), str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(
            completed.stdout.strip(),
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        )

    def test_ingest_sql_is_deterministic_and_does_not_expose_raw_receipt(self) -> None:
        kwargs = {
            "source": "meta-real-run",
            "workspace_id": "preston-company-os",
            "workspace_name": "Preston Company OS",
            "project_id": "meta-ads-gentech",
            "project_name": "Meta Ads GenTech Campaign Manager",
            "run_id": "meta-ads-2026-08-04",
            "framework_version_id": "company-os-e213b283",
            "framework_source_commit": "e213b283ec587462fe0923c6e140f8107cba8003",
            "source_thread_id": "019fceb2-39ff-7471-a421-73e0b312c23c",
            "supersedes_receipt_sha256": None,
        }
        first = INGEST_MODULE.render_ingest_sql(meta_ads_receipt(), **kwargs)
        second = INGEST_MODULE.render_ingest_sql(meta_ads_receipt(), **kwargs)
        self.assertEqual(first, second)
        sql, receipt_sha256, validation = first
        self.assertEqual(64, len(receipt_sha256))
        self.assertIn(
            "company_os_observatory.ingest_execution_efficiency_receipt",
            sql,
        )
        self.assertNotIn(
            "Use an OpenAI Agents SDK based agent as a core system capability.",
            sql,
        )
        self.assertFalse(validation["gates"]["delivery_accepted"])

    def test_observatory_sql_is_portable_append_only_postgres(self) -> None:
        sql_root = (
            ROOT
            / "skills/company-os/intelligence/company-scorecard/sql"
        )
        schema_sql = (sql_root / "001_company_os_observatory.sql").read_text()
        ingest_sql = (
            sql_root / "002_ingest_execution_efficiency_receipt.sql"
        ).read_text()
        self.assertIn("CREATE SCHEMA IF NOT EXISTS company_os_observatory", schema_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS company_os_observatory.run_receipts", schema_sql)
        self.assertIn("reject_evidence_mutation", schema_sql)
        self.assertIn("comparison_trends", schema_sql)
        self.assertIn("ingest_execution_efficiency_receipt", ingest_sql)
        self.assertIn("must pass the source validator", ingest_sql)
        self.assertIn("receipt SHA-256 does not bind", ingest_sql)
        self.assertIn("validation result does not bind the receipt SHA-256", ingest_sql)
        self.assertGreaterEqual(ingest_sql.count("IS DISTINCT FROM"), 5)
        self.assertIn("different source commit", ingest_sql)
        self.assertIn("REVOKE EXECUTE ON FUNCTION", ingest_sql)
        self.assertIn("CREATE EXTENSION IF NOT EXISTS pgcrypto", schema_sql)
        self.assertNotIn("neon", (schema_sql + ingest_sql).lower())


if __name__ == "__main__":
    unittest.main()
