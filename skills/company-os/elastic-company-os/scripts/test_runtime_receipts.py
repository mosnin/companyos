#!/usr/bin/env python3

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path


MODULE = Path(__file__).resolve().with_name("runtime_receipts.py")
SPEC = importlib.util.spec_from_file_location("company_os_runtime_receipts", MODULE)
assert SPEC and SPEC.loader
receipts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(receipts)

GATEWAY_MODULE = Path(__file__).resolve().with_name("runtime_gateway.py")
GATEWAY_SPEC = importlib.util.spec_from_file_location("company_os_runtime_gateway_receipt_test", GATEWAY_MODULE)
assert GATEWAY_SPEC and GATEWAY_SPEC.loader
gateway = importlib.util.module_from_spec(GATEWAY_SPEC)
GATEWAY_SPEC.loader.exec_module(gateway)

LIFECYCLE_MODULE = Path(__file__).resolve().with_name("runtime_lifecycle.py")
LIFECYCLE_SPEC = importlib.util.spec_from_file_location("company_os_runtime_lifecycle_receipt_test", LIFECYCLE_MODULE)
assert LIFECYCLE_SPEC and LIFECYCLE_SPEC.loader
lifecycle_rules = importlib.util.module_from_spec(LIFECYCLE_SPEC)
LIFECYCLE_SPEC.loader.exec_module(lifecycle_rules)


def digest(character: str) -> str:
    return character * 64


class RuntimeReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.private = self.root / "private.pem"
        self.public = self.root / "public.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(self.private)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(self.private), "-pubout", "-out", str(self.public)],
            check=True,
            capture_output=True,
        )
        self.now = datetime.now(timezone.utc)
        self.keyring = self.root / "keyring.json"
        self.keyring.write_text(json.dumps({
            "schema": "company-os.runtime-gateway-keyring.v1",
            "keys": [{
                "key_id": "gateway-1", "algorithm": "rsa-sha256",
                "public_key_path": str(self.public), "status": "active",
                "not_before": (self.now - timedelta(hours=1)).isoformat(),
                "not_after": (self.now + timedelta(hours=1)).isoformat(),
            }],
        }), encoding="utf-8")
        self.attempt = {
            "attempt_id": "manager-attempt",
            "project_id": "company-os-core",
            "manifest_identity_id": "manager-1",
            "program_version": 6,
            "work_id": "work-runtime-v6",
            "cycle_id": "cycle-1",
            "parent_runtime_id": "master",
            "role": "manager",
            "requested_model": "gpt-5.6-sol",
            "provider": "provider-a",
            "surface": "isolated-task",
            "account": "workspace-a",
            "scope": [".company-os/runtime-artifacts"],
            "scope_digest": digest("1"),
            "budget": {
                "time_minutes": 10,
                "token_limit": 2000,
                "cost_usd": 1.0,
                "max_concurrency": 1,
                "max_retries": 0,
            },
            "capabilities": ["emit_artifact", "read_project"],
            "fabric_manifest_digest": digest("2"),
            "phase2_contract_digest": digest("3"),
            "idempotency_key": "manager-launch-1",
            "lifecycle": {
                "status": "succeeded",
                "terminal_status": "succeeded",
                "terminal_authority": "provider_observation",
                "terminal_decision_digest": None,
                "terminal_provider_event_id": "event-terminal-manager",
                "provider_task_id": "provider-task-manager",
                "observed_model": "gpt-5.6-sol",
                "model_evidence_digest": digest("4"),
                "terminal_observation_digest": digest("5"),
                "telemetry": {
                    "input_tokens": 100,
                    "cached_input_tokens": 20,
                    "output_tokens": 25,
                    "total_tokens": 125,
                    "cost_usd": 0.01,
                    "currency": "USD",
                    "semantics": "terminal",
                    "provider_revision": "usage-2",
                    "source_observation_digests": [digest("5")],
                    "provider_revisions": ["usage-2"],
                },
                "receipt": None,
                "reconciliation": None,
            },
        }
        self.sequence = 0
        self.child_attempt = self.make_child_attempt()
        self.child_digest = self.child_attempt["lifecycle"]["receipt"]["receipt_digest"]

    def tearDown(self) -> None:
        for path in sorted(self.root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        self.root.rmdir()

    def sign_bytes(self, value: str) -> str:
        payload_path = self.root / f"payload-{uuid.uuid4().hex}"
        signature_path = self.root / f"signature-{uuid.uuid4().hex}"
        payload_path.write_text(value, encoding="ascii")
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private), "-out", str(signature_path), str(payload_path)],
            check=True,
            capture_output=True,
        )
        return base64.urlsafe_b64encode(signature_path.read_bytes()).decode().rstrip("=")

    def receipt(self, attempt: dict | None = None, *, children: list[str] | None = None) -> dict:
        attempt = attempt or self.attempt
        return {
            "schema": receipts.RECEIPT_SCHEMA,
            "attempt_id": attempt["attempt_id"],
            "role": attempt["role"],
            "status": "complete",
            "runtime_identity_digest": receipts.runtime_identity_digest(attempt),
            "terminal_observation_digest": attempt["lifecycle"]["terminal_observation_digest"],
            "observed_model": attempt["lifecycle"]["observed_model"],
            "model_evidence_digest": attempt["lifecycle"]["model_evidence_digest"],
            "telemetry_digest": receipts.telemetry_digest(attempt["lifecycle"]),
            "artifact_digests": [
                {"path": ".company-os/runtime-artifacts/manager.json", "sha256": digest("7")}
            ],
            "checks": [
                {"name": "artifact-schema", "status": "passed", "evidence": "schema-v1"}
            ],
            "author": (
                attempt["lifecycle"].get("provider_task_id")
                or attempt["lifecycle"].get("terminal_provider_event_id")
            ),
            "attestation_digest": digest("8"),
            "child_receipt_digests": children if children is not None else [self.child_digest],
        }

    def observation(
        self,
        attempt: dict,
        event: str,
        *,
        task_id: str,
        status: str | None = None,
        usage: dict | None = None,
    ) -> object:
        self.sequence += 1
        payload = {"provider_status": event, "usage": usage}
        if status is not None:
            payload["status"] = status
        raw = {
            "provider": attempt["provider"],
            "surface": attempt["surface"],
            "account": attempt["account"],
            "provider_task_id": task_id,
            "provider_event_id": f"event-{uuid.uuid4().hex}",
            "event_type": event,
            "provider_sequence": self.sequence,
            "provider_timestamp": self.now.isoformat(),
            "observed_model": attempt["requested_model"],
            "payload": payload,
        }
        raw_bytes = gateway.canonical_json(raw).encode("utf-8")
        claims = {
            "schema": gateway.RESULT_SCHEMA,
            "gateway_key_id": "gateway-1",
            "request_digest": digest("d"),
            "operation": "launch" if event == "launch" else "observe",
            "provider": attempt["provider"],
            "surface": attempt["surface"],
            "account": attempt["account"],
            "provider_task_id": task_id,
            "provider_event_id": raw["provider_event_id"],
            "event_type": event,
            "provider_sequence": self.sequence,
            "provider_timestamp": self.now.isoformat(),
            "gateway_received_at": self.now.isoformat(),
            "observed_model": attempt["requested_model"],
            "raw_artifact_path": "retained/raw.json",
            "raw_artifact_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "payload_sha256": gateway.sha256_json(payload),
            "project_id": attempt["project_id"],
            "program_version": attempt["program_version"],
            "work_id": attempt["work_id"],
            "cycle_id": attempt["cycle_id"],
            "attempt_id": attempt["attempt_id"],
            "parent_runtime_id": attempt["parent_runtime_id"],
            "role": attempt["role"],
            "requested_model": attempt["requested_model"],
            "fabric_manifest_digest": attempt["fabric_manifest_digest"],
            "phase2_contract_digest": attempt["phase2_contract_digest"],
            "nonce": uuid.uuid4().hex,
            "issued_at": self.now.isoformat(),
            "expires_at": (self.now + timedelta(minutes=4)).isoformat(),
        }
        signature = self.sign_bytes(gateway.canonical_json(claims))
        retained = {
            "observation_digest": gateway.sha256_json(claims),
            "claims": claims,
            "signature": signature,
            "signature_digest": hashlib.sha256(signature.encode()).hexdigest(),
            "raw": raw,
            "raw_artifact_b64": base64.b64encode(raw_bytes).decode("ascii"),
            "verified_at": self.now.isoformat(),
        }
        return gateway.reverify_retained_record(retained, keyring_path=self.keyring, now=self.now)

    def make_child_attempt(self) -> dict:
        child = deepcopy(self.attempt)
        child.update({
            "attempt_id": "worker-attempt",
            "manifest_identity_id": "worker-1",
            "parent_runtime_id": "manager-attempt",
            "role": "worker",
            "requested_model": "gpt-5.6-luna",
            "scope": [],
            "scope_digest": receipts.sha256_json([]),
            "idempotency_key": "worker-launch-1",
            "lifecycle": lifecycle_rules.empty_lifecycle(),
        })
        child = lifecycle_rules.apply_verified_observation(
            child,
            self.observation(child, "launch", task_id="provider-task-worker"),
            keyring_path=self.keyring,
            now=self.now,
        )
        usage = {
            "input_tokens": 80,
            "cached_input_tokens": 20,
            "output_tokens": 20,
            "total_tokens": 100,
            "cost_usd": 0.005,
            "currency": "USD",
            "semantics": "terminal",
            "provider_revision": "worker-terminal-1",
        }
        child = lifecycle_rules.apply_verified_observation(
            child,
            self.observation(
                child,
                "terminal",
                task_id="provider-task-worker",
                status="succeeded",
                usage=usage,
            ),
            keyring_path=self.keyring,
            now=self.now,
        )
        value = self.receipt(child, children=[])
        return self.record_value(child, value, children=[])

    def grant(self, attempt: dict, *, at: str, decision: str = "accepted", reviewer: str = "master-reviewer") -> str:
        payload = receipts.reconciliation_payload(
            attempt, decision=decision, reviewer=reviewer, reconciled_at=at
        )
        claims = {
            "actor": reviewer,
            "action": "reconcile-runtime",
            "resource": f"runtime:{attempt['attempt_id']}",
            "project_id": attempt["project_id"],
            "program_version": attempt["program_version"],
            "work_id": attempt["work_id"],
            "cycle_id": attempt["cycle_id"],
            "dimension": "runtime-reconciliation",
            "decision": decision,
            "payload_hash": receipts.sha256_json(payload),
            "nonce": uuid.uuid4().hex,
            "expiry": (self.now + timedelta(minutes=10)).isoformat(),
        }
        encoded = base64.urlsafe_b64encode(receipts.canonical_json(claims).encode()).decode().rstrip("=")
        return f"{encoded}.{self.sign_bytes(encoded)}"

    def attestation(self, value: dict, attempt: dict | None = None) -> object:
        attempt = attempt or self.attempt
        claims = {
            "schema": gateway.RECEIPT_ATTESTATION_SCHEMA,
            "gateway_key_id": "gateway-1",
            "action": "attest-runtime-receipt",
            "project_id": attempt["project_id"],
            "attempt_id": attempt["attempt_id"],
            "provider_task_id": attempt["lifecycle"]["provider_task_id"],
            "receipt_payload_hash": receipts.sha256_json(
                {key: item for key, item in value.items() if key != "attestation_digest"}
            ),
            "nonce": "receipt-attestation",
            "issued_at": self.now.isoformat(),
            "expires_at": (self.now + timedelta(minutes=4)).isoformat(),
        }
        value["attestation_digest"] = gateway.sha256_json(claims)
        envelope = {"claims": claims, "signature": self.sign_bytes(gateway.canonical_json(claims))}
        return gateway.verify_receipt_attestation(
            envelope, attempt=attempt, keyring_path=self.keyring, now=self.now
        )

    def record_value(
        self,
        attempt: dict,
        value: dict,
        *,
        children: list[dict] | None = None,
    ) -> dict:
        return receipts.record_receipt(
            attempt,
            value,
            expected_child_attempts=(
                children if children is not None
                else ([self.child_attempt] if attempt.get("role") == "manager" else [])
            ),
            verified_attestation=self.attestation(value, attempt),
            keyring_path=self.keyring,
            now=self.now,
        )

    def test_receipt_root_binds_identity_terminal_model_telemetry_artifacts_checks_and_children(self) -> None:
        result = self.record_value(self.attempt, self.receipt())
        retained = result["lifecycle"]["receipt"]
        self.assertEqual(len(retained["receipt_root"]), 64)
        changed_artifact = self.receipt()
        changed_artifact["artifact_digests"][0]["sha256"] = digest("a")
        changed = self.record_value(self.attempt, changed_artifact)
        self.assertNotEqual(
            retained["receipt_root"],
            changed["lifecycle"]["receipt"]["receipt_root"],
        )
        for mutation in (
            lambda value: value.update({"telemetry_digest": digest("b")}),
            lambda value: value.update({"model_evidence_digest": digest("c")}),
            lambda value: value.update({"child_receipt_digests": []}),
            lambda value: value.update({"child_receipt_digests": [self.child_digest, self.child_digest]}),
        ):
            candidate = self.receipt()
            mutation(candidate)
            with self.assertRaises(receipts.ReceiptError):
                self.record_value(self.attempt, candidate)

    def test_worker_receipt_requires_exact_empty_child_set(self) -> None:
        worker = deepcopy(self.attempt)
        worker.update(
            {
                "attempt_id": "worker-attempt",
                "parent_runtime_id": "manager-attempt",
                "role": "worker",
                "requested_model": "gpt-5.6-luna",
                "idempotency_key": "worker-launch-1",
            }
        )
        worker["lifecycle"]["observed_model"] = "gpt-5.6-luna"
        value = self.receipt()
        value.update(
            {
                "attempt_id": worker["attempt_id"],
                "role": "worker",
                "observed_model": "gpt-5.6-luna",
                "runtime_identity_digest": receipts.runtime_identity_digest(worker),
                "child_receipt_digests": [],
            }
        )
        result = self.record_value(worker, value, children=[])
        self.assertEqual(result["lifecycle"]["status"], "receipt_recorded")
        value["child_receipt_digests"] = [digest("a")]
        with self.assertRaises(receipts.ReceiptError):
            self.record_value(worker, value, children=[])

    def test_manager_requires_exact_one_luna_child_and_cancelled_run_needs_no_artifact(self) -> None:
        value = self.receipt()
        with self.assertRaises(receipts.ReceiptError):
            self.record_value(self.attempt, value, children=[])
        wrong_child = deepcopy(self.child_attempt)
        wrong_child["requested_model"] = "gpt-5.6-sol"
        with self.assertRaises(receipts.ReceiptError):
            self.record_value(self.attempt, self.receipt(), children=[wrong_child])
        stub_child = {
            "attempt_id": "worker-stub",
            "role": "worker",
            "requested_model": "gpt-5.6-luna",
            "parent_runtime_id": "manager-attempt",
            "lifecycle": {"receipt": {"receipt_digest": digest("a")}},
        }
        with self.assertRaises(receipts.ReceiptError):
            self.record_value(self.attempt, self.receipt(), children=[stub_child])
        failed_child = deepcopy(self.child_attempt)
        failed_child["lifecycle"]["terminal_status"] = "failed"
        with self.assertRaises(receipts.ReceiptError):
            self.record_value(self.attempt, self.receipt(), children=[failed_child])

        cancelled = deepcopy(self.attempt)
        cancelled["lifecycle"]["status"] = "cancelled"
        cancelled["lifecycle"]["terminal_status"] = "cancelled"
        cancelled_receipt = self.receipt()
        cancelled_receipt.update({
            "status": "cancelled",
            "artifact_digests": [],
            "checks": [],
        })
        receipted = self.record_value(cancelled, cancelled_receipt)
        at = self.now.isoformat()
        reconciled = receipts.reconcile(
            receipted,
            decision="cancelled",
            reviewer="master-reviewer",
            grant_token=self.grant(receipted, at=at, decision="cancelled"),
            decision_public_key_path=self.public,
            reconciled_at=at,
            now=self.now,
        )
        self.assertEqual(reconciled["lifecycle"]["status"], "reconciled")

    def test_blocked_model_unavailable_closes_with_attested_receipt_and_reconciliation(self) -> None:
        blocked = deepcopy(self.attempt)
        blocked["lifecycle"].update({
            "status": "blocked_model_unavailable",
            "terminal_status": "blocked_model_unavailable",
            "provider_task_id": None,
            "terminal_provider_event_id": "event-model-unavailable",
            "terminal_authority": "provider_observation",
            "observed_model": None,
            "model_evidence_digest": None,
            "telemetry": None,
            "budget_overage": None,
        })
        value = self.receipt(blocked, children=[])
        value.update({
            "status": "blocked",
            "artifact_digests": [],
            "checks": [],
            "child_receipt_digests": [],
        })
        receipted = self.record_value(blocked, value, children=[])
        self.assertEqual(receipted["lifecycle"]["status"], "receipt_recorded")
        self.assertEqual(
            receipts.audit_retained_receipt(
                receipted,
                keyring_path=self.keyring,
                expected_child_attempts=[],
            ),
            [],
        )
        at = self.now.isoformat()
        reconciled = receipts.reconcile(
            receipted,
            decision="blocked",
            reviewer="master-reviewer",
            grant_token=self.grant(receipted, at=at, decision="blocked"),
            decision_public_key_path=self.public,
            reconciled_at=at,
            now=self.now,
        )
        self.assertEqual(reconciled["lifecycle"]["status"], "reconciled")

    def test_exact_receipt_retry_is_noop_and_content_drift_requires_new_attestation(self) -> None:
        value = self.receipt()
        retained = self.record_value(self.attempt, value)
        replay = self.record_value(retained, value)
        self.assertEqual(retained, replay)
        drifted = deepcopy(value)
        drifted["checks"][0]["evidence"] = "different-evidence"
        with self.assertRaises(receipts.ReceiptError):
            self.record_value(retained, drifted)

    def test_reconciliation_requires_exact_verified_grant_and_is_restart_idempotent(self) -> None:
        receipted = self.record_value(self.attempt, self.receipt())
        at = datetime.now(timezone.utc).isoformat()
        grant = self.grant(receipted, at=at)
        result = receipts.reconcile(
            receipted,
            decision="accepted",
            reviewer="master-reviewer",
            grant_token=grant,
            decision_public_key_path=self.public,
            reconciled_at=at,
            now=self.now,
        )
        replay = receipts.reconcile(
            result,
            decision="accepted",
            reviewer="master-reviewer",
            grant_token=grant,
            decision_public_key_path=self.public,
            reconciled_at=at,
            now=self.now,
        )
        self.assertEqual(result, replay)
        for candidate in (
            "invalid",
            self.grant(receipted, at=at, decision="rejected"),
        ):
            with self.assertRaises(receipts.ReceiptError):
                receipts.reconcile(
                    receipted,
                    decision="accepted",
                    reviewer="master-reviewer",
                    grant_token=candidate,
                    decision_public_key_path=self.public,
                    reconciled_at=at,
                    now=self.now,
                )

    def test_reconciliation_cannot_be_rewritten_after_restart(self) -> None:
        receipted = self.record_value(self.attempt, self.receipt())
        accepted_at = datetime.now(timezone.utc).isoformat()
        accepted = receipts.reconcile(
            receipted,
            decision="accepted",
            reviewer="master-reviewer",
            grant_token=self.grant(receipted, at=accepted_at),
            decision_public_key_path=self.public,
            reconciled_at=accepted_at,
            now=self.now,
        )
        with self.assertRaises(receipts.ReceiptError):
            rejected_at = datetime.now(timezone.utc).isoformat()
            receipts.reconcile(
                accepted,
                decision="rejected",
                reviewer="different-reviewer",
                grant_token=self.grant(
                    accepted,
                    at=rejected_at,
                    decision="rejected",
                    reviewer="different-reviewer",
                ),
                decision_public_key_path=self.public,
                reconciled_at=rejected_at,
                now=self.now,
            )

    def test_failed_provider_state_cannot_be_receipted_or_reconciled_as_success(self) -> None:
        failed = deepcopy(self.attempt)
        failed["lifecycle"]["status"] = "failed"
        failed["lifecycle"]["terminal_status"] = "failed"
        false_success = self.receipt()
        with self.assertRaises(receipts.ReceiptError):
            self.record_value(failed, false_success)
        failed_receipt = {**false_success, "status": "failed"}
        receipted = self.record_value(failed, failed_receipt)
        failed_at = datetime.now(timezone.utc).isoformat()
        with self.assertRaises(receipts.ReceiptError):
            receipts.reconcile(
                receipted,
                decision="accepted",
                reviewer="master-reviewer",
                grant_token=self.grant(receipted, at=failed_at),
                decision_public_key_path=self.public,
                reconciled_at=failed_at,
                now=self.now,
            )

    def test_restart_audit_rejects_receipt_and_reconciliation_tampering(self) -> None:
        receipted = self.record_value(self.attempt, self.receipt())
        self.assertEqual(
            receipts.audit_retained_receipt(
                receipted,
                keyring_path=self.keyring,
                expected_child_attempts=[self.child_attempt],
            ),
            [],
        )
        tampered_receipt = deepcopy(receipted)
        tampered_receipt["lifecycle"]["receipt"]["artifact_digests"][0]["sha256"] = digest("a")
        self.assertTrue(receipts.audit_retained_receipt(
            tampered_receipt,
            keyring_path=self.keyring,
            expected_child_attempts=[self.child_attempt],
        ))
        at = self.now.isoformat()
        reconciled = receipts.reconcile(
            receipted,
            decision="accepted",
            reviewer="master-reviewer",
            grant_token=self.grant(receipted, at=at),
            decision_public_key_path=self.public,
            reconciled_at=at,
            now=self.now,
        )
        self.assertEqual(
            receipts.audit_retained_reconciliation(
                reconciled,
                decision_public_key_path=self.public,
            ),
            [],
        )
        tampered_decision = deepcopy(reconciled)
        tampered_decision["lifecycle"]["reconciliation"]["decision"] = "rejected"
        self.assertTrue(receipts.audit_retained_reconciliation(
            tampered_decision,
            decision_public_key_path=self.public,
        ))


if __name__ == "__main__":
    unittest.main()
