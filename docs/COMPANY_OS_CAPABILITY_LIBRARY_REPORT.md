# Company OS Capability Library — Implementation Report

Status: independently accepted source slice; installation and runtime pending
Date: 2026-08-03
Scope: external capability ingestion, selective assignment, and manager/worker delivery

## Plain-English outcome

Company OS now treats external skill collections like a secure library, not a
giant prompt. A manager searches a compact index, deliberately chooses zero to
four procedures for one task, and records why each is needed. The selected
references are tied to the exact manager or worker packet with content hashes.
Only that task can see them. The skill text never becomes Company OS authority
and cannot grant tools, money, credentials, deployment, messaging, or broader
scope.

The master → manager → worker structure is unchanged. This is an additive
capability plane beneath the existing authority, budget, cancellation,
ownership, evidence, and acceptance controls.

## What was requested

The campaign covered all 23 requested sources, including the requested
`CLAUDE.md`, package-installer, and shell-installer forms. None of those install
commands was executed. Each source was cloned or resolved outside Company OS,
pinned to an exact Git commit and tree, and inspected as untrusted evidence.

## Source decisions

| Source | Decision | Practical meaning |
| --- | --- | --- |
| Addy Osmani agent skills | extract wrapper | Reuse bounded test/review mechanisms, not hooks or pack-wide authority. |
| Agent Native / Builder.io skills | quarantine | Installer, MCP, auth, config writes, mutable fetches, telemetry, and unclear license block use. |
| Hormozi skills | reference only | Useful commercial concepts may inform future original Company OS methods; no dispatch. |
| Antfu skills | curated subset candidate | Provenance structure is useful; destructive sync, hooks, and mutable fetches are excluded. |
| Cybersecurity skills | quarantine | Large dual-use corpus remains inactive; any future use requires a separate defensive charter. |
| Browserbase skills | extract wrapper | Reuse domain-bound browser design only; exclude cookies, credentials, CDP passthrough, and provider mutation. |
| Cloudflare skills | curated subset candidate | Reuse a pinned durable-state design slice; exclude MCP, provider, deploy, secret, and delete actions. |
| Founder Playbook | reference only | Strategy reference only; legal and authority-pressure language is not dispatched. |
| Google Maps agent skills | quarantine | License conflict plus credential, scraping, network, and legal risk block dispatch. |
| Karpathy guidelines | extract wrapper | Reuse small assumption/simplicity mechanisms; never append remote text into control instructions. |
| Business planning skills | extract wrapper | Reuse bounded market, capability, risk, and scenario procedures. |
| Stratarts | extract wrapper | Reuse one bounded market-opportunity artifact method. |
| Microsoft skills | curated subset candidate | Reuse the MCP contract-design mechanism; exclude hooks, memory injection, provider, and deployment behavior. |
| AI Business Skills | extract wrapper | Reuse one compact marketing-context intake method. |
| MiniMax skills | quarantine | Material license ambiguity, provider behavior, and broad overlap block dispatch. |
| E-commerce skills | curated subset candidate | Retained for later exact subset review; no whole-pack install. |
| NVIDIA skills | curated subset candidate | Strong catalog/eval ideas; only exact licensed subsets may advance after review. |
| Remotion skills | reference only | Useful video architecture, but missing license/source-of-truth proof blocks vendoring. |
| Superpowers | extract wrapper | Reuse systematic debugging only; exclude hooks, persuasion, orchestration, VCS, and global behavior. |
| Vercel agent skills | reference only | Useful frontend evidence, but repository-wide license and live provider behavior are unresolved. |
| Corporate skills | quarantine | Mixed provenance, credentials, legal content, and incomplete licensing block dispatch. |
| Wondel AI skills | reference only | Broad business reference only; no implicit or global loading. |
| AI Legal Claude | quarantine | No safe install or dispatch until licensing, legal scope, scripts, and credential behavior are resolved. |

## Inventory result

- Requested sources handled: **23 / 23**
- Indexed source instruction entrypoints: **2,621**
- Source repositories installed into Company OS: **0**
- Remote installers or repository hooks executed: **0**
- External skills implicitly injected into prompts: **0**
- Initial dispatchable external entries: **0**

The source catalog is intentionally searchable but non-dispatchable. A source
entry can become usable only through a small Company OS-owned wrapper that is
independently reviewed, locally hashed, promoted into the final catalog, and
bound to a single task.

## Architecture implemented

1. **Pinned source corpus** — exact source URLs, commits, trees, licenses,
   dispositions, risk flags, and entrypoint hashes live outside Company OS.
2. **Metadata-only catalog** — search returns IDs, descriptions, domains,
   roles, trust, and source identity. It never returns procedural bodies.
3. **Trust and license gate** — approved, reference-only, quarantine, and
   rejected states are enforced. Missing redistribution rights block direct
   vendoring.
4. **Explicit request** — the manager binds program, packet, role, domains,
   existing permissions, a canonical selected-ID set, an independent
   `execution_order`, rationale, and task-local limits. The task definition is
   authoritative for domains and skill permissions.
5. **Deterministic resolver** — fails on unapproved skills, role/domain mismatch,
   permission widening, conflict, symlink/path escape, hash drift, or bloat.
6. **Deterministic host augmentation** — reproduces every request/assignment
   pair and adds digest-only skill references to the accepted host manifest.
7. **Task-local Program Preflight binding** — reproduces the assignment from
   the installed approved catalog; matches request domains and permissions to
   the definition; proves child narrowing; and emits one receipt only in the
   matching packet. Siblings receive no skill metadata.
