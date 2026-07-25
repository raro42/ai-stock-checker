#!/bin/bash

# Start paper trading simulator with €10,000 capital
# This will simulate real trading with virtual money and track performance

echo "Starting Paper Trading Simulator..."
echo ""
echo "Configuration:"
echo "  - Initial Capital: €10,000"
echo "  - Commission: 0.1% per trade"
echo "  - Position Size: 15% of portfolio per trade"
echo "  - Check Interval: 5 minutes"
echo ""
echo "The simulator will:"
echo "  - Execute real BUY/SELL orders with virtual money"
echo "  - Track portfolio value over time"
echo "  - Show profit/loss on each trade"
echo "  - Calculate total return including fees"
echo ""
echo "View logs with:"
echo "  docker logs -f ai-paper-trader"
echo ""
echo "Stop trading with:"
echo "  docker-compose down paper-trader"
echo ""

# Start the paper trader
docker-compose up -d paper-trader

echo ""
echo "✅ Paper trader started!"
echo ""
echo "View live trading:"
echo "  docker logs -f ai-paper-trader"
echo ""
echo "⚠️  Disclaimer: This is a simulation with virtual money."
echo "   Past performance does not guarantee future results."
echo ""
