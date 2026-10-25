#!/usr/bin/env python3
"""Unit tests for archive cleanup."""

import os
from datetime import datetime, timedelta
from pathlib import Path

from stock_checker.market_scanner import MarketScanner


def _age(path: Path, days: int) -> None:
    ts = (datetime.now() - timedelta(days=days)).timestamp()
    os.utime(path, (ts, ts))


def test_cleanup_old_archives(tmp_path: Path):
    scanner = MarketScanner.__new__(MarketScanner)
    archive = tmp_path / "archive"
    archive.mkdir()

    old = archive / "opportunities_20200101_000000.json"
    old.write_text("{}")
    old_txt = archive / "opportunities_20200101_000000.txt"
    old_txt.write_text("old")
    _age(old, 30)
    _age(old_txt, 30)

    recent = archive / "opportunities_20260725_120000.json"
    recent.write_text("{}")

    removed = scanner.cleanup_old_archives(archive, keep_days=7)
    assert removed == 1
    assert not old.exists()
    assert not old_txt.exists()
    assert recent.exists()


def test_cleanup_keeps_latest_symlink_target(tmp_path: Path):
    """Age prune must not delete the file ``*_latest`` points at (#682)."""
    scanner = MarketScanner.__new__(MarketScanner)
    archive = tmp_path / "archive"
    archive.mkdir()

    pinned = archive / "opportunities_20200101_000000.json"
    pinned.write_text('{"pin": true}')
    pinned_txt = archive / "opportunities_20200101_000000.txt"
    pinned_txt.write_text("pin")
    _age(pinned, 40)
    _age(pinned_txt, 40)

    stray = archive / "opportunities_20200115_000000.json"
    stray.write_text("{}")
    stray_txt = archive / "opportunities_20200115_000000.txt"
    stray_txt.write_text("stray")
    _age(stray, 35)
    _age(stray_txt, 35)

    newest = archive / "opportunities_20200201_000000.json"
    newest.write_text("{}")
    newest_txt = archive / "opportunities_20200201_000000.txt"
    newest_txt.write_text("newest")
    _age(newest, 20)
    _age(newest_txt, 20)

    (archive / "opportunities_latest.json").symlink_to(pinned.name)
    (archive / "opportunities_latest.txt").symlink_to(pinned_txt.name)

    removed = scanner.cleanup_old_archives(archive, keep_days=7)
    # Symlink target + newest protected; middle stray pair is pruned.
    assert removed == 1
    assert pinned.exists()
    assert pinned_txt.exists()
    assert newest.exists()
    assert not stray.exists()
    assert not stray_txt.exists()
    assert (archive / "opportunities_latest.json").resolve() == pinned.resolve()


def test_cleanup_keeps_newest_when_all_past_cutoff(tmp_path: Path):
    """When every timestamped pair is stale, keep the newest publish."""
    scanner = MarketScanner.__new__(MarketScanner)
    archive = tmp_path / "archive"
    archive.mkdir()

    older = archive / "opportunities_20200101_000000.json"
    older.write_text("{}")
    older_txt = archive / "opportunities_20200101_000000.txt"
    older_txt.write_text("older")
    _age(older, 40)
    _age(older_txt, 40)

    newest = archive / "opportunities_20200201_000000.json"
    newest.write_text('{"newest": true}')
    newest_txt = archive / "opportunities_20200201_000000.txt"
    newest_txt.write_text("newest")
    _age(newest, 30)
    _age(newest_txt, 30)

    removed = scanner.cleanup_old_archives(archive, keep_days=7)
    assert removed == 1
    assert not older.exists()
    assert not older_txt.exists()
    assert newest.exists()
    assert newest_txt.exists()
