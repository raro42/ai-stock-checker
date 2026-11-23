"""Optional LAYA / JEV System-1 typed decisions (advisory, fail-open).

Mirrors QuantDinger's JEV pre-trade pattern and open-source Laya
(``system_one`` typed choice / score / noul) without installing torch or
ONNX into the paper stack.

When ``LAYA_BASE_URL`` or ``JEV_BASE_URL`` is set and ``LAYA_ADVISORY=1``,
validate-mode may POST a paper-entry question set and record the typed
answer. Provider errors / missing config **fail open** — never block exits
and never gate buys in this slice. Live entry veto is deferred (see docs/LAYA.md).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from stock_checker.technical_indicators import (
    _finite_signed,
    _valid_close,
    _valid_volume,
    coerce_score,
    daily_pct_change,
)

DECISION_FILE = "laya_decisions.json"
DECISION_CAP = 40
_DEFAULT_REASON_CHARS = 120
_DEFAULT_MODEL_CHARS = 80


def _coerce_decision_cap(
    value: object, default: int = DECISION_CAP
) -> int:
    """Ring retention length, or ``default`` when bool/gap.

    FinRobot + QuantDinger/JEV + tradermonty #700/#655 + xang1234/portfolio AI:
    ``int(True)→1`` / ``False→0→max(1,0)→1`` must not invent a one-row
    advisory ring (AI-validate memory retention peer).
    """
    from stock_checker.technical_indicators import coerce_nonneg_int

    n = coerce_nonneg_int(value)
    if n is None:
        return int(default)
    return n


def _coerce_clip_chars(
    value: object, default: int
) -> int:
    """Positive reason/model char ceiling, or ``default`` when bool/gap/≤0.

    FinRobot + QuantDinger/JEV + tradermonty #700/#655 + xang1234/portfolio AI:
    ``True→1`` must not invent a one-char Ops reason (`o…`) or model strip;
    ``False→0`` must not wipe via ``s[:-1]`` (AI-validate reason clip peer —
    ring cap alone left reason/model ceilings open).
    """
    from stock_checker.technical_indicators import coerce_nonneg_int

    n = coerce_nonneg_int(value)
    if n is None or n <= 0:
        return int(default)
    return n


def _clip(text: object, n: object, *, default: int) -> str:
    limit = _coerce_clip_chars(n, default)
    s = str(text or "").strip()
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"


# Paper-entry System-1 questions (Jev / Laya compatible).
PAPER_ENTRY_QUESTIONS: dict[str, Any] = {
    "entry": {
        "type": "choice",
        "instructions": (
            "Should we paper-buy this name given harsh fees and anti-churn rules?"
        ),
        "criteria": {
            "pass": "clear edge; worth a paper buy",
            "hold": "unclear or weak — wait",
            "reject": "avoid; chase, junk, or fee-unfriendly",
        },
    },
    "edge": {
        "type": "score",
        "instructions": "How strong is the entry edge after fees?",
        "criteria": ["none", "thin", "ok", "strong"],
    },
    "fee_churn": {
        "type": "noul",
        "instructions": "Is this likely fee-churn or flip-flop risk?",
    },
}


Transport = Callable[[str, dict[str, Any], dict[str, str], float], dict[str, Any]]


def _env_truthy(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


def laya_base_url() -> str:
    """Prefer LAYA_BASE_URL; accept JEV_BASE_URL (QuantDinger / TypeSafe)."""
    for key in ("LAYA_BASE_URL", "JEV_BASE_URL"):
        raw = (os.getenv(key) or "").strip().rstrip("/")
        if raw:
            return raw
    return ""


def laya_api_key() -> str:
    for key in ("LAYA_API_KEY", "JEV_API_KEY"):
        raw = (os.getenv(key) or "").strip()
        if raw:
            return raw
    return ""


def laya_model() -> str:
    return (os.getenv("LAYA_MODEL") or os.getenv("JEV_MODEL") or "systemone").strip() or (
        "systemone"
    )


def laya_timeout_sec() -> float:
    raw = os.getenv("LAYA_TIMEOUT_SECONDS") or os.getenv("JEV_TIMEOUT_SECONDS") or "8"
    try:
        return max(1.0, float(raw))
    except (TypeError, ValueError):
        return 8.0


def laya_configured() -> bool:
    return bool(laya_base_url())


def laya_advisory_enabled() -> bool:
    """Advisory recording on when URL set and LAYA_ADVISORY truthy (default off)."""
    return laya_configured() and _env_truthy("LAYA_ADVISORY", default=False)


def decision_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / DECISION_FILE


def build_paper_entry_state(stock_data: dict[str, Any]) -> str:
    """Compact state text for System-1 (no secrets)."""
    symbol = str(stock_data.get("symbol") or "Unknown")
    name = str(stock_data.get("name") or symbol)
    price = stock_data.get("current_price")
    prev = stock_data.get("previous_close")
    hi = stock_data.get("52_week_high")
    lo = stock_data.get("52_week_low")
    pe = stock_data.get("pe_ratio")
    volume = stock_data.get("volume")
    strategy = stock_data.get("strategy") or stock_data.get("signal") or ""

    # Missing/bool/gap → n/a (never invent flat +0.00 / True→$1 / True P/E).
    # Daily% already refused; raw Price/Prev/52w/PE/Volume lines were still open.
    def _money_bit(raw: object) -> str:
        if not _valid_close(raw):
            return "n/a"
        return f"{float(raw):,.2f}"

    daily = daily_pct_change(price, prev)
    daily_bit = f"{daily:+.2f}" if daily is not None else "n/a"
    lines = [
        f"Paper desk candidate: {name} ({symbol})",
        f"Price: {_money_bit(price)}  PrevClose: {_money_bit(prev)}  Daily%: {daily_bit}",
        f"52w High/Low: {_money_bit(hi)} / {_money_bit(lo)}",
        "Fees: Revolut-like ~0.25%/side · €1 min; min hold ≥24h; no loss-rotation.",
        "Live crypto buys: BTC/ETH only. Prefer HOLD over weak BUY.",
    ]
    if _finite_signed(pe):
        lines.append(f"P/E: {float(pe):.2f}")
    if _valid_volume(volume):
        lines.append(f"Volume: {float(volume):,.0f}")
    if strategy:
        lines.append(f"Scanner strategy: {strategy}")
    return "\n".join(lines)


def _http_transport(
    url: str, body: dict[str, Any], headers: dict[str, str], timeout: float
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("system_one response is not an object")
    return parsed


def parse_system_one_answers(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize Laya / Jev ``answers`` into a flat advisory dict."""
    answers = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(answers, dict):
        answers = payload if isinstance(payload, dict) else {}

    entry = answers.get("entry") if isinstance(answers.get("entry"), dict) else {}
    edge = answers.get("edge") if isinstance(answers.get("edge"), dict) else {}
    fee = answers.get("fee_churn") if isinstance(answers.get("fee_churn"), dict) else {}

    choice = str(entry.get("choice") or entry.get("selected") or "").strip().lower()
    if choice not in {"pass", "hold", "reject"}:
        choice = ""

    probs = entry.get("probabilities")
    if not isinstance(probs, dict):
        probs = {}

    # tradermonty #700/#655 + xang1234/portfolio AI: refuse bool/gap invent
    # (True→1.0 edge / 100% fee churn / True→1.0 probs).
    edge_f = coerce_score(edge.get("score"))

    noul = fee.get("noul")
    if noul is None:
        noul = fee.get("probability")
    fee_churn = float(noul) if _finite_signed(noul) else None  # type: ignore[arg-type]

    return {
        "entry": choice or None,
        "probabilities": {
            str(k): float(v) for k, v in probs.items() if _finite_signed(v)
        },
        "edge_score": edge_f,
        "fee_churn": fee_churn,
    }


