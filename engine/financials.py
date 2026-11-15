"""Financial statements for research views (block 10d, D-093): series, ratios, checks. No AI.

Input: parsed NSE XBRL files (data/xbrl.py), one per quarter. Output, all in ₹ crore:
- quarters: revenue, EBITDA (computed, D-054), PBT, PAT, margins, segment revenue/result
- balance sheets (half-yearly, as companies file them): equity, debt, cash, working capital
- cash flows (half-year and full year): CFO, capex, FCF, cash conversion
- ratios: TTM [trailing twelve months] figures, ROE, ROCE, D/E, working-capital days
- checks: PBT - tax = PAT, assets = equity + liabilities, and agreement with the PDF-verified
  results cards; when a printed card disagrees, the printed number wins and the view says so.

Every figure is computed in Python from tagged numbers; each quarter keeps its XBRL link as the
receipt. Proxies (NUS lesson, D-102) are labelled with their formula.
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable

import config
from data import xbrl

ENGINE_VERSION = 1
CR = 1e7                          # rupees per crore
QUARTERS_KEPT = 13                # 3 years + the year-ago quarter for YoY


# ------------------------------------------------------------------ helpers

def crore(v: float | None) -> float | None:
    return None if v is None else round(v / CR, 2)


def pct(num: float | None, den: float | None) -> float | None:
    if num is None or not den:
        return None
    return round(100.0 * num / den, 1)


def growth(cur: float | None, base: float | None) -> float | None:
    """% change; None when the base is missing, zero or negative (growth off a loss is meaningless)."""
    if cur is None or base is None or base <= 0:
        return None
    return round(100.0 * (cur - base) / base, 1)


def total(d: dict, *tags: str) -> float | None:
    """Sum of the tags present (None if none is present)."""
    vals = [d[t] for t in tags if d.get(t) is not None]
    return sum(vals) if vals else None


def segment_key(name: str) -> str:
    """Same segment across filings despite spelling: 'Wires & Cables' == 'Wires and cables'."""
    return " ".join(name.lower().replace("&", " and ").split())


def fiscal_label(end: str) -> str:
    """'2026-09-30' -> 'Q2 FY27' (Indian fiscal year April-March)."""
    d = date.fromisoformat(end)
    fy = d.year + 1 if d.month >= 4 else d.year
    q = {6: 1, 9: 2, 12: 3, 3: 4}.get(d.month, 0)
    return f"Q{q} FY{fy % 100:02d}"


# ------------------------------------------------------------------ statements

def quarter_row(f: dict) -> dict:
    """One quarter's P&L lines (₹ crore) from a parsed file. Banks get bank lines (D-048)."""
    q, m = f["quarter"], f["meta"]
    end = m["period_end"]
    row: dict[str, Any] = {"period_end": end, "label": fiscal_label(end), "bank": m["bank"], "url": m.get("url"),
                           "audited": m.get("audited"), "audit_opinion": m.get("audit_opinion")}
    if m["bank"]:
        row.update({
            "total_income": crore(q.get("Income")),
            "nii": crore(q["InterestEarned"] - q["InterestExpended"]) if q.get("InterestEarned") is not None and q.get("InterestExpended") is not None else None,
            "ppop": crore(q.get("OperatingProfitBeforeProvisionAndContingencies")),
            "provisions": crore(q.get("ProvisionsOtherThanTaxAndContingencies")),
            "pbt": crore(q.get("ProfitLossFromOrdinaryActivitiesBeforeTax")),
            "tax": crore(q.get("TaxExpense")),
            "pat": crore(q.get("ProfitLossForThePeriod")),
        })
        row["revenue"] = row["total_income"]
        row["ebitda"] = None
        row["segments"] = _segments(f)
        return row
    pbt, fin, dep, oth = (q.get(t) for t in ("ProfitBeforeTax", "FinanceCosts",
                                              "DepreciationDepletionAndAmortisationExpense", "OtherIncome"))
    ebitda = pbt + (fin or 0) + (dep or 0) - (oth or 0) if pbt is not None and dep is not None else None
    row.update({
        "revenue": crore(q.get("RevenueFromOperations")), "other_income": crore(oth),
        "ebitda": crore(ebitda), "ebitda_computed": True, "finance_costs": crore(fin), "dep": crore(dep),
        "pbt": crore(pbt), "tax": crore(q.get("TaxExpense")),
        # PAT = profit attributable to the company's own shareholders when a minority holds part of a
        # subsidiary (what results cards print as PAT); else the period's profit.
        "pat": crore(q["ProfitOrLossAttributableToOwnersOfParent"] if q.get("ProfitOrLossAttributableToOwnersOfParent")
                     else q.get("ProfitLossForPeriod")),
        "exceptional": crore(q.get("ExceptionalItemsBeforeTax")),
    })
    row["ebitda_margin"] = pct(row["ebitda"], row["revenue"])
    row["pat_margin"] = pct(row["pat"], row["revenue"])
    row["segments"] = _segments(f)
    return row


