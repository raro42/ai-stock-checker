"""
Hard entry filters for scan-driven buys (CACI-class loss prevention).

Soft gates (regime / RS / breadth) live in entry_gates.py. These run at execution
time with opportunity metadata from the scanner.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Tuple

# Breakout band: need a real pullback (CACI −0.5% / froth entries hurt Aug 2026).
BREAKOUT_PCT_MIN = -5.0
BREAKOUT_PCT_MAX = -2.0

DEFAULT_STOP_LOSS_PCT = 5.0
# Implied swing/ATR stop must leave headroom beyond the book stop.
STOP_BUFFER_PCT = 1.0

_MIN_SIZE_MULT = 0.35


def parse_risk_pct_from_note(note: str) -> float | None:
    """Parse '−5.1%' style risk distance from a scan risk summary."""
    if not note:
        return None
    m = re.search(r"[−-](\d+(?:\.\d+)?)\s*%", note)
    if not m:
        return None
    try:
        return float(m.group(1))
    except (TypeError, ValueError):
        return None


def implied_risk_pct(opportunity: Mapping[str, Any]) -> float | None:
    raw = opportunity.get("risk_pct")
    if raw is not None:
        try:
            return abs(float(raw))
        except (TypeError, ValueError):
            pass
    parsed = parse_risk_pct_from_note(str(opportunity.get("risk_note") or ""))
    return parsed


def ai_entry_allows(
    ai_action: str | None,
    ai_confidence: str | None,
    *,
    strategy: str | None = None,
) -> Tuple[bool, str]:
    action = str(ai_action or "").upper()
    conf = str(ai_confidence or "").upper()
    strat = str(strategy or "").lower()
    if action == "SELL":
        return False, "AI SELL"
    if action == "HOLD" and conf == "LOW":
        return False, "AI HOLD (LOW confidence)"
    # Breakouts need an explicit BUY — HOLD/neutral drove EXPE/NTRA stop chains.
    if strat == "breakout":
        if action != "BUY":
            return False, "breakout needs AI BUY"
        if conf == "LOW":
            return False, "AI LOW confidence on breakout"
    elif conf == "LOW" and action == "HOLD":
        return False, "AI HOLD (LOW confidence)"
    return True, "AI ok"



def breakout_pullback_allows(
    opportunity: Mapping[str, Any],
) -> Tuple[bool, str]:
    asset = str(opportunity.get("asset_class") or "").lower()
    strategy = str(opportunity.get("strategy") or "").lower()
    if asset != "stock" and strategy != "breakout":
        return True, "not stock breakout"
    pct_raw = opportunity.get("pct_from_high")
    if pct_raw is None:
        return True, "no pct_from_high"
    try:
        pct = float(pct_raw)
    except (TypeError, ValueError):
        return True, "pct unreadable"
    if pct > BREAKOUT_PCT_MAX:
        return (
            False,
            f"too extended ({pct:+.2f}% from 52w high; need ≤{BREAKOUT_PCT_MAX:g}%)",
        )
    if pct < BREAKOUT_PCT_MIN:
        return (
            False,
            f"too far from high ({pct:+.2f}%; band ≥{BREAKOUT_PCT_MIN:g}%)",
        )
    return True, "breakout pullback ok"


def scan_risk_allows(
    opportunity: Mapping[str, Any],
    *,
    stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT,
) -> Tuple[bool, str]:
    if opportunity.get("risk_rr_ok") is False:
        return False, "scan R:R not ok"
    implied = implied_risk_pct(opportunity)
    if implied is None:
        return True, "risk n/a"
    ceiling = float(stop_loss_pct) + STOP_BUFFER_PCT
    if implied <= ceiling:
        return (
            False,
            f"implied stop −{implied:.1f}% too tight vs −{stop_loss_pct:g}% book stop",
        )
    return True, "risk ok"


def position_size_multiplier(
    opportunity: Mapping[str, Any],
    *,
    stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT,
) -> float:
    implied = implied_risk_pct(opportunity)
    if implied is None or implied <= 0:
        return 1.0
    headroom = float(stop_loss_pct) + STOP_BUFFER_PCT
    if implied >= headroom * 1.5:
        return 1.0
    ratio = implied / headroom
    return max(_MIN_SIZE_MULT, min(1.0, ratio))


def scan_entry_guards(
    opportunity: Mapping[str, Any],
    *,
    ai_action: str | None = None,
    ai_confidence: str | None = None,
    stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT,
) -> Tuple[bool, str, float]:
    """
    Final scan-entry checks before a buy.

    Returns (allowed, reason, position_size_multiplier).
    """
    ok, why = ai_entry_allows(
        ai_action,
        ai_confidence,
        strategy=str(opportunity.get("strategy") or ""),
    )
    if not ok:
        return False, why, 1.0

    ok, why = breakout_pullback_allows(opportunity)
    if not ok:
        return False, why, 1.0

    ok, why = scan_risk_allows(opportunity, stop_loss_pct=stop_loss_pct)
    if not ok:
        return False, why, 1.0

    mult = position_size_multiplier(opportunity, stop_loss_pct=stop_loss_pct)
    return True, "entry guards ok", mult
