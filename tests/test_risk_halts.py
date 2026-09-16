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


def test_venue_mark_returns_us_xetra_crypto() -> None:
    from stock_checker.risk_halts import book_risk_report, venue_mark_returns

    holds = [
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 10.0,
            "marked": True,
        },
        {
            "symbol": "SAP.DE",
            "kind": "stock",
            "cost_basis": 20_000,
            "unrealized_pct": -5.0,
            "marked": True,
        },
        {
            "symbol": "BTC-USD",
            "kind": "crypto",
            "cost_basis": 5_000,
            "unrealized_pct": 8.0,
            "marked": True,
        },
        {
            "symbol": "SIE.DE",
            "kind": "stock",
            "cost_basis": 8_000,
            "marked": False,
        },
    ]
    venue = venue_mark_returns(holds)
    assert venue["venue_us_pct"] == 10.0
    assert venue["venue_us_label"] == "+10.0%×1"
    assert venue["venue_xetra_pct"] == -5.0
    assert venue["venue_xetra_label"] == "−5.0%×1"
    assert venue["venue_xetra_lots"] == 2
    assert venue["venue_crypto_pct"] == 8.0
    assert venue["venue_crypto_label"] == "+8.0%×1"
    assert venue["venue_marks_ready"] is True
    assert "venue us +10.0%×1 · de −5.0%×1 · cr +8.0%×1" in venue["venue_marks_bit"]

    out = book_risk_report(cash=5_000, equity=80_000, holdings=holds, max_positions=5)
    assert out["venue_marks_ready"] is True
    assert out["venue_xetra_label"] == "−5.0%×1"
    # Venue stays off the glance note (Book strip only)
    assert "venue " not in out["note"]


def test_exit_band_mark_returns_tp_mid_sl() -> None:
    from stock_checker.risk_halts import book_risk_report, exit_band_mark_returns

    holds = [
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 7.0,  # ≥75% of +8% → near TP
            "marked": True,
        },
        {
            "symbol": "MSFT",
            "kind": "stock",
            "cost_basis": 20_000,
            "unrealized_pct": 2.0,  # mid
            "marked": True,
        },
        {
            "symbol": "SAP.DE",
            "kind": "stock",
            "cost_basis": 5_000,
            "unrealized_pct": -4.0,  # ≤−75% of −5% → near SL
            "marked": True,
        },
        {
            "symbol": "BTC-USD",
            "kind": "crypto",
            "cost_basis": 8_000,
            "unrealized_pct": 8.0,  # ≥75% of +10% → near TP
            "marked": True,
        },
        {
            "symbol": "ETH-USD",
            "kind": "crypto",
            "cost_basis": 4_000,
            "marked": False,
        },
    ]
    band = exit_band_mark_returns(holds)
    # TP: AAPL 10k@7 + BTC 8k@8 → (70k+64k)/18k = 7.444… → 7.44
    assert band["exit_band_tp_pct"] == 7.44
    assert band["exit_band_tp_label"] == "+7.4%×2"
    assert band["exit_band_tp_lots"] == 2
    assert band["exit_band_mid_pct"] == 2.0
    assert band["exit_band_mid_label"] == "+2.0%×1"
    assert band["exit_band_sl_pct"] == -4.0
    assert band["exit_band_sl_label"] == "−4.0%×1"
    assert band["exit_band_unmarked_lots"] == 1
    assert band["exit_band_marks_ready"] is True
    assert "exit tp +7.4%×2 · mid +2.0%×1 · sl −4.0%×1" in band["exit_band_marks_bit"]

    out = book_risk_report(cash=5_000, equity=80_000, holdings=holds, max_positions=5)
    assert out["exit_band_marks_ready"] is True
    assert out["exit_band_tp_label"] == "+7.4%×2"
    # Exit band stays off the glance note (Book strip only)
    assert "exit " not in out["note"]


