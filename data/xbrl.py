"""NSE XBRL results data (D-093): structured P&L, balance sheet, cash flow and segments.

Every listed company files its results with the exchange as XBRL [machine-readable XML in which
each number carries a tag such as RevenueFromOperations and a period]. FINN reads these instead
of asking an AI to copy numbers from PDFs: exact to the rupee, free, no model call.

- Index: two NSE APIs list the files: `integrated-filing-results` (from 2025) and
  `corporates-financial-results` (older quarters). Both give a link per quarter and basis
  (consolidated / standalone).
- Files: downloaded once from NSE's archive (user approved, 2026-11-15) and cached in
  `.cache/xbrl/`; parsed into small dicts. The parsed series per stock is frozen in
  `snapshot/xbrl/<T>.json` for the precomputed set so the demo works if NSE blocks us.
- Parsing ignores the XML namespace (the 2020 BSE taxonomy and the 2026 SEBI one use the same
  tag names), keeps undimensioned facts as the statement lines, and groups dimensioned segment
  facts by their context.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

import config
from data.filings import _HEADERS

_session = requests.Session()
_MAX_XML_BYTES = 3_000_000
_SKIP_SEGMENTS = ("less", "inter segment", "inter-segment", "unallocable", "unallocated", "eliminat", "total")


# ------------------------------------------------------------------ index

def _parse_day(text: str) -> date | None:
    for fmt in ("%d-%b-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(text.strip().title(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def parse_index(integrated: list[dict], older: list[dict]) -> list[dict]:
    """Merge both NSE listings into rows {period_end, basis, url, filed, bank}, newest first.

    One row per (quarter end, basis); the integrated listing wins, and a "Revised" filing
    replaces the original.
    """
    rows: dict[tuple[str, str], dict] = {}

    def add(end: date | None, basis_raw: str, url: str, filed: str, bank: bool, revised: bool) -> None:
        if not end or not url or not url.lower().endswith(".xml"):
            return
        basis = "consolidated" if basis_raw.strip().lower().startswith("consolidated") else "standalone"
        key = (end.isoformat(), basis)
        if key in rows and not (revised and rows[key]["source"] == "integrated"):
            return
        rows[key] = {"period_end": end.isoformat(), "basis": basis, "url": url, "filed": filed, "bank": bank,
                     "source": "integrated" if filed is not None else "older"}

    for x in integrated:
        add(_parse_day(x.get("qe_Date") or ""), x.get("consolidated") or "", x.get("xbrl") or "",
            x.get("broadcast_Date") or "", "BANKING" in (x.get("xbrl") or "").upper(),
            (x.get("type_Sub") or "").lower().startswith("revis"))
    for x in older:
        if (x.get("period") or "").lower() != "quarterly" and (x.get("relatingTo") or "").lower() != "annual":
            pass
        add(_parse_day(x.get("toDate") or ""), x.get("consolidated") or "", x.get("xbrl") or "",
            x.get("filingDate") or "", (x.get("bank") or "N") == "Y", False)
    return sorted(rows.values(), key=lambda r: (r["period_end"], r["basis"]), reverse=True)


def _get_json(url: str, params: dict) -> Any:
    last: Exception | None = None
    for attempt in range(config.RETRIES + 1):
        try:
            r = _session.get(url, params=params, headers=_HEADERS, timeout=config.REQUEST_TIMEOUT_S)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"NSE results listing failed: {last}")


def fetch_index(symbol: str) -> list[dict]:
    """Every XBRL results file NSE lists for this symbol (network)."""
    integ = _get_json(config.NSE_INTEGRATED_URL, {"index": "equities", "symbol": symbol, "period_ended": "all",
                                                  "type": "Integrated Filing- Financials"})
    integ_rows = integ.get("data", []) if isinstance(integ, dict) else []
    try:
        older = _get_json(config.NSE_FIN_RESULTS_URL, {"index": "equities", "symbol": symbol, "period": "Quarterly"})
    except RuntimeError:
        older = []
    return parse_index(integ_rows, older if isinstance(older, list) else [])


# ------------------------------------------------------------------ files

def _xml_path(url: str) -> Path:
    return Path(config.CACHE_DIR) / "xbrl" / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".xml")


def check_url(url: str) -> None:
    """Only https links on NSE's own archive (same rule as filing PDFs)."""
    u = urlparse(url)
    if u.scheme != "https" or (u.hostname or "").lower() not in config.PDF_ALLOWED_HOSTS:
        raise ValueError(f"Not an NSE archive link: {url[:80]}")


def download(url: str) -> bytes:
    """The XBRL file, from the local cache or NSE (timeout, one retry)."""
    check_url(url)
    path = _xml_path(url)
    if path.exists():
        return path.read_bytes()
    last: Exception | None = None
    for attempt in range(config.RETRIES + 1):
        try:
            r = _session.get(url, headers=_HEADERS, timeout=config.PDF_TIMEOUT_S)
            r.raise_for_status()
            if len(r.content) > _MAX_XML_BYTES or b"<" not in r.content[:200]:
                raise ValueError("not an XBRL file")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
            return r.content
        except (requests.RequestException, ValueError) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"XBRL download failed: {last}")


# ------------------------------------------------------------------ parsing

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _number(text: str | None) -> float | None:
    try:
        return float((text or "").strip())
    except ValueError:
        return None


