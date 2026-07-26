#!/usr/bin/env python3
"""OpenBB Workspace custom backend — paper portfolio & signals widgets."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from openbb_backend.desk import load_desk_snapshot
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
    "connect-src 'none'; "
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
        "description": "Watchdog and runtime status for the paper trading stack.",
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


@app.get("/favicon.ico")
def favicon_root():
    """Browser default favicon probe."""
    path = _BACKEND_DIR / "static" / "favicon.ico"
    return Response(path.read_bytes(), media_type="image/x-icon")


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
