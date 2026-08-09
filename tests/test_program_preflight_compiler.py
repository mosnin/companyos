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
        assignment["$schema"] = "company-os.capability-assignment.v2"
        assignment["schema_version"] = 2
        assignment.update(
            {
                "review_registry_sha256": "a" * 64,
                "review_portable_bundle_sha256": "b" * 64,
                "review_acceptance_receipt_sha256": "c" * 64,
            }
        )
        assignment["skills"][0].update(
            {
                "review_id": "review-portable-review-v2",
                "review_sha256": "d" * 64,
                "review_phase": "verification",
                "review_effect_class": "no_effect",
                "review_provider_boundary": "fixture-provider",
                "review_consumes_artifact_kinds": ["fixture-request"],
                "review_produces_artifact_kinds": ["fixture-result"],
            }
        )
        if assignment_mutate is not None:
            assignment_mutate(assignment)
        assignment["binding"]["canonical_sha256"] = None
        assignment["binding"]["canonical_sha256"] = MODULE.canonical_digest(assignment)
        host = copy.deepcopy(documents[1])
        host_record = host["skill_assignments"][0]
        host_record["assignment"] = copy.deepcopy(assignment)
        capability = next(item for item in host["capabilities"] if item.get("capability_id") == "portable-review")
        binding = capability["skill_bindings"][0]
        skill = assignment["skills"][0]
        for key in MODULE.V2_REVIEW_ROOT_KEYS:
            if key in assignment:
                binding[key] = assignment[key]
        for key in MODULE.V2_REVIEW_SKILL_KEYS:
            if key in skill:
                binding[key] = copy.deepcopy(skill[key])
        binding["assignment_sha256"] = assignment["binding"]["canonical_sha256"]
        catalog = json.loads((self.portable_paths()[0]).read_text())
        binding["catalog_sha256"] = CAPABILITY_MODULE.canonical_digest(catalog)
        if binding_mutate is not None:
            binding_mutate(binding)
        documents = (documents[0], host, documents[2])
        expected = copy.deepcopy(assignment)
        contract = {
            "_production_catalog": lambda value: False,
            "validate_catalog": lambda value, root, verify_files=True, **kwargs: {
                "catalog_sha256": CAPABILITY_MODULE.canonical_digest(catalog)
            },
            "resolve_assignment": lambda *args, **kwargs: copy.deepcopy(expected),
            "validate_assignment": lambda value: None,
            "canonical_bytes": MODULE.canonical_bytes,
        }
        return documents, context, contract, assignment

    def compile_fixture(self, fixture: str, output: Path) -> dict:
        semantics, capabilities, definitions = self.fixture_paths(fixture)
        return MODULE.compile_program(semantics, capabilities, definitions, output)

    def verify_fixture(self, fixture: str, output: Path) -> dict:
        semantics, capabilities, definitions = self.fixture_paths(fixture)
        return MODULE.verify_output(output, semantics, capabilities, definitions)

    def assert_compile_code(self, fixture: str, mutate, expected_code: str) -> None:
        documents = self.load_fixture(fixture)
        mutate(documents)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            semantics, capabilities, definitions = self.write_inputs(root, documents)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(semantics, capabilities, definitions, root / "output")
            self.assertEqual(expected_code, caught.exception.code)
            self.assertIn(expected_code, str(caught.exception))

    def add_ui_design_capability(self, documents: tuple[dict, dict, dict]) -> None:
        documents[0]["required_capabilities"].append(
            {"capability_id": "ui_design_quality", "required": True}
        )
        documents[1]["capabilities"].append(
            {
                "capability_id": "ui_design_quality",
                "available": True,
                "runtime_id": "python3",
                "tool_locator": "workspace://skills/company-os/ui-design-quality",
                "runtime_locator": "runtime://fixture/python3",
            }
        )

    def add_bound_skill(
        self,
        documents: tuple[dict, dict, dict],
        capability_id: str,
        packet_id: str,
        role: str,
        digest_character: str,
    ) -> None:
        runtime = {
            "runtime_id": "company-os-skill-reference",
            "runtime_type": "codex_native_skill_reference",
            "available": True,
            "locator": "runtime://codex/native-skill",
        }
        if runtime not in documents[1]["runtimes"]:
            documents[1]["runtimes"].append(runtime)
        digest = digest_character * 64
        documents[1]["capabilities"].append(
            {
                "capability_id": capability_id,
                "available": True,
                "runtime_id": "company-os-skill-reference",
                "tool_locator": f"workspace://skills/company-os/assign-capability-skills/vendor/fixture/{capability_id}",
                "runtime_locator": "runtime://codex/native-skill",
                "capability_kind": "skill",
                "artifact_sha256": digest,
                "skill_bindings": [
                    {
                        "assignment_id": f"{packet_id}-skills",
                        "assignment_sha256": "a" * 64,
                        "catalog_sha256": "b" * 64,
                        "entrypoint_sha256": digest,
                        "packet_id": packet_id,
                        "request_sha256": "c" * 64,
                        "role": role,
                        "source_commit": "d" * 40,
                        "source_id": "fixture-source",
                        "upstream_entrypoint_sha256": "e" * 64,
                    }
                ],
            }
        )

    def real_skill_documents(
        self,
        *,
        request_mutate=None,
        manager_domains: list[str] | None = None,
        worker_domains: list[str] | None = None,
        manager_permissions: list[str] | None = None,
        worker_permissions: list[str] | None = None,
    ) -> tuple[tuple[dict, dict, dict], dict, dict, dict[str, object]]:
        skill_root = (
            ROOT
            / "skills/company-os/manage-company-program/fixtures/portable-capability-v1/skill-root"
        )
        catalog_path = skill_root.parent / "catalog.json"
        catalog = json.loads(catalog_path.read_text())
        context: dict[str, object] = {
            "capability_catalog": catalog_path,
            "portable_skill_root": skill_root,
        }
        request = {
            "$schema": "company-os.capability-request.v1",
            "authorized_permissions": [],
            "domains": ["software_engineering"],
            "execution_order": ["portable-review"],
            "max_entrypoint_bytes": 49152,
            "max_skills": 4,
            "packet_id": "activation_path_work",
            "program_id": "company-os-portable-preflight-v1",
            "request_id": "portable-review-worker",
            "requested_capability_ids": ["portable-review"],
            "role": "worker",
            "selection_rationale": {
                "portable-review": "The portable fixture worker reviews its packet-owned artifact."
            },
        }
        if request_mutate is not None:
            request_mutate(request)
        assignment = CAPABILITY_MODULE.resolve_assignment(catalog, request, skill_root)
        documents = self.load_fixture("saas-onboarding-launch")
        documents[0]["program_id"] = "company-os-portable-preflight-v1"
        documents[1]["program_id"] = "company-os-portable-preflight-v1"
        documents[1]["host_profile_id"] = "company-os-portable-host-v1"
        documents[2]["program_id"] = "company-os-portable-preflight-v1"
        manager_definition = next(
            item
            for item in documents[2]["manager_definitions"]
            if item["manager_id"] == "onboarding_manager"
        )
        worker_definition = next(
            item
            for item in documents[2]["work_definitions"]
            if item["work_id"] == "activation_path_work"
        )
        manager_definition["work_domains"] = (
            copy.deepcopy(request["domains"])
            if manager_domains is None
            else manager_domains
        )
        worker_definition["work_domains"] = (
            copy.deepcopy(request["domains"])
            if worker_domains is None
            else worker_domains
        )
        manager_definition["authorized_skill_permissions"] = (
            copy.deepcopy(request["authorized_permissions"])
            if manager_permissions is None
            else manager_permissions
        )
        worker_definition["authorized_skill_permissions"] = (
            copy.deepcopy(request["authorized_permissions"])
            if worker_permissions is None
            else worker_permissions
        )
        documents = (
            documents[0],
            CAPABILITY_MODULE.augment_host_manifest(
                catalog,
                documents[1],
                [(request, assignment)],
                skill_root,
            ),
            documents[2],
        )
        return documents, request, assignment, context

    def test_brokerage_compiles_five_compact_packets_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = self.compile_fixture("brokerage-growth-launch", Path(temp) / "compiled")
            verified = self.verify_fixture("brokerage-growth-launch", Path(result["output_dir"]))
            self.assertEqual(5, verified["manager_count"])
            self.assertEqual(5, verified["work_count"])
            for reference in result["manager_packets"] + result["work_packets"]:
                self.assertLessEqual(reference["size"], 12 * 1024)
            total = sum(
                path.stat().st_size
                for path in Path(result["output_dir"]).rglob("*")
                if path.is_file()
            )
            self.assertLessEqual(total, 100 * 1024)

    def test_saas_fixture_is_materially_different_and_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            brokerage = self.compile_fixture("brokerage-growth-launch", Path(temp) / "brokerage")
            saas = self.compile_fixture("saas-onboarding-launch", Path(temp) / "saas")
            self.assertNotEqual(
                brokerage["manifest"]["program"]["program_id"],
                saas["manifest"]["program"]["program_id"],
            )
            self.assertNotEqual(brokerage["manifest_sha256"], saas["manifest_sha256"])
            self.assertEqual(5, len(saas["manager_packets"]))
            self.assertEqual(5, len(saas["work_packets"]))
            self.verify_fixture("saas-onboarding-launch", Path(saas["output_dir"]))

    def test_identical_inputs_produce_byte_identical_trees(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first"
            second = Path(temp) / "second"
            self.compile_fixture("brokerage-growth-launch", first)
            self.compile_fixture("brokerage-growth-launch", second)
            first_files = sorted(path.relative_to(first) for path in first.rglob("*") if path.is_file())
            second_files = sorted(path.relative_to(second) for path in second.rglob("*") if path.is_file())
            self.assertEqual(first_files, second_files)
            for relative in first_files:
                self.assertEqual((first / relative).read_bytes(), (second / relative).read_bytes())

    def test_cli_compile_and_verify(self) -> None:
        semantics, capabilities, definitions = self.fixture_paths("brokerage-growth-launch")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "compiled"
            self.assertEqual(
                0,
                MODULE.main(
                    [
                        "compile",
                        "--program-semantics",
                        str(semantics),
                        "--host-capabilities",
                        str(capabilities),
                        "--work-definitions",
                        str(definitions),
                        "--output-dir",
                        str(output),
                    ]
                ),
            )
            self.assertEqual(
                0,
                MODULE.main(
                    [
                        "verify",
                        "--output-dir",
                        str(output),
                        "--program-semantics",
                        str(semantics),
                        "--host-capabilities",
                        str(capabilities),
                        "--work-definitions",
                        str(definitions),
                    ]
                ),
            )

    def test_verify_requires_all_three_bound_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "compiled"
            self.compile_fixture("brokerage-growth-launch", output)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.verify_output(output)
            self.assertEqual("E_INPUT_BINDING", caught.exception.code)

    def test_constant_ceiling_drift_is_rejected(self) -> None:
        def mutate(documents):
            documents[0]["constants"][0]["value"] = 190000

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_CONSTANT_DRIFT")

    def test_signed_representation_agreement_cannot_be_relabelled_as_closing(self) -> None:
        def mutate(documents):
            documents[2]["work_definitions"][0]["required_terms"] = ["closings"]

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_TERMINOLOGY_DRIFT")

    def test_overlapping_writer_scope_is_rejected(self) -> None:
        def mutate(documents):
            work = documents[2]["work_definitions"][1]
            work["scope"]["owned_paths"] = ["programs/brokerage-growth-launch/work/market-research"]
            work["deliverables"][0]["path"] = "programs/brokerage-growth-launch/work/market-research/listing-report.md"

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_SCOPE_OVERLAP")

    def test_ancestor_writer_scope_is_rejected(self) -> None:
        def mutate(documents):
            work = documents[2]["work_definitions"][1]
            work["scope"]["owned_paths"] = ["programs/brokerage-growth-launch/work"]
            work["deliverables"][0]["path"] = "programs/brokerage-growth-launch/work/listing-report.md"

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_SCOPE_OVERLAP")

    def test_unavailable_spreadsheet_is_rejected(self) -> None:
        def mutate(documents):
            next(item for item in documents[1]["capabilities"] if item["capability_id"] == "spreadsheet")["available"] = False

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_CAPABILITY_UNAVAILABLE")

    def test_child_must_retain_every_parent_prohibition(self) -> None:
        def mutate(documents):
            documents[2]["work_definitions"][0]["prohibition_ids"] = ["no_customer_send"]

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_AUTHORITY")

    def test_child_capabilities_must_narrow_parent_slice(self) -> None:
        def mutate(documents):
            documents[2]["work_definitions"][0]["required_capabilities"] = ["spreadsheet"]

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_AUTHORITY")

    def test_prohibition_role_applicability_is_enforced(self) -> None:
        def mutate(documents):
            documents[0]["prohibitions"].append(
                {"prohibition_id": "worker_only", "label": "Worker-only control", "applies_to": ["worker"]}
            )
            documents[2]["manager_definitions"][0]["prohibition_ids"] = ["worker_only"]

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_AUTHORITY")

    def test_duplicate_required_capability_is_rejected(self) -> None:
        def mutate(documents):
            documents[0]["required_capabilities"].append(
                {"capability_id": "spreadsheet", "required": False}
            )

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_DUPLICATE_CONCEPT")

    def test_prohibited_terms_are_rejected_in_labels_and_oracle_probes(self) -> None:
        def label_mutation(documents):
            documents[2]["work_definitions"][0]["deliverables"][0]["label"] = "Closings report"

        self.assert_compile_code("brokerage-growth-launch", label_mutation, "E_TERMINOLOGY_DRIFT")

        def probe_mutation(documents):
            documents[2]["work_definitions"][0]["deliverables"][0]["oracle_probe"] = "Summarize closings"

        self.assert_compile_code("brokerage-growth-launch", probe_mutation, "E_TERMINOLOGY_DRIFT")

    def test_missing_or_malformed_locator_is_rejected(self) -> None:
        def mutate(documents):
            next(item for item in documents[1]["capabilities"] if item["capability_id"] == "spreadsheet")["runtime_locator"] = "not-a-runtime-locator"

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_LOCATOR_INVALID")

    def test_uncited_evidence_is_rejected(self) -> None:
        def mutate(documents):
            documents[2]["evidence_units"][0]["citations"] = []

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_EVIDENCE_CLOSURE")

    def test_whitespace_only_normalized_oracle_probe_is_rejected(self) -> None:
        def mutate(documents):
            documents[2]["work_definitions"][0]["deliverables"][0]["oracle_probe"] = " \n\t "

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_ORACLE_EMPTY")

    def test_unknown_alias_is_rejected(self) -> None:
        def mutate(documents):
            documents[2]["work_definitions"][0]["required_terms"] = ["not-a-canonical-term"]

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_UNKNOWN_ALIAS")

    def test_alias_collision_is_rejected(self) -> None:
        def mutate(documents):
            documents[0]["canonical_terms"][1]["aliases"].append("representation agreement")

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_ALIAS_COLLISION")

    def test_duplicate_deliverable_is_rejected(self) -> None:
        def mutate(documents):
            documents[2]["work_definitions"][1]["deliverables"][0]["deliverable_id"] = "market_research_report"

        self.assert_compile_code("brokerage-growth-launch", mutate, "E_DUPLICATE_DELIVERABLE")

    def test_unknown_keys_and_unsupported_constant_types_are_rejected(self) -> None:
        def unknown_key(documents):
            documents[0]["unexpected"] = True

        self.assert_compile_code("brokerage-growth-launch", unknown_key, "E_SCHEMA_UNKNOWN_KEY")

        def unsupported_type(documents):
            documents[0]["constants"][0]["type"] = "float"

        self.assert_compile_code("brokerage-growth-launch", unsupported_type, "E_UNSUPPORTED_TYPE")

    def test_ui_signal_without_explicit_domain_fails_closed(self) -> None:
        def mutate(documents):
            documents[2]["work_definitions"][0]["label"] = "Frontend UI component"

        self.assert_compile_code(
            "saas-onboarding-launch", mutate, "E_UI_DESIGN_CLASSIFICATION"
        )

    def test_ui_source_extension_without_explicit_domain_fails_closed(self) -> None:
        def mutate(documents):
            work = documents[2]["work_definitions"][0]
            path = "programs/saas-onboarding-launch/work/activation-path/output.tsx"
            work["scope"]["owned_paths"] = [path]
            work["deliverables"][0]["path"] = path

        self.assert_compile_code(
            "saas-onboarding-launch", mutate, "E_UI_DESIGN_CLASSIFICATION"
        )

    def test_ui_domain_without_quality_capability_fails_closed(self) -> None:
        def mutate(documents):
            manager = documents[2]["manager_definitions"][0]
            manager["label"] = "UI design manager"
            manager["work_domains"] = ["ui_design"]

        self.assert_compile_code(
            "saas-onboarding-launch", mutate, "E_UI_DESIGN_CAPABILITY"
        )

    def test_ui_worker_requires_ui_classified_parent_manager(self) -> None:
        def mutate(documents):
            self.add_ui_design_capability(documents)
            manager = documents[2]["manager_definitions"][0]
            manager["required_capabilities"].append("ui_design_quality")
            work = documents[2]["work_definitions"][0]
            work["label"] = "Frontend UI component"
            work["work_domains"] = ["ui_design"]
            work["required_capabilities"].append("ui_design_quality")

        self.assert_compile_code(
            "saas-onboarding-launch", mutate, "E_UI_DESIGN_CAPABILITY"
        )

    def test_valid_ui_lane_binds_domain_and_quality_capability_into_packets(self) -> None:
        documents = self.load_fixture("saas-onboarding-launch")
        self.add_ui_design_capability(documents)
        manager = documents[2]["manager_definitions"][0]
        manager["label"] = "UI design manager"
        manager["work_domains"] = ["ui_design"]
        manager["required_capabilities"].append("ui_design_quality")
        work = documents[2]["work_definitions"][0]
        work["label"] = "Frontend UI component"
        work["work_domains"] = ["ui_design"]
        work["required_capabilities"].append("ui_design_quality")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            result = MODULE.compile_program(*paths, root / "output")
            manager_ref = next(
                item for item in result["manager_packets"]
                if item["packet_id"] == "onboarding_manager"
            )
            work_ref = next(
                item for item in result["work_packets"]
                if item["packet_id"] == "activation_path_work"
            )
            manager_packet = json.loads(
                (Path(result["output_dir"]) / manager_ref["path"]).read_text()
            )
            work_packet = json.loads(
                (Path(result["output_dir"]) / work_ref["path"]).read_text()
            )
            for packet in (manager_packet, work_packet):
                self.assertEqual(["ui_design"], packet["work_domains"])
                self.assertIn(
                    "ui_design_quality", packet["required_capability_ids"]
                )
                self.assertEqual(
                    "workspace://skills/company-os/ui-design-quality",
                    next(
                        item["tool_locator"]
                        for item in packet["semantic_slice"]["capabilities"]
                        if item["capability_id"] == "ui_design_quality"
                    ),
                )
            MODULE.verify_output(root / "output", *paths)

    def test_skill_request_domains_and_permissions_are_bound_to_task_authority(self) -> None:
        domain_mismatch, _, _, context = self.real_skill_documents(
            manager_domains=["business_strategy"],
            worker_domains=["business_strategy"],
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, domain_mismatch)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*paths, root / "output", **context)
            self.assertEqual("E_CAPABILITY_BINDING", caught.exception.code)
            self.assertIn("request domains", str(caught.exception))

        def add_permission(request):
            request["authorized_permissions"] = ["filesystem_read"]

        permission_mismatch, _, _, context = self.real_skill_documents(
            request_mutate=add_permission,
            manager_permissions=[],
            worker_permissions=[],
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, permission_mismatch)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*paths, root / "output", **context)
            self.assertEqual("E_CAPABILITY_BINDING", caught.exception.code)
            self.assertIn("request permissions", str(caught.exception))

    def test_worker_skill_authority_must_narrow_its_parent_manager(self) -> None:
        documents, _, _, context = self.real_skill_documents(
            manager_domains=["business_strategy"],
            worker_domains=["software_engineering"],
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*paths, root / "output", **context)
            self.assertEqual("E_AUTHORITY", caught.exception.code)
            self.assertIn("widens parent work domains", str(caught.exception))

    def test_legacy_packet_id_collision_remains_valid_without_skill_assignments(self) -> None:
        documents = self.load_fixture("saas-onboarding-launch")
        manager = documents[2]["manager_definitions"][0]
        worker = documents[2]["work_definitions"][0]
        manager["manager_id"] = worker["work_id"]
        worker["manager_id"] = worker["work_id"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            result = MODULE.compile_program(*paths, root / "output")
            MODULE.verify_output(root / "output", *paths)
            self.assertIn(
                worker["work_id"],
                [item["packet_id"] for item in result["manager_packets"]],
            )
            self.assertIn(
                worker["work_id"],
                [item["packet_id"] for item in result["work_packets"]],
            )

    def test_packet_id_collision_is_rejected_when_skill_assignments_exist(self) -> None:
        documents, _, _, context = self.real_skill_documents()
        manager = next(
            item
            for item in documents[2]["manager_definitions"]
            if item["manager_id"] == "onboarding_manager"
        )
        worker = next(
            item
            for item in documents[2]["work_definitions"]
            if item["work_id"] == "activation_path_work"
        )
        manager["manager_id"] = worker["work_id"]
        worker["manager_id"] = worker["work_id"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*paths, root / "output", **context)
            self.assertEqual("E_CAPABILITY_BINDING", caught.exception.code)
            self.assertIn("packet IDs must not collide", str(caught.exception))

    def test_handcrafted_skill_bindings_are_rejected_without_resolver_records(self) -> None:
        documents = self.load_fixture("saas-onboarding-launch")
        self.add_bound_skill(
            documents,
            "systematic_debugging",
            "activation_path_work",
            "worker",
            "2",
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*paths, root / "output")
            self.assertEqual("E_CAPABILITY_BINDING", caught.exception.code)
            self.assertIn("resolver-verifiable assignment records", str(caught.exception))

    def test_skill_binding_rejects_unknown_packet_role_artifact_drift_and_required_capability_bypass(self) -> None:
        def unknown_packet(documents):
            self.add_bound_skill(
                documents, "systematic_debugging", "missing_work", "worker", "2"
            )

        self.assert_compile_code(
            "saas-onboarding-launch", unknown_packet, "E_CAPABILITY_BINDING"
        )

        def role_mismatch(documents):
            self.add_bound_skill(
                documents, "systematic_debugging", "activation_path_work", "manager", "2"
            )

        self.assert_compile_code(
            "saas-onboarding-launch", role_mismatch, "E_CAPABILITY_BINDING"
        )

        def artifact_drift(documents):
            self.add_bound_skill(
                documents, "systematic_debugging", "activation_path_work", "worker", "2"
            )
            documents[1]["capabilities"][-1]["artifact_sha256"] = "3" * 64

        self.assert_compile_code(
            "saas-onboarding-launch", artifact_drift, "E_CAPABILITY_BINDING"
        )

        def required_capability_bypass(documents):
            self.add_bound_skill(
                documents, "systematic_debugging", "activation_path_work", "worker", "2"
            )
            documents[0]["required_capabilities"].append(
                {"capability_id": "systematic_debugging", "required": False}
            )
            documents[2]["work_definitions"][0]["required_capabilities"].append(
                "systematic_debugging"
            )

        self.assert_compile_code(
            "saas-onboarding-launch",
            required_capability_bypass,
            "E_CAPABILITY_BINDING",
        )

    def test_real_catalog_assignment_compiles_only_into_its_exact_worker_packet(self) -> None:
        skill_root = (
            ROOT
            / "skills/company-os/manage-company-program/fixtures/portable-capability-v1/skill-root"
        )
        catalog_path = skill_root.parent / "catalog.json"
        catalog = json.loads(catalog_path.read_text())
        context = {
            "capability_catalog": catalog_path,
            "portable_skill_root": skill_root,
        }
        request = {
            "$schema": "company-os.capability-request.v1",
            "authorized_permissions": [],
            "domains": ["software_engineering"],
            "execution_order": ["portable-review"],
            "max_entrypoint_bytes": 49152,
            "max_skills": 4,
            "packet_id": "activation_path_work",
            "program_id": "company-os-portable-preflight-v1",
            "request_id": "portable-review-worker",
            "requested_capability_ids": ["portable-review"],
            "role": "worker",
            "selection_rationale": {
                "portable-review": "The portable fixture worker reviews its packet-owned artifact."
            },
        }
        assignment = CAPABILITY_MODULE.resolve_assignment(
            catalog, request, skill_root
        )
        documents = self.load_fixture("saas-onboarding-launch")
        documents[0]["program_id"] = "company-os-portable-preflight-v1"
        documents[1]["program_id"] = "company-os-portable-preflight-v1"
        documents[1]["host_profile_id"] = "company-os-portable-host-v1"
        documents[2]["program_id"] = "company-os-portable-preflight-v1"
        manager_definition = next(
            item
            for item in documents[2]["manager_definitions"]
            if item["manager_id"] == "onboarding_manager"
        )
        worker_definition = next(
            item
            for item in documents[2]["work_definitions"]
            if item["work_id"] == "activation_path_work"
        )
        for definition in (manager_definition, worker_definition):
            definition["work_domains"] = ["software_engineering"]
            definition["authorized_skill_permissions"] = []
        documents = (
            documents[0],
            CAPABILITY_MODULE.augment_host_manifest(
                catalog,
                documents[1],
                [(request, assignment)],
                skill_root,
            ),
            documents[2],
        )
        self.assertEqual(
            CAPABILITY_MODULE.canonical_digest(catalog), assignment["catalog_sha256"]
        )
        self.assertEqual(
            CAPABILITY_MODULE.canonical_digest(request), assignment["request_sha256"]
        )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            result = MODULE.compile_program(*paths, root / "output", **context)
            selected_ref = next(
                item
                for item in result["work_packets"]
                if item["packet_id"] == "activation_path_work"
            )
            selected = json.loads((root / "output" / selected_ref["path"]).read_text())
            self.assertEqual(["portable-review"], selected["assigned_skill_ids"])
            self.assertEqual(["software_engineering"], selected["work_domains"])
            self.assertEqual([], selected["authorized_skill_permissions"])
            self.assertEqual(request, selected["skill_assignment"]["request"])
            self.assertEqual(assignment, selected["skill_assignment"]["assignment"])
            schema_path = (
                ROOT
                / "skills/company-os/manage-company-program/schemas/compiled-preflight.schema.json"
            )
            schema_document = json.loads(schema_path.read_text())
            packet_schema = MODULE._expand_schema_refs(
                schema_document["$defs"]["packet"], schema_document
            )
            MODULE._validate_schema(selected, packet_schema)
            malformed = copy.deepcopy(selected)
            del malformed["skill_assignment"]["request"]["role"]
            with self.assertRaises(MODULE.PreflightError):
                MODULE._validate_schema(malformed, packet_schema)
            skill = next(
                item
                for item in selected["semantic_slice"]["capabilities"]
                if item.get("capability_kind") == "skill"
            )
            self.assertEqual("portable-review", skill["capability_id"])
            self.assertEqual(1, len(skill["skill_bindings"]))
            self.assertEqual(
                assignment["binding"]["canonical_sha256"],
                skill["skill_bindings"][0]["assignment_sha256"],
            )
            self.assertEqual(
                assignment["skills"][0]["entrypoint_sha256"],
                skill["artifact_sha256"],
            )
            self.assertLessEqual(selected_ref["size"], 12 * 1024)

            for reference in result["manager_packets"]:
                packet = json.loads((root / "output" / reference["path"]).read_text())
                self.assertNotIn("assigned_skill_ids", packet)
            for reference in result["work_packets"]:
                if reference["packet_id"] == "activation_path_work":
                    continue
                packet = json.loads((root / "output" / reference["path"]).read_text())
                self.assertNotIn("assigned_skill_ids", packet)
            MODULE.verify_output(root / "output", *paths, **context)

    def test_real_two_skill_worker_bundle_preserves_manager_execution_order(self) -> None:
        skill_root = (
            ROOT
            / "skills/company-os/manage-company-program/fixtures/portable-capability-v1/skill-root"
        )
        catalog_path = skill_root.parent / "catalog.json"
        catalog = json.loads(catalog_path.read_text())
        context = {
            "capability_catalog": catalog_path,
            "portable_skill_root": skill_root,
        }
        request = {
            "$schema": "company-os.capability-request.v1",
            "authorized_permissions": [],
            "domains": ["software_engineering"],
            "execution_order": ["portable-review"],
            "max_entrypoint_bytes": 49152,
            "max_skills": 4,
            "packet_id": "activation_path_work",
            "program_id": "company-os-portable-preflight-v1",
            "request_id": "portable-review-worker-bundle",
            "requested_capability_ids": ["portable-review"],
            "role": "worker",
            "selection_rationale": {
                "portable-review": "Review the bounded fixture artifact.",
            },
        }
        assignment = CAPABILITY_MODULE.resolve_assignment(catalog, request, skill_root)
        self.assertEqual(request["execution_order"], assignment["execution_order"])
        self.assertEqual(
            request["requested_capability_ids"],
            [skill["capability_id"] for skill in assignment["skills"]],
        )
        self.assertLessEqual(assignment["total_entrypoint_bytes"], 48 * 1024)

        documents = self.load_fixture("saas-onboarding-launch")
        documents[0]["program_id"] = "company-os-portable-preflight-v1"
        documents[1]["program_id"] = "company-os-portable-preflight-v1"
        documents[1]["host_profile_id"] = "company-os-portable-host-v1"
        documents[2]["program_id"] = "company-os-portable-preflight-v1"
        manager_definition = next(
            item
            for item in documents[2]["manager_definitions"]
            if item["manager_id"] == "onboarding_manager"
        )
        worker_definition = next(
            item
            for item in documents[2]["work_definitions"]
            if item["work_id"] == "activation_path_work"
        )
        for definition in (manager_definition, worker_definition):
            definition["work_domains"] = ["software_engineering"]
            definition["authorized_skill_permissions"] = []
        documents = (
            documents[0],
            CAPABILITY_MODULE.augment_host_manifest(
                catalog,
                documents[1],
                [(request, assignment)],
                skill_root,
            ),
            documents[2],
        )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            result = MODULE.compile_program(*paths, root / "output", **context)
            selected_ref = next(
                item
                for item in result["work_packets"]
                if item["packet_id"] == "activation_path_work"
            )
            selected = json.loads((root / "output" / selected_ref["path"]).read_text())
            self.assertEqual(
                request["requested_capability_ids"], selected["assigned_skill_ids"]
            )
            self.assertEqual(
                request["execution_order"],
                selected["skill_assignment"]["assignment"]["execution_order"],
            )
            self.assertEqual(request, selected["skill_assignment"]["request"])
            for reference in result["manager_packets"]:
                sibling = json.loads((root / "output" / reference["path"]).read_text())
                self.assertNotIn("assigned_skill_ids", sibling)
            for reference in result["work_packets"]:
                if reference["packet_id"] == "activation_path_work":
                    continue
                sibling = json.loads((root / "output" / reference["path"]).read_text())
                self.assertNotIn("assigned_skill_ids", sibling)
            MODULE.verify_output(root / "output", *paths, **context)

    def test_real_catalog_manager_skill_isolated_to_exact_manager_packet(self) -> None:
        skill_root = (
            ROOT
            / "skills/company-os/manage-company-program/fixtures/portable-capability-v1/skill-root"
        )
        catalog_path = skill_root.parent / "catalog.json"
        catalog = json.loads(catalog_path.read_text())
        context = {
            "capability_catalog": catalog_path,
            "portable_skill_root": skill_root,
        }
        request = {
            "$schema": "company-os.capability-request.v1",
            "authorized_permissions": [],
            "domains": ["software_engineering"],
            "execution_order": ["portable-review"],
            "max_entrypoint_bytes": 49152,
            "max_skills": 4,
            "packet_id": "onboarding_manager",
            "program_id": "company-os-portable-preflight-v1",
            "request_id": "portable-review-manager",
            "requested_capability_ids": ["portable-review"],
            "role": "manager",
            "selection_rationale": {
                "portable-review": "The manager reviews the bounded fixture artifact."
            },
        }
        assignment = CAPABILITY_MODULE.resolve_assignment(catalog, request, skill_root)
        documents = self.load_fixture("saas-onboarding-launch")
        documents[0]["program_id"] = "company-os-portable-preflight-v1"
        documents[1]["program_id"] = "company-os-portable-preflight-v1"
        documents[1]["host_profile_id"] = "company-os-portable-host-v1"
        documents[2]["program_id"] = "company-os-portable-preflight-v1"
        manager_definition = next(
            item
            for item in documents[2]["manager_definitions"]
            if item["manager_id"] == "onboarding_manager"
        )
        manager_definition["work_domains"] = ["software_engineering"]
        manager_definition["authorized_skill_permissions"] = []
        documents = (
            documents[0],
            CAPABILITY_MODULE.augment_host_manifest(
                catalog,
                documents[1],
                [(request, assignment)],
                skill_root,
            ),
            documents[2],
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            result = MODULE.compile_program(*paths, root / "output", **context)
            selected_ref = next(
                item
                for item in result["manager_packets"]
                if item["packet_id"] == "onboarding_manager"
            )
            selected = json.loads((root / "output" / selected_ref["path"]).read_text())
            self.assertEqual(["portable-review"], selected["assigned_skill_ids"])
            self.assertEqual(request, selected["skill_assignment"]["request"])
            self.assertEqual(assignment, selected["skill_assignment"]["assignment"])
            for reference in result["manager_packets"]:
                if reference["packet_id"] == "onboarding_manager":
                    continue
                sibling = json.loads((root / "output" / reference["path"]).read_text())
                self.assertNotIn("assigned_skill_ids", sibling)
            for reference in result["work_packets"]:
                sibling = json.loads((root / "output" / reference["path"]).read_text())
                self.assertNotIn("assigned_skill_ids", sibling)
            MODULE.verify_output(root / "output", *paths, **context)

    def test_portable_v1_producer_output_is_byte_identical_through_compile_and_verify(self) -> None:
        documents, _, _, context = self.real_skill_documents()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            first = MODULE.compile_program(*paths, root / "first", **context)
            second = MODULE.compile_program(*paths, root / "second", **context)
            first_files = sorted(path.relative_to(root / "first") for path in (root / "first").rglob("*") if path.is_file())
            second_files = sorted(path.relative_to(root / "second") for path in (root / "second").rglob("*") if path.is_file())
            self.assertEqual(first_files, second_files)
            for relative in first_files:
                self.assertEqual(
                    (root / "first" / relative).read_bytes(),
                    (root / "second" / relative).read_bytes(),
                )
            self.assertEqual(
                first["manifest_sha256"],
                MODULE.verify_output(root / "first", *paths, **context)["manifest_sha256"],
            )

    def test_skill_host_requires_atomic_four_part_context(self) -> None:
        documents, _, _, _ = self.real_skill_documents()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            for kwargs in ({}, {"review_registry": {}}):
                with self.assertRaises(MODULE.PreflightError) as caught:
                    MODULE.compile_program(*paths, root / "output", **kwargs)
                self.assertEqual("E_CAPABILITY_REVIEW_CONTEXT", caught.exception.code)
                self.assertFalse((root / "output").exists())

    def test_current_production_context_reaches_candidate_decision(self) -> None:
        documents, _, _, _ = self.real_skill_documents()
        context = self.production_context()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*paths, root / "output", **context)
            self.assertEqual("E_DECISION", caught.exception.code)
            self.assertFalse((root / "output").exists())

    def test_independent_provenance_tamper_is_binding_error_and_context_is_unchanged(self) -> None:
        documents, _, _, _ = self.real_skill_documents()
        base_context = self.production_context()
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
                self.assertEqual("E_CAPABILITY_BINDING", caught.exception.code)
                self.assertFalse((root / "output").exists())
            self.assertEqual(before, context)

    def test_portable_fixture_identity_marker_and_cli_boundaries(self) -> None:
        documents, _, _, context = self.real_skill_documents()
        catalog_path, skill_root = self.portable_paths()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            renamed = json.loads(catalog_path.read_text())
            renamed["catalog_id"] = "renamed-portable-catalog"
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*paths, root / "renamed", capability_catalog=renamed, portable_skill_root=skill_root)
            self.assertEqual("E_CAPABILITY_REVIEW_CONTEXT", caught.exception.code)

            wrong_program = copy.deepcopy(documents)
            wrong_program[0]["program_id"] = "wrong-portable-program"
            wrong_program[1]["program_id"] = "wrong-portable-program"
            wrong_program[2]["program_id"] = "wrong-portable-program"
            wrong_paths = self.write_inputs(root / "wrong-program", wrong_program)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*wrong_paths, root / "wrong-program-output", **context)
            self.assertEqual("E_CAPABILITY_REVIEW_CONTEXT", caught.exception.code)

            wrong_host = copy.deepcopy(documents)
            wrong_host[1]["host_profile_id"] = "wrong-portable-host"
            wrong_paths = self.write_inputs(root / "wrong-host", wrong_host)
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*wrong_paths, root / "wrong-host-output", **context)
            self.assertEqual("E_CAPABILITY_REVIEW_CONTEXT", caught.exception.code)

            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*paths, root / "production-root", capability_catalog=catalog_path, portable_skill_root=ROOT / "skills/company-os/assign-capability-skills")
            self.assertEqual("E_CAPABILITY_REVIEW_CONTEXT", caught.exception.code)

            copied_root = root / "missing-marker-root"
            shutil.copytree(skill_root, copied_root)
            (copied_root / MODULE.PORTABLE_FIXTURE_MARKER).unlink()
            with self.assertRaises(MODULE.PreflightError) as caught:
                MODULE.compile_program(*paths, root / "missing-marker", capability_catalog=catalog_path, portable_skill_root=copied_root)
            self.assertEqual("E_CAPABILITY_REVIEW_CONTEXT", caught.exception.code)

            with self.assertRaises(SystemExit):
                MODULE.main(["compile", "--capability-catalog", str(catalog_path)])

    def test_synthetic_accepted_v2_envelope_and_exact_rejections(self) -> None:
        documents, context, contract, assignment = self.synthetic_v2_documents()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            with mock.patch.object(MODULE, "_capability_contract", return_value=contract):
                result = MODULE.compile_program(*paths, root / "accepted", **context)
                verified = MODULE.verify_output(root / "accepted", *paths, **context)
            self.assertEqual(result["manifest_sha256"], verified["manifest_sha256"])

        for missing in (*MODULE.V2_REVIEW_ROOT_KEYS, *MODULE.V2_REVIEW_SKILL_KEYS):
            def remove_field(value, key=missing):
                if key in value:
                    del value[key]
                else:
                    del value["skills"][0][key]

            documents, context, contract, _ = self.synthetic_v2_documents(assignment_mutate=remove_field)
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                paths = self.write_inputs(root, documents)
                with mock.patch.object(MODULE, "_capability_contract", return_value=contract):
                    with self.assertRaises(MODULE.PreflightError) as caught:
                        MODULE.compile_program(*paths, root / "missing", **context)
                self.assertEqual("E_CAPABILITY_BINDING", caught.exception.code)

        for bad_value in (None, "not-a-digest"):
            def bad_review_digest(value, replacement=bad_value):
                value["review_registry_sha256"] = replacement

            documents, context, contract, _ = self.synthetic_v2_documents(assignment_mutate=bad_review_digest)
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                paths = self.write_inputs(root, documents)
                with mock.patch.object(MODULE, "_capability_contract", return_value=contract):
                    with self.assertRaises(MODULE.PreflightError) as caught:
                        MODULE.compile_program(*paths, root / "bad-value", **context)
                self.assertIn(caught.exception.code, {"E_SCHEMA", "E_CAPABILITY_BINDING"})

        def extra_binding(binding):
            binding["review_extra"] = "unexpected"

        documents, context, contract, _ = self.synthetic_v2_documents(binding_mutate=extra_binding)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            with mock.patch.object(MODULE, "_capability_contract", return_value=contract):
                with self.assertRaises(MODULE.PreflightError) as caught:
                    MODULE.compile_program(*paths, root / "extra", **context)
            self.assertIn(caught.exception.code, {"E_SCHEMA_UNKNOWN_KEY", "E_CAPABILITY_BINDING"})

        def substituted_binding(binding):
            binding["review_sha256"] = "e" * 64

        documents, context, contract, _ = self.synthetic_v2_documents(binding_mutate=substituted_binding)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = self.write_inputs(root, documents)
            with mock.patch.object(MODULE, "_capability_contract", return_value=contract):
                with self.assertRaises(MODULE.PreflightError) as caught:
                    MODULE.compile_program(*paths, root / "substituted", **context)
            self.assertEqual("E_CAPABILITY_BINDING", caught.exception.code)

    def test_duplicate_ui_domain_is_rejected(self) -> None:
        def mutate(documents):
            manager = documents[2]["manager_definitions"][0]
            manager["work_domains"] = ["ui_design", "ui_design"]

        self.assert_compile_code(
            "saas-onboarding-launch", mutate, "E_DUPLICATE_CONCEPT"
        )

    def test_mutated_packet_is_rejected_by_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "compiled"
            result = self.compile_fixture("brokerage-growth-launch", output)
            relative = result["work_packets"][0]["path"]
            packet_path = output / relative
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            packet["deliverables"][0]["label"] = "mutated output"
            packet_path.write_bytes(MODULE.canonical_bytes(packet))
            with self.assertRaises(MODULE.PreflightError) as caught:
                self.verify_fixture("brokerage-growth-launch", output)
            self.assertEqual("E_PACKET_MUTATED", caught.exception.code)

    def test_rehashed_packet_and_manifest_are_rejected_against_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "compiled"
            result = self.compile_fixture("brokerage-growth-launch", output)
            reference = result["work_packets"][0]
            old_path = output / reference["path"]
            packet = json.loads(old_path.read_text(encoding="utf-8"))
            packet["deliverables"][0]["label"] = "attacker-rebound"
            packet["binding"]["canonical_sha256"] = None
            packet_digest = MODULE.canonical_digest(packet)
            packet["binding"]["canonical_sha256"] = packet_digest
            new_relative = (
                f"work-packets/work-{packet['packet_id']}-{packet_digest[:16]}.json"
            )
            new_path = output / new_relative
            new_path.write_bytes(MODULE.canonical_bytes(packet))
            old_path.unlink()

            manifest_path = output / "compiled-preflight.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            bound_reference = next(
                item for item in manifest["work_packets"] if item["packet_id"] == packet["packet_id"]
            )
            bound_reference.update(
                path=new_relative,
                sha256=packet_digest,
                size=new_path.stat().st_size,
            )
            manifest["binding"]["canonical_sha256"] = None
            manifest["binding"]["canonical_sha256"] = MODULE.canonical_digest(manifest)
            manifest_path.write_bytes(MODULE.canonical_bytes(manifest))

            with self.assertRaises(MODULE.PreflightError) as caught:
                self.verify_fixture("brokerage-growth-launch", output)
            self.assertEqual("E_UNBOUND_OUTPUT", caught.exception.code)

    def test_unbound_packet_field_and_extra_packet_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "compiled"
            result = self.compile_fixture("brokerage-growth-launch", output)
            packet_path = output / result["manager_packets"][0]["path"]
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            packet["unbound_field"] = "not allowed"
            packet_path.write_bytes(MODULE.canonical_bytes(packet))
            with self.assertRaises(MODULE.PreflightError) as caught:
                self.verify_fixture("brokerage-growth-launch", output)
            self.assertEqual("E_UNBOUND_OUTPUT", caught.exception.code)

            packet_path.unlink()
            # Recompile into a fresh tree because the previous mutation is
            # intentionally not repaired in place.
            output = Path(temp) / "compiled-extra"
            self.compile_fixture("brokerage-growth-launch", output)
            (output / "work-packets" / "extra.json").write_bytes(b"{}")
            with self.assertRaises(MODULE.PreflightError) as caught:
                self.verify_fixture("brokerage-growth-launch", output)
            self.assertEqual("E_PACKET_EXTRA", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
