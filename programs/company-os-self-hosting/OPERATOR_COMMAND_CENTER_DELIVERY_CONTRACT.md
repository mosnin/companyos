# Operator Command Center — Delivery Contract

## Purpose

Package the independently accepted Operator Command Center as Company OS
`0.4.0`, prove the committed package is exact, and transactionally upgrade the
canonical local Codex skills installation only after disposable and detached-
commit parity are proven.

The Experience candidate is accepted at a 9.22 mean with all 13 critical
dimensions at or above 9. Delivery may not change that product contract without
returning to Experience and repeating independent review.

## Required outputs

1. `VERSION`, `README.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`,
   `docs/SCORECARD.md`, and the current self-hosting ledger/report name `0.4.0`
   consistently. Historical 0.3.1 reports remain historical and are not
   rewritten as 0.4.0 work.
2. The manifest binds the exact installed contents of the `company-os` and
   `autonomy-suite` skill bundles; its `distribution_version` binds `VERSION`.
   Repository-only documents and screenshots are not falsely called shipped
   bundle files.
3. Distribution tooling proves prior-install provenance, stages both bundles
   before mutation, replaces both as one transaction, and restores both prior
   bundles on any failure. A controlled upgrade may not use `--force` without
   an exact expected-prior-manifest match.
4. Every shipped manifest path is tracked in the staged Git index, the staged
   diff contains no integrity error, and the candidate contains no unexpected
   untracked or unstaged release file.
5. All controller, store, observation, reference, operator, fabric,
   distribution, compilation, manifest, and diff-integrity gates pass.
6. Empty-root installation and a clean detached checkout of the accepted commit
   each exactly match the manifest.
7. `/Users/preston/.codex/skills` is upgraded only from the detached accepted
   commit, after its existing bundles exactly match the expected 0.3.1 manifest.
8. The in-repository implementation report records a non-self-referential
   distribution-input digest: `VERSION` plus every manifest-input file under
   `skills/company-os` and `skills/autonomy-suite`, with canonical relative
   paths and file bytes. Repository-only reports are explicitly outside that
   digest. A post-commit Company OS evidence record, not the in-repository
   report, records the complete staged-tree digest and actual commit.

## Safety limits

- Chippy remains frozen and outside this repository.
- No provider runtime, recurring scheduler, production system, customer data,
  remote deployment, or external message is touched.
- The session-local issuer remains outside the repository and is never shipped.
- A modified or extra file in the existing canonical bundles fails the prior-
  release provenance check and stops the upgrade; it is never silently erased.
- Any nonzero test, manifest, tracked-inventory, cached-diff, commit, detached-
  checkout, install, parity, audit, or rollback result stops the release.
- A release finding invalidates the freeze. Correct it, establish a new frozen
  candidate, regenerate its manifest once, and repeat every downstream gate.

## Frozen candidate and manifest rule

Complete all source, version, current-document, test, and implementation-report
edits first. Stage one explicit allowlisted release inventory. That staged index
is the frozen candidate. From that point:

1. Regenerate the manifest exactly once for that freeze attempt.
2. Stage the manifest.
3. Prohibit any shipped-file or `VERSION` edit.
4. Require `verify-manifest` immediately before disposable install, commit, and
   canonical install.
5. Require every manifest file to be present in the staged index.

Any needed edit restarts this section; “once” never means preserving a stale
manifest after a legitimate repair.

## Authoritative regression matrix

The frozen candidate must pass:

```text
python3 skills/company-os/elastic-company-os/scripts/test_company_os_controller.py -q
  expected: 114 / 114
python3 skills/company-os/elastic-company-os/scripts/test_control_store.py -q
  expected: 21 / 21
python3 skills/company-os/elastic-company-os/scripts/test_runtime_observation_integration.py RuntimeObservationIntegrationTests -q
  expected: 8 / 8
python3 -m unittest test_operator_brief
  cwd: skills/company-os/elastic-company-os/scripts
  expected: 30 / 30
python3 -m unittest discover -s programs/company-os-self-hosting/reference -q
  expected: 10 / 10
python3 skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_fabric.py --self-test
  expected: pass
python3 -m unittest tests.test_distribution -q
  expected: discovered current suite total, recorded as exact N / N in the
            release report (pre-Delivery baseline: 4 / 4; installer coverage
            added in Delivery increases this inventory)
python3 -m compileall -q skills scripts tests programs/company-os-self-hosting/reference
python3 scripts/distribution.py verify-manifest
git diff --check --cached
```

The release report must record actual inventories rather than copying these
expected counts if the suite legitimately grows during Delivery.

## Transactional delivery sequence

1. Read-only preflight: compare the current canonical installed bundles against
   the committed 0.3.1 manifest, including absence of extra included files.
   Stop on any difference.
2. Implement and test prior-manifest validation plus two-bundle atomic staging,
   replacement, rollback, and exact post-install verification.
3. Finish all 0.4.0 source, named current-document, test, and candidate-report
   changes; preserve historical reports.
4. Stage the explicit release inventory and reject unexpected untracked or
   unstaged release files.
5. Freeze the candidate, regenerate and stage the manifest once, then prove
   every manifest path is tracked in the index.
6. Run the complete authoritative regression matrix and verify the manifest
   again. Any correction restarts at step 3.
7. Install into an empty disposable skills root; prove idempotence and exact
   manifest parity.
8. Independently review the staged release diff, the report's precisely scoped
   distribution-input digest, provenance boundary, rollback tests, and
   non-claims. The complete staged-tree digest is computed after the index is
   frozen and retained in post-commit Company OS evidence, where it cannot be
   self-referential. Any finding restarts at step 3.
9. Verify the manifest and staged diff again, then commit the release. Stop if
   the commit fails or the resulting checkout is unexpectedly dirty.
10. Create a clean detached checkout/archive of that commit. From that clean
    source, verify the manifest, run the distribution suite, install into a new
    empty root, and prove exact parity.
11. Record a post-commit Company OS delivery evidence event containing the
    complete frozen staged-tree digest, actual commit, and detached verification
    result. Do not edit the committed report to insert its own tree or commit.
12. Re-prove canonical installed bundles match the expected 0.3.1 manifest.
    From the detached accepted commit, transactionally upgrade both bundles,
    run exact parity, and retain rollback evidence until success is confirmed.
    If either bundle, post-install check, or cleanup fails, restore both 0.3.1
    bundles and stop; a rollback failure is a release incident.

## Done condition

The repository has one clean, committed `0.4.0` release; every required gate is
green; every manifest file is tracked in the accepted commit; disposable,
detached-commit, and canonical installed copies exactly match the manifest; the
Company OS control record retains post-commit delivery evidence; the installer
can prove and atomically roll forward or restore both bundles; and no frozen
boundary was crossed.
