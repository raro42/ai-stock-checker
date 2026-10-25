"""Fail-open soft-allow glance (display only)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from openbb_backend.desk import build_soft_allow_glance, soft_allow_lean_meta
from stock_checker.gate_audit import (
    soft_allow_last_lead_vs_config,
    soft_allow_last_lead_vs_config_freshness,
    soft_allow_last_vs_lead,
    soft_allow_last_vs_lead_freshness,
    soft_allow_lead_vs_config,
    soft_allow_lead_vs_config_freshness,
)


def test_soft_allow_last_vs_lead_helper() -> None:
    assert soft_allow_last_vs_lead("rs", "breadth") == "last vs lead · breadth"
    assert soft_allow_last_vs_lead("rs", "RS") == "agree"
    assert soft_allow_last_vs_lead("", "breadth") == ""
    assert soft_allow_last_vs_lead("rs", "") == ""


def test_soft_allow_lead_vs_config_helper() -> None:
    """tradermonty #576 same-run: lead ring vs Ops toggle clash|agree."""
    assert soft_allow_lead_vs_config("rs", None) == ""
    assert soft_allow_lead_vs_config("rs", {}) == ""
    assert (
        soft_allow_lead_vs_config("rs", {"rs_gate": True})
        == "agree · lead rs · RS on"
    )
    assert (
        soft_allow_lead_vs_config(
            "rs", {"rs_gate": True}, lead_count=2, lead_share_pct=66.7
        )
        == "agree · lead rs · ×2 · 67% · RS on"
    )
    assert (
        soft_allow_lead_vs_config("rs", {"rs_gate": False})
        == "clash · lead rs · RS off"
    )
    assert (
        soft_allow_lead_vs_config(
            "rs", {"rs_gate": False}, lead_count=2, lead_share_pct=66.7
        )
        == "clash · lead rs · ×2 · 67% · RS off"
    )
    assert (
        soft_allow_lead_vs_config("regime", {"regime_gate": False})
        == "clash · lead regime · regime off"
    )
    assert (
        soft_allow_lead_vs_config("regime", {"regime_gate": True})
        == "agree · lead regime · regime on"
    )
    assert soft_allow_lead_vs_config("earnings", {"rs_gate": False}) == ""


def test_soft_allow_last_lead_vs_config_helper() -> None:
    """last≠lead vs lead↔Ops — share/lean meta polarity."""
    assert soft_allow_last_lead_vs_config("", "agree · lead rs · RS on") == (
        "",
        False,
    )
    assert soft_allow_last_lead_vs_config("agree · last rs · lead rs", "") == (
        "",
        False,
    )
    assert soft_allow_last_lead_vs_config(
        "agree · last rs · lead rs", "agree · lead rs · RS on"
    ) == ("last/config align · both agree", False)
    assert soft_allow_last_lead_vs_config(
        "last vs lead · breadth", "clash · lead rs · RS off"
    ) == ("last/config align · both clash", True)
    assert soft_allow_last_lead_vs_config(
        "agree · last rs · lead rs", "clash · lead rs · RS off"
    ) == ("last/config clash · last agree · config clash", True)
    assert soft_allow_last_lead_vs_config(
        "last vs lead · breadth", "agree · lead rs · RS on"
    ) == ("last/config clash · last clash · config agree", True)
    assert soft_allow_last_lead_vs_config(
        "agree · last rs · lead rs",
        "agree · lead rs · ×2 · 67% · RS on",
        lead_count=2,
        lead_share_pct=66.7,
    ) == ("last/config align · both agree · ×2 · 67%", False)
    assert soft_allow_last_lead_vs_config(
        "last vs lead · breadth",
        "clash · lead rs · ×2 · 67% · RS off",
        lead_count=2,
        lead_share_pct=66.7,
    ) == ("last/config align · both clash · ×2 · 67%", True)


def test_soft_allow_last_vs_lead_freshness_helper() -> None:
    """Gate last≠lead vs newest age — gap last/lead freshness parity."""
    assert soft_allow_last_vs_lead_freshness("", "fresh") == ("", False)
    assert soft_allow_last_vs_lead_freshness(
        "agree · last rs · lead rs", "aging"
    ) == ("", False)
    assert soft_allow_last_vs_lead_freshness(
        "agree · last rs · lead rs", "fresh"
    ) == ("last/lead align · fresh · agree", False)
    assert soft_allow_last_vs_lead_freshness(
        "last vs lead · breadth", "expired"
    ) == ("last/lead align · expired · vs breadth", False)
    assert soft_allow_last_vs_lead_freshness(
        "agree · last rs · lead rs", "expired"
    ) == ("last/lead clash · expired · agree", True)
    assert soft_allow_last_vs_lead_freshness(
        "last vs lead · breadth", "fresh"
    ) == ("last/lead clash · fresh · vs breadth", True)
    assert soft_allow_last_vs_lead_freshness(
        "agree · last rs · lead rs",
        "fresh",
        lead_count=2,
        lead_share_pct=66.7,
    ) == ("last/lead align · fresh · agree · ×2 · 67%", False)


def test_soft_allow_lead_vs_config_freshness_helper() -> None:
    """Lead↔Ops vs newest age — last/lead freshness parity."""
    assert soft_allow_lead_vs_config_freshness("", "fresh") == ("", False)
    assert soft_allow_lead_vs_config_freshness(
        "agree · lead rs · RS on", "aging"
    ) == ("", False)
    assert soft_allow_lead_vs_config_freshness(
        "agree · lead rs · RS on", "fresh"
    ) == ("lead/config align · fresh · on", False)
    assert soft_allow_lead_vs_config_freshness(
        "clash · lead rs · RS off", "expired"
    ) == ("lead/config align · expired · off", False)
    assert soft_allow_lead_vs_config_freshness(
        "agree · lead rs · RS on", "expired"
    ) == ("lead/config clash · expired · on", True)
    assert soft_allow_lead_vs_config_freshness(
        "clash · lead rs · RS off", "fresh"
    ) == ("lead/config clash · fresh · off", True)
    assert soft_allow_lead_vs_config_freshness(
        "agree · lead rs · ×2 · 67% · RS on",
        "expired",
        lead_count=2,
        lead_share_pct=100,
    ) == ("lead/config clash · expired · on · ×2 · 100%", True)


def test_soft_allow_last_lead_vs_config_freshness_helper() -> None:
    """Age↔gate vs age↔Ops — share/lean meta polarity."""
    assert soft_allow_last_lead_vs_config_freshness(
        "", "lead/config align · fresh · on"
    ) == ("", False)
    assert soft_allow_last_lead_vs_config_freshness(
        "last/lead align · fresh · agree", ""
    ) == ("", False)
    assert soft_allow_last_lead_vs_config_freshness(
        "last/lead align · fresh · agree",
        "lead/config align · fresh · on",
    ) == ("last/config age align · both align · fresh", False)
    assert soft_allow_last_lead_vs_config_freshness(
        "last/lead clash · expired · agree",
        "lead/config clash · expired · on",
    ) == ("last/config age align · both clash · expired", True)
    assert soft_allow_last_lead_vs_config_freshness(
        "last/lead align · fresh · agree",
        "lead/config clash · fresh · off",
    ) == (
        "last/config age clash · last/lead align · lead/config clash · fresh",
        True,
    )
    assert soft_allow_last_lead_vs_config_freshness(
        "last/lead clash · fresh · vs breadth",
        "lead/config align · fresh · on",
    ) == (
        "last/config age clash · last/lead clash · lead/config align · fresh",
        True,
    )
    assert soft_allow_last_lead_vs_config_freshness(
        "last/lead align · fresh · agree",
        "lead/config align · expired · on",
    ) == ("last/config age align · both align · mixed", False)
    assert soft_allow_last_lead_vs_config_freshness(
        "last/lead align · fresh · agree · ×2 · 67%",
        "lead/config align · fresh · on · ×2 · 67%",
        lead_count=2,
        lead_share_pct=66.7,
    ) == ("last/config age align · both align · fresh · ×2 · 67%", False)


def test_soft_allow_lean_meta_names_spoken_sleeves() -> None:
    """Quiet chip names gen/gap sleeves; hot appends stages after clash|hot."""
    assert soft_allow_lean_meta("") == "quiet"
    # lead↔Ops toggle (tradermonty #576) — gate + on|off ride with the stage.
    assert (
        soft_allow_lean_meta("agree · lead rs · RS on")
        == "quiet · 1 fold · lead/config rs on"
    )
    assert (
        soft_allow_lean_meta("agree · lead rs · ×2 · 67% · RS on")
        == "quiet · 1 fold · lead/config rs ×2 67% on"
    )
    assert (
        soft_allow_lean_meta("clash · lead rs · ×2 · 67% · RS off", warn=True)
        == "clash · lead/config rs ×2 67% off"
    )
    assert (
        soft_allow_lean_meta("clash · lead rs · RS off", warn=True)
        == "clash · lead/config rs off"
    )
    assert (
        soft_allow_lean_meta(
            "clash · lead rs · RS off · clash · scan stale",
            warn=True,
        )
        == "clash · lead/config rs off · scan"
    )
    # Newest print vs band lead (FinRobot last≠tilt) — gate rides.
    assert (
        soft_allow_lean_meta("agree · last rs · lead rs")
        == "quiet · 1 fold · last/lead rs"
    )
    assert (
        soft_allow_lean_meta("last vs lead · breadth", warn=True)
        == "clash · last/lead breadth"
    )
    assert (
        soft_allow_lean_meta(
            "agree · last rs · lead rs · ×2 · 67%"
        )
        == "quiet · 1 fold · last/lead rs ×2 67%"
    )
    assert (
        soft_allow_lean_meta(
            "last vs lead · breadth · ×2 · 67%", warn=True
        )
        == "clash · last/lead breadth ×2 67%"
    )
    assert (
        soft_allow_lean_meta(
            "agree · lead rs · RS on · agree · last rs · lead rs"
        )
        == "quiet · 2 folds · lead/config rs on · last/lead rs"
    )
    assert (
        soft_allow_lean_meta(
            "agree · lead rs · RS on · agree · last rs · lead rs · "
            "last/config align · both agree · ×2 · 67%"
        )
        == (
            "quiet · 3 folds · lead/config rs on · last/lead rs · "
            "last/config align both agree ×2 67%"
        )
    )
    # Gate last/lead age (gap freshness parity) — verb + age + agree|vs.
    assert (
        soft_allow_lean_meta(
            "agree · last rs · lead rs · last/lead align · fresh · agree"
        )
        == (
            "quiet · 2 folds · last/lead rs · "
            "last/lead align fresh agree"
        )
    )
    assert (
        soft_allow_lean_meta(
            "agree · last rs · lead rs · "
            "last/lead clash · expired · agree",
            warn=True,
        )
        == (
            "clash · last/lead rs · last/lead clash expired agree"
        )
    )
    # Lead↔Ops age (#576 + last/lead freshness parity) — on|off rides.
    assert (
        soft_allow_lean_meta(
            "agree · lead rs · RS on · lead/config align · fresh · on"
        )
        == (
            "quiet · 2 folds · lead/config rs on · "
            "lead/config align fresh on"
        )
    )
    assert (
        soft_allow_lean_meta(
            "agree · lead rs · RS on · "
            "lead/config clash · expired · on",
            warn=True,
        )
        == (
            "clash · lead/config rs on · lead/config clash expired on"
        )
    )
    assert (
        soft_allow_lean_meta(
            "clash · lead rs · RS off · last vs lead · breadth · "
            "last/config align · both clash",
            warn=True,
        )
        == (
            "clash · last/config align both clash · lead/config rs off · "
            "last/lead breadth"
        )
    )
    assert (
        soft_allow_lean_meta(
            "agree · lead rs · RS on · last vs lead · breadth · "
            "last/config clash · last clash · config agree",
            warn=True,
        )
        == (
            "clash · lead/config rs on · last/lead breadth · "
            "last/config clash last clash config agree"
        )
    )
    assert (
        soft_allow_lean_meta(
            "last vs lead · breadth · clash · scan stale",
            warn=True,
        )
        == "clash · last/lead breadth · scan"
    )
    assert soft_allow_lean_meta("clash · scan fresh") == "quiet · 1 fold · scan"
    assert (
        soft_allow_lean_meta(
            "clash · scan fresh · clash · soft fresh · gap expired · "
            "2 gap · last AAPL · fresh"
        )
        == "quiet · 3 folds · scan · soft/gap · gap AAPL fresh"
    )
    # gap↔scan / cash / memory were silent on the chip (N gap alone ≠ generation).
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · scan fresh · gap-only · scan-only"
        )
        == "quiet · 1 fold · gap/scan gap-only scan-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · scan fresh · gap-only · scan-only · US-only"
        )
        == "quiet · 1 fold · gap/scan gap-only scan-only US-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · scan fresh · gap-only · scan-only · "
            "soft-only · short-only"
        )
        == "quiet · 1 fold · gap/scan gap-only scan-only soft-only short-only"
    )
    # Keep-memory after keep-short on gap≠scan (gap≡memory; pin order
    # soft·short·memory).
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · scan fresh · gap-only · scan-only · "
            "soft-only · short-only · debate-only"
        )
        == (
            "quiet · 1 fold · gap/scan gap-only scan-only soft-only "
            "short-only debate-only"
        )
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · scan fresh · gap-only"
        )
        == "quiet · 1 fold · gap/scan gap-only"
    )
    assert (
        soft_allow_lean_meta("clash · gap aging · cash stale")
        == "quiet · 1 fold · gap/cash"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · cash aging · gap-only · US · 50%"
        )
        == "quiet · 1 fold · gap/cash gap-only US 50%"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · cash aging · gap-only · US-only"
        )
        == "quiet · 1 fold · gap/cash gap-only US-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · cash aging · gap-only · US-only · scan-only"
        )
        == "quiet · 1 fold · gap/cash gap-only US-only scan-only"
    )
    # Keep-memory after keep-short on gap≠cash (gap≡memory).
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · cash aging · gap-only · US-only · "
            "scan-only · soft-only · short-only · debate-only"
        )
        == (
            "quiet · 1 fold · gap/cash gap-only US-only scan-only "
            "soft-only short-only debate-only"
        )
    )
    # Short≠gap generation clock (soft≠gap parity; count lean ≠ clock).
    assert (
        soft_allow_lean_meta("clash · short expired · gap fresh")
        == "quiet · 1 fold · short/gap"
    )
    assert (
        soft_allow_lean_meta(
            "clash · short expired · gap fresh · short-only · gap-only"
            " · scan-only · US-only"
        )
        == "quiet · 1 fold · short/gap short-only gap-only scan-only US-only"
    )
    # Short sole pins + keep-scan / keep-cash on the lean chip (gap parity).
    assert (
        soft_allow_lean_meta(
            "clash · short fresh · cash aging · short-only · US-only"
            " · scan-only"
        )
        == "quiet · 1 fold · short/cash short-only US-only scan-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · short fresh · laya stale · debate aging · "
            "short-only · ×2 · 100% · scan-only · US-only"
        )
        == "quiet · 1 fold · short/memory short-only ×2 100% scan-only US-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · short expired · scan fresh · short-only · scan-only"
            " · US-only · laya-only"
        )
        == "quiet · 1 fold · short/scan short-only scan-only US-only laya-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · cash aging · gap-only · ×2 · 100%"
        )
        == "quiet · 1 fold · gap/cash gap-only ×2 100%"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · laya fresh · debate fresh · "
            "gap-only · ×2 · 100%"
        )
        == "quiet · 1 fold · gap/memory gap-only ×2 100%"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · laya fresh · debate fresh · "
            "gap-only · ×2 · 100% · scan-only"
        )
        == "quiet · 1 fold · gap/memory gap-only ×2 100% scan-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · debate stale · gap-only · debate-only · "
            "US-only"
        )
        == "quiet · 1 fold · gap/memory gap-only debate-only US-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · debate stale · gap-only · debate-only"
        )
        == "quiet · 1 fold · gap/memory gap-only debate-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · gap expired · laya fresh · gap-only · laya · 50%"
        )
        == "quiet · 1 fold · gap/memory gap-only laya 50%"
    )
    assert (
        soft_allow_lean_meta(
            "2 gap · last AAPL · fresh · clash · gap expired · scan stale",
            warn=True,
        )
        == "clash · gap AAPL fresh · gap/scan"
    )
    # soft≠gap must not greedily eat a later gap↔scan on the same lean line.
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · gap expired · 2 gap · last AAPL · fresh · "
            "clash · gap expired · scan stale"
        )
        == "quiet · 3 folds · soft/gap · gap AAPL fresh · gap/scan"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · gap expired · soft-only · gap-only"
        )
        == "quiet · 1 fold · soft/gap soft-only gap-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · gap expired · soft-only · gap-only · scan-only"
        )
        == "quiet · 1 fold · soft/gap soft-only gap-only scan-only"
    )
    # Keep-cash + keep-memory + keep-short on soft≠gap (soft≡cash +
    # soft≡memory + soft≡short) — cash/memory pins after scan-only.
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · gap expired · soft-only · gap-only · "
            "scan-only · US-only · debate-only · short-only"
        )
        == (
            "quiet · 1 fold · soft/gap soft-only gap-only scan-only "
            "US-only debate-only short-only"
        )
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · gap expired · gap-only"
        )
        == "quiet · 1 fold · soft/gap gap-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · short expired · soft-only · short-only"
        )
        == "quiet · 1 fold · soft/short soft-only short-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · short expired · soft-only · short-only · "
            "scan-only"
        )
        == "quiet · 1 fold · soft/short soft-only short-only scan-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · cash aging · soft-only · US-only"
        )
        == "quiet · 1 fold · soft/cash soft-only US-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · cash aging · soft-only · US-only · scan-only"
        )
        == "quiet · 1 fold · soft/cash soft-only US-only scan-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · cash aging · soft-only · US-only · "
            "scan-only · gap-only"
        )
        == "quiet · 1 fold · soft/cash soft-only US-only scan-only gap-only"
    )
    # Keep-memory + keep-short on soft≠cash (soft≡memory + soft≡short).
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · cash aging · soft-only · US-only · "
            "gap-only · debate-only · short-only"
        )
        == (
            "quiet · 1 fold · soft/cash soft-only US-only gap-only "
            "debate-only short-only"
        )
    )
    assert (
        soft_allow_lean_meta(
            "clash · scan fresh · soft-only · scan-only · US-only · gap-only"
        )
        == "quiet · 1 fold · scan soft-only scan-only US-only gap-only"
    )
    # Keep-memory + keep-short on soft≠scan must fold (soft≡memory +
    # soft≡short; debate-only is not cash/gap grammar).
    assert (
        soft_allow_lean_meta(
            "clash · scan fresh · soft-only · scan-only · debate-only · "
            "short-only"
        )
        == (
            "quiet · 1 fold · scan soft-only scan-only debate-only "
            "short-only"
        )
    )
    assert (
        soft_allow_lean_meta(
            "clash · scan fresh · soft-only · scan-only · gap-only · "
            "laya · 50% · short-only"
        )
        == (
            "quiet · 1 fold · scan soft-only scan-only gap-only laya 50% "
            "short-only"
        )
    )
    assert (
        soft_allow_lean_meta(
            "clash · debate stale · soft-only · debate-only · US-only · "
            "gap-only"
        )
        == "quiet · 1 fold · memory soft-only debate-only US-only gap-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · cash aging · US-only"
        )
        == "quiet · 1 fold · soft/cash US-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · cash aging · soft-only · Xetra · 50%"
        )
        == "quiet · 1 fold · soft/cash soft-only Xetra 50%"
    )
    assert (
        soft_allow_lean_meta(
            "clash · soft fresh · cash aging · ×2 · 100%"
        )
        == "quiet · 1 fold · soft/cash ×2 100%"
    )
    assert (
        soft_allow_lean_meta(
            "clash · scan fresh · soft-only · scan-only"
        )
        == "quiet · 1 fold · scan soft-only scan-only"
    )
    assert (
        soft_allow_lean_meta("clash · scan fresh · scan-only")
        == "quiet · 1 fold · scan scan-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · debate stale · soft-only · debate-only"
        )
        == "quiet · 1 fold · memory soft-only debate-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · debate stale · soft-only · debate-only · scan-only"
        )
        == "quiet · 1 fold · memory soft-only debate-only scan-only"
    )
    assert (
        soft_allow_lean_meta(
            "clash · laya stale · debate aging · soft-only · ×2 · 100%"
        )
        == "quiet · 1 fold · memory soft-only ×2 100%"
    )
    assert (
        soft_allow_lean_meta(
            "clash · laya stale · debate aging · ×2 · 100%"
        )
        == "quiet · 1 fold · memory ×2 100%"
    )
    assert (
        soft_allow_lean_meta("clash · debate stale · debate-only")
        == "quiet · 1 fold · memory debate-only"
    )
    assert (
        soft_allow_lean_meta("clash · laya stale · laya · 50%")
        == "quiet · 1 fold · memory laya 50%"
    )
    assert (
        soft_allow_lean_meta("clash · scan stale", warn=True)
        == "clash · scan"
    )
    assert (
        soft_allow_lean_meta(
            "2 gap · last AAPL · fresh · hot · 66.7%", warn=True
        )
        == "hot · gap AAPL fresh hot 66.7%"
    )
    # Bare N gap hid age↔share / gap-vs-other / share↔lean on the chip.
    assert (
        soft_allow_lean_meta(
            "2 gap · last AAPL · fresh · hot · 66.7% · "
            "last/share clash · expired · hot · "
            "vs 1 other · thin · 33.3% · "
            "gap vs other clash · gap hot · other ok · "
            "last/lean clash · expired · gap hot · other ok · "
            "share/lean clash · share clash · lean clash"
        )
        == (
            "quiet · 5 folds · gap AAPL fresh hot 66.7% · "
            "last/share clash expired hot vs 1 other thin 33.3% · "
            "gap/other clash gap hot · other ok · "
            "last/lean clash expired gap hot · other ok · +1"
        )
    )
    assert (
        soft_allow_lean_meta(
            "2 gap · last AAPL · fresh · hot · 66.7% · "
            "last/share clash · expired · hot · "
            "gap vs other clash · gap hot · other ok",
            warn=True,
        )
        == (
            "clash · gap AAPL fresh hot 66.7% · last/share clash expired hot · "
            "gap/other clash gap hot · other ok"
        )
    )
    assert (
        soft_allow_lean_meta(
            "2 gap · last MSFT · expired · lead MSFT · 2 · 60% · agree · "
            "last/lead clash · expired · agree · "
            "last/share clash · expired · hot · "
            "lead/share clash · lead clash · share align"
        )
        == (
            "quiet · 5 folds · gap MSFT expired · lead MSFT 2 60% agree · "
            "last/lead clash expired agree · last/share clash expired hot · +1"
        )
    )
    # Cursor name ≠ sample: tied / sole / other owner stay on the chip.
    assert (
        soft_allow_lean_meta("1 gap · last AAPL · fresh · n=1")
        == "quiet · 2 folds · gap AAPL fresh · n=1"
    )
    assert (
        soft_allow_lean_meta("2 gap · last AAPL · fresh · tied · hot · 50%")
        == "quiet · 2 folds · gap AAPL fresh · tied hot 50%"
    )
    assert (
        soft_allow_lean_meta(
            "3 gap · last MSFT · fresh · lead AAPL · 2 · 67% · "
            "last vs lead · MSFT"
        )
        == "quiet · 2 folds · gap MSFT fresh · lead AAPL 2 67% vs lead · MSFT"
    )
    # Owner % alone hid margin and the #2 name. Sole 100% stays silent.
    assert (
        soft_allow_lean_meta(
            "3 gap · last MSFT · fresh · lead AAPL · 2 · 67% · "
            "last vs lead · MSFT · ahead thin · +1 · vs MSFT · 1 · 33%"
        )
        == (
            "quiet · 3 folds · gap MSFT fresh · "
            "lead AAPL 2 67% vs lead · MSFT · ahead thin +1 vs MSFT 1 33%"
        )
    )
    assert (
        soft_allow_lean_meta(
            "4 gap · last MSFT · fresh · lead AAPL · 3 · 75% · "
            "last vs lead · MSFT · ahead wide · +2 · vs MSFT · 1 · 25%",
            warn=True,
        )
        == (
            "warn · gap MSFT fresh · lead AAPL 3 75% vs lead · MSFT · "
            "ahead wide +2 vs MSFT 1 25%"
        )
    )
    assert (
        soft_allow_lean_meta(
            "2 gap · last AAPL · fresh · lead AAPL · 2 · 100% · agree"
        )
        == "quiet · 2 folds · gap AAPL fresh · lead AAPL 2 100% agree"
    )


