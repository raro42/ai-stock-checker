"""tradermonty #737 follow-up: Window A / summarize trades.jsonl UTF-8 IO."""

from __future__ import annotations

from pathlib import Path

from stock_checker.paper_accounts import _last_trade_at
from stock_checker.promote_ab import load_trades_jsonl


def test_load_trades_jsonl_preserves_non_ascii(tmp_path: Path) -> None:
    path = tmp_path / "trades.jsonl"
    path.write_text(
        '{"type":"BUY","symbol":"SAP.DE","note":"München · 東京","timestamp":"2026-11-16T12:00:00Z"}\n',
        encoding="utf-8",
    )
    rows = load_trades_jsonl(path)
    assert len(rows) == 1
    assert rows[0]["note"] == "München · 東京"


def test_load_trades_jsonl_invalid_utf8_is_empty(tmp_path: Path) -> None:
    """Undecodable bytes → [], not a fake thin Window A sample / crash."""
    path = tmp_path / "trades.jsonl"
    path.write_bytes(b'{"type":"BUY"}\n\xff\xfe\n')
    assert load_trades_jsonl(path) == []


def test_load_trades_jsonl_missing_is_empty(tmp_path: Path) -> None:
    assert load_trades_jsonl(tmp_path / "missing.jsonl") == []


def test_load_trades_jsonl_source_uses_utf8() -> None:
    root = Path(__file__).resolve().parents[1] / "stock_checker"
    src = (root / "promote_ab.py").read_text(encoding="utf-8")
    assert 'p.open(encoding="utf-8")' in src
    assert "UnicodeDecodeError" in src
    summarize = (
        Path(__file__).resolve().parents[1] / "scripts" / "summarize_trades.py"
    ).read_text(encoding="utf-8")
    assert "load_trades_jsonl" in summarize
    assert 'encoding="utf-8"' in summarize


def test_last_trade_at_invalid_utf8_is_blank(tmp_path: Path) -> None:
    path = tmp_path / "trades.jsonl"
    path.write_bytes(b'{"timestamp":"2026-11-16T12:00:00Z"}\xff')
    assert _last_trade_at(path) == ""
