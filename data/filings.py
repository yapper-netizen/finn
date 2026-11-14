"""Corporate-announcements fetcher (BE-3): NSE API -> clean filing dicts, snapshot fallback."""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

import config
from data.clock import ist_now
from data.symbols import resolve

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": config.NSE_REFERER,
}
_session = requests.Session()


def _snapshot_path(symbol: str) -> Path:
    return Path(config.SNAPSHOT_DIR) / "filings" / f"{symbol}.json"


def parse_filing(raw: dict[str, Any]) -> dict[str, str]:
    """Turn one NSE record into {date, title, category, subcategory, pdf_url, id}."""
    when = datetime.strptime(raw["an_dt"], "%d-%b-%Y %H:%M:%S")
    return {
        "id": str(raw.get("seq_id") or ""),
        "date": when.isoformat(timespec="seconds"),
        "title": (raw.get("attchmntText") or "").strip(),
        "category": (raw.get("desc") or "").strip(),
        "subcategory": "",  # NSE has no sub-category; the classifier (EN-2) refines from title
        "pdf_url": (raw.get("attchmntFile") or "").strip(),
    }


def parse_filings(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Parse, drop duplicates and unreadable rows, newest first."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for raw in rows:
        try:
            f = parse_filing(raw)
        except (KeyError, ValueError):
            continue  # skip a malformed row rather than fail the whole fetch
        key = f["id"] or f"{f['date']}|{f['title']}"
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return sorted(out, key=lambda f: f["date"], reverse=True)


def _fetch_nse(symbol: str, start: date, end: date) -> list[dict[str, Any]]:
    """One call to NSE; raises on HTTP or JSON problems."""
    r = _session.get(
        config.NSE_ANNOUNCEMENTS_URL,
        params={
            "index": "equities",
            "symbol": symbol,
            "from_date": start.strftime("%d-%m-%Y"),
            "to_date": end.strftime("%d-%m-%Y"),
        },
        headers=_HEADERS,
        timeout=config.REQUEST_TIMEOUT_S,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise ValueError(f"unexpected NSE reply: {str(data)[:80]}")
    return data


def save_snapshot(symbol: str, filings: list[dict[str, str]]) -> None:
    """Freeze filings to JSON so the demo works if NSE blocks us."""
    path = _snapshot_path(symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(filings, indent=1), encoding="utf-8")


def load_snapshot(symbol: str) -> list[dict[str, str]] | None:
    """Frozen filings for a ticker, or None if no snapshot exists."""
    path = _snapshot_path(symbol)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def fetch_filings(
    ticker: str, days: int = config.FILINGS_DAYS, today: date | None = None
) -> tuple[list[dict[str, str]], str]:
    """Filings for an NSE ticker over the last `days` days, newest first.

    Returns (filings, source) with source 'NSE' or 'snapshot'. A live fetch also refreshes
    the snapshot (merged with older saved filings, so the snapshot only grows).
    Raises ValueError for an invalid ticker, RuntimeError if NSE fails and no snapshot exists.
    """
    symbol = resolve(ticker).symbol
    end = today or ist_now().date()
    start = end - timedelta(days=days)
    errors: list[str] = []
    for attempt in range(1 + config.RETRIES):
        try:
            live = parse_filings(_fetch_nse(symbol, start, end))
            old = load_snapshot(symbol) or []
            merged = {f["id"] or f"{f['date']}|{f['title']}": f for f in old + live}
            save_snapshot(symbol, sorted(merged.values(), key=lambda f: f["date"], reverse=True))
            return live, "NSE"
        except Exception as exc:  # network, HTTP block, bad JSON
            errors.append(f"attempt {attempt + 1}: {exc}")
            time.sleep(1)
    snap = load_snapshot(symbol)
    if snap is not None:
        cutoff = datetime.combine(start, datetime.min.time()).isoformat()
        return [f for f in snap if f["date"] >= cutoff], "snapshot"
    raise RuntimeError(f"Could not load filings for {symbol}. Tried NSE: {'; '.join(errors)}")
