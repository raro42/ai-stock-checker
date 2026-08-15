"""Night-only autoresearch window (local TZ, overridable)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from stock_checker.autoresearch_schedule import (
    default_local_tz_name,
    in_night_window,
    night_window_bounds,
    seconds_until_local_hour,
    seconds_until_night_window,
)


TZ = ZoneInfo("Europe/Berlin")


@pytest.fixture(autouse=True)
def _berlin_tz(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_AUTOSEARCH_TZ", "Europe/Berlin")
    monkeypatch.delenv("ASC_LOCAL_TZ", raising=False)
    monkeypatch.delenv("OLLAMA_AUTOSEARCH_FORCE", raising=False)


def _dt(y: int, m: int, d: int, hh: int, mm: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=TZ)


def test_default_bounds() -> None:
    start, end, tz = night_window_bounds()
    assert start == 23
    assert end == 8
    assert tz == "Europe/Berlin"


def test_explicit_tz_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_AUTOSEARCH_TZ", "America/New_York")
    _s, _e, tz = night_window_bounds()
    assert tz == "America/New_York"


def test_default_local_tz_name_respects_asc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_AUTOSEARCH_TZ", raising=False)
    monkeypatch.setenv("ASC_LOCAL_TZ", "Asia/Tokyo")
    assert default_local_tz_name() == "Asia/Tokyo"


@pytest.mark.parametrize(
    "when,expected",
    [
        (_dt(2026, 8, 10, 22, 59), False),
        (_dt(2026, 8, 10, 23, 0), True),
        (_dt(2026, 8, 10, 23, 30), True),
        (_dt(2026, 8, 11, 0, 0), True),
        (_dt(2026, 8, 11, 7, 59), True),
        (_dt(2026, 8, 11, 8, 0), False),
        (_dt(2026, 8, 11, 15, 0), False),
    ],
)
def test_in_night_window(when: datetime, expected: bool) -> None:
    assert in_night_window(when) is expected


def test_force_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_AUTOSEARCH_FORCE", "1")
    assert in_night_window(_dt(2026, 8, 10, 15, 0)) is True
    assert seconds_until_night_window(_dt(2026, 8, 10, 15, 0)) == 0


def test_seconds_until_open_daytime() -> None:
    now = _dt(2026, 8, 10, 15, 0)
    wait = seconds_until_night_window(now)
    assert wait == 8 * 3600


def test_seconds_until_open_after_midnight_still_inside() -> None:
    assert seconds_until_night_window(_dt(2026, 8, 11, 3, 0)) == 0


def test_seconds_until_open_just_after_close() -> None:
    now = _dt(2026, 8, 11, 8, 0)
    wait = seconds_until_night_window(now)
    assert wait == 15 * 3600


def test_seconds_until_morning() -> None:
    # 07:00 → 08:00 = 1h
    assert seconds_until_local_hour(8, _dt(2026, 8, 11, 7, 0)) == 3600
