#!/usr/bin/env python3
"""Unit tests for archive cleanup."""

from datetime import datetime, timedelta
from pathlib import Path

from stock_checker.market_scanner import MarketScanner


def test_cleanup_old_archives(tmp_path: Path):
    scanner = MarketScanner.__new__(MarketScanner)
    archive = tmp_path / "archive"
    archive.mkdir()

    old = archive / "opportunities_20200101_000000.json"
    old.write_text("{}")
    old_txt = archive / "opportunities_20200101_000000.txt"
    old_txt.write_text("old")
    # Force old mtime
    old_ts = (datetime.now() - timedelta(days=30)).timestamp()
    import os

    os.utime(old, (old_ts, old_ts))
    os.utime(old_txt, (old_ts, old_ts))

    recent = archive / "opportunities_20260725_120000.json"
    recent.write_text("{}")

    removed = scanner.cleanup_old_archives(archive, keep_days=7)
    assert removed == 1
    assert not old.exists()
    assert not old_txt.exists()
    assert recent.exists()
