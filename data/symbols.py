"""Ticker resolver (BE-2): validate an NSE symbol and return its company name and ISIN.

Uses NSE's own list of listed symbols shipped in the repo (D-064), so it works offline and
for any NSE ticker. NSE announcements use the same symbols, so no BSE scrip code is needed.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import config


@dataclass(frozen=True)
class Company:
    """A listed company: NSE symbol, full name, ISIN [12-character global security ID]."""
    symbol: str
    name: str
    isin: str


def normalise(raw: str) -> str:
    """Clean user input: 'tcs.ns ' -> 'TCS'."""
    s = (raw or "").strip().upper()
    for suffix in (config.PRIMARY_SUFFIX, config.FALLBACK_SUFFIX):
        if s.endswith(suffix.upper()):
            s = s[: -len(suffix)]
    return s


@lru_cache(maxsize=1)
def _load_all() -> dict[str, Company]:
    """Read the shipped NSE symbol list once; header names have stray spaces, so strip them."""
    path = Path(config.EQUITY_LIST_CSV)
    if not path.exists():
        raise RuntimeError(f"Symbol list missing: {path}. Download NSE EQUITY_L.csv into data/.")
    out: dict[str, Company] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
            if row.get("SYMBOL"):
                out[row["SYMBOL"]] = Company(
                    row["SYMBOL"], row.get("NAME OF COMPANY", ""), row.get("ISIN NUMBER", "")
                )
    return out


def _match_rank(q: str, c: Company) -> int | None:
    """How well a typed query matches a company (lower is better), or None for no match.

    0 exact symbol · 1 symbol starts with it · 2 a word of the name starts with it ·
    3 the name's initials start with it ("IRCT" -> Indian Railway Catering...) · 4 contained anywhere.
    """
    name = c.name.upper()
    words = [w for w in name.replace("&", " ").replace(".", " ").replace("-", " ").split() if w != "THE"]
    if c.symbol == q:
        return 0
    if c.symbol.startswith(q):
        return 1
    if any(w.startswith(q) for w in words) or name.startswith(q):
        return 2
    if len(q) >= 2 and "".join(w[0] for w in words).startswith(q):
        return 3
    if len(q) >= 3 and (q in c.symbol or q in name):
        return 4
    return None


def search(raw: str, limit: int = 8, prefer: frozenset[str] = frozenset()) -> list[Company]:
    """Typeahead over every NSE symbol and company name (D-100).

    Ranked by match quality; within the same quality, `prefer` (portfolio, research set, stored
    research) comes first, then shorter symbols. Empty input gives an empty list.
    """
    q = " ".join(normalise(raw).split())
    if not q:
        return []
    hits: list[tuple[tuple, Company]] = []
    for c in _load_all().values():
        rank = _match_rank(q, c)
        if rank is not None:
            hits.append(((rank, c.symbol not in prefer, len(c.symbol), c.symbol), c))
    hits.sort(key=lambda h: h[0])
    return [c for _, c in hits[:limit]]


def resolve(raw: str) -> Company:
    """Return the Company for an NSE ticker, or raise ValueError with a clear message."""
    symbol = normalise(raw)
    if not symbol:
        raise ValueError("Enter an NSE ticker, e.g. TCS.")
    company = _load_all().get(symbol)
    if company is None:
        raise ValueError(f"'{symbol}' is not a listed NSE ticker. Check the spelling (e.g. TCS, INFY).")
    return company
