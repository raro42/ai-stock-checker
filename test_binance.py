#!/usr/bin/env python3

from stock_checker.data_comparator import DataComparator

print("Testing Binance vs yfinance data sources...")
print("="*60)

comp = DataComparator()
results = comp.compare_crypto_sources(['BTC-USD', 'ETH-USD', 'SOL-USD', 'DOGE-USD'])

print("\nFinal Recommendation:", results['summary']['recommendation'])
