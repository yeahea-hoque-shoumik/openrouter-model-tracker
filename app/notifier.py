import logging
from datetime import datetime, timezone

import requests

from app import config
from app.diff import Diff

log = logging.getLogger(__name__)

MAX_LEN = 4000  # Telegram limit is 4096 characters


def format_message(current_free: set[str], diff: Diff, baseline: bool = False, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    lines = [f"📡 OpenRouter free models ({now:%Y-%m-%d %H:%M} UTC)"]
    if baseline:
        lines.append("First run: baseline recorded.")
    lines.append(f"🟢 Currently free ({len(current_free)}):")
    lines += [f"  {m}" for m in sorted(current_free)] or ["  none"]
    if not baseline:
        if diff.newly_free:
            lines.append("✅ Newly free: " + ", ".join(sorted(diff.newly_free)))
        if diff.became_paid:
            lines.append("❌ No longer free: " + ", ".join(sorted(diff.became_paid)))
        if diff.removed:
            lines.append("🗑 Removed from catalog: " + ", ".join(sorted(diff.removed)))
        if not diff:
            lines.append("No changes since the last run.")
    return "\n".join(lines)


def format_error(message: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"⚠️ OpenRouter tracker run failed ({now:%Y-%m-%d %H:%M} UTC)\n{message[:500]}"


def send_text(text: str) -> bool:
    """Send a Telegram message. Never raises; returns whether it was sent."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.error("telegram not configured, message not sent")
        return False
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN] + "\n…(truncated)"
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text},
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        # Do not log the exception object: requests errors embed the URL, which contains the bot token.
        log.error("telegram send failed: %s", type(e).__name__)
        return False
