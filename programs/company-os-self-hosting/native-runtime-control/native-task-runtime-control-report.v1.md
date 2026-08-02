# Native task runtime control — verification rework report v1

## Manager receipt

- Contract: `company-os.manager-role.v2`
- Disposition: `rework_complete_at_verification_barrier`
- Program / definition: `company-os-self-hosting` v6 / definition v2
- Cycle / manager: `native-runtime-control-cycle-1` / `manager-native-runtime-control-1`
- Master task: `019fa4e9-cd80-7bd2-9416-c8dce5a7e8c3`
- Outcome digest: `73391b5cd8f8582f6108b0152986526a2c5360b89100d64359cd3a178675c1d8`
- Rejected predecessor: `6a038b4fb2ff0166d6508494da749b5fe7ef52fe`
- Independent REWORK review: task `019fc26b-1deb-7070-aa43-f2b893982fe8` (`0 P0`, `2 P1`, `3 P2`)
- Accepted runtime-source commit: `315924018da7a7684787c79922dd3fd4887209c0`
- Exact authority-repair commit under test: `60211bd6962b733344c0c789272e96dc5db18a28`
- Branch: `codex/native-runtime-control`
- Status: **stopped at verification; not independently accepted, integrated, installed, deployed, or enabled**

This slice governs compliant Company OS native launches only. It does not
intercept arbitrary Codex host task creation, and repository code does not call
or claim to call Codex app tools. The prior Luna tasks remain manual native
coordination evidence, not controller-governed runtime proof. No new workers
were dispatched in this rework cycle.

## Rework delivered

### Retained lifecycle replay and exact authority binding

`native_task_runtime.audit_state` now rebuilds lifecycle-controlled state from
the pre-create admission event and reduces every later retained event in order.
It compares the replayed status, dispatch, native identity, host observations,
cancellation state, sequence, events, terminal state, receipt, and restart
reconciliation with the persisted projection. Reordered, duplicated, deleted,
or state-only running/terminal histories therefore fail closed even when an
attacker resequences events and recomputes unkeyed event or receipt digests.

Cancellation dispatch creation, claim, and cooperative delivery are retained
as lifecycle transitions rather than direct state mutations. Pre-launch
cancellation retains its exact reconciliation action. Authority is attached
only after the corresponding event exists, and terminal receipt hashes are
recomputed after that attachment.

Every retained authority entry now contains the exact command details and
lifecycle sequence. The pure audit recomputes the controller command payload
hash from the admitted attempt lineage and verifies the exact retained event or
observation payload. The controller additionally requires one ordered authority
entry for every post-admission event and independently re-audits its signed
grant. Missing, duplicated, reordered, wrong-event, wrong-detail, or altered
payload-hash authority fails.

Adversarial regressions cover reordered create/running events, duplicate
running events, deleted running/terminal history with retained terminal state,
state-only running state, altered authority payload hashes, missing authority
coverage, cancellation dispatch replay, and pre-launch reconciliation.

### Persisted schema and downgrade boundary

New native state is explicitly `company-os.native-task-runtime.v2`. A tested
assessment API covers both active attempts and exact archived runtime-adapter
snapshots. Reading v2 with the v2 reader is safe. Downgrade to v1 or to the
schema-9 pre-native-runtime reader is explicitly `blocked` because lifecycle
replay and authority bindings cannot be represented losslessly. The required
action is to retain the v2 reader or use a later, separately authorized,
lossless migration. No downgrade transformation is claimed or performed.

### Canonical replacement charter authority

The independent re-review accepted the lifecycle/source logic but rejected the
custom scope-amendment record because its signature preimage was not the
standard authorization preimage and charter v1 never owned the integration
test. That custom decision and evidence were deleted, so no project-local
verifier can treat them as active.

The replacement authority is:

- mission charter: `programs/company-os-self-hosting/native-runtime-control/mission-charter.v7.json`, charter v2 / definition v2, byte SHA-256 `8f48f12777b6a8e0ec04894f15ee01b488fbe34af6844f8ef53b326003f7b267`
- definition digest: `62f5eaf0f428934b8be93e9f66ef85478477fe52bbeaa5989090e83319fe95c6`
- phase evidence: `artifacts/company-os-self-hosting/phase-evidence/manager-native-runtime-control-1.charter.v2.json`, byte SHA-256 `24a835d8b76c56366fdb52c8993ab1ea723980739259fe314f68cbb5f7aba64e`
- standard decision: `artifacts/company-os-self-hosting/authorizations/manager-native-runtime-control-1.charter-2.v1.json`, byte SHA-256 `11ed29eb85e18b26e9e4848ca7caa50fca516821a52fce1b97d4827714c6af7c`, canonical SHA-256 `f50866dcfdf6edaff44b18889f811cade604e4507032839f6575b1a3445e5410`
- canonical fixture signature: `4fc0b0a4d3867b4cff08825b78e1c8bac476d23a7a5dc6eb89e5991b39eceb24`

