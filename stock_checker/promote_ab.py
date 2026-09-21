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
# Peak run (`loss_streak_max`) speaks only when it exceeds the ending run
# (xang1234 max vs ending). A hot peak warns only. Still ready for B.
# Ending win run (`win_streak`) is the speak-both-sides complement
# (portfolio AI). Same hot floor. A hot win run speaks and does not warn.
# Peak win run (`win_streak_max`) speaks only when it exceeds the ending
# run (xang1234 max vs ending). A hot peak speaks and does not warn.
# Mean loss run (`loss_streak_mean`) speaks when there are ≥2 loss runs
# (xang1234 mean vs peak). One run stays silent. A hot mean (≥2) warns only.
# Mean win run (`win_streak_mean`) is the speak-both-sides complement.
# Same ≥2-run floor. A hot mean speaks and does not warn.
# Median loss run (`loss_streak_median`) speaks when there are ≥3 loss
# runs and the median differs from the mean (xang1234 median vs mean).
# Two runs: median equals the pair mean, so it stays silent. A hot
# median (≥2) warns only. Missing keys → no bit. Not a live halt.
# Median win run (`win_streak_median`) is the speak-both-sides complement.
# Same ≥3-run floor and gap vs the mean. A hot median speaks and does
# not warn. Missing keys → no bit. Not a live halt.
# Shortest loss run (`loss_streak_min`) speaks when there are ≥2 loss
# runs and the floor is under the peak (xang1234 min vs max). Equal
# lengths stay silent. A hot floor (≥2) warns only. Missing keys → no bit.
# Shortest win run (`win_streak_min`) is the speak-both-sides complement.
# Same ≥2-run floor and min < max. A hot floor speaks and does not warn.
# Loss-run σ (`loss_streak_stdev`) speaks when there are ≥3 loss runs
# and σ ≥ 0.05 (xang1234 flip-run σ). Two runs stay silent (min vs max
# already covers that pair). Near-equal lengths stay silent. A wide σ
# (≥2) warns only. Missing keys → no bit. Not a live halt.
# Win-run σ (`win_streak_stdev`) is the speak-both-sides complement.
# Same ≥3-run floor and σ floor. A wide σ speaks and does not warn.
# Loss-run CV (`loss_streak_cv` = σ ÷ mean) scales that spread by the
# typical run (xang1234 flip-run CV). Same ≥3-run floor and 0.05 floor.
# Mean ≤ 0 stays silent. A wide CV (≥2) warns only. Missing keys → no bit.
# Win-run CV (`win_streak_cv`) is the speak-both-sides complement.
# Same floors. A wide CV speaks and does not warn.
# Exit mix (`exit_tp` / `exit_sl` / `exit_rot` / `exit_trim`) says why
# the book closed (tradermonty postmortem). Win/lose counts do not.
# Speak non-zero live reasons only. Stops + rotation + trim leading
# take-profits warns only.
# Unknown exits (`sells` − those four) sit in the sell meter but not
# in the mix (portfolio AI sample honesty). Speak `A exits unknown · N`
# when N > 0. Zero stays silent. Warn only (still ready for B).
# Exit TP share (`exit_tp` ÷ known live reasons) says how much of that
# mix is take-profit (xang1234 severity). Counts do not. Reuse win-rate
# bands: strong ≥60% · ok mid · thin <40%. Thin warns only. Unknown
# exits stay out of the share. Missing keys → fail-open.
# Exit SL share (`exit_sl` ÷ known live reasons) is the speak-both-sides
# pair (portfolio AI). TP share does not say how much of the rest is
# stops vs rotation vs trim. Same bands, inverted: hot ≥60% warns only;
# quiet <40% speaks and does not warn; mid stays unlabeled. Unknown
# exits stay out. Missing keys → fail-open.
# Exit rotation share (`exit_rot` ÷ known live reasons) is the next
# speak-both-sides slice (portfolio AI + tradermonty postmortem). Stop
# share does not say scan-chase. Same inverted bands. Hot warns only.
# Quiet speaks and does not warn. Unknown exits stay out. Fail-open.
# Exit trim share (`exit_trim` ÷ known live reasons) is the last live
# reason (portfolio AI + tradermonty A16 overweight trim). Rotation
# share does not say trim-to-cap. Same inverted bands. Hot warns only.
# Quiet speaks and does not warn. Unknown exits stay out. Fail-open.
# Exit lead names the peak live reason (xang1234 leader cluster).
# Four shares still need a compare. Unique `tp` speaks. A unique
# adverse lead, or a tie with no `tp`, warns only. Still ready for B.
# Exit euro concentration (`closes_exit_euro_conc`) is the |€| share of
# the unique top reason (portfolio AI + xang1234). Lead/offset/gap
# compare movers; conc asks if one reason owns the tape. Reuse win-rate
# bands. Adverse ≥60% warns only. TP ≥60% speaks strong. Quiet <40%.
# Exit €/count conc skew (`closes_exit_euro_count_skew_pp`): same reason
# owns count lead and € conc, but shares diverge by ≥ strong−thin pp
# (20). Euro lead handles reason disagree; this bit speaks share lie.
# Adverse warns only. Still ready for B.
# Exit € size (`closes_exit_euro_size_ratio`): avg |€|/close of the unique
# €-conc reason vs the rest. Share skew can hide large vs small closes.
# Fat ≥2× · thin ≤0.5× (reuse PROFIT_FACTOR_STRONG / inverse). Adverse
# warns only. Still ready for B.
# Exit € size n (`closes_exit_euro_size_n`): sample honesty after fat/thin.
# One fat close ≠ a size sample (portfolio AI + xang1234). Speak only when
# size ratio spoke. thin when n_lead < WINDOW_A_TARGET_SELLS. thin warns
# only. Still ready for B.
# Exit € size rest n (`closes_exit_euro_size_rest_n`): denominator sample.
# Fat/thin vs one rest close is noise (portfolio AI + xang1234). Speak only
# when size ratio spoke. thin when rest_n < WINDOW_A_TARGET_SELLS. thin
# warns only. Still ready for B.
# Exit € size sign (`closes_exit_euro_size_sign`): signed net of the fat/thin
# €-conc reason. Size uses |€|, and hot/quiet follows the reason label
# (not tp). A profitable rotation is still hot. Speak win/loss when size
# already spoke. loss warns only. win speaks and does not warn. Still ready
# for B.
# Exit € size rest sign (`closes_exit_euro_size_rest_sign`): signed net of
# the non-conc reasons when fat/thin already spoke. Size sign names the
# lead reason; the rest can still win or lose. loss warns only. win speaks
# and does not warn. Near-zero rest stays silent. Still ready for B.
# Exit € size sign clash (`closes_exit_euro_size_sign_clash`): both signs
# spoke and they differ (portfolio AI + xang1234). Same signs stay silent.
# A losing lead warns only (the fat bucket is the loser). A winning lead
# speaks and does not warn. Still ready for B.
# Exit € size clash net (`closes_exit_euro_size_sign_clash_net`): signed
# sum of the lead and the rest when the signs clash. Clash names the
# disagree. The sum says who keeps the money. Speak only when clash
# already spoke. loss warns only. win speaks and does not warn.
# A near-zero sum stays silent. Still ready for B.
# Exit € size clash keep (`closes_exit_euro_size_sign_clash_keep`): |net|
# ÷ (|lead| + |rest|) when the signs clash. Clash net is the leftover
# euros. Keep says how much of the two-sided money survives. strong
# ≥ EXPECTANCY_STRONG (0.5) speaks. thin < EXPECTANCY_THIN (0.25) warns,
# including a full cancel (net ~0). Mid stays silent. Still ready for B.
# Exit € size clash keep fees (`closes_exit_euro_size_sign_clash_keep_fees`):
# window fees ÷ a strong winning leftover. Keep is the share that survives
# the clash. This bit asks if fees eat that leftover (portfolio AI fee-burn
# on the clash, not on all realized). Speak only when keep is strong and
# clash net is a win. Missing fees fail-open. Zero fees stay silent.
# eat when fees > leftover warns. thin ≥ FEES_THIN (0.5) warns.
# comfortable < FEES_COMFORTABLE (0.25) speaks. Mid is ok. A loss leftover
# stays silent (clash net already warns). Still ready for B.
# Exit € size clash keep fees vs drag
# (`closes_exit_euro_size_sign_clash_keep_fees_vs`): leftover fee mood
# versus the window fee mood (fee drag or fees-ok). A calm leftover can
# hide a hot book. Speak only when both spoke and the moods differ.
# worse (calm leftover, hot book) warns. better speaks and does not warn.
# Same mood stays silent. Still ready for B.
# Exit € size clash keep fees vs drag gap
# (`closes_exit_euro_size_sign_clash_keep_fees_vs_gap`): hotter fees× ÷
# cooler fees× when vs-drag already spoke (portfolio AI + xang1234).
# Mood labels ≠ how far apart the multiples sit. Missing window ratio
# (fee-drag total) fail-open. wide ≥ PROFIT_FACTOR_STRONG (2×). thin
# < 1 + EXPECTANCY_THIN (1.25×). Mid stays silent. worse warns only.
# Still ready for B.
# Exit € size clash keep fees vs drag gap dir
# (`closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir`): leftover fees×
# ÷ window fees× when gap already spoke (portfolio AI + xang1234
# speak-both-sides). Undirected gap is |hot÷cool|. Dir names which side
# sits higher: above (leftover hotter) or below (book hotter). Near-equal
# (|log| < 1e-9) stays silent. worse warns only. Still ready for B.
# Exit € size clash keep fees vs drag gap dir sides
# (`closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides`): leftover
# fees× and window fees× when dir already spoke (portfolio AI + xang1234).
# Dir is leftover÷window. Sides speak both multiples so friends can audit
# without reverse-dividing. Fee-drag total fail-open. worse warns only.
# Still ready for B.
# Exit € size clash keep fees vs drag gap dir sides Δ
# (`closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta`):
# leftover fees× − window fees× when sides already spoke (portfolio AI +
# xang1234). Ratio gap is hotter÷cooler. Sides name both multiples. Δ is
# the additive spread. wide |Δ| ≥ FEES_THIN (0.5). thin |Δ| <
# FEES_COMFORTABLE (0.25). Mid stays silent. Near-zero stays silent.
# worse warns only. Still ready for B.
# Exit € size clash keep fees vs drag gap dir sides share
# (`closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share`):
# leftover% and window% of (leftover× + window×) when sides already spoke
# (portfolio AI + xang1234 €-conc share after absolute sides / Δ). Absolute
# × and additive Δ ≠ ownership of the fee-pressure story. worse warns only.
# Still ready for B.
# Exit € size clash keep fees vs drag gap dir sides share Δ
# (`closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta`):
# leftover% − window% when share already spoke (portfolio AI + xang1234).
# Share names both %; Δ is the pp spread so near-even ownership stays quiet
# while a lopsided pair speaks. wide |Δ| ≥ EXIT_CONC_SKEW_PP (20). thin
# |Δ| < half that (10). Mid silent. Near-zero silent. worse warns only.
# Still ready for B.
# Exit € size clash keep fees vs drag gap dir sides share vs Δ
# (`closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta`):
# speak when additive × Δ and share Δ disagree (portfolio AI count ≠ € +
# xang1234 severity). One lean can be mid while the other is wide or thin.
# A thin multiple gap is not a mid share, and a mid multiple gap is not a
# wide share. Same lean stays silent. Both mid stay silent. worse warns
# only. Still ready for B.
# Exit € size clash keep fees vs drag gap dir sides share vs Δ align
# (`closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align`):
# speak when additive × Δ and share Δ agree (both wide or both thin) —
# portfolio AI + xang1234 speak-both-sides confirm. Clash already covers
# mid-vs-spoke. Same lean was silent; align names the match. worse warns
# only. Still ready for B.
WINDOW_A_EXIT_CONC_SKEW_PP = (
    WINDOW_A_WIN_RATE_STRONG_PCT - WINDOW_A_WIN_RATE_THIN_PCT
)
WINDOW_A_SHARE_DELTA_THIN_PP = WINDOW_A_EXIT_CONC_SKEW_PP / 2.0
WINDOW_A_LOSS_STREAK_HOT = 2
WINDOW_A_LOSS_STREAK_MEAN_MIN_RUNS = 2
WINDOW_A_LOSS_STREAK_MEDIAN_MIN_RUNS = 3
WINDOW_A_LOSS_STREAK_MEDIAN_GAP = 0.05
WINDOW_A_LOSS_STREAK_STDEV_MIN_RUNS = 3
WINDOW_A_LOSS_STREAK_STDEV_MIN = 0.05
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


def _fmt_share_pct(share: float) -> str:
    if abs(share - round(share)) < 0.05:
        return f"{int(round(share))}%"
    return f"{share:.1f}%"


def _fmt_share_pp_signed(delta: float) -> str:
    """Signed percentage-point delta (unicode minus; portfolio AI)."""
    body = _fmt_share_pct(abs(delta)).rstrip("%") + "pp"
    if delta > 0:
        return f"+{body}"
    return f"−{body}"


def _adverse_exit_share(
    count: int, known: int, label: str
) -> tuple[float, str, str, bool]:
    """Share of known exits. hot ≥60% warns; quiet <40% speaks."""
    share = round(100.0 * count / known, 1)
    pct_s = _fmt_share_pct(share)
    prefix = f"A exits {label} share"
    if share >= WINDOW_A_WIN_RATE_STRONG_PCT:
        return share, "hot", f"{prefix} hot · {pct_s}", True
    if share < WINDOW_A_WIN_RATE_THIN_PCT:
        return share, "quiet", f"{prefix} quiet · {pct_s}", False
    return share, "", f"{prefix} · {pct_s}", False


def _exit_lead(
    n_tp: int, n_sl: int, n_rot: int, n_trim: int, known: int
) -> tuple[str, float, str, bool]:
    """Peak live reason. Unique adverse lead, or a no-tp tie, warns."""
    counts = (("tp", n_tp), ("sl", n_sl), ("rot", n_rot), ("trim", n_trim))
    top = max(n for _, n in counts)
    leaders = [name for name, n in counts if n == top]
    share = round(100.0 * top / known, 1)
    pct_s = _fmt_share_pct(share)
    if len(leaders) == 1:
        label = leaders[0]
        hot = label != "tp"
        return label, share, f"A exits lead {label} · {pct_s}", hot
    hot = "tp" not in leaders
    joined = "=".join(leaders)
    return "tie", share, f"A exits lead tie · {joined} · {pct_s}", hot


def _fmt_signed_euro(amount: float) -> str:
    abs_n = abs(amount)
    if abs_n >= 1000:
        body = f"€{abs_n / 1000:.1f}k"
    else:
        body = f"€{abs_n:,.0f}"
    if amount < 0:
        return f"−{body}"
    return f"+{body}"


