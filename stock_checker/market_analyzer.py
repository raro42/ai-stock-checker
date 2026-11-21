#!/usr/bin/env python3

from __future__ import annotations

import yfinance as yf
from typing import Dict, List, Optional
from datetime import datetime

from stock_checker.secret_redact import safe_exc_text
from stock_checker.technical_indicators import (
    _finite_signed,
    _valid_close,
    _valid_volume,
    coerce_nonneg_int,
    daily_pct_change,
)


DEFAULT_TOP_MOVERS_LIMIT = 10


def _coerce_movers_limit(value: object, default: int = DEFAULT_TOP_MOVERS_LIMIT) -> int:
    """Positive movers strip length, or ``default`` when bool/gap.

    tradermonty #700/#655 + xang1234/portfolio AI: ``int(True)→1`` /
    ``[:True]→1-row`` must not invent a one-name CLI/monitor movers strip after
    CMC/Binance strip knobs already refused thin packaging.
    """
    n = coerce_nonneg_int(value)
    if n is None or n < 1:
        return int(default)
    return n


def _info_money(raw: object) -> Optional[float]:
    """Yahoo info volume/cap, or None when bool/gap (never ``True→1``)."""
    if not _finite_signed(raw):
        return None
    value = float(raw)  # type: ignore[arg-type]
    if value < 0:
        return None
    return value


def _info_volume(raw: object) -> Optional[float]:
    if not _valid_volume(raw):
        return None
    return float(raw)  # type: ignore[arg-type]


