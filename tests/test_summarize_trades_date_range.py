"""tradermonty #809: summarize_trades refuses inverted / invalid date ranges."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "summarize_trades.py"
_SPEC = spec_from_file_location("summarize_trades_under_test", _SCRIPT)
assert _SPEC and _SPEC.loader
_MOD = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def test_parse_since_window_a_alias() -> None:
    from stock_checker.promote_ab import WINDOW_A_START_UTC

    assert _MOD._parse_since("window-a") == WINDOW_A_START_UTC


def test_parse_since_iso_date() -> None:
    got = _MOD._parse_since("2026-11-17")
    assert got == datetime(2026, 11, 17, tzinfo=timezone.utc)


def test_parse_since_invalid_exits_message() -> None:
    with pytest.raises(ValueError, match="invalid date"):
        _MOD._parse_since("not-a-date")
    with pytest.raises(ValueError, match="invalid date"):
        _MOD._parse_since("2026-13-40")


def test_require_ordered_range_same_day_ok() -> None:
    day = datetime(2026, 11, 17, tzinfo=timezone.utc)
    _MOD._require_ordered_range(day, day)


def test_require_ordered_range_inverted() -> None:
    start = datetime(2026, 11, 18, tzinfo=timezone.utc)
    end = datetime(2026, 11, 17, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="later than"):
        _MOD._require_ordered_range(start, end)


def test_require_ordered_range_partial_ok() -> None:
    day = datetime(2026, 11, 17, tzinfo=timezone.utc)
    _MOD._require_ordered_range(day, None)
    _MOD._require_ordered_range(None, day)
    _MOD._require_ordered_range(None, None)
