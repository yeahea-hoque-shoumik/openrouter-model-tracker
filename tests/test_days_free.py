import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from days_free import free_windows

D = lambda d: datetime(2026, 1, d, tzinfo=timezone.utc)


def test_multiple_windows_and_open():
    ev = [("became_free", D(1)), ("became_paid", D(3)), ("became_free", D(5)), ("removed", D(6)), ("became_free", D(8))]
    assert free_windows(ev, D(10)) == [(D(1), D(3)), (D(5), D(6)), (D(8), D(10))]
