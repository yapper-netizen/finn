"""Research engine (EN-10..16, QA-5): quote guard, timing, merging, facts, verdicts, jobs. No network, no AI."""
import time

import pytest

from engine import research as R
from engine import research_jobs as J

T_PAGE_1 = "Moderator: welcome to the call.\nAnalyst: what is your outlook?"
T_PAGE_2 = ("Management: We expect revenue growth of 20% in FY26 and EBITDA margin of 12% to 13%.\n"
            "We plan to commis-\nsion the new plant by March 2027. Capex will be Rs 500 crore.")
TRANSCRIPT = [T_PAGE_1, T_PAGE_2]


def card(q_end, label, rev, rev_yago, pat, pat_yago, ebitda=None, basis="consolidated", fid="1"):
    m = [{"key": "revenue", "label": "Revenue", "available": True, "source": {"page": 3},
          "values": {"current": rev, "prev_quarter": None, "year_ago": rev_yago},
          "yoy_pct": round((rev - rev_yago) / rev_yago * 100, 1), "yoy_note": None},
         {"key": "pat", "label": "PAT", "available": True, "source": {"page": 3},
          "values": {"current": pat, "prev_quarter": None, "year_ago": pat_yago},
          "yoy_pct": round((pat - pat_yago) / pat_yago * 100, 1), "yoy_note": None}]
    margins = []
    if ebitda:
        m.append({"key": "ebitda", "label": "EBITDA", "available": True, "computed": True, "source": {"page": 3},
                  "values": {"current": ebitda, "prev_quarter": None, "year_ago": None}, "yoy_pct": None, "yoy_note": "n/a"})
        margins = [{"key": "ebitda_margin", "label": "EBITDA margin", "values": {"current": round(ebitda / rev * 100, 1)}, "yoy_bps": 50}]
    return {"status": "ok", "filing_id": fid, "pdf_url": f"https://nsearchives.nseindia.in/corporate/R{fid}.pdf",
            "basis": basis, "period": {"current": q_end, "label": label}, "metrics": m, "margins": margins}


FY26 = [card("2025-06-30", "Q1 FY26", 100, 80, 10, 8, 12, fid="1"), card("2025-09-30", "Q2 FY26", 110, 90, 11, 9, 13.2, fid="2"),
        card("2025-12-31", "Q3 FY26", 120, 100, 12, 10, 15, fid="3"), card("2026-03-31", "Q4 FY26", 130, 110, 13, 11, 16, fid="4")]


# ---------------------------------------------------------------- quote guard (EN-15, D-041)

def test_verbatim_quote_is_found_and_page_corrected():
    page, score = R.verify_quote("We expect revenue growth of 20% in FY26", TRANSCRIPT, hint_page=1)
    assert (page, score) == (2, 1.0)                          # model said page 1; FINN cites page 2


def test_quote_survives_pdf_line_break_hyphen_and_punctuation():
    page, _ = R.verify_quote("We plan to commission the new plant by March 2027", TRANSCRIPT, hint_page=2)
    assert page == 2


def test_invented_quote_is_rejected():
    page, score = R.verify_quote("We guarantee 40% profit growth every year for the next decade", TRANSCRIPT, 2)
    assert page is None and score < 0.9


def test_slightly_misquoted_text_passes_only_above_threshold():
    near = "We expect revenue growth of 20 % in FY 26 and EBITDA margin of 12% to 13%"   # spacing only
    assert R.verify_quote(near, TRANSCRIPT, 2)[0] == 2
    changed = "We expect revenue growth of 35% in FY28 and EBITDA margin of 19% to 21%"
    assert R.verify_quote(changed, TRANSCRIPT, 2)[0] is None


def test_pick_pages_prefers_guidance_pages_within_budget():
    pages = ["Safe harbour statement only.", T_PAGE_2, "Thank you all for joining.", T_PAGE_2 * 50]
    assert R.pick_pages(pages, max_chars=len(T_PAGE_2) + 10) == [1]


# ---------------------------------------------------------------- merging and timing

def promise(pid, statement, made_in, made_on, metric="revenue_growth", due=None):
    return {"id": pid, "statement": statement, "metric": metric, "made_in": made_in, "made_on": made_on, "due": due}


