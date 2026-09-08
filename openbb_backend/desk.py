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
from stock_checker.trade_postmortem import DEFAULT_LIMIT as POSTMORTEM_LIMIT
from stock_checker.trade_postmortem import closed_rounds


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


RECENT_FILLS_LIMIT = 20


def _serialize_trade_row(t: dict, names: dict[str, str]) -> dict[str, Any]:
    sym = t.get("symbol") or "—"
    return {
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
        "exit_reason": t.get("exit_reason"),
        "total_cost": t.get("total_cost"),
        "cash_remaining": t.get("cash_remaining"),
    }


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



def _format_age_short(age_sec: float) -> str:
    """Human age for scan freshness (display only)."""
    sec = max(0, int(age_sec))
    if sec < 60:
        return "just now"
    if sec < 3600:
        return f"{sec // 60}m ago"
    if sec < 36 * 3600:
        return f"{sec // 3600}h ago"
    return f"{sec // 86400}d ago"


def build_scan_freshness(
    scan_time: Any,
    *,
    now: Optional[datetime] = None,
    scan_interval_sec: int = 900,
) -> dict[str, Any]:
    """Scan archive age honesty (RyanJHamby cache-freshness pattern; display only).

    fresh < 2× scan interval · aging < 8× · else stale. Not an entry gate.
    """
    empty = {
        "ready": False,
        "tone": "unknown",
        "age_sec": None,
        "age_label": "",
        "line": "",
        "scan_time": "",
    }
    raw = str(scan_time or "").strip()
    if not raw:
        return empty
    when = _parse_book_ts(raw)
    if when is None:
        return {
            **empty,
            "ready": True,
            "tone": "unknown",
            "line": f"Scan {raw} · age unknown",
            "scan_time": raw,
        }
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    age_sec = max(0.0, (clock - when).total_seconds())
    interval = max(60, int(scan_interval_sec or 900))
    if age_sec < 2 * interval:
        tone = "fresh"
    elif age_sec < 8 * interval:
        tone = "aging"
    else:
        tone = "stale"
    age_label = _format_age_short(age_sec)
    return {
        "ready": True,
        "tone": tone,
        "age_sec": int(age_sec),
        "age_label": age_label,
        "line": f"Scan {age_label} · {tone}",
        "scan_time": raw,
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
    portfolio = _load_json(data_dir / "portfolio.json", {})
    if not isinstance(portfolio, dict):
        portfolio = {}
    free_legs = int(
        portfolio.get("free_legs_per_month")
        or cfg.get("free_legs_per_month")
        or 0
    )
    allowance_used = int(portfolio.get("fee_allowance_used") or 0)
    allowance_month = str(portfolio.get("fee_allowance_month") or "")
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    if allowance_month != current_month:
        allowance_used = 0
    allowance_remaining = max(0, free_legs - allowance_used)

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
        "free_legs_per_month": free_legs,
        "fee_allowance_used": allowance_used,
        "fee_allowance_remaining": allowance_remaining,
        "fee_allowance_month": current_month,
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
        "stock_scan_n": int(pulse.get("stock_scan_n") or 0),
        "stock_scan_up": int(pulse.get("stock_scan_up") or 0),
        "stock_scan_down": int(pulse.get("stock_scan_down") or 0),
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


def scan_breadth_pulse_for_day(
    data_dir: Path, day: str
) -> dict[str, Any] | None:
    """UTC-day scan-list pulse row from Breadth history (display only)."""
    rows = _load_json(data_dir / "scan_breadth_daily.json", [])
    if not isinstance(rows, list):
        return None
    want = str(day or "").strip()
    if not want:
        return None
    for row in rows:
        if isinstance(row, dict) and str(row.get("day") or "") == want:
            return row
    return None


def build_breadth_glance(pulse: dict[str, Any] | None) -> dict[str, Any]:
    """One-line scan-list glance for HTML screens + Charts API (display only; not a gate)."""
    empty = {
        "ready": False,
        "tone": "flat",
        "line": "",
        "crypto_net": 0,
        "stock_net": 0,
        "near_high": 0,
        "big_movers": 0,
    }
    if not isinstance(pulse, dict):
        return empty
    crypto_up = int(pulse.get("crypto_up") or 0)
    crypto_down = int(pulse.get("crypto_down") or 0)
    stock_up = int(pulse.get("stock_scan_up") or 0)
    stock_down = int(pulse.get("stock_scan_down") or 0)
    # Infer n from up+down when daily rows omit crypto_n / stock_scan_n.
    crypto_n = int(pulse.get("crypto_n") or 0) or (crypto_up + crypto_down)
    stock_n = int(pulse.get("stock_scan_n") or 0) or (stock_up + stock_down)
    near = int(pulse.get("stock_within_5pct_high") or 0)
    breakouts_n = int(pulse.get("stock_breakouts_n") or 0)
    movers = int(pulse.get("crypto_big_movers") or 0)
    if crypto_n <= 0 and stock_n <= 0 and breakouts_n <= 0:
        return empty

    crypto_net = crypto_up - crypto_down
    stock_net = stock_up - stock_down
    parts: list[str] = []
    score = 0
    if crypto_n > 0:
        parts.append(f"crypto {crypto_up}/{crypto_down} ({crypto_net:+d})")
        score += crypto_net
    if stock_n > 0:
        parts.append(f"stock batch {stock_up}/{stock_down} ({stock_net:+d})")
        score += stock_net
    if breakouts_n > 0 or near > 0:
        parts.append(f"{near} near-high")
    if movers > 0:
        parts.append(f"{movers} ±4% movers")
    if not parts:
        return empty
    if score > 0:
        tone = "up"
    elif score < 0:
        tone = "down"
    else:
        tone = "flat"
    return {
        "ready": True,
        "tone": tone,
        "line": " · ".join(parts),
        "crypto_net": crypto_net,
        "stock_net": stock_net if stock_n > 0 else 0,
        "near_high": near,
        "big_movers": movers,
    }


def build_breadth_ad_spark(
    rows: list[dict[str, Any]],
    *,
    up_key: str = "crypto_up",
    down_key: str = "crypto_down",
    label: str = "Crypto",
    aria_unit: str = "leaders up minus down",
    width: float = 320.0,
    height: float = 52.0,
    pad: float = 5.0,
) -> dict[str, Any]:
    """Inline SVG: multi-day A/D net (up−down). Display only; needs ≥2 days."""
    series: list[tuple[str, int]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        day = str(r.get("day") or "").strip()
        if not day:
            continue
        # Skip days that never recorded this A/D pair (old history rows).
        if up_key not in r and down_key not in r:
            continue
        up = int(r.get(up_key) or 0)
        down = int(r.get(down_key) or 0)
        series.append((day, up - down))
    empty = {
        "ready": False,
        "n": len(series),
        "svg": "",
        "aria": "",
        "latest_net": 0,
        "first_day": "",
        "last_day": "",
        "label": label,
    }
    if len(series) < 2:
        return empty

    nets = [net for _, net in series]
    y_min = min(min(nets), 0)
    y_max = max(max(nets), 0)
    if y_min == y_max:
        y_min -= 1
        y_max += 1
    span = float(y_max - y_min)
    inner_w = width - 2 * pad
    inner_h = height - 2 * pad
    n = len(series)

    def _xy(i: int, net: int) -> tuple[float, float]:
        x = pad + (inner_w * i / (n - 1))
        y = pad + inner_h * (1.0 - ((net - y_min) / span))
        return x, y

    coords = [_xy(i, net) for i, (_, net) in enumerate(series)]
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    y0 = pad + inner_h * (1.0 - ((0 - y_min) / span))
    last_net = nets[-1]
    tone = "up" if last_net >= 0 else "down"
    first_day, last_day = series[0][0], series[-1][0]
    aria = (
        f"{label} advance/decline net over {n} UTC days from {first_day} to {last_day}. "
        f"Latest net {last_net:+d} ({aria_unit})."
    )
    lx, ly = coords[-1]
    svg = (
        f'<svg class="breadth-ad-spark-svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}" role="img" aria-label="{aria}">'
        f'<line class="breadth-spark-zero" x1="{pad:.1f}" y1="{y0:.1f}" '
        f'x2="{width - pad:.1f}" y2="{y0:.1f}" />'
        f'<polyline class="breadth-spark-line is-{tone}" fill="none" '
        f'points="{points}" />'
        f'<circle class="breadth-spark-dot is-{tone}" cx="{lx:.1f}" cy="{ly:.1f}" r="2.6" />'
        f"</svg>"
    )
    return {
        "ready": True,
        "n": n,
        "svg": svg,
        "aria": aria,
        "latest_net": last_net,
        "first_day": first_day,
        "last_day": last_day,
        "label": label,
    }


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
    postmortems_raw = closed_rounds(trades, limit=POSTMORTEM_LIMIT)
    for r in postmortems_raw:
        if r.get("symbol"):
            name_symbols.append(str(r["symbol"]))
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

    all_trade_rows = [_serialize_trade_row(t, names) for t in reversed(trades)]
    recent = all_trade_rows[:RECENT_FILLS_LIMIT]
    older_trades = all_trade_rows[RECENT_FILLS_LIMIT:]
    postmortems = [
        {
            **r,
            "name": display_name(str(r.get("symbol") or ""), names),
        }
        for r in postmortems_raw
    ]

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
            "title": "Daily scan-pulse history + A/D spark",
            "from": "xang1234/StockBee-style breadth over time",
            "note": "Breadth keeps UTC daily A/D snapshots and a multi-day net A/D sparkline.",
        },
        {
            "title": "Screener breadth beside lists",
            "from": "xang1234/stock-screener (StockBee-lite next to screen)",
            "note": "Screener shows scan-list A/D + near-high / ±4% movers above opportunity lists — display only.",
        },
        {
            "title": "Ideas breadth beside candidates",
            "from": "xang1234/stock-screener (breadth next to research picks)",
            "note": "Ideas shows the same scan-list A/D glance above paper candidates — display only.",
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
        {
            "title": "Closed-round postmortem",
            "from": "tradermonty/claude-trading-skills (trader memory)",
            "note": "Book pairs BUY→SELL: thesis → exit → hold → mark P&L. No inventing MAE/MFE.",
        },
        {
            "title": "Pre-trade + position sizer",
            "from": "tradermonty/claude-trading-skills (pre-trade gate / sizer)",
            "note": "Overview shows PASS/WARN/FAIL + suggested next-buy € (cash frac · concentration · slots).",
        },
        {
            "title": "Book risk report strip",
            "from": "staskh/trading_skills + portfolio AI (risk / mix report)",
            "note": "Book shows slots, posture, cash %, largest name, equity/crypto mix — display only.",
        },
        {
            "title": "Book breadth beside holdings",
            "from": "xang1234/stock-screener + portfolio AI (risk context)",
            "note": "Book shows scan-list A/D glance next to risk strip — context for adds, not a gate.",
        },
        {
            "title": "Charts breadth beside paths",
            "from": "xang1234/stock-screener (StockBee-lite on JS Charts root)",
            "note": "Charts API carries scan-list A/D glance above equity/allocation — display only.",
        },
        {
            "title": "Fail-open soft-allow memory",
            "from": "tradermonty/claude-trading-skills (trader memory) + A5",
            "note": "Ops lists recent regime/RS/breadth/promote soft-allows when bars/data are missing.",
        },
        {
            "title": "Ops breadth beside gate knobs",
            "from": "xang1234/stock-screener (StockBee-lite next to controls)",
            "note": "Ops shows scan-list A/D above trader knobs — context before flipping breadth gate.",
        },
        {
            "title": "Scan-log day breadth glance",
            "from": "xang1234/stock-screener (StockBee day drill-down)",
            "note": "Scan log shows that UTC day’s scan-list A/D above the archive report — display only.",
        },
        {
            "title": "Scan freshness honesty",
            "from": "RyanJHamby/stock-screener (cache / daily-scan age)",
            "note": "Overview / Screener / Breadth / Ops / Book / Ideas / Charts show scan age as fresh / aging / stale — display only, not a gate.",
        },
    ]

    from stock_checker.gate_audit import recent_soft_allows
    from stock_checker.risk_halts import (
        book_risk_report,
        pretrade_status,
        suggest_entry_notional,
    )

    soft_allows = recent_soft_allows(data_dir, limit=12)

    max_pos = int(cfg_fees.get("max_positions") or 5)
    pretrade_level, pretrade_notes = pretrade_status(data_dir, initial_cash=initial)
    entry_size = suggest_entry_notional(
        cash=cash,
        equity=equity,
        open_positions=len(rows),
        max_positions=max_pos,
        position_size=0.10,
    )
    book_risk = book_risk_report(
        cash=cash,
        equity=equity,
        holdings=rows,
        max_positions=max_pos,
    )
    runtime = _trader_runtime_view()
    scan_interval_sec = max(60, int(runtime.get("scan_interval_min") or 15) * 60)
    scan_time_raw = opportunities.get("scan_time") or ""

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
        "pretrade_level": pretrade_level,
        "pretrade_notes": pretrade_notes,
        "entry_size": entry_size,
        "book_risk": book_risk,
        "soft_allows": soft_allows,
        "realized": realized,
        "trade_count": len(trades),
        "buy_count": len(buys),
        "sell_count": len(sells),
        "recent_trades": recent,
        "older_trades": older_trades,
        "recent_fills_limit": RECENT_FILLS_LIMIT,
        "postmortems": postmortems,
        "postmortem_limit": POSTMORTEM_LIMIT,
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
        "breadth_glance": build_breadth_glance(scan_breadth),
        "breadth_ad_spark": build_breadth_ad_spark(scan_breadth_history),
        "breadth_stock_ad_spark": build_breadth_ad_spark(
            scan_breadth_history,
            up_key="stock_scan_up",
            down_key="stock_scan_down",
            label="Stock batch",
            aria_unit="priced scan names up minus down",
        ),
        "scan_time": scan_time_raw,
        "scan_freshness": build_scan_freshness(
            scan_time_raw,
            scan_interval_sec=scan_interval_sec,
        ),
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
        "runtime": runtime,
    }
