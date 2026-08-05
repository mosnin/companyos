# Codex-native task fabric simulation report

Status: `V2_FINAL_ENFORCEMENT_REWORK_LOCALLY_VALIDATED / BROADER_RUNTIME_NO_GO`.

Independent review of commit `16592d4c95671638c6d538e0d2932488020ace91`
was NO-GO: overall 5.8, with 0 P0, 4 P1, and 3 P2 findings. The v2
rework below closes those seven source-contract findings; it does not upgrade
the full runtime.

Independent exact-commit review of `d6f6a03dc848e45b3624859d72f1efc6142af03b`
then closed those seven findings but returned NO-GO at 6.8/10 with three P1
and two P2 enforcement gaps. The final bounded rework closes all five locally;
it does not claim installed behavior, live authentication, or runtime readiness.

## Native task evidence

Exactly two projectless tasks were requested as `gpt-5.6-luna` from this Sol
manager task. Observed model identity was unavailable for both.

| Worker | Native task/thread ID | Requested model | Observed model | Host observations | Duration | Disposition |
| --- | --- | --- | --- | --- | ---: | --- |
| A — provider-assumption inventory | `019fc173-86b9-7310-ac9e-1ea1e819c2ef` | `gpt-5.6-luna` | unavailable | `local`; later `slingshot:env_e_6a45bba84594832ebfa9502583df2b6b` | 184227 ms | accepted after manager source verification |
| B — native design/test analysis | `019fc173-7c60-76c0-8d8d-43455e70d3b2` | `gpt-5.6-luna` | unavailable | `local`; later `slingshot:env_e_6a45bba84594832ebfa9502583df2b6b` | 234219 ms | failed; execution receipt rejected |

Both tasks explicitly prohibited file creation/deletion and child delegation.
Worker B ran compilation in the shared checkout, generated ignored bytecode,
then attempted cleanup. The manager rejected its execution receipt and retained
only source findings independently inspectable in the repository. Three exact
remaining bytecode artifacts identified by the master were removed; subsequent
checks disable bytecode writes. Clean tracked Git status was not treated as
restoration proof.

The final hygiene audit then found 16 additional `.pyc` files, all timestamped
to Worker B's compilation window and confined to the three authorized test
trees. Only those generated caches were removed. The final acceptance rerun
started with 0 cache artifacts, ran with `PYTHONDONTWRITEBYTECODE=1`, and ended
with 0; its fail-closed post-test scan returned
`acceptance-rerun-passed pyc_before=0 pyc_after=0`.

The v2 rework reran the complete relevant lane with bytecode disabled. Its
repository-wide before/after receipt was
`full-v2-acceptance-passed pyc_before=0 pyc_after=0 cache_dirs_before=0 cache_dirs_after=0 shim=absent`.
The final enforcement rerun retained the same zero-artifact boundary and
recorded `final-enforcement-passed pyc_before=0 pyc_after=0
cache_dirs_before=0 cache_dirs_after=0 shim=absent`.

Task/thread ID is native identity. The more specific host value is current
coordination metadata; the earlier `local` value is retained as a raw normalized
observation. Neither host representation establishes lineage. The manager task
ID is `019fc171-8330-7303-9046-656c75cf2109`; the master task ID is
`019fa4e9-cd80-7bd2-9416-c8dce5a7e8c3`. At the simulation observation point,
the manager task was active. `rework` is the manager's simulation disposition
for Worker B, not a fabricated terminal lifecycle state.

Tokens and cost were not exposed. Cancellation acknowledgement and a hard
interrupt were not found. No value was inferred from the requested model.

## Simulation ladder

The concrete input and before-state defects are retained in
`CODEX_NATIVE_TASK_FABRIC_SIMULATION.json`. The executable validator returned:

| Scenario | Objective oracle | After result |
| --- | --- | --- |
| Known-answer synthetic project | Worker and manager JSON answer must equal 42 with valid digests | accepted |
| Three-step malformed dependency | Bad upstream digest; both downstream create/start orders must remain null | blocked; neither downstream task is created or starts |
| One manager plus two tasks requested as `gpt-5.6-luna` | Disjoint scopes, exact IDs, real durations, manager integration review; observed model unavailable | rework; Worker A accepted and Worker B failure preserved |
| Fault and pressure injection | Stale report, scope drift, fail/refuse, task/concurrency caps, and overlapping manager scopes | blocked with every injected defect named, including manager-manager ancestry overlap |
| Similar project isolation | `project-native-01-copy` artifact inserted into `project-native-01` | rejected for task and artifact isolation |

