# Company OS 0.5.1 cancellation-evidence repair — verification report v1

## Verification receipt

- Contract: `company-os.manager-role.v2`
- Disposition: `implementation_complete_at_authenticated_verification_barrier`
- Program / version: `company-os-self-hosting` / `6`
- Charter / definition: `3` / `3`
- Cycle / manager: `release-0.5.1-cancellation-repair-cycle-1` / `manager-release-0.5.1-cancellation-repair-1`
- Master task: `019fa4e9-cd80-7bd2-9416-c8dce5a7e8c3`
- Outcome digest: `9265f3a74d6c5821dd85f90f37d65a23fac2a5a44f3aafb45c419692b86cee2b`
- Rejected release candidate: `722f5e5bf706d1dd1a48dfbcfacddfff269b7eb1` / tree `dd164733eb9b970792960566080048e8b567dd01`
- Rejected independent review task: `019fc2f8-0465-7db2-9323-762f0537e42c`
- Accepted v3 charter commit: `9df2bad9afa1205fa2741bfb76a334f5dfab722e`
- Master-owned control-plane compatibility patch: `ba328d7b2955a18072779ccab29b15ade64c0caf`
- Accepted runtime result: `0a4b492b271864cf5f5290a055507ae15cc9d53d`
- Accepted integration-test result: `7dd82bb30f5fc384d7219f96ebc5efbcf9317f20`
- Manifest-exact implementation candidate: `1e489780e6587a38c36e6e4bb38042dd8ed03835` / tree `45b6b2b45807219adee845784252320e0db699fe`
- Branch: `codex/native-runtime-control`
- Status: **stopped at VERIFICATION; independent review and master integration decisions remain pending**

This is a feature-off source candidate. It does not claim repository-level
interception of arbitrary Codex host task creation. The native worker tasks are
manual coordination evidence, not controller-governed runtime proof. No
installation, runtime or scheduler activation, provider call, deployment,
production mutation, signing action, credential access, or Chippy action was
performed.

## Authority and worker disposition

The v3 mission is
`programs/company-os-self-hosting/release-0.5.1-cancellation-repair/mission-charter.v3.json`,
byte SHA-256
`c383644e44d2bd0a4914acd06ff6f0e7a250cbbc85ddc306ffa75fea02f6c06b`.
Its definition digest is
`cab01209e8dbb865a15264146ad36b260f9929f7ac50e716a1c549b86abd134c`.
The canonical authorization digest is
`12cc77bf6ff740180f97f2c109b32c55d5f800c41dca4a94f7006244fa3f0feb`
and its offline fixture signature is
`25332af1a6b6fe11503aa2ede56b295616636f2de274c4a61ec2164b7689a8dd`.
The signature is repository-fixture integrity only, not live identity proof.

The authenticated v3 design used two disjoint native tasks and no child
delegation:

| Worker | Native task observation | Requested model | Observed model | Accepted result | Disposition |
|---|---|---|---|---|---|
| Runtime | task `019fc336-f196-7fd0-9127-c719c9cca36f`, host `local`; final retry turn duration `94868 ms` | `gpt-5.6-luna` | unavailable | `0a4b492b271864cf5f5290a055507ae15cc9d53d` / tree `496e7d8aff9eeb6be6c334e8fb608d641cecbab0` | Accepted after manager diff inspection and replay-matrix reproduction |
| Integration | task `019fc34e-a991-7bc1-879b-282f78b80501`, host `local`; duration `550781 ms` | `gpt-5.6-luna` | unavailable | `7dd82bb30f5fc384d7219f96ebc5efbcf9317f20` / tree `ea26d9ee65272e8a777f8e1ac8db7836827feeb9` | Accepted after manager diff inspection and stronger 201-case combined regression |

Provider token counts, provider cost, and host cancellation acknowledgement were
not exposed and are therefore recorded as unavailable. Requested model values
were not promoted to observed model evidence.

The runtime history was handled without bypass:

1. `22c34d0a4dd87d14ed10122a1021d52858f0adc7` was rejected after manager
   reproduction found terminalization could not retain truthful hard
   acknowledgement evidence.
2. `7ee55e7e967ae471cff9fd297f9661371e0a6b99` corrected terminalization but
   remained unaccepted because two contradictory retained/replay rows were
   missing.
3. Charter v3 authorized the final retry. `0a4b492b271864cf5f5290a055507ae15cc9d53d`
   added those two rows without changing the accepted runtime source bytes and
   passed manager reproduction.

The integration worker changed exactly the three authorized test files. Its
receipt reported `153/153` for the full owned suites, but independent manager
loading showed that `153` is the controller module's loaded count. The combined
three-module suite contains `201` cases. The manager ran that stronger combined
suite and accepted the result only after `201/201` passed.

## Implemented cancellation evidence contract

The accepted legal cross-product is exactly:

| `hard_status` | `acknowledgement_status` | Projection and evidence meaning |
|---|---|---|
| `acknowledged` | `acknowledged` | explicit hard acknowledgement; active projection may become `cancel_acknowledged`, and an ordered terminal cancellation may retain both fields while becoming `cancelled` |
| `refused` | `not_acknowledged` | distinct refusal evidence; remains a non-acknowledged cancellation outcome |
| `failed` | `not_acknowledged` | distinct hard-cancellation failure evidence; remains a non-acknowledged cancellation outcome |

The other three pairs are contradictory and reject before mutation:
`acknowledged/not_acknowledged`, `refused/acknowledged`, and
`failed/acknowledged`. Retained-event injection and state-only injection of
each contradictory pair also fail audit. Only the explicit
`acknowledged/acknowledged` row can derive `cancel_acknowledged`.

