from __future__ import annotations

import sys
from pathlib import Path

ROUTER_SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "company-os" / "assign-capability-skills" / "scripts"
sys.path.insert(0, str(ROUTER_SCRIPTS))

#!/usr/bin/env python3
from copy import deepcopy
import unittest

from capability_index_contract_v2 import (
    ContractError,
    deterministic_context_units,
    dnf_matches,
    validate_snapshot,
    validate_task,
    validate_row,
)
from route_capability_bundle_v2 import RouteError, eligibility_errors, route, row, task


SHA = "a" * 64
COMMIT = "b" * 40


def evidence() -> dict:
    return {
        "status": "pass",
        "evidence_class": "independent_review",
        "enforcement": "hard_gate",
        "reviewer_or_issuer": "company-os-reviewer",
        "observed_at": "2026-08-05T00:00:00Z",
        "evidence_sha256": SHA,
    }


def publisher_identity() -> dict:
    value = evidence()
    value["publisher_id"] = "example"
    return value


def contract_row() -> dict:
    return {
        "$schema": "company-os.capability-index-row.v2",
        "schema_version": 2,
        "capability_id": "example/report-producer",
        "capability_version": "1.0.0",
        "aliases": [],
        "capability_kind": "artifact_producer",
        "source": {
            "requested_url": "https://github.com/example/report-producer",
            "redirect_chain": [],
            "canonical_forge_id": "example/report-producer",
            "canonical_url": "https://github.com/example/report-producer",
            "source_commit": COMMIT,
            "source_tree": COMMIT,
            "source_commit_at": "2026-08-04T00:00:00Z",
            "upstream_forge_id": None,
            "upstream_url": None,
            "upstream_commit": None,
            "observed_at": "2026-08-05T00:00:00Z",
        },
        "materialization": {
            "mode": "reviewed_wrapper",
            "transform_id": "company-os-advisory-wrapper",
            "transform_version": "1",
            "transform_receipt_sha256": SHA,
            "original_entrypoint_sha256": SHA,
            "materialized_package_sha256": SHA,
            "entrypoint_resource_id": "entrypoint",
            "companion_policy": "closed",
            "resources": [{
                "resource_id": "entrypoint",
                "path": "skills/example/SKILL.md",
                "kind": "entrypoint",
                "sha256": SHA,
                "bytes": 100,
                "load_when": [[{"field": "intents", "op": "contains", "value": "report"}]],
                "license_spdx": "MIT",
                "license_evidence_path": "LICENSE",
                "redistribution": "allowed",
            }],
        },
        "classification": {
            "domains": ["research"],
            "produces_artifacts": ["report"],
            "reviews_artifacts": [],
            "consumes_artifacts": [],
            "reviewer_capabilities": [],
            "lifecycle_phases": ["synthesize"],
            "intents": ["report"],
            "named_technologies": [],
            "modalities": ["text"],
        },
        "activation": {
            "roles": ["worker"],
            "positive_trigger_dnf": [[{"field": "intents", "op": "contains", "value": "report"}]],
            "negative_triggers": [],
            "required_permissions": [],
            "prerequisites": [],
            "requires_capability_ids": [],
            "provides_prerequisite_ids": [],
            "network_mode": "none",
            "allowed_hosts": [],
            "data_egress": "none",
            "sensitivity_ceiling": "public",
            "side_effects": ["advisory"],
            "controller_effect": "none",
            "conflicts": [],
            "composes_before": [],
            "composes_after": [],
        },
        "trust": {
            "state": "approved",
            "provenance_tier": "vendored_reviewed",
            "publisher_identity": publisher_identity(),
            "source_lineage": evidence(),
            "integrity": evidence(),
            "signature": evidence(),
            "scan": evidence(),
            "human_review": evidence(),
            "risk_flags": [],
        },
        "freshness": {
            "last_revalidated_at": "2026-08-05T00:00:00Z",
            "stale_after_days": 90,
            "next_review_at": "2026-11-03T00:00:00Z",
            "supersedes": [],
        },
        "evaluation": {
            "evaluation_class": "independent_scenario",
            "independence": "independent",
            "enforcement": "hard_gate",
            "suite_version": "1",
            "suite_ids": ["router-suite"],
            "scenario_ids": ["n31"],
            "passed": 1,
            "failed": 0,
            "last_run_at": "2026-08-05T00:00:00Z",
            "stale_after_days": 30,
            "evidence_sha256": SHA,
        },
        "context": {
            "summary": "Produce one bounded report.",
            "context_accounting_id": "company-os-utf8-byteceil4-v1",
            "metadata_context_units": 20,
            "max_loaded_bytes": 100,
            "max_loaded_context_units": 25,
            "load_policy": "metadata_then_closed_resources",
            "section_index": [],
        },
    }


