"""Persistence / OpenBB trade-limit knobs must refuse bool invents."""

from __future__ import annotations

import json
from pathlib import Path

from openbb_backend.main import (
    DEFAULT_OPENBB_TRADES_LIMIT,
    _coerce_trades_limit,
)
from stock_checker.persistence import DataPersistence, _coerce_load_limit


def test_coerce_load_limit_refuses_bool() -> None:
    """True→1 must not invent a one-row recent strip."""
    assert _coerce_load_limit(True) is None
    assert _coerce_load_limit(False) is None
    assert _coerce_load_limit(0) is None
    assert _coerce_load_limit(None) is None
    assert _coerce_load_limit(3) == 3


def test_coerce_trades_limit_refuses_bool() -> None:
    """OpenBB bool limit falls back to default (not True→1)."""
    assert _coerce_trades_limit(True) == DEFAULT_OPENBB_TRADES_LIMIT
    assert _coerce_trades_limit(False) == DEFAULT_OPENBB_TRADES_LIMIT
    assert _coerce_trades_limit(0) == DEFAULT_OPENBB_TRADES_LIMIT
    assert _coerce_trades_limit(7) == 7


def test_load_trades_refuses_bool_limit(tmp_path: Path) -> None:
    """Bool limit returns all rows (no True→1 tail invent)."""
    p = DataPersistence(str(tmp_path))
    for i in range(3):
        p.append_trade({"type": "BUY", "symbol": f"T{i}", "price": 10.0 + i})

    all_rows = p.load_trades()
    assert len(all_rows) == 3
    assert len(p.load_trades(limit=True)) == 3
    assert len(p.load_trades(limit=False)) == 3
    assert len(p.load_trades(limit=2)) == 2
    assert p.load_trades(limit=2)[-1]["symbol"] == "T2"


def test_load_findings_refuses_bool_limit(tmp_path: Path) -> None:
    """Bool limit returns all findings (no True→1 invent)."""
    p = DataPersistence(str(tmp_path))
    for i in range(3):
        p.append_finding({"symbol": f"F{i}", "action": "BUY", "score": i})

    assert len(p.load_findings(limit=True)) == 3
    assert len(p.load_findings(limit=1)) == 1
    assert p.load_findings(limit=1)[0]["symbol"] == "F2"


def test_openbb_load_trades_refuses_bool_limit(
    tmp_path: Path, monkeypatch
) -> None:
    """Workspace helper must not strip to one row on True."""
    import openbb_backend.main as main

    trades = tmp_path / "trades.jsonl"
    trades.write_text(
        "".join(
            json.dumps({"symbol": f"S{i}", "type": "BUY"}) + "\n" for i in range(5)
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)

    # Only 5 rows; default 50 → all 5; True must not become 1.
    assert len(main._load_trades(True)) == 5
    assert len(main._load_trades(False)) == 5
    assert len(main._load_trades(2)) == 2
    assert main._load_trades(2)[-1]["symbol"] == "S4"
