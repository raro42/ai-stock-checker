#!/usr/bin/env python3

import argparse
import json
import sys

from stock_checker.fetcher import StockFetcher
from stock_checker.ai_analyzer import OllamaAnalyzer
from stock_checker.market_analyzer import MarketAnalyzer
from stock_checker.secret_redact import safe_exc_text
from stock_checker.technical_indicators import (
    _finite_signed,
    _valid_close,
    _valid_volume,
    coerce_ohlcv_bar,
)


def _fmt_signed_pct(raw: object) -> str:
    """Finite signed % or n/a — never invent flat +0.00 from None/bool."""
    if not _finite_signed(raw):
        return "n/a"
    return f"{float(raw):+.2f}%"


def _fmt_signed_money(raw: object) -> str:
    """Finite signed $ delta or n/a — never invent $0.00 from None/bool."""
    if not _finite_signed(raw):
        return "n/a"
    return f"${float(raw):+.2f}"


def _fmt_volume(raw: object) -> str:
    """Non-negative volume or n/a — never invent 0 / True→1."""
    if not _valid_volume(raw):
        return "n/a"
    return f"{float(raw):,.0f}"


def _fmt_price(raw: object) -> str:
    """Positive mark or n/a — never invent $1 from True."""
    if not _valid_close(raw):
        return "n/a"
    return f"${float(raw):,.2f}"


def _fmt_market_cap(raw: object) -> str:
    """Positive market cap or n/a — never invent $1 from True."""
    if not _valid_close(raw):
        return "n/a"
    return f"${float(raw):,.0f}"


def _fmt_optional_num(raw: object) -> str:
    """Finite number or n/a (PE / yield may be ≤0)."""
    if not _finite_signed(raw):
        return "n/a"
    return str(raw)


def format_stock_info(data: dict) -> str:
    """Format stock information for display."""
    lines = [
        f"\n{'='*60}",
        f"Stock: {data.get('name', 'N/A')} ({data.get('symbol', 'N/A')})",
        f"{'='*60}",
        f"Current Price:    {_fmt_price(data.get('current_price'))}",
        f"Previous Close:   {_fmt_price(data.get('previous_close'))}",
        f"Day Range:        {_fmt_price(data.get('day_low'))} - {_fmt_price(data.get('day_high'))}",
        f"52 Week Range:    {_fmt_price(data.get('52_week_low'))} - {_fmt_price(data.get('52_week_high'))}",
        f"Volume:           {_fmt_volume(data.get('volume'))}",
        f"Market Cap:       {_fmt_market_cap(data.get('market_cap'))}",
        f"P/E Ratio:        {_fmt_optional_num(data.get('pe_ratio'))}",
        f"Dividend Yield:   {_fmt_optional_num(data.get('dividend_yield'))}",
        f"{'='*60}\n",
    ]
    return "\n".join(lines)


def format_historical_summary(data: dict) -> str:
    """Format historical data summary for display."""
    summary = data.get("summary", {}) or {}
    change_pct = summary.get("price_change_pct")
    change_pct_txt = (
        f"{float(change_pct):.2f}%" if _finite_signed(change_pct) else "n/a"
    )
    lines = [
        f"\n{'='*60}",
        f"Historical Data: {data.get('symbol', 'N/A')}",
        f"Period: {data.get('period', 'N/A')} | Interval: {data.get('interval', 'N/A')}",
        f"{'='*60}",
        f"Date Range:       {summary.get('start_date', 'N/A')} to {summary.get('end_date', 'N/A')}",
        f"Records:          {summary.get('num_records', 'N/A')}",
        f"Avg Volume:       {_fmt_volume(summary.get('avg_volume'))}",
        f"Price Change:     {_fmt_signed_money(summary.get('price_change'))}",
        f"Change %:         {change_pct_txt}",
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
        print(f"Error: {safe_exc_text(e)}", file=sys.stderr)
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
        print(f"Error: {safe_exc_text(e)}", file=sys.stderr)
        return 1
    return 0


def cmd_bitcoin(args):
    """Analyze Bitcoin for investment."""
    analyzer = MarketAnalyzer()
    try:
        print("\nAnalyzing Bitcoin...")
        data = analyzer.analyze_bitcoin_for_investment()

        vol_txt = (
            f"30-Day Volatility:  {float(data['volatility_30d']):.2f}%"
            if _finite_signed(data.get("volatility_30d"))
            else "30-Day Volatility:  n/a"
        )
        lines = [
            f"\n{'='*60}",
            f"Bitcoin Investment Analysis",
            f"{'='*60}",
            f"Current Price:      {_fmt_price(data.get('current_price'))}",
            f"24h Volume:         {_fmt_volume(data.get('24h_volume'))}",
            f"Market Cap:         {_fmt_market_cap(data.get('market_cap'))}",
            f"",
            f"Price Changes:",
            f"  1 Day:            {_fmt_signed_pct(data.get('change_1d'))}",
            f"  7 Days:           {_fmt_signed_pct(data.get('change_7d'))}",
            f"  30 Days:          {_fmt_signed_pct(data.get('change_30d'))}",
            f"",
            f"52 Week Range:      {_fmt_price(data.get('52_week_low'))} - {_fmt_price(data.get('52_week_high'))}",
            vol_txt,
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
        print(f"Error: {safe_exc_text(e)}", file=sys.stderr)
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
            raw_name = mover.get('name') or ''
            name = raw_name[:28] if len(raw_name) > 28 else raw_name
            # Claim honesty: missing/bool marks speak n/a (not invent $1 / +0%).
            price = _fmt_price(mover.get('current_price'))
            change = _fmt_signed_money(mover.get('change'))
            change_pct = _fmt_signed_pct(mover.get('change_pct'))

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
        print(f"Error: {safe_exc_text(e)}", file=sys.stderr)
        return 1
    return 0


def cmd_backtest(args):
    """Run a simple SMA momentum backtest for one or more symbols."""
    from stock_checker.backtester import Backtester, momentum_cross_strategy
    from stock_checker.strategy_signals import multi_timeframe_momentum_strategy
    from stock_checker.yfinance_history import fetch_yfinance_history

    strategy = (
        multi_timeframe_momentum_strategy
        if args.strategy == "mtf"
        else momentum_cross_strategy
    )
    symbols = [s.upper() for s in args.symbols]
    historical = {}
    for symbol in symbols:
        try:
            # Join-bounded — hung Yahoo ≠ calm CLI hang (tradermonty #904/#905).
            hist = fetch_yfinance_history(
                symbol, period=args.period, interval=args.interval
            )
        except Exception as e:
            print(
                f"Error: history failed for {symbol}: {safe_exc_text(e)}",
                file=sys.stderr,
            )
            return 1
        if hist is None or getattr(hist, "empty", True):
            print(f"Error: no history for {symbol}", file=sys.stderr)
            return 1
        bars = []
        for idx, row in hist.iterrows():
            vol = row["Volume"] if "Volume" in row.index else None
            bar = coerce_ohlcv_bar(
                open_=row["Open"],
                high=row["High"],
                low=row["Low"],
                close=row["Close"],
                volume=vol,
                date=idx.to_pydatetime().replace(tzinfo=None),
            )
            if bar is not None:
                bars.append(bar)
        if not bars:
            print(f"Error: no usable bars for {symbol}", file=sys.stderr)
            return 1
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
