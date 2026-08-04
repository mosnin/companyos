from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "skills/company-os/force-first-execution/scripts"
sys.path.insert(0, str(SCRIPT_ROOT))


def load_module(name: str, filename: str):
    specification = importlib.util.spec_from_file_location(name, SCRIPT_ROOT / filename)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


FORCE = load_module("force_loop_controller_for_release_tests", "force_loop_controller.py")
SNAPSHOT = load_module("seal_force_snapshot_for_tests", "seal_force_snapshot.py")
SCOPE = load_module("release_scope_controller_for_tests", "release_scope_controller.py")

PAYLOAD = b"accepted-business-artifact"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def force_contract() -> dict:
    return {
        "schema": "company-os.force-contract.v1",
        "task_id": "worker-1",
        "outcome": "Produce a real business artifact.",
        "started_at_epoch": 1000,
        "soft_slos": {
            "first_artifact_seconds": 300,
            "runnable_candidate_seconds": 900,
            "verification_seconds": 1200,
            "acceptance_to_receipt_seconds": 120,
            "receipt_to_decision_seconds": 120,
        },
        "control": {
            "inflight_observation_fresh_seconds": 120,
            "max_rework_cycles": 1,
            "event_log_owner": "manager",
        },
        "hard_stop_codes": sorted(FORCE.BASELINE_HARD_STOPS),
    }


def force_event(sequence: int, name: str, at_epoch: int, evidence: dict | None = None) -> dict:
    return {
        "schema": "company-os.force-event.v1",
        "sequence": sequence,
        "task_id": "worker-1",
        "event": name,
        "at_epoch": at_epoch,
        "evidence": evidence or {},
    }


def terminal_events() -> list[dict]:
    return [
        force_event(1, "task_started", 1000),
        force_event(
            2,
            "artifact_materialized",
            1010,
            {"path": "artifacts/release.bin", "sha256": DIGEST},
        ),
        force_event(3, "candidate_runnable", 1020, {"artifact_paths": ["artifacts/release.bin"]}),
        force_event(4, "verification_passed", 1030, {"check": "independent oracle passed"}),
        force_event(
            5,
            "manager_inspection_passed",
            1040,
            {"artifact_paths": ["artifacts/release.bin"]},
        ),
        force_event(
            6,
            "receipt_materialized",
            1050,
            {"path": "evidence/worker-receipt.json", "sha256": DIGEST},
        ),
        force_event(7, "manager_accept", 1060),
    ]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_events(path: Path, values: list[dict]) -> None:
    path.write_bytes(b"".join(FORCE.canonical_bytes(value) + b"\n" for value in values))


