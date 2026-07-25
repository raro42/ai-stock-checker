# Continuous Monitoring Guide

## Overview

The AI Stock Checker includes a continuous monitoring service that runs 24/7 and outputs buy/sell recommendations to Docker logs. This is ideal for automated trading signals and investment tracking.

## Quick Start

```bash
# Start monitoring with default watchlist
./monitor-start.sh

# View live recommendations
docker logs -f ai-stock-monitor
```

## How It Works

The monitor continuously:
1. Fetches real-time stock data from yfinance
2. Analyzes price momentum, volatility, and position
3. Generates buy/sell/hold recommendations with confidence levels
4. Outputs signals to Docker logs for easy viewing
5. Optionally runs AI analysis on significant signals

## Recommendation Logic

### Stock Recommendations

**BUY signals** are generated when:
- Strong positive momentum (>2% daily gain)
- Price near 52-week low (<20% of range)
- Low P/E ratio (<15)
- Score: +30 or higher

**SELL signals** are generated when:
- Negative momentum (<-2% daily drop)
- Price near 52-week high (>80% of range)
- High P/E ratio (>30)
- Score: -30 or lower

**HOLD** recommendations are filtered out to reduce noise.

### Bitcoin Recommendations

**BUY signals** for Bitcoin when:
- Strong multi-day uptrend (7d +10%, 30d +15%)
- Low volatility (<3%)
- Price near yearly low (<30% of range)
- Score: +40 or higher

**SELL signals** for Bitcoin when:
- Downtrend across timeframes
- High volatility (>10%)
- Price near yearly high (>85% of range)
- Score: -40 or lower

## Usage Examples

### Default Monitoring

Monitors: AAPL, TSLA, MSFT, GOOGL, AMZN, NVDA, META + Bitcoin
Check interval: 5 minutes (300 seconds)

```bash
docker-compose up -d monitor
docker logs -f ai-stock-monitor
```

### Custom Watchlist

```bash
docker run -d --name ai-stock-monitor --network host ai-stock-checker \
  python3 -m stock_checker.monitor \
  --watch AAPL TSLA NVDA AMD INTC \
  --interval 300
```

### Different Check Intervals

```bash
# Check every 1 minute (for active trading)
docker run -d --name ai-stock-monitor --network host ai-stock-checker \
  python3 -m stock_checker.monitor \
  --watch AAPL TSLA \
  --interval 60

# Check every 30 minutes (for long-term investing)
docker run -d --name ai-stock-monitor --network host ai-stock-checker \
  python3 -m stock_checker.monitor \
  --watch AAPL TSLA MSFT \
  --interval 1800
```

### Bitcoin Only

```bash
docker run -d --name ai-stock-monitor --network host ai-stock-checker \
  python3 -m stock_checker.monitor \
  --watch \
  --interval 300
```

### With AI Analysis

Requires Ollama running on host:

```bash
# Start Ollama first
ollama serve

# Then start monitor with AI
docker run -d --name ai-stock-monitor --network host ai-stock-checker \
  python3 -m stock_checker.monitor \
  --watch AAPL TSLA MSFT \
  --interval 300 \
  --analyze \
  --model llama2
```

### Disable Bitcoin Monitoring

```bash
docker run -d --name ai-stock-monitor --network host ai-stock-checker \
  python3 -m stock_checker.monitor \
  --watch AAPL TSLA MSFT \
  --interval 300 \
  --no-bitcoin
```

### Enable S&P 500 Movers

```bash
docker run -d --name ai-stock-monitor --network host ai-stock-checker \
  python3 -m stock_checker.monitor \
  --watch AAPL TSLA \
  --interval 300 \
  --sp500-movers
```

## Viewing Recommendations

### Live Streaming

```bash
# Follow logs in real-time
docker logs -f ai-stock-monitor
```

### Recent Logs

```bash
# Last 50 lines
docker logs --tail 50 ai-stock-monitor

# Last 5 minutes
docker logs --since 5m ai-stock-monitor
```

### Filtering Signals

