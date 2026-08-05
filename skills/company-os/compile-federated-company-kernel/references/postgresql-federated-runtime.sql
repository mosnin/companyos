-- Company OS federated runtime authority for PostgreSQL 15+.
-- The quoted schema matches the canonical kernel persistence identifier.

-- Serialize the complete migration inside the caller's transaction. This
-- prevents concurrent deployers from racing version markers, function ACLs,
-- or legacy quarantine. The adapter and validation path always apply the
-- statement set transactionally.
SELECT pg_advisory_xact_lock(
  hashtextextended('company-os:federated-runtime-migration:v2', 0)
);

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS "company-os";

CREATE TABLE IF NOT EXISTS "company-os".projects (
  project_id text PRIMARY KEY,
  current_revision bigint NOT NULL DEFAULT 0 CHECK (current_revision >= 0),
  created_at timestamptz NOT NULL
);

-- Database identity is part of tenant authority.  An administrator provisions
-- one immutable database role binding before a project can use the runtime.
-- Runtime functions cross a hardened SECURITY DEFINER API boundary and reject
-- callers whose authenticated PostgreSQL session role is not immutably bound
-- to the requested project. Runtime roles receive EXECUTE only and never table
-- privileges; binding remains an administrator-only operation.
CREATE TABLE IF NOT EXISTS "company-os".project_runtime_principals (
  project_id text PRIMARY KEY CHECK (btrim(project_id) <> ''),
  database_role name NOT NULL UNIQUE
);

CREATE UNIQUE INDEX IF NOT EXISTS project_runtime_principals_database_role_idx
  ON "company-os".project_runtime_principals(database_role);

CREATE TABLE IF NOT EXISTS "company-os".events (
  project_id text NOT NULL REFERENCES "company-os".projects(project_id),
  revision bigint NOT NULL CHECK (revision > 0),
  event_type text NOT NULL,
  payload_json text NOT NULL,
  payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL,
  PRIMARY KEY (project_id, revision),
  CHECK (
    payload_sha256 = encode(public.digest(convert_to(payload_json, 'UTF8'), 'sha256'), 'hex')
  )
);

CREATE TABLE IF NOT EXISTS "company-os".kernels (
  project_id text NOT NULL REFERENCES "company-os".projects(project_id),
  kernel_digest text NOT NULL CHECK (kernel_digest ~ '^[0-9a-f]{64}$'),
  kernel_json text NOT NULL,
  kernel_sha256 text NOT NULL CHECK (kernel_sha256 ~ '^[0-9a-f]{64}$'),
  first_seen_revision bigint NOT NULL CHECK (first_seen_revision > 0),
  PRIMARY KEY (project_id, kernel_digest),
  FOREIGN KEY (project_id, first_seen_revision)
    REFERENCES "company-os".events(project_id, revision),
  CHECK (
    kernel_sha256 = encode(public.digest(convert_to(kernel_json, 'UTF8'), 'sha256'), 'hex')
  )
);

CREATE TABLE IF NOT EXISTS "company-os".reconciliation_plans (
  project_id text NOT NULL REFERENCES "company-os".projects(project_id),
  plan_key text NOT NULL CHECK (plan_key ~ '^[0-9a-f]{64}$'),
  stream_key text NOT NULL CHECK (stream_key ~ '^[0-9a-f]{64}$'),
  kernel_digest text NOT NULL,
  generation bigint NOT NULL CHECK (generation > 0),
  cycle_id text NOT NULL,
  parent_runtime_id text NOT NULL,
  request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
  snapshot_cursor bigint NOT NULL CHECK (snapshot_cursor >= 0),
  snapshot_digest text NOT NULL CHECK (snapshot_digest ~ '^[0-9a-f]{64}$'),
  status text NOT NULL CHECK (status IN ('ready', 'deferred', 'blocked')),
  request_json text NOT NULL,
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  plan_json text NOT NULL,
  plan_sha256 text NOT NULL CHECK (plan_sha256 ~ '^[0-9a-f]{64}$'),
  plan_digest text NOT NULL CHECK (plan_digest ~ '^[0-9a-f]{64}$'),
  command_set_digest text NOT NULL CHECK (command_set_digest ~ '^[0-9a-f]{64}$'),
  command_count integer NOT NULL CHECK (command_count >= 0),
  state_revision bigint NOT NULL CHECK (state_revision > 0),
  created_at timestamptz NOT NULL,
  PRIMARY KEY (project_id, plan_key),
  UNIQUE (project_id, stream_key, snapshot_cursor),
  FOREIGN KEY (project_id, kernel_digest)
    REFERENCES "company-os".kernels(project_id, kernel_digest),
  FOREIGN KEY (project_id, state_revision)
    REFERENCES "company-os".events(project_id, revision),
  CHECK (
    request_sha256 = encode(public.digest(convert_to(request_json, 'UTF8'), 'sha256'), 'hex')
  ),
  CHECK (
    plan_sha256 = encode(public.digest(convert_to(plan_json, 'UTF8'), 'sha256'), 'hex')
  )
);

CREATE TABLE IF NOT EXISTS "company-os".observation_cursors (
  project_id text NOT NULL REFERENCES "company-os".projects(project_id),
  stream_key text NOT NULL CHECK (stream_key ~ '^[0-9a-f]{64}$'),
  kernel_digest text NOT NULL,
  generation bigint NOT NULL CHECK (generation > 0),
  cycle_id text NOT NULL,
  parent_runtime_id text NOT NULL,
  last_event_cursor bigint NOT NULL CHECK (last_event_cursor >= 0),
  snapshot_digest text NOT NULL CHECK (snapshot_digest ~ '^[0-9a-f]{64}$'),
  updated_revision bigint NOT NULL CHECK (updated_revision > 0),
  PRIMARY KEY (project_id, stream_key),
  FOREIGN KEY (project_id, kernel_digest)
    REFERENCES "company-os".kernels(project_id, kernel_digest),
  FOREIGN KEY (project_id, updated_revision)
    REFERENCES "company-os".events(project_id, revision)
);

CREATE TABLE IF NOT EXISTS "company-os".commands (
  project_id text NOT NULL REFERENCES "company-os".projects(project_id),
  message_key text NOT NULL CHECK (message_key ~ '^[0-9a-f]{64}$'),
  plan_key text NOT NULL,
  plan_order integer NOT NULL CHECK (plan_order > 0),
  payload_json text NOT NULL,
  payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
  status text NOT NULL CHECK (
    status IN ('pending', 'leased', 'succeeded', 'failed', 'cancelled')
  ),
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  not_before timestamptz,
  lease_owner text,
  lease_token_sha256 text CHECK (
    lease_token_sha256 IS NULL OR lease_token_sha256 ~ '^[0-9a-f]{64}$'
  ),
  lease_generation bigint NOT NULL DEFAULT 0 CHECK (lease_generation >= 0),
  lease_expires_at timestamptz,
  terminal_receipt_json text,
  terminal_receipt_sha256 text CHECK (
    terminal_receipt_sha256 IS NULL OR terminal_receipt_sha256 ~ '^[0-9a-f]{64}$'
  ),
  created_revision bigint NOT NULL CHECK (created_revision > 0),
  updated_revision bigint NOT NULL CHECK (updated_revision >= created_revision),
  PRIMARY KEY (project_id, message_key),
  UNIQUE (project_id, plan_key, plan_order),
  FOREIGN KEY (project_id, plan_key)
    REFERENCES "company-os".reconciliation_plans(project_id, plan_key),
  FOREIGN KEY (project_id, created_revision)
    REFERENCES "company-os".events(project_id, revision),
  FOREIGN KEY (project_id, updated_revision)
    REFERENCES "company-os".events(project_id, revision),
  CHECK (
    payload_sha256 = encode(public.digest(convert_to(payload_json, 'UTF8'), 'sha256'), 'hex')
  ),
  CHECK (
    terminal_receipt_json IS NULL
    OR terminal_receipt_sha256 = encode(
      public.digest(convert_to(terminal_receipt_json, 'UTF8'), 'sha256'), 'hex'
    )
  ),
  CHECK (
    (status IN ('succeeded', 'cancelled')
      AND terminal_receipt_json IS NOT NULL
      AND terminal_receipt_sha256 IS NOT NULL)
    OR status IN ('pending', 'leased', 'failed')
  ),
  CHECK (
    (status = 'leased'
      AND lease_owner IS NOT NULL
      AND lease_token_sha256 IS NOT NULL
      AND lease_expires_at IS NOT NULL
      AND lease_generation > 0)
    OR
    (status <> 'leased'
      AND lease_owner IS NULL
      AND lease_token_sha256 IS NULL
      AND lease_expires_at IS NULL)
  )
);

-- A native host create is an external effect.  Keep its exact, content-bound
-- intent in the same authority before the host call so an expired command
-- lease can never silently become a second create.  The row is deliberately
-- mutable only through the functions below; the immutable event log retains
-- every prepare, recovery, conflict, and settlement transition.
CREATE TABLE IF NOT EXISTS "company-os".native_launch_attempts (
  project_id text NOT NULL,
  message_key text NOT NULL,
  attempt_id text NOT NULL CHECK (btrim(attempt_id) <> ''),
  payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
  content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  dispatch_digest text NOT NULL CHECK (dispatch_digest ~ '^[0-9a-f]{64}$'),
  initial_prompt_sha256 text NOT NULL CHECK (initial_prompt_sha256 ~ '^[0-9a-f]{64}$'),
  status text NOT NULL CHECK (
    status IN ('prepared', 'ambiguous', 'bound', 'abandoned', 'conflict', 'settled', 'cancelled')
  ),
  candidate_count integer NOT NULL DEFAULT 0 CHECK (candidate_count >= 0),
  candidate_evidence_json text,
  candidate_evidence_sha256 text CHECK (
    candidate_evidence_sha256 IS NULL OR candidate_evidence_sha256 ~ '^[0-9a-f]{64}$'
  ),
  task_id text,
  thread_id text,
  host_id text,
  creation_receipt_json text,
  creation_receipt_sha256 text CHECK (
    creation_receipt_sha256 IS NULL OR creation_receipt_sha256 ~ '^[0-9a-f]{64}$'
  ),
  prepared_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  PRIMARY KEY (project_id, message_key),
  UNIQUE (project_id, attempt_id),
  FOREIGN KEY (project_id, message_key)
    REFERENCES "company-os".commands(project_id, message_key),
  CHECK (
    (status IN ('bound', 'settled')
      AND task_id IS NOT NULL
      AND thread_id IS NOT NULL
      AND host_id IS NOT NULL
      AND creation_receipt_json IS NOT NULL
      AND creation_receipt_sha256 IS NOT NULL)
    OR status IN ('prepared', 'ambiguous', 'abandoned', 'conflict', 'cancelled')
  ),
  CHECK (
    candidate_evidence_json IS NULL
    OR candidate_evidence_sha256 = encode(
      public.digest(convert_to(candidate_evidence_json, 'UTF8'), 'sha256'), 'hex'
    )
  ),
  CHECK (
    creation_receipt_json IS NULL
    OR creation_receipt_sha256 = encode(
      public.digest(convert_to(creation_receipt_json, 'UTF8'), 'sha256'), 'hex'
    )
  )
);