def test_entry_session_mark_returns_weekday_vs_weekend() -> None:
    from stock_checker.risk_halts import (
        book_risk_report,
        entry_session_mark_returns,
    )

    holds = [
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 3.0,
            "marked": True,
            "bought_at": "2026-09-15T14:00:00Z",
        },
        {
            "symbol": "MSFT",
            "kind": "stock",
            "cost_basis": 5_000,
            "unrealized_pct": -1.0,
            "marked": True,
            "bought_at": "2026-09-16T10:00:00Z",
        },
        {
            "symbol": "BTC-USD",
            "kind": "crypto",
            "cost_basis": 8_000,
            "unrealized_pct": 5.0,
            "marked": True,
            "bought_at": "2026-09-13T18:00:00Z",
        },
        {
            "symbol": "ETH-USD",
            "kind": "crypto",
            "cost_basis": 2_000,
            "marked": False,
            "bought_at": "2026-09-12T12:00:00Z",
        },
        {
            "symbol": "SAP.DE",
            "kind": "stock",
            "cost_basis": 4_000,
            "unrealized_pct": 2.0,
            "marked": True,
        },
    ]
    sm = entry_session_mark_returns(holds)
    assert sm["entry_session_wd_pct"] == 1.67
    assert sm["entry_session_wd_label"] == "+1.7%×2"
    assert sm["entry_session_wd_lots"] == 2
    assert sm["entry_session_we_pct"] == 5.0
    assert sm["entry_session_we_label"] == "+5.0%×1"
    assert sm["entry_session_we_lots"] == 2
    assert sm["entry_session_unknown_lots"] == 1
    assert sm["entry_session_marks_ready"] is True
    assert "wd +1.7%×2" in sm["entry_session_marks_bit"]
    assert "we +5.0%×1" in sm["entry_session_marks_bit"]

    empty = entry_session_mark_returns([])
    assert empty["entry_session_marks_ready"] is False
    assert empty["entry_session_marks_bit"] == ""

    out = book_risk_report(
        cash=1_000,
        equity=30_000,
        holdings=holds,
        max_positions=5,
    )
    assert out["entry_session_marks_ready"] is True
    assert out["entry_session_wd_pct"] == 1.67


def test_entry_hours_mark_returns_open_closed_crypto() -> None:
    from stock_checker.risk_halts import (
        book_risk_report,
        entry_hours_mark_returns,
    )

    # Tue 2026-09-15 14:00Z = 10:00 ET → US RTH open
    # Tue 2026-09-15 22:00Z = 18:00 ET → US closed (AH)
    # Sat 2026-09-12 → weekend equity closed
    # Crypto always cr (24/7)
    holds = [
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 4.0,
            "marked": True,
            "bought_at": "2026-09-15T14:00:00Z",
        },
        {
            "symbol": "MSFT",
            "kind": "stock",
            "cost_basis": 5_000,
            "unrealized_pct": -2.0,
            "marked": True,
            "bought_at": "2026-09-15T22:00:00Z",
        },
        {
            "symbol": "SAP.DE",
            "kind": "stock",
            "cost_basis": 5_000,
            "unrealized_pct": 1.0,
            "marked": True,
            "bought_at": "2026-09-12T12:00:00Z",
        },
        {
            "symbol": "BTC-USD",
            "kind": "crypto",
            "cost_basis": 8_000,
            "unrealized_pct": 6.0,
            "marked": True,
            "bought_at": "2026-09-13T03:00:00Z",
        },
        {
            "symbol": "NVDA",
            "kind": "stock",
            "cost_basis": 3_000,
            "unrealized_pct": 2.0,
            "marked": True,
        },
    ]
    hm = entry_hours_mark_returns(holds)
    assert hm["entry_hours_open_pct"] == 4.0
    assert hm["entry_hours_open_label"] == "+4.0%×1"
    assert hm["entry_hours_open_lots"] == 1
    assert hm["entry_hours_closed_pct"] == -0.5
    assert hm["entry_hours_closed_label"] == "−0.5%×2"
    assert hm["entry_hours_closed_lots"] == 2
    assert hm["entry_hours_cr_pct"] == 6.0
    assert hm["entry_hours_cr_label"] == "+6.0%×1"
    assert hm["entry_hours_cr_lots"] == 1
    assert hm["entry_hours_unknown_lots"] == 1
    assert hm["entry_hours_marks_ready"] is True
    assert "open +4.0%×1" in hm["entry_hours_marks_bit"]
    assert "closed −0.5%×2" in hm["entry_hours_marks_bit"]
    assert "cr +6.0%×1" in hm["entry_hours_marks_bit"]

    empty = entry_hours_mark_returns([])
    assert empty["entry_hours_marks_ready"] is False
    assert empty["entry_hours_marks_bit"] == ""

    out = book_risk_report(
        cash=1_000,
        equity=32_000,
        holdings=holds,
        max_positions=5,
    )
    assert out["entry_hours_marks_ready"] is True
    assert out["entry_hours_open_pct"] == 4.0


