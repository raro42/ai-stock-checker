#!/usr/bin/env python3
"""
Technical indicators for market analysis.
Implements RSI, MACD, Bollinger Bands, and volume analysis.
"""

from typing import List, Dict, Optional
import numpy as np


class TechnicalIndicators:
    """Calculate technical indicators for trading signals."""

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """
        Calculate Relative Strength Index (RSI) using Wilder smoothing.

        Args:
            prices: List of closing prices (oldest to newest)
            period: RSI period (default 14)

        Returns:
            RSI value between 0-100, or None if insufficient data
        """
        if len(prices) < period + 1:
            return None

        deltas = np.diff(np.asarray(prices, dtype=float))
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        # Seed with simple average of first `period` changes
        avg_gain = float(np.mean(gains[:period]))
        avg_loss = float(np.mean(losses[:period]))

        # Wilder exponential smoothing for remaining bars
        for i in range(period, len(gains)):
            avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)

    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Dict[str, float]:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        Args:
            prices: List of closing prices
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line period (default 9)

        Returns:
            Dict with macd, signal, histogram, or None if insufficient data
        """
        if len(prices) < slow_period + signal_period:
            return None

        prices_array = np.array(prices)

        # Calculate EMAs
        fast_ema = TechnicalIndicators._calculate_ema(prices_array, fast_period)
        slow_ema = TechnicalIndicators._calculate_ema(prices_array, slow_period)

        # MACD line
        macd_line = fast_ema - slow_ema

        # Signal line (EMA of MACD)
        signal_line = TechnicalIndicators._calculate_ema(macd_line, signal_period)

        # Histogram
        histogram = macd_line[-1] - signal_line[-1]

        return {
            'macd': float(macd_line[-1]),
            'signal': float(signal_line[-1]),
            'histogram': float(histogram)
        }

    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Dict[str, float]:
        """
        Calculate Bollinger Bands.

        Args:
            prices: List of closing prices
            period: Moving average period (default 20)
            std_dev: Standard deviation multiplier (default 2.0)

        Returns:
            Dict with upper, middle, lower bands and current position
        """
        if len(prices) < period:
            return None

        prices_array = np.array(prices[-period:])

        # Middle band (SMA)
        middle = np.mean(prices_array)

        # Standard deviation
        std = np.std(prices_array)

        # Upper and lower bands
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)

        # Current price position
        current_price = prices[-1]
        position = (current_price - lower) / (upper - lower) if upper != lower else 0.5

        return {
            'upper': float(upper),
            'middle': float(middle),
            'lower': float(lower),
            'position': float(position),  # 0 = at lower band, 1 = at upper band
            'bandwidth': float((upper - lower) / middle)  # Volatility measure
        }

    @staticmethod
    def analyze_volume(
        volumes: List[float],
        prices: List[float],
        period: int = 20
    ) -> Dict[str, float]:
        """
        Analyze volume patterns.

        Args:
            volumes: List of volume data
            prices: List of closing prices
            period: Analysis period

        Returns:
            Dict with volume analysis metrics
        """
        if len(volumes) < period or len(prices) < period:
            return None

        recent_volumes = np.array(volumes[-period:])
        avg_volume = np.mean(recent_volumes)
        current_volume = volumes[-1]

        # Volume surge detection
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # Price-volume correlation
        recent_prices = np.array(prices[-period:])
        correlation = np.corrcoef(recent_prices, recent_volumes)[0, 1] if len(recent_prices) > 1 else 0

        return {
            'current_volume': float(current_volume),
            'avg_volume': float(avg_volume),
            'volume_ratio': float(volume_ratio),
            'price_volume_correlation': float(correlation)
        }

    @staticmethod
    def calculate_atr(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14
    ) -> float:
        """
        Calculate Average True Range (ATR) for volatility measurement.

        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of closing prices
            period: ATR period

        Returns:
            ATR value
        """
        if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
            return None

        true_ranges = []
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            true_ranges.append(max(high_low, high_close, low_close))

        atr = np.mean(true_ranges[-period:])
        return float(atr)

    @staticmethod
    def _calculate_ema(data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average."""
        ema = np.zeros_like(data)
        multiplier = 2 / (period + 1)

        # Start with SMA
        ema[period-1] = np.mean(data[:period])

        # Calculate EMA
        for i in range(period, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]

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
