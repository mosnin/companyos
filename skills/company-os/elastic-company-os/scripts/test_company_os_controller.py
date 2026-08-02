#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import base64
import io
import json
import os
import subprocess
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import redirect_stdout

MODULE_PATH = Path(__file__).with_name("company_os_controller.py")
SPEC = importlib.util.spec_from_file_location("company_os_controller", MODULE_PATH)
assert SPEC and SPEC.loader
controller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(controller)


def namespace(**values: object) -> object:
    if "lease_id" in values and "owner" not in values:
        values["owner"] = "master-sol" if values["lease_id"] == "fabric-lease" else "scheduler"
    if "manager_id" in values and "lease_id" not in values:
        values.update({"lease_id": "fabric-lease", "generation": 1, "owner": "master-sol"})
    return type("Args", (), values)()


class ControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name).resolve()
        self.private_key = self.project / "test-issuer-private.pem"
        self.public_key = self.project / "test-issuer-public.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(self.private_key)], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(self.private_key), "-pubout", "-out", str(self.public_key)], check=True, capture_output=True)
        self.previous_actor_public_key = os.environ.get(controller.ACTOR_PUBLIC_KEY_ENV)
        os.environ[controller.ACTOR_PUBLIC_KEY_ENV] = str(self.public_key)
        self.previous_launcher_attestation = controller.protected_launcher_attestation
        controller.protected_launcher_attestation = lambda: (True, "")
        self.grant_cache: dict[tuple[str, ...], str] = {}

    def tearDown(self) -> None:
        controller.protected_launcher_attestation = self.previous_launcher_attestation
        if self.previous_actor_public_key is None:
            os.environ.pop(controller.ACTOR_PUBLIC_KEY_ENV, None)
        else:
            os.environ[controller.ACTOR_PUBLIC_KEY_ENV] = self.previous_actor_public_key
        self.temporary.cleanup()

    def grant(
        self,
        actor: str,
        action: str,
        *,
        resource: str,
        work_id: str,
        cycle_id: str,
        dimension: str,
        decision: str,
        payload_hash: str,
    ) -> str:
        cache_key = (actor, action, resource, work_id, cycle_id, dimension, decision, payload_hash)
        if cache_key in self.grant_cache:
            return self.grant_cache[cache_key]
        payload = {
            "actor": actor,
            "action": action,
            "resource": resource,
            "project_id": "test-123",
            "program_version": 1,
            "work_id": work_id,
            "cycle_id": cycle_id,
            "dimension": dimension,
            "decision": decision,
            "payload_hash": payload_hash,
            "nonce": controller.uuid.uuid4().hex,
            "expiry": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        }
        encoded = base64.urlsafe_b64encode(controller.canonical_json(payload).encode()).decode().rstrip("=")
        payload_file = self.project / f"grant-{payload['nonce']}.txt"
        signature_file = self.project / f"grant-{payload['nonce']}.sig"
        payload_file.write_text(encoded, encoding="ascii")
        subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(self.private_key), "-out", str(signature_file), str(payload_file)], check=True, capture_output=True)
        signature = base64.urlsafe_b64encode(signature_file.read_bytes()).decode().rstrip("=")
        token = f"{encoded}.{signature}"
        self.grant_cache[cache_key] = token
        return token

    def rewrite_grant(self, token: str, **changes: object) -> str:
        encoded, _ = token.split(".", 1)
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        payload.update(changes)
        rewritten = base64.urlsafe_b64encode(
            controller.canonical_json(payload).encode()
        ).decode().rstrip("=")
        payload_file = self.project / f"grant-rewrite-{controller.uuid.uuid4().hex}.txt"
        signature_file = self.project / f"grant-rewrite-{controller.uuid.uuid4().hex}.sig"
        payload_file.write_text(rewritten, encoding="ascii")
        subprocess.run(
            [
                "openssl", "dgst", "-sha256", "-sign", str(self.private_key),
                "-out", str(signature_file), str(payload_file),
            ],
            check=True,
            capture_output=True,
        )
        signature = base64.urlsafe_b64encode(signature_file.read_bytes()).decode().rstrip("=")
        return f"{rewritten}.{signature}"

    def evidence(self, bucket: str, *, quality_dimensions: list[str] | None = None) -> dict:
        artifact = self.project / f"{bucket}.md"
        artifact.write_text(f"# {bucket}\nverified evidence\n", encoding="utf-8")
        return {
            "id": f"{bucket}-1",
            "outcome": bucket,
            "project_id": "test-123",
            "program_version": 1,
            "artifact_path": artifact.name,
            "artifact_sha256": controller.sha256_file(artifact),
            "observed_at": controller.utc_now(),
            "freshness_days": 30,
            "source": "test fixture",
            "decision_impact": f"The {bucket} evidence changes the governed decision.",
            "author": f"{bucket}-author",
            "reviewer": f"{bucket}-reviewer",
            "quality_dimensions": quality_dimensions or [],
        }

    def grant_record(self, state: dict, actor: str, token: str) -> dict:
        encoded = token.split(".", 1)[0]
        claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        state["controller"].setdefault("consumed_grant_nonces", []).append(claims["nonce"])
        return {
            "actor": actor,
            "claims": claims,
            "token": token,
            "grant_digest": controller.hashlib.sha256(token.encode()).hexdigest(),
        }

    def test_new_stored_grant_retains_public_verification_material(self) -> None:
        state = self.valid_state()
        payload_hash = controller.command_payload_hash("test-action", {"value": 1})
        token = self.grant(
            "reviewer", "test-action", resource="test:1", work_id="", cycle_id="",
            dimension="test", decision="accepted", payload_hash=payload_hash,
        )
        grant = controller.verify_actor_grant(
            state, token, "reviewer", "test-action", resource="test:1", work_id="",
            cycle_id="", dimension="test", decision="accepted", payload_hash=payload_hash,
        )
        self.assertIn("BEGIN PUBLIC KEY", grant["verification_key_pem"])
        previous = os.environ.pop(controller.ACTOR_PUBLIC_KEY_ENV)
        try:
            errors: list[str] = []
            status = controller.audit_stored_grant(
                state, grant, errors, "stored grant",
                {
                    "actor": "reviewer", "action": "test-action", "resource": "test:1",
                    "work_id": "", "cycle_id": "", "dimension": "test",
                    "decision": "accepted", "payload_hash": payload_hash,
                },
            )
            self.assertEqual(status, "cryptographic")
            self.assertEqual(errors, [])
            grant["verification_key_pem"] += "tamper"
            tampered_errors: list[str] = []
            self.assertEqual(
                controller.audit_stored_grant(state, grant, tampered_errors, "stored grant"),
                "invalid",
            )
            self.assertTrue(tampered_errors)
        finally:
            os.environ[controller.ACTOR_PUBLIC_KEY_ENV] = previous

    def finish_grant(
        self,
        *,
        cycle_id: str,
        lease_id: str,
        generation: int,
        disposition: str,
        decision: str,
        visible: str,
        cost: float = 1.0,
        latency: float = 5.0,
        tokens: int = 100,
        commit: str | None = None,
        ref: str | None = None,
    ) -> str:
        values = {
            "cycle_id": cycle_id, "lease_id": lease_id, "generation": generation,
            "actual_outcome": "capability", "evidence_ids": ["delivery-1"],
            "cost_usd": cost, "latency_minutes": latency, "token_usage": tokens,
            "user_visible_movement": visible, "work_disposition": disposition,
            "reviewer_decision": decision, "reviewer": "cycle-reviewer", "commit": commit, "ref": ref,
        }
        state = controller.load_json(self.project / ".company-os" / "control.json")
        return self.grant(
            "cycle-reviewer", "finish-cycle", resource=f"cycle:{cycle_id}", work_id="cap-1",
            cycle_id=cycle_id, dimension="completion", decision=f"{decision}:{disposition}",
            payload_hash=controller.command_payload_hash("finish-cycle", controller.finish_command_payload(state, values)),
        )

    def valid_state(self) -> dict:
        state = deepcopy(controller.load_json(controller.template_path()))
        state["instance"].update(
            {
                "project_id": "test-123",
                "name": "Test",
                "project_root": str(self.project),
                "project_type": "software",
                "status": "active",
                "created_at": controller.utc_now(),
            }
        )
        state["strategy"].update(
            {
                "north_star": "Create a category-defining product",
                "current_outcome": "Deliver the first integrated workspace",
                "success_metric": "Five users complete the end-to-end flow",
                "program_version": 1,
                "program_updated_at": controller.utc_now(),
            }
        )
        state["strategy"]["program_fingerprint"] = controller.strategy_fingerprint(state["strategy"])
        state["profile"]["departments"] = controller.DEPARTMENT_PRESETS["software"]
        state["profile"]["methods"] = ["discovery", "iterative_delivery", "stage_gates"]
        state["phase"] = "learning"
        state["evidence"] = {
            bucket: [
                self.evidence(
                    bucket,
                    quality_dimensions=list(controller.BASE_DIMENSIONS)
                    if bucket == "verification"
                    else [],
                )
            ]
            for bucket in controller.EVIDENCE_BUCKETS
        }
        state["portfolio"]["committed_outcomes"] = [
            {
                "id": "cap-1",
                "type": "capability",
                "title": "Integrated workspace",
                "user_visible_outcome": "A user completes one new workflow",
                "program_version": 1,
                "status": "active",
            }
        ]
        state["portfolio"]["active_work"] = [
            {
                "id": "cap-1",
                "type": "capability",
                "primary": True,
                "queued_primary": True,
                "title": "Integrated workspace",
                "user_visible_outcome": "A user completes one new workflow",
                "claimed_progress": "capability",
                "program_version": 1,
                "owner": "product-owner",
                "status": "ready",
                "outcome_id": "cap-1",
            }
        ]
        state["portfolio"]["active_work"][0]["queue_payload"] = controller.queue_command_payload(
            {
                "id": "cap-1",
                "type": "capability",
                "primary": "true",
                "title": "Integrated workspace",
                "user_visible_outcome": "A user completes one new workflow",
                "claimed_progress": "capability",
                "owner": "product-owner",
                "outcome_id": "cap-1",
                "unlocks": [],
            }
        )
        state["portfolio"]["active_work"][0]["work_fingerprint"] = controller.work_fingerprint(
            state["portfolio"]["active_work"][0]
        )
        checkpoint = controller.current_quality_checkpoint(state)[2]
        state["evidence"]["verification"][0].update(
            {"outcome_id": "cap-1", "work_id": "cap-1", "cycle_id": checkpoint, "rubric_version": "quality-v1"}
        )
        state["quality"]["dimensions"] = {}
        for name, critical in controller.BASE_DIMENSIONS.items():
            quality_values = {
                "dimension": name, "score": 9, "evidence_ids": ["verification-1"],
                "rubric_version": "quality-v1", "scored_by": "quality-scorer", "reviewed_by": "quality-reviewer",
                "outcome_id": "cap-1", "work_id": "cap-1", "cycle_id": checkpoint,
                "artifact_digest": controller.sha256_file(self.project / "verification.md"),
            }
            quality_payload_hash = controller.command_payload_hash(
                "score-quality", controller.quality_command_payload(quality_values)
            )
            scorer_token = self.grant(
                "quality-scorer", "score-quality", resource=f"quality:{name}", work_id="cap-1",
                cycle_id=checkpoint, dimension=name, decision="score:9", payload_hash=quality_payload_hash,
            )
            reviewer_token = self.grant(
                "quality-reviewer", "score-quality-review", resource=f"quality:{name}", work_id="cap-1",
                cycle_id=checkpoint, dimension=name, decision="review:9", payload_hash=quality_payload_hash,
            )
            state["quality"]["dimensions"][name] = {
                "critical": critical,
                "applicable": True,
                "score": 9,
                "evidence": ["verification-1"],
                "rubric_version": "quality-v1",
                "scored_by": "quality-scorer",
                "reviewed_by": "quality-reviewer",
                "scorer_grant": self.grant_record(state, "quality-scorer", scorer_token),
                "reviewer_grant": self.grant_record(state, "quality-reviewer", reviewer_token),
                "binding": {
                    "outcome_id": "cap-1",
                    "work_id": "cap-1",
                    "cycle_id": checkpoint,
                    "artifact_digest": controller.sha256_file(self.project / "verification.md"),
                    "rubric_version": "quality-v1",
                },
            }
        certifier_token = self.grant(
            "acceptance-reviewer", "certify", resource="certification", work_id="cap-1",
            cycle_id=checkpoint, dimension="learning", decision="accepted",
            payload_hash=controller.command_payload_hash(
                "certify", controller.certification_command_payload(state, "acceptance-reviewer")
            ),
        )
        certifier_grant = self.grant_record(state, "acceptance-reviewer", certifier_token)
        state["controller"]["validated"] = True
        state["controller"]["validation"] = {
            "program_version": 1,
            "reviewer": "acceptance-reviewer",
            "reviewed_at": controller.utc_now(),
            "decision": "accepted",
            "evidence_digest": controller.evidence_digest(state),
            "certifier_grant": certifier_grant,
        }
        return state

    def bind_delivery_evidence(self, cycle_id: str) -> None:
        state = controller.load_json(self.project / ".company-os" / "control.json")
        item = state["evidence"]["delivery"][0]
        item.update(
            {
                "outcome_id": "cap-1",
                "work_id": "cap-1",
                "cycle_id": cycle_id,
                "rubric_version": "quality-v1",
                "quality_dimensions": list(controller.BASE_DIMENSIONS),
            }
        )
        controller.atomic_write_json(self.project / ".company-os" / "control.json", state)

    def rebind_quality(self, cycle_id: str) -> None:
        state = controller.load_json(self.project / ".company-os" / "control.json")
        for name, item in state["quality"]["dimensions"].items():
            quality_values = {
                "dimension": name, "score": 9, "evidence_ids": ["delivery-1"],
                "rubric_version": "quality-v1", "scored_by": "quality-scorer", "reviewed_by": "quality-reviewer",
                "outcome_id": "cap-1", "work_id": "cap-1", "cycle_id": cycle_id,
                "artifact_digest": controller.sha256_file(self.project / "delivery.md"),
            }
            quality_payload_hash = controller.command_payload_hash(
                "score-quality", controller.quality_command_payload(quality_values)
            )
            scorer = self.grant(
                "quality-scorer", "score-quality", resource=f"quality:{name}", work_id="cap-1",
                cycle_id=cycle_id, dimension=name, decision="score:9", payload_hash=quality_payload_hash,
            )
            reviewer = self.grant(
                "quality-reviewer", "score-quality-review", resource=f"quality:{name}", work_id="cap-1",
                cycle_id=cycle_id, dimension=name, decision="review:9", payload_hash=quality_payload_hash,
            )
            item.update(
                {
                    "score": 9,
                    "evidence": ["delivery-1"],
                    "rubric_version": "quality-v1",
                    "scored_by": "quality-scorer",
                    "reviewed_by": "quality-reviewer",
                    "scorer_grant": self.grant_record(state, "quality-scorer", scorer),
                    "reviewer_grant": self.grant_record(state, "quality-reviewer", reviewer),
                    "binding": {
                        "outcome_id": "cap-1",
                        "work_id": "cap-1",
                        "cycle_id": cycle_id,
                        "artifact_digest": controller.sha256_file(self.project / "delivery.md"),
                        "rubric_version": "quality-v1",
                    },
                }
            )
        controller.atomic_write_json(self.project / ".company-os" / "control.json", state)

    def running_finish_state(
        self,
        *,
        cycle_id: str = "cycle-substitution",
        lease_id: str = "lease-substitution",
        generation: int = 1,
    ) -> dict:
        state = self.valid_state()
        state["controller"].update(
            {
                "lease_generation": generation,
                "lease": {
                    "lease_id": lease_id,
                    "owner": "scheduler",
                    "generation": generation,
                    "program_version": 1,
                    "acquired_at": controller.utc_now(),
                    "expires_at": (
                        datetime.now(timezone.utc) + timedelta(minutes=10)
                    ).isoformat(),
                },
                "schedule_enabled": True,
                "validation": None,
                "validated": False,
            }
        )
        state["portfolio"]["active_work"][0]["status"] = "running"
        state["feedback"]["cycles"] = [
            {
                "id": cycle_id,
                "program_version": 1,
                "work_id": "cap-1",
                "work_type": "capability",
                "status": "running",
                "started_at": controller.utc_now(),
                "intended_outcome": "Deliver one inspectable capability",
                "lease_id": lease_id,
                "lease_generation": generation,
            }
        ]
        state["evidence"]["delivery"][0].update(
            {
                "outcome_id": "cap-1",
                "work_id": "cap-1",
                "cycle_id": cycle_id,
                "rubric_version": "quality-v1",
                "quality_dimensions": list(controller.BASE_DIMENSIONS),
            }
        )
        return state

    def report(self, state: dict) -> dict:
        return controller.validate_state(state, expected_project=self.project)

    def fabric_manifest(self) -> dict:
        outcome = "A user completes one new workflow"
        north_star = "Create a category-defining product"
        return {
            "program_id": "test-123",
            "program_version": 1,
            "outcome": outcome,
            "acceptance": ["The integrated workflow passes its executable acceptance check"],
            "program_contract": {
                "north_star": north_star,
                "user_value": "Users complete valuable work faster",
                "rationale": "Use bounded Luna labor without weakening Sol acceptance",
                "architecture": "Sol master and managers supervise Luna workers",
                "roadmap": list(controller.FABRIC_PHASES),
                "dependencies": ["Local repository and test toolchain"],
                "non_goals": ["Production deployment"],
                "constraints": ["No external effects"],
            },
            "max_managers": 2,
            "max_workers_per_manager": 3,
            "max_total_workers": 6,
            "max_depth": 2,
            "max_worker_retries": 1,
            "max_manager_rework_rounds": 2,
            "luna_token_share_target": 0.75,
            "external_effects_allowed": False,
            "budget": {"time_minutes": 60, "token_limit": 10000, "cost_usd": 10.0, "max_concurrency": 6, "max_retries": 1},
            "managers": [
                {
                    "id": "manager-a",
                    "model": "gpt-5.6-sol",
                    "outcome": "Deliver the bounded user workflow",
                    "acceptance": ["Manager verifies the integrated artifact"],
                    "phase_ids": list(controller.FABRIC_PHASES),
                    "write_scope": ["src/workflow"],
                    "budget": {"time_minutes": 30, "token_limit": 5000, "cost_usd": 5.0, "max_concurrency": 3, "max_retries": 1},
                    "workers": [
                        {
                            "id": "worker-a1",
                            "model": "gpt-5.6-luna",
                            "task": "Implement the bounded workflow slice",
                            "acceptance": ["Focused test passes"],
                            "write_scope": ["src/workflow"],
                            "risk": "medium",
                            "budget": {"time_minutes": 15, "token_limit": 2500, "cost_usd": 2.5, "max_concurrency": 1, "max_retries": 1},
                            "outcome_context": {
                                "program_version": 1,
                                "north_star": north_star,
                                "user_value": "Users complete valuable work faster",
                                "program_outcome": outcome,
                                "manager_outcome": "Deliver the bounded user workflow",
                                "roadmap_position": "execution",
                                "dependencies": ["Local repository and test toolchain"],
                                "non_goals": ["Production deployment"],
                                "constraints": ["No external effects"],
                            },
                            "stop_condition": "Focused test passes or a blocker is reported",
                        }
                    ],
                }
            ],
        }

    def configure_fabric_fixture(self) -> dict:
        state = self.valid_state()
        work = state["portfolio"]["active_work"][0]
        work["execution_mode"] = "luna_fabric"
        work["queue_payload"] = controller.retained_queue_command_payload(work)
        work["work_fingerprint"] = controller.work_fingerprint(work)
        state["controller"]["validation"] = None
        state["controller"]["validated"] = False
        self.write_state(state)
        manifest_path = self.project / "fabric-manifest.json"
        manifest_path.write_text(json.dumps(self.fabric_manifest(), indent=2), encoding="utf-8")
        self.assertEqual(
            controller.configure_execution_fabric(
                namespace(
                    project=str(self.project),
                    work_id="cap-1",
                    manifest=manifest_path.name,
                )
            ),
            0,
        )
        return controller.load_json(self.project / ".company-os" / "control.json")

    def begin_fabric_fixture(self) -> str:
        state = self.configure_fabric_fixture()
        state["controller"]["lease_generation"] = 1
        state["controller"]["lease"] = {
            "lease_id": "fabric-lease",
            "owner": "master-sol",
            "generation": 1,
            "program_version": 1,
            "allowed_transitions": sorted(controller.LEASE_TRANSITIONS),
            "acquired_at": controller.utc_now(),
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=30)
            ).isoformat(),
        }
        self.write_state(state)
        self.assertEqual(
            controller.begin_cycle(
                namespace(
                    project=str(self.project),
                    lease_id="fabric-lease",
                    generation=1,
                    work_id="cap-1",
                    intended_outcome="Deliver the bounded user workflow",
                )
            ),
            0,
        )
        running = controller.load_json(self.project / ".company-os" / "control.json")
        cycle_id = running["execution_fabric"]["cycle_id"]
        running["evidence"]["delivery"][0].update(
            {
                "outcome_id": "cap-1",
                "work_id": "cap-1",
                "cycle_id": cycle_id,
                "rubric_version": "quality-v1",
            }
        )
        self.write_state(running)
        return cycle_id

    def write_fabric_report(self, phase: str, cycle_id: str) -> str:
        later_phase = phase in {"execution", "verification", "integration"}
        report = {
            "message_type": "manager_phase_report",
            "program_id": "test-123",
            "program_version": 1,
            "manager_id": "manager-a",
            "phase": phase,
            "cycle_id": cycle_id,
            "status": "ready_for_decision",
            "outcome_state": "on_track",
            "artifacts": [f"artifact:{phase}"],
            "evidence_ids": ["delivery-1"],
            "plan_variance": [],
            "dependencies": [],
            "risks": [],
            "usage": {
                "luna_tokens": 100,
                "terra_tokens": 0,
                "manager_sol_tokens": 15,
                "reviewer_sol_tokens": 5 if phase == "verification" else 0,
                "elapsed_minutes": 5,
            },
            "worker_metrics": {
                "accepted_first_pass": 1 if later_phase else 0,
                "reworked": 0,
                "failed": 0,
                "collisions": 0,
            },
            "requested_decision": "continue",
            "next_plan": ["Advance only after the master decision"],
        }
        if phase == "verification":
            report["independent_review"] = {
                "model": "gpt-5.6-sol",
                "reviewer": "independent-sol-reviewer",
                "decision": "accepted",
                "evidence": ["The bounded acceptance check passed"],
            }
        path = self.project / f"manager-a-{phase}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return path.name

    def test_valid_complete_instance_passes(self) -> None:
        report = self.report(self.valid_state())
        self.assertTrue(report["ok"], report["errors"])
        self.assertTrue(report["scheduler_ready"])
        self.assertTrue(report["quality_ready"])
        self.assertTrue(report["validation_valid"])

    def test_init_is_isolated_and_refuses_overwrite(self) -> None:
        args = namespace(
            project=str(self.project),
            name="Alpha",
            project_type="software",
            north_star="Build the future",
        )
        self.assertEqual(controller.init_instance(args), 0)
        state = json.loads((self.project / ".company-os" / "control.json").read_text())
        self.assertEqual(state["instance"]["project_root"], str(self.project))
        self.assertEqual(state["schema_version"], controller.SCHEMA_VERSION)
        self.assertEqual(controller.init_instance(args), 2)

    def test_state_event_transaction_recovers_after_one_target_replace(self) -> None:
        state = self.valid_state()
        self.write_state(state)
        candidate = deepcopy(state)
        candidate["instance"]["status"] = "paused"
        event = {
            "at": controller.utc_now(),
            "type": "transaction-recovery-test",
            "project_id": candidate["instance"]["project_id"],
            "program_version": candidate["strategy"]["program_version"],
        }
        marker = controller._stage_state_event_transaction(
            self.project,
            self.project / ".company-os" / "control.json",
            candidate,
            event,
        )
        transaction = controller.load_json(marker)
        os.replace(
            self.project / ".company-os" / transaction["state_temp"],
            self.project / ".company-os" / "control.json",
        )
        with controller.locked_state(self.project) as (_, recovered):
            self.assertEqual(recovered["instance"]["status"], "paused")
        self.assertFalse(marker.exists())
        events = (self.project / ".company-os" / "events.jsonl").read_text(encoding="utf-8")
        self.assertIn('\"type\": \"transaction-recovery-test\"', events)

    def test_luna_fabric_is_native_governed_company_os_state(self) -> None:
        configured = self.configure_fabric_fixture()
        self.assertEqual(configured["execution_fabric"]["status"], "ready")
        self.assertEqual(configured["execution_fabric"]["work_id"], "cap-1")
        self.assertEqual(
            set(configured["execution_fabric"]["managers"]),
            {"manager-a"},
        )
        report = self.report(configured)
        self.assertTrue(report["execution_fabric_ready"])
        self.assertFalse(report["scheduler_ready"])

    def test_luna_fabric_enforces_all_phase_barriers_and_completion(self) -> None:
        cycle_id = self.begin_fabric_fixture()
        for phase in controller.FABRIC_PHASES:
            report_path = self.write_fabric_report(phase, cycle_id)
            self.assertEqual(
                controller.record_fabric_phase(
                    namespace(
                        project=str(self.project),
                        manager_id="manager-a",
                        report=report_path,
                    )
                ),
                0,
            )
            state = controller.load_json(self.project / ".company-os" / "control.json")
            payload = controller.fabric_phase_decision_payload(
                state,
                "manager-a",
                phase,
                "continue",
            )
            master_grant = self.grant(
                "master-sol",
                "fabric-phase-decision",
                resource=f"fabric:manager-a:{phase}",
                work_id="cap-1",
                cycle_id=cycle_id,
                dimension="execution-fabric",
                decision="continue",
                payload_hash=controller.command_payload_hash(
                    "fabric-phase-decision",
                    payload,
                ),
            )
            self.assertEqual(
                controller.decide_fabric_phase(
                    namespace(
                        project=str(self.project),
                        manager_id="manager-a",
                        decision="continue",
                        decided_by="master-sol",
                        master_grant=master_grant,
                    )
                ),
                0,
            )
        accepted = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(accepted["execution_fabric"]["status"], "accepted")
        finish_grant = self.finish_grant(
            cycle_id=cycle_id,
            lease_id="fabric-lease",
            generation=1,
            disposition="complete",
            decision="accepted",
            visible="true",
            tokens=720,
        )
        self.assertEqual(
            controller.finish_cycle(
                namespace(
                    project=str(self.project),
                    lease_id="fabric-lease",
                    generation=1,
                    cycle_id=cycle_id,
                    actual_outcome="capability",
                    evidence_ids=["delivery-1"],
                    cost_usd=1.0,
                    latency_minutes=5.0,
                    token_usage=720,
                    user_visible_movement="true",
                    work_disposition="complete",
                    reviewer_decision="accepted",
                    reviewer="cycle-reviewer",
                    reviewer_grant=finish_grant,
                    commit=None,
                    ref=None,
                )
            ),
            0,
        )
        final_state = controller.load_json(self.project / ".company-os" / "control.json")
        final_report = self.report(final_state)
        self.assertTrue(final_report["ok"], final_report["errors"])
        self.assertTrue(final_report["execution_fabric_accepted"])
        self.assertGreaterEqual(final_report["luna_token_share"], 0.70)

    def test_luna_fabric_rejects_phase_skips(self) -> None:
        cycle_id = self.begin_fabric_fixture()
        report_path = self.write_fabric_report("design", cycle_id)
        self.assertEqual(
            controller.record_fabric_phase(
                namespace(
                    project=str(self.project),
                    manager_id="manager-a",
                    report=report_path,
                )
            ),
            2,
        )

    def test_reclaimed_lease_cannot_advance_an_unresolved_fabric_cycle(self) -> None:
        cycle_id = self.begin_fabric_fixture()
        report_path = self.write_fabric_report("charter", cycle_id)
        state = controller.load_json(self.project / ".company-os" / "control.json")
        state["controller"]["lease_generation"] = 2
        state["controller"]["lease"] = {
            "lease_id": "recovery-lease", "owner": "recovery", "generation": 2,
            "program_version": 1, "allowed_transitions": sorted(controller.LEASE_TRANSITIONS),
            "acquired_at": controller.utc_now(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        }
        self.write_state(state)
        before = (self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()
        self.assertEqual(controller.record_fabric_phase(namespace(project=str(self.project), manager_id="manager-a", report=report_path, lease_id="recovery-lease", generation=2, owner="recovery")), 2)
        self.assertEqual(before, ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()))

        state["controller"]["lease_generation"] = 1
        state["controller"]["lease"] = {
            "lease_id": "fabric-lease", "owner": "master-sol", "generation": 1,
            "program_version": 1, "allowed_transitions": sorted(controller.LEASE_TRANSITIONS),
            "acquired_at": controller.utc_now(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        }
        self.write_state(state)
        self.assertEqual(controller.record_fabric_phase(namespace(project=str(self.project), manager_id="manager-a", report=report_path, lease_id="fabric-lease", generation=1, owner="master-sol")), 0)
        state = controller.load_json(self.project / ".company-os" / "control.json")
        payload = controller.fabric_phase_decision_payload(state, "manager-a", "charter", "continue")
        token = self.grant("master-sol", "fabric-phase-decision", resource="fabric:manager-a:charter", work_id="cap-1", cycle_id=cycle_id, dimension="execution-fabric", decision="continue", payload_hash=controller.command_payload_hash("fabric-phase-decision", payload))
        state["controller"]["lease_generation"] = 2
        state["controller"]["lease"] = {**state["controller"]["lease"], "lease_id": "recovery-lease", "owner": "recovery", "generation": 2}
        self.write_state(state)
        before = (self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()
        self.assertEqual(controller.decide_fabric_phase(namespace(project=str(self.project), manager_id="manager-a", decision="continue", decided_by="master-sol", master_grant=token, lease_id="recovery-lease", generation=2, owner="recovery")), 2)
        self.assertEqual(before, ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()))

    def test_fabric_token_usage_requires_integers_at_input_and_retained_audit(self) -> None:
        cycle_id = self.begin_fabric_fixture()
        report_path = self.write_fabric_report("charter", cycle_id)
        state = controller.load_json(self.project / ".company-os" / "control.json")
        report = json.loads((self.project / report_path).read_text())
        report["usage"]["luna_tokens"] = 1.5
        evidence_by_id, valid_evidence_ids = controller.current_fabric_evidence(state, self.project)
        errors = controller.validate_fabric_report_payload(state, "manager-a", "charter", report, valid_evidence_ids=valid_evidence_ids, evidence_by_id=evidence_by_id)
        self.assertIn("usage.luna_tokens must be a non-negative integer", errors)
        self.assertEqual(controller.record_fabric_phase(namespace(project=str(self.project), manager_id="manager-a", report=report_path)), 0)
        state = controller.load_json(self.project / ".company-os" / "control.json")
        entry = state["execution_fabric"]["managers"]["manager-a"]["reports"][0]
        entry["report"]["usage"]["manager_sol_tokens"] = 0.5
        changed = entry["report"]
        (self.project / report_path).write_text(json.dumps(changed), encoding="utf-8")
        entry["report_digest"] = controller.hashlib.sha256(controller.canonical_json(changed).encode()).hexdigest()
        entry["report_sha256"] = controller.sha256_file(self.project / report_path)
        self.write_state(state)
        audit = self.report(controller.load_json(self.project / ".company-os" / "control.json"))
        self.assertTrue(any("usage.manager_sol_tokens must be a non-negative integer" in error for error in audit["errors"]))

    def test_fabric_metric_type_matrix_is_rejected_without_type_errors(self) -> None:
        cycle_id = self.begin_fabric_fixture()
        state = controller.load_json(self.project / ".company-os" / "control.json")
        report = json.loads((self.project / self.write_fabric_report("execution", cycle_id)).read_text())
        evidence_by_id, valid_evidence_ids = controller.current_fabric_evidence(state, self.project)
        for field in ("luna_tokens", "terra_tokens", "manager_sol_tokens", "reviewer_sol_tokens"):
            for value in (-1, True, "1", float("nan"), float("inf"), 1.5):
                candidate = deepcopy(report)
                candidate["usage"][field] = value
                errors = controller.validate_fabric_report_payload(state, "manager-a", "execution", candidate, valid_evidence_ids=valid_evidence_ids, evidence_by_id=evidence_by_id)
                self.assertIn(f"usage.{field} must be a non-negative integer", errors)
            boundary = deepcopy(report)
            boundary["usage"][field] = 0
            errors = controller.validate_fabric_report_payload(state, "manager-a", "execution", boundary, valid_evidence_ids=valid_evidence_ids, evidence_by_id=evidence_by_id)
            self.assertNotIn(f"usage.{field} must be a non-negative integer", errors)
        for value in (-1, True, "1", float("nan"), float("inf")):
            candidate = deepcopy(report)
            candidate["usage"]["elapsed_minutes"] = value
            errors = controller.validate_fabric_report_payload(state, "manager-a", "execution", candidate, valid_evidence_ids=valid_evidence_ids, evidence_by_id=evidence_by_id)
            self.assertIn("usage.elapsed_minutes must be a finite non-negative number", errors)
        malformed_results = deepcopy(report)
        malformed_results["worker_metrics"]["accepted_first_pass"] = "1"
        errors = controller.validate_fabric_report_payload(state, "manager-a", "execution", malformed_results, valid_evidence_ids=valid_evidence_ids, evidence_by_id=evidence_by_id)
        self.assertIn("worker_metrics.accepted_first_pass must be a non-negative integer", errors)

    def test_fabric_malformed_evidence_ids_reject_atomically_without_lookup_errors(self) -> None:
        cycle_id = self.begin_fabric_fixture()
        report_path = self.write_fabric_report("charter", cycle_id)
        report = json.loads((self.project / report_path).read_text())
        report["evidence_ids"] = [{"not": "a string"}]
        (self.project / report_path).write_text(json.dumps(report), encoding="utf-8")
        before = (self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()
        self.assertEqual(controller.record_fabric_phase(namespace(project=str(self.project), manager_id="manager-a", report=report_path)), 2)
        self.assertEqual(before, ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()))

    def test_invalid_fabric_metrics_reject_atomically_at_command_boundary(self) -> None:
        cycle_id = self.begin_fabric_fixture()
        report_path = self.write_fabric_report("charter", cycle_id)
        for section, field, value in (
            ("usage", "luna_tokens", 1.5),
            ("usage", "elapsed_minutes", "1"),
            ("worker_metrics", "accepted_first_pass", "1"),
        ):
            report = json.loads((self.project / report_path).read_text())
            report[section][field] = value
            (self.project / report_path).write_text(json.dumps(report), encoding="utf-8")
            before = (
                (self.project / ".company-os" / "control.json").read_bytes(),
                (self.project / ".company-os" / "events.jsonl").read_bytes(),
            )
            self.assertEqual(
                controller.record_fabric_phase(
                    namespace(
                        project=str(self.project),
                        manager_id="manager-a",
                        report=report_path,
                    )
                ),
                2,
            )
            self.assertEqual(
                before,
                (
                    (self.project / ".company-os" / "control.json").read_bytes(),
                    (self.project / ".company-os" / "events.jsonl").read_bytes(),
                ),
            )
            report[section][field] = (
                5 if field == "luna_tokens"
                else 1 if field == "elapsed_minutes"
                else 0
            )
            (self.project / report_path).write_text(json.dumps(report), encoding="utf-8")


    def test_luna_fabric_rejects_report_tampering_before_master_decision(self) -> None:
        cycle_id = self.begin_fabric_fixture()
        report_path = self.write_fabric_report("charter", cycle_id)
        self.assertEqual(
            controller.record_fabric_phase(
                namespace(
                    project=str(self.project),
                    manager_id="manager-a",
                    report=report_path,
                )
            ),
            0,
        )
        state = controller.load_json(self.project / ".company-os" / "control.json")
        payload = controller.fabric_phase_decision_payload(
            state,
            "manager-a",
            "charter",
            "continue",
        )
        master_grant = self.grant(
            "master-sol",
            "fabric-phase-decision",
            resource="fabric:manager-a:charter",
            work_id="cap-1",
            cycle_id=cycle_id,
            dimension="execution-fabric",
            decision="continue",
            payload_hash=controller.command_payload_hash(
                "fabric-phase-decision",
                payload,
            ),
        )
        (self.project / report_path).write_text(
            '{"tampered": true}\n',
            encoding="utf-8",
        )
        self.assertEqual(
            controller.decide_fabric_phase(
                namespace(
                    project=str(self.project),
                    manager_id="manager-a",
                    decision="continue",
                    decided_by="master-sol",
                    master_grant=master_grant,
                )
            ),
            2,
        )

    def test_luna_fabric_blocks_work_completion_before_manager_acceptance(self) -> None:
        cycle_id = self.begin_fabric_fixture()
        finish_grant = self.finish_grant(
            cycle_id=cycle_id,
            lease_id="fabric-lease",
            generation=1,
            disposition="complete",
            decision="accepted",
            visible="true",
        )
        self.assertEqual(
            controller.finish_cycle(
                namespace(
                    project=str(self.project),
                    lease_id="fabric-lease",
                    generation=1,
                    cycle_id=cycle_id,
                    actual_outcome="capability",
                    evidence_ids=["delivery-1"],
                    cost_usd=1.0,
                    latency_minutes=5.0,
                    token_usage=100,
                    user_visible_movement="true",
                    work_disposition="complete",
                    reviewer_decision="accepted",
                    reviewer="cycle-reviewer",
                    reviewer_grant=finish_grant,
                    commit=None,
                    ref=None,
                )
            ),
            2,
        )

    def test_company_os_cancellation_propagates_to_luna_fabric(self) -> None:
        self.configure_fabric_fixture()
        self.assertEqual(
            controller.cancel_instance(
                namespace(project=str(self.project), reason="user stopped the program")
            ),
            0,
        )
        cancelled = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(cancelled["execution_fabric"]["status"], "cancelled")
        self.assertEqual(
            cancelled["execution_fabric"]["cancellation_reason"],
            "user stopped the program",
        )

    def test_scheduler_rejects_missing_product_gates(self) -> None:
        state = self.valid_state()
        state["evidence"]["reality"] = []
        state["controller"]["schedule_enabled"] = True
        report = self.report(state)
        self.assertFalse(report["ok"])
        self.assertIn("scheduler is enabled before the controller is ready", report["errors"])

    def test_scheduler_requires_exactly_one_ready_primary_work_item(self) -> None:
        state = self.valid_state()
        state["portfolio"]["active_work"][0]["status"] = "blocked"
        state["controller"]["validation"]["evidence_digest"] = controller.evidence_digest(state)
        report = self.report(state)
        self.assertFalse(report["scheduler_ready"])
        self.assertEqual(report["ready_primary_work_count"], 0)
        self.write_state(state)
        self.assertEqual(
            controller.set_schedule(namespace(project=str(self.project), enabled="true")),
            2,
        )

    def test_missing_external_issuer_fails_closed(self) -> None:
        state = self.valid_state()
        self.write_state(state)
        os.environ.pop(controller.ACTOR_PUBLIC_KEY_ENV, None)
        report = self.report(state)
        self.assertFalse(report["actor_issuer_ready"])
        self.assertFalse(report["scheduler_ready"])
        self.assertEqual(controller.set_schedule(namespace(project=str(self.project), enabled="true")), 2)
        self.assertEqual(
            controller.certify_instance(namespace(project=str(self.project), reviewer="certifier", reviewer_grant="missing")),
            2,
        )
        os.environ[controller.ACTOR_PUBLIC_KEY_ENV] = str(self.public_key)

    def test_scheduler_reports_protected_launcher_as_external_prerequisite(self) -> None:
        state = self.valid_state()
        controller.protected_launcher_attestation = self.previous_launcher_attestation
        try:
            report = self.report(state)
        finally:
            controller.protected_launcher_attestation = lambda: (True, "")
        self.assertTrue(report["actor_issuer_ready"])
        self.assertFalse(report["protected_launcher_ready"])
        self.assertFalse(report["scheduler_ready"])
        self.assertTrue(
            any("protected launcher" in item for item in report["external_prerequisites"])
        )

    def test_placeholder_evidence_is_rejected(self) -> None:
        state = self.valid_state()
        state["evidence"]["reality"] = [{"id": "placeholder"}]
        report = self.report(state)
        self.assertFalse(report["scheduler_ready"])
        self.assertTrue(any("evidence.reality" in error for error in report["errors"]))

    def test_strategy_fingerprint_detects_direct_goal_edit(self) -> None:
        state = self.valid_state()
        state["strategy"]["north_star"] = "Changed without program replacement"
        report = self.report(state)
        self.assertIn(
            "strategy.program_fingerprint does not match the authoritative program",
            report["errors"],
        )

    def test_enabler_cannot_claim_capability(self) -> None:
        state = self.valid_state()
        state["portfolio"]["active_work"][0].update(
            {
                "type": "enabler",
                "unlocks": "cap-1",
                "claimed_progress": "capability",
            }
        )
        report = self.report(state)
        self.assertTrue(any("cannot relabel enabler work" in error for error in report["errors"]))

    def test_maintenance_cannot_occupy_discovery_lane(self) -> None:
        state = self.valid_state()
        state["phase"] = "reality_audit"
        state["portfolio"]["active_work"][0].update(
            {
                "type": "maintenance",
                "unlocks": "cap-1",
                "claimed_progress": "reality",
            }
        )
        report = self.report(state)
        self.assertTrue(any("cannot occupy the primary discovery lane" in error for error in report["errors"]))

    def test_invalid_active_work_identity_and_status_are_rejected(self) -> None:
        state = self.valid_state()
        state["portfolio"]["active_work"][0].pop("id")
        state["portfolio"]["active_work"][0]["status"] = "completed"
        report = self.report(state)
        self.assertTrue(any(".id is required" in error for error in report["errors"]))
        self.assertTrue(any("invalid active status" in error for error in report["errors"]))

    def test_stale_lease_is_rejected(self) -> None:
        state = self.valid_state()
        state["controller"]["lease_generation"] = 1
        state["controller"]["lease"] = {
            "lease_id": "lease-1",
            "owner": "controller",
            "generation": 1,
            "program_version": 1,
            "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        }
        report = self.report(state)
        self.assertIn("controller lease is stale", report["errors"])

    def test_cancellation_requires_revoked_lease_and_cleared_work(self) -> None:
        state = self.valid_state()
        state["instance"]["status"] = "cancelled"
        state["controller"]["cancellation_requested"] = True
        state["controller"]["lease_generation"] = 1
        state["controller"]["lease"] = {
            "lease_id": "lease-1",
            "owner": "controller",
            "generation": 1,
            "program_version": 1,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        }
        report = self.report(state)
        self.assertIn("cancellation must revoke the active lease", report["errors"])
        self.assertIn("cancellation must clear active work", report["errors"])

    def test_paused_instance_cannot_schedule(self) -> None:
        state = self.valid_state()
        state["instance"]["status"] = "paused"
        state["controller"]["schedule_enabled"] = True
        report = self.report(state)
        self.assertIn("a paused or cancelled instance cannot enable scheduling", report["errors"])

    def test_project_root_is_bound_to_audit_target(self) -> None:
        state = self.valid_state()
        state["instance"]["project_root"] = "/tmp/not-this-project"
        report = self.report(state)
        self.assertIn("instance.project_root does not match the audited project", report["errors"])

    def test_actual_maintenance_cycles_are_capped(self) -> None:
        state = self.valid_state()
        state["feedback"]["cycles"] = [
            {
                "id": f"cycle-{index}",
                "program_version": 1,
                "work_id": "cap-1",
                "work_type": "maintenance",
                "status": "completed",
                "started_at": controller.utc_now(),
                "finished_at": controller.utc_now(),
                "intended_outcome": "Harden infrastructure",
                "actual_outcome": "capability",
                "evidence_ids": ["delivery-1"],
                "cost_usd": 10,
                "latency_minutes": 25,
                "token_usage": 1000,
                "user_visible_movement": True,
                "work_disposition": "continue",
                "reviewer_decision": "accepted",
                "reviewer": "cycle-reviewer",
                "reviewer_grant": {"actor": "cycle-reviewer", "grant_id": "fixture", "grant_digest": "fixture"},
            }
            for index in range(4)
        ]
        report = self.report(state)
        self.assertIn("actual maintenance cycles exceed the portfolio ceiling", report["errors"])

    def test_quality_requires_real_dimension_specific_evidence(self) -> None:
        state = self.valid_state()
        for item in state["quality"]["dimensions"].values():
            item["evidence"] = ["e-1"]
        report = self.report(state)
        self.assertFalse(report["quality_ready"])
        self.assertTrue(any("invalid or unrelated evidence" in error for error in report["errors"]))

    def test_critical_quality_below_gate_is_rejected(self) -> None:
        state = self.valid_state()
        state["quality"]["dimensions"]["user_value"]["score"] = 8
        report = self.report(state)
        self.assertIn("critical quality dimension user_value is below 9", report["errors"])

    def test_experience_quality_gate_excludes_future_production_dimensions(self) -> None:
        state = self.valid_state()
        state["phase"] = "experience"
        required = controller.applicable_quality_dimensions(state)
        checkpoint = controller.current_quality_checkpoint(state)[2]
        state["evidence"]["experience"][0].update(
            {
                "quality_dimensions": sorted(required), "outcome_id": "cap-1", "work_id": "cap-1",
                "cycle_id": checkpoint, "rubric_version": "quality-v1",
            }
        )
        for name, item in state["quality"]["dimensions"].items():
            item["score"] = None
            item["evidence"] = []
            item["rubric_version"] = None
            item["scored_by"] = None
            item["reviewed_by"] = None
            if name in required:
                quality_values = {
                    "dimension": name, "score": 9, "evidence_ids": ["experience-1"],
                    "rubric_version": "quality-v1", "scored_by": "quality-scorer", "reviewed_by": "quality-reviewer",
                    "outcome_id": "cap-1", "work_id": "cap-1", "cycle_id": checkpoint,
                    "artifact_digest": controller.sha256_file(self.project / "experience.md"),
                }
                quality_payload_hash = controller.command_payload_hash(
                    "score-quality", controller.quality_command_payload(quality_values)
                )
                scorer = self.grant(
                    "quality-scorer", "score-quality", resource=f"quality:{name}", work_id="cap-1",
                    cycle_id=checkpoint, dimension=name, decision="score:9", payload_hash=quality_payload_hash,
                )
                reviewer = self.grant(
                    "quality-reviewer", "score-quality-review", resource=f"quality:{name}", work_id="cap-1",
                    cycle_id=checkpoint, dimension=name, decision="review:9", payload_hash=quality_payload_hash,
                )
                item.update(
                    {
                        "score": 9,
                        "evidence": ["experience-1"],
                        "rubric_version": "quality-v1",
                        "scored_by": "quality-scorer",
                        "reviewed_by": "quality-reviewer",
                        "scorer_grant": self.grant_record(state, "quality-scorer", scorer),
                        "reviewer_grant": self.grant_record(state, "quality-reviewer", reviewer),
                        "binding": {
                            "outcome_id": "cap-1", "work_id": "cap-1", "cycle_id": checkpoint,
                            "artifact_digest": controller.sha256_file(self.project / "experience.md"),
                            "rubric_version": "quality-v1",
                        },
                    }
                )
        state["controller"]["validation"]["evidence_digest"] = controller.evidence_digest(state)
        report = self.report(state)
        self.assertTrue(report["quality_ready"], report["errors"])
        self.assertNotIn("security", report["applicable_quality_dimensions"])
        state["quality"]["dimensions"]["user_value"]["score"] = None
        report = self.report(state)
        self.assertFalse(report["quality_ready"])
        self.assertIn("phase experience requires complete applicable quality evidence", report["errors"])

    def test_meta_loop_cannot_self_approve(self) -> None:
        state = self.valid_state()
        state["feedback"]["applied_adaptations"] = [
            {
                "id": "adapt-1",
                "program_version": 1,
                "failure_pattern": "Repeated drift",
                "hypothesis": "Tighter WIP improves focus",
                "experiment": "Reduce WIP for two cycles",
                "success_metric": "Visible capability each cycle",
                "rollback": "Restore prior WIP",
                "proposer": "sol",
                "reviewer": "sol",
                "review_decision": "accepted",
                "status": "applied",
                "meta_depth": 1,
                "time_cap_minutes": 50,
                "cost_cap_usd": 10,
                "changes": ["max_active_work"],
            }
        ]
        report = self.report(state)
        self.assertTrue(any("self-approved" in error for error in report["errors"]))

    def test_adaptation_review_requires_exact_independent_signed_digest(self) -> None:
        self.write_state(self.valid_state())
        proposal_args = namespace(
            project=str(self.project), id="adapt-signed", failure_pattern="Repeated drift",
            hypothesis="Narrow the review cadence", experiment="One bounded review change",
            success_metric="No repeated drift", rollback="Restore the prior cadence",
            proposer="proposal-owner", time_cap_minutes=30, cost_cap_usd=2.0,
            changes=["review_cadence"],
        )
        self.assertEqual(controller.propose_adaptation(proposal_args), 0)
        before = (self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()
        self.assertEqual(controller.review_adaptation(namespace(project=str(self.project), id="adapt-signed", reviewer="independent-reviewer", decision="accepted", reviewer_grant="")), 2)
        self.assertEqual(before, ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()))
        state = controller.load_json(self.project / ".company-os" / "control.json")
        proposal = state["feedback"]["pending_adaptations"][0]
        payload = {"adaptation_id": "adapt-signed", "proposal_digest": proposal["proposal_digest"], "reviewer": "independent-reviewer", "decision": "accepted"}
        token = self.grant("independent-reviewer", "review-adaptation", resource="adaptation:adapt-signed", work_id="", cycle_id="", dimension="meta-loop", decision="accepted", payload_hash=controller.command_payload_hash("review-adaptation", payload))
        self.assertEqual(controller.review_adaptation(namespace(project=str(self.project), id="adapt-signed", reviewer="independent-reviewer", decision="accepted", reviewer_grant=token)), 0)
        report = self.report(controller.load_json(self.project / ".company-os" / "control.json"))
        self.assertTrue(report["ok"], report["errors"])

    def test_adaptation_review_rejects_grant_matrix_atomically(self) -> None:
        self.write_state(self.valid_state())
        def propose(item_id: str, proposer: str = "proposal-owner") -> dict:
            self.assertEqual(controller.propose_adaptation(namespace(project=str(self.project), id=item_id, failure_pattern="Repeated drift", hypothesis="Narrow cadence", experiment="Bounded change", success_metric="No drift", rollback="Restore cadence", proposer=proposer, time_cap_minutes=1, cost_cap_usd=0.0, changes=["review_cadence"])), 0)
            return controller.load_json(self.project / ".company-os" / "control.json")["feedback"]["pending_adaptations"][-1]
        def unchanged(call) -> None:
            before = (self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()
            self.assertEqual(call(), 2)
            self.assertEqual(before, ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()))
        proposal = propose("adapt-missing")
        unchanged(lambda: controller.review_adaptation(namespace(project=str(self.project), id=proposal["id"], reviewer="reviewer", decision="accepted", reviewer_grant="")))
        proposal = propose("adapt-malformed")
        unchanged(lambda: controller.review_adaptation(namespace(project=str(self.project), id=proposal["id"], reviewer="reviewer", decision="accepted", reviewer_grant="malformed")))
        proposal = propose("adapt-untrusted")
        unchanged(lambda: controller.review_adaptation(namespace(project=str(self.project), id=proposal["id"], reviewer="reviewer", decision="accepted", reviewer_grant=self.grant("other-reviewer", "review-adaptation", resource=f"adaptation:{proposal['id']}", work_id="", cycle_id="", dimension="meta-loop", decision="accepted", payload_hash="wrong"))))
        proposal = propose("adapt-self", proposer="self-reviewer")
        unchanged(lambda: controller.review_adaptation(namespace(project=str(self.project), id=proposal["id"], reviewer="self-reviewer", decision="accepted", reviewer_grant="")))
        proposal = propose("adapt-mismatch")
        mismatch = self.grant("reviewer", "review-adaptation", resource=f"adaptation:{proposal['id']}", work_id="", cycle_id="", dimension="meta-loop", decision="accepted", payload_hash="wrong")
        unchanged(lambda: controller.review_adaptation(namespace(project=str(self.project), id=proposal["id"], reviewer="reviewer", decision="accepted", reviewer_grant=mismatch)))
        proposal = propose("adapt-replay")
        payload = {"adaptation_id": proposal["id"], "proposal_digest": proposal["proposal_digest"], "reviewer": "reviewer", "decision": "accepted"}
        token = self.grant("reviewer", "review-adaptation", resource=f"adaptation:{proposal['id']}", work_id="", cycle_id="", dimension="meta-loop", decision="accepted", payload_hash=controller.command_payload_hash("review-adaptation", payload))
        self.assertEqual(controller.review_adaptation(namespace(project=str(self.project), id=proposal["id"], reviewer="reviewer", decision="accepted", reviewer_grant=token)), 0)
        state = controller.load_json(self.project / ".company-os" / "control.json")
        replay = deepcopy(state["feedback"]["applied_adaptations"][-1])
        replay.update({"status": "proposed"})
        state["feedback"]["pending_adaptations"].append(replay)
        self.write_state(state)
        unchanged(lambda: controller.review_adaptation(namespace(project=str(self.project), id=proposal["id"], reviewer="reviewer", decision="accepted", reviewer_grant=token)))

    def test_adaptation_audit_reconstructs_accepted_and_rejected_reviews(self) -> None:
        self.write_state(self.valid_state())
        def propose_and_review(item_id: str, decision: str) -> None:
            self.assertEqual(controller.propose_adaptation(namespace(project=str(self.project), id=item_id, failure_pattern="Drift", hypothesis="Tighten cadence", experiment="Bounded change", success_metric="No drift", rollback="Restore cadence", proposer="proposer", time_cap_minutes=1, cost_cap_usd=0.0, changes=["review_cadence"])), 0)
            state = controller.load_json(self.project / ".company-os" / "control.json")
            proposal = state["feedback"]["pending_adaptations"][-1]
            payload = {"adaptation_id": item_id, "proposal_digest": proposal["proposal_digest"], "reviewer": "reviewer", "decision": decision}
            token = self.grant("reviewer", "review-adaptation", resource=f"adaptation:{item_id}", work_id="", cycle_id="", dimension="meta-loop", decision=decision, payload_hash=controller.command_payload_hash("review-adaptation", payload))
            self.assertEqual(controller.review_adaptation(namespace(project=str(self.project), id=item_id, reviewer="reviewer", decision=decision, reviewer_grant=token)), 0)
        propose_and_review("adapt-audit-accepted", "accepted")
        propose_and_review("adapt-audit-rejected", "rejected")
        state = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertTrue(self.report(state)["ok"], self.report(state)["errors"])
        state["feedback"]["applied_adaptations"][0]["reviewer_grant"] = None
        audit = self.report(state)
        self.assertTrue(any("reviewer grant" in error for error in audit["errors"]))
        state = controller.load_json(self.project / ".company-os" / "control.json")
        state["feedback"]["applied_adaptations"][1]["proposal_digest"] = "tampered"
        audit = self.report(state)
        self.assertTrue(any("proposal digest" in error or "reviewer grant" in error for error in audit["errors"]))
        state = controller.load_json(self.project / ".company-os" / "control.json")
        state["feedback"]["applied_adaptations"][0]["status"] = "unknown"
        self.assertTrue(any("invalid applied_adaptations status" in error for error in self.report(state)["errors"]))
        state = controller.load_json(self.project / ".company-os" / "control.json")
        pending = deepcopy(state["feedback"]["applied_adaptations"][0])
        pending["status"] = "proposed"
        state["feedback"]["pending_adaptations"].append(pending)
        self.assertTrue(any("carries reviewed authority" in error for error in self.report(state)["errors"]))

    def test_ttl_and_finish_metrics_reject_before_state_or_event_mutation(self) -> None:
        self.write_state(self.valid_state())
        self.assertEqual(controller.set_schedule(namespace(project=str(self.project), enabled="true")), 0)
        before = (self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()
        self.assertEqual(controller.acquire_lease(namespace(project=str(self.project), owner=" ", ttl_seconds=300)), 2)
        self.assertEqual(before, ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()))
        for ttl_seconds in (0, -1, True):
            self.assertEqual(controller.acquire_lease(namespace(project=str(self.project), owner="scheduler", ttl_seconds=ttl_seconds)), 2)
            self.assertEqual(before, ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()))
        self.assertEqual(controller.acquire_lease(namespace(project=str(self.project), owner="scheduler", ttl_seconds=300)), 0)
        lease = controller.load_json(self.project / ".company-os" / "control.json")["controller"]["lease"]
        self.assertEqual(controller.begin_cycle(namespace(project=str(self.project), lease_id=lease["lease_id"], generation=lease["generation"], owner="scheduler", work_id="cap-1", intended_outcome="Deliver capability")), 0)
        cycle_id = controller.load_json(self.project / ".company-os" / "control.json")["feedback"]["cycles"][0]["id"]
        base_finish = {
            "project": str(self.project),
            "lease_id": lease["lease_id"],
            "generation": lease["generation"],
            "owner": "scheduler",
            "cycle_id": cycle_id,
            "actual_outcome": "capability",
            "evidence_ids": ["delivery-1"],
            "cost_usd": 0.0,
            "latency_minutes": 0.0,
            "token_usage": 0,
            "user_visible_movement": "false",
            "work_disposition": "continue",
            "reviewer_decision": "accepted",
            "reviewer": "cycle-reviewer",
            "reviewer_grant": "",
            "commit": None,
            "ref": None,
        }
        for field, invalid_values in (
            ("cost_usd", (-1, True, "1", float("nan"), float("inf"))),
            ("latency_minutes", (-1, True, "1", float("nan"), float("inf"))),
            ("token_usage", (-1, True, "1", 1.5, float("nan"), float("inf"))),
        ):
            for invalid_value in invalid_values:
                candidate = {**base_finish, field: invalid_value}
                before = (
                    (self.project / ".company-os" / "control.json").read_bytes(),
                    (self.project / ".company-os" / "events.jsonl").read_bytes(),
                )
                self.assertEqual(controller.finish_cycle(namespace(**candidate)), 2)
                self.assertEqual(before, ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()))

        self.bind_delivery_evidence(cycle_id)
        self.rebind_quality(cycle_id)
        boundary_grant = self.finish_grant(
            cycle_id=cycle_id,
            lease_id=lease["lease_id"],
            generation=lease["generation"],
            disposition="complete",
            decision="accepted",
            visible="true",
            cost=0.0,
            latency=0.0,
            tokens=0,
        )
        self.assertEqual(
            controller.finish_cycle(
                namespace(
                    **{
                        **base_finish,
                        "user_visible_movement": "true",
                        "work_disposition": "complete",
                        "reviewer_grant": boundary_grant,
                    }
                )
            ),
            0,
        )

    def test_fabric_hard_caps_canonical_scopes_and_narrowing_are_enforced(self) -> None:
        manifest = self.fabric_manifest()
        self.assertTrue(controller.validate_fabric_manifest(manifest)["valid"])
        for mutation in (
            lambda item: item.update({"max_managers": 3}),
            lambda item: item["managers"][0].update({"write_scope": ["src", "src/workflow"]}),
            lambda item: item["managers"][0].update({"write_scope": ["src/workflow", "src"]}),
            lambda item: item["managers"][0].update({"write_scope": ["src", "src"]}),
            lambda item: item["managers"][0].update({"write_scope": ["src/./workflow"]}),
            lambda item: item["managers"][0].update({"write_scope": ["/escape"]}),
            lambda item: item["managers"][0]["workers"][0].update({"write_scope": ["../escape"]}),
            lambda item: item["managers"][0]["workers"][0].update({"write_scope": ["C:/escape"]}),
            lambda item: item["managers"][0].update({"write_scope": ["café", "café"]}),
            lambda item: item["managers"][0]["workers"][0]["budget"].update({"token_limit": 9000}),
            lambda item: item["managers"][0]["workers"][0]["budget"].update({"token_limit": 1.5}),
            lambda item: item["managers"][0]["workers"][0]["budget"].update({"max_concurrency": 2}),
        ):
            candidate = deepcopy(manifest)
            mutation(candidate)
            self.assertFalse(controller.validate_fabric_manifest(candidate)["valid"])

    def test_fabric_exact_2_3_6_boundary_and_malformed_budgets(self) -> None:
        manifest = self.fabric_manifest()
        manifest["managers"][0]["write_scope"] = ["src/a"]
        worker = manifest["managers"][0]["workers"][0]
        worker["write_scope"] = ["src/a/1"]
        worker["budget"] = {"time_minutes": 10, "token_limit": 1500, "cost_usd": 1.5, "max_concurrency": 1, "max_retries": 1}
        for index in (2, 3):
            sibling = deepcopy(worker)
            sibling["id"] = f"worker-a{index}"
            sibling["task"] = f"Bounded task {index}"
            sibling["write_scope"] = [f"src/a/{index}"]
            manifest["managers"][0]["workers"].append(sibling)
        second_manager = deepcopy(manifest["managers"][0])
        second_manager["id"] = "manager-b"
        second_manager["outcome"] = "Deliver the second bounded workflow"
        second_manager["write_scope"] = ["src/b"]
        for index, child in enumerate(second_manager["workers"], start=1):
            child["id"] = f"worker-b{index}"
            child["task"] = f"Second bounded task {index}"
            child["write_scope"] = [f"src/b/{index}"]
            child["outcome_context"]["manager_outcome"] = second_manager["outcome"]
        manifest["managers"].append(second_manager)
        self.assertTrue(controller.validate_fabric_manifest(manifest)["valid"])
        budget_locations = (
            lambda item: item["budget"],
            lambda item: item["managers"][0]["budget"],
            lambda item: item["managers"][0]["workers"][0]["budget"],
        )
        for budget_at in budget_locations:
            for field in ("time_minutes", "cost_usd"):
                for value in (-1, True, "1", float("nan"), float("inf")):
                    malformed = deepcopy(self.fabric_manifest())
                    budget_at(malformed)[field] = value
                    self.assertFalse(controller.validate_fabric_manifest(malformed)["valid"])
            for field in ("token_limit", "max_concurrency", "max_retries"):
                for value in (-1, True, "1", 1.5, float("nan"), float("inf")):
                    malformed = deepcopy(self.fabric_manifest())
                    budget_at(malformed)[field] = value
                    self.assertFalse(controller.validate_fabric_manifest(malformed)["valid"])

        zero_boundary = deepcopy(self.fabric_manifest())
        for budget in (
            zero_boundary["budget"],
            zero_boundary["managers"][0]["budget"],
            zero_boundary["managers"][0]["workers"][0]["budget"],
        ):
            budget.update(
                {
                    "time_minutes": 0,
                    "token_limit": 0,
                    "cost_usd": 0,
                    "max_retries": 0,
                }
            )
        self.assertTrue(controller.validate_fabric_manifest(zero_boundary)["valid"])

    def test_unicode_case_scope_aliases_collide_in_both_declaration_orders(self) -> None:
        for scopes in (["Café", "café"], ["café", "Café"]):
            manifest = self.fabric_manifest()
            manifest["managers"][0]["write_scope"] = scopes
            result = controller.validate_fabric_manifest(manifest)
            self.assertFalse(result["valid"])
            self.assertTrue(any("collision" in error for error in result["errors"]))

    def test_fabric_budget_siblings_cannot_oversubscribe(self) -> None:
        manager_oversubscribed = self.fabric_manifest()
        first = manager_oversubscribed["managers"][0]["workers"][0]
        first["write_scope"] = []
        second = deepcopy(first)
        second.update({"id": "worker-a2", "task": "Separate bounded task"})
        second["budget"] = {
            **second["budget"],
            "time_minutes": 16,
            "token_limit": 3000,
            "cost_usd": 3.0,
        }
        first["budget"] = {
            **first["budget"],
            "time_minutes": 16,
            "token_limit": 3000,
            "cost_usd": 3.0,
        }
        manager_oversubscribed["managers"][0]["workers"].append(second)
        result = controller.validate_fabric_manifest(manager_oversubscribed)
        self.assertFalse(result["valid"])
        self.assertTrue(any("worker time_minutes allocations oversubscribe" in error for error in result["errors"]))
        self.assertTrue(any("worker token_limit allocations oversubscribe" in error for error in result["errors"]))

        program_oversubscribed = self.fabric_manifest()
        second_manager = deepcopy(program_oversubscribed["managers"][0])
        second_manager["id"] = "manager-b"
        second_manager["write_scope"] = ["other"]
        second_manager["workers"][0]["id"] = "worker-b1"
        second_manager["workers"][0]["write_scope"] = ["other/a"]
        program_oversubscribed["managers"].append(second_manager)
        self.assertTrue(controller.validate_fabric_manifest(program_oversubscribed)["valid"])
        program_oversubscribed["budget"]["time_minutes"] = 59
        program_oversubscribed["budget"]["cost_usd"] = 9.0
        result = controller.validate_fabric_manifest(program_oversubscribed)
        self.assertFalse(result["valid"])
        self.assertTrue(any("manager time_minutes allocations oversubscribe" in error for error in result["errors"]))
        self.assertTrue(any("manager cost_usd allocations oversubscribe" in error for error in result["errors"]))

    def test_core_promotion_needs_three_projects(self) -> None:
        state = self.valid_state()
        state["feedback"]["core_promotion_candidates"] = [
            {
                "id": "promote-1",
                "validated_project_ids": ["alpha", "beta"],
                "proposer": "portfolio",
                "reviewer": "audit",
            }
        ]
        report = self.report(state)
        self.assertTrue(any("requires three independent projects" in error for error in report["errors"]))

    def test_recursive_meta_loop_is_rejected(self) -> None:
        state = self.valid_state()
        state["controller"]["meta_loop_depth"] = 2
        report = self.report(state)
        self.assertIn("controller.meta_loop_depth must remain exactly 1", report["errors"])

    def test_maintenance_or_enabler_cannot_be_primary(self) -> None:
        state = self.valid_state()
        state["portfolio"]["active_work"][0].update(
            {
                "type": "maintenance",
                "unlocks": "cap-1",
                "claimed_progress": "learning",
            }
        )
        report = self.report(state)
        self.assertTrue(any("cannot be primary" in error for error in report["errors"]))

        self.write_state(self.valid_state())
        result = controller.queue_work(
            namespace(
                project=str(self.project),
                id="enabler-1",
                type="enabler",
                title="Enable the workspace",
                user_visible_outcome="The workspace becomes faster",
                claimed_progress="learning",
                owner="engineering",
                primary="true",
                unlocks=["cap-1"],
            )
        )
        self.assertEqual(result, 2)

    def test_changing_primary_clears_stale_quality_applicability(self) -> None:
        state = self.valid_state()
        state["portfolio"]["committed_outcomes"].append(
            {
                "id": "cap-2", "type": "capability", "title": "Second workspace",
                "user_visible_outcome": "A user completes a different workflow", "program_version": 1, "status": "active",
            }
        )
        self.write_state(state)
        result = controller.queue_work(
            namespace(
                project=str(self.project), id="work-2", type="capability", title="Second workspace",
                user_visible_outcome="A user completes a different workflow", claimed_progress="capability",
                owner="second-owner", primary="true", unlocks=[], outcome_id="cap-2",
                incident_ref=None, severity=None, justification=None, incident_actor=None, incident_grant=None,
                approval_actor=None, approval_grant=None, repeat_override_reason=None,
                repeat_override_reviewer=None, repeat_override_grant=None,
            )
        )
        self.assertEqual(result, 0)
        changed = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertTrue(all(item["score"] is None for item in changed["quality"]["dimensions"].values()))
        report = self.report(changed)
        self.assertFalse(report["quality_ready"])
        self.assertFalse(report["scheduler_ready"])

    def write_state(self, state: dict) -> None:
        directory = self.project / ".company-os"
        directory.mkdir(exist_ok=True)
        controller.atomic_write_json(directory / "control.json", state)
        (directory / "events.jsonl").write_text("", encoding="utf-8")

    def supersession_args(
        self,
        state: dict,
        evidence_id: str,
        artifact: Path,
        replacement_id: str,
        *,
        reviewer_grant: bool = True,
    ) -> object:
        bucket, predecessor = next(
            (bucket, item)
            for bucket in controller.EVIDENCE_BUCKETS
            for item in state["evidence"][bucket]
            if item["id"] == evidence_id
        )
        args = namespace(
            project=str(self.project), evidence_id=evidence_id,
            artifact=str(artifact.relative_to(self.project)), source="repair",
            decision_impact="restore evidence integrity", author="repair-author",
            reviewer="repair-reviewer", reason="replace invalid current evidence",
            freshness_days=None, quality_dimensions=None, outcome_id=None,
            work_id=None, cycle_id=None, rubric_version=None, id=replacement_id,
            reviewer_grant="",
        )
        review_payload = controller.supersede_evidence_review_payload(
            args,
            predecessor=predecessor,
            replacement_id=replacement_id,
            artifact_digest=controller.sha256_file(artifact),
            bucket=bucket,
            source_artifact_path=str(artifact.relative_to(self.project)),
        )
        if reviewer_grant:
            args.reviewer_grant = self.grant(
                "repair-reviewer", "supersede-evidence", resource=f"evidence:{evidence_id}",
                work_id="", cycle_id="", dimension="evidence", decision="accepted",
                payload_hash=controller.command_payload_hash("supersede-evidence", review_payload),
            )
        return args

    def commit_correction_fixture(self) -> tuple[dict, Path, object, str, str]:
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        subprocess.run(["git", "config", "user.email", "company-os@example.invalid"], cwd=self.project, check=True)
        subprocess.run(["git", "config", "user.name", "Company OS Test"], cwd=self.project, check=True)
        anchor = self.project / "anchor.txt"
        anchor.write_text("accepted release\n", encoding="utf-8")
        subprocess.run(["git", "add", "anchor.txt"], cwd=self.project, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "accepted release"], cwd=self.project, check=True)
        correct_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.project, check=True,
            text=True, capture_output=True,
        ).stdout.strip()
        wrong_commit = "f" * 40

        state = self.valid_state()
        state["instance"]["status"] = "paused"
        self.write_state(state)
        artifact = self.project / "install-provenance.json"
        artifact.write_text(
            json.dumps({"schema_version": 1, "commit": wrong_commit, "release": "test"}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.record_evidence(namespace(
                project=str(self.project), outcome="learning", artifact=artifact.name,
                source="release installer", decision_impact="bind installed release",
                author="release-author", reviewer="install-reviewer", freshness_days=30,
                quality_dimensions=["evidence_integrity"], outcome_id=None, work_id=None,
                cycle_id=None, rubric_version=None, id="commit-provenance",
            )), 0)
        artifact.write_text(
            json.dumps({"schema_version": 1, "commit": correct_commit, "release": "test"}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        state = controller.load_json(self.project / ".company-os" / "control.json")
        predecessor = next(item for item in state["evidence"]["learning"] if item["id"] == "commit-provenance")
        args = namespace(
            project=str(self.project), evidence_id="commit-provenance", artifact=artifact.name,
            source="independent Git verification", decision_impact="correct release provenance",
            reason="recorded commit does not identify the installed release",
            declarant="correction-declarant", adjudicator="correction-adjudicator",
            declarant_grant="", adjudicator_grant="", old_value=wrong_commit,
            new_value=correct_commit, transition_at=controller.utc_now(), freshness_days=30,
            id="commit-provenance-corrected",
        )
        review_payload = controller.correct_evidence_review_payload(
            args, predecessor=predecessor, replacement_id=args.id,
            replacement_digest=controller.sha256_file(artifact), bucket="learning",
            source_artifact_path=artifact.name,
        )
        payload_hash = controller.command_payload_hash("correct-evidence", review_payload)
        args.declarant_grant = self.grant(
            args.declarant, "correct-evidence-declare", resource="evidence:commit-provenance",
            work_id="", cycle_id="", dimension="evidence", decision="proposed",
            payload_hash=payload_hash,
        )
        args.adjudicator_grant = self.grant(
            args.adjudicator, "correct-evidence-adjudicate", resource="evidence:commit-provenance",
            work_id="", cycle_id="", dimension="evidence", decision="accepted",
            payload_hash=payload_hash,
        )
        return state, artifact, args, wrong_commit, correct_commit

    def test_typed_git_commit_correction_is_dually_authorized_and_append_only(self) -> None:
        _, _, args, wrong_commit, correct_commit = self.commit_correction_fixture()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.correct_evidence(args), 0)
        corrected = controller.load_json(self.project / ".company-os" / "control.json")
        current = next(item for item in corrected["evidence"]["learning"] if item["id"] == args.id)
        self.assertEqual(current["supersedes_evidence_id"], "commit-provenance")
        self.assertEqual(current["correction_type"], "git_commit_identity")
        archived = next(
            item for item in corrected["feedback"]["archived_evidence"]
            if item.get("record", {}).get("id") == "commit-provenance"
        )
        self.assertEqual(archived["transition_kind"], "semantic_retraction")
        self.assertEqual(archived["correction_payload"]["old_value"], wrong_commit)
        self.assertEqual(archived["correction_payload"]["new_value"], correct_commit)
        self.assertTrue(archived["old_snapshot_available"])
        self.assertFalse(any("semantic" in error for error in self.report(corrected)["errors"]))

    def test_typed_git_commit_correction_rejects_broader_edits_and_authority_conflicts(self) -> None:
        initial, artifact, args, _, _ = self.commit_correction_fixture()
        new_document = json.loads(artifact.read_text(encoding="utf-8"))
        new_document["release"] = "silently changed"
        artifact.write_text(json.dumps(new_document, sort_keys=True) + "\n", encoding="utf-8")
        before = (self.project / ".company-os" / "control.db").read_bytes() if (self.project / ".company-os" / "control.db").exists() else b""
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.correct_evidence(args), 2)
        retained = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertTrue(any(item["id"] == "commit-provenance" for item in retained["evidence"]["learning"]))
        if before:
            self.assertEqual((self.project / ".company-os" / "control.db").read_bytes(), before)

        artifact.write_text(
            json.dumps({"schema_version": 1, "commit": args.new_value, "release": "test"}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        args.adjudicator = "install-reviewer"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.correct_evidence(args), 2)
        retained = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(
            [item["id"] for item in retained["evidence"]["learning"] if item["id"].startswith("commit-provenance")],
            ["commit-provenance"],
        )

    def test_typed_git_commit_correction_rejects_malformed_predecessor_before_grants(self) -> None:
        baseline, _, args, _, _ = self.commit_correction_fixture()
        malformed = {
            "artifact digest mismatch": lambda item: item.update(artifact_sha256="0" * 64),
            "invalid freshness": lambda item: item.update(freshness_days=0),
            "unarchived predecessor linkage": lambda item: item.update(
                supersedes_evidence_id="missing-predecessor"
            ),
        }
        for label, mutate in malformed.items():
            with self.subTest(label=label):
                candidate = deepcopy(baseline)
                target = next(
                    item for item in candidate["evidence"]["learning"]
                    if item["id"] == args.evidence_id
                )
                mutate(target)
                self.write_state(candidate)
                before = controller.load_json(self.project / ".company-os" / "control.json")
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(controller.correct_evidence(args), 2)
                self.assertIn("semantic correction requires a structurally valid predecessor", output.getvalue())
                self.assertEqual(
                    controller.load_json(self.project / ".company-os" / "control.json"),
                    before,
                )

        implicit = deepcopy(baseline)
        next(
            item for item in implicit["evidence"]["learning"]
            if item["id"] == args.evidence_id
        ).pop("active")
        self.write_state(implicit)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(controller.correct_evidence(args), 2)
        self.assertIn("requires predecessor active=true explicitly", output.getvalue())

    def test_typed_git_commit_correction_archive_tampering_fails_audit(self) -> None:
        _, _, args, _, _ = self.commit_correction_fixture()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.correct_evidence(args), 0)
        corrected = controller.load_json(self.project / ".company-os" / "control.json")
        def archive(state: dict) -> dict:
            return next(
                item for item in state["feedback"]["archived_evidence"]
                if item.get("transition_kind") == "semantic_retraction"
            )
        different_valid_time = (
            datetime.fromisoformat(archive(corrected)["superseded_at"]) - timedelta(seconds=1)
        ).isoformat()

        tampering = {
            "signed payload": lambda state: archive(state)["correction_payload"].update(new_value="0" * 40),
            "archived active state": lambda state: archive(state)["record"].update(active=True),
            "archived record timestamp": lambda state: archive(state)["record"].update(superseded_at=different_valid_time),
            "archive timestamp": lambda state: archive(state).update(superseded_at=different_valid_time),
            "successor observed_at": lambda state: next(
                item for item in state["evidence"]["learning"] if item["id"] == args.id
            ).update(observed_at=different_valid_time),
            "successor artifact path": lambda state: next(
                item for item in state["evidence"]["learning"] if item["id"] == args.id
            ).update(artifact_path="nonexistent.json"),
        }
        for label, mutate in tampering.items():
            with self.subTest(label=label):
                candidate = deepcopy(corrected)
                mutate(candidate)
                self.assertTrue(self.report(candidate)["errors"])

    def test_semantic_successor_remains_content_addressed_after_program_replacement(self) -> None:
        _, _, args, _, _ = self.commit_correction_fixture()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.correct_evidence(args), 0)
            self.assertEqual(controller.replace_program(namespace(
                project=str(self.project), north_star="Next verified program",
                current_outcome="Prove retained correction history",
                success_metric="Every semantic successor remains immutable",
                reason="advance after the correction",
            )), 0)
        replaced = controller.load_json(self.project / ".company-os" / "control.json")
        baseline_errors = self.report(replaced)["errors"]
        self.assertEqual(baseline_errors, ["phase reality_audit requires valid evidence.reality"])

        def successor(state: dict) -> dict:
            return next(
                record
                for archive in state["feedback"]["archived_evidence"]
                if isinstance(archive, dict) and isinstance(archive.get("evidence"), dict)
                for records in archive["evidence"].values()
                for record in records
                if record.get("id") == args.id
            )

        tampering = {
            "artifact path": lambda state: successor(state).update(artifact_path="arbitrary.json"),
            "snapshot digest": lambda state: successor(state).update(snapshot_sha256="0" * 64),
            "inactive successor": lambda state: successor(state).update(active=False),
            "unsigned metadata": lambda state: successor(state).update(trusted=True),
            "mutable source substitution": lambda state: successor(state).update(
                snapshot_path=successor(state)["source_artifact_path"],
                artifact_path=successor(state)["source_artifact_path"],
            ),
        }
        for label, mutate in tampering.items():
            with self.subTest(label=label):
                candidate = deepcopy(replaced)
                mutate(candidate)
                self.assertTrue(any(
                    "semantic" in error
                    for error in set(self.report(candidate)["errors"]) - set(baseline_errors)
                ))

    def test_typed_git_commit_correction_refuses_terminal_references_and_payload_substitution(self) -> None:
        baseline, _, args, _, _ = self.commit_correction_fixture()
        mutated_args = deepcopy(args)
        mutated_args.reason = "substituted after signing"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.correct_evidence(mutated_args), 2)
        retained = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertTrue(any(item["id"] == "commit-provenance" for item in retained["evidence"]["learning"]))

        gates = {
            "completed cycle": lambda state: state["feedback"]["cycles"].append(
                {"id": "terminal-cycle", "status": "completed", "evidence_ids": ["commit-provenance"]}
            ),
            "completed work": lambda state: state["portfolio"]["completed_work"].append(
                {"id": "terminal-work", "completion": {"evidence_ids": ["commit-provenance"]}}
            ),
            "accepted fabric": lambda state: state["execution_fabric"].update(
                status="accepted",
                managers={"manager": {"reports": [{"report": {"evidence_ids": ["commit-provenance"]}}]}},
            ),
        }
        for label, mutator in gates.items():
            with self.subTest(label=label):
                candidate = deepcopy(baseline)
                mutator(candidate)
                self.write_state(candidate)
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(controller.correct_evidence(args), 2)
                unchanged = controller.load_json(self.project / ".company-os" / "control.json")
                self.assertTrue(any(item["id"] == "commit-provenance" for item in unchanged["evidence"]["learning"]))

    def test_typed_git_commit_correction_clears_only_citing_quality_and_invalidates_readiness(self) -> None:
        _, artifact, args, _, _ = self.commit_correction_fixture()
        state = controller.load_json(self.project / ".company-os" / "control.json")
        checkpoint = controller.current_quality_checkpoint(state)[2]
        predecessor = next(item for item in state["evidence"]["learning"] if item["id"] == args.evidence_id)
        predecessor.update({
            "outcome_id": "cap-1", "work_id": "cap-1", "cycle_id": checkpoint,
            "rubric_version": "quality-v1",
        })
        quality_values = {
            "dimension": "evidence_integrity", "score": 9,
            "evidence_ids": [args.evidence_id], "rubric_version": "quality-v1",
            "scored_by": "commit-quality-scorer", "reviewed_by": "commit-quality-reviewer",
            "outcome_id": "cap-1", "work_id": "cap-1", "cycle_id": checkpoint,
            "artifact_digest": predecessor["artifact_sha256"],
        }
        payload_hash = controller.command_payload_hash(
            "score-quality", controller.quality_command_payload(quality_values)
        )
        scorer = self.grant(
            "commit-quality-scorer", "score-quality", resource="quality:evidence_integrity",
            work_id="cap-1", cycle_id=checkpoint, dimension="evidence_integrity",
            decision="score:9", payload_hash=payload_hash,
        )
        reviewer = self.grant(
            "commit-quality-reviewer", "score-quality-review", resource="quality:evidence_integrity",
            work_id="cap-1", cycle_id=checkpoint, dimension="evidence_integrity",
            decision="review:9", payload_hash=payload_hash,
        )
        state["quality"]["dimensions"]["evidence_integrity"].update({
            "score": 9, "evidence": [args.evidence_id], "rubric_version": "quality-v1",
            "scored_by": "commit-quality-scorer", "reviewed_by": "commit-quality-reviewer",
            "scorer_grant": self.grant_record(state, "commit-quality-scorer", scorer),
            "reviewer_grant": self.grant_record(state, "commit-quality-reviewer", reviewer),
            "binding": {
                "outcome_id": "cap-1", "work_id": "cap-1", "cycle_id": checkpoint,
                "artifact_digest": predecessor["artifact_sha256"], "rubric_version": "quality-v1",
            },
        })
        state["controller"]["validation"] = None
        state["controller"]["validated"] = False
        state["controller"]["schedule_enabled"] = False
        self.write_state(state)
        self.assertEqual(self.report(state)["errors"], [])

        review_payload = controller.correct_evidence_review_payload(
            args, predecessor=predecessor, replacement_id=args.id,
            replacement_digest=controller.sha256_file(artifact), bucket="learning",
            source_artifact_path=artifact.name,
        )
        correction_hash = controller.command_payload_hash("correct-evidence", review_payload)
        args.declarant_grant = self.grant(
            args.declarant, "correct-evidence-declare", resource=f"evidence:{args.evidence_id}",
            work_id="", cycle_id="", dimension="evidence", decision="proposed",
            payload_hash=correction_hash,
        )
        args.adjudicator_grant = self.grant(
            args.adjudicator, "correct-evidence-adjudicate", resource=f"evidence:{args.evidence_id}",
            work_id="", cycle_id="", dimension="evidence", decision="accepted",
            payload_hash=correction_hash,
        )
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.correct_evidence(args), 0)
        corrected = controller.load_json(self.project / ".company-os" / "control.json")
        cited = corrected["quality"]["dimensions"]["evidence_integrity"]
        unrelated = corrected["quality"]["dimensions"]["security"]
        self.assertIsNone(cited["score"])
        self.assertEqual(cited["evidence"], [])
        self.assertEqual(unrelated["score"], 9)
        self.assertFalse(corrected["controller"]["validated"])
        self.assertIsNone(corrected["controller"]["validation"])
        self.assertFalse(corrected["controller"]["schedule_enabled"])
        self.assertIn(
            "phase learning requires complete applicable quality evidence",
            self.report(corrected)["errors"],
        )

    def test_snapshot_evidence_remains_valid_when_descriptive_source_drifts(self) -> None:
        state = self.valid_state()
        state["instance"]["status"] = "paused"
        state["portfolio"]["active_work"] = []
        self.write_state(state)
        artifact = self.project / "snapshot-source.md"
        artifact.write_text("immutable source\n", encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.record_evidence(namespace(
                project=str(self.project), outcome="reality", artifact=artifact.name,
                source="test", decision_impact="test snapshot", author="author", reviewer="reviewer",
                freshness_days=30, quality_dimensions=[], outcome_id=None, work_id=None, cycle_id=None,
                rubric_version=None, id="snapshot-source",
            )), 0)
        artifact.write_text("drifted descriptive source\n", encoding="utf-8")
        recorded = controller.load_json(self.project / ".company-os" / "control.json")
        item = next(item for item in recorded["evidence"]["reality"] if item["id"] == "snapshot-source")
        self.assertTrue((self.project / item["snapshot_path"]).is_file())
        self.assertFalse(any("snapshot-source" in error for error in self.report(recorded)["errors"]))

    def test_inactive_evidence_cannot_remain_in_the_current_collection(self) -> None:
        state = self.valid_state()
        state["evidence"]["reality"][0]["active"] = False
        self.assertTrue(any(
            "inactive and must be retained only in archived evidence" in error
            for error in self.report(state)["errors"]
        ))

    def test_legacy_evidence_recovery_archives_and_replaces_same_bucket_index(self) -> None:
        state = self.valid_state()
        state["instance"]["status"] = "paused"
        state["portfolio"]["active_work"] = []
        legacy = state["evidence"]["reality"][0]
        legacy["id"] = "legacy-drift"
        legacy_path = self.project / legacy["artifact_path"]
        legacy_path.write_text("drifted legacy source\n", encoding="utf-8")
        self.write_state(state)
        args = self.supersession_args(state, "legacy-drift", legacy_path, "legacy-repaired")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.supersede_evidence(args), 0)
        repaired = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(repaired["evidence"]["reality"][0]["id"], "legacy-repaired")
        archived = repaired["feedback"]["archived_evidence"][-1]
        self.assertEqual(archived["record"]["id"], "legacy-drift")
        self.assertFalse(archived["old_snapshot_available"])
        self.assertEqual(repaired["evidence"]["reality"][0]["supersedes_evidence_id"], "legacy-drift")

    def test_snapshot_supersession_chain_retains_every_reviewed_transition(self) -> None:
        state = self.valid_state()
        state["instance"]["status"] = "paused"
        state["portfolio"]["active_work"] = []
        old = state["evidence"]["reality"][0]
        old["id"] = "chain-a"
        source = self.project / old["artifact_path"]
        source.write_text("chain b\n", encoding="utf-8")
        self.write_state(state)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                controller.supersede_evidence(
                    self.supersession_args(state, "chain-a", source, "chain-b")
                ),
                0,
            )
        state = controller.load_json(self.project / ".company-os" / "control.json")
        state["evidence"]["reality"][0]["observed_at"] = (
            datetime.now(timezone.utc) - timedelta(days=400)
        ).isoformat()
        source.write_text("chain c\n", encoding="utf-8")
        self.write_state(state)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                controller.supersede_evidence(
                    self.supersession_args(state, "chain-b", source, "chain-c")
                ),
                0,
            )
        repaired = controller.load_json(self.project / ".company-os" / "control.json")
        archives = {
            item["record"]["id"]: item
            for item in repaired["feedback"]["archived_evidence"]
            if item.get("archive_kind") == "evidence_supersession"
        }
        self.assertEqual(archives["chain-a"]["superseded_by_evidence_id"], "chain-b")
        self.assertEqual(archives["chain-b"]["superseded_by_evidence_id"], "chain-c")
        self.assertTrue(archives["chain-b"]["old_snapshot_available"])
        self.assertFalse(any("supersession" in error for error in self.report(repaired)["errors"]))

    def test_program_replacement_retains_valid_supersession_history(self) -> None:
        state = self.valid_state()
        state["instance"]["status"] = "paused"
        state["portfolio"]["active_work"] = []
        old = state["evidence"]["reality"][0]
        old["id"] = "replace-chain-a"
        source = self.project / old["artifact_path"]
        source.write_text("replacement chain\n", encoding="utf-8")
        self.write_state(state)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                controller.supersede_evidence(
                    self.supersession_args(state, "replace-chain-a", source, "replace-chain-b")
                ),
                0,
            )
            self.assertEqual(controller.replace_program(namespace(
                project=str(self.project), north_star="New mandate",
                current_outcome="New governed outcome", success_metric="One accepted result",
                reason="test replacement after supersession",
            )), 0)
        replaced = controller.load_json(self.project / ".company-os" / "control.json")
        errors = self.report(replaced)["errors"]
        self.assertEqual(errors, ["phase reality_audit requires valid evidence.reality"])

    def test_supersession_requires_an_exact_independent_grant(self) -> None:
        state = self.valid_state()
        state["instance"]["status"] = "paused"
        state["portfolio"]["active_work"] = []
        old = state["evidence"]["reality"][0]
        old["id"] = "grant-drift"
        source = self.project / old["artifact_path"]
        source.write_text("grant drift\n", encoding="utf-8")
        self.write_state(state)
        missing = self.supersession_args(
            state, "grant-drift", source, "grant-replacement", reviewer_grant=False
        )
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.supersede_evidence(missing), 2)
        valid = self.supersession_args(state, "grant-drift", source, "grant-replacement")
        valid.reviewer_grant = self.rewrite_grant(valid.reviewer_grant, decision="rejected")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.supersede_evidence(valid), 2)
        unchanged = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(unchanged["evidence"]["reality"][0]["id"], "grant-drift")
        self.assertEqual(unchanged["feedback"]["archived_evidence"], [])

    def test_supersession_refuses_unsafe_runtime_states_and_terminal_references(self) -> None:
        def attempt(mutator: object) -> None:
            state = self.valid_state()
            state["instance"]["status"] = "paused"
            state["portfolio"]["active_work"] = []
            old = state["evidence"]["reality"][0]
            old["id"] = "gated-drift"
            source = self.project / old["artifact_path"]
            source.write_text("gated drift\n", encoding="utf-8")
            mutator(state)
            self.write_state(state)
            args = self.supersession_args(
                state, "gated-drift", source, "gated-replacement", reviewer_grant=False
            )
            with redirect_stdout(io.StringIO()):
                self.assertEqual(controller.supersede_evidence(args), 2)
            retained = controller.load_json(self.project / ".company-os" / "control.json")
            self.assertEqual(retained["evidence"]["reality"][0]["id"], "gated-drift")

        gates = {
            "active instance": lambda state: state["instance"].update(status="active"),
            "enabled schedule": lambda state: state["controller"].update(schedule_enabled=True),
            "active lease": lambda state: state["controller"].update(lease={"lease_id": "held"}),
            "cancellation": lambda state: state["controller"].update(cancellation_requested=True),
            "running cycle": lambda state: state["feedback"]["cycles"].append(
                {"id": "running", "status": "running"}
            ),
            "completed reference": lambda state: state["feedback"]["cycles"].append(
                {"id": "done", "status": "completed", "evidence_ids": ["gated-drift"]}
            ),
            "accepted fabric reference": lambda state: state["execution_fabric"].update(
                status="accepted",
                managers={
                    "manager": {
                        "reports": [
                            {"report": {"evidence_ids": ["gated-drift"]}}
                        ]
                    }
                },
            ),
        }
        for label, mutator in gates.items():
            with self.subTest(label=label):
                attempt(mutator)

    def test_supersession_clears_only_quality_that_cites_the_predecessor(self) -> None:
        state = self.valid_state()
        state["instance"]["status"] = "paused"
        old = state["evidence"]["verification"][0]
        old["id"] = "quality-drift"
        for dimension in state["quality"]["dimensions"].values():
            dimension["evidence"] = ["quality-drift"]
        source = self.project / old["artifact_path"]
        source.write_text("updated quality evidence\n", encoding="utf-8")
        self.write_state(state)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                controller.supersede_evidence(
                    self.supersession_args(state, "quality-drift", source, "quality-repaired")
                ),
                0,
            )
        repaired = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertTrue(all(
            item["score"] is None and item["evidence"] == []
            for item in repaired["quality"]["dimensions"].values()
        ))
        self.assertFalse(self.report(repaired)["quality_ready"])

    def test_missing_or_corrupt_snapshot_fails_closed(self) -> None:
        state = self.valid_state()
        state["instance"]["status"] = "paused"
        state["portfolio"]["active_work"] = []
        self.write_state(state)
        source = self.project / "snapshot-integrity.md"
        source.write_text("trusted bytes\n", encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.record_evidence(namespace(
                project=str(self.project), outcome="reality", artifact=source.name,
                source="test", decision_impact="snapshot integrity", author="author",
                reviewer="reviewer", freshness_days=30, quality_dimensions=[],
                outcome_id=None, work_id=None, cycle_id=None, rubric_version=None,
                id="snapshot-integrity",
            )), 0)
        recorded = controller.load_json(self.project / ".company-os" / "control.json")
        item = next(
            item for item in recorded["evidence"]["reality"]
            if item["id"] == "snapshot-integrity"
        )
        snapshot = self.project / item["snapshot_path"]
        snapshot.write_text("substituted bytes\n", encoding="utf-8")
        self.assertTrue(any(
            "snapshot_sha256 does not match" in error
            for error in self.report(recorded)["errors"]
        ))
        snapshot.unlink()
        self.assertTrue(any(
            "snapshot_path does not exist" in error
            for error in self.report(recorded)["errors"]
        ))

    def test_noncritical_quality_must_reach_eight_and_phase_exit_requires_quality(self) -> None:
        state = self.valid_state()
        state["phase"] = "intelligence"
        state["quality"]["dimensions"]["counterevidence"]["score"] = 7.9
        report = self.report(state)
        self.assertIn("quality dimension counterevidence is below 8", report["errors"])

        state = self.valid_state()
        state["phase"] = "experience"
        state["instance"]["status"] = "paused"
        state["quality"]["dimensions"]["user_value"]["score"] = None
        self.write_state(state)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                controller.advance_phase(namespace(project=str(self.project), phase="delivery")),
                2,
            )
        retained = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(retained["phase"], "experience")

    def test_content_address_publish_is_replay_safe_and_never_overwrites(self) -> None:
        content = b"immutable evidence\n"
        digest = controller._bytes_sha256(content)
        first = controller.publish_evidence_snapshot(self.project, content, digest)
        second = controller.publish_evidence_snapshot(self.project, content, digest)
        self.assertEqual(first, second)
        target = self.project / first
        target.write_bytes(b"hostile substitution\n")
        with self.assertRaisesRegex(ValueError, "bytes do not match"):
            controller.publish_evidence_snapshot(self.project, content, digest)
        self.assertEqual(target.read_bytes(), b"hostile substitution\n")

    def test_failed_supersession_leaves_only_an_unauthoritative_orphan_snapshot(self) -> None:
        state = self.valid_state()
        state["instance"]["status"] = "paused"
        state["portfolio"]["active_work"] = []
        old = state["evidence"]["reality"][0]
        old["id"] = "still-valid"
        self.write_state(state)
        source = self.project / "unnecessary-replacement.md"
        source.write_text("new but unnecessary evidence\n", encoding="utf-8")
        args = self.supersession_args(state, "still-valid", source, "must-not-commit")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(controller.supersede_evidence(args), 2)
        retained = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(retained["evidence"]["reality"][0]["id"], "still-valid")
        self.assertFalse(any(
            item.get("id") == "must-not-commit"
            for bucket in retained["evidence"].values()
            for item in bucket
        ))
        digest = controller.sha256_file(source)
        self.assertTrue(controller.evidence_snapshot_path(self.project, digest).is_file())

    def assert_atomic_lease_rejection(self, transition: str, failure: str) -> None:
        state = self.valid_state()
        lease = {
            "lease_id": "matrix-lease", "owner": "matrix-owner", "generation": 1,
            "program_version": 1, "allowed_transitions": sorted(controller.LEASE_TRANSITIONS),
            "acquired_at": controller.utc_now(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        }
        if failure == "expired":
            lease["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        elif failure == "wrong-program":
            lease["program_version"] = 2
        elif failure == "wrong-owner":
            lease["owner"] = "other-owner"
        elif failure == "transition-not-permitted":
            lease["allowed_transitions"] = [item for item in sorted(controller.LEASE_TRANSITIONS) if item != transition]
        state["controller"].update({"lease_generation": 1, "lease": lease})
        self.write_state(state)
        report_path = self.project / "matrix-report.json"
        report_path.write_text("{}\n", encoding="utf-8")
        common = {"project": str(self.project), "lease_id": "matrix-lease", "generation": 1, "owner": "matrix-owner"}
        calls = {
            "begin-cycle": lambda: controller.begin_cycle(namespace(**common, work_id="cap-1", intended_outcome="matrix")),
            "finish-cycle": lambda: controller.finish_cycle(namespace(**common, cycle_id="matrix-cycle", actual_outcome="capability", evidence_ids=["delivery-1"], cost_usd=0.0, latency_minutes=0.0, token_usage=0, user_visible_movement="false", work_disposition="continue", reviewer_decision="accepted", reviewer="reviewer", reviewer_grant="", commit=None, ref=None)),
            "resolve-cycle": lambda: controller.resolve_cycle(namespace(**common, cycle_id="matrix-cycle", action="abandon", reason="matrix")),
            "release-lease": lambda: controller.release_lease(namespace(**common)),
            "record-fabric-phase": lambda: controller.record_fabric_phase(namespace(**common, manager_id="manager-a", report=report_path.name)),
            "decide-fabric-phase": lambda: controller.decide_fabric_phase(namespace(**common, manager_id="manager-a", decision="continue", decided_by="master", master_grant="")),
            "admit-runtime-attempt": lambda: controller.admit_runtime_attempt(namespace(
                **common, work_id="cap-1", cycle_id="matrix-cycle", attempt_id="matrix-attempt",
                manifest_identity_id="manager-a", parent_runtime_id="master", role="manager",
                requested_model="gpt-5.6-sol", provider="test", surface="local", account="test-account",
                scope='["src/workflow"]', budget='{}', fabric_manifest_digest="missing",
                contract_digest=controller.PHASE2_CONTRACT_DIGEST, idempotency_key="matrix-key",
                admitted_by="master", actor_grant="",
            )),
        }
        before = (self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()
        self.assertEqual(calls[transition](), 2)
        self.assertEqual(before, ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()))

    def admission_fixture(self) -> str:
        cycle_id = self.begin_fabric_fixture()
        state = controller.load_json(self.project / ".company-os" / "control.json")
        state["runtime_adapter"].update(
            {
                "enabled": True,
                "status": "enabled",
                "provider_allowlist": [{"provider": "codex", "surface": "desktop", "account": "test-account"}],
            }
        )
        self.write_state(state)
        return cycle_id

    def admission_args(
        self,
        running_cycle_id: str,
        *,
        role: str = "manager",
        attempt_id: str = "manager-attempt-1",
        idempotency_key: str = "manager-key-1",
        parent_runtime_id: str = "master",
        **overrides: object,
    ) -> object:
        state = controller.load_json(self.project / ".company-os" / "control.json")
        manifest = state["execution_fabric"]["manifest"]
        manager = manifest["managers"][0]
        identity = manager if role == "manager" else manager["workers"][0]
        values = {
            "project": str(self.project), "lease_id": "fabric-lease", "generation": 1, "owner": "master-sol",
            "work_id": "cap-1", "cycle_id": running_cycle_id, "attempt_id": attempt_id,
            "manifest_identity_id": identity["id"], "parent_runtime_id": parent_runtime_id,
            "role": role, "requested_model": identity["model"],
            "provider": "codex", "surface": "desktop", "account": "test-account",
            "scope": controller.canonical_json(identity["write_scope"]),
            "budget": controller.canonical_json(identity["budget"]),
            "fabric_manifest_digest": state["execution_fabric"]["manifest_digest"],
            "contract_digest": controller.PHASE2_CONTRACT_DIGEST,
            "idempotency_key": idempotency_key, "admitted_by": "master-reviewer",
        } | overrides
        args = namespace(**values)
        scope = json.loads(args.scope)
        budget = json.loads(args.budget)
        payload = controller.runtime_admission_payload(
            args, scope=controller.canonical_runtime_scopes(scope), budget=budget,
            lease=state["controller"]["lease"],
        )
        args.actor_grant = self.grant(
            "master-reviewer", "admit-runtime-attempt", resource=f"runtime:{args.attempt_id}",
            work_id=args.work_id, cycle_id=args.cycle_id, dimension="runtime-admission", decision="admitted",
            payload_hash=controller.command_payload_hash("admit-runtime-attempt", payload),
        )
        return args

    def test_runtime_admission_is_feature_off_and_rejections_are_atomic(self) -> None:
        cycle_id = self.begin_fabric_fixture()
        args = self.admission_args(cycle_id)
        before = ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes())
        self.assertEqual(controller.admit_runtime_attempt(args), 2)
        self.assertEqual(before, ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()))

    def test_runtime_admission_rejects_expired_untrusted_and_preconsumed_grants_atomically(self) -> None:
        cycle_id = self.admission_fixture()
        untrusted = self.admission_args(cycle_id)
        untrusted.actor_grant = self.rewrite_grant(
            untrusted.actor_grant,
            actor="not-the-admitter",
            nonce=controller.uuid.uuid4().hex,
        )
        expired = self.admission_args(cycle_id)
        expired.actor_grant = self.rewrite_grant(
            expired.actor_grant,
            expiry=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
            nonce=controller.uuid.uuid4().hex,
        )
        preconsumed = self.admission_args(cycle_id)
        encoded, _ = preconsumed.actor_grant.split(".", 1)
        grant_payload = json.loads(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        )
        state = controller.load_json(self.project / ".company-os" / "control.json")
        state["controller"]["consumed_grant_nonces"].append(grant_payload["nonce"])
        self.write_state(state)
        for args in (untrusted, expired, preconsumed):
            before = (
                (self.project / ".company-os" / "control.json").read_bytes(),
                (self.project / ".company-os" / "events.jsonl").read_bytes(),
            )
            self.assertEqual(controller.admit_runtime_attempt(args), 2)
            self.assertEqual(
                before,
                (
                    (self.project / ".company-os" / "control.json").read_bytes(),
                    (self.project / ".company-os" / "events.jsonl").read_bytes(),
                ),
            )
    def test_runtime_admission_binds_manager_worker_and_exact_retry(self) -> None:
        cycle_id = self.admission_fixture()
        manager = self.admission_args(cycle_id)
        self.assertEqual(controller.admit_runtime_attempt(manager), 0)
        admitted = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(admitted["runtime_adapter"]["attempts"][0]["attempt_id"], "manager-attempt-1")
        self.assertEqual(admitted["runtime_adapter"]["attempts"][0]["manifest_identity_id"], "manager-a")
        self.assertEqual(admitted["runtime_adapter"]["attempts"][0]["scope"], ["src/workflow"])
        retry_bytes = ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes())
        self.assertEqual(controller.admit_runtime_attempt(manager), 0)
        self.assertEqual(retry_bytes, ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()))
        worker = self.admission_args(
            cycle_id, role="worker", attempt_id="worker-attempt-1", idempotency_key="worker-key-1",
            parent_runtime_id="manager-attempt-1",
        )
        self.assertEqual(controller.admit_runtime_attempt(worker), 0)
        attempts = controller.load_json(self.project / ".company-os" / "control.json")["runtime_adapter"]["attempts"]
        self.assertEqual([(item["role"], item["parent_runtime_id"]) for item in attempts], [("manager", "master"), ("worker", "manager-attempt-1")])
        self.assertNotIn("PRIVATE", controller.canonical_json(attempts))

    def test_runtime_admission_audit_rebinds_retained_attempt_to_manifest_identity(self) -> None:
        cycle_id = self.admission_fixture()
        self.assertEqual(controller.admit_runtime_attempt(self.admission_args(cycle_id)), 0)
        state = controller.load_json(self.project / ".company-os" / "control.json")
        for field, value in (
            ("requested_model", "gpt-5.6-luna"),
            ("parent_runtime_id", "not-master"),
            ("scope", ["other"]),
            ("budget", {"time_minutes": 0}),
            ("manifest_identity_id", "unknown-manager"),
        ):
            tampered = deepcopy(state)
            tampered["runtime_adapter"]["attempts"][0][field] = value
            report = self.report(tampered)
            self.assertFalse(report["ok"], field)
            self.assertTrue(any("runtime attempt" in error or "manager runtime" in error for error in report["errors"]), report["errors"])

    def test_runtime_admission_refuses_to_build_on_corrupted_retained_state(self) -> None:
        cycle_id = self.admission_fixture()
        self.assertEqual(controller.admit_runtime_attempt(self.admission_args(cycle_id)), 0)
        baseline = controller.load_json(self.project / ".company-os" / "control.json")
        mutations = (
            lambda attempt: attempt.update({"requested_model": "gpt-5.6-luna"}),
            lambda attempt: attempt["actor_grant"].update({"token": "corrupted"}),
            lambda attempt: attempt.update({"lease_owner": "different-owner"}),
        )
        for mutation in mutations:
            state = deepcopy(baseline)
            mutation(state["runtime_adapter"]["attempts"][0])
            self.write_state(state)
            worker = self.admission_args(
                cycle_id,
                role="worker",
                attempt_id=f"worker-after-corruption-{controller.uuid.uuid4().hex}",
                idempotency_key=f"worker-after-corruption-{controller.uuid.uuid4().hex}",
                parent_runtime_id="manager-attempt-1",
            )
            before = (
                (self.project / ".company-os" / "control.json").read_bytes(),
                (self.project / ".company-os" / "events.jsonl").read_bytes(),
            )
            self.assertEqual(controller.admit_runtime_attempt(worker), 2)
            self.assertEqual(
                before,
                (
                    (self.project / ".company-os" / "control.json").read_bytes(),
                    (self.project / ".company-os" / "events.jsonl").read_bytes(),
                ),
            )

    def test_runtime_admission_rejects_grants_bindings_allowlists_scopes_budgets_and_conflicts_atomically(self) -> None:
        cycle_id = self.admission_fixture()
        malformed_grant = self.admission_args(cycle_id)
        malformed_grant.actor_grant = "malformed"
        aliased_scope = self.admission_args(cycle_id)
        aliased_scope.scope = '["src/workflow","SRC/WORKFLOW"]'
        cases = [
            malformed_grant,
            self.admission_args(cycle_id, attempt_id=""),
            self.admission_args(cycle_id, idempotency_key=""),
            self.admission_args(cycle_id, admitted_by=""),
            self.admission_args(cycle_id, provider="other"),
            self.admission_args(cycle_id, provider=" codex"),
            self.admission_args(cycle_id, scope='["src"]'),
            aliased_scope,
            self.admission_args(cycle_id, budget='{"cost_usd":0,"max_concurrency":0,"max_retries":0,"time_minutes":0,"token_limit":0}'),
            self.admission_args(cycle_id, fabric_manifest_digest="stale-manifest"),
            self.admission_args(cycle_id, contract_digest="stale-contract"),
            self.admission_args(cycle_id, work_id="stale-work"),
            self.admission_args(cycle_id, **{"cycle_id": "stale-cycle"}),
            self.admission_args(cycle_id, requested_model="gpt-5.6-luna"),
            self.admission_args(cycle_id, parent_runtime_id="not-master"),
            self.admission_args(cycle_id, role="invalid"),
            self.admission_args(cycle_id, role="worker", attempt_id="worker-before-parent", idempotency_key="worker-before-parent-key", parent_runtime_id="missing-manager"),
        ]
        for args in cases:
            before = ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes())
            self.assertEqual(controller.admit_runtime_attempt(args), 2)
            self.assertEqual(before, ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()))
        manager = self.admission_args(cycle_id)
        self.assertEqual(controller.admit_runtime_attempt(manager), 0)
        conflict_key = self.admission_args(cycle_id, attempt_id="manager-attempt-2", idempotency_key="manager-key-1")
        conflict_attempt = self.admission_args(cycle_id, attempt_id="manager-attempt-1", idempotency_key="manager-key-2")
        conflict_identity = self.admission_args(cycle_id, attempt_id="manager-attempt-2", idempotency_key="manager-key-2")
        for args in (conflict_key, conflict_attempt, conflict_identity):
            before = ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes())
            self.assertEqual(controller.admit_runtime_attempt(args), 2)
            self.assertEqual(before, ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()))

    def test_runtime_admission_rejects_internally_invalid_adapter_configuration_atomically(self) -> None:
        cycle_id = self.admission_fixture()
        baseline = controller.load_json(self.project / ".company-os" / "control.json")
        mutations = (
            lambda runtime: runtime.update({"status": "disabled"}),
            lambda runtime: runtime.update({"provider_allowlist": runtime["provider_allowlist"] * 2}),
            lambda runtime: runtime.update({"attempts": ["not-an-attempt"]}),
        )
        for mutation in mutations:
            state = deepcopy(baseline)
            mutation(state["runtime_adapter"])
            self.write_state(state)
            args = self.admission_args(cycle_id)
            before = (
                (self.project / ".company-os" / "control.json").read_bytes(),
                (self.project / ".company-os" / "events.jsonl").read_bytes(),
            )
            self.assertEqual(controller.admit_runtime_attempt(args), 2)
            self.assertEqual(
                before,
                (
                    (self.project / ".company-os" / "control.json").read_bytes(),
                    (self.project / ".company-os" / "events.jsonl").read_bytes(),
                ),
            )

    def test_cancel_command_revokes_lease_and_work(self) -> None:
        state = self.valid_state()
        state["controller"]["lease_generation"] = 1
        state["controller"]["lease"] = {
            "lease_id": "lease-1",
            "owner": "controller",
            "generation": 1,
            "program_version": 1,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        }
        self.write_state(state)
        result = controller.cancel_instance(
            namespace(project=str(self.project), reason="user correction")
        )
        self.assertEqual(result, 0)
        cancelled = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertIsNone(cancelled["controller"]["lease"])
        self.assertEqual(cancelled["portfolio"]["active_work"], [])
        self.assertEqual(cancelled["instance"]["status"], "cancelled")

    def test_replace_program_versions_and_clears_stale_state(self) -> None:
        state = self.valid_state()
        self.write_state(state)
        result = controller.replace_program(
            namespace(
                project=str(self.project),
                north_star="A new mandate",
                current_outcome="Run a new discovery",
                success_metric="One accepted prototype",
                reason="user changed direction",
            )
        )
        self.assertEqual(result, 0)
        replaced = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(replaced["strategy"]["program_version"], 2)
        self.assertEqual(replaced["portfolio"]["active_work"], [])
        self.assertTrue(replaced["portfolio"]["cancelled_work"])
        self.assertEqual(replaced["phase"], "reality_audit")
        self.assertEqual(replaced["instance"]["status"], "paused")
        self.assertIsNone(replaced["controller"]["restart_checkpoint"])
        self.assertEqual(replaced["runtime_adapter"], controller.empty_runtime_adapter(2))
        self.assertFalse(any("runtime_adapter belongs to a stale program" in error for error in self.report(replaced)["errors"]))

    def test_schema_eight_upgrade_archives_runtime_and_carries_no_attempt_forward(self) -> None:
        state = self.valid_state()
        state["schema_version"] = 8
        state["core_version"] = "2.5.0"
        state["runtime_adapter"] = {
            "enabled": True,
            "status": "enabled",
            "program_version": 1,
            "gateway_public_key_env": controller.RUNTIME_GATEWAY_PUBLIC_KEY_ENV,
            "phase2_contract_digest": controller.PHASE2_CONTRACT_DIGEST,
            "provider_allowlist": [{"provider": "legacy", "surface": "test", "account": "test"}],
            "attempts": [{"attempt_id": "legacy-attempt", "immutable": "legacy-record"}],
        }
        upgraded = controller.upgrade_state(state)
        self.assertEqual(upgraded["schema_version"], 9)
        self.assertEqual(upgraded["core_version"], "2.6.0")
        self.assertEqual(upgraded["runtime_adapter"], controller.empty_runtime_adapter(2))
        archived = upgraded["feedback"]["schema_upgrade_history"][-1]["runtime_adapter"]
        self.assertEqual(archived["attempts"], [{"attempt_id": "legacy-attempt", "immutable": "legacy-record"}])

    def test_schema_upgrade_restart_checkpoint_is_consumed_when_reality_is_evidenced(self) -> None:
        state = self.valid_state()
        state["schema_version"] = 8
        state["core_version"] = "2.5.0"
        upgraded = controller.upgrade_state(state)
        reality = self.evidence("reality")
        reality["program_version"] = upgraded["strategy"]["program_version"]
        upgraded["evidence"]["reality"] = [reality]
        intelligence = self.evidence("intelligence")
        intelligence["program_version"] = upgraded["strategy"]["program_version"]
        upgraded["evidence"]["intelligence"] = [intelligence]
        self.write_state(upgraded)
        self.assertEqual(
            controller.advance_phase(
                namespace(project=str(self.project), phase="intelligence")
            ),
            0,
        )
        advanced = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertIsNone(advanced["controller"]["restart_checkpoint"])
        report = self.report(advanced)
        self.assertFalse(any("restart_checkpoint" in error for error in report["errors"]), report["errors"])

    def test_upgrade_forward_from_chippi_v4_shape_preserves_monotonic_history(self) -> None:
        state = self.valid_state()
        state["schema_version"] = 4
        state["core_version"] = "2.1.0"
        state["strategy"]["program_version"] = 7
        state["strategy"]["program_fingerprint"] = controller.strategy_fingerprint(state["strategy"])
        state["controller"]["schedule_enabled"] = True
        state["controller"]["validated"] = True
        state["feedback"]["schema_upgrade_history"] = [{"id": "older-upgrade"}]
        state["portfolio"]["completed_work"] = [{"id": "completed-v4", "program_version": 7}]
        state["portfolio"]["cancelled_work"] = [{"id": "cancelled-v4", "program_version": 7}]
        state["feedback"]["cycles"] = [{"id": "cycle-v4", "program_version": 7, "status": "completed"}]
        old_active_work = deepcopy(state["portfolio"]["active_work"])
        old_completed_work = deepcopy(state["portfolio"]["completed_work"])
        old_cancelled_work = deepcopy(state["portfolio"]["cancelled_work"])
        old_evidence = deepcopy(state["evidence"])
        old_cycles = deepcopy(state["feedback"]["cycles"])
        self.write_state(state)
        self.assertEqual(controller.upgrade_instance(namespace(project=str(self.project))), 0)
        upgraded = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(upgraded["schema_version"], controller.SCHEMA_VERSION)
        self.assertEqual(upgraded["core_version"], controller.CORE_VERSION)
        self.assertEqual(upgraded["strategy"]["program_version"], 8)
        self.assertEqual(
            upgraded["strategy"]["program_fingerprint"],
            controller.strategy_fingerprint(upgraded["strategy"]),
        )
        self.assertEqual(upgraded["instance"]["status"], "paused")
        self.assertEqual(upgraded["phase"], "reality_audit")
        self.assertFalse(upgraded["controller"]["schedule_enabled"])
        self.assertIsNone(upgraded["controller"]["validation"])
        self.assertEqual(upgraded["portfolio"]["active_work"], [])
        self.assertEqual(upgraded["portfolio"]["committed_outcomes"], [])
        self.assertEqual(upgraded["portfolio"]["completed_work"], [])
        self.assertEqual(upgraded["portfolio"]["cancelled_work"], [])
        self.assertTrue(all(not items for items in upgraded["evidence"].values()))
        self.assertEqual(upgraded["feedback"]["cycles"], [])
        self.assertEqual(upgraded["controller"]["consumed_grant_nonces"], [])
        checkpoint = upgraded["controller"]["restart_checkpoint"]
        self.assertEqual(
            {
                "from_schema_version": checkpoint["from_schema_version"],
                "to_schema_version": checkpoint["to_schema_version"],
                "from_program_version": checkpoint["from_program_version"],
                "program_version": checkpoint["program_version"],
                "phase": checkpoint["phase"],
                "status": checkpoint["status"],
            },
            {
                "from_schema_version": 4,
                "to_schema_version": controller.SCHEMA_VERSION,
                "from_program_version": 7,
                "program_version": 8,
                "phase": "reality_audit",
                "status": "evidence_required",
            },
        )
        history = upgraded["feedback"]["schema_upgrade_history"]
        self.assertEqual(history[0], {"id": "older-upgrade"})
        archived = history[-1]
        self.assertEqual(archived["program_version"], 7)
        self.assertEqual(archived["next_program_version"], 8)
        self.assertEqual(archived["portfolio"]["active_work"], old_active_work)
        self.assertEqual(archived["portfolio"]["completed_work"], old_completed_work)
        self.assertEqual(archived["portfolio"]["cancelled_work"], old_cancelled_work)
        self.assertEqual(archived["evidence"], old_evidence)
        self.assertEqual(archived["feedback"]["cycles"], old_cycles)
        self.assertNotEqual(archived["id"], "completed-v4")
        report = self.report(upgraded)
        self.assertFalse(report["scheduler_ready"])
        self.assertFalse(
            any("restart_checkpoint" in error for error in report["errors"]),
            report["errors"],
        )

    def test_schema_six_upgrade_archives_unsigned_adaptations_fail_closed(self) -> None:
        state = self.valid_state()
        state["schema_version"] = 6
        state["core_version"] = "2.3.0"
        state["feedback"]["pending_adaptations"] = [{
            "id": "legacy-unsigned", "program_version": 1, "failure_pattern": "legacy",
            "hypothesis": "legacy", "experiment": "legacy", "success_metric": "legacy",
            "rollback": "legacy", "proposer": "legacy", "time_cap_minutes": 1,
            "cost_cap_usd": 0.0, "changes": ["review_cadence"], "meta_depth": 1,
            "status": "proposed", "proposed_at": controller.utc_now(),
        }]
        upgraded = controller.upgrade_state(state)
        self.assertEqual(upgraded["schema_version"], controller.SCHEMA_VERSION)
        self.assertEqual(upgraded["strategy"]["program_version"], 2)
        self.assertEqual(upgraded["feedback"]["pending_adaptations"], [])
        self.assertEqual(upgraded["feedback"]["schema_upgrade_history"][-1]["feedback"]["pending_adaptations"][0]["id"], "legacy-unsigned")

    def test_atomic_schedule_lease_cycle_and_release_lifecycle(self) -> None:
        state = self.valid_state()
        self.write_state(state)
        self.assertEqual(
            controller.set_schedule(namespace(project=str(self.project), enabled="true")),
            0,
        )
        self.assertEqual(
            controller.acquire_lease(
                namespace(project=str(self.project), owner="scheduler", ttl_seconds=300)
            ),
            0,
        )
        leased = controller.load_json(self.project / ".company-os" / "control.json")
        lease = leased["controller"]["lease"]
        self.assertEqual(
            controller.begin_cycle(
                namespace(
                    project=str(self.project),
                    lease_id=lease["lease_id"],
                    generation=lease["generation"],
                    work_id="cap-1",
                    intended_outcome="Deliver one inspectable capability",
                )
            ),
            0,
        )
        running = controller.load_json(self.project / ".company-os" / "control.json")
        cycle_id = running["feedback"]["cycles"][0]["id"]
        self.bind_delivery_evidence(cycle_id)
        self.assertEqual(
            controller.finish_cycle(
                namespace(
                    project=str(self.project),
                    lease_id=lease["lease_id"],
                    generation=lease["generation"],
                    cycle_id=cycle_id,
                    actual_outcome="capability",
                    evidence_ids=["delivery-1"],
                    cost_usd=1.0,
                    latency_minutes=5.0,
                    token_usage=100,
                    user_visible_movement="true",
                    work_disposition="continue",
                    reviewer_decision="accepted",
                    reviewer="cycle-reviewer",
                    reviewer_grant=self.finish_grant(
                        cycle_id=cycle_id, lease_id=lease["lease_id"], generation=lease["generation"],
                        disposition="continue", decision="accepted", visible="true",
                    ),
                    commit=None,
                    ref=None,
                )
            ),
            0,
        )
        self.assertEqual(
            controller.release_lease(
                namespace(
                    project=str(self.project),
                    lease_id=lease["lease_id"],
                    generation=lease["generation"],
                )
            ),
            0,
        )
        finished = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertFalse(finished["controller"]["schedule_enabled"])
        self.assertIsNone(finished["controller"]["validation"])
        self.assertIsNone(finished["controller"]["lease"])
        self.assertEqual(finished["feedback"]["cycles"][0]["status"], "completed")
        self.assertEqual(finished["portfolio"]["active_work"][0]["status"], "ready")
        self.rebind_quality(cycle_id)
        self.assertEqual(
            controller.certify_instance(
                namespace(
                    project=str(self.project),
                    reviewer="acceptance-reviewer",
                    reviewer_grant=self.grant(
                        "acceptance-reviewer", "certify", resource="certification", work_id="cap-1",
                        cycle_id=cycle_id, dimension="learning", decision="accepted",
                        payload_hash=controller.command_payload_hash(
                            "certify",
                            controller.certification_command_payload(
                                controller.load_json(self.project / ".company-os" / "control.json"),
                                "acceptance-reviewer",
                            ),
                        ),
                    ),
                )
            ),
            0,
        )
        self.assertEqual(controller.set_active_instance(namespace(project=str(self.project))), 0)
        self.assertEqual(
            controller.set_schedule(namespace(project=str(self.project), enabled="true")),
            0,
        )

    def test_finish_complete_archives_work_and_prevents_repeat(self) -> None:
        state = self.valid_state()
        self.write_state(state)
        self.assertEqual(controller.set_schedule(namespace(project=str(self.project), enabled="true")), 0)
        self.assertEqual(
            controller.acquire_lease(namespace(project=str(self.project), owner="scheduler", ttl_seconds=300)),
            0,
        )
        lease = controller.load_json(self.project / ".company-os" / "control.json")["controller"]["lease"]
        self.assertEqual(
            controller.begin_cycle(
                namespace(
                    project=str(self.project),
                    lease_id=lease["lease_id"],
                    generation=lease["generation"],
                    work_id="cap-1",
                    intended_outcome="Deliver one inspectable capability",
                )
            ),
            0,
        )
        cycle_id = controller.load_json(self.project / ".company-os" / "control.json")["feedback"]["cycles"][0]["id"]
        self.bind_delivery_evidence(cycle_id)
        self.assertEqual(
            controller.finish_cycle(
                namespace(
                    project=str(self.project),
                    lease_id=lease["lease_id"],
                    generation=lease["generation"],
                    cycle_id=cycle_id,
                    actual_outcome="capability",
                    evidence_ids=["delivery-1"],
                    cost_usd=1.0,
                    latency_minutes=5.0,
                    token_usage=100,
                    user_visible_movement="true",
                    work_disposition="complete",
                    reviewer_decision="accepted",
                    reviewer="cycle-reviewer",
                    reviewer_grant=self.finish_grant(
                        cycle_id=cycle_id, lease_id=lease["lease_id"], generation=lease["generation"],
                        disposition="complete", decision="accepted", visible="true",
                        commit="abc123", ref="refs/heads/main",
                    ),
                    commit="abc123",
                    ref="refs/heads/main",
                )
            ),
            0,
        )
        finished = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(finished["portfolio"]["active_work"], [])
        archived = finished["portfolio"]["completed_work"][0]
        self.assertEqual(archived["completion_cycle_id"], cycle_id)
        self.assertEqual(archived["completion"]["commit"], "abc123")
        self.assertEqual(archived["completion"]["reviewer_decision"], "accepted")
        self.assertEqual(archived["completion"]["reviewer"], "cycle-reviewer")
        self.assertIn("token", archived["completion"]["reviewer_grant"])
        self.assertEqual(finished["feedback"]["cycles"][0]["ref"], "refs/heads/main")
        self.assertTrue(self.report(finished)["ok"], self.report(finished)["errors"])
        self.assertEqual(
            controller.begin_cycle(
                namespace(
                    project=str(self.project),
                    lease_id=lease["lease_id"],
                    generation=lease["generation"],
                    work_id="cap-1",
                    intended_outcome="Repeat completed work",
                )
            ),
            2,
        )
        retry = dict(
            project=str(self.project), id="cap-retry", type="capability", title="  INTEGRATED—WORKSPACE! ",
            user_visible_outcome="a USER completes one new WORKFLOW...", claimed_progress="capability",
            owner="retry-owner", primary="false", unlocks=[], outcome_id="cap-1",
            incident_ref=None, severity=None, justification=None, incident_actor=None, incident_grant=None,
            approval_actor=None, approval_grant=None,
        )
        self.assertEqual(
            controller.queue_work(
                namespace(**retry, repeat_override_reason=None, repeat_override_reviewer=None, repeat_override_grant=None)
            ),
            2,
        )
        retry_fingerprint = controller.work_fingerprint(retry)
        override_values = {
            **retry,
            "repeat_override_reason": "New customer cohort and changed acceptance evidence",
            "repeat_override_reviewer": "repeat-reviewer",
        }
        override = self.grant(
            "repeat-reviewer", "repeat-override", resource=retry_fingerprint, work_id="cap-retry",
            cycle_id="prequeue", dimension="semantic-repeat", decision="accepted",
            payload_hash=controller.command_payload_hash(
                "queue-work",
                controller.queue_command_payload({**override_values, "primary": "true"}),
            ),
        )
        self.assertEqual(
            controller.queue_work(
                namespace(
                    **override_values,
                    repeat_override_grant=override,
                )
            ),
            0,
        )

    def test_rejected_review_cannot_complete_work(self) -> None:
        state = self.valid_state()
        self.write_state(state)
        self.assertEqual(controller.set_schedule(namespace(project=str(self.project), enabled="true")), 0)
        self.assertEqual(
            controller.acquire_lease(namespace(project=str(self.project), owner="scheduler", ttl_seconds=300)),
            0,
        )
        lease = controller.load_json(self.project / ".company-os" / "control.json")["controller"]["lease"]
        self.assertEqual(
            controller.begin_cycle(
                namespace(
                    project=str(self.project),
                    lease_id=lease["lease_id"],
                    generation=lease["generation"],
                    work_id="cap-1",
                    intended_outcome="Deliver one inspectable capability",
                )
            ),
            0,
        )
        cycle_id = controller.load_json(self.project / ".company-os" / "control.json")["feedback"]["cycles"][0]["id"]
        self.bind_delivery_evidence(cycle_id)
        self.assertEqual(
            controller.finish_cycle(
                namespace(
                    project=str(self.project),
                    lease_id=lease["lease_id"],
                    generation=lease["generation"],
                    cycle_id=cycle_id,
                    actual_outcome="capability",
                    evidence_ids=["delivery-1"],
                    cost_usd=1.0,
                    latency_minutes=5.0,
                    token_usage=100,
                    user_visible_movement="false",
                    work_disposition="complete",
                    reviewer_decision="rejected",
                    reviewer="cycle-reviewer",
                    reviewer_grant=self.finish_grant(
                        cycle_id=cycle_id, lease_id=lease["lease_id"], generation=lease["generation"],
                        disposition="complete", decision="rejected", visible="false",
                    ),
                    commit=None,
                    ref=None,
                )
            ),
            2,
        )
        rejected = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(rejected["feedback"]["cycles"][0]["status"], "running")
        self.assertEqual(rejected["portfolio"]["active_work"][0]["status"], "running")

    def test_finish_rejects_forged_reviewer_grant_and_tampered_evidence(self) -> None:
        self.write_state(self.valid_state())
        self.assertEqual(controller.set_schedule(namespace(project=str(self.project), enabled="true")), 0)
        self.assertEqual(controller.acquire_lease(namespace(project=str(self.project), owner="scheduler", ttl_seconds=300)), 0)
        lease = controller.load_json(self.project / ".company-os" / "control.json")["controller"]["lease"]
        self.assertEqual(
            controller.begin_cycle(namespace(project=str(self.project), lease_id=lease["lease_id"], generation=lease["generation"], work_id="cap-1", intended_outcome="Deliver capability")),
            0,
        )
        cycle_id = controller.load_json(self.project / ".company-os" / "control.json")["feedback"]["cycles"][0]["id"]
        self.bind_delivery_evidence(cycle_id)
        finish_args = dict(
            project=str(self.project), lease_id=lease["lease_id"], generation=lease["generation"], cycle_id=cycle_id,
            actual_outcome="capability", evidence_ids=["delivery-1"], cost_usd=1.0, latency_minutes=1.0,
            token_usage=1, user_visible_movement="true", work_disposition="complete", reviewer_decision="accepted",
            reviewer="cycle-reviewer", commit=None, ref=None,
        )
        self.assertEqual(controller.finish_cycle(namespace(**finish_args, reviewer_grant="forged")), 2)
        (self.project / "delivery.md").write_text("tampered", encoding="utf-8")
        self.assertEqual(
            controller.finish_cycle(
                namespace(
                    **finish_args,
                    reviewer_grant=self.finish_grant(
                        cycle_id=cycle_id, lease_id=lease["lease_id"], generation=lease["generation"],
                        disposition="complete", decision="accepted", visible="true", cost=1.0, latency=1.0, tokens=1,
                    ),
                )
            ),
            2,
        )

    def test_certifier_cannot_be_any_involved_actor(self) -> None:
        self.write_state(self.valid_state())
        self.assertEqual(
            controller.certify_instance(
                namespace(
                    project=str(self.project),
                    reviewer="quality-scorer",
                    reviewer_grant=self.grant(
                        "quality-scorer", "certify", resource="certification", work_id="cap-1",
                        cycle_id=controller.current_quality_checkpoint(self.valid_state())[2], dimension="learning", decision="accepted",
                        payload_hash=controller.command_payload_hash(
                            "certify",
                            controller.certification_command_payload(
                                controller.load_json(self.project / ".company-os" / "control.json"),
                                "quality-scorer",
                            ),
                        ),
                    ),
                )
            ),
            2,
        )

    def test_semantic_repeat_and_unapproved_p0_are_rejected(self) -> None:
        self.write_state(self.valid_state())
        repeat = namespace(
            project=str(self.project), id="cap-repeat", type="capability", title="Integrated workspace",
            user_visible_outcome="A user completes one new workflow", claimed_progress="capability", owner="other-owner",
            primary="false", unlocks=[], outcome_id="cap-1", incident_ref=None, severity=None, justification=None,
            incident_actor=None, incident_grant=None, approval_actor=None, approval_grant=None,
            repeat_override_reason=None, repeat_override_reviewer=None, repeat_override_grant=None,
        )
        self.assertEqual(controller.queue_work(repeat), 2)
        p0 = namespace(
            project=str(self.project), id="p0-1", type="p0", title="Incident", user_visible_outcome="Restore users",
            claimed_progress="learning", owner="incident-owner", primary="true", unlocks=[], outcome_id=None,
            incident_ref=None, severity=None, justification=None, incident_actor=None, incident_grant=None,
            approval_actor=None, approval_grant=None, repeat_override_reason=None, repeat_override_reviewer=None,
            repeat_override_grant=None,
        )
        self.assertEqual(controller.queue_work(p0), 2)

    def test_p0_requires_asymmetric_incident_and_independent_approval_grants(self) -> None:
        self.write_state(self.valid_state())
        queue_values = {
            "id": "p0-42", "type": "p0", "title": "Restore access",
            "user_visible_outcome": "Customers regain access", "claimed_progress": "learning",
            "owner": "incident-owner", "primary": "true", "unlocks": [], "outcome_id": None,
            "incident_ref": "INC-42", "severity": "P0", "justification": "Active customer outage",
            "incident_actor": "incident-commander", "approval_actor": "safety-approver",
            "repeat_override_reason": None, "repeat_override_reviewer": None,
        }
        payload_hash = controller.command_payload_hash("queue-work", controller.queue_command_payload(queue_values))
        incident = self.grant(
            "incident-commander", "p0-incident", resource="INC-42", work_id="p0-42",
            cycle_id="precycle", dimension="p0", decision="P0", payload_hash=payload_hash,
        )
        approval = self.grant(
            "safety-approver", "p0-approve", resource="INC-42", work_id="p0-42",
            cycle_id="precycle", dimension="p0", decision="approved", payload_hash=payload_hash,
        )
        result = controller.queue_work(
            namespace(
                project=str(self.project), **queue_values, incident_grant=incident,
                approval_grant=approval, repeat_override_grant=None,
            )
        )
        self.assertEqual(result, 0)
        queued = controller.load_json(self.project / ".company-os" / "control.json")
        p0 = next(item for item in queued["portfolio"]["active_work"] if item["id"] == "p0-42")
        self.assertIn("token", p0["incident_grant"])
        self.assertIn("token", p0["approval"]["grant"])

    def test_running_cycle_requires_explicit_abandon_before_release(self) -> None:
        self.write_state(self.valid_state())
        self.assertEqual(controller.set_schedule(namespace(project=str(self.project), enabled="true")), 0)
        self.assertEqual(controller.acquire_lease(namespace(project=str(self.project), owner="scheduler", ttl_seconds=300)), 0)
        lease = controller.load_json(self.project / ".company-os" / "control.json")["controller"]["lease"]
        self.assertEqual(
            controller.begin_cycle(namespace(project=str(self.project), lease_id=lease["lease_id"], generation=lease["generation"], work_id="cap-1", intended_outcome="Deliver capability")),
            0,
        )
        cycle_id = controller.load_json(self.project / ".company-os" / "control.json")["feedback"]["cycles"][0]["id"]
        self.assertEqual(controller.release_lease(namespace(project=str(self.project), lease_id=lease["lease_id"], generation=lease["generation"])), 2)
        self.assertEqual(
            controller.resolve_cycle(
                namespace(project=str(self.project), lease_id=lease["lease_id"], generation=lease["generation"], cycle_id=cycle_id, action="abandon", reason="operator recovery")
            ),
            0,
        )
        self.assertEqual(controller.release_lease(namespace(project=str(self.project), lease_id=lease["lease_id"], generation=lease["generation"])), 0)
        abandoned = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(abandoned["feedback"]["cycles"][0]["status"], "abandoned")
        self.assertTrue(self.report(abandoned)["ok"], self.report(abandoned)["errors"])

    def test_expired_running_cycle_can_only_receive_a_recovery_lease(self) -> None:
        self.write_state(self.valid_state())
        self.assertEqual(controller.set_schedule(namespace(project=str(self.project), enabled="true")), 0)
        self.assertEqual(controller.acquire_lease(namespace(project=str(self.project), owner="scheduler", ttl_seconds=300)), 0)
        original = controller.load_json(self.project / ".company-os" / "control.json")["controller"]["lease"]
        self.assertEqual(
            controller.begin_cycle(namespace(project=str(self.project), lease_id=original["lease_id"], generation=original["generation"], work_id="cap-1", intended_outcome="Deliver capability")),
            0,
        )
        state = controller.load_json(self.project / ".company-os" / "control.json")
        state["controller"]["lease"]["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        controller.atomic_write_json(self.project / ".company-os" / "control.json", state)
        self.assertEqual(controller.acquire_lease(namespace(project=str(self.project), owner="recovery", ttl_seconds=300)), 0)
        recovered = controller.load_json(self.project / ".company-os" / "control.json")
        lease = recovered["controller"]["lease"]
        cycle_id = recovered["feedback"]["cycles"][0]["id"]
        self.assertNotEqual(lease["lease_id"], original["lease_id"])
        self.assertEqual(
            controller.resolve_cycle(
                namespace(project=str(self.project), lease_id=lease["lease_id"], generation=lease["generation"], owner="recovery", cycle_id=cycle_id, action="recover", reason="expired scheduler")
            ),
            0,
        )
        recovered = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(recovered["feedback"]["cycles"][0]["lease_id"], lease["lease_id"])
        self.assertTrue(self.report(recovered)["ok"], self.report(recovered)["errors"])

    def test_recovery_lease_cannot_release_an_inherited_running_cycle(self) -> None:
        self.write_state(self.valid_state())
        self.assertEqual(controller.set_schedule(namespace(project=str(self.project), enabled="true")), 0)
        self.assertEqual(controller.acquire_lease(namespace(project=str(self.project), owner="scheduler", ttl_seconds=300)), 0)
        original = controller.load_json(self.project / ".company-os" / "control.json")["controller"]["lease"]
        self.assertEqual(controller.begin_cycle(namespace(project=str(self.project), lease_id=original["lease_id"], generation=original["generation"], owner="scheduler", work_id="cap-1", intended_outcome="Deliver capability")), 0)
        state = controller.load_json(self.project / ".company-os" / "control.json")
        state["controller"]["lease"]["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        controller.atomic_write_json(self.project / ".company-os" / "control.json", state)
        self.assertEqual(controller.acquire_lease(namespace(project=str(self.project), owner="recovery", ttl_seconds=300)), 0)
        recovery = controller.load_json(self.project / ".company-os" / "control.json")["controller"]["lease"]
        before = (self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()
        self.assertEqual(controller.release_lease(namespace(project=str(self.project), lease_id=recovery["lease_id"], generation=recovery["generation"], owner="recovery")), 2)
        self.assertEqual(before, ((self.project / ".company-os" / "control.json").read_bytes(), (self.project / ".company-os" / "events.jsonl").read_bytes()))
        cycle_id = state["feedback"]["cycles"][0]["id"]
        self.assertEqual(controller.resolve_cycle(namespace(project=str(self.project), lease_id=recovery["lease_id"], generation=recovery["generation"], owner="recovery", cycle_id=cycle_id, action="abandon", reason="explicit recovery")), 0)
        self.assertEqual(controller.release_lease(namespace(project=str(self.project), lease_id=recovery["lease_id"], generation=recovery["generation"], owner="recovery")), 0)

    def test_failed_cycle_persists_an_auditable_blocked_state(self) -> None:
        self.write_state(self.valid_state())
        self.assertEqual(controller.set_schedule(namespace(project=str(self.project), enabled="true")), 0)
        self.assertEqual(controller.acquire_lease(namespace(project=str(self.project), owner="scheduler", ttl_seconds=300)), 0)
        lease = controller.load_json(self.project / ".company-os" / "control.json")["controller"]["lease"]
        self.assertEqual(
            controller.begin_cycle(namespace(project=str(self.project), lease_id=lease["lease_id"], generation=lease["generation"], work_id="cap-1", intended_outcome="Deliver capability")),
            0,
        )
        cycle_id = controller.load_json(self.project / ".company-os" / "control.json")["feedback"]["cycles"][0]["id"]
        self.assertEqual(
            controller.resolve_cycle(
                namespace(project=str(self.project), lease_id=lease["lease_id"], generation=lease["generation"], cycle_id=cycle_id, action="fail", reason="provider failure")
            ),
            0,
        )
        failed = controller.load_json(self.project / ".company-os" / "control.json")
        self.assertEqual(failed["feedback"]["cycles"][0]["status"], "failed")
        self.assertEqual(failed["portfolio"]["active_work"][0]["status"], "blocked")
        self.assertTrue(self.report(failed)["ok"], self.report(failed)["errors"])

    def test_governance_digest_changes_for_governable_state(self) -> None:
        state = self.valid_state()
        baseline = controller.governance_digest(state)
        state["portfolio"]["active_work"][0]["title"] = "A materially changed capability"
        self.assertNotEqual(baseline, controller.governance_digest(state))

    def test_quality_score_requires_signed_actor_and_exact_binding(self) -> None:
        state = self.valid_state()
        checkpoint = controller.current_quality_checkpoint(state)[2]
        self.write_state(state)
        arguments = dict(
            project=str(self.project), dimension="user_value", score=9.0, evidence_ids=["verification-1"],
            rubric_version="quality-v1", scored_by="new-scorer", reviewed_by="new-reviewer",
            outcome_id="cap-1", work_id="cap-1", cycle_id=checkpoint,
            artifact_digest=controller.sha256_file(self.project / "verification.md"),
        )
        quality_payload_hash = controller.command_payload_hash(
            "score-quality", controller.quality_command_payload(arguments)
        )
        self.assertEqual(
            controller.score_quality(
                namespace(
                    **arguments,
                    scored_by_grant="forged",
                    reviewed_by_grant=self.grant(
                        "new-reviewer", "score-quality-review", resource="quality:user_value", work_id="cap-1",
                        cycle_id=checkpoint, dimension="user_value", decision="review:9.0", payload_hash=quality_payload_hash,
                    ),
                )
            ),
            2,
        )
        signed_arguments = namespace(
            **arguments,
            scored_by_grant=self.grant(
                "new-scorer", "score-quality", resource="quality:user_value", work_id="cap-1",
                cycle_id=checkpoint, dimension="user_value", decision="score:9.0", payload_hash=quality_payload_hash,
            ),
            reviewed_by_grant=self.grant(
                "new-reviewer", "score-quality-review", resource="quality:user_value", work_id="cap-1",
                cycle_id=checkpoint, dimension="user_value", decision="review:9.0", payload_hash=quality_payload_hash,
            ),
        )
        self.assertEqual(controller.score_quality(signed_arguments), 0)
        self.assertEqual(controller.score_quality(signed_arguments), 2)

    def test_quality_score_binds_complete_multi_artifact_evidence_set(self) -> None:
        state = self.valid_state()
        checkpoint = controller.current_quality_checkpoint(state)[2]
        second_artifact = self.project / "verification-second.md"
        second_artifact.write_text("# independent runtime evidence\nverified second source\n", encoding="utf-8")
        second = deepcopy(state["evidence"]["verification"][0])
        second.update(
            {
                "id": "verification-2",
                "artifact_path": second_artifact.name,
                "artifact_sha256": controller.sha256_file(second_artifact),
                "author": "second-evidence-author",
                "reviewer": "second-evidence-reviewer",
            }
        )
        state["evidence"]["verification"].append(second)
        state["controller"]["validation"] = None
        state["controller"]["validated"] = False
        evidence_ids = ["verification-2", "verification-1"]
        evidence_digest = controller.completion_evidence_digest(state, evidence_ids)
        self.write_state(state)
        arguments = dict(
            project=str(self.project), dimension="user_value", score=9.0,
            evidence_ids=evidence_ids, rubric_version="quality-v1",
            scored_by="set-scorer", reviewed_by="set-reviewer",
            outcome_id="cap-1", work_id="cap-1", cycle_id=checkpoint,
            evidence_digest=evidence_digest, artifact_digest=None,
        )
        payload_hash = controller.command_payload_hash(
            "score-quality", controller.quality_command_payload(arguments)
        )
        signed = namespace(
            **arguments,
            scored_by_grant=self.grant(
                "set-scorer", "score-quality", resource="quality:user_value",
                work_id="cap-1", cycle_id=checkpoint, dimension="user_value",
                decision="score:9.0", payload_hash=payload_hash,
            ),
            reviewed_by_grant=self.grant(
                "set-reviewer", "score-quality-review", resource="quality:user_value",
                work_id="cap-1", cycle_id=checkpoint, dimension="user_value",
                decision="review:9.0", payload_hash=payload_hash,
            ),
        )
        self.assertEqual(controller.score_quality(signed), 0)
        recorded = controller.load_json(self.project / ".company-os" / "control.json")
        binding = recorded["quality"]["dimensions"]["user_value"]["binding"]
        self.assertEqual(
            recorded["quality"]["dimensions"]["user_value"]["evidence"],
            ["verification-1", "verification-2"],
        )
        self.assertEqual(binding["evidence_digest"], evidence_digest)
        self.assertNotIn("artifact_digest", binding)
        self.assertFalse(any(
            "quality dimension user_value" in error
            for error in self.report(recorded)["errors"]
        ))

        tampered = deepcopy(recorded)
        tampered["quality"]["dimensions"]["user_value"]["binding"]["evidence_digest"] = "0" * 64
        self.assertIn(
            "quality dimension user_value evidence digest does not match its evidence set",
            self.report(tampered)["errors"],
        )

        duplicate_args = dict(arguments)
        duplicate_args["evidence_ids"] = ["verification-1", "verification-1"]
        duplicate_args["evidence_digest"] = controller.completion_evidence_digest(
            recorded, duplicate_args["evidence_ids"]
        )
        duplicate_hash = controller.command_payload_hash(
            "score-quality", controller.quality_command_payload(duplicate_args)
        )
        self.assertEqual(
            controller.score_quality(namespace(
                **duplicate_args,
                scored_by_grant=self.grant(
                    "duplicate-scorer", "score-quality", resource="quality:user_value",
                    work_id="cap-1", cycle_id=checkpoint, dimension="user_value",
                    decision="score:9.0", payload_hash=duplicate_hash,
                ),
                reviewed_by_grant=self.grant(
                    "duplicate-reviewer", "score-quality-review", resource="quality:user_value",
                    work_id="cap-1", cycle_id=checkpoint, dimension="user_value",
                    decision="review:9.0", payload_hash=duplicate_hash,
                ),
            )),
            2,
        )

    def test_certification_grant_cannot_be_substituted_across_governance_digests(self) -> None:
        state = self.valid_state()
        state["controller"]["validation"] = None
        state["controller"]["validated"] = False
        _, work_id, checkpoint = controller.current_quality_checkpoint(state)
        token = self.grant(
            "fresh-certifier",
            "certify",
            resource="certification",
            work_id=work_id,
            cycle_id=checkpoint,
            dimension="learning",
            decision="accepted",
            payload_hash=controller.command_payload_hash(
                "certify",
                controller.certification_command_payload(state, "fresh-certifier"),
            ),
        )
        state["strategy"]["constraints"].append("No export outside the governed boundary")
        state["strategy"]["program_fingerprint"] = controller.strategy_fingerprint(state["strategy"])
        self.write_state(state)
        self.assertEqual(
            controller.certify_instance(
                namespace(
                    project=str(self.project),
                    reviewer="fresh-certifier",
                    reviewer_grant=token,
                )
            ),
            2,
        )

    def test_finish_grant_binds_every_completion_decision_field(self) -> None:
        cycle_id = "cycle-substitution"
        lease_id = "lease-substitution"
        generation = 1
        base = {
            "project": str(self.project),
            "cycle_id": cycle_id,
            "lease_id": lease_id,
            "generation": generation,
            "actual_outcome": "capability",
            "evidence_ids": ["delivery-1"],
            "cost_usd": 1.0,
            "latency_minutes": 5.0,
            "token_usage": 100,
            "user_visible_movement": "true",
            "work_disposition": "continue",
            "reviewer_decision": "accepted",
            "reviewer": "cycle-reviewer",
            "commit": "abc123",
            "ref": "refs/heads/main",
        }
        substitutions = {
            "evidence_ids": ["delivery-1", "verification-1"],
            "actual_outcome": "learning",
            "cost_usd": 2.0,
            "latency_minutes": 6.0,
            "token_usage": 101,
            "user_visible_movement": "false",
            "work_disposition": "complete",
            "reviewer_decision": "rejected",
            "reviewer": "substitute-reviewer",
            "commit": "def456",
            "ref": "refs/heads/substitute",
        }
        for field, substitute in substitutions.items():
            with self.subTest(field=field):
                state = self.running_finish_state()
                token = self.grant(
                    "cycle-reviewer",
                    "finish-cycle",
                    resource=f"cycle:{cycle_id}",
                    work_id="cap-1",
                    cycle_id=cycle_id,
                    dimension="completion",
                    decision="accepted:continue",
                    payload_hash=controller.command_payload_hash(
                        "finish-cycle",
                        controller.finish_command_payload(state, base),
                    ),
                )
                self.write_state(state)
                changed = {**base, field: substitute, "reviewer_grant": token}
                self.assertEqual(controller.finish_cycle(namespace(**changed)), 2)

        state = self.running_finish_state()
        token = self.grant(
            "cycle-reviewer",
            "finish-cycle",
            resource=f"cycle:{cycle_id}",
            work_id="cap-1",
            cycle_id=cycle_id,
            dimension="completion",
            decision="accepted:continue",
            payload_hash=controller.command_payload_hash(
                "finish-cycle",
                controller.finish_command_payload(state, base),
            ),
        )
        state["evidence"]["delivery"][0]["artifact_sha256"] = "0" * 64
        self.write_state(state)
        self.assertEqual(
            controller.finish_cycle(namespace(**base, reviewer_grant=token)),
            2,
        )

    def test_missing_or_malformed_governance_grants_return_controlled_rc2(self) -> None:
        state = self.valid_state()
        state["controller"]["validation"] = None
        state["controller"]["validated"] = False
        checkpoint = controller.current_quality_checkpoint(state)[2]
        self.write_state(state)
        self.assertEqual(
            controller.certify_instance(
                namespace(
                    project=str(self.project),
                    reviewer="fresh-certifier",
                    reviewer_grant=None,
                )
            ),
            2,
        )
        self.assertEqual(
            controller.score_quality(
                namespace(
                    project=str(self.project),
                    dimension="user_value",
                    score=9.0,
                    evidence_ids=["verification-1"],
                    rubric_version="quality-v1",
                    scored_by="new-scorer",
                    reviewed_by="new-reviewer",
                    outcome_id="cap-1",
                    work_id="cap-1",
                    cycle_id=checkpoint,
                    artifact_digest=controller.sha256_file(self.project / "verification.md"),
                    scored_by_grant=None,
                    reviewed_by_grant="malformed",
                )
            ),
            2,
        )

        finish_state = self.running_finish_state()
        self.write_state(finish_state)
        self.assertEqual(
            controller.finish_cycle(
                namespace(
                    project=str(self.project),
                    cycle_id="cycle-substitution",
                    lease_id="lease-substitution",
                    generation=1,
                    actual_outcome="capability",
                    evidence_ids=["delivery-1"],
                    cost_usd=1.0,
                    latency_minutes=5.0,
                    token_usage=100,
                    user_visible_movement="true",
                    work_disposition="continue",
                    reviewer_decision="accepted",
                    reviewer="cycle-reviewer",
                    reviewer_grant=None,
                    commit=None,
                    ref=None,
                )
            ),
            2,
        )

        self.write_state(self.valid_state())
        self.assertEqual(
            controller.queue_work(
                namespace(
                    project=str(self.project),
                    id="p0-missing-grants",
                    type="p0",
                    title="Contain a production incident",
                    user_visible_outcome="Customer impact is contained",
                    claimed_progress="learning",
                    owner="incident-owner",
                    primary="true",
                    unlocks=[],
                    outcome_id=None,
                    incident_ref="INC-404",
                    severity="P0",
                    justification="Active customer impact",
                    incident_actor="incident-commander",
                    incident_grant=None,
                    approval_actor="incident-approver",
                    approval_grant="malformed",
                    repeat_override_reason=None,
                    repeat_override_reviewer=None,
                    repeat_override_grant=None,
                )
            ),
            2,
        )


def _lease_matrix_test(transition: str, failure: str):
    def test(self: ControllerTests) -> None:
        self.assert_atomic_lease_rejection(transition, failure)
    test.__name__ = f"test_lease_{transition.replace('-', '_')}_{failure.replace('-', '_')}_is_atomic"
    return test


for _transition in sorted(controller.LEASE_TRANSITIONS):
    for _failure in ("expired", "wrong-program", "wrong-owner", "transition-not-permitted"):
        setattr(ControllerTests, f"test_lease_{_transition.replace('-', '_')}_{_failure.replace('-', '_')}_is_atomic", _lease_matrix_test(_transition, _failure))


if __name__ == "__main__":
    unittest.main()
