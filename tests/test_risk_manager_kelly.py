"""RiskManager Kelly / size refuse non-finite and win_rate∉(0,1)."""

from __future__ import annotations

import math

import pytest

from stock_checker.risk_manager import RiskManager


def test_kelly_refuses_perfect_and_zero_win_rate() -> None:
    rm = RiskManager(max_position_size=0.10)
    assert rm.calculate_kelly_criterion(1.0, 80.0, 40.0) == 0.0
    assert rm.calculate_kelly_criterion(0.0, 80.0, 40.0) == 0.0


def test_kelly_refuses_non_finite_inputs() -> None:
    rm = RiskManager(max_position_size=0.10)
    assert rm.calculate_kelly_criterion(math.nan, 80.0, 40.0) == 0.0
    assert rm.calculate_kelly_criterion(0.6, math.inf, 40.0) == 0.0
    assert rm.calculate_kelly_criterion(0.6, 80.0, math.nan) == 0.0


def test_kelly_half_kelly_on_valid_edge() -> None:
    rm = RiskManager(max_position_size=0.10)
    # 60% WR · payoff 2 → f* = 0.6 − 0.4/2 = 0.4 → half = 0.2 → cap 0.10
    assert rm.calculate_kelly_criterion(0.6, 80.0, 40.0) == 0.10
    # thinner edge stays under cap: 55% · R=1.2 → f*≈0.175 → half≈0.0875
    got = rm.calculate_kelly_criterion(0.55, 12.0, 10.0)
    assert 0.08 < got < 0.10


def test_position_size_refuses_non_finite() -> None:
    rm = RiskManager(max_position_size=0.10)
    assert rm.calculate_position_size(math.nan, 10.0) == 0
    assert rm.calculate_position_size(10_000.0, math.inf) == 0
    assert rm.calculate_position_size(10_000.0, 10.0, volatility=math.nan) == 0
    assert rm.calculate_position_size(10_000.0, 10.0) == 100


def test_atr_stop_uses_reported_cent_stop() -> None:
    """tradermonty #813: risk_per_share from rounded stop, not atr×mult."""
    rm = RiskManager(use_atr_stops=True, atr_multiplier=1.5, stop_loss_pct=0.05)
    stop = rm.set_stop_loss("TEST", 5.0, atr=0.024)
    assert stop == 4.96
    assert rm.stop_losses["TEST"] == 4.96
    assert rm.position_risks["TEST"] == pytest.approx(0.04, rel=1e-12)


def test_atr_stop_refuses_bool_and_falls_back_to_pct() -> None:
    rm = RiskManager(use_atr_stops=True, atr_multiplier=2.0, stop_loss_pct=0.05)
    stop = rm.set_stop_loss("TEST", 100.0, atr=True)  # type: ignore[arg-type]
    assert stop == 95.0
    assert rm.position_risks["TEST"] == pytest.approx(5.0, rel=1e-12)
    assert rm.set_stop_loss("BAD", True, atr=2.0) == 0.0  # type: ignore[arg-type]
