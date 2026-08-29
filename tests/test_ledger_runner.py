"""The runner and the v1.3 change signal: triggers, cursor, webhook trust.

The runner is what makes the platform autonomous — so its decisions are
pinned: cadence fires on the clock, kind-watch fires only on watched main
commits, feedback thresholds accumulate across polls, every emitted work
order carries a sealed bundle, and the state cursor advances so a restart
never replays old signals. Webhook signatures verify over exact raw bytes,
constant-time, and reject everything else.
"""
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = "skills/company-os/company-context-ledger/scripts"


def _load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The runner does `from context_ledger import …`; register the client module
# under its plain name first so the sibling import resolves to the same code.
LEDGER = _load(f"{SCRIPTS}/context_ledger.py", "context_ledger")
RUNNER = _load(f"{SCRIPTS}/ledger_runner.py", "ledger_runner_under_test")


class WebhookSignatureTests(unittest.TestCase):
    def test_valid_signature_verifies(self) -> None:
        body = b'{"event":"document_committed","company":"acme"}'
        signature = "sha256=" + hmac.new(b"whsec_abc", body, hashlib.sha256).hexdigest()
        self.assertTrue(LEDGER.verify_webhook_signature("whsec_abc", body, signature))

    def test_wrong_secret_or_tampered_body_fails(self) -> None:
        body = b'{"event":"document_committed"}'
        signature = "sha256=" + hmac.new(b"whsec_abc", body, hashlib.sha256).hexdigest()
        self.assertFalse(LEDGER.verify_webhook_signature("whsec_other", body, signature))
        self.assertFalse(
            LEDGER.verify_webhook_signature("whsec_abc", body + b" ", signature)
        )

    def test_malformed_header_fails_closed(self) -> None:
        self.assertFalse(LEDGER.verify_webhook_signature("s", b"x", ""))
        self.assertFalse(LEDGER.verify_webhook_signature("s", b"x", "md5=abc"))
        self.assertFalse(LEDGER.verify_webhook_signature("s", b"x", "deadbeef"))


class ContextChangesWireTests(unittest.TestCase):
    def test_changes_verb_shapes_arguments_and_returns_page(self) -> None:
        requests: list[dict[str, Any]] = []
        page = {"cursor": 42.5, "has_more": False, "events": [{"type": "run_event"}]}

        def transport(payload: dict[str, Any]) -> dict[str, Any]:
            requests.append(payload)
            return {"jsonrpc": "2.0", "id": 1, "result": {"structuredContent": page}}

        client = LEDGER.ContextLedgerClient(
            "https://ledger.example/mcp", "cos_test", transport=transport
        )
        result = client.context_changes(since=7, limit=50)
        self.assertEqual(result, page)
        self.assertEqual(requests[0]["params"]["name"], "context_changes")
        self.assertEqual(requests[0]["params"]["arguments"], {"since": 7, "limit": 50})
        client.context_changes()
        self.assertEqual(requests[1]["params"]["arguments"], {})


class FakeLedger:
    """Scripted client: change pages in, tool calls recorded out."""

    def __init__(self, pages: list[dict[str, Any]]):
        self.pages = pages
        self.bundle_calls: list[str] = []
        self.appended: list[dict[str, Any]] = []

    def context_changes(self, *, since=None, limit=None):
        if self.pages:
            return self.pages.pop(0)
        return {"cursor": since or 0, "has_more": False, "events": []}

    def bundle_for(self, work_class: str):
        self.bundle_calls.append(work_class)
        return {
            "protocol": "context-ledger.v1",
            "documents": [],
            "bundle_sha256": f"sha-for-{work_class}",
        }

    def run_append(self, **kwargs):
        self.appended.append(kwargs)
        return {"run_id": kwargs.get("run_id")}


def make_runner(
    tmp: Path,
    triggers: list[dict[str, Any]],
    pages: list[dict[str, Any]],
    now: float,
) -> tuple[Any, FakeLedger]:
    fake = FakeLedger(pages)
    runner = RUNNER.LedgerRunner(
        fake,  # duck-typed client: only the three verbs the runner uses
        {"run_id": "runner-test", "triggers": triggers},
        state_path=tmp / "state.json",
        queue_dir=tmp / "queue",
        now=lambda: now,
    )
    return runner, fake


class RunnerTriggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def test_config_validation_fails_closed(self) -> None:
        for bad in (
            {},
            {"triggers": []},
            {"triggers": [{"type": "cadence", "work_class": "sales"}]},
            {"triggers": [{"name": "x", "type": "mystery", "work_class": "sales"}]},
            {"triggers": [{"name": "x", "type": "cadence", "work_class": "sales"}]},
        ):
            with self.assertRaises(RUNNER.RunnerConfigError):
                RUNNER.load_triggers(bad)

    def test_cadence_fires_then_waits_out_the_interval(self) -> None:
        trigger = {
            "name": "daily",
            "type": "cadence",
            "work_class": "marketing",
            "every_seconds": 3600,
        }
        runner, fake = make_runner(self.tmp, [trigger], [], now=1000.0)
        orders = runner.poll()
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["work_class"], "marketing")
        self.assertEqual(orders[0]["bundle_sha256"], "sha-for-marketing")
        # Same clock: nothing new fires; the state file remembers the firing.
        runner2 = RUNNER.LedgerRunner(
            fake,
            {"run_id": "runner-test", "triggers": [trigger]},
            state_path=self.tmp / "state.json",
            queue_dir=self.tmp / "queue",
            now=lambda: 1500.0,
        )
        self.assertEqual(runner2.poll(), [])

    def test_context_change_fires_only_on_watched_main_commits(self) -> None:
        trigger = {
            "name": "sales-watch",
            "type": "context_change",
            "work_class": "sales",
            "kinds": ["icp", "sales-process"],
        }
        pages = [
            {
                "cursor": 10,
                "has_more": False,
                "events": [
                    {"type": "document_committed", "kind": "okrs", "branch": "main"},
                    {"type": "document_committed", "kind": "icp", "branch": "draft-x"},
                ],
            }
        ]
        runner, _ = make_runner(self.tmp, [trigger], pages, now=1.0)
        self.assertEqual(runner.poll(), [])  # wrong kind on main, right kind on a branch

        pages2 = [
            {
                "cursor": 20,
                "has_more": False,
                "events": [
                    {"type": "document_committed", "kind": "icp", "branch": "main"}
                ],
            }
        ]
        runner2, fake2 = make_runner(self.tmp, [trigger], pages2, now=2.0)
        orders = runner2.poll()
        self.assertEqual(len(orders), 1)
        self.assertIn("icp", orders[0]["reason"])
        self.assertEqual(fake2.bundle_calls, ["sales"])

    def test_feedback_threshold_accumulates_across_polls(self) -> None:
        trigger = {
            "name": "fb",
            "type": "feedback_threshold",
            "work_class": "evaluation",
            "min_items": 3,
        }
        first = [
            {
                "cursor": 5,
                "has_more": False,
                "events": [{"type": "feedback_added"}, {"type": "feedback_added"}],
            }
        ]
        runner, _ = make_runner(self.tmp, [trigger], first, now=1.0)
        self.assertEqual(runner.poll(), [])  # 2 < 3, carried in state

        second = [
            {"cursor": 6, "has_more": False, "events": [{"type": "feedback_added"}]}
        ]
        runner2, _ = make_runner(self.tmp, [trigger], second, now=2.0)
        orders = runner2.poll()
        self.assertEqual(len(orders), 1)
        self.assertIn("3 unprocessed", orders[0]["reason"])
        state = json.loads((self.tmp / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["feedback_pending"]["fb"], 0)

    def test_cursor_advances_and_pages_drain(self) -> None:
        trigger = {
            "name": "daily",
            "type": "cadence",
            "work_class": "research",
            "every_seconds": 10,
        }
        pages = [
            {"cursor": 100, "has_more": True, "events": [{"type": "run_event"}]},
            {"cursor": 200, "has_more": False, "events": []},
        ]
        runner, fake = make_runner(self.tmp, [trigger], pages, now=50.0)
        orders = runner.poll()
        self.assertEqual(runner.state["cursor"], 200)
        # The work order file on disk is the queue contract.
        path = self.tmp / "queue" / f"{orders[0]['order_id']}.json"
        written = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(written["bundle"]["bundle_sha256"], "sha-for-research")
        # Telemetry went to run_append with the bundle's seal, not its content.
        self.assertEqual(fake.appended[0]["type"], "runner_work_order")
        self.assertEqual(
            fake.appended[0]["payload"]["bundle_sha256"], "sha-for-research"
        )


if __name__ == "__main__":
    unittest.main()
