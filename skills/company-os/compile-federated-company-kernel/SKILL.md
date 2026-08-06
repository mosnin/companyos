---
name: compile-federated-company-kernel
description: Compile a company objective and accountable workstreams into a federated Company OS topology with durable control cells, dynamic Sol-manager capacity, Luna-max worker capacity, delegated authority, shared services, bounded admission, and explicit scale gates. Use when designing or changing a multi-department autonomous company, planning high-concurrency agent operations, replacing a centralized master bottleneck, or preparing a Company OS instance to scale beyond one supervised project.
---

# Compile Federated Company Kernel

Compile an organization; do not create a prompt hierarchy. Treat departments
and program cells as durable operating systems. Treat managers and workers as
elastic execution capacity admitted against real work.

## Required sequence

1. Start from one concrete company objective, business-unit missions, program
   outcomes, and independently accountable workstreams. For any workstream that
   may execute autonomously, include both non-empty `mandatory_requirements` and
   non-empty `acceptance_checks`; omitting either keeps the delivery contract
   incomplete and prevents autonomous design continuation.
2. Read [references/kernel-contract.md](references/kernel-contract.md).
   Use
   [references/federated-kernel-request.example.json](references/federated-kernel-request.example.json)
   as a canonical starting shape; replace its company facts and workstreams.
3. Validate the mechanism registry against the exact Source Intelligence
   Registry. Repository mechanisms are subordinate contracts, never hidden
   controllers or installation authority.
4. Compile the request:

   ```bash
   python3 scripts/compile_federated_kernel.py compile \
     --request /absolute/path/kernel-request.json \
     --output /absolute/path/federated-kernel.json
   ```

5. Verify the emitted kernel against the unchanged request and registries:

   ```bash
   python3 scripts/compile_federated_kernel.py verify \
     --request /absolute/path/kernel-request.json \
     --kernel /absolute/path/federated-kernel.json
   ```

6. Before any host launch, compile one bounded desired/observed reconciliation
   plan. The request names the current kernel generation, exact manager cells,
   per-manager and global budgets, and the last returned native-task snapshot:
   [references/federated-reconciliation-request.example.json](references/federated-reconciliation-request.example.json)
   is bound to the canonical kernel example and demonstrates the initial empty
   snapshot.

   ```bash
   python3 scripts/reconcile_federated_kernel.py plan \
     --kernel /absolute/path/federated-kernel.json \
     --request /absolute/path/reconciliation-request.json \
     --output /absolute/path/reconciliation-plan.json
   ```

   Verify that plan before an external controller consumes it:

   ```bash
   python3 scripts/reconcile_federated_kernel.py verify \
     --kernel /absolute/path/federated-kernel.json \
     --request /absolute/path/reconciliation-request.json \
     --plan /absolute/path/reconciliation-plan.json
   ```

7. Persist the verified plan into the existing project-local Company OS
   control store before any host command is claimed. This transaction retains
   the exact kernel, request, observed cursor, plan, event, idempotency result,
   and actionable command set together:

   ```bash
   python3 scripts/persist_federated_runtime.py persist \
     --project /absolute/path/company-project \
     --kernel /absolute/path/federated-kernel.json \
     --request /absolute/path/reconciliation-request.json \
     --plan /absolute/path/reconciliation-plan.json \
     --at 2026-08-05T12:00:00+00:00
   ```

   Audit retained plan replay, monotonic cursors, command completeness, lease
   fencing, hashes, and project isolation after every recovery or deployment:

   ```bash
   python3 scripts/persist_federated_runtime.py audit \
     --project /absolute/path/company-project
   ```

   Claim, settle, and cancel commands only through the lease-fenced interface.
   A claim requires a private claim token, owner, explicit expiry, and returned
   generation. Settlement must present that exact tuple. Cancellation is
   authoritative over any later settlement.

## Organizational rules

- Keep founder/board authority, company policy, portfolio allocation,
  department control, program ownership, task execution, independent quality,
  and offline learning distinct.
- Derive managers from accountable workstreams and parallel partitions. Never
  create managers merely to hit a ratio or target agent count.
- Bound a manager's direct Luna span by work complexity and uncertainty. Split
  a wide workstream into peer manager partitions under one program cell; do not
  overload one manager or invent nested prompt bureaucracy.
- Separate declared organizational capacity, admitted concurrency, observed
  utilization, and accepted throughput.
- Escalate exceptions. Do not send routine worker reports or unchanged phase
  acknowledgements to the executive kernel.
- Preserve mandatory objective and scope text byte-for-byte in the compiled
  kernel.
