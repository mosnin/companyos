#!/usr/bin/env python3

from __future__ import annotations

import base64
import importlib.util
import json
import subprocess
import tempfile
import unittest
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path


MODULE = Path(__file__).resolve().with_name("runtime_gateway.py")
SPEC = importlib.util.spec_from_file_location("company_os_runtime_gateway", MODULE)
assert SPEC and SPEC.loader
gateway = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway)

LIFECYCLE_MODULE = Path(__file__).resolve().with_name("runtime_lifecycle.py")
LIFECYCLE_SPEC = importlib.util.spec_from_file_location("company_os_runtime_lifecycle", LIFECYCLE_MODULE)
assert LIFECYCLE_SPEC and LIFECYCLE_SPEC.loader
lifecycle = importlib.util.module_from_spec(LIFECYCLE_SPEC)
LIFECYCLE_SPEC.loader.exec_module(lifecycle)


def digest(character: str) -> str:
    return character * 64


class RuntimeGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.private = self.root / "private.pem"
        self.public = self.root / "public.pem"
        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "RSA",
                "-pkeyopt",
                "rsa_keygen_bits:2048",
                "-out",
                str(self.private),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(self.private), "-pubout", "-out", str(self.public)],
            check=True,
            capture_output=True,
        )
        self.keyring = self.root / "keyring.json"
        self.now = datetime.now(timezone.utc)
        self.keyring.write_text(
            json.dumps(
                {
                    "schema": "company-os.runtime-gateway-keyring.v1",
                    "keys": [
                        {
                            "key_id": "gateway-1",
                            "algorithm": "rsa-sha256",
                            "public_key_path": str(self.public),
                            "status": "active",
                            "not_before": (self.now - timedelta(hours=1)).isoformat(),
                            "not_after": (self.now + timedelta(hours=1)).isoformat(),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.attempt = {
            "attempt_id": "manager-attempt-1",
            "project_id": "company-os-core",
            "manifest_identity_id": "manager-1",
            "work_id": "work-runtime-v6",
            "cycle_id": "cycle-runtime-v6-1",
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
            "idempotency_key": "launch-manager-v6-1",
            "program_version": 6,
            "actor_grant": {"token": "signed-admission-token", "grant_digest": digest("4")},
            "lease_fence": {
                "lease_id": "lease-1",
                "generation": 1,
                "owner": "master-sol",
                "program_version": 6,
                "expires_at": (self.now + timedelta(minutes=10)).isoformat(),
                "allowed_transitions": ["admit-runtime-attempt"],
            },
            "lifecycle": lifecycle.empty_lifecycle(),
        }
        self.manifest = {
            "max_managers": 1,
            "max_workers_per_manager": 1,
            "max_total_workers": 1,
            "external_effects_allowed": False,
            "managers": [
                {
                    "id": "manager-1",
                    "model": "gpt-5.6-sol",
                    "write_scope": [".company-os/runtime-artifacts"],
                    "budget": deepcopy(self.attempt["budget"]),
                    "workers": [
                        {
                            "id": "worker-1",
                            "model": "gpt-5.6-luna",
                            "write_scope": [],
                            "budget": deepcopy(self.attempt["budget"]),
                            "capabilities": ["emit_artifact", "read_project"],
                            "may_delegate": False,
                            "external_effects": False,
                        }
                    ],
                }
            ],
        }
        self.attempt["fabric_manifest_digest"] = gateway.sha256_json(self.manifest)
        self.attempt["scope_digest"] = gateway.sha256_json(self.attempt["scope"])

    def tearDown(self) -> None:
        for path in sorted(self.root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        self.root.rmdir()

    def sign(self, claims: dict) -> str:
        payload = self.root / f"claims-{uuid.uuid4().hex}.json"
        signature = self.root / f"signature-{uuid.uuid4().hex}.bin"
        payload.write_text(gateway.canonical_json(claims), encoding="utf-8")
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private), "-out", str(signature), str(payload)],
            check=True,
            capture_output=True,
        )
        return base64.urlsafe_b64encode(signature.read_bytes()).decode().rstrip("=")

    def current_fence(self) -> dict:
        return {
            **deepcopy(self.attempt["lease_fence"]),
            "lease_id": f"runtime-{uuid.uuid4().hex}",
            "generation": 2,
            "expires_at": (self.now + timedelta(minutes=10)).isoformat(),
        }

    def request(self, attempt: dict, operation: str) -> dict:
        return gateway.build_request(
            attempt,
            manifest=self.manifest,
            operation=operation,
            current_lease_fence=None if operation == "launch" else self.current_fence(),
            now=self.now,
        )

    def apply(self, attempt: dict, record: object) -> dict:
        return lifecycle.apply_verified_observation(
            attempt,
            record,
            keyring_path=self.keyring,
            now=self.now,
        )

    def envelope(
        self,
        request: dict,
        *,
        event: str = "launch",
        task_id: str | None = "provider-task-1",
        observed_model: str | None = "gpt-5.6-sol",
        sequence: int = 1,
        payload: dict | None = None,
        changes: dict | None = None,
    ) -> dict:
        attempt = request["attempt"]
        raw = {
            "provider": attempt["provider"],
            "surface": attempt["surface"],
            "account": attempt["account"],
            "provider_task_id": task_id,
            "provider_event_id": f"event-{uuid.uuid4().hex}",
            "event_type": event,
            "provider_sequence": sequence,
            "provider_timestamp": (self.now - timedelta(seconds=2)).isoformat(),
            "observed_model": observed_model,
            "payload": payload or {"provider_status": event, "usage": None},
        }
        raw_path = self.root / f"raw-{uuid.uuid4().hex}.json"
        raw_path.write_text(gateway.canonical_json(raw), encoding="utf-8")
        claims = {
            "schema": gateway.RESULT_SCHEMA,
            "gateway_key_id": "gateway-1",
            "request_digest": request["request_digest"],
            "operation": request["operation"],
            "provider": raw["provider"],
            "surface": raw["surface"],
            "account": raw["account"],
            "provider_task_id": raw["provider_task_id"],
            "provider_event_id": raw["provider_event_id"],
            "event_type": raw["event_type"],
            "provider_sequence": raw["provider_sequence"],
            "provider_timestamp": raw["provider_timestamp"],
            "gateway_received_at": (self.now - timedelta(seconds=1)).isoformat(),
            "observed_model": raw["observed_model"],
            "raw_artifact_path": raw_path.relative_to(self.root).as_posix(),
            "raw_artifact_sha256": gateway.hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            "payload_sha256": gateway.sha256_json(raw["payload"]),
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
        claims.update(changes or {})
        return {"claims": claims, "signature": self.sign(claims)}

    def receipt_attestation(self, attempt: dict, payload_hash: str, *, changes: dict | None = None) -> dict:
        claims = {
            "schema": gateway.RECEIPT_ATTESTATION_SCHEMA,
            "gateway_key_id": "gateway-1",
            "action": "attest-runtime-receipt",
            "project_id": attempt["project_id"],
            "attempt_id": attempt["attempt_id"],
            "provider_task_id": attempt["lifecycle"]["provider_task_id"],
            "receipt_payload_hash": payload_hash,
            "nonce": uuid.uuid4().hex,
            "issued_at": self.now.isoformat(),
            "expires_at": (self.now + timedelta(minutes=4)).isoformat(),
        }
        claims.update(changes or {})
        return {"claims": claims, "signature": self.sign(claims)}

    def test_request_is_exact_idempotent_read_only_and_contains_no_private_material(self) -> None:
        first = self.request(self.attempt, "launch")
        second = self.request(self.attempt, "launch")
        self.assertEqual(first, second)
        self.assertFalse(first["external_effects_allowed"])
        self.assertEqual(first["attempt"]["capabilities"], ["emit_artifact", "read_project"])
        serialized = gateway.canonical_json(first).casefold()
        self.assertNotIn("private_key", serialized)
        self.assertNotIn("credential", serialized)

    def test_signed_launch_result_advances_lifecycle_with_exact_model(self) -> None:
        request = self.request(self.attempt, "launch")
        record = gateway.verify_result(
            self.envelope(request),
            request=request,
            keyring_path=self.keyring,
            artifact_root=self.root,
            now=self.now,
        )
        advanced = self.apply(self.attempt, record)
        self.assertEqual(advanced["lifecycle"]["status"], "launched")
        self.assertEqual(advanced["lifecycle"]["observed_model"], "gpt-5.6-sol")
        self.assertEqual(advanced["lifecycle"]["provider_task_id"], "provider-task-1")

    def test_signed_running_and_terminal_usage_is_monotonic_and_provider_attributable(self) -> None:
        launch_request = self.request(self.attempt, "launch")
        launch = gateway.verify_result(
            self.envelope(launch_request),
            request=launch_request,
            keyring_path=self.keyring,
            artifact_root=self.root,
            now=self.now,
        )
        attempt = self.apply(self.attempt, launch)
        running_usage = {
            "input_tokens": 50,
            "cached_input_tokens": 20,
            "output_tokens": 10,
            "total_tokens": 60,
            "cost_usd": 0.005,
            "currency": "USD",
            "semantics": "cumulative",
            "provider_revision": "usage-2",
        }
        observe = self.request(attempt, "observe")
        running = gateway.verify_result(
            self.envelope(observe, event="running", sequence=2, payload={"provider_status": "running", "usage": running_usage}),
            request=observe,
            keyring_path=self.keyring,
            artifact_root=self.root,
            now=self.now,
        )
        attempt = self.apply(attempt, running)
        terminal_usage = {
            **running_usage,
            "input_tokens": 100,
            "cached_input_tokens": 40,
            "output_tokens": 25,
            "total_tokens": 125,
            "cost_usd": 0.0125,
            "semantics": "terminal",
            "provider_revision": "usage-3",
        }
        terminal_request = self.request(attempt, "observe")
        terminal = gateway.verify_result(
            self.envelope(
                terminal_request,
                event="terminal",
                sequence=3,
                payload={"provider_status": "completed", "status": "succeeded", "usage": terminal_usage},
            ),
            request=terminal_request,
            keyring_path=self.keyring,
            artifact_root=self.root,
            now=self.now,
        )
        attempt = self.apply(attempt, terminal)
        self.assertEqual(attempt["lifecycle"]["status"], "succeeded")
        self.assertEqual(attempt["lifecycle"]["telemetry"]["provider_revisions"], ["usage-2", "usage-3"])
        self.assertEqual(
            attempt["lifecycle"]["telemetry"]["source_observation_digests"],
            [running["observation_digest"], terminal["observation_digest"]],
        )

    def test_receipt_attestation_is_gateway_signed_and_binds_exact_provider_task_and_payload(self) -> None:
        request = self.request(self.attempt, "launch")
        launch = gateway.verify_result(
            self.envelope(request),
            request=request,
            keyring_path=self.keyring,
            artifact_root=self.root,
            now=self.now,
        )
        attempt = self.apply(self.attempt, launch)
        payload_hash = digest("a")
        envelope = self.receipt_attestation(attempt, payload_hash)
        verified = gateway.verify_receipt_attestation(
            envelope,
            attempt=attempt,
            keyring_path=self.keyring,
            now=self.now,
        )
        self.assertNotIsInstance(verified, dict)
        self.assertEqual(verified["claims"]["receipt_payload_hash"], payload_hash)
        for changes in (
            {"provider_task_id": "other-task"},
            {"receipt_payload_hash": digest("b")},
        ):
            candidate = self.receipt_attestation(attempt, payload_hash, changes=changes)
            if changes.get("receipt_payload_hash"):
                candidate["signature"] = "invalid"
            with self.assertRaises(gateway.GatewayError):
                gateway.verify_receipt_attestation(
                    candidate,
                    attempt=attempt,
                    keyring_path=self.keyring,
                    now=self.now,
                )

    def test_launch_unknown_preserves_intent_and_restart_query_uses_same_idempotency_key(self) -> None:
        request = self.request(self.attempt, "launch")
        record = gateway.verify_result(
            self.envelope(request, event="launch_unknown", task_id=None, observed_model=None),
            request=request,
            keyring_path=self.keyring,
            artifact_root=self.root,
            now=self.now,
        )
        unknown = self.apply(self.attempt, record)
        self.assertEqual(unknown["lifecycle"]["status"], "launch_unknown")
        self.assertIsNone(unknown["lifecycle"]["provider_task_id"])
        query = self.request(unknown, "query")
        self.assertEqual(query["attempt"]["idempotency_key"], request["attempt"]["idempotency_key"])
        still_unknown = gateway.verify_result(
            self.envelope(query, event="launch_unknown", task_id=None, observed_model=None, sequence=2),
            request=query,
            keyring_path=self.keyring,
            artifact_root=self.root,
            now=self.now,
        )
        recovered_after_restart = self.apply(unknown, still_unknown)
        self.assertEqual(recovered_after_restart["lifecycle"]["status"], "launch_unknown")
        self.assertEqual(recovered_after_restart["lifecycle"]["last_provider_sequence"], 2)
        with self.assertRaises(gateway.GatewayError):
            self.request(unknown, "launch")

    def test_definitive_missing_luna_or_sol_model_is_an_honest_blocked_terminal(self) -> None:
        request = self.request(self.attempt, "launch")
        record = gateway.verify_result(
            self.envelope(
                request,
                event="launch_rejected",
                task_id=None,
                observed_model=None,
                payload={"provider_status": "rejected", "reason": "model_unavailable", "usage": None},
            ),
            request=request,
            keyring_path=self.keyring,
            artifact_root=self.root,
            now=self.now,
        )
        blocked = self.apply(self.attempt, record)
        self.assertEqual(blocked["lifecycle"]["status"], "blocked_model_unavailable")
        self.assertIsNone(blocked["lifecycle"]["observed_model"])
        self.assertEqual(
            lifecycle.audit_attempt(blocked, keyring_path=self.keyring),
            [],
        )

    def test_tampered_signature_request_artifact_identity_and_model_fail_closed(self) -> None:
        request = self.request(self.attempt, "launch")
        cases = []
        invalid_signature = self.envelope(request)
        invalid_signature["signature"] = "invalid"
        cases.append(invalid_signature)
        cases.append(self.envelope(request, changes={"request_digest": digest("f")}))
        cases.append(self.envelope(request, changes={"work_id": "other-work"}))
        cases.append(self.envelope(request, observed_model="gpt-5.6-terra"))
        tampered = self.envelope(request)
        raw_path = self.root / tampered["claims"]["raw_artifact_path"]
        raw_path.write_text('{"tampered":true}', encoding="utf-8")
        cases.append(tampered)
        for envelope in cases:
            with self.assertRaises((gateway.GatewayError, ValueError)):
                gateway.verify_result(
                    envelope,
                    request=request,
                    keyring_path=self.keyring,
                    artifact_root=self.root,
                    now=self.now,
                )

    def test_expired_lease_wrong_capabilities_model_and_parent_block_before_gateway(self) -> None:
        cases = []
        expired = deepcopy(self.attempt)
        expired["lease_fence"]["expires_at"] = (self.now - timedelta(seconds=1)).isoformat()
        cases.append(expired)
        capabilities = deepcopy(self.attempt)
        capabilities["capabilities"] = ["shell"]
        cases.append(capabilities)
        model = deepcopy(self.attempt)
        model["requested_model"] = "gpt-5.6-terra"
        cases.append(model)
        parent = deepcopy(self.attempt)
        parent["parent_runtime_id"] = "manager"
        cases.append(parent)
        bad_scope_digest = deepcopy(self.attempt)
        bad_scope_digest["scope_digest"] = digest("f")
        cases.append(bad_scope_digest)
        bad_budget = deepcopy(self.attempt)
        bad_budget["budget"]["token_limit"] = -1
        cases.append(bad_budget)
        wrong_manifest = deepcopy(self.attempt)
        wrong_manifest["fabric_manifest_digest"] = digest("e")
        cases.append(wrong_manifest)
        for attempt in cases:
            with self.assertRaises(gateway.GatewayError):
                self.request(attempt, "launch")

    def test_post_launch_operations_use_current_authority_not_the_expired_admission_fence(self) -> None:
        request = self.request(self.attempt, "launch")
        launch = gateway.verify_result(
            self.envelope(request), request=request, keyring_path=self.keyring,
            artifact_root=self.root, now=self.now,
        )
        attempt = self.apply(self.attempt, launch)
        attempt["lease_fence"]["expires_at"] = (self.now - timedelta(seconds=1)).isoformat()
        observe = gateway.build_request(
            attempt,
            manifest=self.manifest,
            operation="observe",
            current_lease_fence=self.current_fence(),
            now=self.now,
        )
        self.assertNotEqual(observe["lease_fence"]["lease_id"], attempt["lease_fence"]["lease_id"])

    def test_vertical_slice_manifest_enforces_one_exact_read_only_sol_luna_pair(self) -> None:
        manifest = {
            "max_managers": 1,
            "max_workers_per_manager": 1,
            "max_total_workers": 1,
            "external_effects_allowed": False,
            "managers": [
                {
                    "id": "manager-1",
                    "model": "gpt-5.6-sol",
                    "workers": [
                        {
                            "id": "worker-1",
                            "model": "gpt-5.6-luna",
                            "write_scope": [],
                            "capabilities": ["emit_artifact", "read_project"],
                            "may_delegate": False,
                            "external_effects": False,
                        }
                    ],
                }
            ],
        }
        self.assertTrue(gateway.validate_vertical_slice_manifest(manifest)["valid"])
        for mutation in (
            lambda value: value["managers"].append(deepcopy(value["managers"][0])),
            lambda value: value["managers"][0]["workers"][0].update({"model": "gpt-5.6-sol"}),
            lambda value: value["managers"][0]["workers"][0].update({"write_scope": ["src"]}),
            lambda value: value.update({"external_effects_allowed": True}),
        ):
            candidate = deepcopy(manifest)
            mutation(candidate)
            self.assertFalse(gateway.validate_vertical_slice_manifest(candidate)["valid"])


if __name__ == "__main__":
    unittest.main()
