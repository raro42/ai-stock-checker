#!/usr/bin/env python3

from typing import Dict, Optional, List
from .technical_indicators import TechnicalIndicators, _finite_signed, _valid_close


class RecommendationEngine:
    """Advanced recommendation engine with multi-factor analysis."""

    def __init__(self):
        self.indicators = TechnicalIndicators()

    def analyze_stock_recommendation(self, stock_data: dict) -> Dict:
        """
        Analyze stock and generate buy/sell/hold recommendation using advanced factors.

        Returns dict with action, confidence, reasoning, and score.
        """
        try:
            reasons = []
            score = 0.0

            symbol = stock_data.get("symbol", "Unknown")
            current_price = stock_data.get("current_price")

            # PRIMARY FACTOR: Multi-Timeframe Momentum (45 points max)
            try:
                momentum_score = self._calculate_multi_timeframe_score(stock_data)
                momentum_score = float(momentum_score) if momentum_score is not None else 0.0
            except Exception:
                momentum_score = 0.0
            score += momentum_score

            # SECONDARY FACTOR: Technical Strength (25 points max)
            try:
                technical_score = self._calculate_technical_score(stock_data)
                technical_score = float(technical_score) if technical_score is not None else 0.0
            except Exception:
                technical_score = 0.0
            score += technical_score

            # TERTIARY FACTOR: Valuation & Fundamentals (20 points max)
            try:
                fundamental_score = self._calculate_fundamental_score(stock_data)
                fundamental_score = float(fundamental_score) if fundamental_score is not None else 0.0
            except Exception:
                fundamental_score = 0.0
            score += fundamental_score

            # QUATERNARY FACTOR: Volume & Sentiment (10 points max)
            try:
                volume_sentiment_score = self._calculate_volume_sentiment_score(stock_data)
                volume_sentiment_score = float(volume_sentiment_score) if volume_sentiment_score is not None else 0.0
            except Exception:
                volume_sentiment_score = 0.0
            score += volume_sentiment_score

            # Ensure score is always numeric
            try:
                score = float(score) if score is not None else 0.0
            except (TypeError, ValueError):
                score = 0.0
        except Exception:
            # Fallback on any error
            reasons = []
            score = 0.0
            symbol = stock_data.get("symbol", "Unknown")
            current_price = stock_data.get("current_price")

        # Determine action and confidence with IMPROVED thresholds
        if score >= 50:
            action = "BUY"
            confidence = "HIGH"
        elif score >= 25:
            action = "BUY"
            confidence = "MEDIUM"
        elif score >= 5:
            action = "BUY"
            confidence = "LOW"
        elif score <= -20:
            action = "SELL"
            confidence = "HIGH"
        elif score <= -5:
            action = "SELL"
            confidence = "MEDIUM"
        else:
            action = "HOLD"
            confidence = "LOW"
            reasons.append("Waiting for stronger signal")

        return {
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "score": score,
            "reasons": reasons,
            "current_price": current_price,
        }

    def _calculate_multi_timeframe_score(self, stock_data: dict) -> float:
        """Multi-timeframe momentum scoring with trend confirmation."""
        score = 0.0

        # Bool/NaN % prints must not invent mild daily up (float(True)→1.0).
        daily_change = 0.0
        weekly_change = 0.0
        monthly_change = 0.0
        dc = stock_data.get("daily_change")
        if _finite_signed(dc):
            daily_change = float(dc)
        wc = stock_data.get("weekly_change")
        if _finite_signed(wc):
            weekly_change = float(wc)
        mc = stock_data.get("monthly_change")
        if _finite_signed(mc):
            monthly_change = float(mc)

        # Daily momentum (35% weight)
        if daily_change > 3:
            score += 15.75  # Strong daily up
        elif daily_change > 1.5:
            score += 10.5   # Moderate daily up
        elif daily_change > 0.5:
            score += 5.25   # Mild daily up
        elif daily_change < -3:
            score += 10.5   # Daily dip (reversal potential)
        elif daily_change < -1.5:
            score += 5.25   # Moderate daily dip

        # Weekly trend confirmation (35% weight)
        if weekly_change > 5:
            score += 15.75
        elif weekly_change > 2:
            score += 10.5
        elif weekly_change < -5:
            score += 7     # Weekly dip potential

        # Monthly context (30% weight)
        if monthly_change > 10:
            score += 13.5  # Bull market context
        elif monthly_change < -10:
            score += 6.75  # Bear market caution

        return score

    def _calculate_technical_score(self, stock_data: dict) -> float:
        """Technical indicators scoring for trend strength."""
        score = 0

        # RSI (Relative Strength Index) — bool/NaN unavailable (True→1.0 ≠ oversold)
        rsi = stock_data.get("rsi")
        if _finite_signed(rsi):
            rsi_v = float(rsi)
            if rsi_v < 30:
                score += 12  # Oversold
            elif rsi_v > 70:
                score -= 6   # Overbought
            elif rsi_v > 60:
                score += 3   # Bullish
            elif rsi_v < 40:
                score -= 2   # Bearish

        # MACD signal
        macd_signal = stock_data.get("macd_histogram")
        if _finite_signed(macd_signal):
            macd_v = float(macd_signal)
            if macd_v > 0.1:
                score += 8   # Bullish divergence
            elif macd_v < -0.1:
                score -= 4   # Bearish divergence

        # Moving average alignment — gap/bool marks unavailable (True→$1 invent)
        current_price = stock_data.get("current_price")
        sma_20 = stock_data.get("sma_20")
        sma_50 = stock_data.get("sma_50")
        if (
            _valid_close(current_price)
            and _valid_close(sma_20)
            and _valid_close(sma_50)
        ):
            px, s20, s50 = float(current_price), float(sma_20), float(sma_50)
            if px > s20 > s50:
                score += 5
            elif px < s20 < s50:
                score -= 3

        return score

    def _calculate_fundamental_score(self, stock_data: dict) -> float:
        """Fundamental analysis with market positioning."""
        score = 0

        # 52-week position (value consideration)
        range_position = stock_data.get("52_week_position")
        if _finite_signed(range_position):
            rp = float(range_position)
            if rp < 25:
                score += 8  # Potential value
            elif rp > 90:
                score -= 3  # Potentially overextended

        # P/E ratio (if available)
        pe_ratio = stock_data.get("pe_ratio")
        if _finite_signed(pe_ratio):
            pe = float(pe_ratio)
            if pe < 20:
                score += 7
            elif pe > 35:
                score -= 5

        # Market cap consideration (smaller caps = higher risk/reward)
        market_cap = stock_data.get("market_cap")
        if _finite_signed(market_cap) and float(market_cap) > 0:
            if float(market_cap) < 5000000000:  # Under $5B
                score += 5  # Small/mid cap premium

        # Analyst recommendations
        analyst_rating = stock_data.get("analyst_rating", "N/A")
        rating_scores = {
            "Strong Buy": 5,
            "Buy": 3,
            "Hold": 0,
            "Sell": -3,
            "Strong Sell": -5
        }
        score += rating_scores.get(analyst_rating, 0)

        return score

    def _calculate_volume_sentiment_score(self, stock_data: dict) -> float:
        """Volume confirmation, news/OpenBB sentiment, earnings proximity soft penalty."""
        score = 0.0

        # tradermonty #700/#655 + xang1234/portfolio AI: refuse bool —
        # False→0 invents thin volume (−3); True→1 invents mild sentiment /
        # near-earnings (−4) after momentum/technical marks already refused.
        volume_ratio = stock_data.get("volume_ratio")
        if _finite_signed(volume_ratio):
            vr = float(volume_ratio)  # type: ignore[arg-type]
            if vr > 1.5:
                score += 5
            elif vr < 0.7:
                score -= 3

        news_sentiment = stock_data.get("news_sentiment")
        if _finite_signed(news_sentiment):
            ns = max(-1.0, min(1.0, float(news_sentiment)))  # type: ignore[arg-type]
            score += ns * 3.0

        openbb_sentiment = stock_data.get("openbb_sentiment")
        if _finite_signed(openbb_sentiment):
            os_ = max(-1.0, min(1.0, float(openbb_sentiment)))  # type: ignore[arg-type]
            score += os_ * 2.0

        days_to_earn = stock_data.get("days_to_earnings")
        if _finite_signed(days_to_earn):
            d = float(days_to_earn)  # type: ignore[arg-type]
            if 0 <= d <= 2:
                score -= 4
            elif -1 <= d < 0:
                score -= 2

        return float(max(-10.0, min(10.0, score)))

    def analyze_bitcoin_recommendation(self, btc_data: dict) -> Dict:
        """
        Analyze Bitcoin with enhanced crypto-specific factors.
        """
        reasons = []
        score = 0

        current_price = btc_data.get("current_price")
        # Bool/NaN/% gaps unavailable — never invent flat 0 / True→1.0 momentum.
        # MarketAnalyzer speaks change_1d/7d/30d; older callers use daily/weekly/monthly.
        change_1d = 0.0
        change_7d = 0.0
        change_30d = 0.0
        volatility = 0.0
        volume_ratio = 0.0
        dc = btc_data.get("daily_change")
        if not _finite_signed(dc):
            dc = btc_data.get("change_1d")
        if _finite_signed(dc):
            change_1d = float(dc)
        wc = btc_data.get("weekly_change")
        if not _finite_signed(wc):
            wc = btc_data.get("change_7d")
        if _finite_signed(wc):
            change_7d = float(wc)
        mc = btc_data.get("monthly_change")
        if not _finite_signed(mc):
            mc = btc_data.get("change_30d")
        if _finite_signed(mc):
            change_30d = float(mc)
        vol = btc_data.get("volatility_30d")
        if _finite_signed(vol):
            volatility = float(vol)
        vr = btc_data.get("volume_ratio")
        if _finite_signed(vr):
            volume_ratio = float(vr)
        rsi = btc_data.get("rsi")

        # SHORT-TERM MOMENTUM (40% weight)
        if change_1d > 5:
            score += 16  # Explosive up
        elif change_1d > 2:
            score += 12  # Good momentum
        elif change_1d > 0.5:
            score += 8   # Positive momentum
        elif change_1d < -5:
            score += 14  # Flash crash = buy!
        elif change_1d < -2:
            score += 10  # Medium dip

        # MEDIUM-TERM TREND (30% weight)
        if change_7d > 15:
            score += 12
        elif change_7d > 5:
            score += 6
        elif change_7d < -15:
            score += 9  # Oversold

        # LONG-TERM CONTEXT (15% weight)
        if change_30d > 20:
            score += 6
        elif change_30d < -20:
            score += 4.5

        # TECHNICAL FACTORS (15% weight) — bool RSI unavailable (True→1.0 ≠ oversold)
        if _finite_signed(rsi):
            rsi_v = float(rsi)
            if rsi_v < 30:
                score += 4.5  # Oversold
            elif rsi_v > 70:
                score -= 2.25  # Overbought

        if volume_ratio > 1.5:
            score += 2.25  # Volume confirmation

        # VOLATILITY PREMIUM
        if volatility > 8:
            score += 3  # High vol = more opportunity

        # ENHANCED CRYPTO THRESHOLDS
        if score >= 40:
            action = "BUY"
            confidence = "HIGH"
        elif score >= 20:
            action = "BUY"
            confidence = "MEDIUM"
        elif score >= 5:
            action = "BUY"
            confidence = "LOW"
        elif score <= -25:
            action = "SELL"
            confidence = "HIGH"
        elif score <= -10:
            action = "SELL"
            confidence = "MEDIUM"
        else:
            action = "HOLD"
            confidence = "LOW"
            reasons.append("⏸️ Waiting for crypto micro-movement")

        return {
            "symbol": "BTC-USD",
            "action": action,
            "confidence": confidence,
            "score": score,
            "reasons": reasons,
            "current_price": current_price,
        }

    def analyze_with_technical_indicators(
        self,
        stock_data: dict,
        price_history: Optional[List[float]] = None,
        volume_history: Optional[List[float]] = None,
        high_history: Optional[List[float]] = None,
        low_history: Optional[List[float]] = None
    ) -> Dict:
        """
        Enhanced analysis using technical indicators.

        Args:
            stock_data: Basic stock data
            price_history: List of closing prices (oldest to newest)
            volume_history: List of volumes
            high_history: List of high prices
            low_history: List of low prices

        Returns:
            Dict with action, confidence, score, and technical signals
        """
        # Get base recommendation
        base_rec = self.analyze_stock_recommendation(stock_data)

        # If we have price history, enhance with technical analysis
        if price_history and len(price_history) >= 20:
            tech_signals = self.indicators.generate_signals(
                prices=price_history,
                volumes=volume_history,
                highs=high_history,
                lows=low_history
            )

            # Adjust score based on technical signals
            tech_score = tech_signals.get('overall_score', 0)
            combined_score = (base_rec['score'] * 0.6) + (tech_score * 0.4)

            # Update recommendation
            base_rec['score'] = combined_score
            base_rec['technical_signals'] = tech_signals

            # Re-evaluate action based on combined score
            if combined_score >= 50:
                base_rec['action'] = "BUY"
                base_rec['confidence'] = "HIGH"
            elif combined_score >= 25:
                base_rec['action'] = "BUY"
                base_rec['confidence'] = "MEDIUM"
            elif combined_score >= 5:
                base_rec['action'] = "BUY"
                base_rec['confidence'] = "LOW"
            elif combined_score <= -20:
                base_rec['action'] = "SELL"
                base_rec['confidence'] = "HIGH"
            elif combined_score <= -5:
                base_rec['action'] = "SELL"
                base_rec['confidence'] = "MEDIUM"
            else:
                base_rec['action'] = "HOLD"
                base_rec['confidence'] = "LOW"

        return base_rec
