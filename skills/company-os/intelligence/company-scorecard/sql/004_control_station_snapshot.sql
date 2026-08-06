BEGIN;

CREATE OR REPLACE FUNCTION company_os_observatory.control_station_snapshot(
    p_workspace_id text,
    p_run_limit integer DEFAULT 50
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = pg_catalog, company_os_observatory
AS $$
WITH bounded_runs AS (
    SELECT *
    FROM company_os_observatory.run_scorecard
    WHERE workspace_id = p_workspace_id
    ORDER BY recorded_at DESC, run_id
    LIMIT GREATEST(1, LEAST(COALESCE(p_run_limit, 50), 200))
),
summary AS (
    SELECT
        count(*)::integer AS run_count,
        count(*) FILTER (WHERE status = 'accepted')::integer AS accepted_runs,
        count(*) FILTER (WHERE status = 'blocked')::integer AS blocked_runs,
        count(*) FILTER (WHERE status = 'rework')::integer AS rework_runs,
        count(*) FILTER (WHERE status = 'failed')::integer AS failed_runs,
        count(*) FILTER (WHERE luna_execution_proven)::integer AS luna_proven_runs,
        count(*) FILTER (WHERE efficiency_proven)::integer AS efficiency_proven_runs,
        count(*) FILTER (WHERE scaling_evidence_eligible)::integer AS scale_eligible_runs,
        avg(delivery_accepted::integer)::numeric(8, 4) AS delivery_acceptance_rate,
        avg(accepted_artifact_rate)::numeric(8, 4) AS artifact_acceptance_rate,
        COALESCE(sum(write_collisions), 0)::numeric AS write_collisions
    FROM bounded_runs
),
requirement_blockers AS (
    SELECT
        run.run_id,
        'requirement'::text AS blocker_kind,
        requirement.requirement_id AS blocker_id,
        requirement.result_status AS blocker_status,
        requirement.statement AS summary
    FROM bounded_runs AS run
    JOIN company_os_observatory.run_requirements AS requirement
      ON requirement.receipt_sha256 = run.receipt_sha256
    WHERE requirement.mandatory
      AND requirement.result_status <> 'satisfied'
),
capability_blockers AS (
    SELECT
        run.run_id,
        'capability'::text AS blocker_kind,
        capability.capability_id AS blocker_id,
        'not_applied'::text AS blocker_status,
        format(
            'Required capability %s was not applied to artifact %s.',
            capability.capability_id,
            capability.artifact_id
        ) AS summary
    FROM bounded_runs AS run
    JOIN company_os_observatory.run_capability_uses AS capability
      ON capability.receipt_sha256 = run.receipt_sha256
    WHERE capability.required
      AND NOT capability.applied
),
blockers AS (
    SELECT * FROM requirement_blockers
    UNION ALL
    SELECT * FROM capability_blockers
)
SELECT jsonb_build_object(
    'schema', 'company-os.control-station-snapshot.v1',
    'workspace_id', p_workspace_id,
    'as_of', (SELECT max(recorded_at) FROM bounded_runs),
    'summary', jsonb_build_object(
        'run_count', summary.run_count,
        'accepted_runs', summary.accepted_runs,
        'blocked_runs', summary.blocked_runs,
        'rework_runs', summary.rework_runs,
        'failed_runs', summary.failed_runs,
        'luna_proven_runs', summary.luna_proven_runs,
        'efficiency_proven_runs', summary.efficiency_proven_runs,
        'scale_eligible_runs', summary.scale_eligible_runs,
        'delivery_acceptance_rate', summary.delivery_acceptance_rate,
        'artifact_acceptance_rate', summary.artifact_acceptance_rate,
        'write_collisions', summary.write_collisions
    ),
    'runs', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'run_id', run_id,
                'project_id', project_id,
                'program_id', program_id,
                'comparison_class', comparison_class,
                'status', status,
                'recorded_at', recorded_at,
                'delivery_accepted', delivery_accepted,
                'hierarchy_materialized', hierarchy_materialized,
                'luna_execution_proven', luna_execution_proven,
                'efficiency_proven', efficiency_proven,
                'scaling_evidence_eligible', scaling_evidence_eligible,
                'accepted_artifact_rate', accepted_artifact_rate,
                'rework_cycles', rework_cycles,
                'write_collisions', write_collisions,
                'luna_token_share', luna_token_share,
                'sol_token_reduction', sol_token_reduction,
                'lead_time_seconds', lead_time_seconds,
                'mandatory_requirements_satisfied', mandatory_requirements_satisfied,
                'mandatory_requirements_total', mandatory_requirements_total,
                'required_capabilities_applied', required_capabilities_applied,
                'required_capabilities_total', required_capabilities_total
            )
            ORDER BY recorded_at DESC, run_id
        )
        FROM bounded_runs
    ), '[]'::jsonb),
    'blockers', COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'run_id', run_id,
                'kind', blocker_kind,
                'id', blocker_id,
                'status', blocker_status,
                'summary', summary
            )
            ORDER BY run_id, blocker_kind, blocker_id
        )
        FROM blockers
    ), '[]'::jsonb)
)
FROM summary;
$$;

REVOKE EXECUTE ON FUNCTION company_os_observatory.control_station_snapshot(text, integer)
FROM PUBLIC;

INSERT INTO company_os_observatory.schema_migrations(version)
VALUES ('004_control_station_snapshot')
ON CONFLICT (version) DO NOTHING;

COMMIT;
