#!/usr/bin/env python3
"""
Test the market scanner to identify top opportunities.
"""
from stock_checker.market_scanner import MarketScanner

def main():
    print("Initializing Market Scanner...")
    scanner = MarketScanner()

    # Run comprehensive market analysis
    results = scanner.identify_best_opportunities()

    print("\n" + "="*70)
    print("SCAN COMPLETE")
    print("="*70)
    print(f"\nTotal crypto leaders found: {len(results['crypto_leaders'])}")
    print(f"Total stock breakouts found: {len(results['stock_breakouts'])}")
    print(f"Total recommendations: {len(results['recommendations'])}")
    print(f"\nScan timestamp: {results['scan_time']}")

if __name__ == "__main__":
    main()
