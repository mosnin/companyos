#!/usr/bin/env python3
"""Failing fixture contract for the protected OpenAI Responses gateway.

This suite deliberately has no provider, credential, controller, or scheduler
dependency.  It remains red until the feature-off adapter documented in
PHASE_2_OPENAI_RESPONSES_GATEWAY_IMPLEMENTATION_CONTRACT.md exists.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


HERE = Path(__file__).resolve().parent


def load_local(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime_gateway = load_local("runtime_gateway")
runtime_lifecycle = load_local("runtime_lifecycle")

try:
    responses_gateway = load_local("openai_responses_gateway")
    IMPORT_ERROR: Exception | None = None
except FileNotFoundError as exc:
    responses_gateway = None
    IMPORT_ERROR = exc


COMMAND_SCHEMA = "company-os.openai-responses-gateway-command.v1"
REQUEST_KEYRING_SCHEMA = "company-os.openai-responses-request-keyring.v1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return runtime_gateway.sha256_json(value)


class RecordingTransport:
    """Raw-byte fixture transport; it never performs a network request."""

    fixture_only = True

    def __init__(
        self,
        *,
        create: bytes | BaseException,
        retrieve: bytes | BaseException | None = None,
        cancel: bytes | BaseException | None = None,
        on_create: Callable[[bytes], None] | None = None,
        fixture_fault_after_raw_retain: BaseException | None = None,
    ) -> None:
        self.create_reply = create
        self.retrieve_reply = retrieve if retrieve is not None else create
        self.cancel_reply = cancel if cancel is not None else create
        self.on_create = on_create
        self.fixture_fault_after_raw_retain = fixture_fault_after_raw_retain
        self.create_calls: list[bytes] = []
        self.retrieve_calls: list[str] = []
        self.cancel_calls: list[str] = []

    @staticmethod
    def _reply(value: bytes | BaseException) -> bytes:
        if isinstance(value, BaseException):
            raise value
        return value

    def create(self, request_body: bytes) -> bytes:
        self.create_calls.append(request_body)
        if self.on_create:
            self.on_create(request_body)
        return self._reply(self.create_reply)

    def retrieve(self, provider_task_id: str) -> bytes:
        self.retrieve_calls.append(provider_task_id)
        return self._reply(self.retrieve_reply)

    def cancel(self, provider_task_id: str) -> bytes:
        self.cancel_calls.append(provider_task_id)
        return self._reply(self.cancel_reply)


class OpenAIResponsesGatewayContractTests(unittest.TestCase):
    """The implementation must satisfy this test surface without weakening it."""

    def setUp(self) -> None:
        if responses_gateway is None:
            self.fail(
                "missing fixture-only adapter: "
                "skills/company-os/elastic-company-os/scripts/openai_responses_gateway.py"
            )
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        os.chmod(self.root, 0o700)
        self.now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
        self.socket_path = self.root / "gateway.sock"
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        self.state_path = self.root / "gateway-state.json"
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir(mode=0o700)
        self.request_private, self.request_public = self.make_keypair("request")
        self.gateway_private, self.gateway_public = self.make_keypair("gateway")
        self.decision_private, self.decision_public = self.make_keypair("decision")
        self.request_keyring = self.root / "request-keyring.json"
        self.gateway_keyring = self.root / "gateway-keyring.json"
        self.write_keyrings()
        self.attempt, self.manifest = self.make_admitted_attempt()
        self.launch_request = runtime_gateway.build_request(
            self.attempt, manifest=self.manifest, operation="launch", now=self.now
        )

    def tearDown(self) -> None:
        if hasattr(self, "socket"):
            self.socket.close()
        if hasattr(self, "temporary"):
            self.temporary.cleanup()

    def make_keypair(self, name: str) -> tuple[Path, Path]:
        private = self.root / f"{name}-private.pem"
        public = self.root / f"{name}-public.pem"
        subprocess.run(
            [
                "openssl", "genpkey", "-algorithm", "RSA",
                "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
            check=True,
            capture_output=True,
        )
        return private, public

    def write_keyrings(
        self,
        *,
        request_status: str = "active",
        gateway_status: str = "active",
        request_key_id: str = "controller-request-1",
        gateway_key_id: str = "responses-gateway-1",
        request_not_before: datetime | None = None,
        request_not_after: datetime | None = None,
    ) -> None:
        validity = {
            "not_before": (request_not_before or self.now - timedelta(hours=1)).isoformat(),
            "not_after": (request_not_after or self.now + timedelta(hours=1)).isoformat(),
        }
        self.request_keyring.write_text(
            json.dumps({
                "schema": REQUEST_KEYRING_SCHEMA,
                "keys": [{
                    "key_id": request_key_id,
                    "algorithm": "rsa-sha256",
                    "public_key_path": str(self.request_public),
                    "status": request_status,
                    **validity,
                }],
            }, sort_keys=True),
            encoding="utf-8",
        )
        self.gateway_keyring.write_text(
            json.dumps({
                "schema": "company-os.runtime-gateway-keyring.v1",
                "keys": [{
                    "key_id": gateway_key_id,
                    "algorithm": "rsa-sha256",
                    "public_key_path": str(self.gateway_public),
                    "status": gateway_status,
                    **validity,
                }],
            }, sort_keys=True),
            encoding="utf-8",
        )

    def make_admitted_attempt(self) -> tuple[dict[str, Any], dict[str, Any]]:
        budget = {
            "time_minutes": 10,
            "token_limit": 2_000,
            "cost_usd": 1.0,
            "max_concurrency": 1,
            "max_retries": 0,
        }
        attempt = {
            "attempt_id": "manager-attempt-1",
            "project_id": "company-os-core",
            "manifest_identity_id": "manager-1",
            "work_id": "phase-2-responses-canary",
            "cycle_id": "cycle-phase-2-1",
            "parent_runtime_id": "master",
            "role": "manager",
            "requested_model": "gpt-5.6-sol",
            "provider": "openai",
            "surface": "responses-api",
            "account": "fixture-project",
            "scope": [".company-os/runtime-artifacts"],
            "scope_digest": "",
            "budget": deepcopy(budget),
            "capabilities": ["emit_artifact", "read_project"],
            "fabric_manifest_digest": "",
            "phase2_contract_digest": "e" * 64,
            "idempotency_key": "phase-2-responses-manager-1",
            "program_version": 6,
            "actor_grant": {
                "token": "signed-admission-token",
                "grant_digest": "a" * 64,
            },
            "lease_fence": {
                "lease_id": "lease-1",
                "generation": 1,
                "owner": "master-sol",
                "program_version": 6,
                "expires_at": (self.now + timedelta(minutes=10)).isoformat(),
                "allowed_transitions": ["admit-runtime-attempt"],
            },
            "lifecycle": runtime_lifecycle.empty_lifecycle(),
        }
        manifest = {
            "max_managers": 1,
            "max_workers_per_manager": 1,
            "max_total_workers": 1,
            "external_effects_allowed": False,
            "managers": [{
                "id": "manager-1",
                "model": "gpt-5.6-sol",
                "write_scope": [".company-os/runtime-artifacts"],
                "budget": deepcopy(budget),
                "workers": [{
                    "id": "worker-1",
                    "model": "gpt-5.6-luna",
                    "write_scope": [],
                    "budget": deepcopy(budget),
                    "capabilities": ["emit_artifact", "read_project"],
                    "may_delegate": False,
                    "external_effects": False,
                }],
            }],
        }
        attempt["scope_digest"] = sha256_json(attempt["scope"])
        attempt["fabric_manifest_digest"] = sha256_json(manifest)
        return attempt, manifest

    def sign(self, claims: dict[str, Any], private: Path) -> str:
        payload = self.root / f"signed-{uuid.uuid4().hex}.json"
        signature = self.root / f"signed-{uuid.uuid4().hex}.bin"
        payload.write_text(canonical_json(claims), encoding="utf-8")
        subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(private), "-out", str(signature), str(payload)],
            check=True,
            capture_output=True,
        )
        return base64.urlsafe_b64encode(signature.read_bytes()).decode("ascii").rstrip("=")

    def signed_decision_token(self, claims: dict[str, Any]) -> str:
        encoded = base64.urlsafe_b64encode(
            canonical_json(claims).encode("utf-8")
        ).decode("ascii").rstrip("=")
        payload = self.root / f"decision-{uuid.uuid4().hex}.txt"
        signature = self.root / f"decision-{uuid.uuid4().hex}.bin"
        payload.write_text(encoded, encoding="ascii")
        subprocess.run(
            [
                "openssl", "dgst", "-sha256", "-sign", str(self.decision_private),
                "-out", str(signature), str(payload),
            ],
            check=True,
            capture_output=True,
        )
        encoded_signature = base64.urlsafe_b64encode(
            signature.read_bytes()
        ).decode("ascii").rstrip("=")
        return f"{encoded}.{encoded_signature}"

    def cancellation_token(
        self,
        attempt: dict[str, Any],
        *,
        requested_by: str = "master-sol",
        reason: str = "stop the fixture runtime",
        requested_at: str | None = None,
        after_observation_count: int = 0,
    ) -> tuple[str, str, str]:
        requested_at = requested_at or self.now.isoformat()
        request_payload = {
            "attempt_id": attempt["attempt_id"],
            "requested_by": requested_by,
            "reason": reason,
            "requested_at": requested_at,
            "after_observation_count": after_observation_count,
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
            "payload_hash": runtime_lifecycle.sha256_json(request_payload),
            "nonce": uuid.uuid4().hex,
            "expiry": (self.now + timedelta(minutes=5)).isoformat(),
        }
        return self.signed_decision_token(claims), requested_at, reason

    def signed_command(
        self,
        request: dict[str, Any] | None = None,
        *,
        changes: dict[str, Any] | None = None,
        private: Path | None = None,
    ) -> dict[str, Any]:
        request = deepcopy(request or self.launch_request)
        claims: dict[str, Any] = {
            "schema": COMMAND_SCHEMA,
            "request_key_id": "controller-request-1",
            "gateway_request": request,
            "gateway_request_digest": sha256_json(request),
            "nonce": uuid.uuid4().hex,
            "issued_at": self.now.isoformat(),
            "expires_at": (self.now + timedelta(minutes=4)).isoformat(),
        }
        claims.update(changes or {})
        return {"claims": claims, "signature": self.sign(claims, private or self.request_private)}

    def rebound_request(self, request: dict[str, Any]) -> dict[str, Any]:
        request = deepcopy(request)
        request["request_digest"] = sha256_json({
            key: value for key, value in request.items() if key != "request_digest"
        })
        return request

    def response_bytes(
        self,
        *,
        status: str = "in_progress",
        model: str = "gpt-5.6-sol",
        response_id: str = "resp_phase2_1",
        usage: dict[str, Any] | None = None,
    ) -> bytes:
        payload: dict[str, Any] = {
            "id": response_id,
            "object": "response",
            "created_at": 1785671998,
            "status": status,
            "model": model,
        }
        if status in {"completed", "failed", "cancelled", "incomplete"}:
            payload["completed_at"] = 1785672001
            payload["usage"] = usage or {
                "input_tokens": 7,
                "input_tokens_details": {"cached_tokens": 2, "cache_write_tokens": 0},
                "output_tokens": 11,
                "output_tokens_details": {"reasoning_tokens": 1},
                "total_tokens": 18,
            }
        return canonical_json(payload).encode("utf-8")

    def gateway(
        self,
        *,
        state_name: str = "gateway-state.json",
        artifact_name: str = "artifacts",
    ) -> Any:
        state_path = self.root / state_name
        artifact_root = self.root / artifact_name
        if not artifact_root.exists():
            artifact_root.mkdir(mode=0o700)
        return responses_gateway.FixtureResponsesGateway(
            socket_path=self.socket_path,
            state_path=state_path,
            artifact_root=artifact_root,
            request_keyring_path=self.request_keyring,
            gateway_keyring_path=self.gateway_keyring,
            gateway_key_id="responses-gateway-1",
            gateway_private_key_path=self.gateway_private,
            decision_public_key_path=self.decision_public,
            now=self.now,
        )

    def assert_gateway_error(self, callback: Callable[[], object]) -> None:
        with self.assertRaises(responses_gateway.ResponsesGatewayError):
            callback()

    def test_signed_command_is_authenticated_before_any_tombstone_or_transport_effect(self) -> None:
        transport = RecordingTransport(create=self.response_bytes())
        command = self.signed_command(private=self.gateway_private)
        self.assert_gateway_error(lambda: self.gateway().handle(command, transport=transport))
        self.assertEqual(transport.create_calls, [])
        self.assertFalse(self.state_path.exists())

    def test_request_verification_and_result_signing_keys_must_be_cryptographically_distinct(self) -> None:
        self.request_public = self.gateway_public
        self.write_keyrings()
        transport = RecordingTransport(create=self.response_bytes())
        self.assert_gateway_error(lambda: self.gateway().handle(
            self.signed_command(private=self.gateway_private),
            transport=transport,
        ))
        self.assertEqual(transport.create_calls, [])
        self.assertFalse(self.state_path.exists())

    def test_signed_but_non_admitted_request_is_rejected_before_effect(self) -> None:
        request = deepcopy(self.launch_request)
        request["attempt"]["capabilities"] = ["emit_artifact", "read_project", "write_project"]
        request = self.rebound_request(request)
        transport = RecordingTransport(create=self.response_bytes())
        self.assert_gateway_error(lambda: self.gateway().handle(
            self.signed_command(request),
            transport=transport,
        ))
        self.assertEqual(transport.create_calls, [])
        self.assertFalse(self.state_path.exists())

    def test_socket_and_filesystem_boundary_is_owner_only_and_rejects_symlink_or_path_escape(self) -> None:
        command = self.signed_command()
        transport = RecordingTransport(create=self.response_bytes())
        os.chmod(self.socket_path, 0o666)
        self.assert_gateway_error(lambda: self.gateway().handle(command, transport=transport))
        self.assertEqual(transport.create_calls, [])
        os.chmod(self.socket_path, 0o600)
        escaped = self.root / "escaped-artifacts"
        escaped.symlink_to(self.artifacts, target_is_directory=True)
        invalid = responses_gateway.FixtureResponsesGateway(
            socket_path=self.socket_path,
            state_path=self.state_path,
            artifact_root=escaped,
            request_keyring_path=self.request_keyring,
            gateway_keyring_path=self.gateway_keyring,
            gateway_key_id="responses-gateway-1",
            gateway_private_key_path=self.gateway_private,
            decision_public_key_path=self.decision_public,
            now=self.now,
        )
        self.assert_gateway_error(lambda: invalid.handle(command, transport=transport))
        os.chmod(self.gateway_private, 0o644)
        self.assert_gateway_error(lambda: self.gateway().handle(command, transport=transport))
        self.assertEqual(transport.create_calls, [])

    def test_launch_persists_tombstone_before_exact_no_tool_store_false_request(self) -> None:
        def assert_tombstone(body: bytes) -> None:
            self.assertTrue(self.state_path.is_file())
            state = self.state_path.read_text(encoding="utf-8")
            self.assertIn("launching", state)
            payload = json.loads(body)
            self.assertEqual(payload, {
                "background": True,
                "input": "Return exactly READY. Do not call tools or perform external actions.",
                "model": "gpt-5.6-sol",
                "store": False,
                "tools": [],
            })
            self.assertEqual(set(payload) & {"api_key", "credential", "secret"}, set())

        transport = RecordingTransport(create=self.response_bytes(), on_create=assert_tombstone)
        envelope = self.gateway().handle(self.signed_command(), transport=transport)
        self.assertEqual(len(transport.create_calls), 1)
        verified = runtime_gateway.verify_result(
            envelope,
            request=self.launch_request,
            keyring_path=self.gateway_keyring,
            artifact_root=self.artifacts,
            now=self.now,
        )
        self.assertEqual(verified["claims"]["provider_task_id"], "resp_phase2_1")
        self.assertEqual(verified["claims"]["observed_model"], "gpt-5.6-sol")
        self.assertEqual(verified["raw"]["payload"]["provider_status"], "in_progress")
        self.assertEqual(
            verified["raw"]["payload"]["provider_fixture_schema"],
            "responses-fixture-no-tools-v1",
        )
        self.assertEqual(
            verified["raw"]["payload"]["fixed_input_sha256"],
            hashlib.sha256(
                b"Return exactly READY. Do not call tools or perform external actions."
            ).hexdigest(),
        )
        provider_raw = self.artifacts / verified["raw"]["payload"]["provider_raw_artifact_path"]
        self.assertEqual(provider_raw.read_bytes(), self.response_bytes())
        self.assertEqual(
            verified["raw"]["payload"]["provider_raw_sha256"],
            hashlib.sha256(provider_raw.read_bytes()).hexdigest(),
        )
        self.assertEqual(verified["raw"]["payload"]["provider_raw_size"], len(provider_raw.read_bytes()))
        self.assertEqual(provider_raw.stat().st_mode & 0o777, 0o600)

    def test_raw_bytes_response_id_model_status_timestamps_and_terminal_usage_are_mandatory(self) -> None:
        cases = {
            "missing-id": b'{"created_at":1785671998,"status":"in_progress","model":"gpt-5.6-sol"}',
            "missing-model": b'{"created_at":1785671998,"id":"resp_1","status":"in_progress"}',
            "missing-status": b'{"created_at":1785671998,"id":"resp_1","model":"gpt-5.6-sol"}',
            "missing-created-at": b'{"id":"resp_1","status":"in_progress","model":"gpt-5.6-sol"}',
            "duplicate-key": b'{"created_at":1785671998,"id":"resp_1","id":"resp_2","status":"in_progress","model":"gpt-5.6-sol"}',
            "missing-terminal-usage": (
                b'{"completed_at":1785672001,'
                b'"created_at":1785671998,'
                b'"id":"resp_1","model":"gpt-5.6-sol",'
                b'"object":"response","status":"completed"}'
            ),
            "negative-usage": self.response_bytes(
                status="completed",
                usage={
                    "input_tokens": -1,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens": 0,
                    "output_tokens_details": {"reasoning_tokens": 0},
                    "total_tokens": 0,
                },
            ),
        }
        for index, (name, raw) in enumerate(cases.items()):
            with self.subTest(name=name):
                transport = RecordingTransport(create=raw)
                gateway = self.gateway(
                    state_name=f"invalid-{index}.json",
                    artifact_name=f"invalid-artifacts-{index}",
                )
                self.assert_gateway_error(lambda: gateway.handle(self.signed_command(), transport=transport))

    def test_terminal_create_retains_task_and_exact_usage_without_inventing_cost(self) -> None:
        raw = self.response_bytes(status="completed")
        transport = RecordingTransport(create=raw)
        command = self.signed_command()
        envelope = self.gateway().handle(command, transport=transport)
        self.assertEqual(envelope["claims"]["event_type"], "launch")
        self.assertEqual(envelope["claims"]["provider_task_id"], "resp_phase2_1")
        verified = runtime_gateway.verify_result(
            envelope,
            request=self.launch_request,
            keyring_path=self.gateway_keyring,
            artifact_root=self.artifacts,
            now=self.now,
        )
        payload = verified["raw"]["payload"]
        self.assertEqual(payload["provider_status"], "completed")
        self.assertEqual(payload["provider_usage"], json.loads(raw)["usage"])
        self.assertEqual(payload["cost_status"], "unavailable")
        self.assertIsNone(payload["usage"])
        self.assertNotIn("cost_usd", payload)
        self.assertEqual(self.gateway().handle(command, transport=transport), envelope)
        self.assertEqual(len(transport.create_calls), 1)
        attempted = deepcopy(self.attempt)
        attempted["lifecycle"] = {
            **runtime_lifecycle.empty_lifecycle(),
            "status": "launched",
            "provider_task_id": "resp_phase2_1",
        }
        observe = runtime_gateway.build_request(
            attempted,
            manifest=self.manifest,
            operation="observe",
            current_lease_fence={**attempted["lease_fence"], "lease_id": "lease-terminal-create", "generation": 2},
            now=self.now,
        )
        observer = RecordingTransport(create=b"unused", retrieve=self.response_bytes(response_id="resp_forbidden_retrieve"))
        terminal = self.gateway().handle(self.signed_command(observe), transport=observer)
        self.assertEqual(observer.retrieve_calls, [])
        self.assertEqual(terminal["claims"]["event_type"], "terminal")
        terminal_record = runtime_gateway.verify_result(
            terminal,
            request=observe,
            keyring_path=self.gateway_keyring,
            artifact_root=self.artifacts,
            now=self.now,
        )
        self.assertEqual(terminal_record["raw"]["payload"]["provider_status"], "completed")

    def test_provider_shaped_credentials_are_rejected_before_raw_retention(self) -> None:
        credential_fields = {
            "access_token": "access-fixture-secret",
            "client_token": "client-fixture-secret",
            "provider_token": "provider-fixture-secret",
            "bearer_token": "bearer-fixture-secret",
            "authorization": "Bearer authorization-fixture-secret",
            "metadata": "Authorization: Bearer embedded-fixture-secret",
            "signing_keys": "plural-signing-fixture-secret",
            "privateKeys": "camel-private-fixture-secret",
            "jwt": "jwt-fixture-secret",
            "api-keys": "kebab-api-key-fixture-secret",
            "id": "Authorization: Bearer allowed-field-fixture-secret",
        }
        for index, (field, secret) in enumerate(credential_fields.items()):
            with self.subTest(field=field):
                payload = json.loads(self.response_bytes())
                payload[field] = secret
                state_name = f"secret-{index}.json"
                artifact_name = f"secret-artifacts-{index}"
                gateway = self.gateway(state_name=state_name, artifact_name=artifact_name)
                transport = RecordingTransport(create=canonical_json(payload).encode("utf-8"))
                self.assert_gateway_error(lambda: gateway.handle(
                    self.signed_command(), transport=transport,
                ))
                retained_state = json.loads((self.root / state_name).read_text())
                self.assertEqual(
                    retained_state["attempts"]["manager-attempt-1"]["status"],
                    "launch_unknown",
                )
                artifact_bytes = b"".join(
                    path.read_bytes()
                    for path in (self.root / artifact_name).iterdir()
                    if path.is_file()
                )
                self.assertNotIn(secret.encode("utf-8"), artifact_bytes)

    def test_unknown_provider_fields_are_rejected_by_the_versioned_positive_schema(self) -> None:
        payload = json.loads(self.response_bytes())
        payload["harmless_future_field"] = "not a credential"
        transport = RecordingTransport(create=canonical_json(payload).encode("utf-8"))
        command = self.signed_command()
        self.assert_gateway_error(lambda: self.gateway().handle(command, transport=transport))
        retained = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(retained["attempts"]["manager-attempt-1"]["status"], "launch_unknown")
        self.assertFalse(any(self.artifacts.iterdir()))
        replay = self.gateway().handle(command, transport=transport)
        self.assertEqual(replay["claims"]["event_type"], "launch_unknown")
        self.assertEqual(len(transport.create_calls), 1)

    def test_duplicate_provider_task_rejects_before_retaining_the_conflicting_body(self) -> None:
        self.gateway().handle(
            self.signed_command(),
            transport=RecordingTransport(create=self.response_bytes()),
        )
        before_artifacts = {path.name for path in self.artifacts.iterdir()}
        second_attempt = deepcopy(self.attempt)
        second_attempt["attempt_id"] = "manager-attempt-2"
        second_attempt["idempotency_key"] = "phase-2-responses-manager-2"
        second_request = runtime_gateway.build_request(
            second_attempt,
            manifest=self.manifest,
            operation="launch",
            now=self.now,
        )
        conflicting_payload = json.loads(self.response_bytes())
        conflicting_payload["created_at"] = 1785671999
        transport = RecordingTransport(
            create=canonical_json(conflicting_payload).encode("utf-8")
        )
        self.assert_gateway_error(lambda: self.gateway().handle(
            self.signed_command(second_request),
            transport=transport,
        ))
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["attempts"]["manager-attempt-2"]["status"], "launch_unknown")
        self.assertEqual({path.name for path in self.artifacts.iterdir()}, before_artifacts)

    def test_model_mismatch_fails_closed_without_a_signed_success_or_provider_binding(self) -> None:
        transport = RecordingTransport(create=self.response_bytes(model="gpt-5.6-terra"))
        command = self.signed_command()
        self.assert_gateway_error(lambda: self.gateway().handle(command, transport=transport))
        retained = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(retained["attempts"]["manager-attempt-1"]["status"], "launch_unknown")
        self.assertNotIn("resp_phase2_1", canonical_json(retained))
        self.assertNotIn("gpt-5.6-terra", canonical_json(retained))
        replay = self.gateway().handle(command, transport=transport)
        self.assertEqual(replay["claims"]["event_type"], "launch_unknown")
        self.assertEqual(len(transport.create_calls), 1)

    def test_ambiguous_create_becomes_launch_unknown_and_never_blind_retries(self) -> None:
        transport = RecordingTransport(create=ConnectionError("connection lost after provider effect"))
        command = self.signed_command()
        first = self.gateway().handle(command, transport=transport)
        self.assertEqual(first["claims"]["event_type"], "launch_unknown")
        self.assertEqual(first["claims"]["provider_task_id"], None)
        self.assertEqual(len(transport.create_calls), 1)
        retry = self.gateway().handle(command, transport=transport)
        self.assertEqual(retry, first)
        self.assertEqual(len(transport.create_calls), 1)
        changed = self.signed_command(changes={"nonce": "changed-command-nonce"})
        self.assert_gateway_error(lambda: self.gateway().handle(changed, transport=transport))
        self.assertEqual(len(transport.create_calls), 1)
        attempted = deepcopy(self.attempt)
        attempted["lifecycle"] = {**runtime_lifecycle.empty_lifecycle(), "status": "launch_unknown"}
        query = runtime_gateway.build_request(
            attempted,
            manifest=self.manifest,
            operation="query",
            current_lease_fence={**attempted["lease_fence"], "lease_id": "lease-query", "generation": 2},
            now=self.now,
        )
        query_transport = RecordingTransport(create=b"unused", retrieve=self.response_bytes())
        query_result = self.gateway().handle(self.signed_command(query), transport=query_transport)
        self.assertEqual(query_result["claims"]["event_type"], "launch_unknown")
        self.assertIsNone(query_result["claims"]["provider_task_id"])
        self.assertEqual(query_transport.retrieve_calls, [])
        self.assertEqual(len(transport.create_calls), 1)

    def test_restart_after_crash_boundaries_never_blind_relaunches(self) -> None:
        class SimulatedProcessCrash(BaseException):
            pass

        command = self.signed_command()
        after_effect = RecordingTransport(
            create=self.response_bytes(),
            on_create=lambda _body: (_ for _ in ()).throw(SimulatedProcessCrash()),
        )
        with self.assertRaises(SimulatedProcessCrash):
            self.gateway().handle(command, transport=after_effect)
        recovered_unknown = self.gateway().handle(
            command,
            transport=RecordingTransport(create=self.response_bytes()),
        )
        self.assertEqual(recovered_unknown["claims"]["event_type"], "launch_unknown")
        self.assertEqual(len(after_effect.create_calls), 1)

        raw_state = "raw-retained-state.json"
        raw_artifacts = "raw-retained-artifacts"
        after_raw = RecordingTransport(
            create=self.response_bytes(),
            fixture_fault_after_raw_retain=SimulatedProcessCrash(),
        )
        raw_gateway = self.gateway(state_name=raw_state, artifact_name=raw_artifacts)
        with self.assertRaises(SimulatedProcessCrash):
            raw_gateway.handle(command, transport=after_raw)
        recovery_transport = RecordingTransport(create=self.response_bytes(response_id="resp_should_not_exist"))
        recovered = self.gateway(state_name=raw_state, artifact_name=raw_artifacts).handle(
            command,
            transport=recovery_transport,
        )
        self.assertEqual(recovered["claims"]["provider_task_id"], "resp_phase2_1")
        self.assertEqual(recovery_transport.create_calls, [])

        tamper_state = "tamper-retained-state.json"
        tamper_artifacts = "tamper-retained-artifacts"
        tamper_transport = RecordingTransport(
            create=self.response_bytes(),
            fixture_fault_after_raw_retain=SimulatedProcessCrash(),
        )
        with self.assertRaises(SimulatedProcessCrash):
            self.gateway(state_name=tamper_state, artifact_name=tamper_artifacts).handle(
                command,
                transport=tamper_transport,
            )
        retained = json.loads((self.root / tamper_state).read_text(encoding="utf-8"))
        entry = retained["attempts"][self.attempt["attempt_id"]]
        normalized = self.root / tamper_artifacts / entry["raw_retained"]["raw_path"]
        normalized.write_bytes(normalized.read_bytes() + b" ")
        no_retry = RecordingTransport(create=self.response_bytes(response_id="resp_forbidden_retry"))
        self.assert_gateway_error(lambda: self.gateway(
            state_name=tamper_state,
            artifact_name=tamper_artifacts,
        ).handle(command, transport=no_retry))
        self.assertEqual(no_retry.create_calls, [])

    def test_query_poll_and_cancel_are_idempotent_and_bind_the_single_retained_task(self) -> None:
        launch_transport = RecordingTransport(create=self.response_bytes())
        launch = self.gateway().handle(self.signed_command(), transport=launch_transport)
        self.assertEqual(launch["claims"]["provider_task_id"], "resp_phase2_1")
        attempted = deepcopy(self.attempt)
        attempted["lifecycle"] = {**runtime_lifecycle.empty_lifecycle(), "status": "launched", "provider_task_id": "resp_phase2_1"}
        current_fence = {**attempted["lease_fence"], "lease_id": "lease-2", "generation": 2}
        observe = runtime_gateway.build_request(attempted, manifest=self.manifest, operation="observe", current_lease_fence=current_fence, now=self.now)
        observed_command = self.signed_command(observe)
        terminal = self.response_bytes(status="completed")
        observer = RecordingTransport(create=b"unused", retrieve=terminal)
        first = self.gateway().handle(observed_command, transport=observer)
        second = self.gateway().handle(observed_command, transport=observer)
        self.assertEqual(first, second)
        self.assertEqual(observer.retrieve_calls, ["resp_phase2_1"])

    def test_concurrent_exact_launch_is_serialized_to_one_effect(self) -> None:
        entered = threading.Event()

        def on_create(_body: bytes) -> None:
            entered.set()

        transport = RecordingTransport(create=self.response_bytes(), on_create=on_create)
        command = self.signed_command()
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self.gateway().handle, command, transport=transport) for _ in range(2)]
            results = [future.result(timeout=10) for future in futures]
        self.assertTrue(entered.is_set())
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(transport.create_calls), 1)

    def test_cancellation_dominates_late_success_but_retains_its_raw_evidence(self) -> None:
        launch_transport = RecordingTransport(create=self.response_bytes())
        self.gateway().handle(self.signed_command(), transport=launch_transport)
        attempted = deepcopy(self.attempt)
        attempted["lifecycle"] = {**runtime_lifecycle.empty_lifecycle(), "status": "cancel_requested", "provider_task_id": "resp_phase2_1"}
        current_fence = {**attempted["lease_fence"], "lease_id": "lease-3", "generation": 3}
        cancel = runtime_gateway.build_request(attempted, manifest=self.manifest, operation="cancel", current_lease_fence=current_fence, now=self.now)
        cancel_transport = RecordingTransport(create=b"unused", cancel=self.response_bytes(status="in_progress"))
        cancel_command = self.signed_command(cancel)
        result = self.gateway().handle(cancel_command, transport=cancel_transport)
        self.assertEqual(result["claims"]["event_type"], "cancel_acknowledged")
        self.assertEqual(self.gateway().handle(cancel_command, transport=cancel_transport), result)
        self.assertEqual(cancel_transport.cancel_calls, ["resp_phase2_1"])
        late = runtime_gateway.build_request(
            {**attempted, "lifecycle": {**attempted["lifecycle"], "status": "cancel_acknowledged"}},
            manifest=self.manifest, operation="observe", current_lease_fence={**current_fence, "lease_id": "lease-4", "generation": 4}, now=self.now,
        )
        late_result = self.gateway().handle(
            self.signed_command(late),
            transport=RecordingTransport(create=b"unused", retrieve=self.response_bytes(status="completed")),
        )
        self.assertEqual(late_result["claims"]["event_type"], "terminal")
        late_record = runtime_gateway.verify_result(
            late_result,
            request=late,
            keyring_path=self.gateway_keyring,
            artifact_root=self.artifacts,
            now=self.now,
        )
        self.assertEqual(late_record["raw"]["payload"]["provider_status"], "completed")
        self.assertEqual(late_record["raw"]["payload"]["status"], "succeeded")
        self.assertEqual(late_record["claims"]["event_type"], "terminal")
        cancelled_attempt = deepcopy(attempted)
        cancelled_attempt["lifecycle"] = {
            **runtime_lifecycle.empty_lifecycle(),
            "status": "cancelled",
            "provider_task_id": "resp_phase2_1",
            "terminal_status": "cancelled",
            "cancellation": {"grant": {"claims": {"action": "cancel-runtime"}}},
        }
        self.assert_gateway_error(lambda: self.gateway().attest_receipt(
            attempt=cancelled_attempt,
            provider_task_id="resp_phase2_1",
            receipt_payload_hash="e" * 64,
        ))

        signed_cancellation = deepcopy(self.attempt)
        signed_cancellation["lifecycle"] = {
            **runtime_lifecycle.empty_lifecycle(),
            "status": "launched",
            "provider_task_id": "resp_phase2_1",
        }
        grant_token, requested_at, reason = self.cancellation_token(signed_cancellation)
        signed_cancellation = runtime_lifecycle.request_cancellation(
            signed_cancellation,
            requested_by="master-sol",
            reason=reason,
            grant_token=grant_token,
            decision_public_key_path=self.decision_public,
            requested_at=requested_at,
            now=self.now,
        )
        signed_cancellation["lifecycle"].update({
            "status": "cancelled",
            "terminal_status": "cancelled",
            "terminal_authority": "provider_observation",
            "terminal_observation_digest": late_record["observation_digest"],
            "terminal_provider_event_id": late_record["claims"]["provider_event_id"],
        })
        # A valid decision signature alone is still insufficient: the entire
        # lifecycle must replay from the signed provider observations.
        self.assert_gateway_error(lambda: self.gateway().attest_receipt(
            attempt=signed_cancellation,
            provider_task_id="resp_phase2_1",
            receipt_payload_hash="a" * 64,
        ))
        provider_raw = self.artifacts / late_record["raw"]["payload"]["provider_raw_artifact_path"]
        provider_raw.write_bytes(provider_raw.read_bytes() + b" ")
        self.assert_gateway_error(lambda: self.gateway().attest_receipt(
            attempt=cancelled_attempt,
            provider_task_id="resp_phase2_1",
            receipt_payload_hash="f" * 64,
        ))

        caller_lies = deepcopy(self.attempt)
        caller_lies["lifecycle"] = {
            **runtime_lifecycle.empty_lifecycle(),
            "status": "succeeded",
            "provider_task_id": "resp_phase2_1",
            "terminal_status": "succeeded",
        }
        self.assert_gateway_error(lambda: self.gateway().attest_receipt(
            attempt=caller_lies,
            provider_task_id="resp_phase2_1",
            receipt_payload_hash="d" * 64,
        ))

    def test_cancel_ambiguity_is_retained_and_never_blindly_repeated(self) -> None:
        self.gateway().handle(
            self.signed_command(),
            transport=RecordingTransport(create=self.response_bytes()),
        )
        attempted = deepcopy(self.attempt)
        attempted["lifecycle"] = {
            **runtime_lifecycle.empty_lifecycle(),
            "status": "cancel_requested",
            "provider_task_id": "resp_phase2_1",
        }
        cancel = runtime_gateway.build_request(
            attempted,
            manifest=self.manifest,
            operation="cancel",
            current_lease_fence={**attempted["lease_fence"], "lease_id": "lease-cancel-unknown", "generation": 2},
            now=self.now,
        )
        command = self.signed_command(cancel)
        transport = RecordingTransport(create=b"unused", cancel=ConnectionError("ambiguous cancel"))
        self.assert_gateway_error(lambda: self.gateway().handle(command, transport=transport))
        self.assert_gateway_error(lambda: self.gateway().handle(command, transport=transport))
        self.assertEqual(transport.cancel_calls, ["resp_phase2_1"])

        malformed_state = "cancel-malformed-state.json"
        malformed_artifacts = "cancel-malformed-artifacts"
        malformed_gateway = self.gateway(
            state_name=malformed_state,
            artifact_name=malformed_artifacts,
        )
        malformed_gateway.handle(
            self.signed_command(),
            transport=RecordingTransport(create=self.response_bytes()),
        )
        malformed = RecordingTransport(create=b"unused", cancel=b"not-json")
        self.assert_gateway_error(lambda: malformed_gateway.handle(command, transport=malformed))
        self.assert_gateway_error(lambda: malformed_gateway.handle(command, transport=malformed))
        self.assertEqual(malformed.cancel_calls, ["resp_phase2_1"])

    def test_provider_timestamp_beyond_allowed_clock_skew_fails_before_signed_success(self) -> None:
        payload = json.loads(self.response_bytes())
        payload["created_at"] = 1785672061
        transport = RecordingTransport(create=canonical_json(payload).encode("utf-8"))
        self.assert_gateway_error(lambda: self.gateway().handle(
            self.signed_command(),
            transport=transport,
        ))
        self.assertEqual(len(transport.create_calls), 1)

    def test_terminal_cancel_reply_is_terminal_not_a_contradictory_ack(self) -> None:
        self.gateway().handle(
            self.signed_command(),
            transport=RecordingTransport(create=self.response_bytes()),
        )
        attempted = deepcopy(self.attempt)
        attempted["lifecycle"] = {
            **runtime_lifecycle.empty_lifecycle(),
            "status": "cancel_requested",
            "provider_task_id": "resp_phase2_1",
        }
        cancel = runtime_gateway.build_request(
            attempted,
            manifest=self.manifest,
            operation="cancel",
            current_lease_fence={**attempted["lease_fence"], "lease_id": "lease-terminal-cancel", "generation": 2},
            now=self.now,
        )
        result = self.gateway().handle(
            self.signed_command(cancel),
            transport=RecordingTransport(create=b"unused", cancel=self.response_bytes(status="cancelled")),
        )
        self.assertEqual(result["claims"]["event_type"], "terminal")
        verified = runtime_gateway.verify_result(
            result,
            request=cancel,
            keyring_path=self.gateway_keyring,
            artifact_root=self.artifacts,
            now=self.now,
        )
        self.assertEqual(verified["raw"]["payload"]["provider_status"], "cancelled")
        self.assertEqual(verified["raw"]["payload"]["status"], "cancelled")

    def test_gateway_signs_compatible_receipt_attestation_with_distinct_key(self) -> None:
        transport = RecordingTransport(create=self.response_bytes())
        self.gateway().handle(self.signed_command(), transport=transport)
        self.assert_gateway_error(lambda: self.gateway().attest_receipt(
            attempt=self.attempt,
            provider_task_id="resp_phase2_1",
            receipt_payload_hash="c" * 64,
        ))
        attempted = deepcopy(self.attempt)
        attempted["lifecycle"] = {**runtime_lifecycle.empty_lifecycle(), "status": "launched", "provider_task_id": "resp_phase2_1"}
        observe = runtime_gateway.build_request(
            attempted,
            manifest=self.manifest,
            operation="observe",
            current_lease_fence={**attempted["lease_fence"], "lease_id": "lease-receipt", "generation": 2},
            now=self.now,
        )
        self.gateway().handle(
            self.signed_command(observe),
            transport=RecordingTransport(create=b"unused", retrieve=self.response_bytes(status="completed")),
        )
        completed = deepcopy(self.attempt)
        completed["lifecycle"] = {
            **runtime_lifecycle.empty_lifecycle(),
            "status": "succeeded",
            "provider_task_id": "resp_phase2_1",
            "terminal_status": "succeeded",
        }
        # Exact provider token usage is retained, but dollar cost is not supplied
        # by Responses. Successful completion attribution remains fail-closed.
        self.assert_gateway_error(lambda: self.gateway().attest_receipt(
            attempt=completed,
            provider_task_id="resp_phase2_1",
            receipt_payload_hash="c" * 64,
        ))
        wrong_identity = deepcopy(completed)
        wrong_identity["project_id"] = "other-project"
        self.assert_gateway_error(lambda: self.gateway().attest_receipt(
            attempt=wrong_identity,
            provider_task_id="resp_phase2_1",
            receipt_payload_hash="c" * 64,
        ))
        self.assertNotEqual(self.request_public.read_bytes(), self.gateway_public.read_bytes())

    def test_raw_artifact_tamper_is_rejected_by_existing_verifier(self) -> None:
        envelope = self.gateway().handle(
            self.signed_command(),
            transport=RecordingTransport(create=self.response_bytes()),
        )
        artifact = self.artifacts / envelope["claims"]["raw_artifact_path"]
        artifact.write_bytes(artifact.read_bytes() + b" ")
        self.assert_gateway_error(lambda: runtime_gateway.verify_result(
            envelope,
            request=self.launch_request,
            keyring_path=self.gateway_keyring,
            artifact_root=self.artifacts,
            now=self.now,
        ))

    def test_unmarked_transport_is_rejected_before_state_or_effect(self) -> None:
        raw = self.response_bytes()

        class UnsafeTransport:
            def __init__(self) -> None:
                self.calls = 0

            def create(self, _body: bytes) -> bytes:
                self.calls += 1
                return raw

        transport = UnsafeTransport()
        self.assert_gateway_error(lambda: self.gateway().handle(self.signed_command(), transport=transport))
        self.assertEqual(transport.calls, 0)
        self.assertFalse(self.state_path.exists())

    def test_secret_tamper_duplicate_key_rotation_and_skew_fail_closed(self) -> None:
        cases: list[tuple[str, Callable[[], object]]] = [
            ("secret in command", lambda: self.gateway().handle(self.signed_command(changes={"provider_secret": "provider-secret"}), transport=RecordingTransport(create=self.response_bytes()))),
            ("expired command", lambda: self.gateway().handle(self.signed_command(changes={"expires_at": (self.now - timedelta(seconds=1)).isoformat()}), transport=RecordingTransport(create=self.response_bytes()))),
            ("future command", lambda: self.gateway().handle(self.signed_command(changes={"issued_at": (self.now + timedelta(minutes=1)).isoformat()}), transport=RecordingTransport(create=self.response_bytes()))),
        ]
        for name, callback in cases:
            with self.subTest(name=name):
                self.assert_gateway_error(callback)
        self.write_keyrings(request_status="retired")
        self.assert_gateway_error(lambda: self.gateway().handle(
            self.signed_command(),
            transport=RecordingTransport(create=self.response_bytes()),
        ))
        self.write_keyrings(gateway_status="retired")
        self.assert_gateway_error(lambda: self.gateway().handle(
            self.signed_command(),
            transport=RecordingTransport(create=self.response_bytes()),
        ))

    def test_transport_secret_error_is_sanitized_from_state_and_signed_result(self) -> None:
        secret = "sk-fixture-must-never-escape"
        result = self.gateway().handle(
            self.signed_command(),
            transport=RecordingTransport(create=ConnectionError(f"Authorization Bearer {secret}")),
        )
        retained = canonical_json(result) + self.state_path.read_text(encoding="utf-8")
        retained += "".join(path.read_text(encoding="utf-8") for path in self.artifacts.glob("*.json"))
        self.assertNotIn(secret, retained)
        self.assertNotIn("Authorization", retained)


if __name__ == "__main__":
    unittest.main()
