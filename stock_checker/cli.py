#!/usr/bin/env python3

import argparse
import json
import sys
from typing import Optional

from stock_checker.fetcher import StockFetcher
from stock_checker.ai_analyzer import OllamaAnalyzer
from stock_checker.market_analyzer import MarketAnalyzer


def format_stock_info(data: dict) -> str:
    """Format stock information for display."""
    lines = [
        f"\n{'='*60}",
        f"Stock: {data.get('name', 'N/A')} ({data.get('symbol', 'N/A')})",
        f"{'='*60}",
        f"Current Price:    ${data.get('current_price', 'N/A')}",
        f"Previous Close:   ${data.get('previous_close', 'N/A')}",
        f"Day Range:        ${data.get('day_low', 'N/A')} - ${data.get('day_high', 'N/A')}",
        f"52 Week Range:    ${data.get('52_week_low', 'N/A')} - ${data.get('52_week_high', 'N/A')}",
        f"Volume:           {data.get('volume', 'N/A'):,}" if data.get('volume') else "Volume:           N/A",
        f"Market Cap:       ${data.get('market_cap', 'N/A'):,}" if data.get('market_cap') else "Market Cap:       N/A",
        f"P/E Ratio:        {data.get('pe_ratio', 'N/A')}",
        f"Dividend Yield:   {data.get('dividend_yield', 'N/A')}",
        f"{'='*60}\n",
    ]
    return "\n".join(lines)


def format_historical_summary(data: dict) -> str:
    """Format historical data summary for display."""
    summary = data.get("summary", {})
    lines = [
        f"\n{'='*60}",
        f"Historical Data: {data.get('symbol', 'N/A')}",
        f"Period: {data.get('period', 'N/A')} | Interval: {data.get('interval', 'N/A')}",
        f"{'='*60}",
        f"Date Range:       {summary.get('start_date', 'N/A')} to {summary.get('end_date', 'N/A')}",
        f"Records:          {summary.get('num_records', 'N/A')}",
        f"Avg Volume:       {summary.get('avg_volume', 0):,.0f}",
        f"Price Change:     ${summary.get('price_change', 0):.2f}",
        f"Change %:         {summary.get('price_change_pct', 0):.2f}%",
        f"{'='*60}\n",
    ]
    return "\n".join(lines)