def test_soft_allow_glance_empty() -> None:
    assert build_soft_allow_glance(None)["ready"] is False
    assert build_soft_allow_glance([])["ready"] is False
    empty = build_soft_allow_glance(None)
    assert empty["line_core"] == ""
    assert empty["soft_lean"] == ""
    assert empty["soft_lean_warn"] is False
    assert empty["soft_lean_meta"] == "quiet"


def test_soft_allow_glance_one() -> None:
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-09-23T11:00:00Z",
                "gate": "regime",
                "reason": "unknown — no SPY bars",
            }
        ],
        now=now,
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["severity"] == "hot"
    assert g["count"] == 1
    assert g["fresh_count"] == 1
    assert g["aging_count"] == 0
    assert g["expired_count"] == 0
    assert g["aging_hours"] == 12.0
    assert g["last_gate"] == "regime"
    assert g["anchor_gap_count"] == 0
    assert g["anchor_gap_last"] == ""
    assert g["anchor_gap_symbol_lead"] == ""
    assert g["anchor_gap_symbol_lead_name"] == ""
    assert g["anchor_gap_symbol_lead_share"] is None
    assert g["anchor_gap_symbol_lead_margin"] is None
    assert g["anchor_gap_symbol_lead_margin_severity"] == ""
    assert g["anchor_gap_symbol_lead_margin_bit"] == ""
    assert g["anchor_gap_symbol_lead_runner"] == ""
    assert g["anchor_gap_symbol_lead_runner_count"] == 0
    assert g["anchor_gap_symbol_lead_runner_share"] is None
    assert g["anchor_gap_symbol_lead_sides"] == ""
    assert g["anchor_gap_symbol_last_vs_lead"] == ""
    assert g["anchor_gap_last_vs_lead_freshness"] == ""
    assert g["anchor_gap_last_vs_lead_freshness_warn"] is False
    assert g["anchor_gap_symbol_sample_gap"] == ""
    assert g["anchor_gap_share_pct"] is None
    assert g["anchor_gap_share_severity"] == ""
    assert g["anchor_gap_last_vs_share"] == ""
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_last_lead_vs_share"] == ""
    assert g["anchor_gap_last_lead_vs_share_warn"] is False
    assert g["anchor_gap_other_count"] == 0
    assert g["anchor_gap_other_share_pct"] is None
    assert g["anchor_gap_other_share_severity"] == ""
    assert g["anchor_gap_vs_other"] == ""
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == ""
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_lead_vs_lean"] == ""
    assert g["anchor_gap_last_lead_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == ""
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    assert g["anchor_gap_vs_scan_clash"] == ""
    assert g["anchor_gap_vs_scan_clash_warn"] is False
    assert g["anchor_gap_vs_cash_clock_clash"] == ""
    assert g["anchor_gap_vs_cash_clock_clash_warn"] is False
    assert g["anchor_gap_vs_memory_clock_clash"] == ""
    assert g["anchor_gap_vs_memory_clock_clash_warn"] is False
    assert g["soft_vs_gap_clock_clash"] == ""
    assert g["soft_vs_gap_clock_clash_warn"] is False
    assert g["soft_vs_cash_clock_clash"] == ""
    assert g["soft_vs_cash_clock_clash_warn"] is False
    assert g["soft_vs_memory_clock_clash"] == ""
    assert g["soft_vs_memory_clock_clash_warn"] is False
    assert g["short_history_vs_scan_clash"] == ""
    assert g["short_history_vs_scan_clash_warn"] is False
    assert g["short_history_vs_cash_clock_clash"] == ""
    assert g["short_history_vs_cash_clock_clash_warn"] is False
    assert g["short_history_vs_memory_clock_clash"] == ""
    assert g["short_history_vs_memory_clock_clash_warn"] is False
    assert g["laya_freshness"] == ""
    assert g["debate_freshness"] == ""
    assert g["anchor_gap_bit"] == ""
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == ""
    assert g["scan_vs_soft_allow_clash"] == ""
    assert g["line"].startswith("hot · ")
    assert "1 recent soft-allow" in g["line"]
    assert "[regime]" in g["line"]
    assert "no SPY bars" in g["line"]
    assert " gap" not in g["line"]
    assert "clash" not in g["line"]
    assert g["line_core"] == g["line"]
    assert g["soft_lean"] == ""
    assert g["soft_lean_warn"] is False
    assert g["soft_lean_meta"] == "quiet"


def test_soft_allow_glance_short_history_count() -> None:
    """xang1234 #668: rs×N alone ≠ young/short-series fail-open count."""
    now = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-21T11:00:00Z",
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
            {
                "at": "2026-10-21T10:30:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-21T10:00:00Z",
                "gate": "rs",
                "reason": "NEW RS unknown — short history — allow",
            },
        ],
        now=now,
    )
    assert g["ready"] is True
    assert g["short_history_count"] == 2
    assert g["short_history_bench_count"] == 0
    assert g["short_history_last"] == "IPO"
    assert g["short_history_last_freshness"] == "fresh"
    # Two distinct short names → no strict lead (gap sample-gap parity).
    assert g["short_history_symbol_lead"] == ""
    assert g["short_history_symbol_sample_gap"] == "tied"
    assert g["short_history_symbol_last_vs_lead"] == ""
    # Absolute N short · N gap ≠ pair ownership (1÷3 = 33% thin).
    # Short owns 67% (hot) → short vs gap align · hot|thin.
    assert g["short_history_vs_gap"] == "vs gap · thin · 1 · 33%"
    assert g["short_history_vs_gap_count"] == 1
    assert g["short_history_vs_gap_share"] == 33
    assert g["short_history_vs_gap_severity"] == "thin"
    assert g["short_history_pair_share"] == 67
    assert g["short_history_pair_severity"] == "hot"
    # Short÷ring (2/3) ≠ short÷pair (2/3 of short+gap) — ring share speaks.
    assert g["short_history_share_pct"] == 66.7
    assert g["short_history_share_severity"] == "hot"
    assert g["short_history_vs_gap_lean"] == "align · hot|thin"
    assert g["short_history_vs_gap_lean_warn"] is False
    # Lean alone hid how far short÷pair sits (67−33=+34pp wide).
    assert g["short_history_vs_gap_delta_pp"] == 34.0
    assert g["short_history_vs_gap_delta_severity"] == "wide"
    assert g["short_history_vs_gap_lean_vs_delta"] == "align · wide"
    assert g["short_history_vs_gap_lean_vs_delta_warn"] is True
    # Signed +34pp hid that short owns the pair spread (unique/Yahoo Δ lead).
    assert g["short_history_vs_gap_delta_lead"] == "short"
    # Fresh + pair share hot → last/share align (gap last/share parity).
    assert g["short_history_last_vs_share"] == "align · fresh · hot"
    assert g["short_history_last_vs_share_warn"] is False
    # Fresh + short/gap align → last/lean align (gap last/lean parity).
    assert g["short_history_last_vs_lean"] == "align · fresh · hot|thin"
    assert g["short_history_last_vs_lean_warn"] is False
    # last/share + last/lean same verb → share/lean both align (gap share/lean).
    assert g["short_history_last_share_vs_lean"] == "align · both align"
    assert g["short_history_last_share_vs_lean_warn"] is False
    assert g["short_history_last_vs_ring_share"] == "align · fresh · hot"
    assert g["short_history_last_vs_ring_share_warn"] is False
    assert g["short_history_last_share_vs_ring"] == "align · both align"
    assert g["short_history_last_share_vs_ring_warn"] is False
    assert g["short_history_last_ring_vs_lean"] == "align · both align"
    assert g["short_history_last_ring_vs_lean_warn"] is False
    assert g["short_history_bit"] == (
        "2 short · last IPO · fresh · tied · hot · 66.7% · "
        "short last/ring align · fresh · hot · "
        "vs gap · thin · 1 · 33% · "
        "short last/share align · fresh · hot · "
        "short share/ring align · both align · "
        "short vs gap align · hot|thin · "
        "short Δ wide · +34pp · short lean/Δ align · wide · short Δ lead · short · "
        "short last/lean align · fresh · hot|thin · "
        "short share/lean align · both align · "
        "short ring/lean align · both align"
    )
    assert "vs gap · thin · 1 · 33%" in g["line"]
    assert "short last/share align · fresh · hot" in g["line"]
    assert "short share/ring align · both align" in g["line"]
    assert "short vs gap align · hot|thin" in g["line"]
    assert "short Δ wide · +34pp" in g["line"]
    assert "short lean/Δ align · wide · short Δ lead · short" in g["line"]
    assert "short Δ lead · short" in g["line"]
    assert "short last/lean align · fresh · hot|thin" in g["line"]
    assert "short share/lean align · both align" in g["line"]
    assert "short ring/lean align · both align" in g["line"]
    assert g["anchor_gap_count"] == 1
    # Short before gap so the young-listing count is not clipped by gap lean.
    assert g["line"].index("2 short") < g["line"].index("1 gap")
    # Lean fold chip must name short — ``2 short · …`` used to leave
    # soft_lean_meta bare ``quiet`` because only ``N gap`` had a stage.
    # Cursor ticker + age ride on the short stage (#546 + gap freshness
    # parity); tied is its own stage so last ≠ ring ownership is visible
    # on the chip. ``vs gap`` + ``short last/share`` + ``short/gap`` +
    # ``short last/lean`` + ``short share/lean`` + ``short ring/lean``
    # must match or the inventory stalls. Gap still owns soft_lean; the
    # 4-name meta clip may spill it to +N when short + tied + vs gap +
    # short last/share + short/gap already fill it.
    assert "2 short · last IPO · fresh" in g["soft_lean"]
    assert "tied" in g["soft_lean"]
    assert "vs gap · thin · 1 · 33%" in g["soft_lean"]
    assert "short last/share align · fresh · hot" in g["soft_lean"]
    assert "short share/ring align · both align" in g["soft_lean"]
    assert "short vs gap align · hot|thin" in g["soft_lean"]
    assert "short Δ wide · +34pp" in g["soft_lean"]
    assert "short lean/Δ align · wide · short Δ lead · short" in g["soft_lean"]
    assert "short last/lean align · fresh · hot|thin" in g["soft_lean"]
    assert "short share/lean align · both align" in g["soft_lean"]
    assert "short ring/lean align · both align" in g["soft_lean"]
    assert "1 gap" in g["soft_lean"]
    assert "short IPO fresh" in g["soft_lean_meta"]
    assert "tied" in g["soft_lean_meta"]
    assert soft_allow_lean_meta("2 short") == "quiet · 1 fold · short"
    assert soft_allow_lean_meta("2 short · last IPO") == (
        "quiet · 1 fold · short IPO"
    )
    assert soft_allow_lean_meta("2 short · last IPO · fresh") == (
        "quiet · 1 fold · short IPO fresh"
    )
    assert soft_allow_lean_meta(
        "2 short · last IPO · fresh · 1 gap · last AAPL · fresh"
    ) == ("quiet · 2 folds · short IPO fresh · gap AAPL fresh")
    assert soft_allow_lean_meta(
        "2 short · last IPO · fresh · tied · 1 gap · last AAPL · fresh"
    ) == ("quiet · 3 folds · short IPO fresh · tied · gap AAPL fresh")
    assert soft_allow_lean_meta(
        "2 short · last IPO · fresh · tied · hot · 66.7% · "
        "short last/ring align · fresh · hot · "
        "vs gap · thin · 1 · 33% · "
        "short last/share align · fresh · hot · "
        "short share/ring align · both align · "
        "short vs gap align · hot|thin · 1 gap · last AAPL · fresh"
    ) == (
        "quiet · 8 folds · short IPO fresh · tied hot 66.7% · "
        "short last/ring align fresh hot · vs gap thin 1 33% · +4"
    )
    assert soft_allow_lean_meta(
        "2 short · last IPO · fresh · tied · hot · 66.7% · "
        "short last/ring align · fresh · hot · "
        "vs gap · thin · 1 · 33% · "
        "short last/share align · fresh · hot · "
        "short share/ring align · both align · "
        "short vs gap align · hot|thin · "
        "short Δ wide · +34pp · short lean/Δ align · wide · short Δ lead · short · "
        "short last/lean align · fresh · hot|thin · "
        "short share/lean align · both align · "
        "short ring/lean align · both align · "
        "1 gap · last AAPL · fresh"
    ) == (
        "quiet · 14 folds · short IPO fresh · tied hot 66.7% · "
        "short last/ring align fresh hot · vs gap thin 1 33% · +10"
    )
    assert soft_allow_lean_meta("3 short · 2 bench · last SPY · fresh") == (
        "quiet · 1 fold · short 2 bench SPY fresh"
    )
    assert soft_allow_lean_meta(
        "3 short · 2 bench · hot · 66.7% · last SPY · fresh"
    ) == ("quiet · 1 fold · short 2 bench hot 66.7% SPY fresh")
    assert soft_allow_lean_meta(
        "3 short · 2 bench · hot · 66.7% · vs 1 young · thin · 33.3% · "
        "short bench vs young align · hot|thin · last SPY · fresh"
    ) == (
        "quiet · 1 fold · short 2 bench hot 66.7% vs 1 young thin 33.3% "
        "align hot|thin SPY fresh"
    )
    assert soft_allow_lean_meta(
        "3 short · 2 bench · hot · 66.7% · vs 1 young · thin · 33.3% · "
        "short bench vs young align · hot|thin · "
        "short bench Δ wide · +33.4pp · short bench lean/Δ align · wide · "
        "short bench Δ lead · bench · "
        "last SPY · fresh"
    ) == (
        "quiet · 1 fold · short 2 bench hot 66.7% vs 1 young thin 33.3% "
        "align hot|thin wide +33.4pp align wide bench SPY fresh"
    )
    assert soft_allow_lean_meta(
        "short bench Δ wide · +33.4pp · short bench lean/Δ align · wide · "
        "short bench Δ lead · bench"
    ) == (
        "quiet · 3 folds · short bench Δ wide +33.4pp · "
        "short bench lean/Δ align wide · short bench Δ lead bench"
    )
    assert soft_allow_lean_meta(
        "short Δ lead · short · short Δ moods align · both wide"
    ) == (
        "quiet · 2 folds · short Δ lead short · "
        "short Δ moods align both wide"
    )
    assert soft_allow_lean_meta(
        "short Δ moods clash · short/gap wide · bench/young thin"
    ) == (
        "quiet · 1 fold · short Δ moods clash short/gap wide bench/young thin"
    )
    assert soft_allow_lean_meta(
        "short lean moods align · both align"
    ) == ("quiet · 1 fold · short lean moods align both align")
    assert soft_allow_lean_meta(
        "short lean moods clash · short/gap clash · bench/young align"
    ) == (
        "quiet · 1 fold · short lean moods clash short/gap clash "
        "bench/young align"
    )
    assert soft_allow_lean_meta(
        "short lean vs Δ moods align · both align"
    ) == (
        "quiet · 1 fold · short lean vs Δ moods align both align"
    )
    assert soft_allow_lean_meta(
        "short lean vs Δ moods clash · lean align · Δ clash"
    ) == (
        "quiet · 1 fold · short lean vs Δ moods clash lean align Δ clash"
    )
    assert soft_allow_lean_meta(
        "3 short · 2 bench · hot · 66.7% · vs 1 young · thin · 33.3% · "
        "short bench vs young align · hot|thin · last SPY · fresh · "
        "short last/bench align · fresh · hot|thin"
    ) == (
        "quiet · 2 folds · short 2 bench hot 66.7% vs 1 young thin 33.3% "
        "align hot|thin SPY fresh · short last/bench align fresh hot|thin"
    )
    assert soft_allow_lean_meta(
        "short last/bench align · fresh · hot|thin · "
        "short lead/bench clash · lead clash · bench align"
    ) == (
        "quiet · 2 folds · short last/bench align fresh hot|thin · "
        "short lead/bench clash lead clash bench align"
    )
    assert soft_allow_lean_meta(
        "short last/share align · fresh · hot · "
        "short share/bench clash · share align · bench clash"
    ) == (
        "quiet · 2 folds · short last/share align fresh hot · "
        "short share/bench clash share align bench clash"
    )
    assert soft_allow_lean_meta(
        "short last/ring align · fresh · hot · "
        "short ring/bench clash · ring align · bench clash"
    ) == (
        "quiet · 2 folds · short last/ring align fresh hot · "
        "short ring/bench clash ring align bench clash"
    )