class ForceSnapshotTests(unittest.TestCase):
    def prepare(self, root: Path, values: list[dict] | None = None) -> tuple[Path, Path]:
        (root / "artifacts").mkdir()
        (root / "evidence").mkdir()
        (root / "artifacts/release.bin").write_bytes(PAYLOAD)
        (root / "evidence/worker-receipt.json").write_bytes(PAYLOAD)
        contract_path = root / "force-contract.json"
        events_path = root / "force-events.jsonl"
        write_json(contract_path, force_contract())
        write_events(events_path, values or terminal_events())
        return contract_path, events_path

    def test_terminal_log_seals_and_verifies_exact_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path, events_path = self.prepare(root)
            result = SNAPSHOT.seal(
                contract_path,
                events_path,
                root,
                "evidence/force.sealed.jsonl",
                "evidence/force.seal-receipt.json",
            )
            self.assertTrue(result["ok"])
            self.assertEqual(7, result["event_count"])
            verification = SNAPSHOT.verify(
                contract_path,
                root,
                "evidence/force.sealed.jsonl",
                "evidence/force.seal-receipt.json",
            )
            self.assertEqual("manager_accept", verification["terminal_event"])
            self.assertEqual(result["snapshot_sha256"], verification["snapshot_sha256"])

    def test_live_log_append_cannot_change_sealed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path, events_path = self.prepare(root)
            result = SNAPSHOT.seal(
                contract_path,
                events_path,
                root,
                "evidence/force.sealed.jsonl",
                "evidence/force.seal-receipt.json",
            )
            snapshot_before = (root / "evidence/force.sealed.jsonl").read_bytes()
            with events_path.open("ab") as stream:
                stream.write(b'{"later":"untrusted live append"}\n')
            verification = SNAPSHOT.verify(
                contract_path,
                root,
                "evidence/force.sealed.jsonl",
                "evidence/force.seal-receipt.json",
            )
            self.assertEqual(result["snapshot_sha256"], verification["snapshot_sha256"])
            self.assertEqual(snapshot_before, (root / "evidence/force.sealed.jsonl").read_bytes())

    def test_nonterminal_log_cannot_be_sealed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path, events_path = self.prepare(root, terminal_events()[:-2])
            with self.assertRaisesRegex(SNAPSHOT.force.ForceContractError, "terminal"):
                SNAPSHOT.seal(
                    contract_path,
                    events_path,
                    root,
                    "evidence/force.sealed.jsonl",
                    "evidence/force.seal-receipt.json",
                )
            self.assertFalse((root / "evidence/force.sealed.jsonl").exists())

    def test_exact_seal_replay_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path, events_path = self.prepare(root)
            first = SNAPSHOT.seal(
                contract_path,
                events_path,
                root,
                "evidence/force.sealed.jsonl",
                "evidence/force.seal-receipt.json",
            )
            original = (root / "evidence/force.sealed.jsonl").read_bytes()
            second = SNAPSHOT.seal(
                contract_path,
                events_path,
                root,
                "evidence/force.sealed.jsonl",
                "evidence/force.seal-receipt.json",
            )
            self.assertEqual(first, second)
            self.assertEqual(original, (root / "evidence/force.sealed.jsonl").read_bytes())

    def test_orphan_snapshot_can_finish_exact_receipt_after_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path, events_path = self.prepare(root)
            first = SNAPSHOT.seal(
                contract_path,
                events_path,
                root,
                "evidence/force.sealed.jsonl",
                "evidence/force.seal-receipt.json",
            )
            receipt = root / "evidence/force.seal-receipt.json"
            receipt.unlink()
            second = SNAPSHOT.seal(
                contract_path,
                events_path,
                root,
                "evidence/force.sealed.jsonl",
                "evidence/force.seal-receipt.json",
            )
            self.assertEqual(first, second)
            self.assertTrue(receipt.is_file())

    def test_orphan_receipt_can_restore_exact_snapshot_after_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path, events_path = self.prepare(root)
            first = SNAPSHOT.seal(
                contract_path,
                events_path,
                root,
                "evidence/force.sealed.jsonl",
                "evidence/force.seal-receipt.json",
            )
            snapshot = root / "evidence/force.sealed.jsonl"
            snapshot.unlink()
            second = SNAPSHOT.seal(
                contract_path,
                events_path,
                root,
                "evidence/force.sealed.jsonl",
                "evidence/force.seal-receipt.json",
            )
            self.assertEqual(first, second)
            self.assertTrue(snapshot.is_file())

    def test_receipt_directory_fsync_failure_is_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path, events_path = self.prepare(root)
            with mock.patch.object(
                SNAPSHOT,
                "_fsync_directory",
                side_effect=[None, OSError("injected receipt directory fsync failure")],
            ):
                with self.assertRaisesRegex(
                    SNAPSHOT.force.ForceContractError, "could not be written"
                ):
                    SNAPSHOT.seal(
                        contract_path,
                        events_path,
                        root,
                        "evidence/force.sealed.jsonl",
                        "evidence/force.seal-receipt.json",
                    )
            self.assertTrue((root / "evidence/force.sealed.jsonl").is_file())
            self.assertTrue((root / "evidence/force.seal-receipt.json").is_file())
            retried = SNAPSHOT.seal(
                contract_path,
                events_path,
                root,
                "evidence/force.sealed.jsonl",
                "evidence/force.seal-receipt.json",
            )
            self.assertTrue(retried["ok"])

    def test_symlinked_contract_and_event_sources_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path, events_path = self.prepare(root)
            contract_link = root / "contract-link.json"
            events_link = root / "events-link.jsonl"
            contract_link.symlink_to(contract_path)
            events_link.symlink_to(events_path)
            with self.assertRaisesRegex(SNAPSHOT.force.ForceContractError, "symlink"):
                SNAPSHOT.seal(
                    contract_link,
                    events_path,
                    root,
                    "evidence/force.sealed.jsonl",
                    "evidence/force.seal-receipt.json",
                )
            with self.assertRaisesRegex(SNAPSHOT.force.ForceContractError, "symlink"):
                SNAPSHOT.seal(
                    contract_path,
                    events_link,
                    root,
                    "evidence/force.sealed.jsonl",
                    "evidence/force.seal-receipt.json",
                )

    def test_ambiguous_source_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, events_path = self.prepare(root)
            ambiguous_contract = root / "evidence" / ".." / "force-contract.json"
            with self.assertRaisesRegex(
                SNAPSHOT.force.ForceContractError, "parent traversal"
            ):
                SNAPSHOT.seal(
                    ambiguous_contract,
                    events_path,
                    root,
                    "evidence/force.sealed.jsonl",
                    "evidence/force.seal-receipt.json",
                )

    def test_conflicting_existing_snapshot_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path, events_path = self.prepare(root)
            SNAPSHOT.seal(
                contract_path,
                events_path,
                root,
                "evidence/force.sealed.jsonl",
                "evidence/force.seal-receipt.json",
            )
            (root / "evidence/force.sealed.jsonl").write_bytes(b"conflict\n")
            with self.assertRaisesRegex(
                SNAPSHOT.force.ForceContractError, "existing snapshot bytes"
            ):
                SNAPSHOT.seal(
                    contract_path,
                    events_path,
                    root,
                    "evidence/force.sealed.jsonl",
                    "evidence/force.seal-receipt.json",
                )

    def test_snapshot_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path, events_path = self.prepare(root)
            SNAPSHOT.seal(
                contract_path,
                events_path,
                root,
                "evidence/force.sealed.jsonl",
                "evidence/force.seal-receipt.json",
            )
            snapshot = root / "evidence/force.sealed.jsonl"
            snapshot.write_bytes(snapshot.read_bytes().replace(b"manager_accept", b"manager_reject"))
            with self.assertRaises(SNAPSHOT.force.ForceContractError):
                SNAPSHOT.verify(
                    contract_path,
                    root,
                    "evidence/force.sealed.jsonl",
                    "evidence/force.seal-receipt.json",
                )

    def test_snapshot_verification_rejects_symlinked_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path, events_path = self.prepare(root)
            SNAPSHOT.seal(
                contract_path,
                events_path,
                root,
                "evidence/force.sealed.jsonl",
                "evidence/force.seal-receipt.json",
            )
            (root / "alias").symlink_to(root / "evidence", target_is_directory=True)
            with self.assertRaisesRegex(SNAPSHOT.force.ForceContractError, "symlink"):
                SNAPSHOT.verify(
                    contract_path,
                    root,
                    "alias/force.sealed.jsonl",
                    "evidence/force.seal-receipt.json",
                )