def test_restated_promise_is_merged_into_the_first():
    ps = [promise("P1", "FMEG EBITDA margin 8% to 10% by FY30", "Q2 FY27", "2026-10-19", "other", "2030-03-31"),
          promise("P2", "Progress towards 8% to 10% EBITDA in FMEG by FY 2030", "Q3 FY26", "2026-01-22", "ebitda_margin", "2030-03-31"),
          promise("P3", "Grow revenue 20% in FY27", "Q3 FY26", "2026-01-22")]
    out = R.dedupe_promises(ps)
    assert len(out) == 2
    first = next(p for p in out if "FMEG" in p["statement"])
    assert first["made_in"] == "Q3 FY26" and first["restated_in"] == ["Q2 FY27"]
    assert [p["id"] for p in out] == ["P1", "P2"]


def test_parse_due_snaps_to_quarter_end():
    from datetime import date
    assert R._parse_due("2027-03-30") == date(2027, 3, 31)
    assert R._parse_due("2027-02-28") is None and R._parse_due(None) is None


# ---------------------------------------------------------------- facts (Python numbers)

def test_card_facts_quarterly_and_full_year_totals():
    facts = R.card_facts(FY26)
    texts = [f["text"] for f in facts]
    assert any(t.startswith("Revenue Q4 FY26: ₹130 cr, up 18.2% YoY") for t in texts)
    fy = next(f for f in facts if f["metric"] == "revenue_fy")
    assert fy["quarter"] == "FY26" and fy["value"] == round((460 - 380) / 380 * 100, 1)   # 21.1
    assert "sum of 4 quarters" in fy["text"]
    margin_fy = next(f for f in facts if f["metric"] == "ebitda_margin_fy")
    assert margin_fy["value"] == round(56.2 / 460 * 100, 1)
    assert all(f["source"]["pdf_url"].startswith("https://nsearchives") for f in facts)


def test_no_full_year_total_when_bases_are_mixed():
    mixed = FY26[:3] + [card("2026-03-31", "Q4 FY26", 130, 110, 13, 11, basis="standalone", fid="4")]
    assert not any(f["metric"].endswith("_fy") for f in R.card_facts(mixed))


# ---------------------------------------------------------------- the whole pipeline with fakes

class FakeAI:
    """Answers by schema: promises, verdicts, bull/bear. Records calls."""

    def __init__(self, promises, verdicts, bull_bear):
        self.answers = {"PromisesOut": promises, "VerdictsOut": verdicts, "BullBearOut": bull_bear, "TonesOut": {"tones": []}}
        self.calls = []

    def __call__(self, prompt, strong=False, validate=None, use_cache=False, meta=None, schema=None):
        self.calls.append((schema.__name__, strong))
        if meta is not None:
            meta.update(model="fake-strong" if strong else "fake-cheap", tokens_in=10, tokens_out=5, cached=True)
        return validate(self.answers[schema.__name__])


def run(ai, cards_=FY26):
    found = {"symbol": "XYZ", "company": "XYZ Ltd",
             "transcripts": [{"date": "2025-05-10T10:00:00", "quarter_end": "2025-03-31",
                              "pdf_url": "https://nsearchives.nseindia.in/corporate/T1.pdf"}],
             "results": [{"id": c["filing_id"], "date": "2026-05-01T10:00:00"} for c in cards_]}
    by_id = {c["filing_id"]: c for c in cards_}
    steps = []
    out = R.build_research("XYZ", progress=steps.append, ask=ai, finder=lambda t: found,
                           pages_loader=lambda url: TRANSCRIPT, card_getter=lambda f: by_id[f["id"]], pace=lambda m: None,
                           fin_getter=lambda s: None)
    return out, steps


PROMISES = {"promises": [
    {"metric": "revenue_growth", "statement": "Revenue growth of 20% in FY26", "period_text": "FY26",
     "due_quarter_end": "2026-03-31", "quote": "We expect revenue growth of 20% in FY26", "page": 2},
    {"metric": "ebitda_margin", "statement": "EBITDA margin 12-13% in FY28", "period_text": "FY28",
     "due_quarter_end": "2028-03-31", "quote": "EBITDA margin of 12% to 13%", "page": 2},
    {"metric": "other", "statement": "Capex of Rs 500 crore", "period_text": "FY27",
     "due_quarter_end": "2027-03-31", "quote": "Capex will be Rs 500 crore", "page": 2},
    {"metric": "pat_growth", "statement": "PAT to double", "period_text": "FY26",
     "due_quarter_end": "2026-03-31", "quote": "Our profit will double this year, we promise", "page": 2},   # fake quote
]}


