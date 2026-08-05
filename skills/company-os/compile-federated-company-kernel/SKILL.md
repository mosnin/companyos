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
   outcomes, and independently accountable workstreams.
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

## Acceptance

Require deterministic recompilation, exact source/pin resolution, no duplicate
ownership, valid budget shares, span-of-control compliance, one authority path,
task-local capability references, and an explicit scale ladder. Reject a
kernel that serializes source research, capability discovery, evaluation, and
learning as sequential execution gates.
