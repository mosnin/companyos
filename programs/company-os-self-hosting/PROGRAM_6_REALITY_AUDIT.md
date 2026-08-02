# Program 6 Reality Audit

**Decision: NO-GO — remain in `reality_audit`.**

This is a decision record, not launch approval.  It separates what has been
accepted in source, what is installed, what the authoritative instance says,
what local fixtures prove, and what has never been observed at a live provider.
The governing outcome remains: prove one provider-authenticated Sol manager can
supervise one exact GPT-5.6 Luna worker through a durable, budgeted,
cancellable, restart-safe lifecycle in an isolated Company OS project.  The
north star remains a self-improving company control plane that turns ambitious
direction into independently verified outcomes.

## Bottom line

Program 6 has a strong, deliberately disabled control and verification
substrate.  It can represent a constrained runtime admission, verify a signed
gateway-shaped result, model lifecycle and receipt invariants in local tests,
and render an accepted read-only operator surface.  It **cannot yet launch or
supervise a provider worker**.  There is no protected launcher, provider
credential path, authenticated provider connector, live provider event, exact
Luna identity proof, terminal receipt chain, priced usage evidence, or real
restart/cancellation fault evidence.

Fixture-only Responses behavior is not live provider execution: its transport
must be injected and explicitly marked `fixture_only`; the module contains no
HTTP client, provider URL, API-key lookup, listener, or network implementation.
It exercises deterministic raw JSON fixtures and test keys, not an OpenAI
account or a provider-observed run.  A signed fixture result can validate a
parser and trust boundary; it cannot establish credential readiness, model
availability, network behavior, provider semantics, billing, or operational
recovery.

## Evidence ledger — do not merge these categories

| Category | Established fact | What it does not establish |
| --- | --- | --- |
| Accepted source | Canonical commit `a761efab3884555ac352c95cc7378017bbc9415a` is the 0.4.3 release source.  The independent attestation accepts the exact 21-file read-only Operator Command Center surface, including the typed transition-archive repair paths. | Provider execution, scheduling, distribution operation, production, customer mutation, or Chippy onboarding are explicitly outside that attestation. |
| Installed distribution | `python3 scripts/distribution.py check-install --target /Users/preston/.codex/skills` passed from that exact source worktree: the installed distribution matches canonical source. | Installed parity is packaging evidence only; it is not a protected launcher, provider credential, or live-runtime attestation. |
| Authoritative instance | Read-only audit of `/Users/preston/Documents/Codex/company-os-core/.company-os/control.db` reports healthy SQLite authority at revision **131**, Program 6, `paused`; no active/ready work; no valid evidence; runtime disabled with zero attempts/inboxes; scheduler not ready. | A healthy paused database is not runtime success.  It currently fails validation because `reality_audit` has no valid `evidence.reality`. |
| Disposable fixture proof | The Responses adapter, provider-neutral gateway, lifecycle, and receipt modules have focused local test evidence.  The fixture uses owner-only local files/socket checks, signed test envelopes, raw-byte retention, idempotency tombstones, and an injected fixture transport. | Any live OpenAI call, a real account/workspace, provider-observed model/usage/cost, real cancellation, or production durability. |
| Missing live-provider proof | None exists in this audit.  There are no accepted provider launch/running/terminal observations, failure/cancellation traces, receipts, artifacts, telemetry, reconciliation, or provider billing/pricing evidence. | Nothing may be inferred or backfilled from requested model strings, local hashes, HTTP-like fixture bytes, or test success. |

Primary citations: `README.md`; `programs/company-os-self-hosting/OPERATOR_COMMAND_CENTER_ACCEPTANCE_ATTESTATION.json`; `programs/company-os-self-hosting/OPERATOR_COMMAND_CENTER_ACCEPTANCE_REPORT.md`; commit `a761efab3884555ac352c95cc7378017bbc9415a`.

## Architecture and control path as implemented

```text
external decision issuer ──signed admission/cancel/reconcile grant──┐
                                                                  ▼
project SQLite control store → admitted attempt / immutable binding → gateway request
     ▲                           │                                  │
     │                           │ signed observations/receipts      │ (missing live connector)
immutable events, exports       ▼                                  ▼
and fenced leases          observation inbox ← signed gateway result ← fixture transport only
                                  │
                                  └─ lifecycle / receipts / reconciliation verifiers (not a live controller path)

external protected launcher + provider credentials + real provider surface: MISSING
```

- `control_store.py` is the project-local SQLite authority; JSON and JSONL are
  deterministic exports.  Its audit reports ordered events, projections,
  idempotency and one-project constraints.
- `company_os_controller.py` has feature-gated admission and observation
  commands.  Both reject while `runtime_adapter.enabled` is false.  Admission
  requires a current lease, signed actor grant, exact fabric identity, model,
  scope, budget, allowlisted provider/surface/account, and idempotency key.
  Observation ingestion verifies a separate gateway keyring and preserves a
  trusted inbox **without lifecycle advancement**.
