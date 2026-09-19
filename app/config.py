import os


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing required env var {name}")
    return value


DATABASE_URL = _required("DATABASE_URL")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
POLL_INTERVAL_HOURS = float(os.environ.get("POLL_INTERVAL_HOURS", "12"))
NOTIFY_EVERY_RUN = os.environ.get("NOTIFY_EVERY_RUN", "true").strip().lower() in ("1", "true", "yes", "on")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")  # optional; enables latency/throughput lookup
