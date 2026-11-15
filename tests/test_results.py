"""Results card engine (EN-5, QA-3, QA-5 style): parsing, grounding, maths, checks. No network, no AI."""
import pytest

from engine import results as R
from engine.results import Extraction, build_card, growth, parse_amount

# ---------------------------------------------------------------- a synthetic statement page

PAGE = """XYZ INDUSTRIES LIMITED
STATEMENT OF UNAUDITED CONSOLIDATED FINANCIAL RESULTS FOR THE QUARTER ENDED 30.09.2026
(Rs. in Lakhs)
Particulars 30.09.2026 30.06.2026 30.09.2025 30.09.2026 30.09.2025 31.03.2026
1 Revenue from operations 10,000.00 9,000.00 8,000.00 19,000.00 16,000.00 34,000.00
2 Other income 500.00 400.00 300.00 900.00 600.00 1,300.00
3 Total income (1+2) 10,500.00 9,400.00 8,300.00 19,900.00 16,600.00 35,300.00
Finance costs 100.00 1 00.00 100.00 200.00 200.00 400.00
Depreciation and amortisation expense 200.00 180.00 150.00 380.00 300.00 700.00
5 Profit before exceptional items and tax 2,000.00 1,800.00 1,500.00 3,800.00 3,000.00 6,500.00
6 Exceptional items (300.00) - - (300.00) - -
7 Profit before tax (5+6) 1,700.00 1,800.00 1,500.00 3,500.00 3,000.00 6,500.00
8 Total tax expense 425.00 450.00 375.00 875.00 750.00 1,625.00
9 Profit for the period (7-8) 1,275.00 1,350.00 1,125.00 2,625.00 2,250.00 4,875.00
Attributable to owners of the company 1,200.00 1,300.00 1,100.00 2,500.00 2,200.00 4,700.00
"""
COVER = "Dear Sir, the Board approved the results. Please find enclosed. Regards, Company Secretary"
FILING = {"id": "123", "ticker": "XYZ", "company": "XYZ Ltd", "date": "2026-11-05T16:00:00",
          "pdf_url": "https://nsearchives.nseindia.in/corporate/XYZ.pdf", "title": "Financial results"}


def line(label, *vals):
    return {"label": label, "values": list(vals)}


def answer(**over) -> dict:
    ans = {
        "found": True, "basis": "consolidated", "unit": "lakh",
        "columns": ["2026-09-30", "2026-06-30", "2025-09-30"],
        "lines": {
            "revenue": line("Revenue from operations", "10,000.00", "9,000.00", "8,000.00"),
            "other_income": line("Other income", "500.00", "400.00", "300.00"),
            "total_income": line("Total income", "10,500.00", "9,400.00", "8,300.00"),
            "finance_cost": line("Finance costs", "100.00", "1 00.00", "100.00"),
            "depreciation": line("Depreciation", "200.00", "180.00", "150.00"),
            "profit_before_exceptional": line("Profit before exceptional items and tax", "2,000.00", "1,800.00", "1,500.00"),
            "exceptional": line("Exceptional items", "(300.00)", None, None),
            "pbt": line("Profit before tax", "1,700.00", "1,800.00", "1,500.00"),
            "tax": line("Total tax expense", "425.00", "450.00", "375.00"),
            "pat": line("Profit for the period", "1,275.00", "1,350.00", "1,125.00"),
            "pat_owners": line("Owners of the company", "1,200.00", "1,300.00", "1,100.00"),
            "ebitda": None,
        },
        "parts": {},
    }
    ans.update(over)
    return ans


def fake(*answers):
    """A fake model: returns the given answers in turn (validated like the real one)."""
    queue = list(answers)

    def extractor(prompt, meta):
        meta.update(model="fake", tokens_in=1, tokens_out=1, cached=False)
        nxt = queue.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return R.validate_extraction(nxt)
    return extractor


def metric(card, key):
    return next(m for m in card["metrics"] if m["key"] == key)


# ---------------------------------------------------------------- number parsing (QA-3)

