from app.diff import compute_diff
from app.fetcher import FetchError, free_ids, parse_models

import pytest

from app.fetcher import extract_details, tool_calling_index



def test_no_change():
    d = compute_diff({"a:free"}, {"a:free"}, {"a:free", "b"})
    assert not d


def test_added():
    d = compute_diff({"a:free"}, {"a:free", "b:free"}, {"a:free", "b:free"})
    assert d.newly_free == {"b:free"} and not d.became_paid and not d.removed


def test_dropped_paid_vs_removed():
    d = compute_diff({"a:free", "b:free"}, set(), {"a:free"})
    assert d.became_paid == {"a:free"} and d.removed == {"b:free"}


def test_first_run_empty_db():
    d = compute_diff(set(), {"a:free", "b:free"}, {"a:free", "b:free", "c"})
    assert d.newly_free == {"a:free", "b:free"} and not d.became_paid and not d.removed


def test_free_ids_filter():
    assert free_ids({"a:free", "b", "c:free:extra", "d:free"}) == {"a:free", "d:free"}


@pytest.mark.parametrize("payload", [None, [], {}, {"data": None}, {"data": []}, {"data": [{"x": 1}, "s"]}, "garbage"])
def test_garbage_payload_rejected(payload):
    with pytest.raises(FetchError):
        parse_models(payload)


def test_parse_ok():
    assert set(parse_models({"data": [{"id": "a:free"}, {"id": "b"}, {"nope": 1}]})) == {"a:free", "b"}


def test_extract_details_full_and_missing():
    d = extract_details({
        "name": "N", "context_length": 100,
        "top_provider": {"context_length": 200, "max_completion_tokens": 50},
        "benchmarks": {"artificial_analysis": {"intelligence_index": 25, "coding_index": 57.5, "agentic_index": None}},
    })
    assert d["context_length"] == 200 and d["max_completion_tokens"] == 50
    assert d["intelligence_index"] == 25 and d["coding_index"] == 57.5 and d["agentic_index"] is None
    empty = extract_details({"name": "x"})
    assert empty["context_length"] is None and empty["intelligence_index"] is None
    assert empty["tool_calling_index"] == 0


def test_tool_calling_index():
    idx = lambda p: tool_calling_index({"supported_parameters": p})
    assert idx(["temperature"]) == 0
    assert idx(["tools"]) == 1
    assert idx(["tools", "tool_choice"]) == 2
    assert idx(["tool_choice"]) == 0
    assert tool_calling_index({"supported_parameters": None}) == 0