def contract_task() -> dict:
    return {
        "$schema": "company-os.capability-routing-task.v2",
        "schema_version": 2,
        "program_id": "program",
        "packet_id": "packet",
        "parent_packet_id": "parent",
        "role": "worker",
        "controller_id": "controller",
        "decision_as_of": "2026-08-05T00:00:00Z",
        "coverage_atoms": ["artifact:produce:report"],
        "typed_features": {
            "domains": ["research"],
            "artifact_produces": ["report"],
            "artifact_reviews": [],
            "named_technologies": [],
            "lifecycle_phases": ["synthesize"],
            "intents": ["report"],
            "reviewer_capabilities": [],
        },
        "authority": {
            "allowed_permissions": [],
            "available_prerequisites": [],
            "network_mode": "none",
            "allowed_hosts": [],
            "data_egress_ceiling": "none",
            "sensitivity_ceiling": "public",
            "write_scopes": ["outputs"],
            "allowed_side_effects": ["advisory"],
            "license_use_mode": "internal_use",
        },
        "policy": {
            "risk_tier": "low",
            "max_freshness_days": 180,
            "minimum_evaluation_class": "static_contract",
            "minimum_evaluation_independence": "maintainer",
            "minimum_evaluation_enforcement": "advisory",
            "max_skills": 4,
            "max_closed_resource_bytes": 49152,
            "context_accounting_id": "company-os-utf8-byteceil4-v1",
            "max_context_cost_units": 12288,
        },
        "prohibitions": ["deploy"],
        "mandatory_requirements": ["produce-report"],
    }


def contract_snapshot() -> dict:
    return {
        "$schema": "company-os.capability-index-snapshot.v2",
        "schema_version": 2,
        "policy_version": "2",
        "generated_at": "2026-08-05T00:00:00Z",
        "source_pins": [{
            "source_id": "example",
            "canonical_forge_id": "example/report-producer",
            "source_commit": COMMIT,
            "source_tree": COMMIT,
            "observed_at": "2026-08-05T00:00:00Z",
        }],
        "rows": [contract_row()],
        "inverted_indices": {"artifact:produce:report": ["example/report-producer"]},
        "snapshot_sha256": SHA,
    }


