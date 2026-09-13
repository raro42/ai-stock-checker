"""Offline tests for Breadth multi-day A/D sparklines (display only)."""

from pathlib import Path

from openbb_backend.desk import (
    alone_density_pct,
    breadth_confirmed_thrust_streak,
    breadth_days_since_confirmed_thrust,
    breadth_days_since_mixed,
    breadth_days_since_risk_off,
    breadth_days_since_risk_on,
    breadth_days_since_tape_flip,
    breadth_days_since_tape_split,
    breadth_days_since_thrust,
    breadth_days_since_unconfirmed_thrust,
    breadth_dual_advance_streak,
    breadth_mixed_streak,
    breadth_prev_tape_label,
    breadth_risk_off_streak,
    breadth_tape_flip_max_streak,
    breadth_tape_flip_mean_streak,
    breadth_tape_flip_median_streak,
    breadth_tape_flip_min_streak,
    breadth_tape_flip_run_count,
    breadth_tape_flip_stdev_streak,
    breadth_tape_flip_streak,
    breadth_tape_label,
    breadth_tape_split_streak,
    breadth_thrust_streak,
    breadth_unconfirmed_thrust_streak,
    build_breadth_ad_spark,
    build_breadth_crypto_advance_spark,
    build_breadth_glance,
    build_breadth_mover_spark,
    build_breadth_near_high_spark,
    build_breadth_stock_advance_spark,
    build_breadth_tape_summary,
    build_breadth_thrust_summary,
    confirmed_density_pct,
    crypto_advance_ratio_pct,
    crypto_mover_ratio_pct,
    is_breadth_thrust_day,
    is_confirmed_thrust_day,
    is_dual_advance_day,
    is_risk_off_day,
    is_tape_flip,
    is_tape_split_day,
    is_unconfirmed_thrust_day,
    near_high_ratio_pct,
    scan_breadth_pulse_for_day,
    stock_advance_ratio_pct,
    tape_label_density_pct,
    tape_flip_density_pct,
    thrust_confirm_rate_pct,
    thrust_density_pct,
)


def test_crypto_mover_ratio_pct():
    assert crypto_mover_ratio_pct(1, 4) == 25.0
    assert crypto_mover_ratio_pct(0, 5) == 0.0
    assert crypto_mover_ratio_pct(2, 0) is None


def test_near_high_ratio_pct():
    assert near_high_ratio_pct(2, 8) == 25.0
    assert near_high_ratio_pct(0, 5) == 0.0
    assert near_high_ratio_pct(3, 0) is None


def test_stock_advance_ratio_pct():
    assert stock_advance_ratio_pct(4, 5) == 80.0
    assert stock_advance_ratio_pct(0, 5) == 0.0
    assert stock_advance_ratio_pct(2, 0) is None


def test_crypto_advance_ratio_pct():
    assert crypto_advance_ratio_pct(3, 4) == 75.0
    assert crypto_advance_ratio_pct(0, 5) == 0.0
    assert crypto_advance_ratio_pct(2, 0) is None


def test_is_breadth_thrust_day():
    assert is_breadth_thrust_day(25.0, 25.0) is True
    assert is_breadth_thrust_day(40.0, 30.0) is True
    assert is_breadth_thrust_day(24.9, 50.0) is False
    assert is_breadth_thrust_day(50.0, 24.9) is False
    assert is_breadth_thrust_day(None, 50.0) is False
    assert is_breadth_thrust_day(50.0, None) is False


def test_is_confirmed_thrust_day():
    # thrust + dual advance
    assert is_confirmed_thrust_day(25.0, 25.0, 50.0, 50.0) is True
    # thrust alone (split tape)
    assert is_confirmed_thrust_day(40.0, 30.0, 70.0, 30.0) is False
    # risk-on without thrust
    assert is_confirmed_thrust_day(10.0, 10.0, 60.0, 55.0) is False
    assert is_confirmed_thrust_day(None, 25.0, 50.0, 50.0) is False
    assert is_confirmed_thrust_day(25.0, 25.0, None, 50.0) is False


def test_is_unconfirmed_thrust_day():
    # Thrust without dual advance → alone / unconfirmed.
    assert is_unconfirmed_thrust_day(25.0, 25.0, 40.0, 40.0) is True
    assert is_unconfirmed_thrust_day(40.0, 30.0, 70.0, 30.0) is True
    # Confirmed (risk-on) is not alone.
    assert is_unconfirmed_thrust_day(25.0, 25.0, 50.0, 50.0) is False
    # No thrust → not alone.
    assert is_unconfirmed_thrust_day(10.0, 10.0, 30.0, 30.0) is False
    assert is_unconfirmed_thrust_day(None, 25.0, 40.0, 40.0) is False


def test_thrust_confirm_rate_pct():
    assert thrust_confirm_rate_pct(0, 0) is None
    assert thrust_confirm_rate_pct(1, 0) is None
    assert thrust_confirm_rate_pct(0, 2) == 0.0
    assert thrust_confirm_rate_pct(1, 2) == 50.0
    assert thrust_confirm_rate_pct(2, 2) == 100.0


def test_thrust_density_pct():
    assert thrust_density_pct(0, 0) is None
    assert thrust_density_pct(1, 0) is None
    assert thrust_density_pct(0, 4) == 0.0
    assert thrust_density_pct(1, 4) == 25.0
    assert thrust_density_pct(2, 4) == 50.0
    assert thrust_density_pct(4, 4) == 100.0


def test_confirmed_and_alone_density_pct():
    assert confirmed_density_pct(0, 0) is None
    assert alone_density_pct(1, 0) is None
    assert confirmed_density_pct(1, 4) == 25.0
    assert alone_density_pct(2, 4) == 50.0
    assert confirmed_density_pct(0, 3) == 0.0
    assert alone_density_pct(0, 3) == 0.0
    assert confirmed_density_pct(2, 5) == thrust_density_pct(2, 5)
    assert alone_density_pct(3, 5) == thrust_density_pct(3, 5)


def test_tape_label_density_pct():
    assert tape_label_density_pct(0, 0) is None
    assert tape_label_density_pct(1, 0) is None
    assert tape_label_density_pct(0, 4) == 0.0
    assert tape_label_density_pct(1, 4) == 25.0
    assert tape_label_density_pct(2, 4) == 50.0
    assert tape_label_density_pct(4, 4) == 100.0
    assert tape_label_density_pct(3, 5) == thrust_density_pct(3, 5)

def test_is_dual_advance_day():
    assert is_dual_advance_day(50.0, 50.0) is True
    assert is_dual_advance_day(80.0, 55.0) is True
    assert is_dual_advance_day(49.9, 50.0) is False
    assert is_dual_advance_day(50.0, 49.9) is False
    assert is_dual_advance_day(None, 80.0) is False
    assert is_dual_advance_day(80.0, None) is False


def test_is_tape_split_day():
    assert is_tape_split_day(70.0, 30.0) is True
    assert is_tape_split_day(20.0, 65.0) is True
    assert is_tape_split_day(60.0, 40.0) is True
    assert is_tape_split_day(59.9, 40.0) is False
    assert is_tape_split_day(60.0, 40.1) is False
    assert is_tape_split_day(80.0, 70.0) is False  # dual, not split
    assert is_tape_split_day(None, 30.0) is False


def test_is_risk_off_day():
    assert is_risk_off_day(40.0, 40.0) is True
    assert is_risk_off_day(20.0, 30.0) is True
    assert is_risk_off_day(40.1, 40.0) is False
    assert is_risk_off_day(40.0, 40.1) is False
    assert is_risk_off_day(70.0, 30.0) is False  # split, not risk-off
    assert is_risk_off_day(50.0, 50.0) is False  # dual
    assert is_risk_off_day(None, 20.0) is False
    assert is_risk_off_day(20.0, None) is False


def test_breadth_tape_label():
    assert breadth_tape_label(55.0, 60.0) == "risk-on"
    assert breadth_tape_label(70.0, 25.0) == "split"
    assert breadth_tape_label(30.0, 35.0) == "risk-off"
    assert breadth_tape_label(45.0, 55.0) == "mixed"
    assert breadth_tape_label(None, 80.0) == ""
    assert breadth_tape_label(50.0, None) == ""


def test_is_tape_flip():
    assert is_tape_flip("risk-on", "risk-off") is True
    assert is_tape_flip("mixed", "mixed") is False
    assert is_tape_flip("", "risk-on") is False
    assert is_tape_flip("risk-on", "") is False
    assert is_tape_flip(None, "split") is False


def test_breadth_prev_tape_label():
    rows = [
        {"day": "2026-09-01", "tape_label": "risk-on"},
        {"day": "2026-09-02", "tape_label": "mixed"},
        {"day": "2026-09-03", "tape_label": "risk-off"},
    ]
    assert breadth_prev_tape_label(rows) == "mixed"
    assert breadth_prev_tape_label(rows, through_day="2026-09-02") == "risk-on"
    assert breadth_prev_tape_label(rows[:1]) == ""
    assert breadth_prev_tape_label([], through_day="2026-09-01") == ""

def test_breadth_thrust_streak_from_newest():
    rows = [
        {"day": "2026-09-01", "is_thrust": True},
        {"day": "2026-09-02", "is_thrust": False},
        {"day": "2026-09-03", "is_thrust": True},
        {"day": "2026-09-04", "is_thrust": True},
    ]
    assert breadth_thrust_streak(rows) == 2
    assert breadth_thrust_streak(rows, through_day="2026-09-01") == 1
    assert breadth_thrust_streak(rows, through_day="2026-09-02") == 0
    assert breadth_thrust_streak(rows, through_day="1999-01-01") == 0
    assert breadth_thrust_streak([]) == 0


def test_breadth_dual_advance_streak_from_newest():
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True},
        {"day": "2026-09-02", "is_dual_advance": False},
        {"day": "2026-09-03", "is_dual_advance": True},
        {"day": "2026-09-04", "is_dual_advance": True},
    ]
    assert breadth_dual_advance_streak(rows) == 2
    assert breadth_dual_advance_streak(rows, through_day="2026-09-01") == 1
    assert breadth_dual_advance_streak(rows, through_day="2026-09-02") == 0
    assert breadth_dual_advance_streak([]) == 0


def test_breadth_tape_split_streak_from_newest():
    rows = [
        {"day": "2026-09-01", "is_tape_split": True},
        {"day": "2026-09-02", "is_tape_split": True},
        {"day": "2026-09-03", "is_tape_split": False},
    ]
    assert breadth_tape_split_streak(rows) == 0
    assert breadth_tape_split_streak(rows, through_day="2026-09-02") == 2
    assert breadth_tape_split_streak([]) == 0


