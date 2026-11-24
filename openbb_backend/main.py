#!/usr/bin/env python3
"""OpenBB Workspace custom backend — paper portfolio & signals widgets."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    _coerce_desk_cash,
    _coerce_desk_score,
    _coerce_opportunity_strip_limit,
    _fill_commission,
    _fill_signed,
    build_breadth_day_meta,
    build_breadth_glance,
    build_ledger_health,
    find_day_scan_archive,
    load_desk_snapshot,
    load_json_checked,
    load_jsonl_checked,
    resolve_opportunities_archive,
    scan_breadth_pulse_for_day,
)

# OpenBB /opportunities_markdown ceilings — bare ``recs[:15]`` /
# ``txt[:12000]`` lied when bool (desk Opportunities strip peer).
OPPORTUNITY_MARKDOWN_RECS_STRIP = 15
OPPORTUNITY_MARKDOWN_BODY_CHARS = 12000
from openbb_backend.charts import _curve_signed
from stock_checker.portfolio import fill_price_ok, long_only_quantity_ok
from openbb_backend.desk_logs import LOG_SOURCES, follow_log, list_log_sources, read_log_tail
from openbb_backend.repo_meta import load_repo_meta

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
API_KEY = os.getenv("OPENBB_BACKEND_API_KEY", "").strip()
_BACKEND_DIR = Path(__file__).parent

# Desk is same-origin only: no CDN scripts/fonts, no inline JS/CSS.
_DESK_CSP = (
    "default-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "frame-ancestors 'none'; "
    "img-src 'self'; "
    "font-src 'none'; "
    "connect-src 'self'; "
    "style-src 'self'; "
    "script-src 'self'"
)

_DESK_SCREENS = {
    "overview": {
        "template": "desk_overview.html",
        "label": "Overview",
        "title": "Overview — AI Stock Checker Paper Desk",
        "description": "Paper portfolio equity, top holdings, and scan pulse for AI Stock Checker.",
    },
    "charts": {
        "template": "desk_charts.html",
        "label": "Charts",
        "title": "Charts — AI Stock Checker Paper Desk",
        "description": "D3 charts for paper equity path, allocation, relative prices, and scan-list breadth glance.",
    },
    "screener": {
        "template": "desk_screener.html",
        "label": "Screener",
        "title": "Screener — AI Stock Checker Paper Desk",
        "description": "Ranked paper-trading opportunities, crypto leaders, and stock breakouts.",
    },
    "breadth": {
        "template": "desk_breadth.html",
        "label": "Breadth",
        "title": "Breadth — AI Stock Checker Paper Desk",
        "description": "Session mode, cash exposure, and scan coverage breadth.",
    },
    "book": {
        "template": "desk_book.html",
        "label": "Book",
        "title": "Book — AI Stock Checker Paper Desk",
        "description": "Paper holdings, hold times, and recent fills with fees.",
    },
    "ideas": {
        "template": "desk_ideas.html",
        "label": "Ideas",
        "title": "Ideas — AI Stock Checker Paper Desk",
        "description": "External GitHub research watch highlights for transferable trading ideas.",
    },
    "ops": {
        "template": "desk_ops.html",
        "label": "Ops",
        "title": "Ops — AI Stock Checker Paper Desk",
        "description": "Watchdog, runtime logs, and editable AI / regime knobs for the paper trading stack.",
    },
}


def _desk_account_id(request: Request) -> str:
    from stock_checker.paper_accounts import AccountIdError, normalize_account_id

    raw = request.query_params.get("account")
    try:
        return normalize_account_id(raw)
    except AccountIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _desk_nav(account_id: str = "") -> list[dict[str, str]]:
    q = f"?account={account_id}" if account_id else ""
    return [
        {
            "screen": key,
            "label": meta["label"],
            "href": ("/desk" if key == "overview" else f"/desk/{key}") + q,
        }
        for key, meta in _DESK_SCREENS.items()
    ]


def _desk_page_context(request: Request, screen: str) -> dict:
    meta = _DESK_SCREENS[screen]
    account_id = _desk_account_id(request)
    path = "/desk" if screen == "overview" else f"/desk/{screen}"
    if account_id:
        path = f"{path}?account={account_id}"
    return {
        "snap": load_desk_snapshot(DATA_DIR, account=account_id),
        "nav": _desk_nav(account_id),
        "repo": load_repo_meta(),
        "page": {
            "screen": screen,
            "title": meta["title"],
            "description": meta["description"],
            "canonical": str(request.base_url).rstrip("/") + path,
        },
    }



class DeskSecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path
        if path == "/desk" or path.startswith("/desk/"):
            response.headers["Content-Security-Policy"] = _DESK_CSP
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Cache-Control"] = "no-store"
            response.headers["Permissions-Policy"] = (
                "geolocation=(), microphone=(), camera=(), payment=()"
            )
        return response


app = FastAPI(
    title="AI Stock Checker → OpenBB",
    description="Paper portfolio, trades, and opportunities for OpenBB Workspace",
    version="0.8.0",
)

app.add_middleware(DeskSecurityHeaders)
app.mount(
    "/desk/static",
    StaticFiles(directory=str(_BACKEND_DIR / "static")),
    name="desk_static",
)
templates = Jinja2Templates(directory=str(_BACKEND_DIR / "templates"))


def _format_px(value: Any) -> str:
    """Show enough decimals for sub-€1 crypto so 0.0908 ≠ 0.08516 as '0.09'."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if abs(v) < 1:
        return f"{v:.5f}"
    return f"{v:,.2f}"


