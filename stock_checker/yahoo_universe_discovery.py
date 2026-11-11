"""
Yahoo Finance movers → curated universe discovery (not auto-buy).

Pulls day gainers / losers via yfinance screen presets and proposes symbols
for StockUniverseManager. Trading still goes through regime / RS / breadth /
fees gates.
"""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, List, Sequence

from stock_checker.symbol_filters import is_tradeable_symbol

# Keep discovery calm — we are not RyanJHamby's 3800-name firehose.
DEFAULT_MOVER_COUNT = 25
# Re-pull Yahoo movers when last discovery is older than this (desk shows age).
DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS = 24
# xang1234 dfb6a86: do not refetch an empty/dead slice every scan cycle.
# Failed Yahoo still retries sooner than the 24h success throttle, but not
# on every 15m scan — calm the thrash when movers stay blocked.
DEFAULT_YAHOO_FAIL_BACKOFF_HOURS = 1
# xang1234 #639: bound hung Yahoo screens (feedparser/requests had no timeout
# and looked like quiet empty forever). Per-screen join ceiling for yf.screen.
DEFAULT_YAHOO_SCREEN_TIMEOUT_SEC = 20
# xang1234 #726: release a pipeline claim when no worker usefully holds the
# stage. Join ceiling does not kill a hung yf.screen thread; without a TTL a
# zombie claim blocked that screen until container restart. Cap claim age so
# catch-up scans can spend again (orphan daemon may linger — hung ≠ forever).
DEFAULT_YAHOO_SCREEN_CLAIM_MAX_SEC = 120
# One live worker per screen name — a later scan must not start a second
# fetch while the first is still inside the claim window (xang1234 #639
# bound hung requests + #642 not-spent + #726 dead-chain-claim).
# Value: (worker, monotonic start).
_yahoo_screen_inflight: dict[str, tuple[threading.Thread, float]] = {}
_yahoo_screen_inflight_lock = threading.Lock()
DEFAULT_SCREENS: tuple[str, ...] = ("day_gainers", "day_losers", "most_actives")
# xang1234: a mostly empty snapshot is a failed fetch, not a quiet day.
EMPTY_SCREEN_FRACTION = 0.2


class YahooScreenEmptyError(Exception):
    """Yahoo screen returned nothing usable (block / empty payload)."""


def _quotes_from_screen_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        quotes = payload.get("quotes")
        if isinstance(quotes, list):
            return [q for q in quotes if isinstance(q, dict)]
    return []


def screen_payload_failed(payload: Any, *, expected: int) -> bool:
    """True when the screen looks blocked or mostly empty (do not stamp cache)."""
    quotes = _quotes_from_screen_payload(payload)
    if not quotes:
        return True
    want = max(1, int(expected))
    floor = max(1, int(want * EMPTY_SCREEN_FRACTION))
    return len(quotes) < floor


def screens_bundle_failed(ok: int, failed: int) -> bool:
    """True when the mover bundle is blocked or majority-failed.

    xang1234: a 403 / empty Finviz snapshot must not raise, and a mostly
    dead refresh is a failed fetch — do not stamp cache fresh or mix in
    leftover quotes from the one screen that still answered.
    """
    ok_n = max(0, int(ok))
    fail_n = max(0, int(failed))
    if ok_n <= 0:
        return True
    return fail_n > ok_n


def screens_bundle_partial(ok: int, failed: int) -> bool:
    """True when some screens answered and some failed (not majority-dead).

    xang1234 7e0df1e: skip prune baselines for partly failed fetches — leftover
    quotes from the live screens are still addable, but missing names are not
    a complete drop list.
    """
    if screens_bundle_failed(ok, failed):
        return False
    return max(0, int(failed)) > 0


def yahoo_cache_freshness(
    age_sec: float | None,
    *,
    max_age_hours: int = DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS,
    parsed: bool = True,
) -> str:
    """Bound a reused seed by last-good discovery age (xang1234 317b6bb).

    ``never`` = no stamp. ``unknown`` = stamp present but unparsed.
    Otherwise fresh < max_age, aging < 2×, else stale.
    """
    if not parsed:
        return "unknown"
    if age_sec is None:
        return "never"
    limit = max(1, int(max_age_hours)) * 3600.0
    age = max(0.0, float(age_sec))
    if age < limit:
        return "fresh"
    if age < 2 * limit:
        return "aging"
    return "stale"


def _naive_utc(dt: datetime) -> datetime:
    """Normalize to naive UTC wall-clock.

    Aware values convert to UTC. Naive values are treated as UTC already
    (legacy stamps + desk ``_parse_book_ts`` parity). Never compare a UTC
    stamp against ``datetime.now()`` in a non-UTC process TZ — that is the
    xang1234 #743 / #744 false-stuck lease bug.
    """
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def yahoo_stamp_utc_iso(now: datetime | None = None) -> str:
    """UTC ISO stamp with ``Z`` for Yahoo discovery success/fail meta.

    xang1234 #744: workers/API may disagree on process TZ; write lease /
    heartbeat activity as aware UTC so age math cannot mark a fresh stamp
    stuck. Naive ``datetime.now().isoformat()`` hid the zone.
    """
    clock = now if now is not None else datetime.now(timezone.utc)
    return _naive_utc(clock).strftime("%Y-%m-%dT%H:%M:%SZ")


def yahoo_clock_utc_naive(now: datetime | None = None) -> datetime:
    """Clock for Yahoo discovery age / backoff (always naive UTC)."""
    if now is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    return _naive_utc(now)


def yahoo_fail_streak(meta: Any) -> int:
    """Consecutive failed Yahoo discovery attempts (xang1234 #639).

    Failures that looked like a quiet seed reused the same fail stamp without
    naming how many times in a row movers stayed dead. ``0`` when absent /
    unparseable / success cleared the counter.
    """
    if not isinstance(meta, dict):
        return 0
    raw = meta.get("yahoo_discovery_fail_streak")
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def bump_yahoo_fail_streak(meta: dict[str, Any]) -> int:
    """Increment consecutive-fail counter on a blocked / empty movers fetch."""
    n = yahoo_fail_streak(meta) + 1
    meta["yahoo_discovery_fail_streak"] = n
    return n


def clear_yahoo_fail_streak(meta: dict[str, Any]) -> None:
    """Reset streak after a successful movers snapshot (last_success honesty)."""
    meta["yahoo_discovery_fail_streak"] = 0


# Compact fail reasons for desk (xang1234 #639 last-error chip — not a full
# Manage Sources tooltip). Allowlist only so junk meta cannot inflate the line.
# ``plan`` = payment/plan entitlement (FinRobot FMP 402), not a transient HTTP
# outage — friends must not read a billing wall as Yahoo flake.
YAHOO_FAIL_ERROR_CLASSES: frozenset[str] = frozenset(
    ("timeout", "inflight", "plan", "http", "empty", "thin", "error")
)
# Hidden spend side of a timeout↔inflight mix (count flag ≠ ownership).
YAHOO_FAIL_ALSO_SHARE_HOT = 50
YAHOO_FAIL_ALSO_SHARE_QUIET = 25
# Claim-drop ownership of the mover screen roster (count ≠ share).
YAHOO_CLAIM_DROP_SHARE_HOT = 50
YAHOO_CLAIM_DROP_SHARE_QUIET = 25
# Remaining screens after claim drop spoke (share ≠ usable roster).
YAHOO_CLAIM_DROP_KEPT_SHARE_STRONG = 75
YAHOO_CLAIM_DROP_KEPT_SHARE_THIN = 50
# Named class owns the mix when its share of timeout+inflight is this high.
YAHOO_FAIL_ALSO_WINNER_STRONG = 75
# Hidden% − winner% after mix lean spoke (labels ≠ how far the shares sit).
YAHOO_FAIL_ALSO_DELTA_WIDE_PP = 20
YAHOO_FAIL_ALSO_DELTA_THIN_PP = 10


def classify_yahoo_discovery_error(
    exc: BaseException | None = None,
    *,
    screens_ok: int | None = None,
    screens_failed: int | None = None,
    timeout_fails: int = 0,
    inflight_fails: int = 0,
) -> str:
    """Map a dead Yahoo movers fetch to a compact error class.

    xang1234 #639 reports content-source failures by kind so friends see
    *why* movers stayed dead — not only N× / fail age. Bundle path:
    ``empty`` when no screen answered; ``thin`` when majority failed but
    some answered. Transport timeouts own the class when they are the
    majority of failed screens (hung ≠ quiet empty). A still-live worker
    that refused a second ``yf.screen`` is ``inflight`` (held ≠ a new hang).
    Exception path: ``inflight`` / ``timeout`` / ``plan`` / ``http`` /
    ``error``. FinRobot #119: HTTP 402 / payment-required is account plan
    access, not a retryable provider outage — keep it out of the generic
    ``http`` bucket so the Universe glance speaks ``plan``.
    """
    try:
        timed_out = max(0, int(timeout_fails))
    except (TypeError, ValueError):
        timed_out = 0
    try:
        held = max(0, int(inflight_fails))
    except (TypeError, ValueError):
        held = 0
    if screens_ok is not None and screens_failed is not None:
        ok_n = max(0, int(screens_ok))
        fail_n = max(0, int(screens_failed))
        other_fails = max(0, fail_n - timed_out - held)
        dead = ok_n <= 0 or screens_bundle_failed(ok_n, fail_n)
        # Prefer inflight when a refused second spend owns (or ties) timeouts.
        if held > 0 and held >= max(1, timed_out) and held >= max(1, other_fails):
            if dead:
                return "inflight"
        # Prefer timeout when a fresh hang owns (or ties) the remaining fails.
        if timed_out > 0 and timed_out >= max(1, other_fails):
            if dead:
                return "timeout"
        if ok_n <= 0:
            return "empty"
        if screens_bundle_failed(ok_n, fail_n):
            return "thin"
    if exc is None:
        return "error"
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "still in flight" in msg:
        return "inflight"
    if (
        isinstance(exc, TimeoutError)
        or "timeout" in name
        or "timed out" in msg
        or "timeout" in msg
    ):
        return "timeout"
    # Payment/plan before generic http (FinRobot ProviderPlanError / 402).
    if (
        "402" in msg
        or "payment required" in msg
        or "payment/plan" in msg
        or "plan access" in msg
        or "providerplan" in name
    ):
        return "plan"
    if (
        "http" in name
        or "403" in msg
        or "404" in msg
        or "429" in msg
        or "http error" in msg
    ):
        return "http"
    if isinstance(exc, YahooScreenEmptyError) or "empty" in msg:
        return "empty"
    return "error"


