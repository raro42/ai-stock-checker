#!/usr/bin/env python3
"""Offline tests for GitHub idea watch (no network)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import github_idea_watch as gw


class FakeClient:
    def __init__(self, payloads: dict[str, object]):
        self.payloads = payloads

    def get_json(self, path: str):
        # normalize
        key = path if path.startswith("/") else f"/{path}"
        if key not in self.payloads:
            raise RuntimeError(f"missing fixture {key}")
        return self.payloads[key]


def test_diff_baseline_and_updates():
    activity = {
        "commits": [
            {"sha": "aaa1111full", "short": "aaa1111", "message": "feat A", "date": "t", "url": "u"},
            {"sha": "bbb2222full", "short": "bbb2222", "message": "fix B", "date": "t", "url": "u"},
        ],
        "releases": [{"tag": "v1.0", "name": "v1.0", "published_at": "t", "url": "u", "prerelease": False}],
    }
    baseline = gw.diff_against_state(activity, {})
    assert baseline["first_seen"] is True
    assert baseline["has_updates"] is False
    assert len(baseline["new_commits"]) == 2  # capped tip window on first see uses [:3]

    prev = {"last_commit_sha": "bbb2222full", "last_release_tag": "v1.0"}
    # tip is aaa, so new until we hit bbb
    nxt = gw.diff_against_state(activity, prev)
    assert nxt["has_updates"] is True
    assert nxt["new_commits"][0]["sha"] == "aaa1111full"
    assert nxt["new_releases"] == []


def test_interval_from_cadence():
    # ~1 commit/day → ~12h recheck
    assert gw.interval_from_cadence(86400) == 43200
    # hot: 2h avg gap → clamp to MIN 3h
    assert gw.interval_from_cadence(2 * 3600) == gw.MIN_CHECK_INTERVAL_SEC
    # cold: 30d avg gap → clamp to MAX 7d
    assert gw.interval_from_cadence(30 * 86400) == gw.MAX_CHECK_INTERVAL_SEC
    assert gw.interval_from_cadence(None, archived=True) == gw.MAX_CHECK_INTERVAL_SEC
    assert gw.commits_per_day(86400) == 1.0


def test_cadence_refuses_bool_gap() -> None:
    """tradermonty #700/#655: True must not invent 1s gap / 86400 cpd."""
    assert gw._coerce_gap_sec(True) is None
    assert gw._coerce_gap_sec(False) is None
    assert gw._coerce_gap_sec(0) is None
    assert gw._coerce_gap_sec(-1) is None
    assert gw._coerce_gap_sec(86400) == 86400.0
    # bool subclass of int — bare isinstance would pass True→1s → MIN recheck.
    assert gw.interval_from_cadence(True) == gw.DEFAULT_CHECK_INTERVAL_SEC
    assert gw.interval_from_cadence(False) == gw.DEFAULT_CHECK_INTERVAL_SEC
    assert (
        gw.interval_from_cadence(None, single_commit_age_sec=True)
        == gw.DEFAULT_CHECK_INTERVAL_SEC
    )
    assert gw.commits_per_day(True) == 0.0
    assert gw.commits_per_day(False) == 0.0
    assert gw._coerce_check_interval_sec(True) == gw.DEFAULT_CHECK_INTERVAL_SEC
    assert gw._coerce_check_interval_sec(False) == gw.DEFAULT_CHECK_INTERVAL_SEC
    assert gw._coerce_commits_per_day_rate(True) == 0.0
    assert gw._coerce_commits_per_day_rate(False) == 0.0
    assert gw._coerce_commits_per_day_rate(12.5) == 12.5
    now = gw._parse_iso("2026-11-23T00:00:00Z")
    assert now is not None
    sched = gw._schedule_fields(
        avg_gap=True,
        interval=gw.DEFAULT_CHECK_INTERVAL_SEC,
        now=now,
    )
    assert sched["avg_commit_gap_sec"] is None
    assert sched["avg_commit_gap_hours"] is None
    assert sched["commits_per_day"] == 0.0


def test_stars_and_page_limit_refuse_bool() -> None:
    """tradermonty #700/#655: True must not invent 1★ or per_page=1 strip."""
    assert gw._coerce_star_count(True) == 0
    assert gw._coerce_star_count(False) == 0
    assert gw._coerce_star_count(-1) == 0
    assert gw._coerce_star_count(12) == 12
    assert gw._coerce_page_limit(True, default=8) == 8
    assert gw._coerce_page_limit(False, default=8) == 8
    assert gw._coerce_page_limit(0, default=8) == 8
    assert gw._coerce_page_limit(5, default=8) == 5
    assert gw._coerce_page_limit(500, default=8, ceiling=100) == 100


