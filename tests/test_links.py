"""Push meets pull (10h, P8): which promises does a results card test? No network."""
from engine import links as L

CARD = {"ticker": "XYZ", "period": {"label": "Q4 FY26", "current": "2026-03-31"}}


def prom(pid, verdict, quarters=(), due=None, **kw):
    return {"id": pid, "statement": f"promise {pid}", "verdict": verdict, "due": due, "due_label": "Q4 FY27" if due else None,
            "facts": [{"quarter": q} for q in quarters], **kw}


def test_matches_by_quarter_fact_fiscal_year_fact_or_due_date():
    research = {"promises": [
        prom("P1", "Delivered", ["Q3 FY26", "Q4 FY26"]),         # evidence includes this quarter
        prom("P2", "Missed", ["FY26"]),                           # Q4 completes FY26
        prom("P3", "Partial", ["Q1 FY26"], due="2026-03-31"),    # fell due in this quarter
        prom("P4", "Delivered", ["Q2 FY26"]),                     # an older quarter: not tested here
        prom("P5", "Too early", [], due="2027-03-31"),
    ]}
    out = L.promises_for_card(CARD, research)
    assert out["available"] and [p["id"] for p in out["items"]] == ["P2", "P3", "P1"]     # Missed first
    assert out["open_count"] == 1 and out["next_test"]["statement"] == "promise P5"


def test_limit_and_no_research():
    research = {"promises": [prom(f"P{i}", "Delivered", ["Q4 FY26"]) for i in range(5)]}
    out = L.promises_for_card(CARD, research)
    assert len(out["items"]) == 3 and out["more"] == 2
    none = L.promises_for_card(CARD, None)
    assert none["available"] is False and none["items"] == []


def test_api_card_carries_promises_but_does_not_store_them():
    import glob, json
    from fastapi.testclient import TestClient
    import api
    for path in glob.glob("snapshot/cards/*.json"):
        d = json.load(open(path, encoding="utf-8"))
        if d.get("ticker") == "POLYCAB" and d.get("kind") == "results" and d.get("status") == "ok" and d["period"]["label"] == "Q2 FY27":
            j = TestClient(api.app).get(f"/api/card/{d['filing_id']}").json()
            assert j["promises"]["available"] and j["promises"]["items"][0]["verdict"] == "Delivered"
            assert "promises" not in d                          # the stored card is unchanged
            return
    raise AssertionError("POLYCAB Q2 FY27 card not found")
