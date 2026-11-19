"""tradermonty #700/#655/#812: decision-sample meters refuse bool invent."""

from __future__ import annotations

from openbb_backend.desk import _decision_sample_gap, _decision_sample_lead


def test_decision_sample_lead_refuses_bool_buckets() -> None:
    # True→1 would invent lead pass · 1 · 100% on a damaged ring.
    bit, name, share, margin, gap, sides, sides_name, sides_n, sides_share = (
        _decision_sample_lead([("pass", True), ("hold", False)])
    )
    assert bit == ""
    assert name == ""
    assert share is None
    assert margin == ""
    assert gap is None
    assert sides == ""
    assert sides_name == ""
    assert sides_n is None
    assert sides_share is None

    # Real counts still speak.
    bit, name, share, *_rest = _decision_sample_lead(
        [("BUY", 2), ("HOLD", 1)]
    )
    assert bit == "lead BUY · 2 · 67%"
    assert name == "BUY"
    assert share == 67


def test_decision_sample_gap_refuses_bool_total() -> None:
    assert _decision_sample_gap(True, "") == ""
    assert _decision_sample_gap(False, "") == ""
    assert _decision_sample_gap(1, "") == "n=1"
    assert _decision_sample_gap(2, "") == "tied"
    assert _decision_sample_gap(2, "BUY") == ""
