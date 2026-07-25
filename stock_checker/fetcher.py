#!/usr/bin/env python3

from typing import Literal
import os
import json
from pathlib import Path
from datetime import datetime
from urllib3.exceptions import NewConnectionError
from requests.exceptions import ConnectionError as RequestsConnectionError

# Import yfinance as fallback
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("⚠️  yfinance not available")

# Import Finnhub fetcher
try:
    from .finnhub_fetcher import FinnhubFetcher
    FINNHUB_AVAILABLE = True
except ImportError:
    FINNHUB_AVAILABLE = False
    print("⚠️  Finnhub fetcher not available")

ProviderType = Literal["finnhub", "yfinance"]


class ProviderSemaphore:
    """Manage provider selection semaphore to track which data provider to use first."""

    def __init__(self, data_dir: str = "/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.semaphore_file = self.data_dir / "provider_semaphore.json"

    def get_primary_provider(self) -> ProviderType:
        """Get the current primary provider from semaphore file."""
        if not self.semaphore_file.exists():
            # Default to yfinance if semaphore doesn't exist (since finnhub is blocked)
            return "yfinance"

        try:
            with open(self.semaphore_file, "r") as f:
                data = json.load(f)
                provider = data.get("primary_provider", "yfinance")
                if provider not in ["finnhub", "yfinance"]:
                    return "yfinance"
                return provider
        except (json.JSONDecodeError, IOError):
            return "yfinance"

    def switch_provider(self, new_provider: ProviderType):
        """Switch the primary provider and update semaphore file."""
        data = {
            "primary_provider": new_provider,
            "last_switch_time": datetime.now().isoformat(),
            "last_switch_reason": "provider_failure"
        }
        with open(self.semaphore_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"🔄 Switched primary provider to: {new_provider}")


class StockFetcher:
    """Enhanced stock data fetcher with intelligent provider switching."""

    def __init__(self, data_dir: str = "/data"):
        self.finnhub = None
        self.yfinance_fallback = YFINANCE_AVAILABLE
        self.semaphore = ProviderSemaphore(data_dir)

        # Try to initialize Finnhub if available
        if FINNHUB_AVAILABLE and os.getenv("FINNHUB_API_KEY"):
            try:
                self.finnhub = FinnhubFetcher()
            except Exception as e:
                print(f"⚠️  Finnhub unavailable ({e}), using yfinance only")

        if not self.finnhub and not YFINANCE_AVAILABLE:
            raise ValueError("No stock data sources available - need either Finnhub API key or yfinance")

    def _is_network_error(self, exception: Exception) -> bool:
        """Check if exception is a network connection error."""
        error_str = str(exception).lower()
        return (
            isinstance(exception, (NewConnectionError, RequestsConnectionError)) or
            "network is unreachable" in error_str or
            "failed to establish" in error_str or
            "connection" in error_str and "error" in error_str
        )

    def get_stock_info(self, symbol: str) -> dict:
        """Get current stock information with intelligent provider switching."""
        primary_provider = self.semaphore.get_primary_provider()

        # Try primary provider first
        if primary_provider == "finnhub" and self.finnhub:
            try:
                result = self.finnhub.get_stock_info(symbol)
                return result
            except Exception as e:
                if self._is_network_error(e):
                    print(f"⚠️  Finnhub network error for {symbol}, switching to yfinance: {e}")
                    self.semaphore.switch_provider("yfinance")
                else:
                    print(f"⚠️  Finnhub failed for {symbol}, falling back to yfinance: {e}")

        # Try yfinance (either as primary or fallback)
        if self.yfinance_fallback:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info

                # Enhanced yfinance data with basic calculations
                current_price = info.get("currentPrice") or info.get("regularMarketPrice")
                prev_close = info.get("previousClose")

                # Calculate basic daily change
                daily_change = 0
                if current_price and prev_close:
                    daily_change = ((current_price - prev_close) / prev_close) * 100

                result = {
                    "symbol": symbol.upper(),
                    "name": info.get("longName", "N/A"),
                    "current_price": current_price,
                    "previous_close": prev_close,
                    "daily_change_pct": daily_change,
                    "open": info.get("open") or info.get("regularMarketOpen"),
                    "day_high": info.get("dayHigh") or info.get("regularMarketDayHigh"),
                    "day_low": info.get("dayLow") or info.get("regularMarketDayLow"),
                    "volume": info.get("volume") or info.get("regularMarketVolume"),
                    "market_cap": info.get("marketCap"),
                    "pe_ratio": info.get("trailingPE"),
                    "dividend_yield": info.get("dividendYield"),
                    "52_week_high": info.get("fiftyTwoWeekHigh"),
                    "52_week_low": info.get("fiftyTwoWeekLow"),
                    "source": "yfinance"
                }

                # If we were using finnhub as primary and yfinance worked, switch to yfinance
                if primary_provider == "finnhub":
                    self.semaphore.switch_provider("yfinance")

                return result
            except Exception as e:
                # If yfinance fails and we have finnhub, try switching back to finnhub
                if self.finnhub and primary_provider == "yfinance":
                    print(f"⚠️  yfinance failed for {symbol}, switching to finnhub: {e}")
                    self.semaphore.switch_provider("finnhub")
                    # Try finnhub one more time
                    try:
                        return self.finnhub.get_stock_info(symbol)
                    except Exception as finnhub_error:
                        raise ValueError(
                            f"All data sources failed for {symbol}: yfinance={str(e)}, finnhub={str(finnhub_error)}"
                        )
                raise ValueError(f"All data sources failed for {symbol}: {str(e)}")

        raise ValueError(f"No data sources available for {symbol}")

    def get_historical_data(self, symbol: str, period: str = "1mo", interval: str = "1d") -> dict:
        """Get historical data (yfinance only - Finnhub requires different approach)."""

        # Fallback to yfinance
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)

            if hist.empty:
                raise ValueError(f"No historical data found for {symbol}")

            return {
                "symbol": symbol.upper(),
                "period": period,
                "interval": interval,
                "data": hist.to_dict(orient="index"),
                "summary": {
                    "start_date": str(hist.index[0]),
                    "end_date": str(hist.index[-1]),
                    "num_records": len(hist),
                    "avg_volume": float(hist["Volume"].mean()),
                    "price_change": float(hist["Close"].iloc[-1] - hist["Close"].iloc[0]),
                    "price_change_pct": float(
                        ((hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0]) * 100
                    ),
                },
            }
        except Exception as e:
            raise ValueError(f"Failed to fetch historical data for {symbol}: {str(e)}")
