"""
Paper Desk — local web UI for ai-stock-checker.

Open http://127.0.0.1:7779/desk
JSON:  http://127.0.0.1:7779/desk/api
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from openbb_backend.symbol_names import display_name, resolve_symbol_names


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        for line in path.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        return []
    return rows


def _parse_book_ts(raw: Any) -> Optional[datetime]:
    """Parse portfolio reset_at or trade timestamp into aware UTC."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    # ISO with optional Z
    try:
        iso = text.replace("Z", "+00:00") if text.endswith("Z") else text
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19] if len(text) >= 19 else text, fmt).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
    return None


def book_start_meta(
    portfolio: dict,
    trades: list[dict],
    *,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Book start date + age for Overview (reset_at, else first fill)."""
    start = _parse_book_ts(portfolio.get("reset_at"))
    if start is None:
        for t in trades:
            cand = _parse_book_ts(t.get("timestamp"))
            if cand is not None:
                start = cand
                break
    if start is None:
        return {
            "book_start": "",
            "book_age_days": None,
            "book_age_label": "",
        }
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    days = max(0, (clock.date() - start.astimezone(timezone.utc).date()).days)
    date_s = start.strftime("%Y-%m-%d")
    return {
        "book_start": date_s,
        "book_age_days": days,
        "book_age_label": f"{date_s} ({days}d)",
    }


def _trader_runtime_view() -> dict[str, Any]:
    """Read-only + editable trader/desk knobs for Ops — never include API keys."""
    from stock_checker import __version__
    from stock_checker.trader_config import load_trader_config

    data_dir = Path(os.getenv("DATA_DIR", "/data"))
    cfg = load_trader_config(data_dir)

    ai_mode = str(cfg.get("ai_mode") or "off")
    ai_model = str(cfg.get("ai_model") or "gemma4:latest")
    explicit = (os.getenv("LLM_BACKEND") or "").strip().lower()
    if explicit in {"ollama", "openai", "openai-compatible", "off", "none"}:
        llm_backend = "none" if explicit in {"off", "none"} else explicit
    elif any(
        (os.getenv(k) or "").strip()
        for k in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "LLM_API_KEY", "GROQ_API_KEY")
    ):
        llm_backend = "openai-compatible"
    elif ai_mode != "off":
        llm_backend = "ollama"
    else:
        # Still show ollama if host is configured — Ops can flip AI on without
        # implying the trade loop is already calling it.
        if (os.getenv("OLLAMA_HOST") or "").strip():
            llm_backend = "ollama"
        else:
            llm_backend = "none"

    key_set = any(
        (os.getenv(k) or "").strip()
        for k in ("OPENAI_API_KEY", "LLM_API_KEY", "GROQ_API_KEY")
    )
    live_marks = os.getenv("DESK_LIVE_MARKS", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    regime_snap = _load_json(data_dir / "market_regime.json", {})
    if not isinstance(regime_snap, dict):
        regime_snap = {}
    calm_snap = _load_json(data_dir / "paper_calm.json", {})
    if not isinstance(calm_snap, dict):
        calm_snap = {}

    return {
        "trader_version": __version__,
        "ai_mode": ai_mode,
        "ai_model": ai_model,
        "llm_backend": llm_backend,
        "llm_key_set": key_set,
        "ai_multi_role": bool(cfg.get("ai_multi_role", True)),
        # Match docker-compose intelligent-trader defaults (not live-parsed argv).
        # Prefer Ops/file knobs over hard-coded compose display defaults.
        "max_positions": int(cfg.get("max_positions") or 5),
        "min_hold_hours": float(cfg.get("min_hold_hours") or 24),
        "scan_interval_min": 15,
        "trade_interval_min": 5,
        "desk_live_marks": live_marks,
        "regime_gate": bool(cfg.get("regime_gate", True)),
        "rs_gate": bool(cfg.get("rs_gate", True)),
        "breadth_gate": bool(cfg.get("breadth_gate", True)),
        "promote_experiment_strategy": bool(
            cfg.get("promote_experiment_strategy", False)
        ),
        "fee_preset": str(cfg.get("fee_preset") or "revolut_standard"),
        "commission_rate": float(cfg.get("commission_rate") or 0.0025),
        "commission_min_eur": float(cfg.get("commission_min_eur") or 1.0),
        "stock_regime": str(regime_snap.get("stock_regime") or "—"),
        "crypto_regime": str(regime_snap.get("crypto_regime") or "—"),
        "regime_updated": str(regime_snap.get("updated_at") or ""),
        "calm_streak_days": int(calm_snap.get("streak_days") or 0),
        "calm_required_days": int(calm_snap.get("required_days") or 30),
        "calm_ready": bool(calm_snap.get("ready_for_compose_default")),
        "calm_detail": str(calm_snap.get("detail") or ""),
        "calm_hint": (
            "Compose promote default unlocks after 30 calm UTC days "
            "(promote on, book ≤ max, quiet fees)."
        ),
        "config_source": "file"
        if (data_dir / "trader_config.json").is_file()
        else "env",
        "ollama_host": (os.getenv("OLLAMA_HOST") or "").strip() or "—",
    }


def _upsert_scan_breadth_daily(
    data_dir: Path, pulse: dict[str, Any], scan_time: str
) -> list[dict[str, Any]]:
    """Persist one UTC-day scan-pulse row (upsert). Keeps last 30 days."""
    path = data_dir / "scan_breadth_daily.json"
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows_raw = _load_json(path, [])
    rows: list[dict[str, Any]] = [
        r for r in rows_raw if isinstance(r, dict) and r.get("day")
    ] if isinstance(rows_raw, list) else []
    archive_name = ""
    arch = find_day_scan_archive(data_dir, day)
    if arch is not None:
        archive_name = arch.name
    entry = {
        "day": day,
        "scan_time": scan_time or "",
        "crypto_n": int(pulse.get("crypto_n") or 0),
        "crypto_up": int(pulse.get("crypto_up") or 0),
        "crypto_down": int(pulse.get("crypto_down") or 0),
        "crypto_avg_chg": float(pulse.get("crypto_avg_chg") or 0.0),
        "crypto_big_movers": int(pulse.get("crypto_big_movers") or 0),
        "stock_breakouts_n": int(pulse.get("stock_breakouts_n") or 0),
        "stock_within_5pct_high": int(pulse.get("stock_within_5pct_high") or 0),
        "archive_file": archive_name,
    }
    out = [r for r in rows if str(r.get("day")) != day]
    out.append(entry)
    out.sort(key=lambda r: str(r.get("day") or ""))
    out = out[-30:]
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=2) + "\n")
    except OSError:
        return _annotate_scan_history(data_dir, rows[-14:])
    return _annotate_scan_history(data_dir, out[-14:])


def find_day_scan_archive(data_dir: Path, day: str) -> Optional[Path]:
    """Latest opportunities_YYYYMMDD_*.txt for a UTC calendar day."""
    day_s = str(day or "").strip()
    if len(day_s) != 10 or day_s[4] != "-" or day_s[7] != "-":
        return None
    ymd = day_s.replace("-", "")
    if not ymd.isdigit():
        return None
    arch = Path(data_dir) / "archive"
    if not arch.is_dir():
        return None
    files = sorted(arch.glob(f"opportunities_{ymd}_*.txt"))
    return files[-1] if files else None


def _annotate_scan_history(
    data_dir: Path, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Attach scan-log link flags for the Breadth Recent days list."""
    out: list[dict[str, Any]] = []
    for r in rows:
        row = dict(r)
        day = str(row.get("day") or "")
        path = find_day_scan_archive(data_dir, day)
        row["has_scan_log"] = path is not None
        if path is not None:
            row["archive_file"] = path.name
            row["scan_log_href"] = f"/desk/scan-log/{day}"
        else:
            row["scan_log_href"] = ""
        out.append(row)
    return out


def _fmt_hold(seconds: float) -> str:
    if seconds < 0:
        return "—"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def _prices_from_scan(opp: dict[str, Any]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for key in ("crypto_leaders", "stock_breakouts"):
        for row in opp.get(key) or []:
            sym = row.get("symbol")
            px = row.get("price")
            if sym is not None and px is not None:
                try:
                    prices[str(sym)] = float(px)
                except (TypeError, ValueError):
                    continue
    return prices


def _fetch_yfinance_prices(
    symbols: list[str], timeout_s: float = 4.0
) -> dict[str, float]:
    if not symbols:
        return {}

    def _one(sym: str) -> tuple[str, Optional[float]]:
        try:
            import yfinance as yf

            t = yf.Ticker(sym)
            hist = t.history(period="1d")
            if hist is not None and not hist.empty:
                return sym, float(hist["Close"].iloc[-1])
            info = getattr(t, "fast_info", None)
            if info is not None:
                last = getattr(info, "last_price", None) or (
                    info.get("lastPrice") if hasattr(info, "get") else None
                )
                if last is not None:
                    return sym, float(last)
        except Exception:
            return sym, None
        return sym, None

    out: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=min(6, len(symbols))) as pool:
        futs = [pool.submit(_one, s) for s in symbols]
        deadline = time.time() + timeout_s
        for fut in futs:
            remaining = max(0.05, deadline - time.time())
            try:
                sym, px = fut.result(timeout=remaining)
                if px is not None and px > 0:
                    out[sym] = px
            except FuturesTimeout:
                continue
            except Exception:
                continue
    return out


def load_desk_snapshot(
    data_dir: Path,
    *,
    live_marks: Optional[bool] = None,
    price_fetcher: Optional[Callable[[list[str]], dict[str, float]]] = None,
) -> dict[str, Any]:
    """Build the paper desk view model from on-disk trader state."""
    if live_marks is None:
        live_marks = os.getenv("DESK_LIVE_MARKS", "1").strip() not in {
            "0",
            "false",
            "False",
            "no",
        }

    portfolio = _load_json(data_dir / "portfolio.json", {})
    trades = _load_jsonl(data_dir / "trades.jsonl")
    age = book_start_meta(portfolio if isinstance(portfolio, dict) else {}, trades)
    entry_times = _load_json(data_dir / "entry_times.json", {})
    scan_history = _load_json(data_dir / "stock_scan_history.json", {})
    scanned = _load_json(data_dir / "scanned_symbols.json", {})
    watchdog_path = data_dir / "watchdog" / "status.txt"
    watchdog = watchdog_path.read_text().strip() if watchdog_path.exists() else ""

    opp_path = data_dir / "archive" / "opportunities_latest.json"
    if not opp_path.exists():
        arch = data_dir / "archive"
        candidates = (
            sorted(arch.glob("opportunities_2*.json")) if arch.exists() else []
        )
        opp_path = candidates[-1] if candidates else opp_path
    opportunities = _load_json(opp_path, {})

    cash = float(portfolio.get("cash") or 0)
    initial = float(portfolio.get("initial_cash") or 0)
    fees = float(portfolio.get("total_fees_paid") or 0)
    from stock_checker.trader_config import load_trader_config

    cfg_fees = load_trader_config(data_dir)
    try:
        commission_rate = float(
            portfolio.get("commission_rate")
            if portfolio.get("commission_rate") is not None
            else cfg_fees.get("commission_rate")
            or 0.0025
        )
    except (TypeError, ValueError):
        commission_rate = 0.0025
    try:
        commission_min_eur = float(
            portfolio.get("commission_min_eur")
            if portfolio.get("commission_min_eur") is not None
            else cfg_fees.get("commission_min_eur")
            or 1.0
        )
    except (TypeError, ValueError):
        commission_min_eur = 1.0
    fee_preset = str(
        portfolio.get("fee_preset")
        or cfg_fees.get("fee_preset")
        or "revolut_standard"
    )
    holdings = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}
    now = time.time()

    scan_prices = _prices_from_scan(opportunities)
    marks = dict(scan_prices)
    mark_source = "scan" if scan_prices else "cost"
    missing = [s for s in holdings if s not in marks or marks[s] <= 0]
    if live_marks and missing:
        fetcher = price_fetcher or (
            lambda syms: _fetch_yfinance_prices(syms, timeout_s=4.0)
        )
        try:
            live = fetcher(missing)
            if live:
                marks.update(live)
                mark_source = "live+scan" if scan_prices else "live"
        except Exception:
            pass
    if not marks:
        mark_source = "cost"

    rows: list[dict[str, Any]] = []
    cost = 0.0
    market_value = 0.0
    for symbol, qty in holdings.items():
        q = float(qty)
        buy = float(avg.get(symbol, 0) or 0)
        basis = q * buy
        cost += basis
        last = marks.get(symbol)
        if last is None or last <= 0:
            last = buy
            marked = False
        else:
            marked = True
        mv = q * last
        market_value += mv
        unreal = mv - basis
        unreal_pct = (unreal / basis * 100) if basis else 0.0
        entry_ts = float(entry_times.get(symbol) or 0) or None
        held_s = (now - entry_ts) if entry_ts else None
        rows.append(
            {
                "symbol": symbol,
                "quantity": q,
                "avg_buy": buy,
                "cost_basis": basis,
                "last": last,
                "market_value": mv,
                "unrealized": unreal,
                "unrealized_pct": unreal_pct,
                "marked": marked,
                "kind": "crypto" if "-USD" in str(symbol) else "stock",
                "held": _fmt_hold(held_s) if held_s is not None else "—",
                "held_seconds": held_s,
                "bought_at": (
                    datetime.fromtimestamp(entry_ts, tz=timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )
                    if entry_ts
                    else ""
                ),
                "weight_pct": 0.0,
                "weight_bar_pct": 0.0,
            }
        )

    equity_cost = cash + cost
    equity_mtm = cash + market_value
    if any(r["marked"] for r in rows):
        equity = equity_mtm
    else:
        equity = equity_cost
        mark_source = "cost"

    ret_pct = ((equity / initial) - 1) * 100 if initial else 0.0
    unrealized_total = market_value - cost
    unrealized_pct = (unrealized_total / cost * 100) if cost else 0.0
    deployed_pct = ((equity - cash) / equity * 100) if equity else 0.0

    for r in rows:
        w = (r["market_value"] / equity * 100) if equity else 0.0
        r["weight_pct"] = w
        r["weight_bar_pct"] = min(max(w, 0.0), 100.0)
    rows.sort(key=lambda r: r["market_value"], reverse=True)

    # Stuck capital (A15): past min-hold and underwater — visible, not silent.
    min_hold_h = float(cfg_fees.get("min_hold_hours") or 24)
    min_hold_s = max(4.0, min_hold_h) * 3600.0
    stuck = [
        {
            "symbol": r["symbol"],
            "unrealized_pct": r["unrealized_pct"],
            "held": r["held"],
            "held_seconds": r.get("held_seconds"),
        }
        for r in rows
        if (r.get("held_seconds") or 0) >= min_hold_s and float(r.get("unrealized_pct") or 0) < 0
    ]

    sells = [t for t in trades if t.get("type") == "SELL"]
    buys = [t for t in trades if t.get("type") == "BUY"]
    realized = sum(float(t.get("profit_loss") or 0) for t in sells)

    recs_raw = (opportunities.get("recommendations") or [])[:8]
    crypto_raw_all = list(opportunities.get("crypto_leaders") or [])
    stock_raw_all = list(opportunities.get("stock_breakouts") or [])
    crypto_raw = crypto_raw_all[:6]
    stock_raw = stock_raw_all[:6]

    # StockBee-lite pulse from latest scan lists (not a full market A/D line).
    crypto_up = sum(
        1 for r in crypto_raw_all if float(r.get("change_24h") or 0) > 0
    )
    crypto_down = sum(
        1 for r in crypto_raw_all if float(r.get("change_24h") or 0) < 0
    )
    crypto_changes = [float(r.get("change_24h") or 0) for r in crypto_raw_all]
    crypto_avg = (
        sum(crypto_changes) / len(crypto_changes) if crypto_changes else 0.0
    )
    crypto_big = sum(1 for c in crypto_changes if abs(c) >= 4.0)
    stock_near = sum(
        1 for r in stock_raw_all if float(r.get("pct_from_high") or 99) <= 5.0
    )
    stock_pulse = opportunities.get("stock_scan_pulse") or {}
    if not isinstance(stock_pulse, dict):
        stock_pulse = {}
    stock_scan_n = int(stock_pulse.get("stock_scan_n") or 0)
    stock_scan_up = int(stock_pulse.get("stock_scan_up") or 0)
    stock_scan_down = int(stock_pulse.get("stock_scan_down") or 0)
    stock_scan_flat = int(stock_pulse.get("stock_scan_flat") or 0)
    if stock_scan_n > 0:
        stock_ad_note = (
            f"Stock batch A/D {stock_scan_up}/{stock_scan_down} "
            f"of {stock_scan_n} priced names this scan"
        )
    else:
        stock_ad_note = "Stock batch A/D awaits next equity scan"
    scan_breadth = {
        "crypto_n": len(crypto_raw_all),
        "crypto_up": crypto_up,
        "crypto_down": crypto_down,
        "crypto_flat": max(0, len(crypto_raw_all) - crypto_up - crypto_down),
        "crypto_avg_chg": crypto_avg,
        "crypto_big_movers": crypto_big,
        "stock_breakouts_n": len(stock_raw_all),
        "stock_within_5pct_high": stock_near,
        "stock_scan_n": stock_scan_n,
        "stock_scan_up": stock_scan_up,
        "stock_scan_down": stock_scan_down,
        "stock_scan_flat": stock_scan_flat,
        "note": (
            "Scan-list pulse: crypto leaders + this-cycle stock batch A/D "
            "(not full-universe advance/decline). "
            + stock_ad_note
            + "."
        ),
    }
    scan_time = opportunities.get("scan_time") or ""
    # First slice toward multi-day A/D: upsert today's pulse when a scan exists.
    if crypto_raw_all or stock_raw_all or scan_time:
        scan_breadth_history = _upsert_scan_breadth_daily(
            data_dir, scan_breadth, str(scan_time)
        )
    else:
        hist_raw = _load_json(data_dir / "scan_breadth_daily.json", [])
        scan_breadth_history = _annotate_scan_history(
            data_dir,
            (
                [r for r in hist_raw if isinstance(r, dict)][-14:]
                if isinstance(hist_raw, list)
                else []
            ),
        )

    name_symbols: list[str] = []
    for sym in list(holdings.keys()):
        name_symbols.append(str(sym))
    for t in trades[-20:]:
        if t.get("symbol"):
            name_symbols.append(str(t["symbol"]))
    for r in recs_raw + crypto_raw + stock_raw:
        if r.get("symbol"):
            name_symbols.append(str(r["symbol"]))
    # unique, preserve order
    seen: set[str] = set()
    uniq_syms: list[str] = []
    for s in name_symbols:
        if s not in seen:
            seen.add(s)
            uniq_syms.append(s)
    names = resolve_symbol_names(uniq_syms, data_dir)

    for r in rows:
        r["name"] = display_name(r["symbol"], names)

    recent = []
    for t in reversed(trades[-20:]):
        sym = t.get("symbol") or "—"
        recent.append(
            {
                "timestamp": t.get("timestamp") or "—",
                "type": t.get("type") or "—",
                "symbol": sym,
                "name": display_name(str(sym), names),
                "quantity": float(t.get("quantity") or 0),
                "price": float(t.get("price") or 0),
                "commission": float(t.get("commission") or 0),
                "profit_loss": t.get("profit_loss"),
                "profit_loss_pct": t.get("profit_loss_pct"),
                "strategy": t.get("strategy"),
                "note": t.get("note"),
                "score": t.get("score"),
                "confidence": t.get("confidence"),
                "source": t.get("source"),
                "total_cost": t.get("total_cost"),
                "cash_remaining": t.get("cash_remaining"),
            }
        )

    recs = []
    for r in recs_raw:
        sym = r.get("symbol")
        recs.append(
            {
                "rank": r.get("rank"),
                "symbol": sym,
                "name": display_name(str(sym or ""), names),
                "asset_class": r.get("asset_class"),
                "strategy": r.get("strategy"),
                "score": float(r.get("score") or 0),
                "reasoning": r.get("reasoning") or "",
                "risk_note": r.get("risk_note") or "",
                "risk_rr": r.get("risk_rr"),
                "risk_rr_ok": r.get("risk_rr_ok"),
            }
        )

    crypto_leaders = []
    for r in crypto_raw:
        sym = r.get("symbol")
        crypto_leaders.append(
            {
                "symbol": sym,
                "name": display_name(str(sym or ""), names),
                "price": float(r.get("price") or 0),
                "change_24h": float(r.get("change_24h") or 0),
                "score": float(r.get("score") or 0),
                "volume_surge_pct": float(r.get("volume_surge_pct") or 0),
                "tradeable": bool(r.get("tradeable", True)),
                "risk_note": r.get("risk_note") or "",
                "risk_rr": r.get("risk_rr"),
                "risk_rr_ok": r.get("risk_rr_ok"),
            }
        )

    stock_breakouts = []
    for r in stock_raw:
        sym = r.get("symbol")
        stock_breakouts.append(
            {
                "symbol": sym,
                "name": display_name(str(sym or ""), names),
                "sector": r.get("sector") or "",
                "price": float(r.get("price") or 0),
                "pct_from_high": float(r.get("pct_from_high") or 0),
                "strength": r.get("strength") or "",
                "risk_note": r.get("risk_note") or "",
                "risk_rr": r.get("risk_rr"),
                "risk_rr_ok": r.get("risk_rr_ok"),
            }
        )

    scanned_count = len(scanned) if isinstance(scanned, dict) else 0
    hist_scanned = (
        scan_history.get("scanned") if isinstance(scan_history, dict) else {}
    )
    last_full = (
        scan_history.get("last_full_cycle") if isinstance(scan_history, dict) else None
    )
    weekend = datetime.now(timezone.utc).weekday() >= 5

    gh_watch = _load_json(data_dir / "github_watch" / "latest.json", {})
    gh_ideas = list(gh_watch.get("idea_bullets") or [])[:8]
    gh_updates = int(gh_watch.get("update_count") or 0)
    gh_at = gh_watch.get("generated_at") or ""
    gh_repo_count = int(gh_watch.get("repo_count") or 0)
    gh_checked = int(gh_watch.get("checked_count") or 0)
    gh_repos: list[dict[str, Any]] = []
    for row in (gh_watch.get("repos") or [])[:12]:
        tip = str(row.get("tip_message") or "").strip()
        if len(tip) > 110:
            tip = tip[:109] + "…"
        sha = str(row.get("tip_sha") or "")
        tip_short = sha[:7] if sha else ""
        # Prefer tip commit date, else newest listed commit, else repo pushed_at.
        last_commit_at = ""
        commits = row.get("commits") if isinstance(row.get("commits"), list) else []
        if sha and commits:
            for c in commits:
                if not isinstance(c, dict):
                    continue
                csha = str(c.get("sha") or "")
                if csha == sha or csha.startswith(sha[:7]):
                    last_commit_at = str(c.get("date") or "")[:10]
                    break
        if not last_commit_at and commits:
            c0 = commits[0]
            if isinstance(c0, dict):
                last_commit_at = str(c0.get("date") or "")[:10]
        if not last_commit_at:
            last_commit_at = str(row.get("pushed_at") or "")[:10]
        gh_repos.append(
            {
                "repo": row.get("repo") or "",
                "url": row.get("url") or "",
                "why": row.get("why") or "",
                "stars": int(row.get("stars") or 0),
                "status": (
                    "update"
                    if row.get("has_updates")
                    else ("error" if row.get("error") else "quiet")
                ),
                "tip_short": tip_short,
                "tip_message": tip,
                "pushed_at": (row.get("pushed_at") or "")[:10],
                "last_commit_at": last_commit_at,
            }
        )
    # Newest tip / activity first (ISO dates sort lexicographically).
    gh_repos.sort(
        key=lambda r: r.get("last_commit_at") or r.get("pushed_at") or "",
        reverse=True,
    )
    # When the watch is quiet, still surface latest tip per repo so Ideas isn't blank.
    gh_watch_notes: list[str] = []
    if not gh_ideas and gh_repos:
        for r in gh_repos[:6]:
            if r["tip_message"]:
                when = r.get("last_commit_at") or r.get("pushed_at") or ""
                when_bit = f" · {when}" if when else ""
                gh_watch_notes.append(
                    f"{r['repo']}: latest {r['tip_short'] or '—'}{when_bit} — {r['tip_message']}"
                )

    adopted_ideas = [
        {
            "title": "Scan pulse on Breadth",
            "from": "xang1234/stock-screener (StockBee-style A/D)",
            "note": "Crypto leaders advance/decline + ±4% movers from our scan lists.",
        },
        {
            "title": "Since-buy holding paths",
            "from": "portfolio-AI style position charts",
            "note": "Book + Charts show price since fill vs avg cost — no forecast lines.",
        },
        {
            "title": "Multi-screen paper desk",
            "from": "xang1234 screener page map",
            "note": "Overview / Charts / Screener / Breadth / Book / Ideas / Ops.",
        },
        {
            "title": "Daily scan-pulse history",
            "from": "xang1234/StockBee-style breadth over time",
            "note": "Breadth keeps UTC daily A/D snapshots from our scan lists.",
        },
        {
            "title": "Screener counts strip",
            "from": "MonsterDeveloper/simple-stock-screener (simplicity)",
            "note": "One glance: recommendation / crypto / breakout counts + session hint.",
        },
        {
            "title": "SMA market-regime gate",
            "from": "RyanJHamby/stock-screener (regime filtering)",
            "note": "Soft block new buys when SPY is below SMA200 or BTC below SMA50; holds untouched.",
        },
        {
            "title": "Relative-strength entry gate",
            "from": "RyanJHamby/stock-screener (RS as primary filter)",
            "note": "Soft block new buys lagging SPY/BTC over ~63 sessions; Ops toggle; fail-open.",
        },
        {
            "title": "Scan-breadth entry gate",
            "from": "RyanJHamby/stock-screener (market breadth)",
            "note": "Soft block new buys when scan-list A/D looks weak; not full-universe A/D.",
        },
        {
            "title": "ATR / R:R risk notes",
            "from": "RyanJHamby/stock-screener (stop + R:R framing)",
            "note": "Screener shows day-range / vol proxy stops + rough R:R — display only, not exits.",
        },
        {
            "title": "Yahoo movers → universe only",
            "from": "Yahoo Finance day gainers/losers/actives",
            "note": "Discovery into the scan list; buys still need regime/RS/breadth/fees.",
        },
    ]

    return {
        "brand": "AI Stock Checker",
        "tagline": "Paper desk — honest marks, low churn.",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "portfolio_updated": portfolio.get("last_updated") or "",
        "initial": initial,
        "cash": cash,
        "fees": fees,
        "commission_rate_pct": commission_rate * 100,
        "commission_min_eur": commission_min_eur,
        "fee_preset": fee_preset,
        "cost_basis_total": cost,
        "market_value": market_value,
        "equity": equity,
        "equity_cost": equity_cost,
        "ret_pct": ret_pct,
        "book_start": age["book_start"],
        "book_age_days": age["book_age_days"],
        "book_age_label": age["book_age_label"],
        "unrealized_total": unrealized_total,
        "unrealized_pct": unrealized_pct,
        "deployed_pct": deployed_pct,
        "positions": len(rows),
        "holdings": rows,
        "stuck_underwater": stuck,
        "stuck_note": (
            f"{len(stuck)} name(s) past min-hold and underwater — capital trapped until TP/SL/trim"
            if stuck
            else ""
        ),
        "realized": realized,
        "trade_count": len(trades),
        "buy_count": len(buys),
        "sell_count": len(sells),
        "recent_trades": recent,
        "reset_note": portfolio.get("reset_note") or "",
        "weekend_mode": weekend,
        "weekend_hint": "Weekend: crypto-only trading; US stocks paused."
        if weekend
        else "Weekday session: stocks + crypto per scan rules.",
        "mark_source": mark_source,
        "mark_note": {
            "live": "Marks from live quotes + latest scan.",
            "live+scan": "Marks from live quotes + latest scan.",
            "scan": "Marks from latest scan prices (live quotes skipped/unavailable).",
            "cost": "Showing cost basis — no fresh marks yet.",
        }.get(mark_source, ""),
        "recommendations": recs,
        "crypto_leaders": crypto_leaders,
        "stock_breakouts": stock_breakouts,
        "scan_breadth": scan_breadth,
        "scan_breadth_history": scan_breadth_history,
        "scan_time": opportunities.get("scan_time") or "",
        "scanned_symbols": scanned_count,
        "scan_history_symbols": len(hist_scanned) if isinstance(hist_scanned, dict) else 0,
        "last_full_cycle": last_full or "",
        "watchdog": watchdog,
        "has_scan": bool(opportunities),
        "github_watch_at": gh_at,
        "github_watch_updates": gh_updates,
        "github_watch_repos": gh_repo_count,
        "github_watch_checked": gh_checked,
        "github_watch_has_digest": bool(gh_watch),
        "github_ideas": gh_ideas,
        "github_watch_notes": gh_watch_notes,
        "github_repos": gh_repos,
        "adopted_ideas": adopted_ideas,
        "runtime": _trader_runtime_view(),
    }
