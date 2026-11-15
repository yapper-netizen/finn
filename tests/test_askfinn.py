"""Ask FINN across the portfolio (D-107, 5A): the model only fills a query; Python answers. No network."""
from datetime import date, datetime

from engine import askfinn as A

PORT = {"TCS": "Tata Consultancy Services Limited", "INFY": "Infosys Limited", "TITAN": "Titan Company Limited"}
PULSE = {"stocks": [{"ticker": "TCS", "company": PORT["TCS"], "move": -1.4, "move_5d": -3.5, "vol_x": 0.6, "date": "2026-11-13"},
                    {"ticker": "INFY", "company": PORT["INFY"], "move": 2.0, "move_5d": 1.0, "vol_x": 2.5, "date": "2026-11-13"},
                    {"ticker": "TITAN", "company": PORT["TITAN"], "move": -3.0, "move_5d": 0.2, "vol_x": 1.1, "date": "2026-11-13"}],
         "events": [{"ticker": "TITAN", "date": "2026-11-20", "kind": "action", "title": "Ex-date: Interim Dividend - Rs 4"}],
         "expected": [{"ticker": "TCS", "date": "2027-01-12", "kind": "expected", "title": "Results expected around this date"}]}
FILINGS = [{"ticker": "TITAN", "date": "2026-11-12T10:00:00", "title": "Change in Director(s)", "pdf_url": "p", "id": "1",
            "category": "Change in Directors/ Key Managerial Personnel/ Auditor/ Compliance Officer/ Share Transfer Agent"},
           {"ticker": "TCS", "date": "2026-11-01T10:00:00", "title": "Change in Director(s)", "pdf_url": "p", "id": "2",
            "category": "Change in Directors/ Key Managerial Personnel/ Auditor/ Compliance Officer/ Share Transfer Agent"}]
NOW = datetime(2026, 11, 15, 12, 0)


def model(query):
    calls = []

    def ask(prompt, strong, validate, use_cache, meta, schema):
        calls.append(prompt)
        assert not strong and "Do NOT answer it" in prompt
        return validate(query)
    return ask, calls


def test_filings_answered_by_python_from_the_query():
    ask, _ = model({"intent": "filings", "categories": ["management_change"], "days": 7, "tickers": []})
    out = A.ask_portfolio("Which stocks had a management change this week?", FILINGS, PULSE, NOW, ask=ask)
    assert out["answered_by"] == "python" and out["parsed_by"] == "ai"
    assert out["answer"].startswith("1 filing (management change) in the last 7 days") and out["items"][0]["ticker"] == "TITAN"


def test_moves_events_and_unknown_tickers_dropped():
    ask, _ = model({"intent": "moves", "direction": "down", "limit": 2, "tickers": ["NOTMINE"]})
    out = A.ask_portfolio("Top 2 losers", FILINGS, PULSE, NOW, ask=ask)
    assert "TITAN -3.00%, TCS -1.40%" in out["answer"] and out["query"]["tickers"] == []
    ask, _ = model({"intent": "events", "tickers": ["TCS"]})
    out = A.ask_portfolio("When are TCS results?", FILINGS, PULSE, NOW, ask=ask)
    assert out["items"][0]["text"].endswith("(estimate)") and "1 estimated" in out["answer"]


def test_advice_refused_without_calling_the_model():
    ask, calls = model({"intent": "filings"})
    out = A.ask_portfolio("Should I buy Titan?", FILINGS, PULSE, NOW, ask=ask)
    assert out["refused"] and not calls


def test_company_question_routes_to_the_stock_copilot():
    ask, _ = model({"intent": "company", "tickers": ["TCS"]})
    seen = []
    out = A.ask_portfolio("What did TCS say about AI demand?", FILINGS, PULSE, NOW, ask=ask,
                          company_asker=lambda q, t: seen.append(t) or {"answer": "x", "refused": False, "answered_by": "ai", "citations": []})
    assert seen == ["TCS"] and out["routed_to"] == "TCS"


def test_rules_parser_when_ai_fails():
    def broken(*a, **k):
        raise RuntimeError("429 quota")
    out = A.ask_portfolio("Which stocks had unusual volume this week?", FILINGS, PULSE, NOW, ask=broken)
    assert out["parsed_by"] == "rules" and out["query"]["intent"] == "moves" and out["answer"].startswith("Highest volume")
    q = A.rule_query("Any upcoming dividend for Titan?", PORT)
    assert q.intent == "events" and q.tickers == ["TITAN"] and "dividend" in q.categories
