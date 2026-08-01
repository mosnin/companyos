#!/usr/bin/env python3
"""Project-isolated transactional control store for Company OS.

SQLite is authoritative. JSON and JSONL are deterministic compatibility
exports and may always be rebuilt from committed database truth.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any


STORE_SCHEMA_VERSION = 1
DATABASE_NAME = "control.db"


class StoreError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def json_bytes(value: Any, *, pretty: bool = False) -> bytes:
    if pretty:
        return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8")
    return (canonical_json(value) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def database_path(project: Path) -> Path:
    return project.resolve() / ".company-os" / DATABASE_NAME


def exists(project: Path) -> bool:
    return database_path(project).is_file()


def connect(project: Path) -> sqlite3.Connection:
    path = database_path(project)
    connection = sqlite3.connect(f"file:{path}?mode=rw", uri=True, timeout=10.0)
    return _configure_connection(connection, journal_mode="WAL")


def _configure_connection(
    connection: sqlite3.Connection,
    *,
    journal_mode: str,
) -> sqlite3.Connection:
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA synchronous = FULL")
    connection.execute(f"PRAGMA journal_mode = {journal_mode}")
    return connection


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS store_metadata (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  schema_version INTEGER NOT NULL,
  project_id TEXT NOT NULL,
  project_root TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS state_revisions (
  revision INTEGER PRIMARY KEY CHECK (revision > 0),
  project_id TEXT NOT NULL,
  state_json TEXT NOT NULL,
  state_sha256 TEXT NOT NULL,
  event_id TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  project_id TEXT NOT NULL,
  program_version INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  state_revision INTEGER NOT NULL UNIQUE REFERENCES state_revisions(revision)
);
CREATE TABLE IF NOT EXISTS legacy_events (
  sequence INTEGER PRIMARY KEY,
  project_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entities (
  project_id TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  program_version INTEGER,
  status TEXT,
  record_json TEXT NOT NULL,
  record_sha256 TEXT NOT NULL,
  state_revision INTEGER NOT NULL REFERENCES state_revisions(revision),
  PRIMARY KEY (project_id, entity_type, entity_id)
);
CREATE TABLE IF NOT EXISTS inbox_messages (
  project_id TEXT NOT NULL,
  channel TEXT NOT NULL,
  message_key TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL,
  state_revision INTEGER NOT NULL REFERENCES state_revisions(revision),
  PRIMARY KEY (project_id, channel, message_key)
);
CREATE TABLE IF NOT EXISTS outbox_messages (
  project_id TEXT NOT NULL,
  channel TEXT NOT NULL,
  message_key TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending','leased','succeeded','failed','cancelled')),
  attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  not_before TEXT,
  created_revision INTEGER NOT NULL REFERENCES state_revisions(revision),
  updated_revision INTEGER NOT NULL REFERENCES state_revisions(revision),
  PRIMARY KEY (project_id, channel, message_key)
);
CREATE TABLE IF NOT EXISTS command_idempotency (
  project_id TEXT NOT NULL,
  command_scope TEXT NOT NULL,
  command_key TEXT NOT NULL,
  command_name TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  result_json TEXT NOT NULL,
  result_sha256 TEXT NOT NULL,
  state_revision INTEGER NOT NULL REFERENCES state_revisions(revision),
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id, command_scope, command_key)
);
CREATE INDEX IF NOT EXISTS entities_revision_idx ON entities(project_id, state_revision);
CREATE INDEX IF NOT EXISTS inbox_revision_idx ON inbox_messages(project_id, state_revision);
CREATE INDEX IF NOT EXISTS outbox_status_idx ON outbox_messages(project_id, status, not_before);
"""


def _metadata(connection: sqlite3.Connection) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM store_metadata WHERE singleton = 1").fetchone()
    if row is None:
        raise StoreError("transactional control store metadata is missing")
    return row


