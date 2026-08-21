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
                {"ok": True, "company_id": "acme-software", "files": 8},
            )
            for item in first_manifest["files"]:
                self.assertEqual(
                    (first_root / "compiled" / item["path"]).read_bytes(),
                    (second_root / "compiled" / item["path"]).read_bytes(),
                )

            organization = json.loads((first_root / "compiled/organization.json").read_text())
            self.assertEqual(10, organization["department_count"])
            self.assertEqual("elastic_work_graph", organization["capacity_policy"]["topology_mode"])
            self.assertNotIn("max_managers", organization["capacity_policy"])
            routines = json.loads((first_root / "compiled/routine-plan.json").read_text())
            self.assertTrue(routines["routines"])
            self.assertTrue(all(item["activation_state"] == "planned" for item in routines["routines"]))
            self.assertEqual(
                {"daily": "operations-exception-review", "monthly": "company-operating-review", "weekly": "portfolio-and-program-review"},
                routines["cadence"],
            )
            routine_ids = {item["id"] for item in routines["routines"]}
            self.assertTrue(set(routines["cadence"].values()) <= routine_ids)
            capabilities = json.loads((first_root / "compiled/capabilities.json").read_text())
            self.assertTrue(all(item["status"] == "requires-host-preflight" for item in capabilities["skills"]))
            self.assertTrue(all(item["status"] == "requires-host-preflight" for item in capabilities["tools"]))
            self.assertTrue(all(item["steps"] and item["evidence"] for item in capabilities["playbooks"]))

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
            self.assertEqual(7, organization["department_count"])
            self.assertIn("commercial-growth", department_ids)
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
        json_key = self.load_example()
        json_key["identity"]["thesis"] = "Keep credentials in env vars, never password"
        json_key["identity"]["password"] = "supersecretpassword"
        cases.append((json_key, "fields differ from the contract"))
        dsn_thesis = self.load_example()
        dsn_thesis["identity"]["thesis"] = "connect with postgresql://user:s3cretpass@host/db"
        cases.append((dsn_thesis, "secret material"))
        pem = self.load_example()
        pem["identity"]["thesis"] = "-----BEGIN RSA PRIVATE KEY----- MIIEowIBAAKCAQEA0Z3examplekeymaterial"
        cases.append((pem, "secret material"))
        dsn = self.load_example()
        dsn["storage"]["dsn_env"] = "postgresql://user:password@host/db"
        cases.append((dsn, "must name an environment variable"))
        locator = self.load_example()
        locator["assets"] = [
            {"id": "prod-db", "kind": "database", "locator": "postgresql://ops:hunter2secret@db.internal/company"}
        ]
        cases.append((locator, "secret material"))
        leaked_token = self.load_example()
        leaked_token["integrations"] = [
            {
                "id": "customer-crm",
                "kind": "mcp",
                "locator": "mcp://crm",
                "permission_mode": "read_only",
                "api_token": "sk-abcdefghijklmnop",
            }
        ]
        cases.append((leaked_token, "fields differ from the contract"))
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

    def test_verify_rejects_empty_or_malformed_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            empty = root / "empty"
            empty.mkdir()
            (empty / "manifest.json").write_bytes(
                compiler.canonical_bytes(
                    {
                        "$schema": "company-os.compiled-company-manifest.v1",
                        "blueprint_sha256": "a" * 64,
                        "blueprint_version": 1,
                        "company_id": "forged-company",
                        "files": [],
                    }
                )
            )
            with self.assertRaisesRegex(compiler.BlueprintError, "files must be a non-empty list"):
                compiler.verify_compiled(empty)

            malformed = root / "malformed"
            malformed.mkdir()
            (malformed / "manifest.json").write_bytes(
                compiler.canonical_bytes(
                    {
                        "$schema": "company-os.compiled-company-manifest.v1",
                        "blueprint_sha256": "a" * 64,
                        "blueprint_version": 1,
                        "company_id": "forged-company",
                        "files": "not-a-list",
                    }
                )
            )
            with self.assertRaisesRegex(compiler.BlueprintError, "files must be a non-empty list"):
                compiler.verify_compiled(malformed)

    def test_cadence_must_resolve_to_selected_routines(self) -> None:
        invented = self.load_example()
        invented["cadence"]["daily"] = "totally-invented-routine"
        disabled = self.load_example()
        disabled["operating_model"]["department_overrides"] = [
            {"department_id": "operations", "enabled": False, "reason": "Operator declined operations"}
        ]
        for blueprint, expected in (
            (invented, "outside the selected organization"),
            (disabled, "outside the selected organization"),
        ):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with self.assertRaisesRegex(compiler.BlueprintError, expected):
                    compiler.compile_blueprint(self.write_blueprint(root, blueprint), root / "compiled")

    def test_duplicate_unknowns_and_overrides_fail_closed(self) -> None:
        duplicates = self.load_example()
        duplicates["unknowns"] = [
            {"id": "gap-one", "question": "A?", "blocking": False, "owner": "operator", "resolution": "Ask later"},
            {"id": "gap-one", "question": "B?", "blocking": False, "owner": "operator", "resolution": "Ask later"},
        ]
        overrides = self.load_example()
        overrides["operating_model"]["department_overrides"] = [
            {"department_id": "finance", "enabled": False, "reason": "Remove finance"},
            {"department_id": "finance", "enabled": True, "reason": "Keep finance"},
        ]
        for blueprint, expected in (
            (duplicates, "duplicate unknown id"),
            (overrides, "duplicate department override"),
        ):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with self.assertRaisesRegex(compiler.BlueprintError, expected):
                    compiler.compile_blueprint(self.write_blueprint(root, blueprint), root / "compiled")

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
