# Company OS 0.4.0 — Operator Command Center Delivery Report

## Decision boundary

This report closes the editable pre-freeze implementation candidate for Company
OS 0.4.0. It records the independently accepted product, the repaired delivery
mechanism, and the complete disposable pre-freeze regression. It does not
record or predict the frozen Git tree, release commit, detached-commit result,
or canonical installation result. Those facts are recorded only as post-commit
Company OS evidence, where they cannot make this report self-referential.

## Product delivered

- One read-only Operator Command Center renders authoritative SQLite state as
  Markdown, JSON, or self-contained responsive HTML.
- It leads with the exact governed change, why it matters, and one action with
  owner, output, done condition, verification, outcome, and success measure.
- It progressively discloses stage, quality exceptions, work, manager/runtime
  accountability, evidence, cost, schedule, authority, blockers, and explicit
  non-claims.
- It escapes project text, omits grants/nonces/private authority/raw provider
  material, separates requested from observed model identity, and never turns
  missing telemetry or invalid proof into a success claim.
- The independent Experience audit accepted repair cycle 4 at **9.22 / 10**;
  all 13 critical product dimensions scored at least 9.0 and no P0/P1 remained.

## Delivery mechanism

- `VERSION` is 0.4.0 and current repository documentation describes the
  capability and its still-frozen runtime boundaries.
- The distribution manifest covers exactly the `company-os` and
  `autonomy-suite` bundles.
- Existing installations cannot be overwritten by `--force`. A non-canonical
  target requires an exact expected prior manifest and version.
- Both bundles are copied, hashed, and durably staged before target mutation.
- One validated committed manifest is captured before staging; source bytes are
  rechecked against that manifest before, during, and after staging and before
  each replacement. Staged and final targets are verified against the captured
  manifest rather than a newly read mutable source snapshot.
- A non-creating parent-directory POSIX lock and fsynced transaction journal
  bind the exact prior path/hash/size snapshots before the first rename.
- Every forward rename persists both affected directory entries. A later
  `install` invocation restores an interrupted transaction before doing
  anything else.
- Restoration is verified against the journal-bound prior snapshots. A failed
  rollback retains its journal and last recovery copy and reports the incident
  path; it is never silently cleaned up.
- `check-install` is strictly inspect-only and fails on interrupted state;
  `recover-install` is the explicit recovery/cleanup boundary. Only `install`
  can create a missing target parent.
- Adversarial coverage includes blind force, wrong or modified provenance,
  extra prior files, stage-before-mutation, first and second bundle failures,
  cleanup failure, lock contention, tampered/missing recovery, and crashes
  before and after each of the four replacement renames.

## Independently signed accepted surface

- The accepted product boundary is an exact, globally sorted 21-file surface
  recorded in `OPERATOR_COMMAND_CENTER_ACCEPTED_SURFACE.json` with aggregate
  SHA-256
  `a68e46af0933072afb8b59965a04c326b2fa38b72be7095299b3bb9571f3b36c`.
- An independent reviewer recomputed that surface, accepted the exact product
  checkpoint and 9.22 score, and signed the immutable attestation with a
  one-time RSA-2048 key. The private key was destroyed after verification; only
  the public key and detached signature are retained.
- The verifier has no repository-local reviewer default. The independently
  governed Company OS delegation supplies the expected reviewer identity and
  DER-key fingerprint; both must match the signed attestation and retained key.
  CI receives those non-secret anchors as externally administered repository
  variables and fails closed when either is absent or changed.
- `scripts/verify_operator_command_center_surface.py` fails closed on changed
  product bytes, manifest or attestation drift, an invalid signature, a changed
  reviewer key, or altered acceptance claims. CI runs that verifier directly.
- This signature accepts only the product surface. It does not accept the
  installer, distribution manifest, release commit, installation, provider
  runtime, scheduler, or any later repository change.

## Non-self-referential distribution-input digest

