"""Fee-burn glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_fee_burn_glance


def test_fee_burn_glance_empty() -> None:
    assert build_fee_burn_glance(None, None)["ready"] is False
    assert build_fee_burn_glance(0, 10_000)["ready"] is False
    assert build_fee_burn_glance(50, 0)["ready"] is False
    assert build_fee_burn_glance(-1, 10_000)["ready"] is False


def test_fee_burn_glance_refuses_bool_fees_capital_realized() -> None:
    """tradermonty #700/#655: True→€1 fees / €1 start / €1 P&L must not invent."""
    assert build_fee_burn_glance(True, 10_000.0)["ready"] is False  # type: ignore[arg-type]
    assert build_fee_burn_glance(50.0, True)["ready"] is False  # type: ignore[arg-type]
    assert build_fee_burn_glance(False, 10_000.0)["ready"] is False  # type: ignore[arg-type]
    # Damaged realized stays silent (no invent fees>P&L from True→€1).
    g = build_fee_burn_glance(50.0, 10_000.0, realized_pnl=True)  # type: ignore[arg-type]
    assert g["ready"] is True
    assert g["realized"] is None
    assert g["fees_gt_realized"] is False
    assert "P&L" not in g["line"]
    # Damaged threshold falls back to 2% (not invent "off" from False).
    g2 = build_fee_burn_glance(50.0, 10_000.0, threshold=False)  # type: ignore[arg-type]
    assert g2["ready"] is True
    assert g2["tone"] == "quiet"
    assert g2["high"] is False
    # True→100% must not clear a real 3% burn (shared _coerce_fee_burn_pct).
    g3 = build_fee_burn_glance(300.0, 10_000.0, threshold=True)  # type: ignore[arg-type]
    assert g3["ready"] is True
    assert g3["high"] is True
    assert g3["tone"] == "warn"


def test_fee_burn_glance_quiet() -> None:
    g = build_fee_burn_glance(50.0, 10_000.0)
    assert g["ready"] is True
    assert g["tone"] == "quiet"
    assert g["high"] is False
    assert g["fees_gt_realized"] is False
    assert "€50.00" in g["line"]
    assert "0.5%" in g["line"]
    assert "quiet" in g["line"]
    assert "P&L" not in g["line"]


def test_fee_burn_glance_warn() -> None:
    g = build_fee_burn_glance(250.0, 10_000.0)
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["high"] is True
    assert "2.5%" in g["line"]
    assert "high" in g["line"]


def test_fee_burn_glance_threshold_edge() -> None:
    g = build_fee_burn_glance(200.0, 10_000.0, threshold=0.02)
    assert g["ready"] is True
    assert g["high"] is True
    assert g["tone"] == "warn"


def test_fee_burn_glance_vs_realized_quiet() -> None:
    g = build_fee_burn_glance(50.0, 10_000.0, realized_pnl=120.0)
    assert g["ready"] is True
    assert g["tone"] == "quiet"
    assert g["high"] is False
    assert g["fees_gt_realized"] is False
    assert g["realized"] == 120.0
    assert "vs €120.00 P&L" in g["line"]
    assert "quiet" in g["line"]


def test_fee_burn_glance_fees_eat_realized() -> None:
    """Portfolio AI / summarize_trades: fees > realized → warn even under 2% start."""
    g = build_fee_burn_glance(80.0, 10_000.0, realized_pnl=40.0)
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["high"] is True
    assert g["fees_gt_realized"] is True
    assert "fees>P&L" in g["line"]
    assert "vs €40.00 P&L" in g["line"]


def test_fee_burn_glance_fees_vs_zero_realized_after_sells() -> None:
    """Closed sells with €0 net still compare — fees eating flat P&L."""
    g = build_fee_burn_glance(50.0, 10_000.0, realized_pnl=0.0)
    assert g["fees_gt_realized"] is True
    assert g["tone"] == "warn"
    assert "fees>P&L" in g["line"]
