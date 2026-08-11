# Mission Finalization

Acceptance, cancellation, fatal blocker, budget exhaustion, or expiration finalizes the mission.

Finalization revokes the scheduler generation, prevents new dispatches, reconciles active and queued tasks, records the strongest durable checkpoint, distinguishes accepted and quarantined bytes, and emits one compact final report.

A final report cannot promote unverified behavior. It must state the highest proven Reality Level.
