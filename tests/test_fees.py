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


def test_calc_commission_refuses_bool_money():
    """tradermonty #700/#655: True→€1 / True→100% must not invent paper fees."""
    assert calc_commission(True, rate=0.0025, min_eur=1.0) == 0.0
    assert calc_commission(1000.0, rate=True, min_eur=1.0) == 0.0
    assert calc_commission(1000.0, rate=0.0025, min_eur=True) == 0.0
    assert calc_commission(False, rate=0.0025, min_eur=0.0) == 0.0


def test_fee_allowance_from_state_refuses_bool_used():
    """Damaged portfolio JSON must not invent True→1 spent free leg."""
    ledger = FeeAllowanceLedger.from_state(
        {"fee_allowance_month": "2026-11", "fee_allowance_used": True},
        free_legs_per_month=1,
    )
    assert ledger.used == 0
    assert ledger.remaining() == 1
    # First real fill still gets the free leg (not already "spent" by True).
    assert ledger.commission_for_leg(1000.0, "2026-11-01", rate=0.0025, min_eur=1.0) == 0.0
    assert ledger.used == 1


def test_fee_allowance_init_refuses_bool_counts():
    """int(True)→1 must not invent a free-leg quota or used count."""
    ledger = FeeAllowanceLedger(True, used=True)
    assert ledger.free_legs_per_month == 0
    assert ledger.used == 0
    assert abs(
        ledger.commission_for_leg(1000.0, "2026-11-01", rate=0.0025, min_eur=1.0) - 2.5
    ) < 1e-9