- `runtime_gateway.py`, `runtime_lifecycle.py`, and `runtime_receipts.py`
  define and verify deterministic request/result, lifecycle, telemetry,
  cancellation, receipt-root, and reconciliation rules.  They are not proof
  that a gateway has performed those operations at a provider.
- `openai_responses_gateway.py` is a specifically fixture-only adapter.  It
  signs a normalized result after injected fixture `create`, `retrieve`, or
  `cancel` bytes; it never becomes a production client by virtue of passing its
  test suite.
- The Operator Command Center is an accepted **read-only projection** of
  authority.  It is valuable decision visibility, not an execution engine.

Control-path citations: `docs/ARCHITECTURE.md`;
`skills/company-os/elastic-company-os/scripts/company_os_controller.py`;
`skills/company-os/elastic-company-os/scripts/control_store.py`;
`skills/company-os/elastic-company-os/scripts/runtime_gateway.py`;
`skills/company-os/elastic-company-os/scripts/runtime_lifecycle.py`;
`skills/company-os/elastic-company-os/scripts/runtime_receipts.py`;
`skills/company-os/elastic-company-os/scripts/openai_responses_gateway.py`.

## Current capabilities and non-capabilities

| Capability | Status | Boundary |
| --- | --- | --- |
| Transactional single-host control, event pairing, idempotency, leases, cancellation precedence, and state audit | Source- and local-test-supported; authoritative store audit healthy at rev131 | Single-host control substrate, not multi-host or live provider proof. |
| Program-transition repair integrity | Source accepted in the 0.4.3 Operator Command Center surface; authoritative state is rev131 after the repair | The historical application handoff was a dry-run at rev130; it is not itself current-state evidence. |
| Runtime admission and signed observation inbox | Implemented but disabled | Cannot activate or advance without later governed configuration and external prerequisites. |
| Runtime lifecycle, receipt, and reconciliation verification | Feature-off local logic and fixtures | Not durably integrated into an authenticated live gateway/provider cycle. |
| OpenAI Responses boundary | Fixture-only local adapter | No network client, credential provisioning, listener, or OpenAI execution. |
| Operator decision surface | Accepted product surface, 9.22/10 mean; all 13 critical dimensions at least 9.0 | Read-only; does not certify runtime, schedule, production, or customers. |
| Scheduler / recurring work / Chippy | Disabled or frozen | Explicitly out of scope until prior standalone gates pass. |

## Exact blockers and decision impact

1. **Reality evidence is missing now.**  The rev131 audit error is exactly
   `phase reality_audit requires valid evidence.reality`; `valid_evidence_count`
   is zero.  Program 6 cannot leave this phase without an independently
   reviewable evidence record that describes the actual current boundary.
2. **Protected authority is missing.**  The authoritative audit reports
   `actor_issuer_ready: false` and `protected_launcher_ready: false`, with the
   external prerequisite that a launcher verify issuer and scheduler authority
   outside the controller.  Do not enable scheduling or runtime in response.
3. **No authenticated provider execution path exists.**  The adapter is
   disabled and contains only fixture transport.  There is no credential
   provisioner, protected gateway service/local transport, or connector mapping
   real Responses launch/read/wait/cancel operations into the contract.
4. **Exact `gpt-5.6-luna` availability is unproven.**  Requested and observed
   model identities are intentionally separate.  A missing Luna surface must
   produce `blocked_model_unavailable`, never Sol/Terra substitution.
5. **No operational lifecycle evidence exists.**  Success, provider failure,
   cancellation acknowledgement, late completion, ambiguous launch, restart,
   raw bytes, artifact checks, and signed reconciliation have no live proof.
6. **Cost and token evidence is unavailable.**  Fixture usage-schema checks
   exist, but the fixture implementation reports `cost_status: unavailable`;
   it refuses successful receipt attribution without authoritative priced
   usage.  Rev131 has no attempts and `luna_token_share: null`.

**Next-phase decision:** approve intelligence and feasibility work only.  Do
not authorize implementation, enabling flags, issuance, scheduling, provider
calls, credential creation, or customer work based on this audit.

## Recommended intelligence questions / feasibility checks

These are the next exact questions, not an implementation plan:

1. Which protected, independently operated launcher can verify the decision
   issuer, enforce one lease/fence, restrict the provider/account/surface, and
   keep provider credentials outside controller state, artifacts, and logs?
2. Is there a callable provider surface that can return provider-attested exact
   `gpt-5.6-sol` and `gpt-5.6-luna` identities for the narrow read-only canary?
   If not, document `blocked_model_unavailable` and preserve the NO-GO.
3. Can that surface supply raw launch/read/wait/cancel/terminal bytes,
   idempotency lookup after ambiguous launch, native event ordering, provider
   timestamps, and reliable cancellation acknowledgement needed by the frozen
   gateway contract?
4. What immutable, authenticated usage and pricing/billing evidence can bind
   tokens and dollars to each provider task, including cached/reasoning token
   semantics and a versioned pricing digest?  If unavailable, which receipt
   states remain blocked?
