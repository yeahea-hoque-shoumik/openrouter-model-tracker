import logging
import sys
import time

from app import config, db, notifier
from app.diff import compute_diff
from app.fetcher import extract_details, fetch_endpoint_stats, fetch_models, free_ids

log = logging.getLogger("tracker")


def run_cycle() -> None:
    try:
        models = fetch_models()
    except Exception as e:
        log.error("run status=error stage=fetch error=%s", e)
        _record_error(str(e))
        if config.NOTIFY_EVERY_RUN:
            notifier.send_text(notifier.format_error(str(e)))
        return

    all_ids = set(models)
    current_free = free_ids(all_ids)
    details = {m: extract_details(models[m]) for m in current_free}
    if config.OPENROUTER_API_KEY:
        for m in current_free:
            details[m]["latency_p50"], details[m]["throughput_p50"] = fetch_endpoint_stats(m, config.OPENROUTER_API_KEY)
    with db.connect() as conn:
        with conn.transaction():
            baseline = not db.has_successful_run(conn)
            diff = compute_diff(db.get_free_set(conn), current_free, all_ids)
            db.save_ok_run(conn, len(all_ids), current_free, diff, details)

    log.info(
        "run status=ok total=%d free=%d newly_free=%d became_paid=%d removed=%d baseline=%s",
        len(all_ids), len(current_free), len(diff.newly_free), len(diff.became_paid), len(diff.removed), baseline,
    )
    # Notify only after commit. With NOTIFY_EVERY_RUN off, alert on changes only (never on the baseline run).
    if config.NOTIFY_EVERY_RUN or (diff and not baseline):
        notifier.send_text(notifier.format_message(details, diff, baseline))


def _record_error(message: str) -> None:
    try:
        with db.connect() as conn:
            db.save_error_run(conn, message)
    except Exception as e:
        log.error("could not record error run: %s", e)


def safe_cycle() -> bool:
    """Run one cycle; never raises. Returns False if the cycle failed."""
    try:
        db.init_schema()
        run_cycle()
        return True
    except Exception as e:
        log.exception("cycle failed")
        _record_error(f"unhandled: {e}")
        return False


def main() -> None:
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if "--once" in sys.argv[1:]:
        sys.exit(0 if safe_cycle() else 1)
    log.info("tracker starting interval_hours=%s", config.POLL_INTERVAL_HOURS)
    while True:
        safe_cycle()
        time.sleep(config.POLL_INTERVAL_HOURS * 3600)


if __name__ == "__main__":
    main()
