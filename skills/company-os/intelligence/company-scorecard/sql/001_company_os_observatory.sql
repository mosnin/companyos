BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS company_os_observatory;

CREATE TABLE IF NOT EXISTS company_os_observatory.schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS company_os_observatory.workspaces (
    workspace_id text PRIMARY KEY CHECK (workspace_id ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    name text NOT NULL CHECK (btrim(name) <> ''),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS company_os_observatory.projects (
    workspace_id text NOT NULL REFERENCES company_os_observatory.workspaces(workspace_id),
    project_id text NOT NULL CHECK (project_id ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    name text NOT NULL CHECK (btrim(name) <> ''),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (workspace_id, project_id)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.framework_versions (
    framework_version_id text PRIMARY KEY CHECK (framework_version_id ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    source_commit text,
    distribution_manifest_sha256 text CHECK (
        distribution_manifest_sha256 IS NULL
        OR distribution_manifest_sha256 ~ '^[0-9a-f]{64}$'
    ),
    notes text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS company_os_observatory.program_runs (
    run_id text PRIMARY KEY CHECK (run_id ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    workspace_id text NOT NULL,
    project_id text NOT NULL,
    framework_version_id text NOT NULL REFERENCES company_os_observatory.framework_versions(framework_version_id),
    program_id text NOT NULL CHECK (program_id ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    comparison_class text NOT NULL CHECK (comparison_class ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    source_thread_id text,
    opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    closed_at timestamptz,
    FOREIGN KEY (workspace_id, project_id)
        REFERENCES company_os_observatory.projects(workspace_id, project_id),
    CHECK (closed_at IS NULL OR closed_at >= opened_at)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.run_receipts (
    receipt_sha256 text PRIMARY KEY CHECK (receipt_sha256 ~ '^[0-9a-f]{64}$'),
    run_id text NOT NULL REFERENCES company_os_observatory.program_runs(run_id),
    schema_id text NOT NULL CHECK (btrim(schema_id) <> ''),
    status text NOT NULL CHECK (status IN ('accepted', 'rework', 'blocked', 'failed')),
    supersedes_receipt_sha256 text UNIQUE
        REFERENCES company_os_observatory.run_receipts(receipt_sha256),
    raw_receipt jsonb NOT NULL CHECK (jsonb_typeof(raw_receipt) = 'object'),
    validation_result jsonb NOT NULL CHECK (jsonb_typeof(validation_result) = 'object'),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS run_receipts_run_recorded_idx
    ON company_os_observatory.run_receipts(run_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS company_os_observatory.run_requirements (
    receipt_sha256 text NOT NULL REFERENCES company_os_observatory.run_receipts(receipt_sha256),
    requirement_id text NOT NULL CHECK (requirement_id ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    statement text NOT NULL CHECK (btrim(statement) <> ''),
    source text NOT NULL CHECK (btrim(source) <> ''),
    mandatory boolean NOT NULL,
    result_status text NOT NULL CHECK (result_status IN ('satisfied', 'unsatisfied', 'unknown')),
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'array'),
    PRIMARY KEY (receipt_sha256, requirement_id)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.run_lanes (
    receipt_sha256 text NOT NULL REFERENCES company_os_observatory.run_receipts(receipt_sha256),
    lane_id text NOT NULL CHECK (lane_id ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    outcome text NOT NULL CHECK (btrim(outcome) <> ''),
    manager_task_id text,
    PRIMARY KEY (receipt_sha256, lane_id)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.run_tasks (
    receipt_sha256 text NOT NULL REFERENCES company_os_observatory.run_receipts(receipt_sha256),
    task_id text NOT NULL,
    parent_task_id text,
    role text NOT NULL CHECK (role IN ('master', 'manager', 'worker')),
    lane_ids jsonb NOT NULL CHECK (jsonb_typeof(lane_ids) = 'array'),
    requested_model text,
    requested_effort text,
    observed_model text,
    observed_effort text,
    PRIMARY KEY (receipt_sha256, task_id)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.run_artifacts (
    receipt_sha256 text NOT NULL REFERENCES company_os_observatory.run_receipts(receipt_sha256),
    artifact_id text NOT NULL CHECK (artifact_id ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    kind text NOT NULL CHECK (btrim(kind) <> ''),
    title text NOT NULL CHECK (btrim(title) <> ''),
    external_id text NOT NULL CHECK (btrim(external_id) <> ''),
    owner_lane_id text NOT NULL,
    requirement_ids jsonb NOT NULL CHECK (jsonb_typeof(requirement_ids) = 'array'),
    satisfied_requirement_ids jsonb NOT NULL CHECK (jsonb_typeof(satisfied_requirement_ids) = 'array'),
    refetched boolean NOT NULL,
    accepted boolean NOT NULL,
    PRIMARY KEY (receipt_sha256, artifact_id),
    FOREIGN KEY (receipt_sha256, owner_lane_id)
        REFERENCES company_os_observatory.run_lanes(receipt_sha256, lane_id)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.run_capability_uses (
    receipt_sha256 text NOT NULL,
    artifact_id text NOT NULL,
    capability_id text NOT NULL CHECK (capability_id ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    required boolean NOT NULL,
    applied boolean NOT NULL,
    assignment_receipt_sha256 text CHECK (
        assignment_receipt_sha256 IS NULL
        OR assignment_receipt_sha256 ~ '^[0-9a-f]{64}$'
    ),
    PRIMARY KEY (receipt_sha256, artifact_id, capability_id),
    FOREIGN KEY (receipt_sha256, artifact_id)
        REFERENCES company_os_observatory.run_artifacts(receipt_sha256, artifact_id)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.acceptance_decisions (
    receipt_sha256 text PRIMARY KEY REFERENCES company_os_observatory.run_receipts(receipt_sha256),
    status text NOT NULL CHECK (status IN ('accepted', 'rework', 'blocked', 'failed')),
    reviewer text NOT NULL CHECK (btrim(reviewer) <> ''),
    authority text NOT NULL CHECK (authority IN ('manager', 'master', 'user')),
    required_authority text NOT NULL CHECK (required_authority IN ('manager', 'master', 'user')),
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'array')
);

CREATE TABLE IF NOT EXISTS company_os_observatory.run_failures (
    failure_id text PRIMARY KEY CHECK (failure_id ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    run_id text NOT NULL REFERENCES company_os_observatory.program_runs(run_id),
    receipt_sha256 text REFERENCES company_os_observatory.run_receipts(receipt_sha256),
    phase text NOT NULL CHECK (btrim(phase) <> ''),
    severity text NOT NULL CHECK (severity IN ('p0', 'p1', 'p2', 'p3')),
    code text NOT NULL CHECK (btrim(code) <> ''),
    summary text NOT NULL CHECK (btrim(summary) <> ''),
    status text NOT NULL CHECK (status IN ('open', 'resolved', 'accepted_risk', 'superseded')),
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'array'),
    opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    resolved_at timestamptz,
    CHECK (resolved_at IS NULL OR resolved_at >= opened_at)
);

CREATE INDEX IF NOT EXISTS run_failures_run_status_idx
    ON company_os_observatory.run_failures(run_id, status, severity);

CREATE TABLE IF NOT EXISTS company_os_observatory.framework_changes (
    change_id text PRIMARY KEY CHECK (change_id ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    from_framework_version_id text REFERENCES company_os_observatory.framework_versions(framework_version_id),
    to_framework_version_id text NOT NULL REFERENCES company_os_observatory.framework_versions(framework_version_id),
    hypothesis text NOT NULL CHECK (btrim(hypothesis) <> ''),
    source_commit text,
    status text NOT NULL CHECK (status IN ('proposed', 'verified', 'accepted', 'rejected', 'rolled_back')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS company_os_observatory.framework_change_failures (
    change_id text NOT NULL REFERENCES company_os_observatory.framework_changes(change_id),
    failure_id text NOT NULL REFERENCES company_os_observatory.run_failures(failure_id),
    relationship text NOT NULL CHECK (relationship IN ('triggered_by', 'targets', 'resolved', 'regressed')),
    PRIMARY KEY (change_id, failure_id, relationship)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.run_metrics (
    receipt_sha256 text NOT NULL REFERENCES company_os_observatory.run_receipts(receipt_sha256),
    metric_id text NOT NULL CHECK (metric_id ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    value numeric,
    unit text NOT NULL CHECK (btrim(unit) <> ''),
    availability text NOT NULL CHECK (availability IN ('observed', 'derived', 'unavailable', 'not_applicable')),
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'array'),
    PRIMARY KEY (receipt_sha256, metric_id),
    CHECK (
        (availability IN ('observed', 'derived') AND value IS NOT NULL)
        OR (availability IN ('unavailable', 'not_applicable') AND value IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS company_os_observatory.run_events (
    run_id text NOT NULL REFERENCES company_os_observatory.program_runs(run_id),
    sequence_no bigint NOT NULL CHECK (sequence_no > 0),
    event_type text NOT NULL CHECK (event_type ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    actor_id text,
    occurred_at timestamptz,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    payload_sha256 text CHECK (payload_sha256 IS NULL OR payload_sha256 ~ '^[0-9a-f]{64}$'),
    previous_event_sha256 text CHECK (previous_event_sha256 IS NULL OR previous_event_sha256 ~ '^[0-9a-f]{64}$'),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (run_id, sequence_no)
);

CREATE OR REPLACE FUNCTION company_os_observatory.reject_evidence_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Company OS observatory evidence is append-only';
END;
$$;

DO $$
DECLARE
    table_name text;
    trigger_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'run_receipts',
        'run_requirements',
        'run_lanes',
        'run_tasks',
        'run_artifacts',
        'run_capability_uses',
        'acceptance_decisions',
        'run_metrics',
        'run_events'
    ]
    LOOP
        trigger_name := 'reject_' || table_name || '_mutation';
        IF NOT EXISTS (
            SELECT 1
            FROM pg_trigger
            WHERE tgname = trigger_name
              AND tgrelid = format('company_os_observatory.%I', table_name)::regclass
              AND NOT tgisinternal
        ) THEN
            EXECUTE format(
                'CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON company_os_observatory.%I '
                'FOR EACH ROW EXECUTE FUNCTION company_os_observatory.reject_evidence_mutation()',
                trigger_name,
                table_name
            );
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE VIEW company_os_observatory.current_run_receipts AS
SELECT receipt.*
FROM company_os_observatory.run_receipts AS receipt
LEFT JOIN company_os_observatory.run_receipts AS successor
  ON successor.supersedes_receipt_sha256 = receipt.receipt_sha256
WHERE successor.receipt_sha256 IS NULL;

CREATE OR REPLACE VIEW company_os_observatory.run_scorecard AS
SELECT
    run.run_id,
    run.workspace_id,
    run.project_id,
    run.program_id,
    run.comparison_class,
    run.framework_version_id,
    receipt.receipt_sha256,
    receipt.status,
    receipt.recorded_at,
    COALESCE((receipt.validation_result #>> '{gates,delivery_accepted}')::boolean, false)
        AS delivery_accepted,
    COALESCE((receipt.validation_result #>> '{gates,hierarchy_materialized}')::boolean, false)
        AS hierarchy_materialized,
    COALESCE((receipt.validation_result #>> '{gates,luna_execution_proven}')::boolean, false)
        AS luna_execution_proven,
    COALESCE((receipt.validation_result #>> '{gates,efficiency_proven}')::boolean, false)
        AS efficiency_proven,
    COALESCE((receipt.validation_result #>> '{gates,scaling_evidence_eligible}')::boolean, false)
        AS scaling_evidence_eligible,
    NULLIF(receipt.validation_result #>> '{metrics,accepted_artifact_rate}', '')::numeric
        AS accepted_artifact_rate,
    NULLIF(receipt.validation_result #>> '{metrics,rework_cycles}', '')::numeric
        AS rework_cycles,
    NULLIF(receipt.validation_result #>> '{metrics,write_collisions}', '')::numeric
        AS write_collisions,
    NULLIF(receipt.validation_result #>> '{metrics,luna_token_share}', '')::numeric
        AS luna_token_share,
    NULLIF(receipt.validation_result #>> '{metrics,sol_token_reduction}', '')::numeric
        AS sol_token_reduction,
    NULLIF(receipt.validation_result #>> '{metrics,lead_time_seconds}', '')::numeric
        AS lead_time_seconds,
    NULLIF(receipt.validation_result #>> '{metrics,mandatory_requirements_satisfied}', '')::numeric
        AS mandatory_requirements_satisfied,
    NULLIF(receipt.validation_result #>> '{metrics,mandatory_requirements_total}', '')::numeric
        AS mandatory_requirements_total,
    NULLIF(receipt.validation_result #>> '{metrics,required_capabilities_applied}', '')::numeric
        AS required_capabilities_applied,
    NULLIF(receipt.validation_result #>> '{metrics,required_capabilities_total}', '')::numeric
        AS required_capabilities_total
FROM company_os_observatory.program_runs AS run
JOIN company_os_observatory.current_run_receipts AS receipt USING (run_id);

CREATE OR REPLACE VIEW company_os_observatory.comparison_trends AS
SELECT
    workspace_id,
    project_id,
    comparison_class,
    date_trunc('day', recorded_at) AS observed_day,
    count(*) AS run_count,
    avg(delivery_accepted::integer)::numeric(8, 4) AS accepted_run_rate,
    avg(accepted_artifact_rate)::numeric(8, 4) AS accepted_artifact_rate,
    avg(rework_cycles)::numeric(12, 4) AS average_rework_cycles,
    sum(write_collisions)::numeric AS write_collisions,
    avg(luna_token_share)::numeric(8, 4) AS luna_token_share,
    avg(sol_token_reduction)::numeric(8, 4) AS sol_token_reduction,
    avg(lead_time_seconds)::numeric(16, 2) AS average_lead_time_seconds,
    avg(
        CASE
            WHEN mandatory_requirements_total > 0
            THEN mandatory_requirements_satisfied / mandatory_requirements_total
        END
    )::numeric(8, 4) AS requirement_fidelity_rate,
    avg(
        CASE
            WHEN required_capabilities_total > 0
            THEN required_capabilities_applied / required_capabilities_total
        END
    )::numeric(8, 4) AS capability_application_rate
FROM company_os_observatory.run_scorecard
GROUP BY workspace_id, project_id, comparison_class, date_trunc('day', recorded_at);

INSERT INTO company_os_observatory.schema_migrations(version)
VALUES ('001_company_os_observatory')
ON CONFLICT (version) DO NOTHING;

COMMIT;
