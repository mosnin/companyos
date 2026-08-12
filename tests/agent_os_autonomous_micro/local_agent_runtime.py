#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Mapping

OBJECTIVE_ID = "signal-notes-micro"
DEFAULT_MODEL = os.environ.get("AGENT_MODEL", "qwen2.5-coder:3b")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MAX_AGENT_TURNS = int(os.environ.get("MAX_AGENT_TURNS", "16"))
MAX_MISSION_CYCLES = int(os.environ.get("MAX_MISSION_CYCLES", "12"))
MAX_OUTPUT_CHARS = 14000

PROTECTED_PREFIXES = (
    ".git",
    ".codex/skills",
)
PROTECTED_FILES = {
    "OBJECTIVE.md",
    "AGENTS.md",
}
COMMAND_ALLOWLIST = {
    "python",
    "python3",
    "node",
    "npm",
    "git",
    "ls",
    "find",
    "grep",
    "cat",
    "sed",
    "awk",
    "sha256sum",
    "mkdir",
    "cp",
    "mv",
    "pwd",
    "test",
    "true",
    "false",
}
BLOCKED_COMMAND_PAIRS = {
    ("git", "push"),
    ("git", "fetch"),
    ("git", "pull"),
    ("git", "clone"),
    ("git", "remote"),
    ("npm", "install"),
    ("npm", "i"),
    ("npm", "add"),
}
ALLOWED_ENV_KEYS = {
    "PORT",
    "HOST",
    "NODE_ENV",
    "PYTHONUNBUFFERED",
    "PYTHONPATH",
}


