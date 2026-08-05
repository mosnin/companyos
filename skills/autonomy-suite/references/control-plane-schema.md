# Control-plane schema

Use a durable database or equivalent transactional store. Keep agent text and untrusted external payloads separate from authority-bearing fields.

## Minimum records

| Record | Required fields |
| --- | --- |
| Task | id, parent_id, outcome, scope, risk_class, status, dependency_ids, acceptance_criteria, permission_envelope, budget, idempotency_key, version |
| Run | id, task_id, attempt, model_tier, worker_id, status, started_at, heartbeat_at, finished_at, input_version, output_artifact_ids, failure_code |
| Lease | resource_key, holder_run_id, expires_at, fencing_token |
| Approval | id, task_id, requested_action, proposed_parameters, approver, decision, expires_at, policy_version |
| Artifact | id, task_id, type, immutable_location, checksum, provenance, review_status |
| Budget | scope, token_limit, cost_limit, time_limit, concurrency_limit, consumed values |
| Event | id, aggregate_type, aggregate_id, event_type, occurred_at, actor, correlation_id, payload_reference |

## Invariants

- Transition task/run state transactionally and append an event in the same commit.
- Use leases plus fencing tokens for writers; expiration alone must not authorize stale work.
- Accept a completion only when its idempotency key, task version, lease token, and acceptance evidence are valid.
- Store approvals as signed, expiring decisions bound to exact action parameters and policy version.
- Make all external action requests replay-safe and record receipts.
- Put failed, exhausted, or manually stopped work in explicit terminal states; never discard it.

## Minimum state models

Task: `queued → ready → leased → running → verifying → accepted` or `blocked | retry_wait | needs_approval | failed | cancelled | dead_letter`.

Run: `created → started → heartbeating → succeeded` or `failed | cancelled | timed_out | superseded`.

Only the control plane may change authority-bearing state.
