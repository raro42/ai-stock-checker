#!/usr/bin/env python3

from __future__ import annotations

from typing import Literal, Optional
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

from .secret_redact import safe_exc_text
from .technical_indicators import (
    _finite_signed,
    _valid_close,
    _valid_volume,
    daily_pct_change,
)


def _first_valid_close(*candidates: object) -> Optional[float]:
    """First finite positive mark, else None (never keep ``True`` via ``or``)."""
    for raw in candidates:
        if _valid_close(raw):
            return float(raw)  # type: ignore[arg-type]
    return None


def _first_valid_volume(*candidates: object) -> Optional[float]:
    """First non-negative volume, else None (never ``True→1`` via ``or``)."""
    for raw in candidates:
        if _valid_volume(raw):
            return float(raw)  # type: ignore[arg-type]
    return None


def _coerce_signed_metric(raw: object) -> Optional[float]:
    """Finite metric (PE / yield / cap), else None — never ``float(True)``."""
    if raw is None or not _finite_signed(raw):
        return None
    return float(raw)  # type: ignore[arg-type]

ProviderType = Literal["finnhub", "yfinance"]


def is_transient_network_error(exception: Exception) -> bool:
    """True for DNS blips, connection drops, and similar retryable fetch failures."""
    error_str = str(exception).lower()
    markers = (
        "could not resolve host",
        "failed to resolve",
        "name or service not known",
        "temporary failure in name resolution",
        "nodename nor servname provided",
        "network is unreachable",
        "failed to establish",
        "max retries exceeded",
        "curl: (6)",
        "curl: (7)",
        "connection reset",
        "connection refused",
        "timed out",
        "timeout",
    )
    if any(m in error_str for m in markers):
        return True
    if isinstance(exception, (NewConnectionError, RequestsConnectionError)):
        return True
    # Loose match for urllib3/requests pool errors (e.g. HTTPSConnectionPool + NameResolutionError)
    if "connection" in error_str and "error" in error_str:
        return True
    return False


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
            with open(self.semaphore_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                provider = data.get("primary_provider", "yfinance")
                if provider not in ["finnhub", "yfinance"]:
                    return "yfinance"
                return provider
        except (json.JSONDecodeError, IOError, UnicodeDecodeError):
            return "yfinance"

    def switch_provider(self, new_provider: ProviderType):
        """Switch the primary provider and update semaphore file."""
        data = {
            "primary_provider": new_provider,
            "last_switch_time": datetime.now().isoformat(),
            "last_switch_reason": "provider_failure"
        }
        with open(self.semaphore_file, "w", encoding="utf-8") as f:
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
                print(f"⚠️  Finnhub unavailable ({safe_exc_text(e)}), using yfinance only")

        if not self.finnhub and not YFINANCE_AVAILABLE:
            raise ValueError("No stock data sources available - need either Finnhub API key or yfinance")

    def _is_network_error(self, exception: Exception) -> bool:
        """Check if exception is a network connection error."""
        return is_transient_network_error(exception)

    def get_stock_info(self, symbol: str) -> dict:
        """Get current stock information with intelligent provider switching."""
        primary_provider = self.semaphore.get_primary_provider()

        # Try primary provider first
        if primary_provider == "finnhub" and self.finnhub:
            try:
                result = self.finnhub.get_stock_info(symbol)
                return result
            except Exception as e:
                detail = safe_exc_text(e)
                if self._is_network_error(e):
                    print(
                        f"⚠️  Finnhub network error for {symbol}, "
                        f"switching to yfinance: {detail}"
                    )
                    self.semaphore.switch_provider("yfinance")
                else:
                    print(
                        f"⚠️  Finnhub failed for {symbol}, "
                        f"falling back to yfinance: {detail}"
                    )

        # Try yfinance (either as primary or fallback)
        if self.yfinance_fallback:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info

                # tradermonty #700/#655 + xang1234/portfolio AI: never keep
                # ``True`` via ``a or b`` (truthy bool short-circuits) or pass
                # bool/gap marks through for callers to ``float(True)→$1``.
                current_price = _first_valid_close(
                    info.get("currentPrice"),
                    info.get("regularMarketPrice"),
                )
                prev_close = _first_valid_close(info.get("previousClose"))
                daily_change = daily_pct_change(current_price, prev_close)

                result = {
                    "symbol": symbol.upper(),
                    "name": info.get("longName", "N/A"),
                    "current_price": current_price,
                    "previous_close": prev_close,
                    "daily_change_pct": daily_change,
                    "open": _first_valid_close(
                        info.get("open"), info.get("regularMarketOpen")
                    ),
                    "day_high": _first_valid_close(
                        info.get("dayHigh"), info.get("regularMarketDayHigh")
                    ),
                    "day_low": _first_valid_close(
                        info.get("dayLow"), info.get("regularMarketDayLow")
                    ),
                    "volume": _first_valid_volume(
                        info.get("volume"), info.get("regularMarketVolume")
                    ),
                    "market_cap": _coerce_signed_metric(info.get("marketCap")),
                    "pe_ratio": _coerce_signed_metric(info.get("trailingPE")),
                    "dividend_yield": _coerce_signed_metric(
                        info.get("dividendYield")
                    ),
                    "52_week_high": _first_valid_close(
                        info.get("fiftyTwoWeekHigh")
                    ),
                    "52_week_low": _first_valid_close(
                        info.get("fiftyTwoWeekLow")
                    ),
                    "source": "yfinance"
                }

                # If we were using finnhub as primary and yfinance worked, switch to yfinance
                if primary_provider == "finnhub":
                    self.semaphore.switch_provider("yfinance")

                return result
            except Exception as e:
                # If yfinance fails and we have finnhub, try switching back to finnhub
                if self.finnhub and primary_provider == "yfinance":
                    print(
                        f"⚠️  yfinance failed for {symbol}, "
                        f"switching to finnhub: {safe_exc_text(e)}"
                    )
                    self.semaphore.switch_provider("finnhub")
                    # Try finnhub one more time
                    try:
                        return self.finnhub.get_stock_info(symbol)
                    except Exception as finnhub_error:
                        raise ValueError(
                            f"All data sources failed for {symbol}: "
                            f"yfinance={safe_exc_text(e)}, "
                            f"finnhub={safe_exc_text(finnhub_error)}"
                        ) from finnhub_error
                raise ValueError(
                    f"All data sources failed for {symbol}: {safe_exc_text(e)}"
                ) from e

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
            # tradermonty #778: never echo raw provider URLs / token= in raises.
            raise ValueError(
                f"Failed to fetch historical data for {symbol}: {safe_exc_text(e)}"
            ) from e
