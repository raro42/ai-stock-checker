"""Paper-calm streak glance (display only)."""

from __future__ import annotations

from datetime import date

from openbb_backend.desk import (
    _calm_detail_is_promote_off_pause,
    build_calm_streak_glance,
)
from stock_checker.promote_ab import (
    WINDOW_A_TARGET_FILLS,
    WINDOW_A_TARGET_SELLS,
    WINDOW_A_TARGET_TRADING_DAYS,
    weekday_trading_days,
)


def test_calm_streak_glance_empty() -> None:
    assert build_calm_streak_glance(None)["ready"] is False
    assert build_calm_streak_glance({})["ready"] is False


def test_calm_detail_is_promote_off_pause() -> None:
    assert _calm_detail_is_promote_off_pause(
        "promote filter off — streak paused"
    )
    assert _calm_detail_is_promote_off_pause("Promote filter off")
    assert not _calm_detail_is_promote_off_pause("book overweight")
    assert not _calm_detail_is_promote_off_pause("")


def test_calm_streak_glance_blocked() -> None:
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "book overweight",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "blocked"
    assert g["promote_off_paused"] is False
    assert g["window_a_days"] is None
    assert g["window_a_fills"] is None
    assert g["streak"] == 0
    assert g["required"] == 30
    assert "0/30" in g["line"]
    assert "streak not started" in g["line"]
    assert "book overweight" in g["line"]


def test_calm_streak_glance_promote_off_paused() -> None:
    """Window A: promote off is intentional — not 'streak not started' failure."""
    as_of = date(2026, 8, 18)  # Window A running; day target not yet met
    a_days = weekday_trading_days(date(2026, 8, 12), as_of)
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
    )
    assert g["ready"] is True
    assert g["tone"] == "paused"
    assert g["promote_off_paused"] is True
    assert g["window_a_days"] == a_days
    assert g["window_a_target_days"] == WINDOW_A_TARGET_TRADING_DAYS
    assert g["window_a_fills"] is None  # no stats → fail-open silent
    assert g["window_a_fee_net_bit"] == ""
    assert g["window_a_fee_mood_bit"] == ""
    assert g["window_a_fee_drag"] is False
    assert g["window_a_fee_drag_severity"] == ""
    assert g["window_a_closes_polarity_bit"] == ""
    assert g["window_a_closes_polarity"] == ""
    assert g["window_a_closes_all_loss"] is False
    assert g["window_a_closes_expectancy_bit"] == ""
    assert g["window_a_closes_expectancy"] is None
    assert g["window_a_closes_expectancy_neg"] is False
    assert g["window_a_closes_profit_factor_bit"] == ""
    assert g["window_a_closes_profit_factor"] is None
    assert g["window_a_closes_profit_factor_thin"] is False
    assert g["window_a_closes_win_rate_bit"] == ""
    assert g["window_a_closes_win_rate_pct"] is None
    assert g["window_a_closes_win_rate_thin"] is False
    assert g["window_a_closes_wr_vs_be_bit"] == ""
    assert g["window_a_closes_wr_vs_be"] == ""
    assert g["window_a_closes_wr_edge_pp"] is None
    assert g["window_a_closes_wr_edge_thin"] is False
    assert g["window_a_closes_wr_below_be"] is False
    assert g["window_a_closes_net_expectancy_bit"] == ""
    assert g["window_a_closes_net_expectancy"] is None
    assert g["window_a_closes_net_expectancy_neg"] is False
    assert g["window_a_closes_net_expectancy_thin"] is False
    assert g["window_a_closes_net_expectancy_eats_edge"] is False
    assert g["window_a_closes_fee_take_bit"] == ""
    assert g["window_a_closes_fee_take"] is None
    assert g["window_a_closes_fee_take_thin"] is False
    assert g["window_a_closes_fee_take_severity"] == ""
    assert g["window_a_closes_net_profit_factor_bit"] == ""
    assert g["window_a_closes_net_profit_factor"] is None
    assert g["window_a_closes_net_profit_factor_thin"] is False
    assert g["window_a_closes_net_profit_factor_eats_edge"] is False
    assert g["window_a_closes_net_vs_fee_bit"] == ""
    assert g["window_a_closes_net_vs_fee"] is None
    assert g["window_a_closes_net_vs_fee_thin"] is False
    assert g["window_a_closes_net_vs_fee_severity"] == ""
    assert g["window_a_closes_kelly_bit"] == ""
    assert g["window_a_closes_kelly_pct"] is None
    assert g["window_a_closes_kelly_thin"] is False
    assert g["window_a_closes_kelly_neg"] is False
    assert g["window_a_closes_kelly_severity"] == ""
    assert g["window_a_closes_half_kelly_bit"] == ""
    assert g["window_a_closes_half_kelly_pct"] is None
    assert g["window_a_closes_half_kelly_sizer_pct"] is None
    assert g["window_a_closes_half_kelly_vs"] == ""
    assert g["window_a_closes_half_kelly_under"] is False
    assert g["window_a_closes_half_kelly_slot_bit"] == ""
    assert g["window_a_closes_half_kelly_slot_pct"] is None
    assert g["window_a_closes_half_kelly_vs_slot"] == ""
    assert g["window_a_closes_half_kelly_slot_under"] is False
    assert g["window_a_closes_half_kelly_cap_bit"] == ""
    assert g["window_a_closes_half_kelly_cap_pct"] is None
    assert g["window_a_closes_half_kelly_vs_cap"] == ""
    assert g["window_a_closes_half_kelly_cap_under"] is False
    assert g["window_a_closes_quarter_kelly_bit"] == ""
    assert g["window_a_closes_quarter_kelly_pct"] is None
    assert g["window_a_closes_quarter_kelly_sizer_pct"] is None
    assert g["window_a_closes_quarter_kelly_vs"] == ""
    assert g["window_a_closes_quarter_kelly_under"] is False
    assert g["window_a_closes_quarter_kelly_slot_bit"] == ""
    assert g["window_a_closes_quarter_kelly_slot_pct"] is None
    assert g["window_a_closes_quarter_kelly_vs_slot"] == ""
    assert g["window_a_closes_quarter_kelly_slot_under"] is False
    assert g["window_a_closes_quarter_kelly_cap_bit"] == ""
    assert g["window_a_closes_quarter_kelly_cap_pct"] is None
    assert g["window_a_closes_quarter_kelly_vs_cap"] == ""
    assert g["window_a_closes_quarter_kelly_cap_under"] is False
    assert g["window_a_closes_practical_kelly_bit"] == ""
    assert g["window_a_closes_practical_kelly"] == ""
    assert g["window_a_closes_practical_kelly_pct"] is None
    assert g["window_a_closes_practical_kelly_cut"] is False
    assert g["window_a_closes_kelly_sample_bit"] == ""
    assert g["window_a_closes_kelly_sample"] == ""
    assert g["window_a_closes_kelly_sample_n"] is None
    assert g["window_a_closes_kelly_sample_thin"] is False
    assert g["window_a_closes_sell_sessions_bit"] == ""
    assert g["window_a_closes_sell_sessions"] == ""
    assert g["window_a_closes_sell_sessions_n"] is None
    assert g["window_a_closes_sell_sessions_few"] is False
    assert g["window_a_closes_kelly_vs_sessions_bit"] == ""
    assert g["window_a_closes_kelly_vs_sessions"] == ""
    assert g["window_a_closes_kelly_vs_sessions_clash"] is False
    assert g["window_a_closes_per_day_bit"] == ""
    assert g["window_a_closes_per_day"] == ""
    assert g["window_a_closes_per_day_n"] is None
    assert g["window_a_closes_per_day_fat"] is False
    assert g["window_a_closes_sessions_vs_per_day_bit"] == ""
    assert g["window_a_closes_sessions_vs_per_day"] == ""
    assert g["window_a_closes_sessions_vs_per_day_clash"] is False
    assert g["window_a_closes_ksess_vs_sessday_bit"] == ""
    assert g["window_a_closes_ksess_vs_sessday"] == ""
    assert g["window_a_closes_ksess_vs_sessday_clash"] is False
    assert g["window_a_closes_kelly_vs_per_day_bit"] == ""
    assert g["window_a_closes_kelly_vs_per_day"] == ""
    assert g["window_a_closes_kelly_vs_per_day_clash"] is False
    assert g["window_a_closes_kday_vs_kd_bit"] == ""
    assert g["window_a_closes_kday_vs_kd"] == ""
    assert g["window_a_closes_kday_vs_kd_clash"] is False
    assert g["window_a_closes_loss_streak_bit"] == ""
    assert g["window_a_closes_loss_streak"] is None
    assert g["window_a_closes_loss_streak_hot"] is False
    assert g["window_a_closes_loss_streak_max_bit"] == ""
    assert g["window_a_closes_loss_streak_max"] is None
    assert g["window_a_closes_loss_streak_max_hot"] is False
    assert g["window_a_closes_win_streak_bit"] == ""
    assert g["window_a_closes_win_streak"] is None
    assert g["window_a_closes_win_streak_hot"] is False
    assert g["window_a_closes_win_streak_max_bit"] == ""
    assert g["window_a_closes_win_streak_max"] is None
    assert g["window_a_closes_win_streak_max_hot"] is False
    assert g["window_a_closes_flat_bit"] == ""
    assert g["window_a_closes_flat"] is None
    assert g["window_a_closes_flat_warn"] is False
    assert g["window_a_closes_loss_streak_mean_bit"] == ""
    assert g["window_a_closes_loss_streak_mean"] is None
    assert g["window_a_closes_loss_streak_runs"] is None
    assert g["window_a_closes_loss_streak_mean_hot"] is False
    assert g["window_a_closes_win_streak_mean_bit"] == ""
    assert g["window_a_closes_win_streak_mean"] is None
    assert g["window_a_closes_win_streak_runs"] is None
    assert g["window_a_closes_win_streak_mean_hot"] is False
    assert g["window_a_closes_loss_streak_median_bit"] == ""
    assert g["window_a_closes_loss_streak_median"] is None
    assert g["window_a_closes_loss_streak_median_hot"] is False
    assert g["window_a_closes_win_streak_median_bit"] == ""
    assert g["window_a_closes_win_streak_median"] is None
    assert g["window_a_closes_win_streak_median_hot"] is False
    assert g["window_a_closes_loss_streak_min_bit"] == ""
    assert g["window_a_closes_loss_streak_min"] is None
    assert g["window_a_closes_loss_streak_min_hot"] is False
    assert g["window_a_closes_win_streak_min_bit"] == ""
    assert g["window_a_closes_win_streak_min"] is None
    assert g["window_a_closes_win_streak_min_hot"] is False
    assert g["window_a_closes_loss_streak_stdev_bit"] == ""
    assert g["window_a_closes_loss_streak_stdev"] is None
    assert g["window_a_closes_loss_streak_stdev_hot"] is False
    assert g["window_a_closes_win_streak_stdev_bit"] == ""
    assert g["window_a_closes_win_streak_stdev"] is None
    assert g["window_a_closes_win_streak_stdev_hot"] is False
    assert g["window_a_closes_loss_streak_cv_bit"] == ""
    assert g["window_a_closes_loss_streak_cv"] is None
    assert g["window_a_closes_loss_streak_cv_hot"] is False
    assert g["window_a_closes_win_streak_cv_bit"] == ""
    assert g["window_a_closes_win_streak_cv"] is None
    assert g["window_a_closes_win_streak_cv_hot"] is False
    assert g["window_a_closes_exit_mix_bit"] == ""
    assert g["window_a_closes_exit_mix_hot"] is False
    assert g["window_a_closes_exit_unknown_bit"] == ""
    assert g["window_a_closes_exit_unknown"] is None
    assert g["window_a_closes_exit_unknown_warn"] is False
    assert g["window_a_closes_exit_tp_share_bit"] == ""
    assert g["window_a_closes_exit_tp_share_pct"] is None
    assert g["window_a_closes_exit_tp_share_severity"] == ""
    assert g["window_a_closes_exit_tp_share_thin"] is False
    assert g["window_a_closes_exit_sl_share_bit"] == ""
    assert g["window_a_closes_exit_sl_share_pct"] is None
    assert g["window_a_closes_exit_sl_share_severity"] == ""
    assert g["window_a_closes_exit_sl_share_hot"] is False
    assert g["window_a_closes_exit_rot_share_bit"] == ""
    assert g["window_a_closes_exit_rot_share_pct"] is None
    assert g["window_a_closes_exit_rot_share_severity"] == ""
    assert g["window_a_closes_exit_rot_share_hot"] is False
    assert g["window_a_closes_exit_trim_share_bit"] == ""
    assert g["window_a_closes_exit_trim_share_pct"] is None
    assert g["window_a_closes_exit_trim_share_severity"] == ""
    assert g["window_a_closes_exit_trim_share_hot"] is False
    assert g["window_a_closes_exit_euro_lead_bit"] == ""
    assert g["window_a_closes_exit_euro_lead"] is None
    assert g["window_a_closes_exit_euro_pnl"] is None
    assert g["window_a_closes_exit_euro_lead_hot"] is False
    assert g["window_a_closes_exit_euro_offset_bit"] == ""
    assert g["window_a_closes_exit_euro_offset"] is None
    assert g["window_a_closes_exit_euro_offset_pnl"] is None
    assert g["window_a_closes_exit_euro_offset_ratio"] is None
    assert g["window_a_closes_exit_euro_offset_hot"] is False
    assert g["window_a_closes_exit_euro_gap_bit"] == ""
    assert g["window_a_closes_exit_euro_gap_ratio"] is None
    assert g["window_a_closes_exit_euro_gap_vs"] is None
    assert g["window_a_closes_exit_euro_gap_hot"] is False
    assert g["window_a_closes_exit_euro_conc_bit"] == ""
    assert g["window_a_closes_exit_euro_conc"] is None
    assert g["window_a_closes_exit_euro_conc_pct"] is None
    assert g["window_a_closes_exit_euro_conc_hot"] is False
    assert g["window_a_closes_exit_euro_count_skew_bit"] == ""
    assert g["window_a_closes_exit_euro_count_skew_pp"] is None
    assert g["window_a_closes_exit_euro_count_skew_hot"] is False
    assert g["window_a_closes_exit_euro_size_bit"] == ""
    assert g["window_a_closes_exit_euro_size_ratio"] is None
    assert g["window_a_closes_exit_euro_size_hot"] is False
    assert g["window_a_closes_exit_euro_size_n_bit"] == ""
    assert g["window_a_closes_exit_euro_size_n"] is None
    assert g["window_a_closes_exit_euro_size_n_count"] is None
    assert g["window_a_closes_exit_euro_size_n_thin"] is False
    assert g["window_a_closes_exit_euro_size_sign_bit"] == ""
    assert g["window_a_closes_exit_euro_size_sign"] is None
    assert g["window_a_closes_exit_euro_size_sign_pnl"] is None
    assert g["window_a_closes_exit_euro_size_sign_loss"] is False
    assert g["window_a_closes_exit_euro_size_rest_sign_bit"] == ""
    assert g["window_a_closes_exit_euro_size_rest_sign"] is None
    assert g["window_a_closes_exit_euro_size_rest_sign_pnl"] is None
    assert g["window_a_closes_exit_euro_size_rest_sign_loss"] is False
    assert g["window_a_closes_exit_euro_size_sign_clash_bit"] == ""
    assert g["window_a_closes_exit_euro_size_sign_clash"] is None
    assert g["window_a_closes_exit_euro_size_sign_clash_loss"] is False
    assert g["window_a_closes_exit_euro_size_sign_clash_net_bit"] == ""
    assert g["window_a_closes_exit_euro_size_sign_clash_net"] is None
    assert g["window_a_closes_exit_euro_size_sign_clash_net_pnl"] is None
    assert g["window_a_closes_exit_euro_size_sign_clash_net_loss"] is False
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_bit"] == ""
    assert g["window_a_closes_exit_euro_size_sign_clash_keep"] is None
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_ratio"] is None
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_thin"] is False
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_bit"] == ""
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees"] is None
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_ratio"] is None
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_warn"] is False
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == ""
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs"] is None
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_window"] is None
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_warn"] is False
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit"] == ""
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap"] is None
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_ratio"] is None
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn"] is False
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit"] == ""
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir"] is None
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio"] is None
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn"] is False
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"
    ] == ""
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn"
    ] is False
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
    ] == ""
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn"
    ] is False
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == ""
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn"
    ] is False
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit"
    ] == ""
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn"
    ] is False
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit"
    ] == ""
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn"
    ] is False
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit"
    ] == ""
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn"
    ] is False
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit"
    ] == ""
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_warn"
    ] is False
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit"
    ] == ""
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_warn"
    ] is False
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit"
    ] == ""
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_warn"
    ] is False
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == ""
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_louder"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_quieter"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_warn"
    ] is False
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == ""
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_ratio"
    ] is None
    assert g[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_warn"
    ] is False
    assert g["window_a_closes_exit_tp"] is None
    assert g["window_a_closes_exit_sl"] is None
    assert g["window_a_closes_exit_rot"] is None
    assert g["window_a_closes_exit_trim"] is None
    assert "0/30" in g["line"]
    assert "promote off · streak paused" in g["line"]
    assert f"A {a_days}/{WINDOW_A_TARGET_TRADING_DAYS}d" in g["line"]
    assert "fills" not in g["line"]
    assert "fees" not in g["line"]
    assert "drag" not in g["line"]
    assert "streak not started" not in g["line"]
    # Compact status already names the why — do not repeat long detail.
    assert "promote filter off" not in g["line"]