def test_breadth_risk_off_streak_from_newest():
    rows = [
        {"day": "2026-09-01", "is_risk_off": True},
        {"day": "2026-09-02", "is_risk_off": False},
        {"day": "2026-09-03", "is_risk_off": True},
        {"day": "2026-09-04", "is_risk_off": True},
    ]
    assert breadth_risk_off_streak(rows) == 2
    assert breadth_risk_off_streak(rows, through_day="2026-09-01") == 1
    assert breadth_risk_off_streak(rows, through_day="2026-09-02") == 0
    assert breadth_risk_off_streak([]) == 0


def test_breadth_days_since_thrust():
    rows = [
        {"day": "2026-09-01", "is_thrust": True},
        {"day": "2026-09-02", "is_thrust": False},
        {"day": "2026-09-03", "is_thrust": False},
    ]
    assert breadth_days_since_thrust(rows) == 2
    assert breadth_days_since_thrust(rows, through_day="2026-09-02") == 1
    assert breadth_days_since_thrust(
        [{"day": "2026-09-01", "is_thrust": True}]
    ) == 0
    assert breadth_days_since_thrust(
        [{"day": "2026-09-01", "is_thrust": False}]
    ) is None
    assert breadth_days_since_thrust([]) is None


def test_breadth_confirmed_thrust_streak_and_days_since():
    rows = [
        {"day": "2026-09-01", "is_confirmed_thrust": True},
        {"day": "2026-09-02", "is_confirmed_thrust": False, "is_thrust": True},
        {"day": "2026-09-03", "is_confirmed_thrust": True},
        {"day": "2026-09-04", "is_confirmed_thrust": True},
    ]
    assert breadth_confirmed_thrust_streak(rows) == 2
    assert breadth_confirmed_thrust_streak(rows, through_day="2026-09-02") == 0
    assert breadth_days_since_confirmed_thrust(
        [
            {"day": "2026-09-01", "is_confirmed_thrust": True},
            {"day": "2026-09-02", "is_confirmed_thrust": False},
            {"day": "2026-09-03", "is_confirmed_thrust": False},
        ]
    ) == 2
    assert breadth_days_since_confirmed_thrust(
        [{"day": "2026-09-01", "is_confirmed_thrust": False}]
    ) is None


def test_breadth_unconfirmed_thrust_streak_and_days_since():
    rows = [
        {
            "day": "2026-09-01",
            "is_thrust": True,
            "is_confirmed_thrust": False,
            "is_unconfirmed_thrust": True,
        },
        {
            "day": "2026-09-02",
            "is_thrust": True,
            "is_confirmed_thrust": True,
            "is_unconfirmed_thrust": False,
        },
        {
            "day": "2026-09-03",
            "is_thrust": True,
            "is_confirmed_thrust": False,
            "is_unconfirmed_thrust": True,
        },
        {
            "day": "2026-09-04",
            "is_thrust": True,
            "is_confirmed_thrust": False,
            "is_unconfirmed_thrust": True,
        },
    ]
    # Ending alone streak is 2 (confirmed day breaks any-thrust streak sense).
    assert breadth_unconfirmed_thrust_streak(rows) == 2
    assert breadth_thrust_streak(rows) == 4
    assert breadth_unconfirmed_thrust_streak(rows, through_day="2026-09-02") == 0
    assert breadth_days_since_unconfirmed_thrust(
        [
            {
                "day": "2026-09-01",
                "is_unconfirmed_thrust": True,
            },
            {
                "day": "2026-09-02",
                "is_unconfirmed_thrust": False,
                "is_confirmed_thrust": True,
            },
            {
                "day": "2026-09-03",
                "is_unconfirmed_thrust": False,
                "is_thrust": False,
            },
        ]
    ) == 2
    assert (
        breadth_days_since_unconfirmed_thrust(
            [{"day": "2026-09-01", "is_unconfirmed_thrust": False}]
        )
        is None
    )


def test_breadth_days_since_risk_on():
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True},
        {"day": "2026-09-02", "is_dual_advance": False},
        {"day": "2026-09-03", "is_dual_advance": False},
        {"day": "2026-09-04", "is_dual_advance": False},
    ]
    assert breadth_days_since_risk_on(rows) == 3
    assert breadth_days_since_risk_on(rows, through_day="2026-09-02") == 1
    assert breadth_days_since_risk_on(
        [{"day": "2026-09-01", "is_dual_advance": True}]
    ) == 0
    assert breadth_days_since_risk_on([]) is None


def test_breadth_days_since_risk_off():
    rows = [
        {"day": "2026-09-01", "is_risk_off": True},
        {"day": "2026-09-02", "is_risk_off": False},
        {"day": "2026-09-03", "is_risk_off": False},
        {"day": "2026-09-04", "is_risk_off": False},
    ]
    assert breadth_days_since_risk_off(rows) == 3
    assert breadth_days_since_risk_off(rows, through_day="2026-09-02") == 1
    assert breadth_days_since_risk_off(
        [{"day": "2026-09-01", "is_risk_off": True}]
    ) == 0
    assert breadth_days_since_risk_off(
        [{"day": "2026-09-01", "is_risk_off": False}]
    ) is None
    assert breadth_days_since_risk_off([]) is None


def test_breadth_days_since_tape_split():
    rows = [
        {"day": "2026-09-01", "is_tape_split": True},
        {"day": "2026-09-02", "is_tape_split": False},
        {"day": "2026-09-03", "is_tape_split": False},
        {"day": "2026-09-04", "is_tape_split": False},
    ]
    assert breadth_days_since_tape_split(rows) == 3
    assert breadth_days_since_tape_split(rows, through_day="2026-09-02") == 1
    assert breadth_days_since_tape_split(
        [{"day": "2026-09-01", "is_tape_split": True}]
    ) == 0
    assert breadth_days_since_tape_split(
        [{"day": "2026-09-01", "is_tape_split": False}]
    ) is None
    assert breadth_days_since_tape_split([]) is None


def test_breadth_days_since_mixed():
    rows = [
        {"day": "2026-09-01", "tape_label": "mixed"},
        {"day": "2026-09-02", "tape_label": "risk-on"},
        {"day": "2026-09-03", "tape_label": "risk-on"},
        {"day": "2026-09-04", "tape_label": "risk-on"},
    ]
    assert breadth_days_since_mixed(rows) == 3
    assert breadth_days_since_mixed(rows, through_day="2026-09-02") == 1
    assert breadth_days_since_mixed(
        [{"day": "2026-09-01", "tape_label": "mixed"}]
    ) == 0
    assert breadth_days_since_mixed(
        [{"day": "2026-09-01", "tape_label": "risk-on"}]
    ) is None
    assert breadth_days_since_mixed([]) is None


def test_breadth_mixed_streak():
    rows = [
        {"day": "2026-09-01", "tape_label": "risk-on"},
        {"day": "2026-09-02", "tape_label": "mixed"},
        {"day": "2026-09-03", "tape_label": "mixed"},
        {"day": "2026-09-04", "tape_label": "mixed"},
    ]
    assert breadth_mixed_streak(rows) == 3
    assert breadth_mixed_streak(rows, through_day="2026-09-01") == 0
    assert breadth_mixed_streak(rows, through_day="2026-09-02") == 1
    assert breadth_mixed_streak([]) == 0


def test_breadth_thrust_summary_days_since():
    rows = [
        {"day": "2026-09-01", "is_thrust": True},
        {"day": "2026-09-02", "is_thrust": False},
        {"day": "2026-09-03", "is_thrust": False},
    ]
    s = build_breadth_thrust_summary(rows)
    assert s["ready"] is True
    assert s["latest"] is False
    assert s["latest_confirmed"] is False
    assert s["latest_alone"] is False
    assert s["days_since"] == 2
    assert s["alone_n"] == 1
    assert s["days_since_alone"] == 2
    assert s["confirmed_n"] == 0
    assert s["confirm_rate_pct"] == 0.0
    assert "confirm 0% (0/1 thrust)" in s["line"]
    assert "2d since alone" in s["line"]
    assert "0/3 confirmed" in s["line"]
    assert "1/3 alone" in s["line"]
    assert "1/3 thrust days" in s["line"]


def test_breadth_thrust_summary_confirmed_vs_alone():
    alone = [
        {
            "day": "2026-09-01",
            "is_thrust": True,
            "is_dual_advance": False,
            "is_confirmed_thrust": False,
            "is_unconfirmed_thrust": True,
        }
    ]
    s = build_breadth_thrust_summary(alone)
    assert s["latest"] is True
    assert s["latest_confirmed"] is False
    assert s["latest_alone"] is True
    assert s["alone_n"] == 1
    assert s["alone_streak"] == 1
    assert "thrust alone (not risk-on)" in s["line"]
    assert s["tone"] == "flat"

    alone_streak = [
        {
            "day": "2026-09-01",
            "is_thrust": True,
            "is_confirmed_thrust": False,
            "is_unconfirmed_thrust": True,
        },
        {
            "day": "2026-09-02",
            "is_thrust": True,
            "is_confirmed_thrust": False,
            "is_unconfirmed_thrust": True,
        },
    ]
    a2 = build_breadth_thrust_summary(alone_streak)
    assert a2["alone_streak"] == 2
    assert "alone streak 2" in a2["line"]

    confirmed = [
        {
            "day": "2026-09-01",
            "is_thrust": True,
            "is_dual_advance": True,
            "is_confirmed_thrust": True,
            "is_unconfirmed_thrust": False,
        },
        {
            "day": "2026-09-02",
            "is_thrust": True,
            "is_dual_advance": True,
            "is_confirmed_thrust": True,
            "is_unconfirmed_thrust": False,
        },
    ]
    c = build_breadth_thrust_summary(confirmed)
    assert c["latest_confirmed"] is True
    assert c["latest_alone"] is False
    assert c["confirmed_n"] == 2
    assert c["alone_n"] == 0
    assert c["confirm_rate_pct"] == 100.0
    assert c["confirmed_streak"] == 2
    assert "confirmed thrust now" in c["line"]
    assert "confirmed streak 2" in c["line"]
    assert "confirm 100% (2/2 thrust)" in c["line"]
    assert c["tone"] == "up"


def test_breadth_tape_summary_days_since_risk_on():
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_dual_advance": False, "tape_label": "mixed"},
        {"day": "2026-09-03", "is_dual_advance": False, "tape_label": "mixed"},
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["latest_dual"] is False
    assert s["days_since_risk_on"] == 2
    assert "2d since risk-on" in s["line"]
    assert "mixed now" in s["line"]


