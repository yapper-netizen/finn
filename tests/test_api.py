"""Today assembly and API endpoint tests (no network)."""
from datetime import datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import api
import config
from engine.feed import FeedData
from engine.today import build_today

NOW = datetime(2026, 11, 14, 12, 0, 0)


def prices(last_move_pct: float = 8.0, last_vol_x: float = 3.0) -> pd.DataFrame:
    """25 flat days, then a final day with the given move and volume multiple."""
    dates = pd.bdate_range(end="2026-11-13", periods=25)
    close = [100.0] * 24 + [100.0 * (1 + last_move_pct / 100)]
    vol = [1000] * 24 + [int(1000 * last_vol_x)]
    return pd.DataFrame({"Date": dates, "Close": close, "Volume": vol})


def filing(ticker, when, desc, title="", id_="1"):
    return {"id": id_, "ticker": ticker, "company": f"{ticker} Ltd", "date": when,
            "category": desc, "title": title, "pdf_url": "", "subcategory": ""}


def fake_data(fallback=False) -> FeedData:
    return FeedData(
        filings=[
            filing("AAA", "2026-11-13T10:00:00", "Change in Management", id_="a"),   # High, same day as AAA alert
            filing("BBB", "2026-11-13T09:00:00", "Dividend", id_="b"),                # Medium
            filing("CCC", "2026-11-13T08:00:00", "Analysts/Institutional Investor Meet/Con. Call Updates", id_="c"),
        ],
        prices={"AAA": prices(), "BBB": prices(0.5, 1.0), "DDD": prices(-9.0, 1.0)},
        fallback_used=fallback,
        errors=["note"] if fallback else [],
        fetched_at=NOW,
    )


class StubCache:
    def __init__(self, data: FeedData | Exception):
        self.data, self.ready, self.last_error = data, True, None

    def get(self):
        if isinstance(self.data, Exception):
            raise self.data
        return self.data


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "feed_cache", StubCache(fake_data()))
    return TestClient(api.app, raise_server_exceptions=False)


# --- build_today ---
def test_today_groups_and_same_day_flag():
    t = build_today(fake_data(), window="7d", now=NOW)
    assert t["counts"]["cards"] == 1 and t["counts"]["summaries"] == 1 and t["routine_count"] == 1
    card = t["cards"][0]
    assert card["ticker"] == "AAA" and card["moved_same_day"] and card["alert_chip"]


def test_alert_only_lists_stock_without_filing_that_day():
    t = build_today(fake_data(), window="7d", now=NOW)
    only = {a["ticker"] for a in t["alert_only"]}
    assert only == {"DDD"}                       # AAA also filed that day; BBB crossed nothing
    assert t["alert_only"][0]["type"] == "price" and t["session_date"] == "2026-11-13"


def test_thresholds_change_alerts():
    strict = build_today(fake_data(), window="7d", price=10.0, volume=5.0, now=NOW)
    assert strict["alert_only"] == [] and not strict["cards"][0]["moved_same_day"]
    assert strict["thresholds"] == {"price": 10.0, "volume": 5.0}


def test_off_categories_move_to_routine():
    t = build_today(fake_data(), window="7d", off={"management_change"}, now=NOW)
    assert t["counts"]["cards"] == 0 and t["routine_count"] == 2


def test_fallback_and_errors_pass_through():
    t = build_today(fake_data(fallback=True), window="7d", now=NOW)
    assert t["fallback_used"] is True and t["errors"] == ["note"]


# --- endpoints ---
def test_health_and_root(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["data_ready"] is True
    r = client.get("/")
    assert r.status_code == 200 and "FINN" in r.text


def test_digest_default_ok(client):
    r = client.get("/api/digest")
    j = r.json()
    assert r.status_code == 200 and j["window"] == config.DEFAULT_WINDOW
    for key in ("cards", "summaries", "routine", "alert_only", "widened", "fallback_used", "counts", "thresholds"):
        assert key in j


def test_digest_window_and_params(client):
    j = client.get("/api/digest?window=7d&price=10&volume=5&off=management_change,dividend").json()
    assert j["window"] == "7d" and j["thresholds"] == {"price": 10.0, "volume": 5.0}
    assert j["counts"]["cards"] == 0 and j["counts"]["routine"] == 3


@pytest.mark.parametrize("query,needle", [
    ("window=30d", "Unknown window"),
    ("price=abc", "price"),
    ("price=0", "price"),
    ("volume=99", "volume"),
    ("off=made_up", "Unknown categories"),
])
def test_bad_input_is_a_clear_json_error(client, query, needle):
    r = client.get(f"/api/digest?{query}")
    j = r.json()
    assert r.status_code == 400 and needle in j["error"] and j["fallback_used"] is False


def test_unexpected_error_returns_json_not_a_crash_page(monkeypatch):
    monkeypatch.setattr(api, "feed_cache", StubCache(RuntimeError("boom")))
    r = TestClient(api.app, raise_server_exceptions=False).get("/api/digest")
    assert r.status_code == 500 and r.headers["content-type"].startswith("application/json")
    assert "error" in r.json() and r.json()["fallback_used"] is False


def test_fallback_flag_reaches_client(monkeypatch):
    monkeypatch.setattr(api, "feed_cache", StubCache(fake_data(fallback=True)))
    assert TestClient(api.app).get("/api/digest?window=7d").json()["fallback_used"] is True


def test_config_endpoint_lists_categories_and_ranges(client):
    j = client.get("/api/config").json()
    keys = {c["key"] for c in j["categories"]}
    assert keys == set(config.CATEGORY_TIER) and j["windows"] == ["24h", "3d", "7d"]
    assert j["defaults"] == {"price": 5.0, "volume": 2.0}
