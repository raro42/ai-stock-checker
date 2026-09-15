"""Offline tests for daily loss halt + concentration cap."""

from pathlib import Path

from stock_checker.risk_halts import (
    concentration_allows,
    daily_loss_halt,
    realized_pnl_for_utc_day,
    utc_day_key,
)


def test_realized_pnl_sums_sells_for_day(tmp_path: Path) -> None:
    day = "2026-08-28"
    (tmp_path / "trades.jsonl").write_text(
        "\n".join(
            [
                '{"type":"SELL","timestamp":"2026-08-28 13:00:00","profit_loss":-400.0}',
                '{"type":"SELL","timestamp":"2026-08-28T15:00:00","profit_loss":-300.5}',
                '{"type":"BUY","timestamp":"2026-08-28 16:00:00","profit_loss":null}',
                '{"type":"SELL","timestamp":"2026-08-27 12:00:00","profit_loss":-999.0}',
            ]
        )
        + "\n"
    )
    assert realized_pnl_for_utc_day(tmp_path, day=day) == -700.5


def test_daily_loss_halt_triggers(tmp_path: Path) -> None:
    (tmp_path / "trades.jsonl").write_text(
        '{"type":"SELL","timestamp":"2026-08-28 10:00:00","profit_loss":-2100.0}\n'
    )
    block, why, pnl = daily_loss_halt(
        tmp_path, initial_cash=100_000.0, threshold_pct=2.0, day="2026-08-28"
    )
    assert block is True
    assert pnl == -2100.0
    assert "daily loss halt" in why


def test_daily_loss_halt_allows_small_loss(tmp_path: Path) -> None:
    (tmp_path / "trades.jsonl").write_text(
        '{"type":"SELL","timestamp":"2026-08-28 10:00:00","profit_loss":-500.0}\n'
    )
    block, why, pnl = daily_loss_halt(
        tmp_path, initial_cash=100_000.0, threshold_pct=2.0, day="2026-08-28"
    )
    assert block is False
    assert pnl == -500.0
    assert why == "ok"


def test_concentration_cap() -> None:
    ok, _ = concentration_allows(notional=20_000, portfolio_value=100_000, max_name_pct=30)
    assert ok is True
    bad, why = concentration_allows(
        notional=35_000, portfolio_value=100_000, max_name_pct=30
    )
    assert bad is False
    assert "concentration" in why


def test_utc_day_key_format() -> None:
    assert len(utc_day_key()) == 10


def test_pretrade_status_fail_on_daily_halt(tmp_path: Path) -> None:
    from stock_checker.risk_halts import pretrade_status, utc_day_key

    day = utc_day_key()
    (tmp_path / "trades.jsonl").write_text(
        f'{{"type":"SELL","timestamp":"{day} 10:00:00","profit_loss":-2500.0}}\n'
    )
    level, notes = pretrade_status(tmp_path, initial_cash=100_000.0)
    assert level == "FAIL"
    assert any("daily loss" in n for n in notes)


def test_pretrade_status_warn_on_cooldown(tmp_path: Path) -> None:
    from stock_checker.risk_halts import pretrade_status

    level, notes = pretrade_status(
        tmp_path, initial_cash=100_000.0, buy_block_until=9e18, now=1.0
    )
    assert level == "WARN"
    assert any("cooldown" in n for n in notes)


def test_suggest_entry_notional_cash_frac() -> None:
    from stock_checker.risk_halts import suggest_entry_notional

    out = suggest_entry_notional(
        cash=50_000, equity=100_000, open_positions=2, max_positions=5
    )
    assert out["eur"] == 5_000.0
    assert out["capped_by"] == "cash_frac"
    assert out["slots_open"] == 3


def test_suggest_entry_notional_concentration_cap() -> None:
    from stock_checker.risk_halts import suggest_entry_notional

    # 10% of cash = 20k, but 30% of equity = 9k → concentration wins
    out = suggest_entry_notional(
        cash=200_000, equity=30_000, open_positions=0, max_positions=5
    )
    assert out["eur"] == 9_000.0
    assert out["capped_by"] == "concentration"


