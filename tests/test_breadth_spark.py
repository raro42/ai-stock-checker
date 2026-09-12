"""Offline tests for Breadth multi-day A/D sparklines (display only)."""

from pathlib import Path

from openbb_backend.desk import (
    breadth_days_since_mixed,
    breadth_days_since_risk_off,
    breadth_days_since_risk_on,
    breadth_days_since_tape_split,
    breadth_days_since_thrust,
    breadth_dual_advance_streak,
    breadth_mixed_streak,
    breadth_prev_tape_label,
    breadth_risk_off_streak,
    breadth_tape_label,
    breadth_tape_split_streak,
    breadth_thrust_streak,
    build_breadth_ad_spark,
    build_breadth_crypto_advance_spark,
    build_breadth_glance,
    build_breadth_mover_spark,
    build_breadth_near_high_spark,
    build_breadth_stock_advance_spark,
    build_breadth_tape_summary,
    build_breadth_thrust_summary,
    crypto_advance_ratio_pct,
    crypto_mover_ratio_pct,
    is_breadth_thrust_day,
    is_dual_advance_day,
    is_risk_off_day,
    is_tape_flip,
    is_tape_split_day,
    near_high_ratio_pct,
    scan_breadth_pulse_for_day,
    stock_advance_ratio_pct,
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
    assert s["days_since"] == 2
    assert "2d since thrust" in s["line"]
    assert "1/3 thrust days" in s["line"]


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
    assert g["days_since_thrust"] == 1
    assert g["days_since_risk_on"] == 1
    assert "1d since thrust" in g["line"]
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
    assert s["streak"] == 1
    assert s["latest"] is True
    assert s["tone"] == "up"
    assert "thrust now" in s["line"]
    assert "2/3 thrust days" in s["line"]
    assert "streak" not in s["line"]  # streak 1 stays quiet


def test_breadth_thrust_summary_shows_streak_when_multi_day():
    rows = [
        {"day": "2026-09-01", "is_thrust": False},
        {"day": "2026-09-02", "is_thrust": True},
        {"day": "2026-09-03", "is_thrust": True},
    ]
    s = build_breadth_thrust_summary(rows)
    assert s["streak"] == 2
    assert "streak 2" in s["line"]
    assert "thrust now" in s["line"]


def test_breadth_thrust_summary_empty():
    assert build_breadth_thrust_summary([])["ready"] is False
    assert build_breadth_thrust_summary([])["streak"] == 0


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
    assert g["thrust_streak"] == 0
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
    assert "thrust" in g["line"]
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
    assert g["thrust_streak"] == 2
    assert "thrust · streak 2" in g["line"]


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