@pytest.mark.parametrize("printed, decimals, expected", [
    ("1,234.56", 2, 1234.56),
    ("(1,234.56)", 2, -1234.56),
    ("-1,234.56", 2, -1234.56),
    ("( 52.78)", 2, -52.78),
    ("1 7,987.26", 2, 17987.26),       # stray space inside a number
    ("9O575.33", 2, 90575.33),         # OCR letter O for zero
    ("19,885,3", 1, 19885.3),          # OCR comma for the decimal point
    ("872 41", 2, 872.41),             # OCR space for the decimal point
    ("1,23,456", 0, 123456.0),         # Indian grouping, integer table
    ("-", 2, None), ("", 2, None), (None, 2, None), ("—", 2, None),
])
def test_parse_amount(printed, decimals, expected):
    assert parse_amount(printed, decimals) == expected


@pytest.mark.parametrize("printed", ["31.658", "533-402", "60,n6", "abc"])
def test_parse_amount_rejects_garbage_and_three_decimals(printed):
    with pytest.raises(ValueError):
        parse_amount(printed, 2)


def test_page_numbers_handle_split_and_misread_numbers():
    nums = R.page_numbers("Finance costs 4 28.91 431.70\nPAT 19,885,3 28,947.9\nX 872 41 579.23")
    for v in (428.91, 431.70, 19885.3, 872.41, 579.23):
        assert R.is_grounded(v, nums)
    assert R.is_grounded(-428.91, nums)              # sign is ignored
    assert not R.is_grounded(999.99, nums)


def test_clean_ocr_numbers_touches_numbers_only():
    assert R.clean_ocr_numbers("Other 3O.O6.2O26 9O575.33 Owners Ocean") == "Other 30.06.2026 90575.33 Owners Ocean"


# ---------------------------------------------------------------- growth maths (QA-3)

def test_growth_normal_and_rounding():
    assert growth(110.0, 100.0) == (10.0, None)
    assert growth(90.0, 100.0) == (-10.0, None)
    assert growth(1333.07, 1369.53) == (-2.7, None)


def test_growth_zero_and_negative_bases():
    assert growth(50.0, 0.0) == (None, "zero base")
    assert growth(50.0, -20.0) == (None, "turned to profit")
    assert growth(-10.0, -20.0) == (None, "loss narrowed")
    assert growth(-30.0, -20.0) == (None, "loss widened")
    assert growth(-10.0, 20.0) == (-150.0, "turned to loss")
    assert growth(None, 20.0) == (None, "n/a")


def test_fiscal_label():
    from datetime import date
    assert R.fiscal_label(date(2026, 9, 30)) == "Q2 FY27"
    assert R.fiscal_label(date(2026, 12, 31)) == "Q3 FY27"
    assert R.fiscal_label(date(2027, 3, 31)) == "Q4 FY27"
    assert R.fiscal_label(date(2026, 6, 30)) == "Q1 FY27"


# ---------------------------------------------------------------- columns and units

def test_check_columns():
    from datetime import date
    ok, err = R.check_columns(["2026-09-30", "2026-06-30", "2025-09-30"], date(2026, 11, 5))
    assert err is None and ok[0] == date(2026, 9, 30)
    _, err = R.check_columns(["2026-09-30", "2025-09-30", "2026-06-30"], date(2026, 11, 5))
    assert "not latest quarter" in err                       # columns swapped
    _, err = R.check_columns(["2025-09-30", "2025-06-30", "2024-09-30"], date(2026, 11, 5))
    assert "does not match" in err                           # a stale statement


def test_unit_from_header_beats_the_model():
    page = "ABC LTD\nStatement of results\n(₹ million)\nParticulars ..."
    assert R.pick_unit("crore", page, page) == ("million", None)          # model was wrong
    unit, err = R.pick_unit("crore", "ABC\nno unit here", "ABC\nno unit here")
    assert unit is None and "could not be confirmed" in err


# ---------------------------------------------------------------- full card with a fake model

