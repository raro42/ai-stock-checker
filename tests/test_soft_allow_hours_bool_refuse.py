"""Soft-allow freshness TTL knobs must refuse bool invents."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from stock_checker.gate_audit import (
    SOFT_ALLOW_AGING_HOURS,
    SOFT_ALLOW_FRESH_HOURS,
    _DEFAULT_RECENT_SOFT_ALLOW_LIMIT,
    _coerce_soft_allow_hours,
    _coerce_soft_allow_limit,
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


def test_soft_allow_freshness_refuses_bool_ttl() -> None:
    """Bool aging/expire knobs fall back to 12h/24h triad (not True→1h)."""
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Without refuse, True→1h would mark 18h as expired.
    assert soft_allow_freshness(aging, now=now, aging_hours=True, fresh_hours=True) == "aging"
    assert soft_allow_is_expired(aging, now=now, fresh_hours=True) is False
    assert soft_allow_is_expired(aging, now=now, fresh_hours=False) is False
