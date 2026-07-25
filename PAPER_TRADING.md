# Paper Trading Guide

## Overview

The paper trading simulator lets you test the AI Stock Checker's recommendation engine with **virtual €10,000** to see if the strategy would be profitable in real market conditions.

## How It Works

1. **Starts with €10,000** virtual capital
2. **Monitors stocks** every 5 minutes (configurable)
3. **Executes trades** based on BUY/SELL recommendations
4. **Tracks performance** including all fees and profit/loss
5. **Outputs to logs** for easy monitoring

## Trading Rules

### Position Sizing
- Each position is **15% of portfolio value** by default
- Maximum diversification across multiple stocks
- Adjustable with `--position-size` parameter

### Commission Fees
- **0.1% per trade** (both buy and sell)
- Realistic fees similar to most brokers
- Adjustable with `--fee` parameter

### Entry Rules (BUY)
Buys when **HIGH** or **MEDIUM** confidence and:
- Strong positive momentum (>2% daily gain)
- Price near 52-week low (<20% of range)
- Low P/E ratio (<15) indicates undervaluation
- Combined score of +30 or higher

### Exit Rules (SELL)
Sells entire position when **HIGH** or **MEDIUM** confidence and:
- Negative momentum (<-2% daily drop)
- Price near 52-week high (>80% of range)
- High P/E ratio (>30) indicates overvaluation
- Combined score of -30 or lower

## Quick Start

### Default Configuration

```bash
# Start with defaults (€10,000, 5 stocks, 5-minute checks)
./paper-trade-start.sh

# Watch live trading
docker logs -f ai-paper-trader
```

Default settings:
- Capital: €10,000
- Stocks: AAPL, TSLA, MSFT, GOOGL, AMZN
- Bitcoin: Enabled
- Interval: 300 seconds (5 minutes)
- Position size: 15% of portfolio
- Commission: 0.1% per trade

### Custom Configuration

```bash
# Different capital and stocks
docker run -d --name ai-paper-trader --network host ai-stock-checker \
  python3 -m stock_checker.paper_trader \
  --capital 20000 \
  --watch AAPL NVDA AMD \
  --interval 600

# More aggressive position sizing (25% per position)
docker run -d --name ai-paper-trader --network host ai-stock-checker \
  python3 -m stock_checker.paper_trader \
  --capital 10000 \
  --position-size 0.25 \
  --interval 300

# Higher fees (0.25% like some crypto exchanges)
docker run -d --name ai-paper-trader --network host ai-stock-checker \
  python3 -m stock_checker.paper_trader \
  --capital 10000 \
  --fee 0.0025 \
  --watch AAPL TSLA MSFT

# Bitcoin only
docker run -d --name ai-paper-trader --network host ai-stock-checker \
  python3 -m stock_checker.paper_trader \
  --capital 10000 \
  --watch \
  --interval 300

# Without Bitcoin
docker run -d --name ai-paper-trader --network host ai-stock-checker \
  python3 -m stock_checker.paper_trader \
  --capital 10000 \
  --watch AAPL TSLA MSFT \
  --no-bitcoin
```

## Reading the Output

### Portfolio Summary (Every Iteration)

```
================================================================================
💼 PORTFOLIO SUMMARY
================================================================================
Initial Capital:    €10,000.00
Current Cash:       €7,234.50
Holdings Value:     €3,156.80
Total Value:        €10,391.30
Total Return:       €+391.30 (+3.91%)
Fees Paid:          €21.40
Transactions:       8

Open Positions:
--------------------------------------------------------------------------------
🟢 AAPL     Qty: 12.50    Avg Buy: €178.20  Current: €182.40  P/L: €+52.50 (+2.95%)
🟢 TSLA     Qty: 5.00     Avg Buy: €245.80  Current: €251.20  P/L: €+27.00 (+2.20%)
🔴 MSFT     Qty: 8.00     Avg Buy: €385.40  Current: €380.10  P/L: €-42.40 (-1.38%)
================================================================================
```

### Buy Order

```
================================================================================
🟢 BUY ORDER EXECUTED
================================================================================
Symbol:       AAPL
Confidence:   HIGH
Score:        +35
Quantity:     12.5000
Price:        €178.20
Cost:         €2,227.50
Commission:   €2.23
Total Cost:   €2,229.73
Cash Left:    €7,770.27
Reasons:
  • Strong daily momentum: +3.25%
  • Near 52-week low (18.5% of range) - potential value
  • Low P/E ratio (28.50) - potentially undervalued
================================================================================
```

### Sell Order

```
================================================================================
🔴 SELL ORDER EXECUTED
================================================================================
Symbol:       AAPL
Confidence:   HIGH
Score:        -32
Quantity:     12.5000
Sell Price:   €182.40
Buy Price:    €178.20
Proceeds:     €2,280.00
Commission:   €2.28
Net Proceeds: €2,277.72
🟢 Profit/Loss: €+52.50 (+2.36%)
Cash Now:     €10,047.99
Reasons:
  • Negative momentum: -2.5%
  • Near 52-week high (82.5% of range) - potentially overbought
================================================================================
```