def cmd_info(args):
    """Get current stock information."""
    fetcher = StockFetcher()
    try:
        data = fetcher.get_stock_info(args.symbol)
        print(format_stock_info(data))

        if args.analyze:
            print("AI Analysis (this may take a moment)...")
            analyzer = OllamaAnalyzer(model=args.model)
            analysis = analyzer.analyze_stock(data)
            print(f"\n{analysis}\n")

        if args.json:
            print(json.dumps(data, indent=2))

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_history(args):
    """Get historical stock data."""
    fetcher = StockFetcher()
    try:
        data = fetcher.get_historical_data(args.symbol, period=args.period, interval=args.interval)
        print(format_historical_summary(data))

        if args.json:
            print(json.dumps(data, indent=2))

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_bitcoin(args):
    """Analyze Bitcoin for investment."""
    analyzer = MarketAnalyzer()
    try:
        print("\nAnalyzing Bitcoin...")
        data = analyzer.analyze_bitcoin_for_investment()

        lines = [
            f"\n{'='*60}",
            f"Bitcoin Investment Analysis",
            f"{'='*60}",
            f"Current Price:      ${data.get('current_price', 'N/A'):,.2f}",
            f"24h Volume:         {data.get('24h_volume', 'N/A'):,}" if data.get('24h_volume') else "24h Volume:         N/A",
            f"Market Cap:         ${data.get('market_cap', 'N/A'):,}" if data.get('market_cap') else "Market Cap:         N/A",
            f"",
            f"Price Changes:",
            f"  1 Day:            {data.get('change_1d', 0):+.2f}%",
            f"  7 Days:           {data.get('change_7d', 0):+.2f}%",
            f"  30 Days:          {data.get('change_30d', 0):+.2f}%",
            f"",
            f"52 Week Range:      ${data.get('52_week_low', 'N/A'):,.2f} - ${data.get('52_week_high', 'N/A'):,.2f}",
            f"30-Day Volatility:  {data.get('volatility_30d', 'N/A')}%",
            f"",
            f"Investment Signals:",
            f"  Momentum:         {data.get('momentum', 'N/A')}",
            f"  Risk Level:       {data.get('risk_level', 'N/A')}",
            f"",
            f"Analysis Time:      {data.get('analysis_timestamp', 'N/A')}",
            f"{'='*60}\n",
        ]
        print("\n".join(lines))

        if args.analyze:
            print("AI Analysis (this may take a moment)...")
            ai_analyzer = OllamaAnalyzer(model=args.model)
            # Create simplified data for AI
            btc_summary = {
                "symbol": "BTC-USD",
                "name": "Bitcoin",
                "current_price": data.get("current_price"),
                "change_30d": data.get("change_30d"),
                "volatility_30d": data.get("volatility_30d"),
                "momentum": data.get("momentum"),
                "risk_level": data.get("risk_level"),
            }
            analysis = ai_analyzer.analyze_stock(btc_summary)
            print(f"\n{analysis}\n")

        if args.json:
            print(json.dumps(data, indent=2, default=str))

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_movers(args):
    """Get top S&P 500 movers."""
    analyzer = MarketAnalyzer()
    try:
        print(f"\nFetching top {args.limit} S&P 500 movers (period: {args.period})...")
        movers = analyzer.get_top_movers(period=args.period, limit=args.limit)

        if not movers:
            print("No movers data available")
            return 1

        print(f"\n{'='*80}")
        print(f"Top {len(movers)} S&P 500 Movers - Last {args.period}")
        print(f"{'='*80}")
        print(f"{'Symbol':<8} {'Name':<30} {'Price':<12} {'Change':<12} {'Change %':<10}")
        print(f"{'-'*80}")

        for mover in movers:
            symbol = mover['symbol']
            name = mover['name'][:28] if len(mover['name']) > 28 else mover['name']
            price = f"${mover['current_price']:.2f}"
            change = f"${mover['change']:+.2f}"
            change_pct = f"{mover['change_pct']:+.2f}%"

            print(f"{symbol:<8} {name:<30} {price:<12} {change:<12} {change_pct:<10}")

        print(f"{'='*80}\n")

        if args.analyze:
            print("Running AI analysis on top mover...")
            top_mover = movers[0]
            ai_analyzer = OllamaAnalyzer(model=args.model)
            analysis = ai_analyzer.analyze_stock(top_mover)
            print(f"\nTop Mover Analysis ({top_mover['symbol']}):\n{analysis}\n")

        if args.json:
            print(json.dumps(movers, indent=2))

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_backtest(args):
    """Run a simple SMA momentum backtest for one or more symbols."""
    try:
        import yfinance as yf
    except ImportError:
        print("Error: yfinance required for backtest", file=sys.stderr)
        return 1

    from stock_checker.backtester import Backtester, momentum_cross_strategy
    from stock_checker.strategy_signals import multi_timeframe_momentum_strategy

    strategy = (
        multi_timeframe_momentum_strategy
        if args.strategy == "mtf"
        else momentum_cross_strategy
    )
    symbols = [s.upper() for s in args.symbols]
    historical = {}
    for symbol in symbols:
        hist = yf.Ticker(symbol).history(period=args.period, interval=args.interval)
        if hist is None or hist.empty:
            print(f"Error: no history for {symbol}", file=sys.stderr)
            return 1
        bars = []
        for idx, row in hist.iterrows():
            bars.append(
                {
                    "date": idx.to_pydatetime().replace(tzinfo=None),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row.get("Volume", 0) or 0),
                }
            )
        historical[symbol] = bars

    bt = Backtester(
        initial_capital=args.capital,
        commission_rate=args.fee,
        slippage_pct=args.slippage,
        position_fraction=args.position_size,
    )
    result = bt.backtest(historical, strategy)
    result.print_summary()
    if args.json:
        print(json.dumps(result.calculate_metrics(), indent=2, default=str))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="AI Stock Checker - Analyze stocks with AI-powered insights"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    info_parser = subparsers.add_parser("info", help="Get current stock information")
    info_parser.add_argument("symbol", help="Stock ticker symbol (e.g., AAPL, TSLA)")
    info_parser.add_argument(
        "-a", "--analyze", action="store_true", help="Run AI analysis on the stock"
    )
    info_parser.add_argument(
        "-m", "--model", default="gemma4:latest", help="Ollama model (default: gemma4:latest)"
    )
    info_parser.add_argument("--json", action="store_true", help="Output raw JSON data")

    history_parser = subparsers.add_parser("history", help="Get historical stock data")
    history_parser.add_argument("symbol", help="Stock ticker symbol")
    history_parser.add_argument(
        "-p",
        "--period",
        default="1mo",
        help="Period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)",
    )
    history_parser.add_argument(
        "-i",
        "--interval",
        default="1d",
        help="Interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)",
    )
    history_parser.add_argument("--json", action="store_true", help="Output raw JSON data")

    bitcoin_parser = subparsers.add_parser("bitcoin", help="Analyze Bitcoin for investment")
    bitcoin_parser.add_argument(
        "-a", "--analyze", action="store_true", help="Run AI analysis on Bitcoin"
    )
    bitcoin_parser.add_argument(
        "-m", "--model", default="gemma4:latest", help="Ollama model (default: gemma4:latest)"
    )
    bitcoin_parser.add_argument("--json", action="store_true", help="Output raw JSON data")

    movers_parser = subparsers.add_parser("movers", help="Get top S&P 500 movers")
    movers_parser.add_argument(
        "-l", "--limit", type=int, default=10, help="Number of top movers to show (default: 10)"
    )
    movers_parser.add_argument(
        "-p",
        "--period",
        default="1d",
        help="Period for comparison (1d, 5d, 1mo)",
    )
    movers_parser.add_argument(
        "-a", "--analyze", action="store_true", help="Run AI analysis on top mover"
    )
    movers_parser.add_argument(
        "-m", "--model", default="gemma4:latest", help="Ollama model (default: gemma4:latest)"
    )
    movers_parser.add_argument("--json", action="store_true", help="Output raw JSON data")

    backtest_parser = subparsers.add_parser(
        "backtest", help="Backtest SMA momentum strategy on symbols"
    )
    backtest_parser.add_argument("symbols", nargs="+", help="Tickers (e.g. AAPL MSFT)")
    backtest_parser.add_argument("-p", "--period", default="1y", help="History period")
    backtest_parser.add_argument("-i", "--interval", default="1d", help="Bar interval")
    backtest_parser.add_argument("--capital", type=float, default=10000.0)
    backtest_parser.add_argument("--fee", type=float, default=0.001, help="Commission rate")
    backtest_parser.add_argument("--slippage", type=float, default=0.001)
    backtest_parser.add_argument(
        "--position-size", type=float, default=0.2, help="Equity fraction per position"
    )
    backtest_parser.add_argument(
        "--strategy",
        choices=["sma", "mtf"],
        default="sma",
        help="sma=close vs SMA20; mtf=multi-timeframe SMA alignment",
    )
    backtest_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "info":
        return cmd_info(args)
    elif args.command == "history":
        return cmd_history(args)
    elif args.command == "bitcoin":
        return cmd_bitcoin(args)
    elif args.command == "movers":
        return cmd_movers(args)
    elif args.command == "backtest":
        return cmd_backtest(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
