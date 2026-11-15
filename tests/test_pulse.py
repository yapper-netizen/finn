"""Pulse (D-107): stock rows, events parsing, upcoming/recent/expected, API. No network."""
from datetime import date

import pandas as pd
from fastapi.testclient import TestClient

from data import events as E
from engine import pulse as P
from engine.feed import FeedData


def prices(last_move=5.0, vol_x=3.0, n=26):
    dates = pd.bdate_range(end="2026-11-13", periods=n)
    close = [100.0] * (n - 1) + [100.0 * (1 + last_move / 100)]
    vol = [1000] * (n - 1) + [int(1000 * vol_x)]
    return pd.DataFrame({"Date": dates, "Close": close, "Volume": vol})


def test_stock_row_moves_and_volume_multiple():
    r = P.stock_row("TCS", prices(5.0, 3.0))
    assert r["move"] == 5.0 and r["move_5d"] == 5.0 and r["vol_x"] == 3.0 and r["date"] == "2026-11-13"
    assert P.stock_row("TCS", None)["move"] is None
    assert P.stock_row("TCS", prices(n=10))["vol_x"] is None          # not a full 20-day window


def test_parse_board_and_actions():
    b = E.parse_board([{"purpose": "Financial Results", "bm_desc": "To approve results", "date": "16-Jan-2027"},
                       {"purpose": "Fund Raising", "bm_desc": "QIP", "date": "20-Nov-2026"}, {"date": "bad"}], "TCS")
    assert [(e["kind"], e["date"]) for e in b] == [("results", "2027-01-16"), ("board", "2026-11-20")]
    a = E.parse_actions([{"exDate": "25-Nov-2026", "recDate": "25-Nov-2026", "subject": "Interim Dividend - Rs 12"}], "TCS")
    assert a[0]["kind"] == "action" and a[0]["title"].startswith("Ex-date: Interim Dividend")


def test_upcoming_recent_and_expected():
    today = date(2026, 11, 15)
    ev = [{"ticker": "TCS", "date": "2026-11-20", "kind": "board", "title": "x"},
          {"ticker": "TCS", "date": "2026-11-20", "kind": "board", "title": "x"},          # duplicate
          {"ticker": "TCS", "date": "2026-12-20", "kind": "board", "title": "far"},
          {"ticker": "INFY", "date": "2026-11-12", "kind": "action", "title": "past"},
          {"ticker": "INFY", "date": "2026-01-14", "kind": "results", "title": "r"},
          {"ticker": "TCS", "date": "2026-01-12", "kind": "results", "title": "r"},
          {"ticker": "TCS", "date": "2027-01-11", "kind": "results", "title": "confirmed"}]
    assert [e["date"] for e in E.upcoming(ev, today)] == ["2026-11-20"]
    assert [e["title"] for e in E.recent(ev, today)] == ["past"]
    exp = E.expected_results(ev, today)
    assert [(e["ticker"], e["date"]) for e in exp] == [("INFY", "2027-01-14")]        # TCS already confirmed
    assert "last year's meeting was on 14 Jan 2026" in exp[0]["detail"]


def test_build_pulse_breadth_filings_and_calendar():
    data = FeedData(filings=[{"ticker": "TCS", "company": "TCS", "date": "2026-11-13T10:00:00", "title": "Change in Director(s)",
                              "category": "Change in Directors/ Key Managerial Personnel/ Auditor/ Compliance Officer/ Share Transfer Agent", "pdf_url": "", "id": "1"}],
                    prices={"TCS": prices(5.0, 3.0), "INFY": prices(-2.0, 0.5)}, fallback_used=False)
    ev = {"events": [{"ticker": "TCS", "date": "2026-11-20", "kind": "board", "title": "Board meeting: Dividend", "detail": ""}],
          "as_of": "x", "live": True}
    out = P.build_pulse(data, ev, date(2026, 11, 15))
    rows = {r["ticker"]: r for r in out["stocks"]}
    assert rows["TCS"]["filings"] and rows["INFY"]["move"] == -2.0
    assert out["breadth"]["up"] == 1 and out["breadth"]["down"] == 1 and out["events"][0]["company"]
    assert len(out["stocks"]) == 18 and out["session_date"] == "2026-11-13"


def test_events_cache_serves_snapshot_then_live():
    import time
    cache = E.EventsCache(fetcher=lambda syms: ([{"ticker": "TCS", "date": "2026-11-20", "kind": "board", "title": "x"}], []))
    first = cache.get(["TCS"])
    assert first["live"] is False                      # snapshot answers at once
    for _ in range(50):
        if cache.get(["TCS"])["live"]:
            break
        time.sleep(0.02)
    assert cache.get(["TCS"])["events"][0]["title"] == "x"


def test_api_pulse_offline(monkeypatch):
    import api
    monkeypatch.setattr(api.events_cache, "get", lambda syms: {"events": [], "as_of": None, "live": False})
    j = TestClient(api.app).get("/api/pulse").json()
    assert len(j["stocks"]) == 18 and "breadth" in j and j["events"] == []


def test_alert_history_matches_alert_maths():
    data = FeedData(filings=[], prices={"TCS": prices(5.0, 3.0), "INFY": prices(-2.0, 0.5)}, fallback_used=False)
    out = P.alert_history(data, sessions=3)
    last = [r for r in out["rows"] if r["ticker"] == "TCS" and r["date"] == "2026-11-13"][0]
    assert last["move"] == 5.0 and last["vol_x"] == 3.0                    # same as check_alerts: close vs prev, volume vs 20-day mean
    assert len(out["sessions"]) == 3 and out["sessions"][-1] == "2026-11-13"
    flat = [r for r in out["rows"] if r["date"] == out["sessions"][0] and r["ticker"] == "TCS"][0]
    assert flat["move"] == 0.0 and flat["vol_x"] == 1.0


def test_api_preview_offline():
    import api
    j = TestClient(api.app).get("/api/preview?sessions=5").json()
    assert len(j["sessions"]) == 5 and j["rows"] and {"ticker", "date", "move", "vol_x"} <= set(j["rows"][0])