def test_digest_meters_and_gap_hours_refuse_bool() -> None:
    """tradermonty #700/#655: True must not invent digest 1-counts / 1s / 1.0h."""
    assert gw._coerce_nonneg_count(True) == 0
    assert gw._coerce_nonneg_count(False) == 0
    assert gw._coerce_nonneg_count(-3) == 0
    assert gw._coerce_nonneg_count(4) == 4
    assert gw._coerce_loop_sleep_sec(True) == gw.DEFAULT_CHECK_INTERVAL_SEC
    assert gw._coerce_loop_sleep_sec(False) == gw.DEFAULT_CHECK_INTERVAL_SEC
    assert gw._coerce_loop_sleep_sec(True, default=0) == 0
    assert gw._coerce_loop_sleep_sec(60) == gw.MIN_LOOP_SLEEP_SEC
    assert gw._coerce_loop_sleep_sec(gw.MIN_LOOP_SLEEP_SEC + 10) == gw.MIN_LOOP_SLEEP_SEC + 10
    assert gw._coerce_gap_hours(True) is None
    assert gw._coerce_gap_hours(False) is None
    assert gw._coerce_gap_hours(-1) is None
    assert gw._coerce_gap_hours(1.5) == 1.5

    digest = gw.build_digest(
        [{"repo": "acme/x", "why": "w"}],
        [
            {
                "repo": "acme/x",
                "url": "https://github.com/acme/x",
                "description": "",
                "stars": True,
                "pushed_at": "t",
                "default_branch": "main",
                "archived": False,
                "error": None,
                "commits": [],
                "releases": [],
                "avg_commit_gap_hours": True,
            }
        ],
        [
            {
                "first_seen": False,
                "new_commits": [],
                "new_releases": [],
                "has_updates": False,
                "baseline": False,
                "tip_sha": "",
                "tip_tag": "",
                "tip_message": "",
            }
        ],
        checked_count=True,
        skipped_count=False,
        next_sleep_sec=True,
    )
    assert digest["checked_count"] == 0
    assert digest["skipped_count"] == 0
    assert digest["update_count"] == 0
    assert digest["repo_count"] == 1
    assert digest["next_sleep_sec"] == gw.DEFAULT_CHECK_INTERVAL_SEC
    assert digest["repos"][0]["stars"] == 0

    md = gw.render_markdown(
        {
            "generated_at": "t",
            "repo_count": True,
            "checked_count": True,
            "skipped_count": False,
            "update_count": True,
            "next_sleep_sec": True,
            "idea_bullets": [],
            "repos": [
                {
                    "repo": "a/b",
                    "url": "https://github.com/a/b",
                    "description": "d",
                    "stars": True,
                    "pushed_at": "t",
                    "default_branch": "main",
                    "archived": False,
                    "error": None,
                    "why": "w",
                    "baseline": False,
                    "has_updates": False,
                    "new_commits": [],
                    "new_releases": [],
                    "avg_commit_gap_hours": True,
                    "commits_per_day": True,
                    "check_interval_sec": True,
                    "next_check_at": "soon",
                }
            ],
        }
    )
    assert "Repos watched: **0**" in md
    assert "Checked this run: **0**" in md
    assert "Repos with new activity: **0**" in md
    assert "Next loop sleep: **0s**" in md
    assert "Stars: 0" in md
    assert "Cadence:" not in md  # True→1.0h gap must not invent a cadence strip

    class CapturingClient:
        def __init__(self) -> None:
            self.paths: list[str] = []

        def get_json(self, path: str):
            self.paths.append(path)
            if "commits" in path:
                return []
            if "releases" in path:
                return []
            return {
                "html_url": "https://github.com/acme/x",
                "description": "",
                "stargazers_count": True,
                "pushed_at": "2026-11-23T00:00:00Z",
                "default_branch": "main",
                "archived": False,
            }

    client = CapturingClient()
    meta = gw.fetch_repo_meta(client, "acme/x")
    assert meta["stars"] == 0
    act = gw.fetch_repo_activity(client, "acme/x", commits=True, releases=True)
    assert act["stars"] == 0
    assert any("per_page=8" in p for p in client.paths)
    assert any("per_page=3" in p for p in client.paths)
    assert not any("per_page=1" in p for p in client.paths)

    state = gw.update_repo_state(
        {},
        tip_sha="",
        tip_tag="",
        url="u",
        stars=True,
        pushed_at="",
        schedule={
            "avg_commit_gap_sec": None,
            "avg_commit_gap_hours": None,
            "commits_per_day": 0.0,
            "check_interval_sec": gw.DEFAULT_CHECK_INTERVAL_SEC,
            "next_check_at": "2026-11-23T00:00:00Z",
        },
    )
    assert state["stars"] == 0


def test_avg_commit_gap_and_due():
    commits = [
        {"date": "2026-07-26T00:00:00Z"},
        {"date": "2026-07-25T00:00:00Z"},
        {"date": "2026-07-24T00:00:00Z"},
    ]
    gap = gw.avg_commit_gap_seconds(commits)
    assert gap == 86400
    now = gw._parse_iso("2026-07-26T12:00:00Z")
    assert gw.is_repo_due({}, now) is True
    assert (
        gw.is_repo_due({"next_check_at": "2026-07-26T18:00:00Z"}, now) is False
    )
    assert gw.is_repo_due({"next_check_at": "2026-07-26T11:00:00Z"}, now) is True