templates.env.filters["px"] = _format_px

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://pro.openbb.co",
        "https://pro.openbb.dev",
        "http://localhost:7779",
        "http://127.0.0.1:7779",
    ],
    allow_origin_regex=r"https://.*\.openbb\.co",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _check_key(x_api_key: Optional[str]) -> None:
    if not API_KEY:
        return
    if not x_api_key or x_api_key.strip() != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-KEY")


def _load_json(path: Path, default: Any) -> Any:
    """Parse JSON via desk lean-checked loader (xang1234 #498 / #540)."""
    doc, _meta = load_json_checked(path, default)
    return doc


DEFAULT_OPENBB_TRADES_LIMIT = 50


def _coerce_trades_limit(
    value: object, default: int = DEFAULT_OPENBB_TRADES_LIMIT
) -> int:
    """Positive OpenBB trade strip, or ``default`` when bool/gap/≤0.

    tradermonty #700/#655 + xang1234/portfolio AI: ``True→1`` must not invent
    a one-row Workspace recent-fill strip (parity with persistence load limit).
    """
    from stock_checker.persistence import _coerce_load_limit

    n = _coerce_load_limit(value)
    if n is None:
        return int(default)
    return n


def _load_trades(limit: object = DEFAULT_OPENBB_TRADES_LIMIT) -> List[Dict]:
    lim = _coerce_trades_limit(limit)
    rows, _meta = load_jsonl_checked(DATA_DIR / "trades.jsonl")
    return rows[-lim:]


@app.get("/")
def root():
    """Browser home is the desk. Widget discovery stays on /widgets.json."""
    return RedirectResponse(url="/desk", status_code=302)


@app.get("/desk/api")
def paper_desk_api(account: str = Query(default="")):
    """Same desk snapshot as JSON for scripts / friends tooling."""
    from stock_checker.paper_accounts import AccountIdError, normalize_account_id

    try:
        account_id = normalize_account_id(account)
    except AccountIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return load_desk_snapshot(DATA_DIR, account=account_id)


@app.get("/desk/api/leaderboard")
def paper_desk_leaderboard():
    """Offline Mode A leaderboard (cost-basis equity; fees shown)."""
    from stock_checker.paper_accounts import (
        build_leaderboard,
        leaderboard_missing_share,
        shared_desk_pin,
    )

    rows = build_leaderboard(DATA_DIR)
    return {
        "rows": rows,
        "missing": leaderboard_missing_share(rows),
        "shared_desk": shared_desk_pin(DATA_DIR),
    }


