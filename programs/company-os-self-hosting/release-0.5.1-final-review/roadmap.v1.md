# Company OS 0.5.1 Final Release Review Roadmap v1

## One bounded review

1. Confirm the checkout is clean and exactly
   `ca09765716f468f37916d546c636286060ae616c`; confirm baseline
   `19fe809a9544303fb00150c957b317ed03c7a1a3` exists without changing either.
2. Inspect the complete candidate diff, release/version/manifest bindings,
   detached signed 21-file surface, authorization lineage, runtime/controller
   source, tests, and explicit non-capability statements.
3. Run only local read-only verification with bytecode and cache writes
   disabled or in an isolated temporary copy. Record exact commands, counts,
   failures, skips, and residue.
4. Classify findings by P0, P1, P2, and lower severity. Score security,
   authority, durability, cancellation, evidence integrity, and every other
   applicable review dimension without rounding a failed gate upward.
5. Return three separate decisions to the parent task: source release,
   install permission, and runtime/scheduler permission. Do not perform any of
   those downstream actions.

## Stop conditions

Stop and report `REWORK` on candidate mismatch, dirty state, invalid signature,
manifest or release drift, failed required test, P0/P1 finding, score below its
gate, evidence invention, prohibited side effect, or authority change. Stop and
report the gap rather than widening scope, using network, creating another task,
or repairing the candidate.