def set_yahoo_discovery_error(meta: dict[str, Any], klass: str) -> str:
    """Persist allowlisted fail class on universe meta (clear junk)."""
    clean = str(klass or "").strip().lower()
    if clean not in YAHOO_FAIL_ERROR_CLASSES:
        clean = "error"
    meta["last_yahoo_discovery_error"] = clean
    return clean


def set_yahoo_discovery_error_sides(
    meta: dict[str, Any],
    *,
    timeout_fails: int = 0,
    inflight_fails: int = 0,
) -> None:
    """Persist timeout/inflight screen counts for glance mix honesty."""
    try:
        timed = max(0, int(timeout_fails))
    except (TypeError, ValueError):
        timed = 0
    try:
        held = max(0, int(inflight_fails))
    except (TypeError, ValueError):
        held = 0
    meta["last_yahoo_timeout_fails"] = timed
    meta["last_yahoo_inflight_fails"] = held


def clear_yahoo_discovery_error(meta: dict[str, Any]) -> None:
    """Drop last-error class after a successful movers snapshot."""
    meta.pop("last_yahoo_discovery_error", None)
    meta.pop("last_yahoo_timeout_fails", None)
    meta.pop("last_yahoo_inflight_fails", None)


def set_yahoo_discovery_claim_drops(
    meta: dict[str, Any],
    drops: int,
    *,
    dead: int = 0,
    stale: int = 0,
) -> int:
    """Persist how many dead/stale screen claims the last spend released.

    ``dead`` = finished worker · ``stale`` = live zombie past claim TTL
    (xang1234 history: say what each release did — absolute N alone hid why).
    """
    try:
        n = max(0, int(drops))
    except (TypeError, ValueError):
        n = 0
    try:
        n_dead = max(0, int(dead))
    except (TypeError, ValueError):
        n_dead = 0
    try:
        n_stale = max(0, int(stale))
    except (TypeError, ValueError):
        n_stale = 0
    if n <= 0:
        meta["last_yahoo_claim_drops"] = 0
        meta["last_yahoo_claim_drops_dead"] = 0
        meta["last_yahoo_claim_drops_stale"] = 0
        return 0
    n_dead = min(n_dead, n)
    n_stale = min(n_stale, n - n_dead)
    meta["last_yahoo_claim_drops"] = n
    meta["last_yahoo_claim_drops_dead"] = n_dead
    meta["last_yahoo_claim_drops_stale"] = n_stale
    return n


def set_yahoo_discovery_claim_live(
    meta: dict[str, Any],
    live: int,
    *,
    screens: Sequence[str] | None = None,
) -> int:
    """Persist how many screen claims stay held after the last spend.

    Alive workers inside the claim TTL are not released (xang1234 #726
    single-flight) — a later catch-up of that screen is refused until TTL.
    Absolute claim-drop / ok screens alone hid a stuck hung worker once
    other screens went green (xang1234 history: stuck asset not silent).
    Optional ``screens`` names which presets are still held (xang1234:
    say what a stuck asset blocks — absolute N alone hid the sleeve).
    Junk / negative → 0. Returns the stored count.
    """
    try:
        n = max(0, int(live))
    except (TypeError, ValueError):
        n = 0
    meta["last_yahoo_claim_live"] = n
    if n <= 0:
        meta["last_yahoo_claim_live_screens"] = []
        return 0
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in screens or ():
        label = _claim_live_screen_short(raw)
        if not label or label in seen:
            continue
        seen.add(label)
        cleaned.append(label)
        if len(cleaned) >= n:
            break
    meta["last_yahoo_claim_live_screens"] = cleaned
    return n


def yahoo_discovery_claim_drops(meta: Any) -> int:
    """Read last claim-release count; junk / missing → 0."""
    if not isinstance(meta, dict):
        return 0
    try:
        return max(0, int(meta.get("last_yahoo_claim_drops") or 0))
    except (TypeError, ValueError):
        return 0


def yahoo_discovery_claim_live(meta: Any) -> int:
    """Read last still-held screen claim count; junk / missing → 0."""
    if not isinstance(meta, dict):
        return 0
    try:
        return max(0, int(meta.get("last_yahoo_claim_live") or 0))
    except (TypeError, ValueError):
        return 0


# Compact Ops labels — full Yahoo preset names blow the Universe clip.
_CLAIM_LIVE_SCREEN_SHORT: dict[str, str] = {
    "day_gainers": "gainers",
    "day_losers": "losers",
    "most_actives": "actives",
}


def _claim_live_screen_short(raw: Any) -> str:
    """Map a Yahoo screen key to a short Ops label; junk → \"\"."""
    key = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not key:
        return ""
    if key in _CLAIM_LIVE_SCREEN_SHORT:
        return _CLAIM_LIVE_SCREEN_SHORT[key]
    # Unknown preset: keep a short token (≤12) so glance stays readable.
    token = re.sub(r"[^a-z0-9_]+", "", key)
    if not token:
        return ""
    return token[:12]


def yahoo_discovery_claim_live_screens(
    meta: Any,
) -> tuple[str, list[str]]:
    """Name stuck screens when claim live already spoke (display only).

    Absolute ``N claim live`` hid which preset still blocks catch-up
    (xang1234 history: say what a stuck asset blocks + Screener junk-list
    pointer + soft-allow gap ``last SYM``). Sole → ``last gainers``;
    multi → ``in gainers · losers``; missing / zero → silent. Returns
    ``(bit, labels)``.
    """
    n = yahoo_discovery_claim_live(meta)
    if n <= 0 or not isinstance(meta, dict):
        return "", []
    raw = meta.get("last_yahoo_claim_live_screens")
    labels: list[str] = []
    seen: set[str] = set()
    if isinstance(raw, (list, tuple)):
        for item in raw:
            label = _claim_live_screen_short(item)
            if not label or label in seen:
                continue
            seen.add(label)
            labels.append(label)
            if len(labels) >= n:
                break
    if not labels:
        return "", []
    if len(labels) == 1:
        return f"last {labels[0]}", labels
    return f"in {' · '.join(labels)}", labels


