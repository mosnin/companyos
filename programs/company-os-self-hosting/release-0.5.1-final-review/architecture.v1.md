# Company OS 0.5.1 Final Release Review Architecture v1

## Review identity

This package authorizes one independent, read-only Sol review of release
candidate `ca09765716f468f37916d546c636286060ae616c` against canonical baseline
`19fe809a9544303fb00150c957b317ed03c7a1a3` for project and program
`company-os-self-hosting`, program version 6.

The reviewer may inspect repository bytes and run local tests that do not write
repository or external state. The reviewer must not edit, sign, commit, install,
activate, deploy, use network or provider services, enable scheduling, or touch
Chippy. Local test output is source evidence only.

## Evidence boundaries

The review keeps these claims separate:

1. Source-release evidence covers the exact committed candidate, manifest,
   signed surface, release metadata, tests, and repository residue.
2. Install permission is a separate decision about whether a later authorized
   actor may attempt a transactional install. The reviewer does not install.
3. Runtime and scheduler permission is a separate decision. Source, signature,
   manifest, or local-test success cannot prove host execution, cancellation,
   restart recovery, provider identity, telemetry, protected-launcher readiness,
   or scheduler safety.

Requested model `gpt-5.6-sol` is not observed model evidence. Unavailable model,
token, cost, host, cancellation, and provider observations remain unavailable.

## Decision gates

Source release may be accepted only when the exact candidate and baseline are
confirmed, required verification is green, there are no open P0 or P1 findings,
security, authority, durability, cancellation, and evidence integrity each
score at least 9.0/10, and every other applicable dimension scores at least
8.0/10.

Install permission may be allowed only as a distinct, reversible next-step
permission after source acceptance and after the reviewer verifies manifest,
transactional installation, parity, rollback, and residue gates from source.
It never records an install as performed.

Runtime and scheduler permission must remain denied unless separately governed
live evidence proves every required host, cancellation, restart, authority, and
scheduler control. This read-only review cannot create that evidence and must
not infer it from the release candidate.
