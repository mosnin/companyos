# n8n Expert Subsystem Kickoff

## Objective

Build a standalone Company OS compatible subsystem that can autonomously research, design, generate, validate, deploy, inspect, repair, and improve professional n8n workflows from vague user objectives. The subsystem must live outside the Company OS core repository as its own project and be invoked only when Company OS classifies work as n8n automation engineering.

The subsystem must support long running autonomous execution for approximately seven hours without depending on one chat session remaining open. It must use persistent state, dynamically scheduled wakeups, manager check ins, heartbeats, resumable work, and evidence based acceptance.

## Required source repositories

Study and clone these sources into a project local research directory. Treat them as reference implementations and evidence, not as blindly trusted code.

1. https://github.com/czlonkowski/n8n-skills.git
2. https://github.com/czlonkowski/n8n-mcp-cc-buildier.git
3. https://github.com/czlonkowski/n8n-validation-benchmark.git
4. https://github.com/czlonkowski/n8n-manager-for-ai-agents.git
5. https://github.com/n8n-io/n8n.git

Also research current official n8n documentation, node documentation, community workflow examples, public workflow repositories, integration examples, error handling patterns, credential patterns, scaling guidance, queue mode, webhook behavior, retries, idempotency, subworkflows, expressions, code nodes, AI nodes, observability, versioning, testing, and security. Researchers should gather representative real workflows from public sources and classify them by domain, complexity, architecture pattern, node family, failure mode, and quality level.

## System role

This is not a generic n8n template generator. It is an n8n domain expert runtime.

Input examples:

"Build an automation that enriches inbound leads, scores them, routes qualified leads to the right salesperson, creates the CRM record, alerts Slack, and retries safely when vendors fail."

"Build a production workflow that ingests support emails, classifies them with AI, checks customer data, drafts responses, escalates risky tickets, and records every decision."

Expected behavior:

1. Interpret the business outcome.
2. Research unfamiliar integrations and current n8n capabilities.
3. Find comparable high quality workflows and patterns.
4. Produce an explicit workflow architecture.
5. Resolve exact nodes, node versions, credentials, expressions, data contracts, retry behavior, failure behavior, observability, and security boundaries.
6. Generate a real importable n8n workflow.
7. Validate its JSON and node configuration.
8. Run or simulate it in an isolated n8n environment when credentials or external systems permit.
9. Inspect execution results and logs.
10. Diagnose defects.
11. Repair the workflow.
12. Repeat until independent validation accepts it.

## Team topology

The master manager owns the original outcome and the seven hour autonomous run. It must create and continuously reconfigure subordinate teams based on bottlenecks.

Initial teams:

### Domain research manager

Researchers investigate official n8n behavior, current node capabilities, public workflow examples, integration specific constraints, and professional implementation patterns. Research output must include source provenance and reusable pattern extraction.

### Workflow architecture manager

Owns trigger strategy, workflow boundaries, subworkflow decomposition, data contracts, credential boundaries, state, idempotency, retries, dead letter behavior, rate limits, concurrency, queue mode considerations, observability, error workflows, and operational recovery.

### Node and expression specialist manager

Resolves exact n8n nodes, versions, operations, parameters, expressions, item linking semantics, binary data behavior, Code node usage, AI node usage, and unsupported edge cases.

### Workflow implementation manager

Builds actual n8n workflow JSON and supporting configuration. Workers must have exclusive write ownership over workflow boundaries.

### Validation manager

Uses the validation benchmark and n8n validation tooling to check structural validity, node configuration, expressions, references, required parameters, credentials, and importability. Validation agents are independent of implementation agents.

### Runtime verification manager

Runs disposable local n8n instances or other safe test environments, imports workflows, executes representative fixtures, inspects run history and errors, validates side effects, and records evidence. Source JSON alone cannot establish completion.

### Quality and pattern evaluator

Compares the candidate against high quality reference workflows and scores maintainability, clarity, robustness, decomposition, error handling, idempotency, observability, performance, security, and professional n8n idioms.

### Security manager

Reviews credential exposure, unsafe Code node behavior, webhook authentication, injection risks, data leakage, overly broad permissions, secret storage, external calls, and destructive operations. Any live external effect must remain inside explicit authority.

### Integration manager

Owns final assembly, regression checks, import and export reproducibility, documentation generation, and handoff artifacts.

## Recursive engineering constitution

Every manager and worker must inherit the Company OS Engineering Execution Constitution. Child managers may strengthen requirements but never weaken them. Required skills and verification gates accumulate down the hierarchy.

Every coding worker must have:

1. Explicit parent objective binding.
2. Bounded write scope.
3. Required skill bindings.
4. Verification intent.
5. Artifact evidence requirements.
6. Stop condition.
7. Runtime observation requirement where execution is possible.
8. Independent review requirement.

No worker completion narrative is acceptance evidence.

## Dynamic scheduler

Do not use one fixed polling interval for the entire run. The master manager owns a scheduler policy that adapts to task duration and uncertainty.