def test_pipeline_end_to_end_with_fake_model():
    fy_id = next(f["id"] for f in R.card_facts(FY26) if f["metric"] == "revenue_fy")
    ai = FakeAI(PROMISES,
                {"verdicts": [{"promise_id": "P1", "verdict": "Delivered", "fact_ids": ["F99", fy_id], "reason": "Grew 21.1%."}]},
                {"bull": [{"point": "Revenue grew 21% in FY26.", "quote": None, "transcript_id": None, "page": None, "fact_ids": [fy_id]},
                          {"point": "Invented strength.", "quote": "We are the best company in the world", "transcript_id": "T1", "page": 2, "fact_ids": []}],
                 "bear": [{"point": "Capex is heavy.", "quote": "Capex will be Rs 500 crore", "transcript_id": "T1", "page": 2, "fact_ids": []}]})
    out, steps = run(ai)
    by_stmt = {p["statement"]: p for p in out["promises"]}
    assert "PAT to double" not in by_stmt                                      # fake quote dropped (QA-5)
    assert any("quote was not found" in w for w in out["warnings"])
    rev = by_stmt["Revenue growth of 20% in FY26"]
    assert rev["verdict"] == "Delivered" and rev["fact_ids"] == [fy_id]        # unknown F99 discarded
    assert rev["facts"][0]["metric"] == "revenue_fy" and rev["receipt"]["page"] == 2
    assert by_stmt["EBITDA margin 12-13% in FY28"]["verdict"] == "Too early"   # Python timing, no AI
    assert by_stmt["Capex of Rs 500 crore"]["verdict"] in ("Too early", "Not checkable")   # capex is checkable since 10f (XBRL)
    assert out["counts"] == {"Delivered": 1, "Partial": 0, "Missed": 0, "Too early": 2, "Not checkable": 0}   # capex now timed, 10f
    assert [p["point"] for p in out["bull"]] == ["Revenue grew 21% in FY26."]   # unsourced point dropped
    assert out["bear"][0]["receipt"]["page"] == 2
    import config
    assert ("VerdictsOut", True) in ai.calls and ("PromisesOut", config.RESEARCH_EXTRACT_STRONG) in ai.calls   # routing
    assert steps[0].startswith("Finding") and steps[-1] == "Done"


def test_verdict_without_valid_fact_becomes_not_checkable():
    ai = FakeAI({"promises": PROMISES["promises"][:1]},
                {"verdicts": [{"promise_id": "P1", "verdict": "Missed", "fact_ids": ["F404"], "reason": "x"}]},
                {"bull": [], "bear": []})
    out, _ = run(ai)
    assert out["promises"][0]["verdict"] == "Not checkable"


def test_bad_ai_json_shape_is_rejected():
    with pytest.raises(ValueError, match="wrong shape"):
        R._validator(R.PromisesOut)({"promises": [{"metric": "revenue_growth"}]})


def test_no_transcripts_is_a_clear_lookup_error():
    with pytest.raises(LookupError, match="no earnings-call transcripts"):
        R.build_research("XYZ", ask=lambda *a, **k: None,
                         finder=lambda t: {"symbol": "XYZ", "company": "X", "transcripts": [], "results": []})


# ---------------------------------------------------------------- jobs (API-4)

def test_jobs_pending_then_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(J.config, "RESEARCH_DIR", str(tmp_path / "snap"))
    monkeypatch.setattr(J.config, "CACHE_DIR", str(tmp_path / "cache"))

    def builder(symbol, progress):
        progress("Finding transcripts")
        time.sleep(0.2)
        return {"ticker": symbol, "status": "ready", "engine_version": R.ENGINE_VERSION}
    jobs = J.ResearchJobs(builder=builder)
    first = jobs.request("tcs")
    assert first["status"] in ("queued", "pending") and first["ticker"] == "TCS"
    for _ in range(50):
        r = jobs.request("TCS")
        if r["status"] == "ready":
            break
        time.sleep(0.05)
    assert r["status"] == "ready"


