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
        root.mkdir(parents=True, exist_ok=True)
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
            self.assertEqual(
                {
                    "daily": "operations-exception-review",
                    "weekly": "portfolio-and-program-review",
                    "monthly": "company-operating-review",
                },
                routines["company_cadence"],
            )
            self.assertEqual(routines["company_cadence"], routines["cadence"])
            routine_ids = {item["id"] for item in routines["routines"]}
            self.assertTrue(set(routines["cadence"].values()) <= routine_ids)
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
        thesis_dsn = self.load_example()
        thesis_dsn["identity"]["thesis"] = "postgresql://operator:hunter2secret@db.internal/company"
        cases.append((thesis_dsn, "secret material"))
        asset_dsn = self.load_example()
        asset_dsn["assets"] = [
            {"id": "prod-dump", "kind": "database", "locator": "postgres://operator:hunter2secret@db.internal/company"}
        ]
        cases.append((asset_dsn, "secret material"))
        integration_dsn = self.load_example()
        integration_dsn["integrations"] = [
            {
                "id": "prod-db",
                "kind": "database",
                "locator": "mysql://root:hunter2secret@db.internal/company",
                "permission_mode": "read_only",
            }
        ]
        cases.append((integration_dsn, "secret material"))
        knowledge_dsn = self.load_example()
        knowledge_dsn["knowledge"]["sources"] = ["mongodb://operator:hunter2secret@db.internal/company"]
        cases.append((knowledge_dsn, "secret material"))
        token = self.load_example()
        token["identity"]["thesis"] = "sk-proj-abcdefghijklmnopqrstuvwxyz012345"
        cases.append((token, "secret material"))
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
                self.assertFalse((root / "compiled").exists())

    def test_catalog_and_compiled_dsn_material_fail_closed_before_write(self) -> None:
        playbooks = json.loads(
            (ROOT / "skills/company-os/company-blueprint/assets/playbook-library.json").read_text(encoding="utf-8")
        )
        playbooks["playbooks"][0]["steps"][0] = "connect postgresql://operator:hunter2secret@db.internal/company"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = root / "playbooks.json"
            catalog.write_text(json.dumps(playbooks), encoding="utf-8")
            with self.assertRaisesRegex(compiler.BlueprintError, "playbook catalog.*secret material"):
                compiler.compile_blueprint(
                    self.write_blueprint(root, self.load_example()),
                    root / "compiled",
                    playbook_catalog_path=catalog,
                )
            self.assertFalse((root / "compiled").exists())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            compiler.compile_blueprint(self.write_blueprint(root, self.load_example()), root / "compiled")
            path = root / "compiled/storage-plan.json"
            storage = json.loads(path.read_text(encoding="utf-8"))
            storage["note"] = "postgresql://operator:hunter2secret@db.internal/company"
            raw = compiler.canonical_bytes(storage)
            path.write_bytes(raw)
            manifest = json.loads((root / "compiled/manifest.json").read_text(encoding="utf-8"))
            for item in manifest["files"]:
                if item["path"] == "storage-plan.json":
                    item["sha256"] = compiler.digest_bytes(raw)
                    item["size"] = len(raw)
            (root / "compiled/manifest.json").write_bytes(compiler.canonical_bytes(manifest))
            with self.assertRaisesRegex(compiler.BlueprintError, "compiled artifact storage-plan.json.*secret material"):
                compiler.verify_compiled(root / "compiled")

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

    def _paying_teams_blueprint(self, company_id: str, target: str) -> dict:
        blueprint = self.load_example()
        blueprint["company_id"] = company_id
        blueprint["identity"]["legal_name"] = f"{company_id} LLC"
        blueprint["identity"]["operating_name"] = company_id
        blueprint["objectives"] = [
            {
                "baseline": "0 paying Team or Team Plus brokerage accounts as of 2026-08-15",
                "horizon": "2026-12-31",
                "id": "objective-paying-teams",
                "metric": "Paying Team or Team Plus brokerage accounts",
                "outcome": "Tens of thousands of paying Team or Team Plus brokerage accounts",
                "priority": 1,
                "target": target,
            }
        ]
        return blueprint

    def _objective_node(self, compiled: Path, objective_id: str) -> dict:
        graph = json.loads((compiled / "knowledge-graph.json").read_text(encoding="utf-8"))
        node = next(item for item in graph["nodes"] if item["id"] == f"objective:{objective_id}")
        return node

    def test_compile_preserves_objective_target_and_refuses_foreign_company_overwrite(self) -> None:
        chippi_target = "At least 10000 paying Team or Team Plus brokerage accounts"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            compiled = root / "compiled"
            blueprint_path = self.write_blueprint(root, self._paying_teams_blueprint("chippi", chippi_target))
            compiler.compile_blueprint(blueprint_path, compiled)
            compiler.compile_blueprint(blueprint_path, compiled)
            node = self._objective_node(compiled, "objective-paying-teams")
            self.assertEqual(node["target"], chippi_target)
            self.assertEqual(node["label"], "Tens of thousands of paying Team or Team Plus brokerage accounts")
            before = (compiled / "knowledge-graph.json").read_bytes()
            substitute = self._paying_teams_blueprint(
                "other-broker",
                "1000 paying Team or Team Plus brokerage accounts",
            )
            with self.assertRaisesRegex(compiler.BlueprintError, "already bound to company chippi"):
                compiler.compile_blueprint(self.write_blueprint(root / "other", substitute), compiled)
            self.assertEqual((compiled / "knowledge-graph.json").read_bytes(), before)
            self.assertEqual(self._objective_node(compiled, "objective-paying-teams")["target"], chippi_target)

    def test_compile_does_not_write_through_artifact_symlink(self) -> None:
        chippi_target = "At least 10000 paying Team or Team Plus brokerage accounts"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chippi = root / "chippi" / "compiled"
            attacker = root / "attacker" / "compiled"
            compiler.compile_blueprint(
                self.write_blueprint(root / "chippi", self._paying_teams_blueprint("chippi", chippi_target)),
                chippi,
            )
            before = (chippi / "knowledge-graph.json").read_bytes()
            attacker.mkdir(parents=True)
            for name in (
                "asset-registry.json",
                "capabilities.json",
                "integration-registry.json",
                "organization.json",
                "routine-plan.json",
                "storage-plan.json",
                "work-graph.json",
                "manifest.json",
            ):
                (attacker / name).write_bytes((chippi / name).read_bytes())
            (attacker / "knowledge-graph.json").symlink_to(chippi / "knowledge-graph.json")
            substitute = self._paying_teams_blueprint(
                "chippi",
                "1000 paying Team or Team Plus brokerage accounts",
            )
            with self.assertRaisesRegex(compiler.BlueprintError, "symlink"):
                compiler.compile_blueprint(self.write_blueprint(root / "attacker", substitute), attacker)
            self.assertTrue((chippi / "knowledge-graph.json").is_file())
            self.assertFalse((chippi / "knowledge-graph.json").is_symlink())
            self.assertEqual((chippi / "knowledge-graph.json").read_bytes(), before)
            self.assertEqual(self._objective_node(chippi, "objective-paying-teams")["target"], chippi_target)
    def test_company_cadence_must_bind_selected_routines_and_matching_periods(self) -> None:
        cases = [
            (
                lambda blueprint: blueprint["cadence"].update(daily="not-a-compiled-routine"),
                "not in the compiled organization",
            ),
            (
                lambda blueprint: blueprint["cadence"].update(daily="weekly-program-preflight"),
                "runs on a weekly cadence",
            ),
            (
                lambda blueprint: (
                    blueprint["operating_model"]["department_overrides"].append(
                        {
                            "department_id": "security-compliance",
                            "enabled": False,
                            "reason": "Operator declined security",
                        }
                    ),
                    blueprint["cadence"].update(monthly="risk-and-control-review"),
                ),
                "not in the compiled organization",
            ),
            (
                lambda blueprint: blueprint["cadence"].update(
                    daily="portfolio-and-program-review",
                    weekly="portfolio-and-program-review",
                ),
                "distinct routines",
            ),
        ]
        for mutation, expected in cases:
            blueprint = self.load_example()
            mutation(blueprint)
            with self.subTest(expected=expected):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    with self.assertRaisesRegex(compiler.BlueprintError, expected):
                        compiler.compile_blueprint(self.write_blueprint(root, blueprint), root / "compiled")

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
