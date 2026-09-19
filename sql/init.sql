CREATE TABLE IF NOT EXISTS poll_runs (
    id                BIGSERIAL PRIMARY KEY,
    run_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    total_models      INTEGER,
    free_model_count  INTEGER,
    status            TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    error_message     TEXT
);

-- One row per model ever seen free; other tables reference it by id.
CREATE TABLE IF NOT EXISTS models (
    id                     BIGSERIAL PRIMARY KEY,
    model_id               TEXT NOT NULL UNIQUE,
    name                   TEXT,
    context_length         INTEGER,
    max_completion_tokens  INTEGER,
    intelligence_index     DOUBLE PRECISION,
    coding_index           DOUBLE PRECISION,
    agentic_index          DOUBLE PRECISION,
    latency_p50            DOUBLE PRECISION,
    throughput_p50         DOUBLE PRECISION,
    tool_calling_index     SMALLINT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE models ADD COLUMN IF NOT EXISTS tool_calling_index SMALLINT;

CREATE TABLE IF NOT EXISTS free_model_status (
    model_pk            BIGINT PRIMARY KEY REFERENCES models (id),
    currently_free      BOOLEAN NOT NULL,
    first_seen_free_at  TIMESTAMPTZ NOT NULL,
    last_seen_free_at   TIMESTAMPTZ NOT NULL,
    last_checked_at     TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS free_model_events (
    id          BIGSERIAL PRIMARY KEY,
    run_id      BIGINT NOT NULL REFERENCES poll_runs (id),
    model_pk    BIGINT NOT NULL REFERENCES models (id),
    event_type  TEXT NOT NULL CHECK (event_type IN ('became_free', 'became_paid', 'removed')),
    event_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One-time migration of the original layout (text model_id columns) to model_pk references.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = current_schema()
                 AND table_name = 'free_model_status' AND column_name = 'model_id') THEN
        INSERT INTO models (model_id)
            SELECT model_id FROM free_model_status
            UNION
            SELECT model_id FROM free_model_events
        ON CONFLICT (model_id) DO NOTHING;

        ALTER TABLE free_model_status ADD COLUMN model_pk BIGINT REFERENCES models (id);
        UPDATE free_model_status s SET model_pk = m.id FROM models m WHERE m.model_id = s.model_id;
        ALTER TABLE free_model_status DROP CONSTRAINT free_model_status_pkey;
        ALTER TABLE free_model_status DROP COLUMN model_id;
        ALTER TABLE free_model_status ADD PRIMARY KEY (model_pk);

        -- Backfilling the FK is not a change to any event fact; lift the append-only guard just for it.
        ALTER TABLE free_model_events DISABLE TRIGGER USER;
        ALTER TABLE free_model_events ADD COLUMN model_pk BIGINT REFERENCES models (id);
        UPDATE free_model_events e SET model_pk = m.id FROM models m WHERE m.model_id = e.model_id;
        ALTER TABLE free_model_events ALTER COLUMN model_pk SET NOT NULL;
        ALTER TABLE free_model_events DROP COLUMN model_id;
        ALTER TABLE free_model_events ENABLE TRIGGER USER;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS free_model_events_model_idx ON free_model_events (model_pk, event_at);

-- Events are append-only: reject UPDATE and DELETE.
CREATE OR REPLACE FUNCTION free_model_events_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'free_model_events is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS free_model_events_no_mutation ON free_model_events;
CREATE TRIGGER free_model_events_no_mutation
    BEFORE UPDATE OR DELETE ON free_model_events
    FOR EACH ROW EXECUTE FUNCTION free_model_events_append_only();