@app.get("/desk/api/config")
def desk_config_get():
    """Editable trader knobs (no secrets)."""
    from stock_checker.ops_audit import (
        format_last_ops_action_bit,
        last_ops_action,
        ops_changed_impact_warn,
        ops_outcome_vs_file_clash,
        ops_outcome_vs_file_warn,
        trader_config_mtime_utc,
    )
    from stock_checker.trader_config import config_precedence_status, load_trader_config

    cfg = load_trader_config(DATA_DIR)
    prec = config_precedence_status(DATA_DIR)
    last_save = last_ops_action(DATA_DIR, kind="config")
    cfg_mtime = trader_config_mtime_utc(DATA_DIR)
    return {
        **cfg,
        "source": str(prec.get("source") or "env"),
        "precedence": prec.get("line") or "",
        "precedence_tone": prec.get("tone") or "env",
        "precedence_meter": prec.get("meter") or "",
        "precedence_lead": prec.get("lead") or "",
        "precedence_lead_share": prec.get("lead_share") or "",
        "precedence_lead_margin": prec.get("lead_margin") or "",
        "precedence_lead_sides": prec.get("lead_sides") or "",
        "precedence_lead_sides_share": prec.get("lead_sides_share") or "",
        "precedence_lead_sides_share_delta": prec.get("lead_sides_share_delta")
        or "",
        "precedence_lead_sides_share_vs_delta": prec.get(
            "lead_sides_share_vs_delta"
        )
        or "",
        "file_freshness": prec.get("file_freshness") or "",
        "file_age_label": prec.get("file_age_label") or "",
        "file_age_bit": prec.get("file_age_bit") or "",
        "overrides": list(prec.get("overrides") or []),
        "confirms": list(prec.get("confirms") or []),
        "env_fallbacks": list(prec.get("env_fallbacks") or []),
        "last_ops_action": format_last_ops_action_bit(
            last_save, config_mtime=cfg_mtime
        ),
        "last_ops_action_id": str((last_save or {}).get("action_id") or ""),
        "last_ops_outcome": str((last_save or {}).get("outcome") or ""),
        "last_ops_file_clash_warn": ops_outcome_vs_file_warn(
            ops_outcome_vs_file_clash(last_save, config_mtime=cfg_mtime)
        ),
        "last_ops_impact_warn": ops_changed_impact_warn(last_save),
        "note": (
            "Saved Ops row wins over compose/env for keys present in "
            "data/trader_config.json; intelligent-trader hot-reloads each loop. "
            "Config saves audit-before-act (requested row before write)."
        ),
    }