def _assert_binding(connection: sqlite3.Connection, project: Path, state: dict[str, Any] | None = None) -> sqlite3.Row:
    metadata = _metadata(connection)
    expected_root = str(project.resolve())
    if metadata["schema_version"] != STORE_SCHEMA_VERSION:
        raise StoreError("transactional control store schema is unsupported")
    if metadata["project_root"] != expected_root:
        raise StoreError("transactional control store belongs to a different project root")
    if state is not None and metadata["project_id"] != state.get("instance", {}).get("project_id"):
        raise StoreError("transactional control store belongs to a different project ID")
    return metadata


def _load_latest(connection: sqlite3.Connection) -> tuple[int, dict[str, Any]]:
    row = connection.execute(
        "SELECT revision, state_json, state_sha256 FROM state_revisions ORDER BY revision DESC LIMIT 1"
    ).fetchone()
    if row is None:
        raise StoreError("transactional control store has no state revision")
    raw = row["state_json"].encode("utf-8")
    if sha256_bytes(raw) != row["state_sha256"]:
        raise StoreError("transactional control state revision hash is invalid")
    try:
        state = json.loads(row["state_json"])
    except json.JSONDecodeError as exc:
        raise StoreError(f"transactional control state JSON is invalid: {exc}") from None
    if not isinstance(state, dict):
        raise StoreError("transactional control state must be an object")
    return int(row["revision"]), state


def load(project: Path) -> tuple[int, dict[str, Any]]:
    connection = connect(project)
    try:
        _assert_binding(connection, project)
        revision, state = _load_latest(connection)
        _assert_binding(connection, project, state)
        return revision, state
    finally:
        connection.close()


def _entity_records(state: dict[str, Any]) -> list[tuple[str, str, int | None, str | None, dict[str, Any]]]:
    program_version = state.get("strategy", {}).get("program_version")
    records: list[tuple[str, str, int | None, str | None, dict[str, Any]]] = [
        ("program", f"program-{program_version}", program_version, state.get("instance", {}).get("status"), state.get("strategy", {})),
    ]
    portfolio = state.get("portfolio", {})
    for collection, entity_type in (
        ("committed_outcomes", "outcome"),
        ("active_work", "work"),
        ("completed_work", "work"),
        ("cancelled_work", "work"),
    ):
        for item in portfolio.get(collection, []):
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                records.append((entity_type, item["id"], item.get("program_version"), item.get("status"), item))
    for item in state.get("feedback", {}).get("cycles", []):
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            records.append(("cycle", item["id"], item.get("program_version"), item.get("status"), item))
    lease = state.get("controller", {}).get("lease")
    if isinstance(lease, dict) and isinstance(lease.get("lease_id"), str):
        records.append(("lease", lease["lease_id"], lease.get("program_version"), "active", lease))
    for item in state.get("runtime_adapter", {}).get("attempts", []):
        if isinstance(item, dict) and isinstance(item.get("attempt_id"), str):
            records.append(("runtime_attempt", item["attempt_id"], item.get("program_version"), item.get("status"), item))
    for bucket, items in state.get("evidence", {}).items():
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                records.append((f"evidence:{bucket}", item["id"], item.get("program_version"), "recorded", item))
    for collection in ("pending_adaptations", "applied_adaptations"):
        for item in state.get("feedback", {}).get(collection, []):
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                records.append(("adaptation", item["id"], item.get("program_version"), item.get("status"), item))
    return records