def _segments(f: dict) -> list[dict]:
    return [{"name": s["name"], "key": segment_key(s["name"]), "revenue": crore(s.get("revenue")),
             "result": crore(s.get("result")), "margin": pct(s.get("result"), s.get("revenue"))}
            for s in f.get("segments", []) if s.get("revenue")]


def balance_sheet(f: dict) -> dict | None:
    """Balance sheet at the period end (₹ crore), or None if this filing has none (Q1, Q3)."""
    b, m = f["bs"], f["meta"]
    if m["bank"]:
        if b.get("Deposits") is None and b.get("Advances") is None:
            return None
        return {"as_of": m["period_end"], "bank": True, "url": m.get("url"),
                "equity": crore(total(b, "Capital", "ReservesAndSurplus")), "deposits": crore(b.get("Deposits")),
                "advances": crore(b.get("Advances")), "investments": crore(b.get("Investments")),
                "borrowings": crore(b.get("Borrowings")), "total_assets": crore(b.get("Assets") or b.get("CapitalAndLiabilities"))}
    if b.get("Equity") is None and b.get("Assets") is None:
        return None
    debt = total(b, "BorrowingsCurrent", "BorrowingsNoncurrent") or 0.0
    cash = total(b, "CashAndCashEquivalents", "BankBalanceOtherThanCashAndCashEquivalents", "CurrentInvestments") or 0.0
    out = {
        "as_of": m["period_end"], "bank": False, "url": m.get("url"),
        "equity": crore(b.get("EquityAttributableToOwnersOfParent") or b.get("Equity")), "debt": crore(debt), "cash": crore(cash), "net_cash": crore(cash - debt),
        "inventories": crore(b.get("Inventories")),
        "receivables": crore(total(b, "TradeReceivablesCurrent", "TradeReceivablesNoncurrent")),
        "payables": crore(total(b, "TradePayablesCurrent", "TradePayablesNoncurrent")),
        "fixed_assets": crore(total(b, "PropertyPlantAndEquipment", "CapitalWorkInProgress", "OtherIntangibleAssets",
                                    "Goodwill", "IntangibleAssetsUnderDevelopment", "InvestmentProperty")),
        "total_assets": crore(b.get("Assets")), "total_liabilities": crore(b.get("Liabilities")),
    }
    other_assets = (out["total_assets"] or 0) - sum(out[k] or 0 for k in ("fixed_assets", "inventories", "receivables", "cash"))
    out["other_assets"] = round(other_assets, 2)
    out["other_liabilities"] = round((out["total_liabilities"] or 0) - (out["debt"] or 0) - (out["payables"] or 0), 2)
    out["de_ratio"] = round(out["debt"] / out["equity"], 2) if out["equity"] else None
    return out


def cash_flow(f: dict) -> dict | None:
    """Year-to-date cash flow (₹ crore) if this filing carries one (half-year and full year)."""
    y, m = f["ytd"], f["meta"]
    cfo = y.get("CashFlowsFromUsedInOperatingActivities")
    if cfo is None or not m.get("fy_start"):
        return None
    capex = total(y, "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                  "PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities",
                  "PurchaseOfTangibleAssetsClassifiedAsInvestingActivities")
    pat = y.get("ProfitLossForPeriod") or y.get("ProfitLossForThePeriod")
    months = round((date.fromisoformat(m["period_end"]) - date.fromisoformat(m["fy_start"])).days / 30.4)
    return {"from": m["fy_start"], "to": m["period_end"], "months": months, "url": m.get("url"), "bank": m["bank"],
            "cfo": crore(cfo), "capex": crore(capex), "fcf": crore(cfo - capex) if capex is not None else None,
            "pat": crore(pat), "dep": crore(y.get("DepreciationDepletionAndAmortisationExpense")),
            "cash_conversion": pct(cfo, pat) if pat and pat > 0 else None,
            "dividends": crore(y.get("DividendsPaidClassifiedAsFinancingActivities"))}


