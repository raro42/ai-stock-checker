"""Ops mutating-action audit (xang1234 #613 / #628 pattern).

Write a ``requested`` row *before* the side effect. If that commit fails,
do not act. After the action, write an outcome row (``accepted`` / ``error``).
Outcome write failure must not disguise a successful change — return the
real result and keep the request row so friends see intent without a
silent mutation.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

OPS_ACTIONS_FILE = "ops_actions.json"
OPS_ACTIONS_CAP = 40
# Refuse a second same-kind mutation while a fresh ``requested`` row is still
# hanging (xang1234 #606/#613 double-click / in-flight refuse). Older hangings
# fail-open for Save but the glance speaks ``stale pending`` (crash leftover ≠
# in-flight) so friends do not treat an aged hang as a live refuse window.
OPS_PENDING_REFUSE_SECONDS = 120
# Terminal + hanging outcome age bands (display only) — same floors as Ops
# saved-row ``file_freshness`` so audit age and config mtime speak one scale.
OPS_OUTCOME_FRESH_HOURS = 24
OPS_OUTCOME_AGING_HOURS = 168
# ``_safe_detail`` strip ceilings (Save Δ / open_cash / note tags).
OPS_DETAIL_KEYS_MAX = 24
OPS_DETAIL_CHANGED_ITEMS_MAX = 16
OPS_DETAIL_CHANGED_ITEM_CHARS = 40
OPS_DETAIL_OPEN_CASH_ITEMS_MAX = 4
OPS_DETAIL_OPEN_CASH_ITEM_CHARS = 16
OPS_DETAIL_STRING_CHARS = 80

T = TypeVar("T")


def _coerce_ops_detail_ceiling(
    value: object, default: int
) -> int:
    """Positive Ops detail strip ceiling, or ``default`` when bool/gap/≤0.

    FinRobot + tradermonty #700/#655 + xang1234/portfolio AI: ``True→1`` must
    not invent a one-key / one-char Save Δ via ``items[:True]`` /
    ``s[:True]``; ``False→0`` must not wipe (soft-allow reason clip peer —
    ring/TTL already refused; detail ceilings were still bare ``[:24]`` /
    ``[:40]`` / ``[:80]``).
    """
    from stock_checker.entry_slots import coerce_nonneg_int

    n = coerce_nonneg_int(value)
    if n is None or n <= 0:
        return int(default)
    return n


def _coerce_ops_refuse_seconds(
    value: object, default: int = OPS_PENDING_REFUSE_SECONDS
) -> int:
    """Positive in-flight refuse window, or ``default`` when bool/gap.

    tradermonty #700/#655 + xang1234/portfolio AI: ``int(True)→1`` must not
    invent a 1s double-click refuse band (soft-allow TTL peer).
    """
    from stock_checker.entry_slots import coerce_nonneg_int

    n = coerce_nonneg_int(value)
    if n is None or n < 1:
        return int(default)
    return n


def _coerce_ops_actions_cap(value: object, default: int = OPS_ACTIONS_CAP) -> int:
    """Ops audit ring length, or ``default`` when bool/gap.

    tradermonty #700/#655 + xang1234/portfolio AI: ``int(True)→1`` /
    ``False→0→max(1,0)`` must not invent a one-row audit ring (soft-allow
    retention peer).
    """
    from stock_checker.entry_slots import coerce_nonneg_int

    n = coerce_nonneg_int(value)
    if n is None:
        return int(default)
    return n


def _coerce_ops_outcome_hours(value: object, default: float) -> float:
    """Non-negative outcome age hours, or ``default`` when bool/gap.

    tradermonty #700/#655 + xang1234/portfolio AI: ``float(True)→1h`` must
    not invent a thin fresh/aging band (soft-allow hours peer).
    """
    from stock_checker.technical_indicators import _finite_signed

    if value is None or not _finite_signed(value):
        return float(default)
    hours = float(value)  # type: ignore[arg-type]
    return hours if hours >= 0.0 else float(default)


def ops_actions_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / OPS_ACTIONS_FILE


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ops_at(raw: Any) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def pending_ops_in_flight(
    data_dir: Path | str,
    *,
    kind: str,
    now: datetime | None = None,
    refuse_seconds: int = OPS_PENDING_REFUSE_SECONDS,
) -> dict[str, Any] | None:
    """Newest same-kind ``requested`` row when still inside the refuse window.

    Unparseable / aged-out hangings return ``None`` (fail-open) so Ops can save
    again after a crashed mid-flight; the glance speaks ``stale pending`` for
    aged hangings (see ``format_last_ops_action_bit``).

    Fresh hangings whose Ops file is already newer than the request also
    return ``None`` (xang1234 #630 no-worker-for-queue: do not keep Run/Save
    blocked waiting for an accepted stamp that will not arrive — glance still
    speaks ``pending · no outcome``).
    """
    last = last_ops_action(data_dir, kind=kind)
    if not isinstance(last, dict):
        return None
    band = ops_pending_freshness_band(
        last, now=now, refuse_seconds=refuse_seconds
    )
    if band != "fresh":
        return None
    if ops_pending_no_outcome(
        last, config_mtime=trader_config_mtime_utc(data_dir)
    ):
        return None
    return last


def ops_pending_freshness_band(
    row: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    refuse_seconds: int = OPS_PENDING_REFUSE_SECONDS,
) -> str | None:
    """``fresh`` / ``stale`` for a hanging ``requested`` row; else ``None``.

    Fresh = still inside the refuse window (in-flight). Stale = aged past it
    (crash leftover / abandoned). Unparseable stamps stay ``None`` (fail-open
    label: plain ``pending``).
    """
    if not isinstance(row, dict):
        return None
    if str(row.get("outcome") or "") != "requested":
        return None
    stamp = _parse_ops_at(row.get("at"))
    if stamp is None:
        return None
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    age = (clock.astimezone(timezone.utc) - stamp).total_seconds()
    if age < 0:
        return None
    window = _coerce_ops_refuse_seconds(refuse_seconds)
    if age < window:
        return "fresh"
    return "stale"


def trader_config_mtime_utc(data_dir: Path | str) -> datetime | None:
    """``trader_config.json`` mtime as UTC, or ``None`` when missing/unreadable."""
    from stock_checker.trader_config import config_path

    path = config_path(data_dir)
    try:
        if not path.is_file():
            return None
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def ops_pending_no_outcome(
    row: dict[str, Any] | None,
    *,
    config_mtime: datetime | None = None,
) -> bool:
    """True when hanging ``requested`` and Ops file is strictly newer.

    xang1234 #630: a queued job with no responding worker looks live forever.
    Here a hanging request whose outcome writer never answered while
    ``trader_config.json`` already moved looks forever-pending — speak
    ``no outcome`` so friends do not wait for an accepted stamp that will
    not arrive. Missing / unparseable clocks fail-open (False).
    """
    if not isinstance(row, dict):
        return False
    if str(row.get("outcome") or "") != "requested":
        return False
    if config_mtime is None:
        return False
    stamp = _parse_ops_at(row.get("at"))
    if stamp is None:
        return False
    mtime = config_mtime
    if mtime.tzinfo is None:
        mtime = mtime.replace(tzinfo=timezone.utc)
    else:
        mtime = mtime.astimezone(timezone.utc)
    # Audit stamps are second-precision ISO-Z; fractional file mtime in the
    # same second must not look "newer" (would false-open a live in-flight
    # Save). Floor both sides so only a clearly later second counts.
    return mtime.replace(microsecond=0) > stamp.replace(microsecond=0)


def load_ops_actions(data_dir: Path | str) -> list[dict[str, Any]]:
    """Newest-first ring of Ops audit rows (empty on missing/junk)."""
    path = ops_actions_path(data_dir)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if isinstance(raw, list):
        events = raw
    elif isinstance(raw, dict):
        events = raw.get("events")
    else:
        return []
    if not isinstance(events, list):
        return []
    out: list[dict[str, Any]] = []
    for row in events:
        if isinstance(row, dict):
            out.append(row)
    return out


def append_ops_action(
    data_dir: Path | str,
    row: dict[str, Any],
    *,
    cap: int = OPS_ACTIONS_CAP,
) -> bool:
    """Append one audit row. Returns False if the write failed."""
    path = ops_actions_path(data_dir)
    try:
        events = load_ops_actions(data_dir)
        events.append(dict(row))
        # Soft-allow retention already refused bool; Ops audit ring was still open.
        keep = max(1, _coerce_ops_actions_cap(cap))
        events = events[-keep:]
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = str(events[-1].get("at") or _now_iso())
        path.write_text(
            json.dumps({"updated_at": stamp, "events": events}, indent=2) + "\n",
            encoding="utf-8",
        )
        return True
    except OSError as exc:
        logger.warning("ops audit write failed: %s", exc)
        return False


def last_ops_action(
    data_dir: Path | str,
    *,
    kind: str | None = None,
) -> dict[str, Any] | None:
    """Newest audit row (optionally filtered by kind). Newest-last on disk."""
    events = load_ops_actions(data_dir)
    want = (kind or "").strip()
    for row in reversed(events):
        if want and str(row.get("kind") or "") != want:
            continue
        return row
    return None


def ops_skip_reason_label(row: dict[str, Any] | None) -> str:
    """Compact why for a ``skipped`` row (xang1234 #599/#623 skip-says-why).

    Bare ``skipped`` hid whether Ops refused a no-op Save vs some other
    preflight. Unknown / empty reasons stay silent so the glance does not
    invent a cause.
    """
    if not isinstance(row, dict):
        return ""
    if str(row.get("outcome") or "") != "skipped":
        return ""
    raw = str(row.get("reason") or "").strip().lower().replace("_", "-")
    if not raw:
        detail = row.get("detail")
        if isinstance(detail, dict):
            raw = str(detail.get("reason") or "").strip().lower().replace("_", "-")
    if raw in ("no-op", "noop", "no-change", "nochange"):
        return "no-op"
    if raw and len(raw) <= 24 and all(c.isalnum() or c in "-." for c in raw):
        return raw
    return ""


def ops_error_reason_from_exc(exc: BaseException) -> str:
    """Compact non-secret why for an ``error`` audit row.

    Exception *messages* stay out of the glance (paths / hosts). Class family
    is enough for friends to tell write fail vs bad value vs act fail
    (xang1234 #621 show-request-failures adapted — bare ``error`` hid cause).
    """
    if isinstance(exc, OSError):
        return "write-fail"
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return "bad-value"
    return "act-fail"


def ops_error_reason_label(row: dict[str, Any] | None) -> str:
    """Compact why for an ``error`` row (xang1234 #621 failure visibility).

    Bare ``error`` hid write-fail vs act-fail after reload. Unknown / empty
    reasons stay silent so the glance does not invent a cause.
    """
    if not isinstance(row, dict):
        return ""
    if str(row.get("outcome") or "") != "error":
        return ""
    raw = str(row.get("reason") or "").strip().lower().replace("_", "-")
    if not raw:
        detail = row.get("detail")
        if isinstance(detail, dict):
            raw = str(detail.get("reason") or "").strip().lower().replace("_", "-")
    if raw in ("write-fail", "writefail", "io", "oserror"):
        return "write-fail"
    if raw in ("bad-value", "badvalue", "value", "type"):
        return "bad-value"
    if raw in ("act-fail", "actfail", "runtime", "failed"):
        return "act-fail"
    if raw and len(raw) <= 24 and all(c.isalnum() or c in "-." for c in raw):
        return raw
    return ""


def _coerce_ops_age_sec(value: object) -> float | None:
    """Non-negative age/lag seconds, or None when bool/gap/NaN.

    tradermonty #700/#655 + xang1234/portfolio AI: ``float(True)→1`` /
    ``int(True)→1`` must not invent ``now`` / ``1s`` / thin sides Δ on
    Ops audit vs file clocks (desk cash-print / pin-lag age peer).
    """
    from stock_checker.technical_indicators import _finite_signed

    if value is None or not _finite_signed(value):
        return None
    age = float(value)  # type: ignore[arg-type]
    if age < 0.0:
        return None
    return age


def _ops_age_short(age_sec: object) -> str:
    """Compact wall age (``now`` / ``45s`` / ``6m`` / ``3h`` / ``2d``).

    Bool/gap speak ``n/a`` — never invent ``now`` from ``True``.
    """
    age = _coerce_ops_age_sec(age_sec)
    if age is None:
        return "n/a"
    sec = int(age)
    if sec < 60:
        return "now" if sec < 5 else f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m"
    if sec < 36 * 3600:
        return f"{sec // 3600}h"
    return f"{sec // 86400}d"


def ops_outcome_age_band(
    row: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    fresh_hours: float = OPS_OUTCOME_FRESH_HOURS,
    aging_hours: float = OPS_OUTCOME_AGING_HOURS,
) -> str:
    """``fresh`` / ``aging`` / ``stale`` for an audit stamp, or ``\"\"``.

    Same floors as Ops saved-row ``file_freshness`` (24h · 7d). Unparseable
    / future stamps stay empty (fail-open).
    """
    if not isinstance(row, dict):
        return ""
    stamp = _parse_ops_at(row.get("at"))
    if stamp is None:
        return ""
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    age_sec = (clock.astimezone(timezone.utc) - stamp).total_seconds()
    if age_sec < 0:
        return ""
    hours = age_sec / 3600.0
    fresh = _coerce_ops_outcome_hours(fresh_hours, OPS_OUTCOME_FRESH_HOURS)
    aging = _coerce_ops_outcome_hours(aging_hours, OPS_OUTCOME_AGING_HOURS)
    if hours < fresh:
        return "fresh"
    if hours < aging:
        return "aging"
    return "stale"


def ops_file_freshness_band(
    config_mtime: datetime | None,
    *,
    now: datetime | None = None,
    fresh_hours: float = OPS_OUTCOME_FRESH_HOURS,
    aging_hours: float = OPS_OUTCOME_AGING_HOURS,
) -> str:
    """``fresh`` / ``aging`` / ``stale`` for Ops file mtime, or ``\"\"``.

    Parity with ``trader_config`` saved-row floors so audit vs file can clash
    on one scale. Missing mtime stays empty (fail-open).
    """
    if config_mtime is None:
        return ""
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    mtime = config_mtime
    if mtime.tzinfo is None:
        mtime = mtime.replace(tzinfo=timezone.utc)
    else:
        mtime = mtime.astimezone(timezone.utc)
    age_sec = (clock.astimezone(timezone.utc) - mtime).total_seconds()
    if age_sec < 0:
        return ""
    hours = age_sec / 3600.0
    fresh = _coerce_ops_outcome_hours(fresh_hours, OPS_OUTCOME_FRESH_HOURS)
    aging = _coerce_ops_outcome_hours(aging_hours, OPS_OUTCOME_AGING_HOURS)
    if hours < fresh:
        return "fresh"
    if hours < aging:
        return "aging"
    return "stale"


# fresher → older so clash can name which clock is newer (hand-edit vs lag).
_OPS_BAND_AGE_RANK = {"fresh": 0, "aging": 1, "stale": 2}


def _ops_vs_file_clash_sides_delta(audit_age: object, file_age: object) -> str:
    """``sides Δ wide|thin · Nd`` when |age spread| is extreme; mid silent.

    Sides name both wall ages; Δ is the additive spread so a thin band span
    on nearly equal clocks (or a wide band span on close ages) does not look
    like a huge clock gap — FinRobot/xang1234 gap-dir sides Δ + portfolio AI
    after sides alone. Wide ≥ aging floor (7d); thin < fresh floor (24h).
    Bool/gap ages stay silent — never invent ``sides Δ thin · 1s`` from
    ``True``.
    """
    a = _coerce_ops_age_sec(audit_age)
    f = _coerce_ops_age_sec(file_age)
    if a is None or f is None:
        return ""
    delta = abs(a - f)
    hours = delta / 3600.0
    if hours >= float(OPS_OUTCOME_AGING_HOURS):
        lean = "wide"
    elif hours < float(OPS_OUTCOME_FRESH_HOURS):
        lean = "thin"
    else:
        return ""
    return f"sides Δ {lean} · {_ops_age_short(delta)}"


def _ops_vs_file_clash_sides_share_pcts(
    audit_age: object, file_age: object
) -> tuple[int, int] | None:
    """``(audit_pct, file_pct)`` of auditAge+fileAge; ``None`` when empty.

    Bool/gap ages → ``None`` — never invent ``50%/50%`` from ``True``/``False``.
    """
    a = _coerce_ops_age_sec(audit_age)
    f = _coerce_ops_age_sec(file_age)
    if a is None or f is None:
        return None
    total = a + f
    if total <= 0.0:
        return None
    audit_pct = int(round(100.0 * a / total))
    if audit_pct < 0:
        audit_pct = 0
    if audit_pct > 100:
        audit_pct = 100
    return audit_pct, 100 - audit_pct


# Share Δ lean floors (pp): wide ≥20 · thin <10 · mid silent — Window A /
# soft-allow / config precedence share Δ parity after ownership %.
_OPS_VS_FILE_SHARE_DELTA_WIDE_PP = 20
_OPS_VS_FILE_SHARE_DELTA_THIN_PP = 10


def _ops_vs_file_clash_sides_share(audit_age: object, file_age: object) -> str:
    """``audit N% · file M%`` ownership of auditAge+fileAge; else ``\"\"``.

    Absolute wall ages and additive Δ ≠ who owns the age pair — a thin Δ on
    nearly equal clocks can still be ~50/50, while a wide Δ is usually
    one-sided (portfolio AI count≠share + xang1234 gap-dir sides share after
    sides / sides Δ). Near-zero total stays empty (fail-open).
    """
    pcts = _ops_vs_file_clash_sides_share_pcts(audit_age, file_age)
    if pcts is None:
        return ""
    audit_pct, file_pct = pcts
    return f"audit {audit_pct}% · file {file_pct}%"


def _ops_vs_file_clash_sides_share_delta(
    audit_age: object, file_age: object
) -> str:
    """``sides share Δ wide|thin · ±Npp`` when |audit%−file%| is extreme.

    Share names both %; Δ is the pp spread so near-even ownership stays quiet
    while a lopsided pair speaks (portfolio AI + xang1234 gap-dir sides share
    Δ after share). Wide |Δ| ≥20pp · thin <10pp · mid silent.
    """
    pcts = _ops_vs_file_clash_sides_share_pcts(audit_age, file_age)
    if pcts is None:
        return ""
    audit_pct, file_pct = pcts
    delta_pp = audit_pct - file_pct
    abs_pp = abs(delta_pp)
    if abs_pp >= _OPS_VS_FILE_SHARE_DELTA_WIDE_PP:
        lean = "wide"
    elif abs_pp < _OPS_VS_FILE_SHARE_DELTA_THIN_PP:
        lean = "thin"
    else:
        return ""
    sign = "+" if delta_pp > 0 else ""
    return f"sides share Δ {lean} · {sign}{delta_pp}pp"


def _ops_vs_file_age_delta_lean(audit_age: object, file_age: object) -> str:
    """``wide`` / ``thin`` / ``mid`` for |auditAge−fileAge| (sides Δ floors).

    Bool/gap ages → ``mid`` (silent) — never invent ``thin`` from ``True``.
    """
    a = _coerce_ops_age_sec(audit_age)
    f = _coerce_ops_age_sec(file_age)
    if a is None or f is None:
        return "mid"
    hours = abs(a - f) / 3600.0
    if hours >= float(OPS_OUTCOME_AGING_HOURS):
        return "wide"
    if hours < float(OPS_OUTCOME_FRESH_HOURS):
        return "thin"
    return "mid"


def _ops_vs_file_share_delta_lean(audit_age: object, file_age: object) -> str:
    """``wide`` / ``thin`` / ``mid`` for |audit%−file%| (share Δ floors)."""
    pcts = _ops_vs_file_clash_sides_share_pcts(audit_age, file_age)
    if pcts is None:
        return "mid"
    abs_pp = abs(pcts[0] - pcts[1])
    if abs_pp >= _OPS_VS_FILE_SHARE_DELTA_WIDE_PP:
        return "wide"
    if abs_pp < _OPS_VS_FILE_SHARE_DELTA_THIN_PP:
        return "thin"
    return "mid"


def _ops_vs_file_clash_sides_share_vs_delta(
    audit_age: object, file_age: object
) -> str:
    """Age-Δ lean vs ownership-Δ lean after sides share / share Δ.

    ``sides share vs Δ align · wide|thin`` when both leanish match;
    ``sides share vs Δ clash · × mid|thin|wide · % mid|thin|wide`` when
    exactly one lean spoke (the other mid). Both mid / both spoke with
    different leans stay silent — age gap lean ≠ ownership lean was hidden
    by share Δ alone (portfolio AI + xang1234 + config-precedence share vs Δ
    after sides share Δ).
    """
    age = _ops_vs_file_age_delta_lean(audit_age, file_age)
    share = _ops_vs_file_share_delta_lean(audit_age, file_age)
    if age == "mid" and share == "mid":
        return ""
    if age == share:
        return f"sides share vs Δ align · {age}"
    if age == "mid" or share == "mid":
        return f"sides share vs Δ clash · × {age} · % {share}"
    return ""


def _ops_vs_file_clash_sides(
    row: dict[str, Any],
    *,
    config_mtime: datetime,
    now: datetime | None = None,
) -> str:
    """``sides · 3h · 8d`` (+ optional Δ + ownership % + share Δ + share vs Δ).

    Unparseable / future clocks stay empty (fail-open). Mid age-|Δ| stays on
    sides + share (no age-Δ label). Mid share-|Δ| stays on share (no share-Δ).
    Share vs Δ still speaks when exactly one lean is mid.
    """
    stamp = _parse_ops_at(row.get("at"))
    if stamp is None:
        return ""
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    clock = clock.astimezone(timezone.utc)
    mtime = config_mtime
    if mtime.tzinfo is None:
        mtime = mtime.replace(tzinfo=timezone.utc)
    else:
        mtime = mtime.astimezone(timezone.utc)
    audit_age = (clock - stamp).total_seconds()
    file_age = (clock - mtime).total_seconds()
    if audit_age < 0 or file_age < 0:
        return ""
    bit = f"sides · {_ops_age_short(audit_age)} · {_ops_age_short(file_age)}"
    delta_bit = _ops_vs_file_clash_sides_delta(audit_age, file_age)
    if delta_bit:
        bit = f"{bit} · {delta_bit}"
    share_bit = _ops_vs_file_clash_sides_share(audit_age, file_age)
    if not share_bit:
        return bit
    bit = f"{bit} · {share_bit}"
    share_delta = _ops_vs_file_clash_sides_share_delta(audit_age, file_age)
    if share_delta:
        bit = f"{bit} · {share_delta}"
    vs_delta = _ops_vs_file_clash_sides_share_vs_delta(audit_age, file_age)
    if vs_delta:
        return f"{bit} · {vs_delta}"
    return bit


def ops_outcome_vs_file_clash(
    row: dict[str, Any] | None,
    *,
    config_mtime: datetime | None = None,
    now: datetime | None = None,
) -> str:
    """``clash · audit fresh · file stale · … · sides share Δ wide · -96pp · sides share vs Δ align · wide``.

    Missing clocks / hanging ``requested`` stay silent (pending already has
    refuse-window + ``no outcome``). Same band speaks ``agree`` — silent
    match hid that stamp and mtime still line up (portfolio AI speak-both-
    sides after clash-only). Disagree names **both** clocks
    ``clash · audit … · file …`` — file-only hid which audit band disagreed
    once the age clip dropped (FinRobot/xang1234 soft↔cash / LAYA↔cash
    dual-clock clash after outcome age). Dual clocks alone still hid
    direction: ``audit newer`` (file lag) vs ``file newer`` (possible
    hand-edit after last audited Save) — gap-dir / portfolio AI after
    dual-clock clash. Newer alone still hid span: ``wide`` when bands skip
    a step (fresh↔stale); ``thin`` when adjacent (fresh↔aging /
    aging↔stale) — wide-only hid that mild drift was intentional
    (xang1234 severity + portfolio AI speak-both-sides after gap-dir).
    Span alone still hid wall ages: thin/wide is band distance, not how far
    the clocks sit — append ``sides · auditAge · fileAge`` when both parse
    (FinRobot/xang1234 gap-dir sides + portfolio AI speak-both-sides after
    span). Sides alone still hid additive spread: append
    ``sides Δ wide|thin · Nd`` when |age gap| is extreme (wide ≥7d · thin
    <24h · mid silent) so a huge band jump on close ages (or a thin band
    span on nearly equal clocks) does not look like a huge clock gap
    (FinRobot/xang1234 gap-dir sides Δ after sides). Sides / Δ alone still
    hid ownership: append ``audit N% · file M%`` of the age pair so a thin
    Δ on near-equal clocks stays ~50/50 while a wide Δ reads one-sided
    (portfolio AI count≠share + xang1234 gap-dir sides share after sides Δ).
    Share alone still hid the pp spread: append
    ``sides share Δ wide|thin · ±Npp`` when |audit%−file%| is extreme
    (wide ≥20pp · thin <10pp · mid silent) so near-even ownership stays
    quiet while a lopsided pair speaks (portfolio AI + xang1234 gap-dir
    sides share Δ after share). Share Δ alone still hid age-gap lean vs
    ownership lean: append ``sides share vs Δ align · wide|thin`` when both
    match, or ``sides share vs Δ clash · × mid|… · % …`` when exactly one
    lean spoke (both mid / crossed leans silent) — portfolio AI + xang1234
    + config-precedence share vs Δ after sides share Δ.
    """
    if not isinstance(row, dict):
        return ""
    outcome = str(row.get("outcome") or "").strip()
    if outcome in ("", "requested"):
        return ""
    audit_band = ops_outcome_age_band(row, now=now)
    file_band = ops_file_freshness_band(config_mtime, now=now)
    if not audit_band or not file_band:
        return ""
    if audit_band == file_band:
        return f"agree · file {file_band}"
    a_rank = _OPS_BAND_AGE_RANK.get(audit_band)
    f_rank = _OPS_BAND_AGE_RANK.get(file_band)
    if a_rank is None or f_rank is None:
        return f"clash · audit {audit_band} · file {file_band}"
    newer = "audit newer" if a_rank < f_rank else "file newer"
    bit = f"clash · audit {audit_band} · file {file_band} · {newer}"
    span = abs(a_rank - f_rank)
    if span >= 2:
        bit = f"{bit} · wide"
    elif span == 1:
        bit = f"{bit} · thin"
    if config_mtime is not None:
        sides = _ops_vs_file_clash_sides(
            row, config_mtime=config_mtime, now=now
        )
        if sides:
            return f"{bit} · {sides}"
    return bit


def ops_outcome_vs_file_warn(bit: str) -> bool:
    """True when audit vs file relation is adverse (clash, or agree on stale).

    Fresh/aging agree stays calm; ``agree · file stale`` warns — dual-stale
    confirm ≠ quiet (portfolio AI after silent stale agree hid that both
    clocks are old). Clash bits may append ``audit newer`` / ``file newer``,
    ``wide`` / ``thin`` span, ``sides · … · …`` wall ages,
    ``sides Δ wide|thin · …`` age spread, ``audit N% · file M%`` ownership
    of the age pair, ``sides share Δ wide|thin · ±Npp`` pp spread, and
    ``sides share vs Δ align|clash · …`` when age-Δ lean vs ownership lean
    agree or exactly one spoke.
    """
    if not bit:
        return False
    if bit.startswith("clash · audit"):
        return True
    return bit == "agree · file stale"

def ops_outcome_age_line(
    row: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    fresh_hours: float = OPS_OUTCOME_FRESH_HOURS,
    aging_hours: float = OPS_OUTCOME_AGING_HOURS,
) -> str:
    """Compact ``3h fresh`` / ``2d aging`` / ``10d stale`` for an audit stamp.

    Bare ISO hid whether the last Save was recent (RyanJHamby/xang1234
    fresh|aging|stale + Ops saved-row age parity). Unparseable stays empty
    so the glance can still show the raw stamp.
    """
    if not isinstance(row, dict):
        return ""
    stamp = _parse_ops_at(row.get("at"))
    if stamp is None:
        return ""
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    age_sec = (clock.astimezone(timezone.utc) - stamp).total_seconds()
    if age_sec < 0:
        return ""
    band = ops_outcome_age_band(
        row, now=clock, fresh_hours=fresh_hours, aging_hours=aging_hours
    )
    if not band:
        return ""
    return f"{_ops_age_short(age_sec)} {band}"


def format_last_ops_action_bit(
    row: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    refuse_seconds: int = OPS_PENDING_REFUSE_SECONDS,
    config_mtime: datetime | None = None,
) -> str:
    """Compact Ops honesty line: ``last config · accepted · 3h fresh``.

    A hanging ``requested`` row (no accepted/error yet) speaks ``pending`` when
    still inside the refuse window, or ``stale pending`` when aged out — so a
    crash leftover is not read as a live in-flight Save (xang1234 #613/#628
    outcome pairing + RyanJHamby/xang1234 fresh|stale age triad).

    When the Ops file is newer than that hanging request, also speak
    ``no outcome`` (xang1234 #630 no-worker-for-queue adapted) — the save
    likely landed without an accepted stamp, so waiting forever is wrong.

    A ``skipped`` row speaks ``skipped · no-op`` (or another compact reason)
    when the refuse recorded why — bare ``skipped`` hid intentional no-op
    vs other preflight (xang1234 #599/#623 skip-says-why).

    An ``error`` row speaks ``error · write-fail`` (or another compact reason)
    when recorded — bare ``error`` hid why Save failed after reload
    (xang1234 #621 show jobs request failures adapted).

    An ``accepted`` / hanging ``requested`` row with ``detail.changed`` speaks
    compact ``Δ AI · hold`` after the outcome (xang1234 #636 explain what a
    Run affects — adapted to Ops Save knob impact; bare accepted hid which
    knobs moved). When ``detail.open_cash`` names live US/Xetra sleeves,
    also speak ``mid session · US open · half cash · vs 1 closed · 50%`` after Δ
    (xang1234 #636 when-to-run — hot Save during cash RTH ≠ a quiet overnight
    tweak; half/all cash ownership + vs closed after venue names).

    Parseable stamps speak compact relative age + freshness band instead of
    raw ISO (RyanJHamby/xang1234 + Ops saved-row age parity — bare ``…Z``
    hid whether the last Save was recent). Unparseable stamps keep the raw
    ``at`` text (fail-open).

    When a terminal outcome age band is known beside Ops file freshness, also
    speak ``agree · file fresh`` (same band) or
    ``clash · audit fresh · file stale · audit newer · wide · sides · 3h · 8d``
    (disagree: both clocks + which is newer + ``wide`` skip / ``thin``
    adjacent + both wall ages) — silent match hid confirm; stamp ≠ mtime can
    hide a hand-edit or band-boundary drift; file-only clash hid the audit
    side once age clipped; dual clocks alone hid file lag vs hand-edit;
    newer + wide-only hid that adjacent was mild; span alone hid how far the
    clocks sit in wall time (FinRobot/xang1234 dual-clock + gap-dir sides +
    severity + portfolio AI speak-both-sides after outcome age). Agree on
    stale warns (dual-stale ≠ quiet confirm).
    """
    if not isinstance(row, dict):
        return ""
    kind = str(row.get("kind") or "").strip() or "?"
    raw_outcome = str(row.get("outcome") or "").strip() or "?"
    outcome = raw_outcome
    if outcome == "requested":
        band = ops_pending_freshness_band(
            row, now=now, refuse_seconds=refuse_seconds
        )
        outcome = "stale pending" if band == "stale" else "pending"
        if ops_pending_no_outcome(row, config_mtime=config_mtime):
            outcome = f"{outcome} · no outcome"
    elif outcome == "skipped":
        why = ops_skip_reason_label(row)
        if why:
            outcome = f"skipped · {why}"
    elif outcome == "error":
        why = ops_error_reason_label(row)
        if why:
            outcome = f"error · {why}"
    impact = ""
    session = ""
    if raw_outcome in {"accepted", "requested"}:
        impact = ops_changed_impact_bit(row)
        session = ops_changed_session_bit(row)
    age = ops_outcome_age_line(row, now=now)
    relation = ""
    if age and raw_outcome != "requested":
        relation = ops_outcome_vs_file_clash(
            row, config_mtime=config_mtime, now=now
        )
    parts = [f"last {kind}", outcome]
    if impact:
        parts.append(impact)
        if session:
            parts.append(session)
    if age:
        parts.append(age)
        if relation:
            parts.append(relation)
        return " · ".join(parts)
    at = str(row.get("at") or "").strip()
    if at:
        parts.append(at)
        return " · ".join(parts)
    return " · ".join(parts)


def record_ops_skipped(
    data_dir: Path | str,
    *,
    kind: str,
    reason: str = "no-op",
    detail: dict[str, Any] | None = None,
) -> bool:
    """Append a single ``skipped`` outcome (no requested/act dance).

    Used when Ops refuses a mutation that would only no-op (xang1234 #623
    refuse-before-queue when the run would only skip). Glance speaks
    ``last … · skipped · no-op`` so friends see the refuse was intentional
    and why (xang1234 #599/#623 skip-says-why).
    """
    kind_s = str(kind or "").strip() or "ops"
    reason_s = str(reason or "").strip() or "no-op"
    return append_ops_action(
        data_dir,
        {
            "id": str(uuid.uuid4()),
            "action_id": str(uuid.uuid4()),
            "at": _now_iso(),
            "kind": kind_s,
            "outcome": "skipped",
            "reason": reason_s,
            "detail": _safe_detail(detail),
        },
    )


def audited_ops_action(
    data_dir: Path | str,
    *,
    kind: str,
    detail: dict[str, Any] | None,
    act: Callable[[], T],
) -> tuple[T | None, dict[str, Any]]:
    """Run ``act`` only after a durable ``requested`` audit row.

    Returns ``(result, meta)``. When blocked (request write failed),
    ``result`` is ``None`` and ``meta["blocked"]`` is True. When ``act``
    raises, an ``error`` outcome is recorded (best effort) and the
    exception is re-raised.
    """
    action_id = str(uuid.uuid4())
    kind_s = str(kind or "").strip() or "ops"
    detail_safe = _safe_detail(detail)
    in_flight = pending_ops_in_flight(data_dir, kind=kind_s)
    if in_flight is not None:
        return None, {
            "blocked": True,
            "action_id": str(in_flight.get("action_id") or ""),
            "outcome": "blocked",
            "reason": "pending_in_flight",
            "pending_at": str(in_flight.get("at") or ""),
        }
    requested = {
        "id": str(uuid.uuid4()),
        "action_id": action_id,
        "at": _now_iso(),
        "kind": kind_s,
        "outcome": "requested",
        "detail": detail_safe,
    }
    if not append_ops_action(data_dir, requested):
        return None, {
            "blocked": True,
            "action_id": action_id,
            "outcome": "blocked",
            "reason": "audit_request_failed",
        }

    try:
        result = act()
    except Exception as exc:
        # xang1234 #621: persist a compact why so glance speaks error · …
        # after reload (toast alone disappears). Message text stays out.
        append_ops_action(
            data_dir,
            {
                "id": str(uuid.uuid4()),
                "action_id": action_id,
                "at": _now_iso(),
                "kind": kind_s,
                "outcome": "error",
                "reason": ops_error_reason_from_exc(exc),
                "detail": detail_safe,
            },
        )
        raise

    accepted = {
        "id": str(uuid.uuid4()),
        "action_id": action_id,
        "at": _now_iso(),
        "kind": kind_s,
        "outcome": "accepted",
        "detail": detail_safe,
    }
    outcome_ok = append_ops_action(data_dir, accepted)
    return result, {
        "blocked": False,
        "action_id": action_id,
        "outcome": "accepted",
        "outcome_recorded": outcome_ok,
    }


def _ops_changed_keys(row: dict[str, Any] | None) -> list[str]:
    """Parse audit ``detail.changed`` knob keys (empty when absent)."""
    if not isinstance(row, dict):
        return []
    detail = row.get("detail")
    if not isinstance(detail, dict):
        return []
    raw = detail.get("changed")
    if not isinstance(raw, list):
        return []
    return [str(k).strip() for k in raw if str(k).strip()]


def ops_changed_impact_bit(row: dict[str, Any] | None) -> str:
    """Compact ``Δ hot · AI · hold`` from audit ``detail.changed`` (#636)."""
    keys = _ops_changed_keys(row)
    if not keys:
        return ""
    from .trader_config import format_config_changed_bit

    return format_config_changed_bit(keys)


def _ops_open_cash(row: dict[str, Any] | None) -> list[str]:
    """Parse audit ``detail.open_cash`` venue labels (empty when absent)."""
    if not isinstance(row, dict):
        return []
    detail = row.get("detail")
    if not isinstance(detail, dict):
        return []
    raw = detail.get("open_cash")
    if not isinstance(raw, list):
        return []
    return [str(v).strip() for v in raw if str(v).strip()]


def ops_changed_session_bit(row: dict[str, Any] | None) -> str:
    """Compact ``mid session · US open · half cash · vs 1 closed`` (#636).

    Only speaks on hot Saves (book/fee/promote) that recorded open cash —
    quiet AI/gates mid-session stay silent (when-to-run is for live risk).
    Half/all cash ownership follows Hours attention share honesty.
    All-cash open speaks ``open vs closed align · hot|thin`` (Hours lean).
    """
    if not ops_changed_impact_warn(row):
        return ""
    from .trader_config import format_config_save_session_bit

    return format_config_save_session_bit(_ops_open_cash(row))


def ops_changed_session_warn(row: dict[str, Any] | None) -> bool:
    """True when hot Save mid-session open vs closed lean is adverse.

    Hours attention_vs_open_warn parity — all cash live + thin closed
    escalates (hot impact already warns; this names the session lean).
    """
    if not ops_changed_impact_warn(row):
        return False
    from .trader_config import config_save_session_vs_closed_warn

    return config_save_session_vs_closed_warn(_ops_open_cash(row))


def ops_changed_impact_warn(row: dict[str, Any] | None) -> bool:
    """True when last accepted/pending Save moved hot book/fee/promote knobs.

    xang1234 #636 advanced Run red — quiet AI-only Δ stays clay flat.
    """
    if not isinstance(row, dict):
        return False
    outcome = str(row.get("outcome") or "").strip()
    if outcome not in {"accepted", "requested"}:
        return False
    from .trader_config import config_changed_impact_warn

    return config_changed_impact_warn(_ops_changed_keys(row))


def ops_save_body_detail(
    body: dict[str, Any] | None,
    keys_n: object = None,
) -> dict[str, Any]:
    """Ops Save request-body key strip for audit detail (not ``_safe_detail``).

    FinRobot + tradermonty #700/#655 + xang1234/portfolio AI: ``True→1`` must
    not invent a one-key Save audit strip via ``sorted(body)[:True]``;
    ``False→0`` must not wipe (``_safe_detail`` changed-items ceiling peer —
    HTTP Save path was still bare ``[:16]`` after Save Δ detail refuse).
    """
    if not isinstance(body, dict):
        return {}
    ceil = _coerce_ops_detail_ceiling(
        OPS_DETAIL_CHANGED_ITEMS_MAX if keys_n is None else keys_n,
        OPS_DETAIL_CHANGED_ITEMS_MAX,
    )
    return {k: body.get(k) for k in sorted(body)[:ceil]}


def _safe_detail(
    detail: dict[str, Any] | None,
    *,
    keys_n: object = OPS_DETAIL_KEYS_MAX,
    changed_n: object = OPS_DETAIL_CHANGED_ITEMS_MAX,
    changed_chars: object = OPS_DETAIL_CHANGED_ITEM_CHARS,
    open_cash_n: object = OPS_DETAIL_OPEN_CASH_ITEMS_MAX,
    open_cash_chars: object = OPS_DETAIL_OPEN_CASH_ITEM_CHARS,
    string_chars: object = OPS_DETAIL_STRING_CHARS,
) -> dict[str, Any]:
    """Keep a small non-secret summary of what Ops asked to change."""
    from .secret_redact import redact_secrets

    if not isinstance(detail, dict):
        return {}
    key_ceil = _coerce_ops_detail_ceiling(keys_n, OPS_DETAIL_KEYS_MAX)
    changed_ceil = _coerce_ops_detail_ceiling(
        changed_n, OPS_DETAIL_CHANGED_ITEMS_MAX
    )
    changed_char_ceil = _coerce_ops_detail_ceiling(
        changed_chars, OPS_DETAIL_CHANGED_ITEM_CHARS
    )
    open_cash_ceil = _coerce_ops_detail_ceiling(
        open_cash_n, OPS_DETAIL_OPEN_CASH_ITEMS_MAX
    )
    open_cash_char_ceil = _coerce_ops_detail_ceiling(
        open_cash_chars, OPS_DETAIL_OPEN_CASH_ITEM_CHARS
    )
    string_ceil = _coerce_ops_detail_ceiling(
        string_chars, OPS_DETAIL_STRING_CHARS
    )
    out: dict[str, Any] = {}
    for key, val in list(detail.items())[:key_ceil]:
        k = str(key)
        kl = k.lower()
        if any(s in kl for s in ("key", "token", "secret", "password")):
            continue
        if k == "changed" and isinstance(val, list):
            # xang1234 #636: persist knob-impact keys for glance Δ speak.
            cleaned = [
                str(item).strip()[:changed_char_ceil]
                for item in val[:changed_ceil]
                if str(item).strip()
            ]
            if cleaned:
                out[k] = cleaned
            continue
        if k == "open_cash" and isinstance(val, list):
            # xang1234 #636 when-to-run: persist live cash sleeves for mid-session.
            cleaned = [
                str(item).strip()[:open_cash_char_ceil]
                for item in val[:open_cash_ceil]
                if str(item).strip()
            ]
            if cleaned:
                out[k] = cleaned
            continue
        if isinstance(val, (bool, int, float)):
            out[k] = val
        elif isinstance(val, str):
            # tradermonty #556: redact encoded key echoes inside benign string fields.
            out[k] = redact_secrets(val)[:string_ceil]
        elif val is None:
            out[k] = None
        else:
            out[k] = type(val).__name__
    return out
