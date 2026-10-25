"""Shared soft-gate logging (fail-open visibility — review A5).

Prints soft-allows and keeps a short desk-readable ring buffer under data/.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

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
    "short history",  # xang1234 #668 young / short listing vs lookback
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
# Primary RS benchmarks (relative_strength bench_label). Short history on
# these is a stale / thin primary, not a young listing — xang1234 #679.
PRIMARY_RS_BENCH_LABELS = frozenset(
    {"SPY", "SPX", "BTC", "BTCUSDT", "BENCHMARK"}
)


def is_primary_rs_bench_label(label: str) -> bool:
    """True when ``label`` is a stock/crypto RS primary benchmark."""
    return str(label or "").strip().upper() in PRIMARY_RS_BENCH_LABELS


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


def soft_allow_short_history_count(
    events: list[dict[str, Any]] | None,
) -> int:
    """Count soft-allows whose reason is an RS short-history fail-open.

    Gate tallies only say ``rs×N`` — bare ``RS unknown``,
    ``short history``, and ``anchor gap`` looked the same. xang1234
    #668 rates young listings on the horizons they have; we fail-open
    instead, but desk should speak how many ring rows are short-series
    (not gappy anchors). Display only; zero stays silent. Not a gate.
    """
    n = 0
    for row in events or []:
        if not isinstance(row, dict):
            continue
        if "short history" in str(row.get("reason") or "").casefold():
            n += 1
    return n


def soft_allow_short_history_share(
    events: list[dict[str, Any]] | None,
) -> tuple[int, float | None, str]:
    """Short-history count + ring share + severity (display only).

    Returns ``(count, share_pct, severity)``. Zero shorts →
    ``(0, None, "")``. Share is short÷Mapping-rows; hot ≥50% · quiet ≤25% ·
    mid ``ok`` (portfolio AI count≠share after absolute ``N short``;
    soft ``N gap`` share parity + xang1234 #668). Short÷(short+gap) pair
    share stays a separate bit — ring ownership ≠ pair ownership.
    Short-vs-other lean still deferred. Not a gate.
    """
    rows = [r for r in (events or []) if isinstance(r, dict)]
    short_n = soft_allow_short_history_count(rows)
    if short_n <= 0 or not rows:
        return 0, None, ""
    share = round(100.0 * short_n / len(rows), 1)
    if share >= SOFT_ALLOW_ANCHOR_GAP_SHARE_HOT:
        severity = "hot"
    elif share <= SOFT_ALLOW_ANCHOR_GAP_SHARE_QUIET:
        severity = "quiet"
    else:
        severity = "ok"
    return short_n, share, severity


def _short_history_symbol(reason: str) -> str:
    """First token of a short-history reason (asset / bench label)."""
    text = str(reason or "").strip()
    if "short history" not in text.casefold():
        return ""
    tok = text.split(None, 1)[0] if text else ""
    if tok and tok.lower() not in {"rs", "unknown", "—", "-"}:
        return tok
    return ""


def soft_allow_short_history_last_symbol(
    events: list[dict[str, Any]] | None,
) -> str:
    """Newest short-history row's ticker/label (display only).

    Absolute ``N short`` hid which name last failed open on a young /
    short series. Reasons look like ``IPO RS unknown — short history
    — allow`` / ``SPY RS unknown — short history — allow`` — first
    token is the asset or bench label. Ring order is newest-first.
    xang1234 #546 resume-cursor after #668 short count + FinRobot
    last-row; zero / unparseable silent. Cursor age follows via
    ``soft_allow_short_history_last_freshness``. Not a gate.
    """
    for row in events or []:
        if not isinstance(row, dict):
            continue
        sym = _short_history_symbol(str(row.get("reason") or ""))
        if sym:
            return sym
    return ""


def soft_allow_short_history_last_freshness(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> str:
    """Freshness band of the newest parseable short-history row.

    ``last SYM`` alone ≠ whether that young/short fail-open is still
    live. Speaks ``fresh`` / ``aging`` / ``expired`` from enriched
    ``freshness`` or ``at`` (gap last-freshness + RyanJHamby +
    xang1234 soft-allow triad + FinRobot last-row age). Missing /
    unknown stamp stays silent — cursor name still speaks. Display
    only; not a gate.
    """
    for row in events or []:
        if not isinstance(row, dict):
            continue
        if not _short_history_symbol(str(row.get("reason") or "")):
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


def soft_allow_short_history_bench_count(
    events: list[dict[str, Any]] | None,
) -> int:
    """Count short-history rows whose label is a primary RS benchmark.

    Absolute ``N short`` / ``last SYM`` treat SPY/BTC like a young
    listing. xang1234 #679 refuses a warm that stops before the last
    completed session — desk should speak how many short-series
    fail-opens are the primary benchmark (stale/thin SPY or BTC), not
    an IPO. Zero silent. Share via
    ``soft_allow_short_history_bench_share``. Display only; not a gate.
    """
    n = 0
    for row in events or []:
        if not isinstance(row, dict):
            continue
        sym = _short_history_symbol(str(row.get("reason") or ""))
        if sym and is_primary_rs_bench_label(sym):
            n += 1
    return n


def soft_allow_short_history_bench_share(
    events: list[dict[str, Any]] | None,
) -> tuple[int, float | None, str]:
    """Primary-bench short count + share of short rows + severity.

    Returns ``(bench_n, share_pct, severity)``. Zero bench →
    ``(0, None, "")``. Share is bench÷short (not bench÷ring); hot ≥50% ·
    quiet ≤25% · mid ``ok``. Absolute ``N bench`` hid whether thin
    SPY/BTC owns the young/short fail-open sleeve (RyanJHamby
    fundamentals-cache / daily-scan chore adapted as primary-bench
    ownership + xang1234 #679 + portfolio AI count≠share after #668
    ``N bench``). Short÷ring and short÷(short+gap) stay separate bits.
    Display only; not a gate.
    """
    short_n = soft_allow_short_history_count(events)
    bench_n = soft_allow_short_history_bench_count(events)
    if bench_n <= 0 or short_n <= 0:
        return 0, None, ""
    share = round(100.0 * bench_n / short_n, 1)
    if share >= SOFT_ALLOW_ANCHOR_GAP_SHARE_HOT:
        severity = "hot"
    elif share <= SOFT_ALLOW_ANCHOR_GAP_SHARE_QUIET:
        severity = "quiet"
    else:
        severity = "ok"
    return bench_n, share, severity


def soft_allow_short_history_bench_vs_young(
    events: list[dict[str, Any]] | None,
) -> tuple[int, float | None, str]:
    """Non-bench short remainder when bench already spoke (display only).

    Returns ``(young_n, share_pct, severity)``. No bench →
    ``(0, None, "")``. Young = short − bench (share of short rows, not
    ring); strong ≥75% · thin <50% · mid ``ok``. All-bench →
    ``(0, 0.0, "thin")`` — gap vs other / Screener junk vs ok sides
    parity after bench% alone hid usable young/short fail-opens
    (portfolio AI speak-both-sides; RyanJHamby + xang1234 #679 after
    #668 ``N bench · P%``). Display only; not a gate.
    """
    short_n = soft_allow_short_history_count(events)
    bench_n = soft_allow_short_history_bench_count(events)
    if bench_n <= 0 or short_n <= 0:
        return 0, None, ""
    young_n = short_n - bench_n
    share = round(100.0 * young_n / short_n, 1)
    if share >= SOFT_ALLOW_OTHER_SHARE_STRONG:
        severity = "strong"
    elif share < SOFT_ALLOW_OTHER_SHARE_THIN:
        severity = "thin"
    else:
        severity = "ok"
    return young_n, share, severity


def soft_allow_short_history_bench_vs_young_lean(
    events: list[dict[str, Any]] | None,
) -> tuple[str, bool]:
    """Bench vs young lean when both sides already spoke (display only).

    Returns ``(lean_bit, warn)``. Silent when bench did not speak or both
    severities are mid. Screener ``junk_vs_ok`` / gap vs other parity:
    matched extremes speak ``align · hot|thin`` / ``quiet|strong``;
    mismatch or one-lean speaks ``clash · bench … · young …`` (warn when
    bench hot or young thin). Sides alone hid lean agreement (portfolio
    AI speak-both-sides after #679 bench share). Not a gate.
    """
    bench_n, _bench_share, bench_sev = soft_allow_short_history_bench_share(
        events
    )
    young_n, young_share, young_sev = soft_allow_short_history_bench_vs_young(
        events
    )
    if bench_n <= 0 or young_share is None:
        return "", False
    bench_lean = bench_sev in {"hot", "quiet"}
    young_lean = young_sev in {"strong", "thin"}
    if bench_lean and young_lean:
        matched = (bench_sev == "hot" and young_sev == "thin") or (
            bench_sev == "quiet" and young_sev == "strong"
        )
        if matched:
            return f"align · {bench_sev}|{young_sev}", False
        return (
            f"clash · bench {bench_sev} · young {young_sev}",
            True,
        )
    if bench_lean != young_lean:
        warn = bench_sev == "hot" or young_sev == "thin"
        return (
            f"clash · bench {bench_sev} · young {young_sev}",
            warn,
        )
    return "", False


def soft_allow_short_history_bench_vs_young_delta(
    events: list[dict[str, Any]] | None,
) -> tuple[float | None, str]:
    """Bench%−young% ownership spread when lean already spoke.

    Returns ``(delta_pp, severity)``. Silent when bench vs young lean did
    not speak. Wide ≥``SOFT_ALLOW_LEAD_SHARE_DELTA_WIDE_PP`` · thin
    <``SOFT_ALLOW_LEAD_SHARE_DELTA_THIN_PP`` · mid stays silent on the Δ
    bit (short vs gap / Screener junk vs ok share Δ parity). Lean labels
    alone hid how far primary-bench vs young/short ownership sits
    (portfolio AI count≠share + xang1234 after #679 bench vs young lean).
    Display only; not a gate.
    """
    lean, _ = soft_allow_short_history_bench_vs_young_lean(events)
    bench_n, bench_share, _bench_sev = soft_allow_short_history_bench_share(
        events
    )
    young_n, young_share, _young_sev = soft_allow_short_history_bench_vs_young(
        events
    )
    if (
        not lean
        or bench_n <= 0
        or bench_share is None
        or young_share is None
    ):
        return None, ""
    delta_pp = round(float(bench_share) - float(young_share), 1)
    mag = abs(delta_pp)
    if mag < 1e-9:
        return None, ""
    if mag >= SOFT_ALLOW_LEAD_SHARE_DELTA_WIDE_PP:
        return delta_pp, "wide"
    if mag < SOFT_ALLOW_LEAD_SHARE_DELTA_THIN_PP:
        return delta_pp, "thin"
    return None, ""


def soft_allow_short_history_bench_vs_young_lean_vs_delta(
    events: list[dict[str, Any]] | None,
) -> tuple[str, bool]:
    """Bench vs young lean vs ownership-Δ lean (display only).

    Returns ``(bit, warn)``. When lean already spoke: Δ wide|thin speaks
    ``align · wide|thin``; Δ mid (lean spoke, spread silent) speaks
    ``clash · lean · Δ mid`` (warn). Adverse dual-wide confirm
    (``align · hot|thin`` + Δ wide) warns — short vs gap lean vs Δ /
    Screener junk vs ok lean vs Δ parity; favorable quiet|strong stays
    calm. Lean alone hid whether ownership distance agrees with the lean
    label (portfolio AI + xang1234 after #679 bench vs young lean). Not a
    gate.
    """
    lean, _ = soft_allow_short_history_bench_vs_young_lean(events)
    if not lean:
        return "", False
    delta_pp, delta_sev = soft_allow_short_history_bench_vs_young_delta(
        events
    )
    if delta_sev:
        warn = delta_sev == "wide" and lean.startswith("align · hot|thin")
        return f"align · {delta_sev}", warn
    return "clash · lean · Δ mid", True


def soft_allow_short_history_bench_vs_young_delta_lead(
    events: list[dict[str, Any]] | None,
) -> str:
    """Name which sleeve owns a spoken short bench vs young Δ (display only).

    Returns ``bench|young`` / ``\"\"``. When lean vs Δ already spoke with
    a Δ (wide|thin) and ±pp ≠ 0, positive bench%−young% → ``bench``;
    negative → ``young``. Mid-Δ clash / 0pp stay silent. Signed pp alone
    hid which primary-bench vs young/short sleeve owns the spread (short
    vs gap / Screener unique vs dup / Yahoo mix Δ lead parity after
    #679 bench vs young share Δ). Not a gate.
    """
    lean_vs_delta, _ = soft_allow_short_history_bench_vs_young_lean_vs_delta(
        events
    )
    if not str(lean_vs_delta or "").startswith("align ·"):
        return ""
    delta_pp, delta_sev = soft_allow_short_history_bench_vs_young_delta(
        events
    )
    if not delta_sev or delta_pp is None:
        return ""
    try:
        pp = float(delta_pp)
    except (TypeError, ValueError):
        return ""
    if abs(pp) < 1e-9:
        return ""
    return "bench" if pp > 0 else "young"


def soft_allow_short_history_last_vs_bench_young(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last short freshness vs bench/young lean (display only).

    Returns ``(bit, warn)``. Cursor age ≠ primary-bench vs young lean.
    Extremes only: ``fresh``↔ lean ``align`` and ``expired``↔ lean
    ``clash`` speak ``align``; crossed pairs speak ``clash`` (warn).
    ``aging`` / silent lean stay silent — gap last/lean + short last/lean
    parity after #679 bench vs young lean + last freshness alone hid
    age≠bench/young (RyanJHamby triad + FinRobot last-row age +
    portfolio AI speak-both-sides; xang1234 #668). Not a gate.
    """
    last_fresh = soft_allow_short_history_last_freshness(events, now=now)
    lean, _lean_warn = soft_allow_short_history_bench_vs_young_lean(events)
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


def soft_allow_short_history_last_lead_vs_bench_young(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last/lead freshness vs last/bench relationship agreement (display only).

    Returns ``(bit, warn)``. Age↔name-vs-lead ≠ age↔bench/young lean. When
    both already spoke: same verb speaks ``align · both align|clash`` —
    ``both align`` stays calm; ``both clash`` warns (dual-clash agreement
    ≠ quiet confirm). Crossed verbs speak
    ``clash · lead align|clash · bench align|clash`` (warn). Missing
    either stays silent — gap lead/lean + short lead/lean parity after
    #679 last/bench + last/lead alone hid whether cursor-vs-owner and
    age↔bench/young agree *and* whether dual-clash agreement is adverse.
    Side-by-side bits are not transitive. Short-vs-other lean still
    deferred. Not a gate.
    """
    lead_bit, _ = soft_allow_short_history_last_vs_lead_freshness(
        events, now=now
    )
    bench_bit, _ = soft_allow_short_history_last_vs_bench_young(
        events, now=now
    )
    if not lead_bit or not bench_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    lead_verb = _verb(lead_bit)
    bench_verb = _verb(bench_bit)
    if lead_verb is None or bench_verb is None:
        return "", False
    if lead_verb == bench_verb:
        return f"align · both {lead_verb}", lead_verb == "clash"
    return f"clash · lead {lead_verb} · bench {bench_verb}", True


def soft_allow_short_history_last_share_vs_bench_young(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last/share freshness vs last/bench relationship agreement (display only).

    Returns ``(bit, warn)``. Age↔pair-ownership heat ≠ age↔bench/young
    lean. When both already spoke: same verb speaks
    ``align · both align|clash`` — ``both align`` stays calm; ``both
    clash`` warns (dual-clash agreement ≠ quiet confirm). Crossed verbs
    speak ``clash · share align|clash · bench align|clash`` (warn).
    Missing either stays silent — gap share/lean + short share/lean
    parity after #679 last/share + last/bench alone hid whether
    pair-ownership heat and age↔bench/young agree *and* whether
    dual-clash agreement is adverse. Side-by-side bits are not
    transitive (lead/bench + lead/share ≠ this edge). Short-vs-other
    lean still deferred. Not a gate.
    """
    share_bit, _ = soft_allow_short_history_last_vs_share(events, now=now)
    bench_bit, _ = soft_allow_short_history_last_vs_bench_young(
        events, now=now
    )
    if not share_bit or not bench_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    share_verb = _verb(share_bit)
    bench_verb = _verb(bench_bit)
    if share_verb is None or bench_verb is None:
        return "", False
    if share_verb == bench_verb:
        return f"align · both {share_verb}", share_verb == "clash"
    return f"clash · share {share_verb} · bench {bench_verb}", True


def soft_allow_short_history_last_ring_vs_bench_young(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last/ring freshness vs last/bench relationship agreement (display only).

    Returns ``(bit, warn)``. Age↔short÷ring heat ≠ age↔bench/young lean.
    When both already spoke: same verb speaks
    ``align · both align|clash`` — ``both align`` stays calm; ``both
    clash`` warns (dual-clash agreement ≠ quiet confirm). Crossed verbs
    speak ``clash · ring align|clash · bench align|clash`` (warn).
    Missing either stays silent — gap share/lean + short share/bench
    parity after #679 last/ring + last/bench alone hid whether ring
    ownership heat and age↔bench/young agree *and* whether dual-clash
    agreement is adverse. Side-by-side bits are not transitive
    (lead/bench + lead/ring + share/bench + share/ring ≠ this edge).
    Closes ring↔bench↔share with share/bench + share/ring and
    lead↔ring↔bench with lead/bench + lead/ring. Short-vs-other lean
    still deferred. Not a gate.
    """
    ring_bit, _ = soft_allow_short_history_last_vs_ring_share(
        events, now=now
    )
    bench_bit, _ = soft_allow_short_history_last_vs_bench_young(
        events, now=now
    )
    if not ring_bit or not bench_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    ring_verb = _verb(ring_bit)
    bench_verb = _verb(bench_bit)
    if ring_verb is None or bench_verb is None:
        return "", False
    if ring_verb == bench_verb:
        return f"align · both {ring_verb}", ring_verb == "clash"
    return f"clash · ring {ring_verb} · bench {bench_verb}", True


def soft_allow_short_history_last_lean_vs_bench_young(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last/lean freshness vs last/bench relationship agreement (display only).

    Returns ``(bit, warn)``. Age↔short-vs-gap lean ≠ age↔bench/young
    lean. When both already spoke: same verb speaks
    ``align · both align|clash`` — ``both align`` stays calm; ``both
    clash`` warns (dual-clash agreement ≠ quiet confirm). Crossed verbs
    speak ``clash · lean align|clash · bench align|clash`` (warn).
    Missing either stays silent — gap share/lean + short ring/bench
    parity after #679 last/lean + last/bench alone hid whether
    pair-lean heat and age↔bench/young agree *and* whether dual-clash
    agreement is adverse. Side-by-side bits are not transitive
    (lead/bench + lead/lean + share/bench + share/lean + ring/bench +
    ring/lean ≠ this edge). Closes lean↔bench↔ring with ring/bench +
    ring/lean and lean↔bench↔share with share/bench + share/lean.
    Short-vs-other lean still deferred. Not a gate.
    """
    lean_bit, _ = soft_allow_short_history_last_vs_lean(events, now=now)
    bench_bit, _ = soft_allow_short_history_last_vs_bench_young(
        events, now=now
    )
    if not lean_bit or not bench_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    lean_verb = _verb(lean_bit)
    bench_verb = _verb(bench_bit)
    if lean_verb is None or bench_verb is None:
        return "", False
    if lean_verb == bench_verb:
        return f"align · both {lean_verb}", lean_verb == "clash"
    return f"clash · lean {lean_verb} · bench {bench_verb}", True


def _short_history_symbol_counts(
    events: list[dict[str, Any]] | None,
) -> dict[str, int]:
    """Parseable short-history symbol tallies (newest-first; display only)."""
    counts: dict[str, int] = {}
    for row in events or []:
        if not isinstance(row, dict):
            continue
        sym = _short_history_symbol(str(row.get("reason") or ""))
        if not sym:
            continue
        counts[sym] = counts.get(sym, 0) + 1
    return counts


def soft_allow_short_history_symbol_lead(
    events: list[dict[str, Any]] | None,
) -> tuple[str, str, int | None]:
    """Strict lead among parseable short-history symbols (display only).

    Returns ``(lead_bit, lead_name, share_pct)``. ``last SYM`` alone ≠
    which name owns the young/short fail-open ring. When ≥2 parseable
    short symbols and one is strictly largest, speak
    ``lead IPO · N · P%`` (row count then share of parseable short rows).
    Ties / sole-symbol / <2 parseable stay silent on lead (use
    ``soft_allow_short_history_symbol_sample_gap``). Gap symbol-lead +
    Screener junk-list lead + xang1234 multi-meter after last-cursor.
    Margin/sides follow when a runner exists; share/freshness/lean
    cascade still deferred. Not a gate.
    """
    counts = _short_history_symbol_counts(events)
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
    return f"lead {lead_name} · {lead_n} · {share}%", lead_name, share


def soft_allow_short_history_symbol_sample_gap(
    events: list[dict[str, Any]] | None,
) -> str:
    """Speak ``n=1`` / ``tied`` when parseable short names have no lead.

    One parseable short row speaks compact ``n=1`` (``last SYM`` alone ≠
    a thin sample; gap / LAYA ``_decision_sample_gap`` parity). ≥2 with
    no strict lead speaks ``tied``. Lead cases / zero stay silent on
    gap. Display only; not a gate.
    """
    counts = _short_history_symbol_counts(events)
    total = sum(counts.values())
    if total <= 0:
        return ""
    lead_bit, _name, _share = soft_allow_short_history_symbol_lead(events)
    if lead_bit:
        return ""
    if total < 2:
        return "n=1"
    return "tied"


def soft_allow_short_history_symbol_last_vs_lead(
    events: list[dict[str, Any]] | None,
) -> str:
    """Newest short ticker vs symbol lead (display only).

    ``last SYM`` + ``lead SYM · N%`` alone hid whether the resume cursor
    matches the ring owner. When lead already spoke: same name speaks
    ``agree``; different speaks ``last vs lead · NEW``. Tied / no-lead /
    missing cursor stay silent. Reuses ``soft_allow_last_vs_lead``
    (gap symbol last-vs-lead parity). xang1234 #546 + FinRobot
    last≠ring tilt + portfolio AI speak-both-sides. Not a gate.
    """
    _bit, lead_name, _share = soft_allow_short_history_symbol_lead(events)
    if not lead_name:
        return ""
    last = soft_allow_short_history_last_symbol(events)
    return soft_allow_last_vs_lead(lead_name, last)


def soft_allow_short_history_last_vs_lead_freshness(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last short freshness vs symbol last-vs-lead (display only).

    Returns ``(bit, warn)``. Cursor age ≠ name-vs-lead agreement.
    Extremes only: ``fresh``↔``agree`` and ``expired``↔ name clash speak
    ``align``; crossed pairs speak ``clash`` (warn). ``aging`` / silent
    last-vs-lead stay silent — gap last/lead freshness parity +
    RyanJHamby triad + FinRobot last-row age + portfolio AI
    speak-both-sides after bare ``agree`` / ``last vs lead`` hid whether
    the cursor match is still live (stale agree ≠ calm confirm).
    Short÷ring share still deferred (no ``×N · P%``). Not a gate.
    """
    last_fresh = soft_allow_short_history_last_freshness(events, now=now)
    last_vs = soft_allow_short_history_symbol_last_vs_lead(events)
    if last_fresh not in {"fresh", "expired"} or not last_vs:
        return "", False
    if last_vs == "agree":
        name_agree = True
        name_tail = "agree"
    elif last_vs.startswith("last vs lead · "):
        name_agree = False
        name_tail = f"vs {last_vs[len('last vs lead · ') :]}"
    else:
        return "", False
    live_age = last_fresh == "fresh"
    if live_age == name_agree:
        return f"align · {last_fresh} · {name_tail}", False
    return f"clash · {last_fresh} · {name_tail}", True


def soft_allow_short_history_symbol_lead_margin(
    events: list[dict[str, Any]] | None,
) -> tuple[str, int, str] | None:
    """Lead share plus margin over #2 short symbol (display only).

    Returns ``(ahead_bit, margin, severity)``. Ownership % ≠ how far
    ahead. Speaks only when symbol lead already spoke **and** a
    runner-up name exists (sole 100% omits ahead). Severity: ``wide``
    when margin ≥ ``SOFT_ALLOW_LEAD_MARGIN_WIDE``, else ``thin``. Gap
    symbol-lead margin + Screener junk-list lead + portfolio AI after
    lead %. Not a gate.
    """
    lead_bit, _name, _share = soft_allow_short_history_symbol_lead(events)
    if not lead_bit:
        return None
    counts = _short_history_symbol_counts(events)
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    if len(ranked) < 2:
        return None
    margin = int(ranked[0][1]) - int(ranked[1][1])
    if margin < 1:
        return None
    severity = "wide" if margin >= SOFT_ALLOW_LEAD_MARGIN_WIDE else "thin"
    return f"ahead {severity} · +{margin}", margin, severity


def soft_allow_short_history_symbol_lead_sides(
    events: list[dict[str, Any]] | None,
) -> tuple[str, str, int, int] | None:
    """Lead margin plus runner-up short symbol (display only).

    Returns ``(sides_bit, runner, runner_n, runner_share_pct)``. Ahead
    +K ≠ who is #2. Speaks when margin already spoke; runner share is
    runner÷parseable short total (absolute count ≠ ownership). Gap
    symbol-lead sides + portfolio AI speak-both-sides. Not a gate.
    """
    margin = soft_allow_short_history_symbol_lead_margin(events)
    if margin is None:
        return None
    counts = _short_history_symbol_counts(events)
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


def soft_allow_short_vs_gap(
    events: list[dict[str, Any]] | None,
) -> tuple[str, int, int, str] | None:
    """Gap side when short already spoke (display only).

    Returns ``(bit, gap_n, gap_share_pct, gap_severity)`` or None.
    Absolute ``N short`` · ``N gap`` alone hid ownership of the RS
    fail-open pair (young / short vs gappy-anchor). Speaks only when
    both counts > 0: ``vs gap · [strong|thin ·] N · P%``
    (gap÷(short+gap); strong ≥75 · thin <50 · mid omits severity).
    Screener junk vs ok / soft gap vs other sides parity after #668
    short count + #539 gap count; portfolio AI count≠share. Short÷ring
    share shipped beside this pair bit; short-vs-other lean still
    deferred. Not a gate.
    """
    short_n = soft_allow_short_history_count(events)
    gap_n = soft_allow_anchor_gap_count(events)
    if short_n <= 0 or gap_n <= 0:
        return None
    pair = short_n + gap_n
    gap_share = int(round(100.0 * gap_n / pair))
    if gap_share >= SOFT_ALLOW_OTHER_SHARE_STRONG:
        sev = "strong"
    elif gap_share < SOFT_ALLOW_OTHER_SHARE_THIN:
        sev = "thin"
    else:
        sev = "ok"
    if sev in {"strong", "thin"}:
        bit = f"vs gap · {sev} · {gap_n} · {gap_share}%"
    else:
        bit = f"vs gap · {gap_n} · {gap_share}%"
    return bit, gap_n, gap_share, sev


def soft_allow_short_pair_share(
    events: list[dict[str, Any]] | None,
) -> tuple[int, int, str] | None:
    """Short ownership of the short+gap pair (display only).

    Returns ``(short_n, short_share_pct, severity)`` or None when either
    side is silent. ``short÷(short+gap)``; hot ≥50 · quiet ≤25 · mid
    ``ok`` — Screener junk-share / soft gap-share floors so ``vs gap``
    alone does not hide which sleeve owns the RS fail-open pair
    (portfolio AI count≠share). Not a gate.
    """
    short_n = soft_allow_short_history_count(events)
    gap_n = soft_allow_anchor_gap_count(events)
    if short_n <= 0 or gap_n <= 0:
        return None
    pair = short_n + gap_n
    short_share = int(round(100.0 * short_n / pair))
    if short_share >= SOFT_ALLOW_ANCHOR_GAP_SHARE_HOT:
        sev = "hot"
    elif short_share <= SOFT_ALLOW_ANCHOR_GAP_SHARE_QUIET:
        sev = "quiet"
    else:
        sev = "ok"
    return short_n, short_share, sev


def soft_allow_short_vs_gap_lean(
    events: list[dict[str, Any]] | None,
) -> tuple[str, bool]:
    """Short vs gap lean when both pair sides already spoke (display only).

    Returns ``(lean_bit, warn)``. Silent when ``vs gap`` did not speak or
    both severities are mid. Screener junk vs ok / soft gap vs other lean
    parity: matched extremes speak ``align · hot|thin`` /
    ``quiet|strong``; mismatch or one-lean speaks
    ``clash · short … · gap …`` (warn when short hot or gap thin). Sides
    alone hid lean agreement (portfolio AI speak-both-sides). Short÷ring
    share shipped beside pair ownership; short-vs-other lean still
    deferred. Not a gate.
    """
    vs = soft_allow_short_vs_gap(events)
    pair = soft_allow_short_pair_share(events)
    if vs is None or pair is None:
        return "", False
    _bit, _gap_n, _gap_share, gap_sev = vs
    _short_n, _short_share, short_sev = pair
    short_lean = short_sev in {"hot", "quiet"}
    gap_lean = gap_sev in {"strong", "thin"}
    if short_lean and gap_lean:
        matched = (short_sev == "hot" and gap_sev == "thin") or (
            short_sev == "quiet" and gap_sev == "strong"
        )
        if matched:
            return f"align · {short_sev}|{gap_sev}", False
        return (
            f"clash · short {short_sev} · gap {gap_sev}",
            True,
        )
    if short_lean != gap_lean:
        warn = short_sev == "hot" or gap_sev == "thin"
        return (
            f"clash · short {short_sev} · gap {gap_sev}",
            warn,
        )
    return "", False


def soft_allow_short_vs_gap_delta(
    events: list[dict[str, Any]] | None,
) -> tuple[float | None, str]:
    """Short%−gap% pair ownership spread when lean already spoke.

    Returns ``(delta_pp, severity)``. Silent when short vs gap lean did
    not speak. Wide ≥``SOFT_ALLOW_LEAD_SHARE_DELTA_WIDE_PP`` · thin
    <``SOFT_ALLOW_LEAD_SHARE_DELTA_THIN_PP`` · mid stays silent on the Δ
    bit (Screener junk vs ok / unique vs dup share Δ parity). Lean
    labels alone hid how far pair ownership sits (portfolio AI
    count≠share + xang1234 after short vs gap lean). Display only; not
    a gate.
    """
    lean, _ = soft_allow_short_vs_gap_lean(events)
    pair = soft_allow_short_pair_share(events)
    vs = soft_allow_short_vs_gap(events)
    if not lean or pair is None or vs is None:
        return None, ""
    _short_n, short_share, _short_sev = pair
    _bit, _gap_n, gap_share, _gap_sev = vs
    delta_pp = round(float(short_share) - float(gap_share), 1)
    mag = abs(delta_pp)
    if mag < 1e-9:
        return None, ""
    if mag >= SOFT_ALLOW_LEAD_SHARE_DELTA_WIDE_PP:
        return delta_pp, "wide"
    if mag < SOFT_ALLOW_LEAD_SHARE_DELTA_THIN_PP:
        return delta_pp, "thin"
    return None, ""


def soft_allow_short_vs_gap_lean_vs_delta(
    events: list[dict[str, Any]] | None,
) -> tuple[str, bool]:
    """Short vs gap lean vs ownership-Δ lean (display only).

    Returns ``(bit, warn)``. When lean already spoke: Δ wide|thin speaks
    ``align · wide|thin``; Δ mid (lean spoke, spread silent) speaks
    ``clash · lean · Δ mid`` (warn). Adverse dual-wide confirm
    (``align · hot|thin`` + Δ wide) warns — Screener junk vs ok lean vs
    Δ / Hours attn wide-align parity; favorable quiet|strong stays calm.
    Lean alone hid whether ownership distance agrees with the lean
    label (portfolio AI + xang1234 after short vs gap lean). Not a gate.
    """
    lean, _ = soft_allow_short_vs_gap_lean(events)
    if not lean:
        return "", False
    delta_pp, delta_sev = soft_allow_short_vs_gap_delta(events)
    if delta_sev:
        warn = delta_sev == "wide" and lean.startswith("align · hot|thin")
        return f"align · {delta_sev}", warn
    return "clash · lean · Δ mid", True


def soft_allow_short_vs_gap_delta_lead(
    events: list[dict[str, Any]] | None,
) -> str:
    """Name which pair side owns a spoken short vs gap Δ (display only).

    Returns ``short|gap`` / ``\"\"``. When lean vs Δ already spoke with a
    Δ (wide|thin) and ±pp ≠ 0, positive short%−gap% → ``short``; negative →
    ``gap``. Mid-Δ clash / 0pp stay silent. Signed pp alone hid which
    sleeve owns the spread (Screener unique vs dup / Yahoo mix Δ lead
    parity after short vs gap share Δ). Not a gate.
    """
    lean_vs_delta, _ = soft_allow_short_vs_gap_lean_vs_delta(events)
    if not str(lean_vs_delta or "").startswith("align ·"):
        return ""
    delta_pp, delta_sev = soft_allow_short_vs_gap_delta(events)
    if not delta_sev or delta_pp is None:
        return ""
    try:
        pp = float(delta_pp)
    except (TypeError, ValueError):
        return ""
    if abs(pp) < 1e-9:
        return ""
    return "short" if pp > 0 else "gap"


def soft_allow_short_delta_moods(
    events: list[dict[str, Any]] | None,
) -> tuple[str, bool]:
    """Pair lean/Δ mood vs bench/young lean/Δ mood (display only).

    Returns ``(bit, warn)``. When both lean vs Δ already spoke with an
    align severity (``wide|thin``): same → ``align · both wide|thin``;
    crossed → ``clash · short/gap … · bench/young …``. Mid-Δ clash /
    missing side stay silent. Dual wide warns (Yahoo mix share vs gap
    wide-align warn); clash warns. Side-by-side lean/Δ labels alone hid
    whether pair ownership spread mood matches primary-bench vs young
    (Yahoo mix share vs gap + portfolio AI speak-both-sides after short
    vs gap + bench vs young Δ). Δ lead size nest still deferred. Not a
    gate.
    """
    pair_lvd, _ = soft_allow_short_vs_gap_lean_vs_delta(events)
    bench_lvd, _ = soft_allow_short_history_bench_vs_young_lean_vs_delta(
        events
    )
    pair_s = str(pair_lvd or "")
    bench_s = str(bench_lvd or "")
    if not pair_s.startswith("align · ") or not bench_s.startswith(
        "align · "
    ):
        return "", False
    pair_sev = pair_s[len("align · ") :].strip()
    bench_sev = bench_s[len("align · ") :].strip()
    if pair_sev not in {"wide", "thin"} or bench_sev not in {"wide", "thin"}:
        return "", False
    if pair_sev == bench_sev:
        # Dual wide agreement ≠ calm confirm (Yahoo mix share vs gap).
        return f"align · both {pair_sev}", pair_sev == "wide"
    return (
        f"clash · short/gap {pair_sev} · bench/young {bench_sev}",
        True,
    )


def _short_lean_verb(lean: str) -> str:
    """``align`` / ``clash`` verb from a short lean bit (else ``\"\"``)."""
    raw = str(lean or "").strip()
    if raw.startswith("align ·"):
        return "align"
    if raw.startswith("clash ·"):
        return "clash"
    return ""


def soft_allow_short_lean_moods(
    events: list[dict[str, Any]] | None,
) -> tuple[str, bool]:
    """Pair lean verb vs bench/young lean verb (display only).

    Returns ``(bit, warn)``. When both short vs gap lean and bench vs
    young lean already spoke: same → ``align · both align|clash``;
    crossed → ``clash · short/gap … · bench/young …``. Missing lean
    silent. Dual-clash + crossed warn; both-align speaks, no warn.
    Side-by-side lean labels + Δ moods alone hid whether the lean
    *verb* matches (wide Δ mood can still sit on short/gap clash vs
    bench/young align — Window A close sleeve lean moods + FinRobot +
    portfolio AI speak-both-sides). Prefixed ``short lean moods`` so
    ``short Δ moods`` ownership-spread mood stays distinct. Not a gate.
    """
    pair_lean, _ = soft_allow_short_vs_gap_lean(events)
    bench_lean, _ = soft_allow_short_history_bench_vs_young_lean(events)
    pair_v = _short_lean_verb(pair_lean)
    bench_v = _short_lean_verb(bench_lean)
    if not pair_v or not bench_v:
        return "", False
    if pair_v == bench_v:
        # Dual-clash agreement ≠ calm confirm (share/lean both-clash).
        return f"align · both {pair_v}", pair_v == "clash"
    return (
        f"clash · short/gap {pair_v} · bench/young {bench_v}",
        True,
    )


def soft_allow_short_lean_vs_delta_moods(
    events: list[dict[str, Any]] | None,
) -> tuple[str, bool]:
    """Lean moods verb vs Δ moods verb (display only).

    Returns ``(bit, warn)``. When both lean moods and Δ moods already
    spoke: same → ``align · both align|clash``; crossed →
    ``clash · lean … · Δ …``. Missing either side silent. Dual-clash +
    crossed warn; both-align speaks, no warn. Side-by-side lean moods +
    Δ moods alone hid whether the two *relationships* agree (wide Δ
    mood align can still sit on lean moods clash — Window A close
    sleeve lean vs Δ moods + FinRobot + portfolio AI speak-both-sides).
    Prefixed ``short lean vs Δ moods`` in the glance bit so lean moods
    and Δ moods stay distinct. Not a gate.
    """
    lean_moods, _ = soft_allow_short_lean_moods(events)
    delta_moods, _ = soft_allow_short_delta_moods(events)
    lean_v = _short_lean_verb(lean_moods)
    delta_v = _short_lean_verb(delta_moods)
    if not lean_v or not delta_v:
        return "", False
    if lean_v == delta_v:
        # Dual-clash agreement ≠ calm confirm (share/lean both-clash).
        return f"align · both {lean_v}", lean_v == "clash"
    return f"clash · lean {lean_v} · Δ {delta_v}", True


def soft_allow_short_delta_lead_moods(
    events: list[dict[str, Any]] | None,
) -> tuple[str, bool]:
    """Pair Δ lead polarity vs bench/young Δ lead polarity (display only).

    Returns ``(bit, warn)``. When both ``short|gap`` and ``bench|young``
    Δ leads already spoke: same polarity →
    ``align · both adverse|healthy``; crossed →
    ``clash · short/gap … · bench/young …``. Missing either lead silent.
    Adverse = ``short|bench`` (pair short-history sleeve or primary-bench
    sleeve); healthy = ``gap|young`` (anchor-gap sleeve or young/short
    remainder). Dual adverse + crossed warn; both healthy calm.
    Side-by-side ``short Δ lead · short`` and ``short bench Δ lead ·
    bench`` alone hid whether pair ownership and bench/young ownership
    pull the same way (Screener junk/unique Δ lead moods + FinRobot +
    portfolio AI speak-both-sides after short lean vs Δ moods). Prefixed
    ``short Δ lead moods`` in the glance bit so ``short Δ moods``
    severity match stays distinct. Not a gate.
    """
    pair_lead = soft_allow_short_vs_gap_delta_lead(events)
    bench_lead = soft_allow_short_history_bench_vs_young_delta_lead(events)
    pair_s = str(pair_lead or "").strip()
    bench_s = str(bench_lead or "").strip()
    if pair_s not in {"short", "gap"} or bench_s not in {"bench", "young"}:
        return "", False
    pair_adverse = pair_s == "short"
    bench_adverse = bench_s == "bench"
    if pair_adverse == bench_adverse:
        band = "adverse" if pair_adverse else "healthy"
        # Dual adverse agreement ≠ calm confirm (Screener Δ lead moods).
        return f"align · both {band}", pair_adverse
    return (
        f"clash · short/gap {pair_s} · bench/young {bench_s}",
        True,
    )


def soft_allow_short_history_last_vs_share(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last short freshness vs short+gap pair share lean (display only).

    Returns ``(bit, warn)``. Cursor age ≠ pair ownership heat. Extremes
    only: ``fresh``↔``hot`` and ``expired``↔``quiet`` speak ``align``;
    crossed pairs speak ``clash`` (warn). ``aging`` / mid share stay
    silent — gap last/share parity + RyanJHamby triad + FinRobot
    last-row age + portfolio AI speak-both-sides after last freshness +
    ``short_pair_share`` alone hid the relationship. Uses short÷(short+gap)
    (already spoken via ``vs gap``). Ring ownership uses
    ``soft_allow_short_history_last_vs_ring_share`` (short÷ring; pair
    silent when no gap). Not a gate.
    """
    last_fresh = soft_allow_short_history_last_freshness(events, now=now)
    pair = soft_allow_short_pair_share(events)
    if (
        pair is None
        or last_fresh not in {"fresh", "expired"}
        or pair[2] not in {"hot", "quiet"}
    ):
        return "", False
    severity = pair[2]
    live_age = last_fresh == "fresh"
    hot_share = severity == "hot"
    if live_age == hot_share:
        return f"align · {last_fresh} · {severity}", False
    return f"clash · {last_fresh} · {severity}", True


def soft_allow_short_history_last_vs_ring_share(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last short freshness vs short÷ring share lean (display only).

    Returns ``(bit, warn)``. Cursor age ≠ ring ownership heat. Extremes
    only: ``fresh``↔``hot`` and ``expired``↔``quiet`` speak ``align``;
    crossed pairs speak ``clash`` (warn). ``aging`` / mid share stay
    silent — gap last/share parity on short÷ring after ring share
    shipped; pair last/share stays on ``vs gap`` and is silent when
    there is no gap (short-only ring hid age≠ring). RyanJHamby triad +
    FinRobot last-row age + portfolio AI speak-both-sides + xang1234
    #668. Not a gate.
    """
    last_fresh = soft_allow_short_history_last_freshness(events, now=now)
    short_n, _share, severity = soft_allow_short_history_share(events)
    if (
        short_n <= 0
        or last_fresh not in {"fresh", "expired"}
        or severity not in {"hot", "quiet"}
    ):
        return "", False
    live_age = last_fresh == "fresh"
    hot_share = severity == "hot"
    if live_age == hot_share:
        return f"align · {last_fresh} · {severity}", False
    return f"clash · {last_fresh} · {severity}", True


def soft_allow_short_history_last_vs_lean(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last short freshness vs short/gap lean (display only).

    Returns ``(bit, warn)``. Cursor age ≠ lean agreement. Extremes only:
    ``fresh``↔ lean ``align`` and ``expired``↔ lean ``clash`` speak
    ``align``; crossed pairs speak ``clash`` (warn). ``aging`` / silent
    lean stay silent — gap last/lean parity + RyanJHamby triad +
    FinRobot last-row age + portfolio AI speak-both-sides after last
    freshness + short vs gap lean alone hid the relationship. Short÷ring
    share / short-vs-other lean still deferred. Not a gate.
    """
    last_fresh = soft_allow_short_history_last_freshness(events, now=now)
    lean, _lean_warn = soft_allow_short_vs_gap_lean(events)
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


def soft_allow_short_history_last_lead_vs_lean(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last/lead freshness vs last/lean relationship agreement (display only).

    Returns ``(bit, warn)``. Age↔name-vs-lead ≠ age↔lean. When both
    already spoke: same verb speaks ``align · both align|clash`` —
    ``both align`` stays calm; ``both clash`` warns (dual-clash agreement
    ≠ quiet confirm). Crossed verbs speak
    ``clash · lead align|clash · lean align|clash`` (warn). Missing
    either stays silent — gap lead/lean parity + FinRobot last-row age +
    portfolio AI speak-both-sides + RyanJHamby severity after short
    last/lead + last/lean alone hid whether cursor-vs-owner and age↔lean
    agree *and* whether dual-clash agreement is adverse. Side-by-side
    bits are not transitive. Short÷ring share still deferred (no
    ``×N · P%``). Not a gate.
    """
    lead_bit, _ = soft_allow_short_history_last_vs_lead_freshness(
        events, now=now
    )
    lean_bit, _ = soft_allow_short_history_last_vs_lean(events, now=now)
    if not lead_bit or not lean_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    lead_verb = _verb(lead_bit)
    lean_verb = _verb(lean_bit)
    if lead_verb is None or lean_verb is None:
        return "", False
    if lead_verb == lean_verb:
        return f"align · both {lead_verb}", lead_verb == "clash"
    return f"clash · lead {lead_verb} · lean {lean_verb}", True


def soft_allow_short_history_last_lead_vs_share(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last/lead freshness vs last/share relationship agreement (display only).

    Returns ``(bit, warn)``. Age↔name-vs-lead ≠ age↔share heat. When both
    already spoke: same verb speaks ``align · both align|clash`` —
    ``both align`` stays calm; ``both clash`` warns (dual-clash agreement
    ≠ quiet confirm). Crossed verbs speak
    ``clash · lead align|clash · share align|clash`` (warn). Missing
    either stays silent — gap lead/share parity + FinRobot last-row age +
    portfolio AI speak-both-sides + RyanJHamby severity after short
    last/lead + last/share alone hid whether cursor-vs-owner and
    ownership-heat agree *and* whether dual-clash agreement is adverse.
    Lead/lean + share/lean are not transitive with this edge. Short÷ring
    lead/ring closes the ring triangle; short-vs-other lean still
    deferred. Not a gate.
    """
    lead_bit, _ = soft_allow_short_history_last_vs_lead_freshness(
        events, now=now
    )
    share_bit, _ = soft_allow_short_history_last_vs_share(events, now=now)
    if not lead_bit or not share_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    lead_verb = _verb(lead_bit)
    share_verb = _verb(share_bit)
    if lead_verb is None or share_verb is None:
        return "", False
    if lead_verb == share_verb:
        return f"align · both {lead_verb}", lead_verb == "clash"
    return f"clash · lead {lead_verb} · share {share_verb}", True


def soft_allow_short_history_last_lead_vs_ring(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last/lead freshness vs last/ring relationship agreement (display only).

    Returns ``(bit, warn)``. Age↔name-vs-lead ≠ age↔short÷ring heat. When
    both already spoke: same verb speaks ``align · both align|clash`` —
    ``both align`` stays calm; ``both clash`` warns (dual-clash agreement
    ≠ quiet confirm). Crossed verbs speak
    ``clash · lead align|clash · ring align|clash`` (warn). Missing
    either stays silent — gap lead/share parity on short÷ring after
    last/lead + last/ring; pair ``short lead/share`` stays on
    short÷(short+gap) and is silent on short-only rings. Lead/lean +
    ring/lean are not transitive with this edge. FinRobot last-row age +
    portfolio AI speak-both-sides + RyanJHamby severity + xang1234 #668.
    Side-by-side last/lead + last/ring alone hid whether cursor-vs-owner
    and ring ownership heat agree. Not a gate.
    """
    lead_bit, _ = soft_allow_short_history_last_vs_lead_freshness(
        events, now=now
    )
    ring_bit, _ = soft_allow_short_history_last_vs_ring_share(
        events, now=now
    )
    if not lead_bit or not ring_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    lead_verb = _verb(lead_bit)
    ring_verb = _verb(ring_bit)
    if lead_verb is None or ring_verb is None:
        return "", False
    if lead_verb == ring_verb:
        return f"align · both {lead_verb}", lead_verb == "clash"
    return f"clash · lead {lead_verb} · ring {ring_verb}", True


def soft_allow_short_history_last_share_vs_ring(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last/share vs last/ring relationship agreement (display only).

    Returns ``(bit, warn)``. Age↔short÷(short+gap) ≠ age↔short÷ring.
    When both already spoke: same verb speaks
    ``align · both align|clash`` — ``both align`` stays calm; ``both
    clash`` warns (dual-clash agreement ≠ quiet confirm). Crossed verbs
    speak ``clash · share align|clash · ring align|clash`` (warn).
    Missing either stays silent — gap lead/share-style meta on pair vs
    ring after last/share + last/ring; pair ``short share/lean`` and
    ``short ring/lean`` stay on lean edges and are not transitive with
    this edge. FinRobot last-row age + portfolio AI speak-both-sides +
    RyanJHamby severity + xang1234 #668. Side-by-side last/share +
    last/ring alone hid whether pair ownership heat and ring ownership
    heat agree. Closes share↔ring↔lean with share/lean + ring/lean and
    lead↔share↔ring with lead/share + lead/ring. Short-vs-other lean
    still deferred. Not a gate.
    """
    share_bit, _ = soft_allow_short_history_last_vs_share(events, now=now)
    ring_bit, _ = soft_allow_short_history_last_vs_ring_share(
        events, now=now
    )
    if not share_bit or not ring_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    share_verb = _verb(share_bit)
    ring_verb = _verb(ring_bit)
    if share_verb is None or ring_verb is None:
        return "", False
    if share_verb == ring_verb:
        return f"align · both {share_verb}", share_verb == "clash"
    return f"clash · share {share_verb} · ring {ring_verb}", True


def soft_allow_short_history_last_share_vs_lean(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last/share vs last/lean relationship agreement (display only).

    Returns ``(bit, warn)``. Age↔share ≠ age↔lean. When both already
    spoke: same verb speaks ``align · both align|clash`` — ``both
    align`` stays calm; ``both clash`` warns (dual-clash agreement ≠
    quiet confirm). Crossed verbs speak
    ``clash · share align|clash · lean align|clash`` (warn). Missing
    either stays silent — gap share/lean parity + FinRobot last-row age +
    portfolio AI speak-both-sides + RyanJHamby severity after short
    last/share + last/lean alone hid whether the two relationships agree
    *and* whether dual-clash agreement is adverse. Short÷ring /
    short-vs-other lean still deferred. Not a gate.
    """
    share_bit, _ = soft_allow_short_history_last_vs_share(events, now=now)
    lean_bit, _ = soft_allow_short_history_last_vs_lean(events, now=now)
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
        return f"align · both {share_verb}", share_verb == "clash"
    return f"clash · share {share_verb} · lean {lean_verb}", True


def soft_allow_short_history_last_ring_vs_lean(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last/ring vs last/lean relationship agreement (display only).

    Returns ``(bit, warn)``. Age↔short÷ring ≠ age↔short/gap lean. When
    both already spoke: same verb speaks ``align · both align|clash`` —
    ``both align`` stays calm; ``both clash`` warns (dual-clash
    agreement ≠ quiet confirm). Crossed verbs speak
    ``clash · ring align|clash · lean align|clash`` (warn). Missing
    either stays silent — gap share/lean parity on short÷ring after
    last/ring + last/lean; pair ``short share/lean`` stays on
    short÷(short+gap) and is silent on short-only rings (last/lean needs
    a gap). FinRobot last-row age + portfolio AI speak-both-sides +
    RyanJHamby severity + xang1234 #668. Side-by-side last/ring +
    last/lean alone hid whether the two relationships agree. Not a gate.
    """
    ring_bit, _ = soft_allow_short_history_last_vs_ring_share(
        events, now=now
    )
    lean_bit, _ = soft_allow_short_history_last_vs_lean(events, now=now)
    if not ring_bit or not lean_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    ring_verb = _verb(ring_bit)
    lean_verb = _verb(lean_bit)
    if ring_verb is None or lean_verb is None:
        return "", False
    if ring_verb == lean_verb:
        return f"align · both {ring_verb}", ring_verb == "clash"
    return f"clash · ring {ring_verb} · lean {lean_verb}", True


def soft_allow_short_history_vs_scan_clash(
    events: list[dict[str, Any]] | None,
    *,
    scan_freshness: str = "",
    now: datetime | None = None,
    short_pin_size: str = "",
    scan_pin_size: str = "",
    keep_cash_pin_size: str = "",
    keep_memory_pin_size: str = "",
    keep_gap_pin_size: str = "",
    keep_soft_pin_size: str = "",
) -> tuple[str, bool]:
    """Short cursor vs scan archive generation (display only).

    Returns ``(bit, warn)``. When newest short-history clock ≠ scan
    band (``expired``≡``stale``), speak
    ``clash · short expired|aging|fresh · scan fresh|aging|stale`` then
    optional short pin (``short-only`` via ``short_pin_size``) then
    optional scan pin (``scan-only`` via ``scan_pin_size``) — absolute
    ``N short`` lied young/short fail-open ownership was the cursor
    print; the newest short stamp is a sole published pin like soft
    last / gap cursor (gap≠scan ``gap-only · scan-only`` / soft≠scan
    ``soft-only · scan-only`` parity + #647 / #531 / #668). When
    short≠cash is silent (short matches cash), optional
    ``keep_cash_pin_size`` appends the cash pin so scan alone cannot
    hide the match (gap≠scan keep-cash + #660 / #647 / #531). When
    short≠memory is silent (short matches advisory), optional
    ``keep_memory_pin_size`` appends ``laya-only`` / ``debate-only`` /
    ``×2 · 100%`` so scan alone cannot hide the match (gap≠scan
    keep-memory + #660 / #647 / #531). When short≠gap is silent
    (short matches gap cursor), optional ``keep_gap_pin_size`` appends
    ``gap-only`` so scan alone cannot hide the match (soft≠scan
    keep-gap + #660 / #647 / #531). When soft≠short is silent (short
    matches soft last), optional ``keep_soft_pin_size`` appends
    ``soft-only`` so scan alone cannot hide the match (gap≠scan
    keep-soft + #660 / #647 / #531 / #668). Same band / missing either
    silent. Soft-allow *last* matching the scan (and gap≠scan alone)
    can still hide a staler young/short cursor — speak both sides
    (xang1234 #549 / e3c84e1 generation coherence + gap≠scan parity +
    portfolio AI speak-both-sides). A fresh scan does not make an
    expired short-history fail-open live. Not a gate.
    """
    scan = str(scan_freshness or "").strip().casefold()
    if scan not in {"fresh", "aging", "stale"}:
        return "", False
    short_band = soft_allow_short_history_last_freshness(events, now=now)
    short_clock = _soft_allow_gap_clock_tone(short_band)
    if not short_clock or short_clock == scan:
        return "", False
    short_speak = (
        short_band
        if short_band in {"fresh", "aging", "expired"}
        else short_clock
    )
    raw_short = str(short_pin_size or "").strip().lstrip("·").strip()
    short_pin = f" · {raw_short}" if raw_short else ""
    raw_scan = str(scan_pin_size or "").strip().lstrip("·").strip()
    scan_pin = f" · {raw_scan}" if raw_scan else ""
    raw_cash = str(keep_cash_pin_size or "").strip().lstrip("·").strip()
    keep_cash = f" · {raw_cash}" if raw_cash else ""
    raw_mem = str(keep_memory_pin_size or "").strip().lstrip("·").strip()
    keep_mem = f" · {raw_mem}" if raw_mem else ""
    raw_gap = str(keep_gap_pin_size or "").strip().lstrip("·").strip()
    keep_gap = f" · {raw_gap}" if raw_gap else ""
    raw_soft = str(keep_soft_pin_size or "").strip().lstrip("·").strip()
    keep_soft = f" · {raw_soft}" if raw_soft else ""
    return (
        f"clash · short {short_speak} · scan {scan}"
        f"{short_pin}{scan_pin}{keep_cash}{keep_mem}{keep_gap}{keep_soft}",
        True,
    )


def soft_allow_short_history_vs_cash_clock_clash(
    events: list[dict[str, Any]] | None,
    *,
    cash_band: str = "",
    now: datetime | None = None,
    short_pin_size: str = "",
    cash_pin_size: str = "",
    keep_scan_pin_size: str = "",
    keep_memory_pin_size: str = "",
    keep_gap_pin_size: str = "",
    keep_soft_pin_size: str = "",
) -> tuple[str, bool]:
    """Short cursor vs pinned cash-print generation (display only).

    Returns ``(bit, warn)``. When newest short-history clock ≠ worst
    last-published cash sleeve (``expired``≡``stale``), speak
    ``clash · short expired|aging|fresh · cash fresh|aging|stale`` then
    optional short pin (``short-only`` via ``short_pin_size``) then
    optional cash pin (``US-only`` / ``US · 50%`` / ``×2 · 100%`` via
    ``cash_pin_size``) — gap≠cash ``gap-only · US-only`` / soft≠cash
    parity + #647 / #531 / #668. When short≠scan is silent (short
    matches the archive), optional ``keep_scan_pin_size`` appends
    ``scan-only`` so cash alone cannot hide the matched pin (gap≠cash
    keep-scan + #660 / #647 / #531). When short≠memory is silent
    (short matches advisory), optional ``keep_memory_pin_size`` appends
    the advisory pin so cash alone cannot hide the match (gap≠cash
    keep-memory + #660 / #647 / #531). When short≠gap is silent (short
    matches gap cursor), optional ``keep_gap_pin_size`` appends
    ``gap-only`` so cash alone cannot hide the match (soft≠cash
    keep-gap + #660 / #647 / #531). When soft≠short is silent (short
    matches soft last), optional ``keep_soft_pin_size`` appends
    ``soft-only`` so cash alone cannot hide the match (gap≠cash
    keep-soft + #660 / #647 / #531 / #668). Same band / missing either
    / live cash (no pin) silent. Soft-allow *last* matching the scan
    (and short≠scan alone) can still hide a short cursor that matches
    the archive but not the cash print — closes short↔cash beside
    short≠scan + soft↔cash + gap≠cash (xang1234 #549 / e3c84e1
    coherent generations + portfolio AI speak-both-sides + gap≠cash
    parity). Not a gate.
    """
    cash = str(cash_band or "").strip().casefold()
    if cash not in {"fresh", "aging", "stale"}:
        return "", False
    short_band = soft_allow_short_history_last_freshness(events, now=now)
    short_clock = _soft_allow_gap_clock_tone(short_band)
    if not short_clock or short_clock == cash:
        return "", False
    short_speak = (
        short_band
        if short_band in {"fresh", "aging", "expired"}
        else short_clock
    )
    raw_short = str(short_pin_size or "").strip().lstrip("·").strip()
    short_pin = f" · {raw_short}" if raw_short else ""
    raw_cash = str(cash_pin_size or "").strip().lstrip("·").strip()
    cash_pin = f" · {raw_cash}" if raw_cash else ""
    raw_keep = str(keep_scan_pin_size or "").strip().lstrip("·").strip()
    keep = f" · {raw_keep}" if raw_keep else ""
    raw_mem = str(keep_memory_pin_size or "").strip().lstrip("·").strip()
    keep_mem = f" · {raw_mem}" if raw_mem else ""
    raw_gap = str(keep_gap_pin_size or "").strip().lstrip("·").strip()
    keep_gap = f" · {raw_gap}" if raw_gap else ""
    raw_soft = str(keep_soft_pin_size or "").strip().lstrip("·").strip()
    keep_soft = f" · {raw_soft}" if raw_soft else ""
    return (
        f"clash · short {short_speak} · cash {cash}"
        f"{short_pin}{cash_pin}{keep}{keep_mem}{keep_gap}{keep_soft}",
        True,
    )


def soft_allow_short_history_vs_memory_clock_clash(
    events: list[dict[str, Any]] | None,
    *,
    laya_freshness: str = "",
    debate_freshness: str = "",
    now: datetime | None = None,
    short_pin_size: str = "",
    memory_pin_size: str = "",
    keep_scan_pin_size: str = "",
    keep_cash_pin_size: str = "",
    keep_gap_pin_size: str = "",
    keep_soft_pin_size: str = "",
) -> tuple[str, bool]:
    """Short cursor vs LAYA/debate memory generation (display only).

    Returns ``(bit, warn)``. When newest short-history clock ≠ LAYA
    and/or AI-debate clocks (``expired``≡``stale``), speak
    ``clash · short expired|aging|fresh · laya … · debate …`` then
    optional short pin (``short-only`` via ``short_pin_size``) then
    optional advisory pin (``laya-only`` / ``laya · 50%`` / ``×2 ·
    100%`` via ``memory_pin_size``) — gap≠memory ``gap-only`` +
    advisory pin / soft≠memory parity + #647 / #531 / #668. When
    short≠scan is silent (short matches the archive), optional
    ``keep_scan_pin_size`` appends ``scan-only`` so memory alone cannot
    hide the matched pin (gap≠memory keep-scan + #660 / #647 / #531).
    When short≠cash is silent (short matches cash), optional
    ``keep_cash_pin_size`` appends the cash pin so memory alone cannot
    hide the match (gap≠memory keep-cash + #660 / #647 / #531). When
    short≠gap is silent (short matches gap cursor), optional
    ``keep_gap_pin_size`` appends ``gap-only`` so memory alone cannot
    hide the match (soft≠memory keep-gap + #660 / #647 / #531). When
    soft≠short is silent (short matches soft last), optional
    ``keep_soft_pin_size`` appends ``soft-only`` so memory alone cannot
    hide the match (gap≠memory keep-soft + #660 / #647 / #531 / #668).
    Same band / missing either side silent. Soft-allow *last* matching
    the scan (and short≠scan / short≠cash alone) can still hide a
    young/short cursor that matches the archive or cash print but not
    the advisory print — closes short↔memory beside short≠scan +
    short≠cash + soft↔memory + gap≠memory (xang1234 #549 / e3c84e1 +
    FinRobot last-row + portfolio AI speak-both-sides). Not a gate.
    """
    short_band = soft_allow_short_history_last_freshness(events, now=now)
    short_clock = _soft_allow_gap_clock_tone(short_band)
    if not short_clock:
        return "", False
    short_speak = (
        short_band
        if short_band in {"fresh", "aging", "expired"}
        else short_clock
    )
    bits: list[str] = []
    for name, tone in (("laya", laya_freshness), ("debate", debate_freshness)):
        t = str(tone or "").strip().casefold()
        if t == "expired":
            t = "stale"
        elif t == "unknown":
            t = "fresh"
        if t not in {"fresh", "aging", "stale"} or t == short_clock:
            continue
        bits.append(f"{name} {t}")
    if not bits:
        return "", False
    raw_short = str(short_pin_size or "").strip().lstrip("·").strip()
    short_pin = f" · {raw_short}" if raw_short else ""
    raw_mem = str(memory_pin_size or "").strip().lstrip("·").strip()
    mem_pin = f" · {raw_mem}" if raw_mem else ""
    raw_keep = str(keep_scan_pin_size or "").strip().lstrip("·").strip()
    keep = f" · {raw_keep}" if raw_keep else ""
    raw_cash = str(keep_cash_pin_size or "").strip().lstrip("·").strip()
    keep_cash = f" · {raw_cash}" if raw_cash else ""
    raw_gap = str(keep_gap_pin_size or "").strip().lstrip("·").strip()
    keep_gap = f" · {raw_gap}" if raw_gap else ""
    raw_soft = str(keep_soft_pin_size or "").strip().lstrip("·").strip()
    keep_soft = f" · {raw_soft}" if raw_soft else ""
    return (
        f"clash · short {short_speak} · {' · '.join(bits)}"
        f"{short_pin}{mem_pin}{keep}{keep_cash}{keep_gap}{keep_soft}",
        True,
    )


def soft_allow_short_history_vs_gap_clock_clash(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
    short_pin_size: str = "",
    gap_pin_size: str = "",
    keep_scan_pin_size: str = "",
    keep_cash_pin_size: str = "",
    keep_memory_pin_size: str = "",
    keep_soft_pin_size: str = "",
) -> tuple[str, bool]:
    """Short cursor vs gap cursor generation (display only).

    Returns ``(bit, warn)``. When newest short-history clock ≠ newest
    anchor-gap cursor (``expired``≡``stale``), speak
    ``clash · short expired|aging|fresh · gap …`` then optional short
    pin (``short-only`` via ``short_pin_size``) then optional gap pin
    (``gap-only`` via ``gap_pin_size``) — soft≠gap ``soft-only ·
    gap-only`` / gap≠scan sole-pin parity + #647 / #531 / #668. When
    short≠scan is silent (short matches the archive), optional
    ``keep_scan_pin_size`` appends ``scan-only`` so gap alone cannot
    hide the match (soft≠gap keep-scan + #660 / #647 / #531). When
    short≠cash is silent, optional ``keep_cash_pin_size`` appends the
    cash pin; when short≠memory is silent, optional
    ``keep_memory_pin_size`` appends the advisory pin; when soft≠short
    is silent, optional ``keep_soft_pin_size`` appends ``soft-only``.
    Same band / missing either silent. Short matching scan/cash/memory
    (and soft≠gap / short↔gap *count* lean alone) can still hide a
    staler gap cursor — closes short↔gap generation beside
    short≠scan|/cash|/memory + soft≠gap (xang1234 #549 / e3c84e1 +
    portfolio AI speak-both-sides; count lean ≠ clock). Not a gate.
    """
    short_band = soft_allow_short_history_last_freshness(events, now=now)
    short_clock = _soft_allow_gap_clock_tone(short_band)
    if not short_clock:
        return "", False
    gap_band = soft_allow_anchor_gap_last_freshness(events, now=now)
    gap_clock = _soft_allow_gap_clock_tone(gap_band)
    if not gap_clock or short_clock == gap_clock:
        return "", False
    short_speak = (
        short_band
        if short_band in {"fresh", "aging", "expired"}
        else short_clock
    )
    gap_speak = (
        gap_band if gap_band in {"fresh", "aging", "expired"} else gap_clock
    )
    raw_short = str(short_pin_size or "").strip().lstrip("·").strip()
    short_pin = f" · {raw_short}" if raw_short else ""
    raw_gap = str(gap_pin_size or "").strip().lstrip("·").strip()
    gap_pin = f" · {raw_gap}" if raw_gap else ""
    raw_scan = str(keep_scan_pin_size or "").strip().lstrip("·").strip()
    keep_scan = f" · {raw_scan}" if raw_scan else ""
    raw_cash = str(keep_cash_pin_size or "").strip().lstrip("·").strip()
    keep_cash = f" · {raw_cash}" if raw_cash else ""
    raw_mem = str(keep_memory_pin_size or "").strip().lstrip("·").strip()
    keep_mem = f" · {raw_mem}" if raw_mem else ""
    raw_soft = str(keep_soft_pin_size or "").strip().lstrip("·").strip()
    keep_soft = f" · {raw_soft}" if raw_soft else ""
    return (
        f"clash · short {short_speak} · gap {gap_speak}"
        f"{short_pin}{gap_pin}{keep_scan}{keep_cash}{keep_mem}{keep_soft}",
        True,
    )


def format_soft_allow_short_history_bit(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
    scan_freshness: str = "",
    cash_band: str = "",
    laya_freshness: str = "",
    debate_freshness: str = "",
    short_pin_size: str = "",
    scan_pin_size: str = "",
    cash_pin_size: str = "",
    memory_pin_size: str = "",
    gap_pin_size: str = "",
    keep_scan_pin_size: str = "",
    keep_cash_pin_size: str = "",
    keep_memory_pin_size: str = "",
    keep_gap_pin_size: str = "",
    keep_soft_pin_size: str = "",
) -> str:
    """Compact ``N short · N bench · … · vs N young · … · last SYM · …``.

    Zero silent. When any short row names a primary RS benchmark
    (SPY/BTC), ``N bench · [hot|quiet ·] P%`` sits right after the count
    so absolute bench ≠ bench÷short (RyanJHamby cache + #679 + portfolio
    AI count≠share) and young-listing
    short ≠ a stale/thin primary (xang1234 #679 after #668). When bench
    already spoke, ``vs N young · [strong|thin ·] P%`` follows so bench%
    alone cannot hide usable young/short fail-opens (gap vs other /
    Screener junk vs ok sides); when both severities lean, ``short bench
    vs young align|clash`` follows so sides alone cannot hide lean
    agreement; when lean already spoke, ``short bench Δ wide|thin ·
    ±Npp`` then ``short bench lean/Δ align|clash`` follow so lean labels
    alone cannot hide how far bench÷short sits vs young÷short (short vs
    gap / Screener junk vs ok share Δ + lean vs Δ parity; mid Δ silent
    on the Δ bit; lean-spoke + mid → clash · lean · Δ mid); when lean
    vs Δ already spoke with a Δ and ±pp ≠ 0, ``short bench Δ lead ·
    bench|young`` follows so the signed spread alone cannot hide which
    sleeve owns it (short vs gap / unique vs dup Δ lead parity; lead
    size still deferred). ``last SYM``
    follows so lean cannot clip the cursor (#546).     Cursor age
    (``fresh`` / ``aging`` / ``expired``) follows the name so a live
    ticker ≠ a live fail-open (gap last-freshness parity + RyanJHamby +
    FinRobot last-row age; unknown stamp silent). When last freshness
    extremes + bench vs young lean already spoke, ``short last/bench
    align|clash`` follows so age labels + bench/young lean alone cannot
    hide age≠lean (gap last/lean + short last/lean parity after #679).
    When short clock ≠
    scan archive band, ``clash · short … · scan …`` follows age so a
    soft-allow last matching the scan cannot hide a staler young/short
    cursor (xang1234 #549 / e3c84e1 + gap≠scan parity); optional
    ``short-only · scan-only`` sole pins (#647 / #531 / #668); optional
    keep cash / memory / gap-only pins when short≠cash / short≠memory /
    short≠gap are silent. When short clock ≠ pinned cash band,
    ``clash · short … · cash …`` follows so short matching the scan
    cannot hide a staler cash print (gap≠cash / short≠scan parity);
    optional ``short-only`` + cash pin; optional keep ``scan-only`` /
    memory / gap-only when short≠scan / short≠memory / short≠gap are
    silent. When short clock ≠ LAYA and/or AI-debate, ``clash · short …
    · laya … · debate …`` follows so short matching the scan or cash
    cannot hide a staler advisory print (gap≠memory / soft≠memory /
    short≠scan / short≠cash parity); optional ``short-only`` + advisory
    pin; optional keep ``scan-only`` / cash / gap-only when short≠scan /
    short≠cash / short≠gap are silent. When short clock ≠ gap cursor,
    ``clash · short … · gap …`` follows so short matching
    scan/cash/memory cannot hide a staler gap print (soft≠gap /
    short≠scan parity; count lean ≠ clock); optional ``short-only ·
    gap-only``; optional keep ``scan-only`` / cash / memory when those
    short≠* clashes are silent.
    Symbol lead / n=1 / tied follows the cursor
    (last ≠ ring ownership; gap symbol lead parity); when lead spoke,
    ``last vs lead`` / ``agree`` sits right after so cursor≠owner is not
    clipped; when last freshness extremes + last-vs-lead already spoke,
    ``short last/lead align|clash`` follows so age labels + name agree
    alone cannot hide age≠owner (gap last/lead freshness parity); when
    a runner exists, ``ahead wide|thin · +K`` then ``vs SYM · N · P%``
    follow so ownership % ≠ how far ahead ≠ who is #2 (gap margin/sides
    parity; sole 100% omits).     When ``N gap`` also spoke, ``vs gap ·
    [strong|thin ·] N · P%`` follows so absolute short+gap counts ≠
    ownership of the RS fail-open pair; when last freshness extremes +
    pair share lean, ``short last/share align|clash`` follows so age
    labels + ownership heat alone cannot hide age≠share (gap last/share
    parity; short÷pair, not short÷ring); when last/lead + last/share
    already spoke, ``short lead/share align|clash`` follows so
    cursor-vs-owner and ownership heat cannot hide non-agreement or
    dual-clash (gap lead/share parity); when both pair severities lean,
    ``short vs gap align|clash`` follows so sides alone cannot hide lean
    agreement (junk vs ok / gap vs other lean parity); when lean already
    spoke, ``short Δ wide|thin · ±Npp`` then ``short lean/Δ align|clash``
    follow so lean labels alone cannot hide how far pair ownership sits
    (Screener junk vs ok / unique vs dup share Δ + lean vs Δ parity;
    mid Δ silent on the Δ bit; lean-spoke + mid → clash · lean · Δ mid);
    when lean vs Δ already spoke with a Δ and ±pp ≠ 0, ``short Δ lead ·
    short|gap`` follows so the signed spread alone cannot hide which
    sleeve owns it (unique vs dup / Yahoo mix Δ lead parity);     when both
    pair and bench lean/Δ already spoke with align severities,
    ``short Δ moods align|clash`` follows so side-by-side ownership
    spreads cannot hide whether pair mood matches bench/young mood
    (Yahoo mix share vs gap + portfolio AI speak-both-sides); when both
    pair and bench lean already spoke, ``short lean moods align|clash``
    follows so Δ mood match alone cannot hide lean *verb* mismatch
    (Window A close sleeve lean moods + FinRobot + portfolio AI
    speak-both-sides);     when lean moods + Δ moods already spoke,
    ``short lean vs Δ moods align|clash`` follows so side-by-side
    relationship verbs alone cannot hide whether they agree (Window A
    close sleeve lean vs Δ moods + FinRobot + portfolio AI
    speak-both-sides); when both pair and bench Δ leads already spoke,
    ``short Δ lead moods align|clash`` follows so side-by-side lead
    names alone cannot hide whether ownership polarity agrees
    (Screener junk/unique Δ lead moods + FinRobot + portfolio AI
    speak-both-sides; adverse = short|bench · healthy = gap|young).
    When last freshness extremes + lean already spoke, ``short last/lean
    align|clash`` follows so age labels + lean labels alone cannot hide
    age≠lean (gap last/lean parity); when last/lead + last/lean already
    spoke, ``short lead/lean align|clash`` follows so side-by-side
    age↔owner and age↔lean cannot hide non-transitive disagreement or
    dual-clash agreement (gap lead/lean parity); when last/share +
    last/lean already spoke, ``short share/lean align|clash`` follows so
    the two age relationships cannot hide non-agreement or dual-clash
    (gap share/lean parity). Ring share (``hot|quiet · P%``) sits after
    lead/sides / ``n=1`` so absolute ``N short`` ≠ short÷ring (gap share
    parity; short÷pair stays on ``vs gap`` / last/share). When last
    freshness extremes + ring share lean already spoke, ``short
    last/ring align|clash`` follows so age labels + ring heat alone
    cannot hide age≠ring (gap last/share on short÷ring; pair last/share
    stays silent when no gap).     When last/lead + last/ring already spoke,
    ``short lead/ring align|clash`` follows so cursor-vs-owner and ring
    heat cannot hide non-agreement or dual-clash (gap lead/share on
    short÷ring; pair lead/share stays on short÷(short+gap)). When
    last/share + last/ring already spoke, ``short share/ring
    align|clash`` follows so pair ownership heat and ring heat cannot
    hide non-agreement or dual-clash (closes share↔ring↔lean with
    share/lean + ring/lean and lead↔share↔ring with lead/share +
    lead/ring). When last/share + last/bench already spoke, ``short
    share/bench align|clash`` follows so pair ownership heat and
    age↔bench/young cannot hide non-agreement or dual-clash (gap
    share/lean + short share/lean parity after #679; lead/bench +
    lead/share are not transitive with this edge). When last/ring +
    last/bench already spoke, ``short ring/bench align|clash`` follows
    so ring ownership heat and age↔bench/young cannot hide
    non-agreement or dual-clash (closes ring↔bench↔share with
    share/bench + share/ring and lead↔ring↔bench with lead/bench +
    lead/ring; gap share/lean + short share/bench parity after #679).
    When last/ring + last/lean already spoke, ``short ring/lean
    align|clash`` follows so the two age relationships cannot hide
    non-agreement or dual-clash (gap share/lean on short÷ring; pair
    share/lean stays on short÷(short+gap)). Short-vs-other lean still
    deferred. Display only; not a gate.
    """
    n, ring_share, ring_sev = soft_allow_short_history_share(events)
    if n <= 0 or ring_share is None:
        return ""
    head = f"{n} short"
    bench_n, bench_share, bench_sev = soft_allow_short_history_bench_share(
        events
    )
    if bench_n > 0 and bench_share is not None:
        # Absolute ``N bench`` ≠ bench÷short (RyanJHamby cache chore +
        # #679 + portfolio AI count≠share after bare primary-bench count).
        if bench_sev in {"hot", "quiet"}:
            head = (
                f"{head} · {bench_n} bench · {bench_sev} · {bench_share:g}%"
            )
        else:
            head = f"{head} · {bench_n} bench · {bench_share:g}%"
        # Bench% alone hid young/short remainder (gap vs other /
        # Screener junk vs ok sides + portfolio AI speak-both-sides).
        young_n, young_share, young_sev = (
            soft_allow_short_history_bench_vs_young(events)
        )
        if young_share is not None:
            if young_sev in {"strong", "thin"}:
                head = (
                    f"{head} · vs {young_n} young · {young_sev} · "
                    f"{young_share:g}%"
                )
            else:
                head = f"{head} · vs {young_n} young · {young_share:g}%"
            young_lean, _ = soft_allow_short_history_bench_vs_young_lean(
                events
            )
            if young_lean:
                head = f"{head} · short bench vs young {young_lean}"
                # Lean alone hid how far bench÷short sits vs young÷short
                # (short vs gap / Screener junk vs ok share Δ parity).
                delta_pp, delta_sev = (
                    soft_allow_short_history_bench_vs_young_delta(events)
                )
                if delta_sev and delta_pp is not None:
                    sign = (
                        f"+{delta_pp:g}"
                        if delta_pp > 0
                        else f"{delta_pp:g}"
                    )
                    head = (
                        f"{head} · short bench Δ {delta_sev} · {sign}pp"
                    )
                lean_vs_delta, _ = (
                    soft_allow_short_history_bench_vs_young_lean_vs_delta(
                        events
                    )
                )
                if lean_vs_delta:
                    head = (
                        f"{head} · short bench lean/Δ {lean_vs_delta}"
                    )
                # Signed pp alone hid which sleeve owns the spread
                # (short vs gap / unique vs dup Δ lead parity).
                delta_lead = (
                    soft_allow_short_history_bench_vs_young_delta_lead(
                        events
                    )
                )
                if delta_lead:
                    head = (
                        f"{head} · short bench Δ lead · {delta_lead}"
                    )
    last = soft_allow_short_history_last_symbol(events)
    if last:
        head = f"{head} · last {last}"
        last_fresh = soft_allow_short_history_last_freshness(
            events, now=now
        )
        if last_fresh:
            head = f"{head} · {last_fresh}"
            last_vs_bench, _ = soft_allow_short_history_last_vs_bench_young(
                events, now=now
            )
            if last_vs_bench:
                head = f"{head} · short last/bench {last_vs_bench}"
            short_vs_scan, _ = soft_allow_short_history_vs_scan_clash(
                events,
                scan_freshness=scan_freshness,
                now=now,
                short_pin_size=short_pin_size,
                scan_pin_size=scan_pin_size,
                keep_cash_pin_size=keep_cash_pin_size,
                keep_memory_pin_size=keep_memory_pin_size,
                keep_gap_pin_size=keep_gap_pin_size,
                keep_soft_pin_size=keep_soft_pin_size,
            )
            if short_vs_scan:
                head = f"{head} · {short_vs_scan}"
            short_vs_cash, _ = soft_allow_short_history_vs_cash_clock_clash(
                events,
                cash_band=cash_band,
                now=now,
                short_pin_size=short_pin_size,
                cash_pin_size=cash_pin_size,
                keep_scan_pin_size=keep_scan_pin_size,
                keep_memory_pin_size=keep_memory_pin_size,
                keep_gap_pin_size=keep_gap_pin_size,
                keep_soft_pin_size=keep_soft_pin_size,
            )
            if short_vs_cash:
                head = f"{head} · {short_vs_cash}"
            short_vs_mem, _ = soft_allow_short_history_vs_memory_clock_clash(
                events,
                laya_freshness=laya_freshness,
                debate_freshness=debate_freshness,
                now=now,
                short_pin_size=short_pin_size,
                memory_pin_size=memory_pin_size,
                keep_scan_pin_size=keep_scan_pin_size,
                keep_cash_pin_size=keep_cash_pin_size,
                keep_gap_pin_size=keep_gap_pin_size,
                keep_soft_pin_size=keep_soft_pin_size,
            )
            if short_vs_mem:
                head = f"{head} · {short_vs_mem}"
            short_vs_gap_clock, _ = soft_allow_short_history_vs_gap_clock_clash(
                events,
                now=now,
                short_pin_size=short_pin_size,
                gap_pin_size=gap_pin_size,
                keep_scan_pin_size=keep_scan_pin_size,
                keep_cash_pin_size=keep_cash_pin_size,
                keep_memory_pin_size=keep_memory_pin_size,
                keep_soft_pin_size=keep_soft_pin_size,
            )
            if short_vs_gap_clock:
                head = f"{head} · {short_vs_gap_clock}"
    lead_bit, _lead_name, _lead_share = soft_allow_short_history_symbol_lead(
        events
    )
    if lead_bit:
        head = f"{head} · {lead_bit}"
        last_vs = soft_allow_short_history_symbol_last_vs_lead(events)
        if last_vs:
            head = f"{head} · {last_vs}"
            last_vs_lead_fresh, _ = (
                soft_allow_short_history_last_vs_lead_freshness(
                    events, now=now
                )
            )
            if last_vs_lead_fresh:
                head = f"{head} · short last/lead {last_vs_lead_fresh}"
                lead_vs_bench, _ = (
                    soft_allow_short_history_last_lead_vs_bench_young(
                        events, now=now
                    )
                )
                if lead_vs_bench:
                    head = f"{head} · short lead/bench {lead_vs_bench}"
        margin = soft_allow_short_history_symbol_lead_margin(events)
        if margin is not None:
            head = f"{head} · {margin[0]}"
            sides = soft_allow_short_history_symbol_lead_sides(events)
            if sides is not None:
                head = f"{head} · {sides[0]}"
    else:
        sample_gap = soft_allow_short_history_symbol_sample_gap(events)
        if sample_gap:
            head = f"{head} · {sample_gap}"
    # Ring share after ownership sample so ``N short`` ≠ short÷rows
    # (gap ``hot|quiet · P%`` parity; pair share stays on ``vs gap``).
    if ring_sev in {"hot", "quiet"}:
        head = f"{head} · {ring_sev} · {ring_share:g}%"
    else:
        head = f"{head} · {ring_share:g}%"
    last_vs_ring, _ = soft_allow_short_history_last_vs_ring_share(
        events, now=now
    )
    if last_vs_ring:
        head = f"{head} · short last/ring {last_vs_ring}"
        lead_vs_ring, _ = soft_allow_short_history_last_lead_vs_ring(
            events, now=now
        )
        if lead_vs_ring:
            head = f"{head} · short lead/ring {lead_vs_ring}"
        ring_vs_bench, _ = soft_allow_short_history_last_ring_vs_bench_young(
            events, now=now
        )
        if ring_vs_bench:
            head = f"{head} · short ring/bench {ring_vs_bench}"
    vs_gap = soft_allow_short_vs_gap(events)
    if vs_gap is not None:
        head = f"{head} · {vs_gap[0]}"
        last_vs_share, _ = soft_allow_short_history_last_vs_share(
            events, now=now
        )
        if last_vs_share:
            head = f"{head} · short last/share {last_vs_share}"
            share_vs_bench, _ = (
                soft_allow_short_history_last_share_vs_bench_young(
                    events, now=now
                )
            )
            if share_vs_bench:
                head = f"{head} · short share/bench {share_vs_bench}"
            lead_vs_share, _ = soft_allow_short_history_last_lead_vs_share(
                events, now=now
            )
            if lead_vs_share:
                head = f"{head} · short lead/share {lead_vs_share}"
            share_vs_ring, _ = soft_allow_short_history_last_share_vs_ring(
                events, now=now
            )
            if share_vs_ring:
                head = f"{head} · short share/ring {share_vs_ring}"
        lean, _ = soft_allow_short_vs_gap_lean(events)
        if lean:
            head = f"{head} · short vs gap {lean}"
            # Lean alone hid how far short÷pair sits vs gap÷pair
            # (Screener junk vs ok / unique vs dup share Δ parity).
            delta_pp, delta_sev = soft_allow_short_vs_gap_delta(events)
            if delta_sev and delta_pp is not None:
                sign = f"+{delta_pp:g}" if delta_pp > 0 else f"{delta_pp:g}"
                head = f"{head} · short Δ {delta_sev} · {sign}pp"
            lean_vs_delta, _ = soft_allow_short_vs_gap_lean_vs_delta(events)
            if lean_vs_delta:
                head = f"{head} · short lean/Δ {lean_vs_delta}"
            # Signed pp alone hid which pair sleeve owns the spread
            # (unique vs dup / Yahoo mix Δ lead parity).
            delta_lead = soft_allow_short_vs_gap_delta_lead(events)
            if delta_lead:
                head = f"{head} · short Δ lead · {delta_lead}"
            # Side-by-side pair lean/Δ + bench lean/Δ alone hid whether
            # ownership-spread moods agree (Yahoo mix share vs gap +
            # portfolio AI speak-both-sides after both Δ leads).
            delta_moods, _ = soft_allow_short_delta_moods(events)
            if delta_moods:
                head = f"{head} · short Δ moods {delta_moods}"
            # Δ mood match alone hid lean *verb* mismatch (Window A
            # close sleeve lean moods + FinRobot + portfolio AI).
            lean_moods, _ = soft_allow_short_lean_moods(events)
            if lean_moods:
                head = f"{head} · short lean moods {lean_moods}"
            # Side-by-side lean moods + Δ moods alone hid whether the
            # two relationships agree (Window A close sleeve lean vs Δ
            # moods + FinRobot + portfolio AI speak-both-sides).
            lean_vs_delta_moods, _ = soft_allow_short_lean_vs_delta_moods(
                events
            )
            if lean_vs_delta_moods:
                head = (
                    f"{head} · short lean vs Δ moods {lean_vs_delta_moods}"
                )
            # Side-by-side Δ leads alone hid whether ownership polarity
            # agrees (Screener junk/unique Δ lead moods + FinRobot +
            # portfolio AI speak-both-sides after lean vs Δ moods).
            delta_lead_moods, _ = soft_allow_short_delta_lead_moods(events)
            if delta_lead_moods:
                head = (
                    f"{head} · short Δ lead moods {delta_lead_moods}"
                )
            last_vs_lean, _ = soft_allow_short_history_last_vs_lean(
                events, now=now
            )
            if last_vs_lean:
                head = f"{head} · short last/lean {last_vs_lean}"
                lead_vs_lean, _ = soft_allow_short_history_last_lead_vs_lean(
                    events, now=now
                )
                if lead_vs_lean:
                    head = f"{head} · short lead/lean {lead_vs_lean}"
                share_vs_lean, _ = soft_allow_short_history_last_share_vs_lean(
                    events, now=now
                )
                if share_vs_lean:
                    head = f"{head} · short share/lean {share_vs_lean}"
                ring_vs_lean, _ = soft_allow_short_history_last_ring_vs_lean(
                    events, now=now
                )
                if ring_vs_lean:
                    head = f"{head} · short ring/lean {ring_vs_lean}"
                lean_vs_bench, _ = (
                    soft_allow_short_history_last_lean_vs_bench_young(
                        events, now=now
                    )
                )
                if lean_vs_bench:
                    head = f"{head} · short lean/bench {lean_vs_bench}"
    return head


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


def _soft_allow_gap_clock_tone(band: str) -> str:
    """Map gap fresh/aging/expired → scan clock fresh/aging/stale.

    ``expired`` ≡ ``stale`` for generation clash (xang1234 #549 /
    e3c84e1 coherent generations). Empty / junk → silent.
    """
    b = str(band or "").strip().casefold()
    if b == "fresh":
        return "fresh"
    if b == "aging":
        return "aging"
    if b == "expired":
        return "stale"
    return ""


def soft_allow_anchor_gap_vs_scan_clash(
    events: list[dict[str, Any]] | None,
    *,
    scan_freshness: str = "",
    now: datetime | None = None,
    gap_pin_size: str = "",
    scan_pin_size: str = "",
    keep_cash_pin_size: str = "",
    keep_soft_pin_size: str = "",
    keep_short_pin_size: str = "",
    keep_memory_pin_size: str = "",
) -> tuple[str, bool]:
    """Gap cursor vs scan archive generation (display only).

    Returns ``(bit, warn)``. When newest gap-row clock ≠ scan band
    (``expired``≡``stale``), speak
    ``clash · gap expired|aging|fresh · scan fresh|aging|stale`` then
    optional gap pin (``gap-only`` via ``gap_pin_size``) then optional
    scan pin (``scan-only`` via ``scan_pin_size``). When gap≠cash is
    silent (gap matches cash), optional ``keep_cash_pin_size`` appends
    the cash pin so scan alone cannot hide the match (soft≠scan
    keep-cash + #660 / #647 / #531). When soft≠gap is silent (gap
    matches soft), optional ``keep_soft_pin_size`` appends ``soft-only``
    so scan alone cannot hide the match (soft≠* keep gap-only + #660 /
    #647 / #531). When short≠gap is silent (gap matches short cursor),
    optional ``keep_short_pin_size`` appends ``short-only`` so scan alone
    cannot hide the match (short≠* keep-gap speak-both-sides + #660 /
    #647 / #531 / #668). When gap≠memory is silent (gap matches
    advisory), optional ``keep_memory_pin_size`` appends ``laya-only`` /
    ``debate-only`` / ``×2 · 100%`` so scan alone cannot hide the match
    (soft≠* keep-memory + #660 / #647 / #531). Gap sleeve ``×N · P%``
    lied fail-open gap-row ownership was the gap cursor print — the
    cursor is a sole published pin like soft last / scan archive
    (soft≠gap / LAYA≠gap ``gap-only`` parity + #647 / #531). Same band /
    missing either silent. Soft-allow *last* matching the scan can still
    hide a staler gap cursor — speak both sides (xang1234 #549 / e3c84e1
    generation coherence + portfolio AI speak-both-sides + soft-allow vs
    scan parity). A fresh scan does not make an expired gap fail-open
    live. Not a gate.
    """
    scan = str(scan_freshness or "").strip().casefold()
    if scan not in {"fresh", "aging", "stale"}:
        return "", False
    gap_band = soft_allow_anchor_gap_last_freshness(events, now=now)
    gap_clock = _soft_allow_gap_clock_tone(gap_band)
    if not gap_clock or gap_clock == scan:
        return "", False
    # Speak soft-allow vocabulary on the gap side (expired not stale).
    gap_speak = gap_band if gap_band in {"fresh", "aging", "expired"} else gap_clock
    raw_gap = str(gap_pin_size or "").strip().lstrip("·").strip()
    gap_pin = f" · {raw_gap}" if raw_gap else ""
    raw_pin = str(scan_pin_size or "").strip().lstrip("·").strip()
    pin = f" · {raw_pin}" if raw_pin else ""
    raw_keep = str(keep_cash_pin_size or "").strip().lstrip("·").strip()
    keep = f" · {raw_keep}" if raw_keep else ""
    raw_soft = str(keep_soft_pin_size or "").strip().lstrip("·").strip()
    keep_soft = f" · {raw_soft}" if raw_soft else ""
    raw_short = str(keep_short_pin_size or "").strip().lstrip("·").strip()
    keep_short = f" · {raw_short}" if raw_short else ""
    raw_mem = str(keep_memory_pin_size or "").strip().lstrip("·").strip()
    keep_mem = f" · {raw_mem}" if raw_mem else ""
    return (
        f"clash · gap {gap_speak} · scan {scan}"
        f"{gap_pin}{pin}{keep}{keep_soft}{keep_short}{keep_mem}",
        True,
    )


def soft_allow_anchor_gap_vs_cash_clock_clash(
    events: list[dict[str, Any]] | None,
    *,
    cash_band: str = "",
    now: datetime | None = None,
    gap_pin_size: str = "",
    cash_pin_size: str = "",
    keep_scan_pin_size: str = "",
    keep_soft_pin_size: str = "",
    keep_short_pin_size: str = "",
    keep_memory_pin_size: str = "",
) -> tuple[str, bool]:
    """Gap cursor vs pinned cash-print generation (display only).

    Returns ``(bit, warn)``. When newest gap-row clock ≠ worst
    last-published cash sleeve (``expired``≡``stale``), speak
    ``clash · gap expired|aging|fresh · cash …`` then optional gap pin
    (``gap-only`` via ``gap_pin_size``) then optional cash pin size
    (``US-only`` / ``US · 50%`` / ``×2 · 100%`` via ``cash_pin_size``).
    When gap≠scan is silent (gap matches the archive), optional
    ``keep_scan_pin_size`` appends ``scan-only`` so cash alone cannot
    hide the matched pin (peer soft/gap/cash keep-scan-only + #660 /
    #647 / #531). When soft≠gap is silent (gap matches soft), optional
    ``keep_soft_pin_size`` appends ``soft-only`` so cash alone cannot
    hide the match (soft≠* keep gap-only + #660 / #647 / #531). When
    short≠gap is silent (gap matches short cursor), optional
    ``keep_short_pin_size`` appends ``short-only`` so cash alone cannot
    hide the match (short≠* keep-gap speak-both-sides + #660 / #647 /
    #531 / #668). When gap≠memory is silent (gap matches advisory),
    optional ``keep_memory_pin_size`` appends the advisory pin so cash
    alone cannot hide the match (soft≠* keep-memory + #660 / #647 /
    #531). Gap sleeve ``×N · P%`` lied fail-open gap-row ownership was
    the gap cursor print — the cursor is a sole published pin (soft≠gap
    / gap≠scan ``gap-only`` parity + #647 / #531). Same band / missing
    either / live cash (no pin) silent. Soft matching the scan archive
    (and soft≠cash) can still hide a gap cursor that matches soft but
    not the cash print — closes gap↔cash beside soft↔cash + soft↔gap +
    gap↔scan (xang1234 #549 / e3c84e1 coherent generations + portfolio AI
    speak-both-sides). Not a gate.
    """
    cash = str(cash_band or "").strip().casefold()
    if cash not in {"fresh", "aging", "stale"}:
        return "", False
    gap_band = soft_allow_anchor_gap_last_freshness(events, now=now)
    gap_clock = _soft_allow_gap_clock_tone(gap_band)
    if not gap_clock or gap_clock == cash:
        return "", False
    gap_speak = (
        gap_band if gap_band in {"fresh", "aging", "expired"} else gap_clock
    )
    raw_gap = str(gap_pin_size or "").strip().lstrip("·").strip()
    gap_pin = f" · {raw_gap}" if raw_gap else ""
    raw_pin = str(cash_pin_size or "").strip().lstrip("·").strip()
    pin = f" · {raw_pin}" if raw_pin else ""
    raw_keep = str(keep_scan_pin_size or "").strip().lstrip("·").strip()
    keep = f" · {raw_keep}" if raw_keep else ""
    raw_soft = str(keep_soft_pin_size or "").strip().lstrip("·").strip()
    keep_soft = f" · {raw_soft}" if raw_soft else ""
    raw_short = str(keep_short_pin_size or "").strip().lstrip("·").strip()
    keep_short = f" · {raw_short}" if raw_short else ""
    raw_mem = str(keep_memory_pin_size or "").strip().lstrip("·").strip()
    keep_mem = f" · {raw_mem}" if raw_mem else ""
    return (
        f"clash · gap {gap_speak} · cash {cash}"
        f"{gap_pin}{pin}{keep}{keep_soft}{keep_short}{keep_mem}",
        True,
    )


def soft_allow_anchor_gap_vs_memory_clock_clash(
    events: list[dict[str, Any]] | None,
    *,
    laya_freshness: str = "",
    debate_freshness: str = "",
    now: datetime | None = None,
    gap_pin_size: str = "",
    memory_pin_size: str = "",
    keep_scan_pin_size: str = "",
    keep_cash_pin_size: str = "",
    keep_soft_pin_size: str = "",
    keep_short_pin_size: str = "",
) -> tuple[str, bool]:
    """Gap cursor vs LAYA/debate memory generation (display only).

    Returns ``(bit, warn)``. When newest gap-row clock ≠ LAYA and/or
    AI-debate clocks (``expired``≡``stale``), speak
    ``clash · gap expired|aging|fresh · laya … · debate …`` then optional
    gap pin (``gap-only`` via ``gap_pin_size``) then optional advisory
    pin size (``laya-only`` / ``laya · 50%`` / ``×2 · 100%`` via
    ``memory_pin_size``). When gap≠scan is silent (gap matches the
    archive), optional ``keep_scan_pin_size`` appends ``scan-only`` so
    memory alone cannot hide the matched pin (peer soft/gap/cash
    keep-scan-only + #660 / #647 / #531). When gap≠cash is silent
    (gap matches cash), optional ``keep_cash_pin_size`` appends the
    cash pin so memory alone cannot hide the match (soft≠memory
    keep-cash + #660 / #647 / #531). When soft≠gap is silent (gap
    matches soft), optional ``keep_soft_pin_size`` appends ``soft-only``
    so memory alone cannot hide the match (soft≠* keep gap-only + #660 /
    #647 / #531). When short≠gap is silent (gap matches short cursor),
    optional ``keep_short_pin_size`` appends ``short-only`` so memory
    alone cannot hide the match (short≠* keep-gap speak-both-sides +
    #660 / #647 / #531 / #668). Gap sleeve ``×N · P%`` lied fail-open
    gap-row ownership was the gap cursor print — the cursor is a sole
    published pin (soft≠gap / gap≠scan ``gap-only`` parity + #647 /
    #531). Same band / missing either side silent. Soft matching memory
    (and soft≠gap) can still hide a gap cursor that matches soft but not
    the advisory print — closes gap↔memory beside soft↔memory + soft↔gap
    + gap↔scan/cash (xang1234 #549 / e3c84e1 + FinRobot last-row +
    portfolio AI speak-both-sides). Not a gate.
    """
    gap_band = soft_allow_anchor_gap_last_freshness(events, now=now)
    gap_clock = _soft_allow_gap_clock_tone(gap_band)
    if not gap_clock:
        return "", False
    gap_speak = (
        gap_band if gap_band in {"fresh", "aging", "expired"} else gap_clock
    )
    bits: list[str] = []
    for name, tone in (("laya", laya_freshness), ("debate", debate_freshness)):
        t = str(tone or "").strip().casefold()
        if t == "expired":
            t = "stale"
        elif t == "unknown":
            t = "fresh"
        if t not in {"fresh", "aging", "stale"} or t == gap_clock:
            continue
        bits.append(f"{name} {t}")
    if not bits:
        return "", False
    raw_gap = str(gap_pin_size or "").strip().lstrip("·").strip()
    gap_pin = f" · {raw_gap}" if raw_gap else ""
    raw_pin = str(memory_pin_size or "").strip().lstrip("·").strip()
    pin = f" · {raw_pin}" if raw_pin else ""
    raw_keep = str(keep_scan_pin_size or "").strip().lstrip("·").strip()
    keep = f" · {raw_keep}" if raw_keep else ""
    raw_cash = str(keep_cash_pin_size or "").strip().lstrip("·").strip()
    keep_cash = f" · {raw_cash}" if raw_cash else ""
    raw_soft = str(keep_soft_pin_size or "").strip().lstrip("·").strip()
    keep_soft = f" · {raw_soft}" if raw_soft else ""
    raw_short = str(keep_short_pin_size or "").strip().lstrip("·").strip()
    keep_short = f" · {raw_short}" if raw_short else ""
    return (
        f"clash · gap {gap_speak} · {' · '.join(bits)}"
        f"{gap_pin}{pin}{keep}{keep_cash}{keep_soft}{keep_short}",
        True,
    )


def soft_allow_vs_gap_clock_clash(
    events: list[dict[str, Any]] | None,
    *,
    soft_last_freshness: str = "",
    now: datetime | None = None,
    soft_pin_size: str = "",
    gap_pin_size: str = "",
) -> tuple[str, bool]:
    """Soft-allow last vs gap cursor generation (display only).

    Returns ``(bit, warn)``. When newest soft-allow clock ≠ newest gap
    cursor clock (``expired``≡``stale``), speak
    ``clash · soft fresh|aging|stale · gap expired|aging|fresh`` then
    optional soft pin (``soft-only`` via ``soft_pin_size``) then optional
    gap pin (``gap-only`` via ``gap_pin_size``). Same band / missing
    either silent. Gap sleeve ``×N · P%`` lied fail-open gap-row
    ownership was the gap cursor print — the cursor is a sole published
    pin like soft last / scan archive (soft≠scan ``soft-only ·
    scan-only`` / gap≠scan ``gap-only · scan-only`` / LAYA≠gap
    ``gap-only`` parity; xang1234 #647 / #531). Soft last matching the
    scan can still hide a staler gap cursor — naming soft≠gap closes
    the generation triangle with soft-vs-scan and gap-vs-scan
    (xang1234 #549 / e3c84e1 + FinRobot last-row + portfolio AI
    speak-both-sides). Not a gate.
    """
    soft = str(soft_last_freshness or "").strip().casefold()
    if soft == "expired":
        soft = "stale"
    elif soft == "unknown":
        soft = "fresh"
    if soft not in {"fresh", "aging", "stale"}:
        first = next(
            (r for r in (events or []) if isinstance(r, dict)), None
        )
        if first is None:
            return "", False
        band = str(first.get("freshness") or "").strip().casefold()
        if band == "unknown":
            soft = "fresh"
        elif band == "expired":
            soft = "stale"
        elif band in {"fresh", "aging"}:
            soft = band
        else:
            computed = soft_allow_freshness(first.get("at"), now=now)
            if computed == "expired":
                soft = "stale"
            elif computed in {"fresh", "aging"}:
                soft = computed
            else:
                return "", False
    gap_band = soft_allow_anchor_gap_last_freshness(events, now=now)
    gap_clock = _soft_allow_gap_clock_tone(gap_band)
    if not gap_clock or soft == gap_clock:
        return "", False
    gap_speak = (
        gap_band if gap_band in {"fresh", "aging", "expired"} else gap_clock
    )
    raw_soft = str(soft_pin_size or "").strip().lstrip("·").strip()
    soft_pin = f" · {raw_soft}" if raw_soft else ""
    raw_pin = str(gap_pin_size or "").strip().lstrip("·").strip()
    pin = f" · {raw_pin}" if raw_pin else ""
    return f"clash · soft {soft} · gap {gap_speak}{soft_pin}{pin}", True


def soft_allow_vs_short_history_clock_clash(
    events: list[dict[str, Any]] | None,
    *,
    soft_last_freshness: str = "",
    now: datetime | None = None,
    soft_pin_size: str = "",
    short_pin_size: str = "",
) -> tuple[str, bool]:
    """Soft-allow last vs short-history cursor generation (display only).

    Returns ``(bit, warn)``. When newest soft-allow clock ≠ newest
    short-history cursor clock (``expired``≡``stale``), speak
    ``clash · soft fresh|aging|stale · short expired|aging|fresh`` then
    optional soft pin (``soft-only`` via ``soft_pin_size``) then optional
    short pin (``short-only`` via ``short_pin_size``). Same band /
    missing either silent. Soft last matching the scan (and soft≠gap /
    short≠scan alone) can still hide a staler young/short cursor —
    naming soft≠short closes the generation triangle with soft-vs-scan
    and short-vs-scan (soft≠gap / short≠gap parity + xang1234 #549 /
    e3c84e1 + #668 + FinRobot last-row + portfolio AI speak-both-sides).
    Keep soft/short pins deferred to a later tick. Not a gate.
    """
    soft = str(soft_last_freshness or "").strip().casefold()
    if soft == "expired":
        soft = "stale"
    elif soft == "unknown":
        soft = "fresh"
    if soft not in {"fresh", "aging", "stale"}:
        first = next(
            (r for r in (events or []) if isinstance(r, dict)), None
        )
        if first is None:
            return "", False
        band = str(first.get("freshness") or "").strip().casefold()
        if band == "unknown":
            soft = "fresh"
        elif band == "expired":
            soft = "stale"
        elif band in {"fresh", "aging"}:
            soft = band
        else:
            computed = soft_allow_freshness(first.get("at"), now=now)
            if computed == "expired":
                soft = "stale"
            elif computed in {"fresh", "aging"}:
                soft = computed
            else:
                return "", False
    short_band = soft_allow_short_history_last_freshness(events, now=now)
    short_clock = _soft_allow_gap_clock_tone(short_band)
    if not short_clock or soft == short_clock:
        return "", False
    short_speak = (
        short_band
        if short_band in {"fresh", "aging", "expired"}
        else short_clock
    )
    raw_soft = str(soft_pin_size or "").strip().lstrip("·").strip()
    soft_pin = f" · {raw_soft}" if raw_soft else ""
    raw_pin = str(short_pin_size or "").strip().lstrip("·").strip()
    pin = f" · {raw_pin}" if raw_pin else ""
    return (
        f"clash · soft {soft} · short {short_speak}{soft_pin}{pin}",
        True,
    )


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
    symbols and one is strictly largest, speak ``lead AAPL · N · P%``
    (row count then share of parseable gap rows). The runner bit already
    names ``vs MSFT · 1 · 33%``; share alone hid the owner's count
    (portfolio AI count≠share). Ties / sole-symbol / <2 parseable stay
    silent on lead (use ``soft_allow_anchor_gap_symbol_sample_gap``).
    Screener junk-list lead + xang1234 multi-meter after last-cursor.
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
    return f"lead {lead_name} · {lead_n} · {share}%", lead_name, share


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


def _anchor_gap_ring_size(events: list[dict[str, Any]] | None) -> str:
    """`` · ×N · P%`` for the gap sleeve (display only).

    Relationship verbs hid how many gap rows and what share of the ring
    they describe (portfolio AI count≠share). Missing gaps stay silent.
    """
    gap_n, share, _severity = soft_allow_anchor_gap_share(events)
    if gap_n <= 0 or share is None:
        return ""
    return f" · ×{int(gap_n)} · {int(round(float(share)))}%"


def soft_allow_anchor_gap_last_vs_lead_freshness(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last gap freshness vs symbol last-vs-lead (display only).

    Returns ``(bit, warn)``. Cursor age ≠ name-vs-lead agreement.
    Extremes only: ``fresh``↔``agree`` and ``expired``↔ name clash speak
    ``align``; crossed pairs speak ``clash`` (warn). ``aging`` / silent
    last-vs-lead stay silent — RyanJHamby triad + FinRobot last-row age
    + portfolio AI speak-both-sides after bare ``agree`` / ``last vs
    lead`` hid whether the cursor match is still live (stale agree ≠
    calm confirm). Gap count and share ride the bit (``×N · P%``) so
    the verb is not a nameless sleeve. Not a gate.
    """
    last_fresh = soft_allow_anchor_gap_last_freshness(events, now=now)
    last_vs = soft_allow_anchor_gap_symbol_last_vs_lead(events)
    if last_fresh not in {"fresh", "expired"} or not last_vs:
        return "", False
    if last_vs == "agree":
        name_agree = True
        name_tail = "agree"
    elif last_vs.startswith("last vs lead · "):
        name_agree = False
        name_tail = f"vs {last_vs[len('last vs lead · ') :]}"
    else:
        return "", False
    live_age = last_fresh == "fresh"
    size = _anchor_gap_ring_size(events)
    if live_age == name_agree:
        return f"align · {last_fresh} · {name_tail}{size}", False
    return f"clash · {last_fresh} · {name_tail}{size}", True


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
    size = _anchor_gap_ring_size(events)
    if live_age == hot_share:
        return f"align · {last_fresh} · {severity}{size}", False
    return f"clash · {last_fresh} · {severity}{size}", True


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
    size = _anchor_gap_ring_size(events)
    if live_age == lean_align:
        return f"align · {last_fresh} · {lean_tail}{size}", False
    return f"clash · {last_fresh} · {lean_tail}{size}", True


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
    size = _anchor_gap_ring_size(events)
    if share_verb == lean_verb:
        # Dual-clash agreement is adverse; dual-align is calm.
        return f"align · both {share_verb}{size}", share_verb == "clash"
    return f"clash · share {share_verb} · lean {lean_verb}{size}", True


def soft_allow_anchor_gap_last_lead_vs_share(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last/lead freshness vs last/share relationship agreement (display only).

    Returns ``(bit, warn)``. Age↔name-vs-lead ≠ age↔share heat. When both
    already spoke: same verb speaks ``align · both align|clash`` —
    ``both align`` stays calm; ``both clash`` warns (dual-clash agreement
    ≠ quiet confirm). Crossed verbs speak
    ``clash · lead align|clash · share align|clash`` (warn). Missing
    either stays silent — FinRobot last-row age + portfolio AI
    speak-both-sides + RyanJHamby severity after last/lead + last/share
    alone hid whether cursor-vs-owner and ownership-heat agree *and*
    whether dual-clash agreement is adverse. Not a gate.
    """
    lead_bit, _ = soft_allow_anchor_gap_last_vs_lead_freshness(
        events, now=now
    )
    share_bit, _ = soft_allow_anchor_gap_last_vs_share(events, now=now)
    if not lead_bit or not share_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    lead_verb = _verb(lead_bit)
    share_verb = _verb(share_bit)
    if lead_verb is None or share_verb is None:
        return "", False
    size = _anchor_gap_ring_size(events)
    if lead_verb == share_verb:
        return f"align · both {lead_verb}{size}", lead_verb == "clash"
    return f"clash · lead {lead_verb} · share {share_verb}{size}", True


def soft_allow_anchor_gap_last_lead_vs_lean(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> tuple[str, bool]:
    """Last/lead freshness vs last/lean relationship agreement (display only).

    Returns ``(bit, warn)``. Age↔name-vs-lead ≠ age↔lean. When both
    already spoke: same verb speaks ``align · both align|clash`` —
    ``both align`` stays calm; ``both clash`` warns (dual-clash agreement
    ≠ quiet confirm). Crossed verbs speak
    ``clash · lead align|clash · lean align|clash`` (warn). Missing
    either stays silent — FinRobot last-row age + portfolio AI
    speak-both-sides + RyanJHamby severity after last/lead + last/lean
    alone hid whether cursor-vs-owner and age↔lean agree *and* whether
    dual-clash agreement is adverse. lead/share + share/lean do not
    imply lead↔lean (clash/align is not transitive). Not a gate.
    """
    lead_bit, _ = soft_allow_anchor_gap_last_vs_lead_freshness(
        events, now=now
    )
    lean_bit, _ = soft_allow_anchor_gap_last_vs_lean(events, now=now)
    if not lead_bit or not lean_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    lead_verb = _verb(lead_bit)
    lean_verb = _verb(lean_bit)
    if lead_verb is None or lean_verb is None:
        return "", False
    size = _anchor_gap_ring_size(events)
    if lead_verb == lean_verb:
        return f"align · both {lead_verb}{size}", lead_verb == "clash"
    return f"clash · lead {lead_verb} · lean {lean_verb}{size}", True


def format_soft_allow_anchor_gap_bit(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
    scan_freshness: str = "",
    gap_pin_size: str = "",
    scan_pin_size: str = "",
    cash_band: str = "",
    cash_pin_size: str = "",
    laya_freshness: str = "",
    debate_freshness: str = "",
    memory_pin_size: str = "",
    keep_scan_pin_size: str = "",
    keep_cash_pin_size: str = "",
    keep_soft_pin_size: str = "",
    keep_short_pin_size: str = "",
    keep_memory_pin_size: str = "",
) -> str:
    """Compact ``N gap · last SYM · fresh|aging|expired · lead|n=1|tied · …``.

    Zero silent. ``last SYM`` sits right after the count so a long lean
    cascade cannot clip the cursor (xang1234 #546). Cursor age
    (``fresh`` / ``aging`` / ``expired``) follows the name so a live
    ticker ≠ a live fail-open (RyanJHamby + soft-allow triad + FinRobot
    last-row age; unknown stamp silent). When gap clock ≠ scan archive
    band, ``clash · gap … · scan …`` follows age so a soft-allow last
    matching the scan cannot hide a staler gap cursor (xang1234 #549 /
    e3c84e1 generation coherence + portfolio AI speak-both-sides). When
    gap clock ≠ pinned cash print, ``clash · gap … · cash …`` follows so
    soft≠cash alone cannot hide a gap cursor that matches soft but not
    the cash sleeve (gap↔cash after soft↔cash + gap↔scan). When gap
    clock ≠ LAYA/debate, ``clash · gap … · laya … · debate …`` follows
    so soft≠memory alone cannot hide a gap cursor that matches soft but
    not the advisory print (gap↔memory after soft↔memory + soft↔gap).
    Symbol lead /
    n=1 / tied follows the cursor (last ≠ ring ownership; Screener
    junk-list lead + soft-allow sample honesty); when lead spoke,
    ``last vs lead`` / ``agree`` sits right after so the cursor≠owner
    clash is not clipped by share/lean (FinRobot last≠tilt); when last
    freshness + last-vs-lead already spoke, ``last/lead align|clash``
    follows so age ≠ name agreement (stale ``agree`` warns; live name
    clash warns). When a runner exists, ``ahead`` + ``vs SYM`` follow so
    ownership % ≠ how far ahead ≠ who is #2 (soft gate-lead margin/sides;
    sole 100% omits). Share severity follows; when last freshness + share
    lean already spoke, ``last/share align|clash`` sits right after so
    age ≠ ownership heat (portfolio AI speak-both-sides; clash warns).
    When last/lead + last/share already spoke, ``lead/share align|clash``
    follows so cursor-vs-owner ≠ ownership-heat (``both clash`` warns;
    ``both align`` stays calm). When gap/other lean already spoke,
    ``last/lean align|clash`` follows so age ≠ lean agreement. When
    last/lead + last/lean already spoke, ``lead/lean align|clash``
    follows so cursor-vs-owner ≠ age↔lean (``both clash`` warns; ``both
    align`` stays calm). When both last/share and last/lean already
    spoke, ``share/lean align|clash`` follows so the two relationships
    are not silent-confirm (``both clash`` warns; ``both align`` stays
    calm).
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
        gap_vs_scan, _ = soft_allow_anchor_gap_vs_scan_clash(
            events,
            scan_freshness=scan_freshness,
            now=now,
            gap_pin_size=gap_pin_size,
            scan_pin_size=scan_pin_size,
            keep_cash_pin_size=keep_cash_pin_size,
            keep_soft_pin_size=keep_soft_pin_size,
            keep_short_pin_size=keep_short_pin_size,
            keep_memory_pin_size=keep_memory_pin_size,
        )
        if gap_vs_scan:
            head = f"{head} · {gap_vs_scan}"
        gap_vs_cash, _ = soft_allow_anchor_gap_vs_cash_clock_clash(
            events,
            cash_band=cash_band,
            now=now,
            gap_pin_size=gap_pin_size,
            cash_pin_size=cash_pin_size,
            keep_scan_pin_size=keep_scan_pin_size,
            keep_soft_pin_size=keep_soft_pin_size,
            keep_short_pin_size=keep_short_pin_size,
            keep_memory_pin_size=keep_memory_pin_size,
        )
        if gap_vs_cash:
            head = f"{head} · {gap_vs_cash}"
        gap_vs_mem, _ = soft_allow_anchor_gap_vs_memory_clock_clash(
            events,
            laya_freshness=laya_freshness,
            debate_freshness=debate_freshness,
            now=now,
            gap_pin_size=gap_pin_size,
            memory_pin_size=memory_pin_size,
            keep_scan_pin_size=keep_scan_pin_size,
            keep_cash_pin_size=keep_cash_pin_size,
            keep_soft_pin_size=keep_soft_pin_size,
            keep_short_pin_size=keep_short_pin_size,
        )
        if gap_vs_mem:
            head = f"{head} · {gap_vs_mem}"
    lead_bit, _lead_name, _lead_share = soft_allow_anchor_gap_symbol_lead(
        events
    )
    if lead_bit:
        head = f"{head} · {lead_bit}"
        last_vs = soft_allow_anchor_gap_symbol_last_vs_lead(events)
        if last_vs:
            head = f"{head} · {last_vs}"
            last_vs_lead_fresh, _ = soft_allow_anchor_gap_last_vs_lead_freshness(
                events, now=now
            )
            if last_vs_lead_fresh:
                head = f"{head} · last/lead {last_vs_lead_fresh}"
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
        lead_vs_share, _lvs_rel_warn = soft_allow_anchor_gap_last_lead_vs_share(
            events, now=now
        )
        if lead_vs_share:
            bit = f"{bit} · lead/share {lead_vs_share}"
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
            lead_vs_lean, _lvl_rel_warn = (
                soft_allow_anchor_gap_last_lead_vs_lean(events, now=now)
            )
            if lead_vs_lean:
                bit = f"{bit} · lead/lean {lead_vs_lean}"
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
    Desk expands bare ``agree`` to ``agree · last rs · lead rs`` on the
    lean chip (lead/config parity) without changing this helper — gap
    symbol last-vs-lead reuses the bare form. FinRobot last-debate ≠
    ring tilt + portfolio AI speak-both-sides after soft-allow lead
    sides share (LAYA/debate ``last vs lead`` / ``agree`` parity). No
    tone escalate. Not a gate.
    """
    lead = str(lead_gate or "").strip()
    last = str(last_gate or "").strip()
    if not lead or not last:
        return ""
    if lead.casefold() == last.casefold():
        return "agree"
    return f"last vs lead · {last}"


# Soft-allow lead gate → Ops toggle key + compact label (entry-gates glance).
_SOFT_ALLOW_LEAD_CONFIG: dict[str, tuple[str, str]] = {
    "regime": ("regime_gate", "regime"),
    "rs": ("rs_gate", "RS"),
    "breadth": ("breadth_gate", "breadth"),
    "promote": ("promote_experiment_strategy", "promote"),
}


def soft_allow_lead_vs_config(
    lead_gate: str,
    runtime: Mapping[str, Any] | None,
    *,
    lead_count: int = 0,
    lead_share_pct: float | None = None,
) -> str:
    """Lead ring ownership vs Ops soft-gate toggle (display only).

    Compact ``rs leads · fresh · ×N`` hid whether that gate is still on.
    When lead already spoke and the matching Ops toggle is present:
    - explicitly off → ``clash · lead rs · ×N · P% · RS off`` (warn)
    - explicitly on → ``agree · lead rs · ×N · P% · RS on`` (no warn)
    Count and share ride on the bit so the lean chip is not a nameless
    knob (portfolio AI count≠share). Missing count omits the size.
    Missing key / unknown gate / no lead stay silent (tradermonty #576
    same-run provenance — ring handoff vs live config). Not a gate.
    """
    if not isinstance(runtime, Mapping):
        return ""
    lead = str(lead_gate or "").strip().casefold()
    mapped = _SOFT_ALLOW_LEAD_CONFIG.get(lead)
    if mapped is None:
        return ""
    key, label = mapped
    if key not in runtime:
        return ""
    size = ""
    if lead_count > 0:
        size = f" · ×{lead_count}"
        if lead_share_pct is not None:
            size += f" · {int(round(float(lead_share_pct)))}%"
    if bool(runtime.get(key)):
        return f"agree · lead {lead}{size} · {label} on"
    return f"clash · lead {lead}{size} · {label} off"


def soft_allow_last_lead_vs_config(
    last_vs_lead: str,
    lead_vs_config: str,
    *,
    lead_count: int = 0,
    lead_share_pct: float | None = None,
) -> tuple[str, bool]:
    """Last≠lead vs lead↔Ops relationship agreement (display only).

    Returns ``(bit, warn)``. Newest print vs band lead ≠ lead ring vs
    Ops toggle. When both already spoke: same polarity speaks
    ``last/config align · both agree|clash · ×N · P%`` — ``both agree``
    stays calm; ``both clash`` warns (dual-clash agreement ≠ quiet
    confirm). Crossed speaks ``last/config clash · last agree|clash ·
    config agree|clash · ×N · P%`` (warn). Count and share ride on the
    bit so polarity is not a nameless ring (portfolio AI count≠share).
    Missing count omits the size. Missing either relationship stays
    silent — FinRobot last≠tilt + tradermonty #576 provenance +
    portfolio AI speak-both-sides + RyanJHamby dual-clash after
    last/lead + lead/config alone hid whether the two relationships
    agree *and* whether dual-clash agreement is adverse. Not a gate.
    """
    last_bit = str(last_vs_lead or "").strip()
    config_bit = str(lead_vs_config or "").strip()
    if not last_bit or not config_bit:
        return "", False

    def _last_verb(bit: str) -> str | None:
        if bit.startswith("agree"):
            return "agree"
        if bit.startswith("last vs lead"):
            return "clash"
        return None

    def _config_verb(bit: str) -> str | None:
        if bit.startswith("agree"):
            return "agree"
        if bit.startswith("clash"):
            return "clash"
        return None

    last_verb = _last_verb(last_bit)
    config_verb = _config_verb(config_bit)
    if last_verb is None or config_verb is None:
        return "", False
    size = ""
    if lead_count > 0:
        size = f" · ×{lead_count}"
        if lead_share_pct is not None:
            size += f" · {int(round(float(lead_share_pct)))}%"
    if last_verb == config_verb:
        return (
            f"last/config align · both {last_verb}{size}",
            last_verb == "clash",
        )
    return (
        f"last/config clash · last {last_verb} · config {config_verb}{size}",
        True,
    )


def _soft_allow_ring_size(
    lead_count: int = 0, lead_share_pct: float | None = None
) -> str:
    """`` · ×N · P%`` when the lead ring has a size (display only)."""
    if lead_count <= 0:
        return ""
    size = f" · ×{int(lead_count)}"
    if lead_share_pct is not None:
        size += f" · {int(round(float(lead_share_pct)))}%"
    return size


def soft_allow_last_vs_lead_freshness(
    last_vs_lead: str,
    last_freshness: str,
    *,
    lead_count: int = 0,
    lead_share_pct: float | None = None,
) -> tuple[str, bool]:
    """Newest soft-allow age vs gate last-vs-lead (display only).

    Returns ``(bit, warn)``. Cursor age ≠ name-vs-lead agreement.
    Extremes only: ``fresh``↔``agree`` and ``expired``↔ name clash speak
    ``last/lead align · … · ×N · P%``; crossed pairs speak
    ``last/lead clash · …`` (warn). Count and share ride on the bit so
    age is not a nameless ring (portfolio AI count≠share). Missing
    count omits the size. ``aging`` / silent last-vs-lead stay silent —
    gap ``soft_allow_anchor_gap_last_vs_lead_freshness`` parity +
    RyanJHamby triad + FinRobot last-row age + portfolio AI
    speak-both-sides after bare ``agree`` / ``last vs lead`` hid
    whether the gate match is still live *and* how large that ring is
    (stale agree ≠ calm confirm). Not a gate.
    """
    last_fresh = str(last_freshness or "").strip().casefold()
    last_vs = str(last_vs_lead or "").strip()
    if last_fresh not in {"fresh", "expired"} or not last_vs:
        return "", False
    if last_vs.startswith("agree"):
        name_agree = True
        name_tail = "agree"
    elif last_vs.startswith("last vs lead · "):
        name_agree = False
        name_tail = f"vs {last_vs[len('last vs lead · ') :]}"
    else:
        return "", False
    size = _soft_allow_ring_size(lead_count, lead_share_pct)
    live_age = last_fresh == "fresh"
    if live_age == name_agree:
        return f"last/lead align · {last_fresh} · {name_tail}{size}", False
    return f"last/lead clash · {last_fresh} · {name_tail}{size}", True


def soft_allow_lead_vs_config_freshness(
    lead_vs_config: str,
    last_freshness: str,
    *,
    lead_count: int = 0,
    lead_share_pct: float | None = None,
) -> tuple[str, bool]:
    """Newest soft-allow age vs lead↔Ops toggle (display only).

    Returns ``(bit, warn)``. Cursor age ≠ lead ring vs live knob.
    Extremes only: ``fresh``↔``agree`` (on) and ``expired``↔``clash``
    (off) speak ``lead/config align · … · ×N · P%``; crossed pairs
    speak ``lead/config clash · …`` (warn). Count and share ride on
    the bit so age is not a nameless knob (portfolio AI count≠share).
    Missing count omits the size. ``aging`` / silent lead/config stay
    silent — last/lead freshness parity + tradermonty #576 provenance
    + RyanJHamby triad + FinRobot last-row age after bare
    ``agree · lead rs · RS on`` hid whether the knob match is still
    live *and* how large that ring is (stale agree ≠ calm confirm).
    Not a gate.
    """
    last_fresh = str(last_freshness or "").strip().casefold()
    config_bit = str(lead_vs_config or "").strip()
    if last_fresh not in {"fresh", "expired"} or not config_bit:
        return "", False
    tail = config_bit.rsplit(" ", 1)[-1].casefold()
    if tail not in {"on", "off"}:
        return "", False
    if config_bit.startswith("agree"):
        name_agree = True
    elif config_bit.startswith("clash"):
        name_agree = False
    else:
        return "", False
    size = _soft_allow_ring_size(lead_count, lead_share_pct)
    live_age = last_fresh == "fresh"
    if live_age == name_agree:
        return f"lead/config align · {last_fresh} · {tail}{size}", False
    return f"lead/config clash · {last_fresh} · {tail}{size}", True


def soft_allow_last_lead_vs_config_freshness(
    last_vs_lead_freshness: str,
    lead_vs_config_freshness: str,
    *,
    lead_count: int = 0,
    lead_share_pct: float | None = None,
) -> tuple[str, bool]:
    """Last/lead age vs lead↔Ops age agreement (display only).

    Returns ``(bit, warn)``. Age↔newest-gate ≠ age↔live knob. When both
    already spoke: same verb speaks ``last/config age align · both
    align|clash · fresh|expired · ×N · P%`` — ``both align`` stays
    calm; ``both clash`` warns (dual-clash agreement ≠ quiet confirm).
    Crossed verbs speak ``last/config age clash · last/lead … ·
    lead/config … · fresh|expired · ×N · P%`` (warn). The shared clock
    and ring size ride the bit so ``both clash`` is not a silent
    confirm of a stale agree or a live disagree, and the clock is not
    a nameless ring. Mismatched clocks speak ``mixed``. Missing either
    stays silent — FinRobot last-row age + tradermonty #576 provenance
    + portfolio AI speak-both-sides + RyanJHamby dual-clash after
    last/lead freshness + lead/config freshness alone hid whether the
    two age relationships agree, whether that agreement is still live,
    *and* how large that ring is. Not a gate.
    """
    last_bit = str(last_vs_lead_freshness or "").strip()
    config_bit = str(lead_vs_config_freshness or "").strip()
    if not last_bit or not config_bit:
        return "", False

    def _verb(bit: str, prefix: str) -> str | None:
        if bit.startswith(f"{prefix} align"):
            return "align"
        if bit.startswith(f"{prefix} clash"):
            return "clash"
        return None

    def _age(bit: str) -> str:
        parts = [p.strip().casefold() for p in bit.split(" · ")]
        if len(parts) >= 2 and parts[1] in {"fresh", "expired"}:
            return parts[1]
        return ""

    last_verb = _verb(last_bit, "last/lead")
    config_verb = _verb(config_bit, "lead/config")
    if last_verb is None or config_verb is None:
        return "", False
    last_age = _age(last_bit)
    config_age = _age(config_bit)
    if last_age and config_age:
        age = last_age if last_age == config_age else "mixed"
    else:
        age = last_age or config_age
    age_tail = f" · {age}" if age else ""
    size = _soft_allow_ring_size(lead_count, lead_share_pct)
    if last_verb == config_verb:
        return (
            f"last/config age align · both {last_verb}{age_tail}{size}",
            last_verb == "clash",
        )
    return (
        f"last/config age clash · last/lead {last_verb} · "
        f"lead/config {config_verb}{age_tail}{size}",
        True,
    )


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