## Defect-to-iteration map

| Iteration | Observed defect | Correction | Rerun result |
| --- | --- | --- | --- |
| 0 | Runtime direction required an external provider gateway and credentials | Replaced current direction with native task coordination; froze provider code as historical fixtures | contract and roadmap point to Codex-native tasks |
| 1 | Worker B mutated ignored files during a read-only check and claimed tracked cleanliness; final audit found 16 generated `.pyc` files | Rejected receipt; removed only the authorized caches; added bytecode-disabled/disposable-copy rule and ignored-artifact inspection | acceptance rerun began at 0 and ended at 0 cache artifacts; side-effect rule is validated in both role skills |
| 2 | First manager skill routed Luna packets to the manager charter asset | Routed Luna tasks to `$execute-bounded-task` and its work-packet asset | deterministic role validator passes |
| 2 | First manager phase rule risked approval deadlock | Added exception-based auto-continuation with report visibility and master override | deterministic role validator rejects the old wording |
| 3 | Dependency, stale report, scope, budget, and project isolation were narrative only | Added executable five-scenario schema validator | all five after-state oracles match |
| 4 | Barrier policy alternated between wait-everywhere and auto-continue-everywhere | Authenticated charter/design/verification/integration barriers; visible routine execution-only continuation | every authoritative phase source is structurally checked |
| 5 | Compact assets omitted contract authority and budget data | Added strict v2 schemas with versions, digests, authorization, references, permissions, six budgets, review, and barriers | strict dispatched-payload tests pass; workers inherit design evidence and never await master |
| 6 | Fixture/request text could masquerade as observed model | Fixtures cannot claim observed model; native observations require an allowlisted host source class | requested/charter source attacks reject |
| 7 | Active was terminal and open intervals escaped concurrency | Added current/optional-terminal state and ordered create/start/terminal events | accepted-without-start and active-overlap pressure reject |
| 8 | Rerun mappings were unchecked | Require unique iteration IDs and nonempty unique existing scenario references | empty, duplicate, and foreign mappings reject |
| 9 | Scope equality missed path aliases and ancestors | Require lowercase ASCII relative POSIX paths and reject ancestor overlap | case, Unicode, ambiguous path, and descendant attacks reject |
| 10 | Agent metadata could invoke roles implicitly | Added structurally parsed `allow_implicit_invocation: false` | missing, true, and malformed metadata reject without PyYAML |
| 11 | Authorization accepted arbitrary attributable-looking hashes | Added versioned project-local decision records with exact bindings, exact evidence bytes, canonical digest, and repository-fixture HMAC | arbitrary hash/signature and cross-program/phase/definition/outcome/decider/replay substitutions reject |
| 12 | Worker destination could target the master or another manager | Bound mission parent to the charter and separately bound the design-record native manager ID to canonical `task:<parent_manager_task_id>` | wrong-master and cross-manager packets reject; host identity does not become lineage; workers never contact or await master |
| 13 | Worker authority was validated independently of its parent | Load exact accepted parent charter; enforce scope containment, action/tool subsets, retained prohibitions, and six-field budget narrowing against available allocation and charter | cross-project, stale-parent, scope, permission, tool, budget, and replay attacks reject |
| 14 | `max_cost_usd` accepted non-finite values | Added fail-closed finite numeric validation for all six budget fields | NaN, infinities, booleans, strings, negatives, and invalid boundaries reject without exceptions |
| 15 | Artifact references trusted path strings rather than local bytes | Resolve versioned project-local allowed-root files and hash exact bytes | path-string hash, missing, mismatch, foreign project, mutable, absolute, backslash, dot/escape, and symlink attacks reject |

## Brutal manager scorecard

These scores cover only the locally verified correction, not autonomous runtime
operation or installed skill behavior.

