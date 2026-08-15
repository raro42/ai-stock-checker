"""
Live crypto policy — majors only, wider exits, one slot.

Why (paper book Jul–Aug 2026): ESP/BANK/PROM-class alts + flat ±5% stops
burned large fees/P&L. Stocks were fine. PROM later bounced after a −5% stop —
tight stops on noisy alts are the wrong tool. Fix = allow only BTC/ETH for
*live scan + buys*, use wider crypto TP/SL, cap at one crypto position.
"""

from __future__ import annotations

from typing import Iterable, Tuple

# Paper live buys only — Yahoo/Binance style symbols.
LIVE_CRYPTO_SYMBOLS = frozenset({"BTC-USD", "ETH-USD"})

# One crypto name in a max-5 book so one stop cannot dominate P&L.
DEFAULT_MAX_CRYPTO_POSITIONS = 1

# Gross % vs avg buy (same units as stock exit_policy defaults).
# Wider than stock ±5%: crypto chop routinely tags 5%; fees need more edge to TP.
CRYPTO_TAKE_PROFIT_PCT = 10.0
CRYPTO_STOP_LOSS_PCT = 10.0


def is_crypto_symbol(symbol: str) -> bool:
    s = str(symbol or "").upper().strip()
    if not s:
        return False
    return s.endswith(("-USD", "-USDT", "USDT")) or "/" in s


def normalize_live_crypto_symbol(symbol: str) -> str:
    """Map BTCUSDT / BTC-USD → BTC-USD when base is a live major."""
    s = str(symbol or "").upper().strip()
    if s.endswith("/USDT"):
        s = s.replace("/USDT", "-USD")
    elif s.endswith("/USD"):
        s = s.replace("/USD", "-USD")
    elif s.endswith("USDT") and not s.endswith("-USDT"):
        s = s[:-4] + "-USD"
    elif s.endswith("-USDT"):
        s = s[:-5] + "-USD"
    return s


def is_live_crypto_buy_allowed(symbol: str) -> bool:
    """True if this crypto may be bought on the live paper desk."""
    if not is_crypto_symbol(symbol):
        return False
    return normalize_live_crypto_symbol(symbol) in LIVE_CRYPTO_SYMBOLS


def crypto_buy_block_reason(symbol: str) -> str:
    """Human reason when a crypto buy is blocked (empty if allowed / not crypto)."""
    if not is_crypto_symbol(symbol):
        return ""
    if is_live_crypto_buy_allowed(symbol):
        return ""
    return "crypto majors only (BTC/ETH)"


def count_crypto_holdings(symbols: Iterable[str]) -> int:
    return sum(1 for s in symbols if is_crypto_symbol(str(s)))


def crypto_slot_available(
    holdings: Iterable[str],
    *,
    max_crypto: int = DEFAULT_MAX_CRYPTO_POSITIONS,
) -> Tuple[bool, str]:
    """Whether the book can open another crypto position."""
    cap = max(0, int(max_crypto))
    n = count_crypto_holdings(holdings)
    if n >= cap:
        return False, f"crypto slot full ({n}/{cap})"
    return True, "crypto slot open"


def crypto_exit_thresholds() -> Tuple[float, float]:
    """(take_profit_pct, stop_loss_pct) for live crypto majors."""
    return CRYPTO_TAKE_PROFIT_PCT, CRYPTO_STOP_LOSS_PCT