def test_calm_streak_glance_promote_off_paused_window_a_days_ready() -> None:
    """Pause alone must not hide that Window A day floor is already met."""
    as_of = date(2026, 9, 9)
    a_days = weekday_trading_days(date(2026, 8, 12), as_of)
    assert a_days >= WINDOW_A_TARGET_TRADING_DAYS
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
    )
    assert g["promote_off_paused"] is True
    assert g["window_a_days"] == a_days
    assert f"A {a_days}/{WINDOW_A_TARGET_TRADING_DAYS}d" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_sample_meter() -> None:
    """Day meter alone must not hide a thin Window A fill/sell sample."""
    as_of = date(2026, 9, 9)
    a_days = weekday_trading_days(date(2026, 8, 12), as_of)
    assert a_days >= WINDOW_A_TARGET_TRADING_DAYS
    stats = {
        "trades": 4,
        "buys": 3,
        "sells": 1,
        "fees": 5.0,
        "realized_pnl": 2.0,
        "net_after_all_fees": -3.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["promote_off_paused"] is True
    assert g["window_a_days"] == a_days
    assert g["window_a_fills"] == 4
    assert g["window_a_target_fills"] == WINDOW_A_TARGET_FILLS
    assert g["window_a_sells"] == 1
    assert g["window_a_target_sells"] == WINDOW_A_TARGET_SELLS
    assert g["window_a_sample_status"] == "building sample"
    assert g["window_a_fee_net_bit"] == "€5 fees · −€3 net"
    assert g["window_a_fee_mood_bit"] == "drag heavy"
    assert g["window_a_fee_drag"] is True
    assert g["window_a_fee_drag_severity"] == "heavy"
    assert g["window_a_closes_polarity_bit"] == ""  # no wins/losses → silent
    assert g["window_a_closes_payoff_bit"] == ""  # no avgs → silent
    assert g["window_a_closes_expectancy_bit"] == ""  # no avgs → silent
    assert g["window_a_closes_profit_factor_bit"] == ""  # no both sides → silent
    assert g["tone"] == "warn"  # day floor met + thin sample / fee drag
    assert f"A {a_days}/{WINDOW_A_TARGET_TRADING_DAYS}" in g["line"]
    assert "building sample" in g["line"]
    assert "€5" in g["line"]
    assert "−€3" in g["line"]
    assert "drag heavy" in g["line"]
    # Mood + compact € before meters — clip may drop fill counts.
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_sample_ready() -> None:
    """Fill/sell meters alone must not hide that the sample floors are met."""
    as_of = date(2026, 8, 18)  # days still short
    a_days = weekday_trading_days(date(2026, 8, 12), as_of)
    assert a_days < WINDOW_A_TARGET_TRADING_DAYS
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 8.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 12.0,
        "wins": 3,
        "losses": 2,
        "avg_win": 8.0,
        "avg_loss": 4.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["promote_off_paused"] is True
    assert g["window_a_sample_status"] == "sample ready"
    assert g["window_a_fee_net_bit"] == "€8 fees · +€12 net"
    assert g["window_a_fee_mood_bit"] == "fees ok"
    assert g["window_a_fee_drag"] is False
    assert g["window_a_fees_ok_severity"] == "ok"
    assert g["window_a_fees_thin"] is False
    assert g["window_a_closes_polarity_bit"] == "3w/2l"
    assert g["window_a_closes_polarity"] == "mixed"
    assert g["window_a_closes_loss_lean"] is False
    assert g["window_a_closes_payoff_bit"] == "pay strong · 2×"
    assert g["window_a_closes_payoff_severity"] == "strong"
    assert g["window_a_closes_payoff_thin"] is False
    assert g["window_a_closes_payoff_ratio"] == 2.0
    # 0.6·8 − 0.4·4 = 3.2 → strong vs avg_loss
    assert g["window_a_closes_expectancy_bit"] == "exp strong · +€3"
    assert g["window_a_closes_expectancy"] == 3.2
    assert g["window_a_closes_expectancy_severity"] == "strong"
    assert g["window_a_closes_expectancy_thin"] is False
    assert g["window_a_closes_expectancy_neg"] is False
    # gross 24÷8 = 3× → strong PF (expectancy €/close ≠ total €)
    assert g["window_a_closes_profit_factor_bit"] == "PF strong · 3×"
    assert g["window_a_closes_profit_factor"] == 3.0
    assert g["window_a_closes_profit_factor_severity"] == "strong"
    assert g["window_a_closes_profit_factor_thin"] is False
    # 3/5 = 60% → strong WR (PF ≠ hit rate)
    assert g["window_a_closes_win_rate_bit"] == "WR strong · 60%"
    assert g["window_a_closes_win_rate_pct"] == 60.0
    assert g["window_a_closes_win_rate_severity"] == "strong"
    assert g["window_a_closes_win_rate_thin"] is False
    # BE = 100/(1+2) = 33.3%; cushion +26.7pp → above strong
    assert g["window_a_closes_wr_vs_be_bit"] == "WR above BE strong · +26.7pp"
    assert g["window_a_closes_wr_vs_be"] == "above"
    assert g["window_a_closes_breakeven_wr_pct"] == 33.3
    assert g["window_a_closes_wr_edge_pp"] == 26.7
    assert g["window_a_closes_wr_edge_severity"] == "strong"
    assert g["window_a_closes_wr_edge_thin"] is False
    assert g["window_a_closes_wr_below_be"] is False
    # net 12÷5 = 2.4 → strong vs avg_loss (gross exp ≠ fee-adjusted)
    assert g["window_a_closes_net_expectancy_bit"] == "net exp strong · +€2"
    assert g["window_a_closes_net_expectancy"] == 2.4
    assert g["window_a_closes_net_expectancy_severity"] == "strong"
    assert g["window_a_closes_net_expectancy_thin"] is False
    assert g["window_a_closes_net_expectancy_neg"] is False
    assert g["window_a_closes_net_expectancy_eats_edge"] is False
    # take 3.2−2.4 = 0.8 → mid · €1 (0.25 ratio; net ≠ fee take)
    assert g["window_a_closes_fee_take_bit"] == "fee take · €1"
    assert g["window_a_closes_fee_take"] == 0.8
    assert g["window_a_closes_fee_take_ratio"] == 0.25
    assert g["window_a_closes_fee_take_thin"] is False
    assert g["window_a_closes_fee_take_severity"] == ""
    # net wins 24−8=16 ÷ losses 8 → net PF 2× strong (fee take ≠ net PF)
    assert g["window_a_closes_net_profit_factor_bit"] == "net PF strong · 2×"
    assert g["window_a_closes_net_profit_factor"] == 2.0
    assert g["window_a_closes_net_profit_factor_severity"] == "strong"
    assert g["window_a_closes_net_profit_factor_thin"] is False
    assert g["window_a_closes_net_profit_factor_eats_edge"] is False
    # net 2.4 ÷ take 0.8 → 3× strong (net PF ≠ net÷fee-take)
    assert g["window_a_closes_net_vs_fee_bit"] == "net/fee strong · 3×"
    assert g["window_a_closes_net_vs_fee"] == 3.0
    assert g["window_a_closes_net_vs_fee_severity"] == "strong"
    assert g["window_a_closes_net_vs_fee_thin"] is False
    # WR 60% · payoff 2 → f* = 0.6 − 0.4/2 = 40% strong (WR−BE ≠ Kelly)
    assert g["window_a_closes_kelly_bit"] == "Kelly strong · 40%"
    assert g["window_a_closes_kelly_pct"] == 40.0
    assert g["window_a_closes_kelly_severity"] == "strong"
    assert g["window_a_closes_kelly_thin"] is False
    assert g["window_a_closes_kelly_neg"] is False
    # half 20% vs 10% sizer → over; vs 20% slot → match (sizer ≠ slot)
    assert g["window_a_closes_half_kelly_bit"] == "half-K/sizer over · 20% vs 10%"
    assert g["window_a_closes_half_kelly_pct"] == 20.0
    assert g["window_a_closes_half_kelly_sizer_pct"] == 10.0
    assert g["window_a_closes_half_kelly_vs"] == "over"
    assert g["window_a_closes_half_kelly_under"] is False
    assert g["window_a_closes_half_kelly_slot_bit"] == (
        "half-K/slot match · 20% vs 20%"
    )
    assert g["window_a_closes_half_kelly_slot_pct"] == 20.0
    assert g["window_a_closes_half_kelly_vs_slot"] == "match"
    assert g["window_a_closes_half_kelly_slot_under"] is False
    # half 20% vs 30% cap → under (slot match ≠ single-name ceiling)
    assert g["window_a_closes_half_kelly_cap_bit"] == (
        "half-K/cap under · 20% vs 30%"
    )
    assert g["window_a_closes_half_kelly_cap_pct"] == 30.0
    assert g["window_a_closes_half_kelly_vs_cap"] == "under"
    assert g["window_a_closes_half_kelly_cap_under"] is True
    # quarter 10% vs 10% → match (half over sizer ≠ quarter match)
    assert g["window_a_closes_quarter_kelly_bit"] == (
        "qtr-K/sizer match · 10% vs 10%"
    )
    assert g["window_a_closes_quarter_kelly_pct"] == 10.0
    assert g["window_a_closes_quarter_kelly_sizer_pct"] == 10.0
    assert g["window_a_closes_quarter_kelly_vs"] == "match"
    assert g["window_a_closes_quarter_kelly_under"] is False
    # quarter 10% vs 20% slot → under (sizer match ≠ equal book weight)
    assert g["window_a_closes_quarter_kelly_slot_bit"] == (
        "qtr-K/slot under · 10% vs 20%"
    )
    assert g["window_a_closes_quarter_kelly_slot_pct"] == 20.0
    assert g["window_a_closes_quarter_kelly_vs_slot"] == "under"
    assert g["window_a_closes_quarter_kelly_slot_under"] is True
    # quarter 10% vs 30% cap → under (slot under ≠ single-name ceiling)
    assert g["window_a_closes_quarter_kelly_cap_bit"] == (
        "qtr-K/cap under · 10% vs 30%"
    )
    assert g["window_a_closes_quarter_kelly_cap_pct"] == 30.0
    assert g["window_a_closes_quarter_kelly_vs_cap"] == "under"
    assert g["window_a_closes_quarter_kelly_cap_under"] is True
    # half over + quarter match sizer → practical quarter (triad ≠ pick)
    assert g["window_a_closes_practical_kelly"] == "quarter"
    assert g["window_a_closes_practical_kelly_pct"] == 10.0
    assert g["window_a_closes_practical_kelly_cut"] is False
    assert g["window_a_closes_practical_kelly_bit"] == "pract-K quarter · 10%"
    assert g["tone"] == "warn"  # under half-cap / under slot / under qtr-cap
    # sample ready + payoff + exp + PF + WR% + WR/BE + net + fee take +
    # net PF + net/fee + Kelly + half-K triad + qtr-K triad stay in
    # fields; K-sample owns clip
    assert g["window_a_sample_status"] == "sample ready"
    assert "sample ready" not in g["line"]
    assert "pay strong" not in g["line"]
    assert "€8" not in g["line"]  # compact € stays in fields when K-sample spoke
    assert "+€12" not in g["line"]
    assert "fees ok" in g["line"]
    assert "3w/2l" not in g["line"]  # polarity stays in fields
    assert f" · {g['window_a_closes_expectancy_bit']}" not in g["line"]
    assert " · PF" not in g["line"]  # gross PF stays in fields
    assert "WR strong · 60%" not in g["line"]  # WR% stays in fields
    assert "WR above BE strong" not in g["line"]  # WR/BE stays in fields
    assert "net exp strong" not in g["line"]  # net stays in fields
    assert "fee take · €1" not in g["line"]  # fee take stays in fields
    assert "net PF strong · 2×" not in g["line"]  # net PF stays in fields
    assert "net/fee strong · 3×" not in g["line"]  # net/fee stays in fields
    assert "Kelly strong · 40%" not in g["line"]  # Kelly stays in fields
    assert "half-K/sizer over · 20% vs 10%" not in g["line"]  # sizer in fields
    assert "half-K/slot match · 20% vs 20%" not in g["line"]  # slot in fields
    assert "half-K/cap under · 20% vs 30%" not in g["line"]  # cap in fields
    assert "qtr-K/sizer match · 10% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot under · 10% vs 20%" not in g["line"]  # slot in fields
    assert "qtr-K/cap under · 10% vs 30%" not in g["line"]  # cap in fields
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 5
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 5 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 5 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_building_closes() -> None:
    """Fills ok but sparse sells → building closes (not bare meters)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 11,
        "sells": 1,
        "fees": 8.0,
        "realized_pnl": 2.0,
        "net_after_all_fees": -6.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_sample_status"] == "building closes"
    assert g["window_a_fee_net_bit"] == "€8 fees · −€6 net"
    assert g["window_a_fee_mood_bit"] == "drag heavy"
    assert g["window_a_fee_drag"] is True
    assert g["window_a_fee_drag_severity"] == "heavy"
    assert g["tone"] == "warn"  # fee drag escalates even when days short
    assert "building closes" in g["line"]
    assert "€8" in g["line"]
    assert "drag heavy" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_fee_net() -> None:
    """Sample status alone must not hide fee-adjusted Window A net."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 15.0,
        "realized_pnl": 10.0,
        "net_after_all_fees": -5.0,
        "wins": 2,
        "losses": 3,
        "avg_win": 8.0,
        "avg_loss": 4.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_sample_status"] == "sample ready"
    assert g["window_a_fee_net_bit"] == "€15 fees · −€5 net"
    assert g["window_a_fee_mood_bit"] == "drag mild"
    assert g["window_a_fee_drag"] is True
    assert g["window_a_fee_drag_severity"] == "mild"
    assert g["window_a_closes_polarity_bit"] == "2w/3l"
    assert g["window_a_closes_polarity"] == "mixed"
    assert g["window_a_closes_loss_lean"] is True
    assert g["window_a_closes_payoff_bit"] == "pay strong · 2×"
    assert g["window_a_closes_payoff_severity"] == "strong"
    # 0.4·8 − 0.6·4 = 0.8 → thin vs avg_loss (payoff strong ≠ €/close strong)
    assert g["window_a_closes_expectancy_bit"] == "exp thin · +€1"
    assert g["window_a_closes_expectancy"] == 0.8
    assert g["window_a_closes_expectancy_thin"] is True
    # gross 16÷12 ≈ 1.3× mid PF
    assert g["window_a_closes_profit_factor_bit"] == "PF · 1.3×"
    assert g["window_a_closes_profit_factor"] == 1.33
    assert g["window_a_closes_profit_factor_thin"] is False
    # 2/5 = 40% → mid WR (not thin); BE 33.3% → above mid +6.7pp
    assert g["window_a_closes_win_rate_bit"] == "WR · 40%"
    assert g["window_a_closes_win_rate_pct"] == 40.0
    assert g["window_a_closes_win_rate_thin"] is False
    assert g["window_a_closes_wr_vs_be_bit"] == "WR above BE · +6.7pp"
    assert g["window_a_closes_wr_vs_be"] == "above"
    assert g["window_a_closes_wr_edge_pp"] == 6.7
    assert g["window_a_closes_wr_edge_thin"] is False
    # net −5÷5 = −1; gross exp +0.8 → fees eat edge
    assert g["window_a_closes_net_expectancy_bit"] == "net exp −€1 · fees eat"
    assert g["window_a_closes_net_expectancy"] == -1.0
    assert g["window_a_closes_net_expectancy_neg"] is True
    assert g["window_a_closes_net_expectancy_eats_edge"] is True
    # take 0.8−(−1) = 1.8 → thin · €2 (1.8/0.8 ≥ 0.5; net ≠ fee take)
    assert g["window_a_closes_fee_take_bit"] == "fee take thin · €2"
    assert g["window_a_closes_fee_take"] == 1.8
    assert g["window_a_closes_fee_take_thin"] is True
    assert g["window_a_closes_fee_take_severity"] == "thin"
    # net wins 16−15=1 ÷ losses 12 → net PF ~0.08× thin
    assert g["window_a_closes_net_profit_factor_bit"] == "net PF thin · 0.1×"
    assert g["window_a_closes_net_profit_factor"] == 0.08
    assert g["window_a_closes_net_profit_factor_thin"] is True
    assert g["window_a_closes_net_profit_factor_eats_edge"] is False
    # net ≤ 0 → net/fee silent; WR 40% · payoff 2 → Kelly 10% mid;
    # half 5% vs 10% → match owns clip
    assert g["window_a_closes_net_vs_fee_bit"] == ""
    assert g["window_a_closes_net_vs_fee"] is None
    assert g["window_a_closes_net_vs_fee_thin"] is False
    assert g["window_a_closes_kelly_bit"] == "Kelly · 10%"
    assert g["window_a_closes_kelly_pct"] == 10.0
    assert g["window_a_closes_kelly_severity"] == ""
    assert g["window_a_closes_kelly_thin"] is False
    assert g["window_a_closes_kelly_neg"] is False
    assert g["window_a_closes_half_kelly_bit"] == (
        "half-K/sizer match · 5% vs 10%"
    )
    assert g["window_a_closes_half_kelly_vs"] == "match"
    assert g["window_a_closes_half_kelly_under"] is False
    # half 5% vs 20% slot → under; vs 30% cap → under; pract half owns clip
    assert g["window_a_closes_half_kelly_slot_bit"] == (
        "half-K/slot under · 5% vs 20%"
    )
    assert g["window_a_closes_half_kelly_vs_slot"] == "under"
    assert g["window_a_closes_half_kelly_slot_under"] is True
    assert g["window_a_closes_half_kelly_cap_bit"] == (
        "half-K/cap under · 5% vs 30%"
    )
    assert g["window_a_closes_half_kelly_vs_cap"] == "under"
    assert g["window_a_closes_half_kelly_cap_under"] is True
    assert g["window_a_closes_practical_kelly"] == "half"
    assert g["window_a_closes_practical_kelly_bit"] == "pract-K half · 5%"
    assert g["tone"] == "warn"
    assert g["window_a_sample_status"] == "sample ready"
    assert "sample ready" not in g["line"]
    assert "drag mild" in g["line"]
    # Compact € dropped when K-sample spoke so the pract bit fits.
    assert "€15" not in g["line"]
    assert "2w/3l" not in g["line"]  # polarity stays in fields
    assert "pay strong" not in g["line"]
    assert f" · {g['window_a_closes_expectancy_bit']}" not in g["line"]
    assert " · PF" not in g["line"]  # gross PF stays in fields
    assert "WR · 40%" not in g["line"]  # WR% stays in fields
    assert "WR above BE · +6.7pp" not in g["line"]  # WR/BE stays in fields
    assert "net exp −€1" not in g["line"]  # net stays in fields
    assert "fees eat" not in g["line"]
    assert "fee take thin · €2" not in g["line"]  # fee take stays in fields
    assert "net/fee" not in g["line"]
    assert "net PF thin · 0.1×" not in g["line"]  # net PF stays in fields
    assert "Kelly · 10%" not in g["line"]  # Kelly stays in fields
    assert "half-K/sizer match · 5% vs 10%" not in g["line"]  # sizer in fields
    assert "half-K/slot under · 5% vs 20%" not in g["line"]  # slot in fields
    assert "half-K/cap under · 5% vs 30%" not in g["line"]  # cap stays in fields
    assert "qtr-K/sizer under · 2.5% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot under · 2.5% vs 20%" not in g["line"]
    assert "qtr-K/cap under · 2.5% vs 30%" not in g["line"]  # cap stays in fields
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 5
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 5 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 5 closes <10" in g["line"]
    # Mood + K-sample before meters.
    mood_pos = g["line"].find("drag mild")
    ks_pos = g["line"].find("K-sample")
    fill_pos = g["line"].find("fills")
    assert mood_pos > 0
    assert ks_pos > mood_pos
    if fill_pos > 0:
        assert ks_pos < fill_pos
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_fee_mood_comfortable() -> None:
    """€/net alone must not hide comfortable fee mood (speak-both-sides)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 2.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 18.0,
        "wins": 4,
        "losses": 1,
        "avg_win": 6.0,
        "avg_loss": 4.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_fee_net_bit"] == "€2 fees · +€18 net"
    # Line uses "fees calm" (clip); field keeps the band token.
    assert g["window_a_fee_mood_bit"] == "fees calm"
    assert g["window_a_fees_ok_severity"] == "comfortable"
    assert g["window_a_fee_drag"] is False
    assert g["window_a_closes_polarity_bit"] == "4w/1l"
    assert g["window_a_closes_polarity"] == "mixed"
    assert g["window_a_closes_payoff_bit"] == "pay · 1.5×"
    assert g["window_a_closes_payoff_severity"] == ""
    assert g["window_a_closes_payoff_thin"] is False
    # 0.8·6 − 0.2·4 = 4.0 → strong vs avg_loss
    assert g["window_a_closes_expectancy_bit"] == "exp strong · +€4"
    assert g["window_a_closes_expectancy"] == 4.0
    assert g["window_a_closes_expectancy_severity"] == "strong"
    # gross 24÷4 = 6× → strong PF
    assert g["window_a_closes_profit_factor_bit"] == "PF strong · 6×"
    assert g["window_a_closes_profit_factor"] == 6.0
    assert g["window_a_closes_profit_factor_severity"] == "strong"
    # 4/5 = 80% → strong WR; BE 40% → above strong +40pp
    assert g["window_a_closes_win_rate_bit"] == "WR strong · 80%"
    assert g["window_a_closes_win_rate_pct"] == 80.0
    assert g["window_a_closes_win_rate_severity"] == "strong"
    assert g["window_a_closes_wr_vs_be_bit"] == "WR above BE strong · +40pp"
    assert g["window_a_closes_wr_vs_be"] == "above"
    assert g["window_a_closes_breakeven_wr_pct"] == 40.0
    assert g["window_a_closes_wr_edge_pp"] == 40.0
    assert g["window_a_closes_wr_edge_severity"] == "strong"
    # net 18÷5 = 3.6 → strong vs avg_loss
    assert g["window_a_closes_net_expectancy_bit"] == "net exp strong · +€4"
    assert g["window_a_closes_net_expectancy"] == 3.6
    assert g["window_a_closes_net_expectancy_severity"] == "strong"
    assert g["window_a_closes_net_expectancy_neg"] is False
    # take 4.0−3.6 = 0.4 → calm · €0 (0.1 < comfortable; clip rounds €)
    assert g["window_a_closes_fee_take_bit"] == "fee take calm · €0"
    assert g["window_a_closes_fee_take"] == 0.4
    assert g["window_a_closes_fee_take_severity"] == "comfortable"
    assert g["window_a_closes_fee_take_thin"] is False
    assert g["window_a_closes_fee_take_ratio"] == 0.1
    # net wins 24−2=22 ÷ losses 4 → net PF 5.5× strong
    assert g["window_a_closes_net_profit_factor_bit"] == "net PF strong · 5.5×"
    assert g["window_a_closes_net_profit_factor"] == 5.5
    assert g["window_a_closes_net_profit_factor_severity"] == "strong"
    assert g["window_a_closes_net_profit_factor_thin"] is False
    # net 3.6 ÷ take 0.4 → 9× strong (net PF ≠ net÷fee-take)
    assert g["window_a_closes_net_vs_fee_bit"] == "net/fee strong · 9×"
    assert g["window_a_closes_net_vs_fee"] == 9.0
    assert g["window_a_closes_net_vs_fee_severity"] == "strong"
    assert g["window_a_closes_net_vs_fee_thin"] is False
    # WR 80% · payoff 1.5 → f* = 0.8 − 0.2/1.5 ≈ 66.7% strong
    assert g["window_a_closes_kelly_bit"] == "Kelly strong · 66.7%"
    assert g["window_a_closes_kelly_pct"] == 66.7
    assert g["window_a_closes_kelly_severity"] == "strong"
    assert g["window_a_closes_kelly_thin"] is False
    assert g["window_a_closes_kelly_neg"] is False
    assert g["window_a_closes_half_kelly_bit"] == (
        "half-K/sizer over · 33.4% vs 10%"
    )
    assert g["window_a_closes_half_kelly_vs"] == "over"
    assert g["window_a_closes_half_kelly_under"] is False
    assert g["window_a_closes_half_kelly_slot_bit"] == (
        "half-K/slot over · 33.4% vs 20%"
    )
    assert g["window_a_closes_half_kelly_vs_slot"] == "over"
    assert g["window_a_closes_half_kelly_slot_under"] is False
    # half 33.4% vs 30% cap → match (±5pp; slot over ≠ cap match)
    assert g["window_a_closes_half_kelly_cap_bit"] == (
        "half-K/cap match · 33.4% vs 30%"
    )
    assert g["window_a_closes_half_kelly_vs_cap"] == "match"
    assert g["window_a_closes_half_kelly_cap_under"] is False
    # quarter 16.7% vs 30% cap → under (slot match ≠ single-name ceiling)
    assert g["window_a_closes_quarter_kelly_cap_bit"] == (
        "qtr-K/cap under · 16.7% vs 30%"
    )
    assert g["window_a_closes_quarter_kelly_vs_cap"] == "under"
    assert g["window_a_closes_quarter_kelly_cap_under"] is True
    # half over + quarter over sizer → practical sizer (triad ≠ pick)
    assert g["window_a_closes_practical_kelly"] == "sizer"
    assert g["window_a_closes_practical_kelly_pct"] == 10.0
    assert g["window_a_closes_practical_kelly_cut"] is False
    assert g["window_a_closes_practical_kelly_bit"] == "pract-K sizer · 10%"
    assert g["tone"] == "warn"  # qtr-K/cap under
    assert "fees calm" in g["line"]
    assert "4w/1l" not in g["line"]  # polarity stays in fields
    assert "pay · 1.5×" not in g["line"]
    assert f" · {g['window_a_closes_expectancy_bit']}" not in g["line"]
    assert " · PF" not in g["line"]  # gross PF stays in fields
    assert "WR strong · 80%" not in g["line"]  # WR% stays in fields
    assert "WR above BE strong" not in g["line"]  # WR/BE stays in fields
    assert "net exp strong" not in g["line"]  # net stays in fields
    assert "fee take calm · €0" not in g["line"]  # fee take stays in fields
    assert "net PF strong · 5.5×" not in g["line"]  # net PF stays in fields
    assert "net/fee strong · 9×" not in g["line"]  # net/fee stays in fields
    assert "Kelly strong · 66.7%" not in g["line"]  # Kelly stays in fields
    assert "half-K/sizer over · 33.4% vs 10%" not in g["line"]
    assert "half-K/slot over · 33.4% vs 20%" not in g["line"]
    assert "half-K/cap match · 33.4% vs 30%" not in g["line"]  # cap stays in fields
    assert "qtr-K/sizer over · 16.7% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot match · 16.7% vs 20%" not in g["line"]  # slot in fields
    assert "qtr-K/cap under · 16.7% vs 30%" not in g["line"]  # cap in fields
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 5
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 5 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 5 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_payoff_thin() -> None:
    """Nw/Nl alone must not hide thin € payoff (count lean ≠ € lean)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 8,
        "sells": 4,
        "fees": 5.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 35.0,
        "wins": 3,
        "losses": 1,
        "avg_win": 20.0,
        "avg_loss": 40.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_polarity_bit"] == "3w/1l"
    assert g["window_a_closes_polarity"] == "mixed"
    # Count lean mostly wins but € payoff thin.
    assert g["window_a_closes_payoff_bit"] == "pay thin · 0.5×"
    assert g["window_a_closes_payoff_severity"] == "thin"
    assert g["window_a_closes_payoff_thin"] is True
    assert g["window_a_closes_payoff_ratio"] == 0.5
    # 0.75·20 − 0.25·40 = 5.0 → thin vs avg_loss (5/40 < 0.25)
    assert g["window_a_closes_expectancy_bit"] == "exp thin · +€5"
    assert g["window_a_closes_expectancy"] == 5.0
    assert g["window_a_closes_expectancy_thin"] is True
    # gross 60÷40 = 1.5× mid PF
    assert g["window_a_closes_profit_factor_bit"] == "PF · 1.5×"
    assert g["window_a_closes_profit_factor"] == 1.5
    assert g["window_a_closes_profit_factor_thin"] is False
    # 3/4 = 75% → strong WR; BE 66.7% → above mid +8.3pp
    assert g["window_a_closes_win_rate_bit"] == "WR strong · 75%"
    assert g["window_a_closes_win_rate_pct"] == 75.0
    assert g["window_a_closes_win_rate_severity"] == "strong"
    assert g["window_a_closes_wr_vs_be_bit"] == "WR above BE · +8.3pp"
    assert g["window_a_closes_wr_vs_be"] == "above"
    assert g["window_a_closes_wr_edge_pp"] == 8.3
    # net 35÷4 = 8.75 → thin vs avg_loss 40 (8.75/40 < 0.25)
    assert g["window_a_closes_net_expectancy_bit"] == "net exp thin · +€9"
    assert g["window_a_closes_net_expectancy"] == 8.75
    assert g["window_a_closes_net_expectancy_thin"] is True
    # take 5−8.75 = −3.75 → signed −€4 (net > gross; fee take in fields)
    assert g["window_a_closes_fee_take_bit"] == "fee take −€4"
    assert g["window_a_closes_fee_take"] == -3.75
    assert g["window_a_closes_fee_take_thin"] is False
    # net wins 60−5=55 ÷ losses 40 → net PF 1.375 → mid · 1.4×
    assert g["window_a_closes_net_profit_factor_bit"] == "net PF · 1.4×"
    assert g["window_a_closes_net_profit_factor"] == 1.38
    assert g["window_a_closes_net_profit_factor_thin"] is False
    # WR 75% · payoff 0.5 → f* = 0.75 − 0.25/0.5 = 25% strong
    assert g["window_a_closes_kelly_bit"] == "Kelly strong · 25%"
    assert g["window_a_closes_kelly_pct"] == 25.0
    assert g["window_a_closes_kelly_severity"] == "strong"
    assert g["window_a_closes_half_kelly_bit"] == (
        "half-K/sizer match · 12.5% vs 10%"
    )
    assert g["window_a_closes_half_kelly_vs"] == "match"
    assert g["window_a_closes_half_kelly_slot_bit"] == (
        "half-K/slot under · 12.5% vs 20%"
    )
    assert g["window_a_closes_half_kelly_vs_slot"] == "under"
    assert g["window_a_closes_half_kelly_slot_under"] is True
    assert g["window_a_closes_half_kelly_cap_bit"] == (
        "half-K/cap under · 12.5% vs 30%"
    )
    assert g["window_a_closes_half_kelly_vs_cap"] == "under"
    assert g["window_a_closes_half_kelly_cap_under"] is True
    assert g["tone"] == "warn"
    assert "3w/1l" not in g["line"]  # polarity stays in fields
    assert "pay thin" not in g["line"]
    assert f" · {g['window_a_closes_expectancy_bit']}" not in g["line"]
    assert " · PF" not in g["line"]  # gross PF stays in fields
    assert "WR strong · 75%" not in g["line"]  # WR% stays in fields
    assert "WR above BE · +8.3pp" not in g["line"]  # WR/BE stays in fields
    assert "net exp thin" not in g["line"]  # net stays in fields
    assert "fee take −€4" not in g["line"]  # fee take stays in fields
    assert "net PF · 1.4×" not in g["line"]  # net PF stays in fields
    assert "Kelly strong · 25%" not in g["line"]  # Kelly stays in fields
    assert "half-K/sizer match · 12.5% vs 10%" not in g["line"]
    assert "half-K/slot under · 12.5% vs 20%" not in g["line"]
    assert "half-K/cap under · 12.5% vs 30%" not in g["line"]  # cap stays in fields
    assert "qtr-K/sizer match · 6.2% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot under · 6.2% vs 20%" not in g["line"]
    assert "qtr-K/cap under · 6.2% vs 30%" not in g["line"]  # cap stays in fields
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 4
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 4 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 4 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_expectancy_neg() -> None:
    """Payoff alone must not hide negative €/close expectancy."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 2.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 18.0,
        "wins": 1,
        "losses": 4,
        "avg_win": 10.0,
        "avg_loss": 20.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    # 0.2·10 − 0.8·20 = −14 → neg (payoff thin 0.5× also)
    assert g["window_a_closes_payoff_bit"] == "pay thin · 0.5×"
    assert g["window_a_closes_expectancy_bit"] == "exp −€14"
    assert g["window_a_closes_expectancy"] == -14.0
    assert g["window_a_closes_expectancy_neg"] is True
    assert g["window_a_closes_expectancy_thin"] is False
    # gross 10÷80 = 0.125 → thin PF
    assert g["window_a_closes_profit_factor_bit"] == "PF thin · 0.1×"
    assert g["window_a_closes_profit_factor"] == 0.12
    assert g["window_a_closes_profit_factor_thin"] is True
    # 1/5 = 20% → thin WR; BE 66.7% → below −46.7pp
    assert g["window_a_closes_win_rate_bit"] == "WR thin · 20%"
    assert g["window_a_closes_win_rate_pct"] == 20.0
    assert g["window_a_closes_win_rate_thin"] is True
    assert g["window_a_closes_wr_vs_be_bit"] == "WR below BE · -46.7pp"
    assert g["window_a_closes_wr_vs_be"] == "below"
    assert g["window_a_closes_wr_edge_pp"] == -46.7
    assert g["window_a_closes_wr_below_be"] is True
    assert g["window_a_closes_wr_edge_thin"] is True
    # net 18÷5 = 3.6 → thin vs avg_loss 20 (gross− / net+ still speaks)
    assert g["window_a_closes_net_expectancy_bit"] == "net exp thin · +€4"
    assert g["window_a_closes_net_expectancy"] == 3.6
    assert g["window_a_closes_net_expectancy_thin"] is True
    # take −14−3.6 = −17.6 → signed −€18 (gross−; fee take in fields)
    assert g["window_a_closes_fee_take_bit"] == "fee take −€18"
    assert g["window_a_closes_fee_take"] == -17.6
    assert g["window_a_closes_fee_take_thin"] is False
    # net wins 10−2=8 ÷ losses 80 → net PF 0.1× thin
    assert g["window_a_closes_net_profit_factor_bit"] == "net PF thin · 0.1×"
    assert g["window_a_closes_net_profit_factor"] == 0.1
    assert g["window_a_closes_net_profit_factor_thin"] is True
    # WR 20% · payoff 0.5 → f* = 0.2 − 0.8/0.5 = −140% neg
    assert g["window_a_closes_kelly_bit"] == "Kelly neg · −140%"
    assert g["window_a_closes_kelly_pct"] == -140.0
    assert g["window_a_closes_kelly_neg"] is True
    assert g["window_a_closes_half_kelly_bit"] == (
        "half-K/sizer under · −70% vs 10%"
    )
    assert g["window_a_closes_half_kelly_under"] is True
    assert g["tone"] == "warn"
    assert "WR below BE · -46.7pp" not in g["line"]  # WR/BE stays in fields
    assert "WR thin · 20%" not in g["line"]  # WR% stays in fields
    assert " · PF" not in g["line"]  # gross PF stays in fields
    assert "exp −€14" not in g["line"]
    assert "pay thin" not in g["line"]
    assert "sample ready" not in g["line"]
    assert "net exp thin" not in g["line"]  # net stays in fields
    assert "fee take −€18" not in g["line"]  # fee take stays in fields
    assert "net PF thin · 0.1×" not in g["line"]  # net PF stays in fields
    assert "Kelly neg · −140%" not in g["line"]  # Kelly stays in fields
    assert "half-K/sizer under · −70% vs 10%" not in g["line"]
    assert "half-K/slot under · −70% vs 20%" not in g["line"]
    assert "half-K/cap under · −70% vs 30%" not in g["line"]  # cap stays in fields
    assert "qtr-K/sizer under · −35% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot under · −35% vs 20%" not in g["line"]
    assert "qtr-K/cap under · −35% vs 30%" not in g["line"]  # cap stays in fields
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 5
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 5 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 5 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_profit_factor_thin() -> None:
    """Expectancy alone must not hide thin total-€ profit factor."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 2.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 18.0,
        "wins": 2,
        "losses": 3,
        "avg_win": 4.0,
        "avg_loss": 10.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    # payoff 0.4× thin; expectancy 0.4·4−0.6·10 = −4.4 neg
    # gross 8÷30 ≈ 0.27 → thin PF (avg ratio ≠ total € ownership)
    assert g["window_a_closes_payoff_bit"] == "pay thin · 0.4×"
    assert g["window_a_closes_expectancy_neg"] is True
    assert g["window_a_closes_profit_factor_bit"] == "PF thin · 0.3×"
    assert g["window_a_closes_profit_factor"] == 0.27
    assert g["window_a_closes_profit_factor_severity"] == "thin"
    assert g["window_a_closes_profit_factor_thin"] is True
    # 2/5 = 40% → mid WR; BE ≈71.4% → below −31.4pp
    assert g["window_a_closes_win_rate_bit"] == "WR · 40%"
    assert g["window_a_closes_win_rate_pct"] == 40.0
    assert g["window_a_closes_win_rate_thin"] is False
    assert g["window_a_closes_wr_vs_be_bit"] == "WR below BE · -31.4pp"
    assert g["window_a_closes_wr_vs_be"] == "below"
    assert g["window_a_closes_wr_below_be"] is True
    # net 18÷5 = 3.6 → mid vs avg_loss 10 (0.36; not thin <0.25)
    assert g["window_a_closes_net_expectancy_bit"] == "net exp · +€4"
    assert g["window_a_closes_net_expectancy"] == 3.6
    assert g["window_a_closes_net_expectancy_thin"] is False
    # take −4.4−3.6 = −8 → signed −€8 (gross−; fee take in fields)
    assert g["window_a_closes_fee_take_bit"] == "fee take −€8"
    assert g["window_a_closes_fee_take"] == -8.0
    assert g["window_a_closes_fee_take_thin"] is False
    # net wins 8−2=6 ÷ losses 30 → net PF 0.2× thin
    assert g["window_a_closes_net_profit_factor_bit"] == "net PF thin · 0.2×"
    assert g["window_a_closes_net_profit_factor"] == 0.2
    assert g["window_a_closes_net_profit_factor_thin"] is True
    # WR 40% · payoff 0.4 → f* = 0.4 − 0.6/0.4 = −110% neg
    assert g["window_a_closes_kelly_bit"] == "Kelly neg · −110%"
    assert g["window_a_closes_kelly_pct"] == -110.0
    assert g["window_a_closes_kelly_neg"] is True
    assert g["window_a_closes_half_kelly_bit"] == (
        "half-K/sizer under · −55% vs 10%"
    )
    assert g["window_a_closes_half_kelly_under"] is True
    assert g["tone"] == "warn"
    assert "WR below BE · -31.4pp" not in g["line"]
    assert "WR · 40%" not in g["line"]
    assert " · PF" not in g["line"]  # gross PF stays in fields
    assert "exp −" not in g["line"]  # gross expectancy stays in fields
    assert "pay thin" not in g["line"]
    assert "net exp · +€4" not in g["line"]  # net stays in fields
    assert "fee take −€8" not in g["line"]  # fee take stays in fields
    assert "net PF thin · 0.2×" not in g["line"]  # net PF stays in fields
    assert "Kelly neg · −110%" not in g["line"]  # Kelly stays in fields
    assert "half-K/sizer under · −55% vs 10%" not in g["line"]
    assert "half-K/slot under · −55% vs 20%" not in g["line"]
    assert "half-K/cap under · −55% vs 30%" not in g["line"]  # cap stays in fields
    assert "qtr-K/sizer under · −27.5% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot under · −27.5% vs 20%" not in g["line"]
    assert "qtr-K/cap under · −27.5% vs 30%" not in g["line"]  # cap stays in fields
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 5
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 5 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 5 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_rate_thin() -> None:
    """PF alone must not hide thin hit rate (total-€ ≠ win%)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 8,
        "sells": 4,
        "fees": 2.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 38.0,
        "wins": 1,
        "losses": 3,
        "avg_win": 40.0,
        "avg_loss": 5.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    # payoff 8× strong; PF 40÷15 ≈ 2.7× strong; WR 25% thin
    # but BE ≈11.1% → above strong +13.9pp (hit rate thin ≠ below BE)
    assert g["window_a_closes_payoff_bit"] == "pay strong · 8×"
    assert g["window_a_closes_profit_factor_bit"] == "PF strong · 2.7×"
    assert g["window_a_closes_profit_factor_thin"] is False
    assert g["window_a_closes_win_rate_bit"] == "WR thin · 25%"
    assert g["window_a_closes_win_rate_pct"] == 25.0
    assert g["window_a_closes_win_rate_severity"] == "thin"
    assert g["window_a_closes_win_rate_thin"] is True
    assert g["window_a_closes_wr_vs_be_bit"] == "WR above BE strong · +13.9pp"
    assert g["window_a_closes_wr_vs_be"] == "above"
    assert g["window_a_closes_wr_edge_pp"] == 13.9
    assert g["window_a_closes_wr_edge_severity"] == "strong"
    assert g["window_a_closes_wr_below_be"] is False
    # net 38÷4 = 9.5 → strong vs avg_loss 5
    assert g["window_a_closes_net_expectancy_bit"] == "net exp strong · +€10"
    assert g["window_a_closes_net_expectancy"] == 9.5
    assert g["window_a_closes_net_expectancy_severity"] == "strong"
    # exp = 0.25·40 − 0.75·5 = 6.25; take 6.25−9.5 = −3.25 → −€3
    assert g["window_a_closes_fee_take_bit"] == "fee take −€3"
    assert g["window_a_closes_fee_take"] == -3.25
    assert g["window_a_closes_fee_take_thin"] is False
    # net wins 40−2=38 ÷ losses 15 → net PF ≈2.53× strong
    assert g["window_a_closes_net_profit_factor_bit"] == "net PF strong · 2.5×"
    assert g["window_a_closes_net_profit_factor"] == 2.53
    assert g["window_a_closes_net_profit_factor_severity"] == "strong"
    assert g["window_a_closes_net_profit_factor_thin"] is False
    # WR 25% · payoff 8 → f* = 0.25 − 0.75/8 ≈ 15.6% mid
    assert g["window_a_closes_kelly_bit"] == "Kelly · 15.6%"
    assert g["window_a_closes_kelly_pct"] == 15.6
    assert g["window_a_closes_kelly_severity"] == ""
    assert g["window_a_closes_kelly_thin"] is False
    assert g["window_a_closes_half_kelly_bit"] == (
        "half-K/sizer match · 7.8% vs 10%"
    )
    assert g["window_a_closes_half_kelly_vs"] == "match"
    assert g["tone"] == "warn"  # thin WR still warns
    assert "WR above BE strong" not in g["line"]  # WR/BE stays in fields
    assert "WR thin · 25%" not in g["line"]  # WR% stays in fields
    assert " · PF" not in g["line"]  # gross PF stays in fields
    assert "pay strong" not in g["line"]
    assert "sample ready" not in g["line"]
    assert "net exp strong" not in g["line"]  # net stays in fields
    assert "fee take −€3" not in g["line"]  # fee take stays in fields
    assert "net PF strong · 2.5×" not in g["line"]  # net PF stays in fields
    assert "Kelly · 15.6%" not in g["line"]  # Kelly stays in fields
    assert "half-K/sizer match · 7.8% vs 10%" not in g["line"]
    assert "half-K/slot under · 7.8% vs 20%" not in g["line"]
    assert "half-K/cap under · 7.8% vs 30%" not in g["line"]  # cap stays in fields
    assert "qtr-K/sizer under · 3.9% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot under · 3.9% vs 20%" not in g["line"]
    assert "qtr-K/cap under · 3.9% vs 30%" not in g["line"]  # cap stays in fields
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 4
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 4 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 4 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_wr_below_be() -> None:
    """WR% alone must not hide WR below breakeven (payoff-adjusted)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 2.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 18.0,
        "wins": 3,
        "losses": 2,
        "avg_win": 2.0,
        "avg_loss": 10.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    # WR 60% mid/strong band but payoff 0.2× → BE ≈83.3% → below −23.3pp
    assert g["window_a_closes_win_rate_bit"] == "WR strong · 60%"
    assert g["window_a_closes_win_rate_pct"] == 60.0
    assert g["window_a_closes_win_rate_thin"] is False
    assert g["window_a_closes_wr_vs_be_bit"] == "WR below BE · -23.3pp"
    assert g["window_a_closes_wr_vs_be"] == "below"
    assert g["window_a_closes_breakeven_wr_pct"] == 83.3
    assert g["window_a_closes_wr_edge_pp"] == -23.3
    assert g["window_a_closes_wr_below_be"] is True
    assert g["window_a_closes_wr_edge_thin"] is True
    # net 18÷5 = 3.6 → mid vs avg_loss 10 (WR/BE ≠ fee-adjusted €/close)
    assert g["window_a_closes_net_expectancy_bit"] == "net exp · +€4"
    assert g["window_a_closes_net_expectancy"] == 3.6
    assert g["window_a_closes_net_expectancy_thin"] is False
    # exp = 0.6·2 − 0.4·10 = −2.8; take −2.8−3.6 = −6.4 → −€6
    assert g["window_a_closes_fee_take_bit"] == "fee take −€6"
    assert g["window_a_closes_fee_take"] == -6.4
    assert g["window_a_closes_fee_take_thin"] is False
    # net wins 6−2=4 ÷ losses 20 → net PF 0.2× thin
    assert g["window_a_closes_net_profit_factor_bit"] == "net PF thin · 0.2×"
    assert g["window_a_closes_net_profit_factor"] == 0.2
    assert g["window_a_closes_net_profit_factor_thin"] is True
    # WR 60% · payoff 0.2 → f* = 0.6 − 0.4/0.2 = −140% neg
    assert g["window_a_closes_kelly_bit"] == "Kelly neg · −140%"
    assert g["window_a_closes_kelly_pct"] == -140.0
    assert g["window_a_closes_kelly_neg"] is True
    assert g["window_a_closes_half_kelly_bit"] == (
        "half-K/sizer under · −70% vs 10%"
    )
    assert g["window_a_closes_half_kelly_under"] is True
    assert g["tone"] == "warn"
    assert "WR below BE · -23.3pp" not in g["line"]  # WR/BE stays in fields
    assert "WR strong · 60%" not in g["line"]
    assert "pay thin" not in g["line"]
    assert "sample ready" not in g["line"]
    assert "net exp · +€4" not in g["line"]  # net stays in fields
    assert "fee take −€6" not in g["line"]  # fee take stays in fields
    assert "net PF thin · 0.2×" not in g["line"]  # net PF stays in fields
    assert "Kelly neg · −140%" not in g["line"]  # Kelly stays in fields
    assert "half-K/sizer under · −70% vs 10%" not in g["line"]
    assert "half-K/slot under · −70% vs 20%" not in g["line"]
    assert "half-K/cap under · −70% vs 30%" not in g["line"]  # cap stays in fields
    assert "qtr-K/sizer under · −35% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot under · −35% vs 20%" not in g["line"]
    assert "qtr-K/cap under · −35% vs 30%" not in g["line"]  # cap stays in fields
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 5
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 5 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 5 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_polarity_all_loss() -> None:
    """Fee mood alone must not hide an all-loss Window A control book."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 2.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 18.0,
        "wins": 0,
        "losses": 5,
        "avg_win": 0.0,
        "avg_loss": 4.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_polarity_bit"] == "0w/5l"
    assert g["window_a_closes_polarity"] == "all_loss"
    assert g["window_a_closes_all_loss"] is True
    # all_loss → payoff / PF fail-open (needs both sides with positive avgs)
    assert g["window_a_closes_payoff_bit"] == ""
    assert g["window_a_closes_payoff_thin"] is False
    assert g["window_a_closes_profit_factor_bit"] == ""
    assert g["window_a_closes_profit_factor_thin"] is False
    # all-loss → expectancy = −avg_loss; WR 0% thin; no payoff → WR vs BE
    # silent; net 18÷5 = 3.6 → strong owns the clip (gross− ≠ fee-adj net)
    assert g["window_a_closes_expectancy_bit"] == "exp −€4"
    assert g["window_a_closes_expectancy"] == -4.0
    assert g["window_a_closes_expectancy_neg"] is True
    assert g["window_a_closes_win_rate_bit"] == "WR thin · 0%"
    assert g["window_a_closes_win_rate_pct"] == 0.0
    assert g["window_a_closes_win_rate_thin"] is True
    assert g["window_a_closes_wr_vs_be_bit"] == ""
    assert g["window_a_closes_wr_vs_be"] == ""
    assert g["window_a_closes_wr_below_be"] is False
    assert g["window_a_closes_net_expectancy_bit"] == "net exp strong · +€4"
    assert g["window_a_closes_net_expectancy"] == 3.6
    assert g["window_a_closes_net_expectancy_severity"] == "strong"
    # take −4−3.6 = −7.6 → signed −€8 (gross−; fee take owns clip —
    # net PF silent when wins side is empty)
    assert g["window_a_closes_fee_take_bit"] == "fee take −€8"
    assert g["window_a_closes_fee_take"] == -7.6
    assert g["window_a_closes_fee_take_thin"] is False
    assert g["window_a_closes_net_profit_factor_bit"] == ""
    assert g["window_a_closes_net_profit_factor"] is None
    assert g["window_a_closes_net_profit_factor_thin"] is False
    # all-loss → no payoff → Kelly fail-open silent
    assert g["window_a_closes_kelly_bit"] == ""
    assert g["window_a_closes_kelly_pct"] is None
    assert g["window_a_closes_kelly_thin"] is False
    assert g["window_a_closes_kelly_neg"] is False
    assert g["tone"] == "warn"  # all-loss / thin WR escalate
    assert "0w/5l" not in g["line"]  # polarity stays in fields
    assert "fees calm" in g["line"]
    assert "WR thin · 0%" not in g["line"]  # WR% stays in fields
    assert "WR above BE" not in g["line"]
    assert "WR below BE" not in g["line"]
    assert "exp −€4" not in g["line"]
    assert "net exp strong" not in g["line"]  # net stays in fields
    assert "fee take −€8" in g["line"]
    assert "net PF" not in g["line"]
    assert "Kelly" not in g["line"]
    assert "sample ready" not in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_fee_take_thin() -> None:
    """Net expect alone must not hide thin fee take (gross − net €/close)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 8,
        "sells": 4,
        "fees": 190.0,
        "realized_pnl": 200.0,
        "net_after_all_fees": 10.0,
        "wins": 3,
        "losses": 1,
        "avg_win": 80.0,
        "avg_loss": 40.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    # gross 50, net 2.5 → take 47.5 thin (0.95 ≥ 0.5)
    assert g["window_a_closes_net_expectancy_bit"] == "net exp thin · +€2"
    assert g["window_a_closes_net_expectancy"] == 2.5
    assert g["window_a_closes_fee_take_bit"] == "fee take thin · €48"
    assert g["window_a_closes_fee_take"] == 47.5
    assert g["window_a_closes_fee_take_thin"] is True
    assert g["window_a_closes_fee_take_severity"] == "thin"
    assert g["window_a_closes_fee_take_ratio"] == 0.95
    # net wins 240−190=50 ÷ losses 40 → net PF 1.25× mid (fee take ≠ net PF)
    assert g["window_a_closes_net_profit_factor_bit"] == "net PF · 1.2×"
    assert g["window_a_closes_net_profit_factor"] == 1.25
    assert g["window_a_closes_net_profit_factor_thin"] is False
    # net 2.5 ÷ take 47.5 → 0.05× thin (net PF mid ≠ remaining edge multiples)
    assert g["window_a_closes_net_vs_fee_bit"] == "net/fee thin · 0.1×"
    assert g["window_a_closes_net_vs_fee"] == 0.05
    assert g["window_a_closes_net_vs_fee_thin"] is True
    assert g["window_a_closes_net_vs_fee_severity"] == "thin"
    # WR 75% · payoff 2 → Kelly 62.5% strong (net/fee thin ≠ size fraction)
    assert g["window_a_closes_kelly_bit"] == "Kelly strong · 62.5%"
    assert g["window_a_closes_kelly_pct"] == 62.5
    assert g["window_a_closes_kelly_severity"] == "strong"
    assert g["window_a_closes_kelly_thin"] is False
    # half 31.2% vs 10% → over (Kelly alone ≠ cash sizer)
    assert g["window_a_closes_half_kelly_bit"] == (
        "half-K/sizer over · 31.2% vs 10%"
    )
    assert g["window_a_closes_half_kelly_vs"] == "over"
    assert g["window_a_closes_half_kelly_under"] is False
    assert g["tone"] == "warn"  # thin fee take / thin net/fee warn
    assert "net exp thin" not in g["line"]
    assert "fee take thin · €48" not in g["line"]  # fee take stays in fields
    assert "net PF · 1.2×" not in g["line"]  # net PF stays in fields
    assert "net/fee thin · 0.1×" not in g["line"]  # net/fee stays in fields
    assert "Kelly strong · 62.5%" not in g["line"]  # Kelly stays in fields
    assert "half-K/sizer over · 31.2% vs 10%" not in g["line"]
    assert "half-K/slot over · 31.2% vs 20%" not in g["line"]
    assert "half-K/cap match · 31.2% vs 30%" not in g["line"]  # cap stays in fields
    assert "qtr-K/sizer over · 15.6% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot match · 15.6% vs 20%" not in g["line"]
    assert "qtr-K/cap under · 15.6% vs 30%" not in g["line"]  # cap stays in fields
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 4
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 4 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 4 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_net_vs_fee_thin() -> None:
    """Net PF alone must not hide thin net÷fee-take remaining edge."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 8,
        "sells": 4,
        "fees": 10.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 10.0,
        "wins": 3,
        "losses": 1,
        "avg_win": 80.0,
        "avg_loss": 40.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    # gross exp 50; net 2.5 → take 47.5; 2.5÷47.5 → 0.05× thin
    assert g["window_a_closes_net_expectancy"] == 2.5
    assert g["window_a_closes_fee_take"] == 47.5
    assert g["window_a_closes_net_vs_fee"] == 0.05
    assert g["window_a_closes_net_vs_fee_bit"] == "net/fee thin · 0.1×"
    assert g["window_a_closes_net_vs_fee_thin"] is True
    assert g["window_a_closes_net_vs_fee_severity"] == "thin"
    assert g["window_a_closes_kelly_bit"] == "Kelly strong · 62.5%"
    assert g["window_a_closes_half_kelly_bit"] == (
        "half-K/sizer over · 31.2% vs 10%"
    )
    assert g["tone"] == "warn"
    assert "net PF" not in g["line"]  # net PF stays in fields
    assert "net/fee thin · 0.1×" not in g["line"]  # net/fee stays in fields
    assert "Kelly strong · 62.5%" not in g["line"]  # Kelly stays in fields
    assert "half-K/sizer over · 31.2% vs 10%" not in g["line"]
    assert "half-K/slot over · 31.2% vs 20%" not in g["line"]
    assert "half-K/cap match · 31.2% vs 30%" not in g["line"]  # cap stays in fields
    assert "qtr-K/sizer over · 15.6% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot match · 15.6% vs 20%" not in g["line"]
    assert "qtr-K/cap under · 15.6% vs 30%" not in g["line"]  # cap stays in fields
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 4
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 4 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 4 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_net_pf_eats_edge() -> None:
    """Fee take alone must not hide fees-eat net PF (gross PF ≠ fee-adj)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 8,
        "sells": 4,
        "fees": 250.0,
        "realized_pnl": 200.0,
        "net_after_all_fees": -50.0,
        "wins": 3,
        "losses": 1,
        "avg_win": 80.0,
        "avg_loss": 40.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    # gross PF 6×; fees wipe wins → fees eat PF
    assert g["window_a_closes_profit_factor_bit"] == "PF strong · 6×"
    assert g["window_a_closes_net_profit_factor_bit"] == "net PF · fees eat PF"
    assert g["window_a_closes_net_profit_factor"] is None
    assert g["window_a_closes_net_profit_factor_eats_edge"] is True
    assert g["window_a_closes_net_profit_factor_thin"] is True
    # net ≤ 0 → net/fee silent; Kelly + half-K still speak from WR+payoff
    assert g["window_a_closes_net_vs_fee_bit"] == ""
    assert g["window_a_closes_net_vs_fee"] is None
    assert g["window_a_closes_kelly_bit"] == "Kelly strong · 62.5%"
    assert g["window_a_closes_half_kelly_bit"] == (
        "half-K/sizer over · 31.2% vs 10%"
    )
    assert g["tone"] == "warn"
    assert " · PF" not in g["line"]  # gross PF stays in fields
    assert "fee take" not in g["line"]
    assert "net/fee" not in g["line"]
    assert "net PF · fees eat PF" not in g["line"]  # net PF stays in fields
    assert "Kelly strong · 62.5%" not in g["line"]  # Kelly stays in fields
    assert "half-K/sizer over · 31.2% vs 10%" not in g["line"]
    assert "half-K/slot over · 31.2% vs 20%" not in g["line"]
    assert "half-K/cap match · 31.2% vs 30%" not in g["line"]  # cap stays in fields
    assert "qtr-K/sizer over · 15.6% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot match · 15.6% vs 20%" not in g["line"]
    assert "qtr-K/cap under · 15.6% vs 30%" not in g["line"]  # cap stays in fields
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 4
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 4 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 4 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_kelly_thin() -> None:
    """Net/fee alone must not hide thin full-Kelly size fraction."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 2.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 18.0,
        "wins": 5,
        "losses": 5,
        "avg_win": 11.0,
        "avg_loss": 10.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    # 50% WR · payoff 1.1 → f* = 0.5 − 0.5/1.1 ≈ 4.5% thin
    assert g["window_a_closes_kelly_bit"] == "Kelly thin · 4.5%"
    assert g["window_a_closes_kelly_pct"] == 4.5
    assert g["window_a_closes_kelly_severity"] == "thin"
    assert g["window_a_closes_kelly_thin"] is True
    assert g["window_a_closes_kelly_neg"] is False
    # half 2.2% vs 10% → under; vs 20% slot → under; vs 30% cap → under
    # (K-sample owns clip; pract stays in fields)
    assert g["window_a_closes_half_kelly_bit"] == (
        "half-K/sizer under · 2.2% vs 10%"
    )
    assert g["window_a_closes_half_kelly_pct"] == 2.2
    assert g["window_a_closes_half_kelly_sizer_pct"] == 10.0
    assert g["window_a_closes_half_kelly_vs"] == "under"
    assert g["window_a_closes_half_kelly_under"] is True
    assert g["window_a_closes_half_kelly_slot_bit"] == (
        "half-K/slot under · 2.2% vs 20%"
    )
    assert g["window_a_closes_half_kelly_slot_pct"] == 20.0
    assert g["window_a_closes_half_kelly_vs_slot"] == "under"
    assert g["window_a_closes_half_kelly_slot_under"] is True
    assert g["window_a_closes_half_kelly_cap_bit"] == (
        "half-K/cap under · 2.2% vs 30%"
    )
    assert g["window_a_closes_half_kelly_cap_pct"] == 30.0
    assert g["window_a_closes_half_kelly_vs_cap"] == "under"
    assert g["window_a_closes_half_kelly_cap_under"] is True
    assert g["tone"] == "warn"  # thin Kelly / under sizer / slot / cap
    assert "net/fee" not in g["line"]  # net/fee stays in fields
    assert "Kelly thin · 4.5%" not in g["line"]  # Kelly stays in fields
    assert "half-K/sizer under · 2.2% vs 10%" not in g["line"]
    assert "half-K/slot under · 2.2% vs 20%" not in g["line"]
    assert "half-K/cap under · 2.2% vs 30%" not in g["line"]  # cap stays in fields
    assert "qtr-K/sizer under · 1.1% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot under · 1.1% vs 20%" not in g["line"]
    assert "qtr-K/cap under · 1.1% vs 30%" not in g["line"]  # cap stays in fields
    assert g["window_a_closes_kelly_sample"] == "ok"
    assert g["window_a_closes_kelly_sample_n"] == 10
    assert g["window_a_closes_kelly_sample_thin"] is False
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample ok · 10 closes"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample ok · 10 closes" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_half_kelly_under() -> None:
    """Full Kelly alone must not hide half-Kelly under the cash sizer."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 2.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 18.0,
        "wins": 5,
        "losses": 5,
        "avg_win": 11.0,
        "avg_loss": 10.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_kelly_pct"] == 4.5
    assert g["window_a_closes_half_kelly_under"] is True
    assert g["window_a_closes_half_kelly_vs"] == "under"
    assert g["window_a_closes_half_kelly_bit"] == (
        "half-K/sizer under · 2.2% vs 10%"
    )
    assert g["window_a_closes_half_kelly_slot_under"] is True
    assert g["window_a_closes_half_kelly_vs_slot"] == "under"
    assert g["window_a_closes_half_kelly_slot_bit"] == (
        "half-K/slot under · 2.2% vs 20%"
    )
    assert g["window_a_closes_half_kelly_cap_under"] is True
    assert g["window_a_closes_half_kelly_vs_cap"] == "under"
    assert g["window_a_closes_half_kelly_cap_bit"] == (
        "half-K/cap under · 2.2% vs 30%"
    )
    assert g["tone"] == "warn"
    assert "Kelly thin" not in g["line"]
    assert "half-K/sizer under · 2.2% vs 10%" not in g["line"]
    assert "half-K/slot under · 2.2% vs 20%" not in g["line"]
    assert "half-K/cap under · 2.2% vs 30%" not in g["line"]  # cap stays in fields
    assert "qtr-K/sizer under · 1.1% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot under · 1.1% vs 20%" not in g["line"]
    assert "qtr-K/cap under · 1.1% vs 30%" not in g["line"]  # cap stays in fields
    assert g["window_a_closes_kelly_sample"] == "ok"
    assert g["window_a_closes_kelly_sample_n"] == 10
    assert g["window_a_closes_kelly_sample_thin"] is False
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample ok · 10 closes"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample ok · 10 closes" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_half_kelly_slot_under() -> None:
    """Cash-sizer match alone must not hide half-Kelly under equal slot."""
    as_of = date(2026, 8, 18)
    # 50% WR · payoff 2 → Kelly 25 → half 12.5 vs 10 match · vs 20 under
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 2.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 18.0,
        "wins": 2,
        "losses": 2,
        "avg_win": 40.0,
        "avg_loss": 20.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_kelly_pct"] == 25.0
    assert g["window_a_closes_half_kelly_pct"] == 12.5
    assert g["window_a_closes_half_kelly_vs"] == "match"
    assert g["window_a_closes_half_kelly_under"] is False
    assert g["window_a_closes_half_kelly_bit"] == (
        "half-K/sizer match · 12.5% vs 10%"
    )
    assert g["window_a_closes_half_kelly_vs_slot"] == "under"
    assert g["window_a_closes_half_kelly_slot_under"] is True
    assert g["window_a_closes_half_kelly_slot_bit"] == (
        "half-K/slot under · 12.5% vs 20%"
    )
    assert g["window_a_closes_half_kelly_vs_cap"] == "under"
    assert g["window_a_closes_half_kelly_cap_under"] is True
    assert g["window_a_closes_half_kelly_cap_bit"] == (
        "half-K/cap under · 12.5% vs 30%"
    )
    assert g["tone"] == "warn"
    assert "half-K/sizer match · 12.5% vs 10%" not in g["line"]
    assert "half-K/slot under · 12.5% vs 20%" not in g["line"]
    assert "half-K/cap under · 12.5% vs 30%" not in g["line"]  # cap stays in fields
    assert "qtr-K/sizer match · 6.2% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot under · 6.2% vs 20%" not in g["line"]
    assert "qtr-K/cap under · 6.2% vs 30%" not in g["line"]  # cap stays in fields
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 4
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 4 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 4 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_half_kelly_cap_under() -> None:
    """Equal-slot match alone must not hide half-Kelly under conc cap."""
    as_of = date(2026, 8, 18)
    # 60% WR · payoff 2 → Kelly 40 → half 20 vs 10 over · vs 20 match ·
    # vs 30 under
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 4.0,
        "realized_pnl": 16.0,
        "net_after_all_fees": 12.0,
        "wins": 3,
        "losses": 2,
        "avg_win": 8.0,
        "avg_loss": 4.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_kelly_pct"] == 40.0
    assert g["window_a_closes_half_kelly_pct"] == 20.0
    assert g["window_a_closes_half_kelly_vs_slot"] == "match"
    assert g["window_a_closes_half_kelly_slot_under"] is False
    assert g["window_a_closes_half_kelly_vs_cap"] == "under"
    assert g["window_a_closes_half_kelly_cap_under"] is True
    assert g["window_a_closes_half_kelly_cap_bit"] == (
        "half-K/cap under · 20% vs 30%"
    )
    assert g["window_a_closes_quarter_kelly_vs"] == "match"
    assert g["window_a_closes_quarter_kelly_under"] is False
    assert g["window_a_closes_quarter_kelly_vs_slot"] == "under"
    assert g["window_a_closes_quarter_kelly_slot_under"] is True
    assert g["window_a_closes_quarter_kelly_slot_bit"] == (
        "qtr-K/slot under · 10% vs 20%"
    )
    assert g["window_a_closes_quarter_kelly_vs_cap"] == "under"
    assert g["window_a_closes_quarter_kelly_cap_under"] is True
    assert g["window_a_closes_quarter_kelly_cap_bit"] == (
        "qtr-K/cap under · 10% vs 30%"
    )
    assert g["tone"] == "warn"
    assert "half-K/slot match · 20% vs 20%" not in g["line"]
    assert "half-K/cap under · 20% vs 30%" not in g["line"]  # cap stays in fields
    assert "qtr-K/sizer match · 10% vs 10%" not in g["line"]  # sizer in fields
    assert "qtr-K/slot under · 10% vs 20%" not in g["line"]  # slot in fields
    assert "qtr-K/cap under · 10% vs 30%" not in g["line"]  # cap stays in fields
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 5
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 5 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 5 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_quarter_kelly_cap_under() -> None:
    """Quarter-Kelly under name cap → warn on calm glance; slot stays in fields."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 4.0,
        "realized_pnl": 16.0,
        "net_after_all_fees": 12.0,
        "wins": 3,
        "losses": 2,
        "avg_win": 8.0,
        "avg_loss": 4.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_quarter_kelly_pct"] == 10.0
    assert g["window_a_closes_quarter_kelly_vs_slot"] == "under"
    assert g["window_a_closes_quarter_kelly_slot_under"] is True
    assert g["window_a_closes_quarter_kelly_vs_cap"] == "under"
    assert g["window_a_closes_quarter_kelly_cap_under"] is True
    assert g["window_a_closes_quarter_kelly_cap_bit"] == (
        "qtr-K/cap under · 10% vs 30%"
    )
    assert g["tone"] == "warn"
    assert "qtr-K/slot under · 10% vs 20%" not in g["line"]
    assert "qtr-K/cap under · 10% vs 30%" not in g["line"]  # cap stays in fields
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 5
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 5 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 5 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_practical_kelly() -> None:
    """Practical Kelly still in fields; K-sample thin owns the calm clip."""
    as_of = date(2026, 8, 18)
    # 60% WR · payoff 2 → Kelly 40 → half over · quarter match → pract quarter
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 4.0,
        "realized_pnl": 16.0,
        "net_after_all_fees": 12.0,
        "wins": 3,
        "losses": 2,
        "avg_win": 8.0,
        "avg_loss": 4.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_practical_kelly"] == "quarter"
    assert g["window_a_closes_practical_kelly_pct"] == 10.0
    assert g["window_a_closes_practical_kelly_cut"] is False
    assert g["window_a_closes_practical_kelly_bit"] == "pract-K quarter · 10%"
    assert g["window_a_closes_quarter_kelly_cap_under"] is True
    assert g["tone"] == "warn"  # qtr-K/cap under still warns
    assert "qtr-K/cap under · 10% vs 30%" not in g["line"]
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 5
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample thin · 5 closes <10"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample thin · 5 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_practical_kelly_cut() -> None:
    """Half · cut warns via fields; K-sample ok owns clip when n≥10."""
    as_of = date(2026, 8, 18)
    # 50% WR · payoff 1.1 → thin Kelly → half under sizer → pract half · cut
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 2.0,
        "realized_pnl": 20.0,
        "net_after_all_fees": 18.0,
        "wins": 5,
        "losses": 5,
        "avg_win": 11.0,
        "avg_loss": 10.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_practical_kelly"] == "half"
    assert g["window_a_closes_practical_kelly_cut"] is True
    assert g["window_a_closes_practical_kelly_bit"] == (
        "pract-K half · cut · 2.2%"
    )
    assert g["tone"] == "warn"
    assert "qtr-K/cap under" not in g["line"]
    assert g["window_a_closes_kelly_sample"] == "ok"
    assert g["window_a_closes_kelly_sample_n"] == 10
    assert g["window_a_closes_kelly_sample_thin"] is False
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample ok · 10 closes"
    assert "pract-K" not in g["line"]  # pract stays in fields
    assert "K-sample ok · 10 closes" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_kelly_sample_thin() -> None:
    """pract-K alone must not hide that Kelly from few closes is a thin size sample."""
    as_of = date(2026, 8, 18)
    # 5 decided closes < Kelly sample floor of 10
    stats = {
        "trades": 12,
        "buys": 7,
        "sells": 5,
        "fees": 4.0,
        "realized_pnl": 16.0,
        "net_after_all_fees": 12.0,
        "wins": 3,
        "losses": 2,
        "avg_win": 8.0,
        "avg_loss": 4.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_practical_kelly_bit"] == "pract-K quarter · 10%"
    assert g["window_a_closes_kelly_sample"] == "thin"
    assert g["window_a_closes_kelly_sample_n"] == 5
    assert g["window_a_closes_kelly_sample_thin"] is True
    assert g["window_a_closes_kelly_sample_bit"] == (
        "K-sample thin · 5 closes <10"
    )
    assert g["tone"] == "warn"
    assert "pract-K" not in g["line"]
    assert "K-sample thin · 5 closes <10" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_kelly_sample_ok() -> None:
    """≥10 decided closes speaks K-sample ok; pract stays in fields (no thin warn)."""
    as_of = date(2026, 8, 18)
    # Strong edge so pract is quarter (not cut); 12 decided → sample ok
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_kelly_sample"] == "ok"
    assert g["window_a_closes_kelly_sample_n"] == 12
    assert g["window_a_closes_kelly_sample_thin"] is False
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample ok · 12 closes"
    assert g["window_a_closes_practical_kelly_bit"]
    assert "pract-K" not in g["line"]
    assert "K-sample ok · 12 closes" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_sell_sessions_few() -> None:
    """K-sample alone must not hide a same-day sell-session cluster (warn)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "sell_sessions": 2,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample ok · 12 closes"
    assert g["window_a_closes_sell_sessions"] == "few"
    assert g["window_a_closes_sell_sessions_n"] == 2
    assert g["window_a_closes_sell_sessions_few"] is True
    assert g["window_a_closes_sell_sessions_bit"] == "sessions few · 2 days <5"
    assert g["window_a_closes_kelly_vs_sessions"] == "clash"
    assert g["window_a_closes_kelly_vs_sessions_clash"] is True
    assert g["window_a_closes_kelly_vs_sessions_bit"] == (
        "K/sess clash · ok · few"
    )
    assert g["window_a_closes_per_day"] == "fat"
    assert g["window_a_closes_per_day_n"] == 6.0
    assert g["window_a_closes_per_day_fat"] is True
    assert g["window_a_closes_per_day_bit"] == "closes/day fat · 6.0×"
    assert g["window_a_closes_sessions_vs_per_day"] == "align"
    assert g["window_a_closes_sessions_vs_per_day_clash"] is False
    assert g["window_a_closes_sessions_vs_per_day_bit"] == (
        "sess/day align · few · fat"
    )
    assert g["window_a_closes_ksess_vs_sessday"] == "clash"
    assert g["window_a_closes_ksess_vs_sessday_clash"] is True
    assert g["window_a_closes_ksess_vs_sessday_bit"] == (
        "K↔d clash · K clash · s align"
    )
    assert g["window_a_closes_kelly_vs_per_day"] == "clash"
    assert g["window_a_closes_kelly_vs_per_day_clash"] is True
    assert g["window_a_closes_kelly_vs_per_day_bit"] == (
        "K/day clash · ok · fat"
    )
    assert g["window_a_closes_kday_vs_kd"] == "align"
    assert g["window_a_closes_kday_vs_kd_clash"] is True
    assert g["window_a_closes_kday_vs_kd_bit"] == (
        "Kd↔ align · both clash"
    )
    assert g["tone"] == "warn"
    assert "K-sample" not in g["line"]
    assert "sessions few" not in g["line"]
    assert "closes/day fat" not in g["line"]
    assert "sess/day align · few · fat" not in g["line"]
    assert "K↔d clash · K clash · s align" not in g["line"]
    assert "K/day clash · ok · fat" not in g["line"]
    assert "Kd↔ align · both clash" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_sell_sessions_ok() -> None:
    """≥5 UTC sell days; Kd↔ lean owns clip after K/day + K↔d agree."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "sell_sessions": 8,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_sell_sessions"] == "ok"
    assert g["window_a_closes_sell_sessions_n"] == 8
    assert g["window_a_closes_sell_sessions_few"] is False
    assert g["window_a_closes_sell_sessions_bit"] == "sessions ok · 8 days"
    assert g["window_a_closes_kelly_vs_sessions"] == "align"
    assert g["window_a_closes_kelly_vs_sessions_clash"] is False
    assert g["window_a_closes_kelly_vs_sessions_bit"] == "K/sess align · ok"
    assert g["window_a_closes_per_day"] == "ok"
    assert g["window_a_closes_per_day_n"] == 1.5
    assert g["window_a_closes_per_day_fat"] is False
    assert g["window_a_closes_per_day_bit"] == "closes/day ok · 1.5×"
    assert g["window_a_closes_sessions_vs_per_day"] == "align"
    assert g["window_a_closes_sessions_vs_per_day_clash"] is False
    assert g["window_a_closes_sessions_vs_per_day_bit"] == "sess/day align · ok"
    assert g["window_a_closes_ksess_vs_sessday"] == "align"
    assert g["window_a_closes_ksess_vs_sessday_clash"] is False
    assert g["window_a_closes_ksess_vs_sessday_bit"] == (
        "K↔d align · both align"
    )
    assert g["window_a_closes_kelly_vs_per_day"] == "align"
    assert g["window_a_closes_kelly_vs_per_day_clash"] is False
    assert g["window_a_closes_kelly_vs_per_day_bit"] == "K/day align · ok"
    assert g["window_a_closes_kday_vs_kd"] == "align"
    assert g["window_a_closes_kday_vs_kd_clash"] is False
    assert g["window_a_closes_kday_vs_kd_bit"] == (
        "Kd↔ align · both align"
    )
    assert "K-sample" not in g["line"]
    assert "sessions ok" not in g["line"]
    assert "K/sess align" not in g["line"]
    assert "closes/day ok" not in g["line"]
    assert "sess/day align" not in g["line"]
    assert "K↔d align · both align" not in g["line"]
    assert "K/day align · ok" not in g["line"]
    assert "Kd↔ align · both align" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_quiet() -> None:
    """K-sample alone must not hide a quiet ending loss streak."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 1,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak"] == 1
    assert g["window_a_closes_loss_streak_hot"] is False
    assert g["window_a_closes_loss_streak_bit"] == "loss quiet · 1"
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample ok · 12 closes"
    assert "K-sample" not in g["line"]  # K-sample stays in fields
    assert "loss quiet · 1" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_hot() -> None:
    """K-sample alone must not hide a hot ending loss streak (warn)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 3,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak"] == 3
    assert g["window_a_closes_loss_streak_hot"] is True
    assert g["window_a_closes_loss_streak_bit"] == "loss hot · 3"
    assert g["window_a_closes_loss_streak_max_bit"] == ""
    assert g["tone"] == "warn"
    assert g["window_a_closes_kelly_sample_bit"] == "K-sample ok · 12 closes"
    assert "K-sample" not in g["line"]  # K-sample stays in fields
    assert "loss hot · 3" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_max_quiet() -> None:
    """Ending loss alone must not hide a quieter peak > ending."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 1,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak"] == 0
    assert g["window_a_closes_loss_streak_bit"] == "loss quiet · 0"
    assert g["window_a_closes_loss_streak_max"] == 1
    assert g["window_a_closes_loss_streak_max_hot"] is False
    assert g["window_a_closes_loss_streak_max_bit"] == "loss max · 1"
    assert "loss quiet" not in g["line"]  # ending stays in fields
    assert "loss max · 1" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_max_hot() -> None:
    """Ending quiet alone must not hide a hot earlier peak (warn)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak"] == 0
    assert g["window_a_closes_loss_streak_hot"] is False
    assert g["window_a_closes_loss_streak_bit"] == "loss quiet · 0"
    assert g["window_a_closes_loss_streak_max"] == 3
    assert g["window_a_closes_loss_streak_max_hot"] is True
    assert g["window_a_closes_loss_streak_max_bit"] == "loss max · 3"
    assert g["tone"] == "warn"
    assert "loss quiet" not in g["line"]  # ending stays in fields
    assert "loss max · 3" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_max_equal_silent() -> None:
    """Equal peak and ending stay silent on max (ending still speaks)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 2,
        "loss_streak_max": 2,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak"] == 2
    assert g["window_a_closes_loss_streak_hot"] is True
    assert g["window_a_closes_loss_streak_bit"] == "loss hot · 2"
    assert g["window_a_closes_loss_streak_max"] is None
    assert g["window_a_closes_loss_streak_max_bit"] == ""
    assert g["window_a_closes_loss_streak_max_hot"] is False
    assert "loss max" not in g["line"]
    assert "loss hot · 2" in g["line"]
    assert g["tone"] == "warn"
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_quiet() -> None:
    """Loss alone must not hide a quiet ending win streak."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 1,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak"] == 1
    assert g["window_a_closes_win_streak_hot"] is False
    assert g["window_a_closes_win_streak_bit"] == "win quiet · 1"
    assert g["window_a_closes_loss_streak_bit"] == "loss quiet · 0"
    assert "loss quiet" not in g["line"]  # ending loss stays in fields
    assert "win quiet · 1" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_hot() -> None:
    """Loss alone must not hide a hot ending win streak (speaks, no warn)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
    }
    without = build_calm_streak_glance(
        runtime, as_of=as_of, window_stats=base
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "win_streak": 3},
    )
    assert g["window_a_closes_win_streak"] == 3
    assert g["window_a_closes_win_streak_hot"] is True
    assert g["window_a_closes_win_streak_bit"] == "win hot · 3"
    assert g["window_a_closes_loss_streak_bit"] == "loss quiet · 0"
    # Hot win speaks but must not escalate tone vs the same book without it.
    assert g["tone"] == without["tone"]
    assert "loss quiet" not in g["line"]  # ending loss stays in fields
    assert "win hot · 3" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_drops_loss_max() -> None:
    """When loss max already spoke, win streak owns the clip (max stays in fields)."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_max_bit"] == "loss max · 1"
    assert g["window_a_closes_win_streak"] == 2
    assert g["window_a_closes_win_streak_hot"] is True
    assert g["window_a_closes_win_streak_bit"] == "win hot · 2"
    assert "loss max" not in g["line"]  # max stays in fields
    assert "win hot · 2" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_max_quiet() -> None:
    """Ending win alone must not hide a quieter peak > ending."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 1,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak"] == 0
    assert g["window_a_closes_win_streak_bit"] == "win quiet · 0"
    assert g["window_a_closes_win_streak_max"] == 1
    assert g["window_a_closes_win_streak_max_hot"] is False
    assert g["window_a_closes_win_streak_max_bit"] == "win max · 1"
    assert "win quiet" not in g["line"]  # ending stays in fields
    assert "win max · 1" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_max_hot() -> None:
    """Ending win alone must not hide a hotter peak (speaks, no warn)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
    }
    without = build_calm_streak_glance(
        runtime, as_of=as_of, window_stats=base
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "win_streak_max": 3},
    )
    assert g["window_a_closes_win_streak"] == 0
    assert g["window_a_closes_win_streak_max"] == 3
    assert g["window_a_closes_win_streak_max_hot"] is True
    assert g["window_a_closes_win_streak_max_bit"] == "win max · 3"
    # Hot win max speaks but must not escalate tone vs the same book without it.
    assert g["tone"] == without["tone"]
    assert "win quiet" not in g["line"]  # ending stays in fields
    assert "win max · 3" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_max_equal_silent() -> None:
    """Equal peak stays silent — ending already owns the clip."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 2,
        "win_streak_max": 2,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak"] == 2
    assert g["window_a_closes_win_streak_bit"] == "win hot · 2"
    assert g["window_a_closes_win_streak_max"] is None
    assert g["window_a_closes_win_streak_max_bit"] == ""
    assert g["window_a_closes_win_streak_max_hot"] is False
    assert "win max" not in g["line"]
    assert "win hot · 2" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_flat_warns() -> None:
    """Win max alone must not hide zero-P&L sells in the sell meter."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
    }
    without = build_calm_streak_glance(
        runtime, as_of=as_of, window_stats=base
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "flat_closes": 2},
    )
    assert g["window_a_closes_win_streak_max"] == 3
    assert g["window_a_closes_win_streak_max_bit"] == "win max · 3"
    assert g["window_a_closes_flat"] == 2
    assert g["window_a_closes_flat_warn"] is True
    assert g["window_a_closes_flat_bit"] == "flats · 2"
    assert g["tone"] == "warn"
    assert without["tone"] != "warn" or "flats" not in without["line"]
    assert "win max" not in g["line"]  # peak stays in fields
    assert "flats · 2" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_flat_zero_silent() -> None:
    """Zero flats stay silent — sell meter already matches decided closes."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_flat"] is None
    assert g["window_a_closes_flat_bit"] == ""
    assert g["window_a_closes_flat_warn"] is False
    assert "flats" not in g["line"]
    assert "win max · 3" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_flat_missing_fail_open() -> None:
    """Missing flat_closes key fails open — do not invent a warn."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_flat"] is None
    assert g["window_a_closes_flat_bit"] == ""
    assert g["window_a_closes_flat_warn"] is False
    assert "flats" not in g["line"]
    assert "win max · 3" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_mean_hot() -> None:
    """Peak/ending alone must not hide a hot typical loss-run (≥2 runs)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 1.0,
        "loss_streak_runs": 2,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            k: v
            for k, v in base.items()
            if k not in ("loss_streak_mean", "loss_streak_runs")
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "loss_streak_mean": 2.5},
    )
    assert g["window_a_closes_win_streak_max"] == 3
    assert g["window_a_closes_win_streak_max_bit"] == "win max · 3"
    assert g["window_a_closes_loss_streak_mean"] == 2.5
    assert g["window_a_closes_loss_streak_runs"] == 2
    assert g["window_a_closes_loss_streak_mean_hot"] is True
    assert g["window_a_closes_loss_streak_mean_bit"] == (
        "loss mean · 2.5 · 2 runs"
    )
    assert g["tone"] == "warn"
    # Book may already warn (e.g. qtr-K under); mean must still own the clip.
    assert "loss mean" not in without["line"]
    assert "win max" not in g["line"]  # peak stays in fields
    assert "loss mean · 2.5 · 2 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_mean_quiet() -> None:
    """Quiet mean speaks without escalating tone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
    }
    without = build_calm_streak_glance(
        runtime, as_of=as_of, window_stats=base
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "loss_streak_mean": 1.5,
            "loss_streak_runs": 2,
        },
    )
    assert g["window_a_closes_loss_streak_mean"] == 1.5
    assert g["window_a_closes_loss_streak_runs"] == 2
    assert g["window_a_closes_loss_streak_mean_hot"] is False
    assert g["window_a_closes_loss_streak_mean_bit"] == (
        "loss mean · 1.5 · 2 runs"
    )
    # Quiet mean must not escalate vs the same book without it.
    assert g["tone"] == without["tone"]
    assert "win max" not in g["line"]
    assert "loss mean · 1.5 · 2 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_mean_one_run_silent() -> None:
    """One run stays silent — already the max/ending."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 2,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 1,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_mean"] is None
    assert g["window_a_closes_loss_streak_mean_bit"] == ""
    assert g["window_a_closes_loss_streak_mean_hot"] is False
    assert "loss mean" not in g["line"]
    assert "flats · 2" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_mean_missing_fail_open() -> None:
    """Missing loss_streak_mean keys fail open — do not invent a warn."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 2,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_mean"] is None
    assert g["window_a_closes_loss_streak_mean_bit"] == ""
    assert g["window_a_closes_loss_streak_mean_hot"] is False
    assert "loss mean" not in g["line"]
    assert "flats · 2" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_mean_hot() -> None:
    """Peak/ending alone must not hide a hot typical win-run (≥2 runs)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 1.5,
        "loss_streak_runs": 2,
        "win_streak_mean": 1.0,
        "win_streak_runs": 2,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            k: v
            for k, v in base.items()
            if k not in ("win_streak_mean", "win_streak_runs")
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "win_streak_mean": 2.5},
    )
    assert g["window_a_closes_loss_streak_mean"] == 1.5
    assert g["window_a_closes_loss_streak_mean_bit"] == (
        "loss mean · 1.5 · 2 runs"
    )
    assert g["window_a_closes_win_streak_mean"] == 2.5
    assert g["window_a_closes_win_streak_runs"] == 2
    assert g["window_a_closes_win_streak_mean_hot"] is True
    assert g["window_a_closes_win_streak_mean_bit"] == (
        "win mean · 2.5 · 2 runs"
    )
    # Hot win mean speaks; does not escalate vs the same book without it.
    assert g["tone"] == without["tone"]
    assert "win mean" not in without["line"]
    assert "loss mean" not in g["line"]  # loss mean stays in fields
    assert "win mean · 2.5 · 2 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_mean_quiet() -> None:
    """Quiet win mean speaks without escalating tone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 1.5,
        "loss_streak_runs": 2,
    }
    without = build_calm_streak_glance(
        runtime, as_of=as_of, window_stats=base
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "win_streak_mean": 1.5,
            "win_streak_runs": 2,
        },
    )
    assert g["window_a_closes_win_streak_mean"] == 1.5
    assert g["window_a_closes_win_streak_runs"] == 2
    assert g["window_a_closes_win_streak_mean_hot"] is False
    assert g["window_a_closes_win_streak_mean_bit"] == (
        "win mean · 1.5 · 2 runs"
    )
    assert g["tone"] == without["tone"]
    assert "loss mean" not in g["line"]
    assert "win mean · 1.5 · 2 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_mean_one_run_silent() -> None:
    """One win run stays silent — already the max/ending."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 1.5,
        "loss_streak_runs": 2,
        "win_streak_mean": 2.0,
        "win_streak_runs": 1,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak_mean"] is None
    assert g["window_a_closes_win_streak_mean_bit"] == ""
    assert g["window_a_closes_win_streak_mean_hot"] is False
    assert "win mean" not in g["line"]
    assert "loss mean · 1.5 · 2 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_mean_missing_fail_open() -> None:
    """Missing win_streak_mean keys fail open — do not invent a speak."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 1.5,
        "loss_streak_runs": 2,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak_mean"] is None
    assert g["window_a_closes_win_streak_mean_bit"] == ""
    assert g["window_a_closes_win_streak_mean_hot"] is False
    assert "win mean" not in g["line"]
    assert "loss mean · 1.5 · 2 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_median_hot() -> None:
    """Mean alone must not hide a hot median when a storm pulls the mean."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 3.5,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 1.5,
        "win_streak_runs": 2,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            k: v for k, v in base.items() if k != "loss_streak_median"
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "loss_streak_median": 2.5},
    )
    assert g["window_a_closes_win_streak_mean"] == 1.5
    assert g["window_a_closes_win_streak_mean_bit"] == (
        "win mean · 1.5 · 2 runs"
    )
    assert g["window_a_closes_loss_streak_median"] == 2.5
    assert g["window_a_closes_loss_streak_median_hot"] is True
    assert g["window_a_closes_loss_streak_median_bit"] == (
        "loss med · 2.5 · 3 runs"
    )
    assert g["tone"] == "warn"
    assert "loss med" not in without["line"]
    assert "win mean" not in g["line"]  # win mean stays in fields
    assert "loss med · 2.5 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_median_quiet() -> None:
    """Quiet median (med ≠ mean, med < hot) speaks without escalating tone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "win_streak_mean": 1.5,
        "win_streak_runs": 2,
    }
    without = build_calm_streak_glance(
        runtime, as_of=as_of, window_stats=base
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "loss_streak_median": 1.0},
    )
    assert g["window_a_closes_loss_streak_median"] == 1.0
    assert g["window_a_closes_loss_streak_median_hot"] is False
    assert g["window_a_closes_loss_streak_median_bit"] == (
        "loss med · 1.0 · 3 runs"
    )
    assert g["tone"] == without["tone"]
    assert "win mean" not in g["line"]
    assert "loss med · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_median_same_as_mean_silent() -> None:
    """Equal med and mean stay silent — no new information."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 2.0,
        "win_streak_mean": 1.5,
        "win_streak_runs": 2,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_median"] is None
    assert g["window_a_closes_loss_streak_median_bit"] == ""
    assert g["window_a_closes_loss_streak_median_hot"] is False
    assert "loss med" not in g["line"]
    assert "win mean · 1.5 · 2 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_median_two_runs_silent() -> None:
    """Two runs stay silent — med and mean share the same value space."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.5,
        "loss_streak_runs": 2,
        "loss_streak_median": 1.0,
        "win_streak_mean": 1.5,
        "win_streak_runs": 2,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_median"] is None
    assert g["window_a_closes_loss_streak_median_bit"] == ""
    assert g["window_a_closes_loss_streak_median_hot"] is False
    assert "loss med" not in g["line"]
    assert "win mean · 1.5 · 2 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_median_missing_fail_open() -> None:
    """Missing loss_streak_median key fail-open — do not invent a warn."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.5,
        "loss_streak_runs": 3,
        "win_streak_mean": 1.5,
        "win_streak_runs": 2,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_median"] is None
    assert g["window_a_closes_loss_streak_median_bit"] == ""
    assert g["window_a_closes_loss_streak_median_hot"] is False
    assert "loss med" not in g["line"]
    assert "win mean · 1.5 · 2 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_median_hot() -> None:
    """Mean alone must not hide a hot win median when one run pulls the mean."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 3.5,
        "loss_streak_runs": 3,
        "loss_streak_median": 2.5,
        "win_streak_mean": 3.5,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            k: v for k, v in base.items() if k != "win_streak_median"
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "win_streak_median": 2.5},
    )
    assert g["window_a_closes_loss_streak_median"] == 2.5
    assert g["window_a_closes_loss_streak_median_bit"] == (
        "loss med · 2.5 · 3 runs"
    )
    assert g["window_a_closes_win_streak_median"] == 2.5
    assert g["window_a_closes_win_streak_median_hot"] is True
    assert g["window_a_closes_win_streak_median_bit"] == (
        "win med · 2.5 · 3 runs"
    )
    # Hot win med speaks; does not escalate tone (speak-both-sides).
    assert g["tone"] == without["tone"]
    assert "win med" not in without["line"]
    assert "loss med" not in g["line"]  # loss med stays in fields
    assert "win med · 2.5 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_median_quiet() -> None:
    """Quiet win median (med ≠ mean, med < hot) speaks without escalating tone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
    }
    without = build_calm_streak_glance(
        runtime, as_of=as_of, window_stats=base
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "win_streak_median": 1.0},
    )
    assert g["window_a_closes_win_streak_median"] == 1.0
    assert g["window_a_closes_win_streak_median_hot"] is False
    assert g["window_a_closes_win_streak_median_bit"] == (
        "win med · 1.0 · 3 runs"
    )
    assert g["tone"] == without["tone"]
    assert "loss med" not in g["line"]
    assert "win med · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_median_same_as_mean_silent() -> None:
    """Equal win med and mean stay silent — no new information."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 2.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak_median"] is None
    assert g["window_a_closes_win_streak_median_bit"] == ""
    assert g["window_a_closes_win_streak_median_hot"] is False
    assert "win med" not in g["line"]
    assert "loss med · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_median_two_runs_silent() -> None:
    """Two win runs stay silent — med and mean share the same value space."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.5,
        "win_streak_runs": 2,
        "win_streak_median": 1.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak_median"] is None
    assert g["window_a_closes_win_streak_median_bit"] == ""
    assert g["window_a_closes_win_streak_median_hot"] is False
    assert "win med" not in g["line"]
    assert "loss med · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_median_missing_fail_open() -> None:
    """Missing win_streak_median key fail-open — do not invent a speak."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.5,
        "win_streak_runs": 3,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak_median"] is None
    assert g["window_a_closes_win_streak_median_bit"] == ""
    assert g["window_a_closes_win_streak_median_hot"] is False
    assert "win med" not in g["line"]
    assert "loss med · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_min_hot() -> None:
    """Peak alone must not hide a hot loss-run floor under the peak."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 4,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 3.5,
        "loss_streak_runs": 3,
        "loss_streak_median": 2.5,
        "win_streak_mean": 3.5,
        "win_streak_runs": 3,
        "win_streak_median": 2.5,
        "loss_streak_min": 1,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            k: v for k, v in base.items() if k != "loss_streak_min"
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "loss_streak_min": 2},
    )
    assert g["window_a_closes_win_streak_median"] == 2.5
    assert g["window_a_closes_win_streak_median_bit"] == (
        "win med · 2.5 · 3 runs"
    )
    assert g["window_a_closes_loss_streak_min"] == 2
    assert g["window_a_closes_loss_streak_min_hot"] is True
    assert g["window_a_closes_loss_streak_min_bit"] == "loss min · 2"
    assert g["tone"] == "warn"
    assert "loss min" not in without["line"]
    assert "win med" not in g["line"]  # win med stays in fields
    assert "loss min · 2" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_min_quiet() -> None:
    """Quiet loss min (floor < peak, min < hot) speaks without escalating tone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
    }
    without = build_calm_streak_glance(
        runtime, as_of=as_of, window_stats=base
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "loss_streak_min": 1},
    )
    assert g["window_a_closes_loss_streak_min"] == 1
    assert g["window_a_closes_loss_streak_min_hot"] is False
    assert g["window_a_closes_loss_streak_min_bit"] == "loss min · 1"
    assert g["tone"] == without["tone"]
    assert "win med" not in g["line"]
    assert "loss min · 1" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_min_equal_peak_silent() -> None:
    """Equal min and max stay silent — no new information."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 2,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 2,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_min"] is None
    assert g["window_a_closes_loss_streak_min_bit"] == ""
    assert g["window_a_closes_loss_streak_min_hot"] is False
    assert "loss min" not in g["line"]
    assert "win med · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_min_one_run_silent() -> None:
    """One loss run stays silent — min and max share the same value space."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 3.0,
        "loss_streak_runs": 1,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_min"] is None
    assert g["window_a_closes_loss_streak_min_bit"] == ""
    assert g["window_a_closes_loss_streak_min_hot"] is False
    assert "loss min" not in g["line"]
    assert "win med · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_min_missing_fail_open() -> None:
    """Missing loss_streak_min key fail-open — do not invent a warn."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_min"] is None
    assert g["window_a_closes_loss_streak_min_bit"] == ""
    assert g["window_a_closes_loss_streak_min_hot"] is False
    assert "loss min" not in g["line"]
    assert "win med · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_min_hot() -> None:
    """Peak alone must not hide a hot win-run floor under the peak (speak, no warn)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 4,
        "win_streak": 0,
        "win_streak_max": 4,
        "flat_closes": 0,
        "loss_streak_mean": 3.5,
        "loss_streak_runs": 3,
        "loss_streak_median": 2.5,
        "win_streak_mean": 3.5,
        "win_streak_runs": 3,
        "win_streak_median": 2.5,
        "loss_streak_min": 1,
        "win_streak_min": 1,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            k: v for k, v in base.items() if k != "win_streak_min"
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "win_streak_min": 2},
    )
    assert g["window_a_closes_loss_streak_min"] == 1
    assert g["window_a_closes_loss_streak_min_bit"] == "loss min · 1"
    assert g["window_a_closes_win_streak_min"] == 2
    assert g["window_a_closes_win_streak_min_hot"] is True
    assert g["window_a_closes_win_streak_min_bit"] == "win min · 2"
    # Hot win floor speaks; does not escalate tone (loss min quiet here).
    assert g["tone"] == without["tone"]
    assert "win min" not in without["line"]
    assert "loss min" not in g["line"]  # loss min stays in fields
    assert "win min · 2" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_min_quiet() -> None:
    """Quiet win min (floor < peak, min < hot) speaks without escalating tone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
    }
    without = build_calm_streak_glance(
        runtime, as_of=as_of, window_stats=base
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "win_streak_min": 1},
    )
    assert g["window_a_closes_win_streak_min"] == 1
    assert g["window_a_closes_win_streak_min_hot"] is False
    assert g["window_a_closes_win_streak_min_bit"] == "win min · 1"
    assert g["tone"] == without["tone"]
    assert "loss min" not in g["line"]
    assert "win min · 1" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_min_equal_peak_silent() -> None:
    """Equal win min and max stay silent — no new information."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 2,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 2,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak_min"] is None
    assert g["window_a_closes_win_streak_min_bit"] == ""
    assert g["window_a_closes_win_streak_min_hot"] is False
    assert "win min" not in g["line"]
    assert "loss min · 1" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_min_one_run_silent() -> None:
    """One win run stays silent — min and max share the same value space."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 3.0,
        "win_streak_runs": 1,
        "loss_streak_min": 1,
        "win_streak_min": 1,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak_min"] is None
    assert g["window_a_closes_win_streak_min_bit"] == ""
    assert g["window_a_closes_win_streak_min_hot"] is False
    assert "win min" not in g["line"]
    assert "loss min · 1" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_min_missing_fail_open() -> None:
    """Missing win_streak_min key fail-open — do not invent a speak."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak_min"] is None
    assert g["window_a_closes_win_streak_min_bit"] == ""
    assert g["window_a_closes_win_streak_min_hot"] is False
    assert "win min" not in g["line"]
    assert "loss min · 1" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_stdev_hot() -> None:
    """Min/max/mean/med alone must not hide a wide loss-run σ (warn only)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 4,
        "win_streak": 0,
        "win_streak_max": 4,
        "flat_closes": 0,
        "loss_streak_mean": 3.5,
        "loss_streak_runs": 3,
        "loss_streak_median": 2.5,
        "win_streak_mean": 3.5,
        "win_streak_runs": 3,
        "win_streak_median": 2.5,
        "loss_streak_min": 1,
        "win_streak_min": 1,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "loss_streak_stdev": 2.3},
    )
    assert g["window_a_closes_win_streak_min"] == 1
    assert g["window_a_closes_win_streak_min_bit"] == "win min · 1"
    assert g["window_a_closes_loss_streak_stdev"] == 2.3
    assert g["window_a_closes_loss_streak_stdev_hot"] is True
    assert g["window_a_closes_loss_streak_stdev_bit"] == (
        "loss σ · 2.3 · 3 runs"
    )
    assert g["tone"] == "warn"
    assert "loss σ" not in without["line"]
    assert "win min" not in g["line"]  # win min stays in fields
    assert "loss σ · 2.3 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_stdev_quiet() -> None:
    """Quiet loss σ (≥0.05, < hot) speaks without escalating tone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
    }
    without = build_calm_streak_glance(
        runtime, as_of=as_of, window_stats=base
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "loss_streak_stdev": 1.0},
    )
    assert g["window_a_closes_loss_streak_stdev"] == 1.0
    assert g["window_a_closes_loss_streak_stdev_hot"] is False
    assert g["window_a_closes_loss_streak_stdev_bit"] == (
        "loss σ · 1.0 · 3 runs"
    )
    assert g["tone"] == without["tone"]
    assert "win min" not in g["line"]
    assert "loss σ · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_stdev_two_runs_silent() -> None:
    """Two loss runs stay silent — σ needs ≥3 runs."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 2,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 2.8,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_stdev"] is None
    assert g["window_a_closes_loss_streak_stdev_bit"] == ""
    assert g["window_a_closes_loss_streak_stdev_hot"] is False
    assert "loss σ" not in g["line"]
    assert "win min · 1" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_stdev_flat_silent() -> None:
    """Near-zero σ stays silent — lengths are even."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 0.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_stdev"] is None
    assert g["window_a_closes_loss_streak_stdev_bit"] == ""
    assert g["window_a_closes_loss_streak_stdev_hot"] is False
    assert "loss σ" not in g["line"]
    assert "win min · 1" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_stdev_missing_fail_open() -> None:
    """Missing loss_streak_stdev key fail-open — do not invent a warn."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_stdev"] is None
    assert g["window_a_closes_loss_streak_stdev_bit"] == ""
    assert g["window_a_closes_loss_streak_stdev_hot"] is False
    assert "loss σ" not in g["line"]
    assert "win min · 1" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_stdev_hot() -> None:
    """Loss σ alone must not hide a wide win-run σ (speaks, does not warn)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 4,
        "win_streak": 0,
        "win_streak_max": 4,
        "flat_closes": 0,
        "loss_streak_mean": 3.5,
        "loss_streak_runs": 3,
        "loss_streak_median": 2.5,
        "win_streak_mean": 3.5,
        "win_streak_runs": 3,
        "win_streak_median": 2.5,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "win_streak_stdev": 2.3},
    )
    assert g["window_a_closes_loss_streak_stdev"] == 1.0
    assert g["window_a_closes_loss_streak_stdev_bit"] == (
        "loss σ · 1.0 · 3 runs"
    )
    assert g["window_a_closes_win_streak_stdev"] == 2.3
    assert g["window_a_closes_win_streak_stdev_hot"] is True
    assert g["window_a_closes_win_streak_stdev_bit"] == (
        "win σ · 2.3 · 3 runs"
    )
    # Hot win σ speaks; does not escalate tone (speak-both-sides).
    assert g["tone"] == without["tone"]
    assert "win σ" not in without["line"]
    assert "loss σ" not in g["line"]  # loss σ stays in fields
    assert "win σ · 2.3 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_stdev_quiet() -> None:
    """Quiet win σ (≥0.05, < hot) speaks without escalating tone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
    }
    without = build_calm_streak_glance(
        runtime, as_of=as_of, window_stats=base
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "win_streak_stdev": 1.0},
    )
    assert g["window_a_closes_win_streak_stdev"] == 1.0
    assert g["window_a_closes_win_streak_stdev_hot"] is False
    assert g["window_a_closes_win_streak_stdev_bit"] == (
        "win σ · 1.0 · 3 runs"
    )
    assert g["tone"] == without["tone"]
    assert "loss σ" not in g["line"]
    assert "win σ · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_stdev_two_runs_silent() -> None:
    """Two win runs stay silent — σ needs ≥3 runs."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 2,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 2.8,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak_stdev"] is None
    assert g["window_a_closes_win_streak_stdev_bit"] == ""
    assert g["window_a_closes_win_streak_stdev_hot"] is False
    assert "win σ" not in g["line"]
    assert "loss σ · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_stdev_flat_silent() -> None:
    """Near-zero win σ stays silent — lengths are even."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 0.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak_stdev"] is None
    assert g["window_a_closes_win_streak_stdev_bit"] == ""
    assert g["window_a_closes_win_streak_stdev_hot"] is False
    assert "win σ" not in g["line"]
    assert "loss σ · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_stdev_missing_fail_open() -> None:
    """Missing win_streak_stdev key fail-open — do not invent a bit."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak_stdev"] is None
    assert g["window_a_closes_win_streak_stdev_bit"] == ""
    assert g["window_a_closes_win_streak_stdev_hot"] is False
    assert "win σ" not in g["line"]
    assert "loss σ · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_cv_hot() -> None:
    """σ alone must not hide a wide loss-run CV (σ÷mean; warn only)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 4,
        "win_streak": 0,
        "win_streak_max": 4,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "loss_streak_cv": 2.3},
    )
    assert g["window_a_closes_win_streak_stdev"] == 1.0
    assert g["window_a_closes_win_streak_stdev_bit"] == (
        "win σ · 1.0 · 3 runs"
    )
    assert g["window_a_closes_loss_streak_cv"] == 2.3
    assert g["window_a_closes_loss_streak_cv_hot"] is True
    assert g["window_a_closes_loss_streak_cv_bit"] == (
        "loss CV · 2.3 · 3 runs"
    )
    assert g["tone"] == "warn"
    assert "loss CV" not in without["line"]
    assert "win σ" not in g["line"]  # win σ stays in fields
    assert "loss CV · 2.3 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_cv_quiet() -> None:
    """Quiet loss CV (≥0.05, < hot) speaks without escalating tone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
    }
    without = build_calm_streak_glance(
        runtime, as_of=as_of, window_stats=base
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "loss_streak_cv": 0.5},
    )
    assert g["window_a_closes_loss_streak_cv"] == 0.5
    assert g["window_a_closes_loss_streak_cv_hot"] is False
    assert g["window_a_closes_loss_streak_cv_bit"] == (
        "loss CV · 0.5 · 3 runs"
    )
    assert g["tone"] == without["tone"]
    assert "win σ" not in g["line"]
    assert "loss CV · 0.5 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_cv_two_runs_silent() -> None:
    """Two loss runs stay silent — CV needs ≥3 runs."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 2,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 2.8,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_cv"] is None
    assert g["window_a_closes_loss_streak_cv_bit"] == ""
    assert g["window_a_closes_loss_streak_cv_hot"] is False
    assert "loss CV" not in g["line"]
    assert "win σ · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_cv_flat_silent() -> None:
    """Near-zero loss CV stays silent — relative spread is even."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 0.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_cv"] is None
    assert g["window_a_closes_loss_streak_cv_bit"] == ""
    assert g["window_a_closes_loss_streak_cv_hot"] is False
    assert "loss CV" not in g["line"]
    assert "win σ · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_loss_streak_cv_missing_fail_open() -> None:
    """Missing loss_streak_cv key fail-open — do not invent a bit."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_loss_streak_cv"] is None
    assert g["window_a_closes_loss_streak_cv_bit"] == ""
    assert g["window_a_closes_loss_streak_cv_hot"] is False
    assert "loss CV" not in g["line"]
    assert "win σ · 1.0 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_cv_hot() -> None:
    """Loss CV alone must not hide a wide win-run CV (speaks, does not warn)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 4,
        "win_streak": 0,
        "win_streak_max": 4,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 0.5,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "win_streak_cv": 2.3},
    )
    assert g["window_a_closes_loss_streak_cv"] == 0.5
    assert g["window_a_closes_loss_streak_cv_bit"] == (
        "loss CV · 0.5 · 3 runs"
    )
    assert g["window_a_closes_win_streak_cv"] == 2.3
    assert g["window_a_closes_win_streak_cv_hot"] is True
    assert g["window_a_closes_win_streak_cv_bit"] == (
        "win CV · 2.3 · 3 runs"
    )
    # Hot win CV speaks but does not escalate tone (speak-both-sides).
    assert g["tone"] == without["tone"]
    assert "win CV" not in without["line"]
    assert "loss CV" not in g["line"]  # loss CV stays in fields
    assert "win CV · 2.3 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_cv_quiet() -> None:
    """Quiet win CV (≥0.05, < hot) speaks without escalating tone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 0.5,
    }
    without = build_calm_streak_glance(
        runtime, as_of=as_of, window_stats=base
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "win_streak_cv": 0.5},
    )
    assert g["window_a_closes_win_streak_cv"] == 0.5
    assert g["window_a_closes_win_streak_cv_hot"] is False
    assert g["window_a_closes_win_streak_cv_bit"] == (
        "win CV · 0.5 · 3 runs"
    )
    assert g["tone"] == without["tone"]
    assert "loss CV" not in g["line"]
    assert "win CV · 0.5 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_cv_two_runs_silent() -> None:
    """Two win runs stay silent — CV needs ≥3 runs."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 2,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "loss_streak_cv": 0.5,
        "win_streak_cv": 2.8,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak_cv"] is None
    assert g["window_a_closes_win_streak_cv_bit"] == ""
    assert g["window_a_closes_win_streak_cv_hot"] is False
    assert "win CV" not in g["line"]
    assert "loss CV · 0.5 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_cv_flat_silent() -> None:
    """Near-zero win CV stays silent — relative spread is even."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 0.5,
        "win_streak_cv": 0.0,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak_cv"] is None
    assert g["window_a_closes_win_streak_cv_bit"] == ""
    assert g["window_a_closes_win_streak_cv_hot"] is False
    assert "win CV" not in g["line"]
    assert "loss CV · 0.5 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_win_streak_cv_missing_fail_open() -> None:
    """Missing win_streak_cv key fail-open — do not invent a bit."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 0.5,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_win_streak_cv"] is None
    assert g["window_a_closes_win_streak_cv_bit"] == ""
    assert g["window_a_closes_win_streak_cv_hot"] is False
    assert "win CV" not in g["line"]
    assert "loss CV · 0.5 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_mix_hot() -> None:
    """Win CV alone must not hide stops+rot+trim leading TP (warns only)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 4,
        "win_streak": 0,
        "win_streak_max": 4,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 0.5,
        "win_streak_cv": 0.5,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 2,
            "exit_sl": 5,
            "exit_rot": 3,
            "exit_trim": 2,
        },
    )
    assert g["window_a_closes_exit_tp"] == 2
    assert g["window_a_closes_exit_sl"] == 5
    assert g["window_a_closes_exit_rot"] == 3
    assert g["window_a_closes_exit_trim"] == 2
    assert g["window_a_closes_exit_mix_hot"] is True
    assert g["window_a_closes_exit_mix_bit"] == (
        "exits tp 2 · sl 5 · rot 3 · trim 2"
    )
    assert g["window_a_closes_exit_tp_share_thin"] is True
    assert g["window_a_closes_exit_tp_share_bit"] == "tp share thin · 16.7%"
    assert g["window_a_closes_exit_sl_share_pct"] == 41.7
    assert g["window_a_closes_exit_sl_share_severity"] == ""
    assert g["window_a_closes_exit_sl_share_hot"] is False
    assert g["window_a_closes_exit_sl_share_bit"] == "sl share · 41.7%"
    assert g["window_a_closes_exit_rot_share_pct"] == 25.0
    assert g["window_a_closes_exit_rot_share_severity"] == "quiet"
    assert g["window_a_closes_exit_rot_share_hot"] is False
    assert g["window_a_closes_exit_rot_share_bit"] == "rot share quiet · 25%"
    assert g["window_a_closes_exit_trim_share_pct"] == 16.7
    assert g["window_a_closes_exit_trim_share_severity"] == "quiet"
    assert g["window_a_closes_exit_trim_share_hot"] is False
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 16.7%"
    assert g["window_a_closes_exit_unknown_warn"] is False
    assert g["tone"] == "warn"
    assert "exits" not in without["line"]
    assert "win CV" not in g["line"]  # win CV stays in fields
    assert "unknown" not in g["line"]
    assert "exits tp 2 · sl 5 · rot 3 · trim 2" not in g["line"]  # mix fields
    assert "tp share thin · 16.7%" not in g["line"]  # tp stays in fields
    assert "sl share · 41.7%" not in g["line"]  # sl stays in fields
    assert "rot share quiet · 25%" not in g["line"]  # rot stays in fields
    assert "trim share quiet · 16.7%" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_mix_tp_led() -> None:
    """TP-led exit mix speaks without escalating tone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 0.5,
        "win_streak_cv": 0.5,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 8,
            "exit_sl": 2,
            "exit_rot": 1,
            "exit_trim": 1,
        },
    )
    assert g["window_a_closes_exit_mix_hot"] is False
    assert g["window_a_closes_exit_mix_bit"] == (
        "exits tp 8 · sl 2 · rot 1 · trim 1"
    )
    assert g["window_a_closes_exit_tp_share_severity"] == "strong"
    assert g["window_a_closes_exit_tp_share_thin"] is False
    assert g["window_a_closes_exit_tp_share_bit"] == "tp share strong · 66.7%"
    assert g["window_a_closes_exit_sl_share_pct"] == 16.7
    assert g["window_a_closes_exit_sl_share_severity"] == "quiet"
    assert g["window_a_closes_exit_sl_share_hot"] is False
    assert g["window_a_closes_exit_sl_share_bit"] == "sl share quiet · 16.7%"
    assert g["window_a_closes_exit_rot_share_pct"] == 8.3
    assert g["window_a_closes_exit_rot_share_severity"] == "quiet"
    assert g["window_a_closes_exit_rot_share_hot"] is False
    assert g["window_a_closes_exit_rot_share_bit"] == "rot share quiet · 8.3%"
    assert g["window_a_closes_exit_trim_share_pct"] == 8.3
    assert g["window_a_closes_exit_trim_share_severity"] == "quiet"
    assert g["window_a_closes_exit_trim_share_hot"] is False
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 8.3%"
    assert g["window_a_closes_exit_unknown_warn"] is False
    assert g["tone"] == without["tone"]
    assert "unknown" not in g["line"]
    assert "exits tp 8 · sl 2 · rot 1 · trim 1" not in g["line"]  # mix fields
    assert "tp share strong · 66.7%" not in g["line"]  # tp stays in fields
    assert "sl share quiet · 16.7%" not in g["line"]  # sl stays in fields
    assert "rot share quiet · 8.3%" not in g["line"]  # rot stays in fields
    assert "trim share quiet · 8.3%" in g["line"]
    assert "win CV" not in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_mix_missing_fail_open() -> None:
    """Missing exit_* keys fail-open — do not invent a mix bit."""
    as_of = date(2026, 8, 18)
    stats = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 6,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 0.5,
        "win_streak_cv": 0.5,
    }
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats=stats,
    )
    assert g["window_a_closes_exit_mix_bit"] == ""
    assert g["window_a_closes_exit_mix_hot"] is False
    assert g["window_a_closes_exit_tp"] is None
    assert "exits" not in g["line"]
    assert "win CV · 0.5 · 3 runs" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_unknown_warn() -> None:
    """Exit mix alone must not hide sells outside tp/sl/rot/trim (warns only)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 4,
        "win_streak": 0,
        "win_streak_max": 4,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 0.5,
        "win_streak_cv": 0.5,
        "exit_tp": 3,
        "exit_sl": 1,
        "exit_rot": 0,
        "exit_trim": 0,
    }
    covered = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 8,
            "exit_sl": 2,
            "exit_rot": 1,
            "exit_trim": 1,
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    assert g["window_a_closes_exit_unknown"] == 8
    assert g["window_a_closes_exit_unknown_warn"] is True
    assert g["window_a_closes_exit_unknown_bit"] == "exits unknown · 8"
    assert g["window_a_closes_exit_mix_bit"] == "exits tp 3 · sl 1"
    assert g["window_a_closes_exit_tp_share_severity"] == "strong"
    assert g["window_a_closes_exit_tp_share_bit"] == "tp share strong · 75%"
    assert g["window_a_closes_exit_sl_share_pct"] == 25.0
    assert g["window_a_closes_exit_sl_share_severity"] == "quiet"
    assert g["window_a_closes_exit_sl_share_bit"] == "sl share quiet · 25%"
    assert g["window_a_closes_exit_rot_share_pct"] == 0.0
    assert g["window_a_closes_exit_rot_share_severity"] == "quiet"
    assert g["window_a_closes_exit_rot_share_bit"] == "rot share quiet · 0%"
    assert g["window_a_closes_exit_trim_share_pct"] == 0.0
    assert g["window_a_closes_exit_trim_share_severity"] == "quiet"
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 0%"
    assert g["tone"] == "warn"
    assert "exits unknown" not in covered["line"]
    assert covered["window_a_closes_exit_unknown_warn"] is False
    assert "exits tp 3 · sl 1" not in g["line"]  # mix stays in fields
    assert "exits unknown · 8" not in g["line"]  # unknown stays in fields
    assert "tp share strong · 75%" not in g["line"]  # tp stays in fields
    assert "sl share quiet · 25%" not in g["line"]  # sl stays in fields
    assert "rot share quiet · 0%" not in g["line"]  # rot stays in fields
    assert "trim share quiet · 0%" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_unknown_zero_silent() -> None:
    """Zero unknown stays silent — trim share keeps the clip over mix/TP/SL/rot."""
    as_of = date(2026, 8, 18)
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 0,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "promote filter off — streak paused",
        },
        as_of=as_of,
        window_stats={
            "trades": 24,
            "buys": 12,
            "sells": 12,
            "fees": 4.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 36.0,
            "wins": 8,
            "losses": 4,
            "avg_win": 8.0,
            "avg_loss": 4.0,
            "loss_streak": 0,
            "loss_streak_max": 3,
            "win_streak": 0,
            "win_streak_max": 3,
            "flat_closes": 0,
            "loss_streak_mean": 2.0,
            "loss_streak_runs": 3,
            "loss_streak_median": 1.0,
            "win_streak_mean": 2.0,
            "win_streak_runs": 3,
            "win_streak_median": 1.0,
            "loss_streak_min": 1,
            "win_streak_min": 1,
            "loss_streak_stdev": 1.0,
            "win_streak_stdev": 1.0,
            "loss_streak_cv": 0.5,
            "win_streak_cv": 0.5,
            "exit_tp": 8,
            "exit_sl": 2,
            "exit_rot": 1,
            "exit_trim": 1,
        },
    )
    assert g["window_a_closes_exit_unknown"] is None
    assert g["window_a_closes_exit_unknown_bit"] == ""
    assert g["window_a_closes_exit_unknown_warn"] is False
    assert g["window_a_closes_exit_tp_share_severity"] == "strong"
    assert g["window_a_closes_exit_tp_share_bit"] == "tp share strong · 66.7%"
    assert g["window_a_closes_exit_sl_share_severity"] == "quiet"
    assert g["window_a_closes_exit_sl_share_bit"] == "sl share quiet · 16.7%"
    assert g["window_a_closes_exit_rot_share_severity"] == "quiet"
    assert g["window_a_closes_exit_rot_share_bit"] == "rot share quiet · 8.3%"
    assert g["window_a_closes_exit_trim_share_severity"] == "quiet"
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 8.3%"
    assert "unknown" not in g["line"]
    assert "exits tp 8 · sl 2 · rot 1 · trim 1" not in g["line"]  # mix fields
    assert "tp share strong · 66.7%" not in g["line"]  # tp stays in fields
    assert "sl share quiet · 16.7%" not in g["line"]  # sl stays in fields
    assert "rot share quiet · 8.3%" not in g["line"]  # rot stays in fields
    assert "trim share quiet · 8.3%" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_tp_share_thin() -> None:
    """Mix counts alone must not hide a thin take-profit slice (warns only)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 0.5,
        "win_streak_cv": 0.5,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 2,
            "exit_sl": 4,
            "exit_rot": 3,
            "exit_trim": 1,
        },
    )
    assert g["window_a_closes_exit_tp_share_pct"] == 20.0
    assert g["window_a_closes_exit_tp_share_severity"] == "thin"
    assert g["window_a_closes_exit_tp_share_thin"] is True
    assert g["window_a_closes_exit_tp_share_bit"] == "tp share thin · 20%"
    assert g["window_a_closes_exit_sl_share_pct"] == 40.0
    assert g["window_a_closes_exit_sl_share_severity"] == ""
    assert g["window_a_closes_exit_sl_share_hot"] is False
    assert g["window_a_closes_exit_sl_share_bit"] == "sl share · 40%"
    assert g["window_a_closes_exit_rot_share_pct"] == 30.0
    assert g["window_a_closes_exit_rot_share_severity"] == "quiet"
    assert g["window_a_closes_exit_rot_share_bit"] == "rot share quiet · 30%"
    assert g["window_a_closes_exit_trim_share_pct"] == 10.0
    assert g["window_a_closes_exit_trim_share_severity"] == "quiet"
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 10%"
    assert g["window_a_closes_exit_mix_bit"] == (
        "exits tp 2 · sl 4 · rot 3 · trim 1"
    )
    assert g["tone"] == "warn"
    assert "tp share" not in without["line"]
    assert "exits tp 2 · sl 4 · rot 3 · trim 1" not in g["line"]
    assert "tp share thin · 20%" not in g["line"]  # tp stays in fields
    assert "sl share · 40%" not in g["line"]  # sl stays in fields
    assert "rot share quiet · 30%" not in g["line"]  # rot stays in fields
    assert "trim share quiet · 10%" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_tp_share_mid() -> None:
    """Mid TP share speaks without escalating tone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 0.5,
        "win_streak_cv": 0.5,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 5,
            "exit_sl": 3,
            "exit_rot": 1,
            "exit_trim": 1,
        },
    )
    assert g["window_a_closes_exit_tp_share_pct"] == 50.0
    assert g["window_a_closes_exit_tp_share_severity"] == ""
    assert g["window_a_closes_exit_tp_share_thin"] is False
    assert g["window_a_closes_exit_tp_share_bit"] == "tp share · 50%"
    assert g["window_a_closes_exit_sl_share_pct"] == 30.0
    assert g["window_a_closes_exit_sl_share_severity"] == "quiet"
    assert g["window_a_closes_exit_sl_share_hot"] is False
    assert g["window_a_closes_exit_sl_share_bit"] == "sl share quiet · 30%"
    assert g["window_a_closes_exit_rot_share_pct"] == 10.0
    assert g["window_a_closes_exit_rot_share_severity"] == "quiet"
    assert g["window_a_closes_exit_rot_share_bit"] == "rot share quiet · 10%"
    assert g["window_a_closes_exit_trim_share_pct"] == 10.0
    assert g["window_a_closes_exit_trim_share_severity"] == "quiet"
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 10%"
    assert g["window_a_closes_exit_mix_hot"] is False
    assert g["tone"] == without["tone"]
    assert "tp share · 50%" not in g["line"]  # tp stays in fields
    assert "sl share quiet · 30%" not in g["line"]  # sl stays in fields
    assert "rot share quiet · 10%" not in g["line"]  # rot stays in fields
    assert "trim share quiet · 10%" in g["line"]
    assert "exits tp 5" not in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_sl_share_hot() -> None:
    """TP share alone must not hide a hot stop-loss slice (warns only)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 5,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 3,
        "losses": 2,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 2,
        "win_streak": 0,
        "win_streak_max": 2,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 2,
        "win_streak_mean": 2.0,
        "win_streak_runs": 2,
        "loss_streak_min": 1,
        "win_streak_min": 1,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 1,
            "exit_sl": 4,
            "exit_rot": 0,
            "exit_trim": 0,
        },
    )
    assert g["window_a_closes_exit_sl_share_pct"] == 80.0
    assert g["window_a_closes_exit_sl_share_severity"] == "hot"
    assert g["window_a_closes_exit_sl_share_hot"] is True
    assert g["window_a_closes_exit_sl_share_bit"] == "sl share hot · 80%"
    assert g["window_a_closes_exit_rot_share_pct"] == 0.0
    assert g["window_a_closes_exit_rot_share_severity"] == "quiet"
    assert g["window_a_closes_exit_rot_share_bit"] == "rot share quiet · 0%"
    assert g["window_a_closes_exit_trim_share_pct"] == 0.0
    assert g["window_a_closes_exit_trim_share_severity"] == "quiet"
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 0%"
    assert g["window_a_closes_exit_tp_share_pct"] == 20.0
    assert g["window_a_closes_exit_tp_share_thin"] is True
    assert g["tone"] == "warn"
    assert "sl share" not in without["line"]
    assert "tp share thin · 20%" not in g["line"]  # tp stays in fields
    assert "sl share hot · 80%" not in g["line"]  # sl stays in fields
    assert "rot share quiet · 0%" not in g["line"]  # rot stays in fields
    assert "trim share quiet · 0%" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_sl_share_quiet() -> None:
    """Quiet stop share speaks in fields; trim keeps the clip without warn."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 0.5,
        "win_streak_cv": 0.5,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 8,
            "exit_sl": 2,
            "exit_rot": 1,
            "exit_trim": 1,
        },
    )
    assert g["window_a_closes_exit_sl_share_pct"] == 16.7
    assert g["window_a_closes_exit_sl_share_severity"] == "quiet"
    assert g["window_a_closes_exit_sl_share_hot"] is False
    assert g["window_a_closes_exit_sl_share_bit"] == "sl share quiet · 16.7%"
    assert g["window_a_closes_exit_rot_share_pct"] == 8.3
    assert g["window_a_closes_exit_rot_share_severity"] == "quiet"
    assert g["window_a_closes_exit_rot_share_hot"] is False
    assert g["window_a_closes_exit_rot_share_bit"] == "rot share quiet · 8.3%"
    assert g["window_a_closes_exit_trim_share_pct"] == 8.3
    assert g["window_a_closes_exit_trim_share_severity"] == "quiet"
    assert g["window_a_closes_exit_trim_share_hot"] is False
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 8.3%"
    assert g["window_a_closes_exit_tp_share_severity"] == "strong"
    assert g["tone"] == without["tone"]
    assert "sl share quiet · 16.7%" not in g["line"]  # sl stays in fields
    assert "rot share quiet · 8.3%" not in g["line"]  # rot stays in fields
    assert "trim share quiet · 8.3%" in g["line"]
    assert "tp share strong · 66.7%" not in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_rot_share_hot() -> None:
    """SL share alone must not hide a hot rotation slice (warns only)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 5,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 3,
        "losses": 2,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 2,
        "win_streak": 0,
        "win_streak_max": 2,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 2,
        "win_streak_mean": 2.0,
        "win_streak_runs": 2,
        "loss_streak_min": 1,
        "win_streak_min": 1,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 1,
            "exit_sl": 0,
            "exit_rot": 4,
            "exit_trim": 0,
        },
    )
    assert g["window_a_closes_exit_rot_share_pct"] == 80.0
    assert g["window_a_closes_exit_rot_share_severity"] == "hot"
    assert g["window_a_closes_exit_rot_share_hot"] is True
    assert g["window_a_closes_exit_rot_share_bit"] == "rot share hot · 80%"
    assert g["window_a_closes_exit_trim_share_pct"] == 0.0
    assert g["window_a_closes_exit_trim_share_severity"] == "quiet"
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 0%"
    assert g["window_a_closes_exit_sl_share_pct"] == 0.0
    assert g["window_a_closes_exit_sl_share_severity"] == "quiet"
    assert g["window_a_closes_exit_tp_share_thin"] is True
    assert g["tone"] == "warn"
    assert "rot share" not in without["line"]
    assert "sl share quiet · 0%" not in g["line"]  # sl stays in fields
    assert "rot share hot · 80%" not in g["line"]  # rot stays in fields
    assert "trim share quiet · 0%" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_rot_share_quiet() -> None:
    """Quiet rotation share speaks in fields; trim keeps the clip without warn."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 0.5,
        "win_streak_cv": 0.5,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 8,
            "exit_sl": 2,
            "exit_rot": 1,
            "exit_trim": 1,
        },
    )
    assert g["window_a_closes_exit_rot_share_pct"] == 8.3
    assert g["window_a_closes_exit_rot_share_severity"] == "quiet"
    assert g["window_a_closes_exit_rot_share_hot"] is False
    assert g["window_a_closes_exit_rot_share_bit"] == "rot share quiet · 8.3%"
    assert g["window_a_closes_exit_trim_share_pct"] == 8.3
    assert g["window_a_closes_exit_trim_share_severity"] == "quiet"
    assert g["window_a_closes_exit_trim_share_hot"] is False
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 8.3%"
    assert g["window_a_closes_exit_sl_share_severity"] == "quiet"
    assert g["tone"] == without["tone"]
    assert "rot share quiet · 8.3%" not in g["line"]  # rot stays in fields
    assert "trim share quiet · 8.3%" in g["line"]
    assert "sl share quiet · 16.7%" not in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_trim_share_hot() -> None:
    """Rot share alone must not hide a hot trim slice (warns only)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 5,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 3,
        "losses": 2,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 2,
        "win_streak": 0,
        "win_streak_max": 2,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 2,
        "win_streak_mean": 2.0,
        "win_streak_runs": 2,
        "loss_streak_min": 1,
        "win_streak_min": 1,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 1,
            "exit_sl": 0,
            "exit_rot": 0,
            "exit_trim": 4,
        },
    )
    assert g["window_a_closes_exit_trim_share_pct"] == 80.0
    assert g["window_a_closes_exit_trim_share_severity"] == "hot"
    assert g["window_a_closes_exit_trim_share_hot"] is True
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share hot · 80%"
    assert g["window_a_closes_exit_rot_share_pct"] == 0.0
    assert g["window_a_closes_exit_rot_share_severity"] == "quiet"
    assert g["window_a_closes_exit_tp_share_thin"] is True
    assert g["tone"] == "warn"
    assert "trim share" not in without["line"]
    assert "rot share quiet · 0%" not in g["line"]  # rot stays in fields
    assert "trim share hot · 80%" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_trim_share_quiet() -> None:
    """Quiet trim share speaks without escalating tone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 12,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 8,
        "losses": 4,
        "avg_win": 8.0,
        "avg_loss": 4.0,
        "loss_streak": 0,
        "loss_streak_max": 3,
        "win_streak": 0,
        "win_streak_max": 3,
        "flat_closes": 0,
        "loss_streak_mean": 2.0,
        "loss_streak_runs": 3,
        "loss_streak_median": 1.0,
        "win_streak_mean": 2.0,
        "win_streak_runs": 3,
        "win_streak_median": 1.0,
        "loss_streak_min": 1,
        "win_streak_min": 1,
        "loss_streak_stdev": 1.0,
        "win_streak_stdev": 1.0,
        "loss_streak_cv": 0.5,
        "win_streak_cv": 0.5,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats=base,
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 8,
            "exit_sl": 2,
            "exit_rot": 1,
            "exit_trim": 1,
        },
    )
    assert g["window_a_closes_exit_trim_share_pct"] == 8.3
    assert g["window_a_closes_exit_trim_share_severity"] == "quiet"
    assert g["window_a_closes_exit_trim_share_hot"] is False
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 8.3%"
    assert g["window_a_closes_exit_rot_share_severity"] == "quiet"
    assert g["tone"] == without["tone"]
    assert "trim share quiet · 8.3%" in g["line"]
    assert "rot share quiet · 8.3%" not in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_lead_hot() -> None:
    """Trim share alone must not hide an adverse € lead (warns only).

    Thin gap (<2×) so € gap stays silent; € conc owns the clip.
    """
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 4,
        "fees": 4.0,
        "realized_pnl": -30.0,
        "net_after_all_fees": -34.0,
        "wins": 3,
        "losses": 1,
        "avg_win": 50.0 / 3.0,
        "avg_loss": 80.0,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 0,
        "win_streak_max": 2,
        "flat_closes": 0,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 50.0,
            "exit_pnl_sl": -80.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    assert g["window_a_closes_exit_euro_lead"] == "sl"
    assert g["window_a_closes_exit_euro_pnl"] == -80.0
    assert g["window_a_closes_exit_euro_lead_hot"] is True
    assert g["window_a_closes_exit_euro_lead_bit"] == "€ lead sl · −€80"
    assert g["window_a_closes_exit_euro_gap_bit"] == ""
    assert g["window_a_closes_exit_euro_gap_hot"] is False
    # |sl| 80 / 130 ≈ 61.5% → hot conc + fat size; clash owns clip.
    assert g["window_a_closes_exit_euro_conc"] == "sl"
    assert g["window_a_closes_exit_euro_conc_pct"] == 61.5
    assert g["window_a_closes_exit_euro_conc_hot"] is True
    assert g["window_a_closes_exit_euro_conc_bit"] == "€ conc hot · sl · 61.5%"
    assert g["window_a_closes_exit_euro_size_ratio"] == 4.8
    assert g["window_a_closes_exit_euro_size_hot"] is True
    assert g["window_a_closes_exit_euro_size_bit"] == "€ size fat hot · sl · 4.8×"
    assert g["window_a_closes_exit_euro_size_n"] == "thin"
    assert g["window_a_closes_exit_euro_size_n_count"] == 1
    assert g["window_a_closes_exit_euro_size_n_thin"] is True
    assert g["window_a_closes_exit_euro_size_n_bit"] == (
        "€ size n thin · sl · 1 closes <3"
    )
    assert g["window_a_closes_exit_euro_size_sign"] == "loss"
    assert g["window_a_closes_exit_euro_size_sign_pnl"] == -80.0
    assert g["window_a_closes_exit_euro_size_sign_loss"] is True
    assert g["window_a_closes_exit_euro_size_sign_bit"] == (
        "€ size sign loss · sl · −€80"
    )
    assert g["window_a_closes_exit_euro_size_rest_sign"] == "win"
    assert g["window_a_closes_exit_euro_size_rest_sign_pnl"] == 50.0
    assert g["window_a_closes_exit_euro_size_rest_sign_loss"] is False
    assert g["window_a_closes_exit_euro_size_rest_sign_bit"] == (
        "€ size rest sign win · +€50"
    )
    assert g["window_a_closes_exit_euro_size_sign_clash"] == "clash"
    assert g["window_a_closes_exit_euro_size_sign_clash_loss"] is True
    assert g["window_a_closes_exit_euro_size_sign_clash_bit"] == (
        "€ size clash · lead loss · rest win"
    )
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 0%"
    assert g["tone"] == "warn"
    assert "€ lead" not in without["line"]
    assert "€ gap" not in g["line"]
    assert "trim share quiet · 0%" not in g["line"]  # trim stays in fields
    assert "€ lead sl · −€80" not in g["line"]  # lead stays in fields
    assert "€ conc hot · sl · 61.5%" not in g["line"]  # conc stays in fields
    assert "€ size fat hot · sl · 4.8×" not in g["line"]  # size stays in fields
    assert "€ size n thin · sl · 1 closes <3" not in g["line"]  # size-n stays in fields
    assert "€ size sign loss · sl · −€80" not in g["line"]  # size-sign stays in fields
    assert "€ size rest sign win · +€50" not in g["line"]  # rest-sign stays in fields
    assert (
        "€ size clash · lead loss" in g["line"]
        or "€ size clash net" in g["line"]
        or "€ size clash keep" in g["line"]
        or "keep fees" in g["line"]
    )
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_lead_tp() -> None:
    """Take-profit € lead speaks without escalating tone.

    Thin gap (<2×) so € gap stays silent; € conc owns the clip.
    """
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 4,
        "fees": 4.0,
        "realized_pnl": 40.0,
        "net_after_all_fees": 36.0,
        "wins": 1,
        "losses": 3,
        "avg_win": 90.0,
        "avg_loss": 50.0 / 3.0,
        "loss_streak": 0,
        "loss_streak_max": 2,
        "win_streak": 0,
        "win_streak_max": 1,
        "flat_closes": 0,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 1,
            "exit_sl": 3,
            "exit_rot": 0,
            "exit_trim": 0,
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 1,
            "exit_sl": 3,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 90.0,
            "exit_pnl_sl": -50.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    assert g["window_a_closes_exit_euro_lead"] == "tp"
    assert g["window_a_closes_exit_euro_pnl"] == 90.0
    assert g["window_a_closes_exit_euro_lead_hot"] is False
    assert g["window_a_closes_exit_euro_lead_bit"] == "€ lead tp · +€90"
    assert g["window_a_closes_exit_euro_gap_bit"] == ""
    assert g["window_a_closes_exit_euro_gap_hot"] is False
    # |tp| 90 / 140 ≈ 64.3% → strong conc + fat size; size-n thin owns clip.
    assert g["window_a_closes_exit_euro_conc"] == "tp"
    assert g["window_a_closes_exit_euro_conc_pct"] == 64.3
    assert g["window_a_closes_exit_euro_conc_hot"] is False
    assert g["window_a_closes_exit_euro_conc_bit"] == (
        "€ conc strong · tp · 64.3%"
    )
    assert g["window_a_closes_exit_euro_size_ratio"] == 5.4
    assert g["window_a_closes_exit_euro_size_hot"] is False
    assert g["window_a_closes_exit_euro_size_bit"] == (
        "€ size fat quiet · tp · 5.4×"
    )
    assert g["window_a_closes_exit_euro_size_n"] == "thin"
    assert g["window_a_closes_exit_euro_size_n_count"] == 1
    assert g["window_a_closes_exit_euro_size_n_thin"] is True
    assert g["window_a_closes_exit_euro_size_n_bit"] == (
        "€ size n thin · tp · 1 closes <3"
    )
    assert g["window_a_closes_exit_euro_size_sign"] == "win"
    assert g["window_a_closes_exit_euro_size_sign_pnl"] == 90.0
    assert g["window_a_closes_exit_euro_size_sign_loss"] is False
    assert g["window_a_closes_exit_euro_size_sign_bit"] == (
        "€ size sign win · tp · +€90"
    )
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 0%"
    # SL share hot (75%) + size-n thin warn; € lead / size / sign win quiet alone.
    assert g["window_a_closes_exit_sl_share_hot"] is True
    assert g["tone"] == "warn"
    assert "€ lead" not in without["line"]
    assert "€ gap" not in g["line"]
    assert "trim share quiet · 0%" not in g["line"]
    assert "€ lead tp · +€90" not in g["line"]  # lead stays in fields
    assert "€ conc strong · tp · 64.3%" not in g["line"]  # conc stays in fields
    assert "€ size fat quiet · tp · 5.4×" not in g["line"]  # size stays in fields
    assert "€ size n thin · tp · 1 closes <3" not in g["line"]  # size-n stays in fields
    assert "€ size sign win · tp · +€90" not in g["line"]  # size-sign stays in fields
    assert "€ size rest sign loss · −€50" not in g["line"]  # rest-sign stays in fields
    assert (
        "€ size clash · lead win" in g["line"]
        or "€ size clash net" in g["line"]
        or "€ size clash keep" in g["line"]
        or "keep fees" in g["line"]
    )
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_lead_match_silent() -> None:
    """When count lead matches € lead, lead/offset/gap stay silent — € conc owns clip."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 24,
            "buys": 12,
            "sells": 12,
            "fees": 4.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 36.0,
            "wins": 8,
            "losses": 4,
            "avg_win": 8.0,
            "avg_loss": 4.0,
            "loss_streak": 0,
            "loss_streak_max": 3,
            "win_streak": 0,
            "win_streak_max": 3,
            "flat_closes": 0,
            "loss_streak_mean": 2.0,
            "loss_streak_runs": 3,
            "loss_streak_median": 1.0,
            "win_streak_mean": 2.0,
            "win_streak_runs": 3,
            "win_streak_median": 1.0,
            "loss_streak_min": 1,
            "win_streak_min": 1,
            "loss_streak_stdev": 1.0,
            "win_streak_stdev": 1.0,
            "loss_streak_cv": 0.5,
            "win_streak_cv": 0.5,
            "exit_tp": 8,
            "exit_sl": 2,
            "exit_rot": 1,
            "exit_trim": 1,
            # Rest |€| raised so avg size stays mid (<2×) — conc owns clip.
            "exit_pnl_tp": 64.0,
            "exit_pnl_sl": -12.0,
            "exit_pnl_rot": -4.0,
            "exit_pnl_trim": -4.0,
        },
    )
    assert g["window_a_closes_exit_euro_lead"] is None
    assert g["window_a_closes_exit_euro_lead_bit"] == ""
    assert g["window_a_closes_exit_euro_lead_hot"] is False
    assert g["window_a_closes_exit_euro_offset"] is None
    assert g["window_a_closes_exit_euro_offset_bit"] == ""
    assert g["window_a_closes_exit_euro_offset_hot"] is False
    assert g["window_a_closes_exit_euro_gap_bit"] == ""
    assert g["window_a_closes_exit_euro_gap_hot"] is False
    assert g["window_a_closes_exit_euro_size_bit"] == ""
    # |tp| 64 / 84 ≈ 76.2% → strong conc owns the clip; trim stays in fields.
    assert g["window_a_closes_exit_euro_conc"] == "tp"
    assert g["window_a_closes_exit_euro_conc_pct"] == 76.2
    assert g["window_a_closes_exit_euro_conc_hot"] is False
    assert g["window_a_closes_exit_euro_conc_bit"] == (
        "€ conc strong · tp · 76.2%"
    )
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 8.3%"
    assert "€ lead" not in g["line"]
    assert "€ offset" not in g["line"]
    assert "€ gap" not in g["line"]
    assert "€ size" not in g["line"]
    assert "trim share quiet · 8.3%" not in g["line"]  # trim stays in fields
    assert "€ conc strong · tp · 76.2%" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_offset_hot() -> None:
    """Matching lead alone must not hide a large adverse runner-up (warns)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 4,
        "fees": 4.0,
        "realized_pnl": 36.0,
        "net_after_all_fees": 32.0,
        "wins": 3,
        "losses": 1,
        "avg_win": 100.0 / 3.0,
        "avg_loss": 60.0,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 0,
        "win_streak_max": 2,
        "flat_closes": 0,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -10.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -60.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    assert g["window_a_closes_exit_euro_lead"] is None
    assert g["window_a_closes_exit_euro_lead_bit"] == ""
    assert g["window_a_closes_exit_euro_offset"] == "sl"
    assert g["window_a_closes_exit_euro_offset_pnl"] == -60.0
    assert g["window_a_closes_exit_euro_offset_ratio"] == 0.6
    assert g["window_a_closes_exit_euro_offset_hot"] is True
    assert g["window_a_closes_exit_euro_offset_bit"] == (
        "€ offset hot · sl −€60 · 0.6×"
    )
    # |tp| 100 / 160 = 62.5% → strong conc owns the clip; offset stays in fields.
    assert g["window_a_closes_exit_euro_conc"] == "tp"
    assert g["window_a_closes_exit_euro_conc_pct"] == 62.5
    assert g["window_a_closes_exit_euro_conc_hot"] is False
    assert g["window_a_closes_exit_euro_conc_bit"] == (
        "€ conc strong · tp · 62.5%"
    )
    assert g["window_a_closes_exit_trim_share_bit"] == "trim share quiet · 0%"
    assert g["tone"] == "warn"
    assert "€ offset" not in without["line"]
    assert "trim share quiet · 0%" not in g["line"]  # trim stays in fields
    assert "€ offset hot · sl −€60 · 0.6×" not in g["line"]  # offset in fields
    assert "€ conc strong · tp · 62.5%" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_offset_quiet() -> None:
    """Take-profit runner-up speaks without escalating from offset alone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 24,
            "buys": 12,
            "sells": 4,
            "fees": 4.0,
            "realized_pnl": -44.0,
            "net_after_all_fees": -48.0,
            "wins": 1,
            "losses": 3,
            "avg_win": 60.0,
            "avg_loss": 100.0 / 3.0,
            "loss_streak": 0,
            "loss_streak_max": 2,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 1,
            "exit_sl": 3,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 10.0,
            "exit_pnl_sl": -100.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 24,
            "buys": 12,
            "sells": 4,
            "fees": 4.0,
            "realized_pnl": -40.0,
            "net_after_all_fees": -44.0,
            "wins": 1,
            "losses": 3,
            "avg_win": 60.0,
            "avg_loss": 100.0 / 3.0,
            "loss_streak": 0,
            "loss_streak_max": 2,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 1,
            "exit_sl": 3,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 60.0,
            "exit_pnl_sl": -100.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    assert g["window_a_closes_exit_euro_lead"] is None
    assert g["window_a_closes_exit_euro_offset"] == "tp"
    assert g["window_a_closes_exit_euro_offset_hot"] is False
    assert g["window_a_closes_exit_euro_offset_bit"] == (
        "€ offset quiet · tp +€60 · 0.6×"
    )
    assert g["window_a_closes_exit_euro_gap_bit"] == ""
    # |sl| 100 / 160 = 62.5% → hot conc owns the clip; offset stays in fields.
    assert g["window_a_closes_exit_euro_conc"] == "sl"
    assert g["window_a_closes_exit_euro_conc_pct"] == 62.5
    assert g["window_a_closes_exit_euro_conc_hot"] is True
    assert g["window_a_closes_exit_euro_conc_bit"] == "€ conc hot · sl · 62.5%"
    # SL share hot (75%) + conc hot warn; offset quiet does not add warn.
    assert g["window_a_closes_exit_sl_share_hot"] is True
    assert g["tone"] == "warn"
    assert "€ offset" not in without["line"]
    assert "€ gap" not in g["line"]
    assert "€ offset quiet · tp +€60 · 0.6×" not in g["line"]  # offset in fields
    assert "€ conc hot · sl · 62.5%" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_gap_hot() -> None:
    """€ lead alone must not hide a wide adverse disagree gap (warns)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 24,
        "buys": 12,
        "sells": 4,
        "fees": 4.0,
        "realized_pnl": -188.0,
        "net_after_all_fees": -192.0,
        "wins": 3,
        "losses": 1,
        "avg_win": 4.0,
        "avg_loss": 200.0,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 0,
        "win_streak_max": 2,
        "flat_closes": 0,
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 50.0,
            "exit_pnl_sl": -80.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            **base,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 12.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    assert g["window_a_closes_exit_euro_lead"] == "sl"
    assert g["window_a_closes_exit_euro_lead_bit"] == "€ lead sl · −€200"
    assert g["window_a_closes_exit_euro_lead_hot"] is True
    assert g["window_a_closes_exit_euro_offset_bit"] == ""
    assert g["window_a_closes_exit_euro_gap_ratio"] == 16.67
    assert g["window_a_closes_exit_euro_gap_vs"] == "tp"
    assert g["window_a_closes_exit_euro_gap_hot"] is True
    assert g["window_a_closes_exit_euro_gap_bit"] == "€ gap hot · 16.7× vs tp"
    # |sl| 200 / 212 ≈ 94.3% → hot conc + fat size 50×; size-n thin owns clip.
    assert g["window_a_closes_exit_euro_conc"] == "sl"
    assert g["window_a_closes_exit_euro_conc_pct"] == 94.3
    assert g["window_a_closes_exit_euro_conc_hot"] is True
    assert g["window_a_closes_exit_euro_conc_bit"] == "€ conc hot · sl · 94.3%"
    assert g["window_a_closes_exit_euro_size_ratio"] == 50.0
    assert g["window_a_closes_exit_euro_size_hot"] is True
    assert g["window_a_closes_exit_euro_size_bit"] == "€ size fat hot · sl · 50×"
    assert g["window_a_closes_exit_euro_size_n"] == "thin"
    assert g["window_a_closes_exit_euro_size_n_count"] == 1
    assert g["window_a_closes_exit_euro_size_n_thin"] is True
    assert g["window_a_closes_exit_euro_size_n_bit"] == (
        "€ size n thin · sl · 1 closes <3"
    )
    assert g["window_a_closes_exit_euro_size_sign"] == "loss"
    assert g["window_a_closes_exit_euro_size_sign_pnl"] == -200.0
    assert g["window_a_closes_exit_euro_size_sign_loss"] is True
    assert g["window_a_closes_exit_euro_size_sign_bit"] == (
        "€ size sign loss · sl · −€200"
    )
    assert g["tone"] == "warn"
    assert "€ gap" not in without["line"]
    assert "€ lead sl · −€200" not in g["line"]  # lead stays in fields
    assert "€ gap hot · 16.7× vs tp" not in g["line"]  # gap stays in fields
    assert "€ conc hot · sl · 94.3%" not in g["line"]  # conc stays in fields
    assert "€ size fat hot · sl · 50×" not in g["line"]  # size stays in fields
    assert "€ size n thin · sl · 1 closes <3" not in g["line"]  # size-n stays in fields
    assert "€ size sign loss · sl · −€200" not in g["line"]  # size-sign stays in fields
    assert "€ size rest sign win · +€12" not in g["line"]  # rest-sign stays in fields
    assert (
        "€ size clash · lead loss" in g["line"]
        or "€ size clash net" in g["line"]
        or "€ size clash keep" in g["line"]
        or "keep fees" in g["line"]
    )
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_gap_quiet() -> None:
    """Take-profit € gap speaks without escalating from gap alone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 24,
            "buys": 12,
            "sells": 4,
            "fees": 4.0,
            "realized_pnl": 40.0,
            "net_after_all_fees": 36.0,
            "wins": 1,
            "losses": 3,
            "avg_win": 90.0,
            "avg_loss": 50.0 / 3.0,
            "loss_streak": 0,
            "loss_streak_max": 2,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 1,
            "exit_sl": 3,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 90.0,
            "exit_pnl_sl": -50.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 24,
            "buys": 12,
            "sells": 4,
            "fees": 4.0,
            "realized_pnl": 82.0,
            "net_after_all_fees": 78.0,
            "wins": 1,
            "losses": 3,
            "avg_win": 90.0,
            "avg_loss": 8.0 / 3.0,
            "loss_streak": 0,
            "loss_streak_max": 2,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 1,
            "exit_sl": 3,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 90.0,
            "exit_pnl_sl": -8.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    assert g["window_a_closes_exit_euro_lead"] == "tp"
    assert g["window_a_closes_exit_euro_gap_ratio"] == 11.25
    assert g["window_a_closes_exit_euro_gap_vs"] == "sl"
    assert g["window_a_closes_exit_euro_gap_hot"] is False
    assert g["window_a_closes_exit_euro_gap_bit"] == "€ gap quiet · 11.2× vs sl"
    # |tp| 90 / 98 ≈ 91.8% → strong conc + fat size; size-n thin owns clip.
    assert g["window_a_closes_exit_euro_conc"] == "tp"
    assert g["window_a_closes_exit_euro_conc_pct"] == 91.8
    assert g["window_a_closes_exit_euro_conc_hot"] is False
    assert g["window_a_closes_exit_euro_conc_bit"] == (
        "€ conc strong · tp · 91.8%"
    )
    assert g["window_a_closes_exit_euro_size_ratio"] == 33.75
    assert g["window_a_closes_exit_euro_size_hot"] is False
    assert g["window_a_closes_exit_euro_size_bit"] == (
        "€ size fat quiet · tp · 33.8×"
    )
    assert g["window_a_closes_exit_euro_size_n"] == "thin"
    assert g["window_a_closes_exit_euro_size_n_count"] == 1
    assert g["window_a_closes_exit_euro_size_n_thin"] is True
    assert g["window_a_closes_exit_euro_size_n_bit"] == (
        "€ size n thin · tp · 1 closes <3"
    )
    assert g["window_a_closes_exit_euro_size_sign"] == "win"
    assert g["window_a_closes_exit_euro_size_sign_pnl"] == 90.0
    assert g["window_a_closes_exit_euro_size_sign_loss"] is False
    assert g["window_a_closes_exit_euro_size_sign_bit"] == (
        "€ size sign win · tp · +€90"
    )
    # SL share hot (75%) + size-n thin warn; gap/size/sign win quiet alone.
    assert g["window_a_closes_exit_sl_share_hot"] is True
    assert g["tone"] == "warn"
    assert "€ gap" not in without["line"]
    assert "€ lead tp · +€90" not in g["line"]  # lead stays in fields
    assert "€ gap quiet · 11.2× vs sl" not in g["line"]  # gap stays in fields
    assert "€ conc strong · tp · 91.8%" not in g["line"]  # conc stays in fields
    assert "€ size fat quiet · tp · 33.8×" not in g["line"]  # size stays in fields
    assert "€ size n thin · tp · 1 closes <3" not in g["line"]  # size-n stays in fields
    assert "€ size sign win · tp · +€90" not in g["line"]  # size-sign stays in fields
    assert "€ size rest sign loss · −€8" not in g["line"]  # rest-sign stays in fields
    assert (
        "€ size clash · lead win" in g["line"]
        or "€ size clash net" in g["line"]
        or "€ size clash keep" in g["line"]
        or "keep fees" in g["line"]
    )
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_conc_hot() -> None:
    """€ gap alone must not hide that one adverse reason owns most |exit €|."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 24,
            "buys": 12,
            "sells": 4,
            "fees": 4.0,
            "realized_pnl": -188.0,
            "net_after_all_fees": -192.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 4.0,
            "avg_loss": 200.0,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 0,
            "win_streak_max": 2,
            "flat_closes": 0,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 24,
            "buys": 12,
            "sells": 4,
            "fees": 4.0,
            "realized_pnl": -188.0,
            "net_after_all_fees": -192.0,
            "wins": 3,
            "losses": 1,
            "avg_win": 4.0,
            "avg_loss": 200.0,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 0,
            "win_streak_max": 2,
            "flat_closes": 0,
            "exit_tp": 3,
            "exit_sl": 1,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 12.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    assert g["window_a_closes_exit_euro_gap_bit"] == "€ gap hot · 16.7× vs tp"
    assert g["window_a_closes_exit_euro_conc"] == "sl"
    assert g["window_a_closes_exit_euro_conc_pct"] == 94.3
    assert g["window_a_closes_exit_euro_conc_hot"] is True
    assert g["window_a_closes_exit_euro_conc_bit"] == "€ conc hot · sl · 94.3%"
    assert g["window_a_closes_exit_euro_size_ratio"] == 50.0
    assert g["window_a_closes_exit_euro_size_hot"] is True
    assert g["window_a_closes_exit_euro_size_bit"] == "€ size fat hot · sl · 50×"
    assert g["window_a_closes_exit_euro_size_n"] == "thin"
    assert g["window_a_closes_exit_euro_size_n_count"] == 1
    assert g["window_a_closes_exit_euro_size_n_thin"] is True
    assert g["window_a_closes_exit_euro_size_n_bit"] == (
        "€ size n thin · sl · 1 closes <3"
    )
    assert g["window_a_closes_exit_euro_size_sign"] == "loss"
    assert g["window_a_closes_exit_euro_size_sign_pnl"] == -200.0
    assert g["window_a_closes_exit_euro_size_sign_loss"] is True
    assert g["window_a_closes_exit_euro_size_sign_bit"] == (
        "€ size sign loss · sl · −€200"
    )
    assert g["tone"] == "warn"
    assert "€ size" not in without["line"]
    assert "€ gap hot · 16.7× vs tp" not in g["line"]  # gap stays in fields
    assert "€ conc hot · sl · 94.3%" not in g["line"]  # conc stays in fields
    assert "€ size fat hot · sl · 50×" not in g["line"]  # size stays in fields
    assert "€ size n thin · sl · 1 closes <3" not in g["line"]  # size-n stays in fields
    assert "€ size sign loss · sl · −€200" not in g["line"]  # size-sign stays in fields
    assert "€ size rest sign win · +€12" not in g["line"]  # rest-sign stays in fields
    assert (
        "€ size clash · lead loss" in g["line"]
        or "€ size clash net" in g["line"]
        or "€ size clash keep" in g["line"]
        or "keep fees" in g["line"]
    )
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_conc_quiet() -> None:
    """Quiet € concentration speaks without escalating from conc alone."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 14,
            "buys": 7,
            "sells": 4,
            "fees": 4.0,
            "realized_pnl": -1.0,
            "net_after_all_fees": -5.0,
            "wins": 2,
            "losses": 2,
            "avg_win": 30.0,
            "avg_loss": 26.5,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 1,
            "exit_sl": 1,
            "exit_rot": 1,
            "exit_trim": 1,
            "exit_pnl_tp": 30.0,
            "exit_pnl_sl": -28.0,
            "exit_pnl_rot": -25.0,
            "exit_pnl_trim": 22.0,
        },
    )
    # |tp| 30 / 105 ≈ 28.6% → quiet; no lead/offset/gap (near-tie movers).
    assert g["window_a_closes_exit_euro_conc"] == "tp"
    assert g["window_a_closes_exit_euro_conc_pct"] == 28.6
    assert g["window_a_closes_exit_euro_conc_hot"] is False
    assert g["window_a_closes_exit_euro_conc_bit"] == (
        "€ conc quiet · tp · 28.6%"
    )
    assert "€ conc quiet · tp · 28.6%" in g["line"]
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_count_skew_quiet() -> None:
    """Same-reason count/€ ownership with ≥20pp share gap speaks quiet skew."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 76.0,
            "wins": 6,
            "losses": 2,
            "avg_win": 15.0,
            "avg_loss": 5.0,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 0,
            "win_streak_max": 2,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 80.0,
            "exit_pnl_sl": -20.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 95.0,
            "net_after_all_fees": 91.0,
            "wins": 6,
            "losses": 2,
            "avg_win": 16.67,
            "avg_loss": 2.5,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 0,
            "win_streak_max": 2,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    # Count lead tp 75%; € conc tp 95.2% → gap 20.2pp quiet + fat size 6.7×.
    assert g["window_a_closes_exit_euro_conc"] == "tp"
    assert g["window_a_closes_exit_euro_conc_pct"] == 95.2
    assert g["window_a_closes_exit_euro_count_skew_pp"] == 20.2
    assert g["window_a_closes_exit_euro_count_skew_hot"] is False
    assert g["window_a_closes_exit_euro_count_skew_bit"] == (
        "€ skew quiet · tp · n 75% · € 95.2%"
    )
    assert g["window_a_closes_exit_euro_size_ratio"] == 6.67
    assert g["window_a_closes_exit_euro_size_hot"] is False
    assert g["window_a_closes_exit_euro_size_bit"] == (
        "€ size fat quiet · tp · 6.7×"
    )
    assert g["window_a_closes_exit_euro_size_n"] == "ok"
    assert g["window_a_closes_exit_euro_size_n_count"] == 6
    assert g["window_a_closes_exit_euro_size_n_thin"] is False
    assert g["window_a_closes_exit_euro_size_n_bit"] == (
        "€ size n ok · tp · 6 closes"
    )
    assert g["window_a_closes_exit_euro_size_sign"] == "win"
    assert g["window_a_closes_exit_euro_size_sign_pnl"] == 100.0
    assert g["window_a_closes_exit_euro_size_sign_loss"] is False
    assert g["window_a_closes_exit_euro_size_sign_bit"] == (
        "€ size sign win · tp · +€100"
    )
    assert "€ size" not in without["line"]  # mid size silent
    assert "€ skew" not in g["line"]  # skew stays in fields
    assert "€ conc" not in g["line"]  # conc stays in fields
    assert "€ size fat quiet · tp · 6.7×" not in g["line"]  # size stays in fields
    assert "€ size n ok · tp · 6 closes" not in g["line"]  # size-n stays in fields
    assert "€ size sign win · tp · +€100" not in g["line"]  # size-sign stays in fields
    assert "€ size rest sign loss · −€5" not in g["line"]  # rest-sign stays in fields
    assert (
        "€ size clash · lead win" in g["line"]
        or "€ size clash net" in g["line"]
        or "€ size clash keep" in g["line"]
        or "keep fees" in g["line"]
    )
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_count_skew_hot() -> None:
    """€ conc alone must not hide that count/€ shares diverge ≥20pp on adverse."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": -60.0,
            "net_after_all_fees": -64.0,
            "wins": 2,
            "losses": 6,
            "avg_win": 10.0,
            "avg_loss": 13.33,
            "loss_streak": 2,
            "loss_streak_max": 3,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 2,
            "exit_sl": 6,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 20.0,
            "exit_pnl_sl": -80.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": -190.0,
            "net_after_all_fees": -194.0,
            "wins": 2,
            "losses": 6,
            "avg_win": 5.0,
            "avg_loss": 33.33,
            "loss_streak": 2,
            "loss_streak_max": 3,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 2,
            "exit_sl": 6,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 10.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    # Count lead sl 75%; € conc sl 95.2% → gap 20.2pp hot + fat size 6.7×.
    assert g["window_a_closes_exit_euro_conc"] == "sl"
    assert g["window_a_closes_exit_euro_conc_pct"] == 95.2
    assert g["window_a_closes_exit_euro_count_skew_pp"] == 20.2
    assert g["window_a_closes_exit_euro_count_skew_hot"] is True
    assert g["window_a_closes_exit_euro_count_skew_bit"] == (
        "€ skew hot · sl · n 75% · € 95.2%"
    )
    assert g["window_a_closes_exit_euro_size_ratio"] == 6.67
    assert g["window_a_closes_exit_euro_size_hot"] is True
    assert g["window_a_closes_exit_euro_size_bit"] == (
        "€ size fat hot · sl · 6.7×"
    )
    assert g["window_a_closes_exit_euro_size_n"] == "ok"
    assert g["window_a_closes_exit_euro_size_n_count"] == 6
    assert g["window_a_closes_exit_euro_size_n_thin"] is False
    assert g["window_a_closes_exit_euro_size_n_bit"] == (
        "€ size n ok · sl · 6 closes"
    )
    assert g["window_a_closes_exit_euro_size_sign"] == "loss"
    assert g["window_a_closes_exit_euro_size_sign_pnl"] == -200.0
    assert g["window_a_closes_exit_euro_size_sign_loss"] is True
    assert g["window_a_closes_exit_euro_size_sign_bit"] == (
        "€ size sign loss · sl · −€200"
    )
    assert g["tone"] == "warn"
    assert "€ size" not in without["line"]  # mid size silent
    assert "€ skew" not in g["line"]  # skew stays in fields
    assert "€ conc" not in g["line"]  # conc stays in fields
    assert "€ size fat hot · sl · 6.7×" not in g["line"]  # size stays in fields
    assert "€ size n ok · sl · 6 closes" not in g["line"]  # size-n stays in fields
    assert "€ size sign loss · sl · −€200" not in g["line"]  # size-sign stays in fields
    assert "€ size rest sign win · +€10" not in g["line"]  # rest-sign stays in fields
    assert (
        "€ size clash · lead loss" in g["line"]
        or "€ size clash net" in g["line"]
        or "€ size clash keep" in g["line"]
        or "keep fees" in g["line"]
    )
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_quiet() -> None:
    """Fat €/close vs rest speaks quiet size after skew (tp does not warn)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 76.0,
            "wins": 6,
            "losses": 2,
            "avg_win": 15.0,
            "avg_loss": 5.0,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 0,
            "win_streak_max": 2,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 80.0,
            "exit_pnl_sl": -20.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 95.0,
            "net_after_all_fees": 91.0,
            "wins": 6,
            "losses": 2,
            "avg_win": 16.67,
            "avg_loss": 2.5,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 0,
            "win_streak_max": 2,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    # tp avg €16.67 vs sl avg €2.5 → 6.67× fat quiet; size-sign win owns clip.
    assert g["window_a_closes_exit_euro_size_ratio"] == 6.67
    assert g["window_a_closes_exit_euro_size_hot"] is False
    assert g["window_a_closes_exit_euro_size_bit"] == (
        "€ size fat quiet · tp · 6.7×"
    )
    assert g["window_a_closes_exit_euro_size_n"] == "ok"
    assert g["window_a_closes_exit_euro_size_n_count"] == 6
    assert g["window_a_closes_exit_euro_size_n_thin"] is False
    assert g["window_a_closes_exit_euro_size_n_bit"] == (
        "€ size n ok · tp · 6 closes"
    )
    assert g["window_a_closes_exit_euro_size_sign"] == "win"
    assert g["window_a_closes_exit_euro_size_sign_pnl"] == 100.0
    assert g["window_a_closes_exit_euro_size_sign_loss"] is False
    assert g["window_a_closes_exit_euro_size_sign_bit"] == (
        "€ size sign win · tp · +€100"
    )
    assert g["window_a_closes_exit_euro_count_skew_bit"] == (
        "€ skew quiet · tp · n 75% · € 95.2%"
    )
    assert "€ size" not in without["line"]  # mid size silent
    assert "€ skew" not in g["line"]  # skew stays in fields
    assert "€ size fat quiet · tp · 6.7×" not in g["line"]  # size stays in fields
    assert "€ size n ok · tp · 6 closes" not in g["line"]  # size-n stays in fields
    assert "€ size sign win · tp · +€100" not in g["line"]  # size-sign stays in fields
    assert "€ size rest sign loss · −€5" not in g["line"]  # rest-sign stays in fields
    assert (
        "€ size clash · lead win" in g["line"]
        or "€ size clash net" in g["line"]
        or "€ size clash keep" in g["line"]
        or "keep fees" in g["line"]
    )
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_hot() -> None:
    """Skew alone must not hide that €-conc closes are fat vs rest (warns)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": -60.0,
            "net_after_all_fees": -64.0,
            "wins": 2,
            "losses": 6,
            "avg_win": 10.0,
            "avg_loss": 13.33,
            "loss_streak": 2,
            "loss_streak_max": 3,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 2,
            "exit_sl": 6,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 20.0,
            "exit_pnl_sl": -80.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": -190.0,
            "net_after_all_fees": -194.0,
            "wins": 2,
            "losses": 6,
            "avg_win": 5.0,
            "avg_loss": 33.33,
            "loss_streak": 2,
            "loss_streak_max": 3,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 2,
            "exit_sl": 6,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 10.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    # sl avg €33.33 vs tp avg €5 → 6.67× fat hot; clash owns clip.
    assert g["window_a_closes_exit_euro_size_ratio"] == 6.67
    assert g["window_a_closes_exit_euro_size_hot"] is True
    assert g["window_a_closes_exit_euro_size_bit"] == (
        "€ size fat hot · sl · 6.7×"
    )
    assert g["window_a_closes_exit_euro_size_n"] == "ok"
    assert g["window_a_closes_exit_euro_size_n_count"] == 6
    assert g["window_a_closes_exit_euro_size_n_thin"] is False
    assert g["window_a_closes_exit_euro_size_n_bit"] == (
        "€ size n ok · sl · 6 closes"
    )
    assert g["window_a_closes_exit_euro_size_sign"] == "loss"
    assert g["window_a_closes_exit_euro_size_sign_pnl"] == -200.0
    assert g["window_a_closes_exit_euro_size_sign_loss"] is True
    assert g["window_a_closes_exit_euro_size_sign_bit"] == (
        "€ size sign loss · sl · −€200"
    )
    assert g["tone"] == "warn"
    assert "€ size" not in without["line"]  # mid size silent
    assert "€ skew" not in g["line"]  # skew stays in fields
    assert "€ size fat hot · sl · 6.7×" not in g["line"]  # size stays in fields
    assert "€ size n ok · sl · 6 closes" not in g["line"]  # size-n stays in fields
    assert "€ size sign loss · sl · −€200" not in g["line"]  # size-sign stays in fields
    assert "€ size rest sign win · +€10" not in g["line"]  # rest-sign stays in fields
    assert (
        "€ size clash · lead loss" in g["line"]
        or "€ size clash net" in g["line"]
        or "€ size clash keep" in g["line"]
        or "keep fees" in g["line"]
    )
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_n_thin() -> None:
    """Fat € size from one close must speak size-n thin (sample honesty)."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 76.0,
            "wins": 1,
            "losses": 7,
            "avg_win": 100.0,
            "avg_loss": 2.0,
            "loss_streak": 2,
            "loss_streak_max": 3,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 1,
            "exit_sl": 7,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -14.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    g = without  # same fixture: fat from 1 tp close → clash owns clip
    assert g["window_a_closes_exit_euro_size_ratio"] == 50.0
    assert g["window_a_closes_exit_euro_size_bit"] == (
        "€ size fat quiet · tp · 50×"
    )
    assert g["window_a_closes_exit_euro_size_n"] == "thin"
    assert g["window_a_closes_exit_euro_size_n_count"] == 1
    assert g["window_a_closes_exit_euro_size_n_thin"] is True
    assert g["window_a_closes_exit_euro_size_n_bit"] == (
        "€ size n thin · tp · 1 closes <3"
    )
    assert g["window_a_closes_exit_euro_size_sign"] == "win"
    assert g["window_a_closes_exit_euro_size_sign_pnl"] == 100.0
    assert g["window_a_closes_exit_euro_size_sign_loss"] is False
    assert g["window_a_closes_exit_euro_size_sign_bit"] == (
        "€ size sign win · tp · +€100"
    )
    assert g["tone"] == "warn"
    assert "€ size fat quiet · tp · 50×" not in g["line"]  # size stays in fields
    assert "€ size n thin · tp · 1 closes <3" not in g["line"]  # size-n stays in fields
    assert "€ size sign win · tp · +€100" not in g["line"]  # size-sign stays in fields
    assert "€ size rest sign loss · −€14" not in g["line"]  # rest-sign stays in fields
    assert (
        "€ size clash · lead win" in g["line"]
        or "€ size clash net" in g["line"]
        or "€ size clash keep" in g["line"]
        or "keep fees" in g["line"]
    )
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_loss() -> None:
    """|€| size alone must not hide that the €-conc reason is a signed loss."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": -60.0,
            "net_after_all_fees": -64.0,
            "wins": 2,
            "losses": 6,
            "avg_win": 10.0,
            "avg_loss": 13.33,
            "loss_streak": 2,
            "loss_streak_max": 3,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 2,
            "exit_sl": 6,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 20.0,
            "exit_pnl_sl": -80.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": -190.0,
            "net_after_all_fees": -194.0,
            "wins": 2,
            "losses": 6,
            "avg_win": 5.0,
            "avg_loss": 33.33,
            "loss_streak": 2,
            "loss_streak_max": 3,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 2,
            "exit_sl": 6,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 10.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    assert g["window_a_closes_exit_euro_size_sign"] == "loss"
    assert g["window_a_closes_exit_euro_size_sign_pnl"] == -200.0
    assert g["window_a_closes_exit_euro_size_sign_loss"] is True
    assert g["window_a_closes_exit_euro_size_sign_bit"] == (
        "€ size sign loss · sl · −€200"
    )
    assert g["window_a_closes_exit_euro_size_rest_sign"] == "win"
    assert g["window_a_closes_exit_euro_size_rest_sign_pnl"] == 10.0
    assert g["window_a_closes_exit_euro_size_rest_sign_loss"] is False
    assert g["window_a_closes_exit_euro_size_rest_sign_bit"] == (
        "€ size rest sign win · +€10"
    )
    assert g["tone"] == "warn"
    assert "€ size sign" not in without["line"]  # mid size silent → no sign
    assert "€ size n ok · sl · 6 closes" not in g["line"]
    assert "€ size sign loss · sl · −€200" not in g["line"]  # size-sign stays in fields
    assert "€ size rest sign win · +€10" not in g["line"]  # rest-sign stays in fields
    assert (
        "€ size clash · lead loss" in g["line"]
        or "€ size clash net" in g["line"]
        or "€ size clash keep" in g["line"]
        or "keep fees" in g["line"]
    )
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_rest_sign_loss() -> None:
    """Lead size-sign alone must not hide that the rest reasons are a signed loss."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    without = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 95.0,
            "net_after_all_fees": 91.0,
            "wins": 6,
            "losses": 2,
            "avg_win": 16.67,
            "avg_loss": 2.5,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 2,
            "win_streak_max": 3,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    # mid size (near equal avg |€|) stays silent → no rest sign either
    mid = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 60.0,
            "net_after_all_fees": 56.0,
            "wins": 6,
            "losses": 2,
            "avg_win": 13.33,
            "avg_loss": 10.0,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 2,
            "win_streak_max": 3,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 80.0,
            "exit_pnl_sl": -20.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    g = without
    assert g["window_a_closes_exit_euro_size_sign"] == "win"
    assert g["window_a_closes_exit_euro_size_sign_pnl"] == 100.0
    assert g["window_a_closes_exit_euro_size_sign_loss"] is False
    assert g["window_a_closes_exit_euro_size_sign_bit"] == (
        "€ size sign win · tp · +€100"
    )
    assert g["window_a_closes_exit_euro_size_rest_sign"] == "loss"
    assert g["window_a_closes_exit_euro_size_rest_sign_pnl"] == -5.0
    assert g["window_a_closes_exit_euro_size_rest_sign_loss"] is True
    assert g["window_a_closes_exit_euro_size_rest_sign_bit"] == (
        "€ size rest sign loss · −€5"
    )
    assert g["window_a_closes_exit_euro_size_sign_clash"] == "clash"
    assert g["window_a_closes_exit_euro_size_sign_clash_loss"] is False
    assert g["window_a_closes_exit_euro_size_sign_clash_bit"] == (
        "€ size clash · lead win · rest loss"
    )
    assert g["tone"] == "warn"
    assert "€ size rest sign" not in mid["line"]  # mid size silent → no rest
    assert "€ size clash" not in mid["line"]
    assert "€ size sign win · tp · +€100" not in g["line"]  # size-sign stays in fields
    assert "€ size rest sign loss · −€5" not in g["line"]  # rest-sign stays in fields
    assert (
        "€ size clash · lead win" in g["line"]
        or "€ size clash net" in g["line"]
        or "€ size clash keep" in g["line"]
        or "keep fees" in g["line"]
    )
    assert len(g["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_rest_sign_win() -> None:
    """Lead size-sign loss alone must not hide that the rest reasons are a signed win."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    # Near-zero rest (€0) keeps rest-sign silent so size-sign can own the clip.
    flat_rest = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 14,
            "buys": 4,
            "sells": 10,
            "fees": 4.0,
            "realized_pnl": 300.0,
            "net_after_all_fees": 296.0,
            "wins": 8,
            "losses": 2,
            "avg_win": 37.5,
            "avg_loss": 25.0,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 2,
            "win_streak_max": 4,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 2,
            "exit_trim": 0,
            "exit_pnl_tp": 300.0,
            "exit_pnl_sl": -50.0,
            "exit_pnl_rot": 50.0,
            "exit_pnl_trim": 0.0,
        },
    )
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": -190.0,
            "net_after_all_fees": -194.0,
            "wins": 2,
            "losses": 6,
            "avg_win": 5.0,
            "avg_loss": 33.33,
            "loss_streak": 2,
            "loss_streak_max": 3,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 2,
            "exit_sl": 6,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 10.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    assert flat_rest["window_a_closes_exit_euro_size_rest_sign_bit"] == ""
    assert flat_rest["window_a_closes_exit_euro_size_sign_clash_bit"] == ""
    assert flat_rest["window_a_closes_exit_euro_size_sign"] == "win"
    assert "€ size sign win · tp · +€300" in flat_rest["line"]
    assert "€ size rest sign" not in flat_rest["line"]
    assert "€ size clash" not in flat_rest["line"]
    assert g["window_a_closes_exit_euro_size_sign"] == "loss"
    assert g["window_a_closes_exit_euro_size_sign_pnl"] == -200.0
    assert g["window_a_closes_exit_euro_size_sign_loss"] is True
    assert g["window_a_closes_exit_euro_size_rest_sign"] == "win"
    assert g["window_a_closes_exit_euro_size_rest_sign_pnl"] == 10.0
    assert g["window_a_closes_exit_euro_size_rest_sign_loss"] is False
    assert g["window_a_closes_exit_euro_size_rest_sign_bit"] == (
        "€ size rest sign win · +€10"
    )
    assert g["window_a_closes_exit_euro_size_sign_clash"] == "clash"
    assert g["window_a_closes_exit_euro_size_sign_clash_loss"] is True
    assert g["window_a_closes_exit_euro_size_sign_clash_bit"] == (
        "€ size clash · lead loss · rest win"
    )
    assert g["tone"] == "warn"
    assert "€ size sign loss · sl · −€200" not in g["line"]
    assert "€ size rest sign win · +€10" not in g["line"]  # rest-sign stays in fields
    assert (
        "€ size clash · lead loss" in g["line"]
        or "€ size clash net" in g["line"]
        or "€ size clash keep" in g["line"]
        or "keep fees" in g["line"]
    )
    assert len(g["line"]) <= 96
    assert len(flat_rest["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash() -> None:
    """Rest-sign alone must not hide that lead and rest signed nets disagree."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    # Same polarity (both win) stays silent on clash — rest-sign owns the clip.
    same = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 105.0,
            "net_after_all_fees": 101.0,
            "wins": 8,
            "losses": 0,
            "avg_win": 13.12,
            "avg_loss": 0.0,
            "loss_streak": 0,
            "loss_streak_max": 0,
            "win_streak": 2,
            "win_streak_max": 4,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": 5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    # Lead loss · rest win → clash warns (fat bucket is the loser).
    g = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": -190.0,
            "net_after_all_fees": -194.0,
            "wins": 2,
            "losses": 6,
            "avg_win": 5.0,
            "avg_loss": 33.33,
            "loss_streak": 2,
            "loss_streak_max": 3,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 2,
            "exit_sl": 6,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 10.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    assert same["window_a_closes_exit_euro_size_sign"] == "win"
    assert same["window_a_closes_exit_euro_size_rest_sign"] == "win"
    assert same["window_a_closes_exit_euro_size_rest_sign_bit"] == (
        "€ size rest sign win · +€5"
    )
    assert same["window_a_closes_exit_euro_size_sign_clash_bit"] == ""
    assert same["window_a_closes_exit_euro_size_sign_clash"] is None
    assert same["window_a_closes_exit_euro_size_sign_clash_net_bit"] == ""
    assert "€ size clash" not in same["line"]
    assert g["window_a_closes_exit_euro_size_sign_clash"] == "clash"
    assert g["window_a_closes_exit_euro_size_sign_clash_loss"] is True
    assert g["window_a_closes_exit_euro_size_sign_clash_bit"] == (
        "€ size clash · lead loss · rest win"
    )
    # Clash keep owns the clip when |net|÷(|lead|+|rest|) is strong/thin.
    assert g["window_a_closes_exit_euro_size_sign_clash_net"] == "loss"
    assert g["window_a_closes_exit_euro_size_sign_clash_net_pnl"] == -190.0
    assert g["window_a_closes_exit_euro_size_sign_clash_net_loss"] is True
    assert g["window_a_closes_exit_euro_size_sign_clash_net_bit"] == (
        "€ size clash net loss · −€190"
    )
    assert g["window_a_closes_exit_euro_size_sign_clash_keep"] == "strong"
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_ratio"] == 0.9
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_thin"] is False
    assert g["window_a_closes_exit_euro_size_sign_clash_keep_bit"] == (
        "€ size clash keep strong · 0.9×"
    )
    assert g["tone"] == "warn"
    assert "€ size rest sign win · +€10" not in g["line"]
    assert "€ size clash · lead loss" not in g["line"]  # clash stays in fields
    assert "€ size clash net loss · −€190" not in g["line"]  # net stays in fields
    assert "€ size clash keep strong · 0.9×" in g["line"]
    assert len(g["line"]) <= 96
    assert len(same["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_net() -> None:
    """Clash alone must not hide who keeps the money after a size-sign disagree."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    # Mid keep (0.25..0.5) stays silent — net owns the clip.
    mid_keep = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 76.0,
            "wins": 4,
            "losses": 4,
            "avg_win": 35.0,
            "avg_loss": 15.0,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 1,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 4,
            "exit_sl": 4,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 140.0,
            "exit_pnl_sl": -60.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    # Lead win · rest loss with leftover → net + strong keep; keep owns clip
    # (fees 0 so keep-fees stays silent and keep can still own the line).
    win = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 0.0,
            "realized_pnl": 190.0,
            "net_after_all_fees": 190.0,
            "wins": 6,
            "losses": 2,
            "avg_win": 33.33,
            "avg_loss": 5.0,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 2,
            "win_streak_max": 3,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 200.0,
            "exit_pnl_sl": -10.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    # Lead loss · rest win with leftover → net loss + strong keep; keep owns clip.
    loss = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": -190.0,
            "net_after_all_fees": -194.0,
            "wins": 2,
            "losses": 6,
            "avg_win": 5.0,
            "avg_loss": 33.33,
            "loss_streak": 2,
            "loss_streak_max": 3,
            "win_streak": 0,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 2,
            "exit_sl": 6,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 10.0,
            "exit_pnl_sl": -200.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    assert mid_keep["window_a_closes_exit_euro_size_sign_clash"] == "clash"
    assert mid_keep["window_a_closes_exit_euro_size_sign_clash_net"] == "win"
    assert mid_keep["window_a_closes_exit_euro_size_sign_clash_net_bit"] == (
        "€ size clash net win · +€80"
    )
    assert mid_keep["window_a_closes_exit_euro_size_sign_clash_keep_bit"] == ""
    assert mid_keep["window_a_closes_exit_euro_size_sign_clash_keep"] is None
    assert "€ size clash net win · +€80" in mid_keep["line"]
    assert "€ size clash keep" not in mid_keep["line"]

    assert win["window_a_closes_exit_euro_size_sign_clash"] == "clash"
    assert win["window_a_closes_exit_euro_size_sign_clash_net"] == "win"
    assert win["window_a_closes_exit_euro_size_sign_clash_net_pnl"] == 190.0
    assert win["window_a_closes_exit_euro_size_sign_clash_net_loss"] is False
    assert win["window_a_closes_exit_euro_size_sign_clash_net_bit"] == (
        "€ size clash net win · +€190"
    )
    assert win["window_a_closes_exit_euro_size_sign_clash_keep"] == "strong"
    assert win["window_a_closes_exit_euro_size_sign_clash_keep_ratio"] == 0.9
    assert win["window_a_closes_exit_euro_size_sign_clash_keep_thin"] is False
    assert win["window_a_closes_exit_euro_size_sign_clash_keep_bit"] == (
        "€ size clash keep strong · 0.9×"
    )
    assert "€ size clash · lead win" not in win["line"]  # clash stays in fields
    assert "€ size clash net win · +€190" not in win["line"]  # net stays in fields
    assert "€ size clash keep strong · 0.9×" in win["line"]

    assert loss["window_a_closes_exit_euro_size_sign_clash_net"] == "loss"
    assert loss["window_a_closes_exit_euro_size_sign_clash_net_pnl"] == -190.0
    assert loss["window_a_closes_exit_euro_size_sign_clash_net_loss"] is True
    assert loss["window_a_closes_exit_euro_size_sign_clash_net_bit"] == (
        "€ size clash net loss · −€190"
    )
    assert loss["window_a_closes_exit_euro_size_sign_clash_keep"] == "strong"
    assert loss["window_a_closes_exit_euro_size_sign_clash_keep_bit"] == (
        "€ size clash keep strong · 0.9×"
    )
    assert loss["tone"] == "warn"
    assert "€ size clash · lead loss" not in loss["line"]
    assert "€ size clash net loss · −€190" not in loss["line"]
    assert "€ size clash keep strong · 0.9×" in loss["line"]
    assert len(mid_keep["line"]) <= 96
    assert len(win["line"]) <= 96
    assert len(loss["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep() -> None:
    """Clash net alone must not hide how much two-sided money survives."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    # Full cancel — net silent, keep thin · 0× owns the clip and warns.
    cancel = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 0.0,
            "net_after_all_fees": -4.0,
            "wins": 6,
            "losses": 2,
            "avg_win": 16.67,
            "avg_loss": 50.0,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 2,
            "win_streak_max": 3,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 1,
            "exit_rot": 1,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -60.0,
            "exit_pnl_rot": -40.0,
            "exit_pnl_trim": 0.0,
        },
    )
    # Strong leftover — keep owns the clip (fees 0 so keep-fees silent;
    # net stays in fields).
    strong = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 0.0,
            "realized_pnl": 190.0,
            "net_after_all_fees": 190.0,
            "wins": 6,
            "losses": 2,
            "avg_win": 33.33,
            "avg_loss": 5.0,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 2,
            "win_streak_max": 3,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 200.0,
            "exit_pnl_sl": -10.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    # Mid keep silent — net still owns the clip.
    mid = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "realized_pnl": 80.0,
            "net_after_all_fees": 76.0,
            "wins": 4,
            "losses": 4,
            "avg_win": 35.0,
            "avg_loss": 15.0,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 1,
            "win_streak_max": 1,
            "flat_closes": 0,
            "exit_tp": 4,
            "exit_sl": 4,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 140.0,
            "exit_pnl_sl": -60.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    assert cancel["window_a_closes_exit_euro_size_sign_clash"] == "clash"
    assert cancel["window_a_closes_exit_euro_size_sign_clash_net_bit"] == ""
    assert cancel["window_a_closes_exit_euro_size_sign_clash_keep"] == "thin"
    assert cancel["window_a_closes_exit_euro_size_sign_clash_keep_ratio"] == 0.0
    assert cancel["window_a_closes_exit_euro_size_sign_clash_keep_thin"] is True
    assert cancel["window_a_closes_exit_euro_size_sign_clash_keep_bit"] == (
        "€ size clash keep thin · 0×"
    )
    assert cancel["tone"] == "warn"
    assert "€ size clash · lead win" not in cancel["line"]
    assert "€ size clash keep thin · 0×" in cancel["line"]

    assert strong["window_a_closes_exit_euro_size_sign_clash_keep"] == "strong"
    assert strong["window_a_closes_exit_euro_size_sign_clash_keep_ratio"] == 0.9
    assert strong["window_a_closes_exit_euro_size_sign_clash_keep_thin"] is False
    assert strong["window_a_closes_exit_euro_size_sign_clash_keep_bit"] == (
        "€ size clash keep strong · 0.9×"
    )
    assert strong["window_a_closes_exit_euro_size_sign_clash_net_bit"] == (
        "€ size clash net win · +€190"
    )
    assert "€ size clash net win · +€190" not in strong["line"]
    assert "€ size clash keep strong · 0.9×" in strong["line"]

    assert mid["window_a_closes_exit_euro_size_sign_clash_keep_bit"] == ""
    assert mid["window_a_closes_exit_euro_size_sign_clash_keep"] is None
    assert mid["window_a_closes_exit_euro_size_sign_clash_net"] == "win"
    assert "€ size clash net win · +€80" in mid["line"]
    assert "€ size clash keep" not in mid["line"]
    assert len(cancel["line"]) <= 96
    assert len(strong["line"]) <= 96
    assert len(mid["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees() -> None:
    """Clash keep alone must not hide whether fees eat the strong leftover."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }

    def _ws(fees: float) -> dict:
        return {
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": fees,
            "wins": 6,
            "losses": 2,
            "avg_win": 16.67,
            "avg_loss": 2.5,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 2,
            "win_streak_max": 3,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        }

    # Comfortable leftover vs fee-drag total — vs owns the clip (keep fees
    # stays in fields). Thin/eat match hot window mood → vs silent.
    calm = build_calm_streak_glance(runtime, as_of=as_of, window_stats=_ws(4.0))
    # Thin fees÷leftover ≥0.5 — warns and owns the clip (vs silent).
    thin = build_calm_streak_glance(runtime, as_of=as_of, window_stats=_ws(50.0))
    # Fees exceed leftover — eat warns and owns the clip (vs silent).
    eat = build_calm_streak_glance(runtime, as_of=as_of, window_stats=_ws(200.0))
    # Zero fees stay silent — keep can still own the clip.
    zero_stats = _ws(0.0)
    zero_stats["realized_pnl"] = 95.0
    zero_stats["net_after_all_fees"] = 95.0
    zero = build_calm_streak_glance(
        runtime, as_of=as_of, window_stats=zero_stats
    )

    assert calm["window_a_closes_exit_euro_size_sign_clash_keep"] == "strong"
    assert calm["window_a_closes_exit_euro_size_sign_clash_keep_fees"] == (
        "comfortable"
    )
    assert calm["window_a_closes_exit_euro_size_sign_clash_keep_fees_ratio"] == 0.04
    assert calm["window_a_closes_exit_euro_size_sign_clash_keep_fees_warn"] is False
    assert calm["window_a_closes_exit_euro_size_sign_clash_keep_fees_bit"] == (
        "keep fees calm · 0.04×"
    )
    assert calm["window_a_closes_exit_euro_size_sign_clash_keep_bit"] == (
        "€ size clash keep strong · 0.9×"
    )
    assert calm["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs"] == (
        "worse"
    )
    assert calm["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_window"] == (
        "total"
    )
    assert calm["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_warn"] is True
    assert calm["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == (
        "keep fees vs drag worse · calm · total"
    )
    assert "€ size clash keep strong · 0.9×" not in calm["line"]
    assert "keep fees calm · 0.04×" not in calm["line"]
    assert "keep fees vs drag worse · calm · total" in calm["line"]
    assert calm["tone"] == "warn"

    assert thin["window_a_closes_exit_euro_size_sign_clash_keep_fees"] == "thin"
    assert thin["window_a_closes_exit_euro_size_sign_clash_keep_fees_ratio"] == 0.53
    assert thin["window_a_closes_exit_euro_size_sign_clash_keep_fees_warn"] is True
    assert thin["window_a_closes_exit_euro_size_sign_clash_keep_fees_bit"] == (
        "keep fees thin · 0.53×"
    )
    assert thin["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == ""
    assert thin["tone"] == "warn"
    assert "€ size clash keep strong" not in thin["line"]
    assert "keep fees thin · 0.53×" in thin["line"]

    assert eat["window_a_closes_exit_euro_size_sign_clash_keep_fees"] == "eat"
    assert eat["window_a_closes_exit_euro_size_sign_clash_keep_fees_ratio"] == 2.11
    assert eat["window_a_closes_exit_euro_size_sign_clash_keep_fees_warn"] is True
    assert eat["window_a_closes_exit_euro_size_sign_clash_keep_fees_bit"] == (
        "keep fees eat · 2.1×"
    )
    assert eat["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == ""
    assert eat["tone"] == "warn"
    assert "€ size clash keep strong" not in eat["line"]
    assert "keep fees eat · 2.1×" in eat["line"]

    assert zero["window_a_closes_exit_euro_size_sign_clash_keep_fees_bit"] == ""
    assert zero["window_a_closes_exit_euro_size_sign_clash_keep_fees"] is None
    assert zero["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == ""
    assert zero["window_a_closes_exit_euro_size_sign_clash_keep"] == "strong"
    assert "€ size clash keep strong · 0.9×" in zero["line"]
    assert "keep fees" not in zero["line"]
    assert len(calm["line"]) <= 96
    assert len(thin["line"]) <= 96
    assert len(eat["line"]) <= 96
    assert len(zero["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs() -> None:
    """Keep fees alone must not hide leftover mood vs window fee mood."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }

    # Calm leftover · fee-drag total → worse owns the clip.
    worse = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 4.0,
            "wins": 6,
            "losses": 2,
            "avg_win": 16.67,
            "avg_loss": 2.5,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 2,
            "win_streak_max": 3,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    # Hot leftover · calm book → better owns the clip (does not warn).
    better = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 200.0,
            "realized_pnl": 1000.0,
            "wins": 6,
            "losses": 2,
            "avg_win": 16.67,
            "avg_loss": 2.5,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 2,
            "win_streak_max": 3,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )
    # Same hot mood (eat + fee-drag total) stays silent — keep fees owns clip.
    same = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={
            "trades": 12,
            "buys": 4,
            "sells": 8,
            "fees": 200.0,
            "wins": 6,
            "losses": 2,
            "avg_win": 16.67,
            "avg_loss": 2.5,
            "loss_streak": 0,
            "loss_streak_max": 1,
            "win_streak": 2,
            "win_streak_max": 3,
            "flat_closes": 0,
            "exit_tp": 6,
            "exit_sl": 2,
            "exit_rot": 0,
            "exit_trim": 0,
            "exit_pnl_tp": 100.0,
            "exit_pnl_sl": -5.0,
            "exit_pnl_rot": 0.0,
            "exit_pnl_trim": 0.0,
        },
    )

    assert worse["window_a_closes_exit_euro_size_sign_clash_keep_fees"] == (
        "comfortable"
    )
    assert worse["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs"] == (
        "worse"
    )
    assert worse["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_window"] == (
        "total"
    )
    assert worse["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_warn"] is True
    assert worse["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == (
        "keep fees vs drag worse · calm · total"
    )
    assert worse["tone"] == "warn"
    assert "keep fees calm · 0.04×" not in worse["line"]
    assert "keep fees vs drag worse · calm · total" in worse["line"]

    assert better["window_a_closes_exit_euro_size_sign_clash_keep_fees"] == "eat"
    assert better["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs"] == (
        "better"
    )
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_window"
    ] == "comfortable"
    assert better["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_warn"] is False
    assert better["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == (
        "keep fees vs drag better · eat · calm"
    )
    # Gap + dir + sides own the clip when leftover× and window× both
    # exist (fee-drag total fail-open stays on vs). Mood labels ≠ how
    # far multiples sit; unsigned gap ≠ which side is hotter; directed
    # ratio ≠ both audit multiples.
    assert better["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap"] == (
        "wide"
    )
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn"
    ] is False
    assert better["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit"] == (
        "keep fees vs drag gap wide · 10.5×"
    )
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir"
    ] == "above"
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn"
    ] is False
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit"
    ] == "keep fees vs drag gap dir above · 10.5×"
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover"
    ] == 2.11
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window"
    ] == 0.2
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn"
    ] is False
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"
    ] == "gap dir sides · leftover 2.1× · window 0.20×"
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta"
    ] == "wide"
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio"
    ] == 1.91
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
    ] == "gap dir sides Δ wide · +1.9×"
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover"
    ] == 91.3
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window"
    ] == 8.7
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn"
    ] is False
    assert better[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == "sides share · leftover 91.3% · window 8.7%"
    assert "keep fees eat" not in better["line"]
    assert "keep fees vs drag better · eat · calm" not in better["line"]
    assert "keep fees vs drag gap wide · 10.5×" not in better["line"]
    assert "keep fees vs drag gap dir above · 10.5×" not in better["line"]
    assert "gap dir sides · leftover 2.1× · window 0.20×" not in better["line"]
    assert "gap dir sides Δ wide · +1.9×" not in better["line"]
    assert "sides share · leftover 91.3% · window 8.7%" not in better["line"]
    assert "sides share vs Δ align · wide" not in better["line"]
    assert "align size · +1.9× · +82.6pp" in better["line"]
    assert "sides share Δ wide · +82.6pp" not in better["line"]
    # eat alone would warn; better vs/gap/dir/sides/Δ/share/shareΔ do not
    # escalate from vs/gap/dir/sides/Δ/share/shareΔ_warn. keep_fees_warn is
    # still True in fields — tone stays warn from eat.
    assert better["window_a_closes_exit_euro_size_sign_clash_keep_fees_warn"] is True
    assert better["tone"] == "warn"

    assert same["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit"] == ""
    assert same["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs"] is None
    assert same["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit"] == ""
    assert same[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit"
    ] == ""
    assert same[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"
    ] == ""
    assert same[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
    ] == ""
    assert same[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == ""
    assert same["window_a_closes_exit_euro_size_sign_clash_keep_fees"] == "eat"
    assert "keep fees eat · 2.1×" in same["line"]
    assert "keep fees vs drag" not in same["line"]
    assert len(worse["line"]) <= 96
    assert len(better["line"]) <= 96
    assert len(same["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap() -> None:
    """Vs mood alone must not hide how far leftover fees× and window fees× sit."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Calm leftover · fees-ok thin → worse + wide gap + dir below + sides
    # own clip.
    worse_gap = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 20.0, "realized_pnl": 30.0},
    )
    # Hot leftover · calm book → better + wide gap + dir above + sides
    # own clip (gap/dir/sides do not warn; eat still warns in fields).
    better_gap = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 200.0, "realized_pnl": 1000.0},
    )
    # Fee-drag total has no window fees× — gap/dir/sides fail-open; vs owns clip.
    total_no_gap = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 4.0},
    )

    assert worse_gap["window_a_closes_exit_euro_size_sign_clash_keep_fees"] == (
        "comfortable"
    )
    assert worse_gap["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs"] == (
        "worse"
    )
    assert worse_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_window"
    ] == "thin"
    assert worse_gap["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap"] == (
        "wide"
    )
    assert worse_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn"
    ] is True
    assert worse_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir"
    ] == "below"
    assert worse_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn"
    ] is True
    assert worse_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"
    ] == "gap dir sides · leftover 0.21× · window 0.67×"
    assert "keep fees vs drag worse" not in worse_gap["line"]
    assert "keep fees vs drag gap wide" not in worse_gap["line"]
    assert "keep fees vs drag gap dir below · 0.31×" not in worse_gap["line"]
    # mid additive Δ (|−0.46×|) · wide share Δ → share vs Δ clash owns the clip.
    assert worse_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
    ] == ""
    assert worse_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == "sides share · leftover 23.9% · window 76.1%"
    assert "gap dir sides · leftover 0.21× · window 0.67×" not in worse_gap["line"]
    assert "sides share · leftover 23.9% · window 76.1%" not in worse_gap["line"]
    assert "sides share Δ wide · −52.2pp" not in worse_gap["line"]
    assert "sides share vs Δ clash · × mid · % wide" in worse_gap["line"]
    assert worse_gap["tone"] == "warn"

    assert better_gap["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs"] == (
        "better"
    )
    assert better_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap"
    ] == "wide"
    assert better_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_warn"
    ] is False
    assert better_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir"
    ] == "above"
    assert better_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn"
    ] is False
    assert better_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta"
    ] == "wide"
    assert better_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
    ] == "gap dir sides Δ wide · +1.9×"
    assert better_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == "sides share · leftover 91.3% · window 8.7%"
    assert "keep fees vs drag better" not in better_gap["line"]
    assert "keep fees vs drag gap wide · 10.5×" not in better_gap["line"]
    assert "keep fees vs drag gap dir above · 10.5×" not in better_gap["line"]
    assert "gap dir sides · leftover 2.1× · window 0.20×" not in better_gap["line"]
    assert "gap dir sides Δ wide · +1.9×" not in better_gap["line"]
    assert "sides share · leftover 91.3% · window 8.7%" not in better_gap["line"]
    assert "sides share vs Δ align · wide" not in better_gap["line"]
    assert "align size · +1.9× · +82.6pp" in better_gap["line"]
    assert "sides share Δ wide · +82.6pp" not in better_gap["line"]
    assert better_gap["tone"] == "warn"

    assert total_no_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_bit"
    ] == ""
    assert total_no_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap"
    ] is None
    assert total_no_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit"
    ] == ""
    assert total_no_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"
    ] == ""
    assert total_no_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
    ] == ""
    assert total_no_gap[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_bit"
    ] == "keep fees vs drag worse · calm · total"
    assert "keep fees vs drag worse · calm · total" in total_no_gap["line"]
    assert "keep fees vs drag gap" not in total_no_gap["line"]
    assert len(worse_gap["line"]) <= 96
    assert len(better_gap["line"]) <= 96
    assert len(total_no_gap["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir() -> None:
    """Unsigned gap alone must not hide which fee× side sits higher."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Calm leftover · fees-ok thin → dir below + sides (book hotter).
    below = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 20.0, "realized_pnl": 30.0},
    )
    # Hot leftover · calm book → dir above + sides (leftover hotter).
    above = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 200.0, "realized_pnl": 1000.0},
    )
    # Fee-drag total — no window fees× → gap/dir/sides fail-open.
    total_no_dir = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 4.0},
    )

    assert below["window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap"] == (
        "wide"
    )
    assert below[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir"
    ] == "below"
    assert below[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio"
    ] == 0.31
    assert below[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn"
    ] is True
    assert below[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit"
    ] == "keep fees vs drag gap dir below · 0.31×"
    # × mid · % wide → share vs Δ clash owns the clip; prior bits stay in fields.
    assert "keep fees vs drag gap wide" not in below["line"]
    assert "keep fees vs drag gap dir below · 0.31×" not in below["line"]
    assert "gap dir sides · leftover 0.21× · window 0.67×" not in below["line"]
    assert "sides share · leftover 23.9% · window 76.1%" not in below["line"]
    assert "sides share Δ wide · −52.2pp" not in below["line"]
    assert "sides share vs Δ clash · × mid · % wide" in below["line"]
    assert below["tone"] == "warn"

    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir"
    ] == "above"
    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_ratio"
    ] == 10.55
    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_warn"
    ] is False
    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit"
    ] == "keep fees vs drag gap dir above · 10.5×"
    assert "keep fees vs drag gap wide · 10.5×" not in above["line"]
    assert "keep fees vs drag gap dir above · 10.5×" not in above["line"]
    # share Δ owns the clip when share already spoke (share stays in fields).
    assert "gap dir sides · leftover 2.1× · window 0.20×" not in above["line"]
    assert "gap dir sides Δ wide · +1.9×" not in above["line"]
    assert "sides share · leftover 91.3% · window 8.7%" not in above["line"]
    assert "sides share vs Δ align · wide" not in above["line"]
    assert "align size · +1.9× · +82.6pp" in above["line"]
    assert "sides share Δ wide · +82.6pp" not in above["line"]
    assert above["tone"] == "warn"

    assert total_no_dir[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_bit"
    ] == ""
    assert total_no_dir[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir"
    ] is None
    assert total_no_dir[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"
    ] == ""
    assert total_no_dir[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
    ] == ""
    assert "keep fees vs drag worse · calm · total" in total_no_dir["line"]
    assert "keep fees vs drag gap dir" not in total_no_dir["line"]
    assert len(below["line"]) <= 96
    assert len(above["line"]) <= 96
    assert len(total_no_dir["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides() -> None:
    """Directed ratio alone must not hide leftover fees× and window fees×."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Calm leftover · fees-ok thin → sides audit both multiples.
    below = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 20.0, "realized_pnl": 30.0},
    )
    # Hot leftover · calm book → sides audit both multiples.
    above = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 200.0, "realized_pnl": 1000.0},
    )
    # Fee-drag total — no window fees× → gap/dir/sides fail-open.
    total_no_sides = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 4.0},
    )

    assert below[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir"
    ] == "below"
    assert below[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover"
    ] == 0.21
    assert below[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window"
    ] == 0.67
    assert below[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn"
    ] is True
    assert below[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"
    ] == "gap dir sides · leftover 0.21× · window 0.67×"
    assert below[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == "sides share · leftover 23.9% · window 76.1%"
    assert "keep fees vs drag gap dir below · 0.31×" not in below["line"]
    assert "gap dir sides · leftover 0.21× · window 0.67×" not in below["line"]
    assert "sides share · leftover 23.9% · window 76.1%" not in below["line"]
    assert "sides share Δ wide · −52.2pp" not in below["line"]
    assert "sides share vs Δ clash · × mid · % wide" in below["line"]
    assert below["tone"] == "warn"

    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir"
    ] == "above"
    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover"
    ] == 2.11
    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window"
    ] == 0.2
    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_warn"
    ] is False
    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"
    ] == "gap dir sides · leftover 2.1× · window 0.20×"
    # share Δ owns the clip when share already spoke (share stays in fields).
    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta"
    ] == "wide"
    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio"
    ] == 1.91
    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
    ] == "gap dir sides Δ wide · +1.9×"
    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover"
    ] == 91.3
    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window"
    ] == 8.7
    assert above[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == "sides share · leftover 91.3% · window 8.7%"
    assert "keep fees vs drag gap dir above · 10.5×" not in above["line"]
    assert "gap dir sides · leftover 2.1× · window 0.20×" not in above["line"]
    assert "gap dir sides Δ wide · +1.9×" not in above["line"]
    assert "sides share · leftover 91.3% · window 8.7%" not in above["line"]
    assert "sides share vs Δ align · wide" not in above["line"]
    assert "align size · +1.9× · +82.6pp" in above["line"]
    assert "sides share Δ wide · +82.6pp" not in above["line"]
    assert above["tone"] == "warn"

    assert total_no_sides[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_bit"
    ] == ""
    assert total_no_sides[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_leftover"
    ] is None
    assert total_no_sides[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_window"
    ] is None
    assert total_no_sides[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
    ] == ""
    assert total_no_sides[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == ""
    assert "keep fees vs drag worse · calm · total" in total_no_sides["line"]
    assert "gap dir sides" not in total_no_sides["line"]
    assert len(below["line"]) <= 96
    assert len(above["line"]) <= 96
    assert len(total_no_sides["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta() -> None:
    """Both multiples alone must not hide leftover−window additive Δ."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Hot leftover · calm book → wide +1.91× additive Δ.
    wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 200.0, "realized_pnl": 1000.0},
    )
    # Barely-across worse → thin −0.05× additive Δ.
    thin = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 42.75, "realized_pnl": 85.5},
    )
    # Mid |Δ| (0.46×) silent — sides keep the clip.
    mid = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 20.0, "realized_pnl": 30.0},
    )
    # Fee-drag total — no window fees× → gap/dir/sides/Δ fail-open.
    total_no_delta = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 4.0},
    )

    assert wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta"
    ] == "wide"
    assert wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio"
    ] == 1.91
    assert wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn"
    ] is False
    assert wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
    ] == "gap dir sides Δ wide · +1.9×"
    assert "gap dir sides · leftover 2.1× · window 0.20×" not in wide["line"]
    # align owns the clip after matching ×/share Δ (share / Δ stay in fields).
    assert "gap dir sides Δ wide · +1.9×" not in wide["line"]
    assert "sides share · leftover 91.3% · window 8.7%" not in wide["line"]
    assert "sides share vs Δ align · wide" not in wide["line"]
    assert "align size · +1.9× · +82.6pp" in wide["line"]
    assert "sides share Δ wide · +82.6pp" not in wide["line"]
    assert wide["tone"] == "warn"

    assert thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta"
    ] == "thin"
    assert thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_ratio"
    ] == -0.05
    assert thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_warn"
    ] is True
    assert thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
    ] == "gap dir sides Δ thin · −0.05×"
    assert "gap dir sides · leftover" not in thin["line"]
    assert "gap dir sides Δ thin · −0.05×" not in thin["line"]
    assert "sides share · leftover 47.4% · window 52.6%" not in thin["line"]
    assert "sides share vs Δ align · thin" not in thin["line"]
    assert "align size · −0.05× · −5.2pp" not in thin["line"]
    assert "align lead · %" not in thin["line"]
    assert "align lead size · 2.6×" not in thin["line"]
    # Lead size % Δ owns the clip after share (share/Δ/sides stay in fields).
    assert "lead size sides · louder 0.26× · quieter 0.10×" not in thin["line"]
    assert "lead size sides Δ thin · +0.16×" not in thin["line"]
    assert "lead size % · louder 72.2% · quieter 27.8%" not in thin["line"]
    assert "lead size % Δ wide · +44.4pp" in thin["line"]
    assert thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ thin · +0.16×"
    assert thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 0.26× · quieter 0.10×"
    assert "sides share Δ thin · −5.2pp" not in thin["line"]
    assert thin["tone"] == "warn"

    assert mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
    ] == ""
    assert "gap dir sides · leftover 0.21× · window 0.67×" not in mid["line"]
    assert "gap dir sides Δ" not in mid["line"]
    # × mid · % wide → share vs Δ clash owns the clip (share/Δ stay in fields).
    assert "sides share · leftover 23.9% · window 76.1%" not in mid["line"]
    assert "sides share Δ wide · −52.2pp" not in mid["line"]
    assert "sides share vs Δ clash · × mid · % wide" in mid["line"]
    assert mid["tone"] == "warn"

    assert total_no_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta_bit"
    ] == ""
    assert total_no_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_delta"
    ] is None
    assert total_no_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == ""
    assert "keep fees vs drag worse · calm · total" in total_no_delta["line"]
    assert "gap dir sides Δ" not in total_no_delta["line"]
    assert "sides share" not in total_no_delta["line"]
    assert len(wide["line"]) <= 96
    assert len(thin["line"]) <= 96
    assert len(mid["line"]) <= 96
    assert len(total_no_delta["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share() -> None:
    """Both multiples / additive Δ alone must not hide leftover%/window% ownership."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Hot leftover · calm book → share after wide Δ (share Δ then owns clip).
    hot = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 200.0, "realized_pnl": 1000.0},
    )
    # Calm leftover · fees-ok thin → share after silent mid Δ.
    thin_book = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 20.0, "realized_pnl": 30.0},
    )
    # Mid share Δ (10–20pp) — share keeps the clip; Δ silent.
    mid_share_delta = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 38.5, "realized_pnl": 75.0},
    )
    # Fee-drag total — no window fees× → share fail-open.
    total_no_share = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 4.0},
    )

    assert hot[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover"
    ] == 91.3
    assert hot[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window"
    ] == 8.7
    assert hot[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn"
    ] is False
    assert hot[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == "sides share · leftover 91.3% · window 8.7%"
    assert "gap dir sides Δ wide · +1.9×" not in hot["line"]
    # share Δ owns the clip after share (share stays in fields).
    assert "sides share · leftover 91.3% · window 8.7%" not in hot["line"]
    assert "sides share vs Δ align · wide" not in hot["line"]
    assert "align size · +1.9× · +82.6pp" in hot["line"]
    assert "sides share Δ wide · +82.6pp" not in hot["line"]
    assert hot["tone"] == "warn"

    assert thin_book[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover"
    ] == 23.9
    assert thin_book[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_window"
    ] == 76.1
    assert thin_book[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_warn"
    ] is True
    assert thin_book[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == "sides share · leftover 23.9% · window 76.1%"
    assert "gap dir sides · leftover 0.21× · window 0.67×" not in thin_book["line"]
    assert "sides share · leftover 23.9% · window 76.1%" not in thin_book["line"]
    # × mid · % wide → share vs Δ clash owns the clip (share Δ stays in fields).
    assert "sides share Δ wide · −52.2pp" not in thin_book["line"]
    assert "sides share vs Δ clash · × mid · % wide" in thin_book["line"]
    assert thin_book["tone"] == "warn"

    assert mid_share_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == "sides share · leftover 44.6% · window 55.4%"
    assert mid_share_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit"
    ] == ""
    # × thin · % mid → share vs Δ clash owns the clip (share stays in fields).
    assert "sides share · leftover 44.6% · window 55.4%" not in mid_share_delta["line"]
    assert "sides share Δ" not in mid_share_delta["line"]
    assert "sides share vs Δ clash · × thin · % mid" in mid_share_delta["line"]
    assert mid_share_delta["tone"] == "warn"

    assert total_no_share[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == ""
    assert total_no_share[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_leftover"
    ] is None
    assert "keep fees vs drag worse · calm · total" in total_no_share["line"]
    assert "sides share" not in total_no_share["line"]
    assert len(hot["line"]) <= 96
    assert len(thin_book["line"]) <= 96
    assert len(mid_share_delta["line"]) <= 96
    assert len(total_no_share["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta() -> None:
    """Both % alone must not hide leftover%−window% pp spread."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Hot leftover · calm book → wide +82.6pp share Δ.
    wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 200.0, "realized_pnl": 1000.0},
    )
    # Barely-across worse → thin −5.2pp share Δ.
    thin = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 42.75, "realized_pnl": 85.5},
    )
    # Mid |pp| silent — share keeps the clip.
    mid = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 38.5, "realized_pnl": 75.0},
    )
    # Fee-drag total — no window fees× → share/Δ fail-open.
    total_no_delta = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 4.0},
    )

    assert wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta"
    ] == "wide"
    assert wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio"
    ] == 82.6
    assert wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn"
    ] is False
    assert wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit"
    ] == "sides share Δ wide · +82.6pp"
    assert "sides share · leftover 91.3% · window 8.7%" not in wide["line"]
    assert "sides share vs Δ align · wide" not in wide["line"]
    assert "align size · +1.9× · +82.6pp" in wide["line"]
    assert "sides share Δ wide · +82.6pp" not in wide["line"]
    assert wide["tone"] == "warn"

    assert thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta"
    ] == "thin"
    assert thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_ratio"
    ] == -5.2
    assert thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_warn"
    ] is True
    assert thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit"
    ] == "sides share Δ thin · −5.2pp"
    assert "sides share · leftover 47.4% · window 52.6%" not in thin["line"]
    assert "sides share vs Δ align · thin" not in thin["line"]
    assert "align size · −0.05× · −5.2pp" not in thin["line"]
    assert "align lead · %" not in thin["line"]
    assert "align lead size · 2.6×" not in thin["line"]
    # Lead size % Δ owns the clip after share (share/Δ/sides stay in fields).
    assert "lead size sides · louder 0.26× · quieter 0.10×" not in thin["line"]
    assert "lead size sides Δ thin · +0.16×" not in thin["line"]
    assert "lead size % · louder 72.2% · quieter 27.8%" not in thin["line"]
    assert "lead size % Δ wide · +44.4pp" in thin["line"]
    assert thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ thin · +0.16×"
    assert thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 0.26× · quieter 0.10×"
    assert "sides share Δ thin · −5.2pp" not in thin["line"]
    assert thin["tone"] == "warn"

    assert mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit"
    ] == ""
    assert mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta"
    ] is None
    # × thin · % mid → share vs Δ clash owns the clip.
    assert "sides share · leftover 44.6% · window 55.4%" not in mid["line"]
    assert "sides share Δ" not in mid["line"]
    assert "sides share vs Δ clash · × thin · % mid" in mid["line"]
    assert mid["tone"] == "warn"

    assert total_no_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta_bit"
    ] == ""
    assert total_no_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_delta"
    ] is None
    assert total_no_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_bit"
    ] == ""
    assert "keep fees vs drag worse · calm · total" in total_no_delta["line"]
    assert "sides share" not in total_no_delta["line"]
    assert len(wide["line"]) <= 96
    assert len(thin["line"]) <= 96
    assert len(mid["line"]) <= 96
    assert len(total_no_delta["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta() -> None:
    """Additive × Δ lean alone must not hide mid-vs-spoke ownership clash."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Both wide — same lean speaks align; clash stays off.
    both_wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 200.0, "realized_pnl": 1000.0},
    )
    # × thin · % mid → clash owns the clip.
    x_thin_s_mid = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 38.5, "realized_pnl": 75.0},
    )
    # × mid · % wide → clash owns the clip.
    x_mid_s_wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 20.0, "realized_pnl": 30.0},
    )
    # Both thin — same lean speaks align; worse warns.
    both_thin = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 42.75, "realized_pnl": 85.5},
    )

    # Both wide — same lean speaks align; size owns the clip (lead near-equal silent).
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit"
    ] == ""
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta"
    ] is None
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align"
    ] == "align"
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn"
    ] is False
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit"
    ] == "sides share vs Δ align · wide"
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size"
    ] == "size"
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit"
    ] == "align size · +1.9× · +82.6pp"
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit"
    ] == ""
    assert "sides share Δ wide · +82.6pp" not in both_wide["line"]
    assert "sides share vs Δ align · wide" not in both_wide["line"]
    assert "align size · +1.9× · +82.6pp" in both_wide["line"]
    assert "align lead" not in both_wide["line"]
    assert "sides share vs Δ clash" not in both_wide["line"]
    assert both_wide["tone"] == "warn"

    assert x_thin_s_mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta"
    ] == "clash"
    assert x_thin_s_mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn"
    ] is True
    assert x_thin_s_mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit"
    ] == "sides share vs Δ clash · × thin · % mid"
    assert x_thin_s_mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit"
    ] == ""
    assert x_thin_s_mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit"
    ] == ""
    assert x_thin_s_mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit"
    ] == ""
    assert "sides share · leftover 44.6% · window 55.4%" not in x_thin_s_mid["line"]
    assert "sides share Δ" not in x_thin_s_mid["line"]
    assert "sides share vs Δ clash · × thin · % mid" in x_thin_s_mid["line"]
    assert "sides share vs Δ align" not in x_thin_s_mid["line"]
    assert "align size" not in x_thin_s_mid["line"]
    assert "align lead" not in x_thin_s_mid["line"]
    assert x_thin_s_mid["tone"] == "warn"

    assert x_mid_s_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta"
    ] == "clash"
    assert x_mid_s_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_warn"
    ] is True
    assert x_mid_s_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit"
    ] == "sides share vs Δ clash · × mid · % wide"
    assert x_mid_s_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit"
    ] == ""
    assert x_mid_s_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit"
    ] == ""
    assert x_mid_s_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit"
    ] == ""
    assert "sides share Δ wide · −52.2pp" not in x_mid_s_wide["line"]
    assert "sides share vs Δ clash · × mid · % wide" in x_mid_s_wide["line"]
    assert "sides share vs Δ align" not in x_mid_s_wide["line"]
    assert "align size" not in x_mid_s_wide["line"]
    assert "align lead" not in x_mid_s_wide["line"]
    assert x_mid_s_wide["tone"] == "warn"

    # Both thin — same lean speaks align; lead owns the clip (% louder); worse warns.
    assert both_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_bit"
    ] == ""
    assert both_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align"
    ] == "align"
    assert both_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn"
    ] is True
    assert both_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit"
    ] == "sides share vs Δ align · thin"
    assert both_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size"
    ] == "size"
    assert both_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit"
    ] == "align size · −0.05× · −5.2pp"
    assert both_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead"
    ] == "%"
    assert both_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit"
    ] == "align lead · %"
    assert both_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size"
    ] == "size"
    assert both_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit"
    ] == "align lead size · 2.6×"
    assert "sides share Δ thin · −5.2pp" not in both_thin["line"]
    assert "sides share vs Δ align · thin" not in both_thin["line"]
    assert "align size · −0.05× · −5.2pp" not in both_thin["line"]
    assert "align lead · %" not in both_thin["line"]
    assert "align lead size · 2.6×" not in both_thin["line"]
    # Lead size % Δ owns the clip after share (share/Δ/sides stay in fields).
    assert "lead size sides · louder 0.26× · quieter 0.10×" not in both_thin["line"]
    assert "lead size sides Δ thin · +0.16×" not in both_thin["line"]
    assert "lead size % · louder 72.2% · quieter 27.8%" not in both_thin["line"]
    assert "lead size % Δ wide · +44.4pp" in both_thin["line"]
    assert both_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ thin · +0.16×"
    assert both_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 0.26× · quieter 0.10×"
    assert "sides share vs Δ clash" not in both_thin["line"]
    assert both_thin["tone"] == "warn"

    assert len(both_wide["line"]) <= 96
    assert len(x_thin_s_mid["line"]) <= 96
    assert len(x_mid_s_wide["line"]) <= 96
    assert len(both_thin["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align() -> None:
    """Matching × Δ and share Δ lean must speak align; size owns the clip when present."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    align_wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 200.0, "realized_pnl": 1000.0},
    )
    align_thin = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 39.0, "realized_pnl": 77.75},
    )
    clash_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 38.5, "realized_pnl": 75.0},
    )

    assert align_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align"
    ] == "align"
    assert align_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit"
    ] == "sides share vs Δ align · wide"
    assert align_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn"
    ] is False
    # Size owns the clip (lead near-equal silent); align stays in fields.
    assert "sides share vs Δ align · wide" not in align_wide["line"]
    assert "align size · +1.9× · +82.6pp" in align_wide["line"]
    assert "align lead" not in align_wide["line"]
    assert "sides share Δ" not in align_wide["line"]

    assert align_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align"
    ] == "align"
    assert align_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit"
    ] == "sides share vs Δ align · thin"
    assert align_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_warn"
    ] is True
    # Nested share-vs-Δ clash owns the clip (mid × / wide %); share Δ stays in fields.
    assert "sides share vs Δ align · thin" not in align_thin["line"]
    assert "align size · −0.09× · −9.8pp" not in align_thin["line"]
    assert "align lead · %" not in align_thin["line"]
    assert "align lead size · 2.7×" not in align_thin["line"]
    assert "lead size % · louder 73.1% · quieter 26.9%" not in align_thin["line"]
    assert "lead size % vs Δ clash · × mid · % wide" in align_thin["line"]
    assert "lead size sides · louder 0.49× · quieter 0.18×" not in align_thin["line"]
    assert "sides share Δ" not in align_thin["line"]
    assert align_thin["tone"] == "warn"

    assert clash_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta"
    ] == "clash"
    assert clash_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_bit"
    ] == ""
    assert "sides share vs Δ align" not in clash_only["line"]
    assert "align size" not in clash_only["line"]
    assert "align lead" not in clash_only["line"]

    assert len(align_wide["line"]) <= 96
    assert len(align_thin["line"]) <= 96
    assert len(clash_only["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size() -> None:
    """Align size puts both signed spreads on the calm line after align."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    size_wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 200.0, "realized_pnl": 1000.0},
    )
    size_thin = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 39.0, "realized_pnl": 77.75},
    )
    clash_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 38.5, "realized_pnl": 75.0},
    )

    assert size_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size"
    ] == "size"
    assert size_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit"
    ] == "align size · +1.9× · +82.6pp"
    assert size_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_warn"
    ] is False
    assert size_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit"
    ] == ""
    assert "align size · +1.9× · +82.6pp" in size_wide["line"]
    assert "sides share vs Δ align · wide" not in size_wide["line"]
    assert "align lead" not in size_wide["line"]
    assert size_wide["tone"] == "warn"

    assert size_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size"
    ] == "size"
    assert size_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit"
    ] == "align size · −0.09× · −9.8pp"
    assert size_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_warn"
    ] is True
    # Nested share-vs-Δ clash owns the clip; share Δ / lead size stay in fields.
    assert "align size · −0.09× · −9.8pp" not in size_thin["line"]
    assert "align lead · %" not in size_thin["line"]
    assert "align lead size · 2.7×" not in size_thin["line"]
    assert "lead size % · louder 73.1% · quieter 26.9%" not in size_thin["line"]
    assert "lead size % vs Δ clash · × mid · % wide" in size_thin["line"]
    assert "lead size sides · louder 0.49× · quieter 0.18×" not in size_thin["line"]
    assert "sides share vs Δ align · thin" not in size_thin["line"]
    assert size_thin["tone"] == "warn"

    assert clash_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_size_bit"
    ] == ""
    assert "align size" not in clash_only["line"]
    assert "align lead" not in clash_only["line"]

    assert len(size_wide["line"]) <= 96
    assert len(size_thin["line"]) <= 96
    assert len(clash_only["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead() -> None:
    """Align lead names the louder spread (× or %) on the calm line after size."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Near-equal loudness — size stays on the line; lead silent.
    lead_quiet = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 200.0, "realized_pnl": 1000.0},
    )
    # % ≥2× louder than × — lead size owns the clip; lead stays in fields.
    lead_pct = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 39.0, "realized_pnl": 77.75},
    )
    clash_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 38.5, "realized_pnl": 75.0},
    )

    assert lead_quiet[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit"
    ] == ""
    assert lead_quiet[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead"
    ] is None
    assert lead_quiet[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit"
    ] == ""
    assert "align size · +1.9× · +82.6pp" in lead_quiet["line"]
    assert "align lead ·" not in lead_quiet["line"]
    assert "align lead size" not in lead_quiet["line"]

    assert lead_pct[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead"
    ] == "%"
    assert lead_pct[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit"
    ] == "align lead · %"
    assert lead_pct[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_warn"
    ] is True
    assert lead_pct[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size"
    ] == "size"
    assert lead_pct[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit"
    ] == "align lead size · 2.7×"
    assert "align lead · %" not in lead_pct["line"]
    assert "align lead size · 2.7×" not in lead_pct["line"]
    assert "lead size % · louder 73.1% · quieter 26.9%" not in lead_pct["line"]
    assert "lead size % vs Δ clash · × mid · % wide" in lead_pct["line"]
    assert "lead size sides · louder 0.49× · quieter 0.18×" not in lead_pct["line"]
    assert "align size · −0.09× · −9.8pp" not in lead_pct["line"]
    assert "sides share vs Δ align · thin" not in lead_pct["line"]
    assert lead_pct["tone"] == "warn"

    assert clash_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_bit"
    ] == ""
    assert "align lead ·" not in clash_only["line"]
    assert "align lead size" not in clash_only["line"]

    assert len(lead_quiet["line"]) <= 96
    assert len(lead_pct["line"]) <= 96
    assert len(clash_only["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size() -> None:
    """Align lead size puts louder÷quieter floor-units on the calm line after lead."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Near-equal loudness — size stays; lead + lead size silent.
    size_wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 200.0, "realized_pnl": 1000.0},
    )
    # % louder — lead size owns the clip; lead stays in fields.
    lead_size_pct = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 39.0, "realized_pnl": 77.75},
    )
    clash_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 38.5, "realized_pnl": 75.0},
    )

    assert size_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit"
    ] == ""
    assert size_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size"
    ] is None
    assert "align size · +1.9× · +82.6pp" in size_wide["line"]
    assert "align lead size" not in size_wide["line"]
    assert size_wide["tone"] == "warn"

    assert lead_size_pct[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size"
    ] == "size"
    assert lead_size_pct[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit"
    ] == "align lead size · 2.7×"
    assert lead_size_pct[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_warn"
    ] is True
    # Lead size % owns the clip when sides already spoke; sides/lead size
    # stay in fields.
    assert lead_size_pct[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 0.49× · quieter 0.18×"
    assert "lead size % · louder 73.1% · quieter 26.9%" not in lead_size_pct["line"]
    assert "lead size % vs Δ clash · × mid · % wide" in lead_size_pct["line"]
    assert "lead size sides · louder 0.49× · quieter 0.18×" not in lead_size_pct["line"]
    assert "align lead size · 2.7×" not in lead_size_pct["line"]
    assert "align lead · %" not in lead_size_pct["line"]
    assert "align size · −0.09× · −9.8pp" not in lead_size_pct["line"]
    assert lead_size_pct["tone"] == "warn"

    assert clash_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit"
    ] == ""
    assert "align lead size" not in clash_only["line"]
    assert "lead size sides" not in clash_only["line"]

    assert len(size_wide["line"]) <= 96
    assert len(lead_size_pct["line"]) <= 96
    assert len(clash_only["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides() -> None:
    """Align lead size sides puts both floor-units on the calm line after lead size."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Near-equal loudness — size stays; lead size + sides silent.
    size_wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 200.0, "realized_pnl": 1000.0},
    )
    # % louder — sides own the clip; lead size stays in fields.
    sides = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 39.0, "realized_pnl": 77.75},
    )
    clash_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 38.5, "realized_pnl": 75.0},
    )

    assert size_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == ""
    assert size_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_louder"
    ] is None
    assert "lead size sides" not in size_wide["line"]
    assert "align size · +1.9× · +82.6pp" in size_wide["line"]
    assert size_wide["tone"] == "warn"

    assert sides[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_louder"
    ] == 0.49
    assert sides[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_quieter"
    ] == 0.18
    assert sides[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 0.49× · quieter 0.18×"
    assert sides[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_warn"
    ] is True
    # Mid additive Δ stays silent — lead size % Δ owns after share (share/sides
    # stay in fields).
    assert sides[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == ""
    assert "lead size % · louder 73.1% · quieter 26.9%" not in sides["line"]
    assert "lead size % vs Δ clash · × mid · % wide" in sides["line"]
    assert "lead size sides · louder 0.49× · quieter 0.18×" not in sides["line"]
    assert "lead size sides Δ" not in sides["line"]
    assert "align lead size · 2.7×" not in sides["line"]
    assert sides[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_bit"
    ] == "align lead size · 2.7×"
    assert sides["tone"] == "warn"

    assert clash_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == ""
    assert "lead size sides" not in clash_only["line"]

    assert len(size_wide["line"]) <= 96
    assert len(sides["line"]) <= 96
    assert len(clash_only["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta() -> None:
    """Align lead size sides Δ puts additive louder−quieter on the calm line after sides."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Mid Δ — Δ silent; lead size % Δ owns after share.
    sides_mid = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 39.0, "realized_pnl": 77.75},
    )
    # Wide Δ — Δ in fields; lead size % Δ owns the clip.
    delta_wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 60.0, "realized_pnl": 500.0},
    )
    # Thin Δ — Δ in fields; lead size % Δ owns the clip.
    delta_thin = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 45.0, "realized_pnl": 90.0},
    )
    clash_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 38.5, "realized_pnl": 75.0},
    )

    assert sides_mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == ""
    assert sides_mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta"
    ] is None
    assert "lead size % · louder 73.1% · quieter 26.9%" not in sides_mid["line"]
    assert "lead size % vs Δ clash · × mid · % wide" in sides_mid["line"]
    assert "lead size sides · louder 0.49× · quieter 0.18×" not in sides_mid["line"]
    assert "lead size sides Δ" not in sides_mid["line"]
    assert sides_mid["tone"] == "warn"

    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta"
    ] == "wide"
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ wide · +2.4×"
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_ratio"
    ] == 2.38
    # vs=better → Δ speaks and does not warn (other bits may still warn tone).
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_warn"
    ] is False
    # Align size owns the clip after align; share/Δ/sides/align stay in fields.
    assert "lead size % · louder 76.9% · quieter 23.1%" not in delta_wide["line"]
    assert "lead size % Δ wide · +53.8pp" not in delta_wide["line"]
    assert "lead size % vs Δ align · wide" not in delta_wide["line"]
    assert "align size · +2.4× · +53.8pp" in delta_wide["line"]
    assert "lead size sides Δ wide · +2.4×" not in delta_wide["line"]
    assert "lead size sides · louder 3.4× · quieter 1×" not in delta_wide["line"]
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 3.4× · quieter 1×"
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == "lead size % Δ wide · +53.8pp"
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
    ] == "lead size % vs Δ align · wide"
    assert delta_wide["tone"] == "warn"

    assert delta_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta"
    ] == "thin"
    assert delta_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ thin · +0.09×"
    assert delta_thin[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_warn"
    ] is True
    assert "lead size % · louder 71.4% · quieter 28.6%" not in delta_thin["line"]
    assert "lead size % Δ wide · +42.8pp" in delta_thin["line"]
    assert "lead size sides Δ thin · +0.09×" not in delta_thin["line"]
    assert "lead size sides · louder" not in delta_thin["line"]
    assert delta_thin["tone"] == "warn"

    assert clash_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == ""
    assert "lead size sides Δ" not in clash_only["line"]
    assert "lead size %" not in clash_only["line"]

    assert len(sides_mid["line"]) <= 96
    assert len(delta_wide["line"]) <= 96
    assert len(delta_thin["line"]) <= 96
    assert len(clash_only["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share() -> None:
    """Align lead size sides share puts ownership % on the calm line after Δ/sides."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Mid Δ — share owns after sides (Δ silent; sides stay in fields).
    share_mid = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 39.0, "realized_pnl": 77.75},
    )
    # Wide Δ — share owns; Δ stays in fields.
    share_after_delta = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 60.0, "realized_pnl": 500.0},
    )
    clash_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 38.5, "realized_pnl": 75.0},
    )

    assert share_mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_louder_pct"
    ] == 73.1
    assert share_mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_quieter_pct"
    ] == 26.9
    assert share_mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 73.1% · quieter 26.9%"
    assert share_mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_warn"
    ] is True
    # Share Δ owns the clip; share stays in fields.
    assert "lead size % · louder 73.1% · quieter 26.9%" not in share_mid["line"]
    assert "lead size % vs Δ clash · × mid · % wide" in share_mid["line"]
    assert "lead size sides · louder 0.49× · quieter 0.18×" not in share_mid["line"]
    assert share_mid[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 0.49× · quieter 0.18×"
    assert share_mid["tone"] == "warn"

    assert share_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_louder_pct"
    ] == 76.9
    assert share_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 76.9% · quieter 23.1%"
    # vs=better → share speaks and does not warn (other bits may still warn).
    assert share_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_warn"
    ] is False
    assert "lead size % · louder 76.9% · quieter 23.1%" not in share_after_delta["line"]
    assert "lead size % Δ wide · +53.8pp" not in share_after_delta["line"]
    assert "lead size % vs Δ align · wide" not in share_after_delta["line"]
    assert "align size · +2.4× · +53.8pp" in share_after_delta["line"]
    assert "lead size sides Δ wide · +2.4×" not in share_after_delta["line"]
    assert share_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ wide · +2.4×"
    assert share_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == "lead size % Δ wide · +53.8pp"
    assert share_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
    ] == "lead size % vs Δ align · wide"
    assert share_after_delta["tone"] == "warn"

    assert clash_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == ""
    assert "lead size %" not in clash_only["line"]

    assert len(share_mid["line"]) <= 96
    assert len(share_after_delta["line"]) <= 96
    assert len(clash_only["line"]) <= 96



