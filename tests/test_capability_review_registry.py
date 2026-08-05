from __future__ import annotations

import copy
import base64
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/company-os/assign-capability-skills"
MODULE_PATH = SKILL_ROOT / "scripts/capability_review_registry.py"
CATALOG_PATH = SKILL_ROOT / "references/capability-catalog.json"
DECISIONS_PATH = SKILL_ROOT / "references/capability-review-decisions.json"
REGISTRY_PATH = SKILL_ROOT / "references/capability-review-registry.json"
SOURCE_PATH = ROOT / "skills/company-os/source-intelligence/references/source-intelligence-registry.json"
MANIFEST_PATH = Path("/Users/preston/Documents/Codex/2026-08-05/company-os-all-repos-depth/evidence/master/capability-review-checkouts.v1.json")
SPEC = importlib.util.spec_from_file_location("capability_review_registry", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
sys.modules["capability_review_registry"] = MODULE


class CapabilityReviewRegistryTests(unittest.TestCase):
    def values(self) -> tuple[dict, dict, dict, dict]:
        return tuple(
            json.loads(path.read_text(encoding="utf-8"))
            for path in (DECISIONS_PATH, CATALOG_PATH, SOURCE_PATH, REGISTRY_PATH)
        )

    def test_candidate_registry_is_canonical_exactly_covers_dispatchable_wrappers(self) -> None:
        decisions, catalog, sources, registry = self.values()
        self.assertEqual(REGISTRY_PATH.read_bytes(), MODULE.canonical_bytes(registry))
        evidence = MODULE.validate_registry(registry, catalog, sources, SKILL_ROOT, MANIFEST_PATH)
        self.assertEqual(evidence["review_count"], 12)
        self.assertEqual(evidence["candidate_count"], 12)
        self.assertEqual(evidence["accepted_count"], 0)
        dispatchable = {item["capability_id"] for item in catalog["capabilities"] if item["dispatchable"]}
        self.assertEqual({item["capability_id"] for item in decisions["decisions"]}, dispatchable)
        self.assertEqual({item["capability_id"] for item in registry["records"]}, dispatchable)

    def test_build_is_deterministic_and_binds_source_catalog_and_wrapper_bytes(self) -> None:
        decisions, catalog, sources, registry = self.values()
        rebuilt = MODULE.build_registry(decisions, catalog, sources, SKILL_ROOT, MANIFEST_PATH)
        self.assertEqual(MODULE.canonical_bytes(rebuilt), REGISTRY_PATH.read_bytes())
        for record in rebuilt["records"]:
            self.assertRegex(record["source_review_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(record["upstream_entrypoint_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(record["wrapper_entrypoint_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(record["license_conclusion"], "source_acceptance_only_no_redistribution_claim")
            self.assertEqual(record["prompt_injection_boundary"], "upstream_content_not_loaded_at_dispatch")
            self.assertFalse(record["upstream_references_admitted"])

    def test_acceptance_is_a_real_barrier_not_implied_by_candidate_materialization(self) -> None:
        _, catalog, sources, registry = self.values()
        with self.assertRaises(MODULE.ReviewError) as ctx:
            MODULE.validate_registry(registry, catalog, sources, SKILL_ROOT, MANIFEST_PATH, require_accepted=True)
        self.assertEqual(ctx.exception.code, "E_DECISION")

    def test_semantic_family_collision_rejects_two_business_decision_lenses(self) -> None:
        _, catalog, sources, registry = self.values()
        accepted = copy.deepcopy(registry)
        for record in accepted["records"]:
            record["review_decision"] = "approved_narrow_wrapper"
        one = MODULE.resolve_reviews(
            accepted,
            catalog,
            sources,
            SKILL_ROOT,
            ["risk-matrix"],
            MANIFEST_PATH,
        )
        self.assertEqual(one["capability_ids"], ["risk-matrix"])
        with self.assertRaises(MODULE.ReviewError) as ctx:
            MODULE.resolve_reviews(
                accepted,
                catalog,
                sources,
                SKILL_ROOT,
                ["risk-matrix", "scenario-development"],
                MANIFEST_PATH,
            )
        self.assertEqual(ctx.exception.code, "E_EXCLUSIVE_FAMILY")

    def test_tampered_catalog_source_wrapper_authority_and_license_bindings_fail(self) -> None:
        _, catalog, sources, registry = self.values()
        mutations = []
        value = copy.deepcopy(registry)
        value["catalog_sha256"] = "0" * 64
        mutations.append((value, "E_BINDING"))
        value = copy.deepcopy(registry)
        value["source_intelligence_registry_sha256"] = "0" * 64
        mutations.append((value, "E_BINDING"))
        value = copy.deepcopy(registry)
        value["records"][0]["wrapper_entrypoint_sha256"] = "0" * 64
        mutations.append((value, "E_BINDING"))
        value = copy.deepcopy(registry)
        value["records"][0]["upstream_references_admitted"] = True
        mutations.append((value, "E_AUTHORITY"))
        value = copy.deepcopy(registry)
        value["records"][0]["license_conclusion"] = "redistribution_allowed"
        mutations.append((value, "E_LICENSE"))
        for mutation, code in mutations:
            with self.subTest(code=code):
                with self.assertRaises(MODULE.ReviewError) as ctx:
                    MODULE.validate_registry(mutation, catalog, sources, SKILL_ROOT, MANIFEST_PATH)
                self.assertEqual(ctx.exception.code, code)

    def test_review_cannot_drop_or_add_a_dispatchable_capability(self) -> None:
        decisions, catalog, sources, _ = self.values()
        dropped = copy.deepcopy(decisions)
        dropped["decisions"].pop()
        with self.assertRaises(MODULE.ReviewError) as ctx:
            MODULE.build_registry(dropped, catalog, sources, SKILL_ROOT, MANIFEST_PATH)
        self.assertEqual(ctx.exception.code, "E_COVERAGE")
        added = copy.deepcopy(decisions)
        duplicate = copy.deepcopy(added["decisions"][0])
        duplicate["capability_id"] = "not-dispatchable"
        duplicate["review_id"] = "review-not-dispatchable-v1"
        added["decisions"].append(duplicate)
        with self.assertRaises(MODULE.ReviewError) as ctx:
            MODULE.build_registry(added, catalog, sources, SKILL_ROOT, MANIFEST_PATH)
        self.assertEqual(ctx.exception.code, "E_COVERAGE")

    def test_manifest_is_explicit_and_checkout_tampering_fails_closed(self) -> None:
        decisions, catalog, sources, registry = self.values()
        with self.assertRaises(MODULE.ReviewError) as ctx:
            MODULE.validate_registry(registry, catalog, sources, SKILL_ROOT)
        self.assertEqual(ctx.exception.code, "E_CHECKOUT")
        manifest = json.loads(MANIFEST_PATH.read_text())
        for field, code in (("source_commit", "E_BINDING"), ("source_tree", "E_BINDING"), ("checkout_path", "E_PATH")):
            mutated = copy.deepcopy(manifest)
            if field == "checkout_path":
                mutated["sources"][0][field] = "/tmp/does-not-exist"
            else:
                mutated["sources"][0][field] = "0" * 40
            with self.subTest(field=field):
                with self.assertRaises(MODULE.ReviewError) as ctx:
                    MODULE.validate_registry(registry, catalog, sources, SKILL_ROOT, mutated)
                self.assertEqual(ctx.exception.code, code)

    def test_license_transitive_source_and_review_tampering_fail_closed(self) -> None:
        decisions, catalog, sources, registry = self.values()
        for mutation, code in (
            (lambda d: d["decisions"][0]["license_evidence"].update(path="skills/safe-browser/SKILL.md"), "E_LICENSE"),
            (lambda d: d["decisions"][0]["license_evidence"].update(bytes=1), "E_LICENSE"),
            (lambda d: d["decisions"][0]["upstream_transitive_references"][0].update(path="missing"), "E_BINDING"),
            (lambda d: d["decisions"][0]["upstream_transitive_references"][0].update(bytes=1), "E_BINDING"),
            (lambda d: d["decisions"][0].update(upstream_transitive_manifest_sha256="0" * 64), "E_BINDING"),
        ):
            mutated = copy.deepcopy(decisions)
            mutation(mutated)
            with self.subTest(code=code):
                with self.assertRaises(MODULE.ReviewError) as ctx:
                    MODULE.build_registry(mutated, catalog, sources, SKILL_ROOT, MANIFEST_PATH)
                self.assertEqual(ctx.exception.code, code)
        source_mutation = copy.deepcopy(sources)
        source_mutation["records"][0]["review_evidence_sha256"] = "0" * 64
        with self.assertRaises(MODULE.ReviewError) as ctx:
            MODULE.validate_registry(registry, catalog, source_mutation, SKILL_ROOT, MANIFEST_PATH)
        self.assertEqual(ctx.exception.code, "E_BINDING")

    def test_three_business_decision_lenses_collide(self) -> None:
        _, catalog, sources, registry = self.values()
        accepted = copy.deepcopy(registry)
        for record in accepted["records"]:
            record["review_decision"] = "approved_narrow_wrapper"
        with self.assertRaises(MODULE.ReviewError) as ctx:
            MODULE.resolve_reviews(
                accepted,
                catalog,
                sources,
                SKILL_ROOT,
                ["capability-assessment", "risk-matrix", "scenario-development"],
                MANIFEST_PATH,
            )
        self.assertEqual(ctx.exception.code, "E_EXCLUSIVE_FAMILY")

    def test_selected_promotion_requires_external_rsa_receipt_and_portable_bundle(self) -> None:
        _, catalog, sources, registry = self.values()
        now = "2026-08-05T12:00:00Z"
        scope = {
            "program_id": "capability-review-test",
            "packet_id": "promotion-test",
            "purpose": "capability_review_promotion",
            "candidate_author_id": "author-1",
            "candidate_worker_id": "worker-1",
            "candidate_manager_id": "manager-1",
            "operation_id": "promotion-op-1",
        }
        with tempfile.TemporaryDirectory(prefix="company-os-capability-review-test-") as directory:
            tmp = Path(directory)
            private = tmp / "test-only-signing-key.pem"
            public = tmp / "test-only-public-anchor.pem"
            subprocess.run(
                ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private)],
                check=True, capture_output=True,
            )
            subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)], check=True, capture_output=True)
            anchor = {
                "$schema": MODULE.TRUST_ANCHOR_SCHEMA,
                "schema_version": 1,
                "anchor_id": "test-only-capability-review-anchor",
                "algorithm": MODULE.SIGNATURE_ALGORITHM,
                "public_key_pem": public.read_text(),
            }
            selected = ["systematic-debugging"]
            receipt = {
                "$schema": MODULE.ACCEPTANCE_SCHEMA,
                "schema_version": 1,
                "receipt_id": "test-only-acceptance-1",
                "reviewer_id": "reviewer-1",
                "reviewer_role": "independent_reviewer",
                "reviewer_authority_receipt": {
                    "$schema": MODULE.REVIEWER_AUTHORITY_SCHEMA,
                    "schema_version": 1,
                    "receipt_id": "test-only-reviewer-authority-1",
                    "reviewer_id": "reviewer-1",
                    "authority": "independent_capability_review",
                    "status": "active",
                    "issued_at": "2026-08-05T00:00:00Z",
                    "expires_at": "2026-08-06T00:00:00Z",
                    "scope": scope,
                },
                "candidate_digest": MODULE.canonical_digest(registry),
                "catalog_sha256": MODULE.canonical_digest(catalog),
                "source_intelligence_registry_sha256": MODULE.canonical_digest(sources),
                "checkout_manifest_sha256": MODULE.canonical_digest(json.loads(MANIFEST_PATH.read_text())),
                "selected_capability_ids": selected,
                "selected_review_record_digests": MODULE._selected_record_digests(registry["records"], selected),
                "verdict": "accepted",
                "issued_at": "2026-08-05T00:00:00Z",
                "expires_at": "2026-08-06T00:00:00Z",
                "scope": scope,
                "trust_anchor_id": anchor["anchor_id"],
                "signature": {
                    "algorithm": MODULE.SIGNATURE_ALGORITHM,
                    "key_id": anchor["anchor_id"],
                    "value": "placeholder",
                },
            }
            unsigned = MODULE.canonical_bytes(MODULE._receipt_unsigned(receipt))
            payload = tmp / "receipt.json"
            payload.write_bytes(unsigned)
            signature = subprocess.run(
                ["openssl", "dgst", "-sha256", "-sign", str(private), "-out", str(tmp / "receipt.sig"), str(payload)],
                check=True, capture_output=True,
            )
            self.assertEqual(signature.returncode, 0)
            receipt["signature"]["value"] = base64.b64encode((tmp / "receipt.sig").read_bytes()).decode()
            built = MODULE.build_acceptance_receipt(
                receipt_id=receipt["receipt_id"], reviewer_id=receipt["reviewer_id"], reviewer_role=receipt["reviewer_role"],
                reviewer_authority_receipt=receipt["reviewer_authority_receipt"], candidate=registry,
                catalog_sha256=receipt["catalog_sha256"], source_intelligence_registry_sha256=receipt["source_intelligence_registry_sha256"],
                checkout_manifest_sha256=receipt["checkout_manifest_sha256"], selected_capability_ids=selected,
                verdict=receipt["verdict"], issued_at=receipt["issued_at"], expires_at=receipt["expires_at"],
                scope=scope, trust_anchor=anchor, signature=receipt["signature"],
            )
            bundle = MODULE.promote_selected_reviews(
                registry, catalog, sources, SKILL_ROOT, MANIFEST_PATH, built, anchor, selected,
                expected_scope=scope, now=now,
            )
            evidence = MODULE.verify_portable_bundle(bundle, anchor, catalog=catalog, source_registry=sources, now=now)
            self.assertEqual(evidence["selected_capability_ids"], selected)
            self.assertEqual(bundle["records"][0]["review_decision"], "candidate_for_independent_acceptance")

            for mutation, code in (
                (lambda r: r.update(expires_at="2026-08-05T01:00:00Z"), "E_EXPIRED"),
                (lambda r: r.update(selected_capability_ids=["risk-matrix"]), "E_SELECTION"),
                (lambda r: r.update(scope={"program_id": "other"}), "E_SCOPE"),
                (lambda r: r.update(candidate_digest="0" * 64), "E_BINDING"),
            ):
                mutated = copy.deepcopy(built)
                mutation(mutated)
                with self.subTest(code=code):
                    with self.assertRaises(MODULE.ReviewError) as ctx:
                        MODULE.validate_acceptance_receipt(
                            mutated, anchor, candidate_digest=MODULE.canonical_digest(registry),
                            selected_capability_ids=selected, expected_scope=scope, now=now,
                        )
                    self.assertEqual(ctx.exception.code, code)
            with self.assertRaises(MODULE.ReviewError) as ctx:
                MODULE.validate_acceptance_receipt(built, {**anchor, "anchor_id": "other-anchor"}, now=now)
            self.assertEqual(ctx.exception.code, "E_TRUST")
            with self.assertRaises(MODULE.ReviewError) as ctx:
                MODULE.validate_acceptance_receipt(built, anchor, now=now, used_receipt_ids={built["receipt_id"]})
            self.assertEqual(ctx.exception.code, "E_REPLAY")

            def rebind_portable(value: dict) -> None:
                value["acceptance_receipt_sha256"] = MODULE.canonical_digest(value["acceptance_receipt"])
                value["binding"]["canonical_sha256"] = MODULE.canonical_digest(MODULE._bundle_unsigned(value))

            # Receipt validation only reserves/checks replay use; it must never
            # consume before the full portable operation is known to succeed.
            pristine_state = {"consumed_receipts": {}}
            pristine_bytes = MODULE.canonical_bytes(pristine_state)
            MODULE.validate_acceptance_receipt(built, anchor, now=now, replay_state=pristine_state)
            self.assertEqual(pristine_bytes, MODULE.canonical_bytes(pristine_state))

            invalid_signature = copy.deepcopy(bundle)
            invalid_signature["acceptance_receipt"]["signature"]["value"] = base64.b64encode(b"invalid").decode()
            rebind_portable(invalid_signature)
            tampered_record = copy.deepcopy(bundle)
            tampered_record["records"][0]["review_id"] = "tampered-review-id"
            rebind_portable(tampered_record)
            wrong_catalog = copy.deepcopy(catalog)
            wrong_catalog["capabilities"][0]["description"] = "tampered catalog description"
            wrong_source = copy.deepcopy(sources)
            wrong_source["records"][0]["review_evidence_sha256"] = "0" * 64
            for challenged_bundle, challenged_catalog, challenged_source, code in (
                (invalid_signature, catalog, sources, "E_SIGNATURE"),
                (tampered_record, catalog, sources, "E_BINDING"),
                (bundle, wrong_catalog, sources, "E_BINDING"),
                (bundle, catalog, wrong_source, "E_BINDING"),
            ):
                state = {"consumed_receipts": {}}
                before = MODULE.canonical_bytes(state)
                with self.subTest(replay_challenge=code):
                    with self.assertRaises(MODULE.ReviewError) as ctx:
                        MODULE.verify_portable_bundle(
                            challenged_bundle, anchor, catalog=challenged_catalog,
                            source_registry=challenged_source, skill_root=SKILL_ROOT,
                            now=now, replay_state=state,
                        )
                    self.assertEqual(code, ctx.exception.code)
                    self.assertEqual(before, MODULE.canonical_bytes(state))

            state = {"consumed_receipts": {}}
            MODULE.verify_portable_bundle(
                bundle, anchor, catalog=catalog, source_registry=sources,
                skill_root=SKILL_ROOT, now=now, replay_state=state,
            )
            committed = MODULE.canonical_bytes(state)
            # Repeating the identical operation is deterministic and adds no
            # effect; a different operation is still prohibited.
            MODULE.verify_portable_bundle(
                bundle, anchor, catalog=catalog, source_registry=sources,
                skill_root=SKILL_ROOT, now=now, replay_state=state,
            )
            self.assertEqual(committed, MODULE.canonical_bytes(state))
            with self.assertRaises(MODULE.ReviewError) as ctx:
                MODULE.commit_replay_use(state, built["receipt_id"], "different-operation")
            self.assertEqual("E_REPLAY", ctx.exception.code)


if __name__ == "__main__":
    unittest.main()