# ------------------------------------------------------------------ checks

def check_file(f: dict) -> list[str]:
    """Internal consistency of one filing; each failure is a short note."""
    q, b, m = f["quarter"], f["bs"], f["meta"]
    notes: list[str] = []
    pbt = q.get("ProfitBeforeTax") or q.get("ProfitLossFromOrdinaryActivitiesBeforeTax")
    pat = q.get("ProfitLossForPeriod") or q.get("ProfitLossForThePeriod")
    tax = q.get("TaxExpense")
    disc = q.get("ProfitLossFromDiscontinuedOperationsAfterTax") or 0
    share = q.get("ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod") or 0
    if None not in (pbt, pat, tax) and abs(pbt - tax + disc - pat) > max(0.005 * abs(pat), 1e7) and abs(pbt + share - tax + disc - pat) > max(0.005 * abs(pat), 1e7):
        notes.append(f"{fiscal_label(m['period_end'])}: PBT - tax does not equal PAT in the tagged data")
    a, el = b.get("Assets"), b.get("EquityAndLiabilities")
    if a and el and abs(a - el) > 0.001 * a:
        notes.append(f"{fiscal_label(m['period_end'])}: assets do not equal equity + liabilities")
    return notes


def reconcile(quarters: list[dict], cards: list[dict], basis: str | None = None) -> list[str]:
    """Compare with PDF-verified results cards (same quarter end and basis). Printed numbers win.

    Returns notes for every line that differed by more than 0.5%; the quarter row is corrected and
    marks the line in `row["printed_override"]`.
    """
    notes: list[str] = []
    by_end = {q["period_end"]: q for q in quarters}
    keymap = {"revenue": "revenue", "total_income": "revenue", "pbt": "pbt", "pat": "pat"}
    for card in cards:
        row = by_end.get(card.get("period_end"))
        if not row or (basis and card.get("basis") and card["basis"] != basis):
            continue
        for metric in card.get("metrics", []):
            key = keymap.get(metric.get("key"))
            printed = (metric.get("values") or {}).get("current")
            if not key or printed is None or row.get(key) is None:
                continue
            if abs(row[key] - printed) > 0.005 * max(abs(printed), 1):
                notes.append(f"{row['label']} {metric.get('label', key)}: XBRL tag gives ₹{row[key]:,.2f} cr, the printed "
                             f"filing ₹{printed:,.2f} cr; FINN uses the printed figure")
                row.setdefault("printed_override", {})[key] = {"xbrl": row[key], "printed": printed}
                row[key] = printed
        if row.get("revenue") and not row.get("bank"):
            row["ebitda_margin"] = pct(row.get("ebitda"), row["revenue"])
            row["pat_margin"] = pct(row.get("pat"), row["revenue"])
    return notes


# ------------------------------------------------------------------ ratios

def ttm(quarters: list[dict], key: str, upto: int = 0) -> float | None:
    """Sum of 4 quarters starting at index `upto` (newest first); None if any is missing."""
    window = quarters[upto: upto + 4]
    if len(window) < 4 or any(q.get(key) is None for q in window):
        return None
    return round(sum(q[key] for q in window), 2)


def _sheet_near(sheets: list[dict], day: str, max_days: int = 45) -> dict | None:
    target = date.fromisoformat(day)
    best = min(sheets, key=lambda s: abs((date.fromisoformat(s["as_of"]) - target).days), default=None)
    return best if best and abs((date.fromisoformat(best["as_of"]) - target).days) <= max_days else None