def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta() -> None:
    """Align lead size sides share Δ puts louder%−quieter% pp on the calm line after share."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Mid floor-unit Δ + wide share Δ → nested share-vs-Δ clash owns the clip
    # (share Δ stays in fields). Covered in share_vs_delta test below.
    mid_then_clash = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 39.0, "realized_pnl": 77.75},
    )
    # Wide floor-unit Δ — share Δ wide + sides Δ wide → clash silent; align on line.
    wide_after_delta = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 60.0, "realized_pnl": 500.0},
    )
    clash_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 38.5, "realized_pnl": 75.0},
    )

    assert mid_then_clash[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta"
    ] == "wide"
    assert mid_then_clash[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_ratio"
    ] == 46.2
    assert mid_then_clash[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == "lead size % Δ wide · +46.2pp"
    assert mid_then_clash[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_warn"
    ] is True
    # Mid × / wide % → nested clash owns the clip; share Δ stays in fields.
    assert "lead size % Δ wide · +46.2pp" not in mid_then_clash["line"]
    assert "lead size % · louder 73.1% · quieter 26.9%" not in mid_then_clash["line"]
    assert mid_then_clash[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 73.1% · quieter 26.9%"
    assert mid_then_clash["tone"] == "warn"

    assert wide_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta"
    ] == "wide"
    assert wide_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_ratio"
    ] == 53.8
    assert wide_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == "lead size % Δ wide · +53.8pp"
    # vs=better → share Δ field does not warn; align owns the clip.
    assert wide_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_warn"
    ] is False
    assert wide_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align"
    ] == "align"
    assert wide_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
    ] == "lead size % vs Δ align · wide"
    assert wide_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size"
    ] == "size"
    assert wide_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit"
    ] == "align size · +2.4× · +53.8pp"
    assert "lead size % Δ wide · +53.8pp" not in wide_after_delta["line"]
    assert "lead size % vs Δ align · wide" not in wide_after_delta["line"]
    assert "align size · +2.4× · +53.8pp" in wide_after_delta["line"]
    assert "lead size % · louder 76.9% · quieter 23.1%" not in wide_after_delta["line"]
    assert "lead size sides Δ wide · +2.4×" not in wide_after_delta["line"]
    assert "lead size % vs Δ clash" not in wide_after_delta["line"]
    assert wide_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 76.9% · quieter 23.1%"
    assert wide_after_delta["tone"] == "warn"

    assert clash_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == ""
    assert "lead size % Δ" not in clash_only["line"]

    assert len(mid_then_clash["line"]) <= 96
    assert len(wide_after_delta["line"]) <= 96
    assert len(clash_only["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta() -> None:
    """Lead size floor-unit Δ lean alone must not hide mid-vs-spoke ownership clash."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # × mid · % wide → nested clash owns the clip.
    x_mid_s_wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 39.0, "realized_pnl": 77.75},
    )
    # Both wide — same lean → align; size owns the clip with both spreads.
    both_wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 60.0, "realized_pnl": 500.0},
    )
    # First-level sides share vs Δ clash — nested lead-size clash stays off.
    first_level_clash = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 38.5, "realized_pnl": 75.0},
    )

    assert x_mid_s_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta"
    ] == "clash"
    assert x_mid_s_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_warn"
    ] is True
    assert x_mid_s_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit"
    ] == "lead size % vs Δ clash · × mid · % wide"
    assert x_mid_s_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
    ] == ""
    assert "lead size % vs Δ clash · × mid · % wide" in x_mid_s_wide["line"]
    assert "lead size % Δ wide · +46.2pp" not in x_mid_s_wide["line"]
    assert "lead size % · louder 73.1% · quieter 26.9%" not in x_mid_s_wide["line"]
    assert "lead size % vs Δ align" not in x_mid_s_wide["line"]
    # Share Δ stays in fields when clash owns the clip.
    assert x_mid_s_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == "lead size % Δ wide · +46.2pp"
    assert x_mid_s_wide["tone"] == "warn"

    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit"
    ] == ""
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta"
    ] is None
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align"
    ] == "align"
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn"
    ] is False
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
    ] == "lead size % vs Δ align · wide"
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size"
    ] == "size"
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit"
    ] == "align size · +2.4× · +53.8pp"
    assert "lead size % vs Δ clash" not in both_wide["line"]
    assert "lead size % Δ wide · +53.8pp" not in both_wide["line"]
    assert "lead size % vs Δ align · wide" not in both_wide["line"]
    assert "align size · +2.4× · +53.8pp" in both_wide["line"]
    # Share Δ stays in fields when align/size own the clip.
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == "lead size % Δ wide · +53.8pp"
    assert both_wide["tone"] == "warn"

    assert first_level_clash[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit"
    ] == ""
    assert first_level_clash[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
    ] == ""
    assert first_level_clash[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit"
    ] == ""
    assert "lead size % vs Δ" not in first_level_clash["line"]
    assert "align size" not in first_level_clash["line"]
    assert "sides share vs Δ clash · × thin · % mid" in first_level_clash["line"]

    assert len(x_mid_s_wide["line"]) <= 96
    assert len(both_wide["line"]) <= 96
    assert len(first_level_clash["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align() -> None:
    """Matching floor-unit Δ and ownership Δ lean must speak align; size owns the clip."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Wide × / wide % · vs better → align speaks, does not set align_warn.
    align_wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 60.0, "realized_pnl": 500.0},
    )
    # Wide × / wide % · vs worse → align speaks and warns.
    align_wide_warn = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 20.0, "realized_pnl": 22.0},
    )
    # Mid × / wide % → clash owns the clip; align stays silent.
    clash_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 39.0, "realized_pnl": 77.75},
    )

    assert align_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align"
    ] == "align"
    assert align_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn"
    ] is False
    assert align_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
    ] == "lead size % vs Δ align · wide"
    assert align_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit"
    ] == ""
    assert align_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size"
    ] == "size"
    assert align_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit"
    ] == "align size · +2.4× · +53.8pp"
    # Size owns the clip; align stays in fields.
    assert "lead size % vs Δ align · wide" not in align_wide["line"]
    assert "align size · +2.4× · +53.8pp" in align_wide["line"]
    assert "lead size % Δ wide · +53.8pp" not in align_wide["line"]
    assert "lead size % vs Δ clash" not in align_wide["line"]
    assert align_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == "lead size % Δ wide · +53.8pp"
    assert align_wide["tone"] == "warn"

    assert align_wide_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align"
    ] == "align"
    assert align_wide_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn"
    ] is True
    assert align_wide_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
    ] == "lead size % vs Δ align · wide"
    assert align_wide_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size"
    ] == "size"
    assert align_wide_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit"
    ] == "align size · +1.7× · +38.2pp"
    assert align_wide_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_warn"
    ] is True
    assert "lead size % vs Δ align · wide" not in align_wide_warn["line"]
    assert "align size · +1.7× · +38.2pp" in align_wide_warn["line"]
    assert "lead size % Δ wide · +38.2pp" not in align_wide_warn["line"]
    assert align_wide_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == "lead size % Δ wide · +38.2pp"
    assert align_wide_warn["tone"] == "warn"

    assert clash_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
    ] == ""
    assert clash_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit"
    ] == ""
    assert clash_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta"
    ] == "clash"
    assert "lead size % vs Δ clash · × mid · % wide" in clash_only["line"]
    assert "lead size % vs Δ align" not in clash_only["line"]
    assert "align size" not in clash_only["line"]
    assert clash_only["tone"] == "warn"

    assert len(align_wide["line"]) <= 96
    assert len(align_wide_warn["line"]) <= 96
    assert len(clash_only["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size() -> None:
    """Nested align size puts both signed spreads on the calm line after align."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    size_wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 60.0, "realized_pnl": 500.0},
    )
    size_warn = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 20.0, "realized_pnl": 22.0},
    )
    clash_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 39.0, "realized_pnl": 77.75},
    )

    assert size_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size"
    ] == "size"
    assert size_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit"
    ] == "align size · +2.4× · +53.8pp"
    assert size_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_warn"
    ] is False
    assert size_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
    ] == "lead size % vs Δ align · wide"
    assert "align size · +2.4× · +53.8pp" in size_wide["line"]
    assert "lead size % vs Δ align · wide" not in size_wide["line"]
    assert "lead size % Δ wide · +53.8pp" not in size_wide["line"]
    assert size_wide["tone"] == "warn"

    assert size_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size"
    ] == "size"
    assert size_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit"
    ] == "align size · +1.7× · +38.2pp"
    assert size_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_warn"
    ] is True
    assert "align size · +1.7× · +38.2pp" in size_warn["line"]
    assert "lead size % vs Δ align · wide" not in size_warn["line"]
    assert size_warn["tone"] == "warn"

    assert clash_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit"
    ] == ""
    assert "align size" not in clash_only["line"]
    assert "lead size % vs Δ clash · × mid · % wide" in clash_only["line"]

    assert len(size_wide["line"]) <= 96
    assert len(size_warn["line"]) <= 96
    assert len(clash_only["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead() -> None:
    """Nested align lead names louder ×|%; nested lead size owns the calm clip."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # × ≥2× louder — nested lead + lead size + sides + Δ + share; share owns the clip.
    lead_x = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 55.0, "realized_pnl": 850.0},
    )
    # Same lead with worse leftover fee mood — warn tone.
    lead_warn = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 10.0, "realized_pnl": 10.0},
    )
    # Nested size spoke but loudness near-equal — lead silent; size stays.
    size_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 60.0, "realized_pnl": 500.0},
    )

    assert lead_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead"
    ] == "×"
    assert lead_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit"
    ] == "align lead · ×"
    assert lead_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_warn"
    ] is False
    assert lead_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size"
    ] == "size"
    assert lead_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit"
    ] == "align lead size · 2×"
    assert lead_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 6× · quieter 3×"
    # Nested share vs Δ align owns the clip (share/Δ/sides stay in fields).
    assert lead_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ wide · +3.1×"
    assert lead_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 67.1% · quieter 32.9%"
    assert "lead size % · louder 67.1% · quieter 32.9%" not in lead_x["line"]
    assert "lead size % Δ wide · +34.2pp" not in lead_x["line"]
    assert "lead size % vs Δ align · wide" in lead_x["line"]
    assert "lead size sides Δ wide · +3.1×" not in lead_x["line"]
    assert "lead size sides · louder 6× · quieter 3×" not in lead_x["line"]
    assert "align lead size · 2×" not in lead_x["line"]
    assert "align lead · ×" not in lead_x["line"]
    assert "align size · +3× · +59.2pp" not in lead_x["line"]
    assert lead_x["tone"] == "warn"

    assert lead_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead"
    ] == "×"
    assert lead_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size"
    ] == "size"
    assert lead_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit"
    ] == "align lead size · 2.3×"
    assert lead_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_warn"
    ] is True
    assert lead_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 4.5× · quieter 1.9×"
    assert lead_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ wide · +2.5×"
    assert lead_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 69.8% · quieter 30.2%"
    assert "lead size % · louder 69.8% · quieter 30.2%" not in lead_warn["line"]
    assert "lead size % Δ wide · +39.6pp" not in lead_warn["line"]
    assert "lead size % vs Δ align · wide" in lead_warn["line"]
    assert "lead size sides Δ wide · +2.5×" not in lead_warn["line"]
    assert "lead size sides · louder 4.5× · quieter 1.9×" not in lead_warn["line"]
    assert "align lead size · 2.3×" not in lead_warn["line"]
    assert "align lead · ×" not in lead_warn["line"]
    assert lead_warn["tone"] == "warn"

    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_bit"
    ] == ""
    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit"
    ] == ""
    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_size_bit"
    ] == "align size · +2.4× · +53.8pp"
    assert "align size · +2.4× · +53.8pp" in size_only["line"]
    assert "align lead ·" not in size_only["line"]
    assert "align lead size" not in size_only["line"]
    assert "lead size sides" not in size_only["line"]

    assert len(lead_x["line"]) <= 96
    assert len(lead_warn["line"]) <= 96
    assert len(size_only["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size() -> None:
    """Nested align lead size puts louder÷quieter floor-units on the calm line."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Near-equal loudness — nested size stays; lead + lead size silent.
    size_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 60.0, "realized_pnl": 500.0},
    )
    # × louder — nested lead size owns the clip; lead stays in fields.
    lead_size_x = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 55.0, "realized_pnl": 850.0},
    )
    # Worse leftover fee mood — warn.
    lead_size_warn = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 10.0, "realized_pnl": 10.0},
    )

    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit"
    ] == ""
    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size"
    ] is None
    assert "align size · +2.4× · +53.8pp" in size_only["line"]
    assert "align lead size" not in size_only["line"]
    assert "lead size sides" not in size_only["line"]

    assert lead_size_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size"
    ] == "size"
    assert lead_size_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit"
    ] == "align lead size · 2×"
    assert lead_size_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_warn"
    ] is False
    assert lead_size_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead"
    ] == "×"
    # Nested share vs Δ align owns the clip; Δ + sides + lead size stay in fields.
    assert lead_size_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 6× · quieter 3×"
    assert lead_size_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ wide · +3.1×"
    assert lead_size_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 67.1% · quieter 32.9%"
    assert "lead size % · louder 67.1% · quieter 32.9%" not in lead_size_x["line"]
    assert "lead size % Δ wide · +34.2pp" not in lead_size_x["line"]
    assert "lead size % vs Δ align · wide" in lead_size_x["line"]
    assert "lead size sides Δ wide · +3.1×" not in lead_size_x["line"]
    assert "lead size sides · louder 6× · quieter 3×" not in lead_size_x["line"]
    assert "align lead size · 2×" not in lead_size_x["line"]
    assert "align lead · ×" not in lead_size_x["line"]
    assert "align size · +3× · +59.2pp" not in lead_size_x["line"]
    assert lead_size_x["tone"] == "warn"

    assert lead_size_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit"
    ] == "align lead size · 2.3×"
    assert lead_size_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_warn"
    ] is True
    assert lead_size_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 4.5× · quieter 1.9×"
    assert lead_size_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_warn"
    ] is True
    assert lead_size_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ wide · +2.5×"
    assert lead_size_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 69.8% · quieter 30.2%"
    assert "lead size % · louder 69.8% · quieter 30.2%" not in lead_size_warn["line"]
    assert "lead size % Δ wide · +39.6pp" not in lead_size_warn["line"]
    assert "lead size % vs Δ align · wide" in lead_size_warn["line"]
    assert "lead size sides Δ wide · +2.5×" not in lead_size_warn["line"]
    assert "lead size sides · louder 4.5× · quieter 1.9×" not in lead_size_warn["line"]
    assert "align lead size · 2.3×" not in lead_size_warn["line"]
    assert lead_size_warn["tone"] == "warn"

    assert len(size_only["line"]) <= 96
    assert len(lead_size_x["line"]) <= 96
    assert len(lead_size_warn["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides() -> None:
    """Nested align lead size sides puts both floor-units on the calm line."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Near-equal loudness — nested size stays; lead size + sides silent.
    size_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 60.0, "realized_pnl": 500.0},
    )
    # × louder — nested share owns the clip; Δ/sides stay in fields.
    sides_x = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 55.0, "realized_pnl": 850.0},
    )
    # Worse leftover fee mood — warn.
    sides_warn = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 10.0, "realized_pnl": 10.0},
    )

    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == ""
    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_louder"
    ] is None
    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == ""
    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == ""
    assert "align size · +2.4× · +53.8pp" in size_only["line"]
    assert "lead size sides" not in size_only["line"]

    assert sides_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_louder"
    ] == 6.04
    assert sides_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_quieter"
    ] == 2.96
    assert sides_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 6× · quieter 3×"
    assert sides_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_warn"
    ] is False
    assert sides_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size"
    ] == "size"
    assert sides_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_bit"
    ] == "align lead size · 2×"
    # Nested share vs Δ align owns the clip (share/Δ/sides stay in fields).
    assert sides_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta"
    ] == "wide"
    assert sides_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ wide · +3.1×"
    assert sides_x[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 67.1% · quieter 32.9%"
    assert "lead size % · louder 67.1% · quieter 32.9%" not in sides_x["line"]
    assert "lead size % Δ wide · +34.2pp" not in sides_x["line"]
    assert "lead size % vs Δ align · wide" in sides_x["line"]
    assert "lead size sides Δ wide · +3.1×" not in sides_x["line"]
    assert "lead size sides · louder 6× · quieter 3×" not in sides_x["line"]
    assert "align lead size · 2×" not in sides_x["line"]
    assert sides_x["tone"] == "warn"

    assert sides_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 4.5× · quieter 1.9×"
    assert sides_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_warn"
    ] is True
    assert sides_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ wide · +2.5×"
    assert sides_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_warn"
    ] is True
    assert sides_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 69.8% · quieter 30.2%"
    assert "lead size % · louder 69.8% · quieter 30.2%" not in sides_warn["line"]
    assert "lead size % Δ wide · +39.6pp" not in sides_warn["line"]
    assert "lead size % vs Δ align · wide" in sides_warn["line"]
    assert "lead size sides Δ wide · +2.5×" not in sides_warn["line"]
    assert "lead size sides · louder 4.5× · quieter 1.9×" not in sides_warn["line"]
    assert sides_warn["tone"] == "warn"

    assert len(size_only["line"]) <= 96
    assert len(sides_x["line"]) <= 96
    assert len(sides_warn["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta() -> None:
    """Nested align lead size sides Δ puts additive louder−quieter on the calm line."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Near-equal — no nested sides → Δ silent; align size stays.
    size_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 60.0, "realized_pnl": 500.0},
    )
    # Wide Δ — share owns the clip; Δ/sides stay in fields.
    delta_wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 55.0, "realized_pnl": 850.0},
    )
    # Worse leftover fee mood — Δ/share warn.
    delta_warn = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 10.0, "realized_pnl": 10.0},
    )

    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == ""
    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta"
    ] is None
    assert "align size · +2.4× · +53.8pp" in size_only["line"]
    assert "lead size sides Δ" not in size_only["line"]

    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta"
    ] == "wide"
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ wide · +3.1×"
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_ratio"
    ] == 3.08
    # vs=better → Δ speaks and does not warn (other bits may still warn tone).
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_warn"
    ] is False
    # Nested share vs Δ align owns the clip; share / Δ / sides stay in fields.
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 67.1% · quieter 32.9%"
    assert "lead size % · louder 67.1% · quieter 32.9%" not in delta_wide["line"]
    assert "lead size % Δ wide · +34.2pp" not in delta_wide["line"]
    assert "lead size % vs Δ align · wide" in delta_wide["line"]
    assert "lead size sides Δ wide · +3.1×" not in delta_wide["line"]
    assert "lead size sides · louder 6× · quieter 3×" not in delta_wide["line"]
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 6× · quieter 3×"
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == "lead size % Δ wide · +34.2pp"
    assert delta_wide["tone"] == "warn"

    assert delta_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta"
    ] == "wide"
    assert delta_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ wide · +2.5×"
    assert delta_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_ratio"
    ] == 2.53
    assert delta_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_warn"
    ] is True
    assert delta_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 69.8% · quieter 30.2%"
    assert "lead size % · louder 69.8% · quieter 30.2%" not in delta_warn["line"]
    assert "lead size % Δ wide · +39.6pp" not in delta_warn["line"]
    assert "lead size % vs Δ align · wide" in delta_warn["line"]
    assert "lead size sides Δ wide · +2.5×" not in delta_warn["line"]
    assert "lead size sides · louder" not in delta_warn["line"]
    assert delta_warn["tone"] == "warn"

    assert len(size_only["line"]) <= 96
    assert len(delta_wide["line"]) <= 96
    assert len(delta_warn["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share() -> None:
    """Nested align lead size sides share puts ownership % on the calm line after Δ/sides."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Near-equal — no nested sides → share silent; align size stays.
    size_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 60.0, "realized_pnl": 500.0},
    )
    # Wide Δ — share owns the clip; Δ/sides stay in fields.
    share_after_delta = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 55.0, "realized_pnl": 850.0},
    )
    # Worse leftover fee mood — share warns.
    share_warn = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 10.0, "realized_pnl": 10.0},
    )

    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == ""
    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_louder_pct"
    ] is None
    assert "align size · +2.4× · +53.8pp" in size_only["line"]
    assert "lead size %" not in size_only["line"]

    assert share_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_louder_pct"
    ] == 67.1
    assert share_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_quieter_pct"
    ] == 32.9
    assert share_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 67.1% · quieter 32.9%"
    # vs=better → share speaks and does not warn (other bits may still warn).
    assert share_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_warn"
    ] is False
    # Nested share vs Δ align owns the clip; share + share Δ stay in fields.
    assert "lead size % · louder 67.1% · quieter 32.9%" not in share_after_delta["line"]
    assert "lead size % Δ wide · +34.2pp" not in share_after_delta["line"]
    assert "lead size % vs Δ align · wide" in share_after_delta["line"]
    assert "lead size sides Δ wide · +3.1×" not in share_after_delta["line"]
    assert "lead size sides · louder 6× · quieter 3×" not in share_after_delta["line"]
    assert share_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_delta_bit"
    ] == "lead size sides Δ wide · +3.1×"
    assert share_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_bit"
    ] == "lead size sides · louder 6× · quieter 3×"
    assert share_after_delta[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == "lead size % Δ wide · +34.2pp"
    assert share_after_delta["tone"] == "warn"

    assert share_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_louder_pct"
    ] == 69.8
    assert share_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 69.8% · quieter 30.2%"
    assert share_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_warn"
    ] is True
    assert "lead size % · louder 69.8% · quieter 30.2%" not in share_warn["line"]
    assert "lead size % Δ wide · +39.6pp" not in share_warn["line"]
    assert "lead size % vs Δ align · wide" in share_warn["line"]
    assert "lead size sides Δ wide · +2.5×" not in share_warn["line"]
    assert share_warn["tone"] == "warn"

    assert len(size_only["line"]) <= 96
    assert len(share_after_delta["line"]) <= 96
    assert len(share_warn["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta() -> None:
    """Nested align lead size sides share Δ puts louder%−quieter% pp on the calm line after share."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Near-equal — no nested sides → share/Δ silent; align size stays.
    size_only = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 60.0, "realized_pnl": 500.0},
    )
    # Wide Δ — share Δ owns the clip; share stays in fields.
    delta_wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 55.0, "realized_pnl": 850.0},
    )
    # Worse leftover fee mood — share Δ warns.
    delta_warn = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 10.0, "realized_pnl": 10.0},
    )

    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == ""
    assert size_only[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta"
    ] is None
    assert "lead size % Δ" not in size_only["line"]
    assert "align size · +2.4× · +53.8pp" in size_only["line"]

    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta"
    ] == "wide"
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_ratio"
    ] == 34.2
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == "lead size % Δ wide · +34.2pp"
    # vs=better → share Δ field does not warn (other bits may still warn).
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_warn"
    ] is False
    # Both wide → nested share vs Δ align owns the clip; share Δ stays in fields.
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align"
    ] == "align"
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
    ] == "lead size % vs Δ align · wide"
    assert "lead size % vs Δ align · wide" in delta_wide["line"]
    assert "lead size % Δ wide · +34.2pp" not in delta_wide["line"]
    assert "lead size % · louder 67.1% · quieter 32.9%" not in delta_wide["line"]
    assert delta_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 67.1% · quieter 32.9%"
    assert "lead size sides Δ wide · +3.1×" not in delta_wide["line"]
    assert "lead size % vs Δ clash" not in delta_wide["line"]
    assert delta_wide["tone"] == "warn"

    assert delta_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta"
    ] == "wide"
    assert delta_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_ratio"
    ] == 39.6
    assert delta_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == "lead size % Δ wide · +39.6pp"
    assert delta_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_warn"
    ] is True
    assert delta_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align"
    ] == "align"
    assert delta_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn"
    ] is True
    assert "lead size % vs Δ align · wide" in delta_warn["line"]
    assert "lead size % Δ wide · +39.6pp" not in delta_warn["line"]
    assert "lead size % · louder 69.8% · quieter 30.2%" not in delta_warn["line"]
    assert delta_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_bit"
    ] == "lead size % · louder 69.8% · quieter 30.2%"
    assert delta_warn["tone"] == "warn"

    assert len(size_only["line"]) <= 96
    assert len(delta_wide["line"]) <= 96
    assert len(delta_warn["line"]) <= 96


