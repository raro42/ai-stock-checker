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


def test_book_risk_report_empty_book() -> None:
    from stock_checker.risk_halts import book_risk_report

    out = book_risk_report(cash=100_000, equity=100_000, holdings=[], max_positions=5)
    assert out["slots"] == "0/5"
    assert out["posture"] == "open"
    assert out["largest_symbol"] == ""
    assert out["concentration_warn"] is False
    assert out["cash_pct"] == 100.0


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