def exact_file(root: Path, relative: str, content: bytes) -> dict[str, str]:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return {"path": relative, "sha256": hashlib.sha256(content).hexdigest()}


def canonical_file(root: Path, relative: str, value: dict) -> dict[str, str]:
    return exact_file(root, relative, SCOPE.canonical_bytes(value) + b"\n")


def release_contract(root: Path) -> dict:
    contract = {
        "schema": "company-os.release-scope.v1",
        "project_id": "hearthpod",
        "program_id": "hearthpod-launch",
        "program_version": 1,
        "definition_version": 1,
        "cycle_id": "launch-cycle-1",
        "master_task_id": "hearthpod-master-1",
        "outcome_digest": "a" * 64,
        "deliverables": [
            {
                "deliverable_id": "core-launch-package",
                "manager_task_id": "operations-manager-1",
                "criticality": "required",
                "outcome_contribution": "Provides the decision-useful company launch package.",
            },
            {
                "deliverable_id": "seasonal-panel",
                "manager_task_id": "commercial-manager-1",
                "criticality": "optional",
                "outcome_contribution": "Adds a seasonal campaign comparison without changing the core offer.",
            },
        ],
        "policy": {
            "required_failure": "block_release",
            "optional_failure": "omit_without_quality_relaxation",
            "max_optional_recovery_chains": 1,
        },
        "accepted_design_decision": {
            "path": "evidence/release-scope-design.v1.json",
            "sha256": "0" * 64,
        },
    }
    decision = {
        "schema": "company-os.release-scope-design-decision.v1",
        "record_version": 1,
        "decision": "accepted",
        "authority_role": "master",
        "decider_task_id": contract["master_task_id"],
        "bindings": {
            "project_id": contract["project_id"],
            "program_id": contract["program_id"],
            "program_version": contract["program_version"],
            "definition_version": contract["definition_version"],
            "cycle_id": contract["cycle_id"],
            "outcome_digest": contract["outcome_digest"],
            "scope_definition_sha256": SCOPE.scope_definition_sha256(contract),
        },
        "authentication": {
            "scheme": SCOPE.AUTH_SCHEME,
            "key_id": "company-os-repository-test-v1",
            "signature": "0" * 64,
        },
    }
    decision["authentication"]["signature"] = SCOPE.fixture_signature(decision)
    contract["accepted_design_decision"] = canonical_file(
        root, "evidence/release-scope-design.v1.json", decision
    )
    return contract