def test_min_hold_mark_returns_lock_vs_free() -> None:
    from stock_checker.risk_halts import book_risk_report, min_hold_mark_returns

    day = 24 * 3600
    holds = [
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 3.0,
            "marked": True,
            "held_seconds": day * 2,
            "past_min_hold": True,
        },
        {
            "symbol": "MSFT",
            "kind": "stock",
            "cost_basis": 20_000,
            "unrealized_pct": -1.0,
            "marked": True,
            "held_seconds": day * 0.5,
            "past_min_hold": False,
        },
        {
            "symbol": "SAP.DE",
            "kind": "stock",
            "cost_basis": 5_000,
            "unrealized_pct": 1.0,
            "marked": True,
            "held_seconds": day * 0.25,
            "past_min_hold": False,
        },
        {
            "symbol": "BTC-USD",
            "kind": "crypto",
            "cost_basis": 8_000,
            "unrealized_pct": 4.0,
            "marked": True,
            # Missing age → unknown (A7), not lock
        },
        {
            "symbol": "ETH-USD",
            "kind": "crypto",
            "cost_basis": 4_000,
            "held_seconds": day * 3,
            "past_min_hold": True,
            "marked": False,
        },
    ]
    mh = min_hold_mark_returns(holds, min_hold_seconds=day)
    # lock: MSFT 20k@−1 + SAP 5k@1 → (−20k+5k)/25k = −0.6
    assert mh["min_hold_lock_pct"] == -0.6
    assert mh["min_hold_lock_label"] == "−0.6%×2"
    assert mh["min_hold_lock_lots"] == 2
    assert mh["min_hold_free_pct"] == 3.0
    assert mh["min_hold_free_label"] == "+3.0%×1"
    assert mh["min_hold_free_lots"] == 2  # AAPL marked + ETH unmarked lot
    assert mh["min_hold_unknown_lots"] == 1
    assert mh["min_hold_marks_ready"] is True
    assert "hold lock −0.6%×2 · free +3.0%×1" in mh["min_hold_marks_bit"]

    # Without past_min_hold flags, fall back to min_hold_seconds vs held
    computed = min_hold_mark_returns(
        [
            {
                "symbol": "AAPL",
                "cost_basis": 10_000,
                "unrealized_pct": 2.0,
                "marked": True,
                "held_seconds": day * 2,
            },
            {
                "symbol": "MSFT",
                "cost_basis": 10_000,
                "unrealized_pct": -2.0,
                "marked": True,
                "held_seconds": day * 0.5,
            },
        ],
        min_hold_seconds=day,
    )
    assert computed["min_hold_free_pct"] == 2.0
    assert computed["min_hold_lock_pct"] == -2.0

    out = book_risk_report(
        cash=5_000,
        equity=80_000,
        holdings=holds,
        max_positions=5,
        min_hold_seconds=day,
    )
    assert out["min_hold_marks_ready"] is True
    assert out["min_hold_lock_label"] == "−0.6%×2"
    # Min-hold marks stay off the glance note (Book strip only)
    assert "hold " not in out["note"]


def test_scan_mark_returns_on_vs_off() -> None:
    from stock_checker.risk_halts import book_risk_report, scan_mark_returns

    holds = [
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 4.0,
            "marked": True,
        },
        {
            "symbol": "MSFT",
            "kind": "stock",
            "cost_basis": 20_000,
            "unrealized_pct": -2.0,
            "marked": True,
        },
        {
            "symbol": "SAP.DE",
            "kind": "stock",
            "cost_basis": 5_000,
            "unrealized_pct": 1.0,
            "marked": True,
        },
        {
            "symbol": "BTC-USD",
            "kind": "crypto",
            "cost_basis": 8_000,
            "unrealized_pct": 6.0,
            "marked": True,
        },
        {
            "symbol": "ETH-USD",
            "kind": "crypto",
            "cost_basis": 4_000,
            "marked": False,
        },
    ]
    scan = {"AAPL", "BTC-USD", "NVDA"}
    sm = scan_mark_returns(holds, scan)
    # on: AAPL 10k@4 + BTC 8k@6 → (40k+48k)/18k = 4.888… → 4.89
    assert sm["scan_on_pct"] == 4.89
    assert sm["scan_on_label"] == "+4.9%×2"
    assert sm["scan_on_lots"] == 2
    # off: MSFT 20k@−2 + SAP 5k@1 → (−40k+5k)/25k = −1.4; ETH unmarked lot
    assert sm["scan_off_pct"] == -1.4
    assert sm["scan_off_label"] == "−1.4%×2"
    assert sm["scan_off_lots"] == 3
    assert sm["scan_marks_ready"] is True
    assert "scan on +4.9%×2 · off −1.4%×2" in sm["scan_marks_bit"]

    empty = scan_mark_returns(holds, None)
    assert empty["scan_marks_ready"] is False
    assert empty["scan_marks_bit"] == ""
    assert empty["scan_on_lots"] == 0

    out = book_risk_report(
        cash=5_000,
        equity=80_000,
        holdings=holds,
        max_positions=5,
        scan_symbols=scan,
    )
    assert out["scan_marks_ready"] is True
    assert out["scan_on_label"] == "+4.9%×2"
    assert out["scan_off_label"] == "−1.4%×2"
    # Scan marks stay off the glance note (Book strip only)
    assert "scan " not in out["note"]


