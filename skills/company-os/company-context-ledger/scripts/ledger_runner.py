#!/usr/bin/env python3
"""The runner: the ledger's change signal turned into framework work.

This is the piece that makes the platform autonomous instead of a filing
cabinet: a small loop that watches the company's context ledger and decides
when work should happen. Three declarative trigger types:

- ``cadence``            — run a work class every N seconds (the routine).
- ``feedback_threshold`` — run when unprocessed feedback piles up.
- ``context_change``     — run when a commit lands on watched kinds.

The runner's output is a **work order**: a JSON file in the queue directory
carrying the reason it fired and a sealed ``bundle_for`` context bundle,
ready for ``mission_control.bind_context`` (which re-verifies every hash
offline, fail-closed). Authority boundary, preserved: the runner never
dispatches, leases, or accepts anything. A work order is an invitation to
run the mission loop; ``mission-execution-control`` remains the single
dispatch boundary that consumes it.

Configuration (JSON)::

    {
      "run_id": "runner-main",
      "triggers": [
        {"name": "daily-marketing", "type": "cadence",
         "work_class": "marketing", "every_seconds": 86400},
        {"name": "feedback-sweep", "type": "feedback_threshold",
         "work_class": "evaluation", "min_items": 10},
        {"name": "sales-context", "type": "context_change",
         "work_class": "sales", "kinds": ["icp", "sales-process", "battle-card"]}
      ]
    }

State (cursor, cadence clocks, feedback counters) persists in a JSON file,
so the loop survives restarts without replaying old signals.
"""
from __future__ import annotations

import argparse
import json
import time
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

from context_ledger import ContextLedgerClient, ContextLedgerError

VALID_TRIGGER_TYPES = ("cadence", "feedback_threshold", "context_change")
MAX_CHANGE_PAGES = 10


class RunnerConfigError(ValueError):
    """The trigger configuration is malformed; refuse to run on guesses."""


