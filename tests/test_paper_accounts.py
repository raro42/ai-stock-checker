"""Offline tests for Mode A paper account helpers (GitHub #4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from stock_checker.paper_accounts import (
    MAX_ACCOUNTS,
    SHARED_DESK_ACCOUNT_ID,
    AccountIdError,
    account_label,
    account_ledger_missing,
    account_switcher_options,
    build_leaderboard,
    ensure_account_ledger,
    ledger_dir,
    list_account_ids,
    normalize_account_id,
)


def test_normalize_account_id() -> None:
    assert normalize_account_id(None) == ""
    assert normalize_account_id("") == ""
    assert normalize_account_id("  Anna ") == "anna"
    assert normalize_account_id(SHARED_DESK_ACCOUNT_ID) == "desk"
    with pytest.raises(AccountIdError):
        normalize_account_id("Anna!")
    with pytest.raises(AccountIdError):
        normalize_account_id("1bad")


def test_ledger_dir_and_ensure(tmp_path: Path) -> None:
    assert ledger_dir(tmp_path, "") == tmp_path
    assert ledger_dir(tmp_path, "ben") == tmp_path / "accounts" / "ben"
    path = ensure_account_ledger(tmp_path, "desk")
    assert path == tmp_path / "accounts" / "desk"
    assert path.is_dir()
    assert list_account_ids(tmp_path) == ["desk"]
    assert account_label("desk") == "paper · account desk"
    assert account_label("desk", missing=True) == (
        "paper · account desk · missing ledger"
    )
    assert account_label("") == "paper · legacy root"
    assert account_label("", missing=True) == "paper · legacy root"


def test_account_ledger_missing(tmp_path: Path) -> None:
    assert account_ledger_missing(tmp_path, "") is False
    assert account_ledger_missing(tmp_path, "desk") is True
    path = ensure_account_ledger(tmp_path, "desk")
    assert account_ledger_missing(tmp_path, "desk") is True
    (path / "portfolio.json").write_text(
        json.dumps({"cash": 100_000.0, "initial_cash": 100_000.0})
    )
    assert account_ledger_missing(tmp_path, "desk") is False


def test_max_accounts(tmp_path: Path) -> None:
    for i in range(MAX_ACCOUNTS):
        ensure_account_ledger(tmp_path, f"u{i}")
    with pytest.raises(AccountIdError, match="max"):
        ensure_account_ledger(tmp_path, "overflow")
    # Idempotent create of an existing id still works at the cap.
    ensure_account_ledger(tmp_path, "u0")


def test_leaderboard_cost_basis(tmp_path: Path) -> None:
    root_port = {
        "cash": 50_000.0,
        "initial_cash": 100_000.0,
        "total_fees_paid": 12.5,
        "holdings": {"WMT": 10},
        "avg_buy_price": {"WMT": 100.0},
    }
    (tmp_path / "portfolio.json").write_text(json.dumps(root_port))
    (tmp_path / "trades.jsonl").write_text(
        json.dumps(
            {
                "type": "BUY",
                "symbol": "WMT",
                "timestamp": "2026-11-01T12:00:00+00:00",
            }
        )
        + "\n"
    )
    anna = ensure_account_ledger(tmp_path, "anna")
    (anna / "portfolio.json").write_text(
        json.dumps(
            {
                "cash": 100_000.0,
                "initial_cash": 100_000.0,
                "total_fees_paid": 0.0,
                "holdings": {},
                "avg_buy_price": {},
            }
        )
    )
    rows = build_leaderboard(tmp_path)
    # Sorted by cost-basis equity desc — anna €100k ahead of legacy €51k.
    assert [r["account_id"] for r in rows] == ["anna", ""]
    anna_row, legacy = rows[0], rows[1]
    assert anna_row["equity_cost"] == 100_000.0
    assert legacy["equity_cost"] == 51_000.0  # 50k cash + 1k WMT cost
    assert legacy["open_positions"] == 1
    assert legacy["fees"] == 12.5
    assert legacy["price_coverage"] == "cost"
    opts = account_switcher_options(tmp_path)
    assert opts[0]["id"] == ""
    assert opts[1]["id"] == "anna"
    assert opts[1]["href_q"] == "?account=anna"
