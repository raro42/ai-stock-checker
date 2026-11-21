#!/usr/bin/env python3

from __future__ import annotations

import math
import numbers
from typing import Dict, Optional, List
import requests

from .secret_redact import safe_exc_text
from .technical_indicators import _finite_signed, coerce_nonneg_int


BINANCE_LIMIT_MAX = 1000
BINANCE_ORDERBOOK_LIMIT_MAX = 5000
DEFAULT_KLINES_LIMIT = 24
DEFAULT_KLINES_EXTENDED_LIMIT = 100
DEFAULT_RECENT_TRADES_LIMIT = 100
DEFAULT_AGG_TRADES_LIMIT = 500
DEFAULT_ORDERBOOK_LIMIT = 10
DEFAULT_MIN_VOLUME_USDT = 10_000_000.0
DEFAULT_TRENDING_TOP_N = 20


def _coerce_binance_limit(
    value: object, default: int, *, ceiling: int = BINANCE_LIMIT_MAX
) -> int:
    """Positive Binance strip length, or ``default`` when bool/gap.

    tradermonty #700/#655 + xang1234/portfolio AI: ``int(True)→1`` /
    ``min(True, 1000)→True`` must not invent a one-candle / one-trade strip
    after MarketScanner strip knobs already refused thin publish packaging.
    """
    n = coerce_nonneg_int(value)
    if n is None or n < 1:
        n = int(default)
    return min(n, int(ceiling))


def _coerce_binance_min_volume(
    value: object, default: float = DEFAULT_MIN_VOLUME_USDT
) -> float:
    """Positive USDT volume floor, or ``default`` when bool/gap/≤0.

    tradermonty #700/#655 + xang1234/portfolio AI: ``float(True)→1`` /
    ``False→0`` must not invent a $1 (or cleared) liquidity floor that lets
    junk pairs look liquid after strip limits already refused thin packaging.
    """
    if value is None or not _finite_signed(value):
        return float(default)
    n = float(value)  # type: ignore[arg-type]
    if n <= 0:
        return float(default)
    return n


def _binance_json_float(raw: object) -> Optional[float]:
    """Parse Binance JSON number (Real or numeric str); never ``float(True)→1``.

    tradermonty #700/#655 + xang1234/portfolio AI after StockFetcher/Finnhub
    quote refuse: 24hr ticker fields were still open to raw ``float()``.
    """
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, numbers.Real):
        n = float(raw)
    elif isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            n = float(text)
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(n):
        return None
    return n


def _coerce_binance_mark(raw: object) -> Optional[float]:
    """Finite positive last/high/low mark, else None."""
    n = _binance_json_float(raw)
    if n is None or n <= 0.0:
        return None
    return n


def _coerce_binance_signed_pct(raw: object) -> Optional[float]:
    """Finite signed % change (0 / negative ok), else None."""
    return _binance_json_float(raw)


def _coerce_binance_volume(raw: object) -> Optional[float]:
    """Non-negative volume (zero prints ok), else None."""
    n = _binance_json_float(raw)
    if n is None or n < 0.0:
        return None
    return n


def _ticker_24hr_fields(ticker: dict) -> Optional[Dict]:
    """Coerce one 24hr ticker row; None when lastPrice is unreadable."""
    current_price = _coerce_binance_mark(ticker.get("lastPrice"))
    if current_price is None:
        return None
    return {
        "current_price": current_price,
        "change_24h": _coerce_binance_signed_pct(ticker.get("priceChangePercent")),
        "high_24h": _coerce_binance_mark(ticker.get("highPrice")),
        "low_24h": _coerce_binance_mark(ticker.get("lowPrice")),
        "volume_24h": _coerce_binance_volume(ticker.get("volume")),
        "volume_usdt": _coerce_binance_volume(ticker.get("quoteVolume")),
        "trade_count_24h": coerce_nonneg_int(ticker.get("count")),
        "timestamp": ticker.get("closeTime"),
    }


def _parse_orderbook_level(row: object) -> Optional[List[float]]:
    """One bid/ask [price, qty]; skip bad rows (isolate, do not invent $1).

    tradermonty #830/#332 isolate CSV int conversion + #700/#655 bool refuse:
    raw ``float(True)`` / one bad level must not invent depth or wipe the book.
    """
    if not isinstance(row, (list, tuple)) or len(row) < 2:
        return None
    price = _coerce_binance_mark(row[0])
    qty = _coerce_binance_volume(row[1])
    if price is None or qty is None:
        return None
    return [price, qty]


