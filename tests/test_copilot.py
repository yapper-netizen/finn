"""Copilot (D-107): rules, Python number answers, grounded AI answers with verified citations. No network."""
from fastapi.testclient import TestClient

from engine import copilot as C

FIN = {"basis": "consolidated", "bank": False,
       "quarters": [{"label": "Q2 FY27", "period_end": "2026-09-30", "url": "u", "revenue": 1000.0, "revenue_yoy": 20.0,
                     "revenue_qoq": 5.0, "ebitda": 150.0, "ebitda_margin": 15.0, "ebitda_yoy": 10.0, "pat": 90.0, "pat_margin": 9.0,
                     "pbt": 120.0, "tax": 30.0, "finance_costs": 5.0, "dep": 20.0, "other_income": 5.0, "pat_yoy": 8.0, "pat_qoq": 2.0,
                     "segments": [{"name": "Cables", "revenue": 800.0, "margin": 14.0}, {"name": "Fans", "revenue": 200.0, "margin": 6.0}]},
                    {"label": "Q1 FY27", "period_end": "2026-06-30", "url": "u1", "revenue": 950.0, "ebitda_margin": 14.0, "segments": []}],
       "ratios": {"label": "Q2 FY27", "roe": 22.0, "roe_basis": "average equity", "roce": 30.0, "ttm_revenue": 3800.0, "ttm_pat": 340.0,
                  "cash_cycle_days": 60, "inventory_days": 50, "receivable_days": 30, "payable_days": 20, "as_of": "2026-09-30"},
       "balance_sheets": [{"as_of": "2026-09-30", "equity": 1500.0, "debt": 100.0, "cash": 400.0, "net_cash": 300.0, "de_ratio": 0.07, "url": "b"}],
       "cash_flows": [{"label": "H1 FY27", "cfo": 160.0, "pat": 180.0, "capex": 60.0, "fcf": 100.0, "cash_conversion": 88.9, "url": "c"}]}
PAGES = ["Cover page and safe harbour statement for the call. " * 10,
         "Management: Our EBITDA margin expanded because of a better product mix and lower copper costs this quarter. "
         "We expect the fans business to keep growing faster than cables over the next two years.",
         "Analyst: I am worried about rising competition in fans and the impact on pricing power."]
RESEARCH = {"ticker": "XYZ", "company": "XYZ Ltd", "facts": [{"id": "F1", "text": "EBITDA margin Q2 FY27: 15.0%", "source": {"pdf_url": "r"}}],
            "sources": {"transcripts": [{"label": "Q2 FY27 earnings call", "pdf_url": "t"}]}}


def fake(answer):
    calls = []

    def ask(prompt, strong, validate, use_cache, meta, schema):
        calls.append(prompt)
        assert not strong and "ONLY the material below" in prompt
        return validate(answer)
    return ask, calls


def test_rules_refuse_advice_and_empty_questions():
    ask, calls = fake({})
    a = C.ask_stock("What is the price target?", "XYZ", RESEARCH, FIN, ask=ask, loader=lambda u: PAGES)
    assert a["refused"] and a["answered_by"] == "rules" and not calls
    assert C.ask_stock("  ", "XYZ", RESEARCH, FIN, ask=ask)["refused"]
    assert not C.REFUSE.search("What do customers buy most?")


def test_number_questions_are_answered_by_python():
    ask, calls = fake({})
    for q, expect in [("What was EBITDA margin last quarter?", "15.0%"), ("What is the debt?", "net cash ₹300 cr"),
                      ("Segment mix?", "Cables 80%"), ("ROCE?", "30.0%"), ("What is the cash cycle?", "60 days"),
                      ("Revenue growth in Q2 FY27?", "+20.0%"), ("Capex?", "₹60 cr")]:
        a = C.ask_stock(q, "XYZ", RESEARCH, FIN, ask=ask, loader=lambda u: PAGES)
        assert a["answered_by"] == "python" and expect in a["answer"], (q, a["answer"])
        assert a["citations"][0]["kind"] == "figure"
    assert not calls