Charter v2 explicitly owns
`skills/company-os/elastic-company-os/scripts/test_runtime_observation_integration.py`.
Its definition and byte-bound phase evidence retain charter v1 byte digest
`b15d0cd4dbc64a08b6052d4fbffca85ebbf3ec0a3443ecb1d9745cbda2933f30`
and definition digest
`14036ed6823c8da9ebb3684aa3fc06f453290b8b9966ad928db7aee991530f9a`.
The authorization is a standard `company-os.authorization-decision.v1`; its
signature is recomputed by `scripts/validate_role_skills.py` over the canonical
preimage with authentication reduced to only `scheme` and `key_id`. This is
offline repository-fixture integrity, not live identity authentication.

## Exact verification evidence

All passing checks below were rerun against exact authority commit
`60211bd6962b733344c0c789272e96dc5db18a28` with bytecode writing disabled.

| Check | Exact result | Evidence boundary |
|---|---:|---|
| Canonical role validator | passed, zero errors | Role assets and canonical authorization implementation |
| Replacement-charter focused authority test | 1 / 1 passed | Exact charter, decision, evidence, scope and removed-custom-record checks |
| Complete packaged script discovery | 306 / 306 passed | Full relevant packaged regression, including controller and all negative paths |
| Reference contract discovery | 10 / 10 passed | Local reference contracts |
| Diff integrity | passed | `git diff --check` clean before source commit |
| Script bytecode residue | passed | no `.pyc`, `.pyo`, or `__pycache__` retained |
| Root discovery | **55 / 59 passed; 2 failures, 2 errors** | blocked only by prohibited manifest/signed-surface integration gates |
| Distribution manifest | **blocked** | `distribution manifest is stale; run write-manifest` |
| Provider/native live run | not run | prohibited; no provider/runtime proof claimed |

The root failures are disclosed, not waived:

1. `test_check_install_creates_no_lock_or_other_artifact_for_external_target`
   errors because the distribution manifest is stale.
2. `test_current_surface_and_independent_signature_verify` errors because
   `company_os_controller.py` differs from the independently signed Operator
   Command Center surface.
3. The two negative signature-drift tests fail early on that same source drift
   instead of reaching their intended signature-tamper assertions.

Updating `VERSION`, the distribution manifest, or the independently signed
Operator Command Center surface is expressly reserved for master integration
after independent source acceptance. This manager did not modify those files.

## Source artifact digests at the tested commit

- `company_os_controller.py`: `cc4f0ccb20942982d29eef39dc75f12f25b5224c08587d57d7870bbfb23ec7c4`
- `control_store.py`: `e4361ecb2eb07b5a7f6557e852065ca10a9fbacfff6386f157f68464a7179aac`
- `native_task_runtime.py`: `2c50b4541b491f4fd64b04704d4d4652bb44dd0b094f9d0096ca88a5c2d48956`
- `test_company_os_controller.py`: `120b6f34ee9f0bc6af675112f3f491cadf1bfd796c492acac68222a5accece31`
- `test_control_store.py`: `fff4cec7effd48d1d623e924f586221952a7ac2bc566dd408703d6b0a9de4e90`
- `test_native_task_runtime.py`: `1bfcd665b6c05846b0fe15eda34592723107845c7452c33fa7098b642fc5bab1`
- `test_runtime_observation_integration.py`: `c7ba5f91ae7df0ba0fc31f7ec00eb0c885e38b07981616160335d9943701f01e`

## Worker and policy disposition

- Existing worker task evidence: retained; no new worker task created.
- Direct manager repair: accepted as routine execution under the authenticated
  rework directive.
- Collision or policy event: none in the authoritative worktree.
- Telemetry: requested model `gpt-5.6-sol`; observed model, provider tokens,
  provider cost, and hard-cancellation acknowledgement are unavailable and were
  not invented.

## Unresolved gates and next action

The next action is an independent Sol authority/source review of commit
`60211bd6962b733344c0c789272e96dc5db18a28` and this report. Acceptance still
requires no P0/P1 findings and the charter score thresholds. Only after that
source acceptance may the master authorize integration-owned version,
manifest, signed-surface, installation/parity, or runtime work.

Until then the manager receipt is **REWORK COMPLETE / VERIFICATION PENDING /
RUNTIME NO-GO**. No integration, canonical-main merge, installation,
deployment, runtime or scheduler activation, provider/production action, or
Chippy action is authorized or performed.
