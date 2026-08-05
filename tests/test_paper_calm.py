"""Offline tests for paper calm streak tracker."""

from pathlib import Path

from stock_checker.paper_calm import (
    CALM_DAYS_REQUIRED,
    evaluate_calm_day,
    load_paper_calm,
    upsert_calm_day,
)


def test_evaluate_calm_requires_promote_and_book_fit(tmp_path: Path):
    ok, why = evaluate_calm_day(
        promote_on=False,
        holdings_count=3,
        max_positions=5,
        data_dir=tmp_path,
    )
    assert not ok
    assert "promote" in why.lower()

    ok2, why2 = evaluate_calm_day(
        promote_on=True,
        holdings_count=8,
        max_positions=5,
        data_dir=tmp_path,
    )
    assert not ok2
    assert "overweight" in why2


def test_upsert_builds_streak(tmp_path: Path):
    # Seed a fake portfolio without fee burn
    (tmp_path / "portfolio.json").write_text(
        '{"initial_cash": 100000, "total_fees_paid": 10, "cash": 50000, "holdings": {}}'
    )
    for i, day in enumerate(["2026-07-01", "2026-07-02", "2026-07-03"]):
        snap = upsert_calm_day(
            tmp_path,
            promote_on=True,
            holdings_count=3,
            max_positions=5,
            day=day,
        )
        assert snap["streak_days"] == i + 1
        assert snap["ready_for_compose_default"] is False

    # Break streak with overweight
    broken = upsert_calm_day(
        tmp_path,
        promote_on=True,
        holdings_count=9,
        max_positions=5,
        day="2026-07-04",
    )
    assert broken["streak_days"] == 0
    assert broken["ready_for_compose_default"] is False

    loaded = load_paper_calm(tmp_path)
    assert len(loaded["days"]) == 4
    assert CALM_DAYS_REQUIRED == 30
