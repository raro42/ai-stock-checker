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
    account_ledger_status,
    account_switcher_options,
    build_leaderboard,
    ensure_account_ledger,
    leaderboard_missing_share,
    leaderboard_missing_vs_ready_delta,
    leaderboard_missing_vs_ready_delta_lead,
    leaderboard_missing_vs_ready_delta_lead_size,
    leaderboard_missing_vs_ready_lead,
    leaderboard_missing_vs_ready_lead_size,
    leaderboard_missing_vs_ready_lean,
    leaderboard_missing_vs_ready_sample_gap,
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
    assert account_label("desk", damaged=True) == (
        "paper · account desk · damaged ledger"
    )
    assert account_label("") == "paper · legacy root"
    assert account_label("", missing=True) == "paper · legacy root"


def test_account_ledger_missing(tmp_path: Path) -> None:
    assert account_ledger_missing(tmp_path, "") is False
    assert account_ledger_status(tmp_path, "") == "ok"
    assert account_ledger_missing(tmp_path, "desk") is True
    assert account_ledger_status(tmp_path, "desk") == "missing"
    path = ensure_account_ledger(tmp_path, "desk")
    assert account_ledger_missing(tmp_path, "desk") is True
    (path / "portfolio.json").write_text(
        json.dumps({"cash": 100_000.0, "initial_cash": 100_000.0})
    )
    assert account_ledger_missing(tmp_path, "desk") is False
    assert account_ledger_status(tmp_path, "desk") == "ok"