def test_scan_list_mark_returns_lead_brk_rec_off() -> None:
    from stock_checker.risk_halts import book_risk_report, scan_list_mark_returns

    holds = [
        {
            "symbol": "BTC-USD",
            "kind": "crypto",
            "cost_basis": 10_000,
            "unrealized_pct": 5.0,
            "marked": True,
        },
        {
            "symbol": "NVDA",
            "kind": "stock",
            "cost_basis": 20_000,
            "unrealized_pct": 2.0,
            "marked": True,
        },
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 8_000,
            "unrealized_pct": -1.0,
            "marked": True,
        },
        {
            "symbol": "MSFT",
            "kind": "stock",
            "cost_basis": 12_000,
            "unrealized_pct": 3.0,
            "marked": True,
        },
        {
            "symbol": "ETH-USD",
            "kind": "crypto",
            "cost_basis": 4_000,
            "marked": False,
        },
    ]
    # NVDA in both breakouts + recs → brk wins; BTC also in recs → lead wins
    lm = scan_list_mark_returns(
        holds,
        leaders=["BTC-USD"],
        breakouts=["NVDA"],
        recommendations=["NVDA", "AAPL", "BTC-USD"],
    )
    assert lm["scan_list_lead_pct"] == 5.0
    assert lm["scan_list_lead_label"] == "+5.0%×1"
    assert lm["scan_list_brk_pct"] == 2.0
    assert lm["scan_list_brk_label"] == "+2.0%×1"
    assert lm["scan_list_rec_pct"] == -1.0
    assert lm["scan_list_rec_label"] == "−1.0%×1"
    assert lm["scan_list_off_pct"] == 3.0
    assert lm["scan_list_off_label"] == "+3.0%×1"
    assert lm["scan_list_off_lots"] == 2  # MSFT marked + ETH unmarked
    assert lm["scan_list_marks_ready"] is True
    assert (
        "list lead +5.0%×1 · brk +2.0%×1 · rec −1.0%×1 · off +3.0%×1"
        in lm["scan_list_marks_bit"]
    )

    skipped = scan_list_mark_returns(holds)
    assert skipped["scan_list_marks_ready"] is False
    assert skipped["scan_list_marks_bit"] == ""

    out = book_risk_report(
        cash=5_000,
        equity=80_000,
        holdings=holds,
        max_positions=5,
        scan_leaders=["BTC-USD"],
        scan_breakouts=["NVDA"],
        scan_recommendations=["NVDA", "AAPL", "BTC-USD"],
    )
    assert out["scan_list_marks_ready"] is True
    assert out["scan_list_lead_label"] == "+5.0%×1"
    assert out["scan_list_brk_label"] == "+2.0%×1"
    # List marks stay off the glance note (Book strip only)
    assert "list " not in out["note"]


def test_scan_score_mark_returns_hi_mid_lo_off() -> None:
    from stock_checker.risk_halts import (
        SCAN_SCORE_HI,
        SCAN_SCORE_MID,
        book_risk_report,
        scan_score_mark_returns,
    )

    holds = [
        {
            "symbol": "NVDA",
            "kind": "stock",
            "cost_basis": 20_000,
            "unrealized_pct": 4.0,
            "marked": True,
        },
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 1.0,
            "marked": True,
        },
        {
            "symbol": "MSFT",
            "kind": "stock",
            "cost_basis": 8_000,
            "unrealized_pct": -2.0,
            "marked": True,
        },
        {
            "symbol": "BTC-USD",
            "kind": "crypto",
            "cost_basis": 5_000,
            "unrealized_pct": 6.0,
            "marked": True,
        },
        {
            "symbol": "ETH-USD",
            "kind": "crypto",
            "cost_basis": 4_000,
            "marked": False,
        },
    ]
    scores = {
        "NVDA": 55.0,
        "AAPL": 30.0,
        "MSFT": 10.0,
        # BTC absent → off; ETH unmarked off
    }
    sm = scan_score_mark_returns(holds, scores)
    assert sm["scan_score_hi_floor"] == SCAN_SCORE_HI
    assert sm["scan_score_mid_floor"] == SCAN_SCORE_MID
    assert sm["scan_score_hi_pct"] == 4.0
    assert sm["scan_score_hi_label"] == "+4.0%×1"
    assert sm["scan_score_mid_pct"] == 1.0
    assert sm["scan_score_mid_label"] == "+1.0%×1"
    assert sm["scan_score_lo_pct"] == -2.0
    assert sm["scan_score_lo_label"] == "−2.0%×1"
    assert sm["scan_score_off_pct"] == 6.0
    assert sm["scan_score_off_label"] == "+6.0%×1"
    assert sm["scan_score_off_lots"] == 2  # BTC marked + ETH unmarked
    assert sm["scan_score_marks_ready"] is True
    assert (
        "score hi +4.0%×1 · mid +1.0%×1 · lo −2.0%×1 · off +6.0%×1"
        in sm["scan_score_marks_bit"]
    )

    skipped = scan_score_mark_returns(holds, None)
    assert skipped["scan_score_marks_ready"] is False
    assert skipped["scan_score_marks_bit"] == ""

    empty_map = scan_score_mark_returns(holds, {})
    assert empty_map["scan_score_off_lots"] == 5
    assert empty_map["scan_score_marks_ready"] is True

    out = book_risk_report(
        cash=5_000,
        equity=80_000,
        holdings=holds,
        max_positions=5,
        scan_scores=scores,
    )
    assert out["scan_score_marks_ready"] is True
    assert out["scan_score_hi_label"] == "+4.0%×1"
    assert out["scan_score_mid_label"] == "+1.0%×1"
    # Score marks stay off the glance note (Book strip only)
    assert "score " not in out["note"]