def _exit_euro_lead(
    count_lead: str | None,
    pnl_tp: float,
    pnl_sl: float,
    pnl_rot: float,
    pnl_trim: float,
) -> tuple[str | None, float | None, str, bool]:
    """Unique € mover when it is not the count lead. A match stays silent."""
    amounts = (("tp", pnl_tp), ("sl", pnl_sl), ("rot", pnl_rot), ("trim", pnl_trim))
    top = max(abs(v) for _, v in amounts)
    if top < 0.5:
        return None, None, "", False
    leaders = [name for name, v in amounts if abs(abs(v) - top) < 0.05]
    if len(leaders) != 1:
        return None, None, "", False
    label = leaders[0]
    if count_lead == label:
        return None, None, "", False
    value = round(dict(amounts)[label], 2)
    hot = label != "tp"
    return label, value, f"A exits € lead {label} · {_fmt_signed_euro(value)}", hot


def _fmt_multiple(ratio: float) -> str:
    if abs(ratio - round(ratio)) < 0.05:
        return f"{int(round(ratio))}×"
    return f"{ratio:.1f}×"


def _exit_euro_offset(
    count_lead: str | None,
    pnl_tp: float,
    pnl_sl: float,
    pnl_rot: float,
    pnl_trim: float,
) -> tuple[str | None, float | None, float | None, str, bool]:
    """Runner-up € when the euro lead matches the count lead.

    The euro-lead bit stays silent on a match. A large second reason can
    still erase that lead. Speak when runner-up |P&L| is at least
    ``WINDOW_A_FEES_THIN_RATIO`` of the lead. An adverse runner-up warns.
    A take-profit runner-up speaks and does not warn. A disagree, a euro
    tie, and a small runner-up stay silent.
    """
    amounts = (("tp", pnl_tp), ("sl", pnl_sl), ("rot", pnl_rot), ("trim", pnl_trim))
    top = max(abs(v) for _, v in amounts)
    if top < 0.5:
        return None, None, None, "", False
    leaders = [name for name, v in amounts if abs(abs(v) - top) < 0.05]
    if len(leaders) != 1 or count_lead != leaders[0]:
        return None, None, None, "", False
    rest = [(name, v) for name, v in amounts if name != leaders[0]]
    second_name, second_val = max(rest, key=lambda item: abs(item[1]))
    second_abs = abs(second_val)
    if second_abs < 0.5:
        return None, None, None, "", False
    ratio = second_abs / top
    if ratio < WINDOW_A_FEES_THIN_RATIO:
        return None, None, None, "", False
    hot = second_name != "tp"
    severity = "hot" if hot else "quiet"
    bit = (
        f"A exits € offset {severity} · {second_name} "
        f"{_fmt_signed_euro(second_val)} · {_fmt_multiple(ratio)}"
    )
    return second_name, round(second_val, 2), round(ratio, 2), bit, hot



def _exit_euro_gap(
    count_lead: str | None,
    euro_lead: str | None,
    pnl_tp: float,
    pnl_sl: float,
    pnl_rot: float,
    pnl_trim: float,
) -> tuple[float | None, str | None, str, bool]:
    """€-lead multiple vs the count lead when they disagree.

    Euro-lead already names the disagree. This bit speaks how far count
    and € diverge. Speak when |€ lead| is at least
    ``WINDOW_A_PROFIT_FACTOR_STRONG_RATIO`` × |count lead €|. An adverse
    € lead warns. A take-profit € lead speaks and does not warn. Match
    (offset handles), count tie, missing leads, and a thin gap stay
    silent.
    """
    if (
        not euro_lead
        or not count_lead
        or count_lead == "tie"
        or euro_lead == count_lead
    ):
        return None, None, "", False
    amounts = {
        "tp": pnl_tp,
        "sl": pnl_sl,
        "rot": pnl_rot,
        "trim": pnl_trim,
    }
    if euro_lead not in amounts or count_lead not in amounts:
        return None, None, "", False
    euro_abs = abs(amounts[euro_lead])
    count_abs = abs(amounts[count_lead])
    if euro_abs < 0.5 or count_abs < 0.5:
        return None, None, "", False
    ratio = euro_abs / count_abs
    if ratio < WINDOW_A_PROFIT_FACTOR_STRONG_RATIO:
        return None, None, "", False
    hot = euro_lead != "tp"
    severity = "hot" if hot else "quiet"
    bit = (
        f"A exits € gap {severity} · {_fmt_multiple(ratio)} vs {count_lead}"
    )
    return round(ratio, 2), count_lead, bit, hot


def _exit_euro_conc(
    pnl_tp: float,
    pnl_sl: float,
    pnl_rot: float,
    pnl_trim: float,
) -> tuple[str | None, float | None, str, bool]:
    """Share of total |exit €| in the unique top reason.

    Lead / offset / gap compare count vs € movers. Concentration asks
    whether one reason owns most of the tape (xang1234 severity +
    portfolio AI). Reuse win-rate bands: strong/hot ≥60% · quiet <40% ·
    mid unlabeled. An adverse top at ≥60% warns only. A take-profit top
    at ≥60% speaks strong and does not warn. A euro tie and near-zero
    stay silent.
    """
    amounts = (("tp", pnl_tp), ("sl", pnl_sl), ("rot", pnl_rot), ("trim", pnl_trim))
    total = sum(abs(v) for _, v in amounts)
    if total < 0.5:
        return None, None, "", False
    top = max(abs(v) for _, v in amounts)
    leaders = [name for name, v in amounts if abs(abs(v) - top) < 0.05]
    if len(leaders) != 1:
        return None, None, "", False
    label = leaders[0]
    share = round(100.0 * top / total, 1)
    pct_s = _fmt_share_pct(share)
    if share >= WINDOW_A_WIN_RATE_STRONG_PCT:
        if label == "tp":
            return label, share, f"A exits € conc strong · {label} · {pct_s}", False
        return label, share, f"A exits € conc hot · {label} · {pct_s}", True
    if share < WINDOW_A_WIN_RATE_THIN_PCT:
        return label, share, f"A exits € conc quiet · {label} · {pct_s}", False
    return label, share, f"A exits € conc · {label} · {pct_s}", False


def _exit_euro_count_skew(
    count_lead: str | None,
    count_lead_pct: float | None,
    euro_conc: str | None,
    euro_conc_pct: float | None,
) -> tuple[float | None, str, bool]:
    """Same reason owns count and €, but the shares diverge.

    Euro lead names a reason disagree. Conc names € ownership. This bit
    speaks when the same reason leads both tapes while |€% − n%| is at
    least ``WINDOW_A_EXIT_CONC_SKEW_PP`` (strong−thin win-rate band). An
    adverse reason warns only. A take-profit skew speaks quiet. A tie,
    a disagree, and a thin gap stay silent.
    """
    if (
        not count_lead
        or count_lead == "tie"
        or not euro_conc
        or count_lead != euro_conc
        or count_lead_pct is None
        or euro_conc_pct is None
    ):
        return None, "", False
    gap = abs(float(euro_conc_pct) - float(count_lead_pct))
    if gap < WINDOW_A_EXIT_CONC_SKEW_PP:
        return None, "", False
    hot = euro_conc != "tp"
    severity = "hot" if hot else "quiet"
    n_s = _fmt_share_pct(float(count_lead_pct))
    e_s = _fmt_share_pct(float(euro_conc_pct))
    bit = f"A exits € skew {severity} · {euro_conc} · n {n_s} · € {e_s}"
    return round(gap, 1), bit, hot


def _exit_euro_size(
    euro_conc: str | None,
    n_tp: int,
    n_sl: int,
    n_rot: int,
    n_trim: int,
    pnl_tp: float,
    pnl_sl: float,
    pnl_rot: float,
    pnl_trim: float,
) -> tuple[float | None, str, bool]:
    """Avg |€|/close of the €-conc reason vs the rest.

    Share skew can hide whether that reason's closes are larger. Speak
    when avg |€| of the unique €-conc reason is at least
    ``WINDOW_A_PROFIT_FACTOR_STRONG_RATIO`` × the rest (fat) or at most
    the inverse (thin). Need ≥1 close on conc and ≥1 on the rest. An
    adverse reason warns only. A mid ratio and near-zero stay silent.
    """
    if not euro_conc or euro_conc == "tie":
        return None, "", False
    counts = {"tp": n_tp, "sl": n_sl, "rot": n_rot, "trim": n_trim}
    pnls = {"tp": pnl_tp, "sl": pnl_sl, "rot": pnl_rot, "trim": pnl_trim}
    if euro_conc not in counts:
        return None, "", False
    n_lead = counts[euro_conc]
    if n_lead < 1:
        return None, "", False
    lead_abs = abs(pnls[euro_conc])
    if lead_abs < 0.5:
        return None, "", False
    rest_n = 0
    rest_abs = 0.0
    for name in ("tp", "sl", "rot", "trim"):
        if name == euro_conc:
            continue
        rest_n += counts[name]
        rest_abs += abs(pnls[name])
    if rest_n < 1 or rest_abs < 0.5:
        return None, "", False
    avg_rest = rest_abs / rest_n
    if avg_rest < 1e-9:
        return None, "", False
    ratio = (lead_abs / n_lead) / avg_rest
    strong = WINDOW_A_PROFIT_FACTOR_STRONG_RATIO
    if ratio >= strong:
        lean = "fat"
    elif ratio <= 1.0 / strong:
        lean = "thin"
    else:
        return None, "", False
    hot = euro_conc != "tp"
    severity = "hot" if hot else "quiet"
    bit = (
        f"A exits € size {lean} {severity} · {euro_conc} · {_fmt_multiple(ratio)}"
    )
    return round(ratio, 2), bit, hot


def _exit_euro_size_n(
    euro_conc: str | None,
    size_ratio: float | None,
    n_tp: int,
    n_sl: int,
    n_rot: int,
    n_trim: int,
) -> tuple[str, int | None, str, bool]:
    """Sample honesty for fat/thin € size.

    Fat/thin from one close is noise. Speak only when ``size_ratio``
    already spoke. ``thin`` when the €-conc reason has fewer than
    ``WINDOW_A_TARGET_SELLS`` closes. ``thin`` warns only. Still ready
    for B.
    """
    if size_ratio is None or not euro_conc or euro_conc == "tie":
        return "", None, "", False
    counts = {"tp": n_tp, "sl": n_sl, "rot": n_rot, "trim": n_trim}
    if euro_conc not in counts:
        return "", None, "", False
    n_lead = int(counts[euro_conc])
    need = int(WINDOW_A_TARGET_SELLS)
    if n_lead < need:
        return (
            "thin",
            n_lead,
            f"A exits € size n thin · {euro_conc} · {n_lead} closes <{need}",
            True,
        )
    return (
        "ok",
        n_lead,
        f"A exits € size n ok · {euro_conc} · {n_lead} closes",
        False,
    )


def _exit_euro_size_rest_n(
    euro_conc: str | None,
    size_ratio: float | None,
    n_tp: int,
    n_sl: int,
    n_rot: int,
    n_trim: int,
) -> tuple[str, int | None, str, bool]:
    """Sample honesty for the rest bucket under fat/thin € size.

    Fat/thin vs one rest close is noise. Speak only when ``size_ratio``
    already spoke. ``thin`` when non-conc closes are fewer than
    ``WINDOW_A_TARGET_SELLS``. ``thin`` warns only. Still ready for B.
    """
    if size_ratio is None or not euro_conc or euro_conc == "tie":
        return "", None, "", False
    counts = {"tp": n_tp, "sl": n_sl, "rot": n_rot, "trim": n_trim}
    if euro_conc not in counts:
        return "", None, "", False
    rest_n = 0
    for name in ("tp", "sl", "rot", "trim"):
        if name == euro_conc:
            continue
        rest_n += int(counts[name])
    need = int(WINDOW_A_TARGET_SELLS)
    if rest_n < need:
        return (
            "thin",
            rest_n,
            f"A exits € size rest n thin · {rest_n} closes <{need}",
            True,
        )
    return (
        "ok",
        rest_n,
        f"A exits € size rest n ok · {rest_n} closes",
        False,
    )


def _exit_euro_size_sign(
    euro_conc: str | None,
    size_ratio: float | None,
    pnl_tp: float,
    pnl_sl: float,
    pnl_rot: float,
    pnl_trim: float,
) -> tuple[str, float | None, str, bool]:
    """Signed net of the fat/thin €-conc reason.

    Size uses |€|. Hot/quiet follows the reason label, not the money.
    A profitable rotation is still hot. Speak only when ``size_ratio``
    already spoke. ``loss`` warns only. ``win`` speaks and does not warn.
    Still ready for B.
    """
    if size_ratio is None or not euro_conc or euro_conc == "tie":
        return "", None, "", False
    pnls = {"tp": pnl_tp, "sl": pnl_sl, "rot": pnl_rot, "trim": pnl_trim}
    if euro_conc not in pnls:
        return "", None, "", False
    signed = float(pnls[euro_conc])
    if abs(signed) < 0.5:
        return "", None, "", False
    value = round(signed, 2)
    euro = _fmt_signed_euro(value)
    if signed < 0:
        return (
            "loss",
            value,
            f"A exits € size sign loss · {euro_conc} · {euro}",
            True,
        )
    return (
        "win",
        value,
        f"A exits € size sign win · {euro_conc} · {euro}",
        False,
    )


def _exit_euro_size_rest_sign(
    euro_conc: str | None,
    size_ratio: float | None,
    pnl_tp: float,
    pnl_sl: float,
    pnl_rot: float,
    pnl_trim: float,
) -> tuple[str, float | None, str, bool]:
    """Signed net of the rest bucket under fat/thin € size.

    Size sign names the €-conc reason. The other reasons can still win
    or lose. Speak only when ``size_ratio`` already spoke. ``loss`` warns
    only. ``win`` speaks and does not warn. Near-zero rest stays silent.
    Still ready for B.
    """
    if size_ratio is None or not euro_conc or euro_conc == "tie":
        return "", None, "", False
    pnls = {"tp": pnl_tp, "sl": pnl_sl, "rot": pnl_rot, "trim": pnl_trim}
    if euro_conc not in pnls:
        return "", None, "", False
    signed = 0.0
    for name, amount in pnls.items():
        if name == euro_conc:
            continue
        signed += float(amount)
    if abs(signed) < 0.5:
        return "", None, "", False
    value = round(signed, 2)
    euro = _fmt_signed_euro(value)
    if signed < 0:
        return (
            "loss",
            value,
            f"A exits € size rest sign loss · {euro}",
            True,
        )
    return (
        "win",
        value,
        f"A exits € size rest sign win · {euro}",
        False,
    )


