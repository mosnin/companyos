#!/usr/bin/env python3
"""Build, verify, and transactionally install Company OS skill distributions.

The installer deliberately treats an existing skill root as evidence, not as a
blank canvas.  It will only replace a non-canonical installation when the
caller supplies the manifest *and* version that prove exactly what is there.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "skills"
VERSION_FILE = ROOT / "VERSION"
MANIFEST_FILE = ROOT / "distribution-manifest.json"
BUNDLES = ("company-os", "autonomy-suite")
ENTRY_SKILLS = {
    "company-os": Path("company-os/SKILL.md"),
    "autonomy-suite": Path("SKILL.md"),
}
IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo", ".DS_Store"}


class DistributionError(RuntimeError):
    pass


def included_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise DistributionError(f"skill distribution cannot contain symlinks: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.suffix in IGNORED_SUFFIXES or path.name == ".DS_Store":
            continue
        yield path


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest() -> dict[str, object]:
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not version:
        raise DistributionError("VERSION must be non-empty")
    files: list[dict[str, object]] = []
    for bundle in BUNDLES:
        bundle_root = SKILLS_ROOT / bundle
        if not (bundle_root / ENTRY_SKILLS[bundle]).exists():
            raise DistributionError(f"bundle is missing its entry skill: {bundle}")
        for path in included_files(bundle_root):
            relative = path.relative_to(SKILLS_ROOT).as_posix()
            files.append(
                {
                    "path": relative,
                    "sha256": file_digest(path),
                    "size": path.stat().st_size,
                }
            )
    return {
        "schema_version": 1,
        "distribution_version": version,
        "bundles": list(BUNDLES),
        "files": files,
    }


def manifest_bytes(manifest: dict[str, object]) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_manifest() -> None:
    MANIFEST_FILE.write_bytes(manifest_bytes(build_manifest()))
    print(f"wrote {MANIFEST_FILE}")


def _validated_manifest(raw: Any, origin: Path) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise DistributionError(f"manifest must be an object: {origin}")
    if raw.get("schema_version") != 1:
        raise DistributionError(f"unsupported manifest schema: {origin}")
    version = raw.get("distribution_version")
    if not isinstance(version, str) or not version.strip():
        raise DistributionError(f"manifest distribution_version is invalid: {origin}")
    if raw.get("bundles") != list(BUNDLES):
        raise DistributionError(f"manifest bundle set is invalid: {origin}")
    files = raw.get("files")
    if not isinstance(files, list):
        raise DistributionError(f"manifest files must be a list: {origin}")

    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise DistributionError(f"manifest file entry is invalid: {origin}")
        path = item.get("path")
        digest = item.get("sha256")
        size = item.get("size")
        if not isinstance(path, str) or not path or path.startswith("/"):
            raise DistributionError(f"manifest file path is invalid: {origin}")
        path_parts = Path(path).parts
        if ".." in path_parts or "\\" in path or path_parts[0] not in BUNDLES:
            raise DistributionError(f"manifest file path escapes a bundle: {origin}")
        if path in seen:
            raise DistributionError(f"manifest contains duplicate path: {origin}")
        seen.add(path)
        if not isinstance(digest, str) or len(digest) != 64 or any(
            char not in "0123456789abcdef" for char in digest
        ):
            raise DistributionError(f"manifest sha256 is invalid: {origin}")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise DistributionError(f"manifest size is invalid: {origin}")

    for bundle in BUNDLES:
        entry = f"{bundle}/{ENTRY_SKILLS[bundle].as_posix()}"
        if entry not in seen:
            raise DistributionError(f"manifest is missing entry skill for {bundle}: {origin}")
    return raw


def read_manifest(path: Path) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise DistributionError(f"manifest is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise DistributionError(f"manifest is not valid JSON: {path}") from error
    return _validated_manifest(raw, path)


def verify_manifest() -> dict[str, object]:
    actual = read_manifest(MANIFEST_FILE)
    expected = build_manifest()
    if manifest_bytes(actual) != manifest_bytes(expected):
        raise DistributionError("distribution manifest is stale; run write-manifest")
    print("distribution manifest verified")
    return actual


def bundle_snapshot(root: Path, bundle: str) -> dict[str, tuple[str, int]]:
    bundle_root = root / bundle
    if not bundle_root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): (file_digest(path), path.stat().st_size)
        for path in included_files(bundle_root)
    }


def source_snapshot(bundle: str) -> dict[str, tuple[str, int]]:
    return bundle_snapshot(SKILLS_ROOT, bundle)


def manifest_snapshot(manifest: dict[str, object], bundle: str) -> dict[str, tuple[str, int]]:
    return {
        str(item["path"]): (str(item["sha256"]), int(item["size"]))
        for item in manifest["files"]  # type: ignore[index]
        if str(item["path"]).split("/", 1)[0] == bundle
    }


def install_matches_manifest(target: Path, manifest: dict[str, object]) -> bool:
    return all(
        bundle_snapshot(target, bundle) == manifest_snapshot(manifest, bundle)
        for bundle in BUNDLES
    )


def source_matches_manifest(manifest: dict[str, object]) -> bool:
    return all(
        source_snapshot(bundle) == manifest_snapshot(manifest, bundle)
        for bundle in BUNDLES
    )


def require_source_matches_manifest(manifest: dict[str, object], stage: str) -> None:
    if not source_matches_manifest(manifest):
        raise DistributionError(
            "canonical source changed after committed-manifest validation "
            f"during {stage}"
        )


def snapshot_record(snapshot: dict[str, tuple[str, int]]) -> list[dict[str, object]]:
    return [
        {"path": path, "sha256": digest, "size": size}
        for path, (digest, size) in sorted(snapshot.items())
    ]


def snapshot_from_record(value: object, origin: Path) -> dict[str, tuple[str, int]]:
    if not isinstance(value, list):
        raise DistributionError(f"transaction snapshot is invalid: {origin}")
    snapshot: dict[str, tuple[str, int]] = {}
    for entry in value:
        if not isinstance(entry, dict):
            raise DistributionError(f"transaction snapshot is invalid: {origin}")
        path = entry.get("path")
        digest = entry.get("sha256")
        size = entry.get("size")
        if (
            not isinstance(path, str)
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or path in snapshot
        ):
            raise DistributionError(f"transaction snapshot is invalid: {origin}")
        snapshot[path] = (digest, size)
    return snapshot


def check_install(target: Path) -> None:
    target = target.resolve()
    with install_lock(target):
        paths = transaction_paths(target)
        if paths["journal"].exists():
            raise DistributionError(
                "recovery required before check-install; active transaction journal at "
                f"{paths['journal']}. Run recover-install --target {target}"
            )
        if paths["root"].exists():
            raise DistributionError(
                "recovery required before check-install; orphan transaction root at "
                f"{paths['root']}. Run recover-install --target {target}"
            )
        manifest = verify_manifest()
        _check_install_snapshot(target, manifest)
    print("installed Company OS distribution matches canonical source")


def copy_bundle(source: Path, destination: Path) -> None:
    for path in included_files(source):
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        _fsync_file(target)


# Small seams intentionally kept separate for deterministic fault-injection tests.
def rename_path(source: Path, destination: Path) -> None:
    source.rename(destination)


def remove_tree(path: Path) -> None:
    shutil.rmtree(path)


def _transaction_id(target: Path) -> str:
    return hashlib.sha256(str(target.resolve()).encode("utf-8")).hexdigest()[:16]


def transaction_paths(target: Path) -> dict[str, Path]:
    prefix = target.parent / f".company-os-install-{_transaction_id(target)}"
    return {
        "journal": Path(f"{prefix}.journal.json"),
        "root": Path(f"{prefix}.transaction"),
    }


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_tree(root: Path) -> None:
    """Make a copied recovery/staging tree durable, leaves before directories."""
    for path in sorted(root.rglob("*")):
        if path.is_file():
            _fsync_file(path)
    directories = [root, *(path for path in root.rglob("*") if path.is_dir())]
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        _fsync_directory(directory)


def durable_rename(source: Path, destination: Path) -> None:
    """Persist both directory entries before advancing the transaction journal."""
    rename_path(source, destination)
    _fsync_directory(source.parent)
    if destination.parent != source.parent:
        _fsync_directory(destination.parent)


def write_transaction_journal(path: Path, journal: dict[str, object]) -> None:
    """Atomically persist a journal before a filesystem mutation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    payload = (json.dumps(journal, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def load_transaction_journal(path: Path) -> dict[str, object]:
    try:
        journal = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise DistributionError(f"transaction journal is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise DistributionError(f"transaction journal is corrupt: {path}") from error
    if not isinstance(journal, dict) or journal.get("schema_version") != 1:
        raise DistributionError(f"transaction journal is invalid: {path}")
    if not isinstance(journal.get("target"), str):
        raise DistributionError(f"transaction journal target is invalid: {path}")
    prior = journal.get("prior_present")
    if not isinstance(prior, dict) or set(prior) != set(BUNDLES):
        raise DistributionError(f"transaction journal prior state is invalid: {path}")
    if any(not isinstance(prior[bundle], bool) for bundle in BUNDLES):
        raise DistributionError(f"transaction journal prior state is invalid: {path}")
    snapshots = journal.get("prior_snapshots")
    if not isinstance(snapshots, dict) or set(snapshots) != set(BUNDLES):
        raise DistributionError(f"transaction journal snapshots are invalid: {path}")
    for bundle in BUNDLES:
        snapshot = snapshot_from_record(snapshots[bundle], path)
        if bool(prior[bundle]) != bool(snapshot):
            raise DistributionError(f"transaction journal snapshot presence is invalid: {path}")
    return journal


@contextmanager
def install_lock(target: Path) -> Iterable[None]:
    """Serialize operations without creating a lock artifact in the target tree."""
    parent = target.parent
    if not parent.is_dir():
        raise DistributionError(f"target parent does not exist for install lock: {parent}")
    descriptor = os.open(parent, os.O_RDONLY)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise DistributionError(
                f"another Company OS install is active for target parent: {parent}"
            ) from error
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _target_has_bundles(target: Path) -> bool:
    return any((target / bundle).exists() for bundle in BUNDLES)


def _validate_prior_install(
    target: Path,
    prior_manifest: Path | None,
    prior_version: str | None,
) -> None:
    if prior_manifest is None or prior_version is None:
        raise DistributionError(
            "refusing blind upgrade: provide --prior-manifest and --prior-version"
        )
    previous = read_manifest(prior_manifest)
    if previous["distribution_version"] != prior_version:
        raise DistributionError("prior manifest version does not match --prior-version")
    if not install_matches_manifest(target, previous):
        raise DistributionError(
            "refusing upgrade: target does not exactly match the supplied prior manifest"
        )


def _stage_canonical_bundles(
    stage_root: Path,
    manifest: dict[str, object],
) -> dict[str, dict[str, tuple[str, int]]]:
    if stage_root.exists():
        raise DistributionError(f"transaction staging root already exists: {stage_root}")
    stage_root.mkdir(parents=True)
    expected = {bundle: manifest_snapshot(manifest, bundle) for bundle in BUNDLES}
    try:
        require_source_matches_manifest(manifest, "before staging")
        for bundle in BUNDLES:
            staged = stage_root / bundle
            staged.mkdir()
            copy_bundle(SKILLS_ROOT / bundle, staged)
            require_source_matches_manifest(manifest, f"staging {bundle}")
        for bundle in BUNDLES:
            if bundle_snapshot(stage_root, bundle) != expected[bundle]:
                raise DistributionError(f"staged bundle verification failed: {bundle}")
        require_source_matches_manifest(manifest, "after staging")
    except BaseException:
        remove_tree(stage_root)
        raise
    return expected


def _restore_prior_bundles(
    target: Path,
    prior_present: dict[str, bool],
    backups: Path,
    recovery: Path,
) -> list[str]:
    errors: list[str] = []
    for bundle in reversed(BUNDLES):
        destination = target / bundle
        try:
            if destination.exists():
                remove_tree(destination)
            if not prior_present[bundle]:
                continue
            backup = backups / bundle
            if backup.exists():
                durable_rename(backup, destination)
            elif (recovery / bundle).exists():
                # Copy rather than move: a partial second restore must leave the
                # last recovery copy available for the next invocation.
                shutil.copytree(recovery / bundle, destination)
                _fsync_tree(destination)
                _fsync_directory(destination.parent)
            else:
                raise DistributionError(f"missing recovery copy for {bundle}")
        except Exception as error:  # restoration is best effort, but never concealed
            errors.append(f"{bundle}: {error}")
    return errors


def _remove_completed_transaction(paths: dict[str, Path]) -> None:
    # Journal removal is the commit point for a successful rollback. Never remove
    # the final recovery tree while an active journal can still point at it.
    if paths["journal"].exists():
        paths["journal"].unlink()
        _fsync_directory(paths["journal"].parent)
    if paths["root"].exists():
        try:
            remove_tree(paths["root"])
        except Exception:
            # The journal is gone and the target was restored; this is only a
            # removable orphan, not an incomplete transaction.
            pass


def recover_incomplete_transaction(target: Path) -> bool:
    """Restore the exact prior pair from a durable interrupted transaction.

    Returns ``True`` only when a journal existed and recovery completed. On
    failure the journal and recovery directory are deliberately retained so a
    future invocation can retry or an operator can inspect the incident.
    """
    paths = transaction_paths(target)
    journal_path = paths["journal"]
    if not journal_path.exists():
        # A crash before the fsynced marker cannot have mutated the target.
        if paths["root"].exists():
            remove_tree(paths["root"])
        return False
    journal = load_transaction_journal(journal_path)
    if Path(str(journal["target"])).resolve() != target.resolve():
        raise DistributionError(f"transaction journal targets another install: {journal_path}")
    root = paths["root"]
    recovery = root / "recovery"
    backups = root / "backups"
    if not root.exists() or not recovery.exists() or not backups.exists():
        raise DistributionError(f"transaction recovery material is missing: {journal_path}")
    prior = journal["prior_present"]
    snapshots = journal["prior_snapshots"]
    assert isinstance(prior, dict)
    assert isinstance(snapshots, dict)
    expected = {
        bundle: snapshot_from_record(snapshots[bundle], journal_path) for bundle in BUNDLES
    }
    for bundle in BUNDLES:
        if bool(prior[bundle]) and bundle_snapshot(recovery, bundle) != expected[bundle]:
            raise DistributionError(
                "transaction recovery copy does not match the journal-bound prior snapshot; "
                f"recovery retained at {journal_path}: {bundle}"
            )
    errors = _restore_prior_bundles(
        target,
        {bundle: bool(prior[bundle]) for bundle in BUNDLES},
        backups,
        recovery,
    )
    for bundle in BUNDLES:
        if bundle_snapshot(target, bundle) != expected[bundle]:
            errors.append(f"{bundle}: restored snapshot does not match journal-bound prior state")
    if errors:
        raise DistributionError(
            "transaction rollback incomplete; recovery retained at "
            f"{journal_path}: " + "; ".join(errors)
        )
    try:
        _remove_completed_transaction(paths)
    except Exception as error:
        raise DistributionError(
            "transaction rollback restored the target but cleanup is retained at "
            f"{journal_path}: {error}"
        ) from error
    return True


def recover_install(target: Path) -> None:
    """Explicitly recover an interrupted transaction or clean a markerless orphan."""
    target = target.resolve()
    with install_lock(target):
        paths = transaction_paths(target)
        had_journal = paths["journal"].exists()
        had_orphan = paths["root"].exists()
        recovered = recover_incomplete_transaction(target)
    if recovered or had_journal:
        print("interrupted Company OS install recovered")
    elif had_orphan:
        print("markerless Company OS transaction staging cleaned")
    else:
        print("no interrupted Company OS install found")


def _write_operation(journal_path: Path, journal: dict[str, object], operation: str) -> None:
    journal["operation"] = operation
    write_transaction_journal(journal_path, journal)


def _prepare_transaction(
    target: Path,
    paths: dict[str, Path],
    manifest: dict[str, object],
) -> tuple[dict[str, object], Path]:
    root = paths["root"]
    if root.exists():
        raise DistributionError(f"transaction directory already exists: {root}")
    root.mkdir(parents=True)
    staged = root / "staged"
    backups = root / "backups"
    recovery = root / "recovery"
    try:
        _stage_canonical_bundles(staged, manifest)
        backups.mkdir()
        recovery.mkdir()
        prior_present = {bundle: (target / bundle).exists() for bundle in BUNDLES}
        prior_snapshots = {
            bundle: bundle_snapshot(target, bundle) for bundle in BUNDLES
        }
        for bundle, exists in prior_present.items():
            if exists:
                shutil.copytree(target / bundle, recovery / bundle)
        _fsync_tree(root)
        for bundle in BUNDLES:
            if bundle_snapshot(recovery, bundle) != prior_snapshots[bundle]:
                raise DistributionError(f"recovery snapshot verification failed: {bundle}")
        journal: dict[str, object] = {
            "schema_version": 1,
            "target": str(target.resolve()),
            "prior_present": prior_present,
            "prior_snapshots": {
                bundle: snapshot_record(prior_snapshots[bundle]) for bundle in BUNDLES
            },
            "operation": "prepared",
        }
        # This is the durable boundary: no target mutation may precede it.
        write_transaction_journal(paths["journal"], journal)
        return journal, staged
    except BaseException:
        if not paths["journal"].exists() and root.exists():
            remove_tree(root)
        raise


def _transactional_replace(
    target: Path,
    paths: dict[str, Path],
    journal: dict[str, object],
    staged: Path,
    manifest: dict[str, object],
) -> None:
    root = paths["root"]
    backups = root / "backups"
    recovery = root / "recovery"
    prior = journal["prior_present"]
    assert isinstance(prior, dict)
    rollback_required = False
    try:
        for bundle in BUNDLES:
            require_source_matches_manifest(manifest, f"before installing {bundle}")
            destination = target / bundle
            if bool(prior[bundle]):
                backup = backups / bundle
                # Mark rollback before the first destructive rename. This includes
                # a staged-rename failure immediately after moving the old bundle.
                rollback_required = True
                _write_operation(paths["journal"], journal, f"before-backup-{bundle}")
                durable_rename(destination, backup)
                _write_operation(paths["journal"], journal, f"after-backup-{bundle}")
            rollback_required = True
            _write_operation(paths["journal"], journal, f"before-install-{bundle}")
            durable_rename(staged / bundle, destination)
            _write_operation(paths["journal"], journal, f"after-install-{bundle}")

        _check_install_snapshot(target, manifest)

        # Recovery copies remain available until every pre-commit cleanup completes.
        for bundle in BUNDLES:
            backup = backups / bundle
            if backup.exists():
                _write_operation(paths["journal"], journal, f"before-cleanup-{bundle}")
                remove_tree(backup)
                _write_operation(paths["journal"], journal, f"after-cleanup-{bundle}")
        staged_root = root / "staged"
        if staged_root.exists():
            _write_operation(paths["journal"], journal, "before-cleanup-staged")
            remove_tree(staged_root)
            _write_operation(paths["journal"], journal, "after-cleanup-staged")

        # Do not delete the final recovery copy while the journal is active. Once
        # the committed marker is durable, losing it cannot strand a partial pair.
        _write_operation(paths["journal"], journal, "committed")
        paths["journal"].unlink()
        _fsync_directory(paths["journal"].parent)
        # Post-commit garbage collection is intentionally best-effort. An orphan
        # without a journal is known to be post-commit and can be removed safely
        # before a future transaction starts.
        if root.exists():
            try:
                remove_tree(root)
            except Exception:
                pass
    except Exception as error:
        if not rollback_required:
            raise DistributionError(f"transactional install failed before mutation: {error}") from error
        try:
            recover_incomplete_transaction(target)
        except DistributionError as recovery_error:
            raise DistributionError(
                "transactional install failed; rollback incomplete; recovery retained at "
                f"{paths['journal']}: {recovery_error}"
            ) from error
        raise DistributionError(f"transactional install failed and was rolled back: {error}") from error


def _check_install_snapshot(target: Path, manifest: dict[str, object]) -> None:
    errors: list[str] = []
    for bundle in BUNDLES:
        if manifest_snapshot(manifest, bundle) != bundle_snapshot(target, bundle):
            errors.append(bundle)
    if errors:
        raise DistributionError(
            "installed bundles differ from canonical source: " + ", ".join(errors)
        )


def install(
    target: Path,
    force: bool = False,
    *,
    prior_manifest: Path | None = None,
    prior_version: str | None = None,
) -> None:
    """Install both bundles, refusing unproven replacement.

    ``force`` remains accepted for backwards-compatible CLI parsing but has no
    authority on its own. It cannot bypass the explicit prior-install proof.
    """
    del force
    target = target.resolve()
    # Creation is authorized for install; inspection and recovery never create a
    # parent merely to obtain a coordination lock.
    target.parent.mkdir(parents=True, exist_ok=True)
    with install_lock(target):
        recover_incomplete_transaction(target)
        current_manifest = verify_manifest()

        if target.exists() and install_matches_manifest(target, current_manifest):
            print("installed Company OS distribution matches canonical source")
            return

        existing_bundles = target.exists() and _target_has_bundles(target)
        if existing_bundles:
            _validate_prior_install(target, prior_manifest, prior_version)

        # Stage and verify both bundles before creating or changing the target root.
        paths = transaction_paths(target)
        journal, staged = _prepare_transaction(target, paths, current_manifest)
        if target.exists() and _target_has_bundles(target):
            # Detect a change between the prior validation and the first mutation.
            _validate_prior_install(target, prior_manifest, prior_version)
        target.mkdir(parents=True, exist_ok=True)
        _fsync_directory(target.parent)
        _transactional_replace(target, paths, journal, staged, current_manifest)


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser()
    commands = command_parser.add_subparsers(dest="command", required=True)
    commands.add_parser("write-manifest")
    commands.add_parser("verify-manifest")
    check = commands.add_parser("check-install")
    check.add_argument("--target", type=Path, required=True)
    recover = commands.add_parser("recover-install")
    recover.add_argument("--target", type=Path, required=True)
    install_command = commands.add_parser("install")
    install_command.add_argument("--target", type=Path, required=True)
    install_command.add_argument("--prior-manifest", type=Path)
    install_command.add_argument("--prior-version")
    install_command.add_argument(
        "--force",
        action="store_true",
        help="deprecated; cannot bypass prior-manifest validation",
    )
    return command_parser


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "write-manifest":
            write_manifest()
        elif args.command == "verify-manifest":
            verify_manifest()
        elif args.command == "check-install":
            check_install(args.target)
        elif args.command == "recover-install":
            recover_install(args.target)
        elif args.command == "install":
            install(
                args.target,
                args.force,
                prior_manifest=args.prior_manifest,
                prior_version=args.prior_version,
            )
    except DistributionError as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