def test_scan_near_high_mark_returns_near_mid_deep_off() -> None:
    from stock_checker.risk_halts import (
        SCAN_NEAR_HIGH_MID,
        SCAN_NEAR_HIGH_PCT,
        book_risk_report,
        scan_near_high_mark_returns,
    )

    holds = [
        {
            "symbol": "NVDA",
            "kind": "stock",
            "cost_basis": 20_000,
            "unrealized_pct": 4.0,
            "marked": True,
        },
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 1.0,
            "marked": True,
        },
        {
            "symbol": "MSFT",
            "kind": "stock",
            "cost_basis": 8_000,
            "unrealized_pct": -2.0,
            "marked": True,
        },
        {
            "symbol": "BTC-USD",
            "kind": "crypto",
            "cost_basis": 5_000,
            "unrealized_pct": 6.0,
            "marked": True,
        },
        {
            "symbol": "ETH-USD",
            "kind": "crypto",
            "cost_basis": 4_000,
            "marked": False,
        },
    ]
    highs = {
        "NVDA": -2.0,  # near (≥ −5)
        "AAPL": -12.0,  # mid
        "MSFT": -25.0,  # deep
        # BTC absent → off; ETH unmarked off
    }
    nh = scan_near_high_mark_returns(holds, highs)
    assert nh["scan_near_high_floor"] == SCAN_NEAR_HIGH_PCT
    assert nh["scan_near_high_mid_floor"] == SCAN_NEAR_HIGH_MID
    assert nh["scan_near_high_near_pct"] == 4.0
    assert nh["scan_near_high_near_label"] == "+4.0%×1"
    assert nh["scan_near_high_mid_pct"] == 1.0
    assert nh["scan_near_high_mid_label"] == "+1.0%×1"
    assert nh["scan_near_high_deep_pct"] == -2.0
    assert nh["scan_near_high_deep_label"] == "−2.0%×1"
    assert nh["scan_near_high_off_pct"] == 6.0
    assert nh["scan_near_high_off_label"] == "+6.0%×1"
    assert nh["scan_near_high_off_lots"] == 2
    assert nh["scan_near_high_marks_ready"] is True
    assert (
        "high near +4.0%×1 · mid +1.0%×1 · deep −2.0%×1 · off +6.0%×1"
        in nh["scan_near_high_marks_bit"]
    )

    skipped = scan_near_high_mark_returns(holds, None)
    assert skipped["scan_near_high_marks_ready"] is False
    assert skipped["scan_near_high_marks_bit"] == ""

    empty_map = scan_near_high_mark_returns(holds, {})
    assert empty_map["scan_near_high_off_lots"] == 5
    assert empty_map["scan_near_high_marks_ready"] is True

    out = book_risk_report(
        cash=5_000,
        equity=80_000,
        holdings=holds,
        max_positions=5,
        scan_pct_from_high=highs,
    )
    assert out["scan_near_high_marks_ready"] is True
    assert out["scan_near_high_near_label"] == "+4.0%×1"
    assert out["scan_near_high_mid_label"] == "+1.0%×1"
    assert "high " not in out["note"]


