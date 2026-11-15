"""'Brief me' (FE-9, D-091) and the snapshot refresh's change detection (BE-7, D-090). No network."""
from engine.brief import brief_me


def card(kind, ticker="XYZ", company="XYZ Industries Limited", **extra):
    return {"kind": kind, "ticker": ticker, "company": company, "title": "A filing", **extra}


MOVE = {"ticker": "ABC", "company": "ABC Paints Limited", "type": "price", "value": -3.4}


def test_three_sentences_that_add_up():
    payload = {"window": "7d", "routine_count": 9, "alert_only": [MOVE, {**MOVE, "ticker": "DEF", "type": "volume", "value": 2.5}],
               "cards": [card("management_change", mgmt={"key_role": True, "headline": "x",
                              "first": {"event": "reappointment", "person": "V. Rangan", "role": "Whole-time Director",
                                        "effective_date": "2026-11-23"}}),
                         card("results", results={"period": "Q2 FY27", "verdict": "Revenue up 16% year on year."})]}
    b = brief_me(payload)
    assert len(b["sentences"]) == 3 and b["text"] == " ".join(b["sentences"])
    assert b["sentences"][0] == ("In the last 7 days, 4 things matter: 1 management change, 1 results filing "
                                 "and 2 unusual moves.")
    assert b["sentences"][1] == ("Top of the list is a key management change at XYZ Industries: "
                                 "V. Rangan re-appointed as Whole-time Director from 23 Nov 2026.")
    assert b["sentences"][2] == "ABC Paints moved down 3.4 percent with no filing to explain it, and 1 more unusual move."


def test_results_top_and_quiet_day():
    b = brief_me({"window": "24h", "alert_only": [], "routine_count": 0,
                  "cards": [card("results", results={"period": "Q2 FY27", "verdict": "All 4 lines up year on year."})]})
    assert b["sentences"][1] == "Top of the list: XYZ Industries's Q2 FY27 results, with all 4 lines up year on year."
    assert b["sentences"][2] == "No stock made an unusual move without a filing to explain it."
    quiet = brief_me({"window": "24h", "cards": [], "alert_only": [], "routine_count": 1})
    assert quiet["sentences"][0] == "In the last 24 hours, nothing that matters changed across your stocks."
    assert "1 routine filings" not in quiet["text"] and len(quiet["sentences"]) == 3


def test_research_rebuilt_only_when_documents_change():
    from refresh_snapshot import research_documents_changed
    saved = {"sources": {"transcripts": [{"date": "2026-10-19T10:00:00"}], "results": [{"filing_id": "1"}]}}
    same = {"transcripts": [{"date": "2026-10-19T12:00:00"}], "results": [{"id": "1"}]}
    assert research_documents_changed(saved, same) is False
    assert research_documents_changed(saved, {**same, "transcripts": [{"date": "2027-01-20T10:00:00"}]}) is True
    assert research_documents_changed(saved, {**same, "results": [{"id": "1"}, {"id": "2"}]}) is True
    assert research_documents_changed(saved, {**same, "results": [{"id": "1"}, {"id": "3", "candidate": True}]}) is False
    assert research_documents_changed(None, same) is True


def test_refresh_ignores_documents_already_seen_even_if_unreadable():
    from refresh_snapshot import research_documents_changed
    saved = {"documents_seen": {"transcripts": ["2026-10-19"], "results": ["1", "2"]},
             "sources": {"transcripts": [], "results": [{"filing_id": "1"}]}}     # "2" was unreadable
    found = {"transcripts": [{"date": "2026-10-19T09:00:00"}], "results": [{"id": "1"}, {"id": "2"}]}
    assert research_documents_changed(saved, found) is False
