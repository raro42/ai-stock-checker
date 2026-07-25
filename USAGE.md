# AI Stock Checker - Usage Guide

## Quick Start with Docker

### Build the Docker image:
```bash
docker build -t ai-stock-checker .
```

Or use docker-compose:
```bash
docker-compose build
```

### Run commands:

#### Get current stock information:
```bash
docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli info AAPL
```

#### Get stock info with AI analysis:
```bash
docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli info AAPL --analyze
```

#### Get historical data:
```bash
docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli history TSLA -p 1mo
```

#### Analyze Bitcoin:
```bash
docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli bitcoin --analyze
```

#### Get S&P 500 top movers:
```bash
docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli movers -l 10
```

#### Interactive shell:
```bash
docker run --rm -it --network host -v "$(pwd):/app" ai-stock-checker bash
```

Then inside the container:
```bash
python3 -m stock_checker.cli info AAPL
python3 -m stock_checker.cli info AAPL --analyze
python3 -m stock_checker.cli history MSFT -p 3mo
```

## Commands

### `info` - Get current stock information
```bash
python3 -m stock_checker.cli info <SYMBOL> [options]
```

Options:
- `-a, --analyze`: Run AI analysis using Ollama
- `-m, --model MODEL`: Specify Ollama model (default: llama2)
- `--json`: Output raw JSON data

Examples:
```bash
python3 -m stock_checker.cli info AAPL
python3 -m stock_checker.cli info TSLA --analyze
python3 -m stock_checker.cli info MSFT --analyze --model llama3
python3 -m stock_checker.cli info GOOGL --json
```

### `history` - Get historical stock data
```bash
python3 -m stock_checker.cli history <SYMBOL> [options]
```

Options:
- `-p, --period PERIOD`: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
- `-i, --interval INTERVAL`: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
- `--json`: Output raw JSON data

Examples:
```bash
python3 -m stock_checker.cli history AAPL -p 1mo
python3 -m stock_checker.cli history TSLA -p 6mo -i 1wk
python3 -m stock_checker.cli history MSFT -p 1y --json
```

### `bitcoin` - Analyze Bitcoin for investment
```bash
python3 -m stock_checker.cli bitcoin [options]
```

Options:
- `-a, --analyze`: Run AI analysis on Bitcoin data
- `-m, --model MODEL`: Specify Ollama model (default: llama2)
- `--json`: Output raw JSON data

Examples:
```bash
python3 -m stock_checker.cli bitcoin
python3 -m stock_checker.cli bitcoin --analyze
python3 -m stock_checker.cli bitcoin --analyze --model llama3
python3 -m stock_checker.cli bitcoin --json
```

Features:
- Current price and 24h volume
- Price changes (1d, 7d, 30d)
- 30-day volatility metric
- Momentum analysis (uptrend/downtrend/sideways)
- Risk level assessment
- AI-powered investment insights (with --analyze)

### `movers` - Get top S&P 500 movers
```bash
python3 -m stock_checker.cli movers [options]
```

Options:
- `-l, --limit NUM`: Number of top movers to show (default: 10)
- `-p, --period PERIOD`: Period for comparison (1d, 5d, 1mo)
- `-a, --analyze`: Run AI analysis on the top mover
- `-m, --model MODEL`: Specify Ollama model (default: llama2)
- `--json`: Output raw JSON data

Examples:
```bash
python3 -m stock_checker.cli movers
python3 -m stock_checker.cli movers -l 20
python3 -m stock_checker.cli movers -p 5d -l 15
python3 -m stock_checker.cli movers --analyze
python3 -m stock_checker.cli movers --json
```

Features:
- Analyzes 100 major S&P 500 stocks
- Shows stocks with biggest price movements
- Displays price, change amount, and change percentage
- Optional AI analysis of the top mover

## Automation

### Manual Automation Script
Run automated analysis that checks Bitcoin, S&P 500 movers, and key tech stocks:

```bash
./automate.sh
```

This will:
- Analyze Bitcoin for investment
- Fetch top 10 S&P 500 movers
- Check AAPL, MSFT, GOOGL, AMZN, TSLA
- Save all reports to `analysis_reports/` directory

### Scheduled Automation (Cron)
Set up automated analysis on a schedule. See `cron-example.txt` for examples:

```bash
# Edit your crontab
crontab -e

# Example: Bitcoin analysis every day at 9 AM
0 9 * * * cd /path/to/ai-stock-checker && docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli bitcoin --analyze >> logs/bitcoin.log 2>&1

# Example: S&P 500 movers every weekday at 4:30 PM (after market close)
30 16 * * 1-5 cd /path/to/ai-stock-checker && docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli movers -l 10 >> logs/movers.log 2>&1
```

Create logs directory first:
```bash
mkdir -p logs
```

## Running Tests

Inside the Docker container:
```bash
docker run --rm ai-stock-checker pytest
```

Or interactively:
```bash
docker run --rm -it --network host -v "$(pwd):/app" ai-stock-checker bash
pytest
```

## AI Analysis with Ollama

To use AI analysis features:

1. Make sure Ollama is running on your host machine:
   ```bash
   ollama serve
   ```

2. Pull a model (if not already available):
   ```bash
   ollama pull llama2
   ```

3. Run stock analysis with the `--analyze` flag:
   ```bash
   docker run --rm --network host ai-stock-checker python3 -m stock_checker.cli info AAPL --analyze
   ```

The `--network host` flag allows the container to access Ollama running on localhost:11434.

## Using Podman Instead of Docker

Replace `docker` with `podman` in all commands:

```bash
podman build -t ai-stock-checker .
podman run --rm --network host ai-stock-checker python3 -m stock_checker.cli info AAPL
```

## Configuration

### Ollama Settings
Edit `stock_checker/ai_analyzer.py` to change:
- Base URL (default: http://localhost:11434)
- Default model (default: llama2)

### Available Stock Data
The stock fetcher uses yfinance, which supports:
- US stocks (AAPL, TSLA, MSFT, etc.)
- International stocks (use exchange suffix, e.g., 0700.HK)
- ETFs, indices, currencies, and cryptocurrencies
- Bitcoin via BTC-USD ticker

## Troubleshooting

### "Failed to fetch data"
- Check that the stock symbol is valid
- Verify internet connection
- Some symbols may require exchange suffixes

### "Error connecting to Ollama"
- Ensure Ollama is running: `ollama serve`
- Check that you're using `--network host` with Docker
- Verify Ollama is accessible at http://localhost:11434

### Import errors
- Rebuild the Docker image: `docker build -t ai-stock-checker .`
- Ensure all files are in the correct locations
