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
# Race-board ownership of empty shells (named accounts only; legacy excluded).
MISSING_SHARE_HOT = 50.0
MISSING_SHARE_QUIET = 25.0
# Remaining ready named books after missing share (short-refuse vs long).
READY_SHARE_STRONG = 75.0
READY_SHARE_THIN = 50.0


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


def leaderboard_missing_vs_ready_lead(
    n_missing: int,
    n_ready: int,
) -> tuple[str, str, int | None]:
    """Strict lead among missing vs ready named counts (display only).

    Absolute ``N missing`` beside ``vs M ready`` hid which slot owns the
    race board (short-refuse vs long lead + portfolio AI count≠share +
    xang1234 multi-meter). Both sides must be >0 and total ≥2; strict lead
    → ``lead missing · N%`` / ``lead ready · N%``; ties / sole-side → silent
    (use ``leaderboard_missing_vs_ready_sample_gap`` for ``missing/ready
    tied``). Not a new entry gate.
    """
    try:
        missing_n = max(0, int(n_missing))
    except (TypeError, ValueError):
        missing_n = 0
    try:
        ready_n = max(0, int(n_ready))
    except (TypeError, ValueError):
        ready_n = 0
    total = missing_n + ready_n
    if total < 2 or missing_n <= 0 or ready_n <= 0 or missing_n == ready_n:
        return "", "", None
    if missing_n > ready_n:
        name, n = "missing", missing_n
    else:
        name, n = "ready", ready_n
    share = int(round(100.0 * n / total))
    return f"lead {name} · {share}%", name, share


def leaderboard_missing_vs_ready_sample_gap(
    n_missing: int,
    n_ready: int,
) -> str:
    """Speak ``missing/ready tied`` when both sides spoke with no strict lead.

    Lead / sole-side / zero stay silent. Display only.
    """
    try:
        missing_n = max(0, int(n_missing))
    except (TypeError, ValueError):
        missing_n = 0
    try:
        ready_n = max(0, int(n_ready))
    except (TypeError, ValueError):
        ready_n = 0
    if missing_n <= 0 or ready_n <= 0:
        return ""
    lead_bit, _name, _share = leaderboard_missing_vs_ready_lead(
        missing_n, ready_n
    )
    if lead_bit:
        return ""
    return "missing/ready tied"


def leaderboard_missing_vs_ready_lead_size(
    n_missing: int,
    n_ready: int,
    *,
    lead_name: str = "",
) -> tuple[float | None, int | None, int | None]:
    """How many times louder owns quieter after missing/ready lead (display).

    When ``lead_name`` already spoke (``missing|ready``) and both counts are
    >0, ``lead size · N×`` is louder÷quieter; zero quieter stays silent.
    Lead name/% ≠ magnitude (short-refuse vs long lead size + portfolio AI
    count≠share + xang1234 multi-meter). Returns ``(size, louder_n,
    quieter_n)`` or all-None. Not a new entry gate.
    """
    if str(lead_name or "").strip().casefold() not in {"missing", "ready"}:
        return None, None, None
    try:
        missing_n = max(0, int(n_missing))
    except (TypeError, ValueError):
        missing_n = 0
    try:
        ready_n = max(0, int(n_ready))
    except (TypeError, ValueError):
        ready_n = 0
    quieter = min(missing_n, ready_n)
    louder = max(missing_n, ready_n)
    if quieter <= 0:
        return None, None, None
    return round(louder / quieter, 2), louder, quieter