def _replace_projections(connection: sqlite3.Connection, state: dict[str, Any], revision: int) -> None:
    project_id = state["instance"]["project_id"]
    connection.execute("DELETE FROM entities WHERE project_id = ?", (project_id,))
    for entity_type, entity_id, program_version, status, record in _entity_records(state):
        encoded = canonical_json(record)
        connection.execute(
            "INSERT INTO entities VALUES (?,?,?,?,?,?,?,?)",
            (project_id, entity_type, entity_id, program_version, status, encoded, sha256_bytes(encoded.encode()), revision),
        )
    connection.execute("DELETE FROM inbox_messages WHERE project_id = ?", (project_id,))
    inboxes = state.get("runtime_adapter", {}).get("observation_inboxes", {})
    if isinstance(inboxes, dict):
        for attempt_id, inbox in inboxes.items():
            if not isinstance(inbox, dict):
                continue
            for observation in inbox.get("trusted_observations", []):
                if not isinstance(observation, dict) or not isinstance(observation.get("event_key"), str):
                    continue
                encoded = canonical_json(observation)
                connection.execute(
                    "INSERT INTO inbox_messages VALUES (?,?,?,?,?,?,?)",
                    (
                        project_id,
                        f"runtime:{attempt_id}",
                        observation["event_key"],
                        sha256_bytes(encoded.encode()),
                        encoded,
                        "accepted",
                        revision,
                    ),
                )


def _insert_revision(connection: sqlite3.Connection, state: dict[str, Any], event: dict[str, Any]) -> int:
    metadata = _assert_binding(connection, Path(state["instance"]["project_root"]), state)
    current = connection.execute("SELECT COALESCE(MAX(revision), 0) AS value FROM state_revisions").fetchone()["value"]
    revision = int(current) + 1
    event_id = str(event.get("event_id") or uuid.uuid4().hex)
    event_payload = {**event, "event_id": event_id, "state_revision": revision}
    state_text = canonical_json(state)
    event_text = canonical_json(event_payload)
    connection.execute(
        "INSERT INTO state_revisions VALUES (?,?,?,?,?,?)",
        (revision, metadata["project_id"], state_text, sha256_bytes(state_text.encode()), event_id, event_payload.get("at")),
    )
    connection.execute(
        "INSERT INTO events(event_id,project_id,program_version,event_type,payload_json,payload_sha256,state_revision) VALUES (?,?,?,?,?,?,?)",
        (event_id, metadata["project_id"], event_payload.get("program_version"), event_payload.get("type"), event_text, sha256_bytes(event_text.encode()), revision),
    )
    _replace_projections(connection, state, revision)
    return revision


def _read_legacy_events(project: Path, project_id: str) -> list[tuple[int, str, str, str]]:
    path = project.resolve() / ".company-os" / "events.jsonl"
    if not path.exists():
        return []
    records: list[tuple[int, str, str, str]] = []
    for sequence, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StoreError(f"legacy event log line {sequence} is invalid: {exc}") from None
        if not isinstance(value, dict) or value.get("project_id") != project_id:
            raise StoreError(f"legacy event log line {sequence} is not bound to this project")
        encoded = canonical_json(value)
        records.append((sequence, project_id, encoded, sha256_bytes(encoded.encode())))
    return records


def initialize(project: Path, state: dict[str, Any], event: dict[str, Any]) -> int:
    project = project.resolve()
    path = database_path(project)
    if path.exists():
        revision, existing = load(project)
        if canonical_json(existing) != canonical_json(state):
            raise StoreError("transactional control store already exists with different state")
        repair_exports(project)
        return revision
    project_id = state.get("instance", {}).get("project_id")
    if not isinstance(project_id, str) or not project_id:
        raise StoreError("cannot initialize a control store without a project ID")
    if state.get("instance", {}).get("project_root") != str(project):
        raise StoreError("cannot initialize a control store for a different project root")
    path.parent.mkdir(parents=True, exist_ok=True)
    legacy = _read_legacy_events(project, project_id)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.initializing")
    connection = _configure_connection(
        sqlite3.connect(temporary, timeout=10.0),
        journal_mode="DELETE",
    )
    try:
        connection.executescript(SCHEMA_SQL)
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT INTO store_metadata VALUES (1,?,?,?,?)",
            (STORE_SCHEMA_VERSION, project_id, str(project), event.get("at")),
        )
        connection.executemany("INSERT INTO legacy_events VALUES (?,?,?,?)", legacy)
        revision = _insert_revision(connection, state, event)
        connection.commit()
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        connection.rollback()
        connection.close()
        for suffix in ("", "-journal", "-wal", "-shm"):
            candidate = Path(str(temporary) + suffix)
            if candidate.exists():
                candidate.unlink()
        raise
    else:
        connection.close()
    repair_exports(project)
    return revision


