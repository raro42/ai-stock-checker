"""
Paper trading commission helpers.

Models Revolut EEA stock pricing: monthly commission-free order allowance,
then 0.25%/side with €1 minimum (Ultra/Pro: 0.12%). Calendar-month buckets
match Revolut billing cycles closely enough for paper.

Not modeled: crypto fee schedules / spreads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Paid-plan tiers after free monthly quota (Revolut Trading Ltd disclosure).
REVOLUT_STANDARD_RATE = 0.0025
REVOLUT_STANDARD_MIN_EUR = 1.0
REVOLUT_ULTRA_RATE = 0.0012
REVOLUT_ULTRA_MIN_EUR = 1.0
BINANCE_LIKE_RATE = 0.001
BINANCE_LIKE_MIN_EUR = 0.0

FEE_PRESETS: dict[str, dict[str, Any]] = {
    "revolut_standard": {
        "commission_rate": REVOLUT_STANDARD_RATE,
        "commission_min_eur": REVOLUT_STANDARD_MIN_EUR,
        "free_legs_per_month": 1,
        "label": "Revolut Standard · 0.25% · €1 min · 1 free/mo",
    },
    "revolut_plus": {
        "commission_rate": REVOLUT_STANDARD_RATE,
        "commission_min_eur": REVOLUT_STANDARD_MIN_EUR,
        "free_legs_per_month": 3,
        "label": "Revolut Plus · 0.25% · €1 min · 3 free/mo",
    },
    "revolut_ultra": {
        "commission_rate": REVOLUT_ULTRA_RATE,
        "commission_min_eur": REVOLUT_ULTRA_MIN_EUR,
        "free_legs_per_month": 10,
        "label": "Revolut Ultra / Trading Pro · 0.12% · €1 min · 10 free/mo",
    },
    "binance_like": {
        "commission_rate": BINANCE_LIKE_RATE,
        "commission_min_eur": BINANCE_LIKE_MIN_EUR,
        "free_legs_per_month": 0,
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


def _preset_spec(preset: str) -> dict[str, Any]:
    key = (preset or DEFAULT_FEE_PRESET).strip().lower()
    return FEE_PRESETS.get(key) or FEE_PRESETS[DEFAULT_FEE_PRESET]


def rates_for_preset(preset: str) -> tuple[float, float]:
    spec = _preset_spec(preset)
    return float(spec["commission_rate"]), float(spec["commission_min_eur"])


def free_legs_for_preset(preset: str) -> int:
    return int(_preset_spec(preset).get("free_legs_per_month") or 0)


def month_key_from_timestamp(timestamp: str) -> str:
    """YYYY-MM from trade timestamp (UTC/local ISO strings)."""
    raw = (timestamp or "").strip()
    if len(raw) >= 7 and raw[4] == "-":
        return raw[:7]
    return datetime.now(timezone.utc).strftime("%Y-%m")


class FeeAllowanceLedger:
    """Track Revolut-style free order legs per calendar month."""

    def __init__(
        self,
        free_legs_per_month: int = 0,
        *,
        month: str = "",
        used: int = 0,
    ) -> None:
        self.free_legs_per_month = max(0, int(free_legs_per_month))
        self.month = month or ""
        self.used = max(0, int(used))

    def remaining(self) -> int:
        return max(0, self.free_legs_per_month - self.used)

    def _roll_month(self, month: str) -> None:
        if month and month != self.month:
            self.month = month
            self.used = 0

    def commission_for_leg(
        self,
        notional: float,
        timestamp: str,
        *,
        rate: float,
        min_eur: float,
    ) -> float:
        month = month_key_from_timestamp(timestamp)
        self._roll_month(month)
        if self.free_legs_per_month > 0 and self.used < self.free_legs_per_month:
            self.used += 1
            return 0.0
        return calc_commission(notional, rate=rate, min_eur=min_eur)

    @classmethod
    def reconcile_from_transactions(
        cls,
        transactions: list[dict[str, Any]],
        *,
        free_legs_per_month: int,
        current_month: str | None = None,
    ) -> FeeAllowanceLedger:
        month = current_month or datetime.now(timezone.utc).strftime("%Y-%m")
        used = sum(
            1
            for t in transactions
            if month_key_from_timestamp(str(t.get("timestamp") or "")) == month
        )
        return cls(free_legs_per_month, month=month, used=used)

    def to_state(self) -> dict[str, Any]:
        return {
            "fee_allowance_month": self.month,
            "fee_allowance_used": self.used,
            "free_legs_per_month": self.free_legs_per_month,
        }

    @classmethod
    def from_state(
        cls,
        state: dict[str, Any] | None,
        *,
        free_legs_per_month: int,
    ) -> FeeAllowanceLedger:
        if not isinstance(state, dict):
            return cls(free_legs_per_month)
        return cls(
            free_legs_per_month,
            month=str(state.get("fee_allowance_month") or ""),
            used=int(state.get("fee_allowance_used") or 0),
        )
