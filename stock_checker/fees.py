"""
Paper trading commission helpers.

Defaults target Revolut EEA stock pricing after free monthly allowance:
0.25%/side with €1 minimum (Ultra/Pro: 0.12%). This is harsher than the old
0.1% spot-like assumption — intentional for honest friend-group paper.

Not modeled (paper can over/under-state real brokerage):
- Free monthly Revolut stock allowance
- Crypto fee schedules / spreads
"""

from __future__ import annotations

from typing import Any

# After free monthly quota (not modeled): Standard–Metal.
REVOLUT_STANDARD_RATE = 0.0025
REVOLUT_STANDARD_MIN_EUR = 1.0
# Ultra / Trading Pro add-on.
REVOLUT_ULTRA_RATE = 0.0012
REVOLUT_ULTRA_MIN_EUR = 1.0
# Old desk default (Binance-like spot).
BINANCE_LIKE_RATE = 0.001
BINANCE_LIKE_MIN_EUR = 0.0

FEE_PRESETS: dict[str, dict[str, Any]] = {
    "revolut_standard": {
        "commission_rate": REVOLUT_STANDARD_RATE,
        "commission_min_eur": REVOLUT_STANDARD_MIN_EUR,
        "label": "Revolut Standard–Metal · 0.25% · €1 min",
    },
    "revolut_ultra": {
        "commission_rate": REVOLUT_ULTRA_RATE,
        "commission_min_eur": REVOLUT_ULTRA_MIN_EUR,
        "label": "Revolut Ultra / Trading Pro · 0.12% · €1 min",
    },
    "binance_like": {
        "commission_rate": BINANCE_LIKE_RATE,
        "commission_min_eur": BINANCE_LIKE_MIN_EUR,
        "label": "Spot-like · 0.1% · no floor",
    },
}

DEFAULT_FEE_PRESET = "revolut_standard"


def calc_commission(
    notional: float,
    *,
    rate: float,
    min_eur: float = 0.0,
) -> float:
    """Commission for one side: max(notional × rate, min_eur)."""
    try:
        notion = float(notional)
        r = float(rate)
        floor = float(min_eur)
    except (TypeError, ValueError):
        return 0.0
    if notion <= 0 or r < 0:
        return 0.0
    fee = notion * r
    if floor > 0:
        return max(fee, floor)
    return fee


def rates_for_preset(preset: str) -> tuple[float, float]:
    key = (preset or DEFAULT_FEE_PRESET).strip().lower()
    spec = FEE_PRESETS.get(key) or FEE_PRESETS[DEFAULT_FEE_PRESET]
    return float(spec["commission_rate"]), float(spec["commission_min_eur"])