def test_company_card_happy_path_converts_lakh_to_crore():
    card = build_card(FILING, [COVER, PAGE], extractor=fake(answer()))
    assert card["status"] == "ok" and card["card_type"] == "company"
    assert card["basis"] == "consolidated" and card["source_unit"] == "lakh" and card["unit"] == "Rs crore"
    assert card["period"]["label"] == "Q2 FY27" and card["pages"] == [2]
    rev = metric(card, "revenue")
    assert rev["values"] == {"current": 100.0, "prev_quarter": 90.0, "year_ago": 80.0}   # lakh / 100
    assert (rev["qoq_pct"], rev["yoy_pct"]) == (11.1, 25.0)
    assert rev["source"]["page"] == 2 and rev["source"]["line"] == "Revenue from operations"
    pat = metric(card, "pat")
    assert pat["values"]["current"] == 12.0 and pat["note"] == "attributable to owners"
    assert all(c["passed"] for c in card["checks"]) and len(card["checks"]) == 3
    assert any("took ₹3.0 crore off PBT" in w for w in card["warnings"])


def test_ebitda_is_computed_with_formula_when_not_printed():
    card = build_card(FILING, [COVER, PAGE], extractor=fake(answer()))
    e = metric(card, "ebitda")
    # (2000 + 100 + 200 - 500) lakh = 18 crore; uses profit BEFORE exceptional items
    assert e["computed"] is True and e["values"]["current"] == 18.0
    assert e["values"]["prev_quarter"] == 16.8 and e["values"]["year_ago"] == 14.5
    assert "other income" in e["formula"] and set(e["inputs"]) == {
        "profit_before_exceptional", "finance_cost", "depreciation", "other_income"}


def test_printed_ebitda_is_used_as_is():
    page = PAGE + "EBITDA 2,345.00 2,100.00 1,800.00 4,445.00 3,600.00 7,000.00\n"
    ans = answer()
    ans["lines"]["ebitda"] = line("EBITDA", "2,345.00", "2,100.00", "1,800.00")
    e = metric(build_card(FILING, [COVER, page], extractor=fake(ans)), "ebitda")
    assert e["computed"] is False and e["values"]["current"] == 23.45


def test_ungrounded_number_is_dropped_never_shown():
    ans = answer()
    ans["lines"]["pat_owners"] = line("Owners", "9,999.00", "1,300.00", "1,100.00")   # 9,999 is not on the page
    ans["lines"]["pat"] = line("Profit", "1,276.00", "1,350.00", "1,125.00")          # nor is 1,276
    card = build_card(FILING, [COVER, PAGE], extractor=fake(ans))
    assert card["status"] == "partial"
    assert metric(card, "pat")["available"] is False
    assert any("not printed on the page" in w for w in card["warnings"])


def test_shifted_column_is_caught_by_a_cross_check():
    ans = answer()
    ans["lines"]["pat"] = line("Profit", "1,350.00", "1,125.00", "1,275.00")   # grounded, wrong columns
    ans["lines"]["pat_owners"] = None                                          # so the shifted row is shown
    card = build_card(FILING, [COVER, PAGE], extractor=fake(ans))
    pat_check = next(c for c in card["checks"] if c["name"].startswith("PAT"))
    assert pat_check["passed"] is False and "off by" in pat_check["detail"]


def test_revenue_from_sub_rows_is_summed_by_python():
    page = PAGE.replace("1 Revenue from operations 10,000.00 9,000.00 8,000.00 19,000.00 16,000.00 34,000.00",
                        "Sale of products 9,800.00 8,850.00 7,900.00 1 1 1\nOther operating revenue 200.00 150.00 100.00 1 1 1")
    ans = answer(parts={"revenue": [line("Sale of products", "9,800.00", "8,850.00", "7,900.00"),
                                    line("Other operating revenue", "200.00", "150.00", "100.00")]})
    ans["lines"]["revenue"] = None
    rev = metric(build_card(FILING, [COVER, page], extractor=fake(ans)), "revenue")
    assert rev["values"]["current"] == 100.0 and "sum of 2 printed lines" in rev["source"]["note"]


def test_wrong_quarter_columns_fail_the_card():
    card = build_card(FILING, [COVER, PAGE], extractor=fake(answer(columns=["2026-09-30", "2025-09-30", "2026-06-30"])))
    assert card["status"] == "could not extract" and "Column check failed" in card["reason"]