def test_scan_mover_mark_returns_hot_cold_quiet_off() -> None:
    from stock_checker.risk_halts import (
        SCAN_MOVER_PCT,
        book_risk_report,
        scan_mover_mark_returns,
    )

    holds = [
        {
            "symbol": "NVDA",
            "kind": "stock",
            "cost_basis": 20_000,
            "unrealized_pct": 4.0,
            "marked": True,
        },
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 1.0,
            "marked": True,
        },
        {
            "symbol": "MSFT",
            "kind": "stock",
            "cost_basis": 8_000,
            "unrealized_pct": -2.0,
            "marked": True,
        },
        {
            "symbol": "BTC-USD",
            "kind": "crypto",
            "cost_basis": 5_000,
            "unrealized_pct": 6.0,
            "marked": True,
        },
        {
            "symbol": "ETH-USD",
            "kind": "crypto",
            "cost_basis": 4_000,
            "marked": False,
        },
    ]
    changes = {
        "NVDA": 5.5,  # hot (≥ +4)
        "AAPL": -6.0,  # cold
        "MSFT": 1.2,  # quiet
        # BTC absent → off; ETH unmarked off
    }
    mv = scan_mover_mark_returns(holds, changes)
    assert mv["scan_mover_floor"] == SCAN_MOVER_PCT
    assert mv["scan_mover_hot_pct"] == 4.0
    assert mv["scan_mover_hot_label"] == "+4.0%×1"
    assert mv["scan_mover_cold_pct"] == 1.0
    assert mv["scan_mover_cold_label"] == "+1.0%×1"
    assert mv["scan_mover_quiet_pct"] == -2.0
    assert mv["scan_mover_quiet_label"] == "−2.0%×1"
    assert mv["scan_mover_off_pct"] == 6.0
    assert mv["scan_mover_off_label"] == "+6.0%×1"
    assert mv["scan_mover_off_lots"] == 2
    assert mv["scan_mover_marks_ready"] is True
    assert (
        "move hot +4.0%×1 · cold +1.0%×1 · quiet −2.0%×1 · off +6.0%×1"
        in mv["scan_mover_marks_bit"]
    )

    skipped = scan_mover_mark_returns(holds, None)
    assert skipped["scan_mover_marks_ready"] is False
    assert skipped["scan_mover_marks_bit"] == ""

    empty_map = scan_mover_mark_returns(holds, {})
    assert empty_map["scan_mover_off_lots"] == 5
    assert empty_map["scan_mover_marks_ready"] is True

    out = book_risk_report(
        cash=5_000,
        equity=80_000,
        holdings=holds,
        max_positions=5,
        scan_change_24h=changes,
    )
    assert out["scan_mover_marks_ready"] is True
    assert out["scan_mover_hot_label"] == "+4.0%×1"
    assert out["scan_mover_cold_label"] == "+1.0%×1"
    assert "move " not in out["note"]


def test_ai_debate_mark_returns_buy_hold_sell_none() -> None:
    from stock_checker.risk_halts import ai_debate_mark_returns, book_risk_report

    holds = [
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 4.0,
            "marked": True,
        },
        {
            "symbol": "MSFT",
            "kind": "stock",
            "cost_basis": 20_000,
            "unrealized_pct": -2.0,
            "marked": True,
        },
        {
            "symbol": "SAP.DE",
            "kind": "stock",
            "cost_basis": 5_000,
            "unrealized_pct": 1.0,
            "marked": True,
        },
        {
            "symbol": "BTC-USD",
            "kind": "crypto",
            "cost_basis": 8_000,
            "unrealized_pct": 6.0,
            "marked": True,
        },
        {
            "symbol": "ETH-USD",
            "kind": "crypto",
            "cost_basis": 4_000,
            "marked": False,
        },
    ]
    actions = {"AAPL": "BUY", "MSFT": "HOLD", "BTC-USD": "SELL"}
    am = ai_debate_mark_returns(holds, actions)
    assert am["ai_debate_buy_pct"] == 4.0
    assert am["ai_debate_buy_label"] == "+4.0%×1"
    assert am["ai_debate_hold_pct"] == -2.0
    assert am["ai_debate_hold_label"] == "−2.0%×1"
    assert am["ai_debate_sell_pct"] == 6.0
    assert am["ai_debate_sell_label"] == "+6.0%×1"
    # none: SAP 5k@1 marked + ETH unmarked lot
    assert am["ai_debate_none_pct"] == 1.0
    assert am["ai_debate_none_label"] == "+1.0%×1"
    assert am["ai_debate_none_lots"] == 2
    assert am["ai_debate_marks_ready"] is True
    assert "ai buy +4.0%×1 · hold −2.0%×1 · sell +6.0%×1 · none +1.0%×1" in am[
        "ai_debate_marks_bit"
    ]

    skipped = ai_debate_mark_returns(holds, None)
    assert skipped["ai_debate_marks_ready"] is False
    assert skipped["ai_debate_marks_bit"] == ""

    empty_map = ai_debate_mark_returns(holds, {})
    assert empty_map["ai_debate_marks_ready"] is True
    assert empty_map["ai_debate_none_lots"] == 5
    assert empty_map["ai_debate_buy_lots"] == 0

    out = book_risk_report(
        cash=5_000,
        equity=80_000,
        holdings=holds,
        max_positions=5,
        ai_actions=actions,
    )
    assert out["ai_debate_marks_ready"] is True
    assert out["ai_debate_buy_label"] == "+4.0%×1"
    assert out["ai_debate_sell_label"] == "+6.0%×1"
    # AI debate marks stay off the glance note (Book strip only)
    assert "ai " not in out["note"]