class AgentRuntimeError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def truncate(value: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(value) <= limit:
        return value
    half = max(1, limit // 2)
    return value[:half] + "\n...[truncated]...\n" + value[-half:]


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AgentRuntimeError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_path(root: Path, raw: str, *, allow_missing: bool = True) -> Path:
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
        raise AgentRuntimeError("path must be a nonempty string")
    raw_path = Path(raw)
    if raw_path.is_absolute():
        candidate = raw_path.resolve()
    else:
        candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise AgentRuntimeError(f"path escapes workspace: {raw}") from exc
    if not allow_missing and not candidate.exists():
        raise AgentRuntimeError(f"path does not exist: {raw}")
    return candidate


def relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def is_protected(relative_path: str) -> bool:
    normalized = relative_path.strip("/")
    if normalized in PROTECTED_FILES:
        return True
    return any(normalized == prefix or normalized.startswith(prefix + "/") for prefix in PROTECTED_PREFIXES)


def scope_allows(relative_path: str, scopes: list[str]) -> bool:
    target = relative_path.strip("/")
    if is_protected(target):
        return False
    for raw_scope in scopes:
        if not isinstance(raw_scope, str) or not raw_scope.strip():
            continue
        scope = raw_scope.strip().strip("/")
        if scope in {".", ""}:
            return True
        scope_name = Path(scope).name
        exact_file = bool(Path(scope).suffix) or scope_name in {
            "package.json",
            "package-lock.json",
            "pyproject.toml",
            "requirements.txt",
        }
        if exact_file and target == scope:
            return True
        if not exact_file and (target == scope or target.startswith(scope + "/")):
            return True
    return False


def unwrap_arguments(value: Any) -> Any:
    if isinstance(value, list):
        return [unwrap_arguments(item) for item in value]
    if isinstance(value, dict):
        if "value" in value and set(value).issubset({"type", "value", "description"}):
            return unwrap_arguments(value["value"])
        return {str(key): unwrap_arguments(item) for key, item in value.items()}
    return value


def parse_json_object(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.I)
        candidate = re.sub(r"\s*```$", "", candidate)
    attempts = [candidate]
    if "{" in candidate and "}" in candidate:
        attempts.append(candidate[candidate.find("{"):candidate.rfind("}") + 1])
    for attempt in attempts:
        if not attempt:
            continue
        try:
            value = json.loads(attempt)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def extract_actions(message: Mapping[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    raw_calls = message.get("tool_calls")
    if isinstance(raw_calls, list):
        for raw_call in raw_calls:
            if not isinstance(raw_call, Mapping):
                continue
            function = raw_call.get("function")
            if not isinstance(function, Mapping):
                continue
            name = function.get("name")
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                parsed = parse_json_object(arguments)
                arguments = parsed if parsed is not None else {}
            if isinstance(name, str) and isinstance(arguments, Mapping):
                actions.append({"name": name, "arguments": unwrap_arguments(dict(arguments))})
    if actions:
        return actions

    content = message.get("content")
    if not isinstance(content, str):
        return []
    envelope = parse_json_object(content)
    if not isinstance(envelope, dict):
        return []
    if isinstance(envelope.get("function"), Mapping):
        function = envelope["function"]
        name = function.get("name")
        arguments = function.get("arguments", {})
    else:
        name = envelope.get("name") or envelope.get("tool")
        arguments = envelope.get("arguments", envelope.get("args", envelope.get("parameters", {})))
    if isinstance(arguments, str):
        parsed = parse_json_object(arguments)
        arguments = parsed if parsed is not None else {}
    if isinstance(name, str) and isinstance(arguments, Mapping):
        return [{"name": name, "arguments": unwrap_arguments(dict(arguments))}]
    return []


def tool_schema(name: str, description: str, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
                "additionalProperties": False,
            },
        },
    }


class OllamaClient:
    def __init__(self, model: str = DEFAULT_MODEL, endpoint: str = OLLAMA_URL) -> None:
        self.model = model
        self.endpoint = endpoint.rstrip("/")

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": {
                "temperature": 0.12,
                "num_ctx": 16384,
                "num_predict": 1000,
            },
        }
        request = urllib.request.Request(
            self.endpoint + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                body = json.load(response)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise AgentRuntimeError(f"model request failed: {exc}") from exc
        message = body.get("message")
        if not isinstance(message, dict):
            raise AgentRuntimeError(f"model returned no message: {body}")
        return dict(message)


class AgentOSRuntime:
    def __init__(self, workspace: Path, objective: str, model: str = DEFAULT_MODEL) -> None:
        self.workspace = workspace.resolve()
        self.objective = objective.strip()
        self.client = OllamaClient(model=model)
        self.trace_path = self.workspace / ".company-os-test/agent-trace.jsonl"
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self.threads: list[dict[str, Any]] = []
        self.worker_results: dict[str, dict[str, Any]] = {}
        self.product_registration: dict[str, Any] | None = None
        self.evidence_paths: set[str] = set()
        self.processes: dict[str, subprocess.Popen[str]] = {}
        self.process_logs: dict[str, Any] = {}
        self.dispatched_fabric_digests: set[str] = set()
        self.root_product_writes: list[str] = []
        self.blocker: str | None = None

    def trace(self, event: str, **payload: Any) -> None:
        record = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": event,
            **payload,
        }
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def run_command(
        self,
        argv: list[str],
        *,
        cwd: str = ".",
        timeout_seconds: int = 90,
        env: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
            raise AgentRuntimeError("argv must be a nonempty string array")
        executable = Path(argv[0]).name
        if executable not in COMMAND_ALLOWLIST:
            raise AgentRuntimeError(f"command is not allowed: {executable}")
        if len(argv) >= 2 and (executable, argv[1]) in BLOCKED_COMMAND_PAIRS:
            raise AgentRuntimeError(f"command pair is not allowed: {executable} {argv[1]}")
        if executable in {"python", "python3"} and len(argv) >= 3 and argv[1] == "-m" and argv[2] in {"pip", "ensurepip", "venv"}:
            raise AgentRuntimeError(f"python module is not allowed: {argv[2]}")
        cwd_path = safe_path(self.workspace, cwd, allow_missing=False)
        if not cwd_path.is_dir():
            raise AgentRuntimeError(f"cwd is not a directory: {cwd}")
        bounded_timeout = max(1, min(int(timeout_seconds), 180))
        environment = os.environ.copy()
        for key, value in (env or {}).items():
            if key not in ALLOWED_ENV_KEYS:
                raise AgentRuntimeError(f"environment key is not allowed: {key}")
            environment[key] = str(value)
        started = time.monotonic()
        result = subprocess.run(
            argv,
            cwd=cwd_path,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=bounded_timeout,
        )
        return {
            "argv": argv,
            "cwd": relative(self.workspace, cwd_path) or ".",
            "exit_code": result.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "output": truncate(result.stdout or ""),
        }

    def start_process(
        self,
        argv: list[str],
        *,
        cwd: str = ".",
        env: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
            raise AgentRuntimeError("argv must be a nonempty string array")
        executable = Path(argv[0]).name
        if executable not in {"python", "python3", "node", "npm"}:
            raise AgentRuntimeError(f"background command is not allowed: {executable}")
        if executable == "npm" and len(argv) >= 2 and argv[1] in {"install", "i", "add"}:
            raise AgentRuntimeError("dependency installation is not allowed")
        cwd_path = safe_path(self.workspace, cwd, allow_missing=False)
        environment = os.environ.copy()
        for key, value in (env or {}).items():
            if key not in ALLOWED_ENV_KEYS:
                raise AgentRuntimeError(f"environment key is not allowed: {key}")
            environment[key] = str(value)
        process_id = str(uuid.uuid4())
        log_path = self.workspace / f".company-os-test/process-{process_id}.log"
        log_handle = log_path.open("w", encoding="utf-8")
        process = subprocess.Popen(
            argv,
            cwd=cwd_path,
            env=environment,
            text=True,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        self.processes[process_id] = process
        self.process_logs[process_id] = log_handle
        time.sleep(0.5)
        return {
            "process_id": process_id,
            "pid": process.pid,
            "running": process.poll() is None,
            "exit_code": process.poll(),
            "log_path": relative(self.workspace, log_path),
        }

    def stop_process(self, process_id: str) -> dict[str, Any]:
        process = self.processes.get(process_id)
        if process is None:
            raise AgentRuntimeError(f"unknown process id: {process_id}")
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        handle = self.process_logs.pop(process_id, None)
        if handle is not None:
            handle.close()
        return {"process_id": process_id, "exit_code": process.returncode}

    def stop_all_processes(self) -> None:
        for process_id in list(self.processes):
            try:
                self.stop_process(process_id)
            except Exception:
                pass

    def list_files(self, path: str = ".", max_depth: int = 4) -> dict[str, Any]:
        base = safe_path(self.workspace, path, allow_missing=False)
        if not base.is_dir():
            raise AgentRuntimeError(f"not a directory: {path}")
        depth = max(1, min(int(max_depth), 8))
        files: list[str] = []
        base_parts = len(base.parts)
        for candidate in sorted(base.rglob("*")):
            if len(candidate.parts) - base_parts > depth:
                continue
            rel = relative(self.workspace, candidate)
            if rel.startswith(".git/"):
                continue
            if candidate.is_file():
                files.append(rel)
            elif candidate.is_dir():
                files.append(rel + "/")
            if len(files) >= 400:
                break
        return {"base": relative(self.workspace, base) or ".", "entries": files, "truncated": len(files) >= 400}

    def read_file(self, path: str, start_line: int = 1, end_line: int = 400) -> dict[str, Any]:
        candidate = safe_path(self.workspace, path, allow_missing=False)
        if not candidate.is_file():
            raise AgentRuntimeError(f"not a file: {path}")
        if candidate.stat().st_size > 2_000_000:
            raise AgentRuntimeError(f"file is too large to read: {path}")
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise AgentRuntimeError(f"file is not UTF-8 text: {path}") from exc
        start = max(1, int(start_line))
        end = max(start, min(int(end_line), start + 799, len(lines) or start))
        selected = "\n".join(f"{index}: {lines[index - 1]}" for index in range(start, min(end, len(lines)) + 1))
        return {
            "path": relative(self.workspace, candidate),
            "start_line": start,
            "end_line": min(end, len(lines)),
            "total_lines": len(lines),
            "content": truncate(selected),
        }

    def search_text(self, query: str, path: str = ".") -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise AgentRuntimeError("query must be nonempty")
        base = safe_path(self.workspace, path, allow_missing=False)
        pattern = query.casefold()
        matches: list[dict[str, Any]] = []
        candidates = [base] if base.is_file() else sorted(base.rglob("*"))
        for candidate in candidates:
            if len(matches) >= 120:
                break
            if not candidate.is_file() or ".git" in candidate.parts or candidate.stat().st_size > 1_000_000:
                continue
            try:
                lines = candidate.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for index, line in enumerate(lines, 1):
                if pattern in line.casefold():
                    matches.append({
                        "path": relative(self.workspace, candidate),
                        "line": index,
                        "text": truncate(line, 500),
                    })
                    if len(matches) >= 120:
                        break
        return {"query": query, "matches": matches, "truncated": len(matches) >= 120}

    def write_file(self, scopes: list[str], path: str, content: str) -> dict[str, Any]:
        if not isinstance(content, str):
            raise AgentRuntimeError("content must be a string")
        candidate = safe_path(self.workspace, path)
        rel = relative(self.workspace, candidate)
        if not scope_allows(rel, scopes):
            raise AgentRuntimeError(f"write is outside worker scope: {rel}; allowed scopes: {scopes}")
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(content, encoding="utf-8")
        return {"path": rel, "sha256": file_digest(candidate), "bytes": candidate.stat().st_size}

    def delete_path(self, scopes: list[str], path: str) -> dict[str, Any]:
        candidate = safe_path(self.workspace, path, allow_missing=False)
        rel = relative(self.workspace, candidate)
        if not scope_allows(rel, scopes):
            raise AgentRuntimeError(f"delete is outside worker scope: {rel}")
        if candidate.is_dir():
            if any(candidate.iterdir()):
                raise AgentRuntimeError("directory deletion is allowed only for an empty directory")
            candidate.rmdir()
        else:
            candidate.unlink()
        return {"path": rel, "deleted": True}

    def fetch_url(self, url: str, max_chars: int = 20000) -> dict[str, Any]:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise AgentRuntimeError("only public HTTP or HTTPS URLs are allowed")
        try:
            addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror as exc:
            raise AgentRuntimeError(f"cannot resolve URL host: {parsed.hostname}") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise AgentRuntimeError("private or special network addresses are not allowed")
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "CompanyOS-Autonomous-Micro-Test/1.0",
                "Accept": "text/html,text/plain,application/json;q=0.9,*/*;q=0.1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                raw = response.read(1_000_000)
                content_type = response.headers.get("Content-Type", "")
                final_url = response.geturl()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AgentRuntimeError(f"URL fetch failed: {exc}") from exc
        text = raw.decode("utf-8", errors="replace")
        if "html" in content_type.casefold():
            text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
            text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
        limit = max(1000, min(int(max_chars), 40000))
        return {
            "url": final_url,
            "content_type": content_type,
            "content": truncate(text, limit),
        }

    def register_product(self, scopes: list[str], product_root: str, start_command: list[str], url: str) -> dict[str, Any]:
        root = safe_path(self.workspace, product_root, allow_missing=False)
        rel = relative(self.workspace, root)
        if not root.is_dir():
            raise AgentRuntimeError("product_root must be a directory")
        if not any(scope_allows(relative(self.workspace, candidate), scopes) for candidate in root.rglob("*") if candidate.is_file()):
            raise AgentRuntimeError("product root contains no file owned by this worker")
        if not isinstance(start_command, list) or not start_command or not all(isinstance(item, str) and item for item in start_command):
            raise AgentRuntimeError("start_command must be a nonempty string array")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise AgentRuntimeError("product URL must be local HTTP")
        registration = {
            "product_root": rel,
            "start_command": list(start_command),
            "url": url,
        }
        self.product_registration = registration
        self.trace("product_registered", **registration)
        return registration

    def worker_tools(self) -> list[dict[str, Any]]:
        return [
            tool_schema("list_files", "List files and directories inside the isolated workspace.", {
                "path": {"type": "string"},
                "max_depth": {"type": "integer"},
            }),
            tool_schema("read_file", "Read a bounded line range from one UTF-8 workspace file.", {
                "path": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
            }, ["path"]),
            tool_schema("search_text", "Search UTF-8 workspace files for an exact case-insensitive text fragment.", {
                "query": {"type": "string"},
                "path": {"type": "string"},
            }, ["query"]),
            tool_schema("write_file", "Create or replace one UTF-8 file inside the exact worker write scope.", {
                "path": {"type": "string"},
                "content": {"type": "string"},
            }, ["path", "content"]),
            tool_schema("delete_path", "Delete one scoped file or one empty scoped directory.", {
                "path": {"type": "string"},
            }, ["path"]),
            tool_schema("run_command", "Run one bounded local command without a shell and observe its real output.", {
                "argv": {"type": "array", "items": {"type": "string"}},
                "cwd": {"type": "string"},
                "timeout_seconds": {"type": "integer"},
                "env": {"type": "object", "additionalProperties": {"type": "string"}},
            }, ["argv"]),
            tool_schema("start_process", "Start a bounded local background process such as a development server.", {
                "argv": {"type": "array", "items": {"type": "string"}},
                "cwd": {"type": "string"},
                "env": {"type": "object", "additionalProperties": {"type": "string"}},
            }, ["argv"]),
            tool_schema("stop_process", "Stop a background process started by this test runtime.", {
                "process_id": {"type": "string"},
            }, ["process_id"]),
            tool_schema("fetch_url", "Fetch a public read-only URL for route-relevant primary-source research.", {
                "url": {"type": "string"},
                "max_chars": {"type": "integer"},
            }, ["url"]),
            tool_schema("register_product", "Register the real local product root, one start command, and local URL after runtime behavior has been observed.", {
                "product_root": {"type": "string"},
                "start_command": {"type": "array", "items": {"type": "string"}},
                "url": {"type": "string"},
            }, ["product_root", "start_command", "url"]),
            tool_schema("finish_worker", "Finish this worker only after producing exact evidence or proving a concrete blocker.", {
                "status": {"type": "string", "enum": ["accepted", "blocked", "failed"]},
                "summary": {"type": "string"},
                "evidence_paths": {"type": "array", "items": {"type": "string"}},
                "blocker": {"type": "string"},
            }, ["status", "summary", "evidence_paths"]),
        ]

    def manager_tools(self) -> list[dict[str, Any]]:
        return [
            tool_schema("list_files", "List actual workspace files for inspection.", {
                "path": {"type": "string"},
                "max_depth": {"type": "integer"},
            }),
            tool_schema("read_file", "Read an actual workspace file for inspection.", {
                "path": {"type": "string"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"},
            }, ["path"]),
            tool_schema("search_text", "Search actual workspace files for exact evidence.", {
                "query": {"type": "string"},
                "path": {"type": "string"},
            }, ["query"]),
            tool_schema("run_command", "Run one bounded local verification command and inspect its output.", {
                "argv": {"type": "array", "items": {"type": "string"}},
                "cwd": {"type": "string"},
                "timeout_seconds": {"type": "integer"},
                "env": {"type": "object", "additionalProperties": {"type": "string"}},
            }, ["argv"]),
            tool_schema("spawn_worker", "Start one real independent worker thread from the exact listed Company OS worker packet.", {
                "worker_id": {"type": "string"},
            }, ["worker_id"]),
            tool_schema("request_rework", "Request one targeted rework pass from a previously completed worker without changing its scope.", {
                "worker_id": {"type": "string"},
                "defect": {"type": "string"},
            }, ["worker_id", "defect"]),
            tool_schema("finish_manager", "Finish the manager after inspecting actual worker bytes and behavior.", {
                "status": {"type": "string", "enum": ["accepted", "blocked", "failed"]},
                "summary": {"type": "string"},
                "accepted_worker_ids": {"type": "array", "items": {"type": "string"}},
                "blocker": {"type": "string"},
            }, ["status", "summary", "accepted_worker_ids"]),
        ]

    def worker_system_prompt(self, packet: Mapping[str, Any], rework_defect: str | None = None) -> str:
        rework = f"\nTargeted rework defect: {rework_defect}\n" if rework_defect else ""
        return f"""You are a real Company OS worker running in an isolated workspace.

Original objective:
{self.objective}

Exact Company OS worker packet:
{json.dumps(packet, indent=2, sort_keys=True)}
{rework}
Operate only inside the packet scope and budget. Read enough actual code and state to understand the task, then take the smallest sufficient state-changing action. Plans, explanations, source listings, schemas, and completion claims are not product progress unless the packet explicitly requires that artifact class. Use the provided tools. Do not ask the operator questions. Do not add dependencies when standard library, native platform features, installed code, or existing project structure are sufficient.

For implementation work, create real product bytes, run them, observe behavior, and write every canonical handoff or receipt required by the packet. When you create a runnable product, call register_product after observing it. For research, use fetch_url only for the assigned live blocker and cite exact URLs in the required proposal. For evaluation, do not modify candidate bytes and write the exact evaluator receipt.

Never simplify away explicit requirements, validation, persistence, accessibility, security, error handling, runtime evidence, or independent verification. Never write outside the exact write_scope. The finish_worker tool is the only valid completion signal. A prose response without a tool call is not completion.

Return exactly one tool call per response. If native tool calling is unavailable, return only a strict JSON object of the form:
{{"name":"tool_name","arguments":{{...}}}}
"""

    def manager_system_prompt(self, packet: Mapping[str, Any]) -> str:
        return f"""You are a real Company OS manager running in an isolated workspace.

Original objective:
{self.objective}

Exact Company OS manager packet:
{json.dumps(packet, indent=2, sort_keys=True)}

Use spawn_worker to start each exact worker listed in this packet. Those workers are independent model sessions, not role play. Do not write product code yourself. After each worker returns, inspect actual bytes and actual behavior using the read, search, and command tools. A worker narrative is not evidence. If the dominant defect can be fixed inside the same scope, request one precise rework pass. Do not expand scope, create new requirements, or replace execution with generic research, architecture, audits, or documentation.

Finish accepted only when the packet acceptance checks are supported by actual workspace evidence. Finish blocked only with a concrete evidence-backed blocker. The finish_manager tool is the only valid completion signal.

Return exactly one tool call per response. If native tool calling is unavailable, return only a strict JSON object of the form:
{{"name":"tool_name","arguments":{{...}}}}
"""

    def run_worker(self, packet: Mapping[str, Any], *, rework_defect: str | None = None) -> dict[str, Any]:
        worker_id = str(packet.get("id") or "worker")
        thread_id = str(uuid.uuid4())
        scopes = [str(item) for item in packet.get("write_scope", []) if isinstance(item, str)]
        before = self.workspace_snapshot()
        record = {
            "thread_id": thread_id,
            "role": "worker",
            "actor_id": worker_id,
            "status": "running",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "rework": rework_defect is not None,
        }
        self.threads.append(record)
        self.trace("thread_started", **record)
        messages = [{"role": "system", "content": self.worker_system_prompt(packet, rework_defect)}]
        tools = self.worker_tools()
        final: dict[str, Any] | None = None
        no_action_count = 0

        for turn in range(1, MAX_AGENT_TURNS + 1):
            message = self.client.chat(messages, tools)
            content = message.get("content") if isinstance(message.get("content"), str) else ""
            self.trace("model_message", thread_id=thread_id, turn=turn, role="worker", content=truncate(content, 5000), tool_calls=message.get("tool_calls"))
            actions = extract_actions(message)
            if not actions:
                no_action_count += 1
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": "No executable tool call was detected. Use exactly one available tool now. Return only the JSON tool envelope.",
                })
                if no_action_count >= 3:
                    final = {
                        "status": "blocked",
                        "summary": "Worker did not enter the tool execution loop.",
                        "evidence_paths": [],
                        "blocker": "Three consecutive model responses contained no executable tool call.",
                    }
                    break
                continue
            no_action_count = 0
            action = actions[0]
            name = action["name"]
            arguments = action["arguments"]
            try:
                result, terminal = self.execute_worker_tool(name, arguments, packet, scopes)
                tool_result = {"ok": True, "result": result}
            except Exception as exc:
                terminal = False
                tool_result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            self.trace("tool_result", thread_id=thread_id, turn=turn, role="worker", tool=name, arguments=arguments, result=tool_result)
            messages.append({"role": "assistant", "content": content or json.dumps(action, sort_keys=True)})
            messages.append({
                "role": "user",
                "content": f"Tool {name} returned:\n{truncate(json.dumps(tool_result, sort_keys=True), 10000)}\nChoose the next single tool call.",
            })
            if terminal:
                final = dict(result)
                break

        if final is None:
            final = {
                "status": "blocked",
                "summary": "Worker exhausted its bounded turn budget.",
                "evidence_paths": [],
                "blocker": f"Worker exceeded {MAX_AGENT_TURNS} model turns without a terminal receipt.",
            }
        after = self.workspace_snapshot()
        changes = self.snapshot_diff(before, after)
        final["changed_paths"] = changes
        for path in final.get("evidence_paths", []):
            if isinstance(path, str):
                self.evidence_paths.add(path)
        record.update({
            "status": final.get("status"),
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "result": final,
        })
        self.worker_results[worker_id] = final
        self.trace("thread_completed", **record)
        return {"thread_id": thread_id, "worker_id": worker_id, **final}

    def execute_worker_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
        packet: Mapping[str, Any],
        scopes: list[str],
    ) -> tuple[Any, bool]:
        if name == "list_files":
            return self.list_files(str(arguments.get("path", ".")), int(arguments.get("max_depth", 4))), False
        if name == "read_file":
            return self.read_file(
                str(arguments.get("path")),
                int(arguments.get("start_line", 1)),
                int(arguments.get("end_line", 400)),
            ), False
        if name == "search_text":
            return self.search_text(str(arguments.get("query")), str(arguments.get("path", "."))), False
        if name == "write_file":
            return self.write_file(scopes, str(arguments.get("path")), str(arguments.get("content", ""))), False
        if name == "delete_path":
            return self.delete_path(scopes, str(arguments.get("path"))), False
        if name == "run_command":
            return self.run_command(
                list(arguments.get("argv", [])),
                cwd=str(arguments.get("cwd", ".")),
                timeout_seconds=int(arguments.get("timeout_seconds", 90)),
                env=arguments.get("env") if isinstance(arguments.get("env"), Mapping) else None,
            ), False
        if name == "start_process":
            return self.start_process(
                list(arguments.get("argv", [])),
                cwd=str(arguments.get("cwd", ".")),
                env=arguments.get("env") if isinstance(arguments.get("env"), Mapping) else None,
            ), False
        if name == "stop_process":
            return self.stop_process(str(arguments.get("process_id"))), False
        if name == "fetch_url":
            return self.fetch_url(str(arguments.get("url")), int(arguments.get("max_chars", 20000))), False
        if name == "register_product":
            return self.register_product(
                scopes,
                str(arguments.get("product_root")),
                list(arguments.get("start_command", [])),
                str(arguments.get("url")),
            ), False
        if name == "finish_worker":
            status = str(arguments.get("status"))
            if status not in {"accepted", "blocked", "failed"}:
                raise AgentRuntimeError("invalid worker status")
            evidence_paths = arguments.get("evidence_paths")
            if not isinstance(evidence_paths, list) or not all(isinstance(item, str) for item in evidence_paths):
                raise AgentRuntimeError("evidence_paths must be a string array")
            verified_paths: list[str] = []
            for raw in evidence_paths:
                candidate = safe_path(self.workspace, raw, allow_missing=False)
                verified_paths.append(relative(self.workspace, candidate))
            blocker = arguments.get("blocker")
            if blocker is not None and not isinstance(blocker, str):
                raise AgentRuntimeError("blocker must be a string or null")
            final = {
                "status": status,
                "summary": str(arguments.get("summary", "")).strip(),
                "evidence_paths": verified_paths,
                "blocker": blocker,
            }
            if status == "accepted" and not verified_paths:
                raise AgentRuntimeError("accepted workers must provide at least one existing evidence path")
            return final, True
        raise AgentRuntimeError(f"unknown worker tool: {name}")

    def run_manager(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        manager_id = str(packet.get("id") or "manager")
        thread_id = str(uuid.uuid4())
        workers_raw = packet.get("workers")
        workers = [dict(item) for item in workers_raw if isinstance(item, Mapping)] if isinstance(workers_raw, list) else []
        worker_by_id = {str(item.get("id")): item for item in workers}
        rework_count: dict[str, int] = {}
        spawned: dict[str, dict[str, Any]] = {}
        record = {
            "thread_id": thread_id,
            "role": "manager",
            "actor_id": manager_id,
            "status": "running",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self.threads.append(record)
        self.trace("thread_started", **record)
        messages = [{"role": "system", "content": self.manager_system_prompt(packet)}]
        tools = self.manager_tools()
        final: dict[str, Any] | None = None
        no_action_count = 0

        for turn in range(1, MAX_AGENT_TURNS + 1):
            message = self.client.chat(messages, tools)
            content = message.get("content") if isinstance(message.get("content"), str) else ""
            self.trace("model_message", thread_id=thread_id, turn=turn, role="manager", content=truncate(content, 5000), tool_calls=message.get("tool_calls"))
            actions = extract_actions(message)
            if not actions:
                no_action_count += 1
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": "No executable tool call was detected. Use exactly one manager tool now. Spawn pending workers before discussing completion.",
                })
                if no_action_count >= 3:
                    final = {
                        "status": "blocked",
                        "summary": "Manager did not enter the execution loop.",
                        "accepted_worker_ids": [],
                        "blocker": "Three consecutive manager responses contained no executable tool call.",
                    }
                    break
                continue
            no_action_count = 0
            action = actions[0]
            name = action["name"]
            arguments = action["arguments"]
            try:
                result, terminal = self.execute_manager_tool(
                    name,
                    arguments,
                    packet,
                    worker_by_id,
                    spawned,
                    rework_count,
                )
                tool_result = {"ok": True, "result": result}
            except Exception as exc:
                terminal = False
                tool_result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            self.trace("tool_result", thread_id=thread_id, turn=turn, role="manager", tool=name, arguments=arguments, result=tool_result)
            messages.append({"role": "assistant", "content": content or json.dumps(action, sort_keys=True)})
            messages.append({
                "role": "user",
                "content": f"Tool {name} returned:\n{truncate(json.dumps(tool_result, sort_keys=True), 12000)}\nChoose the next single manager tool call.",
            })
            if terminal:
                final = dict(result)
                break

        if final is None:
            final = {
                "status": "blocked",
                "summary": "Manager exhausted its bounded turn budget.",
                "accepted_worker_ids": [],
                "blocker": f"Manager exceeded {MAX_AGENT_TURNS} model turns without a terminal receipt.",
            }
        record.update({
            "status": final.get("status"),
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "result": final,
        })
        self.trace("thread_completed", **record)
        return {"thread_id": thread_id, "manager_id": manager_id, **final}

    def execute_manager_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
        packet: Mapping[str, Any],
        worker_by_id: Mapping[str, dict[str, Any]],
        spawned: dict[str, dict[str, Any]],
        rework_count: dict[str, int],
    ) -> tuple[Any, bool]:
        if name == "list_files":
            return self.list_files(str(arguments.get("path", ".")), int(arguments.get("max_depth", 4))), False
        if name == "read_file":
            return self.read_file(
                str(arguments.get("path")),
                int(arguments.get("start_line", 1)),
                int(arguments.get("end_line", 400)),
            ), False
        if name == "search_text":
            return self.search_text(str(arguments.get("query")), str(arguments.get("path", "."))), False
        if name == "run_command":
            return self.run_command(
                list(arguments.get("argv", [])),
                cwd=str(arguments.get("cwd", ".")),
                timeout_seconds=int(arguments.get("timeout_seconds", 90)),
                env=arguments.get("env") if isinstance(arguments.get("env"), Mapping) else None,
            ), False
        if name == "spawn_worker":
            worker_id = str(arguments.get("worker_id"))
            packet_value = worker_by_id.get(worker_id)
            if packet_value is None:
                raise AgentRuntimeError(f"worker is not listed in manager packet: {worker_id}")
            if worker_id in spawned:
                raise AgentRuntimeError(f"worker was already spawned: {worker_id}")
            result = self.run_worker(packet_value)
            spawned[worker_id] = result
            return result, False
        if name == "request_rework":
            worker_id = str(arguments.get("worker_id"))
            defect = str(arguments.get("defect", "")).strip()
            if worker_id not in spawned:
                raise AgentRuntimeError("worker must complete once before rework")
            if worker_id not in worker_by_id:
                raise AgentRuntimeError("worker is not listed in manager packet")
            if rework_count.get(worker_id, 0) >= 1:
                raise AgentRuntimeError("only one targeted rework pass is allowed")
            if not defect:
                raise AgentRuntimeError("rework defect must be specific")
            rework_count[worker_id] = rework_count.get(worker_id, 0) + 1
            result = self.run_worker(worker_by_id[worker_id], rework_defect=defect)
            spawned[worker_id] = result
            return result, False
        if name == "finish_manager":
            status = str(arguments.get("status"))
            if status not in {"accepted", "blocked", "failed"}:
                raise AgentRuntimeError("invalid manager status")
            accepted_ids = arguments.get("accepted_worker_ids")
            if not isinstance(accepted_ids, list) or not all(isinstance(item, str) for item in accepted_ids):
                raise AgentRuntimeError("accepted_worker_ids must be a string array")
            unknown = sorted(set(accepted_ids) - set(worker_by_id))
            if unknown:
                raise AgentRuntimeError(f"manager accepted unknown workers: {unknown}")
            if status == "accepted":
                missing = sorted(set(worker_by_id) - set(spawned))
                if missing:
                    raise AgentRuntimeError(f"manager cannot accept before spawning all workers: {missing}")
                not_accepted = sorted(
                    worker_id for worker_id in worker_by_id
                    if spawned.get(worker_id, {}).get("status") != "accepted"
                )
                if not_accepted:
                    raise AgentRuntimeError(f"manager cannot accept workers without accepted receipts: {not_accepted}")
                if set(accepted_ids) != set(worker_by_id):
                    raise AgentRuntimeError("accepted_worker_ids must include every listed worker")
            blocker = arguments.get("blocker")
            if blocker is not None and not isinstance(blocker, str):
                raise AgentRuntimeError("blocker must be a string or null")
            final = {
                "status": status,
                "summary": str(arguments.get("summary", "")).strip(),
                "accepted_worker_ids": list(accepted_ids),
                "blocker": blocker,
            }
            return final, True
        raise AgentRuntimeError(f"unknown manager tool: {name}")

    def workspace_snapshot(self) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for path in sorted(self.workspace.rglob("*")):
            if not path.is_file() or ".git" in path.parts:
                continue
            rel = relative(self.workspace, path)
            try:
                snapshot[rel] = file_digest(path)
            except OSError:
                continue
        return snapshot

    @staticmethod
    def snapshot_diff(before: Mapping[str, str], after: Mapping[str, str]) -> list[dict[str, Any]]:
        paths = sorted(set(before) | set(after))
        changes: list[dict[str, Any]] = []
        for path in paths:
            if before.get(path) == after.get(path):
                continue
            status = "added" if path not in before else "deleted" if path not in after else "modified"
            changes.append({"path": path, "status": status, "sha256": after.get(path)})
        return changes

    def run_cli(self, argv: list[str], *, timeout_seconds: int = 180) -> dict[str, Any]:
        result = self.run_command(argv, cwd=".", timeout_seconds=timeout_seconds)
        if result["exit_code"] != 0:
            raise AgentRuntimeError(f"Company OS command failed: {argv}\n{result['output']}")
        lines = [line.strip() for line in result["output"].splitlines() if line.strip()]
        for line in reversed(lines):
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        return {"ok": True, "output": result["output"]}

    @property
    def controller_path(self) -> str:
        return ".codex/skills/company-os/elastic-company-os/scripts/company_os_controller.py"

    @property
    def director_path(self) -> str:
        return ".codex/skills/company-os/direct-outcome/scripts/direct_outcome.py"

    def initialize_company_os(self) -> None:
        self.trace("mission_initializing", objective_id=OBJECTIVE_ID, objective=self.objective)
        init = self.run_cli([
            "python3",
            self.controller_path,
            "init",
            "--project",
            str(self.workspace),
            "--name",
            "Signal Notes Autonomous Micro",
            "--project-type",
            "general",
            "--north-star",
            self.objective,
        ])
        start = self.run_cli([
            "python3",
            self.director_path,
            "start",
            "--project-root",
            str(self.workspace),
            "--objective-id",
            OBJECTIVE_ID,
            "--objective",
            self.objective,
        ])
        self.trace("mission_initialized", controller=init, director=start)

    def director_state_path(self) -> Path:
        return self.workspace / f".company-os/outcomes/{OBJECTIVE_ID}/director-state.json"

    def mission_state_path(self) -> Path:
        return self.workspace / f".company-os/outcomes/{OBJECTIVE_ID}/mission-execution-state.json"

    def load_director(self) -> dict[str, Any]:
        return read_json(self.director_state_path())

    def load_mission(self) -> dict[str, Any]:
        return read_json(self.mission_state_path())

    def advance(self) -> dict[str, Any]:
        result = self.run_cli([
            "python3",
            self.director_path,
            "advance",
            "--project-root",
            str(self.workspace),
            "--objective-id",
            OBJECTIVE_ID,
        ])
        self.trace("director_advanced", result=result)
        return result

    def collect_path_strings(self, value: Any) -> list[str]:
        found: list[str] = []
        if isinstance(value, str):
            if value.endswith(".json"):
                found.append(value)
        elif isinstance(value, Mapping):
            for item in value.values():
                found.extend(self.collect_path_strings(item))
        elif isinstance(value, list):
            for item in value:
                found.extend(self.collect_path_strings(item))
        return found

    def find_pending_fabric(self, director: Mapping[str, Any]) -> tuple[Path, dict[str, Any]] | None:
        candidates: list[Path] = []
        for section in (director.get("next_action"), director.get("artifacts")):
            for raw in self.collect_path_strings(section):
                try:
                    candidate = safe_path(self.workspace, raw, allow_missing=False)
                except Exception:
                    continue
                candidates.append(candidate)
        outcome_root = self.workspace / f".company-os/outcomes/{OBJECTIVE_ID}"
        if outcome_root.is_dir():
            candidates.extend(sorted(outcome_root.rglob("*fabric*.json"), key=lambda path: path.stat().st_mtime, reverse=True))
        seen_paths: set[str] = set()
        for candidate in candidates:
            rel = relative(self.workspace, candidate)
            if rel in seen_paths or not candidate.is_file():
                continue
            seen_paths.add(rel)
            try:
                value = read_json(candidate)
            except Exception:
                continue
            managers = value.get("managers")
            if not isinstance(managers, list) or not managers:
                continue
            candidate_digest = file_digest(candidate)
            if candidate_digest in self.dispatched_fabric_digests:
                continue
            return candidate, value
        return None

    def dispatch_fabric(self, path: Path, fabric: Mapping[str, Any]) -> list[dict[str, Any]]:
        fabric_sha = file_digest(path)
        managers_raw = fabric.get("managers")
        if not isinstance(managers_raw, list) or not managers_raw:
            raise AgentRuntimeError("execution fabric has no managers")
        self.trace(
            "fabric_dispatch_started",
            path=relative(self.workspace, path),
            sha256=fabric_sha,
            manager_count=len(managers_raw),
        )
        results: list[dict[str, Any]] = []
        for raw_manager in managers_raw:
            if not isinstance(raw_manager, Mapping):
                continue
            result = self.run_manager(dict(raw_manager))
            results.append(result)
            if result.get("status") != "accepted":
                self.blocker = str(result.get("blocker") or result.get("summary") or "manager did not accept its lane")
                break
        if results and all(result.get("status") == "accepted" for result in results) and len(results) == len(managers_raw):
            self.dispatched_fabric_digests.add(fabric_sha)
        self.trace(
            "fabric_dispatch_completed",
            path=relative(self.workspace, path),
            sha256=fabric_sha,
            results=results,
        )
        return results

    def mission_arrived(self) -> bool:
        try:
            director = self.load_director()
            mission = self.load_mission()
        except Exception:
            return False
        navigation = mission.get("navigation") if isinstance(mission.get("navigation"), Mapping) else {}
        position = navigation.get("position") if isinstance(navigation.get("position"), Mapping) else {}
        return (
            director.get("stage") == "accepted"
            and navigation.get("mode") == "arrived"
            and position.get("destination_distance") == 0
        )

    def run_mission(self) -> dict[str, Any]:
        self.initialize_company_os()
        stagnant_cycles = 0
        prior_state_digest: str | None = None

        for cycle in range(1, MAX_MISSION_CYCLES + 1):
            director = self.load_director()
            mission = self.load_mission()
            state_marker = digest({
                "director": director.get("director_sha256"),
                "mission": mission.get("state_sha256"),
                "stage": director.get("stage"),
                "next_action": director.get("next_action"),
            })
            self.trace(
                "mission_cycle",
                cycle=cycle,
                director_stage=director.get("stage"),
                navigation=mission.get("navigation"),
            )
            if self.mission_arrived():
                return self.finalize_result("accepted", None)

            pending = self.find_pending_fabric(director)
            if pending is not None:
                path, fabric = pending
                results = self.dispatch_fabric(path, fabric)
                if not results or any(result.get("status") != "accepted" for result in results):
                    return self.finalize_result("blocked", self.blocker or "A Company OS manager lane did not complete.")
                try:
                    self.advance()
                except Exception as exc:
                    self.blocker = f"Director could not ingest accepted worker evidence: {exc}"
                    return self.finalize_result("blocked", self.blocker)
            else:
                try:
                    self.advance()
                except Exception as exc:
                    self.blocker = f"No executable fabric was available and director advance failed: {exc}"
                    return self.finalize_result("blocked", self.blocker)

            new_director = self.load_director()
            new_mission = self.load_mission()
            new_marker = digest({
                "director": new_director.get("director_sha256"),
                "mission": new_mission.get("state_sha256"),
                "stage": new_director.get("stage"),
                "next_action": new_director.get("next_action"),
            })
            if new_marker == prior_state_digest or new_marker == state_marker:
                stagnant_cycles += 1
            else:
                stagnant_cycles = 0
            prior_state_digest = new_marker
            if stagnant_cycles >= 2:
                self.blocker = "Company OS produced no new fabric, state transition, or accepted destination across two complete cycles."
                return self.finalize_result("blocked", self.blocker)

        self.blocker = f"Mission exceeded the bounded {MAX_MISSION_CYCLES} cycle limit."
        return self.finalize_result("blocked", self.blocker)

    def finalize_result(self, status: str, blocker: str | None) -> dict[str, Any]:
        director: dict[str, Any] = {}
        mission: dict[str, Any] = {}
        try:
            director = self.load_director()
            mission = self.load_mission()
        except Exception:
            pass
        navigation = mission.get("navigation") if isinstance(mission.get("navigation"), Mapping) else {}
        position = navigation.get("position") if isinstance(navigation.get("position"), Mapping) else {}
        managers = [
            {
                "thread_id": item["thread_id"],
                "role": item["actor_id"],
                "result": item.get("status"),
            }
            for item in self.threads
            if item.get("role") == "manager"
        ]
        workers = [
            {
                "thread_id": item["thread_id"],
                "role": item["actor_id"],
                "result": item.get("status"),
            }
            for item in self.threads
            if item.get("role") == "worker"
        ]
        registration = self.product_registration or {}
        accepted = (
            status == "accepted"
            and director.get("stage") == "accepted"
            and navigation.get("mode") == "arrived"
            and position.get("destination_distance") == 0
            and bool(registration)
        )
        if status == "accepted" and not accepted:
            status = "blocked"
            blocker = blocker or "Company OS had not reached accepted and arrived state with a registered runnable product."
        result = {
            "status": status,
            "objective_id": OBJECTIVE_ID,
            "product_root": registration.get("product_root"),
            "start_command": registration.get("start_command"),
            "url": registration.get("url", "http://127.0.0.1:8765"),
            "director_stage": director.get("stage"),
            "navigation_mode": navigation.get("mode"),
            "destination_distance": position.get("destination_distance"),
            "manager_threads": managers,
            "worker_threads": workers,
            "evidence_paths": sorted({
                *self.evidence_paths,
                relative(self.workspace, self.trace_path),
                relative(self.workspace, self.director_state_path()) if self.director_state_path().is_file() else "",
                relative(self.workspace, self.mission_state_path()) if self.mission_state_path().is_file() else "",
            } - {""}),
            "root_product_writes": list(self.root_product_writes),
            "blocker": blocker,
        }
        write_json(self.workspace / ".company-os-test/result.json", result)
        self.trace("mission_finished", result=result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--objective-file", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    objective_file = args.objective_file.resolve()
    objective = objective_file.read_text(encoding="utf-8").strip()
    runtime = AgentOSRuntime(workspace, objective, model=args.model)
    try:
        result = runtime.run_mission()
    except Exception as exc:
        runtime.blocker = f"Uncaught local agent runtime failure: {type(exc).__name__}: {exc}"
        result = runtime.finalize_result("blocked", runtime.blocker)
    finally:
        runtime.stop_all_processes()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
