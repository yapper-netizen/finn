"""Windowed digest (EN-4): what changed in the last 24h / 3d / 7d, filtered into three groups.

cards     = every High filing (D-065: uncapped; the filter is the tier, not a card count)
summaries = Medium filings, one line each
routine   = Low filings, collapsed into "Routine (N)"
If the window has no filings at all, widen to the most recent day with filings and set
`widened` so the app can show a banner (D-046).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import config
from data.clock import ist_now
from engine.ranker import rank_filings


def _group(ranked: list[dict]) -> dict:
    """Split ranked filings into cards / summaries / routine."""
    return {
        "cards": [i for i in ranked if i["tier"] == "High"],
        "summaries": [i for i in ranked if i["tier"] == "Medium"],
        "routine": [i for i in ranked if i["tier"] == "Low"],
    }


def build_digest(
    filings: list[dict],
    alerts_by_ticker: dict[str, list[dict]] | None = None,
    window: str = config.DEFAULT_WINDOW,
    toggles: dict[str, bool] | None = None,
    now: datetime | None = None,
) -> dict:
    """Build the digest for one window. `filings` is the flat list across tickers."""
    if window not in config.WINDOWS_HOURS:
        raise ValueError(f"Unknown window '{window}'. Use one of {list(config.WINDOWS_HOURS)}.")
    now = now or ist_now()
    cutoff = now - timedelta(hours=config.WINDOWS_HOURS[window])
    inside = [f for f in filings if cutoff <= datetime.fromisoformat(f["date"]) <= now]

    widened, as_of = False, None
    past = [f for f in filings if f["date"] <= now.isoformat()]
    if not inside and past:
        latest_day = max(f["date"][:10] for f in past)
        inside = [f for f in past if f["date"][:10] == latest_day]
        widened, as_of = True, latest_day

    groups = _group(rank_filings(inside, alerts_by_ticker, toggles))
    return {
        "window": window,
        "widened": widened,
        "as_of": as_of,
        "generated_at": now.isoformat(timespec="seconds"),
        **groups,
        "counts": {
            "cards": len(groups["cards"]),
            "summaries": len(groups["summaries"]),
            "routine": len(groups["routine"]),
            "total": len(inside),
        },
    }
