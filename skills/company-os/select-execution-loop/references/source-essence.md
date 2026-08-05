# Curated source essence

Observed 2026-08-05. These revisions are research inputs, not vendored runtime
dependencies.

| Source | Pinned revision | Mechanism retained | Boundary |
| --- | --- | --- | --- |
| Forward Future Loopy | `75966cbd572a4185064971c9fe5e9c52e8f8456d` | Observe, choose, act, verify, record, then stop on finite terminal states; debrief receipts before changing a loop | MIT; catalog prompts remain untrusted reference data |
| context-labs HALO | `0b68141633c14f488461aaecdf91a739a411f05d` | Hierarchical trace inspection, subanalysis, synthesis, prompt compaction, and production-trace bottleneck diagnosis | Repository advertises MIT but the pinned root has no license file ([issue 34](https://github.com/context-labs/HALO/issues/34)); provider routing and small-corpus completion also have reported failures ([issues 81](https://github.com/context-labs/HALO/issues/81) and [41](https://github.com/context-labs/HALO/issues/41)); no code copied |
| plasma-ai Fractal | `73ce05adcd73d52c69afb394447d7ab95880d321` | Recursive node trees, isolated Git worktrees, explicit lifecycle, central event/cost database, parent-child messaging, and growth caps | External runtime not installed; stale-file/node-seed merge risks and writes outside worktrees remain open upstream ([issues 9](https://github.com/plasma-ai/fractal/issues/9) and [6](https://github.com/plasma-ai/fractal/issues/6)) |
| aeonfun Aeon | `463b642a5c6e314d4abccf66e3950aa5b3e70c8d` | Scheduled skills, health checks, persistent memory, frequency guards, evaluation, repair proposals, and operator scorecards | Unattended self-modification and broad integrations require independent approval; repository redirect resolved to `aeonfun/aeon` |
| valkor-ai Loom | `32f80926ac11ae514342401c6eeaae1fb860656a` | Contract-first delivery from confirmed scope through architecture, task execution, evidence, review, and runtime closure | Large delivery harness; use progressive disclosure instead of loading its corpus |
| disler Infinite Agentic Loop | `6e9a012f81ef2291faf174d67176f7e69832cc0a` | Parallel divergent generation with prior-output context used to increase variation | Experimental prompt project with no repository license ([issue 4](https://github.com/disler/infinite-agentic-loop/issues/4)); no code copied; converted to finite exploration with held-out acceptance |
| Agent Apprenticeship | `4beafff2ff41da7d97a4faee9b516ccde466fb4b` | Structured traces, mentor checkpoints, evaluation, revision, lesson extraction, and experience compilation | Learning artifacts cannot approve the run that produced them |
| Durable Streams | `a172acc389351cb3db6deb5cd60e3dec11e7ff39` | Append-only ordered streams, resumable offsets, idempotent producers, forks, subscriptions, generation fencing, claims, heartbeats, acks, and replay | Event substrate, not a planner or manager loop; open offset and close-propagation defects prevent treating current clients as accepted infrastructure without conformance tests ([issues 397](https://github.com/durable-streams/durable-streams/issues/397) and [398](https://github.com/durable-streams/durable-streams/issues/398)) |

## Company OS synthesis

The catalog separates four planes:

1. **Iteration:** bounded evidence, phase delivery, recursive delivery,
   exploration, or recurring operations.
2. **Diagnosis:** trace optimization observes a run and proposes the next test.
3. **Learning:** apprenticeship compiles independently reviewed experience for
   later runs.
4. **Transport:** durable event reaction preserves ordered, replayable wake and
   progress evidence.

Only the iteration plane chooses the next action. This prevents nested tools
from becoming competing orchestrators.
