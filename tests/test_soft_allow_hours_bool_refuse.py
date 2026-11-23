"""Soft-allow freshness TTL + retention knobs must refuse bool invents."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_checker.gate_audit import (
    SOFT_ALLOW_AGING_HOURS,
    SOFT_ALLOW_CAP,
    SOFT_ALLOW_FRESH_HOURS,
    SOFT_ALLOW_REASON_MAX,
    _DEFAULT_RECENT_SOFT_ALLOW_LIMIT,
    _clip_soft_allow_reason,
    _coerce_soft_allow_hours,
    _coerce_soft_allow_limit,
    _coerce_soft_allow_reason_chars,
    load_soft_allows,
    record_soft_allow,
    soft_allow_event_key,
    soft_allow_freshness,
    soft_allow_is_expired,
)


def test_coerce_soft_allow_hours_refuses_bool() -> None:
    """tradermonty #700/#655 + xang1234: True→1h must not invent thin TTL."""
    assert _coerce_soft_allow_hours(True, SOFT_ALLOW_FRESH_HOURS) == SOFT_ALLOW_FRESH_HOURS
    assert _coerce_soft_allow_hours(False, SOFT_ALLOW_AGING_HOURS) == SOFT_ALLOW_AGING_HOURS
    assert _coerce_soft_allow_hours(0, 24.0) == 24.0
    assert _coerce_soft_allow_hours(-3.0, 12.0) == 12.0
    assert _coerce_soft_allow_hours(6.0, 12.0) == 6.0


def test_coerce_soft_allow_limit_refuses_bool() -> None:
    """True→1 must not invent a one-row Ops soft-allow strip."""
    assert _coerce_soft_allow_limit(True) == _DEFAULT_RECENT_SOFT_ALLOW_LIMIT
    assert _coerce_soft_allow_limit(False) == _DEFAULT_RECENT_SOFT_ALLOW_LIMIT
    assert _coerce_soft_allow_limit(5) == 5
    assert _coerce_soft_allow_limit(0) == 0
    assert _coerce_soft_allow_limit(True, SOFT_ALLOW_CAP) == SOFT_ALLOW_CAP


def test_coerce_soft_allow_reason_chars_refuses_bool() -> None:
    """True→1 / [:True] must not invent a one-char fail-open reason key."""
    assert _coerce_soft_allow_reason_chars(True) == SOFT_ALLOW_REASON_MAX
    assert _coerce_soft_allow_reason_chars(False) == SOFT_ALLOW_REASON_MAX
    assert _coerce_soft_allow_reason_chars(0) == SOFT_ALLOW_REASON_MAX
    assert _coerce_soft_allow_reason_chars(None) == SOFT_ALLOW_REASON_MAX
    assert _coerce_soft_allow_reason_chars(40) == 40


def test_clip_soft_allow_reason_refuses_bool_ceiling() -> None:
    """Bool ceiling falls back to 240; False must not wipe via [:False]."""
    long = "x" * 300
    assert len(_clip_soft_allow_reason(long, True)) == SOFT_ALLOW_REASON_MAX
    assert len(_clip_soft_allow_reason(long, False)) == SOFT_ALLOW_REASON_MAX
    assert _clip_soft_allow_reason("  unknown — no bars  ", 12) == "unknown — no"
    assert soft_allow_event_key("rs", long, reason_n=True)[1] == (
        "x" * SOFT_ALLOW_REASON_MAX
    ).casefold()


def test_record_soft_allow_refuses_bool_reason_ceiling(tmp_path: Path) -> None:
    """True→1 must not persist a one-char soft-allow reason."""
    reason = "unknown — " + ("y" * 280)
    record_soft_allow(tmp_path, "regime", reason, reason_n=True)
    events = load_soft_allows(tmp_path)
    assert len(events) == 1
    assert len(events[0]["reason"]) == SOFT_ALLOW_REASON_MAX
    # Without refuse, reason_n=True → [:True] would leave a single "u".
    assert events[0]["reason"].startswith("unknown — ")


def test_soft_allow_freshness_refuses_bool_ttl() -> None:
    """Bool aging/expire knobs fall back to 12h/24h triad (not True→1h)."""
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Without refuse, True→1h would mark 18h as expired.
    assert soft_allow_freshness(aging, now=now, aging_hours=True, fresh_hours=True) == "aging"
    assert soft_allow_is_expired(aging, now=now, fresh_hours=True) is False
    assert soft_allow_is_expired(aging, now=now, fresh_hours=False) is False


def test_record_soft_allow_refuses_bool_cap(tmp_path: Path) -> None:
    """True→1 must not shrink the soft-allow ring to a single row."""
    for i in range(5):
        record_soft_allow(tmp_path, "rs", f"insufficient #{i}", cap=True)
    # Without refuse, int(True)→1 would keep only the newest event.
    assert len(load_soft_allows(tmp_path)) == 5

    for i in range(3):
        record_soft_allow(tmp_path, "breadth", f"unknown #{i}", cap=False)
    # False→0 via int() then max(1,0)→1 would also invent a 1-row ring.
    assert len(load_soft_allows(tmp_path)) == 8

    record_soft_allow(tmp_path, "regime", "unknown — a", cap=2)
    record_soft_allow(tmp_path, "regime", "unknown — b", cap=2)
    record_soft_allow(tmp_path, "regime", "unknown — c", cap=2)
    assert len(load_soft_allows(tmp_path)) == 2
