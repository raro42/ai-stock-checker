"""Ideas GitHub-watch activity/quiet-note clip ceilings refuse bool invent."""

from __future__ import annotations

import json
from pathlib import Path

from openbb_backend.desk import (
    GH_WATCH_IDEA_MAX,
    _clip_gh_watch_idea,
    _coerce_gh_watch_idea_chars,
    load_desk_snapshot,
)


def _seed_portfolio(tmp_path: Path) -> None:
    (tmp_path / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 100000,
                "cash": 100000,
                "holdings": {},
                "avg_buy_price": {},
                "total_fees_paid": 0,
            }
        )
    )
    (tmp_path / "trades.jsonl").write_text("")


def test_gh_watch_idea_default() -> None:
    assert GH_WATCH_IDEA_MAX == 160


def test_gh_watch_idea_coerce_refuses_bool() -> None:
    assert _coerce_gh_watch_idea_chars(True) == GH_WATCH_IDEA_MAX
    assert _coerce_gh_watch_idea_chars(False) == GH_WATCH_IDEA_MAX
    assert _coerce_gh_watch_idea_chars(0) == GH_WATCH_IDEA_MAX
    assert _coerce_gh_watch_idea_chars(None) == GH_WATCH_IDEA_MAX
    assert _coerce_gh_watch_idea_chars(40) == 40


def test_clip_gh_watch_idea_ellipsis() -> None:
    long = "i" * 200
    clipped = _clip_gh_watch_idea(long)
    assert len(clipped) == GH_WATCH_IDEA_MAX
    assert clipped.endswith("…")
    assert clipped == "i" * (GH_WATCH_IDEA_MAX - 1) + "…"
    # True→1 must not invent a one-char Ideas bullet.
    assert _clip_gh_watch_idea(long, True) == clipped
    assert _clip_gh_watch_idea(long, False) == clipped
    thin = _clip_gh_watch_idea(long, 20)
    assert len(thin) == 20
    assert thin.endswith("…")
    assert _clip_gh_watch_idea("short") == "short"
    assert _clip_gh_watch_idea("") == ""
    assert _clip_gh_watch_idea(None) == ""


def test_load_desk_snapshot_refuses_bool_gh_watch_idea_clip(
    tmp_path: Path, monkeypatch
) -> None:
    """True→1 must not invent a one-char Ideas activity bullet."""
    _seed_portfolio(tmp_path)
    gw = tmp_path / "github_watch"
    gw.mkdir(parents=True, exist_ok=True)
    long_bullet = "B" * 200
    (gw / "latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-11-24T12:00:00Z",
                "repo_count": 1,
                "checked_count": 1,
                "update_count": 1,
                "idea_bullets": [long_bullet],
                "repos": [
                    {
                        "repo": "acme/idea",
                        "url": "https://github.com/acme/idea",
                        "why": "screener UX",
                        "stars": 1,
                        "pushed_at": "2026-11-20T12:00:00Z",
                        "has_updates": True,
                        "tip_sha": "deadbeef",
                        "tip_message": "new tip",
                        "commits": [],
                    }
                ],
            }
        )
    )
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")

    snap_true = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
        gh_idea_n=True,
    )
    assert snap_true["github_watch_idea_limit"] == GH_WATCH_IDEA_MAX
    ideas = snap_true["github_ideas"]
    assert len(ideas) == 1
    assert len(ideas[0]) == GH_WATCH_IDEA_MAX
    assert ideas[0].endswith("…")
    assert ideas[0] == "B" * (GH_WATCH_IDEA_MAX - 1) + "…"

    snap_thin = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
        gh_idea_n=20,
    )
    assert snap_thin["github_watch_idea_limit"] == 20
    thin = snap_thin["github_ideas"][0]
    assert len(thin) == 20
    assert thin.endswith("…")


def test_load_desk_snapshot_clips_quiet_notes(
    tmp_path: Path, monkeypatch
) -> None:
    """Quiet composed notes reuse the same idea ceiling (no activity bullets)."""
    _seed_portfolio(tmp_path)
    gw = tmp_path / "github_watch"
    gw.mkdir(parents=True, exist_ok=True)
    long_tip = "T" * 200
    (gw / "latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-11-24T12:00:00Z",
                "repo_count": 1,
                "checked_count": 1,
                "update_count": 0,
                "idea_bullets": [],
                "repos": [
                    {
                        "repo": "acme/quiet",
                        "url": "https://github.com/acme/quiet",
                        "why": "screener UX",
                        "stars": 1,
                        "pushed_at": "2026-11-20T12:00:00Z",
                        "has_updates": False,
                        "tip_sha": "cafebabe",
                        "tip_message": long_tip,
                        "commits": [],
                    }
                ],
            }
        )
    )
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")

    snap = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
        gh_idea_n=40,
    )
    assert snap["github_ideas"] == []
    notes = snap["github_watch_notes"]
    assert len(notes) == 1
    assert len(notes[0]) == 40
    assert notes[0].endswith("…")
    assert notes[0].startswith("acme/quiet:")