def bound_force_contract(task_id: str) -> dict:
    contract = force_contract()
    contract["task_id"] = task_id
    return contract


def bound_force_events(
    task_id: str,
    artifact: dict[str, str],
    worker_receipt: dict[str, str],
    disposition: str,
    rework_cycles: int,
    prior_artifact: dict[str, str] | None = None,
) -> list[dict]:
    if rework_cycles not in {0, 1}:
        raise AssertionError("test fixture supports zero or one rework cycle")
    if rework_cycles == 1 and prior_artifact is None:
        raise AssertionError("rework fixture requires prior artifact evidence")
    values: list[dict] = []

    def append(name: str, evidence: dict | None = None) -> None:
        sequence = len(values) + 1
        values.append(
            {
                **force_event(sequence, name, 990 + (sequence * 10), evidence),
                "task_id": task_id,
            }
        )

    append("task_started")
    if rework_cycles == 1:
        assert prior_artifact is not None
        append("artifact_materialized", prior_artifact)
        append("candidate_runnable", {"artifact_paths": [prior_artifact["path"]]})
        append("verification_passed", {"check": "first-pass oracle"})
        append("manager_inspection_failed", {"defects": ["bounded rework required"]})
        append("manager_rework", {"defects": ["bounded rework required"]})
        append("rework_started", {"defects": ["bounded rework required"]})
    append("artifact_materialized", artifact)
    append("candidate_runnable", {"artifact_paths": [artifact["path"]]})
    append("verification_passed", {"check": "independent oracle"})
    if disposition == "accepted":
        append("manager_inspection_passed", {"artifact_paths": [artifact["path"]]})
        append("receipt_materialized", worker_receipt)
        append("manager_accept")
    else:
        append("manager_inspection_failed", {"defects": ["quality threshold not met"]})
        append("manager_reject", {"reason": "quality threshold not met"})
    return values