def yahoo_discovery_claim_live_screen_sample_gap(
    labels: Sequence[str] | None,
) -> str:
    """Speak ``tied`` when ≥2 named stuck screens (display only).

    Multi ``in gainers · losers`` alone hid that equal one-claim sleeves
    have no owner (Screener junk-list / claim-drop reason sample-gap +
    soft-allow / LAYA ``_decision_sample_gap`` parity + portfolio AI
    speak-both-sides). Sole ``last …`` / empty / junk stay silent on gap
    (each hung preset is one claim — no strict lead among equals).
    """
    if not isinstance(labels, (list, tuple)):
        return ""
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in labels:
        label = str(item or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        cleaned.append(label)
    if len(cleaned) < 2:
        return ""
    return "tied"


def yahoo_discovery_claim_live_share(
    live: int,
    *,
    screen_count: int | None = None,
) -> tuple[str, int | None, str]:
    """Claim-live ownership of the mover screen roster (portfolio AI count≠share).

    Absolute ``N claim live`` hid whether one hung screen or most of the
    bundle was still held after peers went green (xang1234 stuck-asset +
    claim-drop share parity). Same hot≥50% / quiet≤25% bands as claim-drop
    share. Zero / junk → silent. Returns ``(bit, pct, severity)``.
    """
    return yahoo_discovery_claim_drop_share(live, screen_count=screen_count)


def yahoo_discovery_claim_drop_reasons(
    meta: Any,
) -> tuple[str, int, int]:
    """Dead vs stale sides when claim drops already spoke (display only).

    Absolute ``N claim drop`` hid whether a finished worker leftover or a
    hung zombie was cleared (xang1234 history: say what each release did).
    Returns ``(bit, dead, stale)``. Zero total / both sides zero → silent
    (legacy meta without reason keys stays quiet). All-dead → ``dead``;
    all-stale → ``stale``; mix → ``N dead · M stale``.
    """
    if not isinstance(meta, dict):
        return "", 0, 0
    total = yahoo_discovery_claim_drops(meta)
    if total <= 0:
        return "", 0, 0
    try:
        dead = max(0, int(meta.get("last_yahoo_claim_drops_dead") or 0))
    except (TypeError, ValueError):
        dead = 0
    try:
        stale = max(0, int(meta.get("last_yahoo_claim_drops_stale") or 0))
    except (TypeError, ValueError):
        stale = 0
    dead = min(dead, total)
    stale = min(stale, total - dead)
    if dead <= 0 and stale <= 0:
        return "", 0, 0
    if dead > 0 and stale <= 0:
        return ("dead" if dead == total else f"{dead} dead"), dead, 0
    if stale > 0 and dead <= 0:
        return ("stale" if stale == total else f"{stale} stale"), 0, stale
    return f"{dead} dead · {stale} stale", dead, stale


def _claim_two_side_lead(
    left: int,
    right: int,
    *,
    left_name: str,
    right_name: str,
) -> tuple[str, str, int | None]:
    """Strict lead between two positive claim-side counts (display only).

    Both sides must be >0 and total ≥2; strict lead → ``lead NAME · N%``;
    ties / sole-side / junk → silent. Shared by dead/stale reason lead and
    drop/live activity lead.
    """
    try:
        n_left = max(0, int(left))
    except (TypeError, ValueError):
        n_left = 0
    try:
        n_right = max(0, int(right))
    except (TypeError, ValueError):
        n_right = 0
    total = n_left + n_right
    if total < 2 or n_left <= 0 or n_right <= 0:
        return "", "", None
    if n_left == n_right:
        return "", "", None
    if n_right > n_left:
        name, n = right_name, n_right
    else:
        name, n = left_name, n_left
    share = int(round(100.0 * n / total))
    return f"lead {name} · {share}%", name, share


def yahoo_discovery_claim_drop_reason_lead(
    dead: int,
    stale: int,
) -> tuple[str, str, int | None]:
    """Strict lead among dead vs stale claim-drop reasons (display only).

    Absolute ``N dead · M stale`` hid which release reason owns the sweep
    (Screener junk-list lead / soft-allow gap-symbol lead + portfolio AI
    count≠share + xang1234 multi-meter). Returns ``(bit, name, share_pct)``.
    Both sides must be >0 and total ≥2; strict lead → ``lead stale · N%``;
    ties / sole-side / junk → silent (use
    ``yahoo_discovery_claim_drop_reason_sample_gap`` for ``tied``).
    """
    return _claim_two_side_lead(
        dead, stale, left_name="dead", right_name="stale"
    )


def yahoo_discovery_claim_drop_reason_sample_gap(
    dead: int,
    stale: int,
) -> str:
    """Speak ``tied`` when dead/stale both spoke with no strict lead.

    ≥2 reasons with equal dead and stale speaks ``tied`` after the reason
    bit (soft-allow / Screener junk-list sample-gap parity). Lead cases /
    sole-side / zero stay silent on gap. Absolute sides alone hid that a
    50/50 release has no owner. Display only.
    """
    try:
        n_dead = max(0, int(dead))
    except (TypeError, ValueError):
        n_dead = 0
    try:
        n_stale = max(0, int(stale))
    except (TypeError, ValueError):
        n_stale = 0
    if n_dead <= 0 or n_stale <= 0:
        return ""
    lead_bit, _name, _share = yahoo_discovery_claim_drop_reason_lead(
        n_dead, n_stale
    )
    if lead_bit:
        return ""
    return "tied"


def yahoo_discovery_claim_drop_vs_live_lead(
    drops: int,
    live: int,
) -> tuple[str, str, int | None]:
    """Strict lead among claim-drop vs claim-live counts (display only).

    Absolute ``N claim drop`` beside ``M claim live`` hid which claim
    activity owns the sweep (release leftovers vs still-stuck screens —
    xang1234 multi-meter + portfolio AI speak-both-sides after both bits).
    Returns ``(bit, name, share_pct)``. Both sides must be >0 and total ≥2;
    strict lead → ``lead drop · N%`` / ``lead live · N%``; ties / sole-side
    / junk → silent (use ``yahoo_discovery_claim_drop_vs_live_sample_gap``).
    """
    return _claim_two_side_lead(
        drops, live, left_name="drop", right_name="live"
    )


def yahoo_discovery_claim_drop_vs_live_sample_gap(
    drops: int,
    live: int,
) -> str:
    """Speak ``drop/live tied`` when both sides spoke with no strict lead.

    Prefixed ``drop/live`` so the bit stays distinct from claim-live screen
    ``tied`` after ``in …``. Lead cases / sole-side / zero stay silent.
    Absolute drop+live alone hid that a 50/50 claim activity has no owner.
    Display only.
    """
    try:
        n_drops = max(0, int(drops))
    except (TypeError, ValueError):
        n_drops = 0
    try:
        n_live = max(0, int(live))
    except (TypeError, ValueError):
        n_live = 0
    if n_drops <= 0 or n_live <= 0:
        return ""
    lead_bit, _name, _share = yahoo_discovery_claim_drop_vs_live_lead(
        n_drops, n_live
    )
    if lead_bit:
        return ""
    return "drop/live tied"


def yahoo_discovery_claim_drop_share(
    drops: int,
    *,
    screen_count: int | None = None,
) -> tuple[str, int | None, str]:
    """Claim-drop ownership of the mover screen roster (portfolio AI count≠share).

    Absolute ``N claim drop`` hid whether one zombie or most of the bundle
    was cleared before spend. Share uses ``len(DEFAULT_SCREENS)`` unless
    ``screen_count`` is passed. ``hot`` ≥50% · ``quiet`` ≤25% · mid shows
    the percent only. Zero / junk → silent. Returns ``(bit, pct, severity)``
    ready to append after the count (``hot · 67%``).
    """
    try:
        n = max(0, int(drops))
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return "", None, ""
    try:
        denom = (
            len(DEFAULT_SCREENS)
            if screen_count is None
            else max(1, int(screen_count))
        )
    except (TypeError, ValueError):
        denom = len(DEFAULT_SCREENS)
    pct = int(round(100.0 * min(n, denom) / denom))
    if pct >= YAHOO_CLAIM_DROP_SHARE_HOT:
        return f"hot · {pct}%", pct, "hot"
    if pct <= YAHOO_CLAIM_DROP_SHARE_QUIET:
        return f"quiet · {pct}%", pct, "quiet"
    return f"{pct}%", pct, "ok"


def _yahoo_discovery_claim_vs_remainder(
    held: int,
    *,
    noun: str,
    screen_count: int | None = None,
) -> tuple[str, int | None, int | None, str]:
    """Remaining screens opposite a held claim count (display only).

    Shared by claim-drop→kept and claim-live→free. Zero / junk held →
    silent. Remainder = denom − min(held, denom); ``strong`` ≥75% ·
    ``thin`` <50% · mid shows the percent only. All-held →
    ``vs 0 {noun} · thin · 0%``.
    """
    try:
        n = max(0, int(held))
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return "", None, None, ""
    label = str(noun or "").strip() or "kept"
    try:
        denom = (
            len(DEFAULT_SCREENS)
            if screen_count is None
            else max(1, int(screen_count))
        )
    except (TypeError, ValueError):
        denom = len(DEFAULT_SCREENS)
    rem = max(0, denom - min(n, denom))
    pct = int(round(100.0 * rem / denom))
    if pct >= YAHOO_CLAIM_DROP_KEPT_SHARE_STRONG:
        severity = "strong"
        bit = f"vs {rem} {label} · strong · {pct}%"
    elif pct < YAHOO_CLAIM_DROP_KEPT_SHARE_THIN:
        severity = "thin"
        bit = f"vs {rem} {label} · thin · {pct}%"
    else:
        severity = "ok"
        bit = f"vs {rem} {label} · {pct}%"
    return bit, rem, pct, severity


def yahoo_discovery_claim_drop_vs_kept(
    drops: int,
    *,
    screen_count: int | None = None,
) -> tuple[str, int | None, int | None, str]:
    """Remaining screens when claim-drop share already spoke (display only).

    Absolute drop% alone hid whether the mover roster still had usable
    screens (Screener junk vs ok / soft-allow gap vs other + portfolio AI
    speak-both-sides). Returns ``(bit, kept_n, kept_pct, severity)``.
    Zero / junk drops → silent. Kept = denom − min(drops, denom);
    ``strong`` ≥75% · ``thin`` <50% · mid shows the percent only.
    All-drop → ``vs 0 kept · thin · 0%``.
    """
    return _yahoo_discovery_claim_vs_remainder(
        drops, noun="kept", screen_count=screen_count
    )


def yahoo_discovery_claim_drop_vs_kept_lean(
    drop_severity: str,
    kept_severity: str,
) -> tuple[str, bool]:
    """Lean agreement of claim-drop vs kept share bands (display only).

    Absolute ``hot|quiet · P%`` beside ``vs N kept · strong|thin`` hid
    whether the two *severity* bands agree (Screener junk vs ok lean /
    opportunity damaged vs ok lean + portfolio AI speak-both-sides +
    xang1234 severity). Align when ``hot|thin`` or ``quiet|strong``; clash
    when exactly one lean spoke or the pair disagrees. Adverse clash
    (drop hot / kept thin mismatch, or sole hot/thin) warns. Mid both
    silent. Desk keeps this in ``claim_lean`` so the Universe clip stays
    short. Not a gate.
    """
    drop = str(drop_severity or "").strip().casefold()
    kept = str(kept_severity or "").strip().casefold()
    drop_lean = drop in {"hot", "quiet"}
    kept_lean = kept in {"strong", "thin"}
    if drop_lean and kept_lean:
        matched = (drop == "hot" and kept == "thin") or (
            drop == "quiet" and kept == "strong"
        )
        if matched:
            return f"drop vs kept align · {drop}|{kept}", False
        return f"drop vs kept clash · drop {drop} · kept {kept}", True
    if drop_lean != kept_lean:
        drop_label = drop if drop_lean else (drop or "ok")
        kept_label = kept if kept_lean else (kept or "ok")
        warn = drop == "hot" or kept == "thin"
        return (
            f"drop vs kept clash · drop {drop_label} · kept {kept_label}",
            warn,
        )
    return "", False


def yahoo_discovery_claim_drop_kept_vs_live_free(
    drop_kept_lean: str,
    live_free_lean: str,
) -> tuple[str, bool]:
    """Mood agreement of drop-vs-kept lean vs live-vs-free lean (display only).

    Absolute ``drop vs kept align|clash`` beside ``live vs free align|clash``
    hid whether the two claim meters *agree* — FinRobot edge/conf + portfolio
    AI speak-both-sides + xang1234 multi-meter + improve-tick fresher polarity
    vs scan-meter after claim-drop vs kept lean + claim-live vs free lean hid
    meter agreement. Both calm → ``drop-kept vs live-free align · both
    align`` (confirm). Both adverse → ``… · both clash`` (warn — dual-clash
    ≠ quiet confirm; soft-allow share/lean parity). Mixed →
    ``clash · drop-kept vs live-free · drop clash · live-free align`` /
    ``clash · drop-kept vs live-free · drop align · live-free clash``
    (warn; stage name stays on the chip for lean meta). Sole side silent.
    Desk keeps this under ``claim_lean``. Not a gate.
    """
    dk = str(drop_kept_lean or "").strip()
    lf = str(live_free_lean or "").strip()
    if not dk or not lf:
        return "", False
    dk_adverse = "clash" in dk.casefold()
    lf_adverse = "clash" in lf.casefold()
    if dk_adverse == lf_adverse:
        if dk_adverse:
            return "drop-kept vs live-free align · both clash", True
        return "drop-kept vs live-free align · both align", False
    if dk_adverse:
        return (
            "clash · drop-kept vs live-free · drop clash · live-free align",
            True,
        )
    return (
        "clash · drop-kept vs live-free · drop align · live-free clash",
        True,
    )


def yahoo_discovery_claim_lean_meta(
    lean: str, *, warn: bool = False
) -> str:
    """Summary chip for Universe claim lean fold (display only).

    Bare quiet/warn hid whether drop vs kept / live vs free / drop-kept vs
    live-free severity spoke — MonsterDeveloper fold inventory + Screener/
    opportunity lean meta + improve-tick finished confirm after sides alone.
    Inventories spoken stages (``drop-kept vs live-free`` first ·
    ``drop vs kept`` · ``live vs free``). Warn → ``warn · …``; calm spoken
    lean → ``confirm · …`` (speak-both-sides peer of warn); empty →
    ``quiet``. Spoken meter stages also share improve-tick finished
    thin/not-thin honesty (``confirm · not thin · …`` / ``warn · not thin
    · …``) so bare confirm|warn after sides alone does not hide that a
    meter already spoke (xang1234 b09fb49 / 1cd7968 + portfolio AI
    speak-both-sides). Claim lean has no explain-only stages today — sole
    / few ``no result`` stays on improve-tick hung. Not a gate.
    """
    text = str(lean or "").strip()
    if not text:
        return "quiet"
    lower = text.casefold()
    stages: list[str] = []
    if "drop-kept vs live-free" in lower:
        stages.append("drop-kept vs live-free")
    if "drop vs kept" in lower:
        stages.append("drop vs kept")
    if "live vs free" in lower:
        stages.append("live vs free")
    prefix = "warn" if warn else "confirm"
    if not stages:
        return prefix
    # Meter stages → not thin (improve-tick finished thin/not-thin parity).
    return f"{prefix} · not thin · " + " · ".join(stages)


def yahoo_discovery_claim_live_vs_free(
    live: int,
    *,
    screen_count: int | None = None,
) -> tuple[str, int | None, int | None, str]:
    """Remaining free screens when claim-live share already spoke (display only).

    Absolute live% alone hid whether peers were free after a hung worker
    (claim-drop vs kept / Screener junk vs ok + portfolio AI speak-both-sides
    + xang1234 stuck-asset). Returns ``(bit, free_n, free_pct, severity)``.
    Zero / junk live → silent. Free = denom − min(live, denom);
    ``strong`` ≥75% · ``thin`` <50% · mid shows the percent only.
    All-live → ``vs 0 free · thin · 0%``.
    """
    return _yahoo_discovery_claim_vs_remainder(
        live, noun="free", screen_count=screen_count
    )


def yahoo_discovery_claim_live_vs_free_lean(
    live_severity: str,
    free_severity: str,
) -> tuple[str, bool]:
    """Lean agreement of claim-live vs free share bands (display only).

    Absolute ``hot|quiet · P%`` beside ``vs N free · strong|thin`` hid
    whether the two *severity* bands agree (claim-drop vs kept lean /
    Screener junk vs ok lean / opportunity damaged vs ok lean + portfolio
    AI speak-both-sides + xang1234 severity + MonsterDeveloper fold). Align
    when ``hot|thin`` or ``quiet|strong``; clash when exactly one lean spoke
    or the pair disagrees. Adverse clash (live hot / free thin mismatch, or
    sole hot/thin) warns. Mid both silent. Desk keeps this in ``claim_lean``
    so the Universe clip stays short. Not a gate.
    """
    live = str(live_severity or "").strip().casefold()
    free = str(free_severity or "").strip().casefold()
    live_lean = live in {"hot", "quiet"}
    free_lean = free in {"strong", "thin"}
    if live_lean and free_lean:
        matched = (live == "hot" and free == "thin") or (
            live == "quiet" and free == "strong"
        )
        if matched:
            return f"live vs free align · {live}|{free}", False
        return f"live vs free clash · live {live} · free {free}", True
    if live_lean != free_lean:
        live_label = live if live_lean else (live or "ok")
        free_label = free if free_lean else (free or "ok")
        warn = live == "hot" or free == "thin"
        return (
            f"live vs free clash · live {live_label} · free {free_label}",
            warn,
        )
    return "", False


def yahoo_discovery_error_class(meta: Any) -> str:
    """Read allowlisted last-error class; unknown / missing → ``\"\"``."""
    if not isinstance(meta, dict):
        return ""
    raw = str(meta.get("last_yahoo_discovery_error") or "").strip().lower()
    if raw in YAHOO_FAIL_ERROR_CLASSES:
        return raw
    return ""


def yahoo_fail_plan_held(meta: Any) -> bool:
    """True when last movers fail is a plan entitlement wall (FinRobot #119).

    Plan stays out of the auto-retry circuit: backoff expiry must not
    re-dispatch Yahoo spend against a billing wall. Clear only on a later
    success (or a non-plan fail that replaces the class).
    """
    if not isinstance(meta, dict):
        return False
    status = str(meta.get("last_yahoo_discovery_status") or "").strip().lower()
    if status != "failed":
        return False
    return yahoo_discovery_error_class(meta) == "plan"


def yahoo_discovery_error_sides(meta: Any) -> tuple[int, int]:
    """Read persisted timeout/inflight fail counts; junk → ``(0, 0)``."""
    if not isinstance(meta, dict):
        return 0, 0
    try:
        timed = max(0, int(meta.get("last_yahoo_timeout_fails") or 0))
    except (TypeError, ValueError):
        timed = 0
    try:
        held = max(0, int(meta.get("last_yahoo_inflight_fails") or 0))
    except (TypeError, ValueError):
        held = 0
    return timed, held


def yahoo_fail_error_also_bit(
    klass: str,
    *,
    timeout_fails: int = 0,
    inflight_fails: int = 0,
) -> str:
    """Speak the spend side the winning class hid (xang1234 #639 + portfolio AI).

    ``classify_yahoo_discovery_error`` picks one of ``timeout`` / ``inflight``
    when both screen sides failed. Bare ``inflight`` hid a fresh hang;
    bare ``timeout`` hid a refused second spend. Returns ``+timeout`` /
    ``+held`` / ``\"\"`` (both sides must be >0; other classes stay silent).
    """
    k = str(klass or "").strip().lower()
    try:
        timed = max(0, int(timeout_fails))
    except (TypeError, ValueError):
        timed = 0
    try:
        held = max(0, int(inflight_fails))
    except (TypeError, ValueError):
        held = 0
    if timed <= 0 or held <= 0:
        return ""
    if k == "inflight":
        return "+timeout"
    if k == "timeout":
        return "+held"
    return ""


def yahoo_fail_error_also_counts(
    klass: str,
    *,
    timeout_fails: int = 0,
    inflight_fails: int = 0,
) -> str:
    """Absolute timeout and inflight counts when the mix bit already spoke.

    Hidden share and Δ hid whether a 50/50 is one hung screen plus one held
    worker or a wide outage (xang1234 #639 + portfolio AI count ≠ share).
    Sole-side and other classes stay silent.
    """
    also = yahoo_fail_error_also_bit(
        klass, timeout_fails=timeout_fails, inflight_fails=inflight_fails
    )
    if not also:
        return ""
    try:
        timed = max(0, int(timeout_fails))
    except (TypeError, ValueError):
        timed = 0
    try:
        held = max(0, int(inflight_fails))
    except (TypeError, ValueError):
        held = 0
    return f"{timed} timeout · {held} held"


def yahoo_fail_error_also_share(
    klass: str,
    *,
    timeout_fails: int = 0,
    inflight_fails: int = 0,
) -> tuple[str, int | None, str]:
    """Hidden side's share of timeout+inflight (xang1234 #639 + portfolio AI).

    ``+timeout`` / ``+held`` alone hid whether the other spend is half the
    mix or a sliver. Share is the side the winning class did not name.
    ``hot`` ≥50% · ``quiet`` ≤25% · mid shows the percent only. Sole-side
    and other classes stay silent. Returns ``(bit, pct, severity)``.
    """
    also = yahoo_fail_error_also_bit(
        klass, timeout_fails=timeout_fails, inflight_fails=inflight_fails
    )
    if not also:
        return "", None, ""
    try:
        timed = max(0, int(timeout_fails))
    except (TypeError, ValueError):
        timed = 0
    try:
        held = max(0, int(inflight_fails))
    except (TypeError, ValueError):
        held = 0
    total = timed + held
    if total <= 0:
        return "", None, ""
    hidden = timed if also == "+timeout" else held
    pct = int(round(100.0 * hidden / total))
    if pct >= YAHOO_FAIL_ALSO_SHARE_HOT:
        return f"hot · {pct}%", pct, "hot"
    if pct <= YAHOO_FAIL_ALSO_SHARE_QUIET:
        return f"quiet · {pct}%", pct, "quiet"
    return f"{pct}%", pct, "ok"


def yahoo_fail_error_also_vs_winner(
    klass: str,
    *,
    timeout_fails: int = 0,
    inflight_fails: int = 0,
) -> tuple[str, int | None, str]:
    """Named class's share of timeout+inflight when hidden share already spoke.

    Hidden % alone hid the winning spend's ownership (friends invert
    100−hidden). ``strong`` ≥75 · mid shows the percent only. The winning
    count is at least the hidden count, so this share is ≥50 and there is
    no thin band. Returns ``(bit, pct, severity)``.
    """
    _bit, hidden_pct, _sev = yahoo_fail_error_also_share(
        klass, timeout_fails=timeout_fails, inflight_fails=inflight_fails
    )
    if hidden_pct is None:
        return "", None, ""
    k = str(klass or "").strip().lower()
    if k not in ("timeout", "inflight"):
        return "", None, ""
    try:
        timed = max(0, int(timeout_fails))
    except (TypeError, ValueError):
        timed = 0
    try:
        held = max(0, int(inflight_fails))
    except (TypeError, ValueError):
        held = 0
    total = timed + held
    if total <= 0:
        return "", None, ""
    winner_n = held if k == "inflight" else timed
    pct = int(round(100.0 * winner_n / total))
    if pct >= YAHOO_FAIL_ALSO_WINNER_STRONG:
        return f"vs {k} · strong · {pct}%", pct, "strong"
    return f"vs {k} · {pct}%", pct, "ok"


def yahoo_fail_error_also_vs_lean(
    hidden_severity: str,
    winner_severity: str,
) -> tuple[str, bool]:
    """Hidden share vs named-class share when both sides already spoke.

    Side-by-side percents hid a quiet sliver that agrees with a strong
    winner, and a hot half-mix whose class label does not own the spend.
    Mid/mid stays silent. ``align · quiet|strong`` does not warn.
    ``clash · hidden hot · winner ok`` (50/50) warns. Returns ``(bit, warn)``.
    """
    hidden = str(hidden_severity or "").strip().lower()
    winner = str(winner_severity or "").strip().lower()
    if hidden not in {"hot", "quiet", "ok"} or winner not in {"strong", "ok"}:
        return "", False
    if hidden not in {"hot", "quiet"} and winner != "strong":
        return "", False
    if hidden == "quiet" and winner == "strong":
        return "align · quiet|strong", False
    warn = hidden == "hot"
    return f"clash · hidden {hidden} · winner {winner}", warn


def yahoo_fail_error_also_vs_delta(
    hidden_pct: int | None,
    winner_pct: int | None,
) -> tuple[str, int | None, str]:
    """Hidden% − winner% once mix lean already spoke (xang1234 + portfolio AI).

    ``align · quiet|strong`` / ``clash · hidden hot`` hid whether the spend
    shares sit on top of each other or a wide gap. ``wide`` ≥20pp · ``thin``
    <10pp. Mid stays silent (no lean-vs-Δ nest). Returns ``(bit, pp, severity)``.
    """
    if hidden_pct is None or winner_pct is None:
        return "", None, ""
    try:
        delta = int(hidden_pct) - int(winner_pct)
    except (TypeError, ValueError):
        return "", None, ""
    abs_delta = abs(delta)
    if abs_delta >= YAHOO_FAIL_ALSO_DELTA_WIDE_PP:
        severity = "wide"
    elif abs_delta < YAHOO_FAIL_ALSO_DELTA_THIN_PP:
        severity = "thin"
    else:
        return "", None, ""
    sign = f"+{delta}" if delta > 0 else str(delta)
    return f"Δ {severity} · {sign}pp", delta, severity


def yahoo_fail_error_also_vs_delta_lead(
    klass: str,
    delta_pp: int | None,
    severity: str,
) -> str:
    """Name which spend side owns a spoken mix Δ (xang1234 + portfolio AI).

    ``Δ wide · -50pp`` is hidden%−winner%. The sign alone hid whether
    ``timeout`` or ``held`` is louder. Zero pp and a silent mid band stay
    quiet (no lean-vs-Δ nest). Returns ``Δ lead · timeout|held`` / ``\"\"``.
    """
    if str(severity or "").strip().lower() not in {"wide", "thin"}:
        return ""
    if delta_pp is None:
        return ""
    try:
        delta = int(delta_pp)
    except (TypeError, ValueError):
        return ""
    if delta == 0:
        return ""
    k = str(klass or "").strip().lower()
    if k == "inflight":
        winner, hidden = "held", "timeout"
    elif k == "timeout":
        winner, hidden = "timeout", "held"
    else:
        return ""
    lead = winner if delta < 0 else hidden
    return f"Δ lead · {lead}"


def yahoo_fail_error_also_vs_delta_lead_size(
    lead: str,
    hidden_pct: int | None,
    winner_pct: int | None,
    *,
    timeout_fails: int | None = None,
    inflight_fails: int | None = None,
) -> tuple[str, float | None]:
    """How many times the louder mix side owns the quieter one.

    ``Δ lead · held`` names the side. It hid a 3× ownership gap versus a
    near tie. Rounded percents also hid a 7-to-1 screen mix as ``7.33×``
    (1 and 7 → 12% and 88%). When both screen counts are known, the ratio
    uses those counts. Otherwise it uses the percents. Speaks only after
    lead already spoke and the quieter side is above zero. Returns
    ``(Δ lead size · N×, ratio)`` / ``(\"\", None)``.
    """
    if not str(lead or "").strip():
        return "", None
    louder: int | None = None
    quieter: int | None = None
    if timeout_fails is not None and inflight_fails is not None:
        try:
            timed = max(0, int(timeout_fails))
            held = max(0, int(inflight_fails))
        except (TypeError, ValueError):
            timed = held = 0
        if timed > 0 and held > 0:
            louder = max(timed, held)
            quieter = min(timed, held)
    if louder is None:
        if hidden_pct is None or winner_pct is None:
            return "", None
        try:
            louder = max(int(hidden_pct), int(winner_pct))
            quieter = min(int(hidden_pct), int(winner_pct))
        except (TypeError, ValueError):
            return "", None
    if quieter is None or quieter <= 0:
        return "", None
    size = round(louder / quieter, 2)
    return f"Δ lead size · {size:g}×", size


def yahoo_fail_error_also_vs_delta_lead_size_sides(
    size: float | None,
    klass: str,
    hidden_pct: int | None,
    winner_pct: int | None,
    *,
    timeout_fails: int | None = None,
    inflight_fails: int | None = None,
) -> tuple[str, int | None, int | None]:
    """Both named spend sides once mix Δ lead size already spoke.

    ``Δ lead size · 3×`` hid that held is 3 screens and timeout is 1.
    Rounded percents also hid a 7-to-1 mix as ``88%`` / ``12%`` beside
    ``7×``. When both screen counts are known and unequal, the sides use
    those counts. Otherwise they use the percents. Speaks only after a
    positive size and a known class. Louder name first. Returns
    ``(Δ lead size sides · held 7 · timeout 1, louder, quieter)``
    / ``(\"\", None, None)``.
    """
    try:
        ratio = float(size) if size is not None else 0.0
    except (TypeError, ValueError):
        return "", None, None
    k = str(klass or "").strip().lower()
    if k == "inflight":
        pass
    elif k == "timeout":
        pass
    else:
        return "", None, None
    if ratio <= 0:
        return "", None, None
    if timeout_fails is not None and inflight_fails is not None:
        try:
            timed = max(0, int(timeout_fails))
            held = max(0, int(inflight_fails))
        except (TypeError, ValueError):
            timed = held = 0
        if timed > 0 and held > 0 and timed != held:
            if held > timed:
                loud_name, quiet_name = "held", "timeout"
                louder, quieter = held, timed
            else:
                loud_name, quiet_name = "timeout", "held"
                louder, quieter = timed, held
            bit = (
                f"Δ lead size sides · {loud_name} {louder}"
                f" · {quiet_name} {quieter}"
            )
            return bit, louder, quieter
    if hidden_pct is None or winner_pct is None:
        return "", None, None
    try:
        hidden = int(hidden_pct)
        winner = int(winner_pct)
    except (TypeError, ValueError):
        return "", None, None
    if k == "inflight":
        winner_name, hidden_name = "held", "timeout"
    else:
        winner_name, hidden_name = "timeout", "held"
    louder = max(hidden, winner)
    quieter = min(hidden, winner)
    if quieter <= 0:
        return "", None, None
    if hidden >= winner:
        loud_name, quiet_name = hidden_name, winner_name
    else:
        loud_name, quiet_name = winner_name, hidden_name
    bit = (
        f"Δ lead size sides · {loud_name} {louder}% · {quiet_name} {quieter}%"
    )
    return bit, louder, quieter


def yahoo_fail_error_also_vs_delta_lead_size_sides_delta(
    sides: str,
    louder: int | None,
    quieter: int | None,
) -> tuple[str, int | None, str]:
    """Additive screen gap once mix Δ lead size sides named counts.

    ``Δ wide · -20pp`` is hidden%−winner% on rounded shares. A 3-vs-2 mix
    is one extra hung screen and still reads wide. ``held 3 · timeout 2``
    plus ``1.5×`` does not say that. Speak only after count sides (no
    ``%`` — percent sides already have the pp Δ). One extra screen is
    ``thin``; two or more is ``wide``. Returns
    ``(Δ lead size sides Δ wide|thin · N screens, gap, severity)``
    / ``(\"\", None, \"\")``.
    """
    text = str(sides or "")
    if not text.strip() or "%" in text:
        return "", None, ""
    if louder is None or quieter is None:
        return "", None, ""
    try:
        gap = int(louder) - int(quieter)
    except (TypeError, ValueError):
        return "", None, ""
    if gap <= 0:
        return "", None, ""
    severity = "thin" if gap == 1 else "wide"
    unit = "screen" if gap == 1 else "screens"
    return (
        f"Δ lead size sides Δ {severity} · {gap} {unit}",
        gap,
        severity,
    )


def yahoo_fail_error_also_vs_delta_lead_size_sides_share(
    sides_delta: str,
    sides: str,
    louder: int | None,
    quieter: int | None,
) -> tuple[str, int | None, int | None]:
    """Ownership of the count pair once mix Δ lead size sides Δ spoke.

    ``wide · 6 screens`` on 7 vs 1 is 88/12. The same gap on 20 vs 14 is
    59/41. Absolute screens ≠ who owns the pair. Percent sides stay silent
    (they already name %). Quieter percent is the remainder so the two
    shares sum to 100. Returns
    ``(Δ lead size sides share · held 88% · timeout 12%, louder%, quieter%)``
    / ``(\"\", None, None)``.
    """
    if not str(sides_delta or "").strip():
        return "", None, None
    text = str(sides or "")
    if not text.strip() or "%" in text:
        return "", None, None
    if louder is None or quieter is None:
        return "", None, None
    try:
        loud_n = int(louder)
        quiet_n = int(quieter)
    except (TypeError, ValueError):
        return "", None, None
    total = loud_n + quiet_n
    if loud_n <= 0 or quiet_n <= 0 or total <= 0:
        return "", None, None
    parts = [part.strip() for part in text.split(" · ")]
    if len(parts) < 3:
        return "", None, None
    loud_bits = parts[1].split()
    quiet_bits = parts[2].split()
    if len(loud_bits) < 2 or len(quiet_bits) < 2:
        return "", None, None
    loud_name, quiet_name = loud_bits[0], quiet_bits[0]
    if not loud_name.isalpha() or not quiet_name.isalpha():
        return "", None, None
    loud_pct = int(round(100.0 * loud_n / total))
    quiet_pct = 100 - loud_pct
    bit = (
        f"Δ lead size sides share · {loud_name} {loud_pct}%"
        f" · {quiet_name} {quiet_pct}%"
    )
    return bit, loud_pct, quiet_pct


def yahoo_fail_error_also_vs_delta_lead_size_sides_share_delta(
    share: str,
    louder_pct: int | None,
    quieter_pct: int | None,
) -> tuple[str, int | None, str]:
    """Ownership spread once mix Δ lead size sides share already spoke.

    ``held 88% · timeout 12%`` and ``timeout 59% · held 41%`` both name
    sides after the same screen-gap label can fire. Absolute % ≠ how far
    the pair sits. ``wide`` ≥20pp · ``thin`` <10pp · mid silent (no nest).
    Louder−quieter is always ≥0 when share spoke. Returns
    ``(Δ lead size sides share Δ wide|thin · +Npp, pp, severity)``
    / ``(\"\", None, \"\")``.
    """
    if not str(share or "").strip():
        return "", None, ""
    if louder_pct is None or quieter_pct is None:
        return "", None, ""
    try:
        delta = int(louder_pct) - int(quieter_pct)
    except (TypeError, ValueError):
        return "", None, ""
    if delta < 0:
        return "", None, ""
    abs_delta = abs(delta)
    if abs_delta >= YAHOO_FAIL_ALSO_DELTA_WIDE_PP:
        severity = "wide"
    elif abs_delta < YAHOO_FAIL_ALSO_DELTA_THIN_PP:
        severity = "thin"
    else:
        return "", None, ""
    sign = f"+{delta}" if delta > 0 else str(delta)
    return (
        f"Δ lead size sides share Δ {severity} · {sign}pp",
        delta,
        severity,
    )


def yahoo_fail_error_also_vs_delta_lead_size_sides_share_vs_gap(
    share_delta: str,
    share_severity: str,
    gap_severity: str,
) -> tuple[str, str, bool]:
    """Ownership-spread severity vs screen-gap severity (speak-both-sides).

    ``wide · 6 screens`` beside ``share Δ wide · +76pp`` can still hide a
    thin 1-screen gap beside a wide ownership spread (2 vs 1 is +34pp).
    Absolute screens ≠ pp ownership. Speak only when both severities are
    ``wide|thin`` (share Δ mid stays silent upstream). Same lean →
    ``align · wide|thin`` (not silent confirm). ``align · wide`` warns
    (both sides confirm a lopsided outage; ``align · thin`` stays calm).
    Crossed → ``clash · screens thin|wide · % wide|thin`` and warns.
    Returns ``(verb, bit, warn)`` / ``(\"\", \"\", False)``.
    """
    if not str(share_delta or "").strip():
        return "", "", False
    share = str(share_severity or "").strip().lower()
    gap = str(gap_severity or "").strip().lower()
    if share not in ("wide", "thin") or gap not in ("wide", "thin"):
        return "", "", False
    if share == gap:
        return (
            "align",
            f"Δ lead size sides share vs gap align · {share}",
            share == "wide",
        )
    return (
        "clash",
        f"Δ lead size sides share vs gap clash · screens {gap} · % {share}",
        True,
    )


# Quiet mix chip names spoken stages (Close honesty inventory). Cap matches
# the calm fold-name clip so a long Δ ladder does not bury the hidden side.
_MIX_QUIET_NAME_CAP = 4
_MIX_STAGE_RES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^\+timeout\b"), "+timeout"),
    (re.compile(r"^\+held\b"), "+held"),
    (re.compile(r"^\d+ timeout · \d+ held\b"), "counts"),
    (re.compile(r"^(?:hot|quiet) · \d+%"), "share"),
    (re.compile(r"^\d+%"), "share"),
    (re.compile(r"^vs (?:timeout|inflight) · (?:strong · )?\d+%"), "vs"),
    (re.compile(r"^(?:align|clash) ·"), "lean"),
    (re.compile(r"^Δ lead size sides share vs gap\b"), "vs gap"),
    (re.compile(r"^Δ lead size sides share Δ\b"), "share Δ"),
    (re.compile(r"^Δ lead size sides share ·"), "own"),
    (re.compile(r"^Δ lead size sides Δ\b"), "screens"),
    (re.compile(r"^Δ lead size sides ·"), "sides"),
    (re.compile(r"^Δ lead size ·"), "size"),
    (re.compile(r"^Δ lead ·"), "lead"),
    (re.compile(r"^Δ "), "Δ"),
)


