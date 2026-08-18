from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills/company-os/company-blueprint/scripts/compile_company_blueprint.py"
EXAMPLE = ROOT / "skills/company-os/company-blueprint/assets/company-blueprint.example.json"
SQL = ROOT / "skills/company-os/intelligence/company-scorecard/sql/003_company_blueprints.sql"

SPEC = importlib.util.spec_from_file_location("company_blueprint_compiler", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
compiler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compiler)


class CompanyBlueprintTests(unittest.TestCase):
    def load_example(self) -> dict:
        return json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def write_blueprint(self, root: Path, value: dict) -> Path:
        path = root / "blueprint.json"
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return path

    def test_software_company_compiles_deterministically_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_root = Path(first)
            second_root = Path(second)
            first_manifest = compiler.compile_blueprint(
                self.write_blueprint(first_root, self.load_example()), first_root / "compiled"
            )
            second_manifest = compiler.compile_blueprint(
                self.write_blueprint(second_root, self.load_example()), second_root / "compiled"
            )
            self.assertEqual(first_manifest, second_manifest)
            self.assertEqual(
                compiler.verify_compiled(first_root / "compiled"),
                {"ok": True, "company_id": "acme-software", "files": 9},
            )
            for item in first_manifest["files"]:
                self.assertEqual(
                    (first_root / "compiled" / item["path"]).read_bytes(),
                    (second_root / "compiled" / item["path"]).read_bytes(),
                )

            organization = json.loads((first_root / "compiled/organization.json").read_text())
            self.assertEqual(12, organization["department_count"])
            self.assertEqual("elastic_work_graph", organization["capacity_policy"]["topology_mode"])
            self.assertNotIn("max_managers", organization["capacity_policy"])
            routines = json.loads((first_root / "compiled/routine-plan.json").read_text())
            self.assertTrue(routines["routines"])
            self.assertTrue(all(item["activation_state"] == "planned" for item in routines["routines"]))
            capabilities = json.loads((first_root / "compiled/capabilities.json").read_text())
            self.assertTrue(all(item["status"] == "requires-host-preflight" for item in capabilities["skills"]))
            self.assertTrue(all(item["status"] == "requires-host-preflight" for item in capabilities["tools"]))
            self.assertTrue(all(item["steps"] and item["evidence"] for item in capabilities["playbooks"]))
            registry = json.loads((first_root / "compiled/agent-registry.json").read_text())
            self.assertEqual("templates-not-running-agents", registry["activation_policy"])
            self.assertEqual(27, len(registry["slots"]))
            self.assertTrue(all(item["status"] in {"template", "stored"} for item in registry["slots"]))
            self.assertTrue(all(item["role"] in {"manager", "worker"} for item in registry["slots"]))

    def test_materially_different_agency_selects_smaller_organization(self) -> None:
        blueprint = self.load_example()
        blueprint["company_id"] = "northstar-agency"
        blueprint["identity"]["legal_name"] = "Northstar Agency LLC"
        blueprint["identity"]["operating_name"] = "Northstar"
        blueprint["operating_model"] = {
            "archetypes": ["agency"],
            "department_overrides": [],
            "requested_capabilities": ["brand-system", "financial-control", "revenue-growth"],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            compiler.compile_blueprint(self.write_blueprint(root, blueprint), root / "compiled")
            organization = json.loads((root / "compiled/organization.json").read_text())
            department_ids = {item["id"] for item in organization["departments"]}
            self.assertEqual(8, organization["department_count"])
            self.assertIn("marketing", department_ids)
            self.assertIn("sales", department_ids)
            self.assertNotIn("commercial-growth", department_ids)
            self.assertNotIn("engineering-quality", department_ids)

    def test_unknown_capability_and_disabled_owner_fail_before_dispatch(self) -> None:
        for mutation, expected in (
            (
                lambda blueprint: blueprint["operating_model"]["requested_capabilities"].append("quantum-sales"),
                "E_REQUIRED_CAPABILITY_UNAVAILABLE: quantum-sales",
            ),
            (
                lambda blueprint: blueprint["operating_model"]["department_overrides"].append(
                    {"department_id": "finance", "enabled": False, "reason": "Operator declined finance"}
                ),
                "E_REQUIRED_CAPABILITY_UNAVAILABLE: financial-control",
            ),
        ):
            blueprint = self.load_example()
            mutation(blueprint)
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with self.assertRaisesRegex(compiler.BlueprintError, expected):
                    compiler.compile_blueprint(self.write_blueprint(root, blueprint), root / "compiled")

    def test_blocking_unknown_secret_and_embedded_database_url_fail_closed(self) -> None:
        cases = []
        blocking = self.load_example()
        blocking["unknowns"] = [
            {"id": "unknown-market", "question": "Which market first?", "blocking": True, "owner": "operator", "resolution": "Interview operator"}
        ]
        cases.append((blocking, "blocking unknowns"))
        secret = self.load_example()
        secret["identity"]["thesis"] = "api_key=sk-test-secret-value"
        cases.append((secret, "secret material"))
        dsn = self.load_example()
        dsn["storage"]["dsn_env"] = "postgresql://user:password@host/db"
        cases.append((dsn, "must name an environment variable"))
        for blueprint, expected in cases:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with self.assertRaisesRegex(compiler.BlueprintError, expected):
                    compiler.compile_blueprint(self.write_blueprint(root, blueprint), root / "compiled")

    def test_assets_integrations_knowledge_graph_and_portable_storage_are_bound(self) -> None:
        blueprint = self.load_example()
        blueprint["assets"] = [
            {"id": "brand-guide", "kind": "brand-guideline", "locator": "notion://brand-guide", "content_sha256": "a" * 64}
        ]
        blueprint["integrations"] = [
            {"id": "customer-crm", "kind": "mcp", "locator": "mcp://crm", "permission_mode": "proposal_only", "credential_reference": "CRM_CONNECTION"}
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            compiler.compile_blueprint(self.write_blueprint(root, blueprint), root / "compiled")
            assets = json.loads((root / "compiled/asset-registry.json").read_text())
            integrations = json.loads((root / "compiled/integration-registry.json").read_text())
            graph = json.loads((root / "compiled/knowledge-graph.json").read_text())
            storage = json.loads((root / "compiled/storage-plan.json").read_text())
            self.assertEqual("brand-guide", assets["assets"][0]["id"])
            self.assertEqual("CRM_CONNECTION", integrations["integrations"][0]["credential_reference"])
            self.assertIn("asset:brand-guide", {node["id"] for node in graph["nodes"]})
            self.assertEqual("COMPANY_OS_DATABASE_URL", storage["dsn_env"])
            self.assertEqual(
                {"neon", "supabase", "amazon-rds", "google-cloud-sql", "self-managed-postgresql"},
                set(storage["portability"]),
            )

    def test_compiled_artifact_drift_and_extra_files_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            compiler.compile_blueprint(self.write_blueprint(root, self.load_example()), root / "compiled")
            artifact = root / "compiled/organization.json"
            artifact.write_bytes(artifact.read_bytes() + b" ")
            with self.assertRaisesRegex(compiler.BlueprintError, "drifted"):
                compiler.verify_compiled(root / "compiled")

    def test_department_packs_store_reusable_manager_and_staff_slots(self) -> None:
        catalog = json.loads(
            (ROOT / "skills/company-os/company-blueprint/assets/department-packs.json").read_text(
                encoding="utf-8"
            )
        )
        departments = compiler.validate_department_catalog(catalog)
        self.assertEqual(12, len(departments))
        self.assertIn("marketing", departments)
        self.assertIn("sales", departments)
        self.assertIn("human-resources", departments)
        self.assertNotIn("commercial-growth", departments)
        for department in departments.values():
            roles = {slot["role"] for slot in department["agent_slots"]}
            self.assertIn("manager", roles)
            self.assertTrue(any(slot["management_tier"] in {"middle", "low_level"} for slot in department["agent_slots"]))
            self.assertTrue(all(slot["management_tier"] != "senior" for slot in department["agent_slots"]))

    def test_store_agent_clones_a_template_without_starting_a_thread(self) -> None:
        catalog = json.loads(
            (ROOT / "skills/company-os/company-blueprint/assets/department-packs.json").read_text(
                encoding="utf-8"
            )
        )
        source = next(
            slot
            for slot in catalog["departments"][0]["agent_slots"]
            if slot["id"] == "executive-strategy-manager"
        )
        stored = dict(source)
        stored.update(
            {
                "id": "executive-strategy-manager-onboarding",
                "origin": "stored",
                "source_slot_id": "executive-strategy-manager",
                "status": "stored",
                "outcome": "Coordinate the onboarding program strategy slice",
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog_path = root / "department-packs.json"
            slot_path = root / "stored-slot.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            slot_path.write_text(json.dumps(stored), encoding="utf-8")
            result = compiler.store_agent_slot(
                catalog_path, "executive-strategy", slot_path, catalog_path
            )
            self.assertEqual("executive-strategy-manager-onboarding", result["slot_id"])
            self.assertFalse(result["running"])
            updated = compiler.validate_department_catalog(
                json.loads(catalog_path.read_text(encoding="utf-8"))
            )
            ids = {slot["id"] for slot in updated["executive-strategy"]["agent_slots"]}
            self.assertIn("executive-strategy-manager-onboarding", ids)
            with self.assertRaisesRegex(compiler.BlueprintError, "already stored"):
                compiler.store_agent_slot(
                    catalog_path, "executive-strategy", slot_path, catalog_path
                )
        shared_source = (
            ROOT / "skills/company-os/company-blueprint/assets/department-packs.json"
        )
        with tempfile.TemporaryDirectory() as temporary:
            slot_path = Path(temporary) / "stored-slot.json"
            slot_path.write_text(json.dumps(stored), encoding="utf-8")
            with self.assertRaisesRegex(compiler.BlueprintError, "shared department catalog"):
                compiler.store_agent_slot(
                    shared_source,
                    "executive-strategy",
                    slot_path,
                    compiler.DEFAULT_DEPARTMENTS,
                )

    def test_store_agent_rejects_role_or_model_drift(self) -> None:
        catalog = json.loads(
            (ROOT / "skills/company-os/company-blueprint/assets/department-packs.json").read_text(
                encoding="utf-8"
            )
        )
        stored = {
            "forbidden_roles": ["master", "worker"],
            "id": "executive-strategy-manager-bad",
            "management_tier": "staff",
            "origin": "stored",
            "outcome": "Illegal staff manager",
            "requested_model": "gpt-5.6-sol",
            "role": "manager",
            "skills": ["manage-company-program", "strategy-pillar"],
            "source_slot_id": "executive-strategy-manager",
            "status": "stored",
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog_path = root / "department-packs.json"
            slot_path = root / "stored-slot.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            slot_path.write_text(json.dumps(stored), encoding="utf-8")
            with self.assertRaisesRegex(compiler.BlueprintError, "role and management tier"):
                compiler.store_agent_slot(
                    catalog_path, "executive-strategy", slot_path, catalog_path
                )

    def test_postgres_blueprint_storage_is_portable_and_append_only(self) -> None:
        sql = SQL.read_text(encoding="utf-8")
        self.assertIn("company_os_observatory.company_blueprints", sql)
        self.assertIn("company_os_observatory.company_knowledge_edges", sql)
        self.assertIn("company_os_observatory.company_routines", sql)
        self.assertIn("reject_evidence_mutation", sql)
        self.assertNotIn("neon.tech", sql.lower())
        self.assertNotIn("supabase.com", sql.lower())
        self.assertNotIn("postgresql://", sql.lower())


if __name__ == "__main__":
    unittest.main()
