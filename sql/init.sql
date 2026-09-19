CREATE TABLE IF NOT EXISTS poll_runs (
    id                BIGSERIAL PRIMARY KEY,
    run_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    total_models      INTEGER,
    free_model_count  INTEGER,
    status            TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    error_message     TEXT
);

CREATE TABLE IF NOT EXISTS free_model_status (
    model_id            TEXT PRIMARY KEY,
    currently_free      BOOLEAN NOT NULL,
    first_seen_free_at  TIMESTAMPTZ NOT NULL,
    last_seen_free_at   TIMESTAMPTZ NOT NULL,
    last_checked_at     TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS free_model_events (
    id          BIGSERIAL PRIMARY KEY,
    run_id      BIGINT NOT NULL REFERENCES poll_runs (id),
    model_id    TEXT NOT NULL,
    event_type  TEXT NOT NULL CHECK (event_type IN ('became_free', 'became_paid', 'removed')),
    event_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS free_model_events_model_idx ON free_model_events (model_id, event_at);

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