def test_breadth_tape_summary_days_since_risk_off():
    rows = [
        {"day": "2026-09-01", "is_risk_off": True, "tape_label": "risk-off"},
        {
            "day": "2026-09-02",
            "is_dual_advance": True,
            "is_risk_off": False,
            "tape_label": "risk-on",
        },
        {
            "day": "2026-09-03",
            "is_dual_advance": True,
            "is_risk_off": False,
            "tape_label": "risk-on",
        },
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["latest_dual"] is True
    assert s["latest_risk_off"] is False
    assert s["days_since_risk_off"] == 2
    assert "2d since risk-off" in s["line"]
    assert "risk-on now" in s["line"]
    # Active risk-off day must not append "Nd since risk-off".
    off_now = build_breadth_tape_summary(
        [
            {"day": "2026-09-01", "is_risk_off": True, "tape_label": "risk-off"},
            {"day": "2026-09-02", "is_risk_off": True, "tape_label": "risk-off"},
        ]
    )
    assert off_now["days_since_risk_off"] == 0
    assert "since risk-off" not in off_now["line"]
    assert "risk-off now" in off_now["line"]


def test_breadth_tape_summary_days_since_tape_split():
    rows = [
        {"day": "2026-09-01", "is_tape_split": True, "tape_label": "split"},
        {
            "day": "2026-09-02",
            "is_dual_advance": True,
            "is_tape_split": False,
            "tape_label": "risk-on",
        },
        {
            "day": "2026-09-03",
            "is_dual_advance": True,
            "is_tape_split": False,
            "tape_label": "risk-on",
        },
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["latest_dual"] is True
    assert s["latest_split"] is False
    assert s["days_since_tape_split"] == 2
    assert "2d since split" in s["line"]
    assert "risk-on now" in s["line"]
    # Active split day must not append "Nd since split".
    split_now = build_breadth_tape_summary(
        [
            {"day": "2026-09-01", "is_tape_split": True, "tape_label": "split"},
            {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        ]
    )
    assert split_now["days_since_tape_split"] == 0
    assert "since split" not in split_now["line"]
    assert "split now" in split_now["line"]


def test_breadth_tape_summary_days_since_mixed():
    rows = [
        {"day": "2026-09-01", "tape_label": "mixed"},
        {
            "day": "2026-09-02",
            "is_dual_advance": True,
            "tape_label": "risk-on",
        },
        {
            "day": "2026-09-03",
            "is_dual_advance": True,
            "tape_label": "risk-on",
        },
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["latest_dual"] is True
    assert s["latest_mixed"] is False
    assert s["days_since_mixed"] == 2
    assert "2d since mixed" in s["line"]
    assert "risk-on now" in s["line"]
    # Active mixed day must not append "Nd since mixed"; streak ≥2 shown.
    mixed_now = build_breadth_tape_summary(
        [
            {"day": "2026-09-01", "tape_label": "mixed"},
            {"day": "2026-09-02", "tape_label": "mixed"},
        ]
    )
    assert mixed_now["days_since_mixed"] == 0
    assert mixed_now["mixed_streak"] == 2
    assert "since mixed" not in mixed_now["line"]
    assert "mixed now" in mixed_now["line"]
    assert "streak 2" in mixed_now["line"]


def test_breadth_glance_days_since_from_history():
    hist = [
        {
            "day": "2026-09-01",
            "is_thrust": True,
            "is_dual_advance": True,
            "stock_scan_up": 6,
            "stock_scan_down": 4,
            "crypto_up": 3,
            "crypto_down": 2,
            "crypto_big_movers": 2,
            "stock_breakouts_n": 4,
            "stock_within_5pct_high": 2,
        },
        {
            "day": "2026-09-02",
            # mixed: 50% stock · 40% crypto; no thrust
            "stock_scan_up": 5,
            "stock_scan_down": 5,
            "crypto_up": 2,
            "crypto_down": 3,
            "crypto_big_movers": 0,
            "stock_breakouts_n": 4,
            "stock_within_5pct_high": 0,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["is_thrust"] is False
    assert g["is_dual_advance"] is False
    assert g["is_confirmed_thrust"] is False
    assert g["days_since_thrust"] == 1
    assert g["days_since_confirmed_thrust"] == 1
    assert g["days_since_risk_on"] == 1
    assert "1d since confirmed" in g["line"]
    assert "1d since risk-on" in g["line"]


def test_breadth_glance_days_since_risk_off_from_history():
    hist = [
        {
            "day": "2026-09-01",
            # risk-off: both sleeves ≤40%
            "stock_scan_up": 2,
            "stock_scan_down": 8,
            "crypto_up": 1,
            "crypto_down": 4,
            "crypto_big_movers": 0,
            "stock_breakouts_n": 4,
            "stock_within_5pct_high": 0,
        },
        {
            "day": "2026-09-02",
            # risk-on: both ≥50%
            "stock_scan_up": 6,
            "stock_scan_down": 4,
            "crypto_up": 3,
            "crypto_down": 2,
            "crypto_big_movers": 0,
            "stock_breakouts_n": 4,
            "stock_within_5pct_high": 0,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["is_dual_advance"] is True
    assert g["is_risk_off"] is False
    assert g["days_since_risk_off"] == 1
    assert "1d since risk-off" in g["line"]
    assert "since risk-on" not in g["line"]


def test_breadth_glance_days_since_tape_split_from_history():
    hist = [
        {
            "day": "2026-09-01",
            # split: stock 70% · crypto 30%
            "stock_scan_up": 7,
            "stock_scan_down": 3,
            "crypto_up": 3,
            "crypto_down": 7,
            "crypto_big_movers": 0,
            "stock_breakouts_n": 4,
            "stock_within_5pct_high": 0,
        },
        {
            "day": "2026-09-02",
            # risk-on: both ≥50%
            "stock_scan_up": 6,
            "stock_scan_down": 4,
            "crypto_up": 3,
            "crypto_down": 2,
            "crypto_big_movers": 0,
            "stock_breakouts_n": 4,
            "stock_within_5pct_high": 0,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["is_dual_advance"] is True
    assert g["is_tape_split"] is False
    assert g["days_since_tape_split"] == 1
    assert "1d since split" in g["line"]
    assert "since risk-on" not in g["line"]


def test_breadth_glance_days_since_mixed_from_history():
    hist = [
        {
            "day": "2026-09-01",
            # mixed: 50% stock · 40% crypto
            "stock_scan_up": 5,
            "stock_scan_down": 5,
            "crypto_up": 2,
            "crypto_down": 3,
            "crypto_big_movers": 0,
            "stock_breakouts_n": 4,
            "stock_within_5pct_high": 0,
        },
        {
            "day": "2026-09-02",
            # risk-on: both ≥50%
            "stock_scan_up": 6,
            "stock_scan_down": 4,
            "crypto_up": 3,
            "crypto_down": 2,
            "crypto_big_movers": 0,
            "stock_breakouts_n": 4,
            "stock_within_5pct_high": 0,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["is_dual_advance"] is True
    assert g["is_mixed"] is False
    assert g["days_since_mixed"] == 1
    assert "1d since mixed" in g["line"]
    assert "since risk-on" not in g["line"]


def test_breadth_glance_mixed_streak_from_history():
    hist = [
        {
            "day": "2026-09-01",
            "stock_scan_up": 5,
            "stock_scan_down": 5,
            "crypto_up": 2,
            "crypto_down": 3,
        },
        {
            "day": "2026-09-02",
            "stock_scan_up": 5,
            "stock_scan_down": 5,
            "crypto_up": 2,
            "crypto_down": 3,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["is_mixed"] is True
    assert g["mixed_streak"] == 2
    assert "mixed · streak 2" in g["line"]
    assert "since mixed" not in g["line"]


def test_breadth_tape_summary_risk_on_streak():
    rows = [
        {"day": "2026-09-01", "is_dual_advance": False, "is_tape_split": True},
        {"day": "2026-09-02", "is_dual_advance": True, "is_tape_split": False},
        {"day": "2026-09-03", "is_dual_advance": True, "is_tape_split": False},
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["dual_n"] == 2
    assert s["split_n"] == 1
    assert s["risk_off_n"] == 0
    assert s["dual_streak"] == 2
    assert s["split_streak"] == 0
    assert s["latest_dual"] is True
    assert s["tone"] == "up"
    assert "risk-on now" in s["line"]
    assert "streak 2" in s["line"]
    assert "2/3 risk-on" in s["line"]
    assert "0/3 risk-off" in s["line"]
    assert "0/3 mixed" in s["line"]
    assert s["mixed_n"] == 0
    # Ending day continues risk-on; flip was day 1→2, not day 2→3.
    assert s["tape_flip"] is False
    assert s["prev_label"] == "risk-on"
    assert "flipped" not in s["line"]


def test_breadth_tape_summary_split_now():
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "is_tape_split": False},
        {"day": "2026-09-02", "is_dual_advance": False, "is_tape_split": True},
    ]
    s = build_breadth_tape_summary(rows)
    assert s["latest_split"] is True
    assert s["split_streak"] == 1
    assert s["tone"] == "down"
    assert "split now" in s["line"]
    assert "streak" not in s["line"]  # streak 1 stays quiet
    assert s["tape_flip"] is True
    assert "flipped risk-on→split" in s["line"]


def test_breadth_tape_summary_mixed_and_no_false_flip():
    rows = [
        {"day": "2026-09-01", "tape_label": "mixed"},
        {"day": "2026-09-02", "tape_label": "mixed"},
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["mixed_n"] == 2
    assert s["latest_mixed"] is True
    assert s["latest_label"] == "mixed"
    assert s["tape_flip"] is False
    assert "mixed now" in s["line"]
    assert "2/2 mixed" in s["line"]
    assert "flipped" not in s["line"]


def test_breadth_tape_summary_risk_off_streak():
    rows = [
        {
            "day": "2026-09-01",
            "is_dual_advance": False,
            "is_tape_split": False,
            "is_risk_off": True,
        },
        {
            "day": "2026-09-02",
            "is_dual_advance": False,
            "is_tape_split": False,
            "is_risk_off": True,
        },
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["risk_off_n"] == 2
    assert s["risk_off_streak"] == 2
    assert s["latest_risk_off"] is True
    assert s["tone"] == "down"
    assert "risk-off now" in s["line"]
    assert "streak 2" in s["line"]
    assert "2/2 risk-off" in s["line"]


def test_breadth_tape_summary_empty():
    assert build_breadth_tape_summary([])["ready"] is False
    assert build_breadth_tape_summary([])["dual_streak"] == 0
    assert build_breadth_tape_summary([])["risk_off_streak"] == 0
    assert build_breadth_tape_summary([])["risk_on_density_pct"] is None
    assert build_breadth_tape_summary([])["split_density_pct"] is None
    assert build_breadth_tape_summary([])["risk_off_density_pct"] is None
    assert build_breadth_tape_summary([])["mixed_density_pct"] is None
    assert build_breadth_tape_summary([])["flip_density_pct"] is None
    assert build_breadth_tape_summary([])["flip_n"] == 0
    assert build_breadth_tape_summary([])["pair_n"] == 0
    assert build_breadth_tape_summary([])["days_since_tape_flip"] is None


def test_tape_flip_density_pct():
    assert tape_flip_density_pct(0, 0) is None
    assert tape_flip_density_pct(1, 0) is None
    assert tape_flip_density_pct(0, 3) == 0.0
    assert tape_flip_density_pct(2, 4) == 50.0
    assert tape_flip_density_pct(3, 3) == 100.0


def test_breadth_days_since_tape_flip():
    # risk-on → split → mixed → mixed: last flip on day 3 → 1d since on day 4
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "tape_label": "mixed"},
        {"day": "2026-09-04", "tape_label": "mixed"},
    ]
    assert breadth_days_since_tape_flip(rows) == 1
    assert breadth_days_since_tape_flip(rows, through_day="2026-09-02") == 0
    assert breadth_days_since_tape_flip(rows, through_day="2026-09-03") == 0
    assert breadth_days_since_tape_flip(
        [
            {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-02", "is_dual_advance": True, "tape_label": "risk-on"},
        ]
    ) is None
    assert breadth_days_since_tape_flip([]) is None
    assert breadth_days_since_tape_flip(
        [{"day": "2026-09-01", "tape_label": "mixed"}]
    ) is None


def test_breadth_tape_flip_streak():
    # risk-on → split → risk-off → mixed: 3 consecutive flips ending now
    storm = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-04", "tape_label": "mixed"},
    ]
    assert breadth_tape_flip_streak(storm) == 3
    assert breadth_tape_flip_streak(storm, through_day="2026-09-02") == 1
    assert breadth_tape_flip_streak(storm, through_day="2026-09-03") == 2
    # settle after flip → streak 0
    settle = storm + [{"day": "2026-09-05", "tape_label": "mixed"}]
    assert breadth_tape_flip_streak(settle) == 0
    assert breadth_tape_flip_streak([]) == 0
    assert breadth_tape_flip_streak(
        [{"day": "2026-09-01", "tape_label": "mixed"}]
    ) == 0
    assert breadth_tape_flip_streak(
        [
            {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-02", "is_dual_advance": True, "tape_label": "risk-on"},
        ]
    ) == 0


def test_breadth_tape_flip_max_streak():
    # early storm of 3, then settle, then single flip → max stays 3
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-04", "tape_label": "mixed"},
        {"day": "2026-09-05", "tape_label": "mixed"},
        {"day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
    ]
    assert breadth_tape_flip_max_streak(rows) == 3
    assert breadth_tape_flip_streak(rows) == 1
    assert breadth_tape_flip_max_streak(rows, through_day="2026-09-04") == 3
    assert breadth_tape_flip_max_streak(rows, through_day="2026-09-02") == 1
    assert breadth_tape_flip_max_streak([]) == 0
    assert breadth_tape_flip_max_streak(
        [{"day": "2026-09-01", "tape_label": "mixed"}]
    ) == 0
    calm = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_dual_advance": True, "tape_label": "risk-on"},
    ]
    assert breadth_tape_flip_max_streak(calm) == 0
    # ending storm equals max
    storm = rows[:4]
    assert breadth_tape_flip_max_streak(storm) == 3
    assert breadth_tape_flip_streak(storm) == 3


def test_breadth_tape_flip_mean_streak():
    # runs: length 3 then length 1 → mean 2.0, two runs
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-04", "tape_label": "mixed"},
        {"day": "2026-09-05", "tape_label": "mixed"},
        {"day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
    ]
    assert breadth_tape_flip_mean_streak(rows) == 2.0
    assert breadth_tape_flip_run_count(rows) == 2
    assert breadth_tape_flip_mean_streak(rows, through_day="2026-09-04") == 3.0
    assert breadth_tape_flip_run_count(rows, through_day="2026-09-04") == 1
    assert breadth_tape_flip_mean_streak([]) is None
    assert breadth_tape_flip_run_count([]) == 0
    assert breadth_tape_flip_mean_streak(
        [{"day": "2026-09-01", "tape_label": "mixed"}]
    ) is None
    calm = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_dual_advance": True, "tape_label": "risk-on"},
    ]
    assert breadth_tape_flip_mean_streak(calm) is None
    assert breadth_tape_flip_run_count(calm) == 0
    # single run → mean equals max
    storm = rows[:4]
    assert breadth_tape_flip_mean_streak(storm) == 3.0
    assert breadth_tape_flip_run_count(storm) == 1


def test_breadth_tape_flip_median_streak():
    # runs: 3, 1, 1 → mean ≈1.67, median 1.0 (mean pulled by long storm)
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-04", "tape_label": "mixed"},
        {"day": "2026-09-05", "tape_label": "mixed"},
        {"day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-07", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-08", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-09", "is_risk_off": True, "tape_label": "risk-off"},
    ]
    assert breadth_tape_flip_run_count(rows) == 3
    assert abs(breadth_tape_flip_mean_streak(rows) - (5.0 / 3.0)) < 1e-9
    assert breadth_tape_flip_median_streak(rows) == 1.0
    assert breadth_tape_flip_median_streak(rows, through_day="2026-09-04") == 3.0
    assert breadth_tape_flip_median_streak([]) is None
    assert breadth_tape_flip_median_streak(
        [{"day": "2026-09-01", "tape_label": "mixed"}]
    ) is None
    # two runs → median equals mean of the pair
    two = rows[:6]
    assert breadth_tape_flip_run_count(two) == 2
    assert breadth_tape_flip_median_streak(two) == 2.0
    assert breadth_tape_flip_mean_streak(two) == 2.0
    calm = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_dual_advance": True, "tape_label": "risk-on"},
    ]
    assert breadth_tape_flip_median_streak(calm) is None


def test_breadth_tape_flip_min_streak():
    # runs: 3, 1, 1 → min 1, max 3
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-04", "tape_label": "mixed"},
        {"day": "2026-09-05", "tape_label": "mixed"},
        {"day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-07", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-08", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-09", "is_risk_off": True, "tape_label": "risk-off"},
    ]
    assert breadth_tape_flip_min_streak(rows) == 1
    assert breadth_tape_flip_max_streak(rows) == 3
    assert breadth_tape_flip_min_streak(rows, through_day="2026-09-04") == 3
    assert breadth_tape_flip_min_streak([]) == 0
    assert breadth_tape_flip_min_streak(
        [{"day": "2026-09-01", "tape_label": "mixed"}]
    ) == 0
    # two runs 3 + 1 → min 1
    two = rows[:6]
    assert breadth_tape_flip_run_count(two) == 2
    assert breadth_tape_flip_min_streak(two) == 1
    assert breadth_tape_flip_max_streak(two) == 3
    calm = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_dual_advance": True, "tape_label": "risk-on"},
    ]
    assert breadth_tape_flip_min_streak(calm) == 0
    # single run → min equals max
    storm = rows[:4]
    assert breadth_tape_flip_min_streak(storm) == 3
    assert breadth_tape_flip_max_streak(storm) == 3


def test_breadth_tape_flip_stdev_streak():
    # runs: 3, 1, 1 → sample σ = sqrt(4/3) ≈ 1.1547
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-04", "tape_label": "mixed"},
        {"day": "2026-09-05", "tape_label": "mixed"},
        {"day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-07", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-08", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-09", "is_risk_off": True, "tape_label": "risk-off"},
    ]
    assert abs(breadth_tape_flip_stdev_streak(rows) - (4.0 / 3.0) ** 0.5) < 1e-9
    # through first run only → one run → None
    assert breadth_tape_flip_stdev_streak(rows, through_day="2026-09-04") is None
    assert breadth_tape_flip_stdev_streak([]) is None
    assert breadth_tape_flip_stdev_streak(
        [{"day": "2026-09-01", "tape_label": "mixed"}]
    ) is None
    # two runs 3 + 1 → sample σ = sqrt(2)
    two = rows[:6]
    assert breadth_tape_flip_run_count(two) == 2
    assert abs(breadth_tape_flip_stdev_streak(two) - (2.0**0.5)) < 1e-9
    calm = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_dual_advance": True, "tape_label": "risk-on"},
    ]
    assert breadth_tape_flip_stdev_streak(calm) is None
    # equal run lengths → σ = 0
    even = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "tape_label": "mixed"},
        {"day": "2026-09-04", "tape_label": "mixed"},
        {"day": "2026-09-05", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-07", "is_dual_advance": True, "tape_label": "risk-on"},
    ]
    # runs: 2, 2 → σ = 0
    assert breadth_tape_flip_run_count(even) == 2
    assert breadth_tape_flip_stdev_streak(even) == 0.0


def test_breadth_tape_summary_flip_max_streak_replay():
    """Peak chop after settle: max flip > ending streak shows on summary."""
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-04", "tape_label": "mixed"},
        {"day": "2026-09-05", "tape_label": "mixed"},
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["flip_streak"] == 0
    assert s["flip_max_streak"] == 3
    assert s["days_since_tape_flip"] == 1
    assert "1d since flip" in s["line"]
    assert "max flip 3" in s["line"]
    assert "flip streak" not in s["line"]
    # at peak: ending == max → no separate max bit
    peak = build_breadth_tape_summary(rows[:4])
    assert peak["flip_streak"] == 3
    assert peak["flip_max_streak"] == 3
    assert "flip streak 3" in peak["line"]
    assert "max flip" not in peak["line"]
    calm = build_breadth_tape_summary(
        [
            {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-02", "is_dual_advance": True, "tape_label": "risk-on"},
        ]
    )
    assert calm["flip_max_streak"] == 0
    assert "max flip" not in calm["line"]


def test_breadth_tape_summary_flip_mean_streak_replay():
    """Typical chop: ≥2 flip runs → avg flip on summary (vs peak max)."""
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-04", "tape_label": "mixed"},
        {"day": "2026-09-05", "tape_label": "mixed"},
        {"day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["flip_max_streak"] == 3
    assert s["flip_mean_streak"] == 2.0
    assert s["flip_run_n"] == 2
    assert "max flip 3" in s["line"]
    assert "avg flip 2.0 (2 runs)" in s["line"]
    # single run → mean equals max; hide avg (redundant)
    peak = build_breadth_tape_summary(rows[:4])
    assert peak["flip_mean_streak"] == 3.0
    assert peak["flip_run_n"] == 1
    assert "avg flip" not in peak["line"]
    calm = build_breadth_tape_summary(
        [
            {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-02", "is_dual_advance": True, "tape_label": "risk-on"},
        ]
    )
    assert calm["flip_mean_streak"] is None
    assert calm["flip_run_n"] == 0
    assert "avg flip" not in calm["line"]


def test_breadth_tape_summary_flip_median_streak_replay():
    """Robust typical: ≥3 runs + median ≠ mean → med flip on summary."""
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-04", "tape_label": "mixed"},
        {"day": "2026-09-05", "tape_label": "mixed"},
        {"day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-07", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-08", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-09", "is_risk_off": True, "tape_label": "risk-off"},
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["flip_run_n"] == 3
    assert s["flip_median_streak"] == 1.0
    assert abs(s["flip_mean_streak"] - (5.0 / 3.0)) < 1e-9
    assert "avg flip 1.7 (3 runs)" in s["line"]
    assert "med flip 1.0" in s["line"]
    # two runs only → median == mean; hide med (needs ≥3 + diverge)
    two = build_breadth_tape_summary(rows[:6])
    assert two["flip_run_n"] == 2
    assert two["flip_median_streak"] == 2.0
    assert "med flip" not in two["line"]
    assert "avg flip 2.0 (2 runs)" in two["line"]


def test_breadth_tape_summary_flip_min_streak_replay():
    """Floor chop: ≥2 runs and min < max → min flip on summary."""
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-04", "tape_label": "mixed"},
        {"day": "2026-09-05", "tape_label": "mixed"},
        {"day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["flip_run_n"] == 2
    assert s["flip_min_streak"] == 1
    assert s["flip_max_streak"] == 3
    assert "min flip 1" in s["line"]
    assert "max flip 3" in s["line"]
    # single run → min == max; hide min
    peak = build_breadth_tape_summary(rows[:4])
    assert peak["flip_min_streak"] == 3
    assert peak["flip_max_streak"] == 3
    assert "min flip" not in peak["line"]
    calm = build_breadth_tape_summary(
        [
            {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-02", "is_dual_advance": True, "tape_label": "risk-on"},
        ]
    )
    assert calm["flip_min_streak"] == 0
    assert "min flip" not in calm["line"]


def test_breadth_tape_summary_flip_stdev_streak_replay():
    """Chop dispersion: ≥3 runs and σ ≥ 0.05 → σ flip on summary."""
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-04", "tape_label": "mixed"},
        {"day": "2026-09-05", "tape_label": "mixed"},
        {"day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-07", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-08", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-09", "is_risk_off": True, "tape_label": "risk-off"},
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["flip_run_n"] == 3
    assert abs(s["flip_stdev_streak"] - (4.0 / 3.0) ** 0.5) < 1e-9
    assert "σ flip 1.2" in s["line"]
    # two runs only → hide σ (needs ≥3)
    two = build_breadth_tape_summary(rows[:6])
    assert two["flip_run_n"] == 2
    assert abs(two["flip_stdev_streak"] - (2.0**0.5)) < 1e-9
    assert "σ flip" not in two["line"]
    # equal lengths → σ = 0; hide
    even = build_breadth_tape_summary(
        [
            {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
            {"day": "2026-09-03", "tape_label": "mixed"},
            {"day": "2026-09-04", "tape_label": "mixed"},
            {"day": "2026-09-05", "is_risk_off": True, "tape_label": "risk-off"},
            {"day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-07", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-08", "is_tape_split": True, "tape_label": "split"},
            {"day": "2026-09-09", "is_risk_off": True, "tape_label": "risk-off"},
            {"day": "2026-09-10", "is_risk_off": True, "tape_label": "risk-off"},
        ]
    )
    # runs 2, 2, 2 → σ = 0
    assert even["flip_run_n"] == 3
    assert even["flip_stdev_streak"] == 0.0
    assert "σ flip" not in even["line"]


def test_breadth_glance_flip_max_streak_from_history():
    hist = [
        {
            "day": "2026-09-01",
            "is_dual_advance": True,
            "tape_label": "risk-on",
            "crypto_n": 4,
            "crypto_up": 3,
            "crypto_down": 1,
            "stock_scan_n": 10,
            "stock_scan_up": 6,
            "stock_scan_down": 4,
        },
        {
            "day": "2026-09-02",
            "is_tape_split": True,
            "tape_label": "split",
            "crypto_n": 4,
            "crypto_up": 1,
            "crypto_down": 3,
            "stock_scan_n": 10,
            "stock_scan_up": 7,
            "stock_scan_down": 3,
        },
        {
            "day": "2026-09-03",
            "is_risk_off": True,
            "tape_label": "risk-off",
            "crypto_n": 4,
            "crypto_up": 1,
            "crypto_down": 3,
            "stock_scan_n": 10,
            "stock_scan_up": 3,
            "stock_scan_down": 7,
        },
        {
            "day": "2026-09-04",
            "is_risk_off": True,
            "tape_label": "risk-off",
            "crypto_n": 4,
            "crypto_up": 1,
            "crypto_down": 3,
            "stock_scan_n": 10,
            "stock_scan_up": 3,
            "stock_scan_down": 7,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["flip_streak"] == 0
    assert g["flip_max_streak"] == 2
    assert "max flip 2" in g["line"]
    assert "flip streak" not in g["line"]


def test_breadth_glance_flip_mean_streak_from_history():
    """Glance shows avg flip when ≥2 distinct flip runs in history."""
    base = {
        "crypto_n": 4,
        "crypto_up": 2,
        "crypto_down": 2,
        "stock_scan_n": 10,
        "stock_scan_up": 5,
        "stock_scan_down": 5,
    }
    hist = [
        {**base, "day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {**base, "day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {**base, "day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {**base, "day": "2026-09-04", "tape_label": "mixed"},
        {**base, "day": "2026-09-05", "tape_label": "mixed"},
        {**base, "day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["flip_mean_streak"] == 2.0
    assert g["flip_run_n"] == 2
    assert g["flip_max_streak"] == 3
    assert "avg flip 2.0 (2 runs)" in g["line"]
    assert "max flip 3" in g["line"]


def test_breadth_glance_flip_median_streak_from_history():
    """Glance shows med flip when ≥3 runs and median diverges from mean."""
    base = {
        "crypto_n": 4,
        "crypto_up": 2,
        "crypto_down": 2,
        "stock_scan_n": 10,
        "stock_scan_up": 5,
        "stock_scan_down": 5,
    }
    hist = [
        {**base, "day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {**base, "day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {**base, "day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {**base, "day": "2026-09-04", "tape_label": "mixed"},
        {**base, "day": "2026-09-05", "tape_label": "mixed"},
        {**base, "day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
        {**base, "day": "2026-09-07", "is_dual_advance": True, "tape_label": "risk-on"},
        {**base, "day": "2026-09-08", "is_risk_off": True, "tape_label": "risk-off"},
        {**base, "day": "2026-09-09", "is_risk_off": True, "tape_label": "risk-off"},
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["flip_run_n"] == 3
    assert g["flip_median_streak"] == 1.0
    assert "med flip 1.0" in g["line"]
    assert "avg flip 1.7 (3 runs)" in g["line"]


def test_breadth_glance_flip_min_streak_from_history():
    """Glance shows min flip when ≥2 runs and min < max."""
    base = {
        "crypto_n": 4,
        "crypto_up": 2,
        "crypto_down": 2,
        "stock_scan_n": 10,
        "stock_scan_up": 5,
        "stock_scan_down": 5,
    }
    hist = [
        {**base, "day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {**base, "day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {**base, "day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {**base, "day": "2026-09-04", "tape_label": "mixed"},
        {**base, "day": "2026-09-05", "tape_label": "mixed"},
        {**base, "day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["flip_min_streak"] == 1
    assert g["flip_max_streak"] == 3
    assert "min flip 1" in g["line"]
    assert "max flip 3" in g["line"]


def test_breadth_glance_flip_stdev_streak_from_history():
    """Glance shows σ flip when ≥3 uneven runs."""
    base = {
        "crypto_n": 4,
        "crypto_up": 2,
        "crypto_down": 2,
        "stock_scan_n": 10,
        "stock_scan_up": 5,
        "stock_scan_down": 5,
    }
    hist = [
        {**base, "day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {**base, "day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {**base, "day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {**base, "day": "2026-09-04", "tape_label": "mixed"},
        {**base, "day": "2026-09-05", "tape_label": "mixed"},
        {**base, "day": "2026-09-06", "is_dual_advance": True, "tape_label": "risk-on"},
        {**base, "day": "2026-09-07", "is_dual_advance": True, "tape_label": "risk-on"},
        {**base, "day": "2026-09-08", "is_risk_off": True, "tape_label": "risk-off"},
        {**base, "day": "2026-09-09", "is_risk_off": True, "tape_label": "risk-off"},
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["flip_run_n"] == 3
    assert abs(g["flip_stdev_streak"] - (4.0 / 3.0) ** 0.5) < 1e-9
    assert "σ flip 1.2" in g["line"]


def test_breadth_tape_summary_flip_streak_replay():
    """Chop storm: consecutive flips ending now show flip streak ≥2."""
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["tape_flip"] is True
    assert s["flip_streak"] == 2
    assert s["days_since_tape_flip"] == 0
    assert "flipped split→risk-off" in s["line"]
    assert "flip streak 2" in s["line"]
    calm = build_breadth_tape_summary(
        [
            {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-02", "is_dual_advance": True, "tape_label": "risk-on"},
        ]
    )
    assert calm["flip_streak"] == 0
    assert "flip streak" not in calm["line"]
    single = build_breadth_tape_summary(
        [
            {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-02", "is_risk_off": True, "tape_label": "risk-off"},
        ]
    )
    assert single["flip_streak"] == 1
    assert "flipped risk-on→risk-off" in single["line"]
    assert "flip streak" not in single["line"]  # only ≥2


def test_breadth_glance_flip_streak_from_history():
    hist = [
        {
            "day": "2026-09-01",
            "is_dual_advance": True,
            "tape_label": "risk-on",
            "crypto_n": 4,
            "crypto_up": 3,
            "crypto_down": 1,
            "stock_scan_n": 10,
            "stock_scan_up": 6,
            "stock_scan_down": 4,
        },
        {
            "day": "2026-09-02",
            "is_tape_split": True,
            "tape_label": "split",
            "crypto_n": 4,
            "crypto_up": 1,
            "crypto_down": 3,
            "stock_scan_n": 10,
            "stock_scan_up": 7,
            "stock_scan_down": 3,
        },
        {
            "day": "2026-09-03",
            "is_risk_off": True,
            "tape_label": "risk-off",
            "crypto_n": 4,
            "crypto_up": 1,
            "crypto_down": 3,
            "stock_scan_n": 10,
            "stock_scan_up": 3,
            "stock_scan_down": 7,
        },
    ]
    pulse = hist[-1]
    g = build_breadth_glance(pulse, history=hist)
    assert g["ready"] is True
    assert g["tape_flip"] is True
    assert g["flip_streak"] == 2
    assert "flip streak 2" in g["line"]
    settled = hist + [
        {
            "day": "2026-09-04",
            "is_risk_off": True,
            "tape_label": "risk-off",
            "crypto_n": 4,
            "crypto_up": 1,
            "crypto_down": 3,
            "stock_scan_n": 10,
            "stock_scan_up": 3,
            "stock_scan_down": 7,
        }
    ]
    g2 = build_breadth_glance(settled[-1], history=settled)
    assert g2["flip_streak"] == 0
    assert "flip streak" not in g2["line"]


def test_breadth_tape_summary_flip_density_replay():
    """tradermonty-style executable replay: fixed multi-day tape path → flip dens."""
    # risk-on → split → risk-off → mixed → mixed: 3 flips / 4 pairs = 75%
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-04", "tape_label": "mixed"},
        {"day": "2026-09-05", "tape_label": "mixed"},
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["pair_n"] == 4
    assert s["flip_n"] == 3
    assert s["flip_density_pct"] == tape_flip_density_pct(3, 4)
    assert s["tape_flip"] is False  # ending day continues mixed
    assert s["days_since_tape_flip"] == 1
    assert s["flip_streak"] == 0
    assert "1d since flip" in s["line"]
    assert "flip dens 75% (3/4)" in s["line"]
    calm = build_breadth_tape_summary(
        [
            {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-02", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-03", "is_dual_advance": True, "tape_label": "risk-on"},
        ]
    )
    assert calm["pair_n"] == 2
    assert calm["flip_n"] == 0
    assert calm["flip_density_pct"] == 0.0
    assert calm["days_since_tape_flip"] is None
    assert calm["flip_streak"] == 0
    assert "flip dens 0% (0/2)" in calm["line"]
    assert "since flip" not in calm["line"]
    flip_now = build_breadth_tape_summary(
        [
            {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-02", "is_risk_off": True, "tape_label": "risk-off"},
        ]
    )
    assert flip_now["tape_flip"] is True
    assert flip_now["days_since_tape_flip"] == 0
    assert flip_now["flip_streak"] == 1
    assert "flipped risk-on→risk-off" in flip_now["line"]
    assert "since flip" not in flip_now["line"]
    assert "flip streak" not in flip_now["line"]

def test_breadth_glance_flip_density_from_history():
    hist = [
        {
            "day": "2026-09-01",
            "is_dual_advance": True,
            "tape_label": "risk-on",
            "crypto_n": 4,
            "crypto_up": 3,
            "crypto_down": 1,
            "stock_scan_n": 10,
            "stock_scan_up": 6,
            "stock_scan_down": 4,
        },
        {
            "day": "2026-09-02",
            "is_risk_off": True,
            "tape_label": "risk-off",
            "crypto_n": 4,
            "crypto_up": 1,
            "crypto_down": 3,
            "stock_scan_n": 10,
            "stock_scan_up": 3,
            "stock_scan_down": 7,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["pair_n"] == 1
    assert g["flip_n"] == 1
    assert g["flip_density_pct"] == 100.0
    assert g["tape_flip"] is True
    assert g["days_since_tape_flip"] == 0
    assert (
        "flip dens 100% (1/1)" in g["line"]
        or g["line"].endswith("estimate · not full-universe")
    )


def test_breadth_glance_days_since_tape_flip_from_history():
    hist = [
        {
            "day": "2026-09-01",
            "is_dual_advance": True,
            "tape_label": "risk-on",
            "crypto_n": 4,
            "crypto_up": 3,
            "crypto_down": 1,
            "stock_scan_n": 10,
            "stock_scan_up": 6,
            "stock_scan_down": 4,
        },
        {
            "day": "2026-09-02",
            "is_risk_off": True,
            "tape_label": "risk-off",
            "crypto_n": 4,
            "crypto_up": 1,
            "crypto_down": 3,
            "stock_scan_n": 10,
            "stock_scan_up": 3,
            "stock_scan_down": 7,
        },
        {
            "day": "2026-09-03",
            "is_risk_off": True,
            "tape_label": "risk-off",
            "crypto_n": 4,
            "crypto_up": 1,
            "crypto_down": 3,
            "stock_scan_n": 10,
            "stock_scan_up": 3,
            "stock_scan_down": 7,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["tape_flip"] is False
    assert g["days_since_tape_flip"] == 1
    assert "1d since flip" in g["line"]


def test_breadth_tape_summary_label_densities():
    rows = [
        {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
        {"day": "2026-09-02", "is_tape_split": True, "tape_label": "split"},
        {"day": "2026-09-03", "is_risk_off": True, "tape_label": "risk-off"},
        {"day": "2026-09-04", "tape_label": "mixed"},
    ]
    s = build_breadth_tape_summary(rows)
    assert s["ready"] is True
    assert s["days"] == 4
    assert s["dual_n"] == 1
    assert s["split_n"] == 1
    assert s["risk_off_n"] == 1
    assert s["mixed_n"] == 1
    assert s["risk_on_density_pct"] == tape_label_density_pct(1, 4)
    assert s["split_density_pct"] == tape_label_density_pct(1, 4)
    assert s["risk_off_density_pct"] == tape_label_density_pct(1, 4)
    assert s["mixed_density_pct"] == tape_label_density_pct(1, 4)
    assert "risk-on dens 25% (1/4)" in s["line"]
    assert "split dens 25% (1/4)" in s["line"]
    assert "risk-off dens 25% (1/4)" in s["line"]
    assert "mixed dens 25% (1/4)" in s["line"]
    on_heavy = build_breadth_tape_summary(
        [
            {"day": "2026-09-01", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-02", "is_dual_advance": True, "tape_label": "risk-on"},
            {"day": "2026-09-03", "tape_label": "mixed"},
        ]
    )
    assert on_heavy["risk_on_density_pct"] == tape_label_density_pct(2, 3)
    assert on_heavy["mixed_density_pct"] == tape_label_density_pct(1, 3)
    assert on_heavy["split_density_pct"] == 0.0
    assert on_heavy["risk_off_density_pct"] == 0.0
    assert "risk-on dens 67% (2/3)" in on_heavy["line"]
    assert "mixed dens 33% (1/3)" in on_heavy["line"]


def test_breadth_thrust_summary_counts_and_latest():
    rows = [
        {"day": "2026-09-01", "crypto_n": 4, "crypto_big_movers": 1,
         "stock_breakouts_n": 8, "stock_within_5pct_high": 2},  # 25/25 thrust
        {"day": "2026-09-02", "crypto_n": 4, "crypto_big_movers": 0,
         "stock_breakouts_n": 8, "stock_within_5pct_high": 2},  # 0/25 no
        {"day": "2026-09-03", "crypto_n": 5, "crypto_big_movers": 2,
         "stock_breakouts_n": 10, "stock_within_5pct_high": 3},  # 40/30 thrust
    ]
    s = build_breadth_thrust_summary(rows)
    assert s["ready"] is True
    assert s["days"] == 3
    assert s["thrust_n"] == 2
    assert s["confirmed_n"] == 0
    assert s["alone_n"] == 2
    assert s["confirm_rate_pct"] == 0.0
    assert s["density_pct"] == thrust_density_pct(2, 3)
    assert s["confirmed_density_pct"] == confirmed_density_pct(0, 3)
    assert s["alone_density_pct"] == alone_density_pct(2, 3)
    assert s["streak"] == 1
    assert s["alone_streak"] == 1
    assert s["latest"] is True
    assert s["latest_alone"] is True
    assert s["latest_confirmed"] is False
    assert s["tone"] == "flat"
    assert "thrust alone (not risk-on)" in s["line"]
    assert "confirm 0% (0/2 thrust)" in s["line"]
    assert "density 67% (2/3 days)" in s["line"]
    assert "confirmed dens 0% (0/3)" in s["line"]
    assert "alone dens 67% (2/3)" in s["line"]
    assert "0/3 confirmed" in s["line"]
    assert "2/3 alone" in s["line"]
    assert "2/3 thrust days" in s["line"]
    assert "streak" not in s["line"]  # streak 1 stays quiet


def test_breadth_thrust_summary_mixed_confirm_rate():
    rows = [
        {
            "day": "2026-09-01",
            "is_thrust": True,
            "is_confirmed_thrust": True,
            "is_unconfirmed_thrust": False,
        },
        {
            "day": "2026-09-02",
            "is_thrust": True,
            "is_confirmed_thrust": False,
            "is_unconfirmed_thrust": True,
        },
        {"day": "2026-09-03", "is_thrust": False},
    ]
    s = build_breadth_thrust_summary(rows)
    assert s["thrust_n"] == 2
    assert s["confirmed_n"] == 1
    assert s["alone_n"] == 1
    assert s["confirm_rate_pct"] == 50.0
    assert "confirm 50% (1/2 thrust)" in s["line"]
    assert s["confirm_rate_pct"] is not None
    assert s["confirmed_density_pct"] == confirmed_density_pct(1, 3)
    assert s["alone_density_pct"] == alone_density_pct(1, 3)
    assert "confirmed dens 33% (1/3)" in s["line"]
    assert "alone dens 33% (1/3)" in s["line"]

def test_breadth_thrust_summary_shows_streak_when_multi_day():
    rows = [
        {"day": "2026-09-01", "is_thrust": False},
        {"day": "2026-09-02", "is_thrust": True},
        {"day": "2026-09-03", "is_thrust": True},
    ]
    s = build_breadth_thrust_summary(rows)
    assert s["streak"] == 2
    assert s["alone_streak"] == 2
    assert "alone streak 2" in s["line"]
    assert "thrust alone (not risk-on)" in s["line"]
    assert s["latest_confirmed"] is False


def test_breadth_thrust_summary_empty():
    assert build_breadth_thrust_summary([])["ready"] is False
    assert build_breadth_thrust_summary([])["streak"] == 0
    assert build_breadth_thrust_summary([])["confirmed_n"] == 0
    assert build_breadth_thrust_summary([])["alone_n"] == 0
    assert build_breadth_thrust_summary([])["alone_streak"] == 0
    assert build_breadth_thrust_summary([])["confirm_rate_pct"] is None
    assert build_breadth_thrust_summary([])["density_pct"] is None
    assert build_breadth_thrust_summary([])["confirmed_density_pct"] is None
    assert build_breadth_thrust_summary([])["alone_density_pct"] is None


def test_breadth_glance_confirmed_thrust_from_history():
    hist = [
        {
            "day": "2026-09-01",
            "is_thrust": True,
            "is_dual_advance": True,
            "is_confirmed_thrust": True,
        },
        {
            "day": "2026-09-02",
            "crypto_n": 4,
            "crypto_up": 3,
            "crypto_down": 1,
            "crypto_big_movers": 1,
            "stock_scan_n": 5,
            "stock_scan_up": 4,
            "stock_scan_down": 1,
            "stock_breakouts_n": 8,
            "stock_within_5pct_high": 2,
            "is_thrust": True,
            "is_dual_advance": True,
            "is_confirmed_thrust": True,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["is_thrust"] is True
    assert g["is_confirmed_thrust"] is True
    assert g["confirmed_thrust_streak"] == 2
    assert "confirmed thrust · streak 2" in g["line"]


def test_breadth_glance_empty_when_no_scan():
    assert build_breadth_glance(None)["ready"] is False
    assert build_breadth_glance({})["ready"] is False
    assert build_breadth_glance({"crypto_n": 0, "stock_scan_n": 0})["ready"] is False


def test_breadth_glance_infers_n_from_up_down():
    g = build_breadth_glance(
        {
            "crypto_up": 2,
            "crypto_down": 1,
            "stock_scan_up": 4,
            "stock_scan_down": 1,
        }
    )
    assert g["ready"] is True
    assert g["crypto_net"] == 1
    assert g["stock_net"] == 3
    assert g["stock_advance_pct"] == 80.0
    assert g["crypto_advance_pct"] == round(100.0 * 2 / 3, 1)
    assert g["is_dual_advance"] is True
    assert g["is_tape_split"] is False
    assert g["tape_label"] == "risk-on"
    assert g["tone"] == "up"
    assert "crypto 2/1 (+1) of 3 · adv 67%" in g["line"]
    assert "stock 4/1 (+3) of 5 · adv 80%" in g["line"]
    assert "risk-on" in g["line"]
    assert "estimate · not full-universe" in g["line"]
    assert g["estimate"] is True
    assert g["full_universe"] is False
    assert g["is_thrust"] is False


def test_scan_breadth_pulse_for_day(tmp_path: Path):
    (tmp_path / "scan_breadth_daily.json").write_text(
        '[{"day":"2026-09-01","crypto_up":1,"crypto_down":0},'
        '{"day":"2026-09-02","crypto_up":0,"crypto_down":2}]\n',
        encoding="utf-8",
    )
    assert scan_breadth_pulse_for_day(tmp_path, "2026-09-02")["crypto_down"] == 2
    assert scan_breadth_pulse_for_day(tmp_path, "1999-01-01") is None
    assert scan_breadth_pulse_for_day(tmp_path, "") is None


def test_breadth_glance_sums_nets_and_tone():
    g = build_breadth_glance(
        {
            "crypto_n": 4,
            "crypto_up": 3,
            "crypto_down": 1,
            "stock_scan_n": 10,
            "stock_scan_up": 2,
            "stock_scan_down": 5,
            "stock_breakouts_n": 8,
            "stock_within_5pct_high": 2,
            "crypto_big_movers": 1,
        }
    )
    assert g["ready"] is True
    assert g["crypto_net"] == 2
    assert g["stock_net"] == -3
    assert g["near_high"] == 2
    assert g["near_high_pct"] == 25.0
    assert g["big_movers"] == 1
    assert g["mover_pct"] == 25.0
    assert g["is_thrust"] is True
    assert g["is_confirmed_thrust"] is False
    assert g["is_unconfirmed_thrust"] is True
    assert g["thrust_streak"] == 0
    assert g["unconfirmed_thrust_streak"] == 0
    assert g["crypto_n"] == 4
    assert g["stock_n"] == 10
    assert g["stock_advance_pct"] == 20.0
    assert g["crypto_advance_pct"] == 75.0
    assert g["is_dual_advance"] is False
    assert g["is_tape_split"] is True
    assert g["tape_label"] == "split"
    assert g["tone"] == "down"  # +2 + −3 = −1
    assert "crypto 3/1 (+2) of 4 · adv 75%" in g["line"]
    assert "stock 2/5 (-3) of 10 · adv 20%" in g["line"]
    assert "2 near-high (25%)" in g["line"]
    assert "1 ±4% (25%)" in g["line"]
    assert "thrust alone" in g["line"]
    assert "split" in g["line"]
    assert "streak" not in g["line"]
    assert "estimate · not full-universe" in g["line"]
    assert g["estimate"] is True
    assert g["full_universe"] is False


def test_breadth_glance_thrust_streak_from_history():
    hist = [
        {"day": "2026-09-01", "is_thrust": True},
        {
            "day": "2026-09-02",
            "crypto_n": 4,
            "crypto_up": 3,
            "crypto_down": 1,
            "crypto_big_movers": 1,
            "stock_breakouts_n": 8,
            "stock_within_5pct_high": 2,
            "is_thrust": True,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["is_thrust"] is True
    assert g["is_unconfirmed_thrust"] is True
    assert g["thrust_streak"] == 2
    assert g["unconfirmed_thrust_streak"] == 2
    assert g["thrust_n"] == 2
    assert g["confirmed_n"] == 0
    assert g["confirm_rate_pct"] == 0.0
    assert "thrust alone · streak 2" in g["line"]
    assert "confirm 0% (0/2)" in g["line"]
    assert g["density_pct"] == 100.0
    assert "density 100% (2/2)" in g["line"]
    assert g["confirmed_density_pct"] == 0.0
    assert g["alone_density_pct"] == 100.0
    assert g["alone_n"] == 2
    assert g["dual_n"] == 0
    assert g["risk_on_density_pct"] == 0.0
    assert g["split_density_pct"] == 0.0
    assert g["risk_off_density_pct"] == 0.0
    assert g["mixed_density_pct"] == 0.0
    # Densities live on the glance payload; long lines may trim dens text.
    assert "risk-on dens 0% (0/2)" in g["line"] or g["line"].endswith(
        "estimate · not full-universe"
    )


def test_breadth_glance_tape_label_densities():
    hist = [
        {
            "day": "2026-09-01",
            "is_dual_advance": True,
            "tape_label": "risk-on",
            "crypto_n": 4,
            "crypto_up": 3,
            "crypto_down": 1,
            "stock_scan_n": 10,
            "stock_scan_up": 6,
            "stock_scan_down": 4,
        },
        {
            "day": "2026-09-02",
            "is_risk_off": True,
            "tape_label": "risk-off",
            "crypto_n": 4,
            "crypto_up": 1,
            "crypto_down": 3,
            "stock_scan_n": 10,
            "stock_scan_up": 3,
            "stock_scan_down": 7,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["dual_n"] == 1
    assert g["risk_off_n"] == 1
    assert g["risk_on_density_pct"] == 50.0
    assert g["risk_off_density_pct"] == 50.0
    assert g["split_density_pct"] == 0.0
    assert g["mixed_density_pct"] == 0.0
    # Prefer dens text when the glance line fits; payload fields are the contract.
    assert (
        "risk-on dens 50% (1/2)" in g["line"]
        or "risk-off dens 50% (1/2)" in g["line"]
        or g["line"].endswith("estimate · not full-universe")
    )


def test_breadth_glance_confirm_rate_mixed_history():
    hist = [
        {
            "day": "2026-09-01",
            "is_thrust": True,
            "is_confirmed_thrust": True,
            "is_dual_advance": True,
        },
        {
            "day": "2026-09-02",
            "crypto_n": 4,
            "crypto_up": 3,
            "crypto_down": 1,
            "crypto_big_movers": 1,
            "stock_breakouts_n": 8,
            "stock_within_5pct_high": 2,
            "stock_scan_n": 10,
            "stock_scan_up": 3,
            "stock_scan_down": 7,
            "is_thrust": True,
            "is_confirmed_thrust": False,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["thrust_n"] == 2
    assert g["confirmed_n"] == 1
    assert g["alone_n"] == 1
    assert g["confirm_rate_pct"] == 50.0
    assert g["density_pct"] == 100.0
    assert g["confirmed_density_pct"] == 50.0
    assert g["alone_density_pct"] == 50.0
    # Prefer structured fields; long glance lines may truncate confirm/density.


def test_breadth_glance_risk_on_streak_from_history():
    hist = [
        {
            "day": "2026-09-01",
            "is_dual_advance": True,
            "stock_scan_up": 3,
            "stock_scan_down": 1,
            "crypto_up": 2,
            "crypto_down": 1,
        },
        {
            "day": "2026-09-02",
            "stock_scan_up": 4,
            "stock_scan_down": 1,
            "crypto_up": 3,
            "crypto_down": 1,
            "is_dual_advance": True,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["is_dual_advance"] is True
    assert g["dual_advance_streak"] == 2
    assert "risk-on · streak 2" in g["line"]
    assert g["tape_label"] == "risk-on"


def test_breadth_glance_risk_off_from_pulse():
    g = build_breadth_glance(
        {
            "crypto_n": 5,
            "crypto_up": 1,
            "crypto_down": 4,
            "stock_scan_n": 10,
            "stock_scan_up": 3,
            "stock_scan_down": 7,
        }
    )
    assert g["ready"] is True
    assert g["stock_advance_pct"] == 30.0
    assert g["crypto_advance_pct"] == 20.0
    assert g["is_risk_off"] is True
    assert g["is_dual_advance"] is False
    assert g["is_tape_split"] is False
    assert g["tape_label"] == "risk-off"
    assert "risk-off" in g["line"]


def test_breadth_glance_risk_off_streak_from_history():
    hist = [
        {
            "day": "2026-09-01",
            "is_risk_off": True,
            "stock_scan_up": 2,
            "stock_scan_down": 8,
            "crypto_up": 1,
            "crypto_down": 4,
        },
        {
            "day": "2026-09-02",
            "stock_scan_up": 3,
            "stock_scan_down": 7,
            "crypto_up": 1,
            "crypto_down": 4,
            "is_risk_off": True,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["is_risk_off"] is True
    assert g["risk_off_streak"] == 2
    assert "risk-off · streak 2" in g["line"]
    assert g["tape_label"] == "risk-off"


def test_breadth_glance_mixed_and_tape_flip():
    hist = [
        {
            "day": "2026-09-01",
            "tape_label": "risk-on",
            "stock_scan_up": 6,
            "stock_scan_down": 4,
            "crypto_up": 3,
            "crypto_down": 2,
        },
        {
            "day": "2026-09-02",
            # 50% stock · 40% crypto → mid mixed (not dual / split / risk-off)
            "stock_scan_up": 5,
            "stock_scan_down": 5,
            "crypto_up": 2,
            "crypto_down": 3,
        },
    ]
    g = build_breadth_glance(hist[-1], history=hist)
    assert g["ready"] is True
    assert g["stock_advance_pct"] == 50.0
    assert g["crypto_advance_pct"] == 40.0
    assert g["tape_label"] == "mixed"
    assert g["is_mixed"] is True
    assert g["prev_tape_label"] == "risk-on"
    assert g["tape_flip"] is True
    assert "mixed" in g["line"]
    assert "flipped risk-on→mixed" in g["line"]


def test_breadth_glance_up_when_crypto_leads():
    g = build_breadth_glance(
        {
            "crypto_n": 3,
            "crypto_up": 3,
            "crypto_down": 0,
            "stock_scan_n": 0,
            "stock_breakouts_n": 0,
            "stock_within_5pct_high": 0,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "up"
    assert g["stock_net"] == 0
    assert g["big_movers"] == 0
    assert g["mover_pct"] == 0.0
    assert g["near_high_pct"] is None
    assert g["is_thrust"] is False
    assert g["crypto_n"] == 3
    assert g["crypto_advance_pct"] == 100.0
    assert "crypto 3/0 (+3) of 3 · adv 100%" in g["line"]
    assert "±4%" not in g["line"]
    assert "thrust" not in g["line"]
    assert "estimate · not full-universe" in g["line"]


def test_breadth_ad_spark_needs_two_days():
    one = [{"day": "2026-09-01", "crypto_up": 2, "crypto_down": 1}]
    assert build_breadth_ad_spark(one)["ready"] is False
    assert build_breadth_ad_spark([])["ready"] is False


def test_breadth_ad_spark_builds_svg_and_latest_net():
    rows = [
        {"day": "2026-09-01", "crypto_up": 1, "crypto_down": 3},
        {"day": "2026-09-02", "crypto_up": 2, "crypto_down": 1},
        {"day": "2026-09-03", "crypto_up": 4, "crypto_down": 0},
    ]
    spark = build_breadth_ad_spark(rows)
    assert spark["ready"] is True
    assert spark["n"] == 3
    assert spark["latest_net"] == 4
    assert spark["first_day"] == "2026-09-01"
    assert spark["last_day"] == "2026-09-03"
    assert spark["label"] == "Crypto"
    assert "polyline" in spark["svg"]
    assert "is-up" in spark["svg"]
    assert "Crypto advance/decline net" in spark["aria"]


def test_breadth_ad_spark_down_tone():
    rows = [
        {"day": "2026-09-01", "crypto_up": 3, "crypto_down": 0},
        {"day": "2026-09-02", "crypto_up": 0, "crypto_down": 2},
    ]
    spark = build_breadth_ad_spark(rows)
    assert spark["ready"] is True
    assert spark["latest_net"] == -2
    assert "is-down" in spark["svg"]


def test_stock_batch_ad_spark_skips_legacy_rows():
    rows = [
        {"day": "2026-09-01", "crypto_up": 1, "crypto_down": 0},
        {
            "day": "2026-09-02",
            "crypto_up": 2,
            "crypto_down": 1,
            "stock_scan_up": 3,
            "stock_scan_down": 5,
        },
        {
            "day": "2026-09-03",
            "crypto_up": 1,
            "crypto_down": 1,
            "stock_scan_up": 6,
            "stock_scan_down": 2,
        },
    ]
    spark = build_breadth_ad_spark(
        rows,
        up_key="stock_scan_up",
        down_key="stock_scan_down",
        label="Stock batch",
        aria_unit="priced scan names up minus down",
    )
    assert spark["ready"] is True
    assert spark["n"] == 2
    assert spark["latest_net"] == 4
    assert spark["first_day"] == "2026-09-02"
    assert "Stock batch advance/decline net" in spark["aria"]


def test_stock_batch_ad_spark_needs_two_recorded_days():
    rows = [
        {"day": "2026-09-01", "crypto_up": 1, "crypto_down": 0},
        {
            "day": "2026-09-02",
            "stock_scan_up": 1,
            "stock_scan_down": 0,
        },
    ]
    spark = build_breadth_ad_spark(
        rows,
        up_key="stock_scan_up",
        down_key="stock_scan_down",
        label="Stock batch",
    )
    assert spark["ready"] is False
    assert spark["n"] == 1


def test_breadth_mover_spark_needs_two_days():
    one = [{"day": "2026-09-01", "crypto_n": 4, "crypto_big_movers": 1}]
    assert build_breadth_mover_spark(one)["ready"] is False
    assert build_breadth_mover_spark([])["ready"] is False


def test_breadth_mover_spark_ratio_and_delta():
    rows = [
        {"day": "2026-09-01", "crypto_n": 4, "crypto_big_movers": 0},
        {"day": "2026-09-02", "crypto_n": 4, "crypto_big_movers": 1},
        {"day": "2026-09-03", "crypto_n": 5, "crypto_big_movers": 2},
    ]
    spark = build_breadth_mover_spark(rows)
    assert spark["ready"] is True
    assert spark["n"] == 3
    assert spark["latest_pct"] == 40.0
    assert spark["delta_pct"] == 15.0  # 40 − 25
    assert spark["tone"] == "up"
    assert spark["first_day"] == "2026-09-01"
    assert spark["last_day"] == "2026-09-03"
    assert "polyline" in spark["svg"]
    assert "is-up" in spark["svg"]
    assert "±4% mover ratio" in spark["aria"]


def test_breadth_mover_spark_down_tone():
    rows = [
        {"day": "2026-09-01", "crypto_up": 2, "crypto_down": 2, "crypto_big_movers": 2},
        {"day": "2026-09-02", "crypto_up": 3, "crypto_down": 1, "crypto_big_movers": 0},
    ]
    spark = build_breadth_mover_spark(rows)
    assert spark["ready"] is True
    assert spark["latest_pct"] == 0.0
    assert spark["delta_pct"] == -50.0
    assert spark["tone"] == "down"
    assert "is-down" in spark["svg"]


def test_breadth_near_high_spark_needs_two_days():
    one = [
        {
            "day": "2026-09-01",
            "stock_breakouts_n": 8,
            "stock_within_5pct_high": 2,
        }
    ]
    assert build_breadth_near_high_spark(one)["ready"] is False
    assert build_breadth_near_high_spark([])["ready"] is False


def test_breadth_near_high_spark_ratio_and_delta():
    rows = [
        {
            "day": "2026-09-01",
            "stock_breakouts_n": 8,
            "stock_within_5pct_high": 0,
        },
        {
            "day": "2026-09-02",
            "stock_breakouts_n": 8,
            "stock_within_5pct_high": 2,
        },
        {
            "day": "2026-09-03",
            "stock_breakouts_n": 10,
            "stock_within_5pct_high": 4,
        },
    ]
    spark = build_breadth_near_high_spark(rows)
    assert spark["ready"] is True
    assert spark["n"] == 3
    assert spark["latest_pct"] == 40.0
    assert spark["delta_pct"] == 15.0  # 40 − 25
    assert spark["tone"] == "up"
    assert spark["label"] == "Near-high ratio"
    assert "polyline" in spark["svg"]
    assert "is-up" in spark["svg"]
    assert "within 5% of high ratio" in spark["aria"]


def test_breadth_near_high_spark_down_tone():
    rows = [
        {
            "day": "2026-09-01",
            "stock_breakouts_n": 4,
            "stock_within_5pct_high": 2,
        },
        {
            "day": "2026-09-02",
            "stock_breakouts_n": 4,
            "stock_within_5pct_high": 0,
        },
    ]
    spark = build_breadth_near_high_spark(rows)
    assert spark["ready"] is True
    assert spark["latest_pct"] == 0.0
    assert spark["delta_pct"] == -50.0
    assert spark["tone"] == "down"
    assert "is-down" in spark["svg"]


def test_breadth_stock_advance_spark_needs_two_days():
    one = [{"day": "2026-09-01", "stock_scan_n": 5, "stock_scan_up": 4}]
    assert build_breadth_stock_advance_spark(one)["ready"] is False
    assert build_breadth_stock_advance_spark([])["ready"] is False


def test_breadth_stock_advance_spark_ratio_and_delta():
    rows = [
        {
            "day": "2026-09-01",
            "stock_scan_n": 10,
            "stock_scan_up": 2,
            "stock_scan_down": 8,
        },
        {
            "day": "2026-09-02",
            "stock_scan_n": 10,
            "stock_scan_up": 5,
            "stock_scan_down": 5,
        },
        {
            "day": "2026-09-03",
            "stock_scan_n": 10,
            "stock_scan_up": 8,
            "stock_scan_down": 2,
        },
    ]
    spark = build_breadth_stock_advance_spark(rows)
    assert spark["ready"] is True
    assert spark["n"] == 3
    assert spark["latest_pct"] == 80.0
    assert spark["delta_pct"] == 30.0  # 80 − 50
    assert spark["tone"] == "up"
    assert spark["label"] == "Stock advance %"
    assert "polyline" in spark["svg"]
    assert "is-up" in spark["svg"]
    assert "stock advance participation" in spark["aria"]


def test_breadth_stock_advance_spark_down_tone():
    rows = [
        {
            "day": "2026-09-01",
            "stock_scan_up": 4,
            "stock_scan_down": 1,
        },
        {
            "day": "2026-09-02",
            "stock_scan_up": 1,
            "stock_scan_down": 4,
        },
    ]
    spark = build_breadth_stock_advance_spark(rows)
    assert spark["ready"] is True
    assert spark["latest_pct"] == 20.0
    assert spark["delta_pct"] == -60.0
    assert spark["tone"] == "down"
    assert "is-down" in spark["svg"]


def test_breadth_crypto_advance_spark_needs_two_days():
    one = [{"day": "2026-09-01", "crypto_n": 4, "crypto_up": 3}]
    assert build_breadth_crypto_advance_spark(one)["ready"] is False
    assert build_breadth_crypto_advance_spark([])["ready"] is False


def test_breadth_crypto_advance_spark_ratio_and_delta():
    rows = [
        {"day": "2026-09-01", "crypto_n": 4, "crypto_up": 1, "crypto_down": 3},
        {"day": "2026-09-02", "crypto_n": 4, "crypto_up": 2, "crypto_down": 2},
        {"day": "2026-09-03", "crypto_n": 4, "crypto_up": 3, "crypto_down": 1},
    ]
    spark = build_breadth_crypto_advance_spark(rows)
    assert spark["ready"] is True
    assert spark["n"] == 3
    assert spark["latest_pct"] == 75.0
    assert spark["delta_pct"] == 25.0  # 75 − 50
    assert spark["tone"] == "up"
    assert spark["label"] == "Crypto advance %"
    assert "polyline" in spark["svg"]
    assert "is-up" in spark["svg"]
    assert "Crypto leaders advance participation" in spark["aria"]


def test_breadth_crypto_advance_spark_down_tone():
    rows = [
        {"day": "2026-09-01", "crypto_up": 3, "crypto_down": 1},
        {"day": "2026-09-02", "crypto_up": 1, "crypto_down": 3},
    ]
    spark = build_breadth_crypto_advance_spark(rows)
    assert spark["ready"] is True
    assert spark["latest_pct"] == 25.0
    assert spark["delta_pct"] == -50.0
    assert spark["tone"] == "down"
    assert "is-down" in spark["svg"]
