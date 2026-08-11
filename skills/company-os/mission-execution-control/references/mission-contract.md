# Mission Execution Contract

## Mission classes

- `quick_build`: 30 to 90 minutes, one manager, at most two workers.
- `bounded_feature`: 60 to 180 minutes, small manager tree.
- `company_mission`: 180 to 420 minutes, full executive governor.
- `long_running_company`: explicit external scheduler and persistent operational metrics.

## First Reality defaults

For a seven-hour software mission:

- repository inspection by minute 5;
- first product mutation by minute 15;
- first build or runtime command by minute 20;
- first rendered or running artifact by minute 40;
- connected R3 behavior by minute 105;
- first independent runtime review by minute 150;
- reality closure begins after 88 percent of mission time.

Other mission durations scale these deadlines within safe minimum and maximum bounds.

## Work admission

Every dispatch declares one work class. A dispatch is admissible only when the current governor decision allows that class.

Research or documentation after bootstrap additionally requires:

- `consumer_task_id`;
- `blocker_id`;
- `decision_dependency`;
- `deadline_minutes`.

Replacement of a supplied implementation additionally requires a failed integration spike receipt.

## Capability evidence

- `missing`: no valid evidence.
- `partial`: exact product bytes exist.
- `runnable`: a bound runtime receipt proves isolated execution.
- `connected`: one complete First Reality journey is proven.
- `verified`: independent evidence accepts the capability.

## Replacement

The first missed execution deadline produces an intervention. A second miss by the same task produces worker replacement. Two subordinate replacements or a failure to obey the governor produces manager replacement.

## Scheduler lease

A wake is accepted only when mission ID and generation match, the mission is active, `not_before` has passed, `expires_at` has not passed, and its idempotency key has not already been consumed.
