"""RiskManager Kelly / size refuse non-finite and win_rate∉(0,1)."""

from __future__ import annotations

import math

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
