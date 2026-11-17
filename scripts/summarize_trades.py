#!/usr/bin/env python3
"""Summarize paper-trading fees vs realized P&L from trades.jsonl."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path

from stock_checker.promote_ab import (
    WINDOW_A_START_UTC,
    load_trades_jsonl,
    summarize_window_trades,
)


def _parse_since(raw: str | None) -> datetime | None:
    """Parse UTC bound; raise ValueError on garbage (tradermonty #809)."""
    if not raw:
        return None
    text = str(raw).strip()
    if text.lower() in {"window-a", "a", "promote-a"}:
        return WINDOW_A_START_UTC
    try:
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            d = date.fromisoformat(text)
            return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(
            f"invalid date (expected YYYY-MM-DD or ISO datetime): {raw!r}"
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _require_ordered_range(
    start: datetime | None, end: datetime | None
) -> None:
    """Refuse inverted --since/--until so empty windows are not silent ok."""
    if start is not None and end is not None and start > end:
        raise ValueError(
            f"--since {start.date().isoformat()} is later than "
            f"--until {end.date().isoformat()}"
        )


def main() -> None:
    from stock_checker.paper_accounts import (
        AccountIdError,
        account_label,
        ledger_dir,
        normalize_account_id,
    )

    parser = argparse.ArgumentParser(description="Summarize paper trades / fees")
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Data directory (default: data); used with --account",
    )
    parser.add_argument(
        "--account",
        default="",
        help="Named paper account under data/accounts/<id>/ (Mode A)",
    )
    parser.add_argument(
        "--trades",
        default="",
        help="Path to trades.jsonl (default: <ledger>/trades.jsonl)",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="UTC start (ISO date/time, or 'window-a' for promote Window A)",
    )
    parser.add_argument(
        "--until",
        default=None,
        help="UTC end inclusive (ISO date/time)",
    )
    args = parser.parse_args()
    try:
        account_id = normalize_account_id(args.account)
    except AccountIdError as exc:
        raise SystemExit(f"error: {exc}") from exc
    if args.trades:
        path = Path(args.trades)
    else:
        path = ledger_dir(args.data_dir, account_id) / "trades.jsonl"
    if not path.exists():
        print(f"No trades file at {path}")
        return

    try:
        start = _parse_since(args.since)
        end = _parse_since(args.until)
        _require_ordered_range(start, end)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from exc
    # tradermonty #737: UTF-8 via load_trades_jsonl (locale decode is not a ledger).
    try:
        path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"Unreadable trades file (not UTF-8) at {path}")
        raise SystemExit(2) from None
    except OSError as exc:
        print(f"Unreadable trades file at {path}: {exc}")
        raise SystemExit(2) from exc
    trades = load_trades_jsonl(path)

    if start is None and end is None:
        s = summarize_window_trades(
            trades,
            start=datetime(1970, 1, 1, tzinfo=timezone.utc),
        )
        period = f"{s['first']} → {s['last']}"
    else:
        s = summarize_window_trades(
            trades,
            start=start or datetime(1970, 1, 1, tzinfo=timezone.utc),
            end=end,
        )
        period = f"{s['start_utc']} → {s['end_utc'] or s['last']}"

    print("Paper trading summary")
    print(f"  Book: {account_label(account_id)}")
    print(f"  Period: {period}")
    print(f"  Trades: {s['trades']} (buys={s['buys']}, sells={s['sells']})")
    print(f"  Fees paid: €{s['fees']:,.2f}")
    print(f"  Realized P&L (sells): €{s['realized_pnl']:,.2f}")
    print(f"  Net after sell fees: €{s['net_after_sell_fees']:,.2f}")
    print(f"  Net after all fees: €{s['net_after_all_fees']:,.2f}")
    print(f"  Wins/Losses: {s['wins']}/{s['losses']}")
    print(f"  Legs: stock={s['stock_legs']} crypto={s['crypto_legs']}")
    print(
        f"  Closes: stock={s.get('stock_closes', 0)} crypto={s.get('crypto_closes', 0)}"
    )


if __name__ == "__main__":
    main()
