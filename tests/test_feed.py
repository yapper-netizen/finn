"""FeedCache tests: first load, snapshot fallback, stale-while-revalidate, failures (no network)."""
import threading
import time

import pandas as pd

from engine.feed import FeedCache, FeedData, load_all


def data(tag: str = "x") -> FeedData:
    return FeedData(filings=[{"ticker": tag}], prices={}, fallback_used=False)


def snap() -> FeedData:
    return FeedData(filings=[{"ticker": "SNAP"}], prices={}, fallback_used=True, errors=["snapshot"])


def wait_until(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_first_get_waits_for_live_load():
    c = FeedCache(loader=lambda: data("LIVE"), snapshot_loader=snap, wait=2)
    assert c.get().filings[0]["ticker"] == "LIVE" and c.ready


def test_slow_first_load_falls_back_to_snapshot_without_blocking_forever():
    release = threading.Event()

    def slow():
        release.wait(5)
        return data("LIVE")

    c = FeedCache(loader=slow, snapshot_loader=snap, wait=0.1)
    t0 = time.time()
    first = c.get()
    assert first.fallback_used and first.filings[0]["ticker"] == "SNAP"
    assert time.time() - t0 < 1.5
    release.set()
    assert wait_until(lambda: c.ready)
    assert c.get().filings[0]["ticker"] == "LIVE"


def test_failed_first_load_uses_snapshot_and_records_error():
    def boom():
        raise RuntimeError("nse down")

    c = FeedCache(loader=boom, snapshot_loader=snap, wait=1)
    assert c.get().fallback_used
    assert "nse down" in (c.last_error or "")


def test_stale_data_served_instantly_then_refreshed_in_background():
    now = [0.0]
    calls = {"n": 0}
    gate = threading.Event()

    def loader():
        calls["n"] += 1
        if calls["n"] > 1:
            gate.wait(3)
        return data(f"v{calls['n']}")

    c = FeedCache(loader=loader, snapshot_loader=snap, ttl=10, wait=2, clock=lambda: now[0])
    assert c.get().filings[0]["ticker"] == "v1"
    now[0] = 100.0                                   # expired
    assert c.get().filings[0]["ticker"] == "v1"      # stale answer, no waiting
    gate.set()
    assert wait_until(lambda: c.get().filings[0]["ticker"] == "v2")


def test_fresh_data_does_not_trigger_reload():
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return data()

    c = FeedCache(loader=loader, snapshot_loader=snap, ttl=900, wait=2)
    c.get()
    c.get()
    c.get()
    assert calls["n"] == 1


def test_failed_refresh_keeps_old_data():
    now = [0.0]
    state = {"fail": False}

    def loader():
        if state["fail"]:
            raise RuntimeError("blocked")
        return data("OLD")

    c = FeedCache(loader=loader, snapshot_loader=snap, ttl=10, wait=2, clock=lambda: now[0])
    c.get()
    state["fail"], now[0] = True, 100.0
    c.get()
    assert wait_until(lambda: c.last_error is not None)
    assert c.get().filings[0]["ticker"] == "OLD"


def test_load_all_collects_results_and_never_raises(monkeypatch):
    import engine.feed as feed

    df = pd.DataFrame({"Date": pd.to_datetime(["2026-11-13", "2026-11-14"]), "Close": [1.0, 2.0], "Volume": [1, 2]})

    def fake_filings(t, days):
        if t == "BAD":
            raise RuntimeError("blocked")
        return [{"id": "1", "date": "2026-11-14T10:00:00", "title": "t", "category": "c", "pdf_url": ""}], "snapshot"

    monkeypatch.setattr(feed.filings_mod, "fetch_filings", fake_filings)
    monkeypatch.setattr(feed.prices_mod, "fetch_prices", lambda t: (df, "NSE"))
    out = load_all(["TCS", "BAD"])
    assert [f["ticker"] for f in out.filings] == ["TCS"] and out.fallback_used
    assert set(out.prices) == {"TCS", "BAD"} and any("BAD filings" in e for e in out.errors)