def load_triggers(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate the trigger list fail-closed: a bad trigger stops the runner."""
    triggers = config.get("triggers")
    if not isinstance(triggers, list) or not triggers:
        raise RunnerConfigError("config needs a non-empty 'triggers' list")
    seen_names: set[str] = set()
    for trigger in triggers:
        if not isinstance(trigger, dict):
            raise RunnerConfigError("each trigger must be an object")
        name = trigger.get("name")
        kind = trigger.get("type")
        if not isinstance(name, str) or not name:
            raise RunnerConfigError("every trigger needs a 'name'")
        if name in seen_names:
            raise RunnerConfigError(f"duplicate trigger name '{name}'")
        seen_names.add(name)
        if kind not in VALID_TRIGGER_TYPES:
            raise RunnerConfigError(f"trigger '{name}' has unknown type '{kind}'")
        if not isinstance(trigger.get("work_class"), str):
            raise RunnerConfigError(f"trigger '{name}' needs a 'work_class'")
        if kind == "cadence" and not isinstance(trigger.get("every_seconds"), (int, float)):
            raise RunnerConfigError(f"cadence trigger '{name}' needs 'every_seconds'")
        if kind == "feedback_threshold" and not isinstance(trigger.get("min_items"), int):
            raise RunnerConfigError(f"feedback trigger '{name}' needs integer 'min_items'")
        if kind == "context_change":
            kinds = trigger.get("kinds")
            if not isinstance(kinds, list) or not all(isinstance(k, str) for k in kinds):
                raise RunnerConfigError(f"context_change trigger '{name}' needs 'kinds'")
    return triggers


class LedgerRunner:
    """One poll = read the change signal, evaluate triggers, emit work orders."""

    def __init__(
        self,
        client: ContextLedgerClient,
        config: dict[str, Any],
        *,
        state_path: Path,
        queue_dir: Path,
        now: Callable[[], float] = time.time,
        telemetry: bool = True,
    ):
        self.client = client
        self.run_id = str(config.get("run_id") or "runner-main")
        self.triggers = load_triggers(config)
        self.state_path = state_path
        self.queue_dir = queue_dir
        self.now = now
        self.telemetry = telemetry
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(state, dict):
                return state
        return {"cursor": 0, "last_fired": {}, "feedback_pending": {}}

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def _pull_changes(self) -> list[dict[str, Any]]:
        """Drain the change cursor (bounded pages), advancing state['cursor']."""
        events: list[dict[str, Any]] = []
        for _ in range(MAX_CHANGE_PAGES):
            page = self.client.context_changes(since=self.state.get("cursor") or 0)
            events.extend(page.get("events", []))
            self.state["cursor"] = page.get("cursor", self.state.get("cursor", 0))
            if not page.get("has_more"):
                break
        return events

    def _emit(self, trigger: dict[str, Any], reason: str) -> dict[str, Any]:
        """One work order: reason + sealed context bundle, queued as a file."""
        work_class = trigger["work_class"]
        bundle = self.client.bundle_for(work_class)
        order = {
            "order_id": f"wo-{uuid.uuid4().hex[:12]}",
            "run_id": self.run_id,
            "trigger": trigger["name"],
            "trigger_type": trigger["type"],
            "work_class": work_class,
            "reason": reason,
            "created_at": self.now(),
            "bundle_sha256": bundle["bundle_sha256"],
            "bundle": bundle,
        }
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        path = self.queue_dir / f"{order['order_id']}.json"
        path.write_text(json.dumps(order, indent=2) + "\n", encoding="utf-8")
        if self.telemetry:
            try:
                self.client.run_append(
                    run_id=self.run_id,
                    type="runner_work_order",
                    payload={
                        "order_id": order["order_id"],
                        "trigger": trigger["name"],
                        "work_class": work_class,
                        "reason": reason,
                        "bundle_sha256": bundle["bundle_sha256"],
                    },
                    summary=f"Runner: {trigger['name']} → {work_class} ({reason})",
                )
            except ContextLedgerError as exc:
                order["telemetry_error"] = str(exc)
        return order

    def poll(self) -> list[dict[str, Any]]:
        """Evaluate every trigger against the clock and the change signal."""
        now = self.now()
        events = self._pull_changes()
        last_fired: dict[str, Any] = self.state.setdefault("last_fired", {})
        pending: dict[str, Any] = self.state.setdefault("feedback_pending", {})

        # Tally this page's signal once, then let each trigger read it.
        committed_kinds = {
            event.get("kind")
            for event in events
            if event.get("type") == "document_committed" and event.get("branch") in (None, "main")
        }
        feedback_events = [e for e in events if e.get("type") == "feedback_added"]

        orders: list[dict[str, Any]] = []
        for trigger in self.triggers:
            name = trigger["name"]
            if trigger["type"] == "cadence":
                last = last_fired.get(name)
                # Never fired = fire now: a routine starts when it is adopted.
                if last is None or now - float(last) >= float(trigger["every_seconds"]):
                    orders.append(self._emit(trigger, "cadence elapsed"))
                    last_fired[name] = now
            elif trigger["type"] == "context_change":
                hits = sorted(committed_kinds & set(trigger["kinds"]))
                # One order per poll however many watched commits landed —
                # the mission reads current state, not the event backlog.
                if hits:
                    orders.append(
                        self._emit(trigger, f"watched kinds committed: {', '.join(hits)}")
                    )
                    last_fired[name] = now
            else:  # feedback_threshold
                count = int(pending.get(name, 0)) + len(feedback_events)
                if count >= int(trigger["min_items"]):
                    orders.append(
                        self._emit(trigger, f"{count} unprocessed feedback items")
                    )
                    pending[name] = 0
                    last_fired[name] = now
                else:
                    pending[name] = count

        self._save_state()
        return orders


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="ledger MCP endpoint (…/mcp)")
    parser.add_argument("--token", required=True, help="cos_ agent key (write scope for telemetry)")
    parser.add_argument("--config", required=True, help="trigger config JSON file")
    parser.add_argument("--state", required=True, help="cursor/clock state JSON file")
    parser.add_argument("--queue", required=True, help="directory work orders land in")
    parser.add_argument("--no-telemetry", action="store_true", help="skip run_append events")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("once", help="one poll, then exit")
    loop_parser = commands.add_parser("loop", help="poll forever")
    loop_parser.add_argument("--interval", type=float, default=300.0)
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    runner = LedgerRunner(
        ContextLedgerClient(args.url, args.token),
        config,
        state_path=Path(args.state),
        queue_dir=Path(args.queue),
        telemetry=not args.no_telemetry,
    )

    def poll_once() -> None:
        try:
            orders = runner.poll()
        except ContextLedgerError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}))
            return
        print(
            json.dumps(
                {
                    "ok": True,
                    "orders": [
                        {k: order[k] for k in ("order_id", "trigger", "work_class", "reason")}
                        for order in orders
                    ],
                    "cursor": runner.state.get("cursor"),
                }
            )
        )

    if args.command == "once":
        poll_once()
    else:
        while True:
            poll_once()
            time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
