"""Ideas GitHub-watch why clip ceilings refuse bool invent."""

from __future__ import annotations

import json
from pathlib import Path

from openbb_backend.desk import (
    GH_WATCH_WHY_MAX,
    _clip_gh_watch_why,
    _coerce_gh_watch_why_chars,
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


def test_gh_watch_why_default() -> None:
    assert GH_WATCH_WHY_MAX == 95


def test_gh_watch_why_coerce_refuses_bool() -> None:
    assert _coerce_gh_watch_why_chars(True) == GH_WATCH_WHY_MAX
    assert _coerce_gh_watch_why_chars(False) == GH_WATCH_WHY_MAX
    assert _coerce_gh_watch_why_chars(0) == GH_WATCH_WHY_MAX
    assert _coerce_gh_watch_why_chars(None) == GH_WATCH_WHY_MAX
    assert _coerce_gh_watch_why_chars(40) == 40


def test_clip_gh_watch_why_ellipsis() -> None:
    long = "w" * 200
    clipped = _clip_gh_watch_why(long)
    assert len(clipped) == GH_WATCH_WHY_MAX
    assert clipped.endswith("…")
    assert clipped == "w" * (GH_WATCH_WHY_MAX - 1) + "…"
    # True→1 must not invent a one-char why.
    assert _clip_gh_watch_why(long, True) == clipped
    assert _clip_gh_watch_why(long, False) == clipped
    thin = _clip_gh_watch_why(long, 20)
    assert len(thin) == 20
    assert thin.endswith("…")
    assert _clip_gh_watch_why("short") == "short"
    assert _clip_gh_watch_why("") == ""
    assert _clip_gh_watch_why(None) == ""


def test_load_desk_snapshot_refuses_bool_gh_watch_why_clip(
    tmp_path: Path, monkeypatch
) -> None:
    """True→1 must not invent a one-char why on Ideas repos."""
    _seed_portfolio(tmp_path)
    gw = tmp_path / "github_watch"
    gw.mkdir(parents=True, exist_ok=True)
    long_why = "W" * 200
    sha = "deadbeefcafebabe01234567"
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
                        "repo": "acme/why",
                        "url": "https://github.com/acme/why",
                        "why": long_why,
                        "stars": 1,
                        "pushed_at": "2026-11-20T12:00:00Z",
                        "has_updates": False,
                        "tip_sha": sha,
                        "tip_message": "quiet tip",
                        "commits": [
                            {
                                "sha": sha,
                                "date": "2026-11-19T08:00:00Z",
                                "message": "quiet tip",
                            }
                        ],
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
        gh_why_n=True,
    )
    assert snap_true["github_watch_why_limit"] == GH_WATCH_WHY_MAX
    row = snap_true["github_repos"][0]
    assert len(row["why"]) == GH_WATCH_WHY_MAX
    assert row["why"].endswith("…")
    assert row["why"] == "W" * (GH_WATCH_WHY_MAX - 1) + "…"

    snap_thin = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
        gh_why_n=20,
    )
    assert snap_thin["github_watch_why_limit"] == 20
    thin_row = snap_thin["github_repos"][0]
    assert len(thin_row["why"]) == 20
    assert thin_row["why"].endswith("…")