def test_jobs_report_errors_and_bad_tickers(tmp_path, monkeypatch):
    monkeypatch.setattr(J.config, "RESEARCH_DIR", str(tmp_path / "snap"))
    monkeypatch.setattr(J.config, "CACHE_DIR", str(tmp_path / "cache"))

    def builder(symbol, progress):
        raise LookupError("NSE has no earnings-call transcripts for TCS")
    jobs = J.ResearchJobs(builder=builder)
    jobs.request("TCS")
    for _ in range(50):
        r = jobs.request("TCS")
        if r["status"] == "error":
            break
        time.sleep(0.05)
    assert r["status"] == "error" and r["retryable"] is False and "transcripts" in r["error"]
    with pytest.raises(ValueError):
        jobs.request("NOTATICKER")


def test_research_set_is_precomputed_and_committed():
    import config
    for t in config.RESEARCH_SET:
        data = J.stored(t)
        assert data and data["status"] == "ready" and data["promises"], t


def test_api_research_precomputed_and_bad_ticker(monkeypatch):
    """Offline: a precomputed stock answers from the committed JSON; a bad ticker is a clear 404."""
    from fastapi.testclient import TestClient
    import api

    def no_network(*a, **k):
        raise AssertionError("research endpoint must not build a precomputed stock")
    monkeypatch.setattr(api.research_jobs, "_builder", no_network)
    c = TestClient(api.app)
    r = c.get("/api/research/polycab")
    assert r.status_code == 200 and r.json()["status"] == "ready" and r.json()["ticker"] == "POLYCAB"
    bad = c.get("/api/research/NOTATICKER")
    assert bad.status_code == 404 and "not a listed NSE ticker" in bad.json()["error"]


def test_cover_letter_is_detected():
    assert R.is_cover_letter(["Sub: Transcript of Earnings Call. The transcript is available at www.x.com"])
    assert not R.is_cover_letter([T_PAGE_2] * 5)


def test_linked_pdf_must_be_public_https(monkeypatch):
    from data import docs
    for bad in ("http://example.com/t.pdf", "https://127.0.0.1/t.pdf", "https://example.com/t.html"):
        with pytest.raises(ValueError):
            docs.check_linked_url(bad)
    monkeypatch.setattr(docs.socket, "getaddrinfo", lambda h, p: [(0, 0, 0, "", ("10.0.0.5", 443))])
    with pytest.raises(ValueError, match="non-public"):
        docs.check_linked_url("https://intranet.example.com/t.pdf")


def test_quote_must_state_the_target():
    # verbatim but empty: the target was in the analyst's question (seen on HAVELLS)
    assert not R.quote_states_target("Over two percentage points margin improvement", "No, that remains as is.")
    assert R.quote_states_target("EBITDA margin 11% to 13%", "we should expect 11% to 13% EBITDA margin")
    assert R.quote_states_target("Double revenue by FY30", "we aim to double our revenue by 2030")
    assert R.quote_states_target("Growth momentum to continue", "we are confident of the momentum")   # no number


# ---------------------------------------------------------------- block 10f: XBRL facts, say-do, tone

FIN = {"basis": "consolidated", "quarters": [
    {"period_end": e, "label": l, "url": "https://nsearchives.nseindia.in/x.xml", "tax": 25.0, "pbt": 100.0, "revenue_yoy": g,
     "segments": [{"name": "Plumbing", "key": "plumbing", "revenue": rp, "margin": 15.0},
                  {"name": "Paints", "key": "paints", "revenue": rq, "margin": 5.0}]}
    for e, l, rp, rq, g in [("2025-06-30", "Q1 FY26", 100, 20, 10.0), ("2025-09-30", "Q2 FY26", 100, 20, 12.0),
                            ("2025-12-31", "Q3 FY26", 100, 20, 11.0), ("2026-03-31", "Q4 FY26", 100, 20, 30.0),
                            ("2026-06-30", "Q1 FY27", 120, 30, 9.0)]],
       "cash_flows": [{"label": "H2 FY26", "capex": 180.0, "cash_conversion": 120.0, "url": "u2"},
                      {"label": "H1 FY26", "capex": 150.0, "cash_conversion": 80.0, "url": "u1"}]}