@app.put("/desk/api/config")
async def desk_config_put(
    request: Request,
    dry_run: bool = Query(
        False,
        description="Preview Save impact only (no audit / disk write)",
    ),
):
    """Update trader knobs from Ops. Never accepts API keys.

    xang1234 #613/#628: audit ``requested`` before the file write; block
    the mutation when that audit commit fails so a silent change cannot
    land without a record of intent.

    ``dry_run=1`` (xang1234 #636 confirm-first): return changed / severity /
    confirm copy without writing — Ops asks once before a hot Save.
    """
    from stock_checker.ops_audit import (
        audited_ops_action,
        ops_save_body_detail,
        record_ops_skipped,
    )
    from stock_checker.trader_config import (
        ALLOWED_AI_MODES,
        config_changed_impact_severity,
        config_changed_impact_warn,
        config_save_open_cash_venues,
        format_config_changed_bit,
        format_config_save_confirm,
        format_config_save_session_bit,
        save_trader_config,
        trader_config_changed_keys,
    )

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="JSON body required") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object required")

    # Strip anything that looks like a secret.
    forbidden = {
        k
        for k in body
        if "key" in str(k).lower()
        or "token" in str(k).lower()
        or "secret" in str(k).lower()
        or "password" in str(k).lower()
    }
    if forbidden:
        raise HTTPException(status_code=400, detail="Secrets are not accepted here")

    mode = str(body.get("ai_mode", "")).strip().lower()
    if mode and mode not in ALLOWED_AI_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"ai_mode must be one of: {', '.join(sorted(ALLOWED_AI_MODES))}",
        )

    changed = trader_config_changed_keys(DATA_DIR, body)
    impact = format_config_changed_bit(changed)
    severity = config_changed_impact_severity(changed)
    needs_confirm = config_changed_impact_warn(changed)
    # xang1234 #636 when-to-run: mid-session only matters for hot Saves.
    open_cash = config_save_open_cash_venues() if needs_confirm else []
    session_bit = format_config_save_session_bit(open_cash)
    confirm = format_config_save_confirm(changed, open_cash=open_cash)

    # xang1234 #636: preview impact before Run/Save — no audit noise on dry-run.
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "changed": changed,
            "changed_bit": impact,
            "changed_impact_severity": severity,
            "needs_confirm": needs_confirm,
            "confirm": confirm,
            "open_cash": open_cash,
            "session_bit": session_bit,
            "mid_session": bool(session_bit),
            "note": (
                confirm
                or (
                    f"Quiet Save ({impact}) — no confirm."
                    if impact
                    else "No config changes — save would skip."
                )
            ),
        }

    # xang1234 #623: refuse before audit/write when Save would only skip;
    # record why so glance speaks ``skipped · no-op`` (#599 skip-says-why).
    # True→1 must not invent a one-key strip via sorted(body)[:True]
    # (_safe_detail changed-items peer — HTTP Save was still bare [:16]).
    if not changed:
        record_ops_skipped(
            DATA_DIR,
            kind="config",
            reason="no-op",
            detail=ops_save_body_detail(body),
        )
        raise HTTPException(
            status_code=409,
            detail="No config changes — save skipped",
        )

    # xang1234 #636: persist which knobs this Save affects (glance Δ + toast).
    # Mid-session open_cash only on hot Saves (when-to-run honesty).
    detail = ops_save_body_detail(body)
    detail["changed"] = changed
    if open_cash:
        detail["open_cash"] = open_cash

    saved, audit = audited_ops_action(
        DATA_DIR,
        kind="config",
        detail=detail,
        act=lambda: save_trader_config(DATA_DIR, body),
    )
    if audit.get("blocked") or saved is None:
        if audit.get("reason") == "pending_in_flight":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Ops config save already in flight — wait for the pending "
                    "audit outcome, then retry"
                ),
            )
        raise HTTPException(
            status_code=503,
            detail="Ops audit unavailable — config not saved",
        )
    note = "Saved. Trader applies on the next loop iteration (~trade interval)."
    if impact:
        if session_bit:
            note = (
                f"Saved ({impact} · {session_bit}). "
                "Trader applies on the next loop iteration (~trade interval)."
            )
        else:
            note = (
                f"Saved ({impact}). "
                "Trader applies on the next loop iteration (~trade interval)."
            )
    return {
        **saved,
        "source": "file",
        "ok": True,
        "action_id": audit.get("action_id") or "",
        "audit_outcome": audit.get("outcome") or "accepted",
        "audit_outcome_recorded": bool(audit.get("outcome_recorded")),
        "changed": changed,
        "changed_bit": impact,
        "changed_impact_severity": severity,
        "open_cash": open_cash,
        "session_bit": session_bit,
        "mid_session": bool(session_bit),
        "note": note,
    }


@app.get("/desk/api/charts")
def paper_desk_charts():
    """Equity / allocation / price series for the Charts screen."""
    return load_chart_payload(DATA_DIR)


@app.get("/desk/api/logs")
def desk_logs_list():
    """Allowlisted log files under DATA_DIR (shared volume with the trader)."""
    return {"sources": list_log_sources(DATA_DIR), "default": "trader"}