def test_soft_allow_glance_short_history_bench_count() -> None:
    """xang1234 #679: primary-benchmark short ≠ young listing short."""
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-22T11:00:00Z",
                "gate": "rs",
                "reason": "SPY RS unknown — short history — allow",
            },
            {
                "at": "2026-10-22T10:30:00Z",
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
            {
                "at": "2026-10-22T10:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
    )
    assert g["ready"] is True
    assert g["short_history_count"] == 2
    assert g["short_history_bench_count"] == 1
    assert g["short_history_bench_share_pct"] == 50.0
    assert g["short_history_bench_share_severity"] == "hot"
    assert g["short_history_bench_vs_young_n"] == 1
    assert g["short_history_bench_vs_young_share_pct"] == 50.0
    assert g["short_history_bench_vs_young_severity"] == "ok"
    # One-lean clash (bench hot · young mid) — gap vs other parity.
    assert g["short_history_bench_vs_young"] == "clash · bench hot · young ok"
    assert g["short_history_bench_vs_young_warn"] is True
    # 50/50 → mid/0pp silent on Δ bit; lean-spoke → clash · lean · Δ mid.
    assert g["short_history_bench_vs_young_delta_pp"] is None
    assert g["short_history_bench_vs_young_delta_severity"] == ""
    assert g["short_history_bench_vs_young_lean_vs_delta"] == (
        "clash · lean · Δ mid"
    )
    assert g["short_history_bench_vs_young_lean_vs_delta_warn"] is True
    # Mid-Δ clash → no Δ lead (short vs gap Δ lead parity).
    assert g["short_history_bench_vs_young_delta_lead"] == ""
    assert g["short_history_last"] == "SPY"
    assert g["short_history_last_freshness"] == "fresh"
    # Fresh + clash lean → last/bench clash (gap last/lean parity).
    assert g["short_history_last_vs_bench_young"] == (
        "clash · fresh · bench hot · young ok"
    )
    assert g["short_history_last_vs_bench_young_warn"] is True
    # Tied SPY/IPO → no last/lead → lead/bench silent.
    assert g["short_history_last_lead_vs_bench_young"] == ""
    assert g["short_history_last_lead_vs_bench_young_warn"] is False
    assert g["short_history_last_vs_share"] == "align · fresh · hot"
    assert g["short_history_last_vs_share_warn"] is False
    # last/share align + last/bench clash → short share/bench crossed.
    assert g["short_history_last_share_vs_bench_young"] == (
        "clash · share align · bench clash"
    )
    assert g["short_history_last_share_vs_bench_young_warn"] is True
    # last/ring align + last/bench clash → short ring/bench crossed.
    assert g["short_history_last_ring_vs_bench_young"] == (
        "clash · ring align · bench clash"
    )
    assert g["short_history_last_ring_vs_bench_young_warn"] is True
    assert g["short_history_last_vs_lean"] == "align · fresh · hot|thin"
    assert g["short_history_last_vs_lean_warn"] is False
    assert g["short_history_last_share_vs_lean"] == "align · both align"
    assert g["short_history_last_share_vs_lean_warn"] is False
    assert g["short_history_last_ring_vs_lean"] == "align · both align"
    assert g["short_history_last_ring_vs_lean_warn"] is False
    # last/lean align + last/bench clash → short lean/bench crossed.
    assert g["short_history_last_lean_vs_bench_young"] == (
        "clash · lean align · bench clash"
    )
    assert g["short_history_last_lean_vs_bench_young_warn"] is True
    assert g["short_history_share_pct"] == 66.7
    assert g["short_history_share_severity"] == "hot"
    assert g["short_history_last_vs_ring_share"] == "align · fresh · hot"
    assert g["short_history_last_vs_ring_share_warn"] is False
    assert g["short_history_last_share_vs_ring"] == "align · both align"
    assert g["short_history_last_share_vs_ring_warn"] is False
    assert g["short_history_bit"] == (
        "2 short · 1 bench · hot · 50% · vs 1 young · 50% · "
        "short bench vs young clash · bench hot · young ok · "
        "short bench lean/Δ clash · lean · Δ mid · "
        "last SPY · fresh · "
        "short last/bench clash · fresh · bench hot · young ok · "
        "tied · hot · 66.7% · "
        "short last/ring align · fresh · hot · "
        "short ring/bench clash · ring align · bench clash · "
        "vs gap · thin · "
        "1 · 33% · short last/share align · fresh · hot · "
        "short share/bench clash · share align · bench clash · "
        "short share/ring align · both align · "
        "short vs gap align · hot|thin · "
        "short Δ wide · +34pp · short lean/Δ align · wide · short Δ lead · short · "
        "short lean moods clash · short/gap align · bench/young clash · "
        "short last/lean align · fresh · hot|thin · "
        "short share/lean align · both align · "
        "short ring/lean align · both align · "
        "short lean/bench clash · lean align · bench clash"
    )
    assert g["short_history_lean_moods"] == (
        "clash · short/gap align · bench/young clash"
    )
    assert g["short_history_lean_moods_warn"] is True
    assert "1 bench · hot · 50%" in g["line"]
    assert "vs 1 young · 50%" in g["line"]
    assert "short last/bench clash" in g["line"]
    assert "short share/bench clash" in g["line"]
    assert "short ring/bench clash" in g["line"]
    assert "short lean/bench clash" in g["line"]
    assert "short lean moods clash" in g["line"]
    assert g["tone"] == "warn"
    assert g["soft_lean_warn"] is True
    assert "short 1 bench hot 50% vs 1 young 50% clash" in g["soft_lean_meta"]
    assert "SPY fresh" in g["soft_lean_meta"]
    assert "short last/bench clash" in g["soft_lean_meta"]
    # share/bench may clip off soft_lean_meta (+N); soft_lean keeps it.
    assert "short share/bench clash" in g["soft_lean"]
    assert "short ring/bench clash" in g["soft_lean"]
    assert "short lean/bench clash" in g["soft_lean"]


def test_soft_allow_glance_short_delta_moods() -> None:
    """Pair lean/Δ mood vs bench/young lean/Δ — Yahoo share vs gap parity."""
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-22T11:00:00Z",
                "gate": "rs",
                "reason": "SPY RS unknown — short history — allow",
            },
            {
                "at": "2026-10-22T10:30:00Z",
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
            {
                "at": "2026-10-22T10:00:00Z",
                "gate": "rs",
                "reason": "BTC RS unknown — short history — allow",
            },
            {
                "at": "2026-10-22T09:30:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
    )
    assert g["short_history_vs_gap_lean_vs_delta"] == "align · wide"
    assert g["short_history_bench_vs_young_lean_vs_delta"] == "align · wide"
    assert g["short_history_delta_moods"] == "align · both wide"
    assert g["short_history_delta_moods_warn"] is True
    assert g["short_history_lean_moods"] == "align · both align"
    assert g["short_history_lean_moods_warn"] is False
    assert g["short_history_lean_vs_delta_moods"] == "align · both align"
    assert g["short_history_lean_vs_delta_moods_warn"] is False
    assert g["short_history_delta_lead_moods"] == "align · both adverse"
    assert g["short_history_delta_lead_moods_warn"] is True
    assert "short Δ moods align · both wide" in g["short_history_bit"]
    assert "short lean moods align · both align" in g["short_history_bit"]
    assert "short lean vs Δ moods align · both align" in g["short_history_bit"]
    assert "short Δ lead moods align · both adverse" in g["short_history_bit"]
    assert "short Δ moods align · both wide" in g["line"]
    assert "short lean moods align · both align" in g["line"]
    assert "short lean vs Δ moods align · both align" in g["line"]
    assert "short Δ lead moods align · both adverse" in g["line"]
    assert "short Δ moods align · both wide" in g["soft_lean"]
    assert "short lean moods align · both align" in g["soft_lean"]
    assert "short lean vs Δ moods align · both align" in g["soft_lean"]
    assert "short Δ lead moods align · both adverse" in g["soft_lean"]
    assert g["tone"] == "warn"
    assert g["soft_lean_warn"] is True
    # Pair wide + bench/young thin → clash (Yahoo share vs gap crossed).
    clash = build_soft_allow_glance(
        (
            [
                {
                    "at": "2026-10-22T11:00:00Z",
                    "gate": "rs",
                    "reason": "SPY RS unknown — short history — allow",
                }
            ]
            * 6
            + [
                {
                    "at": "2026-10-22T10:30:00Z",
                    "gate": "rs",
                    "reason": "IPO RS unknown — short history — allow",
                }
            ]
            * 5
            + [
                {
                    "at": "2026-10-22T10:00:00Z",
                    "gate": "rs",
                    "reason": "AAPL RS unknown — anchor gap — allow",
                }
            ]
        ),
        now=now,
    )
    assert clash["short_history_delta_moods"] == (
        "clash · short/gap wide · bench/young thin"
    )
    assert clash["short_history_delta_moods_warn"] is True
    assert clash["short_history_lean_moods"] == "align · both align"
    assert clash["short_history_lean_moods_warn"] is False
    assert clash["short_history_lean_vs_delta_moods"] == (
        "clash · lean align · Δ clash"
    )
    assert clash["short_history_lean_vs_delta_moods_warn"] is True
    assert "short Δ moods clash · short/gap wide · bench/young thin" in (
        clash["short_history_bit"]
    )
    assert "short lean moods align · both align" in clash["short_history_bit"]
    assert "short lean vs Δ moods clash · lean align · Δ clash" in (
        clash["short_history_bit"]
    )
    assert clash["short_history_delta_lead_moods"] == "align · both adverse"
    assert clash["short_history_delta_lead_moods_warn"] is True
    assert "short Δ lead moods align · both adverse" in clash["short_history_bit"]


def test_soft_allow_glance_short_lead_vs_bench_young() -> None:
    """last/lead ≠ last/bench — short lead/bench after #679 last/bench."""
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-22T11:30:00Z",
                "gate": "rs",
                "reason": "NEW RS unknown — short history — allow",
            },
            {
                "at": "2026-10-22T11:00:00Z",
                "gate": "rs",
                "reason": "SPY RS unknown — short history — allow",
            },
            {
                "at": "2026-10-22T10:30:00Z",
                "gate": "rs",
                "reason": "SPY RS unknown — short history — allow",
            },
            {
                "at": "2026-10-22T10:00:00Z",
                "gate": "rs",
                "reason": "BTC RS unknown — short history — allow",
            },
        ],
        now=now,
    )
    assert g["short_history_last_vs_bench_young"] == (
        "align · fresh · hot|thin"
    )
    assert g["short_history_last_vs_bench_young_warn"] is False
    assert g["short_history_last_vs_lead_freshness"] == (
        "clash · fresh · vs NEW"
    )
    assert g["short_history_last_lead_vs_bench_young"] == (
        "clash · lead clash · bench align"
    )
    assert g["short_history_last_lead_vs_bench_young_warn"] is True
    assert "short lead/bench clash · lead clash · bench align" in g["line"]
    assert "short lead/bench clash · lead clash · bench align" in g[
        "short_history_bit"
    ]
    assert "short lead/bench clash · lead clash · bench align" in g[
        "soft_lean"
    ]
    assert g["tone"] == "warn"
    assert g["soft_lean_warn"] is True


def test_soft_allow_glance_short_vs_gap_clock_when_short_matches_scan() -> None:
    """xang1234 #549: short matching scan ≠ gap cursor generation."""
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    assert g["scan_vs_soft_allow_clash"] == ""
    # Soft≠gap may also speak (soft last fresh vs gap fresh → silent;
    # gap is fresh same as soft). Short cursor expired ≠ gap fresh.
    assert g["short_history_vs_gap_clock_clash"] == (
        "clash · short expired · gap fresh · short-only · gap-only"
    )
    assert g["short_history_vs_gap_clock_clash_warn"] is True
    assert g["tone"] == "warn"
    assert "clash · short expired · gap fresh · short-only · gap-only" in (
        g["short_history_bit"]
    )
    assert "clash · short expired · gap fresh · short-only · gap-only" in (
        g["line"]
    )
    assert "clash · short expired · gap fresh · short-only · gap-only" in (
        g["soft_lean"]
    )
    # Meta may spill short/gap past the 4-name clip when scan/cash also
    # clash — lean string still carries the generation bit.
    same = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert same["short_history_vs_gap_clock_clash"] == ""
    assert same["short_history_vs_gap_clock_clash_warn"] is False


def test_soft_allow_glance_short_keep_gap_when_short_matches_gap() -> None:
    """xang1234 #660/#647: short≠scan keeps gap-only when short≡gap."""
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert g["short_history_last_freshness"] == "expired"
    assert g["anchor_gap_last_freshness"] == "expired"
    # Short matches gap — no short≠gap clock clash.
    assert g["short_history_vs_gap_clock_clash"] == ""
    assert g["short_history_vs_gap_clock_clash_warn"] is False
    # Short≠scan speaks short-only · scan-only and keeps gap-only so
    # scan alone cannot hide the matched gap cursor (soft≠scan keep-gap
    # + sole-pin #647 / #531 / #668).
    scan_clash = g["short_history_vs_scan_clash"]
    assert scan_clash.startswith(
        "clash · short expired · scan fresh · short-only · scan-only"
    )
    assert scan_clash.endswith(" · gap-only")
    assert g["short_history_vs_scan_clash_warn"] is True
    assert scan_clash in g["short_history_bit"]
    assert "gap-only" in g["soft_lean_meta"] or "gap-only" in g["soft_lean"]
    assert "short-only" in g["soft_lean_meta"] or "short-only" in g["soft_lean"]
    # Speak-both-sides: gap≠scan keeps short-only so scan alone cannot
    # hide the matched short cursor (short keep-gap + #668).
    gap_scan = g["anchor_gap_vs_scan_clash"]
    assert gap_scan.startswith("clash · gap expired · scan fresh")
    assert "short-only" in gap_scan
    assert gap_scan in g["anchor_gap_bit"]
    assert "short-only" in g["soft_lean_meta"] or "short-only" in g["soft_lean"]
    assert g["tone"] == "warn"