-- An earlier launch protocol could label a caller-attested empty listing as
-- `abandoned`, then silently reuse the same intent for another external create.
-- Versioned quarantine makes upgrades fail closed. On the first v2 migration,
-- every pre-existing terminal binding and every suspect active attempt is
-- preserved verbatim and converted to conflict. A rerun never quarantines work
-- created by the current protocol.
CREATE TABLE IF NOT EXISTS "company-os".runtime_schema_migrations (
  migration_key text PRIMARY KEY CHECK (btrim(migration_key) <> ''),
  applied_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS "company-os".native_launch_legacy_quarantine (
  project_id text NOT NULL,
  message_key text NOT NULL,
  attempt_id text NOT NULL,
  source_status text NOT NULL,
  reason_code text NOT NULL,
  raw_attempt_json jsonb NOT NULL,
  raw_command_json jsonb,
  quarantined_at timestamptz NOT NULL,
  PRIMARY KEY (project_id, message_key, reason_code)
);

DO $company_os_native_launch_v2$
DECLARE
  v_acquired text;
BEGIN
  INSERT INTO "company-os".runtime_schema_migrations(migration_key, applied_at)
  VALUES ('native-launch-authority-v2', transaction_timestamp())
  ON CONFLICT DO NOTHING
  RETURNING migration_key INTO v_acquired;

  IF v_acquired IS NOT NULL THEN
    INSERT INTO "company-os".native_launch_legacy_quarantine(
      project_id, message_key, attempt_id, source_status, reason_code,
      raw_attempt_json, raw_command_json, quarantined_at
    )
    SELECT
      launch.project_id,
      launch.message_key,
      launch.attempt_id,
      launch.status,
      CASE
        WHEN launch.status = 'abandoned' THEN 'legacy-unproven-absence'
        WHEN command.status = 'failed' THEN 'legacy-failed-command-active-launch'
        ELSE 'legacy-unverified-bound-receipt'
      END,
      to_jsonb(launch),
      to_jsonb(command),
      transaction_timestamp()
    FROM "company-os".native_launch_attempts AS launch
    JOIN "company-os".commands AS command
      ON command.project_id = launch.project_id
     AND command.message_key = launch.message_key
    WHERE launch.status IN ('abandoned', 'bound', 'settled')
       OR (
         command.status = 'failed'
         AND launch.status IN ('prepared', 'ambiguous', 'bound', 'conflict')
       )
    ON CONFLICT DO NOTHING;

    UPDATE "company-os".native_launch_attempts AS launch
    SET status = 'conflict', updated_at = transaction_timestamp()
    WHERE EXISTS (
      SELECT 1
      FROM "company-os".native_launch_legacy_quarantine AS quarantine
      WHERE quarantine.project_id = launch.project_id
        AND quarantine.message_key = launch.message_key
    )
      AND launch.status <> 'cancelled';

  END IF;
END;
$company_os_native_launch_v2$;

CREATE INDEX IF NOT EXISTS commands_claimable_idx
  ON "company-os".commands(project_id, status, not_before, created_revision, plan_order);
CREATE INDEX IF NOT EXISTS commands_expired_lease_idx
  ON "company-os".commands(project_id, lease_expires_at)
  WHERE status = 'leased';
CREATE INDEX IF NOT EXISTS plans_revision_idx
  ON "company-os".reconciliation_plans(project_id, state_revision);
CREATE INDEX IF NOT EXISTS native_launch_attempts_recovery_idx
  ON "company-os".native_launch_attempts(project_id, status, updated_at);
CREATE UNIQUE INDEX IF NOT EXISTS native_launch_attempts_task_idx
  ON "company-os".native_launch_attempts(project_id, task_id)
  WHERE task_id IS NOT NULL;

CREATE OR REPLACE FUNCTION "company-os".reject_immutable_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'immutable Company OS history cannot be changed';
END;
$$;

CREATE OR REPLACE FUNCTION "company-os".native_launch_content_sha256(
  p_message_key text,
  p_payload_sha256 text,
  p_attempt_id text,
  p_dispatch_digest text,
  p_initial_prompt_sha256 text
)
RETURNS text
LANGUAGE sql
IMMUTABLE
SET search_path = pg_catalog
AS $$
  SELECT encode(
    public.digest(
      convert_to(
        concat_ws(
          '|',
          p_message_key,
          p_payload_sha256,
          p_attempt_id,
          p_dispatch_digest,
          p_initial_prompt_sha256
        ),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  )
$$;

CREATE OR REPLACE FUNCTION "company-os".bind_project_runtime_principal(
  p_project_id text,
  p_database_role name
)
RETURNS void
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
DECLARE
  v_existing name;
BEGIN
  IF p_project_id IS NULL OR btrim(p_project_id) = '' OR p_database_role IS NULL THEN
    RAISE EXCEPTION 'invalid project runtime principal binding';
  END IF;
  SELECT database_role INTO v_existing
  FROM "company-os".project_runtime_principals
  WHERE project_id = p_project_id
  FOR UPDATE;
  IF FOUND THEN
    IF v_existing IS DISTINCT FROM p_database_role THEN
      RAISE EXCEPTION 'project runtime principal is immutable';
    END IF;
    RETURN;
  END IF;
  IF EXISTS (
    SELECT 1
    FROM "company-os".project_runtime_principals
    WHERE database_role = p_database_role
      AND project_id <> p_project_id
  ) THEN
    RAISE EXCEPTION 'database role is already bound to another Company OS project';
  END IF;
  INSERT INTO "company-os".project_runtime_principals(project_id, database_role)
  VALUES (p_project_id, p_database_role);
END;
$$;

CREATE OR REPLACE FUNCTION "company-os".assert_project_runtime_principal(
  p_project_id text
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
SET search_path = pg_catalog
AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM "company-os".project_runtime_principals
    WHERE project_id = p_project_id
      AND database_role = session_user::name
  ) THEN
    RAISE EXCEPTION 'database role is not authorized for Company OS project';
  END IF;
  RETURN true;
END;
$$;

CREATE OR REPLACE FUNCTION "company-os".prepare_native_launch_attempt(
  p_project_id text,
  p_message_key text,
  p_owner text,
  p_claim_token text,
  p_lease_generation bigint,
  p_attempt_id text,
  p_dispatch_digest text,
  p_initial_prompt_sha256 text,
  p_at timestamptz
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
  v_command "company-os".commands%ROWTYPE;
  v_attempt "company-os".native_launch_attempts%ROWTYPE;
  v_revision bigint;
  v_content_sha256 text;
  v_event jsonb;
  v_action jsonb;
BEGIN
  IF p_project_id IS NULL OR p_message_key IS NULL
     OR p_owner IS NULL OR btrim(p_owner) = ''
     OR p_claim_token IS NULL OR p_claim_token = ''
     OR p_lease_generation < 1
     OR p_attempt_id IS NULL OR btrim(p_attempt_id) = ''
     OR p_dispatch_digest IS NULL
     OR p_dispatch_digest !~ '^[0-9a-f]{64}$'
     OR p_initial_prompt_sha256 IS NULL
     OR p_initial_prompt_sha256 !~ '^[0-9a-f]{64}$'
     OR p_at IS NULL THEN
    RAISE EXCEPTION 'invalid native launch preparation request';
  END IF;
  PERFORM "company-os".assert_project_runtime_principal(p_project_id);

  SELECT command.* INTO v_command
  FROM "company-os".commands AS command
  WHERE command.project_id = p_project_id AND command.message_key = p_message_key
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'federated command does not exist';
  END IF;
  -- Cancellation is authoritative even when a stale host still presents a
  -- valid-looking launch packet.
  IF v_command.status = 'cancelled' THEN
    RETURN jsonb_build_object(
      'status', 'cancelled',
      'message_key', p_message_key,
      'attempt_id', p_attempt_id
    );
  END IF;
  IF v_command.status <> 'leased'
     OR v_command.lease_owner <> p_owner
     OR v_command.lease_token_sha256 <> encode(
       public.digest(convert_to(p_claim_token, 'UTF8'), 'sha256'), 'hex'
     )
     OR v_command.lease_generation <> p_lease_generation
     OR v_command.lease_expires_at < p_at THEN
    RAISE EXCEPTION 'federated command lease fence does not match';
  END IF;

  v_action := v_command.payload_json::jsonb -> 'action';
  IF (v_action ->> 'kind') IS DISTINCT FROM 'persist-admission-intent'
     OR (v_action ->> 'attempt_id') IS DISTINCT FROM p_attempt_id THEN
    RAISE EXCEPTION 'native launch attempt does not bind the claimed command';
  END IF;
  v_content_sha256 := "company-os".native_launch_content_sha256(
    p_message_key,
    v_command.payload_sha256,
    p_attempt_id,
    p_dispatch_digest,
    p_initial_prompt_sha256
  );

  SELECT launch.* INTO v_attempt
  FROM "company-os".native_launch_attempts AS launch
  WHERE launch.project_id = p_project_id AND launch.message_key = p_message_key
  FOR UPDATE;
  IF FOUND THEN
    IF v_attempt.attempt_id <> p_attempt_id
       OR v_attempt.payload_sha256 <> v_command.payload_sha256
       OR v_attempt.content_sha256 <> v_content_sha256
       OR v_attempt.dispatch_digest <> p_dispatch_digest
       OR v_attempt.initial_prompt_sha256 <> p_initial_prompt_sha256 THEN
      RAISE EXCEPTION 'native launch attempt conflicts with different content';
    END IF;
    IF v_attempt.status = 'abandoned' THEN
      RAISE EXCEPTION 'legacy native launch attempt is quarantined; explicit resolution required';
    END IF;
    RETURN jsonb_build_object(
      'status', v_attempt.status,
      'message_key', p_message_key,
      'attempt_id', v_attempt.attempt_id,
      'content_sha256', v_attempt.content_sha256,
      'lease_generation', p_lease_generation,
      'task_id', v_attempt.task_id
    );
  END IF;

  SELECT current_revision + 1 INTO v_revision
  FROM "company-os".projects
  WHERE project_id = p_project_id
  FOR UPDATE;
  v_event := jsonb_build_object(
    'message_key', p_message_key,
    'attempt_id', p_attempt_id,
    'content_sha256', v_content_sha256,
    'payload_sha256', v_command.payload_sha256,
    'dispatch_digest', p_dispatch_digest,
    'initial_prompt_sha256', p_initial_prompt_sha256,
    'lease_generation', p_lease_generation
  );
  INSERT INTO "company-os".events(
    project_id, revision, event_type, payload_json, payload_sha256, created_at
  ) VALUES (
    p_project_id,
    v_revision,
    'federated_native_launch_prepared',
    v_event::text,
    encode(public.digest(convert_to(v_event::text, 'UTF8'), 'sha256'), 'hex'),
    p_at
  );
  INSERT INTO "company-os".native_launch_attempts(
    project_id, message_key, attempt_id, payload_sha256, content_sha256,
    dispatch_digest, initial_prompt_sha256, status, prepared_at, updated_at
  ) VALUES (
    p_project_id,
    p_message_key,
    p_attempt_id,
    v_command.payload_sha256,
    v_content_sha256,
    p_dispatch_digest,
    p_initial_prompt_sha256,
    'prepared',
    p_at,
    p_at
  );
  UPDATE "company-os".commands SET updated_revision = v_revision
  WHERE project_id = p_project_id AND message_key = p_message_key;
  UPDATE "company-os".projects SET current_revision = v_revision
  WHERE project_id = p_project_id;
  RETURN jsonb_build_object(
    'status', 'prepared',
    'message_key', p_message_key,
    'attempt_id', p_attempt_id,
    'content_sha256', v_content_sha256,
    'lease_generation', p_lease_generation
  );
END;
$$;

CREATE OR REPLACE FUNCTION "company-os".mark_native_launch_ambiguous(
  p_project_id text,
  p_message_key text,
  p_owner text,
  p_claim_token text,
  p_lease_generation bigint,
  p_attempt_id text,
  p_at timestamptz
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
  v_command "company-os".commands%ROWTYPE;
  v_attempt "company-os".native_launch_attempts%ROWTYPE;
  v_revision bigint;
  v_event jsonb;
BEGIN
  IF p_at IS NULL THEN
    RAISE EXCEPTION 'invalid native launch ambiguity time';
  END IF;
  PERFORM "company-os".assert_project_runtime_principal(p_project_id);
  SELECT * INTO v_command
  FROM "company-os".commands
  WHERE project_id = p_project_id AND message_key = p_message_key
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'federated command does not exist';
  END IF;
  IF v_command.status = 'cancelled' THEN
    RETURN jsonb_build_object('status', 'cancelled', 'message_key', p_message_key);
  END IF;
  IF v_command.status <> 'leased'
     OR v_command.lease_owner <> p_owner
     OR v_command.lease_token_sha256 <> encode(
       public.digest(convert_to(p_claim_token, 'UTF8'), 'sha256'), 'hex'
     )
     OR v_command.lease_generation <> p_lease_generation
     OR v_command.lease_expires_at < p_at THEN
    RAISE EXCEPTION 'federated command lease fence does not match';
  END IF;
  SELECT * INTO v_attempt
  FROM "company-os".native_launch_attempts
  WHERE project_id = p_project_id AND message_key = p_message_key
  FOR UPDATE;
  IF NOT FOUND OR v_attempt.attempt_id <> p_attempt_id THEN
    RAISE EXCEPTION 'native launch attempt is not prepared';
  END IF;
  IF v_attempt.status = 'ambiguous' THEN
    RETURN jsonb_build_object(
      'status', 'ambiguous', 'message_key', p_message_key, 'attempt_id', p_attempt_id
    );
  END IF;
  IF v_attempt.status <> 'prepared' THEN
    RAISE EXCEPTION 'native launch attempt cannot become ambiguous from its current state';
  END IF;
  SELECT current_revision + 1 INTO v_revision
  FROM "company-os".projects
  WHERE project_id = p_project_id
  FOR UPDATE;
  v_event := jsonb_build_object(
    'message_key', p_message_key,
    'attempt_id', p_attempt_id,
    'content_sha256', v_attempt.content_sha256,
    'lease_generation', p_lease_generation
  );
  INSERT INTO "company-os".events(
    project_id, revision, event_type, payload_json, payload_sha256, created_at
  ) VALUES (
    p_project_id,
    v_revision,
    'federated_native_launch_ambiguous',
    v_event::text,
    encode(public.digest(convert_to(v_event::text, 'UTF8'), 'sha256'), 'hex'),
    p_at
  );
  UPDATE "company-os".native_launch_attempts SET
    status = 'ambiguous', updated_at = p_at
  WHERE project_id = p_project_id AND message_key = p_message_key;
  UPDATE "company-os".commands SET updated_revision = v_revision
  WHERE project_id = p_project_id AND message_key = p_message_key;
  UPDATE "company-os".projects SET current_revision = v_revision
  WHERE project_id = p_project_id;
  RETURN jsonb_build_object(
    'status', 'ambiguous', 'message_key', p_message_key, 'attempt_id', p_attempt_id
  );
END;
$$;

-- Explicit recovery lease: normal claim/retry stays blocked while an
-- unresolved native launch exists, but a recovery worker may fence in a new
-- owner/generation without issuing a second host create.
CREATE OR REPLACE FUNCTION "company-os".reclaim_native_launch_attempt(
  p_project_id text,
  p_message_key text,
  p_owner text,
  p_claim_token text,
  p_expected_generation bigint,
  p_now timestamptz,
  p_lease_expires_at timestamptz
)
RETURNS TABLE(
  message_key text,
  payload_json text,
  payload_sha256 text,
  lease_generation bigint,
  attempt_id text,
  attempt_status text
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
  v_command "company-os".commands%ROWTYPE;
  v_attempt "company-os".native_launch_attempts%ROWTYPE;
  v_revision bigint;
  v_event jsonb;
BEGIN
  IF p_owner IS NULL OR btrim(p_owner) = ''
     OR p_claim_token IS NULL OR p_claim_token = ''
     OR p_expected_generation < 1
     OR p_now IS NULL
     OR p_lease_expires_at IS NULL
     OR p_lease_expires_at <= p_now THEN
    RAISE EXCEPTION 'invalid native launch recovery lease request';
  END IF;
  PERFORM "company-os".assert_project_runtime_principal(p_project_id);
  SELECT command.* INTO v_command
  FROM "company-os".commands AS command
  WHERE command.project_id = p_project_id AND command.message_key = p_message_key
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'federated command does not exist';
  END IF;
  IF v_command.status = 'cancelled' THEN
    RETURN QUERY SELECT p_message_key, NULL::text, NULL::text,
      v_command.lease_generation, NULL::text, 'cancelled';
    RETURN;
  END IF;
  IF v_command.status <> 'leased'
     OR v_command.lease_generation <> p_expected_generation
     OR v_command.lease_expires_at > p_now THEN
    RAISE EXCEPTION 'native launch recovery lease is not reclaimable';
  END IF;
  SELECT launch.* INTO v_attempt
  FROM "company-os".native_launch_attempts AS launch
  WHERE launch.project_id = p_project_id AND launch.message_key = p_message_key
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'native launch attempt does not exist';
  END IF;
  IF v_attempt.status NOT IN ('prepared', 'ambiguous', 'bound') THEN
    RAISE EXCEPTION 'native launch attempt is not recoverable';
  END IF;
  SELECT current_revision + 1 INTO v_revision
  FROM "company-os".projects
  WHERE project_id = p_project_id
  FOR UPDATE;
  v_event := jsonb_build_object(
    'message_key', p_message_key,
    'attempt_id', v_attempt.attempt_id,
    'previous_lease_generation', p_expected_generation,
    'lease_generation', v_command.lease_generation + 1,
    'lease_owner', p_owner,
    'lease_expires_at', p_lease_expires_at
  );
  INSERT INTO "company-os".events(
    project_id, revision, event_type, payload_json, payload_sha256, created_at
  ) VALUES (
    p_project_id,
    v_revision,
    'federated_native_launch_recovery_claimed',
    v_event::text,
    encode(public.digest(convert_to(v_event::text, 'UTF8'), 'sha256'), 'hex'),
    p_now
  );
  UPDATE "company-os".commands AS command SET
    lease_owner = p_owner,
    lease_token_sha256 = encode(
      public.digest(convert_to(p_claim_token, 'UTF8'), 'sha256'), 'hex'
    ),
    lease_generation = v_command.lease_generation + 1,
    lease_expires_at = p_lease_expires_at,
    updated_revision = v_revision
  WHERE command.project_id = p_project_id AND command.message_key = p_message_key;
  UPDATE "company-os".projects SET current_revision = v_revision
  WHERE project_id = p_project_id;
  RETURN QUERY SELECT
    v_command.message_key,
    v_command.payload_json,
    v_command.payload_sha256,
    v_command.lease_generation + 1,
    v_attempt.attempt_id,
    v_attempt.status;
END;
$$;

-- Recovery now requires typed absence evidence for a zero-candidate result;
-- migrate away from the earlier bare-array signature so [] cannot requeue a
-- command after a delayed or omitted host listing.
DROP FUNCTION IF EXISTS "company-os".recover_native_launch_attempt(
  text, text, text, text, bigint, text, text, timestamptz, timestamptz
);

CREATE OR REPLACE FUNCTION "company-os".recover_native_launch_attempt(
  p_project_id text,
  p_message_key text,
  p_owner text,
  p_claim_token text,
  p_lease_generation bigint,
  p_attempt_id text,
  p_candidates_json text,
  p_at timestamptz,
  p_requeue_at timestamptz DEFAULT NULL,
  p_absence_evidence_json text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
  v_command "company-os".commands%ROWTYPE;
  v_attempt "company-os".native_launch_attempts%ROWTYPE;
  v_revision bigint;
  v_candidates jsonb;
  v_candidate jsonb;
  v_count integer;
  v_event jsonb;
  v_candidate_text text;
  v_candidate_sha256 text;
  v_requeue_at timestamptz := COALESCE(p_requeue_at, p_at);
  v_existing_task_count integer;
  v_absence_evidence jsonb;
  v_absence_observed_at timestamptz;
BEGIN
  IF p_project_id IS NULL OR p_message_key IS NULL
     OR p_owner IS NULL OR btrim(p_owner) = ''
     OR p_claim_token IS NULL OR p_claim_token = ''
     OR p_lease_generation < 1
     OR p_attempt_id IS NULL OR btrim(p_attempt_id) = ''
     OR p_candidates_json IS NULL
     OR p_at IS NULL THEN
    RAISE EXCEPTION 'invalid native launch recovery request';
  END IF;
  PERFORM "company-os".assert_project_runtime_principal(p_project_id);
  IF v_requeue_at < p_at THEN
    RAISE EXCEPTION 'native launch requeue time cannot precede recovery time';
  END IF;
  SELECT * INTO v_command
  FROM "company-os".commands
  WHERE project_id = p_project_id AND message_key = p_message_key
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'federated command does not exist';
  END IF;
  -- Cancellation is checked before candidate parsing or lease validation so a
  -- late host result cannot outrank the authoritative cancel transition.
  IF v_command.status = 'cancelled' THEN
    RETURN jsonb_build_object('status', 'cancelled', 'message_key', p_message_key);
  END IF;
  IF v_command.status <> 'leased'
     OR v_command.lease_owner <> p_owner
     OR v_command.lease_token_sha256 <> encode(
       public.digest(convert_to(p_claim_token, 'UTF8'), 'sha256'), 'hex'
     )
     OR v_command.lease_generation <> p_lease_generation
     OR v_command.lease_expires_at < p_at THEN
    RAISE EXCEPTION 'federated command lease fence does not match';
  END IF;
  SELECT * INTO v_attempt
  FROM "company-os".native_launch_attempts
  WHERE project_id = p_project_id AND message_key = p_message_key
  FOR UPDATE;
  IF NOT FOUND OR v_attempt.attempt_id <> p_attempt_id THEN
    RAISE EXCEPTION 'native launch attempt is not prepared';
  END IF;

  BEGIN
    v_candidates := p_candidates_json::jsonb;
  EXCEPTION WHEN others THEN
    RAISE EXCEPTION 'native launch recovery candidates are not valid JSON';
  END;
  IF jsonb_typeof(v_candidates) IS DISTINCT FROM 'array' THEN
    RAISE EXCEPTION 'native launch recovery candidates must be a JSON array';
  END IF;

  v_count := jsonb_array_length(v_candidates);
  IF v_count <> 0 AND p_absence_evidence_json IS NOT NULL THEN
    RAISE EXCEPTION 'absence evidence is only valid for zero candidates';
  END IF;
  IF v_count = 0 THEN
    -- A host list/read with no rows is not authoritative: it may be truncated,
    -- timed out, stale, or race a create that completed after the read.  Record
    -- the typed observation for audit, but keep the attempt ambiguous and the
    -- command leased.  A separate operator-authorized transition is required
    -- before any abandon/requeue can be introduced.
    IF v_attempt.status = 'abandoned' THEN
      RETURN jsonb_build_object(
        'status', 'abandoned', 'message_key', p_message_key,
        'attempt_id', p_attempt_id, 'requeued', false, 'already_abandoned', true
      );
    END IF;
    IF v_attempt.status NOT IN ('prepared', 'ambiguous') THEN
      RAISE EXCEPTION 'zero-evidence recovery cannot resolve this launch attempt';
    END IF;
    IF p_absence_evidence_json IS NULL THEN
      RAISE EXCEPTION 'native launch absence evidence is required for zero candidates';
    END IF;
    BEGIN
      v_absence_evidence := p_absence_evidence_json::jsonb;
    EXCEPTION WHEN others THEN
      RAISE EXCEPTION 'native launch absence evidence is not valid JSON';
    END;
    IF jsonb_typeof(v_absence_evidence) IS DISTINCT FROM 'object'
       OR (v_absence_evidence ->> '$schema') IS DISTINCT FROM
         'company-os.codex-native-absence-evidence.v1'
       OR (v_absence_evidence ->> 'project_id') IS DISTINCT FROM p_project_id
       OR (v_absence_evidence ->> 'message_key') IS DISTINCT FROM p_message_key
       OR (v_absence_evidence ->> 'attempt_id') IS DISTINCT FROM p_attempt_id
       OR (v_absence_evidence ->> 'attempt_id_sha256') IS DISTINCT FROM encode(
         public.digest(convert_to(p_attempt_id, 'UTF8'), 'sha256'), 'hex'
       )
       OR (v_absence_evidence ->> 'message_key_sha256') IS DISTINCT FROM encode(
         public.digest(convert_to(p_message_key, 'UTF8'), 'sha256'), 'hex'
       )
       OR (v_absence_evidence ->> 'content_sha256') IS DISTINCT FROM v_attempt.content_sha256
       OR (v_absence_evidence ->> 'dispatch_digest') IS DISTINCT FROM v_attempt.dispatch_digest
       OR (v_absence_evidence -> 'listing_complete') IS DISTINCT FROM 'true'::jsonb
       OR (v_absence_evidence -> 'read_complete') IS DISTINCT FROM 'true'::jsonb
       OR jsonb_typeof(v_absence_evidence -> 'listed_task_ids') IS DISTINCT FROM 'array'
       OR jsonb_typeof(v_absence_evidence -> 'read_task_ids') IS DISTINCT FROM 'array'
       OR jsonb_array_length(v_absence_evidence -> 'listed_task_ids') <> 0
       OR jsonb_array_length(v_absence_evidence -> 'read_task_ids') <> 0
       OR COALESCE(v_absence_evidence ->> 'scenario', '') = ''
       OR (SELECT count(*) FROM jsonb_object_keys(v_absence_evidence)) <> 14 THEN
      RAISE EXCEPTION 'native launch absence evidence does not bind the prepared content';
    END IF;
    BEGIN
      v_absence_observed_at := (v_absence_evidence ->> 'observed_at')::timestamptz;
    EXCEPTION WHEN others THEN
      RAISE EXCEPTION 'native launch absence evidence timestamp is invalid';
    END;
    IF v_absence_observed_at IS NULL
       OR v_absence_observed_at > p_at
       OR p_at - v_absence_observed_at > interval '5 minutes' THEN
      RAISE EXCEPTION 'native launch absence evidence is stale';
    END IF;
    v_candidate_text := v_absence_evidence::text;
    v_candidate_sha256 := encode(
      public.digest(convert_to(v_candidate_text, 'UTF8'), 'sha256'), 'hex'
    );
    IF v_attempt.status = 'ambiguous'
       AND v_attempt.candidate_evidence_sha256 IS NOT NULL THEN
      IF v_attempt.candidate_evidence_sha256 <> v_candidate_sha256 THEN
        RAISE EXCEPTION 'native launch absence evidence conflicts with recorded observation';
      END IF;
      RETURN jsonb_build_object(
        'status', 'ambiguous', 'message_key', p_message_key,
        'attempt_id', p_attempt_id, 'blocked', true, 'requeued', false,
        'absence_evidence_sha256', v_candidate_sha256
      );
    END IF;
    SELECT current_revision + 1 INTO v_revision
    FROM "company-os".projects
    WHERE project_id = p_project_id
    FOR UPDATE;
    v_event := jsonb_build_object(
      'message_key', p_message_key,
      'attempt_id', p_attempt_id,
      'content_sha256', v_attempt.content_sha256,
      'absence_evidence_sha256', v_candidate_sha256,
      'blocked', true
    );
    INSERT INTO "company-os".events(
      project_id, revision, event_type, payload_json, payload_sha256, created_at
    ) VALUES (
      p_project_id,
      v_revision,
      'federated_native_launch_absence_observed',
      v_event::text,
      encode(public.digest(convert_to(v_event::text, 'UTF8'), 'sha256'), 'hex'),
      p_at
    );
    UPDATE "company-os".native_launch_attempts SET
      status = 'ambiguous',
      candidate_count = 0,
      candidate_evidence_json = v_candidate_text,
      candidate_evidence_sha256 = v_candidate_sha256,
      updated_at = p_at
    WHERE project_id = p_project_id AND message_key = p_message_key;
    UPDATE "company-os".commands SET updated_revision = v_revision
    WHERE project_id = p_project_id AND message_key = p_message_key;
    UPDATE "company-os".projects SET current_revision = v_revision
    WHERE project_id = p_project_id;
    RETURN jsonb_build_object(
      'status', 'ambiguous', 'message_key', p_message_key,
      'attempt_id', p_attempt_id, 'blocked', true, 'requeued', false,
      'absence_evidence_sha256', v_candidate_sha256
    );
  END IF;

  IF v_count > 1 THEN
    IF v_attempt.status = 'conflict' THEN
      RETURN jsonb_build_object(
        'status', 'conflict', 'message_key', p_message_key,
        'attempt_id', p_attempt_id, 'candidate_count', v_attempt.candidate_count
      );
    END IF;
    IF v_attempt.status NOT IN ('prepared', 'ambiguous') THEN
      RAISE EXCEPTION 'multiple-candidate recovery conflicts with terminal launch state';
    END IF;
    v_candidate_text := v_candidates::text;
    v_candidate_sha256 := encode(public.digest(convert_to(v_candidate_text, 'UTF8'), 'sha256'), 'hex');
    SELECT current_revision + 1 INTO v_revision
    FROM "company-os".projects
    WHERE project_id = p_project_id
    FOR UPDATE;
    v_event := jsonb_build_object(
      'message_key', p_message_key,
      'attempt_id', p_attempt_id,
      'candidate_count', v_count,
      'candidate_evidence_sha256', v_candidate_sha256
    );
    INSERT INTO "company-os".events(
      project_id, revision, event_type, payload_json, payload_sha256, created_at
    ) VALUES (
      p_project_id,
      v_revision,
      'federated_native_launch_conflict',
      v_event::text,
      encode(public.digest(convert_to(v_event::text, 'UTF8'), 'sha256'), 'hex'),
      p_at
    );
    UPDATE "company-os".native_launch_attempts SET
      status = 'conflict',
      candidate_count = v_count,
      candidate_evidence_json = v_candidate_text,
      candidate_evidence_sha256 = v_candidate_sha256,
      updated_at = p_at
    WHERE project_id = p_project_id AND message_key = p_message_key;
    UPDATE "company-os".commands SET updated_revision = v_revision
    WHERE project_id = p_project_id AND message_key = p_message_key;
    UPDATE "company-os".projects SET current_revision = v_revision
    WHERE project_id = p_project_id;
    RETURN jsonb_build_object(
      'status', 'conflict', 'message_key', p_message_key,
      'attempt_id', p_attempt_id, 'candidate_count', v_count,
      'candidate_evidence_sha256', v_candidate_sha256
    );
  END IF;

  v_candidate := v_candidates -> 0;
  IF jsonb_typeof(v_candidate) IS DISTINCT FROM 'object'
     OR (v_candidate ->> '$schema') IS DISTINCT FROM
       'company-os.codex-native-creation-receipt.v1'
     OR (v_candidate ->> 'status') IS DISTINCT FROM 'host_created'
     OR (v_candidate -> 'settlement_eligible') IS DISTINCT FROM 'true'::jsonb
     OR (v_candidate ->> 'message_key') IS DISTINCT FROM p_message_key
     OR (v_candidate ->> 'project_id') IS DISTINCT FROM p_project_id
     OR (v_candidate ->> 'cell_id') IS DISTINCT FROM
       (v_command.payload_json::jsonb #>> '{action,cell_id}')
     OR (v_candidate ->> 'tool') IS DISTINCT FROM 'codex_app__create_thread'
     OR COALESCE(v_candidate ->> 'task_id', '') = ''
     OR (v_candidate ->> 'task_id') IS DISTINCT FROM (v_candidate ->> 'thread_id')
     OR COALESCE(v_candidate ->> 'host_id', '') = ''
     OR (v_candidate ->> 'dispatch_digest') IS DISTINCT FROM v_attempt.dispatch_digest
     OR (v_candidate ->> 'initial_prompt_sha256') IS DISTINCT FROM v_attempt.initial_prompt_sha256 THEN
    RAISE EXCEPTION 'native launch recovery candidate does not bind the prepared content';
  END IF;
  IF v_attempt.status = 'bound' OR v_attempt.status = 'settled' THEN
    IF v_attempt.task_id IS DISTINCT FROM (v_candidate ->> 'task_id')
       OR v_attempt.creation_receipt_sha256 IS DISTINCT FROM encode(
         public.digest(convert_to(v_candidate::text, 'UTF8'), 'sha256'), 'hex'
       ) THEN
      RAISE EXCEPTION 'native launch recovery conflicts with the bound task';
    END IF;
    RETURN jsonb_build_object(
      'status', v_attempt.status, 'message_key', p_message_key,
      'attempt_id', p_attempt_id, 'task_id', v_attempt.task_id
    );
  END IF;
  IF v_attempt.status NOT IN ('prepared', 'ambiguous') THEN
    RAISE EXCEPTION 'single-task recovery cannot bind this launch attempt';
  END IF;
  SELECT count(*) INTO v_existing_task_count
  FROM "company-os".native_launch_attempts
  WHERE project_id = p_project_id
    AND task_id = (v_candidate ->> 'task_id')
    AND message_key <> p_message_key;
  IF v_existing_task_count > 0 THEN
    RAISE EXCEPTION 'native task is already bound to another launch attempt';
  END IF;
  v_candidate_text := v_candidate::text;
  v_candidate_sha256 := encode(public.digest(convert_to(v_candidate_text, 'UTF8'), 'sha256'), 'hex');
  SELECT current_revision + 1 INTO v_revision
  FROM "company-os".projects
  WHERE project_id = p_project_id
  FOR UPDATE;
  v_event := jsonb_build_object(
    'message_key', p_message_key,
    'attempt_id', p_attempt_id,
    'task_id', v_candidate ->> 'task_id',
    'thread_id', v_candidate ->> 'thread_id',
    'host_id', v_candidate ->> 'host_id',
    'creation_receipt_sha256', v_candidate_sha256
  );
  INSERT INTO "company-os".events(
    project_id, revision, event_type, payload_json, payload_sha256, created_at
  ) VALUES (
    p_project_id,
    v_revision,
    'federated_native_launch_bound',
    v_event::text,
    encode(public.digest(convert_to(v_event::text, 'UTF8'), 'sha256'), 'hex'),
    p_at
  );
  UPDATE "company-os".native_launch_attempts SET
    status = 'bound',
    candidate_count = 1,
    candidate_evidence_json = v_candidate_text,
    candidate_evidence_sha256 = v_candidate_sha256,
    task_id = v_candidate ->> 'task_id',
    thread_id = v_candidate ->> 'thread_id',
    host_id = v_candidate ->> 'host_id',
    creation_receipt_json = v_candidate_text,
    creation_receipt_sha256 = v_candidate_sha256,
    updated_at = p_at
  WHERE project_id = p_project_id AND message_key = p_message_key;
  UPDATE "company-os".commands SET updated_revision = v_revision
  WHERE project_id = p_project_id AND message_key = p_message_key;
  UPDATE "company-os".projects SET current_revision = v_revision
  WHERE project_id = p_project_id;
  RETURN jsonb_build_object(
    'status', 'bound', 'message_key', p_message_key,
    'attempt_id', p_attempt_id, 'task_id', v_candidate ->> 'task_id'
  );
END;
$$;

DROP FUNCTION IF EXISTS "company-os".abandon_native_launch_attempt(
  text, text, text, text, bigint, text, timestamptz, timestamptz
);

CREATE OR REPLACE FUNCTION "company-os".abandon_native_launch_attempt(
  p_project_id text,
  p_message_key text,
  p_owner text,
  p_claim_token text,
  p_lease_generation bigint,
  p_attempt_id text,
  p_at timestamptz,
  p_absence_evidence_json text,
  p_requeue_at timestamptz DEFAULT NULL
)
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
  SELECT "company-os".recover_native_launch_attempt(
    p_project_id,
    p_message_key,
    p_owner,
    p_claim_token,
    p_lease_generation,
    p_attempt_id,
    '[]',
    p_at,
    p_requeue_at,
    p_absence_evidence_json
  )
$$;

DROP TRIGGER IF EXISTS events_immutable ON "company-os".events;
CREATE TRIGGER events_immutable
BEFORE UPDATE OR DELETE ON "company-os".events
FOR EACH ROW EXECUTE FUNCTION "company-os".reject_immutable_change();

DROP TRIGGER IF EXISTS kernels_immutable ON "company-os".kernels;
CREATE TRIGGER kernels_immutable
BEFORE UPDATE OR DELETE ON "company-os".kernels
FOR EACH ROW EXECUTE FUNCTION "company-os".reject_immutable_change();

DROP TRIGGER IF EXISTS plans_immutable ON "company-os".reconciliation_plans;
CREATE TRIGGER plans_immutable
BEFORE UPDATE OR DELETE ON "company-os".reconciliation_plans
FOR EACH ROW EXECUTE FUNCTION "company-os".reject_immutable_change();

CREATE OR REPLACE FUNCTION "company-os".persist_reconciliation(p_record jsonb)
RETURNS TABLE(idempotent boolean, state_revision bigint, enqueued_commands integer)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
  v_project_id text := p_record ->> 'project_id';
  v_plan_key text := p_record ->> 'plan_key';
  v_stream_key text := p_record ->> 'stream_key';
  v_kernel_digest text := p_record ->> 'kernel_digest';
  v_request_sha text := p_record ->> 'request_sha256';
  v_plan_sha text := p_record ->> 'plan_sha256';
  v_snapshot_digest text := p_record ->> 'snapshot_digest';
  v_command_set_digest text := p_record ->> 'command_set_digest';
  v_created_at timestamptz := (p_record ->> 'created_at')::timestamptz;
  v_kernel jsonb := (p_record ->> 'kernel_json')::jsonb;
  v_request jsonb := (p_record ->> 'request_json')::jsonb;
  v_plan jsonb := (p_record ->> 'plan_json')::jsonb;
  v_revision bigint;
  v_existing "company-os".reconciliation_plans%ROWTYPE;
  v_cursor "company-os".observation_cursors%ROWTYPE;
  v_command jsonb;
  v_count integer := 0;
  v_actual_command_set_digest text;
BEGIN
  IF v_project_id IS NULL OR v_plan_key !~ '^[0-9a-f]{64}$'
     OR v_stream_key !~ '^[0-9a-f]{64}$'
     OR v_kernel_digest !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'invalid federated persistence identity';
  END IF;
  PERFORM "company-os".assert_project_runtime_principal(v_project_id);
  IF jsonb_typeof(p_record -> 'commands') <> 'array' THEN
    RAISE EXCEPTION 'commands must be a JSON array';
  END IF;
  IF v_kernel ->> 'kernel_digest' <> v_kernel_digest
     OR v_kernel #>> '{persistence,adapter}' <> 'postgresql'
     OR v_request ->> 'project_id' <> v_project_id
     OR v_request ->> 'kernel_digest' <> v_kernel_digest
     OR (v_request ->> 'generation')::bigint <> (p_record ->> 'generation')::bigint
     OR v_request ->> 'cycle_id' <> p_record ->> 'cycle_id'
     OR v_request ->> 'parent_runtime_id' <> p_record ->> 'parent_runtime_id'
     OR (v_request #>> '{observed_snapshot,last_event_cursor}')::bigint
        <> (p_record ->> 'snapshot_cursor')::bigint
     OR v_plan ->> 'kernel_digest' <> v_kernel_digest
     OR (v_plan ->> 'generation')::bigint <> (p_record ->> 'generation')::bigint
     OR v_plan ->> 'request_digest' <> p_record ->> 'request_digest'
     OR (v_plan ->> 'snapshot_cursor')::bigint <> (p_record ->> 'snapshot_cursor')::bigint
     OR v_plan ->> 'status' <> p_record ->> 'status'
     OR v_plan ->> 'plan_digest' <> p_record ->> 'plan_digest' THEN
    RAISE EXCEPTION 'federated kernel request or plan binding is invalid';
  END IF;
  IF (p_record ->> 'status') = 'blocked'
     AND jsonb_array_length(p_record -> 'commands') <> 0 THEN
    RAISE EXCEPTION 'blocked reconciliation cannot enqueue commands';
  END IF;
  SELECT encode(
    public.digest(
      convert_to(
        coalesce(string_agg(item ->> 'message_key', ',' ORDER BY item ->> 'message_key'), ''),
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  )
  INTO v_actual_command_set_digest
  FROM jsonb_array_elements(p_record -> 'commands') AS item;
  IF v_actual_command_set_digest <> v_command_set_digest THEN
    RAISE EXCEPTION 'command set digest does not verify';
  END IF;

  INSERT INTO "company-os".projects(project_id, created_at)
  VALUES (v_project_id, v_created_at)
  ON CONFLICT (project_id) DO NOTHING;
  SELECT current_revision INTO v_revision
  FROM "company-os".projects
  WHERE project_id = v_project_id
  FOR UPDATE;

  SELECT * INTO v_existing
  FROM "company-os".reconciliation_plans
  WHERE project_id = v_project_id AND plan_key = v_plan_key;
  IF FOUND THEN
    IF v_existing.request_sha256 <> v_request_sha
       OR v_existing.plan_sha256 <> v_plan_sha
       OR v_existing.command_set_digest <> v_command_set_digest THEN
      RAISE EXCEPTION 'federated plan key conflicts with different bytes';
    END IF;
    RETURN QUERY SELECT true, v_existing.state_revision, 0;
    RETURN;
  END IF;

  SELECT * INTO v_cursor
  FROM "company-os".observation_cursors
  WHERE project_id = v_project_id AND stream_key = v_stream_key;
  IF FOUND THEN
    IF (p_record ->> 'snapshot_cursor')::bigint < v_cursor.last_event_cursor THEN
      RAISE EXCEPTION 'observation cursor would move backwards';
    END IF;
    IF (p_record ->> 'snapshot_cursor')::bigint = v_cursor.last_event_cursor
       AND v_snapshot_digest <> v_cursor.snapshot_digest THEN
      RAISE EXCEPTION 'same observation cursor conflicts with different snapshot';
    END IF;
  END IF;

  v_revision := v_revision + 1;
  INSERT INTO "company-os".events(
    project_id, revision, event_type, payload_json, payload_sha256, created_at
  ) VALUES (
    v_project_id,
    v_revision,
    'federated_reconciliation_plan_persisted',
    p_record::text,
    encode(public.digest(convert_to(p_record::text, 'UTF8'), 'sha256'), 'hex'),
    v_created_at
  );

  INSERT INTO "company-os".kernels(
    project_id, kernel_digest, kernel_json, kernel_sha256, first_seen_revision
  ) VALUES (
    v_project_id,
    v_kernel_digest,
    p_record ->> 'kernel_json',
    p_record ->> 'kernel_sha256',
    v_revision
  )
  ON CONFLICT (project_id, kernel_digest) DO NOTHING;
  IF NOT EXISTS (
    SELECT 1 FROM "company-os".kernels
    WHERE project_id = v_project_id
      AND kernel_digest = v_kernel_digest
      AND kernel_sha256 = p_record ->> 'kernel_sha256'
  ) THEN
    RAISE EXCEPTION 'kernel digest conflicts with different bytes';
  END IF;

  INSERT INTO "company-os".reconciliation_plans(
    project_id, plan_key, stream_key, kernel_digest, generation, cycle_id,
    parent_runtime_id, request_digest, snapshot_cursor, snapshot_digest,
    status, request_json, request_sha256, plan_json, plan_sha256, plan_digest,
    command_set_digest, command_count, state_revision, created_at
  ) VALUES (
    v_project_id,
    v_plan_key,
    v_stream_key,
    v_kernel_digest,
    (p_record ->> 'generation')::bigint,
    p_record ->> 'cycle_id',
    p_record ->> 'parent_runtime_id',
    p_record ->> 'request_digest',
    (p_record ->> 'snapshot_cursor')::bigint,
    v_snapshot_digest,
    p_record ->> 'status',
    p_record ->> 'request_json',
    v_request_sha,
    p_record ->> 'plan_json',
    v_plan_sha,
    p_record ->> 'plan_digest',
    v_command_set_digest,
    jsonb_array_length(p_record -> 'commands'),
    v_revision,
    v_created_at
  );

  INSERT INTO "company-os".observation_cursors(
    project_id, stream_key, kernel_digest, generation, cycle_id,
    parent_runtime_id, last_event_cursor, snapshot_digest, updated_revision
  ) VALUES (
    v_project_id,
    v_stream_key,
    v_kernel_digest,
    (p_record ->> 'generation')::bigint,
    p_record ->> 'cycle_id',
    p_record ->> 'parent_runtime_id',
    (p_record ->> 'snapshot_cursor')::bigint,
    v_snapshot_digest,
    v_revision
  )
  ON CONFLICT (project_id, stream_key) DO UPDATE SET
    last_event_cursor = EXCLUDED.last_event_cursor,
    snapshot_digest = EXCLUDED.snapshot_digest,
    updated_revision = EXCLUDED.updated_revision
  WHERE "company-os".observation_cursors.last_event_cursor < EXCLUDED.last_event_cursor;

  FOR v_command IN SELECT value FROM jsonb_array_elements(p_record -> 'commands')
  LOOP
    IF (v_command ->> 'message_key') !~ '^[0-9a-f]{64}$'
       OR (v_command ->> 'payload_sha256') <> encode(
         public.digest(convert_to(v_command ->> 'payload_json', 'UTF8'), 'sha256'), 'hex'
       )
       OR (v_command ->> 'payload_json')::jsonb ->> 'command_digest'
          <> v_command ->> 'message_key'
       OR (v_command ->> 'payload_json')::jsonb ->> 'project_id' <> v_project_id
       OR (v_command ->> 'payload_json')::jsonb ->> 'kernel_digest' <> v_kernel_digest
       OR ((v_command ->> 'payload_json')::jsonb ->> 'generation')::bigint
          <> (p_record ->> 'generation')::bigint
       OR (v_command ->> 'payload_json')::jsonb ->> 'cycle_id'
          <> p_record ->> 'cycle_id'
       OR (v_command ->> 'payload_json')::jsonb ->> 'parent_runtime_id'
          <> p_record ->> 'parent_runtime_id'
       OR (v_command ->> 'payload_json')::jsonb ->> 'plan_digest'
          <> p_record ->> 'plan_digest'
       OR ((v_command ->> 'payload_json')::jsonb ->> 'plan_order')::integer
          <> (v_command ->> 'plan_order')::integer THEN
      RAISE EXCEPTION 'federated command identity or payload digest is invalid';
    END IF;
    INSERT INTO "company-os".commands(
      project_id, message_key, plan_key, plan_order, payload_json,
      payload_sha256, status, created_revision, updated_revision
    ) VALUES (
      v_project_id,
      v_command ->> 'message_key',
      v_plan_key,
      (v_command ->> 'plan_order')::integer,
      v_command ->> 'payload_json',
      v_command ->> 'payload_sha256',
      'pending',
      v_revision,
      v_revision
    );
    v_count := v_count + 1;
  END LOOP;
  UPDATE "company-os".projects
  SET current_revision = v_revision
  WHERE project_id = v_project_id;
  RETURN QUERY SELECT false, v_revision, v_count;
END;
$$;

-- PostgreSQL cannot replace a function when its OUT columns change. Acquire
-- this one-time migration marker atomically so an old signature is dropped
-- exactly once; later schema replays use CREATE OR REPLACE and preserve every
-- project role's explicit EXECUTE ACL.
DO $company_os_claim_command_v2$
DECLARE
  v_acquired text;
BEGIN
  INSERT INTO "company-os".runtime_schema_migrations(migration_key, applied_at)
  VALUES ('claim-command-signature-v2', transaction_timestamp())
  ON CONFLICT DO NOTHING
  RETURNING migration_key INTO v_acquired;
  IF v_acquired IS NOT NULL THEN
    DROP FUNCTION IF EXISTS "company-os".claim_command(
      text, text, text, timestamptz, timestamptz, text
    );
  END IF;
END;
$company_os_claim_command_v2$;

CREATE OR REPLACE FUNCTION "company-os".claim_command(
  p_project_id text,
  p_owner text,
  p_claim_token text,
  p_now timestamptz,
  p_lease_expires_at timestamptz,
  p_message_key text DEFAULT NULL
)
RETURNS TABLE(
  message_key text,
  payload_json text,
  payload_sha256 text,
  lease_generation bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
  v_command "company-os".commands%ROWTYPE;
  v_revision bigint;
BEGIN
  IF p_owner IS NULL OR btrim(p_owner) = '' OR p_claim_token IS NULL OR p_claim_token = ''
     OR p_lease_expires_at <= p_now THEN
    RAISE EXCEPTION 'invalid federated command lease request';
  END IF;
  PERFORM "company-os".assert_project_runtime_principal(p_project_id);
  SELECT * INTO v_command
  FROM "company-os".commands AS candidate
  WHERE candidate.project_id = p_project_id
    AND (p_message_key IS NULL OR candidate.message_key = p_message_key)
    AND (candidate.not_before IS NULL OR candidate.not_before <= p_now)
    AND (
      candidate.status IN ('pending', 'failed')
      OR (candidate.status = 'leased' AND candidate.lease_expires_at <= p_now)
    )
    -- A native launch has an external-effect crash boundary.  Prepared,
    -- ambiguous, bound, abandoned, and conflict attempts remain authoritative until an
    -- explicit recovery/settlement transition; ordinary lease reclaim must
    -- not issue another host create for the same content.
    AND (
      (candidate.payload_json::jsonb #>> '{action,kind}') IS DISTINCT FROM
        'persist-admission-intent'
      OR NOT EXISTS (
        SELECT 1
        FROM "company-os".native_launch_attempts AS launch
        WHERE launch.project_id = candidate.project_id
          AND launch.message_key = candidate.message_key
          AND launch.status IN ('prepared', 'ambiguous', 'bound', 'abandoned', 'conflict')
      )
    )
  ORDER BY candidate.created_revision, candidate.plan_order, candidate.message_key
  FOR UPDATE SKIP LOCKED
  LIMIT 1;
  IF NOT FOUND THEN
    RETURN;
  END IF;
  SELECT current_revision + 1 INTO v_revision
  FROM "company-os".projects
  WHERE project_id = p_project_id
  FOR UPDATE;
  INSERT INTO "company-os".events(
    project_id, revision, event_type, payload_json, payload_sha256, created_at
  )
  SELECT
    p_project_id,
    v_revision,
    'federated_runtime_command_claimed',
    jsonb_build_object(
      'message_key', v_command.message_key,
      'lease_owner', p_owner,
      'lease_generation', v_command.lease_generation + 1,
      'lease_expires_at', p_lease_expires_at
    )::text,
    encode(public.digest(convert_to(jsonb_build_object(
      'message_key', v_command.message_key,
      'lease_owner', p_owner,
      'lease_generation', v_command.lease_generation + 1,
      'lease_expires_at', p_lease_expires_at
    )::text, 'UTF8'), 'sha256'), 'hex'),
    p_now;
  UPDATE "company-os".commands AS target SET
    status = 'leased',
    attempt_count = target.attempt_count + 1,
    lease_owner = p_owner,
    lease_token_sha256 = encode(
      public.digest(convert_to(p_claim_token, 'UTF8'), 'sha256'), 'hex'
    ),
    lease_generation = target.lease_generation + 1,
    lease_expires_at = p_lease_expires_at,
    terminal_receipt_json = NULL,
    terminal_receipt_sha256 = NULL,
    updated_revision = v_revision
  WHERE target.project_id = p_project_id AND target.message_key = v_command.message_key;
  UPDATE "company-os".projects SET current_revision = v_revision
  WHERE project_id = p_project_id;
  RETURN QUERY
  SELECT
    v_command.message_key,
    v_command.payload_json,
    v_command.payload_sha256,
    v_command.lease_generation + 1;
END;
$$;

CREATE OR REPLACE FUNCTION "company-os".settle_command(
  p_project_id text,
  p_message_key text,
  p_owner text,
  p_claim_token text,
  p_lease_generation bigint,
  p_outcome text,
  p_receipt_json text,
  p_receipt_sha256 text,
  p_at timestamptz
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
  v_command "company-os".commands%ROWTYPE;
  v_attempt "company-os".native_launch_attempts%ROWTYPE;
  v_revision bigint;
  v_receipt jsonb;
BEGIN
  IF p_outcome NOT IN ('succeeded', 'failed')
     OR p_receipt_sha256 <> encode(
       public.digest(convert_to(p_receipt_json, 'UTF8'), 'sha256'), 'hex'
     ) THEN
    RAISE EXCEPTION 'invalid federated command settlement';
  END IF;
  PERFORM "company-os".assert_project_runtime_principal(p_project_id);
  SELECT * INTO v_command
  FROM "company-os".commands
  WHERE project_id = p_project_id AND message_key = p_message_key
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'federated command does not exist';
  END IF;
  IF v_command.status = 'cancelled' THEN
    RETURN 'cancelled';
  END IF;
  IF p_outcome = 'failed'
     AND (v_command.payload_json::jsonb #>> '{action,kind}') = 'persist-admission-intent' THEN
    SELECT * INTO v_attempt
    FROM "company-os".native_launch_attempts
    WHERE project_id = p_project_id AND message_key = p_message_key
    FOR UPDATE;
    IF FOUND AND v_attempt.status <> 'cancelled' THEN
      RAISE EXCEPTION 'native launch attempt must be explicitly recovered before failure settlement';
    END IF;
  END IF;
  IF p_outcome = 'succeeded'
     AND (v_command.payload_json::jsonb #>> '{action,kind}') = 'persist-admission-intent' THEN
    BEGIN
      v_receipt := p_receipt_json::jsonb;
    EXCEPTION WHEN others THEN
      RAISE EXCEPTION 'native creation receipt is not valid JSON';
    END;
    IF jsonb_typeof(v_receipt) IS DISTINCT FROM 'object'
       OR (v_receipt ->> '$schema') IS DISTINCT FROM 'company-os.codex-native-creation-receipt.v1'
       OR (v_receipt ->> 'status') IS DISTINCT FROM 'host_created'
       OR (v_receipt -> 'settlement_eligible') IS DISTINCT FROM 'true'::jsonb
       OR (v_receipt ->> 'message_key') IS DISTINCT FROM p_message_key
       OR (v_receipt ->> 'project_id') IS DISTINCT FROM p_project_id
       OR (v_receipt ->> 'cell_id') IS DISTINCT FROM
         (v_command.payload_json::jsonb #>> '{action,cell_id}')
       OR (v_receipt ->> 'tool') IS DISTINCT FROM 'codex_app__create_thread'
       OR COALESCE(v_receipt ->> 'task_id', '') = ''
       OR (v_receipt ->> 'task_id') IS DISTINCT FROM (v_receipt ->> 'thread_id')
       OR COALESCE(v_receipt ->> 'host_id', '') = ''
       OR COALESCE(v_receipt ->> 'dispatch_digest', '') !~ '^[0-9a-f]{64}$'
       OR COALESCE(v_receipt ->> 'initial_prompt_sha256', '') !~ '^[0-9a-f]{64}$' THEN
      RAISE EXCEPTION 'native creation receipt does not bind the claimed command';
    END IF;
    SELECT * INTO v_attempt
    FROM "company-os".native_launch_attempts
    WHERE project_id = p_project_id AND message_key = p_message_key
    FOR UPDATE;
    IF NOT FOUND
       OR v_attempt.status <> 'bound'
       OR v_attempt.attempt_id IS DISTINCT FROM
         (v_command.payload_json::jsonb #>> '{action,attempt_id}')
       OR v_attempt.payload_sha256 <> v_command.payload_sha256
       OR v_attempt.dispatch_digest IS DISTINCT FROM (v_receipt ->> 'dispatch_digest')
       OR v_attempt.initial_prompt_sha256 IS DISTINCT FROM
         (v_receipt ->> 'initial_prompt_sha256')
       OR v_attempt.task_id IS DISTINCT FROM (v_receipt ->> 'task_id')
       OR v_attempt.thread_id IS DISTINCT FROM (v_receipt ->> 'thread_id')
       OR v_attempt.host_id IS DISTINCT FROM (v_receipt ->> 'host_id')
       OR v_attempt.creation_receipt_json::jsonb IS DISTINCT FROM v_receipt THEN
      RAISE EXCEPTION 'native launch attempt is not bound to the verified creation receipt';
    END IF;
  END IF;
  IF v_command.status <> 'leased'
     OR v_command.lease_owner <> p_owner
     OR v_command.lease_token_sha256 <> encode(
       public.digest(convert_to(p_claim_token, 'UTF8'), 'sha256'), 'hex'
     )
     OR v_command.lease_generation <> p_lease_generation
     OR v_command.lease_expires_at < p_at THEN
    RAISE EXCEPTION 'federated command lease fence does not match';
  END IF;
  SELECT current_revision + 1 INTO v_revision
  FROM "company-os".projects
  WHERE project_id = p_project_id
  FOR UPDATE;
  INSERT INTO "company-os".events(
    project_id, revision, event_type, payload_json, payload_sha256, created_at
  )
  SELECT
    p_project_id,
    v_revision,
    'federated_runtime_command_settled',
    jsonb_build_object(
      'message_key', p_message_key,
      'lease_generation', p_lease_generation,
      'outcome', p_outcome,
      'receipt_sha256', p_receipt_sha256
    )::text,
    encode(public.digest(convert_to(jsonb_build_object(
      'message_key', p_message_key,
      'lease_generation', p_lease_generation,
      'outcome', p_outcome,
      'receipt_sha256', p_receipt_sha256
    )::text, 'UTF8'), 'sha256'), 'hex'),
    p_at;
  UPDATE "company-os".commands SET
    status = p_outcome,
    lease_owner = NULL,
    lease_token_sha256 = NULL,
    lease_expires_at = NULL,
    terminal_receipt_json = p_receipt_json,
    terminal_receipt_sha256 = p_receipt_sha256,
    updated_revision = v_revision
  WHERE project_id = p_project_id AND message_key = p_message_key;
  IF p_outcome = 'succeeded'
     AND (v_command.payload_json::jsonb #>> '{action,kind}') = 'persist-admission-intent' THEN
    UPDATE "company-os".native_launch_attempts SET
      status = 'settled', updated_at = p_at
    WHERE project_id = p_project_id AND message_key = p_message_key;
  END IF;
  UPDATE "company-os".projects SET current_revision = v_revision
  WHERE project_id = p_project_id;
  RETURN p_outcome;
END;
$$;

-- The cancellation fence grew from the original four-argument helper.  Drop
-- the old signature so an in-place migration cannot leave an unfenced escape
-- hatch alongside the current authority function.
DROP FUNCTION IF EXISTS "company-os".cancel_command(
  text, text, text, timestamptz
);

CREATE OR REPLACE FUNCTION "company-os".cancel_command(
  p_project_id text,
  p_message_key text,
  p_owner text,
  p_claim_token text,
  p_lease_generation bigint,
  p_reason text,
  p_at timestamptz
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
  v_command "company-os".commands%ROWTYPE;
  v_revision bigint;
  v_receipt text;
BEGIN
  IF p_reason IS NULL OR btrim(p_reason) = ''
     OR p_owner IS NULL OR btrim(p_owner) = ''
     OR p_claim_token IS NULL OR p_claim_token = ''
     OR p_lease_generation < 1
     OR p_at IS NULL THEN
    RAISE EXCEPTION 'cancellation reason is required';
  END IF;
  PERFORM "company-os".assert_project_runtime_principal(p_project_id);
  SELECT * INTO v_command
  FROM "company-os".commands
  WHERE project_id = p_project_id AND message_key = p_message_key
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'federated command does not exist';
  END IF;
  IF v_command.status = 'cancelled' THEN
    RETURN 'cancelled';
  END IF;
  IF v_command.status = 'succeeded' THEN
    RAISE EXCEPTION 'succeeded federated command cannot be cancelled';
  END IF;
  IF v_command.status <> 'leased'
     OR v_command.lease_owner <> p_owner
     OR v_command.lease_token_sha256 <> encode(
       public.digest(convert_to(p_claim_token, 'UTF8'), 'sha256'), 'hex'
     )
     OR v_command.lease_generation <> p_lease_generation
     OR v_command.lease_expires_at < p_at THEN
    RAISE EXCEPTION 'federated command cancellation lease fence does not match';
  END IF;
  SELECT current_revision + 1 INTO v_revision
  FROM "company-os".projects
  WHERE project_id = p_project_id
  FOR UPDATE;
  v_receipt := jsonb_build_object(
    'schema', 'company-os.federated-command-cancellation.v1',
    'reason', p_reason,
    'at', p_at,
    'superseded_lease_generation', v_command.lease_generation
  )::text;
  INSERT INTO "company-os".events(
    project_id, revision, event_type, payload_json, payload_sha256, created_at
  ) VALUES (
    p_project_id,
    v_revision,
    'federated_runtime_command_cancelled',
    v_receipt,
    encode(public.digest(convert_to(v_receipt, 'UTF8'), 'sha256'), 'hex'),
    p_at
  );
  UPDATE "company-os".commands SET
    status = 'cancelled',
    lease_owner = NULL,
    lease_token_sha256 = NULL,
    lease_expires_at = NULL,
    terminal_receipt_json = v_receipt,
    terminal_receipt_sha256 = encode(
      public.digest(convert_to(v_receipt, 'UTF8'), 'sha256'), 'hex'
    ),
    updated_revision = v_revision
  WHERE project_id = p_project_id AND message_key = p_message_key;
  UPDATE "company-os".native_launch_attempts SET
    status = 'cancelled', updated_at = p_at
  WHERE project_id = p_project_id
    AND message_key = p_message_key
    AND status IN ('prepared', 'ambiguous', 'bound', 'conflict');
  UPDATE "company-os".projects SET current_revision = v_revision
  WHERE project_id = p_project_id;
  RETURN 'cancelled';
END;
$$;

CREATE OR REPLACE FUNCTION "company-os".audit_project(p_project_id text)
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = pg_catalog
AS $$
WITH authorized AS MATERIALIZED (
  SELECT "company-os".assert_project_runtime_principal(p_project_id) AS allowed
), project AS (
  SELECT current_revision FROM "company-os".projects WHERE project_id = p_project_id
), counts AS (
  SELECT
    (SELECT count(*) FROM "company-os".events WHERE project_id = p_project_id) AS events,
    (SELECT count(*) FROM "company-os".reconciliation_plans WHERE project_id = p_project_id) AS plans,
    (SELECT count(*) FROM "company-os".commands WHERE project_id = p_project_id) AS commands,
    (SELECT count(*) FROM "company-os".commands
      WHERE project_id = p_project_id AND status IN ('pending', 'leased')) AS open_commands,
    (SELECT count(*) FROM "company-os".commands
      WHERE project_id = p_project_id AND (
        (status = 'leased' AND (lease_owner IS NULL OR lease_token_sha256 IS NULL OR lease_expires_at IS NULL))
        OR (status <> 'leased' AND (lease_owner IS NOT NULL OR lease_token_sha256 IS NOT NULL OR lease_expires_at IS NOT NULL))
      )) AS lease_errors,
    (SELECT count(*) FROM "company-os".native_launch_attempts
      WHERE project_id = p_project_id
        AND status IN ('prepared', 'ambiguous', 'bound', 'conflict')) AS native_launch_blocks,
    (SELECT count(*) FROM "company-os".native_launch_attempts AS launch
      LEFT JOIN "company-os".commands AS command
        ON command.project_id = launch.project_id
       AND command.message_key = launch.message_key
      WHERE launch.project_id = p_project_id
        AND (
          command.message_key IS NULL
          OR launch.payload_sha256 <> command.payload_sha256
          OR (command.status = 'failed' AND launch.status <> 'cancelled')
          OR (launch.status IN ('bound', 'settled')
              AND (launch.task_id IS NULL OR launch.thread_id IS NULL
                   OR launch.host_id IS NULL OR launch.creation_receipt_json IS NULL))
        )) AS native_launch_errors,
    (SELECT count(*) FROM "company-os".native_launch_legacy_quarantine
      WHERE project_id = p_project_id) AS native_launch_quarantines,
    (SELECT count(*) FROM "company-os".reconciliation_plans AS p
      WHERE p.project_id = p_project_id AND p.command_count <>
        (SELECT count(*) FROM "company-os".commands AS c
         WHERE c.project_id = p.project_id AND c.plan_key = p.plan_key)) AS command_set_errors
)
SELECT jsonb_build_object(
  'ok',
  EXISTS (SELECT 1 FROM project)
    AND (SELECT events FROM counts) = (SELECT current_revision FROM project)
    AND (SELECT lease_errors FROM counts) = 0
    AND (SELECT native_launch_errors FROM counts) = 0
    AND (SELECT native_launch_quarantines FROM counts) = 0
    AND (SELECT command_set_errors FROM counts) = 0,
  'current_revision', (SELECT current_revision FROM project),
  'events', (SELECT events FROM counts),
  'plans', (SELECT plans FROM counts),
  'commands', (SELECT commands FROM counts),
  'open_commands', (SELECT open_commands FROM counts),
  'lease_errors', (SELECT lease_errors FROM counts),
  'native_launch_blocks', (SELECT native_launch_blocks FROM counts),
  'native_launch_errors', (SELECT native_launch_errors FROM counts),
  'native_launch_quarantines', (SELECT native_launch_quarantines FROM counts),
  'command_set_errors', (SELECT command_set_errors FROM counts)
)
FROM authorized;
$$;

REVOKE ALL ON SCHEMA "company-os" FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA "company-os" FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA "company-os" FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA "company-os"
  REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA "company-os"
  REVOKE ALL ON FUNCTIONS FROM PUBLIC;

-- An upgrade can replace a function signature before the protected owner is
-- bootstrapped. Rebuild every already-bound runtime role's closed API inside
-- the same migration transaction so the first v2 upgrade cannot strand a
-- project with a missing claim permission. The project principal table is the
-- sole allowlist; a missing database role aborts the migration instead of
-- silently weakening or partially applying authority.
DO $company_os_restore_bound_runtime_acl$
DECLARE
  v_role name;
BEGIN
  FOR v_role IN
    SELECT database_role
    FROM "company-os".project_runtime_principals
    ORDER BY database_role::text
  LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_roles r
      WHERE r.rolname = v_role
        AND r.rolcanlogin
        AND NOT r.rolinherit
        AND NOT r.rolsuper
        AND NOT r.rolcreaterole
        AND NOT r.rolcreatedb
        AND NOT r.rolreplication
        AND NOT r.rolbypassrls
        AND NOT EXISTS (
          SELECT 1 FROM pg_auth_members am WHERE am.member = r.oid
        )
    ) THEN
      RAISE EXCEPTION 'bound Company OS runtime role must be a restricted direct NOINHERIT login with zero role memberships';
    END IF;
    EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA "company-os" FROM %I', v_role);
    EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA "company-os" FROM %I', v_role);
    EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA "company-os" FROM %I', v_role);
    EXECUTE format('GRANT USAGE ON SCHEMA "company-os" TO %I', v_role);
    EXECUTE format('GRANT EXECUTE ON FUNCTION "company-os".persist_reconciliation(jsonb) TO %I', v_role);
    EXECUTE format('GRANT EXECUTE ON FUNCTION "company-os".claim_command(text,text,text,timestamptz,timestamptz,text) TO %I', v_role);
    EXECUTE format('GRANT EXECUTE ON FUNCTION "company-os".prepare_native_launch_attempt(text,text,text,text,bigint,text,text,text,timestamptz) TO %I', v_role);
    EXECUTE format('GRANT EXECUTE ON FUNCTION "company-os".mark_native_launch_ambiguous(text,text,text,text,bigint,text,timestamptz) TO %I', v_role);
    EXECUTE format('GRANT EXECUTE ON FUNCTION "company-os".reclaim_native_launch_attempt(text,text,text,text,bigint,timestamptz,timestamptz) TO %I', v_role);
    EXECUTE format('GRANT EXECUTE ON FUNCTION "company-os".recover_native_launch_attempt(text,text,text,text,bigint,text,text,timestamptz,timestamptz,text) TO %I', v_role);
    EXECUTE format('GRANT EXECUTE ON FUNCTION "company-os".abandon_native_launch_attempt(text,text,text,text,bigint,text,timestamptz,text,timestamptz) TO %I', v_role);
    EXECUTE format('GRANT EXECUTE ON FUNCTION "company-os".settle_command(text,text,text,text,bigint,text,text,text,timestamptz) TO %I', v_role);
    EXECUTE format('GRANT EXECUTE ON FUNCTION "company-os".cancel_command(text,text,text,text,bigint,text,timestamptz) TO %I', v_role);
    EXECUTE format('GRANT EXECUTE ON FUNCTION "company-os".audit_project(text) TO %I', v_role);
  END LOOP;
END;
$company_os_restore_bound_runtime_acl$;
