"""Night-only autoresearch window (Europe/Berlin)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from stock_checker.autoresearch_schedule import (
    in_night_window,
    night_window_bounds,
    seconds_until_night_window,
)


TZ = ZoneInfo("Europe/Berlin")


def _dt(y: int, m: int, d: int, hh: int, mm: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=TZ)


def test_default_bounds() -> None:
    start, end, tz = night_window_bounds()
    assert start == 23
    assert end == 8
    assert tz == "Europe/Berlin"


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
def test_in_night_window(when: datetime, expected: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_AUTOSEARCH_FORCE", raising=False)
    assert in_night_window(when) is expected


def test_force_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_AUTOSEARCH_FORCE", "1")
    assert in_night_window(_dt(2026, 8, 10, 15, 0)) is True
    assert seconds_until_night_window(_dt(2026, 8, 10, 15, 0)) == 0


def test_seconds_until_open_daytime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_AUTOSEARCH_FORCE", raising=False)
    now = _dt(2026, 8, 10, 15, 0)
    wait = seconds_until_night_window(now)
    # 15:00 → 23:00 same day = 8 hours
    assert wait == 8 * 3600


def test_seconds_until_open_after_midnight_still_inside(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OLLAMA_AUTOSEARCH_FORCE", raising=False)
    assert seconds_until_night_window(_dt(2026, 8, 11, 3, 0)) == 0


def test_seconds_until_open_just_after_close(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_AUTOSEARCH_FORCE", raising=False)
    now = _dt(2026, 8, 11, 8, 0)
    wait = seconds_until_night_window(now)
    # 08:00 → 23:00 same day = 15 hours
    assert wait == 15 * 3600