def test_ai_confidence_mark_returns_hi_med_lo_none() -> None:
    from stock_checker.risk_halts import ai_confidence_mark_returns, book_risk_report

    holds = [
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 4.0,
            "marked": True,
        },
        {
            "symbol": "MSFT",
            "kind": "stock",
            "cost_basis": 20_000,
            "unrealized_pct": -2.0,
            "marked": True,
        },
        {
            "symbol": "SAP.DE",
            "kind": "stock",
            "cost_basis": 5_000,
            "unrealized_pct": 1.0,
            "marked": True,
        },
        {
            "symbol": "BTC-USD",
            "kind": "crypto",
            "cost_basis": 8_000,
            "unrealized_pct": 6.0,
            "marked": True,
        },
        {
            "symbol": "ETH-USD",
            "kind": "crypto",
            "cost_basis": 4_000,
            "marked": False,
        },
    ]
    confs = {"AAPL": "HIGH", "MSFT": "MEDIUM", "BTC-USD": "LOW"}
    cm = ai_confidence_mark_returns(holds, confs)
    assert cm["ai_conf_high_pct"] == 4.0
    assert cm["ai_conf_high_label"] == "+4.0%×1"
    assert cm["ai_conf_med_pct"] == -2.0
    assert cm["ai_conf_med_label"] == "−2.0%×1"
    assert cm["ai_conf_low_pct"] == 6.0
    assert cm["ai_conf_low_label"] == "+6.0%×1"
    assert cm["ai_conf_none_pct"] == 1.0
    assert cm["ai_conf_none_label"] == "+1.0%×1"
    assert cm["ai_conf_none_lots"] == 2
    assert cm["ai_conf_marks_ready"] is True
    assert "conf hi +4.0%×1 · med −2.0%×1 · lo +6.0%×1 · none +1.0%×1" in cm[
        "ai_conf_marks_bit"
    ]

    skipped = ai_confidence_mark_returns(holds, None)
    assert skipped["ai_conf_marks_ready"] is False
    assert skipped["ai_conf_marks_bit"] == ""

    empty_map = ai_confidence_mark_returns(holds, {})
    assert empty_map["ai_conf_marks_ready"] is True
    assert empty_map["ai_conf_none_lots"] == 5
    assert empty_map["ai_conf_high_lots"] == 0

    out = book_risk_report(
        cash=5_000,
        equity=80_000,
        holdings=holds,
        max_positions=5,
        ai_confidences=confs,
    )
    assert out["ai_conf_marks_ready"] is True
    assert out["ai_conf_high_label"] == "+4.0%×1"
    assert out["ai_conf_low_label"] == "+6.0%×1"
    # Confidence marks stay off the glance note (Book strip only)
    assert "conf " not in out["note"]


def test_ai_gated_mark_returns_gated_free_none() -> None:
    from stock_checker.risk_halts import ai_gated_mark_returns, book_risk_report

    holds = [
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 4.0,
            "marked": True,
        },
        {
            "symbol": "MSFT",
            "kind": "stock",
            "cost_basis": 20_000,
            "unrealized_pct": -2.0,
            "marked": True,
        },
        {
            "symbol": "SAP.DE",
            "kind": "stock",
            "cost_basis": 5_000,
            "unrealized_pct": 1.0,
            "marked": True,
        },
        {
            "symbol": "BTC-USD",
            "kind": "crypto",
            "cost_basis": 8_000,
            "unrealized_pct": 6.0,
            "marked": True,
        },
        {
            "symbol": "ETH-USD",
            "kind": "crypto",
            "cost_basis": 4_000,
            "marked": False,
        },
    ]
    gated = {"AAPL": True, "MSFT": False, "BTC-USD": False}
    gm = ai_gated_mark_returns(holds, gated)
    assert gm["ai_roles_gated_pct"] == 4.0
    assert gm["ai_roles_gated_label"] == "+4.0%×1"
    # free: MSFT 20k@−2 + BTC 8k@6 → (−40k+48k)/28k = 0.2857…
    assert gm["ai_roles_free_pct"] == 0.29
    assert gm["ai_roles_free_label"] == "+0.3%×2"
    assert gm["ai_roles_free_lots"] == 2
    # none: SAP 5k@1 marked + ETH unmarked lot
    assert gm["ai_roles_none_pct"] == 1.0
    assert gm["ai_roles_none_label"] == "+1.0%×1"
    assert gm["ai_roles_none_lots"] == 2
    assert gm["ai_roles_marks_ready"] is True
    assert "roles gated +4.0%×1 · free +0.3%×2 · none +1.0%×1" in gm[
        "ai_roles_marks_bit"
    ]

    skipped = ai_gated_mark_returns(holds, None)
    assert skipped["ai_roles_marks_ready"] is False
    assert skipped["ai_roles_marks_bit"] == ""

    empty_map = ai_gated_mark_returns(holds, {})
    assert empty_map["ai_roles_marks_ready"] is True
    assert empty_map["ai_roles_none_lots"] == 5
    assert empty_map["ai_roles_gated_lots"] == 0

    out = book_risk_report(
        cash=5_000,
        equity=80_000,
        holdings=holds,
        max_positions=5,
        ai_gated=gated,
    )
    assert out["ai_roles_marks_ready"] is True
    assert out["ai_roles_gated_label"] == "+4.0%×1"
    assert out["ai_roles_free_label"] == "+0.3%×2"
    # Roles marks stay off the glance note (Book strip only)
    assert "roles " not in out["note"]


