from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills/company-os/manage-company-program/scripts/compile_program_preflight.py"
SPEC = importlib.util.spec_from_file_location("compile_program_preflight", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProgramPreflightCompilerTests(unittest.TestCase):
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
        names = ("program-semantics.json", "host-capabilities.json", "work-definitions.json")
        paths = []
        for name, document in zip(names, documents):
            path = directory / name
            path.write_bytes(MODULE.canonical_bytes(document))
            paths.append(path)
        return tuple(paths)  # type: ignore[return-value]

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
