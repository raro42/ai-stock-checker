#!/usr/bin/env python3
"""Offline tests for desk repo footer metadata."""

from openbb_backend.repo_meta import load_repo_meta, _parse_git_date


def test_parse_git_date_utc():
    iso, display = _parse_git_date("2026-07-26T14:30:00+02:00")
    assert iso == "2026-07-26T12:30:00Z"
    assert "UTC" in display


def test_load_repo_meta_from_probe():
    meta = load_repo_meta(
        repo_url="https://github.com/raro42/ai-stock-checker",
        git_probe=lambda: {
            "sha": "abc123def456",
            "short_sha": "abc123d",
            "message": "style desk links with a shared palette",
            "committed_at": "2026-07-26T10:43:00Z",
            "committed_at_display": "2026-07-26 10:43 UTC",
        },
    )
    assert meta["available"] is True
    assert meta["short_sha"] == "abc123d"
    assert meta["commit_url"].endswith("/commit/abc123def456")
    assert "shared palette" in meta["message"]


def test_load_repo_meta_missing():
    meta = load_repo_meta(git_probe=lambda: None)
    assert meta["available"] is False
    assert meta["url"].endswith("ai-stock-checker")
