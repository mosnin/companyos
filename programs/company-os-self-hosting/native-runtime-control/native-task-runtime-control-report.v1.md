# Native task runtime control — verification report v1

## Barrier status

**VERIFICATION BARRIER REACHED — STOPPED, NOT ACCEPTED, NOT INTEGRATED.**

This report is bound to:

- program: `company-os-self-hosting`, program version `6`, definition version `1`
- cycle: `native-runtime-control-cycle-1`
- manager: `manager-native-runtime-control-1`
- authenticated master task: `019fa4e9-cd80-7bd2-9416-c8dce5a7e8c3`
- manager native task: `019fc22b-f9f4-76e0-b26c-b181c21e1ab4`
- accepted outcome digest: `73391b5cd8f8582f6108b0152986526a2c5360b89100d64359cd3a178675c1d8`
- source baseline: `19fe809a9544303fb00150c957b317ed03c7a1a3`
- accepted design evidence SHA-256: `48b464344a52df67f7d7086805522f32d94a04e3c34c08a8750416c3cb702ae3`
- exact charter bytes SHA-256: `b15d0cd4dbc64a08b6052d4fbffca85ebbf3ec0a3443ecb1d9745cbda2933f30`

The slice governs compliant Company OS native launches. It does not intercept
arbitrary Codex host task creation. Repository code does not call or claim to
call Codex app tools. The two implementation workers were manually coordinated
native tasks and are not controller-governed runtime proof.

## Delivered feature-off slice

The implementation adds a pure native-task state machine and controller
commands that require the transactional SQLite authority before admission or a
lifecycle mutation. Admission commits the exact attempt plus a content-bound
`admitted_pre_create` receipt and `native-task-create` outbox row atomically.
Only a separately authorized dispatch claim may move that row to `leased`,
after which a returned host observation may bind the immutable native
`task_id`, `thread_id`, and `host_id`.

Ordered host observations retain sequence numbers and payload digests.
Terminal success requires create and running observations. The terminal
receipt binds admission, dispatch, returned identity, all host observations,
cancellation state, terminal state, unavailable telemetry, and retained
authority history.

Cancellation persists desired intent independently from cooperative delivery,
hard-cancellation status, and acknowledgement status. Success or failure after
cancellation intent is rejected. A task cancelled before dispatch claim is
terminalized as `cancelled_before_launch` and its create outbox is cancelled.
An in-flight claim without returned identity reconciles to
`reconcile_host_listing`; it is never converted into a second create intent.

Requested model remains separate from observed model. Observed model, provider
usage/tokens, and cost remain structured `unavailable` values because the
native host did not expose them. No values are inferred from the request.

The retained-state audit fails closed on unknown native fields, altered
admission or dispatch receipts, reordered observations, identity conflicts,
forged authority history, invented telemetry, and invalid terminal receipts.
The controller rejects stale leases, duplicate task/thread binding,
cross-project grant replay, parent mismatch, idempotency conflict, and manifest
scope/model/budget widening.

## Durable store changes

The existing SQLite state/event/idempotency/outbox authority is reused. Outbox
reconciliation now supports explicit compare-and-set guards for expected
status and payload digest under the same staged state/event revision. Outbox
inspection verifies the project binding, stored JSON type, and content digest.
Idempotency recording is replay-safe for the exact retained payload.

No scheduler, provider, production, credential, deployment, installation,
canonical-main, or Chippy action occurred.

## Worker evidence disposition

Both compact v2 packets were validated before native creation and were scoped
to disjoint files:

- state packet: `programs/company-os-self-hosting/native-runtime-control/work-packets/native-runtime-state-worker-1.v1.json`, SHA-256 `ceb57dc8eb9fdb380cc7c76acb286617c0ef16e27e85e73a00951774cee9d457`
- store packet: `programs/company-os-self-hosting/native-runtime-control/work-packets/native-runtime-store-worker-1.v1.json`, SHA-256 `271d7a2c20d25a38da3453cf392202a570aa3f2830715e7aa6fdee33a1944467`

The store worker receipt is provisionally accepted based on manager inspection
and a clean 38-test store suite. The state worker's final `complete` label is
rejected because it disclosed one outdated failing test after its only allowed
rework. The manager independently repaired, strengthened, and reverified that
state-machine lane. Worker completion labels are not treated as acceptance.

## Verification evidence

| Check | Result | Evidence boundary |
|---|---:|---|
| Native state-machine suite | 11/11 passed | Pure local state transitions; no host/runtime proof |
| Transactional store suite | 38/38 passed | Local SQLite durability, crash rollback, outbox CAS and integrity |
| Controller suite | 150/150 passed | Local controller, archive, lease, authority and negative-path coverage |
| Complete packaged skill discovery | 299/299 passed | Full local packaged controller regression after master-owned integration-test correction |
| Diff integrity | passed | `git diff --check` clean |
| Python bytecode residue | passed | No `.pyc`, `.pyo`, or `__pycache__` remains under the script tree |
| Distribution manifest | blocked as expected | `verify-manifest` reports stale; root manifest is outside owned paths and integration is prohibited |
| Installed distribution parity | not run | Installation and integration were prohibited; source differs intentionally |
| Provider/native live run | not run | Provider calls and runtime enablement were prohibited |
| Independent Sol review | not performed | The two-task charter budget was fully allocated to the two required Luna workers |

