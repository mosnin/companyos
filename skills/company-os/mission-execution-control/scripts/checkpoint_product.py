#!/usr/bin/env python3
"""Create a durable product checkpoint and optionally a scoped Git commit."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


class CheckpointError(ValueError):
    pass


def safe_path(root: Path, value: Any, label: str) -> tuple[Path, str]:
    if not isinstance(value, str) or not value.strip() or "\\" in value:
        raise CheckpointError(f"{label} is invalid")
    pure = PurePosixPath(value)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        raise CheckpointError(f"{label} is unsafe")
    base = root.resolve()
    current = base
    for part in pure.parts:
        current /= part
        if current.is_symlink():
            raise CheckpointError(f"{label} traverses a symlink")
    resolved = current.resolve(strict=True)
    if base != resolved and base not in resolved.parents:
        raise CheckpointError(f"{label} escapes project root")
    if not resolved.is_file() or resolved.is_symlink():
        raise CheckpointError(f"{label} is not a regular file")
    return resolved, pure.as_posix()


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def load_mission_module():
    path = Path(__file__).resolve().with_name("mission_control.py")
    spec = importlib.util.spec_from_file_location("company_os_checkpoint_mission", path)
    if spec is None or spec.loader is None:
        raise CheckpointError("mission control module is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checkpoint(
    project_root: Path,
    mission_state: Mapping[str, Any],
    candidate: Mapping[str, Any],
    verification_receipts: list[Mapping[str, Any]],
    *,
    commit: bool,
    message: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    mission = load_mission_module()
    verified_state = mission.verify_state(mission_state)
    candidate_id = candidate.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise CheckpointError("candidate_id is required")
    artifacts = []
    paths = []
    for index, raw in enumerate(candidate.get("artifacts", [])):
        if not isinstance(raw, Mapping):
            raise CheckpointError(f"artifact {index} is invalid")
        path, relative = safe_path(project_root, raw.get("path"), f"artifact[{index}].path")
        expected = raw.get("sha256")
        actual = digest_file(path)
        if expected != actual:
            raise CheckpointError(f"artifact bytes changed: {relative}")
        artifacts.append({"path": relative, "sha256": actual})
        paths.append(relative)
    if not artifacts:
        raise CheckpointError("candidate contains no product artifacts")
    commit_sha = None
    if commit:
        run_git(project_root, "rev-parse", "--is-inside-work-tree")
        staged_before = run_git(project_root, "diff", "--cached", "--name-only").stdout.splitlines()
        if staged_before:
            raise CheckpointError("refusing product checkpoint while unrelated staged files exist")
        if run_git(project_root, "config", "--get", "user.name", check=False).returncode != 0:
            run_git(project_root, "config", "user.name", "company-os-product-checkpoint-bot")
        if run_git(project_root, "config", "--get", "user.email", check=False).returncode != 0:
            run_git(project_root, "config", "user.email", "company-os-product-checkpoint-bot@users.noreply.github.com")
        run_git(project_root, "add", "--", *paths)
        diff = run_git(project_root, "diff", "--cached", "--quiet", check=False)
        if diff.returncode not in {0, 1}:
            raise CheckpointError(diff.stderr.strip() or "cannot inspect staged product checkpoint")
        if diff.returncode == 1:
            commit_message = message or f"checkpoint(company-os): {candidate_id}"
            created = run_git(project_root, "commit", "-m", commit_message, check=False)
            if created.returncode != 0:
                raise CheckpointError(created.stderr.strip() or "cannot commit product checkpoint")
        commit_sha = run_git(project_root, "rev-parse", "HEAD").stdout.strip()
    capabilities = sorted(
        {
            str(raw.get("artifact_class_id"))
            for raw in candidate.get("artifacts", [])
            if isinstance(raw, Mapping) and raw.get("artifact_class_id")
        }
    )
    return mission.create_checkpoint(
        verified_state,
        candidate_id=candidate_id,
        capability_ids=capabilities,
        artifacts=artifacts,
        verification_receipts=verification_receipts,
        git_commit=commit_sha,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--mission-state", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--verification-receipt", type=Path, action="append", default=[])
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--message")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        mission_state = json.loads(args.mission_state.read_text(encoding="utf-8"))
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        receipts = []
        for path in args.verification_receipt:
            receipts.append({"path": path.resolve().relative_to(args.project_root.resolve()).as_posix(), "sha256": digest_file(path)})
        result = checkpoint(
            args.project_root,
            mission_state,
            candidate,
            receipts,
            commit=args.commit,
            message=args.message,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "checkpoint_sha256": result["checkpoint_sha256"], "git_commit": result.get("git_commit")}, sort_keys=True))
        return 0
    except (CheckpointError, OSError, UnicodeDecodeError, json.JSONDecodeError, subprocess.SubprocessError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