Suggested initial policy:

* Active implementation task expected under 15 minutes: manager wakeup every 5 minutes.
* Research or validation task expected 15 to 45 minutes: wakeup every 10 minutes.
* Long integration, environment setup, or benchmark task: wakeup every 15 minutes.
* Blocked task with external dependency: back off to 20 to 30 minutes while another productive lane is scheduled.
* Critical failing validation or runtime gate: shorten wakeup to 3 to 5 minutes until the failure is triaged.

At every wakeup the responsible manager must inspect machine readable state and evidence, not merely ask the worker for a status narrative.

The scheduler must dynamically recompute the next wakeup from:

* active task count
* expected completion time
* failure state
* bottleneck severity
* remaining budget
* unresolved dependencies
* evaluator queue
* integration queue
* recent progress rate

The master manager must maintain an independent heartbeat ensuring the whole project cannot become dormant while unfinished work remains.

The seven hour target is a maximum autonomous execution window, not an excuse to consume the full budget. Finish early if the outcome passes reality acceptance. If the window ends before acceptance, persist exact state, blockers, artifacts, evidence, and the next executable action so another run resumes without reconstructing context.

## Research corpus

Create a project local corpus under a path such as `research/workflows/`.

Researchers must collect public sample workflows from official n8n sources, GitHub, public template collections, technical articles where redistribution permits, and other credible sources. Preserve source URLs and licenses. Do not copy restricted material into the project when licensing does not permit it. Metadata and learned patterns may still be recorded.

Normalize examples into a searchable catalog containing at least:

* source
* title
* use case
* trigger type
* integrations
* node types
* node count
* branching complexity
* subworkflow use
* retry strategy
* error strategy
* idempotency pattern
* state pattern
* credential pattern
* AI usage
* observability pattern
* deployment assumptions
* quality notes
* known defects

Use the corpus to create positive, middle, and negative quality anchors so evaluators learn the difference between merely valid n8n JSON and professional workflow engineering.

## Knowledge model

The finished subsystem should maintain reusable domain knowledge rather than researching the same concepts on every invocation.

Create structured registries for:

* node capabilities
* node versions
* common integration recipes
* expression patterns
* pagination patterns
* batching patterns
* retry patterns
* idempotency patterns
* webhook patterns
* authentication patterns
* error workflow patterns
* subworkflow patterns
* queue and scaling patterns
* AI workflow patterns
* testing patterns
* security patterns
* known n8n pitfalls

Every registry entry needs provenance, freshness information, and confidence. Current official documentation outranks stale examples when conflicts exist.

## Workflow artifact contract

A completed workflow package should include as applicable:

* importable workflow JSON
* referenced subworkflow JSON
* credential requirements without secrets
* environment variable requirements
* test fixtures
* execution scenarios
* expected outputs
* error scenarios
* retry expectations
* deployment notes
* observability notes
* security notes
* validation receipts
* runtime execution receipts
* quality evaluation receipts

## Validation and reality acceptance

A workflow is not complete because JSON parses or because n8n accepts the import.

Acceptance should progressively prove:

1. JSON and schema validity.
2. Exact node and parameter validity.
3. Expression and reference validity.
4. Importability into the target n8n version.
5. Expected execution against representative fixtures.
6. Error path behavior.
7. Retry and idempotency behavior where required.
8. Correct interaction with integrations using mocks, sandboxes, or explicitly authorized credentials.
9. Security boundaries.
10. Professional maintainability and architecture.
11. Satisfaction of the original user outcome.

The final evaluator must receive the original objective and actual workflow evidence without relying on the production team's completion narrative.

## Autonomous improvement loop

The subsystem must run:

objective -> research -> benchmark -> architecture -> build -> validate -> execute -> observe -> evaluate -> diagnose -> targeted repair -> reexecute -> reality acceptance

When a dimension passes, preserve it. Focus rework on the dominant failing constraint. If the same dimension stagnates across repeated iterations, reorganize the team, change strategy, acquire additional examples or capabilities, or challenge the architecture rather than repeatedly polishing the same implementation.

## First seven hour build mission

Use Company OS itself to build this subsystem in a completely separate project folder. The first run should not merely write documents. It must leave a functioning n8n expert system with executable components, tests, a research corpus pipeline, validation tooling, runtime integration, autonomous scheduling, persistent project state, and at least several end to end benchmark workflows proving it can take vague objectives and produce validated workflow packages.

The master manager should create its own roadmap after inspecting the source repositories and current n8n ecosystem. It may revise the initial team topology when evidence supports a better organization.

During the build, maintain scheduled wakeups for every active manager and an independent master heartbeat. Continuously spawn additional researchers or specialists when unresolved domain uncertainty becomes the bottleneck. Reduce concurrency when integration conflicts become the bottleneck.

Do not declare success from test counts, file counts, manager reports, or token expenditure. Success means the subsystem can independently produce professional n8n workflows from new objectives and demonstrate that capability through real evidence.