def ratios(quarters: list[dict], sheets: list[dict]) -> dict:
    """Headline ratios for the latest balance sheet date (₹ crore, %, days). Python only."""
    if not quarters or not sheets:
        return {}
    bs = sheets[0]
    idx = next((i for i, q in enumerate(quarters) if q["period_end"] == bs["as_of"]), None)
    if idx is None:
        return {}
    rev, pat, ebitda = ttm(quarters, "revenue", idx), ttm(quarters, "pat", idx), ttm(quarters, "ebitda", idx)
    pbt, fin = ttm(quarters, "pbt", idx), ttm(quarters, "finance_costs", idx)
    year_ago = _sheet_near(sheets, (date.fromisoformat(bs["as_of"]).replace(year=date.fromisoformat(bs["as_of"]).year - 1)).isoformat())
    out: dict[str, Any] = {"as_of": bs["as_of"], "label": quarters[idx]["label"], "ttm_revenue": rev, "ttm_pat": pat,
                           "ttm_ebitda": ebitda}
    eq_avg = (bs["equity"] + year_ago["equity"]) / 2 if year_ago and bs.get("equity") and year_ago.get("equity") else bs.get("equity")
    out["roe"] = pct(pat, eq_avg)
    out["roe_basis"] = "average equity over the year" if year_ago else "closing equity"
    if bs.get("bank"):
        out["advances_to_deposits"] = pct(bs.get("advances"), bs.get("deposits"))
        return out
    if pbt is not None:
        ebit = pbt + (fin or 0)
        cap = (bs.get("equity") or 0) + (bs.get("debt") or 0)
        cap_prev = ((year_ago.get("equity") or 0) + (year_ago.get("debt") or 0)) if year_ago else None
        out["roce"] = pct(ebit, (cap + cap_prev) / 2 if cap_prev else cap)
    out["de_ratio"] = bs.get("de_ratio")
    out["net_cash"] = bs.get("net_cash")
    if rev:
        days = lambda v: round(365 * v / rev) if v is not None else None   # on revenue, labelled
        out["inventory_days"] = days(bs.get("inventories"))
        out["receivable_days"] = days(bs.get("receivables"))
        out["payable_days"] = days(bs.get("payables"))
        if None not in (out["inventory_days"], out["receivable_days"], out["payable_days"]):
            out["cash_cycle_days"] = out["inventory_days"] + out["receivable_days"] - out["payable_days"]
    return out


def half_years(flows: list[dict]) -> list[dict]:
    """H1 and H2 per fiscal year from the YTD flows (H2 = full year - H1), newest first."""
    by_from: dict[str, dict[int, dict]] = {}
    for f in flows:
        by_from.setdefault(f["from"], {})[f["months"]] = f
    out: list[dict] = []
    for start, per in sorted(by_from.items(), reverse=True):
        fy = date.fromisoformat(start).year + 1
        h1, full = per.get(6), per.get(12)
        if full and h1:
            h2 = {k: (round(full[k] - h1[k], 2) if isinstance(full.get(k), (int, float)) and isinstance(h1.get(k), (int, float)) else None)
                  for k in ("cfo", "capex", "fcf", "pat", "dep", "dividends")}
            h2.update({"label": f"H2 FY{fy % 100:02d}", "url": full["url"], "derived": "full year minus H1",
                       "cash_conversion": pct(h2["cfo"], h2["pat"]) if h2.get("pat") and h2["pat"] > 0 else None})
            out.append(h2)
        if h1:
            out.append({**{k: h1[k] for k in ("cfo", "capex", "fcf", "pat", "dep", "dividends", "cash_conversion", "url")},
                        "label": f"H1 FY{fy % 100:02d}"})
    return out


def capex_proxy(sheets: list[dict], quarters: list[dict]) -> dict | None:
    """When no cash flow statement is filed: capex ≈ change in fixed assets + depreciation (D-102)."""
    if len(sheets) < 2 or sheets[0].get("bank"):
        return None
    new, old = sheets[0], sheets[1]
    deps = [q.get("dep") for q in quarters if old["as_of"] < q["period_end"] <= new["as_of"]]
    if None in (new.get("fixed_assets"), old.get("fixed_assets")) or not deps or None in deps:
        return None
    return {"from": old["as_of"], "to": new["as_of"], "value": round(new["fixed_assets"] - old["fixed_assets"] + sum(deps), 2),
            "formula": "fixed assets (end) − fixed assets (start) + depreciation in between", "proxy": True}


# ------------------------------------------------------------------ build

def choose_basis(index: list[dict]) -> str:
    """Consolidated if the latest quarter has it, else standalone (one basis for the whole series)."""
    if not index:
        return "consolidated"
    latest = index[0]["period_end"]
    return "consolidated" if any(r["period_end"] == latest and r["basis"] == "consolidated" for r in index) else "standalone"


