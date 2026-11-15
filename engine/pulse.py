"""Pulse (block 10g, D-107): the 10-second glance at the whole portfolio. Python only, no AI.

- Heatmap (DB1): each stock's last move, 5-day move, and whether a High/Medium filing landed
  on the latest session.
- Move vs volume (DB6): the same rows carry the volume multiple (latest volume ÷ the average of
  the 20 sessions before it), so the screen can plot them against the user's thresholds.
- Calendar (DB2): upcoming board meetings and ex-dates (data/events.py), next 14 days.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

import config
from engine.feed import FeedData, company_name
from engine.ranker import rank_filings


def stock_row(ticker: str, df: pd.DataFrame | None) -> dict:
    """Last close, 1-day and 5-day move (%), volume multiple, session date for one stock."""
    row = {"ticker": ticker, "company": company_name(ticker), "move": None, "move_5d": None, "vol_x": None,
           "close": None, "date": None}
    if df is None or len(df) < 2:
        return row
    df = df.sort_values("Date").reset_index(drop=True)
    last, prev = df.iloc[-1], df.iloc[-2]
    row.update(close=round(float(last["Close"]), 2), date=last["Date"].strftime("%Y-%m-%d"))
    if prev["Close"] > 0:
        row["move"] = round((float(last["Close"]) / float(prev["Close"]) - 1) * 100, 2)
    if len(df) >= 6 and df.iloc[-6]["Close"] > 0:
        row["move_5d"] = round((float(last["Close"]) / float(df.iloc[-6]["Close"]) - 1) * 100, 2)
    hist = df["Volume"].iloc[:-1].tail(config.VOLUME_AVG_WINDOW)
    if len(hist) == config.VOLUME_AVG_WINDOW and hist.mean() > 0:
        row["vol_x"] = round(float(last["Volume"]) / float(hist.mean()), 2)
    return row


def build_pulse(data: FeedData, events: dict, today: date) -> dict:
    """Payload for the Pulse tab."""
    from data.events import expected_results, recent, upcoming
    rows = [stock_row(t, data.prices.get(t)) for t in config.PORTFOLIO]
    session = max((r["date"] for r in rows if r["date"]), default=None)
    ranked = rank_filings(data.filings, {}, {})
    filed: dict[str, list[dict]] = {}
    for f in ranked:
        if f["tier"] != "Low" and session and f["date"][:10] == session:
            filed.setdefault(f["ticker"], []).append({"kind": f.get("kind"), "tier": f["tier"], "title": f.get("title", "")[:90]})
    for r in rows:
        r["filings"] = filed.get(r["ticker"], [])
    names = {r["ticker"]: r["company"] for r in rows}
    mine = [e for e in events.get("events", []) if e["ticker"] in names]
    named = lambda es: [{**e, "company": names.get(e["ticker"], e["ticker"])} for e in es]
    cal = named(upcoming(mine, today))
    moved = [r for r in rows if r["move"] is not None]
    return {
        "session_date": session, "stocks": rows, "events": cal,
        "recent_events": named(recent(mine, today)), "expected": named(expected_results(mine, today)),
        "events_as_of": events.get("as_of"), "events_live": events.get("live", False),
        "breadth": {"up": sum(1 for r in moved if r["move"] > 0), "down": sum(1 for r in moved if r["move"] < 0),
                    "avg_move": round(sum(r["move"] for r in moved) / len(moved), 2) if moved else None},
        "fallback_used": data.fallback_used,
    }


def alert_history(data: FeedData, sessions: int = 7) -> dict:
    """Each portfolio stock's day move and volume multiple for the last `sessions` trading days (10h, P4).

    The Settings screen counts these against the user's sliders as they drag, so "what would
    ±3% have meant?" is answered from real data. Same maths as engine.alerts: the move is close
    vs the previous close; the volume multiple is volume ÷ the average of the 20 sessions before.
    """
    rows: list[dict] = []
    dates: set[str] = set()
    w = config.VOLUME_AVG_WINDOW
    for t in config.PORTFOLIO:
        df = data.prices.get(t)
        if df is None or len(df) < 2:
            continue
        df = df.sort_values("Date").reset_index(drop=True)
        for i in range(max(1, len(df) - sessions), len(df)):
            prev, cur = float(df.iloc[i - 1]["Close"]), float(df.iloc[i]["Close"])
            move = round((cur / prev - 1) * 100, 2) if prev > 0 else None
            hist = df["Volume"].iloc[max(0, i - w):i]
            vol_x = round(float(df.iloc[i]["Volume"]) / float(hist.mean()), 2) if len(hist) == w and hist.mean() > 0 else None
            day = df.iloc[i]["Date"].strftime("%Y-%m-%d")
            dates.add(day)
            rows.append({"ticker": t, "date": day, "move": move, "vol_x": vol_x})
    return {"sessions": sorted(dates)[-sessions:], "rows": [r for r in rows if r["date"] in dates],
            "fallback_used": data.fallback_used}