def test_scan_vol_mark_returns_with_soft_off() -> None:
    from stock_checker.risk_halts import book_risk_report, scan_vol_mark_returns

    holds = [
        {
            "symbol": "NVDA",
            "kind": "stock",
            "cost_basis": 20_000,
            "unrealized_pct": 4.0,
            "marked": True,
        },
        {
            "symbol": "AAPL",
            "kind": "stock",
            "cost_basis": 10_000,
            "unrealized_pct": 1.0,
            "marked": True,
        },
        {
            "symbol": "MSFT",
            "kind": "stock",
            "cost_basis": 8_000,
            "unrealized_pct": -2.0,
            "marked": True,
        },
        {
            "symbol": "BTC-USD",
            "kind": "crypto",
            "cost_basis": 5_000,
            "unrealized_pct": 6.0,
            "marked": True,
        },
        {
            "symbol": "ETH-USD",
            "kind": "crypto",
            "cost_basis": 4_000,
            "marked": False,
        },
    ]
    has_vol = {
        "NVDA": True,  # with
        "AAPL": False,  # soft n/a
        "MSFT": True,  # with
        # BTC absent → off; ETH unmarked off
    }
    vol = scan_vol_mark_returns(holds, has_vol)
    # with: NVDA 20k@4 + MSFT 8k@−2 → (80k − 16k)/28k = 2.2857…
    assert vol["scan_vol_with_pct"] == 2.29
    assert vol["scan_vol_with_label"] == "+2.3%×2"
    assert vol["scan_vol_with_lots"] == 2
    assert vol["scan_vol_soft_pct"] == 1.0
    assert vol["scan_vol_soft_label"] == "+1.0%×1"
    assert vol["scan_vol_off_pct"] == 6.0
    assert vol["scan_vol_off_label"] == "+6.0%×1"
    assert vol["scan_vol_off_lots"] == 2
    assert vol["scan_vol_marks_ready"] is True
    assert (
        "vol with +2.3%×2 · soft +1.0%×1 · off +6.0%×1"
        in vol["scan_vol_marks_bit"]
    )

    skipped = scan_vol_mark_returns(holds, None)
    assert skipped["scan_vol_marks_ready"] is False
    assert skipped["scan_vol_marks_bit"] == ""

    empty_map = scan_vol_mark_returns(holds, {})
    assert empty_map["scan_vol_off_lots"] == 5
    assert empty_map["scan_vol_marks_ready"] is True

    prefer2 = scan_vol_mark_returns(
        [
            {
                "symbol": "AAPL",
                "kind": "stock",
                "cost_basis": 10_000,
                "unrealized_pct": 3.0,
                "marked": True,
            }
        ],
        {"aapl": False, "AAPL": True},
    )
    assert prefer2["scan_vol_with_lots"] == 1
    assert prefer2["scan_vol_soft_lots"] == 0

    out = book_risk_report(
        cash=5_000,
        equity=80_000,
        holdings=holds,
        max_positions=5,
        scan_has_vol=has_vol,
    )
    assert out["scan_vol_marks_ready"] is True
    assert out["scan_vol_with_label"] == "+2.3%×2"
    assert out["scan_vol_soft_label"] == "+1.0%×1"
    assert "vol " not in out["note"]


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
    assert out["venue_marks_ready"] is False
    assert out["venue_marks_bit"] == ""
    assert out["exit_band_marks_ready"] is False
    assert out["exit_band_marks_bit"] == ""
    assert out["min_hold_marks_ready"] is False
    assert out["min_hold_marks_bit"] == ""
    assert out["scan_marks_ready"] is False
    assert out["scan_marks_bit"] == ""
    assert out["scan_list_marks_ready"] is False
    assert out["scan_list_marks_bit"] == ""
    assert out["scan_vol_marks_ready"] is False
    assert out["scan_vol_marks_bit"] == ""
    assert out["ai_debate_marks_ready"] is False
    assert out["ai_conf_marks_ready"] is False
    assert out["ai_roles_marks_ready"] is False
    assert out["ai_roles_marks_bit"] == ""


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
