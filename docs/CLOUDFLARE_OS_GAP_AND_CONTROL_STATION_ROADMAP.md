# Cloudflare OS → Company OS: Deep Gap Analysis and Architecture Decision

**Program contract:** `company-os.cloudflare-os-gap-research.v1`
**Contract version:** `1.0.0`
**Evidence cutoff:** 2026-08-05
**Cloudflare OS source pin:** `e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682`
**Source tree:** `6768f0f1d1cda9469d83820467b881b729a9be12`
**License:** Apache-2.0
**Company OS comparison snapshot:** `f7cf7001ce505cd8f1947530ceb3f59bb2b9d664` plus disclosed uncommitted work; comparison only, not immutable release evidence.

## Executive decision

Cloudflare OS is not a replacement for Company OS and should not be forked wholesale. It solves a different layer exceptionally well: an AI-native personal productivity workspace with sandboxed user-created applications, capability-scoped external resources, human approval, and a polished web shell. Company OS is stronger at company hierarchy, portfolio/program decomposition, manager/worker control, accepted deliverables, business scorecards, and evidence-bound execution.

**INFERENCE — architectural decision:** The right move is a **fusion with a hard authority boundary**:

1. Keep **one Company OS controller** as the only source of task, budget, capability, lifecycle, and acceptance authority.
2. Build a provider-neutral **Execution Adapter Gateway** so Codex, Claude, Kimi, Hermes, OpenAI Agents SDK, and future runtimes join as workers—not peer controllers.
3. Build **Company Gateways**, inspired by Cloudflare Gatekeepers, for resource-scoped tools, recorded observations, typed write proposals, approval, execution verification, and compensation.
4. Build a shared **Control Station** web product and a thin Tauri-class desktop shell. The desktop is an operator client, never the durability root.
5. Add a sandbox broker and artifact workspace so agents can safely create and manipulate code, documents, spreadsheets, media, and eventually Company Apps.

Cloudflare OS is early access, has no native desktop client, has no general agent-framework adapter protocol, and contains several semantics Company OS must explicitly reject: unaudited child spawning, trusting BYO MCP `readOnlyHint`, counterfactual write simulation presented as completion, fixed shared scheduler failure domains, and unsigned release promotion.

## Evidence classification

- **SOURCE:** direct code, tests, repository metadata, issue, or maintainer documentation at the pinned commit.
- **CLAIM:** upstream maintainer/product claim not independently proven at runtime.
- **USER:** target requirements supplied for Company OS.
- **INFERENCE:** architectural conclusion drawn from the cited evidence.

No production system, credentials, provider account, Company OS canonical file, deployment, installation, or external service was mutated during this program.

## Repository identity and maturity