```bash
# Only BUY signals
docker logs ai-stock-monitor | grep "🟢 BUY"

# Only SELL signals
docker logs ai-stock-monitor | grep "🔴 SELL"

# High confidence signals only
docker logs ai-stock-monitor | grep "HIGH"

# Specific stock
docker logs ai-stock-monitor | grep "AAPL"
```

### Save Logs to File

```bash
# Save all logs
docker logs ai-stock-monitor > trading_signals.log

# Continuously append to file
docker logs -f ai-stock-monitor >> trading_signals.log
```

## Log Format

Each recommendation includes:

```
================================================================================
[2025-11-29 17:30:45] 🟢 BUY AAPL | Confidence: HIGH | Score: +35
================================================================================
Price: $180.25

Reasons:
  • Strong daily momentum: +3.25%
  • Near 52-week low (18.5% of range) - potential value
  • Low P/E ratio (28.50) - potentially undervalued

💡 AI Insight:
Based on the current momentum and valuation metrics, AAPL shows strong
buy signals. The stock is recovering from recent lows with solid volume.
Consider entry for medium to long-term positions.

================================================================================
```

## Managing the Service

### Check Status

```bash
docker ps | grep ai-stock-monitor
```

### Restart Monitor

```bash
docker restart ai-stock-monitor
```

### Stop Monitor

```bash
docker stop ai-stock-monitor
docker rm ai-stock-monitor

# Or with docker-compose
docker-compose down monitor
```

### Update and Restart

```bash
# Rebuild with latest code
docker-compose build monitor

# Restart with new code
docker-compose up -d monitor
```

## Integration Tips

### Export to Trading System

```bash
# Stream to a file that your trading bot reads
docker logs -f ai-stock-monitor | tee -a signals.log

# Parse JSON output (add --json flag when available)
docker logs ai-stock-monitor | grep "BUY" | your-trading-script.py
```

### Email Alerts

```bash
# Monitor logs and send email on BUY signals
docker logs -f ai-stock-monitor | while read line; do
    if echo "$line" | grep -q "🟢 BUY"; then
        echo "$line" | mail -s "Stock BUY Signal" you@email.com
    fi
done
```

### Slack/Discord Webhooks

```bash
# Send signals to Slack/Discord
docker logs -f ai-stock-monitor | while read line; do
    if echo "$line" | grep -qE "BUY|SELL"; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"$line\"}" \
            YOUR_WEBHOOK_URL
    fi
done
```

## Customizing Watchlist

Edit `watchlist.txt`:

```bash
# Edit watchlist
nano watchlist.txt

# Restart monitor to apply changes
docker restart ai-stock-monitor
```

Or mount custom watchlist:

```bash
docker run -d --name ai-stock-monitor --network host \
  -v $(pwd)/my-watchlist.txt:/app/watchlist.txt \
  ai-stock-checker python3 -m stock_checker.monitor
```

## Troubleshooting

### No recommendations appearing

- Monitor only shows BUY/SELL signals, not HOLD
- Wait for market movement (volatility creates signals)
- Lower the check interval for more frequent checks
- Check logs for errors: `docker logs ai-stock-monitor | grep ERROR`

### High memory/CPU usage

- Increase check interval (--interval)
- Reduce watchlist size
- Disable AI analysis if not needed

### API rate limiting

- Increase check interval to avoid hitting yfinance rate limits
- Default 300s (5 min) is safe for moderate watchlists
- For large watchlists (>20 stocks), use 600s (10 min)

## Best Practices

1. **Start with defaults**: Use the default watchlist and interval first
2. **Monitor logs regularly**: Check logs daily to understand signal patterns
3. **Combine with research**: Don't trade solely on automated signals
4. **Adjust intervals**: Find the right balance for your strategy
5. **Use AI selectively**: Enable AI analysis for important signals only
6. **Save logs**: Keep historical logs for backtesting
7. **Set alerts**: Integrate with notification systems for important signals

## Disclaimer

This tool is for informational purposes only. Always do your own research and consider consulting with financial advisors before making investment decisions. Past performance does not guarantee future results.
