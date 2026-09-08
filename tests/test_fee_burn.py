"""Tests for fee-burn startup warning."""

from stock_checker.fee_burn import fee_burn_facts, fee_burn_warning


def test_fee_burn_none_when_missing(tmp_path):
    assert fee_burn_warning(str(tmp_path)) is None
    assert fee_burn_facts(str(tmp_path)) is None


def test_fee_burn_facts_quiet(tmp_path):
    p = tmp_path / "portfolio.json"
    p.write_text('{"initial_cash": 10000, "total_fees_paid": 100}')
    facts = fee_burn_facts(str(tmp_path), fee_pct_of_capital=0.02)
    assert facts is not None
    assert facts["high"] is False
    assert facts["ratio"] == 0.01


def test_fee_burn_triggers_at_2pct(tmp_path):
    p = tmp_path / "portfolio.json"
    p.write_text('{"initial_cash": 10000, "total_fees_paid": 250}')
    msg = fee_burn_warning(str(tmp_path), fee_pct_of_capital=0.02)
    assert msg is not None
    assert "250" in msg
    facts = fee_burn_facts(str(tmp_path), fee_pct_of_capital=0.02)
    assert facts is not None
    assert facts["high"] is True


def test_fee_burn_quiet_below_threshold(tmp_path):
    p = tmp_path / "portfolio.json"
    p.write_text('{"initial_cash": 10000, "total_fees_paid": 100}')
    assert fee_burn_warning(str(tmp_path), fee_pct_of_capital=0.02) is None
