"""Rule-based price/volume alerts. No AI: plain thresholds, easy to audit."""
from __future__ import annotations

import pandas as pd

import config


def check_alerts(
    ticker: str,
    df: pd.DataFrame,
    volume_multiple: float = config.VOLUME_MULTIPLE,
    price_move_pct: float = config.PRICE_MOVE_PCT,
    avg_window: int = config.VOLUME_AVG_WINDOW,
) -> list[dict]:
    """Flag alerts for the latest trading day in `df` (columns Date, Close, Volume).

    - price: |close vs previous close| > price_move_pct
    - volume: latest volume > volume_multiple x average of the `avg_window` days BEFORE it
    Returns a list of alert dicts (empty if nothing crossed or data is too short).
    """
    df = df.sort_values("Date").reset_index(drop=True)
    alerts: list[dict] = []
    if len(df) < 2:
        return alerts

    last, prev = df.iloc[-1], df.iloc[-2]
    date = last["Date"].strftime("%Y-%m-%d")

    if prev["Close"] > 0:
        move = round((last["Close"] / prev["Close"] - 1) * 100, 6)  # rounds away float noise
        if abs(move) > price_move_pct:
            alerts.append({
                "ticker": ticker, "date": date, "type": "price",
                "value": round(float(move), 2), "threshold": price_move_pct,
                "message": f"{ticker} moved {move:+.2f}% on {date} (limit ±{price_move_pct}%)",
            })

    history = df["Volume"].iloc[:-1].tail(avg_window)
    if len(history) == avg_window:  # need a full window for a fair average
        avg = float(history.mean())
        if avg > 0 and last["Volume"] > volume_multiple * avg:
            ratio = float(last["Volume"]) / avg
            alerts.append({
                "ticker": ticker, "date": date, "type": "volume",
                "value": round(ratio, 2), "threshold": volume_multiple,
                "message": f"{ticker} volume {ratio:.1f}x the {avg_window}-day average on {date} (limit {volume_multiple}x)",
            })
    return alerts