The repair preserves cooperative request and delivery as distinct evidence,
cancellation dominance over later success, hard-acknowledgement non-invention,
ordered lifecycle and authority-payload binding, persisted schema and downgrade
rejection, and ambiguous-restart no-relaunch.

## Transactional no-mutation evidence

- Direct runtime transition tests compare the complete state before and after
  every illegal pair and require the rejected transition to append nothing.
- Replay tests inject every illegal pair once as retained event evidence and
  once into state only; both surfaces must produce audit errors.
- Controller tests require rejection with byte-identical retained state and
  event storage, and no new authority history.
- SQLite store tests require an unchanged state projection, revision, event
  count, and authority state.
- Host-observation integration tests require an unchanged state projection and
  byte-identical persistence for each rejected pair.
- All legal rows are exercised at runtime, store, controller, and integration
  layers and remain semantically distinct.

## Independent manager verification

All accepted test runs used `PYTHONDONTWRITEBYTECODE=1`. Counts below overlap;
they are reported per oracle and are not summed into an inflated total.

| Check | Result | Boundary |
|---|---:|---|
| Exact runtime direct/replay/terminal matrix | 3 / 3 passed | Six direct rows, all three illegal retained-event and state-only injections, legal terminal cancellation |
| Complete runtime module | 19 / 19 passed | Runtime transition, replay, audit, downgrade, cancellation dominance, ambiguous restart |
| Controller/store/host-integration focused matrix | 3 / 3 passed | All six rows at each integration layer and atomic illegal rejection |
| Combined three owned integration modules | 201 / 201 passed | Stronger independent replacement for the worker's imprecise 153 count |
| Complete packaged script discovery | 312 / 312 passed | All Company OS packaged script tests, including the repaired runtime and integration paths |
| Reference contract discovery | 10 / 10 passed | Observation-gateway reference contract |
| Non-signature root suite | 52 / 52 passed | Native fabric, distribution, and role-contract tests; signed-surface tests intentionally excluded |
| Standalone native-fabric validator suite | 17 / 17 passed | Requested-versus-observed identity and native-lifecycle fabric invariants |
| Canonical role validator | valid, zero errors | Exact repository role package and canonical fixture authorizations |
| Distribution manifest | verified | One post-implementation refresh; no second write |
| Diff integrity | passed | Worker diffs and final manager diff pass `git diff --check` |

Two initial test commands used package paths incompatible with sibling imports
and failed during module loading before the affected assertions ran. Both were
rerun from their canonical scripts directories and passed. These harness
failures are not counted as product failures or accepted evidence. No accepted
suite reported a failure or skip.

## Exact frozen artifact digests

- `native_task_runtime.py`: `c5b1cd8bd059462b98fd0901f895b45c84eaa88047cae527795f3cfc0dd70f80`
- `test_native_task_runtime.py`: `f481d023263a56bcaef00a35eacf2a630e2d45c7b13e52115bce14e384fa7008`
- `test_company_os_controller.py`: `34b444d9131d02d7aa7840d3666805e2dfd061addd14642826b29c2ea2ea35b3`
- `test_control_store.py`: `32b49e5cb396028b7eadb51de89926fed93b6038c4b27b7c719d388353c17712`
- `test_runtime_observation_integration.py`: `329b4a9d44ead7b136ed7d5d0b991d3bbab242800f0987e6ca4e68b192f12fbc`
- `distribution-manifest.json`: `1f13a4f78de31a6e1f4c2b896a5d3d782778c5d35729055f572cae773988ea71`

The manifest refresh changed exactly these five entries: the runtime source and
the four repair test files above. `VERSION` was not changed.

## Stale signature and remaining gates

The existing 0.5.1 Operator Command Center attestation and detached signature
remain valid only for their old exact surface and are intentionally stale for
this candidate. They bind carrier
`17420a836ea11b0c42faef9c0f08eaba9ad53019`, tree
`82f34027d446ed9bf2ba40bbc1f1c342ae38dcf9`, runtime source commit
`315924018da7a7684787c79922dd3fd4887209c0`, canonical authority commit
`60211bd6962b733344c0c789272e96dc5db18a28`, and a 21-file aggregate
`f7ff37866190efc09fb13c7be7bd8c270467558d8e35ce7cb7aea628f21539e3`.
This repair changes two files in that signed 21-file set and changes the bound
runtime lineage. No old signature is promoted to this candidate, and no signing
test is counted in the non-signature verification result.

Remaining master or independent-review gates are:

1. master-owned `README.md` correction binding the exact prior 0.5.0 release;
2. master-owned `programs/company-os-self-hosting/LEDGER.md` correction that
   distinguishes canonical repository path from reviewed worktree path;
3. independent Sol review of the exact manifest candidate and this evidence
   carrier, with zero P0/P1 and the charter score thresholds;
4. a fresh externally signed 0.5.1 surface bound to the accepted final carrier;
5. separate master decisions for source integration, installation, and runtime
   or scheduler permission.

Manager source-slice assessment, pending independent review:

| Dimension | Score |
|---|---:|
| Cancellation semantics | 9.6 |
| Evidence integrity | 9.5 |
| Authority preservation | 9.4 |
| Durability / restart safety | 9.4 |
| Security / fail-closed behavior | 9.4 |
| Replay and reconciliation | 9.4 |
| Test completeness | 9.5 |
| Maintainability | 8.9 |
| Operability | 8.8 |
| Source-slice documentation | 8.7 |

No P0 or P1 is known to this manager after the complete oracle. These scores
are a manager assessment, not independent acceptance. Overall release readiness
remains gated by the master-owned documentation corrections, fresh signature,
and independent review.

The manager receipt is therefore **IMPLEMENTATION COMPLETE / VERIFICATION
DECISION REQUIRED / INTEGRATION NO-GO / RUNTIME NO-GO**.
