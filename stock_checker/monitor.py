#!/usr/bin/env python3

import json
import time
import sys
from datetime import datetime
from typing import List, Optional

from stock_checker.fetcher import StockFetcher
from stock_checker.market_analyzer import MarketAnalyzer
from stock_checker.recommender import RecommendationEngine
from stock_checker.ai_recommender import AIRecommender
from stock_checker.ai_analyzer import OllamaAnalyzer


class ContinuousMonitor:
    """Continuously monitor stocks and output buy/sell recommendations."""

    def __init__(
        self,
        watch_list: List[str],
        check_interval: int = 300,
        enable_ai: bool = False,
        ai_model: str = "llama2",
        enable_bitcoin: bool = True,
        enable_sp500_movers: bool = False,
        ai_mode: str = "off",
    ):
        """
        Initialize continuous monitor.

        Args:
            watch_list: List of stock symbols to monitor
            check_interval: Seconds between checks (default: 300 = 5 minutes)
            enable_ai: Enable AI analysis (requires Ollama)
            ai_model: Ollama model to use
            enable_bitcoin: Monitor Bitcoin
            enable_sp500_movers: Check S&P 500 top movers
        """
        self.watch_list = watch_list
        self.check_interval = check_interval
        self.enable_ai = enable_ai
        self.ai_model = ai_model
        self.enable_bitcoin = enable_bitcoin
        self.enable_sp500_movers = enable_sp500_movers

        self.fetcher = StockFetcher()
        self.market_analyzer = MarketAnalyzer()
        self.recommender = RecommendationEngine()
        self.ai_analyzer = OllamaAnalyzer(model=ai_model) if enable_ai else None
        self.ai_recommender = AIRecommender(ai_model) if ai_mode != "off" else None
        self.ai_mode = ai_mode

        self.iteration = 0

    def log_recommendation(self, recommendation: dict, ai_insight: Optional[str] = None):
        """Log a recommendation to stdout (visible in docker logs)."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        symbol = recommendation["symbol"]
        action = recommendation["action"]
        confidence = recommendation["confidence"]
        score = recommendation["score"]
        price = recommendation.get("current_price", "N/A")
        reasons = recommendation.get("reasons", [])

        # Color codes for terminal (optional, works in most environments)
        if action == "BUY":
            action_display = f"🟢 {action}"
        elif action == "SELL":
            action_display = f"🔴 {action}"
        else:
            action_display = f"🟡 {action}"

        print(f"\n{'='*80}")
        print(f"[{timestamp}] {action_display} {symbol} | Confidence: {confidence} | Score: {int(score):+d}")
        print(f"{'='*80}")
        print(f"Price: ${price}")
        print(f"\nReasons:")
        for reason in reasons:
            print(f"  • {reason}")

        if ai_insight:
            print(f"\n💡 AI Insight:")
            print(f"{ai_insight}")

        print(f"{'='*80}\n")
        sys.stdout.flush()

    def check_stock(self, symbol: str):
        """Check a single stock and output recommendation."""
        try:
            data = self.fetcher.get_stock_info(symbol)

            # Get recommendation based on AI mode
            if self.ai_mode == "full":
                recommendation = self.ai_recommender.get_ai_recommendation(data)
            elif self.ai_mode == "validate":
                rule_rec = self.recommender.analyze_stock_recommendation(data)
                recommendation = self.ai_recommender.validate_recommendation(rule_rec, data)
            else:
                recommendation = self.recommender.analyze_stock_recommendation(data)

            ai_insight = None
            if self.enable_ai and recommendation["action"] in ["BUY", "SELL"]:
                try:
                    ai_insight = self.ai_analyzer.analyze_stock(data)
                except Exception as e:
                    ai_insight = f"AI analysis failed: {str(e)}"

            # Only log BUY/SELL recommendations, skip HOLD to reduce noise
            if recommendation["action"] in ["BUY", "SELL"]:
                self.log_recommendation(recommendation, ai_insight)

        except Exception as e:
            print(f"[ERROR] Failed to check {symbol}: {str(e)}", file=sys.stderr)
            sys.stderr.flush()

    def check_bitcoin(self):
        """Check Bitcoin and output recommendation."""
        try:
            data = self.market_analyzer.analyze_bitcoin_for_investment()

            # Get recommendation based on AI mode
            if self.ai_mode == "full":
                recommendation = self.ai_recommender.get_bitcoin_ai_recommendation(data)
            elif self.ai_mode == "validate":
                rule_rec = self.recommender.analyze_bitcoin_recommendation(data)
                btc_stock_data = {
                    **data,
                    "symbol": "BTC-USD",
                    "name": "Bitcoin",
                    "current_price": data.get("current_price"),
                }
                recommendation = self.ai_recommender.validate_recommendation(rule_rec, btc_stock_data)
            else:
                recommendation = self.recommender.analyze_bitcoin_recommendation(data)

            ai_insight = None
            if self.enable_ai and recommendation["action"] in ["BUY", "SELL"]:
                try:
                    btc_summary = {
                        "symbol": "BTC-USD",
                        "name": "Bitcoin",
                        "current_price": data.get("current_price"),
                        "change_30d": data.get("change_30d"),
                        "volatility_30d": data.get("volatility_30d"),
                    }
                    ai_insight = self.ai_analyzer.analyze_stock(btc_summary)
                except Exception as e:
                    ai_insight = f"AI analysis failed: {str(e)}"

            # Always log Bitcoin recommendations
            self.log_recommendation(recommendation, ai_insight)

        except Exception as e:
            print(f"[ERROR] Failed to check Bitcoin: {str(e)}", file=sys.stderr)
            sys.stderr.flush()

    def check_sp500_movers(self):
        """Check S&P 500 top movers."""
        try:
            movers = self.market_analyzer.get_top_movers(period="1d", limit=5)

            if movers:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n{'='*80}")
                print(f"[{timestamp}] 📊 S&P 500 TOP 5 MOVERS")
                print(f"{'='*80}")

                for i, mover in enumerate(movers, 1):
                    symbol = mover["symbol"]
                    change_pct = mover["change_pct"]
                    price = mover["current_price"]

                    if change_pct > 0:
                        direction = "🟢"
                    else:
                        direction = "🔴"

                    print(f"{i}. {direction} {symbol:<8} ${price:<10.2f} {change_pct:+.2f}%")

                print(f"{'='*80}\n")
                sys.stdout.flush()

        except Exception as e:
            print(f"[ERROR] Failed to check S&P 500 movers: {str(e)}", file=sys.stderr)
            sys.stderr.flush()

    def run(self):
        """Run continuous monitoring loop."""
        print(f"\n{'='*80}")
        print(f"🚀 AI STOCK CHECKER - CONTINUOUS MONITORING")
        print(f"{'='*80}")
        print(f"Watch List: {', '.join(self.watch_list)}")
        print(f"Check Interval: {self.check_interval}s ({self.check_interval/60:.1f} min)")
        print(f"Bitcoin Monitoring: {'✅' if self.enable_bitcoin else '❌'}")
        print(f"S&P 500 Movers: {'✅' if self.enable_sp500_movers else '❌'}")
        print(f"AI Analysis: {'✅' if self.enable_ai else '❌'}")
        if self.enable_ai:
            print(f"AI Model: {self.ai_model}")

        ai_mode_display = {
            "off": "❌ Rules Only",
            "validate": "🔀 Hybrid (AI Validates)",
            "full": "🤖 Full AI-Driven"
        }
        print(f"AI Mode: {ai_mode_display.get(self.ai_mode, self.ai_mode)}")

        print(f"{'='*80}\n")
        sys.stdout.flush()

        while True:
            try:
                self.iteration += 1
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                print(f"\n[{timestamp}] 🔄 Iteration #{self.iteration}")
                sys.stdout.flush()

                # Check Bitcoin
                if self.enable_bitcoin:
                    self.check_bitcoin()

                # Check watch list
                for symbol in self.watch_list:
                    self.check_stock(symbol)

                # Check S&P 500 movers
                if self.enable_sp500_movers:
                    self.check_sp500_movers()

                # Wait for next iteration
                next_check = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n[{timestamp}] ⏸️  Sleeping for {self.check_interval}s...")
                print(f"Next check at approximately: {next_check}")
                sys.stdout.flush()

                time.sleep(self.check_interval)

            except KeyboardInterrupt:
                print("\n\n[INFO] Monitoring stopped by user")
                sys.stdout.flush()
                break
            except Exception as e:
                print(f"\n[ERROR] Unexpected error: {str(e)}", file=sys.stderr)
                sys.stderr.flush()
                time.sleep(60)  # Wait a minute before retrying


def main():
    """Main entry point for continuous monitoring."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Continuously monitor stocks and output buy/sell recommendations"
    )
    parser.add_argument(
        "-w",
        "--watch",
        nargs="+",
        default=["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN"],
        help="Stock symbols to monitor (default: AAPL TSLA MSFT GOOGL AMZN)",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=300,
        help="Check interval in seconds (default: 300 = 5 min)",
    )
    parser.add_argument(
        "-a",
        "--analyze",
        action="store_true",
        help="Enable AI analysis (requires Ollama)",
    )
    parser.add_argument(
        "-m",
        "--model",
        default="llama2",
        help="Ollama model to use (default: llama2)",
    )
    parser.add_argument(
        "--no-bitcoin",
        action="store_true",
        help="Disable Bitcoin monitoring",
    )
    parser.add_argument(
        "--sp500-movers",
        action="store_true",
        help="Enable S&P 500 top movers monitoring",
    )
    parser.add_argument(
        "--ai-mode",
        choices=["off", "validate", "full"],
        default="off",
        help="AI mode: off (rules only), validate (AI validates), full (AI-driven)",
    )

    args = parser.parse_args()

    monitor = ContinuousMonitor(
        watch_list=args.watch,
        check_interval=args.interval,
        enable_ai=args.analyze,
        ai_model=args.model,
        enable_bitcoin=not args.no_bitcoin,
        enable_sp500_movers=args.sp500_movers,
        ai_mode=args.ai_mode,
    )

    monitor.run()


if __name__ == "__main__":
    main()
