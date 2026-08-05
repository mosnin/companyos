#!/usr/bin/env python3

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
import unittest
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import gate2_observation_gateway_contract as gateway


class ObservationGatewayContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        self.now = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
        self.gateway_private, self.gateway_public = self.make_keypair("gateway")
        self.decision_private, self.decision_public = self.make_keypair("decision")
        self.keyring = self.root / "gateway-keyring.json"
        self.write_keyring()
        self.expected = {
            "status": "admitted",
            "project_id": "company-os-self-hosting",
            "program_version": 3,
            "work_id": "gate-2",
            "cycle_id": "cycle-gate-2",
            "attempt_id": "manager-attempt-1",
            "parent_runtime_id": "master",
            "role": "manager",
            "requested_model": "gpt-5.6-sol",
            "provider": "codex",
            "surface": "desktop",
            "account": "local-test-account",
            "provider_task_id": None,
            "fabric_manifest_digest": "a" * 64,
            "phase2_contract_digest": "b83f727e472c95911a60757efb0769a0c39acf11f0c8a7051e1056e34b8b8348",
        }

    def tearDown(self) -> None:
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

    def write_keyring(
        self,
        *,
        status: str = "active",
        key_id: str = "gateway-test-1",
        public_key: Path | None = None,
        not_before: datetime | None = None,
        not_after: datetime | None = None,
    ) -> None:
        self.keyring.write_text(
            json.dumps(
                {
                    "schema": gateway.KEYRING_SCHEMA,
                    "keys": [
                        {
                            "key_id": key_id,
                            "algorithm": "rsa-sha256",
                            "public_key_path": str(public_key or self.gateway_public),
                            "status": status,
                            "not_before": (not_before or self.now - timedelta(days=1)).isoformat(),
                            "not_after": (not_after or self.now + timedelta(days=1)).isoformat(),
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def sign(self, claims: dict[str, object], private_key: Path | None = None) -> str:
        payload = self.root / f"claims-{uuid.uuid4().hex}.json"
        signature = self.root / f"claims-{uuid.uuid4().hex}.sig"
        payload.write_text(gateway.canonical_json(claims), encoding="utf-8")
        subprocess.run(
            [
                "openssl", "dgst", "-sha256", "-sign",
                str(private_key or self.gateway_private),
                "-out", str(signature), str(payload),
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
        observed_model: str | None = "gpt-5.6-sol",
        event_type: str = "launch",
        raw_name: str | None = None,
        claim_changes: dict[str, object] | None = None,
        raw_changes: dict[str, object] | None = None,
        private_key: Path | None = None,
    ) -> dict[str, object]:
        raw = {
            "provider": "codex",
            "surface": "desktop",
            "account": "local-test-account",
            "provider_task_id": "task-1",
            "provider_event_id": event_id,
            "event_type": event_type,
            "provider_sequence": sequence,
            "provider_timestamp": (self.now - timedelta(seconds=2)).isoformat(),
            "observed_model": observed_model,
            "payload": {"provider_status": "created", "usage": None},
        }
        raw.update(raw_changes or {})
        path = self.artifacts / (raw_name or f"{event_id}-{uuid.uuid4().hex}.json")
        path.write_text(json.dumps(raw, sort_keys=True) + "\n", encoding="utf-8")
        claims: dict[str, object] = {
            "schema": gateway.SCHEMA,
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
            "payload_sha256": gateway.sha256_json(raw["payload"]),
            "raw_artifact_path": path.relative_to(self.artifacts).as_posix(),
            "raw_artifact_sha256": gateway.sha256_bytes(path.read_bytes()),
            "project_id": self.expected["project_id"],
            "program_version": self.expected["program_version"],
            "work_id": self.expected["work_id"],
            "cycle_id": self.expected["cycle_id"],
            "attempt_id": self.expected["attempt_id"],
            "parent_runtime_id": self.expected["parent_runtime_id"],
            "role": self.expected["role"],
            "requested_model": self.expected["requested_model"],
            "observed_model": raw["observed_model"],
            "fabric_manifest_digest": self.expected["fabric_manifest_digest"],
            "phase2_contract_digest": self.expected["phase2_contract_digest"],
            "nonce": nonce or uuid.uuid4().hex,
            "issued_at": self.now.isoformat(),
            "expires_at": (self.now + timedelta(minutes=4)).isoformat(),
        }
        claims.update(claim_changes or {})
        return {"claims": claims, "signature": self.sign(claims, private_key)}

    def ingest(
        self,
        state: dict[str, object],
        envelope: dict[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        return gateway.verify_and_ingest(
            state,
            envelope,
            expected_attempt=self.expected,
            keyring_path=self.keyring,
            artifact_root=self.artifacts,
            now=self.now,
        )

    def assert_rejected_atomically(
        self,
        state: dict[str, object],
        envelope: dict[str, object],
    ) -> None:
        before = gateway.canonical_json(state)
        with self.assertRaises(gateway.ObservationError):
            self.ingest(state, envelope)
        self.assertEqual(before, gateway.canonical_json(state))

    def test_feature_off_valid_observation_and_exact_retry(self) -> None:
        envelope = self.envelope()
        self.assert_rejected_atomically(gateway.empty_inbox(), envelope)
        state = gateway.empty_inbox(enabled=True)
        accepted, result = self.ingest(state, envelope)
        self.assertFalse(result["idempotent"])
        self.assertEqual(state["trusted_observations"], [])
        self.assertEqual(len(accepted["trusted_observations"]), 1)
        self.assertEqual(accepted["trusted_observations"][0]["trust"], "gateway_verified")
        retry, retry_result = self.ingest(accepted, envelope)
        self.assertTrue(retry_result["idempotent"])
        self.assertEqual(gateway.canonical_json(accepted), gateway.canonical_json(retry))

    def test_unknown_model_stays_unknown(self) -> None:
        state, _ = self.ingest(gateway.empty_inbox(enabled=True), self.envelope(observed_model=None))
        self.assertIsNone(state["trusted_observations"][0]["claims"]["observed_model"])
        self.assertEqual(
            state["trusted_observations"][0]["claims"]["requested_model"],
            "gpt-5.6-sol",
        )

    def test_key_and_signature_failures_are_atomic(self) -> None:
        state = gateway.empty_inbox(enabled=True)
        self.assert_rejected_atomically(
            state,
            self.envelope(private_key=self.decision_private),
        )
        unknown = self.envelope(claim_changes={"gateway_key_id": "unknown-key"})
        self.assert_rejected_atomically(state, unknown)
        malformed = self.envelope()
        malformed["signature"] = "not-base64***"
        self.assert_rejected_atomically(state, malformed)
        self.write_keyring(status="revoked")
        self.assert_rejected_atomically(state, self.envelope())
        self.write_keyring(not_after=self.now - timedelta(seconds=1))
        self.assert_rejected_atomically(state, self.envelope())

    def test_identity_and_time_substitutions_are_atomic(self) -> None:
        state = gateway.empty_inbox(enabled=True)
        for field, value in (
            ("project_id", "other-project"),
            ("program_version", 4),
            ("work_id", "other-work"),
            ("cycle_id", "other-cycle"),
            ("attempt_id", "other-attempt"),
            ("parent_runtime_id", "other-parent"),
            ("role", "worker"),
            ("requested_model", "gpt-5.6-luna"),
            ("provider", "other-provider"),
            ("surface", "other-surface"),
            ("account", "other-account"),
            ("fabric_manifest_digest", "c" * 64),
            ("phase2_contract_digest", "d" * 64),
        ):
            with self.subTest(field=field):
                self.assert_rejected_atomically(
                    state,
                    self.envelope(claim_changes={field: value}),
                )
        self.assert_rejected_atomically(
            state,
            self.envelope(claim_changes={"expires_at": (self.now - timedelta(seconds=1)).isoformat()}),
        )
        self.assert_rejected_atomically(
            state,
            self.envelope(claim_changes={"issued_at": (self.now + timedelta(minutes=1)).isoformat()}),
        )
        self.assert_rejected_atomically(
            state,
            self.envelope(claim_changes={"expires_at": (self.now + timedelta(minutes=10)).isoformat()}),
        )

    def test_raw_artifact_and_payload_integrity_failures_are_atomic(self) -> None:
        state = gateway.empty_inbox(enabled=True)
        changed_after_signing = self.envelope()
        artifact = self.artifacts / changed_after_signing["claims"]["raw_artifact_path"]
        artifact.write_text('{"tampered":true}\n', encoding="utf-8")
        self.assert_rejected_atomically(state, changed_after_signing)
        self.assert_rejected_atomically(
            state,
            self.envelope(claim_changes={"payload_sha256": "0" * 64}),
        )
        outside = self.root / "outside.json"
        outside.write_text("{}\n", encoding="utf-8")
        traversal = self.envelope(
            claim_changes={
                "raw_artifact_path": "../outside.json",
                "raw_artifact_sha256": gateway.sha256_bytes(outside.read_bytes()),
            }
        )
        self.assert_rejected_atomically(state, traversal)
        duplicate = self.artifacts / "duplicate.json"
        duplicate.write_text(
            '{"provider":"codex","provider":"other","surface":"desktop",'
            '"account":"local-test-account","provider_task_id":"task-1",'
            '"provider_event_id":"event-duplicate","event_type":"launch",'
            '"provider_sequence":1,"provider_timestamp":"2026-07-31T11:59:58+00:00",'
            '"observed_model":"gpt-5.6-sol","payload":{}}\n',
            encoding="utf-8",
        )
        duplicate_envelope = self.envelope(
            event_id="event-duplicate",
            claim_changes={
                "raw_artifact_path": duplicate.name,
                "raw_artifact_sha256": gateway.sha256_bytes(duplicate.read_bytes()),
            },
        )
        self.assert_rejected_atomically(state, duplicate_envelope)
        invalid_utf8 = self.artifacts / "invalid-utf8.json"
        invalid_utf8.write_bytes(b"\xff\xfe")
        self.assert_rejected_atomically(
            state,
            self.envelope(
                event_id="event-invalid-utf8",
                claim_changes={
                    "raw_artifact_path": invalid_utf8.name,
                    "raw_artifact_sha256": gateway.sha256_bytes(invalid_utf8.read_bytes()),
                },
            ),
        )
        oversized = self.artifacts / "oversized.json"
        oversized.write_bytes(b" " * (gateway.MAX_ARTIFACT_BYTES + 1))
        self.assert_rejected_atomically(
            state,
            self.envelope(
                event_id="event-oversized",
                claim_changes={
                    "raw_artifact_path": oversized.name,
                    "raw_artifact_sha256": gateway.sha256_bytes(oversized.read_bytes()),
                },
            ),
        )

    def test_nonce_event_conflict_and_sequence_replay_are_atomic(self) -> None:
        initial_envelope = self.envelope(sequence=2)
        state, _ = self.ingest(gateway.empty_inbox(enabled=True), initial_envelope)
        nonce = initial_envelope["claims"]["nonce"]
        self.assert_rejected_atomically(
            state,
            self.envelope(event_id="event-2", sequence=3, nonce=nonce),
        )
        self.assert_rejected_atomically(
            state,
            self.envelope(event_id="event-1", sequence=2, event_type="running"),
        )
        self.assert_rejected_atomically(
            state,
            self.envelope(event_id="event-stale", sequence=1),
        )
        boolean_sequence = self.envelope()
        boolean_sequence["claims"]["provider_sequence"] = True
        boolean_sequence["signature"] = self.sign(boolean_sequence["claims"])
        self.assert_rejected_atomically(state, boolean_sequence)

    def test_missing_fields_and_corrupt_retained_state_fail_atomically(self) -> None:
        state = gateway.empty_inbox(enabled=True)
        missing = self.envelope()
        del missing["claims"]["provider_timestamp"]
        missing["signature"] = self.sign(missing["claims"])
        self.assert_rejected_atomically(state, missing)
        corrupt = deepcopy(state)
        corrupt["trusted_observations"] = ["not-an-observation"]
        self.assert_rejected_atomically(corrupt, self.envelope())

    def test_new_observation_cannot_build_on_corrupted_retained_evidence(self) -> None:
        accepted, _ = self.ingest(
            gateway.empty_inbox(enabled=True),
            self.envelope(sequence=1),
        )
        mutations = (
            lambda item, state: item["claims"].update({"requested_model": "gpt-5.6-luna"}),
            lambda item, state: item.update({"signature": "corrupted"}),
            lambda item, state: item.update({"event_key": "0" * 64}),
            lambda item, state: state.update({"consumed_nonces": []}),
            lambda item, state: state.update({"bound_provider_task_id": "other-task"}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation.__code__.co_firstlineno):
                corrupt = deepcopy(accepted)
                mutation(corrupt["trusted_observations"][0], corrupt)
                self.assert_rejected_atomically(
                    corrupt,
                    self.envelope(event_id=f"next-{uuid.uuid4().hex}", sequence=2),
                )

    def test_one_admission_cannot_switch_provider_tasks(self) -> None:
        accepted, _ = self.ingest(
            gateway.empty_inbox(enabled=True),
            self.envelope(sequence=1),
        )
        self.assertEqual(accepted["bound_provider_task_id"], "task-1")
        self.assert_rejected_atomically(
            accepted,
            self.envelope(
                event_id="event-from-another-task",
                sequence=1,
                raw_changes={"provider_task_id": "task-2"},
            ),
        )

    def test_retired_key_audits_history_but_cannot_sign_new_observations(self) -> None:
        accepted, _ = self.ingest(
            gateway.empty_inbox(enabled=True),
            self.envelope(sequence=1),
        )
        self.write_keyring(status="retired")
        self.assert_rejected_atomically(
            accepted,
            self.envelope(event_id="event-after-retirement", sequence=2),
        )


if __name__ == "__main__":
    unittest.main()