def _card_rows(symbol: str) -> list[dict]:
    """PDF-verified results cards for this stock: {period_end, metrics}."""
    out = []
    for folder in (Path(config.CARDS_DIR), Path(config.CACHE_DIR) / "cards"):
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            try:
                c = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            end = (c.get("period") or {}).get("current")
            if c.get("ticker") == symbol and c.get("kind") == "results" and c.get("status") == "ok" and end:
                out.append({"period_end": end, "basis": c.get("basis"), "metrics": c.get("metrics", [])})
    return out


def build(symbol: str, index_fetch: Callable[[str], list[dict]] = xbrl.fetch_index,
          loader: Callable[[str], dict] = xbrl.load, cards: list[dict] | None = None,
          progress: Callable[[str], None] = lambda s: None, pace_s: float = 0.4) -> dict:
    """All statements and ratios for one stock (network: NSE listing + XBRL files)."""
    progress("Listing results filings on NSE")
    index = index_fetch(symbol)
    if not index:
        raise LookupError(f"NSE lists no XBRL results for {symbol}")
    basis = choose_basis(index)
    rows = [r for r in index if r["basis"] == basis][:QUARTERS_KEPT]
    files: list[dict] = []
    for i, r in enumerate(rows):
        progress(f"Reading {fiscal_label(r['period_end'])} ({basis})")
        try:
            f = loader(r["url"])
        except Exception as exc:              # one bad file must not sink the series
            files.append({"error": str(exc)[:120], "period_end": r["period_end"]})
            continue
        if f["meta"]["period_end"] != r["period_end"]:
            continue
        files.append(f)
        if i < len(rows) - 1:
            time.sleep(pace_s)
    good = [f for f in files if "error" not in f]
    quarters = [quarter_row(f) for f in good]
    quarters.sort(key=lambda q: q["period_end"], reverse=True)
    for i, q in enumerate(quarters):           # QoQ and YoY in Python
        prev = quarters[i + 1] if i + 1 < len(quarters) else None
        ya = next((x for x in quarters if x["period_end"] == q["period_end"].replace(q["period_end"][:4], str(int(q["period_end"][:4]) - 1), 1)), None)
        for key in ("revenue", "ebitda", "pat"):
            q[f"{key}_qoq"] = growth(q.get(key), prev.get(key)) if prev else None
            q[f"{key}_yoy"] = growth(q.get(key), ya.get(key)) if ya else None
    notes = [n for f in good for n in check_file(f)]
    notes += reconcile(quarters, cards if cards is not None else _card_rows(symbol), basis)
    sheets = sorted([s for s in (balance_sheet(f) for f in good) if s], key=lambda s: s["as_of"], reverse=True)
    flows = [c for c in (cash_flow(f) for f in good) if c]
    halves = half_years(flows)
    latest = good and max(good, key=lambda f: f["meta"]["period_end"])
    return {
        "ticker": symbol, "engine_version": ENGINE_VERSION, "basis": basis, "bank": bool(quarters and quarters[0]["bank"]),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "source": "NSE XBRL results filings",
        "quarters": quarters, "balance_sheets": sheets, "cash_flows": halves,
        "ratios": ratios(quarters, sheets), "capex_proxy": None if halves else capex_proxy(sheets, quarters),
        "audit": {"opinion": latest["meta"]["audit_opinion"], "audited": latest["meta"]["audited"],
                  "label": fiscal_label(latest["meta"]["period_end"])} if latest else None,
        "checks": notes, "missing": [f["period_end"] for f in files if "error" in f],
    }


# ------------------------------------------------------------------ store

def _paths(symbol: str) -> list[Path]:
    return [Path(config.FINANCIALS_DIR) / f"{symbol}.json", Path(config.CACHE_DIR) / "financials" / f"{symbol}.json"]


def stored(symbol: str) -> dict | None:
    for path in _paths(symbol):
        if path.exists():
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if d.get("engine_version") == ENGINE_VERSION:
                return d
    return None


def save(result: dict, snapshot: bool = False) -> None:
    path = _paths(result["ticker"])[0 if snapshot else 1]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")


def get(symbol: str, **kw: Any) -> dict:
    """Stored result, else build and keep it."""
    done = stored(symbol)
    if done:
        return done
    result = build(symbol, **kw)
    save(result)
    return result
