"""Book limits: compose CLI flags must match Ops trader_config.DEFAULTS."""

from __future__ import annotations

import inspect
import re
from pathlib import Path

from stock_checker.intelligent_trader import IntelligentTrader
from stock_checker.trader_config import DEFAULTS


ROOT = Path(__file__).resolve().parents[1]


def test_ops_defaults_are_anti_churn() -> None:
    assert int(DEFAULTS["max_positions"]) == 5
    assert float(DEFAULTS["min_hold_hours"]) == 24.0


def test_intelligent_trader_ctor_defaults_match_ops() -> None:
    sig = inspect.signature(IntelligentTrader.__init__)
    assert sig.parameters["max_positions"].default == int(DEFAULTS["max_positions"])
    assert sig.parameters["min_hold_time"].default == int(
        float(DEFAULTS["min_hold_hours"]) * 3600
    )


def test_compose_intelligent_trader_flags_match_ops() -> None:
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    # Only the intelligent-trader service block
    m = re.search(
        r"intelligent-trader:.*?command:\s*>(.*?)(?:\n  [a-z]|\Z)",
        text,
        flags=re.S,
    )
    assert m, "intelligent-trader command block not found"
    cmd = m.group(1)
    max_m = re.search(r"--max-positions\s+(\d+)", cmd)
    hold_m = re.search(r"--min-hold-time\s+(\d+)", cmd)
    assert max_m, "missing --max-positions in compose"
    assert hold_m, "missing --min-hold-time in compose"
    assert int(max_m.group(1)) == int(DEFAULTS["max_positions"])
    assert int(hold_m.group(1)) == int(float(DEFAULTS["min_hold_hours"]) * 3600)