def test_suggest_entry_notional_book_full() -> None:
    from stock_checker.risk_halts import suggest_entry_notional

    out = suggest_entry_notional(
        cash=50_000, equity=100_000, open_positions=5, max_positions=5
    )
    assert out["eur"] == 0.0
    assert out["capped_by"] == "book_full"
    assert out["slots_open"] == 0


def test_book_risk_report_mix_and_warn() -> None:
    from stock_checker.risk_halts import book_risk_report

    out = book_risk_report(
        cash=20_000,
        equity=100_000,
        max_positions=5,
        holdings=[
            {"symbol": "JPM", "market_value": 40_000, "kind": "stock"},
            {"symbol": "ETH-USD", "market_value": 25_000, "kind": "crypto"},
            {"symbol": "HALO", "market_value": 15_000, "kind": "stock"},
        ],
    )
    assert out["slots"] == "3/5"
    assert out["posture"] == "open"
    assert out["cash_pct"] == 20.0
    assert out["largest_symbol"] == "JPM"
    assert out["largest_pct"] == 40.0
    assert out["concentration_warn"] is True
    assert out["equity_pct"] == 68.8  # 55k / 80k
    assert out["crypto_pct"] == 31.2
    # Cost-only rows: missing marks are — not 0 (Group Matrix honesty)
    assert out["sleeve_marks_ready"] is True
    assert out["equity_mark_label"] == "—×2"
    assert out["crypto_mark_label"] == "—×1"
    assert "marks eq —×2 / cr —×1" in out["note"]


def test_book_risk_report_sleeve_marks_weighted() -> None:
    from stock_checker.risk_halts import book_risk_report, sleeve_mark_returns

    holds = [
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 10_000,
            "market_value": 11_000,
            "unrealized_pct": 10.0,
            "marked": True,
        },
        {
            "symbol": "MSFT",
            "kind": "stock",
            "cost_basis": 30_000,
            "market_value": 27_000,
            "unrealized_pct": -10.0,
            "marked": True,
        },
        {
            "symbol": "ETH-USD",
            "kind": "crypto",
            "cost_basis": 5_000,
            "market_value": 5_000,
            "unrealized_pct": 0.0,
            "marked": False,  # cost flat — not a real mark
        },
    ]
    marks = sleeve_mark_returns(holds)
    # (10k*10 + 30k*-10) / 40k = -5.0
    assert marks["equity_mark_pct"] == -5.0
    assert marks["equity_mark_label"] == "−5.0%×2"
    assert marks["crypto_mark_label"] == "—×1"
    assert marks["crypto_mark_pct"] is None
    assert marks["equity_marked"] == 2
    assert "marks eq −5.0%×2 / cr —×1" in marks["sleeve_marks_bit"]

    out = book_risk_report(
        cash=10_000, equity=53_000, holdings=holds, max_positions=5
    )
    assert out["equity_mark_pct"] == -5.0
    assert "marks eq −5.0%×2 / cr —×1" in out["note"]
    # No hold ages → tenure strip empty (not in glance note)
    assert out["tenure_marks_ready"] is False
    assert out["tenure_marks_bit"] == ""
    assert out["tenure_unknown_lots"] == 3


def test_tenure_mark_returns_week_month_buckets() -> None:
    from stock_checker.risk_halts import (
        TENURE_MONTH_SEC,
        TENURE_WEEK_SEC,
        book_risk_report,
        tenure_mark_returns,
    )

    holds = [
        {
            "symbol": "NEW",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 4.0,
            "marked": True,
            "held_seconds": TENURE_WEEK_SEC - 1,
        },
        {
            "symbol": "MID",
            "kind": "stock",
            "cost_basis": 20_000,
            "unrealized_pct": -2.0,
            "marked": True,
            "held_seconds": TENURE_WEEK_SEC + 100,
        },
        {
            "symbol": "OLD",
            "kind": "crypto",
            "cost_basis": 5_000,
            "unrealized_pct": 8.0,
            "marked": True,
            "held_seconds": TENURE_MONTH_SEC + 1,
        },
        {
            "symbol": "NOAGE",
            "kind": "stock",
            "cost_basis": 1_000,
            "unrealized_pct": 50.0,
            "marked": True,
            # missing held_seconds
        },
        {
            "symbol": "FLAT",
            "kind": "stock",
            "cost_basis": 2_000,
            "held_seconds": TENURE_WEEK_SEC - 10,
            "marked": False,
        },
    ]
    tenure = tenure_mark_returns(holds)
    assert tenure["tenure_lt_7d_pct"] == 4.0
    assert tenure["tenure_lt_7d_label"] == "+4.0%×1"
    assert tenure["tenure_7_30d_pct"] == -2.0
    assert tenure["tenure_ge_30d_pct"] == 8.0
    assert tenure["tenure_unknown_lots"] == 1
    # FLAT has age but unmarked — does not dilute NEW's marked %
    assert "tenure <7d +4.0%×1 · 7–30d −2.0%×1 · ≥30d +8.0%×1" in tenure["tenure_marks_bit"]

    out = book_risk_report(cash=5_000, equity=43_000, holdings=holds, max_positions=5)
    assert out["tenure_marks_ready"] is True
    assert out["tenure_lt_7d_pct"] == 4.0
    # Tenure stays off the glance note (Book strip only)
    assert "tenure" not in out["note"]