def _quiet_inventory_chip(
    text: str,
    stages: tuple[tuple[re.Pattern[str], str], ...],
    *,
    cap: int,
    quiet: bool = True,
    front_if: str = "",
) -> str:
    """Name stages that actually spoke.

    Quiet: ``quiet · N folds · … · +K``. Hot tail (``quiet=False``): clipped
    names only (``unique · Δ · lean · lead · +K``), or ``""`` when none —
    Hours inactive hot-venue append parity. ``front_if`` moves matching
    names ahead of the clip so an adverse tail (``both clash``) is not
    hidden behind ``+K``.
    """

    def stage_at(blob: str) -> tuple[str, int] | None:
        for rx, label in stages:
            match = rx.match(blob)
            if not match:
                continue
            # Capture groups append to the label (``gap`` + ticker + age).
            pieces = [label] if label else []
            for i in range(1, (match.lastindex or 0) + 1):
                piece = str(match.group(i) or "").strip()
                if piece:
                    pieces.append(piece)
            shown = " ".join(pieces).strip()
            if shown:
                return shown, match.end()
        return None

    rest = str(text or "").strip()
    if not rest:
        return "quiet" if quiet else ""
    names: list[str] = []
    for _ in range(24):
        hit = stage_at(rest)
        if hit is None:
            break
        label, end = hit
        names.append(label)
        tail = rest[end:]
        rest = ""
        while tail:
            if tail.startswith(" · "):
                nxt = tail[3:]
                if stage_at(nxt):
                    rest = nxt
                    break
                tail = nxt
                continue
            sep = tail.find(" · ")
            if sep < 0:
                break
            tail = tail[sep:]
    if not names:
        return "quiet" if quiet else ""
    if front_if:
        front = [name for name in names if front_if in name]
        back = [name for name in names if front_if not in name]
        names = front + back
    extra = len(names) - cap
    shown = names[:cap]
    if extra > 0:
        shown.append(f"+{extra}")
    joined = " · ".join(shown)
    if not quiet:
        return joined
    unit = "fold" if len(names) == 1 else "folds"
    return f"quiet · {len(names)} {unit} · {joined}"


