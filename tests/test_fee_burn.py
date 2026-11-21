"""Tests for fee-burn startup warning."""

import json

from stock_checker.fee_burn import (
    DEFAULT_FEE_BURN_PCT,
    _coerce_fee_burn_pct,
    fee_burn_facts,
    fee_burn_warning,
)


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


def test_fee_burn_refuses_bool_invent(tmp_path):
    """tradermonty #700/#655: True→€1 must not invent fee burn."""
    p = tmp_path / "portfolio.json"
    p.write_text(json.dumps({"initial_cash": True, "total_fees_paid": True}))
    assert fee_burn_facts(str(tmp_path)) is None
    assert fee_burn_warning(str(tmp_path)) is None
    p.write_text(json.dumps({"initial_cash": 10_000, "total_fees_paid": True}))
    assert fee_burn_facts(str(tmp_path)) is None
    p.write_text(json.dumps({"initial_cash": None, "total_fees_paid": 250}))
    assert fee_burn_facts(str(tmp_path)) is None


def test_coerce_fee_burn_pct_refuses_bool() -> None:
    """False→0% must not invent always-high; True→100% must not clear burn."""
    assert _coerce_fee_burn_pct(True) == DEFAULT_FEE_BURN_PCT
    assert _coerce_fee_burn_pct(False) == DEFAULT_FEE_BURN_PCT
    assert _coerce_fee_burn_pct(0) == DEFAULT_FEE_BURN_PCT
    assert _coerce_fee_burn_pct(None) == DEFAULT_FEE_BURN_PCT
    assert _coerce_fee_burn_pct(0.05) == 0.05


def test_fee_burn_facts_refuses_bool_threshold(tmp_path):
    """1% fees stay quiet under default 2% when threshold is bool/0."""
    p = tmp_path / "portfolio.json"
    p.write_text('{"initial_cash": 10000, "total_fees_paid": 100}')
    # Without refuse, False→0% would mark high=True.
    facts = fee_burn_facts(str(tmp_path), fee_pct_of_capital=False)
    assert facts is not None
    assert facts["high"] is False
    assert facts["threshold"] == DEFAULT_FEE_BURN_PCT
    assert fee_burn_warning(str(tmp_path), fee_pct_of_capital=False) is None
    # Without refuse, True→100% would clear a 3% burn.
    p.write_text('{"initial_cash": 10000, "total_fees_paid": 300}')
    hot = fee_burn_facts(str(tmp_path), fee_pct_of_capital=True)
    assert hot is not None
    assert hot["high"] is True
    assert hot["threshold"] == DEFAULT_FEE_BURN_PCT