#!/usr/bin/env python3
"""
Risk management system for intelligent trading.
Implements stop-loss, position sizing, and drawdown protection.

Display/quarantine helper (A10) — not the live entry sizer. Still refuse
non-finite / impossible Kelly inputs (tradermonty a1d65fd). ATR stops size
risk against the cent-rounded reported stop (tradermonty #813).
"""

import math
from typing import Dict, Optional, Tuple


def _positive_finite(x: object) -> bool:
    """True for finite >0 numbers; bool/NaN refuse (True→1.0 trap)."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return False
    return math.isfinite(float(x)) and float(x) > 0.0


def _coerce_risk_frac(value: object, default: float) -> float:
    """Positive finite risk fraction, or ``default`` when bool/gap/NaN.

    tradermonty #700/#655 + xang1234/portfolio AI: ``float(True)==1.0`` must
    not invent a 100% size / risk / drawdown / stop or a 1× ATR stop.
    """
    if not _positive_finite(value):
        return float(default)
    return float(value)  # type: ignore[arg-type]


class RiskManager:
    """Manage trading risk through position sizing, stop-losses, and drawdown limits."""

    def __init__(
        self,
        max_position_size: float = 0.10,  # Max 10% per position
        max_total_risk: float = 0.25,  # Max 25% total portfolio at risk
        max_drawdown: float = 0.15,  # Max 15% drawdown before stopping
        stop_loss_pct: float = 0.05,  # 5% stop loss
        use_atr_stops: bool = True,  # Use ATR-based dynamic stops
        atr_multiplier: float = 2.0,  # ATR multiplier for stops
    ):
        # tradermonty #700/#655: refuse bool knobs — True→100% size / 1× ATR.
        self.max_position_size = _coerce_risk_frac(max_position_size, 0.10)
        self.max_total_risk = _coerce_risk_frac(max_total_risk, 0.25)
        self.max_drawdown = _coerce_risk_frac(max_drawdown, 0.15)
        self.stop_loss_pct = _coerce_risk_frac(stop_loss_pct, 0.05)
        self.use_atr_stops = bool(use_atr_stops)
        self.atr_multiplier = _coerce_risk_frac(atr_multiplier, 2.0)

        # Track stop losses for each position
        self.stop_losses: Dict[str, float] = {}  # symbol -> stop price
        self.entry_prices: Dict[str, float] = {}  # symbol -> entry price
        self.position_risks: Dict[str, float] = {}  # symbol -> risk amount

        # Track drawdown
        self.peak_value = 0.0
        self.current_drawdown = 0.0

    def calculate_position_size(
        self,
        portfolio_value: float,
        current_price: float,
        volatility: Optional[float] = None,
        signal_strength: float = 1.0
    ) -> int:
        """
        Calculate optimal position size based on risk parameters.

        Args:
            portfolio_value: Current portfolio value
            current_price: Current asset price
            volatility: Asset volatility (optional, for volatility-based sizing)
            signal_strength: Signal strength 0-1 (scales position size)

        Returns:
            Number of shares to buy
        """
        # tradermonty #700/#655: refuse bool — True→€1 equity / $1 print / full strength.
        if (
            isinstance(portfolio_value, bool)
            or isinstance(current_price, bool)
            or isinstance(signal_strength, bool)
            or not math.isfinite(portfolio_value)
            or not math.isfinite(current_price)
            or not math.isfinite(signal_strength)
            or portfolio_value <= 0
            or current_price <= 0
            or signal_strength < 0
        ):
            return 0
        if volatility is not None and (
            isinstance(volatility, bool)
            or not math.isfinite(volatility)
            or volatility < 0
        ):
            return 0

        # Base position size
        base_size = float(portfolio_value) * self.max_position_size

        # Adjust for volatility if available
        if volatility is not None and volatility > 0:
            # Higher volatility = smaller position
            vol_adjustment = 1.0 / (1.0 + float(volatility))
            base_size *= vol_adjustment

        # Scale by signal strength
        base_size *= float(signal_strength)

        # Convert to shares
        shares = int(base_size / float(current_price))

        return max(shares, 0)

    def set_stop_loss(
        self,
        symbol: str,
        entry_price: float,
        atr: Optional[float] = None
    ) -> float:
        """
        Set stop loss for a position.

        Args:
            symbol: Asset symbol
            entry_price: Entry price
            atr: Average True Range (optional, for dynamic stops)

        Returns:
            Stop loss price (cent-rounded). ATR path uses the reported stop
            for risk_per_share (tradermonty #813); invalid ATR falls back to %.
        """
        if not _positive_finite(entry_price):
            return 0.0
        entry = float(entry_price)
        stop_price: Optional[float] = None
        if self.use_atr_stops and atr is not None and _positive_finite(atr):
            if _positive_finite(self.atr_multiplier):
                raw = entry - float(atr) * float(self.atr_multiplier)
                reported = round(raw, 2)
                # Size / track risk at the monetized stop, not atr×mult.
                if 0.0 < reported < entry:
                    stop_price = reported
        if stop_price is None:
            if not _positive_finite(self.stop_loss_pct) or self.stop_loss_pct >= 1.0:
                return 0.0
            stop_price = round(entry * (1.0 - float(self.stop_loss_pct)), 2)
            if not (0.0 < stop_price < entry):
                return 0.0

        self.stop_losses[symbol] = stop_price
        self.entry_prices[symbol] = entry
        self.position_risks[symbol] = entry - stop_price
        return stop_price

    def check_stop_loss(self, symbol: str, current_price: float) -> bool:
        """
        Check if stop loss is triggered.

        Args:
            symbol: Asset symbol
            current_price: Current price

        Returns:
            True if stop loss triggered
        """
        if symbol not in self.stop_losses:
            return False

        # tradermonty #700/#655: refuse bool — True→$1 cannot invent a stop hit.
        if not _positive_finite(current_price):
            return False
        return float(current_price) <= self.stop_losses[symbol]

    def update_trailing_stop(
        self,
        symbol: str,
        current_price: float,
        trail_pct: float = 0.05
    ) -> float:
        """
        Update trailing stop loss.

        Args:
            symbol: Asset symbol
            current_price: Current price
            trail_pct: Trailing percentage (default 5%)

        Returns:
            New stop loss price
        """
        if symbol not in self.stop_losses:
            return None

        # tradermonty #700/#655: refuse bool — True→$1 mark / True→100% trail → stop $0.
        if not _positive_finite(current_price) or not _positive_finite(trail_pct):
            return self.stop_losses[symbol]
        if float(trail_pct) >= 1.0:
            return self.stop_losses[symbol]

        current_stop = self.stop_losses[symbol]
        new_stop = float(current_price) * (1.0 - float(trail_pct))

        # Only raise the stop, never lower it
        if new_stop > current_stop:
            self.stop_losses[symbol] = new_stop
            return new_stop

        return current_stop

    def check_total_risk(self, portfolio_value: float) -> Tuple[bool, float]:
        """
        Check if total portfolio risk is within limits.

        Returns:
            (within_limits, current_risk_pct)
        """
        # tradermonty #700/#655: refuse bool — True→€1 equity invents risk%.
        if not _positive_finite(portfolio_value):
            return True, 0.0
        total_risk = sum(self.position_risks.values())
        risk_pct = total_risk / float(portfolio_value)

        return risk_pct <= self.max_total_risk, risk_pct

    def update_drawdown(self, portfolio_value: float) -> Tuple[bool, float]:
        """
        Update drawdown tracking and check if max drawdown exceeded.

        Returns:
            (within_limits, current_drawdown_pct)
        """
        # tradermonty #700/#655: refuse bool — True→€1 equity invents peak/DD.
        if not _positive_finite(portfolio_value):
            return True, self.current_drawdown
        pv = float(portfolio_value)
        # Update peak
        if pv > self.peak_value:
            self.peak_value = pv
            self.current_drawdown = 0.0
        else:
            # Calculate drawdown
            self.current_drawdown = (self.peak_value - pv) / self.peak_value

        return self.current_drawdown <= self.max_drawdown, self.current_drawdown

    def remove_position(self, symbol: str):
        """Remove position from risk tracking."""
        if symbol in self.stop_losses:
            del self.stop_losses[symbol]
        if symbol in self.entry_prices:
            del self.entry_prices[symbol]
        if symbol in self.position_risks:
            del self.position_risks[symbol]

    def get_risk_metrics(self, portfolio_value: float) -> Dict:
        """Get current risk metrics."""
        within_risk_limit, risk_pct = self.check_total_risk(portfolio_value)
        within_dd_limit, dd_pct = self.update_drawdown(portfolio_value)

        return {
            'total_risk_pct': risk_pct * 100,
            'max_risk_pct': self.max_total_risk * 100,
            'within_risk_limit': within_risk_limit,
            'current_drawdown_pct': dd_pct * 100,
            'max_drawdown_pct': self.max_drawdown * 100,
            'within_drawdown_limit': within_dd_limit,
            'peak_value': self.peak_value,
            'active_stops': len(self.stop_losses),
            'stop_losses': dict(self.stop_losses)
        }

    def should_reduce_exposure(self, portfolio_value: float) -> bool:
        """
        Check if we should reduce exposure due to risk limits.

        Returns:
            True if we should reduce exposure
        """
        within_risk, _ = self.check_total_risk(portfolio_value)
        within_dd, _ = self.update_drawdown(portfolio_value)

        return not within_risk or not within_dd

    def calculate_kelly_criterion(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate Kelly Criterion for optimal position sizing.

        Args:
            win_rate: Historical win rate (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount

        Returns:
            Optimal position size fraction (0-1). 0 when inputs are
            non-finite or win_rate is not strictly between 0 and 1
            (perfect WR made full Kelly 100% of equity — tradermonty a1d65fd).
        """
        # tradermonty #700/#655: refuse bool — True→1 invents WR/€ wins/losses.
        if (
            isinstance(win_rate, bool)
            or isinstance(avg_win, bool)
            or isinstance(avg_loss, bool)
            or not math.isfinite(win_rate)
            or not math.isfinite(avg_win)
            or not math.isfinite(avg_loss)
            or not (0.0 < float(win_rate) < 1.0)
            or float(avg_win) <= 0
            or float(avg_loss) <= 0
        ):
            return 0.0

        wr = float(win_rate)
        aw = float(avg_win)
        al = float(avg_loss)
        win_loss_ratio = aw / al
        if not math.isfinite(win_loss_ratio) or win_loss_ratio <= 0:
            return 0.0

        kelly = (wr * win_loss_ratio - (1.0 - wr)) / win_loss_ratio
        if not math.isfinite(kelly):
            return 0.0

        # Apply half-Kelly for safety
        kelly = kelly * 0.5

        # Cap at max position size
        return min(max(kelly, 0), self.max_position_size)

    def calculate_risk_adjusted_score(
        self,
        signal_score: float,
        volatility: float,
        current_positions: int
    ) -> float:
        """
        Adjust signal score based on current risk exposure.

        Args:
            signal_score: Raw signal score (-100 to +100)
            volatility: Asset volatility
            current_positions: Number of current positions

        Returns:
            Risk-adjusted score
        """
        from stock_checker.technical_indicators import (
            _finite_signed,
            coerce_nonneg_int,
        )

        # tradermonty #700/#655: refuse bool — True→1 invents score/vol/slots.
        if not _finite_signed(signal_score) or not _finite_signed(volatility):
            return 0.0
        n_pos = coerce_nonneg_int(current_positions)
        if n_pos is None:
            return 0.0
        score = float(signal_score)  # type: ignore[arg-type]
        vol = float(volatility)  # type: ignore[arg-type]
        if vol < 0.0:
            return 0.0

        # Reduce score if we have too many positions
        position_penalty = n_pos / 15.0  # Penalty increases with positions

        # Reduce score for high volatility
        vol_penalty = min(vol * 2.0, 0.5)  # Cap at 50% reduction

        # Apply penalties
        return score * (1.0 - position_penalty) * (1.0 - vol_penalty)
