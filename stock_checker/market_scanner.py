#!/usr/bin/env python3

from __future__ import annotations

import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pytz
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from .binance_fetcher import BinanceFetcher
from .entry_slots import STOCK_BREAKOUT_SCORE_BASE
from .fetcher import StockFetcher
from .secret_redact import redact_secrets, safe_exc_text
from .stock_universe_manager import StockUniverseManager
from .symbol_filters import filter_ranked_opportunities, is_tradeable_symbol
from .technical_indicators import _finite_signed, _valid_close, _valid_volume


def coerce_scan_price(value: object) -> Optional[float]:
    """tradermonty #655/#754: scan marks must be real finite positive (never bool)."""
    if not _valid_close(value):
        return None
    return float(value)


def coerce_signed_pct(value: object) -> Optional[float]:
    """Finite signed % (may be ≤0); never invent flat ``0.0`` / ``True→1.0``.

    tradermonty #798/#655 + xang1234/portfolio AI claim honesty: missing 24h%
    or pct-from-high is unavailable — do not score as flat or near-high.
    """
    if not _finite_signed(value):
        return None
    return float(value)


def stock_pulse_side(day_chg: object) -> Optional[str]:
    """Scan-batch A/D bucket: ``up`` / ``down`` / ``flat``, or None when % unavailable.

    xang1234 breadth + tradermonty #798/#655: bool/gap/NaN must not inflate
    ``stock_scan_n`` as invented flat (that silently boosts advance/decline).
    """
    pct = coerce_signed_pct(day_chg)
    if pct is None:
        return None
    if pct > 0:
        return "up"
    if pct < 0:
        return "down"
    return "flat"