def leaderboard_missing_share(
    rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Named-account missing-ledger ownership (display only).

    Absolute ``N missing`` on a row ≠ most of the race board. Denominator is
    named accounts only (legacy root is never a missing shell). Silent when
    zero missing or no named books. Hot ≥50% · quiet ≤25% (mid % only).

    When missing already spoke, also fill ``lean`` with remaining ready books
    ``vs N ready · [strong|thin] · P%`` (strong ≥75% · thin <50%; all-missing
    ``vs 0 ready · thin · 0%``). When both missing + ready counts are >0,
    append ownership ``lead missing|ready · N%`` or ``missing/ready tied``
    (sole-side / all-missing silent). When ownership lead already spoke and
    quieter count >0, also append ``lead size · N×`` + ``lead size sides ·
    louder N · quieter M`` so name/% ≠ magnitude. Primary ``bit`` stays
    absolute+share so the Overview race strip stays short; lean lives under
    a details fold.
    """
    out: dict[str, Any] = {
        "n_named": 0,
        "n_missing": 0,
        "n_ready": 0,
        "missing_share_pct": None,
        "missing_share_severity": "",
        "ready_share_pct": None,
        "ready_share_severity": "",
        "vs_ready_lead": "",
        "vs_ready_lead_name": "",
        "vs_ready_lead_pct": None,
        "vs_ready_sample_gap": "",
        "vs_ready_lead_size": None,
        "vs_ready_lead_size_louder": None,
        "vs_ready_lead_size_quieter": None,
        "bit": "",
        "lean": "",
        "lean_meta": "",
        "lean_warn": False,
        "warn": False,
    }
    named = [r for r in (rows or []) if str(r.get("account_id") or "")]
    n_named = len(named)
    if n_named <= 0:
        return out
    n_missing = sum(1 for r in named if r.get("missing"))
    n_ready = n_named - n_missing
    out["n_named"] = n_named
    out["n_missing"] = n_missing
    out["n_ready"] = n_ready
    if n_missing <= 0:
        return out
    pct = round(100.0 * n_missing / n_named, 1)
    out["missing_share_pct"] = pct
    if pct >= MISSING_SHARE_HOT:
        out["missing_share_severity"] = "hot"
        out["bit"] = f"{n_missing} missing · hot · {pct:g}%"
        out["warn"] = True
    elif pct <= MISSING_SHARE_QUIET:
        out["missing_share_severity"] = "quiet"
        out["bit"] = f"{n_missing} missing · quiet · {pct:g}%"
    else:
        out["missing_share_severity"] = "ok"
        out["bit"] = f"{n_missing} missing · {pct:g}%"

    ready_pct = round(100.0 * n_ready / n_named, 1)
    out["ready_share_pct"] = ready_pct
    lean_parts: list[str] = []
    if ready_pct >= READY_SHARE_STRONG:
        out["ready_share_severity"] = "strong"
        lean_parts.append(f"vs {n_ready} ready · strong · {ready_pct:g}%")
    elif ready_pct < READY_SHARE_THIN:
        out["ready_share_severity"] = "thin"
        lean_parts.append(f"vs {n_ready} ready · thin · {ready_pct:g}%")
        out["lean_warn"] = True
    else:
        out["ready_share_severity"] = "ok"
        lean_parts.append(f"vs {n_ready} ready · {ready_pct:g}%")

    lead_bit, lead_name, lead_pct = leaderboard_missing_vs_ready_lead(
        n_missing, n_ready
    )
    sample_gap = leaderboard_missing_vs_ready_sample_gap(n_missing, n_ready)
    out["vs_ready_lead"] = lead_bit
    out["vs_ready_lead_name"] = lead_name
    out["vs_ready_lead_pct"] = lead_pct
    out["vs_ready_sample_gap"] = sample_gap
    own = lead_bit or sample_gap
    meta_parts = ["vs ready"]
    if own:
        lean_parts.append(own)
        meta_parts.append("ownership")
    size, louder, quieter = leaderboard_missing_vs_ready_lead_size(
        n_missing, n_ready, lead_name=lead_name
    )
    out["vs_ready_lead_size"] = size
    out["vs_ready_lead_size_louder"] = louder
    out["vs_ready_lead_size_quieter"] = quieter
    if size is not None and louder is not None and quieter is not None:
        lean_parts.append(f"lead size · {size:g}×")
        lean_parts.append(f"lead size sides · louder {louder} · quieter {quieter}")
        meta_parts.append("size")
    out["lean_meta"] = " · ".join(meta_parts)
    out["lean"] = " · ".join(lean_parts)
    return out


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
