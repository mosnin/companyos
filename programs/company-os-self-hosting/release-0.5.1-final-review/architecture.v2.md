# Company OS 0.5.1 Pre-Signing Review Architecture v2

## Review identity

This package authorizes one independent, read-only Sol review of repaired release
candidate ed4863b4d7832c03c1bc892aa768cdad32ba29b8 against canonical baseline 19fe809a9544303fb00150c957b317ed03c7a1a3. The manifest-exact
implementation is 1e489780e6587a38c36e6e4bb38042dd8ed03835 and its manager verification carrier is
a79fb8c37af674cbdd0609d5bc349145aebe5c8d.

The reviewer may inspect repository bytes and run local tests that do not write
repository or external state. The reviewer must not edit, sign, commit, create a
task, install, activate, deploy, use network or provider services, enable
scheduling, access credentials, or touch Chippy.

## Evidence boundaries

1. Pre-signing evidence covers the exact candidate, manifest, repair report,
   release metadata, authority lineage, tests, repository residue, and expected
   rejection of the prior stale 21-file signature.
2. READY-TO-SIGN authorizes no signing by itself. It only permits the master to
   consider a separately chartered key-rotation/signing stage.
3. Source release remains NO-GO until a fresh externally signed surface and
   final independent review bind the exact final carrier.
4. Installation, runtime, and scheduler are separate decisions. Source or local
   tests cannot prove installation, host execution, provider identity,
   cancellation acknowledgement, telemetry, recovery, or scheduling.

Requested model gpt-5.6-sol is not observed-model evidence. Any unavailable
model, token, cost, host, cancellation, or provider observations remain
unavailable.

## Decision gates

READY-TO-SIGN requires the exact clean candidate and baseline, verified
implementation/evidence lineage, expected stale-signature rejection, all
non-signature checks green, zero P0/P1, critical dimensions at least 9.0, and
all other applicable dimensions at least 8.0. Otherwise the result is REWORK.

Source release, installation, runtime, and scheduler remain denied in this
pre-signing phase. No downstream action is performed.
