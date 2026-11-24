"""Ideas GitHub-watch last-check stamp clip ceilings refuse bool invent."""

from __future__ import annotations

import json
from pathlib import Path

from openbb_backend.desk import (
    GH_WATCH_AT_CHARS,
    _clip_gh_watch_at,
    _coerce_gh_watch_at_chars,
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


def test_gh_watch_at_default() -> None:
    assert GH_WATCH_AT_CHARS == 20


def test_gh_watch_at_coerce_refuses_bool() -> None:
    assert _coerce_gh_watch_at_chars(True) == GH_WATCH_AT_CHARS
    assert _coerce_gh_watch_at_chars(False) == GH_WATCH_AT_CHARS
    assert _coerce_gh_watch_at_chars(0) == GH_WATCH_AT_CHARS
    assert _coerce_gh_watch_at_chars(None) == GH_WATCH_AT_CHARS
    assert _coerce_gh_watch_at_chars(10) == 10


def test_clip_gh_watch_at_prefix() -> None:
    stamp = "2026-11-24T19:21:29.123456Z"
    clipped = _clip_gh_watch_at(stamp)
    assert clipped == stamp[:GH_WATCH_AT_CHARS]
    assert len(clipped) == GH_WATCH_AT_CHARS
    # True→1 must not invent a one-char Last check.
    assert _clip_gh_watch_at(stamp, True) == clipped
    assert _clip_gh_watch_at(stamp, False) == clipped
    thin = _clip_gh_watch_at(stamp, 10)
    assert thin == "2026-11-24"
    assert _clip_gh_watch_at("2026-11-24T12:00:00Z") == "2026-11-24T12:00:00Z"
    assert _clip_gh_watch_at("") == ""
    assert _clip_gh_watch_at(None) == ""


def test_load_desk_snapshot_refuses_bool_gh_watch_at_clip(
    tmp_path: Path, monkeypatch
) -> None:
    """True→1 must not invent a one-char Last check on Ideas."""
    _seed_portfolio(tmp_path)
    gw = tmp_path / "github_watch"
    gw.mkdir(parents=True, exist_ok=True)
    long_at = "2026-11-24T19:21:29.123456789Z"
    (gw / "latest.json").write_text(
        json.dumps(
            {
                "generated_at": long_at,
                "repo_count": 1,
                "checked_count": 1,
                "update_count": 0,
                "idea_bullets": [],
                "repos": [],
            }
        )
    )
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")

    snap_true = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
        gh_at_n=True,
    )
    assert snap_true["github_watch_at_limit"] == GH_WATCH_AT_CHARS
    assert snap_true["github_watch_at"] == long_at[:GH_WATCH_AT_CHARS]
    assert len(snap_true["github_watch_at"]) == GH_WATCH_AT_CHARS

    snap_thin = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
        gh_at_n=10,
    )
    assert snap_thin["github_watch_at_limit"] == 10
    assert snap_thin["github_watch_at"] == "2026-11-24"
