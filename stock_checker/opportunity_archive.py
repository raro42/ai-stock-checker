"""Opportunity archive readiness pin (keep-newest).

Shared by market_scanner cleanup and desk resolve so hard-readers of
``opportunities_latest`` see the newest publish without waiting for the
next scan prune (xang1234 #682 / #685).

A session-shaped publish is never rewritten; heal/resolve therefore refuse
a malformed JSON artifact and index only usable object publishes
(xang1234 8d447fa / 40a968e market-history refuse-malformed + skip-damaged).
"""

from __future__ import annotations

import json
from pathlib import Path


def opportunity_publish_usable(path: Path) -> bool:
    """True when ``path`` is a parseable JSON object (dict).

    Truncated / wrong-container publishes must not become the readiness pin
    or the keep-newest target — presence alone ≠ usable.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(doc, dict)


def timestamped_opportunity_publishes(archive_dir: Path) -> list[Path]:
    """All timestamped opportunity JSON paths, oldest→newest by filename."""
    if not archive_dir.is_dir():
        return []
    return sorted(archive_dir.glob("opportunities_2*.json"))


def usable_opportunity_publishes(archive_dir: Path) -> list[Path]:
    """Timestamped opportunity JSON objects, oldest→newest by filename."""
    return [
        p
        for p in timestamped_opportunity_publishes(archive_dir)
        if opportunity_publish_usable(p)
    ]


def damaged_opportunity_publish_count(archive_dir: Path) -> int:
    """Count timestamped publishes that are not usable JSON objects.

    Silent skip ≠ hide damage — desk speaks this so keep-newest refuse
    does not look like a clean archive (xang1234 40a968e + Screener junk).
    """
    return sum(
        1
        for p in timestamped_opportunity_publishes(archive_dir)
        if not opportunity_publish_usable(p)
    )


def opportunity_damaged_vs_ok_lead(
    damaged: int,
    ok: int,
) -> tuple[str, str, int | None]:
    """Strict lead among damaged vs ok publish counts (display only).

    Absolute ``N damaged`` beside ``vs M ok`` hid which slot type owns the
    archive (xang1234 market-history skip-damaged + claim-drop vs live lead +
    portfolio AI count≠share). Both sides must be >0 and total ≥2; strict
    lead → ``lead damaged · N%`` / ``lead ok · N%``; ties / sole-side →
    silent (use ``opportunity_damaged_vs_ok_sample_gap`` for tied).
    """
    try:
        n_dmg = max(0, int(damaged))
    except (TypeError, ValueError):
        n_dmg = 0
    try:
        n_ok = max(0, int(ok))
    except (TypeError, ValueError):
        n_ok = 0
    total = n_dmg + n_ok
    if total < 2 or n_dmg <= 0 or n_ok <= 0:
        return "", "", None
    if n_dmg == n_ok:
        return "", "", None
    if n_dmg > n_ok:
        name, n = "damaged", n_dmg
    else:
        name, n = "ok", n_ok
    share = int(round(100.0 * n / total))
    return f"lead {name} · {share}%", name, share


def opportunity_damaged_vs_ok_sample_gap(damaged: int, ok: int) -> str:
    """Speak ``damaged/ok tied`` when both sides spoke with no strict lead.

    Prefixed so the bit stays distinct from Yahoo claim ``tied`` /
    ``drop/live tied``. Lead cases / sole-side / zero stay silent.
    Absolute damaged+ok alone hid that a 50/50 archive has no owner.
    Display only.
    """
    lead_bit, _name, _share = opportunity_damaged_vs_ok_lead(damaged, ok)
    if lead_bit:
        return ""
    try:
        n_dmg = max(0, int(damaged))
    except (TypeError, ValueError):
        n_dmg = 0
    try:
        n_ok = max(0, int(ok))
    except (TypeError, ValueError):
        n_ok = 0
    if n_dmg <= 0 or n_ok <= 0:
        return ""
    if n_dmg != n_ok:
        return ""
    return "damaged/ok tied"


def opportunity_damaged_vs_ok_lean(
    damaged_severity: str,
    ok_severity: str,
) -> tuple[str, bool]:
    """Lean agreement of damaged vs ok share bands (display only).

    Absolute sides + ownership lead hid whether the two *severity* bands
    agree (Screener ``junk vs ok`` lean + portfolio AI speak-both-sides).
    Align when ``hot|thin`` or ``quiet|strong``; clash when exactly one
    lean spoke or the pair disagrees. Adverse clash (damaged hot / ok thin
    mismatch, or sole hot/thin) warns. Mid both silent. Desk keeps this in
    ``pin_lean`` so the scan-freshness core clip stays short.
    """
    dmg = str(damaged_severity or "").strip().casefold()
    ok = str(ok_severity or "").strip().casefold()
    dmg_lean = dmg in {"hot", "quiet"}
    ok_lean = ok in {"strong", "thin"}
    if dmg_lean and ok_lean:
        matched = (dmg == "hot" and ok == "thin") or (
            dmg == "quiet" and ok == "strong"
        )
        if matched:
            return f"damaged vs ok align · {dmg}|{ok}", False
        return f"damaged vs ok clash · damaged {dmg} · ok {ok}", True
    if dmg_lean != ok_lean:
        dmg_label = dmg if dmg_lean else (dmg or "ok")
        ok_label = ok if ok_lean else (ok or "ok")
        warn = dmg == "hot" or ok == "thin"
        return (
            f"damaged vs ok clash · damaged {dmg_label} · ok {ok_label}",
            warn,
        )
    return "", False


def opportunity_damaged_vs_ok_delta(
    damaged_share_pct: float | int | None,
    ok_share_pct: float | int | None,
    *,
    lean_bit: str = "",
    wide_pp: float = 20.0,
    thin_pp: float = 10.0,
) -> tuple[int | None, str, str, bool]:
    """Share Δ after damaged vs ok lean (display only).

    Lean alone hid how far ``damaged% − ok%`` sits (Screener junk vs ok
    share Δ + behind-vs-pin Δ + portfolio AI count≠spread). Requires lean
    already spoke. Wide ≥``wide_pp`` · thin <``thin_pp`` · mid →
    ``lean vs Δ clash · lean · Δ mid`` (warn). Adverse
    ``align · hot|thin`` + Δ wide warns; ``quiet|strong`` stays calm.

    Returns ``(delta_pp, delta_severity, lean_vs_delta, lean_vs_delta_warn)``.
    """
    if not str(lean_bit or "").strip():
        return None, "", "", False
    if damaged_share_pct is None or ok_share_pct is None:
        return None, "", "", False
    try:
        dmg = float(damaged_share_pct)
        ok = float(ok_share_pct)
    except (TypeError, ValueError):
        return None, "", "", False
    raw = int(round(dmg - ok))
    abs_delta = abs(raw)
    delta_sev = ""
    if abs_delta >= wide_pp:
        delta_sev = "wide"
    elif abs_delta < thin_pp:
        delta_sev = "thin"
    if delta_sev:
        lean_vs_delta = f"align · {delta_sev}"
        lean_vs_delta_warn = delta_sev == "wide" and str(lean_bit).startswith(
            "damaged vs ok align · hot|thin"
        )
        return raw, delta_sev, lean_vs_delta, lean_vs_delta_warn
    return raw, "", "clash · lean · Δ mid", True


def opportunity_damaged_vs_ok_delta_lead(
    delta_pp: int | None,
    delta_severity: str,
    *,
    lean_vs_delta: str = "",
) -> str:
    """Name which slot type owns a spoken damaged vs ok Δ (display only).

    When lean vs Δ already spoke with a Δ (wide|thin) and ±pp ≠ 0,
    positive ``damaged% − ok%`` → ``damaged``; negative → ``ok``. Mid-Δ
    clash / 0pp stay silent. Signed pp alone hid which archive slot type
    owns the spread (Screener unique vs dup / Yahoo mix / Window A sleeve
    Δ lead + portfolio AI speak-both-sides). Returns ``damaged|ok`` / ``\"\"``.
    """
    if not str(lean_vs_delta or "").startswith("align ·"):
        return ""
    if str(delta_severity or "").strip().casefold() not in {"wide", "thin"}:
        return ""
    if delta_pp is None:
        return ""
    try:
        pp = int(delta_pp)
    except (TypeError, ValueError):
        return ""
    if pp == 0:
        return ""
    return "damaged" if pp > 0 else "ok"


def newest_usable_opportunity_publish(archive_dir: Path) -> Path | None:
    """Newest filename among usable timestamped publishes (or None)."""
    usable = usable_opportunity_publishes(archive_dir)
    return usable[-1] if usable else None


def heal_opportunities_latest_pin(archive_dir: Path) -> bool:
    """Retarget ``*_latest`` to the newest *usable* timestamped publish.

    Filename sort matches desk ``resolve_opportunities_archive`` (not mtime).
    Malformed / wrong-container JSON is skipped so heal never promotes junk
    over a good older publish. Returns True when a pin was created or
    retargeted.
    """
    if not archive_dir.is_dir():
        return False
    newest = newest_usable_opportunity_publish(archive_dir)
    if newest is None:
        return False
    healed = False
    for latest_name, target in (
        ("opportunities_latest.json", newest),
        (
            "opportunities_latest.txt",
            newest.with_suffix(".txt")
            if newest.with_suffix(".txt").exists()
            else None,
        ),
    ):
        if target is None or not target.exists():
            continue
        latest = archive_dir / latest_name
        need = True
        if latest.is_symlink() or latest.is_file():
            try:
                if latest_name.endswith(".json") and latest.exists():
                    # Live pin on a damaged artifact must retarget even when
                    # the symlink name already matches a junk path.
                    if not opportunity_publish_usable(latest.resolve()):
                        need = True
                    else:
                        need = latest.resolve() != target.resolve()
                else:
                    need = (not latest.exists()) or (
                        latest.resolve() != target.resolve()
                    )
            except OSError:
                need = True
        if not need:
            continue
        try:
            if latest.exists() or latest.is_symlink():
                latest.unlink()
            latest.symlink_to(target.name)
            healed = True
        except OSError as exc:
            print(f"⚠️  Could not heal {latest_name}: {exc}")
    if healed:
        print(f"📌 Healed opportunities_latest → {newest.name}")
    return healed
