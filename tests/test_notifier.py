import os

os.environ.setdefault("DATABASE_URL", "postgresql://x")

from datetime import datetime, timezone

from app import notifier
from app.diff import Diff


def test_format_message():
    d = Diff(frozenset({"a:free"}), frozenset({"b:free"}), frozenset({"c:free"}))
    msg = notifier.format_message(d, datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc))
    assert "2026-09-19 12:00 UTC" in msg
    assert "✅ Newly free: a:free" in msg
    assert "❌ No longer free: b:free" in msg
    assert "c:free" in msg


def test_send_failure_never_raises(monkeypatch):
    monkeypatch.setattr(notifier.config, "TELEGRAM_BOT_TOKEN", "bad")
    monkeypatch.setattr(notifier.config, "TELEGRAM_CHAT_ID", "1")

    def boom(*a, **k):
        raise RuntimeError("network")

    monkeypatch.setattr(notifier.requests, "post", boom)
    assert notifier.send_alert(Diff(frozenset({"a:free"}), frozenset(), frozenset())) is False