def test_ai_failure_is_retryable_and_says_so():
    card = build_card(FILING, [COVER, PAGE], extractor=fake(RuntimeError("All AI calls failed")))
    assert card["status"] == "could not extract" and card["retryable"] is True


def test_bad_ai_shape_is_rejected():
    with pytest.raises(ValueError, match="wrong shape"):
        R.validate_extraction({"found": True, "columns": ["a", "b", "c"], "lines": {"revenue": "10,000.00"}})


def test_no_statement_and_scanned_pdf_give_clear_reasons():
    card = build_card(FILING, [COVER], extractor=fake())
    assert "No readable quarterly results table" in card["reason"]
    card = build_card(FILING, [COVER, "", "", ""], extractor=fake())
    assert "scanned images" in card["reason"]
    card = build_card(FILING, ["", ""], extractor=fake())
    assert "scanned image" in card["reason"]


def test_falls_back_to_standalone_when_consolidated_cannot_be_read():
    standalone = PAGE.replace("CONSOLIDATED", "STANDALONE")
    bad = answer(unit="crore")                  # consolidated attempt: unit not on the page header ...
    bad_page = PAGE.replace("(Rs. in Lakhs)", "(garbled)")
    card = build_card(FILING, [COVER, bad_page, standalone], extractor=fake(bad, answer(basis="standalone")))
    assert card["status"] == "ok" and card["basis"] == "standalone" and card["pages"] == [3]
    assert "could not be read" in card["basis_note"]
    assert card["warnings"][0].startswith("Consolidated statement:")


def test_bank_card_is_bank_lite():
    page = """ABC BANK LIMITED
UNAUDITED CONSOLIDATED FINANCIAL RESULTS FOR THE QUARTER ENDED SEPTEMBER 30, 2026
(₹ in crore)
Particulars 30.09.2026 30.06.2026 30.09.2025 30.09.2026 30.09.2025 31.03.2026
1 Interest earned 9,000.00 8,800.00 8,000.00 17,800.00 16,000.00 33,000.00
2 Other income 1,000.00 900.00 800.00 1,900.00 1,600.00 3,500.00
3 Total income 10,000.00 9,700.00 8,800.00 19,700.00 17,600.00 36,500.00
4 Interest expended 5,000.00 4,900.00 4,500.00 9,900.00 9,000.00 18,500.00
10 Profit from ordinary activities before tax 2,000.00 1,900.00 1,700.00 3,900.00 3,400.00 7,200.00
11 Tax expense 500.00 475.00 425.00 975.00 850.00 1,800.00
12 Net profit for the period 1,500.00 1,425.00 1,275.00 2,925.00 2,550.00 5,400.00
"""
    ans = answer(unit="crore", lines={
        "total_income": line("Total income", "10,000.00", "9,700.00", "8,800.00"),
        "other_income": line("Other income", "1,000.00", "900.00", "800.00"),
        "pbt": line("Profit before tax", "2,000.00", "1,900.00", "1,700.00"),
        "tax": line("Tax expense", "500.00", "475.00", "425.00"),
        "pat": line("Net profit", "1,500.00", "1,425.00", "1,275.00"),
    })
    card = build_card(FILING, [COVER, page], extractor=fake(ans))
    assert card["card_type"] == "bank" and card["status"] == "ok"
    keys = [m["key"] for m in card["metrics"]]
    assert keys == ["total_income", "ebitda", "pbt", "pat"]
    assert metric(card, "ebitda") == {"key": "ebitda", "label": "EBITDA", "available": False, "note": "n/a for banks"}
    assert metric(card, "total_income")["values"]["current"] == 10000.0
    assert card["margins"] == []


def test_verdict_and_margins():
    card = build_card(FILING, [COVER, PAGE], extractor=fake(answer()))
    # revenue +25% YoY, PAT (owners) +9.1% YoY, PBT +13.3%, EBITDA +24.1%: all up
    assert card["verdict"].startswith("All 4 lines up year on year.")
    m = {x["key"]: x for x in card["margins"]}
    assert m["ebitda_margin"]["values"]["current"] == 18.0
    assert m["ebitda_margin"]["yoy_bps"] == round((18.0 - 18.1) * 100)
