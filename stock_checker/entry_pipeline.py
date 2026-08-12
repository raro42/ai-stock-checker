"""Entry pipeline: promote filter + asset-class slot order (not live exits)."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .entry_slots import interleave_asset_slots
from .gate_audit import log_soft_allow
from .promoted_strategy import (
    build_bars_for_symbols,
    filter_opportunities as filter_promoted_opportunities,
)


def apply_promote_entry_filter(
    opportunities: List[Dict],
    *,
    promote_on: bool,
    bars_builder: Optional[Callable[[List[str]], Dict]] = None,
) -> List[Dict]:
    """
    Optional champion entry veto. Soft-keeps names with missing bars.
    Does not change exit_policy.
    """
    if not promote_on or not opportunities:
        return list(opportunities)
    symbols = [str(o.get("symbol") or "") for o in opportunities if o.get("symbol")]
    builder = bars_builder or build_bars_for_symbols
    bars = builder(symbols)
    before = len(opportunities)
    kept = filter_promoted_opportunities(opportunities, bars)
    print(
        f"   Promote filter: kept {len(kept)}/{before} "
        f"(rejected {before - len(kept)}; no-bars kept)"
    )
    for opp in kept:
        if str(opp.get("promoted_filter") or "") == "skip_no_bars":
            log_soft_allow("promote", f"{opp.get('symbol')}: skip_no_bars")
    return kept


def order_entry_candidates(
    opportunities: List[Dict],
    *,
    max_crypto: int,
    max_stock: int,
) -> List[Dict]:
    """Interleave crypto/stock slots instead of pure global score sort."""
    return interleave_asset_slots(
        list(opportunities),
        max_crypto=max(1, int(max_crypto)),
        max_stock=max(1, int(max_stock)),
    )
