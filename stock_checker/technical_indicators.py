#!/usr/bin/env python3
"""
Technical indicators for market analysis.
Implements RSI, MACD, Bollinger Bands, and volume analysis.
"""

from __future__ import annotations

import math
import numbers
from typing import List, Dict, Optional

import numpy as np


def _valid_close(price: object) -> bool:
    """tradermonty #655/#754: close must be a real finite positive number (never bool)."""
    if isinstance(price, bool) or not isinstance(price, numbers.Real):
        return False
    value = float(price)
    return math.isfinite(value) and value > 0.0


def daily_pct_change(price: object, prev: object) -> Optional[float]:
    """Daily % change, or None when either print is bool/gap/NaN/non-positive.

    tradermonty #798/#655: missing/invalid marks are unavailable — never invent
    a flat ``+0.00`` (or ``True→1.0``) for AI prompts.
    """
    if not (_valid_close(price) and _valid_close(prev)):
        return None
    p, q = float(price), float(prev)
    return ((p - q) / q) * 100.0


def _finite_signed(value: object) -> bool:
    """Finite real (may be ≤0); never bool — ``float(True)`` is 1.0."""
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return False
    return math.isfinite(float(value))


def coerce_score(value: object) -> Optional[float]:
    """Finite score, or None when bool/gap/NaN/non-numeric.

    tradermonty #700/#655 + xang1234/portfolio AI: never ``float(raw or 0)`` /
    ``True→1.0`` into entry ranking or desk score columns. Zero is a real score.
    """
    if value is None or not _finite_signed(value):
        return None
    return float(value)  # type: ignore[arg-type]


def coerce_nonneg_int(value: object) -> Optional[int]:
    """Non-negative int, or None when bool/gap/NaN (never ``True→1`` / ``False→0``).

    tradermonty #700/#655 + xang1234/portfolio AI — slot caps, sample meters,
    and book knobs must not invent a one-slot / one-fill count from a bool.
    """
    if value is None or not _finite_signed(value):
        return None
    n = int(value)  # type: ignore[arg-type]
    if n < 0:
        return None
    return n


def _coerce_indicator_period(period: object) -> Optional[int]:
    """Positive indicator window, or None when bool/gap/NaN (never ``True→1``).

    tradermonty #700/#655 + xang1234/portfolio AI after regime SMA / RS lookback
    refuse: ``int(True)`` must not invent RSI/MACD/BB/ATR/volume over a 1-bar
    window.
    """
    n = coerce_nonneg_int(period)
    if n is None or n <= 0:
        return None
    return n


def coerce_unix_ts(value: object) -> Optional[float]:
    """Unix epoch seconds, or None when bool/gap/NaN/non-positive.

    tradermonty #655 / xang1234 / portfolio AI: ``float(True)==1.0`` invents
    ~1970 hold age (past min-hold / cooldown clear). Missing/invalid → unknown.
    """
    if not _finite_signed(value):
        return None
    ts = float(value)  # type: ignore[arg-type]
    if ts <= 0.0:
        return None
    return ts


def _valid_volume(volume: object) -> bool:
    """Volume may be zero (no prints) but never negative / non-finite / non-numeric."""
    if isinstance(volume, bool) or not isinstance(volume, numbers.Real):
        return False
    value = float(volume)
    return math.isfinite(value) and value >= 0.0


def _valid_ohlc_bar(high: object, low: object, close: object) -> bool:
    """Positive finite OHLC with high ≥ low and close inside [low, high]."""
    if not (_valid_close(high) and _valid_close(low) and _valid_close(close)):
        return False
    h, lo, c = float(high), float(low), float(close)
    return h >= lo and lo <= c <= h