def test_account_ledger_damaged_not_euro_zero_ready(tmp_path: Path) -> None:
    """Corrupt portfolio.json must not rank as a €0 reset / ready book.

    xang1234 tolerate-missing + portfolio AI empty-vs-missing (GitHub #4).
    """
    path = ensure_account_ledger(tmp_path, "ben")
    (path / "portfolio.json").write_text("{not-json")
    assert account_ledger_status(tmp_path, "ben") == "damaged"
    assert account_ledger_missing(tmp_path, "ben") is True
    (tmp_path / "portfolio.json").write_text(
        json.dumps({"cash": 100_000.0, "initial_cash": 100_000.0})
    )
    anna = ensure_account_ledger(tmp_path, "anna")
    (anna / "portfolio.json").write_text(
        json.dumps(
            {
                "cash": 100_000.0,
                "initial_cash": 100_000.0,
                "holdings": {},
                "avg_buy_price": {},
            }
        )
    )
    rows = build_leaderboard(tmp_path)
    by_id = {r["account_id"]: r for r in rows}
    assert list(by_id)[-1] == "ben"  # unusable sorts last
    assert set(by_id) == {"", "anna", "ben"}
    ben = by_id["ben"]
    assert ben["missing"] is True
    assert ben["ledger_status"] == "damaged"
    assert ben["label"] == "paper · account ben · damaged ledger"
    assert ben["equity_cost"] == 0.0
    assert ben["price_coverage"] == "damaged"
    assert by_id["anna"]["missing"] is False
    opts = {o["id"]: o for o in account_switcher_options(tmp_path)}
    assert opts["ben"]["label"] == "ben · damaged"
    assert opts["ben"]["missing"] == "1"
    assert opts["ben"]["ledger_status"] == "damaged"
    share = leaderboard_missing_share(rows)
    assert share["n_missing"] == 1
    assert share["n_ready"] == 1
    assert share["bit"] == "1 missing · hot · 50%"


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
    # Empty shell dir must not rank as a €0 race loser.
    ensure_account_ledger(tmp_path, "desk")
    rows = build_leaderboard(tmp_path)
    # Sorted by equity desc; missing ledgers last.
    assert [r["account_id"] for r in rows] == ["anna", "", "desk"]
    anna_row, legacy, desk = rows[0], rows[1], rows[2]
    assert anna_row["equity_cost"] == 100_000.0
    assert anna_row["missing"] is False
    assert legacy["equity_cost"] == 51_000.0  # 50k cash + 1k WMT cost
    assert legacy["open_positions"] == 1
    assert legacy["fees"] == 12.5
    assert legacy["price_coverage"] == "cost"
    assert desk["missing"] is True
    assert desk["label"] == "paper · account desk · missing ledger"
    assert desk["equity_cost"] == 0.0
    assert desk["price_coverage"] == "missing"
    opts = account_switcher_options(tmp_path)
    assert opts[0]["id"] == ""
    by_id = {o["id"]: o for o in opts}
    assert by_id["anna"]["href_q"] == "?account=anna"
    assert by_id["anna"]["label"] == "anna"
    assert by_id["desk"]["label"] == "desk · missing"
    assert by_id["desk"]["missing"] == "1"
    # Absolute 1 missing ≠ board ownership — 1 of 2 named = 50% hot.
    share = leaderboard_missing_share(rows)
    assert share["n_named"] == 2
    assert share["n_missing"] == 1
    assert share["n_ready"] == 1
    assert share["missing_share_pct"] == 50.0
    assert share["missing_share_severity"] == "hot"
    assert share["warn"] is True
    assert share["bit"] == "1 missing · hot · 50%"
    # Missing% alone ≠ usable race peers — 1 of 2 ready = 50% mid (ok).
    assert share["ready_share_pct"] == 50.0
    assert share["ready_share_severity"] == "ok"
    # 1 missing · 1 ready → tied ownership (no strict lead · no size).
    # hot missing + mid ready → severity clash (sides alone ≠ band agreement).
    assert share["vs_ready_sample_gap"] == "missing/ready tied"
    assert share["vs_ready_lead"] == ""
    assert share["vs_ready_lead_size"] is None
    assert share["vs_ready_lean"] == (
        "missing vs ready clash · missing hot · ready ok"
    )
    assert share["vs_ready_lean_warn"] is True
    # 50% − 50% = 0pp → thin Δ; clash severity stays calm on lean vs Δ.
    # 0pp → Δ lead silent (signed pp alone ≠ ownership when spread is 0).
    assert share["vs_ready_delta_pp"] == 0
    assert share["vs_ready_delta_severity"] == "thin"
    assert share["vs_ready_lean_vs_delta"] == "align · thin"
    assert share["vs_ready_lean_vs_delta_warn"] is False
    assert share["vs_ready_delta_lead"] == ""
    assert share["vs_ready_delta_lead_size"] is None
    assert share["lean"] == (
        "vs 1 ready · 50% · missing/ready tied · "
        "missing vs ready clash · missing hot · ready ok · "
        "Δ thin · 0pp · lean vs Δ align · thin"
    )
    assert share["lean_warn"] is True
    assert share["lean_meta"] == (
        "vs ready · ownership · severity · Δ · lean/Δ"
    )
    # All ready → silent (bit + lean).
    ready_only = leaderboard_missing_share(
        [r for r in rows if not r.get("missing")]
    )
    assert ready_only["bit"] == ""
    assert ready_only["lean"] == ""
    # Sole missing named → 100% hot · vs 0 ready thin · align hot|thin.
    # 100% − 0% = +100pp → wide Δ; adverse hot|thin + wide warns.
    sole = leaderboard_missing_share([rows[2]])
    assert sole["bit"] == "1 missing · hot · 100%"
    assert sole["vs_ready_lean"] == "missing vs ready align · hot|thin"
    assert sole["vs_ready_lean_warn"] is False
    assert sole["vs_ready_delta_pp"] == 100
    assert sole["vs_ready_delta_severity"] == "wide"
    assert sole["vs_ready_lean_vs_delta"] == "align · wide"
    assert sole["vs_ready_lean_vs_delta_warn"] is True
    assert sole["vs_ready_delta_lead"] == "missing"
    # 100% vs 0% → Δ lead size silent (zero quieter).
    assert sole["vs_ready_delta_lead_size"] is None
    assert sole["lean"] == (
        "vs 0 ready · thin · 0% · missing vs ready align · hot|thin · "
        "Δ wide · +100pp · lean vs Δ align · wide · Δ lead · missing"
    )
    assert sole["lean_warn"] is True  # thin ready + adverse Δ open the fold
    assert sole["vs_ready_lead"] == ""
    assert sole["vs_ready_sample_gap"] == ""
    assert sole["vs_ready_lead_size"] is None
    assert sole["lean_meta"] == "vs ready · severity · Δ · lean/Δ · Δ lead"
    # Quiet band: 1 of 5 named → missing quiet · ready strong · align · size.
    quiet_rows = [
        {"account_id": "a0", "missing": True},
        {"account_id": "a1", "missing": False},
        {"account_id": "a2", "missing": False},
        {"account_id": "a3", "missing": False},
        {"account_id": "a4", "missing": False},
    ]
    quiet = leaderboard_missing_share(quiet_rows)
    assert quiet["missing_share_severity"] == "quiet"
    assert quiet["warn"] is False
    assert quiet["bit"] == "1 missing · quiet · 20%"
    assert quiet["ready_share_severity"] == "strong"
    assert quiet["vs_ready_lead"] == "lead ready · 80%"
    assert quiet["vs_ready_lead_name"] == "ready"
    assert quiet["vs_ready_lead_pct"] == 80
    assert quiet["vs_ready_lead_size"] == 4.0
    assert quiet["vs_ready_lead_size_louder"] == 4
    assert quiet["vs_ready_lead_size_quieter"] == 1
    assert quiet["vs_ready_lean"] == "missing vs ready align · quiet|strong"
    assert quiet["vs_ready_lean_warn"] is False
    # 20% − 80% = −60pp → wide Δ; quiet|strong stays calm on lean vs Δ.
    # Negative spread → Δ lead ready (signed pp ≠ slot name).
    assert quiet["vs_ready_delta_pp"] == -60
    assert quiet["vs_ready_delta_severity"] == "wide"
    assert quiet["vs_ready_lean_vs_delta"] == "align · wide"
    assert quiet["vs_ready_lean_vs_delta_warn"] is False
    assert quiet["vs_ready_delta_lead"] == "ready"
    # 80%÷20% → Δ lead size 4× (lead name ≠ magnitude).
    assert quiet["vs_ready_delta_lead_size"] == 4.0
    assert quiet["vs_ready_delta_lead_size_louder"] == 80.0
    assert quiet["vs_ready_delta_lead_size_quieter"] == 20.0
    assert quiet["lean"] == (
        "vs 4 ready · strong · 80% · lead ready · 80% · "
        "lead size · 4× · lead size sides · ready 4 · missing 1 · "
        "missing vs ready align · quiet|strong · "
        "Δ wide · -60pp · lean vs Δ align · wide · Δ lead · ready · "
        "Δ lead size · 4× · "
        "Δ lead size sides · ready 80% · missing 20%"
    )
    assert quiet["lean_warn"] is False
    assert quiet["lean_meta"] == (
        "vs ready · ownership · size · severity · Δ · lean/Δ · Δ lead · Δ size"
    )
    # Missing-heavy board → lead missing · size 3× · align hot|thin.
    # 75% − 25% = +50pp → wide Δ; adverse hot|thin + wide warns.
    heavy = leaderboard_missing_share(
        [
            {"account_id": "m0", "missing": True},
            {"account_id": "m1", "missing": True},
            {"account_id": "m2", "missing": True},
            {"account_id": "r0", "missing": False},
        ]
    )
    assert heavy["vs_ready_lead"] == "lead missing · 75%"
    assert heavy["vs_ready_lead_name"] == "missing"
    assert heavy["vs_ready_lead_size"] == 3.0
    assert heavy["vs_ready_lean"] == "missing vs ready align · hot|thin"
    assert heavy["vs_ready_delta_pp"] == 50
    assert heavy["vs_ready_delta_severity"] == "wide"
    assert heavy["vs_ready_lean_vs_delta"] == "align · wide"
    assert heavy["vs_ready_lean_vs_delta_warn"] is True
    assert heavy["vs_ready_delta_lead"] == "missing"
    assert heavy["vs_ready_delta_lead_size"] == 3.0
    assert heavy["vs_ready_delta_lead_size_louder"] == 75.0
    assert heavy["vs_ready_delta_lead_size_quieter"] == 25.0
    assert "lead missing · 75%" in heavy["lean"]
    assert "lead size · 3×" in heavy["lean"]
    assert "lead size sides · missing 3 · ready 1" in heavy["lean"]
    assert "missing vs ready align · hot|thin" in heavy["lean"]
    assert "Δ wide · +50pp" in heavy["lean"]
    assert "lean vs Δ align · wide" in heavy["lean"]
    assert "Δ lead · missing" in heavy["lean"]
    assert "Δ lead size · 3×" in heavy["lean"]
    assert "Δ lead size sides · missing 75% · ready 25%" in heavy["lean"]
    assert heavy["lean_warn"] is True
    assert heavy["lean_meta"] == (
        "vs ready · ownership · size · severity · Δ · lean/Δ · Δ lead · Δ size"
    )
    # Helpers: sole-side / tie / bad input / lead size / severity lean / Δ.
    assert leaderboard_missing_vs_ready_lead(2, 0) == ("", "", None)
    assert leaderboard_missing_vs_ready_lead(1, 1) == ("", "", None)
    assert leaderboard_missing_vs_ready_sample_gap(1, 1) == (
        "missing/ready tied"
    )
    assert leaderboard_missing_vs_ready_sample_gap(2, 1) == ""
    assert leaderboard_missing_vs_ready_lead_size(
        4, 1, lead_name="missing"
    ) == (4.0, 4, 1)
    assert leaderboard_missing_vs_ready_lead_size(
        1, 1, lead_name=""
    ) == (None, None, None)
    assert leaderboard_missing_vs_ready_lead_size(
        2, 0, lead_name="missing"
    ) == (None, None, None)
    assert leaderboard_missing_vs_ready_lean("hot", "thin") == (
        "missing vs ready align · hot|thin",
        False,
    )
    assert leaderboard_missing_vs_ready_lean("quiet", "strong") == (
        "missing vs ready align · quiet|strong",
        False,
    )
    assert leaderboard_missing_vs_ready_lean("hot", "strong") == (
        "missing vs ready clash · missing hot · ready strong",
        True,
    )
    assert leaderboard_missing_vs_ready_lean("hot", "ok") == (
        "missing vs ready clash · missing hot · ready ok",
        True,
    )
    assert leaderboard_missing_vs_ready_lean("ok", "ok") == ("", False)
    assert leaderboard_missing_vs_ready_delta(
        75, 25, lean_bit="missing vs ready align · hot|thin"
    ) == (50, "wide", "align · wide", True)
    assert leaderboard_missing_vs_ready_delta(
        20, 80, lean_bit="missing vs ready align · quiet|strong"
    ) == (-60, "wide", "align · wide", False)
    assert leaderboard_missing_vs_ready_delta(
        55, 45, lean_bit="missing vs ready clash · missing hot · ready ok"
    ) == (10, "", "clash · lean · Δ mid", True)
    assert leaderboard_missing_vs_ready_delta(50, 50, lean_bit="") == (
        None,
        "",
        "",
        False,
    )
    assert (
        leaderboard_missing_vs_ready_delta_lead(
            50, "wide", lean_vs_delta="align · wide"
        )
        == "missing"
    )
    assert (
        leaderboard_missing_vs_ready_delta_lead(
            -60, "wide", lean_vs_delta="align · wide"
        )
        == "ready"
    )
    assert (
        leaderboard_missing_vs_ready_delta_lead(
            0, "thin", lean_vs_delta="align · thin"
        )
        == ""
    )
    assert (
        leaderboard_missing_vs_ready_delta_lead(
            10, "", lean_vs_delta="clash · lean · Δ mid"
        )
        == ""
    )
    assert leaderboard_missing_vs_ready_delta_lead_size(
        75, 25, delta_lead="missing"
    ) == (3.0, 75.0, 25.0)
    assert leaderboard_missing_vs_ready_delta_lead_size(
        20, 80, delta_lead="ready"
    ) == (4.0, 80.0, 20.0)
    assert leaderboard_missing_vs_ready_delta_lead_size(
        100, 0, delta_lead="missing"
    ) == (None, None, None)
    assert leaderboard_missing_vs_ready_delta_lead_size(
        50, 50, delta_lead=""
    ) == (None, None, None)
    # Legacy-only board silent.
    legacy_only = leaderboard_missing_share([rows[1]])
    assert legacy_only["bit"] == ""
    assert legacy_only["lean"] == ""
