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
# missing% − ready% after severity lean (short-refuse / unmatched share Δ).
MISSING_VS_READY_DELTA_WIDE_PP = 20.0
MISSING_VS_READY_DELTA_THIN_PP = 10.0


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


def account_ledger_status(data_dir: Path | str, account_id: str = "") -> str:
    """Named-book portfolio status: ``ok`` / ``missing`` / ``damaged``.

    Absent ``portfolio.json`` → ``missing``. Unreadable / non-object JSON →
    ``damaged`` (xang1234 tolerate-missing + portfolio AI empty-vs-missing —
    corrupt must not read as a €0 reset). Legacy root → ``ok``. Display only.
    """
    aid = normalize_account_id(account_id)
    if not aid:
        return "ok"
    path = ledger_dir(data_dir, aid) / "portfolio.json"
    if not path.exists():
        return "missing"
    try:
        doc = json.loads(path.read_text() or "{}")
    except (OSError, json.JSONDecodeError, UnicodeError):
        return "damaged"
    if not isinstance(doc, dict):
        return "damaged"
    return "ok"


def account_ledger_missing(data_dir: Path | str, account_id: str = "") -> bool:
    """True when a named account has no usable ``portfolio.json``.

    Covers absent **and** corrupt/non-object files so €0 cash is not mistaken
    for a reset book (display only).
    """
    return account_ledger_status(data_dir, account_id) in {"missing", "damaged"}


def account_label(
    account_id: str = "",
    *,
    missing: bool = False,
    damaged: bool = False,
) -> str:
    aid = normalize_account_id(account_id)
    if not aid:
        return "paper · legacy root"
    if damaged:
        return f"paper · account {aid} · damaged ledger"
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


