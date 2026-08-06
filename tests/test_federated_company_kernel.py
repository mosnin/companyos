from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "skills"
    / "company-os"
    / "compile-federated-company-kernel"
    / "scripts"
    / "compile_federated_kernel.py"
)
MECHANISMS = SCRIPT.parents[1] / "references" / "federated-mechanism-contracts.json"
EXAMPLE = SCRIPT.parents[1] / "references" / "federated-kernel-request.example.json"
SOURCES = (
    ROOT
    / "skills"
    / "company-os"
    / "source-intelligence"
    / "references"
    / "source-intelligence-registry.json"
)
SPEC = importlib.util.spec_from_file_location("compile_federated_kernel", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def request_fixture() -> dict:
    return {
        "$schema": "company-os.federated-kernel-request.v1",
        "company_id": "atlas-holdings",
        "objective": {
            "id": "objective-autonomous-scale",
            "statement": "Operate a nine-figure autonomous company with one thousand governed agents",
            "metric": "Accepted business outcomes per operating day",
            "target": "Scale to 1000 admitted agents without losing quality or authority",
            "horizon": "2027-Q4",
        },
        "target_capacity_agents": 1000,
        "initial_active_concurrency_limit": 50,
        "authority": {
            "human_approval_actions": [
                "external-communication",
                "financial-commitment",
                "legal-commitment",
                "production-write",
            ],
            "executive_exception_actions": [
                "budget-overrun",
                "cross-cell-conflict",
                "recovery-failure",
                "scope-change",
            ],
            "delegated_risk_tiers": ["low", "medium", "high"],
        },
        "persistence": {
            "adapter": "postgresql",
            "dsn_env": "COMPANY_OS_DATABASE_URL",
            "schema": "company-os",
        },
        "quality_targets": {
            "first_pass_acceptance_min": 0.85,
            "rework_max": 0.20,
            "write_collisions_max": 0,
            "recovery_rate_min": 1.0,
            "luna_labor_share_min": 0.70,
            "sol_overhead_share_max": 0.20,
            "scale_efficiency_min": 0.70,
            "utilization_ceiling": 0.75,
        },
        "business_units": [
            {
                "id": "product-engineering",
                "mission": "Create and operate differentiated products",
                "budget_share_percent": 40,
                "programs": [
                    {
                        "id": "platform-release",
                        "objective": "Release an agent-native operating platform",
                        "risk_tier": "high",
                        "budget_share_percent": 100,
                        "workstreams": [
                            {
                                "id": "platform-architecture",
                                "deliverable": "Accepted platform architecture and implementation",
                                "complexity": 5,
                                "uncertainty": 4,
                                "repetitiveness": 1,
                                "estimated_tasks": 60,
                                "parallel_width": 12,
                                "artifact_kinds": ["code", "technical-architecture"],
                                "required_capabilities": ["engineering", "system-design"],
                            },
                            {
                                "id": "product-experience",
                                "deliverable": "Validated product experience",
                                "complexity": 4,
                                "uncertainty": 4,
                                "repetitiveness": 2,
                                "estimated_tasks": 30,
                                "parallel_width": 8,
                                "artifact_kinds": ["prototype", "user-interface"],
                                "required_capabilities": ["product-design", "ui-design-quality"],
                            },
                        ],
                    }
                ],
            },
            {
                "id": "commercial-growth",
                "mission": "Turn customer value into repeatable revenue",
                "budget_share_percent": 30,
                "programs": [
                    {
                        "id": "market-expansion",
                        "objective": "Create and validate a new enterprise growth motion",
                        "risk_tier": "medium",
                        "budget_share_percent": 100,
                        "workstreams": [
                            {
                                "id": "market-intelligence",
                                "deliverable": "Evidence-backed market and account strategy",
                                "complexity": 3,
                                "uncertainty": 4,
                                "repetitiveness": 3,
                                "estimated_tasks": 40,
                                "parallel_width": 10,
                                "artifact_kinds": ["research-report"],
                                "required_capabilities": ["market-research"],
                            },
                            {
                                "id": "enterprise-offer",
                                "deliverable": "Accepted enterprise offer and sales system",
                                "complexity": 3,
                                "uncertainty": 3,
                                "repetitiveness": 3,
                                "estimated_tasks": 16,
                                "parallel_width": 4,
                                "artifact_kinds": ["offer", "proposal"],
                                "required_capabilities": ["offer-design", "sales"],
                            },
                        ],
                    }
                ],
            },
            {
                "id": "operations-finance",
                "mission": "Maintain operating reliability and financial truth",
                "budget_share_percent": 30,
                "programs": [
                    {
                        "id": "operating-control",
                        "objective": "Operate reliable finance and service controls",
                        "risk_tier": "consequential",
                        "budget_share_percent": 100,
                        "workstreams": [
                            {
                                "id": "financial-control",
                                "deliverable": "Verified operating model and financial controls",
                                "complexity": 4,
                                "uncertainty": 2,
                                "repetitiveness": 4,
                                "estimated_tasks": 24,
                                "parallel_width": 6,
                                "artifact_kinds": ["operating-procedure", "spreadsheet"],
                                "required_capabilities": ["financial-analysis", "operations"],
                            }
                        ],
                    }
                ],
            },
        ],
    }


class FederatedCompanyKernelTests(unittest.TestCase):
    def compile(self, request: dict | None = None) -> dict:
        normalized = MODULE.validate_request(request or request_fixture())
        mechanisms, _sources, mechanism_digest, source_digest = MODULE.validate_mechanisms(
            MECHANISMS, SOURCES
        )
        return MODULE.compile_kernel(normalized, mechanisms, mechanism_digest, source_digest)

    def test_compiles_deterministically_and_preserves_objective(self):
        request = request_fixture()
        first = self.compile(request)
        second = self.compile(copy.deepcopy(request))
        self.assertEqual(first, second)
        self.assertEqual(first["objective"], request["objective"])
        self.assertEqual(first["kernel_digest"], MODULE.digest_value({k: v for k, v in first.items() if k != "kernel_digest"}))

    def test_topology_is_dynamic_and_respects_manager_span(self):
        kernel = self.compile()
        managers = kernel["organization"]["manager_cells"]
        self.assertGreater(len(managers), len(request_fixture()["business_units"]))
        self.assertTrue(all(item["declared_worker_slots"] <= item["direct_report_limit"] for item in managers))
        architecture = [item for item in managers if item["workstream_id"] == "platform-architecture"]
        self.assertEqual(len(architecture), 3)
        self.assertEqual(sum(item["declared_worker_slots"] for item in architecture), 12)

    def test_explicit_delivery_contract_reaches_every_manager_partition(self):
        request = request_fixture()
        stream = request["business_units"][1]["programs"][0]["workstreams"][0]
        stream["mandatory_requirements"] = ["Retain the requested enterprise scope."]
        stream["acceptance_checks"] = ["Independent review confirms the enterprise scope."]
        kernel = self.compile(request)
        managers = [
            item
            for item in kernel["organization"]["manager_cells"]
            if item["workstream_id"] == "market-intelligence"
        ]
        self.assertTrue(managers)
        self.assertTrue(
            all(item["delivery_contract_status"] == "complete" for item in managers)
        )
        self.assertTrue(
            all(item["mandatory_requirements"] == stream["mandatory_requirements"] for item in managers)
        )

    def test_partial_delivery_contract_fails_closed(self):
        request = request_fixture()
        stream = request["business_units"][1]["programs"][0]["workstreams"][0]
        stream["mandatory_requirements"] = ["Retain the requested enterprise scope."]
        with self.assertRaisesRegex(MODULE.KernelError, "must provide both"):
            self.compile(request)

    def test_role_contracts_do_not_reintroduce_fixed_team_ratios(self):
        paths = [
            ROOT / "skills" / "company-os" / "manage-company-program" / "SKILL.md",
            ROOT / "skills" / "autonomy-suite" / "delegation" / "supervised-subagent-tree" / "SKILL.md",
            ROOT
            / "skills"
            / "autonomy-suite"
            / "orchestration"
            / "luna-execution-fabric"
            / "references"
            / "codex-native-task-fabric.md",
        ]
        combined = "\n".join(path.read_text() for path in paths)
        self.assertNotIn("three Luna workers per manager", combined)
        self.assertNotIn("three workers per manager and six globally", combined)
        self.assertIn("direct_report_limit", combined)
        self.assertIn("Capacity is not", combined)

    def test_example_request_is_canonical_and_compiles(self):
        raw = EXAMPLE.read_bytes()
        request = json.loads(raw)
        self.assertEqual(raw, MODULE.canonical_bytes(request))
        kernel = self.compile(request)
        self.assertEqual(kernel["admission"]["target_capacity_agents"], 1000)
        self.assertGreater(kernel["organization"]["manager_partition_count"], 1)

    def test_target_capacity_does_not_force_idle_agents_active(self):
        kernel = self.compile()
        self.assertEqual(kernel["admission"]["target_capacity_agents"], 1000)
        self.assertEqual(kernel["admission"]["initial_active_concurrency_limit"], 50)
        self.assertLess(kernel["admission"]["initial_active_luna_limit"], 50)
        self.assertTrue(kernel["admission"]["scale_only_from_observed_accepted_throughput"])

    def test_four_domains_are_not_eight_sequential_governance_layers(self):
        kernel = self.compile()
        self.assertEqual(len(kernel["operating_domains"]), 4)
        self.assertTrue(all(not item["governing_layer"] for item in kernel["shared_services"]))
        stages = [item["stage"] for item in kernel["execution_hot_path"]]
        self.assertNotIn("source-intelligence", stages)
        self.assertNotIn("capability-catalog", stages)
        self.assertNotIn("offline-learning", stages)

    def test_repository_mechanisms_bind_exact_pins_and_rejections(self):
        kernel = self.compile()
        bindings = {item["contract_id"]: item for item in kernel["mechanism_bindings"]}
        self.assertEqual(
            set(bindings),
            {
                "artifact-specific-transfer-evaluation",
                "bounded-cell-reservation-and-adoption",
                "bounded-debrief-loop",
                "contract-transition-diagnostics",
                "desired-observed-host-reconciliation",
                "durable-event-cursor-and-replay",
                "governed-experience-and-transfer",
                "protected-candidate-search",
                "read-only-cited-context-broker",
                "role-intent-and-observed-readback",
                "trace-diagnosis-adapter",
            },
        )
        self.assertEqual(
            {
                source["source_id"]
                for binding in bindings.values()
                for source in binding["source_bindings"]
            },
            {
                "agentscope-ai-agentteams",
                "agno-agi-scout",
                "aitransformationdirector-use-luna-subagents",
                "context-labs-halo",
                "durable-streams-durable-streams",
                "forward-future-loopy",
                "gepa-ai-gepa",
                "metauto-ai-hgm",
                "miyago9267-pilotfish-codex",
                "neo4j-agent-memory",
                "plasma-ai-fractal",
                "ray-r-ren-agent-apprenticeship",
                "sentient-agi-evoskill",
                "shengranhu-adas",
                "snap-stanford-mlagentbench",
                "tencent-youtu-graphrag",
                "thudm-agentbench",
                "topoteretes-cognee",
                "valkor-ai-loom",
            },
        )
        self.assertIn("desired-observed-host-reconciliation", bindings)
        self.assertIn("bounded-cell-reservation-and-adoption", bindings)
        self.assertIn("durable-event-cursor-and-replay", bindings)
        self.assertIn("worktrees as security isolation", bindings["bounded-cell-reservation-and-adoption"]["rejected_mechanisms"])
        agentteams = bindings["desired-observed-host-reconciliation"]["source_bindings"][0]
        self.assertEqual(agentteams["pin"], "124f06d13fd6bb4c2054128dcff26bcd9f9c8dbf")

    def test_context_memory_and_graphs_remain_read_only_shared_service(self):
        kernel = self.compile()
        broker = next(item for item in kernel["shared_services"] if item["service_id"] == "context-broker")
        self.assertEqual(broker["mode"], "read_only_cited_evidence_projection")
        self.assertIn("read-only-cited-context-broker", broker["mechanism_contracts"])
        self.assertNotIn("read-only-cited-context-broker", kernel["offline_learning"]["mechanism_contracts"])

    def test_improvement_mechanisms_cannot_dispatch_accept_or_promote(self):
        learning = self.compile()["offline_learning"]
        self.assertFalse(learning["may_dispatch"])
        self.assertFalse(learning["may_accept"])
        self.assertFalse(learning["may_promote"])
        self.assertIn("protected-candidate-search", learning["mechanism_contracts"])

    def test_compilation_never_authorizes_runtime_or_scheduler(self):
        activation = self.compile()["activation"]
        self.assertEqual(activation["state"], "planned")
        self.assertFalse(activation["execution_authorized"])
        self.assertFalse(activation["runtime_authorized"])
        self.assertFalse(activation["scheduler_authorized"])
        self.assertIn("protected_launcher_unproven", activation["blockers"])

    def test_scale_ladder_reaches_one_thousand_with_gates(self):
        ladder = self.compile()["scale_ladder"]
        self.assertEqual([item["capacity_agents"] for item in ladder], [10, 50, 100, 250, 500, 1000])
        thousand = ladder[-1]
        self.assertEqual(thousand["first_pass_acceptance_min"], 0.85)
        self.assertEqual(thousand["write_collisions_max"], 0)
        self.assertEqual(thousand["recovery_rate_min"], 1.0)
        self.assertEqual(thousand["required_sustained_windows"], 3)

    def test_invalid_business_unit_and_program_budget_shares_fail(self):
        request = request_fixture()
        request["business_units"][0]["budget_share_percent"] = 41
        with self.assertRaisesRegex(MODULE.KernelError, "business unit budget shares"):
            MODULE.validate_request(request)
        request = request_fixture()
        second = copy.deepcopy(request["business_units"][0]["programs"][0])
        second["id"] = "second-program"
        for stream in second["workstreams"]:
            stream["id"] = f"second-{stream['id']}"
        request["business_units"][0]["programs"].append(second)
        with self.assertRaisesRegex(MODULE.KernelError, "program budget shares"):
            MODULE.validate_request(request)

    def test_protected_actions_and_consequential_delegation_fail_closed(self):
        request = request_fixture()
        request["authority"]["human_approval_actions"].remove("production-write")
        with self.assertRaisesRegex(MODULE.KernelError, "protected actions"):
            MODULE.validate_request(request)
        request = request_fixture()
        request["authority"]["delegated_risk_tiers"].append("consequential")
        with self.assertRaisesRegex(MODULE.KernelError, "consequential"):
            MODULE.validate_request(request)
        kernel = self.compile()
        consequential = [
            item
            for item in kernel["organization"]["manager_cells"]
            if item["risk_tier"] == "consequential"
        ]
        self.assertTrue(consequential)
        self.assertTrue(
            all(item["decision_mode"] == "analysis_only_human_decision" for item in consequential)
        )

    def test_source_registry_byte_drift_and_pin_substitution_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_copy = root / "sources.json"
            source_copy.write_bytes(SOURCES.read_bytes() + b"\n")
            with self.assertRaisesRegex(MODULE.KernelError, "exact source intelligence"):
                MODULE.validate_mechanisms(MECHANISMS, source_copy)
            mechanism_copy = root / "mechanisms.json"
            mechanisms = json.loads(MECHANISMS.read_text())
            mechanisms["contracts"][0]["source_bindings"][0]["pin"] = "0" * 40
            mechanism_copy.write_text(json.dumps(mechanisms))
            with self.assertRaisesRegex(MODULE.KernelError, "exact source pin"):
                MODULE.validate_mechanisms(mechanism_copy, SOURCES)

    def test_verify_rejects_noncanonical_and_semantically_tampered_kernel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "request.json"
            kernel_path = root / "kernel.json"
            request_path.write_text(json.dumps(request_fixture()))
            kernel = self.compile()
            kernel_path.write_bytes(MODULE.canonical_bytes(kernel))
            receipt = MODULE.verify_kernel(request_path, kernel_path, MECHANISMS, SOURCES)
            self.assertTrue(receipt["ok"])
            kernel["activation"]["execution_authorized"] = True
            kernel_path.write_bytes(MODULE.canonical_bytes(kernel))
            with self.assertRaisesRegex(MODULE.KernelError, "does not reproduce"):
                MODULE.verify_kernel(request_path, kernel_path, MECHANISMS, SOURCES)
            kernel_path.write_text(json.dumps(self.compile(), indent=2))
            with self.assertRaisesRegex(MODULE.KernelError, "not canonical"):
                MODULE.verify_kernel(request_path, kernel_path, MECHANISMS, SOURCES)

    def test_cli_compiles_and_verifies_without_external_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "request.json"
            kernel_path = root / "kernel.json"
            request_path.write_text(json.dumps(request_fixture()))
            compiled = subprocess.run(
                [sys.executable, str(SCRIPT), "compile", "--request", str(request_path), "--output", str(kernel_path)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            verified = subprocess.run(
                [sys.executable, str(SCRIPT), "verify", "--request", str(request_path), "--kernel", str(kernel_path)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
            self.assertFalse(json.loads(verified.stdout)["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