def _parse_orderbook_side(rows: object, *, take: int) -> List[List[float]]:
    """Keep readable levels only; bad rows isolated (tradermonty #830)."""
    if not isinstance(rows, list):
        return []
    out: List[List[float]] = []
    for row in rows:
        if len(out) >= take:
            break
        level = _parse_orderbook_level(row)
        if level is not None:
            out.append(level)
    return out


def _parse_kline_candle(row: object) -> Optional[Dict]:
    """Basic OHLCV candle; None when any OHLC/volume is unreadable.

    tradermonty #830 isolate conversion + #700/#655: ``float(True)→$1`` /
    ``int(True)→1`` must not invent a candle after ticker marks already refused.
    """
    if not isinstance(row, (list, tuple)) or len(row) < 7:
        return None
    o = _coerce_binance_mark(row[1])
    h = _coerce_binance_mark(row[2])
    lo = _coerce_binance_mark(row[3])
    c = _coerce_binance_mark(row[4])
    vol = _coerce_binance_volume(row[5])
    if None in (o, h, lo, c, vol):
        return None
    return {
        "open_time": row[0],
        "open": o,
        "high": h,
        "low": lo,
        "close": c,
        "volume": vol,
        "close_time": row[6],
    }


def _parse_extended_kline_candle(row: object) -> Optional[Dict]:
    """Extended kline row; skip when core OHLC/volume or extras invent."""
    base = _parse_kline_candle(row)
    if base is None or not isinstance(row, (list, tuple)) or len(row) < 11:
        return None
    quote_vol = _coerce_binance_volume(row[7])
    num_trades = coerce_nonneg_int(row[8])
    taker_base = _coerce_binance_volume(row[9])
    taker_quote = _coerce_binance_volume(row[10])
    if None in (quote_vol, num_trades, taker_base, taker_quote):
        return None
    base.update(
        {
            "quote_volume": quote_vol,
            "num_trades": num_trades,
            "taker_buy_base_volume": taker_base,
            "taker_buy_quote_volume": taker_quote,
        }
    )
    return base


def _parse_recent_trade(row: object) -> Optional[Dict]:
    """One /trades row; None when price/qty invent or maker side is missing.

    tradermonty #830 isolate + #700/#655: ``float(True)→$1`` must not invent
    a print after orderbook/klines already refused — one junk trade must not
    invent buy/sell pressure either.
    """
    if not isinstance(row, dict):
        return None
    price = _coerce_binance_mark(row.get("price"))
    qty = _coerce_binance_volume(row.get("qty"))
    quote_qty = _coerce_binance_volume(row.get("quoteQty"))
    maker = row.get("isBuyerMaker")
    if None in (price, qty, quote_qty) or not isinstance(maker, bool):
        return None
    return {
        "id": row.get("id"),
        "price": price,
        "qty": qty,
        "quote_qty": quote_qty,
        "time": row.get("time"),
        "is_buyer_maker": maker,  # True = sell, False = buy
        "is_buy": not maker,
    }


def _parse_agg_trade(row: object) -> Optional[Dict]:
    """One /aggTrades row; None when price/qty invent or maker side is missing."""
    if not isinstance(row, dict):
        return None
    price = _coerce_binance_mark(row.get("p"))
    qty = _coerce_binance_volume(row.get("q"))
    maker = row.get("m")
    if None in (price, qty) or not isinstance(maker, bool):
        return None
    return {
        "price": price,
        "qty": qty,
        "first_trade_id": row.get("f"),
        "last_trade_id": row.get("l"),
        "time": row.get("T"),
        "is_buyer_maker": maker,
        "is_buy": not maker,
    }


