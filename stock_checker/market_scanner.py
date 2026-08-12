#!/usr/bin/env python3

from typing import Dict, List
import time
import json
from datetime import datetime, time as dt_time
from pathlib import Path
import pytz
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from .binance_fetcher import BinanceFetcher
from .fetcher import StockFetcher
from .stock_universe_manager import StockUniverseManager
from .symbol_filters import filter_ranked_opportunities, is_tradeable_symbol


class MarketScanner:
    """
    Advanced market scanner to identify top performers and opportunities.

    Analyzes:
    - Momentum leaders (top gainers)
    - Volume spikes (unusual activity)
    - Breakouts (52-week highs with momentum)
    - Value plays (deep pullbacks with strong fundamentals)
    - Sector rotation (which sectors are hot)
    """

    def __init__(self, top_crypto_count: int = 3):
        self.binance = BinanceFetcher()
        self.stock_fetcher = StockFetcher()
        self.top_crypto_count = top_crypto_count

        # Import CoinMarketCap fetcher
        try:
            from .coinmarketcap_fetcher import CoinMarketCapFetcher
            self.cmc = CoinMarketCapFetcher()
        except ImportError:
            self.cmc = None
            print("⚠️  CoinMarketCap fetcher not available")

        # Comprehensive watchlists
        self.crypto_universe = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
            'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'DOTUSDT', 'MATICUSDT',
            'LINKUSDT', 'UNIUSDT', 'LTCUSDT', 'ATOMUSDT', 'NEARUSDT'
        ]

        self.etf_universe = [
            "SPY", "QQQ", "IWM", "DIA",  # Major indices
            "VOO", "VTI", "SCHD",  # Low-cost core
            "ARKK", "ARKW", "ARKG",  # Innovation
            "XLF", "XLE", "XLK", "XLV", "XLY",  # Sector SPDRs
            "GLD", "SLV", "UNG", "USO"  # Commodities
        ]

        # Initialize persistent stock universe manager
        self.universe_manager = StockUniverseManager(data_dir="/data")
        
        # Initialize persistence for symbol tracking
        from .persistence import DataPersistence
        self.persistence = DataPersistence(data_dir="/data")
        self._last_stock_scan_pulse: dict = {}

    def is_weekend(self) -> bool:
        """
        Check if it's currently a weekend (Saturday or Sunday).
        
        Returns:
            True if it's Saturday or Sunday, False otherwise
        """
        try:
            et_tz = pytz.timezone('US/Eastern')
            now_et = datetime.now(et_tz)
            return now_et.weekday() >= 5  # Saturday = 5, Sunday = 6
        except Exception as e:
            print(f"⚠️  Weekend detection failed: {e}, assuming not weekend")
            return False

    def is_market_closed(self) -> bool:
        """
        Check if US stock market is currently closed.
        Market hours: 9:30 AM - 4:00 PM ET, Monday-Friday
        
        Returns:
            True if market is closed (weekend, before 9:30 AM ET, or after 4:00 PM ET)
            False if market is open
        """
        try:
            # Get current time in ET timezone
            et_tz = pytz.timezone('US/Eastern')
            now_et = datetime.now(et_tz)
            
            # Check if weekend
            if now_et.weekday() >= 5:  # Saturday = 5, Sunday = 6
                return True
            
            # Market hours: 9:30 AM - 4:00 PM ET
            market_open = dt_time(9, 30)
            market_close = dt_time(16, 0)
            current_time = now_et.time()
            
            # Market is closed if before 9:30 AM or after 4:00 PM
            return current_time < market_open or current_time >= market_close
        except Exception as e:
            # If timezone detection fails, assume market might be open
            # (safer to not save during potential market hours)
            print(f"⚠️  Market hours detection failed: {e}, assuming market might be open")
            return False

    def scan_crypto_momentum(self, top_n: int = 10) -> List[Dict]:
        """
        Scan crypto market for top momentum plays.

        Returns:
            List of top cryptos ranked by:
            - 24h % change (primary)
            - Volume surge
            - Volatility (opportunity)
        """
        import sys

        print(f"\n{'='*70}")
        print(f"🔍  CRYPTO MARKET SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")

        # Show CoinMarketCap top gainers/losers first
        if self.cmc:
            print(f"\n📊 CoinMarketCap Top Movers:")
            movers = self.cmc.get_top_movers()

            if movers.get('gainers'):
                print(f"\n🚀 TOP GAINERS:")
                print(f"{'Symbol':<10} {'Price':<15} {'24h%':<10}")
                print(f"{'-'*35}")
                for coin in movers['gainers'][:5]:
                    print(f"{coin['symbol']:<10} ${coin['price']:<14,.4f} {coin['change_24h']:>8.2f}%")

            if movers.get('losers'):
                print(f"\n📉 TOP LOSERS:")
                print(f"{'Symbol':<10} {'Price':<15} {'24h%':<10}")
                print(f"{'-'*35}")
                for coin in movers['losers'][:5]:
                    print(f"{coin['symbol']:<10} ${coin['price']:<14,.4f} {coin['change_24h']:>8.2f}%")

            sys.stdout.flush()

        # Scan ALL Binance pairs (not just watchlist)
        print(f"\n📋 Scanning ALL Binance USDT pairs (min volume: $25M)...")
        sys.stdout.flush()
        prices = self.binance.get_all_tickers(min_volume_usdt=25000000)

        if not prices:
            print("❌ Failed to fetch crypto data")
            return []

        print(f"   Found {len(prices)} liquid trading pairs")
        sys.stdout.flush()
        
        # Track all scanned crypto symbols
        crypto_symbols = [symbol.replace('USDT', '-USD') for symbol in prices.keys()]
        self.persistence.track_scanned_symbols_batch(crypto_symbols, "crypto")

        # Calculate scores (skip stables, leveraged tokens, noise)
        ranked = []
        skipped = 0
        for symbol, data in prices.items():
            yf_symbol = symbol.replace('USDT', '-USD')
            if not is_tradeable_symbol(yf_symbol):
                skipped += 1
                continue

            # Momentum score
            momentum_score = data['change_24h']

            # Volatility bonus (high vol = more profit potential)
            vol_range = ((data['high_24h'] - data['low_24h']) / data['low_24h']) * 100
            volatility_score = min(vol_range * 0.5, 20)  # Cap at +20 points

            # Volume score
            volume_usdt = data.get('volume_usdt', data['volume_24h'] * data['current_price'])
            volume_score = min(volume_usdt / 10000000, 10)  # $10M = 1 point

            total_score = momentum_score + volatility_score + volume_score

            ranked.append({
                'symbol': yf_symbol,
                'binance_symbol': symbol,
                'price': data['current_price'],
                'change_24h': data['change_24h'],
                'volume_24h': data['volume_24h'],
                'volume_usdt': volume_usdt,
                'volatility': vol_range,
                'score': total_score
            })

        # Sort by score
        ranked.sort(key=lambda x: x['score'], reverse=True)
        if skipped:
            print(f"   Filtered out {skipped} non-tradeable symbols (stables/leveraged/noise)")

        # Enhance top candidates with breakout & liquidity analysis
        print(f"\n🔬 Deep analysis on top {min(top_n, len(ranked))} candidates...")
        sys.stdout.flush()

        for crypto in ranked[:top_n]:
            symbol = crypto['binance_symbol']

            # Breakout analysis
            breakout = self.binance.analyze_breakout(symbol)
            if breakout:
                crypto['breakout_score'] = breakout['breakout_score']
                crypto['is_higher_high'] = breakout['is_higher_high']
                crypto['volume_surge_pct'] = breakout.get('volume_surge_pct', 0)
            else:
                crypto['breakout_score'] = 0
                crypto['is_higher_high'] = False
                crypto['volume_surge_pct'] = 0

            # Liquidity check
            liquidity = self.binance.check_liquidity(symbol)
            if liquidity:
                crypto['liquidity_score'] = liquidity['liquidity_score']
                crypto['spread_pct'] = liquidity['spread_pct']
                crypto['tradeable'] = liquidity['tradeable']
            else:
                crypto['liquidity_score'] = 0
                crypto['spread_pct'] = 999
                crypto['tradeable'] = False

            # Buy/sell pressure analysis (for top candidates)
            if crypto in ranked[:top_n]:
                pressure = self.binance.analyze_buy_sell_pressure(symbol, limit=100)
                if pressure:
                    crypto['buy_ratio'] = pressure['buy_ratio']
                    crypto['pressure_score'] = pressure['pressure_score']
                    crypto['buy_volume'] = pressure['buy_volume']
                    crypto['sell_volume'] = pressure['sell_volume']
                else:
                    crypto['buy_ratio'] = 0.5
                    crypto['pressure_score'] = 0
                    crypto['buy_volume'] = 0
                    crypto['sell_volume'] = 0

            # Calculate technical indicators for top 3 candidates only
            if crypto in ranked[:3]:
                tech_indicators = self.binance.get_technical_indicators(symbol)
                if tech_indicators:
                    crypto['rsi'] = tech_indicators.get('rsi')
                    if 'macd' in tech_indicators:
                        crypto['macd'] = tech_indicators['macd']
                    else:
                        crypto['macd'] = None
                else:
                    crypto['rsi'] = None
                    crypto['macd'] = None
            else:
                crypto['rsi'] = None
                crypto['macd'] = None

            # Adjust final score with breakout, liquidity, RSI, and MACD
            base_final_score = (
                crypto['score'] +
                (crypto['breakout_score'] * 0.3) +
                (crypto['liquidity_score'] * 0.2)
            )
            
            # Add RSI weight (small adjustment)
            rsi_bonus = 0
            if crypto.get('rsi') is not None:
                rsi = crypto['rsi']
                if rsi < 40:
                    rsi_bonus = 5  # Oversold opportunity
                elif rsi > 70:
                    rsi_bonus = -5  # Overbought warning
            
            # Add MACD weight (small adjustment)
            macd_bonus = 0
            if crypto.get('macd') is not None and 'histogram' in crypto['macd']:
                macd_histogram = crypto['macd']['histogram']
                if macd_histogram > 0.1:
                    macd_bonus = 3  # Bullish MACD
                elif macd_histogram < -0.1:
                    macd_bonus = -3  # Bearish MACD
            
            # Add buy/sell pressure weight (small adjustment)
            pressure_bonus = 0
            if crypto.get('pressure_score') is not None:
                pressure_score = crypto['pressure_score']
                if pressure_score > 30:  # Strong buy pressure
                    pressure_bonus = 3
                elif pressure_score < -30:  # Strong sell pressure
                    pressure_bonus = -3
            
            crypto['final_score'] = base_final_score + rsi_bonus + macd_bonus + pressure_bonus

        # Re-sort by final score
        ranked.sort(key=lambda x: x.get('final_score', x['score']), reverse=True)

        # Display results
        print(f"\n{'Rank':<5} {'Symbol':<12} {'Price':<15} {'24h%':<10} {'Breakout':<10} {'Liquid':<8} {'RSI':<8} {'MACD':<10} {'Score':<8}")
        print(f"{'-'*98}")

        for i, crypto in enumerate(ranked[:top_n], 1):
            emoji = '🚀' if crypto['change_24h'] > 10 else '🟢' if crypto['change_24h'] > 0 else '🔴'
            breakout_emoji = '🔥' if crypto.get('breakout_score', 0) > 70 else '⚡' if crypto.get('breakout_score', 0) > 40 else '  '
            tradeable_emoji = '✅' if crypto.get('tradeable', False) else '⚠️'
            rsi_display = f"{crypto.get('rsi', 0):>5.1f}" if crypto.get('rsi') is not None else "  N/A"
            macd_display = f"{crypto.get('macd', {}).get('histogram', 0):>7.2f}" if crypto.get('macd') is not None and 'histogram' in crypto.get('macd', {}) else "    N/A"

            print(f"{i:<5} {emoji} {crypto['symbol']:<10} ${crypto['price']:>12,.2f} "
                  f"{crypto['change_24h']:>8.2f}% {breakout_emoji} {crypto.get('breakout_score', 0):>5.0f} "
                  f"{tradeable_emoji} {crypto.get('liquidity_score', 0):>3.0f} {rsi_display:>7} {macd_display:>9} {crypto.get('final_score', crypto['score']):>7.1f}")

        print(f"{'='*80}\n")
        sys.stdout.flush()
        return ranked[:top_n]

    def scan_stock_breakouts(self, sector: str = None) -> List[Dict]:
        """
        Scan for stocks breaking to new highs with momentum.
        Uses persistent disk-based rotation to cover entire market over time.
        
        On weekends, scans more aggressively to build a list for Monday opening.

        Args:
            sector: Specific sector to scan, or None for all
        """
        import sys

        print(f"\n{'='*70}")
        print(f"📈  STOCK BREAKOUT SCAN - {sector or 'ALL SECTORS'}")
        print(f"{'='*70}")

        # Weekend mode: scan more aggressively
        is_weekend = self.is_weekend()
        if is_weekend:
            print(f"🌙  WEEKEND MODE: Scanning aggressively to build Monday watchlist")
            scan_limit = 100  # Scan more stocks on weekends
            max_age_hours = 48  # Don't re-scan stocks scanned in last 48 hours
        else:
            scan_limit = 30
            max_age_hours = 24

        # Get statistics
        stats = self.universe_manager.get_stats()
        print(f"📊  Universe: {stats['total_stocks']} stocks | "
              f"Scanned: {stats['scanned_stocks']} ({stats['coverage_pct']:.1f}%) | "
              f"Unscanned: {stats['unscanned_stocks']}")

        # Get stocks to scan (limit depends on weekend mode)
        stocks_to_scan, cycle_just_reset = self.universe_manager.get_stocks_to_scan(limit=scan_limit, max_age_hours=max_age_hours)
        
        # Curated seed + Yahoo movers: on cycle reset, weekends, or when discovery is stale (≥24h).
        discovery_due = self.universe_manager.yahoo_discovery_due(max_age_hours=24)
        if cycle_just_reset or is_weekend or discovery_due:
            print(f"\n🔍 Universe refresh (seed merge + Yahoo movers discovery)...")
            self._add_stocks_from_coinmarketcap(
                force_yahoo=cycle_just_reset or is_weekend or discovery_due
            )
            # Re-fetch batch if we just grew the universe on an empty unscanned set.
            stocks_to_scan, cycle_just_reset = self.universe_manager.get_stocks_to_scan(
                limit=scan_limit, max_age_hours=max_age_hours
            )

        if cycle_just_reset:
            print(f"📋  Starting new cycle: Scanning {len(stocks_to_scan)} stocks")
        else:
            print(f"📋  Scanning {len(stocks_to_scan)} stocks this cycle")
        print(f"   Stocks: {', '.join(stocks_to_scan[:10])}{'...' if len(stocks_to_scan) > 10 else ''}")
        sys.stdout.flush()

        breakouts = []
        # Batch advance/decline for this scan slice (broader than breakouts-only).
        stock_up = 0
        stock_down = 0
        stock_flat = 0
        stock_priced = 0

        for idx, symbol in enumerate(stocks_to_scan, 1):
            # Get sector info for display
            sector_name = self.universe_manager.universe["stocks"].get(symbol, {}).get("sector", "unknown")
            print(f"   [{idx}/{len(stocks_to_scan)}] Scanning {symbol}...", end=" ", flush=True)
            try:
                # Add timeout protection (30 seconds per stock)
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self.stock_fetcher.get_stock_info, symbol)
                    try:
                        data = future.result(timeout=30)  # 30 second timeout
                    except FutureTimeoutError:
                        print(f"⏱️  Timeout after 30s")
                        sys.stdout.flush()
                        # Mark as scanned even on timeout to avoid retrying immediately
                        self.universe_manager.mark_scanned([symbol])
                        # Track symbol as paper even on timeout
                        self.persistence.track_scanned_symbol(symbol, "paper")
                        continue

                if not data.get('current_price'):
                    print("✓ (no price data)")
                    sys.stdout.flush()
                    # Mark as scanned immediately after attempt
                    self.universe_manager.mark_scanned([symbol])
                    # Track symbol as paper
                    self.persistence.track_scanned_symbol(symbol, "paper")
                    continue

                price = data['current_price']
                high_52w = data.get('52_week_high')
                try:
                    day_chg = float(data.get("daily_change_pct") or 0)
                    stock_priced += 1
                    if day_chg > 0:
                        stock_up += 1
                    elif day_chg < 0:
                        stock_down += 1
                    else:
                        stock_flat += 1
                except (TypeError, ValueError):
                    day_chg = 0.0

                # Skip if no 52-week high data
                if high_52w is None or high_52w == 0 or high_52w == "None":
                    print("✓ (no 52w high)")
                    sys.stdout.flush()
                    # Mark as scanned immediately after attempt
                    self.universe_manager.mark_scanned([symbol])
                    # Track symbol as paper
                    self.persistence.track_scanned_symbol(symbol, "paper")
                    continue

                try:
                    price = float(price)
                    # Handle None before float conversion
                    if high_52w is None:
                        # Mark as scanned immediately after attempt
                        self.universe_manager.mark_scanned([symbol])
                        # Track symbol as paper
                        self.persistence.track_scanned_symbol(symbol, "paper")
                        continue
                    high_52w = float(high_52w)
                    # Calculate distance from 52-week high
                    pct_from_high = ((price - high_52w) / high_52w) * 100
                except (TypeError, ValueError, ZeroDivisionError):
                    print(f"⚠️  Error: {type(high_52w).__name__} = {repr(high_52w)[:30]}")
                    sys.stdout.flush()
                    # Mark as scanned immediately after attempt
                    self.universe_manager.mark_scanned([symbol])
                    # Track symbol as paper
                    self.persistence.track_scanned_symbol(symbol, "paper")
                    continue

                # Breakout if within 5% of 52-week high
                if pct_from_high >= -5:
                    print(f"🔥 BREAKOUT! ({pct_from_high:+.2f}% from high)")
                    sys.stdout.flush()
                    from stock_checker.atr_risk import note_from_day_range

                    risk = note_from_day_range(
                        entry=price,
                        day_high=data.get("day_high"),
                        day_low=data.get("day_low"),
                    )
                    breakouts.append({
                        'symbol': symbol,
                        'sector': sector_name,
                        'price': price,
                        'pct_from_high': pct_from_high,
                        'strength': 'STRONG' if pct_from_high >= -1 else 'MODERATE',
                        'daily_change_pct': day_chg,
                        'risk_note': risk.get("summary") or "risk n/a",
                        'risk_rr': risk.get("rr"),
                        'risk_rr_ok': risk.get("rr_ok"),
                    })
                else:
                    print("✓")
                    sys.stdout.flush()

                # Mark as scanned immediately after successful processing
                self.universe_manager.mark_scanned([symbol])
                # Track symbol as paper
                self.persistence.track_scanned_symbol(symbol, "paper")
                time.sleep(0.15)  # Faster rate limiting

            except Exception as e:
                print(f"⚠️  Error: {type(e).__name__}: {str(e)[:50]}")
                sys.stdout.flush()
                # Mark as scanned even on error to avoid infinite retry loop
                self.universe_manager.mark_scanned([symbol])
                # Track symbol as paper even on error
                self.persistence.track_scanned_symbol(symbol, "paper")
                continue

        # Sort by proximity to highs
        breakouts.sort(key=lambda x: x['pct_from_high'], reverse=True)

        # Stash batch A/D for identify_best_opportunities / desk Breadth.
        self._last_stock_scan_pulse = {
            "stock_scan_n": stock_priced,
            "stock_scan_up": stock_up,
            "stock_scan_down": stock_down,
            "stock_scan_flat": stock_flat,
            "stock_scan_batch": len(stocks_to_scan),
        }

        if breakouts:
            print(f"\n{'Symbol':<10} {'Sector':<15} {'Price':<12} {'From High':<12} {'Strength'}")
            print(f"{'-'*70}")
            for b in breakouts:
                emoji = '🔥' if b['strength'] == 'STRONG' else '⚡'
                print(f"{emoji} {b['symbol']:<10} {b['sector']:<15} ${b['price']:>10.2f} "
                      f"{b['pct_from_high']:>9.2f}% {b['strength']}")
        else:
            print("No breakouts detected in current scan")

        # Show updated statistics
        updated_stats = self.universe_manager.get_stats()
        
        if cycle_just_reset:
            print(f"\n📊  New cycle started: {updated_stats['scanned_stocks']}/{updated_stats['total_stocks']} stocks scanned in this cycle ({updated_stats['coverage_pct']:.1f}%)")
            if updated_stats['last_full_cycle']:
                print(f"   Previous full cycle completed: {updated_stats['last_full_cycle']}")
        else:
            print(f"\n📊  Progress: {updated_stats['scanned_stocks']}/{updated_stats['total_stocks']} stocks scanned ({updated_stats['coverage_pct']:.1f}%)")
            if updated_stats['last_full_cycle']:
                print(f"   Last full cycle: {updated_stats['last_full_cycle']}")

        print(f"{'='*70}\n")
        return breakouts

    def _add_stocks_from_coinmarketcap(self, *, force_yahoo: bool = False):
        """
        Expand the stock universe: curated seed merge + Yahoo movers discovery.

        Does not place trades — only grows the scan list behind existing filters.
        """
        try:
            print("   🌱 Refreshing stock universe (seed merge + Yahoo movers)...")
            added = self.universe_manager.discover_and_add_stocks(force_yahoo=force_yahoo)
            if added:
                print(f"   ✅ Universe grew by {added} name(s)")
            else:
                print("   ℹ️  Universe unchanged this pass")
        except Exception as e:
            print(f"   ⚠️  Error expanding stock universe: {e}")

    def _format_opportunities_report(self, results: dict) -> str:
        """
        Format opportunities as human-readable report.
        
        Args:
            results: Dict from identify_best_opportunities() containing:
                - crypto_leaders: List of crypto opportunities
                - stock_breakouts: List of stock breakouts
                - recommendations: List of ranked recommendations
                - scan_time: ISO timestamp
        
        Returns:
            Formatted string report
        """
        lines = [
            f"\n{'='*80}",
            f"PRE-MARKET OPPORTUNITY LIST",
            f"Generated: {results['scan_time']}",
            f"{'='*80}\n",
        ]
        
        # Summary
        lines.append("SUMMARY:")
        lines.append(f"  Total Crypto Leaders: {len(results['crypto_leaders'])}")
        lines.append(f"  Total Stock Breakouts: {len(results['stock_breakouts'])}")
        lines.append(f"  Total Recommendations: {len(results['recommendations'])}")
        lines.append("")
        
        # Top Recommendations
        if results['recommendations']:
            lines.append(f"{'='*80}")
            lines.append("TOP RECOMMENDATIONS (Ranked by Opportunity Score)")
            lines.append(f"{'='*80}")
            lines.append(f"{'Rank':<6} {'Symbol':<12} {'Type':<10} {'Strategy':<12} {'Score':<10} {'Reasoning'}")
            lines.append(f"{'-'*80}")
            
            for rec in results['recommendations']:
                lines.append(
                    f"{rec['rank']:<6} {rec['symbol']:<12} {rec['asset_class']:<10} "
                    f"{rec['strategy']:<12} {rec.get('score', 0):>8.1f}  {rec['reasoning']}"
                )
            lines.append("")
        
        # Top Crypto Leaders
        if results['crypto_leaders']:
            lines.append(f"{'='*80}")
            lines.append("TOP CRYPTO MOMENTUM LEADERS")
            lines.append(f"{'='*80}")
            lines.append(f"{'Symbol':<12} {'Price':<15} {'24h%':<10} {'Volatility':<12} {'Score':<10}")
            lines.append(f"{'-'*80}")
            
            for crypto in results['crypto_leaders'][:10]:
                lines.append(
                    f"{crypto['symbol']:<12} ${crypto['price']:>12,.2f} "
                    f"{crypto['change_24h']:>8.2f}% {crypto['volatility']:>10.1f}% "
                    f"{crypto.get('final_score', crypto['score']):>8.1f}"
                )
            lines.append("")
        
        # Stock Breakouts
        if results['stock_breakouts']:
            lines.append(f"{'='*80}")
            lines.append("STOCK BREAKOUTS (Near 52-Week Highs)")
            lines.append(f"{'='*80}")
            lines.append(f"{'Symbol':<10} {'Sector':<20} {'Price':<12} {'From High':<12} {'Strength'}")
            lines.append(f"{'-'*80}")
            
            for stock in results['stock_breakouts']:
                lines.append(
                    f"{stock['symbol']:<10} {stock.get('sector', 'N/A'):<20} "
                    f"${stock['price']:>10.2f} {stock['pct_from_high']:>10.2f}% "
                    f"{stock['strength']}"
                )
            lines.append("")
        
        lines.append(f"{'='*80}")
        lines.append(f"End of Report")
        lines.append(f"{'='*80}\n")
        
        return "\n".join(lines)

    def save_opportunities_to_archive(self, results: Dict, data_dir: str = "/data") -> tuple:
        """
        Save opportunity list to archive directory with timestamp.
        Creates both JSON and human-readable text files.
        
        Args:
            results: Dict from identify_best_opportunities() containing scan results
            data_dir: Base data directory (default: /data)
        
        Returns:
            Tuple of (json_path, report_path) or (None, None) on error
        """
        try:
            data_path = Path(data_dir)
            archive_dir = data_path / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now()
            date_str = timestamp.strftime("%Y%m%d")
            time_str = timestamp.strftime("%H%M%S")
            
            # Generate filenames
            json_filename = f"opportunities_{date_str}_{time_str}.json"
            report_filename = f"opportunities_{date_str}_{time_str}.txt"
            
            json_path = archive_dir / json_filename
            report_path = archive_dir / report_filename
            
            # Save JSON data
            with open(json_path, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            # Generate and save human-readable report
            report = self._format_opportunities_report(results)
            with open(report_path, 'w') as f:
                f.write(report)
            
            # Create symlinks to latest (for easy access)
            try:
                latest_json = archive_dir / "opportunities_latest.json"
                latest_report = archive_dir / "opportunities_latest.txt"
                
                if latest_json.exists() or latest_json.is_symlink():
                    latest_json.unlink()
                if latest_report.exists() or latest_report.is_symlink():
                    latest_report.unlink()
                
                latest_json.symlink_to(json_filename)
                latest_report.symlink_to(report_filename)
            except Exception as symlink_error:
                # Symlinks are optional, don't fail if they can't be created
                print(f"⚠️  Could not create symlinks: {symlink_error}")
            
            print(f"\n{'='*80}")
            print(f"💾 OPPORTUNITY LIST SAVED TO ARCHIVE")
            print(f"{'='*80}")
            print(f"JSON: {json_path}")
            print(f"Report: {report_path}")
            print(f"Latest: {archive_dir / 'opportunities_latest.json'}")
            print(f"{'='*80}\n")

            self.cleanup_old_archives(archive_dir, keep_days=7)
            
            return json_path, report_path
            
        except Exception as e:
            print(f"⚠️  Failed to save opportunities to archive: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    def cleanup_old_archives(self, archive_dir: Path, keep_days: int = 7) -> int:
        """Delete timestamped opportunity archives older than keep_days. Keep latest symlinks."""
        import time as time_mod

        if not archive_dir.exists():
            return 0
        cutoff = time_mod.time() - (keep_days * 86400)
        removed = 0
        for path in archive_dir.glob("opportunities_*.json"):
            if path.name.endswith("_latest.json") or "latest" in path.name:
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
                    twin = path.with_suffix(".txt")
                    twin.unlink(missing_ok=True)
                    removed += 1
            except OSError as exc:
                print(f"⚠️  Could not remove archive {path.name}: {exc}")
        if removed:
            print(f"🧹 Removed {removed} archive pair(s) older than {keep_days} days")
        return removed

    def identify_best_opportunities(self) -> Dict:
        """
        Comprehensive market analysis to identify top opportunities.

        Returns:
            Dict with:
            - top_crypto_momentum: Best crypto plays
            - stock_breakouts: Stocks at new highs
            - sector_leaders: Strongest sectors
            - recommendations: Prioritized trade ideas
        """
        print(f"\n{'#'*70}")
        print(f"🎯  MARKET OPPORTUNITY ANALYSIS")
        print(f"{'#'*70}\n")

        # Scan crypto
        crypto_leaders = self.scan_crypto_momentum(10)

        # Scan stocks
        breakouts = self.scan_stock_breakouts()

        # Generate recommendations
        recommendations = []

        # Major cryptos that should always be considered if available
        major_cryptos = ['BTC-USD', 'ETH-USD']
        
        # Collect top N crypto momentum plays
        top_cryptos = list(crypto_leaders[:self.top_crypto_count])
        top_crypto_symbols = {c['symbol'] for c in top_cryptos}
        
        # Ensure major cryptos are included (replace lowest-ranked if needed)
        for major in major_cryptos:
            major_crypto = next((c for c in crypto_leaders if c['symbol'] == major), None)
            if major_crypto and major not in top_crypto_symbols:
                # Remove the lowest-ranked crypto and add the major crypto
                if len(top_cryptos) >= self.top_crypto_count:
                    removed = top_cryptos.pop()
                    print(f"   ⭐ Including major crypto {major} (ranked #{crypto_leaders.index(major_crypto) + 1}, replacing {removed['symbol']})")
                else:
                    print(f"   ⭐ Including major crypto {major} (ranked #{crypto_leaders.index(major_crypto) + 1})")
                # Insert at beginning for priority
                top_cryptos.insert(0, major_crypto)
                top_crypto_symbols.add(major)
        
        # Top N crypto momentum plays (now includes major cryptos if needed)
        for i, crypto in enumerate(top_cryptos[:self.top_crypto_count], 1):
            recommendations.append({
                'rank': i,
                'symbol': crypto['symbol'],
                'asset_class': 'crypto',
                'strategy': 'momentum',
                'score': crypto.get('final_score', crypto['score']),
                'change_24h': crypto.get('change_24h'),
                'reasoning': f"+{crypto['change_24h']:.2f}% 24h momentum, {crypto['volatility']:.1f}% volatility"
            })

        # Top stock breakouts — score band so near-highs can compete with crypto
        # momentum points without raw 24h% domination (review A11).
        for i, stock in enumerate(breakouts[:3], len(recommendations) + 1):
            risk_bit = stock.get("risk_note") or ""
            pct = float(stock.get("pct_from_high") or 0)
            reasoning = (
                f"{stock['strength']} breakout, {pct:+.2f}% from 52w high"
            )
            if risk_bit and risk_bit != "risk n/a":
                reasoning = f"{reasoning} · {risk_bit}"
            recommendations.append({
                'rank': i,
                'symbol': stock['symbol'],
                'asset_class': 'stock',
                'strategy': 'breakout',
                # Map [-5, 0] near-high into ~[35, 40] so sort slots aren't crypto-only.
                'score': 40.0 + pct,
                'pct_from_high': pct,
                'change_24h': stock.get('daily_change_pct'),
                'reasoning': reasoning,
                'risk_note': risk_bit,
                'risk_rr': stock.get('risk_rr'),
                'risk_rr_ok': stock.get('risk_rr_ok'),
            })

        # Crypto risk notes (volatility as ATR%)
        from stock_checker.atr_risk import note_from_day_range

        for crypto in crypto_leaders:
            try:
                px = float(crypto.get("price") or 0)
                vol = float(crypto.get("volatility") or 0)
            except (TypeError, ValueError):
                continue
            if px <= 0:
                continue
            risk = note_from_day_range(entry=px, volatility_pct=vol)
            crypto["risk_note"] = risk.get("summary") or "risk n/a"
            crypto["risk_rr"] = risk.get("rr")
            crypto["risk_rr_ok"] = risk.get("rr_ok")

        # Display final recommendations
        print(f"\n{'='*70}")
        print(f"🏆 TOP INVESTMENT OPPORTUNITIES")
        print(f"{'='*70}")
        print(f"{'Rank':<5} {'Symbol':<10} {'Type':<10} {'Strategy':<12} {'Reasoning'}")
        print(f"{'-'*70}")

        for rec in recommendations:
            print(f"{rec['rank']:<5} {rec['symbol']:<10} {rec['asset_class']:<10} "
                  f"{rec['strategy']:<12} {rec['reasoning']}")

        print(f"{'='*70}\n")

        recommendations = filter_ranked_opportunities(recommendations)
        # Re-rank after filtering
        for i, rec in enumerate(recommendations, 1):
            rec['rank'] = i

        results = {
            'crypto_leaders': filter_ranked_opportunities(crypto_leaders),
            'stock_breakouts': filter_ranked_opportunities(breakouts),
            'recommendations': recommendations,
            'scan_time': datetime.now().isoformat(),
            'stock_scan_pulse': getattr(self, "_last_stock_scan_pulse", {}) or {},
        }
        
        # Auto-save to archive when market is closed
        if self.is_market_closed():
            self.save_opportunities_to_archive(results)
        
        return results
