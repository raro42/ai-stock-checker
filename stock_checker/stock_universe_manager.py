#!/usr/bin/env python3
"""
Dynamic stock universe manager.
Discovers, persists, and manages the full stock universe on disk.
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict
from pathlib import Path


class StockUniverseManager:
    """Manage dynamic stock universe with disk persistence."""

    def __init__(self, data_dir: str = "/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        self.universe_file = self.data_dir / "stock_universe.json"
        self.scan_history_file = self.data_dir / "stock_scan_history.json"

        # Load or initialize universe
        self.universe = self._load_universe()
        self.scan_history = self._load_scan_history()

        # Seed with initial stocks if universe is empty
        if not self.universe.get("stocks"):
            self._seed_initial_universe()

    def _load_universe(self) -> Dict:
        """Load stock universe from disk."""
        if self.universe_file.exists():
            try:
                with open(self.universe_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Error loading universe: {e}")
                return self._create_empty_universe()
        return self._create_empty_universe()

    def _create_empty_universe(self) -> Dict:
        """Create empty universe structure."""
        return {
            "last_updated": datetime.now().isoformat(),
            "total_stocks": 0,
            "stocks": {},  # symbol -> {"sector": str, "exchange": str, "added": timestamp}
            "sectors": {},  # sector -> [symbols]
            "exchanges": {}  # exchange -> [symbols]
        }

    def _save_universe(self):
        """Save universe to disk."""
        self.universe["last_updated"] = datetime.now().isoformat()
        self.universe["total_stocks"] = len(self.universe["stocks"])

        with open(self.universe_file, 'w') as f:
            json.dump(self.universe, f, indent=2)

    def _load_scan_history(self) -> Dict:
        """Load scan history from disk."""
        if self.scan_history_file.exists():
            try:
                with open(self.scan_history_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Error loading scan history: {e}")
                return {"scanned": {}, "last_full_cycle": None}
        return {"scanned": {}, "last_full_cycle": None}

    def _save_scan_history(self):
        """Save scan history to disk."""
        with open(self.scan_history_file, 'w') as f:
            json.dump(self.scan_history, f, indent=2)

    def _seed_initial_universe(self):
        """Seed with initial comprehensive stock list."""
        print("🌱 Seeding initial stock universe...")

        initial_stocks = {
            # US Mega Cap Tech
            "AAPL": {"sector": "technology", "exchange": "NASDAQ"},
            "MSFT": {"sector": "technology", "exchange": "NASDAQ"},
            "GOOGL": {"sector": "technology", "exchange": "NASDAQ"},
            "AMZN": {"sector": "technology", "exchange": "NASDAQ"},
            "NVDA": {"sector": "technology", "exchange": "NASDAQ"},
            "META": {"sector": "technology", "exchange": "NASDAQ"},
            "TSLA": {"sector": "automotive", "exchange": "NASDAQ"},
            "ORCL": {"sector": "technology", "exchange": "NYSE"},
            "ADBE": {"sector": "technology", "exchange": "NASDAQ"},
            "CRM": {"sector": "technology", "exchange": "NYSE"},
            "NFLX": {"sector": "entertainment", "exchange": "NASDAQ"},
            "DIS": {"sector": "entertainment", "exchange": "NYSE"},

            # Semiconductors
            "AMD": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "INTC": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "QCOM": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "AVGO": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "TSM": {"sector": "semiconductor", "exchange": "NYSE"},
            "ASML": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "MU": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "AMAT": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "LRCX": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "KLAC": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "MRVL": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "ON": {"sector": "semiconductor", "exchange": "NASDAQ"},

            # AI & Cloud
            "PLTR": {"sector": "ai", "exchange": "NYSE"},
            "AI": {"sector": "ai", "exchange": "NYSE"},
            "SNOW": {"sector": "cloud", "exchange": "NYSE"},
            "NET": {"sector": "cloud", "exchange": "NYSE"},
            "DDOG": {"sector": "cloud", "exchange": "NASDAQ"},
            "CRWD": {"sector": "cybersecurity", "exchange": "NASDAQ"},
            "ZS": {"sector": "cybersecurity", "exchange": "NASDAQ"},
            "S": {"sector": "cloud", "exchange": "NYSE"},
            "PANW": {"sector": "cybersecurity", "exchange": "NASDAQ"},
            "FTNT": {"sector": "cybersecurity", "exchange": "NASDAQ"},

            # Finance
            "JPM": {"sector": "banking", "exchange": "NYSE"},
            "BAC": {"sector": "banking", "exchange": "NYSE"},
            "GS": {"sector": "banking", "exchange": "NYSE"},
            "MS": {"sector": "banking", "exchange": "NYSE"},
            "V": {"sector": "payments", "exchange": "NYSE"},
            "MA": {"sector": "payments", "exchange": "NYSE"},
            "AXP": {"sector": "payments", "exchange": "NYSE"},
            "C": {"sector": "banking", "exchange": "NYSE"},
            "WFC": {"sector": "banking", "exchange": "NYSE"},
            "BLK": {"sector": "asset_management", "exchange": "NYSE"},
            "SCHW": {"sector": "brokerage", "exchange": "NYSE"},
            "USB": {"sector": "banking", "exchange": "NYSE"},

            # Energy
            "XOM": {"sector": "energy", "exchange": "NYSE"},
            "CVX": {"sector": "energy", "exchange": "NYSE"},
            "COP": {"sector": "energy", "exchange": "NYSE"},
            "SLB": {"sector": "energy", "exchange": "NYSE"},
            "OXY": {"sector": "energy", "exchange": "NYSE"},
            "EOG": {"sector": "energy", "exchange": "NYSE"},
            "MPC": {"sector": "energy", "exchange": "NYSE"},
            "PSX": {"sector": "energy", "exchange": "NYSE"},
            "VLO": {"sector": "energy", "exchange": "NYSE"},
            "HAL": {"sector": "energy", "exchange": "NYSE"},
            "BKR": {"sector": "energy", "exchange": "NASDAQ"},

            # Consumer
            "WMT": {"sector": "retail", "exchange": "NYSE"},
            "TGT": {"sector": "retail", "exchange": "NYSE"},
            "COST": {"sector": "retail", "exchange": "NASDAQ"},
            "NKE": {"sector": "apparel", "exchange": "NYSE"},
            "LULU": {"sector": "apparel", "exchange": "NASDAQ"},
            "HD": {"sector": "retail", "exchange": "NYSE"},
            "LOW": {"sector": "retail", "exchange": "NYSE"},
            "MCD": {"sector": "restaurant", "exchange": "NYSE"},
            "SBUX": {"sector": "restaurant", "exchange": "NASDAQ"},
            "CMG": {"sector": "restaurant", "exchange": "NYSE"},
            "BKNG": {"sector": "travel", "exchange": "NASDAQ"},
            "MAR": {"sector": "hospitality", "exchange": "NASDAQ"},

            # Healthcare
            "UNH": {"sector": "healthcare", "exchange": "NYSE"},
            "JNJ": {"sector": "healthcare", "exchange": "NYSE"},
            "LLY": {"sector": "pharma", "exchange": "NYSE"},
            "ABBV": {"sector": "pharma", "exchange": "NYSE"},
            "PFE": {"sector": "pharma", "exchange": "NYSE"},
            "TMO": {"sector": "healthcare", "exchange": "NYSE"},
            "ABT": {"sector": "healthcare", "exchange": "NYSE"},
            "DHR": {"sector": "healthcare", "exchange": "NYSE"},
            "BMY": {"sector": "pharma", "exchange": "NYSE"},
            "AMGN": {"sector": "biotech", "exchange": "NASDAQ"},
            "GILD": {"sector": "biotech", "exchange": "NASDAQ"},
            "VRTX": {"sector": "biotech", "exchange": "NASDAQ"},

            # Crypto Stocks
            "COIN": {"sector": "crypto", "exchange": "NASDAQ"},
            "MSTR": {"sector": "crypto", "exchange": "NASDAQ"},
            "MARA": {"sector": "crypto", "exchange": "NASDAQ"},
            "RIOT": {"sector": "crypto", "exchange": "NASDAQ"},
            "HUT": {"sector": "crypto", "exchange": "NASDAQ"},
            "CLSK": {"sector": "crypto", "exchange": "NASDAQ"},
            "BITF": {"sector": "crypto", "exchange": "NASDAQ"},
            "CIFR": {"sector": "crypto", "exchange": "NASDAQ"},

            # European Stocks
            "ADS.DE": {"sector": "apparel", "exchange": "XETRA"},
            "SAP": {"sector": "technology", "exchange": "NYSE"},
            "SIE.DE": {"sector": "industrial", "exchange": "XETRA"},
            "VOW3.DE": {"sector": "automotive", "exchange": "XETRA"},
            "AIR.PA": {"sector": "aerospace", "exchange": "EURONEXT"},
            "OR.PA": {"sector": "luxury", "exchange": "EURONEXT"},
            "MC.PA": {"sector": "luxury", "exchange": "EURONEXT"},
            "SHEL": {"sector": "energy", "exchange": "NYSE"},
            "BP": {"sector": "energy", "exchange": "NYSE"},

            # Industrial
            "BA": {"sector": "aerospace", "exchange": "NYSE"},
            "CAT": {"sector": "machinery", "exchange": "NYSE"},
            "DE": {"sector": "agriculture", "exchange": "NYSE"},
            "GE": {"sector": "industrial", "exchange": "NYSE"},
            "HON": {"sector": "industrial", "exchange": "NASDAQ"},
            "LMT": {"sector": "defense", "exchange": "NYSE"},
            "RTX": {"sector": "defense", "exchange": "NYSE"},
            "UPS": {"sector": "logistics", "exchange": "NYSE"},
            "FDX": {"sector": "logistics", "exchange": "NYSE"},
            "MMM": {"sector": "industrial", "exchange": "NYSE"},
            "EMR": {"sector": "industrial", "exchange": "NYSE"},
            "ETN": {"sector": "industrial", "exchange": "NYSE"},

            # Large-cap refresh (2026-08) — liquid names missing from older seed
            "IBM": {"sector": "technology", "exchange": "NYSE"},
            "CSCO": {"sector": "technology", "exchange": "NASDAQ"},
            "ACN": {"sector": "technology", "exchange": "NYSE"},
            "NOW": {"sector": "cloud", "exchange": "NYSE"},
            "INTU": {"sector": "software", "exchange": "NASDAQ"},
            "TXN": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "ADI": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "ISRG": {"sector": "healthcare", "exchange": "NASDAQ"},
            "SYK": {"sector": "healthcare", "exchange": "NYSE"},
            "MDT": {"sector": "healthcare", "exchange": "NYSE"},
            "PEP": {"sector": "consumer", "exchange": "NASDAQ"},
            "KO": {"sector": "consumer", "exchange": "NYSE"},
            "PG": {"sector": "consumer", "exchange": "NYSE"},
            "PM": {"sector": "consumer", "exchange": "NYSE"},
            "TMUS": {"sector": "telecom", "exchange": "NASDAQ"},
            "VZ": {"sector": "telecom", "exchange": "NYSE"},
            "T": {"sector": "telecom", "exchange": "NYSE"},
            "UBER": {"sector": "travel", "exchange": "NYSE"},
            "ABNB": {"sector": "travel", "exchange": "NASDAQ"},
            "SHOP": {"sector": "retail", "exchange": "NYSE"},
            "MELI": {"sector": "retail", "exchange": "NASDAQ"},
            "APP": {"sector": "software", "exchange": "NASDAQ"},
            "ARM": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "SMCI": {"sector": "technology", "exchange": "NASDAQ"},
        }

        for symbol, info in initial_stocks.items():
            self.add_stock(symbol, info["sector"], info["exchange"])

        self._save_universe()
        print(f"✅ Seeded {len(initial_stocks)} stocks")

    def ensure_curated_seed(self) -> int:
        """
        Merge curated seed into an existing universe (add missing only).

        Safe for live data/: does not delete Yahoo-discovered names.
        Returns count of newly added symbols.
        """
        before = len(self.universe.get("stocks") or {})
        removed = False
        for dead in ("PXD",):
            if dead in self.universe.get("stocks", {}):
                del self.universe["stocks"][dead]
                removed = True
                for idx in (self.universe.get("sectors"), self.universe.get("exchanges")):
                    if not isinstance(idx, dict):
                        continue
                    for key, syms in list(idx.items()):
                        if isinstance(syms, list) and dead in syms:
                            idx[key] = [s for s in syms if s != dead]

        # Large-cap refresh + liquid US names (same block as seed).
        extras = {
            "IBM": {"sector": "technology", "exchange": "NYSE"},
            "CSCO": {"sector": "technology", "exchange": "NASDAQ"},
            "ACN": {"sector": "technology", "exchange": "NYSE"},
            "NOW": {"sector": "cloud", "exchange": "NYSE"},
            "INTU": {"sector": "software", "exchange": "NASDAQ"},
            "TXN": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "ADI": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "ISRG": {"sector": "healthcare", "exchange": "NASDAQ"},
            "SYK": {"sector": "healthcare", "exchange": "NYSE"},
            "MDT": {"sector": "healthcare", "exchange": "NYSE"},
            "PEP": {"sector": "consumer", "exchange": "NASDAQ"},
            "KO": {"sector": "consumer", "exchange": "NYSE"},
            "PG": {"sector": "consumer", "exchange": "NYSE"},
            "PM": {"sector": "consumer", "exchange": "NYSE"},
            "TMUS": {"sector": "telecom", "exchange": "NASDAQ"},
            "VZ": {"sector": "telecom", "exchange": "NYSE"},
            "T": {"sector": "telecom", "exchange": "NYSE"},
            "UBER": {"sector": "travel", "exchange": "NYSE"},
            "ABNB": {"sector": "travel", "exchange": "NASDAQ"},
            "SHOP": {"sector": "retail", "exchange": "NYSE"},
            "MELI": {"sector": "retail", "exchange": "NASDAQ"},
            "APP": {"sector": "software", "exchange": "NASDAQ"},
            "ARM": {"sector": "semiconductor", "exchange": "NASDAQ"},
            "SMCI": {"sector": "technology", "exchange": "NASDAQ"},
        }
        added = 0
        for symbol, info in extras.items():
            if self.add_stock(symbol, info["sector"], info["exchange"]):
                added += 1
        if added or removed:
            self._save_universe()
        after = len(self.universe.get("stocks") or {})
        if added or removed:
            print(f"🌱 Universe seed merge: +{added} (now {after} names)")
        return added

    def yahoo_discovery_due(self, *, max_age_hours: int = 24) -> bool:
        """True when Yahoo movers have never run or last run is older than max_age."""
        meta = self.universe.get("meta")
        if not isinstance(meta, dict):
            return True
        last = str(meta.get("last_yahoo_discovery") or "").strip()
        if not last:
            return True
        try:
            then = datetime.fromisoformat(last.replace("Z", "+00:00"))
            if then.tzinfo is not None:
                then = then.replace(tzinfo=None)
            age_h = (datetime.now() - then).total_seconds() / 3600.0
            return age_h >= float(max_age_hours)
        except (TypeError, ValueError):
            return True

    def discover_yahoo_movers(self, *, per_screen: int = 25, max_new: int = 40) -> int:
        """
        Add Yahoo day gainers/losers/actives into the universe (discovery only).

        Does not buy anything. Caps new adds per call to avoid universe bloat.
        """
        from stock_checker.yahoo_universe_discovery import discover_yahoo_mover_symbols

        try:
            symbols = discover_yahoo_mover_symbols(per_screen=per_screen)
        except Exception as e:
            print(f"   ⚠️ Yahoo movers discovery failed: {str(e)[:120]}")
            return 0

        added = 0
        for sym in symbols:
            if added >= max_new:
                break
            if self.add_stock(sym, sector="yahoo_mover", exchange="US"):
                added += 1
        meta = self.universe.setdefault("meta", {})
        if not isinstance(meta, dict):
            meta = {}
            self.universe["meta"] = meta
        meta["last_yahoo_discovery"] = datetime.now().isoformat()
        meta["last_yahoo_added"] = added
        self._save_universe()
        if added:
            print(f"   📡 Yahoo movers → universe: +{added} (cap {max_new})")
        else:
            print("   📡 Yahoo movers → universe: no new names")
        return added

    def add_stock(self, symbol: str, sector: str = "unknown", exchange: str = "unknown"):
        """Add a stock to the universe."""
        if symbol not in self.universe["stocks"]:
            self.universe["stocks"][symbol] = {
                "sector": sector,
                "exchange": exchange,
                "added": datetime.now().isoformat()
            }

            # Update sector index
            if sector not in self.universe["sectors"]:
                self.universe["sectors"][sector] = []
            if symbol not in self.universe["sectors"][sector]:
                self.universe["sectors"][sector].append(symbol)

            # Update exchange index
            if exchange not in self.universe["exchanges"]:
                self.universe["exchanges"][exchange] = []
            if symbol not in self.universe["exchanges"][exchange]:
                self.universe["exchanges"][exchange].append(symbol)

            return True
        return False

    def add_stocks_batch(self, stocks: List[Dict]):
        """Add multiple stocks at once."""
        added = 0
        for stock in stocks:
            if self.add_stock(stock.get("symbol"), stock.get("sector", "unknown"), stock.get("exchange", "unknown")):
                added += 1

        if added > 0:
            self._save_universe()
            print(f"✅ Added {added} new stocks to universe")

        return added

    def get_stocks_to_scan(self, limit: int = 30, max_age_hours: int = 24) -> tuple:
        """
        Get next batch of stocks to scan based on scan history.
        
        Returns:
            Tuple of (list of symbols to scan, was_cycle_reset)
            was_cycle_reset: True if a full cycle was just completed and reset
        """
        cutoff_time = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()

        # Get all stocks
        all_stocks = list(self.universe["stocks"].keys())

        # Filter out recently scanned stocks
        unscanned = []
        stale = []

        for symbol in all_stocks:
            last_scan = self.scan_history["scanned"].get(symbol)

            if not last_scan:
                unscanned.append(symbol)
            elif last_scan < cutoff_time:
                stale.append(symbol)

        # Prioritize: unscanned first, then stale
        candidates = unscanned + stale

        # If we've scanned everything recently, reset and start over
        was_reset = False
        if len(candidates) < limit:
            print(f"🔄 Completed full market cycle! Scanned {len(self.universe['stocks'])} stocks")
            self.scan_history["last_full_cycle"] = datetime.now().isoformat()
            self.scan_history["scanned"] = {}
            self._save_scan_history()
            candidates = all_stocks
            was_reset = True

        # Return next batch
        import random
        random.shuffle(candidates)  # Randomize to avoid patterns
        return candidates[:limit], was_reset

    def mark_scanned(self, symbols: List[str]):
        """Mark stocks as scanned."""
        now = datetime.now().isoformat()
        for symbol in symbols:
            self.scan_history["scanned"][symbol] = now

        self._save_scan_history()

    def get_stats(self) -> Dict:
        """Get universe statistics."""
        # Reload scan history from disk to ensure we have latest data
        self.scan_history = self._load_scan_history()
        
        total = len(self.universe["stocks"])
        scanned = len(self.scan_history["scanned"])

        return {
            "total_stocks": total,
            "scanned_stocks": scanned,
            "unscanned_stocks": total - scanned,
            "coverage_pct": (scanned / total * 100) if total > 0 else 0,
            "sectors": len(self.universe["sectors"]),
            "exchanges": len(self.universe["exchanges"]),
            "last_updated": self.universe.get("last_updated"),
            "last_full_cycle": self.scan_history.get("last_full_cycle")
        }

    def discover_and_add_stocks(
        self, *, force_yahoo: bool = False, yahoo_max_age_hours: int = 24
    ) -> int:
        """Merge curated seed + Yahoo movers into the universe (discovery only)."""
        added = self.ensure_curated_seed()
        run_yahoo = force_yahoo or self.yahoo_discovery_due(
            max_age_hours=yahoo_max_age_hours
        )
        if not run_yahoo:
            print("   📡 Yahoo movers skipped (discovery fresh <24h)")
            return added
        try:
            added += self.discover_yahoo_movers()
        except Exception as e:
            print(f"⚠️  Yahoo discovery skipped: {str(e)[:100]}")
        return added
