import os

os.environ.setdefault("DATABASE_URL", "postgresql://x")

from datetime import datetime, timezone

from app import notifier
from app.diff import Diff

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
NO_DIFF = Diff(frozenset(), frozenset(), frozenset())
FULL = {"context_length": 262144, "intelligence_index": 25, "coding_index": 57.5, "agentic_index": None,
        "latency_p50": 0.8, "throughput_p50": 45}


def test_table_is_aligned_with_header():
    lines = notifier.format_table({"a/model:free": FULL, "z:free": {}}).split("\n")
    assert lines[0].split() == ["Model", "Ctx", "Int", "Code", "Agent", "Lat", "TPS"]
    assert lines[2].split() == ["a/model", "262k", "25", "57.5", "-", "0.8", "45"]
    assert lines[3].split() == ["z", "-", "-", "-", "-", "-", "-"]
    assert len({len(l) for l in lines}) == 1  # every row the same width


def test_table_drops_empty_latency_columns():
    header = notifier.format_table({"a:free": {"context_length": 1000}}).split("\n")[0]
    assert "Lat" not in header and "TPS" not in header


def test_long_name_shortened():
    row = notifier.format_table({"x" * 60 + ":free": {}}).split("\n")[2]
    assert "…" in row and len(row.split()[0]) == 30


def test_format_with_changes():
    d = Diff(frozenset({"a:free"}), frozenset({"b:free"}), frozenset({"c:free"}))
    msg = notifier.format_message({"a:free": FULL, "z:free": {}}, d, now=NOW)
    assert "2026-09-19 12:00 UTC" in msg and "Currently free (2)" in msg
    assert "<pre>" in msg and "</pre>" in msg
    assert "✅ Newly free: a:free" in msg
    assert "❌ No longer free: b:free" in msg
    assert "c:free" in msg


def test_html_is_escaped():
    d = Diff(frozenset({"<b>x:free"}), frozenset(), frozenset())
    msg = notifier.format_message({"<b>x:free": {}}, d, now=NOW)
    assert "<b>" not in msg and "&lt;b&gt;" in msg


def test_format_no_changes():
    msg = notifier.format_message({"a:free": {}}, NO_DIFF, now=NOW)
    assert "No changes" in msg and "Currently free (1)" in msg


def test_format_baseline_omits_diff():
    d = Diff(frozenset({"a:free"}), frozenset(), frozenset())
    msg = notifier.format_message({"a:free": {}}, d, baseline=True, now=NOW)
    assert "baseline" in msg and "Newly free" not in msg


def test_huge_list_trimmed_but_valid_html():
    models = {f"vendor/model-{i:04d}:free": FULL for i in range(500)}
    msg = notifier.format_message(models, NO_DIFF, now=NOW)
    assert len(msg) <= 4096 and msg.count("<pre>") == 1 and msg.count("</pre>") == 1
    assert "more not shown" in msg


def test_send_failure_never_raises(monkeypatch):
    monkeypatch.setattr(notifier.config, "TELEGRAM_BOT_TOKEN", "bad")
    monkeypatch.setattr(notifier.config, "TELEGRAM_CHAT_ID", "1")

    def boom(*a, **k):
        raise RuntimeError("network")

    monkeypatch.setattr(notifier.requests, "post", boom)
    assert notifier.send_text("hi") is False


def test_send_uses_html_parse_mode(monkeypatch):
    monkeypatch.setattr(notifier.config, "TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setattr(notifier.config, "TELEGRAM_CHAT_ID", "1")
    sent = {}

    class R:
        def raise_for_status(self):
            pass

    monkeypatch.setattr(notifier.requests, "post", lambda url, json, timeout: sent.update(json) or R())
    assert notifier.send_text("hi") is True
    assert sent["parse_mode"] == "HTML"
