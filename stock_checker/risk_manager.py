#!/usr/bin/env python3
"""
Risk management system for intelligent trading.
Implements stop-loss, position sizing, and drawdown protection.
"""

from typing import Dict, Optional, Tuple


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
        self.max_position_size = max_position_size
        self.max_total_risk = max_total_risk
        self.max_drawdown = max_drawdown
        self.stop_loss_pct = stop_loss_pct
        self.use_atr_stops = use_atr_stops
        self.atr_multiplier = atr_multiplier

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
        # Base position size
        base_size = portfolio_value * self.max_position_size

        # Adjust for volatility if available
        if volatility is not None and volatility > 0:
            # Higher volatility = smaller position
            vol_adjustment = 1.0 / (1.0 + volatility)
            base_size *= vol_adjustment

        # Scale by signal strength
        base_size *= signal_strength

        # Convert to shares
        shares = int(base_size / current_price)

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
            Stop loss price
        """
        if self.use_atr_stops and atr is not None:
            # ATR-based stop (more dynamic)
            stop_distance = atr * self.atr_multiplier
            stop_price = entry_price - stop_distance
        else:
            # Percentage-based stop
            stop_price = entry_price * (1 - self.stop_loss_pct)

        self.stop_losses[symbol] = stop_price
        self.entry_prices[symbol] = entry_price

        # Calculate risk for this position
        risk_per_share = entry_price - stop_price
        self.position_risks[symbol] = risk_per_share

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

        return current_price <= self.stop_losses[symbol]

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

        current_stop = self.stop_losses[symbol]
        new_stop = current_price * (1 - trail_pct)

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
        total_risk = sum(self.position_risks.values())
        risk_pct = total_risk / portfolio_value if portfolio_value > 0 else 0

        return risk_pct <= self.max_total_risk, risk_pct

    def update_drawdown(self, portfolio_value: float) -> Tuple[bool, float]:
        """
        Update drawdown tracking and check if max drawdown exceeded.

        Returns:
            (within_limits, current_drawdown_pct)
        """
        # Update peak
        if portfolio_value > self.peak_value:
            self.peak_value = portfolio_value
            self.current_drawdown = 0.0
        else:
            # Calculate drawdown
            self.current_drawdown = (self.peak_value - portfolio_value) / self.peak_value

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
            Optimal position size fraction (0-1)
        """
        if avg_loss == 0 or win_rate == 0:
            return self.max_position_size

        win_loss_ratio = avg_win / avg_loss
        kelly = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio

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
        # Reduce score if we have too many positions
        position_penalty = current_positions / 15.0  # Penalty increases with positions

        # Reduce score for high volatility
        vol_penalty = min(volatility * 2, 0.5)  # Cap at 50% reduction

        # Apply penalties
        adjusted_score = signal_score * (1 - position_penalty) * (1 - vol_penalty)

        return adjusted_score
