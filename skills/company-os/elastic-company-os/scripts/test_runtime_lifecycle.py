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


MODULE = Path(__file__).resolve().with_name("runtime_lifecycle.py")
SPEC = importlib.util.spec_from_file_location("company_os_runtime_lifecycle", MODULE)
assert SPEC and SPEC.loader
lifecycle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lifecycle)

GATEWAY_MODULE = Path(__file__).resolve().with_name("runtime_gateway.py")
GATEWAY_SPEC = importlib.util.spec_from_file_location("company_os_runtime_gateway_lifecycle_test", GATEWAY_MODULE)
assert GATEWAY_SPEC and GATEWAY_SPEC.loader
gateway = importlib.util.module_from_spec(GATEWAY_SPEC)
GATEWAY_SPEC.loader.exec_module(gateway)


def digest(character: str) -> str:
    return character * 64


DEFAULT_MODEL = object()


class RuntimeLifecycleTests(unittest.TestCase):
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
                "not_before": "2020-01-01T00:00:00+00:00",
                "not_after": "2035-01-01T00:00:00+00:00",
            }],
        }), encoding="utf-8")
        self.attempt = {
            "attempt_id": "attempt-1",
            "project_id": "company-os-core",
            "manifest_identity_id": "manager-1",
            "work_id": "work-1",
            "cycle_id": "cycle-1",
            "parent_runtime_id": "master",
            "role": "manager",
            "requested_model": "gpt-5.6-sol",
            "provider": "codex",
            "surface": "desktop",
            "account": "workspace-1",
            "program_version": 6,
            "scope": [".company-os/runtime-artifacts"],
            "scope_digest": digest("9"),
            "budget": {
                "time_minutes": 10,
                "token_limit": 2000,
                "cost_usd": 1.0,
                "max_concurrency": 1,
                "max_retries": 0,
            },
            "capabilities": ["emit_artifact", "read_project"],
            "idempotency_key": "launch-intent-1",
            "fabric_manifest_digest": digest("a"),
            "phase2_contract_digest": digest("b"),
            "lifecycle": lifecycle.empty_lifecycle(),
        }
        self.sequence = 0
        self.child_attempt = self.make_child_attempt()

    def tearDown(self) -> None:
        for path in sorted(self.root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        self.root.rmdir()

    def sign(self, claims: dict) -> str:
        payload_path = self.root / f"claims-{uuid.uuid4().hex}.json"
        signature_path = self.root / f"signature-{uuid.uuid4().hex}.bin"
        payload_path.write_text(gateway.canonical_json(claims), encoding="utf-8")
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private), "-out", str(signature_path), str(payload_path)],
            check=True,
            capture_output=True,
        )
        return base64.urlsafe_b64encode(signature_path.read_bytes()).decode().rstrip("=")

    def record(
        self,
        event: str,
        *,
        status: str | None = None,
        observed_model: object = DEFAULT_MODEL,
        usage: dict | None = None,
        task_id: str | None = "provider-task-1",
        bound_attempt: dict | None = None,
        provider_timestamp: datetime | None = None,
    ) -> dict:
        bound_attempt = bound_attempt or self.attempt
        provider_timestamp = provider_timestamp or self.now
        if observed_model is DEFAULT_MODEL:
            observed_model = bound_attempt["requested_model"]
        self.sequence += 1
        payload = (
            {"provider_status": "rejected", "reason": "model_unavailable", "usage": None}
            if event == "launch_rejected"
            else {"provider_status": event, "usage": usage}
        )
        if status is not None:
            payload["status"] = status
        raw = {
            "provider": bound_attempt["provider"],
            "surface": bound_attempt["surface"],
            "account": bound_attempt["account"],
            "provider_task_id": task_id,
            "provider_event_id": f"event-{uuid.uuid4().hex}",
            "event_type": event,
            "provider_sequence": self.sequence,
            "provider_timestamp": provider_timestamp.isoformat(),
            "observed_model": observed_model,
            "payload": payload,
        }
        raw_bytes = gateway.canonical_json(raw).encode("utf-8")
        claims = {
            "schema": gateway.RESULT_SCHEMA,
            "gateway_key_id": "gateway-1",
            "request_digest": digest("d"),
            "operation": (
                "launch"
                if event in {"launch", "launch_unknown", "launch_rejected"}
                else ("cancel" if event == "cancel_acknowledged" else "observe")
            ),
            "provider": bound_attempt["provider"],
            "surface": bound_attempt["surface"],
            "account": bound_attempt["account"],
            "provider_task_id": task_id,
            "provider_event_id": raw["provider_event_id"],
            "event_type": event,
            "provider_sequence": self.sequence,
            "provider_timestamp": provider_timestamp.isoformat(),
            "gateway_received_at": self.now.isoformat(),
            "observed_model": observed_model,
            "raw_artifact_path": "retained/raw.json",
            "raw_artifact_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "payload_sha256": gateway.sha256_json(payload),
            "project_id": bound_attempt["project_id"],
            "program_version": bound_attempt["program_version"],
            "work_id": bound_attempt["work_id"],
            "cycle_id": bound_attempt["cycle_id"],
            "attempt_id": bound_attempt["attempt_id"],
            "parent_runtime_id": bound_attempt["parent_runtime_id"],
            "role": bound_attempt["role"],
            "requested_model": bound_attempt["requested_model"],
            "fabric_manifest_digest": bound_attempt["fabric_manifest_digest"],
            "phase2_contract_digest": bound_attempt["phase2_contract_digest"],
            "nonce": uuid.uuid4().hex,
            "issued_at": self.now.isoformat(),
            "expires_at": (self.now + timedelta(minutes=4)).isoformat(),
        }
        signature = self.sign(claims)
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

    def apply(self, attempt: dict, record: object) -> dict:
        return lifecycle.apply_verified_observation(
            attempt, record, keyring_path=self.keyring, now=self.now
        )

    def terminal_usage(self, *, revision: str = "usage-3") -> dict:
        return {
            "input_tokens": 100,
            "cached_input_tokens": 40,
            "output_tokens": 25,
            "total_tokens": 125,
            "cost_usd": 0.0125,
            "currency": "USD",
            "semantics": "terminal",
            "provider_revision": revision,
        }

    def advance_to_success(self) -> dict:
        attempt = self.apply(self.attempt, self.record("launch"))
        attempt = self.apply(attempt, self.record("running"))
        return self.apply(
            attempt,
            self.record("terminal", status="succeeded", usage=self.terminal_usage()),
        )

    def receipt(self, attempt: dict, *, children: list[str] | None = None) -> dict:
        receipts = lifecycle.receipt_module()
        return {
            "schema": "company-os.runtime-receipt.v1",
            "attempt_id": attempt["attempt_id"],
            "role": attempt["role"],
            "status": "complete",
            "runtime_identity_digest": receipts.runtime_identity_digest(attempt),
            "terminal_observation_digest": attempt["lifecycle"]["terminal_observation_digest"],
            "observed_model": attempt["lifecycle"]["observed_model"],
            "model_evidence_digest": attempt["lifecycle"]["model_evidence_digest"],
            "telemetry_digest": receipts.telemetry_digest(attempt["lifecycle"]),
            "artifact_digests": [{"path": ".company-os/runtime/a.json", "sha256": digest("c")}],
            "checks": [{"name": "schema", "status": "passed", "evidence": "validated"}],
            "author": attempt["lifecycle"]["provider_task_id"],
            "attestation_digest": digest("d"),
            "child_receipt_digests": children if children is not None else [
                self.child_attempt["lifecycle"]["receipt"]["receipt_digest"]
            ],
        }

    def make_child_attempt(self) -> dict:
        child = deepcopy(self.attempt)
        child.update({
            "attempt_id": "worker-attempt-1",
            "manifest_identity_id": "worker-1",
            "parent_runtime_id": "attempt-1",
            "role": "worker",
            "requested_model": "gpt-5.6-luna",
            "scope": [],
            "scope_digest": lifecycle.sha256_json([]),
            "idempotency_key": "worker-launch-1",
            "lifecycle": lifecycle.empty_lifecycle(),
        })
        child = self.apply(
            child,
            self.record("launch", bound_attempt=child, task_id="provider-task-worker"),
        )
        child = self.apply(
            child,
            self.record(
                "terminal",
                bound_attempt=child,
                task_id="provider-task-worker",
                status="succeeded",
                usage=self.terminal_usage(revision="worker-usage-terminal"),
            ),
        )
        value = self.receipt(child, children=[])
        return lifecycle.record_receipt(
            child,
            value,
            expected_child_attempts=[],
            verified_attestation=self.attestation(value, child),
            keyring_path=self.keyring,
            now=self.now,
        )

    def attestation(self, receipt: dict, attempt: dict) -> object:
        receipts = lifecycle.receipt_module()
        claims = {
            "schema": gateway.RECEIPT_ATTESTATION_SCHEMA,
            "gateway_key_id": "gateway-1",
            "action": "attest-runtime-receipt",
            "project_id": attempt["project_id"],
            "attempt_id": attempt["attempt_id"],
            "provider_task_id": attempt["lifecycle"]["provider_task_id"],
            "receipt_payload_hash": receipts.sha256_json(
                {key: value for key, value in receipt.items() if key != "attestation_digest"}
            ),
            "nonce": uuid.uuid4().hex,
            "issued_at": self.now.isoformat(),
            "expires_at": (self.now + timedelta(minutes=4)).isoformat(),
        }
        receipt["attestation_digest"] = gateway.sha256_json(claims)
        envelope = {"claims": claims, "signature": self.sign(claims)}
        return gateway.verify_receipt_attestation(
            envelope, attempt=attempt, keyring_path=self.keyring, now=self.now
        )

    def decision_grant(
        self,
        attempt: dict,
        *,
        decision: str,
        reviewer: str,
        reconciled_at: str,
    ) -> str:
        receipts = lifecycle.receipt_module()
        payload = receipts.reconciliation_payload(
            attempt,
            decision=decision,
            reviewer=reviewer,
            reconciled_at=reconciled_at,
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
        return self.sign_grant(claims)

    def sign_grant(self, claims: dict) -> str:
        receipts = lifecycle.receipt_module()
        encoded = base64.urlsafe_b64encode(receipts.canonical_json(claims).encode()).decode().rstrip("=")
        payload_path = self.root / f"grant-{uuid.uuid4().hex}.txt"
        signature_path = self.root / f"grant-signature-{uuid.uuid4().hex}.bin"
        payload_path.write_text(encoded, encoding="ascii")
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private), "-out", str(signature_path), str(payload_path)],
            check=True,
            capture_output=True,
        )
        signature = base64.urlsafe_b64encode(signature_path.read_bytes()).decode().rstrip("=")
        return f"{encoded}.{signature}"

    def cancellation_grant(
        self,
        attempt: dict,
        *,
        requested_by: str,
        reason: str,
        requested_at: str,
    ) -> str:
        payload = {
            "attempt_id": attempt["attempt_id"],
            "requested_by": requested_by,
            "reason": reason,
            "requested_at": lifecycle._time(requested_at, "requested_at"),
            "after_observation_count": len(attempt["lifecycle"]["verified_observations"]),
        }
        claims = {
            "actor": requested_by,
            "action": "cancel-runtime",
            "resource": f"runtime:{attempt['attempt_id']}",
            "project_id": attempt["project_id"],
            "program_version": attempt["program_version"],
            "work_id": attempt["work_id"],
            "cycle_id": attempt["cycle_id"],
            "dimension": "runtime-cancellation",
            "decision": "cancelled",
            "payload_hash": lifecycle.sha256_json(payload),
            "nonce": uuid.uuid4().hex,
            "expiry": (self.now + timedelta(minutes=10)).isoformat(),
        }
        return self.sign_grant(claims)

    def test_success_path_requires_exact_model_terminal_usage_receipt_and_reconciliation(self) -> None:
        attempt = self.advance_to_success()
        self.assertEqual(attempt["lifecycle"]["status"], "succeeded")
        self.assertEqual(attempt["lifecycle"]["observed_model"], "gpt-5.6-sol")
        self.assertEqual(attempt["lifecycle"]["telemetry"]["total_tokens"], 125)
        receipt = self.receipt(attempt)
        attempt = lifecycle.record_receipt(
            attempt,
            receipt,
            expected_child_attempts=[self.child_attempt],
            verified_attestation=self.attestation(receipt, attempt),
            keyring_path=self.keyring,
            now=self.now,
        )
        self.assertEqual(attempt["lifecycle"]["status"], "receipt_recorded")
        reconciled_at = self.now.isoformat()
        attempt = lifecycle.reconcile(
            attempt,
            decision="accepted",
            reviewer="independent-master",
            grant_token=self.decision_grant(
                attempt,
                decision="accepted",
                reviewer="independent-master",
                reconciled_at=reconciled_at,
            ),
            decision_public_key_path=self.public,
            reconciled_at=reconciled_at,
            now=self.now,
        )
        self.assertEqual(attempt["lifecycle"]["status"], "reconciled")
        self.assertEqual(
            lifecycle.audit_attempt(
                attempt,
                keyring_path=self.keyring,
                decision_public_key_path=self.public,
                expected_child_attempts=[self.child_attempt],
            ),
            [],
        )

    def test_model_mismatch_missing_model_wrong_binding_and_task_conflict_fail_closed(self) -> None:
        for observed_model in ("gpt-5.6-terra", None):
            with self.assertRaises(gateway.GatewayError):
                self.record("launch", observed_model=observed_model)
        retained = self.record("launch").retained_record()
        retained["claims"]["work_id"] = "other-work"
        retained["observation_digest"] = gateway.sha256_json(retained["claims"])
        retained["signature"] = self.sign(retained["claims"])
        retained["signature_digest"] = hashlib.sha256(retained["signature"].encode()).hexdigest()
        wrong_binding = gateway.reverify_retained_record(
            retained,
            keyring_path=self.keyring,
            now=self.now,
        )
        with self.assertRaises(lifecycle.LifecycleError):
            self.apply(self.attempt, wrong_binding)
        launched = self.apply(self.attempt, self.record("launch"))
        with self.assertRaises(lifecycle.LifecycleError):
            self.apply(
                launched,
                self.record("running", task_id="provider-task-2"),
            )

    def test_launch_unknown_recovers_by_observation_without_blind_success(self) -> None:
        unknown = self.apply(
            self.attempt,
            self.record("launch_unknown", observed_model=None, task_id=None),
        )
        self.assertEqual(unknown["lifecycle"]["status"], "launch_unknown")
        recovered = self.apply(unknown, self.record("launch"))
        self.assertEqual(recovered["lifecycle"]["status"], "launched")
        with self.assertRaises(lifecycle.LifecycleError):
            self.apply(unknown, self.record("running"))

    def test_cancellation_is_irreversible_dominates_late_success_and_requires_ack(self) -> None:
        launched = self.apply(self.attempt, self.record("launch"))
        requested_at = self.now.isoformat()
        cancelled = lifecycle.request_cancellation(
            launched,
            requested_by="master",
            reason="budget exhausted",
            grant_token=self.cancellation_grant(
                launched,
                requested_by="master",
                reason="budget exhausted",
                requested_at=requested_at,
            ),
            decision_public_key_path=self.public,
            requested_at=requested_at,
            now=self.now,
        )
        late_success = self.apply(
            cancelled,
            self.record("terminal", status="succeeded", usage=self.terminal_usage()),
        )
        self.assertEqual(late_success["lifecycle"]["status"], "cancelled")
        self.assertEqual(late_success["lifecycle"]["terminal_status"], "cancelled")
        acknowledged = self.apply(cancelled, self.record("cancel_acknowledged"))
        terminal = self.apply(
            acknowledged,
            self.record("terminal", status="cancelled", usage=self.terminal_usage()),
        )
        self.assertEqual(terminal["lifecycle"]["status"], "cancelled")
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.request_cancellation(
                acknowledged,
                requested_by="other",
                reason="different",
                grant_token="invalid",
                decision_public_key_path=self.public,
                requested_at=self.now.isoformat(),
                now=self.now,
            )
        self.assertEqual(
            lifecycle.audit_attempt(
                terminal,
                keyring_path=self.keyring,
                decision_public_key_path=self.public,
            ),
            [],
        )

    def test_prelaunch_and_unknown_cancellation_are_signed_terminal_or_recoverable(self) -> None:
        at = self.now.isoformat()
        token = self.cancellation_grant(
            self.attempt,
            requested_by="master",
            reason="stop before launch",
            requested_at=at,
        )
        before_launch = lifecycle.request_cancellation(
            self.attempt,
            requested_by="master",
            reason="stop before launch",
            grant_token=token,
            decision_public_key_path=self.public,
            requested_at=at,
            now=self.now,
        )
        self.assertEqual(before_launch["lifecycle"]["status"], "cancelled_before_launch")
        self.assertEqual(
            lifecycle.audit_attempt(
                before_launch,
                keyring_path=self.keyring,
                decision_public_key_path=self.public,
            ),
            [],
        )
        exact_retry = lifecycle.request_cancellation(
            before_launch,
            requested_by="master",
            reason="stop before launch",
            grant_token=token,
            decision_public_key_path=self.public,
            requested_at=at,
            now=self.now,
        )
        self.assertEqual(exact_retry, before_launch)
        expired_exact_retry = lifecycle.request_cancellation(
            before_launch,
            requested_by="master",
            reason="stop before launch",
            grant_token=token,
            decision_public_key_path=self.public,
            requested_at=at,
            now=self.now + timedelta(minutes=11),
        )
        self.assertEqual(expired_exact_retry, before_launch)
        receipts = lifecycle.receipt_module()
        grant_digest = before_launch["lifecycle"]["cancellation"]["grant"]["grant_digest"]
        cancellation_receipt = {
            "schema": "company-os.runtime-receipt.v1",
            "attempt_id": before_launch["attempt_id"],
            "role": before_launch["role"],
            "status": "cancelled",
            "runtime_identity_digest": receipts.runtime_identity_digest(before_launch),
            "terminal_observation_digest": None,
            "observed_model": None,
            "model_evidence_digest": None,
            "telemetry_digest": receipts.telemetry_digest(before_launch["lifecycle"]),
            "artifact_digests": [],
            "checks": [],
            "author": "master",
            "attestation_digest": grant_digest,
            "child_receipt_digests": [],
        }
        receipted = lifecycle.record_receipt(
            before_launch,
            cancellation_receipt,
            expected_child_attempts=[],
            verified_attestation=None,
            keyring_path=self.keyring,
            decision_public_key_path=self.public,
            now=self.now,
        )
        tampered_receipt = deepcopy(receipted)
        retained = tampered_receipt["lifecycle"]["receipt"]
        retained["author"] = "attacker"
        retained["artifact_digests"] = [{"path": "invented.txt", "sha256": digest("f")}]
        retained["checks"] = [{"name": "invented", "status": "passed", "evidence": "invented"}]
        base = {
            key: value
            for key, value in retained.items()
            if key not in {"receipt_digest", "receipt_root", "attestation_record"}
        }
        retained["receipt_digest"] = receipts.sha256_json(base)
        retained["receipt_root"] = receipts.sha256_json(receipts._receipt_root_payload(retained))
        self.assertTrue(
            lifecycle.audit_attempt(
                tampered_receipt,
                keyring_path=self.keyring,
                decision_public_key_path=self.public,
                expected_child_attempts=[],
            )
        )
        reconciled = lifecycle.reconcile(
            receipted,
            decision="cancelled",
            reviewer="independent-master",
            grant_token=self.decision_grant(
                receipted,
                decision="cancelled",
                reviewer="independent-master",
                reconciled_at=at,
            ),
            decision_public_key_path=self.public,
            reconciled_at=at,
            now=self.now,
        )
        self.assertEqual(
            lifecycle.audit_attempt(
                reconciled,
                keyring_path=self.keyring,
                decision_public_key_path=self.public,
                expected_child_attempts=[],
            ),
            [],
        )
        unsigned = deepcopy(self.attempt)
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.request_cancellation(
                unsigned,
                requested_by="master",
                reason="stop before launch",
                grant_token="unsigned",
                decision_public_key_path=self.public,
                requested_at=at,
                now=self.now,
            )

        unknown = self.apply(
            self.attempt,
            self.record("launch_unknown", observed_model=None, task_id=None),
        )
        unknown_at = self.now.isoformat()
        unknown_token = self.cancellation_grant(
            unknown,
            requested_by="master",
            reason="ambiguous launch",
            requested_at=unknown_at,
        )
        cancel_unknown = lifecycle.request_cancellation(
            unknown,
            requested_by="master",
            reason="ambiguous launch",
            grant_token=unknown_token,
            decision_public_key_path=self.public,
            requested_at=unknown_at,
            now=self.now,
        )
        recovered = self.apply(cancel_unknown, self.record("launch"))
        self.assertEqual(recovered["lifecycle"]["status"], "cancel_requested")
        self.assertEqual(recovered["lifecycle"]["provider_task_id"], "provider-task-1")
        recovered_retry = lifecycle.request_cancellation(
            recovered,
            requested_by="master",
            reason="ambiguous launch",
            grant_token=unknown_token,
            decision_public_key_path=self.public,
            requested_at=unknown_at,
            now=self.now + timedelta(minutes=11),
        )
        self.assertEqual(recovered_retry, recovered)

    def test_provider_terminal_cannot_claim_pre_task_special_states(self) -> None:
        launched = self.apply(self.attempt, self.record("launch"))
        for false_terminal in ("blocked_model_unavailable", "cancelled_before_launch"):
            with self.assertRaises(lifecycle.LifecycleError):
                self.apply(
                    launched,
                    self.record(
                        "terminal",
                        status=false_terminal,
                        usage=self.terminal_usage(revision=f"false-{false_terminal}"),
                    ),
                )

    def test_reordered_post_terminal_and_untrusted_observations_cannot_mutate(self) -> None:
        launch = self.record("launch")
        launched = self.apply(self.attempt, launch)
        before = deepcopy(launched)
        repeated = self.apply(launched, launch)
        self.assertEqual(repeated, before)
        stale = self.record("running")
        stale["claims"]["provider_sequence"] = 0
        with self.assertRaises(lifecycle.LifecycleError):
            self.apply(launched, stale)
        terminal = self.apply(
            launched,
            self.record("terminal", status="failed", usage=self.terminal_usage()),
        )
        with self.assertRaises(lifecycle.LifecycleError):
            self.apply(terminal, self.record("heartbeat"))
        untrusted = self.record("running").retained_record()
        with self.assertRaises(lifecycle.LifecycleError):
            self.apply(launched, untrusted)

    def test_receipts_fail_without_telemetry_or_with_missing_children_and_workers_cannot_claim_children(self) -> None:
        attempt = self.apply(self.attempt, self.record("launch"))
        with self.assertRaises(lifecycle.LifecycleError):
            self.apply(
                attempt,
                self.record("terminal", status="succeeded", usage=None),
            )
        successful = self.advance_to_success()
        bad = self.receipt(successful)
        bad["artifact_digests"] = []
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.record_receipt(
                successful,
                bad,
                expected_child_attempts=[self.child_attempt],
                verified_attestation=self.attestation(bad, successful),
                keyring_path=self.keyring,
                now=self.now,
            )
        worker = deepcopy(successful)
        worker["role"] = "worker"
        worker["parent_runtime_id"] = "manager-attempt"
        worker_receipt = self.receipt(worker, children=[])
        worker_receipt.update({"role": "worker", "child_receipt_digests": []})
        lifecycle.record_receipt(
            worker,
            worker_receipt,
            expected_child_attempts=[],
            verified_attestation=self.attestation(worker_receipt, worker),
            keyring_path=self.keyring,
            now=self.now,
        )
        worker_receipt["child_receipt_digests"] = [digest("e")]
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.record_receipt(
                worker,
                worker_receipt,
                expected_child_attempts=[],
                verified_attestation=self.attestation(worker_receipt, worker),
                keyring_path=self.keyring,
                now=self.now,
            )

    def test_receipt_and_reconciliation_cannot_turn_failure_into_success(self) -> None:
        launched = self.apply(self.attempt, self.record("launch"))
        failed = self.apply(
            launched,
            self.record("terminal", status="failed", usage=self.terminal_usage()),
        )
        false_success = self.receipt(failed)
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.record_receipt(
                failed,
                false_success,
                expected_child_attempts=[self.child_attempt],
                verified_attestation=self.attestation(false_success, failed),
                keyring_path=self.keyring,
                now=self.now,
            )
        failed_receipt = {**false_success, "status": "failed"}
        receipted = lifecycle.record_receipt(
            failed,
            failed_receipt,
            expected_child_attempts=[self.child_attempt],
            verified_attestation=self.attestation(failed_receipt, failed),
            keyring_path=self.keyring,
            now=self.now,
        )
        reconciled_at = self.now.isoformat()
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.reconcile(
                receipted,
                decision="accepted",
                reviewer="independent-master",
                grant_token=self.decision_grant(
                    receipted,
                    decision="accepted",
                    reviewer="independent-master",
                    reconciled_at=reconciled_at,
                ),
                decision_public_key_path=self.public,
                reconciled_at=reconciled_at,
                now=self.now,
            )

    def test_usage_rejects_invented_zero_nan_bad_totals_and_cached_overflow(self) -> None:
        base = self.terminal_usage()
        mutations = [
            {**base, "cost_usd": float("nan")},
            {**base, "total_tokens": 1},
            {**base, "cached_input_tokens": 101},
            {**base, "currency": "EUR"},
            {key: value for key, value in base.items() if key != "provider_revision"},
        ]
        launched = self.apply(self.attempt, self.record("launch"))
        for usage in mutations:
            with self.assertRaises((lifecycle.LifecycleError, ValueError)):
                self.apply(
                    launched,
                    self.record("terminal", status="succeeded", usage=usage),
                )
        cumulative_terminal = {**base, "semantics": "cumulative"}
        with self.assertRaises(lifecycle.LifecycleError):
            self.apply(
                launched,
                self.record("terminal", status="succeeded", usage=cumulative_terminal),
            )

    def test_cumulative_usage_cannot_decrease_or_reuse_provider_revision(self) -> None:
        launched = self.apply(self.attempt, self.record("launch"))
        cumulative = {
            **self.terminal_usage(),
            "semantics": "cumulative",
            "provider_revision": "usage-running-1",
        }
        running = self.apply(
            launched,
            self.record("running", usage=cumulative),
        )
        decreased = {
            **cumulative,
            "input_tokens": 99,
            "total_tokens": 124,
            "provider_revision": "usage-running-2",
        }
        with self.assertRaises(lifecycle.LifecycleError):
            self.apply(
                running,
                self.record("heartbeat", usage=decreased),
            )
        repeated_revision = {**cumulative}
        with self.assertRaises(lifecycle.LifecycleError):
            self.apply(
                running,
                self.record("heartbeat", usage=repeated_revision),
            )

    def test_provider_overage_is_retained_and_blocks_complete_receipt(self) -> None:
        launched = self.apply(self.attempt, self.record("launch"))
        overage_usage = {
            "input_tokens": 2100,
            "cached_input_tokens": 0,
            "output_tokens": 50,
            "total_tokens": 2150,
            "cost_usd": 1.25,
            "currency": "USD",
            "semantics": "terminal",
            "provider_revision": "usage-overage",
        }
        terminal = self.apply(
            launched,
            self.record("terminal", status="succeeded", usage=overage_usage),
        )
        self.assertEqual(
            set(terminal["lifecycle"]["budget_overage"]),
            {"total_tokens", "cost_usd"},
        )
        value = self.receipt(terminal)
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.record_receipt(
                terminal,
                value,
                expected_child_attempts=[self.child_attempt],
                verified_attestation=self.attestation(value, terminal),
                keyring_path=self.keyring,
                now=self.now,
            )

    def test_time_budget_and_deterministic_restart_replay_fail_closed(self) -> None:
        launched = self.apply(
            self.attempt,
            self.record("launch", provider_timestamp=self.now),
        )
        terminal = self.apply(
            launched,
            self.record(
                "terminal",
                status="succeeded",
                usage=self.terminal_usage(revision="late-terminal"),
                provider_timestamp=self.now + timedelta(minutes=11),
            ),
        )
        self.assertEqual(set(terminal["lifecycle"]["budget_overage"]), {"time_minutes"})
        self.assertEqual(lifecycle.audit_attempt(terminal, keyring_path=self.keyring), [])
        for field, value in (
            ("provider_task_id", "tampered-task"),
            ("terminal_status", "failed"),
            ("budget_overage", None),
        ):
            tampered = deepcopy(terminal)
            tampered["lifecycle"][field] = value
            self.assertTrue(lifecycle.audit_attempt(tampered, keyring_path=self.keyring))
        telemetry_tampered = deepcopy(terminal)
        telemetry_tampered["lifecycle"]["telemetry"]["cost_usd"] = 0.99
        self.assertTrue(lifecycle.audit_attempt(telemetry_tampered, keyring_path=self.keyring))
        decreasing = self.record(
            "heartbeat",
            provider_timestamp=self.now - timedelta(seconds=1),
        )
        with self.assertRaises(lifecycle.LifecycleError):
            self.apply(launched, decreasing)

    def test_blocked_model_path_receipts_reconciles_and_replays_without_invented_model(self) -> None:
        blocked = self.apply(
            self.attempt,
            self.record("launch_rejected", observed_model=None, task_id=None),
        )
        receipts = lifecycle.receipt_module()
        value = {
            "schema": "company-os.runtime-receipt.v1",
            "attempt_id": blocked["attempt_id"],
            "role": blocked["role"],
            "status": "blocked",
            "runtime_identity_digest": receipts.runtime_identity_digest(blocked),
            "terminal_observation_digest": blocked["lifecycle"]["terminal_observation_digest"],
            "observed_model": None,
            "model_evidence_digest": None,
            "telemetry_digest": receipts.telemetry_digest(blocked["lifecycle"]),
            "artifact_digests": [],
            "checks": [],
            "author": blocked["lifecycle"]["terminal_provider_event_id"],
            "attestation_digest": digest("d"),
            "child_receipt_digests": [],
        }
        receipted = lifecycle.record_receipt(
            blocked,
            value,
            expected_child_attempts=[],
            verified_attestation=self.attestation(value, blocked),
            keyring_path=self.keyring,
            now=self.now,
        )
        at = self.now.isoformat()
        reconciled = lifecycle.reconcile(
            receipted,
            decision="blocked",
            reviewer="independent-master",
            grant_token=self.decision_grant(
                receipted,
                decision="blocked",
                reviewer="independent-master",
                reconciled_at=at,
            ),
            decision_public_key_path=self.public,
            reconciled_at=at,
            now=self.now,
        )
        self.assertEqual(
            lifecycle.audit_attempt(
                reconciled,
                keyring_path=self.keyring,
                decision_public_key_path=self.public,
                expected_child_attempts=[],
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
