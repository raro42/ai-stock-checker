"""Offline tests for Breadth multi-day A/D sparklines (display only)."""

from pathlib import Path

from openbb_backend.desk import (
    breadth_thrust_streak,
    build_breadth_ad_spark,
    build_breadth_glance,
    build_breadth_mover_spark,
    build_breadth_near_high_spark,
    build_breadth_stock_advance_spark,
    build_breadth_thrust_summary,
    crypto_mover_ratio_pct,
    is_breadth_thrust_day,
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


def test_is_breadth_thrust_day():
    assert is_breadth_thrust_day(25.0, 25.0) is True
    assert is_breadth_thrust_day(40.0, 30.0) is True
    assert is_breadth_thrust_day(24.9, 50.0) is False
    assert is_breadth_thrust_day(50.0, 24.9) is False
    assert is_breadth_thrust_day(None, 50.0) is False
    assert is_breadth_thrust_day(50.0, None) is False


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
    assert g["tone"] == "up"
    assert "crypto 2/1 (+1) of 3" in g["line"]
    assert "stock 4/1 (+3) of 5 · adv 80%" in g["line"]
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
    assert g["tone"] == "down"  # +2 + −3 = −1
    assert "crypto 3/1 (+2) of 4" in g["line"]
    assert "stock 2/5 (-3) of 10 · adv 20%" in g["line"]
    assert "2 near-high (25%)" in g["line"]
    assert "1 ±4% (25%)" in g["line"]
    assert "thrust" in g["line"]
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
    assert "crypto 3/0 (+3) of 3" in g["line"]
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