def clean_segment(raw: str) -> str:
    """'a) Wires and Cables' / '(i) FMEG' / '1. EPC' -> 'Wires and Cables' / 'FMEG' / 'EPC'."""
    label = " ".join((raw or "").split())
    return re.sub(r"^\(?(?:[a-z]|[ivx]{1,4}|\d{1,2})[).:]\s+", "", label, flags=re.IGNORECASE).strip(" -:")


def parse(xml: bytes) -> dict:
    """XBRL bytes -> {meta, quarter, ytd, bs, bs_prev, segments, segments_ytd}.

    quarter / ytd: undimensioned duration facts for the latest quarter and the year to date.
    bs / bs_prev: undimensioned instant facts at the period end and at the earlier instant.
    segments: [{name, revenue, result, assets, liabilities}] for the quarter (and ytd).
    Values are in rupees as filed; text facts (auditor opinion, rounding) go in meta.
    """
    root = ET.fromstring(xml)
    contexts: dict[str, dict] = {}
    for ctx in root.iter():
        if _local(ctx.tag) != "context":
            continue
        info: dict[str, Any] = {"dims": False}
        for el in ctx.iter():
            name = _local(el.tag)
            if name in ("startDate", "endDate", "instant"):
                info[name] = (el.text or "").strip()[:10]
            elif name in ("explicitMember", "typedMember"):
                info["dims"] = True
        contexts[ctx.get("id", "")] = info

    facts: list[tuple[str, str, str]] = []
    for el in root:
        ref = el.get("contextRef")
        if ref and el.text is not None:
            facts.append((_local(el.tag), ref, el.text.strip()))

    text = {n: v for n, ref, v in facts if not contexts.get(ref, {}).get("dims") and _number(v) is None}
    end = text.get("DateOfEndOfReportingPeriod", "")[:10]
    fy_start = text.get("DateOfStartOfFinancialYear", "")[:10]
    durations = sorted({(c["startDate"], c["endDate"]) for c in contexts.values()
                        if "startDate" in c and not c["dims"] and c.get("endDate") == end})
    q_period = max(durations, default=None)                     # latest start = the quarter
    if not fy_start and durations:          # older filings may omit the year start: longest period
        fy_start = min(durations)[0]
    ytd_period = (fy_start, end) if (fy_start, end) in durations and (fy_start, end) != q_period else None
    instants = sorted({c["instant"] for c in contexts.values() if "instant" in c and not c["dims"]})
    prev_instant = max((i for i in instants if i < end), default=None)

    out: dict[str, Any] = {"quarter": {}, "ytd": {}, "bs": {}, "bs_prev": {}, "segments": [], "segments_ytd": []}
    seg: dict[str, dict[str, dict]] = {"q": {}, "y": {}}
    seg_names: dict[str, str] = {}
    for name, ref, raw in facts:
        c = contexts.get(ref)
        if not c:
            continue
        if c["dims"]:
            if name == "DescriptionOfReportableSegment":
                seg_names[ref] = raw
            continue
        v = _number(raw)
        if v is None:
            continue
        period = (c.get("startDate"), c.get("endDate"))
        if "instant" in c:
            bucket = "bs" if c["instant"] == end else "bs_prev" if c["instant"] == prev_instant else None
        else:
            bucket = "quarter" if period == q_period else "ytd" if period == ytd_period else None
        if bucket:
            out[bucket].setdefault(name, v)

    seg_fields = {"SegmentRevenue": "revenue", "SegmentRevenueFromOperations": "revenue",
                  "SegmentProfitLossBeforeTaxAndFinanceCosts": "result", "SegmentAssets": "assets",
                  "SegmentLiabilities": "liabilities"}
    for name, ref, raw in facts:
        c = contexts.get(ref)
        if not c or not c["dims"] or name not in seg_fields or ref not in seg_names:
            continue
        label = clean_segment(seg_names[ref])
        if not label or label.lower().startswith(_SKIP_SEGMENTS):
            continue
        v = _number(raw)
        if v is None:
            continue
        if "instant" in c:
            which = "q" if c["instant"] == end else None
        else:
            period = (c.get("startDate"), c.get("endDate"))
            which = "q" if period == q_period else "y" if period == ytd_period else None
        if which:
            seg[which].setdefault(label, {"name": label}).setdefault(seg_fields[name], v)
    out["segments"] = list(seg["q"].values())
    out["segments_ytd"] = list(seg["y"].values())
    out["meta"] = {
        "period_end": end, "period_start": q_period[0] if q_period else None, "fy_start": fy_start or None,
        "prev_instant": prev_instant, "basis": text.get("NatureOfReportStandaloneConsolidated", ""),
        "audited": text.get("WhetherResultsAreAuditedOrUnaudited", ""),
        "audit_opinion": text.get("DeclarationOfUnmodifiedOpinionOrStatementOnImpactOfAuditQualification", ""),
        "rounding": text.get("LevelOfRounding", ""), "bank": "InterestEarned" in out["quarter"],
    }
    return out


def load(url: str) -> dict:
    """Download (or read cached) and parse one XBRL file; adds its url to meta."""
    data = parse(download(url))
    data["meta"]["url"] = url
    return data


def snapshot_path(symbol: str) -> Path:
    return Path(config.SNAPSHOT_DIR) / "xbrl" / f"{symbol}.json"


def save_snapshot(symbol: str, payload: dict) -> None:
    path = snapshot_path(symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")


def load_snapshot(symbol: str) -> dict | None:
    path = snapshot_path(symbol)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