@app.get("/desk/api/logs/{source}")
def desk_logs_tail(source: str, max_bytes: int = Query(64_000, ge=1024, le=512_000)):
    """Snapshot tail of one allowlisted log."""
    if source not in LOG_SOURCES:
        raise HTTPException(status_code=404, detail="Unknown log source")
    return read_log_tail(DATA_DIR, source, max_bytes=max_bytes)


@app.get("/desk/api/logs/{source}/stream")
async def desk_logs_stream(source: str):
    """SSE live tail — same files the trader/loops write under /data."""
    if source not in LOG_SOURCES:
        raise HTTPException(status_code=404, detail="Unknown log source")

    async def event_gen():
        try:
            async for chunk in follow_log(DATA_DIR, source):
                for line in chunk.splitlines() or [""]:
                    yield f"data: {line}\n"
                yield "\n"
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — surface to client then end
            yield f"event: logerror\ndata: {exc}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/favicon.ico")
def favicon_root():
    """Browser default favicon probe."""
    path = _BACKEND_DIR / "static" / "favicon.ico"
    return Response(path.read_bytes(), media_type="image/x-icon")


@app.get("/desk/scan-log/{day}", response_class=HTMLResponse)
def desk_scan_log(request: Request, day: str):
    """Show the latest scan opportunity report for a UTC day (Breadth Recent days)."""
    path = find_day_scan_archive(DATA_DIR, day)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="No scan log for that day")
    try:
        body = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:120]) from exc
    # Cap huge archives for the browser view.
    if len(body) > 200_000:
        body = body[:200_000] + "\n\n… truncated …\n"
    snap = load_desk_snapshot(DATA_DIR)
    # Day-specific glance (not "latest") — StockBee-style drill-down, display only.
    day_pulse = scan_breadth_pulse_for_day(DATA_DIR, day)
    day_meta = build_breadth_day_meta(day_pulse)
    snap = {
        **snap,
        "breadth_glance": build_breadth_glance(
            day_pulse,
            history=snap.get("scan_breadth_history")
            if isinstance(snap.get("scan_breadth_history"), list)
            else None,
        ),
    }
    return templates.TemplateResponse(
        request=request,
        name="desk_scan_log.html",
        context={
            "snap": snap,
            "nav": _desk_nav(),
            "repo": load_repo_meta(),
            "day": day,
            "day_meta": day_meta,
            "archive_file": path.name,
            "body": body,
            "page": {
                "screen": "breadth",
                "title": f"Scan log {day} — AI Stock Checker Paper Desk",
                "description": f"Trader opportunity report for UTC day {day}.",
                "canonical": str(request.base_url).rstrip("/") + f"/desk/scan-log/{day}",
            },
        },
    )


@app.get("/desk", response_class=HTMLResponse)
@app.get("/desk/{screen}", response_class=HTMLResponse)
def paper_desk(request: Request, screen: str = "overview"):
    """Local paper desk UI — multi-screen (no OpenBB account required)."""
    if screen not in _DESK_SCREENS:
        raise HTTPException(status_code=404, detail="Unknown desk screen")
    meta = _DESK_SCREENS[screen]
    return templates.TemplateResponse(
        request=request,
        name=meta["template"],
        context=_desk_page_context(request, screen),
    )


@app.get("/widgets.json")
def widgets():
    return JSONResponse(
        content=json.loads((Path(__file__).parent / "widgets.json").read_text())
    )


@app.get("/apps.json")
def apps():
    return JSONResponse(
        content=json.loads((Path(__file__).parent / "apps.json").read_text())
    )