class MarketAnalyzer:
    """Analyze market trends and identify top movers."""

    def __init__(self):
        self.sp500_ticker = "^GSPC"

    def get_sp500_components(self) -> List[str]:
        """
        Get S&P 500 component symbols.
        Using a curated list of major S&P 500 stocks for analysis.
        """
        # Top liquid S&P 500 stocks for demonstration
        # In production, you'd fetch the full list from Wikipedia or other sources
        major_sp500 = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
            "UNH", "JNJ", "XOM", "V", "JPM", "WMT", "PG", "MA", "CVX", "HD",
            "LLY", "MRK", "ABBV", "PEP", "KO", "AVGO", "COST", "MCD", "TMO",
            "CSCO", "ABT", "ACN", "DHR", "VZ", "NKE", "ADBE", "CRM", "TXN",
            "NEE", "CMCSA", "DIS", "PM", "ORCL", "INTC", "WFC", "BMY", "UPS",
            "AMD", "HON", "COP", "RTX", "UNP", "LOW", "MS", "QCOM", "IBM",
            "CAT", "AMGN", "T", "GS", "BA", "BLK", "LMT", "PLD", "SPGI",
            "GILD", "DE", "AXP", "INTU", "ISRG", "C", "SBUX", "SYK", "BKNG",
            "MDLZ", "ADI", "TJX", "MMC", "PFE", "NOW", "REGN", "ZTS", "TMUS",
            "CVS", "CB", "CI", "MO", "SO", "DUK", "PGR", "EL", "BDX", "SLB",
            "ITW", "BSX", "AON", "HUM", "EOG", "MU", "FIS", "APD", "GE", "USB"
        ]
        return major_sp500

    def get_top_movers(
        self, period: str = "1d", limit: object = DEFAULT_TOP_MOVERS_LIMIT
    ) -> List[Dict]:
        """
        Get top gaining and losing stocks from S&P 500.

        Args:
            period: Time period for comparison (1d, 5d, 1mo)
            limit: Number of top movers to return

        Returns:
            List of dicts with stock info and price changes
        """
        limit = _coerce_movers_limit(limit, DEFAULT_TOP_MOVERS_LIMIT)
        symbols = self.get_sp500_components()
        movers = []

        print(f"Analyzing {len(symbols)} S&P 500 stocks...")

        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period)

                if hist.empty or len(hist) < 2:
                    continue

                start_raw = hist["Close"].iloc[0]
                end_raw = hist["Close"].iloc[-1]
                # Refuse bool/gap — float(True)→$1 invents a fake mover.
                change_pct = daily_pct_change(end_raw, start_raw)
                if change_pct is None:
                    continue
                start_price = float(start_raw)
                end_price = float(end_raw)

                info = ticker.info
                vol = _info_volume(info.get("volume"))
                if vol is None:
                    vol = _info_volume(info.get("regularMarketVolume"))
                movers.append({
                    "symbol": symbol,
                    "name": info.get("longName", symbol),
                    "start_price": round(start_price, 2),
                    "current_price": round(end_price, 2),
                    "change": round(end_price - start_price, 2),
                    "change_pct": round(change_pct, 2),
                    "volume": vol,
                    "market_cap": _info_money(info.get("marketCap")),
                })
            except Exception:
                # Skip stocks that fail to fetch
                continue

        # Sort by absolute percentage change
        movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)

        return movers[:limit]

    def get_bitcoin_data(self) -> Dict:
        """Get Bitcoin price data using BTC-USD ticker."""
        try:
            ticker = yf.Ticker("BTC-USD")
            info = ticker.info
            hist = ticker.history(period="1mo")

            if hist.empty:
                raise ValueError("No Bitcoin data available")

            current_raw = hist["Close"].iloc[-1]
            month_ago_raw = hist["Close"].iloc[0]
            # Refuse bool/gap — float(True)→$1 invents BTC marks / flat %.
            if not (_valid_close(current_raw) and _valid_close(month_ago_raw)):
                raise ValueError("No usable Bitcoin closes available")
            current_price = float(current_raw)
            change_pct = daily_pct_change(current_raw, month_ago_raw)
            if change_pct is None:
                raise ValueError("No usable Bitcoin 30d change available")

            # Volatility from usable closes only (skip bool/gap bars).
            closes = [
                float(c)
                for c in hist["Close"].tolist()
                if _valid_close(c)
            ]
            volatility: Optional[float] = None
            if len(closes) >= 2:
                rets = [
                    (closes[i] - closes[i - 1]) / closes[i - 1]
                    for i in range(1, len(closes))
                ]
                if rets:
                    mean = sum(rets) / len(rets)
                    var = sum((r - mean) ** 2 for r in rets) / len(rets)
                    vol_raw = (var**0.5) * 100.0
                    if _finite_signed(vol_raw):
                        volatility = float(vol_raw)

            vol_24h = _info_volume(info.get("volume24Hr"))
            if vol_24h is None:
                vol_24h = _info_volume(info.get("regularMarketVolume"))

            return {
                "symbol": "BTC-USD",
                "name": "Bitcoin",
                "current_price": round(current_price, 2),
                "24h_volume": vol_24h,
                "market_cap": _info_money(info.get("marketCap")),
                "change_1d": self._get_period_change(ticker, "1d"),
                "change_7d": self._get_period_change(ticker, "7d"),
                "change_30d": round(change_pct, 2),
                "volatility_30d": (
                    round(volatility, 2) if volatility is not None else None
                ),
                "52_week_high": _info_money(info.get("fiftyTwoWeekHigh")),
                "52_week_low": _info_money(info.get("fiftyTwoWeekLow")),
                "historical_data": hist.tail(30).to_dict(orient="index"),
            }
        except Exception as e:
            raise ValueError(
                f"Failed to fetch Bitcoin data: {safe_exc_text(e)}"
            ) from e

    def _get_period_change(self, ticker, period: str) -> Optional[float]:
        """Period % change, or None when unavailable (never invent flat ``0.0``)."""
        try:
            hist = ticker.history(period=period)
            if hist.empty or len(hist) < 2:
                return None
            change = daily_pct_change(hist["Close"].iloc[-1], hist["Close"].iloc[0])
            if change is None:
                return None
            return round(change, 2)
        except Exception:
            return None

    def analyze_bitcoin_for_investment(self) -> Dict:
        """
        Analyze Bitcoin with investment-relevant metrics.

        Returns comprehensive analysis including price trends, volatility,
        and momentum indicators.
        """
        btc_data = self.get_bitcoin_data()

        # Simple momentum analysis — missing %/vol stay unavailable (not flat 0).
        change_30d = btc_data.get("change_30d")
        volatility = btc_data.get("volatility_30d")
        change_ok = _finite_signed(change_30d)
        vol_ok = _finite_signed(volatility)

        if not change_ok:
            momentum = "Unavailable"
        elif vol_ok and float(change_30d) > 10 and float(volatility) < 5:
            momentum = "Strong Uptrend - Low Volatility"
        elif float(change_30d) > 5:
            momentum = "Moderate Uptrend"
        elif float(change_30d) < -10:
            momentum = "Strong Downtrend"
        elif float(change_30d) < -5:
            momentum = "Moderate Downtrend"
        else:
            momentum = "Sideways/Consolidation"

        if not vol_ok:
            risk_level = "Unavailable"
        elif float(volatility) > 10:
            risk_level = "High"
        elif float(volatility) > 5:
            risk_level = "Moderate"
        else:
            risk_level = "Low"

        return {
            **btc_data,
            "momentum": momentum,
            "risk_level": risk_level,
            "analysis_timestamp": datetime.now().isoformat(),
        }
