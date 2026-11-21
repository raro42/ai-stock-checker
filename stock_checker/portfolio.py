#!/usr/bin/env python3

import math
import numbers
from typing import Any, Dict, List, Optional
from .risk_manager import RiskManager
from .fees import (
    DEFAULT_FEE_PRESET,
    REVOLUT_STANDARD_MIN_EUR,
    REVOLUT_STANDARD_RATE,
    FeeAllowanceLedger,
    free_legs_for_preset,
    rates_for_preset,
)
from .technical_indicators import _finite_signed, _valid_close, coerce_nonneg_int

# Paper desk is long-only (tradermonty #681 reject unsupported equity shorts).
UNSUPPORTED_SHORT_REASON = "Unsupported short — long-only book"
INVALID_FILL_PRICE_REASON = "Invalid fill price — refuse bool/gap/NaN marks"
_DEFAULT_INITIAL_CASH = 10000.0


def _coerce_portfolio_cash(
    value: object, default: float = _DEFAULT_INITIAL_CASH
) -> float:
    """Cash ≥0, or ``default`` when bool/gap (never ``True→€1``).

    tradermonty #700/#655 + xang1234/portfolio AI: ``float(True)`` must not
    invent a €1 book or clear capital to a fake €1 seed.
    """
    if not _finite_signed(value):
        return float(default)
    cash = float(value)  # type: ignore[arg-type]
    if cash < 0.0:
        return float(default)
    return cash


def _coerce_portfolio_rate(value: object, default: float) -> float:
    """Commission rate in [0, 1], or ``default`` when bool/gap (never ``True→100%``)."""
    if not _finite_signed(value):
        return float(default)
    rate = float(value)  # type: ignore[arg-type]
    if rate < 0.0 or rate > 1.0:
        return float(default)
    return rate


def _coerce_portfolio_min_eur(value: object, default: float) -> float:
    """Commission floor ≥0, or ``default`` when bool/gap (never ``True→€1`` invent)."""
    if not _finite_signed(value):
        return float(default)
    floor = float(value)  # type: ignore[arg-type]
    if floor < 0.0:
        return float(default)
    return floor


def _coerce_portfolio_fees_paid(value: object, default: float = 0.0) -> float:
    """Ledger fees paid ≥0, or ``default`` when bool/gap (never ``True→€1`` burn)."""
    if not _finite_signed(value):
        return float(default)
    paid = float(value)  # type: ignore[arg-type]
    if paid < 0.0:
        return float(default)
    return paid


def long_only_quantity_ok(quantity: Any) -> bool:
    """True when qty is a finite positive number (no shorts / zero / NaN / bool)."""
    # float(True)==1.0 — bool must not invent a 1-share lot.
    if isinstance(quantity, bool) or not isinstance(quantity, numbers.Real):
        return False
    q = float(quantity)
    return math.isfinite(q) and q > 0


def fill_price_ok(price: Any) -> bool:
    """tradermonty #655/#754: fills must be real finite positive numbers (never bool)."""
    return _valid_close(price)


def marked_lot_value(quantity: Any, price: Any) -> Optional[float]:
    """Long-lot market value, or None when qty/mark would invent (bool/gap/NaN).

    tradermonty #700/#655 + xang1234/portfolio AI: ``True→€1`` marks must not
    invent MTM equity after fill refuse already covered buy/sell.
    """
    if not long_only_quantity_ok(quantity) or not fill_price_ok(price):
        return None
    return float(quantity) * float(price)


def unsupported_short_symbols(holdings: Any) -> List[str]:
    """Symbols with non-positive qty in a holdings map (corrupt / short ledger)."""
    if not isinstance(holdings, dict):
        return []
    out: List[str] = []
    for sym, qty in holdings.items():
        name = str(sym or "").strip()
        if not name:
            continue
        if long_only_quantity_ok(qty):
            continue
        out.append(name.upper())
    return sorted(set(out))


