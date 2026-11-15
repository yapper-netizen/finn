"""Ranker (EN-3) + category toggles (EN-18): classify, assign a tier, order by what matters.

Order: tier (High > Medium > Low), then "also moved/spiked that day" boost, then newest.
A toggled-off category, or one the user moved to Routine, drops to Low (Routine). The user can also
raise or lower a category's tier in Settings (`tiers`); a category they put in High gets the "alert" chip. A High category that is toggled on gets an
"alert" chip (D-047). The price/volume boost never changes the tier, only the order and a flag.
"""
from __future__ import annotations

from datetime import datetime

import config
from engine.classifier import buried_reason, classify, tier_of


def _same_day_alert(filing_date: str, alerts: list[dict]) -> bool:
    """True if the stock crossed a price/volume alert on the filing's calendar day."""
    day = filing_date[:10]
    return any(a.get("date") == day for a in alerts)


def rank_filings(
    filings: list[dict],
    alerts_by_ticker: dict[str, list[dict]] | None = None,
    toggles: dict[str, bool] | None = None,
    tiers: dict[str, str] | None = None,
) -> list[dict]:
    """Return filings enriched with category/tier/chips, most important first.

    Each input filing needs `ticker`, `date` (ISO), `title`, `category` (NSE label).
    Added keys: `kind` (our category), `tier` (effective), `base_tier`, `muted`,
    `alert_chip`, `moved_same_day`, `why` (the reason, for Routine items only).
    """
    alerts_by_ticker = alerts_by_ticker or {}
    on = {**config.DEFAULT_TOGGLES, **(toggles or {})}
    out: list[dict] = []
    for f in filings:
        kind = classify(f)
        override = (tiers or {}).get(kind)             # the user's own tier for this type (Settings, 10 Nov+)
        base = override if override in config.TIER_ORDER else tier_of(kind)
        muted = (not on.get(kind, True)) or override == "Low"
        tier = "Low" if muted else base
        out.append({
            **f,
            "kind": kind,
            "base_tier": base,
            "tier": tier,
            "muted": muted,
            "why": buried_reason(f, kind, muted) if tier == "Low" else None,
            "alert_chip": (not muted) and base == "High",
            "moved_same_day": _same_day_alert(f["date"], alerts_by_ticker.get(f["ticker"], [])),
        })
    out.sort(key=_sort_key)
    return out


def _sort_key(item: dict) -> tuple:
    """High first, then boosted, then newest, then ticker (stable, deterministic ties)."""
    ts = datetime.fromisoformat(item["date"]).timestamp()
    return (config.TIER_ORDER[item["tier"]], not item["moved_same_day"], -ts, item["ticker"])