def evaluate_paper_entry(
    stock_data: dict[str, Any],
    *,
    transport: Transport | None = None,
    questions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call System-1 for one paper candidate. Always fail-open on error.

    Returns keys: ok, fail_open, reason, entry, probabilities, edge_score,
    fee_churn, latency_ms, provider, model, symbol.
    """
    symbol = str(stock_data.get("symbol") or "")
    base = laya_base_url()
    out: dict[str, Any] = {
        "ok": False,
        "fail_open": True,
        "reason": "",
        "entry": None,
        "probabilities": {},
        "edge_score": None,
        "fee_churn": None,
        "latency_ms": None,
        "provider": "laya",
        "model": laya_model(),
        "symbol": symbol,
    }
    if not base:
        out["reason"] = "not_configured"
        return out
    if not _env_truthy("LAYA_ADVISORY", default=False):
        out["reason"] = "advisory_off"
        return out

    url = f"{base}/v1/systemone"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    key = laya_api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    body = {
        "state": build_paper_entry_state(stock_data),
        "questions": questions or PAPER_ENTRY_QUESTIONS,
        "model": laya_model(),
    }
    started = datetime.now(timezone.utc)
    try:
        fn = transport or _http_transport
        payload = fn(url, body, headers, laya_timeout_sec())
        parsed = parse_system_one_answers(payload)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds() * 1000.0
        out.update(parsed)
        out["latency_ms"] = round(elapsed, 1)
        if not out.get("entry"):
            out["reason"] = "invalid_choice"
            out["fail_open"] = True
            out["ok"] = False
            return out
        out["ok"] = True
        out["fail_open"] = False
        out["reason"] = "ok"
        return out
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        out["reason"] = f"provider_error:{type(exc).__name__}"
        return out
    except (ValueError, json.JSONDecodeError, TypeError, KeyError) as exc:
        out["reason"] = f"parse_error:{type(exc).__name__}"
        return out


def load_laya_decisions(data_dir: Path | str) -> list[dict[str, Any]]:
    path = decision_path(data_dir)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    events = raw.get("events") if isinstance(raw, dict) else None
    if not isinstance(events, list):
        return []
    return [e for e in events if isinstance(e, dict)]


def record_laya_decision(
    data_dir: Path | str,
    result: dict[str, Any],
    *,
    symbol: str | None = None,
    cap: object = DECISION_CAP,
    reason_n: object = _DEFAULT_REASON_CHARS,
    model_n: object = _DEFAULT_MODEL_CHARS,
) -> None:
    """Append one advisory row (ring buffer). Never raises to the trader."""
    root = Path(data_dir)
    try:
        root.mkdir(parents=True, exist_ok=True)
        events = load_laya_decisions(root)
        row = {
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "symbol": symbol or result.get("symbol") or "",
            "ok": bool(result.get("ok")),
            "fail_open": bool(result.get("fail_open")),
            # FinRobot/JEV + tradermonty #700/#655: refuse bool clip ceilings —
            # True→1 must not invent a one-char reason/model Ops strip.
            "reason": _clip(
                result.get("reason"), reason_n, default=_DEFAULT_REASON_CHARS
            ),
            "entry": result.get("entry"),
            "edge_score": result.get("edge_score"),
            "fee_churn": result.get("fee_churn"),
            "latency_ms": result.get("latency_ms"),
            "model": _clip(
                result.get("model"), model_n, default=_DEFAULT_MODEL_CHARS
            ),
        }
        events.append(row)
        # AI-validate retention already refused bool; LAYA advisory ring was
        # still open to int(True)→1 / False→0→max(1,0)→1.
        keep = max(1, _coerce_decision_cap(cap))
        events = events[-keep:]
        decision_path(root).write_text(
            json.dumps({"events": events}, indent=2) + "\n", encoding="utf-8"
        )
    except OSError:
        return


def summarize_laya_decisions(data_dir: Path | str) -> dict[str, Any]:
    events = load_laya_decisions(data_dir)
    counts = {"pass": 0, "hold": 0, "reject": 0, "fail_open": 0}
    for e in events:
        if e.get("fail_open") or not e.get("ok"):
            counts["fail_open"] += 1
            continue
        entry = str(e.get("entry") or "").lower()
        if entry in counts:
            counts[entry] += 1
    newest = events[-1] if events else None
    return {
        "count": len(events),
        "pass": counts["pass"],
        "hold": counts["hold"],
        "reject": counts["reject"],
        "fail_open": counts["fail_open"],
        "newest": newest,
    }


def laya_status(data_dir: Path | str | None = None) -> dict[str, Any]:
    """Ops / desk status dict (display only)."""
    root = data_dir if data_dir is not None else Path(os.getenv("DATA_DIR", "data"))
    configured = laya_configured()
    advisory = laya_advisory_enabled()
    stats = summarize_laya_decisions(root) if configured or advisory else {
        "count": 0,
        "pass": 0,
        "hold": 0,
        "reject": 0,
        "fail_open": 0,
        "newest": None,
    }
    return {
        "configured": configured,
        "advisory": advisory,
        "base_url_set": configured,
        "model": laya_model() if configured else "",
        "stats": stats,
    }


def maybe_advise_paper_entry(
    stock_data: dict[str, Any],
    data_dir: Path | str,
    *,
    transport: Transport | None = None,
) -> dict[str, Any] | None:
    """If advisory is on, evaluate + record; else None. Never raises."""
    if not laya_advisory_enabled():
        return None
    try:
        result = evaluate_paper_entry(stock_data, transport=transport)
        record_laya_decision(data_dir, result, symbol=str(stock_data.get("symbol") or ""))
        return result
    except Exception:
        return {
            "ok": False,
            "fail_open": True,
            "reason": "unexpected_error",
            "entry": None,
            "symbol": str(stock_data.get("symbol") or ""),
        }
