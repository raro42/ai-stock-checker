"""Book start / age helpers for Overview."""

from __future__ import annotations

from datetime import datetime, timezone

from openbb_backend.desk import book_start_meta


def test_book_start_from_first_trade() -> None:
    meta = book_start_meta(
        {},
        [{"timestamp": "2026-07-26 10:11:35", "type": "BUY"}],
        now=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc),
    )
    assert meta["book_start"] == "2026-07-26"
    assert meta["book_age_days"] == 17
    assert meta["book_age_label"] == "2026-07-26 (17d)"


def test_book_start_prefers_reset_at() -> None:
    meta = book_start_meta(
        {"reset_at": "2026-07-25T21:53:19.897425"},
        [{"timestamp": "2026-07-26 10:11:35"}],
        now=datetime(2026, 8, 8, tzinfo=timezone.utc),
    )
    assert meta["book_start"] == "2026-07-25"
    assert meta["book_age_days"] == 14
    assert meta["book_age_label"] == "2026-07-25 (14d)"


def test_book_start_empty() -> None:
    meta = book_start_meta({}, [])
    assert meta["book_start"] == ""
    assert meta["book_age_label"] == ""
