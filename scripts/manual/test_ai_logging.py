#!/usr/bin/env python3
"""
Quick test to demonstrate AI conversation logging.
"""

import sys
sys.path.insert(0, '/Users/raro42/projects/ai-stock-checker')

from stock_checker.ai_recommender import AIRecommender

# Sample Bitcoin data
btc_data = {
    "symbol": "BTC-USD",
    "name": "Bitcoin",
    "current_price": 90761.29,
    "change_1d": 0.54,
    "change_7d": -2.31,
    "change_30d": 12.45,
    "volatility_30d": 15.2,
    "52_week_high": 108000,
    "52_week_low": 38500,
}

print("=" * 80)
print("🧪 Testing AI Conversation Logging")
print("=" * 80)
print(f"\nUsing model: llama3.2")
print(f"Testing with: {btc_data['symbol']} @ ${btc_data['current_price']:,.2f}\n")

# Initialize AI recommender with llama3.2 (faster for testing)
recommender = AIRecommender(model="llama3.2")

# Get recommendation - this should show our new logging!
print("Calling AI recommender...")
print()

recommendation = recommender.get_bitcoin_ai_recommendation(btc_data)

print()
print("=" * 80)
print("✅ Test Complete!")
print("=" * 80)
print(f"\nRecommendation: {recommendation['action']}")
print(f"Confidence: {recommendation['confidence']}")
print(f"Score: {recommendation['score']}")
print(f"Reasoning: {recommendation['reasons'][0][:100]}...")