| Item | Evidence | Finding |
|---|---|---|
| Official project | SOURCE | `cloudflare/cloudflare-os`, repository ID `1211925923` |
| Exact pin | SOURCE | commit `e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682`, tree `6768f0f1d1cda9469d83820467b881b729a9be12` |
| License | SOURCE | Apache License 2.0; preserve notices, mark modifications, and obtain legal review before copying code |
| Release maturity | SOURCE | zero tags, zero GitHub releases, zero GitHub security advisories at cutoff |
| Product maturity | SOURCE | README calls v2 a complete rewrite, heavy development, early access, with rough edges ([README 44–48](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/README.md#L44-L48)) |
| Self-hosting maturity | SOURCE | local Wrangler/workerd path is explicitly non-production; production workerd documentation is “COMING SOON” ([README 184–200](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/README.md#L184-L200)) |
| Desktop | SOURCE | no Electron, Tauri, native wrapper, desktop updater, or signed desktop distribution surface found in the pinned tree |

## What Cloudflare OS actually is

Cloudflare OS is a React web workspace backed by Cloudflare Workers. Its own mapping is:

| OS metaphor | Cloudflare implementation |
|---|---|
| Kernel | `packages/workshop-backend` |
| Drivers | `packages/gatekeeper-*` |
| Shell | `packages/workshop-frontend` |
| Processes | Gadgets |
| Executables | Blueprints |
| Security | capability-scoped Gatekeepers and sharing permissions |

This mapping and the special treatment of AI agents are explicit in [README 93–118](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/README.md#L93-L118). Every workspace is a Durable Object; Gadget servers execute in Dynamic Worker Facets; Gadget clients execute in sandboxed iframes; explicit bindings are the route to external authority ([README 114–120](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/README.md#L114-L120), [README 158–170](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/README.md#L158-L170)).

It is a **personal AI application/workspace OS**. Company OS is intended to be a **multi-company management and execution OS**. The former is a powerful execution and interaction plane; the latter must remain the governing plane.

## Mechanism → capability → control → business outcome

| Cloudflare mechanism | Capability created | Subprocess / runtime | Control mechanism | Metric Company OS should capture | Business outcome |
|---|---|---|---|---|---|
| Per-user Gadgets | Instant mutable personal software | Dynamic Worker Facet + iframe | no outbound network; named bindings | build-to-first-use time, isolation failures, artifact reuse | employees can create tailored internal tools quickly |
| Gatekeeper resource sessions | Narrow access to GitHub, Docs, Notion, Slack, etc. | separate Worker/facet per connector | authorize observations; stage writes; durable action log | unauthorized attempts, approval latency, effect verification | autonomy without ambient company-wide access |
| Simulated pending writes | Agent continues while approval waits | connector-specific shadow state | later apply/reject/revert | proposal accuracy, dependency-on-provisional-state rate | less synchronous approval blocking |
| Agent catalog | Progressive tool/skill discovery | bounded connector catalog | entry count and metadata limits | discovery precision, irrelevant skill load, context bytes | better tool selection with less prompt bloat |
| Agent spawner | New chat/sub-agent | same agent harness | limited inherited bindings | spawn acceptance, lineage completeness | parallel task execution |
| Durable chat checkpoints | Resume agent after restart | Overseer durable state | persist model-facing snapshots; barrier at turn end | recovery success, duplicate tool effect rate | long-running chat continuity |
| Scheduler state machine | Background callbacks | account `ScheduleDriver` DO | `scheduleId`, `runId`, persisted state, retries, fencing | lateness, retry rate, dead occurrences | unattended recurring work |
| WebSocket RPC subscriptions | Live multiplayer state | Cap’n Web + DO | capability stubs and reconnection | event lag, replay loss, presence accuracy | responsive collaborative work |
| Content-addressed release bundles | Reproducible release content | modules/assets in R2 | manifest written last | provenance verification, rollback success | safer software distribution |
| Blueprints | Reusable app code | copied source snapshot | excludes credentials/live state | reuse rate, time saved, post-copy divergence | reusable institutional software patterns |

## Cloudflare advantages Company OS currently lacks

| Gap | Cloudflare evidence | Company OS current state | Priority |
|---|---|---|---:|
| Real operator product | Persistent web shell, workspace/chat/code/diff/output experiences | skills, schemas, scripts, tests; no accepted operator app | P0 |
| Sandboxed user-created apps | Gadgets are private mutable app instances ([README 52–62](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/README.md#L52-L62)) | no general Company App runtime | P1 |
| Capability-scoped integrations | Gatekeeper sessions and explicit introductions ([gatekeeper.ts 589–623](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/packages/workshop-shared/src/gatekeeper.ts#L589-L623)) | policy/skill contracts exist; live gateway product absent | P0 |
| Approval UX and action queue | writes become durable pending actions and may wait asynchronously ([gatekeeper.ts 789–814](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/packages/workshop-shared/src/gatekeeper.ts#L789-L814)) | proposals/evidence exist, but no unified end-user inbox | P0 |
| Progressive agent catalogs | context library exposes bounded SKILL metadata ([agent-skill.ts 46–63](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/packages/gatekeeper-context/src/agent-skill.ts#L46-L63)) | large skill library exists; discovery/assignment usability remains weak | P0 |
| Integrated artifact studio | code, files, diff, UI, chat, outputs in one surface | deliverables exist mainly as filesystem/Notion artifacts | P1 |
| Provider-native model routing | direct OpenAI/Anthropic/Google/Cloudflare/Ollama paths and API overrides | model routing policy exists, but no accepted cross-framework runtime gateway | P0 |
| Live workspace collaboration | DO-backed subscriptions and presence | no accepted real-time operator runtime | P2 |
| Mutable app templates | Blueprints clone whole app source | department/skill/project templates, but no runnable personal app template | P2 |
| Release packaging | immutable content-addressed blobs and manifest-last completion | package signing work exists, product updater absent | P1 |

## Where Company OS is stronger

| Company OS advantage | Why Cloudflare OS does not replace it |
|---|---|
| Master → dynamic Sol manager → Luna worker hierarchy | Cloudflare’s spawner is a lightweight chat-spawn API, not a company program protocol |
| Portfolio and company objective decomposition | Cloudflare workspaces do not provide a company-level portfolio authority model |
| Outcome digests, ownership, budgets, acceptance barriers | Cloudflare child spawns carry title/prompt/model/bindings, not accepted task contracts |
| Deliverable receipts and independent manager review | Cloudflare centers workspace/action history, not cross-department accepted deliverables |
| Business scorecards and quality gates | Cloudflare telemetry is product/runtime oriented, not business outcome governance |
| Dynamic organizational scaling | Cloudflare scheduler and workspaces use fixed local limits; they are not a dynamic corporate topology |
| External SQL control plane direction | Cloudflare is tightly coupled to Workers/DO/Facets |
| Specialized skill assignment requirements | Cloudflare has discovery catalogs, but not evidence that correct skills were selected and used |

## Critical findings: patterns that must not be copied

### P0 — Child spawning bypasses the action/approval seam

`AgentSpawnerGatekeeper.startSession()` receives an `ApprovalQueue` but discards it. `spawn()` and `spawnCallable()` directly call the Overseer, and a source TODO asks whether an audit record is needed ([overseer.ts 9445–9519](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/packages/workshop-backend/src/overseer.ts#L9445-L9519)).

**Company OS rule:** every child must originate from an accepted durable command containing parent lineage, project/tenant, outcome digest, capabilities, dependency set, budget, deadline, attempt/generation, lease, cancellation state, and terminal receipt. No adapter may create an unobserved child.

### P0 — BYO MCP can mislabel a destructive tool as read-only

Cloudflare’s MCP README explicitly states that a BYO MCP server marking a destructive tool `readOnlyHint: true` can run it without a prompt ([gatekeeper-mcp README 145–168](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/packages/gatekeeper-mcp/README.md#L145-L168)).

**Company OS rule:** server annotations are metadata, never authority. An administrator-owned taxonomy plus resource and argument constraints determines read/write/irreversible classification. Unknown is deny-by-default.

### P0 — This is not framework interoperability

The provider union is `openai | anthropic | google | cloudflare | ollama`, with an optional compatible API URL ([api.ts 919–949](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/packages/workshop-shared/src/api.ts#L919-L949)). The spawner config carries `modelId` and an environment binding snapshot ([api.ts 1259–1288](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/packages/workshop-shared/src/api.ts#L1259-L1288)).

Claude, Kimi, GPT, and other models in a picker do **not** equal Claude Code, Kimi Agent, Codex, Hermes, or Agents SDK runtime interoperability. Those frameworks have different lifecycle, file, tool, event, resume, cancellation, approval, and usage semantics.

### P1 — Counterfactual state must never become accepted truth

Cloudflare Gatekeepers can tell an agent a pending action completed and return simulated later reads ([README 75–79](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/README.md#L75-L79)). This is an innovative UX pattern but dangerous when downstream effects depend on provisional state.

**Company OS adaptation:** store typed `proposed`, `simulated`, `approved`, `applying`, `verified`, `rejected`, `compensated` states. A proposal may support planning, but never satisfies acceptance and never authorizes an irreversible dependent effect.

### P1 — Scheduler semantics are unsuitable for critical company workflows

Cloudflare’s scheduler has excellent stable run IDs, persist-before-RPC, bounded retries, and generation fencing. But a due slot is consumed even if admission or delivery fails; missed occurrences are skipped; disabling resets count; one account is a shared failure domain; v1 lacks run history, pause, and actor attribution ([scheduler README 62–100](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/packages/gatekeeper-scheduler/README.md#L62-L100), [142–171](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/packages/gatekeeper-scheduler/README.md#L142-L171), [225–229](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/packages/gatekeeper-scheduler/README.md#L225-L229)).

**Company OS adaptation:** occurrence history, explicit missed-run policy, independent delivery leases, actor identity, pause/resume, cancellation precedence, definition version, step/effect idempotency, dead letters, and configurable quotas.

### P1 — Release packaging is not a secure desktop updater

The build content-addresses modules/assets ([build-release 1–13](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/scripts/release/build-release.mjs#L1-L13)) and writes the manifest last ([build-release 124–139](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/scripts/release/build-release.mjs#L124-L139)). Promotion explicitly documents a check-then-act race that needs external serialization ([promote-release 1–17](https://github.com/cloudflare/cloudflare-os/blob/e1ab8fbd4f609aff7ede9d490bafe1bcf9b2a682/scripts/release/promote-release.mjs#L1-L17)). `git verify-commit` failed for the pinned commit with no signature output, so it is not accepted as a signed source release.

**Company OS rule:** signed reproducible packages, SBOM, threshold/TUF-style metadata, rollback protection, atomic install, health checks, migration compatibility, and last-known-good rollback.

## Adopt, adapt, reject

### Adopt as concepts

1. Per-resource capability sessions and explicit resource introductions.
2. Every read recorded as an observation; every side effect staged as a durable action.
3. Bounded untrusted catalogs for progressive skill/tool discovery.
4. No default egress from agent-generated code; only named bindings.
5. Stable logical run IDs, persist-before-RPC, retry bounds, and stale-generation fencing.
6. Durable vs provisional event separation and stream generation resets.
7. Content-addressed artifacts and manifest-last completeness.
8. Blueprints that exclude credentials, live connections, and private runtime state.
9. Integrated chat/code/diff/artifact/operator experience.
10. Provider-native inference paths where abstraction would erase reasoning, caching, or response semantics.

### Adapt behind Company OS-owned contracts

1. Gatekeepers → **Company Gateways** with typed proposals and verified outcomes.
2. Gadgets → **Company Apps** with project/tenant/run identity, quotas, and auditable artifact export.
3. Agent catalog → **Capability Catalog** with skill assignment receipts and performance feedback.
4. Agent spawner → **Execution Adapter Gateway** under durable parent commands.
5. Scheduler → **Occurrence Engine** with company-grade history and idempotency.
6. Workspace shell → **Control Station** for objective, org graph, tasks, artifacts, approval, incidents, and cost.
7. Blueprints → versioned company/department/program/app templates.
8. Simulated writes → visible typed shadow branches, never accepted actual state.

### Reject

- Wholesale Cloudflare Workers/Durable Object lock-in as the Company OS core.
- A second autonomous controller inside Cloudflare OS or any external framework.
- Chat history as task truth.
- Direct child spawning without durable authority and audit.
- Trust in MCP/provider self-declared read-only status.
- “All tools” grants that automatically absorb future catalog changes.
- Tool-name-only write scope when arguments/resources can be constrained.
- Counterfactual writes presented as completed business state.
- Dev environments with weaker egress/SSRF invariants as production evidence.
- Fixed account-wide scheduler failure domains.
- Unsigned updater or release flow.
- Desktop-held database/provider credentials.

## Target architecture: Company OS Control Station

```text
┌─────────────────────────────────────────────────────────────────────┐
│ CONTROL STATION                                                     │
│ Web app + thin Tauri desktop shell + Codex MCP/API control          │
│ objectives | org graph | tasks | artifacts | approvals | incidents │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ authenticated commands / event stream
┌──────────────────────────────▼──────────────────────────────────────┐
│ COMPANY OS CONTROL & DATA PLANE                                    │
│ Postgres authority | plans/DAGs | leases | events | outbox          │
│ policy/grants | budgets | evidence | acceptance | scorecards        │
└──────────┬───────────────────┬────────────────────┬─────────────────┘
           │                   │                    │
┌──────────▼─────────┐ ┌───────▼──────────┐ ┌──────▼─────────────────┐
│ EXECUTION ADAPTER  │ │ COMPANY GATEWAYS │ │ SANDBOX BROKER         │
│ Codex              │ │ GitHub/Notion... │ │ local/container/VM/    │
│ Claude Code/SDK    │ │ observe/propose/ │ │ Modal/Workers adapters │
│ Kimi Agent         │ │ approve/apply/   │ │ mounts/egress/secrets  │
│ Hermes Agent       │ │ verify/rollback  │ │ quotas/attestation     │
│ Agents SDK/future  │ │                  │ │                        │
└──────────┬─────────┘ └────────┬─────────┘ └──────────┬─────────────┘
           └────────────────────┴───────────────────────┘
                                │
                  external tools, models, and workloads
```

### Desktop boundary

**INFERENCE — candidate implementation decision:** Build the product as a shared React web app plus a thin Tauri 2-class shell. Tauri is preferred over Electron for the first prototype because the shell should remain small, memory-efficient, and separated from control authority. Stage 0 must validate updater, accessibility, OS integration, plugin maturity, and security requirements before this becomes an irreversible platform choice.

The desktop includes:

- objective and portfolio dashboard;
- live master → manager → worker graph;
- task/event timeline with causal lineage;
- artifact studio for code, docs, spreadsheets, images, audio/video, and app previews;
- capability and skill inspector;
- approval inbox with proposed diff, effect, risk, approver, and rollback plan;
- provider/runtime health and conformance status;
- tokens, cost, latency, utilization, and business outcome dashboard;
- incident, cancellation, recovery, and dead-letter surfaces;
- command palette and accessibility-first keyboard navigation.

The shell has an authenticated local broker using a Unix socket/named pipe, OS keychain, signed application identity, deep links, notifications, and local sandbox handoff. The renderer receives no raw database or provider credentials. Desktop crashes cannot stop programs; it reconstructs state from the durable event log.

The desktop threat model must also require a strict webview CSP, explicit native-command allowlist, disabled arbitrary navigation, origin-bound IPC, request nonces and sequence fencing, short-lived workload identity, local data encryption with rotation, redacted crash logs, signed deep links, dependency/SBOM scanning, and adversarial tests for IPC spoofing, malicious artifacts, path traversal, protocol-handler injection, and updater rollback. A Tauri shell is not intrinsically safe merely because it is smaller than Electron.

Codex should control the product through an authenticated MCP/API surface. Pixel/computer use may inspect or test the UI but must not be the authority path.

### Offline policy

**Allowed offline:** view cached plans/evidence/artifacts; compose unsubmitted commands; run a local sandbox only while a current signed policy bundle permits it.

**Denied offline:** external writes, new delegation, approval finalization, schedule claims, authority changes, remote provider calls. On reconnect, the client submits signed expiring intents; it never merges local authority state into canonical state.

## Multi-framework Execution Adapter Protocol

The core distinction is **model provider adapter ≠ agent framework adapter**. A framework adapter must normalize lifecycle and evidence, not language-model request syntax.

### Required envelopes

- `TaskEnvelope`: task/parent/project/program IDs, outcome digest, dependencies, attempt/generation, deadline, acceptance checks.
- `CapabilityGrant`: signed subject/resource/action/argument limits, expiry, run mode, delegation permission.
- `WorkspaceLease`: sandbox identity, mounts, quotas, lease generation, heartbeat and expiry.
- `LifecycleCommand`: launch, pause, resume, cancel, reconcile, terminate.
- `RunEvent`: ordered causal event with source identity and durable/provisional classification.
- `ArtifactReceipt`: content digest, producer, provenance, verification and accepted state.
- `UsageRecord`: requested and observed model/runtime, tokens, cost, latency, cache utilization.
- `ResumeToken`: adapter-owned opaque state plus controller generation binding.
- `HealthSnapshot`: runtime reachability, observed capabilities, current task, last heartbeat.

Every envelope also carries protocol version, issuer, audience, tenant, nonce, created/expiry times, signature/key ID, and canonical digest. Transport must use mutually authenticated workload identity or an equivalent signed challenge; neither a desktop session nor an adapter process is trusted solely because it is local.

### Required adapter methods

```text
discoverCapabilities() -> CapabilityDescriptor
prepare(TaskEnvelope, CapabilityGrant, WorkspaceLease) -> PreparedRun
launch(PreparedRun) -> ObservedRunIdentity
observe(run, cursor) -> RunEvent[]
heartbeat(run) -> HealthSnapshot
send(run, message) -> CommandReceipt
cancel(run, generation) -> CancellationReceipt
resume(run, ResumeToken) -> ObservedRunIdentity
reconcile(run) -> ReconciliationReceipt
settle(run) -> TerminalReceipt
```

### Adapter implementations

1. Codex Native adapter — first and reference implementation.
2. Claude Code / Claude Agent SDK adapter.
3. Kimi Agent adapter.
4. Hermes Agent adapter.
5. OpenAI Agents SDK adapter.
6. Generic MCP/A2A bridge for narrower runtimes.

Every adapter is a worker boundary. It cannot mint authority, change budgets, accept its own deliverables, or spawn an unregistered child. Requested identity is never promoted to observed identity. Unavailable tokens/cost remain unavailable, never zero.

### Conformance suite

Each adapter must pass:

- create/observe/stream/cancel/resume/settle happy path;
- crash before create acknowledgement;
- crash after create but before controller receipt;
- duplicate launch command;
- stale lease and stale generation;
- cancel vs completion race;
- crash after external effect;
- restart/replay from durable cursor;
- missing or dishonest usage telemetry;
- provider substitution or wrong observed model;
- capability denial and attempted widening;
- prompt-injection attempt to call a forbidden tool;
- artifact digest mismatch;
- network partition and late event delivery.

## Ordered build roadmap

Scores: 10 is highest expected performance gain, implementation complexity, or execution risk.

| Phase | Outcome | Gain | Complexity | Risk | Exit gate |
|---:|---|---:|---:|---:|---|
| 0 | Freeze TaskAdapter, event, grant, proposal/effect, sandbox, and signed-update contracts; complete threat model | 10 | 7 | 8 | adversarial contract suite; zero unresolved P0 |
| 1 | Real Codex vertical slice: DB command → observed run → stream → cancel/reconcile → receipt | 10 | 8 | 8 | fault matrix passes; read-only tools only |
| 2 | Read-only Control Station web app and desktop shell | 9 | 8 | 5 | state rebuild, offline/reconnect, revocation, UX/accessibility proof |
| 3 | Capability Catalog and progressive skill assignment | 8 | 5 | 4 | specialized tasks select correct skills with receipts; prompt budget respected |
| 4 | Sandbox broker and read-only Company Gateways | 10 | 9 | 9 | escape, exfiltration, SSRF, secret, cross-project tests pass |
| 5 | Claude, Kimi, Hermes adapters through identical conformance suite | 9 | 8 | 8 | lifecycle and identity matrix passes without special authority paths |
| 6 | Controlled writes: propose → approve → apply → verify → compensate | 10 | 9 | 10 | irreversible-effect fixtures, stale approval, replay, rollback drills pass |
| 7 | Company-grade occurrence engine and scheduled programs | 9 | 8 | 9 | run history, catch-up policy, cancellation, dead-letter and exact-effect tests pass |
| 8 | Artifact studio and sandboxed Company Apps / Blueprints | 8 | 9 | 8 | three materially different apps; isolation and export provenance pass |
| 9 | Signed desktop distribution and staged updater | 7 | 8 | 9 | reproducible build, SBOM, threshold signature, atomic rollback proof |
| 10 | Real-time collaboration and higher concurrency | 7 | 8 | 7 | no collisions; load, recovery, tenancy, cost controls pass at each scale step |

Phases 1 and 2 can overlap only after Phase 0 contracts freeze. UI work must consume recorded events; it may not invent backend state.

## First useful vertical slice

Do not start by recreating Cloudflare OS. Deliver one measurable Company OS operation:

- one concrete business objective;
- dynamic plan with two Sol managers only if decomposition justifies two;
- Luna workers doing bounded labor through the Codex adapter;
- one read-only GitHub gateway and one read-only Notion gateway;
- live Control Station view of lineage, state, artifacts, evidence, tokens/cost, and acceptance;
- one Claude adapter running in shadow conformance mode;
- tested cancellation, crash recovery, replay, and stale lease rejection;
- no production writes.

### Acceptance metrics

- 100% task-envelope and capability-grant validation.
- Zero duplicate launches, write collisions, cross-project reads, or unauthorized effects.
- Cancellation acknowledgement ≤5 seconds p95 where the provider exposes cancellation.
- Event lag ≤1 second p95 and warm task start ≤3 seconds p95.
- ≥85% first-pass artifact acceptance and <20% rework.
- ≥70% bounded labor assigned to Luna; manager overhead <20% of measured usage.
- 100% adapter conformance scenarios pass.
- 100% write proposals identify resource, exact effect, risk, approver, idempotency key, and compensation/rollback status.
- Unknown/unreported usage is never recorded as zero.
- Desktop restart reconstructs state with zero lost accepted commands.
- Specialized deliverables have a catalog selection receipt showing the relevant skills were evaluated and assigned.
- Worker prompt load remains bounded: no more than four skill entry points and 48 KiB unless a measured exception is accepted.

## Issue and community signal

These are mutable reports, not confirmed source defects unless linked above:

- [Issue #15](https://github.com/cloudflare/cloudflare-os/issues/15): initial pnpm run crash on RHEL.
- [Issue #13](https://github.com/cloudflare/cloudflare-os/issues/13): request for MCP Apps rich UI; current gap signal.
- [Issue #11](https://github.com/cloudflare/cloudflare-os/issues/11): local MCP requires HTTPS; local integration friction.
- [Issue #10](https://github.com/cloudflare/cloudflare-os/issues/10): stale GitHub credentials and missing repair/removal UX.
- [Issue #9](https://github.com/cloudflare/cloudflare-os/issues/9): free-plan gating discovered late in deployment flow.
- [Issue #8](https://github.com/cloudflare/cloudflare-os/issues/8): dependency advisories, closed; distinct from the zero-advisory repository API result.

These reinforce the decision to mine mechanisms, not treat the early-access repository as production-ready Company OS infrastructure.

## Verification performed

- Exact `HEAD` and tree verified.
- `git ls-remote` and fetch matched the pinned `main` during research.
- Clone remained clean; `git diff --exit-code` passed.
- Static inventory: 809 tracked repository paths; 109 tracked `*.test.*` / `*.spec.*` files. These are inventory counts, not coverage or quality evidence.
- Safe no-install run: `NODE_OPTIONS=--no-warnings node --test scripts/*.test.js` produced 14 passing assertions. Three top-level suites could not load because local dependencies `typescript`, `jsonc-parser`, and `aws4fetch` were absent. No install was authorized; this is an environment limitation, not a product failure.
- Independently rechecked the child-spawner bypass, BYO MCP trust semantics, hard-coded provider/spawner shape, scheduler tradeoffs, and development SSRF variance at the exact pin.
- Runtime behavior, sandbox escape resistance, live provider execution, desktop packaging, and production deployment were not tested and are not claimed.

## Final recommendation

Proceed with **Stage 0 contract and threat-model work**, followed by the **Codex real-runtime vertical slice** and a **read-only Control Station**. Do not begin with a cosmetic desktop wrapper and do not graft Cloudflare OS into the core. The high-leverage outcome is a provider-neutral, capability-safe operating substrate that can command several agent frameworks while preserving one Company OS authority chain.

Cloudflare OS contributes the missing product intuition: agents need an actual place to work, create software, connect to resources safely, and show humans what is happening. Company OS contributes the missing company logic: objectives, hierarchy, budgets, acceptance, evidence, scale, and business outcomes. The fusion is the product.
