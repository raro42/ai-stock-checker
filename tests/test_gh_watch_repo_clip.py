"""Ideas GitHub-watch repo-name clip ceilings refuse bool invent."""

from __future__ import annotations

import json
from pathlib import Path

from openbb_backend.desk import (
    GH_WATCH_REPO_MAX,
    _clip_gh_watch_repo,
    _coerce_gh_watch_repo_chars,
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


def test_gh_watch_repo_default() -> None:
    assert GH_WATCH_REPO_MAX == 48


def test_gh_watch_repo_coerce_refuses_bool() -> None:
    assert _coerce_gh_watch_repo_chars(True) == GH_WATCH_REPO_MAX
    assert _coerce_gh_watch_repo_chars(False) == GH_WATCH_REPO_MAX
    assert _coerce_gh_watch_repo_chars(0) == GH_WATCH_REPO_MAX
    assert _coerce_gh_watch_repo_chars(None) == GH_WATCH_REPO_MAX
    assert _coerce_gh_watch_repo_chars(24) == 24


def test_clip_gh_watch_repo_ellipsis() -> None:
    long = "r" * 80
    clipped = _clip_gh_watch_repo(long)
    assert len(clipped) == GH_WATCH_REPO_MAX
    assert clipped.endswith("…")
    assert clipped == "r" * (GH_WATCH_REPO_MAX - 1) + "…"
    # True→1 must not invent a one-char repo name.
    assert _clip_gh_watch_repo(long, True) == clipped
    assert _clip_gh_watch_repo(long, False) == clipped
    thin = _clip_gh_watch_repo(long, 20)
    assert len(thin) == 20
    assert thin.endswith("…")
    assert _clip_gh_watch_repo("acme/short") == "acme/short"
    assert _clip_gh_watch_repo("") == ""
    assert _clip_gh_watch_repo(None) == ""


def test_load_desk_snapshot_refuses_bool_gh_watch_repo_clip(
    tmp_path: Path, monkeypatch
) -> None:
    """True→1 must not invent a one-char repo on Ideas watched list."""
    _seed_portfolio(tmp_path)
    gw = tmp_path / "github_watch"
    gw.mkdir(parents=True, exist_ok=True)
    long_repo = "owner/" + ("n" * 80)
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
                        "repo": long_repo,
                        "url": "https://github.com/owner/long",
                        "why": "screener UX",
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
        gh_repo_n=True,
    )
    assert snap_true["github_watch_repo_limit"] == GH_WATCH_REPO_MAX
    repos = snap_true["github_repos"]
    assert len(repos) == 1
    assert len(repos[0]["repo"]) == GH_WATCH_REPO_MAX
    assert repos[0]["repo"].endswith("…")
    assert repos[0]["repo"] == "owner/" + "n" * (GH_WATCH_REPO_MAX - 7) + "…"

    snap_thin = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
        gh_repo_n=20,
    )
    assert snap_thin["github_watch_repo_limit"] == 20
    thin = snap_thin["github_repos"][0]["repo"]
    assert len(thin) == 20
    assert thin.endswith("…")


def test_quiet_notes_use_clipped_repo_name(
    tmp_path: Path, monkeypatch
) -> None:
    """Quiet composed notes reuse the clipped repo (not raw passthrough)."""
    _seed_portfolio(tmp_path)
    gw = tmp_path / "github_watch"
    gw.mkdir(parents=True, exist_ok=True)
    long_repo = "owner/" + ("n" * 80)
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
                        "repo": long_repo,
                        "url": "https://github.com/owner/long",
                        "why": "screener UX",
                        "stars": 1,
                        "pushed_at": "2026-11-20T12:00:00Z",
                        "has_updates": False,
                        "tip_sha": "cafebabe",
                        "tip_message": "quiet tip",
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
        gh_repo_n=24,
        gh_idea_n=200,
    )
    assert snap["github_ideas"] == []
    notes = snap["github_watch_notes"]
    assert len(notes) == 1
    assert notes[0].startswith("owner/" + "n" * 17 + "…:")