@app.get("/portfolio_table")
def portfolio_table(x_api_key: Optional[str] = Header(default=None, alias="X-API-KEY")):
    """Holdings table for OpenBB.

    tradermonty #700/#655 + desk Overview: bool/gap qty·avg must not invent
    1-share / €1 cost rows (``True→1.0``).
    """
    _check_key(x_api_key)
    portfolio = _load_json(DATA_DIR / "portfolio.json", {})
    holdings = portfolio.get("holdings") or {}
    if not isinstance(holdings, dict):
        holdings = {}
    avg = portfolio.get("avg_buy_price") or {}
    if not isinstance(avg, dict):
        avg = {}
    rows = []
    for symbol, qty in holdings.items():
        if not long_only_quantity_ok(qty):
            continue
        buy_raw = avg.get(symbol)
        if not fill_price_ok(buy_raw):
            continue
        buy = float(buy_raw)
        q = float(qty)
        rows.append(
            {
                "symbol": symbol,
                "quantity": round(q, 6),
                "avg_buy_price": round(buy, 4),
                "cost_basis": round(q * buy, 2),
            }
        )
    rows.sort(key=lambda r: r["cost_basis"], reverse=True)
    return rows


@app.get("/portfolio_markdown")
def portfolio_markdown(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-KEY"),
):
    """Markdown summary of paper portfolio health.

    tradermonty #700/#655 + xang1234/portfolio AI: refuse bool/gap cash·fees·
    lots·P&L so OpenBB widgets cannot invent €1 book / flat +€1 realized.
    """
    _check_key(x_api_key)
    portfolio = _load_json(DATA_DIR / "portfolio.json", {})
    trades = _load_trades(5000)
    sells = [t for t in trades if t.get("type") == "SELL"]
    fees = _coerce_desk_cash(portfolio.get("total_fees_paid"))
    if fees is None:
        fees = 0.0
    realized = 0.0
    for t in sells:
        pl = _curve_signed(t.get("profit_loss"))
        if pl is not None:
            realized += pl
    cash = _coerce_desk_cash(portfolio.get("cash"))
    if cash is None:
        cash = 0.0
    initial = _coerce_desk_cash(portfolio.get("initial_cash"))
    if initial is None:
        initial = 0.0
    holdings = portfolio.get("holdings") or {}
    if not isinstance(holdings, dict):
        holdings = {}
    avg = portfolio.get("avg_buy_price") or {}
    if not isinstance(avg, dict):
        avg = {}
    cost = 0.0
    n_pos = 0
    for s, q in holdings.items():
        if not long_only_quantity_ok(q):
            continue
        buy_raw = avg.get(s)
        if not fill_price_ok(buy_raw):
            continue
        cost += float(q) * float(buy_raw)
        n_pos += 1
    approx_equity = cash + cost
    ret = ((approx_equity / initial) - 1) * 100 if initial else 0.0

    md = f"""# Paper Portfolio

- **Initial capital:** €{initial:,.2f}
- **Cash:** €{cash:,.2f}
- **Holdings (cost basis):** €{cost:,.2f}
- **Approx equity:** €{approx_equity:,.2f} ({ret:+.2f}%)
- **Positions:** {n_pos}
- **Fees paid:** €{fees:,.2f}
- **Realized P&L (sells):** €{realized:,.2f}
- **Trades logged:** {len(trades)}
- **Updated:** {portfolio.get("last_updated", "n/a")}

> Equity uses average cost when live marks are unavailable.
"""
    return PlainTextResponse(md)


@app.get("/trades_table")
def trades_table(
    limit: int = Query(40, ge=1, le=200),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-KEY"),
):
    """Recent trades table.

    tradermonty #700/#655 + desk Recent fills: bool/gap/0 qty·price or bad
    commission/P&L must not invent 1-share / €1 / flat +€1 Workspace rows
    (``True→1.0``). Damaged rows stay visible with nulls + ``fill_ok=False``.
    """
    _check_key(x_api_key)
    rows = []
    for t in reversed(_load_trades(limit)):
        if not isinstance(t, dict):
            continue
        qty_ok = long_only_quantity_ok(t.get("quantity"))
        px_ok = fill_price_ok(t.get("price"))
        commission = _fill_commission(t.get("commission"))
        fill_ok = bool(qty_ok and px_ok and commission is not None)
        rows.append(
            {
                "timestamp": t.get("timestamp"),
                "type": t.get("type"),
                "symbol": t.get("symbol"),
                "quantity": float(t["quantity"]) if qty_ok else None,
                "price": float(t["price"]) if px_ok else None,
                "commission": commission,
                "profit_loss": _fill_signed(t.get("profit_loss")),
                "fill_ok": fill_ok,
            }
        )
    return rows