def _load_portfolio(path: Path) -> tuple[dict[str, Any], str]:
    """Load portfolio JSON; status is ``ok`` / ``missing`` / ``damaged``."""
    if not path.exists():
        return {}, "missing"
    try:
        doc = json.loads(path.read_text() or "{}")
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}, "damaged"
    if not isinstance(doc, dict):
        return {}, "damaged"
    return doc, "ok"


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
    portfolio, file_status = _load_portfolio(ledger / "portfolio.json")
    # Named books: absent or corrupt portfolio ≠ €0 reset / race loser.
    if aid and file_status in {"missing", "damaged"}:
        status = file_status
    else:
        status = "ok"
    unusable = status in {"missing", "damaged"}
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
    return {
        "account_id": aid,
        "label": account_label(
            aid, missing=status == "missing", damaged=status == "damaged"
        ),
        "path": str(ledger),
        "missing": unusable,
        "ledger_status": status,
        "cash": 0.0 if unusable else cash,
        "fees": 0.0 if unusable else fees,
        "initial": 0.0 if unusable else initial,
        "equity_cost": 0.0 if unusable else cash + cost,
        "open_positions": 0 if unusable else open_n,
        "last_trade_at": "" if unusable else last_trade,
        "last_trade_age": "" if unusable else _age_label(last_trade, now=now),
        "price_coverage": status if unusable else "cost",
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


def leaderboard_missing_vs_ready_lean(
    missing_severity: str,
    ready_severity: str,
) -> tuple[str, bool]:
    """Lean agreement of missing vs ready share bands (display only).

    Absolute sides + ownership lead + lead size hid whether the two
    *severity* bands agree (short-refuse vs long lean / unmatched vs matched
    lean + portfolio AI speak-both-sides + xang1234 severity). Align when
    ``hot|thin`` or ``quiet|strong``; clash when exactly one lean spoke or
    the pair disagrees. Adverse clash (missing hot / ready thin mismatch,
    or sole hot/thin) warns. Mid both silent. Lives under the Overview
    missing lean fold. Not a new entry gate.
    """
    miss = str(missing_severity or "").strip().casefold()
    ready = str(ready_severity or "").strip().casefold()
    miss_lean = miss in {"hot", "quiet"}
    ready_lean = ready in {"strong", "thin"}
    if miss_lean and ready_lean:
        matched = (miss == "hot" and ready == "thin") or (
            miss == "quiet" and ready == "strong"
        )
        if matched:
            return f"missing vs ready align · {miss}|{ready}", False
        return (
            f"missing vs ready clash · missing {miss} · ready {ready}",
            True,
        )
    if miss_lean != ready_lean:
        miss_label = miss if miss_lean else (miss or "ok")
        ready_label = ready if ready_lean else (ready or "ok")
        warn = miss == "hot" or ready == "thin"
        return (
            f"missing vs ready clash · missing {miss_label} · ready {ready_label}",
            warn,
        )
    return "", False


def leaderboard_missing_vs_ready_delta(
    missing_share_pct: float | int | None,
    ready_share_pct: float | int | None,
    *,
    lean_bit: str = "",
    wide_pp: float = MISSING_VS_READY_DELTA_WIDE_PP,
    thin_pp: float = MISSING_VS_READY_DELTA_THIN_PP,
) -> tuple[int | None, str, str, bool]:
    """Share Δ after missing vs ready severity lean (display only).

    Lean alone hid how far ``missing% − ready%`` sits (short-refuse vs long
    share Δ / unmatched vs matched share Δ + portfolio AI count≠spread +
    xang1234 severity). Requires lean already spoke. Wide ≥``wide_pp`` ·
    thin <``thin_pp`` · mid → ``lean vs Δ clash · lean · Δ mid`` (warn).
    Adverse ``align · hot|thin`` + Δ wide warns; ``quiet|strong`` stays
    calm.

    Returns ``(delta_pp, delta_severity, lean_vs_delta, lean_vs_delta_warn)``.
    Not a new entry gate.
    """
    if not str(lean_bit or "").strip():
        return None, "", "", False
    if missing_share_pct is None or ready_share_pct is None:
        return None, "", "", False
    try:
        miss = float(missing_share_pct)
        ready = float(ready_share_pct)
    except (TypeError, ValueError):
        return None, "", "", False
    raw = int(round(miss - ready))
    abs_delta = abs(raw)
    delta_sev = ""
    if abs_delta >= wide_pp:
        delta_sev = "wide"
    elif abs_delta < thin_pp:
        delta_sev = "thin"
    if delta_sev:
        lean_vs_delta = f"align · {delta_sev}"
        lean_vs_delta_warn = delta_sev == "wide" and str(lean_bit).startswith(
            "missing vs ready align · hot|thin"
        )
        return raw, delta_sev, lean_vs_delta, lean_vs_delta_warn
    return raw, "", "clash · lean · Δ mid", True


def leaderboard_missing_vs_ready_delta_lead(
    delta_pp: int | None,
    delta_severity: str,
    *,
    lean_vs_delta: str = "",
) -> str:
    """Name which slot owns a spoken missing vs ready Δ (display only).

    When lean vs Δ already spoke with a Δ (wide|thin) and ±pp ≠ 0,
    positive ``missing% − ready%`` → ``missing``; negative → ``ready``.
    Mid-Δ clash / 0pp stay silent. Signed pp alone hid which race-board
    slot owns the spread (opportunity damaged vs ok / Screener unique vs
    dup Δ lead + portfolio AI speak-both-sides + xang1234). Returns
    ``missing|ready`` / ``\"\"``. Not a new entry gate.
    """
    if not str(lean_vs_delta or "").startswith("align ·"):
        return ""
    if str(delta_severity or "").strip().casefold() not in {"wide", "thin"}:
        return ""
    if delta_pp is None:
        return ""
    try:
        pp = int(delta_pp)
    except (TypeError, ValueError):
        return ""
    if pp == 0:
        return ""
    return "missing" if pp > 0 else "ready"


def leaderboard_missing_vs_ready_delta_lead_size(
    missing_share_pct: float | int | None,
    ready_share_pct: float | int | None,
    *,
    delta_lead: str = "",
) -> tuple[float | None, float | None, float | None]:
    """How many times louder owns quieter after Δ lead (display only).

    When ``delta_lead`` already spoke (``missing|ready``) and both shares
    are known, ``Δ lead size · N×`` is louder%÷quieter%; zero quieter
    (all-missing) stays silent. Lead name ≠ magnitude (short-refuse vs
    long / unmatched vs matched / opportunity damaged vs ok Δ lead size
    + portfolio AI count≠share + xang1234). Returns
    ``(size, louder_pct, quieter_pct)`` or ``(None, None, None)``. Not a
    new entry gate.
    """
    if str(delta_lead or "").strip().casefold() not in {"missing", "ready"}:
        return None, None, None
    if missing_share_pct is None or ready_share_pct is None:
        return None, None, None
    try:
        miss = float(missing_share_pct)
        ready = float(ready_share_pct)
    except (TypeError, ValueError):
        return None, None, None
    louder = max(miss, ready)
    quieter = min(miss, ready)
    if quieter <= 0:
        return None, None, None
    return round(louder / quieter, 2), louder, quieter


def _leaderboard_unusable_noun(n_absent: int, n_damaged: int) -> str:
    """Speak absent vs damaged mix on the race strip (display only).

    Portfolio AI empty-vs-missing + xang1234 tolerate-missing: a corrupt
    ``portfolio.json`` must not read as a bare empty shell on the share bit.
    """
    absent = max(0, int(n_absent))
    damaged = max(0, int(n_damaged))
    if damaged <= 0:
        return f"{absent} missing"
    if absent <= 0:
        return f"{damaged} damaged"
    return f"{absent} missing · {damaged} damaged"


def leaderboard_absent_vs_damaged_lead(
    n_absent: int,
    n_damaged: int,
) -> tuple[str, str, int | None]:
    """Strict lead among empty-shell vs corrupt unusable books (display only).

    Absolute ``N missing · M damaged`` hid which unusable kind owns the race
    board (postmortem skip-reason lead + portfolio AI count≠share + xang1234).
    Both sides must be >0 and total ≥2; strict lead → ``lead absent|damaged ·
    N%``; ties / sole-side → silent (use
    ``leaderboard_absent_vs_damaged_sample_gap``). Uses ``absent`` (not
    ``missing``) so the bit stays distinct from ``lead missing|ready``.
    Not a new entry gate.
    """
    try:
        absent = max(0, int(n_absent))
    except (TypeError, ValueError):
        absent = 0
    try:
        damaged = max(0, int(n_damaged))
    except (TypeError, ValueError):
        damaged = 0
    total = absent + damaged
    if total < 2 or absent <= 0 or damaged <= 0 or absent == damaged:
        return "", "", None
    if absent > damaged:
        name, n = "absent", absent
    else:
        name, n = "damaged", damaged
    share = int(round(100.0 * n / total))
    return f"lead {name} · {share}%", name, share


def leaderboard_absent_vs_damaged_sample_gap(
    n_absent: int,
    n_damaged: int,
) -> str:
    """Speak ``absent/damaged tied`` when both unusable kinds spoke with no lead.

    Lead / sole-side / zero stay silent. Display only.
    """
    try:
        absent = max(0, int(n_absent))
    except (TypeError, ValueError):
        absent = 0
    try:
        damaged = max(0, int(n_damaged))
    except (TypeError, ValueError):
        damaged = 0
    if absent <= 0 or damaged <= 0:
        return ""
    lead_bit, _name, _share = leaderboard_absent_vs_damaged_lead(
        absent, damaged
    )
    if lead_bit:
        return ""
    return "absent/damaged tied"


def leaderboard_absent_vs_damaged_lead_size(
    n_absent: int,
    n_damaged: int,
    *,
    lead_name: str = "",
) -> tuple[float | None, int | None, int | None]:
    """How many times louder owns quieter after absent/damaged lead (display).

    When ``lead_name`` already spoke (``absent|damaged``) and both counts are
    >0, ``mix size · N×`` is louder÷quieter; zero quieter stays silent. Lead
    name/% ≠ magnitude (postmortem skip-reason lead size + missing vs ready
    lead size + portfolio AI count≠share + xang1234). Returns
    ``(size, louder_n, quieter_n)`` or all-None. Not a new entry gate.
    """
    if str(lead_name or "").strip().casefold() not in {"absent", "damaged"}:
        return None, None, None
    try:
        absent_n = max(0, int(n_absent))
    except (TypeError, ValueError):
        absent_n = 0
    try:
        damaged_n = max(0, int(n_damaged))
    except (TypeError, ValueError):
        damaged_n = 0
    quieter = min(absent_n, damaged_n)
    louder = max(absent_n, damaged_n)
    if quieter <= 0:
        return None, None, None
    return round(louder / quieter, 2), louder, quieter


def leaderboard_absent_vs_damaged_share_bands(
    n_absent: int,
    n_damaged: int,
    *,
    hot: float = MISSING_SHARE_HOT,
    quiet: float = MISSING_SHARE_QUIET,
) -> tuple[float | None, str, float | None, str]:
    """Per-kind ownership of the unusable mix (display only).

    Absolute mix + lead + mix size hid whether empty-shell vs corrupt *share*
    of unusable is extreme (postmortem skip-reason share bands + portfolio AI
    count≠share + xang1234). Both sides must be >0; sole-side / zero → silent.
    Returns ``(absent_pct, absent_sev, damaged_pct, damaged_sev)`` with
    ``hot|quiet|\"\"`` severities. Not a new entry gate.
    """
    try:
        absent = max(0, int(n_absent))
    except (TypeError, ValueError):
        absent = 0
    try:
        damaged = max(0, int(n_damaged))
    except (TypeError, ValueError):
        damaged = 0
    total = absent + damaged
    if total <= 0 or absent <= 0 or damaged <= 0:
        return None, "", None, ""
    absent_pct = round(100.0 * absent / total)
    damaged_pct = round(100.0 * damaged / total)

    def _sev(pct: float) -> str:
        if pct >= hot:
            return "hot"
        if pct <= quiet:
            return "quiet"
        return ""

    return absent_pct, _sev(absent_pct), damaged_pct, _sev(damaged_pct)


def leaderboard_absent_vs_damaged_lean(
    absent_severity: str,
    damaged_severity: str,
) -> tuple[str, bool]:
    """Lean agreement of absent vs damaged mix-share bands (display only).

    Absolute mix + ownership lead + mix size hid whether the two *severity*
    bands agree (postmortem skip-reason lean / missing vs ready lean +
    portfolio AI speak-both-sides + xang1234 severity). Both sides use
    ``hot|quiet`` of unusable. Align when complementary ``hot|quiet`` /
    ``quiet|hot``; clash when exactly one lean spoke or both hot (e.g.
    50/50). Adverse clash (any ``hot``) warns. Mid both silent. Lives under
    the missing lean fold. Not a new entry gate.
    """
    a = str(absent_severity or "").strip().casefold()
    d = str(damaged_severity or "").strip().casefold()
    a_lean = a in {"hot", "quiet"}
    d_lean = d in {"hot", "quiet"}
    if a_lean and d_lean:
        complementary = (a == "hot" and d == "quiet") or (
            a == "quiet" and d == "hot"
        )
        if complementary:
            return f"absent vs damaged align · {a}|{d}", False
        return (
            f"absent vs damaged clash · absent {a} · damaged {d}",
            True,
        )
    if a_lean != d_lean:
        a_label = a if a_lean else (a or "ok")
        d_label = d if d_lean else (d or "ok")
        warn = a == "hot" or d == "hot"
        return (
            "absent vs damaged clash · absent "
            f"{a_label} · damaged {d_label}",
            warn,
        )
    return "", False


def leaderboard_missing_share(
    rows: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Named-account missing-ledger ownership (display only).

    Absolute ``N missing`` on a row ≠ most of the race board. Denominator is
    named accounts only (legacy root is never a missing shell). Silent when
    zero missing or no named books. Hot ≥50% · quiet ≤25% (mid % only).

    ``n_missing`` stays total unusable (absent + damaged) for ready/share
    math. When any damaged named book exists, primary ``bit`` speaks the
    absent/damaged mix (``N damaged`` alone, or ``N missing · M damaged``)
    so a corrupt ledger is not mistaken for an empty shell. When both
    absent + damaged counts are >0, lean also speaks mix ownership
    ``lead absent|damaged · N%`` or ``absent/damaged tied`` (sole-side
    silent; ``absent`` ≠ race-board ``lead missing|ready``) so absolute
    mix alone does not hide which unusable kind owns the board. When mix
    ownership lead already spoke and quieter count >0, also append
    ``mix size · N×`` + ``mix size sides · absent|damaged N ·
    damaged|absent M`` (louder slot first) so name/% ≠ magnitude and
    anonymous louder/quieter does not hide which unusable kind owns quieter.
    When both absent + damaged share severity bands already spoke, also
    append ``absent vs damaged align · hot|quiet`` / ``clash · absent hot ·
    damaged ok`` so sides/lead/size alone do not hide severity agreement
    (postmortem skip-reason lean parity).

    When missing already spoke, also fill ``lean`` with remaining ready books
    ``vs N ready · [strong|thin] · P%`` (strong ≥75% · thin <50%; all-missing
    ``vs 0 ready · thin · 0%``). When both missing + ready counts are >0,
    append ownership ``lead missing|ready · N%`` or ``missing/ready tied``
    (sole-side / all-missing silent). When ownership lead already spoke and
    quieter count >0, also append ``lead size · N×`` + ``lead size sides ·
    missing|ready N · ready|missing M`` (louder slot first; Yahoo named
    sides) so name/% ≠ magnitude and anonymous louder/quieter does not
    hide which race-board slot owns the count. When missing + ready
    severity bands already spoke, also append ``missing vs ready align ·
    hot|thin`` / ``quiet|strong`` or ``clash · missing hot · ready ok`` so
    sides/lead/size alone do not hide severity agreement. When severity lean
    already spoke, also append ``Δ wide|thin · ±Npp`` + ``lean vs Δ
    align|clash`` so lean alone does not hide missing%−ready% spread. When
    lean vs Δ already spoke with a non-zero Δ, also append ``Δ lead ·
    missing|ready`` so signed pp alone does not hide which slot owns the
    spread. When Δ lead already spoke and quieter% > 0, also append
    ``Δ lead size · N×`` + ``Δ lead size sides · missing|ready N% ·
    ready|missing M%`` (louder slot first) so lead name alone does not hide
    magnitude or which share owns quieter. Primary ``bit`` stays
    absolute+share so the Overview race strip stays short; lean lives
    under a details fold.
    """
    out: dict[str, Any] = {
        "n_named": 0,
        "n_missing": 0,
        "n_absent": 0,
        "n_damaged": 0,
        "n_ready": 0,
        "missing_share_pct": None,
        "missing_share_severity": "",
        "ready_share_pct": None,
        "ready_share_severity": "",
        "absent_vs_damaged_lead": "",
        "absent_vs_damaged_lead_name": "",
        "absent_vs_damaged_lead_pct": None,
        "absent_vs_damaged_sample_gap": "",
        "absent_vs_damaged_lead_size": None,
        "absent_vs_damaged_lead_size_louder": None,
        "absent_vs_damaged_lead_size_quieter": None,
        "absent_vs_damaged_absent_share_pct": None,
        "absent_vs_damaged_absent_severity": "",
        "absent_vs_damaged_damaged_share_pct": None,
        "absent_vs_damaged_damaged_severity": "",
        "absent_vs_damaged_lean": "",
        "absent_vs_damaged_lean_warn": False,
        "vs_ready_lead": "",
        "vs_ready_lead_name": "",
        "vs_ready_lead_pct": None,
        "vs_ready_sample_gap": "",
        "vs_ready_lead_size": None,
        "vs_ready_lead_size_louder": None,
        "vs_ready_lead_size_quieter": None,
        "vs_ready_lean": "",
        "vs_ready_lean_warn": False,
        "vs_ready_delta_pp": None,
        "vs_ready_delta_severity": "",
        "vs_ready_lean_vs_delta": "",
        "vs_ready_lean_vs_delta_warn": False,
        "vs_ready_delta_lead": "",
        "vs_ready_delta_lead_size": None,
        "vs_ready_delta_lead_size_louder": None,
        "vs_ready_delta_lead_size_quieter": None,
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
    n_damaged = sum(
        1 for r in named if str(r.get("ledger_status") or "") == "damaged"
    )
    n_absent = sum(
        1 for r in named if str(r.get("ledger_status") or "") == "missing"
    )
    # Rows without ledger_status still count as unusable via missing=True.
    if n_absent + n_damaged < n_missing:
        n_absent = n_missing - n_damaged
    n_ready = n_named - n_missing
    out["n_named"] = n_named
    out["n_missing"] = n_missing
    out["n_absent"] = n_absent
    out["n_damaged"] = n_damaged
    out["n_ready"] = n_ready
    if n_missing <= 0:
        return out
    pct = round(100.0 * n_missing / n_named, 1)
    out["missing_share_pct"] = pct
    noun = _leaderboard_unusable_noun(n_absent, n_damaged)
    if pct >= MISSING_SHARE_HOT:
        out["missing_share_severity"] = "hot"
        out["bit"] = f"{noun} · hot · {pct:g}%"
        out["warn"] = True
    elif pct <= MISSING_SHARE_QUIET:
        out["missing_share_severity"] = "quiet"
        out["bit"] = f"{noun} · quiet · {pct:g}%"
    else:
        out["missing_share_severity"] = "ok"
        out["bit"] = f"{noun} · {pct:g}%"

    ready_pct = round(100.0 * n_ready / n_named, 1)
    out["ready_share_pct"] = ready_pct
    lean_parts: list[str] = []
    meta_parts: list[str] = []
    mix_lead, mix_name, mix_pct = leaderboard_absent_vs_damaged_lead(
        n_absent, n_damaged
    )
    mix_gap = leaderboard_absent_vs_damaged_sample_gap(n_absent, n_damaged)
    out["absent_vs_damaged_lead"] = mix_lead
    out["absent_vs_damaged_lead_name"] = mix_name
    out["absent_vs_damaged_lead_pct"] = mix_pct
    out["absent_vs_damaged_sample_gap"] = mix_gap
    mix_own = mix_lead or mix_gap
    if mix_own:
        lean_parts.append(mix_own)
        meta_parts.append("absent/damaged")
    mix_size, mix_louder, mix_quieter = leaderboard_absent_vs_damaged_lead_size(
        n_absent, n_damaged, lead_name=mix_name
    )
    out["absent_vs_damaged_lead_size"] = mix_size
    out["absent_vs_damaged_lead_size_louder"] = mix_louder
    out["absent_vs_damaged_lead_size_quieter"] = mix_quieter
    if (
        mix_size is not None
        and mix_louder is not None
        and mix_quieter is not None
    ):
        mix_other = "damaged" if mix_name == "absent" else "absent"
        lean_parts.append(f"mix size · {mix_size:g}×")
        lean_parts.append(
            f"mix size sides · {mix_name} {mix_louder} · "
            f"{mix_other} {mix_quieter}"
        )
        meta_parts.append("mix size")
    (
        absent_mix_pct,
        absent_mix_sev,
        damaged_mix_pct,
        damaged_mix_sev,
    ) = leaderboard_absent_vs_damaged_share_bands(n_absent, n_damaged)
    out["absent_vs_damaged_absent_share_pct"] = absent_mix_pct
    out["absent_vs_damaged_absent_severity"] = absent_mix_sev
    out["absent_vs_damaged_damaged_share_pct"] = damaged_mix_pct
    out["absent_vs_damaged_damaged_severity"] = damaged_mix_sev
    mix_sev_bit, mix_sev_warn = leaderboard_absent_vs_damaged_lean(
        absent_mix_sev, damaged_mix_sev
    )
    out["absent_vs_damaged_lean"] = mix_sev_bit
    out["absent_vs_damaged_lean_warn"] = mix_sev_warn
    if mix_sev_bit:
        lean_parts.append(mix_sev_bit)
        meta_parts.append("mix severity")
        if mix_sev_warn:
            out["lean_warn"] = True
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
    meta_parts.append("vs ready")
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
        other = "ready" if lead_name == "missing" else "missing"
        lean_parts.append(f"lead size · {size:g}×")
        lean_parts.append(
            f"lead size sides · {lead_name} {louder} · {other} {quieter}"
        )
        meta_parts.append("size")
    sev_bit, sev_warn = leaderboard_missing_vs_ready_lean(
        out["missing_share_severity"],
        out["ready_share_severity"],
    )
    out["vs_ready_lean"] = sev_bit
    out["vs_ready_lean_warn"] = sev_warn
    if sev_bit:
        lean_parts.append(sev_bit)
        meta_parts.append("severity")
        if sev_warn:
            out["lean_warn"] = True
        (
            delta_pp,
            delta_sev,
            lean_vs_delta,
            lean_vs_delta_warn,
        ) = leaderboard_missing_vs_ready_delta(
            out["missing_share_pct"],
            out["ready_share_pct"],
            lean_bit=sev_bit,
        )
        out["vs_ready_delta_pp"] = delta_pp
        out["vs_ready_delta_severity"] = delta_sev
        out["vs_ready_lean_vs_delta"] = lean_vs_delta
        out["vs_ready_lean_vs_delta_warn"] = lean_vs_delta_warn
        if delta_sev and delta_pp is not None:
            sign = f"+{delta_pp}" if delta_pp > 0 else f"{delta_pp}"
            lean_parts.append(f"Δ {delta_sev} · {sign}pp")
            meta_parts.append("Δ")
        if lean_vs_delta:
            lean_parts.append(f"lean vs Δ {lean_vs_delta}")
            meta_parts.append("lean/Δ")
            if lean_vs_delta_warn:
                out["lean_warn"] = True
        delta_lead = leaderboard_missing_vs_ready_delta_lead(
            delta_pp,
            delta_sev,
            lean_vs_delta=lean_vs_delta,
        )
        out["vs_ready_delta_lead"] = delta_lead
        if delta_lead:
            lean_parts.append(f"Δ lead · {delta_lead}")
            meta_parts.append("Δ lead")
            d_size, d_louder, d_quieter = (
                leaderboard_missing_vs_ready_delta_lead_size(
                    out["missing_share_pct"],
                    out["ready_share_pct"],
                    delta_lead=delta_lead,
                )
            )
            out["vs_ready_delta_lead_size"] = d_size
            out["vs_ready_delta_lead_size_louder"] = d_louder
            out["vs_ready_delta_lead_size_quieter"] = d_quieter
            if (
                d_size is not None
                and d_louder is not None
                and d_quieter is not None
            ):
                d_other = "ready" if delta_lead == "missing" else "missing"
                lean_parts.append(f"Δ lead size · {d_size:g}×")
                lean_parts.append(
                    f"Δ lead size sides · {delta_lead} {d_louder:g}% · "
                    f"{d_other} {d_quieter:g}%"
                )
                meta_parts.append("Δ size")
    out["lean_meta"] = " · ".join(meta_parts)
    out["lean"] = " · ".join(lean_parts)
    return out


def account_switcher_options(data_dir: Path | str) -> list[dict[str, str]]:
    """Desk switcher entries: legacy root first, then named ids."""
    opts = [{"id": "", "label": "legacy root", "href_q": ""}]
    for aid in list_account_ids(data_dir):
        status = account_ledger_status(data_dir, aid)
        if status == "damaged":
            label = f"{aid} · damaged"
        elif status == "missing":
            label = f"{aid} · missing"
        else:
            label = aid
        opts.append(
            {
                "id": aid,
                "label": label,
                "href_q": f"?account={aid}",
                "missing": "1" if status in {"missing", "damaged"} else "",
                "ledger_status": status,
            }
        )
    return opts
