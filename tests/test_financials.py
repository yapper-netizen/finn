"""XBRL parsing and financial statements (block 10d, D-093). No network: synthetic XBRL."""
import pytest

from data import xbrl
from engine import financials as F

NS = "http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt"


def ctx(cid, start=None, end=None, instant=None, dim=False):
    period = f"<xbrli:instant>{instant}</xbrli:instant>" if instant else \
        f"<xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate>"
    scen = '<xbrli:scenario><xbrldi:typedMember dimension="x:Seg"><x:Id>1</x:Id></xbrldi:typedMember></xbrli:scenario>' if dim else ""
    return f'<xbrli:context id="{cid}"><xbrli:entity><xbrli:identifier scheme="s">1</xbrli:identifier></xbrli:entity><xbrli:period>{period}</xbrli:period>{scen}</xbrli:context>'


def fact(name, cid, value):
    return f'<c:{name} contextRef="{cid}" unitRef="INR" decimals="-4">{value}</c:{name}>'


def make_xml(end="2026-09-30", qstart="2026-07-01", fy="2026-04-01", rev=1e10, pbt=1.3e9, tax=3e8, pat=1e9,
             owners=None, cfo=None, capex=None, ytd_pat=None, equity=1.3e11, extra="", ns=NS):
    facts = [ctx("Q", qstart, end), ctx("Y", fy, end), ctx("I", instant=end), ctx("P", instant="2026-03-31"),
             ctx("S1", qstart, end, dim=True), ctx("S2", qstart, end, dim=True), ctx("S3", qstart, end, dim=True),
             fact("DateOfEndOfReportingPeriod", "Q", end), fact("DateOfStartOfFinancialYear", "Q", fy),
             fact("NatureOfReportStandaloneConsolidated", "Q", "Consolidated"),
             fact("DeclarationOfUnmodifiedOpinionOrStatementOnImpactOfAuditQualification", "Q", "Declaration of unmodified opinion"),
             fact("RevenueFromOperations", "Q", rev), fact("OtherIncome", "Q", 1e8), fact("FinanceCosts", "Q", 5e7),
             fact("DepreciationDepletionAndAmortisationExpense", "Q", 2e8), fact("ProfitBeforeTax", "Q", pbt),
             fact("TaxExpense", "Q", tax), fact("ProfitLossForPeriod", "Q", pat),
             fact("RevenueFromOperations", "Y", 2 * rev), fact("CashAndCashEquivalents", "P", 5e8),
             fact("DescriptionOfReportableSegment", "S1", "a) Wires &amp; Cables"), fact("SegmentRevenue", "S1", 0.8 * rev),
             fact("SegmentProfitLossBeforeTaxAndFinanceCosts", "S1", 1e9),
             fact("DescriptionOfReportableSegment", "S2", "(ii) FMEG"), fact("SegmentRevenue", "S2", 0.2 * rev),
             fact("DescriptionOfReportableSegment", "S3", "Less: Inter segment"), fact("SegmentRevenue", "S3", 0)]
    if owners is not None:
        facts.append(fact("ProfitOrLossAttributableToOwnersOfParent", "Q", owners))
    if cfo is not None:
        facts += [fact("CashFlowsFromUsedInOperatingActivities", "Y", cfo), fact("ProfitLossForPeriod", "Y", ytd_pat),
                  fact("PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities", "Y", capex)]
    if equity is not None:
        facts += [fact("Equity", "I", equity), fact("BorrowingsCurrent", "I", 1e9), fact("BorrowingsNoncurrent", "I", 0),
                  fact("CashAndCashEquivalents", "I", 2e9), fact("CurrentInvestments", "I", 3e9),
                  fact("Inventories", "I", 7e9), fact("TradeReceivablesCurrent", "I", 4e9),
                  fact("TradePayablesCurrent", "I", 2e9), fact("PropertyPlantAndEquipment", "I", 5e9),
                  fact("Assets", "I", 2.4e11), fact("EquityAndLiabilities", "I", 2.4e11), fact("Liabilities", "I", 1.1e11)]
    return (f'<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" '
            f'xmlns:x="urn:x" xmlns:c="{ns}">' + "".join(facts) + extra + "</xbrli:xbrl>").encode()


# ---------------------------------------------------------------- parsing