def terminal_receipt(
    root: Path,
    contract: dict,
    deliverable_id: str,
    attempt_chain: int,
    disposition: str,
    rework_cycles: int,
    variant: str = "",
) -> dict[str, str]:
    slug = f"{deliverable_id}-chain-{attempt_chain}"
    if variant:
        slug = f"{slug}-{variant}"
    task_id = f"{slug}-worker"
    artifact = exact_file(
        root,
        f"release/{slug}.bin",
        f"{slug}:{disposition}".encode("utf-8"),
    )
    worker_receipt = exact_file(
        root,
        f"evidence/force/{slug}.worker-receipt.json",
        f"worker-receipt:{slug}".encode("utf-8"),
    )
    prior_artifact = None
    if rework_cycles == 1:
        prior_artifact = exact_file(
            root,
            f"release/{slug}.first-pass.bin",
            f"{slug}:first-pass".encode("utf-8"),
        )
    force_contract_reference = canonical_file(
        root,
        f"evidence/force/{slug}.contract.json",
        bound_force_contract(task_id),
    )
    events_relative = f"evidence/force/{slug}.events.jsonl"
    events_path = root / events_relative
    write_events(
        events_path,
        bound_force_events(
            task_id,
            artifact,
            worker_receipt,
            disposition,
            rework_cycles,
            prior_artifact,
        ),
    )
    snapshot_relative = f"evidence/force/{slug}.sealed.jsonl"
    snapshot_receipt_relative = f"evidence/force/{slug}.snapshot-receipt.json"
    SNAPSHOT.seal(
        root / force_contract_reference["path"],
        events_path,
        root,
        snapshot_relative,
        snapshot_receipt_relative,
    )
    snapshot_receipt = exact_file(
        root,
        snapshot_receipt_relative,
        (root / snapshot_receipt_relative).read_bytes(),
    )
    receipt = {
        "schema": "company-os.release-deliverable-receipt.v1",
        "project_id": contract["project_id"],
        "program_id": contract["program_id"],
        "program_version": contract["program_version"],
        "definition_version": contract["definition_version"],
        "cycle_id": contract["cycle_id"],
        "deliverable_id": deliverable_id,
        "manager_task_id": next(
            item["manager_task_id"]
            for item in contract["deliverables"]
            if item["deliverable_id"] == deliverable_id
        ),
        "attempt_chain": attempt_chain,
        "force_task_id": task_id,
        "rework_cycles": rework_cycles,
        "disposition": disposition,
        "force_contract": force_contract_reference,
        "terminal_force_snapshot_receipt": snapshot_receipt,
        "quality_score": 9.2 if disposition == "accepted" else 8.0,
        "quality_gate_lowered": False,
        "defects": [] if disposition == "accepted" else ["quality threshold not met"],
        "artifact_evidence": [artifact],
        "authentication": {
            "scheme": SCOPE.AUTH_SCHEME,
            "key_id": "company-os-repository-test-v1",
            "signature": "0" * 64,
        },
    }
    receipt["authentication"]["signature"] = SCOPE.fixture_signature(receipt)
    return canonical_file(root, f"evidence/terminal/{slug}.json", receipt)


def release_status(root: Path, contract: dict) -> dict:
    core = terminal_receipt(root, contract, "core-launch-package", 1, "accepted", 1)
    seasonal_first = terminal_receipt(root, contract, "seasonal-panel", 1, "rejected", 1)
    seasonal_second = terminal_receipt(root, contract, "seasonal-panel", 2, "rejected", 1)
    return {
        "schema": "company-os.release-status.v1",
        "project_id": contract["project_id"],
        "program_id": contract["program_id"],
        "program_version": contract["program_version"],
        "definition_version": contract["definition_version"],
        "cycle_id": contract["cycle_id"],
        "scope_contract_sha256": SCOPE.canonical_sha256(contract),
        "deliverables": [
            {
                "deliverable_id": "core-launch-package",
                "disposition": "accepted",
                "attempt_chains": 1,
                "rework_cycles": 1,
                "evidence": {"terminal_receipts": [core]},
            },
            {
                "deliverable_id": "seasonal-panel",
                "disposition": "rejected",
                "attempt_chains": 2,
                "rework_cycles": 2,
                "evidence": {"terminal_receipts": [seasonal_first, seasonal_second]},
            },
        ],
    }


