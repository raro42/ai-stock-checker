"""Shared soft-gate logging (fail-open visibility — review A5).

Prints soft-allows and keeps a short desk-readable ring buffer under data/.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOFT_ALLOW_FILE = "gate_soft_allows.json"
SOFT_ALLOW_CAP = 40
# tradermonty #437: soft-allows older than this are expired diagnostics.
SOFT_ALLOW_FRESH_HOURS = 24.0
# xang1234 / RyanJHamby scan-age triad: aging before expired (display only).
SOFT_ALLOW_AGING_HOURS = 12.0
_SOFT_MARKERS = (
    "unknown",
    "no bars",
    "skip_no_bars",
    "insufficient",
    "empty yahoo",
    "empty earnings",
    "malformed yahoo",
    "anchor gap",  # xang1234 #539 RS positional miss >25%
)


def _default_data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "data"))


def soft_allow_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / SOFT_ALLOW_FILE


def is_soft_allow_reason(reason: str) -> bool:
    r = (reason or "").lower()
    return any(m in r for m in _SOFT_MARKERS)


# Anchor-gap ownership of the soft-allow ring (gap÷rows). Same hot/quiet
# floors as Screener junk share — absolute ``N gap`` ≠ ring share.
SOFT_ALLOW_ANCHOR_GAP_SHARE_HOT = 50.0
SOFT_ALLOW_ANCHOR_GAP_SHARE_QUIET = 25.0
# Non-gap remainder (other÷rows). Same strong/thin floors as Screener ok
# share — gap% alone hid usable fail-opens that are not anchor-gap.
SOFT_ALLOW_OTHER_SHARE_STRONG = 75.0
SOFT_ALLOW_OTHER_SHARE_THIN = 50.0


def soft_allow_anchor_gap_count(
    events: list[dict[str, Any]] | None,
) -> int:
    """Count soft-allows whose reason is an RS anchor-gap fail-open.

    Gate tallies only say ``rs×N`` — bare ``RS unknown`` and
    ``RS unknown — anchor gap — allow`` look the same. xang1234 #539
    rejects compressed-window RS; desk should speak how many ring rows
    are gappy-anchor fail-opens (display only; zero stays silent).
    """
    n = 0
    for row in events or []:
        if not isinstance(row, dict):
            continue
        if "anchor gap" in str(row.get("reason") or "").casefold():
            n += 1
    return n


def _anchor_gap_symbol(reason: str) -> str:
    """First token of an anchor-gap reason (asset / bench label)."""
    text = str(reason or "").strip()
    if "anchor gap" not in text.casefold():
        return ""
    tok = text.split(None, 1)[0] if text else ""
    if tok and tok.lower() not in {"rs", "unknown", "—", "-"}:
        return tok
    return ""


def soft_allow_anchor_gap_last_symbol(
    events: list[dict[str, Any]] | None,
) -> str:
    """Newest anchor-gap row's ticker/label (display only).

    Absolute ``N gap`` + lean hid which name last failed open on a
    gappy RS window. Reasons look like ``AAPL RS unknown — anchor gap
    — allow`` / ``SPY RS unknown — anchor gap — allow`` — first token
    is the asset or bench label. Ring order is newest-first. xang1234
    #546 resume-cursor honesty + FinRobot last-row; zero / unparseable
    silent.
    """
    for row in events or []:
        if not isinstance(row, dict):
            continue
        sym = _anchor_gap_symbol(str(row.get("reason") or ""))
        if sym:
            return sym
    return ""


def soft_allow_anchor_gap_last_freshness(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> str:
    """Freshness band of the newest parseable gap row (display only).

    ``last SYM`` alone ≠ whether that gappy fail-open is still live.
    Speaks ``fresh`` / ``aging`` / ``expired`` from enriched
    ``freshness`` or ``at`` (RyanJHamby + xang1234 soft-allow triad +
    FinRobot last-row age). Missing / unknown stamp stays silent —
    cursor name still speaks. Not a gate.
    """
    for row in events or []:
        if not isinstance(row, dict):
            continue
        if not _anchor_gap_symbol(str(row.get("reason") or "")):
            continue
        band = str(row.get("freshness") or "").strip().casefold()
        if band in {"fresh", "aging", "expired"}:
            return band
        if band == "unknown":
            return ""
        computed = soft_allow_freshness(row.get("at"), now=now)
        if computed in {"fresh", "aging", "expired"}:
            return computed
        return ""
    return ""


def _anchor_gap_symbol_counts(
    events: list[dict[str, Any]] | None,
) -> dict[str, int]:
    """Parseable gap-symbol tallies (newest-first ring; display only)."""
    counts: dict[str, int] = {}
    for row in events or []:
        if not isinstance(row, dict):
            continue
        sym = _anchor_gap_symbol(str(row.get("reason") or ""))
        if not sym:
            continue
        counts[sym] = counts.get(sym, 0) + 1
    return counts


def soft_allow_anchor_gap_symbol_lead(
    events: list[dict[str, Any]] | None,
) -> tuple[str, str, int | None]:
    """Strict lead among parseable gap symbols (display only).

    Returns ``(lead_bit, lead_name, share_pct)``. ``last SYM`` alone ≠
    which name owns the gap fail-open ring. When ≥2 parseable gap
    symbols and one is strictly largest, speak ``lead AAPL · N%``
    (share of parseable gap rows). Ties / sole-symbol / <2 parseable
    stay silent on lead (use ``soft_allow_anchor_gap_symbol_sample_gap``).
    Screener junk-list lead + xang1234 multi-meter + portfolio AI
    count≠share after last-cursor.
    """
    counts = _anchor_gap_symbol_counts(events)
    total = sum(counts.values())
    if total < 2:
        return "", "", None
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    lead_name, lead_n = ranked[0]
    if lead_n <= 0:
        return "", "", None
    if len(ranked) > 1 and ranked[1][1] == lead_n:
        return "", "", None
    share = int(round(100.0 * lead_n / total))
    return f"lead {lead_name} · {share}%", lead_name, share


def soft_allow_anchor_gap_symbol_lead_margin(
    events: list[dict[str, Any]] | None,
) -> tuple[str, int, str] | None:
    """Lead share plus margin over #2 gap symbol (display only).

    Returns ``(ahead_bit, margin, severity)``. Ownership % ≠ how far
    ahead. Speaks only when symbol lead already spoke **and** a
    runner-up name exists (sole 100% omits ahead). Severity: ``wide``
    when margin ≥ ``SOFT_ALLOW_LEAD_MARGIN_WIDE``, else ``thin``. Soft
    gate-lead margin + Screener junk-list lead + portfolio AI after
    lead %. Not a gate.
    """
    lead_bit, _name, _share = soft_allow_anchor_gap_symbol_lead(events)
    if not lead_bit:
        return None
    counts = _anchor_gap_symbol_counts(events)
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    if len(ranked) < 2:
        return None
    margin = int(ranked[0][1]) - int(ranked[1][1])
    if margin < 1:
        return None
    severity = "wide" if margin >= SOFT_ALLOW_LEAD_MARGIN_WIDE else "thin"
    return f"ahead {severity} · +{margin}", margin, severity


def soft_allow_anchor_gap_symbol_lead_sides(
    events: list[dict[str, Any]] | None,
) -> tuple[str, str, int, int] | None:
    """Lead margin plus runner-up gap symbol (display only).

    Returns ``(sides_bit, runner, runner_n, runner_share_pct)``. Ahead
    +K ≠ who is #2. Speaks when margin already spoke; runner share is
    runner÷parseable gap total (absolute count ≠ ownership). Soft
    gate-lead sides share + portfolio AI speak-both-sides. Not a gate.
    """
    margin = soft_allow_anchor_gap_symbol_lead_margin(events)
    if margin is None:
        return None
    counts = _anchor_gap_symbol_counts(events)
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    if len(ranked) < 2:
        return None
    total = sum(counts.values())
    if total <= 0:
        return None
    runner, runner_n = ranked[1]
    runner_share = int(round(100.0 * int(runner_n) / total))
    bit = f"vs {runner} · {runner_n} · {runner_share}%"
    return bit, str(runner), int(runner_n), runner_share


def soft_allow_anchor_gap_symbol_sample_gap(
    events: list[dict[str, Any]] | None,
) -> str:
    """Speak ``n=1`` / ``tied`` when parseable gap names have no lead.

    One parseable gap row speaks compact ``n=1`` (``last SYM`` alone ≠ a
    thin sample; soft-allow / LAYA ``_decision_sample_gap`` parity). ≥2
    with no strict lead speaks ``tied``. Lead cases / zero stay silent
    on gap (not edge-band ``thin``). Silent sole hid that a single gap
    name is not a ring tilt. Display only.
    """
    counts = _anchor_gap_symbol_counts(events)
    total = sum(counts.values())
    if total <= 0:
        return ""
    lead_bit, _name, _share = soft_allow_anchor_gap_symbol_lead(events)
    if lead_bit:
        return ""
    if total < 2:
        return "n=1"
    return "tied"


def soft_allow_anchor_gap_symbol_last_vs_lead(
    events: list[dict[str, Any]] | None,
) -> str:
    """Newest gap ticker vs symbol lead (display only).

    ``last SYM`` + ``lead SYM · N%`` alone hid whether the resume cursor
    matches the ring owner. When lead already spoke: same name speaks
    ``agree``; different speaks ``last vs lead · MSFT``. Tied / no-lead /
    missing cursor stay silent. Reuses ``soft_allow_last_vs_lead``
    (gate lead parity). xang1234 #546 resume-cursor + FinRobot last≠ring
    tilt + portfolio AI speak-both-sides. Not a gate.
    """
    _bit, lead_name, _share = soft_allow_anchor_gap_symbol_lead(events)
    if not lead_name:
        return ""
    last = soft_allow_anchor_gap_last_symbol(events)
    return soft_allow_last_vs_lead(lead_name, last)


def soft_allow_anchor_gap_share(
    events: list[dict[str, Any]] | None,
) -> tuple[int, float | None, str]:
    """Anchor-gap count + ring share + severity (display only).

    Returns ``(count, share_pct, severity)``. Zero gaps →
    ``(0, None, "")``. Share is gap÷Mapping-rows; hot ≥50% · quiet ≤25% ·
    mid ``ok`` (portfolio AI count≠share after absolute ``N gap``;
    xang1234 #539 reject-anchor-gap).
    """
    rows = [r for r in (events or []) if isinstance(r, dict)]
    gap_n = soft_allow_anchor_gap_count(rows)
    if gap_n <= 0 or not rows:
        return 0, None, ""
    share = round(100.0 * gap_n / len(rows), 1)
    if share >= SOFT_ALLOW_ANCHOR_GAP_SHARE_HOT:
        severity = "hot"
    elif share <= SOFT_ALLOW_ANCHOR_GAP_SHARE_QUIET:
        severity = "quiet"
    else:
        severity = "ok"
    return gap_n, share, severity


def soft_allow_anchor_gap_vs_other(
    events: list[dict[str, Any]] | None,
) -> tuple[int, float | None, str]:
    """Non-gap remainder when gap already spoke (display only).

    Returns ``(other_n, share_pct, severity)``. No gaps →
    ``(0, None, "")``. Other = Mapping-rows − gap; strong ≥75% ·
    thin <50% · mid ``ok``. All-gap → ``(0, 0.0, "thin")`` — Screener
    junk vs ok sides parity after gap% alone hid usable ring rows
    (portfolio AI speak-both-sides; xang1234 #539).
    """
    rows = [r for r in (events or []) if isinstance(r, dict)]
    gap_n = soft_allow_anchor_gap_count(rows)
    if gap_n <= 0 or not rows:
        return 0, None, ""
    other_n = len(rows) - gap_n
    share = round(100.0 * other_n / len(rows), 1)
    if share >= SOFT_ALLOW_OTHER_SHARE_STRONG:
        severity = "strong"
    elif share < SOFT_ALLOW_OTHER_SHARE_THIN:
        severity = "thin"
    else:
        severity = "ok"
    return other_n, share, severity


def soft_allow_anchor_gap_vs_other_lean(
    events: list[dict[str, Any]] | None,
) -> tuple[str, bool]:
    """Gap vs other lean when both sides already spoke (display only).

    Returns ``(lean_bit, warn)``. Silent when gap did not speak or both
    severities are mid. Screener ``junk_vs_ok`` parity: matched extremes
    speak ``align · hot|thin`` / ``quiet|strong``; mismatch or one-lean
    speaks ``clash · gap … · other …`` (warn when gap hot or other thin).
    Sides alone hid lean agreement (portfolio AI speak-both-sides).
    """
    gap_n, _gap_share, gap_sev = soft_allow_anchor_gap_share(events)
    other_n, other_share, other_sev = soft_allow_anchor_gap_vs_other(events)
    if gap_n <= 0 or other_share is None:
        return "", False
    gap_lean = gap_sev in {"hot", "quiet"}
    other_lean = other_sev in {"strong", "thin"}
    if gap_lean and other_lean:
        matched = (gap_sev == "hot" and other_sev == "thin") or (
            gap_sev == "quiet" and other_sev == "strong"
        )
        if matched:
            return f"align · {gap_sev}|{other_sev}", False
        return (
            f"clash · gap {gap_sev} · other {other_sev}",
            True,
        )
    if gap_lean != other_lean:
        warn = gap_sev == "hot" or other_sev == "thin"
        return (
            f"clash · gap {gap_sev} · other {other_sev}",
            warn,
        )
    return "", False


def soft_allow_anchor_gap_last_vs_share(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last gap freshness vs gap share lean (display only).

    Returns ``(bit, warn)``. Cursor age ≠ ownership heat. Extremes only:
    ``fresh``↔``hot`` and ``expired``↔``quiet`` speak ``align``; crossed
    pairs speak ``clash`` (warn). ``aging`` / mid share stay silent —
    RyanJHamby triad + FinRobot last-row age + portfolio AI
    speak-both-sides after last-freshness + share labels alone hid the
    relationship. Not a gate.
    """
    last_fresh = soft_allow_anchor_gap_last_freshness(events, now=now)
    gap_n, _share, severity = soft_allow_anchor_gap_share(events)
    if (
        gap_n <= 0
        or last_fresh not in {"fresh", "expired"}
        or severity not in {"hot", "quiet"}
    ):
        return "", False
    live_age = last_fresh == "fresh"
    hot_share = severity == "hot"
    if live_age == hot_share:
        return f"align · {last_fresh} · {severity}", False
    return f"clash · {last_fresh} · {severity}", True


def soft_allow_anchor_gap_last_vs_lean(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last gap freshness vs gap/other lean (display only).

    Returns ``(bit, warn)``. Cursor age ≠ lean agreement. Extremes only:
    ``fresh``↔ lean ``align`` and ``expired``↔ lean ``clash`` speak
    ``align``; crossed pairs speak ``clash`` (warn). ``aging`` / silent
    lean stay silent — RyanJHamby triad + FinRobot last-row age +
    portfolio AI speak-both-sides after last/share + lean labels alone
    hid the relationship. Not a gate.
    """
    last_fresh = soft_allow_anchor_gap_last_freshness(events, now=now)
    lean, _lean_warn = soft_allow_anchor_gap_vs_other_lean(events)
    if last_fresh not in {"fresh", "expired"} or not lean:
        return "", False
    if lean.startswith("align · "):
        lean_align = True
        lean_tail = lean[len("align · ") :]
    elif lean.startswith("clash · "):
        lean_align = False
        lean_tail = lean[len("clash · ") :]
    else:
        return "", False
    live_age = last_fresh == "fresh"
    if live_age == lean_align:
        return f"align · {last_fresh} · {lean_tail}", False
    return f"clash · {last_fresh} · {lean_tail}", True


def soft_allow_anchor_gap_last_share_vs_lean(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last/share vs last/lean relationship agreement (display only).

    Returns ``(bit, warn)``. Age↔share ≠ age↔lean. When both already
    spoke: same verb speaks ``align · both align|clash`` — ``both
    align`` stays calm; ``both clash`` warns (agreement that both
    relationships disagree ≠ quiet confirm). Crossed verbs speak
    ``clash · share align|clash · lean align|clash`` (warn). Missing
    either stays silent — FinRobot last-row age + portfolio AI
    speak-both-sides + RyanJHamby severity after last/share +
    last/lean alone hid whether the two relationships agree *and*
    whether dual-clash agreement is adverse. Not a gate.
    """
    share_bit, _ = soft_allow_anchor_gap_last_vs_share(events, now=now)
    lean_bit, _ = soft_allow_anchor_gap_last_vs_lean(events, now=now)
    if not share_bit or not lean_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    share_verb = _verb(share_bit)
    lean_verb = _verb(lean_bit)
    if share_verb is None or lean_verb is None:
        return "", False
    if share_verb == lean_verb:
        # Dual-clash agreement is adverse; dual-align is calm.
        return f"align · both {share_verb}", share_verb == "clash"
    return f"clash · share {share_verb} · lean {lean_verb}", True


def format_soft_allow_anchor_gap_bit(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> str:
    """Compact ``N gap · last SYM · fresh|aging|expired · lead|n=1|tied · …``.

    Zero silent. ``last SYM`` sits right after the count so a long lean
    cascade cannot clip the cursor (xang1234 #546). Cursor age
    (``fresh`` / ``aging`` / ``expired``) follows the name so a live
    ticker ≠ a live fail-open (RyanJHamby + soft-allow triad + FinRobot
    last-row age; unknown stamp silent). Symbol lead / n=1 / tied
    follows the cursor (last ≠ ring ownership; Screener junk-list lead
    + soft-allow sample honesty); when lead spoke, ``last vs lead`` /
    ``agree`` sits right after so the cursor≠owner clash is not clipped
    by share/lean (FinRobot last≠tilt); when a runner exists, ``ahead``
    + ``vs SYM`` follow so ownership % ≠ how far ahead ≠ who is #2
    (soft gate-lead margin/sides; sole 100% omits). Share severity
    follows; when last freshness + share lean already spoke, ``last/share
    align|clash`` sits right after so age ≠ ownership heat (portfolio AI
    speak-both-sides; clash warns). When gap/other lean already spoke,
    ``last/lean align|clash`` follows so age ≠ lean agreement. When both
    last/share and last/lean already spoke, ``share/lean align|clash``
    follows so the two relationships are not silent-confirm (``both
    clash`` warns; ``both align`` stays calm).
    """
    gap_n, share, severity = soft_allow_anchor_gap_share(events)
    if gap_n <= 0 or share is None:
        return ""
    last = soft_allow_anchor_gap_last_symbol(events)
    head = f"{gap_n} gap"
    if last:
        head = f"{head} · last {last}"
        last_fresh = soft_allow_anchor_gap_last_freshness(events, now=now)
        if last_fresh:
            head = f"{head} · {last_fresh}"
    lead_bit, _lead_name, _lead_share = soft_allow_anchor_gap_symbol_lead(
        events
    )
    if lead_bit:
        head = f"{head} · {lead_bit}"
        last_vs = soft_allow_anchor_gap_symbol_last_vs_lead(events)
        if last_vs:
            head = f"{head} · {last_vs}"
        margin = soft_allow_anchor_gap_symbol_lead_margin(events)
        if margin is not None:
            head = f"{head} · {margin[0]}"
            sides = soft_allow_anchor_gap_symbol_lead_sides(events)
            if sides is not None:
                head = f"{head} · {sides[0]}"
    else:
        sample_gap = soft_allow_anchor_gap_symbol_sample_gap(events)
        if sample_gap:
            head = f"{head} · {sample_gap}"
    if severity in {"hot", "quiet"}:
        bit = f"{head} · {severity} · {share:g}%"
    else:
        bit = f"{head} · {share:g}%"
    last_vs_share, _lvs_warn = soft_allow_anchor_gap_last_vs_share(
        events, now=now
    )
    if last_vs_share:
        bit = f"{bit} · last/share {last_vs_share}"
    other_n, other_share, other_sev = soft_allow_anchor_gap_vs_other(events)
    if other_share is None:
        return bit
    if other_sev in {"strong", "thin"}:
        other_bit = f"vs {other_n} other · {other_sev} · {other_share:g}%"
    else:
        other_bit = f"vs {other_n} other · {other_share:g}%"
    bit = f"{bit} · {other_bit}"
    lean, _warn = soft_allow_anchor_gap_vs_other_lean(events)
    if lean:
        bit = f"{bit} · gap vs other {lean}"
        last_vs_lean, _lvl_warn = soft_allow_anchor_gap_last_vs_lean(
            events, now=now
        )
        if last_vs_lean:
            bit = f"{bit} · last/lean {last_vs_lean}"
            share_vs_lean, _svl_warn = soft_allow_anchor_gap_last_share_vs_lean(
                events, now=now
            )
            if share_vs_lean:
                bit = f"{bit} · share/lean {share_vs_lean}"
    return bit


def load_soft_allows(data_dir: Path | str) -> list[dict[str, Any]]:
    path = soft_allow_path(data_dir)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    events = raw.get("events") if isinstance(raw, dict) else None
    if not isinstance(events, list):
        return []
    return [e for e in events if isinstance(e, dict)]


def recent_soft_allows(
    data_dir: Path | str, *, limit: int = 12
) -> list[dict[str, Any]]:
    """Newest-first soft-allows for Ops (display only)."""
    lim = max(0, int(limit))
    events = load_soft_allows(data_dir)
    return list(reversed(events[-lim:])) if lim else []


def parse_soft_allow_at(raw: Any) -> datetime | None:
    """Parse a soft-allow ``at`` stamp (UTC). Unknown shapes → None."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def soft_allow_age_hours(
    at: Any,
    *,
    now: datetime | None = None,
) -> float | None:
    """Hours since ``at``, or None when the stamp is missing/unparseable."""
    stamp = parse_soft_allow_at(at)
    if stamp is None:
        return None
    clock = now if now is not None else datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    else:
        clock = clock.astimezone(timezone.utc)
    return max(0.0, (clock - stamp).total_seconds() / 3600.0)


def soft_allow_is_expired(
    at: Any,
    *,
    now: datetime | None = None,
    fresh_hours: float = SOFT_ALLOW_FRESH_HOURS,
) -> bool:
    """True when age is known and older than ``fresh_hours``.

    Missing/unparseable ``at`` stays fresh (fail-open — do not hide the row).
    """
    age = soft_allow_age_hours(at, now=now)
    if age is None:
        return False
    return age > float(fresh_hours)


def soft_allow_freshness(
    at: Any,
    *,
    now: datetime | None = None,
    aging_hours: float = SOFT_ALLOW_AGING_HOURS,
    fresh_hours: float = SOFT_ALLOW_FRESH_HOURS,
) -> str:
    """fresh / aging / expired / unknown — scan-age triad for fail-open rows.

    Missing stamp → ``unknown`` (speak, do not hide). Not an entry gate.
    """
    age = soft_allow_age_hours(at, now=now)
    if age is None:
        return "unknown"
    aging = float(aging_hours)
    expire = float(fresh_hours)
    if expire < aging:
        expire = aging
    if age > expire:
        return "expired"
    if age > aging:
        return "aging"
    return "fresh"


def enrich_soft_allows(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
    fresh_hours: float = SOFT_ALLOW_FRESH_HOURS,
    aging_hours: float = SOFT_ALLOW_AGING_HOURS,
) -> list[dict[str, Any]]:
    """Copy rows with freshness + ``expired`` + ``age_hours`` (display only)."""
    out: list[dict[str, Any]] = []
    for row in events or []:
        if not isinstance(row, dict):
            continue
        copy = dict(row)
        age = soft_allow_age_hours(copy.get("at"), now=now)
        copy["age_hours"] = None if age is None else round(age, 2)
        band = soft_allow_freshness(
            copy.get("at"),
            now=now,
            aging_hours=aging_hours,
            fresh_hours=fresh_hours,
        )
        copy["freshness"] = band
        copy["expired"] = band == "expired"
        out.append(copy)
    return out


def soft_allow_band_tally(
    events: list[dict[str, Any]] | None,
    *,
    band: str,
) -> list[tuple[str, int]]:
    """Gate counts for one freshness band — sorted by count desc, then gate.

    ``band`` is ``fresh`` / ``aging`` / ``expired``. Expired also matches the
    legacy ``expired`` bool when ``freshness`` is missing. Fresh also matches
    ``unknown`` stamps (fail-open — same as glance ``fresh_count``).
    """
    want = str(band or "").strip().casefold()
    counts: dict[str, int] = {}
    for row in events or []:
        if not isinstance(row, dict):
            continue
        freshness = str(row.get("freshness") or "").strip().casefold()
        if not freshness and want == "expired" and row.get("expired"):
            freshness = "expired"
        if want == "fresh":
            if freshness not in ("fresh", "unknown"):
                continue
        elif freshness != want:
            continue
        gate = str(row.get("gate") or "?").strip() or "?"
        counts[gate] = counts.get(gate, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def format_soft_allow_band_tally(
    events: list[dict[str, Any]] | None,
    *,
    band: str,
) -> str:
    """Compact ``regime×2 · rs×1`` for one freshness band."""
    parts = [
        f"{gate}×{n}" for gate, n in soft_allow_band_tally(events, band=band)
    ]
    return " · ".join(parts)


def expired_soft_allow_tally(
    events: list[dict[str, Any]] | None,
) -> list[tuple[str, int]]:
    """Gate counts for expired rows only (tradermonty #437)."""
    return soft_allow_band_tally(events, band="expired")


def format_expired_soft_allow_tally(
    events: list[dict[str, Any]] | None,
) -> str:
    """Compact ``regime×2 · rs×1`` for expired soft-allows (tradermonty #437)."""
    return format_soft_allow_band_tally(events, band="expired")


def aging_soft_allow_tally(
    events: list[dict[str, Any]] | None,
) -> list[tuple[str, int]]:
    """Gate counts for aging rows only — speak-both-sides with expired tally."""
    return soft_allow_band_tally(events, band="aging")


def format_aging_soft_allow_tally(
    events: list[dict[str, Any]] | None,
) -> str:
    """Compact ``breadth×1 · rs×1`` for aging soft-allows (portfolio AI + xang1234)."""
    return format_soft_allow_band_tally(events, band="aging")


def fresh_soft_allow_tally(
    events: list[dict[str, Any]] | None,
) -> list[tuple[str, int]]:
    """Gate counts for fresh (+ unknown) rows — speak-both-sides with aging/expired."""
    return soft_allow_band_tally(events, band="fresh")


def format_fresh_soft_allow_tally(
    events: list[dict[str, Any]] | None,
) -> str:
    """Compact ``rs×1 · regime×1`` for fresh soft-allows (portfolio AI + xang1234)."""
    return format_soft_allow_band_tally(events, band="fresh")


def soft_allow_lead_gate(
    events: list[dict[str, Any]] | None,
    *,
    band: str,
    min_count: int = 2,
) -> tuple[str, int] | None:
    """Dominant gate in one freshness band (portfolio AI concentration).

    Speaks when the top gate reaches ``min_count`` and strictly leads #2
    (ties stay silent). One soft-allow ≠ concentration. Display only.
    """
    tally = soft_allow_band_tally(events, band=band)
    if not tally:
        return None
    gate, n = tally[0]
    if n < int(min_count):
        return None
    if len(tally) > 1 and tally[1][1] >= n:
        return None
    return gate, n


def soft_allow_lead_share(
    events: list[dict[str, Any]] | None,
    *,
    band: str,
    min_count: int = 2,
) -> tuple[str, int, float] | None:
    """Lead gate plus band ownership % (count ≠ share).

    Same speak rules as ``soft_allow_lead_gate``. Share is lead÷band total
    (portfolio AI + xang1234 after exit-lead %). Display only.
    """
    lead = soft_allow_lead_gate(events, band=band, min_count=min_count)
    if lead is None:
        return None
    gate, n = lead
    total = sum(c for _, c in soft_allow_band_tally(events, band=band))
    if total <= 0:
        return None
    return gate, n, round(100.0 * n / total, 1)


# Lead−#2 count gap: wide ≥2 · thin = 1 (sole-gate stays silent — no runner).
SOFT_ALLOW_LEAD_MARGIN_WIDE = 2


def soft_allow_lead_margin(
    events: list[dict[str, Any]] | None,
    *,
    band: str,
    min_count: int = 2,
) -> tuple[str, int, float, int, str] | None:
    """Lead share plus margin over #2 (share ≠ how far ahead).

    Same speak rules as ``soft_allow_lead_share``. Margin speaks only when a
    runner-up exists (sole 100% stays silent on ahead). Severity: ``wide`` when
    margin ≥ ``SOFT_ALLOW_LEAD_MARGIN_WIDE``, else ``thin``. Display only.
    """
    lead = soft_allow_lead_share(events, band=band, min_count=min_count)
    if lead is None:
        return None
    gate, n, pct = lead
    tally = soft_allow_band_tally(events, band=band)
    if len(tally) < 2:
        return None
    margin = int(n) - int(tally[1][1])
    if margin < 1:
        return None
    severity = "wide" if margin >= SOFT_ALLOW_LEAD_MARGIN_WIDE else "thin"
    return gate, n, pct, margin, severity


def soft_allow_lead_sides(
    events: list[dict[str, Any]] | None,
    *,
    band: str,
    min_count: int = 2,
) -> tuple[str, int, float, int, str, str, int] | None:
    """Lead margin plus runner-up gate×count (ahead ≠ who is #2).

    Same speak rules as ``soft_allow_lead_margin``. Absolute +K does not
    name the second gate — portfolio AI + xang1234 speak-both-sides after
    margin. Display only.
    """
    margin = soft_allow_lead_margin(events, band=band, min_count=min_count)
    if margin is None:
        return None
    gate, n, pct, gap, severity = margin
    tally = soft_allow_band_tally(events, band=band)
    if len(tally) < 2:
        return None
    runner_gate, runner_n = tally[1]
    return gate, n, pct, gap, severity, str(runner_gate), int(runner_n)


def soft_allow_lead_sides_share(
    events: list[dict[str, Any]] | None,
    *,
    band: str,
    min_count: int = 2,
) -> tuple[str, int, float, int, str, str, int, float] | None:
    """Lead sides plus runner band ownership % (×K ≠ share).

    Same speak rules as ``soft_allow_lead_sides``. Runner share is
    runner÷band total — portfolio AI + xang1234 after exit-€ sides share.
    Not lead÷runner (that ratio stays deferred). Display only.
    """
    sides = soft_allow_lead_sides(events, band=band, min_count=min_count)
    if sides is None:
        return None
    gate, n, pct, gap, severity, runner, runner_n = sides
    total = sum(c for _, c in soft_allow_band_tally(events, band=band))
    if total <= 0:
        return None
    return (
        gate,
        n,
        pct,
        gap,
        severity,
        runner,
        runner_n,
        round(100.0 * int(runner_n) / total, 1),
    )


# Lead% − runner% ownership spread (exit-€ share Δ bands): wide ≥20pp · thin <10pp.
SOFT_ALLOW_LEAD_SHARE_DELTA_WIDE_PP = 20.0
SOFT_ALLOW_LEAD_SHARE_DELTA_THIN_PP = 10.0


def _soft_allow_share_delta_lean(lead_pct: float, runner_pct: float) -> str | None:
    """Ownership Δ lean: ``wide`` / ``thin`` / ``mid``, or None when near-zero."""
    delta = float(lead_pct) - float(runner_pct)
    mag = abs(delta)
    if mag < 1e-9:
        return None
    if mag >= SOFT_ALLOW_LEAD_SHARE_DELTA_WIDE_PP:
        return "wide"
    if mag < SOFT_ALLOW_LEAD_SHARE_DELTA_THIN_PP:
        return "thin"
    return "mid"


def soft_allow_lead_sides_share_delta(
    events: list[dict[str, Any]] | None,
    *,
    band: str,
    min_count: int = 2,
) -> tuple[str, int, float, int, str, str, int, float, float, str] | None:
    """Lead/runner shares plus ownership Δ pp (two % ≠ the spread).

    Same speak rules as ``soft_allow_lead_sides_share``. Speaks only when
    |lead% − runner%| is wide (≥``SOFT_ALLOW_LEAD_SHARE_DELTA_WIDE_PP``) or
    thin (<``SOFT_ALLOW_LEAD_SHARE_DELTA_THIN_PP``); mid stays silent —
    portfolio AI + xang1234 after exit-€ share Δ. Display only.
    """
    sides = soft_allow_lead_sides_share(events, band=band, min_count=min_count)
    if sides is None:
        return None
    gate, n, pct, gap, severity, runner, runner_n, runner_pct = sides
    lean = _soft_allow_share_delta_lean(pct, runner_pct)
    if lean not in ("wide", "thin"):
        return None
    delta = round(float(pct) - float(runner_pct), 1)
    return (
        gate,
        n,
        pct,
        gap,
        severity,
        runner,
        runner_n,
        runner_pct,
        delta,
        lean,
    )


def soft_allow_lead_sides_share_vs_delta(
    events: list[dict[str, Any]] | None,
    *,
    band: str,
    min_count: int = 2,
) -> tuple[str, str, str] | None:
    """Count-ahead lean vs ownership-Δ lean (exit-€ share vs Δ adapted).

    Requires a runner-up (sides share). Ahead is always ``wide``/``thin`` when
    sides spoke. Speak ``clash`` when share Δ is mid (exactly one lean spoke).
    Speak ``align`` when both leanish and equal. Different lean stays silent —
    portfolio AI + xang1234 after soft-allow share Δ. Display only.
    """
    sides = soft_allow_lead_sides_share(events, band=band, min_count=min_count)
    if sides is None:
        return None
    _gate, _n, pct, _gap, ahead, _runner, _rn, runner_pct = sides
    if ahead not in ("wide", "thin"):
        return None
    share = _soft_allow_share_delta_lean(pct, runner_pct)
    if share is None:
        return None
    if share == "mid":
        return "clash", ahead, "mid"
    if share == ahead:
        return "align", ahead, share
    return None


def _soft_allow_row_in_band(
    row: dict[str, Any] | None,
    *,
    gate: str,
    band: str,
) -> bool:
    """True when row gate matches and freshness sits in the severity band.

    Fresh also matches ``unknown`` stamps (same as band tally). Shared by
    lead and runner list tags — portfolio AI + xang1234 band identity.
    """
    if not isinstance(row, dict):
        return False
    want = str(gate or "").strip()
    band_s = str(band or "").strip().casefold()
    if not want or band_s not in ("fresh", "aging", "expired"):
        return False
    row_gate = str(row.get("gate") or "").strip()
    if row_gate.casefold() != want.casefold():
        return False
    freshness = str(row.get("freshness") or "").strip().casefold()
    if band_s == "fresh":
        return freshness in ("fresh", "unknown")
    return freshness == band_s


def soft_allow_row_is_lead(
    row: dict[str, Any] | None,
    *,
    lead_gate: str,
    lead_band: str,
) -> bool:
    """True when this Ops list row is in the glance lead gate×band.

    Fresh lead also matches ``unknown`` stamps (same as band tally). Display
    only — portfolio AI + xang1234 concentration on the list, not glance-only.
    """
    return _soft_allow_row_in_band(row, gate=lead_gate, band=lead_band)


def soft_allow_row_is_runner(
    row: dict[str, Any] | None,
    *,
    runner_gate: str,
    lead_band: str,
) -> bool:
    """True when this Ops list row is the glance runner-up gate×band.

    Same band rules as lead (severity-driving band ≠ row cool-off). Speak-
    both-sides after lead tags — portfolio AI + xang1234. Display only.
    """
    return _soft_allow_row_in_band(row, gate=runner_gate, band=lead_band)


def mark_soft_allow_lead_rows(
    events: list[dict[str, Any]] | None,
    *,
    lead_gate: str,
    lead_band: str,
    runner_gate: str = "",
) -> list[dict[str, Any]]:
    """Set lead/runner tags on each enriched soft-allow for Ops list.

    ``lead_band`` is the glance severity band that owns concentration (fresh /
    aging / expired) — not the row's own cool-off stamp. Runner tags reuse
    that band when glance already spoke ``vs``. Lead wins if both match
    (should not happen). xang1234 identity clarity: list tag ≠ row
    aging/expired meta. Display only.
    """
    rows = list(events or [])
    band = str(lead_band or "").strip().casefold()
    for row in rows:
        if isinstance(row, dict):
            is_lead = soft_allow_row_is_lead(
                row, lead_gate=lead_gate, lead_band=lead_band
            )
            is_runner = (
                (not is_lead)
                and soft_allow_row_is_runner(
                    row, runner_gate=runner_gate, lead_band=lead_band
                )
            )
            row["is_lead"] = is_lead
            row["is_runner"] = is_runner
            # Only tagged rows carry the glance-band label (avoid confusing
            # non-lead/runner rows whose freshness already has aging/expired).
            row["lead_band"] = band if is_lead and band else ""
            row["runner_band"] = band if is_runner and band else ""
    return rows


def _soft_allow_lead_prefix(gate: str, band: str) -> str:
    """``rs leads · fresh`` — gate + severity-band identity (xang1234).

    Band name matches Ops ``leads · fresh|aging|expired`` so friends do not
    read concentration as whole-ring. Unknown band omits the label.
    """
    g = str(gate or "").strip() or "?"
    band_s = str(band or "").strip().casefold()
    if band_s in ("fresh", "aging", "expired"):
        return f"{g} leads · {band_s}"
    return f"{g} leads"


def soft_allow_last_vs_lead(lead_gate: str, last_gate: str) -> str:
    """Newest soft-allow gate vs band lead (display only).

    Compact ``rs leads · …`` hid whether the newest print matches the
    severity-band tilt. When lead already spoke: same gate speaks
    ``agree`` (silent confirm hid match); different speaks
    ``last vs lead · breadth``. Lead ownership ≠ newest print.
    FinRobot last-debate ≠ ring tilt + portfolio AI speak-both-sides
    after soft-allow lead sides share (LAYA/debate ``last vs lead`` /
    ``agree`` parity). No tone escalate. Not a gate.
    """
    lead = str(lead_gate or "").strip()
    last = str(last_gate or "").strip()
    if not lead or not last:
        return ""
    if lead.casefold() == last.casefold():
        return "agree"
    return f"last vs lead · {last}"


def soft_allow_sample_gap(
    events: list[dict[str, Any]] | None,
    *,
    band: str,
    lead_gate: str = "",
) -> str:
    """Speak thin/tied when a severity-band lead would overclaim (display only).

    Empty ring stays on the caller. A single row in the severity-driving
    band is compact ``n=1`` (last-row ≠ ring tilt; not cool-off ``aging``).
    Two-plus with no strict lead is ``tied`` (counts without a winner).
    Lead cases stay silent. Window A Kelly sample thin + xang1234 sample
    honesty + LAYA/debate ``_decision_sample_gap`` parity. Not a gate.
    """
    if str(lead_gate or "").strip():
        return ""
    total = sum(c for _, c in soft_allow_band_tally(events, band=band))
    if total <= 0:
        return ""
    if total < 2:
        return "n=1"
    return "tied"


def format_soft_allow_lead_bit(
    events: list[dict[str, Any]] | None,
    *,
    band: str,
    min_count: int = 2,
) -> str:
    """Compact ``rs leads · fresh · ×2 · 67% · ahead thin · +1 · vs …``.

    Band identity mirrors Ops ``leads · band`` (severity-driving band ≠ row
    cool-off stamp). Sole-gate omits ahead and vs (no runner-up). Share Δ
    omits mid spreads. Share vs Δ speaks clash (share mid) or align (same
    lean); different lean silent.
    """
    vs = soft_allow_lead_sides_share_vs_delta(
        events, band=band, min_count=min_count
    )
    delta = soft_allow_lead_sides_share_delta(
        events, band=band, min_count=min_count
    )
    if delta is not None:
        (
            gate,
            n,
            pct,
            gap,
            severity,
            runner,
            runner_n,
            runner_pct,
            pp,
            lean,
        ) = delta
        signed = int(round(pp))
        bit = (
            f"{_soft_allow_lead_prefix(gate, band)} · ×{n} · "
            f"{int(round(pct))}% · ahead {severity} · "
            f"+{gap} · vs {runner} ×{runner_n} · {int(round(runner_pct))}% · "
            f"share Δ {lean} · {signed:+d}pp"
        )
        if vs is not None and vs[0] == "align":
            bit = f"{bit} · share vs Δ align · {vs[1]}"
        return bit
    sides = soft_allow_lead_sides_share(events, band=band, min_count=min_count)
    if sides is not None:
        gate, n, pct, gap, severity, runner, runner_n, runner_pct = sides
        bit = (
            f"{_soft_allow_lead_prefix(gate, band)} · ×{n} · "
            f"{int(round(pct))}% · ahead {severity} · "
            f"+{gap} · vs {runner} ×{runner_n} · {int(round(runner_pct))}%"
        )
        if vs is not None and vs[0] == "clash":
            bit = (
                f"{bit} · share vs Δ clash · ahead {vs[1]} · share {vs[2]}"
            )
        return bit
    lead = soft_allow_lead_share(events, band=band, min_count=min_count)
    if lead is None:
        return ""
    gate, n, pct = lead
    return (
        f"{_soft_allow_lead_prefix(gate, band)} · ×{n} · {int(round(pct))}%"
    )

def soft_allow_event_key(gate: str, reason: str) -> tuple[str, str]:
    """Identity for one soft-allow row (gate + reason, case-folded).

    tradermonty #447 rejects duplicate hypothesis ids in multi-asset replay —
    same idea here: one live fail-open key, refresh stamp instead of flooding.
    """
    g = str(gate or "").strip() or "?"
    r = str(reason or "").strip()[:240]
    return (g.casefold(), r.casefold())


def record_soft_allow(
    data_dir: Path | str,
    gate: str,
    reason: str,
    *,
    cap: int = SOFT_ALLOW_CAP,
) -> None:
    """Append one soft-allow; keep the newest ``cap`` rows.

    Replacing a prior row with the same gate+reason refreshes ``at`` and
    drops the duplicate (tradermonty #447). Distinct reasons still accumulate.
    """
    if not is_soft_allow_reason(reason):
        return
    path = soft_allow_path(data_dir)
    gate_s = str(gate or "").strip() or "?"
    reason_s = str(reason or "").strip()[:240]
    key = soft_allow_event_key(gate_s, reason_s)
    events = [
        e
        for e in load_soft_allows(data_dir)
        if soft_allow_event_key(
            str(e.get("gate") or ""), str(e.get("reason") or "")
        )
        != key
    ]
    events.append(
        {
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "gate": gate_s,
            "reason": reason_s,
        }
    )
    keep = max(1, int(cap))
    events = events[-keep:]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"updated_at": events[-1]["at"], "events": events}, indent=2)
            + "\n"
        )
    except OSError:
        pass


def log_soft_allow(
    gate: str,
    reason: str,
    data_dir: Path | str | None = None,
) -> None:
    """Print + persist when a gate allows because data is missing / unknown."""
    if not is_soft_allow_reason(reason):
        return
    print(f"   ⚪ Soft-allow [{gate}]: {reason}")
    record_soft_allow(data_dir or _default_data_dir(), gate, reason)