def _exit_euro_size_sign_clash(
    lead_sign: str,
    rest_sign: str,
) -> tuple[str, str, bool]:
    """Lead and rest signed nets disagree under fat/thin € size.

    Each sign bit names one side. Speak only when both spoke and they
    differ. A losing lead warns only (the fat bucket is the loser). A
    winning lead speaks and does not warn. Same signs stay silent.
    Still ready for B.
    """
    if lead_sign not in ("win", "loss") or rest_sign not in ("win", "loss"):
        return "", "", False
    if lead_sign == rest_sign:
        return "", "", False
    bit = f"A exits € size clash · lead {lead_sign} · rest {rest_sign}"
    return "clash", bit, lead_sign == "loss"


def _exit_euro_size_sign_clash_net(
    clash: str,
    lead_pnl: float | None,
    rest_pnl: float | None,
) -> tuple[str, float | None, str, bool]:
    """Signed sum of lead and rest when size signs clash.

    Clash names the disagree. The sum says who keeps the money. Speak
    only when clash already spoke and both nets are known. ``loss``
    warns only. ``win`` speaks and does not warn. A near-zero sum stays
    silent. Still ready for B.
    """
    if clash != "clash" or lead_pnl is None or rest_pnl is None:
        return "", None, "", False
    signed = float(lead_pnl) + float(rest_pnl)
    if abs(signed) < 0.5:
        return "", None, "", False
    value = round(signed, 2)
    euro = _fmt_signed_euro(value)
    if signed < 0:
        return (
            "loss",
            value,
            f"A exits € size clash net loss · {euro}",
            True,
        )
    return (
        "win",
        value,
        f"A exits € size clash net win · {euro}",
        False,
    )


def _exit_euro_size_sign_clash_keep(
    clash: str,
    lead_pnl: float | None,
    rest_pnl: float | None,
) -> tuple[str, float | None, str, bool]:
    """Share of two-sided euros that survive a size-sign clash.

    Clash net names the leftover. Keep is |lead + rest| ÷ (|lead| + |rest|).
    Speak only when clash already spoke and both nets are known. strong
    ≥ ``WINDOW_A_EXPECTANCY_STRONG_RATIO`` speaks and does not warn. thin
    < ``WINDOW_A_EXPECTANCY_THIN_RATIO`` warns only, including a full
    cancel. Mid stays silent. Still ready for B.
    """
    if clash != "clash" or lead_pnl is None or rest_pnl is None:
        return "", None, "", False
    lead = float(lead_pnl)
    rest = float(rest_pnl)
    gross = abs(lead) + abs(rest)
    if gross < 0.5:
        return "", None, "", False
    keep = abs(lead + rest) / gross
    if keep >= WINDOW_A_EXPECTANCY_STRONG_RATIO:
        lean = "strong"
        thin = False
    elif keep < WINDOW_A_EXPECTANCY_THIN_RATIO:
        lean = "thin"
        thin = True
    else:
        return "", None, "", False
    bit = f"A exits € size clash keep {lean} · {_fmt_multiple(keep)}"
    return lean, round(keep, 2), bit, thin


def _fmt_fee_keep(ratio: float) -> str:
    """Fee multiple for a clash leftover. Small ratios keep two decimals."""
    if ratio >= 1 and abs(ratio - round(ratio)) < 0.05:
        return f"{int(round(ratio))}×"
    if ratio >= 1:
        return f"{ratio:.1f}×"
    return f"{ratio:.2f}×"


def _fmt_fee_keep_signed(delta: float) -> str:
    """Signed fee-multiple delta (unicode minus; portfolio AI speak-both-sides)."""
    mag = _fmt_fee_keep(abs(delta))
    if delta > 0:
        return f"+{mag}"
    return f"−{mag}"


def _exit_euro_size_sign_clash_keep_fees(
    keep: str,
    net_sign: str,
    lead_pnl: float | None,
    rest_pnl: float | None,
    fees: float | None,
) -> tuple[str, float | None, str, bool]:
    """Window fees versus a strong winning clash leftover.

    Keep says how much two-sided money survives. This bit asks if fees
    eat that leftover. Speak only when keep is strong and the clash net
    is a win. A loss leftover stays silent. Missing fees fail-open.
    Zero fees stay silent. ``eat`` when fees exceed the leftover warns.
    ``thin`` when fees ÷ leftover ≥ ``WINDOW_A_FEES_THIN_RATIO`` warns.
    ``comfortable`` when the ratio is under
    ``WINDOW_A_FEES_COMFORTABLE_RATIO`` speaks. Mid is ``ok``. Still
    ready for B.
    """
    if (
        keep != "strong"
        or net_sign != "win"
        or lead_pnl is None
        or rest_pnl is None
        or fees is None
    ):
        return "", None, "", False
    leftover = abs(float(lead_pnl) + float(rest_pnl))
    fee_v = float(fees)
    if leftover < 0.5 or fee_v <= 0:
        return "", None, "", False
    ratio = fee_v / leftover
    rounded = round(ratio, 2)
    mult = _fmt_fee_keep(ratio)
    if ratio > 1:
        return (
            "eat",
            rounded,
            f"A exits € size clash keep fees eat · {mult}",
            True,
        )
    if ratio >= WINDOW_A_FEES_THIN_RATIO:
        return (
            "thin",
            rounded,
            f"A exits € size clash keep fees thin · {mult}",
            True,
        )
    if ratio < WINDOW_A_FEES_COMFORTABLE_RATIO:
        return (
            "comfortable",
            rounded,
            f"A exits € size clash keep fees comfortable · {mult}",
            False,
        )
    return (
        "ok",
        rounded,
        f"A exits € size clash keep fees ok · {mult}",
        False,
    )


def _exit_euro_size_sign_clash_keep_fees_vs(
    keep_fees: str,
    fee_drag_severity: str,
    fees_ok_severity: str,
) -> tuple[str, str, str, bool]:
    """Leftover fee mood versus the window fee mood.

    Clash-keep fees is fees ÷ leftover. Fee drag and fees-ok are fees ÷
    all realized. A calm leftover can hide a hot book. A hot leftover can
    overstate a calm book. Speak only when both spoke and the moods
    differ. ``worse`` (calm leftover, hot book) warns. ``better`` speaks
    and does not warn. Same mood stays silent. Still ready for B.
    """
    if keep_fees not in ("comfortable", "ok", "thin", "eat"):
        return "", "", "", False
    if fee_drag_severity:
        window = fee_drag_severity
        window_hot = True
    elif fees_ok_severity in ("comfortable", "ok", "thin"):
        window = fees_ok_severity
        window_hot = fees_ok_severity == "thin"
    else:
        return "", "", "", False
    leftover_hot = keep_fees in ("thin", "eat")
    if leftover_hot == window_hot:
        return "", "", "", False
    if leftover_hot:
        return (
            "better",
            window,
            (
                "A exits € size clash keep fees vs drag better"
                f" · {keep_fees} · {window}"
            ),
            False,
        )
    return (
        "worse",
        window,
        (
            "A exits € size clash keep fees vs drag worse"
            f" · {keep_fees} · {window}"
        ),
        True,
    )


def _exit_euro_size_sign_clash_keep_fees_vs_gap(
    vs: str,
    keep_fees_ratio: float | None,
    fee_drag_ratio: float | None,
    fees_ok_ratio: float | None,
) -> tuple[str, float | None, str, bool]:
    """How far leftover fees× and window fees× sit apart.

    Vs-drag names the mood disagree. Gap speaks the directed multiple
    (hotter ÷ cooler). Speak only when vs already spoke and both ratios
    are > 0. Fee-drag ``total`` has no ratio → fail-open. wide ≥
    ``WINDOW_A_PROFIT_FACTOR_STRONG_RATIO``. thin <
    ``1 + WINDOW_A_EXPECTANCY_THIN_RATIO``. Mid stays silent. ``worse``
    warns only. Still ready for B.
    """
    if vs not in ("worse", "better"):
        return "", None, "", False
    if keep_fees_ratio is None or keep_fees_ratio <= 0:
        return "", None, "", False
    window_ratio: float | None = None
    if fee_drag_ratio is not None and fee_drag_ratio > 0:
        window_ratio = float(fee_drag_ratio)
    elif fees_ok_ratio is not None and fees_ok_ratio > 0:
        window_ratio = float(fees_ok_ratio)
    else:
        return "", None, "", False
    leftover = float(keep_fees_ratio)
    hot = max(leftover, window_ratio)
    cool = min(leftover, window_ratio)
    if cool < 1e-9:
        return "", None, "", False
    gap = hot / cool
    thin_floor = 1.0 + WINDOW_A_EXPECTANCY_THIN_RATIO
    if gap >= WINDOW_A_PROFIT_FACTOR_STRONG_RATIO:
        lean = "wide"
    elif gap < thin_floor:
        lean = "thin"
    else:
        return "", None, "", False
    rounded = round(gap, 2)
    bit = (
        "A exits € size clash keep fees vs drag gap "
        f"{lean} · {_fmt_fee_keep(gap)}"
    )
    return lean, rounded, bit, vs == "worse"


def _exit_euro_size_sign_clash_keep_fees_vs_gap_dir(
    gap: str,
    vs: str,
    keep_fees_ratio: float | None,
    fee_drag_ratio: float | None,
    fees_ok_ratio: float | None,
) -> tuple[str, float | None, str, bool]:
    """Directed leftover fees× ÷ window fees× when gap already spoke.

    Gap is hotter÷cooler (unsigned). Dir speaks leftover÷window so friends
    see which side sits higher. Speak only when gap is ``wide`` or
    ``thin`` and both ratios are > 0. Fee-drag ``total`` has no window
    ratio → fail-open (gap already silent). Near-equal stays silent.
    ``worse`` warns only. Still ready for B.
    """
    if gap not in ("wide", "thin"):
        return "", None, "", False
    if vs not in ("worse", "better"):
        return "", None, "", False
    if keep_fees_ratio is None or keep_fees_ratio <= 0:
        return "", None, "", False
    window_ratio: float | None = None
    if fee_drag_ratio is not None and fee_drag_ratio > 0:
        window_ratio = float(fee_drag_ratio)
    elif fees_ok_ratio is not None and fees_ok_ratio > 0:
        window_ratio = float(fees_ok_ratio)
    else:
        return "", None, "", False
    leftover = float(keep_fees_ratio)
    if window_ratio < 1e-9:
        return "", None, "", False
    directed = leftover / window_ratio
    if abs(directed - 1.0) < 1e-9:
        return "", None, "", False
    lean = "above" if directed > 1.0 else "below"
    rounded = round(directed, 2)
    bit = (
        "A exits € size clash keep fees vs drag gap dir "
        f"{lean} · {_fmt_fee_keep(directed)}"
    )
    return lean, rounded, bit, vs == "worse"


def _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides(
    gap_dir: str,
    vs: str,
    keep_fees_ratio: float | None,
    fee_drag_ratio: float | None,
    fees_ok_ratio: float | None,
) -> tuple[float | None, float | None, str, bool]:
    """Leftover fees× and window fees× when gap dir already spoke.

    Dir speaks leftover÷window. Sides speak both multiples so friends can
    audit without reverse-dividing. Speak only when dir is ``above`` or
    ``below`` and both ratios are > 0. Fee-drag ``total`` has no window
    ratio → fail-open (dir already silent). ``worse`` warns only. Still
    ready for B.
    """
    if gap_dir not in ("above", "below"):
        return None, None, "", False
    if vs not in ("worse", "better"):
        return None, None, "", False
    if keep_fees_ratio is None or keep_fees_ratio <= 0:
        return None, None, "", False
    window_ratio: float | None = None
    if fee_drag_ratio is not None and fee_drag_ratio > 0:
        window_ratio = float(fee_drag_ratio)
    elif fees_ok_ratio is not None and fees_ok_ratio > 0:
        window_ratio = float(fees_ok_ratio)
    else:
        return None, None, "", False
    leftover = float(keep_fees_ratio)
    if window_ratio < 1e-9:
        return None, None, "", False
    leftover_r = round(leftover, 2)
    window_r = round(window_ratio, 2)
    bit = (
        "A exits € size clash keep fees vs drag gap dir sides · leftover "
        f"{_fmt_fee_keep(leftover)} · window {_fmt_fee_keep(window_ratio)}"
    )
    return leftover_r, window_r, bit, vs == "worse"


def _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta(
    sides_bit: str,
    vs: str,
    leftover: float | None,
    window: float | None,
) -> tuple[str, float | None, str, bool]:
    """Additive leftover − window fees× when sides already spoke.

    Ratio gap is hotter÷cooler. Sides name both multiples. Δ speaks the
    signed spread so a huge ratio on tiny multiples does not look like a
    huge euro-multiple gap. Speak only when sides already spoke and both
    multiples are known. wide |Δ| ≥ ``WINDOW_A_FEES_THIN_RATIO``. thin
    |Δ| < ``WINDOW_A_FEES_COMFORTABLE_RATIO``. Mid stays silent.
    Near-zero stays silent. ``worse`` warns only. Still ready for B.
    """
    if not (sides_bit or "").strip():
        return "", None, "", False
    if vs not in ("worse", "better"):
        return "", None, "", False
    if leftover is None or window is None:
        return "", None, "", False
    delta = float(leftover) - float(window)
    if abs(delta) < 1e-9:
        return "", None, "", False
    mag = abs(delta)
    if mag >= WINDOW_A_FEES_THIN_RATIO:
        lean = "wide"
    elif mag < WINDOW_A_FEES_COMFORTABLE_RATIO:
        lean = "thin"
    else:
        return "", None, "", False
    rounded = round(delta, 2)
    bit = (
        "A exits € size clash keep fees vs drag gap dir sides Δ "
        f"{lean} · {_fmt_fee_keep_signed(delta)}"
    )
    return lean, rounded, bit, vs == "worse"



def _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share(
    sides_bit: str,
    vs: str,
    leftover: float | None,
    window: float | None,
) -> tuple[float | None, float | None, str, bool]:
    """Leftover% and window% of fee× sum when gap dir sides already spoke.

    Sides speak absolute fees×. Δ speaks additive spread. Share speaks
    ownership of that fee-pressure pair (portfolio AI + xang1234 €-conc
    after absolute). Speak only when sides already spoke and both
    multiples are > 0. ``worse`` warns only. Still ready for B.
    """
    if not (sides_bit or "").strip():
        return None, None, "", False
    if vs not in ("worse", "better"):
        return None, None, "", False
    if leftover is None or window is None:
        return None, None, "", False
    left = float(leftover)
    win = float(window)
    if left <= 0 or win <= 0:
        return None, None, "", False
    total = left + win
    if total < 1e-9:
        return None, None, "", False
    left_pct = round(100.0 * left / total, 1)
    win_pct = round(100.0 - left_pct, 1)
    bit = (
        "A exits € size clash keep fees vs drag gap dir sides share · "
        f"leftover {_fmt_share_pct(left_pct)} · window {_fmt_share_pct(win_pct)}"
    )
    return left_pct, win_pct, bit, vs == "worse"