def test_xbrl_facts_segments_capex_tax():
    facts = R.xbrl_facts(FIN, 10)
    texts = [f["text"] for f in facts]
    assert facts[0]["id"] == "F10"
    seg = next(f for f in facts if f["metric"] == "segment_revenue" and "Paints" in f["text"] and "Q1 FY27" in f["text"])
    assert seg["value"] == 50.0 and seg["unit"] == "% YoY"                     # 30 vs 20 a year ago
    assert any("not EBITDA" in t for t in texts)                              # segment result labelled honestly
    capex_fy = next(f for f in facts if f["metric"] == "capex" and f["quarter"] == "FY26")
    assert capex_fy["value"] == 330.0 and capex_fy["unit"] == "cr"
    assert next(f for f in facts if f["metric"] == "tax_rate")["value"] == 25.0
    assert R.xbrl_facts(None, 1) == []


def test_worth_judging_skips_promises_without_filed_figures():
    segs = ["Plumbing", "Paints"]
    assert R.worth_judging({"metric": "other", "statement": "Capex of 300 to 350 crore for FY27"}, segs)
    assert R.worth_judging({"metric": "other", "statement": "Paints to grow 20% this year"}, segs)
    assert not R.worth_judging({"metric": "other", "statement": "Exports above 10% of revenue by FY30"}, segs)
    assert not R.worth_judging({"metric": "other", "statement": "Nagarro deal closure by Q1 CY27"}, segs)
    assert R.worth_judging({"metric": "revenue_growth", "statement": "Grow 1.5x the market"}, segs)


def test_say_do_needs_target_in_the_promise_and_matching_fact():
    facts = {"F1": {"value": 1480.0, "unit": "cr", "text": "Capex FY26: ₹1,480 cr"},
             "F2": {"value": 21.1, "unit": "% YoY", "text": "Revenue FY26 up 21.1%"}}
    p = {"statement": "Capex of ₹12 billion to ₹16 billion a year", "receipt": {"quote": "12 to 16 billion"},
         "target": {"low": 12, "high": 16}, "actual_fact_id": "F1"}
    assert R.say_do(p, facts) == {"low": 1200, "high": 1600, "actual": 1480.0, "unit": "cr", "fact": "Capex FY26: ₹1,480 cr"}
    invented = {**p, "statement": "Revenue growth of 20%", "receipt": {"quote": "20% growth"}, "target": {"low": 25, "high": None},
                "actual_fact_id": "F2"}
    assert R.say_do(invented, facts) is None                                 # 25 is not in the promise's words
    assert R.say_do({**p, "actual_fact_id": None}, facts) is None


def test_tone_vs_numbers_verifies_quote_and_flags_gap():
    pages = ["cover " * 100, "Management: Demand was very strong and we are confident of the year ahead. " * 8, "more " * 100]
    ts = [{"id": "T1", "quarter": "Q4 FY26", "quarter_end": "2026-03-31", "pages": pages, "pdf_url": "u", "label": "Q4 FY26 earnings call"}]

    def ask(prompt, strong, validate, use_cache, meta, schema):
        assert not strong and "CALL T1" in prompt
        return validate({"tones": [{"transcript_id": "T1", "score": 2, "label": "upbeat on demand",
                                    "quote": "Demand was very strong and we are confident of the year ahead.", "page": 2},
                                   {"transcript_id": "T9", "score": 0, "label": "x", "quote": "y", "page": 1}]})
    rows = R.tone_vs_numbers(ask, "XYZ", ts, FIN, {})
    assert len(rows) == 1 and rows[0]["growth"] == 30.0 and rows[0]["growth_next"] == 9.0
    assert rows[0]["gap"].startswith("Upbeat call, then growth slowed") and rows[0]["receipt"]["page"] == 2

    def bad(prompt, strong, validate, use_cache, meta, schema):
        return validate({"tones": [{"transcript_id": "T1", "score": 1, "label": "x", "quote": "We never said this sentence at all.", "page": 2}]})
    assert R.tone_vs_numbers(bad, "XYZ", ts, FIN, {}) == []


