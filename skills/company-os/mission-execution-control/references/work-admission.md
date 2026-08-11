# Work Admission Enforcement

Every task declares exactly one work class:

`research`, `architecture`, `governance`, `implementation`, `integration`, `runtime`, `repair`, `evaluation`, `documentation`, `packaging`, or `checkpoint`.

The current governor decision is authoritative. A task whose class is paused is rejected before dispatch.

After bootstrap, research and documentation additionally require:

```json
{
  "consumer_task_id": "task identity",
  "blocker_id": "active capability blocker",
  "decision_dependency": "decision changed by this result",
  "deadline_minutes": 15
}
```

Replacement of a supplied repository, provider, SDK, framework, or service additionally requires a failed integration spike receipt containing exact version, commands, runtime evidence, blocking incompatibility, extension analysis, and replacement cost.

A plan, report, schema, benchmark design, or audit cannot reset an execution deadline. Only exact product mutation, runnable behavior, connected behavior, independent review, or durable checkpoint evidence can do so.
