# Company OS Self-Hosting Program — Phase 1

## Program identity

- Program ID: `company-os-self-hosting`
- Program version: `1`
- Phase: `kernel-truthfulness`
- North star: Company OS can direct and improve ambitious project work without confusing agent activity, safety work, or self-reported status with accepted progress.
- Phase outcome: the installed Company OS kernel rejects invalid authority, lease, metric, scope, and self-adaptation transitions before they mutate governed state, and expresses one bounded fractal control pattern that can be reused at every orchestration level.

## Why this phase is first

The current system is a useful governance specification with a local state-machine kernel, but it cannot truthfully govern its own next phase while expired leases, invalid metrics, overlapping ownership, and unauthenticated self-adaptation can pass transition boundaries. Runtime launch and scheduling come later; automating an untrustworthy kernel would amplify errors.

## Fractal control invariant

The same six-part contract applies at every level:

1. **Outcome:** a concrete result and why it matters.
2. **Envelope:** scope, authority, constraints, dependencies, and non-goals.
3. **Budget:** time, tokens, cost, concurrency, and retry ceilings.
4. **Execution:** one bounded unit of work with a single accountable owner.
5. **Evidence:** attributable artifacts and checks that prove the result.
6. **Reconciliation:** accept, rework, escalate, pause, or terminate.

The pattern repeats at `company → program → manager → worker`, but authority and budgets may only narrow downward. Evidence and exceptions roll upward. The maximum executable delegation depth remains `master → manager → worker`; the meta-loop remains depth one.

## Phase 1 scope

### Included

- Reject non-positive lease TTLs.
- Bind each lease to its program, owner, explicit permitted transitions, generation, and expiry. Require the caller to present the matching owner and an unexpired lease at every lease-authorized transition. This local binding is not a claim of authenticated runtime identity; that remains a Phase 2 external-attestation requirement.
- Reject negative, non-finite, boolean, string, or otherwise invalid cost, latency, token, and worker metrics before state mutation. Cost and latency are finite non-negative numbers; token and count metrics are non-negative integers.
- Canonicalize declared write scopes lexically and deterministically, without consulting the filesystem. Reject aliases, empty/dot segments, traversal, absolute paths, duplicates, and parent/child overlap in either declaration order.
- Prevent unreviewed scaling above the initial 2-manager / 3-worker-per-manager / 6-worker global envelope.
- Require independently signed adaptation review. The signed claims must bind the exact proposal digest, program/version, decision, reviewer identity, nonce, and expiry; proposer/reviewer strings alone are not authority.
- Encode the fractal contract in the fabric manifest with explicit program, manager, and worker budget objects. Validate that time, tokens, cost, concurrency, and retry authority only narrow at each child level and that evidence references roll upward.
- Bump the core/schema version and make schema-6 upgrades fail closed: archive old unsigned adaptation/fabric authority, clear executable state, and require a new reality audit instead of silently grandfathering it.
- Create a dedicated project-local `.company-os` dogfood instance without enabling scheduling.
- Validate every command fully before persistence. A rejected transition must leave governed state and append-only event artifacts byte-for-byte unchanged.

### Excluded

- Runtime manager/worker launch, messaging, heartbeats, or cancellation propagation.
- Protected launcher or external issuer deployment.
- Distributed/Postgres state, event-log transactions, or production scheduling.
- Chippy product changes, deployment, database migration, or customer data.
- Promotion of this project-specific result into a production control plane.

## Roles and authority

- Master: this root task; owns the versioned contract and final phase decision.
- Design manager: independent Sol task; may challenge scope and acceptance but not edit implementation.
- Implementation worker: bounded Terra task; may edit only the controller, validator, their tests, and directly linked skill references.
- Acceptance reviewer: a separate Sol task; read-only and receives the contract plus resulting artifacts, not the implementer’s preferred verdict.
- Company OS under test: may propose refinements to its project-local method; it may not approve changes to its own authority boundary.

## Acceptance gates

All must pass:

1. Regression tests reproduce and then reject expired-lease execution, invalid finish/report metrics, nested/aliased scope collisions, unreviewed limit expansion, and unsigned/self-approved adaptation review.
2. Lease tests cover zero/negative TTL, expired, wrong-program, wrong-owner, and transition-not-permitted cases across every lease-authorized command, and confirm atomic rejection.
3. Metric tests cover negative values, booleans, strings, `NaN`, and infinities plus valid boundary values.
4. Scope tests cover absolute paths, traversal, aliases, duplicates, and parent/child overlap in both declaration orders.
5. Scaling tests accept exactly 2 managers / 3 workers per manager / 6 globally and reject every unreviewed overage.
6. Adaptation tests reject missing, malformed, untrusted, replayed, self-reviewed, and proposal-mismatched grants and accept only the exact independently signed review.
7. Existing controller and fabric-validator test suites pass.
8. All modified skills pass skill validation and Python compilation.
9. An independent reviewer finds no open P0/P1 defect inside Phase 1 scope.
10. The dogfood instance audits honestly: scheduling remains disabled and unavailable runtime/issuer/launcher dependencies remain explicit.
11. The ledger distinguishes implemented controls, local test evidence, dogfood evidence, and unimplemented runtime capabilities.

## Stop conditions

Stop Phase 1 on any authority regression, destructive external action, unrelated product edit, repeated unchanged failure, or inability to preserve existing user files. Do not enable a scheduler or claim operational autonomy from local tests.

## Phase 2 candidate

Only after Phase 1 acceptance: implement a real runtime adapter with attributable task identities, manager/worker receipts, provider-derived telemetry, heartbeats, cancellation propagation, and reconciliation. Phase 2 must use the same fractal contract and may not weaken Phase 1 controls.
