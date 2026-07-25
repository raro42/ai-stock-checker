#!/usr/bin/env python3

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class DataPersistence:
    """Handle persistent storage of portfolio, trades, and findings."""

    def __init__(self, data_dir: str = "/data"):
        """
        Initialize persistence layer.

        Args:
            data_dir: Directory to store persistent data (default: /data for container volume)
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.portfolio_file = self.data_dir / "portfolio.json"
        self.trades_file = self.data_dir / "trades.jsonl"
        self.findings_file = self.data_dir / "findings.jsonl"
        self.state_file = self.data_dir / "state.json"
        self.entry_times_file = self.data_dir / "entry_times.json"
        self.scanned_symbols_file = self.data_dir / "scanned_symbols.json"

    def save_portfolio(self, portfolio_data: Dict):
        """Save current portfolio state."""
        portfolio_data["last_updated"] = datetime.now().isoformat()
        with open(self.portfolio_file, "w") as f:
            json.dump(portfolio_data, f, indent=2)

    def load_portfolio(self) -> Optional[Dict]:
        """Load portfolio state from disk."""
        if self.portfolio_file.exists():
            with open(self.portfolio_file) as f:
                return json.load(f)
        return None

    def append_trade(self, trade: Dict):
        """Append a trade to the trades log (JSONL format for streaming)."""
        trade["timestamp"] = trade.get("timestamp", datetime.now().isoformat())
        with open(self.trades_file, "a") as f:
            f.write(json.dumps(trade) + "\n")

    def load_trades(self, limit: Optional[int] = None) -> List[Dict]:
        """Load trades from disk."""
        if not self.trades_file.exists():
            return []

        trades = []
        with open(self.trades_file) as f:
            for line in f:
                trades.append(json.loads(line.strip()))

        if limit:
            return trades[-limit:]
        return trades

    def append_finding(self, finding: Dict):
        """
        Append a market finding/signal to the findings log.

        Finding format:
        {
            "timestamp": "2025-11-29T17:30:00",
            "symbol": "BTC-USD",
            "action": "BUY",
            "confidence": "HIGH",
            "score": 35,
            "price": 90924.55,
            "reasons": ["Strong momentum", "Near 52-week low"],
            "executed": true/false,
            "ai_validated": true/false
        }
        """
        finding["timestamp"] = finding.get("timestamp", datetime.now().isoformat())
        with open(self.findings_file, "a") as f:
            f.write(json.dumps(finding) + "\n")

    def load_findings(
        self,
        limit: Optional[int] = None,
        symbol: Optional[str] = None,
        action: Optional[str] = None
    ) -> List[Dict]:
        """Load findings from disk with optional filters."""
        if not self.findings_file.exists():
            return []

        findings = []
        with open(self.findings_file) as f:
            for line in f:
                finding = json.loads(line.strip())

                # Apply filters
                if symbol and finding.get("symbol") != symbol:
                    continue
                if action and finding.get("action") != action:
                    continue

                findings.append(finding)

        if limit:
            return findings[-limit:]
        return findings

    def save_state(self, state: Dict):
        """Save general application state."""
        state["last_updated"] = datetime.now().isoformat()
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def load_state(self) -> Optional[Dict]:
        """Load application state."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return None

    def save_entry_times(self, entry_times: Dict[str, float]):
        """Save position entry times."""
        with open(self.entry_times_file, "w") as f:
            json.dump(entry_times, f, indent=2)

    def load_entry_times(self) -> Dict[str, float]:
        """Load position entry times from disk."""
        if self.entry_times_file.exists():
            with open(self.entry_times_file) as f:
                return json.load(f)
        return {}

    def track_scanned_symbol(self, symbol: str, source: str):
        """
        Track a scanned symbol with its source.
        
        Args:
            symbol: Symbol like 'BTC-USD' or 'AAPL'
            source: 'crypto' or 'paper'
        """
        # Load existing symbols
        scanned_symbols = self.load_scanned_symbols()
        
        # Update or add symbol
        scanned_symbols[symbol] = {
            "source": source,
            "last_scanned": datetime.now().isoformat(),
            "first_scanned": scanned_symbols.get(symbol, {}).get("first_scanned", datetime.now().isoformat())
        }
        
        # Save back to disk
        with open(self.scanned_symbols_file, "w") as f:
            json.dump(scanned_symbols, f, indent=2)

    def track_scanned_symbols_batch(self, symbols: List[str], source: str):
        """
        Track multiple symbols at once (more efficient for batch scans).
        
        Args:
            symbols: List of symbols
            source: 'crypto' or 'paper'
        """
        scanned_symbols = self.load_scanned_symbols()
        now = datetime.now().isoformat()
        
        for symbol in symbols:
            if symbol not in scanned_symbols:
                scanned_symbols[symbol] = {
                    "source": source,
                    "last_scanned": now,
                    "first_scanned": now
                }
            else:
                scanned_symbols[symbol]["last_scanned"] = now
                # Keep existing first_scanned timestamp
        
        # Save back to disk
        with open(self.scanned_symbols_file, "w") as f:
            json.dump(scanned_symbols, f, indent=2)

    def load_scanned_symbols(self) -> Dict[str, Dict]:
        """
        Load all scanned symbols with their source information.
        
        Returns:
            Dict mapping symbol -> {
                "source": "crypto" | "paper",
                "last_scanned": "2025-11-30T15:00:00",
                "first_scanned": "2025-11-30T10:00:00"
            }
        """
        if self.scanned_symbols_file.exists():
            with open(self.scanned_symbols_file) as f:
                return json.load(f)
        return {}

    def get_symbol_source(self, symbol: str) -> Optional[str]:
        """
        Get the source (crypto/paper) for a symbol.
        
        Returns:
            'crypto', 'paper', or None if not found
        """
        scanned_symbols = self.load_scanned_symbols()
        return scanned_symbols.get(symbol, {}).get("source")

    def get_summary(self) -> Dict:
        """Get a summary of all stored data."""
        trades = self.load_trades()
        findings = self.load_findings()
        portfolio = self.load_portfolio()
        state = self.load_state()

        return {
            "data_directory": str(self.data_dir),
            "total_trades": len(trades),
            "total_findings": len(findings),
            "portfolio_exists": portfolio is not None,
            "state_exists": state is not None,
            "files": {
                "portfolio": str(self.portfolio_file),
                "trades": str(self.trades_file),
                "findings": str(self.findings_file),
                "state": str(self.state_file),
            }
        }

    def export_csv(self, output_dir: Optional[str] = None):
        """Export data to CSV files for analysis."""
        import csv

        output_dir = Path(output_dir or self.data_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Export trades
        trades = self.load_trades()
        if trades:
            trades_csv = output_dir / "trades.csv"
            with open(trades_csv, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=trades[0].keys())
                writer.writeheader()
                writer.writerows(trades)

        # Export findings
        findings = self.load_findings()
        if findings:
            findings_csv = output_dir / "findings.csv"
            with open(findings_csv, "w", newline="") as f:
                # Flatten nested lists/dicts
                flattened = []
                for finding in findings:
                    flat = finding.copy()
                    if "reasons" in flat:
                        flat["reasons"] = "; ".join(flat["reasons"])
                    flattened.append(flat)

                writer = csv.DictWriter(f, fieldnames=flattened[0].keys())
                writer.writeheader()
                writer.writerows(flattened)

        return {
            "trades_csv": str(output_dir / "trades.csv") if trades else None,
            "findings_csv": str(output_dir / "findings.csv") if findings else None,
        }
