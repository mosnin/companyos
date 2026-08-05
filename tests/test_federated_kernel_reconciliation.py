from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "company-os" / "compile-federated-company-kernel"
KERNEL_SCRIPT = SKILL / "scripts" / "compile_federated_kernel.py"
RECONCILER_SCRIPT = SKILL / "scripts" / "reconcile_federated_kernel.py"
EXAMPLE = SKILL / "references" / "federated-kernel-request.example.json"
RECONCILIATION_EXAMPLE = (
    SKILL / "references" / "federated-reconciliation-request.example.json"
)


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


KERNEL = load("federated_kernel_for_reconciliation_tests", KERNEL_SCRIPT)
RECONCILE = load("federated_reconciler_for_tests", RECONCILER_SCRIPT)


def compiled_kernel() -> dict:
    request = KERNEL.validate_request(json.loads(EXAMPLE.read_text()))
    mechanisms, _sources, mechanism_digest, source_digest = KERNEL.validate_mechanisms()
    return KERNEL.compile_kernel(request, mechanisms, mechanism_digest, source_digest)


def budget(tokens: int = 1000, cost: int = 100, wall: int = 60) -> dict:
    return {
        "max_tokens": tokens,
        "max_cost_microusd": cost,
        "max_wall_seconds": wall,
    }


def request_fixture(kernel: dict, *, count: int = 3) -> dict:
    cells = kernel["organization"]["manager_cells"][:count]
    return {
        "$schema": RECONCILE.REQUEST_SCHEMA,
        "kernel_digest": kernel["kernel_digest"],
        "generation": 1,
        "project_id": "atlas-project",
        "cycle_id": "cycle-1",
        "parent_runtime_id": "master-runtime-1",
        "budget_envelope": budget(tokens=10_000, cost=10_000, wall=300),
        "manager_admissions": [
            {"cell_id": cell["cell_id"], "budget": budget()} for cell in cells
        ],
        "observed_snapshot": {
            "$schema": RECONCILE.SNAPSHOT_SCHEMA,
            "last_event_cursor": 0,
            "attempts": [],
        },
    }


def inconclusive() -> dict:
    return {
        "status": "inconclusive",
        "observed_model": None,
        "observed_reasoning": None,
        "source": "unavailable",
        "reason": "host_did_not_expose_runtime_role",
    }


def confirmed(state: dict) -> dict:
    return {
        "status": "confirmed",
        "observed_model": state["requested_model"],
        "observed_reasoning": state["admission"]["metadata"]["requested_reasoning"],
        "source": "host_observation",
        "reason": None,
    }


class FederatedKernelReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.kernel = compiled_kernel()

    def validated(self, request: dict | None = None) -> dict:
        return RECONCILE.validate_request(request or request_fixture(self.kernel), self.kernel)

    def admitted(self, cell_id: str | None = None, request: dict | None = None) -> dict:
        request = request or request_fixture(self.kernel)
        admission = next(
            item
            for item in request["manager_admissions"]
            if cell_id is None or item["cell_id"] == cell_id
        )
        cell = next(
            item
            for item in self.kernel["organization"]["manager_cells"]
            if item["cell_id"] == admission["cell_id"]
        )
        return RECONCILE.admitted_state(
            kernel=self.kernel,
            cell=cell,
            generation=request["generation"],
            project_id=request["project_id"],
            cycle_id=request["cycle_id"],
            parent_runtime_id=request["parent_runtime_id"],
            budget=admission["budget"],
        )

    def observe(self, request: dict, states: list[tuple[dict, dict]]) -> None:
        attempts = []
        for cursor, (state, role) in enumerate(states, start=1):
            attempts.append(
                {
                    "event_cursor": cursor,
                    "native_runtime": state,
                    "role_readback": role,
                }
            )
        request["observed_snapshot"] = {
            "$schema": RECONCILE.SNAPSHOT_SCHEMA,
            "last_event_cursor": len(attempts),
            "attempts": attempts,
        }

    def test_empty_snapshot_emits_bounded_precreate_admissions(self):
        request = self.validated()
        plan = RECONCILE.compile_plan(self.kernel, request)
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(
            [item["kind"] for item in plan["actions"]],
            ["persist-admission-intent"] * 3,
        )
        self.assertEqual(plan["slot_accounting"]["manager_limit"], 3)
        self.assertTrue(all(item["admission_state"]["status"] == "dispatch_intent_recorded" for item in plan["actions"]))
        self.assertFalse(plan["non_claims"]["task_launch_performed"])

    def test_checked_in_reconciliation_example_is_canonical_and_bound(self):
        raw = RECONCILIATION_EXAMPLE.read_bytes()
        request = json.loads(raw)
        self.assertEqual(raw, RECONCILE.canonical_bytes(request))
        normalized = self.validated(request)
        plan = RECONCILE.compile_plan(self.kernel, normalized)
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(len(plan["actions"]), 3)

    def test_plan_is_deterministic_and_cli_verifies(self):
        request = request_fixture(self.kernel)
        normalized = self.validated(request)
        first = RECONCILE.compile_plan(self.kernel, normalized)
        second = RECONCILE.compile_plan(self.kernel, self.validated(deepcopy(request)))
        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kernel_path = root / "kernel.json"
            request_path = root / "request.json"
            plan_path = root / "plan.json"
            kernel_path.write_bytes(RECONCILE.canonical_bytes(self.kernel))
            request_path.write_bytes(RECONCILE.canonical_bytes(request))
            generated = subprocess.run(
                [
                    sys.executable,
                    str(RECONCILER_SCRIPT),
                    "plan",
                    "--kernel",
                    str(kernel_path),
                    "--request",
                    str(request_path),
                    "--output",
                    str(plan_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
            verified = subprocess.run(
                [
                    sys.executable,
                    str(RECONCILER_SCRIPT),
                    "verify",
                    "--kernel",
                    str(kernel_path),
                    "--request",
                    str(request_path),
                    "--plan",
                    str(plan_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
            self.assertFalse(json.loads(verified.stdout)["launch_performed"])

    def test_manager_count_and_global_budgets_fail_closed(self):
        request = request_fixture(self.kernel, count=3)
        fourth = self.kernel["organization"]["manager_cells"][3]
        request["manager_admissions"].append(
            {"cell_id": fourth["cell_id"], "budget": budget()}
        )
        with self.assertRaisesRegex(RECONCILE.ReconciliationError, "manager limit"):
            self.validated(request)
        request = request_fixture(self.kernel)
        request["budget_envelope"]["max_tokens"] = 2_999
        with self.assertRaisesRegex(RECONCILE.ReconciliationError, "global envelope"):
            self.validated(request)

    def test_retained_intent_reconciles_without_relaunch(self):
        request = request_fixture(self.kernel, count=1)
        state = self.admitted(request=request)
        self.observe(request, [(state, inconclusive())])
        plan = RECONCILE.compile_plan(self.kernel, self.validated(request))
        self.assertEqual(len(plan["actions"]), 1)
        self.assertEqual(plan["actions"][0]["kind"], "native-next-action")
        self.assertEqual(plan["actions"][0]["native_next_action"], "claim_dispatch")

    def test_ambiguous_claim_requires_host_listing_not_create(self):
        request = request_fixture(self.kernel, count=1)
        state = RECONCILE.NATIVE.claim_dispatch(self.admitted(request=request))
        self.observe(request, [(state, inconclusive())])
        plan = RECONCILE.compile_plan(self.kernel, self.validated(request))
        action = plan["actions"][0]
        self.assertEqual(action["native_next_action"], "reconcile_host_listing")
        self.assertNotIn("create", action["native_next_action"])

    def test_bound_host_requires_role_readback(self):
        request = request_fixture(self.kernel, count=1)
        state = RECONCILE.NATIVE.bind_host_identity(
            RECONCILE.NATIVE.claim_dispatch(self.admitted(request=request)),
            task_id="task-1",
            thread_id="thread-1",
            host_id="host-1",
            tool="create_task",
        )
        self.observe(request, [(state, inconclusive())])
        plan = RECONCILE.compile_plan(self.kernel, self.validated(request))
        self.assertEqual(plan["actions"][0]["kind"], "observe-role")

    def test_confirmed_role_continues_and_refuted_role_cancels(self):
        request = request_fixture(self.kernel, count=1)
        state = RECONCILE.NATIVE.bind_host_identity(
            RECONCILE.NATIVE.claim_dispatch(self.admitted(request=request)),
            task_id="task-1",
            thread_id="thread-1",
            host_id="host-1",
            tool="create_task",
        )
        self.observe(request, [(state, confirmed(state))])
        plan = RECONCILE.compile_plan(self.kernel, self.validated(request))
        self.assertEqual(plan["actions"][0]["native_next_action"], "await_started_observation")
        refuted = confirmed(state)
        refuted["status"] = "refuted"
        refuted["observed_model"] = "gpt-5.6-terra"
        self.observe(request, [(state, refuted)])
        plan = RECONCILE.compile_plan(self.kernel, self.validated(request))
        self.assertEqual(plan["actions"][0]["kind"], "request-cancellation")
        self.assertEqual(plan["actions"][0]["reason"], "observed_role_drift")

    def test_contradictory_role_readback_is_rejected(self):
        request = request_fixture(self.kernel, count=1)
        state = self.admitted(request=request)
        invalid = confirmed(state)
        invalid["observed_model"] = "gpt-5.6-terra"
        self.observe(request, [(state, invalid)])
        with self.assertRaisesRegex(RECONCILE.ReconciliationError, "conflicts"):
            self.validated(request)

    def test_observed_role_readback_requires_bound_host_identity(self):
        request = request_fixture(self.kernel, count=1)
        state = self.admitted(request=request)
        self.observe(request, [(state, confirmed(state))])
        with self.assertRaisesRegex(RECONCILE.ReconciliationError, "bound native host"):
            self.validated(request)

    def test_terminal_role_drift_is_quarantined_not_settled(self):
        request = request_fixture(self.kernel, count=1)
        state = RECONCILE.NATIVE.bind_host_identity(
            RECONCILE.NATIVE.claim_dispatch(self.admitted(request=request)),
            task_id="task-terminal-drift",
            thread_id="thread-terminal-drift",
            host_id="host-terminal-drift",
            tool="create_task",
        )
        state = RECONCILE.NATIVE.apply_event(
            state,
            "running",
            source="host_observation",
            tool="wait_task",
            task_id="task-terminal-drift",
            thread_id="thread-terminal-drift",
            host_id="host-terminal-drift",
            current_status="running",
        )
        state = RECONCILE.NATIVE.apply_event(
            state,
            "terminal",
            source="host_observation",
            tool="read_task",
            task_id="task-terminal-drift",
            thread_id="thread-terminal-drift",
            host_id="host-terminal-drift",
            status="succeeded",
        )
        role = confirmed(state)
        role["status"] = "refuted"
        role["observed_model"] = "gpt-5.6-terra"
        self.observe(request, [(state, role)])
        plan = RECONCILE.compile_plan(self.kernel, self.validated(request))
        self.assertEqual(plan["actions"][0]["kind"], "quarantine-terminal")

    def test_stale_active_attempt_cancels_and_holds_its_slot(self):
        request = request_fixture(self.kernel)
        states = []
        for admission in request["manager_admissions"][:2]:
            states.append((self.admitted(admission["cell_id"], request), inconclusive()))
        stale = deepcopy(self.admitted(request["manager_admissions"][2]["cell_id"], request))
        stale["admission"]["metadata"]["generation"] = 2
        stale["admission"]["metadata"]["kernel_digest"] = "0" * 64
        stale = RECONCILE.NATIVE.admit(
            attempt_id="stale-g2",
            idempotency_key="stale-dispatch",
            requested_model=stale["requested_model"],
            project_id=request["project_id"],
            work_id=stale["admission"]["work_id"],
            cycle_id=request["cycle_id"],
            parent_runtime_id=request["parent_runtime_id"],
            role="manager",
            scope=stale["admission"]["scope"],
            budget=stale["admission"]["budget"],
            metadata=stale["admission"]["metadata"],
        )
        states.append((stale, inconclusive()))
        self.observe(request, states)
        plan = RECONCILE.compile_plan(self.kernel, self.validated(request))
        kinds = [item["kind"] for item in plan["actions"]]
        self.assertIn("request-cancellation", kinds)
        self.assertIn("defer-admission", kinds)
        self.assertEqual(plan["slot_accounting"]["available_manager_slots"], 0)

    def test_stale_terminal_archives_and_releases_capacity(self):
        request = request_fixture(self.kernel, count=1)
        stale = self.admitted(request=request)
        stale["admission"]["metadata"]["generation"] = 2
        stale["admission"]["metadata"]["kernel_digest"] = "0" * 64
        stale = RECONCILE.NATIVE.admit(
            attempt_id="stale-g2",
            idempotency_key="stale-dispatch",
            requested_model=stale["requested_model"],
            project_id=request["project_id"],
            work_id=stale["admission"]["work_id"],
            cycle_id=request["cycle_id"],
            parent_runtime_id=request["parent_runtime_id"],
            role="manager",
            scope=stale["admission"]["scope"],
            budget=stale["admission"]["budget"],
            metadata=stale["admission"]["metadata"],
        )
        stale = RECONCILE.NATIVE.request_cancellation(
            stale, reason="stale generation", requested_by="master"
        )
        stale = RECONCILE.NATIVE.apply_event(
            stale,
            "cancelled_before_launch",
            source="controller_reconciliation",
            next_action="finalize_cancelled_before_launch",
        )
        self.observe(request, [(stale, inconclusive())])
        plan = RECONCILE.compile_plan(self.kernel, self.validated(request))
        self.assertEqual(
            [item["kind"] for item in plan["actions"]],
            ["archive-stale-terminal", "persist-admission-intent"],
        )

    def test_current_budget_or_spec_drift_blocks_without_launch(self):
        request = request_fixture(self.kernel, count=1)
        state = self.admitted(request=request)
        request["manager_admissions"][0]["budget"]["max_tokens"] += 1
        self.observe(request, [(state, inconclusive())])
        plan = RECONCILE.compile_plan(self.kernel, self.validated(request))
        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["conflicts"][0]["reason"], "current_spec_or_budget_drift")
        self.assertFalse(plan["actions"])

    def test_any_conflict_suppresses_unrelated_stale_actions(self):
        request = request_fixture(self.kernel, count=2)
        current = self.admitted(request["manager_admissions"][0]["cell_id"], request)
        request["manager_admissions"][0]["budget"]["max_tokens"] += 1
        stale = self.admitted(request["manager_admissions"][1]["cell_id"], request)
        stale_metadata = deepcopy(stale["admission"]["metadata"])
        stale_metadata["generation"] = 2
        stale_metadata["kernel_digest"] = "0" * 64
        stale = RECONCILE.NATIVE.admit(
            attempt_id="stale-conflict-g2",
            idempotency_key="stale-conflict-dispatch",
            requested_model=stale["requested_model"],
            project_id=request["project_id"],
            work_id=stale["admission"]["work_id"],
            cycle_id=request["cycle_id"],
            parent_runtime_id=request["parent_runtime_id"],
            role="manager",
            scope=stale["admission"]["scope"],
            budget=stale["admission"]["budget"],
            metadata=stale_metadata,
        )
        self.observe(request, [(current, inconclusive()), (stale, inconclusive())])
        plan = RECONCILE.compile_plan(self.kernel, self.validated(request))
        self.assertEqual(plan["status"], "blocked")
        self.assertFalse(plan["actions"])

    def test_event_cursor_and_native_tamper_fail_closed(self):
        request = request_fixture(self.kernel, count=1)
        state = self.admitted(request=request)
        self.observe(request, [(state, inconclusive())])
        request["observed_snapshot"]["last_event_cursor"] = 2
        with self.assertRaisesRegex(RECONCILE.ReconciliationError, "last_event_cursor"):
            self.validated(request)
        request = request_fixture(self.kernel, count=1)
        state = self.admitted(request=request)
        state["admission"]["project_id"] = "tampered"
        self.observe(request, [(state, inconclusive())])
        with self.assertRaisesRegex(RECONCILE.ReconciliationError, "failed audit"):
            self.validated(request)

    def test_consequential_cell_remains_analysis_only_in_admission(self):
        source = json.loads(EXAMPLE.read_text())
        source["business_units"][1]["programs"][0]["risk_tier"] = "consequential"
        normalized = KERNEL.validate_request(source)
        mechanisms, _sources, mechanism_digest, source_digest = KERNEL.validate_mechanisms()
        self.kernel = KERNEL.compile_kernel(
            normalized, mechanisms, mechanism_digest, source_digest
        )
        consequential = next(
            cell
            for cell in self.kernel["organization"]["manager_cells"]
            if cell["risk_tier"] == "consequential"
        )
        request = request_fixture(self.kernel, count=1)
        request["manager_admissions"][0]["cell_id"] = consequential["cell_id"]
        state = self.admitted(consequential["cell_id"], request)
        self.assertEqual(state["admission"]["scope"]["decision_mode"], "analysis_only_human_decision")

    def test_noncanonical_request_and_tampered_plan_reject(self):
        request = request_fixture(self.kernel, count=1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kernel_path = root / "kernel.json"
            request_path = root / "request.json"
            plan_path = root / "plan.json"
            kernel_path.write_bytes(RECONCILE.canonical_bytes(self.kernel))
            request_path.write_text(json.dumps(request, indent=2))
            result = subprocess.run(
                [
                    sys.executable,
                    str(RECONCILER_SCRIPT),
                    "plan",
                    "--kernel",
                    str(kernel_path),
                    "--request",
                    str(request_path),
                    "--output",
                    str(plan_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(plan_path.exists())
            request_path.write_bytes(RECONCILE.canonical_bytes(request))
            normalized = self.validated(request)
            plan = RECONCILE.compile_plan(self.kernel, normalized)
            plan["non_claims"]["task_launch_performed"] = True
            plan_path.write_bytes(RECONCILE.canonical_bytes(plan))
            with self.assertRaisesRegex(RECONCILE.ReconciliationError, "does not reproduce"):
                RECONCILE.verify_plan(kernel_path, request_path, plan_path)


if __name__ == "__main__":
    unittest.main()