def test_soft_allow_glance_soft_keep_short_when_soft_matches_short() -> None:
    """xang1234 #660/#668: soft≠scan keeps short-only when soft≡short."""
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": expired_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "stale"
    assert g["short_history_last_freshness"] == "expired"
    # Soft matches short — no soft≠short clock clash (expired≡stale).
    assert g["soft_vs_short_clock_clash"] == ""
    assert g["soft_vs_short_clock_clash_warn"] is False
    # Soft≠scan still speaks and keeps short-only so scan alone cannot
    # hide the matched short cursor (gap≠scan keep-short parity + #668).
    soft_scan = g["scan_vs_soft_allow_clash"]
    assert soft_scan.startswith("clash · scan fresh")
    assert "soft-only" in soft_scan
    assert soft_scan.endswith(" · short-only")
    assert soft_scan in g["line"]
    assert "short-only" in g["soft_lean_meta"] or "short-only" in g["soft_lean"]
    # Speak-both-sides: short≠scan names short-only · scan-only and keeps
    # soft-only so scan alone cannot hide the matched soft last
    # (soft keep-short + sole-pin #647 / #531 / #668).
    short_scan = g["short_history_vs_scan_clash"]
    assert short_scan.startswith(
        "clash · short expired · scan fresh · short-only · scan-only"
    )
    assert short_scan.endswith(" · soft-only")
    assert g["short_history_vs_scan_clash_warn"] is True
    assert short_scan in g["short_history_bit"]
    assert "soft-only" in g["soft_lean_meta"] or "soft-only" in g["soft_lean"]
    assert g["tone"] == "warn"


def test_soft_allow_glance_short_vs_scan_when_last_matches_scan() -> None:
    """xang1234 #549/e3c84e1: soft last matching scan ≠ live short cursor."""
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    # Soft-allow last matches scan — no ring-level clash.
    assert g["scan_vs_soft_allow_clash"] == ""
    # Soft last ≠ short cursor — soft↔short↔scan triangle (soft≠gap
    # parity + #668); soft matches scan so keep scan-only.
    assert g["soft_vs_short_clock_clash"] == (
        "clash · soft fresh · short expired · soft-only · short-only · "
        "scan-only"
    )
    assert g["soft_vs_short_clock_clash_warn"] is True
    assert (
        "clash · soft fresh · short expired · soft-only · short-only · "
        "scan-only"
        in g["line"]
    )
    assert "soft/short" in g["soft_lean_meta"] or "short-only" in (
        g["soft_lean_meta"]
    )
    # Short cursor is a different generation — speak both sides with
    # sole pins short-only · scan-only (#647 / #531 / #668).
    assert g["short_history_vs_scan_clash"] == (
        "clash · short expired · scan fresh · short-only · scan-only"
    )
    assert g["short_history_vs_scan_clash_warn"] is True
    assert g["tone"] == "warn"
    assert (
        "clash · short expired · scan fresh · short-only · scan-only"
        in g["short_history_bit"]
    )
    assert (
        "last IPO · expired · clash · short expired · scan fresh"
        " · short-only · scan-only"
        in g["short_history_bit"]
    )
    assert (
        "clash · short expired · scan fresh · short-only · scan-only"
        in g["line"]
    )
    assert "short/scan" in g["soft_lean_meta"] or "short-only" in (
        g["soft_lean_meta"]
    )
    same = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert same["short_history_vs_scan_clash"] == ""
    assert same["short_history_vs_scan_clash_warn"] is False
    assert same["soft_vs_short_clock_clash"] == ""
    assert same["soft_vs_short_clock_clash_warn"] is False
    assert "clash · soft fresh · short" not in same["line"]
    # Same short↔scan band silent on the bit (short≠cash may still speak).
    assert "clash · short" not in same["short_history_bit"] or (
        same["short_history_vs_cash_clock_clash"]
        and " · scan " not in same["short_history_bit"]
    )


def test_soft_allow_glance_short_vs_cash_when_short_matches_scan() -> None:
    """xang1234 #549: short matching scan ≠ pinned cash print generation."""
    # Saturday afternoon UTC — cash sleeves last-published (US aging).
    # Soft last + short cursor both fresh match the scan → short≠scan
    # silent; short≠cash still speaks (gap≠cash / soft≠cash parity) and
    # keeps ``scan-only`` so cash alone cannot hide the archive match
    # (gap≠cash keep-scan + #660 / #647 / #531).
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
        ],
        now=now,
        scan_time=fresh_at,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    assert g["short_history_last_freshness"] == "fresh"
    assert g["short_history_vs_scan_clash"] == ""
    assert g["short_history_vs_scan_clash_warn"] is False
    cash = g["short_history_vs_cash_clock_clash"]
    assert cash.startswith("clash · short fresh · cash ")
    # Sole short-only + cash pin; soft≡short silent — keep soft-only
    # after scan-only so cash alone cannot hide the matched soft last
    # (#668 / #647 / #531 speak-both-sides).
    assert " · short-only" in cash
    assert " · scan-only" in cash
    assert cash.endswith(" · soft-only")
    assert g["short_history_vs_cash_clock_clash_warn"] is True
    assert cash in g["short_history_bit"]
    assert cash in g["line"]
    assert g["tone"] == "warn"
    assert "short/cash" in g["soft_lean_meta"]
    assert "short-only" in g["soft_lean_meta"]
    assert "scan-only" in g["soft_lean_meta"]
    assert "soft-only" in g["soft_lean_meta"] or "soft-only" in g["soft_lean"]
    # Same-evening last-published: short fresh + cash fresh → silent.
    even = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    even_at = (even - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    same = build_soft_allow_glance(
        [
            {
                "at": even_at,
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
        ],
        now=even,
        scan_time=even_at,
        scan_interval_sec=900,
    )
    assert same["short_history_last_freshness"] == "fresh"
    assert same["short_history_vs_cash_clock_clash"] == ""
    assert same["short_history_vs_cash_clock_clash_warn"] is False
    assert "clash · short" not in same["short_history_bit"]


def test_soft_allow_glance_short_vs_memory_when_short_matches_scan() -> None:
    """xang1234 #549: short matching scan ≠ live LAYA/debate print."""
    # Same-evening last-published: soft + short fresh match scan + cash →
    # short≠scan / short≠cash silent; short≠memory still speaks and keeps
    # ``scan-only`` + cash pin so memory alone cannot hide those matches
    # (gap≠memory keep-scan|/cash + #660 / #647 / #531).
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
        ],
        now=now,
        scan_time=fresh_at,
        scan_interval_sec=900,
        laya_freshness="stale",
        debate_freshness="aging",
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    assert g["short_history_last_freshness"] == "fresh"
    assert g["short_history_vs_scan_clash"] == ""
    assert g["short_history_vs_scan_clash_warn"] is False
    assert g["short_history_vs_cash_clock_clash"] == ""
    mem = g["short_history_vs_memory_clock_clash"]
    assert mem.startswith(
        "clash · short fresh · laya stale · debate aging · short-only"
    )
    assert " · scan-only" in mem
    assert "short-only" in mem
    # Advisory pin + keep-scan ride after short-only; cash may follow.
    assert mem.endswith("-only") or " · ×" in mem or " · US" in mem
    assert g["short_history_vs_memory_clock_clash_warn"] is True
    assert mem in g["short_history_bit"]
    assert mem in g["line"]
    assert g["tone"] == "warn"
    assert "short/memory" in g["soft_lean_meta"]
    assert "scan-only" in g["soft_lean_meta"]
    assert "short-only" in g["soft_lean_meta"]
    # Same band as short — silent (no false mixed-generation warn).
    same = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
        ],
        now=now,
        scan_time=fresh_at,
        scan_interval_sec=900,
        laya_freshness="fresh",
        debate_freshness="fresh",
    )
    assert same["short_history_vs_memory_clock_clash"] == ""
    assert same["short_history_vs_memory_clock_clash_warn"] is False
    assert "clash · short" not in same["short_history_bit"] or (
        " · laya " not in same["short_history_bit"]
        and " · debate " not in same["short_history_bit"]
    )
    # Only debate disagrees — sole advisory side on the bit.
    one = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
        ],
        now=now,
        scan_time=fresh_at,
        scan_interval_sec=900,
        laya_freshness="fresh",
        debate_freshness="stale",
    )
    assert one["short_history_vs_memory_clock_clash"].startswith(
        "clash · short fresh · debate stale · short-only"
    )
    # Sole short-only + debate · 50%; soft≡short silent — keep soft-only
    # so debate alone cannot hide the matched soft last (#668 / #647 /
    # #531 speak-both-sides). Cash dual pin may ride as keep-cash.
    mem_one = one["short_history_vs_memory_clock_clash"]
    assert " · short-only" in mem_one
    assert " · debate · 50%" in mem_one or " · debate-only" in mem_one
    assert " · scan-only" in mem_one
    assert mem_one.endswith(" · soft-only")
    assert one["short_history_vs_memory_clock_clash_warn"] is True
    assert "laya" not in mem_one.split(" · debate ")[0]


def test_soft_allow_glance_short_history_last_freshness_expired() -> None:
    """last SYM alone ≠ live young/short fail-open (gap freshness parity)."""
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-20T11:00:00Z",
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
        ],
        now=now,
    )
    assert g["ready"] is True
    assert g["short_history_count"] == 1
    assert g["short_history_last"] == "IPO"
    assert g["short_history_last_freshness"] == "expired"
    assert g["short_history_last_vs_lean"] == ""
    assert g["short_history_last_vs_lean_warn"] is False
    assert g["short_history_share_pct"] == 100.0
    assert g["short_history_share_severity"] == "hot"
    assert g["short_history_last_vs_ring_share"] == (
        "clash · expired · hot"
    )
    assert g["short_history_last_vs_ring_share_warn"] is True
    assert g["short_history_last_vs_share"] == ""
    assert g["short_history_bit"] == (
        "1 short · last IPO · expired · n=1 · hot · 100% · "
        "short last/ring clash · expired · hot"
    )
    assert "last IPO · expired" in g["line"]
    assert "hot · 100%" in g["line"]
    assert g["tone"] == "warn"
    assert g["soft_lean_warn"] is True
    assert "short IPO expired" in g["soft_lean_meta"]


def test_soft_allow_glance_short_history_last_vs_lean_clash() -> None:
    """last freshness + short/gap lean alone ≠ age↔lean (gap last/lean)."""
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-20T11:00:00Z",
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
            {
                "at": "2026-10-20T10:30:00Z",
                "gate": "rs",
                "reason": "NEW RS unknown — short history — allow",
            },
            {
                "at": "2026-10-20T10:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
    )
    assert g["ready"] is True
    assert g["short_history_count"] == 2
    assert g["short_history_last_freshness"] == "expired"
    assert g["short_history_vs_gap_lean"] == "align · hot|thin"
    # Expired ↔ pair share hot → last/share clash (gap last/share parity).
    assert g["short_history_last_vs_share"] == "clash · expired · hot"
    assert g["short_history_last_vs_share_warn"] is True
    # Expired ↔ lean align → clash warn (gap last/lean parity).
    assert g["short_history_last_vs_lean"] == "clash · expired · hot|thin"
    assert g["short_history_last_vs_lean_warn"] is True
    # Dual clash → share/lean both clash warn (gap share/lean parity).
    assert g["short_history_last_share_vs_lean"] == "align · both clash"
    assert g["short_history_last_share_vs_lean_warn"] is True
    # Dual clash → ring/lean both clash warn (gap share/lean on short÷ring).
    assert g["short_history_last_ring_vs_lean"] == "align · both clash"
    assert g["short_history_last_ring_vs_lean_warn"] is True
    assert "short last/share clash · expired · hot" in g["short_history_bit"]
    assert "short share/ring align · both clash" in g["short_history_bit"]
    assert "short last/lean clash · expired · hot|thin" in g["short_history_bit"]
    assert "short share/lean align · both clash" in g["short_history_bit"]
    assert "short ring/lean align · both clash" in g["short_history_bit"]
    assert g["short_history_last_share_vs_ring"] == "align · both clash"
    assert g["short_history_last_share_vs_ring_warn"] is True
    assert "short last/lean clash · expired · hot|thin" in g["line"]
    assert "short share/ring align · both clash" in g["line"]
    assert "short share/lean align · both clash" in g["line"]
    assert "short ring/lean align · both clash" in g["line"]
    assert g["tone"] == "warn"
    assert g["soft_lean_warn"] is True