class RouterReferenceTests(unittest.TestCase):
    def test_contract_validator_accepts_exact_row(self):
        validate_row(contract_row())

    def test_task_and_snapshot_contracts_accept_exact_fixtures(self):
        validate_task(contract_task())
        validate_snapshot(contract_snapshot())

    def test_trigger_comparison_is_nfc_casefolded_and_not_substring(self):
        dnf = [[{"field": "intents", "op": "contains", "value": "CAFÉ"}]]
        self.assertTrue(dnf_matches({"intents": ["cafe\u0301"]}, dnf))
        self.assertFalse(dnf_matches({"intents": ["café-report"]}, dnf))

    def test_side_effects_are_composable_subset_not_total_order(self):
        candidate = row("multi", ["artifact:produce:report"], side_effects=["external_read", "spend"])
        self.assertIn("E_SIDE_EFFECT_WIDENING", eligibility_errors(task(allowed_side_effects=["external_read"]), candidate))
        self.assertNotIn("E_SIDE_EFFECT_WIDENING", eligibility_errors(task(allowed_side_effects=["external_read", "spend"]), candidate))

    def test_positive_zero_coverage_dependency_is_selectable_and_counted(self):
        rows = [
            row("producer", ["artifact:produce:report"], requires=["helper"]),
            row("helper", [], closed_bytes=1),
        ]
        self.assertEqual(route(task(), rows)["selected"], ["helper", "producer"])
        with self.assertRaisesRegex(RouteError, "E_NO_VALID_BUNDLE"):
            route(task(max_skills=1), rows)

    def test_semantic_tie_requires_manager_and_is_input_order_invariant(self):
        rows = [row("alpha", ["artifact:produce:report"]), row("beta", ["artifact:produce:report"])]
        first = route(task(), rows)
        second = route(task(), list(reversed(rows)))
        self.assertTrue(first["decision_required"])
        self.assertEqual(first, second)

    def test_smallest_sufficient_precedes_specificity(self):
        rows = [
            row("small", ["artifact:produce:report", "domain:research"], specificity=1),
            row("domain", ["domain:research"], specificity=100),
            row("artifact", ["artifact:produce:report"], specificity=100),
        ]
        self.assertEqual(route(task(atoms=["artifact:produce:report", "domain:research"]), rows)["selected"], ["small"])

    def test_deterministic_context_cost_accounting(self):
        self.assertEqual(deterministic_context_units(0), 0)
        self.assertEqual(deterministic_context_units(1), 1)
        self.assertEqual(deterministic_context_units(4), 1)
        self.assertEqual(deterministic_context_units(5), 2)

    def test_required_value_types_fail_closed(self):
        mutations = []
        value = contract_row(); value["materialization"]["resources"][0]["sha256"] = None; mutations.append(value)
        value = contract_row(); value["source"]["observed_at"] = 17; mutations.append(value)
        value = contract_row(); value["evaluation"]["passed"] = -1; mutations.append(value)
        value = contract_row(); value["context"]["section_index"] = {"oops": True}; mutations.append(value)
        value = contract_row(); value["trust"]["publisher_identity"] = {"oops": True}; mutations.append(value)
        for invalid in mutations:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ContractError):
                    validate_row(invalid)

    def test_prerequisite_types_fail_closed(self):
        value = contract_row()
        value["activation"]["prerequisites"] = [{
            "prerequisite_id": "runtime", "kind": "runtime", "constraint": {},
            "availability_source": {}, "required": "yes",
        }]
        with self.assertRaises(ContractError):
            validate_row(value)

    def test_transitive_prerequisite_and_reviewer_coverage(self):
        rows = [
            row("producer", ["artifact:produce:report"], requires=["runtime-helper"]),
            row("runtime-helper", [], prerequisites=["python"]),
            row("reviewer", ["artifact:review:report", "review:independent"]),
        ]
        routed = route(task(
            atoms=["artifact:produce:report", "artifact:review:report", "review:independent"],
            available_prerequisites=["python"],
        ), rows)
        self.assertEqual(routed["selected"], ["producer", "reviewer", "runtime-helper"])
        with self.assertRaisesRegex(RouteError, "E_NO_VALID_BUNDLE"):
            route(task(
                atoms=["artifact:produce:report", "artifact:review:report", "review:independent"],
                available_prerequisites=[],
            ), rows)

    def test_n31_no_preeligibility_cap_keeps_candidate_33(self):
        rows = [row(f"bad-{i:02d}", ["artifact:produce:report"], trust="quarantine") for i in range(32)]
        rows.append(row("valid-33", ["artifact:produce:report"]))
        self.assertEqual(route(task(), rows)["selected"], ["valid-33"])

    def test_n32_closed_transitive_resources_fail_bytes_before_load(self):
        rows = [
            row("producer", ["artifact:produce:report"], requires=["helper"], closed_bytes=100),
            row("helper", [], closed_bytes=49053),
        ]
        with self.assertRaisesRegex(RouteError, "E_CONTEXT_BYTES"):
            route(task(), rows)

    def test_n33_dependency_cycle_has_stable_code(self):
        rows = [
            row("a", ["artifact:produce:report"], requires=["b"]),
            row("b", [], requires=["c"]),
            row("c", [], requires=["a"]),
        ]
        with self.assertRaisesRegex(RouteError, "E_DEPENDENCY_CYCLE"):
            route(task(), rows)

    def test_n34_exact_keys_and_evaluation_enforcement(self):
        extra = contract_row()
        extra["unexpected"] = True
        with self.assertRaisesRegex(ContractError, "E_SCHEMA_EXACT_KEYS"):
            validate_row(extra)
        missing = contract_row()
        del missing["evaluation"]["enforcement"]
        with self.assertRaisesRegex(ContractError, "E_SCHEMA_EXACT_KEYS"):
            validate_row(missing)

    def test_n35_transform_or_symlink_escape_fails_closure(self):
        candidate = row("escape", ["artifact:produce:report"], materialization_closure_ok=False)
        self.assertIn("E_MATERIALIZATION_CLOSURE", eligibility_errors(task(), candidate))
        invalid = contract_row()
        invalid["materialization"]["resources"][0]["path"] = "../outside.md"
        with self.assertRaisesRegex(ContractError, "E_MATERIALIZATION_CLOSURE"):
            validate_row(invalid)

    def test_n36_hidden_controller_in_original_bytes_is_ineligible(self):
        candidate = row("hidden", ["artifact:produce:report"], hidden_controller_effect=True)
        self.assertIn("E_HIDDEN_CONTROLLER_EFFECT", eligibility_errors(task(), candidate))

    def test_n37_evaluation_receipt_digest_and_freshness_are_hard_gates(self):
        receipt = row("receipt", ["artifact:produce:report"], evaluation_receipt_ok=False)
        stale = row("stale-eval", ["artifact:produce:report"], evaluation_fresh=False)
        self.assertIn("E_EVALUATION_RECEIPT", eligibility_errors(task(), receipt))
        self.assertIn("E_EVALUATION_FRESHNESS", eligibility_errors(task(), stale))

    def test_n38_resource_license_overrides_root_license(self):
        candidate = row("mixed-license", ["artifact:produce:report"], resource_license_ok=False)
        self.assertIn("E_LICENSE_RESOURCE_CONFLICT", eligibility_errors(task(), candidate))

    def test_n39_bound_decision_time_drives_freshness(self):
        candidate = row("fresh", ["artifact:produce:report"], last_revalidated_at="2026-08-04T00:00:00Z")
        bound = task(decision_as_of="2026-08-05T00:00:00Z", max_freshness_days=1)
        self.assertEqual(route(bound, [candidate]), route(deepcopy(bound), [deepcopy(candidate)]))
        self.assertIn("E_FRESHNESS", eligibility_errors(task(decision_as_of="2026-08-06T00:00:00Z", max_freshness_days=1), candidate))

    def test_n40_host_allowlist_and_egress_are_independent_gates(self):
        candidate = row(
            "remote", ["artifact:produce:report"], network_mode="allowlisted_read",
            allowed_hosts=["api.example.com"], data_egress="content",
        )
        errors = eligibility_errors(task(network_mode="allowlisted_read", allowed_hosts=["docs.example.com"]), candidate)
        self.assertIn("E_HOST_ALLOWLIST", errors)
        self.assertIn("E_DATA_EGRESS", errors)

    def test_n41_redirect_identity_drift_is_ineligible(self):
        candidate = row("redirect", ["artifact:produce:report"], source_redirect_ok=False)
        self.assertIn("E_SOURCE_REDIRECT_DRIFT", eligibility_errors(task(), candidate))

    def test_n42_any_bound_materialization_digest_drift_is_ineligible(self):
        candidate = row("drift", ["artifact:produce:report"], materialization_digest_ok=False)
        self.assertIn("E_MATERIALIZATION_DRIFT", eligibility_errors(task(), candidate))


if __name__ == "__main__":
    unittest.main()