5. Can a protected gateway process be isolated so that socket permissions,
   key separation/rotation, credential non-retention, raw-artifact retention,
   and crash recovery meet the contracts without expanding scopes or effects?
6. What minimal provider-sandbox fault matrix can demonstrate real success,
   provider failure, cancellation, late terminal result, ambiguous launch, and
   process restart without production/customer effects?

Feasibility references: `programs/company-os-self-hosting/PHASE_2_PROGRAM_CONTRACT.md`;
`programs/company-os-self-hosting/PHASE_2_OPENAI_RESPONSES_GATEWAY_IMPLEMENTATION_CONTRACT.md`;
`programs/company-os-self-hosting/PHASE_2_CONNECTOR_FEASIBILITY.md`;
`programs/company-os-self-hosting/PHASE_2_PROVIDER_SURFACE_DISCOVERY.md`.

## Quality baseline and brutally honest scorecard

| Dimension | Score/status | Gate interpretation |
| --- | --- | --- |
| Accepted Operator Command Center experience | **9.22/10**, 13/13 critical dimensions at least 9.0 | Accepted, but only for the exact read-only product surface. |
| Runtime provider execution | **0.0/10** | Below the 8/10 gate: no live run or provider evidence. |
| Protected launcher / issuer readiness | **0.0/10** | Below the 9/10 critical control gate: both are missing in rev131. |
| Cost and token observability | **0.0/10** live evidence | Below gate: no provider-priced usage; fixture cost is explicitly unavailable. |
| Runtime lifecycle/receipt logic | **Unscored for acceptance; local test evidence only** | Do not convert fixture coverage into an operational score. |
| Program 6 exit | **NO-GO** | Reality evidence and all live-provider/control prerequisites remain missing. |

The 0.4.3 acceptance must not be re-used as a Program 6 runtime score.  Its
attestation says exactly that the fixture-only adapter is outside its accepted
surface and unaccepted as provider execution.

## Read-only verification performed for this audit

All checks were run from an isolated worktree at
`/Users/preston/Documents/Codex/company-os-core-program6-reality-audit`, based
on `a761efab3884555ac352c95cc7378017bbc9415a`; no `.company-os` state,
provider, scheduler, credential, Chippy, or production system was changed.

- `scripts/distribution.py verify-manifest` — passed.
- `scripts/distribution.py check-install --target /Users/preston/.codex/skills`
  — passed; installed distribution matches canonical source.
- Focused fixture/runtime suites — **62/62 passed**: Responses gateway 29,
  provider-neutral runtime gateway 10, lifecycle 14, receipts 9.
- Controller — **126/126 passed**; transactional control store — **37/37
  passed**; runtime-observation integration — **8/8 passed**; operator brief —
  **30/30 passed**.
- Repository distribution and accepted-surface suite — **29/29 passed**.
- `git diff --check` — passed before this report was added.
- Read-only `company_os_controller.py audit` on the canonical instance —
  healthy SQLite store at revision 131, but validation NO-GO for missing
  reality evidence and external protected-launcher prerequisite.

These are local test and parity results.  They do not supersede the explicit
runtime evidence gap.

## Acceptance criteria to leave the reality audit

Leaving `reality_audit` requires independent acceptance of an evidence record
that, at minimum:

1. names the exact authoritative revision and records the source/installed/
   state/fixture/live-provider boundaries above without claiming missing proof;
2. confirms the instance remains paused, scheduler and runtime remain disabled,
   and Chippy remains frozen pending later gates;
3. proves, or honestly blocks, protected launcher and issuer feasibility;
4. proves, or honestly blocks, exact provider surface and `gpt-5.6-luna`
   availability without model substitution;
5. specifies the authenticated raw-observation, cancellation, idempotency,
   restart, receipt, and pricing evidence a later live canary must provide;
6. is independently reviewed with no P0/P1 finding and does not award a
   runtime, security, authority, durability, cancellation, or evidence score
   below the required gate; and
7. changes no feature flag, provider credential, scheduler, production system,
   customer data, or Chippy state as part of audit acceptance.

## Newest decisions and residual risks

- The Program 5→6 transition repair was designed at rev130 and is now reflected
  by the authoritative rev131 audit.  The original handoff remains useful for
  the invariant and payload history, but its `NOT_APPLIED` status is historical,
  not current state.  See
  `programs/company-os-self-hosting/PROGRAM_TRANSITION_REPAIR_APPLICATION_HANDOFF.md`.
- Version 0.4.3 source and installed parity are verified.  That is a meaningful
  release/provenance improvement, not evidence of a runtime deployment.
- The main risk is false promotion: treating a requested model, an admission,
  a fixture signature, test-key result, local raw bytes, or a passing unit test
  as provider-authenticated execution.  The program must continue to fail
  closed on that distinction.
- Secondary risks are credential leakage at a future gateway boundary,
  launch/cancel ambiguity, missing pricing provenance, incomplete recovery
  semantics, and collapsing decision-issuer/gateway/implementation/reviewer
  authority.  None is retired by this report.
