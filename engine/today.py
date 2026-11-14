"""Assemble the Today payload (API-2): digest + same-day alert chips + alert-only stocks.

Alerts (price/volume) come from the latest trading session in the price data; they are shown
whatever the filing window, labelled with their session date. A stock that spiked with no filing
that day appears in `alert_only` (D-040/D-067); one that also filed gets a `moved_same_day` flag
on its filing card instead.
"""
from __future__ import annotations

from datetime import datetime

import config
from engine.alerts import check_alerts
from engine.digest import build_digest
from engine.feed import FeedData, company_name


def _alerts_by_ticker(data: FeedData, price: float, volume: float) -> dict[str, list[dict]]:
    """Run the rule-based alerts for every stock with the user's thresholds."""
    return {
        t: check_alerts(t, df, volume_multiple=volume, price_move_pct=price)
        for t, df in data.prices.items()
    }


def build_today(
    data: FeedData,
    window: str = config.DEFAULT_WINDOW,
    price: float = config.PRICE_MOVE_PCT,
    volume: float = config.VOLUME_MULTIPLE,
    off: set[str] | None = None,
    now: datetime | None = None,
) -> dict:
    """Return the full JSON-ready payload for the Today screen."""
    alerts = _alerts_by_ticker(data, price, volume)
    toggles = {c: False for c in (off or set())}
    digest = build_digest(data.filings, alerts, window, toggles, now)

    filed_days = {(f["ticker"], f["date"][:10]) for f in data.filings}
    alert_only = [
        {**a, "company": company_name(a["ticker"])}
        for t, items in alerts.items()
        for a in items
        if (t, a["date"]) not in filed_days
    ]
    alert_only.sort(key=lambda a: (-abs(a["value"]) if a["type"] == "price" else -a["value"], a["ticker"]))

    return {
        **digest,
        "routine_count": digest["counts"]["routine"],
        "alert_only": alert_only,
        "session_date": _latest_session(data),
        "thresholds": {"price": price, "volume": volume},
        "fallback_used": data.fallback_used,
        "errors": data.errors,
        "data_as_of": data.fetched_at.isoformat(timespec="seconds"),
    }


def _latest_session(data: FeedData) -> str | None:
    """Date of the most recent trading session across all price data."""
    dates = [df["Date"].max() for df in data.prices.values() if len(df)]
    return max(dates).strftime("%Y-%m-%d") if dates else None
