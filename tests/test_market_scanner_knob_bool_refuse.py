"""MarketScanner strip / retention knobs must refuse bool invents."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from stock_checker.market_scanner import (
    DEFAULT_ARCHIVE_KEEP_DAYS,
    DEFAULT_CRYPTO_MOMENTUM_TOP_N,
    DEFAULT_TOP_CRYPTO_COUNT,
    MarketScanner,
    _coerce_archive_keep_days,
    _coerce_scan_top_n,
    _coerce_top_crypto_count,
)


def _age(path: Path, days: int) -> None:
    ts = (datetime.now() - timedelta(days=days)).timestamp()
    os.utime(path, (ts, ts))


def test_coerce_top_crypto_count_refuses_bool() -> None:
    """True→1 must not invent a one-name live-major strip."""
    assert _coerce_top_crypto_count(True) == DEFAULT_TOP_CRYPTO_COUNT
    assert _coerce_top_crypto_count(False) == DEFAULT_TOP_CRYPTO_COUNT
    assert _coerce_top_crypto_count(0) == DEFAULT_TOP_CRYPTO_COUNT
    assert _coerce_top_crypto_count(2) == 2


def test_coerce_scan_top_n_refuses_bool() -> None:
    """True→1 must not invent a one-name alt deep-analysis pass."""
    assert _coerce_scan_top_n(True) == DEFAULT_CRYPTO_MOMENTUM_TOP_N
    assert _coerce_scan_top_n(False) == DEFAULT_CRYPTO_MOMENTUM_TOP_N
    assert _coerce_scan_top_n(0) == DEFAULT_CRYPTO_MOMENTUM_TOP_N
    assert _coerce_scan_top_n(5) == 5


def test_coerce_archive_keep_days_refuses_bool() -> None:
    """True→1d must not invent a thin archive wipe window."""
    assert _coerce_archive_keep_days(True) == DEFAULT_ARCHIVE_KEEP_DAYS
    assert _coerce_archive_keep_days(False) == DEFAULT_ARCHIVE_KEEP_DAYS
    assert _coerce_archive_keep_days(0) == DEFAULT_ARCHIVE_KEEP_DAYS
    assert _coerce_archive_keep_days(14) == 14


def test_market_scanner_ctor_refuses_bool_top_crypto() -> None:
    """Ctor must not store True (int(True)→1 strip invent)."""
    scanner = MarketScanner(top_crypto_count=True)
    assert scanner.top_crypto_count == DEFAULT_TOP_CRYPTO_COUNT
    scanner2 = MarketScanner(top_crypto_count=False)
    assert scanner2.top_crypto_count == DEFAULT_TOP_CRYPTO_COUNT
    scanner3 = MarketScanner(top_crypto_count=2)
    assert scanner3.top_crypto_count == 2


def test_cleanup_old_archives_refuses_bool_keep_days(tmp_path: Path) -> None:
    """Bool keep_days falls back to 7d (not True→1d wipe)."""
    scanner = MarketScanner.__new__(MarketScanner)
    archive = tmp_path / "archive"
    archive.mkdir()

    old = archive / "opportunities_20200101_000000.json"
    old.write_text("{}", encoding="utf-8")
    old_txt = archive / "opportunities_20200101_000000.txt"
    old_txt.write_text("old", encoding="utf-8")
    _age(old, 3)
    _age(old_txt, 3)

    recent = archive / "opportunities_20260725_120000.json"
    recent.write_text("{}", encoding="utf-8")

    # Without refuse, True→1d would prune the 3-day-old publish.
    removed = scanner.cleanup_old_archives(archive, keep_days=True)
    assert removed == 0
    assert old.exists()
    assert recent.exists()

    removed2 = scanner.cleanup_old_archives(archive, keep_days=2)
    assert removed2 == 1
    assert not old.exists()
    assert recent.exists()
