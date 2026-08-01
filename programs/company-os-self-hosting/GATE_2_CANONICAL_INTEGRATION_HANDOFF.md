# Gate 2 Canonical Integration Handoff

## Exact next outcome

Install the accepted observation-verification mechanics into the canonical
Company OS controller while the runtime adapter remains disabled. The
controller may store a verified observation in an attempt-scoped inbox; it may
not launch work, change lifecycle, accept a model, consume budget, reconcile a
result, or schedule another cycle.

## Required controller revision

- Advance the controller to schema `9` / core `2.6.0`. The observation inbox is
  governed state and must not be slipped into schema 8 invisibly.
- Add a distinct observation-gateway keyring configuration. Do not reuse the
  master decision issuer, actor-grant issuer, or a private key.
- Preserve the schema-8 admission record unchanged. Store task binding and
  trusted observations in a separate attempt-scoped inbox.
- Add one command: `ingest-runtime-observation`.
- Parse the incoming envelope with duplicate-key and non-finite-number
  rejection before it becomes an in-memory object.
- Revalidate every retained observation and its immutable raw artifact before
  append or exact-retry no-op.
- Persist observation state and its audit event atomically under the existing
  controller lock.
- Keep `runtime_adapter.enabled: false` and require an explicit later contract
  before any provider adapter can call this command.

## Canonical state shape

Each admitted attempt receives one feature-off observation inbox:

```json
{
  "enabled": false,
  "status": "disabled",
  "attempt_binding_digest": null,
  "bound_provider_task_id": null,
  "trusted_observations": [],
  "consumed_nonces": []
}
```

Private keys, credentials, provider tokens, and self-reported lifecycle or
telemetry do not enter state.

## Implementation order

1. Port the strict JSON, canonical hashing, keyring, signature, exact-byte,
   identity, time, replay, ordering, and retained-history checks from the
   project-local reference.
2. Add schema-9 fail-closed upgrade behavior and state-audit invariants.
3. Port every project-local adversarial case into the canonical controller
   suite and add command/event atomicity assertions.
4. Run the full controller regression, Python compilation, validator self-test,
   and official Company OS, Elastic Company OS, and Luna Execution Fabric skill
   validation.
5. Run a separate read-only Sol review focused on trust roots, mutation order,
   artifact immutability, key rotation, crash ambiguity, evidence labels, and
   feature-off guarantees.
6. Accept only with all tests green and no open P0/P1. Otherwise mark `REWORK`
   and keep schema 8 frozen.

## Mandatory additional integration tests

- A schema-8 instance upgrades fail closed with no runtime work carried over.
- The observation inbox cannot be enabled while the runtime adapter is
  disabled.
- A command rejection changes neither `control.json` nor `events.jsonl`.
- An exact retry changes neither file.
- A retained record signed by a now-retired key remains auditable; a new record
  cannot use that key.
- Removing an historical verification key or immutable raw artifact blocks
  forward ingestion instead of silently weakening auditability.
- Attempt, provider task, event, and nonce conflicts remain unique across
  restart and reload.
- No observation field can mutate attempt lifecycle, model acceptance,
  budgets, telemetry, receipts, or reconciliation.

## Still blocked after this integration

Provider launch, model-verification policy, heartbeat/liveness, cancellation,
terminal receipts, reconciliation, real Luna dogfood, Chippy forward work, and
recurring operation remain separate later gates. Canonical Gate 2 is a trust
boundary, not permission to skip them.
