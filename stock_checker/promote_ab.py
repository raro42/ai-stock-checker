"""Promote A/B window honesty (display / docs; not an entry gate).

Protocol: docs/PROMOTE_AB.md and docs/history/promote_ab_2026-08-12.md.
Calm streak unlocks compose default — A/B measures fee-adjusted live edge.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from stock_checker.risk_halts import (
    DEFAULT_ENTRY_CASH_FRAC,
    DEFAULT_MAX_NAME_PCT,
)
from stock_checker.trader_config import DEFAULTS as TRADER_DEFAULTS

# Window A control (promote OFF) — started 2026-08-12 ~15:22 UTC
WINDOW_A_START = date(2026, 8, 12)
WINDOW_A_START_UTC = datetime(2026, 8, 12, 15, 22, tzinfo=timezone.utc)
WINDOW_A_TARGET_TRADING_DAYS = 10
# Protocol records days *and* fills — day count alone is a thin sample (PROMOTE_AB).
WINDOW_A_TARGET_FILLS = 10
# Fee-adjusted edge needs closed rounds. All-buy = open-only; 1–2 sells = thin closes.
# One lucky close after many buys is not a fair control sample (portfolio AI).
WINDOW_A_TARGET_SELLS = 3
# staskh confirm-against-latest-closed → Window A closes must be fresh.
WINDOW_A_MAX_SELL_STALE_DAYS = 5
# RyanJHamby fresh/aging/stale — warn before hard stale (display only).
WINDOW_A_AGING_SELL_DAYS = 3
# Fee-drag severity from fees÷realized (portfolio AI + xang1234 severity bands).
# mild <2× · heavy ≥2× · severe ≥5× · total when realized ≤0 (no multiple).
WINDOW_A_FEE_DRAG_HEAVY_RATIO = 2.0
WINDOW_A_FEE_DRAG_SEVERE_RATIO = 5.0
# Fees ≤ realized severity triad (portfolio AI quiet vs high + xang1234 bands):
# comfortable <0.25 · ok mid · thin ≥0.5 (warn, still ready for B).
WINDOW_A_FEES_COMFORTABLE_RATIO = 0.25
WINDOW_A_FEES_THIN_RATIO = 0.5
# Close win/lose polarity (portfolio AI Book Win·Lose + xang1234 speak-both-sides).
# all_win / mixed / all_loss — all_loss warns; does not block ready for B.
# Close payoff = avg_win ÷ avg_loss (portfolio AI + xang1234 severity).
# Count lean ≠ € lean — many small wins / one large loss is thin payoff.
# strong ≥2× · ok mid · thin <1× (warn only; still ready for B).
WINDOW_A_PAYOFF_STRONG_RATIO = 2.0
WINDOW_A_PAYOFF_THIN_RATIO = 1.0
# Close expectancy €/close = win_rate·avg_win − loss_rate·avg_loss
# (portfolio AI expectancy; payoff is ratio, expectancy is €).
# Positive severity vs avg_loss (xang1234 bands + portfolio AI):
# strong ≥0.5× · ok mid · thin <0.25× (warn only). Negative warns only.
# Still ready for B in all cases.
WINDOW_A_EXPECTANCY_STRONG_RATIO = 0.5
WINDOW_A_EXPECTANCY_THIN_RATIO = 0.25
# Close profit factor = gross wins ÷ gross losses (portfolio AI).
# Distinct from payoff (avg_win ÷ avg_loss): count × size, not avg alone.
# strong ≥2× · ok mid · thin <1× (warn only; still ready for B).
WINDOW_A_PROFIT_FACTOR_STRONG_RATIO = 2.0
WINDOW_A_PROFIT_FACTOR_THIN_RATIO = 1.0
# Close win rate % = wins ÷ (wins+losses) (portfolio AI after polarity).
# Count lean ≠ hit rate — 3W/2L is mostly-wins lean and 60% strong.
# strong ≥60% · ok mid · thin <40% (warn only; still ready for B).
WINDOW_A_WIN_RATE_STRONG_PCT = 60.0
WINDOW_A_WIN_RATE_THIN_PCT = 40.0
# Win rate vs breakeven from payoff (portfolio AI edge + xang1234 severity).
# BE% = 100 / (1 + avg_win/avg_loss). Hit rate alone ≠ edge when payoff ≠ 1.
# above / at (±AT pp) / below (warn only; still ready for B).
WINDOW_A_WR_BE_AT_PP = 2.0
# Edge cushion (WR − BE) severity when above BE (portfolio AI + xang1234).
# above alone ≠ wide edge — thin cushion <THIN pp warns; strong ≥STRONG pp.
# below keeps warn via closes_wr_below_be (still ready for B).
WINDOW_A_WR_EDGE_STRONG_PP = 10.0
WINDOW_A_WR_EDGE_THIN_PP = 5.0
# Full Kelly % of equity = 100·(p − (1−p)/R) from win rate and payoff.
# WR vs BE says if hit rate clears breakeven; Kelly says the size fraction.
# Full Kelly only (not half, not clamped). strong ≥20% · thin <5% · neg ≤0.
# Neg and thin warn only (still ready for B). Not a live sizer.
WINDOW_A_KELLY_STRONG_PCT = 20.0
WINDOW_A_KELLY_THIN_PCT = 5.0
# Half of full Kelly vs the live cash sizer (DEFAULT_ENTRY_CASH_FRAC ~10%).
# Full Kelly is the theoretical max; the desk sizes near 10% of cash.
# match within ±MATCH pp. under = sizer larger than the practical edge
# (warn). over = sizer smaller (ok). Not a live sizer change.
WINDOW_A_HALF_KELLY_MATCH_PP = 5.0
# Half-Kelly vs equal-slot equity share (100 / max_positions ≈20% at 5).
# Cash sizer ≠ equal book weight when the book is full. Same MATCH band.
# under = slot larger than practical edge (warn). Not a live book change.
WINDOW_A_EQUAL_SLOT_PCT = round(
    100.0 / max(1, int(TRADER_DEFAULTS.get("max_positions") or 5)), 1
)
# Half-Kelly vs soft single-name concentration cap (~30% equity).
# Equal slot ≠ the soft max-name ceiling (C-conc / Book Cap). Same MATCH.
# under = cap larger than practical edge (warn). Not a live cap change.
WINDOW_A_CONC_CAP_PCT = round(float(DEFAULT_MAX_NAME_PCT), 1)
# Quarter of full Kelly vs the live cash sizer (~10%).
# Half-Kelly often sits well above the desk cash slice when edge is strong;
# quarter-Kelly is the conservative practical fraction (portfolio AI).
# Same MATCH band. under = sizer larger than ¼ Kelly (warn). Not a live sizer.
WINDOW_A_QUARTER_KELLY_FRAC = 0.25
# Decided closes (wins+losses) before a Kelly fraction is a size sample.
# Close floor is 3 sells. That is not enough to trust f*. thin <10 warns.
# ok speaks when the count is met (xang1234 speak-both-sides). Warn only
# (still ready for B). Not a live sizer. Missing wins/losses → no bit.
WINDOW_A_KELLY_SAMPLE_MIN = 10
# Ending run of losing closes (portfolio AI + tradermonty postmortem).
# Win/lose counts ≠ a current run. quiet is 0 or 1. hot is ≥2 (warn only).
# Still ready for B. Missing loss_streak → no bit. Not a live halt.
WINDOW_A_LOSS_STREAK_HOT = 2
# Fee-adjusted net expectancy €/close = net_after_all_fees ÷ sells
# (portfolio AI after gross expectancy). Gross €/close ≠ fee-adjusted €/close.
# Positive severity reuses EXPECTANCY_* ratios vs avg_loss. Neg + thin warn
# only (still ready for B). Gross+ / net− → closes_net_expectancy_eats_edge.
# Expectancy fee take €/close = gross_expectancy − net_expectancy
# (portfolio AI after net expect). Distinct from fee drag (total fees vs
# realized) and from net expect (€/close). Severity when gross > 0 reuses
# FEES_COMFORTABLE / FEES_THIN ratios (comfortable <0.25 · thin ≥0.5 warn).
# Thin warn only (still ready for B).
# Net vs fee take multiple = net_expectancy ÷ fee_take when both > 0
# (portfolio AI after fee take). Fee take € alone ≠ how many fee-takes of
# edge remain. Reuses PROFIT_FACTOR_* ratios (strong ≥2× · ok mid · thin <1×).
# Thin warn only (still ready for B).
# Fee-adjusted net profit factor = (gross_wins − fees) ÷ gross_losses
# (portfolio AI after gross PF + fee take). Gross PF ≠ fee-adjusted PF.
# Severity reuses PROFIT_FACTOR_* ratios. Gross PF ≥1× / net wins ≤0 →
# closes_net_profit_factor_eats_edge. Thin / eats-edge warn only (still
# ready for B).
WINDOW_B_START: date | None = None  # Window B (promote ON) — not started
WINDOW_B_START_UTC: datetime | None = None
# Protocol table in docs/PROMOTE_AB.md — restore before starting B
PROTOCOL_MAX_POSITIONS = 5
PROTOCOL_MIN_HOLD_HOURS = 24.0
PROTOCOL_FEE_PRESET = "revolut_standard"
# Soft entry gates stay ON for A and B (only promote flips). Not new gates.
PROTOCOL_REGIME_GATE = True
PROTOCOL_RS_GATE = True
PROTOCOL_BREADTH_GATE = True
# Window A/B knobs table: AI validate (not off/full). Model may still be
# gemma4 or another instruct — mode drift changes churn more than the tag.
PROTOCOL_AI_MODE = "validate"
# FinRobot / TradingAgents multi-role stays ON for A and B (bull·bear·risk).
PROTOCOL_AI_MULTI_ROLE = True
# Anti-churn floors (AUTOPILOT / loop-cadence glance). Faster loops skew A/B.
PROTOCOL_SCAN_INTERVAL_MIN = 15
PROTOCOL_TRADE_INTERVAL_MIN = 5


def window_b_readiness(
    *,
    max_positions: int | None = None,
    open_positions: int | None = None,
    min_hold_hours: float | None = None,
    fee_preset: str | None = None,
    regime_gate: bool | None = None,
    rs_gate: bool | None = None,
    breadth_gate: bool | None = None,
    ai_mode: str | None = None,
    ai_multi_role: bool | None = None,
    scan_interval_min: int | None = None,
    trade_interval_min: int | None = None,
    protocol_max: int = PROTOCOL_MAX_POSITIONS,
    protocol_min_hold_hours: float = PROTOCOL_MIN_HOLD_HOURS,
    protocol_fee_preset: str = PROTOCOL_FEE_PRESET,
    protocol_regime_gate: bool = PROTOCOL_REGIME_GATE,
    protocol_rs_gate: bool = PROTOCOL_RS_GATE,
    protocol_breadth_gate: bool = PROTOCOL_BREADTH_GATE,
    protocol_ai_mode: str = PROTOCOL_AI_MODE,
    protocol_ai_multi_role: bool = PROTOCOL_AI_MULTI_ROLE,
    protocol_scan_interval_min: int = PROTOCOL_SCAN_INTERVAL_MIN,
    protocol_trade_interval_min: int = PROTOCOL_TRADE_INTERVAL_MIN,
) -> dict[str, Any]:
    """Why Window B should wait (display / ops honesty; not a gate).

    Protocol wants the same book caps, min hold, fee preset, soft entry
    gates, AI mode, multi-role, and loop cadence floors for A and B
    (default max 5 / 24h / revolut_standard / regime·RS·breadth on /
    AI validate / multi-role on / scan ≥15m / trade ≥5m).
    Only promote should flip between windows. Live Ops drift pauses a fair
    A/B compare — surface it on the desk instead of saying "ready for B".
    FinRobot / TradingAgents AI honesty + RyanJHamby schedule floors +
    portfolio AI readiness.
    """
    cap = max(1, int(protocol_max))
    hold_need = float(protocol_min_hold_hours)
    fee_need = str(protocol_fee_preset or PROTOCOL_FEE_PRESET).strip().lower()
    ai_need = (
        str(protocol_ai_mode or PROTOCOL_AI_MODE).strip().lower() or PROTOCOL_AI_MODE
    )
    scan_need = max(1, int(protocol_scan_interval_min))
    trade_need = max(1, int(protocol_trade_interval_min))
    blockers: list[str] = []
    if max_positions is not None:
        slots = int(max_positions)
        if slots != cap:
            blockers.append(f"max pos {slots}≠{cap}")
    if open_positions is not None:
        n = int(open_positions)
        if n > cap:
            blockers.append(f"{n} open >{cap}")
    if min_hold_hours is not None:
        hold_h = float(min_hold_hours)
        if abs(hold_h - hold_need) > 0.05:
            blockers.append(f"hold {hold_h:g}h≠{hold_need:g}h")
    if fee_preset is not None:
        preset = str(fee_preset).strip().lower()
        if preset and preset != fee_need:
            short = fee_need.replace("revolut_", "")
            blockers.append(f"fee {preset}≠{short}")
    if regime_gate is not None and bool(regime_gate) != bool(protocol_regime_gate):
        want = "on" if protocol_regime_gate else "off"
        blockers.append(f"regime {'on' if regime_gate else 'off'}≠{want}")
    if rs_gate is not None and bool(rs_gate) != bool(protocol_rs_gate):
        want = "on" if protocol_rs_gate else "off"
        blockers.append(f"RS {'on' if rs_gate else 'off'}≠{want}")
    if breadth_gate is not None and bool(breadth_gate) != bool(protocol_breadth_gate):
        want = "on" if protocol_breadth_gate else "off"
        blockers.append(f"breadth {'on' if breadth_gate else 'off'}≠{want}")
    if ai_mode is not None:
        mode = str(ai_mode).strip().lower()
        if mode and mode != ai_need:
            blockers.append(f"AI {mode}≠{ai_need}")
    if ai_multi_role is not None and bool(ai_multi_role) != bool(
        protocol_ai_multi_role
    ):
        want = "on" if protocol_ai_multi_role else "off"
        blockers.append(f"multi-role {'on' if ai_multi_role else 'off'}≠{want}")
    if scan_interval_min is not None:
        scan_m = int(scan_interval_min)
        if scan_m < scan_need:
            blockers.append(f"scan {scan_m}m<{scan_need}m")
    if trade_interval_min is not None:
        trade_m = int(trade_interval_min)
        if trade_m < trade_need:
            blockers.append(f"trade {trade_m}m<{trade_need}m")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "protocol_max_positions": cap,
        "protocol_min_hold_hours": hold_need,
        "protocol_fee_preset": fee_need,
        "protocol_regime_gate": bool(protocol_regime_gate),
        "protocol_rs_gate": bool(protocol_rs_gate),
        "protocol_breadth_gate": bool(protocol_breadth_gate),
        "protocol_ai_mode": ai_need,
        "protocol_ai_multi_role": bool(protocol_ai_multi_role),
        "protocol_scan_interval_min": scan_need,
        "protocol_trade_interval_min": trade_need,
    }


def format_window_b_block_bit(blockers: list[str] | None) -> str:
    """Short Window B block bit for promote A/B glance."""
    if not blockers:
        return ""
    clean = [str(b).strip() for b in blockers if str(b).strip()]
    if not clean:
        return ""
    return "B blocked · " + " · ".join(clean)


def _weekday_days_since(earlier: date, later: date) -> int:
    """Weekday trading days strictly after ``earlier`` through ``later``."""
    if later <= earlier:
        return 0
    return weekday_trading_days(earlier + timedelta(days=1), later)


def window_a_sample_readiness(
    stats: dict[str, Any] | None,
    *,
    target_fills: int = WINDOW_A_TARGET_FILLS,
    target_sells: int = WINDOW_A_TARGET_SELLS,
    max_sell_stale_days: int = WINDOW_A_MAX_SELL_STALE_DAYS,
    aging_sell_days: int = WINDOW_A_AGING_SELL_DAYS,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Whether Window A has enough fills to start B (display / ops honesty).

    PROMOTE_AB records trading days *and* fills. Hitting the day target with a
    thin ledger is not a fair control sample — portfolio AI sample-size
    honesty before ``ready for B``. When ``buys``/``sells`` are present, an
    all-buy ledger is ``open-only`` (no closed rounds → fee-adjusted edge is
    just −fees). Sparse closes (``0 < sells < target_sells``) are ``thin
    closes`` — one lucky SELL after many buys is not a fair control (staskh
    confirm-against-latest-closed + portfolio AI close floor). When a last
    SELL timestamp is present and the close floor is met, closes use
    RyanJHamby fresh/aging/stale vs ``aging_sell_days`` / ``max_sell_stale_days``
    weekday days. Fresh and aging speak on the glance; stale blocks ready.
    Missing stats → unknown (keep summarize). Missing side keys / last_sell →
    fail-open on those checks. When closed rounds exist and in-window fees
    exceed realized sell P&L, ``fee_drag`` warns (portfolio AI fee-burn
    adapted) — bit prefers fee-adjusted ``net −€N`` when known so friends
    see the € damage without parsing the fees strip; appends ``fees N×``
    (fees÷realized) when realized > 0; labels severity ``mild`` / ``heavy`` /
    ``severe`` / ``total`` from the multiple (xang1234 severity bands +
    portfolio AI); does not block ready. When closes exist and fees ≤
    realized, ``fees_ok`` speaks the quiet complement
    (``A fees ok · net +€N · fees N×``) — portfolio AI fee-burn quiet vs
    high + xang1234 speak-both-sides (like fresh completes freshness).
    Fees-ok severity triad (xang1234 speak-both-sides):
    ``A fees comfortable`` when fees÷realized < ``WINDOW_A_FEES_COMFORTABLE_RATIO``;
    ``A fees ok`` in the mid band; ``A fees thin`` when ≥ ``WINDOW_A_FEES_THIN_RATIO``
    (still ≤1×; warn tone, does not block ready) — thin edge before fee drag.
    When closed rounds exist and ``wins``/``losses`` keys are present, speak
    close polarity ``A all-win|mixed|all-loss · Nw/Nl`` (portfolio AI
    Win·Lose + xang1234 speak-both-sides). Mixed closes add a lean triad
    (xang1234 severity + portfolio AI Win·Lose): ``mostly wins`` when
    wins > losses, ``even`` when equal, ``mostly losses`` when losses >
    wins (``closes_polarity_lean`` = win_lean / even / loss_lean).
    ``all_loss`` and mixed ``loss_lean`` warn only — do not block ready
    (one red or loss-lean book is still a valid control sample). Missing
    wins/losses → fail-open (no bit). When ``avg_win`` and ``avg_loss`` are
    both > 0, speak close payoff ``A payoff [strong|thin] · N×`` (avg win ÷
    avg loss) — portfolio AI + xang1234 severity triad
    (strong ≥``WINDOW_A_PAYOFF_STRONG_RATIO`` · ok mid · thin
    <``WINDOW_A_PAYOFF_THIN_RATIO``). Count lean ≠ € lean; thin warns only
    (still ready for B). When wins/losses + avgs allow, speak close
    expectancy ``A expectancy [strong|thin] · +€N`` / ``−€N``
    (win_rate·avg_win − loss_rate·avg_loss) — portfolio AI €/close after
    payoff ratio; all-win uses avg_win; all-loss uses −avg_loss. Positive
    expectancy adds a severity triad vs avg_loss (xang1234 + portfolio AI):
    strong ≥``WINDOW_A_EXPECTANCY_STRONG_RATIO`` · ok mid · thin
    <``WINDOW_A_EXPECTANCY_THIN_RATIO`` (tiny € edge vs typical loss).
    Negative and thin warn only (still ready for B). Missing avg_loss →
    signed € only (fail-open severity). Missing avgs → fail-open. When
    both sides have positive gross €, speak close profit factor
    ``A PF [strong|thin] · N×`` (gross wins ÷ gross losses; PF = profit
    factor) — portfolio AI after expectancy; payoff is avg ratio, PF is
    total € ratio (count × size). strong ≥``WINDOW_A_PROFIT_FACTOR_STRONG_RATIO``
    · ok mid · thin <``WINDOW_A_PROFIT_FACTOR_THIN_RATIO`` (warn only;
    still ready for B). Missing grosses → fail-open. When wins+losses > 0,
    speak close win rate ``A win rate [strong|thin] · N%``
    (wins ÷ (wins+losses); portfolio AI hit rate after polarity + xang1234
    severity). Count lean ≠ hit rate. strong ≥``WINDOW_A_WIN_RATE_STRONG_PCT``
    · ok mid · thin <``WINDOW_A_WIN_RATE_THIN_PCT`` (warn only; still ready
    for B). Missing polarity → fail-open. When win rate and payoff are both
    known, speak WR vs breakeven ``A WR [above|at|below] BE [strong|thin] · ±Npp``
    (BE% = 100/(1+payoff); portfolio AI edge after WR+payoff + xang1234
    severity). Hit rate alone ≠ edge when payoff ≠ 1. ``at`` within
    ±``WINDOW_A_WR_BE_AT_PP`` pp. Above-BE cushion severity:
    strong ≥``WINDOW_A_WR_EDGE_STRONG_PP`` · ok mid · thin
    <``WINDOW_A_WR_EDGE_THIN_PP`` (warn). ``below`` and thin cushion warn
    only (still ready for B). Missing payoff or WR → fail-open. When win
    rate and payoff are both known, speak full Kelly
    ``A Kelly [strong|thin|neg] · N%`` (f* = p − (1−p)/R) — portfolio AI
    size fraction after WR vs BE. WR vs BE ≠ the equity fraction the edge
    supports. strong ≥``WINDOW_A_KELLY_STRONG_PCT`` · ok mid · thin
    <``WINDOW_A_KELLY_THIN_PCT`` · neg ≤0. Neg and thin warn only (still
    ready for B). The Kelly bit is full Kelly, not half and not the live
    sizer. When Kelly is known, speak half-Kelly vs that sizer
    ``A half-Kelly vs sizer [under|match|over] · N% vs 10%`` (half of f*
    vs ``DEFAULT_ENTRY_CASH_FRAC``). Full Kelly ≠ the cash slice the desk
    uses. ``under`` when half-Kelly is more than
    ``WINDOW_A_HALF_KELLY_MATCH_PP`` below the sizer (warn only; still
    ready for B). When Kelly is known, also speak half-Kelly vs equal
    slot ``A half-Kelly vs slot [under|match|over] · N% vs 20%``
    (``WINDOW_A_EQUAL_SLOT_PCT`` = 100/max_positions). Cash sizer ≠ equal
    book weight when the book is full. ``under`` when half-Kelly is more
    than ``WINDOW_A_HALF_KELLY_MATCH_PP`` below the slot (warn only; still
    ready for B). When Kelly is known, also speak half-Kelly vs soft
    concentration cap ``A half-Kelly vs cap [under|match|over] · N% vs 30%``
    (``WINDOW_A_CONC_CAP_PCT`` = ``DEFAULT_MAX_NAME_PCT``). Equal slot ≠
    the single-name ceiling. ``under`` when half-Kelly is more than
    ``WINDOW_A_HALF_KELLY_MATCH_PP`` below the cap (warn only; still
    ready for B). When Kelly is known, also speak quarter-Kelly vs sizer
    ``A quarter-Kelly vs sizer [under|match|over] · N% vs 10%``
    (``WINDOW_A_QUARTER_KELLY_FRAC`` of f*). Half-Kelly often sits well
    above the cash slice when edge is strong; quarter is the conservative
    practical fraction. ``under`` when quarter-Kelly is more than
    ``WINDOW_A_HALF_KELLY_MATCH_PP`` below the sizer (warn only; still
    ready for B). When Kelly is known, also speak quarter-Kelly vs equal
    slot ``A quarter-Kelly vs slot [under|match|over] · N% vs 20%``
    (``WINDOW_A_EQUAL_SLOT_PCT``). Cash sizer ≠ equal book weight; quarter
    vs sizer ≠ quarter vs slot. ``under`` when quarter-Kelly is more than
    ``WINDOW_A_HALF_KELLY_MATCH_PP`` below the slot (warn only; still
    ready for B). When Kelly is known, also speak quarter-Kelly vs soft
    concentration cap ``A quarter-Kelly vs cap [under|match|over] · N% vs 30%``
    (``WINDOW_A_CONC_CAP_PCT``). Equal slot ≠ the single-name ceiling;
    quarter vs slot ≠ quarter vs cap. Quarter of full Kelly is at most 25%,
    so vs 30% it is usually ``under``. ``under`` when quarter-Kelly is more
    than ``WINDOW_A_HALF_KELLY_MATCH_PP`` below the cap (warn only; still
    ready for B). When Kelly is known, also speak one practical pick
    ``A practical Kelly [half|quarter|sizer|none]`` — the largest
    conventional fraction that fits the cash sizer (portfolio AI after
    the half/quarter comparisons + tradermonty sizer). ``half · cut`` when
    half is under the sizer. ``half`` when half matches. ``quarter`` when
    half is over but quarter fits. ``sizer`` when even quarter is over
    (desk already tighter than ¼ Kelly). ``none`` when f* ≤ 0. Cut and
    none warn only (still ready for B). Missing WR or payoff → fail-open. When
    ``net_after_all_fees`` is known and sells > 0, speak fee-adjusted net
    expectancy ``A net expect [strong|thin] · +€N`` / ``−€N``
    (net ÷ sells) — portfolio AI after gross expectancy; gross €/close ≠
    fee-adjusted €/close. Positive severity reuses
    ``WINDOW_A_EXPECTANCY_*_RATIO`` vs avg_loss. When gross expectancy > 0
    and net expect < 0, ``closes_net_expectancy_eats_edge`` warns (fees eat
    gross edge). Neg / thin / eats-edge warn only (still ready for B).
    Missing net → fail-open. When gross and net expectancy are both known,
    speak expectancy fee take ``A fee take [comfortable|thin] · €N/close``
    (gross − net) — portfolio AI after net expect; distinct from fee drag
    (total fees vs realized) and from net expect (€/close). Severity when
    gross > 0 reuses ``WINDOW_A_FEES_COMFORTABLE_RATIO`` /
    ``WINDOW_A_FEES_THIN_RATIO``. Thin warn only (still ready for B).
    When net expect and fee take are both > 0, speak net/fee multiple
    ``A net/fee [strong|thin] · N×`` (net ÷ fee take) — portfolio AI after
    fee take; fee take € alone ≠ remaining edge multiples. Severity reuses
    ``WINDOW_A_PROFIT_FACTOR_*_RATIO``. Thin warn only (still ready for B).
    When gross wins/losses and fees are known, speak fee-adjusted net
    profit factor ``A net PF [strong|thin] · N×``
    ((gross_wins − fees) ÷ gross_losses) — portfolio AI after gross PF +
    fee take; gross PF ≠ fee-adjusted PF. Severity reuses
    ``WINDOW_A_PROFIT_FACTOR_*``. When gross PF ≥1× and net wins ≤0,
    ``closes_net_profit_factor_eats_edge`` warns (fees eat PF). Thin /
    eats-edge warn only (still ready for B). Missing fees/grosses →
    fail-open. Not a gate; does not flip compose promote.
    """
    need = max(1, int(target_fills))
    sell_need = max(1, int(target_sells))
    stale_need = max(1, int(max_sell_stale_days))
    aging_need = max(0, min(int(aging_sell_days), stale_need))
    empty = {
        "ready": False,
        "known": False,
        "fills": 0,
        "target_fills": need,
        "buys": 0,
        "sells": 0,
        "sides_known": False,
        "target_sells": sell_need,
        "thin": False,
        "thin_bit": "",
        "open_only": False,
        "open_only_bit": "",
        "thin_closes": False,
        "thin_closes_bit": "",
        "stale_closes": False,
        "stale_closes_bit": "",
        "aging_closes": False,
        "aging_closes_bit": "",
        "fresh_closes": False,
        "fresh_closes_bit": "",
        "closes_freshness": "",
        "fee_drag": False,
        "fee_drag_bit": "",
        "fee_drag_net": None,
        "fee_drag_ratio": None,
        "fee_drag_severity": "",
        "fees_ok": False,
        "fees_ok_bit": "",
        "fees_ok_net": None,
        "fees_ok_ratio": None,
        "fees_ok_severity": "",
        "closes_wins": 0,
        "closes_losses": 0,
        "closes_polarity_known": False,
        "closes_polarity": "",
        "closes_polarity_bit": "",
        "closes_polarity_lean": "",
        "closes_all_loss": False,
        "closes_loss_lean": False,
        "closes_avg_win": None,
        "closes_avg_loss": None,
        "closes_payoff_ratio": None,
        "closes_payoff_severity": "",
        "closes_payoff_bit": "",
        "closes_payoff_thin": False,
        "closes_expectancy": None,
        "closes_expectancy_bit": "",
        "closes_expectancy_neg": False,
        "closes_expectancy_severity": "",
        "closes_expectancy_thin": False,
        "closes_expectancy_ratio": None,
        "closes_profit_factor": None,
        "closes_profit_factor_severity": "",
        "closes_profit_factor_bit": "",
        "closes_profit_factor_thin": False,
        "closes_gross_wins": None,
        "closes_gross_losses": None,
        "closes_win_rate_pct": None,
        "closes_win_rate_severity": "",
        "closes_win_rate_bit": "",
        "closes_win_rate_thin": False,
        "closes_breakeven_wr_pct": None,
        "closes_wr_vs_be": "",
        "closes_wr_vs_be_bit": "",
        "closes_wr_below_be": False,
        "closes_wr_edge_pp": None,
        "closes_wr_edge_severity": "",
        "closes_wr_edge_thin": False,
        "closes_kelly_pct": None,
        "closes_kelly_bit": "",
        "closes_kelly_severity": "",
        "closes_kelly_thin": False,
        "closes_kelly_neg": False,
        "closes_half_kelly_pct": None,
        "closes_half_kelly_sizer_pct": None,
        "closes_half_kelly_vs": "",
        "closes_half_kelly_bit": "",
        "closes_half_kelly_under": False,
        "closes_half_kelly_slot_pct": None,
        "closes_half_kelly_vs_slot": "",
        "closes_half_kelly_slot_bit": "",
        "closes_half_kelly_slot_under": False,
        "closes_half_kelly_cap_pct": None,
        "closes_half_kelly_vs_cap": "",
        "closes_half_kelly_cap_bit": "",
        "closes_half_kelly_cap_under": False,
        "closes_quarter_kelly_pct": None,
        "closes_quarter_kelly_sizer_pct": None,
        "closes_quarter_kelly_vs": "",
        "closes_quarter_kelly_bit": "",
        "closes_quarter_kelly_under": False,
        "closes_quarter_kelly_slot_pct": None,
        "closes_quarter_kelly_vs_slot": "",
        "closes_quarter_kelly_slot_bit": "",
        "closes_quarter_kelly_slot_under": False,
        "closes_quarter_kelly_cap_pct": None,
        "closes_quarter_kelly_vs_cap": "",
        "closes_quarter_kelly_cap_bit": "",
        "closes_quarter_kelly_cap_under": False,
        "closes_practical_kelly": "",
        "closes_practical_kelly_pct": None,
        "closes_practical_kelly_bit": "",
        "closes_practical_kelly_cut": False,
        "closes_kelly_sample": "",
        "closes_kelly_sample_n": None,
        "closes_kelly_sample_bit": "",
        "closes_kelly_sample_thin": False,
        "closes_loss_streak": None,
        "closes_loss_streak_bit": "",
        "closes_loss_streak_hot": False,
        "closes_net_expectancy": None,
        "closes_net_expectancy_bit": "",
        "closes_net_expectancy_neg": False,
        "closes_net_expectancy_severity": "",
        "closes_net_expectancy_thin": False,
        "closes_net_expectancy_ratio": None,
        "closes_net_expectancy_eats_edge": False,
        "closes_fee_take": None,
        "closes_fee_take_bit": "",
        "closes_fee_take_severity": "",
        "closes_fee_take_thin": False,
        "closes_fee_take_ratio": None,
        "closes_net_vs_fee": None,
        "closes_net_vs_fee_bit": "",
        "closes_net_vs_fee_severity": "",
        "closes_net_vs_fee_thin": False,
        "closes_net_profit_factor": None,
        "closes_net_profit_factor_bit": "",
        "closes_net_profit_factor_severity": "",
        "closes_net_profit_factor_thin": False,
        "closes_net_profit_factor_eats_edge": False,
        "closes_net_gross_wins": None,
        "sell_stale_days": None,
        "max_sell_stale_days": stale_need,
        "aging_sell_days": aging_need,
        "last_sell": None,
    }
    if not isinstance(stats, dict):
        return empty
    try:
        fills = int(stats.get("trades") or 0)
    except (TypeError, ValueError):
        fills = 0
    sides_known = "sells" in stats or "buys" in stats
    buys = 0
    sells = 0
    if sides_known:
        try:
            buys = int(stats.get("buys") or 0)
        except (TypeError, ValueError):
            buys = 0
        try:
            sells = int(stats.get("sells") or 0)
        except (TypeError, ValueError):
            sells = 0
        if "buys" not in stats and "sells" in stats:
            buys = max(0, fills - sells)
        elif "sells" not in stats and "buys" in stats:
            sells = max(0, fills - buys)
    thin = fills < need
    thin_bit = ""
    if thin:
        thin_bit = f"A thin · {fills} fills <{need}"
    open_only = sides_known and fills > 0 and sells == 0
    open_only_bit = ""
    if open_only:
        open_only_bit = "A open-only · 0 sells"
    thin_closes = sides_known and sells > 0 and sells < sell_need
    thin_closes_bit = ""
    if thin_closes:
        thin_closes_bit = f"A thin closes · {sells} sells <{sell_need}"

    last_sell_raw = stats.get("last_sell")
    last_sell_dt = parse_trade_timestamp(last_sell_raw)
    sell_stale_days: int | None = None
    stale_closes = False
    stale_closes_bit = ""
    aging_closes = False
    aging_closes_bit = ""
    fresh_closes = False
    fresh_closes_bit = ""
    closes_freshness = ""
    if (
        last_sell_dt is not None
        and not open_only
        and not thin_closes
        and sells >= sell_need
    ):
        today = as_of or date.today()
        sell_stale_days = _weekday_days_since(last_sell_dt.date(), today)
        if sell_stale_days > stale_need:
            stale_closes = True
            closes_freshness = "stale"
            stale_closes_bit = (
                f"A stale closes · last sell {sell_stale_days}d >{stale_need}d"
            )
        elif aging_need > 0 and sell_stale_days > aging_need:
            aging_closes = True
            closes_freshness = "aging"
            aging_closes_bit = (
                f"A aging closes · last sell {sell_stale_days}d"
            )
        else:
            fresh_closes = True
            closes_freshness = "fresh"
            fresh_closes_bit = (
                f"A fresh closes · last sell {sell_stale_days}d"
            )

    # Portfolio AI fee-burn: fees > realized on closed rounds → fee drag warn.
    # Prefer net −€N on the bit (same math as format_window_stats_bit).
    # Append fees÷realized multiple when realized > 0; label mild/heavy/severe
    # (or total when closed red) so friends see severity without math
    # (xang1234 severity bands + portfolio AI). When fees ≤ realized, speak
    # fees-ok triad: comfortable (<0.25×) · ok (mid) · thin (≥0.5× warn) —
    # portfolio AI quiet vs high + xang1234 speak-both-sides.
    # Open-only is already −fees.
    fee_drag = False
    fee_drag_bit = ""
    fee_drag_net: float | None = None
    fee_drag_ratio: float | None = None
    fee_drag_severity = ""
    fees_ok = False
    fees_ok_bit = ""
    fees_ok_net: float | None = None
    fees_ok_ratio: float | None = None
    fees_ok_severity = ""
    if sides_known and sells > 0 and not open_only:
        try:
            fees = float(stats.get("fees") or 0)
            realized = float(stats.get("realized_pnl") or 0)
            if stats.get("net_after_all_fees") is not None:
                net = float(stats.get("net_after_all_fees") or 0)
            else:
                net = realized - fees
        except (TypeError, ValueError):
            fees = 0.0
            realized = 0.0
            net = 0.0

        def _ratio_bit(fees_v: float, realized_v: float) -> tuple[float | None, str]:
            if realized_v <= 0:
                return None, ""
            ratio = fees_v / realized_v
            rounded = round(ratio, 2)
            if abs(ratio - round(ratio)) < 0.05:
                return rounded, f"fees {int(round(ratio))}×"
            return rounded, f"fees {ratio:.1f}×"

        def _net_s(net_v: float) -> str:
            abs_n = abs(net_v)
            if abs_n >= 1000:
                body = f"€{abs_n / 1000:.1f}k"
            else:
                body = f"€{abs_n:,.0f}"
            if net_v < 0:
                return f"−{body}"
            if net_v > 0:
                return f"+{body}"
            return body

        if fees > 0 and fees > realized:
            fee_drag = True
            fee_drag_net = net
            fee_drag_ratio, ratio_bit = _ratio_bit(fees, realized)
            if realized > 0:
                if fee_drag_ratio is not None and fee_drag_ratio >= WINDOW_A_FEE_DRAG_SEVERE_RATIO:
                    fee_drag_severity = "severe"
                elif fee_drag_ratio is not None and fee_drag_ratio >= WINDOW_A_FEE_DRAG_HEAVY_RATIO:
                    fee_drag_severity = "heavy"
                else:
                    fee_drag_severity = "mild"
            else:
                fee_drag_severity = "total"
            head = f"A fee drag {fee_drag_severity}"
            if net < 0:
                fee_drag_bit = f"{head} · net {_net_s(net)}"
                if ratio_bit:
                    fee_drag_bit = f"{fee_drag_bit} · {ratio_bit}"
            elif ratio_bit:
                fee_drag_bit = f"{head} · {ratio_bit}"
            else:
                fee_drag_bit = f"{head} · fees > realized"
        elif fees >= 0 and fees <= realized and (fees > 0 or realized > 0):
            # Quiet complement when churn did not eat closed-round edge.
            # Triad: comfortable (<0.25×) · ok (mid) · thin (≥0.5×, warn only).
            fees_ok = True
            fees_ok_net = net
            fees_ok_ratio, ratio_bit = _ratio_bit(fees, realized)
            if (
                fees_ok_ratio is not None
                and fees_ok_ratio >= WINDOW_A_FEES_THIN_RATIO
            ):
                fees_ok_severity = "thin"
                fees_ok_bit = "A fees thin"
            elif (
                fees_ok_ratio is not None
                and fees_ok_ratio < WINDOW_A_FEES_COMFORTABLE_RATIO
            ):
                fees_ok_severity = "comfortable"
                fees_ok_bit = "A fees comfortable"
            else:
                fees_ok_bit = "A fees ok"
            if net != 0:
                fees_ok_bit = f"{fees_ok_bit} · net {_net_s(net)}"
            if ratio_bit:
                fees_ok_bit = f"{fees_ok_bit} · {ratio_bit}"

    # Portfolio AI Win·Lose + xang1234 speak-both-sides: closed-round polarity.
    # all_win / mixed / all_loss · Nw/Nl. Mixed lean triad: mostly wins / even /
    # mostly losses (xang1234 severity bands). all_loss + loss_lean warn only
    # (still ready for B). Missing wins/losses keys → fail-open (no bit).
    closes_wins = 0
    closes_losses = 0
    closes_polarity_known = False
    closes_polarity = ""
    closes_polarity_bit = ""
    closes_polarity_lean = ""
    closes_all_loss = False
    closes_loss_lean = False
    if sides_known and sells > 0 and not open_only and (
        "wins" in stats or "losses" in stats
    ):
        try:
            closes_wins = int(stats.get("wins") or 0)
        except (TypeError, ValueError):
            closes_wins = 0
        try:
            closes_losses = int(stats.get("losses") or 0)
        except (TypeError, ValueError):
            closes_losses = 0
        closes_polarity_known = True
        side_bit = f"{closes_wins}w/{closes_losses}l"
        if closes_wins > 0 and closes_losses == 0:
            closes_polarity = "all_win"
            closes_polarity_bit = f"A all-win · {side_bit}"
        elif closes_losses > 0 and closes_wins == 0:
            closes_polarity = "all_loss"
            closes_all_loss = True
            closes_polarity_bit = f"A all-loss · {side_bit}"
        elif closes_wins > 0 and closes_losses > 0:
            closes_polarity = "mixed"
            if closes_wins > closes_losses:
                closes_polarity_lean = "win_lean"
                closes_polarity_bit = f"A mixed · mostly wins · {side_bit}"
            elif closes_losses > closes_wins:
                closes_polarity_lean = "loss_lean"
                closes_loss_lean = True
                closes_polarity_bit = f"A mixed · mostly losses · {side_bit}"
            else:
                closes_polarity_lean = "even"
                closes_polarity_bit = f"A mixed · even · {side_bit}"
        # else: all flat closes (0w/0l) — stay silent (rare; no edge signal)

    # Portfolio AI expectancy + xang1234 severity: avg_win ÷ avg_loss.
    # Count lean ≠ € lean (many small wins / one large loss → thin payoff).
    # Needs both sides with positive avgs; all_win / all_loss → fail-open.
    # thin <1× warns only (still ready for B).
    closes_avg_win: float | None = None
    closes_avg_loss: float | None = None
    closes_payoff_ratio: float | None = None
    closes_payoff_severity = ""
    closes_payoff_bit = ""
    closes_payoff_thin = False
    if sides_known and sells > 0 and not open_only and (
        "avg_win" in stats or "avg_loss" in stats or "payoff_ratio" in stats
    ):
        try:
            aw = stats.get("avg_win")
            closes_avg_win = float(aw) if aw is not None else None
        except (TypeError, ValueError):
            closes_avg_win = None
        try:
            al = stats.get("avg_loss")
            closes_avg_loss = float(al) if al is not None else None
        except (TypeError, ValueError):
            closes_avg_loss = None
        try:
            pr = stats.get("payoff_ratio")
            closes_payoff_ratio = float(pr) if pr is not None else None
        except (TypeError, ValueError):
            closes_payoff_ratio = None
        if (
            closes_payoff_ratio is None
            and closes_avg_win is not None
            and closes_avg_loss is not None
            and closes_avg_win > 0
            and closes_avg_loss > 0
        ):
            closes_payoff_ratio = closes_avg_win / closes_avg_loss
        if closes_payoff_ratio is not None and closes_payoff_ratio > 0:
            rounded = round(closes_payoff_ratio, 2)
            if abs(closes_payoff_ratio - round(closes_payoff_ratio)) < 0.05:
                ratio_s = f"{int(round(closes_payoff_ratio))}×"
            else:
                ratio_s = f"{closes_payoff_ratio:.1f}×"
            closes_payoff_ratio = rounded
            if closes_payoff_ratio < WINDOW_A_PAYOFF_THIN_RATIO:
                closes_payoff_severity = "thin"
                closes_payoff_thin = True
                closes_payoff_bit = f"A payoff thin · {ratio_s}"
            elif closes_payoff_ratio >= WINDOW_A_PAYOFF_STRONG_RATIO:
                closes_payoff_severity = "strong"
                closes_payoff_bit = f"A payoff strong · {ratio_s}"
            else:
                closes_payoff_bit = f"A payoff · {ratio_s}"

    # Portfolio AI €/close expectancy after payoff ratio.
    # win_rate·avg_win − loss_rate·avg_loss; all-win → avg_win; all-loss → −avg_loss.
    # Positive severity vs avg_loss (xang1234 bands): strong ≥0.5× · ok mid ·
    # thin <0.25× (tiny € edge vs typical loss). Neg + thin warn only.
    # Missing avgs / expectancy → fail-open.
    closes_expectancy: float | None = None
    closes_expectancy_bit = ""
    closes_expectancy_neg = False
    closes_expectancy_severity = ""
    closes_expectancy_thin = False
    closes_expectancy_ratio: float | None = None
    if sides_known and sells > 0 and not open_only:
        n_closed = closes_wins + closes_losses
        exp: float | None = None
        if "expectancy" in stats:
            try:
                raw_exp = stats.get("expectancy")
                exp = float(raw_exp) if raw_exp is not None else None
            except (TypeError, ValueError):
                exp = None
        elif n_closed > 0:
            aw = closes_avg_win
            al = closes_avg_loss
            if closes_wins > 0 and closes_losses == 0 and aw is not None and aw > 0:
                exp = aw
            elif closes_losses > 0 and closes_wins == 0 and al is not None and al > 0:
                exp = -al
            elif (
                closes_wins > 0
                and closes_losses > 0
                and aw is not None
                and al is not None
                and aw > 0
                and al > 0
            ):
                exp = (closes_wins / n_closed) * aw - (closes_losses / n_closed) * al
        if exp is not None:
            closes_expectancy = round(exp, 2)
            abs_e = abs(closes_expectancy)
            if abs_e >= 1000:
                body = f"€{abs_e / 1000:.1f}k"
            else:
                body = f"€{abs_e:,.0f}"
            if closes_expectancy < 0:
                signed = f"−{body}"
                closes_expectancy_neg = True
                closes_expectancy_bit = f"A expectancy {signed}"
            elif closes_expectancy > 0:
                signed = f"+{body}"
                # Severity vs avg_loss when known (payoff-style ratio bands).
                al = closes_avg_loss
                if al is not None and al > 0:
                    closes_expectancy_ratio = round(closes_expectancy / al, 3)
                    if closes_expectancy_ratio < WINDOW_A_EXPECTANCY_THIN_RATIO:
                        closes_expectancy_severity = "thin"
                        closes_expectancy_thin = True
                        closes_expectancy_bit = f"A expectancy thin · {signed}"
                    elif closes_expectancy_ratio >= WINDOW_A_EXPECTANCY_STRONG_RATIO:
                        closes_expectancy_severity = "strong"
                        closes_expectancy_bit = f"A expectancy strong · {signed}"
                    else:
                        closes_expectancy_bit = f"A expectancy · {signed}"
                else:
                    closes_expectancy_bit = f"A expectancy {signed}"
            else:
                closes_expectancy_bit = f"A expectancy {body}"

    # Portfolio AI profit factor after expectancy: gross wins ÷ gross losses.
    # Payoff is avg_win÷avg_loss; profit factor is total € (count × size).
    # Needs both sides with positive gross; all_win / all_loss → fail-open.
    # thin <1× warns only (still ready for B).
    closes_gross_wins: float | None = None
    closes_gross_losses: float | None = None
    closes_profit_factor: float | None = None
    closes_profit_factor_severity = ""
    closes_profit_factor_bit = ""
    closes_profit_factor_thin = False
    if sides_known and sells > 0 and not open_only and closes_wins > 0 and closes_losses > 0:
        try:
            gw = stats.get("gross_wins")
            closes_gross_wins = float(gw) if gw is not None else None
        except (TypeError, ValueError):
            closes_gross_wins = None
        try:
            gl = stats.get("gross_losses")
            closes_gross_losses = float(gl) if gl is not None else None
        except (TypeError, ValueError):
            closes_gross_losses = None
        try:
            pf = stats.get("profit_factor")
            closes_profit_factor = float(pf) if pf is not None else None
        except (TypeError, ValueError):
            closes_profit_factor = None
        if (
            closes_gross_wins is None
            and closes_avg_win is not None
            and closes_avg_win > 0
        ):
            closes_gross_wins = closes_wins * closes_avg_win
        if (
            closes_gross_losses is None
            and closes_avg_loss is not None
            and closes_avg_loss > 0
        ):
            closes_gross_losses = closes_losses * closes_avg_loss
        if (
            closes_profit_factor is None
            and closes_gross_wins is not None
            and closes_gross_losses is not None
            and closes_gross_wins > 0
            and closes_gross_losses > 0
        ):
            closes_profit_factor = closes_gross_wins / closes_gross_losses
        if closes_profit_factor is not None and closes_profit_factor > 0:
            rounded = round(closes_profit_factor, 2)
            if abs(closes_profit_factor - round(closes_profit_factor)) < 0.05:
                ratio_s = f"{int(round(closes_profit_factor))}×"
            else:
                ratio_s = f"{closes_profit_factor:.1f}×"
            closes_profit_factor = rounded
            if closes_gross_wins is not None:
                closes_gross_wins = round(closes_gross_wins, 2)
            if closes_gross_losses is not None:
                closes_gross_losses = round(closes_gross_losses, 2)
            if closes_profit_factor < WINDOW_A_PROFIT_FACTOR_THIN_RATIO:
                closes_profit_factor_severity = "thin"
                closes_profit_factor_thin = True
                closes_profit_factor_bit = f"A PF thin · {ratio_s}"
            elif closes_profit_factor >= WINDOW_A_PROFIT_FACTOR_STRONG_RATIO:
                closes_profit_factor_severity = "strong"
                closes_profit_factor_bit = f"A PF strong · {ratio_s}"
            else:
                closes_profit_factor_bit = f"A PF · {ratio_s}"

    # Portfolio AI win rate % after polarity: wins ÷ (wins+losses).
    # Count lean ≠ hit rate (3W/2L = mostly-wins lean and 60% strong).
    # Flats (pnl==0) are excluded from wins/losses already. thin <40% warns
    # only (still ready for B). Missing polarity → fail-open.
    closes_win_rate_pct: float | None = None
    closes_win_rate_severity = ""
    closes_win_rate_bit = ""
    closes_win_rate_thin = False
    if closes_polarity_known:
        n_decided = closes_wins + closes_losses
        if n_decided > 0:
            if "win_rate" in stats:
                try:
                    wr_raw = stats.get("win_rate")
                    closes_win_rate_pct = (
                        float(wr_raw) if wr_raw is not None else None
                    )
                except (TypeError, ValueError):
                    closes_win_rate_pct = None
            if closes_win_rate_pct is None:
                closes_win_rate_pct = 100.0 * closes_wins / n_decided
            closes_win_rate_pct = round(closes_win_rate_pct, 1)
            pct_s = (
                f"{int(round(closes_win_rate_pct))}%"
                if abs(closes_win_rate_pct - round(closes_win_rate_pct)) < 0.05
                else f"{closes_win_rate_pct:.1f}%"
            )
            if closes_win_rate_pct < WINDOW_A_WIN_RATE_THIN_PCT:
                closes_win_rate_severity = "thin"
                closes_win_rate_thin = True
                closes_win_rate_bit = f"A win rate thin · {pct_s}"
            elif closes_win_rate_pct >= WINDOW_A_WIN_RATE_STRONG_PCT:
                closes_win_rate_severity = "strong"
                closes_win_rate_bit = f"A win rate strong · {pct_s}"
            else:
                closes_win_rate_bit = f"A win rate · {pct_s}"

    # Portfolio AI WR vs breakeven from payoff: BE% = 100/(1+R).
    # Hit rate alone ≠ edge when payoff ≠ 1 (need higher WR when R < 1).
    # above / at (±AT pp) / below — speak cushion ±Npp with severity triad.
    # Thin cushion + below warn only (still ready for B).
    closes_breakeven_wr_pct: float | None = None
    closes_wr_vs_be = ""
    closes_wr_vs_be_bit = ""
    closes_wr_below_be = False
    closes_wr_edge_pp: float | None = None
    closes_wr_edge_severity = ""
    closes_wr_edge_thin = False
    if (
        closes_win_rate_pct is not None
        and closes_payoff_ratio is not None
        and closes_payoff_ratio > 0
    ):
        closes_breakeven_wr_pct = round(100.0 / (1.0 + closes_payoff_ratio), 1)
        delta = closes_win_rate_pct - closes_breakeven_wr_pct
        closes_wr_edge_pp = round(delta, 1)

        def _fmt_edge_pp(pp: float) -> str:
            if abs(pp) < 0.05:
                return "~0pp"
            nearest = round(pp)
            if abs(pp - nearest) < 0.05:
                return f"{int(nearest):+d}pp"
            return f"{pp:+.1f}pp"

        pp_s = _fmt_edge_pp(closes_wr_edge_pp)
        if delta < -WINDOW_A_WR_BE_AT_PP:
            closes_wr_vs_be = "below"
            closes_wr_below_be = True
            closes_wr_edge_thin = True
            closes_wr_vs_be_bit = f"A WR below BE · {pp_s}"
        elif delta > WINDOW_A_WR_BE_AT_PP:
            closes_wr_vs_be = "above"
            if closes_wr_edge_pp >= WINDOW_A_WR_EDGE_STRONG_PP:
                closes_wr_edge_severity = "strong"
                closes_wr_vs_be_bit = f"A WR above BE strong · {pp_s}"
            elif closes_wr_edge_pp < WINDOW_A_WR_EDGE_THIN_PP:
                closes_wr_edge_severity = "thin"
                closes_wr_edge_thin = True
                closes_wr_vs_be_bit = f"A WR above BE thin · {pp_s}"
            else:
                closes_wr_vs_be_bit = f"A WR above BE · {pp_s}"
        else:
            closes_wr_vs_be = "at"
            closes_wr_vs_be_bit = f"A WR at BE · {pp_s}"

    # Portfolio AI full Kelly after WR vs BE.
    # f* = p − (1−p)/R. WR vs BE ≠ the equity fraction the edge supports.
    # Full Kelly only — not half-Kelly and not the live cash sizer.
    # neg ≤0 and thin <5% warn only (still ready for B).
    closes_kelly_pct: float | None = None
    closes_kelly_bit = ""
    closes_kelly_severity = ""
    closes_kelly_thin = False
    closes_kelly_neg = False
    if (
        closes_win_rate_pct is not None
        and closes_payoff_ratio is not None
        and closes_payoff_ratio > 0
    ):
        p = closes_win_rate_pct / 100.0
        kelly = p - ((1.0 - p) / closes_payoff_ratio)
        closes_kelly_pct = round(kelly * 100.0, 1)
        abs_k = abs(closes_kelly_pct)
        if abs(abs_k - round(abs_k)) < 0.05:
            num = f"{int(round(abs_k))}"
        else:
            num = f"{abs_k:.1f}"
        if closes_kelly_pct < 0:
            closes_kelly_neg = True
            closes_kelly_bit = f"A Kelly neg · −{num}%"
        elif closes_kelly_pct == 0:
            closes_kelly_neg = True
            closes_kelly_bit = "A Kelly neg · 0%"
        elif closes_kelly_pct < WINDOW_A_KELLY_THIN_PCT:
            closes_kelly_severity = "thin"
            closes_kelly_thin = True
            closes_kelly_bit = f"A Kelly thin · {num}%"
        elif closes_kelly_pct >= WINDOW_A_KELLY_STRONG_PCT:
            closes_kelly_severity = "strong"
            closes_kelly_bit = f"A Kelly strong · {num}%"
        else:
            closes_kelly_bit = f"A Kelly · {num}%"

    # Portfolio AI half-Kelly vs the live ~10% cash sizer.
    # Practitioners size at half of full Kelly. The desk uses ~10% of cash.
    # under = sizer larger than that practical edge (warn only).
    # Then half-Kelly vs equal-slot (~20% at max_positions=5): cash sizer
    # ≠ equal book weight when the book is full (xang1234 severity).
    # Then half-Kelly vs soft concentration cap (~30%): equal slot ≠ the
    # single-name ceiling (tradermonty max_position_pct / C-conc).
    closes_half_kelly_pct: float | None = None
    closes_half_kelly_sizer_pct: float | None = None
    closes_half_kelly_vs = ""
    closes_half_kelly_bit = ""
    closes_half_kelly_under = False
    closes_half_kelly_slot_pct: float | None = None
    closes_half_kelly_vs_slot = ""
    closes_half_kelly_slot_bit = ""
    closes_half_kelly_slot_under = False
    closes_half_kelly_cap_pct: float | None = None
    closes_half_kelly_vs_cap = ""
    closes_half_kelly_cap_bit = ""
    closes_half_kelly_cap_under = False
    closes_quarter_kelly_pct: float | None = None
    closes_quarter_kelly_sizer_pct: float | None = None
    closes_quarter_kelly_vs = ""
    closes_quarter_kelly_bit = ""
    closes_quarter_kelly_under = False
    closes_quarter_kelly_slot_pct: float | None = None
    closes_quarter_kelly_vs_slot = ""
    closes_quarter_kelly_slot_bit = ""
    closes_quarter_kelly_slot_under = False
    closes_quarter_kelly_cap_pct: float | None = None
    closes_quarter_kelly_vs_cap = ""
    closes_quarter_kelly_cap_bit = ""
    closes_quarter_kelly_cap_under = False
    closes_practical_kelly = ""
    closes_practical_kelly_pct: float | None = None
    closes_practical_kelly_bit = ""
    closes_practical_kelly_cut = False
    closes_kelly_sample = ""
    closes_kelly_sample_n: int | None = None
    closes_kelly_sample_bit = ""
    closes_kelly_sample_thin = False
    closes_loss_streak: int | None = None
    closes_loss_streak_bit = ""
    closes_loss_streak_hot = False
    if closes_kelly_pct is not None:
        closes_half_kelly_pct = round(closes_kelly_pct / 2.0, 1)
        sizer_pct = round(float(DEFAULT_ENTRY_CASH_FRAC) * 100.0, 1)
        closes_half_kelly_sizer_pct = sizer_pct
        delta = closes_half_kelly_pct - sizer_pct

        def _fmt_kelly_pct(pct: float) -> str:
            abs_v = abs(pct)
            if abs(abs_v - round(abs_v)) < 0.05:
                num_s = f"{int(round(abs_v))}"
            else:
                num_s = f"{abs_v:.1f}"
            if pct < 0:
                return f"−{num_s}"
            return num_s

        pair = (
            f"{_fmt_kelly_pct(closes_half_kelly_pct)}% vs "
            f"{_fmt_kelly_pct(sizer_pct)}%"
        )
        if delta < -WINDOW_A_HALF_KELLY_MATCH_PP:
            closes_half_kelly_vs = "under"
            closes_half_kelly_under = True
            closes_half_kelly_bit = f"A half-Kelly vs sizer under · {pair}"
        elif delta > WINDOW_A_HALF_KELLY_MATCH_PP:
            closes_half_kelly_vs = "over"
            closes_half_kelly_bit = f"A half-Kelly vs sizer over · {pair}"
        else:
            closes_half_kelly_vs = "match"
            closes_half_kelly_bit = f"A half-Kelly vs sizer match · {pair}"

        slot_pct = float(WINDOW_A_EQUAL_SLOT_PCT)
        closes_half_kelly_slot_pct = slot_pct
        slot_delta = closes_half_kelly_pct - slot_pct
        slot_pair = (
            f"{_fmt_kelly_pct(closes_half_kelly_pct)}% vs "
            f"{_fmt_kelly_pct(slot_pct)}%"
        )
        if slot_delta < -WINDOW_A_HALF_KELLY_MATCH_PP:
            closes_half_kelly_vs_slot = "under"
            closes_half_kelly_slot_under = True
            closes_half_kelly_slot_bit = (
                f"A half-Kelly vs slot under · {slot_pair}"
            )
        elif slot_delta > WINDOW_A_HALF_KELLY_MATCH_PP:
            closes_half_kelly_vs_slot = "over"
            closes_half_kelly_slot_bit = (
                f"A half-Kelly vs slot over · {slot_pair}"
            )
        else:
            closes_half_kelly_vs_slot = "match"
            closes_half_kelly_slot_bit = (
                f"A half-Kelly vs slot match · {slot_pair}"
            )

        cap_pct = float(WINDOW_A_CONC_CAP_PCT)
        closes_half_kelly_cap_pct = cap_pct
        cap_delta = closes_half_kelly_pct - cap_pct
        cap_pair = (
            f"{_fmt_kelly_pct(closes_half_kelly_pct)}% vs "
            f"{_fmt_kelly_pct(cap_pct)}%"
        )
        if cap_delta < -WINDOW_A_HALF_KELLY_MATCH_PP:
            closes_half_kelly_vs_cap = "under"
            closes_half_kelly_cap_under = True
            closes_half_kelly_cap_bit = (
                f"A half-Kelly vs cap under · {cap_pair}"
            )
        elif cap_delta > WINDOW_A_HALF_KELLY_MATCH_PP:
            closes_half_kelly_vs_cap = "over"
            closes_half_kelly_cap_bit = (
                f"A half-Kelly vs cap over · {cap_pair}"
            )
        else:
            closes_half_kelly_vs_cap = "match"
            closes_half_kelly_cap_bit = (
                f"A half-Kelly vs cap match · {cap_pair}"
            )

        # Quarter-Kelly vs cash sizer — conservative practical fraction.
        # Half often sits well above ~10% when edge is strong; quarter shows
        # whether the desk cash slice is closer to ¼ Kelly (portfolio AI).
        closes_quarter_kelly_pct = round(
            closes_kelly_pct * float(WINDOW_A_QUARTER_KELLY_FRAC), 1
        )
        closes_quarter_kelly_sizer_pct = sizer_pct
        q_delta = closes_quarter_kelly_pct - sizer_pct
        q_pair = (
            f"{_fmt_kelly_pct(closes_quarter_kelly_pct)}% vs "
            f"{_fmt_kelly_pct(sizer_pct)}%"
        )
        if q_delta < -WINDOW_A_HALF_KELLY_MATCH_PP:
            closes_quarter_kelly_vs = "under"
            closes_quarter_kelly_under = True
            closes_quarter_kelly_bit = (
                f"A quarter-Kelly vs sizer under · {q_pair}"
            )
        elif q_delta > WINDOW_A_HALF_KELLY_MATCH_PP:
            closes_quarter_kelly_vs = "over"
            closes_quarter_kelly_bit = (
                f"A quarter-Kelly vs sizer over · {q_pair}"
            )
        else:
            closes_quarter_kelly_vs = "match"
            closes_quarter_kelly_bit = (
                f"A quarter-Kelly vs sizer match · {q_pair}"
            )

        # Quarter-Kelly vs equal-slot (~20%): cash sizer ≠ equal book weight.
        # Same ±5pp match band. Cap is the next comparison.
        closes_quarter_kelly_slot_pct = slot_pct
        q_slot_delta = closes_quarter_kelly_pct - slot_pct
        q_slot_pair = (
            f"{_fmt_kelly_pct(closes_quarter_kelly_pct)}% vs "
            f"{_fmt_kelly_pct(slot_pct)}%"
        )
        if q_slot_delta < -WINDOW_A_HALF_KELLY_MATCH_PP:
            closes_quarter_kelly_vs_slot = "under"
            closes_quarter_kelly_slot_under = True
            closes_quarter_kelly_slot_bit = (
                f"A quarter-Kelly vs slot under · {q_slot_pair}"
            )
        elif q_slot_delta > WINDOW_A_HALF_KELLY_MATCH_PP:
            closes_quarter_kelly_vs_slot = "over"
            closes_quarter_kelly_slot_bit = (
                f"A quarter-Kelly vs slot over · {q_slot_pair}"
            )
        else:
            closes_quarter_kelly_vs_slot = "match"
            closes_quarter_kelly_slot_bit = (
                f"A quarter-Kelly vs slot match · {q_slot_pair}"
            )

        # Quarter-Kelly vs soft concentration cap (~30%).
        # Equal slot ≠ single-name ceiling. ¼ of full Kelly is ≤25%, so
        # vs 30% this is usually under (portfolio AI + C-conc).
        closes_quarter_kelly_cap_pct = cap_pct
        q_cap_delta = closes_quarter_kelly_pct - cap_pct
        q_cap_pair = (
            f"{_fmt_kelly_pct(closes_quarter_kelly_pct)}% vs "
            f"{_fmt_kelly_pct(cap_pct)}%"
        )
        if q_cap_delta < -WINDOW_A_HALF_KELLY_MATCH_PP:
            closes_quarter_kelly_vs_cap = "under"
            closes_quarter_kelly_cap_under = True
            closes_quarter_kelly_cap_bit = (
                f"A quarter-Kelly vs cap under · {q_cap_pair}"
            )
        elif q_cap_delta > WINDOW_A_HALF_KELLY_MATCH_PP:
            closes_quarter_kelly_vs_cap = "over"
            closes_quarter_kelly_cap_bit = (
                f"A quarter-Kelly vs cap over · {q_cap_pair}"
            )
        else:
            closes_quarter_kelly_vs_cap = "match"
            closes_quarter_kelly_cap_bit = (
                f"A quarter-Kelly vs cap match · {q_cap_pair}"
            )

        # One pick after the half/quarter comparisons (portfolio AI).
        # Largest conventional fraction that fits the cash sizer.
        # half · cut when the sizer exceeds half-Kelly. none when f* ≤ 0.
        # Cut and none warn only (still ready for B). Not a live sizer.
        if closes_kelly_pct <= 0:
            closes_practical_kelly = "none"
            closes_practical_kelly_cut = True
            closes_practical_kelly_bit = "A practical Kelly none"
        elif closes_half_kelly_vs == "under":
            closes_practical_kelly = "half"
            closes_practical_kelly_cut = True
            closes_practical_kelly_pct = closes_half_kelly_pct
            closes_practical_kelly_bit = (
                "A practical Kelly half · cut · "
                f"{_fmt_kelly_pct(closes_half_kelly_pct)}%"
            )
        elif closes_half_kelly_vs == "match":
            closes_practical_kelly = "half"
            closes_practical_kelly_pct = closes_half_kelly_pct
            closes_practical_kelly_bit = (
                "A practical Kelly half · "
                f"{_fmt_kelly_pct(closes_half_kelly_pct)}%"
            )
        elif closes_quarter_kelly_vs == "over":
            closes_practical_kelly = "sizer"
            closes_practical_kelly_pct = sizer_pct
            closes_practical_kelly_bit = (
                "A practical Kelly sizer · "
                f"{_fmt_kelly_pct(sizer_pct)}%"
            )
        else:
            closes_practical_kelly = "quarter"
            closes_practical_kelly_pct = closes_quarter_kelly_pct
            closes_practical_kelly_bit = (
                "A practical Kelly quarter · "
                f"{_fmt_kelly_pct(closes_quarter_kelly_pct)}%"
            )

        # Kelly from few closes is noise (portfolio AI + xang1234 sample).
        # Close floor of 3 sells ≠ a size sample. thin warns only.
        if closes_polarity_known:
            n_sample = closes_wins + closes_losses
            closes_kelly_sample_n = n_sample
            need = int(WINDOW_A_KELLY_SAMPLE_MIN)
            if n_sample < need:
                closes_kelly_sample = "thin"
                closes_kelly_sample_thin = True
                closes_kelly_sample_bit = (
                    f"A Kelly sample thin · {n_sample} closes <{need}"
                )
            else:
                closes_kelly_sample = "ok"
                closes_kelly_sample_bit = (
                    f"A Kelly sample ok · {n_sample} closes"
                )

    # Newest losing-close run (portfolio AI + tradermonty). Counts ≠ a run.
    # quiet 0–1 speaks. hot ≥2 warns only (still ready for B).
    # Missing key or None → fail-open (no bit).
    if sides_known and sells > 0 and not open_only and "loss_streak" in stats:
        raw_streak = stats.get("loss_streak")
        if raw_streak is not None:
            try:
                n_streak = int(raw_streak)
            except (TypeError, ValueError):
                n_streak = -1
            if n_streak >= 0:
                closes_loss_streak = n_streak
                if n_streak >= WINDOW_A_LOSS_STREAK_HOT:
                    closes_loss_streak_hot = True
                    closes_loss_streak_bit = f"A loss streak hot · {n_streak}"
                else:
                    closes_loss_streak_bit = f"A loss streak quiet · {n_streak}"

    # Portfolio AI fee-adjusted net expectancy after gross €/close.
    # net_after_all_fees ÷ sells — buy+sell fees on every close. Gross
    # expectancy can look fine while fee-adjusted €/close is red.
    # Severity reuses EXPECTANCY_* vs avg_loss. Gross+ / net− → eats_edge.
    # Neg + thin + eats_edge warn only (still ready for B).
    closes_net_expectancy: float | None = None
    closes_net_expectancy_bit = ""
    closes_net_expectancy_neg = False
    closes_net_expectancy_severity = ""
    closes_net_expectancy_thin = False
    closes_net_expectancy_ratio: float | None = None
    closes_net_expectancy_eats_edge = False
    if sides_known and sells > 0 and not open_only:
        net_all: float | None = None
        if "net_after_all_fees" in stats:
            try:
                raw_net = stats.get("net_after_all_fees")
                net_all = float(raw_net) if raw_net is not None else None
            except (TypeError, ValueError):
                net_all = None
        elif "fees" in stats and "realized_pnl" in stats:
            try:
                net_all = float(stats.get("realized_pnl") or 0) - float(
                    stats.get("fees") or 0
                )
            except (TypeError, ValueError):
                net_all = None
        if net_all is not None:
            closes_net_expectancy = round(net_all / sells, 2)
            abs_n = abs(closes_net_expectancy)
            if abs_n >= 1000:
                body = f"€{abs_n / 1000:.1f}k"
            else:
                body = f"€{abs_n:,.0f}"
            if closes_net_expectancy < 0:
                signed = f"−{body}"
                closes_net_expectancy_neg = True
                closes_net_expectancy_bit = f"A net expect {signed}"
                if (
                    closes_expectancy is not None
                    and closes_expectancy > 0
                ):
                    closes_net_expectancy_eats_edge = True
                    closes_net_expectancy_bit = (
                        f"A net expect {signed} · fees eat edge"
                    )
            elif closes_net_expectancy > 0:
                signed = f"+{body}"
                al = closes_avg_loss
                if al is not None and al > 0:
                    closes_net_expectancy_ratio = round(
                        closes_net_expectancy / al, 3
                    )
                    if (
                        closes_net_expectancy_ratio
                        < WINDOW_A_EXPECTANCY_THIN_RATIO
                    ):
                        closes_net_expectancy_severity = "thin"
                        closes_net_expectancy_thin = True
                        closes_net_expectancy_bit = (
                            f"A net expect thin · {signed}"
                        )
                    elif (
                        closes_net_expectancy_ratio
                        >= WINDOW_A_EXPECTANCY_STRONG_RATIO
                    ):
                        closes_net_expectancy_severity = "strong"
                        closes_net_expectancy_bit = (
                            f"A net expect strong · {signed}"
                        )
                    else:
                        closes_net_expectancy_bit = f"A net expect · {signed}"
                else:
                    closes_net_expectancy_bit = f"A net expect {signed}"
            else:
                closes_net_expectancy_bit = f"A net expect {body}"

    # Portfolio AI expectancy fee take after gross + net €/close.
    # fee_take = gross_expectancy − net_expectancy (€/close fees remove).
    # Distinct from fee drag (total fees vs realized) and net expect (€/close).
    # Severity when gross > 0 reuses FEES_* ratios (comfortable <0.25 ·
    # thin ≥0.5). Thin warn only (still ready for B).
    closes_fee_take: float | None = None
    closes_fee_take_bit = ""
    closes_fee_take_severity = ""
    closes_fee_take_thin = False
    closes_fee_take_ratio: float | None = None
    if (
        closes_expectancy is not None
        and closes_net_expectancy is not None
    ):
        closes_fee_take = round(closes_expectancy - closes_net_expectancy, 2)
        if abs(closes_fee_take) >= 0.005:
            abs_t = abs(closes_fee_take)
            if abs_t >= 1000:
                body = f"€{abs_t / 1000:.1f}k"
            else:
                body = f"€{abs_t:,.0f}"
            if closes_fee_take < 0:
                closes_fee_take_bit = f"A fee take −{body}/close"
            elif closes_expectancy > 0:
                closes_fee_take_ratio = round(
                    closes_fee_take / closes_expectancy, 3
                )
                if closes_fee_take_ratio >= WINDOW_A_FEES_THIN_RATIO:
                    closes_fee_take_severity = "thin"
                    closes_fee_take_thin = True
                    closes_fee_take_bit = f"A fee take thin · {body}/close"
                elif (
                    closes_fee_take_ratio < WINDOW_A_FEES_COMFORTABLE_RATIO
                ):
                    closes_fee_take_severity = "comfortable"
                    closes_fee_take_bit = (
                        f"A fee take comfortable · {body}/close"
                    )
                else:
                    closes_fee_take_bit = f"A fee take · {body}/close"
            else:
                closes_fee_take_bit = f"A fee take · {body}/close"

    # Portfolio AI net vs fee take after fee take €/close.
    # net_vs_fee = net_expectancy ÷ fee_take — how many fee-takes of edge
    # remain. Fee take € alone ≠ remaining edge multiples. Severity reuses
    # PROFIT_FACTOR_* (strong ≥2× · thin <1×). Thin warn only (still ready
    # for B). Skip when net ≤ 0 or fee take ≤ 0 (covered by other bits).
    closes_net_vs_fee: float | None = None
    closes_net_vs_fee_bit = ""
    closes_net_vs_fee_severity = ""
    closes_net_vs_fee_thin = False
    if (
        closes_net_expectancy is not None
        and closes_fee_take is not None
        and closes_net_expectancy > 0
        and closes_fee_take > 0
    ):
        closes_net_vs_fee = round(closes_net_expectancy / closes_fee_take, 2)
        if abs(closes_net_vs_fee - round(closes_net_vs_fee)) < 0.05:
            ratio_s = f"{int(round(closes_net_vs_fee))}×"
        else:
            ratio_s = f"{closes_net_vs_fee:.1f}×"
        if closes_net_vs_fee < WINDOW_A_PROFIT_FACTOR_THIN_RATIO:
            closes_net_vs_fee_severity = "thin"
            closes_net_vs_fee_thin = True
            closes_net_vs_fee_bit = f"A net/fee thin · {ratio_s}"
        elif closes_net_vs_fee >= WINDOW_A_PROFIT_FACTOR_STRONG_RATIO:
            closes_net_vs_fee_severity = "strong"
            closes_net_vs_fee_bit = f"A net/fee strong · {ratio_s}"
        else:
            closes_net_vs_fee_bit = f"A net/fee · {ratio_s}"

    # Portfolio AI fee-adjusted net profit factor after gross PF + fee take.
    # net_wins = gross_wins − window fees (conservative: fees hit winners).
    # net_pf = net_wins ÷ gross_losses. Gross PF can look fine while fees
    # wipe the total € ratio. Severity reuses PROFIT_FACTOR_*. Gross PF ≥1×
    # and net_wins ≤0 → eats_edge. Thin + eats_edge warn only (still ready).
    closes_net_profit_factor: float | None = None
    closes_net_profit_factor_bit = ""
    closes_net_profit_factor_severity = ""
    closes_net_profit_factor_thin = False
    closes_net_profit_factor_eats_edge = False
    closes_net_gross_wins: float | None = None
    if (
        closes_gross_wins is not None
        and closes_gross_losses is not None
        and closes_gross_wins > 0
        and closes_gross_losses > 0
        and sides_known
        and sells > 0
        and not open_only
    ):
        fees_for_pf: float | None = None
        if "fees" in stats:
            try:
                fees_for_pf = float(stats.get("fees") or 0)
            except (TypeError, ValueError):
                fees_for_pf = None
        if fees_for_pf is not None and fees_for_pf >= 0:
            closes_net_gross_wins = round(closes_gross_wins - fees_for_pf, 2)
            gross_pf_ok = (
                closes_profit_factor is not None
                and closes_profit_factor >= WINDOW_A_PROFIT_FACTOR_THIN_RATIO
            )
            if closes_net_gross_wins <= 0:
                closes_net_profit_factor_thin = True
                if gross_pf_ok:
                    closes_net_profit_factor_eats_edge = True
                    closes_net_profit_factor_bit = "A net PF · fees eat PF"
                else:
                    closes_net_profit_factor_severity = "thin"
                    closes_net_profit_factor_bit = "A net PF thin · 0×"
            else:
                net_pf = closes_net_gross_wins / closes_gross_losses
                rounded = round(net_pf, 2)
                if abs(net_pf - round(net_pf)) < 0.05:
                    ratio_s = f"{int(round(net_pf))}×"
                else:
                    ratio_s = f"{net_pf:.1f}×"
                closes_net_profit_factor = rounded
                if net_pf < WINDOW_A_PROFIT_FACTOR_THIN_RATIO:
                    closes_net_profit_factor_severity = "thin"
                    closes_net_profit_factor_thin = True
                    closes_net_profit_factor_bit = f"A net PF thin · {ratio_s}"
                elif net_pf >= WINDOW_A_PROFIT_FACTOR_STRONG_RATIO:
                    closes_net_profit_factor_severity = "strong"
                    closes_net_profit_factor_bit = f"A net PF strong · {ratio_s}"
                else:
                    closes_net_profit_factor_bit = f"A net PF · {ratio_s}"


    ready = (
        (not thin)
        and (not open_only)
        and (not thin_closes)
        and (not stale_closes)
    )
    return {
        "ready": ready,
        "known": True,
        "fills": fills,
        "target_fills": need,
        "buys": buys,
        "sells": sells,
        "sides_known": sides_known,
        "target_sells": sell_need,
        "thin": thin,
        "thin_bit": thin_bit,
        "open_only": open_only,
        "open_only_bit": open_only_bit,
        "thin_closes": thin_closes,
        "thin_closes_bit": thin_closes_bit,
        "stale_closes": stale_closes,
        "stale_closes_bit": stale_closes_bit,
        "aging_closes": aging_closes,
        "aging_closes_bit": aging_closes_bit,
        "fresh_closes": fresh_closes,
        "fresh_closes_bit": fresh_closes_bit,
        "closes_freshness": closes_freshness,
        "fee_drag": fee_drag,
        "fee_drag_bit": fee_drag_bit,
        "fee_drag_net": fee_drag_net,
        "fee_drag_ratio": fee_drag_ratio,
        "fee_drag_severity": fee_drag_severity,
        "fees_ok": fees_ok,
        "fees_ok_bit": fees_ok_bit,
        "fees_ok_net": fees_ok_net,
        "fees_ok_ratio": fees_ok_ratio,
        "fees_ok_severity": fees_ok_severity,
        "closes_wins": closes_wins,
        "closes_losses": closes_losses,
        "closes_polarity_known": closes_polarity_known,
        "closes_polarity": closes_polarity,
        "closes_polarity_bit": closes_polarity_bit,
        "closes_polarity_lean": closes_polarity_lean,
        "closes_all_loss": closes_all_loss,
        "closes_loss_lean": closes_loss_lean,
        "closes_avg_win": closes_avg_win,
        "closes_avg_loss": closes_avg_loss,
        "closes_payoff_ratio": closes_payoff_ratio,
        "closes_payoff_severity": closes_payoff_severity,
        "closes_payoff_bit": closes_payoff_bit,
        "closes_payoff_thin": closes_payoff_thin,
        "closes_expectancy": closes_expectancy,
        "closes_expectancy_bit": closes_expectancy_bit,
        "closes_expectancy_neg": closes_expectancy_neg,
        "closes_expectancy_severity": closes_expectancy_severity,
        "closes_expectancy_thin": closes_expectancy_thin,
        "closes_expectancy_ratio": closes_expectancy_ratio,
        "closes_profit_factor": closes_profit_factor,
        "closes_profit_factor_severity": closes_profit_factor_severity,
        "closes_profit_factor_bit": closes_profit_factor_bit,
        "closes_profit_factor_thin": closes_profit_factor_thin,
        "closes_gross_wins": closes_gross_wins,
        "closes_gross_losses": closes_gross_losses,
        "closes_win_rate_pct": closes_win_rate_pct,
        "closes_win_rate_severity": closes_win_rate_severity,
        "closes_win_rate_bit": closes_win_rate_bit,
        "closes_win_rate_thin": closes_win_rate_thin,
        "closes_breakeven_wr_pct": closes_breakeven_wr_pct,
        "closes_wr_vs_be": closes_wr_vs_be,
        "closes_wr_vs_be_bit": closes_wr_vs_be_bit,
        "closes_wr_below_be": closes_wr_below_be,
        "closes_wr_edge_pp": closes_wr_edge_pp,
        "closes_wr_edge_severity": closes_wr_edge_severity,
        "closes_wr_edge_thin": closes_wr_edge_thin,
        "closes_kelly_pct": closes_kelly_pct,
        "closes_kelly_bit": closes_kelly_bit,
        "closes_kelly_severity": closes_kelly_severity,
        "closes_kelly_thin": closes_kelly_thin,
        "closes_kelly_neg": closes_kelly_neg,
        "closes_half_kelly_pct": closes_half_kelly_pct,
        "closes_half_kelly_sizer_pct": closes_half_kelly_sizer_pct,
        "closes_half_kelly_vs": closes_half_kelly_vs,
        "closes_half_kelly_bit": closes_half_kelly_bit,
        "closes_half_kelly_under": closes_half_kelly_under,
        "closes_half_kelly_slot_pct": closes_half_kelly_slot_pct,
        "closes_half_kelly_vs_slot": closes_half_kelly_vs_slot,
        "closes_half_kelly_slot_bit": closes_half_kelly_slot_bit,
        "closes_half_kelly_slot_under": closes_half_kelly_slot_under,
        "closes_half_kelly_cap_pct": closes_half_kelly_cap_pct,
        "closes_half_kelly_vs_cap": closes_half_kelly_vs_cap,
        "closes_half_kelly_cap_bit": closes_half_kelly_cap_bit,
        "closes_half_kelly_cap_under": closes_half_kelly_cap_under,
        "closes_quarter_kelly_pct": closes_quarter_kelly_pct,
        "closes_quarter_kelly_sizer_pct": closes_quarter_kelly_sizer_pct,
        "closes_quarter_kelly_vs": closes_quarter_kelly_vs,
        "closes_quarter_kelly_bit": closes_quarter_kelly_bit,
        "closes_quarter_kelly_under": closes_quarter_kelly_under,
        "closes_quarter_kelly_slot_pct": closes_quarter_kelly_slot_pct,
        "closes_quarter_kelly_vs_slot": closes_quarter_kelly_vs_slot,
        "closes_quarter_kelly_slot_bit": closes_quarter_kelly_slot_bit,
        "closes_quarter_kelly_slot_under": closes_quarter_kelly_slot_under,
        "closes_quarter_kelly_cap_pct": closes_quarter_kelly_cap_pct,
        "closes_quarter_kelly_vs_cap": closes_quarter_kelly_vs_cap,
        "closes_quarter_kelly_cap_bit": closes_quarter_kelly_cap_bit,
        "closes_quarter_kelly_cap_under": closes_quarter_kelly_cap_under,
        "closes_practical_kelly": closes_practical_kelly,
        "closes_practical_kelly_pct": closes_practical_kelly_pct,
        "closes_practical_kelly_bit": closes_practical_kelly_bit,
        "closes_practical_kelly_cut": closes_practical_kelly_cut,
        "closes_kelly_sample": closes_kelly_sample,
        "closes_kelly_sample_n": closes_kelly_sample_n,
        "closes_kelly_sample_bit": closes_kelly_sample_bit,
        "closes_kelly_sample_thin": closes_kelly_sample_thin,
        "closes_loss_streak": closes_loss_streak,
        "closes_loss_streak_bit": closes_loss_streak_bit,
        "closes_loss_streak_hot": closes_loss_streak_hot,
        "closes_net_expectancy": closes_net_expectancy,
        "closes_net_expectancy_bit": closes_net_expectancy_bit,
        "closes_net_expectancy_neg": closes_net_expectancy_neg,
        "closes_net_expectancy_severity": closes_net_expectancy_severity,
        "closes_net_expectancy_thin": closes_net_expectancy_thin,
        "closes_net_expectancy_ratio": closes_net_expectancy_ratio,
        "closes_net_expectancy_eats_edge": closes_net_expectancy_eats_edge,
        "closes_fee_take": closes_fee_take,
        "closes_fee_take_bit": closes_fee_take_bit,
        "closes_fee_take_severity": closes_fee_take_severity,
        "closes_fee_take_thin": closes_fee_take_thin,
        "closes_fee_take_ratio": closes_fee_take_ratio,
        "closes_net_vs_fee": closes_net_vs_fee,
        "closes_net_vs_fee_bit": closes_net_vs_fee_bit,
        "closes_net_vs_fee_severity": closes_net_vs_fee_severity,
        "closes_net_vs_fee_thin": closes_net_vs_fee_thin,
        "closes_net_profit_factor": closes_net_profit_factor,
        "closes_net_profit_factor_bit": closes_net_profit_factor_bit,
        "closes_net_profit_factor_severity": closes_net_profit_factor_severity,
        "closes_net_profit_factor_thin": closes_net_profit_factor_thin,
        "closes_net_profit_factor_eats_edge": closes_net_profit_factor_eats_edge,
        "closes_net_gross_wins": closes_net_gross_wins,
        "sell_stale_days": sell_stale_days,
        "max_sell_stale_days": stale_need,
        "aging_sell_days": aging_need,
        "last_sell": last_sell_dt.isoformat() if last_sell_dt else None,
    }