def test_soft_allow_glance_short_history_symbol_lead() -> None:
    """last SYM alone ≠ which young/short name owns the fail-open ring."""
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-22T11:00:00Z",
                "gate": "rs",
                "reason": "NEW RS unknown — short history — allow",
            },
            {
                "at": "2026-10-22T10:45:00Z",
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
            {
                "at": "2026-10-22T10:30:00Z",
                "gate": "rs",
                "reason": "IPO RS unknown — short history — allow",
            },
            {
                "at": "2026-10-22T10:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
    )
    assert g["ready"] is True
    assert g["short_history_count"] == 3
    assert g["short_history_last"] == "NEW"
    assert g["short_history_last_freshness"] == "fresh"
    assert g["short_history_symbol_lead"] == "lead IPO · 2 · 67%"
    assert g["short_history_symbol_lead_name"] == "IPO"
    assert g["short_history_symbol_lead_share"] == 67
    assert g["short_history_symbol_sample_gap"] == ""
    assert g["short_history_symbol_last_vs_lead"] == "last vs lead · NEW"
    # Fresh + name clash → short last/lead clash warn (gap last/lead).
    assert g["short_history_last_vs_lead_freshness"] == (
        "clash · fresh · vs NEW"
    )
    assert g["short_history_last_vs_lead_freshness_warn"] is True
    assert g["short_history_symbol_lead_margin"] == 1
    assert g["short_history_symbol_lead_margin_severity"] == "thin"
    assert g["short_history_symbol_lead_margin_bit"] == "ahead thin · +1"
    assert g["short_history_symbol_lead_runner"] == "NEW"
    assert g["short_history_symbol_lead_runner_count"] == 1
    assert g["short_history_symbol_lead_runner_share"] == 33
    assert g["short_history_symbol_lead_sides"] == "vs NEW · 1 · 33%"
    # 3 short + 1 gap → gap owns 25% thin; short 75% hot → align.
    assert g["short_history_vs_gap"] == "vs gap · thin · 1 · 25%"
    assert g["short_history_vs_gap_count"] == 1
    assert g["short_history_vs_gap_share"] == 25
    assert g["short_history_vs_gap_severity"] == "thin"
    assert g["short_history_pair_share"] == 75
    assert g["short_history_pair_severity"] == "hot"
    assert g["short_history_vs_gap_lean"] == "align · hot|thin"
    assert g["short_history_vs_gap_lean_warn"] is False
    assert g["short_history_last_vs_share"] == "align · fresh · hot"
    assert g["short_history_last_vs_share_warn"] is False
    assert g["short_history_last_vs_lean"] == "align · fresh · hot|thin"
    assert g["short_history_last_vs_lean_warn"] is False
    # last/lead clash + last/share align → short lead/share clash (gap lead/share).
    assert g["short_history_last_lead_vs_share"] == (
        "clash · lead clash · share align"
    )
    assert g["short_history_last_lead_vs_share_warn"] is True
    # last/lead clash + last/ring align → short lead/ring clash (gap lead/share on ring).
    assert g["short_history_last_lead_vs_ring"] == (
        "clash · lead clash · ring align"
    )
    assert g["short_history_last_lead_vs_ring_warn"] is True
    # last/lead clash + last/lean align → short lead/lean clash (not transitive).
    assert g["short_history_last_lead_vs_lean"] == (
        "clash · lead clash · lean align"
    )
    assert g["short_history_last_lead_vs_lean_warn"] is True
    # last/share + last/lean both align → share/lean both align (gap share/lean).
    assert g["short_history_last_share_vs_lean"] == "align · both align"
    assert g["short_history_last_share_vs_lean_warn"] is False
    # last/share + last/ring both align → share/ring both align.
    assert g["short_history_last_share_vs_ring"] == "align · both align"
    assert g["short_history_last_share_vs_ring_warn"] is False
    # last/ring + last/lean both align → ring/lean both align (gap share/lean on ring).
    assert g["short_history_last_ring_vs_lean"] == "align · both align"
    assert g["short_history_last_ring_vs_lean_warn"] is False
    assert g["short_history_share_pct"] == 75.0
    assert g["short_history_share_severity"] == "hot"
    assert g["short_history_last_vs_ring_share"] == "align · fresh · hot"
    assert g["short_history_last_vs_ring_share_warn"] is False
    assert g["short_history_bit"] == (
        "3 short · last NEW · fresh · lead IPO · 2 · 67% · "
        "last vs lead · NEW · short last/lead clash · fresh · vs NEW · "
        "ahead thin · +1 · vs NEW · 1 · 33% · hot · 75% · "
        "short last/ring align · fresh · hot · "
        "short lead/ring clash · lead clash · ring align · "
        "vs gap · thin · 1 · 25% · short last/share align · fresh · hot · "
        "short lead/share clash · lead clash · share align · "
        "short share/ring align · both align · "
        "short vs gap align · hot|thin · "
        "short Δ wide · +50pp · short lean/Δ align · wide · short Δ lead · short · "
        "short last/lean align · fresh · hot|thin · "
        "short lead/lean clash · lead clash · lean align · "
        "short share/lean align · both align · "
        "short ring/lean align · both align"
    )
    assert "lead IPO · 2 · 67%" in g["line"]
    assert "last vs lead · NEW" in g["line"]
    assert "short last/lead clash · fresh · vs NEW" in g["line"]
    assert "short last/lead clash · fresh · vs NEW" in g["soft_lean"]
    assert "short lead/ring clash · lead clash · ring align" in g["line"]
    assert "short lead/ring clash · lead clash · ring align" in g["soft_lean"]
    assert "short lead/share clash · lead clash · share align" in g["line"]
    assert "short lead/share clash · lead clash · share align" in g["soft_lean"]
    assert "short share/ring align · both align" in g["line"]
    assert "short share/ring align · both align" in g["soft_lean"]
    assert "short lead/lean clash · lead clash · lean align" in g["line"]
    assert "short lead/lean clash · lead clash · lean align" in g["soft_lean"]
    assert "short share/lean align · both align" in g["line"]
    assert "short share/lean align · both align" in g["soft_lean"]
    assert "short ring/lean align · both align" in g["line"]
    assert "short ring/lean align · both align" in g["soft_lean"]
    assert g["tone"] == "warn"
    assert g["soft_lean_warn"] is True
    assert "ahead thin · +1" in g["line"]
    assert "vs NEW · 1 · 33%" in g["line"]
    assert "vs gap · thin · 1 · 25%" in g["line"]
    assert "short vs gap align · hot|thin" in g["line"]
    assert "short NEW fresh" in g["soft_lean_meta"]
    assert "lead IPO" in g["soft_lean_meta"]
    # short lead/ring + lead/share + share/ring + lead/lean are in soft_lean; 4-name meta may spill.
    assert "short lead/ring" in g["soft_lean"]
    assert "short lead/share" in g["soft_lean"]
    assert "short share/ring" in g["soft_lean"]
    assert "short lead/lean" in g["soft_lean"]
    assert "short share/lean" in g["soft_lean"]
    assert "short ring/lean" in g["soft_lean"]
    assert g["soft_lean_meta"].startswith("clash")


def test_soft_allow_glance_anchor_gap_count() -> None:
    """xang1234 #539: rs×N alone ≠ gappy-anchor fail-open count + share."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-08T11:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:30:00Z",
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
            {
                "at": "2026-10-08T10:00:00Z",
                "gate": "rs",
                "reason": "MSFT RS unknown — anchor gap — allow",
            },
        ],
        now=now,
    )
    assert g["ready"] is True
    assert g["short_history_count"] == 0
    assert g["short_history_bit"] == ""
    assert g["anchor_gap_count"] == 2
    assert g["anchor_gap_last"] == "AAPL"
    assert g["anchor_gap_last_freshness"] == "fresh"
    assert g["anchor_gap_symbol_lead"] == ""
    assert g["anchor_gap_symbol_last_vs_lead"] == ""
    assert g["anchor_gap_symbol_sample_gap"] == "tied"
    assert g["anchor_gap_share_pct"] == 66.7
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last_vs_share"] == "align · fresh · hot · ×2 · 67%"
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_other_count"] == 1
    assert g["anchor_gap_other_share_pct"] == 33.3
    assert g["anchor_gap_other_share_severity"] == "thin"
    assert g["anchor_gap_vs_other"] == "align · hot|thin"
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == (
        "align · fresh · hot|thin · ×2 · 67%"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == (
        "align · both align · ×2 · 67%"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    assert g["anchor_gap_bit"] == (
        "2 gap · last AAPL · fresh · tied · hot · 66.7% · "
        "last/share align · fresh · hot · ×2 · 67% · vs 1 other · thin · "
        "33.3% · gap vs other align · hot|thin · "
        "last/lean align · fresh · hot|thin · ×2 · 67% · "
        "share/lean align · both align · ×2 · 67%"
    )
    assert (
        "2 gap · last AAPL · fresh · tied · hot · 66.7% · "
        "last/share align · fresh · hot · ×2 · 67% · vs 1 other · thin · "
        "33.3% · gap vs other align · hot|thin · "
        "last/lean align · fresh · hot|thin · ×2 · 67% · "
        "share/lean align · both align · ×2 · 67%"
    ) in g["line"]
    # Gate last=lead agree + fresh age ride the lean fold beside RS-gap.
    assert g["last_vs_lead"] == "agree · last rs · lead rs · ×3 · 100%"
    assert g["last_vs_lead_freshness"] == (
        "last/lead align · fresh · agree · ×3 · 100%"
    )
    assert g["soft_lean"].startswith(
        "agree · last rs · lead rs · ×3 · 100% · "
        "last/lead align · fresh · agree · ×3 · 100% · "
    )
    assert g["soft_lean"].endswith(g["anchor_gap_bit"])
    assert g["soft_lean_warn"] is True
    assert g["soft_lean_meta"] == (
        "hot · last/lead rs ×3 100% · last/lead align fresh agree ×3 100% · "
        "gap AAPL fresh · tied hot 66.7% · +4"
    )
    assert g["anchor_gap_bit"] not in g["line_core"]
    assert "soft-allow" in g["line_core"]
    assert "last/share" not in g["line_core"]
    assert "last [rs]" in g["line"]
    assert "anchor gap" in g["line"]


def test_soft_allow_glance_anchor_gap_symbol_lead() -> None:
    """last SYM ≠ ring ownership: strict gap-symbol lead speaks %."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-08T11:00:00Z",
                "gate": "rs",
                "reason": "MSFT RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:45:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:30:00Z",
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
            {
                "at": "2026-10-08T10:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_count"] == 3
    assert g["anchor_gap_last"] == "MSFT"
    assert g["anchor_gap_last_freshness"] == "fresh"
    assert g["anchor_gap_symbol_lead"] == "lead AAPL · 2 · 67%"
    assert g["anchor_gap_symbol_lead_name"] == "AAPL"
    assert g["anchor_gap_symbol_lead_share"] == 67
    assert g["anchor_gap_symbol_lead_margin"] == 1
    assert g["anchor_gap_symbol_lead_margin_severity"] == "thin"
    assert g["anchor_gap_symbol_lead_margin_bit"] == "ahead thin · +1"
    assert g["anchor_gap_symbol_lead_runner"] == "MSFT"
    assert g["anchor_gap_symbol_lead_runner_count"] == 1
    assert g["anchor_gap_symbol_lead_runner_share"] == 33
    assert g["anchor_gap_symbol_lead_sides"] == "vs MSFT · 1 · 33%"
    assert g["anchor_gap_symbol_last_vs_lead"] == "last vs lead · MSFT"
    assert g["anchor_gap_last_vs_lead_freshness"] == (
        "clash · fresh · vs MSFT · ×3 · 75%"
    )
    assert g["anchor_gap_last_vs_lead_freshness_warn"] is True
    assert g["anchor_gap_symbol_sample_gap"] == ""
    assert g["anchor_gap_last_vs_share"] == "align · fresh · hot · ×3 · 75%"
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_last_lead_vs_share"] == (
        "clash · lead clash · share align · ×3 · 75%"
    )
    assert g["anchor_gap_last_lead_vs_share_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == (
        "align · fresh · hot|thin · ×3 · 75%"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_lead_vs_lean"] == (
        "clash · lead clash · lean align · ×3 · 75%"
    )
    assert g["anchor_gap_last_lead_vs_lean_warn"] is True
    assert g["anchor_gap_last_share_vs_lean"] == (
        "align · both align · ×3 · 75%"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    assert g["anchor_gap_bit"] == (
        "3 gap · last MSFT · fresh · lead AAPL · 2 · 67% · last vs lead · MSFT · "
        "last/lead clash · fresh · vs MSFT · ×3 · 75% · "
        "ahead thin · +1 · vs MSFT · 1 · 33% · hot · 75% · "
        "last/share align · fresh · hot · ×3 · 75% · "
        "lead/share clash · lead clash · share align · ×3 · 75% · "
        "vs 1 other · thin · 25% · gap vs other align · hot|thin · "
        "last/lean align · fresh · hot|thin · ×3 · 75% · "
        "lead/lean clash · lead clash · lean align · ×3 · 75% · "
        "share/lean align · both align · ×3 · 75%"
    )
    assert "lead AAPL · 2 · 67%" in g["line"]
    assert "last vs lead · MSFT" in g["line"]
    assert "last/lead clash · fresh · vs MSFT" in g["line"]
    assert "ahead thin · +1" in g["line"]
    assert "vs MSFT · 1 · 33%" in g["line"]
    # Gate last=lead agree + age align take chip slots; gap last/lead +
    # ahead may sit in +N.
    assert g["last_vs_lead_freshness"] == (
        "last/lead align · fresh · agree · ×4 · 100%"
    )
    assert "last/lead rs" in g["soft_lean_meta"]
    assert "last/lead align fresh agree ×4 100%" in g["soft_lean_meta"]
    assert "last/lead clash · fresh · vs MSFT" in g["soft_lean"]
    assert "ahead thin · +1 · vs MSFT · 1 · 33%" in g["soft_lean"]
    assert "last/share align · fresh · hot" in g["line"]
    assert "lead/share clash · lead clash · share align" in g["line"]
    assert "last/lean align · fresh · hot|thin" in g["line"]
    assert "lead/lean clash · lead clash · lean align" in g["line"]
    assert "share/lean align · both align" in g["line"]


def test_soft_allow_glance_anchor_gap_last_vs_lead_freshness_stale_agree() -> None:
    """Bare agree ≠ live owner: expired + agree clashes and warns."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_symbol_last_vs_lead"] == "agree"
    assert g["anchor_gap_last_vs_lead_freshness"] == (
        "clash · expired · agree · ×2 · 100%"
    )
    assert g["anchor_gap_last_vs_lead_freshness_warn"] is True
    assert g["anchor_gap_last_vs_share"] == (
        "clash · expired · hot · ×2 · 100%"
    )
    assert g["anchor_gap_last_lead_vs_share"] == (
        "align · both clash · ×2 · 100%"
    )
    assert g["anchor_gap_last_lead_vs_share_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == (
        "clash · expired · hot|thin · ×2 · 100%"
    )
    assert g["anchor_gap_last_lead_vs_lean"] == (
        "align · both clash · ×2 · 100%"
    )
    assert g["anchor_gap_last_lead_vs_lean_warn"] is True
    assert g["tone"] == "warn"
    assert "last/lead clash · expired · agree" in g["anchor_gap_bit"]
    assert "lead/share align · both clash" in g["anchor_gap_bit"]
    assert "lead/lean align · both clash" in g["anchor_gap_bit"]
    assert "last/lead clash · expired · agree" in g["line"]
    assert "lead/share align · both clash" in g["line"]
    assert "lead/lean align · both clash" in g["line"]


def test_soft_allow_lean_meta_keeps_relationship_payload() -> None:
    """Verb alone ≠ the print: age, heat, and crossed pairs stay on the chip."""
    from openbb_backend.desk import soft_allow_lean_meta

    crossed = soft_allow_lean_meta(
        "lead/share clash · lead clash · share align",
        warn=True,
    )
    assert crossed == "clash · lead/share clash lead clash share align"
    gap_other = soft_allow_lean_meta(
        "gap vs other clash · gap hot · other ok",
        warn=True,
    )
    assert gap_other == "clash · gap/other clash gap hot · other ok"
    calm = soft_allow_lean_meta(
        "2 gap · last AAPL · fresh · last/share align · fresh · hot",
        warn=False,
    )
    assert calm == "quiet · 2 folds · gap AAPL fresh · last/share align fresh hot"


def test_soft_allow_glance_anchor_gap_share_lean_both_clash_warns() -> None:
    """Dual-clash agreement ≠ calm: align · both clash warns + tone."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": stale,
                "gate": "rs",
                "reason": "MSFT RS unknown — anchor gap — allow",
            },
            {
                "at": stale,
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_last_freshness"] == "expired"
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last_vs_share"] == (
        "clash · expired · hot · ×2 · 67%"
    )
    assert g["anchor_gap_last_vs_share_warn"] is True
    assert g["anchor_gap_vs_other"] == "align · hot|thin"
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == (
        "clash · expired · hot|thin · ×2 · 67%"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is True
    assert g["anchor_gap_last_share_vs_lean"] == (
        "align · both clash · ×2 · 67%"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert g["severity"] == "cool"
    assert g["tone"] == "warn"
    assert "share/lean align · both clash" in g["anchor_gap_bit"]
    assert "share/lean align · both clash" in g["line"]
    assert g["soft_lean_meta"].startswith(
        "clash · share/lean align both clash"
    )
    assert "last/lead rs" in g["soft_lean_meta"]
    assert "last/share clash · expired · hot" in g["soft_lean"]


def test_soft_allow_glance_anchor_gap_share_quiet() -> None:
    """portfolio AI: low gap ownership speaks quiet · % + vs other strong."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-08T11:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:45:00Z",
                "gate": "rs",
                "reason": "MSFT RS unknown — allow",
            },
            {
                "at": "2026-10-08T10:30:00Z",
                "gate": "regime",
                "reason": "unknown — no SPY bars",
            },
            {
                "at": "2026-10-08T10:00:00Z",
                "gate": "breadth",
                "reason": "unknown scan",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_count"] == 1
    assert g["anchor_gap_last"] == "AAPL"
    assert g["anchor_gap_last_freshness"] == "fresh"
    assert g["anchor_gap_symbol_lead"] == ""
    assert g["anchor_gap_symbol_sample_gap"] == "n=1"
    assert g["anchor_gap_share_pct"] == 25.0
    assert g["anchor_gap_share_severity"] == "quiet"
    assert g["anchor_gap_last_vs_share"] == (
        "clash · fresh · quiet · ×1 · 25%"
    )
    assert g["anchor_gap_last_vs_share_warn"] is True
    assert g["anchor_gap_other_count"] == 3
    assert g["anchor_gap_other_share_pct"] == 75.0
    assert g["anchor_gap_other_share_severity"] == "strong"
    assert g["anchor_gap_vs_other"] == "align · quiet|strong"
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == (
        "align · fresh · quiet|strong · ×1 · 25%"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == (
        "clash · share clash · lean align · ×1 · 25%"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert g["anchor_gap_bit"] == (
        "1 gap · last AAPL · fresh · n=1 · quiet · 25% · "
        "last/share clash · fresh · quiet · ×1 · 25% · vs 3 other · strong · "
        "75% · gap vs other align · quiet|strong · "
        "last/lean align · fresh · quiet|strong · ×1 · 25% · "
        "share/lean clash · share clash · lean align · ×1 · 25%"
    )
    assert (
        "1 gap · last AAPL · fresh · n=1 · quiet · 25% · "
        "last/share clash · fresh · quiet · ×1 · 25% · vs 3 other · strong · "
        "75% · gap vs other align · quiet|strong · "
        "last/lean align · fresh · quiet|strong · ×1 · 25% · "
        "share/lean clash · share clash · lean align · ×1 · 25%"
    ) in g["line"]
    assert g["last_vs_lead_freshness"] == (
        "last/lead align · fresh · agree · ×2 · 50%"
    )
    assert "last/lead rs" in g["soft_lean_meta"]
    assert "last/lead align fresh agree ×2 50%" in g["soft_lean_meta"]
    assert "n=1 quiet 25%" in g["soft_lean_meta"]
    # last/share may sit in +N once gate age takes a chip slot.
    assert "last/share clash · fresh · quiet" in g["soft_lean"]
    # gap/other may sit in +N once last/lead takes a chip slot.
    assert "gap vs other align · quiet|strong" in g["soft_lean"]


def test_soft_allow_glance_anchor_gap_vs_other_clash() -> None:
    """Sides alone ≠ lean: gap hot + other mid speaks clash (junk_vs_ok)."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-08T11:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:30:00Z",
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last"] == "AAPL"
    assert g["anchor_gap_last_freshness"] == "fresh"
    assert g["anchor_gap_last_vs_share"] == "align · fresh · hot · ×1 · 50%"
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_symbol_lead"] == ""
    assert g["anchor_gap_symbol_sample_gap"] == "n=1"
    assert g["anchor_gap_other_share_severity"] == "ok"
    assert g["anchor_gap_vs_other"] == "clash · gap hot · other ok"
    assert g["anchor_gap_vs_other_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == (
        "clash · fresh · gap hot · other ok · ×1 · 50%"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is True
    assert g["anchor_gap_last_share_vs_lean"] == (
        "clash · share align · lean clash · ×1 · 50%"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert "1 gap · last AAPL · fresh · n=1 · hot · 50%" in g["anchor_gap_bit"]
    assert "last/share align · fresh · hot" in g["anchor_gap_bit"]
    assert "gap vs other clash · gap hot · other ok" in g["anchor_gap_bit"]
    assert "last/lean clash · fresh · gap hot · other ok" in g["anchor_gap_bit"]
    assert (
        "share/lean clash · share align · lean clash" in g["anchor_gap_bit"]
    )
    assert "gap vs other clash · gap hot · other ok" in g["line"]


def test_soft_allow_glance_anchor_gap_last_freshness_aging() -> None:
    """Cursor name ≠ live fail-open: aging/expired speak after last SYM."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": aging,
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_last"] == "AAPL"
    assert g["anchor_gap_last_freshness"] == "aging"
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last_vs_share"] == ""
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_vs_other_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == ""
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == ""
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    # Hot share / lean clash escalate tone; severity stays aging (not hot).
    assert g["severity"] == "aging"
    assert g["tone"] == "warn"
    assert g["anchor_gap_bit"].startswith("1 gap · last AAPL · aging · n=1")
    assert "n=1 hot 50% vs 1 other 50%" in g["soft_lean_meta"]
    assert "last AAPL · aging" in g["line"]
    assert "last/share" not in g["anchor_gap_bit"]
    assert "last/lean" not in g["anchor_gap_bit"]
    assert "share/lean" not in g["anchor_gap_bit"]


def test_soft_allow_glance_anchor_gap_expired_tone_warn() -> None:
    """RyanJHamby age≠severity: expired gap cursor warns; cool-off stays cool."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    other = {
        "at": stale,
        "gate": "rs",
        "reason": "SPY RS unknown — allow",
    }
    g = build_soft_allow_glance(
        [
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            other,
            {**other, "reason": "MSFT RS unknown — allow"},
            {**other, "reason": "NVDA RS unknown — allow"},
        ],
        now=now,
    )
    assert g["anchor_gap_last_freshness"] == "expired"
    assert g["anchor_gap_share_severity"] == "quiet"
    assert g["anchor_gap_last_vs_share"] == (
        "align · expired · quiet · ×1 · 25%"
    )
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == (
        "clash · expired · quiet|strong · ×1 · 25%"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is True
    assert g["anchor_gap_last_share_vs_lean"] == (
        "clash · share align · lean clash · ×1 · 25%"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert g["severity"] == "cool"
    assert g["tone"] == "warn"
    assert "last AAPL · expired" in g["anchor_gap_bit"]
    assert "last/share align · expired · quiet" in g["anchor_gap_bit"]
    assert "last/lean clash · expired · quiet|strong" in g["anchor_gap_bit"]
    assert (
        "share/lean clash · share align · lean clash" in g["anchor_gap_bit"]
    )


def test_soft_allow_glance_anchor_gap_last_vs_share_clash_tone() -> None:
    """Cursor age ≠ ownership heat: expired·hot clash warns (cool-off cool)."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": stale,
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_last_freshness"] == "expired"
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last_vs_share"] == (
        "clash · expired · hot · ×1 · 50%"
    )
    assert g["anchor_gap_last_vs_share_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == (
        "align · expired · gap hot · other ok · ×1 · 50%"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == (
        "clash · share clash · lean align · ×1 · 50%"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert g["severity"] == "cool"
    assert g["tone"] == "warn"
    assert "last/share clash · expired · hot" in g["anchor_gap_bit"]
    assert "last/share clash · expired · hot" in g["line"]
    assert "last/lean align · expired · gap hot · other ok" in g["line"]
    assert "share/lean clash · share clash · lean align" in g["line"]


def test_soft_allow_glance_anchor_gap_aging_quiet_stays_flat() -> None:
    """Aging quiet gap label alone does not escalate (expired/hot/clash do)."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    other = {
        "at": aging,
        "gate": "rs",
        "reason": "SPY RS unknown — allow",
    }
    g = build_soft_allow_glance(
        [
            {
                "at": aging,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            other,
            {**other, "reason": "MSFT RS unknown — allow"},
            {**other, "reason": "NVDA RS unknown — allow"},
        ],
        now=now,
    )
    assert g["anchor_gap_last_freshness"] == "aging"
    assert g["anchor_gap_share_severity"] == "quiet"
    assert g["anchor_gap_last_vs_share"] == ""
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == ""
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == ""
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    assert g["severity"] == "aging"
    assert g["tone"] == "flat"


def test_soft_allow_glance_truncates_reason() -> None:
    long = "x" * 100
    g = build_soft_allow_glance([{"at": "t", "gate": "rs", "reason": long}])
    assert g["ready"] is True
    assert g["last_reason"].endswith("…")
    assert len(g["last_reason"]) <= 72


def test_soft_allow_glance_speaks_aging() -> None:
    """xang1234 / RyanJHamby: aging (>12h) speaks before expired."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient history"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["count"] == 2
    assert g["fresh_count"] == 1
    assert g["aging_count"] == 1
    assert g["expired_count"] == 0
    assert g["fresh_tally"] == "rs×1"
    assert g["aging_tally"] == "breadth×1"
    assert g["expired_tally"] == ""
    assert g["severity"] == "hot"
    assert g["tone"] == "warn"
    assert g["line"].startswith("hot · ")
    assert "2 soft-allows" in g["line"]
    assert "1 fresh" in g["line"]
    assert "rs×1" in g["line"]
    assert "1 aging" in g["line"]
    assert "breadth×1" in g["line"]
    assert "expired" not in g["line"]
    assert "[rs]" in g["line"]


def test_soft_allow_glance_consolidates_expired() -> None:
    """tradermonty #437: expired soft-allows speak count + gate tally."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient history"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
            {"at": stale, "gate": "regime", "reason": "unknown — no SPY bars"},
            {"at": stale, "gate": "regime", "reason": "unknown — no BTC bars"},
        ],
        now=now,
        fresh_hours=24.0,
    )
    assert g["count"] == 4
    assert g["fresh_count"] == 1
    assert g["aging_count"] == 1
    assert g["expired_count"] == 2
    assert g["fresh_tally"] == "rs×1"
    assert g["aging_tally"] == "breadth×1"
    assert g["expired_tally"] == "regime×2"
    assert g["severity"] == "hot"
    assert g["tone"] == "warn"
    assert g["line"].startswith("hot · ")
    assert "4 soft-allows" in g["line"]
    assert "1 fresh" in g["line"]
    assert "rs×1" in g["line"]
    assert "1 aging" in g["line"]
    assert "breadth×1" in g["line"]
    assert "2 expired" in g["line"]
    assert "regime×2" in g["line"]
    assert "[rs]" in g["line"]


def test_soft_allow_glance_aging_tally_only() -> None:
    """Aging-only ledger consolidates gates like the expired all-expired path."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": aging, "gate": "breadth", "reason": "unknown scan a"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan b"},
            {"at": aging, "gate": "rs", "reason": "insufficient history"},
        ],
        now=now,
    )
    assert g["aging_count"] == 3
    assert g["expired_count"] == 0
    assert g["fresh_tally"] == ""
    assert g["aging_tally"] == "breadth×2 · rs×1"
    assert g["severity"] == "aging"
    assert g["tone"] == "flat"
    assert g["lead_bit"] == (
        "breadth leads · aging · ×2 · 67% · ahead thin · +1 · vs rs ×1 · 33% · share Δ wide · +33pp"
    )
    assert g["lead_runner_gate"] == "rs"
    assert g["lead_runner_count"] == 1
    assert g["lead_runner_share_pct"] == 33.3
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert g["lead_share_vs_delta"] == ""
    assert g["line"].startswith(
        "aging · breadth leads · aging · ×2 · 67% · ahead thin · +1 · vs rs ×1 · 33% · "
        "share Δ wide · +33pp · "
    )
    assert "3 soft-allows" in g["line"]
    assert "3 aging" in g["line"]
    assert "breadth×2" in g["line"]
    assert "rs×1" in g["line"]
    assert "fresh" not in g["line"]
    assert "expired" not in g["line"]


def test_soft_allow_glance_fresh_tally_mixed() -> None:
    """portfolio AI + xang1234: fresh gate tally beside aging/expired."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "regime", "reason": "no SPY bars"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["fresh_count"] == 2
    assert g["aging_count"] == 1
    assert g["fresh_tally"] == "regime×1 · rs×1"
    assert "2 fresh" in g["line"]
    assert "regime×1" in g["line"]
    assert "rs×1" in g["line"]
    assert "1 aging" in g["line"]


def test_soft_allow_glance_fresh_tally_multi_recent() -> None:
    """All-fresh multi-gate ledger consolidates without aging noise."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["fresh_count"] == 3
    assert g["aging_count"] == 0
    assert g["expired_count"] == 0
    assert g["fresh_tally"] == "rs×2 · breadth×1"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×2 · 67% · ahead thin · +1 · vs breadth ×1 · 33% · "
        "share Δ wide · +33pp"
    )
    assert g["lead_runner_gate"] == "breadth"
    assert g["lead_runner_count"] == 1
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert "3 recent soft-allows" in g["line"]
    assert "rs×2" in g["line"]
    assert "breadth×1" in g["line"]
    assert "aging" not in g["line"]
    assert "expired" not in g["line"]


def test_soft_allow_glance_all_expired() -> None:
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": stale, "gate": "promote", "reason": "ABC: skip_no_bars"},
            {"at": stale, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["expired_count"] == 2
    assert g["fresh_count"] == 0
    assert g["aging_count"] == 0
    assert g["severity"] == "cool"
    assert g["tone"] == "flat"
    assert g["line"].startswith("cool · ")
    assert "2 expired soft-allows" in g["line"]
    assert "breadth×1" in g["line"]
    assert "promote×1" in g["line"]


def test_soft_allow_glance_cool_off_severity_triad() -> None:
    """portfolio AI + xang1234: hot / aging / cool — expired is not warn."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = (now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hot = build_soft_allow_glance(
        [{"at": fresh, "gate": "rs", "reason": "insufficient"}],
        now=now,
    )
    cooling = build_soft_allow_glance(
        [{"at": aging, "gate": "breadth", "reason": "unknown scan"}],
        now=now,
    )
    cool = build_soft_allow_glance(
        [{"at": stale, "gate": "regime", "reason": "no SPY bars"}],
        now=now,
    )
    assert (hot["severity"], hot["tone"]) == ("hot", "warn")
    assert (cooling["severity"], cooling["tone"]) == ("aging", "flat")
    assert (cool["severity"], cool["tone"]) == ("cool", "flat")
    assert hot["lead_bit"] == ""
    assert cooling["lead_bit"] == ""
    assert cool["lead_bit"] == ""


def test_soft_allow_glance_lead_gate_hot() -> None:
    """portfolio AI concentration: dominant fresh gate after severity."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["severity"] == "hot"
    assert g["lead_gate"] == "rs"
    assert g["lead_count"] == 2
    assert g["lead_share_pct"] == 66.7
    assert g["lead_margin"] == 1
    assert g["lead_margin_severity"] == "thin"
    assert g["lead_runner_gate"] == "breadth"
    assert g["lead_runner_count"] == 1
    assert g["lead_band"] == "fresh"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×2 · 67% · ahead thin · +1 · vs breadth ×1 · 33% · share Δ wide · +33pp"
    )
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert g["lead_share_vs_delta"] == ""
    assert g["lead_vs_config"] == ""
    assert g["line"].startswith(
        "hot · rs leads · fresh · ×2 · 67% · ahead thin · +1 · vs breadth ×1 · 33% · "
        "share Δ wide · +33pp · "
    )
    assert "rs×2" in g["line"]


def test_soft_allow_glance_lead_vs_config_off() -> None:
    """tradermonty #576: lead rs vs RS toggle speaks clash|agree."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [
        {"at": fresh, "gate": "rs", "reason": "insufficient a"},
        {"at": fresh, "gate": "rs", "reason": "insufficient b"},
        {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
    ]
    on = build_soft_allow_glance(
        rows, now=now, runtime={"rs_gate": True, "breadth_gate": True}
    )
    assert on["lead_vs_config"] == "agree · lead rs · ×2 · 67% · RS on"
    assert "agree · lead rs · ×2 · 67% · RS on" in on["line"]
    assert "agree · lead rs · ×2 · 67% · RS on" in on["soft_lean"]
    # Newest row matches lead → last/lead agree rides the lean chip.
    assert on["last_vs_lead"] == "agree · last rs · lead rs · ×2 · 67%"
    assert on["last_lead_vs_config"] == (
        "last/config align · both agree · ×2 · 67%"
    )
    assert on["last_lead_vs_config_warn"] is False
    # Fresh + agree → last/lead + lead/config age align (calm).
    assert on["last_vs_lead_freshness"] == (
        "last/lead align · fresh · agree · ×2 · 67%"
    )
    assert on["last_vs_lead_freshness_warn"] is False
    assert on["lead_vs_config_freshness"] == (
        "lead/config align · fresh · on · ×2 · 67%"
    )
    assert on["lead_vs_config_freshness_warn"] is False
    assert on["last_lead_vs_config_freshness"] == (
        "last/config age align · both align · fresh · ×2 · 67%"
    )
    assert on["last_lead_vs_config_freshness_warn"] is False
    assert on["soft_lean_warn"] is False
    assert on["soft_lean_meta"] == (
        "quiet · 6 folds · lead/config rs ×2 67% on · last/lead rs ×2 67% · "
        "last/config align both agree ×2 67% · "
        "last/lead align fresh agree ×2 67% · +2"
    )
    assert on["line"].index("rs leads") < on["line"].index(
        "agree · lead rs · ×2 · 67% · RS on"
    )
    assert on["tone"] == "warn"  # hot severity already warns; agree does not escalate
    off = build_soft_allow_glance(
        rows, now=now, runtime={"rs_gate": False, "breadth_gate": True}
    )
    assert off["lead_gate"] == "rs"
    assert off["lead_vs_config"] == "clash · lead rs · ×2 · 67% · RS off"
    assert "clash · lead rs · ×2 · 67% · RS off" in off["line"]
    assert "clash · lead rs · ×2 · 67% · RS off" in off["soft_lean"]
    # last matches lead + config off → crossed (last agree · config clash).
    assert off["last_vs_lead"] == "agree · last rs · lead rs · ×2 · 67%"
    assert off["last_lead_vs_config"] == (
        "last/config clash · last agree · config clash · ×2 · 67%"
    )
    assert off["last_lead_vs_config_warn"] is True
    assert off["last_vs_lead_freshness"] == (
        "last/lead align · fresh · agree · ×2 · 67%"
    )
    # Fresh + config off → lead/config age clash (live knob disagree).
    assert off["lead_vs_config_freshness"] == (
        "lead/config clash · fresh · off · ×2 · 67%"
    )
    assert off["lead_vs_config_freshness_warn"] is True
    assert off["last_lead_vs_config_freshness"] == (
        "last/config age clash · last/lead align · lead/config clash · "
        "fresh · ×2 · 67%"
    )
    assert off["last_lead_vs_config_freshness_warn"] is True
    assert off["soft_lean_warn"] is True
    assert off["soft_lean_meta"] == (
        "clash · lead/config rs ×2 67% off · last/lead rs ×2 67% · "
        "last/config clash last agree config clash ×2 67% · "
        "last/lead align fresh agree ×2 67% · +2"
    )
    assert off["line"].index("rs leads") < off["line"].index(
        "clash · lead rs · ×2 · 67% · RS off"
    )
    assert off["tone"] == "warn"
    # Aging-only ring stays flat until config clash escalates.
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cooling = build_soft_allow_glance(
        [
            {"at": aging, "gate": "rs", "reason": "insufficient a"},
            {"at": aging, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
        runtime={"rs_gate": False},
    )
    assert cooling["severity"] == "aging"
    assert cooling["lead_vs_config"] == "clash · lead rs · ×2 · 100% · RS off"
    assert cooling["tone"] == "warn"
    # Config clash alone opens the lean fold (no gen-clash / RS-gap).
    # Aging extremes stay silent on last/lead freshness.
    assert cooling["last_vs_lead"] == "agree · last rs · lead rs · ×2 · 100%"
    assert cooling["last_vs_lead_freshness"] == ""
    assert cooling["lead_vs_config_freshness"] == ""
    assert cooling["last_lead_vs_config_freshness"] == ""
    assert cooling["last_lead_vs_config"] == (
        "last/config clash · last agree · config clash · ×2 · 100%"
    )
    assert cooling["soft_lean"] == (
        "clash · lead rs · ×2 · 100% · RS off · "
        "agree · last rs · lead rs · ×2 · 100% · "
        "last/config clash · last agree · config clash · ×2 · 100%"
    )
    assert cooling["soft_lean_warn"] is True
    assert cooling["soft_lean_meta"] == (
        "clash · lead/config rs ×2 100% off · last/lead rs ×2 100% · "
        "last/config clash last agree config clash ×2 100%"
    )
    # Agree on aging does not escalate flat → warn.
    cooling_on = build_soft_allow_glance(
        [
            {"at": aging, "gate": "rs", "reason": "insufficient a"},
            {"at": aging, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
        runtime={"rs_gate": True},
    )
    assert cooling_on["severity"] == "aging"
    assert cooling_on["lead_vs_config"] == "agree · lead rs · ×2 · 100% · RS on"
    assert cooling_on["tone"] == "flat"
    assert cooling_on["last_lead_vs_config"] == (
        "last/config align · both agree · ×2 · 100%"
    )
    assert cooling_on["soft_lean"] == (
        "agree · lead rs · ×2 · 100% · RS on · "
        "agree · last rs · lead rs · ×2 · 100% · "
        "last/config align · both agree · ×2 · 100%"
    )
    assert cooling_on["soft_lean_warn"] is False
    assert cooling_on["soft_lean_meta"] == (
        "quiet · 3 folds · lead/config rs ×2 100% on · last/lead rs ×2 100% · "
        "last/config align both agree ×2 100%"
    )
    # Expired + RS on → stale knob agree warns (last/lead freshness parity).
    expired = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_on = build_soft_allow_glance(
        [
            {"at": expired, "gate": "rs", "reason": "insufficient a"},
            {"at": expired, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
        runtime={"rs_gate": True},
    )
    assert stale_on["lead_vs_config"] == "agree · lead rs · ×2 · 100% · RS on"
    assert stale_on["lead_vs_config_freshness"] == (
        "lead/config clash · expired · on · ×2 · 100%"
    )
    assert stale_on["lead_vs_config_freshness_warn"] is True
    assert stale_on["last_vs_lead_freshness"] == (
        "last/lead clash · expired · agree · ×2 · 100%"
    )
    assert stale_on["last_lead_vs_config_freshness"] == (
        "last/config age align · both clash · expired · ×2 · 100%"
    )
    assert stale_on["last_lead_vs_config_freshness_warn"] is True
    assert stale_on["tone"] == "warn"
    assert "lead/config clash · expired · on" in stale_on["soft_lean"]
    assert stale_on["soft_lean_warn"] is True
    # Stale both-clash pins the clock so expired agree ≠ a live off.
    assert stale_on["soft_lean_meta"].startswith(
        "clash · last/config age align both clash expired ×2 100%"
    )
    # Dual clash: newest ≠ lead + Ops off — both-clash pins on the chip.
    dual = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
        runtime={"rs_gate": False, "breadth_gate": True},
    )
    assert dual["last_vs_lead"] == "last vs lead · breadth · ×2 · 67%"
    assert dual["lead_vs_config"] == "clash · lead rs · ×2 · 67% · RS off"
    assert dual["last_lead_vs_config"] == (
        "last/config align · both clash · ×2 · 67%"
    )
    assert dual["last_lead_vs_config_warn"] is True
    assert dual["last_vs_lead_freshness"] == (
        "last/lead clash · fresh · vs breadth · ×2 · 67%"
    )
    assert dual["last_vs_lead_freshness_warn"] is True
    assert dual["lead_vs_config_freshness"] == (
        "lead/config clash · fresh · off · ×2 · 67%"
    )
    assert dual["lead_vs_config_freshness_warn"] is True
    assert dual["last_lead_vs_config_freshness"] == (
        "last/config age align · both clash · fresh · ×2 · 67%"
    )
    assert dual["last_lead_vs_config_freshness_warn"] is True
    assert dual["soft_lean_warn"] is True
    assert dual["soft_lean_meta"] == (
        "clash · last/config align both clash ×2 67% · "
        "last/config age align both clash fresh ×2 67% · "
        "lead/config rs ×2 67% off · "
        "last/lead breadth ×2 67% · +2"
    )


def test_soft_allow_glance_lead_gate_aging() -> None:
    """Aging severity drives lead from the aging band (not expired)."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": aging, "gate": "breadth", "reason": "unknown scan a"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan b"},
            {"at": aging, "gate": "rs", "reason": "insufficient history"},
        ],
        now=now,
    )
    assert g["severity"] == "aging"
    assert g["lead_gate"] == "breadth"
    assert g["lead_count"] == 2
    assert g["lead_share_pct"] == 66.7
    assert g["lead_margin"] == 1
    assert g["lead_margin_severity"] == "thin"
    assert g["lead_runner_gate"] == "rs"
    assert g["lead_runner_count"] == 1
    assert g["lead_band"] == "aging"
    assert g["lead_bit"] == (
        "breadth leads · aging · ×2 · 67% · ahead thin · +1 · vs rs ×1 · 33% · share Δ wide · +33pp"
    )
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert g["line"].startswith(
        "aging · breadth leads · aging · ×2 · 67% · ahead thin · +1 · vs rs ×1 · 33% · "
        "share Δ wide · +33pp · "
    )


def test_soft_allow_glance_lead_gate_tie_silent() -> None:
    """Tied top gates stay silent — no false concentration."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "regime", "reason": "no SPY a"},
            {"at": fresh, "gate": "regime", "reason": "no SPY b"},
        ],
        now=now,
    )
    assert g["fresh_tally"] == "regime×2 · rs×2"
    assert g["lead_bit"] == ""
    assert g["lead_gate"] == ""
    assert g["lead_share_pct"] is None
    assert g["lead_margin"] is None
    assert g["lead_margin_severity"] == ""
    assert g["lead_runner_gate"] == ""
    assert g["lead_runner_count"] == 0
    assert g["lead_share_delta_pp"] is None
    assert g["lead_share_delta_severity"] == ""
    assert "leads" not in g["line"]


def test_soft_allow_glance_lead_gate_cool_expired() -> None:
    """Cool severity drives lead from the expired band."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": stale, "gate": "regime", "reason": "no SPY bars"},
            {"at": stale, "gate": "regime", "reason": "no BTC bars"},
            {"at": stale, "gate": "promote", "reason": "ABC: skip_no_bars"},
        ],
        now=now,
    )
    assert g["severity"] == "cool"
    assert g["lead_gate"] == "regime"
    assert g["lead_count"] == 2
    assert g["lead_share_pct"] == 66.7
    assert g["lead_margin"] == 1
    assert g["lead_margin_severity"] == "thin"
    assert g["lead_runner_gate"] == "promote"
    assert g["lead_runner_count"] == 1
    assert g["lead_band"] == "expired"
    assert g["lead_bit"] == (
        "regime leads · expired · ×2 · 67% · ahead thin · +1 · vs promote ×1 · 33% · "
        "share Δ wide · +33pp"
    )
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert g["line"].startswith(
        "cool · regime leads · expired · ×2 · 67% · ahead thin · +1 · vs promote ×1 · 33% · "
        "share Δ wide · +33pp · "
    )


def test_soft_allow_glance_lead_margin_wide() -> None:
    """Wide ahead when lead clears #2 by ≥2 (share ≠ margin)."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "rs", "reason": "insufficient c"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["lead_margin"] == 2
    assert g["lead_margin_severity"] == "wide"
    assert g["lead_runner_gate"] == "breadth"
    assert g["lead_runner_count"] == 1
    assert g["lead_runner_share_pct"] == 25.0
    assert g["lead_share_delta_pp"] == 50.0
    assert g["lead_share_delta_severity"] == "wide"
    assert g["lead_share_vs_delta"] == "align"
    assert g["lead_share_vs_delta_ahead"] == "wide"
    assert g["lead_share_vs_delta_share"] == "wide"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×3 · 75% · ahead wide · +2 · vs breadth ×1 · 25% · "
        "share Δ wide · +50pp · share vs Δ align · wide"
    )
    assert g["line"].startswith(
        "hot · rs leads · fresh · ×3 · 75% · ahead wide · +2 · vs breadth ×1 · 25% · "
        "share Δ wide · +50pp · share vs Δ align · wide · "
    )


def test_soft_allow_glance_lead_sole_no_ahead() -> None:
    """Sole-gate 100% share still omits ahead (no runner-up)."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
    )
    assert g["lead_share_pct"] == 100.0
    assert g["lead_margin"] is None
    assert g["lead_margin_severity"] == ""
    assert g["lead_runner_gate"] == ""
    assert g["lead_runner_count"] == 0
    assert g["lead_bit"] == "rs leads · fresh · ×2 · 100%"
    assert "ahead" not in g["lead_bit"]
    assert "vs " not in g["lead_bit"]
    assert g["lead_runner_share_pct"] is None
    assert g["lead_share_delta_pp"] is None
    assert g["lead_share_delta_severity"] == ""
    assert g["lead_share_vs_delta"] == ""
    assert "share Δ" not in g["lead_bit"]


def test_soft_allow_glance_lead_share_delta_mid_clash() -> None:
    """Mid ownership spread: share Δ silent; share vs Δ clash speaks."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "a"},
            {"at": fresh, "gate": "rs", "reason": "b"},
            {"at": fresh, "gate": "rs", "reason": "c"},
            {"at": fresh, "gate": "rs", "reason": "d"},
            {"at": fresh, "gate": "regime", "reason": "e"},
            {"at": fresh, "gate": "regime", "reason": "f"},
            {"at": fresh, "gate": "regime", "reason": "g"},
        ],
        now=now,
    )
    assert g["lead_share_pct"] == 57.1
    assert g["lead_runner_share_pct"] == 42.9
    assert g["lead_share_delta_pp"] is None
    assert g["lead_share_delta_severity"] == ""
    assert g["lead_share_vs_delta"] == "clash"
    assert g["lead_share_vs_delta_ahead"] == "thin"
    assert g["lead_share_vs_delta_share"] == "mid"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×4 · 57% · ahead thin · +1 · vs regime ×3 · 43% · "
        "share vs Δ clash · ahead thin · share mid"
    )
    assert "share Δ" not in g["lead_bit"]


def test_soft_allow_glance_lead_share_delta_thin() -> None:
    """Thin ownership spread speaks when |Δ| < 10pp; align when ahead thin."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": f"a{i}"}
            for i in range(6)
        ]
        + [
            {"at": fresh, "gate": "regime", "reason": f"b{i}"}
            for i in range(5)
        ],
        now=now,
    )
    assert g["lead_share_delta_pp"] == 9.0
    assert g["lead_share_delta_severity"] == "thin"
    assert g["lead_share_vs_delta"] == "align"
    assert g["lead_share_vs_delta_ahead"] == "thin"
    assert g["lead_share_vs_delta_share"] == "thin"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×6 · 54% · ahead thin · +1 · vs regime ×5 · 46% · "
        "share Δ thin · +9pp · share vs Δ align · thin"
    )


def test_soft_allow_glance_last_vs_lead() -> None:
    """Newest gate vs band lead — FinRobot last ≠ ring tilt (LAYA parity)."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Newest print is breadth; fresh band still led by rs.
    clash = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
    )
    assert clash["lead_gate"] == "rs"
    assert clash["last_gate"] == "breadth"
    assert clash["last_vs_lead"] == "last vs lead · breadth · ×2 · 67%"
    assert clash["last_vs_lead_freshness"] == (
        "last/lead clash · fresh · vs breadth · ×2 · 67%"
    )
    assert "last vs lead · breadth" in clash["line"]
    assert "last vs lead · breadth" in clash["soft_lean"]
    assert clash["soft_lean_warn"] is True
    assert clash["soft_lean_meta"] == (
        "clash · last/lead breadth ×2 67% · "
        "last/lead clash fresh vs breadth ×2 67%"
    )
    assert clash["line"].startswith(
        "hot · rs leads · fresh · ×2 · 67% · ahead thin · +1 · vs breadth ×1 · 33% · "
        "share Δ wide · +33pp · last vs lead · breadth · "
    )
    # Last≠lead clash alone opens the lean fold (no gen-clash / RS-gap).
    # Aging ring + newest gate ≠ lead stays flat on glance tone;
    # aging stays silent on last/lead freshness.
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cooling = build_soft_allow_glance(
        [
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
            {"at": aging, "gate": "rs", "reason": "insufficient a"},
            {"at": aging, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
    )
    assert cooling["severity"] == "aging"
    assert cooling["last_vs_lead"] == "last vs lead · breadth · ×2 · 67%"
    assert cooling["last_vs_lead_freshness"] == ""
    assert cooling["tone"] == "flat"  # last≠lead does not escalate tone
    assert cooling["soft_lean"] == "last vs lead · breadth · ×2 · 67%"
    assert cooling["soft_lean_warn"] is True
    assert cooling["soft_lean_meta"] == "clash · last/lead breadth ×2 67%"

    # Newest matches lead — speak agree (silent confirm hid match).
    match = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert match["lead_gate"] == "rs"
    assert match["last_gate"] == "rs"
    assert match["last_vs_lead"] == "agree · last rs · lead rs · ×2 · 67%"
    assert match["last_vs_lead_freshness"] == (
        "last/lead align · fresh · agree · ×2 · 67%"
    )
    assert "agree · last rs · lead rs" in match["line"]
    assert "agree · last rs · lead rs" in match["soft_lean"]
    assert match["soft_lean_warn"] is False
    assert match["soft_lean_meta"] == (
        "quiet · 2 folds · last/lead rs ×2 67% · "
        "last/lead align fresh agree ×2 67%"
    )
    assert "last vs lead" not in match["line"]

    # Expired + agree → stale match warns (gap last/lead freshness parity).
    expired = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_agree = build_soft_allow_glance(
        [
            {"at": expired, "gate": "rs", "reason": "insufficient a"},
            {"at": expired, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
    )
    assert stale_agree["severity"] == "cool"
    assert stale_agree["last_vs_lead"] == "agree · last rs · lead rs · ×2 · 100%"
    assert stale_agree["last_vs_lead_freshness"] == (
        "last/lead clash · expired · agree · ×2 · 100%"
    )
    assert stale_agree["last_vs_lead_freshness_warn"] is True
    assert stale_agree["tone"] == "warn"
    assert stale_agree["soft_lean_warn"] is True
    assert (
        "last/lead clash · expired · agree · ×2 · 100%"
        in stale_agree["soft_lean"]
    )
    assert stale_agree["soft_lean_meta"] == (
        "clash · last/lead rs ×2 100% · "
        "last/lead clash expired agree ×2 100%"
    )

    # No lead (thin) — speak n=1 (last-row ≠ ring tilt; LAYA sample-gap parity).
    thin = build_soft_allow_glance(
        [{"at": fresh, "gate": "breadth", "reason": "unknown scan"}],
        now=now,
    )
    assert thin["lead_gate"] == ""
    assert thin["last_vs_lead"] == ""
    assert thin["sample_gap"] == "n=1"
    assert "n=1" in thin["line"]
    assert thin["line"].startswith("hot · n=1 · ")
    assert "last vs lead" not in thin["line"]
    assert "agree" not in thin["line"]

    # No lead (ties) — speak tied (≥2 in band, no strict winner).
    tied = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert tied["lead_gate"] == ""
    assert tied["sample_gap"] == "tied"
    assert "tied" in tied["line"]
    assert tied["line"].startswith("hot · tied · ")
    assert "leads" not in tied["line"]

    # Lead cases stay silent on sample_gap.
    assert match["sample_gap"] == ""
    assert "n=1" not in match["line"]
    assert "tied" not in match["line"]


def test_soft_allow_glance_scan_clash_expired_vs_fresh() -> None:
    """xang1234 #549: expired soft-allow ≠ fresh scan → clash · scan fresh."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — allow",
            }
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert g["ready"] is True
    assert g["last_freshness"] == "stale"
    assert g["scan_freshness"] == "fresh"
    assert g["scan_vs_soft_allow_clash"] == (
        "clash · scan fresh · soft-only · scan-only"
    )
    assert g["tone"] == "warn"
    assert g["severity"] == "cool"
    assert g["line"].startswith(
        "cool · clash · scan fresh · soft-only · scan-only"
    )
    assert "clash" in g["line"]
    assert g["line_core"].startswith("cool · ")
    assert "clash · scan" not in g["line_core"]
    assert g["soft_lean"].startswith(
        "clash · scan fresh · soft-only · scan-only"
    )
    assert g["soft_lean_warn"] is True
    assert g["soft_lean_meta"].startswith("clash · scan")
    assert "soft-only" in g["soft_lean_meta"]
    assert "scan-only" in g["soft_lean_meta"]
    same = build_soft_allow_glance(
        [
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — allow",
            }
        ],
        now=now,
        scan_time=expired_at,
        scan_interval_sec=900,
    )
    assert same["scan_freshness"] == "stale"
    assert same["scan_vs_soft_allow_clash"] == ""
    # Soft↔scan same band — soft≠cash may still speak (pinned print age).
    assert "clash · scan" not in same["line"]
    if same["soft_vs_cash_clock_clash"]:
        assert same["tone"] == "warn"
        assert same["soft_vs_cash_clock_clash"] in same["line"]
    else:
        assert same["tone"] == "flat"


def test_soft_allow_glance_scan_clash_fresh_vs_stale() -> None:
    """Fresh fail-open vs stale scan → clash · scan stale (mixed generation)."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_scan = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "breadth",
                "reason": "unknown breadth — allow",
            }
        ],
        now=now,
        scan_time=stale_scan,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == "stale"
    assert g["scan_vs_soft_allow_clash"] == (
        "clash · scan stale · soft-only · scan-only"
    )
    assert g["tone"] == "warn"
    assert g["line"].startswith(
        "hot · clash · scan stale · soft-only · scan-only"
    )
    # Soft ring share lied soft coverage was the archive; pins stay
    # soft-only · scan-only even when the soft ring is mixed.
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    mixed = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "breadth",
                "reason": "unknown breadth — allow",
            },
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — allow",
            },
        ],
        now=now,
        scan_time=stale_scan,
        scan_interval_sec=900,
    )
    assert mixed["scan_vs_soft_allow_clash"] == (
        "clash · scan stale · soft-only · scan-only"
    )
    assert "soft-only" in mixed["soft_lean_meta"]
    assert "scan-only" in mixed["soft_lean_meta"]
    assert "×1" not in mixed["scan_vs_soft_allow_clash"]


