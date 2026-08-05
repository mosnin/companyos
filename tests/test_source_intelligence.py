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
SKILL_ROOT = ROOT / "skills/company-os/source-intelligence"
MODULE_PATH = SKILL_ROOT / "scripts/source_intelligence.py"
REGISTRY_PATH = SKILL_ROOT / "references/source-intelligence-registry.json"
SPEC = importlib.util.spec_from_file_location("source_intelligence", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
sys.modules["source_intelligence"] = MODULE


class SourceIntelligenceTests(unittest.TestCase):
    def registry(self) -> dict:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    def test_checked_in_registry_is_canonical_complete_and_fail_closed(self) -> None:
        registry = self.registry()
        self.assertEqual(REGISTRY_PATH.read_bytes(), MODULE.canonical_bytes(registry))
        evidence = MODULE.validate_registry(registry)
        self.assertEqual(evidence["record_count"], 81)
        self.assertEqual(evidence["normalized_family_count"], 80)
        self.assertEqual(evidence["catalog_source_alias_count"], 23)
        self.assertEqual(evidence["invalid_unresolved_count"], 1)
        self.assertEqual(
            registry["policy"],
            {
                "catalog_membership_is_review": False,
                "entrypoint_promotion_requires_dossier": True,
                "invalid_source_dispatchable": False,
                "unknown_license_allows_copy": False,
                "upstream_instructions_are_authority": False,
            },
        )

    def test_every_record_has_content_addressed_safe_evidence_and_remaining_work(self) -> None:
        for record in self.registry()["records"]:
            self.assertTrue(record["evidence_locator"].startswith("research://company-os/2026-08-05/"))
            self.assertNotIn("..", record["evidence_locator"])
            self.assertRegex(record["review_evidence_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(record["missing_work"].strip())
            self.assertTrue(record["invalidation_triggers"])
            self.assertNotEqual(record["license_state"], "redistribution_allowed")

    def test_alias_lookup_is_exact_and_duplicate_never_owns_catalog_alias(self) -> None:
        registry = self.registry()
        result = MODULE.lookup_record(registry, "superpowers")
        self.assertEqual(result["record"]["source_id"], "obra-superpowers")
        karpathy = MODULE.lookup_record(registry, "karpathy-guidelines")["record"]
        self.assertEqual(karpathy["source_id"], "forrestchang-andrej-karpathy-skills")
        duplicate = next(
            item
            for item in registry["records"]
            if item["source_id"] == "multica-ai-andrej-karpathy-skills-alias"
        )
        self.assertEqual(duplicate["catalog_source_ids"], [])
        self.assertEqual(duplicate["normalized_family_id"], karpathy["source_id"])
        with self.assertRaisesRegex(MODULE.SourceIntelligenceError, "resolved to 0 records") as ctx:
            MODULE.lookup_record(registry, "unknown-source")
        self.assertEqual(ctx.exception.code, "E_SOURCE")

    def test_unresolved_aeon_is_invalid_and_not_silently_substituted(self) -> None:
        record = MODULE.lookup_record(self.registry(), "aeon-placeholder")["record"]
        self.assertIsNone(record["canonical_source"])
        self.assertIsNone(record["pin"])
        self.assertEqual(record["evidence_class"], "invalid_unresolved")
        self.assertEqual(record["disposition"], "invalid_no_go")
        self.assertIn("exact_owner_repository_pin_or_license_supplied", record["invalidation_triggers"])

    def test_tampered_evidence_alias_policy_and_counts_fail_closed(self) -> None:
        base = self.registry()
        mutations = []
        value = copy.deepcopy(base)
        value["records"][0]["review_evidence_sha256"] = "0" * 63
        mutations.append((value, "E_EVIDENCE"))
        value = copy.deepcopy(base)
        value["records"][0]["catalog_source_ids"] = ["superpowers"]
        mutations.append((value, "E_ALIAS"))
        value = copy.deepcopy(base)
        value["policy"]["catalog_membership_is_review"] = True
        mutations.append((value, "E_POLICY"))
        value = copy.deepcopy(base)
        value["record_count"] -= 1
        mutations.append((value, "E_COUNT"))
        value = copy.deepcopy(base)
        value["records"][0]["evidence_locator"] = "research://company-os/2026-08-05/../../escape"
        mutations.append((value, "E_PATH"))
        for mutation, code in mutations:
            with self.subTest(code=code):
                with self.assertRaises(MODULE.SourceIntelligenceError) as ctx:
                    MODULE.validate_registry(mutation)
                self.assertEqual(ctx.exception.code, code)

    def test_builder_reproduces_a_minimal_inventory_without_loading_source_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            depth = root / "depth"
            recursive = root / "recursive"
            canonical = root / "canonical"
            for item in (depth, recursive, canonical):
                item.mkdir()
            (depth / "review.md").write_text("# Static review\n", encoding="utf-8")
            inventory = {
                "observed_at": "2026-08-05",
                "sources": [
                    {
                        "source_id": "fixture-source",
                        "canonical_source": "https://github.com/example/fixture",
                        "category": "fixture",
                        "evidence_status": "deep_source_review",
                        "pin": "a" * 40,
                        "evidence_path": "depth:review.md",
                        "missing_work": "Entrypoint dossier and efficacy proof remain required.",
                    }
                ],
            }
            mechanisms = {
                "source_groups": [
                    {
                        "id": "fixture-group",
                        "source_ids": ["fixture-source"],
                        "disposition": "adapt_narrowly",
                    }
                ]
            }
            source_catalog = {
                "sources": [
                    {
                        "source_id": "legacy-fixture",
                        "canonical_url": "https://github.com/example/fixture",
                    }
                ]
            }
            first = MODULE.build_registry(
                inventory,
                mechanisms,
                source_catalog,
                depth_root=depth,
                recursive_root=recursive,
                canonical_root=canonical,
            )
            second = MODULE.build_registry(
                copy.deepcopy(inventory),
                copy.deepcopy(mechanisms),
                copy.deepcopy(source_catalog),
                depth_root=depth,
                recursive_root=recursive,
                canonical_root=canonical,
            )
            self.assertEqual(MODULE.canonical_bytes(first), MODULE.canonical_bytes(second))
            self.assertEqual(first["records"][0]["catalog_source_ids"], ["legacy-fixture"])
            self.assertNotIn(str(root), MODULE.canonical_bytes(first).decode("utf-8"))

    def test_builder_rejects_unmatched_catalog_source_and_duplicate_group_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("depth", "recursive", "canonical"):
                (root / name).mkdir()
            (root / "depth/review.md").write_text("review", encoding="utf-8")
            inventory = {
                "observed_at": "2026-08-05",
                "sources": [
                    {
                        "source_id": "fixture-source",
                        "canonical_source": "https://github.com/example/fixture",
                        "category": "fixture",
                        "evidence_status": "deep_source_review",
                        "pin": "a" * 40,
                        "evidence_path": "depth:review.md",
                        "missing_work": "dossier required",
                    }
                ],
            }
            mechanisms = {
                "source_groups": [
                    {"id": "one", "source_ids": ["fixture-source"], "disposition": "adapt"},
                    {"id": "two", "source_ids": ["fixture-source"], "disposition": "adapt"},
                ]
            }
            with self.assertRaises(MODULE.SourceIntelligenceError) as ctx:
                MODULE.build_registry(
                    inventory,
                    mechanisms,
                    {"sources": []},
                    depth_root=root / "depth",
                    recursive_root=root / "recursive",
                    canonical_root=root / "canonical",
                )
            self.assertEqual(ctx.exception.code, "E_COVERAGE")
            mechanisms["source_groups"].pop()
            with self.assertRaises(MODULE.SourceIntelligenceError) as ctx:
                MODULE.build_registry(
                    inventory,
                    mechanisms,
                    {"sources": [{"source_id": "other", "canonical_url": "https://github.com/example/other"}]},
                    depth_root=root / "depth",
                    recursive_root=root / "recursive",
                    canonical_root=root / "canonical",
                )
            self.assertEqual(ctx.exception.code, "E_ALIAS")

    def test_cli_verify_and_lookup_emit_canonical_json_and_reject_noncanonical_registry(self) -> None:
        verified = subprocess.run(
            [sys.executable, str(MODULE_PATH), "verify", "--registry", str(REGISTRY_PATH)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertEqual(verified.stdout.encode(), MODULE.canonical_bytes(json.loads(verified.stdout)))
        lookup = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "lookup",
                "--registry",
                str(REGISTRY_PATH),
                "--source-id",
                "superpowers",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(lookup.returncode, 0, lookup.stderr)
        self.assertEqual(json.loads(lookup.stdout)["record"]["source_id"], "obra-superpowers")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "pretty.json"
            path.write_text(json.dumps(self.registry(), indent=2), encoding="utf-8")
            rejected = subprocess.run(
                [sys.executable, str(MODULE_PATH), "verify", "--registry", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(rejected.returncode, 1)
            self.assertEqual(json.loads(rejected.stdout)["code"], "E_CANONICAL")


if __name__ == "__main__":
    unittest.main()