def test_parse_buckets_periods_and_segments():
    d = xbrl.parse(make_xml())
    assert d["meta"]["period_end"] == "2026-09-30" and d["meta"]["period_start"] == "2026-07-01"
    assert d["quarter"]["RevenueFromOperations"] == 1e10 and d["ytd"]["RevenueFromOperations"] == 2e10
    assert d["bs"]["Equity"] == 1.3e11 and d["bs_prev"]["CashAndCashEquivalents"] == 5e8
    assert [s["name"] for s in d["segments"]] == ["Wires & Cables", "FMEG"]       # prefixes and "Less:" dropped
    assert d["segments"][0]["result"] == 1e9
    assert d["meta"]["audit_opinion"].startswith("Declaration of unmodified")


def test_parse_ignores_namespace_of_older_taxonomy():
    d = xbrl.parse(make_xml(ns="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"))
    assert d["quarter"]["ProfitBeforeTax"] == 1.3e9


def test_clean_segment_and_labels():
    assert [xbrl.clean_segment(x) for x in ("a) Wires and Cables", "(iv) Others", "1. EPC", "Ireland")] == \
        ["Wires and Cables", "Others", "EPC", "Ireland"]
    assert F.fiscal_label("2026-09-30") == "Q2 FY27" and F.fiscal_label("2026-03-31") == "Q4 FY26"
    assert F.segment_key("Wires & Cables") == F.segment_key("Wires and cables")


def test_index_merges_listings_and_rejects_other_hosts():
    integ = [{"qe_Date": "30-SEP-2026", "consolidated": "Consolidated", "xbrl": "https://nsearchives.nseindia.in/a.xml",
              "broadcast_Date": "x", "type_Sub": "Original"}]
    older = [{"toDate": "30-Sep-2026", "consolidated": "Consolidated", "xbrl": "https://nsearchives.nseindia.in/old.xml",
              "filingDate": "y", "period": "Quarterly"},
             {"toDate": "31-Dec-2024", "consolidated": "Non-Consolidated", "xbrl": "https://nsearchives.nseindia.in/b.xml",
              "filingDate": "z", "period": "Quarterly"}]
    rows = xbrl.parse_index(integ, older)
    assert [(r["period_end"], r["basis"], r["url"][-5:]) for r in rows] == \
        [("2026-09-30", "consolidated", "a.xml"), ("2024-12-31", "standalone", "b.xml")]
    with pytest.raises(ValueError):
        xbrl.check_url("https://evil.example.com/a.xml")


# ---------------------------------------------------------------- statements

def test_quarter_row_computes_ebitda_and_uses_owners_pat():
    row = F.quarter_row(xbrl.parse(make_xml(owners=9.8e8)))
    assert row["revenue"] == 1000.0 and row["pat"] == 98.0           # owners' share, ₹ crore
    assert row["ebitda"] == 145.0                                     # 130 + 5 + 20 - 10
    assert row["ebitda_margin"] == 14.5 and row["segments"][0]["margin"] == 12.5


def test_balance_sheet_and_ratios():
    bs = F.balance_sheet(xbrl.parse(make_xml()))
    assert bs["debt"] == 100.0 and bs["cash"] == 500.0 and bs["net_cash"] == 400.0 and bs["de_ratio"] == 0.01
    qs = [{"period_end": f"2026-{m:02d}-30", "label": "q", "revenue": 1000.0, "pat": 100.0, "ebitda": 150.0, "pbt": 130.0,
           "finance_costs": 5.0} for m in (9, 6, 3, 1)]
    qs[0]["period_end"] = "2026-09-30"
    r = F.ratios(qs, [bs])
    assert r["roe"] == round(100 * 400 / 13000, 1) and r["roe_basis"] == "closing equity"
    assert r["inventory_days"] == round(365 * 700 / 4000) and r["cash_cycle_days"] == r["inventory_days"] + r["receivable_days"] - r["payable_days"]


def test_cash_flow_and_half_years():
    h1 = F.cash_flow(xbrl.parse(make_xml(cfo=1.6e9, capex=6e8, ytd_pat=1.8e9)))
    assert h1["months"] == 6 and h1["fcf"] == 100.0 and h1["cash_conversion"] == round(100 * 160 / 180, 1)
    full = {**h1, "to": "2027-03-31", "months": 12, "cfo": 400.0, "capex": 130.0, "fcf": 270.0, "pat": 360.0}
    halves = F.half_years([h1, full])
    assert [h["label"] for h in halves] == ["H2 FY27", "H1 FY27"]
    assert halves[0]["cfo"] == 240.0 and halves[0]["derived"] == "full year minus H1"


