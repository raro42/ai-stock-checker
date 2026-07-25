#!/usr/bin/env python3

from typing import Dict, Optional, List
import requests


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

            return {
                "symbol": symbol,
                "current_price": float(data["lastPrice"]),
                "change_24h": float(data["priceChangePercent"]),
                "high_24h": float(data["highPrice"]),
                "low_24h": float(data["lowPrice"]),
                "volume_24h": float(data["volume"]),
                "timestamp": data["closeTime"],
                "source": "binance"
            }

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch Binance data for {symbol}: {str(e)}")
            return None

    def get_orderbook_depth(self, symbol: str, limit: int = 10) -> Optional[Dict]:
        """
        Get order book depth (bid/ask levels).

        Args:
            symbol: Trading pair
            limit: Number of levels (5, 10, 20, 50, 100, 500, 1000, 5000)
        """
        try:
            depth_url = f"{self.base_url}/depth"
            params = {"symbol": symbol, "limit": limit}

            response = self.session.get(depth_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            bids = [[float(price), float(qty)] for price, qty in data["bids"][:5]]
            asks = [[float(price), float(qty)] for price, qty in data["asks"][:5]]

            return {
                "symbol": symbol,
                "best_bid": bids[0][0] if bids else 0,
                "best_ask": asks[0][0] if asks else 0,
                "spread": (asks[0][0] - bids[0][0]) if bids and asks else 0,
                "spread_pct": ((asks[0][0] - bids[0][0]) / bids[0][0] * 100) if bids and asks else 0,
                "bids": bids,
                "asks": asks,
                "source": "binance"
            }

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch order book for {symbol}: {str(e)}")
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
                if ticker["symbol"] in symbol_set:
                    result[ticker["symbol"]] = {
                        "current_price": float(ticker["lastPrice"]),
                        "change_24h": float(ticker["priceChangePercent"]),
                        "high_24h": float(ticker["highPrice"]),
                        "low_24h": float(ticker["lowPrice"]),
                        "volume_24h": float(ticker["volume"]),
                        "timestamp": ticker["closeTime"],
                        "source": "binance"
                    }

            return result

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch multiple prices: {str(e)}")
            return {}

    def get_all_tickers(self, min_volume_usdt: float = 10000000) -> Dict[str, Dict]:
        """
        Get ALL trading pairs on Binance (discover new movers beyond our watchlist).

        Args:
            min_volume_usdt: Minimum 24h volume in USDT to filter out low-liquidity coins

        Returns:
            Dict of symbol -> price data, sorted by 24h % change descending
        """
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

                volume_usdt = float(ticker["quoteVolume"])

                # Filter low-liquidity coins
                if volume_usdt < min_volume_usdt:
                    continue

                result[symbol] = {
                    "current_price": float(ticker["lastPrice"]),
                    "change_24h": float(ticker["priceChangePercent"]),
                    "high_24h": float(ticker["highPrice"]),
                    "low_24h": float(ticker["lowPrice"]),
                    "volume_24h": float(ticker["volume"]),
                    "volume_usdt": volume_usdt,
                    "trade_count_24h": int(ticker.get("count", 0)),  # Number of trades (proxy for activity/visits)
                    "timestamp": ticker["closeTime"],
                    "source": "binance"
                }

            return result

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch all tickers: {str(e)}")
            return {}

    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 24) -> Optional[list]:
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

            # Parse to useful format
            candles = []
            for k in klines:
                candles.append({
                    "open_time": k[0],
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "close_time": k[6]
                })

            return candles

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch klines for {symbol}: {str(e)}")
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
            print(f"[ERROR] Breakout analysis failed for {symbol}: {str(e)}")
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

            bids = [[float(price), float(qty)] for price, qty in data["bids"][:10]]
            asks = [[float(price), float(qty)] for price, qty in data["asks"][:10]]

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
            print(f"[ERROR] Failed to check liquidity for {symbol}: {str(e)}")
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
            print(f"[ERROR] Failed to calculate technical indicators for {symbol}: {str(e)}")
            return None

    def get_klines_extended(self, symbol: str, interval: str = "1h", limit: int = 100) -> Optional[list]:
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

            # Parse to extended format with all available data
            candles = []
            for k in klines:
                candles.append({
                    "open_time": k[0],
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),  # Base asset volume
                    "close_time": k[6],
                    "quote_volume": float(k[7]),  # Quote asset volume (USDT)
                    "num_trades": int(k[8]),  # Number of trades
                    "taker_buy_base_volume": float(k[9]),  # Taker buy base volume
                    "taker_buy_quote_volume": float(k[10]),  # Taker buy quote volume
                })

            return candles

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch extended klines for {symbol}: {str(e)}")
            return None

    def get_recent_trades(self, symbol: str, limit: int = 100) -> Optional[list]:
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
        try:
            trades_url = f"{self.base_url}/trades"
            params = {
                "symbol": symbol,
                "limit": min(limit, 1000)  # Binance max is 1000
            }

            print(f"   🌐  GET {trades_url}?symbol={symbol}&limit={params['limit']}")

            response = self.session.get(trades_url, params=params, timeout=10)
            response.raise_for_status()
            trades = response.json()

            # Parse to useful format
            parsed_trades = []
            for trade in trades:
                parsed_trades.append({
                    "id": trade["id"],
                    "price": float(trade["price"]),
                    "qty": float(trade["qty"]),
                    "quote_qty": float(trade["quoteQty"]),
                    "time": trade["time"],
                    "is_buyer_maker": trade["isBuyerMaker"],  # True = sell, False = buy
                    "is_buy": not trade["isBuyerMaker"]  # Convenience field
                })

            return parsed_trades

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch recent trades for {symbol}: {str(e)}")
            return None

    def get_agg_trades(self, symbol: str, limit: int = 500) -> Optional[list]:
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
        try:
            agg_trades_url = f"{self.base_url}/aggTrades"
            params = {
                "symbol": symbol,
                "limit": min(limit, 1000)  # Binance max is 1000
            }

            print(f"   🌐  GET {agg_trades_url}?symbol={symbol}&limit={params['limit']}")

            response = self.session.get(agg_trades_url, params=params, timeout=10)
            response.raise_for_status()
            agg_trades = response.json()

            # Parse to useful format
            parsed_trades = []
            for trade in agg_trades:
                parsed_trades.append({
                    "price": float(trade["p"]),
                    "qty": float(trade["q"]),
                    "first_trade_id": trade["f"],
                    "last_trade_id": trade["l"],
                    "time": trade["T"],
                    "is_buyer_maker": trade["m"],  # True = sell, False = buy
                    "is_buy": not trade["m"]  # Convenience field
                })

            return parsed_trades

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch aggregated trades for {symbol}: {str(e)}")
            return None

    def analyze_buy_sell_pressure(self, symbol: str, limit: int = 100) -> Optional[Dict]:
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
            print(f"[ERROR] Failed to analyze buy/sell pressure for {symbol}: {str(e)}")
            return None

    def get_trending_coins(self, min_volume_usdt: float = 10000000, top_n: int = 20) -> List[Dict]:
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
                
                volume_usdt = float(ticker["quoteVolume"])
                trade_count = int(ticker.get("count", 0))
                change_24h = float(ticker["priceChangePercent"])
                
                # Filter low-liquidity coins
                if volume_usdt < min_volume_usdt:
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
                    "yf_symbol": symbol.replace('USDT', '-USD'),
                    "trending_score": trending_score,
                    "trade_count_24h": trade_count,
                    "volume_usdt": volume_usdt,
                    "change_24h": change_24h,
                    "current_price": float(ticker["lastPrice"]),
                    "high_24h": float(ticker["highPrice"]),
                    "low_24h": float(ticker["lowPrice"]),
                })
            
            # Sort by trending score (highest first)
            trending.sort(key=lambda x: x['trending_score'], reverse=True)
            
            return trending[:top_n]
            
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch trending coins: {str(e)}")
            return []
