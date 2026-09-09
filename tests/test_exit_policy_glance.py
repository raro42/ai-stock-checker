"""Stock exit-policy glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_exit_policy_glance


def test_exit_policy_glance_stock_bands() -> None:
    g = build_exit_policy_glance()
    assert g["ready"] is True
    assert g["tone"] == "stock"
    assert g["take_profit_pct"] == 8.0
    assert g["stop_loss_pct"] == 5.0
    assert g["rotate_min_pct"] == 5.0
    assert "TP +8%" in g["line"]
    assert "SL −5%" in g["line"] or "SL -5%" in g["line"]
    assert "rotate ≥+5%" in g["line"] or "rotate >=+5%" in g["line"]
