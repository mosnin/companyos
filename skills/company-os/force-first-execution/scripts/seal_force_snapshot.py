#!/usr/bin/env python3
"""Seal and verify an immutable terminal snapshot of a force event log."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

import force_loop_controller as force


SNAPSHOT_SCHEMA = "company-os.force-log-snapshot.v1"
SOURCE_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def _artifact_rows(events: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "event": item["event"],
            "path": item["evidence"]["path"],
            "sha256": item["evidence"]["sha256"],
        }
        for item in events
        if item["event"] in {"artifact_materialized", "receipt_materialized"}
    ]


def _terminal_artifact_rows(events: list[dict[str, Any]]) -> list[dict[str, str]]:
    terminal_event = events[-1]["event"]
    if terminal_event == "manager_accept":
        boundary = next(
            (
                item
                for item in reversed(events)
                if item["event"] == "manager_inspection_passed"
            ),
            None,
        )
    elif terminal_event == "manager_reject":
        candidate, _, inspection = _terminal_rejection_chain(events)
        boundary = candidate if inspection is not None else None
    else:
        boundary = None
    if boundary is None:
        return []
    paths = boundary["evidence"]["artifact_paths"]
    materialized = {
        item["evidence"]["path"]: item["evidence"]["sha256"]
        for item in events
        if item["event"] == "artifact_materialized"
        and item["sequence"] < boundary["sequence"]
    }
    return [
        {"path": path, "sha256": materialized[path]}
        for path in sorted(paths)
    ]


def _terminal_rejection_chain(
    events: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    if events[-1]["event"] != "manager_reject":
        return None, None, None
    candidate = next(
        (item for item in reversed(events[:-1]) if item["event"] == "candidate_runnable"),
        None,
    )
    if candidate is None:
        return None, None, None
    verification = next(
        (
            item
            for item in events[candidate["sequence"] : -1]
            if item["event"] == "verification_passed"
        ),
        None,
    )
    if verification is None:
        return candidate, None, None
    inspection = next(
        (
            item
            for item in events[verification["sequence"] : -1]
            if item["event"] == "manager_inspection_failed"
        ),
        None,
    )
    if inspection is None:
        return candidate, verification, None
    invalid_after_inspection = {
        "artifact_materialized",
        "candidate_runnable",
        "verification_passed",
        "manager_inspection_passed",
        "manager_rework",
        "rework_started",
    }
    if any(
        item["event"] in invalid_after_inspection
        for item in events[inspection["sequence"] : -1]
    ):
        return candidate, verification, None
    return candidate, verification, inspection


def _snapshot_bytes(events: list[dict[str, Any]]) -> bytes:
    return b"".join(force.canonical_bytes(item) + b"\n" for item in events)


def _safe_target(root: Path, relative: str) -> tuple[Path, bytes | None]:
    safe = force._safe_path(relative, "snapshot target")
    resolved_root = force._artifact_root(root)
    current = resolved_root
    parts = safe.split("/")
    for part in parts[:-1]:
        current = current / part
        try:
            status = current.lstat()
        except OSError as error:
            raise force.ForceContractError(
                f"snapshot target parent is missing or unreadable: {safe}"
            ) from error
        if stat.S_ISLNK(status.st_mode) or not stat.S_ISDIR(status.st_mode):
            raise force.ForceContractError(
                f"snapshot target parent must be a real directory: {safe}"
            )
    target = current / parts[-1]
    try:
        status = target.lstat()
    except FileNotFoundError:
        return target, None
    except OSError as error:
        raise force.ForceContractError(
            f"snapshot target could not be inspected: {safe}"
        ) from error
    if stat.S_ISLNK(status.st_mode) or not stat.S_ISREG(status.st_mode):
        raise force.ForceContractError(
            f"snapshot target must be a regular non-symlink file: {safe}"
        )
    try:
        return target, target.read_bytes()
    except OSError as error:
        raise force.ForceContractError(
            f"snapshot target could not be read: {safe}"
        ) from error


def _safe_existing_source(root: Path, supplied: Path, label: str) -> Path:
    if ".." in supplied.parts:
        raise force.ForceContractError(f"{label} must not contain parent traversal")
    resolved_root = force._artifact_root(root)
    lexical_root = Path(os.path.abspath(root))
    candidate = supplied if supplied.is_absolute() else lexical_root / supplied
    lexical = Path(os.path.abspath(candidate))
    try:
        relative = lexical.relative_to(lexical_root)
    except ValueError as error:
        raise force.ForceContractError(f"{label} must stay under artifact root") from error
    relative_text = relative.as_posix()
    if not SOURCE_PATH.fullmatch(relative_text) or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise force.ForceContractError(f"{label} must be a safe project-relative path")
    current = resolved_root
    for index, part in enumerate(relative.parts):
        current = current / part
        try:
            status = current.lstat()
        except OSError as error:
            raise force.ForceContractError(f"{label} is missing or unreadable") from error
        if stat.S_ISLNK(status.st_mode):
            raise force.ForceContractError(f"{label} path contains a symlink")
        if index < len(relative.parts) - 1 and not stat.S_ISDIR(status.st_mode):
            raise force.ForceContractError(f"{label} parent is not a directory")
        if index == len(relative.parts) - 1 and not stat.S_ISREG(status.st_mode):
            raise force.ForceContractError(f"{label} must be a regular file")
    return current


def _exclusive_write(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        _fsync_directory(path.parent)
    except FileExistsError as error:
        raise force.ForceContractError(
            f"snapshot target already exists: {path.name}"
        ) from error
    except OSError as error:
        raise force.ForceContractError(
            f"snapshot target could not be written: {path.name}: {error}"
        ) from error


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def build_receipt(
    contract: dict[str, Any],
    events: list[dict[str, Any]],
    snapshot_path: str,
    snapshot_sha256: str,
) -> dict[str, Any]:
    terminal = events[-1]
    if terminal["event"] not in force.TERMINAL_EVENTS:
        raise force.ForceContractError(
            "force log may be sealed only after a terminal manager decision or hard stop"
        )
    return {
        "schema": SNAPSHOT_SCHEMA,
        "task_id": contract["task_id"],
        "contract_sha256": force.canonical_sha256(contract),
        "snapshot_path": snapshot_path,
        "snapshot_sha256": snapshot_sha256,
        "event_count": len(events),
        "terminal": {
            "event": terminal["event"],
            "sequence": terminal["sequence"],
            "at_epoch": terminal["at_epoch"],
        },
        "artifact_set_sha256": force.canonical_sha256(_artifact_rows(events)),
    }


def seal(
    contract_path: Path,
    events_path: Path,
    artifact_root: Path,
    snapshot_relative: str,
    receipt_relative: str,
) -> dict[str, Any]:
    safe_contract_path = _safe_existing_source(artifact_root, contract_path, "force contract")
    safe_events_path = _safe_existing_source(artifact_root, events_path, "force event log")
    contract = force.read_contract(safe_contract_path)
    events = force.read_events(safe_events_path, contract, artifact_root)
    snapshot_target, existing_snapshot = _safe_target(artifact_root, snapshot_relative)
    receipt_target, existing_receipt = _safe_target(artifact_root, receipt_relative)
    if snapshot_target == receipt_target:
        raise force.ForceContractError("snapshot and receipt targets must differ")

    snapshot_content = _snapshot_bytes(events)
    snapshot_sha256 = hashlib.sha256(snapshot_content).hexdigest()
    receipt = build_receipt(
        contract,
        events,
        force._safe_path(snapshot_relative, "snapshot path"),
        snapshot_sha256,
    )
    receipt_content = force.canonical_bytes(receipt) + b"\n"

    if existing_snapshot is not None and existing_snapshot != snapshot_content:
        raise force.ForceContractError("existing snapshot bytes do not match terminal evidence")
    if existing_receipt is not None and existing_receipt != receipt_content:
        raise force.ForceContractError("existing snapshot receipt does not match terminal evidence")
    snapshot_created = existing_snapshot is None
    if snapshot_created:
        _exclusive_write(snapshot_target, snapshot_content)
    try:
        if existing_receipt is None:
            _exclusive_write(receipt_target, receipt_content)
        _fsync_directory(snapshot_target.parent)
        if receipt_target.parent != snapshot_target.parent:
            _fsync_directory(receipt_target.parent)
    except force.ForceContractError:
        raise
    except OSError as error:
        raise force.ForceContractError(
            f"snapshot pair durability could not be confirmed: {error}"
        ) from error

    return {
        "schema": "company-os.force-log-seal-result.v1",
        "ok": True,
        "task_id": contract["task_id"],
        "snapshot_path": snapshot_relative,
        "snapshot_sha256": snapshot_sha256,
        "receipt_path": receipt_relative,
        "receipt_sha256": hashlib.sha256(receipt_content).hexdigest(),
        "event_count": len(events),
        "terminal_event": events[-1]["event"],
    }


def _read_canonical_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink():
        raise force.ForceContractError(f"{label} must not be a symlink")
    try:
        status = path.lstat()
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise force.ForceContractError(f"{label} could not be read: {error}") from error
    if not stat.S_ISREG(status.st_mode) or not isinstance(value, dict):
        raise force.ForceContractError(f"{label} must be a regular canonical JSON object")
    if raw != force.canonical_bytes(value) + b"\n":
        raise force.ForceContractError(f"{label} bytes are not canonical JSON")
    return value, raw


def _read_snapshot(path: Path) -> tuple[list[dict[str, Any]], bytes]:
    if path.is_symlink():
        raise force.ForceContractError("snapshot must not be a symlink")
    try:
        status = path.lstat()
        raw = path.read_bytes()
    except OSError as error:
        raise force.ForceContractError(f"snapshot could not be read: {error}") from error
    if not stat.S_ISREG(status.st_mode) or not raw.endswith(b"\n"):
        raise force.ForceContractError("snapshot must be a newline-terminated regular file")
    values: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(raw.splitlines(), start=1):
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise force.ForceContractError(
                f"snapshot line {line_number} is not JSON"
            ) from error
        if not isinstance(value, dict) or raw_line != force.canonical_bytes(value):
            raise force.ForceContractError(
                f"snapshot line {line_number} is not canonical JSON"
            )
        values.append(value)
    return values, raw


def verify(
    contract_path: Path,
    artifact_root: Path,
    snapshot_relative: str,
    receipt_relative: str,
) -> dict[str, Any]:
    safe_contract_path = _safe_existing_source(artifact_root, contract_path, "force contract")
    contract = force.read_contract(safe_contract_path)
    resolved_root = force._artifact_root(artifact_root)
    force._verified_file(resolved_root, snapshot_relative)
    force._verified_file(resolved_root, receipt_relative)
    snapshot_path = resolved_root / force._safe_path(snapshot_relative, "snapshot path")
    receipt_path = resolved_root / force._safe_path(receipt_relative, "receipt path")
    receipt, receipt_bytes = _read_canonical_json(receipt_path, "snapshot receipt")
    expected_keys = {
        "schema",
        "task_id",
        "contract_sha256",
        "snapshot_path",
        "snapshot_sha256",
        "event_count",
        "terminal",
        "artifact_set_sha256",
    }
    force._exact_keys(receipt, expected_keys, "snapshot receipt")
    if receipt["schema"] != SNAPSHOT_SCHEMA:
        raise force.ForceContractError("snapshot receipt schema is unsupported")
    if receipt["task_id"] != contract["task_id"]:
        raise force.ForceContractError("snapshot receipt task does not match contract")
    if receipt["contract_sha256"] != force.canonical_sha256(contract):
        raise force.ForceContractError("snapshot receipt contract digest does not match")
    if receipt["snapshot_path"] != snapshot_relative:
        raise force.ForceContractError("snapshot receipt path does not match requested snapshot")

    events, snapshot_bytes = _read_snapshot(snapshot_path)
    accepted_events = force.validate_events(contract, events, resolved_root)
    expected_receipt = build_receipt(
        contract,
        accepted_events,
        snapshot_relative,
        hashlib.sha256(snapshot_bytes).hexdigest(),
    )
    if receipt != expected_receipt:
        raise force.ForceContractError("snapshot receipt does not match exact snapshot evidence")
    return {
        "schema": "company-os.force-log-snapshot-verification.v1",
        "ok": True,
        "task_id": contract["task_id"],
        "snapshot_sha256": receipt["snapshot_sha256"],
        "receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "event_count": len(accepted_events),
        "terminal_event": accepted_events[-1]["event"],
        "terminal_artifacts": _terminal_artifact_rows(accepted_events),
        "rework_cycles": sum(
            item["event"] == "rework_started" for item in accepted_events
        ),
        "terminal_rejection_inspected": (
            _terminal_rejection_chain(accepted_events)[2] is not None
            if accepted_events[-1]["event"] == "manager_reject"
            else None
        ),
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    seal_parser = commands.add_parser("seal")
    verify_parser = commands.add_parser("verify")
    for command in (seal_parser, verify_parser):
        command.add_argument("--contract", type=Path, required=True)
        command.add_argument("--artifact-root", type=Path, required=True)
        command.add_argument("--snapshot-path", required=True)
        command.add_argument("--receipt-path", required=True)
    seal_parser.add_argument("--events", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "seal":
            result = seal(
                args.contract,
                args.events,
                args.artifact_root,
                args.snapshot_path,
                args.receipt_path,
            )
        else:
            result = verify(
                args.contract,
                args.artifact_root,
                args.snapshot_path,
                args.receipt_path,
            )
    except force.ForceContractError as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
