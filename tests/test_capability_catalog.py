from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/company-os/assign-capability-skills"
MODULE_PATH = SKILL_ROOT / "scripts/capability_catalog.py"
SPEC = importlib.util.spec_from_file_location("capability_catalog", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
sys.modules["capability_catalog"] = MODULE
BUILDER_PATH = SKILL_ROOT / "scripts/build_capability_catalog.py"
BUILDER_SPEC = importlib.util.spec_from_file_location("build_capability_catalog", BUILDER_PATH)
BUILDER = importlib.util.module_from_spec(BUILDER_SPEC)
assert BUILDER_SPEC.loader is not None
BUILDER_SPEC.loader.exec_module(BUILDER)
PROMOTER_PATH = SKILL_ROOT / "scripts/promote_curated_capabilities.py"
PROMOTER_SPEC = importlib.util.spec_from_file_location("promote_curated_capabilities", PROMOTER_PATH)
PROMOTER = importlib.util.module_from_spec(PROMOTER_SPEC)
assert PROMOTER_SPEC.loader is not None
PROMOTER_SPEC.loader.exec_module(PROMOTER)


class CapabilityCatalogTests(unittest.TestCase):
    def git(self, root: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def source_campaign(self, root: Path) -> tuple[dict, Path]:
        checkout = root / "external-source"
        checkout.mkdir()
        self.git(checkout, "init", "-q")
        self.git(checkout, "config", "user.email", "test@example.com")
        self.git(checkout, "config", "user.name", "Test")
        skill = checkout / "skills/review/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            "---\nname: bounded-review\ndescription: Review bounded engineering work.\n---\n",
            encoding="utf-8",
        )
        (checkout / "CLAUDE.md").write_text("# External method\n", encoding="utf-8")
        (checkout / "LICENSE").write_text("MIT License\n", encoding="utf-8")
        self.git(checkout, "add", ".")
        self.git(checkout, "commit", "-qm", "fixture")
        commit = self.git(checkout, "rev-parse", "HEAD")
        tree = self.git(checkout, "rev-parse", "HEAD^{tree}")
        campaign = {
            "$schema": "company-os.capability-source-campaign.v1",
            "schema_version": 1,
            "campaign_id": "fixture-campaign",
            "sources": [
                {
                    "source_id": "fixture-source",
                    "checkout_path": str(checkout),
                    "canonical_url": "https://github.com/example/fixture",
                    "source_commit": commit,
                    "source_tree": tree,
                    "observed_at": "2026-08-03T12:00:00Z",
                    "license": {
                        "spdx": "MIT",
                        "evidence_path": "LICENSE",
                        "redistribution": "allowed",
                    },
                    "disposition": "reference_only",
                    "risk_flags": [],
                    "default_domains": ["software_engineering"],
                    "default_roles": ["manager", "worker"],
                    "default_trust_state": "reference_only",
                    "entrypoint_globs": [],
                    "entrypoint_paths": ["CLAUDE.md"],
                }
            ],
        }
        return campaign, checkout

    def curation(self) -> dict:
        return {
            "$schema": "company-os.capability-curation.v1",
            "schema_version": 1,
            "curation_id": "fixture-curation",
            "capabilities": [
                {
                    "capability_id": "curated-bounded-review",
                    "name": "Curated bounded review",
                    "description": "Run a bounded review with task-local evidence.",
                    "source_id": "example-source",
                    "upstream_skill_path": "skills/review/SKILL.md",
                    "entrypoint": "vendor/example/curated-bounded-review/SKILL.md",
                    "roles": ["worker"],
                    "domains": ["software_engineering"],
                    "tags": ["evidence", "review"],
                    "required_permissions": [],
                    "conflicts": [],
                }
            ],
        }

    def fixture(self, root: Path) -> tuple[Path, dict, dict]:
        skill_root = root / "skill-root"
        entrypoint = skill_root / "vendor/example/review/SKILL.md"
        entrypoint.parent.mkdir(parents=True)
        entrypoint.write_text(
            "---\nname: example-review\ndescription: Review a frontend artifact.\n---\n\n# Secret procedural body\n",
            encoding="utf-8",
        )
        raw = entrypoint.read_bytes()
        catalog = {
            "$schema": "company-os.capability-catalog.v1",
            "schema_version": 1,
            "catalog_id": "test-catalog",
            "policy": {
                "max_skills_per_assignment": 4,
                "max_entrypoint_bytes_per_assignment": 49152,
                "max_search_results": 5,
            },
            "sources": [
                {
                    "source_id": "example-source",
                    "canonical_url": "https://github.com/example/skills",
                    "source_commit": "a" * 40,
                    "source_tree": "b" * 40,
                    "observed_at": "2026-08-03T12:00:00Z",
                    "license": {
                        "spdx": "MIT",
                        "evidence_path": "LICENSE",
                        "redistribution": "allowed",
                    },
                    "disposition": "vendor_curated_subset",
                    "risk_flags": [],
                }
            ],
            "capabilities": [
                {
                    "capability_id": "example-frontend-review",
                    "name": "Example frontend review",
                    "description": "Review frontend behavior and accessibility evidence.",
                    "source_id": "example-source",
                    "upstream_skill_path": "skills/review/SKILL.md",
                    "upstream_entrypoint_sha256": hashlib.sha256(raw).hexdigest(),
                    "upstream_entrypoint_bytes": len(raw),
                    "entrypoint": "vendor/example/review/SKILL.md",
                    "entrypoint_sha256": hashlib.sha256(raw).hexdigest(),
                    "entrypoint_bytes": len(raw),
                    "roles": ["manager", "worker"],
                    "domains": ["software_engineering", "ui_design"],
                    "tags": ["accessibility", "frontend", "review"],
                    "trust_state": "approved",
                    "dispatchable": True,
                    "load_policy": "explicit",
                    "required_permissions": ["filesystem_read"],
                    "conflicts": [],
                }
            ],
        }
        request = {
            "$schema": "company-os.capability-request.v1",
            "authorized_permissions": ["filesystem_read"],
            "domains": ["ui_design"],
            "execution_order": ["example-frontend-review"],
            "max_entrypoint_bytes": 49152,
            "max_skills": 4,
            "packet_id": "ui-worker",
            "program_id": "website-launch",
            "request_id": "ui-review-request",
            "requested_capability_ids": ["example-frontend-review"],
            "role": "worker",
            "selection_rationale": {
                "example-frontend-review": "The accepted UI scope needs an independent frontend review."
            },
        }
        return skill_root, catalog, request

    def write_json(self, path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(MODULE.canonical_bytes(value))

    def test_generated_source_catalog_closes_over_every_requested_source_without_dispatch(self) -> None:
        catalog_path = SKILL_ROOT / "references/source-catalog.json"
        raw = catalog_path.read_bytes()
        catalog = json.loads(raw)
        self.assertEqual(raw, MODULE.canonical_bytes(catalog))
        evidence = MODULE.validate_catalog(catalog, SKILL_ROOT, verify_files=True)
        self.assertEqual(23, evidence["source_count"])
        self.assertEqual(2621, evidence["capability_count"])
        self.assertEqual(0, evidence["dispatchable_count"])
        self.assertEqual(
            {
                "addyosmani-agent-skills",
                "agent-native-skills",
                "alexsmedile-hormozi-skills",
                "antfu-skills",
                "anthropic-cybersecurity-skills",
                "browserbase-skills",
                "cloudflare-skills",
                "getagentseal-founder-playbook",
                "gmapsscraper-google-maps-agent-skills",
                "karpathy-guidelines",
                "linuszz-business-strategy-planning-skills",
                "maigentic-stratarts",
                "microsoft-skills",
                "minhnv0807-ai-business-skills",
                "minimax-ai-skills",
                "nexscope-ai-ecommerce-skills",
                "nvidia-skills",
                "remotion-skills",
                "superpowers",
                "vercel-agent-skills",
                "w95-awesome-claude-corporate-skills",
                "wondelai-skills",
                "zubair-trabzada-ai-legal-claude",
            },
            {item["source_id"] for item in catalog["sources"]},
        )

    def test_final_catalog_promotes_only_the_twelve_manager_accepted_wrappers(self) -> None:
        catalog_path = SKILL_ROOT / "references/capability-catalog.json"
        raw = catalog_path.read_bytes()
        catalog = json.loads(raw)
        self.assertEqual(raw, MODULE.canonical_bytes(catalog))
        evidence = MODULE.validate_catalog(catalog, SKILL_ROOT, verify_files=True)
        self.assertEqual(23, evidence["source_count"])
        self.assertEqual(2633, evidence["capability_count"])
        self.assertEqual(12, evidence["dispatchable_count"])
        self.assertEqual(
            {
                "browser-boundary-design",
                "capability-assessment",
                "durable-state-design",
                "engineering-adversarial-review",
                "engineering-red-green-evidence",
                "market-definition",
                "market-opportunity-artifact",
                "marketing-context-intake",
                "mcp-tool-contract-design",
                "risk-matrix",
                "scenario-development",
                "systematic-debugging",
            },
            {
                item["capability_id"]
                for item in catalog["capabilities"]
                if item["dispatchable"]
            },
        )
        source_catalog = json.loads(
            (SKILL_ROOT / "references/source-catalog.json").read_text()
        )
        curation = json.loads(
            (SKILL_ROOT / "references/curation-manifest.json").read_text()
        )
        reproduced = PROMOTER.promote(source_catalog, curation, SKILL_ROOT)
        self.assertEqual(raw, MODULE.canonical_bytes(reproduced))
        results = MODULE.search_catalog(
            catalog,
            "systematic debugging evidence",
            role="worker",
            domain="software_engineering",
            limit=5,
            dispatchable_only=True,
        )
        self.assertTrue(results["dispatchable_only"])
        self.assertIn(
            "systematic-debugging",
            [item["capability_id"] for item in results["results"]],
        )
        self.assertTrue(all(item["dispatchable"] for item in results["results"]))

    def test_promoter_rejects_readme_and_mismatched_skill_frontmatter(self) -> None:
        source_catalog = json.loads(
            (SKILL_ROOT / "references/source-catalog.json").read_text()
        )
        full_curation = json.loads(
            (SKILL_ROOT / "references/curation-manifest.json").read_text()
        )
        entry = copy.deepcopy(full_curation["capabilities"][0])
        curation = copy.deepcopy(full_curation)
        curation["capabilities"] = [entry]

        with tempfile.TemporaryDirectory() as directory:
            skill_root = Path(directory)
            readme = skill_root / "vendor/engineering/browser-boundary-design/README.md"
            readme.parent.mkdir(parents=True)
            readme.write_text(
                "---\nname: browser-boundary-design\ndescription: Invalid filename.\n---\n",
                encoding="utf-8",
            )
            curation["capabilities"][0]["entrypoint"] = (
                "vendor/engineering/browser-boundary-design/README.md"
            )
            with self.assertRaisesRegex(MODULE.CatalogError, "SKILL.md"):
                PROMOTER.promote(source_catalog, curation, skill_root)

        with tempfile.TemporaryDirectory() as directory:
            skill_root = Path(directory)
            wrapper = skill_root / "vendor/engineering/browser-boundary-design/SKILL.md"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text(
                "---\nname: different-capability\ndescription: Mismatched identity.\n---\n",
                encoding="utf-8",
            )
            curation["capabilities"][0]["entrypoint"] = (
                "vendor/engineering/browser-boundary-design/SKILL.md"
            )
            with self.assertRaisesRegex(MODULE.CatalogError, "does not match"):
                PROMOTER.promote(source_catalog, curation, skill_root)

    def test_validate_and_search_return_metadata_without_skill_body(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root, catalog, _ = self.fixture(Path(directory))
            evidence = MODULE.validate_catalog(catalog, skill_root)
            self.assertEqual(1, evidence["dispatchable_count"])
            result = MODULE.search_catalog(catalog, "frontend review", role="worker", domain="ui_design", limit=5)
            encoded = MODULE.canonical_bytes(result)
            self.assertEqual("example-frontend-review", result["results"][0]["capability_id"])
            self.assertNotIn(b"Secret procedural body", encoded)
            self.assertNotIn(b"entrypoint_sha256", encoded)

    def test_resolve_is_deterministic_and_contains_only_exact_requested_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root, catalog, request = self.fixture(Path(directory))
            first = MODULE.resolve_assignment(catalog, request, skill_root)
            second = MODULE.resolve_assignment(catalog, request, skill_root)
            self.assertEqual(MODULE.canonical_bytes(first), MODULE.canonical_bytes(second))
            self.assertEqual(1, first["skill_count"])
            self.assertEqual("example-frontend-review", first["skills"][0]["capability_id"])
            self.assertNotIn(b"Secret procedural body", MODULE.canonical_bytes(first))
            MODULE.validate_assignment(first)

    def test_multi_skill_execution_order_is_explicit_preserved_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root, catalog, request = self.fixture(Path(directory))
            second_path = skill_root / "vendor/example/red-green/SKILL.md"
            second_path.parent.mkdir(parents=True)
            second_raw = b"---\nname: example-red-green\ndescription: Evidence cycle.\n---\n\nBounded evidence procedure.\n"
            second_path.write_bytes(second_raw)
            second = copy.deepcopy(catalog["capabilities"][0])
            second.update(
                {
                    "capability_id": "example-red-green",
                    "name": "Example red green",
                    "upstream_skill_path": "skills/red-green/SKILL.md",
                    "upstream_entrypoint_sha256": hashlib.sha256(second_raw).hexdigest(),
                    "upstream_entrypoint_bytes": len(second_raw),
                    "entrypoint": "vendor/example/red-green/SKILL.md",
                    "entrypoint_sha256": hashlib.sha256(second_raw).hexdigest(),
                    "entrypoint_bytes": len(second_raw),
                }
            )
            catalog["capabilities"].append(second)
            catalog["capabilities"].sort(key=lambda item: item["capability_id"])
            request["requested_capability_ids"] = [
                "example-frontend-review",
                "example-red-green",
            ]
            request["execution_order"] = [
                "example-red-green",
                "example-frontend-review",
            ]
            request["selection_rationale"] = {
                "example-frontend-review": "Review the completed behavior.",
                "example-red-green": "Establish behavior evidence before review.",
            }

            assignment = MODULE.resolve_assignment(catalog, request, skill_root)
            self.assertEqual(
                ["example-frontend-review", "example-red-green"],
                [skill["capability_id"] for skill in assignment["skills"]],
            )
            self.assertEqual(request["execution_order"], assignment["execution_order"])
            MODULE.validate_assignment(assignment)

            for invalid_order in (
                ["example-red-green"],
                ["example-red-green", "example-red-green"],
                ["example-red-green", "example-frontend-review", "unassigned-skill"],
            ):
                malformed = copy.deepcopy(request)
                malformed["execution_order"] = invalid_order
                with self.assertRaises(MODULE.CatalogError):
                    MODULE.resolve_assignment(catalog, malformed, skill_root)

            rebound = copy.deepcopy(assignment)
            rebound["execution_order"] = ["example-frontend-review"]
            rebound["binding"]["canonical_sha256"] = MODULE.canonical_digest(
                MODULE._assignment_unsigned(rebound)
            )
            with self.assertRaisesRegex(MODULE.CatalogError, "execution_order"):
                MODULE.validate_assignment(rebound)

    def test_verified_assignment_augments_host_with_digest_only_task_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root, catalog, request = self.fixture(Path(directory))
            assignment = MODULE.resolve_assignment(catalog, request, skill_root)
            base_host = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "company-os.host-capabilities.v1",
                "schema_version": 1,
                "program_id": "website-launch",
                "host_profile_id": "fixture-host",
                "runtimes": [
                    {
                        "runtime_id": "python3",
                        "runtime_type": "python",
                        "available": True,
                        "locator": "runtime://fixture/python3",
                    }
                ],
                "capabilities": [
                    {
                        "capability_id": "filesystem_read",
                        "available": True,
                        "runtime_id": "python3",
                        "tool_locator": "tool://fixture/filesystem-read",
                        "runtime_locator": "runtime://fixture/python3",
                    }
                ],
            }
            augmented = MODULE.augment_host_manifest(
                catalog, base_host, [(request, assignment)], skill_root
            )
            skill = next(
                item
                for item in augmented["capabilities"]
                if item["capability_id"] == "example-frontend-review"
            )
            self.assertEqual("skill", skill["capability_kind"])
            self.assertEqual(assignment["skills"][0]["entrypoint_sha256"], skill["artifact_sha256"])
            self.assertEqual("ui-worker", skill["skill_bindings"][0]["packet_id"])
            self.assertEqual("worker", skill["skill_bindings"][0]["role"])
            self.assertEqual(
                "workspace://skills/company-os/assign-capability-skills/vendor/example/review",
                skill["tool_locator"],
            )
            encoded = MODULE.canonical_bytes(augmented)
            self.assertNotIn(b"Secret procedural body", encoded)
            self.assertIn(b"company-os-skill-reference", encoded)

    def test_zero_skill_assignment_preserves_base_host_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root, catalog, request = self.fixture(Path(directory))
            request["requested_capability_ids"] = []
            request["execution_order"] = []
            request["selection_rationale"] = {}
            assignment = MODULE.resolve_assignment(catalog, request, skill_root)
            base_host = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "company-os.host-capabilities.v1",
                "schema_version": 1,
                "program_id": "website-launch",
                "host_profile_id": "fixture-host",
                "runtimes": [],
                "capabilities": [],
            }
            augmented = MODULE.augment_host_manifest(
                catalog, base_host, [(request, assignment)], skill_root
            )
            self.assertEqual(MODULE.canonical_bytes(base_host), MODULE.canonical_bytes(augmented))

    def test_host_augmentation_rejects_rebound_or_duplicate_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root, catalog, request = self.fixture(Path(directory))
            assignment = MODULE.resolve_assignment(catalog, request, skill_root)
            base_host = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "company-os.host-capabilities.v1",
                "schema_version": 1,
                "program_id": "website-launch",
                "host_profile_id": "fixture-host",
                "runtimes": [],
                "capabilities": [],
            }
            rebound = copy.deepcopy(assignment)
            rebound["skills"][0]["selection_rationale"] = "Rebound without its source request."
            rebound["binding"]["canonical_sha256"] = MODULE.canonical_digest(
                MODULE._assignment_unsigned(rebound)
            )
            with self.assertRaisesRegex(MODULE.CatalogError, "does not reproduce"):
                MODULE.augment_host_manifest(catalog, base_host, [(request, rebound)], skill_root)
            with self.assertRaisesRegex(MODULE.CatalogError, "more than one capability assignment"):
                MODULE.augment_host_manifest(
                    catalog,
                    base_host,
                    [(request, assignment), (request, assignment)],
                    skill_root,
                )

    def test_zero_skill_assignment_is_valid_and_does_not_force_a_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root, catalog, request = self.fixture(Path(directory))
            request["requested_capability_ids"] = []
            request["execution_order"] = []
            request["selection_rationale"] = {}
            assignment = MODULE.resolve_assignment(catalog, request, skill_root)
            self.assertEqual([], assignment["skills"])
            self.assertEqual(0, assignment["total_entrypoint_bytes"])

    def test_quarantined_or_reference_only_capabilities_cannot_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root, catalog, request = self.fixture(Path(directory))
            capability = catalog["capabilities"][0]
            capability["trust_state"] = "quarantine"
            capability["dispatchable"] = False
            capability["entrypoint"] = None
            capability["entrypoint_sha256"] = None
            capability["entrypoint_bytes"] = 0
            with self.assertRaisesRegex(MODULE.CatalogError, "not dispatchable"):
                MODULE.resolve_assignment(catalog, request, skill_root)

    def test_skill_cannot_widen_permissions_or_role(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root, catalog, request = self.fixture(Path(directory))
            request["authorized_permissions"] = []
            with self.assertRaisesRegex(MODULE.CatalogError, "widen permissions"):
                MODULE.resolve_assignment(catalog, request, skill_root)
            request["authorized_permissions"] = ["filesystem_read"]
            request["role"] = "manager"
            catalog["capabilities"][0]["roles"] = ["worker"]
            with self.assertRaisesRegex(MODULE.CatalogError, "not allowed for role"):
                MODULE.resolve_assignment(catalog, request, skill_root)

    def test_domain_mismatch_and_conflict_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root, catalog, request = self.fixture(Path(directory))
            request["domains"] = ["finance"]
            with self.assertRaisesRegex(MODULE.CatalogError, "does not match"):
                MODULE.resolve_assignment(catalog, request, skill_root)
            request["domains"] = ["ui_design"]
            second = copy.deepcopy(catalog["capabilities"][0])
            second["capability_id"] = "example-conflicting-review"
            second["conflicts"] = ["example-frontend-review"]
            catalog["capabilities"].append(second)
            catalog["capabilities"].sort(key=lambda item: item["capability_id"])
            request["requested_capability_ids"] = ["example-conflicting-review", "example-frontend-review"]
            request["execution_order"] = ["example-frontend-review", "example-conflicting-review"]
            request["selection_rationale"] = {
                "example-conflicting-review": "Challenge conflict handling.",
                "example-frontend-review": "Challenge conflict handling.",
            }
            with self.assertRaisesRegex(MODULE.CatalogError, "conflicts"):
                MODULE.resolve_assignment(catalog, request, skill_root)

    def test_bundle_limits_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root, catalog, request = self.fixture(Path(directory))
            request["max_entrypoint_bytes"] = 1
            with self.assertRaisesRegex(MODULE.CatalogError, "byte limit"):
                MODULE.resolve_assignment(catalog, request, skill_root)
            request["max_entrypoint_bytes"] = 49152
            request["max_skills"] = 5
            with self.assertRaisesRegex(MODULE.CatalogError, "exceeds catalog policy"):
                MODULE.resolve_assignment(catalog, request, skill_root)

    def test_entrypoint_hash_drift_and_symlink_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill_root, catalog, request = self.fixture(root)
            entrypoint = skill_root / catalog["capabilities"][0]["entrypoint"]
            entrypoint.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(MODULE.CatalogError, "drift"):
                MODULE.resolve_assignment(catalog, request, skill_root)
            target = root / "outside.md"
            target.write_text("outside", encoding="utf-8")
            entrypoint.unlink()
            entrypoint.symlink_to(target)
            capability = catalog["capabilities"][0]
            capability["entrypoint_bytes"] = len(target.read_bytes())
            capability["entrypoint_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
            with self.assertRaisesRegex(MODULE.CatalogError, "symlink"):
                MODULE.resolve_assignment(catalog, request, skill_root)

    def test_unknown_redistribution_blocks_vendored_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_root, catalog, _ = self.fixture(Path(directory))
            catalog["sources"][0]["license"]["redistribution"] = "unknown"
            with self.assertRaisesRegex(MODULE.CatalogError, "redistribution authority"):
                MODULE.validate_catalog(catalog, skill_root)

    def test_tampered_assignment_fails_reproduction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill_root, catalog, request = self.fixture(root)
            catalog_path = root / "catalog.json"
            request_path = root / "request.json"
            assignment_path = root / "assignment.json"
            self.write_json(catalog_path, catalog)
            self.write_json(request_path, request)
            assignment = MODULE.resolve_assignment(catalog, request, skill_root)
            assignment["skills"][0]["selection_rationale"] = "A different story."
            assignment["binding"]["canonical_sha256"] = MODULE.canonical_digest(
                MODULE._assignment_unsigned(assignment)
            )
            self.write_json(assignment_path, assignment)
            result = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "verify",
                    "--catalog",
                    str(catalog_path),
                    "--request",
                    str(request_path),
                    "--assignment",
                    str(assignment_path),
                    "--skill-root",
                    str(skill_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, result.returncode)
            self.assertEqual("E_ASSIGNMENT_DRIFT", json.loads(result.stdout)["error"]["code"])

    def test_cli_resolve_and_verify_emit_canonical_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill_root, catalog, request = self.fixture(root)
            catalog_path = root / "catalog.json"
            request_path = root / "request.json"
            assignment_path = root / "assignment.json"
            self.write_json(catalog_path, catalog)
            self.write_json(request_path, request)
            resolve = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "resolve",
                    "--catalog",
                    str(catalog_path),
                    "--request",
                    str(request_path),
                    "--skill-root",
                    str(skill_root),
                    "--output",
                    str(assignment_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, resolve.returncode, resolve.stdout + resolve.stderr)
            self.assertEqual(MODULE.canonical_bytes(json.loads(assignment_path.read_bytes())), assignment_path.read_bytes())
            verify = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "verify",
                    "--catalog",
                    str(catalog_path),
                    "--request",
                    str(request_path),
                    "--assignment",
                    str(assignment_path),
                    "--skill-root",
                    str(skill_root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, verify.returncode, verify.stdout + verify.stderr)
            self.assertTrue(json.loads(verify.stdout)["ok"])

    def test_builder_catalogs_tracked_skill_and_explicit_instruction_file_without_approving_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign, checkout = self.source_campaign(root)
            (checkout / "skills/untracked/SKILL.md").parent.mkdir(parents=True)
            (checkout / "skills/untracked/SKILL.md").write_text("untracked", encoding="utf-8")
            result = BUILDER.build_catalog(campaign)
            self.assertEqual(2, len(result["capabilities"]))
            paths = {item["upstream_skill_path"] for item in result["capabilities"]}
            self.assertEqual({"CLAUDE.md", "skills/review/SKILL.md"}, paths)
            for capability in result["capabilities"]:
                self.assertFalse(capability["dispatchable"])
                self.assertEqual("reference_only", capability["trust_state"])
                self.assertIsNone(capability["entrypoint"])

    def test_builder_refuses_to_automatically_approve_external_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            campaign, _ = self.source_campaign(Path(directory))
            campaign["sources"][0]["default_trust_state"] = "approved"
            with self.assertRaisesRegex(MODULE.CatalogError, "may not create approved"):
                BUILDER.build_catalog(campaign)

    def test_builder_accepts_a_tracked_intelligence_node_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign, checkout = self.source_campaign(root)
            manifest = checkout / "integrations/companyos/intelligence-node.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({
                "$schema": "company-os.intelligence-node.v1",
                "schema_version": 1,
                "node_id": "business-os",
                "controller": "company-os",
                "role": "passive_expert_kernel",
                "effects": [],
                "authority": {"dispatch": False, "external_write": False},
            }) + "\n", encoding="utf-8")
            self.git(checkout, "add", ".")
            self.git(checkout, "commit", "-qm", "add intelligence manifest")
            campaign["sources"][0]["source_commit"] = self.git(checkout, "rev-parse", "HEAD")
            campaign["sources"][0]["source_tree"] = self.git(checkout, "rev-parse", "HEAD^{tree}")
            campaign["sources"][0]["intelligence_node_manifest"] = manifest.relative_to(checkout).as_posix()
            result = BUILDER.build_catalog(campaign)
            self.assertEqual(2, len(result["capabilities"]))

            manifest.write_text(manifest.read_text().replace('"dispatch": false', '"dispatch": true'))
            self.git(checkout, "add", ".")
            self.git(checkout, "commit", "-qm", "make node active")
            campaign["sources"][0]["source_commit"] = self.git(checkout, "rev-parse", "HEAD")
            campaign["sources"][0]["source_tree"] = self.git(checkout, "rev-parse", "HEAD^{tree}")
            with self.assertRaisesRegex(MODULE.CatalogError, "passive"):
                BUILDER.build_catalog(campaign)

    def test_builder_rejects_an_untracked_intelligence_node_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            campaign, _ = self.source_campaign(Path(directory))
            campaign["sources"][0]["intelligence_node_manifest"] = "missing-node.json"
            with self.assertRaisesRegex(MODULE.CatalogError, "manifest is missing"):
                BUILDER.build_catalog(campaign)

    def test_builder_rejects_checkout_head_or_tree_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign, checkout = self.source_campaign(root)
            (checkout / "new.txt").write_text("new", encoding="utf-8")
            self.git(checkout, "add", "new.txt")
            self.git(checkout, "commit", "-qm", "new head")
            with self.assertRaisesRegex(MODULE.CatalogError, "does not match"):
                BUILDER.build_catalog(campaign)

    def test_promoter_adds_exact_local_wrapper_without_replacing_source_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill_root, source_catalog, _ = self.fixture(root)
            wrapper = skill_root / "vendor/example/curated-bounded-review/SKILL.md"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text(
                "---\nname: curated-bounded-review\ndescription: Review bounded work.\n---\n",
                encoding="utf-8",
            )
            result = PROMOTER.promote(source_catalog, self.curation(), skill_root)
            indexed = {item["capability_id"]: item for item in result["capabilities"]}
            self.assertIn("example-frontend-review", indexed)
            promoted = indexed["curated-bounded-review"]
            self.assertTrue(promoted["dispatchable"])
            self.assertEqual("approved", promoted["trust_state"])
            self.assertEqual(
                hashlib.sha256(wrapper.read_bytes()).hexdigest(), promoted["entrypoint_sha256"]
            )

    def test_promoter_rejects_unbound_wrapper_sidecar_resources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill_root, source_catalog, _ = self.fixture(root)
            wrapper = skill_root / "vendor/example/curated-bounded-review/SKILL.md"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text(
                "---\nname: curated-bounded-review\ndescription: Review bounded work.\n---\n",
                encoding="utf-8",
            )
            (wrapper.parent / "unbound-reference.md").write_text(
                "unbound", encoding="utf-8"
            )
            with self.assertRaisesRegex(MODULE.CatalogError, "no sidecar files"):
                PROMOTER.promote(source_catalog, self.curation(), skill_root)

    def test_promoter_rejects_blocked_source_or_missing_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill_root, source_catalog, _ = self.fixture(root)
            wrapper = skill_root / "vendor/example/curated-bounded-review/SKILL.md"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text("wrapper", encoding="utf-8")
            source_reference = source_catalog["capabilities"][0]
            source_reference["dispatchable"] = False
            source_reference["trust_state"] = "reference_only"
            source_reference["entrypoint"] = None
            source_reference["entrypoint_sha256"] = None
            source_reference["entrypoint_bytes"] = 0
            source_catalog["sources"][0]["disposition"] = "reference_only"
            with self.assertRaisesRegex(MODULE.CatalogError, "not eligible"):
                PROMOTER.promote(source_catalog, self.curation(), skill_root)
            source_catalog["sources"][0]["disposition"] = "vendor_curated_subset"
            curation = self.curation()
            curation["capabilities"][0]["upstream_skill_path"] = "skills/missing/SKILL.md"
            with self.assertRaisesRegex(MODULE.CatalogError, "no exact pinned"):
                PROMOTER.promote(source_catalog, curation, skill_root)


if __name__ == "__main__":
    unittest.main()
