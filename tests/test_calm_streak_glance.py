"""Paper-calm streak glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import (
    _calm_detail_is_promote_off_pause,
    build_calm_streak_glance,
)


def test_calm_streak_glance_empty() -> None:
    assert build_calm_streak_glance(None)["ready"] is False
    assert build_calm_streak_glance({})["ready"] is False


def test_calm_detail_is_promote_off_pause() -> None:
    assert _calm_detail_is_promote_off_pause(
        "promote filter off — streak paused"
    )
    assert _calm_detail_is_promote_off_pause("Promote filter off")
    assert not _calm_detail_is_promote_off_pause("book overweight")
    assert not _calm_detail_is_promote_off_pause("")


def test_calm_streak_glance_blocked() -> None:
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "book overweight",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "blocked"
    assert g["promote_off_paused"] is False
    assert g["streak"] == 0
    assert g["required"] == 30
    assert "0/30" in g["line"]
    assert "streak not started" in g["line"]
    assert "book overweight" in g["line"]


def test_calm_streak_glance_promote_off_paused() -> None:
    """Window A: promote off is intentional — not 'streak not started' failure."""
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "paused"
    assert g["promote_off_paused"] is True
    assert "0/30" in g["line"]
    assert "promote off · streak paused" in g["line"]
    assert "streak not started" not in g["line"]
    # Compact status already names the why — do not repeat long detail.
    assert "promote filter off" not in g["line"]


def test_calm_streak_glance_progress() -> None:
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 12,
            "calm_required_days": 30,
            "calm_ready": False,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "progress"
    assert g["calm_ready"] is False
    assert g["promote_off_paused"] is False
    assert "12/30" in g["line"]
    assert "building" in g["line"]


def test_calm_streak_glance_ready() -> None:
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 30,
            "calm_required_days": 30,
            "calm_ready": True,
            "calm_detail": "should not appear when ready",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "ready"
    assert g["calm_ready"] is True
    assert g["promote_off_paused"] is False
    assert "compose promote default ready" in g["line"]
    assert "should not appear" not in g["line"]


def test_calm_streak_glance_truncates_line() -> None:
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 1,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "x" * 80,
        }
    )
    assert g["ready"] is True
    assert len(g["line"]) <= 96
