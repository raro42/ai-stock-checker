"""Resolve ticker → human company / asset name for the paper desk."""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Callable, Optional

# Common crypto base names when yfinance is offline / skipped.
_CRYPTO_BASE = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "BNB": "BNB",
    "XRP": "XRP",
    "SOL": "Solana",
    "ADA": "Cardano",
    "DOGE": "Dogecoin",
    "DOT": "Polkadot",
    "AVAX": "Avalanche",
    "LINK": "Chainlink",
    "LTC": "Litecoin",
    "MATIC": "Polygon",
    "SHIB": "Shiba Inu",
    "TRX": "TRON",
    "UNI": "Uniswap",
    "ATOM": "Cosmos",
}

# Fast offline hints for common desk names (cache + yfinance still win).
_WELL_KNOWN = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "NVDA": "NVIDIA",
    "META": "Meta Platforms",
    "TSLA": "Tesla",
    "JPM": "JPMorgan Chase",
    "BAC": "Bank of America",
    "WMT": "Walmart",
    "BMY": "Bristol-Myers Squibb",
    "JNJ": "Johnson & Johnson",
    "XOM": "Exxon Mobil",
    "CVX": "Chevron",
    "ORCL": "Oracle",
    "V": "Visa",
    "MA": "Mastercard",
    "DIS": "Walt Disney",
    "NFLX": "Netflix",
    "AMD": "AMD",
    "INTC": "Intel",
    "CSCO": "Cisco",
    "PFE": "Pfizer",
    "MRK": "Merck",
    "ABBV": "AbbVie",
    "KO": "Coca-Cola",
    "PEP": "PepsiCo",
    "COST": "Costco",
    "HD": "Home Depot",
    "MCD": "McDonald's",
    "NKE": "Nike",
    "SPY": "SPDR S&P 500 ETF",
    "QQQ": "Invesco QQQ Trust",
    "IWM": "iShares Russell 2000 ETF",
    "GLD": "SPDR Gold Shares",
}



def _load_cache(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    if isinstance(raw, dict) and isinstance(raw.get("names"), dict):
        return {str(k): str(v) for k, v in raw["names"].items() if v}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items() if k != "updated_at" and v}
    return {}


def _save_cache(path: Path, names: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "names": dict(sorted(names.items())),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def crypto_fallback_name(symbol: str) -> Optional[str]:
    sym = symbol.upper()
    if not sym.endswith("-USD"):
        return None
    base = sym[: -len("-USD")]
    return _CRYPTO_BASE.get(base) or base.replace("-", " ").title()


def _fetch_yfinance_name(symbol: str) -> Optional[str]:
    try:
        import yfinance as yf

        t = yf.Ticker(symbol)
        info = getattr(t, "info", None) or {}
        if isinstance(info, dict):
            for key in ("longName", "shortName", "name"):
                val = info.get(key)
                if val and str(val).strip() and str(val).strip().upper() != symbol.upper():
                    return str(val).strip()
        # Crypto often lands here
        fb = crypto_fallback_name(symbol)
        if fb:
            return fb
    except Exception:
        return crypto_fallback_name(symbol)
    return None


def resolve_symbol_names(
    symbols: list[str],
    data_dir: Path,
    *,
    live: Optional[bool] = None,
    fetcher: Optional[Callable[[str], Optional[str]]] = None,
    timeout_s: float = 6.0,
) -> dict[str, str]:
    """Return mapping symbol → display name (cache + optional live lookup)."""
    if live is None:
        live = os.getenv("DESK_RESOLVE_NAMES", "1").strip() not in {
            "0",
            "false",
            "False",
            "no",
        }

    cache_path = data_dir / "symbol_names.json"
    cache = _load_cache(cache_path)
    out: dict[str, str] = {}
    missing: list[str] = []

    for sym in symbols:
        if not sym or sym == "—":
            continue
        if sym in cache:
            out[sym] = cache[sym]
            continue
        if sym in _WELL_KNOWN:
            out[sym] = _WELL_KNOWN[sym]
            cache[sym] = _WELL_KNOWN[sym]
            continue
        fb = crypto_fallback_name(sym)
        if fb and (sym.endswith("-USD") or not live):
            out[sym] = fb
            cache[sym] = fb
            continue
        missing.append(sym)

    if live and missing:
        fetch = fetcher or _fetch_yfinance_name
        with ThreadPoolExecutor(max_workers=min(6, len(missing))) as pool:
            futs = {pool.submit(fetch, s): s for s in missing}
            deadline = time.time() + timeout_s
            for fut, sym in futs.items():
                remaining = max(0.05, deadline - time.time())
                try:
                    name = fut.result(timeout=remaining)
                except FuturesTimeout:
                    name = crypto_fallback_name(sym)
                except Exception:
                    name = crypto_fallback_name(sym)
                if name:
                    out[sym] = name
                    cache[sym] = name

    if cache != _load_cache(cache_path):
        try:
            _save_cache(cache_path, cache)
        except OSError:
            pass

    return out


def display_name(symbol: str, names: dict[str, str]) -> str:
    """Name for templates; empty string if unknown / same as ticker."""
    name = (names.get(symbol) or "").strip()
    if not name or name.upper() == symbol.upper():
        return ""
    return name
