"""Ranker, toggles and digest tests (no network)."""
from datetime import datetime

import pytest

from engine.digest import build_digest
from engine.ranker import rank_filings

NOW = datetime(2026, 11, 14, 12, 0, 0)


def fil(ticker, when, desc, title="", id_=None):
    return {"id": id_ or f"{ticker}{when}", "ticker": ticker, "date": when, "category": desc, "title": title}


RESULTS = "Outcome of Board Meeting"
RESULT_TITLE = "has submitted to the Exchange, the financial results for the period"
MGMT = "Change in Management"
DIV = "Dividend"
MEET = "Analysts/Institutional Investor Meet/Con. Call Updates"


def test_tier_order_high_medium_low():
    out = rank_filings([fil("A", "2026-11-14T10:00:00", MEET), fil("B", "2026-11-14T09:00:00", DIV),
                        fil("C", "2026-11-14T08:00:00", RESULTS, RESULT_TITLE)])
    assert [i["tier"] for i in out] == ["High", "Medium", "Low"]


def test_alert_boost_orders_within_tier_but_keeps_tier():
    older_moved = fil("A", "2026-11-14T08:00:00", MGMT)
    newer = fil("B", "2026-11-14T11:00:00", MGMT)
    alerts = {"A": [{"date": "2026-11-14", "type": "price"}]}
    out = rank_filings([newer, older_moved], alerts)
    assert [i["ticker"] for i in out] == ["A", "B"]
    assert out[0]["moved_same_day"] and out[0]["tier"] == "High"


def test_alert_on_other_day_gives_no_boost():
    out = rank_filings([fil("A", "2026-11-13T08:00:00", MGMT)], {"A": [{"date": "2026-11-14"}]})
    assert out[0]["moved_same_day"] is False


def test_ties_break_newest_then_ticker():
    out = rank_filings([fil("B", "2026-11-14T10:00:00", MGMT), fil("A", "2026-11-14T10:00:00", MGMT),
                        fil("C", "2026-11-14T11:00:00", MGMT)])
    assert [i["ticker"] for i in out] == ["C", "A", "B"]


def test_toggle_off_moves_high_category_to_routine():
    out = rank_filings([fil("A", "2026-11-14T10:00:00", MGMT)], toggles={"management_change": False})
    assert out[0]["tier"] == "Low" and out[0]["muted"] and not out[0]["alert_chip"]
    assert out[0]["base_tier"] == "High"


def test_toggle_on_high_gets_alert_chip_but_medium_does_not():
    out = rank_filings([fil("A", "2026-11-14T10:00:00", MGMT), fil("B", "2026-11-14T10:00:00", DIV)])
    chips = {i["ticker"]: i["alert_chip"] for i in out}
    assert chips == {"A": True, "B": False}


def test_toggle_on_for_low_category_stays_low():
    out = rank_filings([fil("A", "2026-11-14T10:00:00", MEET)], toggles={"investor_meetings": True})
    assert out[0]["tier"] == "Low"


# --- digest ---
def sample():
    return [
        fil("A", "2026-11-14T09:00:00", MGMT),                      # 3h ago
        fil("B", "2026-11-13T09:00:00", RESULTS, RESULT_TITLE),     # 27h ago
        fil("C", "2026-11-10T09:00:00", DIV),                       # 4.1 days ago
        fil("D", "2026-11-14T10:00:00", MEET),                      # 2h ago, routine
    ]


def test_window_counts():
    d24 = build_digest(sample(), window="24h", now=NOW)["counts"]
    d3 = build_digest(sample(), window="3d", now=NOW)["counts"]
    d7 = build_digest(sample(), window="7d", now=NOW)["counts"]
    assert (d24["cards"], d24["summaries"], d24["routine"]) == (1, 0, 1)
    assert (d3["cards"], d3["total"]) == (2, 3)
    assert (d7["cards"], d7["summaries"], d7["routine"], d7["total"]) == (2, 1, 1, 4)


def test_cards_are_uncapped_d065():
    many = [fil(f"T{i}", f"2026-11-14T0{i}:00:00", MGMT) for i in range(1, 9)]
    assert build_digest(many, window="24h", now=NOW)["counts"]["cards"] == 8


def test_empty_24h_widens_to_latest_day_with_filings():
    old = [fil("A", "2026-11-11T09:00:00", MGMT), fil("B", "2026-11-11T15:00:00", DIV),
           fil("C", "2026-11-09T09:00:00", MGMT)]
    d = build_digest(old, window="24h", now=NOW)
    assert d["widened"] is True and d["as_of"] == "2026-11-11"
    assert d["counts"]["total"] == 2


def test_no_filings_at_all_is_empty_not_widened():
    d = build_digest([], window="24h", now=NOW)
    assert d["widened"] is False and d["counts"]["total"] == 0


def test_non_empty_window_does_not_widen():
    assert build_digest(sample(), window="24h", now=NOW)["widened"] is False


def test_unknown_window_rejected():
    with pytest.raises(ValueError):
        build_digest([], window="30d", now=NOW)


def test_digest_respects_toggles():
    d = build_digest(sample(), window="7d", toggles={"management_change": False}, now=NOW)
    assert d["counts"]["cards"] == 1 and d["counts"]["routine"] == 2


def test_buried_reasons_are_specific_and_honest():
    from engine.classifier import buried_reason
    f = lambda cat, title="x": {"category": cat, "title": title}
    assert "switched this type off" in buried_reason(f("Dividend"), "dividend", True)
    assert "Trading-window" in buried_reason(f("Trading Window"), "unclassified", False)
    assert "Employee share-option" in buried_reason(f("ESOP/ESOS/ESPS"), "unclassified", False)
    assert "call notice or transcript" in buried_reason(f("Analysts/Institutional Investor Meet/Con. Call Updates"), "earnings_call", False)
    assert "Compliance paperwork" in buried_reason(f("General Updates"), "unclassified", False)


def test_routine_items_carry_why_and_digest_groups_them():
    from datetime import datetime
    from engine.digest import build_digest
    now = datetime(2026, 11, 14, 12, 0)
    filings = [
        {"ticker": "AAA", "date": "2026-11-14T09:00:00", "title": "Trading window closure", "category": "Trading Window", "id": "1"},
        {"ticker": "BBB", "date": "2026-11-14T09:30:00", "title": "Change in Director(s)", "category": "Change in Directors/ Key Managerial Personnel/ Auditor/ Compliance Officer/ Share Transfer Agent", "id": "2"},
        {"ticker": "CCC", "date": "2026-11-14T10:00:00", "title": "Dividend declared", "category": "Dividend", "id": "3"},
    ]
    d = build_digest(filings, {}, "24h", {"dividend": False}, now)
    assert d["cards"][0]["why"] is None
    assert all(r["why"] for r in d["routine"])
    assert {(g["kind"], g["muted"], g["count"]) for g in d["routine_groups"]} == {("unclassified", False, 1), ("dividend", True, 1)}