class BinanceFetcher:
    """Fetch real-time crypto data from Binance API (no auth required for market data)."""

    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"
        self.session = requests.Session()

    def get_crypto_price(self, symbol: str) -> Optional[Dict]:
        """
        Get real-time price data from Binance.

        Args:
            symbol: Trading pair like 'BTCUSDT', 'ETHUSDT'

        Returns dict with:
            - current_price: Latest price
            - change_24h: 24-hour price change %
            - high_24h: 24-hour high
            - low_24h: 24-hour low
            - volume_24h: 24-hour trading volume
            - timestamp: Server time
        """
        try:
            # Get 24hr ticker statistics
            ticker_url = f"{self.base_url}/ticker/24hr"
            params = {"symbol": symbol}

            response = self.session.get(ticker_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            fields = _ticker_24hr_fields(data)
            if fields is None:
                return None

            return {
                "symbol": symbol,
                "current_price": fields["current_price"],
                "change_24h": fields["change_24h"],
                "high_24h": fields["high_24h"],
                "low_24h": fields["low_24h"],
                "volume_24h": fields["volume_24h"],
                "timestamp": fields["timestamp"],
                "source": "binance",
            }

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch Binance data for {symbol}: {safe_exc_text(e)}")
            return None

    def get_orderbook_depth(
        self, symbol: str, limit: object = DEFAULT_ORDERBOOK_LIMIT
    ) -> Optional[Dict]:
        """
        Get order book depth (bid/ask levels).

        Args:
            symbol: Trading pair
            limit: Number of levels (5, 10, 20, 50, 100, 500, 1000, 5000)
        """
        # Klines/trades already refuse bool; orderbook depth was still open.
        limit = _coerce_binance_limit(
            limit, DEFAULT_ORDERBOOK_LIMIT, ceiling=BINANCE_ORDERBOOK_LIMIT_MAX
        )
        try:
            depth_url = f"{self.base_url}/depth"
            params = {"symbol": symbol, "limit": limit}

            response = self.session.get(depth_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            bids = _parse_orderbook_side(data.get("bids"), take=5)
            asks = _parse_orderbook_side(data.get("asks"), take=5)
            if not bids or not asks:
                return None

            best_bid = bids[0][0]
            best_ask = asks[0][0]
            spread = best_ask - best_bid
            return {
                "symbol": symbol,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": spread,
                "spread_pct": (spread / best_bid * 100) if best_bid > 0 else None,
                "bids": bids,
                "asks": asks,
                "source": "binance",
            }

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch order book for {symbol}: {safe_exc_text(e)}")
            return None

    def convert_symbol(self, yf_symbol: str) -> str:
        """
        Convert yfinance symbol to Binance format.

        Examples:
            BTC-USD -> BTCUSDT
            ETH-USD -> ETHUSDT
        """
        if "-USD" in yf_symbol:
            base = yf_symbol.replace("-USD", "")
            return f"{base}USDT"
        return yf_symbol


    def get_multiple_prices(self, symbols: list) -> Dict[str, Dict]:
        """
        Get prices for multiple symbols in one API call (more efficient).

        Args:
            symbols: List of Binance symbols like ['BTCUSDT', 'ETHUSDT']
        """
        try:
            ticker_url = f"{self.base_url}/ticker/24hr"

            response = self.session.get(ticker_url, timeout=10)
            response.raise_for_status()
            all_tickers = response.json()

            # Filter for our symbols
            result = {}
            symbol_set = set(symbols)

            for ticker in all_tickers:
                if ticker["symbol"] not in symbol_set:
                    continue
                fields = _ticker_24hr_fields(ticker)
                if fields is None:
                    continue
                result[ticker["symbol"]] = {
                    "current_price": fields["current_price"],
                    "change_24h": fields["change_24h"],
                    "high_24h": fields["high_24h"],
                    "low_24h": fields["low_24h"],
                    "volume_24h": fields["volume_24h"],
                    "timestamp": fields["timestamp"],
                    "source": "binance",
                }

            return result

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch multiple prices: {safe_exc_text(e)}")
            return {}

    def get_all_tickers(
        self, min_volume_usdt: float = DEFAULT_MIN_VOLUME_USDT
    ) -> Dict[str, Dict]:
        """
        Get ALL trading pairs on Binance (discover new movers beyond our watchlist).

        Args:
            min_volume_usdt: Minimum 24h volume in USDT to filter out low-liquidity coins

        Returns:
            Dict of symbol -> price data, sorted by 24h % change descending
        """
        min_volume_usdt = _coerce_binance_min_volume(
            min_volume_usdt, DEFAULT_MIN_VOLUME_USDT
        )
        try:
            ticker_url = f"{self.base_url}/ticker/24hr"

            print(f"   🌐  GET {ticker_url} (all symbols)")

            response = self.session.get(ticker_url, timeout=15)
            response.raise_for_status()
            all_tickers = response.json()

            # Filter for USDT pairs with sufficient volume
            result = {}
            for ticker in all_tickers:
                symbol = ticker["symbol"]

                # Only USDT pairs
                if not symbol.endswith("USDT"):
                    continue

                fields = _ticker_24hr_fields(ticker)
                if fields is None:
                    continue
                volume_usdt = fields["volume_usdt"]
                if volume_usdt is None or volume_usdt < min_volume_usdt:
                    continue

                result[symbol] = {
                    "current_price": fields["current_price"],
                    "change_24h": fields["change_24h"],
                    "high_24h": fields["high_24h"],
                    "low_24h": fields["low_24h"],
                    "volume_24h": fields["volume_24h"],
                    "volume_usdt": volume_usdt,
                    # Number of trades (proxy for activity/visits)
                    "trade_count_24h": fields["trade_count_24h"] or 0,
                    "timestamp": fields["timestamp"],
                    "source": "binance",
                }

            return result

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch all tickers: {safe_exc_text(e)}")
            return {}

    def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: object = DEFAULT_KLINES_LIMIT,
    ) -> Optional[list]:
        """
        Get candlestick/kline data for trend analysis.

        Args:
            symbol: Trading pair like 'BTCUSDT'
            interval: 1m, 5m, 15m, 1h, 4h, 1d, 1w
            limit: Number of candles (max 1000)

        Returns:
            List of candles, each containing:
            [open_time, open, high, low, close, volume, close_time, ...]
        """
        limit = _coerce_binance_limit(limit, DEFAULT_KLINES_LIMIT)
        try:
            klines_url = f"{self.base_url}/klines"
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }

            print(f"   🌐  GET {klines_url}?symbol={symbol}&interval={interval}&limit={limit}")

            response = self.session.get(klines_url, params=params, timeout=10)
            response.raise_for_status()
            klines = response.json()

            # Isolate bad bars (tradermonty #830); never invent float(True)→$1.
            candles = []
            for k in klines:
                candle = _parse_kline_candle(k)
                if candle is not None:
                    candles.append(candle)

            return candles

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch klines for {symbol}: {safe_exc_text(e)}")
            return None

    def analyze_breakout(self, symbol: str) -> Optional[Dict]:
        """
        Analyze if a coin is experiencing a real breakout or just noise.

        Uses 24h candles to detect:
        - Higher highs (bullish)
        - Increasing volume (confirmation)
        - Above recent resistance

        Returns:
            Dict with breakout_score (0-100) and analysis
        """
        try:
            # Get 7 days of daily candles
            klines = self.get_klines(symbol, interval="1d", limit=7)
            if not klines or len(klines) < 7:
                return None

            # Current candle
            current = klines[-1]
            prev_candles = klines[:-1]

            # Calculate metrics
            avg_volume = sum(c["volume"] for c in prev_candles) / len(prev_candles)
            volume_surge = (current["volume"] / avg_volume - 1) * 100 if avg_volume > 0 else 0

            # Check for higher highs
            prev_high = max(c["high"] for c in prev_candles)
            is_higher_high = current["high"] > prev_high

            # Calculate breakout score
            score = 0
            if is_higher_high:
                score += 40
            if volume_surge > 50:  # 50% above average
                score += 30
            if volume_surge > 100:  # 2x average
                score += 15
            if current["close"] > current["open"]:  # Bullish candle
                score += 15

            return {
                "symbol": symbol,
                "breakout_score": min(score, 100),
                "is_higher_high": is_higher_high,
                "volume_surge_pct": volume_surge,
                "current_price": current["close"],
                "prev_high": prev_high,
                "breakout_pct": ((current["high"] - prev_high) / prev_high * 100) if is_higher_high else 0
            }

        except Exception as e:
            print(f"[ERROR] Breakout analysis failed for {symbol}: {safe_exc_text(e)}")
            return None

    def check_liquidity(self, symbol: str) -> Optional[Dict]:
        """
        Check order book liquidity for safe entry/exit.

        Returns:
            Dict with spread, bid/ask depth, and liquidity score
        """
        try:
            depth_url = f"{self.base_url}/depth"
            params = {"symbol": symbol, "limit": 20}

            print(f"   🌐  GET {depth_url}?symbol={symbol}&limit=20")

            response = self.session.get(depth_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            bids = _parse_orderbook_side(data.get("bids"), take=10)
            asks = _parse_orderbook_side(data.get("asks"), take=10)

            if not bids or not asks:
                return None

            best_bid = bids[0][0]
            best_ask = asks[0][0]
            spread_pct = ((best_ask - best_bid) / best_bid * 100)

            # Calculate depth (total volume in top 5 levels)
            bid_depth = sum(qty for _, qty in bids[:5])
            ask_depth = sum(qty for _, qty in asks[:5])

            # Liquidity score (0-100)
            liquidity_score = 100
            if spread_pct > 0.5:
                liquidity_score -= 30  # Wide spread = poor liquidity
            if spread_pct > 1.0:
                liquidity_score -= 30  # Very wide = avoid

            # Check depth imbalance
            if bid_depth > 0 and ask_depth > 0:
                imbalance = abs(bid_depth - ask_depth) / (bid_depth + ask_depth)
                if imbalance > 0.5:
                    liquidity_score -= 20  # Imbalanced book

            return {
                "symbol": symbol,
                "spread_pct": spread_pct,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "bid_depth": bid_depth,
                "ask_depth": ask_depth,
                "liquidity_score": max(liquidity_score, 0),
                "tradeable": spread_pct < 0.5 and liquidity_score >= 50
            }

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to check liquidity for {symbol}: {safe_exc_text(e)}")
            return None

    def get_technical_indicators(self, symbol: str) -> Optional[Dict]:
        """
        Calculate technical indicators for a crypto symbol.
        
        Calculates RSI and MACD. Uses 1h candles with 50+ candles for accuracy.
        
        Args:
            symbol: Trading pair like 'BTCUSDT', 'ETHUSDT'
            
        Returns:
            Dict with 'rsi' and 'macd' values, or None if insufficient data or error
        """
        try:
            # Fetch klines data (1h interval, 50 candles minimum for RSI and MACD)
            klines = self.get_klines(symbol, interval="1h", limit=50)
            if not klines or len(klines) < 35:  # Need at least 35 for MACD (slow_period 26 + signal 9)
                return None
            
            # Extract closing prices
            closing_prices = [candle["close"] for candle in klines]
            
            # Import TechnicalIndicators
            from .technical_indicators import TechnicalIndicators
            
            result = {}
            
            # Calculate RSI
            rsi = TechnicalIndicators.calculate_rsi(closing_prices, period=14)
            if rsi is not None:
                result["rsi"] = rsi
            
            # Calculate MACD
            macd = TechnicalIndicators.calculate_macd(closing_prices)
            if macd is not None:
                result["macd"] = macd
            
            # Return None if no indicators calculated
            if not result:
                return None
            
            return result
            
        except Exception as e:
            print(f"[ERROR] Failed to calculate technical indicators for {symbol}: {safe_exc_text(e)}")
            return None

    def get_klines_extended(
        self,
        symbol: str,
        interval: str = "1h",
        limit: object = DEFAULT_KLINES_EXTENDED_LIMIT,
    ) -> Optional[list]:
        """
        Get extended klines data with additional information.
        
        Extended klines include:
        - All standard OHLCV data
        - Quote volume (volume in quote currency)
        - Number of trades
        - Taker buy base/quote volume (buy vs sell pressure)
        
        Args:
            symbol: Trading pair like 'BTCUSDT'
            interval: 1m, 5m, 15m, 1h, 4h, 1d, 1w
            limit: Number of candles (max 1000)
            
        Returns:
            List of extended candles with additional data
        """
        limit = _coerce_binance_limit(limit, DEFAULT_KLINES_EXTENDED_LIMIT)
        try:
            klines_url = f"{self.base_url}/klines"
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }

            print(f"   🌐  GET {klines_url}?symbol={symbol}&interval={interval}&limit={limit} (extended)")

            response = self.session.get(klines_url, params=params, timeout=10)
            response.raise_for_status()
            klines = response.json()

            # Isolate bad bars; refuse bool OHLC / int(True) trade counts.
            candles = []
            for k in klines:
                candle = _parse_extended_kline_candle(k)
                if candle is not None:
                    candles.append(candle)

            return candles

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch extended klines for {symbol}: {safe_exc_text(e)}")
            return None

    def get_recent_trades(
        self, symbol: str, limit: object = DEFAULT_RECENT_TRADES_LIMIT
    ) -> Optional[list]:
        """
        Get recent trades for a symbol.
        
        Useful for:
        - Analyzing buy/sell pressure
        - Detecting unusual trading activity
        - Understanding market sentiment
        
        Args:
            symbol: Trading pair like 'BTCUSDT'
            limit: Number of recent trades (default 100, max 1000)
            
        Returns:
            List of recent trades, each containing:
            - id: Trade ID
            - price: Trade price
            - qty: Trade quantity
            - quote_qty: Trade value in quote currency
            - time: Trade timestamp
            - is_buyer_maker: True if buyer is maker (sell), False if buyer is taker (buy)
        """
        limit = _coerce_binance_limit(limit, DEFAULT_RECENT_TRADES_LIMIT)
        try:
            trades_url = f"{self.base_url}/trades"
            params = {
                "symbol": symbol,
                "limit": limit,
            }

            print(f"   🌐  GET {trades_url}?symbol={symbol}&limit={params['limit']}")

            response = self.session.get(trades_url, params=params, timeout=10)
            response.raise_for_status()
            trades = response.json()
            if not isinstance(trades, list):
                return None

            # Isolate bad prints; never invent float(True)→$1 pressure.
            parsed_trades = []
            for trade in trades:
                parsed = _parse_recent_trade(trade)
                if parsed is not None:
                    parsed_trades.append(parsed)

            return parsed_trades

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch recent trades for {symbol}: {safe_exc_text(e)}")
            return None

    def get_agg_trades(
        self, symbol: str, limit: object = DEFAULT_AGG_TRADES_LIMIT
    ) -> Optional[list]:
        """
        Get aggregated trades (compressed trade data).
        
        More efficient than get_recent_trades for large volumes.
        Aggregates trades at the same price within the same second.
        
        Args:
            symbol: Trading pair like 'BTCUSDT'
            limit: Number of aggregated trades (default 500, max 1000)
            
        Returns:
            List of aggregated trades with:
            - price: Trade price
            - qty: Total quantity
            - first_trade_id: First trade ID in aggregation
            - last_trade_id: Last trade ID in aggregation
            - time: Timestamp
            - is_buyer_maker: True if buyer is maker
        """
        limit = _coerce_binance_limit(limit, DEFAULT_AGG_TRADES_LIMIT)
        try:
            agg_trades_url = f"{self.base_url}/aggTrades"
            params = {
                "symbol": symbol,
                "limit": limit,
            }

            print(f"   🌐  GET {agg_trades_url}?symbol={symbol}&limit={params['limit']}")

            response = self.session.get(agg_trades_url, params=params, timeout=10)
            response.raise_for_status()
            agg_trades = response.json()
            if not isinstance(agg_trades, list):
                return None

            # Isolate bad prints; never invent float(True)→$1 aggregates.
            parsed_trades = []
            for trade in agg_trades:
                parsed = _parse_agg_trade(trade)
                if parsed is not None:
                    parsed_trades.append(parsed)

            return parsed_trades

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch aggregated trades for {symbol}: {safe_exc_text(e)}")
            return None

    def analyze_buy_sell_pressure(
        self, symbol: str, limit: object = DEFAULT_RECENT_TRADES_LIMIT
    ) -> Optional[Dict]:
        """
        Analyze buy vs sell pressure from recent trades.
        
        Uses recent trades to determine if buyers or sellers are more active.
        
        Args:
            symbol: Trading pair like 'BTCUSDT'
            limit: Number of recent trades to analyze (default 100)
            
        Returns:
            Dict with:
            - buy_volume: Total buy volume
            - sell_volume: Total sell volume
            - buy_ratio: Buy volume / total volume (0-1, >0.5 = bullish)
            - buy_count: Number of buy trades
            - sell_count: Number of sell trades
            - pressure_score: -100 to +100 (positive = bullish)
        """
        try:
            trades = self.get_recent_trades(symbol, limit=limit)
            if not trades or len(trades) < 10:
                return None
            
            buy_volume = sum(t['quote_qty'] for t in trades if t['is_buy'])
            sell_volume = sum(t['quote_qty'] for t in trades if not t['is_buy'])
            total_volume = buy_volume + sell_volume
            
            if total_volume == 0:
                return None
            
            buy_count = sum(1 for t in trades if t['is_buy'])
            sell_count = len(trades) - buy_count
            
            buy_ratio = buy_volume / total_volume
            
            # Pressure score: -100 (all sell) to +100 (all buy)
            pressure_score = (buy_ratio - 0.5) * 200
            
            return {
                "buy_volume": buy_volume,
                "sell_volume": sell_volume,
                "buy_ratio": buy_ratio,
                "buy_count": buy_count,
                "sell_count": sell_count,
                "pressure_score": pressure_score,
                "total_trades": len(trades)
            }
            
        except Exception as e:
            print(f"[ERROR] Failed to analyze buy/sell pressure for {symbol}: {safe_exc_text(e)}")
            return None

    def get_trending_coins(
        self,
        min_volume_usdt: float = DEFAULT_MIN_VOLUME_USDT,
        top_n: int = DEFAULT_TRENDING_TOP_N,
    ) -> List[Dict]:
        """
        Get trending/most active coins based on multiple factors.
        
        Similar to Binance's "most visited" page, this identifies coins with:
        - High trading activity (number of trades)
        - High volume
        - Significant price movement
        
        Args:
            min_volume_usdt: Minimum 24h volume in USDT
            top_n: Number of trending coins to return
            
        Returns:
            List of trending coins sorted by trending score, each containing:
            - symbol: Trading pair
            - trending_score: Combined score (0-100)
            - trade_count_24h: Number of trades (activity indicator)
            - volume_usdt: Trading volume
            - change_24h: Price change %
            - current_price: Current price
        """
        min_volume_usdt = _coerce_binance_min_volume(
            min_volume_usdt, DEFAULT_MIN_VOLUME_USDT
        )
        top_n = _coerce_binance_limit(top_n, DEFAULT_TRENDING_TOP_N)
        try:
            ticker_url = f"{self.base_url}/ticker/24hr"
            
            print(f"   🌐  GET {ticker_url} (trending analysis)")
            
            response = self.session.get(ticker_url, timeout=15)
            response.raise_for_status()
            all_tickers = response.json()
            
            trending = []

            for ticker in all_tickers:
                symbol = ticker["symbol"]

                # Only USDT pairs
                if not symbol.endswith("USDT"):
                    continue

                fields = _ticker_24hr_fields(ticker)
                if fields is None:
                    continue
                volume_usdt = fields["volume_usdt"]
                change_24h = fields["change_24h"]
                trade_count = fields["trade_count_24h"]
                if (
                    volume_usdt is None
                    or volume_usdt < min_volume_usdt
                    or change_24h is None
                    or trade_count is None
                ):
                    continue

                # Calculate trending score (0-100)
                # Factors:
                # - Trade count (activity/visits): 40% weight
                # - Volume: 30% weight
                # - Price change: 30% weight

                # Normalize trade count (assume max ~5M trades for top coins)
                trade_score = min((trade_count / 5000000) * 40, 40)

                # Normalize volume (assume max ~$1B for top coins)
                volume_score = min((volume_usdt / 1000000000) * 30, 30)

                # Price change score (absolute value, capped at 30)
                change_score = min(abs(change_24h) * 0.6, 30)

                trending_score = trade_score + volume_score + change_score

                trending.append({
                    "symbol": symbol,
                    "yf_symbol": symbol.replace("USDT", "-USD"),
                    "trending_score": trending_score,
                    "trade_count_24h": trade_count,
                    "volume_usdt": volume_usdt,
                    "change_24h": change_24h,
                    "current_price": fields["current_price"],
                    "high_24h": fields["high_24h"],
                    "low_24h": fields["low_24h"],
                })

            # Sort by trending score (highest first)
            trending.sort(key=lambda x: x["trending_score"], reverse=True)

            return trending[:top_n]
            
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch trending coins: {safe_exc_text(e)}")
            return []
