#!/usr/bin/env python3
"""
Backtesting framework for strategy validation.
Supports historical OHLCV bars, commissions, slippage, and performance metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from stock_checker.fees import FeeAllowanceLedger


@dataclass
class Trade:
    """Record of a single trade."""

    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    shares: float
    pnl: float
    pnl_pct: float
    reason: str  # 'stop_loss', 'take_profit', 'signal_exit', etc.


class BacktestResult:
    """Container for backtest results and metrics."""

    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = [initial_capital]
        self.timestamps: List[datetime] = []

    def add_trade(self, trade: Trade) -> None:
        """Add a completed trade."""
        self.trades.append(trade)

    def calculate_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics."""
        if not self.trades:
            final = self.equity_curve[-1] if self.equity_curve else self.initial_capital
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "total_return": final - self.initial_capital,
                "total_return_pct": ((final / self.initial_capital) - 1) * 100,
                "sharpe_ratio": 0.0,
                "max_drawdown": self._calculate_max_drawdown() * 100,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "avg_duration_hours": 0.0,
                "final_capital": final,
            }

        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl < 0]

        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0

        pnls = [float(t.pnl) for t in self.trades if t.pnl is not None and np.isfinite(float(t.pnl))]
        total_pnl = float(sum(pnls)) if pnls else 0.0
        if self.equity_curve:
            final_eq = float(self.equity_curve[-1])
            if np.isfinite(final_eq):
                total_pnl = final_eq - self.initial_capital
        total_return_pct = (total_pnl / self.initial_capital) * 100.0
        if not np.isfinite(total_return_pct):
            total_return_pct = 0.0
        if not np.isfinite(total_pnl):
            total_pnl = 0.0

        avg_win = float(np.mean([t.pnl for t in winning_trades])) if winning_trades else 0.0
        avg_loss = float(np.mean([t.pnl for t in losing_trades])) if losing_trades else 0.0
        if not np.isfinite(avg_win):
            avg_win = 0.0
        if not np.isfinite(avg_loss):
            avg_loss = 0.0

        gross_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0.0
        gross_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        trade_durations = [
            (t.exit_time - t.entry_time).total_seconds() / 3600 for t in self.trades
        ]
        avg_duration_hours = float(np.mean(trade_durations)) if trade_durations else 0.0

        return {
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate * 100,
            "total_return": total_pnl,
            "total_return_pct": total_return_pct,
            "sharpe_ratio": self._calculate_sharpe_ratio(),
            "max_drawdown": self._calculate_max_drawdown() * 100,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "avg_duration_hours": avg_duration_hours,
            "final_capital": self.initial_capital + total_pnl,
        }

    def _calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate annualized Sharpe ratio from equity curve."""
        if len(self.equity_curve) < 2:
            return 0.0

        equity = np.asarray(self.equity_curve, dtype=float)
        equity = equity[np.isfinite(equity) & (equity > 0)]
        if len(equity) < 2:
            return 0.0

        returns = np.diff(equity) / equity[:-1]
        returns = returns[np.isfinite(returns)]
        if len(returns) == 0 or float(np.std(returns)) == 0.0:
            return 0.0

        mean_return = float(np.mean(returns) * 252)
        std_return = float(np.std(returns) * np.sqrt(252))
        sharpe = (mean_return - risk_free_rate) / std_return
        return float(sharpe) if np.isfinite(sharpe) else 0.0

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown as a fraction."""
        if len(self.equity_curve) < 2:
            return 0.0

        equity = np.asarray(self.equity_curve, dtype=float)
        equity = equity[np.isfinite(equity)]
        if len(equity) < 2:
            return 0.0

        running_max = np.maximum.accumulate(equity)
        with np.errstate(divide="ignore", invalid="ignore"):
            drawdown = (equity - running_max) / running_max
        drawdown = drawdown[np.isfinite(drawdown)]
        if len(drawdown) == 0:
            return 0.0
        return float(abs(np.min(drawdown)))

    def print_summary(self) -> None:
        """Print backtest summary."""
        metrics = self.calculate_metrics()

        print(f"\n{'='*70}")
        print("📊 BACKTEST RESULTS")
        print(f"{'='*70}")
        print(f"Initial Capital:      ${self.initial_capital:,.2f}")
        print(f"Final Capital:        ${metrics['final_capital']:,.2f}")
        print(
            f"Total Return:         ${metrics['total_return']:,.2f} "
            f"({metrics['total_return_pct']:+.2f}%)"
        )
        print(f"\nTrades:               {metrics['total_trades']}")
        print(f"Winners:              {metrics['winning_trades']} ({metrics['win_rate']:.1f}%)")
        print(f"Losers:               {metrics['losing_trades']}")
        print(f"Avg Win:              ${metrics['avg_win']:,.2f}")
        print(f"Avg Loss:             ${metrics['avg_loss']:,.2f}")
        print(f"Profit Factor:        {metrics['profit_factor']:.2f}")
        print("\nRisk Metrics:")
        print(f"Sharpe Ratio:         {metrics['sharpe_ratio']:.2f}")
        print(f"Max Drawdown:         {metrics['max_drawdown']:.2f}%")
        print(f"Avg Trade Duration:   {metrics['avg_duration_hours']:.1f} hours")
        print(f"{'='*70}\n")


