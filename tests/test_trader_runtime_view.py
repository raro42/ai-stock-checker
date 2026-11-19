"""Ops runtime view refuse bool meters from damaged portfolio / calm JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from openbb_backend.desk import _trader_runtime_view


def test_trader_runtime_view_refuses_bool_calm_and_fee_meters(
    tmp_path: Path, monkeypatch
) -> None:
    """tradermonty #700/#655: True→1 must not invent calm unlock / free legs."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    (tmp_path / "portfolio.json").write_text(
        json.dumps(
            {
                "cash": 100000,
                "free_legs_per_month": True,
                "fee_allowance_used": True,
                "fee_allowance_month": month,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "paper_calm.json").write_text(
        json.dumps(
            {
                "streak_days": True,
                "required_days": True,
                "ready_for_compose_default": False,
                "detail": "book overweight",
            }
        ),
        encoding="utf-8",
    )
    view = _trader_runtime_view()
    assert view["free_legs_per_month"] == 0
    assert view["fee_allowance_used"] == 0
    assert view["fee_allowance_remaining"] == 0
    assert view["calm_streak_days"] == 0
    assert view["calm_required_days"] == 30
    assert view["max_positions"] == 5
    assert view["min_hold_hours"] == 24.0
