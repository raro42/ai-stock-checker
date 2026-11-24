"""Ideas GitHub-watch date clip ceilings refuse bool invent."""

from __future__ import annotations

import json
from pathlib import Path

from openbb_backend.desk import (
    GH_WATCH_DATE_CHARS,
    _clip_gh_watch_date,
    _coerce_gh_watch_date_chars,
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


def test_gh_watch_date_default() -> None:
    assert GH_WATCH_DATE_CHARS == 10


def test_gh_watch_date_coerce_refuses_bool() -> None:
    assert _coerce_gh_watch_date_chars(True) == GH_WATCH_DATE_CHARS
    assert _coerce_gh_watch_date_chars(False) == GH_WATCH_DATE_CHARS
    assert _coerce_gh_watch_date_chars(0) == GH_WATCH_DATE_CHARS
    assert _coerce_gh_watch_date_chars(None) == GH_WATCH_DATE_CHARS
    assert _coerce_gh_watch_date_chars(4) == 4


def test_clip_gh_watch_date() -> None:
    stamp = "2026-11-20T08:00:00Z"
    assert _clip_gh_watch_date(stamp) == "2026-11-20"
    # True→1 must not invent a one-char date.
    assert _clip_gh_watch_date(stamp, True) == "2026-11-20"
    assert _clip_gh_watch_date(stamp, False) == "2026-11-20"
    assert _clip_gh_watch_date(stamp, 4) == "2026"
    assert _clip_gh_watch_date("") == ""
    assert _clip_gh_watch_date(None) == ""


def test_load_desk_snapshot_refuses_bool_gh_watch_date_clip(
    tmp_path: Path, monkeypatch
) -> None:
    """True→1 must not invent a one-char pushed_at / last_commit_at on Ideas."""
    _seed_portfolio(tmp_path)
    gw = tmp_path / "github_watch"
    gw.mkdir(parents=True, exist_ok=True)
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
                        "repo": "acme/date",
                        "url": "https://github.com/acme/date",
                        "why": "test",
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
        gh_date_n=True,
    )
    assert snap_true["github_watch_date_limit"] == GH_WATCH_DATE_CHARS
    row = snap_true["github_repos"][0]
    assert row["last_commit_at"] == "2026-11-19"
    assert row["pushed_at"] == "2026-11-20"

    snap_thin = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
        gh_date_n=4,
    )
    assert snap_thin["github_watch_date_limit"] == 4
    thin_row = snap_thin["github_repos"][0]
    assert thin_row["last_commit_at"] == "2026"
    assert thin_row["pushed_at"] == "2026"
