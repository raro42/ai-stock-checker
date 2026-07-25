"""Tests for fee-burn startup warning."""

from stock_checker.fee_burn import fee_burn_warning


def test_fee_burn_none_when_missing(tmp_path):
    assert fee_burn_warning(str(tmp_path)) is None


def test_fee_burn_triggers_at_2pct(tmp_path):
    p = tmp_path / "portfolio.json"
    p.write_text('{"initial_cash": 10000, "total_fees_paid": 250}')
    msg = fee_burn_warning(str(tmp_path), fee_pct_of_capital=0.02)
    assert msg is not None
    assert "250" in msg


def test_fee_burn_quiet_below_threshold(tmp_path):
    p = tmp_path / "portfolio.json"
    p.write_text('{"initial_cash": 10000, "total_fees_paid": 100}')
    assert fee_burn_warning(str(tmp_path), fee_pct_of_capital=0.02) is None