def _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta(
    share_bit: str,
    vs: str,
    leftover_pct: float | None,
    window_pct: float | None,
) -> tuple[str, float | None, str, bool]:
    """Additive leftover% − window% when share already spoke.

    Share speaks ownership %. Δ speaks the pp spread so a huge absolute ×
    gap on near-even shares does not look like lopsided ownership (and
    vice versa). Speak only when share already spoke and both % known.
    wide |Δ| ≥ ``WINDOW_A_EXIT_CONC_SKEW_PP``. thin |Δ| <
    ``WINDOW_A_SHARE_DELTA_THIN_PP``. Mid stays silent. Near-zero stays
    silent. ``worse`` warns only. Still ready for B.
    """
    if not (share_bit or "").strip():
        return "", None, "", False
    if vs not in ("worse", "better"):
        return "", None, "", False
    if leftover_pct is None or window_pct is None:
        return "", None, "", False
    delta = float(leftover_pct) - float(window_pct)
    if abs(delta) < 1e-9:
        return "", None, "", False
    mag = abs(delta)
    if mag >= WINDOW_A_EXIT_CONC_SKEW_PP:
        lean = "wide"
    elif mag < WINDOW_A_SHARE_DELTA_THIN_PP:
        lean = "thin"
    else:
        return "", None, "", False
    rounded = round(delta, 1)
    bit = (
        "A exits € size clash keep fees vs drag gap dir sides share Δ "
        f"{lean} · {_fmt_share_pp_signed(delta)}"
    )
    return lean, rounded, bit, vs == "worse"


def _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta(
    sides_delta: str,
    share_delta: str,
    vs: str,
) -> tuple[str, str, bool]:
    """Speak when additive × Δ and ownership Δ disagree.

    Sides Δ is leftover× − window×. Share Δ is leftover% − window%.
    A mid multiple gap can still be a wide share, and a thin multiple
    gap can still be a mid share. Speak only when exactly one lean is
    wide or thin and the other is mid. Same lean stays silent. Both mid
    stay silent. ``worse`` warns only. Still ready for B.
    """
    if vs not in ("worse", "better"):
        return "", "", False
    x_on = sides_delta in ("wide", "thin")
    s_on = share_delta in ("wide", "thin")
    if x_on == s_on:
        return "", "", False
    x_label = sides_delta if x_on else "mid"
    s_label = share_delta if s_on else "mid"
    bit = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        f"clash · × {x_label} · % {s_label}"
    )
    return "clash", bit, vs == "worse"


