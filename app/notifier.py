import logging
from datetime import datetime, timezone

import requests

from app import config
from app.diff import Diff

log = logging.getLogger(__name__)


def format_message(diff: Diff, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    lines = [f"📡 OpenRouter free-model change ({now:%Y-%m-%d %H:%M} UTC)"]
    if diff.newly_free:
        lines.append("✅ Newly free: " + ", ".join(sorted(diff.newly_free)))
    if diff.became_paid:
        lines.append("❌ No longer free: " + ", ".join(sorted(diff.became_paid)))
    if diff.removed:
        lines.append("🗑 Removed from catalog: " + ", ".join(sorted(diff.removed)))
    return "\n".join(lines)


def send_alert(diff: Diff) -> bool:
    """Send a Telegram message. Never raises; returns whether it was sent."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.error("telegram not configured, alert not sent")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": format_message(diff)},
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        # Do not log the exception object: requests errors embed the URL, which contains the bot token.
        log.error("telegram send failed: %s", type(e).__name__)
        return False
