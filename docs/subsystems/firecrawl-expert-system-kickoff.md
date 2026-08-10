# Firecrawl Expert System Kickoff

Build this subsystem outside Company OS as an independently versioned domain expert project. Company OS orchestrates it through a capability contract; Company OS core must not absorb Firecrawl specific implementation logic.

## Mission

Create a professional autonomous web acquisition and document intelligence subsystem capable of selecting and executing the right strategy across search, scrape, crawl, map, structured extraction, workflow orchestration, MCP, CLI, PDF inspection, arbitrary document processing, and persistent ingestion state.

The subsystem must turn vague objectives such as "build a continuously refreshed competitor intelligence corpus", "extract all product data from this documentation estate", "research this market with citations", or "ingest these sites and PDFs into our application" into verified acquisition systems.

## Primary sources

Study and extract primitives from these repositories:

* `firecrawl/firecrawl` as the authoritative crawling and extraction implementation source.
* `firecrawl/firecrawl-workflows` for reusable multi step acquisition and transformation workflows.
* `firecrawl/skills` for agent facing Firecrawl operating knowledge and task patterns.
* `firecrawl/cli` for command line control and automation patterns.
* `firecrawl/firecrawl-mcp-server` for agent and MCP integration.
* `firecrawl/pdf-inspector` for PDF analysis and extraction patterns.
* `firecrawl/anydoc` for generalized document processing.
* `firecrawl/firecrawl-convex` for persistent application integration and ingestion state with Convex.

Do not blindly combine repositories. Map overlapping responsibilities, determine canonical sources, and build one coherent expert subsystem.

## Required expert capabilities

The final module should understand and execute:

* URL discovery and site mapping
* targeted scraping
* breadth and depth crawling
* search driven research
* structured extraction against schemas
* JavaScript rendered sites
* dynamic pages
* pagination and infinite scroll
* authentication where explicitly authorized
* rate limiting and politeness controls
* retries and backoff
* duplicate detection
* canonical URL handling
* content freshness and recrawling
* change detection
* metadata preservation
* provenance and citation binding
* markdown and structured output
* PDFs
* office and arbitrary documents where supported
* multimodal document inspection where applicable
* workflow composition
* MCP invocation
* CLI invocation
* API integration
* persistent ingestion state
* queues and resumability
* observability
* cost and credit awareness
* failure recovery
* quality evaluation
* security and prompt injection awareness

## Autonomous research

Spawn research teams to study official Firecrawl documentation, source behavior, examples, public workflow patterns, web crawling engineering, extraction benchmarks, document parsing techniques, anti bot environments, data quality, freshness strategies, retrieval pipelines, RAG ingestion patterns, crawler observability, and failure modes.

Researchers must build a structured corpus, not a pile of links.

Classify examples by objective, input type, discovery strategy, acquisition method, extraction method, output schema, pagination, rendering requirements, retries, anti bot behavior, cost, runtime, quality, provenance, freshness, persistence, and failure patterns.

## Team topology

Start with a master subsystem manager and dynamically create these lanes as required:

### Web Acquisition Research Manager

Own web crawling and scraping research, Firecrawl source intelligence, public examples, and current Firecrawl capabilities.

### Crawl Architecture Manager

Own discovery strategy, map versus crawl versus scrape decisions, breadth and depth limits, canonicalization, duplicate handling, pagination, scheduling, recrawling, concurrency, retries, and rate control.

### Extraction Manager

Own markdown extraction, structured schema extraction, content cleaning, metadata, provenance, citations, and output quality.

### Browser and Dynamic Web Manager

Own JavaScript rendered pages, interaction dependent content, dynamic loading, anti bot constraints, authentication within explicit authorization, and runtime verification.

### Document Intelligence Manager

Own PDFs and arbitrary documents using `pdf-inspector`, `anydoc`, and related patterns. Handle document classification, extraction, tables, sections, metadata, and validation.

### Workflow Manager

Own reusable Firecrawl workflows and multi stage acquisition pipelines using patterns from `firecrawl-workflows`.

### Agent Interface Manager

Own MCP and CLI integration using `firecrawl-mcp-server`, `cli`, and `skills`. Expose a stable capability contract to Company OS and other agents.

### Persistent Ingestion Manager

Own durable crawl jobs, ingestion state, deduplication, freshness, change tracking, and Convex integration where useful using `firecrawl-convex` as a source reference.

### Validation and Evaluation Manager

Independently verify actual acquired content, schema correctness, coverage, provenance, citation fidelity, duplicate rate, freshness, extraction quality, and failure recovery.

### Security Manager

Review prompt injection in fetched content, unsafe URLs, SSRF style risks, credential handling, authenticated crawl boundaries, secret exposure, malicious documents, untrusted HTML, dangerous downloads, and data exfiltration risks.

## Engineering constitution

Every manager and worker inherits the Company OS Engineering Execution Constitution. Children may strengthen but not weaken requirements. One writer per resource boundary. Required skills accumulate. Runtime observation and independent review are mandatory where applicable.

## Seven hour autonomous window

Run autonomously for approximately seven hours or until reality acceptance passes. Do not consume seven hours merely because the budget exists. Do not stop after the first implementation while material capability gaps remain.

Use dynamic scheduling rather than one fixed heartbeat.

Suggested initial scheduler policy:

* active implementation or debugging: inspect in roughly 3 to 7 minutes
* focused research: roughly 8 to 15 minutes
* long crawl, benchmark, or environment job: roughly 10 to 20 minutes
* critical failing evaluator: shorten wakeup
* slow external dependency: lengthen that lane while keeping other lanes productive

Scheduler inputs should include task age, recent progress, expected completion, worker health, manager health, failure severity, dependency state, remaining time, remaining cost, remaining tokens, pending evaluation, bottleneck severity, and stagnation.

The master heartbeat must remain independent of subordinate schedules so the organization cannot silently go dormant.

## First vertical slice

Before broadening the platform, prove one complete autonomous loop:

vague acquisition objective
→ research
→ strategy selection
→ Firecrawl capability selection
→ real acquisition
→ extracted artifact
→ provenance
→ independent evaluation
→ gap diagnosis
→ targeted repair
→ reacquisition
→ reality acceptance

Only after this works should the subsystem expand.

## Benchmark suite

Before acceptance, use the same autonomous pipeline against unseen objectives including at least:

1. A documentation site requiring map plus targeted crawl.
2. A JavaScript heavy site requiring rendered extraction.
3. A multi page structured dataset extraction task.
4. A PDF heavy research task.
5. A mixed web plus document ingestion task.
6. A recurring freshness or change detection task.
7. A research task requiring source provenance and citations.
8. A workflow requiring persistent state and resumability.

Track coverage, precision, duplicate rate, extraction correctness, citation fidelity, runtime, credits or cost, retries, failures, iterations, and human interventions.

## Completion standard

Do not accept the subsystem because API calls succeed, markdown exists, tests pass, or an agent reports completion.

Accept only when fresh vague objectives can be converted autonomously into professional web acquisition or document intelligence results with verified content quality, provenance, operational robustness, and the strongest available runtime evidence.

## Company OS interface

Company OS should know only that this expert module exists, its advertised capabilities, required authority, invocation interface, persistent task identity, status interface, evidence interface, and output contract.

The Firecrawl module remains independently maintainable and independently versioned outside Company OS.
