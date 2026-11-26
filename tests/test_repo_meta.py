#!/usr/bin/env python3
"""Offline tests for desk repo footer metadata."""

from openbb_backend.repo_meta import (
    BUILD_INFO_SHORT_SHA_CHARS,
    REPO_SHORT_SHA_CHARS,
    _clip_repo_short_sha,
    _coerce_repo_short_sha_chars,
    _parse_git_date,
    load_repo_meta,
)


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


def test_repo_short_sha_clip_refuses_bool_ceiling() -> None:
    """True→1 must not invent a one-char footer SHA; False must not wipe."""
    full = "deadbeefcafebabe01234567"
    default = _clip_repo_short_sha(full)
    assert len(default) == REPO_SHORT_SHA_CHARS
    assert default == full[:REPO_SHORT_SHA_CHARS]
    assert _clip_repo_short_sha(full, True) == default
    assert _clip_repo_short_sha(full, False) == default
    assert _clip_repo_short_sha(full, 0) == default
    assert _coerce_repo_short_sha_chars(True) == REPO_SHORT_SHA_CHARS
    assert _coerce_repo_short_sha_chars(False) == REPO_SHORT_SHA_CHARS
    assert _clip_repo_short_sha(full, 4) == full[:4]

    build = _clip_repo_short_sha(full, default=BUILD_INFO_SHORT_SHA_CHARS)
    assert len(build) == BUILD_INFO_SHORT_SHA_CHARS
    assert _clip_repo_short_sha(
        full, True, default=BUILD_INFO_SHORT_SHA_CHARS
    ) == build
    assert _clip_repo_short_sha(
        full, False, default=BUILD_INFO_SHORT_SHA_CHARS
    ) == build
    assert (
        _coerce_repo_short_sha_chars(True, BUILD_INFO_SHORT_SHA_CHARS)
        == BUILD_INFO_SHORT_SHA_CHARS
    )


def test_load_repo_meta_fallback_sha_refuses_bool_ceiling() -> None:
    """Missing short_sha falls back to clipped full SHA — bool cannot invent."""
    full = "abcdef0123456789deadbeef"
    meta = load_repo_meta(
        git_probe=lambda: {
            "sha": full,
            "short_sha": "",
            "message": "footer claim honesty",
            "committed_at": "2026-11-26T18:00:00Z",
            "committed_at_display": "2026-11-26 18:00 UTC",
        },
        short_sha_n=True,
    )
    assert meta["short_sha"] == full[:REPO_SHORT_SHA_CHARS]
    thin = load_repo_meta(
        git_probe=lambda: {
            "sha": full,
            "short_sha": "",
            "message": "footer claim honesty",
            "committed_at": "2026-11-26T18:00:00Z",
            "committed_at_display": "2026-11-26 18:00 UTC",
        },
        short_sha_n=3,
    )
    assert thin["short_sha"] == full[:3]
