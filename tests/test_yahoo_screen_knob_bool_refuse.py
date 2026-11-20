"""Yahoo screen timeout / claim / count / age knobs must refuse bool invents."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from stock_checker.yahoo_universe_discovery import (
    DEFAULT_MOVER_COUNT,
    DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS,
    DEFAULT_YAHOO_FAIL_BACKOFF_HOURS,
    DEFAULT_YAHOO_SCREEN_CLAIM_MAX_SEC,
    DEFAULT_YAHOO_SCREEN_TIMEOUT_SEC,
    _coerce_yahoo_claim_max_sec,
    _coerce_yahoo_fail_backoff_hours,
    _coerce_yahoo_max_age_hours,
    _coerce_yahoo_mover_count,
    _coerce_yahoo_screen_timeout_sec,
    list_live_yahoo_screen_claims,
    release_dead_yahoo_screen_claims,
    yahoo_discovery_due_from_meta,
    yahoo_fail_retry_remaining_sec,
)


def test_coerce_yahoo_mover_count_refuses_bool() -> None:
    """True→1 must not invent a one-quote Yahoo spend."""
    assert _coerce_yahoo_mover_count(True) == DEFAULT_MOVER_COUNT
    assert _coerce_yahoo_mover_count(False) == DEFAULT_MOVER_COUNT
    assert _coerce_yahoo_mover_count(0) == DEFAULT_MOVER_COUNT
    assert _coerce_yahoo_mover_count(5) == 5
    assert _coerce_yahoo_mover_count(250) == 100


def test_coerce_yahoo_screen_timeout_refuses_bool() -> None:
    """True→1s must not invent a thin hung-screen join ceiling."""
    assert (
        _coerce_yahoo_screen_timeout_sec(True) == DEFAULT_YAHOO_SCREEN_TIMEOUT_SEC
    )
    assert (
        _coerce_yahoo_screen_timeout_sec(False) == DEFAULT_YAHOO_SCREEN_TIMEOUT_SEC
    )
    assert _coerce_yahoo_screen_timeout_sec(0) == DEFAULT_YAHOO_SCREEN_TIMEOUT_SEC
    assert _coerce_yahoo_screen_timeout_sec(7) == 7


def test_coerce_yahoo_claim_max_sec_refuses_bool() -> None:
    """True→1s must not invent a thin claim TTL."""
    assert (
        _coerce_yahoo_claim_max_sec(True) == float(DEFAULT_YAHOO_SCREEN_CLAIM_MAX_SEC)
    )
    assert (
        _coerce_yahoo_claim_max_sec(False) == float(DEFAULT_YAHOO_SCREEN_CLAIM_MAX_SEC)
    )
    assert (
        _coerce_yahoo_claim_max_sec(0.5) == float(DEFAULT_YAHOO_SCREEN_CLAIM_MAX_SEC)
    )
    assert _coerce_yahoo_claim_max_sec(45.0) == 45.0


def test_coerce_yahoo_max_age_hours_refuses_bool() -> None:
    """True→1h must not invent a thin rediscovery band."""
    assert (
        _coerce_yahoo_max_age_hours(True) == DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS
    )
    assert (
        _coerce_yahoo_max_age_hours(False) == DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS
    )
    assert _coerce_yahoo_max_age_hours(0) == DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS
    assert _coerce_yahoo_max_age_hours(12) == 12


def test_coerce_yahoo_fail_backoff_refuses_bool() -> None:
    """False→0 must not clear the fail throttle; numeric 0 stays deliberate."""
    assert (
        _coerce_yahoo_fail_backoff_hours(True) == DEFAULT_YAHOO_FAIL_BACKOFF_HOURS
    )
    assert (
        _coerce_yahoo_fail_backoff_hours(False) == DEFAULT_YAHOO_FAIL_BACKOFF_HOURS
    )
    assert _coerce_yahoo_fail_backoff_hours(0) == 0
    assert _coerce_yahoo_fail_backoff_hours(3) == 3


def test_yahoo_discovery_due_refuses_bool_max_age() -> None:
    """Bool max_age falls back to 24h (not True→1h due after one hour)."""
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    stamp = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = {
        "last_yahoo_discovery": stamp,
        "last_yahoo_discovery_status": "ok",
    }
    # Without refuse, True→1 would mark a 2h-old success as due.
    assert yahoo_discovery_due_from_meta(meta, now=now, max_age_hours=True) is False
    assert yahoo_discovery_due_from_meta(meta, now=now, max_age_hours=False) is False
    assert yahoo_discovery_due_from_meta(meta, now=now, max_age_hours=1) is True


def test_yahoo_fail_retry_refuses_bool_backoff() -> None:
    """Bool fail backoff falls back to 1h (not False→0 immediate retry)."""
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    stamp = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = {
        "last_yahoo_discovery_status": "failed",
        "last_yahoo_discovery_fail": stamp,
    }
    remain = yahoo_fail_retry_remaining_sec(
        meta, now=now, fail_backoff_hours=False
    )
    assert remain is not None and remain > 0
    assert (
        yahoo_discovery_due_from_meta(meta, now=now, fail_backoff_hours=False)
        is False
    )
    assert (
        yahoo_fail_retry_remaining_sec(meta, now=now, fail_backoff_hours=0) == 0
    )


def test_release_dead_claims_refuses_bool_ttl() -> None:
    """Bool claim TTL falls back to 120s (not True→1s instant stale)."""
    # Empty map — just prove bool knobs do not raise / invent thin ceiling.
    assert release_dead_yahoo_screen_claims(max_age_sec=True) == (0, 0, 0)
    assert release_dead_yahoo_screen_claims(max_age_sec=False) == (0, 0, 0)
    assert list_live_yahoo_screen_claims(max_age_sec=True) == []
