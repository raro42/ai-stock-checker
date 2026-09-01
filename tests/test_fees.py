"""Offline tests for paper commission helpers."""

from stock_checker.fees import (
    FeeAllowanceLedger,
    calc_commission,
    free_legs_for_preset,
    rates_for_preset,
)


def test_calc_commission_floor():
    assert abs(calc_commission(50.0, rate=0.0025, min_eur=1.0) - 1.0) < 1e-9
    assert abs(calc_commission(1000.0, rate=0.0025, min_eur=1.0) - 2.5) < 1e-9
    assert abs(calc_commission(1000.0, rate=0.001, min_eur=0.0) - 1.0) < 1e-9


def test_rates_for_preset():
    r, m = rates_for_preset("revolut_standard")
    assert abs(r - 0.0025) < 1e-9 and abs(m - 1.0) < 1e-9
    r2, m2 = rates_for_preset("revolut_ultra")
    assert abs(r2 - 0.0012) < 1e-9 and abs(m2 - 1.0) < 1e-9


def test_free_legs_for_preset():
    assert free_legs_for_preset("revolut_standard") == 1
    assert free_legs_for_preset("revolut_plus") == 3
    assert free_legs_for_preset("revolut_ultra") == 10
    assert free_legs_for_preset("binance_like") == 0


def test_allowance_uses_free_legs_then_charges():
    ledger = FeeAllowanceLedger(3)
    assert ledger.commission_for_leg(1000.0, "2026-08-01", rate=0.0025, min_eur=1.0) == 0.0
    assert ledger.commission_for_leg(1000.0, "2026-08-02", rate=0.0025, min_eur=1.0) == 0.0
    assert ledger.commission_for_leg(1000.0, "2026-08-03", rate=0.0025, min_eur=1.0) == 0.0
    assert abs(
        ledger.commission_for_leg(1000.0, "2026-08-04", rate=0.0025, min_eur=1.0) - 2.5
    ) < 1e-9
    assert ledger.remaining() == 0


def test_allowance_resets_each_month():
    ledger = FeeAllowanceLedger(1)
    assert ledger.commission_for_leg(500.0, "2026-08-15", rate=0.0025, min_eur=1.0) == 0.0
    assert abs(
        ledger.commission_for_leg(400.0, "2026-08-16", rate=0.0025, min_eur=1.0) - 1.0
    ) < 1e-9
    assert ledger.commission_for_leg(500.0, "2026-09-01", rate=0.0025, min_eur=1.0) == 0.0
