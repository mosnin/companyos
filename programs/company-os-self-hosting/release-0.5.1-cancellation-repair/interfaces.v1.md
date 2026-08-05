# Company OS 0.5.1 Cancellation Repair Interfaces v1

## Manager input

- Project/program: `company-os-self-hosting`
- Program version: `6`
- Rejected candidate: `722f5e5bf706d1dd1a48dfbcfacddfff269b7eb1`
- Rejected tree: `dd164733eb9b970792960566080048e8b567dd01`
- Rejected review task: `019fc2f8-0465-7db2-9323-762f0537e42c`
- Requested manager model: `gpt-5.6-sol`
- Future workers: at most two disjoint `gpt-5.6-luna` packets using global
  `$execute-bounded-task`, only after authenticated design approval

Requested and observed model identity remain separate. Host, token, cost,
cancellation acknowledgement, provider, and runtime evidence remain
unavailable unless independently exposed; this source repair cannot create it.

## Cancellation transition contract

`hard_cancellation_observed` accepts only:

- `hard_status=acknowledged`, `acknowledgement_status=acknowledged`;
- `hard_status=refused`, `acknowledgement_status=not_acknowledged`;
- `hard_status=failed`, `acknowledgement_status=not_acknowledged`.

The other three values in the 3×2 cross-product raise the domain error before
event append or durable mutation. Audit and replay independently apply the same
rule to retained evidence. Exact event payloads and canonical digests remain
bound to ordered authority history.

The projection exposes requested intent, cooperative delivery, hard outcome,
and acknowledgement separately. Only explicit host-observed
`acknowledged/acknowledged` produces `cancel_acknowledged`. Refused and failed
remain non-acknowledged outcomes requiring truthful reconciliation/reporting;
they do not become terminal cancellation or permit post-cancel success/failure.

## Required test interface

Table-driven tests exercise all three legal and all three illegal pairs through:

1. direct transition and derived projection;
2. persisted store round-trip and audit;
3. controller command and transactional no-mutation rejection;
4. retained event replay, including contradictory state-only and event-payload
   injection.

Focused regressions prove cancellation dominance, cooperative-stop hard-ack
non-invention, authority payload binding, downgrade rejection, and ambiguous
restart no-relaunch. The manager records exact focused and full-suite commands,
counts, failures, skips, and ignored residue.

## Ownership and reports

Manager and Luna writes are limited to the exact lowercase owned paths in the
charter. `README.md` and `programs/company-os-self-hosting/LEDGER.md` are
master-owned post-worker corrections. They must be complete before fresh
signing/review but are not manager or Luna deliverables.

At charter, discovery, design, execution, verification, and integration, the
manager reports contract/ID bindings, artifacts and digests, worker task
dispositions, exact tests, scope/prohibition compliance, variance, risks,
observable elapsed time, unavailable telemetry, the authenticated decision
reference at barriers, and one next action to
`task:019fa4e9-cd80-7bd2-9416-c8dce5a7e8c3`.

The verification receipt identifies the unsigned repair commit/tree, manifest
digest, expected stale prior signature, severity findings, and scores. It must
not claim signing, installation, provider execution, runtime/scheduler
activation, production effects, or Chippy action.
