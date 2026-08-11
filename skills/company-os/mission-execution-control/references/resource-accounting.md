# Observable Resource Accounting

Use provider token and cost telemetry when available. Never invent it when unavailable.

Always track observable proxies:

- elapsed wall time;
- manager and worker tasks;
- scheduled wakes;
- source and documentation mutations;
- commands, builds, tests, services, browser renders, and runtime receipts;
- artifact bytes;
- retries, failures, and rework cycles;
- checkpoints.

Before R3, direct execution consists of implementation, integration, runtime, and repair. Default allocation targets are at least 60 percent direct execution, at most 15 percent research, 10 percent architecture, 10 percent governance, and 5 percent documentation.

The controller derives allocation from events. Manager estimates may provide context but cannot override observed activity.