def test_calm_streak_glance_promote_off_paused_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta() -> None:
    """Nested floor-unit Δ lean alone must not hide mid-vs-spoke ownership clash; same lean speaks align."""
    as_of = date(2026, 8, 18)
    runtime = {
        "calm_streak_days": 0,
        "calm_required_days": 30,
        "calm_ready": False,
        "calm_detail": "promote filter off — streak paused",
    }
    base = {
        "trades": 12,
        "buys": 4,
        "sells": 8,
        "wins": 6,
        "losses": 2,
        "avg_win": 16.67,
        "avg_loss": 2.5,
        "loss_streak": 0,
        "loss_streak_max": 1,
        "win_streak": 2,
        "win_streak_max": 3,
        "flat_closes": 0,
        "exit_tp": 6,
        "exit_sl": 2,
        "exit_rot": 0,
        "exit_trim": 0,
        "exit_pnl_tp": 100.0,
        "exit_pnl_sl": -5.0,
        "exit_pnl_rot": 0.0,
        "exit_pnl_trim": 0.0,
    }

    # Both wide — same lean → nested align owns the clip; share Δ in fields.
    both_wide = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 55.0, "realized_pnl": 850.0},
    )
    # Worse leftover fee mood — align warns.
    both_wide_warn = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 10.0, "realized_pnl": 10.0},
    )
    # First-level sides share vs Δ clash — nested lead-size nest stays off.
    first_level_clash = build_calm_streak_glance(
        runtime,
        as_of=as_of,
        window_stats={**base, "fees": 38.5, "realized_pnl": 75.0},
    )

    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit"
    ] == ""
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta"
    ] is None
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align"
    ] == "align"
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn"
    ] is False
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
    ] == "lead size % vs Δ align · wide"
    assert "lead size % vs Δ align · wide" in both_wide["line"]
    assert "lead size % Δ wide · +34.2pp" not in both_wide["line"]
    assert "lead size % vs Δ clash" not in both_wide["line"]
    # Share Δ stays in fields when align owns the clip.
    assert both_wide[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_delta_bit"
    ] == "lead size % Δ wide · +34.2pp"
    assert both_wide["tone"] == "warn"

    assert both_wide_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align"
    ] == "align"
    assert both_wide_warn[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_warn"
    ] is True
    assert "lead size % vs Δ align · wide" in both_wide_warn["line"]
    assert "lead size % Δ wide · +39.6pp" not in both_wide_warn["line"]
    assert both_wide_warn["tone"] == "warn"

    assert first_level_clash[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_bit"
    ] == ""
    assert first_level_clash[
        "window_a_closes_exit_euro_size_sign_clash_keep_fees_vs_gap_dir_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_lead_size_sides_share_vs_delta_align_bit"
    ] == ""
    assert "lead size % vs Δ align" not in first_level_clash["line"]
    assert "lead size % vs Δ clash" not in first_level_clash["line"]
    assert "sides share vs Δ clash · × thin · % mid" in first_level_clash["line"]

    assert len(both_wide["line"]) <= 96
    assert len(both_wide_warn["line"]) <= 96
    assert len(first_level_clash["line"]) <= 96


def test_calm_streak_glance_progress() -> None:
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 12,
            "calm_required_days": 30,
            "calm_ready": False,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "progress"
    assert g["calm_ready"] is False
    assert g["promote_off_paused"] is False
    assert g["window_a_days"] is None
    assert g["window_a_fills"] is None
    assert "12/30" in g["line"]
    assert "building" in g["line"]


def test_calm_streak_glance_ready() -> None:
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 30,
            "calm_required_days": 30,
            "calm_ready": True,
            "calm_detail": "should not appear when ready",
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "ready"
    assert g["calm_ready"] is True
    assert g["promote_off_paused"] is False
    assert g["window_a_days"] is None
    assert g["window_a_fills"] is None
    assert "compose promote default ready" in g["line"]
    assert "should not appear" not in g["line"]


def test_calm_streak_glance_truncates_line() -> None:
    g = build_calm_streak_glance(
        {
            "calm_streak_days": 1,
            "calm_required_days": 30,
            "calm_ready": False,
            "calm_detail": "x" * 80,
        }
    )
    assert g["ready"] is True
    assert len(g["line"]) <= 96