class ReleaseScopeTests(unittest.TestCase):
    def prepare(self, root: Path) -> tuple[dict, dict]:
        (root / "release").mkdir()
        (root / "evidence").mkdir()
        contract = release_contract(root)
        status = release_status(root, contract)
        return contract, status

    def test_optional_failure_produces_explicit_graceful_degradation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = SCOPE.validate_contract(contract, root)
            status_value = SCOPE.validate_status(contract_value, status, root)
            result = SCOPE.evaluate(contract_value, status_value)
            self.assertEqual(
                "eligible_for_core_acceptance_with_graceful_degradation",
                result["decision"],
            )
            self.assertEqual(["seasonal-panel"], result["omitted_optional_deliverables"])
            self.assertFalse(result["quality_gate_lowered"])
            self.assertFalse(result["master_acceptance_inferred"])
            self.assertEqual(
                "request_authenticated_master_scope_decision", result["next_action"]
            )

    def test_rejected_required_deliverable_blocks_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status_value = self.prepare(root)
            contract_value = SCOPE.validate_contract(contract, root)
            core = status_value["deliverables"][0]
            core["disposition"] = "rejected"
            core["rework_cycles"] = 1
            core["evidence"] = {
                "terminal_receipts": [
                    terminal_receipt(
                        root,
                        contract,
                        "core-launch-package",
                        1,
                        "rejected",
                        1,
                        "required-reject",
                    )
                ]
            }
            accepted_status = SCOPE.validate_status(contract_value, status_value, root)
            result = SCOPE.evaluate(contract_value, accepted_status)
            self.assertEqual("release_blocked", result["decision"])
            self.assertEqual(["core-launch-package"], result["rejected_required_deliverables"])

    def test_optional_recovery_cap_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status_value = self.prepare(root)
            contract_value = SCOPE.validate_contract(contract, root)
            optional = status_value["deliverables"][1]
            optional["attempt_chains"] = 3
            optional["rework_cycles"] = 3
            optional["evidence"]["terminal_receipts"].append(
                terminal_receipt(root, contract, "seasonal-panel", 3, "rejected", 1)
            )
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "recovery-chain cap"):
                SCOPE.validate_status(contract_value, status_value, root)

    def test_optional_omission_requires_recovery_cap_exhaustion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = SCOPE.validate_contract(contract, root)
            optional = status["deliverables"][1]
            optional["attempt_chains"] = 1
            optional["rework_cycles"] = 1
            optional["evidence"]["terminal_receipts"] = optional["evidence"][
                "terminal_receipts"
            ][:1]
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "cap exhaustion"):
                SCOPE.validate_status(contract_value, status, root)

    def test_scope_mutation_requires_a_new_master_design_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, _ = self.prepare(root)
            contract["deliverables"][1]["criticality"] = "required"
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "exact pre-dispatch scope"):
                SCOPE.validate_contract(contract, root)

    def test_forged_master_design_signature_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, _ = self.prepare(root)
            decision_path = root / contract["accepted_design_decision"]["path"]
            decision = json.loads(decision_path.read_text(encoding="utf-8"))
            decision["authentication"]["signature"] = "f" * 64
            contract["accepted_design_decision"] = canonical_file(
                root, contract["accepted_design_decision"]["path"], decision
            )
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "does not verify"):
                SCOPE.validate_contract(contract, root)

    def test_plain_failure_bytes_cannot_satisfy_terminal_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = SCOPE.validate_contract(contract, root)
            plain = exact_file(root, "evidence/plain-failure.txt", b"failed")
            status["deliverables"][1]["evidence"]["terminal_receipts"][0] = plain
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "canonical JSON"):
                SCOPE.validate_status(contract_value, status, root)

    def test_terminal_receipt_cannot_claim_uninspected_artifacts_or_manager(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = SCOPE.validate_contract(contract, root)
            reference = status["deliverables"][0]["evidence"]["terminal_receipts"][0]
            receipt = json.loads((root / reference["path"]).read_text(encoding="utf-8"))
            receipt["artifact_evidence"].append(
                exact_file(root, "release/uninspected.bin", b"not inspected")
            )
            receipt["authentication"]["signature"] = SCOPE.fixture_signature(receipt)
            status["deliverables"][0]["evidence"]["terminal_receipts"][0] = canonical_file(
                root, reference["path"], receipt
            )
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "terminal force candidate"):
                SCOPE.validate_status(contract_value, status, root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = SCOPE.validate_contract(contract, root)
            reference = status["deliverables"][0]["evidence"]["terminal_receipts"][0]
            receipt = json.loads((root / reference["path"]).read_text(encoding="utf-8"))
            receipt["manager_task_id"] = "different-manager-1"
            receipt["authentication"]["signature"] = SCOPE.fixture_signature(receipt)
            status["deliverables"][0]["evidence"]["terminal_receipts"][0] = canonical_file(
                root, reference["path"], receipt
            )
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "exact release scope"):
                SCOPE.validate_status(contract_value, status, root)

    def test_terminal_receipt_signature_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = SCOPE.validate_contract(contract, root)
            reference = status["deliverables"][0]["evidence"]["terminal_receipts"][0]
            receipt = json.loads((root / reference["path"]).read_text(encoding="utf-8"))
            receipt["authentication"]["signature"] = "e" * 64
            status["deliverables"][0]["evidence"]["terminal_receipts"][0] = canonical_file(
                root, reference["path"], receipt
            )
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "does not verify"):
                SCOPE.validate_status(contract_value, status, root)

    def test_terminal_receipt_rework_count_must_match_force_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = SCOPE.validate_contract(contract, root)
            reference = status["deliverables"][0]["evidence"]["terminal_receipts"][0]
            receipt = json.loads((root / reference["path"]).read_text(encoding="utf-8"))
            receipt["rework_cycles"] = 0
            receipt["authentication"]["signature"] = SCOPE.fixture_signature(receipt)
            status["deliverables"][0]["rework_cycles"] = 0
            status["deliverables"][0]["evidence"]["terminal_receipts"][0] = canonical_file(
                root, reference["path"], receipt
            )
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "sealed force evidence"):
                SCOPE.validate_status(contract_value, status, root)

    def test_terminal_snapshot_and_quality_gate_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = SCOPE.validate_contract(contract, root)
            reference = status["deliverables"][0]["evidence"]["terminal_receipts"][0]
            receipt_path = root / reference["path"]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["quality_gate_lowered"] = True
            receipt["authentication"]["signature"] = SCOPE.fixture_signature(receipt)
            status["deliverables"][0]["evidence"]["terminal_receipts"][0] = canonical_file(
                root, reference["path"], receipt
            )
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "lowered a quality gate"):
                SCOPE.validate_status(contract_value, status, root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = SCOPE.validate_contract(contract, root)
            reference = status["deliverables"][0]["evidence"]["terminal_receipts"][0]
            receipt = json.loads((root / reference["path"]).read_text(encoding="utf-8"))
            snapshot_reference = receipt["terminal_force_snapshot_receipt"]
            snapshot_receipt = json.loads(
                (root / snapshot_reference["path"]).read_text(encoding="utf-8")
            )
            snapshot_path = root / snapshot_receipt["snapshot_path"]
            snapshot_path.write_bytes(snapshot_path.read_bytes() + b'{}\n')
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "digest does not match"):
                SCOPE.validate_status(contract_value, status, root)

    def test_scope_and_failure_evidence_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = SCOPE.validate_contract(contract, root)
            missing = json.loads(json.dumps(status))
            missing["deliverables"] = missing["deliverables"][:1]
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "scope differs"):
                SCOPE.validate_status(contract_value, missing, root)

            no_receipt = json.loads(json.dumps(status))
            no_receipt["deliverables"][1]["evidence"]["terminal_receipts"] = []
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "cover every attempt"):
                SCOPE.validate_status(contract_value, no_receipt, root)

            tampered = json.loads(json.dumps(status))
            tampered["deliverables"][1]["evidence"]["terminal_receipts"][0]["sha256"] = "0" * 64
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "digest does not match"):
                SCOPE.validate_status(contract_value, tampered, root)


if __name__ == "__main__":
    unittest.main()