def test_soft_allow_glance_gap_vs_scan_when_last_matches_scan() -> None:
    """xang1234 #549/e3c84e1: soft-allow last matching scan ≠ live gap cursor."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    # Soft-allow last matches scan — no ring-level clash.
    assert g["scan_vs_soft_allow_clash"] == ""
    # Soft last ≠ gap cursor — close the generation triangle; soft matches
    # scan so keep scan-only (peer soft keep-scan-only / #660).
    assert g["soft_vs_gap_clock_clash"] == (
        "clash · soft fresh · gap expired · soft-only · gap-only · scan-only"
    )
    assert g["soft_vs_gap_clock_clash_warn"] is True
    assert (
        "clash · soft fresh · gap expired · soft-only · gap-only · scan-only"
        in g["line"]
    )
    # Gap cursor is a different generation — speak both sides; soft≠gap
    # names soft-only · gap-only; gap≠scan names gap-only · scan-only.
    assert g["anchor_gap_vs_scan_clash"] == (
        "clash · gap expired · scan fresh · gap-only · scan-only"
    )
    assert g["anchor_gap_vs_scan_clash_warn"] is True
    assert g["tone"] == "warn"
    assert "clash · gap expired · scan fresh · gap-only · scan-only" in (
        g["anchor_gap_bit"]
    )
    assert "last AAPL · expired · clash · gap expired · scan fresh" in (
        g["anchor_gap_bit"]
    )
    same = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert same["soft_vs_gap_clock_clash"] == ""
    assert same["soft_vs_gap_clock_clash_warn"] is False
    assert "clash · soft fresh · gap" not in same["line"]
    assert "clash · soft stale · gap" not in same["line"]
    assert same["anchor_gap_vs_scan_clash"] == ""
    assert same["anchor_gap_vs_scan_clash_warn"] is False
    # Soft↔gap + gap↔scan silent; soft≠cash / gap≠cash may still speak
    # and keep scan-only when the archive match is silent; soft≠cash also
    # keeps gap-only when soft matches the gap cursor; gap≠cash keeps
    # soft-only after scan-only (#660 speak-both-sides).
    assert "clash · gap" not in same["anchor_gap_bit"] or "scan fresh" not in (
        same["anchor_gap_bit"]
    )
    if same["soft_vs_cash_clock_clash"]:
        assert same["soft_vs_cash_clock_clash"] in same["line"]
        assert " · scan-only" in same["soft_vs_cash_clock_clash"]
        assert same["soft_vs_cash_clock_clash"].endswith(" · gap-only")
    if same["anchor_gap_vs_cash_clock_clash"]:
        assert same["anchor_gap_vs_cash_clock_clash"] in same["anchor_gap_bit"]
        assert " · scan-only" in same["anchor_gap_vs_cash_clock_clash"]
        assert same["anchor_gap_vs_cash_clock_clash"].endswith(" · soft-only")


def test_soft_allow_glance_soft_vs_gap_same_when_last_is_gap() -> None:
    """When soft last *is* the gap row, soft≠gap stays silent."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "MSFT RS unknown — anchor gap — allow",
            }
        ],
        now=now,
    )
    assert g["last_freshness"] == "stale"
    assert g["anchor_gap_last_freshness"] == "expired"
    assert g["soft_vs_gap_clock_clash"] == ""
    assert g["soft_vs_gap_clock_clash_warn"] is False
    assert "clash · soft" not in g["line"]