- Carry mandatory requirements and acceptance checks into every manager
  partition. Never infer a complete delivery contract from a broad objective,
  a feature name, or a manager's preferred implementation.
- Persist an admission intent before creation. After a create claim, reconcile
  the host listing; never issue another create merely because the caller timed
  out. Hold stale active work against capacity until cancellation or terminal
  settlement is observed.
- Treat requested model and reasoning as intent. Require returned role readback
  to confirm them; cancel on refuted drift and record inconclusive when the host
  cannot expose them.

## Mechanism boundaries

Use the repository-derived contracts in
[references/federated-mechanism-contracts.json](references/federated-mechanism-contracts.json):

- desired/observed reconciliation for host state;
- finite cell depth, reservation, adoption fencing, and wind-down capacity;
- monotonic event cursors and replay for transport;
- requested-versus-observed model readback;
- contract transition diagnostics;
- cited read-only context retrieval;
- artifact-specific independent evaluation;
- trace diagnosis and later-task learning in the offline lab.

Never import upstream schedulers, installers, mutable room state, prompt-only
permissions, worktree sandbox claims, graph authority, unbounded loops, or
self-promotion.

## Activation boundary

Compilation emits planned desired state only. It cannot launch Codex tasks,
activate a scheduler, call a provider, install a repository, allocate money,
or approve production actions. Runtime admission requires separately accepted
persistence, launcher, identity, telemetry, cancellation, and recovery
adapters.

Persistence is also not activation. `persist_federated_runtime.py` extends the
same SQLite authority already used by the Company OS controller and writes only
durable intent. It does not consume its outbox. A separately accepted native
adapter must claim commands, perform the exact host action, return observed
identity and role evidence, and settle the command. Never infer provider
success from a pending, leased, or timed-out command.

The local persistence implementation accepts only kernels whose persistence
adapter is `sqlite`. It rejects a PostgreSQL-configured kernel instead of
silently falling back to local storage.

For a PostgreSQL kernel, use the separate shared adapter. It reads the DSN only
from the environment variable named by the compiled kernel and requires
`psycopg` 3 in the host environment. Migration is explicit and never runs as a
side effect of persistence:

```bash
python3 scripts/postgres_federated_runtime.py migrate \
  --kernel /absolute/path/federated-kernel.json

python3 scripts/postgres_federated_runtime.py persist \
  --kernel /absolute/path/federated-kernel.json \
  --request /absolute/path/reconciliation-request.json \
  --plan /absolute/path/reconciliation-plan.json \
  --at 2026-08-05T12:00:00+00:00
```

After migration, an authorized database administrator must run the checked-in
bootstrap/audit boundary. It requires an existing restricted direct-login
runtime role, creates a protected definer only when explicitly requested,
binds one unique project principal, transfers the exact trusted function
surface, installs only the ten-function runtime API, and emits canonical raw
catalog evidence without printing the DSN:

```bash
python3 scripts/postgres_runtime_admin.py bootstrap \
  --dsn-env COMPANY_OS_POSTGRES_ADMIN_DSN \
  --project-id company-project \
  --runtime-role company_os_project_runtime \
  --definer-role company_os_runtime_definer \
  --target-label staging-branch-id
```

The bootstrap does not create runtime logins or passwords and cannot activate
runtime or scheduling. Repeat `audit` on every target and after every upgrade.

The PostgreSQL adapter has passed the transaction, idempotency, parallel claim,
lease recovery, cancellation, immutable-history, cross-binding, and audit
matrix on the disposable Neon branch recorded in
[references/postgresql-validation-receipt.json](references/postgresql-validation-receipt.json).
The receipt binds the machine-readable database catalog output in
[references/postgresql-admin-validation-evidence.json](references/postgresql-admin-validation-evidence.json)
and the independently replayable admin harness.
Every new target database remains blocked until its own migration and audit
complete; a library validation receipt is not target runtime evidence.

After target-database acceptance, use `$operate-federated-codex-runtime` to
consume commands through native Codex tasks. Persistence never calls task tools
and native dispatch never becomes durable by prompt text alone.

## Acceptance

Require deterministic recompilation, exact source/pin resolution, no duplicate
ownership, valid budget shares, span-of-control compliance, one authority path,
task-local capability references, an explicit scale ladder, atomic intent and
outbox commit, monotonic observation cursors, expiring generation-fenced
leases, cancellation precedence, restart audit, and exact idempotent replay.
Reject a kernel that serializes source research, capability discovery,
evaluation, and learning as sequential execution gates.
