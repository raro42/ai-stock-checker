"""Entry candidate ordering — avoid crypto score domination (review A11)."""

from __future__ import annotations

from itertools import zip_longest
from typing import Any, Dict, List

# Stock breakouts map near-high % into this base so slots are not crypto-only.
STOCK_BREAKOUT_SCORE_BASE = 40.0
DEFAULT_MAX_CRYPTO_SLOTS = 2
DEFAULT_MAX_STOCK_SLOTS = 3


def _is_crypto(opp: Dict[str, Any]) -> bool:
    sym = str(opp.get("symbol") or "").upper()
    ac = str(opp.get("asset_class") or "").lower()
    return ac == "crypto" or "-USD" in sym or sym.endswith("USDT")


def interleave_asset_slots(
    opportunities: List[Dict[str, Any]],
    *,
    max_crypto: int = DEFAULT_MAX_CRYPTO_SLOTS,
    max_stock: int = DEFAULT_MAX_STOCK_SLOTS,
) -> List[Dict[str, Any]]:
    """
    Take top crypto and top stock by score, then interleave so execution
    is not a pure global sort (crypto momentum points used to crowd out stocks).
    """
    crypto = [
        o for o in opportunities if isinstance(o, dict) and _is_crypto(o)
    ]
    stock = [
        o for o in opportunities if isinstance(o, dict) and not _is_crypto(o)
    ]
    crypto.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    stock.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    top_c = crypto[: max(0, int(max_crypto))]
    top_s = stock[: max(0, int(max_stock))]
    out: List[Dict[str, Any]] = []
    for a, b in zip_longest(top_c, top_s):
        if a is not None:
            out.append(a)
        if b is not None:
            out.append(b)
    return out
