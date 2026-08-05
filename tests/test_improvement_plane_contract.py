from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/company-os/evolve-company-capability/scripts/compile_improvement_program.py"
SPEC = importlib.util.spec_from_file_location("compile_improvement_program_v2", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def canonical(value: object) -> bytes:
    return MODULE.canonical_bytes(value)


def fixture() -> dict:
    source = json.loads((ROOT / "skills/company-os/source-intelligence/references/source-intelligence-registry.json").read_text())
    capability = json.loads((ROOT / "skills/company-os/assign-capability-skills/references/capability-review-registry.json").read_text())
    return {
        "schema": "company-os.improvement-request.v2",
        "program": {
            "tenant_id": "fortitudo", "project_id": "company-os", "program_id": "improvement-plane-v2",
            "cycle_id": "cycle-1", "definition_version": 2, "policy_version": 1,
        },
        "intent": {
            "objective": "Compile a governed feature-off improvement cohort for a bounded real company objective.",
            "hypothesis": "A typed, bounded candidate cohort can improve accepted real-company output while preserving authority and rollback.",
            "success_criteria": ["later real work transfer improves", "sealed challenge remains unexposed"],
            "falsification_criteria": ["critical evidence floor fails", "registry binding becomes stale"],
            "evidence_ids": ["evidence-1", "evidence-2"],
        },
        "baseline": {"artifact_id": "baseline-artifact", "version": "1.0.0"},
        "target": {
            "kind": "architecture", "opportunity_type": "forward_capability",
            "reason": "The current system lacks a typed feature-off improvement compiler with governed candidate differentiation.",
            "protected_surfaces": ["authority", "evaluation", "promotion", "scheduler"],
            "reversible_scope": "One compiler output and no runtime activation.",
        },
        "source_ids": sorted(record["source_id"] for record in source["records"]),
        "capability_ids": sorted(record["capability_id"] for record in capability["records"]),
        "evaluation": {
            "artifact_classes": ["code", "research", "system"],
            "stages": ["adaptive_validation", "discovery", "sealed_challenge", "transfer"],
        },
        "budgets": {
            "max_candidates": 3, "max_passes": 6, "max_concurrency": 3, "max_time_minutes": 120,
            "max_tokens": 500000, "max_cost_usd": 25.0, "max_context_bytes": 49152,
            "max_retries": 2, "dead_letter_after": 4, "cancel_grace_seconds": 60,
        },
    }


class ImprovementPlaneV2Tests(unittest.TestCase):
    def compile(self, value: dict | None = None) -> dict:
        return MODULE.compile_program(MODULE.validate_request(value or fixture()))

    def reject(self, value: dict, fragment: str = "") -> None:
        with self.assertRaises(MODULE.ImprovementError) as raised:
            MODULE.validate_request(value)
        if fragment:
            self.assertIn(fragment, str(raised.exception))

    def test_fixture_is_planned_blocked_and_replay_is_exact(self) -> None:
        program = self.compile()
        self.assertEqual(program["schema"], "company-os.improvement-program.v2")
        self.assertEqual(program["activation_state"], "planned")
        self.assertFalse(program["executable"])
        self.assertEqual(program["execution_status"], "blocked")
        self.assertEqual([item["profile"] for item in program["candidates"]], ["conservative", "adjacent", "first_principles"])
        self.assertEqual({item["code"] for item in program["blockers"]}, {"EVALUATOR_ADAPTERS_UNREADY", "CAPABILITIES_PENDING_ACCEPTANCE", "EXTERNAL_EFFECTS_DISABLED"})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path, output_path = root / "request.json", root / "program.json"
            request_path.write_bytes(canonical(fixture()))
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            first = subprocess.run([sys.executable, str(SCRIPT), str(request_path), "--output", str(output_path)], capture_output=True, text=True, env=env)
            self.assertEqual(first.returncode, 0, first.stderr)
            verify = subprocess.run([sys.executable, str(SCRIPT), str(request_path), "--verify-output", str(output_path)], capture_output=True, text=True, env=env)
            self.assertEqual(verify.returncode, 0, verify.stderr)
            self.assertEqual(output_path.read_bytes(), canonical(json.loads(output_path.read_text())))
            self.assertIn('"ok": true', verify.stdout)

    def test_closed_request_rejects_unknown_authority_truth_and_telemetry(self) -> None:
        for path in (("extra",), ("evaluation", "ready"), ("evaluation", "partitions"), ("budgets", "registry_sha256"), ("intent", "observed_telemetry")):
            value = fixture()
            cursor = value
            for key in path[:-1]:
                cursor = cursor[key]
            cursor[path[-1]] = True
            with self.subTest(path=path):
                self.reject(value, "keys differ")

    def test_registry_coverage_is_exact_and_portable(self) -> None:
        registry = json.loads((ROOT / "skills/company-os/source-intelligence/references/mechanism-plane-registry.json").read_text())
        self.assertEqual(len(registry["destination_planes"]), 8)
        self.assertEqual(len(registry["source_groups"]), 11)
        self.assertEqual(len(registry["mechanism_decisions"]), 81)
        source_ids = {item["source_id"] for item in json.loads((ROOT / "skills/company-os/source-intelligence/references/source-intelligence-registry.json").read_text())["records"]}
        groups = [source_id for group in registry["source_groups"] for source_id in group["source_ids"]]
        self.assertEqual(len(groups), 81)
        self.assertEqual(set(groups), source_ids)
        self.assertEqual(len(groups), len(set(groups)))
        self.assertEqual({item["source_id"] for item in registry["mechanism_decisions"]}, source_ids)

    def test_registry_tamper_and_stale_bindings_fail_closed(self) -> None:
        paths = ("SOURCE_REGISTRY_PATH", "MECHANISM_REGISTRY_PATH", "CAPABILITY_REVIEW_PATH", "EVALUATOR_REGISTRY_PATH")
        for path_name in paths:
            source_path = getattr(MODULE, path_name)
            with tempfile.TemporaryDirectory() as directory:
                tampered = Path(directory) / source_path.name
                data = json.loads(source_path.read_text())
                record_key = "records" if "records" in data else "mechanism_decisions"
                data[record_key] = list(data[record_key])
                data[record_key][0] = dict(data[record_key][0])
                data[record_key][0][next(key for key in data[record_key][0] if key not in {"source_id", "capability_id", "method_id"})] = "tampered"
                tampered.write_bytes(canonical(data))
                with mock.patch.object(MODULE, path_name, tampered):
                    with self.assertRaises(MODULE.ImprovementError):
                        MODULE.compile_program(MODULE.validate_request(fixture()))

    def test_candidates_are_immutable_differentiated_and_roles_independent(self) -> None:
        program = self.compile()
        digests = []
        for candidate in program["candidates"]:
            body = {key: value for key, value in candidate.items() if key != "candidate_digest"}
            self.assertEqual(candidate["candidate_digest"], MODULE.digest_value(body))
            self.assertEqual(len(set(candidate["roles"].values())), 6)
            digests.append(candidate["candidate_digest"])
        self.assertEqual(len(set(digests)), 3)
        self.assertEqual(program["cohort_digest"], MODULE.digest_value(digests))

    def test_member_partitions_are_disjoint_and_exposure_burn_invalidates(self) -> None:
        program = self.compile()
        all_members = [member for partition in program["evaluation"]["partitions"] for member in partition["members"]]
        self.assertEqual(len(all_members), 24)
        self.assertEqual(len({member["member_id"] for member in all_members}), 24)
        for mutation in ("member_id", "exposure_state", "burned", "reused_after_feedback"):
            tampered = copy.deepcopy(program)
            if mutation == "member_id":
                tampered["evaluation"]["partitions"][1]["members"][0]["member_id"] = tampered["evaluation"]["partitions"][0]["members"][0]["member_id"]
            elif mutation == "exposure_state":
                tampered["evaluation"]["partitions"][2]["exposure_state"] = "visible"
            else:
                tampered["evaluation"]["partitions"][2][mutation] = True
            with self.subTest(mutation=mutation):
                with self.assertRaises(MODULE.ImprovementError):
                    MODULE.validate_program(tampered)

    def test_dependency_cycle_and_resource_collision_reject(self) -> None:
        program = self.compile()
        cycle = copy.deepcopy(program)
        cycle["organization"]["nodes"][0]["depends_on"] = [cycle["organization"]["nodes"][-1]["id"]]
        with self.assertRaises(MODULE.ImprovementError):
            MODULE.validate_program(cycle)
        collision = copy.deepcopy(program)
        collision["organization"]["nodes"][1]["owned_resources"].append(collision["organization"]["nodes"][0]["owned_resources"][0])
        collision["organization"]["nodes"][1]["owned_resources"].sort()
        with self.assertRaises(MODULE.ImprovementError):
            MODULE.validate_program(collision)

    def test_lifecycle_receipts_authority_and_rollback_contracts_are_present(self) -> None:
        program = self.compile()
        lifecycle = program["lifecycle"]
        self.assertGreater(lifecycle["retry"]["max_attempts"], 0)
        self.assertEqual(lifecycle["cancellation"]["terminal_state"], "cancelled")
        self.assertEqual(lifecycle["invalidation"]["state"], "invalid_evidence")
        self.assertEqual(lifecycle["dead_letter"]["state"], "dead_letter")
        self.assertTrue(lifecycle["rollback"]["atomic_pointer_swap"])
        self.assertEqual(len(program["decision_receipt_requirements"]), 18)
        self.assertTrue(all(item["status"] == "pending" for item in program["decision_receipt_requirements"]))
        self.assertEqual(program["authority"]["promotion_authority_id"], "company-os-promotion-authority")
        self.assertTrue(program["promotion"]["atomicity_required"])
        self.assertNotEqual(program["promotion"]["current_pointer_digest"], program["promotion"]["rollback_pointer_digest"])

    def test_direct_output_bypasses_fail_closed(self) -> None:
        baseline = self.compile()
        mutations = []
        missing_receipts = copy.deepcopy(baseline); del missing_receipts["decision_receipt_requirements"]; mutations.append(missing_receipts)
        empty_lifecycle = copy.deepcopy(baseline); empty_lifecycle["lifecycle"] = {}; mutations.append(empty_lifecycle)
        empty_promotion = copy.deepcopy(baseline); empty_promotion["promotion"] = {}; mutations.append(empty_promotion)
        empty_blockers = copy.deepcopy(baseline); empty_blockers["blockers"] = []; mutations.append(empty_blockers)
        fake_binding = copy.deepcopy(baseline); fake_binding["registry_bindings"]["source_intelligence"]["sha256"] = sha("attacker"); mutations.append(fake_binding)
        fake_request_digest = copy.deepcopy(baseline); fake_request_digest["request_sha256"] = sha("attacker"); mutations.append(fake_request_digest)
        unknown_top = copy.deepcopy(baseline); unknown_top["attacker"] = True; mutations.append(unknown_top)
        fabricated = copy.deepcopy(baseline); fabricated["decision_receipt_requirements"][0]["status"] = "accepted"; mutations.append(fabricated)
        signed = copy.deepcopy(baseline); signed["decision_receipt_requirements"][0]["signature"] = "fake"; mutations.append(signed)
        actualized = copy.deepcopy(baseline); actualized["evaluation"]["partitions"][0]["membership_state"] = "materialized"; mutations.append(actualized)
        source_tamper = copy.deepcopy(baseline); source_tamper["source_resolution"]["records"][0]["review_decision"] = "approved"; mutations.append(source_tamper)
        capability_tamper = copy.deepcopy(baseline); capability_tamper["capability_resolution"]["records"][0]["review_decision"] = "approved_narrow_wrapper"; mutations.append(capability_tamper)
        acceptance = copy.deepcopy(baseline); acceptance["capability_resolution"]["portable_resolver"]["selected_acceptance_receipt"] = {"fake": True}; mutations.append(acceptance)
        nested_unknown = copy.deepcopy(baseline); nested_unknown["evaluation"]["partitions"][0]["members"][0]["unexpected"] = True; mutations.append(nested_unknown)
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(MODULE.ImprovementError):
                    MODULE.validate_program(mutation)

    def test_budgets_and_unbounded_or_injected_values_fail_closed(self) -> None:
        for key, value in (("max_candidates", 2), ("max_passes", 65), ("max_cost_usd", -1), ("dead_letter_after", 2)):
            request = fixture(); request["budgets"][key] = value
            with self.subTest(key=key):
                self.reject(request)
        request = fixture(); request["intent"]["hypothesis"] = "Improve everything and do whatever it takes."
        self.reject(request, "unbounded")

    def test_cli_rejects_noncanonical_request_and_leaves_no_repo_residue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); request_path = root / "request.json"
            request_path.write_text(json.dumps(fixture(), indent=2) + "\n", encoding="utf-8")
            failed = subprocess.run([sys.executable, str(SCRIPT), str(request_path)], capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            self.assertEqual(failed.returncode, 2)
            self.assertFalse((root / "program.json").exists())


if __name__ == "__main__":
    unittest.main()