def test_soft_allow_glance_soft_vs_cash_when_soft_matches_scan() -> None:
    """xang1234 #549: soft matching scan ≠ pinned cash print generation."""
    # Saturday afternoon UTC — both cash sleeves last-published; US Fri
    # close is ~17h ago → cash aging while a fresh soft-allow + fresh
    # scan archive stay soft↔scan silent.
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            }
        ],
        now=now,
        scan_time=fresh_at,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    assert g["scan_vs_soft_allow_clash"] == ""
    cash = g["soft_vs_cash_clock_clash"]
    assert cash.startswith("clash · soft fresh · cash ")
    # Soft-only then cash pin sleeve (not soft ring): sole → venue-only;
    # dual half → named venue · 50%; both same band → ×2 · 100%; soft
    # matches scan → keep scan-only (#647 / #531 / #660; peer soft keep
    # scan-only parity; gap≠* own+other pin parity).
    assert " · soft-only · " in cash
    assert cash.endswith(" · scan-only")
    assert (
        " · US-only · scan-only" in cash
        or " · Xetra-only · scan-only" in cash
        or " · US · 50% · scan-only" in cash
        or " · Xetra · 50% · scan-only" in cash
        or " · ×2 · 100% · scan-only" in cash
    )
    assert g["soft_vs_cash_clock_clash_warn"] is True
    assert cash in g["line"]
    assert g["tone"] == "warn"
    # Same-evening last-published: soft fresh + cash fresh → silent.
    even = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    even_at = (even - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    same = build_soft_allow_glance(
        [
            {
                "at": even_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            }
        ],
        now=even,
        scan_time=even_at,
        scan_interval_sec=900,
    )
    assert same["last_freshness"] == "fresh"
    assert same["soft_vs_cash_clock_clash"] == ""
    assert same["soft_vs_cash_clock_clash_warn"] is False
    assert "cash" not in same["line"] or "clash · soft" not in same["line"]


def test_soft_allow_glance_gap_vs_cash_when_soft_matches_cash() -> None:
    """xang1234 #549: soft≠cash can still hide gap≠cash on the gap bit."""
    # Saturday afternoon UTC — cash sleeves last-published (US aging).
    # Soft last aging (12–24h) matches cash aging → soft≠cash silent;
    # expired gap cursor ≠ cash → gap≠cash speaks on the gap bit.
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    aging_at = (now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Fresh scan archive so soft aging ≠ scan is a separate bit; gap≠cash
    # still speaks on the gap bit after gap≠scan.
    fresh_scan = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "aging"
    assert g["anchor_gap_last_freshness"] == "expired"
    assert g["soft_vs_cash_clock_clash"] == ""
    # Soft matches cash → keep cash pin on soft≠scan / soft≠gap so those
    # bits cannot hide the match (keep-scan-only parity + #660 / #647).
    soft_scan = g["scan_vs_soft_allow_clash"]
    # _clock_clash names the other sleeve only (scan …); soft pin follows.
    assert soft_scan.startswith("clash · scan fresh · soft-only · scan-only · ")
    assert (
        soft_scan.endswith("US-only")
        or soft_scan.endswith("Xetra-only")
        or soft_scan.endswith("US · 50%")
        or soft_scan.endswith("Xetra · 50%")
        or soft_scan.endswith("×2 · 100%")
    )
    soft_gap = g["soft_vs_gap_clock_clash"]
    assert soft_gap.startswith(
        "clash · soft aging · gap expired · soft-only · gap-only · "
    )
    assert (
        soft_gap.endswith("US-only")
        or soft_gap.endswith("Xetra-only")
        or soft_gap.endswith("US · 50%")
        or soft_gap.endswith("Xetra · 50%")
        or soft_gap.endswith("×2 · 100%")
    )
    gap_cash = g["anchor_gap_vs_cash_clock_clash"]
    assert gap_cash.startswith("clash · gap expired · cash ")
    # Gap-only sole cursor pin; cash pin names coverage (#647 / #531).
    assert " · gap-only · " in gap_cash
    assert (
        gap_cash.endswith(" · US-only")
        or gap_cash.endswith(" · Xetra-only")
        or gap_cash.endswith(" · US · 50%")
        or gap_cash.endswith(" · Xetra · 50%")
        or gap_cash.endswith(" · ×2 · 100%")
    )
    assert g["anchor_gap_vs_cash_clock_clash_warn"] is True
    assert gap_cash in g["anchor_gap_bit"]
    assert g["tone"] == "warn"
    # Same-evening last-published: gap fresh + cash fresh → silent.
    even = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    even_at = (even - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    same = build_soft_allow_glance(
        [
            {
                "at": even_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            }
        ],
        now=even,
        scan_time=even_at,
        scan_interval_sec=900,
    )
    assert same["anchor_gap_last_freshness"] == "fresh"
    assert same["anchor_gap_vs_cash_clock_clash"] == ""
    assert same["anchor_gap_vs_cash_clock_clash_warn"] is False
    assert "cash" not in same["anchor_gap_bit"] or "clash · gap" not in (
        same["anchor_gap_bit"]
    )


def test_soft_allow_glance_vs_memory_clock_clash() -> None:
    """xang1234 #549: soft matching scan ≠ live LAYA/debate print."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — allow",
            }
        ],
        now=now,
        scan_time=fresh_at,
        scan_interval_sec=900,
        laya_freshness="stale",
        debate_freshness="aging",
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_vs_soft_allow_clash"] == ""
    assert g["laya_freshness"] == "stale"
    assert g["debate_freshness"] == "aging"
    assert g["soft_vs_memory_clock_clash"] == (
        "clash · laya stale · debate aging · soft-only · ×2 · 100% · scan-only"
    )
    assert g["soft_vs_memory_clock_clash_warn"] is True
    assert g["tone"] == "warn"
    assert "clash · laya stale · debate aging" in g["line"]

    # Same band as soft — silent (no false mixed-generation warn).
    same = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — allow",
            }
        ],
        now=now,
        scan_time=fresh_at,
        scan_interval_sec=900,
        laya_freshness="fresh",
        debate_freshness="fresh",
    )
    assert same["soft_vs_memory_clock_clash"] == ""
    assert same["soft_vs_memory_clock_clash_warn"] is False
    assert "clash · laya" not in same["line"]
    assert "clash · debate" not in same["line"]

    # Only debate disagrees — soft-only then half-owner pin (dual
    # advisory configured; soft ring size no longer rides).
    one = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "breadth",
                "reason": "unknown breadth — allow",
            }
        ],
        now=now,
        laya_freshness="fresh",
        debate_freshness="stale",
    )
    assert one["soft_vs_memory_clock_clash"] == (
        "clash · debate stale · soft-only · debate · 50%"
    )
    assert one["soft_vs_memory_clock_clash_warn"] is True
    assert "clash · debate stale" in one["line"]
    assert "laya" not in one["soft_vs_memory_clock_clash"].split(" · debate ")[0]

    # Sole configured advisory that clashes → soft-only · debate-only.
    sole = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "breadth",
                "reason": "unknown breadth — allow",
            }
        ],
        now=now,
        laya_freshness="",
        debate_freshness="stale",
    )
    assert sole["soft_vs_memory_clock_clash"] == (
        "clash · debate stale · soft-only · debate-only"
    )


def test_soft_allow_glance_soft_vs_memory_keeps_cash_when_soft_matches_cash() -> None:
    """Soft matching cash keeps cash pin on soft≠memory (#660 / #647)."""
    # Saturday afternoon UTC — soft aging matches cash aging; fresh scan
    # ≠ soft so keep-scan does not ride soft≠memory; stale debate ≠ soft
    # → soft≠memory speaks and must keep the cash pin.
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    aging_at = (now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_scan = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            }
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
        laya_freshness="",
        debate_freshness="stale",
    )
    assert g["last_freshness"] == "aging"
    assert g["soft_vs_cash_clock_clash"] == ""
    assert g["scan_vs_soft_allow_clash"].startswith(
        "clash · scan fresh · soft-only · scan-only · "
    )
    mem = g["soft_vs_memory_clock_clash"]
    assert mem.startswith("clash · debate stale · soft-only · debate-only · ")
    assert (
        mem.endswith("US-only")
        or mem.endswith("Xetra-only")
        or mem.endswith("US · 50%")
        or mem.endswith("Xetra · 50%")
        or mem.endswith("×2 · 100%")
    )
    assert " · scan-only" not in mem
    assert mem in g["line"]
    assert g["tone"] == "warn"


def test_soft_allow_glance_soft_keeps_gap_when_soft_matches_gap() -> None:
    """Soft matching gap keeps gap-only on soft≠scan / soft≠memory (#660)."""
    # Saturday afternoon UTC — soft last is the gap cursor (same stamp)
    # → soft≠gap silent; fresh scan ≠ soft → soft≠scan keeps gap-only;
    # stale debate ≠ soft → soft≠memory keeps gap-only (and cash when
    # soft also matches cash). LAYA keep gap-only + soft keep-cash mirror.
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    aging_at = (now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_scan = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            }
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
        laya_freshness="",
        debate_freshness="stale",
    )
    assert g["last_freshness"] == "aging"
    assert g["anchor_gap_last_freshness"] == "aging"
    assert g["soft_vs_gap_clock_clash"] == ""
    soft_scan = g["scan_vs_soft_allow_clash"]
    assert soft_scan.startswith("clash · scan fresh · soft-only · scan-only · ")
    assert soft_scan.endswith(" · gap-only")
    mem = g["soft_vs_memory_clock_clash"]
    assert mem.startswith("clash · debate stale · soft-only · debate-only · ")
    assert mem.endswith(" · gap-only")
    assert " · scan-only" not in mem
    assert soft_scan in g["line"] or soft_scan in (g.get("soft_lean") or "")
    assert mem in g["line"] or mem in (g.get("soft_lean") or "")
    assert g["tone"] == "warn"


def test_soft_allow_glance_gap_keeps_soft_when_gap_matches_soft() -> None:
    """Gap matching soft keeps soft-only on gap≠scan / gap≠memory (#660)."""
    # Saturday afternoon UTC — soft last is the gap cursor (same stamp)
    # → soft≠gap silent; fresh scan ≠ gap → gap≠scan keeps soft-only;
    # stale debate ≠ gap → gap≠memory keeps soft-only (soft≠* keep
    # gap-only speak-both-sides + #660 / #647 / #531). Cash keep may
    # also ride when gap matches cash.
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    aging_at = (now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_scan = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            }
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
        laya_freshness="",
        debate_freshness="stale",
    )
    assert g["soft_vs_gap_clock_clash"] == ""
    assert g["anchor_gap_last_freshness"] == "aging"
    gap_scan = g["anchor_gap_vs_scan_clash"]
    assert gap_scan.startswith(
        "clash · gap aging · scan fresh · gap-only · scan-only · "
    )
    assert gap_scan.endswith(" · soft-only")
    gap_mem = g["anchor_gap_vs_memory_clock_clash"]
    assert gap_mem.startswith(
        "clash · gap aging · debate stale · gap-only · debate-only · "
    )
    assert gap_mem.endswith(" · soft-only")
    assert " · scan-only" not in gap_mem
    assert gap_scan in g["anchor_gap_bit"]
    assert gap_mem in g["anchor_gap_bit"]
    assert g["tone"] == "warn"


def test_soft_allow_glance_gap_keeps_cash_when_gap_matches_cash() -> None:
    """Gap matching cash keeps cash pin on gap≠scan / gap≠memory (#660)."""
    # Saturday afternoon UTC — cash last-published aging. Gap aging
    # matches cash → gap≠cash silent; fresh scan ≠ gap → gap≠scan keeps
    # cash; stale debate ≠ gap → gap≠memory keeps cash (soft≠* keep-cash
    # mirror + #660 / #647 / #531). Soft also matches gap → soft-only
    # rides after cash (gap keep soft-only speak-both-sides).
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    aging_at = (now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_scan = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            }
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
        laya_freshness="",
        debate_freshness="stale",
    )
    assert g["anchor_gap_last_freshness"] == "aging"
    assert g["anchor_gap_vs_cash_clock_clash"] == ""
    gap_scan = g["anchor_gap_vs_scan_clash"]
    assert gap_scan.startswith(
        "clash · gap aging · scan fresh · gap-only · scan-only · "
    )
    assert gap_scan.endswith(" · soft-only")
    assert (
        "US-only" in gap_scan
        or "Xetra-only" in gap_scan
        or "US · 50%" in gap_scan
        or "Xetra · 50%" in gap_scan
        or "×2 · 100%" in gap_scan
    )
    gap_mem = g["anchor_gap_vs_memory_clock_clash"]
    assert gap_mem.startswith(
        "clash · gap aging · debate stale · gap-only · debate-only · "
    )
    assert gap_mem.endswith(" · soft-only")
    assert (
        "US-only" in gap_mem
        or "Xetra-only" in gap_mem
        or "US · 50%" in gap_mem
        or "Xetra · 50%" in gap_mem
        or "×2 · 100%" in gap_mem
    )
    assert " · scan-only" not in gap_mem
    assert gap_scan in g["anchor_gap_bit"]
    assert gap_mem in g["anchor_gap_bit"]
    assert g["tone"] == "warn"


