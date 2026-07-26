#!/usr/bin/env python3

"""
Intelligent trader that continuously scans markets and auto-rebalances portfolio.

This combines market scanning with paper trading to:
1. Scan markets every 5 minutes for top opportunities
2. Compare current holdings against best opportunities
3. Rebalance portfolio if better opportunities emerge
4. Monitor existing positions with profit-taking and stop-loss
"""

from typing import List, Dict
import time
import traceback
from datetime import datetime
from .market_scanner import MarketScanner
from .portfolio import Portfolio
from .persistence import DataPersistence
from .symbol_filters import is_tradeable_symbol
from .earnings_guard import is_in_earnings_blackout
from . import __version__


class IntelligentTrader:
    """
    Autonomous trading system with continuous market analysis.
    """

    def __init__(
        self,
        initial_cash: float = 10000.0,
        scan_interval: int = 900,  # 15 minutes
        trade_interval: int = 300,  # 5 minutes
        max_positions: int = 8,
        position_size: float = 0.10,  # 10% per position
        rebalance_threshold: float = 0.15,  # 15% score difference to trigger rebalance
        min_hold_time: int = 14400,  # 4 hours minimum hold (anti-churn)
        ai_mode: str = "off",  # off, validate, full
        ai_model: str = "gemma4:latest",
        top_crypto_count: int = 2
    ):
        self.scanner = MarketScanner(top_crypto_count=top_crypto_count)
        self.persistence = DataPersistence()
        self.portfolio = Portfolio(initial_cash, commission_rate=0.001, persistence=self.persistence)

        self.scan_interval = scan_interval
        self.trade_interval = trade_interval
        self.max_positions = max_positions
        self.position_size = position_size
        self.rebalance_threshold = rebalance_threshold
        self.min_hold_time = min_hold_time

        # AI configuration
        self.ai_mode = ai_mode
        self.ai_model = ai_model
        if ai_mode != "off":
            from .ai_recommender import AIRecommender
            self.ai_recommender = AIRecommender(model=ai_model)
        else:
            self.ai_recommender = None

        self.last_scan_time = 0
        self.current_opportunities = []

        # Load position entry times from disk (survives restarts)
        self.position_entry_times = self.persistence.load_entry_times()
        if self.position_entry_times:
            print(f"   Loaded {len(self.position_entry_times)} position entry times from disk")

        print(f"🤖 Intelligent Trader initialized")
        print(f"   Capital: €{initial_cash:,.2f}")
        print(f"   Max positions: {max_positions}")
        print(f"   Position size: {position_size*100}%")
        print(f"   Scan interval: {scan_interval}s")
        print(f"   Trade interval: {trade_interval}s")
        print(f"   Rebalance threshold: {rebalance_threshold*100}%")
        print(f"   Min hold time: {min_hold_time}s")
        print(f"   AI Mode: {ai_mode}")
        if ai_mode != "off":
            print(f"   AI Model: {ai_model}")
        from stock_checker.fee_burn import maybe_print_fee_burn_warning

        maybe_print_fee_burn_warning(str(self.persistence.data_dir))

    def should_scan(self) -> bool:
        """Check if it's time for a new market scan."""
        return (time.time() - self.last_scan_time) >= self.scan_interval

    def scan_markets(self) -> List[Dict]:
        """
        Run comprehensive market scan and return ranked opportunities.
        """
        print(f"\n{'='*70}")
        print(f"🔍  SCANNING MARKETS - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*70}")

        results = self.scanner.identify_best_opportunities()

        opportunities = results['recommendations']

        # AI Validation if enabled
        if self.ai_mode != "off" and self.ai_recommender and opportunities:
            print(f"\n{'#'*70}")
            print(f"🤖 AI VALIDATION - {self.ai_mode.upper()} MODE")
            print(f"   Model: {self.ai_model}")
            print(f"{'#'*70}\n")

            opportunities = self._ai_validate_opportunities(opportunities)

        self.current_opportunities = opportunities
        self.last_scan_time = time.time()

        return self.current_opportunities

    def _ai_validate_opportunities(self, opportunities: List[Dict]) -> List[Dict]:
        """
        Use AI to validate trading opportunities.

        In 'validate' mode: Only validate top opportunities
        In 'full' mode: Get AI recommendations for all
        """
        from .fetcher import StockFetcher
        from .binance_fetcher import BinanceFetcher
        import sys

        try:
            import yfinance as yf
            yfinance_available = True
        except ImportError:
            yfinance_available = False
            print("   ⚠️  yfinance not available - P/E and volume data may be limited")
            sys.stdout.flush()

        fetcher = StockFetcher()
        binance = BinanceFetcher()
        validated_opportunities = []

        # Limit validation to top N opportunities to save AI calls
        max_to_validate = 5 if self.ai_mode == "validate" else 10
        opportunities_to_check = opportunities[:max_to_validate]

        print(f"   Validating top {len(opportunities_to_check)} opportunities with AI...")
        sys.stdout.flush()

        for i, opp in enumerate(opportunities_to_check, 1):
            symbol = opp['symbol']
            strategy = opp.get('strategy', 'unknown')

            print(f"\n   [{i}/{len(opportunities_to_check)}] Analyzing {symbol} ({strategy})...")
            sys.stdout.flush()

            try:
                # Fetch detailed data for AI analysis
                is_crypto = "-USD" in symbol

                if is_crypto:
                    binance_symbol = binance.convert_symbol(symbol)
                    crypto_data = binance.get_crypto_price(binance_symbol)
                    if not crypto_data:
                        print(f"   ⚠️  Could not fetch data for {symbol}, skipping AI validation")
                        sys.stdout.flush()
                        validated_opportunities.append(opp)
                        continue

                    # Build stock_data format for AIRecommender
                    stock_data = {
                        "symbol": symbol,
                        "name": symbol,
                        "current_price": crypto_data.get("current_price"),
                        "previous_close": crypto_data.get("current_price"),  # Crypto doesn't have prev close
                        "52_week_high": crypto_data.get("current_price") * 1.5,  # Approximate
                        "52_week_low": crypto_data.get("current_price") * 0.5,   # Approximate
                        "pe_ratio": None,
                        "volume": None,
                    }

                    # Try to enrich crypto with yfinance data
                    if yfinance_available:
                        try:
                            ticker = yf.Ticker(symbol)
                            info = ticker.info

                            # Get 52-week range from yfinance if available
                            if info.get("fiftyTwoWeekHigh"):
                                stock_data["52_week_high"] = info.get("fiftyTwoWeekHigh")
                            if info.get("fiftyTwoWeekLow"):
                                stock_data["52_week_low"] = info.get("fiftyTwoWeekLow")

                            # Get volume if available
                            if info.get("volume") or info.get("regularMarketVolume"):
                                stock_data["volume"] = info.get("volume") or info.get("regularMarketVolume")

                            # Update previous close if available
                            if info.get("previousClose"):
                                stock_data["previous_close"] = info.get("previousClose")

                        except Exception:
                            pass  # Silently fail - crypto data is approximate anyway
                else:
                    stock_info = fetcher.get_stock_info(symbol)
                    if not stock_info or not stock_info.get("current_price"):
                        print(f"   ⚠️  Could not fetch data for {symbol}, skipping AI validation")
                        sys.stdout.flush()
                        validated_opportunities.append(opp)
                        continue

                    stock_data = {
                        "symbol": symbol,
                        "name": stock_info.get("name", symbol),
                        "current_price": stock_info.get("current_price"),
                        "previous_close": stock_info.get("previous_close"),
                        "52_week_high": stock_info.get("52_week_high"),
                        "52_week_low": stock_info.get("52_week_low"),
                        "pe_ratio": stock_info.get("pe_ratio"),
                        "volume": stock_info.get("volume"),
                    }

                # Enrich with yfinance if data is missing
                if yfinance_available and (not stock_data.get("pe_ratio") or not stock_data.get("volume")):
                    try:
                        ticker = yf.Ticker(symbol)
                        info = ticker.info

                        if not stock_data.get("pe_ratio"):
                            stock_data["pe_ratio"] = info.get("trailingPE") or info.get("forwardPE")

                        if not stock_data.get("volume"):
                            stock_data["volume"] = info.get("volume") or info.get("regularMarketVolume")

                        if not stock_data.get("52_week_high"):
                            stock_data["52_week_high"] = info.get("fiftyTwoWeekHigh")

                        if not stock_data.get("52_week_low"):
                            stock_data["52_week_low"] = info.get("fiftyTwoWeekLow")

                    except Exception:
                        pass  # Silently fail - not critical

                # Get AI recommendation
                ai_result = self.ai_recommender.get_ai_recommendation(stock_data)

                # Apply AI filtering based on mode
                if self.ai_mode == "validate":
                    # In validate mode: Keep if AI says BUY or HOLD (reject only if SELL)
                    if ai_result['action'] == 'SELL':
                        print(f"   ❌ {symbol}: AI recommends SELL - filtering out")
                        print(f"      Reasoning: {ai_result['reasons'][0]}")
                        sys.stdout.flush()
                        continue
                    elif ai_result['action'] == 'HOLD':
                        print(f"   ⚠️  {symbol}: AI suggests HOLD (neutral) - keeping with lower confidence")
                        sys.stdout.flush()
                        # Lower the opportunity score
                        opp['score'] = opp.get('score', 0) * 0.7
                    else:  # BUY
                        print(f"   ✅ {symbol}: AI confirms BUY")
                        print(f"      Reasoning: {ai_result['reasons'][0]}")
                        sys.stdout.flush()
                        # Boost the score
                        opp['score'] = opp.get('score', 0) * 1.2

                    # Add AI metadata
                    opp['ai_validated'] = True
                    opp['ai_action'] = ai_result['action']
                    opp['ai_confidence'] = ai_result['confidence']
                    opp['ai_score'] = ai_result['score']
                    opp['ai_reasoning'] = ai_result['reasons'][0]

                elif self.ai_mode == "full":
                    # In full mode: Use AI score heavily
                    if ai_result['score'] < -20:
                        print(f"   ❌ {symbol}: AI score {ai_result['score']} too negative - filtering out")
                        sys.stdout.flush()
                        continue
                    elif ai_result['score'] < 20:
                        print(f"   ⚠️  {symbol}: AI score {ai_result['score']} low - keeping with caution")
                        sys.stdout.flush()
                        opp['score'] = ai_result['score']
                    else:
                        print(f"   ✅ {symbol}: AI score {ai_result['score']} - strong signal")
                        sys.stdout.flush()
                        opp['score'] = ai_result['score']

                    opp['ai_validated'] = True
                    opp['ai_action'] = ai_result['action']
                    opp['ai_confidence'] = ai_result['confidence']
                    opp['ai_score'] = ai_result['score']
                    opp['ai_reasoning'] = ai_result['reasons'][0]

                validated_opportunities.append(opp)

            except Exception as e:
                print(f"   ⚠️  AI validation error for {symbol}: {str(e)}")
                sys.stdout.flush()
                import traceback
                traceback.print_exc()
                sys.stdout.flush()
                # Keep opportunity if AI fails
                validated_opportunities.append(opp)

        # Add remaining opportunities without AI validation
        remaining = opportunities[max_to_validate:]
        if remaining:
            print(f"\n   Keeping {len(remaining)} remaining opportunities without AI validation")
            sys.stdout.flush()
            validated_opportunities.extend(remaining)

        # Re-sort by score after AI adjustments
        validated_opportunities.sort(key=lambda x: x.get('score', 0), reverse=True)

        print(f"\n   AI Validation complete: {len(validated_opportunities)} opportunities")
        sys.stdout.flush()

        return validated_opportunities

    def display_position_details(self):
        """
        Display detailed information about current positions.
        """
        from .fetcher import StockFetcher
        from .binance_fetcher import BinanceFetcher

        fetcher = StockFetcher()
        binance = BinanceFetcher()

        print(f"\n{'='*90}")
        print(f"📊  CURRENT POSITIONS ANALYSIS")
        print(f"{'='*90}")
        print(f"{'Symbol':<12} {'Qty':<10} {'Buy Price':<12} {'Current':<12} {'P&L':<10} {'P&L%':<8} {'Hold Time':<15} {'Value':<12}")
        print(f"{'-'*90}")

        total_position_value = 0.0
        current_time = time.time()
        api_urls = []  # Collect URLs for reference section

        for symbol in self.portfolio.holdings.keys():
            try:
                quantity = self.portfolio.holdings[symbol]
                avg_buy = self.portfolio.avg_buy_price[symbol]

                # Get current price
                is_crypto = "-USD" in symbol
                if is_crypto:
                    binance_symbol = binance.convert_symbol(symbol)
                    binance_data = binance.get_crypto_price(binance_symbol)
                    if not binance_data:
                        continue
                    current_price = binance_data["current_price"]
                    # Collect URL instead of printing immediately
                    api_urls.append(f"   {symbol:<12} https://api.binance.com/api/v3/ticker/24hr?symbol={binance_symbol}")
                else:
                    data = fetcher.get_stock_info(symbol)
                    current_price = data.get("current_price")
                    if not current_price:
                        continue

                # Calculate metrics
                position_value = quantity * current_price
                total_position_value += position_value
                profit_loss = position_value - (quantity * avg_buy)
                profit_pct = ((current_price - avg_buy) / avg_buy) * 100

                # Hold time
                if symbol in self.position_entry_times:
                    hold_seconds = current_time - self.position_entry_times[symbol]
                    if hold_seconds < 3600:
                        hold_time = f"{int(hold_seconds/60)}m"
                    else:
                        hold_time = f"{hold_seconds/3600:.1f}h"
                else:
                    hold_time = "unknown"

                # Format output
                emoji = "🟢" if profit_pct >= 0 else "🔴"
                print(f"{emoji} {symbol:<10} {quantity:<10.2f} €{avg_buy:<11.2f} €{current_price:<11.2f} "
                      f"€{profit_loss:>8.2f} {profit_pct:>7.2f}% {hold_time:<15} €{position_value:>10.2f}")

            except Exception as e:
                print(f"⚠️  {symbol:<10} Error: {str(e)[:40]}")

        print(f"{'-'*90}")
        print(f"{'TOTAL POSITIONS VALUE:':<75} €{total_position_value:>12,.2f}")
        print(f"{'CASH:':<75} €{self.portfolio.cash:>12,.2f}")
        print(f"{'PORTFOLIO TOTAL:':<75} €{total_position_value + self.portfolio.cash:>12,.2f}")
        print(f"{'='*90}")

        # API Reference section
        if api_urls:
            print(f"\n📡 API Calls:")
            for url in api_urls:
                print(url)
        print()

    def check_existing_positions(self):
        """
        Monitor existing positions for profit-taking and stop-loss.
        """
        from .fetcher import StockFetcher
        from .binance_fetcher import BinanceFetcher

        fetcher = StockFetcher()
        binance = BinanceFetcher()

        holdings = list(self.portfolio.holdings.keys())

        for symbol in holdings:
            try:
                # Get current price
                is_crypto = "-USD" in symbol
                if is_crypto:
                    binance_symbol = binance.convert_symbol(symbol)
                    binance_data = binance.get_crypto_price(binance_symbol)
                    if not binance_data:
                        continue
                    price = binance_data["current_price"]
                else:
                    data = fetcher.get_stock_info(symbol)
                    price = data.get("current_price")
                    if not price:
                        continue

                # Check profit-taking and stop-loss
                avg_buy = self.portfolio.avg_buy_price[symbol]
                profit_pct = ((price - avg_buy) / avg_buy) * 100

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # RSI-based exit signal for crypto (early profit-taking consideration)
                if is_crypto and profit_pct > 5.0:
                    tech_indicators = binance.get_technical_indicators(binance_symbol)
                    if tech_indicators and 'rsi' in tech_indicators:
                        rsi = tech_indicators['rsi']
                        if rsi > 70:
                            print(f"   📊 {symbol}: RSI high ({rsi:.1f}) with profit {profit_pct:.2f}% - consider early profit-taking")

                # PROFIT TAKING: +3%
                if profit_pct >= 3.0:
                    quantity = self.portfolio.holdings[symbol]
                    result = self.portfolio.sell(symbol, price, quantity, timestamp)
                    if result["success"]:
                        print(f"   💰 {symbol}: Profit target hit (+{profit_pct:.2f}%) - SOLD €{result['transaction']['profit_loss']:+,.2f}")
                        # Remove from entry times and persist
                        if symbol in self.position_entry_times:
                            del self.position_entry_times[symbol]
                            self.persistence.save_entry_times(self.position_entry_times)

                # STOP LOSS: -5%
                elif profit_pct <= -5.0:
                    quantity = self.portfolio.holdings[symbol]
                    result = self.portfolio.sell(symbol, price, quantity, timestamp)
                    if result["success"]:
                        print(f"   🛑 {symbol}: Stop loss triggered ({profit_pct:.2f}%) - SOLD €{result['transaction']['profit_loss']:+,.2f}")
                        # Remove from entry times and persist
                        if symbol in self.position_entry_times:
                            del self.position_entry_times[symbol]
                            self.persistence.save_entry_times(self.position_entry_times)

            except Exception as e:
                print(f"   ⚠️ Error checking {symbol}: {str(e)[:50]}")
                print(f"   Traceback: {traceback.format_exc()}")

    def execute_new_trades(self):
        """
        Execute trades for validated opportunities.

        Weekends: crypto only (24/7). US stocks stay paused.
        """
        from .fetcher import StockFetcher
        from .binance_fetcher import BinanceFetcher

        fetcher = StockFetcher()
        binance = BinanceFetcher()

        is_weekend = self.scanner.is_weekend()
        if is_weekend:
            print(f"   📅 Weekend: crypto-only trading (stocks paused)")

        # US cash session closed? stocks skip; crypto still OK on weekdays too
        market_closed = self.scanner.is_market_closed()

        # Sort opportunities by score (highest first)
        sorted_opportunities = sorted(
            self.current_opportunities,
            key=lambda x: x.get("score", 0),
            reverse=True
        )

        trades_executed = 0

        for opportunity in sorted_opportunities:
            # Check if we still have room for more positions
            if len(self.portfolio.holdings) >= self.max_positions:
                print(f"   📊 Max positions reached ({self.max_positions}), stopping new trades")
                break

            symbol = opportunity.get("symbol")

            # Skip if we already hold this position
            if symbol in self.portfolio.holdings:
                continue

            if not is_tradeable_symbol(str(symbol)):
                print(f"   ⏸️  Skipping {symbol}: filtered (stable/leveraged/noise)")
                continue

            blocked, why = is_in_earnings_blackout(str(symbol))
            if blocked:
                print(f"   ⏸️  Skipping {symbol}: earnings blackout ({why})")
                continue

            try:
                # Get current price
                is_crypto = "-USD" in symbol

                if is_weekend and not is_crypto:
                    continue

                # Skip stock trades if market is closed
                if not is_crypto and market_closed:
                    print(f"   ⏸️  Skipping {symbol}: Market is closed (stocks only trade during market hours)")
                    continue

                if is_crypto:
                    binance_symbol = binance.convert_symbol(symbol)
                    binance_data = binance.get_crypto_price(binance_symbol)
                    if not binance_data:
                        print(f"   ⚠️ Could not fetch price for {symbol}")
                        continue
                    current_price = binance_data["current_price"]
                    
                    # Check RSI for crypto - skip if overbought
                    tech_indicators = binance.get_technical_indicators(binance_symbol)
                    if tech_indicators and 'rsi' in tech_indicators:
                        rsi = tech_indicators['rsi']
                        if rsi > 75:
                            print(f"   ⏸️  Skipping {symbol}: RSI too high ({rsi:.1f} > 75) - overbought condition")
                            continue
                else:
                    data = fetcher.get_stock_info(symbol)
                    current_price = data.get("current_price")
                    if not current_price:
                        print(f"   ⚠️ Could not fetch price for {symbol}")
                        continue

                # Calculate investment amount (position_size % of portfolio)
                investment_amount = self.portfolio.cash * self.position_size

                # Calculate shares to buy
                shares = investment_amount / current_price

                # Ensure we have enough cash
                total_cost = shares * current_price
                if total_cost > self.portfolio.cash:
                    print(f"   ⚠️ Insufficient cash for {symbol} (need €{total_cost:,.2f}, have €{self.portfolio.cash:,.2f})")
                    continue

                # Execute the buy order
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                result = self.portfolio.buy(symbol, current_price, shares, timestamp)

                if result["success"]:
                    trades_executed += 1
                    action = opportunity.get("action", "BUY")
                    confidence = opportunity.get("confidence", "UNKNOWN")
                    score = opportunity.get("score", 0)
                    reason = opportunity.get("reasons", ["No reason provided"])[0]

                    print(f"   ✅ EXECUTED: {symbol}")
                    print(f"      Action: {action} | Confidence: {confidence} | Score: {score:+.0f}")
                    print(f"      Price: €{current_price:.2f} | Shares: {shares:.4f} | Cost: €{total_cost:,.2f}")
                    print(f"      Reason: {reason}")

                    # Record entry time and persist
                    self.position_entry_times[symbol] = time.time()
                    self.persistence.save_entry_times(self.position_entry_times)
                else:
                    print(f"   ❌ Trade failed for {symbol}: {result.get('message', 'Unknown error')}")

            except Exception as e:
                print(f"   ⚠️ Error executing trade for {symbol}: {str(e)[:100]}")
                print(f"   Traceback: {traceback.format_exc()}")

        if trades_executed > 0:
            print(f"\n💼 Executed {trades_executed} new trade(s)")
        else:
            print(f"\n💼 No new trades executed")

    def evaluate_rebalancing(self) -> bool:
        """
        Evaluate if portfolio should be rebalanced based on new opportunities.

        Weekends: crypto only (24/7). US stocks stay paused.

        Returns True if rebalancing occurred.
        """
        from .fetcher import StockFetcher
        from .binance_fetcher import BinanceFetcher
        from .recommender import RecommendationEngine

        if not self.current_opportunities:
            return False

        is_weekend = self.scanner.is_weekend()
        if is_weekend:
            print(f"   📅 Weekend: crypto-only rebalancing (stocks paused)")

        fetcher = StockFetcher()
        binance = BinanceFetcher()
        recommender = RecommendationEngine()

        # Check if market is closed (for stocks only - crypto trades 24/7)
        market_closed = self.scanner.is_market_closed()

        # Get current holdings
        current_holdings = set(self.portfolio.holdings.keys())

        # Get top N opportunities (where N = max_positions)
        top_opportunities = [
            opp
            for opp in self.current_opportunities
            if (not is_weekend) or ("-USD" in str(opp.get("symbol", "")))
        ][: self.max_positions]
        top_symbols = {opp['symbol'] for opp in top_opportunities}

        # Check if we have capital to add new positions
        portfolio_value = self.portfolio.get_total_value()
        available_pct = self.portfolio.cash / portfolio_value

        # Identify symbols we should hold but don't
        missing_opportunities = top_symbols - current_holdings

        # Identify symbols we hold but aren't in top opportunities
        stale_holdings = current_holdings - top_symbols

        rebalanced = False

        # Sell stale holdings (with smart exit logic)
        for symbol in stale_holdings:
            try:
                # Check minimum hold time
                if symbol in self.position_entry_times:
                    hold_time = time.time() - self.position_entry_times[symbol]
                    if hold_time < self.min_hold_time:
                        print(f"   ⏳ {symbol}: Holding (only {int(hold_time)}s, min {self.min_hold_time}s)")
                        continue

                # Get current price
                is_crypto = "-USD" in symbol

                if is_weekend and not is_crypto:
                    continue

                # Skip stock trades if market is closed
                if not is_crypto and market_closed:
                    print(f"   ⏸️  Skipping {symbol}: Market is closed (stocks only trade during market hours)")
                    continue
                
                if is_crypto:
                    binance_symbol = binance.convert_symbol(symbol)
                    binance_data = binance.get_crypto_price(binance_symbol)
                    if not binance_data:
                        continue
                    price = binance_data["current_price"]
                else:
                    data = fetcher.get_stock_info(symbol)
                    price = data.get("current_price")
                    if not price:
                        continue

                # Check P&L before selling
                avg_buy = self.portfolio.avg_buy_price[symbol]
                profit_pct = ((price - avg_buy) / avg_buy) * 100

                # Don't sell at a loss unless it's been held long enough or loss is significant
                if profit_pct < 0 and profit_pct > -2.0 and hold_time < self.min_hold_time * 2:
                    print(f"   💎 {symbol}: Holding through small loss ({profit_pct:.2f}%)")
                    continue

                # Sell the position
                quantity = self.portfolio.holdings[symbol]
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                result = self.portfolio.sell(symbol, price, quantity, timestamp)

                if result["success"]:
                    print(f"   📤 {symbol}: Exited stale position - €{result['transaction']['profit_loss']:+,.2f} ({profit_pct:+.2f}%)")
                    # Remove from entry times and persist
                    if symbol in self.position_entry_times:
                        del self.position_entry_times[symbol]
                        self.persistence.save_entry_times(self.position_entry_times)
                    rebalanced = True

            except Exception as e:
                print(f"   ⚠️ Error selling {symbol}: {str(e)[:50]}")

        # Buy missing opportunities if we have cash
        if available_pct >= self.position_size:
            for opp in top_opportunities:
                symbol = opp['symbol']

                if symbol in current_holdings:
                    continue

                if symbol not in missing_opportunities:
                    continue

                try:
                    # Get current price and data
                    is_crypto = "-USD" in symbol

                    if is_weekend and not is_crypto:
                        continue

                    # Skip stock trades if market is closed
                    if not is_crypto and market_closed:
                        print(f"   ⏸️  Skipping {symbol}: Market is closed (stocks only trade during market hours)")
                        continue
                    
                    if is_crypto:
                        binance_symbol = binance.convert_symbol(symbol)
                        binance_data = binance.get_crypto_price(binance_symbol)
                        if not binance_data:
                            continue
                        price = binance_data["current_price"]
                        data = {
                            "symbol": symbol,
                            "current_price": price,
                            "previous_close": price / (1 + binance_data["change_24h"]/100),
                            "52_week_high": binance_data["high_24h"],
                            "52_week_low": binance_data["low_24h"],
                            "source": "binance"
                        }
                    else:
                        data = fetcher.get_stock_info(symbol)
                        price = data.get("current_price")
                        if not price:
                            continue

                    # Get recommendation to validate buy
                    recommendation = recommender.analyze_stock_recommendation(data)

                    if recommendation["action"] == "BUY":
                        # Calculate position size
                        portfolio_value = self.portfolio.get_total_value()
                        max_investment = portfolio_value * self.position_size
                        quantity = max_investment / price

                        # Round quantity
                        if price > 100:
                            quantity = round(quantity, 2)
                        else:
                            quantity = round(quantity, 4)

                        # Execute buy
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if quantity > 0 and self.portfolio.can_buy(symbol, price, quantity):
                            result = self.portfolio.buy(symbol, price, quantity, timestamp)

                            if result["success"]:
                                print(f"   📥 {symbol}: Added new opportunity ({opp['strategy']}) - €{result['transaction']['total_cost']:,.2f}")
                                # Track entry time and persist
                                self.position_entry_times[symbol] = time.time()
                                self.persistence.save_entry_times(self.position_entry_times)
                                rebalanced = True

                                # Update available cash
                                portfolio_value = self.portfolio.get_total_value()
                                available_pct = self.portfolio.cash / portfolio_value

                                if available_pct < self.position_size:
                                    break

                except Exception as e:
                    print(f"   ⚠️ Error buying {symbol}: {str(e)[:50]}")

        return rebalanced

    def run(self):
        """
        Main trading loop.
        """
        print(f"\n{'#'*70}")
        print(f"🚀  INTELLIGENT TRADER STARTED")
        print(f"{'#'*70}\n")

        iteration = 0

        while True:
            iteration += 1
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            print(f"\n{'='*70}")
            print(f"⏰  Iteration #{iteration} - {timestamp}")
            print(f"{'='*70}")

            # Periodic market scan
            if self.should_scan():
                opportunities = self.scan_markets()

                # Show top 5 opportunities
                print(f"\n🎯 Top 5 Opportunities:")
                for i, opp in enumerate(opportunities[:5], 1):
                    print(f"   {i}. {opp['symbol']} - {opp['strategy']} - {opp['reasoning']}")

            # Display detailed position analysis
            if self.portfolio.holdings:
                self.display_position_details()

            # Check existing positions (profit-taking, stop-loss)
            if self.portfolio.holdings:
                print(f"\n📊 Monitoring {len(self.portfolio.holdings)} positions for profit-taking/stop-loss...")
                self.check_existing_positions()

            # Execute new trades if we have opportunities and room for more positions
            if self.current_opportunities and len(self.portfolio.holdings) < self.max_positions:
                print(f"\n📈 Evaluating new trade opportunities ({len(self.portfolio.holdings)}/{self.max_positions} positions used)...")
                self.execute_new_trades()

            # Evaluate rebalancing
            if self.current_opportunities:
                rebalanced = self.evaluate_rebalancing()
                if rebalanced:
                    print(f"\n✅ Portfolio rebalanced")

            # Show portfolio status summary
            portfolio_value = self.portfolio.get_total_value()
            total_return = ((portfolio_value - self.portfolio.initial_cash) / self.portfolio.initial_cash) * 100

            print(f"\n💰 Portfolio Summary:")
            print(f"   Version: {__version__}")
            print(f"   Cash: €{self.portfolio.cash:,.2f}")
            print(f"   Holdings: {len(self.portfolio.holdings)} positions")
            print(f"   Total Value: €{portfolio_value:,.2f}")
            print(f"   Return: {total_return:+.2f}%")
            print(f"   Total Fees Paid: €{self.portfolio.total_fees_paid:,.2f}")
            print(f"   Total Trades: {len(self.portfolio.transactions)}")

            # Sleep until next trade interval
            print(f"\n💤 Sleeping for {self.trade_interval}s...")
            time.sleep(self.trade_interval)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Intelligent trading with continuous market analysis")
    parser.add_argument("--capital", type=float, default=10000.0, help="Initial capital")
    parser.add_argument("--scan-interval", type=int, default=900, help="Market scan interval (seconds)")
    parser.add_argument("--trade-interval", type=int, default=300, help="Trading check interval (seconds)")
    parser.add_argument("--max-positions", type=int, default=8, help="Maximum positions")
    parser.add_argument("--position-size", type=float, default=0.10, help="Position size as % of portfolio")
    parser.add_argument("--min-hold-time", type=int, default=14400, help="Minimum hold time (seconds)")
    parser.add_argument("--ai-mode", type=str, default="off", choices=["off", "validate", "full"],
                        help="AI analysis mode: off (rule-based only), validate (AI validates HIGH signals), full (AI-driven)")
    parser.add_argument("--ai-model", type=str, default="gemma4:latest",
                        help="Ollama instruct/general model (not coder models)")
    parser.add_argument("--top-crypto-count", type=int, default=2, help="Number of top crypto opportunities to include")

    args = parser.parse_args()

    trader = IntelligentTrader(
        initial_cash=args.capital,
        scan_interval=args.scan_interval,
        trade_interval=args.trade_interval,
        max_positions=args.max_positions,
        position_size=args.position_size,
        min_hold_time=args.min_hold_time,
        ai_mode=args.ai_mode,
        ai_model=args.ai_model,
        top_crypto_count=args.top_crypto_count
    )

    trader.run()


if __name__ == "__main__":
    main()
