"""Offline tests for paper commission helpers."""

from stock_checker.fees import calc_commission, rates_for_preset


def test_calc_commission_floor():
    assert abs(calc_commission(50.0, rate=0.0025, min_eur=1.0) - 1.0) < 1e-9
    assert abs(calc_commission(1000.0, rate=0.0025, min_eur=1.0) - 2.5) < 1e-9
    assert abs(calc_commission(1000.0, rate=0.001, min_eur=0.0) - 1.0) < 1e-9


def test_rates_for_preset():
    r, m = rates_for_preset("revolut_standard")
    assert abs(r - 0.0025) < 1e-9 and abs(m - 1.0) < 1e-9
    r2, m2 = rates_for_preset("revolut_ultra")
    assert abs(r2 - 0.0012) < 1e-9 and abs(m2 - 1.0) < 1e-9