8. **Lazy worker loading** — the assigned task verifies the packet and local
   entrypoint digest, then reads only that selected standalone `SKILL.md`.
   Catalog v1 rejects sibling sidecars and unbound resources.
9. **Independent acceptance** — the manager judges the produced artifact; a
   valid skill assignment is not evidence that the work is good.

## Anti-bloat and control limits

- Zero selected skills is valid and preserves the base host.
- Maximum four skills and 48 KiB of entrypoint text per task by default.
- Maximum five metadata search results by default.
- Multi-skill bundles must declare one unique, exact `execution_order` covering
  the selected set. Packet-bound companions are permitted; autonomous wrapper
  discovery is not.
- No catalog, source root, installer, generic router, or skill body is pasted
  into master or manager context.
- Strategy procedures default to managers; production procedures default to
  workers. A production skill assigned to a worker is not loaded by its manager.
- Skills may narrow technique but never widen scope, permissions, tools,
  budgets, concurrency, external effects, or delegation rights.
- Company OS instructions always outrank imported procedure text.

## Curated Company OS wrappers

Twelve small, original wrappers passed independent manager inspection and form
the first approved catalog. They cover:

- engineering adversarial review
- red/green evidence discipline
- browser boundary design
- MCP tool contract design
- durable state design
- systematic debugging
- marketing context intake
- market definition
- capability assessment
- risk matrix
- scenario development
- market-opportunity artifact design

These wrappers retain the useful procedure while removing installer commands,
global hooks, provider credentials, authority override, child orchestration,
live mutation, telemetry, and unrelated source content.

## Verification status

Current evidence:

- Catalog/resolver, Program Preflight, and role-contract focused tests: **93
  passed**
- Full repository test discovery: **188 run; 187 passed, 1 intentional skip**
- Distribution manifest: **written and verified**
- Final catalog: **23 sources, 2,633 entries, 12 dispatchable wrappers**
- Final catalog SHA-256: **`eaff2f1a03189d72b3ded9290df7f92bc236e1eaa28e6c6df2328c4f8a765ca9`**
- Warm local metadata-search probe: **11.5 ms median, 13.3 ms p95 across 50
  searches**; results contained metadata only
- Legacy Brokerage and SaaS packet fixtures: **byte-compatible and passing**
- Task isolation: manager and worker packets receive only their own assigned
  skill, while unrelated packets receive none
- Negative paths covered: quarantine/reference-only dispatch, role mismatch,
  domain mismatch, permission widening, conflicts, size limits, symlinks, hash
  drift, assignment rebinding, duplicate assignment, unknown packet, role
  mismatch, artifact drift, required-capability bypass, incomplete or duplicate
  execution order, reordered requested IDs, permission injection, sibling
  injection, and rehashed order substitution
- Reproducible single-skill simulation: `systematic-debugging` resolved only
  into `activation_path_work`; its **6,721-byte** packet verified, while all
  five manager packets and four sibling worker packets contained no
  assigned-skill metadata
- Independent two-skill composition challenge: the manager selected canonical
  IDs `engineering-red-green-evidence` plus `systematic-debugging`, then bound
  execution as **systematic debugging → red/green evidence**. The **8,339-byte**
  bundle stayed under the 49,152-byte limit, compiled and verified, preserved
  empty permissions, and remained absent from all five manager and four sibling
  worker packets. The manager accepted this source-contract evidence first pass
  with zero rework after **64 / 64** focused checks and eight negative attacks.
  The compact receipt is
  `/Users/preston/Documents/Codex/external-skill-sources/company-os-capability-campaign-2026-08-03/assignment-simulation/control/post-composition/systematic-debugging-red-green.acceptance-receipt.json`
  with SHA-256
  `56c7917f718602bf175e1ebe7b9c5ae391f1205b99da9cd831dff994f40b7855`.

The official skill quick-validator was invoked for every wrapper, but all local
interpreters lack its PyYAML dependency. No dependency was installed or fetched.
Independent Ruby YAML parsing plus stricter frontmatter/path/name/size checks
passed the router and all 12 wrappers; the environment limitation remains explicit rather than being
reported as an official-validator pass.

## Known boundaries

- No external pack was globally installed.
- No provider, credential, deployment, production, customer, or scheduler state
  was changed.
- Reference-only and quarantined entries are visible for research decisions but
  cannot be assigned.
- Dynamic provider documentation and current cloud behavior were not claimed.
- Requested worker model identity is intent unless the host exposes observed
  model telemetry.
- No fresh worker executed the current two-skill composition. Compilation and
  packet order are proven; runtime adherence to that order, current wrapper
  bytes, and Luna execution are not yet observed.

## Next acceptance steps

1. Add a read-only packet-only worker verifier, make dispatchable-only search
   the safe default, and move the compact composition receipt into versioned
   portable evidence.
2. Run one fresh worker from the current two-skill packet and inspect actual
   skill loading, order adherence, artifact quality, model telemetry, and
   failure behavior.
3. Decide global installation separately after source acceptance; runtime
   activation and scheduling remain separate gates.
4. Publish this report to a new Notion page once the Notion connection is
   available in this task.

Independent review accepted this source slice at **9.2 / 10** with no P0 or P1
findings. Its lower dimensions were discovery and worker usability (**8.5**),
evidence portability (**8.3**), current real-worker evidence (**8.1**), and
installed runtime readiness (**5.5**). Those limits remain explicit rather
than being promoted into a broader readiness claim.