def test_run_watch_offline(tmp_path: Path, monkeypatch):
    watchlist = tmp_path / "watch.json"
    watchlist.write_text(
        json.dumps(
            {
                "repos": [
                    {"repo": "acme/screener", "why": "test"},
                    {"repo": "acme/dead", "why": "err"},
                ]
            }
        )
    )
    state_dir = tmp_path / "state"
    docs = tmp_path / "docs" / "history"
    docs.mkdir(parents=True)
    monkeypatch.setattr(gw, "ROOT", tmp_path)

    payloads = {
        "/repos/acme/screener": {
            "html_url": "https://github.com/acme/screener",
            "description": "A screener",
            "stargazers_count": 12,
            "pushed_at": "2026-07-26T00:00:00Z",
            "default_branch": "main",
            "archived": False,
        },
        "/repos/acme/screener/commits?per_page=5": [
            {
                "sha": "deadbeefcafe",
                "html_url": "https://github.com/acme/screener/commit/deadbeefcafe",
                "commit": {
                    "message": "add RSI filter\n\nbody",
                    "author": {"date": "2026-07-26T01:00:00Z"},
                },
            },
            {
                "sha": "older0000001",
                "html_url": "u",
                "commit": {
                    "message": "init",
                    "author": {"date": "2026-07-25T01:00:00Z"},
                },
            },
        ],
        "/repos/acme/screener/releases?per_page=3": [
            {
                "tag_name": "v0.1.0",
                "name": "First",
                "published_at": "2026-07-01T00:00:00Z",
                "html_url": "https://github.com/acme/screener/releases/tag/v0.1.0",
                "prerelease": False,
            }
        ],
    }

    class MixedClient(FakeClient):
        def get_json(self, path: str):
            key = path if path.startswith("/") else f"/{path}"
            if key.startswith("/repos/acme/dead"):
                raise RuntimeError("404")
            return super().get_json(path)

    client = MixedClient(payloads)
    digest = gw.run_watch(
        watchlist_path=watchlist,
        state_dir=state_dir,
        client=client,
        archive=True,
        commit_count=5,
        force=True,
    )
    assert digest["repo_count"] == 2
    assert digest["checked_count"] == 2
    assert (state_dir / "next_sleep_sec").exists()
    assert (state_dir / "latest.md").exists()
    md = (state_dir / "latest.md").read_text()
    assert "acme/screener" in md
    assert "Cadence:" in md or "recheck" in md.lower() or "commits/day" in md

    # Not due yet → skip deep work
    digest2 = gw.run_watch(
        watchlist_path=watchlist,
        state_dir=state_dir,
        client=client,
        archive=False,
        commit_count=5,
        force=False,
    )
    assert digest2["skipped_count"] >= 1
    assert digest2["update_count"] == 0

    # Make due + new tip commit
    st = json.loads((state_dir / "state.json").read_text())
    st["repos"]["acme/screener"]["next_check_at"] = "2020-01-01T00:00:00Z"
    st["repos"]["acme/screener"]["pushed_at"] = "2026-07-26T00:00:00Z"
    (state_dir / "state.json").write_text(json.dumps(st))
    payloads["/repos/acme/screener"]["pushed_at"] = "2026-07-26T12:00:00Z"
    payloads["/repos/acme/screener/commits?per_page=5"] = [
        {
            "sha": "newsha0000001",
            "html_url": "u",
            "commit": {
                "message": "add earnings blackout",
                "author": {"date": "2026-07-26T12:00:00Z"},
            },
        },
        payloads["/repos/acme/screener/commits?per_page=5"][0],
    ]
    digest3 = gw.run_watch(
        watchlist_path=watchlist,
        state_dir=state_dir,
        client=client,
        archive=False,
        commit_count=5,
        force=False,
    )
    assert digest3["update_count"] == 1
    assert any("earnings blackout" in b for b in digest3["idea_bullets"])


def test_render_markdown_contains_guidance():
    md = gw.render_markdown(
        {
            "generated_at": "t",
            "repo_count": 1,
            "update_count": 0,
            "idea_bullets": [],
            "repos": [
                {
                    "repo": "a/b",
                    "url": "https://github.com/a/b",
                    "description": "d",
                    "stars": 1,
                    "pushed_at": "t",
                    "default_branch": "main",
                    "archived": False,
                    "error": None,
                    "why": "w",
                    "baseline": True,
                    "has_updates": False,
                    "new_commits": [],
                    "new_releases": [],
                }
            ],
        }
    )
    assert "transferable" in md.lower() or "adapt" in md.lower()
    assert "a/b" in md
