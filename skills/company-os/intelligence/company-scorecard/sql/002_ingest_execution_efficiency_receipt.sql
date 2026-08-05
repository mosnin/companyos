BEGIN;

CREATE OR REPLACE FUNCTION company_os_observatory.ingest_execution_efficiency_receipt(
    p_workspace_id text,
    p_workspace_name text,
    p_project_id text,
    p_project_name text,
    p_run_id text,
    p_framework_version_id text,
    p_framework_source_commit text,
    p_source_thread_id text,
    p_receipt_sha256 text,
    p_supersedes_receipt_sha256 text,
    p_receipt_canonical text,
    p_validation_result jsonb
)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
    existing_receipt company_os_observatory.run_receipts%ROWTYPE;
    existing_run company_os_observatory.program_runs%ROWTYPE;
    existing_framework company_os_observatory.framework_versions%ROWTYPE;
    next_sequence bigint;
    expected_requirements integer;
    inserted_requirements integer;
    p_receipt jsonb := p_receipt_canonical::jsonb;
BEGIN
    IF p_receipt_sha256 IS NULL
       OR p_receipt_sha256 !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'receipt SHA-256 must be 64 lowercase hex characters';
    END IF;
    IF encode(digest(convert_to(p_receipt_canonical, 'UTF8'), 'sha256'), 'hex')
       <> p_receipt_sha256 THEN
        RAISE EXCEPTION 'receipt SHA-256 does not bind the canonical receipt bytes';
    END IF;
    IF p_receipt ->> 'schema'
       IS DISTINCT FROM 'company-os.execution-efficiency-receipt.v1' THEN
        RAISE EXCEPTION 'unsupported execution-efficiency receipt schema';
    END IF;
    IF COALESCE((p_validation_result ->> 'ok')::boolean, false) IS NOT TRUE THEN
        RAISE EXCEPTION 'receipt must pass the source validator before persistence';
    END IF;
    IF p_validation_result ->> 'receipt_sha256'
       IS DISTINCT FROM p_receipt_sha256 THEN
        RAISE EXCEPTION 'validation result does not bind the receipt SHA-256';
    END IF;
    IF p_validation_result ->> 'program_id'
       IS DISTINCT FROM p_receipt ->> 'program_id' THEN
        RAISE EXCEPTION 'validation result does not bind the receipt program';
    END IF;
    IF p_validation_result ->> 'comparison_class'
       IS DISTINCT FROM p_receipt ->> 'comparison_class' THEN
        RAISE EXCEPTION 'validation result does not bind the receipt comparison class';
    END IF;
    IF p_supersedes_receipt_sha256 = p_receipt_sha256 THEN
        RAISE EXCEPTION 'a receipt cannot supersede itself';
    END IF;

    SELECT * INTO existing_receipt
    FROM company_os_observatory.run_receipts
    WHERE receipt_sha256 = p_receipt_sha256;
    IF FOUND THEN
        IF existing_receipt.run_id <> p_run_id
           OR existing_receipt.raw_receipt <> p_receipt
           OR existing_receipt.validation_result <> p_validation_result
           OR existing_receipt.supersedes_receipt_sha256
              IS DISTINCT FROM p_supersedes_receipt_sha256 THEN
            RAISE EXCEPTION 'receipt hash already exists with different immutable evidence';
        END IF;
        RETURN p_receipt_sha256;
    END IF;

    INSERT INTO company_os_observatory.workspaces(workspace_id, name)
    VALUES (p_workspace_id, p_workspace_name)
    ON CONFLICT (workspace_id) DO NOTHING;

    INSERT INTO company_os_observatory.projects(workspace_id, project_id, name)
    VALUES (p_workspace_id, p_project_id, p_project_name)
    ON CONFLICT (workspace_id, project_id) DO NOTHING;

    INSERT INTO company_os_observatory.framework_versions(
        framework_version_id,
        source_commit
    )
    VALUES (p_framework_version_id, p_framework_source_commit)
    ON CONFLICT (framework_version_id) DO NOTHING;

    SELECT * INTO existing_framework
    FROM company_os_observatory.framework_versions
    WHERE framework_version_id = p_framework_version_id;
    IF existing_framework.source_commit IS DISTINCT FROM p_framework_source_commit THEN
        RAISE EXCEPTION 'framework version ID already exists with a different source commit';
    END IF;

    INSERT INTO company_os_observatory.program_runs(
        run_id,
        workspace_id,
        project_id,
        framework_version_id,
        program_id,
        comparison_class,
        source_thread_id
    )
    VALUES (
        p_run_id,
        p_workspace_id,
        p_project_id,
        p_framework_version_id,
        p_receipt ->> 'program_id',
        p_receipt ->> 'comparison_class',
        p_source_thread_id
    )
    ON CONFLICT (run_id) DO NOTHING;

    SELECT * INTO existing_run
    FROM company_os_observatory.program_runs
    WHERE run_id = p_run_id;
    IF existing_run.workspace_id <> p_workspace_id
       OR existing_run.project_id <> p_project_id
       OR existing_run.framework_version_id <> p_framework_version_id
       OR existing_run.program_id <> p_receipt ->> 'program_id'
       OR existing_run.comparison_class <> p_receipt ->> 'comparison_class'
       OR existing_run.source_thread_id IS DISTINCT FROM p_source_thread_id THEN
        RAISE EXCEPTION 'run ID already exists with a different immutable identity';
    END IF;

    IF p_supersedes_receipt_sha256 IS NOT NULL THEN
        SELECT * INTO existing_receipt
        FROM company_os_observatory.run_receipts
        WHERE receipt_sha256 = p_supersedes_receipt_sha256;
        IF NOT FOUND OR existing_receipt.run_id <> p_run_id THEN
            RAISE EXCEPTION 'superseded receipt is missing or belongs to another run';
        END IF;
    END IF;

    INSERT INTO company_os_observatory.run_receipts(
        receipt_sha256,
        run_id,
        schema_id,
        status,
        supersedes_receipt_sha256,
        raw_receipt,
        validation_result
    )
    VALUES (
        p_receipt_sha256,
        p_run_id,
        p_receipt ->> 'schema',
        p_receipt ->> 'status',
        p_supersedes_receipt_sha256,
        p_receipt,
        p_validation_result
    );

    expected_requirements := jsonb_array_length(p_receipt -> 'requirements');
    INSERT INTO company_os_observatory.run_requirements(
        receipt_sha256,
        requirement_id,
        statement,
        source,
        mandatory,
        result_status,
        evidence
    )
    SELECT
        p_receipt_sha256,
        requirement ->> 'requirement_id',
        requirement ->> 'statement',
        requirement ->> 'source',
        (requirement ->> 'mandatory')::boolean,
        result ->> 'status',
        result -> 'evidence'
    FROM jsonb_array_elements(p_receipt -> 'requirements') AS requirement
    JOIN LATERAL (
        SELECT candidate
        FROM jsonb_array_elements(p_receipt -> 'requirement_results') AS candidate
        WHERE candidate ->> 'requirement_id' = requirement ->> 'requirement_id'
    ) AS matched(result) ON true;
    GET DIAGNOSTICS inserted_requirements = ROW_COUNT;
    IF inserted_requirements <> expected_requirements THEN
        RAISE EXCEPTION 'requirement/result closure failed during persistence';
    END IF;

    INSERT INTO company_os_observatory.run_lanes(
        receipt_sha256,
        lane_id,
        outcome,
        manager_task_id
    )
    SELECT
        p_receipt_sha256,
        lane ->> 'lane_id',
        lane ->> 'outcome',
        (
            SELECT manager ->> 'manager_task_id'
            FROM jsonb_array_elements(
                p_receipt #> '{topology,manager_assignments}'
            ) AS manager
            WHERE EXISTS (
                SELECT 1
                FROM jsonb_array_elements_text(manager -> 'lane_ids') AS manager_lane(lane_id)
                WHERE manager_lane.lane_id = lane ->> 'lane_id'
            )
        )
    FROM jsonb_array_elements(p_receipt #> '{topology,requested_lanes}') AS lane;

    INSERT INTO company_os_observatory.run_tasks(
        receipt_sha256,
        task_id,
        parent_task_id,
        role,
        lane_ids,
        requested_model,
        requested_effort,
        observed_model,
        observed_effort
    )
    SELECT
        p_receipt_sha256,
        manager ->> 'manager_task_id',
        NULL,
        'manager',
        manager -> 'lane_ids',
        manager ->> 'requested_model',
        manager ->> 'requested_effort',
        manager ->> 'observed_model',
        manager ->> 'observed_effort'
    FROM jsonb_array_elements(
        p_receipt #> '{topology,manager_assignments}'
    ) AS manager;

    INSERT INTO company_os_observatory.run_tasks(
        receipt_sha256,
        task_id,
        parent_task_id,
        role,
        lane_ids,
        requested_model,
        requested_effort,
        observed_model,
        observed_effort
    )
    SELECT
        p_receipt_sha256,
        worker ->> 'worker_task_id',
        worker ->> 'manager_task_id',
        'worker',
        '[]'::jsonb,
        worker ->> 'requested_model',
        worker ->> 'requested_effort',
        worker ->> 'observed_model',
        worker ->> 'observed_effort'
    FROM jsonb_array_elements(p_receipt #> '{topology,workers}') AS worker;

    INSERT INTO company_os_observatory.run_artifacts(
        receipt_sha256,
        artifact_id,
        kind,
        title,
        external_id,
        owner_lane_id,
        requirement_ids,
        satisfied_requirement_ids,
        refetched,
        accepted
    )
    SELECT
        p_receipt_sha256,
        artifact ->> 'artifact_id',
        artifact ->> 'kind',
        artifact ->> 'title',
        artifact ->> 'external_id',
        artifact ->> 'owner_lane_id',
        plan -> 'requirement_ids',
        artifact -> 'satisfied_requirement_ids',
        (artifact ->> 'refetched')::boolean,
        (artifact ->> 'accepted')::boolean
    FROM jsonb_array_elements(p_receipt -> 'artifacts') AS artifact
    JOIN LATERAL (
        SELECT candidate
        FROM jsonb_array_elements(p_receipt -> 'artifact_plan') AS candidate
        WHERE candidate ->> 'artifact_id' = artifact ->> 'artifact_id'
    ) AS matched(plan) ON true;

    INSERT INTO company_os_observatory.run_capability_uses(
        receipt_sha256,
        artifact_id,
        capability_id,
        required,
        applied,
        assignment_receipt_sha256
    )
    SELECT
        p_receipt_sha256,
        artifact ->> 'artifact_id',
        capability.capability_id,
        capability.capability_id = ANY(
            ARRAY(
                SELECT jsonb_array_elements_text(plan -> 'required_capability_ids')
            )
        ),
        capability.capability_id = ANY(
            ARRAY(
                SELECT jsonb_array_elements_text(artifact -> 'applied_capability_ids')
            )
        ),
        NULL
    FROM jsonb_array_elements(p_receipt -> 'artifacts') AS artifact
    JOIN LATERAL (
        SELECT candidate
        FROM jsonb_array_elements(p_receipt -> 'artifact_plan') AS candidate
        WHERE candidate ->> 'artifact_id' = artifact ->> 'artifact_id'
    ) AS matched(plan) ON true
    CROSS JOIN LATERAL (
        SELECT DISTINCT capability_id
        FROM (
            SELECT jsonb_array_elements_text(plan -> 'required_capability_ids') AS capability_id
            UNION ALL
            SELECT jsonb_array_elements_text(artifact -> 'applied_capability_ids') AS capability_id
        ) AS capability_union
    ) AS capability;

    INSERT INTO company_os_observatory.acceptance_decisions(
        receipt_sha256,
        status,
        reviewer,
        authority,
        required_authority,
        evidence
    )
    VALUES (
        p_receipt_sha256,
        p_receipt #>> '{decision,status}',
        p_receipt #>> '{decision,reviewer}',
        p_receipt #>> '{decision,authority}',
        p_receipt #>> '{decision,required_authority}',
        p_receipt #> '{decision,evidence}'
    );

    INSERT INTO company_os_observatory.run_metrics(
        receipt_sha256,
        metric_id,
        value,
        unit,
        availability,
        evidence
    )
    SELECT
        p_receipt_sha256,
        metric.key,
        (metric.value #>> '{}')::numeric,
        CASE
            WHEN metric.key LIKE '%rate' OR metric.key LIKE '%share' OR metric.key LIKE '%reduction' OR metric.key LIKE '%improvement' THEN 'ratio'
            WHEN metric.key LIKE '%seconds' THEN 'seconds'
            ELSE 'count'
        END,
        'derived',
        jsonb_build_array('company-os.execution-efficiency-validation.v1')
    FROM jsonb_each(p_validation_result -> 'metrics') AS metric
    WHERE jsonb_typeof(metric.value) = 'number';

    SELECT COALESCE(max(sequence_no), 0) + 1
    INTO next_sequence
    FROM company_os_observatory.run_events
    WHERE run_id = p_run_id;

    INSERT INTO company_os_observatory.run_events(
        run_id,
        sequence_no,
        event_type,
        actor_id,
        occurred_at,
        payload,
        payload_sha256,
        previous_event_sha256
    )
    VALUES (
        p_run_id,
        next_sequence,
        'receipt-recorded',
        p_receipt #>> '{decision,reviewer}',
        clock_timestamp(),
        jsonb_build_object(
            'receipt_sha256', p_receipt_sha256,
            'status', p_receipt ->> 'status',
            'supersedes_receipt_sha256', p_supersedes_receipt_sha256
        ),
        NULL,
        NULL
    );

    RETURN p_receipt_sha256;
END;
$$;

REVOKE EXECUTE ON FUNCTION company_os_observatory.ingest_execution_efficiency_receipt(
    text, text, text, text, text, text, text, text, text, text, text, jsonb
) FROM PUBLIC;

INSERT INTO company_os_observatory.schema_migrations(version)
VALUES ('002_ingest_execution_efficiency_receipt')
ON CONFLICT (version) DO NOTHING;

COMMIT;