The manager initially stopped at 298/299 because
`test_transactional_store_projects_one_inbox_message_and_retry_adds_no_revision`
asserted an absolute revision of `2`. The accepted design migrates the fixture
to SQLite before admission, so that number was unrelated to the functional
contract. At the master verification boundary, the test was corrected to
capture the pre-ingestion revision, assert exactly one increment for the first
durable observation, and assert no additional revision for exact replay. The
complete packaged discovery then passed 299/299.

The distribution manifest is also stale because the new module/test and the
changed packaged files have not been integrated into the root manifest. That
is an integration task and was intentionally not performed at this barrier.

Focused negative and fault evidence covers:

- stale, expired, wrong-owner, wrong-program and transition-disallowed leases
- malformed, expired, consumed, project-mismatched and payload-mismatched grants
- create outbox pending/leased/succeeded and pre-launch cancelled transitions
- compare-and-set mismatch rollback without a new store revision
- corrupted outbox payload JSON/digest and wrong-project inspection
- create claim crash/restart with no identity and no relaunch
- terminal observation before create/running
- missing or non-host task/thread/host identity
- duplicate task/thread binding across attempts
- conflicting attempt, idempotency, parent, scope, budget and model bindings
- cooperative cancellation without invented hard acknowledgement
- rejected post-cancellation success
- terminal receipt, observation chain, unknown-field, authority and telemetry tampering
- exact retry no-ops for admission, dispatch claim, observations and reconciliation

One incidental syntax check initially created
`scripts/__pycache__/native_task_runtime.cpython-314.pyc`; the exact file and
the empty directory were removed immediately. Final residue is zero.

## Source artifact digests

- `company_os_controller.py`: `437adbfc4128dca80696f63553b29eecd3c0e71af4daffdbd795e19df2ea757c`
- `control_store.py`: `e4361ecb2eb07b5a7f6557e852065ca10a9fbacfff6386f157f68464a7179aac`
- `native_task_runtime.py`: `e808682ff83db9d078f28e47fd2f12724c4df54059314a5c434b311db81eb6ca`
- `test_company_os_controller.py`: `545be88cb42e95e5f255ce09d2bec3d0ccb9a519165b37c21064c495cd97b45e`
- `test_control_store.py`: `fff4cec7effd48d1d623e924f586221952a7ac2bc566dd408703d6b0a9de4e90`
- `test_native_task_runtime.py`: `af5fa94823ae56c714f9c8cca5929847c7213ce9806d68695d8517af31883d75`
- `test_runtime_observation_integration.py`: `c7ba5f91ae7df0ba0fc31f7ec00eb0c885e38b07981616160335d9943701f01e`

These are working-tree digests, not commit evidence. No exact implementation
commit exists because integration and canonical-main writes were prohibited.

## Provisional manager scorecard

These scores are the implementing manager's assessment, not the required
independent Sol verdict:

| Dimension | Score / 10 | Basis |
|---|---:|---|
| Security | 9.2 | Feature-off, no I/O state machine, strict host-returned identity, no secret/provider path |
| Authority | 9.3 | Project/cycle/lease-fenced signed decisions retained and audited per transition |
| Durability | 9.2 | Atomic SQLite state/event/idempotency/outbox writes with CAS reconciliation |
| Cancellation | 9.1 | Intent, delivery, hard status, acknowledgement and terminal outcome remain distinct |
| Evidence integrity | 9.2 | Content-bound receipts, ordered digests, unavailable telemetry and tamper rejection |
| Reliability | 8.8 | Deterministic restart actions and exact no-op replay; no live host exercise |
| Maintainability | 8.5 | Pure state module and controller/store separation; controller integration remains substantial |
| Test strength | 9.0 | Strong negative/crash matrix and clean 299-test packaged discovery; live host behavior remains unproven |
| Observability | 8.7 | Durable ordered lifecycle and terminal receipt; host/provider fields remain unavailable |
| Rollback readiness | 8.4 | Feature-off source-only change; no install or runtime activation |

## Verification decision required

The implementation is ready for an authenticated master verification decision,
but it does **not** satisfy final acceptance yet. The master must arrange:

1. an independent Sol review with no P0/P1 findings and an independent scored verdict;
2. integration-owned distribution manifest and signed-surface updates with passing integrity checks;
3. full regression and installed-distribution parity after integration.

Until those conditions are met, the correct disposition is **verification
pending / runtime NO-GO**. No integration, merge, install, enablement,
scheduler, provider, production, or Chippy action is authorized by this report.
