"""Fetch end-of-day (EOD) price and volume history from yfinance, with snapshot fallback."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

import config

COLUMNS = ["Date", "Close", "Volume"]


def _snapshot_path(ticker: str) -> Path:
    return Path(config.SNAPSHOT_DIR) / "prices" / f"{ticker}.json"


def save_snapshot(ticker: str, df: pd.DataFrame) -> None:
    """Freeze fetched prices to JSON so the demo works if yfinance is blocked."""
    path = _snapshot_path(ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.assign(Date=df["Date"].dt.strftime("%Y-%m-%d"))
    path.write_text(out.to_json(orient="records"), encoding="utf-8")


def load_snapshot(ticker: str) -> pd.DataFrame | None:
    """Return the frozen prices for a ticker, or None if no snapshot exists."""
    path = _snapshot_path(ticker)
    if not path.exists():
        return None
    df = pd.DataFrame(json.loads(path.read_text(encoding="utf-8")), columns=COLUMNS)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def _fetch_one(symbol: str, days: int) -> pd.DataFrame:
    """One yfinance call (e.g. 'TCS.NS'); returns Date/Close/Volume, empty if no data."""
    raw = yf.Ticker(symbol).history(
        period=f"{days}d", interval="1d", auto_adjust=False, timeout=config.REQUEST_TIMEOUT_S
    )
    if raw.empty:
        return pd.DataFrame(columns=COLUMNS)
    df = raw.reset_index()[["Date", "Close", "Volume"]]
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.normalize()
    return df.dropna(subset=["Close"]).reset_index(drop=True)


def fetch_prices(ticker: str, days: int = config.HISTORY_DAYS) -> tuple[pd.DataFrame, str]:
    """Get ~`days` of EOD prices for an NSE ticker.

    Order: NSE (.NS) -> retry once -> BSE (.BO) -> saved snapshot.
    Returns (dataframe, source) where source is 'NSE', 'BSE' or 'snapshot'.
    Raises RuntimeError with a clear message if every source fails.
    """
    errors: list[str] = []
    for suffix, label in ((config.PRIMARY_SUFFIX, "NSE"), (config.FALLBACK_SUFFIX, "BSE")):
        for attempt in range(1 + config.RETRIES):
            try:
                df = _fetch_one(ticker + suffix, days)
                if not df.empty:
                    save_snapshot(ticker, df)
                    return df, label
                errors.append(f"{ticker}{suffix}: no data")
                break  # empty is not a transient error; skip retry
            except Exception as exc:  # network/parse errors
                errors.append(f"{ticker}{suffix} attempt {attempt + 1}: {exc}")
                time.sleep(1)
    snap = load_snapshot(ticker)
    if snap is not None:
        return snap, "snapshot"
    raise RuntimeError(f"Could not load prices for {ticker}. Tried: {'; '.join(errors)}")
