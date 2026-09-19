import html
import logging
from datetime import datetime, timezone

import requests

from app import config
from app.diff import Diff

log = logging.getLogger(__name__)

MAX_LEN = 4000  # Telegram limit is 4096 characters


def _ctx(v) -> str:
    return f"{v // 1000}k" if v else "-"


def _num(v) -> str:
    return "-" if v is None else f"{v:g}"


def _short(model_id: str, width: int = 30) -> str:
    name = model_id.removesuffix(":free")
    return name if len(name) <= width else name[: width - 1] + "…"


def format_table(current_free: dict[str, dict]) -> str:
    """Monospace, column-aligned table. Latency/throughput columns appear only if any model has a value."""
    cols = [("Model", None), ("Ctx", "context_length"), ("Int", "intelligence_index"),
            ("Code", "coding_index"), ("Agent", "agentic_index")]
    if any(d.get("latency_p50") is not None for d in current_free.values()):
        cols.append(("Lat", "latency_p50"))
    if any(d.get("throughput_p50") is not None for d in current_free.values()):
        cols.append(("TPS", "throughput_p50"))
    rows = [[_short(m)] + [_ctx(d.get(k)) if k == "context_length" else _num(d.get(k)) for _, k in cols[1:]]
            for m, d in sorted(current_free.items())]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, (h, _) in enumerate(cols)]
    fmt = lambda cells: "  ".join(c.ljust(w) if i == 0 else c.rjust(w) for i, (c, w) in enumerate(zip(cells, widths)))
    return "\n".join([fmt([h for h, _ in cols]), fmt(["-" * w for w in widths])] + [fmt(r) for r in rows])


def format_message(current_free: dict[str, dict], diff: Diff, baseline: bool = False, now: datetime | None = None) -> str:
    """HTML for Telegram (parse_mode=HTML). current_free maps model id -> details."""
    now = now or datetime.now(timezone.utc)
    esc = lambda ids: html.escape(", ".join(sorted(ids)))
    tail = []
    if baseline:
        tail.append("First run: baseline recorded.")
    else:
        if diff.newly_free:
            tail.append("✅ Newly free: " + esc(diff.newly_free))
        if diff.became_paid:
            tail.append("❌ No longer free: " + esc(diff.became_paid))
        if diff.removed:
            tail.append("🗑 Removed from catalog: " + esc(diff.removed))
        if not diff:
            tail.append("No changes since the last run.")
    head = f"📡 OpenRouter free models ({now:%Y-%m-%d %H:%M} UTC)\n🟢 Currently free ({len(current_free)}):"
    if not current_free:
        return "\n".join([head, "none"] + tail)

    legend = "Int/Code/Agent = Artificial Analysis indexes"
    models = dict(current_free)
    while True:
        omitted = len(current_free) - len(models)
        note = [f"(+{omitted} more not shown)"] if omitted else []
        text = "\n".join([head, f"<pre>{html.escape(format_table(models))}</pre>", legend] + note + tail)
        if len(text) <= MAX_LEN or len(models) <= 1:
            return text
        models.pop(max(models))  # drop alphabetically-last rows until it fits


def format_error(message: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return f"⚠️ OpenRouter tracker run failed ({now:%Y-%m-%d %H:%M} UTC)\n{html.escape(message[:500])}"


def send_text(text: str) -> bool:
    """Send a Telegram message. Never raises; returns whether it was sent."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.error("telegram not configured, message not sent")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        # Do not log the exception object: requests errors embed the URL, which contains the bot token.
        log.error("telegram send failed: %s", type(e).__name__)
        return False
