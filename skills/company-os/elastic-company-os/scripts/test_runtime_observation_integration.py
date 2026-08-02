#!/usr/bin/env python3

from __future__ import annotations

import base64
import json
import os
import subprocess
import unittest
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import test_company_os_controller as controller_test

controller = controller_test.controller


class RuntimeObservationIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = controller_test.ControllerTests(methodName="runTest")
        self.fixture.setUp()
        self.project = self.fixture.project
        self.now = datetime.now(timezone.utc)
        self.gateway_private = self.project / "gateway-private.pem"
        self.gateway_public = self.project / "gateway-public.pem"
        subprocess.run(
            [
                "openssl", "genpkey", "-algorithm", "RSA",
                "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(self.gateway_private),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(self.gateway_private), "-pubout", "-out", str(self.gateway_public)],
            check=True,
            capture_output=True,
        )
        self.keyring = self.project / "gateway-keyring.json"
        self.write_keyring()
        self.previous_keyring = os.environ.get(controller.OBSERVATION_GATEWAY_KEYRING_ENV)
        os.environ[controller.OBSERVATION_GATEWAY_KEYRING_ENV] = str(self.keyring)

        cycle_id = self.fixture.admission_fixture()
        self.attempt_args = self.fixture.admission_args(cycle_id)
        self.assertEqual(controller.admit_runtime_attempt(self.attempt_args), 0)
        self.enable_inbox()

    def tearDown(self) -> None:
        if self.previous_keyring is None:
            os.environ.pop(controller.OBSERVATION_GATEWAY_KEYRING_ENV, None)
        else:
            os.environ[controller.OBSERVATION_GATEWAY_KEYRING_ENV] = self.previous_keyring
        self.fixture.tearDown()

    def write_keyring(self, *, status: str = "active", include_key: bool = True) -> None:
        keys = []
        if include_key:
            keys.append(
                {
                    "key_id": "gateway-test-1",
                    "algorithm": "rsa-sha256",
                    "public_key_path": str(self.gateway_public),
                    "status": status,
                    "not_before": (self.now - timedelta(days=1)).isoformat(),
                    "not_after": (self.now + timedelta(days=1)).isoformat(),
                }
            )
        self.keyring.write_text(
            json.dumps({"schema": "company-os.runtime-gateway-keyring.v1", "keys": keys}, indent=2) + "\n",
            encoding="utf-8",
        )

    def enable_inbox(self) -> None:
        state = controller.load_json(self.project / ".company-os" / "control.json")
        inbox = state["runtime_adapter"]["observation_inboxes"][self.attempt_args.attempt_id]
        inbox.update({"enabled": True, "status": "enabled"})
        self.fixture.write_state(state)

    def sign(self, claims: dict[str, object], private_key: Path | None = None) -> str:
        payload = self.project / f"claims-{uuid.uuid4().hex}.json"
        signature = self.project / f"claims-{uuid.uuid4().hex}.sig"
        observation = controller.runtime_observation_module()
        payload.write_text(observation.canonical_json(claims), encoding="utf-8")
        subprocess.run(
            [
                "openssl", "dgst", "-sha256", "-sign",
                str(private_key or self.gateway_private), "-out", str(signature), str(payload),
            ],
            check=True,
            capture_output=True,
        )
        return base64.urlsafe_b64encode(signature.read_bytes()).decode().rstrip("=")

    def envelope(
        self,
        *,
        event_id: str = "event-1",
        sequence: int = 1,
        nonce: str | None = None,
        claim_changes: dict[str, object] | None = None,
        raw_changes: dict[str, object] | None = None,
        private_key: Path | None = None,
    ) -> Path:
        state = controller.load_json(self.project / ".company-os" / "control.json")
        attempt = state["runtime_adapter"]["attempts"][0]
        observation = controller.runtime_observation_module()
        raw = {
            "provider": attempt["provider"],
            "surface": attempt["surface"],
            "account": attempt["account"],
            "provider_task_id": "task-1",
            "provider_event_id": event_id,
            "event_type": "launch",
            "provider_sequence": sequence,
            "provider_timestamp": (self.now - timedelta(seconds=2)).isoformat(),
            "observed_model": attempt["requested_model"],
            "payload": {"provider_status": "created", "usage": None},
        }
        raw.update(raw_changes or {})
        raw_path = self.project / f"raw-{event_id}-{uuid.uuid4().hex}.json"
        raw_path.write_text(json.dumps(raw, sort_keys=True) + "\n", encoding="utf-8")
        claims: dict[str, object] = {
            "schema": observation.SCHEMA,
            "gateway_key_id": "gateway-test-1",
            "provider": raw["provider"],
            "surface": raw["surface"],
            "account": raw["account"],
            "provider_task_id": raw["provider_task_id"],
            "provider_event_id": raw["provider_event_id"],
            "event_type": raw["event_type"],
            "provider_sequence": raw["provider_sequence"],
            "provider_timestamp": raw["provider_timestamp"],
            "gateway_received_at": (self.now - timedelta(seconds=1)).isoformat(),
            "payload_sha256": observation.sha256_json(raw["payload"]),
            "raw_artifact_path": raw_path.relative_to(self.project).as_posix(),
            "raw_artifact_sha256": observation.sha256_bytes(raw_path.read_bytes()),
            "project_id": state["instance"]["project_id"],
            "program_version": attempt["program_version"],
            "work_id": attempt["work_id"],
            "cycle_id": attempt["cycle_id"],
            "attempt_id": attempt["attempt_id"],
            "parent_runtime_id": attempt["parent_runtime_id"],
            "role": attempt["role"],
            "requested_model": attempt["requested_model"],
            "observed_model": raw["observed_model"],
            "fabric_manifest_digest": attempt["fabric_manifest_digest"],
            "phase2_contract_digest": attempt["phase2_contract_digest"],
            "nonce": nonce or uuid.uuid4().hex,
            "issued_at": self.now.isoformat(),
            "expires_at": (self.now + timedelta(minutes=4)).isoformat(),
        }
        claims.update(claim_changes or {})
        envelope_path = self.project / f"envelope-{event_id}-{uuid.uuid4().hex}.json"
        envelope_path.write_text(
            json.dumps({"claims": claims, "signature": self.sign(claims, private_key)}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return envelope_path

    def ingest(self, envelope: Path) -> int:
        return controller.ingest_runtime_observation(
            type(
                "Args",
                (),
                {
                    "project": str(self.project),
                    "attempt_id": self.attempt_args.attempt_id,
                    "envelope": envelope.name,
                },
            )()
        )

    def state_and_events(self) -> tuple[bytes, bytes]:
        return (
            (self.project / ".company-os" / "control.json").read_bytes(),
            (self.project / ".company-os" / "events.jsonl").read_bytes(),
        )

    def assert_atomic_rejection(self, envelope: Path) -> None:
        before = self.state_and_events()
        self.assertEqual(self.ingest(envelope), 2)
        self.assertEqual(before, self.state_and_events())

    def test_verified_observation_changes_only_inbox_and_audit_event_and_retry_is_exact_noop(self) -> None:
        envelope = self.envelope()
        before = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(self.ingest(envelope), 0)
        after = controller.load_json(self.project / ".company-os" / "control.json")
        for field in ("instance", "strategy", "phase", "controller", "portfolio", "evidence", "quality", "execution_fabric", "feedback"):
            self.assertEqual(before[field], after[field], field)
        self.assertEqual(before["runtime_adapter"]["attempts"], after["runtime_adapter"]["attempts"])
        inbox = after["runtime_adapter"]["observation_inboxes"][self.attempt_args.attempt_id]
        self.assertEqual(len(inbox["trusted_observations"]), 1)
        retry_bytes = self.state_and_events()
        self.assertEqual(self.ingest(envelope), 0)
        self.assertEqual(retry_bytes, self.state_and_events())

    def test_transactional_store_projects_one_inbox_message_and_retry_adds_no_revision(self) -> None:
        state = controller.load_json(self.project / ".company-os" / "control.json")
        controller.control_store_module().initialize(
            self.project,
            state,
            {
                "at": controller.utc_now(),
                "type": "test_control_store_initialized",
                "project_id": state["instance"]["project_id"],
                "program_version": state["strategy"]["program_version"],
            },
        )
        store = controller.control_store_module()
        before_revision = store.audit(self.project)["revision"]
        envelope = self.envelope(event_id="transactional-event")
        self.assertEqual(self.ingest(envelope), 0)
        first_report = store.audit(self.project)
        self.assertEqual(first_report["revision"], before_revision + 1)
        connection = store.connect(self.project)
        try:
            count = connection.execute("SELECT COUNT(*) FROM inbox_messages").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 1)
        self.assertEqual(self.ingest(envelope), 0)
        self.assertEqual(store.audit(self.project)["revision"], first_report["revision"])

    def test_signature_identity_artifact_and_strict_json_rejections_are_atomic(self) -> None:
        other_private = self.project / "other-private.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(other_private)],
            check=True,
            capture_output=True,
        )
        self.assert_atomic_rejection(self.envelope(private_key=other_private))
        self.assert_atomic_rejection(self.envelope(claim_changes={"work_id": "other-work"}))
        tampered = self.envelope(event_id="tampered")
        value = json.loads(tampered.read_text(encoding="utf-8"))
        raw_path = self.project / value["claims"]["raw_artifact_path"]
        raw_path.write_text('{"tampered":true}\n', encoding="utf-8")
        self.assert_atomic_rejection(tampered)
        duplicate = self.project / "duplicate-envelope.json"
        duplicate.write_text('{"claims":{},"claims":{},"signature":"x"}\n', encoding="utf-8")
        self.assert_atomic_rejection(duplicate)

    def test_observation_time_cannot_predate_admission_or_stale_before_signing(self) -> None:
        state = controller.load_json(self.project / ".company-os" / "control.json")
        admitted_at = datetime.fromisoformat(state["runtime_adapter"]["attempts"][0]["admitted_at"])
        self.assert_atomic_rejection(
            self.envelope(
                event_id="before-admission",
                raw_changes={"provider_timestamp": (admitted_at - timedelta(minutes=5)).isoformat()},
            )
        )
        self.assert_atomic_rejection(
            self.envelope(
                event_id="stale-gateway-receipt",
                raw_changes={"provider_timestamp": (self.now - timedelta(minutes=11)).isoformat()},
                claim_changes={"gateway_received_at": (self.now - timedelta(minutes=10)).isoformat()},
            )
        )

    def test_host_observation_integration_covers_all_cancellation_pairs_and_preserves_distinct_outcomes(self) -> None:
        pairs = (
            ("acknowledged", "acknowledged", True, "cancel_acknowledged"),
            ("acknowledged", "not_acknowledged", False, "cancel_requested"),
            ("refused", "acknowledged", False, "cancel_requested"),
            ("refused", "not_acknowledged", True, "cancel_requested"),
            ("failed", "acknowledged", False, "cancel_requested"),
            ("failed", "not_acknowledged", True, "cancel_requested"),
        )
        for index, (hard_status, acknowledgement_status, legal, expected_status) in enumerate(pairs):
            with self.subTest(hard_status=hard_status, acknowledgement_status=acknowledgement_status):
                fixture = controller_test.ControllerTests(methodName="runTest")
                fixture.setUp()
                try:
                    attempt_id = fixture.prepare_native_cancellation(attempt_id=f"observation-pair-{index}")
                    before_state = controller.load_json(fixture.project / ".company-os" / "control.json")
                    before_bytes = (
                        (fixture.project / ".company-os" / "control.json").read_bytes(),
                        (fixture.project / ".company-os" / "events.jsonl").read_bytes(),
                    )
                    observation = {
                        "source": "host_observation",
                        "tool": "observation-hard-cancel-return",
                        "task_id": f"{attempt_id}-task",
                        "thread_id": f"{attempt_id}-thread",
                        "host_id": f"{attempt_id}-host",
                        "hard_status": hard_status,
                        "acknowledgement_status": acknowledgement_status,
                    }
                    result = controller.record_native_task_observation(
                        fixture.native_observation_args(attempt_id, "hard_cancellation_observed", observation)
                    )
                    if not legal:
                        self.assertEqual(result, 2)
                        self.assertEqual(before_state, controller.load_json(fixture.project / ".company-os" / "control.json"))
                        self.assertEqual(
                            before_bytes,
                            (
                                (fixture.project / ".company-os" / "control.json").read_bytes(),
                                (fixture.project / ".company-os" / "events.jsonl").read_bytes(),
                            ),
                        )
                    else:
                        self.assertEqual(result, 0)
                        native = controller.load_json(fixture.project / ".company-os" / "control.json")["runtime_adapter"]["attempts"][0]["native_task_runtime"]
                        self.assertEqual(native["status"], expected_status)
                        self.assertEqual(
                            (native["cancellation"]["hard_cancellation_status"], native["cancellation"]["acknowledgement_status"]),
                            (hard_status, acknowledgement_status),
                        )
                        self.assertEqual(controller.native_task_runtime_module().audit_state(native), [])
                        if (hard_status, acknowledgement_status) == ("acknowledged", "acknowledged"):
                            self.assertEqual(native["status"], "cancel_acknowledged")
                        else:
                            self.assertNotEqual(native["status"], "cancel_acknowledged")
                finally:
                    fixture.tearDown()

    def test_nonce_event_sequence_and_provider_task_conflicts_survive_reload(self) -> None:
        first = self.envelope(sequence=2)
        first_value = json.loads(first.read_text(encoding="utf-8"))
        self.assertEqual(self.ingest(first), 0)
        self.assert_atomic_rejection(
            self.envelope(event_id="nonce-replay", sequence=3, nonce=first_value["claims"]["nonce"])
        )
        self.assert_atomic_rejection(self.envelope(event_id="stale", sequence=1))
        self.assert_atomic_rejection(
            self.envelope(event_id="other-task", sequence=3, raw_changes={"provider_task_id": "task-2"})
        )

    def test_retired_key_preserves_history_but_cannot_sign_forward(self) -> None:
        self.assertEqual(self.ingest(self.envelope(sequence=1)), 0)
        self.write_keyring(status="retired")
        report = controller.validate_state(
            controller.load_json(self.project / ".company-os" / "control.json"),
            expected_project=self.project,
        )
        self.assertFalse(any("runtime observation inbox" in error for error in report["errors"]), report["errors"])
        self.assert_atomic_rejection(self.envelope(event_id="after-retirement", sequence=2))

    def test_missing_historical_key_or_artifact_blocks_forward_ingestion(self) -> None:
        first = self.envelope(sequence=1)
        self.assertEqual(self.ingest(first), 0)
        retained = controller.load_json(self.project / ".company-os" / "control.json")
        retained_claims = retained["runtime_adapter"]["observation_inboxes"][self.attempt_args.attempt_id]["trusted_observations"][0]["claims"]
        artifact = self.project / retained_claims["raw_artifact_path"]
        artifact.unlink()
        self.assert_atomic_rejection(self.envelope(event_id="after-artifact-removal", sequence=2))
        # Restore only the artifact, then remove the historical verification key.
        first_raw = json.loads(first.read_text(encoding="utf-8"))["claims"]
        artifact.write_text(
            json.dumps(
                {
                    "provider": first_raw["provider"],
                    "surface": first_raw["surface"],
                    "account": first_raw["account"],
                    "provider_task_id": first_raw["provider_task_id"],
                    "provider_event_id": first_raw["provider_event_id"],
                    "event_type": first_raw["event_type"],
                    "provider_sequence": first_raw["provider_sequence"],
                    "provider_timestamp": first_raw["provider_timestamp"],
                    "observed_model": first_raw["observed_model"],
                    "payload": {"provider_status": "created", "usage": None},
                },
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(controller.runtime_observation_module().sha256_bytes(artifact.read_bytes()), first_raw["raw_artifact_sha256"])
        self.write_keyring(include_key=False)
        self.assert_atomic_rejection(self.envelope(event_id="after-key-removal", sequence=2))

    def test_inbox_cannot_be_enabled_under_disabled_runtime(self) -> None:
        state = controller.load_json(self.project / ".company-os" / "control.json")
        state["runtime_adapter"].update({"enabled": False, "status": "disabled"})
        report = controller.validate_state(state, expected_project=self.project)
        self.assertIn(
            "runtime observation inbox cannot be enabled while the runtime adapter is disabled",
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
