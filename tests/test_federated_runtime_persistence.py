from __future__ import annotations

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "company-os" / "compile-federated-company-kernel"
KERNEL_PATH = SKILL / "scripts" / "compile_federated_kernel.py"
RECONCILE_PATH = SKILL / "scripts" / "reconcile_federated_kernel.py"
PERSIST_PATH = SKILL / "scripts" / "persist_federated_runtime.py"
CONTROL_STORE_PATH = (
    ROOT
    / "skills"
    / "company-os"
    / "elastic-company-os"
    / "scripts"
    / "control_store.py"
)
EXAMPLE = SKILL / "references" / "federated-kernel-request.example.json"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


KERNEL = load("federated_kernel_for_persistence_tests", KERNEL_PATH)
RECONCILE = load("federated_reconcile_for_persistence_tests", RECONCILE_PATH)
PERSIST = load("federated_persistence_tests", PERSIST_PATH)
STORE = load("control_store_for_federated_persistence_tests", CONTROL_STORE_PATH)


def compiled_kernel() -> dict:
    raw = json.loads(EXAMPLE.read_text())
    raw["persistence"] = {
        "adapter": "sqlite",
        "dsn_env": None,
        "schema": "company-os",
    }
    request = KERNEL.validate_request(raw)
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


class FederatedRuntimePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name).resolve()
        self.kernel = compiled_kernel()
        self.state = {
            "schema_version": 1,
            "core_version": "test",
            "instance": {
                "project_id": "atlas-project",
                "project_root": str(self.project),
                "status": "paused",
            },
            "strategy": {"program_version": 1},
            "runtime_adapter": {"observation_inboxes": {}, "attempts": []},
        }
        STORE.initialize(
            self.project,
            self.state,
            {
                "at": "2026-08-05T12:00:00+00:00",
                "type": "instance_initialized",
                "project_id": "atlas-project",
                "program_version": 1,
            },
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def validated(self, request: dict) -> dict:
        return RECONCILE.validate_request(request, self.kernel)

    def plan(self, request: dict) -> tuple[dict, dict]:
        normalized = self.validated(request)
        return normalized, RECONCILE.compile_plan(self.kernel, normalized)

    def admitted(self, request: dict, index: int) -> dict:
        admission = request["manager_admissions"][index]
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

    def observe(self, request: dict, states: list[dict]) -> None:
        request["observed_snapshot"] = {
            "$schema": RECONCILE.SNAPSHOT_SCHEMA,
            "last_event_cursor": len(states),
            "attempts": [
                {
                    "event_cursor": index,
                    "native_runtime": state,
                    "role_readback": inconclusive(),
                }
                for index, state in enumerate(states, start=1)
            ],
        }

    def persist(self, request: dict, *, at: str = "2026-08-05T12:01:00+00:00") -> dict:
        normalized, plan = self.plan(request)
        return PERSIST.persist_plan(
            self.project, self.kernel, normalized, plan, created_at=at
        )

    def command_keys(self) -> list[str]:
        return [
            row["message_key"]
            for row in PERSIST.STORE.inspect_outbox(
                self.project, channel=PERSIST.OUTBOX_CHANNEL
            )
        ]

    def test_plan_event_cursor_and_commands_commit_atomically_and_replay(self) -> None:
        request = request_fixture(self.kernel)
        receipt = self.persist(request)
        self.assertFalse(receipt["idempotent"])
        self.assertEqual(receipt["state_revision"], 2)
        self.assertEqual(receipt["enqueued_commands"], 3)
        self.assertEqual(len(self.command_keys()), 3)
        self.assertTrue(STORE.audit(self.project)["ok"])
        report = PERSIST.audit(self.project)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual((report["plans"], report["commands"]), (1, 3))

        retry = self.persist(request, at="2026-08-05T12:02:00+00:00")
        self.assertTrue(retry["idempotent"])
        self.assertEqual(STORE.load(self.project)[0], 2)
        self.assertEqual(len(self.command_keys()), 3)

    def test_injected_failure_rolls_back_schema_plan_event_and_outbox(self) -> None:
        request = request_fixture(self.kernel)
        normalized, plan = self.plan(request)
        with self.assertRaisesRegex(PERSIST.PersistenceError, "injected"):
            PERSIST.persist_plan(
                self.project,
                self.kernel,
                normalized,
                plan,
                created_at="2026-08-05T12:01:00+00:00",
                inject_failure_after=1,
            )
        self.assertEqual(STORE.load(self.project)[0], 1)
        self.assertEqual(STORE.inspect_outbox(self.project), [])
        connection = STORE.connect(self.project)
        try:
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            self.assertNotIn("federated_reconciliation_plans", tables)
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(outbox_messages)")
            }
            self.assertNotIn("lease_generation", columns)
        finally:
            connection.close()

    def test_postgresql_kernel_cannot_silently_fall_back_to_local_sqlite(self) -> None:
        raw = json.loads(EXAMPLE.read_text())
        request = KERNEL.validate_request(raw)
        mechanisms, _sources, mechanism_digest, source_digest = KERNEL.validate_mechanisms()
        postgresql_kernel = KERNEL.compile_kernel(
            request, mechanisms, mechanism_digest, source_digest
        )
        reconciliation = request_fixture(postgresql_kernel, count=1)
        normalized = RECONCILE.validate_request(reconciliation, postgresql_kernel)
        plan = RECONCILE.compile_plan(postgresql_kernel, normalized)
        with self.assertRaisesRegex(PERSIST.PersistenceError, "different persistence adapter"):
            PERSIST.persist_plan(
                self.project,
                postgresql_kernel,
                normalized,
                plan,
                created_at="2026-08-05T12:01:00+00:00",
            )
        self.assertEqual(STORE.load(self.project)[0], 1)
        self.assertEqual(STORE.inspect_outbox(self.project), [])

    def test_cursor_cannot_move_backwards_or_change_bytes_at_same_position(self) -> None:
        request = request_fixture(self.kernel, count=2)
        states = [self.admitted(request, 0), self.admitted(request, 1)]
        self.observe(request, states)
        self.persist(request)

        older = request_fixture(self.kernel, count=2)
        self.observe(older, states[:1])
        normalized, plan = self.plan(older)
        with self.assertRaisesRegex(PERSIST.PersistenceError, "backwards"):
            PERSIST.persist_plan(
                self.project,
                self.kernel,
                normalized,
                plan,
                created_at="2026-08-05T12:02:00+00:00",
            )
        self.assertEqual(STORE.load(self.project)[0], 2)

        changed = deepcopy(request)
        changed_state = RECONCILE.NATIVE.claim_dispatch(states[1])
        changed["observed_snapshot"]["attempts"][1]["native_runtime"] = changed_state
        normalized, plan = self.plan(changed)
        with self.assertRaisesRegex(PERSIST.PersistenceError, "conflicts"):
            PERSIST.persist_plan(
                self.project,
                self.kernel,
                normalized,
                plan,
                created_at="2026-08-05T12:03:00+00:00",
            )
        self.assertEqual(STORE.load(self.project)[0], 2)

    def test_live_lease_blocks_claim_and_cancellation_wins_over_settlement(self) -> None:
        self.persist(request_fixture(self.kernel, count=1))
        key = self.command_keys()[0]
        claim = PERSIST.claim_command(
            self.project,
            key=key,
            owner="dispatcher-a",
            claim_token="secret-a",
            now="2026-08-05T12:02:00+00:00",
            lease_expires_at="2026-08-05T12:12:00+00:00",
        )
        self.assertEqual(claim["lease_generation"], 1)
        with self.assertRaisesRegex(PERSIST.PersistenceError, "live lease"):
            PERSIST.claim_command(
                self.project,
                key=key,
                owner="dispatcher-b",
                claim_token="secret-b",
                now="2026-08-05T12:03:00+00:00",
                lease_expires_at="2026-08-05T12:13:00+00:00",
            )
        with self.assertRaisesRegex(PERSIST.PersistenceError, "fence"):
            PERSIST.settle_command(
                self.project,
                key=key,
                owner="dispatcher-a",
                claim_token="wrong",
                lease_generation=1,
                outcome="succeeded",
                receipt={"result": "wrong"},
                at="2026-08-05T12:04:00+00:00",
            )
        cancelled = PERSIST.cancel_command(
            self.project,
            key=key,
            reason="operator stop",
            at="2026-08-05T12:05:00+00:00",
        )
        self.assertEqual(cancelled["status"], "cancelled")
        late = PERSIST.settle_command(
            self.project,
            key=key,
            owner="dispatcher-a",
            claim_token="secret-a",
            lease_generation=1,
            outcome="succeeded",
            receipt={"result": "late"},
            at="2026-08-05T12:06:00+00:00",
        )
        self.assertEqual(late["status"], "cancelled")
        self.assertTrue(late["idempotent"])
        report = PERSIST.audit(self.project)
        self.assertTrue(report["ok"], report["errors"])

    def test_expired_lease_reclaims_with_new_generation_and_fences_old_worker(self) -> None:
        self.persist(request_fixture(self.kernel, count=1))
        key = self.command_keys()[0]
        first = PERSIST.claim_command(
            self.project,
            key=key,
            owner="dispatcher-a",
            claim_token="secret-a",
            now="2026-08-05T12:02:00+00:00",
            lease_expires_at="2026-08-05T12:03:00+00:00",
        )
        second = PERSIST.claim_command(
            self.project,
            key=key,
            owner="dispatcher-b",
            claim_token="secret-b",
            now="2026-08-05T12:04:00+00:00",
            lease_expires_at="2026-08-05T12:14:00+00:00",
        )
        self.assertEqual((first["lease_generation"], second["lease_generation"]), (1, 2))
        with self.assertRaisesRegex(PERSIST.PersistenceError, "fence"):
            PERSIST.settle_command(
                self.project,
                key=key,
                owner="dispatcher-a",
                claim_token="secret-a",
                lease_generation=1,
                outcome="succeeded",
                receipt={"result": "stale"},
                at="2026-08-05T12:05:00+00:00",
            )
        settled = PERSIST.settle_command(
            self.project,
            key=key,
            owner="dispatcher-b",
            claim_token="secret-b",
            lease_generation=2,
            outcome="succeeded",
            receipt={"result": "accepted"},
            at="2026-08-05T12:06:00+00:00",
        )
        self.assertEqual(settled["status"], "succeeded")
        self.assertTrue(PERSIST.audit(self.project)["ok"])

    def test_tampered_plan_or_command_fails_extension_audit(self) -> None:
        self.persist(request_fixture(self.kernel, count=1))
        connection = STORE.connect(self.project)
        try:
            connection.execute(
                "UPDATE outbox_messages SET payload_json='{}' WHERE channel=?",
                (PERSIST.OUTBOX_CHANNEL,),
            )
            connection.commit()
        finally:
            connection.close()
        report = PERSIST.audit(self.project)
        self.assertFalse(report["ok"])
        self.assertTrue(
            any("command" in error or "control store" in error for error in report["errors"])
        )

    def test_conflicted_plan_is_retained_without_dispatchable_commands(self) -> None:
        request = request_fixture(self.kernel, count=1)
        admission = request["manager_admissions"][0]
        cell = next(
            item
            for item in self.kernel["organization"]["manager_cells"]
            if item["cell_id"] == admission["cell_id"]
        )
        drifted = RECONCILE.admitted_state(
            kernel=self.kernel,
            cell=cell,
            generation=request["generation"],
            project_id=request["project_id"],
            cycle_id=request["cycle_id"],
            parent_runtime_id=request["parent_runtime_id"],
            budget=budget(tokens=999),
        )
        self.observe(request, [drifted])
        normalized, plan = self.plan(request)
        self.assertEqual(plan["status"], "blocked")
        receipt = PERSIST.persist_plan(
            self.project,
            self.kernel,
            normalized,
            plan,
            created_at="2026-08-05T12:01:00+00:00",
        )
        self.assertEqual(receipt["enqueued_commands"], 0)
        self.assertEqual(self.command_keys(), [])
        self.assertTrue(PERSIST.audit(self.project)["ok"])

    def test_concurrent_claims_have_exactly_one_winner(self) -> None:
        self.persist(request_fixture(self.kernel, count=1))
        key = self.command_keys()[0]
        barrier = threading.Barrier(2)

        def contender(index: int) -> str:
            barrier.wait()
            try:
                PERSIST.claim_command(
                    self.project,
                    key=key,
                    owner=f"dispatcher-{index}",
                    claim_token=f"secret-{index}",
                    now="2026-08-05T12:02:00+00:00",
                    lease_expires_at="2026-08-05T12:12:00+00:00",
                )
                return "claimed"
            except PERSIST.PersistenceError:
                return "rejected"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(contender, (1, 2)))
        self.assertEqual(sorted(outcomes), ["claimed", "rejected"])
        rows = STORE.inspect_outbox(self.project, channel=PERSIST.OUTBOX_CHANNEL)
        self.assertEqual(rows[0]["status"], "leased")
        self.assertEqual(rows[0]["attempt_count"], 1)
        self.assertTrue(PERSIST.audit(self.project)["ok"])


if __name__ == "__main__":
    unittest.main()
