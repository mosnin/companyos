from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KERNEL_SKILL = ROOT / "skills" / "company-os" / "compile-federated-company-kernel"
BRIDGE_SKILL = ROOT / "skills" / "company-os" / "operate-federated-codex-runtime"
KERNEL_PATH = KERNEL_SKILL / "scripts" / "compile_federated_kernel.py"
RECONCILE_PATH = KERNEL_SKILL / "scripts" / "reconcile_federated_kernel.py"
POSTGRES_PATH = KERNEL_SKILL / "scripts" / "postgres_federated_runtime.py"
BRIDGE_PATH = BRIDGE_SKILL / "scripts" / "prepare_native_codex_dispatch.py"
EXAMPLE = KERNEL_SKILL / "references" / "federated-kernel-request.example.json"
BINDING_EXAMPLE = BRIDGE_SKILL / "references" / "native-host-binding.example.json"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


KERNEL = load("native_bridge_kernel_tests", KERNEL_PATH)
RECONCILE = load("native_bridge_reconcile_tests", RECONCILE_PATH)
POSTGRES = load("native_bridge_postgres_tests", POSTGRES_PATH)
BRIDGE = load("native_codex_dispatch_bridge_tests", BRIDGE_PATH)


def compiled_kernel() -> dict:
    request = KERNEL.validate_request(json.loads(EXAMPLE.read_text()))
    mechanisms, _sources, mechanism_digest, source_digest = KERNEL.validate_mechanisms()
    return KERNEL.compile_kernel(request, mechanisms, mechanism_digest, source_digest)


def budget(tokens: int, cost: int, wall: int) -> dict:
    return {
        "max_tokens": tokens,
        "max_cost_microusd": cost,
        "max_wall_seconds": wall,
    }


def command_claim(kernel: dict, cell_index: int = 0) -> dict:
    cell = kernel["organization"]["manager_cells"][cell_index]
    request = RECONCILE.validate_request(
        {
            "$schema": RECONCILE.REQUEST_SCHEMA,
            "kernel_digest": kernel["kernel_digest"],
            "generation": 1,
            "project_id": "atlas-project",
            "cycle_id": "cycle-1",
            "parent_runtime_id": "master-runtime-1",
            "budget_envelope": budget(10_000, 10_000, 300),
            "manager_admissions": [
                {"cell_id": cell["cell_id"], "budget": budget(1_000, 100, 60)}
            ],
            "observed_snapshot": {
                "$schema": RECONCILE.SNAPSHOT_SCHEMA,
                "last_event_cursor": 0,
                "attempts": [],
            },
        },
        kernel,
    )
    plan = RECONCILE.compile_plan(kernel, request)
    record = POSTGRES.build_record(
        kernel, request, plan, created_at="2026-08-05T12:00:00+00:00"
    )
    command = record["commands"][0]
    return {
        "$schema": POSTGRES.POSTGRESQL_CLAIM_SCHEMA,
        "ok": True,
        "backend": "postgresql",
        "project_id": "atlas-project",
        "claim_owner": "master-runtime-1",
        "claim": {
            "message_key": command["message_key"],
            "payload_json": command["payload_json"],
            "payload_sha256": command["payload_sha256"],
            "lease_generation": 1,
        },
    }


def host_binding(kernel: dict) -> dict:
    return {
        "$schema": BRIDGE.BINDING_SCHEMA,
        "binding_id": "atlas-project-local",
        "company_project_id": "atlas-project",
        "kernel_digest": kernel["kernel_digest"],
        "target": {"type": "projectless", "directory_name": "atlas-manager-runtime"},
    }


def kernel_with_complete_medium_contract(*, delegate_medium: bool = True) -> dict:
    request = json.loads(EXAMPLE.read_text())
    if not delegate_medium:
        request["authority"]["delegated_risk_tiers"] = ["low", "high"]
    for unit in request["business_units"]:
        for program in unit["programs"]:
            if program["risk_tier"] != "medium":
                continue
            for stream in program["workstreams"]:
                stream["mandatory_requirements"] = [
                    "Preserve the complete user-requested outcome and constraints."
                ]
                stream["acceptance_checks"] = [
                    "Independent readback proves the requested outcome and constraints."
                ]
    normalized = KERNEL.validate_request(request)
    mechanisms, _sources, mechanism_digest, source_digest = KERNEL.validate_mechanisms()
    return KERNEL.compile_kernel(normalized, mechanisms, mechanism_digest, source_digest)


