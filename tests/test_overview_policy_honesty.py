"""Overview collapses long policy glances (MonsterDeveloper simplicity)."""

from __future__ import annotations

from pathlib import Path


def test_overview_policy_honesty_details() -> None:
    root = Path(__file__).resolve().parents[1] / "openbb_backend" / "templates"
    text = (root / "desk_overview.html").read_text(encoding="utf-8")
    assert 'class="policy-honesty"' in text
    assert 'id="policy-honesty"' in text
    open_idx = text.index('class="policy-honesty"')
    close_idx = text.index("</details>", open_idx)
    body = text[open_idx:close_idx]
    above = text[:open_idx]
    # Keep live decision context above the fold.
    for needle in (
        "entry_gates_glance(",
        "calm_streak_glance(",
        "promote_ab_glance(",
        "book_posture_glance(",
        "book_risk_glance(",
    ):
        assert needle in above, needle
    # Nested policy lines live inside the disclosure.
    for needle in (
        "crypto_policy_glance(",
        "gate_params_glance(",
        "fee_burn_glance(",
        "postmortem_glance(",
    ):
        assert needle in body, needle


def test_policy_honesty_css() -> None:
    css = (
        Path(__file__).resolve().parents[1]
        / "openbb_backend"
        / "static"
        / "desk.css"
    ).read_text(encoding="utf-8")
    assert ".policy-honesty" in css
    assert ".policy-honesty > summary" in css