def format_window_a_thin_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A thin-sample bit for promote A/B glance."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("thin_bit") or "").strip()
    return bit


def format_window_a_open_only_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A open-only (no closed rounds) bit for promote A/B glance."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("open_only_bit") or "").strip()
    return bit


def format_window_a_thin_closes_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A thin-closes bit (sparse sells vs close floor; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("thin_closes_bit") or "").strip()
    return bit


def format_window_a_stale_closes_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A stale-closes bit (last sell too old) for promote A/B glance."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("stale_closes_bit") or "").strip()
    return bit


def format_window_a_aging_closes_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A aging-closes bit (warn before hard stale; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("aging_closes_bit") or "").strip()
    return bit


def format_window_a_fresh_closes_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A fresh-closes bit (completes fresh/aging/stale; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("fresh_closes_bit") or "").strip()
    return bit


def format_window_a_fee_drag_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A fee-drag bit (net −€N · fees N× when known; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("fee_drag_bit") or "").strip()
    return bit


def format_window_a_fees_ok_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A fees-ok bit (quiet complement to fee drag; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("fees_ok_bit") or "").strip()
    return bit


def format_window_a_closes_polarity_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A close win/lose polarity bit (display only; not a gate)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_polarity_bit") or "").strip()
    return bit


def format_window_a_closes_payoff_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A close payoff bit (avg win ÷ avg loss; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_payoff_bit") or "").strip()
    return bit


def format_window_a_closes_expectancy_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A close expectancy bit (€/close; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_expectancy_bit") or "").strip()
    return bit


def format_window_a_closes_profit_factor_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A profit-factor bit (gross wins ÷ losses; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_profit_factor_bit") or "").strip()
    return bit


def format_window_a_closes_win_rate_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A win-rate bit (wins ÷ decided closes; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_win_rate_bit") or "").strip()
    return bit


def format_window_a_closes_wr_vs_be_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A WR vs breakeven bit (±pp cushion; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_wr_vs_be_bit") or "").strip()
    return bit


def format_window_a_closes_kelly_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A full-Kelly bit (equity fraction; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_kelly_bit") or "").strip()
    return bit


def format_window_a_closes_half_kelly_bit(sample: dict[str, Any] | None) -> str:
    """Short Window A half-Kelly vs cash-sizer bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_half_kelly_bit") or "").strip()
    return bit


def format_window_a_closes_half_kelly_slot_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A half-Kelly vs equal-slot bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_half_kelly_slot_bit") or "").strip()
    return bit


def format_window_a_closes_half_kelly_cap_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A half-Kelly vs concentration-cap bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_half_kelly_cap_bit") or "").strip()
    return bit


def format_window_a_closes_quarter_kelly_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A quarter-Kelly vs cash-sizer bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_quarter_kelly_bit") or "").strip()
    return bit


def format_window_a_closes_quarter_kelly_slot_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A quarter-Kelly vs equal-slot bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_quarter_kelly_slot_bit") or "").strip()
    return bit


def format_window_a_closes_quarter_kelly_cap_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A quarter-Kelly vs concentration-cap bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_quarter_kelly_cap_bit") or "").strip()
    return bit


def format_window_a_closes_practical_kelly_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A practical-Kelly pick (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_practical_kelly_bit") or "").strip()
    return bit


def format_window_a_closes_kelly_sample_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A Kelly sample-size bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_kelly_sample_bit") or "").strip()
    return bit


def format_window_a_closes_loss_streak_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A ending loss-streak bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_loss_streak_bit") or "").strip()
    return bit


def format_window_a_closes_net_expectancy_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A fee-adjusted net expectancy bit (€/close; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_net_expectancy_bit") or "").strip()
    return bit


def format_window_a_closes_fee_take_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A expectancy fee take bit (€/close; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_fee_take_bit") or "").strip()
    return bit



def format_window_a_closes_net_vs_fee_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A net/fee multiple bit (net ÷ fee take; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_net_vs_fee_bit") or "").strip()
    return bit


def format_window_a_closes_net_profit_factor_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A fee-adjusted net profit-factor bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_net_profit_factor_bit") or "").strip()
    return bit


def format_window_a_side_bit(sample: dict[str, Any] | None) -> str:
    """Compact buy/sell composition: ``Nb/Ns`` (portfolio AI sample honesty).

    Unknown sides → empty. Display only; not a gate.
    Prefer ``format_window_a_sell_progress_bit`` on the glance meter.
    """
    if not isinstance(sample, dict) or not sample.get("known"):
        return ""
    if not sample.get("sides_known"):
        return ""
    try:
        buys = int(sample.get("buys") or 0)
        sells = int(sample.get("sells") or 0)
    except (TypeError, ValueError):
        return ""
    return f"{buys}b/{sells}s"


def format_window_a_sell_progress_bit(sample: dict[str, Any] | None) -> str:
    """Close-floor meter: ``N/M sells`` (portfolio AI + xang1234 multi-meter).

    Fills alone mislead after the ≥3 close floor — show sell progress beside
    days/fills. Unknown / no sides → empty. Display only; not a gate.
    """
    if not isinstance(sample, dict) or not sample.get("known"):
        return ""
    if not sample.get("sides_known"):
        return ""
    try:
        sells = int(sample.get("sells") or 0)
        need = int(sample.get("target_sells") or WINDOW_A_TARGET_SELLS)
    except (TypeError, ValueError):
        return ""
    need = max(1, need)
    return f"{sells}/{need} sells"


def format_window_a_fill_progress_bit(sample: dict[str, Any] | None) -> str:
    """Triple sample meter: ``N/M fills`` · ``N/M sells`` beside days.

    Days alone mislead — show fill progress while Window A is still running.
    When buy/sell sides are known, append close-floor ``N/M sells`` (not
    ``Nb/Ns`` — sell progress toward the floor is the honest dual meter).
    Unknown stats → empty (keep summarize). Display only; not a gate.
    """
    if not isinstance(sample, dict) or not sample.get("known"):
        return ""
    try:
        fills = int(sample.get("fills") or 0)
        need = int(sample.get("target_fills") or WINDOW_A_TARGET_FILLS)
    except (TypeError, ValueError):
        return ""
    need = max(1, need)
    bit = f"{fills}/{need} fills"
    sells = format_window_a_sell_progress_bit(sample)
    if sells:
        bit = f"{bit} · {sells}"
    return bit


def weekday_trading_days(start: date, end: date) -> int:
    """Count Mon–Fri calendar days from start through end (inclusive)."""
    if end < start:
        return 0
    days = 0
    cur = start
    one = timedelta(days=1)
    while cur <= end:
        if cur.weekday() < 5:
            days += 1
        cur += one
    return days


def promote_ab_snapshot(
    promote_on: bool,
    *,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Compact Window A/B status for desk honesty (not a gate)."""
    today = as_of or date.today()
    if WINDOW_B_START is not None:
        b_days = weekday_trading_days(WINDOW_B_START, today)
        return {
            "window": "B",
            "promote_expected": True,
            "promote_on": bool(promote_on),
            "trading_days": b_days,
            "target_days": WINDOW_A_TARGET_TRADING_DAYS,
            "target_met": b_days >= WINDOW_A_TARGET_TRADING_DAYS,
            "protocol_ok": bool(promote_on),
            "window_a_start": WINDOW_A_START.isoformat(),
            "window_b_start": WINDOW_B_START.isoformat(),
        }

    a_days = weekday_trading_days(WINDOW_A_START, today)
    return {
        "window": "A",
        "promote_expected": False,
        "promote_on": bool(promote_on),
        "trading_days": a_days,
        "target_days": WINDOW_A_TARGET_TRADING_DAYS,
        "target_met": a_days >= WINDOW_A_TARGET_TRADING_DAYS,
        "protocol_ok": not bool(promote_on),
        "window_a_start": WINDOW_A_START.isoformat(),
        "window_b_start": None,
    }


def parse_trade_timestamp(raw: Any) -> datetime | None:
    """Parse trade timestamp to aware UTC datetime, or None."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        text = str(raw).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        # Allow "YYYY-MM-DD HH:MM:SS" from paper ledger
        if "T" not in text and " " in text and "+" not in text:
            text = text.replace(" ", "T", 1)
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def active_window_start_utc(*, promote_on: bool | None = None) -> datetime:
    """UTC start of the active promote A/B window (B if started, else A)."""
    if WINDOW_B_START_UTC is not None:
        return WINDOW_B_START_UTC
    if WINDOW_B_START is not None:
        return datetime(
            WINDOW_B_START.year,
            WINDOW_B_START.month,
            WINDOW_B_START.day,
            tzinfo=timezone.utc,
        )
    _ = promote_on  # protocol uses calendar start; promote flag checked elsewhere
    return WINDOW_A_START_UTC


def filter_trades_in_window(
    trades: Iterable[dict[str, Any]],
    *,
    start: datetime,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    """Keep trades with timestamp in [start, end] (end inclusive if set)."""
    out: list[dict[str, Any]] = []
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        ts = parse_trade_timestamp(trade.get("timestamp"))
        if ts is None:
            continue
        if ts < start:
            continue
        if end is not None and ts > end:
            continue
        out.append(trade)
    return out


def ending_loss_streak(sells: Iterable[dict[str, Any]]) -> int | None:
    """Newest run of losing closes. None when no dated decided sell.

    Flat closes do not count and do not break the run. A win breaks the run.
    Order uses timestamps, not list order. Display only — not a gate.
    """
    dated: list[tuple[datetime, float]] = []
    for sell in sells:
        if not isinstance(sell, dict):
            continue
        ts = parse_trade_timestamp(sell.get("timestamp"))
        if ts is None:
            continue
        try:
            pnl = float(sell.get("profit_loss") or 0)
        except (TypeError, ValueError):
            continue
        if pnl == 0:
            continue
        dated.append((ts, pnl))
    if not dated:
        return None
    dated.sort(key=lambda row: row[0])
    streak = 0
    for _ts, pnl in reversed(dated):
        if pnl < 0:
            streak += 1
            continue
        break
    return streak


def summarize_window_trades(
    trades: Iterable[dict[str, Any]],
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, Any]:
    """Fee vs realized fill stats for a promote window (portfolio AI honesty).

    Realized P&L is sell ``profit_loss`` only. Fees sum all legs in-window.
    Crypto legs use ``is_crypto_symbol`` (historical alts included). Not a gate.
    """
    from stock_checker.crypto_policy import is_crypto_symbol

    start_dt = start if start is not None else WINDOW_A_START_UTC
    window = filter_trades_in_window(trades, start=start_dt, end=end)
    buys = [t for t in window if str(t.get("type") or "").upper() == "BUY"]
    sells = [t for t in window if str(t.get("type") or "").upper() == "SELL"]
    fees = sum(float(t.get("commission") or 0) for t in window)
    realized = sum(float(t.get("profit_loss") or 0) for t in sells)
    sell_fees = sum(float(t.get("commission") or 0) for t in sells)
    crypto_legs = sum(
        1 for t in window if is_crypto_symbol(str(t.get("symbol") or ""))
    )
    wins = sum(1 for t in sells if float(t.get("profit_loss") or 0) > 0)
    losses = sum(1 for t in sells if float(t.get("profit_loss") or 0) < 0)
    win_pnls = [
        float(t.get("profit_loss") or 0)
        for t in sells
        if float(t.get("profit_loss") or 0) > 0
    ]
    loss_pnls = [
        abs(float(t.get("profit_loss") or 0))
        for t in sells
        if float(t.get("profit_loss") or 0) < 0
    ]
    avg_win = (sum(win_pnls) / len(win_pnls)) if win_pnls else None
    avg_loss = (sum(loss_pnls) / len(loss_pnls)) if loss_pnls else None
    payoff_ratio = (
        (avg_win / avg_loss)
        if avg_win is not None and avg_loss is not None and avg_loss > 0
        else None
    )
    gross_wins = sum(win_pnls) if win_pnls else None
    gross_losses = sum(loss_pnls) if loss_pnls else None
    profit_factor = (
        (gross_wins / gross_losses)
        if gross_wins is not None
        and gross_losses is not None
        and gross_wins > 0
        and gross_losses > 0
        else None
    )
    n_closed = wins + losses
    expectancy: float | None = None
    if n_closed > 0:
        if wins > 0 and losses == 0 and avg_win is not None and avg_win > 0:
            expectancy = avg_win
        elif losses > 0 and wins == 0 and avg_loss is not None and avg_loss > 0:
            expectancy = -avg_loss
        elif (
            wins > 0
            and losses > 0
            and avg_win is not None
            and avg_loss is not None
            and avg_win > 0
            and avg_loss > 0
        ):
            expectancy = (wins / n_closed) * avg_win - (losses / n_closed) * avg_loss
    win_rate = (100.0 * wins / n_closed) if n_closed > 0 else None
    first_ts = window[0].get("timestamp") if window else None
    last_ts = window[-1].get("timestamp") if window else None
    last_sell_ts = None
    last_sell_dt: datetime | None = None
    for sell in sells:
        ts = parse_trade_timestamp(sell.get("timestamp"))
        if ts is None:
            continue
        if last_sell_dt is None or ts > last_sell_dt:
            last_sell_dt = ts
            last_sell_ts = sell.get("timestamp")
    # Fee-adjusted edge for A/B: realized sell P&L minus *all* in-window fees
    # (buy+sell). net_after_sell_fees keeps sell-leg-only for summarize_trades.
    net_all = realized - fees
    return {
        "trades": len(window),
        "buys": len(buys),
        "sells": len(sells),
        "fees": fees,
        "realized_pnl": realized,
        "net_after_sell_fees": realized - sell_fees,
        "net_after_all_fees": net_all,
        "wins": wins,
        "losses": losses,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff_ratio": payoff_ratio,
        "gross_wins": gross_wins,
        "gross_losses": gross_losses,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "win_rate": win_rate,
        "loss_streak": ending_loss_streak(sells),
        "crypto_legs": crypto_legs,
        "stock_legs": len(window) - crypto_legs,
        "first": first_ts,
        "last": last_ts,
        "last_sell": last_sell_ts,
        "start_utc": start_dt.isoformat(),
        "end_utc": end.isoformat() if end is not None else None,
    }


def load_trades_jsonl(path: Path | str) -> list[dict[str, Any]]:
    """Load trades.jsonl rows (skip bad lines)."""
    p = Path(path)
    if not p.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def window_stats_from_data_dir(
    data_dir: Path | str | None,
    *,
    promote_on: bool = False,
) -> dict[str, Any] | None:
    """Summarize active window fills from ``data/trades.jsonl``, or None."""
    if data_dir is None:
        return None
    root = Path(data_dir)
    trades = load_trades_jsonl(root / "trades.jsonl")
    if not trades:
        return None
    start = active_window_start_utc(promote_on=promote_on)
    return summarize_window_trades(trades, start=start)


def format_window_stats_bit(
    stats: dict[str, Any] | None,
    *,
    include_fills: bool = True,
) -> str:
    """Short fee / fee-adjusted net / fill bit for promote A/B glance.

    Prefers ``net_after_all_fees`` (realized − all buy+sell fees) so the desk
    does not read gross sell P&L as edge. Falls back to realized − fees when
    older stats dicts omit the field. When ``include_fills`` is False, omit the
    trailing fill count (glance already shows ``N/M fills`` dual progress).
    Portfolio AI fee honesty; display only.
    """
    if not isinstance(stats, dict):
        return ""
    try:
        n = int(stats.get("trades") or 0)
        fees = float(stats.get("fees") or 0)
        realized = float(stats.get("realized_pnl") or 0)
        if stats.get("net_after_all_fees") is not None:
            net = float(stats.get("net_after_all_fees") or 0)
        else:
            net = realized - fees
    except (TypeError, ValueError):
        return ""
    if n <= 0 and fees <= 0 and realized == 0 and net == 0:
        return "0 fills" if include_fills else ""
    sign = "+" if net >= 0 else "−"
    abs_n = abs(net)
    if abs_n >= 1000:
        pnl = f"{sign}€{abs_n / 1000:.1f}k"
    else:
        pnl = f"{sign}€{abs_n:,.0f}"
    bit = f"€{fees:,.0f} fees · {pnl} net"
    if include_fills:
        bit = f"{bit} · {n} fills"
    return bit