def coerce_ohlcv_bar(
    *,
    open_: object,
    high: object,
    low: object,
    close: object,
    volume: object = None,
    date: object = None,
) -> Optional[Dict]:
    """Build one OHLCV bar, or None when any print is bool/gap/inverted.

    tradermonty #700/#655 + xang1234/portfolio AI: never ``float(True)`` /
    ``float(Volume or 0)`` invent ``True→$1`` OHLC or ``True→1`` volume into
    overnight / CLI Yahoo loaders after promote ``bars_from_closes`` refuse.
    Missing volume → 0 (real no-print); bool/NaN volume refuses the bar.
    """
    if not _valid_close(open_):
        return None
    if not _valid_ohlc_bar(high, low, close):
        return None
    if volume is None:
        vol = 0.0
    elif not _valid_volume(volume):
        return None
    else:
        vol = float(volume)
    bar: Dict = {
        "open": float(open_),  # type: ignore[arg-type]
        "high": float(high),  # type: ignore[arg-type]
        "low": float(low),  # type: ignore[arg-type]
        "close": float(close),  # type: ignore[arg-type]
        "volume": vol,
    }
    if date is not None:
        bar["date"] = date
    return bar


class TechnicalIndicators:
    """Calculate technical indicators for trading signals."""

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """
        Calculate Relative Strength Index (RSI) using Wilder smoothing.

        Args:
            prices: List of closing prices (oldest to newest)
            period: RSI period (default 14)

        Returns:
            RSI value between 0-100, or None if insufficient / invalid data
        """
        # tradermonty #700/#655: refuse bool period — True→RSI(1) invent.
        n = _coerce_indicator_period(period)
        if n is None:
            return None
        if len(prices) < n + 1:
            return None
        # Gap/zero/NaN closes must not become a fake oversold/overbought score
        if any(not _valid_close(p) for p in prices):
            return None

        deltas = np.diff(np.asarray(prices, dtype=float))
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        # Seed with simple average of first `period` changes
        avg_gain = float(np.mean(gains[:n]))
        avg_loss = float(np.mean(losses[:n]))

        # Wilder exponential smoothing for remaining bars
        for i in range(n, len(gains)):
            avg_gain = ((avg_gain * (n - 1)) + gains[i]) / n
            avg_loss = ((avg_loss * (n - 1)) + losses[i]) / n

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        if not math.isfinite(rsi):
            return None
        return float(rsi)

    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Optional[Dict[str, float]]:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        Args:
            prices: List of closing prices
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line period (default 9)

        Returns:
            Dict with macd, signal, histogram, or None if insufficient / invalid data
        """
        # tradermonty #700/#655: refuse bool periods — True→EMA(1) invent.
        fast_n = _coerce_indicator_period(fast_period)
        slow_n = _coerce_indicator_period(slow_period)
        signal_n = _coerce_indicator_period(signal_period)
        if fast_n is None or slow_n is None or signal_n is None:
            return None
        if len(prices) < slow_n + signal_n:
            return None
        # Gap/zero/NaN closes must not become a fake MACD histogram
        if any(not _valid_close(p) for p in prices):
            return None

        prices_array = np.asarray(prices, dtype=float)

        # Calculate EMAs
        fast_ema = TechnicalIndicators._calculate_ema(prices_array, fast_n)
        slow_ema = TechnicalIndicators._calculate_ema(prices_array, slow_n)

        # MACD line
        macd_line = fast_ema - slow_ema

        # Signal line (EMA of MACD)
        signal_line = TechnicalIndicators._calculate_ema(macd_line, signal_n)

        # Histogram
        macd_v = float(macd_line[-1])
        signal_v = float(signal_line[-1])
        histogram = macd_v - signal_v
        if not all(math.isfinite(v) for v in (macd_v, signal_v, histogram)):
            return None

        return {
            'macd': macd_v,
            'signal': signal_v,
            'histogram': float(histogram)
        }

    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Optional[Dict[str, float]]:
        """
        Calculate Bollinger Bands.

        Args:
            prices: List of closing prices
            period: Moving average period (default 20)
            std_dev: Standard deviation multiplier (default 2.0)

        Returns:
            Dict with upper, middle, lower bands and current position, or None if invalid
        """
        # tradermonty #700/#655: refuse bool period/std — True→BB(1)/±1σ invent.
        n = _coerce_indicator_period(period)
        if n is None or not _finite_signed(std_dev):
            return None
        k = float(std_dev)  # type: ignore[arg-type]
        if k <= 0.0:
            return None
        if len(prices) < n:
            return None
        # Gap/zero/NaN closes must not become fake band positions
        if any(not _valid_close(p) for p in prices):
            return None

        prices_array = np.asarray(prices[-n:], dtype=float)

        # Middle band (SMA)
        middle = float(np.mean(prices_array))

        # Standard deviation
        std = float(np.std(prices_array))

        # Upper and lower bands
        upper = middle + (k * std)
        lower = middle - (k * std)

        # Current price position
        current_price = float(prices[-1])
        position = (current_price - lower) / (upper - lower) if upper != lower else 0.5
        bandwidth = (upper - lower) / middle if middle != 0 else 0.0
        if not all(math.isfinite(v) for v in (upper, middle, lower, position, bandwidth)):
            return None

        return {
            'upper': float(upper),
            'middle': float(middle),
            'lower': float(lower),
            'position': float(position),  # 0 = at lower band, 1 = at upper band
            'bandwidth': float(bandwidth)  # Volatility measure
        }

    @staticmethod
    def analyze_volume(
        volumes: List[float],
        prices: List[float],
        period: int = 20
    ) -> Optional[Dict[str, float]]:
        """
        Analyze volume patterns.

        Args:
            volumes: List of volume data
            prices: List of closing prices
            period: Analysis period

        Returns:
            Dict with volume analysis metrics, or None if insufficient / invalid bars
        """
        # tradermonty #700/#655: refuse bool period — True→vol(1) invent.
        n = _coerce_indicator_period(period)
        if n is None:
            return None
        if len(volumes) < n or len(prices) < n:
            return None
        if len(volumes) != len(prices):
            return None
        # Gap/zero/NaN closes or bad volume must not become a fake surge/correlation
        if any(not _valid_close(p) for p in prices):
            return None
        if any(not _valid_volume(v) for v in volumes):
            return None

        recent_volumes = np.asarray(volumes[-n:], dtype=float)
        avg_volume = float(np.mean(recent_volumes))
        current_volume = float(volumes[-1])

        # Volume surge detection
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # Price-volume correlation
        recent_prices = np.asarray(prices[-n:], dtype=float)
        if len(recent_prices) > 1:
            correlation = float(np.corrcoef(recent_prices, recent_volumes)[0, 1])
        else:
            correlation = 0.0

        metrics = {
            'current_volume': current_volume,
            'avg_volume': avg_volume,
            'volume_ratio': float(volume_ratio),
            'price_volume_correlation': correlation,
        }
        if not all(math.isfinite(v) for v in metrics.values()):
            return None
        return metrics

    @staticmethod
    def calculate_atr(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14
    ) -> Optional[float]:
        """
        Calculate Average True Range (ATR) with Wilder smoothing (RMA).

        Seeds with the mean of the first ``period`` true ranges, then
        ``atr = (atr*(period-1) + tr) / period`` — same alpha=1/period as RSI.
        A trailing SMA of the last N TRs (or span-EMA) is not Wilder and
        over-reacts to a single wide bar (xang1234 #749).

        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of closing prices
            period: ATR period

        Returns:
            ATR value, or None if insufficient / invalid OHLC bars
        """
        # tradermonty #700/#655: refuse bool period — True→ATR(1) invent.
        n = _coerce_indicator_period(period)
        if n is None:
            return None
        if len(highs) < n + 1 or len(lows) < n + 1 or len(closes) < n + 1:
            return None
        if not (len(highs) == len(lows) == len(closes)):
            return None
        # Gap/zero/NaN or inverted OHLC must not become a fake volatility reading
        if any(not _valid_ohlc_bar(h, lo, c) for h, lo, c in zip(highs, lows, closes)):
            return None

        true_ranges: List[float] = []
        for i in range(1, len(closes)):
            high_low = float(highs[i]) - float(lows[i])
            high_close = abs(float(highs[i]) - float(closes[i - 1]))
            low_close = abs(float(lows[i]) - float(closes[i - 1]))
            true_ranges.append(max(high_low, high_close, low_close))

        if len(true_ranges) < n:
            return None

        atr = float(sum(true_ranges[:n]) / float(n))
        for tr in true_ranges[n:]:
            atr = ((atr * (n - 1)) + tr) / float(n)

        if not math.isfinite(atr) or atr < 0:
            return None
        return atr

    @staticmethod
    def _calculate_ema(data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average.

        Caller must pass a positive coerced period (never bool).
        """
        n = int(period)
        ema = np.zeros_like(data)
        multiplier = 2 / (n + 1)

        # Start with SMA
        ema[n - 1] = np.mean(data[:n])

        # Calculate EMA
        for i in range(n, len(data)):
            ema[i] = (data[i] - ema[i - 1]) * multiplier + ema[i - 1]

        return ema

    @staticmethod
    def generate_signals(
        prices: List[float],
        volumes: Optional[List[float]] = None,
        highs: Optional[List[float]] = None,
        lows: Optional[List[float]] = None
    ) -> Dict[str, any]:
        """
        Generate comprehensive trading signals from technical indicators.

        Returns:
            Dict with all indicators and overall signal strength
        """
        signals = {}

        # RSI signals
        rsi = TechnicalIndicators.calculate_rsi(prices)
        if rsi is not None:
            signals['rsi'] = rsi
            signals['rsi_signal'] = 'oversold' if rsi < 30 else 'overbought' if rsi > 70 else 'neutral'

        # MACD signals
        macd = TechnicalIndicators.calculate_macd(prices)
        if macd:
            signals['macd'] = macd
            signals['macd_signal'] = 'bullish' if macd['histogram'] > 0 else 'bearish'

        # Bollinger Bands signals
        bb = TechnicalIndicators.calculate_bollinger_bands(prices)
        if bb:
            signals['bollinger'] = bb
            if bb['position'] < 0.2:
                signals['bb_signal'] = 'oversold'
            elif bb['position'] > 0.8:
                signals['bb_signal'] = 'overbought'
            else:
                signals['bb_signal'] = 'neutral'

        # Volume analysis
        if volumes:
            vol_analysis = TechnicalIndicators.analyze_volume(volumes, prices)
            if vol_analysis:
                signals['volume'] = vol_analysis
                signals['volume_signal'] = 'high' if vol_analysis['volume_ratio'] > 1.5 else 'normal'

        # ATR for volatility
        if highs and lows:
            atr = TechnicalIndicators.calculate_atr(highs, lows, prices)
            if atr is not None:
                signals['atr'] = atr
                signals['volatility'] = atr / prices[-1] if prices[-1] > 0 else 0

        # Calculate overall signal score (-100 to +100)
        score = TechnicalIndicators._calculate_signal_score(signals)
        signals['overall_score'] = score
        signals['overall_signal'] = 'BUY' if score > 30 else 'SELL' if score < -30 else 'HOLD'

        return signals

    @staticmethod
    def _calculate_signal_score(signals: Dict) -> float:
        """Calculate overall signal score from individual indicators."""
        score = 0
        count = 0

        # RSI contribution
        if 'rsi' in signals:
            rsi = signals['rsi']
            if rsi < 30:
                score += 30  # Oversold = bullish
            elif rsi > 70:
                score -= 30  # Overbought = bearish
            else:
                score += (50 - rsi) * 0.6  # Gradual scoring
            count += 1

        # MACD contribution
        if 'macd' in signals:
            histogram = signals['macd']['histogram']
            score += np.clip(histogram * 10, -30, 30)  # Scale to ±30
            count += 1

        # Bollinger Bands contribution
        if 'bollinger' in signals:
            position = signals['bollinger']['position']
            if position < 0.2:
                score += 20  # Near lower band = bullish
            elif position > 0.8:
                score -= 20  # Near upper band = bearish
            count += 1

        # Volume contribution
        if 'volume' in signals:
            vol_ratio = signals['volume']['volume_ratio']
            correlation = signals['volume']['price_volume_correlation']
            if vol_ratio > 1.5 and correlation > 0:
                score += 15  # High volume + positive correlation = bullish
            elif vol_ratio > 1.5 and correlation < 0:
                score -= 15  # High volume + negative correlation = bearish
            count += 1

        # Average the score
        return score / count if count > 0 else 0
