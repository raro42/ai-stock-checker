"""Desk screens collapse long policy glances (MonsterDeveloper simplicity)."""

from __future__ import annotations

from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "openbb_backend" / "templates"

POLICY_HONESTY_SCREENS = (
    "desk_overview.html",
    "desk_screener.html",
    "desk_ideas.html",
    "desk_book.html",
    "desk_breadth.html",
    "desk_ops.html",
    "desk_scan_log.html",
)

ABOVE_FOLD = (
    "entry_gates_glance(",
    "calm_streak_glance(",
    "promote_ab_glance(",
    "book_posture_glance(",
)

INSIDE_DETAILS = (
    "crypto_policy_glance(",
    "gate_params_glance(",
    "fee_burn_glance(",
    "postmortem_glance(",
)


def test_policy_honesty_details_on_desk_screens() -> None:
    for name in POLICY_HONESTY_SCREENS:
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert 'class="policy-honesty"' in text, name
        assert 'id="policy-honesty"' in text, name
        open_idx = text.index('class="policy-honesty"')
        close_idx = text.index("</details>", open_idx)
        body = text[open_idx:close_idx]
        above = text[:open_idx]
        for needle in ABOVE_FOLD:
            assert needle in above, f"{name}: {needle} should stay above fold"
            assert needle not in body, f"{name}: {needle} must not be inside details"
        if "{{ book_risk_glance(" in text:
            assert "{{ book_risk_glance(" in above, name
            assert "{{ book_risk_glance(" not in body, name
        for needle in INSIDE_DETAILS:
            assert needle in body, f"{name}: {needle} should be inside details"


def test_policy_honesty_css() -> None:
    css = (
        Path(__file__).resolve().parents[1]
        / "openbb_backend"
        / "static"
        / "desk.css"
    ).read_text(encoding="utf-8")
    assert ".policy-honesty" in css
    assert ".policy-honesty > summary" in css


def test_charts_js_policy_honesty_parity() -> None:
    """Charts (JS) must match HTML screens: collapse long policy wall."""
    js = (
        Path(__file__).resolve().parents[1]
        / "openbb_backend"
        / "static"
        / "charts.js"
    ).read_text(encoding="utf-8")
    assert 'className = "policy-honesty"' in js
    assert 'id = "policy-honesty"' in js
    assert "function appendGlance" in js
    page = js[js.index("function renderChartsPage") :]
    # Above-fold: gates / calm / promote A/B / posture / risk before details.
    for name in (
        "renderEntryGatesGlance",
        "renderCalmStreakGlance",
        "renderPromoteAbGlance",
        "renderBookPostureGlance",
        "renderBookRiskGlance",
    ):
        assert name in page[: page.index("policy-honesty")], name
    details_idx = page.index("policy-honesty")
    after = page[details_idx:]
    for name in (
        "renderCryptoPolicyGlance",
        "renderGateParamsGlance",
        "renderFeeBurnGlance",
        "renderPostmortemGlance",
    ):
        assert name in after, name
    # Breadth stays after the disclosure (with the chart mounts).
    assert after.index("glanceMount = null") < after.index("renderBreadthGlance")