def _mix_quiet_chip(mix_lean: str) -> str:
    """``quiet · N folds · +timeout · counts · … · +K`` for bits on the line."""
    return _quiet_inventory_chip(
        mix_lean, _MIX_STAGE_RES, cap=_MIX_QUIET_NAME_CAP
    )


def yahoo_fail_mix_lean_meta(
    *,
    share_vs_gap: str,
    share_vs_gap_verb: str,
    share_vs_gap_warn: bool,
    lean_warn: bool,
    mix_lean: str = "",
) -> str:
    """Summary chip for the mix fold — why it opened, not another body bit.

    A quiet fold names the stages that spoke
    (``quiet · N folds · +timeout · counts · share · vs``), clipped at 4,
    so ``timeout · held`` does not claim both spend sides when the line is
    only the hidden flag plus counts. Empty text stays ``quiet``.
    A warned share-vs-gap speaks ``align · wide`` or ``clash`` (the fold
    body still holds the full bit). A lean-only warn speaks ``clash``.
    Hot chips also append clipped spoken stages
    (``align · wide · +timeout · counts · share · vs``) so severity alone
    does not hide which ladder bits spoke (Screener weight / Hours inactive
    hot inventory). ``align · thin`` does not warn, so it uses the quiet
    inventory.
    """

    def _hot(severity: str) -> str:
        stage_tail = _quiet_inventory_chip(
            mix_lean, _MIX_STAGE_RES, cap=_MIX_QUIET_NAME_CAP, quiet=False
        )
        if stage_tail:
            return f"{severity} · {stage_tail}"
        return severity

    if share_vs_gap_warn and str(share_vs_gap or "").strip():
        verb = str(share_vs_gap_verb or "").strip().lower()
        if verb == "align":
            tail = str(share_vs_gap).rsplit("·", 1)[-1].strip().lower()
            if tail in ("wide", "thin"):
                return _hot(f"align · {tail}")
        if verb == "clash":
            return _hot("clash")
    if lean_warn:
        return _hot("clash")
    return _mix_quiet_chip(mix_lean)


