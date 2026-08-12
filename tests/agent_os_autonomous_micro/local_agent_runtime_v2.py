#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from typing import Any, Mapping

import local_agent_runtime as base


class CompactOllamaClient(base.OllamaClient):
    def _bounded_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not messages:
            return []
        system = dict(messages[0])
        if isinstance(system.get("content"), str):
            system["content"] = base.truncate(system["content"], 12000)
        tail: list[dict[str, Any]] = []
        for raw in messages[-10:]:
            item = dict(raw)
            if isinstance(item.get("content"), str):
                item["content"] = base.truncate(item["content"], 5500)
            tail.append(item)
        if tail and tail[0] == system:
            return tail
        return [system, *tail]

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        bounded_messages = self._bounded_messages(messages)
        payload = {
            "model": self.model,
            "messages": bounded_messages,
            "tools": tools,
            "stream": False,
            "keep_alive": "15m",
            "options": {
                "temperature": 0.08,
                "num_ctx": 8192,
                "num_predict": 480,
            },
        }
        request = urllib.request.Request(
            self.endpoint + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                body = json.load(response)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise base.AgentRuntimeError(
                f"model request failed after {round(time.monotonic() - started, 1)} seconds: {exc}"
            ) from exc
        message = body.get("message")
        if not isinstance(message, dict):
            raise base.AgentRuntimeError(f"model returned no message: {body}")
        return dict(message)


class CompactAgentOSRuntime(base.AgentOSRuntime):
    def __init__(self, workspace: Path, objective: str, model: str) -> None:
        super().__init__(workspace, objective, model=model)
        self.client = CompactOllamaClient(model=model)
        self.packet_root = self.workspace / ".company-os-test/agent-packets"
        self.packet_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _selected(mapping: Mapping[str, Any], keys: list[str]) -> dict[str, Any]:
        return {key: mapping[key] for key in keys if key in mapping}

    def _packet_record(self, packet: Mapping[str, Any], role: str) -> tuple[str, str]:
        actor_id = str(packet.get("id") or role)
        packet_sha = base.digest(packet)
        safe_actor = re.sub(r"[^a-zA-Z0-9_.]+", "-", actor_id).strip("-") or role
        path = self.packet_root / f"{safe_actor}-{packet_sha[:12]}.json"
        if not path.exists():
            base.write_json(path, dict(packet))
        return base.relative(self.workspace, path), packet_sha

    def _compact_worker(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        context = packet.get("outcome_context")
        context = dict(context) if isinstance(context, Mapping) else {}
        mission = packet.get("mission_control")
        mission = dict(mission) if isinstance(mission, Mapping) else {}
        navigation = mission.get("navigation")
        navigation = dict(navigation) if isinstance(navigation, Mapping) else {}
        return {
            **self._selected(packet, [
                "id",
                "model",
                "task",
                "acceptance",
                "write_scope",
                "risk",
                "budget",
                "work_class",
                "stop_condition",
                "artifact_classes",
                "outcome_loop_lane_id",
                "outcome_loop_lane_sha256",
            ]),
            "outcome_context": self._selected(context, [
                "program_outcome",
                "manager_outcome",
                "user_value",
                "roadmap_position",
                "artifact_classes",
                "dependencies",
                "non_goals",
                "constraints",
                "execution_policy",
                "evaluator_id",
                "score_dimensions",
            ]),
            "navigation": self._selected(navigation, [
                "mode",
                "waypoint",
                "position",
                "next_action",
                "orders",
                "sensor_posture",
                "actuation_policy",
            ]),
        }

    def _compact_manager(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        mission = packet.get("mission_control")
        mission = dict(mission) if isinstance(mission, Mapping) else {}
        navigation = mission.get("navigation")
        navigation = dict(navigation) if isinstance(navigation, Mapping) else {}
        workers = packet.get("workers")
        worker_summaries = []
        if isinstance(workers, list):
            for worker in workers:
                if not isinstance(worker, Mapping):
                    continue
                worker_summaries.append(self._selected(worker, [
                    "id",
                    "model",
                    "task",
                    "acceptance",
                    "write_scope",
                    "budget",
                    "work_class",
                    "stop_condition",
                ]))
        return {
            **self._selected(packet, [
                "id",
                "model",
                "outcome",
                "acceptance",
                "phase_ids",
                "budget",
                "work_class",
                "write_scope",
                "artifact_classes",
                "outcome_loop_lane_id",
                "outcome_loop_lane_sha256",
            ]),
            "navigation": self._selected(navigation, [
                "mode",
                "waypoint",
                "position",
                "next_action",
                "orders",
                "sensor_posture",
                "actuation_policy",
            ]),
            "workers": worker_summaries,
        }

    def worker_system_prompt(self, packet: Mapping[str, Any], rework_defect: str | None = None) -> str:
        packet_path, packet_sha = self._packet_record(packet, "worker")
        compact = self._compact_worker(packet)
        rework = f"\nTargeted rework defect: {rework_defect}\n" if rework_defect else ""
        return f"""You are a real Company OS worker in an isolated workspace.

Original objective:
{self.objective}

Bound worker packet digest: {packet_sha}
Exact packet file: {packet_path}
Compact task-local packet:
{json.dumps(compact, indent=2, sort_keys=True)}
{rework}
The exact packet file is authoritative. Read it only when a field missing from the compact view is required to execute safely.

Act through tools. Read the actual workspace, then perform the smallest sufficient state-changing action inside write_scope. Plans and prose do not count. Implementation work must create real bytes, run them, observe behavior, and write the required canonical receipt or handoff. A worker that creates a runnable product must call register_product after observing it. Research must be limited to its assigned live blocker and must produce the exact cited proposal. Evaluation must preserve candidate bytes.

Never cut explicit requirements, validation, persistence, accessibility, security, error handling, tests, runtime evidence, or independent verification. finish_worker is the only valid completion signal.

Use exactly one tool per response. Return either a native tool call or only:
{{"name":"tool_name","arguments":{{...}}}}
"""

    def manager_system_prompt(self, packet: Mapping[str, Any]) -> str:
        packet_path, packet_sha = self._packet_record(packet, "manager")
        compact = self._compact_manager(packet)
        return f"""You are a real Company OS manager in an isolated workspace.

Original objective:
{self.objective}

Bound manager packet digest: {packet_sha}
Exact packet file: {packet_path}
Compact manager packet:
{json.dumps(compact, indent=2, sort_keys=True)}

The exact packet file is authoritative. Immediately use spawn_worker for each listed worker. Each call creates a separate model thread from the exact bound worker packet. Do not write product code yourself.

After workers return, inspect actual bytes and behavior. A completion narrative is not evidence. Request at most one targeted rework for a concrete dominant defect. Do not expand scope or replace execution with generic research, architecture, audits, or documentation. finish_manager accepted is valid only after every listed worker has an accepted evidence receipt.

Use exactly one tool per response. Return either a native tool call or only:
{{"name":"tool_name","arguments":{{...}}}}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--objective-file", type=Path, required=True)
    parser.add_argument("--model", default=os.environ.get("AGENT_MODEL", "qwen2.5-coder:3b"))
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    objective = args.objective_file.resolve().read_text(encoding="utf-8").strip()
    runtime = CompactAgentOSRuntime(workspace, objective, model=args.model)
    try:
        result = runtime.run_mission()
    except Exception as exc:
        for thread in runtime.threads:
            if thread.get("status") == "running":
                thread["status"] = "blocked"
                thread["result"] = {
                    "status": "blocked",
                    "blocker": f"Provider adapter failure: {type(exc).__name__}: {exc}",
                }
        runtime.blocker = f"Uncaught local agent runtime failure: {type(exc).__name__}: {exc}"
        result = runtime.finalize_result("blocked", runtime.blocker)
    finally:
        runtime.stop_all_processes()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
