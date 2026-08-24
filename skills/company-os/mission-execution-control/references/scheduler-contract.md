# Scheduler Lease Contract

Every autonomous mission has exactly one active scheduler lease.
The lease is part of sealed mission state: `mission_id`, `generation`,
`started_at`, and `expires_at` must match the mission, `wake_count` must
equal the unique consumed wake keys, and a terminal mission must revoke
the lease. A drifted lease cannot mint or admit a wake.

Required mission fields:

```json
{
  "mission_id": "stable identity",
  "generation": 1,
  "started_at": "RFC3339 UTC",
  "expires_at": "RFC3339 UTC",
  "owner_id": "scheduler owner",
  "max_wakes": 64,
  "wake_count": 0,
  "status": "active"
}
```

Every wake is admitted only when mission ID and generation match the active lease, `not_before` has passed, `expires_at` has not passed, the expected director state still matches, and its idempotency key has not already been consumed.

Acceptance, cancellation, fatal failure, budget exhaustion, or expiration revokes the generation, prevents new wakes, and reconciles queued and active work before final reporting.