| Dimension | Score | Evidence and residual defect |
| --- | ---: | --- |
| Phase authority integrity | 9.1 | Authenticated true barriers, bounded silence escalation, routine execution-only auto-continuation, and no worker-owned master wait are validated across every authoritative source |
| Authorization and authority integrity | 9.2 | Accepted local decision records bind exact program/definition/outcome/phase/decider/task/parent data and byte-verified evidence under a deterministic fixture signature; signed task, mission-parent, and whole-record substitutions reject; live identity remains unproven |
| Compact contract integrity | 9.1 | Strict v2 charter/packet keys carry versions, real local reference bytes, requested model, permissions, six budgets, parent allocation, review, barrier policy, and exact authorization records |
| Lifecycle/concurrency integrity | 9.0 | Current versus terminal state, native identity, ordered events, and open active intervals are adversarially tested |
| Cancellation integrity | 9.2 | Contract refuses to invent hard cancellation and treats stop as cooperative; operational hard interrupt remains unavailable and blocks broader runtime |
| Evidence integrity | 9.2 | Task IDs/durations, requested/observed split, allowlisted native model sources, failed receipt preservation, digests, and objective oracles |
| Parent/project/scope isolation | 9.2 | Foreign bindings, stale/cross-manager parents, child scope escape, permission/tool widening, case/Unicode/path ambiguity, and manager-manager or worker-worker ancestor overlap reject; malformed parent fields also fail closed under a bounded JSON-shape matrix; live multi-project tasks remain untested |
| Iteration mapping integrity | 8.8 | Rerun mappings must be nonempty, unique, and reference existing scenario IDs |
| Agent policy integrity | 9.0 | Both source roles disable implicit invocation through a bounded structural parser |
| Dependency safety | 9.3 | Malformed upstream artifact blocks both downstream starts deterministically |
| Failure and rework | 9.3 | Real Worker B failure is rejected and never upgraded; synthetic fail/refuse paths block |
| Artifact evidence integrity | 9.1 | Allowed-root, project namespace, version, regular-file, no-symlink, and exact-byte SHA-256 rules are adversarially tested without exposing file content |
| Budget truth | 9.0 | Every numeric field is finite/type/boundary checked and worker allocations narrow the parent; native token/cost observation and enforcement remain full-runtime blockers |
| Routing integrity | 9.2 | Worker lineage, parent charter/design evidence, manager task ID, and reporting destination must agree; master or cross-manager routing rejects |
| Regression strength | 9.1 | 59 root repository tests, including all 27 role-contract tests, plus 17 separate native-fabric, 126 controller, 37 store, 8 observation, 10 gateway, 14 lifecycle, 9 receipt, 29 Responses-fixture, 30 operator-brief, and 10 reference tests pass, plus strict role/fabric validators, manifest, syntax, diff, secret/scope, and zero-bytecode gates |

Every applicable local-correction score exceeds 8; authority, routing,
cancellation integrity, and evidence integrity exceed 9. Operational hard cancellation is
not being scored as implemented: it is absent, so the broader autonomous
runtime is explicitly NO-GO.

## Full-system runtime readiness — NO-GO

These scores measure actual Company OS runtime capability, not whether the
contract describes its absence truthfully. They intentionally fail the release
gate.

| Runtime capability | Score | Current reality |
| --- | ---: | --- |
| Hard cancellation | 2.0 | No proven native interrupt or cancellation acknowledgement; cooperative follow-up only |
| Controller admission before native create | 1.0 | Controller does not invoke or durably admit Codex task creation |
| Fresh installed role-skill behavior | 2.0 | Source validates locally; distribution is not installed or fresh-thread tested |
| Successful two-Luna integration | 3.0 | One worker accepted and one failed; this proves supervision/rejection only |
| Observed model identity | 2.0 | Requested model recorded; no observed-model field exposed |
| Token and cost telemetry | 1.0 | Unavailable for both native workers |
| Durable native lifecycle/reconciliation | 2.0 | Interactive task results are not persisted through controller state transitions |
| Protected recurring scheduling | 0.0 | Disabled and explicitly out of scope |

The full system fails every 8/9 threshold. No local-contract score may be used
to conceal these missing capabilities.

The standard skill `quick_validate.py` could not run with its real PyYAML
dependency in this environment. A compatibility-shim run is excluded from
acceptance. The repository's stricter deterministic role validator and root
tests are the accepted skill-structure, prompt-size, frontmatter, asset-schema,
and routing evidence.

## Next exact gate

Install the candidate role skills only through a separately accepted release,
then forward-test fresh native Sol-manager and Luna-worker tasks using only the
skill invocation plus compact charter/packet. Add controller admission-before-
create and a proven hard interrupt/cancellation acknowledgement before any
scheduler or autonomous-runtime GO.
