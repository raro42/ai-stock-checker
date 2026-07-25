#!/usr/bin/env python3

import sys
import time
import signal
import traceback
from datetime import datetime
from typing import Dict, List

from stock_checker.fetcher import StockFetcher
from stock_checker.binance_fetcher import BinanceFetcher
from stock_checker.market_analyzer import MarketAnalyzer
from stock_checker.recommender import RecommendationEngine
from stock_checker.ai_recommender import AIRecommender
from stock_checker.portfolio import Portfolio
from stock_checker.persistence import DataPersistence
from stock_checker import __version__


class PaperTrader:
    """Advanced paper trading engine with dynamic risk management."""

    def __init__(
        self,
        initial_cash: float = 10000.0,
        commission_rate: float = 0.001,
        watch_list: List[str] = None,
        check_interval: int = 300,
        position_size_pct: float = 0.15,
        enable_bitcoin: bool = True,
        ai_mode: str = "off",
        ai_model: str = "gemma4:latest",
        data_dir: str = "/data",
    ):
        """
        Initialize advanced paper trader.
        """
        # Initialize persistence layer
        self.persistence = DataPersistence(data_dir)

        # Initialize portfolio with persistence
        self.portfolio = Portfolio(initial_cash, commission_rate, self.persistence)

        self.watch_list = watch_list or ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN"]
        self.check_interval = check_interval
        self.position_size_pct = position_size_pct
        self.enable_bitcoin = enable_bitcoin
        self.ai_mode = ai_mode
        self.ai_model = ai_model

        # Enhanced risk management parameters
        self.max_portfolio_drawdown = 0.15  # 15% max drawdown
        self.volatility_adjustment = True
        self.correlation_limits = True
        self.max_sector_exposure = 0.40  # 40% max per sector

        # Dynamic position sizing
        self.base_position_size = position_size_pct
        self.min_position_size = 0.03  # 3% minimum
        self.max_position_size = 0.25  # 25% maximum

        # Market regime tracking
        self.market_regime = "neutral"
        self.regime_update_counter = 0

        # Hot reload support
        self.restart_requested = False
        signal.signal(signal.SIGHUP, self._handle_restart_signal)

        self.fetcher = StockFetcher()
        self.binance = BinanceFetcher()
        self.market_analyzer = MarketAnalyzer()
        self.recommender = RecommendationEngine()
        self.ai_recommender = AIRecommender(ai_model) if ai_mode != "off" else None

        # Load state if exists
        state = self.persistence.load_state()
        self.iteration = state.get("iteration", 0) if state else 0
        self.current_prices: Dict[str, float] = {}

        self.log(f"📁 Data directory: {data_dir}")
        if state:
            self.log(f"✅ Loaded existing state - iteration #{self.iteration}")

    def log(self, message: str):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
        sys.stdout.flush()

    def _handle_restart_signal(self, signum, frame):
        """Handle SIGHUP signal for hot reloading."""
        self.log(f"🔄 SIGHUP received - scheduling graceful restart...")
        self.restart_requested = True

    def log_portfolio_summary(self):
        """Log current portfolio status."""
        summary = self.portfolio.get_summary(self.current_prices)

        print(f"\n{'='*80}")
        print(f"💼 PORTFOLIO SUMMARY")
        print(f"{'='*80}")
        print(f"Version:            {__version__}")
        print(f"Initial Capital:    €{summary['initial_cash']:,.2f}")
        print(f"Current Cash:       €{summary['current_cash']:,.2f}")
        print(f"Holdings Value:     €{summary['holdings_value']:,.2f}")
        print(f"Total Value:        €{summary['total_value']:,.2f}")
        print(f"Total Return:       €{summary['total_return']:+,.2f} ({summary['total_return_pct']:+.2f}%)")
        print(f"Fees Paid:          €{summary['total_fees_paid']:,.2f}")
        print(f"Transactions:       {summary['num_transactions']}")

        if summary['positions']:
            print(f"\nOpen Positions:")
            print(f"{'-'*80}")
            for pos in summary['positions']:
                profit_emoji = "🟢" if pos['profit_loss'] >= 0 else "🔴"
                print(
                    f"{profit_emoji} {pos['symbol']:<8} "
                    f"Qty: {pos['quantity']:<8.2f} "
                    f"Avg Buy: €{pos['avg_buy_price']:<8.2f} "
                    f"Current: €{pos['current_price']:<8.2f} "
                    f"P/L: €{pos['profit_loss']:+,.2f} ({pos['profit_loss_pct']:+.2f}%)"
                )
        else:
            print(f"\nNo open positions")

        print(f"{'='*80}\n")
        sys.stdout.flush()

    def calculate_dynamic_position_size(self, symbol: str, recommendation: Dict, stock_data: Dict) -> float:
        """Calculate position size based on confidence, volatility, and market conditions."""
        base_size = self.base_position_size

        # Adjust for confidence
        confidence_multipliers = {
            "HIGH": 1.4,
            "MEDIUM": 1.0,
            "LOW": 0.6
        }
        confidence = recommendation.get("confidence", "MEDIUM")
        base_size *= confidence_multipliers.get(confidence, 0.8)

        # Adjust for volatility
        volatility = stock_data.get("volatility_30d")
        if volatility is not None:
            try:
                volatility = float(volatility)
                if volatility > 0.05:  # 5% daily volatility
                    vol_adjustment = max(0.4, 1.0 - (volatility - 0.05) * 15)
                    base_size *= vol_adjustment
            except (TypeError, ValueError):
                pass

        # Adjust for market regime
        regime_multipliers = {
            "bull": 1.2,    # More aggressive in bull markets
            "bear": 0.6,    # More conservative in bear markets
            "volatile": 0.7, # Smaller positions in volatile markets
            "sideways": 0.9  # Slightly conservative in ranging markets
        }
        base_size *= regime_multipliers.get(self.market_regime, 1.0)

        # Check correlation limits (simplified)
        current_exposure = self._calculate_symbol_exposure(symbol)
        if current_exposure > self.max_sector_exposure:
            base_size *= 0.5  # Reduce if over-exposed

        # Apply bounds
        return min(max(base_size, self.min_position_size), self.max_position_size)

    def _calculate_symbol_exposure(self, symbol: str) -> float:
        """Calculate current exposure to symbol's sector (simplified)."""
        # In production, this would map symbols to sectors
        # For now, return conservative estimate
        return 0.0

    def update_market_regime(self):
        """Update market regime every 10 iterations."""
        self.regime_update_counter += 1
        if self.regime_update_counter >= 10:
            self.market_regime = self._detect_market_regime()
            self.regime_update_counter = 0

    def _detect_market_regime(self) -> str:
        """Detect current market regime using major indices."""
        try:
            # Check S&P 500 trend
            spx_data = self.fetcher.get_stock_info("^GSPC")
            spx_change = spx_data.get("daily_change")
            if spx_change is None:
                spx_change = 0
            else:
                try:
                    spx_change = float(spx_change)
                except (TypeError, ValueError):
                    spx_change = 0

            # Check VIX for volatility
            vix_data = self.fetcher.get_stock_info("^VIX")
            vix_level = vix_data.get("current_price")
            if vix_level is None:
                vix_level = 20
            else:
                try:
                    vix_level = float(vix_level)
                except (TypeError, ValueError):
                    vix_level = 20

            if spx_change > 1.0 and vix_level < 20:
                return "bull"
            elif spx_change < -1.0 and vix_level > 25:
                return "bear"
            elif vix_level > 30:
                return "volatile"
            else:
                return "sideways"
        except:
            return "neutral"

    def execute_trade(self, recommendation: Dict, price: float, stock_data: Dict):
        """Execute trade with enhanced risk management."""
        symbol = recommendation["symbol"]
        action = recommendation["action"]
        confidence = recommendation["confidence"]
        score = recommendation["score"]

        # Debug: Always log the recommendation score
        print(f"[DEBUG] {symbol}: {action} (confidence: {confidence}, score: {score:+.1f})")
        sys.stdout.flush()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Save finding to persistent storage
        finding = {
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "score": score,
            "price": price,
            "reasons": recommendation.get("reasons", []),
            "ai_validated": recommendation.get("ai_validated", False),
            "executed": False,
        }
        self.persistence.append_finding(finding)

        if action == "BUY" and confidence in ["HIGH", "MEDIUM", "LOW"]:
            # Calculate dynamic position size
            position_size = self.calculate_dynamic_position_size(symbol, recommendation, stock_data)

            # Calculate investment amount
            portfolio_value = self.portfolio.get_portfolio_value(self.current_prices)
            max_investment = portfolio_value * position_size
            quantity = max_investment / price

            # Round to reasonable quantity
            if price > 100:
                quantity = round(quantity, 2)
            else:
                quantity = round(quantity, 4)

            if quantity > 0 and self.portfolio.can_buy(symbol, price, quantity):
                result = self.portfolio.buy(symbol, price, quantity, timestamp)

                if result["success"]:
                    tx = result["transaction"]
                    print(f"\n{'='*80}")
                    print(f"🟢 BUY ORDER EXECUTED")
                    print(f"{'='*80}")
                    print(f"Symbol:       {symbol}")
                    print(f"Confidence:   {confidence}")
                    print(f"Score:        {int(score):+d}")
                    print(f"Position Size: {position_size*100:.1f}%")
                    print(f"Quantity:     {quantity:.4f}")
                    print(f"Price:        €{price:.2f}")
                    print(f"Cost:         €{tx['cost']:.2f}")
                    print(f"Commission:   €{tx['commission']:.2f}")
                    print(f"Total Cost:   €{tx['total_cost']:.2f}")
                    print(f"Cash Left:    €{tx['cash_remaining']:.2f}")
                    print(f"Reasons:")
                    for reason in recommendation.get("reasons", []):
                        print(f"  • {reason}")
                    if recommendation.get("ai_validated"):
                        print(f"✅ AI Validated")
                    if self.ai_mode == "full":
                        print(f"🤖 AI-Driven Decision")
                    print(f"{'='*80}\n")
                    sys.stdout.flush()

                    # Mark finding as executed
                    finding["executed"] = True
                    self.persistence.append_finding(finding)

        elif action == "SELL" and confidence in ["HIGH", "MEDIUM", "LOW"]:
            # Sell entire position if we have one
            if symbol in self.portfolio.holdings:
                quantity = self.portfolio.holdings[symbol]
                result = self.portfolio.sell(symbol, price, quantity, timestamp)

                if result["success"]:
                    tx = result["transaction"]
                    profit_emoji = "🟢" if tx["profit_loss"] >= 0 else "🔴"
                    print(f"\n{'='*80}")
                    print(f"🔴 SELL ORDER EXECUTED")
                    print(f"{'='*80}")
                    print(f"Symbol:       {symbol}")
                    print(f"Confidence:   {confidence}")
                    print(f"Score:        {int(score):+d}")
                    print(f"Quantity:     {quantity:.4f}")
                    print(f"Sell Price:   €{price:.2f}")
                    print(f"Buy Price:    €{tx['buy_price']:.2f}")
                    print(f"Proceeds:     €{tx['proceeds']:.2f}")
                    print(f"Commission:   €{tx['commission']:.2f}")
                    print(f"Net Proceeds: €{tx['net_proceeds']:.2f}")
                    print(f"{profit_emoji} Profit/Loss: €{tx['profit_loss']:+.2f} ({tx['profit_loss_pct']:+.2f}%)")
                    print(f"Cash Now:     €{tx['cash_remaining']:.2f}")
                    print(f"Reasons:")
                    for reason in recommendation.get("reasons", []):
                        print(f"  • {reason}")
                    if recommendation.get("ai_validated"):
                        print(f"✅ AI Validated")
                    if self.ai_mode == "full":
                        print(f"🤖 AI-Driven Decision")
                    print(f"{'='*80}\n")
                    sys.stdout.flush()

    def check_stock(self, symbol: str):
        """Check a stock/crypto and potentially trade with enhanced risk management."""
        try:
            # Use Binance for crypto (faster, real-time)
            is_crypto = "-USD" in symbol
            if is_crypto:
                binance_symbol = self.binance.convert_symbol(symbol)
                binance_data = self.binance.get_crypto_price(binance_symbol)
                if binance_data:
                    price = binance_data["current_price"]
                    # Adapt to stock_info format
                    data = {
                        "symbol": symbol,
                        "current_price": price,
                        "previous_close": price / (1 + binance_data["change_24h"]/100),
                        "52_week_high": binance_data["high_24h"],
                        "52_week_low": binance_data["low_24h"],
                        "source": "binance"
                    }
                else:
                    return
            else:
                # Use enhanced fetcher for stocks
                data = self.fetcher.get_stock_info(symbol)
                price = data.get("current_price")
                if not price:
                    return

            self.current_prices[symbol] = price

            # Check for profit-taking or stop-loss on existing positions
            if symbol in self.portfolio.holdings:
                avg_buy = self.portfolio.avg_buy_price.get(symbol)
                if avg_buy is None or price is None:
                    return
                try:
                    profit_pct = ((float(price) - float(avg_buy)) / float(avg_buy)) * 100
                except (TypeError, ValueError, ZeroDivisionError):
                    return

                # Dynamic profit targets based on volatility
                volatility = data.get("volatility_30d")
                base_target = 4.0  # Increased from 3%
                vol_adjustment = 0.0
                if volatility is not None:
                    try:
                        volatility = float(volatility)
                        vol_adjustment = volatility * 100 * 1.5
                    except (TypeError, ValueError):
                        vol_adjustment = 0.0
                profit_target = base_target + vol_adjustment

                # Dynamic stop loss based on volatility
                base_stop = 6.0  # Increased from 5%
                stop_loss = base_stop + vol_adjustment

                if profit_pct >= profit_target:
                    quantity = self.portfolio.holdings[symbol]
                    result = self.portfolio.sell(symbol, price, quantity, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    if result["success"]:
                        tx = result["transaction"]
                        print(f"\n{'='*80}")
                        print(f"💰 PROFIT TARGET HIT - AUTO SELL")
                        print(f"{'='*80}")
                        print(f"Symbol:       {symbol}")
                        print(f"Profit:       +{profit_pct:.2f}% (Target: +{profit_target:.2f}%)")
                        print(f"Quantity:     {quantity:.4f}")
                        print(f"Sell Price:   €{price:.2f}")
                        print(f"Buy Price:    €{avg_buy:.2f}")
                        print(f"🟢 Profit:    €{tx['profit_loss']:+.2f}")
                        print(f"Cash Now:     €{tx['cash_remaining']:.2f}")
                        print(f"{'='*80}\n")
                        sys.stdout.flush()
                        return  # Exit early - position closed

                elif profit_pct <= -stop_loss:
                    quantity = self.portfolio.holdings[symbol]
                    result = self.portfolio.sell(symbol, price, quantity, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    if result["success"]:
                        tx = result["transaction"]
                        print(f"\n{'='*80}")
                        print(f"🛑 STOP LOSS TRIGGERED - AUTO SELL")
                        print(f"{'='*80}")
                        print(f"Symbol:       {symbol}")
                        print(f"Loss:         {profit_pct:.2f}% (Limit: -{stop_loss:.2f}%)")
                        print(f"Quantity:     {quantity:.4f}")
                        print(f"Sell Price:   €{price:.2f}")
                        print(f"Buy Price:    €{avg_buy:.2f}")
                        print(f"🔴 Loss:      €{tx['profit_loss']:+.2f}")
                        print(f"Cash Now:     €{tx['cash_remaining']:.2f}")
                        print(f"{'='*80}\n")
                        sys.stdout.flush()
                        return  # Exit early - position closed

            # Get recommendation based on AI mode
            if self.ai_mode == "full":
                recommendation = self.ai_recommender.get_ai_recommendation(data)
            elif self.ai_mode == "validate":
                rule_rec = self.recommender.analyze_stock_recommendation(data)
                recommendation = self.ai_recommender.validate_recommendation(rule_rec, data)
            else:
                recommendation = self.recommender.analyze_stock_recommendation(data)

            self.execute_trade(recommendation, price, data)

        except Exception as e:
            self.log(f"[ERROR] Failed to check {symbol}: {str(e)}")
            self.log(f"[TRACEBACK] {traceback.format_exc()}")

    def check_bitcoin(self):
        """Check Bitcoin with enhanced analysis."""
        try:
            data = self.market_analyzer.analyze_bitcoin_for_investment()
            price = data.get("current_price")

            if not price:
                return

            self.current_prices["BTC-USD"] = price

            # Enhanced profit-taking for crypto
            if "BTC-USD" in self.portfolio.holdings:
                avg_buy = self.portfolio.avg_buy_price.get("BTC-USD")
                if avg_buy is None or price is None:
                    return
                try:
                    profit_pct = ((float(price) - float(avg_buy)) / float(avg_buy)) * 100
                except (TypeError, ValueError, ZeroDivisionError):
                    return

                # Crypto-specific targets (higher due to volatility)
                profit_target = 5.0  # 5% for crypto
                stop_loss = 8.0      # 8% stop for crypto

                if profit_pct >= profit_target:
                    quantity = self.portfolio.holdings["BTC-USD"]
                    result = self.portfolio.sell("BTC-USD", price, quantity, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    if result["success"]:
                        tx = result["transaction"]
                        print(f"\n{'='*80}")
                        print(f"💰 CRYPTO PROFIT TARGET - AUTO SELL")
                        print(f"{'='*80}")
                        print(f"Symbol:       BTC-USD")
                        print(f"Profit:       +{profit_pct:.2f}% (Target: +{profit_target:.2f}%)")
                        print(f"Quantity:     {quantity:.8f}")
                        print(f"Sell Price:   €{price:.2f}")
                        print(f"Buy Price:    €{avg_buy:.2f}")
                        print(f"🟢 Profit:    €{tx['profit_loss']:+.2f}")
                        print(f"Cash Now:     €{tx['cash_remaining']:.2f}")
                        print(f"{'='*80}\n")
                        sys.stdout.flush()
                        return  # Exit early - position closed

                elif profit_pct <= -stop_loss:
                    quantity = self.portfolio.holdings["BTC-USD"]
                    result = self.portfolio.sell("BTC-USD", price, quantity, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    if result["success"]:
                        tx = result["transaction"]
                        print(f"\n{'='*80}")
                        print(f"🛑 CRYPTO STOP LOSS - AUTO SELL")
                        print(f"{'='*80}")
                        print(f"Symbol:       BTC-USD")
                        print(f"Loss:         {profit_pct:.2f}% (Limit: -{stop_loss:.2f}%)")
                        print(f"Quantity:     {quantity:.8f}")
                        print(f"Sell Price:   €{price:.2f}")
                        print(f"Buy Price:    €{avg_buy:.2f}")
                        print(f"🔴 Loss:      €{tx['profit_loss']:+.2f}")
                        print(f"Cash Now:     €{tx['cash_remaining']:.2f}")
                        print(f"{'='*80}\n")
                        sys.stdout.flush()
                        return  # Exit early - position closed

            # Get recommendation
            if self.ai_mode == "full":
                recommendation = self.ai_recommender.get_bitcoin_ai_recommendation(data)
            elif self.ai_mode == "validate":
                rule_rec = self.recommender.analyze_bitcoin_recommendation(data)
                btc_stock_data = {
                    **data,
                    "symbol": "BTC-USD",
                    "name": "Bitcoin",
                    "current_price": price,
                }
                recommendation = self.ai_recommender.validate_recommendation(rule_rec, btc_stock_data)
            else:
                recommendation = self.recommender.analyze_bitcoin_recommendation(data)

            # Use dynamic position sizing for crypto too
            self.execute_trade(recommendation, price, data)

        except Exception as e:
            self.log(f"[ERROR] Failed to check Bitcoin: {str(e)}")

    def run(self):
        """Run enhanced paper trading loop."""
        print(f"\n{'='*80}")
        print(f"🚀 ENHANCED PAPER TRADING SIMULATOR")
        print(f"{'='*80}")
        print(f"Initial Capital:    €{self.portfolio.initial_cash:,.2f}")
        print(f"Commission Rate:    {self.portfolio.commission_rate*100:.2f}%")
        print(f"Position Size:      {self.position_size_pct*100:.0f}% (dynamic)")
        print(f"Watch List:         {', '.join(self.watch_list)}")
        print(f"Bitcoin:            {'✅' if self.enable_bitcoin else '❌'}")
        print(f"Check Interval:     {self.check_interval}s ({self.check_interval/60:.1f} min)")
        print(f"Max Drawdown:       {self.max_portfolio_drawdown*100:.0f}%")
        print(f"Risk Management:    {'✅ Enhanced' if self.volatility_adjustment else '❌ Basic'}")

        ai_mode_display = {
            "off": "❌ Rules Only",
            "validate": "🔀 Hybrid (AI Validates Rules)",
            "full": "🤖 Full AI-Driven"
        }
        print(f"AI Mode:            {ai_mode_display.get(self.ai_mode, self.ai_mode)}")
        if self.ai_mode != "off":
            print(f"AI Model:           {self.ai_model}")

        print(f"{'='*80}\n")
        sys.stdout.flush()

        while True:
            try:
                self.iteration += 1
                self.log(f"🔄 Iteration #{self.iteration}")

                # Update market regime periodically
                self.update_market_regime()
                self.log(f"📊 Market Regime: {self.market_regime}")

                # Check Bitcoin
                if self.enable_bitcoin:
                    self.check_bitcoin()

                # Check watch list
                for symbol in self.watch_list:
                    self.check_stock(symbol)

                # Log portfolio summary
                self.log_portfolio_summary()

                # Save state after each iteration
                self.persistence.save_state({"iteration": self.iteration})

                # Wait for next iteration with restart check
                remaining_time = self.check_interval
                while remaining_time > 0:
                    if self.restart_requested:
                        self.log("🔄 Performing graceful restart...")
                        self.restart_requested = False
                        break
                    time.sleep(min(1, remaining_time))  # Check every second for restart signal
                    remaining_time -= 1

                if self.restart_requested:
                    continue  # Restart the main loop

            except KeyboardInterrupt:
                self.log("\n🛑 Trading stopped by user")
                self.log_portfolio_summary()

                # Final report
                print(f"\n{'='*80}")
                print(f"📊 FINAL PERFORMANCE REPORT")
                print(f"{'='*80}")
                summary = self.portfolio.get_summary(self.current_prices)
                print(f"Started with:       €{summary['initial_cash']:,.2f}")
                print(f"Ended with:         €{summary['total_value']:,.2f}")
                print(f"Return:             €{summary['total_return']:+,.2f} ({summary['total_return_pct']:+.2f}%)")
                print(f"Total Fees:         €{summary['total_fees_paid']:,.2f}")
                print(f"Total Trades:       {summary['num_transactions']}")
                print(f"Time Period:        {self.iteration} iterations")

                if summary['num_transactions'] > 0:
                    wins = sum(1 for tx in self.portfolio.transactions if tx.get('profit_loss', 0) > 0)
                    losses = sum(1 for tx in self.portfolio.transactions if tx.get('profit_loss', 0) < 0)
                    sells = sum(1 for tx in self.portfolio.transactions if tx['type'] == 'SELL')
                    if sells > 0:
                        print(f"Winning Trades:     {wins}/{sells} ({(wins/sells)*100:.1f}%)")

                print(f"{'='*80}\n")
                break

            except Exception as e:
                self.log(f"[ERROR] Unexpected error: {str(e)}")
                time.sleep(60)


def main():
    """Main entry point for paper trading."""
    import argparse

    parser = argparse.ArgumentParser(description="Paper trading simulator with €10,000 capital")
    parser.add_argument(
        "-c",
        "--capital",
        type=float,
        default=10000.0,
        help="Initial capital in EUR (default: 10000)",
    )
    parser.add_argument(
        "-f",
        "--fee",
        type=float,
        default=0.001,
        help="Commission rate (default: 0.001 = 0.1%%)",
    )
    parser.add_argument(
        "-w",
        "--watch",
        nargs="+",
        default=["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN"],
        help="Stock symbols to trade",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=300,
        help="Check interval in seconds (default: 300)",
    )
    parser.add_argument(
        "-p",
        "--position-size",
        type=float,
        default=0.15,
        help="Position size as %% of portfolio (default: 0.15 = 15%%)",
    )
    parser.add_argument(
        "--no-bitcoin", action="store_true", help="Disable Bitcoin trading"
    )
    parser.add_argument(
        "--ai-mode",
        choices=["off", "validate", "full"],
        default="off",
        help="AI mode: off (rules only), validate (AI validates rules), full (AI-driven)",
    )
    parser.add_argument(
        "--ai-model",
        default="gemma4:latest",
        help="Ollama model for AI mode (default: gemma4:latest)",
    )

    args = parser.parse_args()

    trader = PaperTrader(
        initial_cash=args.capital,
        commission_rate=args.fee,
        watch_list=args.watch,
        check_interval=args.interval,
        position_size_pct=args.position_size,
        enable_bitcoin=not args.no_bitcoin,
        ai_mode=args.ai_mode,
        ai_model=args.ai_model,
    )

    trader.run()


if __name__ == "__main__":
    main()
