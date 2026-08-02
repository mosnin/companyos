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
