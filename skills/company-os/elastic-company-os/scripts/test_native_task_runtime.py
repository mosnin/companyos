from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "native_task_runtime", Path(__file__).with_name("native_task_runtime.py")
)
runtime = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(runtime)


class NativeTaskRuntimeTests(unittest.TestCase):
    def admitted(self):
        return runtime.admit(
            attempt_id="attempt-1",
            idempotency_key="dispatch-1",
            requested_model="gpt-5.6-luna",
            project_id="project-1",
            work_id="work-1",
            cycle_id="cycle-1",
            parent_runtime_id="manager-1",
            role="worker",
            scope=["owned/file.py"],
            budget={"max_tokens": 1000},
        )

    def claimed(self):
        return runtime.claim_dispatch(self.admitted())

    def created(self):
        return runtime.bind_host_identity(
            self.claimed(),
            task_id="task-1",
            thread_id="thread-1",
            host_id="host-a",
            tool="create_task",
        )

    def running(self):
        return runtime.apply_event(
            self.created(),
            "running",
            source="host_observation",
            tool="wait_task",
            task_id="task-1",
            thread_id="thread-1",
            host_id="host-a",
            current_status="running",
        )

    def completed(self):
        return runtime.apply_event(
            self.running(),
            "terminal",
            source="host_observation",
            tool="read_task",
            task_id="task-1",
            thread_id="thread-1",
            status="succeeded",
        )

    def reseal_events(self, state):
        for sequence, event in enumerate(state["events"], start=1):
            event["sequence"] = sequence
            event["payload_sha256"] = runtime.canonical_digest(event["payload"])
        state["sequence"] = len(state["events"])
        state["host_observations"] = [
            deepcopy(event)
            for event in state["events"]
            if event["payload"].get("source") == "host_observation"
        ]
        if state["receipt"] is not None:
            state["receipt"]["payload_sha256"] = runtime.canonical_digest(
                runtime._receipt_payload(state)
            )

    def test_admission_receipt_precedes_claim_and_host_binding(self):
        admitted = self.admitted()
        self.assertEqual(admitted["status"], "dispatch_intent_recorded")
        self.assertEqual(admitted["dispatch_receipt"]["status"], "admitted_pre_create")
        with self.assertRaises(runtime.RuntimeStateError):
            runtime.bind_host_identity(
                admitted, task_id="task-1", thread_id="thread-1", tool="create_task"
            )
        claimed = runtime.claim_dispatch(admitted)
        self.assertEqual(claimed["dispatch"]["status"], "claimed_create_in_flight")
        created = runtime.bind_host_identity(
            claimed, task_id="task-1", thread_id="thread-1", host_id="host-a",
            tool="create_task"
        )
        self.assertEqual(created["native_identity"]["thread_id"], "thread-1")
        self.assertEqual(runtime.audit_state(created), [])

    def test_exact_replays_are_noops_and_conflicts_reject(self):
        claimed = self.claimed()
        self.assertEqual(runtime.claim_dispatch(claimed), claimed)
        created = self.created()
        duplicate = runtime.bind_host_identity(
            created,
            task_id="task-1",
            thread_id="thread-1",
            host_id="host-a",
            tool="create_task",
        )
        self.assertEqual(duplicate, created)
        with self.assertRaises(runtime.RuntimeStateError):
            runtime.bind_host_identity(
                created, task_id="task-2", thread_id="thread-1", tool="create_task"
            )

    def test_restart_reconciliation_never_relaunches_ambiguous_claim(self):
        admitted = runtime.reconcile_restart(self.admitted())
        self.assertEqual(admitted["reconciliation"]["next_action"], "claim_dispatch")
        ambiguous = runtime.reconcile_restart(self.claimed())
        self.assertEqual(
            ambiguous["reconciliation"]["next_action"], "reconcile_host_listing"
        )
        self.assertNotIn("create", ambiguous["reconciliation"]["next_action"])

    def test_host_identity_requires_returned_task_and_thread(self):
        claimed = self.claimed()
        for values in (
            {"task_id": "", "thread_id": "thread-1", "tool": "create_task"},
            {"task_id": "task-1", "thread_id": "", "tool": "create_task"},
        ):
            with self.assertRaises(runtime.RuntimeStateError):
                runtime.bind_host_identity(claimed, **values)
        with self.assertRaises(runtime.RuntimeStateError):
            runtime.apply_event(
                claimed,
                "host_created",
                source="prompt_claim",
                tool="create_task",
                task_id="task-1",
                thread_id="thread-1",
            )

    def test_terminal_requires_ordered_create_and_start(self):
        terminal = {
            "source": "host_observation",
            "tool": "read_task",
            "task_id": "task-1",
            "thread_id": "thread-1",
            "status": "succeeded",
        }
        with self.assertRaises(runtime.RuntimeStateError):
            runtime.record_event(self.claimed(), "terminal", payload=terminal)
        with self.assertRaises(runtime.RuntimeStateError):
            runtime.record_event(self.created(), "terminal", payload=terminal)
        completed = runtime.record_event(self.running(), "terminal", payload=terminal)
        self.assertEqual(completed["status"], "succeeded")
        self.assertEqual(completed["receipt"]["status"], "complete")
        self.assertEqual(runtime.audit_state(completed), [])

    def test_terminal_receipt_binds_full_chain_and_detects_tamper(self):
        completed = runtime.apply_event(
            self.running(),
            "terminal",
            source="host_observation",
            tool="read_task",
            task_id="task-1",
            thread_id="thread-1",
            status="succeeded",
            artifact_digests=["a" * 64],
        )
        self.assertEqual(
            runtime.apply_event(
                completed,
                "terminal",
                source="host_observation",
                tool="read_task",
                task_id="task-1",
                thread_id="thread-1",
                status="succeeded",
                artifact_digests=["a" * 64],
            ),
            completed,
        )
        tampered = deepcopy(completed)
        tampered["host_observations"][0]["payload"]["task_id"] = "other"
        self.assertIn("native runtime terminal receipt is invalid", runtime.audit_state(tampered))
        widened = deepcopy(completed)
        widened["invented_provider_model"] = "gpt-invented"
        self.assertIn("native runtime state fields are invalid", runtime.audit_state(widened))

    def test_cancellation_intent_is_separate_and_dominates_success(self):
        cancelled = runtime.request_cancellation(
            self.running(), reason="operator stop", requested_by="master"
        )
        self.assertEqual(cancelled["cancellation"]["desired_intent"], "cancel")
        self.assertEqual(cancelled["cancellation"]["hard_cancellation_status"], "unavailable")
        with self.assertRaises(runtime.RuntimeStateError):
            runtime.apply_event(
                cancelled,
                "terminal",
                source="host_observation",
                tool="read_task",
                task_id="task-1",
                thread_id="thread-1",
                status="succeeded",
            )
        terminal = runtime.apply_event(
            cancelled,
            "terminal",
            source="host_observation",
            tool="read_task",
            task_id="task-1",
            thread_id="thread-1",
            status="cancelled",
        )
        self.assertEqual(terminal["receipt"]["status"], "cancelled")

    def test_cooperative_delivery_does_not_invent_hard_acknowledgement(self):
        cancelled = runtime.request_cancellation(
            self.running(), reason="operator stop", requested_by="master"
        )
        delivered = runtime.apply_event(
            cancelled,
            "cooperative_stop_delivered",
            source="host_observation",
            tool="send_message",
            task_id="task-1",
            thread_id="thread-1",
        )
        self.assertEqual(
            delivered["cancellation"]["cooperative_stop_delivery"], "delivered"
        )
        self.assertEqual(
            delivered["cancellation"]["acknowledgement_status"], "unavailable"
        )

    def test_hard_acknowledgement_requires_explicit_host_observation(self):
        cancelled = runtime.request_cancellation(
            self.running(), reason="operator stop", requested_by="master"
        )
        with self.assertRaises(runtime.RuntimeStateError):
            runtime.apply_event(
                cancelled,
                "hard_cancellation_observed",
                source="controller_claim",
                tool="hard_cancel",
                task_id="task-1",
                thread_id="thread-1",
                hard_status="acknowledged",
                acknowledgement_status="acknowledged",
            )
        observed = runtime.apply_event(
            cancelled,
            "hard_cancellation_observed",
            source="host_observation",
            tool="hard_cancel",
            task_id="task-1",
            thread_id="thread-1",
            hard_status="acknowledged",
            acknowledgement_status="acknowledged",
        )
        self.assertEqual(
            observed["cancellation"]["hard_cancellation_status"], "acknowledged"
        )

    def test_cancellation_evidence_matrix_direct_transition_is_atomic(self):
        pairs = (
            ("acknowledged", "acknowledged", True, "cancel_acknowledged"),
            ("acknowledged", "not_acknowledged", False, None),
            ("refused", "acknowledged", False, None),
            ("refused", "not_acknowledged", True, "cancel_requested"),
            ("failed", "acknowledged", False, None),
            ("failed", "not_acknowledged", True, "cancel_requested"),
        )
        for hard_status, acknowledgement_status, legal, expected_status in pairs:
            with self.subTest(hard_status=hard_status, acknowledgement_status=acknowledgement_status):
                state = runtime.request_cancellation(
                    self.running(), reason="operator stop", requested_by="master"
                )
                before = deepcopy(state)
                if not legal:
                    with self.assertRaises(runtime.RuntimeStateError):
                        runtime.apply_event(
                            state,
                            "hard_cancellation_observed",
                            source="host_observation",
                            tool="hard_cancel",
                            task_id="task-1",
                            thread_id="thread-1",
                            hard_status=hard_status,
                            acknowledgement_status=acknowledgement_status,
                        )
                    self.assertEqual(state, before)
                    continue
                observed = runtime.apply_event(
                    state,
                    "hard_cancellation_observed",
                    source="host_observation",
                    tool="hard_cancel",
                    task_id="task-1",
                    thread_id="thread-1",
                    hard_status=hard_status,
                    acknowledgement_status=acknowledgement_status,
                )
                self.assertEqual(observed["status"], expected_status)
                self.assertEqual(
                    (observed["cancellation"]["hard_cancellation_status"],
                     observed["cancellation"]["acknowledgement_status"]),
                    (hard_status, acknowledgement_status),
                )
                self.assertEqual(runtime.audit_state(observed), [])

    def test_cancellation_evidence_matrix_replay_rejects_illegal_and_state_only_injection(self):
        for hard_status, legal_acknowledgement_status in (
            ("refused", "not_acknowledged"),
            ("acknowledged", "acknowledged"),
            ("failed", "not_acknowledged"),
        ):
            with self.subTest(hard_status=hard_status):
                legal = runtime.apply_event(
                    runtime.request_cancellation(
                        self.running(), reason="operator stop", requested_by="master"
                    ),
                    "hard_cancellation_observed",
                    source="host_observation",
                    tool="hard_cancel",
                    task_id="task-1",
                    thread_id="thread-1",
                    hard_status=hard_status,
                    acknowledgement_status=legal_acknowledgement_status,
                )
                injected_event = deepcopy(legal)
                injected_event["events"][-1]["payload"]["acknowledgement_status"] = (
                    "acknowledged"
                    if legal_acknowledgement_status == "not_acknowledged"
                    else "not_acknowledged"
                )
                self.reseal_events(injected_event)
                self.assertTrue(runtime.audit_state(injected_event))
                with self.assertRaises(runtime.RuntimeStateError):
                    runtime.record_event(
                        injected_event,
                        "hard_cancellation_observed",
                        payload=injected_event["events"][-1]["payload"],
                    )

                injected_state = deepcopy(legal)
                injected_state["cancellation"]["acknowledgement_status"] = (
                    injected_event["events"][-1]["payload"]["acknowledgement_status"]
                )
                self.assertTrue(runtime.audit_state(injected_state))

    def test_acknowledged_cancellation_can_reach_terminal_cancelled(self):
        observed = runtime.apply_event(
            runtime.request_cancellation(
                self.running(), reason="operator stop", requested_by="master"
            ),
            "hard_cancellation_observed",
            source="host_observation",
            tool="hard_cancel",
            task_id="task-1",
            thread_id="thread-1",
            hard_status="acknowledged",
            acknowledgement_status="acknowledged",
        )
        terminal = runtime.apply_event(
            observed,
            "terminal",
            source="host_observation",
            tool="read_task",
            task_id="task-1",
            thread_id="thread-1",
            status="cancelled",
        )
        self.assertEqual(terminal["status"], "cancelled")
        self.assertEqual(
            terminal["cancellation"]["hard_cancellation_status"], "acknowledged"
        )
        self.assertEqual(
            terminal["cancellation"]["acknowledgement_status"], "acknowledged"
        )
        self.assertIsNotNone(terminal["receipt"])
        self.assertEqual(runtime.audit_state(terminal), [])

    def test_prelaunch_cancel_only_when_dispatch_not_claimed(self):
        requested = runtime.request_cancellation(
            self.admitted(), reason="operator stop", requested_by="master"
        )
        self.assertEqual(
            runtime.reconcile_restart(requested)["reconciliation"]["next_action"],
            "finalize_cancelled_before_launch",
        )
        terminal = runtime.apply_event(
            requested,
            "cancelled_before_launch",
            source="controller_reconciliation",
            next_action="finalize_cancelled_before_launch",
        )
        self.assertEqual(terminal["status"], "cancelled_before_launch")
        ambiguous = runtime.request_cancellation(
            self.claimed(), reason="operator stop", requested_by="master"
        )
        with self.assertRaises(runtime.RuntimeStateError):
            runtime.apply_event(
                ambiguous,
                "cancelled_before_launch",
                source="controller_reconciliation",
                next_action="finalize_cancelled_before_launch",
            )

    def test_lifecycle_replay_rejects_reordered_and_duplicate_running_events(self):
        completed = self.completed()
        reordered = deepcopy(completed)
        reordered["events"][2], reordered["events"][3] = (
            reordered["events"][3], reordered["events"][2]
        )
        self.reseal_events(reordered)
        self.assertIn(
            "native runtime lifecycle does not replay from admission",
            runtime.audit_state(reordered),
        )

        duplicated = deepcopy(completed)
        duplicated["events"].insert(4, deepcopy(duplicated["events"][3]))
        self.reseal_events(duplicated)
        self.assertIn(
            "native runtime lifecycle does not replay from admission",
            runtime.audit_state(duplicated),
        )

    def test_lifecycle_replay_rejects_deleted_and_state_only_history(self):
        deleted = deepcopy(self.completed())
        deleted["events"] = deleted["events"][:3]
        self.reseal_events(deleted)
        self.assertIn(
            "native runtime lifecycle does not replay from admission",
            runtime.audit_state(deleted),
        )

        state_only = deepcopy(self.created())
        state_only["status"] = "running"
        state_only["reconciliation"] = {
            "status": "pending",
            "next_action": "await_terminal_observation",
        }
        self.assertIn(
            "native runtime lifecycle does not replay from admission",
            runtime.audit_state(state_only),
        )

    def test_cancellation_dispatch_is_retained_and_replayed(self):
        cancellation_dispatch = {
            "status": "pending",
            "key": "attempt-1",
            "payload_sha256": "a" * 64,
        }
        requested = runtime.request_cancellation(
            self.running(),
            reason="operator stop",
            requested_by="master",
            dispatch=cancellation_dispatch,
        )
        claimed = runtime.claim_cancellation_dispatch(requested)
        self.assertEqual(claimed["cancellation"]["dispatch"]["status"], "claimed")
        delivered = runtime.apply_event(
            claimed,
            "cooperative_stop_delivered",
            source="host_observation",
            tool="send_message",
            task_id="task-1",
            thread_id="thread-1",
        )
        self.assertEqual(delivered["cancellation"]["dispatch"]["status"], "delivered")
        self.assertEqual(runtime.audit_state(delivered), [])

    def test_persisted_schema_downgrade_boundary_is_explicit(self):
        state = self.completed()
        self.assertEqual(state["schema"], "company-os.native-task-runtime.v2")
        current = runtime.downgrade_assessment(state, runtime.SCHEMA)
        self.assertTrue(current["compatible"])
        legacy = runtime.downgrade_assessment(state, runtime.LEGACY_SCHEMA)
        self.assertFalse(legacy["compatible"])
        self.assertEqual(legacy["status"], "blocked")
        self.assertEqual(
            legacy["reason"],
            "v2_lifecycle_replay_and_authority_bindings_are_not_representable",
        )

    def test_authority_hash_must_bind_its_exact_retained_transition(self):
        state = self.claimed()
        details = deepcopy(state["events"][1]["payload"])
        command_payload = {
            "attempt_id": "attempt-1",
            "work_id": "work-1",
            "cycle_id": "cycle-1",
            "parent_runtime_id": "manager-1",
            "action": "claim-native-task-dispatch",
            "details": details,
        }
        authority = {
            "action": "claim-native-task-dispatch",
            "actor": "controller",
            "decision": "claimed",
            "event": "dispatch_claimed",
            "details": details,
            "payload_hash": runtime.canonical_digest({
                "command": "claim-native-task-dispatch",
                "payload": command_payload,
            }),
            "lifecycle_sequence": 2,
            "grant": {"fixture": "opaque-to-pure-state-machine"},
        }
        bound = runtime.attach_authority(state, authority)
        self.assertEqual(runtime.audit_state(bound), [])
        tampered = deepcopy(bound)
        tampered["authority_history"][0]["payload_hash"] = "0" * 64
        self.assertIn(
            "native runtime authority payload hash does not bind exact retained transition",
            runtime.audit_state(tampered),
        )

    def test_requested_model_usage_and_cost_remain_unavailable(self):
        state = self.running()
        self.assertEqual(state["requested_model"], "gpt-5.6-luna")
        for field in ("observed_model", "provider_usage", "cost"):
            self.assertEqual(state[field]["status"], "unavailable")
            self.assertIsNone(state[field]["value"])
        forged = deepcopy(state)
        forged["observed_model"] = {
            "status": "observed",
            "value": "gpt-5.6-luna",
            "reason": "requested model",
        }
        self.assertIn(
            "native runtime observed_model must remain unavailable",
            runtime.audit_state(forged),
        )


if __name__ == "__main__":
    unittest.main()
