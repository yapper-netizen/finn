"""Card service and background prebuilder (API-3, D-078). No network, no AI."""
from engine import cards
from engine.feed import FeedCache, FeedData

RESULTS = {"id": "555", "ticker": "XYZ", "company": "XYZ Ltd", "date": "2026-11-14T16:00:00",
           "category": "Outcome of Board Meeting", "title": "Unaudited financial results for the quarter",
           "pdf_url": "https://nsearchives.nseindia.in/corporate/XYZ.pdf"}
DIVIDEND = {**RESULTS, "id": "556", "category": "Dividend", "title": "Interim dividend"}


def feed(*filings) -> FeedData:
    return FeedData(filings=list(filings), prices={}, fallback_used=False)


def builder(built, card=None, **kw):
    def build(f):
        built.append(f["id"])
        return card or {"status": "ok"}
    return cards.CardPrebuilder(build=build, pace_s=0, enabled=True, sleep=lambda s: None, **kw)


def test_only_results_without_a_stored_card_are_queued(monkeypatch):
    monkeypatch.setattr(cards, "stored_card", lambda fid: {"status": "ok"} if fid == "999" else None)
    built: list[str] = []
    pb = builder(built)
    monkeypatch.setattr(pb, "_start", lambda: None)          # run the queue in this thread instead
    stored = {**RESULTS, "id": "999"}
    assert pb.enqueue_from(feed(RESULTS, DIVIDEND, stored)) == 1
    assert pb.enqueue_from(feed(RESULTS)) == 0               # already queued: not twice
    pb.run_pending()
    assert built == ["555"] and pb.built == ["555"]


def test_failed_build_is_retried_at_most_max_tries(monkeypatch):
    monkeypatch.setattr(cards, "stored_card", lambda fid: None)
    built: list[str] = []
    pb = builder(built, card={"status": "could not extract", "retryable": True}, max_tries=2)
    monkeypatch.setattr(pb, "_start", lambda: None)
    for _ in range(4):                                       # four feed refreshes
        pb.enqueue_from(feed(RESULTS))
        pb.run_pending()
    assert built == ["555", "555"] and pb.built == []


def test_disabled_without_key_does_nothing(monkeypatch):
    monkeypatch.setattr(cards, "stored_card", lambda fid: None)
    pb = cards.CardPrebuilder(build=lambda f: {}, enabled=False)
    assert pb.enqueue_from(feed(RESULTS)) == 0


def test_feed_refresh_calls_the_hook_and_survives_its_failure():
    seen = []
    cache = FeedCache(loader=lambda: feed(RESULTS), on_loaded=lambda d: seen.append(len(d.filings)))
    cache._refresh()
    assert seen == [1] and cache.ready

    def boom(d):
        raise RuntimeError("hook broke")
    cache = FeedCache(loader=lambda: feed(RESULTS), on_loaded=boom)
    cache._refresh()
    assert cache.ready and cache.last_error is None          # the feed still serves data


def test_get_card_rejects_bad_ids_and_non_results():
    import pytest
    with pytest.raises(ValueError):
        cards.get_card({**RESULTS, "id": "../etc"})
    with pytest.raises(ValueError):
        cards.get_card(DIVIDEND)


def test_every_saved_results_filing_has_a_committed_card():
    """OPS-3 for cards: what reviewers open must be precomputed (Render's disk is wiped)."""
    from run_cards import results_filings
    missing = [f"{f['ticker']} {f['id']}" for f in results_filings([]) if not cards._snapshot_path(f["id"]).exists()]
    assert missing == []