def breakout_from_high(
    price: object, high_52w: object
) -> Optional[Tuple[float, float, float]]:
    """Return ``(price, high_52w, pct_from_high)`` or None when either mark is unusable."""
    px = coerce_scan_price(price)
    hi = coerce_scan_price(high_52w)
    if px is None or hi is None:
        return None
    return px, hi, ((px - hi) / hi) * 100.0


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
            print(f"⚠️  Weekend detection failed: {safe_exc_text(e)}, assuming not weekend")
            return False

    def is_market_closed(self) -> bool:
        """
        US cash session closed? (9:30–16:00 America/New_York, Mon–Fri).

        For per-symbol hours (German .DE uses Xetra), use
        ``is_symbol_session_closed``.
        """
        try:
            from .market_hours import is_us_cash_session_closed

            return is_us_cash_session_closed()
        except Exception as e:
            print(f"⚠️  Market hours detection failed: {safe_exc_text(e)}, assuming market might be open")
            return False

    def is_symbol_session_closed(self, symbol: str) -> bool:
        """True when this equity should not open a new paper trade for hours."""
        try:
            from .market_hours import is_equity_session_closed

            return is_equity_session_closed(symbol)
        except Exception as e:
            print(f"⚠️  Symbol session detection failed for {symbol}: {safe_exc_text(e)}")
            return self.is_market_closed()

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

    def scan_live_crypto_majors(self) -> List[Dict]:
        """
        Price/momentum for LIVE_CRYPTO_SYMBOLS only (BTC/ETH).

        Used by the live paper path — no full Binance alt scan.
        """
        from stock_checker.crypto_policy import LIVE_CRYPTO_SYMBOLS, normalize_live_crypto_symbol

        import sys

        print(f"\n{'='*70}")
        print(f"🔍  LIVE CRYPTO MAJORS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        out: List[Dict] = []
        for yf_sym in sorted(LIVE_CRYPTO_SYMBOLS):
            bsym = yf_sym.replace("-USD", "USDT")
            data = self.binance.get_crypto_price(bsym)
            if not data:
                print(f"   ⚠️  No price for {bsym}")
                continue
            price = coerce_scan_price(data.get("current_price"))
            if price is None:
                print(f"   ⚠️  Invalid price for {bsym} (unavailable)")
                continue
            chg = coerce_signed_pct(data.get("change_24h"))
            if chg is None:
                print(f"   ⚠️  Invalid 24h% for {bsym} (unavailable)")
                continue
            high = coerce_scan_price(data.get("high_24h")) or price
            low = coerce_scan_price(data.get("low_24h")) or price
            if low > high:
                print(f"   ⚠️  Invalid day range for {bsym} (unavailable)")
                continue
            vol_range = ((high - low) / low) * 100 if low > 0 else 0.0
            vol_raw = data.get("volume_24h")
            volume_base = float(vol_raw) if _valid_volume(vol_raw) else 0.0
            volume_usdt = volume_base * price
            score = chg + min(vol_range * 0.5, 20) + min(volume_usdt / 10_000_000, 10)
            row = {
                "symbol": normalize_live_crypto_symbol(yf_sym),
                "binance_symbol": bsym,
                "price": price,
                "change_24h": chg,
                "volume_24h": volume_base,
                "volume_usdt": volume_usdt,
                "volatility": vol_range,
                "score": score,
                "final_score": score,
                "tradeable": True,
            }
            out.append(row)
            print(f"   {row['symbol']}: ${price:,.2f}  24h {chg:+.2f}%  score {score:.1f}")
        self.persistence.track_scanned_symbols_batch(
            [r["symbol"] for r in out], "crypto"
        )
        out.sort(key=lambda x: x.get("final_score", x["score"]), reverse=True)
        print(f"{'='*70}\n")
        sys.stdout.flush()
        return out

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
        
        # Curated seed + Yahoo movers: on cycle reset, weekends, or when discovery is stale.
        discovery_due = self.universe_manager.yahoo_discovery_due()
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

                price_raw = data.get("current_price")
                if not _valid_close(price_raw):
                    # bool True is truthy — refuse True→$1 invent; None/0 stay "no price"
                    label = "no price data" if not price_raw else "invalid price"
                    print(f"✓ ({label})")
                    sys.stdout.flush()
                    self.universe_manager.mark_scanned([symbol])
                    self.persistence.track_scanned_symbol(symbol, "paper")
                    continue

                high_52w_raw = data.get("52_week_high")
                day_chg = coerce_signed_pct(data.get("daily_change_pct"))
                side = stock_pulse_side(day_chg)
                if side is not None:
                    stock_priced += 1
                    if side == "up":
                        stock_up += 1
                    elif side == "down":
                        stock_down += 1
                    else:
                        stock_flat += 1

                broke = breakout_from_high(price_raw, high_52w_raw)
                if broke is None:
                    print("✓ (no/invalid 52w high)")
                    sys.stdout.flush()
                    self.universe_manager.mark_scanned([symbol])
                    self.persistence.track_scanned_symbol(symbol, "paper")
                    continue
                price, high_52w, pct_from_high = broke

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
                        'risk_pct': risk.get("risk_pct"),
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
                print(f"⚠️  Error: {safe_exc_text(e, limit=50)}")
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
            print(f"   ⚠️  Error expanding stock universe: {safe_exc_text(e)}")

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
            
            # Save JSON data (explicit UTF-8 — locale encoding must not mangle notes)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, default=str, ensure_ascii=False)
            
            # Generate and save human-readable report
            report = self._format_opportunities_report(results)
            with open(report_path, "w", encoding="utf-8") as f:
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
                print(
                    f"⚠️  Could not create symlinks: {safe_exc_text(symlink_error)}"
                )
            
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
            import traceback

            print(f"⚠️  Failed to save opportunities to archive: {safe_exc_text(e)}")
            print(redact_secrets(traceback.format_exc()))
            return None, None

    @staticmethod
    def heal_opportunities_latest_pin(archive_dir: Path) -> bool:
        """Retarget ``*_latest`` to the newest timestamped publish when behind.

        Desk already falls back when ``opportunities_latest`` is missing,
        dangling, or stale — but leaving the pin behind still hid the
        current auto scan from hard-readers (xang1234 #685 keep-newest).
        Cleanup + desk resolve heal so the readiness name matches the
        newest publish. Filename sort matches desk resolve (not mtime).
        Returns True when a pin was created or retargeted.
        """
        from stock_checker.opportunity_archive import (
            heal_opportunities_latest_pin as _heal,
        )

        return _heal(archive_dir)

    def cleanup_old_archives(self, archive_dir: Path, keep_days: int = 7) -> int:
        """Delete timestamped opportunity archives older than keep_days.

        Always keep ``*_latest`` names, the resolved targets of latest
        symlinks (and their .json/.txt twins), and the single newest
        timestamped pair — age prune must not dangle ``*_latest`` or wipe
        the only publish (xang1234 #682 keep-newest-auto adapted). After
        prune, retarget ``*_latest`` to the newest publish when behind
        (#685 heal — display fallback alone left the pin stale).
        """
        import time as time_mod

        if not archive_dir.exists():
            return 0
        cutoff = time_mod.time() - (keep_days * 86400)
        try:
            archive_root = archive_dir.resolve()
        except OSError:
            archive_root = archive_dir

        protected: set[Path] = set()

        def _protect(path: Path) -> None:
            try:
                resolved = path.resolve()
            except OSError:
                return
            try:
                if not resolved.exists():
                    return
                if resolved.parent.resolve() != archive_root:
                    return
            except OSError:
                return
            protected.add(resolved)
            twin = (
                resolved.with_suffix(".txt")
                if resolved.suffix == ".json"
                else resolved.with_suffix(".json")
            )
            try:
                if twin.exists() and twin.parent.resolve() == archive_root:
                    protected.add(twin.resolve())
            except OSError:
                pass

        for latest_name in (
            "opportunities_latest.json",
            "opportunities_latest.txt",
        ):
            latest = archive_dir / latest_name
            if latest.is_symlink() or latest.is_file():
                _protect(latest)

        candidates: list[Path] = []
        for path in archive_dir.glob("opportunities_*.json"):
            if path.name.endswith("_latest.json") or "latest" in path.name:
                continue
            candidates.append(path)

        if candidates:
            try:
                newest = max(candidates, key=lambda p: p.stat().st_mtime)
            except OSError:
                newest = None
            if newest is not None:
                _protect(newest)

        removed = 0
        for path in candidates:
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if resolved in protected:
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
        self.heal_opportunities_latest_pin(archive_dir)
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

        # Live crypto: majors only (BTC/ETH). Do not scan the alt carnival —
        # trader will not buy them; scanning them wastes time and confuses Screener.
        from stock_checker.crypto_policy import LIVE_CRYPTO_SYMBOLS

        print(f"\n📋 Scanning live crypto majors only: {', '.join(sorted(LIVE_CRYPTO_SYMBOLS))}")
        crypto_leaders = self.scan_live_crypto_majors()

        # Scan stocks
        breakouts = self.scan_stock_breakouts()

        # Generate recommendations
        recommendations = []

        # At most top_crypto_count majors (policy also caps open crypto slots to 1)
        top_cryptos = list(crypto_leaders[: max(1, int(self.top_crypto_count))])

        for i, crypto in enumerate(top_cryptos, 1):
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
        stock_rank = len(recommendations) + 1
        for stock in breakouts[:3]:
            pct = coerce_signed_pct(stock.get("pct_from_high"))
            if pct is None:
                continue
            risk_bit = stock.get("risk_note") or ""
            reasoning = (
                f"{stock['strength']} breakout, {pct:+.2f}% from 52w high"
            )
            if risk_bit and risk_bit != "risk n/a":
                reasoning = f"{reasoning} · {risk_bit}"
            recommendations.append({
                'rank': stock_rank,
                'symbol': stock['symbol'],
                'asset_class': 'stock',
                'strategy': 'breakout',
                # Map [-5, 0] near-high into ~[35, 40] so sort slots aren't crypto-only.
                'score': STOCK_BREAKOUT_SCORE_BASE + pct,
                'pct_from_high': pct,
                'change_24h': stock.get('daily_change_pct'),
                'reasoning': reasoning,
                'risk_note': risk_bit,
                'risk_rr': stock.get('risk_rr'),
                'risk_rr_ok': stock.get('risk_rr_ok'),
                'risk_pct': stock.get('risk_pct'),
            })
            stock_rank += 1

        # Crypto risk notes (volatility as ATR%)
        from stock_checker.atr_risk import note_from_day_range

        for crypto in crypto_leaders:
            px = coerce_scan_price(crypto.get("price"))
            if px is None:
                continue
            # Unavailable vol → None (never invent flat 0% ATR% risk note)
            vol = coerce_signed_pct(crypto.get("volatility"))
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
