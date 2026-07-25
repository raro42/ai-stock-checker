#!/usr/bin/env python3

from typing import Dict, List
from .binance_fetcher import BinanceFetcher
from .fetcher import StockFetcher
import time


class DataComparator:
    """Compare data quality from multiple sources."""

    def __init__(self):
        self.binance = BinanceFetcher()
        self.yfinance = StockFetcher()

    def compare_crypto_sources(self, crypto_symbols: List[str]) -> Dict:
        """
        Compare Binance vs yfinance for crypto prices.

        Args:
            crypto_symbols: List like ['BTC-USD', 'ETH-USD']

        Returns comparison report with:
            - Price differences
            - Latency measurements
            - Data freshness
            - Recommendations
        """
        results = {
            "timestamp": time.time(),
            "comparisons": {},
            "summary": {
                "binance_faster": 0,
                "binance_available": 0,
                "price_diffs": [],
                "avg_latency_binance": 0,
                "avg_latency_yfinance": 0
            }
        }

        for yf_symbol in crypto_symbols:
            print(f"\n{'='*60}")
            print(f"Comparing: {yf_symbol}")
            print(f"{'='*60}")

            # Binance fetch
            binance_symbol = self.binance.convert_symbol(yf_symbol)
            start_binance = time.time()
            binance_data = self.binance.get_crypto_price(binance_symbol)
            latency_binance = (time.time() - start_binance) * 1000

            # yfinance fetch
            start_yf = time.time()
            yf_data = self.yfinance.get_stock_info(yf_symbol)
            latency_yf = (time.time() - start_yf) * 1000

            comparison = {
                "symbol": yf_symbol,
                "binance": {
                    "price": binance_data["current_price"] if binance_data else None,
                    "latency_ms": latency_binance,
                    "available": binance_data is not None,
                    "change_24h": binance_data.get("change_24h") if binance_data else None
                },
                "yfinance": {
                    "price": yf_data.get("current_price"),
                    "latency_ms": latency_yf,
                    "available": yf_data.get("current_price") is not None,
                    "change_24h": None  # yfinance doesn't provide this directly
                }
            }

            # Calculate price difference
            if binance_data and yf_data.get("current_price"):
                price_diff = abs(binance_data["current_price"] - yf_data["current_price"])
                price_diff_pct = (price_diff / binance_data["current_price"]) * 100
                comparison["price_diff"] = price_diff
                comparison["price_diff_pct"] = price_diff_pct
                results["summary"]["price_diffs"].append(price_diff_pct)
            else:
                comparison["price_diff"] = None
                comparison["price_diff_pct"] = None

            # Print comparison
            print(f"Binance:  €{comparison['binance']['price']:.2f} ({latency_binance:.0f}ms) {'✅' if binance_data else '❌'}")
            print(f"yfinance: €{comparison['yfinance']['price']:.2f} ({latency_yf:.0f}ms) {'✅' if yf_data.get('current_price') else '❌'}")

            if comparison["price_diff"]:
                print(f"Diff:     €{comparison['price_diff']:.2f} ({comparison['price_diff_pct']:.3f}%)")

            if binance_data and binance_data.get("change_24h"):
                print(f"24h Change (Binance): {binance_data['change_24h']:+.2f}%")

            results["comparisons"][yf_symbol] = comparison

            # Update summary
            if binance_data:
                results["summary"]["binance_available"] += 1
            if latency_binance < latency_yf:
                results["summary"]["binance_faster"] += 1

        # Calculate averages
        if results["summary"]["price_diffs"]:
            results["summary"]["avg_price_diff_pct"] = sum(results["summary"]["price_diffs"]) / len(results["summary"]["price_diffs"])

        # Generate recommendation
        binance_win_rate = (results["summary"]["binance_faster"] / len(crypto_symbols)) * 100
        results["summary"]["recommendation"] = "Binance" if binance_win_rate > 50 else "yfinance"

        print(f"\n{'='*60}")
        print(f"SUMMARY")
        print(f"{'='*60}")
        print(f"Binance faster:    {results['summary']['binance_faster']}/{len(crypto_symbols)} ({binance_win_rate:.0f}%)")
        print(f"Avg price diff:    {results['summary'].get('avg_price_diff_pct', 0):.3f}%")
        print(f"Recommendation:    {results['summary']['recommendation']}")
        print(f"{'='*60}\n")

        return results
