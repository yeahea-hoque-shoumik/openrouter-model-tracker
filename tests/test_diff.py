from app.diff import compute_diff
from app.fetcher import FetchError, free_ids, parse_model_ids

import pytest


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
        parse_model_ids(payload)


def test_parse_ok():
    assert parse_model_ids({"data": [{"id": "a:free"}, {"id": "b"}, {"nope": 1}]}) == {"a:free", "b"}
