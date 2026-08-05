# Company OS Observatory

The observatory answers one operating question: **is Company OS producing more
accepted business value with less supervision, cost, drift, and rework over
time?** It records real work and simulations through the same contract, while
keeping their comparison classes distinct.

## Architecture

```text
Company OS run
  -> canonical execution-efficiency receipt
  -> local schema and semantic validator
  -> content-bound ingestion statement
  -> operator-supplied Postgres connection
  -> immutable evidence + normalized dimensions
  -> scorecard and comparison trend views
  -> smallest useful framework change
  -> materially different real program
```

The framework owns the receipt schema, validator, migrations, and queries. The
operator owns the database account, retention, backup, access policy, and
connection mechanism. The SQL uses standard PostgreSQL plus `pgcrypto`; it does
not require a provider-specific API. A user can host it on Neon, Supabase,
RDS/Aurora PostgreSQL, Cloud SQL, or a self-managed PostgreSQL service that
permits `pgcrypto`.

## Evidence lifecycle

1. Freeze mandatory requirements, artifact identities, authority, capability
   needs, topology, budgets, and expected telemetry before dispatch.
2. Capture observed—not merely requested—managers, workers, model/effort,
   concurrency, timing, usage, artifacts, collisions, and acceptance.
3. Validate the receipt locally. An unavailable metric stays unavailable and
   cannot produce a green gate.
4. Render deterministic ingestion SQL. The receipt is canonicalized, SHA-256
   bound, and base64-carried so client text is not exposed in ordinary SQL
   review output.
5. Ingest once. Replaying the same hash is idempotent.
6. Correct an earlier record only by ingesting a new receipt whose
   `supersedes_receipt_sha256` points at the current receipt for that run.
7. Compare only like-for-like `comparison_class` cohorts. Do not average a
   website build with a proposal package and call the result an efficiency
   trend.

The database rejects update/delete attempts on the principal evidence tables.
Framework changes and failure relationships are stored separately so a score
change can be tied to the hypothesis that caused it.

## Installation contract

Run these migrations in order through an already-authorized PostgreSQL
connection:

```text
sql/001_company_os_observatory.sql
sql/002_ingest_execution_efficiency_receipt.sql
```

Use a dedicated database when practical, otherwise use the dedicated
`company_os_observatory` schema. The migration role needs permission to create a
schema, tables, functions, triggers, views, and the `pgcrypto` extension. The
runtime ingestion role should receive only the minimum function/schema rights
needed by the operator; it does not need ownership of the database.

Never commit or print a database URL. Never place API keys, passwords, customer
exports, ad credentials, or full private documents into a receipt. For sensitive
artifacts, retain the stable provider ID, hash, acceptance result, and restricted
evidence reference.

## Ingestion

Example renderer invocation:

```bash
python3 scripts/render_execution_efficiency_ingest.py receipt.json \
  --workspace-id operator-company-os \
  --workspace-name "Operator Company OS" \
  --project-id client-program \
  --project-name "Client Program" \
  --run-id client-program-2026-08-04-01 \
  --framework-version-id company-os-<commit> \
  --framework-source-commit <full-commit> \
  --source-thread-id <task-id>
```

Send the generated statement to the approved database client. For a reworked
receipt of the same run, add `--supersedes-receipt-sha256 <current-hash>`.

## Decision queries

Current evidence for one run:

```sql
SELECT *
FROM company_os_observatory.run_scorecard
WHERE run_id = $1;
```

Like-for-like trend:

```sql
SELECT *
FROM company_os_observatory.comparison_trends
WHERE workspace_id = $1
  AND project_id = $2
  AND comparison_class = $3
ORDER BY observed_day;
```

Open material failures:

```sql
SELECT severity, code, summary, opened_at
FROM company_os_observatory.run_failures
WHERE run_id = $1 AND status = 'open'
ORDER BY CASE severity
  WHEN 'p0' THEN 0 WHEN 'p1' THEN 1 WHEN 'p2' THEN 2 ELSE 3 END,
  opened_at;
```

## Scale gate

Database availability does not authorize higher concurrency. Increase manager
or worker fan-out only after at least three comparable accepted runs show all of
the following:

- at least 85% first-pass artifact acceptance;
- less than 20% rework;
- zero write collisions and duplicate artifacts;
- observed Luna/max labor with at least 70% of measured execution tokens;
- at least 40% fewer Sol tokens than the single-thread baseline;
- no lead-time regression;
- complete mandatory-requirement and capability-application closure;
- independently proven cancellation and recovery for the relevant runtime.

If telemetry is missing, fix instrumentation before scaling. If output is fast
but rejected, improve scope fidelity and capability routing before adding more
agents.
