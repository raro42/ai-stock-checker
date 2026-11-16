"""tradermonty #737 follow-up: scanner archive + provider semaphore UTF-8 IO."""

from __future__ import annotations

import json
from pathlib import Path

from stock_checker.fetcher import ProviderSemaphore
from stock_checker.market_scanner import MarketScanner


def test_save_opportunities_archive_preserves_non_ascii(tmp_path: Path) -> None:
    """Archive JSON/txt keep non-ASCII notes (locale encoding must not mangle)."""
    scanner = object.__new__(MarketScanner)
    results = {
        "scan_time": "2026-11-16T12:00:00",
        "crypto_leaders": [],
        "stock_breakouts": [
            {
                "symbol": "SAP.DE",
                "sector": "München · Soft",
                "price": 100.0,
                "pct_from_high": -1.5,
                "strength": "東京",
            }
        ],
        "recommendations": [
            {
                "rank": 1,
                "symbol": "SAP.DE",
                "asset_class": "stock",
                "strategy": "breakout",
                "score": 72.0,
                "reasoning": "Xetra · München",
            }
        ],
    }
    json_path, report_path = scanner.save_opportunities_to_archive(
        results, data_dir=str(tmp_path)
    )
    assert json_path is not None and report_path is not None
    raw = Path(json_path).read_text(encoding="utf-8")
    assert "München" in raw
    assert "東京" in raw
    assert "\\u" not in raw  # ensure_ascii=False
    report = Path(report_path).read_text(encoding="utf-8")
    assert "München" in report
    assert "東京" in report


def test_provider_semaphore_utf8_roundtrip(tmp_path: Path) -> None:
    """Provider semaphore JSON is explicit UTF-8 read/write."""
    sem = ProviderSemaphore(str(tmp_path))
    sem.switch_provider("yfinance")
    text = sem.semaphore_file.read_text(encoding="utf-8")
    assert json.loads(text)["primary_provider"] == "yfinance"
    assert sem.get_primary_provider() == "yfinance"


def test_provider_semaphore_invalid_utf8_falls_back(tmp_path: Path) -> None:
    """Undecodable semaphore bytes → yfinance, not a crash."""
    sem = ProviderSemaphore(str(tmp_path))
    sem.semaphore_file.write_bytes(b'{"primary_provider": "finnhub"\xff}')
    assert sem.get_primary_provider() == "yfinance"


def test_scanner_fetcher_open_calls_use_utf8() -> None:
    """Source lint: leftover bare open() on archive/semaphore text paths."""
    root = Path(__file__).resolve().parents[1] / "stock_checker"
    scanner = (root / "market_scanner.py").read_text(encoding="utf-8")
    assert 'open(json_path, "w", encoding="utf-8")' in scanner
    assert 'open(report_path, "w", encoding="utf-8")' in scanner
    assert "safe_exc_text(symlink_error)" in scanner
    fetcher = (root / "fetcher.py").read_text(encoding="utf-8")
    assert 'open(self.semaphore_file, "r", encoding="utf-8")' in fetcher
    assert 'open(self.semaphore_file, "w", encoding="utf-8")' in fetcher
