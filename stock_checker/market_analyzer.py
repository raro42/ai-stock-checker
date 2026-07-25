#!/usr/bin/env python3

import yfinance as yf
from typing import List, Dict
from datetime import datetime


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

    def get_top_movers(self, period: str = "1d", limit: int = 10) -> List[Dict]:
        """
        Get top gaining and losing stocks from S&P 500.

        Args:
            period: Time period for comparison (1d, 5d, 1mo)
            limit: Number of top movers to return

        Returns:
            List of dicts with stock info and price changes
        """
        symbols = self.get_sp500_components()
        movers = []

        print(f"Analyzing {len(symbols)} S&P 500 stocks...")

        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period)

                if hist.empty or len(hist) < 2:
                    continue

                start_price = float(hist["Close"].iloc[0])
                end_price = float(hist["Close"].iloc[-1])
                change_pct = ((end_price - start_price) / start_price) * 100

                info = ticker.info
                movers.append({
                    "symbol": symbol,
                    "name": info.get("longName", symbol),
                    "start_price": round(start_price, 2),
                    "current_price": round(end_price, 2),
                    "change": round(end_price - start_price, 2),
                    "change_pct": round(change_pct, 2),
                    "volume": info.get("volume") or info.get("regularMarketVolume"),
                    "market_cap": info.get("marketCap"),
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

            current_price = float(hist["Close"].iloc[-1])
            month_ago_price = float(hist["Close"].iloc[0])
            change_pct = ((current_price - month_ago_price) / month_ago_price) * 100

            # Calculate volatility (standard deviation of daily returns)
            daily_returns = hist["Close"].pct_change().dropna()
            volatility = float(daily_returns.std() * 100)

            return {
                "symbol": "BTC-USD",
                "name": "Bitcoin",
                "current_price": round(current_price, 2),
                "24h_volume": info.get("volume24Hr") or info.get("regularMarketVolume"),
                "market_cap": info.get("marketCap"),
                "change_1d": self._get_period_change(ticker, "1d"),
                "change_7d": self._get_period_change(ticker, "7d"),
                "change_30d": round(change_pct, 2),
                "volatility_30d": round(volatility, 2),
                "52_week_high": info.get("fiftyTwoWeekHigh"),
                "52_week_low": info.get("fiftyTwoWeekLow"),
                "historical_data": hist.tail(30).to_dict(orient="index"),
            }
        except Exception as e:
            raise ValueError(f"Failed to fetch Bitcoin data: {str(e)}")

    def _get_period_change(self, ticker, period: str) -> float:
        """Helper to calculate price change over a period."""
        try:
            hist = ticker.history(period=period)
            if hist.empty or len(hist) < 2:
                return 0.0
            start = float(hist["Close"].iloc[0])
            end = float(hist["Close"].iloc[-1])
            return round(((end - start) / start) * 100, 2)
        except:
            return 0.0

    def analyze_bitcoin_for_investment(self) -> Dict:
        """
        Analyze Bitcoin with investment-relevant metrics.

        Returns comprehensive analysis including price trends, volatility,
        and momentum indicators.
        """
        btc_data = self.get_bitcoin_data()

        # Simple momentum analysis
        change_30d = btc_data["change_30d"]
        volatility = btc_data["volatility_30d"]

        # Basic investment signals
        if change_30d > 10 and volatility < 5:
            momentum = "Strong Uptrend - Low Volatility"
        elif change_30d > 5:
            momentum = "Moderate Uptrend"
        elif change_30d < -10:
            momentum = "Strong Downtrend"
        elif change_30d < -5:
            momentum = "Moderate Downtrend"
        else:
            momentum = "Sideways/Consolidation"

        if volatility > 10:
            risk_level = "High"
        elif volatility > 5:
            risk_level = "Moderate"
        else:
            risk_level = "Low"

        return {
            **btc_data,
            "momentum": momentum,
            "risk_level": risk_level,
            "analysis_timestamp": datetime.now().isoformat(),
        }
