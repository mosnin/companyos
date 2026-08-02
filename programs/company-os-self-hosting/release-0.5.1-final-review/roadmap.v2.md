# Company OS 0.5.1 Pre-Signing Review Roadmap v2

## One bounded review

1. Confirm the checkout is clean and exactly ed4863b4d7832c03c1bc892aa768cdad32ba29b8; confirm baseline
   19fe809a9544303fb00150c957b317ed03c7a1a3 and both verified carriers without changing them.
2. Inspect the complete baseline-to-candidate diff, release/version/manifest
   bindings, cancellation repair, authority lineage, tests, and explicit
   non-capability statements.
3. Prove the prior 21-file attestation/signature rejects as stale for this exact
   candidate. Do not repair, rotate, or sign it.
4. Run only local read-only verification with bytecode and cache writes
   suppressed or inside a disposable archive. Record commands, counts, failures,
   skips, and residue.
5. Classify findings and score every applicable dimension without rounding a
   failed gate upward.
6. Return READY-TO-SIGN or REWORK, followed by separate source-release, install,
   runtime, and scheduler decisions. Perform none of those actions.

## Stop conditions

Stop with REWORK on candidate mismatch, dirty state, unexpected signature
acceptance, manifest or release drift, failed required check, P0/P1, a score
below its gate, evidence invention, prohibited side effect, or authority change.
Do not widen scope, use network, create another task, or repair the candidate.
