BEGIN;

CREATE TABLE IF NOT EXISTS company_os_observatory.company_blueprints (
    workspace_id text NOT NULL REFERENCES company_os_observatory.workspaces(workspace_id),
    company_id text NOT NULL CHECK (company_id ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'),
    blueprint_version integer NOT NULL CHECK (blueprint_version > 0),
    blueprint_sha256 text NOT NULL UNIQUE CHECK (blueprint_sha256 ~ '^[0-9a-f]{64}$'),
    compiled_manifest_sha256 text NOT NULL CHECK (compiled_manifest_sha256 ~ '^[0-9a-f]{64}$'),
    execution_ready boolean NOT NULL,
    raw_blueprint jsonb NOT NULL CHECK (jsonb_typeof(raw_blueprint) = 'object'),
    supersedes_blueprint_sha256 text UNIQUE
        REFERENCES company_os_observatory.company_blueprints(blueprint_sha256),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (workspace_id, company_id, blueprint_version)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.company_departments (
    blueprint_sha256 text NOT NULL REFERENCES company_os_observatory.company_blueprints(blueprint_sha256),
    department_id text NOT NULL CHECK (department_id ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'),
    mission text NOT NULL CHECK (btrim(mission) <> ''),
    decision_rights jsonb NOT NULL CHECK (jsonb_typeof(decision_rights) = 'array'),
    metrics jsonb NOT NULL CHECK (jsonb_typeof(metrics) = 'array'),
    interfaces jsonb NOT NULL CHECK (jsonb_typeof(interfaces) = 'array'),
    PRIMARY KEY (blueprint_sha256, department_id)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.company_capabilities (
    blueprint_sha256 text NOT NULL REFERENCES company_os_observatory.company_blueprints(blueprint_sha256),
    capability_id text NOT NULL CHECK (capability_id ~ '^[a-z0-9][a-z0-9._:-]{0,127}$'),
    department_id text,
    capability_kind text NOT NULL CHECK (capability_kind IN ('business', 'skill', 'tool', 'playbook')),
    locator text,
    required boolean NOT NULL,
    PRIMARY KEY (blueprint_sha256, capability_kind, capability_id),
    FOREIGN KEY (blueprint_sha256, department_id)
        REFERENCES company_os_observatory.company_departments(blueprint_sha256, department_id)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.company_routines (
    blueprint_sha256 text NOT NULL REFERENCES company_os_observatory.company_blueprints(blueprint_sha256),
    routine_id text NOT NULL CHECK (routine_id ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'),
    department_id text NOT NULL,
    cadence text NOT NULL CHECK (btrim(cadence) <> ''),
    playbook_id text NOT NULL CHECK (playbook_id ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'),
    activation_state text NOT NULL CHECK (activation_state IN ('planned', 'enabled', 'paused', 'retired')),
    required_approvals jsonb NOT NULL CHECK (jsonb_typeof(required_approvals) = 'array'),
    PRIMARY KEY (blueprint_sha256, routine_id),
    FOREIGN KEY (blueprint_sha256, department_id)
        REFERENCES company_os_observatory.company_departments(blueprint_sha256, department_id)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.company_knowledge_nodes (
    blueprint_sha256 text NOT NULL REFERENCES company_os_observatory.company_blueprints(blueprint_sha256),
    node_id text NOT NULL CHECK (btrim(node_id) <> ''),
    node_kind text NOT NULL CHECK (node_kind IN ('company', 'objective', 'department', 'skill', 'asset', 'integration', 'fact', 'decision', 'policy')),
    label text NOT NULL CHECK (btrim(label) <> ''),
    classification text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    PRIMARY KEY (blueprint_sha256, node_id)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.company_knowledge_edges (
    blueprint_sha256 text NOT NULL,
    from_node_id text NOT NULL,
    edge_kind text NOT NULL CHECK (btrim(edge_kind) <> ''),
    to_node_id text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    PRIMARY KEY (blueprint_sha256, from_node_id, edge_kind, to_node_id),
    FOREIGN KEY (blueprint_sha256, from_node_id)
        REFERENCES company_os_observatory.company_knowledge_nodes(blueprint_sha256, node_id),
    FOREIGN KEY (blueprint_sha256, to_node_id)
        REFERENCES company_os_observatory.company_knowledge_nodes(blueprint_sha256, node_id)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.company_assets (
    blueprint_sha256 text NOT NULL REFERENCES company_os_observatory.company_blueprints(blueprint_sha256),
    asset_id text NOT NULL CHECK (asset_id ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'),
    asset_kind text NOT NULL CHECK (btrim(asset_kind) <> ''),
    locator text NOT NULL CHECK (btrim(locator) <> ''),
    content_sha256 text CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$'),
    classification text,
    PRIMARY KEY (blueprint_sha256, asset_id)
);

CREATE TABLE IF NOT EXISTS company_os_observatory.company_integrations (
    blueprint_sha256 text NOT NULL REFERENCES company_os_observatory.company_blueprints(blueprint_sha256),
    integration_id text NOT NULL CHECK (integration_id ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'),
    integration_kind text NOT NULL CHECK (integration_kind IN ('mcp', 'plugin', 'api', 'repository', 'database', 'filesystem', 'human')),
    locator text NOT NULL CHECK (btrim(locator) <> ''),
    permission_mode text NOT NULL CHECK (permission_mode IN ('read_only', 'proposal_only', 'approved_write', 'unavailable')),
    credential_reference text,
    PRIMARY KEY (blueprint_sha256, integration_id),
    CHECK (credential_reference IS NULL OR credential_reference ~ '^[A-Z][A-Z0-9_]*$')
);

DO $$
DECLARE
    table_name text;
    trigger_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'company_blueprints',
        'company_departments',
        'company_capabilities',
        'company_routines',
        'company_knowledge_nodes',
        'company_knowledge_edges',
        'company_assets',
        'company_integrations'
    ]
    LOOP
        trigger_name := 'reject_' || table_name || '_mutation';
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger
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

CREATE OR REPLACE VIEW company_os_observatory.current_company_blueprints AS
SELECT blueprint.*
FROM company_os_observatory.company_blueprints AS blueprint
LEFT JOIN company_os_observatory.company_blueprints AS successor
  ON successor.supersedes_blueprint_sha256 = blueprint.blueprint_sha256
WHERE successor.blueprint_sha256 IS NULL;

INSERT INTO company_os_observatory.schema_migrations(version)
VALUES ('003_company_blueprints')
ON CONFLICT (version) DO NOTHING;

COMMIT;
