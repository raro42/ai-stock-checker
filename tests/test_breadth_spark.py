"""Offline tests for Breadth multi-day A/D sparklines (display only)."""

from openbb_backend.desk import build_breadth_ad_spark


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