# Quiet error/streak chip names spoken relationships (mix quiet inventory).
# Longer prefixes first so ``error seed/fail`` is not read as ``seed/fail``.
_CASCADE_QUIET_NAME_CAP = 4
_CASCADE_STAGE_RES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^error sf/budget\b"), "sf/budget"),
    (re.compile(r"^error seed/fail\b"), "seed/fail"),
    (re.compile(r"^error/budget\b"), "budget"),
    (re.compile(r"^error/fail\b"), "fail"),
    (re.compile(r"^error/seed\b"), "seed"),
    (re.compile(r"^sf/budget\b"), "sf/budget"),
    (re.compile(r"^streak/budget\b"), "budget"),
    (re.compile(r"^streak/fail\b"), "fail"),
    (re.compile(r"^streak/seed\b"), "seed"),
    (re.compile(r"^seed/fail\b"), "seed/fail"),
)


def _cascade_quiet_chip(lean: str) -> str:
    """``quiet · N folds · seed · budget · …`` for bits on the lean line."""
    return _quiet_inventory_chip(
        lean, _CASCADE_STAGE_RES, cap=_CASCADE_QUIET_NAME_CAP
    )


def yahoo_fail_cascade_lean_meta(
    *,
    outer_bit: str = "",
    outer_warn: bool = False,
    inner_bit: str = "",
    inner_warn: bool = False,
    lean: str = "",
) -> str:
    """Summary chip for error/streak lean folds — why open, not another body bit.

    A quiet fold names the stages that spoke
    (``quiet · N folds · seed · budget``), clipped at 4, so ``cascade`` does
    not claim seed/fail/budget when the line is only a seed bit. Empty text
    stays ``quiet``. Prefer outer sf/budget warn over inner seed/fail.
    ``align · both clash`` / adverse ``align · both align`` keep that phrase;
    any ``clash · …`` bit shortens to ``clash``. Hot chips also append
    clipped spoken stages (``align · both clash · seed · budget · +K``) so
    severity alone does not hide which relationships spoke (mix / Screener
    weight hot inventory). Fold body still holds the full relationship text
    (mix-fold meta parity).
    """

    def _hot(severity: str) -> str:
        stage_tail = _quiet_inventory_chip(
            lean, _CASCADE_STAGE_RES, cap=_CASCADE_QUIET_NAME_CAP, quiet=False
        )
        if stage_tail:
            return f"{severity} · {stage_tail}"
        return severity

    bit = ""
    if outer_warn and str(outer_bit or "").strip():
        bit = str(outer_bit).strip()
    elif inner_warn and str(inner_bit or "").strip():
        bit = str(inner_bit).strip()
    else:
        return _cascade_quiet_chip(lean)
    low = bit.lower()
    if low.startswith("align · both "):
        tail = low[len("align · both ") :].strip()
        if tail in ("clash", "align"):
            return _hot(f"align · both {tail}")
    if low.startswith("clash"):
        return _hot("clash")
    return _hot("clash")


def yahoo_fail_error_vs_seed(error: str, seed_freshness: str) -> str:
    """Typed last-error vs reused-seed extremes (xang1234 #639 + portfolio AI).

    Allowlisted ``empty|thin|timeout|inflight|plan|http|error`` alone hid a
    still-fresh reused list on the *first* fail (N× / streak/seed stay silent
    until ≥2).
    Same polarity as ``yahoo_fail_streak_vs_seed``: fresh seed clashes with a
    typed dead Yahoo; stale seed aligns. Mid ``aging`` / missing class /
    never|unknown stay silent. Returns ``clash · fresh`` / ``align · stale``
    / ``""``.
    """
    klass = str(error or "").strip().lower()
    if klass not in YAHOO_FAIL_ERROR_CLASSES:
        return ""
    band = str(seed_freshness or "").strip().lower()
    if band == "fresh":
        return "clash · fresh"
    if band == "stale":
        return "align · stale"
    return ""


