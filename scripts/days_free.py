"""Total days a model was free, from the free_model_events log.

Usage: DATABASE_URL=postgresql://... python scripts/days_free.py <model_id>
"""
import os
import sys
from datetime import datetime, timezone

import psycopg


def free_windows(events, now):
    """events: [(event_type, event_at)] ordered by time -> [(start, end)]; open window ends at now."""
    windows, start = [], None
    for event_type, at in events:
        if event_type == "became_free" and start is None:
            start = at
        elif event_type in ("became_paid", "removed") and start is not None:
            windows.append((start, at))
            start = None
    if start is not None:
        windows.append((start, now))
    return windows


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    model_id = sys.argv[1]
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        events = conn.execute(
            """
            SELECT e.event_type, e.event_at FROM free_model_events e
            JOIN models m ON m.id = e.model_pk
            WHERE m.model_id = %s ORDER BY e.event_at, e.id
            """,
            (model_id,),
        ).fetchall()
    if not events:
        sys.exit(f"no events for {model_id}")
    windows = free_windows(events, datetime.now(timezone.utc))
    total = sum((end - start).total_seconds() for start, end in windows) / 86400
    for start, end in windows:
        print(f"{start:%Y-%m-%d %H:%M} -> {end:%Y-%m-%d %H:%M} UTC  ({(end - start).total_seconds() / 86400:.2f} d)")
    print(f"{model_id}: {total:.2f} days free across {len(windows)} window(s)")


if __name__ == "__main__":
    main()
