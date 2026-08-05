# Company OS Phase 1B Acceptance Matrix

| Gate | Fault or substitution | Required result |
| --- | --- | --- |
| Migration | Valid schema-9 JSON; missing/corrupt/stale source; repeated migration | One exact revision or atomic rejection; repeat is no-op |
| Atomic pair | Crash before commit; commit before export; export corruption | No partial authority; committed DB wins and exports rebuild |
| Revision chain | Missing, duplicate, skipped, reordered, or hash-mismatched revision/event | Audit fails closed |
| Idempotency | Same key/same digest; same key/different digest; restart replay | Exact no-op; conflict rejects; behavior survives restart |
| Lease claim | Two processes claim the same ready project | Exactly one authoritative owner |
| Cancellation | Completion/retry after cancellation | Cancellation remains terminal and authoritative |
| Inbox | Duplicate/conflicting signed observation | One accepted message; conflict rejects atomically |
| Outbox | Duplicate key; pending/retry/terminal state | No duplicate effect intent; state is inspectable |
| Export drift | JSON/JSONL edited, deleted, or stale | Database authority unchanged; deterministic rebuild |
| Isolation | Database copied/opened under another project/root | Project binding rejects before mutation |
| Regression | Existing controller, observation, distribution, compile, validator suites | All green; runtime and scheduler remain off |

## Operator journey

1. Initialize or migrate one project.
2. Audit shows `sqlite`, the current revision, export parity, and no hidden
   pending effect.
3. Run one bounded controller command.
4. Observe one new revision and one paired event.
5. Repeat the exact command and observe no new revision.
6. Interrupt export publication, restart, and observe automatic export repair
   from committed truth.
7. Cancel and verify no later completion path can supersede it.