def _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align(
    sides_delta: str,
    share_delta: str,
    vs: str,
) -> tuple[str, str, bool]:
    """Speak when additive × Δ and ownership Δ agree.

    Clash covers mid-vs-spoke. Align covers both wide or both thin so
    friends see count≠€ severity confirm (portfolio AI + xang1234
    speak-both-sides). Speak only when both leanish and equal. Different
    lean stays silent. One mid stays on clash. ``worse`` warns only.
    Still ready for B.
    """
    if vs not in ("worse", "better"):
        return "", "", False
    if sides_delta not in ("wide", "thin"):
        return "", "", False
    if share_delta != sides_delta:
        return "", "", False
    bit = (
        "A exits € size clash keep fees vs drag gap dir sides share vs Δ "
        f"align · {sides_delta}"
    )
    return "align", bit, vs == "worse"


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
        "closes_loss_streak_max": None,
        "closes_loss_streak_max_bit": "",
        "closes_loss_streak_max_hot": False,
        "closes_loss_streak_mean": None,
        "closes_loss_streak_runs": None,
        "closes_loss_streak_mean_bit": "",
        "closes_loss_streak_mean_hot": False,
        "closes_loss_streak_median": None,
        "closes_loss_streak_median_bit": "",
        "closes_loss_streak_median_hot": False,
        "closes_loss_streak_min": None,
        "closes_loss_streak_min_bit": "",
        "closes_loss_streak_min_hot": False,
        "closes_loss_streak_stdev": None,
        "closes_loss_streak_stdev_bit": "",
        "closes_loss_streak_stdev_hot": False,
        "closes_loss_streak_cv": None,
        "closes_loss_streak_cv_bit": "",
        "closes_loss_streak_cv_hot": False,
        "closes_win_streak": None,
        "closes_win_streak_bit": "",
        "closes_win_streak_hot": False,
        "closes_win_streak_max": None,
        "closes_win_streak_max_bit": "",
        "closes_win_streak_max_hot": False,
        "closes_win_streak_mean": None,
        "closes_win_streak_runs": None,
        "closes_win_streak_mean_bit": "",
        "closes_win_streak_mean_hot": False,
        "closes_win_streak_median": None,
        "closes_win_streak_median_bit": "",
        "closes_win_streak_median_hot": False,
        "closes_win_streak_min": None,
        "closes_win_streak_min_bit": "",
        "closes_win_streak_min_hot": False,
        "closes_win_streak_stdev": None,
        "closes_win_streak_stdev_bit": "",
        "closes_win_streak_stdev_hot": False,
        "closes_win_streak_cv": None,
        "closes_win_streak_cv_bit": "",
        "closes_win_streak_cv_hot": False,
        "closes_flat": None,
        "closes_flat_bit": "",
        "closes_flat_warn": False,
        "closes_exit_tp": None,
        "closes_exit_sl": None,
        "closes_exit_rot": None,
        "closes_exit_trim": None,
        "closes_exit_mix_bit": "",
        "closes_exit_mix_hot": False,
        "closes_exit_unknown": None,
        "closes_exit_unknown_bit": "",
        "closes_exit_unknown_warn": False,
        "closes_exit_tp_share_pct": None,
        "closes_exit_tp_share_severity": "",
        "closes_exit_tp_share_bit": "",
        "closes_exit_tp_share_thin": False,
        "closes_exit_sl_share_pct": None,
        "closes_exit_sl_share_severity": "",
        "closes_exit_sl_share_bit": "",
        "closes_exit_sl_share_hot": False,
        "closes_exit_rot_share_pct": None,
        "closes_exit_rot_share_severity": "",
        "closes_exit_rot_share_bit": "",
        "closes_exit_rot_share_hot": False,
        "closes_exit_trim_share_pct": None,
        "closes_exit_trim_share_severity": "",
        "closes_exit_trim_share_bit": "",
        "closes_exit_trim_share_hot": False,
        "closes_exit_lead": None,
        "closes_exit_lead_pct": None,
        "closes_exit_lead_bit": "",
        "closes_exit_lead_hot": False,
        "closes_exit_euro_lead": None,
        "closes_exit_euro_pnl": None,
        "closes_exit_euro_lead_bit": "",
        "closes_exit_euro_lead_hot": False,
        "closes_exit_euro_offset": None,
        "closes_exit_euro_offset_pnl": None,
        "closes_exit_euro_offset_ratio": None,
        "closes_exit_euro_offset_bit": "",
        "closes_exit_euro_offset_hot": False,
        "closes_exit_euro_gap_ratio": None,
        "closes_exit_euro_gap_vs": None,
        "closes_exit_euro_gap_bit": "",
        "closes_exit_euro_gap_hot": False,
        "closes_exit_euro_conc": None,
        "closes_exit_euro_conc_pct": None,
        "closes_exit_euro_conc_bit": "",
        "closes_exit_euro_conc_hot": False,
        "closes_exit_euro_count_skew_pp": None,
        "closes_exit_euro_count_skew_bit": "",
        "closes_exit_euro_count_skew_hot": False,
        "closes_exit_euro_size_ratio": None,
        "closes_exit_euro_size_bit": "",
        "closes_exit_euro_size_hot": False,
        "closes_exit_euro_size_n": "",
        "closes_exit_euro_size_n_count": None,
        "closes_exit_euro_size_n_bit": "",
        "closes_exit_euro_size_n_thin": False,
        "closes_exit_euro_size_rest_n": "",
        "closes_exit_euro_size_rest_n_count": None,
        "closes_exit_euro_size_rest_n_bit": "",
        "closes_exit_euro_size_rest_n_thin": False,
        "closes_exit_euro_size_sign": "",
        "closes_exit_euro_size_sign_pnl": None,
        "closes_exit_euro_size_sign_bit": "",
        "closes_exit_euro_size_sign_loss": False,
        "closes_exit_euro_size_rest_sign": "",
        "closes_exit_euro_size_rest_sign_pnl": None,
        "closes_exit_euro_size_rest_sign_bit": "",
        "closes_exit_euro_size_rest_sign_loss": False,
        "closes_exit_euro_size_sign_clash": "",
        "closes_exit_euro_size_sign_clash_bit": "",
        "closes_exit_euro_size_sign_clash_loss": False,
        "closes_exit_euro_size_sign_clash_net": "",
        "closes_exit_euro_size_sign_clash_net_pnl": None,
        "closes_exit_euro_size_sign_clash_net_bit": "",
        "closes_exit_euro_size_sign_clash_net_loss": False,
        "closes_exit_euro_size_sign_clash_keep": "",
        "closes_exit_euro_size_sign_clash_keep_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_bit": "",
        "closes_exit_euro_size_sign_clash_keep_thin": False,
        "closes_exit_euro_size_sign_clash_keep_fees": "",
        "closes_exit_euro_size_sign_clash_keep_fees_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_fees_bit": "",
        "closes_exit_euro_size_sign_clash_keep_fees_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_window": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_bit": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio": None,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn": False,
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit": "",
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn": False,
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
    closes_loss_streak_max: int | None = None
    closes_loss_streak_max_bit = ""
    closes_loss_streak_max_hot = False
    closes_loss_streak_mean: float | None = None
    closes_loss_streak_runs: int | None = None
    closes_loss_streak_mean_bit = ""
    closes_loss_streak_mean_hot = False
    closes_loss_streak_median: float | None = None
    closes_loss_streak_median_bit = ""
    closes_loss_streak_median_hot = False
    closes_loss_streak_min: int | None = None
    closes_loss_streak_min_bit = ""
    closes_loss_streak_min_hot = False
    closes_loss_streak_stdev: float | None = None
    closes_loss_streak_stdev_bit = ""
    closes_loss_streak_stdev_hot = False
    closes_loss_streak_cv: float | None = None
    closes_loss_streak_cv_bit = ""
    closes_loss_streak_cv_hot = False
    closes_win_streak: int | None = None
    closes_win_streak_bit = ""
    closes_win_streak_hot = False
    closes_win_streak_max: int | None = None
    closes_win_streak_max_bit = ""
    closes_win_streak_max_hot = False
    closes_win_streak_mean: float | None = None
    closes_win_streak_runs: int | None = None
    closes_win_streak_mean_bit = ""
    closes_win_streak_mean_hot = False
    closes_win_streak_median: float | None = None
    closes_win_streak_median_bit = ""
    closes_win_streak_median_hot = False
    closes_win_streak_min: int | None = None
    closes_win_streak_min_bit = ""
    closes_win_streak_min_hot = False
    closes_win_streak_stdev: float | None = None
    closes_win_streak_stdev_bit = ""
    closes_win_streak_stdev_hot = False
    closes_win_streak_cv: float | None = None
    closes_win_streak_cv_bit = ""
    closes_win_streak_cv_hot = False
    closes_flat: int | None = None
    closes_flat_bit = ""
    closes_flat_warn = False
    closes_exit_tp: int | None = None
    closes_exit_sl: int | None = None
    closes_exit_rot: int | None = None
    closes_exit_trim: int | None = None
    closes_exit_mix_bit = ""
    closes_exit_mix_hot = False
    closes_exit_unknown: int | None = None
    closes_exit_unknown_bit = ""
    closes_exit_unknown_warn = False
    closes_exit_tp_share_pct: float | None = None
    closes_exit_tp_share_severity = ""
    closes_exit_tp_share_bit = ""
    closes_exit_tp_share_thin = False
    closes_exit_sl_share_pct: float | None = None
    closes_exit_sl_share_severity = ""
    closes_exit_sl_share_bit = ""
    closes_exit_sl_share_hot = False
    closes_exit_rot_share_pct: float | None = None
    closes_exit_rot_share_severity = ""
    closes_exit_rot_share_bit = ""
    closes_exit_rot_share_hot = False
    closes_exit_trim_share_pct: float | None = None
    closes_exit_trim_share_severity = ""
    closes_exit_trim_share_bit = ""
    closes_exit_trim_share_hot = False
    closes_exit_lead: str | None = None
    closes_exit_lead_pct: float | None = None
    closes_exit_lead_bit = ""
    closes_exit_lead_hot = False
    closes_exit_euro_lead: str | None = None
    closes_exit_euro_pnl: float | None = None
    closes_exit_euro_lead_bit = ""
    closes_exit_euro_lead_hot = False
    closes_exit_euro_offset: str | None = None
    closes_exit_euro_offset_pnl: float | None = None
    closes_exit_euro_offset_ratio: float | None = None
    closes_exit_euro_offset_bit = ""
    closes_exit_euro_offset_hot = False
    closes_exit_euro_gap_ratio: float | None = None
    closes_exit_euro_gap_vs: str | None = None
    closes_exit_euro_gap_bit = ""
    closes_exit_euro_gap_hot = False
    closes_exit_euro_conc: str | None = None
    closes_exit_euro_conc_pct: float | None = None
    closes_exit_euro_conc_bit = ""
    closes_exit_euro_conc_hot = False
    closes_exit_euro_count_skew_pp: float | None = None
    closes_exit_euro_count_skew_bit = ""
    closes_exit_euro_count_skew_hot = False
    closes_exit_euro_size_ratio: float | None = None
    closes_exit_euro_size_bit = ""
    closes_exit_euro_size_hot = False
    closes_exit_euro_size_n = ""
    closes_exit_euro_size_n_count: int | None = None
    closes_exit_euro_size_n_bit = ""
    closes_exit_euro_size_n_thin = False
    closes_exit_euro_size_rest_n = ""
    closes_exit_euro_size_rest_n_count: int | None = None
    closes_exit_euro_size_rest_n_bit = ""
    closes_exit_euro_size_rest_n_thin = False
    closes_exit_euro_size_sign = ""
    closes_exit_euro_size_sign_pnl: float | None = None
    closes_exit_euro_size_sign_bit = ""
    closes_exit_euro_size_sign_loss = False
    closes_exit_euro_size_rest_sign = ""
    closes_exit_euro_size_rest_sign_pnl: float | None = None
    closes_exit_euro_size_rest_sign_bit = ""
    closes_exit_euro_size_rest_sign_loss = False
    closes_exit_euro_size_sign_clash = ""
    closes_exit_euro_size_sign_clash_bit = ""
    closes_exit_euro_size_sign_clash_loss = False
    closes_exit_euro_size_sign_clash_net = ""
    closes_exit_euro_size_sign_clash_net_pnl: float | None = None
    closes_exit_euro_size_sign_clash_net_bit = ""
    closes_exit_euro_size_sign_clash_net_loss = False
    closes_exit_euro_size_sign_clash_keep = ""
    closes_exit_euro_size_sign_clash_keep_ratio: float | None = None
    closes_exit_euro_size_sign_clash_keep_bit = ""
    closes_exit_euro_size_sign_clash_keep_thin = False
    closes_exit_euro_size_sign_clash_keep_fees = ""
    closes_exit_euro_size_sign_clash_keep_fees_ratio: float | None = None
    closes_exit_euro_size_sign_clash_keep_fees_bit = ""
    closes_exit_euro_size_sign_clash_keep_fees_warn = False
    closes_exit_euro_size_sign_clash_keep_fees_vs = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_window = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_bit = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_warn = False
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_ratio: float | None = None
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn = False
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio: float | None = None
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn = False
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover: float | None = (
        None
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window: float | None = (
        None
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn = False
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio: (
        float | None
    ) = None
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn = False
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover: (
        float | None
    ) = None
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window: (
        float | None
    ) = None
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn = False
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio: (
        float | None
    ) = None
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn = False
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit = ""
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn = (
        False
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align = (
        ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit = (
        ""
    )
    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn = (
        False
    )
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

    # Peak losing run vs the newest run (xang1234 max vs ending).
    # An ending streak of 0 can hide an earlier storm. Speak only when
    # max > ending. A hot peak warns only (still ready for B).
    # Missing key → fail-open (no bit).
    if (
        sides_known
        and sells > 0
        and not open_only
        and closes_loss_streak is not None
        and "loss_streak_max" in stats
    ):
        raw_max = stats.get("loss_streak_max")
        if raw_max is not None:
            try:
                n_max = int(raw_max)
            except (TypeError, ValueError):
                n_max = -1
            if n_max > closes_loss_streak:
                closes_loss_streak_max = n_max
                closes_loss_streak_max_bit = f"A loss streak max · {n_max}"
                if n_max >= WINDOW_A_LOSS_STREAK_HOT:
                    closes_loss_streak_max_hot = True

    # Typical loss-run length vs the peak (xang1234 mean vs max).
    # Speak only when ≥2 runs. One run is already the max. A hot mean
    # (≥2) warns only (still ready for B). Missing keys → fail-open.
    if (
        sides_known
        and sells > 0
        and not open_only
        and "loss_streak_mean" in stats
        and "loss_streak_runs" in stats
    ):
        raw_mean = stats.get("loss_streak_mean")
        raw_runs = stats.get("loss_streak_runs")
        if raw_mean is not None and raw_runs is not None:
            try:
                mean_v = float(raw_mean)
                n_runs = int(raw_runs)
            except (TypeError, ValueError):
                mean_v = -1.0
                n_runs = -1
            if n_runs >= WINDOW_A_LOSS_STREAK_MEAN_MIN_RUNS and mean_v >= 0:
                closes_loss_streak_mean = mean_v
                closes_loss_streak_runs = n_runs
                closes_loss_streak_mean_bit = (
                    f"A loss streak mean · {mean_v:.1f} · {n_runs} runs"
                )
                if mean_v >= WINDOW_A_LOSS_STREAK_HOT:
                    closes_loss_streak_mean_hot = True

    # Robust typical loss-run length (xang1234 median vs mean).
    # Speak only when ≥3 runs and med differs from mean. Two runs share
    # the same med and mean. A hot median (≥2) warns only (still ready
    # for B). Missing keys → fail-open.
    if (
        sides_known
        and sells > 0
        and not open_only
        and "loss_streak_median" in stats
        and "loss_streak_mean" in stats
        and "loss_streak_runs" in stats
    ):
        raw_med = stats.get("loss_streak_median")
        raw_mean_cmp = stats.get("loss_streak_mean")
        raw_med_runs = stats.get("loss_streak_runs")
        if (
            raw_med is not None
            and raw_mean_cmp is not None
            and raw_med_runs is not None
        ):
            try:
                med_v = float(raw_med)
                mean_cmp = float(raw_mean_cmp)
                n_med_runs = int(raw_med_runs)
            except (TypeError, ValueError):
                med_v = -1.0
                mean_cmp = -1.0
                n_med_runs = -1
            if (
                n_med_runs >= WINDOW_A_LOSS_STREAK_MEDIAN_MIN_RUNS
                and med_v >= 0
                and abs(med_v - mean_cmp) >= WINDOW_A_LOSS_STREAK_MEDIAN_GAP
            ):
                closes_loss_streak_median = med_v
                closes_loss_streak_median_bit = (
                    f"A loss streak med · {med_v:.1f} · {n_med_runs} runs"
                )
                if med_v >= WINDOW_A_LOSS_STREAK_HOT:
                    closes_loss_streak_median_hot = True

    # Shortest loss run vs the peak (xang1234 min vs max).
    # Speak only when ≥2 runs and min < max. Equal lengths stay silent.
    # A hot floor (≥2) warns only (still ready for B). Missing keys → fail-open.
    if (
        sides_known
        and sells > 0
        and not open_only
        and "loss_streak_min" in stats
        and "loss_streak_max" in stats
        and "loss_streak_runs" in stats
    ):
        raw_min = stats.get("loss_streak_min")
        raw_peak = stats.get("loss_streak_max")
        raw_min_runs = stats.get("loss_streak_runs")
        if raw_min is not None and raw_peak is not None and raw_min_runs is not None:
            try:
                n_min = int(raw_min)
                n_peak = int(raw_peak)
                n_min_runs = int(raw_min_runs)
            except (TypeError, ValueError):
                n_min = -1
                n_peak = -1
                n_min_runs = -1
            if (
                n_min_runs >= WINDOW_A_LOSS_STREAK_MEAN_MIN_RUNS
                and n_min >= 0
                and n_min < n_peak
            ):
                closes_loss_streak_min = n_min
                closes_loss_streak_min_bit = f"A loss streak min · {n_min}"
                if n_min >= WINDOW_A_LOSS_STREAK_HOT:
                    closes_loss_streak_min_hot = True

    # Dispersion of loss-run lengths (xang1234 flip-run σ).
    # Speak only when ≥3 runs and σ ≥ 0.05. Two runs stay silent.
    # Near-equal lengths stay silent. A wide σ (≥2) warns only
    # (still ready for B). Missing keys → fail-open.
    if (
        sides_known
        and sells > 0
        and not open_only
        and "loss_streak_stdev" in stats
        and "loss_streak_runs" in stats
    ):
        raw_stdev = stats.get("loss_streak_stdev")
        raw_stdev_runs = stats.get("loss_streak_runs")
        if raw_stdev is not None and raw_stdev_runs is not None:
            try:
                stdev_v = float(raw_stdev)
                n_stdev_runs = int(raw_stdev_runs)
            except (TypeError, ValueError):
                stdev_v = -1.0
                n_stdev_runs = -1
            if (
                n_stdev_runs >= WINDOW_A_LOSS_STREAK_STDEV_MIN_RUNS
                and stdev_v >= WINDOW_A_LOSS_STREAK_STDEV_MIN
            ):
                closes_loss_streak_stdev = stdev_v
                closes_loss_streak_stdev_bit = (
                    f"A loss streak σ · {stdev_v:.1f} · {n_stdev_runs} runs"
                )
                if stdev_v >= WINDOW_A_LOSS_STREAK_HOT:
                    closes_loss_streak_stdev_hot = True

    # Relative spread of loss-run lengths (xang1234 flip-run CV = σ / mean).
    # Speak only when ≥3 runs and CV ≥ 0.05. Two runs stay silent.
    # Mean ≤ 0 stays silent. A wide CV (≥2) warns only (still ready for B).
    # Missing keys → fail-open.
    if (
        sides_known
        and sells > 0
        and not open_only
        and "loss_streak_cv" in stats
        and "loss_streak_runs" in stats
    ):
        raw_cv = stats.get("loss_streak_cv")
        raw_cv_runs = stats.get("loss_streak_runs")
        if raw_cv is not None and raw_cv_runs is not None:
            try:
                cv_v = float(raw_cv)
                n_cv_runs = int(raw_cv_runs)
            except (TypeError, ValueError):
                cv_v = -1.0
                n_cv_runs = -1
            if (
                n_cv_runs >= WINDOW_A_LOSS_STREAK_STDEV_MIN_RUNS
                and cv_v >= WINDOW_A_LOSS_STREAK_STDEV_MIN
            ):
                closes_loss_streak_cv = cv_v
                closes_loss_streak_cv_bit = (
                    f"A loss streak CV · {cv_v:.1f} · {n_cv_runs} runs"
                )
                if cv_v >= WINDOW_A_LOSS_STREAK_HOT:
                    closes_loss_streak_cv_hot = True

    # Newest winning-close run (portfolio AI speak-both-sides).
    # Loss counts ≠ a current win run. quiet 0–1 speaks. hot ≥2 speaks.
    # A hot win run does not warn (still ready for B).
    # Missing key or None → fail-open (no bit).
    if sides_known and sells > 0 and not open_only and "win_streak" in stats:
        raw_win = stats.get("win_streak")
        if raw_win is not None:
            try:
                n_win = int(raw_win)
            except (TypeError, ValueError):
                n_win = -1
            if n_win >= 0:
                closes_win_streak = n_win
                if n_win >= WINDOW_A_LOSS_STREAK_HOT:
                    closes_win_streak_hot = True
                    closes_win_streak_bit = f"A win streak hot · {n_win}"
                else:
                    closes_win_streak_bit = f"A win streak quiet · {n_win}"

    # Peak winning run vs the newest run (xang1234 max vs ending).
    # Speak only when max > ending. A hot peak does not warn.
    # Missing key → fail-open (no bit).
    if (
        sides_known
        and sells > 0
        and not open_only
        and closes_win_streak is not None
        and "win_streak_max" in stats
    ):
        raw_win_max = stats.get("win_streak_max")
        if raw_win_max is not None:
            try:
                n_win_max = int(raw_win_max)
            except (TypeError, ValueError):
                n_win_max = -1
            if n_win_max > closes_win_streak:
                closes_win_streak_max = n_win_max
                closes_win_streak_max_bit = f"A win streak max · {n_win_max}"
                if n_win_max >= WINDOW_A_LOSS_STREAK_HOT:
                    closes_win_streak_max_hot = True

    # Typical win-run length vs the peak (xang1234 mean vs max).
    # Speak only when ≥2 runs. One run is already the max. A hot mean
    # speaks and does not warn (still ready for B). Missing keys → fail-open.
    if (
        sides_known
        and sells > 0
        and not open_only
        and "win_streak_mean" in stats
        and "win_streak_runs" in stats
    ):
        raw_win_mean = stats.get("win_streak_mean")
        raw_win_runs = stats.get("win_streak_runs")
        if raw_win_mean is not None and raw_win_runs is not None:
            try:
                mean_win = float(raw_win_mean)
                n_win_runs = int(raw_win_runs)
            except (TypeError, ValueError):
                mean_win = -1.0
                n_win_runs = -1
            if (
                n_win_runs >= WINDOW_A_LOSS_STREAK_MEAN_MIN_RUNS
                and mean_win >= 0
            ):
                closes_win_streak_mean = mean_win
                closes_win_streak_runs = n_win_runs
                closes_win_streak_mean_bit = (
                    f"A win streak mean · {mean_win:.1f} · {n_win_runs} runs"
                )
                if mean_win >= WINDOW_A_LOSS_STREAK_HOT:
                    closes_win_streak_mean_hot = True

    # Robust typical win-run length (xang1234 median vs mean).
    # Speak only when ≥3 runs and med differs from mean. Two runs share
    # the same med and mean. A hot median (≥2) speaks and does not warn
    # (still ready for B). Missing keys → fail-open.
    if (
        sides_known
        and sells > 0
        and not open_only
        and "win_streak_median" in stats
        and "win_streak_mean" in stats
        and "win_streak_runs" in stats
    ):
        raw_win_med = stats.get("win_streak_median")
        raw_win_mean_cmp = stats.get("win_streak_mean")
        raw_win_med_runs = stats.get("win_streak_runs")
        if (
            raw_win_med is not None
            and raw_win_mean_cmp is not None
            and raw_win_med_runs is not None
        ):
            try:
                med_win = float(raw_win_med)
                mean_win_cmp = float(raw_win_mean_cmp)
                n_win_med_runs = int(raw_win_med_runs)
            except (TypeError, ValueError):
                med_win = -1.0
                mean_win_cmp = -1.0
                n_win_med_runs = -1
            if (
                n_win_med_runs >= WINDOW_A_LOSS_STREAK_MEDIAN_MIN_RUNS
                and med_win >= 0
                and abs(med_win - mean_win_cmp)
                >= WINDOW_A_LOSS_STREAK_MEDIAN_GAP
            ):
                closes_win_streak_median = med_win
                closes_win_streak_median_bit = (
                    f"A win streak med · {med_win:.1f} · {n_win_med_runs} runs"
                )
                if med_win >= WINDOW_A_LOSS_STREAK_HOT:
                    closes_win_streak_median_hot = True

    # Shortest win run vs the peak (xang1234 min vs max).
    # Speak only when ≥2 runs and min < max. Equal lengths stay silent.
    # A hot floor (≥2) speaks and does not warn (still ready for B).
    # Missing keys → fail-open.
    if (
        sides_known
        and sells > 0
        and not open_only
        and "win_streak_min" in stats
        and "win_streak_max" in stats
        and "win_streak_runs" in stats
    ):
        raw_win_min = stats.get("win_streak_min")
        raw_win_peak = stats.get("win_streak_max")
        raw_win_min_runs = stats.get("win_streak_runs")
        if (
            raw_win_min is not None
            and raw_win_peak is not None
            and raw_win_min_runs is not None
        ):
            try:
                n_win_min = int(raw_win_min)
                n_win_peak = int(raw_win_peak)
                n_win_min_runs = int(raw_win_min_runs)
            except (TypeError, ValueError):
                n_win_min = -1
                n_win_peak = -1
                n_win_min_runs = -1
            if (
                n_win_min_runs >= WINDOW_A_LOSS_STREAK_MEAN_MIN_RUNS
                and n_win_min >= 0
                and n_win_min < n_win_peak
            ):
                closes_win_streak_min = n_win_min
                closes_win_streak_min_bit = f"A win streak min · {n_win_min}"
                if n_win_min >= WINDOW_A_LOSS_STREAK_HOT:
                    closes_win_streak_min_hot = True

    # Dispersion of win-run lengths (xang1234 flip-run σ).
    # Speak only when ≥3 runs and σ ≥ 0.05. Two runs stay silent.
    # Near-equal lengths stay silent. A wide σ (≥2) speaks and does
    # not warn (still ready for B). Missing keys → fail-open.
    if (
        sides_known
        and sells > 0
        and not open_only
        and "win_streak_stdev" in stats
        and "win_streak_runs" in stats
    ):
        raw_win_stdev = stats.get("win_streak_stdev")
        raw_win_stdev_runs = stats.get("win_streak_runs")
        if raw_win_stdev is not None and raw_win_stdev_runs is not None:
            try:
                stdev_win = float(raw_win_stdev)
                n_win_stdev_runs = int(raw_win_stdev_runs)
            except (TypeError, ValueError):
                stdev_win = -1.0
                n_win_stdev_runs = -1
            if (
                n_win_stdev_runs >= WINDOW_A_LOSS_STREAK_STDEV_MIN_RUNS
                and stdev_win >= WINDOW_A_LOSS_STREAK_STDEV_MIN
            ):
                closes_win_streak_stdev = stdev_win
                closes_win_streak_stdev_bit = (
                    f"A win streak σ · {stdev_win:.1f} · {n_win_stdev_runs} runs"
                )
                if stdev_win >= WINDOW_A_LOSS_STREAK_HOT:
                    closes_win_streak_stdev_hot = True

    # Relative spread of win-run lengths (xang1234 flip-run CV = σ / mean).
    # Speak only when ≥3 runs and CV ≥ 0.05. Two runs stay silent.
    # Mean ≤ 0 stays silent. A wide CV (≥2) speaks and does not warn
    # (still ready for B). Missing keys → fail-open.
    if (
        sides_known
        and sells > 0
        and not open_only
        and "win_streak_cv" in stats
        and "win_streak_runs" in stats
    ):
        raw_win_cv = stats.get("win_streak_cv")
        raw_win_cv_runs = stats.get("win_streak_runs")
        if raw_win_cv is not None and raw_win_cv_runs is not None:
            try:
                cv_win = float(raw_win_cv)
                n_win_cv_runs = int(raw_win_cv_runs)
            except (TypeError, ValueError):
                cv_win = -1.0
                n_win_cv_runs = -1
            if (
                n_win_cv_runs >= WINDOW_A_LOSS_STREAK_STDEV_MIN_RUNS
                and cv_win >= WINDOW_A_LOSS_STREAK_STDEV_MIN
            ):
                closes_win_streak_cv = cv_win
                closes_win_streak_cv_bit = (
                    f"A win streak CV · {cv_win:.1f} · {n_win_cv_runs} runs"
                )
                if cv_win >= WINDOW_A_LOSS_STREAK_HOT:
                    closes_win_streak_cv_hot = True

    # Zero-P&L sells sit in the N/3 sell meter but not in WR or Kelly
    # (portfolio AI sample honesty). Speak when any flat close exists.
    # Warn only (still ready for B). Zero stays silent. Missing key → fail-open.
    if sides_known and sells > 0 and not open_only and "flat_closes" in stats:
        raw_flat = stats.get("flat_closes")
        if raw_flat is not None:
            try:
                n_flat = int(raw_flat)
            except (TypeError, ValueError):
                n_flat = -1
            if n_flat > 0:
                closes_flat = n_flat
                closes_flat_bit = f"A flats · {n_flat}"
                closes_flat_warn = True

    # Why the book closed (tradermonty postmortem). Win/lose counts do not
    # say take-profit vs stop vs rotation vs trim. Speak non-zero live
    # reasons. Stops + rot + trim leading take-profits warns only.
    # Sells with no live reason speak `A exits unknown · N` (portfolio AI
    # sample honesty). Zero unknown stays silent. Warn only (still ready
    # for B). Missing keys → fail-open.
    if (
        sides_known
        and sells > 0
        and not open_only
        and "exit_tp" in stats
        and "exit_sl" in stats
        and "exit_rot" in stats
        and "exit_trim" in stats
    ):
        raw_tp = stats.get("exit_tp")
        raw_sl = stats.get("exit_sl")
        raw_rot = stats.get("exit_rot")
        raw_trim = stats.get("exit_trim")
        if None not in (raw_tp, raw_sl, raw_rot, raw_trim):
            try:
                n_tp = int(raw_tp)
                n_sl = int(raw_sl)
                n_rot = int(raw_rot)
                n_trim = int(raw_trim)
            except (TypeError, ValueError):
                n_tp = n_sl = n_rot = n_trim = -1
            known = n_tp + n_sl + n_rot + n_trim
            if min(n_tp, n_sl, n_rot, n_trim) >= 0:
                n_unknown = sells - known
                if known > 0:
                    closes_exit_tp = n_tp
                    closes_exit_sl = n_sl
                    closes_exit_rot = n_rot
                    closes_exit_trim = n_trim
                    parts = [
                        f"{name} {n}"
                        for name, n in (
                            ("tp", n_tp),
                            ("sl", n_sl),
                            ("rot", n_rot),
                            ("trim", n_trim),
                        )
                        if n
                    ]
                    closes_exit_mix_bit = "A exits " + " · ".join(parts)
                    if (n_sl + n_rot + n_trim) > n_tp:
                        closes_exit_mix_hot = True
                    # Take-profit share of known live reasons (xang1234
                    # severity). Counts do not say the slice. Unknown
                    # exits stay out. Thin <40% warns only.
                    share = round(100.0 * n_tp / known, 1)
                    closes_exit_tp_share_pct = share
                    pct_s = (
                        f"{int(round(share))}%"
                        if abs(share - round(share)) < 0.05
                        else f"{share:.1f}%"
                    )
                    if share < WINDOW_A_WIN_RATE_THIN_PCT:
                        closes_exit_tp_share_severity = "thin"
                        closes_exit_tp_share_thin = True
                        closes_exit_tp_share_bit = (
                            f"A exits tp share thin · {pct_s}"
                        )
                    elif share >= WINDOW_A_WIN_RATE_STRONG_PCT:
                        closes_exit_tp_share_severity = "strong"
                        closes_exit_tp_share_bit = (
                            f"A exits tp share strong · {pct_s}"
                        )
                    else:
                        closes_exit_tp_share_bit = f"A exits tp share · {pct_s}"
                    # Stop and rotation shares of the same known set
                    # (portfolio AI speak-both-sides). A stop problem is
                    # not a scan-chase problem. hot ≥60% warns only.
                    # quiet <40% speaks and does not warn. Unknown stays out.
                    (
                        closes_exit_sl_share_pct,
                        closes_exit_sl_share_severity,
                        closes_exit_sl_share_bit,
                        closes_exit_sl_share_hot,
                    ) = _adverse_exit_share(n_sl, known, "sl")
                    (
                        closes_exit_rot_share_pct,
                        closes_exit_rot_share_severity,
                        closes_exit_rot_share_bit,
                        closes_exit_rot_share_hot,
                    ) = _adverse_exit_share(n_rot, known, "rot")
                    # Trim share of the same known set (portfolio AI +
                    # tradermonty A16). Rotation is not overweight trim.
                    # hot ≥60% warns only. quiet <40% speaks and does not
                    # warn. Unknown stays out.
                    (
                        closes_exit_trim_share_pct,
                        closes_exit_trim_share_severity,
                        closes_exit_trim_share_bit,
                        closes_exit_trim_share_hot,
                    ) = _adverse_exit_share(n_trim, known, "trim")
                    # Peak reason (xang1234 leader). Four shares still
                    # need a compare. Unique tp speaks. Unique adverse
                    # lead, or a tie with no tp, warns only.
                    (
                        closes_exit_lead,
                        closes_exit_lead_pct,
                        closes_exit_lead_bit,
                        closes_exit_lead_hot,
                    ) = _exit_lead(n_tp, n_sl, n_rot, n_trim, known)
                    # Count lead ≠ euro lead (portfolio AI). Speak only when
                    # the largest |P&L| reason is not the count lead. A match,
                    # a euro tie, and near-zero stay silent. Adverse € lead
                    # warns only. Missing keys fail-open.
                    euro_keys = (
                        "exit_pnl_tp",
                        "exit_pnl_sl",
                        "exit_pnl_rot",
                        "exit_pnl_trim",
                    )
                    if all(k in stats for k in euro_keys):
                        raws = [stats.get(k) for k in euro_keys]
                        if None not in raws:
                            try:
                                euros = tuple(float(v) for v in raws)
                            except (TypeError, ValueError):
                                euros = None
                            if euros is not None:
                                (
                                    closes_exit_euro_lead,
                                    closes_exit_euro_pnl,
                                    closes_exit_euro_lead_bit,
                                    closes_exit_euro_lead_hot,
                                ) = _exit_euro_lead(closes_exit_lead, *euros)
                                (
                                    closes_exit_euro_offset,
                                    closes_exit_euro_offset_pnl,
                                    closes_exit_euro_offset_ratio,
                                    closes_exit_euro_offset_bit,
                                    closes_exit_euro_offset_hot,
                                ) = _exit_euro_offset(closes_exit_lead, *euros)
                                (
                                    closes_exit_euro_gap_ratio,
                                    closes_exit_euro_gap_vs,
                                    closes_exit_euro_gap_bit,
                                    closes_exit_euro_gap_hot,
                                ) = _exit_euro_gap(
                                    closes_exit_lead,
                                    closes_exit_euro_lead,
                                    *euros,
                                )
                                (
                                    closes_exit_euro_conc,
                                    closes_exit_euro_conc_pct,
                                    closes_exit_euro_conc_bit,
                                    closes_exit_euro_conc_hot,
                                ) = _exit_euro_conc(*euros)
                                (
                                    closes_exit_euro_count_skew_pp,
                                    closes_exit_euro_count_skew_bit,
                                    closes_exit_euro_count_skew_hot,
                                ) = _exit_euro_count_skew(
                                    closes_exit_lead,
                                    closes_exit_lead_pct,
                                    closes_exit_euro_conc,
                                    closes_exit_euro_conc_pct,
                                )
                                (
                                    closes_exit_euro_size_ratio,
                                    closes_exit_euro_size_bit,
                                    closes_exit_euro_size_hot,
                                ) = _exit_euro_size(
                                    closes_exit_euro_conc,
                                    n_tp,
                                    n_sl,
                                    n_rot,
                                    n_trim,
                                    *euros,
                                )
                                (
                                    closes_exit_euro_size_n,
                                    closes_exit_euro_size_n_count,
                                    closes_exit_euro_size_n_bit,
                                    closes_exit_euro_size_n_thin,
                                ) = _exit_euro_size_n(
                                    closes_exit_euro_conc,
                                    closes_exit_euro_size_ratio,
                                    n_tp,
                                    n_sl,
                                    n_rot,
                                    n_trim,
                                )
                                (
                                    closes_exit_euro_size_rest_n,
                                    closes_exit_euro_size_rest_n_count,
                                    closes_exit_euro_size_rest_n_bit,
                                    closes_exit_euro_size_rest_n_thin,
                                ) = _exit_euro_size_rest_n(
                                    closes_exit_euro_conc,
                                    closes_exit_euro_size_ratio,
                                    n_tp,
                                    n_sl,
                                    n_rot,
                                    n_trim,
                                )
                                (
                                    closes_exit_euro_size_sign,
                                    closes_exit_euro_size_sign_pnl,
                                    closes_exit_euro_size_sign_bit,
                                    closes_exit_euro_size_sign_loss,
                                ) = _exit_euro_size_sign(
                                    closes_exit_euro_conc,
                                    closes_exit_euro_size_ratio,
                                    *euros,
                                )
                                (
                                    closes_exit_euro_size_rest_sign,
                                    closes_exit_euro_size_rest_sign_pnl,
                                    closes_exit_euro_size_rest_sign_bit,
                                    closes_exit_euro_size_rest_sign_loss,
                                ) = _exit_euro_size_rest_sign(
                                    closes_exit_euro_conc,
                                    closes_exit_euro_size_ratio,
                                    *euros,
                                )
                                (
                                    closes_exit_euro_size_sign_clash,
                                    closes_exit_euro_size_sign_clash_bit,
                                    closes_exit_euro_size_sign_clash_loss,
                                ) = _exit_euro_size_sign_clash(
                                    closes_exit_euro_size_sign,
                                    closes_exit_euro_size_rest_sign,
                                )
                                (
                                    closes_exit_euro_size_sign_clash_net,
                                    closes_exit_euro_size_sign_clash_net_pnl,
                                    closes_exit_euro_size_sign_clash_net_bit,
                                    closes_exit_euro_size_sign_clash_net_loss,
                                ) = _exit_euro_size_sign_clash_net(
                                    closes_exit_euro_size_sign_clash,
                                    closes_exit_euro_size_sign_pnl,
                                    closes_exit_euro_size_rest_sign_pnl,
                                )
                                (
                                    closes_exit_euro_size_sign_clash_keep,
                                    closes_exit_euro_size_sign_clash_keep_ratio,
                                    closes_exit_euro_size_sign_clash_keep_bit,
                                    closes_exit_euro_size_sign_clash_keep_thin,
                                ) = _exit_euro_size_sign_clash_keep(
                                    closes_exit_euro_size_sign_clash,
                                    closes_exit_euro_size_sign_pnl,
                                    closes_exit_euro_size_rest_sign_pnl,
                                )
                                keep_fees = None
                                if "fees" in stats:
                                    try:
                                        keep_fees = float(stats.get("fees") or 0)
                                    except (TypeError, ValueError):
                                        keep_fees = None
                                (
                                    closes_exit_euro_size_sign_clash_keep_fees,
                                    closes_exit_euro_size_sign_clash_keep_fees_ratio,
                                    closes_exit_euro_size_sign_clash_keep_fees_bit,
                                    closes_exit_euro_size_sign_clash_keep_fees_warn,
                                ) = _exit_euro_size_sign_clash_keep_fees(
                                    closes_exit_euro_size_sign_clash_keep,
                                    closes_exit_euro_size_sign_clash_net,
                                    closes_exit_euro_size_sign_pnl,
                                    closes_exit_euro_size_rest_sign_pnl,
                                    keep_fees,
                                )
                                (
                                    closes_exit_euro_size_sign_clash_keep_fees_vs,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_window,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_bit,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_warn,
                                ) = _exit_euro_size_sign_clash_keep_fees_vs(
                                    closes_exit_euro_size_sign_clash_keep_fees,
                                    fee_drag_severity,
                                    fees_ok_severity,
                                )
                                (
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_ratio,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn,
                                ) = _exit_euro_size_sign_clash_keep_fees_vs_gap(
                                    closes_exit_euro_size_sign_clash_keep_fees_vs,
                                    closes_exit_euro_size_sign_clash_keep_fees_ratio,
                                    fee_drag_ratio,
                                    fees_ok_ratio,
                                )
                                (
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn,
                                ) = _exit_euro_size_sign_clash_keep_fees_vs_gap_dir(
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs,
                                    closes_exit_euro_size_sign_clash_keep_fees_ratio,
                                    fee_drag_ratio,
                                    fees_ok_ratio,
                                )
                                (
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn,
                                ) = _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides(
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs,
                                    closes_exit_euro_size_sign_clash_keep_fees_ratio,
                                    fee_drag_ratio,
                                    fees_ok_ratio,
                                )
                                (
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn,
                                ) = _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta(
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window,
                                )
                                (
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn,
                                ) = _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share(
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window,
                                )
                                (
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn,
                                ) = _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta(
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window,
                                )
                                (
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn,
                                ) = _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta(
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs,
                                )
                                (
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn,
                                ) = _exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align(
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta,
                                    closes_exit_euro_size_sign_clash_keep_fees_vs,
                                )
                if n_unknown > 0:
                    closes_exit_unknown = n_unknown
                    closes_exit_unknown_bit = f"A exits unknown · {n_unknown}"
                    closes_exit_unknown_warn = True

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
        "closes_loss_streak_max": closes_loss_streak_max,
        "closes_loss_streak_max_bit": closes_loss_streak_max_bit,
        "closes_loss_streak_max_hot": closes_loss_streak_max_hot,
        "closes_loss_streak_mean": closes_loss_streak_mean,
        "closes_loss_streak_runs": closes_loss_streak_runs,
        "closes_loss_streak_mean_bit": closes_loss_streak_mean_bit,
        "closes_loss_streak_mean_hot": closes_loss_streak_mean_hot,
        "closes_loss_streak_median": closes_loss_streak_median,
        "closes_loss_streak_median_bit": closes_loss_streak_median_bit,
        "closes_loss_streak_median_hot": closes_loss_streak_median_hot,
        "closes_loss_streak_min": closes_loss_streak_min,
        "closes_loss_streak_min_bit": closes_loss_streak_min_bit,
        "closes_loss_streak_min_hot": closes_loss_streak_min_hot,
        "closes_loss_streak_stdev": closes_loss_streak_stdev,
        "closes_loss_streak_stdev_bit": closes_loss_streak_stdev_bit,
        "closes_loss_streak_stdev_hot": closes_loss_streak_stdev_hot,
        "closes_loss_streak_cv": closes_loss_streak_cv,
        "closes_loss_streak_cv_bit": closes_loss_streak_cv_bit,
        "closes_loss_streak_cv_hot": closes_loss_streak_cv_hot,
        "closes_win_streak": closes_win_streak,
        "closes_win_streak_bit": closes_win_streak_bit,
        "closes_win_streak_hot": closes_win_streak_hot,
        "closes_win_streak_max": closes_win_streak_max,
        "closes_win_streak_max_bit": closes_win_streak_max_bit,
        "closes_win_streak_max_hot": closes_win_streak_max_hot,
        "closes_win_streak_mean": closes_win_streak_mean,
        "closes_win_streak_runs": closes_win_streak_runs,
        "closes_win_streak_mean_bit": closes_win_streak_mean_bit,
        "closes_win_streak_mean_hot": closes_win_streak_mean_hot,
        "closes_win_streak_median": closes_win_streak_median,
        "closes_win_streak_median_bit": closes_win_streak_median_bit,
        "closes_win_streak_median_hot": closes_win_streak_median_hot,
        "closes_win_streak_min": closes_win_streak_min,
        "closes_win_streak_min_bit": closes_win_streak_min_bit,
        "closes_win_streak_min_hot": closes_win_streak_min_hot,
        "closes_win_streak_stdev": closes_win_streak_stdev,
        "closes_win_streak_stdev_bit": closes_win_streak_stdev_bit,
        "closes_win_streak_stdev_hot": closes_win_streak_stdev_hot,
        "closes_win_streak_cv": closes_win_streak_cv,
        "closes_win_streak_cv_bit": closes_win_streak_cv_bit,
        "closes_win_streak_cv_hot": closes_win_streak_cv_hot,
        "closes_flat": closes_flat,
        "closes_flat_bit": closes_flat_bit,
        "closes_flat_warn": closes_flat_warn,
        "closes_exit_tp": closes_exit_tp,
        "closes_exit_sl": closes_exit_sl,
        "closes_exit_rot": closes_exit_rot,
        "closes_exit_trim": closes_exit_trim,
        "closes_exit_mix_bit": closes_exit_mix_bit,
        "closes_exit_mix_hot": closes_exit_mix_hot,
        "closes_exit_unknown": closes_exit_unknown,
        "closes_exit_unknown_bit": closes_exit_unknown_bit,
        "closes_exit_unknown_warn": closes_exit_unknown_warn,
        "closes_exit_tp_share_pct": closes_exit_tp_share_pct,
        "closes_exit_tp_share_severity": closes_exit_tp_share_severity,
        "closes_exit_tp_share_bit": closes_exit_tp_share_bit,
        "closes_exit_tp_share_thin": closes_exit_tp_share_thin,
        "closes_exit_sl_share_pct": closes_exit_sl_share_pct,
        "closes_exit_sl_share_severity": closes_exit_sl_share_severity,
        "closes_exit_sl_share_bit": closes_exit_sl_share_bit,
        "closes_exit_sl_share_hot": closes_exit_sl_share_hot,
        "closes_exit_rot_share_pct": closes_exit_rot_share_pct,
        "closes_exit_rot_share_severity": closes_exit_rot_share_severity,
        "closes_exit_rot_share_bit": closes_exit_rot_share_bit,
        "closes_exit_rot_share_hot": closes_exit_rot_share_hot,
        "closes_exit_trim_share_pct": closes_exit_trim_share_pct,
        "closes_exit_trim_share_severity": closes_exit_trim_share_severity,
        "closes_exit_trim_share_bit": closes_exit_trim_share_bit,
        "closes_exit_trim_share_hot": closes_exit_trim_share_hot,
        "closes_exit_lead": closes_exit_lead,
        "closes_exit_lead_pct": closes_exit_lead_pct,
        "closes_exit_lead_bit": closes_exit_lead_bit,
        "closes_exit_lead_hot": closes_exit_lead_hot,
        "closes_exit_euro_lead": closes_exit_euro_lead,
        "closes_exit_euro_pnl": closes_exit_euro_pnl,
        "closes_exit_euro_lead_bit": closes_exit_euro_lead_bit,
        "closes_exit_euro_lead_hot": closes_exit_euro_lead_hot,
        "closes_exit_euro_offset": closes_exit_euro_offset,
        "closes_exit_euro_offset_pnl": closes_exit_euro_offset_pnl,
        "closes_exit_euro_offset_ratio": closes_exit_euro_offset_ratio,
        "closes_exit_euro_offset_bit": closes_exit_euro_offset_bit,
        "closes_exit_euro_offset_hot": closes_exit_euro_offset_hot,
        "closes_exit_euro_gap_ratio": closes_exit_euro_gap_ratio,
        "closes_exit_euro_gap_vs": closes_exit_euro_gap_vs,
        "closes_exit_euro_gap_bit": closes_exit_euro_gap_bit,
        "closes_exit_euro_gap_hot": closes_exit_euro_gap_hot,
        "closes_exit_euro_conc": closes_exit_euro_conc,
        "closes_exit_euro_conc_pct": closes_exit_euro_conc_pct,
        "closes_exit_euro_conc_bit": closes_exit_euro_conc_bit,
        "closes_exit_euro_conc_hot": closes_exit_euro_conc_hot,
        "closes_exit_euro_count_skew_pp": closes_exit_euro_count_skew_pp,
        "closes_exit_euro_count_skew_bit": closes_exit_euro_count_skew_bit,
        "closes_exit_euro_count_skew_hot": closes_exit_euro_count_skew_hot,
        "closes_exit_euro_size_ratio": closes_exit_euro_size_ratio,
        "closes_exit_euro_size_bit": closes_exit_euro_size_bit,
        "closes_exit_euro_size_hot": closes_exit_euro_size_hot,
        "closes_exit_euro_size_n": closes_exit_euro_size_n,
        "closes_exit_euro_size_n_count": closes_exit_euro_size_n_count,
        "closes_exit_euro_size_n_bit": closes_exit_euro_size_n_bit,
        "closes_exit_euro_size_n_thin": closes_exit_euro_size_n_thin,
        "closes_exit_euro_size_rest_n": closes_exit_euro_size_rest_n,
        "closes_exit_euro_size_rest_n_count": closes_exit_euro_size_rest_n_count,
        "closes_exit_euro_size_rest_n_bit": closes_exit_euro_size_rest_n_bit,
        "closes_exit_euro_size_rest_n_thin": closes_exit_euro_size_rest_n_thin,
        "closes_exit_euro_size_sign": closes_exit_euro_size_sign,
        "closes_exit_euro_size_sign_pnl": closes_exit_euro_size_sign_pnl,
        "closes_exit_euro_size_sign_bit": closes_exit_euro_size_sign_bit,
        "closes_exit_euro_size_sign_loss": closes_exit_euro_size_sign_loss,
        "closes_exit_euro_size_rest_sign": closes_exit_euro_size_rest_sign,
        "closes_exit_euro_size_rest_sign_pnl": closes_exit_euro_size_rest_sign_pnl,
        "closes_exit_euro_size_rest_sign_bit": closes_exit_euro_size_rest_sign_bit,
        "closes_exit_euro_size_rest_sign_loss": (
            closes_exit_euro_size_rest_sign_loss
        ),
        "closes_exit_euro_size_sign_clash": closes_exit_euro_size_sign_clash,
        "closes_exit_euro_size_sign_clash_bit": (
            closes_exit_euro_size_sign_clash_bit
        ),
        "closes_exit_euro_size_sign_clash_loss": (
            closes_exit_euro_size_sign_clash_loss
        ),
        "closes_exit_euro_size_sign_clash_net": (
            closes_exit_euro_size_sign_clash_net
        ),
        "closes_exit_euro_size_sign_clash_net_pnl": (
            closes_exit_euro_size_sign_clash_net_pnl
        ),
        "closes_exit_euro_size_sign_clash_net_bit": (
            closes_exit_euro_size_sign_clash_net_bit
        ),
        "closes_exit_euro_size_sign_clash_net_loss": (
            closes_exit_euro_size_sign_clash_net_loss
        ),
        "closes_exit_euro_size_sign_clash_keep": (
            closes_exit_euro_size_sign_clash_keep
        ),
        "closes_exit_euro_size_sign_clash_keep_ratio": (
            closes_exit_euro_size_sign_clash_keep_ratio
        ),
        "closes_exit_euro_size_sign_clash_keep_bit": (
            closes_exit_euro_size_sign_clash_keep_bit
        ),
        "closes_exit_euro_size_sign_clash_keep_thin": (
            closes_exit_euro_size_sign_clash_keep_thin
        ),
        "closes_exit_euro_size_sign_clash_keep_fees": (
            closes_exit_euro_size_sign_clash_keep_fees
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_ratio": (
            closes_exit_euro_size_sign_clash_keep_fees_ratio
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_bit": (
            closes_exit_euro_size_sign_clash_keep_fees_bit
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_warn
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs": (
            closes_exit_euro_size_sign_clash_keep_fees_vs
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_window": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_window
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_bit": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_bit
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_warn
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_ratio": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_ratio
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit
        ),
        "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn": (
            closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn
        ),
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


def format_window_a_closes_loss_streak_max_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A peak loss-streak bit (max > ending; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_loss_streak_max_bit") or "").strip()
    return bit


def format_window_a_closes_loss_streak_mean_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A mean loss-streak bit (≥2 runs; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_loss_streak_mean_bit") or "").strip()
    return bit


def format_window_a_closes_loss_streak_median_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A median loss-streak bit (≥3 runs, med ≠ mean; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_loss_streak_median_bit") or "").strip()
    return bit


def format_window_a_closes_loss_streak_min_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A min loss-streak bit (≥2 runs, min < max; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_loss_streak_min_bit") or "").strip()
    return bit


def format_window_a_closes_loss_streak_stdev_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A loss-streak σ bit (≥3 runs, σ ≥ 0.05; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_loss_streak_stdev_bit") or "").strip()
    return bit


def format_window_a_closes_loss_streak_cv_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A loss-streak CV bit (≥3 runs, CV ≥ 0.05; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_loss_streak_cv_bit") or "").strip()
    return bit


def format_window_a_closes_win_streak_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A ending win-streak bit (display only; hot does not warn)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_win_streak_bit") or "").strip()
    return bit


def format_window_a_closes_win_streak_max_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A peak win-streak bit (max > ending; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_win_streak_max_bit") or "").strip()
    return bit


def format_window_a_closes_win_streak_mean_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A mean win-streak bit (≥2 runs; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_win_streak_mean_bit") or "").strip()
    return bit


def format_window_a_closes_win_streak_median_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A median win-streak bit (≥3 runs, med ≠ mean; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_win_streak_median_bit") or "").strip()
    return bit


def format_window_a_closes_win_streak_min_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A min win-streak bit (≥2 runs, min < max; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_win_streak_min_bit") or "").strip()
    return bit


def format_window_a_closes_win_streak_stdev_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A win-streak σ bit (≥3 runs, σ ≥ 0.05; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_win_streak_stdev_bit") or "").strip()
    return bit


def format_window_a_closes_win_streak_cv_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A win-streak CV bit (≥3 runs, CV ≥ 0.05; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_win_streak_cv_bit") or "").strip()
    return bit


def format_window_a_closes_flat_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A flat-close bit (sell meter ≠ decided closes; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_flat_bit") or "").strip()
    return bit


def format_window_a_closes_exit_mix_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A exit-mix bit (tp/sl/rot/trim; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_mix_bit") or "").strip()
    return bit


def format_window_a_closes_exit_unknown_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A unknown-exit bit (sells outside tp/sl/rot/trim; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_unknown_bit") or "").strip()
    return bit


def format_window_a_closes_exit_tp_share_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A take-profit share bit (tp ÷ known exits; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_tp_share_bit") or "").strip()
    return bit


def format_window_a_closes_exit_sl_share_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A stop share bit (sl ÷ known exits; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_sl_share_bit") or "").strip()
    return bit


def format_window_a_closes_exit_rot_share_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A rotation share bit (rot ÷ known exits; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_rot_share_bit") or "").strip()
    return bit


def format_window_a_closes_exit_trim_share_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A trim share bit (trim ÷ known exits; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_trim_share_bit") or "").strip()
    return bit


def format_window_a_closes_exit_lead_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A exit-lead bit (peak live reason; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_lead_bit") or "").strip()
    return bit


def format_window_a_closes_exit_euro_lead_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A euro-lead bit (P&L mover ≠ count lead; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_euro_lead_bit") or "").strip()
    return bit


def format_window_a_closes_exit_euro_offset_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A euro-offset bit (runner-up vs a matching lead; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_euro_offset_bit") or "").strip()
    return bit


def format_window_a_closes_exit_euro_gap_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A euro-gap bit (€ lead multiple vs count lead; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_euro_gap_bit") or "").strip()
    return bit


def format_window_a_closes_exit_euro_conc_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A euro-conc bit (top reason share of |exit €|; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_euro_conc_bit") or "").strip()
    return bit


def format_window_a_closes_exit_euro_count_skew_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A €/count conc-skew bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_euro_count_skew_bit") or "").strip()
    return bit


def format_window_a_closes_exit_euro_size_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A €/close size bit vs rest (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_euro_size_bit") or "").strip()
    return bit


def format_window_a_closes_exit_euro_size_n_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A exit € size-n sample bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_euro_size_n_bit") or "").strip()
    return bit


def format_window_a_closes_exit_euro_size_rest_n_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A exit € size rest-n sample bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_euro_size_rest_n_bit") or "").strip()
    return bit


def format_window_a_closes_exit_euro_size_sign_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A exit € size sign bit (signed net; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_euro_size_sign_bit") or "").strip()
    return bit


def format_window_a_closes_exit_euro_size_rest_sign_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A exit € size rest-sign bit (rest signed net; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_euro_size_rest_sign_bit") or "").strip()
    return bit


def format_window_a_closes_exit_euro_size_sign_clash_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A exit € size sign-clash bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(sample.get("closes_exit_euro_size_sign_clash_bit") or "").strip()
    return bit


def format_window_a_closes_exit_euro_size_sign_clash_net_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A exit € size clash-net bit (signed sum; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(
        sample.get("closes_exit_euro_size_sign_clash_net_bit") or ""
    ).strip()
    return bit


def format_window_a_closes_exit_euro_size_sign_clash_keep_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A exit € size clash-keep bit (|net| share; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(
        sample.get("closes_exit_euro_size_sign_clash_keep_bit") or ""
    ).strip()
    return bit


def format_window_a_closes_exit_euro_size_sign_clash_keep_fees_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A clash-keep fees bit (fees vs leftover; display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees_bit") or ""
    ).strip()
    return bit


def format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A leftover-vs-window fee mood bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees_vs_bit") or ""
    ).strip()
    return bit


def format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A leftover-vs-window fee gap bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit")
        or ""
    ).strip()
    return bit


def format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A leftover÷window fee gap direction bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(
        sample.get("closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit")
        or ""
    ).strip()
    return bit


def format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A leftover+window fee sides bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"
        )
        or ""
    ).strip()
    return bit


def format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A leftover−window fee sides Δ bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
        )
        or ""
    ).strip()
    return bit


def format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A leftover/window fee sides share bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
        )
        or ""
    ).strip()
    return bit


def format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A leftover−window fee sides share Δ bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit"
        )
        or ""
    ).strip()
    return bit


def format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A × Δ vs share Δ clash bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit"
        )
        or ""
    ).strip()
    return bit


def format_window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit(
    sample: dict[str, Any] | None,
) -> str:
    """Short Window A × Δ vs share Δ align bit (display only)."""
    if not isinstance(sample, dict):
        return ""
    bit = str(
        sample.get(
            "closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit"
        )
        or ""
    ).strip()
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


def _dated_decided_pnls(
    sells: Iterable[dict[str, Any]],
) -> list[tuple[datetime, float]]:
    """Dated decided sell P&L, oldest first. Flats and bad rows drop out."""
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
    dated.sort(key=lambda row: row[0])
    return dated


def ending_win_streak(sells: Iterable[dict[str, Any]]) -> int | None:
    """Newest run of winning closes. None when no dated decided sell.

    Flat closes do not count and do not break the run. A loss breaks the run.
    Order uses timestamps, not list order. Display only — not a gate.
    """
    dated = _dated_decided_pnls(sells)
    if not dated:
        return None
    streak = 0
    for _ts, pnl in reversed(dated):
        if pnl > 0:
            streak += 1
            continue
        break
    return streak


def ending_loss_streak(sells: Iterable[dict[str, Any]]) -> int | None:
    """Newest run of losing closes. None when no dated decided sell.

    Flat closes do not count and do not break the run. A win breaks the run.
    Order uses timestamps, not list order. Display only — not a gate.
    """
    dated = _dated_decided_pnls(sells)
    if not dated:
        return None
    streak = 0
    for _ts, pnl in reversed(dated):
        if pnl < 0:
            streak += 1
            continue
        break
    return streak


def _loss_run_lengths(sells: Iterable[dict[str, Any]]) -> list[int] | None:
    """Lengths of losing-close runs. None when no dated decided sell.

    Flat closes do not count and do not break a run. A win breaks the run.
    An empty list means dated sells with no losses. Display only — not a gate.
    """
    dated = _dated_decided_pnls(sells)
    if not dated:
        return None
    runs: list[int] = []
    streak = 0
    for _ts, pnl in dated:
        if pnl < 0:
            streak += 1
            continue
        if streak:
            runs.append(streak)
            streak = 0
    if streak:
        runs.append(streak)
    return runs


def max_loss_streak(sells: Iterable[dict[str, Any]]) -> int | None:
    """Longest run of losing closes. None when no dated decided sell.

    Flat closes do not count and do not break a run. A win breaks the run.
    The peak can exceed the newest ending run. Display only — not a gate.
    """
    runs = _loss_run_lengths(sells)
    if runs is None:
        return None
    if not runs:
        return 0
    return max(runs)


def min_loss_streak(sells: Iterable[dict[str, Any]]) -> int | None:
    """Shortest run of losing closes. None when there is no loss run.

    The floor can sit under the peak. Equal runs share one length.
    Display only — not a gate.
    """
    runs = _loss_run_lengths(sells)
    if not runs:
        return None
    return min(runs)


def _sample_stdev(runs: list[int] | None) -> float | None:
    """Sample stdev (n−1). None when fewer than two runs."""
    if not runs or len(runs) < 2:
        return None
    mean = sum(runs) / len(runs)
    var = sum((r - mean) ** 2 for r in runs) / (len(runs) - 1)
    return var**0.5


def stdev_loss_streak(sells: Iterable[dict[str, Any]]) -> float | None:
    """Sample stdev of losing-close run lengths. None when fewer than two runs.

    Min and max are the floor and the peak. The mean and the median are
    the typical run. σ shows how uneven those lengths are.
    Display only — not a gate.
    """
    return _sample_stdev(_loss_run_lengths(sells))


def _sample_cv(runs: list[int] | None) -> float | None:
    """Sample coefficient of variation (σ / mean). None when σ is missing or mean ≤ 0."""
    stdev = _sample_stdev(runs)
    if stdev is None or not runs:
        return None
    mean = sum(runs) / len(runs)
    if mean <= 0:
        return None
    return stdev / mean


def cv_loss_streak(sells: Iterable[dict[str, Any]]) -> float | None:
    """Sample CV of losing-close run lengths (σ / mean).

    σ is the absolute spread. CV scales that spread by the typical run.
    None when fewer than two runs or the mean is not positive.
    Display only — not a gate.
    """
    return _sample_cv(_loss_run_lengths(sells))


def mean_loss_streak(sells: Iterable[dict[str, Any]]) -> float | None:
    """Average losing-close run length. None when there is no loss run.

    One long storm and many short runs share the same peak. The mean
    shows the typical run. Display only — not a gate.
    """
    runs = _loss_run_lengths(sells)
    if not runs:
        return None
    return sum(runs) / len(runs)


def _median_run_length(runs: list[int] | None) -> float | None:
    """Median run length. None when there is no run."""
    if not runs:
        return None
    ordered = sorted(runs)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def median_loss_streak(sells: Iterable[dict[str, Any]]) -> float | None:
    """Median losing-close run length. None when there is no loss run.

    One long storm pulls the mean up. The median resists that.
    Display only — not a gate.
    """
    return _median_run_length(_loss_run_lengths(sells))


def median_win_streak(sells: Iterable[dict[str, Any]]) -> float | None:
    """Median winning-close run length. None when there is no win run.

    One long run pulls the mean up. The median resists that.
    Display only — not a gate.
    """
    return _median_run_length(_win_run_lengths(sells))


def loss_streak_run_count(sells: Iterable[dict[str, Any]]) -> int | None:
    """Count of losing-close runs. None when no dated decided sell.

    Zero means dated sells with no losses. Display only — not a gate.
    """
    runs = _loss_run_lengths(sells)
    if runs is None:
        return None
    return len(runs)


def _win_run_lengths(sells: Iterable[dict[str, Any]]) -> list[int] | None:
    """Lengths of winning-close runs. None when no dated decided sell.

    Flat closes do not count and do not break a run. A loss breaks the run.
    An empty list means dated sells with no wins. Display only — not a gate.
    """
    dated = _dated_decided_pnls(sells)
    if not dated:
        return None
    runs: list[int] = []
    streak = 0
    for _ts, pnl in dated:
        if pnl > 0:
            streak += 1
            continue
        if streak:
            runs.append(streak)
            streak = 0
    if streak:
        runs.append(streak)
    return runs


def min_win_streak(sells: Iterable[dict[str, Any]]) -> int | None:
    """Shortest run of winning closes. None when there is no win run.

    The floor can sit under the peak. Equal runs share one length.
    Display only — not a gate.
    """
    runs = _win_run_lengths(sells)
    if not runs:
        return None
    return min(runs)


def max_win_streak(sells: Iterable[dict[str, Any]]) -> int | None:
    """Longest run of winning closes. None when no dated decided sell.

    Flat closes do not count and do not break a run. A loss breaks the run.
    The peak can exceed the newest ending run. Display only — not a gate.
    """
    runs = _win_run_lengths(sells)
    if runs is None:
        return None
    if not runs:
        return 0
    return max(runs)


def mean_win_streak(sells: Iterable[dict[str, Any]]) -> float | None:
    """Average winning-close run length. None when there is no win run.

    One long run and many short runs share the same peak. The mean
    shows the typical run. Display only — not a gate.
    """
    runs = _win_run_lengths(sells)
    if not runs:
        return None
    return sum(runs) / len(runs)


def stdev_win_streak(sells: Iterable[dict[str, Any]]) -> float | None:
    """Sample stdev of winning-close run lengths. None when fewer than two runs.

    Min and max are the floor and the peak. The mean and the median are
    the typical run. σ shows how uneven those lengths are.
    Display only — not a gate.
    """
    return _sample_stdev(_win_run_lengths(sells))


def cv_win_streak(sells: Iterable[dict[str, Any]]) -> float | None:
    """Sample CV of winning-close run lengths (σ / mean).

    σ is the absolute spread. CV scales that spread by the typical run.
    None when fewer than two runs or the mean is not positive.
    Display only — not a gate.
    """
    return _sample_cv(_win_run_lengths(sells))


_EXIT_REASON_BUCKET = {
    "tp": "tp",
    "take_profit": "tp",
    "take-profit": "tp",
    "sl": "sl",
    "stop_loss": "sl",
    "stop-loss": "sl",
    "stop": "sl",
    "rotation": "rot",
    "rot": "rot",
    "rotate": "rot",
    "trim": "trim",
}


def exit_reason_bucket(raw: Any) -> str | None:
    """Map a ledger exit_reason to tp, sl, rot, or trim. Unknown stays None."""
    key = str(raw or "").strip().lower().replace(" ", "_")
    if not key:
        return None
    return _EXIT_REASON_BUCKET.get(key)


def sell_exit_pnl(sells: Iterable[dict[str, Any]]) -> dict[str, float] | None:
    """Signed profit_loss by live exit reason. None when there are no sells.

    Unknown reasons stay out. Display only — not a gate.
    """
    rows = list(sells)
    if not rows:
        return None
    pnl = {"tp": 0.0, "sl": 0.0, "rot": 0.0, "trim": 0.0}
    for row in rows:
        bucket = exit_reason_bucket(row.get("exit_reason"))
        if not bucket:
            continue
        try:
            pnl[bucket] += float(row.get("profit_loss") or 0)
        except (TypeError, ValueError):
            continue
    return {k: round(v, 2) for k, v in pnl.items()}


def sell_exit_counts(sells: Iterable[dict[str, Any]]) -> dict[str, int] | None:
    """Count live exit reasons on sells. None when there are no sells.

    Missing or unknown reasons stay out of the four buckets.
    All-zero means sells exist but none used tp, sl, rot, or trim.
    Display only — not a gate.
    """
    rows = list(sells)
    if not rows:
        return None
    counts = {"tp": 0, "sl": 0, "rot": 0, "trim": 0}
    for row in rows:
        bucket = exit_reason_bucket(row.get("exit_reason"))
        if bucket:
            counts[bucket] += 1
    return counts


def win_streak_run_count(sells: Iterable[dict[str, Any]]) -> int | None:
    """Count of winning-close runs. None when no dated decided sell.

    Zero means dated sells with no wins. Display only — not a gate.
    """
    runs = _win_run_lengths(sells)
    if runs is None:
        return None
    return len(runs)


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
    flat_closes = sum(1 for t in sells if float(t.get("profit_loss") or 0) == 0)
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
    exits = sell_exit_counts(sells)
    pnls = sell_exit_pnl(sells)
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
        "flat_closes": flat_closes,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "payoff_ratio": payoff_ratio,
        "gross_wins": gross_wins,
        "gross_losses": gross_losses,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "win_rate": win_rate,
        "loss_streak": ending_loss_streak(sells),
        "loss_streak_max": max_loss_streak(sells),
        "loss_streak_min": min_loss_streak(sells),
        "loss_streak_stdev": stdev_loss_streak(sells),
        "loss_streak_cv": cv_loss_streak(sells),
        "loss_streak_mean": mean_loss_streak(sells),
        "loss_streak_median": median_loss_streak(sells),
        "loss_streak_runs": loss_streak_run_count(sells),
        "win_streak": ending_win_streak(sells),
        "win_streak_max": max_win_streak(sells),
        "win_streak_min": min_win_streak(sells),
        "win_streak_stdev": stdev_win_streak(sells),
        "win_streak_cv": cv_win_streak(sells),
        "win_streak_mean": mean_win_streak(sells),
        "win_streak_median": median_win_streak(sells),
        "win_streak_runs": win_streak_run_count(sells),
        "exit_tp": None if exits is None else exits["tp"],
        "exit_sl": None if exits is None else exits["sl"],
        "exit_rot": None if exits is None else exits["rot"],
        "exit_trim": None if exits is None else exits["trim"],
        "exit_pnl_tp": None if pnls is None else pnls["tp"],
        "exit_pnl_sl": None if pnls is None else pnls["sl"],
        "exit_pnl_rot": None if pnls is None else pnls["rot"],
        "exit_pnl_trim": None if pnls is None else pnls["trim"],
        "exit_unknown": (
            None
            if exits is None
            else len(sells) - (exits["tp"] + exits["sl"] + exits["rot"] + exits["trim"])
        ),
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