### Final Report (On Stop)

```
================================================================================
📊 FINAL PERFORMANCE REPORT
================================================================================
Started with:       €10,000.00
Ended with:         €10,525.40
Return:             €+525.40 (+5.25%)
Total Fees:         €47.80
Total Trades:       16
Time Period:        48 iterations
Winning Trades:     6/8 (75.0%)
================================================================================
```

## Viewing Logs

### Live Streaming

```bash
docker logs -f ai-paper-trader
```

### Filter by Action

```bash
# Only see buy orders
docker logs ai-paper-trader | grep "BUY ORDER"

# Only see sell orders
docker logs ai-paper-trader | grep "SELL ORDER"

# Portfolio summaries only
docker logs ai-paper-trader | grep "PORTFOLIO SUMMARY" -A 15
```

### Export to File

```bash
# Save all logs
docker logs ai-paper-trader > my_trading_results.log

# Continuously append
docker logs -f ai-paper-trader >> trading_log.txt
```

## Managing the Simulator

### Check Status

```bash
docker ps | grep ai-paper-trader
```

### Stop and View Final Report

```bash
# Stop gracefully (CTRL+C equivalent)
docker stop ai-paper-trader

# View final report in logs
docker logs --tail 50 ai-paper-trader
```

### Restart with Same Config

```bash
docker restart ai-paper-trader
```

### Fresh Start

```bash
# Remove old container
docker stop ai-paper-trader && docker rm ai-paper-trader

# Start new simulation
./paper-trade-start.sh
```

## Performance Expectations

### Realistic Expectations

⚠️ **Important**: This is a **simulated trading system** with several caveats:

1. **Market conditions vary**: Bull markets will show better returns than bear markets
2. **No guarantee of profit**: Past performance doesn't predict future results
3. **Slippage not modeled**: Real trades may execute at different prices
4. **Limited indicators**: Uses momentum and valuation, not technical analysis
5. **No risk management**: Doesn't implement stop-losses or position limits

### What Affects Profitability

✅ **Favorable conditions**:
- Trending markets (strong up or down movements)
- High volatility (creates trading opportunities)
- Large cap stocks (more liquidity, better data)
- Longer time horizons (more trades to average out)

❌ **Challenging conditions**:
- Sideways/choppy markets
- Low volatility (fewer signals)
- Small cap stocks (less reliable data)
- Very short time periods (high variance)

### Measuring Success

- **Break-even**: 0% return (you kept your capital)
- **Beat fees**: >1% return (covered trading costs)
- **Beat cash**: >2-3% return (better than savings account)
- **Beat market**: >8-10% annual return (S&P 500 average)
- **Strong performance**: >15% annual return

## Optimization Tips

### 1. Adjust Position Sizing

```bash
# Conservative (10% per position)
--position-size 0.10

# Default (15% per position)
--position-size 0.15

# Aggressive (20% per position)
--position-size 0.20
```

### 2. Change Check Frequency

```bash
# Day trading (every 1 minute - high activity)
--interval 60

# Active trading (every 5 minutes)
--interval 300

# Swing trading (every 30 minutes)
--interval 1800

# Position trading (every 4 hours)
--interval 14400
```

### 3. Select Different Assets

```bash
# Tech-focused
--watch AAPL MSFT GOOGL NVDA AMD TSLA

# Diversified
--watch AAPL JPM JNJ XOM PG WMT

# Crypto-heavy
--watch BTC-USD ETH-USD --no-bitcoin

# Large cap only
--watch AAPL MSFT GOOGL AMZN META
```

## Limitations

1. **Execution assumptions**: Assumes instant fills at market price
2. **No slippage**: Real orders may get worse prices on large volumes
3. **Perfect data**: Assumes yfinance data is accurate and timely
4. **No market hours**: Trades 24/7, real markets have hours
5. **No circuit breakers**: Doesn't model trading halts
6. **No dividends**: Doesn't track dividend income
7. **No margin**: Cash-only, no leverage
8. **No shorts**: Only long positions

## FAQ

**Q: Will this make me money in real trading?**
A: Not guaranteed. Use this to evaluate the strategy first.

**Q: Can I use this for live trading?**
A: This is simulation only. Never connect real money without thorough testing.

**Q: How long should I run it?**
A: At least 100 iterations (8-10 hours at 5min intervals) for meaningful results.

**Q: What's a good return percentage?**
A: Depends on timeframe. 1% per day is excellent. 10% per year beats most funds.

**Q: Why am I losing money?**
A: Markets may be choppy, fees add up, or the strategy needs tuning. Try longer intervals.

**Q: Can I backtest historical data?**
A: Not yet - currently live simulation only. Historical backtesting is a future feature.

## Disclaimer

⚠️ **WARNING**: This tool is for **educational and simulation purposes only**.

- Does not constitute financial advice
- Past performance doesn't guarantee future results
- Trading involves substantial risk of loss
- Never trade with money you cannot afford to lose
- Consult a licensed financial advisor before investing

The developers are not responsible for any financial losses incurred from using this software.