def test_why_question_goes_to_ai_with_verified_quote():
    ask, calls = fake({"answer": "Management says margins expanded on a better mix and lower copper costs.", "found": True,
                       "citations": [{"passage": "P1", "quote": "Our EBITDA margin expanded because of a better product mix and lower copper costs"},
                                     {"passage": "P1", "quote": "a sentence that is not in the transcript at all anywhere"},
                                     {"fact": "F1"}, {"fact": "F99"}]})
    a = C.ask_stock("Why did EBITDA margin rise?", "XYZ", RESEARCH, FIN, ask=ask, loader=lambda u: PAGES)
    assert a["answered_by"] == "ai" and not a["refused"]
    assert [c["kind"] for c in a["citations"]] == ["quote", "fact"]          # invented quote and unknown id dropped
    assert a["citations"][0]["page"] == 2 and "copper" in calls[0]


def test_ai_answer_without_valid_citation_is_not_shown():
    ask, _ = fake({"answer": "Margins rose because the CEO is brilliant.", "found": True,
                   "citations": [{"passage": "P1", "quote": "the CEO is brilliant and everyone loves him dearly"}]})
    a = C.ask_stock("Why did margins rise?", "XYZ", RESEARCH, FIN, ask=ask, loader=lambda u: PAGES)
    assert a["refused"] and "could not verify" in a["answer"]
    ask, _ = fake({"answer": "Not in the documents FINN read.", "found": False, "citations": []})
    assert C.ask_stock("What did they say about the moon?", "XYZ", RESEARCH, FIN, ask=ask, loader=lambda u: PAGES)["refused"]


def test_retrieval_ranks_matching_passages():
    chunks = [t for _, t in C.passages(PAGES)]
    assert "competition" in chunks[C.rank("worried about competition in fans", chunks, 1)[0]]
    assert C.suggestions(RESEARCH, FIN)[0].startswith("Why did EBITDA margin rise in Q2 FY27")


def test_filing_copilot_uses_card_figures():
    card = {"ticker": "XYZ", "company": "XYZ Ltd", "pdf_url": "f", "period": {"label": "Q2 FY27"},
            "metrics": [{"key": "pat", "label": "PAT", "available": True, "values": {"current": 90.0}, "yoy_pct": 8.0, "qoq_pct": 2.0}]}
    ask, calls = fake({"answer": "PAT was ₹90 cr.", "found": True, "citations": [{"fact": "F1"}]})
    a = C.ask_filing("What happened to profit?", card, ask=ask, loader=lambda u: PAGES)
    assert a["answered_by"] == "ai" and a["citations"][0]["text"].startswith("PAT Q2 FY27: ₹90.00 cr")


def test_api_ask_number_question_and_errors():
    import api
    c = TestClient(api.app)
    r = c.post("/api/ask", json={"question": "What was EBITDA margin last quarter?", "ticker": "POLYCAB"})
    assert r.status_code == 200 and r.json()["answered_by"] == "python" and "%" in r.json()["answer"]
    assert c.post("/api/ask", json={"question": "price target?", "ticker": "POLYCAB"}).json()["refused"]
    assert c.post("/api/ask", json={"question": "x", "ticker": "NOTATICKER"}).status_code == 404
    assert c.post("/api/ask", json={"question": "hi"}).status_code == 400
    assert c.post("/api/ask", json={"question": "q" * 400, "ticker": "TCS"}).status_code in (400, 422)


def test_unexplained_why_falls_back_to_the_figure():
    ask, _ = fake({"answer": "Not in the documents FINN read.", "found": False, "citations": []})
    a = C.ask_stock("Why did operating cash flow fall?", "XYZ", RESEARCH, FIN, ask=ask, loader=lambda u: PAGES)
    assert not a["refused"] and a["answer"].startswith("Management did not explain this") and "₹160 cr" in a["answer"]