def readback(dispatch: dict, thread_id: str = "thread-1", host_id: str = "local") -> dict:
    return {
        "schemaVersion": 1,
        "thread": {"id": thread_id, "hostId": host_id},
        "turns": [
            {
                "id": "turn-1",
                "startedAt": 1,
                "items": [
                    {
                        "type": "userMessage",
                        "content": [{"type": "text", "text": dispatch["arguments"]["prompt"]}],
                    }
                ],
            }
        ],
    }


def candidate_set(dispatch: dict, phase: str, readbacks: list[dict]) -> dict:
    thread_ids = sorted(value["thread"]["id"] for value in readbacks)
    return {
        "$schema": BRIDGE.RECONCILIATION_INPUT_SCHEMA,
        "phase": phase,
        "observation": {
            "$schema": BRIDGE.RECONCILIATION_OBSERVATION_SCHEMA,
            "source": "codex_app__list_threads",
            "observed_at": "2026-08-05T18:00:00Z",
            "listing_complete": True,
            "listing_limit": 100,
            "returned_count": len(thread_ids),
            "listed_thread_ids": thread_ids,
        },
        "readbacks": readbacks,
    }


class NativeCodexDispatchBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.kernel = compiled_kernel()
        self.claim = command_claim(self.kernel)
        self.binding = host_binding(self.kernel)
        self.dispatch = BRIDGE.build_dispatch(self.kernel, self.claim, self.binding)

    def test_dispatch_is_deterministic_compact_and_uses_dynamic_cell_capacity(self) -> None:
        second = BRIDGE.build_dispatch(
            deepcopy(self.kernel), deepcopy(self.claim), deepcopy(self.binding)
        )
        self.assertEqual(self.dispatch, second)
        self.assertEqual(self.dispatch["tool"], "codex_app__create_thread")
        self.assertEqual(self.dispatch["arguments"]["model"], "gpt-5.6-sol")
        self.assertEqual(self.dispatch["arguments"]["thinking"], "xhigh")
        prompt = self.dispatch["arguments"]["prompt"]
        self.assertIn("$luna-execution-fabric", prompt)
        self.assertIn('"requested_worker_model":"gpt-5.6-luna"', prompt)
        self.assertIn('"requested_worker_reasoning":"max"', prompt)
        cell = self.kernel["organization"]["manager_cells"][0]
        self.assertIn(f'"direct_report_limit":{cell["direct_report_limit"]}', prompt)
        self.assertIn(f'"declared_worker_slots":{cell["declared_worker_slots"]}', prompt)
        expected_cap = min(
            cell["declared_worker_slots"],
            self.kernel["admission"]["initial_active_luna_limit"]
            // self.kernel["admission"]["initial_active_manager_limit"],
        )
        self.assertIn(f'"active_worker_concurrency_cap":{expected_cap}', prompt)
        self.assertIn('"program_objective":', prompt)
        self.assertIn("Do not create workers until the master sends an explicit CONTINUE", prompt)
        self.assertIn('"design_barrier":"authenticated_master_decision"', prompt)
        self.assertIn('"manager_direct_labor":"exception_only_with_variance"', prompt)
        self.assertIn("must not materialize a worker-eligible artifact itself", prompt)
        self.assertEqual(
            self.dispatch["attempt_id"],
            json.loads(self.claim["claim"]["payload_json"])["action"]["attempt_id"],
        )
        self.assertEqual(
            self.dispatch["initial_prompt_sha256"], BRIDGE.digest_text(prompt)
        )
        retained = deepcopy(self.dispatch)
        digest = retained.pop("dispatch_digest")
        self.assertEqual(digest, BRIDGE.digest_text(BRIDGE.canonical_json(retained)))

    def test_medium_risk_delegated_cell_auto_continues_design_without_a_master_round_trip(self) -> None:
        kernel = kernel_with_complete_medium_contract()
        medium_index = next(
            index
            for index, cell in enumerate(kernel["organization"]["manager_cells"])
            if cell["risk_tier"] == "medium"
        )
        claim = command_claim(kernel, medium_index)
        dispatch = BRIDGE.build_dispatch(kernel, claim, host_binding(kernel))
        prompt = dispatch["arguments"]["prompt"]
        self.assertIn('"design_barrier":"charter_bound_auto_continue"', prompt)
        self.assertIn("signed dispatch preauthorizes design-to-execution continuation", prompt)
        self.assertIn("create eligible Luna/max workers in the same turn", prompt)
        self.assertNotIn(
            "Do not create workers until the master sends an explicit CONTINUE",
            prompt,
        )
        self.assertIn('"luna_labor_share_min":0.7', prompt)
        self.assertIn('"sol_overhead_share_max":0.2', prompt)
        self.assertIn("Preserve the complete user-requested outcome and constraints.", prompt)
        self.assertIn(
            "Independent readback proves the requested outcome and constraints.",
            prompt,
        )

    def test_non_delegated_medium_cell_cannot_auto_continue(self) -> None:
        kernel = kernel_with_complete_medium_contract(delegate_medium=False)
        medium_index = next(
            index
            for index, cell in enumerate(kernel["organization"]["manager_cells"])
            if cell["risk_tier"] == "medium"
        )
        dispatch = BRIDGE.build_dispatch(
            kernel,
            command_claim(kernel, medium_index),
            host_binding(kernel),
        )
        prompt = dispatch["arguments"]["prompt"]
        self.assertIn('"design_barrier":"authenticated_master_decision"', prompt)
        self.assertIn("Do not create workers until the master sends an explicit CONTINUE", prompt)

    def test_incomplete_delivery_contract_cannot_auto_continue(self) -> None:
        medium_index = next(
            index
            for index, cell in enumerate(self.kernel["organization"]["manager_cells"])
            if cell["risk_tier"] == "medium"
        )
        dispatch = BRIDGE.build_dispatch(
            self.kernel,
            command_claim(self.kernel, medium_index),
            self.binding,
        )
        prompt = dispatch["arguments"]["prompt"]
        self.assertIn('"delivery_contract_status":"incomplete"', prompt)
        self.assertIn('"design_barrier":"authenticated_master_decision"', prompt)

    def test_claim_payload_tampering_and_cross_project_binding_fail_closed(self) -> None:
        tampered = deepcopy(self.claim)
        payload = json.loads(tampered["claim"]["payload_json"])
        payload["project_id"] = "other-project"
        tampered["claim"]["payload_json"] = BRIDGE.canonical_json(payload)
        with self.assertRaisesRegex(BRIDGE.NativeBridgeError, "digest"):
            BRIDGE.build_dispatch(self.kernel, tampered, self.binding)

        crossed = deepcopy(self.binding)
        crossed["company_project_id"] = "other-project"
        with self.assertRaisesRegex(BRIDGE.NativeBridgeError, "does not match"):
            BRIDGE.build_dispatch(self.kernel, self.claim, crossed)

    def test_claim_cannot_rebind_mutated_budget_under_the_old_command_key(self) -> None:
        tampered = deepcopy(self.claim)
        payload = json.loads(tampered["claim"]["payload_json"])
        payload["action"]["admission_state"]["admission"]["budget"]["max_tokens"] = 999_000
        tampered_json = BRIDGE.canonical_json(payload)
        tampered["claim"]["payload_json"] = tampered_json
        tampered["claim"]["payload_sha256"] = BRIDGE.digest_text(tampered_json)
        with self.assertRaisesRegex(BRIDGE.NativeBridgeError, "command digest"):
            BRIDGE.build_dispatch(self.kernel, tampered, self.binding)

    def test_every_command_field_is_bound_by_the_original_message_key(self) -> None:
        mutations = [
            ("budget", lambda value: value["action"]["admission_state"]["admission"]["budget"].__setitem__("max_tokens", 9_999)),
            ("admission", lambda value: value["action"]["admission_state"].__setitem__("admission_digest", "0" * 64)),
            ("parent", lambda value: value.__setitem__("parent_runtime_id", "other-parent")),
            ("scope", lambda value: value["action"]["admission_state"]["admission"]["scope"].__setitem__("deliverable", "other")),
            ("order", lambda value: value.__setitem__("plan_order", 99)),
            ("action", lambda value: value["action"].__setitem__("reason", "other")),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label):
                tampered = deepcopy(self.claim)
                payload = json.loads(tampered["claim"]["payload_json"])
                mutate(payload)
                payload_json = BRIDGE.canonical_json(payload)
                tampered["claim"]["payload_json"] = payload_json
                tampered["claim"]["payload_sha256"] = BRIDGE.digest_text(payload_json)
                with self.assertRaisesRegex(BRIDGE.NativeBridgeError, "command digest"):
                    BRIDGE.build_dispatch(self.kernel, tampered, self.binding)

    def test_project_binding_translates_only_explicit_worktree_state(self) -> None:
        binding = host_binding(self.kernel)
        binding["target"] = {
            "type": "project",
            "project_id": "local-project-id",
            "environment": {
                "type": "worktree",
                "starting_state": {"type": "branch", "branch_name": "accepted-branch"},
            },
        }
        dispatch = BRIDGE.build_dispatch(self.kernel, self.claim, binding)
        self.assertEqual(
            dispatch["arguments"]["target"],
            {
                "type": "project",
                "projectId": "local-project-id",
                "environment": {
                    "type": "worktree",
                    "startingState": {"type": "branch", "branchName": "accepted-branch"},
                },
            },
        )

    def test_exact_create_and_initial_prompt_readback_produce_settlement_receipt(self) -> None:
        receipt = BRIDGE.verify_creation(
            self.dispatch,
            {"threadId": "thread-1", "hostId": "local"},
            readback(self.dispatch),
        )
        self.assertTrue(receipt["settlement_eligible"])
        self.assertEqual(receipt["status"], "host_created")
        self.assertEqual(receipt["task_id"], receipt["thread_id"])
        self.assertEqual(receipt["message_key"], self.claim["claim"]["message_key"])

    def test_setup_pending_is_not_settlement_evidence(self) -> None:
        receipt = BRIDGE.verify_creation(
            self.dispatch, {"clientThreadId": "pending-client"}, {}
        )
        self.assertEqual(receipt["status"], "setup_pending")
        self.assertFalse(receipt["settlement_eligible"])
        self.assertNotIn("thread_id", receipt)

    def test_candidate_reconciliation_separates_create_recovery_and_conflict(self) -> None:
        absent = BRIDGE.reconcile_candidates(
            self.dispatch,
            candidate_set(self.dispatch, "pre_create", []),
        )
        self.assertEqual(absent["status"], "absent")
        self.assertTrue(absent["create_allowed"])
        self.assertEqual(absent["action"], "prepare_launch_attempt_before_create")

        recovered = BRIDGE.reconcile_candidates(
            self.dispatch,
            candidate_set(
                self.dispatch, "ambiguous_recovery", [readback(self.dispatch)]
            ),
        )
        self.assertEqual(recovered["status"], "recovered")
        self.assertFalse(recovered["create_allowed"])
        self.assertTrue(
            recovered["recovered_creation_receipt"]["settlement_eligible"]
        )

        second = readback(self.dispatch, thread_id="thread-2", host_id="host-2")
        conflict = BRIDGE.reconcile_candidates(
            self.dispatch,
            candidate_set(
                self.dispatch,
                "ambiguous_recovery",
                [readback(self.dispatch), second],
            ),
        )
        self.assertEqual(conflict["status"], "conflict")
        self.assertEqual(conflict["action"], "block_and_escalate")

    def test_ambiguous_zero_candidate_does_not_authorize_recreate(self) -> None:
        receipt = BRIDGE.reconcile_candidates(
            self.dispatch,
            candidate_set(self.dispatch, "ambiguous_recovery", []),
        )
        self.assertEqual(receipt["status"], "ambiguous")
        self.assertFalse(receipt["create_allowed"])
        self.assertEqual(
            receipt["action"], "require_separately_authorized_absence_decision"
        )

    def test_candidate_reconciliation_requires_complete_fresh_listing_evidence(self) -> None:
        for label, mutate in [
            ("missing observation", lambda value: value.pop("observation")),
            (
                "incomplete listing",
                lambda value: value["observation"].__setitem__("listing_complete", False),
            ),
            (
                "missing readback",
                lambda value: value["observation"].__setitem__(
                    "listed_thread_ids", ["missing-thread"]
                ),
            ),
            (
                "stale shape",
                lambda value: value["observation"].__setitem__("observed_at", "not-time"),
            ),
        ]:
            with self.subTest(label=label):
                candidate = candidate_set(self.dispatch, "ambiguous_recovery", [])
                mutate(candidate)
                with self.assertRaises(BRIDGE.NativeBridgeError):
                    BRIDGE.reconcile_candidates(self.dispatch, candidate)

    def test_missing_initial_turn_time_cannot_promote_later_copied_prompt(self) -> None:
        drifted = readback(self.dispatch)
        drifted["turns"][0]["startedAt"] = None
        drifted["turns"][0]["items"][0]["content"][0]["text"] = "DIFFERENT"
        drifted["turns"].append(
            {
                "id": "turn-2",
                "startedAt": 2,
                "items": [
                    {
                        "type": "userMessage",
                        "content": [
                            {"type": "text", "text": self.dispatch["arguments"]["prompt"]}
                        ],
                    }
                ],
            }
        )
        with self.assertRaisesRegex(BRIDGE.NativeBridgeError, "authoritative startedAt"):
            BRIDGE.verify_creation(
                self.dispatch,
                {"threadId": "thread-1", "hostId": "local"},
                drifted,
            )

    def test_later_copied_marker_cannot_replace_malformed_initial_user_message(self) -> None:
        drifted = readback(self.dispatch)
        later = deepcopy(drifted["turns"][0])
        later["id"] = "turn-2"
        later["startedAt"] = 2
        drifted["turns"][0]["items"][0]["content"] = [
            {"type": "attachment", "text": self.dispatch["marker"]}
        ]
        drifted["turns"].append(later)
        with self.assertRaisesRegex(BRIDGE.NativeBridgeError, "unsupported content"):
            BRIDGE.verify_creation(
                self.dispatch,
                {"threadId": "thread-1", "hostId": "local"},
                drifted,
            )
        reconciled = BRIDGE.reconcile_candidates(
            self.dispatch,
            candidate_set(self.dispatch, "ambiguous_recovery", [drifted]),
        )
        self.assertEqual(reconciled["status"], "conflict")

    def test_wrong_identity_prompt_and_dispatch_digest_are_rejected(self) -> None:
        with self.assertRaisesRegex(BRIDGE.NativeBridgeError, "identity"):
            BRIDGE.verify_creation(
                self.dispatch,
                {"threadId": "thread-1", "hostId": "local"},
                readback(self.dispatch, thread_id="thread-2"),
            )
        wrong_prompt = readback(self.dispatch)
        wrong_prompt["turns"][0]["items"][0]["content"][0]["text"] = "different"
        with self.assertRaisesRegex(BRIDGE.NativeBridgeError, "prompt"):
            BRIDGE.verify_creation(
                self.dispatch,
                {"threadId": "thread-1", "hostId": "local"},
                wrong_prompt,
            )
        drifted = deepcopy(self.dispatch)
        drifted["cell_id"] = "different-cell"
        with self.assertRaisesRegex(BRIDGE.NativeBridgeError, "digest"):
            BRIDGE.verify_creation(
                drifted,
                {"threadId": "thread-1", "hostId": "local"},
                readback(drifted),
            )
        prompt_hash_drifted = deepcopy(self.dispatch)
        prompt_hash_drifted["initial_prompt_sha256"] = "0" * 64
        retained = deepcopy(prompt_hash_drifted)
        retained.pop("dispatch_digest")
        prompt_hash_drifted["dispatch_digest"] = BRIDGE.digest_text(
            BRIDGE.canonical_json(retained)
        )
        with self.assertRaisesRegex(BRIDGE.NativeBridgeError, "digest"):
            BRIDGE.verify_creation(
                prompt_hash_drifted,
                {"threadId": "thread-1", "hostId": "local"},
                readback(prompt_hash_drifted),
            )

    def test_checked_in_binding_is_canonical_and_current(self) -> None:
        raw = BINDING_EXAMPLE.read_bytes()
        binding = json.loads(raw)
        self.assertEqual(raw, (BRIDGE.canonical_json(binding) + "\n").encode())
        self.assertEqual(binding["kernel_digest"], self.kernel["kernel_digest"])

    def test_cli_compile_emits_canonical_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kernel_path = root / "kernel.json"
            claim_path = root / "claim.json"
            binding_path = root / "binding.json"
            kernel_path.write_text(BRIDGE.canonical_json(self.kernel) + "\n")
            claim_path.write_text(BRIDGE.canonical_json(self.claim) + "\n")
            binding_path.write_text(BRIDGE.canonical_json(self.binding) + "\n")
            # Exercise the same compile function used by the CLI without shell redirection.
            compiled = BRIDGE.build_dispatch(
                RECONCILE.verify_kernel_document(kernel_path),
                BRIDGE.read_canonical(claim_path, "claim"),
                BRIDGE.read_canonical(binding_path, "binding"),
            )
            self.assertEqual(
                json.loads(BRIDGE.canonical_json(compiled)), self.dispatch
            )


if __name__ == "__main__":
    unittest.main()