def test_soft_allow_glance_soft_keeps_memory_when_soft_matches_memory() -> None:
    """Soft matching advisory keeps memory pin on soft≠scan / soft≠gap (#660)."""
    # Soft aging matches dual fresh→aging advisories → soft≠memory silent;
    # fresh scan ≠ soft → soft≠scan keeps ×2 · 100%; soft≠gap silent when
    # gap cursor is the same stamp (gap keep-memory speak-both-sides below).
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    aging_at = (now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_scan = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            }
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
        laya_freshness="aging",
        debate_freshness="aging",
    )
    assert g["last_freshness"] == "aging"
    assert g["soft_vs_memory_clock_clash"] == ""
    soft_scan = g["scan_vs_soft_allow_clash"]
    assert soft_scan.startswith("clash · scan fresh · soft-only · scan-only · ")
    assert soft_scan.endswith(" · ×2 · 100%")
    assert " · debate-only" not in soft_scan
    assert soft_scan in g["line"] or soft_scan in (g.get("soft_lean") or "")
    # Sole advisory match → debate-only on soft≠scan.
    sole = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "breadth",
                "reason": "unknown breadth — allow",
            }
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
        laya_freshness="",
        debate_freshness="aging",
    )
    assert sole["soft_vs_memory_clock_clash"] == ""
    assert sole["scan_vs_soft_allow_clash"].endswith(" · debate-only")
    assert g["tone"] == "warn"


def test_soft_allow_glance_gap_keeps_memory_when_gap_matches_memory() -> None:
    """Gap matching advisory keeps memory pin on gap≠scan (#660)."""
    # Soft/gap aging matches dual aging advisories → gap≠memory silent;
    # fresh scan ≠ gap → gap≠scan keeps ×2 · 100% after soft-only / cash.
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    aging_at = (now - timedelta(hours=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_scan = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            }
        ],
        now=now,
        scan_time=fresh_scan,
        scan_interval_sec=900,
        laya_freshness="aging",
        debate_freshness="aging",
    )
    assert g["anchor_gap_last_freshness"] == "aging"
    assert g["anchor_gap_vs_memory_clock_clash"] == ""
    gap_scan = g["anchor_gap_vs_scan_clash"]
    assert gap_scan.startswith(
        "clash · gap aging · scan fresh · gap-only · scan-only · "
    )
    assert gap_scan.endswith(" · ×2 · 100%")
    assert gap_scan in g["anchor_gap_bit"]
    assert g["tone"] == "warn"


def test_memory_advisory_pin_size_matched() -> None:
    """Keep-memory pins matching sleeves; clash mode still disagrees only."""
    from openbb_backend.desk import memory_advisory_pin_size

    assert (
        memory_advisory_pin_size(
            own_clock="fresh",
            laya_freshness="fresh",
            debate_freshness="fresh",
            matched=True,
        )
        == " · ×2 · 100%"
    )
    assert (
        memory_advisory_pin_size(
            own_clock="aging",
            laya_freshness="",
            debate_freshness="aging",
            matched=True,
        )
        == " · debate-only"
    )
    assert (
        memory_advisory_pin_size(
            own_clock="fresh",
            laya_freshness="fresh",
            debate_freshness="stale",
            matched=True,
        )
        == " · laya · 50%"
    )
    assert (
        memory_advisory_pin_size(
            own_clock="fresh",
            laya_freshness="stale",
            debate_freshness="stale",
            matched=True,
        )
        == ""
    )
    assert (
        memory_advisory_pin_size(
            own_clock="fresh",
            laya_freshness="stale",
            debate_freshness="",
        )
        == " · laya-only"
    )


def test_soft_allow_glance_gap_vs_memory_when_soft_matches_memory() -> None:
    """xang1234 #549: soft≠memory can still hide gap≠memory on the gap bit."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Soft last fresh matches laya/debate fresh → soft≠memory silent;
    # expired gap cursor ≠ memory → gap≠memory speaks on the gap bit.
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
        scan_time=fresh_at,
        scan_interval_sec=900,
        laya_freshness="fresh",
        debate_freshness="fresh",
    )
    assert g["last_freshness"] == "fresh"
    assert g["soft_vs_memory_clock_clash"] == ""
    assert g["anchor_gap_last_freshness"] == "expired"
    gap_mem = g["anchor_gap_vs_memory_clock_clash"]
    assert gap_mem == (
        "clash · gap expired · laya fresh · debate fresh · "
        "gap-only · ×2 · 100%"
    )
    assert g["anchor_gap_vs_memory_clock_clash_warn"] is True
    assert gap_mem in g["anchor_gap_bit"]
    assert g["tone"] == "warn"
    # Same band as gap (expired≡stale) — silent.
    same = build_soft_allow_glance(
        [
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            }
        ],
        now=now,
        laya_freshness="stale",
        debate_freshness="stale",
    )
    assert same["anchor_gap_vs_memory_clock_clash"] == ""
    assert same["anchor_gap_vs_memory_clock_clash_warn"] is False
    assert "laya" not in same["anchor_gap_bit"]
    assert "debate" not in same["anchor_gap_bit"]


def test_soft_allow_lean_fold_in_templates_css_charts() -> None:
    """Desk + Charts render soft lean fold (Yahoo mix lean parity)."""
    root = Path(__file__).resolve().parents[1]
    macros = (root / "openbb_backend/templates/macros.html").read_text(
        encoding="utf-8"
    )
    assert "soft-allow-lean" in macros
    assert "soft_lean_meta" in macros
    assert "line_core" in macros
    css = (root / "openbb_backend/static/desk.css").read_text(encoding="utf-8")
    assert ".soft-allow-glance .soft-allow-lean" in css
    charts = (root / "openbb_backend/static/charts.js").read_text(
        encoding="utf-8"
    )
    assert "soft_lean" in charts
    assert "soft-allow-lean" in charts
    assert "line_core" in charts
