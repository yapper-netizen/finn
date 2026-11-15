"""Management-change card (EN-6), board-outcome promotion (D-087) and the full offline test (QA-6)."""
from datetime import date

import pytest

from engine import cards, mgmt
from engine.mgmt import MgmtOut, build_mgmt_card

PAGE_1 = """13th November, 2026
Sub: Change in Management of the Company
The Board approved the appointment of Mr. Ravi Kumar Menon as Chief Financial Officer of the Company
with effect from 1st December, 2026. Ms. Anita Rao, Chief Financial Officer, has resigned
with effect from 30th November, 2026 to pursue opportunities outside the Company."""
PAGE_2 = """Annexure A - Details under Regulation 30
Name Mr. Ravi Kumar Menon Ms. Anita Rao
Brief profile Mr. Ravi Kumar Menon is a Chartered Not applicable
Accountant with 22 years of experience in finance at two listed consumer companies."""
PAGES = [PAGE_1, PAGE_2]
FILING = {"id": "777", "ticker": "XYZ", "company": "XYZ Ltd", "date": "2026-11-13T18:00:00",
          "category": "Change in Management", "title": "Change in management",
          "pdf_url": "https://nsearchives.nseindia.in/corporate/XYZ_mgmt.pdf"}


def change(**kw):
    base = {"event": "appointment", "person": "Ravi Kumar Menon", "role": "Chief Financial Officer",
            "previous_role": None, "effective_date": "2026-12-01", "reason": None,
            "profile_quote": "Mr. Ravi Kumar Menon is a Chartered Accountant with 22 years of experience in finance",
            "bio": "A chartered accountant with 22 years in finance.", "page": 2}
    return {**base, **kw}


def fake(*changes):
    def extractor(prompt, meta):
        meta.update(model="fake", cached=False)
        return MgmtOut.model_validate({"changes": list(changes)})
    return extractor


def test_appointment_and_exit_are_verified_and_key_role_flagged():
    card = build_mgmt_card(FILING, PAGES, extractor=fake(
        change(), change(event="resignation", person="Anita Rao", effective_date="2026-11-30",
                         profile_quote=None, bio=None, reason="To pursue opportunities outside")))
    assert card["status"] == "ok" and card["kind"] == "management" and card["key_role"] is True
    menon, rao = card["changes"]
    assert menon["profile"]["page"] == 2 and menon["effective_date"] == "2026-12-01"   # profile from 2 interleaved columns
    assert rao["label"] == "Resigned" and rao["profile"] is None
    assert card["headline"].startswith("Appointed: Ravi Kumar Menon, Chief Financial Officer, from 1 Dec 2026")


def test_invented_person_date_and_profile_are_not_shown():
    card = build_mgmt_card(FILING, PAGES, extractor=fake(
        change(person="Suresh Iyer"),                                        # not in the filing
        change(effective_date="2026-12-15",                                  # date not printed
               profile_quote="Mr. Ravi Kumar Menon was CEO of a global bank for 30 years")))   # invented
    assert [c["person"] for c in card["changes"]] == ["Ravi Kumar Menon"]
    ch = card["changes"][0]
    assert ch["effective_date"] is None and ch["profile"] is None
    assert len(card["warnings"]) == 3


def test_scanned_filing_and_ai_failure():
    assert "scanned" in build_mgmt_card(FILING, ["", ""], extractor=fake())["reason"]

    def boom(prompt, meta):
        raise RuntimeError("All AI calls failed")
    card = build_mgmt_card(FILING, PAGES, extractor=boom)
    assert card["status"] == "could not extract" and card["retryable"] is True


@pytest.mark.parametrize("role, key", [
    ("Chief Financial Officer", True), ("Managing Director & CEO", True), ("Vice-Chairman", True),
    ("Whole-time Director (designated as Executive Director)", True), ("Company Secretary", False),
    ("Vice President - FMCG", False), ("President and Chief Executive Officer for Americas 2 Strategic Market Unit", False),
    ("Independent Director", False)])
def test_key_role_rule(role, key):
    assert mgmt.is_key_role(role) is key


def test_dates_in_common_print_forms():
    d = date(2026, 11, 3)
    for text in ("with effect from November 03, 2026", "w.e.f. 3rd November 2026", "on 03.11.2026", "from 3 Nov 2026"):
        assert mgmt.date_in_text(d, text), text
    assert not mgmt.date_in_text(d, "with effect from 13th November 2026")


# ---------------------------------------------------------------- board outcome promotion (D-087)

BOARD = {"id": "888", "ticker": "XYZ", "company": "XYZ Ltd", "date": "2026-10-15T15:00:00",
         "category": "Outcome of Board Meeting", "title": "Outcome of the Board Meeting",
         "pdf_url": "https://nsearchives.nseindia.in/corporate/XYZ_bm.pdf"}


def test_board_outcome_candidate_window():
    assert cards.is_results_candidate(BOARD)                                   # 15 days after 30 Sep
    assert not cards.is_results_candidate({**BOARD, "date": "2026-12-28T10:00:00"})  # 89 days after
    assert not cards.is_results_candidate({**BOARD, "category": "Dividend", "title": "Dividend"})


def test_promotion_only_when_a_statement_is_found(monkeypatch):
    from tests.test_results import COVER, PAGE
    assert cards.promote_if_results(BOARD, pages_loader=lambda url: [COVER])["status"] == "not results"
    built = {}
    monkeypatch.setattr(cards, "stored_card", lambda fid: None)
    monkeypatch.setattr(cards, "save_card", lambda card, path: built.update(card=card))
    monkeypatch.setattr(cards, "build_card", lambda f, pages: {"status": "ok", "kind": "results", "seen": f.get("kind_override")})
    out = cards.promote_if_results(BOARD, pages_loader=lambda url: [COVER, PAGE])
    assert out["status"] == "ok" and out["seen"] == "results"


def test_apply_promotions_marks_results(monkeypatch):
    monkeypatch.setattr(cards, "stored_card", lambda fid: {"kind": "results", "status": "ok"} if fid == "888" else None)
    from engine.classifier import classify
    out = cards.apply_promotions([BOARD, {**BOARD, "id": "889"}])
    assert [classify(f) for f in out] == ["results", "board_outcome"]
    assert "kind_override" not in BOARD                                        # inputs not mutated


# ---------------------------------------------------------------- QA-6: everything offline

def test_whole_app_works_with_the_network_blocked(monkeypatch):
    """Prices, filings, PDFs and AI all fail: Today, saved cards and saved research still answer."""
    from fastapi.testclient import TestClient
    import api
    from data import docs, filings as filings_mod, prices as prices_mod
    from engine import llm
    from engine.feed import FeedCache, load_all

    def dead(*a, **k):
        raise ConnectionError("network down")
    for mod, name in ((filings_mod, "_fetch_nse"), (prices_mod, "_fetch_one"), (docs, "download_pdf"), (llm, "_call_once")):
        monkeypatch.setattr(mod, name, dead)
    for mod in (filings_mod, prices_mod, llm):
        monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(api, "feed_cache", FeedCache(loader=load_all))
    c = TestClient(api.app)
    today = c.get("/api/digest?window=7d").json()
    assert today["fallback_used"] is True and today["cards"]
    assert c.get("/api/card/106857040").json()["status"] == "ok"           # IRCTC results (saved)
    assert c.get("/api/card/106858492").json()["kind"] == "management"     # DMART management (saved)
    assert c.get("/api/research/POLYCAB").json()["status"] == "ready"      # research (saved)
