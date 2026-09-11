"""Offline tests for Breadth multi-day A/D sparklines (display only)."""

from pathlib import Path

from openbb_backend.desk import (
    build_breadth_ad_spark,
    build_breadth_glance,
    scan_breadth_pulse_for_day,
)


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
    assert g["tone"] == "up"
    assert "crypto 2/1 (+1) of 3" in g["line"]
    assert "stock 4/1 (+3) of 5" in g["line"]
    assert "estimate · not full-universe" in g["line"]
    assert g["estimate"] is True
    assert g["full_universe"] is False


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
            "stock_breakouts_n": 3,
            "stock_within_5pct_high": 2,
            "crypto_big_movers": 1,
        }
    )
    assert g["ready"] is True
    assert g["crypto_net"] == 2
    assert g["stock_net"] == -3
    assert g["near_high"] == 2
    assert g["big_movers"] == 1
    assert g["crypto_n"] == 4
    assert g["stock_n"] == 10
    assert g["tone"] == "down"  # +2 + −3 = −1
    assert "crypto 3/1 (+2) of 4" in g["line"]
    assert "stock 2/5 (-3) of 10" in g["line"]
    assert "2 near-high" in g["line"]
    assert "1 ±4% movers" in g["line"]
    assert "estimate · not full-universe" in g["line"]
    assert g["estimate"] is True
    assert g["full_universe"] is False


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
    assert g["crypto_n"] == 3
    assert "crypto 3/0 (+3) of 3" in g["line"]
    assert "±4% movers" not in g["line"]
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
