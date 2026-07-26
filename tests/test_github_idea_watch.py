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
            }
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
        "/repos/acme/dead": None,  # will error via Fake if we raise — use exception path
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
    )
    assert digest["repo_count"] == 2
    assert (state_dir / "latest.md").exists()
    assert (state_dir / "latest.json").exists()
    assert (tmp_path / "docs" / "history" / "github_watch_latest.md").exists()
    md = (state_dir / "latest.md").read_text()
    assert "acme/screener" in md
    assert "RSI" in md or "baseline" in md.lower()

    # Second run with same tip → quiet
    digest2 = gw.run_watch(
        watchlist_path=watchlist,
        state_dir=state_dir,
        client=client,
        archive=True,
        commit_count=5,
    )
    assert digest2["update_count"] == 0

    # New commit → update flagged
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
    assert "transferable idea" in md.lower() or "Steal" in md
    assert "a/b" in md