def momentum_cross_strategy(
    bars_by_symbol: Dict[str, List[Dict]],
    index: int,
    portfolio: Dict,
    lookback: int = 20,
) -> Dict[str, str]:
    """
    Simple long-only momentum: buy if close > SMA(lookback), sell if below.

    strategy_func signature for Backtester.backtest.
    """
    signals: Dict[str, str] = {}
    for symbol, bars in bars_by_symbol.items():
        if index < lookback or index >= len(bars):
            continue
        window = [float(b["close"]) for b in bars[index - lookback : index]]
        sma = sum(window) / lookback
        close = float(bars[index]["close"])
        in_pos = symbol in portfolio.get("positions", {})
        if close > sma and not in_pos:
            signals[symbol] = "BUY"
        elif close < sma and in_pos:
            signals[symbol] = "SELL"
    return signals


class Backtester:
    """Backtest trading strategies on historical OHLCV data."""

    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission_rate: float = 0.001,
        slippage_pct: float = 0.001,
        position_fraction: float = 0.2,
        commission_min_eur: float = 0.0,
        max_positions: int = 0,
        min_hold_bars: int = 0,
        free_legs_per_month: int = 0,
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.commission_min_eur = float(commission_min_eur or 0.0)
        self.free_legs_per_month = max(0, int(free_legs_per_month or 0))
        self.slippage_pct = slippage_pct
        self.position_fraction = position_fraction
        # 0 = unlimited
        self.max_positions = int(max_positions or 0)
        # Skip signal exits until held at least this many bars (daily ≈ hours/24)
        self.min_hold_bars = max(0, int(min_hold_bars or 0))

    def _fee(
        self,
        notional: float,
        ts: datetime,
        ledger: FeeAllowanceLedger,
    ) -> float:
        ts_str = ts.strftime("%Y-%m-%d") if isinstance(ts, datetime) else str(ts)
        return ledger.commission_for_leg(
            notional,
            ts_str,
            rate=self.commission_rate,
            min_eur=self.commission_min_eur,
        )

    def backtest(
        self,
        historical_data: Dict[str, List[Dict]],
        strategy_func: Callable,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> BacktestResult:
        """
        Run a long-only backtest on aligned OHLCV bars.

        Each bar dict must include: close, and optionally open/high/low/volume/date.
        `date` may be datetime or ISO string.
        """
        result = BacktestResult(self.initial_capital)
        if not historical_data:
            return result

        fee_ledger = FeeAllowanceLedger(self.free_legs_per_month)

        # Align on common length (shortest series)
        symbols = list(historical_data.keys())
        min_len = min(len(historical_data[s]) for s in symbols)
        if min_len < 2:
            return result

        portfolio = {
            "cash": float(self.initial_capital),
            "positions": {},  # symbol -> {shares, entry_price, entry_time, entry_i}
        }

        def parse_ts(bar: Dict, fallback_i: int) -> datetime:
            raw = bar.get("date") or bar.get("timestamp")
            if isinstance(raw, datetime):
                return raw
            if isinstance(raw, str):
                try:
                    return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
                except ValueError:
                    pass
            return datetime(2000, 1, 1) + __import__("datetime").timedelta(days=fallback_i)

        for i in range(min_len):
            # Date filter using first symbol's bar
            sample = historical_data[symbols[0]][i]
            ts = parse_ts(sample, i)
            if start_date and ts < start_date:
                continue
            if end_date and ts > end_date:
                break

            prices = {}
            for s in symbols:
                try:
                    px = float(historical_data[s][i]["close"])
                except (TypeError, ValueError):
                    continue
                if px == px and px > 0:
                    prices[s] = px
            if not prices:
                continue
            signals = strategy_func(historical_data, i, portfolio) or {}

            # Process sells first
            for symbol, action in list(signals.items()):
                if action != "SELL" or symbol not in portfolio["positions"]:
                    continue
                pos = portfolio["positions"][symbol]
                entry_i = int(pos.get("entry_i", i))
                if self.min_hold_bars > 0 and (i - entry_i) < self.min_hold_bars:
                    continue
                portfolio["positions"].pop(symbol)
                exit_price = prices[symbol] * (1 - self.slippage_pct)
                proceeds = pos["shares"] * exit_price
                commission = self._fee(proceeds, ts, fee_ledger)
                net = proceeds - commission
                portfolio["cash"] += net
                pnl = (exit_price - pos["entry_price"]) * pos["shares"] - commission
                # Entry commission already paid; approximate total pnl vs entry notional
                entry_notional = pos["shares"] * pos["entry_price"]
                result.add_trade(
                    Trade(
                        symbol=symbol,
                        entry_time=pos["entry_time"],
                        exit_time=ts,
                        entry_price=pos["entry_price"],
                        exit_price=exit_price,
                        shares=pos["shares"],
                        pnl=pnl,
                        pnl_pct=(pnl / entry_notional) * 100 if entry_notional else 0.0,
                        reason="signal_exit",
                    )
                )

            # Process buys
            for symbol, action in list(signals.items()):
                if action != "BUY" or symbol in portfolio["positions"]:
                    continue
                if self.max_positions > 0 and len(portfolio["positions"]) >= self.max_positions:
                    break
                equity = portfolio["cash"] + sum(
                    p["shares"] * prices.get(s, p["entry_price"])
                    for s, p in portfolio["positions"].items()
                )
                budget = equity * self.position_fraction
                entry_price = prices[symbol] * (1 + self.slippage_pct)
                if entry_price <= 0 or budget <= 0:
                    continue
                shares = budget / entry_price
                cost = shares * entry_price
                commission = self._fee(cost, ts, fee_ledger)
                total = cost + commission
                if total > portfolio["cash"]:
                    continue
                portfolio["cash"] -= total
                portfolio["positions"][symbol] = {
                    "shares": shares,
                    "entry_price": entry_price,
                    "entry_time": ts,
                    "entry_i": i,
                }

            # Mark-to-market equity
            mtm = portfolio["cash"] + sum(
                p["shares"] * prices.get(s, p["entry_price"])
                for s, p in portfolio["positions"].items()
            )
            result.equity_curve.append(mtm)
            result.timestamps.append(ts)

        # Force-close remaining positions at last prices
        if portfolio["positions"]:
            last_i = min_len - 1
            last_ts = parse_ts(historical_data[symbols[0]][last_i], last_i)
            for symbol, pos in list(portfolio["positions"].items()):
                try:
                    raw_close = float(historical_data[symbol][last_i]["close"])
                except (TypeError, ValueError):
                    raw_close = float("nan")
                if not (raw_close == raw_close and raw_close > 0):
                    # Walk back to last finite close
                    raw_close = float(pos["entry_price"])
                    for j in range(last_i, -1, -1):
                        try:
                            c = float(historical_data[symbol][j]["close"])
                        except (TypeError, ValueError):
                            continue
                        if c == c and c > 0:
                            raw_close = c
                            break
                exit_price = raw_close * (1 - self.slippage_pct)
                proceeds = pos["shares"] * exit_price
                commission = self._fee(proceeds, ts, fee_ledger)
                portfolio["cash"] += proceeds - commission
                pnl = (exit_price - pos["entry_price"]) * pos["shares"] - commission
                entry_notional = pos["shares"] * pos["entry_price"]
                result.add_trade(
                    Trade(
                        symbol=symbol,
                        entry_time=pos["entry_time"],
                        exit_time=last_ts,
                        entry_price=pos["entry_price"],
                        exit_price=exit_price,
                        shares=pos["shares"],
                        pnl=pnl,
                        pnl_pct=(pnl / entry_notional) * 100 if entry_notional else 0.0,
                        reason="end_of_data",
                    )
                )
            portfolio["positions"].clear()
            result.equity_curve.append(portfolio["cash"])
            result.timestamps.append(last_ts)

        return result

    def walk_forward_optimization(
        self,
        historical_data: Dict[str, List[Dict]],
        strategy_func: Callable,
        train_period_days: int = 180,
        test_period_days: int = 30,
        param_grid: Optional[Dict] = None,
    ) -> Dict:
        """Placeholder for walk-forward sweeps (use vectorbt for heavy grids)."""
        return {
            "status": "not_implemented",
            "message": (
                "Use Backtester.backtest for single runs; "
                "prefer vectorbt for large parameter grids."
            ),
            "train_period_days": train_period_days,
            "test_period_days": test_period_days,
            "param_grid": param_grid or {},
        }

    def monte_carlo_simulation(
        self,
        trades: List[Trade],
        num_simulations: int = 1000,
        num_trades: int = 100,
    ) -> Dict:
        """Run Monte Carlo simulation on trade return samples."""
        if not trades:
            return {
                "mean_return": 0.0,
                "median_return": 0.0,
                "std_return": 0.0,
                "percentile_5": 0.0,
                "percentile_95": 0.0,
                "probability_profit": 0.0,
            }

        trade_returns = [t.pnl_pct for t in trades]
        simulation_results = []
        for _ in range(num_simulations):
            sampled = np.random.choice(trade_returns, size=min(num_trades, len(trade_returns)), replace=True)
            simulation_results.append(float(np.sum(sampled)))

        arr = np.array(simulation_results)
        return {
            "mean_return": float(np.mean(arr)),
            "median_return": float(np.median(arr)),
            "std_return": float(np.std(arr)),
            "percentile_5": float(np.percentile(arr, 5)),
            "percentile_95": float(np.percentile(arr, 95)),
            "probability_profit": float(np.sum(arr > 0) / num_simulations),
            "worst_case": float(np.min(arr)),
            "best_case": float(np.max(arr)),
        }


class StrategyValidator:
    """Validate strategies against minimum risk/return criteria."""

    def __init__(self):
        self.backtester = Backtester()

    def validate_result(
        self,
        result: BacktestResult,
        min_sharpe: float = 0.5,
        max_drawdown: float = 0.25,
        min_win_rate: float = 0.40,
        min_profit_factor: float = 1.0,
    ) -> Tuple[bool, Dict]:
        """Validate a completed BacktestResult against thresholds."""
        metrics = result.calculate_metrics()
        checks = {
            "sharpe_ok": metrics["sharpe_ratio"] >= min_sharpe,
            "drawdown_ok": (metrics["max_drawdown"] / 100) <= max_drawdown,
            "win_rate_ok": (metrics["win_rate"] / 100) >= min_win_rate,
            "profit_factor_ok": metrics["profit_factor"] >= min_profit_factor,
            "has_trades": metrics["total_trades"] > 0,
        }
        is_valid = all(checks.values())
        return is_valid, {"metrics": metrics, "checks": checks}

    def validate_strategy(
        self,
        strategy_func: Callable,
        min_sharpe: float = 1.0,
        max_drawdown: float = 0.20,
        min_win_rate: float = 0.40,
        min_profit_factor: float = 1.5,
    ) -> Tuple[bool, Dict]:
        """Legacy hook — prefer validate_result with real historical_data."""
        return False, {
            "status": "needs_data",
            "message": "Pass historical OHLCV into Backtester.backtest, then validate_result.",
            "criteria": {
                "min_sharpe": min_sharpe,
                "max_drawdown": max_drawdown,
                "min_win_rate": min_win_rate,
                "min_profit_factor": min_profit_factor,
            },
        }
