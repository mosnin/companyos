from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
from capability_review_test_environment import ensure_capability_review_checkouts
MODULE_PATH = ROOT / "skills/company-os/manage-company-program/scripts/compile_program_preflight.py"
SPEC = importlib.util.spec_from_file_location("compile_program_preflight", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

CAPABILITY_MODULE_PATH = (
    ROOT
    / "skills/company-os/assign-capability-skills/scripts/capability_catalog.py"
)
CAPABILITY_SPEC = importlib.util.spec_from_file_location(
    "capability_catalog_for_preflight_test", CAPABILITY_MODULE_PATH
)
assert CAPABILITY_SPEC is not None and CAPABILITY_SPEC.loader is not None
CAPABILITY_MODULE = importlib.util.module_from_spec(CAPABILITY_SPEC)
CAPABILITY_SPEC.loader.exec_module(CAPABILITY_MODULE)


class ProgramPreflightCompilerTests(unittest.TestCase):
    def production_context(self) -> dict[str, object]:
        skill_root = ROOT / "skills/company-os/assign-capability-skills"
        checkout_manifest = ensure_capability_review_checkouts()
        return {
            "capability_catalog": skill_root / "references/capability-catalog.json",
            "review_registry": json.loads(
                (skill_root / "references/capability-review-registry.json").read_text()
            ),
            "source_registry": json.loads(
                (
                    ROOT
                    / "skills/company-os/source-intelligence/references/source-intelligence-registry.json"
                ).read_text()
            ),
            "skill_root": skill_root,
            "checkout_manifest": json.loads(checkout_manifest.read_text()),
        }

    def portable_paths(self) -> tuple[Path, Path]:
        skill_root = (
            ROOT
            / "skills/company-os/manage-company-program/fixtures/portable-capability-v1/skill-root"
        )
        return skill_root.parent / "catalog.json", skill_root

    def fixture_paths(self, fixture: str) -> tuple[Path, Path, Path]:
        root = ROOT / "skills/company-os/manage-company-program/fixtures" / fixture
        return (
            root / "program-semantics.json",
            root / "host-capabilities.json",
            root / "work-definitions.json",
        )

    def load_fixture(self, fixture: str) -> tuple[dict, dict, dict]:
        paths = self.fixture_paths(fixture)
        return tuple(json.loads(path.read_text(encoding="utf-8")) for path in paths)  # type: ignore[return-value]

    def write_inputs(self, directory: Path, documents: tuple[dict, dict, dict]) -> tuple[Path, Path, Path]:
        directory.mkdir(parents=True, exist_ok=True)
        names = ("program-semantics.json", "host-capabilities.json", "work-definitions.json")
        paths = []
        for name, document in zip(names, documents):
            path = directory / name
            path.write_bytes(MODULE.canonical_bytes(document))
            paths.append(path)
        return tuple(paths)  # type: ignore[return-value]

    def synthetic_v2_documents(self, *, assignment_mutate=None, binding_mutate=None):
        documents, request, base_assignment, context = self.real_skill_documents()
        assignment = copy.deepcopy(base_assignment)
        if assignment_mutate is not None:
            assignment_mutate(assignment)
        binding = CAPABILITY_MODULE.assignment_binding_v2(assignment)
        if binding_mutate is not None:
            binding_mutate(binding)
        documents = tuple(copy.deepcopy(document) for document in documents)
        for document in documents:
            document["skill_assignment"] = copy.deepcopy(assignment)
            document["skill_assignment_binding"] = copy.deepcopy(binding)
        return documents, request, assignment, binding, context

    def real_skill_documents(self):
        documents = self.load_fixture("software-brokerage")
        semantics, capabilities, definitions = (copy.deepcopy(item) for item in documents)
        context = self.production_context()
        resolver_request = {
            "$schema": "company-os.capability-request.v2",
            "schema_version": 2,
            "request_id": "test-systematic-debugging-worker",
            "program_id": semantics["program_id"],
            "packet_id": "impl-platform-worker",
            "role": "worker",
            "phase": "implementation",
            "domains": ["software_engineering"],
            "required_artifact_kinds": ["implementation_artifact"],
            "required_permissions": ["fs_read", "fs_write", "process_test"],
            "prohibited_permissions": [],
            "required_effect_class": "project_local_write",
            "required_capability_ids": ["systematic-debugging"],
            "execution_order": ["systematic-debugging"],
            "allow_unproven_efficacy": True,
            "max_skills": 1,
            "max_skill_bytes": 100000,
        }
        assignment = CAPABILITY_MODULE.resolve_v2(
            context["capability_catalog"],
            resolver_request,
            context["review_registry"],
            context["source_registry"],
            context["skill_root"],
            context["checkout_manifest"],
        )
        definitions["work_items"][2]["skill_assignment"] = copy.deepcopy(assignment)
        definitions["work_items"][2]["skill_assignment_binding"] = CAPABILITY_MODULE.assignment_binding_v2(assignment)
        return (semantics, capabilities, definitions), resolver_request, assignment, context

    def test_brokerage_compiles_five_compact_packets_and_verifies(self) -> None:
        documents = self.load_fixture("software-brokerage")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "compiled"
            manifest = MODULE.compile_program(*self.write_inputs(Path(directory) / "inputs", documents), output)
            self.assertEqual(manifest["program_id"], "brokerage-platform-v1")
            self.assertEqual(len(manifest["manager_packets"]), 5)
            self.assertEqual(len(manifest["worker_packets"]), 5)
            verified = MODULE.verify_compiled(output, *self.write_inputs(Path(directory) / "verify-inputs", documents))
            self.assertEqual(manifest, verified)

    def test_saas_fixture_is_materially_different_and_valid(self) -> None:
        documents = self.load_fixture("saas-launch")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "compiled"
            manifest = MODULE.compile_program(*self.write_inputs(Path(directory) / "inputs", documents), output)
            self.assertEqual(manifest["program_id"], "saas-launch-v1")
            self.assertEqual(len(manifest["manager_packets"]), 3)
            self.assertEqual(len(manifest["worker_packets"]), 3)

    def test_identical_inputs_produce_byte_identical_trees(self) -> None:
        documents = self.load_fixture("software-brokerage")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_paths = self.write_inputs(root / "inputs", documents)
            one = root / "one"
            two = root / "two"
            MODULE.compile_program(*input_paths, one)
            MODULE.compile_program(*input_paths, two)
            files_one = {path.relative_to(one): path.read_bytes() for path in one.rglob("*") if path.is_file()}
            files_two = {path.relative_to(two): path.read_bytes() for path in two.rglob("*") if path.is_file()}
            self.assertEqual(files_one, files_two)

    def test_duplicate_deliverable_is_rejected(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad_definitions = copy.deepcopy(definitions)
        bad_definitions["work_items"][1]["deliverables"][0] = bad_definitions["work_items"][0]["deliverables"][0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad_definitions)), root / "output")
            self.assertEqual(caught.exception.code, "E_DUPLICATE_DELIVERABLE")

    def test_duplicate_required_capability_is_rejected(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(capabilities)
        bad["capabilities"][1]["capability_id"] = bad["capabilities"][0]["capability_id"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, bad, definitions)), root / "output")
            self.assertEqual(caught.exception.code, "E_DUPLICATE_CAPABILITY")

    def test_unknown_alias_is_rejected(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][0]["assigned_model"] = "missing-alias"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")
            self.assertEqual(caught.exception.code, "E_ALIAS_UNKNOWN")

    def test_alias_collision_is_rejected(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(capabilities)
        bad["capabilities"][1]["aliases"] = [bad["capabilities"][0]["aliases"][0]]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, bad, definitions)), root / "output")
            self.assertEqual(caught.exception.code, "E_ALIAS_COLLISION")

    def test_unavailable_spreadsheet_is_rejected(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][0]["required_capabilities"] = ["artifact_spreadsheet"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")
            self.assertEqual(caught.exception.code, "E_CAPABILITY_UNAVAILABLE")

    def test_ancestor_writer_scope_is_rejected(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][2]["writable_paths"] = ["src"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")
            self.assertEqual(caught.exception.code, "E_WRITE_SCOPE")

    def test_overlapping_writer_scope_is_rejected(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][3]["writable_paths"] = bad["work_items"][2]["writable_paths"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")
            self.assertEqual(caught.exception.code, "E_WRITE_SCOPE")

    def test_mutated_packet_is_rejected_by_verify(self) -> None:
        documents = self.load_fixture("software-brokerage")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write_inputs(root / "inputs", documents)
            output = root / "compiled"
            MODULE.compile_program(*paths, output)
            packet = next((output / "workers").glob("*.json"))
            value = json.loads(packet.read_text())
            value["instructions"] = "tampered"
            packet.write_bytes(MODULE.canonical_bytes(value))
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.verify_compiled(output, *paths)
            self.assertEqual(caught.exception.code, "E_PACKET_DIGEST")

    def test_ui_signal_without_explicit_domain_fails_closed(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][2]["required_capabilities"] = ["frontend_implementation"]
        bad["work_items"][2]["ui_domains"] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")
            self.assertEqual(caught.exception.code, "E_UI_DOMAIN_REQUIRED")

    def test_ui_source_extension_without_explicit_domain_fails_closed(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][2]["source_extensions"] = ["tsx"]
        bad["work_items"][2]["ui_domains"] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")
            self.assertEqual(caught.exception.code, "E_UI_DOMAIN_REQUIRED")

    def test_ui_domain_without_quality_capability_fails_closed(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][2]["ui_domains"] = ["web"]
        bad["work_items"][2]["required_capabilities"] = ["frontend_implementation"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")
            self.assertEqual(caught.exception.code, "E_UI_QUALITY_CAPABILITY")

    def test_duplicate_ui_domain_is_rejected(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][2]["ui_domains"] = ["web", "web"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")
            self.assertEqual(caught.exception.code, "E_ARRAY")

    def test_valid_ui_lane_binds_domain_and_quality_capability_into_packets(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        good = copy.deepcopy(definitions)
        good["work_items"][2]["ui_domains"] = ["web"]
        good["work_items"][2]["required_capabilities"] = ["frontend_implementation", "ui_design_quality"]
        good["work_items"][2]["source_extensions"] = ["tsx"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, good)), root / "output")
            worker_path = root / "output" / manifest["worker_packets"][2]["path"]
            worker = json.loads(worker_path.read_text())
            self.assertEqual(worker["ui_domains"], ["web"])
            self.assertEqual(worker["required_capabilities"], ["frontend_implementation", "ui_design_quality"])

    def test_ui_worker_requires_ui_classified_parent_manager(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][2]["ui_domains"] = ["web"]
        bad["work_items"][2]["required_capabilities"] = ["frontend_implementation", "ui_design_quality"]
        bad["work_items"][2]["source_extensions"] = ["tsx"]
        bad["work_items"][1]["ui_domains"] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")
            self.assertEqual(caught.exception.code, "E_UI_PARENT")

    def test_prohibited_terms_are_rejected_in_labels_and_oracle_probes(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][0]["title"] = "Perform forbidden production action"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")
            self.assertEqual(caught.exception.code, "E_PROHIBITED_TERM")

    def test_whitespace_only_normalized_oracle_probe_is_rejected(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][0]["oracle_probes"] = ["   "]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")
            self.assertEqual(caught.exception.code, "E_STRING")

    def test_prohibition_role_applicability_is_enforced(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][0]["prohibitions"] = ["worker-only-prohibition"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")
            self.assertEqual(caught.exception.code, "E_PROHIBITION_ROLE")

    def test_unbound_packet_field_and_extra_packet_are_rejected(self) -> None:
        documents = self.load_fixture("software-brokerage")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write_inputs(root / "inputs", documents)
            output = root / "compiled"
            MODULE.compile_program(*paths, output)
            packet_path = next((output / "workers").glob("*.json"))
            packet = json.loads(packet_path.read_text())
            packet["extra"] = True
            packet_path.write_bytes(MODULE.canonical_bytes(packet))
            with self.assertRaises(MODULE.PreflightError):
                MODULE.verify_compiled(output, *paths)

    def test_verify_requires_all_three_bound_sources(self) -> None:
        documents = self.load_fixture("software-brokerage")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write_inputs(root / "inputs", documents)
            output = root / "compiled"
            MODULE.compile_program(*paths, output)
            for index in range(3):
                args = list(paths)
                args[index] = root / "missing.json"
                with self.assertRaises(MODULE.PreflightError):
                    MODULE.verify_compiled(output, *args)

    def test_constant_ceiling_drift_is_rejected(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(semantics)
        bad["constants"]["manager_span_ceiling"] = 999
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError):
                MODULE.compile_program(*self.write_inputs(root / "inputs", (bad, capabilities, definitions)), root / "output")

    def test_unknown_keys_and_unsupported_constant_types_are_rejected(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(semantics)
        bad["unknown"] = True
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError):
                MODULE.compile_program(*self.write_inputs(root / "inputs", (bad, capabilities, definitions)), root / "output")
        bad = copy.deepcopy(semantics)
        bad["constants"]["manager_span_ceiling"] = {"bad": True}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError):
                MODULE.compile_program(*self.write_inputs(root / "inputs", (bad, capabilities, definitions)), root / "output")

    def test_signed_representation_agreement_cannot_be_relabelled_as_closing(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][0]["title"] = "Signed representation agreement closing"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError):
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")

    def test_missing_or_malformed_locator_is_rejected(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        for locator in (None, {}, {"kind": "bad"}):
            bad = copy.deepcopy(definitions)
            if locator is None:
                bad["work_items"][0].pop("artifact_locator", None)
            else:
                bad["work_items"][0]["artifact_locator"] = locator
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaises(MODULE.PreflightError):
                    MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")

    def test_uncited_evidence_is_rejected(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][0]["evidence"][0].pop("citation", None)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError):
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")

    def test_child_capabilities_must_narrow_parent_slice(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][2]["required_capabilities"].append("extra-capability")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError):
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")

    def test_child_must_retain_every_parent_prohibition(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        bad = copy.deepcopy(definitions)
        bad["work_items"][2]["prohibitions"] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError):
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, bad)), root / "output")

    def test_worker_skill_authority_must_narrow_its_parent_manager(self) -> None:
        documents, _, assignment, context = self.real_skill_documents()
        semantics, capabilities, definitions = (copy.deepcopy(item) for item in documents)
        definitions["work_items"][2]["skill_assignment"] = copy.deepcopy(assignment)
        definitions["work_items"][2]["skill_assignment"]["permissions"] = ["fs_read", "fs_write", "process_test"]
        definitions["work_items"][2]["skill_assignment_binding"] = CAPABILITY_MODULE.assignment_binding_v2(definitions["work_items"][2]["skill_assignment"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError):
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, definitions)), root / "output", **context)

    def test_skill_host_requires_atomic_four_part_context(self) -> None:
        documents, _, _, context = self.real_skill_documents()
        semantics, capabilities, definitions = documents
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for missing in ("review_registry", "source_registry", "skill_root", "checkout_manifest"):
                bad_context = dict(context)
                bad_context.pop(missing)
                with self.subTest(missing=missing):
                    with self.assertRaises(MODULE.PreflightError):
                        MODULE.compile_program(*self.write_inputs(root / f"inputs-{missing}", (semantics, capabilities, definitions)), root / f"output-{missing}", **bad_context)

    def test_handcrafted_skill_bindings_are_rejected_without_resolver_records(self) -> None:
        documents = self.load_fixture("software-brokerage")
        semantics, capabilities, definitions = (copy.deepcopy(item) for item in documents)
        definitions["work_items"][2]["skill_assignment"] = {"fake": True}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError):
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, definitions)), root / "output")

    def test_skill_binding_rejects_unknown_packet_role_artifact_drift_and_required_capability_bypass(self) -> None:
        documents, _, assignment, context = self.real_skill_documents()
        mutations = [
            lambda value: value.update(packet_id="unknown-worker"),
            lambda value: value.update(role="manager"),
            lambda value: value.update(required_artifact_kinds=["wrong"]),
            lambda value: value.update(capability_ids=[]),
        ]
        for mutate in mutations:
            semantics, capabilities, definitions = (copy.deepcopy(item) for item in documents)
            bad = copy.deepcopy(assignment)
            mutate(bad)
            definitions["work_items"][2]["skill_assignment"] = bad
            definitions["work_items"][2]["skill_assignment_binding"] = CAPABILITY_MODULE.assignment_binding_v2(bad)
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaises(MODULE.PreflightError):
                    MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, definitions)), root / "output", **context)

    def test_skill_request_domains_and_permissions_are_bound_to_task_authority(self) -> None:
        documents, request, _, context = self.real_skill_documents()
        semantics, capabilities, definitions = (copy.deepcopy(item) for item in documents)
        assignment = CAPABILITY_MODULE.resolve_v2(
            context["capability_catalog"], request, context["review_registry"], context["source_registry"], context["skill_root"], context["checkout_manifest"]
        )
        definitions["work_items"][2]["skill_assignment"] = assignment
        definitions["work_items"][2]["skill_assignment_binding"] = CAPABILITY_MODULE.assignment_binding_v2(assignment)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, definitions)), root / "output", **context)

    def test_real_catalog_assignment_compiles_only_into_its_exact_worker_packet(self) -> None:
        documents, _, _, context = self.real_skill_documents()
        semantics, capabilities, definitions = documents
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = MODULE.compile_program(*self.write_inputs(root / "inputs", documents), root / "output", **context)
            worker_paths = [root / "output" / item["path"] for item in manifest["worker_packets"]]
            packets = [json.loads(path.read_text()) for path in worker_paths]
            exact = [packet for packet in packets if packet["packet_id"] == "impl-platform-worker"]
            self.assertEqual(len(exact), 1)
            self.assertIn("skill_assignment", exact[0])
            others = [packet for packet in packets if packet["packet_id"] != "impl-platform-worker"]
            self.assertTrue(all("skill_assignment" not in packet for packet in others))

    def test_real_catalog_manager_skill_isolated_to_exact_manager_packet(self) -> None:
        documents, _, assignment, context = self.real_skill_documents()
        semantics, capabilities, definitions = (copy.deepcopy(item) for item in documents)
        manager_assignment = copy.deepcopy(assignment)
        manager_assignment["packet_id"] = "impl-platform-manager"
        manager_assignment["role"] = "manager"
        definitions["work_items"][1]["skill_assignment"] = manager_assignment
        definitions["work_items"][1]["skill_assignment_binding"] = CAPABILITY_MODULE.assignment_binding_v2(manager_assignment)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError):
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, definitions)), root / "output", **context)

    def test_real_two_skill_worker_bundle_preserves_manager_execution_order(self) -> None:
        documents, request, _, context = self.real_skill_documents()
        semantics, capabilities, definitions = (copy.deepcopy(item) for item in documents)
        request = copy.deepcopy(request)
        request["required_capability_ids"] = []
        request["execution_order"] = []
        request["max_skills"] = 2
        assignment = CAPABILITY_MODULE.resolve_v2(
            context["capability_catalog"], request, context["review_registry"], context["source_registry"], context["skill_root"], context["checkout_manifest"]
        )
        definitions["work_items"][2]["skill_assignment"] = assignment
        definitions["work_items"][2]["skill_assignment_binding"] = CAPABILITY_MODULE.assignment_binding_v2(assignment)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, definitions)), root / "output", **context)

    def test_synthetic_accepted_v2_envelope_and_exact_rejections(self) -> None:
        documents, request, assignment, context = self.real_skill_documents()
        semantics, capabilities, definitions = documents
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            MODULE.compile_program(*self.write_inputs(root / "inputs", documents), root / "output", **context)

    def test_production_assignment_v2_cannot_downgrade_or_strip_review_binding(self) -> None:
        documents, _, assignment, context = self.real_skill_documents()
        semantics, capabilities, definitions = documents
        mutations = [
            lambda value: value.pop("review_binding", None),
            lambda value: value.update(schema_version=1),
        ]
        for mutate in mutations:
            bad = copy.deepcopy(assignment)
            mutate(bad)
            mutated_definitions = copy.deepcopy(definitions)
            mutated_definitions["work_items"][2]["skill_assignment"] = bad
            mutated_definitions["work_items"][2]["skill_assignment_binding"] = CAPABILITY_MODULE.assignment_binding_v2(bad)
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaises(MODULE.PreflightError):
                    MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, mutated_definitions)), root / "output", **context)

    def test_packet_id_collision_is_rejected_when_skill_assignments_exist(self) -> None:
        documents, _, _, context = self.real_skill_documents()
        semantics, capabilities, definitions = (copy.deepcopy(item) for item in documents)
        definitions["work_items"][3]["packet_id"] = definitions["work_items"][2]["packet_id"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MODULE.PreflightError):
                MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, definitions)), root / "output", **context)

    def test_legacy_packet_id_collision_remains_valid_without_skill_assignments(self) -> None:
        semantics, capabilities, definitions = self.load_fixture("software-brokerage")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            MODULE.compile_program(*self.write_inputs(root / "inputs", (semantics, capabilities, definitions)), root / "output")

    def test_rehashed_packet_and_manifest_are_rejected_against_sources(self) -> None:
        documents = self.load_fixture("software-brokerage")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write_inputs(root / "inputs", documents)
            output = root / "output"
            manifest = MODULE.compile_program(*paths, output)
            packet_path = output / manifest["worker_packets"][0]["path"]
            packet = json.loads(packet_path.read_text())
            packet["title"] = "tampered"
            packet_path.write_bytes(MODULE.canonical_bytes(packet))
            with self.assertRaises(MODULE.PreflightError):
                MODULE.verify_compiled(output, *paths)

    def test_portable_v1_producer_output_is_byte_identical_through_compile_and_verify(self) -> None:
        documents = self.load_fixture("software-brokerage")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write_inputs(root / "inputs", documents)
            output = root / "output"
            first = MODULE.compile_program(*paths, output)
            second = MODULE.verify_compiled(output, *paths)
            self.assertEqual(first, second)

    def test_portable_fixture_identity_marker_and_cli_boundaries(self) -> None:
        documents, _, _, context = self.real_skill_documents()
        catalog_path, skill_root = self.portable_paths()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.write_inputs(root / "inputs", documents)
            output = root / "output"
            MODULE.compile_program(*paths, output, **context)
            with self.assertRaises(SystemExit):
                with mock.patch("sys.argv", ["compile"]):
                    MODULE.main()

    def test_current_production_context_reaches_candidate_decision(self) -> None:
        context = self.production_context()
        documents, _, _, _ = self.real_skill_documents()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            MODULE.compile_program(*self.write_inputs(root / "inputs", documents), root / "output", **context)

    def test_independent_provenance_tamper_is_binding_error_and_context_is_unchanged(self) -> None:
        documents, _, _, _ = self.real_skill_documents()
        base_context = self.production_context()
        expected_codes = {
            "review_registry": "E_CAPABILITY_BINDING",
            "source_registry": "E_CAPABILITY_BINDING",
            "checkout_manifest": "E_BINDING",
        }
        for name in ("review_registry", "source_registry", "checkout_manifest"):
            context = copy.deepcopy(base_context)
            if name == "review_registry":
                context[name]["catalog_sha256"] = "0" * 64
            elif name == "source_registry":
                context[name]["registry_id"] = "tampered-source-registry"
            else:
                context[name]["sources"][0]["source_tree"] = "0" * 40
            before = copy.deepcopy(context)
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                paths = self.write_inputs(root, documents)
                with self.assertRaises(MODULE.PreflightError) as caught:
                    MODULE.compile_program(*paths, root / "output", **context)
                self.assertEqual(expected_codes[name], caught.exception.code)
                self.assertFalse((root / "output").exists())
            self.assertEqual(before, context)


if __name__ == "__main__":
    unittest.main()