def yahoo_fail_error_vs_fail(error: str, fail_freshness: str) -> str:
    """Typed last-error vs fail-stamp extremes (xang1234 #639 + portfolio AI).

    Allowlisted class alone hid a stale fail stamp on the *first* fail
    (N× / streak/fail stay silent until ≥2). Same polarity as
    ``yahoo_fail_streak_vs_fail``: fresh fail aligns with typed death; stale
    fail clashes (class printed without a live death clock). Mid ``aging`` /
    missing class / never|unknown stay silent. Returns ``align · fresh`` /
    ``clash · stale`` / ``""``.
    """
    klass = str(error or "").strip().lower()
    if klass not in YAHOO_FAIL_ERROR_CLASSES:
        return ""
    band = str(fail_freshness or "").strip().lower()
    if band == "fresh":
        return "align · fresh"
    if band == "stale":
        return "clash · stale"
    return ""


def yahoo_fail_streak_vs_seed(streak: int, seed_freshness: str) -> str:
    """Streak vs reused-seed extremes when N× already spoke (xang1234 #639).

    Chronic ``N×`` beside a still-fresh seed looks healthy; a stale seed with
    a hot streak agrees. Mid ``aging`` / streak <2 / never|unknown stay
    silent. Returns ``clash · fresh`` / ``align · stale`` / ``""``.
    """
    try:
        n = int(streak)
    except (TypeError, ValueError):
        return ""
    if n < 2:
        return ""
    band = str(seed_freshness or "").strip().lower()
    if band == "fresh":
        return "clash · fresh"
    if band == "stale":
        return "align · stale"
    return ""


def yahoo_fail_streak_vs_fail(streak: int, fail_freshness: str) -> str:
    """Streak vs fail-stamp extremes when N× already spoke (xang1234 #639).

    Chronic ``N×`` with a fresh fail stamp agrees (live dead Yahoo). A stale
    fail stamp beside a hot streak clashes — counter kept climbing without a
    live death clock. Mid ``aging`` / streak <2 / never|unknown stay silent.
    Polarity is inverted vs ``yahoo_fail_streak_vs_seed`` (seed fresh = clash).
    Returns ``align · fresh`` / ``clash · stale`` / ``""``.
    """
    try:
        n = int(streak)
    except (TypeError, ValueError):
        return ""
    if n < 2:
        return ""
    band = str(fail_freshness or "").strip().lower()
    if band == "fresh":
        return "align · fresh"
    if band == "stale":
        return "clash · stale"
    return ""


def _yahoo_fail_budget_spend_bit(
    *,
    retry_due: bool,
    retry_remain_sec: int | None,
    plan_held: bool = False,
) -> str:
    """Fetch-budget hold vs about-to-spend (xang1234 #640/#642).

    Cooling (remain > 0) is unused capacity: ``clash · held · not spent``.
    FinRobot #119 plan walls stay held even after backoff expiry (not
    ``align · due``). Retry due aligns: ``align · due``. Missing remain
    while not due stays silent. Shared by streak (N×≥2) and first-fail
    typed error.
    """
    if plan_held:
        return "clash · held · not spent"
    if retry_due:
        return "align · due"
    try:
        remain = int(retry_remain_sec) if retry_remain_sec is not None else None
    except (TypeError, ValueError):
        return ""
    if remain is not None and remain > 0:
        # xang1234 #642: cooling = reservation not dispatched — speak not spent
        # so held backoff ≠ a live fetch that already burned budget.
        return "clash · held · not spent"
    return ""


def yahoo_fail_streak_vs_budget(
    streak: int,
    *,
    retry_due: bool,
    retry_remain_sec: int | None,
    plan_held: bool = False,
) -> str:
    """Streak vs fetch-budget spend when N× already spoke (xang1234 #640).

    Chronic ``N×`` alone hid whether discovery is still spending Yahoo fetch
    budget or holding unused capacity in fail backoff. Cooling (remain > 0)
    clashes with a hot streak (counter ≠ live spend). Retry due aligns
    (about to spend / spending again). Plan held never aligns due.
    Streak <2 / missing remain while not due stay silent. Returns
    ``clash · held · not spent`` / ``align · due`` / ``""``.
    """
    try:
        n = int(streak)
    except (TypeError, ValueError):
        return ""
    if n < 2:
        return ""
    return _yahoo_fail_budget_spend_bit(
        retry_due=retry_due,
        retry_remain_sec=retry_remain_sec,
        plan_held=plan_held,
    )


def yahoo_fail_error_vs_budget(
    error: str,
    *,
    retry_due: bool,
    retry_remain_sec: int | None,
    plan_held: bool = False,
) -> str:
    """Typed last-error vs fetch-budget on the first fail (xang1234 #640).

    Allowlisted class alone hid whether the first fail is holding unused
    Yahoo capacity or about to spend. Same grammar as
    ``yahoo_fail_streak_vs_budget``. Callers omit this when N× already owns
    streak/budget. Missing class / missing remain while not due stay silent.
    Returns ``clash · held · not spent`` / ``align · due`` / ``""``.
    """
    klass = str(error or "").strip().lower()
    if klass not in YAHOO_FAIL_ERROR_CLASSES:
        return ""
    return _yahoo_fail_budget_spend_bit(
        retry_due=retry_due,
        retry_remain_sec=retry_remain_sec,
        plan_held=plan_held or klass == "plan",
    )


def yahoo_fail_streak_seed_vs_fail(
    streak_vs_seed: str,
    streak_vs_fail: str,
) -> tuple[str, bool]:
    """Streak/seed vs streak/fail relationship agreement (display only).

    Returns ``(bit, warn)``. N×↔seed ≠ N×↔fail stamp. When both already
    spoke: same verb speaks ``align · both align|clash`` — ``both align``
    stays calm; ``both clash`` warns (dual-clash agreement ≠ quiet confirm).
    Crossed verbs speak ``clash · seed align|clash · fail align|clash``
    (warn). Missing either stays silent — portfolio AI speak-both-sides +
    soft-allow share/lean parity after streak/seed + streak/fail alone hid
    whether the two relationships agree. Not a gate.
    """
    seed_bit = str(streak_vs_seed or "").strip()
    fail_bit = str(streak_vs_fail or "").strip()
    if not seed_bit or not fail_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    seed_verb = _verb(seed_bit)
    fail_verb = _verb(fail_bit)
    if seed_verb is None or fail_verb is None:
        return "", False
    if seed_verb == fail_verb:
        return f"align · both {seed_verb}", seed_verb == "clash"
    return f"clash · seed {seed_verb} · fail {fail_verb}", True


def yahoo_fail_error_seed_vs_fail(
    error_vs_seed: str,
    error_vs_fail: str,
) -> tuple[str, bool]:
    """Error/seed vs error/fail relationship on first fail (display only).

    Same bit grammar as ``yahoo_fail_streak_seed_vs_fail`` — typed death vs
    seed ≠ typed death vs fail stamp. Side-by-side ``error/seed`` +
    ``error/fail`` alone hid whether the two relationships agree before
    N×≥2. Reuses the streak helper (identical verbs). Not a gate.
    """
    return yahoo_fail_streak_seed_vs_fail(error_vs_seed, error_vs_fail)


def yahoo_fail_error_seed_fail_vs_budget(
    error_seed_vs_fail: str,
    error_vs_budget: str,
) -> tuple[str, bool]:
    """Error seed/fail vs error/budget on the first fail (display only).

    Same bit grammar as ``yahoo_fail_streak_seed_fail_vs_budget``.
    Side-by-side ``error seed/fail`` + ``error/budget`` alone hid whether
    typed-death relationships agree with fetch-budget hold before N×≥2
    (including dual-clash under retry-due). Callers omit this when streak
    sf/budget already owns the lean. Not a gate.
    """
    return yahoo_fail_streak_seed_fail_vs_budget(
        error_seed_vs_fail, error_vs_budget
    )


def yahoo_fail_streak_seed_fail_vs_budget(
    seed_vs_fail: str,
    streak_vs_budget: str,
) -> tuple[str, bool]:
    """Seed/fail meta vs streak/budget agreement (display only).

    Returns ``(bit, warn)``. Seed/fail relationship ≠ fetch-budget hold.
    When both already spoke: same verb speaks ``align · both align|clash``
    — outer ``both clash`` warns; calm ``both align`` warns when seed/fail
    already spoke ``both clash`` and budget is ``due`` (inner dual-clash
    about to spend ≠ quiet confirm; soft-allow share/lean both-clash warn
    parity). Crossed verbs speak
    ``clash · seed/fail align|clash · budget align|clash`` (warn). Missing
    either stays silent — portfolio AI speak-both-sides + soft-allow
    share/lean parity after seed/fail + streak/budget alone hid whether
    the two relationships agree. Not a gate.
    """
    sf_bit = str(seed_vs_fail or "").strip()
    budget_bit = str(streak_vs_budget or "").strip()
    if not sf_bit or not budget_bit:
        return "", False

    def _verb(bit: str) -> str | None:
        if bit.startswith("align · "):
            return "align"
        if bit.startswith("clash · "):
            return "clash"
        return None

    sf_verb = _verb(sf_bit)
    budget_verb = _verb(budget_bit)
    if sf_verb is None or budget_verb is None:
        return "", False
    if sf_verb == budget_verb:
        bit = f"align · both {sf_verb}"
        # RyanJHamby + soft-allow both-clash warn: outer both-align can still
        # hide seed/fail dual-clash under retry-due (about to spend Yahoo).
        adverse_due = (
            sf_verb == "align"
            and "both clash" in sf_bit
            and "due" in budget_bit
        )
        return bit, sf_verb == "clash" or adverse_due
    return f"clash · seed/fail {sf_verb} · budget {budget_verb}", True


def yahoo_fail_retry_remaining_sec(
    meta: Any,
    *,
    now: datetime | None = None,
    fail_backoff_hours: int = DEFAULT_YAHOO_FAIL_BACKOFF_HOURS,
) -> int | None:
    """Seconds left on the fail backoff, or ``0`` when retry is due.

    ``None`` when status is not failed or the fail stamp is missing/unparsed
    (caller should treat missing stamp as retry-due immediately).
    """
    if not isinstance(meta, dict):
        return None
    status = str(meta.get("last_yahoo_discovery_status") or "").strip().lower()
    if status != "failed":
        return None
    fail_raw = str(meta.get("last_yahoo_discovery_fail") or "").strip()
    if not fail_raw:
        return None
    try:
        then = datetime.fromisoformat(fail_raw.replace("Z", "+00:00"))
        then = _naive_utc(then)
        clock = yahoo_clock_utc_naive(now)
        age_sec = max(0.0, (clock - then).total_seconds())
        limit = max(0, int(fail_backoff_hours)) * 3600.0
        return max(0, int(limit - age_sec))
    except (TypeError, ValueError):
        return None


