"""Live data feed for the API (D-067): filings + prices for the portfolio, cached in memory.

- Loads every stock in parallel (few workers; the exchange is not ours).
- A request is never slow after the first load: stale data is served instantly while a
  background thread refreshes it (stale-while-revalidate [serve old, fetch new quietly]).
- If the first load is not ready in WARM_WAIT_S, or fails, the saved snapshots answer
  instead, flagged `fallback_used`, so the app always shows something.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import pandas as pd

import config
from data import filings as filings_mod
from data import prices as prices_mod
from data.clock import ist_now
from data.symbols import resolve


@dataclass
class FeedData:
    """Everything the Today screen needs, already fetched."""
    filings: list[dict]                 # flat list; each has ticker + company
    prices: dict[str, pd.DataFrame]     # ticker -> Date/Close/Volume
    fallback_used: bool                 # True if any part came from a saved snapshot
    errors: list[str] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=ist_now)


def company_name(ticker: str) -> str:
    """Company name for display; fall back to the ticker."""
    try:
        return resolve(ticker).name
    except ValueError:
        return ticker


def _load_one(ticker: str) -> tuple[list[dict], pd.DataFrame | None, bool, list[str]]:
    """Fetch one stock's filings and prices; never raises."""
    errors: list[str] = []
    fallback = False
    rows: list[dict] = []
    df: pd.DataFrame | None = None
    try:
        got, src = filings_mod.fetch_filings(ticker, max(config.WINDOWS_HOURS.values()) // 24)
        rows = [{**r, "ticker": ticker, "company": company_name(ticker)} for r in got]
        fallback |= src == "snapshot"
    except (ValueError, RuntimeError) as exc:
        errors.append(f"{ticker} filings: {exc}")
    try:
        df, src = prices_mod.fetch_prices(ticker)
        fallback |= src == "snapshot"
    except (ValueError, RuntimeError) as exc:
        errors.append(f"{ticker} prices: {exc}")
    return rows, df, fallback, errors


def load_all(tickers: list[str] | None = None) -> FeedData:
    """Fetch every portfolio stock in parallel."""
    tickers = tickers or config.PORTFOLIO
    with ThreadPoolExecutor(max_workers=config.FEED_WORKERS) as pool:
        results = list(pool.map(_load_one, tickers))
    filings: list[dict] = []
    prices: dict[str, pd.DataFrame] = {}
    errors: list[str] = []
    fallback = False
    for t, (rows, df, fb, errs) in zip(tickers, results):
        filings += rows
        if df is not None and not df.empty:
            prices[t] = df
        fallback |= fb
        errors += errs
    return FeedData(filings, prices, fallback, errors)


def load_snapshots(tickers: list[str] | None = None) -> FeedData:
    """Build the feed from saved snapshots only (no network). Used when live data is not ready."""
    tickers = tickers or config.PORTFOLIO
    filings: list[dict] = []
    prices: dict[str, pd.DataFrame] = {}
    for t in tickers:
        snap = filings_mod.load_snapshot(t) or []
        filings += [{**r, "ticker": t, "company": company_name(t)} for r in snap]
        df = prices_mod.load_snapshot(t)
        if df is not None and not df.empty:
            prices[t] = df
    return FeedData(filings, prices, True, ["Showing saved snapshot data."])


class FeedCache:
    """In-memory cache with background refresh. One instance per server process."""

    def __init__(
        self,
        loader: Callable[[], FeedData] = load_all,
        snapshot_loader: Callable[[], FeedData] = load_snapshots,
        ttl: float = config.CACHE_TTL_S,
        wait: float = config.WARM_WAIT_S,
        clock: Callable[[], float] = time.monotonic,
        on_loaded: Callable[[FeedData], None] | None = None,
    ) -> None:
        self._loader, self._snapshot_loader = loader, snapshot_loader
        self._on_loaded = on_loaded  # e.g. queue new results filings for card building (D-078)
        self._ttl, self._wait, self._clock = ttl, wait, clock
        self._data: FeedData | None = None
        self._loaded_at = 0.0
        self._ready = threading.Event()
        self._busy = threading.Lock()
        self.last_error: str | None = None

    @property
    def ready(self) -> bool:
        return self._data is not None

    def _refresh(self) -> None:
        """Load fresh data; keep the old data if the load fails. Skips if already running."""
        if not self._busy.acquire(blocking=False):
            return
        try:
            self._data = self._loader()
            self._loaded_at = self._clock()
            self.last_error = None
        except Exception as exc:  # any failure: keep serving what we have
            self.last_error = f"{type(exc).__name__}: {exc}"
        else:
            if self._on_loaded is not None:
                try:
                    self._on_loaded(self._data)
                except Exception as exc:  # a hook must never break the feed
                    print(f"[feed] on_loaded hook failed: {type(exc).__name__}: {exc}")
        finally:
            self._ready.set()
            self._busy.release()

    def refresh_async(self) -> None:
        """Start a background refresh unless one is already running."""
        if not self._busy.locked():
            threading.Thread(target=self._refresh, daemon=True).start()

    def get(self) -> FeedData:
        """Return the freshest data available without making the caller wait long."""
        if self._data is None:
            self.refresh_async()
            self._ready.wait(timeout=self._wait)
            if self._data is None:
                return self._snapshot_loader()
        elif self._clock() - self._loaded_at > self._ttl:
            self.refresh_async()
        return self._data
