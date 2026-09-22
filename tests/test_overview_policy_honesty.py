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


def test_promote_honesty_fold_in_macro_and_charts() -> None:
    """Close-stat bits sit under details. The short A/B line stays the decision."""
    macro = (TEMPLATES / "macros.html").read_text(encoding="utf-8")
    assert 'class="promote-honesty"' in macro
    assert "glance.summary_line or glance.line" in macro
    assert "glance.honesty_line" in macro
    css = (
        Path(__file__).resolve().parents[1] / "openbb_backend" / "static" / "desk.css"
    ).read_text(encoding="utf-8")
    assert ".promote-honesty" in css
    js = (
        Path(__file__).resolve().parents[1] / "openbb_backend" / "static" / "charts.js"
    ).read_text(encoding="utf-8")
    assert "glance.summary_line || glance.line" in js
    assert 'details.className = "promote-honesty"' in js
    assert "promote-kelly" in macro
    assert "promote-streaks" in macro
    assert "promote-edge" in macro
    assert "promote-exit-mix" in macro
    assert "promote-fees" in macro
    assert "promote-polarity" in macro
    assert "glance.kelly_line" in macro
    assert "glance.streak_line" in macro
    assert "glance.edge_line" in macro
    assert "glance.exit_mix_line" in macro
    assert "glance.fees_line" in macro
    assert "glance.polarity_line" in macro
    assert "glance.align_nest_line" in macro
    assert ".promote-kelly" in css
    assert ".promote-streaks" in css
    assert ".promote-edge" in css
    assert ".promote-exit-mix" in css
    assert ".promote-fees" in css
    assert ".promote-polarity" in css
    assert ".promote-align-nest" in css
    assert "promote-kelly" in js
    assert "promote-streaks" in js
    assert "promote-edge" in js
    assert "promote-exit-mix" in js
    assert "promote-fees" in js
    assert "promote-polarity" in js
    assert "promote-align-nest" in js
    assert "glance.honesty_warns" in macro
    assert "glance.honesty_warns" in js
    assert "{% if warns %} open{% endif %}" in macro
    assert "details.open = warns.length > 0" in js
    # Hot child folds open with the parent (MonsterDeveloper + xang1234).
    assert "{% if 'fees' in warns %} open{% endif %}" in macro
    assert "{% if 'fee pressure' in warns %} open{% endif %}" in macro
    assert "{% if 'align nest' in warns %} open{% endif %}" in macro
    assert "fold.open = hot" in js
    assert ".promote-honesty.warn" in css
