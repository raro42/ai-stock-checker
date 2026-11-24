"""Ideas GitHub-watch tip clip ceilings refuse bool invent."""

from __future__ import annotations

import json
from pathlib import Path

from openbb_backend.desk import (
    GH_WATCH_TIP_MAX,
    GH_WATCH_TIP_SHA_CHARS,
    _clip_gh_watch_tip,
    _clip_gh_watch_tip_sha,
    _coerce_gh_watch_tip_chars,
    _coerce_gh_watch_tip_sha_chars,
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


def test_gh_watch_tip_defaults() -> None:
    assert GH_WATCH_TIP_MAX == 110
    assert GH_WATCH_TIP_SHA_CHARS == 7


def test_gh_watch_tip_coerce_refuses_bool() -> None:
    assert _coerce_gh_watch_tip_chars(True) == GH_WATCH_TIP_MAX
    assert _coerce_gh_watch_tip_chars(False) == GH_WATCH_TIP_MAX
    assert _coerce_gh_watch_tip_chars(0) == GH_WATCH_TIP_MAX
    assert _coerce_gh_watch_tip_chars(None) == GH_WATCH_TIP_MAX
    assert _coerce_gh_watch_tip_chars(40) == 40
    assert _coerce_gh_watch_tip_sha_chars(True) == GH_WATCH_TIP_SHA_CHARS
    assert _coerce_gh_watch_tip_sha_chars(False) == GH_WATCH_TIP_SHA_CHARS
    assert _coerce_gh_watch_tip_sha_chars(3) == 3


def test_clip_gh_watch_tip_ellipsis() -> None:
    long = "x" * 200
    clipped = _clip_gh_watch_tip(long)
    assert len(clipped) == GH_WATCH_TIP_MAX
    assert clipped.endswith("…")
    assert clipped == "x" * (GH_WATCH_TIP_MAX - 1) + "…"
    # True→1 must not invent a one-char tip.
    assert _clip_gh_watch_tip(long, True) == clipped
    assert _clip_gh_watch_tip(long, False) == clipped
    thin = _clip_gh_watch_tip(long, 20)
    assert len(thin) == 20
    assert thin.endswith("…")


def test_clip_gh_watch_tip_sha() -> None:
    sha = "abcdef0123456789deadbeef"
    assert _clip_gh_watch_tip_sha(sha) == "abcdef0"
    assert _clip_gh_watch_tip_sha(sha, True) == "abcdef0"
    assert _clip_gh_watch_tip_sha(sha, False) == "abcdef0"
    assert _clip_gh_watch_tip_sha(sha, 3) == "abc"
    assert _clip_gh_watch_tip_sha("") == ""
    assert _clip_gh_watch_tip_sha(None) == ""


def test_load_desk_snapshot_refuses_bool_gh_watch_tip_clip(
    tmp_path: Path, monkeypatch
) -> None:
    """True→1 must not invent a one-char tip / tip_short on Ideas repos."""
    _seed_portfolio(tmp_path)
    gw = tmp_path / "github_watch"
    gw.mkdir(parents=True, exist_ok=True)
    long_tip = "T" * 200
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
                        "repo": "acme/tip",
                        "url": "https://github.com/acme/tip",
                        "why": "test",
                        "stars": 1,
                        "pushed_at": "2026-11-20T12:00:00Z",
                        "has_updates": False,
                        "tip_sha": sha,
                        "tip_message": long_tip,
                        "commits": [
                            {
                                "sha": sha,
                                "date": "2026-11-20T08:00:00Z",
                                "message": long_tip,
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
        gh_tip_n=True,
        gh_tip_sha_n=True,
    )
    assert snap_true["github_watch_tip_limit"] == GH_WATCH_TIP_MAX
    assert snap_true["github_watch_tip_sha_limit"] == GH_WATCH_TIP_SHA_CHARS
    row = snap_true["github_repos"][0]
    assert len(row["tip_message"]) == GH_WATCH_TIP_MAX
    assert row["tip_message"].endswith("…")
    assert row["tip_short"] == sha[:GH_WATCH_TIP_SHA_CHARS]
    # Quiet notes reuse the clipped tip (not invent one-char).
    assert snap_true["github_watch_notes"]
    assert "T" * (GH_WATCH_TIP_MAX - 1) in snap_true["github_watch_notes"][0]

    snap_thin = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
        gh_tip_n=30,
        gh_tip_sha_n=4,
    )
    assert snap_thin["github_watch_tip_limit"] == 30
    assert snap_thin["github_watch_tip_sha_limit"] == 4
    thin_row = snap_thin["github_repos"][0]
    assert len(thin_row["tip_message"]) == 30
    assert thin_row["tip_short"] == sha[:4]
    # Date match still finds tip commit via default sha prefix.
    assert thin_row["last_commit_at"] == "2026-11-20"
