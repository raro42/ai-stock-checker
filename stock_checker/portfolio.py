#!/usr/bin/env python3

from datetime import datetime
from typing import Dict, List, Optional
from .risk_manager import RiskManager


class Portfolio:
    """Manage portfolio with cash, holdings, and transaction tracking."""

    def __init__(
        self,
        initial_cash: float = 10000.0,
        commission_rate: float = 0.001,
        persistence=None,
        enable_risk_management: bool = True
    ):
        """
        Initialize portfolio.

        Args:
            initial_cash: Starting cash in EUR
            commission_rate: Commission rate per trade (default 0.1% = 0.001)
            persistence: DataPersistence instance for saving state
        """
        self.persistence = persistence

        # Try to load existing portfolio state
        if self.persistence:
            loaded = self.persistence.load_portfolio()
            if loaded:
                self.initial_cash = loaded["initial_cash"]
                self.cash = loaded["cash"]
                self.commission_rate = loaded["commission_rate"]
                self.holdings = loaded["holdings"]
                self.avg_buy_price = loaded["avg_buy_price"]
                self.total_fees_paid = loaded["total_fees_paid"]
                self.transactions = self.persistence.load_trades()
                return

        # Initialize new portfolio
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission_rate = commission_rate
        self.holdings: Dict[str, float] = {}  # symbol -> quantity
        self.avg_buy_price: Dict[str, float] = {}  # symbol -> avg price
        self.transactions: List[Dict] = []
        self.total_fees_paid = 0.0

        # Initialize risk management
        self.enable_risk_management = enable_risk_management
        if self.enable_risk_management:
            self.risk_manager = RiskManager()
        else:
            self.risk_manager = None

        # Save initial state
        if self.persistence:
            self._save_state()

    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio value including cash and holdings."""
        holdings_value = 0.0
        for symbol, quantity in self.holdings.items():
            if symbol in current_prices:
                holdings_value += quantity * current_prices[symbol]
        return self.cash + holdings_value

    def get_total_value(self, current_prices: Dict[str, float] = None) -> float:
        """
        Calculate total portfolio value.
        If current_prices not provided, uses average buy prices (conservative estimate).
        """
        if current_prices:
            return self.get_portfolio_value(current_prices)

        # Use avg buy prices as fallback
        holdings_value = 0.0
        for symbol, quantity in self.holdings.items():
            if symbol in self.avg_buy_price:
                holdings_value += quantity * self.avg_buy_price[symbol]
        return self.cash + holdings_value

    def get_holdings_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate value of holdings only."""
        holdings_value = 0.0
        for symbol, quantity in self.holdings.items():
            if symbol in current_prices:
                holdings_value += quantity * current_prices[symbol]
        return holdings_value

    def can_buy(self, symbol: str, price: float, quantity: float) -> bool:
        """Check if we have enough cash to buy."""
        cost = price * quantity
        commission = cost * self.commission_rate
        total_cost = cost + commission
        return self.cash >= total_cost

    def buy(self, symbol: str, price: float, quantity: float, timestamp: str) -> Dict:
        """
        Execute buy order.

        Returns transaction details or None if insufficient funds.
        """
        cost = price * quantity
        commission = cost * self.commission_rate
        total_cost = cost + commission

        if self.cash < total_cost:
            return {
                "success": False,
                "reason": "Insufficient funds",
                "cash_available": self.cash,
                "cost_required": total_cost,
            }

        # Update holdings
        if symbol in self.holdings:
            # Update average buy price
            old_quantity = self.holdings[symbol]
            old_total_cost = old_quantity * self.avg_buy_price[symbol]
            new_total_cost = old_total_cost + cost
            new_quantity = old_quantity + quantity
            self.avg_buy_price[symbol] = new_total_cost / new_quantity
            self.holdings[symbol] = new_quantity
        else:
            self.holdings[symbol] = quantity
            self.avg_buy_price[symbol] = price

        self.cash -= total_cost
        self.total_fees_paid += commission

        transaction = {
            "timestamp": timestamp,
            "type": "BUY",
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "cost": cost,
            "commission": commission,
            "total_cost": total_cost,
            "cash_remaining": self.cash,
        }
        self.transactions.append(transaction)

        # Persist trade and state
        if self.persistence:
            self.persistence.append_trade(transaction)
            self._save_state()

        return {"success": True, "transaction": transaction}

    def can_sell(self, symbol: str, quantity: float) -> bool:
        """Check if we have enough shares to sell."""
        return symbol in self.holdings and self.holdings[symbol] >= quantity

    def sell(self, symbol: str, price: float, quantity: float, timestamp: str) -> Dict:
        """
        Execute sell order.

        Returns transaction details or None if insufficient shares.
        """
        if not self.can_sell(symbol, quantity):
            return {
                "success": False,
                "reason": "Insufficient shares",
                "holdings": self.holdings.get(symbol, 0),
                "quantity_requested": quantity,
            }

        proceeds = price * quantity
        commission = proceeds * self.commission_rate
        net_proceeds = proceeds - commission

        # Calculate profit/loss
        buy_price = self.avg_buy_price[symbol]
        profit_loss = (price - buy_price) * quantity

        # Update holdings
        self.holdings[symbol] -= quantity
        if self.holdings[symbol] <= 0:
            del self.holdings[symbol]
            del self.avg_buy_price[symbol]

        self.cash += net_proceeds
        self.total_fees_paid += commission

        transaction = {
            "timestamp": timestamp,
            "type": "SELL",
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "proceeds": proceeds,
            "commission": commission,
            "net_proceeds": net_proceeds,
            "buy_price": buy_price,
            "profit_loss": profit_loss,
            "profit_loss_pct": (profit_loss / (buy_price * quantity)) * 100,
            "cash_remaining": self.cash,
        }
        self.transactions.append(transaction)

        # Persist trade and state
        if self.persistence:
            self.persistence.append_trade(transaction)
            self._save_state()

        return {"success": True, "transaction": transaction}

    def _save_state(self):
        """Save portfolio state to disk."""
        if self.persistence:
            self.persistence.save_portfolio({
                "initial_cash": self.initial_cash,
                "cash": self.cash,
                "commission_rate": self.commission_rate,
                "holdings": self.holdings,
                "avg_buy_price": self.avg_buy_price,
                "total_fees_paid": self.total_fees_paid,
            })

    def get_position(self, symbol: str, current_price: float) -> Optional[Dict]:
        """Get details about a specific position."""
        if symbol not in self.holdings:
            return None

        quantity = self.holdings[symbol]
        avg_buy = self.avg_buy_price[symbol]
        current_value = quantity * current_price
        cost_basis = quantity * avg_buy
        profit_loss = current_value - cost_basis
        profit_loss_pct = (profit_loss / cost_basis) * 100

        return {
            "symbol": symbol,
            "quantity": quantity,
            "avg_buy_price": avg_buy,
            "current_price": current_price,
            "cost_basis": cost_basis,
            "current_value": current_value,
            "profit_loss": profit_loss,
            "profit_loss_pct": profit_loss_pct,
        }

    def get_summary(self, current_prices: Dict[str, float]) -> Dict:
        """Get portfolio summary with performance metrics."""
        total_value = self.get_portfolio_value(current_prices)
        holdings_value = self.get_holdings_value(current_prices)
        total_return = total_value - self.initial_cash
        total_return_pct = (total_return / self.initial_cash) * 100

        positions = []
        for symbol in self.holdings.keys():
            if symbol in current_prices:
                pos = self.get_position(symbol, current_prices[symbol])
                if pos:
                    positions.append(pos)

        summary = {
            "initial_cash": self.initial_cash,
            "current_cash": self.cash,
            "holdings_value": holdings_value,
            "total_value": total_value,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "total_fees_paid": self.total_fees_paid,
            "positions": positions,
            "num_transactions": len(self.transactions),
        }

        # Add risk metrics if enabled
        if self.risk_manager:
            risk_metrics = self.risk_manager.get_risk_metrics(total_value)
            summary['risk_metrics'] = risk_metrics

        return summary

    def check_stop_losses(self, current_prices: Dict[str, float]) -> List[str]:
        """
        Check all positions for stop loss triggers.

        Returns:
            List of symbols that triggered stop loss
        """
        if not self.risk_manager:
            return []

        triggered = []
        for symbol in list(self.holdings.keys()):
            if symbol in current_prices:
                if self.risk_manager.check_stop_loss(symbol, current_prices[symbol]):
                    triggered.append(symbol)

        return triggered

    def set_position_stop_loss(self, symbol: str, entry_price: float, atr: Optional[float] = None):
        """Set stop loss for a position."""
        if self.risk_manager:
            return self.risk_manager.set_stop_loss(symbol, entry_price, atr)
        return None

    def remove_position_risk(self, symbol: str):
        """Remove position from risk tracking."""
        if self.risk_manager:
            self.risk_manager.remove_position(symbol)