def test_polarity_mark_returns_win_lose() -> None:
    from stock_checker.risk_halts import book_risk_report, polarity_mark_returns

    holds = [
        {
            "symbol": "WIN1",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 10.0,
            "marked": True,
        },
        {
            "symbol": "WIN2",
            "kind": "stock",
            "cost_basis": 30_000,
            "unrealized_pct": 5.0,
            "marked": True,
        },
        {
            "symbol": "LOSE",
            "kind": "crypto",
            "cost_basis": 20_000,
            "unrealized_pct": -8.0,
            "marked": True,
        },
        {
            "symbol": "FLAT",
            "kind": "stock",
            "cost_basis": 5_000,
            "unrealized_pct": 0.0,
            "marked": True,
        },
        {
            "symbol": "DARK",
            "kind": "stock",
            "cost_basis": 4_000,
            "marked": False,
        },
    ]
    pol = polarity_mark_returns(holds)
    # win: (10k*10 + 30k*5) / 40k = 6.25
    assert pol["polarity_win_pct"] == 6.25
    assert pol["polarity_win_label"] == "+6.2%×2"
    assert pol["polarity_lose_pct"] == -8.0
    assert pol["polarity_lose_label"] == "−8.0%×1"
    assert pol["polarity_win_lots"] == 2
    assert pol["polarity_lose_lots"] == 1
    assert pol["polarity_flat_lots"] == 1
    assert pol["polarity_unmarked_lots"] == 1
    assert "polarity win +6.2%×2 · lose −8.0%×1" in pol["polarity_marks_bit"]

    out = book_risk_report(cash=10_000, equity=70_000, holdings=holds, max_positions=5)
    assert out["polarity_marks_ready"] is True
    assert out["polarity_win_pct"] == 6.25
    # Polarity stays off the glance note (Book strip only)
    assert "polarity" not in out["note"]
    assert "win +" not in out["note"]


def test_size_mark_returns_median_split() -> None:
    from stock_checker.risk_halts import book_risk_report, size_mark_returns

    holds = [
        {
            "symbol": "SM",
            "kind": "stock",
            "cost_basis": 5_000,
            "unrealized_pct": 10.0,
            "marked": True,
        },
        {
            "symbol": "LG1",
            "kind": "stock",
            "cost_basis": 20_000,
            "unrealized_pct": -4.0,
            "marked": True,
        },
        {
            "symbol": "LG2",
            "kind": "crypto",
            "cost_basis": 30_000,
            "unrealized_pct": 2.0,
            "marked": True,
        },
        {
            "symbol": "DARK",
            "kind": "stock",
            "cost_basis": 1_000,
            "marked": False,
        },
    ]
    size = size_mark_returns(holds)
    # Sorted costs: 1k DARK, 5k SM | 20k LG1, 30k LG2 (mid=2)
    # small: DARK unmarked + SM marked → only SM in weight → +10%
    assert size["size_small_pct"] == 10.0
    assert size["size_small_label"] == "+10.0%×1"
    assert size["size_small_lots"] == 2
    # large: (20k*-4 + 30k*2) / 50k = -0.4
    assert size["size_large_pct"] == -0.4
    assert size["size_large_label"] == "−0.4%×2"
    assert size["size_large_lots"] == 2
    assert "size lg −0.4%×2 · sm +10.0%×1" in size["size_marks_bit"]

    alone = size_mark_returns(
        [
            {
                "symbol": "ONLY",
                "cost_basis": 10_000,
                "unrealized_pct": 5.0,
                "marked": True,
            }
        ]
    )
    assert alone["size_marks_ready"] is False
    assert alone["size_marks_bit"] == ""

    out = book_risk_report(cash=10_000, equity=66_000, holdings=holds, max_positions=5)
    assert out["size_marks_ready"] is True
    assert out["size_large_pct"] == -0.4
    # Size stays off the glance note (Book strip only)
    assert "size " not in out["note"]