- Digest: `11b40f6c7759266b8525d19492880d10f56e550236b688e1717576d0269145cc`
- Algorithm: SHA-256 over an ordered binary stream. The first entry is
  `VERSION`; the remaining 64 entries follow the exact deterministic
  `build_manifest()` order: bundle order `company-os`, `autonomy-suite`, then
  each bundle's `included_files()` lexicographic path order. The distribution
  input path for each manifest item is its repository-relative
  `skills/<manifest path>` (for example,
  `skills/company-os/company-os/SKILL.md`). Each entry is encoded as unsigned
  64-bit big-endian path-byte length, UTF-8 repository-relative path, unsigned
  64-bit big-endian content length, then exact file bytes.
- Scope exclusion: the manifest, this report, repository documents, generated
  HTML, concept art, and screenshots are not distribution inputs and are not
  included in this digest.

## Disposable pre-freeze verification

A disposable copy of the completed source candidate generated a fresh 0.4.0
manifest and passed the following exact matrix before the repository freeze:

| Gate | Result |
| --- | --- |
| Canonical controller | 114 / 114 passed |
| Transactional store | 21 / 21 passed |
| Runtime observation integration | 8 / 8 passed |
| Operator Command Center | 30 / 30 passed |
| Frozen observation reference | 10 / 10 passed |
| Distribution and installer | 20 / 20 passed, including 8 crash subcases and deterministic manifest/source mutation races |
| Signed accepted surface | 6 / 6 adversarial tests and detached signature verification passed with an external governed reviewer identity/key anchor |
| Luna Execution Fabric | Self-test passed |
| Python compilation | Passed |
| Fresh disposable manifest | Verified |
| Repository diff integrity | Passed |

Commands:

```text
python3 skills/company-os/elastic-company-os/scripts/test_company_os_controller.py -q
python3 skills/company-os/elastic-company-os/scripts/test_control_store.py -q
python3 skills/company-os/elastic-company-os/scripts/test_runtime_observation_integration.py RuntimeObservationIntegrationTests -q
python3 -m unittest test_operator_brief -q
  cwd: skills/company-os/elastic-company-os/scripts
python3 -m unittest discover -s programs/company-os-self-hosting/reference -q
python3 skills/autonomy-suite/orchestration/luna-execution-fabric/scripts/validate_fabric.py --self-test
python3 -m unittest tests.test_distribution -q
python3 -m unittest tests.test_operator_command_center_surface -q
python3 scripts/verify_operator_command_center_surface.py \
  --expected-reviewer-id "$COMPANY_OS_OCC_REVIEWER_ID" \
  --expected-reviewer-public-key-der-sha256 \
  "$COMPANY_OS_OCC_REVIEWER_PUBLIC_KEY_DER_SHA256"
python3 -m compileall -q skills scripts tests programs/company-os-self-hosting/reference
python3 scripts/distribution.py verify-manifest
git diff --check --cached
```

## Independent review

- The Experience reviewer rejected four product iterations before accepting
  the 9.22 candidate.
- The Delivery-contract reviewer rejected the first contract until freeze,
  digest, provenance, rollback, and historical-report semantics were exact.
- The installer reviewer rejected the first implementation for a first-rename
  data-loss window, missing restart recovery, unsafe cleanup after rollback
  failure, and a stale-manifest test contradiction.
- The repaired installer received an independent static **GO** with no remaining
  P0, P1, or P2 on crash and rollback semantics. A subsequent frozen-release
  review correctly rejected the candidate because `check-install` could still
  recover interrupted work while its documentation promised inspection only.
  The current candidate splits inspect-only `check-install` from explicit
  `recover-install` and proves the boundary with byte-exact tests. A later
  frozen review rejected mutable source snapshots after manifest validation;
  the current candidate carries one validated manifest through staging and
  final verification and proves before/during-staging mutation rejection. Final
  frozen review remains pending and is recorded outside this report.

## Prior-install provenance

A read-only preflight compared the existing canonical local skill bundles to a
clean archive of accepted commit `305de1f` and its 0.3.1 manifest. Both bundles
matched all 62 prior shipped files exactly with no additional included file.
This fact must be reproved immediately before the canonical upgrade; an observed
difference stops delivery.

## Explicit non-claims

- No release commit, detached-commit verification, or canonical 0.4.0 install
  is claimed by this pre-freeze report.
- No provider model was launched and no Sol/Luna runtime result is claimed.
- Recurring scheduling remains disabled.
- No production system, customer data, remote deployment, or external message
  was touched.
- Chippy remains frozen and outside this repository.