class Portfolio:
    """Manage portfolio with cash, holdings, and transaction tracking."""

    def __init__(
        self,
        initial_cash: float = 10000.0,
        commission_rate: float = REVOLUT_STANDARD_RATE,
        commission_min_eur: float = REVOLUT_STANDARD_MIN_EUR,
        persistence=None,
        enable_risk_management: bool = True,
        fee_preset: str = DEFAULT_FEE_PRESET,
    ):
        """
        Initialize portfolio.

        Args:
            initial_cash: Starting cash in EUR
            commission_rate: Commission rate per side (default Revolut 0.25%)
            commission_min_eur: Minimum commission per side in EUR (default €1)
            persistence: DataPersistence instance for saving state
            fee_preset: Named preset label stored for Ops/desk honesty
        """
        self.persistence = persistence
        self.fee_preset = fee_preset or DEFAULT_FEE_PRESET
        # tradermonty #700/#655 + xang1234/portfolio AI: coerce ctor knobs first so
        # True→€1 cash / True→100% rate / True→€1 min cannot seed a new book —
        # and so load fallbacks are never bool either.
        cash0 = _coerce_portfolio_cash(initial_cash)
        rate0 = _coerce_portfolio_rate(commission_rate, REVOLUT_STANDARD_RATE)
        min0 = _coerce_portfolio_min_eur(commission_min_eur, REVOLUT_STANDARD_MIN_EUR)

        # Try to load existing portfolio state
        if self.persistence:
            loaded = self.persistence.load_portfolio()
            if loaded:
                init = _coerce_portfolio_cash(
                    loaded.get("initial_cash"), cash0
                )
                live = _coerce_portfolio_cash(loaded.get("cash"), init)
                self.initial_cash = init
                self.cash = live
                self.commission_rate = _coerce_portfolio_rate(
                    loaded.get("commission_rate", rate0), rate0
                )
                self.commission_min_eur = _coerce_portfolio_min_eur(
                    loaded.get("commission_min_eur", min0), min0
                )
                self.fee_preset = str(
                    loaded.get("fee_preset") or self.fee_preset
                )
                self.holdings = loaded["holdings"]
                self.avg_buy_price = loaded["avg_buy_price"]
                self.total_fees_paid = _coerce_portfolio_fees_paid(
                    loaded.get("total_fees_paid"), 0.0
                )
                self.transactions = self.persistence.load_trades()
                self._init_fee_allowance(loaded)
                self.enable_risk_management = enable_risk_management
                if self.enable_risk_management:
                    self.risk_manager = RiskManager()
                else:
                    self.risk_manager = None
                return

        # Initialize new portfolio
        self.initial_cash = cash0
        self.cash = cash0
        self.commission_rate = rate0
        self.commission_min_eur = min0
        self.holdings: Dict[str, float] = {}  # symbol -> quantity
        self.avg_buy_price: Dict[str, float] = {}  # symbol -> avg price
        self.transactions: List[Dict] = []
        self.total_fees_paid = 0.0
        self._init_fee_allowance(None)

        # Initialize risk management
        self.enable_risk_management = enable_risk_management
        if self.enable_risk_management:
            self.risk_manager = RiskManager()
        else:
            self.risk_manager = None

        # Save initial state
        if self.persistence:
            self._save_state()

    def _init_fee_allowance(self, loaded: Optional[Dict[str, Any]]) -> None:
        free = free_legs_for_preset(self.fee_preset)
        if isinstance(loaded, dict) and loaded.get("fee_allowance_month"):
            self._fee_allowance = FeeAllowanceLedger.from_state(
                loaded, free_legs_per_month=free
            )
        elif self.transactions:
            self._fee_allowance = FeeAllowanceLedger.reconcile_from_transactions(
                self.transactions, free_legs_per_month=free
            )
        else:
            self._fee_allowance = FeeAllowanceLedger(free)

    def commission_for(self, notional: float, timestamp: str = "") -> float:
        """One-side commission with monthly free-leg allowance."""
        return self._fee_allowance.commission_for_leg(
            notional,
            timestamp,
            rate=self.commission_rate,
            min_eur=self.commission_min_eur,
        )

    def fee_allowance_remaining(self) -> int:
        return self._fee_allowance.remaining()

    def set_fee_schedule(
        self,
        *,
        rate: float,
        min_eur: float,
        preset: str = "custom",
        free_legs_per_month: Optional[int] = None,
        persist: bool = True,
    ) -> None:
        """Update live fee schedule (Ops hot-reload). Affects future fills only."""
        # tradermonty #700/#655: refuse bool — float(True) invents 100% / €1.
        if not _finite_signed(rate) or not _finite_signed(min_eur):
            return
        self.commission_rate = float(rate)  # type: ignore[arg-type]
        self.commission_min_eur = max(0.0, float(min_eur))  # type: ignore[arg-type]
        self.fee_preset = str(preset or "custom")
        if free_legs_per_month is not None:
            # tradermonty #700/#655: refuse bool — int(True)→1 invents a free leg.
            n = coerce_nonneg_int(free_legs_per_month)
            self._fee_allowance.free_legs_per_month = 0 if n is None else n
        elif preset != "custom":
            self._fee_allowance.free_legs_per_month = free_legs_for_preset(preset)
        if persist and self.persistence:
            self._save_state()

    def apply_fee_preset(self, preset: str, *, persist: bool = True) -> None:
        rate, min_eur = rates_for_preset(preset)
        self.set_fee_schedule(
            rate=rate,
            min_eur=min_eur,
            preset=preset,
            free_legs_per_month=free_legs_for_preset(preset),
            persist=persist,
        )
    def _lot_money(self, symbol: str, quantity: Any, mark: Any) -> float:
        """Usable mark×qty, else cost basis, else 0 (never invent True→€1 MTM)."""
        mv = marked_lot_value(quantity, mark)
        if mv is not None:
            return mv
        cost = marked_lot_value(quantity, self.avg_buy_price.get(symbol))
        return 0.0 if cost is None else cost

    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio value including cash and holdings."""
        holdings_value = 0.0
        prices = current_prices or {}
        for symbol, quantity in self.holdings.items():
            holdings_value += self._lot_money(symbol, quantity, prices.get(symbol))
        return self.cash + holdings_value

    def get_total_value(self, current_prices: Dict[str, float] = None) -> float:
        """
        Calculate total portfolio value.
        If current_prices not provided, uses average buy prices (conservative estimate).
        """
        if current_prices:
            return self.get_portfolio_value(current_prices)

        # Use avg buy prices as fallback (refuse bool/gap cost invent)
        holdings_value = 0.0
        for symbol, quantity in self.holdings.items():
            holdings_value += self._lot_money(symbol, quantity, None)
        return self.cash + holdings_value

    def get_holdings_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate value of holdings only."""
        holdings_value = 0.0
        prices = current_prices or {}
        for symbol, quantity in self.holdings.items():
            holdings_value += self._lot_money(symbol, quantity, prices.get(symbol))
        return holdings_value

    def can_buy(
        self,
        symbol: str,
        price: float,
        quantity: float,
        timestamp: str = "",
    ) -> bool:
        """Check if we have enough cash to buy (long-only; qty/price must be usable)."""
        if not long_only_quantity_ok(quantity) or not fill_price_ok(price):
            return False
        cost = float(price) * float(quantity)
        commission = self.commission_for(cost, timestamp)
        total_cost = cost + commission
        return self.cash >= total_cost

    @staticmethod
    def _refuse_short(quantity: float) -> Optional[Dict[str, Any]]:
        if long_only_quantity_ok(quantity):
            return None
        return {
            "success": False,
            "reason": UNSUPPORTED_SHORT_REASON,
            "quantity_requested": quantity,
        }

    @staticmethod
    def _refuse_bad_fill(price: Any) -> Optional[Dict[str, Any]]:
        if fill_price_ok(price):
            return None
        return {
            "success": False,
            "reason": INVALID_FILL_PRICE_REASON,
            "price_requested": price,
        }

    def buy(
        self,
        symbol: str,
        price: float,
        quantity: float,
        timestamp: str,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """
        Execute buy order.

        Returns transaction details or None if insufficient funds.
        """
        refused = self._refuse_short(quantity)
        if refused:
            return refused
        bad_px = self._refuse_bad_fill(price)
        if bad_px:
            return bad_px

        price = float(price)
        quantity = float(quantity)
        cost = price * quantity
        commission = self.commission_for(cost, timestamp)
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
        if context:
            for key in ("strategy", "note", "score", "confidence", "source"):
                val = context.get(key)
                if val is not None and val != "":
                    transaction[key] = val
        self.transactions.append(transaction)

        # Persist trade and state
        if self.persistence:
            self.persistence.append_trade(transaction)
            self._save_state()

        return {"success": True, "transaction": transaction}

    def can_sell(self, symbol: str, quantity: float) -> bool:
        """Check if we have enough shares to sell (long-only; no short opens)."""
        if not long_only_quantity_ok(quantity):
            return False
        return symbol in self.holdings and self.holdings[symbol] >= quantity

    def sell(
        self,
        symbol: str,
        price: float,
        quantity: float,
        timestamp: str,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """
        Execute sell order.

        Returns transaction details or None if insufficient shares.
        """
        refused = self._refuse_short(quantity)
        if refused:
            return refused
        bad_px = self._refuse_bad_fill(price)
        if bad_px:
            return bad_px
        if not self.can_sell(symbol, quantity):
            return {
                "success": False,
                "reason": "Insufficient shares",
                "holdings": self.holdings.get(symbol, 0),
                "quantity_requested": quantity,
            }

        price = float(price)
        quantity = float(quantity)
        proceeds = price * quantity
        commission = self.commission_for(proceeds, timestamp)
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
        if context:
            for key in ("exit_reason", "note", "source"):
                val = context.get(key)
                if val is not None and val != "":
                    transaction[key] = val
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
                "commission_min_eur": self.commission_min_eur,
                "fee_preset": self.fee_preset,
                "holdings": self.holdings,
                "avg_buy_price": self.avg_buy_price,
                "total_fees_paid": self.total_fees_paid,
                **self._fee_allowance.to_state(),
            })

    def get_position(self, symbol: str, current_price: float) -> Optional[Dict]:
        """Get details about a specific position."""
        if symbol not in self.holdings:
            return None

        quantity = self.holdings[symbol]
        avg_buy = self.avg_buy_price.get(symbol)
        # Refuse bool/gap marks — float(True)→€1 invents fake MTM / ±1% P&L.
        if (
            not long_only_quantity_ok(quantity)
            or not fill_price_ok(avg_buy)
            or not fill_price_ok(current_price)
        ):
            return None
        qty = float(quantity)
        mark = float(current_price)
        cost = float(avg_buy)
        current_value = qty * mark
        cost_basis = qty * cost
        profit_loss = current_value - cost_basis
        profit_loss_pct = (profit_loss / cost_basis) * 100

        return {
            "symbol": symbol,
            "quantity": qty,
            "avg_buy_price": cost,
            "current_price": mark,
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