def test_guard_verdict_half_year_capex_and_outside_figures():
    facts = {"F1": {"metric": "capex", "quarter": "H1 FY27", "value": 598.0, "unit": "cr", "text": "Capex H1 FY27: ₹598 cr"},
             "F2": {"metric": "ebitda_margin", "quarter": "Q2 FY27", "value": 10.0, "unit": "%", "text": "EBITDA margin 10%"}}
    capex = {"verdict": "Delivered", "statement": "Annual capex of ₹12 to 16 billion", "receipt": {"quote": "12 to 16 billion"},
             "target": {"low": 12, "high": 16}, "actual_fact_id": "F1"}
    R.guard_verdict(capex, facts)
    assert capex["verdict"] == "Too early" and capex["decided_by"] == "rules"
    margin = {"verdict": "Delivered", "statement": "EBITDA margin of 12% to 14%", "receipt": {"quote": "12% to 14%"},
              "target": {"low": 12, "high": 14}, "actual_fact_id": "F2"}
    R.guard_verdict(margin, facts)
    assert margin["verdict"] == "Not checkable" and "outside the promise" in margin["reason"]
    beat = {**margin, "verdict": "Delivered", "target": {"low": 8, "high": 9}, "statement": "EBITDA margin of 8% to 9%",
            "receipt": {"quote": "8% to 9%"}}
    R.guard_verdict(beat, facts)
    assert beat["verdict"] == "Delivered"                                      # above a margin range = beat


def test_operating_margin_promise_is_not_judged_against_ebitda():
    assert not R.worth_judging({"metric": "other", "statement": "Maintain operating margin in the 16% to 17% range"}, [])
    assert not R.worth_judging({"metric": "ebitda_margin", "statement": "EBIT margin of 14%"}, [])
    assert R.worth_judging({"metric": "ebitda_margin", "statement": "EBITDA margin of 14%"}, [])


def test_opening_pages_prefer_management_voice():
    pages = ["Cover page and disclaimer text. " * 30,
             "Moderator: Ladies and gentlemen, welcome to the call. Agenda follows. " * 10,
             "We delivered strong growth and our margins expanded; we expect us to keep going. " * 10,
             "We saw our demand rise and we are confident. " * 10,
             "Question from an analyst about pricing in the market today. " * 10]
    assert R.opening_pages(pages) == [2, 3]


def test_target_and_actual_worked_out_in_python_when_model_gives_none():
    assert R.target_from_statement("EBITDA margin of 11% to 13%") == (11.0, 13.0)
    assert R.target_from_statement("Revenue growth of 20%+ in FY27") == (20.0, None)
    assert R.target_from_statement("Tax rate of 22.5% for the year") == (22.5, 22.5)
    assert R.target_from_statement("Margins will improve") == (None, None)
    facts = {"F1": {"id": "F1", "metric": "ebitda_margin", "quarter": "Q1 FY27", "value": 13.8, "unit": "%", "text": "a"},
             "F2": {"id": "F2", "metric": "ebitda_margin", "quarter": "Q2 FY27", "value": 14.4, "unit": "%", "text": "b"},
             "F3": {"id": "F3", "metric": "revenue", "quarter": "Q2 FY27", "value": 30.0, "unit": "% YoY", "text": "c"}}
    p = {"statement": "EBITDA margin of 11% to 13%", "receipt": {"quote": "11% to 13%"}, "fact_ids": ["F1", "F2", "F3"],
         "target": {"low": None, "high": None}, "actual_fact_id": None}
    assert R.say_do(p, facts) == {"low": 11.0, "high": 13.0, "actual": 14.4, "unit": "%", "fact": "b"}


def test_guidance_filter_keeps_stated_headline_numbers():
    assert R.is_guidance({"metric": "ebitda_margin", "statement": "Margins will improve"})
    assert R.is_guidance({"metric": "other", "statement": "Capex of 300 to 350 crore in FY27"})
    assert not R.is_guidance({"metric": "other", "statement": "CPVC plant to be complete by September 2026"})
    assert not R.is_guidance({"metric": "other", "statement": "Healthy growth in the second half"})
