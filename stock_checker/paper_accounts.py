"""Optional named paper ledgers for friend competition (GitHub #4 Mode A).

Ledger-only isolation under ``data/accounts/<id>/``. Scan archives and Ops
knobs stay on the shared ``DATA_DIR`` root. Display / scripts only — not a
new entry gate.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ACCOUNT_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
MAX_ACCOUNTS = 8
DEFAULT_STARTING_CAPITAL = 100_000.0
SHARED_DESK_ACCOUNT_ID = "desk"


class AccountIdError(ValueError):
    """Invalid or disallowed paper account id."""


def normalize_account_id(raw: str | None) -> str:
    """Return validated account id, or ``\"\"`` for the legacy root book."""
    text = str(raw or "").strip().lower()
    if not text:
        return ""
    if not ACCOUNT_ID_RE.fullmatch(text):
        raise AccountIdError(
            "account id must match [a-z][a-z0-9_-]{0,31} "
            f"(got {raw!r})"
        )
    return text


def ledger_dir(data_dir: Path | str, account_id: str = "") -> Path:
    """Portfolio/trades directory for an account (root when id is empty)."""
    root = Path(data_dir)
    aid = normalize_account_id(account_id)
    if not aid:
        return root
    return root / "accounts" / aid


def accounts_root(data_dir: Path | str) -> Path:
    return Path(data_dir) / "accounts"


def list_account_ids(data_dir: Path | str) -> list[str]:
    """Named accounts that already have a ledger directory."""
    root = accounts_root(data_dir)
    if not root.is_dir():
        return []
    out: list[str] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        try:
            aid = normalize_account_id(child.name)
        except AccountIdError:
            continue
        if aid:
            out.append(aid)
    return out


def account_ledger_missing(data_dir: Path | str, account_id: str = "") -> bool:
    """True when a named account is selected but ``portfolio.json`` is absent.

    Empty €0 cash without this flag reads like a real reset book — friends
    need the missing-ledger speak (display only).
    """
    aid = normalize_account_id(account_id)
    if not aid:
        return False
    return not (ledger_dir(data_dir, aid) / "portfolio.json").exists()


def account_label(account_id: str = "", *, missing: bool = False) -> str:
    aid = normalize_account_id(account_id)
    if not aid:
        return "paper · legacy root"
    if missing:
        return f"paper · account {aid} · missing ledger"
    return f"paper · account {aid}"


def ensure_account_ledger(data_dir: Path | str, account_id: str) -> Path:
    """Create ``accounts/<id>/`` when missing; enforce max named accounts."""
    aid = normalize_account_id(account_id)
    if not aid:
        raise AccountIdError("named account id required")
    existing = list_account_ids(data_dir)
    target = ledger_dir(data_dir, aid)
    if aid not in existing and len(existing) >= MAX_ACCOUNTS:
        raise AccountIdError(
            f"max {MAX_ACCOUNTS} named accounts on one host "
            f"(have {len(existing)})"
        )
    target.mkdir(parents=True, exist_ok=True)
    return target


def _load_portfolio(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        doc = json.loads(path.read_text() or "{}")
    except (OSError, json.JSONDecodeError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _last_trade_at(trades_path: Path) -> str:
    if not trades_path.exists():
        return ""
    last = ""
    try:
        with trades_path.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = str(row.get("timestamp") or "").strip()
                if ts:
                    last = ts
    except OSError:
        return ""
    return last


def _age_label(ts: str, *, now: datetime | None = None) -> str:
    if not ts:
        return ""
    text = ts
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    age_h = max(0.0, (now - dt.astimezone(timezone.utc)).total_seconds() / 3600.0)
    if age_h < 1:
        return f"{int(age_h * 60)}m ago"
    if age_h < 48:
        return f"{age_h:.0f}h ago"
    return f"{age_h / 24.0:.0f}d ago"


def ledger_summary(
    data_dir: Path | str,
    account_id: str = "",
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Offline book row for leaderboard (cost-basis equity; no live marks)."""
    aid = normalize_account_id(account_id)
    ledger = ledger_dir(data_dir, aid)
    portfolio = _load_portfolio(ledger / "portfolio.json")
    holdings = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}
    if not isinstance(holdings, dict):
        holdings = {}
    if not isinstance(avg, dict):
        avg = {}
    cash = float(portfolio.get("cash") or 0)
    fees = float(portfolio.get("total_fees_paid") or 0)
    initial = float(portfolio.get("initial_cash") or 0)
    cost = 0.0
    open_n = 0
    for sym, qty in holdings.items():
        try:
            q = float(qty)
        except (TypeError, ValueError):
            continue
        if q <= 0:
            continue
        open_n += 1
        try:
            px = float(avg.get(sym) or 0)
        except (TypeError, ValueError):
            px = 0.0
        cost += q * px
    last_trade = _last_trade_at(ledger / "trades.jsonl")
    # Named dir without portfolio.json is not a €0 reset — keep numbers at 0
    # but flag missing so leaderboard/CLI do not rank empty shells as losers.
    missing = bool(aid) and not (ledger / "portfolio.json").exists()
    return {
        "account_id": aid,
        "label": account_label(aid, missing=missing),
        "path": str(ledger),
        "missing": missing,
        "cash": 0.0 if missing else cash,
        "fees": 0.0 if missing else fees,
        "initial": 0.0 if missing else initial,
        "equity_cost": 0.0 if missing else cash + cost,
        "open_positions": 0 if missing else open_n,
        "last_trade_at": "" if missing else last_trade,
        "last_trade_age": "" if missing else _age_label(last_trade, now=now),
        "price_coverage": "missing" if missing else "cost",
    }


def build_leaderboard(
    data_dir: Path | str,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Legacy root + named accounts, sorted by cost-basis equity desc.

    Missing ledgers sort last so empty dirs do not look like race losers.
    """
    rows = [ledger_summary(data_dir, "", now=now)]
    for aid in list_account_ids(data_dir):
        rows.append(ledger_summary(data_dir, aid, now=now))
    rows.sort(
        key=lambda r: (
            1 if r.get("missing") else 0,
            -float(r.get("equity_cost") or 0),
        )
    )
    return rows


def account_switcher_options(data_dir: Path | str) -> list[dict[str, str]]:
    """Desk switcher entries: legacy root first, then named ids."""
    opts = [{"id": "", "label": "legacy root", "href_q": ""}]
    for aid in list_account_ids(data_dir):
        missing = account_ledger_missing(data_dir, aid)
        label = f"{aid} · missing" if missing else aid
        opts.append(
            {
                "id": aid,
                "label": label,
                "href_q": f"?account={aid}",
                "missing": "1" if missing else "",
            }
        )
    return opts
