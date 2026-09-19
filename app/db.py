from pathlib import Path

import psycopg

from app import config
from app.diff import Diff


def connect() -> psycopg.Connection:
    return psycopg.connect(config.DATABASE_URL)


def init_schema() -> None:
    """Apply sql/init.sql (idempotent) so an existing, empty database gets the tables."""
    sql = (Path(__file__).resolve().parent.parent / "sql" / "init.sql").read_text()
    with connect() as conn:
        conn.execute(sql)


def get_free_set(conn: psycopg.Connection) -> set[str]:
    rows = conn.execute("SELECT model_id FROM free_model_status WHERE currently_free").fetchall()
    return {r[0] for r in rows}


def has_successful_run(conn: psycopg.Connection) -> bool:
    return conn.execute("SELECT EXISTS (SELECT 1 FROM poll_runs WHERE status = 'ok')").fetchone()[0]


def save_ok_run(conn: psycopg.Connection, total_models: int, current_free: set[str], diff: Diff) -> int:
    """Persist one successful run. Caller owns the transaction (commit)."""
    run_id = conn.execute(
        "INSERT INTO poll_runs (total_models, free_model_count, status) VALUES (%s, %s, 'ok') RETURNING id",
        (total_models, len(current_free)),
    ).fetchone()[0]
    now = conn.execute("SELECT now()").fetchone()[0]

    conn.execute("UPDATE free_model_status SET last_checked_at = %s", (now,))
    if current_free:
        conn.execute(
            """
            INSERT INTO free_model_status
                (model_id, currently_free, first_seen_free_at, last_seen_free_at, last_checked_at)
            SELECT m, true, %(now)s, %(now)s, %(now)s FROM unnest(%(ids)s::text[]) AS m
            ON CONFLICT (model_id) DO UPDATE
                SET currently_free = true,
                    last_seen_free_at = EXCLUDED.last_seen_free_at,
                    last_checked_at = EXCLUDED.last_checked_at
            """,
            {"now": now, "ids": sorted(current_free)},
        )
    gone = diff.became_paid | diff.removed
    if gone:
        conn.execute(
            "UPDATE free_model_status SET currently_free = false WHERE model_id = ANY(%s)",
            (sorted(gone),),
        )

    events = (
        [(m, "became_free") for m in sorted(diff.newly_free)]
        + [(m, "became_paid") for m in sorted(diff.became_paid)]
        + [(m, "removed") for m in sorted(diff.removed)]
    )
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO free_model_events (run_id, model_id, event_type, event_at) VALUES (%s, %s, %s, %s)",
            [(run_id, m, t, now) for m, t in events],
        )
    return run_id


def save_error_run(conn: psycopg.Connection, error_message: str) -> None:
    conn.execute(
        "INSERT INTO poll_runs (status, error_message) VALUES ('error', %s)",
        (error_message[:2000],),
    )