def test_leader_mark_returns_top_vs_rest() -> None:
    from stock_checker.risk_halts import book_risk_report, leader_mark_returns

    holds = [
        {
            "symbol": "big",
            "kind": "stock",
            "cost_basis": 40_000,
            "unrealized_pct": -5.0,
            "marked": True,
        },
        {
            "symbol": "A",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 10.0,
            "marked": True,
        },
        {
            "symbol": "B",
            "kind": "crypto",
            "cost_basis": 20_000,
            "unrealized_pct": 4.0,
            "marked": True,
        },
        {
            "symbol": "DARK",
            "kind": "stock",
            "cost_basis": 5_000,
            "marked": False,
        },
    ]
    leader = leader_mark_returns(holds)
    assert leader["leader_symbol"] == "BIG"
    assert leader["leader_mark_pct"] == -5.0
    assert leader["leader_mark_label"] == "−5.0%×1"
    # rest: (10k*10 + 20k*4) / 30k = 6.0 — DARK unmarked does not dilute
    assert leader["leader_rest_pct"] == 6.0
    assert leader["leader_rest_label"] == "+6.0%×2"
    assert leader["leader_lots"] == 1
    assert leader["leader_rest_lots"] == 3
    assert leader["leader_cost_share"] == round(40_000 / 75_000 * 100.0, 1)
    assert "leader top BIG −5.0%×1 · rest +6.0%×2" in leader["leader_marks_bit"]

    alone = leader_mark_returns(
        [
            {
                "symbol": "ONLY",
                "cost_basis": 10_000,
                "unrealized_pct": 5.0,
                "marked": True,
            }
        ]
    )
    assert alone["leader_marks_ready"] is False
    assert alone["leader_marks_bit"] == ""

    out = book_risk_report(cash=5_000, equity=80_000, holdings=holds, max_positions=5)
    assert out["leader_marks_ready"] is True
    assert out["leader_symbol"] == "BIG"
    assert out["leader_mark_pct"] == -5.0
    # Leader stays off the glance note (Book strip only)
    assert "leader " not in out["note"]


def test_book_risk_report_empty_book() -> None:
    from stock_checker.risk_halts import book_risk_report

    out = book_risk_report(cash=100_000, equity=100_000, holdings=[], max_positions=5)
    assert out["slots"] == "0/5"
    assert out["posture"] == "open"
    assert out["largest_symbol"] == ""
    assert out["concentration_warn"] is False
    assert out["cash_pct"] == 100.0
    assert out["sleeve_marks_ready"] is False
    assert out["sleeve_marks_bit"] == ""
    assert out["tenure_marks_ready"] is False
    assert out["tenure_marks_bit"] == ""
    assert out["polarity_marks_ready"] is False
    assert out["polarity_marks_bit"] == ""
    assert out["size_marks_ready"] is False
    assert out["size_marks_bit"] == ""
    assert out["leader_marks_ready"] is False
    assert out["leader_marks_bit"] == ""


def test_book_risk_report_overweight() -> None:
    from stock_checker.risk_halts import book_risk_report

    holds = [
        {"symbol": f"S{i}", "market_value": 10_000, "kind": "stock"} for i in range(6)
    ]
    out = book_risk_report(
        cash=40_000, equity=100_000, holdings=holds, max_positions=5
    )
    assert out["posture"] == "overweight"
    assert out["slots"] == "6/5"
