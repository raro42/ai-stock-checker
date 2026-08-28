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
