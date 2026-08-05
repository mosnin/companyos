-- Company OS federated runtime authority for PostgreSQL 15+.
-- The quoted schema matches the canonical kernel persistence identifier.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS "company-os";

CREATE TABLE IF NOT EXISTS "company-os".projects (
  project_id text PRIMARY KEY,
  current_revision bigint NOT NULL DEFAULT 0 CHECK (current_revision >= 0),
  created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS "company-os".events (
  project_id text NOT NULL REFERENCES "company-os".projects(project_id),
  revision bigint NOT NULL CHECK (revision > 0),
  event_type text NOT NULL,
  payload_json text NOT NULL,
  payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL,
  PRIMARY KEY (project_id, revision),
  CHECK (
    payload_sha256 = encode(digest(convert_to(payload_json, 'UTF8'), 'sha256'), 'hex')
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
    kernel_sha256 = encode(digest(convert_to(kernel_json, 'UTF8'), 'sha256'), 'hex')
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
    request_sha256 = encode(digest(convert_to(request_json, 'UTF8'), 'sha256'), 'hex')
  ),
  CHECK (
    plan_sha256 = encode(digest(convert_to(plan_json, 'UTF8'), 'sha256'), 'hex')
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
    payload_sha256 = encode(digest(convert_to(payload_json, 'UTF8'), 'sha256'), 'hex')
  ),
  CHECK (
    terminal_receipt_json IS NULL
    OR terminal_receipt_sha256 = encode(
      digest(convert_to(terminal_receipt_json, 'UTF8'), 'sha256'), 'hex'
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

CREATE INDEX IF NOT EXISTS commands_claimable_idx
  ON "company-os".commands(project_id, status, not_before, created_revision, plan_order);
CREATE INDEX IF NOT EXISTS commands_expired_lease_idx
  ON "company-os".commands(project_id, lease_expires_at)
  WHERE status = 'leased';
CREATE INDEX IF NOT EXISTS plans_revision_idx
  ON "company-os".reconciliation_plans(project_id, state_revision);

CREATE OR REPLACE FUNCTION "company-os".reject_immutable_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'immutable Company OS history cannot be changed';
END;
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
    digest(
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
    encode(digest(convert_to(p_record::text, 'UTF8'), 'sha256'), 'hex'),
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
         digest(convert_to(v_command ->> 'payload_json', 'UTF8'), 'sha256'), 'hex'
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

CREATE OR REPLACE FUNCTION "company-os".claim_command(
  p_project_id text,
  p_owner text,
  p_claim_token text,
  p_now timestamptz,
  p_lease_expires_at timestamptz,
  p_message_key text DEFAULT NULL
)
RETURNS TABLE(message_key text, payload_json text, lease_generation bigint)
LANGUAGE plpgsql
AS $$
DECLARE
  v_command "company-os".commands%ROWTYPE;
  v_revision bigint;
BEGIN
  IF p_owner IS NULL OR btrim(p_owner) = '' OR p_claim_token IS NULL OR p_claim_token = ''
     OR p_lease_expires_at <= p_now THEN
    RAISE EXCEPTION 'invalid federated command lease request';
  END IF;
  SELECT * INTO v_command
  FROM "company-os".commands AS candidate
  WHERE candidate.project_id = p_project_id
    AND (p_message_key IS NULL OR candidate.message_key = p_message_key)
    AND (candidate.not_before IS NULL OR candidate.not_before <= p_now)
    AND (
      candidate.status IN ('pending', 'failed')
      OR (candidate.status = 'leased' AND candidate.lease_expires_at <= p_now)
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
    encode(digest(convert_to(jsonb_build_object(
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
      digest(convert_to(p_claim_token, 'UTF8'), 'sha256'), 'hex'
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
  SELECT v_command.message_key, v_command.payload_json, v_command.lease_generation + 1;
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
AS $$
DECLARE
  v_command "company-os".commands%ROWTYPE;
  v_revision bigint;
BEGIN
  IF p_outcome NOT IN ('succeeded', 'failed')
     OR p_receipt_sha256 <> encode(
       digest(convert_to(p_receipt_json, 'UTF8'), 'sha256'), 'hex'
     ) THEN
    RAISE EXCEPTION 'invalid federated command settlement';
  END IF;
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
  IF v_command.status <> 'leased'
     OR v_command.lease_owner <> p_owner
     OR v_command.lease_token_sha256 <> encode(
       digest(convert_to(p_claim_token, 'UTF8'), 'sha256'), 'hex'
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
    encode(digest(convert_to(jsonb_build_object(
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
  UPDATE "company-os".projects SET current_revision = v_revision
  WHERE project_id = p_project_id;
  RETURN p_outcome;
END;
$$;

CREATE OR REPLACE FUNCTION "company-os".cancel_command(
  p_project_id text,
  p_message_key text,
  p_reason text,
  p_at timestamptz
)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  v_command "company-os".commands%ROWTYPE;
  v_revision bigint;
  v_receipt text;
BEGIN
  IF p_reason IS NULL OR btrim(p_reason) = '' THEN
    RAISE EXCEPTION 'cancellation reason is required';
  END IF;
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
    encode(digest(convert_to(v_receipt, 'UTF8'), 'sha256'), 'hex'),
    p_at
  );
  UPDATE "company-os".commands SET
    status = 'cancelled',
    lease_owner = NULL,
    lease_token_sha256 = NULL,
    lease_expires_at = NULL,
    terminal_receipt_json = v_receipt,
    terminal_receipt_sha256 = encode(
      digest(convert_to(v_receipt, 'UTF8'), 'sha256'), 'hex'
    ),
    updated_revision = v_revision
  WHERE project_id = p_project_id AND message_key = p_message_key;
  UPDATE "company-os".projects SET current_revision = v_revision
  WHERE project_id = p_project_id;
  RETURN 'cancelled';
END;
$$;

CREATE OR REPLACE FUNCTION "company-os".audit_project(p_project_id text)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
WITH project AS (
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
    AND (SELECT command_set_errors FROM counts) = 0,
  'current_revision', (SELECT current_revision FROM project),
  'events', (SELECT events FROM counts),
  'plans', (SELECT plans FROM counts),
  'commands', (SELECT commands FROM counts),
  'open_commands', (SELECT open_commands FROM counts),
  'lease_errors', (SELECT lease_errors FROM counts),
  'command_set_errors', (SELECT command_set_errors FROM counts)
);
$$;

REVOKE ALL ON SCHEMA "company-os" FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA "company-os" FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA "company-os" FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA "company-os"
  REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA "company-os"
  REVOKE ALL ON FUNCTIONS FROM PUBLIC;
