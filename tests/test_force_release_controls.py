from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import subprocess
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


def generate_key_pair(root: Path, name: str) -> dict[str, Path]:
    private_key = root / f"{name}.private.pem"
    public_key = root / f"{name}.public.pem"
    subprocess.run(
        [
            "openssl",
            "genpkey",
            "-algorithm",
            "RSA",
            "-pkeyopt",
            "rsa_keygen_bits:3072",
            "-out",
            str(private_key),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
        check=True,
        capture_output=True,
    )
    return {"private": private_key, "public": public_key}


def sign_record(record: dict, keys: dict[str, Path], key_id: str) -> None:
    record["authentication"] = {
        "scheme": SCOPE.AUTH_SCHEME,
        "key_id": key_id,
        "public_key_sha256": hashlib.sha256(keys["public"].read_bytes()).hexdigest(),
        "signature": "A" * 512,
    }
    signed = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", str(keys["private"])],
        input=SCOPE.signature_payload(record),
        check=True,
        capture_output=True,
    ).stdout
    record["authentication"]["signature"] = (
        base64.urlsafe_b64encode(signed).decode("ascii").rstrip("=")
    )


def release_contract(
    root: Path,
    keys: dict[str, dict[str, Path]],
    trusted_admission_registry: Path,
    *,
    definition_version: int = 1,
    predecessor_reference: dict[str, str] | None = None,
    seasonal_criticality: str = "optional",
) -> dict:
    admission_path = f"evidence/release-scope-admission.v{definition_version}.json"
    admission_verification_path = (
        f"evidence/release-scope-admission-verification.v{definition_version}.json"
    )
    manager_charters: dict[str, dict[str, str]] = {}
    for manager in ("operations-manager-1", "commercial-manager-1"):
        charter = {
            "schema": "company-os.mission-charter.v2",
            "program_version": 1,
            "definition_version": definition_version,
            "ids": {
                "project_id": "hearthpod",
                "program_id": "hearthpod-launch",
                "cycle_id": "launch-cycle-1",
                "task_id": manager,
                "parent_task_id": "hearthpod-master-1",
            },
            "outcome_digest": "a" * 64,
            "task_local_context": {
                "artifact_paths": [admission_path, admission_verification_path]
            },
        }
        manager_charters[manager] = canonical_file(
            root,
            f"evidence/charters/{manager}.v{definition_version}.json",
            charter,
        )
    manager_keys = {
        manager: exact_file(
            root,
            f"evidence/keys/{manager}.public.pem",
            keys[manager]["public"].read_bytes(),
        )
        for manager in ("operations-manager-1", "commercial-manager-1")
    }
    contract = {
        "schema": "company-os.release-scope.v1",
        "project_id": "hearthpod",
        "program_id": "hearthpod-launch",
        "program_version": 1,
        "definition_version": definition_version,
        "cycle_id": "launch-cycle-1",
        "master_task_id": "hearthpod-master-1",
        "outcome_digest": "a" * 64,
        "predecessor_admission_sha256": (
            predecessor_reference["sha256"] if predecessor_reference else "0" * 64
        ),
        "predecessor_scope_admission": predecessor_reference,
        "admission_verification_path": admission_verification_path,
        "deliverables": [
            {
                "deliverable_id": "core-launch-package",
                "manager_task_id": "operations-manager-1",
                "manager_public_key": manager_keys["operations-manager-1"],
                "manager_charter": manager_charters["operations-manager-1"],
                "criticality": "required",
                "outcome_contribution": "Provides the decision-useful company launch package.",
            },
            {
                "deliverable_id": "seasonal-panel",
                "manager_task_id": "commercial-manager-1",
                "manager_public_key": manager_keys["commercial-manager-1"],
                "manager_charter": manager_charters["commercial-manager-1"],
                "criticality": seasonal_criticality,
                "outcome_contribution": "Adds a seasonal campaign comparison without changing the core offer.",
            },
        ],
        "policy": {
            "required_failure": "block_release",
            "optional_failure": "omit_without_quality_relaxation",
            "max_optional_recovery_chains": 1,
        },
        "accepted_design_decision": {
            "path": f"evidence/release-scope-design.v{definition_version}.json",
            "sha256": "0" * 64,
        },
        "scope_admission": {
            "path": admission_path,
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
            "predecessor_admission_sha256": contract["predecessor_admission_sha256"],
            "scope_definition_sha256": SCOPE.scope_definition_sha256(contract),
        },
        "authentication": {},
    }
    sign_record(decision, keys["master"], "hearthpod-master-key-1")
    contract["accepted_design_decision"] = canonical_file(
        root, f"evidence/release-scope-design.v{definition_version}.json", decision
    )
    admission = {
        "schema": SCOPE.ADMISSION_SCHEMA,
        "record_version": 1,
        "admission_id": f"hearthpod-launch-scope-{definition_version}",
        "decision": "admitted_pre_dispatch",
        "bindings": {
            "project_id": contract["project_id"],
            "program_id": contract["program_id"],
            "program_version": contract["program_version"],
            "definition_version": contract["definition_version"],
            "cycle_id": contract["cycle_id"],
            "master_task_id": contract["master_task_id"],
            "outcome_digest": contract["outcome_digest"],
            "scope_definition_sha256": SCOPE.scope_definition_sha256(contract),
            "predecessor_admission_sha256": contract["predecessor_admission_sha256"],
            "accepted_design_decision_sha256": contract["accepted_design_decision"]["sha256"],
        },
        "accepted_design_decision": contract["accepted_design_decision"],
        "authentication": {},
    }
    sign_record(admission, keys["master"], "hearthpod-master-key-1")
    contract["scope_admission"] = canonical_file(
        root,
        f"evidence/release-scope-admission.v{definition_version}.json",
        admission,
    )
    SCOPE.write_admission_verification(
        contract,
        root,
        keys["master"]["public"],
        trusted_admission_registry,
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
    inspected_rejection: bool = True,
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
        if inspected_rejection:
            append("manager_inspection_failed", {"defects": ["quality threshold not met"]})
        append("manager_reject", {"reason": "quality threshold not met"})
    return values


def terminal_receipt(
    root: Path,
    contract: dict,
    keys: dict[str, dict[str, Path]],
    deliverable_id: str,
    attempt_chain: int,
    disposition: str,
    rework_cycles: int,
    variant: str = "",
    inspected_rejection: bool = True,
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
            inspected_rejection,
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
        "manager_charter": next(
            item["manager_charter"]
            for item in contract["deliverables"]
            if item["deliverable_id"] == deliverable_id
        ),
        "scope_admission_verification": exact_file(
            root,
            contract["admission_verification_path"],
            (root / contract["admission_verification_path"]).read_bytes(),
        ),
        "force_contract": force_contract_reference,
        "terminal_force_snapshot_receipt": snapshot_receipt,
        "quality_score": 9.2 if disposition == "accepted" else 8.0,
        "quality_gate_lowered": False,
        "defects": [] if disposition == "accepted" else ["quality threshold not met"],
        "artifact_evidence": [artifact],
        "authentication": {},
    }
    sign_record(
        receipt,
        keys[receipt["manager_task_id"]],
        f"{receipt['manager_task_id']}-key-1",
    )
    return canonical_file(root, f"evidence/terminal/{slug}.json", receipt)


def release_status(
    root: Path, contract: dict, keys: dict[str, dict[str, Path]]
) -> dict:
    core = terminal_receipt(
        root, contract, keys, "core-launch-package", 1, "accepted", 1
    )
    seasonal_first = terminal_receipt(
        root, contract, keys, "seasonal-panel", 1, "rejected", 1
    )
    seasonal_second = terminal_receipt(
        root, contract, keys, "seasonal-panel", 2, "rejected", 1
    )
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
    @classmethod
    def setUpClass(cls) -> None:
        cls.key_directory = tempfile.TemporaryDirectory()
        key_root = Path(cls.key_directory.name)
        cls.keys = {
            name: generate_key_pair(key_root, name)
            for name in (
                "master",
                "operations-manager-1",
                "commercial-manager-1",
                "attacker",
            )
        }
        cls.master_public_key = cls.keys["master"]["public"]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.key_directory.cleanup()

    def resign_terminal_receipt(self, receipt: dict) -> None:
        manager_task_id = receipt["manager_task_id"]
        sign_record(
            receipt,
            self.keys[manager_task_id],
            f"{manager_task_id}-key-1",
        )

    def registry_for(self, root: Path) -> Path:
        digest = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:24]
        registry = Path(self.key_directory.name) / "registries" / digest
        registry.mkdir(parents=True, exist_ok=True)
        return registry

    def prepare(self, root: Path) -> tuple[dict, dict]:
        (root / "release").mkdir()
        (root / "evidence").mkdir()
        contract = release_contract(root, self.keys, self.registry_for(root))
        status = release_status(root, contract, self.keys)
        return contract, status

    def validate_contract(self, contract: dict, root: Path) -> dict:
        return SCOPE.validate_contract(
            contract,
            root,
            self.master_public_key,
            self.registry_for(root),
        )

    def validate_status(self, contract: dict, status: dict, root: Path) -> dict:
        return SCOPE.validate_status(
            contract,
            status,
            root,
            self.master_public_key,
            self.registry_for(root),
        )

    def resign_scope_evidence(
        self,
        contract: dict,
        root: Path,
        signing_keys: dict[str, Path],
        key_id: str,
    ) -> None:
        decision_path = root / contract["accepted_design_decision"]["path"]
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        decision["bindings"]["scope_definition_sha256"] = (
            SCOPE.scope_definition_sha256(contract)
        )
        sign_record(decision, signing_keys, key_id)
        contract["accepted_design_decision"] = canonical_file(
            root,
            contract["accepted_design_decision"]["path"],
            decision,
        )
        admission_path = root / contract["scope_admission"]["path"]
        admission = json.loads(admission_path.read_text(encoding="utf-8"))
        admission["bindings"]["scope_definition_sha256"] = (
            SCOPE.scope_definition_sha256(contract)
        )
        admission["bindings"]["accepted_design_decision_sha256"] = contract[
            "accepted_design_decision"
        ]["sha256"]
        admission["accepted_design_decision"] = contract["accepted_design_decision"]
        sign_record(admission, signing_keys, key_id)
        contract["scope_admission"] = canonical_file(
            root,
            contract["scope_admission"]["path"],
            admission,
        )

    def test_optional_failure_produces_explicit_graceful_degradation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = self.validate_contract(contract, root)
            status_value = self.validate_status(contract_value, status, root)
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
            contract_value = self.validate_contract(contract, root)
            core = status_value["deliverables"][0]
            core["disposition"] = "rejected"
            core["rework_cycles"] = 1
            core["evidence"] = {
                "terminal_receipts": [
                    terminal_receipt(
                        root,
                        contract,
                        self.keys,
                        "core-launch-package",
                        1,
                        "rejected",
                        1,
                        "required-reject",
                    )
                ]
            }
            accepted_status = self.validate_status(contract_value, status_value, root)
            result = SCOPE.evaluate(contract_value, accepted_status)
            self.assertEqual("release_blocked", result["decision"])
            self.assertEqual(["core-launch-package"], result["rejected_required_deliverables"])

    def test_optional_recovery_cap_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status_value = self.prepare(root)
            contract_value = self.validate_contract(contract, root)
            optional = status_value["deliverables"][1]
            optional["attempt_chains"] = 3
            optional["rework_cycles"] = 3
            optional["evidence"]["terminal_receipts"].append(
                terminal_receipt(
                    root,
                    contract,
                    self.keys,
                    "seasonal-panel",
                    3,
                    "rejected",
                    1,
                )
            )
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "recovery-chain cap"):
                self.validate_status(contract_value, status_value, root)

    def test_optional_omission_requires_recovery_cap_exhaustion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = self.validate_contract(contract, root)
            optional = status["deliverables"][1]
            optional["attempt_chains"] = 1
            optional["rework_cycles"] = 1
            optional["evidence"]["terminal_receipts"] = optional["evidence"][
                "terminal_receipts"
            ][:1]
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "cap exhaustion"):
                self.validate_status(contract_value, status, root)

    def test_scope_mutation_requires_a_new_master_design_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, _ = self.prepare(root)
            contract["deliverables"][1]["criticality"] = "required"
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "exact pre-dispatch scope"):
                self.validate_contract(contract, root)

    def test_same_version_master_resign_cannot_replace_registered_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, _ = self.prepare(root)
            contract["deliverables"][0]["manager_task_id"] = "commercial-manager-1"
            contract["deliverables"][0]["manager_public_key"] = contract[
                "deliverables"
            ][1]["manager_public_key"]
            contract["deliverables"][0]["manager_charter"] = contract[
                "deliverables"
            ][1]["manager_charter"]
            contract["deliverables"][1]["criticality"] = "required"
            self.resign_scope_evidence(
                contract,
                root,
                self.keys["master"],
                "hearthpod-master-key-1",
            )
            with self.assertRaisesRegex(
                SCOPE.ReleaseScopeError,
                "already registered with different bytes",
            ):
                SCOPE.write_admission_verification(
                    contract,
                    root,
                    self.master_public_key,
                    self.registry_for(root),
                )

    def test_scope_change_requires_exact_next_registered_predecessor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "release").mkdir()
            (root / "evidence").mkdir()
            registry = self.registry_for(root)
            first = release_contract(root, self.keys, registry)
            second = release_contract(
                root,
                self.keys,
                registry,
                definition_version=2,
                predecessor_reference=first["scope_admission"],
                seasonal_criticality="required",
            )
            accepted = self.validate_contract(second, root)
            self.assertEqual(2, accepted["definition_version"])
            with self.assertRaisesRegex(
                SCOPE.ReleaseScopeError,
                "not the current exact trusted admission",
            ):
                SCOPE.validate_contract(
                    first,
                    root,
                    self.master_public_key,
                    registry,
                )

    def test_trust_anchor_and_registry_must_be_outside_artifact_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, _ = self.prepare(root)
            in_project_key = root / "evidence/master.public.pem"
            in_project_key.write_bytes(self.master_public_key.read_bytes())
            with self.assertRaisesRegex(
                SCOPE.ReleaseScopeError,
                "outside the artifact root",
            ):
                SCOPE.validate_contract(
                    contract,
                    root,
                    in_project_key,
                    self.registry_for(root),
                )
            with self.assertRaisesRegex(
                SCOPE.ReleaseScopeError,
                "outside the artifact root",
            ):
                SCOPE.validate_contract(
                    contract,
                    root,
                    self.master_public_key,
                    root / "evidence",
                )

    def test_pre_dispatch_admission_gate_is_exact_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, _ = self.prepare(root)
            first = SCOPE.write_admission_verification(
                contract,
                root,
                self.master_public_key,
                self.registry_for(root),
            )
            second = SCOPE.write_admission_verification(
                contract,
                root,
                self.master_public_key,
                self.registry_for(root),
            )
            self.assertEqual(first, second)
            self.assertEqual(
                contract["admission_verification_path"],
                first["evidence"]["path"],
            )

    def test_packaged_templates_match_external_rsa_admission_contract(self) -> None:
        skill_root = ROOT / "skills/company-os/force-first-execution"
        assets = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in (skill_root / "assets").glob("release-*.json")
        }
        scope = assets["release-scope.v1.json"]
        self.assertEqual("0" * 64, scope["predecessor_admission_sha256"])
        self.assertIsNone(scope["predecessor_scope_admission"])
        self.assertTrue(scope["admission_verification_path"].endswith(".v1.json"))
        self.assertTrue(
            all(
                {"manager_public_key", "manager_charter"}.issubset(deliverable)
                for deliverable in scope["deliverables"]
            )
        )
        for name in (
            "release-scope-design-decision.v1.json",
            "release-scope-admission.v1.json",
            "release-deliverable-receipt.v1.json",
        ):
            authentication = assets[name]["authentication"]
            self.assertEqual(SCOPE.AUTH_SCHEME, authentication["scheme"])
            self.assertEqual(64, len(authentication["public_key_sha256"]))
            self.assertEqual(512, len(authentication["signature"]))
        verification = assets["release-scope-admission-verification.v1.json"]
        self.assertIn("registry_record_sha256", verification)
        self.assertIn("scope_contract_sha256", verification)

    def test_forged_master_design_signature_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, _ = self.prepare(root)
            decision_path = root / contract["accepted_design_decision"]["path"]
            decision = json.loads(decision_path.read_text(encoding="utf-8"))
            decision["authentication"]["signature"] = "A" * 512
            contract["accepted_design_decision"] = canonical_file(
                root, contract["accepted_design_decision"]["path"], decision
            )
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "does not verify"):
                self.validate_contract(contract, root)

    def test_plain_failure_bytes_cannot_satisfy_terminal_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = self.validate_contract(contract, root)
            plain = exact_file(root, "evidence/plain-failure.txt", b"failed")
            status["deliverables"][1]["evidence"]["terminal_receipts"][0] = plain
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "canonical JSON"):
                self.validate_status(contract_value, status, root)

    def test_terminal_receipt_cannot_claim_uninspected_artifacts_or_manager(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = self.validate_contract(contract, root)
            reference = status["deliverables"][0]["evidence"]["terminal_receipts"][0]
            receipt = json.loads((root / reference["path"]).read_text(encoding="utf-8"))
            receipt["artifact_evidence"].append(
                exact_file(root, "release/uninspected.bin", b"not inspected")
            )
            self.resign_terminal_receipt(receipt)
            status["deliverables"][0]["evidence"]["terminal_receipts"][0] = canonical_file(
                root, reference["path"], receipt
            )
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "terminal force candidate"):
                self.validate_status(contract_value, status, root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = self.validate_contract(contract, root)
            reference = status["deliverables"][0]["evidence"]["terminal_receipts"][0]
            receipt = json.loads((root / reference["path"]).read_text(encoding="utf-8"))
            receipt["manager_task_id"] = "different-manager-1"
            sign_record(
                receipt,
                self.keys["operations-manager-1"],
                "operations-manager-1-key-1",
            )
            status["deliverables"][0]["evidence"]["terminal_receipts"][0] = canonical_file(
                root, reference["path"], receipt
            )
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "exact release scope"):
                self.validate_status(contract_value, status, root)

    def test_uninspected_rejection_cannot_support_graceful_degradation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = self.validate_contract(contract, root)
            status["deliverables"][1]["evidence"]["terminal_receipts"][0] = (
                terminal_receipt(
                    root,
                    contract,
                    self.keys,
                    "seasonal-panel",
                    1,
                    "rejected",
                    1,
                    "uninspected",
                    inspected_rejection=False,
                )
            )
            with self.assertRaisesRegex(
                SCOPE.ReleaseScopeError,
                "rejection lacks verified failed inspection",
            ):
                self.validate_status(contract_value, status, root)

    def test_terminal_receipt_signature_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = self.validate_contract(contract, root)
            reference = status["deliverables"][0]["evidence"]["terminal_receipts"][0]
            receipt = json.loads((root / reference["path"]).read_text(encoding="utf-8"))
            receipt["authentication"]["signature"] = "A" * 512
            status["deliverables"][0]["evidence"]["terminal_receipts"][0] = canonical_file(
                root, reference["path"], receipt
            )
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "does not verify"):
                self.validate_status(contract_value, status, root)

    def test_terminal_receipt_rework_count_must_match_force_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = self.validate_contract(contract, root)
            reference = status["deliverables"][0]["evidence"]["terminal_receipts"][0]
            receipt = json.loads((root / reference["path"]).read_text(encoding="utf-8"))
            receipt["rework_cycles"] = 0
            self.resign_terminal_receipt(receipt)
            status["deliverables"][0]["rework_cycles"] = 0
            status["deliverables"][0]["evidence"]["terminal_receipts"][0] = canonical_file(
                root, reference["path"], receipt
            )
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "sealed force evidence"):
                self.validate_status(contract_value, status, root)

    def test_terminal_snapshot_and_quality_gate_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = self.validate_contract(contract, root)
            reference = status["deliverables"][0]["evidence"]["terminal_receipts"][0]
            receipt_path = root / reference["path"]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["quality_gate_lowered"] = True
            self.resign_terminal_receipt(receipt)
            status["deliverables"][0]["evidence"]["terminal_receipts"][0] = canonical_file(
                root, reference["path"], receipt
            )
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "lowered a quality gate"):
                self.validate_status(contract_value, status, root)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = self.validate_contract(contract, root)
            reference = status["deliverables"][0]["evidence"]["terminal_receipts"][0]
            receipt = json.loads((root / reference["path"]).read_text(encoding="utf-8"))
            snapshot_reference = receipt["terminal_force_snapshot_receipt"]
            snapshot_receipt = json.loads(
                (root / snapshot_reference["path"]).read_text(encoding="utf-8")
            )
            snapshot_path = root / snapshot_receipt["snapshot_path"]
            snapshot_path.write_bytes(snapshot_path.read_bytes() + b'{}\n')
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "digest does not match"):
                self.validate_status(contract_value, status, root)

    def test_scope_and_failure_evidence_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, status = self.prepare(root)
            contract_value = self.validate_contract(contract, root)
            missing = json.loads(json.dumps(status))
            missing["deliverables"] = missing["deliverables"][:1]
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "scope differs"):
                self.validate_status(contract_value, missing, root)

            no_receipt = json.loads(json.dumps(status))
            no_receipt["deliverables"][1]["evidence"]["terminal_receipts"] = []
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "cover every attempt"):
                self.validate_status(contract_value, no_receipt, root)

            tampered = json.loads(json.dumps(status))
            tampered["deliverables"][1]["evidence"]["terminal_receipts"][0]["sha256"] = "0" * 64
            with self.assertRaisesRegex(SCOPE.ReleaseScopeError, "digest does not match"):
                self.validate_status(contract_value, tampered, root)


if __name__ == "__main__":
    unittest.main()