def yahoo_discovery_due_from_meta(
    meta: Any,
    *,
    now: datetime | None = None,
    max_age_hours: int = DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS,
    fail_backoff_hours: int = DEFAULT_YAHOO_FAIL_BACKOFF_HOURS,
) -> bool:
    """True when movers have never succeeded or last success is older than max_age.

    xang1234: a failed fetch does not inherit the success-age throttle.
    xang1234 dfb6a86: after a failed fetch, wait ``fail_backoff_hours`` before
    retrying (missing fail stamp → retry immediately).
    FinRobot #119: a ``plan`` fail stays out of the auto-retry circuit —
    backoff expiry must not mark discovery due against a billing wall.
    """
    if not isinstance(meta, dict):
        return True
    status = str(meta.get("last_yahoo_discovery_status") or "").strip().lower()
    if status == "failed":
        # Plan entitlement ≠ flake — never auto-due (desk: retry held · plan).
        if yahoo_fail_plan_held(meta):
            return False
        remain = yahoo_fail_retry_remaining_sec(
            meta, now=now, fail_backoff_hours=fail_backoff_hours
        )
        # No / bad fail stamp → try again (cannot apply backoff).
        if remain is None:
            return True
        return remain <= 0
    last = str(meta.get("last_yahoo_discovery") or "").strip()
    if not last:
        return True
    try:
        then = datetime.fromisoformat(last.replace("Z", "+00:00"))
        then = _naive_utc(then)
        clock = yahoo_clock_utc_naive(now)
        age_h = (clock - then).total_seconds() / 3600.0
        return age_h >= float(max(1, int(max_age_hours)))
    except (TypeError, ValueError):
        return True


def release_dead_yahoo_screen_claims(
    *,
    max_age_sec: float | None = None,
    now: float | None = None,
) -> tuple[int, int, int]:
    """Drop finished or stale Yahoo screen claims (xang1234 #726).

    Returns ``(released, dead, stale)``. ``dead`` = finished worker;
    ``stale`` = live zombie past claim TTL. Alive workers younger than the
    claim TTL stay held so a second spend is refused.
    """
    ceiling = (
        float(DEFAULT_YAHOO_SCREEN_CLAIM_MAX_SEC)
        if max_age_sec is None
        else max(1.0, float(max_age_sec))
    )
    clock = time.monotonic() if now is None else float(now)
    released = 0
    dead = 0
    stale = 0
    with _yahoo_screen_inflight_lock:
        for key, entry in list(_yahoo_screen_inflight.items()):
            worker, started = entry
            age = clock - float(started)
            if worker.is_alive() and age < ceiling:
                continue
            if worker.is_alive():
                stale += 1
            else:
                dead += 1
            _yahoo_screen_inflight.pop(key, None)
            released += 1
    return released, dead, stale


def list_live_yahoo_screen_claims(
    *,
    max_age_sec: float | None = None,
    now: float | None = None,
) -> list[str]:
    """Screen keys still held by alive workers inside the claim TTL.

    Oldest claim first (most stuck). Does not mutate the map. Finished /
    stale zombies are omitted — ``release_dead_yahoo_screen_claims`` clears
    those. Used so Ops can name which preset blocks catch-up (xang1234:
    say what a stuck asset blocks).
    """
    ceiling = (
        float(DEFAULT_YAHOO_SCREEN_CLAIM_MAX_SEC)
        if max_age_sec is None
        else max(1.0, float(max_age_sec))
    )
    clock = time.monotonic() if now is None else float(now)
    held: list[tuple[float, str]] = []
    with _yahoo_screen_inflight_lock:
        for key, entry in _yahoo_screen_inflight.items():
            worker, started = entry
            age = clock - float(started)
            if worker.is_alive() and age < ceiling:
                held.append((float(started), str(key)))
    held.sort()
    return [name for _started, name in held]


def count_live_yahoo_screen_claims(
    *,
    max_age_sec: float | None = None,
    now: float | None = None,
) -> int:
    """Count alive workers still inside the claim TTL (display/ops).

    Does not mutate the map. Finished / stale zombies are not live —
    ``release_dead_yahoo_screen_claims`` clears those. A hung screen that
    timed out but is still inside TTL stays live and blocks that name
    (xang1234 stuck-asset honesty after other screens go green).
    """
    return len(list_live_yahoo_screen_claims(max_age_sec=max_age_sec, now=now))


def fetch_yahoo_screen_symbols(
    screen: str,
    *,
    count: int = DEFAULT_MOVER_COUNT,
    timeout_sec: int | None = None,
    claim_max_sec: float | None = None,
) -> List[str]:
    """
    Return tradeable equity symbols from a yfinance predefined screen.

    Network call — wrap in try/except at call sites. Offline tests should mock.
    xang1234 #639: join ceiling so a hung Yahoo cannot stall the scan loop;
    timeout raises ``TimeoutError`` (not quiet empty). A still-live worker
    inside the claim TTL blocks a second dispatch for the same screen
    (hung ≠ another spend). xang1234 #726: dead or stale claims release so a
    zombie hang cannot block that screen until container restart.
    """
    import yfinance as yf

    want = max(1, min(100, int(count)))
    limit = (
        DEFAULT_YAHOO_SCREEN_TIMEOUT_SEC
        if timeout_sec is None
        else max(1, int(timeout_sec))
    )
    claim_ceiling = (
        float(DEFAULT_YAHOO_SCREEN_CLAIM_MAX_SEC)
        if claim_max_sec is None
        else max(1.0, float(claim_max_sec))
    )
    screen_key = str(screen or "").strip() or "screen"
    box: dict[str, Any] = {}

    def _call() -> None:
        try:
            box["payload"] = yf.screen(screen, count=want)
        except Exception as e:
            box["error"] = e

    worker = threading.Thread(
        target=_call, name=f"yahoo-screen-{screen_key}", daemon=True
    )
    with _yahoo_screen_inflight_lock:
        prev = _yahoo_screen_inflight.get(screen_key)
        if prev is not None:
            prev_worker, started = prev
            age = time.monotonic() - float(started)
            if prev_worker.is_alive() and age < claim_ceiling:
                raise TimeoutError(
                    f"yahoo screen {screen_key} still in flight — timed out"
                )
            # Dead thread or stale zombie claim — release before new spend.
            _yahoo_screen_inflight.pop(screen_key, None)
        _yahoo_screen_inflight[screen_key] = (worker, time.monotonic())
    worker.start()
    try:
        worker.join(timeout=float(limit))
        if worker.is_alive():
            raise TimeoutError(
                f"yahoo screen {screen_key} timed out after {limit}s"
            )
    finally:
        if not worker.is_alive():
            with _yahoo_screen_inflight_lock:
                held = _yahoo_screen_inflight.get(screen_key)
                if held is not None and held[0] is worker:
                    _yahoo_screen_inflight.pop(screen_key, None)
    if "error" in box:
        err = box["error"]
        if isinstance(err, TimeoutError):
            raise err
        # xang1234 008f0ca: HTTP 403 / soft block → failed screen, not a raise
        # out of universe refresh.
        raise YahooScreenEmptyError(screen) from err
    payload = box.get("payload")
    if screen_payload_failed(payload, expected=want):
        raise YahooScreenEmptyError(screen)
    out: list[str] = []
    seen: set[str] = set()
    for q in _quotes_from_screen_payload(payload):
        sym = str(q.get("symbol") or "").strip().upper()
        if not sym or sym in seen:
            continue
        if not is_tradeable_symbol(sym):
            continue
        # Skip obvious non-common noise (warrants / units) if any slip through.
        if any(ch in sym for ch in ("=", "^", "/")):
            continue
        seen.add(sym)
        out.append(sym)
    return out


def discover_yahoo_mover_report(
    *,
    screens: Sequence[str] = DEFAULT_SCREENS,
    per_screen: int = DEFAULT_MOVER_COUNT,
    timeout_sec: int | None = None,
) -> tuple[List[str], int, int, int, int, int, int, int]:
    """Symbols plus ok / failed / timeout / inflight / claim counts.

    Claim drops (xang1234 #726): finished or stale single-flight claims
    released before this bundle — Ops can see a zombie was cleared.
    Claim live (xang1234 stuck-asset honesty): alive workers still inside
    TTL after the bundle — a hung screen is not silent once peers succeed.
    Trailing ints are ``claim_drops``, ``claim_dead``, ``claim_stale``,
    ``claim_live``.
    """
    # Sweep finished/stale claims before the bundle so a prior hung screen
    # does not poison the first name in the list (xang1234 #726).
    claim_drops, claim_dead, claim_stale = release_dead_yahoo_screen_claims()
    out: list[str] = []
    seen: set[str] = set()
    ok = 0
    failed = 0
    timeouts = 0
    inflight = 0
    for name in screens:
        try:
            batch = fetch_yahoo_screen_symbols(
                name, count=per_screen, timeout_sec=timeout_sec
            )
            ok += 1
        except TimeoutError as e:
            failed += 1
            if "still in flight" in str(e).lower():
                inflight += 1
            else:
                timeouts += 1
            continue
        except Exception:
            failed += 1
            continue
        for sym in batch:
            if sym in seen:
                continue
            if not is_tradeable_symbol(sym):
                continue
            seen.add(sym)
            out.append(sym)
    claim_live = count_live_yahoo_screen_claims()
    return (
        out,
        ok,
        failed,
        timeouts,
        inflight,
        claim_drops,
        claim_dead,
        claim_stale,
        claim_live,
    )


def discover_yahoo_mover_symbols(
    *,
    screens: Sequence[str] = DEFAULT_SCREENS,
    per_screen: int = DEFAULT_MOVER_COUNT,
) -> List[str]:
    """Union of symbols across screens, stable order, de-duplicated."""
    symbols, _ok, _failed, _timeouts, _inflight, _drops, _dead, _stale, _live = (
        discover_yahoo_mover_report(screens=screens, per_screen=per_screen)
    )
    return symbols


def sector_hint_from_quote(quote: dict[str, Any] | None) -> str:
    if not isinstance(quote, dict):
        return "unknown"
    sector = quote.get("sector")
    if isinstance(sector, str) and sector.strip():
        return sector.strip().lower().replace(" ", "_")
    return "unknown"


def exchange_hint_from_quote(quote: dict[str, Any] | None) -> str:
    if not isinstance(quote, dict):
        return "unknown"
    for key in ("fullExchangeName", "exchange"):
        val = quote.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().upper()
    return "unknown"
