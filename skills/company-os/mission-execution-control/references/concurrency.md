# Concurrency Control

Active concurrency is bounded by integration capacity. The controller reduces worker count when write collisions, integration delay, failed handoffs, or repeated rework rise. It increases worker count only when the current bottleneck can be partitioned into nonoverlapping ownership boundaries and integration throughput remains healthy.
