#!/usr/bin/env python3
"""Build and verify deterministic Company OS skill distributions."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Iterable


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
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.suffix in IGNORED_SUFFIXES or path.name == ".DS_Store":
            continue
        if path.is_symlink():
            raise DistributionError(f"skill distribution cannot contain symlinks: {path}")
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


def verify_manifest() -> None:
    if not MANIFEST_FILE.exists():
        raise DistributionError("distribution-manifest.json is missing")
    expected = manifest_bytes(build_manifest())
    actual = MANIFEST_FILE.read_bytes()
    if actual != expected:
        raise DistributionError("distribution manifest is stale; run write-manifest")
    print("distribution manifest verified")


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


def check_install(target: Path) -> None:
    errors: list[str] = []
    for bundle in BUNDLES:
        source = source_snapshot(bundle)
        installed = bundle_snapshot(target, bundle)
        if source != installed:
            errors.append(bundle)
    if errors:
        raise DistributionError(
            "installed bundles differ from canonical source: " + ", ".join(errors)
        )
    print("installed Company OS distribution matches canonical source")


def copy_bundle(source: Path, destination: Path) -> None:
    for path in included_files(source):
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def install(target: Path, force: bool) -> None:
    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)
    verify_manifest()
    for bundle in BUNDLES:
        source = SKILLS_ROOT / bundle
        destination = target / bundle
        if destination.exists():
            if source_snapshot(bundle) == bundle_snapshot(target, bundle):
                continue
            if not force:
                raise DistributionError(
                    f"refusing to replace modified installation: {destination}"
                )
        with tempfile.TemporaryDirectory(
            prefix=f".{bundle}-install-", dir=target
        ) as temp_dir:
            staged = Path(temp_dir) / bundle
            staged.mkdir()
            copy_bundle(source, staged)
            if bundle_snapshot(Path(temp_dir), bundle) != source_snapshot(bundle):
                raise DistributionError(f"staged bundle verification failed: {bundle}")
            backup = target / f".{bundle}.previous"
            if backup.exists():
                raise DistributionError(f"stale installation backup exists: {backup}")
            if destination.exists():
                destination.rename(backup)
            try:
                staged.rename(destination)
            except Exception:
                if backup.exists() and not destination.exists():
                    backup.rename(destination)
                raise
            if backup.exists():
                shutil.rmtree(backup)
    check_install(target)


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser()
    commands = command_parser.add_subparsers(dest="command", required=True)
    commands.add_parser("write-manifest")
    commands.add_parser("verify-manifest")
    check = commands.add_parser("check-install")
    check.add_argument("--target", type=Path, required=True)
    install_command = commands.add_parser("install")
    install_command.add_argument("--target", type=Path, required=True)
    install_command.add_argument("--force", action="store_true")
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
        elif args.command == "install":
            install(args.target, args.force)
    except DistributionError as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