class Transaction:
    def __init__(self, project: Path):
        self.project = project.resolve()
        self.connection = connect(self.project)
        self.connection.execute("BEGIN IMMEDIATE")
        _assert_binding(self.connection, self.project)
        self.base_revision, self.state = _load_latest(self.connection)
        _assert_binding(self.connection, self.project, self.state)
        self.staged_revision: int | None = None

    def stage(self, state: dict[str, Any], event: dict[str, Any]) -> int:
        if self.staged_revision is not None:
            raise StoreError("one controller transaction may stage only one state/event pair")
        self.staged_revision = _insert_revision(self.connection, state, event)
        self.state = state
        return self.staged_revision

    def idempotency_lookup(
        self,
        *,
        scope: str,
        key: str,
        payload_sha256: str,
    ) -> dict[str, Any] | None:
        return idempotency_lookup(
            self.connection,
            self.state["instance"]["project_id"],
            scope,
            key,
            payload_sha256,
        )

    def record_idempotency(
        self,
        *,
        scope: str,
        key: str,
        command_name: str,
        payload_sha256: str,
        result: dict[str, Any],
        created_at: str,
    ) -> None:
        if self.staged_revision is None:
            raise StoreError("idempotency result requires a staged state/event revision")
        idempotency_record(
            self.connection,
            project_id=self.state["instance"]["project_id"],
            scope=scope,
            key=key,
            command_name=command_name,
            payload_sha256=payload_sha256,
            result=result,
            state_revision=self.staged_revision,
            created_at=created_at,
        )

    def outbox_lookup(
        self,
        *,
        channel: str,
        key: str,
        payload_sha256: str,
    ) -> dict[str, Any] | None:
        return outbox_lookup(
            self.connection,
            self.state["instance"]["project_id"],
            channel,
            key,
            payload_sha256,
        )

    def enqueue_outbox(
        self,
        *,
        channel: str,
        key: str,
        payload: dict[str, Any],
        not_before: str | None = None,
    ) -> dict[str, Any]:
        if self.staged_revision is None:
            raise StoreError("outbox enqueue requires a staged state/event revision")
        return outbox_enqueue(
            self.connection,
            project_id=self.state["instance"]["project_id"],
            channel=channel,
            key=key,
            payload=payload,
            state_revision=self.staged_revision,
            not_before=not_before,
        )

    def transition_outbox(
        self,
        *,
        channel: str,
        key: str,
        status: str,
    ) -> dict[str, Any]:
        if self.staged_revision is None:
            raise StoreError("outbox transition requires a staged state/event revision")
        return outbox_transition(
            self.connection,
            project_id=self.state["instance"]["project_id"],
            channel=channel,
            key=key,
            status=status,
            state_revision=self.staged_revision,
        )

    def close(self, success: bool) -> None:
        try:
            if success and self.staged_revision is not None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.connection.close()
        if success and self.staged_revision is not None:
            try:
                repair_exports(self.project)
            except Exception as exc:
                # Authority is already committed. Reporting command failure here
                # would invite a duplicate retry; export drift is observable and
                # repaired on the next governed open.
                print(
                    json.dumps(
                        {
                            "warning": "transaction committed but compatibility exports could not be published",
                            "revision": self.staged_revision,
                            "error": str(exc),
                        }
                    ),
                    file=sys.stderr,
                )


def begin(project: Path) -> Transaction:
    return Transaction(project)