def test_reconcile_prefers_printed_figure_and_ignores_other_basis():
    qs = [{"period_end": "2026-09-30", "label": "Q2 FY27", "revenue": 1000.0, "pbt": 120.0, "pat": 90.0, "ebitda": 150.0}]
    card = {"period_end": "2026-09-30", "basis": "consolidated",
            "metrics": [{"key": "pbt", "label": "PBT", "values": {"current": 130.0}},
                        {"key": "revenue", "label": "Revenue", "values": {"current": 1000.0}}]}
    assert F.reconcile(qs, [{**card, "basis": "standalone"}], "consolidated") == []
    notes = F.reconcile(qs, [card], "consolidated")
    assert len(notes) == 1 and "printed" in notes[0] and qs[0]["pbt"] == 130.0
    assert qs[0]["printed_override"]["pbt"] == {"xbrl": 120.0, "printed": 130.0}


def test_check_file_flags_inconsistent_tags():
    assert F.check_file(xbrl.parse(make_xml())) == []
    assert F.check_file(xbrl.parse(make_xml(pat=5e8)))                 # 130 - 30 != 50


def test_build_series_growth_and_tolerates_a_bad_file():
    ends = ["2026-09-30", "2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30"]
    index = [{"period_end": e, "basis": "consolidated", "url": f"u{e}"} for e in ends] + \
            [{"period_end": "2025-06-30", "basis": "consolidated", "url": "bad"}]
    starts = {"2026-09-30": "2026-07-01", "2026-06-30": "2026-04-01", "2026-03-31": "2026-01-01",
              "2025-12-31": "2025-10-01", "2025-09-30": "2025-07-01"}
    revs = dict(zip(ends, (1.2e10, 1.1e10, 1.05e10, 1.0e10, 1.0e10)))

    def loader(url):
        if url == "bad":
            raise RuntimeError("404")
        e = url[1:]
        fy = "2026-04-01" if e >= "2026-04-01" else "2025-04-01"
        return xbrl.parse(make_xml(end=e, qstart=starts[e], fy=fy, rev=revs[e]))
    r = F.build("XYZ", index_fetch=lambda s: index, loader=loader, cards=[], pace_s=0)
    assert [q["label"] for q in r["quarters"]] == ["Q2 FY27", "Q1 FY27", "Q4 FY26", "Q3 FY26", "Q2 FY26"]
    assert r["quarters"][0]["revenue_yoy"] == 20.0 and r["quarters"][0]["revenue_qoq"] == round(100 / 11, 1)
    assert r["missing"] == ["2025-06-30"] and r["audit"]["opinion"].startswith("Declaration")


def test_growth_off_a_loss_is_not_reported():
    assert F.growth(10.0, -5.0) is None and F.growth(10.0, 0) is None and F.growth(12.0, 10.0) == 20.0


def test_research_set_financials_are_committed():
    import config
    for t in config.RESEARCH_SET:
        d = F.stored(t)
        assert d and len(d["quarters"]) >= 8 and d["balance_sheets"] and d["ratios"].get("roe") is not None, t


def test_api_financials_precomputed_offline_and_errors(monkeypatch):
    from fastapi.testclient import TestClient
    import api

    def no_network(*a, **k):
        raise AssertionError("must not build a precomputed stock")
    monkeypatch.setattr(api.financials, "build", no_network)
    c = TestClient(api.app)
    r = c.get("/api/financials/polycab")
    assert r.status_code == 200 and r.json()["ticker"] == "POLYCAB" and r.json()["quarters"]
    assert c.get("/api/financials/NOTATICKER").status_code == 404

    def down(*a, **k):
        raise RuntimeError("NSE results listing failed: timeout")
    monkeypatch.setattr(api.financials, "stored", lambda s: None)
    monkeypatch.setattr(api.financials, "build", down)
    bad = c.get("/api/financials/TCS")
    assert bad.status_code == 503 and "NSE" in bad.json()["error"] and bad.json()["fallback_used"] is False