def _opportunities_markdown_body(
    data_dir: Path,
    *,
    recs_n: object = None,
    body_n: object = None,
) -> str:
    """Prefer opportunities_latest; fall back like desk (xang1234 #682/#685).

    Hard-reading ``opportunities_latest.txt``/``.json`` alone hid a missing,
    dangling, or stale pin that desk/Charts already fall back from.

    tradermonty #700/#655 + staskh dash-for-null: JSON fallback must not dump
    bool/gap scores as printable marks (``True→1`` / bare ``True``).

    FinRobot + xang1234 screener + tradermonty #700/#655 + portfolio AI:
    strip/body ceilings refuse bool so ``True→1`` cannot invent a one-name
    Workspace strip via ``recs[:True]`` / one-char txt via ``body[:True]``;
    ``False→0`` must not wipe (desk Opportunities strip peer — OpenBB widget
    was still bare ``[:15]`` / ``[:12000]``).
    """
    # True→1 must not invent a one-name / one-char OpenBB strip.
    recs_cap = _coerce_opportunity_strip_limit(
        OPPORTUNITY_MARKDOWN_RECS_STRIP if recs_n is None else recs_n,
        OPPORTUNITY_MARKDOWN_RECS_STRIP,
    )
    body_cap = _coerce_opportunity_strip_limit(
        OPPORTUNITY_MARKDOWN_BODY_CHARS if body_n is None else body_n,
        OPPORTUNITY_MARKDOWN_BODY_CHARS,
    )

    archive_res = resolve_opportunities_archive(data_dir)
    path = Path(archive_res["path"])
    pin_bit = str(archive_res.get("bit") or "").strip()
    prefix = f"_Archive pin: {pin_bit}_\n\n" if pin_bit else ""

    txt = path.with_suffix(".txt") if path.suffix.lower() == ".json" else path
    if txt.is_file():
        body = txt.read_text()[:body_cap]
        return f"{prefix}{body}" if prefix else body

    if path.is_file():
        data = _load_json(path, {})
        if not isinstance(data, dict):
            data = {}
        recs = data.get("recommendations") or []
        if not isinstance(recs, list):
            recs = []
        lines = ["# Latest opportunities", ""]
        shown = 0
        for r in recs[:recs_cap]:
            if not isinstance(r, dict):
                continue
            score = _coerce_desk_score(r.get("score"))
            score_s = f"{score:g}" if score is not None else "n/a"
            lines.append(
                f"- **{r.get('symbol')}** ({r.get('asset_class')}) "
                f"score={score_s} — {r.get('reasoning')}"
            )
            shown += 1
        body = "\n".join(lines) if shown else "# No recommendations"
        return f"{prefix}{body}" if prefix else body

    return "# No opportunity archive yet\nRun intelligent-trader scans first."


@app.get("/opportunities_markdown")
def opportunities_markdown(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-KEY"),
):
    """Latest archived opportunities (keep-newest parity with desk).

    tradermonty #700/#655 + desk Opportunities: bool/gap scores speak ``n/a``
    on the JSON fallback path (``True→1.0`` refuse). Strip/body ceilings also
    refuse bool invent (``[:15]`` / ``[:12000]`` peers).
    """
    _check_key(x_api_key)
    return PlainTextResponse(_opportunities_markdown_body(DATA_DIR))


@app.get("/health")
def health():
    ledger = build_ledger_health(DATA_DIR)
    return {
        "ok": True,
        "time": datetime.utcnow().isoformat() + "Z",
        "portfolio_exists": (DATA_DIR / "portfolio.json").exists(),
        "ledger": ledger.get("line") or "ledger none",
        "ledger_severity": ledger.get("severity") or "",
    }
