from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "distribution.py"
CONTROLLER = (
    ROOT
    / "skills"
    / "company-os"
    / "elastic-company-os"
    / "scripts"
    / "company_os_controller.py"
)


def load_distribution():
    spec = importlib.util.spec_from_file_location("company_os_distribution", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def generated_manifest(distribution, directory: Path):
    original = distribution.MANIFEST_FILE
    manifest = directory / "current-manifest.json"
    manifest.write_bytes(distribution.manifest_bytes(distribution.build_manifest()))
    distribution.MANIFEST_FILE = manifest
    try:
        yield manifest
    finally:
        distribution.MANIFEST_FILE = original


def copy_canonical(distribution, target: Path) -> None:
    for bundle in distribution.BUNDLES:
        shutil.copytree(distribution.SKILLS_ROOT / bundle, target / bundle)


def isolated_canonical_distribution(directory: Path):
    """Use a disposable canonical source so mutation tests never touch the checkout."""
    distribution = load_distribution()
    source_root = directory / "isolated-canonical"
    shutil.copytree(distribution.SKILLS_ROOT, source_root / "skills")
    shutil.copy2(distribution.VERSION_FILE, source_root / "VERSION")
    distribution.SKILLS_ROOT = source_root / "skills"
    distribution.VERSION_FILE = source_root / "VERSION"
    return distribution


def prior_install(distribution, target: Path, directory: Path, version: str = "prior-1") -> Path:
    copy_canonical(distribution, target)
    for bundle in distribution.BUNDLES:
        entry = target / bundle / distribution.ENTRY_SKILLS[bundle]
        entry.write_text(entry.read_text() + "\nprior release marker\n")
    manifest = distribution.build_manifest()
    manifest["distribution_version"] = version
    manifest["files"] = [
        {"path": path, "sha256": digest, "size": size}
        for bundle in distribution.BUNDLES
        for path, (digest, size) in distribution.bundle_snapshot(target, bundle).items()
    ]
    prior = directory / f"prior-{target.name}.json"
    prior.write_bytes(distribution.manifest_bytes(manifest))
    return prior


def exact_tree_state(root: Path) -> dict[str, tuple[bytes | None, int, int, int]]:
    if not root.exists():
        return {}
    state: dict[str, tuple[bytes | None, int, int, int]] = {}
    for path in [root, *sorted(root.rglob("*"))]:
        stat = path.stat()
        state[path.relative_to(root).as_posix()] = (
            path.read_bytes() if path.is_file() else None,
            stat.st_mode,
            stat.st_size,
            stat.st_mtime_ns,
        )
    return state


class DistributionTests(unittest.TestCase):
    def test_fresh_manifest_verifies(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            with generated_manifest(distribution, Path(temp_dir)):
                distribution.verify_manifest()

    def test_install_lock_rejects_a_second_owner(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "skills"
            descriptor = os.open(target.parent, os.O_RDONLY)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(distribution.DistributionError, "install is active"):
                    distribution.install(target)
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def test_check_install_creates_no_lock_or_other_artifact_for_external_target(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "external-skills"
            copy_canonical(distribution, target)
            paths = distribution.transaction_paths(target.resolve())
            before_parent = exact_tree_state(root)
            distribution.check_install(target)
            self.assertEqual(exact_tree_state(root), before_parent)
            self.assertFalse(paths["journal"].exists())
            self.assertFalse(paths["root"].exists())

    def test_durable_rename_fsyncs_both_affected_parents(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_parent = root / "source"
            destination_parent = root / "destination"
            source_parent.mkdir()
            destination_parent.mkdir()
            source = source_parent / "bundle"
            destination = destination_parent / "bundle"
            source.mkdir()
            calls: list[Path] = []
            original_fsync = distribution._fsync_directory

            def record_fsync(path):
                calls.append(path)

            distribution._fsync_directory = record_fsync
            try:
                distribution.durable_rename(source, destination)
            finally:
                distribution._fsync_directory = original_fsync
            self.assertTrue(destination.exists())
            self.assertEqual(calls, [source_parent, destination_parent])

    def test_check_install_is_read_only_for_interrupted_journal_then_recover_passes(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "skills"
            with generated_manifest(distribution, root):
                distribution.install(target)
                paths = distribution.transaction_paths(target.resolve())
                journal, _staged = distribution._prepare_transaction(
                    target,
                    paths,
                    distribution.read_manifest(distribution.MANIFEST_FILE),
                )
                distribution.durable_rename(
                    target / "company-os",
                    paths["root"] / "backups" / "company-os",
                )
                # The prepared journal binds the canonical pre-mutation state.
                self.assertEqual(journal["operation"], "prepared")
                before_target = exact_tree_state(target)
                before_journal = paths["journal"].read_bytes()
                before_transaction = exact_tree_state(paths["root"])
                before_hashes = {
                    bundle: distribution.bundle_snapshot(target, bundle)
                    for bundle in distribution.BUNDLES
                }
                with self.assertRaisesRegex(distribution.DistributionError, "recovery required"):
                    distribution.check_install(target)
                self.assertEqual(exact_tree_state(target), before_target)
                self.assertEqual(paths["journal"].read_bytes(), before_journal)
                self.assertEqual(exact_tree_state(paths["root"]), before_transaction)
                self.assertEqual(
                    {
                        bundle: distribution.bundle_snapshot(target, bundle)
                        for bundle in distribution.BUNDLES
                    },
                    before_hashes,
                )
                distribution.recover_install(target)
                distribution.check_install(target)

    def test_check_install_is_read_only_for_orphan_root_then_recover_passes(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "skills"
            with generated_manifest(distribution, root):
                distribution.install(target)
                paths = distribution.transaction_paths(target.resolve())
                orphan = paths["root"]
                orphan.mkdir()
                (orphan / "orphan-marker").write_text("safe to clean only by recover-install")
                before_target = exact_tree_state(target)
                before_transaction = exact_tree_state(orphan)
                before_hashes = {
                    bundle: distribution.bundle_snapshot(target, bundle)
                    for bundle in distribution.BUNDLES
                }
                with self.assertRaisesRegex(distribution.DistributionError, "orphan transaction root"):
                    distribution.check_install(target)
                self.assertEqual(exact_tree_state(target), before_target)
                self.assertEqual(exact_tree_state(orphan), before_transaction)
                self.assertEqual(
                    {
                        bundle: distribution.bundle_snapshot(target, bundle)
                        for bundle in distribution.BUNDLES
                    },
                    before_hashes,
                )
                distribution.recover_install(target)
                self.assertFalse(orphan.exists())
                distribution.check_install(target)

    def test_install_to_empty_root_is_exact_and_idempotent(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "skills"
            with generated_manifest(distribution, root) as manifest_path:
                committed = distribution.read_manifest(manifest_path)
                expected = {
                    bundle: distribution.manifest_snapshot(committed, bundle)
                    for bundle in distribution.BUNDLES
                }
                distribution.install(target)
                first = {
                    bundle: distribution.bundle_snapshot(target, bundle)
                    for bundle in distribution.BUNDLES
                }
                distribution.install(target)
                second = {
                    bundle: distribution.bundle_snapshot(target, bundle)
                    for bundle in distribution.BUNDLES
                }
            self.assertEqual(first, expected)
            self.assertEqual(second, expected)

    def test_manifest_binding_rejects_source_mutation_before_or_during_staging(self) -> None:
        for timing in ("before", "during"):
            with self.subTest(timing=timing):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    distribution = isolated_canonical_distribution(root)
                    target = root / f"skills-{timing}"
                    entry = (
                        distribution.SKILLS_ROOT
                        / "company-os"
                        / distribution.ENTRY_SKILLS["company-os"]
                    )
                    original_prepare = distribution._prepare_transaction
                    original_copy = distribution.copy_bundle

                    def mutate_source():
                        entry.write_text(entry.read_text() + "\nmutation after manifest validation\n")

                    if timing == "before":
                        def mutate_before_stage(*args, **kwargs):
                            mutate_source()
                            return original_prepare(*args, **kwargs)

                        distribution._prepare_transaction = mutate_before_stage
                    else:
                        mutated = False

                        def mutate_during_stage(source, destination):
                            nonlocal mutated
                            original_copy(source, destination)
                            if not mutated and source.name == "company-os":
                                mutated = True
                                mutate_source()

                        distribution.copy_bundle = mutate_during_stage
                    try:
                        with generated_manifest(distribution, root):
                            with self.assertRaisesRegex(
                                distribution.DistributionError,
                                "canonical source changed after committed-manifest validation",
                            ):
                                distribution.install(target)
                    finally:
                        distribution._prepare_transaction = original_prepare
                        distribution.copy_bundle = original_copy
                    self.assertFalse(target.exists())

    def test_modified_install_refuses_blind_force(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "skills"
            with generated_manifest(distribution, root):
                distribution.install(target)
                skill = target / "company-os" / "company-os" / "SKILL.md"
                skill.write_text(skill.read_text() + "\nmodified\n")
                with self.assertRaisesRegex(distribution.DistributionError, "blind upgrade"):
                    distribution.install(target, force=True)

    def test_prior_manifest_rejects_modified_or_extra_install(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "skills"
            prior = root / "prior.json"
            with generated_manifest(distribution, root):
                distribution.install(target)
                prior.write_bytes(distribution.manifest_bytes(distribution.build_manifest()))
                (target / "company-os" / "extra.md").write_text("not in manifest")
                with self.assertRaisesRegex(distribution.DistributionError, "does not exactly match"):
                    distribution.install(
                        target,
                        prior_manifest=prior,
                        prior_version=distribution.build_manifest()["distribution_version"],
                    )

    def test_prior_manifest_rejects_wrong_version_or_manifest(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "skills"
            prior = root / "prior.json"
            with generated_manifest(distribution, root):
                distribution.install(target)
                prior.write_bytes(distribution.manifest_bytes(distribution.build_manifest()))
                # Make the target non-canonical while leaving the supplied proof stale.
                (target / "autonomy-suite" / "SKILL.md").write_text("changed")
                with self.assertRaisesRegex(distribution.DistributionError, "prior manifest version"):
                    distribution.install(target, prior_manifest=prior, prior_version="not-the-version")
                with self.assertRaisesRegex(distribution.DistributionError, "does not exactly match"):
                    distribution.install(
                        target,
                        prior_manifest=prior,
                        prior_version=distribution.build_manifest()["distribution_version"],
                    )

    def test_both_bundles_stage_before_target_mutation(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "skills"
            seen_target_states: list[bool] = []
            original_copy = distribution.copy_bundle

            def observing_copy(source, destination):
                seen_target_states.append(target.exists())
                original_copy(source, destination)

            distribution.copy_bundle = observing_copy
            try:
                with generated_manifest(distribution, root):
                    distribution.install(target)
            finally:
                distribution.copy_bundle = original_copy
            self.assertEqual(seen_target_states, [False, False])

    def test_second_bundle_rename_failure_restores_both_prior_bundles(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "skills"
            prior = prior_install(distribution, target, root)
            before = {
                bundle: distribution.bundle_snapshot(target, bundle)
                for bundle in distribution.BUNDLES
            }
            original_rename = distribution.rename_path
            failed = False

            def fail_second_stage(source, destination):
                nonlocal failed
                if (
                    not failed
                    and source.name == "autonomy-suite"
                    and destination == (target / "autonomy-suite").resolve()
                ):
                    failed = True
                    raise OSError("injected second bundle failure")
                original_rename(source, destination)

            distribution.rename_path = fail_second_stage
            try:
                with generated_manifest(distribution, root):
                    with self.assertRaisesRegex(distribution.DistributionError, "transactional install failed"):
                        distribution.install(
                            target,
                            prior_manifest=prior,
                            prior_version="prior-1",
                        )
            finally:
                distribution.rename_path = original_rename
            after = {
                bundle: distribution.bundle_snapshot(target, bundle)
                for bundle in distribution.BUNDLES
            }
            self.assertEqual(after, before)

    def test_first_staged_rename_failure_restores_both_prior_bundles(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "skills"
            prior = prior_install(distribution, target, root)
            before = {
                bundle: distribution.bundle_snapshot(target, bundle)
                for bundle in distribution.BUNDLES
            }
            original_rename = distribution.rename_path
            failed = False

            def fail_first_staged_rename(source, destination):
                nonlocal failed
                if (
                    not failed
                    and source.parent.name == "staged"
                    and source.name == "company-os"
                    and destination == (target / "company-os").resolve()
                ):
                    failed = True
                    raise OSError("injected first staged rename failure")
                original_rename(source, destination)

            distribution.rename_path = fail_first_staged_rename
            try:
                with generated_manifest(distribution, root):
                    with self.assertRaisesRegex(distribution.DistributionError, "rolled back"):
                        distribution.install(
                            target,
                            prior_manifest=prior,
                            prior_version="prior-1",
                        )
            finally:
                distribution.rename_path = original_rename
            after = {
                bundle: distribution.bundle_snapshot(target, bundle)
                for bundle in distribution.BUNDLES
            }
            self.assertEqual(after, before)

    def test_crash_before_and_after_every_rename_recovers_prior_pair_before_retry(self) -> None:
        for rename_number in range(1, 5):
            for timing in ("before", "after"):
                with self.subTest(rename_number=rename_number, timing=timing):
                    distribution = load_distribution()
                    with tempfile.TemporaryDirectory() as temp_dir:
                        root = Path(temp_dir)
                        target = root / f"skills-{rename_number}-{timing}"
                        prior = prior_install(distribution, target, root)
                        before = {
                            bundle: distribution.bundle_snapshot(target, bundle)
                            for bundle in distribution.BUNDLES
                        }
                        original_rename = distribution.rename_path
                        call_count = 0

                        def crash_at_rename(source, destination):
                            nonlocal call_count
                            call_count += 1
                            if call_count == rename_number and timing == "before":
                                raise SystemExit("injected crash before rename")
                            original_rename(source, destination)
                            if call_count == rename_number and timing == "after":
                                raise SystemExit("injected crash after rename")

                        distribution.rename_path = crash_at_rename
                        try:
                            with generated_manifest(distribution, root) as manifest:
                                with self.assertRaises(SystemExit):
                                    distribution.install(
                                        target,
                                        prior_manifest=prior,
                                        prior_version="prior-1",
                                    )
                                # A fresh process/module invocation recovers the prior pair
                                # automatically before it attempts the requested upgrade.
                                fresh = load_distribution()
                                fresh.MANIFEST_FILE = manifest
                                observed_prior: list[dict[str, dict[str, tuple[str, int]]]] = []
                                original_recover = fresh.recover_incomplete_transaction

                                def observe_recovery(recovery_target):
                                    recovered = original_recover(recovery_target)
                                    observed_prior.append(
                                        {
                                            bundle: fresh.bundle_snapshot(recovery_target, bundle)
                                            for bundle in fresh.BUNDLES
                                        }
                                    )
                                    return recovered

                                fresh.recover_incomplete_transaction = observe_recovery
                                fresh.install(
                                    target,
                                    prior_manifest=prior,
                                    prior_version="prior-1",
                                )
                                self.assertEqual(observed_prior, [before])
                                fresh.check_install(target)
                        finally:
                            distribution.rename_path = original_rename

    def test_failed_rollback_retains_journal_and_recovery_material(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "skills"
            prior = prior_install(distribution, target, root)
            paths = distribution.transaction_paths(target.resolve())
            original_rename = distribution.rename_path
            original_remove = distribution.remove_tree
            failed = False

            def fail_first_staged_rename(source, destination):
                nonlocal failed
                if (
                    not failed
                    and source.parent.name == "staged"
                    and source.name == "company-os"
                ):
                    failed = True
                    raise OSError("injected install failure")
                original_rename(source, destination)

            def fail_rollback_remove(path):
                if path == (target / "autonomy-suite").resolve():
                    raise OSError("injected rollback failure")
                original_remove(path)

            distribution.rename_path = fail_first_staged_rename
            distribution.remove_tree = fail_rollback_remove
            try:
                with generated_manifest(distribution, root):
                    with self.assertRaisesRegex(distribution.DistributionError, "recovery retained at"):
                        distribution.install(
                            target,
                            prior_manifest=prior,
                            prior_version="prior-1",
                        )
            finally:
                distribution.rename_path = original_rename
                distribution.remove_tree = original_remove
            self.assertTrue(paths["journal"].exists())
            self.assertTrue((paths["root"] / "recovery").exists())

    def test_tampered_or_missing_recovery_is_rejected_with_incident_retained(self) -> None:
        for damage in ("tampered", "missing"):
            with self.subTest(damage=damage):
                distribution = load_distribution()
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    target = root / f"skills-{damage}"
                    prior = prior_install(distribution, target, root)
                    paths = distribution.transaction_paths(target.resolve())
                    original_rename = distribution.rename_path
                    crashed = False

                    def crash_before_first_staged_rename(source, destination):
                        nonlocal crashed
                        if not crashed and source.parent.name == "staged":
                            crashed = True
                            raise SystemExit("injected crash")
                        original_rename(source, destination)

                    distribution.rename_path = crash_before_first_staged_rename
                    try:
                        with generated_manifest(distribution, root) as manifest:
                            with self.assertRaises(SystemExit):
                                distribution.install(
                                    target,
                                    prior_manifest=prior,
                                    prior_version="prior-1",
                                )
                            recovery_entry = (
                                paths["root"]
                                / "recovery"
                                / "company-os"
                                / distribution.ENTRY_SKILLS["company-os"]
                            )
                            if damage == "tampered":
                                recovery_entry.write_text("tampered recovery")
                            else:
                                shutil.rmtree(paths["root"] / "recovery" / "company-os")
                            fresh = load_distribution()
                            fresh.MANIFEST_FILE = manifest
                            with self.assertRaisesRegex(
                                fresh.DistributionError,
                                "recovery copy does not match",
                            ):
                                fresh.recover_incomplete_transaction(target)
                    finally:
                        distribution.rename_path = original_rename
                    self.assertTrue(paths["journal"].exists())
                    self.assertTrue((paths["root"] / "recovery").exists())

    def test_backup_cleanup_failure_restores_both_prior_bundles(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "skills"
            prior = prior_install(distribution, target, root)
            before = {
                bundle: distribution.bundle_snapshot(target, bundle)
                for bundle in distribution.BUNDLES
            }
            original_remove = distribution.remove_tree

            def fail_backup_cleanup(path):
                if path.name == "autonomy-suite" and path.parent.name == "backups":
                    raise OSError("injected cleanup failure")
                original_remove(path)

            distribution.remove_tree = fail_backup_cleanup
            try:
                with generated_manifest(distribution, root):
                    with self.assertRaisesRegex(distribution.DistributionError, "transactional install failed"):
                        distribution.install(
                            target,
                            prior_manifest=prior,
                            prior_version="prior-1",
                        )
            finally:
                distribution.remove_tree = original_remove
            after = {
                bundle: distribution.bundle_snapshot(target, bundle)
                for bundle in distribution.BUNDLES
            }
            self.assertEqual(after, before)

    def test_exact_controlled_upgrade_replaces_both_bundles(self) -> None:
        distribution = load_distribution()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "skills"
            copy_canonical(distribution, target)
            for bundle in distribution.BUNDLES:
                entry = target / bundle / distribution.ENTRY_SKILLS[bundle]
                entry.write_text(entry.read_text() + "\nprior release marker\n")
            previous = distribution.build_manifest()
            previous["distribution_version"] = "prior-1"
            previous["files"] = [
                {
                    "path": path,
                    "sha256": digest,
                    "size": size,
                }
                for bundle in distribution.BUNDLES
                for path, (digest, size) in distribution.bundle_snapshot(target, bundle).items()
            ]
            prior = root / "prior.json"
            prior.write_bytes(distribution.manifest_bytes(previous))
            with generated_manifest(distribution, root):
                distribution.install(target, prior_manifest=prior, prior_version="prior-1")
                distribution.check_install(target)

    def test_clean_project_bootstrap_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "self-host"
            project.mkdir()
            initialized = subprocess.run(
                [
                    sys.executable,
                    str(CONTROLLER),
                    "init",
                    "--project",
                    str(project),
                    "--name",
                    "Company OS Self Host",
                    "--project-type",
                    "software",
                    "--north-star",
                    "Company OS produces independently verified outcomes",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            self.assertTrue((project / ".company-os" / "control.json").exists())
            audit = subprocess.run(
                [sys.executable, str(CONTROLLER), "audit", "--project", str(project)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(audit.returncode, 1)
            report = json.loads(audit.stdout)
            self.assertFalse(report["ok"])
            self.assertFalse(report["scheduler_ready"])
            self.assertIn("strategy.current_outcome is required before execution", report["errors"])


if __name__ == "__main__":
    unittest.main()
