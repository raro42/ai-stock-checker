"""Ideas GitHub-watch strip ceilings refuse bool invent."""

from __future__ import annotations

import json
from pathlib import Path

from openbb_backend.desk import (
    GH_WATCH_IDEAS_STRIP,
    GH_WATCH_NOTES_STRIP,
    GH_WATCH_REPOS_STRIP,
    _coerce_gh_watch_strip_limit,
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


def test_gh_watch_strip_defaults() -> None:
    assert GH_WATCH_REPOS_STRIP == 12
    assert GH_WATCH_IDEAS_STRIP == 8
    assert GH_WATCH_NOTES_STRIP == 6


def test_gh_watch_strip_refuses_bool() -> None:
    assert _coerce_gh_watch_strip_limit(True) == GH_WATCH_NOTES_STRIP
    assert _coerce_gh_watch_strip_limit(False) == GH_WATCH_NOTES_STRIP
    assert _coerce_gh_watch_strip_limit(0) == GH_WATCH_NOTES_STRIP
    assert _coerce_gh_watch_strip_limit(None) == GH_WATCH_NOTES_STRIP
    assert _coerce_gh_watch_strip_limit(3) == 3
    assert (
        _coerce_gh_watch_strip_limit(True, default=GH_WATCH_REPOS_STRIP)
        == GH_WATCH_REPOS_STRIP
    )


def test_load_desk_snapshot_refuses_bool_gh_watch_strips(
    tmp_path: Path, monkeypatch
) -> None:
    """True→1 must not invent a one-repo / one-bullet Ideas strip."""
    _seed_portfolio(tmp_path)
    gw = tmp_path / "github_watch"
    gw.mkdir(parents=True, exist_ok=True)
    repos = []
    for i in range(15):
        repos.append(
            {
                "repo": f"acme/r{i}",
                "url": f"https://github.com/acme/r{i}",
                "why": "test",
                "stars": i,
                "pushed_at": f"2026-11-{15 - (i % 10):02d}T12:00:00Z",
                "has_updates": False,
                "tip_sha": f"{i:016x}",
                "tip_message": f"Tip {i}",
                "commits": [
                    {
                        "sha": f"{i:016x}deadbeef",
                        "date": f"2026-11-{15 - (i % 10):02d}T08:00:00Z",
                        "message": f"Tip {i}",
                    }
                ],
            }
        )
    ideas = [f"idea {i}" for i in range(12)]
    (gw / "latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-11-24T12:00:00Z",
                "repo_count": 15,
                "checked_count": 15,
                "update_count": 0,
                "idea_bullets": ideas,
                "repos": repos,
            }
        )
    )
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")

    snap_true = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
        gh_repos_n=True,
        gh_ideas_n=True,
        gh_notes_n=True,
    )
    assert snap_true["github_watch_repos_limit"] == GH_WATCH_REPOS_STRIP
    assert snap_true["github_watch_ideas_limit"] == GH_WATCH_IDEAS_STRIP
    assert snap_true["github_watch_notes_limit"] == GH_WATCH_NOTES_STRIP
    assert len(snap_true["github_repos"]) == GH_WATCH_REPOS_STRIP
    assert len(snap_true["github_ideas"]) == GH_WATCH_IDEAS_STRIP
    # Quiet notes stay empty when idea_bullets already spoke.
    assert snap_true["github_watch_notes"] == []
    # Digest meters stay full (not strip-capped).
    assert snap_true["github_watch_repos"] == 15
    assert snap_true["github_watch_checked"] == 15

    snap_false = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
        gh_repos_n=False,
        gh_ideas_n=False,
        gh_notes_n=False,
    )
    assert len(snap_false["github_repos"]) == GH_WATCH_REPOS_STRIP
    assert len(snap_false["github_ideas"]) == GH_WATCH_IDEAS_STRIP

    snap_thin = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
        gh_repos_n=3,
        gh_ideas_n=2,
        gh_notes_n=4,
    )
    assert len(snap_thin["github_repos"]) == 3
    assert len(snap_thin["github_ideas"]) == 2
    assert snap_thin["github_watch_repos_limit"] == 3
    assert snap_thin["github_watch_ideas_limit"] == 2
    assert snap_thin["github_watch_notes_limit"] == 4


def test_load_desk_snapshot_refuses_bool_gh_watch_quiet_notes(
    tmp_path: Path, monkeypatch
) -> None:
    """True→1 must not invent a one-note quiet strip via repos[:True]."""
    _seed_portfolio(tmp_path)
    gw = tmp_path / "github_watch"
    gw.mkdir(parents=True, exist_ok=True)
    repos = []
    for i in range(10):
        repos.append(
            {
                "repo": f"acme/q{i}",
                "url": f"https://github.com/acme/q{i}",
                "why": "quiet",
                "stars": i,
                "pushed_at": f"2026-11-{20 - i:02d}T12:00:00Z",
                "has_updates": False,
                "tip_sha": f"{i:016x}",
                "tip_message": f"Quiet tip {i}",
                "commits": [
                    {
                        "sha": f"{i:016x}deadbeef",
                        "date": f"2026-11-{20 - i:02d}T08:00:00Z",
                        "message": f"Quiet tip {i}",
                    }
                ],
            }
        )
    (gw / "latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-11-24T12:00:00Z",
                "repo_count": 10,
                "checked_count": 10,
                "update_count": 0,
                "idea_bullets": [],
                "repos": repos,
            }
        )
    )
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")

    snap_true = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
        gh_notes_n=True,
    )
    assert len(snap_true["github_watch_notes"]) == GH_WATCH_NOTES_STRIP
    assert snap_true["github_watch_notes_limit"] == GH_WATCH_NOTES_STRIP

    snap_thin = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
        gh_notes_n=2,
    )
    assert len(snap_thin["github_watch_notes"]) == 2
    assert snap_thin["github_watch_notes_limit"] == 2
