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
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import find_day_scan_archive, load_desk_snapshot
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
        "description": "D3 charts for paper equity path, allocation, and relative prices.",
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
        "description": "Session mode, cash exposure, scan coverage, and allocation breadth.",
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


def _desk_nav() -> list[dict[str, str]]:
    return [
        {
            "screen": key,
            "label": meta["label"],
            "href": "/desk" if key == "overview" else f"/desk/{key}",
        }
        for key, meta in _DESK_SCREENS.items()
    ]


def _desk_page_context(request: Request, screen: str) -> dict:
    meta = _DESK_SCREENS[screen]
    path = "/desk" if screen == "overview" else f"/desk/{screen}"
    return {
        "snap": load_desk_snapshot(DATA_DIR),
        "nav": _desk_nav(),
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
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def _load_trades(limit: int = 50) -> List[Dict]:
    path = DATA_DIR / "trades.jsonl"
    if not path.exists():
        return []
    rows: List[Dict] = []
    try:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        return []
    return rows[-limit:]


@app.get("/")
def root():
    return {
        "info": "AI Stock Checker OpenBB backend",
        "data_dir": str(DATA_DIR),
        "auth_required": bool(API_KEY),
        "desk": "/desk",
        "desk_screens": list(_DESK_SCREENS),
        "desk_api": "/desk/api",
    }


@app.get("/desk/api")
def paper_desk_api():
    """Same desk snapshot as JSON for scripts / friends tooling."""
    return load_desk_snapshot(DATA_DIR)


@app.get("/desk/api/config")
def desk_config_get():
    """Editable trader knobs (no secrets)."""
    from stock_checker.trader_config import load_trader_config

    cfg = load_trader_config(DATA_DIR)
    return {
        **cfg,
        "source": "file"
        if (DATA_DIR / "trader_config.json").is_file()
        else "env",
        "note": "Saved to data/trader_config.json; intelligent-trader hot-reloads each loop.",
    }


@app.put("/desk/api/config")
async def desk_config_put(request: Request):
    """Update trader knobs from Ops. Never accepts API keys."""
    from stock_checker.trader_config import ALLOWED_AI_MODES, save_trader_config

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

    saved = save_trader_config(DATA_DIR, body)
    return {
        **saved,
        "source": "file",
        "ok": True,
        "note": "Saved. Trader applies on the next loop iteration (~trade interval).",
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
    return templates.TemplateResponse(
        request=request,
        name="desk_scan_log.html",
        context={
            "snap": load_desk_snapshot(DATA_DIR),
            "nav": _desk_nav(),
            "repo": load_repo_meta(),
            "day": day,
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
    """Holdings table for OpenBB."""
    _check_key(x_api_key)
    portfolio = _load_json(DATA_DIR / "portfolio.json", {})
    holdings = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}
    rows = []
    for symbol, qty in holdings.items():
        buy = float(avg.get(symbol, 0) or 0)
        rows.append(
            {
                "symbol": symbol,
                "quantity": round(float(qty), 6),
                "avg_buy_price": round(buy, 4),
                "cost_basis": round(float(qty) * buy, 2),
            }
        )
    rows.sort(key=lambda r: r["cost_basis"], reverse=True)
    return rows


@app.get("/portfolio_markdown")
def portfolio_markdown(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-KEY"),
):
    """Markdown summary of paper portfolio health."""
    _check_key(x_api_key)
    portfolio = _load_json(DATA_DIR / "portfolio.json", {})
    trades = _load_trades(5000)
    sells = [t for t in trades if t.get("type") == "SELL"]
    fees = float(portfolio.get("total_fees_paid") or 0)
    realized = sum(float(t.get("profit_loss") or 0) for t in sells)
    cash = float(portfolio.get("cash") or 0)
    initial = float(portfolio.get("initial_cash") or 0)
    holdings = portfolio.get("holdings") or {}
    cost = sum(
        float(q) * float((portfolio.get("avg_buy_price") or {}).get(s, 0) or 0)
        for s, q in holdings.items()
    )
    approx_equity = cash + cost
    ret = ((approx_equity / initial) - 1) * 100 if initial else 0.0

    md = f"""# Paper Portfolio

- **Initial capital:** €{initial:,.2f}
- **Cash:** €{cash:,.2f}
- **Holdings (cost basis):** €{cost:,.2f}
- **Approx equity:** €{approx_equity:,.2f} ({ret:+.2f}%)
- **Positions:** {len(holdings)}
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
    """Recent trades table."""
    _check_key(x_api_key)
    rows = []
    for t in reversed(_load_trades(limit)):
        rows.append(
            {
                "timestamp": t.get("timestamp"),
                "type": t.get("type"),
                "symbol": t.get("symbol"),
                "quantity": t.get("quantity"),
                "price": t.get("price"),
                "commission": t.get("commission"),
                "profit_loss": t.get("profit_loss"),
            }
        )
    return rows


@app.get("/opportunities_markdown")
def opportunities_markdown(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-KEY"),
):
    """Latest archived opportunities (if present)."""
    _check_key(x_api_key)
    latest = DATA_DIR / "archive" / "opportunities_latest.txt"
    if latest.exists():
        return PlainTextResponse(latest.read_text()[:12000])
    latest_json = DATA_DIR / "archive" / "opportunities_latest.json"
    if latest_json.exists():
        data = _load_json(latest_json, {})
        recs = data.get("recommendations") or []
        lines = ["# Latest opportunities", ""]
        for r in recs[:15]:
            lines.append(
                f"- **{r.get('symbol')}** ({r.get('asset_class')}) "
                f"score={r.get('score')} — {r.get('reasoning')}"
            )
        return PlainTextResponse("\n".join(lines) or "# No recommendations")
    return PlainTextResponse("# No opportunity archive yet\nRun intelligent-trader scans first.")


@app.get("/health")
def health():
    return {
        "ok": True,
        "time": datetime.utcnow().isoformat() + "Z",
        "portfolio_exists": (DATA_DIR / "portfolio.json").exists(),
    }
