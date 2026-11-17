"""Refuse bool/gap entry/exit stamps so True→1.0 cannot invent ~1970 ages."""

from __future__ import annotations

import math

from openbb_backend.desk import _coerce_entry_ts
from stock_checker.technical_indicators import coerce_unix_ts


def test_coerce_unix_ts_accepts_real_epoch() -> None:
    assert coerce_unix_ts(1_700_000_000) == 1_700_000_000.0
    assert coerce_unix_ts(1_700_000_000.5) == 1_700_000_000.5


def test_coerce_unix_ts_refuses_bool_gap_nonpositive() -> None:
    assert coerce_unix_ts(True) is None
    assert coerce_unix_ts(False) is None
    assert coerce_unix_ts(0) is None
    assert coerce_unix_ts(-1) is None
    assert coerce_unix_ts(math.nan) is None
    assert coerce_unix_ts(math.inf) is None
    assert coerce_unix_ts(None) is None
    assert coerce_unix_ts("1700000000") is None


def test_coerce_entry_ts_desk_alias() -> None:
    assert _coerce_entry_ts(True) is None
    assert _coerce_entry_ts(1_700_000_000) == 1_700_000_000.0
