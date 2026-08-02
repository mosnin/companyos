# Codex-native task fabric simulation report

Status: `SAFE_CORRECTION_ACCEPTABLE / BROADER_RUNTIME_NO_GO`.

## Native task evidence

Exactly two projectless Luna tasks were created from this Sol manager task.

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
| Three-step malformed dependency | Bad upstream digest; both downstream start orders must remain null | blocked; neither downstream task starts |
| One manager plus two Luna workers | Disjoint scopes, exact IDs, real durations, manager integration review | rework; Worker A accepted and Worker B failure preserved |
| Fault and pressure injection | Stale report, scope drift, fail/refuse, task and concurrency caps | blocked with every injected defect named |
| Similar project isolation | `project-native-01-copy` artifact inserted into `project-native-01` | rejected for task and artifact isolation |

## Defect-to-iteration map

| Iteration | Observed defect | Correction | Rerun result |
| --- | --- | --- | --- |
| 0 | Runtime direction required an external provider gateway and credentials | Replaced current direction with native task coordination; froze provider code as historical fixtures | contract and roadmap point to Codex-native tasks |
| 1 | Worker B mutated ignored files during a read-only check and claimed tracked cleanliness; final audit found 16 generated `.pyc` files | Rejected receipt; removed only the authorized caches; added bytecode-disabled/disposable-copy rule and ignored-artifact inspection | acceptance rerun began at 0 and ended at 0 cache artifacts; side-effect rule is validated in both role skills |
| 2 | First manager skill routed Luna packets to the manager charter asset | Routed Luna tasks to `$execute-bounded-task` and its work-packet asset | deterministic role validator passes |
| 2 | First manager phase rule risked approval deadlock | Added exception-based auto-continuation with report visibility and master override | deterministic role validator rejects the old wording |
| 3 | Dependency, stale report, scope, budget, and project isolation were narrative only | Added executable five-scenario schema validator | all five after-state oracles match |

## Brutal manager scorecard

These scores cover only the locally verified correction, not autonomous runtime
operation or installed skill behavior.

| Dimension | Score | Evidence and residual defect |
| --- | ---: | --- |
| Authority integrity | 9.3 | Exact roles, charter narrowing, no worker delegation, master-only final acceptance; controller admission is still not wired to native create |
| Cancellation integrity | 9.2 | Contract refuses to invent hard cancellation and treats stop as cooperative; operational hard interrupt remains unavailable and blocks broader runtime |
| Evidence integrity | 9.4 | Actual task IDs/durations, requested/observed split, failed receipt preservation, content digests, objective oracles |
| Project isolation | 9.2 | Exact binding and foreign-artifact simulation pass; multi-project live tasks are not yet forward-tested |
| Dependency safety | 9.3 | Malformed upstream artifact blocks both downstream starts deterministically |
| Failure and rework | 9.3 | Real Worker B failure is rejected and never upgraded; synthetic fail/refuse paths block |
| Budget and concurrency | 8.8 | Deterministic pressure gate passes; native host does not expose enforceable token/cost budgets |
| Role/prompt architecture | 9.1 | Concise versioned global skills and compact assets; installed fresh-thread discovery remains unproven |
| Observability truth | 9.3 | Elapsed is independent; model/tokens/cost/cancellation stay unavailable |
| Regression strength | 9.0 | 32 repository tests; 7 focused native-fabric tests; 126 controller; 37 store; 8 observation; 10 gateway; 14 lifecycle; 9 receipt; 29 Responses fixture; 10 reference tests; validators and AST parse pass |

Every applicable local-correction score exceeds 8; authority, cancellation
integrity, and evidence integrity exceed 9. Operational hard cancellation is
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
