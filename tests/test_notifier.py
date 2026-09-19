import os

os.environ.setdefault("DATABASE_URL", "postgresql://x")

from datetime import datetime, timezone

from app import notifier
from app.diff import Diff

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


def test_format_with_changes():
    d = Diff(frozenset({"a:free"}), frozenset({"b:free"}), frozenset({"c:free"}))
    msg = notifier.format_message({"a:free", "z:free"}, d, now=NOW)
    assert "2026-09-19 12:00 UTC" in msg
    assert "Currently free (2)" in msg and "  z:free" in msg
    assert "✅ Newly free: a:free" in msg
    assert "❌ No longer free: b:free" in msg
    assert "c:free" in msg


def test_format_no_changes():
    msg = notifier.format_message({"a:free"}, Diff(frozenset(), frozenset(), frozenset()), now=NOW)
    assert "No changes" in msg and "Currently free (1)" in msg


def test_format_baseline_omits_diff():
    d = Diff(frozenset({"a:free"}), frozenset(), frozenset())
    msg = notifier.format_message({"a:free"}, d, baseline=True, now=NOW)
    assert "baseline" in msg and "Newly free" not in msg


def test_send_failure_never_raises(monkeypatch):
    monkeypatch.setattr(notifier.config, "TELEGRAM_BOT_TOKEN", "bad")
    monkeypatch.setattr(notifier.config, "TELEGRAM_CHAT_ID", "1")

    def boom(*a, **k):
        raise RuntimeError("network")

    monkeypatch.setattr(notifier.requests, "post", boom)
    assert notifier.send_text("hi") is False


def test_long_message_truncated(monkeypatch):
    monkeypatch.setattr(notifier.config, "TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setattr(notifier.config, "TELEGRAM_CHAT_ID", "1")
    sent = {}

    class R:
        def raise_for_status(self):
            pass

    monkeypatch.setattr(notifier.requests, "post", lambda url, json, timeout: sent.update(json) or R())
    assert notifier.send_text("x" * 9000) is True
    assert len(sent["text"]) < 4096