def _export_values(connection: sqlite3.Connection) -> tuple[bytes, bytes, int]:
    revision, state = _load_latest(connection)
    state_export = json_bytes(state, pretty=True)
    event_lines: list[str] = []
    for row in connection.execute("SELECT payload_json FROM legacy_events ORDER BY sequence"):
        event_lines.append(row["payload_json"])
    for row in connection.execute("SELECT payload_json FROM events ORDER BY sequence"):
        event_lines.append(row["payload_json"])
    events_export = (("\n".join(event_lines) + "\n") if event_lines else "").encode("utf-8")
    return state_export, events_export, revision


def _atomic_bytes(path: Path, value: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def repair_exports(project: Path) -> dict[str, Any]:
    project = project.resolve()
    connection = connect(project)
    try:
        _assert_binding(connection, project)
        state_bytes, events_bytes, revision = _export_values(connection)
    finally:
        connection.close()
    directory = project / ".company-os"
    _atomic_bytes(directory / "control.json", state_bytes)
    _atomic_bytes(directory / "events.jsonl", events_bytes)
    return {"revision": revision, "state_sha256": sha256_bytes(state_bytes), "events_sha256": sha256_bytes(events_bytes)}


def audit(project: Path) -> dict[str, Any]:
    project = project.resolve()
    errors: list[str] = []
    connection = connect(project)
    try:
        metadata = _assert_binding(connection, project)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            errors.append(f"SQLite integrity check failed: {integrity}")
        revision, state = _load_latest(connection)
        _assert_binding(connection, project, state)
        for table in (
            "state_revisions",
            "events",
            "legacy_events",
            "entities",
            "inbox_messages",
            "outbox_messages",
            "command_idempotency",
        ):
            foreign_projects = connection.execute(
                f"SELECT DISTINCT project_id FROM {table} WHERE project_id <> ?",
                (metadata["project_id"],),
            ).fetchall()
            if foreign_projects:
                errors.append(f"{table} contains records for a foreign project")
        revision_rows = connection.execute(
            "SELECT revision,project_id,state_json,state_sha256,event_id FROM state_revisions ORDER BY revision"
        ).fetchall()
        revision_count = len(revision_rows)
        revision_bounds = connection.execute(
            "SELECT MIN(revision) AS minimum, MAX(revision) AS maximum FROM state_revisions"
        ).fetchone()
        event_rows = connection.execute(
            "SELECT sequence,event_id,project_id,program_version,event_type,payload_json,payload_sha256,state_revision FROM events ORDER BY sequence"
        ).fetchall()
        event_count = len(event_rows)
        paired_count = connection.execute(
            "SELECT COUNT(*) FROM state_revisions r JOIN events e ON e.state_revision = r.revision AND e.event_id = r.event_id"
        ).fetchone()[0]
        if revision_count != event_count or paired_count != revision_count:
            errors.append("state revisions and audit events are not one-to-one")
        if revision_bounds["minimum"] != 1 or revision_bounds["maximum"] != revision_count:
            errors.append("state revision sequence is not contiguous from one")
        for expected_revision, row in enumerate(revision_rows, start=1):
            if row["revision"] != expected_revision:
                errors.append("state revision sequence is not ordered contiguously")
                break
            if row["project_id"] != metadata["project_id"]:
                errors.append("state revision belongs to a different project")
                break
            if sha256_bytes(row["state_json"].encode()) != row["state_sha256"]:
                errors.append("a retained state revision hash is invalid")
                break
            try:
                retained_state = json.loads(row["state_json"])
            except json.JSONDecodeError:
                errors.append("a retained state revision contains invalid JSON")
                break
            if retained_state.get("instance", {}).get("project_id") != metadata["project_id"]:
                errors.append("a retained state revision is not bound to this project")
                break
        revisions_by_number = {row["revision"]: row for row in revision_rows}
        for expected_sequence, row in enumerate(event_rows, start=1):
            if row["sequence"] != expected_sequence or row["state_revision"] != expected_sequence:
                errors.append("audit event order does not match state revision order")
                break
            if row["project_id"] != metadata["project_id"]:
                errors.append("an audit event belongs to a different project")
                break
            if sha256_bytes(row["payload_json"].encode()) != row["payload_sha256"]:
                errors.append("a retained audit event hash is invalid")
                break
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                errors.append("a retained audit event contains invalid JSON")
                break
            paired_revision = revisions_by_number.get(row["state_revision"])
            if (
                paired_revision is None
                or paired_revision["event_id"] != row["event_id"]
                or payload.get("event_id") != row["event_id"]
                or payload.get("state_revision") != row["state_revision"]
                or payload.get("project_id") != row["project_id"]
                or payload.get("program_version") != row["program_version"]
                or payload.get("type") != row["event_type"]
            ):
                errors.append("an audit event does not exactly bind its state revision")
                break
        for row in connection.execute(
            "SELECT project_id,payload_json,payload_sha256 FROM legacy_events ORDER BY sequence"
        ):
            if (
                row["project_id"] != metadata["project_id"]
                or sha256_bytes(row["payload_json"].encode()) != row["payload_sha256"]
            ):
                errors.append("a retained legacy event is corrupt or cross-project")
                break
        state_bytes, events_bytes, _ = _export_values(connection)
        entity_rows = connection.execute(
            "SELECT entity_type,entity_id,record_json,record_sha256,state_revision FROM entities WHERE project_id = ?",
            (metadata["project_id"],),
        ).fetchall()
        expected_entities = {
            (kind, identifier): canonical_json(record)
            for kind, identifier, _, _, record in _entity_records(state)
        }
        actual_entities = {
            (row["entity_type"], row["entity_id"]): row["record_json"]
            for row in entity_rows
            if row["state_revision"] == revision
            and sha256_bytes(row["record_json"].encode()) == row["record_sha256"]
        }
        if actual_entities != expected_entities:
            errors.append("transactional entity projections do not match authoritative state")
        expected_inbox: dict[tuple[str, str], str] = {}
        for attempt_id, inbox in state.get("runtime_adapter", {}).get("observation_inboxes", {}).items():
            if not isinstance(inbox, dict):
                continue
            for observation in inbox.get("trusted_observations", []):
                if isinstance(observation, dict) and isinstance(observation.get("event_key"), str):
                    encoded = canonical_json(observation)
                    expected_inbox[(f"runtime:{attempt_id}", observation["event_key"])] = sha256_bytes(
                        encoded.encode()
                    )
        inbox_rows = connection.execute(
            "SELECT channel,message_key,payload_json,payload_sha256,state_revision FROM inbox_messages WHERE project_id = ?",
            (metadata["project_id"],),
        ).fetchall()
        actual_inbox = {
            (row["channel"], row["message_key"]): row["payload_sha256"]
            for row in inbox_rows
            if row["state_revision"] == revision
            and sha256_bytes(row["payload_json"].encode()) == row["payload_sha256"]
        }
        if actual_inbox != expected_inbox:
            errors.append("transactional inbox projections do not match authoritative state")
        pending_outbox = connection.execute(
            "SELECT COUNT(*) FROM outbox_messages WHERE project_id = ? AND status IN ('pending','leased')",
            (metadata["project_id"],),
        ).fetchone()[0]
        for row in connection.execute(
            "SELECT payload_json,payload_sha256,created_revision,updated_revision FROM outbox_messages WHERE project_id = ?",
            (metadata["project_id"],),
        ):
            if (
                sha256_bytes(row["payload_json"].encode()) != row["payload_sha256"]
                or row["created_revision"] > row["updated_revision"]
                or row["updated_revision"] > revision
            ):
                errors.append("transactional outbox contains an invalid retained record")
                break
        events_by_revision: dict[int, dict[str, Any]] = {}
        for event_row in event_rows:
            if sha256_bytes(event_row["payload_json"].encode()) != event_row["payload_sha256"]:
                continue
            try:
                retained_event = json.loads(event_row["payload_json"])
            except json.JSONDecodeError:
                continue
            if isinstance(retained_event, dict):
                events_by_revision[event_row["state_revision"]] = retained_event
        for row in connection.execute(
            "SELECT command_scope,command_key,command_name,payload_sha256,result_json,result_sha256,state_revision "
            "FROM command_idempotency WHERE project_id = ?",
            (metadata["project_id"],),
        ):
            try:
                result_value = json.loads(row["result_json"])
            except json.JSONDecodeError:
                errors.append("command idempotency contains invalid result JSON")
                break
            if (
                not isinstance(result_value, dict)
                or sha256_bytes(row["result_json"].encode()) != row["result_sha256"]
                or not isinstance(row["payload_sha256"], str)
                or len(row["payload_sha256"]) != 64
                or row["state_revision"] > revision
            ):
                errors.append("command idempotency contains an invalid retained record")
                break
            if row["command_scope"] == "controller-cli":
                event_payload = events_by_revision.get(row["state_revision"])
                if event_payload is None:
                    errors.append("controller command replay is missing its paired audit event")
                    break
                event_fields = {
                    key: value
                    for key, value in event_payload.items()
                    if key
                    not in {
                        "at",
                        "type",
                        "project_id",
                        "program_version",
                        "event_id",
                        "state_revision",
                        "command_envelope",
                    }
                }
                expected_command_envelope = {
                    "name": row["command_name"],
                    "key": row["command_key"],
                    "payload_sha256": row["payload_sha256"],
                }
                if event_payload.get("command_envelope") != expected_command_envelope:
                    errors.append("controller command identity does not match its paired audit event")
                    break
                expected_result = {
                    "ok": True,
                    "command": row["command_name"],
                    "command_key": row["command_key"],
                    "event_type": event_payload.get("type"),
                    "state_revision": row["state_revision"],
                    "event": event_fields,
                }
                if result_value != expected_result:
                    errors.append("controller command replay result does not match its paired audit event")
                    break
    finally:
        connection.close()
    state_path = project / ".company-os" / "control.json"
    events_path = project / ".company-os" / "events.jsonl"
    state_export_match = state_path.is_file() and state_path.read_bytes() == state_bytes
    events_export_match = events_path.is_file() and events_path.read_bytes() == events_bytes
    return {
        "ok": not errors,
        "errors": errors,
        "backend": "sqlite",
        "store_schema_version": STORE_SCHEMA_VERSION,
        "revision": revision,
        "project_id": metadata["project_id"],
        "state_export_match": state_export_match,
        "events_export_match": events_export_match,
        "pending_outbox": pending_outbox,
    }


def idempotency_lookup(
    connection: sqlite3.Connection,
    project_id: str,
    scope: str,
    key: str,
    payload_sha256: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT payload_sha256,result_json,result_sha256,state_revision FROM command_idempotency WHERE project_id=? AND command_scope=? AND command_key=?",
        (project_id, scope, key),
    ).fetchone()
    if row is None:
        return None
    if row["payload_sha256"] != payload_sha256:
        raise StoreError("command idempotency key conflicts with a different payload digest")
    if sha256_bytes(row["result_json"].encode()) != row["result_sha256"]:
        raise StoreError("command idempotency result integrity is invalid")
    try:
        result = json.loads(row["result_json"])
    except json.JSONDecodeError:
        raise StoreError("command idempotency result JSON is invalid") from None
    if not isinstance(result, dict):
        raise StoreError("command idempotency result must be an object")
    return {"result": result, "state_revision": row["state_revision"]}


def idempotency_record(
    connection: sqlite3.Connection,
    *,
    project_id: str,
    scope: str,
    key: str,
    command_name: str,
    payload_sha256: str,
    result: dict[str, Any],
    state_revision: int,
    created_at: str,
) -> None:
    encoded_result = canonical_json(result)
    connection.execute(
        "INSERT INTO command_idempotency VALUES (?,?,?,?,?,?,?,?,?)",
        (
            project_id,
            scope,
            key,
            command_name,
            payload_sha256,
            encoded_result,
            sha256_bytes(encoded_result.encode()),
            state_revision,
            created_at,
        ),
    )


def outbox_lookup(
    connection: sqlite3.Connection,
    project_id: str,
    channel: str,
    key: str,
    payload_sha256: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT payload_sha256,payload_json,status,attempt_count,not_before,created_revision,updated_revision "
        "FROM outbox_messages WHERE project_id=? AND channel=? AND message_key=?",
        (project_id, channel, key),
    ).fetchone()
    if row is None:
        return None
    if row["payload_sha256"] != payload_sha256:
        raise StoreError("outbox message key conflicts with a different payload digest")
    return {
        "payload": json.loads(row["payload_json"]),
        "payload_sha256": row["payload_sha256"],
        "status": row["status"],
        "attempt_count": row["attempt_count"],
        "not_before": row["not_before"],
        "created_revision": row["created_revision"],
        "updated_revision": row["updated_revision"],
    }


def outbox_enqueue(
    connection: sqlite3.Connection,
    *,
    project_id: str,
    channel: str,
    key: str,
    payload: dict[str, Any],
    state_revision: int,
    not_before: str | None = None,
) -> dict[str, Any]:
    if not channel or not key:
        raise StoreError("outbox channel and message key must be non-empty")
    encoded = canonical_json(payload)
    payload_sha256 = sha256_bytes(encoded.encode())
    retained = outbox_lookup(connection, project_id, channel, key, payload_sha256)
    if retained is not None:
        return {**retained, "idempotent": True}
    connection.execute(
        "INSERT INTO outbox_messages(project_id,channel,message_key,payload_sha256,payload_json,status,attempt_count,not_before,created_revision,updated_revision) "
        "VALUES (?,?,?,?,?,'pending',0,?,?,?)",
        (
            project_id,
            channel,
            key,
            payload_sha256,
            encoded,
            not_before,
            state_revision,
            state_revision,
        ),
    )
    return {
        "payload": payload,
        "payload_sha256": payload_sha256,
        "status": "pending",
        "attempt_count": 0,
        "not_before": not_before,
        "created_revision": state_revision,
        "updated_revision": state_revision,
        "idempotent": False,
    }


OUTBOX_TRANSITIONS = {
    "pending": {"leased", "cancelled"},
    "leased": {"succeeded", "failed", "cancelled"},
    "failed": {"leased", "cancelled"},
    "succeeded": set(),
    "cancelled": set(),
}


def outbox_transition(
    connection: sqlite3.Connection,
    *,
    project_id: str,
    channel: str,
    key: str,
    status: str,
    state_revision: int,
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT status,attempt_count FROM outbox_messages WHERE project_id=? AND channel=? AND message_key=?",
        (project_id, channel, key),
    ).fetchone()
    if row is None:
        raise StoreError("outbox message does not exist")
    current = row["status"]
    if status == current:
        return {"status": current, "attempt_count": row["attempt_count"], "idempotent": True}
    if status not in OUTBOX_TRANSITIONS.get(current, set()):
        raise StoreError(f"outbox transition {current}->{status} is not allowed")
    attempt_count = row["attempt_count"] + (1 if status == "leased" else 0)
    connection.execute(
        "UPDATE outbox_messages SET status=?,attempt_count=?,updated_revision=? "
        "WHERE project_id=? AND channel=? AND message_key=?",
        (status, attempt_count, state_revision, project_id, channel, key),
    )
    return {"status": status, "attempt_count": attempt_count, "idempotent": False}
